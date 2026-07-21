"""auth: staff_users, sessions, audit_log (all tenant-scoped, RLS-forced)

Revision ID: 0003
Revises: 0002
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0003"
down_revision = "0002"
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
    op.execute(
        f"""
        CREATE TABLE staff_users (
            {_STANDARD},
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'owner'
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_staff_users_tenant_email_unique "
        "ON staff_users(tenant_id, email) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("staff_users"))

    op.execute(
        f"""
        CREATE TABLE sessions (
            {_STANDARD},
            staff_user_id UUID NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    # Active-session lookup (hot path): token_hash where not soft-deleted.
    op.execute(
        "CREATE INDEX idx_sessions_token_hash_active "
        "ON sessions(token_hash) WHERE deleted_at IS NULL"
    )
    # Supports a future expired/revoked-session sweep job.
    op.execute("CREATE INDEX idx_sessions_expires_at ON sessions(expires_at)")
    op.execute(_updated_at_trigger("sessions"))

    op.execute(
        f"""
        CREATE TABLE audit_log (
            {_STANDARD},
            actor_id UUID,
            action TEXT NOT NULL,
            entity TEXT,
            details JSONB NOT NULL DEFAULT '{{}}'::jsonb
        )
        """
    )
    op.execute("CREATE INDEX idx_audit_log_tenant_created ON audit_log(tenant_id, created_at)")
    op.execute(_updated_at_trigger("audit_log"))

    for table in ("staff_users", "sessions", "audit_log"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)


def downgrade() -> None:
    for table in ("audit_log", "sessions", "staff_users"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
