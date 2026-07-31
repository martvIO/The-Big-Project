import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class TenantGatewayCredential(StandardColumns, Base):
    """One boutique's payment-gateway credential set, encrypted at rest.

    `ciphertext` is a SecretBox blob and NEVER a plaintext field. Nothing reads
    it back out through the API — there is no response field for it, which is
    what makes the credentials write-only by construction rather than by a rule
    somebody has to remember.

    Rotation is soft-delete + insert (D6), so the superseded row is the rotation
    trail an incident review needs; `key_ref` is what tells that review which box
    and key wrote each one. At most one row per (tenant, provider) is active —
    0012's partial unique index makes that structural.

    `last_validated_at` is NOT NULL and there is no 'unvalidated' status: the
    provider is pinged BEFORE the row is written (D4), so a stored-but-unproven
    credential is not a state this table can hold.
    """

    __tablename__ = "tenant_gateway_credentials"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'valid'"))
    last_validated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Scrubbed + truncated provider detail. Operator telemetry, held to the same
    # containment as message_log.error — never rendered to an owner.
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # staff_users.id; no FK by house rule.
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
