import datetime
import uuid

from sqlalchemy import Integer, Text, Time, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class ShiftTemplate(StandardColumns, Base):
    """One named shift the boutique runs on one weekday (F39, spec D2).

    MUTABLE IN PLACE AND NEVER VERSIONED. Versioning would force every reader —
    including all of F40's roster — to resolve templates *as of* a week, and
    would hand the owner a growing pile of dead rows for every typo she fixes.
    The cost is that a material edit invalidates the answers given against it
    (D4), which is a visible act with a count on the confirm dialog rather than a
    silent re-pointing.

    OVERLAPPING TEMPLATES ON ONE WEEKDAY ARE LEGAL, deliberately, and this is the
    one place F39 departs from `validate_weekly_rules`' shape: a morning and an
    afternoon sharing the changeover hour is an ordinary split shift. The count
    is bounded instead (`MAX_TEMPLATES_PER_DAY`, `MAX_TEMPLATES`).

    `availability_rules.capacity` is deliberately NOT copied here by the seed
    (D3): it is the slot engine's parallel-appointments number, not a headcount,
    and a "capacity 2" window reading as "two staff needed" would be a coverage
    target — F40's, and wrong the day a boutique takes two fittings with one
    assistant.
    """

    __tablename__ = "shift_templates"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # 0=Sunday … 6=Saturday — `availability_rules.day_of_week`'s encoding, which
    # `jerusalem_day_index` produces and is never re-derived.
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    # `ends_at_time > starts_at_time` is a named DB CHECK, so no overnight shift.
    ends_at_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # F40 (spec D10). A SPARSE map keyed by `StaffRole`: {"sales_assistant": 2}.
    # An ABSENT key is «no target» and renders as a plain count; `0` is
    # «deliberately nobody» and renders as a target. The two are not the same
    # thing, which is why this is a map and never a five-element vector.
    #
    # ⚠ A TARGET EDIT IS NOT A MATERIAL EDIT. `MATERIAL_FIELDS` reads
    # `day_of_week`, `starts_at_time`, `ends_at_time` and must NOT gain a fourth:
    # a coverage number changes nothing any staffer answered, and adding it would
    # soft-delete every future submission on this template the first time
    # somebody fixes a target from 2 to 3.
    coverage_targets: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
