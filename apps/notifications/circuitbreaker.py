"""
Circuit breaker per SMS provider.

Standard three-state design (closed / open / half-open), as described in the
resilience literature: track recent failures, "open" the circuit once a
threshold is crossed so calls fail fast instead of piling up on a dead
dependency, then probe with a small number of trial requests after a cooldown
to see whether the provider has recovered.

State is stored in the shared cache (see cache_backend.py) so all Celery
workers see the same breaker state for a given provider — one worker tripping
the breaker on Africa's Talking should stop *every* worker from hammering it,
not just the one that saw the failure.
"""
import time


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name,
        cache,
        failure_threshold=5,
        recovery_timeout_seconds=30,
        half_open_max_calls=1,
    ):
        self.name = name
        self.cache = cache
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_calls = half_open_max_calls

    def _key(self, suffix):
        return f"smscb:{self.name}:{suffix}"

    def _state(self):
        return self.cache.get(self._key("state"), CircuitState.CLOSED)

    def _opened_at(self):
        return self.cache.get(self._key("opened_at"))

    def allow_request(self):
        """Returns True if a call to the provider should be attempted."""
        state = self._state()

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            opened_at = self._opened_at()
            if opened_at is not None and (time.monotonic() - opened_at) >= self.recovery_timeout_seconds:
                # Cooldown elapsed — allow a probe through half-open. This
                # call itself IS the first probe, so it must count against
                # half_open_max_calls immediately (set to 1, not 0) —
                # otherwise a second concurrent caller slips through before
                # anyone increments the counter.
                self.cache.set(self._key("state"), CircuitState.HALF_OPEN, timeout=self.recovery_timeout_seconds * 4)
                self.cache.set(self._key("half_open_calls"), 1, timeout=self.recovery_timeout_seconds * 4)
                return True
            return False

        if state == CircuitState.HALF_OPEN:
            calls = self.cache.get(self._key("half_open_calls"), 0)
            if calls < self.half_open_max_calls:
                try:
                    self.cache.incr(self._key("half_open_calls"))
                except ValueError:
                    self.cache.set(self._key("half_open_calls"), 1, timeout=self.recovery_timeout_seconds * 4)
                return True
            return False

        return True

    def record_success(self):
        state = self._state()
        if state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            # Recovered — close the circuit and reset failure counters.
            self.cache.set(self._key("state"), CircuitState.CLOSED, timeout=None)
            self.cache.delete(self._key("failures"))
            self.cache.delete(self._key("opened_at"))
        else:
            # Still closed; a success can reset a partial failure streak.
            self.cache.delete(self._key("failures"))

    def record_failure(self):
        state = self._state()

        if state == CircuitState.HALF_OPEN:
            # Probe failed — snap back open immediately.
            self._trip()
            return

        if not self.cache.add(self._key("failures"), 1, timeout=self.recovery_timeout_seconds * 4):
            try:
                failures = self.cache.incr(self._key("failures"))
            except ValueError:
                self.cache.set(self._key("failures"), 1, timeout=self.recovery_timeout_seconds * 4)
                failures = 1
        else:
            failures = 1

        if failures >= self.failure_threshold:
            self._trip()

    def _trip(self):
        self.cache.set(self._key("state"), CircuitState.OPEN, timeout=self.recovery_timeout_seconds * 4)
        self.cache.set(self._key("opened_at"), time.monotonic(), timeout=self.recovery_timeout_seconds * 4)
        self.cache.delete(self._key("failures"))

    def current_state(self):
        """For monitoring/dashboards — not used in the hot path."""
        return self._state()
