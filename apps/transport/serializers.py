from rest_framework import serializers

from .models import (
    Vehicle,
    Driver,
    Route,
    Stop,
    StudentTransportAssignment,
    TripLog,
    VehicleLocationPing,
    BoardingEvent,
    RouteDeviationAlert,
    MaintenanceRecord,
)


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = [
            "id", "registration_number", "make", "model", "capacity", "fuel_type",
            "status", "insurance_expiry", "road_license_expiry", "inspection_expiry",
            "gps_device_id",
        ]


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ["id", "staff", "full_name", "phone", "license_number", "license_expiry", "assigned_vehicle", "active"]


class StopSerializer(serializers.ModelSerializer):
    eta_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Stop
        fields = ["id", "route", "sequence", "name", "latitude", "longitude", "scheduled_time", "radius_meters", "eta_minutes"]

    def get_eta_minutes(self, obj):
        from django.core.cache import cache
        return cache.get(f"stop:{obj.id}:eta_minutes")


class RouteSerializer(serializers.ModelSerializer):
    stops = StopSerializer(many=True, read_only=True)

    class Meta:
        model = Route
        fields = ["id", "name", "code", "vehicle", "driver", "shift", "planned_path", "active", "stops"]


class StudentTransportAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentTransportAssignment
        fields = ["id", "student", "route", "pickup_stop", "dropoff_stop", "active", "start_date", "end_date"]


class TripLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripLog
        fields = ["id", "route", "vehicle", "driver", "date", "shift", "status", "started_at", "ended_at"]


class VehicleLocationPingSerializer(serializers.ModelSerializer):
    """Accepts pings from the driver app. Supports both live posting and offline-queued
    batch sync — `recorded_at` reflects when the fix actually happened on the device,
    which may be well before `synced_at`."""

    class Meta:
        model = VehicleLocationPing
        fields = ["id", "trip", "latitude", "longitude", "speed_kmh", "heading", "source", "recorded_at"]


class BoardingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardingEvent
        fields = ["id", "trip", "student", "stop", "event_type", "method", "recorded_at"]


class RouteDeviationAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteDeviationAlert
        fields = ["id", "trip", "alert_type", "details", "distance_meters", "created_at", "resolved"]


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceRecord
        fields = ["id", "vehicle", "record_type", "description", "cost", "performed_at", "next_due_at", "performed_by"]
