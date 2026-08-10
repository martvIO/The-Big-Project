import uuid

from sqlalchemy import Boolean, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class RosterAssignment(StandardColumns, Base):
    """One staffer on one shift of one roster (F40, spec D11/D12).

    ⚠ `override_of_state` IS STAMPED AT ASSIGNMENT TIME AND NEVER UPDATED. It
    records what she had submitted when the owner assigned her anyway — NULL when
    nothing was overridden. A staffer who goes unavailable AFTER she was rostered
    is a different fact with a different render (design F-5), and both are on the
    wire: the stamp comes from this column, the later change from the live
    `staff_availability` row. Overwriting this would erase the record of what the
    owner knowingly did.

    ⚠ `is_shift_manager` IS GATED ON `staff_users.shift_manager_eligible` ALONE
    (D12) and never on `role`. F38 shipped that boolean specifically to separate
    "may be assigned as shift manager" from "her job is shift manager", and
    deriving one from the other deletes the distinction it was created to make.
    At most one per (roster, shift), enforced by a partial unique index rather
    than a service read-then-write.

    THIS IS NOT AN HOURS-WORKED RECORD. Nothing here carries a duration, nothing
    sums one, and no reader may treat these rows as attendance — the epic's
    labour-law row makes that drift review-blocking rather than a design nit.
    """

    __tablename__ = "roster_assignments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # No FK on any pointer (house rule); the service proves each parent is live.
    roster_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    shift_template_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    staff_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    is_shift_manager: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # CHECKed against the whole `AvailabilityState` set, not just the one literal
    # the service writes today — see the migration.
    override_of_state: Mapped[str | None] = mapped_column(Text, nullable=True)
