"""
SMSService — the orchestrator.

This is the piece that turns "call a provider" into something resembling
what Twilio/AWS describe as reliable messaging: validate the input, refuse
to double-send, respect a rate budget, then walk a prioritized list of
providers where each one is wrapped in its own circuit breaker so a dead
provider gets skipped instead of retried into the ground.

Deliberately has zero Django imports so it can be unit tested and
benchmarked in plain Python. The Django-specific glue (reading settings,
writing SMSMessage rows) lives in sms.py.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .exceptions import (
    AllProvidersExhaustedError,
    InvalidPhoneNumberError,
    ProviderSendError,
    RateLimitExceededError,
)
from .phone import normalize_phone

logger = logging.getLogger("notifications.sms")


@dataclass
class AttemptRecord:
    provider: str
    outcome: str  # "sent" | "failed" | "skipped_circuit_open"
    error: Optional[str] = None


@dataclass
class SendOutcome:
    ok: bool
    status: str  # "sent" | "duplicate_suppressed" | "rate_limited" | "invalid_number" | "failed"
    phone_e164: Optional[str] = None
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    cost: Optional[str] = None
    error: Optional[str] = None
    attempts: List[AttemptRecord] = field(default_factory=list)


class SMSService:
    def __init__(
        self,
        providers,
        breaker_factory,
        rate_limiter=None,
        idempotency_guard=None,
        default_region="UG",
        rate_limit_tokens=1,
    ):
        """
        providers: ordered list of BaseSMSProvider instances, tried in order
            (e.g. [AfricasTalkingProvider(...), TwilioProvider(...)]).
        breaker_factory: callable(provider_name) -> CircuitBreaker. Passed in
            rather than constructed here so callers control breaker config
            per provider and can share one factory/cache across the app.
        rate_limiter: optional TokenBucketRateLimiter. None disables limiting.
        idempotency_guard: optional IdempotencyGuard. None disables dedup.
        """
        if not providers:
            raise ValueError("SMSService requires at least one provider")
        self.providers = providers
        self.breaker_factory = breaker_factory
        self.rate_limiter = rate_limiter
        self.idempotency_guard = idempotency_guard
        self.default_region = default_region
        self.rate_limit_tokens = rate_limit_tokens

    def send(self, tenant_key, phone, message, *, sender_id=None, idempotency_key=None, default_region=None):
        # 1. Validate + normalize. Permanent failure — no point going further.
        try:
            phone_e164 = normalize_phone(phone, default_region or self.default_region)
        except InvalidPhoneNumberError as exc:
            logger.warning("Rejecting SMS to tenant=%s: %s", tenant_key, exc)
            return SendOutcome(ok=False, status="invalid_number", error=str(exc))

        # 2. Idempotency — refuse to send the same thing twice.
        if self.idempotency_guard is not None:
            claimed = self.idempotency_guard.claim(tenant_key, phone_e164, message, idempotency_key)
            if not claimed:
                logger.info("Suppressing duplicate SMS to %s for tenant=%s", phone_e164, tenant_key)
                return SendOutcome(ok=True, status="duplicate_suppressed", phone_e164=phone_e164)

        # 3. Rate limit — protect cost and provider throughput limits.
        if self.rate_limiter is not None:
            if not self.rate_limiter.allow(str(tenant_key), tokens=self.rate_limit_tokens):
                logger.warning("Rate limit exceeded for tenant=%s", tenant_key)
                return SendOutcome(ok=False, status="rate_limited", phone_e164=phone_e164)

        # 4. Walk the provider chain, respecting each provider's circuit breaker.
        attempts = []
        for provider in self.providers:
            breaker = self.breaker_factory(provider.name)

            if not breaker.allow_request():
                attempts.append(AttemptRecord(provider=provider.name, outcome="skipped_circuit_open"))
                continue

            try:
                result = provider.send(phone_e164, message, sender_id=sender_id)
            except ProviderSendError as exc:
                attempts.append(AttemptRecord(provider=provider.name, outcome="failed", error=str(exc)))
                if exc.is_transient:
                    breaker.record_failure()
                    continue  # try the next provider
                else:
                    # Permanent failure (bad number format the provider itself
                    # rejects, blacklist, etc). Still worth trying exactly one
                    # more provider since rejection reasons are sometimes
                    # provider-specific, but don't record a breaker failure —
                    # this wasn't the provider's fault.
                    continue

            breaker.record_success()
            return SendOutcome(
                ok=True,
                status="sent",
                phone_e164=phone_e164,
                provider=result.provider,
                provider_message_id=result.message_id,
                cost=result.cost,
                attempts=attempts,
            )

        logger.error("All SMS providers exhausted for tenant=%s phone=%s: %s", tenant_key, phone_e164, attempts)
        return SendOutcome(
            ok=False,
            status="failed",
            phone_e164=phone_e164,
            error="All providers failed or unavailable",
            attempts=attempts,
        )
