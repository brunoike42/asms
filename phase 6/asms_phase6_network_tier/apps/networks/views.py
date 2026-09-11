"""
apps/networks/views.py

URL shape follows Appendix E exactly: /api/v1/{module}/{resource}/ and
/api/v1/{module}/{parent}/{id}/{child}/ for nested resources. Mounted at
/api/v1/networks/ in the project's root urls.py (see urls.py in this app
and the README for the one line that goes in your real urlconf).

Every write to Tenant.network below goes through NetworkMembership too,
so the join/leave history survives even though Tenant.network itself only
ever holds current state — see the model docstring for why.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .api_utils import EnvelopePagination, error, success
from .models import Network, NetworkAdminRole, NetworkDailyMetric, NetworkMembership, NetworkQueryLog
from .permissions import IsNetworkAdminOrPlatformStaff
from .serializers import (
    AddSchoolSerializer,
    MemberSchoolSerializer,
    NetworkAdminRoleSerializer,
    NetworkDailyMetricSerializer,
    NetworkQueryLogSerializer,
    NetworkSerializer,
)


class NetworkListView(APIView):
    """
    GET  /api/v1/networks/networks/  — platform staff see every network;
         everyone else sees only networks they actively administer.
    POST /api/v1/networks/networks/  — platform staff only (Section 4.2:
         networks are provisioned by the platform owner, same as tenants).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            qs = Network.objects.all()
        else:
            qs = Network.objects.filter(admins__user=request.user, admins__is_active=True)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs.order_by("name"), request, view=self)
        return paginator.get_paginated_response(NetworkSerializer(page, many=True).data)

    def post(self, request):
        if not request.user.is_staff:
            return error("FORBIDDEN", "Only platform staff can create a network.", status.HTTP_403_FORBIDDEN)
        serializer = NetworkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        network = serializer.save()
        return success(NetworkSerializer(network).data, status_code=status.HTTP_201_CREATED)


class NetworkDetailView(APIView):
    """GET /api/v1/networks/networks/{id}/"""

    permission_classes = [IsAuthenticated, IsNetworkAdminOrPlatformStaff]

    def get(self, request, pk):
        network = get_object_or_404(Network, pk=pk)
        self.check_object_permissions(request, network)
        return success(NetworkSerializer(network).data)


class NetworkSchoolsView(APIView):
    """
    GET  /api/v1/networks/networks/{network_pk}/schools/  — list member schools
    POST /api/v1/networks/networks/{network_pk}/schools/  — add a school (tenant_id in body)
    """

    permission_classes = [IsAuthenticated, IsNetworkAdminOrPlatformStaff]

    def _get_network(self, request, network_pk):
        network = get_object_or_404(Network, pk=network_pk)
        self.check_object_permissions(request, network)
        return network

    def get(self, request, network_pk):
        network = self._get_network(request, network_pk)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(network.tenants.all().order_by("name"), request, view=self)
        return paginator.get_paginated_response(MemberSchoolSerializer(page, many=True).data)

    def post(self, request, network_pk):
        network = self._get_network(request, network_pk)
        serializer = AddSchoolSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Local import: keeps apps.networks free of a module-level dependency
        # on apps.core, since the reverse (core -> networks) already exists
        # via the Tenant.network FK from the companion patch.
        from apps.core.models import Tenant

        tenant = get_object_or_404(Tenant, pk=serializer.validated_data["tenant_id"])

        if tenant.network_id is not None:
            return error(
                "SCHOOL_ALREADY_IN_NETWORK",
                f"{tenant} already belongs to a network.",
                status.HTTP_409_CONFLICT,
            )

        tenant.network = network
        tenant.save(update_fields=["network"])
        NetworkMembership.objects.create(network=network, tenant=tenant, joined_by=request.user)

        return success(MemberSchoolSerializer(tenant).data, status_code=status.HTTP_201_CREATED)


class NetworkSchoolDetailView(APIView):
    """DELETE /api/v1/networks/networks/{network_pk}/schools/{tenant_pk}/ — remove a school from the network"""

    permission_classes = [IsAuthenticated, IsNetworkAdminOrPlatformStaff]

    def delete(self, request, network_pk, tenant_pk):
        network = get_object_or_404(Network, pk=network_pk)
        self.check_object_permissions(request, network)

        from apps.core.models import Tenant

        tenant = get_object_or_404(Tenant, pk=tenant_pk, network=network)
        tenant.network = None
        tenant.save(update_fields=["network"])
        NetworkMembership.objects.filter(network=network, tenant=tenant, left_at__isnull=True).update(
            left_at=timezone.now()
        )
        return success({"removed": True})


class NetworkAdminsView(APIView):
    """
    GET  /api/v1/networks/networks/{network_pk}/admins/
    POST /api/v1/networks/networks/{network_pk}/admins/  — grant a user Network Admin for this network
    """

    permission_classes = [IsAuthenticated, IsNetworkAdminOrPlatformStaff]

    def get(self, request, network_pk):
        network = get_object_or_404(Network, pk=network_pk)
        self.check_object_permissions(request, network)
        qs = NetworkAdminRole.objects.filter(network=network).select_related("user")
        return success(NetworkAdminRoleSerializer(qs, many=True).data)

    def post(self, request, network_pk):
        network = get_object_or_404(Network, pk=network_pk)
        self.check_object_permissions(request, network)
        payload = request.data.copy()
        payload["network"] = network.pk
        serializer = NetworkAdminRoleSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success(serializer.data, status_code=status.HTTP_201_CREATED)


class NetworkRollupsView(APIView):
    """
    GET /api/v1/networks/networks/{network_pk}/rollups/
        ?metric=ATTENDANCE_RATE&date_from=2026-08-01&date_to=2026-08-25&scope=network|schools

    Reads NetworkDailyMetric — the "wide date range, fast" lane, distinct
    from /logs/ (the audit trail) and from calling network_scoped_queryset()
    directly (still correct for narrow, live questions). scope=network
    returns only the network-wide total rows; scope=schools returns only
    the per-school breakdown; omitted returns both — this is the Stripe
    Connect "Aggregated report vs. Single report" toggle from the
    benchmark, as a query parameter.
    """

    permission_classes = [IsAuthenticated, IsNetworkAdminOrPlatformStaff]

    def get(self, request, network_pk):
        network = get_object_or_404(Network, pk=network_pk)
        self.check_object_permissions(request, network)

        qs = NetworkDailyMetric.objects.filter(network=network).select_related("tenant")

        metric = request.query_params.get("metric")
        if metric:
            qs = qs.filter(metric=metric)

        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(date__lte=date_to)

        scope = request.query_params.get("scope")
        if scope == "network":
            qs = qs.filter(tenant__isnull=True)
        elif scope == "schools":
            qs = qs.filter(tenant__isnull=False)

        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs.order_by("-date", "metric"), request, view=self)
        return paginator.get_paginated_response(NetworkDailyMetricSerializer(page, many=True).data)


class NetworkQueryLogsView(APIView):
    """GET /api/v1/networks/networks/{network_pk}/logs/ — audit trail of cross-tenant reads for this network"""

    permission_classes = [IsAuthenticated, IsNetworkAdminOrPlatformStaff]

    def get(self, request, network_pk):
        network = get_object_or_404(Network, pk=network_pk)
        self.check_object_permissions(request, network)
        qs = NetworkQueryLog.objects.filter(network=network).select_related("user").order_by("-created_at")
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(NetworkQueryLogSerializer(page, many=True).data)
