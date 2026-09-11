from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.networks.models import Network, NetworkAdminRole, NetworkMembership, NetworkQueryLog
from apps.networks.services import get_network_scope, network_scoped_queryset

User = get_user_model()


class NetworkScopeTests(TestCase):
    def setUp(self):
        self.network = Network.objects.create(name="Aga Khan Schools Uganda", slug="agakhan", country="Uganda")
        self.admin = User.objects.create_user("agakhan_admin")
        self.staff = User.objects.create_user("platform_staff", is_staff=True)
        self.outsider = User.objects.create_user("random_teacher")
        NetworkAdminRole.objects.create(network=self.network, user=self.admin)

    def test_non_admin_denied(self):
        with self.assertRaises(PermissionDenied):
            get_network_scope(self.outsider, self.network)

    def test_active_admin_allowed(self):
        self.assertEqual(get_network_scope(self.admin, self.network), [])

    def test_platform_staff_bypasses_admin_role_requirement(self):
        # The fix: is_staff should pass even with zero NetworkAdminRole
        # rows for this network — same rule the view-layer permission
        # class already enforced, now consistent at the service layer too.
        self.assertFalse(NetworkAdminRole.objects.filter(network=self.network, user=self.staff).exists())
        self.assertEqual(get_network_scope(self.staff, self.network), [])

    def test_suspended_network_denies_everyone_including_staff(self):
        self.network.status = "SUSPENDED"
        self.network.save()
        with self.assertRaises(PermissionDenied):
            get_network_scope(self.admin, self.network)
        with self.assertRaises(PermissionDenied):
            get_network_scope(self.staff, self.network)

    def test_scoped_queryset_writes_audit_log_with_exact_tenant_ids(self):
        from apps.core.models import Tenant

        t1 = Tenant.objects.create(name="School A", subdomain="school-a", network=self.network)
        NetworkMembership.objects.create(network=self.network, tenant=t1)

        network_scoped_queryset(self.admin, self.network, NetworkMembership)

        log = NetworkQueryLog.objects.latest("created_at")
        self.assertEqual(log.tenant_ids, [t1.pk])
        self.assertEqual(log.model_label, "networks.networkmembership")
