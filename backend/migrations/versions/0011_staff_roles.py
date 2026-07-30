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
    # Two values only: reception/seamstress/sales join when E6-proper gives them
    # a consumer (the ScheduledMessageKind rule — no speculative kinds).
    op.execute(
        "ALTER TABLE staff_users ADD CONSTRAINT staff_users_role_check "
        "CHECK (role IN ('owner', 'shift_manager'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS staff_users_role_check")
