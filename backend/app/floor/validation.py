"""Pure domain validation for the floor's room registry, and the two occupancy
conflicts — no I/O, unit-tested locally.

One bound, one normaliser and two errors. `sort_order`'s bound is deliberately
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


class _OccupiedError(Exception):
    """Base for every 409 here that can carry an optional `details` — F36's two
    occupancy conflicts, and F58's two ticket-state ones. **Not** a
    `DomainValidationError` subclass, and that is load-bearing: Starlette
    resolves a handler by walking
    `type(exc).__mro__`, so parenting these onto the domain-400 base would make
    the shipped handler answer 400 and leave both 409 handlers unreachable.

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


class QueueEmptyError(Exception):
    """Take-next found nobody waiting. A 409, and it follows `_OccupiedError`'s
    PATTERN rather than its class: it is deliberately NOT a
    `DomainValidationError` subclass, because Starlette resolves a handler by
    walking `type(exc).__mro__` and parenting it onto the domain-400 base would
    make the shipped 400 handler answer first and leave this 409's handler
    unreachable. It carries no `details` and never will — there is nobody to
    name — so it needs none of `_OccupiedError`'s machinery either.

    Not a 404: that would mean the ROOM is missing, which the panel renders as
    «החדר כבר לא זמין» about a room that is fine. Not an unchanged 200 either,
    which leaves the manager wondering whether the tap registered. And not an
    outage register on the client: the queue emptying between the render and the
    tap is an ordinary five-second race.
    """


class RoomOccupiedError(_OccupiedError):
    """Somebody else holds this room — a claim that violated
    `idx_fitting_room_assignments_room_active`, or a delete refused because the
    room is occupied. `details` names her: `{"staff_display_name": …}`."""


class QueueTicketNotWaitingError(_OccupiedError):
    """The ticket a verb named is live but is no longer `waiting` — she was
    dispatched, skipped out or removed between the render and the tap. `details`
    names the state: `{"status": …}`, which is what lets the console choose
    between «היא כבר בטיפול.» and «הכניסה הזו נסגרה.»

    ⚠ `details` is REQUIRED in practice on this one and optional in the type,
    which is `_OccupiedError`'s shape and deliberately not narrowed: the two
    handlers share `_occupied_body`, and a body that omits an absent key beats
    one that writes a null on a legally binding surface.
    """


class QueueTicketChangedError(_OccupiedError):
    """A skip whose `skip_count` moved under the caller.

    ⚠ **This 409 is what stops two ordinary single taps removing a customer.**
    Both managers rendered `skip_count == 0`, so neither client showed the
    confirm — which is gated on `>= 1` — and without the refusal the second tap
    would escalate to `removed` on a count nobody saw. `details` carries the
    count the server actually holds; the next tick renders it and the next press
    correctly opens the confirm.

    Its own code rather than a flavour of `QUEUE_TICKET_NOT_WAITING`: the ticket
    IS still waiting and still skippable, and the remedy is «רענני ונסי שוב»
    rather than «הכניסה הזו נסגרה».
    """


class StaffOccupiedError(_OccupiedError):
    """The target staffer already holds another room — a claim or a handover
    that violated `idx_fitting_room_assignments_staff_active`. `details` names
    that room: `{"room_label": …}`.

    Its own code rather than a flavour of `ROOM_OCCUPIED` with a discriminating
    `details`: two causes, two Hebrew sentences, two remedies (take another room
    vs. release her other room first), and a `details`-key sniff in the frontend
    is a worse place for that branch than an error code.
    """
