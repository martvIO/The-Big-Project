"""walk-in queue: queue_tickets (self-check-in, position computed on read)

Revision ID: 0016
Revises: 0015
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0016"
down_revision = "0015"
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
    # queue_day is a STORED DATE, not `(created_at AT TIME ZONE 'Asia/Jerusalem')::date`.
    # Both forms were probed against a live 16.14 — the naive `created_at::date`
    # really is illegal (date(timestamptz) is STABLE) and the zone-named form
    # really is legal — so this is a choice, not an inability. Three reasons:
    # an expression makes the day the DATABASE's clock and untestable against the
    # injectable Clock; Jerusalem arithmetic lives in Python by rule
    # (storefront/validation.py); and IMMUTABLE is a marking rather than a
    # guarantee, so a tzdata update would silently diverge stored entries from
    # fresh lookups.
    #
    # called_at, requeued_at and skip_count ship with NO writer in F33. The first
    # two are READ here — called_at is what lets the position screen say "go to
    # the counter", requeued_at is half of F33's published ordering — so F58 must
    # not be able to change this feature's read semantics by adding a column.
    # skip_count ships because F58 was scoped to need no migration.
    op.execute(
        f"""
        CREATE TABLE queue_tickets (
            {_STANDARD},
            queue_day DATE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            visit_type TEXT NOT NULL CHECK (visit_type IN ('bride','evening')),
            status TEXT NOT NULL DEFAULT 'waiting'
                CHECK (status IN ('waiting','in_service','done','removed')),
            called_at TIMESTAMPTZ,
            requeued_at TIMESTAMPTZ,
            skip_count INTEGER NOT NULL DEFAULT 0 CHECK (skip_count >= 0),
            marketing_opt_in_at TIMESTAMPTZ
        )
        """
    )
    # ONE index, and deliberately NOT unique. There is no dedup in this feature:
    # the create always creates.
    #
    # The unique `(tenant_id, queue_day, phone) WHERE deleted_at IS NULL AND
    # status IN ('waiting','in_service')` this replaces was deleted for two
    # reasons a later reader must answer before re-adding any uniqueness here.
    # Its partial predicate freed a key only on a status change or a soft delete
    # and F33 writes NEITHER, so one anonymous POST carrying a known mobile took
    # that number's slot for the rest of the boutique day with no remedy anywhere
    # in the shipped product; and the refusal it produced was a free, silent,
    # unbounded presence oracle.
    #
    # What the predicate buys in both directions: `deleted_at IS NULL` keeps the
    # index off soft-deleted rows, and it is deliberately NOT the narrower live
    # status set, because F20's retention sweep needs to see closed rows and a
    # second index for that would be one more thing to keep true. The column
    # order is exactly the prefix the position count filters on, so the count is
    # an index range scan over one day's rows.
    op.execute(
        "CREATE INDEX idx_queue_tickets_tenant_day_active "
        "ON queue_tickets (tenant_id, queue_day) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("queue_tickets"))

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON queue_tickets TO app_user")
    for statement in enable_tenant_rls("queue_tickets"):
        op.execute(statement)


def downgrade() -> None:
    # The index, trigger and policy go with the table. F33 touches no existing
    # table, so there is nothing to un-touch.
    op.execute("DROP TABLE IF EXISTS queue_tickets")
