from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class PlatformInvite(Base, StandardColumns):
    """An operator-issued authorisation to create ONE boutique at ONE address.

    Platform-scoped like `PlatformOperator` (spec D3): no `tenant_id`, no RLS.
    The tenant this invite creates does not exist until it is redeemed, and the
    one it produced is recorded as `redeemed_tenant_id` — 0004's
    `target_tenant_id` shape, not a `tenant_id` column.

    ⚠ THERE IS NO RAW-CODE FIELD AND THERE MUST NEVER BE ONE. `code_hash` is
    `hash_token(code)`; the raw value exists in exactly one response, once, and
    then only in the operator's clipboard (spec D3). Adding a `code` column "for
    support" would turn a database leak into a set of live boutique-creation
    credentials.

    `slug`, `name` and `owner_email` are the operator's pre-assignment (D2). The
    redeemer contributes only a password, which is what makes a leaked link
    harmless: it can create the boutique the operator authorised, at the address
    he authorised, and nothing else.

    `redeemed_at IS NULL` is the single-use predicate, and it is enforced by an
    atomic conditional UPDATE rather than by a read-then-write — see
    `PlatformInvitesRepository.claim`.
    """

    __tablename__ = "platform_invites"

    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_email: Mapped[str] = mapped_column(Text, nullable=False)
    # The authenticated operator's email. Carried onto BOTH redemption audit
    # rows, because the redeemer authenticates as nobody and this is the
    # accountable identity behind the act.
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    redeemed_tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
