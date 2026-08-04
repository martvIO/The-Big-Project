import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class SosAlert(StandardColumns, Base):
    """One staffer asking for help, right now, from one target.

    **`status` is the whole state machine and there is no second copy of it.**
    `open -> accepted -> resolved`, `open -> cancelled`, pinned by the CHECK in
    the migration. `escalated` and `stalled` are NOT columns: they are read-time
    predicates over this row and a clock (D6), so there is no instant at which
    anything happens and no writer to hang them on. A worker-stamped
    `escalated_at` would arrive up to a full minute late against a thirty-second
    requirement and would introduce a write that races a concurrent ack.

    **`created_at` is the escalation clock's left operand and it is
    DB-generated** — `server_default=text("now()")`, i.e. the database host's
    transaction-start time — while `server_now` is the service's Python clock.
    The skew is NTP-bounded and irrelevant against a 30-second threshold read
    every 2 seconds, but it is why the `db` suite SEEDS `created_at` rather than
    relying on the default: the default applies only when the column is omitted,
    and a test that goes green or red on machine speed will be re-run until it
    passes.

    **No customer datum of any kind, ever.** `note` is free text a staffer types
    about her OWN situation and is disclosed to the alert's audience alone. The
    payload this row feeds is polled app-wide on every section by every one of
    the five roles, and that is exactly why it carries staff names and a room
    label and nothing else.
    """

    __tablename__ = "sos_alerts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # WHO IS CALLING. Never body-supplied: it is the StaffContext resolved from
    # the session cookie. Nobody may raise a page AS somebody else — not even an
    # owner — because an SOS is a first-person statement.
    raised_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # WHOM SHE CALLED. NULL = the shift-manager ROLE, which is the audience
    # {owner, shift_manager}. Also NULL when a named colleague turned out to be
    # unreachable and the raise rerouted — which is why the audit row carries the
    # REQUESTED target and this column cannot.
    target_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # WHERE. NULL is ordinary: a staffer not in a room, or a pointer that no
    # longer resolved to HER OWN assignment at raise time.
    fitting_room_assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # FOUR WORDS. Stripped; "" and NULL are one input.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'open'"), default="open"
    )
    # WHO OWNS IT — written by the same atomic UPDATE that sets `status`, so the
    # pair can never disagree.
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    # Stamped from the service's injectable clock rather than SQL now(), so the
    # db suite can freeze it and assert an equality — the shipped shape one
    # method over (`FittingRoomAssignmentsRepository.release`'s `at`).
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
