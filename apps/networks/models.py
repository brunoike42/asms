"""
apps/networks/models.py

Phase 6, Aspect 1 — the Network/Group tier (spec Section 4.1, Level 1).

A Network groups multiple School tenants under shared administration —
either a private school group (e.g. Aga Khan Schools Uganda) or a
government district education office (type=GOVERNMENT_DISTRICT, feeds
Aspect 4's EMIS export later).

Deliberately NOT a TenantModel subclass. A Network holds no operational
student/exam/attendance data of its own — that stays isolated inside
each member School's own tenant_id boundary (apps.core.Tenant). This
app only holds identity, membership, and administrative role
assignment for the group layer, following the pattern every benchmarked
system used: Infinite Campus, PowerSchool, Google Workspace, Salesforce,
Azure Lighthouse, Toast, Epic Community Connect, Uganda's own EMIS, and
Stripe Connect all keep the operating unit's data where it is and give
the group layer a scoped, delegated view on top — never a merge.

IDs are plain integer auto PKs throughout, per Appendix E: "IDs: Always
integers in database, exposed as integers in API (no UUIDs in v1)."
"""

from django.conf import settings
from django.db import models
from apps.core.models import Tenant


class NetworkType(models.TextChoices):
    PRIVATE_GROUP = "PRIVATE_GROUP", "Private group"
    GOVERNMENT_DISTRICT = "GOVERNMENT_DISTRICT", "Government district"


class NetworkStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"


class Network(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Used for the network admin portal subdomain, e.g. agakhan.asms.app.",
    )
    type = models.CharField(max_length=32, choices=NetworkType.choices, default=NetworkType.PRIVATE_GROUP)
    country = models.CharField(max_length=100)
    status = models.CharField(max_length=16, choices=NetworkStatus.choices, default=NetworkStatus.ACTIVE)

    # String reference — apps.networks never hard-imports apps.billing.
    plan = models.CharField(
        max_length=20,
        choices=Tenant.PlanChoices.choices,
        default=Tenant.PlanChoices.NETWORK,
        help_text="The network's own consolidated plan (Section 5.1 Network plan). "
                  "Same catalogue as Tenant.plan / platform_billing.Plan.slug.",
    )
    billing_status = models.CharField(
        max_length=20,
        choices=Tenant.StatusChoices.choices,
        default=Tenant.StatusChoices.TRIAL,
    )
    plan_end = models.DateTimeField(null=True, blank=True)
    

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Network"
        verbose_name_plural = "Networks"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def member_tenant_ids(self):
        """
        The single choke point for "which schools does this network see".
        Aspects 2-5 (consolidated reporting, curriculum push, EMIS export,
        exam intelligence) should all call this rather than filtering
        Tenant.objects.filter(network=...) directly wherever they need it —
        that way an opt-out flag or a k-anonymity rule only ever has to be
        enforced in one place.
        """
        return self.tenants.values_list("pk", flat=True)


class NetworkAdminRole(models.Model):
    """
    A user's Network Admin assignment. Kept separate from any School-level
    staff/role table on purpose: this role is scoped by network, not by
    tenant, and must never be treated as an implicit Principal or School
    Super Admin on any member school — see the capability table in the
    design doc for exactly what a Network Admin can and cannot touch.
    """

    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="admins")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="network_admin_roles"
    )
    is_active = models.BooleanField(default=True)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Network admin"
        verbose_name_plural = "Network admins"
        constraints = [
            models.UniqueConstraint(fields=["network", "user"], name="unique_network_admin_per_user"),
        ]

    def __str__(self):
        return f"{self.user} — {self.network} (network admin)"


class NetworkMembership(models.Model):
    """
    Append-only history of a School tenant joining/leaving a Network.

    Tenant.network (added to apps.core in the companion patch) always
    reflects *current* membership and is what day-to-day queries filter
    on. This table exists purely so a school leaving a network doesn't
    erase the audit trail — Section 16.3 already requires write-operation
    logging, and a membership change is exactly that kind of event.
    """

    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="membership_history")
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="network_membership_history"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    joined_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Network membership record"
        verbose_name_plural = "Network membership records"
        ordering = ["-joined_at"]

    def __str__(self):
        status = "active" if self.left_at is None else f"left {self.left_at:%Y-%m-%d}"
        return f"{self.tenant} in {self.network} ({status})"


class NetworkQueryLog(models.Model):
    """
    Append-only audit trail for every network-scoped cross-tenant read —
    the same principle Section 16.3 already applies to admin access of
    sensitive data ("Counsellor viewing medical notes, principal viewing
    discipline — all logged"). Nothing ever updates or deletes a row here.

    Stores the actual tenant_ids touched, not just a count, so a question
    like "did this admin ever read a school outside their network" is
    answerable after the fact rather than only inferable.
    """

    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="query_logs")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    model_label = models.CharField(max_length=100, help_text="e.g. 'academics.examresult'")
    tenant_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Network query log"
        verbose_name_plural = "Network query logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} read {self.model_label} across {len(self.tenant_ids)} schools in {self.network}"


class NetworkMetric(models.TextChoices):
    ENROLLMENT_COUNT = "ENROLLMENT_COUNT", "Enrollment count"
    ATTENDANCE_RATE = "ATTENDANCE_RATE", "Attendance rate"
    FEE_COLLECTION_RATE = "FEE_COLLECTION_RATE", "Fee collection rate"
    EXAM_PASS_RATE = "EXAM_PASS_RATE", "Exam pass rate"


class NetworkDailyMetric(models.Model):
    """
    The nightly rollup table Consolidated Reporting reads from — the
    "wide date range, fast" lane in the two-path design from the
    benchmark. Written exclusively by apps.networks.tasks.compute_network_rollups;
    nothing else should ever write to this table.

    tenant=None is the network-wide total for that date and metric —
    computed as a properly weighted aggregate (e.g. total present over
    total attendance records), never as an average of each school's own
    rate, which would silently misweight schools of different sizes.
    A non-null tenant is that one school's own figure for the same date.
    """

    network = models.ForeignKey(Network, on_delete=models.CASCADE, related_name="daily_metrics")
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text="Null = network-wide total for this date and metric.",
    )
    date = models.DateField()
    metric = models.CharField(max_length=32, choices=NetworkMetric.choices)
    value = models.FloatField()
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Network daily metric"
        verbose_name_plural = "Network daily metrics"
        constraints = [
            models.UniqueConstraint(
                fields=["network", "tenant", "date", "metric"], name="unique_network_metric_per_day"
            ),
        ]
        indexes = [models.Index(fields=["network", "metric", "date"])]
        ordering = ["-date"]

    def __str__(self):
        scope = "network-wide" if self.tenant_id is None else str(self.tenant)
        return f"{self.network} · {self.metric} · {scope} · {self.date} = {self.value}"
