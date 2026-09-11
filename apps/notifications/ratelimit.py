"""
Per-tenant token bucket rate limiter.

Token bucket lets a tenant burst up to `capacity` messages, then refills at
`rate_per_second`. Chosen over a fixed window because fixed windows allow
2x-the-limit bursts at window boundaries, and over a pure sliding window
because token bucket is cheaper to compute and is what production API
gateways use for this exact problem.

HONEST LIMITATION: this implementation does a get-then-set on the cache,
which is not a single atomic operation. Under heavy concurrent access from
multiple processes against a shared Redis cache, two requests can race and
both see enough tokens, letting a *few* extra messages through right at the
boundary. For an SMS notification system (bounded by human events — bus
arrivals, boarding taps) this is an acceptable tradeoff. If you need hard
guarantees at high concurrency, replace the body of `allow()` with a Redis
Lua script implementing the same GCRA logic atomically server-side.
"""
import time


class TokenBucketRateLimiter:
    def __init__(self, cache, rate_per_second, capacity, key_prefix="smsrl"):
        self.cache = cache
        self.rate_per_second = rate_per_second
        self.capacity = capacity
        self.key_prefix = key_prefix

    def _key(self, bucket_key):
        return f"{self.key_prefix}:{bucket_key}"

    def allow(self, bucket_key, tokens=1):
        """Returns True and consumes `tokens` if available, else False."""
        now = time.monotonic()
        key = self._key(bucket_key)
        state = self.cache.get(key)

        if state is None:
            available = self.capacity
        else:
            available, last_ts = state["tokens"], state["ts"]
            elapsed = max(0.0, now - last_ts)
            available = min(self.capacity, available + elapsed * self.rate_per_second)

        if available >= tokens:
            self.cache.set(key, {"tokens": available - tokens, "ts": now}, timeout=3600)
            return True

        self.cache.set(key, {"tokens": available, "ts": now}, timeout=3600)
        return False

    def tokens_remaining(self, bucket_key):
        state = self.cache.get(self._key(bucket_key))
        if state is None:
            return self.capacity
        now = time.monotonic()
        available, last_ts = state["tokens"], state["ts"]
        elapsed = max(0.0, now - last_ts)
        return min(self.capacity, available + elapsed * self.rate_per_second)
