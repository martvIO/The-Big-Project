from app.auth.rate_limit import FixedWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _limiter(clock: FakeClock) -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=3, window_seconds=900, clock=clock)


def test_blocks_only_after_max_failures() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        assert limiter.is_blocked("k") is False
        limiter.record_failure("k")
    assert limiter.is_blocked("k") is True


def test_reads_do_not_increment() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(10):
        assert limiter.is_blocked("k") is False  # never recorded → never blocks


def test_window_expiry_resets_the_counter() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("k")
    assert limiter.is_blocked("k") is True
    clock.advance(901)
    assert limiter.is_blocked("k") is False


def test_keys_are_independent() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("a")
    assert limiter.is_blocked("a") is True
    assert limiter.is_blocked("b") is False


def test_reset_clears_a_key() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.record_failure("k")
    limiter.reset("k")
    assert limiter.is_blocked("k") is False


def test_the_key_space_stays_bounded_across_many_expired_windows() -> None:
    """The auth callers record only failures, so their key space is bounded by
    principals who fail. The storefront caller records on the SUCCESS path — it
    meters reads — which makes the keys "every anonymous visitor IP ever seen".
    Without a sweep that dict grows monotonically until process restart.

    The sweep is amortised, not immediate: it fires when the map outgrows its
    high-water mark, and the mark then floats to 2x the surviving set so a busy
    instance does not sweep on every insert. So the property to assert is that
    memory tracks the LIVE window, not that any single write collects.
    """
    clock = FakeClock()
    limiter = _limiter(clock)
    floor = FixedWindowRateLimiter._SWEEP_FLOOR
    rounds = 10

    for round_index in range(rounds):
        for i in range(floor):
            limiter.record_failure(f"r{round_index}-ip{i}")
        clock.advance(10_000)  # the whole window dies before the next round

    # Ten rounds wrote floor*10 distinct keys; without sweeping every one would
    # still be resident.
    assert len(limiter._buckets) < floor * rounds
    assert len(limiter._buckets) <= floor + 1


def test_the_sweep_never_drops_a_live_window() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    floor = FixedWindowRateLimiter._SWEEP_FLOOR

    # Same instant throughout, so a sweep must be a no-op rather than a reset —
    # dropping a live bucket would hand a blocked client a fresh allowance.
    for i in range(floor + 2):
        limiter.record_failure(f"ip-{i}")
    assert len(limiter._buckets) == floor + 2

    for i in range(floor + 2):
        assert f"ip-{i}" in limiter._buckets
