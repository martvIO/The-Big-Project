"""client portal: customer_sessions + customers.bell_seen_at (F24's session store)

Revision ID: 0027
Revises: 0026

Built as 0027 / down_revision 0026 — resolved from `alembic heads` in the F24
worktree on the day of writing (F22's waitlist had already merged 0026), and
re-resolved immediately before the pre-push rebase. A reserved-but-wrong number
does not fail politely: alembic refuses a branched history outright and every
db-marked test errors at fixture setup.
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0027"
down_revision = "0026"
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
    # A SEPARATE table from `sessions`, never a widening of it (spec D2):
    # `sessions.staff_user_id` is NOT NULL, so a customer row could not exist
    # there without making that column nullable — and the moment staff and
    # customer sessions share one lookup path, a bug in either resolves the
    # wrong principal. Two tables, two cookies, two dependencies.
    #
    # `customer_id` carries no FK (house rule) and is validated in the app.
    # `token_hash` is sha256 of a 256-bit `generate_session_token` — the raw
    # token exists only in the cookie, exactly as the staff table stores it.
    # `expires_at` is a FIXED instant with no sliding renewal (D2): renewal is
    # a write on every read, and the remedy for expiry is one OTP.
    op.execute(
        f"""
        CREATE TABLE customer_sessions (
            {_STANDARD},
            customer_id UUID NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    # The authenticated-request lookup: every portal call resolves its cookie
    # through this one. `WHERE deleted_at IS NULL` is not an optimisation — a
    # logout and an erase both revoke by soft-delete, so without the predicate
    # the index still offers revoked rows to the planner and the liveness check
    # moves entirely into the heap.
    op.execute(
        "CREATE INDEX idx_customer_sessions_token "
        "ON customer_sessions (tenant_id, token_hash) WHERE deleted_at IS NULL"
    )
    # The erase-revocation path (D2). F20's subject-erase revokes every live
    # session this customer holds inside its own transaction; without this
    # index that statement is a sequential scan taken while the per-tenant
    # advisory lock is held, i.e. behind every concurrent booking.
    op.execute(
        "CREATE INDEX idx_customer_sessions_customer "
        "ON customer_sessions (tenant_id, customer_id) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("customer_sessions"))

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON customer_sessions TO app_user")
    for statement in enable_tenant_rls("customer_sessions"):
        op.execute(statement)

    # The bell's whole read-state model (D6): one timestamp, no per-item rows.
    # NULLABLE WITH NO DEFAULT deliberately — NULL is the only spelling of
    # "never opened the bell", so every message is unread until she looks. A
    # `DEFAULT now()` would make that state unreachable for existing rows and
    # silently zero the badge for every customer the platform already has.
    op.execute("ALTER TABLE customers ADD COLUMN bell_seen_at TIMESTAMPTZ")


def downgrade() -> None:
    # The indexes, trigger and policy go with the table. The column is the only
    # thing F24 added to an existing table; `message_log`, `scheduled_messages`
    # and `bookings` are untouched (spec D7), so there is nothing else to undo.
    op.execute("DROP TABLE IF EXISTS customer_sessions")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS bell_seen_at")
