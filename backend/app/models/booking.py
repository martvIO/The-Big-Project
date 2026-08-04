import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class Booking(StandardColumns, Base):
    """One appointment at one start time.

    A booking has no end: the slot model is a START TIME and `duration_minutes`
    on the type is information the boutique acts on, not geometry the engine
    reasons about (F12). `seat_index` plus the partial unique index in 0008 is
    what makes overselling impossible at any capacity.

    The `*_name` / `dress_*` columns are SNAPSHOTS, not denormalization for
    speed: a renamed type or an archived dress must not rewrite history the
    customer agreed to.
    """

    __tablename__ = "bookings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    seat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'confirmed'"))
    # Set by F16's reminder-link "confirm" action; the owner's console renders it.
    attendance_confirmed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # When a staff member recorded that this person is physically in the boutique
    # (F34's live shift board). NULL = not arrived (yet), and it is the only
    # sentinel. NOT a fifth BookingStatus (spec D1): status says what became of
    # the appointment, this says whether she is in the building, and the two are
    # true at once — a bride is checked in and then `completed`.
    #
    # Emphatically NOT `attendance_confirmed_at` above: that one is the BRIDE's,
    # written through her own tokenized link, and F15's /confirm refuses to touch
    # it in writing. A staffer's tap does not get to speak for her.
    checked_in_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # WHICH SURFACE CREATED THIS BOOKING (F50 D1) — 'storefront' | 'walk_in', a DB
    # CHECK. Not decoration and not analytics: it is the DISCRIMINATOR the
    # `bookings_terms_evidence_check` below needs, because without it a NULL
    # `terms_version_accepted` has two indistinguishable meanings — "a staffer
    # created this row and nobody accepted anything" and "a storefront booking lost
    # its evidence to a bug" — and only the first is legal.
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'storefront'"))
    # A pointer into the append-only terms_versions table, never a copy of the
    # text: the number is permanent evidence at a fraction of the size.
    #
    # NULLABLE SINCE F50, and the NULL is bounded rather than free: 0025's
    # `bookings_terms_evidence_check` admits it ONLY on `source = 'walk_in'`, which
    # is the one path where nobody accepted anything and stamping a version would
    # be manufacturing legal evidence. Every reader must narrow — a reader that
    # assumes evidence exists is right for every row it sees in development and
    # wrong for the first walk-in (spec Risk 3).
    terms_version_accepted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    appointment_type_name: Mapped[str] = mapped_column(Text, nullable=False)
    dress_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    dress_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    dress_size: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # sha256 of the tokenized manage link (F16, 0010). The RAW token never lands
    # here — it rides the SMS body and, while a reminder is pending, the
    # scheduled_messages row. NULL only on pre-F16 rows the backfill has not
    # reached.
    manage_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cancel evidence: E4 #19 evaluates refund-due vs forfeit from these plus
    # starts_at and the ACCEPTED terms version. 'customer' | 'owner' (DB CHECK).
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(Text, nullable=True)
