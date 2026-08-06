import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class CustomerSession(StandardColumns, Base):
    """A logged-in customer's portal session — the first customer-side session
    this platform has (F24 D2).

    Deliberately NOT a row on `sessions`: that table's `staff_user_id` is NOT
    NULL, and making it nullable to fit a customer here would put staff and
    customer principals on one lookup path, where a single missing predicate
    resolves the wrong one. The cookie name differs for the same reason —
    `boutique_customer_session` beside `boutique_session`, because both apps
    live on the same tenant host and one name would let a staff login clobber a
    customer's session.

    `expires_at` is FIXED at mint (30 days) with no sliding renewal: renewal is
    a write on every read, and the remedy for an expired session is one OTP.
    """

    __tablename__ = "customer_sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
