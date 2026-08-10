import datetime
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.constants import WaitlistEntryStatus
from app.models.waitlist_entry import WaitlistEntry

# One tenant's due offers in one tick. `DepositSweeper`'s SWEEP_BATCH_SIZE with
# the same reasoning: an unbounded expiry UPDATE on a table nobody has purged is
# the shape that turns one bad night into a lock storm. Anything left over is
# still due sixty seconds later.
_EXPIRY_BATCH_SIZE = 200

# The ISSUE half's ceiling, and it exists for `_EXPIRY_BATCH_SIZE`'s reason one
# step further: every pair this returns costs the cascade a day-grid
# materialization AND an `offer` UPDATE that row-locks its entry until the whole
# tick commits. Uncapped, one phone on SLOT_WINDOW_MAX_DAYS+1 days times the
# type count is ~1,200 grids inside a single transaction — a bride's claim POST
# blocks behind it, and every later tenant's drain and sweep queue behind that.
#
# A LIMIT rotates fairly on its own and needs no cursor: a pair that gets an
# offer drops out of the `NOT EXISTS` below for the whole window, so the next
# tick's first N are different pairs.
_ISSUE_BATCH_SIZE = 50

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

        **The deadline is cleared, the token hash is KEPT.** Clearing the hash
        would be a belt on braces that were never loose — `claim` below guards
        `status = 'offered'`, so a cancelled row cannot be claimed off a stale
        link whatever its hash says — and it costs the product design row G:
        "declined | decline 200, **or lookup on `cancelled`**". A bride who
        re-opens her SMS link after declining, or after the owner cancelled her,
        must read «ויתרת על ההצעה» and not «הקישור אינו תקין». The hash is a
        sha256 of 32 random bytes the caller must already possess, so keeping it
        hands a prober nothing.

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
        sent, `waiting` for one whose SMS never left (D7) — and the two clear
        DIFFERENT columns. Both clear the deadline.

        **`expired` KEEPS the token hash**, for `claim` and `cancel`'s reason and
        because expiry is the most common end of an offer. Her SMS thread is the
        only artefact she has: clearing the hash made `/w/{token}` 404 into
        «הקישור אינו תקין» from the first sweep after the deadline — about a
        minute — so design row E («תוקף ההצעה הזו פג» + the rebook CTA) was
        reachable only in `_view`'s pre-sweep projection and never in production.
        Nothing is loosened by keeping it: `claim` guards `status = 'offered'`,
        so an expired row cannot be claimed off a stale link.

        **`waiting` clears everything the dead offer wrote**, `offer_starts_at`
        included. The row holds no instant any more, and design §4's offer column
        renders whatever that column says — a survivor is a phantom hold on a
        slot the owner should be booking directly. Her token goes too: it was
        never delivered (that IS D7's condition) and a `waiting` row has no
        designed page state. The next tick writes both afresh when it re-offers.

        Empty input short-circuits: an UPDATE with `IN ()` is legal but pointless
        and the steady state is empty.
        """
        if not entry_ids:
            return []
        values: dict[str, str | None] = {"status": status, "offer_expires_at": None}
        if status == WaitlistEntryStatus.WAITING.value:
            values["offer_token_hash"] = None
            values["offer_starts_at"] = None
        stmt = (
            update(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.id.in_(entry_ids),
                WaitlistEntry.status == WaitlistEntryStatus.OFFERED.value,
                WaitlistEntry.deleted_at.is_(None),
            )
            .values(**values)
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

        **The token hash SURVIVES the transition**, for `cancel`'s reason. The
        guard above is what stops a second delivery of the same SMS from booking
        twice — it matches zero rows and the loser is TOLD `claimed` — and
        clearing the hash on top of it only cost design row D: "already claimed
        by you | lookup 200, `claimed`". A bride re-opening her SMS link half an
        hour after booking has that thread as her only artefact, and it must
        answer «התור הזה כבר נקבע.» rather than «הקישור אינו תקין».
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
            .values(status=WaitlistEntryStatus.CLAIMED.value)
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
        log read the same twice. Capped at `_ISSUE_BATCH_SIZE`: see that
        constant for why an uncapped walk is a tick that holds locks for
        everybody else.
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
            .limit(_ISSUE_BATCH_SIZE)
        )
        return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]

    async def offered_instants(
        self, session: AsyncSession, tenant_id: UUID, *, day: datetime.date
    ) -> dict[datetime.datetime, int]:
        """How many LIVE offers already name each instant on this day.

        `waiting_pairs`' `NOT EXISTS` keys on `(day, appointment_type_id)`, but
        `day_slots` is type-AGNOSTIC — one grid per day for every type — so two
        pairs on the same day walk the same grid and, without this, pick the same
        earliest free slot and text two brides about one seat (#13's "no
        broadcast" is a claim about instants, not about pairs). The `offered`
        rows are the record: `offer_starts_at` IS the instant held.

        Counted rather than collected as a set, because a slot's capacity may be
        more than one and two offers on a two-seat instant are two seats, not a
        double-book. The caller compares against `Slot.remaining`.

        No deadline predicate: the cascade expires due offers before it issues,
        in the same transaction, so every surviving `offered` row is live.
        """
        stmt = (
            select(WaitlistEntry.offer_starts_at, func.count())
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.day == day,
                WaitlistEntry.status == WaitlistEntryStatus.OFFERED.value,
                WaitlistEntry.offer_starts_at.is_not(None),
                WaitlistEntry.deleted_at.is_(None),
            )
            .group_by(WaitlistEntry.offer_starts_at)
        )
        return {row[0]: row[1] for row in (await session.execute(stmt)).all()}

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
