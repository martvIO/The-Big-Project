"""F35's read side: the panel's list and the mark-read write.

⚠ **The module is `app/floor/notifications.py` and NOT `app/notifications/`.**
That package is TAKEN — it is the SMS/OTP module (`NotificationService`, Twilio,
the `test_notifications_*.py` family) — and naming this work `notifications` at
package or test level collides on both. Test files here are `test_bell_*.py`.

**Why a second service class instead of two more methods on `FloorService`.**
`FloorService` is the floor: rooms, dispatch, the queue, the page. It builds
eleven repositories and it is the class every floor verb's transaction lives in.
The bell's reads share nothing with any of them — no room, no ticket, no
customer — and the one place the two features DO meet is the unread count on the
SOS payload, which lives on `FloorService.sos` precisely because it must ride
that verb's existing session.

**The write side is not here.** The four producers are call sites inside
`FloorService`'s own transactions (`service.py`), because a notification that
committed separately from its event would be a bell claiming a dispatch that
rolled back.
"""

import datetime
import uuid
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories.staff_notifications import (
    StaffNotificationRow,
    StaffNotificationsRepository,
)
from app.db.tenant import tenant_session


class NotificationsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._notifications = StaffNotificationsRepository()
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))

    async def recent(self, tenant_id: UUID, *, actor_id: UUID) -> list[StaffNotificationRow]:
        """The panel's whole read: one statement, newest 20, hers alone.

        ⚠ **`actor_id` comes from the session cookie and is never
        request-supplied.** RLS scopes the tenant; this argument is the only
        thing scoping the person, and the route hands it the `StaffContext`.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            return await self._notifications.recent(session, tenant_id, actor_id)

    async def mark_read(self, tenant_id: UUID, ids: list[uuid.UUID], *, actor_id: UUID) -> int:
        """Stamp her own rows, answer her own count.

        `ids` is the only client-supplied value in this feature, and it is
        harmless because it is intersected with `staff_user_id = actor_id`: a
        colleague's id in the list matches nothing and changes nothing, and the
        answer is still the CALLER's count — which is the number her bell is
        about to render.

        No audit row, and that is a recorded decision rather than a gap
        (`UNAUDITED_BY_DECISION` in `test_audit_coverage.py` carries the reason):
        a person marking her own notification read is not an administrative act.
        """
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            return await self._notifications.mark_read(session, tenant_id, actor_id, ids, at=at)
