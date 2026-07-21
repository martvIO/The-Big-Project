from collections.abc import Callable


class FixedWindowRateLimiter:
    """Per-instance fixed-window limiter. Sufficient for a single-instance pilot;
    distributed limiting (Redis) is the Feature 21 hardening gate. The clock is
    injectable so windows are testable without real time."""

    def __init__(
        self, max_attempts: int, window_seconds: float, clock: Callable[[], float]
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._buckets: dict[str, tuple[float, int]] = {}

    def check_and_increment(self, key: str) -> bool:
        """Record an attempt; return False once the window's limit is exceeded."""
        now = self._clock()
        window_start, count = self._buckets.get(key, (now, 0))
        if now - window_start >= self._window:
            window_start, count = now, 0
        if count >= self._max:
            return False
        self._buckets[key] = (window_start, count + 1)
        return True

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)
