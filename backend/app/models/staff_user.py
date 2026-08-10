import uuid
from datetime import date, datetime

from sqlalchemy import TIMESTAMP, Boolean, Date, Integer, Text, text
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
    # The second half of F38's migration 0031. Unlike the two blocks above, this
    # one IS enforced: test_staff_user_declares_every_column_the_hr_migration_adds
    # reads 0031's own column list and compares it to this class, so the parity
    # those comments could only ask for is now a red test.
    #
    # CONTACT ONLY, and never a login identifier (spec C1). Interview Q11 was
    # overridden by F31 — staff sign in with email + password — so nothing in
    # app/auth reads this column, it carries no unique index, and the retention
    # scrub NULLs it.
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Jerusalem CALENDAR dates, not instants: `date` on the wire and `date` in the
    # column, because "her last day" is a day and an instant would make the
    # boundary depend on what o'clock somebody pressed the button.
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # NULL means still employed. The retention policy requires it NOT NULL, which
    # is why 0031's backfill exists and why offboarding defaults it rather than
    # letting a blank body through.
    last_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    # A boolean SEPARATE from `role`, and the separation is the point: "may be
    # assigned as shift manager" is not "her job is shift manager". F38 stores it
    # and enforces nothing; F40 is its only consumer (spec O4).
    shift_manager_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # D22's self-falsifying guard, `customers.erased_at`'s shape: the scrub's own
    # UPDATE destroys the predicate that selected the row.
    scrubbed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # The live triple and the pending triple. Each is all-or-nothing and the
    # schema cannot say so — a CHECK spanning three columns would refuse the
    # ordinary intermediate state a two-phase confirm creates — so the invariant
    # lives in StaffService, which writes and clears each triple as a unit.
    #
    # The PAIR of triples is what makes *replace* safe: the old photo keeps
    # rendering off `photo_key` until the new one confirms, at which point pending
    # moves to live and the superseded object is deleted.
    photo_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_confirmed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    photo_pending_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_pending_content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_pending_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
