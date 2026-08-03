"""F59's board: the first-name rule, the wire models and the board service,
driven with fakes and no database.

The SQL half is `test_queue_repositories.py` (db-marked) and the HTTP half is
`test_queue_board_api.py`. What is worth testing here is the derivation table
of D5 — nine decided cases, every one of them about reducing how identifiable a
woman is on a screen a room full of strangers can read — the absence of a
ticket id from the wire model, and the metering.
"""

import pytest

from app.booking.validation import BookingValidationError, validate_customer_name
from app.queue.schemas import QueueBoardEntry, QueueBoardView
from app.queue.validation import BOARD_NAME_MAX, BOARD_ROW_LIMIT, board_display_name

# --- D5: the first-name derivation, every decided case ---


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        # The ordinary case: her surname stays in the database.
        ("נועה כהן", "נועה"),
        # Three tokens, still one token out.
        ("נועה מרים כהן", "נועה"),
        # A one-word name is shown IN FULL — there is no surname to drop, and a
        # placeholder would make the board useless for her.
        ("נועה", "נועה"),
        # ⚠ DECIDED BEHAVIOUR, NOT A BUG. Writing the family name first is
        # ordinary Israeli form-filling and `name` is one free-text field with
        # no structure, so the derivation has no way to know. Declined: a
        # name-order heuristic; declined: a surname stop-list — no heuristic can
        # classify a token in free text and every one that tries is wrong on
        # real names. What the code guarantees is exactly this and nothing more:
        # ONE whitespace-delimited token leaves the database, whichever it is.
        # The remedy is the collection notice, not a heuristic here.
        ("כהן נועה", "כהן"),
        # `str.split()` with no argument: any run of whitespace, empties
        # discarded. Leading spaces, double spaces and a trailing newline all
        # fall out. `.split(" ")` would answer "" here.
        ("  נועה   כהן\n", "נועה"),
        # An honorific first renders a harmless word. Declined: a stop-list.
        ("גב' כהן", "גב'"),
        # Hyphens are not whitespace, so a hyphenated given name is one token.
        ("נועה-מרים כהן", "נועה-מרים"),
    ],
)
def test_the_first_name_rule_is_one_whitespace_delimited_token(stored: str, shown: str) -> None:
    assert board_display_name(stored) == shown


def test_a_token_at_the_bound_is_shown_whole() -> None:
    """The boundary comes from D5's RULE — `first[:BOARD_NAME_MAX - 1] + "…"` —
    never from an example payload."""
    exactly = "א" * BOARD_NAME_MAX
    assert len(exactly) == 12
    assert board_display_name(exactly) == exactly
    assert board_display_name(f"{exactly} כהן") == exactly


def test_a_token_one_character_past_the_bound_is_truncated_with_a_visible_ellipsis() -> None:
    """11 characters then «…», so the rendered string is still 12. Truncating at
    BOARD_NAME_MAX instead would put 13 characters on the wall.

    The ellipsis is visible on purpose: the board never silently misrepresents a
    name. And the truncation is SERVER-side, so the tail never reaches the wire
    — a client-side text-ellipsis would ship the whole token and hide it."""
    over = "א" * (BOARD_NAME_MAX + 1)
    shown = board_display_name(over)
    assert shown == "א" * (BOARD_NAME_MAX - 1) + "…"
    assert len(shown) == BOARD_NAME_MAX


def test_the_derivation_cannot_raise_on_a_stored_row() -> None:
    """`name.split()[0]` would IndexError on a whitespace-only name, and nothing
    can store one: `validate_customer_name` rejects `not name.strip()` before
    the insert. Asserted here so a future loosening of that validator fails a
    test rather than a wall screen."""
    for blank in ("", "   ", "\t\n"):
        with pytest.raises(BookingValidationError):
            validate_customer_name(blank)


def test_the_row_cap_is_a_server_side_bound() -> None:
    """It lives beside the name bound because it is the same kind of thing: at
    most this many names leave the database, whatever the queue length. A
    client-side cap would ship forty names to a browser and render five."""
    assert BOARD_ROW_LIMIT == 5


# --- D7: the wire, and the id that must never be on it ---


def test_a_board_entry_carries_exactly_three_fields_and_no_ticket_id() -> None:
    """The ticket id IS F33's capability, issued exactly once at creation and by
    no other server path ever. A board that returned ids would hand every
    passer-by a live, pollable capability over every woman's visit, six at a
    time, every five seconds, forever.

    Pydantic introspection rather than a source grep, so it fails the moment
    anyone ADDS a field rather than passing vacuously."""
    assert set(QueueBoardEntry.model_fields) == {"position", "first_name", "called"}


def test_the_board_view_carries_the_entries_and_the_untruncated_total() -> None:
    assert set(QueueBoardView.model_fields) == {"entries", "waiting_total"}


def test_called_is_a_boolean_and_never_the_instant() -> None:
    """The wall needs to know WHETHER, not WHEN. Shipping the instant would let
    anyone watching time how long a named woman has stood at the counter, and
    nothing on the board renders it."""
    entry = QueueBoardEntry(position=1, first_name="נועה", called=True)
    assert entry.model_dump() == {"position": 1, "first_name": "נועה", "called": True}
    assert isinstance(entry.called, bool)


def test_an_empty_board_is_a_real_view_and_never_a_null() -> None:
    view = QueueBoardView(entries=[], waiting_total=0)
    assert view.model_dump() == {"entries": [], "waiting_total": 0}
