"""
apps/networks/permissions.py

Every view in this app checks object-level permission against a Network
instance before doing anything else. Platform staff (request.user.is_staff)
always pass, mirroring Section 4.2's "super-admin bypass" — everyone else
must hold an active NetworkAdminRole for that specific network.

This is the same rule services.get_network_scope() enforces for reads —
kept here too because a view can deny a request before it ever touches
services.py (e.g. rejecting a POST outright), and the two should never
drift apart.
"""
from rest_framework.permissions import BasePermission

from .models import NetworkAdminRole


class IsNetworkAdminOrPlatformStaff(BasePermission):
    message = "You are not an active admin of this network."

    def has_permission(self, request, view):
        # List/create views have no object yet — just require auth.
        # Per-object scoping happens in has_object_permission below.
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return NetworkAdminRole.objects.filter(
            network=obj, user=request.user, is_active=True
        ).exists()
