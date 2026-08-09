import datetime
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.constants import WaitlistEntryStatus
from app.models.waitlist_entry import WaitlistEntry

# One tenant's due offers in one tick. `DepositSweeper`'s SWEEP_BATCH_SIZE with
# the same reasoning: an unbounded expiry UPDATE on a table nobody has purged is
# the shape that turns one bad night into a lock storm. Anything left over is
# still due sixty seconds later.
_EXPIRY_BATCH_SIZE = 200

# The two states the active-unique index predicate names — "on the list" as far
# as the join's dedup and the manage list are concerned. Spelled once here so
# by_active_tuple and list_active cannot drift from each other, though the INDEX
# predicate is the one the database enforces.
_ACTIVE = (WaitlistEntryStatus.WAITING.value, WaitlistEntryStatus.OFFERED.value)


class WaitlistEntriesRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see CustomersRepository)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        day: datetime.date,
        appointment_type_id: UUID,
        phone: str,
    ) -> WaitlistEntry:
        """`status` is left to its DB default — F22's join writes no transition,
        and `created_at` is the column default because it is the FIFO sort key:
        a caller-supplied one would let a client choose its own place in line.

        The active-unique index makes the duplicate tuple an IntegrityError; the
        SERVICE owns that branch (re-read, same 201) because the answer is a
        product decision, not a storage one.
        """
        row = WaitlistEntry(
            tenant_id=tenant_id,
            day=day,
            appointment_type_id=appointment_type_id,
            phone=phone,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def by_active_tuple(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        phone: str,
        day: datetime.date,
        appointment_type_id: UUID,
    ) -> WaitlistEntry | None:
        """The IntegrityError re-read: exactly the unique index's key and
        predicate, so the row that refused the INSERT is the row this answers."""
        stmt = select(WaitlistEntry).where(
            WaitlistEntry.tenant_id == tenant_id,
            WaitlistEntry.phone == phone,
            WaitlistEntry.day == day,
            WaitlistEntry.appointment_type_id == appointment_type_id,
            WaitlistEntry.status.in_(_ACTIVE),
            WaitlistEntry.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_active(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        day: datetime.date | None = None,
        from_day: datetime.date | None = None,
    ) -> Sequence[WaitlistEntry]:
        """The manage list: active entries, `(day, created_at)` — FIFO visible
        as row order, which IS the position (D5: computed nowhere, returned to
        no one). `day` filters one day; otherwise `from_day` floors the range
        (the service passes today, hiding dead past-day rows the retention
        sweep owns). `, id` breaks a created_at tie so two reads cannot
        transpose two rows."""
        stmt = select(WaitlistEntry).where(
            WaitlistEntry.tenant_id == tenant_id,
            WaitlistEntry.status.in_(_ACTIVE),
            WaitlistEntry.deleted_at.is_(None),
        )
        if day is not None:
            stmt = stmt.where(WaitlistEntry.day == day)
        elif from_day is not None:
            stmt = stmt.where(WaitlistEntry.day >= from_day)
        stmt = stmt.order_by(WaitlistEntry.day, WaitlistEntry.created_at, WaitlistEntry.id)
        return list((await session.execute(stmt)).scalars().all())

    async def cancel(
        self, session: AsyncSession, tenant_id: UUID, entry_id: UUID
    ) -> WaitlistEntry | None:
        """The guarded UPDATE — `WHERE status IN ('waiting','offered')`, F23 D8's
        widening of F22's `waiting`-only guard. Rowcount 0 has two causes the
        service tells apart with `by_id`: gone/foreign (404) and already-terminal
        (the idempotent double-tap, answered with the row as-is).

        The offer half of the row is cleared with the transition, for the same
        reason `scheduled_messages` clears `manage_token` on every terminal
        status: a live offer token outliving the entry it authorises would let a
        bride claim a seat off a list she has been taken off.

        `synchronize_session=False`: the WHERE is not Python-evaluable and no
        caller reads an identity-mapped instance afterwards — the entity is
        re-read fresh below. `updated_at` is the trigger's."""
        stmt = (
            update(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.id == entry_id,
                WaitlistEntry.status.in_(_ACTIVE),
                WaitlistEntry.deleted_at.is_(None),
            )
            .values(
                status=WaitlistEntryStatus.CANCELLED.value,
                offer_token_hash=None,
                offer_expires_at=None,
            )
            .returning(WaitlistEntry.id)
            .execution_options(synchronize_session=False)
        )
        cancelled = (await session.execute(stmt)).scalar_one_or_none()
        if cancelled is None:
            return None
        return await self.by_id(session, tenant_id, cancelled)

    # --- F23: the offer lifecycle ------------------------------------------

    async def offer(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        entry_id: UUID,
        *,
        now: datetime.datetime,
        starts_at: datetime.datetime,
        expires_at: datetime.datetime,
        token_hash: str,
    ) -> bool:
        """D3 statement 1: `waiting -> offered`, guarded, atomic, lock-free.

        Returns whether the row moved. Zero rows means another worker offered
        this entry between this tick's read and this write — the cascade skips
        the pair and says nothing. **This one guarded predicate IS the
        cascade-vs-cascade race answer**; there is no advisory lock here and
        none is wanted, because losing is a no-op rather than an error.
        """
        stmt = (
            update(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.id == entry_id,
                WaitlistEntry.status == WaitlistEntryStatus.WAITING.value,
                WaitlistEntry.deleted_at.is_(None),
            )
            .values(
                status=WaitlistEntryStatus.OFFERED.value,
                offered_at=now,
                offer_starts_at=starts_at,
                offer_expires_at=expires_at,
                offer_token_hash=token_hash,
            )
            .returning(WaitlistEntry.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def due_offers(
        self, session: AsyncSession, tenant_id: UUID, *, now: datetime.datetime
    ) -> Sequence[WaitlistEntry]:
        """The entries whose offer deadline has passed, read BEFORE the
        transition so the caller can still see each one's `offer_expires_at`.

        A plain SELECT, not `FOR UPDATE`: `expire` below re-asserts
        `status = 'offered'` in its own WHERE, so a claim that commits between
        this read and that write simply makes the transition match nothing. A
        lock here would only move the same arbitration earlier and would block
        behind an in-flight claim for no gain.
        """
        stmt = (
            select(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.status == WaitlistEntryStatus.OFFERED.value,
                WaitlistEntry.offer_expires_at <= now,
                WaitlistEntry.deleted_at.is_(None),
            )
            .order_by(WaitlistEntry.offer_expires_at)
            .limit(_EXPIRY_BATCH_SIZE)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def close_offer(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        entry_ids: Sequence[UUID],
        *,
        status: str,
    ) -> list[UUID]:
        """The expiry transition, `DepositSweeper._expire_holds`'s shape: bulk,
        guarded on `status = 'offered'`, answer read off RETURNING.

        `status` is the destination — `expired` for an offer that was really
        sent, `waiting` for one whose SMS never left (D7). Both clear the token
        and the deadline; `offer_starts_at` deliberately survives so the manage
        column can still say what was offered until the next tick overwrites it.

        Empty input short-circuits: an UPDATE with `IN ()` is legal but pointless
        and the steady state is empty.
        """
        if not entry_ids:
            return []
        stmt = (
            update(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.id.in_(entry_ids),
                WaitlistEntry.status == WaitlistEntryStatus.OFFERED.value,
                WaitlistEntry.deleted_at.is_(None),
            )
            .values(status=status, offer_token_hash=None, offer_expires_at=None)
            .returning(WaitlistEntry.id)
            .execution_options(synchronize_session=False)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def by_offer_token_hash(
        self, session: AsyncSession, token_hash: str
    ) -> WaitlistEntry | None:
        """The `/w/{token}` lookup — and the ONE repository method with no
        tenant_id predicate, because the caller has no tenant yet: the token IS
        the tenant resolution. `idx_waitlist_entries_offer_token` is global for
        the same reason.

        Tenancy is still enforced, by RLS: this runs inside the storefront's
        host-resolved `tenant_session`, so a token minted for another boutique
        is filtered out by the policy and answers None — the same
        indistinguishable 404 an invented token gets.
        """
        stmt = select(WaitlistEntry).where(
            WaitlistEntry.offer_token_hash == token_hash,
            WaitlistEntry.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def claim(
        self, session: AsyncSession, tenant_id: UUID, entry_id: UUID, *, now: datetime.datetime
    ) -> bool:
        """D4 step 2, and the single most important statement in the feature.

        `WHERE status = 'offered' AND offer_expires_at > now` decides BOTH the
        claim-vs-claim race and the expiry-vs-late-claim race, in one round trip,
        with no lock. Zero rows means somebody or something else already moved
        the row; the SERVICE re-reads it to say which.

        The token hash is cleared here so a second delivery of the same SMS
        cannot even resolve the row — belt to the guard's braces.
        """
        stmt = (
            update(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.id == entry_id,
                WaitlistEntry.status == WaitlistEntryStatus.OFFERED.value,
                WaitlistEntry.offer_expires_at > now,
                WaitlistEntry.deleted_at.is_(None),
            )
            .values(status=WaitlistEntryStatus.CLAIMED.value, offer_token_hash=None)
            .returning(WaitlistEntry.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def waiting_pairs(
        self, session: AsyncSession, tenant_id: UUID, *, from_day: datetime.date
    ) -> Sequence[tuple[datetime.date, UUID]]:
        """D2 step 3: the distinct `(day, appointment_type_id)` pairs that have a
        `waiting` entry and NO live offer.

        **The `NOT EXISTS` half is the whole "sequential, one at a time, no
        broadcast" decision (#13)**, spelled as a predicate rather than as a
        counter the cascade would have to maintain. It is also what makes the
        cascade idempotent across ticks: a pair holding an `offered` entry is
        simply not a candidate until that offer resolves.

        Ordered so two workers walk the pairs in the same sequence — not
        required for correctness (the guarded UPDATE arbitrates) but it makes a
        log read the same twice.
        """
        live_offer = aliased(WaitlistEntry, name="live_offer")
        offered = (
            select(live_offer.id)
            .where(
                live_offer.tenant_id == tenant_id,
                live_offer.day == WaitlistEntry.day,
                live_offer.appointment_type_id == WaitlistEntry.appointment_type_id,
                live_offer.status == WaitlistEntryStatus.OFFERED.value,
                live_offer.deleted_at.is_(None),
            )
            .exists()
        )
        stmt = (
            select(WaitlistEntry.day, WaitlistEntry.appointment_type_id)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.day >= from_day,
                WaitlistEntry.status == WaitlistEntryStatus.WAITING.value,
                WaitlistEntry.deleted_at.is_(None),
                ~offered,
            )
            .distinct()
            .order_by(WaitlistEntry.day, WaitlistEntry.appointment_type_id)
        )
        return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]

    async def oldest_waiting(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        day: datetime.date,
        appointment_type_id: UUID,
    ) -> WaitlistEntry | None:
        """FIFO by join time (#14). `, id` breaks a `created_at` tie so two ticks
        cannot pick two different brides for one pair — `list_active` orders the
        same way for the same reason."""
        stmt = (
            select(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.day == day,
                WaitlistEntry.appointment_type_id == appointment_type_id,
                WaitlistEntry.status == WaitlistEntryStatus.WAITING.value,
                WaitlistEntry.deleted_at.is_(None),
            )
            .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
            .limit(1)
        )
        return (await session.execute(stmt)).scalars().first()

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, entry_id: UUID
    ) -> WaitlistEntry | None:
        stmt = select(WaitlistEntry).where(
            WaitlistEntry.tenant_id == tenant_id,
            WaitlistEntry.id == entry_id,
            WaitlistEntry.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()
