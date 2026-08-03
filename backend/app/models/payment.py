import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class Payment(StandardColumns, Base):
    """One deposit against one booking. `PaymentService` is its single writer —
    no adapter and no future caller can skip this row, exactly as no SMS path can
    skip `message_log`.

    `provider` and `amount_agorot` are SNAPSHOTS, not read-throughs (the 0008
    appointment_type_name/dress_name argument): the owner can change a deposit at
    any time, and what was charged must render as what the customer agreed to.

    No `currency` column (D10) — agorot are ILS by definition and a column with
    one legal value lies about being optional. No receipt columns (D11) — whether
    the production PSP auto-issues a קבלה is unverifiable until an account
    exists, and the storage shape depends on the answer.
    """

    __tablename__ = "payments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # No FK by house rule; F19 owns the booking side of this relationship.
    booking_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    amount_agorot: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    # The hosted-page session F19 redirects to.
    provider_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The hosted-page URL itself (F19 D8). Stored rather than re-minted, because
    # `open_deposit` converges on an existing hold WITHOUT calling the gateway —
    # so a double-tap or the 0009 replay branch has no session to hand back
    # unless this column kept the first one. Re-minting instead would create the
    # orphaned-payable-session bug that D23's ordering exists to prevent.
    #
    # Blanked in the same .values() as every transition out of 'pending'
    # (settle, settle_late, and the sweeper's expiry claim): a live checkout URL
    # outliving its hold is a link that takes real money for a seat the boutique
    # has already given away.
    redirect_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The webhook's identity, and the replay key behind 0012's unique index.
    provider_transaction_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # F19's expiry sweeper reads this.
    hold_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # Scrubbed provider detail; never a response body.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
