from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'transport'

router = DefaultRouter()
router.register(r"vehicles", views.VehicleViewSet, basename="vehicle")
router.register(r"drivers", views.DriverViewSet, basename="driver")
router.register(r"routes", views.RouteViewSet, basename="route")
router.register(r"stops", views.StopViewSet, basename="stop")
router.register(r"assignments", views.StudentTransportAssignmentViewSet, basename="assignment")
router.register(r"trips", views.TripLogViewSet, basename="trip")
router.register(r"maintenance", views.MaintenanceRecordViewSet, basename="maintenance")
router.register(r"alerts", views.RouteDeviationAlertViewSet, basename="alert")
router.register(r"location-pings", views.DriverLocationPingViewSet, basename="location-ping")
router.register(r"boarding-events", views.BoardingEventViewSet, basename="boarding-event")


urlpatterns = [
    path("", include(router.urls)),
    path("students/<int:student_id>/status/", views.ParentTripStatusView.as_view(), name="parent-trip-status"),
    
    path("driver/app/", views.DriverAppView.as_view(), name="driver-app"),
]

