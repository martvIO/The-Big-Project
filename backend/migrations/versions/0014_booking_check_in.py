"""booking check-in: the arrival timestamp the live board writes

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # When a staff member recorded that this person is physically in the
    # boutique. NOT a fifth BookingStatus (spec D1): status says what became of
    # the appointment, this says whether she is in the building, and the two are
    # true at once. NULL means "not arrived (yet)" and is the only sentinel —
    # there is no 'left' timestamp in v1.
    #
    # Deliberately absent, each for a verified reason, stated so a reviewer can
    # check the list is COMPLETE rather than merely short:
    #
    #   * No GRANT. 0008 issued table-level
    #     `GRANT SELECT, INSERT, UPDATE, DELETE ON bookings TO app_user`; table
    #     grants are column-agnostic and no column-level grant was ever issued
    #     here. (The ALTER DEFAULT PRIVILEGES gotcha in .claude/CLAUDE.md is
    #     about newly CREATED tables, not added columns.)
    #   * No enable_tenant_rls. RLS is a table property, already forced by 0008.
    #     test_every_tenant_id_table_has_forced_rls stays green unedited, and
    #     that is the assertion that no table snuck in here.
    #   * No _updated_at_trigger. trg_bookings_updated_at exists from 0008.
    #   * No index, no CHECK, no default, no backfill. Nothing filters or sorts
    #     on this column — the board reads the day and renders the value — so a
    #     partial index would serve no reader and cost every write.
    op.execute("ALTER TABLE bookings ADD COLUMN checked_in_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS checked_in_at")
