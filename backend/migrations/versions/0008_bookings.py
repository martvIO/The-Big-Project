"""booking core: customers, bookings (seat-indexed slot claim)

Revision ID: 0008
Revises: 0007
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0008"
down_revision = "0007"
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
        CREATE TABLE customers (
            {_STANDARD},
            phone TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """
    )
    # One customer per phone per tenant. The SAME phone under two tenants is two
    # customers, deliberately: a bride who visits two boutiques is not one
    # cross-tenant identity, and the partial predicate keeps a soft-deleted
    # record from blocking her return.
    op.execute(
        "CREATE UNIQUE INDEX idx_customers_tenant_phone_unique "
        "ON customers (tenant_id, phone) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("customers"))

    # Snapshot columns (appointment_type_name, dress_name, dress_size) are
    # copied at booking time: the owner may rename a type or archive a dress,
    # and a booking must render as what the customer agreed to. dress_id is kept
    # alongside so the image resolves at read time — a storage key would
    # duplicate the media lifecycle and a presigned URL would store something
    # that expires.
    op.execute(
        f"""
        CREATE TABLE bookings (
            {_STANDARD},
            customer_id UUID NOT NULL,
            appointment_type_id UUID NOT NULL,
            starts_at TIMESTAMPTZ NOT NULL,
            seat_index INTEGER NOT NULL CHECK (seat_index >= 1 AND seat_index <= 1000),
            status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed','cancelled','no_show','completed')),
            attendance_confirmed_at TIMESTAMPTZ,
            terms_version_accepted INTEGER NOT NULL CHECK (terms_version_accepted > 0),
            terms_accepted_at TIMESTAMPTZ NOT NULL,
            appointment_type_name TEXT NOT NULL,
            dress_id UUID,
            dress_name TEXT,
            dress_size TEXT,
            notes TEXT
        )
        """
    )
    # THE oversell guard, and it is structural at ANY capacity — which a plain
    # unique on (tenant, starts_at) would not be. The service claims
    # seat_index = booked + 1 under a per-tenant advisory lock; this index is
    # what makes a lost race an IntegrityError rather than a second bride.
    #
    # `status <> 'cancelled'` and not `= 'confirmed'`: a no-show or completed
    # booking still OCCUPIED its seat, and only a cancellation frees it. That is
    # also what keeps this index correct when E4 adds 'pending_payment' — a held
    # seat is an occupied seat, so E4 widens the CHECK and leaves this alone.
    op.execute(
        "CREATE UNIQUE INDEX idx_bookings_slot_seat_unique "
        "ON bookings (tenant_id, starts_at, seat_index) "
        "WHERE deleted_at IS NULL AND status <> 'cancelled'"
    )
    # The claim counts seats at one instant and F12's grid counts them across a
    # window; both are (tenant_id, starts_at) range scans.
    op.execute(
        "CREATE INDEX idx_bookings_tenant_starts "
        "ON bookings (tenant_id, starts_at) WHERE deleted_at IS NULL"
    )
    # F15's list and F16's reminder sweep both read a tenant's bookings by
    # customer; without this that is a full scan per owner page.
    op.execute(
        "CREATE INDEX idx_bookings_tenant_customer "
        "ON bookings (tenant_id, customer_id) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("bookings"))

    for table in ("customers", "bookings"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)


def downgrade() -> None:
    for table in ("bookings", "customers"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
