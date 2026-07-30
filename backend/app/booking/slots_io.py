"""The I/O-shaped sibling of `slots.py`: read the rows, then ask the pure grid.

`slots.py` is pure by construction — "no session, no ORM write, no `Settings`,
no `datetime.now()`" — and that purity is the reason it is trustworthy, so a
coroutine taking an `AsyncSession` and three repositories cannot live in it.
This module is where the reads that FEED `materialize_slots` live, and it holds
exactly one caller-facing question: is this instant offered right now?

Two services ask it: F13's `create_booking` validating a claim, and F15's owner
reschedule choosing a target. One implementation, for the reason `slots.py:6-8`
gives — three would be three chances to disagree.
"""

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.slots import Slot, materialize_slots
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.storefront.validation import BOUTIQUE_TIMEZONE


async def offered_slot(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    starts_at: datetime.datetime,
    now: datetime.datetime,
    rules: AvailabilityRulesRepository,
    exceptions: AvailabilityExceptionsRepository,
    bookings: BookingsRepository,
) -> Slot | None:
    """The requested instant as the grid currently offers it, or None.

    Not a formality: without this a caller books 03:00 on a closed Saturday
    by posting an arbitrary timestamp. One boutique-calendar day is enough —
    a slot's date in the boutique's own zone is the only date whose rules
    and exceptions can produce it."""
    wanted = starts_at.astimezone(datetime.UTC)
    target_date = wanted.astimezone(BOUTIQUE_TIMEZONE).date()
    active_rules = await rules.list_active(session, tenant_id)
    active_exceptions = await exceptions.list_active(
        session, tenant_id, on_or_after=target_date, on_or_before=target_date
    )
    day_start = datetime.datetime.combine(
        target_date, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)
    day_end = datetime.datetime.combine(
        target_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)
    booked = await bookings.count_by_start(
        session, tenant_id, from_instant=day_start, until_instant=day_end
    )
    slots = materialize_slots(
        rules=active_rules,
        exceptions=active_exceptions,
        booked=booked,
        window_start=target_date,
        window_end=target_date,
        now=now,
    )
    return next((slot for slot in slots if slot.starts_at == wanted), None)
