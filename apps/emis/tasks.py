from celery import shared_task
from apps.core.models import Tenant, AcademicYear
from .exporters.registry import get_exporter


@shared_task
def remind_pending_census_submissions():
    """
    Runs daily (see CELERY_BEAT_SCHEDULE). For each active tenant with a
    current academic year, an emis_country set, and unresolved compliance
    issues, notify school_admin/principal users.

    NOT YET WIRED: the actual send call below. This needs apps.notifications'
    real interface (function name, args) to avoid guessing at it — see the
    open question in chat. Everything else in this function is final.
    """
    for tenant in Tenant.objects.filter(is_active=True).exclude(emis_country=""):
        year = AcademicYear.objects.filter(tenant=tenant, is_current=True).first()
        if not year:
            continue
        exporter = get_exporter(tenant.emis_country)
        issues = exporter.compliance_issues(tenant)
        if not issues:
            continue

        # PENDING — replace with the real apps.notifications call once its
        # interface is confirmed. Recipients: tenant's school_admin/principal
        # users, e.g. User.objects.filter(tenant=tenant, role__in=[...]).
        raise NotImplementedError(
            "remind_pending_census_submissions: notification send call not "
            "wired yet — needs apps.notifications' interface."
        )
