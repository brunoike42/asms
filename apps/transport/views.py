"""
Transport API views. Follows the response envelope and URL conventions from Appendix E
({"status": "success", "data": ..., "meta": ...}).
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from .models import (
    Vehicle, Driver, Route, Stop, StudentTransportAssignment, TripLog,
    VehicleLocationPing, BoardingEvent, RouteDeviationAlert, MaintenanceRecord,
)
from .serializers import (
    VehicleSerializer, DriverSerializer, RouteSerializer, StopSerializer,
    StudentTransportAssignmentSerializer, TripLogSerializer, VehicleLocationPingSerializer,
    BoardingEventSerializer, RouteDeviationAlertSerializer, MaintenanceRecordSerializer,
)


class TenantCreateMixin:
    """Injects the resolved tenant into every object this viewset creates.
    Required because `tenant` is deliberately not a client-writable serializer field."""

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


def envelope(data, meta=None):
    return {"status": "success", "data": data, "meta": meta or {}}


class VehicleViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    queryset = Vehicle.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class DriverViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    serializer_class = DriverSerializer
    queryset = Driver.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class RouteViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    serializer_class = RouteSerializer
    queryset = Route.objects.prefetch_related("stops")
    permission_classes = [permissions.IsAuthenticated]


class StopViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    serializer_class = StopSerializer
    queryset = Stop.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class StudentTransportAssignmentViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    serializer_class = StudentTransportAssignmentSerializer
    queryset = StudentTransportAssignment.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class TripLogViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    serializer_class = TripLogSerializer
    queryset = TripLog.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class MaintenanceRecordViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    serializer_class = MaintenanceRecordSerializer
    queryset = MaintenanceRecord.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class RouteDeviationAlertViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RouteDeviationAlertSerializer
    queryset = RouteDeviationAlert.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        from django.utils import timezone
        alert = self.get_object()
        alert.resolved = True
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["resolved", "resolved_at"])
        return Response(envelope(RouteDeviationAlertSerializer(alert).data))


class DriverLocationPingViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    """Driver-app-facing endpoint. Supports a `bulk` action so a driver's phone can flush
    a queue of pings accumulated while offline (Section 6.3 offline-first principle) in
    one request once connectivity returns."""

    serializer_class = VehicleLocationPingSerializer
    queryset = VehicleLocationPing.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["post", "get", "head"]

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(tenant=request.tenant)
        return Response(envelope(serializer.data), status=status.HTTP_201_CREATED)


class BoardingEventViewSet(TenantCreateMixin, viewsets.ModelViewSet):
    """Driver/monitor scans a student's RFID/QR, or logs a manual entry."""

    serializer_class = BoardingEventSerializer
    queryset = BoardingEvent.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["post", "get", "head"]

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(tenant=request.tenant)
        return Response(envelope(serializer.data), status=status.HTTP_201_CREATED)


class ParentTripStatusView(APIView):
    """GET /api/v1/transport/students/{student_id}/status/
    Returns the child's assigned route, current vehicle location (from the feature-store
    cache), and ETA to their stop — what the parent portal's "live GPS link" (Section 10) calls.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        assignment = get_object_or_404(
            StudentTransportAssignment, student_id=student_id, active=True
        )
        vehicle = assignment.route.vehicle
        location = cache.get(f"vehicle:{vehicle.id}:location")
        eta = None
        if assignment.pickup_stop_id:
            eta = cache.get(f"stop:{assignment.pickup_stop_id}:eta_minutes")

        return Response(
            envelope(
                {
                    "route": assignment.route.name,
                    "vehicle_registration": vehicle.registration_number,
                    "current_location": location,
                    "eta_minutes_to_pickup_stop": eta,
                }
            )
        )
        
        
        # transport/views.py (add this)


class DriverAppView(TemplateView):
    template_name = "transport/driver_app.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trip_id"] = self.request.GET.get("trip_id")  # or however you resolve today's trip
        return ctx
