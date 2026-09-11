"""
Exception hierarchy for the SMS subsystem.

Kept deliberately flat and framework-agnostic (no Django imports) so the same
exceptions can be raised/caught from the benchmark harness and the test suite
without pulling in Django.
"""


class SMSError(Exception):
    """Base class for every error this package raises."""


class InvalidPhoneNumberError(SMSError):
    """The phone number could not be parsed/normalized to E.164.

    This is a *permanent* failure — retrying or trying another provider
    will not help. Callers should not retry on this exception.
    """


class ProviderSendError(SMSError):
    """A provider rejected or failed to send a message.

    is_transient distinguishes failures worth retrying/failing-over on
    (network errors, 5xx, carrier congestion, rate limiting on the
    provider's side) from permanent ones (blacklisted number, invalid
    sender ID, account suspended) where trying again — even on a
    different provider — is very unlikely to succeed but is still
    attempted once since providers do occasionally reject numbers that
    a different carrier route accepts.
    """

    def __init__(self, message, *, is_transient=True, provider=None, raw_response=None):
        super().__init__(message)
        self.is_transient = is_transient
        self.provider = provider
        self.raw_response = raw_response


class CircuitOpenError(SMSError):
    """Raised internally when a provider's circuit breaker is open.

    The service layer catches this and moves on to the next provider in
    the chain rather than propagating it.
    """

    def __init__(self, provider_name):
        super().__init__(f"Circuit breaker open for provider '{provider_name}'")
        self.provider_name = provider_name


class AllProvidersExhaustedError(SMSError):
    """Every configured provider failed or had an open circuit."""


class RateLimitExceededError(SMSError):
    """The tenant has exceeded its configured SMS send rate."""

    def __init__(self, tenant_key, retry_after_seconds=None):
        super().__init__(f"SMS rate limit exceeded for tenant '{tenant_key}'")
        self.tenant_key = tenant_key
        self.retry_after_seconds = retry_after_seconds
