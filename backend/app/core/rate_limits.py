"""Bounded, process-local request counters for one API worker."""

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import UUID

RequestGroup = Literal["ai", "upload"]


@dataclass
class RequestWindow:
    expires_at: float
    count: int


class RateLimitCapacityError(Exception):
    """New counters cannot be tracked without discarding an active allowance."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__("Request limit counters are full")


class RequestRateLimiter:
    def __init__(
        self, *, max_buckets: int = 10000, clock: Callable[[], float] = monotonic
    ):
        self._max_buckets = max_buckets
        self._clock = clock
        self._windows: dict[tuple[UUID, RequestGroup], RequestWindow] = {}
        self._next_cleanup = 0.0
        self._lock = Lock()

    def consume(
        self, user_id: UUID, group: RequestGroup, *, limit: int, window_seconds: int
    ) -> int:
        """Count an allowed attempt; return seconds to wait when its quota is used."""
        with self._lock:
            now = self._clock()
            key = (user_id, group)
            if now >= self._next_cleanup or (
                key not in self._windows and len(self._windows) >= self._max_buckets
            ):
                self._windows = {
                    key: window
                    for key, window in self._windows.items()
                    if window.expires_at > now
                }
                self._next_cleanup = now + window_seconds

            window = self._windows.get(key)
            if window is None or window.expires_at <= now:
                if window is None and len(self._windows) >= self._max_buckets:
                    retry_after = ceil(
                        min(w.expires_at for w in self._windows.values()) - now
                    )
                    raise RateLimitCapacityError(max(1, retry_after))
                self._windows[key] = RequestWindow(now + window_seconds, 1)
                return 0

            if window.count >= limit:
                return max(1, ceil(window.expires_at - now))
            window.count += 1
            return 0
