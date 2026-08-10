"""F22's entries model against real Postgres as the non-owner app role.

Everything here is a claim no fake can make: the active-unique partial index
(one ACTIVE entry per (tenant, phone, day, type) — refused by the DATABASE, not
by a pre-check), its per-tenant scoping under forced RLS, the FIFO order the
manage list publishes, and the guarded cancel's rowcount-0 idempotence.

⚠ db-marked: runs on CI only (no local Docker). Every test mints its own tenant
id — the container is session-scoped and nothing here truncates.
"""

import asyncio
import datetime
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.constants import WaitlistEntryStatus

pytestmark = pytest.mark.db

REPO = WaitlistEntriesRepository()

DAY = datetime.date(2026, 8, 20)
PHONE = "+972501234567"


def _factory(app_role_url: str) -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _run(coro: Callable[[], Coroutine[Any, Any, None]]) -> None:
    asyncio.run(coro())


async def _insert(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    day: datetime.date = DAY,
    type_id: uuid.UUID | None = None,
    phone: str = PHONE,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await REPO.insert(
            session,
            tenant_id=tenant_id,
            day=day,
            appointment_type_id=type_id or uuid.uuid4(),
            phone=phone,
        )
        return row.id


def test_insert_round_trips_with_the_waiting_default(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id, type_id=type_id)
            async with tenant_session(factory, tenant_id) as session:
                row = await REPO.by_id(session, tenant_id, entry_id)
                assert row is not None
                assert row.day == DAY
                assert row.appointment_type_id == type_id
                assert row.phone == PHONE
                # The DB default, never a client literal: F22 writes no status
                # on the insert at all.
                assert row.status == WaitlistEntryStatus.WAITING.value
                assert row.created_at is not None
        finally:
            await engine.dispose()

    _run(check)


def test_the_active_unique_index_refuses_the_exact_tuple(app_role_url: str) -> None:
    """D1's whole point, refused by the database. The second insert of one
    (tenant, phone, day, type) tuple raises — the SERVICE turns that into the
    idempotent re-read; this layer proves the race collapses to one row."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _insert(factory, tenant_id, type_id=type_id)
            with pytest.raises(IntegrityError):
                await _insert(factory, tenant_id, type_id=type_id)
        finally:
            await engine.dispose()

    _run(check)


def test_the_active_unique_index_is_per_tenant(app_role_url: str) -> None:
    """The same (phone, day, type) under two tenants both insert: tenant_id
    leads the index columns, so one bride on two boutiques' waitlists is two
    rows, not a conflict."""
    engine, factory = _factory(app_role_url)
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _insert(factory, uuid.uuid4(), type_id=type_id)
            await _insert(factory, uuid.uuid4(), type_id=type_id)
        finally:
            await engine.dispose()

    _run(check)


def test_a_different_day_or_type_is_not_a_conflict(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _insert(factory, tenant_id, type_id=type_id)
            await _insert(factory, tenant_id, type_id=type_id, day=DAY + datetime.timedelta(days=1))
            await _insert(factory, tenant_id, type_id=uuid.uuid4())
        finally:
            await engine.dispose()

    _run(check)


def test_a_cancelled_entry_frees_the_key(app_role_url: str) -> None:
    """The partial predicate's other half, and F33's first recorded objection
    answered: cancelled leaves the predicate, so the owner cancel (D5) really is
    the in-product remedy for a stuck key — she can rejoin the same day."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id, type_id=type_id)
            async with tenant_session(factory, tenant_id) as session:
                cancelled = await REPO.cancel(session, tenant_id, entry_id)
                assert cancelled is not None
                assert cancelled.status == WaitlistEntryStatus.CANCELLED.value
            await _insert(factory, tenant_id, type_id=type_id)
        finally:
            await engine.dispose()

    _run(check)


def test_cancel_is_a_guarded_update_and_a_second_tap_moves_nothing(app_role_url: str) -> None:
    """`WHERE status = 'waiting'` — rowcount 0 on a cancelled row, so the
    service's double-tap answer is the row as-is rather than a second write."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id)
            async with tenant_session(factory, tenant_id) as session:
                assert await REPO.cancel(session, tenant_id, entry_id) is not None
            async with tenant_session(factory, tenant_id) as session:
                assert await REPO.cancel(session, tenant_id, entry_id) is None
                row = await REPO.by_id(session, tenant_id, entry_id)
                assert row is not None
                assert row.status == WaitlistEntryStatus.CANCELLED.value
        finally:
            await engine.dispose()

    _run(check)


def test_list_active_is_fifo_within_a_day_and_days_ascend(app_role_url: str) -> None:
    """(day, created_at) — the row order IS the position the manage table
    publishes (design §4: no position column, the top row is next)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later_day = DAY + datetime.timedelta(days=2)

    async def check() -> None:
        try:
            first = await _insert(factory, tenant_id, phone="+972501111111")
            second = await _insert(factory, tenant_id, phone="+972502222222")
            early_on_later_day = await _insert(factory, tenant_id, day=later_day)
            async with tenant_session(factory, tenant_id) as session:
                rows = await REPO.list_active(session, tenant_id, from_day=DAY)
                assert [row.id for row in rows] == [first, second, early_on_later_day]
                only_later = await REPO.list_active(session, tenant_id, day=later_day)
                assert [row.id for row in only_later] == [early_on_later_day]
        finally:
            await engine.dispose()

    _run(check)


def test_list_active_hides_cancelled_and_past_days(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            live = await _insert(factory, tenant_id, phone="+972501111111")
            cancelled = await _insert(factory, tenant_id, phone="+972502222222")
            await _insert(
                factory, tenant_id, phone="+972503333333", day=DAY - datetime.timedelta(days=7)
            )
            async with tenant_session(factory, tenant_id) as session:
                await REPO.cancel(session, tenant_id, cancelled)
            async with tenant_session(factory, tenant_id) as session:
                rows = await REPO.list_active(session, tenant_id, from_day=DAY)
                assert [row.id for row in rows] == [live]
        finally:
            await engine.dispose()

    _run(check)


def test_another_tenants_entries_are_invisible(app_role_url: str) -> None:
    """RLS plus the explicit predicate: B's list is empty of A's rows, and A's
    entry id answers None to B — the cross-tenant walker proves the HTTP face of
    this, the repository face lives here."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_a)
            async with tenant_session(factory, tenant_b) as session:
                assert await REPO.by_id(session, tenant_b, entry_id) is None
                assert await REPO.list_active(session, tenant_b, from_day=DAY) == []
                assert await REPO.cancel(session, tenant_b, entry_id) is None
        finally:
            await engine.dispose()

    _run(check)


# --- F23: the offer lifecycle ------------------------------------------------

NOW = datetime.datetime(2026, 8, 19, 9, 0, tzinfo=datetime.UTC)
SLOT = datetime.datetime(2026, 8, 20, 11, 30, tzinfo=datetime.UTC)
DEADLINE = NOW + datetime.timedelta(hours=2)


def _hash(label: str) -> str:
    """⚠ NEVER a bare literal. `idx_waitlist_entries_offer_token` is GLOBAL — it
    has no tenant column, because `/w/{token}` resolves a tenant FROM the token —
    and this file truncates nothing, so two tests sharing one literal are a
    duplicate key across two tenants that had nothing to do with each other. A
    real hash is a sha256 of 32 random bytes, so the collision is an artefact of
    writing them by hand; the suffix restores that property and the label keeps
    the assertions readable."""
    return f"{label}-{uuid.uuid4()}"


async def _offer(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
    *,
    token_hash: str,
    expires_at: datetime.datetime = DEADLINE,
) -> bool:
    async with tenant_session(factory, tenant_id) as session:
        return await REPO.offer(
            session,
            tenant_id,
            entry_id,
            now=NOW,
            starts_at=SLOT,
            expires_at=expires_at,
            token_hash=token_hash,
        )


def test_the_offer_guard_moves_a_waiting_row_once_and_only_once(app_role_url: str) -> None:
    """D3 statement 1. The second call is a concurrent worker arriving late:
    `WHERE status='waiting'` matches nothing and it answers False, which the
    cascade reads as "skip this pair" rather than as an error."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id)
            winner = _hash("hash-a")
            assert await _offer(factory, tenant_id, entry_id, token_hash=winner)
            assert not await _offer(factory, tenant_id, entry_id, token_hash=_hash("hash-b"))
            async with tenant_session(factory, tenant_id) as session:
                row = await REPO.by_id(session, tenant_id, entry_id)
                assert row is not None
                assert row.status == WaitlistEntryStatus.OFFERED.value
                assert row.offered_at == NOW
                assert row.offer_starts_at == SLOT
                assert row.offer_expires_at == DEADLINE
                # The LOSER's token never landed — the winner's row is intact.
                assert row.offer_token_hash == winner
        finally:
            await engine.dispose()

    _run(check)


def test_due_offers_returns_only_the_expired_ones_and_close_offer_moves_them(
    app_role_url: str,
) -> None:
    """The expiry sweep's two halves. `due_offers` reads before the transition so
    the caller can still see each deadline; `close_offer` is the guarded bulk
    UPDATE and its RETURNING is the honest count."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            due = await _insert(factory, tenant_id, phone="+972501111111")
            live = await _insert(factory, tenant_id, phone="+972502222222")
            due_hash = _hash("hash-due")
            await _offer(
                factory,
                tenant_id,
                due,
                token_hash=due_hash,
                expires_at=NOW - datetime.timedelta(minutes=1),
            )
            await _offer(factory, tenant_id, live, token_hash=_hash("hash-live"))
            async with tenant_session(factory, tenant_id) as session:
                rows = await REPO.due_offers(session, tenant_id, now=NOW)
                assert [row.id for row in rows] == [due]
                moved = await REPO.close_offer(
                    session, tenant_id, [due], status=WaitlistEntryStatus.EXPIRED.value
                )
                assert moved == [due]
            async with tenant_session(factory, tenant_id) as session:
                expired = await REPO.by_id(session, tenant_id, due)
                assert expired is not None
                assert expired.status == WaitlistEntryStatus.EXPIRED.value
                assert expired.offer_expires_at is None
                # Both SURVIVE the transition deliberately: the token so her SMS
                # link still answers design row E (`expired`) instead of the
                # invalid state, and the instant so that answer can name the slot.
                assert expired.offer_token_hash == due_hash
                assert expired.offer_starts_at == SLOT
                still_live = await REPO.by_id(session, tenant_id, live)
                assert still_live is not None
                assert still_live.status == WaitlistEntryStatus.OFFERED.value
        finally:
            await engine.dispose()

    _run(check)


def test_close_offer_can_return_an_unsent_offer_to_waiting(app_role_url: str) -> None:
    """D7: the offer clock does not run on an SMS that never left. The same
    statement, a different destination — and the row is re-offerable, which is
    what makes the provider-outage loop self-healing rather than a queue burn."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id)
            await _offer(factory, tenant_id, entry_id, token_hash=_hash("hash-unsent"))
            async with tenant_session(factory, tenant_id) as session:
                await REPO.close_offer(
                    session, tenant_id, [entry_id], status=WaitlistEntryStatus.WAITING.value
                )
            async with tenant_session(factory, tenant_id) as session:
                returned = await REPO.by_id(session, tenant_id, entry_id)
                assert returned is not None
                assert returned.status == WaitlistEntryStatus.WAITING.value
                # NOTHING about the dead offer survives on a row that holds
                # nothing: the manage column would otherwise render a phantom
                # hold, and the undelivered token has no page state to answer.
                assert returned.offer_token_hash is None
                assert returned.offer_expires_at is None
                assert returned.offer_starts_at is None
            assert await _offer(factory, tenant_id, entry_id, token_hash=_hash("hash-retry"))
        finally:
            await engine.dispose()

    _run(check)


def test_the_claim_guard_refuses_an_expired_offer_and_a_second_claim(app_role_url: str) -> None:
    """D4 step 2 — the statement that decides claim-vs-claim AND
    expiry-vs-late-claim. An expired deadline is refused by the DATABASE's own
    comparison, not by a Python `if` the caller could forget."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            live = await _insert(factory, tenant_id, phone="+972501111111")
            stale = await _insert(factory, tenant_id, phone="+972502222222")
            await _offer(factory, tenant_id, live, token_hash=_hash("hash-live"))
            await _offer(
                factory,
                tenant_id,
                stale,
                token_hash=_hash("hash-stale"),
                expires_at=NOW - datetime.timedelta(seconds=1),
            )
            async with tenant_session(factory, tenant_id) as session:
                assert await REPO.claim(session, tenant_id, live, now=NOW)
            async with tenant_session(factory, tenant_id) as session:
                assert not await REPO.claim(session, tenant_id, live, now=NOW)
                assert not await REPO.claim(session, tenant_id, stale, now=NOW)
                claimed = await REPO.by_id(session, tenant_id, live)
                assert claimed is not None
                assert claimed.status == WaitlistEntryStatus.CLAIMED.value
                # The `status='offered'` guard above is what refused the second
                # claim — the hash SURVIVES, so design row D (a lookup on a
                # claimed entry) is reachable.
                assert claimed.offer_token_hash is not None
        finally:
            await engine.dispose()

    _run(check)


def test_waiting_pairs_skips_a_pair_that_already_holds_a_live_offer(app_role_url: str) -> None:
    """The NOT EXISTS half IS "sequential, one at a time, no broadcast" (#13).
    Two brides waiting on one (day, type): once the first is offered the pair
    stops being a candidate, and it becomes one again the moment that offer
    resolves."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()
    other_type = uuid.uuid4()

    async def check() -> None:
        try:
            first = await _insert(factory, tenant_id, type_id=type_id, phone="+972501111111")
            await _insert(factory, tenant_id, type_id=type_id, phone="+972502222222")
            await _insert(factory, tenant_id, type_id=other_type, phone="+972503333333")
            async with tenant_session(factory, tenant_id) as session:
                pairs = await REPO.waiting_pairs(session, tenant_id, from_day=DAY)
                assert sorted(pairs) == sorted([(DAY, type_id), (DAY, other_type)])
            await _offer(factory, tenant_id, first, token_hash=_hash("hash-first"))
            async with tenant_session(factory, tenant_id) as session:
                pairs = await REPO.waiting_pairs(session, tenant_id, from_day=DAY)
                assert pairs == [(DAY, other_type)]
                # And a past day is never a candidate, for the reason
                # list_active floors its range: the slot is unbookable.
                assert (
                    await REPO.waiting_pairs(
                        session, tenant_id, from_day=DAY + datetime.timedelta(days=1)
                    )
                    == []
                )
        finally:
            await engine.dispose()

    _run(check)


def test_waiting_pairs_is_capped_so_one_tick_cannot_walk_the_whole_window(
    app_role_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The expiry half has `_EXPIRY_BATCH_SIZE`; the issue half needs its own.

    Every pair this returns costs the cascade a day-grid materialization AND an
    `offer` UPDATE that row-locks its entry until the whole tick commits, all in
    ONE transaction — so an uncapped walk (SLOT_WINDOW_MAX_DAYS+1 days times the
    type count, which one verified phone can fill) blocks a bride's claim POST
    and every later tenant's drain and sweep behind it.

    Patched down rather than seeded past 50: the assertion is that the LIMIT is
    applied, and 51 rows would test Postgres.
    """
    monkeypatch.setattr("app.db.repositories.waitlist_entries.ISSUE_BATCH_SIZE", 1)
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _insert(factory, tenant_id, type_id=uuid.uuid4(), phone="+972501111111")
            await _insert(factory, tenant_id, type_id=uuid.uuid4(), phone="+972502222222")
            async with tenant_session(factory, tenant_id) as session:
                assert len(await REPO.waiting_pairs(session, tenant_id, from_day=DAY)) == 1
        finally:
            await engine.dispose()

    _run(check)


def test_offered_instants_counts_the_live_offers_on_one_day(app_role_url: str) -> None:
    """The cascade's cross-TYPE guard. `waiting_pairs` keys on (day, type) but
    `day_slots` is type-agnostic, so the only record that an instant is already
    spoken for is the live `offered` rows themselves — counted, not collected,
    because a two-seat instant can carry two offers without being a broadcast."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            first = await _insert(factory, tenant_id, type_id=uuid.uuid4(), phone="+972501111111")
            second = await _insert(factory, tenant_id, type_id=uuid.uuid4(), phone="+972502222222")
            waiting = await _insert(factory, tenant_id, type_id=uuid.uuid4(), phone="+972503333333")
            async with tenant_session(factory, tenant_id) as session:
                assert await REPO.offered_instants(session, tenant_id, day=DAY) == {}
            await _offer(factory, tenant_id, first, token_hash=_hash("hash-first"))
            await _offer(factory, tenant_id, second, token_hash=_hash("hash-second"))
            async with tenant_session(factory, tenant_id) as session:
                assert await REPO.offered_instants(session, tenant_id, day=DAY) == {SLOT: 2}
                # A `waiting` row holds nothing, and another day is another grid.
                assert await REPO.by_id(session, tenant_id, waiting) is not None
                assert (
                    await REPO.offered_instants(
                        session, tenant_id, day=DAY + datetime.timedelta(days=1)
                    )
                    == {}
                )
        finally:
            await engine.dispose()

    _run(check)


def test_oldest_waiting_is_fifo_and_ignores_the_offered_row(app_role_url: str) -> None:
    """#14, by join time. The already-offered bride is not the answer twice —
    she has left `waiting`, so the next tick after her offer resolves picks the
    bride behind her."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            first = await _insert(factory, tenant_id, type_id=type_id, phone="+972501111111")
            second = await _insert(factory, tenant_id, type_id=type_id, phone="+972502222222")
            async with tenant_session(factory, tenant_id) as session:
                oldest = await REPO.oldest_waiting(
                    session, tenant_id, day=DAY, appointment_type_id=type_id
                )
                assert oldest is not None
                assert oldest.id == first
            await _offer(factory, tenant_id, first, token_hash=_hash("hash-first"))
            async with tenant_session(factory, tenant_id) as session:
                oldest = await REPO.oldest_waiting(
                    session, tenant_id, day=DAY, appointment_type_id=type_id
                )
                assert oldest is not None
                assert oldest.id == second
        finally:
            await engine.dispose()

    _run(check)


def test_the_owner_cancel_now_also_takes_an_offered_entry_and_clears_its_deadline(
    app_role_url: str,
) -> None:
    """D8's widened guard, at the repository. The deadline goes; the token hash
    stays. `claim` guards `status='offered'`, so a cancelled row cannot be
    claimed off a stale link whatever its hash says, and keeping the hash is what
    makes design row G — a LOOKUP on `cancelled` — answer «ויתרת על ההצעה»
    instead of «הקישור אינו תקין»."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id)
            offered_hash = _hash("hash-offered")
            await _offer(factory, tenant_id, entry_id, token_hash=offered_hash)
            async with tenant_session(factory, tenant_id) as session:
                cancelled = await REPO.cancel(session, tenant_id, entry_id)
                assert cancelled is not None
                assert cancelled.status == WaitlistEntryStatus.CANCELLED.value
                assert cancelled.offer_token_hash == offered_hash
                assert cancelled.offer_expires_at is None
        finally:
            await engine.dispose()

    _run(check)


def test_an_offer_token_is_invisible_across_tenants(app_role_url: str) -> None:
    """`idx_waitlist_entries_offer_token` is GLOBAL — it has to be, because
    `/w/{token}` resolves a tenant FROM the token. RLS is what keeps that safe:
    inside tenant B's session, tenant A's token answers None, which is the same
    indistinguishable 404 an invented token gets. The HTTP face of this is
    test_waitlist_offer_token.py; the repository face is here."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    token_hash = _hash("hash-cross-tenant")

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_a)
            await _offer(factory, tenant_a, entry_id, token_hash=token_hash)
            async with tenant_session(factory, tenant_a) as session:
                mine = await REPO.by_offer_token_hash(session, token_hash)
                assert mine is not None
                assert mine.id == entry_id
            async with tenant_session(factory, tenant_b) as session:
                assert await REPO.by_offer_token_hash(session, token_hash) is None
                assert not await REPO.claim(session, tenant_b, entry_id, now=NOW)
        finally:
            await engine.dispose()

    _run(check)
