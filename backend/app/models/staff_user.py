import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns
from app.models.constants import StaffRole


class StaffUser(StandardColumns, Base):
    __tablename__ = "staff_users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{StaffRole.OWNER}'")
    )
    # The second half of F57's migration, and not optional: no model<->migration
    # parity test exists anywhere in Backend/tests, so without this every line of
    # the break writers and the floor read is an AttributeError.
    break_started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # The second half of F42's migration, and not optional for the same reason:
    # no model<->migration parity test exists anywhere in Backend/tests, so
    # without this every line of the capacity route and the board's resolution
    # is an AttributeError.
    #
    # `int | None`, and the None is load-bearing: NULL means "no capacity
    # recorded", which resolves to the tenant default, while 0 means "she is not
    # available this week" and is HERS. Every reader branches on `is not None`
    # and never on truthiness.
    weekly_capacity_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
