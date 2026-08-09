"""The I/O-shaped sibling of `slots.py`: read the rows, then ask the pure grid.

`slots.py` is pure by construction — "no session, no ORM write, no `Settings`,
no `datetime.now()`" — and that purity is the reason it is trustworthy, so a
coroutine taking an `AsyncSession` and three repositories cannot live in it.
This module is where the reads that FEED `materialize_slots` live, and it holds
exactly two caller-facing questions:

1. **Is this instant offered right now?** (`offered_slot`) — F13's
   `create_booking` validating a claim, and F15's owner reschedule choosing a
   target. One implementation, for the reason `slots.py:6-8` gives: three would
   be three chances to disagree.
2. **How full is the grid over a date range?** (`forward_capacity`) — F52's
   dashboard panel.
"""

import dataclasses
import datetime
import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.booking.slots import Slot, materialize_slots
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.storefront.validation import BOUTIQUE_TIMEZONE


@dataclasses.dataclass(frozen=True)
class ForwardCapacity:
    capacity: int
    # The CLAMPED GRID SUM, never sum(booked_by_instant.values()). Shipping the
    # dict's sum would put two integers on one card that visibly disagree with
    # the percentage beside them.
    booked: int

    @property
    def utilization(self) -> float | None:
        # None means NOT COMPUTABLE, never zero — a boutique that has set no
        # hours is a different fact from one nobody has booked, and the console
        # renders the two differently.
        return self.booked / self.capacity if self.capacity else None


def grid_totals(
    grid: Sequence[Slot], booked_by_instant: Mapping[datetime.datetime, int]
) -> ForwardCapacity:
    """Seat-slots offered, and seat-slots taken, over a materialized grid.

    **Iterate the GRID, not the mapping.** `count_by_start` can hold instants
    the grid no longer offers — a booking made under a weekly rule the owner has
    since deleted, or on a date a later exception closed. Those rows exist and
    are counted but have no capacity behind them, so summing the mapping
    produces `booked > capacity` and a utilization above 100%.

    `min(booked, capacity)` is the same defensive posture `Slot.remaining` takes
    with `max(capacity - booked, 0)` for the identical anomaly
    (`slots.py:36-41`).

    Capacity here means SEAT-SLOTS: one start time times its capacity. A slot
    has no duration (`slots.py:9-14`), so a minutes-based ratio would be
    arithmetic over geometry the booking engine explicitly refuses to reason
    about, and it would disagree with what the engine actually enforces.
    """
    return ForwardCapacity(
        capacity=sum(slot.capacity for slot in grid),
        booked=sum(min(booked_by_instant.get(slot.starts_at, 0), slot.capacity) for slot in grid),
    )


async def day_slots(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    day: datetime.date,
    now: datetime.datetime,
    rules: AvailabilityRulesRepository,
    exceptions: AvailabilityExceptionsRepository,
    bookings: BookingsRepository,
) -> list[Slot]:
    """One boutique-calendar day's grid, fed the REAL booked counts — ascending.

    Extracted from `offered_slot` below rather than written beside it, because
    F23's cascade needs the same grid to pick a slot to OFFER and a second
    assembly of "rules + exceptions + count_by_start -> materialize_slots" is a
    second chance to disagree with the engine that will then refuse the claim.
    The whole point of `slots.py:6-8` is that there is one implementation.

    A full slot is DROPPED by `materialize_slots`, never marked, so "the earliest
    slot here" already means "the earliest FREE slot" and no caller has to ask
    about capacity.
    """
    active_rules = await rules.list_active(session, tenant_id)
    active_exceptions = await exceptions.list_active(
        session, tenant_id, on_or_after=day, on_or_before=day
    )
    day_start = datetime.datetime.combine(
        day, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)
    day_end = datetime.datetime.combine(
        day + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)
    booked = await bookings.count_by_start(
        session, tenant_id, from_instant=day_start, until_instant=day_end
    )
    return materialize_slots(
        rules=active_rules,
        exceptions=active_exceptions,
        booked=booked,
        window_start=day,
        window_end=day,
        now=now,
    )


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
    slots = await day_slots(
        session,
        tenant_id=tenant_id,
        day=wanted.astimezone(BOUTIQUE_TIMEZONE).date(),
        now=now,
        rules=rules,
        exceptions=exceptions,
        bookings=bookings,
    )
    return next((slot for slot in slots if slot.starts_at == wanted), None)


async def forward_capacity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    window_start: datetime.date,
    window_end: datetime.date,
    now: datetime.datetime,
    rules: AvailabilityRulesRepository,
    exceptions: AvailabilityExceptionsRepository,
    bookings: BookingsRepository,
) -> ForwardCapacity:
    """How full `[window_start, window_end]` is right now — both bounds
    inclusive boutique-calendar dates, matching the engine's own window.

    **`booked={}`, and that is the whole trick.** `materialize_slots` DROPS
    every slot where `taken >= capacity` rather than marking it, because *"a
    public response that enumerated them would disclose the boutique's booking
    density"* (`slots.py:149-152`). Summing `capacity` over
    `StorefrontService.list_slots` or `OwnerBookingService.list_slots` therefore
    omits precisely the fully-booked slots — the ones that make utilization
    high. That number is biased downward, can never reach 100%, and the error
    GROWS as the boutique gets busier, i.e. it is worst exactly when the number
    matters. Passing `booked={}` makes `taken` 0 at every instant, and
    `CHECK (capacity > 0)` (`0005_boutique_settings.py:65`) guarantees
    `0 < capacity` everywhere, so nothing is dropped for fullness. The grid comes
    back complete with zero change to the engine — which is also why there is no
    `include_full` flag: a switch whose only purpose is disabling a disclosure
    control on the function that ALSO serves anonymous traffic is a permanent
    footgun.

    **This deliberately republishes the density aggregate the anonymous surface
    is fenced against, and that is a posture, not an oversight.** It is allowed
    because the caller is behind `require_role(OWNER, SHIFT_MANAGER)` on a
    host-resolved tenant reading its own rows, and because `GET /manage/slots`
    already ships PER-SLOT `capacity` and `remaining` to those same two roles
    (`booking/owner_router.py:306-330`) — strictly more disclosure than two
    integers. **`forward_capacity` must never grow a slot-list return**: that is
    the shape the fence exists to stop.
    """
    active_rules = await rules.list_active(session, tenant_id)
    active_exceptions = await exceptions.list_active(
        session, tenant_id, on_or_after=window_start, on_or_before=window_end
    )
    # The engine keys `booked` by UTC start instant; the window is boutique
    # calendar dates, so its edges become boutique-midnight instants. The right
    # edge is half-open — start of the day AFTER window_end.
    #
    # The two bounds therefore differ by one day and that is deliberate, not a
    # typo: `materialize_slots`'s window_end is an INCLUSIVE date
    # (`slots.py:116-117, 134`) while `count_by_start` is half-open on the right
    # over instants. Writing `last = midnight(window_end)` reads correct against
    # the sentence "the window is [start, end]" and understates utilization by
    # up to a seventh — the last day's capacity stays in the denominator while
    # its bookings vanish from the numerator — permanently and silently.
    first = datetime.datetime.combine(
        window_start, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)
    last = datetime.datetime.combine(
        window_end + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)
    booked_by_instant = await bookings.count_by_start(
        session, tenant_id, from_instant=first, until_instant=last
    )
    grid = materialize_slots(
        rules=active_rules,
        exceptions=active_exceptions,
        booked={},
        window_start=window_start,
        window_end=window_end,
        now=now,
    )
    return grid_totals(grid, booked_by_instant)
