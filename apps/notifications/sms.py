"""
Public facade.

`send_sms(tenant, phone, message)` keeps the EXACT signature the rest of the
codebase already imports (see apps/transport/tasks.py) — nothing else in the
project needs to change. Everything advanced (failover, circuit breaking,
rate limiting, idempotency, DB logging) happens transparently behind this
one function.

Configuration lives in Django settings — see settings_template.py in this
package for the full block to copy into your project's settings.py.
"""
import logging

from django.conf import settings

from .cache_backend import get_django_cache
from .circuitbreaker import CircuitBreaker
from .exceptions import SMSError
from .idempotency import IdempotencyGuard
from .ratelimit import TokenBucketRateLimiter
from .service import SMSService

logger = logging.getLogger("notifications.sms")

_service_singleton = None


def _build_providers():
    from .providers.console import ConsoleProvider

    configured = getattr(settings, "NOTIFICATIONS_PROVIDERS", None)
    if not configured:
        # Safe default for fresh installs / test runs: log to console
        # instead of silently failing to import a provider that isn't
        # configured yet. Covers both "setting absent" and "setting set to
        # an empty list" — both mean "nothing configured yet".
        logger.warning(
            "NOTIFICATIONS_PROVIDERS not set — defaulting to ConsoleProvider only. "
            "See notifications/settings_template.py to configure real providers."
        )
        return [ConsoleProvider()]

    providers = []
    for entry in configured:
        provider_type = entry["type"]
        kwargs = {k: v for k, v in entry.items() if k != "type"}

        if provider_type == "africastalking":
            from .providers.africastalking import AfricasTalkingProvider

            providers.append(AfricasTalkingProvider(**kwargs))
        elif provider_type == "twilio":
            from .providers.twilio import TwilioProvider

            providers.append(TwilioProvider(**kwargs))
        elif provider_type == "console":
            providers.append(ConsoleProvider())
        else:
            raise ValueError(f"Unknown NOTIFICATIONS_PROVIDERS entry type: {provider_type!r}")

    return providers


def get_service():
    global _service_singleton
    if _service_singleton is not None:
        return _service_singleton

    cache = get_django_cache(getattr(settings, "NOTIFICATIONS_CACHE_ALIAS", "default"))
    providers = _build_providers()

    breaker_cfg = getattr(settings, "NOTIFICATIONS_CIRCUIT_BREAKER", {})

    def breaker_factory(provider_name):
        return CircuitBreaker(
            name=provider_name,
            cache=cache,
            failure_threshold=breaker_cfg.get("failure_threshold", 5),
            recovery_timeout_seconds=breaker_cfg.get("recovery_timeout_seconds", 30),
            half_open_max_calls=breaker_cfg.get("half_open_max_calls", 1),
        )

    rate_cfg = getattr(settings, "NOTIFICATIONS_RATE_LIMIT", None)
    rate_limiter = None
    if rate_cfg:
        rate_limiter = TokenBucketRateLimiter(
            cache=cache,
            rate_per_second=rate_cfg["rate_per_second"],
            capacity=rate_cfg["capacity"],
        )

    idem_cfg = getattr(settings, "NOTIFICATIONS_IDEMPOTENCY", {})
    idempotency_guard = None
    if idem_cfg.get("enabled", True):
        idempotency_guard = IdempotencyGuard(cache=cache, ttl_seconds=idem_cfg.get("ttl_seconds", 3600))

    _service_singleton = SMSService(
        providers=providers,
        breaker_factory=breaker_factory,
        rate_limiter=rate_limiter,
        idempotency_guard=idempotency_guard,
        default_region=getattr(settings, "NOTIFICATIONS_DEFAULT_REGION", "UG"),
    )
    return _service_singleton


def _log_to_db(tenant, outcome, message, idempotency_key):
    """Best-effort DB write. Never let a logging failure take down the
    calling Celery task — the SMS may have already been sent."""
    try:
        from .models import SMSMessage

        SMSMessage.objects.create(
            tenant=tenant,
            phone_e164=outcome.phone_e164 or "",
            message=message,
            status=outcome.status,
            provider=outcome.provider or "",
            provider_message_id=outcome.provider_message_id or "",
            cost=outcome.cost or "",
            error_message=outcome.error or "",
            idempotency_key=idempotency_key or "",
            attempt_log=[a.__dict__ for a in outcome.attempts],
        )
    except Exception:
        logger.exception("Failed to persist SMSMessage record (send itself may have succeeded)")


def send_sms(tenant, phone, message, *, sender_id=None, idempotency_key=None):
    """Drop-in for the original assumption:
    notifications.sms.send_sms(tenant, phone, message)

    Returns True if the message was sent (or was a suppressed duplicate of
    an already-sent message), False otherwise. Never raises — callers in
    transport/tasks.py were written against a function that doesn't, and
    changing that contract would silently break every call site.
    """
    tenant_key = getattr(tenant, "pk", None) or getattr(tenant, "id", None) or str(tenant)

    try:
        outcome = get_service().send(
            tenant_key=tenant_key,
            phone=phone,
            message=message,
            sender_id=sender_id,
            idempotency_key=idempotency_key,
        )
    except SMSError as exc:
        logger.error("Unexpected SMS error for tenant=%s: %s", tenant_key, exc)
        return False

    _log_to_db(tenant, outcome, message, idempotency_key)

    if not outcome.ok:
        logger.error(
            "SMS to %s failed for tenant=%s: status=%s error=%s attempts=%s",
            outcome.phone_e164, tenant_key, outcome.status, outcome.error, outcome.attempts,
        )

    return outcome.ok
