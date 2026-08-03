import datetime
import uuid

from sqlalchemy import TIMESTAMP, Date, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class AlterationTicket(StandardColumns, Base):
    """One garment's alteration, from the counter to the bride's hands.

    THE FIVE NULLABLE TIMESTAMPS BELOW ARE THE STATE MACHINE. There is no status
    column and deliberately not (spec D2, pre-decided #39): the current stage is
    the RIGHTMOST stamped column — `app.atelier.stages.stage_of` — and the
    timestamps are simultaneously the state and the record of when each stage
    happened. A status column beside them would be two representations of one
    fact that a concurrent writer can desynchronise, and it answers neither
    metric this epic promises: median time-in-state IS `ready_at -
    in_progress_at`.

    An earlier stamp that is NULL while a later one is set means "that stage was
    never separately recorded", NOT that it did not happen. A seamstress who
    takes a hem from intake straight to ready in one sitting leaves
    `in_progress_at` and `qc_at` NULL forever and the ticket reads `ready`. Any
    reader that walks forward looking for the first NULL is wrong on exactly
    that row, and F44's medians must treat a NULL as "no observation" rather
    than as zero.

    Backwards is not a state these columns can express, and no CHECK enforces
    that — the write predicate does, in one clause instead of ten
    (`AND <every later column> IS NULL`).
    """

    __tablename__ = "alteration_tickets"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # The bride. A POINTER, not a snapshot — `customers.name` is updated toward
    # the truth on every write, so a name snapshotted at intake would keep
    # calling her by a spelling she has since corrected. No FK (house rule);
    # integrity is the service's.
    customer_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # The priority key the whole epic subtracts from, and the ATELIER ruling's
    # replacement for E9's wedding_date (an evening gown has no wedding). A DATE
    # and not a TIMESTAMPTZ: it is a calendar day the bride names, not an
    # instant, and it is the one place Asia/Jerusalem is allowed to appear —
    # `overdue` is computed on read against today_jerusalem and never stored.
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # MINUTES persist, never the band label. A boutique that re-tunes its bands
    # must not silently re-value work already estimated, which is why there is
    # no effort_band column: the band is an input affordance resolved
    # server-side from tenants.settings["atelier"]["effort_bands"].
    effort_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL is a real state and the board renders it — an unassigned ticket is
    # the thing a shift manager is looking for. Keyed on the ID and never a
    # name, because the offboarding scrub blanks personal fields and leaves the
    # id. Point-in-time validated as a seamstress at assign time, never a live
    # guarantee of role: F51's staff CRUD can re-role or retire her afterwards,
    # which is why the board's `seamstresses[]` is a UNION and not a filter.
    assigned_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # 0008's three snapshot columns and its exact reasoning: the owner may
    # rename or archive a dress mid-alteration and the ticket must keep
    # rendering the garment it was opened for. All three nullable because an
    # alteration is frequently on the bride's own gown, which has no catalog
    # row — so dress_name has two sources (the server's copy of dresses.name
    # when dress_id is supplied, or the client's free text when it is not).
    #
    # dress_id has NO console writer in F41 and F43 is its caller: the board
    # renders no image, so nothing on this surface reads it.
    dress_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    dress_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What she MEASURED — «38, מותן מוקטן» — not a stock bucket. Deliberately
    # not validated against dress_variants, which is a different question.
    dress_size: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free text, bounded, rendered as text and never HTML. This is the column
    # most likely to hold body measurements, which is the most intimate data
    # this platform carries — F20 owns the retention clock for it, and the audit
    # rows for an edit carry changed field NAMES and never values.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Stage 1 of five, stamped by the INSERT itself. Structurally non-null and
    # immutable in practice — undo refuses to clear it and no other verb writes
    # it — so it is NOT evidence that anything was separately recorded, unlike
    # the four below it.
    intake_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    in_progress_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    qc_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ready_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Terminal. `delivered_at IS NOT NULL` cancels overdue (a garment delivered
    # late is a fact about the past) and is what the board's seven-day window
    # filters on.
    delivered_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
