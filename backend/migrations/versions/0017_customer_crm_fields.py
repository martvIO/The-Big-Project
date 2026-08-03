"""customer CRM: the notes the owner writes and the tags she files a bride under

Revision ID: 0017
Revises: 0014
"""

from alembic import op

# Resolved from `alembic heads` on the REBASED branch, which is the only source
# this repo trusts for a revision id — never a planning document, which is
# written before the race it describes has run.
#
# The race was real. This file was built as 0018/down_revision 0014 while FOUR
# features were in flight, because 0015 was claimed TWICE at the time
# (0015_floor_roles.py and 0015_deposit_flow.py). Both have since merged, in
# that order, and F19 renumbered itself to 0016 — so head is 0016 and this is
# 0017. THE HAZARD THAT MADE THAT WORTH DESIGNING AROUND IS STILL LIVE: the
# filenames differ, so git merges two same-revision migrations with no conflict
# at all, and the only symptom is alembic reporting multiple heads at runtime,
# far from the change that caused it. F33 is carrying 0016_queue_tickets.py
# against a main whose 0016 is already taken, and will hit exactly this.
revision = "0017"
down_revision = "0016"
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
