"""booking idempotency: one live booking per (tenant, customer, instant)

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The structural backstop for the lost-201 retry. A booking commits, the
    # response dies in transit, and the spent verification token turns the
    # client's retry into a 403 whose copy tells the customer to request a new
    # code and resubmit — so she resubmits the SAME appointment and, before
    # this, got a second one. The service converges that retry onto the
    # existing row under the per-tenant advisory lock; this index is what makes
    # a duplicate impossible even for a writer that skips the lock.
    #
    # The predicate is 0008's, deliberately identical: `deleted_at IS NULL AND
    # status <> 'cancelled'`. A no-show or completed booking still occupied the
    # instant, only a cancellation releases it — so a customer who cancels can
    # rebook the very same time, and E4's 'pending_payment' needs no change
    # here for the same reason it needs none on the seat index.
    #
    # It also states something true independently of retries: one person cannot
    # be at two appointments at one instant, whatever their types.
    op.execute(
        "CREATE UNIQUE INDEX idx_bookings_tenant_customer_starts_unique "
        "ON bookings (tenant_id, customer_id, starts_at) "
        "WHERE deleted_at IS NULL AND status <> 'cancelled'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_bookings_tenant_customer_starts_unique")
