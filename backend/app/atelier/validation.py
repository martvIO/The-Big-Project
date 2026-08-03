"""Pure domain bounds and error types for the atelier — no I/O.

Every bound here either REUSES a shipped constant's value and its reason, or is
new and says why. Restating a magnitude that already exists elsewhere is how two
places drift, and `test_frontend_constant_parity` exists because that has
happened.

⚠ NO CLIENT CONSTANT MIRRORS ANY OF THESE. The due-date horizon in particular is
a SERVER bound: the console renders the 400 the server returns rather than
pre-checking against a copy.
"""

from app.booking.validation import (
    _CONTROL_CHARS,
    _CONTROL_CHARS_EXCEPT_WS,
    MAX_BOOKING_NOTES_LENGTH,
    MAX_CUSTOMER_NAME_LENGTH,
)
from app.catalog.validation import MAX_DRESS_NAME_LENGTH
from app.errors import DomainValidationError

# The booking path's bounds, reused rather than re-derived. Notes are «להרים 4
# ס״מ, לצרף חגורה» — a paragraph, not a document, rendered as text and never as
# HTML. The dress label mirrors the catalog's own name bound because it is a
# snapshot of exactly that string when dress_id is supplied.
MAX_TICKET_NOTES_LENGTH = MAX_BOOKING_NOTES_LENGTH
MAX_DRESS_LABEL_LENGTH = MAX_DRESS_NAME_LENGTH

# «38, מותן מוקטן» — what she measured, not a stock bucket, and deliberately not
# validated against dress_variants. Short because it is a label a human reads off
# a card at arm's length.
MAX_DRESS_SIZE_LENGTH = 40

# A TYPO FENCE, not a policy about how far ahead a boutique may plan. DATE accepts
# year 9999; `overdue` and F42's date arithmetic both consume this column
# unbounded, so one mistyped year poisons the board's sort and every capacity
# number derived from it. Two years is far beyond any real boutique.
#
# ⚠ THERE IS NO LOWER BOUND, DELIBERATELY. A past due_date is accepted on create
# AND on update, 200, no warning field: a dress that was due yesterday is exactly
# the ticket a boutique most needs to open. The past-date warning is a client
# affordance only.
MAX_DUE_DATE_HORIZON_DAYS = 730

# Re-exported so the service imports its bounds from one module. The two control-
# character regexes are the BOOKING path's, not the storefront's: the whole C0 set
# is barred from every label (a line break in a value that reaches an SMS template
# is header-injection material), while `notes` keeps newlines and tabs because it
# is a paragraph.
CONTROL_CHARS = _CONTROL_CHARS
CONTROL_CHARS_EXCEPT_WS = _CONTROL_CHARS_EXCEPT_WS

__all__ = [
    "CONTROL_CHARS",
    "CONTROL_CHARS_EXCEPT_WS",
    "MAX_CUSTOMER_NAME_LENGTH",
    "MAX_DRESS_LABEL_LENGTH",
    "MAX_DRESS_SIZE_LENGTH",
    "MAX_DUE_DATE_HORIZON_DAYS",
    "MAX_TICKET_NOTES_LENGTH",
    "AtelierValidationError",
    "TicketAlreadyAssignedError",
    "TicketStageConflictError",
]


class AtelierValidationError(DomainValidationError):
    """Domain-rule violation on an atelier write; the platform handler maps it to
    the house-shape 400."""


class TicketStageConflictError(Exception):
    """409 TICKET_STAGE_CONFLICT — the ticket is not where this caller last saw
    it.

    Its own class rather than the shipped generic CONFLICT because the console's
    copy and the user's next move differ from an assignment conflict: a stage
    conflict says the GARMENT moved on and the remedy is to look again. Collapsing
    the two would make the console branch on a message string.
    """


class TicketAlreadyAssignedError(Exception):
    """409 TICKET_ALREADY_ASSIGNED — a colleague claimed it first.

    Raised by the seamstress claim only. Elevated assignment is deliberately
    last-write-wins and takes no 409: a manager reassigning a garment is making a
    staffing decision with a person in front of her.
    """
