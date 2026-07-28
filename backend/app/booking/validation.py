"""Named bounds and the Israeli-week conversion for the booking grid.

Deliberately NOT env-tunable, per F8's rule that `Settings` carries deployment
identity and never product policy. The boutique wall clock itself lives once in
`app/storefront/validation.py` (`BOUTIQUE_TIMEZONE`) and is imported, not
restated — two zone constants is one zone constant too many.
"""

import datetime

# The boutique's scheduling granularity. 15 doubles the picker for no pilot
# benefit; 60 loses the half-hour starts owners actually use. Per-tenant
# tunability is a column plus a settings row, deferred until a boutique asks.
SLOT_INTERVAL_MINUTES = 30

# Matches the availability_rules.capacity DB default. Used only when an
# exception opens a date that has no weekly rule to inherit staffing from.
DEFAULT_SLOT_CAPACITY = 1

# Two weeks is what a picker shows before "next".
SLOT_WINDOW_DEFAULT_DAYS = 14

# One anonymous request must not materialize years of grid. 60 days of 30-minute
# steps over a 9-hour day is ~1000 slots — a bounded response.
SLOT_WINDOW_MAX_DAYS = 60


def jerusalem_day_index(date: datetime.date) -> int:
    """0=Sunday … 6=Saturday — the Israeli week, and the encoding
    `availability_rules.day_of_week` uses.

    Python's `date.weekday()` is 0=Monday, so the shift lives here once.
    `packages/ui/src/lib/hours.ts` maps the same seven names to the same seven
    indices for rendering; `test_frontend_constant_parity.py` pins them together.
    """
    return (date.weekday() + 1) % 7
