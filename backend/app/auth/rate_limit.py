from collections.abc import Callable


class FixedWindowRateLimiter:
    """Per-instance fixed-window limiter. Sufficient for a single-instance pilot;
    distributed limiting (Redis) is the Feature 21 hardening gate. The clock is
    injectable so windows are testable without real time.

    The auth callers record only failed attempts, so a shared client IP or a
    legitimate owner can't be throttled by other users' activity. is_blocked is a
    read-only pre-check.

    The storefront caller records on the SUCCESS path — it meters reads, not
    failures — which changes the key space from "principals who failed" to "every
    anonymous visitor IP", the first unbounded one. Hence the sweep below: expired
    buckets are dropped once the map outgrows its high-water mark, so memory
    tracks the live window rather than every IP seen since boot. Amortised, not
    per-write: the mark then floats to 2x the surviving set so a busy instance
    does not sweep on every insert. A size/TTL-capped shared store still lands
    with the distributed limiter in Feature 21."""

    _SWEEP_FLOOR = 1024

    def __init__(
        self, max_attempts: int, window_seconds: float, clock: Callable[[], float]
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._buckets: dict[str, tuple[float, int]] = {}
        self._sweep_at = self._SWEEP_FLOOR

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
        if len(self._buckets) > self._sweep_at:
            self._sweep()

    def _sweep(self) -> None:
        now = self._clock()
        self._buckets = {
            key: bucket for key, bucket in self._buckets.items() if now - bucket[0] < self._window
        }
        self._sweep_at = max(self._SWEEP_FLOOR, len(self._buckets) * 2)

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)
