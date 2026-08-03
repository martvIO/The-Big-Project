import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Insert, func, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fitting_assignment_dress import FittingAssignmentDress


class FittingAssignmentDressesRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defence-in-depth (house pattern — see `FittingRoomsRepository`)."""

    async def add(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        assignment_id: uuid.UUID,
        dress_id: uuid.UUID,
        dress_name: str,
        dress_size: str | None,
    ) -> tuple[bool, FittingAssignmentDress]:
        """A concurrent double-add is a SUCCESS, not a 409: two staffers tapping
        «שמלה 47» at the same instant both want the dress in the room, and the
        dress is in the room. Telling the second she lost a race would be telling
        her she was wrong when she was right.

        ⚠ **`DO UPDATE`, not `DO NOTHING`, and the difference is a silent lost
        update.** With `DO NOTHING`: T1 soft-deletes binding B (uncommitted); T2
        adds the same dress, conflicts against the still-live B, does nothing and
        answers 200 «נוספה»; T1 commits. The dress is OUT of the room and the
        staffer who put it in was told it went in — no error, no index able to
        say so. `DO UPDATE` BLOCKS on T1's uncommitted delete; when T1 commits,
        ON CONFLICT's re-check finds the row no longer in the partial index and
        the add re-inserts cleanly. The rule, stated once: an add and a remove of
        the same dress serialise on the binding row, and the later commit wins.

        The SET target is `updated_at` because a DO UPDATE must set something and
        this is the only column whose value nothing renders — the BEFORE UPDATE
        trigger rewrites it to `now()` regardless, so the statement's effect is
        its BLOCKING, not its assignment. In particular the snapshots
        (`dress_name`, `dress_size`) are deliberately NOT overwritten: what the
        room was given must not be rewritten by a second tap.

        `(xmax = 0)` is the `(wrote, row)` discriminator — true only on a real
        insert. No IntegrityError, therefore no aborted transaction, therefore no
        savepoint on this path: the claim needs one because it must REPORT the
        conflict, and this one must not.
        """
        stmt: Insert = (
            pg_insert(FittingAssignmentDress)
            .values(
                tenant_id=tenant_id,
                fitting_room_assignment_id=assignment_id,
                dress_id=dress_id,
                dress_name=dress_name,
                dress_size=dress_size,
            )
            .on_conflict_do_update(
                index_elements=[
                    FittingAssignmentDress.tenant_id,
                    FittingAssignmentDress.fitting_room_assignment_id,
                    FittingAssignmentDress.dress_id,
                ],
                index_where=FittingAssignmentDress.deleted_at.is_(None),
                set_={"updated_at": func.now()},
            )
            .returning(FittingAssignmentDress, literal_column("(xmax = 0)").label("inserted"))
        )
        row = (await session.execute(stmt)).one()
        return bool(row.inserted), row[0]

    async def remove(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        assignment_id: uuid.UUID,
        binding_id: uuid.UUID,
        actor_id: uuid.UUID,
        at: datetime,
    ) -> bool:
        """A soft delete stamping `deleted_at` AND `removed_by`, and that pair IS
        the audit record — which is why no FITTING_DRESS_REMOVED action exists.
        Without the actor the row answers what left the room and when, and cannot
        answer who took it out.

        `assignment_id` is in the predicate as well as `binding_id`: the route
        addresses a binding through its assignment, and a binding id belonging to
        a different assignment must be one indistinguishable miss rather than a
        cross-assignment write. `deleted_at IS NULL` makes a second call answer
        False instead of re-stamping — which also means the second of two racing
        removes does not overwrite the first remover's name.
        """
        stmt = (
            update(FittingAssignmentDress)
            .where(
                FittingAssignmentDress.tenant_id == tenant_id,
                FittingAssignmentDress.id == binding_id,
                FittingAssignmentDress.fitting_room_assignment_id == assignment_id,
                FittingAssignmentDress.deleted_at.is_(None),
            )
            .values(deleted_at=at, removed_by=actor_id)
            .returning(FittingAssignmentDress.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def by_id_any_state(
        self, session: AsyncSession, tenant_id: uuid.UUID, binding_id: uuid.UUID
    ) -> FittingAssignmentDress | None:
        """The removed row read back, and the ONLY method here that does not
        filter `deleted_at`. It exists because the soft delete is the audit
        record: something has to be able to read it."""
        stmt = (
            select(FittingAssignmentDress)
            .where(
                FittingAssignmentDress.tenant_id == tenant_id,
                FittingAssignmentDress.id == binding_id,
            )
            .execution_options(populate_existing=True)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_assignment_ids(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_ids: Sequence[uuid.UUID],
    ) -> dict[uuid.UUID, list[FittingAssignmentDress]]:
        """The payload's SECOND statement, grouped so `from_rows` stays a pure
        renderer. Empty input short-circuits with no round trip at all — an
        unoccupied boutique polls every five seconds and must not pay for it.

        Rides idx_fitting_assignment_dresses_assignment. Keys are present only
        for assignments that HAVE live bindings, so the caller reads with
        `.get(id, [])`.
        """
        if not assignment_ids:
            return {}
        stmt = (
            select(FittingAssignmentDress)
            .where(
                FittingAssignmentDress.tenant_id == tenant_id,
                FittingAssignmentDress.fitting_room_assignment_id.in_(assignment_ids),
                FittingAssignmentDress.deleted_at.is_(None),
            )
            .order_by(FittingAssignmentDress.created_at, FittingAssignmentDress.id)
        )
        grouped: dict[uuid.UUID, list[FittingAssignmentDress]] = {}
        for row in (await session.execute(stmt)).scalars().all():
            grouped.setdefault(row.fitting_room_assignment_id, []).append(row)
        return grouped
