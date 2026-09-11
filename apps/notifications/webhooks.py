"""
Delivery receipt (DLR) webhooks.

Providers call these URLs asynchronously, sometime after the initial send,
to report final delivery status. Twilio's own guidance is to keep these
handlers fast and idempotent (an event can be delivered more than once) and
to push heavy processing onto a queue rather than doing it inline — we do
the update itself inline since it's a single indexed row update, but you
should put this behind a queueing layer (e.g. a reverse proxy limiting
concurrency) if delivery volume gets large.

Wire these into your project's urls.py — see urls.py in this package.
"""
import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import SMSMessage

logger = logging.getLogger("notifications.webhooks")


@csrf_exempt
@require_POST
def africastalking_delivery_report(request):
    """AT posts form-encoded fields: id, status, phoneNumber, networkCode,
    failureReason. 'id' matches the messageId we stored as
    provider_message_id at send time."""
    message_id = request.POST.get("id")
    status = (request.POST.get("status") or "").strip()

    if not message_id:
        return HttpResponseBadRequest("Missing 'id'")

    _apply_delivery_status(provider="africastalking", provider_message_id=message_id, provider_status=status)
    return HttpResponse("OK")


@csrf_exempt
@require_POST
def twilio_status_callback(request):
    """Twilio posts form-encoded MessageSid / MessageStatus.

    NOTE: production deployments should validate the X-Twilio-Signature
    header using twilio.request_validator.RequestValidator before trusting
    this payload — omitted here to keep the sample dependency-light, but do
    not ship this to production without it.
    """
    message_sid = request.POST.get("MessageSid")
    status = (request.POST.get("MessageStatus") or "").strip()

    if not message_sid:
        return HttpResponseBadRequest("Missing 'MessageSid'")

    _apply_delivery_status(provider="twilio", provider_message_id=message_sid, provider_status=status)
    return HttpResponse("OK")


_DELIVERED_STATUSES = {"delivered", "success"}
_FAILED_STATUSES = {"failed", "undelivered", "rejected"}


def _apply_delivery_status(provider, provider_message_id, provider_status):
    lowered = provider_status.lower()

    try:
        record = SMSMessage.objects.get(provider=provider, provider_message_id=provider_message_id)
    except SMSMessage.DoesNotExist:
        logger.warning(
            "DLR for unknown message: provider=%s id=%s status=%s",
            provider, provider_message_id, provider_status,
        )
        return
    except SMSMessage.MultipleObjectsReturned:
        logger.warning(
            "Multiple SMSMessage rows for provider=%s id=%s — updating most recent",
            provider, provider_message_id,
        )
        record = (
            SMSMessage.objects.filter(provider=provider, provider_message_id=provider_message_id)
            .order_by("-created_at")
            .first()
        )

    if lowered in _DELIVERED_STATUSES:
        # Idempotent: re-delivering the same "delivered" event a second
        # time is a harmless no-op, matching Twilio's own guidance that
        # event delivery can duplicate and consumers must tolerate it.
        record.status = SMSMessage.Status.DELIVERED
        record.delivered_at = record.delivered_at or timezone.now()
    elif lowered in _FAILED_STATUSES:
        record.status = SMSMessage.Status.FAILED
        record.error_message = record.error_message or f"Provider reported status: {provider_status}"

    record.save(update_fields=["status", "delivered_at", "error_message", "updated_at"])
