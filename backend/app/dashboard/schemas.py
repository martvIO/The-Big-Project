"""The dashboard's wire shapes — one nested response, no request body.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=`
(the shipped house form). No `ForbidExtraModel`: the endpoint takes no body, so
there are no extras to forbid.

`null` on a rate means **not computable**, never zero — the console renders the
two differently (D5, D10). The backend emits the UNROUNDED quotient; all
rounding is the console's (D5).

The worked payload for `generated_on = 2026-07-31` (a Friday,
`jerusalem_day_index == 5`) is normative, and its three shape invariants are
pinned by `tests/test_dashboard_math.py` — an off-by-one-week version of this
block survived a full review once:

    generated_on   2026-07-31
    history.from_date  2026-05-03   (the first bucket's Sunday)
    history.to_date    2026-07-25   (the Saturday before the current week)

    to_date == from_date + 7 * HISTORY_WEEKS - 1 day
    to_date <  generated_on
    weeks[-1].week_start == generated_on - (jerusalem_day_index(generated_on) + 7) days
"""

import datetime
import uuid

from pydantic import BaseModel


class WeekBucket(BaseModel):
    """One complete Israeli week. `bookings` counts the seat-slots the boutique
    HELD — every status except `cancelled`, so a no-show is in the bar (D5).
    The label the console draws says exactly that."""

    week_start: datetime.date
    bookings: int


class StatusTotals(BaseModel):
    """All four CHECK-pinned statuses. `confirmed` over a window entirely in the
    past is the UNCLASSIFIED count — an appointment whose outcome the owner
    never recorded — and it ships beside `no_show_rate` for that reason (D5)."""

    confirmed: int
    cancelled: int
    no_show: int
    completed: int


class AppointmentTypeCount(BaseModel):
    """`name` is an appointment TYPE label, never a person's — which is why F52's
    forbidden-key walk cannot contain the bare key `name` (D8)."""

    appointment_type_id: uuid.UUID
    name: str
    bookings: int


class CustomerMix(BaseModel):
    total: int
    new: int
    returning: int
    repeat_rate: float | None


class HistoryPanel(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    weeks: list[WeekBucket]
    status_totals: StatusTotals
    cancellation_rate: float | None
    # These two can sum to LESS than status_totals.cancelled: a row cancelled
    # before migration 0010 added the column carries NULL and is in neither
    # (Risk 11). The console must never render them as a partition.
    cancelled_by_customer: int
    cancelled_by_owner: int
    no_show_rate: float | None
    appointment_types: list[AppointmentTypeCount]
    customers: CustomerMix


class ForwardPanel(BaseModel):
    """`to_date` is INCLUSIVE, matching the slot engine's window. `booked` is the
    CLAMPED GRID SUM, never `sum(booked_by_instant.values())` (D4)."""

    from_date: datetime.date
    to_date: datetime.date
    capacity: int
    booked: int
    utilization: float | None


class DashboardResponse(BaseModel):
    generated_on: datetime.date
    history: HistoryPanel
    forward: ForwardPanel
