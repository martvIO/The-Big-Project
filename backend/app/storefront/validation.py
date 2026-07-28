"""Named bounds and the boutique wall clock for the public storefront.

Nothing here is mirrored to the frontend — no storefront constant is enforced
client-side, so `test_frontend_constant_parity.py` gains no rows. These are
deliberately NOT env-tunable, per F8's rule that `Settings` carries deployment
identity and never product policy. (The read-throttle bounds ARE `Settings`
fields, following the `media_presign_*` and `login_*` precedent, so they can be
tightened during an incident without a deploy.)
"""

import datetime
from collections.abc import Callable
from zoneinfo import ZoneInfo

# Same as DRESS_LIST_DEFAULT_LIMIT: the grid is 2/3/4-col, so 24 fills 6/8/12
# rows and the worst case is 24 unprocessed covers.
STOREFRONT_LIST_DEFAULT_LIMIT = 24

# EQUAL to the default, unlike manage's 100 — and that is the point.
#
# The UI never asks for more, and every extra unit is a denial-of-wallet
# multiplier: one unauthenticated call mints one fresh 900-second redeemable URL
# per item, worth up to the 10 MiB upload cap, redeemable by any third party.
# Symmetry with the AUTHENTICATED manage list is not an argument for a public
# endpoint. Raise this in the feature that ships a UI which asks for more.
STOREFRONT_LIST_MAX_LIMIT = 24

# One editorial card's worth. A boutique that has recorded every holiday for
# three years must not turn /about into a calendar.
UPCOMING_EXCEPTIONS_LIMIT = 12

# The boutique's own wall clock. Hours, exception dates and "closed today" are
# local-calendar facts, so filtering them against a UTC date would drop or keep
# a row for the two hours either side of midnight in Israel. The frontend binds
# "today" to the same IANA zone; the two must agree or an exception dated today
# vanishes from /about for the hours the calendars differ.
BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")

Clock = Callable[[], datetime.datetime]


class StorefrontThrottledError(Exception):
    """The per-tenant anonymous read budget is spent; main.py maps it to a 429
    carrying the shared TOO_MANY_ATTEMPTS body.

    Its own class rather than a reuse of auth's RateLimitedError: those two
    surfaces have unrelated budgets, keys and operational meanings, and
    importing a LOGIN error into the public read path to dodge a three-line
    handler would be a semantic lie no test catches. Reparenting all four
    throttle errors onto one base is a behaviour-neutral cleanup owned by F21.
    """


def today_jerusalem(clock: Clock | None = None) -> datetime.date:
    """The boutique's current calendar date.

    `clock` is injectable so the date cutoff is unit-testable with no I/O and no
    dependence on the machine's TZ — the CI runner, a developer's laptop and
    Israel are three different calendar days for part of every day.
    """
    now = clock() if clock is not None else datetime.datetime.now(BOUTIQUE_TIMEZONE)
    return now.astimezone(BOUTIQUE_TIMEZONE).date()
