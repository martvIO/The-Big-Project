"""Named bounds, request validation and the Israeli-week conversion for booking.

Deliberately NOT env-tunable, per F8's rule that `Settings` carries deployment
identity and never product policy. The boutique wall clock itself lives once in
`app/storefront/validation.py` (`BOUTIQUE_TIMEZONE`) and is imported, not
restated — two zone constants is one zone constant too many.
"""

import datetime
import re
import uuid

from app.errors import DomainValidationError


class BookingValidationError(DomainValidationError):
    """Domain-rule violation on a booking write; the platform handler maps it
    to the house-shape 400."""


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

# A human name, not an essay; deliberately tighter than the catalog's 200-char
# dress names because this string reaches SMS templates (F16) where length is
# billable.
MAX_CUSTOMER_NAME_LENGTH = 80

# "מגיעה עם אמא ושתי אחיות" — a paragraph, not a document. Free customer text
# that reaches the owner's console: bounded here, rendered as text there, never
# HTML (spec risk #3).
MAX_BOOKING_NOTES_LENGTH = 500

# One Jerusalem day of the owner console's booking list. A pilot boutique runs
# tens of appointments a day across every seat, so 50 is the whole day in one
# page and the screen ships no paging controls at all.
BOOKING_LIST_DEFAULT_LIMIT = 50

# The `?limit=` ceiling, enforced as Query(ge=1, le=…) at the owner router. 4x
# the default: enough headroom for a boutique that grows past one page a day,
# and small enough that one request can never materialize a month.
BOOKING_LIST_MAX_LIMIT = 200

# Matches MAX_RULE_CAPACITY exactly (not the usual 10x absurdity ceiling):
# a seat index above capacity can never be claimed, so capacity itself is
# already the bound and 0008's CHECK pins the same number.
MAX_SEAT_INDEX = 1000

# These are the FIRST customer-authored strings in the product — every earlier
# free-text write sits behind manage auth. Postgres rejects U+0000 in `text`
# outright, and an uncaught asyncpg DataError on an anonymous route is a 500,
# so the NUL is a availability bug before it is anything else. The rest of the
# C0 set is barred from a name for a different reason: a line break in a value
# that F16 will template into an SMS is header-injection material. `notes` is
# a paragraph, so it keeps newlines and tabs.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_CONTROL_CHARS_EXCEPT_WS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate_booking_request(
    *,
    name: str,
    notes: str | None,
    dress_id: uuid.UUID | None,
    dress_size: str | None,
) -> None:
    """Pure shape checks only. Whether the dress exists, the size is one of its
    active variants, or the slot is real are SERVICE questions (404/409, and
    they need the database); everything here is answerable from the request
    alone and maps to 400."""
    if not name.strip():
        raise BookingValidationError("name must not be blank")
    if len(name) > MAX_CUSTOMER_NAME_LENGTH:
        raise BookingValidationError("name is too long")
    if _CONTROL_CHARS.search(name):
        raise BookingValidationError("name contains invalid characters")
    if notes is not None:
        if len(notes) > MAX_BOOKING_NOTES_LENGTH:
            raise BookingValidationError("notes is too long")
        if _CONTROL_CHARS_EXCEPT_WS.search(notes):
            raise BookingValidationError("notes contains invalid characters")
    # The two-path model, enforced at the boundary: item-based carries BOTH
    # dress_id and dress_size, generic carries NEITHER. A size without a dress
    # is noise; a dress without a size books unfittable stock.
    if dress_id is not None and (dress_size is None or not dress_size.strip()):
        raise BookingValidationError("dress_size is required when dress_id is given")
    if dress_id is None and dress_size is not None:
        raise BookingValidationError("dress_size requires dress_id")


def jerusalem_day_index(date: datetime.date) -> int:
    """0=Sunday … 6=Saturday — the Israeli week, and the encoding
    `availability_rules.day_of_week` uses.

    Python's `date.weekday()` is 0=Monday, so the shift lives here once.
    `packages/ui/src/lib/hours.ts` maps the same seven names to the same seven
    indices for rendering; `test_frontend_constant_parity.py` pins them together.
    """
    return (date.weekday() + 1) % 7
