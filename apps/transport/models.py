"""
Transport & Fleet Intelligence — data models.

ASSUMPTIONS (adjust these three imports to match your actual Phase 1-3 app labels;
nothing else in this file needs to change):

    core.models.TenantAwareModel  -> abstract base with `tenant` FK + tenant-scoped manager
    students.models.Student       -> the existing Student entity (Appendix C)
    staff.models.Staff            -> the existing Staff entity (Appendix C)

If your project does not yet have a TenantAwareModel, the minimal version is:

    class TenantManager(models.Manager):
        def get_queryset(self):
            from core.middleware import get_current_tenant
            qs = super().get_queryset()
            tenant = get_current_tenant()
            return qs.filter(tenant=tenant) if tenant else qs

    class TenantModel(models.Model):
        tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE)
        objects = TenantManager()
        class Meta:
            abstract = True
"""
from django.conf import settings
from django.db import models

from apps.core.models import TenantModel  # noqa: F401  (see assumptions above)


class Vehicle(TenantModel):
    class FuelType(models.TextChoices):
        DIESEL = "DIESEL", "Diesel"
        PETROL = "PETROL", "Petrol"
        ELECTRIC = "ELECTRIC", "Electric"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        MAINTENANCE = "MAINTENANCE", "In Maintenance"
        RETIRED = "RETIRED", "Retired"

    registration_number = models.CharField(max_length=32)
    make = models.CharField(max_length=64, blank=True)
    model = models.CharField(max_length=64, blank=True)
    capacity = models.PositiveIntegerField(help_text="Number of student seats")
    fuel_type = models.CharField(max_length=16, choices=FuelType.choices, default=FuelType.DIESEL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    # Compliance / document-expiry fields — benchmarked against BusCMMS's compliance automation
    insurance_expiry = models.DateField(null=True, blank=True)
    road_license_expiry = models.DateField(null=True, blank=True)
    inspection_expiry = models.DateField(null=True, blank=True)

    # Optional dedicated GPS hardware ID (Zonar/Transfinder style). Not required — the driver's
    # phone via the offline-capable driver app is the default, Africa-first data source.
    gps_device_id = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tenant", "registration_number")
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self):
        return f"{self.registration_number} ({self.get_status_display()})"


class Driver(TenantModel):
    staff = models.OneToOneField(
        "staff_hr.StaffProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="driver_profile"
    )
    full_name = models.CharField(max_length=128, help_text="Used if driver is not also a Staff user")
    phone = models.CharField(max_length=32)
    license_number = models.CharField(max_length=64)
    license_expiry = models.DateField(null=True, blank=True)
    assigned_vehicle = models.ForeignKey(
        Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="drivers"
    )
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.full_name


class Route(TenantModel):
    class Shift(models.TextChoices):
        AM = "AM", "Morning Pickup"
        PM = "PM", "Afternoon Drop-off"
        BOTH = "BOTH", "Both"

    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="routes")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="routes")
    shift = models.CharField(max_length=8, choices=Shift.choices, default=Shift.BOTH)
    # Planned path as an ordered list of {"lat": .., "lng": ..} — used for deviation detection,
    # the same "planned vs actual" comparison Transfinder's RouteTracer/GPS Connect is built on.
    planned_path = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("tenant", "code")

    def __str__(self):
        return f"{self.code} — {self.name}"


class Stop(TenantModel):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    sequence = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=128)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    scheduled_time = models.TimeField()
    radius_meters = models.PositiveIntegerField(default=150, help_text="Geofence radius for arrival detection")

    class Meta:
        ordering = ["route", "sequence"]
        unique_together = ("route", "sequence")

    def __str__(self):
        return f"{self.route.code} · Stop {self.sequence}: {self.name}"


class StudentTransportAssignment(TenantModel):
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="transport_assignments")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="student_assignments")
    pickup_stop = models.ForeignKey(Stop, on_delete=models.SET_NULL, null=True, related_name="pickups")
    dropoff_stop = models.ForeignKey(Stop, on_delete=models.SET_NULL, null=True, related_name="dropoffs")
    active = models.BooleanField(default=True, db_column="is_active")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "transport_student_assignment"
        indexes = [models.Index(fields=["tenant", "active"])]

    def __str__(self):
        return f"{self.student} on {self.route.code}"


class TripLog(TenantModel):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="trips")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="trips")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="trips")
    date = models.DateField()
    shift = models.CharField(max_length=8, choices=Route.Shift.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "date", "status"])]

    def __str__(self):
        return f"{self.route.code} · {self.date} {self.shift}"


class VehicleLocationPing(TenantModel):
    class Source(models.TextChoices):
        DRIVER_APP = "DRIVER_APP", "Driver Phone App"
        DEVICE = "DEVICE", "Dedicated GPS Hardware"

    trip = models.ForeignKey(TripLog, on_delete=models.CASCADE, related_name="pings")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed_kmh = models.FloatField(default=0)
    heading = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.DRIVER_APP)
    # recorded_at = when the GPS fix actually happened on the device (may be in the past if queued offline)
    recorded_at = models.DateTimeField()
    # synced_at = when the ping actually reached the server — the gap between these two reveals
    # how long a driver was offline, useful for African-infra connectivity monitoring
    synced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["trip", "recorded_at"])]
        ordering = ["recorded_at"]


class BoardingEvent(TenantModel):
    class EventType(models.TextChoices):
        BOARD = "BOARD", "Boarded"
        ALIGHT = "ALIGHT", "Alighted"

    class Method(models.TextChoices):
        RFID = "RFID", "RFID Card"
        QR = "QR", "QR Code"
        MANUAL = "MANUAL", "Manual Entry"

    trip = models.ForeignKey(TripLog, on_delete=models.CASCADE, related_name="boarding_events")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="boarding_events")
    stop = models.ForeignKey(Stop, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=8, choices=EventType.choices)
    method = models.CharField(max_length=8, choices=Method.choices, default=Method.MANUAL)
    recorded_at = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["trip", "student"])]
        ordering = ["recorded_at"]


class RouteDeviationAlert(TenantModel):
    class AlertType(models.TextChoices):
        OFF_ROUTE = "OFF_ROUTE", "Off Planned Route"
        LATE = "LATE", "Running Late"
        SPEED = "SPEED", "Speed Violation"
        UNSCHEDULED_STOP = "UNSCHEDULED_STOP", "Unscheduled Stop"

    trip = models.ForeignKey(TripLog, on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=20, choices=AlertType.choices)
    details = models.TextField(blank=True)
    distance_meters = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["tenant", "resolved"])]
        ordering = ["-created_at"]


class MaintenanceRecord(TenantModel):
    class RecordType(models.TextChoices):
        INSPECTION = "INSPECTION", "Inspection"
        SERVICE = "SERVICE", "Routine Service"
        REPAIR = "REPAIR", "Repair"

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="maintenance_records")
    record_type = models.CharField(max_length=16, choices=RecordType.choices)
    description = models.TextField()
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    performed_at = models.DateField()
    next_due_at = models.DateField(null=True, blank=True)
    performed_by = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ["-performed_at"]
