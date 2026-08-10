import datetime
import uuid

from sqlalchemy import Date, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class StaffAvailability(StandardColumns, Base):
    """One staffer's answer for one shift in one week (F39, spec D8/D11).

    ⚠ THIS IS NOT AN HOURS-WORKED RECORD AND MUST NEVER BECOME ONE. The epic's
    labour-law row binds here: a later feature reading these rows as attendance
    is a review-blocking drift. Nothing in F39 sums them, and nothing renders an
    hour total on any screen.

    THE ABSENCE OF A ROW IS "NOT ANSWERED" (D8). There is deliberately no fourth
    `pending` state: the roster-readiness read counts missing rows, and a stored
    "pending" would make «she has not answered» and «she answered *pending*»
    indistinguishable in exactly the query the owner opens that screen to run.
    Clearing an answer is a soft delete, which returns the pair to "not answered"
    by the same predicate.

    NO NAME, NO PHONE, NO FREE TEXT — nothing a subject request could name (D9),
    which is why F39 adds no retention policy and `app/privacy/retention.py`
    stays at EIGHT classes. These are operational history joined by a
    `staff_user_id` that is never nulled: the `staff_users` SCRUB blanks the
    person and these rows survive pointing at an erased row, which is the answer
    rather than a gap.
    """

    __tablename__ = "staff_availability"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # No FK on either pointer (house rule); the service proves both parents are
    # live before it writes, and a write naming a soft-deleted staffer is a 404.
    staff_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    shift_template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # The Jerusalem Sunday that opens the week, as a plain calendar DATE (D1),
    # pinned by `staff_availability_week_start_check`. Always computed
    # server-side from `today_jerusalem()`; a client may NAME a week but the
    # server validates the Sunday-ness and never trusts the arithmetic.
    week_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # One of AvailabilityState, pinned by a named DB CHECK because it is a
    # STORED value (SosStatus' rule).
    state: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL when she recorded it herself (D5). An elevated actor is not subject to
    # the deadline and may record for anyone; this column is what lets her own
    # screen say «נרשם על ידי {{name}}.» honestly rather than guess.
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
