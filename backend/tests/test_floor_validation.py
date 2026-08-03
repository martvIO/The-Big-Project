"""F36's room label rule, the symmetric sort_order bound, the two 409s, and
F37's SOS note.

Fast, no Postgres, no fakes: `app/floor/validation.py` is pure and the request
models are pydantic. This is the module that pins the two things a later editor
would most plausibly get wrong — that the label bound is checked AFTER the strip,
and that `sort_order` is the house SYMMETRIC bound rather than a `0 <=` floor.
"""

import uuid

import pytest
from pydantic import ValidationError

from app.catalog.validation import MAX_SORT_ORDER
from app.errors import DomainValidationError
from app.floor.schemas import (
    ClaimRoomRequest,
    CreateRoomRequest,
    RaiseSosRequest,
    UpdateRoomRequest,
)
from app.floor.validation import (
    MAX_ROOM_LABEL_LENGTH,
    MAX_SOS_NOTE_LENGTH,
    FloorValidationError,
    RoomOccupiedError,
    SosValidationError,
    StaffOccupiedError,
    normalize_room_label,
    normalize_sos_note,
)

# --- the label ---------------------------------------------------------------


def test_a_room_label_is_stripped() -> None:
    assert normalize_room_label("  חדר 2  ") == "חדר 2"


@pytest.mark.parametrize("raw", ["", "   ", "\t", "\n"])
def test_a_label_that_is_blank_after_stripping_is_refused(raw: str) -> None:
    """A room whose label is whitespace renders an empty tile a staffer cannot
    name over the radio. The strip is what makes `" "` the same input as `""`."""
    with pytest.raises(FloorValidationError):
        normalize_room_label(raw)


def test_the_room_label_bound_is_checked_after_the_strip() -> None:
    """⚠ Order matters and this is the assertion that pins it. 40 characters
    wrapped in spaces is a LEGAL label; checking the length first would refuse
    it, and a bound applied to text the server is about to throw away is a bound
    on the wrong string."""
    assert MAX_ROOM_LABEL_LENGTH == 40
    at_bound = "א" * MAX_ROOM_LABEL_LENGTH
    assert normalize_room_label(f"  {at_bound}  ") == at_bound
    with pytest.raises(FloorValidationError):
        normalize_room_label("א" * (MAX_ROOM_LABEL_LENGTH + 1))


def test_the_label_error_is_a_house_400_and_not_a_new_code() -> None:
    """`FloorValidationError` subclasses the shared base, so `main.py`'s shipped
    `DomainValidationError` handler answers it — no new handler, no new code."""
    assert issubclass(FloorValidationError, DomainValidationError)
    with pytest.raises(DomainValidationError):
        normalize_room_label("")


# --- sort_order --------------------------------------------------------------


@pytest.mark.parametrize("value", [-MAX_SORT_ORDER, -1, 0, 1, MAX_SORT_ORDER])
def test_sort_order_takes_the_house_symmetric_bound(value: int) -> None:
    """⚠ NEGATIVES ARE LEGAL, and that is the point rather than an oversight.

    `Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)` is the shipped
    line (`catalog/schemas.py`, `boutique/schemas.py`), and a negative is how
    the registry's reorder control moves one room to the front without
    renumbering the rest. Halving the shipped constant's range would leave the
    floor in prose only, where a builder copying the neighbouring `Field(...)`
    would never see it.
    """
    assert CreateRoomRequest(label="חדר", sort_order=value).sort_order == value
    assert UpdateRoomRequest(sort_order=value).sort_order == value


@pytest.mark.parametrize("value", [-MAX_SORT_ORDER - 1, MAX_SORT_ORDER + 1])
def test_sort_order_one_past_either_bound_is_refused(value: int) -> None:
    with pytest.raises(ValidationError):
        CreateRoomRequest(label="חדר", sort_order=value)
    with pytest.raises(ValidationError):
        UpdateRoomRequest(sort_order=value)


def test_sort_order_defaults_to_zero_and_the_registry_may_omit_it() -> None:
    assert CreateRoomRequest(label="חדר").sort_order == 0
    assert UpdateRoomRequest().sort_order is None


def test_every_room_body_forbids_unknown_keys() -> None:
    """`ForbidExtraModel`, the house form — an unknown key is a 400, not a
    silently ignored field."""
    for model, payload in (
        (CreateRoomRequest, {"label": "חדר", "nope": 1}),
        (UpdateRoomRequest, {"label": "חדר", "nope": 1}),
        (ClaimRoomRequest, {"nope": 1}),
    ):
        with pytest.raises(ValidationError):
            model(**payload)


def test_a_claim_body_may_name_neither_a_staffer_nor_a_booking() -> None:
    """The anonymous visit is the DEFAULT, not an edge case: a staffer prepping
    a room claims it for herself with no client at all (D9)."""
    body = ClaimRoomRequest()
    assert body.staff_user_id is None
    assert body.booking_id is None


# --- the two 409s ------------------------------------------------------------


@pytest.mark.parametrize("error", [RoomOccupiedError, StaffOccupiedError])
def test_an_occupancy_error_carries_details_or_omits_them_entirely(
    error: type[RoomOccupiedError] | type[StaffOccupiedError],
) -> None:
    """⚠ `details` is OPTIONAL and is never `{"…": None}`.

    The loser of a claim blocks on the winner's uncommitted index key and gets
    the violation when the winner commits — and between that commit and the
    occupant read the winner can RELEASE. There is then nobody to name, and
    «{{name}} כבר בחדר הזה.» rendering with an empty interpolation on a legally
    binding surface is worse than a sentence that admits it does not know.
    """
    assert error().details is None
    assert error({"room_label": "חדר 2"}).details == {"room_label": "חדר 2"}


@pytest.mark.parametrize("error", [RoomOccupiedError, StaffOccupiedError])
def test_an_occupancy_error_is_not_a_validation_error(
    error: type[RoomOccupiedError] | type[StaffOccupiedError],
) -> None:
    """Starlette resolves a handler by walking `type(exc).__mro__`, so an
    occupancy error parented onto `DomainValidationError` would answer 400 from
    the shipped handler and the two 409s would be unreachable."""
    assert not issubclass(error, DomainValidationError)


# --- F37: the SOS note -------------------------------------------------------


def test_an_sos_note_is_stripped() -> None:
    assert normalize_sos_note("  צריך סיכות  ") == "צריך סיכות"


@pytest.mark.parametrize("raw", [None, "", "   ", "\t", "\n"])
def test_a_blank_sos_note_is_none_and_is_not_an_error(raw: str | None) -> None:
    """⚠ The ASYMMETRY with `normalize_room_label` is the decision. A blank label
    is REFUSED because a room nobody can name over the radio is a broken tile; a
    blank note is the ORDINARY case — she tapped the button and did not type,
    which is the whole design of a one-tap page. `None` and `""` are one input
    and both mean "no note"."""
    assert normalize_sos_note(raw) is None


def test_the_sos_note_bound_is_checked_after_the_strip() -> None:
    """Same order rule as the label, same reason: 120 characters wrapped in
    spaces is a legal note, and a bound applied before the strip is a bound on a
    string the server is about to throw away."""
    assert MAX_SOS_NOTE_LENGTH == 120
    at_bound = "א" * MAX_SOS_NOTE_LENGTH
    assert normalize_sos_note(f"  {at_bound}  ") == at_bound
    with pytest.raises(SosValidationError):
        normalize_sos_note("א" * (MAX_SOS_NOTE_LENGTH + 1))


def test_the_note_error_is_a_house_400_and_not_a_new_code() -> None:
    """`SosValidationError` subclasses the shared base, so `main.py`'s shipped
    `DomainValidationError` handler answers it. F37 adds TWO error codes and
    neither of them is this one."""
    assert issubclass(SosValidationError, DomainValidationError)
    with pytest.raises(DomainValidationError):
        normalize_sos_note("א" * (MAX_SOS_NOTE_LENGTH + 1))


def test_the_raise_body_forbids_unknown_keys_including_raised_by() -> None:
    """⚠ **The named assertion, not an assertion-in-prose.** `raised_by` is
    exactly the shape `FloorService._authorize`'s docstring calls THE hazard: a
    body-supplied staff id doubling as the caller's identity. The raise body
    carries a TARGET and never an actor, and `ForbidExtraModel` is what makes
    "the server ignores it" into "the server refuses it" — nobody may raise a
    page AS somebody else, not even an owner, because an SOS is a first-person
    statement."""
    for payload in ({"raised_by": str(uuid.uuid4())}, {"nope": 1}):
        with pytest.raises(ValidationError):
            RaiseSosRequest(**payload)


def test_a_raise_body_may_be_completely_empty() -> None:
    """The one-tap page: no target (the shift-manager ROLE), no room, no note.
    All three default to None and that is the common case, not an edge one."""
    body = RaiseSosRequest()
    assert body.target_staff_user_id is None
    assert body.fitting_room_assignment_id is None
    assert body.note is None
