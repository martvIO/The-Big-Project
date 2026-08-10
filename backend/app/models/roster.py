import datetime
import uuid

from sqlalchemy import TIMESTAMP, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class Roster(StandardColumns, Base):
    """One week's staffing plan for one boutique (F40, spec D6).

    ⚠ `published_at` / `published_by` ARE THE WHOLE OF THIS TABLE'S STATE. There
    is no `status` enum and deliberately so: it would be a second copy of a fact
    `published_at` already states, and the pair could disagree —
    `sos_alerts.status`' own model comment makes the identical argument.

    ⚠ THE ROW EXISTS SO "PUBLISHED WITH NOBODY ON THIS SHIFT" AND "NO ROSTER
    PUBLISHED" CAN BE TOLD APART (D5). Deriving "published" from
    `EXISTS(roster_assignments)` collapses them, and it collapses them in the
    dangerous direction: an owner who publishes a genuinely empty Saturday would
    find the whole boutique reported as on shift.

    A draft is never authoritative and is invisible to staff (D6): with
    `published_at IS NULL` the resolver's rule 2 does not fire at all and rule 3
    answers, which is today's behaviour unchanged.

    THERE IS NO UNPUBLISH (spec C5/D7). To stop a roster governing a week the
    owner removes its assignments — an honest published statement ("nobody is
    rostered") rather than a hidden reversion to fallback.
    """

    __tablename__ = "rosters"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # The Jerusalem Sunday, F39's `week_start` encoding unchanged.
    week_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    published_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    published_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
