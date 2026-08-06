"""booking waitlist: waitlist_entries (F22's join model; F23 reads it FIFO)

Revision ID: 0026
Revises: 0025

Built as 0026 / down_revision 0025 — resolved from `alembic heads` on the day of
writing, and re-resolved immediately before the pre-push rebase (0018's header
records the renumber-at-rebase hazard this paragraph inherits).
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0026"
down_revision = "0025"
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
    # `day` is a STORED Jerusalem DATE computed in Python, 0018's ruling
    # inherited whole — except here the customer picks it rather than the clock
    # stamping it, so the day-window validation lives in app/waitlist/validation.
    #
    # `phone` is normalize_israeli_mobile output, matching customers.phone
    # spelling, which is what makes the F20 export/erase joins reachable.
    #
    # The CHECK ships ALL FIVE lifecycle states while F22 writes only 'waiting'
    # (join) and 'cancelled' (owner cancel): the lifecycle is F23's contract,
    # pinned here where the cascade cannot re-litigate it. F23's offer
    # bookkeeping (offered_at, offer token hash, expiry cursor) is F23's own
    # additive migration — 0018's unwritten-column apology is not repeated.
    op.execute(
        f"""
        CREATE TABLE waitlist_entries (
            {_STANDARD},
            day DATE NOT NULL,
            appointment_type_id UUID NOT NULL,
            phone TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting'
                CHECK (status IN ('waiting','offered','claimed','expired','cancelled'))
        )
        """
    )
    # One ACTIVE entry per (tenant, phone, day, type). 0018 deleted this table's
    # queue-side twin and demanded any later uniqueness answer its two findings
    # AT THE INDEX — answered here:
    #   * no presence oracle — the refusal is only reachable through an
    #     OTP-proven caller (the join consumes a verification token first), so
    #     it reveals the caller's own state to herself and nothing to anyone
    #     else;
    #   * no stuck key — cancelled/claimed/expired leave the predicate, the
    #     owner cancel (D5) is the in-product remedy F33 lacked, and a stale
    #     'waiting' key blocks only re-joining a PAST day, which is unbookable
    #     anyway.
    op.execute(
        "CREATE UNIQUE INDEX idx_waitlist_entries_active_unique "
        "ON waitlist_entries (tenant_id, phone, day, appointment_type_id) "
        "WHERE deleted_at IS NULL AND status IN ('waiting','offered')"
    )
    # The list/cascade read path: one day's entries, FIFO by created_at.
    # deleted_at-only predicate so F20's retention sweep sees closed rows —
    # 0018's reasoning, inherited verbatim.
    op.execute(
        "CREATE INDEX idx_waitlist_entries_tenant_day "
        "ON waitlist_entries (tenant_id, day) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("waitlist_entries"))

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON waitlist_entries TO app_user")
    for statement in enable_tenant_rls("waitlist_entries"):
        op.execute(statement)


def downgrade() -> None:
    # The indexes, trigger and policy go with the table. F22 touches no existing
    # table, so there is nothing to un-touch.
    op.execute("DROP TABLE IF EXISTS waitlist_entries")
