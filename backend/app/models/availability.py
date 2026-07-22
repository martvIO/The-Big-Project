import datetime
import uuid

from sqlalchemy import Date, Integer, Text, Time, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class AvailabilityRule(StandardColumns, Base):
    """Weekly recurring window. day_of_week: 0=Sunday … 6=Saturday (Israeli week).
    Multiple windows per day; non-overlap per day is enforced in the service."""

    __tablename__ = "availability_rules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    open_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    close_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    # Parallel appointments per window; E3 #12 may refine semantics additively.
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class AvailabilityException(StandardColumns, Base):
    """Per-date override that beats the weekly grid in both directions. Both
    times NULL = closed all day; both set = special hours; one-sided rejected in
    the service. One window per exception date is a documented v1 limitation."""

    __tablename__ = "availability_exceptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    open_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    close_time: Mapped[datetime.time | None] = mapped_column(Time, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
