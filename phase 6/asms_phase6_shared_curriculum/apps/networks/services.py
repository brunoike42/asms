"""
apps/networks/services.py

The network-scoped read layer — the Azure-Lighthouse piece of the design:
a "logical projection" across several School tenants, granted on
least-privilege terms, and always auditable — never a data merge.

This is deliberately NOT a variant of TenantManager. TenantManager filters
every queryset to exactly one tenant, resolved from request-scoped
contextvars (apps.core middleware). This module filters to an explicit,
enumerated list of tenant_ids belonging to one Network, and does the
authorization + audit logging TenantManager was never built to do.

The two code paths must never merge. A bug in the single-tenant filter
must not be able to widen into a cross-tenant leak, and a bug here must
not be able to touch a school outside its own network.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from .models import Network, NetworkAdminRole, NetworkQueryLog, NetworkStatus


def user_administers_network(user, network: Network) -> bool:
    """
    The single source of truth for "is this user allowed to act as this
    network's admin" — platform staff (Section 4.2's super-admin bypass)
    or an active NetworkAdminRole holder for this specific network.

    Previously this rule was written twice — once here, once in
    permissions.py's DRF permission class — and the two drifted (the
    service-layer copy was missing the staff bypass until that was
    caught and fixed). Everything that needs this check now calls this
    one function: get_network_scope below, the view-layer permission
    class, and apps.curriculum's pre-object-creation checks, which need
    the same answer before a DRF object-permission check has anything
    to check against yet.
    """
    if user.is_staff:
        return True
    return NetworkAdminRole.objects.filter(network=network, user=user, is_active=True).exists()


def get_network_scope(user, network: Network) -> list:
    """
    Authorization + scope resolution in one place — every other function
    in this module goes through this first. Raises PermissionDenied unless:

      1. `network` is ACTIVE (a suspended network's admin loses read access
         the same day the network is suspended, mirroring the grace/suspend
         cascade the billing engine already applies to tenant subscriptions), and
      2. user_administers_network(user, network) is true.

    Returns the list of tenant_ids currently in scope. Callers should never
    build this list themselves by querying Tenant directly.
    """
    if network.status != NetworkStatus.ACTIVE:
        raise PermissionDenied(f"Network '{network}' is not active.")

    if not user_administers_network(user, network):
        raise PermissionDenied(f"{user} is not an active admin of '{network}'.")

    return list(network.member_tenant_ids)


def network_scoped_queryset(user, network: Network, model, *, tenant_field: str = "tenant_id") -> QuerySet:
    """
    The one sanctioned way to read a model across a network's member
    schools at once. Every call is logged via NetworkQueryLog, so a
    network's scope of visibility is always reconstructable afterwards.

    Usage (once Aspect 2 — consolidated reporting — needs it):
        qs = network_scoped_queryset(request.user, network, ExamResult)
        qs.aggregate(Avg("marks"))
    """
    tenant_ids = get_network_scope(user, network)

    NetworkQueryLog.objects.create(
        network=network,
        user=user,
        model_label=f"{model._meta.app_label}.{model._meta.model_name}",
        tenant_ids=tenant_ids,
    )

    return model.objects.filter(**{f"{tenant_field}__in": tenant_ids})
