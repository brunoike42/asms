"""
apps/curriculum/views.py

URL shape follows Appendix E, module=curriculum:
    /api/v1/curriculum/resources/
    /api/v1/curriculum/resources/{id}/publish/
    /api/v1/curriculum/resources/{id}/adoptions/     <- "the adoption endpoint"
    /api/v1/curriculum/adoptions/{id}/diverge/
"""
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.networks.api_utils import EnvelopePagination, error, success
from apps.networks.services import user_administers_network

from .models import CurriculumAdoption, CurriculumResource
from .permissions import user_belongs_to_tenant
from .serializers import CurriculumAdoptionSerializer, CurriculumResourceSerializer
from .services import adopt_resource, diverge_adoption, publish_resource


class CurriculumResourceListView(APIView):
    """
    GET  /api/v1/curriculum/resources/  — staff see all; others see
         resources from networks they administer, plus baseline (no
         network) content everyone can see.
    POST /api/v1/curriculum/resources/  — network admins for their own
         network; platform staff for baseline content.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            qs = CurriculumResource.objects.all()
        else:
            qs = CurriculumResource.objects.filter(
                Q(network__admins__user=request.user, network__admins__is_active=True) | Q(network__isnull=True)
            ).distinct()
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs.order_by("-id"), request, view=self)
        return paginator.get_paginated_response(CurriculumResourceSerializer(page, many=True).data)

    def post(self, request):
        network_id = request.data.get("network")
        if network_id:
            from apps.networks.models import Network

            network = get_object_or_404(Network, pk=network_id)
            if not user_administers_network(request.user, network):
                return error("FORBIDDEN", "Not an admin of this network.", status.HTTP_403_FORBIDDEN)
        elif not request.user.is_staff:
            return error(
                "FORBIDDEN", "Only platform staff can create baseline curriculum with no network.", status.HTTP_403_FORBIDDEN
            )

        serializer = CurriculumResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save()
        return success(CurriculumResourceSerializer(resource).data, status_code=status.HTTP_201_CREATED)


class CurriculumResourcePublishView(APIView):
    """POST /api/v1/curriculum/resources/{resource_pk}/publish/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, resource_pk):
        resource = get_object_or_404(CurriculumResource, pk=resource_pk)
        try:
            resource, synced, skipped = publish_resource(resource, request.user)
        except PermissionDenied as e:
            return error("FORBIDDEN", str(e), status.HTTP_403_FORBIDDEN)

        return success(
            {
                "resource": CurriculumResourceSerializer(resource).data,
                "synced": synced,
                "skipped": skipped,
            }
        )


class CurriculumResourceAdoptionsView(APIView):
    """
    GET /api/v1/curriculum/resources/{resource_pk}/adoptions/ — the
    adoption endpoint: per-school sync status for one resource.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, resource_pk):
        resource = get_object_or_404(CurriculumResource, pk=resource_pk)

        if resource.network_id:
            if not user_administers_network(request.user, resource.network):
                return error("FORBIDDEN", "Not an admin of this resource's network.", status.HTTP_403_FORBIDDEN)
        elif not request.user.is_staff:
            return error(
                "FORBIDDEN", "Only platform staff can view adoption of baseline curriculum.", status.HTTP_403_FORBIDDEN
            )

        qs = CurriculumAdoption.objects.filter(resource=resource).select_related("tenant")
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs.order_by("tenant__name"), request, view=self)
        return paginator.get_paginated_response(CurriculumAdoptionSerializer(page, many=True).data)


class CurriculumResourceAdoptView(APIView):
    """POST /api/v1/curriculum/resources/{resource_pk}/adopt/ — a school opting into baseline content."""

    permission_classes = [IsAuthenticated]

    def post(self, request, resource_pk):
        resource = get_object_or_404(CurriculumResource, pk=resource_pk)
        tenant_id = request.data.get("tenant_id")
        if not tenant_id:
            return error("VALIDATION_ERROR", "tenant_id is required.", status.HTTP_400_BAD_REQUEST)

        from apps.core.models import Tenant

        tenant = get_object_or_404(Tenant, pk=tenant_id)
        if not user_belongs_to_tenant(request.user, tenant):
            return error("FORBIDDEN", "Not staff at this school.", status.HTTP_403_FORBIDDEN)

        adoption = adopt_resource(tenant, resource)
        return success(CurriculumAdoptionSerializer(adoption).data, status_code=status.HTTP_201_CREATED)


class CurriculumAdoptionDivergeView(APIView):
    """POST /api/v1/curriculum/adoptions/{adoption_pk}/diverge/ — a school editing its local copy."""

    permission_classes = [IsAuthenticated]

    def post(self, request, adoption_pk):
        adoption = get_object_or_404(CurriculumAdoption, pk=adoption_pk)
        if not user_belongs_to_tenant(request.user, adoption.tenant):
            return error("FORBIDDEN", "Not staff at this school.", status.HTTP_403_FORBIDDEN)

        new_content = request.data.get("content")
        if not new_content:
            return error("VALIDATION_ERROR", "content is required.", status.HTTP_400_BAD_REQUEST)

        try:
            diverge_adoption(adoption, new_content)
        except PermissionDenied as e:
            return error("LOCKED", str(e), status.HTTP_403_FORBIDDEN)

        return success(CurriculumAdoptionSerializer(adoption).data)
