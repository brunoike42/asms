"""
ASMS Platform Billing — Phase 5B/5D tasks.
Appendix D.5: "Celery task: provision_tenant — set up default academic year,
term structure, fee categories."
Appendix D.7: "Celery Beat task: check_subscription_due" — the daily
lifecycle sweep, added in Phase 5D below provision_tenant.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def provision_tenant(tenant_id):
    """
    Give a freshly self-onboarded tenant a working starting skeleton:
    one current academic year, three terms, two fee categories.
    Idempotent — safe to retry.
    """
    from apps.core.models import Tenant, AcademicYear, Term
    from apps.finance.models import FeeCategory

    try:
        tenant = Tenant.objects.get(pk=tenant_id)
    except Tenant.DoesNotExist:
        logger.error(f'provision_tenant: tenant {tenant_id} not found')
        return

    if AcademicYear.objects.filter(tenant=tenant, is_current=True).exists():
        logger.info(f'provision_tenant: {tenant.slug} already provisioned, skipping')
        return

    today = timezone.now().date()
    year_end = today + timedelta(days=365)

    academic_year = AcademicYear.objects.create(
        tenant=tenant,
        name=f'{today.year}/{today.year + 1}',
        start_date=today,
        end_date=year_end,
        is_current=True,
    )

    # Placeholder term structure — three roughly-equal terms starting today.
    # The school edits real dates during onboarding; this just avoids a
    # totally empty term table blocking attendance/exams/finance screens.
    span = (year_end - today).days
    third = span // 3
    term_specs = [
        (Term.TermChoices.TERM_1, 0, third),
        (Term.TermChoices.TERM_2, third, third * 2),
        (Term.TermChoices.TERM_3, third * 2, span),
    ]
    for name, start_offset, end_offset in term_specs:
        Term.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            name=name,
            start_date=today + timedelta(days=start_offset),
            end_date=today + timedelta(days=end_offset),
            is_current=(name == Term.TermChoices.TERM_1),
        )

    for order, cat_name in enumerate(['Tuition', 'Activity Fee']):
        FeeCategory.objects.get_or_create(
            tenant=tenant, name=cat_name,
            defaults={'order': order},
        )

    logger.info(f'provision_tenant: {tenant.slug} provisioned ({academic_year.name}, 3 terms, 2 fee categories)')


# ─────────────────────────────────────────────────────────────
# Phase 5D — daily lifecycle sweep (Appendix D.7)
# ─────────────────────────────────────────────────────────────

GRACE_PERIOD_DAYS = 7        # days past due before ACTIVE -> GRACE_PERIOD
SUSPEND_AFTER_GRACE_DAYS = 7  # days in grace before GRACE_PERIOD -> SUSPENDED (14 total past due)
DELETION_WARNING_AFTER_DAYS = 60  # days suspended before the warning email


@shared_task
def check_subscription_due():
    """
    Runs daily (06:00 UTC per D.7). For every self-serve tenant, checks
    where it sits in the billing lifecycle and moves it along: reminders
    before the due date, grace period if payment doesn't land, suspension
    after that, a one-time deletion warning after a long suspension.

    Network and Government tenants are excluded — Plan.is_self_serve=False
    for both, since those go through a sales-assisted contract, not this
    automated dunning flow. Reuses the same flag 5B's registration form
    already filters on, rather than hardcoding plan names here too.

    Reactivation is NOT this task's job — Phase 5C's
    activate_tenant_on_payment receiver does that immediately when a
    payment confirms, not on the next daily run.
    """
    from apps.core.models import Tenant
    from .models import Plan

    self_serve_slugs = list(Plan.objects.filter(is_self_serve=True).values_list('slug', flat=True))
    tenants = Tenant.objects.filter(
        is_active=True, plan__in=self_serve_slugs,
    ).exclude(status=Tenant.StatusChoices.CANCELLED)

    processed, failed = 0, 0
    for tenant in tenants:
        try:
            _process_tenant_billing(tenant)
            processed += 1
        except Exception:
            failed += 1
            logger.exception(f'check_subscription_due: failed for tenant {tenant.slug} — skipping, sweep continues')

    logger.info(f'check_subscription_due: swept {processed} tenants ({failed} failed)')


def _process_tenant_billing(tenant):
    from apps.core.models import Tenant
    now = timezone.now()

    if tenant.status == Tenant.StatusChoices.TRIAL:
        _handle_trial(tenant, now)
    elif tenant.status == Tenant.StatusChoices.ACTIVE:
        _handle_active(tenant, now)
    elif tenant.status == Tenant.StatusChoices.GRACE_PERIOD:
        _handle_grace_period(tenant, now)
    elif tenant.status == Tenant.StatusChoices.SUSPENDED:
        _handle_suspended(tenant, now)


def _handle_trial(tenant, now):
    """D.5: reminders at day 7/12/13/14 of a 14-day trial, expressed here
    as 7/2/1/0 days remaining. Day 14 with no payment -> GRACE_PERIOD
    (there's no TRIAL_EXPIRED in the real status enum, so a missed trial
    and a missed renewal share the same grace/suspend path from here on)."""
    from apps.core.models import Tenant
    if not tenant.trial_end:
        return
    days_remaining = (tenant.trial_end.date() - now.date()).days

    if days_remaining in (7, 2, 1):
        _send_reminder_email(tenant, f'Your ASMS trial ends in {days_remaining} day(s) — add a payment method to keep access.')
        return

    if days_remaining == 0:
        _send_reminder_email(tenant, 'Your ASMS trial ends today — add a payment method to keep access.')
        return

    if days_remaining < 0:
        tenant.status = Tenant.StatusChoices.GRACE_PERIOD
        tenant.grace_started_at = now
        tenant.save(update_fields=['status', 'grace_started_at'])
        _send_reminder_email(tenant, 'Your ASMS trial has ended. Pay now to avoid restricted access.')
        logger.info(f'{tenant.slug}: trial ended unpaid -> GRACE_PERIOD')


def _handle_active(tenant, now):
    """D.7: reminder 7 days before plan_end; on the due date itself, a
    same-day notice; from day 1 to day 6 past due, silence (this is
    where PesaPal's own automatic card debit — or the school completing
    a MoMo/Airtel prompt — is expected to land); day 7+ past due with no
    payment received -> GRACE_PERIOD."""
    from apps.core.models import Tenant
    if not tenant.plan_end:
        return
    days_until_due = (tenant.plan_end.date() - now.date()).days

    if days_until_due == 7:
        _send_reminder_email(tenant, 'Your ASMS subscription renews in 7 days.')
        return
    if days_until_due > 0:
        return

    days_overdue = -days_until_due
    if days_overdue == 0:
        if tenant.billing_method == Tenant.BillingMethodChoices.PESAPAL_CARD:
            _send_reminder_email(tenant, 'Your card renewal is due today — we\u2019ll confirm once PesaPal processes it.')
        else:
            _send_reminder_email(tenant, 'Your ASMS subscription is due today. Pay now to avoid restricted access.')
        return
    if days_overdue < GRACE_PERIOD_DAYS:
        return  # already reminded on day 0; let the automatic/manual payment land

    tenant.status = Tenant.StatusChoices.GRACE_PERIOD
    tenant.grace_started_at = now
    tenant.save(update_fields=['status', 'grace_started_at'])
    _send_reminder_email(tenant, 'Your ASMS subscription is overdue. Access is now read-only — pay now to restore it.')
    logger.info(f'{tenant.slug}: renewal {days_overdue} days overdue -> GRACE_PERIOD')


def _handle_grace_period(tenant, now):
    from apps.core.models import Tenant
    if not tenant.grace_started_at:
        tenant.grace_started_at = now
        tenant.save(update_fields=['grace_started_at'])
        return

    days_in_grace = (now.date() - tenant.grace_started_at.date()).days
    if days_in_grace < SUSPEND_AFTER_GRACE_DAYS:
        return

    tenant.status = Tenant.StatusChoices.SUSPENDED
    tenant.suspended_at = now
    tenant.save(update_fields=['status', 'suspended_at'])
    _send_reminder_email(tenant, 'Your ASMS account has been suspended for non-payment. Data is retained — pay now to restore access.')
    logger.info(f'{tenant.slug}: {days_in_grace} days in grace, unpaid -> SUSPENDED')


def _handle_suspended(tenant, now):
    if not tenant.suspended_at:
        tenant.suspended_at = now
        tenant.save(update_fields=['suspended_at'])
        return

    days_suspended = (now.date() - tenant.suspended_at.date()).days
    if days_suspended >= DELETION_WARNING_AFTER_DAYS and not tenant.deletion_warning_sent_at:
        tenant.deletion_warning_sent_at = now
        tenant.save(update_fields=['deletion_warning_sent_at'])
        _send_reminder_email(
            tenant,
            'Your ASMS account has been suspended for 60 days. Your data will be '
            'permanently deleted in 14 days unless you pay or contact us.'
        )
        logger.info(f'{tenant.slug}: {days_suspended} days suspended -> deletion warning sent')


def _send_reminder_email(tenant, message: str) -> None:
    """
    Mirrors views._send_welcome_email's try/except pattern — a failed
    send must never break the sweep for every other tenant.
    Recipients: the tenant's School Admin user(s), plus the school's own
    contact email from Tenant.email if it's set and different.
    """
    from apps.accounts.models import User
    from django.conf import settings as dj_settings

    recipients = list(
        User.objects.filter(tenant=tenant, role=User.RoleChoices.SCHOOL_ADMIN)
        .exclude(email='').values_list('email', flat=True)
    )
    if tenant.email and tenant.email not in recipients:
        recipients.append(tenant.email)
    if not recipients:
        logger.warning(f'{tenant.slug}: no recipient email found for billing reminder — skipped')
        return

    try:
        send_mail(
            subject=f'ASMS — {tenant.name}',
            message=f'{message}\n\nManage billing: {tenant.get_portal_url()}',
            from_email=getattr(dj_settings, 'DEFAULT_FROM_EMAIL', 'noreply@asms.app'),
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f'{tenant.slug}: reminder email failed: {e}')

    _send_sms_reminder(tenant, message)


def _send_sms_reminder(tenant, message: str) -> None:
    """
    STUB — Section 6.4 treats SMS as the guaranteed fallback channel for
    every notification that matters, and this one genuinely matters, but
    I haven't seen apps/notifications well enough to know the real
    send-SMS call (only its inbound delivery-report webhook has come up
    in recon so far). Logs the intent so nothing is silently lost; wire
    the real Africa's Talking call in here once that's confirmed.
    """
    logger.info(f'[SMS STUB] would notify {tenant.slug}: {message[:140]}')
