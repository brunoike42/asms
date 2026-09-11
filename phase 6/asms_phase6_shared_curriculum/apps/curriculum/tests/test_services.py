from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.core.models import Tenant
from apps.curriculum.models import CurriculumAdoption, CurriculumPublishLog, CurriculumResource
from apps.curriculum.services import adopt_resource, diverge_adoption, publish_resource, sync_resource_to_network
from apps.networks.models import Network, NetworkAdminRole

User = get_user_model()


class PublishAndSyncTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("agakhan_admin")
        self.outsider = User.objects.create_user("random_teacher")
        self.staff = User.objects.create_user("platform_staff", is_staff=True)

        self.network = Network.objects.create(name="Aga Khan Schools Uganda", slug="agakhan", country="Uganda")
        NetworkAdminRole.objects.create(network=self.network, user=self.admin)

        self.school_a = Tenant.objects.create(name="School A", subdomain="school-a", network=self.network)
        self.school_b = Tenant.objects.create(name="School B", subdomain="school-b", network=self.network)

        self.resource = CurriculumResource.objects.create(
            network=self.network,
            title="S1 Biology — Cell Structure",
            resource_type="SCHEME_OF_WORK",
            subject="Biology",
            level="S1",
            content="Original network content v1",
        )

    # ---- publish authorization ----

    def test_non_admin_cannot_publish(self):
        with self.assertRaises(PermissionDenied):
            publish_resource(self.resource, self.outsider)

    def test_admin_can_publish(self):
        resource, synced, skipped = publish_resource(self.resource, self.admin)
        self.assertEqual(resource.version, 2)
        self.assertEqual(resource.status, "PUBLISHED")
        self.assertEqual(synced, 2)  # first-time adoption for both schools
        self.assertEqual(skipped, 0)

    def test_baseline_resource_requires_platform_staff(self):
        baseline = CurriculumResource.objects.create(
            network=None, title="NCDC S1 Biology", resource_type="SYLLABUS_TOPIC", subject="Biology", level="S1",
            content="National baseline",
        )
        with self.assertRaises(PermissionDenied):
            publish_resource(baseline, self.admin)  # network admin, but this resource has no network
        resource, synced, skipped = publish_resource(baseline, self.staff)
        self.assertEqual(resource.version, 2)
        self.assertEqual(synced, 0)  # no network to push through — schools opt in via /adopt/

    def test_publish_writes_a_log_row(self):
        publish_resource(self.resource, self.admin)
        log = CurriculumPublishLog.objects.get(resource=self.resource, version=2)
        self.assertEqual(log.published_by, self.admin)
        self.assertEqual(log.synced_count, 2)

    # ---- the core mechanic: locked always syncs, diverged never does ----

    def test_first_publish_creates_adoption_rows_for_every_member_school(self):
        publish_resource(self.resource, self.admin)
        self.assertTrue(CurriculumAdoption.objects.filter(tenant=self.school_a, resource=self.resource).exists())
        self.assertTrue(CurriculumAdoption.objects.filter(tenant=self.school_b, resource=self.resource).exists())

    def test_locked_item_cannot_diverge(self):
        self.resource.default_locked = True
        self.resource.save()
        publish_resource(self.resource, self.admin)
        adoption = CurriculumAdoption.objects.get(tenant=self.school_a, resource=self.resource)

        with self.assertRaises(PermissionDenied):
            diverge_adoption(adoption, "School A's own version")

        adoption.refresh_from_db()
        self.assertFalse(adoption.is_diverged)

    def test_unlocked_edit_diverges_and_survives_future_syncs(self):
        publish_resource(self.resource, self.admin)  # v2, both schools adopted

        adoption_a = CurriculumAdoption.objects.get(tenant=self.school_a, resource=self.resource)
        diverge_adoption(adoption_a, "School A's localized version")
        adoption_a.refresh_from_db()
        self.assertTrue(adoption_a.is_diverged)
        self.assertIsNotNone(adoption_a.diverged_at)

        # Network publishes v3 — School B (never touched it) should sync
        # forward; School A (diverged) must stay exactly where it was.
        self.resource.content = "Updated network content"
        self.resource.save()
        resource, synced, skipped = publish_resource(self.resource, self.admin)
        self.assertEqual(resource.version, 3)
        self.assertEqual(synced, 1)   # School B only
        self.assertEqual(skipped, 1)  # School A, diverged

        adoption_a.refresh_from_db()
        adoption_b = CurriculumAdoption.objects.get(tenant=self.school_b, resource=self.resource)
        self.assertEqual(adoption_a.adopted_version, 2)  # untouched
        self.assertEqual(adoption_b.adopted_version, 3)  # advanced

    def test_effective_from_date_in_the_future_delays_sync_entirely(self):
        self.resource.effective_from_date = date.today() + timedelta(days=30)
        self.resource.save()
        resource, synced, skipped = publish_resource(self.resource, self.admin)
        self.assertEqual(resource.version, 2)  # publish itself still happens
        self.assertEqual(synced, 0)
        self.assertEqual(skipped, 0)
        self.assertFalse(CurriculumAdoption.objects.filter(resource=self.resource).exists())

    def test_sync_is_idempotent_for_non_diverged_schools(self):
        publish_resource(self.resource, self.admin)
        synced, skipped = sync_resource_to_network(self.resource, self.admin)
        self.assertEqual(synced, 2)  # re-synced, not re-created
        self.assertEqual(CurriculumAdoption.objects.filter(resource=self.resource).count(), 2)

    # ---- direct adoption (baseline / opt-in path) ----

    def test_adopt_resource_is_idempotent(self):
        first = adopt_resource(self.school_a, self.resource)
        second = adopt_resource(self.school_a, self.resource)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(CurriculumAdoption.objects.filter(tenant=self.school_a, resource=self.resource).count(), 1)
