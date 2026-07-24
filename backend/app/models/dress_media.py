import uuid

from sqlalchemy import Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns
from app.models.constants import DressMediaStatus


class DressMedia(StandardColumns, Base):
    """One uploaded photo, pending from presign until confirm verifies the object.

    storage_key embeds this row's own id, so it is computable before the INSERT
    and is written in that single statement — never patched afterwards, never
    mutated. content_type and byte_size are declared by the client and enforced
    twice: by the POST policy S3 signs and by the DB CHECKs.
    """

    __tablename__ = "dress_media"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dress_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{DressMediaStatus.PENDING}'")
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
