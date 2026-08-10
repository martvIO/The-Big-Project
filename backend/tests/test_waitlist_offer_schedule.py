"""The offer clock against a frozen clock — spec D3's unit list, including the
DST cases Risk 5 refuses to let be an assumption.

NOT db-marked and deliberately so: these are two pure functions, and the whole
point of keeping them pure is that the arithmetic deciding when a bride's window
closes can be checked without a container.
"""

import datetime

from app.core.config import Settings
from app.storefront.validation import BOUTIQUE_TIMEZONE
from app.waitlist.schedule import in_quiet_hours, offer_expiry

QUIET_START = 21
QUIET_END = 8
WINDOW = datetime.timedelta(hours=2)
MIN_LEAD = datetime.timedelta(hours=2)


def _jerusalem(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime.datetime:
    """A Jerusalem WALL-CLOCK moment as the UTC instant it really is. Every case
    below is stated in the zone the rule is written in, then converted — which is
    what makes the DST cases mean anything."""
    return datetime.datetime(year, month, day, hour, minute, tzinfo=BOUTIQUE_TIMEZONE).astimezone(
        datetime.UTC
    )


# --- the quiet-hours gate ----------------------------------------------------


def test_the_quiet_block_wraps_midnight_and_its_edges_are_half_open() -> None:
    """[21:00, 08:00). 20:59 still offers, 21:00 does not, 07:59 does not,
    08:00 does. The half-open edge matters: a closed upper bound would leave a
    one-minute hole at 08:00 that nothing covers."""
    cases = {
        _jerusalem(2026, 8, 19, 20, 59): False,
        _jerusalem(2026, 8, 19, 21, 0): True,
        _jerusalem(2026, 8, 19, 21, 30): True,
        _jerusalem(2026, 8, 20, 3, 0): True,
        _jerusalem(2026, 8, 20, 7, 59): True,
        _jerusalem(2026, 8, 20, 8, 0): False,
        _jerusalem(2026, 8, 20, 12, 0): False,
    }
    for moment, expected in cases.items():
        assert in_quiet_hours(moment, start_hour=QUIET_START, end_hour=QUIET_END) is expected, (
            moment.astimezone(BOUTIQUE_TIMEZONE)
        )


def test_the_gate_reads_the_jerusalem_wall_clock_not_the_utc_hour() -> None:
    """The bug this exists to catch: 22:00 Jerusalem in August is 19:00 UTC, so a
    gate comparing `now.hour` on the UTC instant would answer "not quiet" for the
    first three hours of every night — and would look right in any test written
    at noon."""
    quiet_local = _jerusalem(2026, 8, 19, 22, 0)
    assert quiet_local.astimezone(datetime.UTC).hour == 19
    assert in_quiet_hours(quiet_local, start_hour=QUIET_START, end_hour=QUIET_END)


def test_the_gate_survives_both_jerusalem_dst_transitions() -> None:
    """Risk 5, and it is a test rather than an assumption.

    Spring forward 2026: 02:00 -> 03:00 on Friday 27 March, so 03:00 IS the
    first instant after the jump and it must still read as quiet — the 03:00
    case spec Risk 5 names by hand.

    Autumn back 2026: 02:00 -> 01:00 on Sunday 25 October, so it is **01:00-02:00
    that happens twice**, not 02:00-03:00 (the obvious guess, and the one this
    test was first written with). BOTH readings are inside the block, so the
    ambiguity cannot change the answer — which is the property that makes the
    gate safe here rather than merely lucky.
    """
    spring = _jerusalem(2026, 3, 27, 3, 0)
    assert in_quiet_hours(spring, start_hour=QUIET_START, end_hour=QUIET_END)

    autumn_local = datetime.datetime(2026, 10, 25, 1, 30, tzinfo=BOUTIQUE_TIMEZONE)
    for fold in (0, 1):
        moment = autumn_local.replace(fold=fold).astimezone(datetime.UTC)
        assert in_quiet_hours(moment, start_hour=QUIET_START, end_hour=QUIET_END), fold
    # The two folds really are two different instants — otherwise the loop above
    # would be asserting one thing twice.
    assert autumn_local.replace(fold=0).astimezone(datetime.UTC) != autumn_local.replace(
        fold=1
    ).astimezone(datetime.UTC)


def test_a_non_wrapping_block_and_a_degenerate_one_both_behave() -> None:
    """A boutique that set 13->15 gets a lunch gap, not an inverted gate. Equal
    hours read as NO quiet block at all — the direction that fails is "silently
    stopped offering forever", so that is the one refused."""
    afternoon = _jerusalem(2026, 8, 19, 14, 0)
    assert in_quiet_hours(afternoon, start_hour=13, end_hour=15)
    assert not in_quiet_hours(_jerusalem(2026, 8, 19, 16, 0), start_hour=13, end_hour=15)
    assert not in_quiet_hours(afternoon, start_hour=13, end_hour=13)


# --- the expiry clamp --------------------------------------------------------


def test_the_ordinary_window_is_now_plus_the_setting() -> None:
    now = _jerusalem(2026, 8, 19, 10, 0)
    slot = _jerusalem(2026, 8, 21, 14, 0)
    assert offer_expiry(now, slot, window=WINDOW, min_lead=MIN_LEAD) == now + WINDOW


def test_a_slot_inside_two_windows_truncates_at_slot_minus_lead() -> None:
    """#15's worked case: a slot 2h30m out at 20:00 expires at 20:30, not 22:00,
    so an offer can never outlive the appointment it names."""
    now = _jerusalem(2026, 8, 19, 20, 0)
    slot = _jerusalem(2026, 8, 19, 22, 30)
    assert offer_expiry(now, slot, window=WINDOW, min_lead=MIN_LEAD) == _jerusalem(
        2026, 8, 19, 20, 30
    )


def test_a_slot_at_exactly_the_lead_or_closer_is_not_offerable() -> None:
    """`expires_at <= now` -> None. At exactly the lead the window is zero, which
    is an offer nobody could ever accept; inside it the window is negative."""
    now = _jerusalem(2026, 8, 19, 20, 0)
    assert offer_expiry(now, now + MIN_LEAD, window=WINDOW, min_lead=MIN_LEAD) is None
    assert (
        offer_expiry(now, now + datetime.timedelta(minutes=30), window=WINDOW, min_lead=MIN_LEAD)
        is None
    )
    assert (
        offer_expiry(now, now - datetime.timedelta(hours=1), window=WINDOW, min_lead=MIN_LEAD)
        is None
    )


def test_a_deadline_landing_inside_quiet_hours_is_kept_not_extended() -> None:
    """D3's second worked case, and the one most likely to be "fixed" by a later
    reader: an offer ISSUED at 20:59 expires at 22:59, inside the quiet block,
    and that is correct. She was texted while awake, the window is hers, and at
    22:59 the slot returns to the pool and stays directly bookable all night.

    This function does not know about quiet hours at all — that is the design,
    stated as a test so the coupling is not added back."""
    now = _jerusalem(2026, 8, 19, 20, 59)
    slot = _jerusalem(2026, 8, 21, 11, 0)
    deadline = offer_expiry(now, slot, window=WINDOW, min_lead=MIN_LEAD)
    assert deadline == _jerusalem(2026, 8, 19, 22, 59)
    assert deadline is not None
    assert in_quiet_hours(deadline, start_hour=QUIET_START, end_hour=QUIET_END)


def test_the_window_adds_real_hours_across_the_spring_forward() -> None:
    """01:30 + 2h on 27 March 2026 is 04:30, NOT 03:30, because 02:00-03:00 does
    not exist that night. Instant arithmetic gets this right for free —
    wall-clock arithmetic would land on the nonexistent 03:00 hour and silently
    normalise it, which is exactly the case spec Risk 5 refuses to assume."""
    late = _jerusalem(2026, 3, 27, 1, 30)
    slot = _jerusalem(2026, 3, 29, 11, 0)
    deadline = offer_expiry(late, slot, window=WINDOW, min_lead=MIN_LEAD)
    assert deadline == late + WINDOW
    assert deadline is not None
    assert deadline.astimezone(BOUTIQUE_TIMEZONE).hour == 4
    assert deadline.astimezone(BOUTIQUE_TIMEZONE).minute == 30


def test_the_window_adds_real_hours_across_the_fall_back() -> None:
    """The mirror, and the one that reads wrong at a glance: 01:30 (first pass,
    IDT) + 2h on 25 October 2026 lands at 02:30, which LOOKS like one hour later.
    It is two real hours — 01:00-02:00 runs twice that night. A deadline stated
    as an instant is unambiguous through it; a naive local one would be an hour
    off for every offer issued in that window, in the direction that expires a
    bride's window early."""
    late = datetime.datetime(2026, 10, 25, 1, 30, fold=0, tzinfo=BOUTIQUE_TIMEZONE).astimezone(
        datetime.UTC
    )
    slot = _jerusalem(2026, 10, 27, 11, 0)
    deadline = offer_expiry(late, slot, window=WINDOW, min_lead=MIN_LEAD)
    assert deadline == late + WINDOW
    assert deadline is not None
    local = deadline.astimezone(BOUTIQUE_TIMEZONE)
    assert (local.hour, local.minute) == (2, 30)
    # ONE wall-clock hour on the face of it, TWO real hours in the arithmetic —
    # which is the entire claim, and the reason the naive spelling is a bug.
    naive_gap = local.replace(tzinfo=None) - late.astimezone(BOUTIQUE_TIMEZONE).replace(tzinfo=None)
    assert naive_gap == datetime.timedelta(hours=1)
    assert deadline - late == WINDOW


def test_the_shipped_defaults_cannot_produce_a_deadline_past_midnight() -> None:
    """The guarantee design §1 leans on for the bare `HH:MM` in the SMS, checked
    against the SETTINGS rather than against a literal — so raising the window in
    config.py reds this test instead of silently making the body ambiguous
    (design F-O1)."""
    settings = Settings()
    latest_issue_hour = settings.waitlist_quiet_start_hour - 1
    now = _jerusalem(2026, 8, 19, latest_issue_hour, 59)
    slot = _jerusalem(2026, 8, 21, 11, 0)
    deadline = offer_expiry(
        now,
        slot,
        window=datetime.timedelta(seconds=settings.waitlist_offer_window_seconds),
        min_lead=datetime.timedelta(seconds=settings.waitlist_offer_min_lead_seconds),
    )
    assert deadline is not None
    assert deadline.astimezone(BOUTIQUE_TIMEZONE).date() == now.astimezone(BOUTIQUE_TIMEZONE).date()
