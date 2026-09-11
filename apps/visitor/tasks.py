# -*- coding: utf-8 -*-
"""
ASMS Visitor Management — Celery Tasks

Overstay detection: VisitorLog.StatusChoices already defines OVERSTAY but
nothing in the module ever sets it. This task closes that gap.

Not tenant-scoped on purpose: VisitorLog.objects is a TenantManager, which
only filters by the *current thread-local* tenant. A Celery worker running
a scheduled task has no request-bound tenant, so TenantManager.get_queryset()
falls through to its unfiltered branch and this naturally sweeps every
tenant in one pass — no per-tenant loop needed.

Add to CELERY_BEAT_SCHEDULE in settings.py (not patched here — I don't have
that file yet):

    "flag-overstay-visitors": {
        "task": "apps.visitor.tasks.flag_overstay_visitors",
        "schedule": crontab(minute="*/15"),
    },
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import VisitorLog

logger = logging.getLogger("visitor.tasks")


@shared_task
def flag_overstay_visitors():
    """
    Finds every VisitorLog still status=checked_in whose check_in_time is
    older than VISITOR_OVERSTAY_THRESHOLD_HOURS (default 4), flips it to
    status=overstay. Returns the count flagged.

    Reception notification is deliberately left as a TODO: there's no
    established "who is reception at this tenant" lookup yet (User has
    role=RECEPTIONIST, but nothing ties a specific receptionist to
    on-duty status). Wiring that in once the check-in views exist (Phase B)
    is a one-line addition here — logging only for now so nothing breaks.
    """
    threshold_hours = getattr(settings, "VISITOR_OVERSTAY_THRESHOLD_HOURS", 4)
    cutoff = timezone.now() - timedelta(hours=threshold_hours)

    overdue = VisitorLog.objects.filter(
        status=VisitorLog.StatusChoices.CHECKED_IN,
        check_in_time__lt=cutoff,
    ).select_related("visitor", "tenant")

    flagged_count = 0
    for log in overdue:
        log.status = VisitorLog.StatusChoices.OVERSTAY
        log.save(update_fields=["status", "updated_at"])
        flagged_count += 1
        logger.info(
            "Overstay: %s (badge %s) at tenant=%s past %sh threshold",
            log.visitor.full_name, log.badge_number, log.tenant_id, threshold_hours,
        )

        # TODO once reception lookup exists:
        # from apps.accounts.models import User
        # from apps.notifications.sms import send_sms
        # for receptionist in User.objects.filter(tenant=log.tenant, role=User.RoleChoices.RECEPTIONIST):
        #     send_sms(tenant=log.tenant, phone=receptionist.phone,
        #              message=f"Overstay alert: {log.visitor.full_name} "
        #                      f"(badge {log.badge_number}) has been on-site over {threshold_hours}h.")

    return flagged_count
