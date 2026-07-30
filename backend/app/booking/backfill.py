"""The one-time deploy step F16 needs because F14 shipped first.

F14 is live, so at F16 deploy there are already `confirmed` future-dated bookings
with no manage token and no reminder row. The ROADMAP's definition of done
promises the reminder unconditionally, and the gap's victims are the pilot's first
real customers — so every such booking gets a token and a D3-band reminder here.

**No retroactive confirmation SMS** (D10): a "your appointment is confirmed" text
days after the fact reads as spam, and the reminder carries the same link anyway.

Idempotent by predicate rather than by a ledger: the feed is
`manage_token_hash IS NULL`, which the first run fills, so a second run finds
nothing. That is also why it is safe to re-run after a partial failure.
"""

import dataclasses
import datetime
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.booking.comms import reminder_send_after
from app.booking.tokens import manage_token_hash, mint_manage_token
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.constants import ScheduledMessageKind
from app.storefront.validation import Clock

logger = logging.getLogger("app")

# One page of bookings per transaction, and a hard chunk ceiling so a runaway
# cannot loop forever (house batch-processing rule). 500 x 50 is two orders of
# magnitude past the pilot's whole book.
CHUNK_SIZE = 500
MAX_CHUNKS = 50


@dataclasses.dataclass(frozen=True)
class BackfillResult:
    tenants: int = 0
    tokens_minted: int = 0
    reminders_scheduled: int = 0


class ManageLinkBackfill:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._tenants = TenantsRepository(session_factory)
        self._bookings = BookingsRepository()
        self._scheduled = ScheduledMessagesRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def run(self) -> BackfillResult:
        now = self._now()
        tenants = await self._tenants.list_active()
        minted = scheduled = 0
        for tenant in tenants:
            tenant_minted, tenant_scheduled = await self._run_for_tenant(tenant.id, now=now)
            minted += tenant_minted
            scheduled += tenant_scheduled
        return BackfillResult(
            tenants=len(tenants), tokens_minted=minted, reminders_scheduled=scheduled
        )

    async def _run_for_tenant(
        self, tenant_id: uuid.UUID, *, now: datetime.datetime
    ) -> tuple[int, int]:
        minted = scheduled = 0
        for chunk_index in range(MAX_CHUNKS):
            async with tenant_session(self._session_factory, tenant_id) as session:
                # No offset: each pass consumes its own rows by filling
                # manage_token_hash, so paging by offset would skip the rows the
                # previous pass shifted forward.
                rows = await self._bookings.list_confirmed_without_manage_token(
                    session, tenant_id, after=now, limit=CHUNK_SIZE
                )
                if not rows:
                    return minted, scheduled
                for booking in rows:
                    token = mint_manage_token()
                    await self._bookings.set_manage_token_hash(
                        session, tenant_id, booking.id, token_hash=manage_token_hash(token)
                    )
                    minted += 1
                    send_after = reminder_send_after(starts_at=booking.starts_at, now=now)
                    if send_after is None:
                        # Inside the two-hour window. She keeps the link — the
                        # backfill's other half — and gets no reminder, exactly
                        # as a fresh booking at that notice would not.
                        continue
                    await self._scheduled.insert(
                        session,
                        tenant_id=tenant_id,
                        booking_id=booking.id,
                        kind=ScheduledMessageKind.REMINDER.value,
                        send_after=send_after,
                        manage_token=token,
                    )
                    scheduled += 1
            if len(rows) < CHUNK_SIZE:
                return minted, scheduled
            logger.info("backfill: tenant %s chunk %d done", tenant_id, chunk_index)
        logger.warning("backfill: tenant %s hit MAX_CHUNKS — re-run to finish", tenant_id)
        return minted, scheduled
