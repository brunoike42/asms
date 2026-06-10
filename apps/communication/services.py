"""
SMS service — Africa's Talking integration.
In development, logs to console instead of sending.
"""
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_sms(phone: str, message: str, tenant=None, trigger='manual',
             student=None, sent_by=None) -> bool:
    """
    Send an SMS via Africa's Talking API.
    Always creates an SMSLog record regardless of outcome.
    Returns True on success, False on failure.
    """
    from apps.communication.models import SMSLog

    log = SMSLog.objects.create(
        tenant=tenant,
        recipient_phone=phone,
        message=message,
        trigger=trigger,
        status='pending',
        related_student=student,
        sent_by=sent_by,
    )

    api_key = getattr(settings, 'AFRICASTALKING_API_KEY', '')
    username = getattr(settings, 'AFRICASTALKING_USERNAME', 'sandbox')

    if not api_key or settings.DEBUG:
        # Development: print instead of sending
        logger.info(f'[SMS DEV] To: {phone} | Message: {message[:80]}...')
        print(f'\n📱 SMS (DEV MODE)\n  To: {phone}\n  Message: {message}\n')
        log.status = 'sent'
        log.sent_at = timezone.now()
        log.provider_ref = 'DEV-MODE'
        log.save()
        return True

    try:
        import africastalking
        africastalking.initialize(username, api_key)
        sms = africastalking.SMS
        sender = getattr(settings, 'AFRICASTALKING_SENDER_ID', 'ASMS')
        response = sms.send(message, [phone], sender_id=sender)
        recipients = response.get('SMSMessageData', {}).get('Recipients', [])
        if recipients:
            rec = recipients[0]
            log.status = 'sent' if rec.get('status') == 'Success' else 'failed'
            log.provider_ref = rec.get('messageId', '')
            log.cost = float(rec.get('cost', '0').replace('UGX ', '').replace(',', '') or 0)
        log.sent_at = timezone.now()
        log.save()
        return log.status == 'sent'
    except Exception as e:
        log.status = 'failed'
        log.error_message = str(e)
        log.save()
        logger.error(f'SMS failed to {phone}: {e}')
        return False


def send_absence_notification(student, date, parent_phone: str, tenant):
    """Standard absence SMS sent to parent when student is marked absent."""
    message = (
        f"Dear Parent/Guardian, {student.get_display_name()} was marked "
        f"ABSENT from {tenant.name} on {date.strftime('%d %B %Y')}. "
        f"Please contact the school if this is unexpected. Call: {tenant.phone}"
    )
    return send_sms(
        phone=parent_phone,
        message=message,
        tenant=tenant,
        trigger='attendance',
        student=student,
    )


def send_fee_reminder(student, invoice, parent_phone: str, tenant):
    """Fee reminder SMS sent to parent when invoice is overdue."""
    message = (
        f"Dear Parent/Guardian, the school fees for {student.get_display_name()} "
        f"at {tenant.name} are outstanding. "
        f"Balance due: UGX {invoice.balance_due:,.0f}. "
        f"Please pay as soon as possible. Call: {tenant.phone}"
    )
    return send_sms(
        phone=parent_phone,
        message=message,
        tenant=tenant,
        trigger='fee',
        student=student,
    )
