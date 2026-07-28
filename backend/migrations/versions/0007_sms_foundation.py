"""sms foundation: message_log (Spam-Law evidence trail), otp_codes

Revision ID: 0007
Revises: 0006
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0007"
down_revision = "0006"
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
    # Full CRUD grants, unlike terms_versions: message_log is operational
    # telemetry with a compliance duty (status transitions UPDATE it), not
    # immutable financial evidence. Soft-delete discipline still applies.
    op.execute(
        f"""
        CREATE TABLE message_log (
            {_STANDARD},
            phone TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN
                ('otp','confirmation','reminder','owner_cancel','owner_reschedule')),
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','sent','failed')),
            provider_message_id TEXT,
            error TEXT,
            booking_id UUID
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_message_log_tenant_created "
        "ON message_log (tenant_id, created_at) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("message_log"))

    # attempts CHECK at 50 = 10x the service cap of 5 (the 0005 absurdity-ceiling
    # convention): the DB bound stops a broken write path, it does not encode policy.
    op.execute(
        f"""
        CREATE TABLE otp_codes (
            {_STANDARD},
            phone TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0
                CHECK (attempts >= 0 AND attempts <= 50),
            consumed_at TIMESTAMPTZ,
            verification_token_hash TEXT,
            verification_expires_at TIMESTAMPTZ,
            verification_consumed_at TIMESTAMPTZ
        )
        """
    )
    # The send path reads "the single live code for this phone" on every verify
    # and resend; the partial predicate keeps consumed and invalidated rows out
    # of the scan the same way idx_availability_rules_tenant_active does.
    op.execute(
        "CREATE INDEX idx_otp_codes_tenant_phone_active "
        "ON otp_codes (tenant_id, phone) WHERE consumed_at IS NULL AND deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("otp_codes"))

    for table in ("message_log", "otp_codes"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)


def downgrade() -> None:
    for table in ("otp_codes", "message_log"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
