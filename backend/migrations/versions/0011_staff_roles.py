"""staff roles: pin the role set now that a second role exists

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD CONSTRAINT validates existing rows too — every pre-0011 row carries
    # the 'owner' default, so this cannot fail on live data. Both halves of that
    # claim are proven on a POPULATED table by
    # tests/test_migrations.py::test_adding_the_role_check_validates_existing_rows.
    # Two values only at the time: reception/seamstress/sales were to join when
    # E6-proper gave them a consumer (the ScheduledMessageKind rule — no
    # speculative kinds). The floor program was that consumer and F57's migration
    # widened this constraint to five, so the bar this comment set was MET rather
    # than waived. Left in the past tense rather than deleted: it is the record
    # of why the set was two for as long as it was.
    op.execute(
        "ALTER TABLE staff_users ADD CONSTRAINT staff_users_role_check "
        "CHECK (role IN ('owner', 'shift_manager'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS staff_users_role_check")
