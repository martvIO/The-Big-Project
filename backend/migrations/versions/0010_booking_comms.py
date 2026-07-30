"""booking comms: manage token, cancel evidence, scheduled_messages

Revision ID: 0010
Revises: 0009
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0010"
down_revision = "0009"
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
    # The tokenized manage link's credential, stored ONLY as sha256 — the raw
    # value lives in the SMS body and (while a reminder is still pending) on the
    # scheduled_messages row below. NULL on every pre-F16 row until the one-time
    # backfill mints one.
    op.execute("ALTER TABLE bookings ADD COLUMN manage_token_hash TEXT")
    # Cancel evidence, recorded now so E4 #19 can evaluate refund-due vs forfeit
    # from (cancelled_at, starts_at, terms_version_accepted) without a second
    # migration. 'customer' is the token page; 'owner' arrives with F15.
    op.execute("ALTER TABLE bookings ADD COLUMN cancelled_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE bookings ADD COLUMN cancelled_by TEXT "
        "CHECK (cancelled_by IN ('customer', 'owner'))"
    )
    # The lookup path: token possession -> exactly one booking. Partial on
    # NOT NULL so pre-F16 and backfilled-away rows cost nothing, and tenant-first
    # so the index is usable under RLS's tenant predicate.
    op.execute(
        "CREATE INDEX idx_bookings_manage_token ON bookings (tenant_id, manage_token_hash) "
        "WHERE deleted_at IS NULL AND manage_token_hash IS NOT NULL"
    )

    # The SCHEDULE state, never the evidence — that stays message_log's job, and
    # NotificationService remains its single writer.
    #
    # `manage_token` holds the raw link token while the row is pending, and is
    # cleared the moment the row reaches a terminal status. It has to exist:
    # bookings stores only a sha256, the reminder must carry the SAME link as the
    # confirmation (a fresh token would kill the link in a text the customer is
    # still reading — Interview Q4 makes the 2-24h reminder fire seconds after
    # the confirmation), and the worker sends hours or days later in another
    # process. Recorded as a spec amendment in specs/booking-comms.md.
    op.execute(
        f"""
        CREATE TABLE scheduled_messages (
            {_STANDARD},
            booking_id UUID NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('reminder')),
            send_after TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'sent', 'cancelled', 'failed')),
            manage_token TEXT
        )
        """
    )
    # THE idempotency key: at most one PENDING message of a kind per booking, so
    # a double-schedule converges on one row instead of sending twice. Terminal
    # rows are excluded deliberately — a reschedule must be able to leave a
    # 'sent' reminder in place and add a fresh pending one for the new time.
    op.execute(
        "CREATE UNIQUE INDEX idx_scheduled_messages_pending_unique "
        "ON scheduled_messages (tenant_id, booking_id, kind) "
        "WHERE deleted_at IS NULL AND status = 'pending'"
    )
    # The poller's claim: one range scan per tenant per tick.
    op.execute(
        "CREATE INDEX idx_scheduled_messages_due "
        "ON scheduled_messages (tenant_id, send_after) "
        "WHERE deleted_at IS NULL AND status = 'pending'"
    )
    op.execute(_updated_at_trigger("scheduled_messages"))

    # The STANDARD FORCE RLS policy, no exception (D6). The poller stays inside
    # the tenancy posture by enumerating tenants (that table is deliberately
    # RLS-free) and claiming one tenant_session at a time: cross-tenant leakage
    # is the recorded existential risk, and the first background reader in the
    # codebase does not get to be the first RLS exception.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON scheduled_messages TO app_user")
    for statement in enable_tenant_rls("scheduled_messages"):
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scheduled_messages")
    op.execute("DROP INDEX IF EXISTS idx_bookings_manage_token")
    for column in ("cancelled_by", "cancelled_at", "manage_token_hash"):
        op.execute(f"ALTER TABLE bookings DROP COLUMN IF EXISTS {column}")
