"""Pure domain validation for the floor's room registry, the two occupancy
conflicts and F37's SOS page — no I/O, unit-tested locally.

Two bounds, two normalisers and five errors. `sort_order`'s bound is deliberately
NOT restated here: it is `MAX_SORT_ORDER` from `app/catalog/validation.py`,
applied on the request models the way `catalog/schemas.py` and
`boutique/schemas.py` already apply it, so there is one number and one place to
change it.
"""

from app.errors import DomainValidationError


class FloorValidationError(DomainValidationError):
    """Domain-rule violation on a room write; `main.py`'s shipped handler maps
    it to the house-shape 400 carrying this message. No new code, no new
    handler."""


# A room label is a word a staffer says out loud across a shop floor — «חדר 2»,
# «הבמה», «האולם הגדול». Forty characters is a phrase, not a paragraph, and the
# registry renders every label on a tile beside a claim control.
MAX_ROOM_LABEL_LENGTH = 40


def normalize_room_label(label: str) -> str:
    """Strip, then bound — and the ORDER is the rule, not the implementation.

    A forty-character label typed with a trailing space is a legal label; a
    length check applied before the strip would refuse it, which is a bound on
    a string the server is about to throw away. The blank check comes out of the
    same strip: `" "` and `""` are one input, because a room whose label is
    whitespace renders a tile nobody can name over the radio.
    """
    stripped = label.strip()
    if not stripped:
        raise FloorValidationError("label is required")
    if len(stripped) > MAX_ROOM_LABEL_LENGTH:
        raise FloorValidationError(f"label must be at most {MAX_ROOM_LABEL_LENGTH} characters")
    return stripped


class _DetailedConflictError(Exception):
    """Base for the FOUR 409s that can carry a `details` key — F36's two
    occupancy conflicts and F37's two SOS conflicts.

    ⚠ **Renamed from `_OccupiedError` in F37 and the rename is the point**: two
    of its four subclasses have nothing to do with occupancy, and a base named
    for one half of its children is how the next reader concludes the SOS
    conflicts must be modelled some other way.

    ⚠ **`main.py` registers a handler PER CONCRETE CLASS and there is no handler
    on this base.** Verified rather than assumed, and it is why every subclass
    added here must arrive with its own `@app.exception_handler` block in the
    same PR — without one the 409 answers a bare **500**. Both F37 blocks were
    deleted, one at a time, and each reddened only its own code's tests.

    **Not** a `DomainValidationError` subclass. ⚠ **F37 ran that mutation and the
    inherited sentence here was WRONG**, so it is corrected rather than copied:
    it used to claim that parenting these onto the domain-400 base would make the
    shipped handler answer 400 and leave the 409 handlers unreachable. It does
    not. Starlette walks `type(exc).__mro__` and takes the FIRST match, so a
    handler registered on the CONCRETE class still wins and every 409 stays a
    409 — the mutation left every HTTP assertion green and reddened only the
    `issubclass` one.

    What the parentage actually decides is the fate of a subclass shipped
    WITHOUT its own handler: as an `Exception` it answers a loud 500 that a
    first-run test catches, and under `DomainValidationError` it would answer a
    quiet, plausible **400** on a conflict — the same wrong status the whole
    409-not-400 argument exists to avoid, arriving silently. The rule is
    unchanged; only the reason was overstated.

    ⚠ `details` is OPTIONAL, and when there is nobody to name the key is ABSENT
    rather than null. The loser of a claim blocks on the winner's uncommitted
    index key and gets the violation when the winner commits — and a fitting can
    end in the seconds a claim is queued, so between that commit and the occupant
    read the winner can release. `{"staff_display_name": None}` would break the
    console's `Record<string, string>` type and «{{name}} כבר בחדר הזה.» would
    render with an empty interpolation on a legally binding surface. A sentence
    that admits it does not know is better.
    """

    def __init__(self, details: dict[str, str] | None = None) -> None:
        super().__init__(type(self).__name__)
        self.details = details


class RoomOccupiedError(_DetailedConflictError):
    """Somebody else holds this room — a claim that violated
    `idx_fitting_room_assignments_room_active`, or a delete refused because the
    room is occupied. `details` names her: `{"staff_display_name": …}`."""


class StaffOccupiedError(_DetailedConflictError):
    """The target staffer already holds another room — a claim or a handover
    that violated `idx_fitting_room_assignments_staff_active`. `details` names
    that room: `{"room_label": …}`.

    Its own code rather than a flavour of `ROOM_OCCUPIED` with a discriminating
    `details`: two causes, two Hebrew sentences, two remedies (take another room
    vs. release her other room first), and a `details`-key sniff in the frontend
    is a worse place for that branch than an error code.
    """


# --- F37: the SOS page --------------------------------------------------------

# FOUR WORDS, not a paragraph. «צריך סיכות», «תפס לה הרוכסן» — what a staffer can
# type one-handed while holding a corset closed. 120 characters is the cap and it
# is deliberately generous: a length check on an emergency field is the product
# being clever at the expense of the person in front of it, so the bound exists
# to stop a paste, not to shape a sentence.
MAX_SOS_NOTE_LENGTH = 120


class SosValidationError(DomainValidationError):
    """A page refused before it was written. `main.py`'s shipped handler maps it
    to the house-shape 400 carrying this message — no new code, no new handler.

    ⚠ **There are exactly TWO of these and the list is closed by design**: the
    note is too long, or she tried to page herself. NOTHING ABOUT THE STATE OF
    THE BOUTIQUE MAY RAISE IT — not a missing room, not a deleted room, not a
    released assignment, not a colleague who went home, not a colleague who does
    not exist, not another alert already open. That sentence is «a page is never
    silently dropped» expressed as a list a test can walk.
    """


def normalize_sos_note(note: str | None) -> str | None:
    """Strip, then bound — `normalize_room_label`'s order, for its reason — and
    `""` and `"   "` collapse to `None` rather than raising.

    A blank label is refused because a room nobody can name over the radio is a
    broken tile; a blank NOTE is the ordinary case. She tapped the button and did
    not type, which is the whole design of a one-tap page, so an empty string and
    a missing key are ONE input and both mean "no note".
    """
    if note is None:
        return None
    stripped = note.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_SOS_NOTE_LENGTH:
        raise SosValidationError(f"note must be at most {MAX_SOS_NOTE_LENGTH} characters")
    return stripped


class SosAlreadyAcceptedError(_DetailedConflictError):
    """Somebody else already took it — a losing accept, or a cancel of an
    accepted alert. `details` names her: `{"staff_display_name": …}`.

    ⚠ **`details` is OPTIONAL here and the key is ABSENT rather than null when
    there is nobody to name.** `accepted_by` points at a `staff_users` row that
    staff removal can soft-delete at any time, and the acceptor can be removed
    between her accept and this read. «{{name}} כבר מגיעה.» rendering with an
    empty interpolation on a legally binding surface is worse than a sentence
    that admits it does not know.
    """


class SosClosedError(_DetailedConflictError):
    """The alert is already resolved or cancelled — there is nothing to accept.

    ⚠ **This one NEVER carries `details`, and that is deliberate rather than an
    oversight.** Three of four `details`-bearing codes would be the drift toward
    treating an error envelope as a response; four would make it the default.
    There is also nobody to name: a resolved alert's remedy is not "go talk to
    her", it is "there is nothing to do".
    """
