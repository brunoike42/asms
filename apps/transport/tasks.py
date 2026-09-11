"""
Transport Celery tasks — mirrors the event-workflow pattern in Appendix D
(e.g. D.1 Student Marked Absent: signal -> Celery task -> notification).

SMS sending is handled by apps.notifications.sms.send_sms(tenant, phone, message).
"""
import math
from datetime import datetime, timedelta

from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.utils import timezone

from apps.notifications.sms import send_sms
from .models import (
    VehicleLocationPing,
    BoardingEvent,
    Stop,
    RouteDeviationAlert,
    Vehicle,
    Driver,
)




OFF_ROUTE_THRESHOLD_METERS = 300
LOCATION_CACHE_TTL_SECONDS = 120


def _haversine_meters(lat1, lng1, lat2, lng2):
    """Distance between two lat/lng points in meters."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _distance_to_polyline_meters(lat, lng, path):
    """Cheapest possible planned-vs-actual check: minimum distance from the point to any
    vertex in the planned path. Good enough for the sparse waypoint lists used here; swap
    for a proper point-to-segment calc if routes get more geometrically complex."""
    if not path:
        return None
    return min(_haversine_meters(lat, lng, p["lat"], p["lng"]) for p in path)


@shared_task
def broadcast_location(ping_id):
    """T.1 — fired on every VehicleLocationPing save."""
    try:
        ping = VehicleLocationPing.objects.select_related("trip__route", "trip__vehicle").get(id=ping_id)
    except VehicleLocationPing.DoesNotExist:
        return

    trip = ping.trip
    route = trip.route

    # 1. Update the Redis feature-store style cache (mirrors Appendix H.5 pattern)
    cache.set(
        f"vehicle:{trip.vehicle_id}:location",
        {
            "lat": float(ping.latitude),
            "lng": float(ping.longitude),
            "speed_kmh": ping.speed_kmh,
            "recorded_at": ping.recorded_at.isoformat(),
        },
        timeout=LOCATION_CACHE_TTL_SECONDS,
    )

    # 2. Push to parent/student portals subscribed to this route via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"route_{route.id}",
        {
            "type": "location.update",
            "vehicle_id": trip.vehicle_id,
            "trip_id": trip.id,
            "lat": float(ping.latitude),
            "lng": float(ping.longitude),
            "speed_kmh": ping.speed_kmh,
            "recorded_at": ping.recorded_at.isoformat(),
        },
    )

    # 3. Off-route deviation check (Transfinder RouteTracer pattern)
    distance = _distance_to_polyline_meters(float(ping.latitude), float(ping.longitude), route.planned_path)
    if distance is not None and distance > OFF_ROUTE_THRESHOLD_METERS:
        RouteDeviationAlert.objects.create(
            tenant=trip.tenant,
            trip=trip,
            alert_type=RouteDeviationAlert.AlertType.OFF_ROUTE,
            details=f"Vehicle {distance:.0f}m from planned route",
            distance_meters=distance,
        )

    # 4. Stop-arrival + ETA check
    check_stop_arrival_and_eta.delay(ping_id)


@shared_task
def check_stop_arrival_and_eta(ping_id):
    """Checks proximity to the next scheduled stop; marks arrival and computes a simple ETA
    for the stops after it based on current speed."""
    try:
        ping = VehicleLocationPing.objects.select_related("trip__route").get(id=ping_id)
    except VehicleLocationPing.DoesNotExist:
        return

    stops = list(Stop.objects.filter(route=ping.trip.route).order_by("sequence"))
    if not stops:
        return

    lat, lng = float(ping.latitude), float(ping.longitude)
    speed = max(ping.speed_kmh, 5)  # floor to avoid division-by-near-zero ETA blowups

    for stop in stops:
        d = _haversine_meters(lat, lng, float(stop.latitude), float(stop.longitude))
        if d <= stop.radius_meters:
            notify_stop_arrival.delay(stop.id, ping.trip_id)
        eta_minutes = round((d / 1000) / speed * 60, 1)
        cache.set(f"stop:{stop.id}:eta_minutes", eta_minutes, timeout=LOCATION_CACHE_TTL_SECONDS)


@shared_task
def notify_stop_arrival(stop_id, trip_id):
    """SMS + push to parents of students assigned to this stop — Section 6.4 SMS-first principle."""
    from .models import StudentTransportAssignment  # local import avoids circulars

    stop = Stop.objects.select_related("route").get(id=stop_id)
    assignments = StudentTransportAssignment.objects.filter(
        models_Q_active_stop(stop)
    ).select_related("student")

    for assignment in assignments:
        student = assignment.student
        parent_phone = getattr(getattr(student, "guardian", None), "phone", None)
        if parent_phone:
            send_sms(
                tenant=stop.tenant,
                phone=parent_phone,
                message=f"The school bus has arrived at {stop.name} for {student.first_name}.",
            )


def models_Q_active_stop(stop):
    """Small helper kept local to avoid importing Q at module top purely for one call site."""
    from django.db.models import Q

    return Q(active=True) & (Q(pickup_stop=stop) | Q(dropoff_stop=stop))


@shared_task
def send_boarding_notification(event_id):
    """T.2 — fired on every BoardingEvent save."""
    try:
        event = BoardingEvent.objects.select_related("student", "stop").get(id=event_id)
    except BoardingEvent.DoesNotExist:
        return

    student = event.student
    parent_phone = getattr(getattr(student, "guardian", None), "phone", None)
    verb = "boarded" if event.event_type == BoardingEvent.EventType.BOARD else "alighted from"
    stop_name = event.stop.name if event.stop else "the bus stop"
    time_str = event.recorded_at.strftime("%H:%M")

    if parent_phone:
        send_sms(
            tenant=event.tenant,
            phone=parent_phone,
            message=f"{student.first_name} {verb} the school bus at {stop_name}, {time_str}.",
        )


@shared_task
def daily_document_expiry_check():
    """T.3 — Celery Beat, daily. Mirrors the subscription-due reminder cadence in Appendix D.7."""
    today = timezone.localdate()
    windows = (30, 14, 7)

    for vehicle in Vehicle.objects.exclude(status=Vehicle.Status.RETIRED):
        for field, label in (
            ("insurance_expiry", "insurance"),
            ("road_license_expiry", "road license"),
            ("inspection_expiry", "inspection"),
        ):
            expiry = getattr(vehicle, field)
            if expiry and (expiry - today).days in windows:
                _notify_transport_officer(
                    vehicle.tenant,
                    f"Vehicle {vehicle.registration_number}: {label} expires in {(expiry - today).days} days.",
                )

    for driver in Driver.objects.filter(active=True):
        if driver.license_expiry and (driver.license_expiry - today).days in windows:
            _notify_transport_officer(
                driver.tenant,
                f"Driver {driver.full_name}: license expires in {(driver.license_expiry - today).days} days.",
            )


def _notify_transport_officer(tenant, message):
    """Placeholder hook — wire this to whatever internal staff-notification mechanism
    the base system already uses for admin alerts (e.g. the same channel that powers
    the Principal dashboard alerts in Appendix D.6)."""
    # e.g. Notification.objects.create(tenant=tenant, role="TRANSPORT_OFFICER", message=message)
    pass
