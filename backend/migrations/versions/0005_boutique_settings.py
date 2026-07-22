"""boutique settings: appointment_types, availability_rules/exceptions,
terms_versions (append-only, DB-enforced)

Revision ID: 0005
Revises: 0004
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0005"
down_revision = "0004"
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
    # CHECKs on the bounds that feed E4's refund math live in the DB, not just
    # the service: immutable financial evidence must be safe against any
    # non-router write path.
    op.execute(
        f"""
        CREATE TABLE appointment_types (
            {_STANDARD},
            name TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
            audience TEXT NOT NULL DEFAULT 'all',
            deposit_required BOOLEAN NOT NULL DEFAULT false,
            deposit_amount_agorot INTEGER
                CHECK (deposit_amount_agorot IS NULL OR deposit_amount_agorot > 0),
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # Partial unique: soft delete = archive, so an archived type frees its name.
    op.execute(
        "CREATE UNIQUE INDEX idx_appointment_types_tenant_name_unique "
        "ON appointment_types(tenant_id, name) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("appointment_types"))

    op.execute(
        f"""
        CREATE TABLE availability_rules (
            {_STANDARD},
            day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
            open_time TIME NOT NULL,
            close_time TIME NOT NULL,
            capacity INTEGER NOT NULL DEFAULT 1 CHECK (capacity > 0),
            CHECK (close_time > open_time)
        )
        """
    )
    op.execute(_updated_at_trigger("availability_rules"))
    # E3's slot engine reads the active weekly set on every computation, and
    # each atomic replace accumulates soft-deleted rows the scan must skip.
    op.execute(
        "CREATE INDEX idx_availability_rules_tenant_active "
        "ON availability_rules (tenant_id) WHERE deleted_at IS NULL"
    )

    op.execute(
        f"""
        CREATE TABLE availability_exceptions (
            {_STANDARD},
            date DATE NOT NULL,
            open_time TIME,
            close_time TIME,
            note TEXT
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_availability_exceptions_tenant_date_unique "
        "ON availability_exceptions(tenant_id, date) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("availability_exceptions"))

    op.execute(
        f"""
        CREATE TABLE terms_versions (
            {_STANDARD},
            version INTEGER NOT NULL CHECK (version > 0),
            terms_text TEXT NOT NULL,
            refundable_until_hours_before INTEGER NOT NULL
                CHECK (refundable_until_hours_before >= 0),
            forfeit_percent INTEGER NOT NULL DEFAULT 100
                CHECK (forfeit_percent BETWEEN 0 AND 100),
            created_by UUID NOT NULL
        )
        """
    )
    # PLAIN unique (no partial predicate): nothing is ever deleted from this
    # table, and it doubles as the concurrency backstop for version = max + 1.
    op.execute(
        "CREATE UNIQUE INDEX idx_terms_versions_tenant_version_unique "
        "ON terms_versions(tenant_id, version)"
    )
    # No updated_at trigger: rows are immutable evidence, never updated.

    for table in ("appointment_types", "availability_rules", "availability_exceptions"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)

    # terms_versions: append-only is structural, not conventional. REVOKE first —
    # 0002's ALTER DEFAULT PRIVILEGES auto-granted full CRUD (the 0004 precedent).
    # SELECT stays granted (unlike platform_audit_log) so reads and
    # INSERT … RETURNING work; UPDATE/DELETE are impossible for app_user.
    op.execute("REVOKE ALL ON terms_versions FROM app_user")
    op.execute("GRANT SELECT, INSERT ON terms_versions TO app_user")
    for statement in enable_tenant_rls("terms_versions"):
        op.execute(statement)


def downgrade() -> None:
    for table in (
        "terms_versions",
        "availability_exceptions",
        "availability_rules",
        "appointment_types",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
