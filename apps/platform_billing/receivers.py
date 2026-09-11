"""
ASMS Platform Billing — Phase 5C receiver.
On a confirmed platform payment: record it (PlatformPayment.save() marks
the invoice paid on its own, from Phase 5A), then move the tenant to
ACTIVE and clear whatever lifecycle state it was in.
"""
import logging
from datetime import timedelta

from django.dispatch import receiver
from django.utils import timezone

from .signals import platform_payment_confirmed
from .models import Plan, PlatformPayment

logger = logging.getLogger(__name__)


def _method_for_transaction(txn) -> str:
    """
    Best-effort mapping from PesaPal's returned payment_method string to
    PlatformPayment.MethodChoices. Not verified against a real PesaPal
    sandbox response yet — check this against actual transaction data
    once live and adjust the substring matches if PesaPal's wording
    differs (e.g. 'MPESA' vs 'M-PESA', 'AIRTELMONEY' vs 'AIRTEL').
    """
    pm = (txn.payment_method or '').lower()
    if 'momo' in pm or 'mtn' in pm:
        return PlatformPayment.MethodChoices.MTN_MOMO
    if 'airtel' in pm:
        return PlatformPayment.MethodChoices.AIRTEL_MONEY
    if 'bank' in pm:
        return PlatformPayment.MethodChoices.BANK_TRANSFER
    return PlatformPayment.MethodChoices.PESAPAL_CARD


@receiver(platform_payment_confirmed)
def activate_tenant_on_payment(sender, transaction, **kwargs):
    invoice = transaction.invoice
    tenant = invoice.tenant

    if not PlatformPayment.objects.filter(invoice=invoice).exists():
        PlatformPayment.objects.create(
            tenant=tenant,
            invoice=invoice,
            amount=transaction.amount,
            method=_method_for_transaction(transaction),
            reference=transaction.order_tracking_id,
            is_recurring_charge=transaction.is_recurring_setup,
            raw_gateway_response=transaction.status_response,
        )

    period_days = 30 if invoice.plan.billing_interval == Plan.BillingIntervalChoices.MONTHLY else 365
    tenant.status = tenant.StatusChoices.ACTIVE
    tenant.plan_end = timezone.now() + timedelta(days=period_days)
    tenant.grace_started_at = None
    tenant.suspended_at = None
    if transaction.is_recurring_setup:
        tenant.billing_method = tenant.BillingMethodChoices.PESAPAL_CARD
    tenant.save(update_fields=['status', 'plan_end', 'grace_started_at', 'suspended_at', 'billing_method'])

    logger.info(f'Tenant activated on payment: {tenant.slug} -> ACTIVE until {tenant.plan_end.date()}')
