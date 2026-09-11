"""
Optional Celery wrapper around send_sms for call sites that want to enqueue
rather than block inline (send_sms() itself is synchronous and already has
its own resilience — failover, breakers — so most callers, including the
existing transport/tasks.py, can keep calling it directly from inside a
task they're already running in). Use send_sms_async.delay(...) instead when
you want the *outer* Celery retry/backoff layer too, e.g. for a rate-limited
send that should be retried later rather than dropped.
"""
import random

from celery import shared_task

from .exceptions import RateLimitExceededError


def _backoff_with_jitter(retry_count, base_seconds=5, max_seconds=300):
    """Exponential backoff with full jitter — the same approach Twilio's
    own event delivery retries use, to avoid every queued retry landing on
    the provider at the same instant (a 'retry storm')."""
    exp = min(max_seconds, base_seconds * (2 ** retry_count))
    return random.uniform(0, exp)


@shared_task(bind=True, max_retries=5)
def send_sms_async(self, tenant_id, phone, message, sender_id=None, idempotency_key=None):
    from .models import SMSMessage  # local import avoids app-loading order issues

    tenant_model = SMSMessage._meta.get_field("tenant").related_model
    tenant = tenant_model.objects.get(pk=tenant_id)

    from .sms import get_service

    outcome = get_service().send(
        tenant_key=tenant_id,
        phone=phone,
        message=message,
        sender_id=sender_id,
        idempotency_key=idempotency_key,
    )

    if outcome.status == "rate_limited":
        raise self.retry(
            exc=RateLimitExceededError(tenant_id),
            countdown=_backoff_with_jitter(self.request.retries),
        )

    from .sms import _log_to_db

    _log_to_db(tenant, outcome, message, idempotency_key)
    return outcome.ok
