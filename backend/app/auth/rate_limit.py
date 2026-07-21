from collections.abc import Callable


class FixedWindowRateLimiter:
    """Per-instance fixed-window limiter. Sufficient for a single-instance pilot;
    distributed limiting (Redis) is the Feature 21 hardening gate. The clock is
    injectable so windows are testable without real time.

    Only failed attempts are recorded (via record_failure); successes never count,
    so a shared client IP or a legitimate owner can't be throttled by other users'
    activity. is_blocked is a read-only pre-check.

    Buckets are not evicted beyond in-place window rollover — acceptable at pilot
    scale (the number of distinct keys is bounded by real tenants/emails/IPs);
    a size/TTL-capped store lands with the distributed limiter in Feature 21."""

    def __init__(
        self, max_attempts: int, window_seconds: float, clock: Callable[[], float]
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._buckets: dict[str, tuple[float, int]] = {}

    def _current_count(self, key: str) -> tuple[float, int]:
        now = self._clock()
        window_start, count = self._buckets.get(key, (now, 0))
        if now - window_start >= self._window:
            return now, 0
        return window_start, count

    def is_blocked(self, key: str) -> bool:
        _, count = self._current_count(key)
        return count >= self._max

    def record_failure(self, key: str) -> None:
        window_start, count = self._current_count(key)
        self._buckets[key] = (window_start, count + 1)

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)
