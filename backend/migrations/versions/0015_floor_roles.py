"""floor roles + break status: widen the role CHECK and record who stepped away

Revision ID: 0015
Revises: 0014
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

_ROLES = "'owner', 'shift_manager', 'reception', 'sales_assistant', 'seamstress'"


def upgrade() -> None:
    # DROP + ADD, not ALTER CONSTRAINT: Postgres has no way to change a CHECK's
    # expression in place. ADD CONSTRAINT validates every existing row — which is
    # 0011's own claim — and a WIDENING can only ever admit rows that were
    # already legal, so this cannot fail on live data. Proven on a POPULATED
    # table by tests/test_migrations.py::
    # test_adding_the_widened_role_check_validates_existing_rows, the shape
    # 0011's claim is proven with.
    #
    # Declined: NOT VALID + a later VALIDATE CONSTRAINT. That is the right
    # pattern for a NARROWING constraint on a large table; here the table is a
    # single-digit staff list per tenant, so the two-step buys a lock avoidance
    # nothing needs and leaves a window where the constraint means nothing.
    op.execute("ALTER TABLE staff_users DROP CONSTRAINT staff_users_role_check")
    op.execute(
        f"ALTER TABLE staff_users ADD CONSTRAINT staff_users_role_check CHECK (role IN ({_ROLES}))"
    )
    # When this staffer stepped away. NULL means "not on a break" and is the ONLY
    # sentinel; a non-null value is both the fact and the since-when the card
    # renders. NOT a status column (spec D2): 'occupied' is F36's
    # fitting_room_assignments index, not a value anything here may write, and a
    # status column would oblige F36 to double-write into this table on every
    # claim and release.
    #
    # Deliberately absent, each for a verified reason, stated so a reviewer can
    # check the list is COMPLETE rather than merely short:
    #
    #   * No GRANT. 0003 issued table-level
    #     `GRANT SELECT, INSERT, UPDATE, DELETE ON staff_users TO app_user`;
    #     table grants are column-agnostic and no column-level grant was ever
    #     issued here. (The ALTER DEFAULT PRIVILEGES gotcha in .claude/CLAUDE.md
    #     is about newly CREATED tables, not added columns.)
    #   * No enable_tenant_rls. RLS is a table property, forced on staff_users
    #     since 0003. F57 adds no table, and
    #     test_every_tenant_id_table_has_forced_rls staying green UNEDITED is the
    #     assertion that none snuck in.
    #   * No _updated_at_trigger. trg_staff_users_updated_at exists from 0003.
    #   * No index, no default, no NOT NULL, no backfill. Nothing filters or
    #     sorts on this column — list_live already returns the tenant's whole
    #     staff list and the status derivation reads the column off rows it has
    #     in hand — so a partial index would serve no reader and cost every
    #     write.
    op.execute("ALTER TABLE staff_users ADD COLUMN break_started_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE staff_users DROP COLUMN IF EXISTS break_started_at")
    op.execute("ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS staff_users_role_check")
    # Deliberately NOT `IF EXISTS`-shaped and deliberately ABLE TO FAIL: a row
    # holding one of the three new roles must BLOCK the narrowing rather than be
    # left sitting past a constraint its own value violates. Asserted by
    # test_the_downgrade_refuses_to_narrow_past_a_floor_role_row.
    op.execute(
        "ALTER TABLE staff_users ADD CONSTRAINT staff_users_role_check "
        "CHECK (role IN ('owner', 'shift_manager'))"
    )
