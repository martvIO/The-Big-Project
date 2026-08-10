import datetime
import uuid

from sqlalchemy import TIMESTAMP, Date, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class WaitlistEntry(StandardColumns, Base):
    """One OTP-verified phone waiting for one (day, appointment type) at one
    boutique — pre-decided #14's whole entry shape.

    No name, no dress binding, no terms, no marketing-consent field, no stored
    position. FIFO is `ORDER BY (day, created_at)` when a reader needs it; the
    consent field is ABSENT rather than false because an absent field is the
    only spelling a future caller cannot flip (F50 D3b). Terms are accepted at
    BOOKING time — F23's claim runs the real booking path, which enforces them.

    Uniqueness IS here, unlike queue_tickets, and the difference is the trust
    posture: this table's refusal is only reachable through a caller who proved
    possession of the phone via OTP, so there is no presence oracle, and the
    owner cancel is the stuck-key remedy F33 lacked. The rationale lives at the
    index in 0026, per 0018's demand.
    """

    __tablename__ = "waitlist_entries"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # The day she wants, Jerusalem-calendar, CUSTOMER-picked — validated against
    # today..today+SLOT_WINDOW_MAX_DAYS in app/waitlist/validation.py, never a
    # DB expression (0018's stored-DATE ruling).
    day: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # No FK, app-level integrity (house rule). The join resolves it through
    # AppointmentTypesRepository.by_id before the INSERT.
    appointment_type_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # normalize_israeli_mobile output, matching customers.phone spelling exactly
    # — which is what makes the F20 export/erase joins reachable for a bride who
    # both booked and waited.
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'waiting'"))
    # --- F23's offer bookkeeping (0033), all four NULL until she is offered ---
    #
    # They move and clear TOGETHER, always inside one guarded UPDATE: the offer
    # write sets all four, the expiry sweep clears the token and the deadline,
    # and the claim clears the token. Nothing reads one without the others, and
    # "no live offer" is spelled NULL rather than by a sentinel.
    offered_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    offer_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # THE slot instant this offer names. One offer names one instant, which is
    # what lets the claim re-materialize a single grid position rather than a set.
    offer_starts_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # sha256 only — `mint_manage_token`'s raw value never lands here. It lives in
    # the SMS body and, while the offer message is pending, on
    # `scheduled_messages.manage_token`.
    offer_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
