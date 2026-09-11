from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import Tenant
from apps.networks.models import Network, NetworkAdminRole, NetworkDailyMetric, NetworkMembership
from apps.networks.services import network_scoped_queryset

User = get_user_model()


class NetworkViewsTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user("platform_staff", is_staff=True)
        self.admin = User.objects.create_user("agakhan_admin")
        self.outsider = User.objects.create_user("random_teacher")

        self.network = Network.objects.create(
            name="Aga Khan Schools Uganda", slug="agakhan-uganda", country="Uganda"
        )
        NetworkAdminRole.objects.create(network=self.network, user=self.admin)

        self.member_school = Tenant.objects.create(
            name="Aga Khan Primary Kampala", subdomain="akps", network=self.network
        )
        NetworkMembership.objects.create(network=self.network, tenant=self.member_school)

        self.unaffiliated_school = Tenant.objects.create(name="St Marys Kitende", subdomain="stmarys")

    # ---- authentication / authorization boundaries ----

    def test_unauthenticated_request_denied(self):
        resp = self.client.get(reverse("networks:network-list"))
        # DRF returns 401 only when a configured authenticator implements a
        # challenge (authenticate_header) — otherwise it falls back to 403.
        # This sandbox has no DEFAULT_AUTHENTICATION_CLASSES configured, so
        # 403 is correct here; with JWT auth wired up in the real project
        # this same request should come back 401. Either way, the point of
        # this test is that it's denied — assert that, not the exact code.
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_outsider_sees_empty_network_list(self):
        self.client.force_authenticate(self.outsider)
        resp = self.client.get(reverse("networks:network-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"], [])

    def test_admin_sees_only_their_network(self):
        Network.objects.create(name="Other Group", slug="other-group", country="Kenya")
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("networks:network-list"))
        names = [n["name"] for n in resp.data["data"]]
        self.assertEqual(names, ["Aga Khan Schools Uganda"])

    def test_staff_sees_every_network(self):
        Network.objects.create(name="Other Group", slug="other-group", country="Kenya")
        self.client.force_authenticate(self.staff)
        resp = self.client.get(reverse("networks:network-list"))
        self.assertEqual(len(resp.data["data"]), 2)

    def test_outsider_cannot_retrieve_network_detail(self):
        self.client.force_authenticate(self.outsider)
        resp = self.client.get(reverse("networks:network-detail", args=[self.network.pk]))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_retrieve_own_network_detail(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("networks:network-detail", args=[self.network.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["data"]["school_count"], 1)

    def test_only_staff_can_create_network(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("networks:network-list"),
            {"name": "New Group", "slug": "new-group", "country": "Rwanda"},
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.staff)
        resp = self.client.post(
            reverse("networks:network-list"),
            {"name": "New Group", "slug": "new-group", "country": "Rwanda"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    # ---- member schools ----

    def test_list_member_schools(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("networks:network-schools", args=[self.network.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["meta"]["total"], 1)
        self.assertEqual(resp.data["data"][0]["subdomain"], "akps")

    def test_add_school_to_network(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("networks:network-schools", args=[self.network.pk]),
            {"tenant_id": self.unaffiliated_school.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.unaffiliated_school.refresh_from_db()
        self.assertEqual(self.unaffiliated_school.network_id, self.network.pk)
        self.assertTrue(
            NetworkMembership.objects.filter(network=self.network, tenant=self.unaffiliated_school).exists()
        )

    def test_cannot_add_school_already_in_a_network(self):
        other_network = Network.objects.create(name="Other", slug="other", country="Kenya")
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("networks:network-schools", args=[other_network.pk]),
            {"tenant_id": self.member_school.pk},  # already in self.network
        )
        # admin isn't even an admin of other_network -> 403 comes first
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # same call against the network the school IS already in, by a real admin of it
        resp = self.client.post(
            reverse("networks:network-schools", args=[self.network.pk]),
            {"tenant_id": self.member_school.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "SCHOOL_ALREADY_IN_NETWORK")

    def test_remove_school_from_network(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(
            reverse("networks:network-school-detail", args=[self.network.pk, self.member_school.pk])
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.member_school.refresh_from_db()
        self.assertIsNone(self.member_school.network_id)
        membership = NetworkMembership.objects.get(network=self.network, tenant=self.member_school)
        self.assertIsNotNone(membership.left_at)

    # ---- admins ----

    def test_list_and_grant_admins(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("networks:network-admins", args=[self.network.pk]))
        self.assertEqual(len(resp.data["data"]), 1)

        resp = self.client.post(
            reverse("networks:network-admins", args=[self.network.pk]),
            {"user": self.outsider.pk},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            NetworkAdminRole.objects.filter(network=self.network, user=self.outsider, is_active=True).exists()
        )

    # ---- audit log surfaced through the API ----

    def test_query_log_entries_are_visible_to_the_admin(self):
        network_scoped_queryset(self.admin, self.network, NetworkMembership)  # writes one log row

        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse("networks:network-logs", args=[self.network.pk]))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["model_label"], "networks.networkmembership")

    # ---- rollups endpoint ----

    def test_rollups_scope_filter_matches_stripe_style_toggle(self):
        today = date.today()
        NetworkDailyMetric.objects.create(
            network=self.network, tenant=None, date=today, metric="ATTENDANCE_RATE", value=71.05
        )
        NetworkDailyMetric.objects.create(
            network=self.network, tenant=self.member_school, date=today, metric="ATTENDANCE_RATE", value=87.5
        )

        self.client.force_authenticate(self.admin)
        base_url = reverse("networks:network-rollups", args=[self.network.pk])

        resp = self.client.get(base_url, {"scope": "network"})
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertIsNone(resp.data["data"][0]["school"])

        resp = self.client.get(base_url, {"scope": "schools"})
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["school"], self.member_school.name)

        resp = self.client.get(base_url)  # no scope -> both rows
        self.assertEqual(len(resp.data["data"]), 2)

    def test_rollups_metric_and_date_filters(self):
        today = date.today()
        NetworkDailyMetric.objects.create(
            network=self.network, tenant=None, date=today, metric="ATTENDANCE_RATE", value=71.05
        )
        NetworkDailyMetric.objects.create(
            network=self.network, tenant=None, date=today, metric="FEE_COLLECTION_RATE", value=87.5
        )

        self.client.force_authenticate(self.admin)
        resp = self.client.get(
            reverse("networks:network-rollups", args=[self.network.pk]), {"metric": "FEE_COLLECTION_RATE"}
        )
        self.assertEqual(len(resp.data["data"]), 1)
        self.assertEqual(resp.data["data"][0]["metric"], "FEE_COLLECTION_RATE")

    def test_outsider_cannot_read_rollups(self):
        self.client.force_authenticate(self.outsider)
        resp = self.client.get(reverse("networks:network-rollups", args=[self.network.pk]))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
