"""platform_audit_log — append-only, platform-scoped operator trail

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOTE: target_tenant_id, NOT tenant_id — a tenant_id column would trip the
    # forced-RLS metadata-scan test; this table is intentionally platform-wide.
    op.execute(
        """
        CREATE TABLE platform_audit_log (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            operator TEXT NOT NULL,
            action TEXT NOT NULL,
            target_tenant_id UUID,
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_platform_audit_log_target "
        "ON platform_audit_log(target_tenant_id, created_at)"
    )
    op.execute("GRANT SELECT, INSERT ON platform_audit_log TO app_user")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS platform_audit_log")
