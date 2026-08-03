"""customer CRM: the notes the owner writes and the tags she files a bride under

Revision ID: 0018
Revises: 0014
"""

from alembic import op

# 0015 is claimed TWICE in flight right now — 0015_floor_roles.py and
# 0015_deposit_flow.py, different filenames, so git merges both cleanly and
# alembic then reports multiple heads at runtime. F53 declines to be the third
# claimant. A non-contiguous id is valid: alembic follows the linked list, not
# the sequence (`alembic history` prints `0014 -> 0018 (head)`), so only
# down_revision moves at rebase. Re-resolve BOTH from `alembic heads` on the
# rebased branch — never from the plan document.
revision = "0018"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Two columns the owner console writes and nothing else reads. `notes` is a
    # paragraph that accretes across a year of fittings (nullable — NULL and ''
    # both mean "nothing written", and the service treats '' as the cleared
    # value). `tags` is the first array column in this codebase; NOT NULL
    # DEFAULT '{}' so a row never has to answer "no tags" with NULL, which the
    # ORM would surface as None where every reader expects a list.
    #
    # The default costs no table rewrite: PG 11+ stores it in pg_attribute
    # (atthasmissing = t, attmissingval = {"{}"}) and materialises it lazily on
    # read. Verified on the live cluster, not assumed.
    #
    # Deliberately absent, each for a verified reason, stated so a reviewer can
    # check the list is COMPLETE rather than merely short:
    #
    #   * No GRANT. 0008 issued table-level
    #     `GRANT SELECT, INSERT, UPDATE, DELETE ON customers TO app_user`; table
    #     grants are column-agnostic and no column-level grant was ever issued
    #     here. (The ALTER DEFAULT PRIVILEGES gotcha in .claude/CLAUDE.md is
    #     about newly CREATED tables, not added columns.)
    #   * No enable_tenant_rls. RLS is a table property, forced on customers
    #     since 0008. F53 adds no table — test_every_tenant_id_table_has_forced_rls
    #     staying green UNEDITED is the assertion that none snuck in.
    #   * No _updated_at_trigger. trg_customers_updated_at exists from 0008.
    #   * No index, no CHECK, no backfill. NOT NULL DEFAULT '{}' is the backfill,
    #     and the three indexes a reader will ask about are all upgrade paths
    #     with thresholds rather than omissions:
    #
    #     -- Customer search, at ~50k live customer rows per tenant. A btree
    #     -- cannot serve an unanchored %term% at all; only pg_trgm can, and
    #     -- CREATE EXTENSION is a privilege this migration does not have.
    #     CREATE EXTENSION pg_trgm;
    #     CREATE INDEX idx_customers_name_trgm ON customers
    #       USING gin (name gin_trgm_ops) WHERE deleted_at IS NULL;
    #     CREATE INDEX idx_customers_phone_trgm ON customers
    #       USING gin (phone gin_trgm_ops) WHERE deleted_at IS NULL;
    #
    #     -- The customer SMS log, at ~100k message_log rows per tenant. A PAIR
    #     -- or nothing: the predicate ORs across two columns, so the planner
    #     -- needs a BitmapOr and one index alone buys nothing.
    #     CREATE INDEX idx_message_log_tenant_phone ON message_log
    #       (tenant_id, phone) WHERE deleted_at IS NULL;
    #     CREATE INDEX idx_message_log_tenant_booking ON message_log
    #       (tenant_id, booking_id) WHERE deleted_at IS NULL;
    #
    #     -- Tag filtering, the day a reader exists. Nothing filters by tags
    #     -- today, and a GIN index with no reader is a cost on every write.
    #     CREATE INDEX idx_customers_tags ON customers
    #       USING gin (tags) WHERE deleted_at IS NULL;
    op.execute("ALTER TABLE customers ADD COLUMN notes TEXT")
    op.execute("ALTER TABLE customers ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS tags")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS notes")
