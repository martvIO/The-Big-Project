import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class Payment(StandardColumns, Base):
    """One deposit against one booking.

    **`PaymentService` was this table's single writer, and F19 made it two.**
    The rule it enforced still stands and is worth restating: no adapter and no
    future caller may skip this row, exactly as no SMS path can skip
    `message_log`. Every route still reaches this table only through
    `PaymentService` — that is why `settle_late` is wrapped by
    `honour_late_settlement` rather than called from the webhook route.

    The second writer is `DepositSweeper` (`app/payments/sweeper.py`), and the
    reason is a boundary rather than convenience: the hold expiry writes
    `payments` AND `bookings` in ONE transaction, and `PaymentService` owns
    neither side of that pair — `settle_from_webhook` and
    `honour_late_settlement` each state in their own docstrings that they do not
    touch `bookings`, because a seat decision needs the advisory lock and the
    occupancy reads that live in the booking domain. Folding a `bookings` writer
    into `PaymentService` would erase that boundary on its first commit; and the
    sweeper runs in the worker, which would otherwise have to build a gateway
    adapter and a secret box it never calls.

    The accepted cost, stated so a third writer has to argue past it: `status`
    now has two writers and a future caller could cite the precedent. The
    containment is that `DepositSweeper` lives in the same package, takes the
    same injected `WallClock` as `open_deposit`, only ever writes one column
    pair on rows its own guarded `WHERE` already proved `pending`, and never
    inserts.

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
