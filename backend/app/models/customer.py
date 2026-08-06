import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class Customer(StandardColumns, Base):
    """Keyed by (tenant, phone) and created ONLY after OTP verification proved
    possession of that number — an unverified phone would strand a paying
    customer behind an SMS link that can never arrive."""

    __tablename__ = "customers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # CRM fields the owner console writes (0017). `tags` carries the server
    # default so an untouched row reads [] and never None.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    # Privacy consent and erasure (0024). All four nullable with NO default, and
    # that is the design: consent is the PRESENCE of a timestamp, so NULL is the
    # only spelling of "no consent on record" and a default would make the absent
    # state unreachable. Effective marketing consent is
    # `marketing_consent_at IS NOT NULL AND marketing_consent_withdrawn_at IS NULL`
    # — withdrawal is additive, because clearing the consent stamp would destroy
    # the Spam-Law evidence that consent existed when a message was sent.
    marketing_consent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    marketing_consent_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketing_consent_withdrawn_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    erased_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # F24's bell (0027). The WHOLE read-state model: one timestamp, no per-item
    # rows. NULL is not "unknown" — it is "never opened the bell", which is why
    # the column carries no default: every message is unread until she looks.
    bell_seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
