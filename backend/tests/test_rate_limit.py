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


def test_allows_up_to_the_limit_then_blocks() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    assert limiter.check_and_increment("k") is True
    assert limiter.check_and_increment("k") is True
    assert limiter.check_and_increment("k") is True
    assert limiter.check_and_increment("k") is False


def test_window_expiry_resets_the_counter() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.check_and_increment("k")
    assert limiter.check_and_increment("k") is False
    clock.advance(901)
    assert limiter.check_and_increment("k") is True


def test_keys_are_independent() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.check_and_increment("a")
    assert limiter.check_and_increment("a") is False
    assert limiter.check_and_increment("b") is True


def test_reset_clears_a_key() -> None:
    clock = FakeClock()
    limiter = _limiter(clock)
    for _ in range(3):
        limiter.check_and_increment("k")
    limiter.reset("k")
    assert limiter.check_and_increment("k") is True
