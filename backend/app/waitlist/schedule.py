"""The offer clock, as two pure functions.

Pure by construction — no session, no `Settings`, no `datetime.now()` — for the
reason `booking/slots.py` gives about itself: the arithmetic that decides when a
bride's window closes is the part that must be readable, and a function taking a
clock as an argument is the only shape a DST test can pin.

Spec D3 in one sentence: **quiet hours gate the CASCADE, never the WINDOW.** No
offer is issued inside the quiet block; an offer already issued keeps its full
window even if that window ends inside it. Extending a window across the quiet
block would hold a live slot hostage for one bride for ~13 hours, which is the
opposite of what the feature is for.
"""

import datetime

from app.storefront.validation import BOUTIQUE_TIMEZONE


def in_quiet_hours(now: datetime.datetime, *, start_hour: int, end_hour: int) -> bool:
    """Is `now` inside `[start_hour, end_hour)` on the boutique's wall clock?

    The block WRAPS midnight at the shipped default (21 -> 8), so the comparison
    is a disjunction, not a range. Written to handle the non-wrapping case too
    (`start < end`, e.g. a boutique that only wanted a lunch gap) because getting
    that wrong silently inverts the gate rather than erroring.

    ⚠ The hour is read off the JERUSALEM wall clock, which is why this takes an
    aware instant and converts. Comparing `now.hour` on a UTC instant would put
    the quiet block three hours early in summer and two in winter — and it would
    look right in every test written at noon.
    """
    hour = now.astimezone(BOUTIQUE_TIMEZONE).hour
    if start_hour == end_hour:
        # Degenerate: an empty block, not a 24-hour one. The direction that fails
        # is "silently stopped offering forever", so it is the one refused.
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def offer_expiry(
    now: datetime.datetime,
    slot_starts_at: datetime.datetime,
    *,
    window: datetime.timedelta,
    min_lead: datetime.timedelta,
) -> datetime.datetime | None:
    """`min(now + window, slot_starts_at - min_lead)`, or None if that is not in
    the future.

    Two independent ceilings and the earlier one wins:

    * `now + window` is the ordinary 2-hour deadline (#12).
    * `slot_starts_at - min_lead` is #15's truncation, and it is what stops an
      offer expiring after the appointment has already begun. A slot 2h30m out at
      20:00 gets a window to 20:30, not to 22:00.

    None means "do not offer this at all" — the slot is inside the lead, so the
    window would be zero or negative. The cascade drops the pair silently; it is
    the steady state near closing time, not an error.

    ⚠ ARITHMETIC ON INSTANTS, not on wall clock. Adding two hours across a DST
    transition must add two REAL hours, and `datetime + timedelta` on an aware
    UTC-normalised instant does exactly that, while the same addition on a naive
    Jerusalem wall clock would land on a nonexistent 03:00 in spring and an
    ambiguous one in autumn. `in_quiet_hours` above is the only wall-clock
    question in this module, and it asks it by converting rather than by
    computing.
    """
    expires_at = min(now + window, slot_starts_at - min_lead)
    return expires_at if expires_at > now else None
