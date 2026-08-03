"""The two error classes and the one bound F33 owns.

The name and the phone rules are IMPORTED, never restated: a queue ticket
carries the same customer name as a booking and the same normalised Israeli
mobile, so a second copy of either would be a second place for the bound to
drift. F33 invents no name rule and no phone rule.
"""

from app.booking.validation import validate_customer_name
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.constants import VisitType

# The two values the migration's CHECK admits, read off the enum so widening the
# column and widening the API cannot happen independently.
VISIT_TYPES = frozenset(visit_type.value for visit_type in VisitType)


class CheckinThrottledError(Exception):
    """One of the three check-in budgets is spent; main.py maps it to a 429
    carrying the shared TOO_MANY_ATTEMPTS body.

    Its own class rather than a reuse of StorefrontThrottledError, for the
    reason that class's own docstring gives: unrelated budgets, keys and
    operational meanings, and importing a read-throttle error into the queue
    path to dodge a three-line handler would be a semantic lie no test catches.
    Reparenting every throttle error onto one base is F21's behaviour-neutral
    cleanup.

    All three keys it can carry are about a boutique or about a ticket the
    caller already holds — never about a person. That is what makes ONE shared
    429 safe here where the OTP surface needed two different answers.
    """


class QueueTicketNotFoundError(DomainNotFoundError):
    """An unknown, soft-deleted or foreign-tenant ticket id.

    A DomainNotFoundError subclass so the platform's shipped handler maps it to
    the house-shape 404 — no new handler, no new error code. Foreign-tenant is
    deliberately the SAME answer as absent: RLS plus the repository's explicit
    predicate make the two indistinguishable, and a 403 would confirm that the
    guessed ticket exists.
    """


def validate_checkin_request(*, name: str, visit_type: str) -> None:
    """Pure shape checks only, and there are exactly two.

    There is no check on the phone here — `normalize_israeli_mobile` is both the
    check and the conversion, so the service calls it directly and gets the
    stored form back.
    """
    validate_customer_name(name)
    if visit_type not in VISIT_TYPES:
        raise DomainValidationError("visit_type is not one of the accepted values")
