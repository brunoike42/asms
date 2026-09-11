import time

from ..cache_backend import InMemoryCache
from ..circuitbreaker import CircuitBreaker, CircuitState


def make_breaker(**overrides):
    cache = InMemoryCache()
    defaults = dict(name="testprovider", cache=cache, failure_threshold=3, recovery_timeout_seconds=0.2, half_open_max_calls=1)
    defaults.update(overrides)
    return CircuitBreaker(**defaults), cache


def test_starts_closed():
    breaker, _ = make_breaker()
    assert breaker.current_state() == CircuitState.CLOSED
    assert breaker.allow_request() is True


def test_opens_after_threshold_failures():
    breaker, _ = make_breaker(failure_threshold=3)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.current_state() == CircuitState.OPEN
    assert breaker.allow_request() is False


def test_success_resets_failure_count_below_threshold():
    breaker, _ = make_breaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()  # should reset counter
    breaker.record_failure()
    assert breaker.current_state() == CircuitState.CLOSED


def test_transitions_to_half_open_after_recovery_timeout():
    breaker, _ = make_breaker(failure_threshold=1, recovery_timeout_seconds=0.05)
    breaker.record_failure()
    assert breaker.current_state() == CircuitState.OPEN
    time.sleep(0.08)
    assert breaker.allow_request() is True
    assert breaker.current_state() == CircuitState.HALF_OPEN


def test_half_open_limits_trial_calls():
    breaker, _ = make_breaker(failure_threshold=1, recovery_timeout_seconds=0.05, half_open_max_calls=1)
    breaker.record_failure()
    time.sleep(0.08)
    assert breaker.allow_request() is True  # the one allowed probe
    assert breaker.allow_request() is False  # second concurrent probe denied


def test_half_open_failure_snaps_back_open():
    breaker, _ = make_breaker(failure_threshold=1, recovery_timeout_seconds=0.05)
    breaker.record_failure()
    time.sleep(0.08)
    breaker.allow_request()  # moves to half-open
    breaker.record_failure()  # probe failed
    assert breaker.current_state() == CircuitState.OPEN


def test_half_open_success_closes_circuit():
    breaker, _ = make_breaker(failure_threshold=1, recovery_timeout_seconds=0.05)
    breaker.record_failure()
    time.sleep(0.08)
    breaker.allow_request()
    breaker.record_success()
    assert breaker.current_state() == CircuitState.CLOSED


def test_breaker_state_is_shared_across_instances_via_cache():
    """Simulates two Celery worker processes sharing one Redis-backed cache:
    a breaker trip seen by worker A must be visible to worker B."""
    cache = InMemoryCache()
    worker_a = CircuitBreaker(name="shared", cache=cache, failure_threshold=1)
    worker_b = CircuitBreaker(name="shared", cache=cache, failure_threshold=1)

    worker_a.record_failure()

    assert worker_b.allow_request() is False
