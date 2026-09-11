import time

from ..cache_backend import InMemoryCache
from ..ratelimit import TokenBucketRateLimiter


def test_allows_up_to_capacity_then_blocks():
    cache = InMemoryCache()
    limiter = TokenBucketRateLimiter(cache=cache, rate_per_second=1, capacity=3)

    assert limiter.allow("tenant-1") is True
    assert limiter.allow("tenant-1") is True
    assert limiter.allow("tenant-1") is True
    assert limiter.allow("tenant-1") is False  # bucket exhausted


def test_refills_over_time():
    cache = InMemoryCache()
    limiter = TokenBucketRateLimiter(cache=cache, rate_per_second=20, capacity=1)

    assert limiter.allow("tenant-1") is True
    assert limiter.allow("tenant-1") is False
    time.sleep(0.1)  # 20 tokens/sec * 0.1s = 2 tokens, capped at capacity=1
    assert limiter.allow("tenant-1") is True


def test_tenants_are_isolated():
    cache = InMemoryCache()
    limiter = TokenBucketRateLimiter(cache=cache, rate_per_second=1, capacity=1)

    assert limiter.allow("tenant-A") is True
    assert limiter.allow("tenant-A") is False
    # A different tenant's bucket is untouched by tenant-A's usage.
    assert limiter.allow("tenant-B") is True


def test_never_exceeds_capacity_even_after_long_idle():
    cache = InMemoryCache()
    limiter = TokenBucketRateLimiter(cache=cache, rate_per_second=1000, capacity=2)
    limiter.cache.set(
        limiter._key("tenant-1"),
        {"tokens": 0, "ts": time.monotonic() - 3600},  # "an hour ago"
        timeout=3600,
    )
    # Even after a huge idle gap, only `capacity` tokens are available.
    assert limiter.allow("tenant-1", tokens=2) is True
    assert limiter.allow("tenant-1", tokens=1) is False
