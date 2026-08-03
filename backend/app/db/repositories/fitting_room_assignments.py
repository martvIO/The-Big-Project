import uuid
from datetime import datetime

from sqlalchemy import exists, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fitting_room_assignment import FittingRoomAssignment

# The two partial unique index names, declared ONCE here and imported by the
# service, so a rename in the migration cannot silently drift away from the
# branch that reads it. They are the discriminator for WHICH 409 to raise and
# nothing else: idempotence is resolved first, keyed on the REQUEST, because a
# re-claim of the room she already holds violates both indexes at once and
# Postgres reports whichever has the lower OID — i.e. migration creation order,
# which flips after any REINDEX CONCURRENTLY or pg_repack.
ROOM_ACTIVE_INDEX = "idx_fitting_room_assignments_room_active"
STAFF_ACTIVE_INDEX = "idx_fitting_room_assignments_staff_active"


def violated_index(error: IntegrityError) -> str | None:
    """The name of the unique index a failed write violated, or None.

    ⚠ **It is NOT `error.orig.constraint_name`, and the spec says it is.**
    `error.orig` is SQLAlchemy's own `AsyncAdapt_asyncpg_dbapi.IntegrityError`,
    constructed as `Error("%s: %s" % (type(error), error))` and then raised
    `from` the asyncpg exception — a brand-new object carrying a formatted
    STRING and two pgcode attributes, and nothing else. It has no
    `constraint_name`, so `getattr(error.orig, "constraint_name", None)` is
    `None` for every violation there has ever been. Written that way, the claim's
    discriminator takes its unrecognised-constraint branch every single time and
    a room conflict answers **500 instead of 409** — the whole of D3, D6 and D8's
    error design silently unreachable, with the happy path green.

    asyncpg's own `UniqueViolationError` is the one that carries
    `constraint_name`, and it survives as `orig.__cause__`.

    Spelled defensively at both hops: a `None` at either reads as unrecognised
    and lets the caller re-raise, which is the right answer for a violation
    nobody predicted. Mapping an unknown constraint to ROOM_OCCUPIED would tell a
    staffer a lie about furniture.
    """
    return getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)


class FittingRoomAssignmentsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defence-in-depth (house pattern — see `FittingRoomsRepository` for what that
    redundancy is and is not proved by)."""

    async def claim(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        room_id: uuid.UUID,
        staff_id: uuid.UUID,
        booking_id: uuid.UUID | None,
    ) -> FittingRoomAssignment:
        """One INSERT. No advisory lock, and the absence is the design.

        F13's `pg_advisory_xact_lock` guards a read-then-write — it claims "the
        lowest free seat", so the value inserted is derived from a count of
        existing rows and only a lock makes that atomic. A fitting room has no
        seat to number: this inserts three values the caller already holds,
        derives nothing, and the statement either violates a unique index or it
        does not. A lock here would serialise every claim in the boutique behind
        every other and turn an immediate refusal into a wait that ends in the
        same refusal — and a staffer standing in a corridor is better served by
        an immediate 409 naming the occupant.

        F51's advisory lock is not the precedent either: its invariant is "AT
        LEAST ONE owner", which no index can express because an index expresses
        at most one of something. F36's invariant is "at most one", which is
        exactly and only what a unique index says.

        ⚠ **A CORE `session.execute(insert(...))`, never `session.add`, and that
        is load-bearing.** With `session.add` the flush happens inside
        `AsyncSessionTransaction.__aexit__`, so the `IntegrityError` surfaces
        when the savepoint block EXITS and a `try` placed inside it catches
        nothing. This raises from the execute, where the caller's `try` — placed
        OUTSIDE its `async with session.begin_nested()` — can see it.

        This repository raises. The SAVEPOINT is the service's, because only the
        service needs the outer transaction alive afterwards to read the occupant
        the 409 has to name.
        """
        stmt = (
            insert(FittingRoomAssignment)
            .values(
                tenant_id=tenant_id,
                fitting_room_id=room_id,
                staff_user_id=staff_id,
                booking_id=booking_id,
            )
            .returning(FittingRoomAssignment)
        )
        return (await session.execute(stmt)).scalars().one()

    async def active_for(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> FittingRoomAssignment | None:
        """The idempotence read, and it is keyed on the REQUEST — never on the
        constraint name. A hit means "you already have this room": 200 with that
        card, no audit row, deterministic whichever index happened to fire."""
        stmt = select(FittingRoomAssignment).where(
            FittingRoomAssignment.tenant_id == tenant_id,
            FittingRoomAssignment.fitting_room_id == room_id,
            FittingRoomAssignment.staff_user_id == staff_id,
            FittingRoomAssignment.released_at.is_(None),
            FittingRoomAssignment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(
        self, session: AsyncSession, tenant_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> FittingRoomAssignment | None:
        """⚠ **`deleted_at IS NULL` only — NO `released_at IS NULL`, and that is
        the release's whole idempotence.**

        The release authorizes on the row's `staff_user_id`, so it must read the
        row before it writes. Filtering `released_at IS NULL` there would make a
        second release read as ABSENT and answer 404 — but she wanted the room
        free and the room is free, so it is a 200. The `(wrote, row)` pair from
        `release()` is what separates "already released" from "never existed";
        this read must not pre-empt that distinction.
        """
        return await self._refreshed(session, tenant_id, assignment_id)

    async def active_by_id(
        self, session: AsyncSession, tenant_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> FittingRoomAssignment | None:
        """The dress routes' read, and it DOES filter `released_at IS NULL`.

        The asymmetry with `by_id` is deliberate and is the error table's: a
        released assignment is a 200 to the release and a 404 to everything else,
        because the fitting is over and nothing more goes into that room.
        """
        stmt = select(FittingRoomAssignment).where(
            FittingRoomAssignment.tenant_id == tenant_id,
            FittingRoomAssignment.id == assignment_id,
            FittingRoomAssignment.released_at.is_(None),
            FittingRoomAssignment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def occupant_of_room(
        self, session: AsyncSession, tenant_id: uuid.UUID, room_id: uuid.UUID
    ) -> FittingRoomAssignment | None:
        """Who is in this room — the row the ROOM_OCCUPIED 409's `details` comes
        from. `None` is a legitimate answer and not a bug: the loser of a claim
        blocks on the winner's uncommitted index key, and between that commit and
        this read the winner can release. A 409 that names nobody is worse than
        one that says so, which is why `details` is optional on both codes."""
        stmt = select(FittingRoomAssignment).where(
            FittingRoomAssignment.tenant_id == tenant_id,
            FittingRoomAssignment.fitting_room_id == room_id,
            FittingRoomAssignment.released_at.is_(None),
            FittingRoomAssignment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def room_of_staff(
        self, session: AsyncSession, tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> FittingRoomAssignment | None:
        """Which room she is in — the STAFF_OCCUPIED 409's `details`. At most one
        row BY CONSTRUCTION, which is what makes the staff card's `occupied` a
        fact rather than a guess: the derivation never has to pick."""
        stmt = select(FittingRoomAssignment).where(
            FittingRoomAssignment.tenant_id == tenant_id,
            FittingRoomAssignment.staff_user_id == staff_id,
            FittingRoomAssignment.released_at.is_(None),
            FittingRoomAssignment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def has_active_for_room(
        self, session: AsyncSession, tenant_id: uuid.UUID, room_id: uuid.UUID
    ) -> bool:
        """The delete's occupancy guard, and it MUST be issued as its own
        statement AFTER `by_id_for_update` holds the room's row lock — a new
        statement snapshot taken under the lock is what sees the committed claim.
        Folded into the UPDATE as a `NOT EXISTS` subquery it would be evaluated
        against the transaction's snapshot and would be exactly the unsafe shape
        F51's docstring rejects."""
        stmt = select(
            exists().where(
                FittingRoomAssignment.tenant_id == tenant_id,
                FittingRoomAssignment.fitting_room_id == room_id,
                FittingRoomAssignment.released_at.is_(None),
                FittingRoomAssignment.deleted_at.is_(None),
            )
        )
        return bool((await session.execute(stmt)).scalar_one())

    async def release(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        *,
        at: datetime,
    ) -> tuple[bool, FittingRoomAssignment | None]:
        """The conditional UPDATE. `released_at IS NULL` in the predicate makes a
        second release keep the FIRST timestamp instead of moving it.

        `(False, row)` means somebody already released it — she wanted the room
        free and the room is free, so that is a 200 with no audit row, not an
        error. `(False, None)` means gone, and that is the 404.

        `at` is the service's injectable clock rather than SQL `now()`, so the db
        suite can freeze it and assert an equality. `created_at` cannot be
        frozen that way — it is `server_default=text("now()")`, i.e. the DATABASE
        host's transaction-start time — which is why D2 asserts orderings on it
        and equalities only here.
        """
        wrote = await session.execute(
            update(FittingRoomAssignment)
            .where(
                FittingRoomAssignment.tenant_id == tenant_id,
                FittingRoomAssignment.id == assignment_id,
                FittingRoomAssignment.released_at.is_(None),
                FittingRoomAssignment.deleted_at.is_(None),
            )
            .values(released_at=at)
            .returning(FittingRoomAssignment.id)
        )
        refreshed = await self._refreshed(session, tenant_id, assignment_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def handover(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        *,
        new_staff_id: uuid.UUID,
    ) -> tuple[bool, FittingRoomAssignment | None]:
        """ONE statement mutating ONE column, and that is why the dress bindings
        survive for free: release-and-reinsert would have to copy every child
        row, which is a loop, a second failure mode, and a window in which the
        room is momentarily free for a third staffer to take.

        Three consequences, all deliberate. `created_at` does not move, so the
        card's elapsed time stays the CLIENT's time in the room. The assignment
        id is stable, which is what keeps F37's alert pointer correct after the
        room changes hands. And the `(tenant_id, staff_user_id)` index guards the
        RECEIVING staffer — handing a room to a colleague who already holds one
        raises, and the service turns that into a 409 naming her current room.

        ⚠ The caller must capture the OLD `staff_user_id` into a local BEFORE
        calling this. The UPDATE is ORM-enabled DML whose `evaluate`
        synchronization stamps the new value onto the same identity-mapped
        instance, so reading it afterwards records the new staffer as the old one
        and empties the audit row of its entire informational content.
        """
        wrote = await session.execute(
            update(FittingRoomAssignment)
            .where(
                FittingRoomAssignment.tenant_id == tenant_id,
                FittingRoomAssignment.id == assignment_id,
                FittingRoomAssignment.released_at.is_(None),
                FittingRoomAssignment.deleted_at.is_(None),
            )
            .values(staff_user_id=new_staff_id)
            .returning(FittingRoomAssignment.id)
        )
        if wrote.scalar_one_or_none() is None:
            return False, None
        return True, await self._refreshed(session, tenant_id, assignment_id)

    async def _refreshed(
        self, session: AsyncSession, tenant_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> FittingRoomAssignment | None:
        """`StaffUsersRepository._refreshed` applied to this table.

        `populate_existing=True` is the whole mechanism: without it this SELECT
        returns the instance already in the identity map WITHOUT overwriting its
        attributes — i.e. the object the UPDATE just stamped — so the caller
        renders its own intent instead of the database's answer. Applied
        unconditionally rather than per call site, because whether a caller
        happened to load the row first is exactly the reasoning that has bitten
        this repo three times.

        ⚠ **Dropping the flag leaves the repository suite GREEN**, and that is
        recorded rather than hidden: every test in `test_fitting_rooms_repositories.py`
        opens a fresh session per step, so the identity map is empty and the flag
        is a no-op there. What it defends is one session doing the write and the
        re-read — the shipped service's shape — and the loser of a concurrent
        release rendering the winner's timestamp. Mutation performed, green,
        restored; the case that can see it is the forced interleave.

        No `released_at IS NULL` here on purpose: the release path needs the
        just-released row back to render it.
        """
        return (
            await session.execute(
                select(FittingRoomAssignment)
                .where(
                    FittingRoomAssignment.tenant_id == tenant_id,
                    FittingRoomAssignment.id == assignment_id,
                    FittingRoomAssignment.deleted_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
