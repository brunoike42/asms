from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import Staff, Tenant
from apps.curriculum.models import CurriculumAdoption, CurriculumResource
from apps.curriculum.services import publish_resource
from apps.networks.models import Network, NetworkAdminRole

User = get_user_model()


class CurriculumViewsTests(APITestCase):
    def setUp(self):
        self.network_admin = User.objects.create_user("agakhan_admin")
        self.teacher = User.objects.create_user("school_a_teacher")
        self.outsider = User.objects.create_user("random_person")

        self.network = Network.objects.create(name="Aga Khan Schools Uganda", slug="agakhan", country="Uganda")
        NetworkAdminRole.objects.create(network=self.network, user=self.network_admin)

        self.school_a = Tenant.objects.create(name="School A", subdomain="school-a", network=self.network)
        Staff.objects.create(tenant=self.school_a, user=self.teacher, role="TEACHER")

        self.resource = CurriculumResource.objects.create(
            network=self.network, title="S1 Biology", resource_type="SCHEME_OF_WORK",
            subject="Biology", level="S1", content="v1 content",
        )

    def test_teacher_cannot_create_resource(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.post(
            reverse("curriculum:resource-list"),
            {"network": self.network.pk, "title": "New", "resource_type": "LESSON_PLAN",
             "subject": "Math", "level": "S2", "content": "..."},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_network_admin_can_create_and_publish(self):
        self.client.force_authenticate(self.network_admin)
        resp = self.client.post(
            reverse("curriculum:resource-list"),
            {"network": self.network.pk, "title": "New", "resource_type": "LESSON_PLAN",
             "subject": "Math", "level": "S2", "content": "..."},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        resource_id = resp.data["data"]["id"]

        resp = self.client.post(reverse("curriculum:resource-publish", args=[resource_id]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["resource"]["version"], 2)
        self.assertEqual(resp.data["data"]["synced"], 1)  # School A

    def test_adoptions_endpoint_shows_status(self):
        publish_resource(self.resource, self.network_admin)
        self.client.force_authenticate(self.network_admin)
        resp = self.client.get(reverse("curriculum:resource-adoptions", args=[self.resource.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["school"], "School A")
        self.assertFalse(resp.data["data"][0]["is_diverged"])

    def test_teacher_cannot_view_adoptions(self):
        publish_resource(self.resource, self.network_admin)
        self.client.force_authenticate(self.teacher)
        resp = self.client.get(reverse("curriculum:resource-adoptions", args=[self.resource.pk]))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_can_diverge_unlocked_adoption(self):
        publish_resource(self.resource, self.network_admin)
        adoption = CurriculumAdoption.objects.get(tenant=self.school_a, resource=self.resource)

        self.client.force_authenticate(self.teacher)
        resp = self.client.post(
            reverse("curriculum:adoption-diverge", args=[adoption.pk]), {"content": "Our localized version"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["data"]["is_diverged"])

    def test_teacher_cannot_diverge_locked_adoption(self):
        self.resource.default_locked = True
        self.resource.save()
        publish_resource(self.resource, self.network_admin)
        adoption = CurriculumAdoption.objects.get(tenant=self.school_a, resource=self.resource)

        self.client.force_authenticate(self.teacher)
        resp = self.client.post(
            reverse("curriculum:adoption-diverge", args=[adoption.pk]), {"content": "Attempted edit"}
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "LOCKED")

    def test_teacher_at_different_school_cannot_diverge(self):
        other_school = Tenant.objects.create(name="School C", subdomain="school-c")
        other_teacher = User.objects.create_user("school_c_teacher")
        Staff.objects.create(tenant=other_school, user=other_teacher, role="TEACHER")

        publish_resource(self.resource, self.network_admin)
        adoption = CurriculumAdoption.objects.get(tenant=self.school_a, resource=self.resource)

        self.client.force_authenticate(other_teacher)
        resp = self.client.post(
            reverse("curriculum:adoption-diverge", args=[adoption.pk]), {"content": "Not my school"}
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        resp = self.client.get(reverse("curriculum:resource-list"))
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
