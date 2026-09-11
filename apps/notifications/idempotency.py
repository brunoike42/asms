"""
Idempotency guard.

Mirrors the idempotency-key pattern used by Twilio and Stripe: before doing
the side-effecting thing (sending an SMS, charging a card), atomically claim
a key. If the claim fails, someone already claimed it — this is a duplicate
attempt (e.g. a Celery task retried after a timeout, or a signal fired
twice) and must not repeat the send.

This relies entirely on cache.add(), which IS atomic on Redis/Memcached
(the "set if not exists" primitive) — unlike the rate limiter's get-then-set,
this one gives a hard guarantee with no race window.
"""
import hashlib


class IdempotencyGuard:
    def __init__(self, cache, ttl_seconds=3600, key_prefix="smsidem"):
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

    def build_key(self, tenant_key, phone, message, explicit_key=None):
        """If the caller supplies an explicit idempotency key (e.g. a
        BoardingEvent id — the correct domain-level choice, since it's
        stable across retries even if the message text changes), use it.
        Otherwise derive one from content, which still protects against the
        common case: the exact same Celery task retried with identical args.
        """
        if explicit_key:
            raw = f"{tenant_key}:{explicit_key}"
        else:
            raw = f"{tenant_key}:{phone}:{message}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
        return f"{self.key_prefix}:{digest}"

    def claim(self, tenant_key, phone, message, explicit_key=None):
        """Attempt to claim this send. Returns True if this is the first
        (allowed) attempt, False if it's a duplicate that should be
        suppressed."""
        key = self.build_key(tenant_key, phone, message, explicit_key)
        return self.cache.add(key, 1, timeout=self.ttl_seconds)
