"""
Cache backend abstraction.

The circuit breaker, rate limiter, and idempotency guard all need a shared,
atomic key-value store so they work correctly across multiple Celery worker
*processes* (a plain in-process dict would give every worker its own view of
"is the circuit open", which defeats the point).

Rather than importing django.core.cache directly into every module, we depend
on a tiny Protocol that matches Django's cache API. In production you inject
django.core.cache.cache (backed by Redis — required for cross-process
atomicity of .add()/.incr()). In tests and the standalone benchmark script we
inject InMemoryCache, so the exact same CircuitBreaker/RateLimiter/
IdempotencyGuard classes run in both places with no mocking required.

IMPORTANT (production note): Django's LocMemCache is NOT safe for this
purpose because each process gets its own memory space. Use django-redis or
another shared backend for the cache alias passed in here.
"""
import time
import threading


class CacheProtocol:
    """Documents the subset of Django's cache API this package relies on."""

    def get(self, key, default=None):
        raise NotImplementedError

    def set(self, key, value, timeout=None):
        raise NotImplementedError

    def add(self, key, value, timeout=None):
        """Set only if the key doesn't already exist. Returns True if set."""
        raise NotImplementedError

    def incr(self, key, delta=1):
        """Atomically increment. Must raise ValueError if key is absent —
        this matches Django's cache.incr() contract exactly."""
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError


class InMemoryCache(CacheProtocol):
    """Thread-safe in-memory cache matching Django's cache.* semantics.

    Used by the test suite and the benchmark harness so resilience logic
    can be exercised deterministically without spinning up Redis. Safe to
    use in a single Django process for local dev, but NOT across multiple
    processes/workers — see module docstring.
    """

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def _expired(self, entry):
        value, expires_at = entry
        return expires_at is not None and expires_at < time.monotonic()

    def get(self, key, default=None):
        with self._lock:
            entry = self._store.get(key)
            if entry is None or self._expired(entry):
                self._store.pop(key, None)
                return default
            return entry[0]

    def set(self, key, value, timeout=None):
        expires_at = time.monotonic() + timeout if timeout else None
        with self._lock:
            self._store[key] = (value, expires_at)

    def add(self, key, value, timeout=None):
        with self._lock:
            entry = self._store.get(key)
            if entry is not None and not self._expired(entry):
                return False
            expires_at = time.monotonic() + timeout if timeout else None
            self._store[key] = (value, expires_at)
            return True

    def incr(self, key, delta=1):
        with self._lock:
            entry = self._store.get(key)
            if entry is None or self._expired(entry):
                self._store.pop(key, None)
                raise ValueError(f"Key '{key}' not found")
            value, expires_at = entry
            new_value = value + delta
            self._store[key] = (new_value, expires_at)
            return new_value

    def delete(self, key):
        with self._lock:
            self._store.pop(key, None)


def get_django_cache(alias="default"):
    """Lazily fetch a Django cache instance by alias. Import is deferred so
    this module has zero hard Django dependency at import time."""
    from django.core.cache import caches

    return caches[alias]
