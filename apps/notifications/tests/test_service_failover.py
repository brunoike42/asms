from ..cache_backend import InMemoryCache
from ..circuitbreaker import CircuitBreaker
from ..exceptions import ProviderSendError
from ..idempotency import IdempotencyGuard
from ..providers.base import BaseSMSProvider, SMSProviderResult
from ..ratelimit import TokenBucketRateLimiter
from ..service import SMSService


class FakeProvider(BaseSMSProvider):
    """A provider whose behaviour is scripted for the test: either always
    succeeds, always raises a transient error, or always raises a
    permanent error. Records every call it receives."""

    def __init__(self, name, behavior="success"):
        self.name = name
        self.behavior = behavior
        self.calls = []

    def send(self, phone_e164, message, sender_id=None):
        self.calls.append((phone_e164, message))
        if self.behavior == "success":
            return SMSProviderResult(provider=self.name, message_id="msg-1", status="Success", cost="0.01")
        if self.behavior == "transient":
            raise ProviderSendError(f"{self.name} down", is_transient=True, provider=self.name)
        if self.behavior == "permanent":
            raise ProviderSendError(f"{self.name} rejected number", is_transient=False, provider=self.name)
        raise AssertionError(f"unknown behavior {self.behavior}")


def make_service(providers, cache=None, rate_limiter=None, idempotency_guard=None):
    cache = cache or InMemoryCache()

    def breaker_factory(name):
        return CircuitBreaker(name=name, cache=cache, failure_threshold=2, recovery_timeout_seconds=10)

    return SMSService(
        providers=providers,
        breaker_factory=breaker_factory,
        rate_limiter=rate_limiter,
        idempotency_guard=idempotency_guard,
    )


def test_sends_via_primary_provider_when_healthy():
    primary = FakeProvider("primary", "success")
    service = make_service([primary])

    outcome = service.send("tenant-1", "0712345678", "hello")

    assert outcome.ok is True
    assert outcome.status == "sent"
    assert outcome.provider == "primary"
    assert len(primary.calls) == 1


def test_fails_over_to_secondary_when_primary_is_transiently_down():
    primary = FakeProvider("primary", "transient")
    secondary = FakeProvider("secondary", "success")
    service = make_service([primary, secondary])

    outcome = service.send("tenant-1", "0712345678", "hello")

    assert outcome.ok is True
    assert outcome.provider == "secondary"
    assert len(primary.calls) == 1
    assert len(secondary.calls) == 1


def test_all_providers_down_returns_failed_outcome():
    primary = FakeProvider("primary", "transient")
    secondary = FakeProvider("secondary", "transient")
    service = make_service([primary, secondary])

    outcome = service.send("tenant-1", "0712345678", "hello")

    assert outcome.ok is False
    assert outcome.status == "failed"
    assert len(outcome.attempts) == 2


def test_open_circuit_skips_provider_without_calling_it():
    cache = InMemoryCache()
    primary = FakeProvider("primary", "transient")
    secondary = FakeProvider("secondary", "success")
    service = make_service([primary, secondary], cache=cache)

    # Trip primary's breaker (threshold=2) with two failed sends.
    service.send("tenant-1", "0712345678", "msg one")
    service.send("tenant-1", "0798765432", "msg two")
    assert len(primary.calls) == 2

    # Third send: breaker should now be open, primary must NOT be called again.
    outcome = service.send("tenant-1", "0700000001", "msg three")

    assert outcome.ok is True
    assert outcome.provider == "secondary"
    assert len(primary.calls) == 2  # unchanged — breaker skipped it


def test_invalid_phone_number_never_reaches_a_provider():
    primary = FakeProvider("primary", "success")
    service = make_service([primary])

    outcome = service.send("tenant-1", "not-a-number", "hello")

    assert outcome.ok is False
    assert outcome.status == "invalid_number"
    assert len(primary.calls) == 0


def test_duplicate_send_is_suppressed_and_provider_not_called_twice():
    primary = FakeProvider("primary", "success")
    guard = IdempotencyGuard(cache=InMemoryCache())
    service = make_service([primary], idempotency_guard=guard)

    first = service.send("tenant-1", "0712345678", "bus arrived")
    second = service.send("tenant-1", "0712345678", "bus arrived")

    assert first.status == "sent"
    assert second.status == "duplicate_suppressed"
    assert len(primary.calls) == 1


def test_rate_limited_tenant_is_blocked_before_hitting_provider():
    primary = FakeProvider("primary", "success")
    limiter = TokenBucketRateLimiter(cache=InMemoryCache(), rate_per_second=0, capacity=1)
    service = make_service([primary], rate_limiter=limiter)

    first = service.send("tenant-1", "0712345678", "one")
    second = service.send("tenant-1", "0798765432", "two")

    assert first.status == "sent"
    assert second.status == "rate_limited"
    assert len(primary.calls) == 1
