"""Window boundaries, isolation and concurrent use of the real counter."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from app.core.rate_limits import RateLimitCapacityError, RequestRateLimiter


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_limit_retry_rounding_and_exact_window_boundary():
    clock = Clock()
    limiter = RequestRateLimiter(clock=clock)
    owner = uuid4()

    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 0
    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 0
    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 60
    clock.now = 0.1
    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 60
    clock.now = 59.9
    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 1
    clock.now = 60
    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 0
    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 0
    assert limiter.consume(owner, "ai", limit=2, window_seconds=60) == 60


def test_users_and_request_groups_have_separate_allowances():
    limiter = RequestRateLimiter(clock=Clock())
    owner, other = uuid4(), uuid4()
    assert limiter.consume(owner, "ai", limit=1, window_seconds=60) == 0
    assert limiter.consume(owner, "ai", limit=1, window_seconds=60) == 60
    assert limiter.consume(owner, "upload", limit=1, window_seconds=60) == 0
    assert limiter.consume(other, "ai", limit=1, window_seconds=60) == 0


def test_concurrent_requests_cannot_exceed_one_users_limit():
    limiter = RequestRateLimiter(clock=Clock())
    owner = uuid4()

    def consume(_):
        return limiter.consume(owner, "ai", limit=10, window_seconds=60)

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(consume, range(100)))
    assert results.count(0) == 10
    assert results.count(60) == 90


def test_full_store_preserves_live_limits_and_reuses_only_expired_space():
    clock = Clock()
    limiter = RequestRateLimiter(max_buckets=2, clock=clock)
    first, second, third = uuid4(), uuid4(), uuid4()
    assert limiter.consume(first, "ai", limit=1, window_seconds=60) == 0
    clock.now = 10
    assert limiter.consume(second, "ai", limit=1, window_seconds=60) == 0
    clock.now = 20
    with pytest.raises(RateLimitCapacityError) as failure:
        limiter.consume(third, "ai", limit=1, window_seconds=60)
    assert failure.value.retry_after == 40
    assert limiter.consume(first, "ai", limit=1, window_seconds=60) == 40
    clock.now = 60
    assert limiter.consume(third, "ai", limit=1, window_seconds=60) == 0
    assert limiter.consume(second, "ai", limit=1, window_seconds=60) == 10
    clock.now = 70
    assert limiter.consume(second, "ai", limit=1, window_seconds=60) == 0
    assert limiter.consume(third, "ai", limit=1, window_seconds=60) == 50


def test_application_counters_are_independent():
    owner = uuid4()
    first = RequestRateLimiter(clock=Clock())
    second = RequestRateLimiter(clock=Clock())
    assert first.consume(owner, "ai", limit=1, window_seconds=60) == 0
    assert first.consume(owner, "ai", limit=1, window_seconds=60) == 60
    assert second.consume(owner, "ai", limit=1, window_seconds=60) == 0
