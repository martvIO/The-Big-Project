"""The owner console's booking surface: the day list, the detail, the four
transitions, reschedule, phone correction and the resend.

Session-authed, CSRF-fenced and `no-store`, so unlike the tokenized manage page
this one may carry the customer's phone and her notes — the operational point of
the screen is that the owner can call the bride and read what she wrote (D18).
"""

# STOREFRONT/CATALOG's MAX_LIST_OFFSET, restated for the same reason it exists
# there: `offset` reaches the driver as `OFFSET $n::BIGINT` (SQLAlchemy's
# asyncpg dialect casts it explicitly), so an unbounded Python int never becomes
# a 400 — it dies in asyncpg's `int8_encode` as a DataError with no handler
# above it, i.e. a 500. Clamped in the service, below the router's Query bound,
# so a non-router caller cannot reach the encoder either.
MAX_LIST_OFFSET = 1_000_000


class BookingTransitionInvalidError(Exception):
    """The booking's current state — or the clock — refuses this change. 409
    BOOKING_TRANSITION_INVALID.

    Deliberately ONE code for an illegal status pair, no-show/complete before
    `starts_at`, cancel after it, and resend/phone/reschedule on a booking that
    is not confirmed-and-future. The console renders one sentence either way and
    the refused pair rides this exception's message (D19).
    """


class CustomerAlreadyBookedError(Exception):
    """This customer already holds a live booking at the target instant — a
    reschedule target, or a phone-correction re-point onto a customer who
    already holds this instant (0009's partial unique index, D8). 409
    CUSTOMER_ALREADY_BOOKED."""


class OwnerResendThrottledError(Exception):
    """The per-tenant owner-SMS budget is spent; main.py maps it to the shared
    TOO_MANY_ATTEMPTS 429 with no new code (D10).

    Its own class for the same reason as StorefrontThrottledError / OtpThrottledError
    / BookingThrottledError: these budgets have unrelated keys and unrelated
    operational meanings. Reparenting all of them onto one base stays F21's.
    """


class NotAuthorizedError(Exception):
    """A live staff session whose StaffRole is not OWNER. 403 NOT_AUTHORIZED.

    A no-op today — StaffRole has exactly one member — which is precisely why it
    ships now: on the day E6 adds ASSISTANT, inheriting the future role model by
    default would hand an assistant the bride's phone with no code change and no
    failing test. 403 and not 401: the caller IS authenticated, she is just not
    an owner.
    """
