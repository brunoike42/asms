"""
apps/curriculum/permissions.py

Two different actors need two different checks in this app:
  - Publishing/viewing adoption status is a Network Admin action —
    apps.networks.permissions.IsNetworkAdminOrPlatformStaff already
    covers this, since it now works against anything with a .network
    FK, not just Network itself.
  - Diverging a local copy is a School-level action — a teacher or
    admin at that specific school, not a Network Admin. That's the one
    new check this app adds.
"""
from apps.core.models import Staff


def user_belongs_to_tenant(user, tenant) -> bool:
    if user.is_staff:
        return True
    return Staff.objects.filter(tenant=tenant, user=user).exists()
