"""atelier: alteration_tickets (five nullable stamps, no status column)

Revision ID: 0019
Revises: 0018

The number was resolved from `alembic heads` at build time and is not reserved:
0017's header records what reserving one costs, and F33 then lived it — two
files declaring revision "0016", different filenames, a textually clean merge
and nothing in review looking wrong. If this branch rebases behind another
migration, the fix is three edits to this one file (the filename, `revision`,
`down_revision`) and `test_exactly_one_migration_head` is what catches a forgotten
one, in half a second, in the fast suite.
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

_STANDARD = """
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
"""


def _updated_at_trigger(table: str) -> str:
    return f"""
        CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """


def upgrade() -> None:
    # THE FIVE STAMPS ARE THE STATE MACHINE AND THERE IS NO status COLUMN (D2,
    # pre-decided #39, left standing by the 2026-07-31 ATELIER ruling). The
    # current stage is the RIGHTMOST stamped column; an earlier NULL beside a
    # later stamp means "that stage was never separately recorded", not that it
    # did not happen — a hem taken from intake straight to ready in one sitting
    # is normal. A status column beside these would be two representations of
    # one fact that a concurrent writer can desynchronise, and it answers
    # neither metric this epic promises (median time-in-state IS
    # ready_at - in_progress_at).
    #
    # ALL FIVE ARE NULLABLE, intake_at included, and the symmetry is deliberate:
    # the INSERT always stamps intake_at, but making it NOT NULL would make the
    # block four-plus-one in the DDL and force every later reader — F42's load
    # query, F44's medians — to know which one is special.
    #
    # No ordering CHECK between them. A `CHECK (in_progress_at IS NULL OR
    # intake_at IS NOT NULL)` chain would forbid exactly the legitimate skip
    # above; the invariant that matters (never stamp BEHIND the current stage)
    # is one clause in the write predicate instead of ten in the DDL.
    #
    # dress_id ships with NO WRITER REACHABLE FROM THIS CONSOLE. F41's intake
    # dialog sends the free-text dress_name alone and dress_id: null — the only
    # dress source is GET /manage/dresses, whose router admits owner and
    # shift_manager while this feature's intake admits a seamstress, and this
    # board renders no image, so the column has no reader on this surface. The
    # SERVER path is built and tested and F43 is its caller. F33's skip_count
    # precedent, verbatim: one nullable column in the migration that creates the
    # table is cheaper than a migration in the feature that was scoped not to
    # have one.
    op.execute(
        f"""
        CREATE TABLE alteration_tickets (
            {_STANDARD},
            customer_id UUID NOT NULL,
            due_date DATE NOT NULL,
            effort_minutes INTEGER NOT NULL CHECK (effort_minutes > 0 AND effort_minutes <= 1440),
            assigned_staff_user_id UUID,
            dress_id UUID,
            dress_name TEXT,
            dress_size TEXT,
            notes TEXT,
            intake_at      TIMESTAMPTZ,
            in_progress_at TIMESTAMPTZ,
            qc_at          TIMESTAMPTZ,
            ready_at       TIMESTAMPTZ,
            delivered_at   TIMESTAMPTZ
        )
        """
    )
    # ONE index, partial, and NOT unique. `(tenant_id, due_date)` is exactly the
    # filter-then-sort the board read performs: one tenant's live tickets by
    # bride-date rank. `WHERE deleted_at IS NULL` keeps the index off
    # soft-deleted rows, which is every row this surface never reads.
    #
    # There is deliberately NO uniqueness of any kind beyond the primary key:
    # two tickets for one bride on one dress is legitimate (a gown and a
    # going-away dress; a re-do), so there is nothing here that is unique. A
    # later reader who wants one must first say which of those pairs they intend
    # to refuse — test_alteration_tickets_has_no_unique_index_but_the_primary_key
    # is where that conversation starts.
    #
    # Declined: an index on assigned_staff_user_id. F42's load query
    # (SUM(effort_minutes) … GROUP BY assigned_staff_user_id) is its only
    # reader, and F42 has a migration of its own — the feature that measures the
    # query buys the index. Same for (tenant_id, customer_id) and for any of the
    # five stamps.
    op.execute(
        "CREATE INDEX idx_alteration_tickets_tenant_due "
        "ON alteration_tickets (tenant_id, due_date) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("alteration_tickets"))

    # Table-level and column-agnostic (0003_auth.py:83-84's precedent), and no
    # REVOKE-first dance: that is terms_versions' and platform_audit_log's
    # append-only shape, and this table is ordinary CRUD. Nothing FAILS if this
    # GRANT is dropped until the first app-role read, which then reads
    # `permission denied` — the isolation suite is where that surfaces, not
    # here.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON alteration_tickets TO app_user")
    for statement in enable_tenant_rls("alteration_tickets"):
        op.execute(statement)


def downgrade() -> None:
    # The index, trigger and policy go with the table. F41 touches no existing
    # table, so there is nothing to un-touch.
    op.execute("DROP TABLE IF EXISTS alteration_tickets")
