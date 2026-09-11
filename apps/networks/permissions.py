"""
apps/networks/permissions.py

Every view in this app checks object-level permission against a Network
— or anything with a .network FK, like curriculum.CurriculumResource —
before doing anything else. Platform staff always pass (Section 4.2's
super-admin bypass); everyone else must hold an active NetworkAdminRole
for that specific network.

This is the same rule services.get_network_scope() enforces for reads —
both now call services.user_administers_network() so the two can't drift
apart the way they already did once.
"""
from rest_framework.permissions import BasePermission

from .models import Network
from .services import user_administers_network


class IsNetworkAdminOrPlatformStaff(BasePermission):
    message = "You are not an active admin of this network."

    def has_permission(self, request, view):
        # List/create views have no object yet — just require auth.
        # Per-object scoping happens in has_object_permission below.
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        network = obj if isinstance(obj, Network) else getattr(obj, "network", None)
        if network is None:
            return False
        return user_administers_network(request.user, network)
