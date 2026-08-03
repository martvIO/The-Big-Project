"""The two error classes, F33's one bound, and F59's board rule with its two.

The name and the phone rules are IMPORTED, never restated: a queue ticket
carries the same customer name as a booking and the same normalised Israeli
mobile, so a second copy of either would be a second place for the bound to
drift. F33 invents no name rule and no phone rule.

F59's two bounds are a different kind of thing and that is why they live here
rather than in a layout file: both are DISCLOSURE limits on an anonymous,
unauthenticated endpoint whose output is a television on a boutique wall. How
many names leave the database, and how much of each one, are decided on the
server and nowhere else.
"""

from app.booking.validation import validate_customer_name
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.constants import VisitType

# The two values the migration's CHECK admits, read off the enum so widening the
# column and widening the API cannot happen independently.
VISIT_TYPES = frozenset(visit_type.value for visit_type in VisitType)

# At most this many rows leave the database on a board read, whatever the queue
# length, and it is applied in the SQL LIMIT rather than in the client. A
# client-side cap would ship forty names to a browser and render five, which is
# forty names in a network trace, a devtools panel and any intermediary that
# ignores no-store. It does not adapt to the viewport: a bigger screen gets more
# whitespace, not more names, because otherwise the amount of personal data on
# the wire would be a function of the boutique's display settings.
BOARD_ROW_LIMIT = 5

# The longest first name the board publishes. Longer tokens are truncated
# SERVER-side so the tail never reaches the wire.
BOARD_NAME_MAX = 12


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


def board_display_name(name: str) -> str:
    """The ONLY personal datum F59 puts on the wire.

    Exactly ONE whitespace-delimited token leaves the database — WHICHEVER token
    she typed first. That is usually the given name and it is NOT a guarantee:
    «כהן נועה» is ordinary Israeli form-filling and this returns «כהן». No
    heuristic fixes that (none can classify a token in free text, and every one
    that tries is wrong on real names); the collection notice at check-in is the
    remedy, not code here.

    `str.split()` with no argument, deliberately: it splits on any run of
    whitespace and discards empties, so leading spaces, double spaces and a
    trailing newline all fall out. It cannot IndexError on a STORED row because
    `validate_customer_name` rejects a blank name before the insert — pinned by
    a test so a future loosening of that validator fails there rather than on a
    wall screen.

    ponytail: truncation slices code points, so a surrogate pair cannot split
    but a combining mark can detach from its base and render as a stray
    diacritic. Grapheme-aware truncation needs a dependency (`regex` /
    `grapheme`) for a cosmetic edge on a name already too long to fit; accepted
    ceiling, upgrade when a real name hits it.
    """
    first = name.split()[0]
    return first if len(first) <= BOARD_NAME_MAX else first[: BOARD_NAME_MAX - 1] + "…"


def validate_checkin_request(*, name: str, visit_type: str) -> None:
    """Pure shape checks only, and there are exactly two.

    There is no check on the phone here — `normalize_israeli_mobile` is both the
    check and the conversion, so the service calls it directly and gets the
    stored form back.
    """
    validate_customer_name(name)
    if visit_type not in VISIT_TYPES:
        raise DomainValidationError("visit_type is not one of the accepted values")
