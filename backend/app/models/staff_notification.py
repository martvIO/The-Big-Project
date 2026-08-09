import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class StaffNotification(StandardColumns, Base):
    """One row per (recipient, event): somebody else made you responsible for a
    person.

    ⚠ **NO CUSTOMER DATUM, EVER — no name, no phone, no ticket id.** The row
    says WHO DID WHAT TO YOU; the floor screen, under its own audience rules,
    says who the customer is. The bell's list is fetched by a staffer for
    herself alone and its count rides a payload polled app-wide, so the cheapest
    way to keep it out of F20's territory is for there to be nothing here a
    subject request could name.

    **`staff_user_id` is the RECIPIENT** — the bell is per staff user, and every
    statement in the repository carries this column beside `tenant_id`. RLS
    scopes the tenant; only this predicate scopes the person.

    **`actor_staff_user_id` is never equal to `staff_user_id`.** All four
    producers guard on it: a manager taking the next walk-in for herself is the
    ORDINARY case, and a notification telling her what she just did is noise on
    the one surface whose whole value is that its count means something. The
    column is NOT NULL because a row that cannot say who did it to her has
    nothing to render — a NULL `actor_name` one layer up means the staff ROW is
    gone, never that the id was missing.

    **`entity_id` is untyped and `kind` names the table it points into.** It is
    stored because it is what makes the row a RECORD rather than a log line, and
    it is deliberately NOT on the wire: nothing renders it today, and the day a
    deep link exists it is one response field and no migration.

    **`read_at IS NULL` IS the unread state** — there is no boolean beside it,
    and a re-mark keeps the first timestamp. `deleted_at` has no v1 writer:
    reading is a status, not a deletion, and there is no per-row dismiss.
    """

    __tablename__ = "staff_notifications"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    staff_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_staff_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
