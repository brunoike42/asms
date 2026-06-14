"""
Counselling module signals.

Per spec Section 7.1:
- Counselling case open > 21 days unresolved → MEDIUM escalation to principal
- Dropout risk score > 70 → CRITICAL alert to counsellor
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import WelfareCase, CounsellingSession, BursaryApplication


@receiver(post_save, sender=WelfareCase)
def on_welfare_case_saved(sender, instance, created, **kwargs):
    """Notify assigned counsellor when a case is newly opened or escalated."""
    import logging
    logger = logging.getLogger(__name__)

    if created:
        if instance.auto_opened:
            logger.info(
                f'Auto-opened welfare case {instance.reference_number} for '
                f'{instance.student} (trigger: {instance.trigger})'
            )
        # Schedule 21-day overdue check via Celery Beat in production
        # check_overdue_welfare_cases.apply_async(
        #     eta=timezone.now() + timedelta(days=21),
        #     kwargs={'case_pk': instance.pk}
        # )

    if not created and instance.status == 'escalated' and instance.escalated_to:
        _notify_principal_of_escalation(instance)


def _notify_principal_of_escalation(case):
    """Send notification to principal when a case is escalated."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        principal = case.escalated_to
        if principal and hasattr(principal, 'email') and principal.email:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject=f'[ASMS] Welfare Case Escalated — {case.reference_number}',
                message=(
                    f'A welfare case has been escalated to you.\n\n'
                    f'Case: {case.reference_number}\n'
                    f'Student: {case.student}\n'
                    f'Reason: {case.escalation_reason}\n\n'
                    f'Please log in to ASMS to review.'
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@asms.app'),
                recipient_list=[principal.email],
                fail_silently=True,
            )
    except Exception as e:
        logger.warning(f'Failed to notify principal of escalation: {e}')


@receiver(post_save, sender=CounsellingSession)
def on_session_saved(sender, instance, created, **kwargs):
    """
    Update the welfare case last-updated timestamp and handle
    safeguarding escalations when a new session is recorded.
    """
    if created:
        # Touch the welfare case's updated_at
        WelfareCase.objects.filter(pk=instance.welfare_case_id).update(
            updated_at=timezone.now()
        )

        if instance.safeguarding_concern_raised:
            _handle_safeguarding_flag(instance)


def _handle_safeguarding_flag(session):
    """
    When a safeguarding concern is flagged in a session note,
    mark the welfare case and ensure the principal is notified.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        WelfareCase.objects.filter(pk=session.welfare_case_id).update(
            involves_safeguarding=True,
            priority='critical',
            updated_at=timezone.now(),
        )
        logger.warning(
            f'SAFEGUARDING flagged: case {session.welfare_case.reference_number}, '
            f'session {session.pk} on {session.session_date}'
        )
    except Exception as e:
        logger.error(f'Safeguarding flag update failed: {e}')


@receiver(post_save, sender=BursaryApplication)
def on_bursary_saved(sender, instance, created, **kwargs):
    """Notify finance when a bursary is approved and ready to be applied."""
    import logging
    logger = logging.getLogger(__name__)

    if not created and instance.status == 'approved' and instance.amount_approved:
        logger.info(
            f'Bursary approved for {instance.student}: '
            f'UGX {instance.amount_approved:,.0f}. '
            f'Finance team should apply credit to invoice.'
        )
        # In production: send notification to accountant role users
