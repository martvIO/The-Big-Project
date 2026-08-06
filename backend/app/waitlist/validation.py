"""F22's one bound and one error class. The phone rule is IMPORTED at the call
site (`normalize_israeli_mobile` is both the check and the conversion, the
queue's own note) — F22 invents no phone rule and no name rule, and has no name
to rule on.
"""

import datetime

from app.booking.validation import SLOT_WINDOW_MAX_DAYS
from app.errors import DomainValidationError
from app.storefront.validation import Clock, today_jerusalem


class WaitlistThrottledError(Exception):
    """One of the two join budgets is spent; main.py maps it to the shared 429
    TOO_MANY_ATTEMPTS body.

    Its own class like the four throttles before it (unrelated budgets, keys
    and operational meanings); the F21 reparenting note on
    StorefrontThrottledError covers this one too.
    """


def validate_waitlist_day(day: datetime.date, *, clock: Clock | None = None) -> None:
    """D2 step 1: `today <= day <= today + SLOT_WINDOW_MAX_DAYS`, Jerusalem
    calendar on both sides.

    The ceiling is the SLOT window's own bound — an entry for a day the picker
    cannot offer is an entry no cancellation can ever free a slot for. The
    floor refuses the past outright: yesterday's full day is not coming back.
    Both refusals are the shipped VALIDATION_ERROR 400; the server deliberately
    does NOT check the day is actually full (D2 — a fullness check is a TOCTOU
    race against concurrent cancellations, and the CTA gates the honest path).
    """
    today = today_jerusalem(clock)
    if not today <= day <= today + datetime.timedelta(days=SLOT_WINDOW_MAX_DAYS):
        raise DomainValidationError("day is outside the joinable window")
