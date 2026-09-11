from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.academics.models import AttendanceRecord, ExamResult, Student
from apps.core.models import Tenant
from apps.finance.models import FeeInvoice
from apps.networks.models import Network, NetworkAdminRole, NetworkDailyMetric, NetworkQueryLog
from apps.networks.tasks import _system_user, compute_rollups_for_network

User = get_user_model()


class ComputeNetworkRollupsTests(TestCase):
    """
    School A is small, School B is three times its size, and their rates
    are deliberately far apart (50% vs 100% fee collection). If the
    network-wide figure were ever computed as a naive average of each
    school's rate instead of a properly weighted one, these assertions
    would fail — that's the point of sizing them this differently.
    """

    def setUp(self):
        self.admin = User.objects.create_user("agakhan_admin")
        self.network = Network.objects.create(name="Aga Khan Schools Uganda", slug="agakhan", country="Uganda")
        NetworkAdminRole.objects.create(network=self.network, user=self.admin)

        self.school_a = Tenant.objects.create(name="School A", subdomain="school-a", network=self.network)
        self.school_b = Tenant.objects.create(name="School B", subdomain="school-b", network=self.network)

        today = date.today()

        # --- School A: 2 students ---
        a1 = Student.objects.create(tenant=self.school_a, first_name="A", last_name="One")
        a2 = Student.objects.create(tenant=self.school_a, first_name="A", last_name="Two")
        for _ in range(3):
            AttendanceRecord.objects.create(tenant=self.school_a, student=a1, date=today, status="PRESENT")
        AttendanceRecord.objects.create(tenant=self.school_a, student=a1, date=today, status="ABSENT")
        for _ in range(4):
            AttendanceRecord.objects.create(tenant=self.school_a, student=a2, date=today, status="PRESENT")
        # School A attendance: 7 present / 8 total = 87.5%

        ExamResult.objects.create(tenant=self.school_a, student=a1, marks=80, passed=True)
        ExamResult.objects.create(tenant=self.school_a, student=a2, marks=30, passed=False)
        # School A exam pass rate: 1/2 = 50%

        FeeInvoice.objects.create(tenant=self.school_a, student=a1, total=1000, amount_paid=500)
        # School A fee collection: 500/1000 = 50%

        # --- School B: 3 students, 3x School A's attendance volume ---
        b1 = Student.objects.create(tenant=self.school_b, first_name="B", last_name="One")
        b2 = Student.objects.create(tenant=self.school_b, first_name="B", last_name="Two")
        b3 = Student.objects.create(tenant=self.school_b, first_name="B", last_name="Three")
        for student in (b1, b2):
            for _ in range(10):
                AttendanceRecord.objects.create(tenant=self.school_b, student=student, date=today, status="PRESENT")
        for _ in range(10):
            AttendanceRecord.objects.create(tenant=self.school_b, student=b3, date=today, status="ABSENT")
        # School B attendance: 20 present / 30 total = 66.67%

        ExamResult.objects.create(tenant=self.school_b, student=b1, marks=70, passed=True)
        ExamResult.objects.create(tenant=self.school_b, student=b2, marks=65, passed=True)
        ExamResult.objects.create(tenant=self.school_b, student=b3, marks=20, passed=False)
        # School B exam pass rate: 2/3 = 66.67%

        FeeInvoice.objects.create(tenant=self.school_b, student=b1, total=3000, amount_paid=3000)
        # School B fee collection: 3000/3000 = 100%

        compute_rollups_for_network(self.network, today, _system_user())
        self.today = today

    def _value(self, metric, tenant=None):
        return NetworkDailyMetric.objects.get(
            network=self.network, tenant=tenant, date=self.today, metric=metric
        ).value

    def test_per_school_figures_are_correct(self):
        self.assertEqual(self._value("ATTENDANCE_RATE", self.school_a), 87.5)
        self.assertAlmostEqual(self._value("ATTENDANCE_RATE", self.school_b), 66.67, places=2)
        self.assertEqual(self._value("FEE_COLLECTION_RATE", self.school_a), 50.0)
        self.assertEqual(self._value("FEE_COLLECTION_RATE", self.school_b), 100.0)
        self.assertEqual(self._value("ENROLLMENT_COUNT", self.school_a), 2)
        self.assertEqual(self._value("ENROLLMENT_COUNT", self.school_b), 3)

    def test_network_wide_attendance_is_weighted_not_averaged(self):
        # Naive average of 87.5 and 66.67 would be ~77.08 — wrong.
        # Correctly weighted: (7 + 20) present / (8 + 30) total = 71.05.
        value = self._value("ATTENDANCE_RATE", tenant=None)
        self.assertAlmostEqual(value, 71.05, places=2)
        self.assertNotAlmostEqual(value, 77.08, places=1)

    def test_network_wide_fee_collection_is_weighted_not_averaged(self):
        # Naive average of 50 and 100 would be 75 — wrong.
        # Correctly weighted: (500 + 3000) paid / (1000 + 3000) total = 87.5.
        value = self._value("FEE_COLLECTION_RATE", tenant=None)
        self.assertEqual(value, 87.5)
        self.assertNotEqual(value, 75.0)

    def test_network_wide_enrollment_is_additive(self):
        self.assertEqual(self._value("ENROLLMENT_COUNT", tenant=None), 5)

    def test_rollup_run_writes_one_audit_log_per_metric(self):
        # 4 metrics computed, each via network_scoped_queryset() once.
        self.assertEqual(NetworkQueryLog.objects.filter(network=self.network).count(), 4)

    def test_rerunning_for_the_same_day_updates_rather_than_duplicates(self):
        before = NetworkDailyMetric.objects.count()
        compute_rollups_for_network(self.network, self.today, _system_user())
        self.assertEqual(NetworkDailyMetric.objects.count(), before)
