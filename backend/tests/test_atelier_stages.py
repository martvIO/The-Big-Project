"""The five-stage derivation, exhaustively — pure, fast, no Postgres, no fakes.

`stage_of` is the one function in this feature that every other one depends on,
and the rule it implements is the one a reader most reliably gets wrong: the
current stage is the RIGHTMOST stamped column, never the first NULL. All 32
combinations of the five nullable stamps are exercised below, which is what turns
spec D2's rule from a comment into a fact.
"""

import datetime
import itertools

import pytest

from app.atelier.stages import STAGE_COLUMNS, later_columns, stage_of
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import TicketStage

_AT = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)


def _ticket(**stamps: datetime.datetime | None) -> AlterationTicket:
    """A detached ORM instance carrying only the stamps under test. Nothing here
    touches a session — `stage_of` reads attributes and that is all it does."""
    return AlterationTicket(
        tenant_id=None,
        customer_id=None,
        due_date=datetime.date(2026, 8, 20),
        effort_minutes=60,
        **{column: stamps.get(column) for column in STAGE_COLUMNS.values()},
    )


def test_the_declaration_order_is_the_total_order() -> None:
    """D2: "DECLARATION ORDER IS THE TOTAL ORDER and D3's predicate builder reads
    it. A member inserted in the middle changes the semantics of every advance."

    So the order is asserted rather than assumed, and a member added anywhere but
    the end is a red test instead of a silent semantic change to every conditional
    write in the feature."""
    assert list(TicketStage) == [
        TicketStage.INTAKE,
        TicketStage.IN_PROGRESS,
        TicketStage.QC,
        TicketStage.READY,
        TicketStage.DELIVERED,
    ]


def test_every_stage_has_exactly_one_column_and_no_column_is_shared() -> None:
    """A sixth stage with no column, or two stages sharing one, would make
    `later_columns` build a predicate that cannot express what it claims."""
    assert set(STAGE_COLUMNS) == set(TicketStage)
    assert len(set(STAGE_COLUMNS.values())) == len(TicketStage)


def test_a_row_with_no_stamp_at_all_reads_intake() -> None:
    """The total-function floor. The writer cannot produce this row — the INSERT
    stamps intake_at — so this is a defence against a hand-edited row, and its
    value is that a poll running every five seconds cannot crash on one."""
    assert stage_of(_ticket()) is TicketStage.INTAKE


def test_the_skipped_stages_row_reads_ready_and_not_in_progress() -> None:
    """THE ROW THE WHOLE RULE EXISTS FOR (D2).

    A seamstress takes a hem from intake straight to ready in one sitting.
    `in_progress_at` and `qc_at` stay NULL forever and the ticket is at `ready`.
    An implementation that walks forward looking for the first NULL answers
    `in_progress` here and is wrong — and it is wrong in the direction that lets
    a stale board stamp a stage the garment has already left."""
    row = _ticket(intake_at=_AT, ready_at=_AT)
    assert stage_of(row) is TicketStage.READY


def test_a_gap_in_the_middle_still_reads_the_rightmost_stamp() -> None:
    """The same rule one column over: qc recorded, in_progress never was."""
    assert stage_of(_ticket(intake_at=_AT, qc_at=_AT)) is TicketStage.QC


def test_only_a_later_stamp_and_nothing_before_it_reads_that_stage() -> None:
    """Not reachable through the API — intake_at is stamped by the INSERT — but
    it is what proves the walk keys on the RIGHTMOST set column rather than on
    a count of set columns or on a contiguous prefix."""
    assert stage_of(_ticket(delivered_at=_AT)) is TicketStage.DELIVERED


@pytest.mark.parametrize(
    "stamped",
    [
        frozenset(combination)
        for size in range(len(TicketStage) + 1)
        for combination in itertools.combinations(TicketStage, size)
    ],
)
def test_stage_of_over_all_thirty_two_combinations(stamped: frozenset[TicketStage]) -> None:
    """All 2^5 subsets of the five stamps, with the expected answer derived from
    the RULE (the last member of TicketStage present in the subset, floor intake)
    rather than from a table — a table would let a reader "fix" both halves the
    same wrong way.

    This is the assertion that makes D2 total: there is no combination of the
    five nullable columns, reachable or not, for which `stage_of` raises or
    returns None."""
    row = _ticket(**{STAGE_COLUMNS[stage]: _AT for stage in stamped})
    expected = TicketStage.INTAKE
    for stage in TicketStage:
        if stage in stamped:
            expected = stage
    assert stage_of(row) is expected


def test_later_columns_for_each_of_the_five_targets() -> None:
    """D3's whole concurrency mechanism, unit-testable with no database.

    The advance predicate is `AND <target>_at IS NULL AND <every later column>
    IS NULL`, and this tuple is that "every later column". `delivered` is the
    empty tuple — nothing comes after it — which is what makes the last advance
    an ordinary conditional write and not a special case."""
    assert later_columns(TicketStage.INTAKE) == (
        "in_progress_at",
        "qc_at",
        "ready_at",
        "delivered_at",
    )
    assert later_columns(TicketStage.IN_PROGRESS) == ("qc_at", "ready_at", "delivered_at")
    assert later_columns(TicketStage.QC) == ("ready_at", "delivered_at")
    assert later_columns(TicketStage.READY) == ("delivered_at",)
    assert later_columns(TicketStage.DELIVERED) == ()


def test_later_columns_never_includes_the_target_itself() -> None:
    """The target's own column is a SEPARATE clause in the predicate (`IS NULL`
    for an advance, `IS NOT NULL` for an undo), so folding it in here would make
    the undo's predicate self-contradictory."""
    for stage in TicketStage:
        assert STAGE_COLUMNS[stage] not in later_columns(stage)
