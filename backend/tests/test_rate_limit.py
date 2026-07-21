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
