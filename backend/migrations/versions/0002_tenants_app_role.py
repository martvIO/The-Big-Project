"""tenants table, update_updated_at trigger function, non-owner app_user role

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Shared trigger function — created once here, reused by every later table.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    op.execute(
        """
        CREATE TABLE tenants (
          id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
          slug TEXT NOT NULL,
          name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          settings JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ,
          deleted_at TIMESTAMPTZ
        )
        """
    )
    # Partial unique index: active slugs are unique, soft-deleted slugs are reclaimable.
    op.execute(
        "CREATE UNIQUE INDEX idx_tenants_slug_unique ON tenants(slug) WHERE deleted_at IS NULL"
    )
    op.execute(
        """
        CREATE TRIGGER trg_tenants_updated_at
        BEFORE UPDATE ON tenants
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        """
    )

    # Non-superuser, non-owner group role for the application. RLS FORCE binds it —
    # superusers and table owners would bypass RLS (Feature 1 security review).
    # Deployments create a LOGIN role granted membership here (tests do the same).
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
            CREATE ROLE app_user NOLOGIN;
          END IF;
        END
        $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user")
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_tenants_updated_at ON tenants")
    op.execute("DROP TABLE IF EXISTS tenants")
    # app_user role and update_updated_at() are intentionally kept: the role is
    # cluster-wide (other databases may reference it) and the function is shared.
