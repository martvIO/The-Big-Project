"""F59's board: the first-name rule, the wire models and the board service,
driven with fakes and no database.

The SQL half is `test_queue_repositories.py` (db-marked) and the HTTP half is
`test_queue_board_api.py`. What is worth testing here is the derivation table
of D5 — nine decided cases, every one of them about reducing how identifiable a
woman is on a screen a room full of strangers can read — the absence of a
ticket id from the wire model, and the metering.
"""

import datetime
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, NamedTuple, cast

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.validation import BookingValidationError, validate_customer_name
from app.core.config import Settings
from app.main import create_app
from app.queue.schemas import QueueBoardEntry, QueueBoardView
from app.queue.service import QueueService
from app.queue.validation import (
    BOARD_NAME_MAX,
    BOARD_ROW_LIMIT,
    CheckinThrottledError,
    board_display_name,
)
from app.storefront.validation import Clock

TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
# 20:00Z on 2026-07-18 is 23:00 Jerusalem the SAME day. A UTC-derived date would
# agree here and disagree at 21:30Z, which is why the boundary pair is below.
NOW = datetime.datetime(2026, 7, 18, 20, 0, tzinfo=datetime.UTC)
JERUSALEM_DAY = datetime.date(2026, 7, 18)

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
    passer-by a live, pollable capability over every woman's visit, five at a
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


# --- D6: the board service, its own budget, and the clock it reads once ---


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _BoardRow(NamedTuple):
    name: str
    called_at: datetime.datetime | None


class _FakeResult:
    def __init__(self, rows: list[_BoardRow], total: int) -> None:
        self._rows = rows
        self._total = total

    def all(self) -> list[_BoardRow]:
        return self._rows

    def scalar_one(self) -> int:
        return self._total


class _FakeSession:
    """The `test_checkin_service.py` scaffold: enough surface for
    `tenant_session` and the REAL `QueueTicketsRepository`, so a statement
    escaping to a real session raises here instead of passing silently. The
    repository is real on purpose — a fake one would let the service and the
    query drift apart, which is the one failure this feature cannot afford.

    `statements` holds the SELECT objects, not `str()` of them: `execute`
    answers a canned result whatever it is handed, so any claim about a WHERE
    clause or a LIMIT has to read the statement itself.
    """

    def __init__(self, rows: list[_BoardRow] | None = None, total: int | None = None) -> None:
        self.rows = rows if rows is not None else []
        self.total = total if total is not None else len(self.rows)
        self.statements: list[Any] = []

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> _FakeResult:
        if args:
            self.statements.append(args[0])
        return _FakeResult(self.rows, self.total)


def _board_select(session: _FakeSession) -> Any:
    """statements[0] is `tenant_session`'s own `set_config`; [1] is the board's
    projection and [2] its count. Named rather than indexed inline so the next
    reader does not have to rediscover that the session binding is a
    statement."""
    return session.statements[1]


def _factory(session: _FakeSession) -> Any:
    @asynccontextmanager
    async def factory() -> AsyncIterator[_FakeSession]:
        yield session

    return factory


def _service(
    session: _FakeSession | None = None,
    *,
    board_limiter: FixedWindowRateLimiter | None = None,
    clock: Clock | None = None,
) -> QueueService:
    return QueueService(
        cast(async_sessionmaker, _factory(session if session is not None else _FakeSession())),
        create_limiter=FixedWindowRateLimiter(200, 3600.0, lambda: 0.0),
        position_ticket_limiter=FixedWindowRateLimiter(30, 60.0, lambda: 0.0),
        position_miss_limiter=FixedWindowRateLimiter(120, 60.0, lambda: 0.0),
        board_limiter=board_limiter or FixedWindowRateLimiter(600, 60.0, lambda: 0.0),
        clock=clock or (lambda: NOW),
    )


async def test_the_board_numbers_its_entries_from_one_in_list_order() -> None:
    """The positions are the SERVER's, derived from the order the repository
    returned. A client that renumbered would be free to disagree with her phone,
    and the whole point of the read is that it cannot."""
    session = _FakeSession([_BoardRow(f"א{index}", None) for index in range(3)], total=3)
    view = await _service(session).board(TENANT_ID)
    assert [entry.position for entry in view.entries] == [1, 2, 3]
    assert [entry.first_name for entry in view.entries] == ["א0", "א1", "א2"]


async def test_called_is_derived_from_the_instant_and_the_instant_never_reaches_the_view() -> None:
    called = datetime.datetime(2026, 7, 18, 20, 30, tzinfo=datetime.UTC)
    session = _FakeSession([_BoardRow("נועה", called), _BoardRow("מיכל", None)], total=2)
    view = await _service(session).board(TENANT_ID)
    assert [entry.called for entry in view.entries] == [True, False]
    assert str(called.hour) not in view.model_dump_json()
    assert view.model_dump() == {
        "entries": [
            {"position": 1, "first_name": "נועה", "called": True},
            {"position": 2, "first_name": "מיכל", "called": False},
        ],
        "waiting_total": 2,
    }


async def test_the_service_derives_the_first_name_and_never_ships_the_stored_one() -> None:
    session = _FakeSession([_BoardRow("נועה כהן", None)], total=1)
    view = await _service(session).board(TENANT_ID)
    assert view.entries[0].first_name == "נועה"
    assert "כהן" not in view.model_dump_json()


async def test_an_empty_board_is_a_view_and_never_a_miss() -> None:
    """There is no miss branch and there must not be one: every resolvable
    tenant has a board, empty or not. A 404 on an empty queue would render the
    screen's error arm for most of the shop day."""
    view = await _service(_FakeSession([], total=0)).board(TENANT_ID)
    assert view.model_dump() == {"entries": [], "waiting_total": 0}


async def test_the_total_is_the_repositorys_count_and_not_the_row_count() -> None:
    """The overflow line's only source. `len(entries)` is capped, so it would
    say «ועוד 0» forever, silently, on a wall."""
    session = _FakeSession([_BoardRow(f"א{index}", None) for index in range(BOARD_ROW_LIMIT)])
    session.total = 9
    view = await _service(session).board(TENANT_ID)
    assert len(view.entries) == BOARD_ROW_LIMIT
    assert view.waiting_total == 9


async def test_the_cap_is_the_servers_and_it_is_in_the_sql() -> None:
    """D4: at most BOARD_ROW_LIMIT names leave the database whatever the queue
    length. A client-side cap would ship forty names to a browser and render
    five — forty names in a network trace and in any intermediary that ignores
    no-store."""
    session = _FakeSession([_BoardRow("נועה", None)], total=1)
    await _service(session).board(TENANT_ID)
    assert _board_select(session)._limit == BOARD_ROW_LIMIT


async def test_the_board_reads_todays_jerusalem_day_from_the_injected_clock() -> None:
    """The one clock read in the feature, and it is on the SERVER. The request
    carries no date at all, so the board empties at midnight Jerusalem with zero
    client-side date logic — on a screen expected to be mounted for months.

    Asserted on the statement's bound value, because the fake answers the same
    rows whatever it is handed."""
    session = _FakeSession([_BoardRow("נועה", None)], total=1)
    await _service(session).board(TENANT_ID)
    assert _board_select(session).compile().params["queue_day_1"] == JERUSALEM_DAY


async def test_the_jerusalem_day_rolls_before_the_utc_day_does() -> None:
    """21:30Z on the 18th is 00:30 Jerusalem on the 19th. The boutique's queue
    has already turned over; the UTC calendar has not."""
    session = _FakeSession([_BoardRow("נועה", None)], total=1)
    await _service(
        session, clock=lambda: datetime.datetime(2026, 7, 18, 21, 30, tzinfo=datetime.UTC)
    ).board(TENANT_ID)
    bound = _board_select(session).compile().params
    assert bound["queue_day_1"] == datetime.date(2026, 7, 19)
    assert JERUSALEM_DAY not in bound.values()


# --- the fourth budget ---


async def test_the_board_budget_is_charged_on_every_read_including_an_empty_one() -> None:
    """The cost is the query, not the rows: two index scans per request, twelve
    times a minute per screen, forever."""
    limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    await _service(_FakeSession([], total=0), board_limiter=limiter).board(TENANT_ID)
    assert limiter.is_blocked(f"queue:board:{TENANT_ID}") is True


async def test_a_spent_board_budget_throttles_the_next_read() -> None:
    limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    service = _service(_FakeSession([_BoardRow("נועה", None)], total=1), board_limiter=limiter)
    await service.board(TENANT_ID)
    with pytest.raises(CheckinThrottledError):
        await service.board(TENANT_ID)


async def test_the_board_budget_is_keyed_on_the_boutique_and_never_on_a_person() -> None:
    """What keeps the shared TOO_MANY_ATTEMPTS body safe here: the key is an
    operational fact about a shop, so a 429 discloses nothing about anybody."""
    limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    await _service(board_limiter=limiter).board(TENANT_ID)
    assert limiter.is_blocked(f"queue:board:{TENANT_ID}") is True
    assert limiter.is_blocked(f"queue:board:{uuid.uuid4()}") is False


async def test_a_spent_board_budget_leaves_the_three_check_in_budgets_alone() -> None:
    """ONE BUDGET, ONE INSTANCE. Two keys on one FixedWindowRateLimiter share
    one ceiling, so a flooded wall screen must not be able to 429 a woman
    scanning the QR at the door."""
    board_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    service = _service(board_limiter=board_limiter)
    await service.board(TENANT_ID)
    with pytest.raises(CheckinThrottledError):
        await service.board(TENANT_ID)
    assert board_limiter.is_blocked(f"checkin:{TENANT_ID}") is False


def test_the_app_wires_four_distinct_limiter_instances_into_the_queue_service() -> None:
    """⚠ THE assertion that catches a builder reaching for an existing instance.

    `max_attempts` lives on the LIMITER, so one instance is one ceiling however
    many keys it holds. Reusing any of the three shipped budgets is the failure
    D6 works the arithmetic against: one wall screen is 720 reads/hour, which is
    3.6x the ENTIRE check-in create ceiling and would spend it seventeen minutes
    into the shop day — closing the front door to every woman scanning the QR.

    Read off the real `create_app` wiring rather than a service this test built,
    because main.py is where the mistake would be made.
    """
    service = create_app().state.queue_service
    limiters = [
        service._create_limiter,
        service._position_ticket_limiter,
        service._position_miss_limiter,
        service._board_limiter,
    ]
    assert len({id(limiter) for limiter in limiters}) == 4
    # Four objects is not enough on its own: a FOURTH instance built from
    # another feature's settings is four objects with the wrong ceiling, and at
    # the miss brake's 120/60s the board holds ten concurrent viewers — two
    # screens and eight phones, which is the ordinary afternoon this feature
    # exists for. The wired budget must be the BOARD's.
    settings = Settings()
    assert service._board_limiter._max == settings.queue_board_max_per_window
    assert service._board_limiter._window == settings.queue_board_window_seconds


def test_the_board_budget_has_its_own_two_settings_fields() -> None:
    """Tunable during an incident without a deploy, the `checkin_*` precedent.
    The number is sized against CONCURRENT VIEWERS — screens plus the phones in
    the room, which D11 deliberately puts on this same key — not against screens
    alone."""
    settings = Settings()
    assert settings.queue_board_max_per_window == 600
    assert settings.queue_board_window_seconds == 60
