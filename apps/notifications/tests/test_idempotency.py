from ..cache_backend import InMemoryCache
from ..idempotency import IdempotencyGuard


def test_first_claim_succeeds_second_is_suppressed():
    guard = IdempotencyGuard(cache=InMemoryCache())
    assert guard.claim("tenant-1", "+256712345678", "hello") is True
    assert guard.claim("tenant-1", "+256712345678", "hello") is False


def test_different_message_content_is_not_deduped():
    guard = IdempotencyGuard(cache=InMemoryCache())
    assert guard.claim("tenant-1", "+256712345678", "message A") is True
    assert guard.claim("tenant-1", "+256712345678", "message B") is True


def test_explicit_key_dedupes_even_if_message_text_differs():
    """This is the correct pattern for BoardingEvent-style callers: the
    domain event id is stable across retries even if the rendered message
    text changes (e.g. it includes a timestamp)."""
    guard = IdempotencyGuard(cache=InMemoryCache())
    assert guard.claim("tenant-1", "+256712345678", "arrived at 08:00", explicit_key="event-42") is True
    assert guard.claim("tenant-1", "+256712345678", "arrived at 08:01", explicit_key="event-42") is False


def test_different_tenants_do_not_collide():
    guard = IdempotencyGuard(cache=InMemoryCache())
    assert guard.claim("tenant-1", "+256712345678", "hello") is True
    assert guard.claim("tenant-2", "+256712345678", "hello") is True
