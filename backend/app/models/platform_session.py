import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class PlatformSession(Base, StandardColumns):
    """An operator's console session.

    Its OWN table rather than a widening of `sessions` (spec D3): that table's
    `tenant_id` and `staff_user_id` are both NOT NULL, and — the real reason —
    staff auth and operator auth must never share a lookup path. Two populations
    on one path is one missing predicate away from a staff cookie resolving as an
    operator. The F24 `customer_sessions` precedent, applied at higher stakes.

    Only the sha256 of the token is stored, exactly as for staff.
    """

    __tablename__ = "platform_sessions"

    operator_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
