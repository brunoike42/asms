from django.contrib import admin

from .models import (
    Vehicle, Driver, Route, Stop, StudentTransportAssignment, TripLog,
    VehicleLocationPing, BoardingEvent, RouteDeviationAlert, MaintenanceRecord,
)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "status", "capacity", "insurance_expiry", "road_license_expiry")
    list_filter = ("status", "fuel_type")
    search_fields = ("registration_number",)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "license_expiry", "assigned_vehicle", "active")
    list_filter = ("active",)
    search_fields = ("full_name", "license_number")


class StopInline(admin.TabularInline):
    model = Stop
    extra = 1


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "vehicle", "driver", "shift", "active")
    list_filter = ("shift", "active")
    inlines = [StopInline]


@admin.register(StudentTransportAssignment)
class StudentTransportAssignmentAdmin(admin.ModelAdmin):
    list_display = ("student", "route", "pickup_stop", "dropoff_stop", "active")
    list_filter = ("active",)


@admin.register(TripLog)
class TripLogAdmin(admin.ModelAdmin):
    list_display = ("route", "date", "shift", "status", "started_at", "ended_at")
    list_filter = ("status", "shift", "date")


@admin.register(RouteDeviationAlert)
class RouteDeviationAlertAdmin(admin.ModelAdmin):
    list_display = ("trip", "alert_type", "distance_meters", "created_at", "resolved")
    list_filter = ("alert_type", "resolved")


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "record_type", "performed_at", "next_due_at", "cost")
    list_filter = ("record_type",)


admin.site.register(VehicleLocationPing)
admin.site.register(BoardingEvent)
