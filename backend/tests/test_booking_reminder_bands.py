"""D3's reminder timing, the whole decision table, plus both Israeli DST edges.

Pure arithmetic on injected instants — the house `WallClock` pattern, no
freezegun, no sleeps, no database. Interview pre-decided #6 keeps the bands
exactly as Gate 1 approved them; Interview Q4 changed only what the immediate
band's body SAYS (see test_booking_comms_templates.py), never when it fires.
"""

import datetime

from app.booking.comms import (
    REMINDER_LEAD_SECONDS,
    REMINDER_SUPPRESS_UNDER_SECONDS,
    reminder_send_after,
)
from app.storefront.validation import BOUTIQUE_TIMEZONE

NOW = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.UTC)


def _at(**delta: float) -> datetime.datetime:
    return NOW + datetime.timedelta(**delta)


def _local(instant: datetime.datetime) -> datetime.datetime:
    return instant.astimezone(BOUTIQUE_TIMEZONE)


# --- the three bands -------------------------------------------------------


def test_a_booking_a_week_out_is_reminded_24h_before() -> None:
    starts_at = _at(days=7)
    assert reminder_send_after(starts_at=starts_at, now=NOW) == starts_at - datetime.timedelta(
        seconds=REMINDER_LEAD_SECONDS
    )


def test_a_booking_inside_24h_is_reminded_immediately() -> None:
    """She still gets the confirm-attendance ask — which is the whole no-show
    defence — so the reminder is not skipped, only moved to now (Interview Q4:
    the second text within minutes is accepted for exactly that reason)."""
    assert reminder_send_after(starts_at=_at(hours=6), now=NOW) == NOW


def test_a_booking_inside_2h_gets_no_reminder_row_at_all() -> None:
    """The confirmation SMS is seconds old; a second message inside two hours is
    noise, not service."""
    assert reminder_send_after(starts_at=_at(minutes=90), now=NOW) is None


# --- the boundaries, to the second ----------------------------------------


def test_exactly_24h_out_takes_the_scheduled_band() -> None:
    starts_at = _at(seconds=REMINDER_LEAD_SECONDS)
    # ... which computes to `now`, and that is correct rather than a coincidence:
    # 24h before an appointment exactly 24h away IS this instant.
    assert reminder_send_after(starts_at=starts_at, now=NOW) == NOW


def test_one_second_inside_24h_takes_the_immediate_band() -> None:
    assert reminder_send_after(starts_at=_at(seconds=REMINDER_LEAD_SECONDS - 1), now=NOW) == NOW


def test_exactly_2h_out_still_gets_a_reminder() -> None:
    """The suppression is `lead < 2h`, so the 2h mark itself is inside the
    immediate band. Pinned because an off-by-one here silently drops the
    confirm-attendance ask for a whole band of bookings."""
    at_the_mark = _at(seconds=REMINDER_SUPPRESS_UNDER_SECONDS)
    assert reminder_send_after(starts_at=at_the_mark, now=NOW) == NOW


def test_one_second_inside_2h_is_suppressed() -> None:
    assert (
        reminder_send_after(starts_at=_at(seconds=REMINDER_SUPPRESS_UNDER_SECONDS - 1), now=NOW)
        is None
    )


def test_an_appointment_already_in_the_past_is_suppressed() -> None:
    """Reachable through the reschedule upsert and the backfill, not through a
    fresh claim (create_booking rejects a past instant first). Must not compute a
    send_after in the past and hand the poller a row it would fire at once."""
    assert reminder_send_after(starts_at=_at(hours=-1), now=NOW) is None


# --- DST: the reminder is 24h of REAL TIME, not 24 wall-clock hours -------


def test_spring_forward_keeps_the_lead_at_exactly_24_hours_of_real_time() -> None:
    """Israel springs forward at 02:00 on the Friday before the last Sunday of
    March — 27 March 2026. An appointment at 10:00 local on that Friday is
    reminded at 09:00 local on the Thursday: the lead is 86 400 real seconds, and
    the local wall clock therefore shifts by one hour.

    That is the correct behaviour and the reason this arithmetic stays on UTC
    instants. Naive local-date arithmetic would produce 10:00 local, which is 25
    real hours out — and the body renders from `starts_at`, so a reminder that
    fires early or late still states the true appointment time either way.
    """
    starts_at = datetime.datetime(2026, 3, 27, 7, 0, tzinfo=datetime.UTC)  # 10:00 IDT
    now = datetime.datetime(2026, 3, 20, 9, 0, tzinfo=datetime.UTC)
    send_after = reminder_send_after(starts_at=starts_at, now=now)

    assert send_after == datetime.datetime(2026, 3, 26, 7, 0, tzinfo=datetime.UTC)
    assert (starts_at - send_after).total_seconds() == REMINDER_LEAD_SECONDS
    assert _local(starts_at).hour == 10
    assert _local(send_after).hour == 9  # IST, one hour behind IDT


def test_fall_back_keeps_the_lead_at_exactly_24_hours_of_real_time() -> None:
    """The mirror case. Israel falls back at 02:00 on the last Sunday of October
    — 25 October 2026 — so a 09:00-local Sunday appointment is reminded at 10:00
    local on the Saturday."""
    starts_at = datetime.datetime(2026, 10, 25, 7, 0, tzinfo=datetime.UTC)  # 09:00 IST
    now = datetime.datetime(2026, 10, 18, 9, 0, tzinfo=datetime.UTC)
    send_after = reminder_send_after(starts_at=starts_at, now=now)

    assert send_after == datetime.datetime(2026, 10, 24, 7, 0, tzinfo=datetime.UTC)
    assert (starts_at - send_after).total_seconds() == REMINDER_LEAD_SECONDS
    assert _local(starts_at).hour == 9
    assert _local(send_after).hour == 10  # IDT, one hour ahead of IST


def test_the_dst_shift_does_not_move_a_booking_between_bands() -> None:
    """A booking made 25 real hours before a spring-forward appointment is 24
    LOCAL hours out. It must still take the scheduled band on real time, not be
    mis-sorted into the immediate one."""
    starts_at = datetime.datetime(2026, 3, 27, 7, 0, tzinfo=datetime.UTC)
    now = starts_at - datetime.timedelta(hours=25)
    assert reminder_send_after(starts_at=starts_at, now=now) == starts_at - datetime.timedelta(
        seconds=REMINDER_LEAD_SECONDS
    )


# --- the constants themselves ---------------------------------------------


def test_the_named_constants_are_the_spec_values() -> None:
    assert REMINDER_LEAD_SECONDS == 86_400
    assert REMINDER_SUPPRESS_UNDER_SECONDS == 7_200
