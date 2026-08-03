import datetime
import uuid

from sqlalchemy import TIMESTAMP, Date, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class QueueTicket(StandardColumns, Base):
    """One walk-in's place in one boutique day's queue.

    A queue ticket is NOT a booking, and that is the point: no starts_at, no
    seat, no terms acceptance, no manage token, no SMS. Folding walk-ins into
    `bookings` would have meant a nullable starts_at on the table whose oversell
    guard is keyed on (tenant_id, starts_at, seat_index).

    There is no stored position — it is counted on read, ordered by
    COALESCE(requeued_at, created_at). A stored one must be renumbered on every
    insert and removal, and two concurrent renumberings produce duplicate or
    skipped positions a customer sees on two different phones.

    There is no uniqueness of any kind beyond the primary key: a second ticket
    for the same phone on the same day is a real, expected outcome, and F58
    merges or removes it. That is what closes the presence oracle.
    """

    __tablename__ = "queue_tickets"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # The scope of "today's queue", from today_jerusalem(clock) at create time.
    # Without it a ticket nobody closed overnight is still `waiting` and still
    # counted, so this morning's first arrival renders behind yesterday's ghosts.
    queue_day: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Normalised E.164, so it matches customers.phone exactly when F20 promotes a
    # consenting ticket. Not a key of any kind in F33 — no index, no uniqueness,
    # no lookup: nothing in the request path consults it.
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    visit_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'waiting'"))
    # Stamped when a manager calls her forward. F33 READS it — it is what lets
    # the position screen say "go to the counter" instead of showing 1 forever —
    # even though F58 writes it.
    called_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # F58's skip-to-back. It exists in F33 because F33 DEFINES the ordering, and
    # F58 must not be able to change a published read's semantics by adding a
    # column.
    requeued_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # F58's second-skip rule. Neither reader nor writer in F33.
    skip_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # The Spam Law consent timestamp, on THIS table rather than on `customers`:
    # F33 never writes to `customers` at all. NULL means no consent on record for
    # this visit. Set at INSERT and never updated, so "first timestamp wins"
    # holds by construction rather than by a guard.
    marketing_opt_in_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
