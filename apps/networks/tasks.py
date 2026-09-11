"""
apps/networks/tasks.py

Nightly rollup — the second consumer of the audited network-scoped read
service, running the same rhythm as the ACI Engine's own nightly
extract_tenant_patterns (Appendix H, 00:00 UTC). Add compute_network_rollups
to your existing Celery Beat schedule alongside it.

Every metric computation below goes through network_scoped_queryset(),
not a manual tenant_id__in filter — so every night's run writes real
NetworkQueryLog rows, the same audit trail a human Network Admin's query
would produce. There is no separate "system reads don't get logged" path.

Metric functions assume the field names Appendix C documents for Student,
AttendanceRecord, ExamResult, and FeeInvoice — verify against your real
models before relying on this (see README). The one non-obvious rule
every metric here follows: a network-wide figure is a properly weighted
aggregate (total present / total records), never an average of each
school's own rate — averaging rates silently misweights schools of very
different sizes.
"""
from datetime import date, timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum

from .models import Network, NetworkDailyMetric, NetworkStatus
from .services import network_scoped_queryset

ROLLING_ATTENDANCE_WINDOW_DAYS = 28  # matches Section 7's "rolling 4-week" convention


def _system_user():
    """
    network_scoped_queryset() requires an authorized reader. Rather than
    giving this task a silent bypass, it runs as a real, dedicated,
    is_staff account — the exact same platform-staff rule Section 4.2
    already grants a human super-admin, not a special case for background
    jobs. is_active=False means it can never be used to log in.
    """
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username="asms_rollup_system", defaults={"is_staff": True, "is_active": False}
    )
    return user


def _weighted_rate(qs, tenant_field="tenant_id", positive_filter=None):
    """
    Shared shape for every rate metric: per-tenant breakdown via one
    GROUP BY query, plus a correctly weighted network-wide figure from a
    second aggregate over the same queryset — not derived from the
    per-tenant numbers.
    """
    per_tenant = {}
    for row in qs.values(tenant_field).annotate(total=Count("id"), positive=Count("id", filter=positive_filter)):
        tid = row[tenant_field]
        per_tenant[tid] = round(100 * row["positive"] / row["total"], 2) if row["total"] else None

    overall = qs.aggregate(total=Count("id"), positive=Count("id", filter=positive_filter))
    network_wide = round(100 * overall["positive"] / overall["total"], 2) if overall["total"] else None
    return per_tenant, network_wide


def _enrollment_count(network, user):
    from apps.academics.models import Student

    qs = network_scoped_queryset(user, network, Student).filter(status="ACTIVE")
    rows = qs.values("tenant_id").annotate(n=Count("id"))
    per_tenant = {r["tenant_id"]: r["n"] for r in rows}
    return per_tenant, (sum(per_tenant.values()) if per_tenant else None)


def _attendance_rate(network, user):
    from apps.academics.models import AttendanceRecord

    since = date.today() - timedelta(days=ROLLING_ATTENDANCE_WINDOW_DAYS)
    qs = network_scoped_queryset(user, network, AttendanceRecord).filter(date__gte=since)
    return _weighted_rate(qs, positive_filter=Q(status="PRESENT"))


def _fee_collection_rate(network, user):
    from apps.finance.models import FeeInvoice

    qs = network_scoped_queryset(user, network, FeeInvoice)
    per_tenant = {}
    for row in qs.values("tenant_id").annotate(total=Sum("total"), paid=Sum("amount_paid")):
        per_tenant[row["tenant_id"]] = (
            round(100 * float(row["paid"]) / float(row["total"]), 2) if row["total"] else None
        )
    overall = qs.aggregate(total=Sum("total"), paid=Sum("amount_paid"))
    network_wide = round(100 * float(overall["paid"]) / float(overall["total"]), 2) if overall["total"] else None
    return per_tenant, network_wide


def _exam_pass_rate(network, user):
    from apps.academics.models import ExamResult

    qs = network_scoped_queryset(user, network, ExamResult)
    return _weighted_rate(qs, positive_filter=Q(passed=True))


METRIC_COMPUTERS = {
    "ENROLLMENT_COUNT": _enrollment_count,
    "ATTENDANCE_RATE": _attendance_rate,
    "FEE_COLLECTION_RATE": _fee_collection_rate,
    "EXAM_PASS_RATE": _exam_pass_rate,
}


def _upsert(network, tenant_id, as_of, metric_name, value):
    if value is None:
        return
    NetworkDailyMetric.objects.update_or_create(
        network=network, tenant_id=tenant_id, date=as_of, metric=metric_name, defaults={"value": value}
    )


def compute_rollups_for_network(network, as_of, user):
    """
    Factored out of the Celery entry point so it's directly callable —
    for tests, and later for an admin "recompute now" action — without
    going through the task queue.
    """
    if not network.tenants.exists():
        return

    for metric_name, compute in METRIC_COMPUTERS.items():
        per_tenant, network_wide = compute(network, user)
        _upsert(network, None, as_of, metric_name, network_wide)
        for tenant_id, value in per_tenant.items():
            _upsert(network, tenant_id, as_of, metric_name, value)


@shared_task
def compute_network_rollups():
    """Celery Beat entry point — one nightly call computes every metric for every active network."""
    today = date.today()
    system_user = _system_user()
    for network in Network.objects.filter(status=NetworkStatus.ACTIVE):
        compute_rollups_for_network(network, today, system_user)
