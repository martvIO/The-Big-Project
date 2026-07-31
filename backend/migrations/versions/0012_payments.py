"""payments: per-tenant gateway credentials + the money row

Revision ID: 0012
Revises: 0011
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0012"
down_revision = "0011"
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
    # NEITHER table touches `bookings`. The 'pending_payment' status widening is
    # F19's (app/models/constants.py:48 says so); claiming it here would widen a
    # CHECK this feature has no writer for.
    op.execute(
        f"""
        CREATE TABLE tenant_gateway_credentials (
            {_STANDARD},
            -- A SECURITY CONTROL, not only the no-speculative-values rule (D8).
            -- payment_provider='fake' is a production boot failure, so in
            -- production this table can hold NO ROWS AT ALL until a real
            -- adapter's own migration widens this CHECK alongside it. The window
            -- in which real merchant credentials could be stored by a fake
            -- secret box does not exist.
            provider          TEXT NOT NULL CHECK (provider IN ('fake')),
            -- base64 SecretBox blob. NEVER a plaintext field, NEVER logged, and
            -- never reachable through the API — there is no read path for it.
            ciphertext        TEXT NOT NULL,
            -- Which box + key wrote it. A rotation must know what it is
            -- replacing, which is why UnconfiguredSecretBox.key_ref raises
            -- rather than answering None.
            key_ref           TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'valid'
                              CHECK (status IN ('valid', 'invalid')),
            -- NOT NULL is the invariant that makes D4 structural: credentials
            -- are pinged BEFORE they are stored, so "stored but unvalidated" is
            -- not a state this schema can represent. That is stronger than a
            -- service-level rule, and it is free.
            last_validated_at TIMESTAMPTZ NOT NULL,
            -- Scrubbed + truncated provider detail. Operators only; held to the
            -- same containment as message_log.error.
            validation_error  TEXT,
            created_by        UUID NOT NULL
        )
        """
    )
    # One ACTIVE credential set per (tenant, provider). Rotation soft-deletes and
    # inserts (D6), so the superseded row is the rotation trail an incident
    # review needs and "one active set" is structural rather than conventional.
    op.execute(
        "CREATE UNIQUE INDEX idx_tenant_gateway_credentials_active_unique "
        "ON tenant_gateway_credentials (tenant_id, provider) WHERE deleted_at IS NULL"
    )
    # D20's verification lookup: the newest row for (tenant, provider) REGARDLESS
    # of deleted_at and status. Not partial, deliberately — the whole point is
    # that it still resolves after a disconnect or an 'invalid' flip, because
    # verifying a signature is reading evidence about money that has ALREADY
    # moved, not authorisation to move more.
    op.execute(
        "CREATE INDEX idx_tenant_gateway_credentials_newest "
        "ON tenant_gateway_credentials (tenant_id, provider, created_at DESC)"
    )
    op.execute(_updated_at_trigger("tenant_gateway_credentials"))

    op.execute(
        f"""
        CREATE TABLE payments (
            {_STANDARD},
            booking_id              UUID NOT NULL,
            -- Snapshot: which gateway took this money. Not a read-through.
            provider                TEXT NOT NULL,
            -- Also a snapshot (the 0008 appointment_type_name/dress_name
            -- argument): the owner can change the deposit at any time, and the
            -- amount charged must render as what the customer agreed to.
            amount_agorot           INTEGER NOT NULL CHECK (amount_agorot > 0),
            status                  TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending','paid','failed','expired',
                                                      'refund_due','refunded','forfeited')),
            provider_session_id     TEXT,
            provider_transaction_id TEXT,
            hold_expires_at         TIMESTAMPTZ,
            paid_at                 TIMESTAMPTZ,
            error                   TEXT
        )
        """
    )
    # Webhook replay protection BACKSTOP, the 0009 argument read correctly (D24):
    # the service converges a redelivery under the guarded UPDATE and this index
    # is what stops a writer that skips it. It is NOT the mechanism — on the
    # settle path there is no insert for it to refuse, only an update to one row.
    op.execute(
        "CREATE UNIQUE INDEX idx_payments_provider_txn_unique "
        "ON payments (tenant_id, provider, provider_transaction_id) "
        "WHERE deleted_at IS NULL AND provider_transaction_id IS NOT NULL"
    )
    # At most one live hold per booking — the idx_scheduled_messages_pending_unique
    # trick, and D23's backstop for a writer that skips the advisory lock.
    op.execute(
        "CREATE UNIQUE INDEX idx_payments_booking_pending_unique "
        "ON payments (tenant_id, booking_id) WHERE deleted_at IS NULL AND status = 'pending'"
    )
    op.execute(
        "CREATE INDEX idx_payments_tenant_booking "
        "ON payments (tenant_id, booking_id) WHERE deleted_at IS NULL"
    )
    # F19's expiry sweeper: "pending holds whose clock has run out", per tenant.
    op.execute(
        "CREATE INDEX idx_payments_hold_expiry "
        "ON payments (tenant_id, hold_expires_at) "
        "WHERE deleted_at IS NULL AND status = 'pending'"
    )
    op.execute(_updated_at_trigger("payments"))

    # Grants DEPART from the house default on both tables (D7). REVOKE first,
    # the 0004/0005 dance: migration 0002's ALTER DEFAULT PRIVILEGES auto-granted
    # full CRUD to app_user, so a plain GRANT would not remove DELETE.
    #
    # A hard DELETE of a payment row destroys financial evidence; of a credential
    # row, the rotation trail. UPDATE stays because soft-delete and every status
    # transition need it. SELECT stays because both tables are read on the hot
    # path — and note the SCHEMA gotcha does NOT bite here: with SELECT granted,
    # INSERT … RETURNING works, so no client-side id/timestamp generation is
    # needed. Erasure is column blanking, not row removal (D21), which revoked
    # DELETE does not block.
    for table in ("tenant_gateway_credentials", "payments"):
        op.execute(f"REVOKE ALL ON {table} FROM app_user")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO app_user")
        # The standard FORCE RLS policy, no exception. This is also what makes
        # test_tenant_isolation's mechanical sweep pick both tables up with no
        # test edit at all.
        for statement in enable_tenant_rls(table):
            op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS payments")
    op.execute("DROP TABLE IF EXISTS tenant_gateway_credentials")
