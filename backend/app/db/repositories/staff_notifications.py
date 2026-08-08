import dataclasses
import uuid
from datetime import datetime

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff_notification import StaffNotification
from app.models.staff_user import StaffUser

RECENT_LIMIT = 20


@dataclasses.dataclass(frozen=True)
class StaffNotificationRow:
    """One panel row: the notification plus the one thing its actor pointer
    resolves to.

    Frozen, and holding the ORM row rather than copying its columns out, so
    there is no second transcription of six fields to drift from the model.

    ⚠ **There is no customer datum here and there is no join that could produce
    one.** The only join in this module is to `staff_users`, for a colleague's
    display name.
    """

    notification: StaffNotification
    # NULL ONLY when the actor's staff row is gone entirely: the join carries no
    # `deleted_at` filter, so a colleague removed after the fact still has a
    # name. The copy has a nameless variant for the remaining case.
    actor_name: str | None


class StaffNotificationsRepository:
    """Tenant-scoped via RLS **and person-scoped by an explicit predicate**, and
    the two are not the same kind of guarantee.

    `tenant_id` beside every statement is redundant defence-in-depth (the house
    pattern — forced RLS already carries tenant isolation). `staff_user_id` is
    NOT redundant: nothing in the database scopes a row to one staffer, so every
    statement here spells it, and dropping it from `mark_read` would let a
    staffer clear a colleague's bell while dropping it from `recent` would put a
    colleague's notifications on her screen.

    Both predicates are on all three methods. There is no method here without a
    `staff_user_id` argument, and that is the design rather than an accident.
    """

    async def insert(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        staff_user_id: uuid.UUID,
        actor_staff_user_id: uuid.UUID,
        kind: str,
        entity_id: uuid.UUID,
    ) -> StaffNotification:
        """ONE plain statement, called inside the PRODUCER's transaction and
        never in one of its own.

        That is the whole delivery guarantee: the notification commits with the
        dispatch or the page, or neither happens. All four call sites sit beside
        an existing `_audit.record` inside the same `tenant_session`, so a
        rolled-back handover leaves no bell row claiming it happened.

        `read_at` is left to the column's NULL rather than passed — unread is the
        absence of a stamp, and the DDL is the single place that is written down.
        """
        stmt = (
            insert(StaffNotification)
            .values(
                tenant_id=tenant_id,
                staff_user_id=staff_user_id,
                actor_staff_user_id=actor_staff_user_id,
                kind=kind,
                entity_id=entity_id,
            )
            .returning(StaffNotification)
        )
        return (await session.execute(stmt)).scalars().one()

    async def unread_count(
        self, session: AsyncSession, tenant_id: uuid.UUID, staff_user_id: uuid.UUID
    ) -> int:
        """⚠ **This predicate is `idx_staff_notifications_unread`'s predicate,
        character for character, and it must stay that way.**

        This is the one statement in the feature that rides the SOS poll's
        payload — the console's only app-wide tick, every 5 seconds, on all 18
        sections, for every signed-in device. It is affordable exactly because it
        is an index-only scan on the partial index and for no other reason. If it
        ever needs a different predicate, it needs a different index, which is a
        new migration and a new review rather than a widened one.
        """
        stmt = select(func.count()).where(
            StaffNotification.tenant_id == tenant_id,
            StaffNotification.staff_user_id == staff_user_id,
            StaffNotification.read_at.is_(None),
            StaffNotification.deleted_at.is_(None),
        )
        return int((await session.execute(stmt)).scalar_one())

    async def recent(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        staff_user_id: uuid.UUID,
        limit: int = RECENT_LIMIT,
    ) -> list[StaffNotificationRow]:
        """Newest first, hard cap, **no cursor and no pagination**.

        The panel's cap note says «the latest 20» on screen, so the number is a
        product statement rather than a page size — a «load more» would be a
        different design, not a parameter.

        ⚠ **The `staff_users` join carries NO `deleted_at` filter**, F37's shipped
        rule handed here verbatim: a colleague removed after the fact still has a
        name, and it is LEFT so a notification whose actor row was swept entirely
        still renders, with a null name and copy that says so. An inner join
        would silently drop the row instead.

        Read rows come back too — the panel shows the last 20 whatever their
        state, and unread is a distinction it draws in the rendering.
        """
        actor = StaffUser
        stmt = (
            select(StaffNotification, actor.display_name)
            .select_from(StaffNotification)
            .outerjoin(
                actor,
                and_(
                    actor.tenant_id == tenant_id,
                    actor.id == StaffNotification.actor_staff_user_id,
                ),
            )
            .where(
                StaffNotification.tenant_id == tenant_id,
                StaffNotification.staff_user_id == staff_user_id,
                StaffNotification.deleted_at.is_(None),
            )
            .order_by(StaffNotification.created_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return [StaffNotificationRow(notification=row[0], actor_name=row[1]) for row in rows]

    async def mark_read(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        staff_user_id: uuid.UUID,
        ids: list[uuid.UUID],
        *,
        at: datetime,
    ) -> int:
        """Stamp, then answer HER OWN unread count.

        ⚠ **`read_at IS NULL` in the predicate is what makes a re-mark
        idempotent** — a retried request, or a row already read on another
        device, writes nothing and the stamp keeps saying when she actually saw
        it. Without it the second mark would move the timestamp forward and the
        column would mean «last time she looked at the panel».

        ⚠ **`staff_user_id` is the whole authorization** and there is no other:
        ids arrive from a request body, so a colleague's id in the list simply
        matches nothing. The answer is still the CALLER's count, because that is
        the number her bell is about to render.

        An empty list skips the UPDATE and still answers — a 200 no-op, which is
        what «she tapped a row that was already read» looks like from here.
        """
        if ids:
            await session.execute(
                update(StaffNotification)
                .where(
                    StaffNotification.tenant_id == tenant_id,
                    StaffNotification.staff_user_id == staff_user_id,
                    StaffNotification.id.in_(ids),
                    StaffNotification.read_at.is_(None),
                    StaffNotification.deleted_at.is_(None),
                )
                .values(read_at=at)
            )
        return await self.unread_count(session, tenant_id, staff_user_id)
