"""walk in bookings: the source discriminator and the terms evidence CHECK

Revision ID: 0025
Revises: 0024
"""

from alembic import op

# Resolved from `alembic heads` on the REBASED branch, which is the only source
# this repo trusts for a revision id — never a planning document, which is
# written before the race it describes has run. 0017's and 0024's headers record
# that hazard firing three times between them; F50 therefore keeps this file as
# the LAST commit on the branch, so a renumber at rebase is one amend to one
# file and touches no test (test_migrations resolves the downgrade target by
# IDENTITY, via `_parent_of("walk in bookings")`).
revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # WHICH SURFACE CREATED THIS BOOKING. Not decoration and not analytics: it is
    # the DISCRIMINATOR the terms CHECK below needs. Without it a NULL
    # `terms_version_accepted` has two indistinguishable meanings — "a staffer
    # created this row and nobody accepted anything" and "a storefront booking
    # lost its evidence to a bug" — and only the first is legal.
    #
    # NOT NULL DEFAULT 'storefront' is metadata-only in PG 11+ (non-volatile
    # default, no rewrite), and the default is load-bearing rather than
    # convenient: it is what makes the terms CHECK below true of 100% of existing
    # rows with NO BACKFILL UPDATE, because every row that exists today WAS
    # created by the storefront. 0017's `tags TEXT[] NOT NULL DEFAULT '{}'` is the
    # precedent.
    op.execute("ALTER TABLE bookings ADD COLUMN source TEXT NOT NULL DEFAULT 'storefront'")
    # NAMED and its own statement — 0011's, 0015's and 0024's shape. An inline
    # CHECK on ADD COLUMN takes a Postgres-generated name, and the remote half's
    # widening ('owner') would then depend on guessing it.
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_source_check "
        "CHECK (source IN ('storefront','walk_in'))"
    )

    # The two NOT NULLs go, and the CHECK below is what replaces them. Dropping
    # NOT NULL never fails on existing data and never rewrites.
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_version_accepted DROP NOT NULL")
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_accepted_at DROP NOT NULL")

    # ⚠ THE EXEMPTION IS ENUMERATED, NOT THE REQUIREMENT, and that direction is
    # the whole design of this constraint. Written the other way round —
    # `source <> 'storefront' OR (...)` — it says the same thing today and the
    # OPPOSITE thing tomorrow: the remote/scheduled half adds 'owner' to the
    # source CHECK above and would silently inherit a terms exemption it must not
    # have. Written this way, a third source value is a FAILING INSERT until its
    # author decides about terms on purpose.
    #
    # Added AFTER the two DROP NOT NULLs, and the order is not cosmetic: ADD
    # CONSTRAINT validates existing rows, so reading this file top to bottom is
    # what makes the "no backfill UPDATE" claim checkable.
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT bookings_terms_evidence_check "
        "CHECK (source = 'walk_in' OR "
        "(terms_version_accepted IS NOT NULL AND terms_accepted_at IS NOT NULL))"
    )

    # The inline `CHECK (terms_version_accepted > 0)` from 0008 is DELIBERATELY
    # untouched: a CHECK over a NULL evaluates to NULL, which is not FALSE, so it
    # passes on a walk-in row without an edit — and hunting its Postgres-generated
    # name to drop and re-add would be work that buys nothing. Stated so a
    # reviewer does not go looking, and proved by
    # test_the_inline_positive_version_check_still_binds.
    #
    # Deliberately absent, each for a verified reason:
    #
    #   * No GRANT. 0008 issued table-level
    #     `GRANT SELECT, INSERT, UPDATE, DELETE ON bookings TO app_user`; table
    #     grants are column-agnostic. (0002's ALTER DEFAULT PRIVILEGES gotcha is
    #     about newly CREATED tables, not added columns.)
    #   * No enable_tenant_rls. RLS is a table property, forced on `bookings`
    #     since 0008. F50 adds no table — test_every_tenant_id_table_has_forced_rls
    #     staying green UNEDITED is the assertion that none snuck in.
    #   * No _updated_at_trigger. trg_bookings_updated_at exists from 0008.
    #   * No index on `source`. Nothing filters or sorts on it — the board reads
    #     the day and renders the value. An index with no reader is a cost on
    #     every write.
    #   * No touch to the status CHECK or to either partial unique index. A
    #     walk-in is `confirmed`, occupies its own microsecond-unique instant, and
    #     both indexes bind on it exactly as they bind on a storefront row.
    #     test_the_booking_check_in_migration_leaves_the_status_check_and_both_unique_indexes_alone
    #     re-reads all three at head and is what proves it, UNEDITED.


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_terms_evidence_check")
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_source_check")
    # ⚠ DELIBERATELY ABLE TO FAIL, and deliberately without a pre-clean. On a
    # table holding any walk_in row these two statements raise, and that is the
    # REFUSAL, not a defect: the only ways to make them succeed are to DELETE real
    # appointment records or to stamp terms evidence nobody gave, and this feature
    # exists because the second one is not allowed. An operator who genuinely
    # wants to go back decides about those rows by hand, on purpose.
    #
    # F57's `test_the_downgrade_refuses_to_narrow_past_a_floor_role_row` is the
    # precedent and its docstring the argument: "a lenient downgrade leaves the
    # database describing a state its own schema forbids." The db test asserts the
    # failure rather than describing it.
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_accepted_at SET NOT NULL")
    op.execute("ALTER TABLE bookings ALTER COLUMN terms_version_accepted SET NOT NULL")
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS source")
