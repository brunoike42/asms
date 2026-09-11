"""
apps/curriculum/services.py

The publish/sync/diverge logic — the part of the benchmark that actually
mattered. Three rules, all straight from Canvas Blueprint Courses:

  1. Only the network (never the school) decides default_locked.
  2. Syncing a publish always overwrites non-diverged adoptions and
     always skips diverged ones — no partial merge, no silent overwrite
     of a school's local edit.
  3. Diverging is a one-way door for that adoption row: it happens the
     moment a school edits an unlocked item, and nothing re-syncs it
     automatically afterward.
"""
from datetime import date

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.networks.services import user_administers_network, get_network_scope

from .models import CurriculumAdoption, CurriculumPublishLog, ResourceStatus


def sync_resource_to_network(resource, user):
    """
    Returns (synced_count, skipped_count). No-op (0, 0) for baseline
    (network=None) content — schools opt into that directly via
    adopt_resource, there's no network membership to push through — and
    for anything whose effective_from_date hasn't arrived yet.
    """
    if resource.network_id is None:
        return 0, 0
    if resource.effective_from_date and resource.effective_from_date > date.today():
        return 0, 0

    tenant_ids = get_network_scope(user, resource.network)

    synced = skipped = 0
    for tenant_id in tenant_ids:
        adoption, created = CurriculumAdoption.objects.get_or_create(
            tenant_id=tenant_id,
            resource=resource,
            defaults={"adopted_version": resource.version},
        )
        if created:
            synced += 1
            continue
        if adoption.is_diverged:
            skipped += 1
            continue
        adoption.adopted_version = resource.version
        adoption.save(update_fields=["adopted_version"])
        synced += 1

    return synced, skipped


def publish_resource(resource, user):
    """
    Bumps the version, marks PUBLISHED, syncs to every member school
    that hasn't diverged, and writes one CurriculumPublishLog row.
    """
    if resource.network_id:
        if not user_administers_network(user, resource.network):
            raise PermissionDenied(f"{user} cannot publish curriculum for {resource.network}.")
    elif not user.is_staff:
        raise PermissionDenied("Only platform staff can publish baseline (no-network) curriculum.")

    resource.version += 1
    resource.status = ResourceStatus.PUBLISHED
    resource.save(update_fields=["version", "status"])

    synced, skipped = sync_resource_to_network(resource, user)

    CurriculumPublishLog.objects.create(
        resource=resource,
        version=resource.version,
        published_by=user,
        synced_count=synced,
        skipped_count=skipped,
    )
    return resource, synced, skipped


def adopt_resource(tenant, resource):
    """
    A school opting into a resource directly — the path for baseline
    (network=None) content, or for a network resource the school wants
    before the next sync reaches it. get_or_create so calling it twice
    is harmless.
    """
    adoption, _ = CurriculumAdoption.objects.get_or_create(
        tenant=tenant, resource=resource, defaults={"adopted_version": resource.version}
    )
    return adoption


def diverge_adoption(adoption, new_content):
    """
    The one-way door. Raises PermissionDenied if the resource is locked
    — locked items can't diverge by construction, not by convention.
    """
    if adoption.resource.default_locked:
        raise PermissionDenied(f"'{adoption.resource.title}' is locked by its network — cannot be edited locally.")

    adoption.is_diverged = True
    adoption.local_content = new_content
    adoption.diverged_at = timezone.now()
    adoption.save(update_fields=["is_diverged", "local_content", "diverged_at"])
    return adoption
