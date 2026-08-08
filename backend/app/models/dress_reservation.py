import datetime
import uuid

from sqlalchemy import Date, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class DressReservation(StandardColumns, Base):
    """One gown, away for a range of calendar days (F28, spec D2).

    DATES AND NOT TIMESTAMPS, and `ends_on` is INCLUSIVE. A rental leaves and
    returns on days; the boutique operates in one timezone, so DATE makes the
    overlap arithmetic exact and DST-proof, and "unavailable 12-18" means the
    18th is unavailable too. Every reader comparing an INSTANT against these
    columns must convert to the boutique-local date first — `starts_at.date()`
    in UTC is off by a day for anything from 22:00 UTC onwards.

    Per DRESS, not per variant (D1): bookings snapshot `dress_id + dress_size`,
    the badge and the manual flag are dress-level, and `dress_variants` are size
    buckets with quantities rather than identifiable physical units.

    This does NOT replace `dresses.reserved`, it narrows it. That boolean is the
    manual, date-less hold ("away indefinitely, keep showing her") and keeps its
    exact shipped behaviour; these rows drive the date lines and the claim check.
    The two states are orthogonal and no precedence rule is needed.
    """

    __tablename__ = "dress_reservations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # No FK (house rule); the service proves the parent dress is live before it
    # inserts.
    dress_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    starts_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # Optional, and a POINTER — `alteration_tickets.customer_id`'s precedent
    # verbatim (D7). There are deliberately NO name/phone columns here: an erase
    # scrubs the `customers` row and every reservation renders the scrubbed name
    # automatically, so F20's export and erase surfaces need zero changes. A
    # renter who is not in CRM goes in `notes`.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    # Owner-authored operational text: bounded by MAX_RESERVATION_NOTES_LENGTH,
    # rendered as text and never HTML — `bookings.notes`' accepted class.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
