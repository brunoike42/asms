"""
Payments signals.

payment_confirmed fires when PesaPal confirms a transaction as COMPLETED.
It then:
  1. Creates a finance.Payment record (links to existing invoice)
  2. Updates FeeInvoice status to PAID (or PARTIAL)
  3. Sends confirmation SMS to parent
  4. Logs the event
"""
import logging
from django.dispatch import Signal, receiver
from django.utils import timezone

logger = logging.getLogger(__name__)

# Custom signal — fired from views._apply_status_update when payment completes
payment_confirmed = Signal()


@receiver(payment_confirmed)
def handle_payment_confirmed(sender, transaction, **kwargs):
    """
    Downstream handler for a confirmed PesaPal payment.
    Creates the finance.Payment record and updates the invoice.
    """
    logger.info(
        f'[payments.signals] Processing confirmed payment: '
        f'{transaction.merchant_reference} — UGX {transaction.amount}'
    )

    # ── 1. Create finance.Payment record ──────────────────────────
    try:
        from apps.finance.models import Payment
        finance_payment = Payment.objects.create(
            tenant           = transaction.tenant,
            invoice          = transaction.invoice,
            amount           = transaction.amount,
            payment_method   = 'online',
            reference        = transaction.confirmation_code or transaction.merchant_reference,
            notes            = (
                f'PesaPal online payment. '
                f'Method: {transaction.payment_method}. '
                f'Tracking: {transaction.order_tracking_id}.'
            ),
            recorded_by      = transaction.initiated_by,
            # status field — adjust field name to match your finance.Payment model
            # status = 'confirmed',
        )
        # Link back to the pesapal transaction
        transaction.finance_payment = finance_payment
        transaction.save(update_fields=['finance_payment'])
        logger.info(f'Finance payment #{finance_payment.pk} created for invoice #{transaction.invoice_id}')
    except Exception as e:
        logger.error(f'Failed to create finance.Payment for txn {transaction.pk}: {e}')

    # ── 2. Update invoice status ───────────────────────────────────
    try:
        _update_invoice_status(transaction.invoice)
    except Exception as e:
        logger.error(f'Failed to update invoice status: {e}')

    # ── 3. Send SMS confirmation to parent ────────────────────────
    try:
        _send_payment_sms(transaction)
    except Exception as e:
        logger.warning(f'SMS send failed for payment {transaction.merchant_reference}: {e}')


def _update_invoice_status(invoice):
    """
    Recalculate invoice status after a new payment is applied.
    Marks as PAID if fully settled, PARTIAL otherwise.
    """
    try:
        # Sum all confirmed payments
        from django.db.models import Sum
        total_paid = invoice.payments.aggregate(total=Sum('amount'))['total'] or 0

        invoice_total = getattr(invoice, 'total_amount', None) or getattr(invoice, 'amount', 0)

        if total_paid >= invoice_total:
            new_status = 'paid'
        elif total_paid > 0:
            new_status = 'partial'
        else:
            new_status = invoice.status

        if invoice.status != new_status:
            invoice.status = new_status
            invoice.save(update_fields=['status'])
            logger.info(f'Invoice #{invoice.pk} status updated to {new_status}')
    except Exception as e:
        logger.error(f'Invoice status update failed: {e}')


def _send_payment_sms(transaction):
    """Send a payment confirmation SMS to the parent."""
    student  = transaction.student
    tenant   = transaction.tenant
    amount   = f'UGX {transaction.amount:,.0f}'
    ref      = transaction.confirmation_code or transaction.merchant_reference
    school   = getattr(tenant, 'name', 'ASMS School')

    message = (
        f'Dear Parent, payment of {amount} for {student.first_name} {student.last_name} '
        f'at {school} has been confirmed. Ref: {ref}. Thank you.'
    )

    # Try Africa's Talking
    phone = transaction.payer_phone
    if not phone:
        # Try guardian phone
        try:
            guardian = student.guardians.filter(is_primary=True).first()
            if guardian:
                phone = getattr(guardian, 'phone_number', '') or getattr(guardian, 'phone', '')
        except Exception:
            pass

    if not phone:
        logger.warning(f'No phone for payment SMS: txn {transaction.merchant_reference}')
        return

    try:
        from django.conf import settings
        at_username = getattr(settings, 'AT_USERNAME', None)
        at_api_key  = getattr(settings, 'AT_API_KEY', None)

        if at_username and at_api_key:
            import africastalking
            africastalking.initialize(at_username, at_api_key)
            sms = africastalking.SMS
            response = sms.send(message, [phone])
            logger.info(f'Payment SMS sent to {phone}: {response}')
        else:
            logger.info(f'[SMS STUB] To: {phone} | {message}')
    except Exception as e:
        logger.error(f'SMS failed for {phone}: {e}')
