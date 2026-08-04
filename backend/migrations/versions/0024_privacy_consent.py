"""privacy consent: the marketing-consent pair, its source, and the erasure stamp

Revision ID: 0024
Revises: 0023
"""

from alembic import op

# Resolved from `alembic heads` on the REBASED branch, which is the only source
# this repo trusts for a revision id — never a planning document, which is
# written before the race it describes has run. 0017's header records that hazard
# firing twice; F20's plan (§6) therefore keeps this file as the LAST commit on
# the branch, so a renumber at rebase is one amend to one file and touches no
# test (test_migrations resolves the downgrade target by IDENTITY, via
# `_parent_of("privacy consent")`).
revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Four columns on `customers`, all NULLABLE WITH NO DEFAULT, and the absence
    # of a default is the design rather than an omission (D6).
    #
    #   marketing_consent_at            §30A consent. DEFAULT-OFF IS STRUCTURAL:
    #                                   consent is the PRESENCE of a timestamp, so
    #                                   there is no boolean whose server_default a
    #                                   later migration could flip to opt-out, and
    #                                   no second spelling of "no consent" for two
    #                                   predicates to disagree about.
    #   marketing_consent_source        which surface took it. ONE allowed value at
    #                                   F20 — see the CHECK below.
    #   marketing_consent_withdrawn_at  withdrawal is ADDITIVE. Clearing the
    #                                   consent stamp would destroy the Spam-Law
    #                                   evidence that consent existed at the moment
    #                                   a message was sent. Effective consent is
    #                                   `at IS NOT NULL AND withdrawn IS NULL`.
    #   erased_at                       §14 erasure evidence, the flag that makes
    #                                   the `[erased]` placeholder honest, and the
    #                                   guard that stops the `customers` retention
    #                                   SCRUB consuming rows it already erased.
    #
    # ADD COLUMN with no default is metadata-only in PG 11+ — no table rewrite.
    op.execute("ALTER TABLE customers ADD COLUMN marketing_consent_at TIMESTAMPTZ")
    op.execute("ALTER TABLE customers ADD COLUMN marketing_consent_source TEXT")
    op.execute("ALTER TABLE customers ADD COLUMN marketing_consent_withdrawn_at TIMESTAMPTZ")
    op.execute("ALTER TABLE customers ADD COLUMN erased_at TIMESTAMPTZ")

    # Exactly two CHECKs, both NAMED and each its own statement — 0011's shape
    # (`staff_users_role_check`). Named and separate is what makes a later
    # widening a one-line edit instead of a guess at a Postgres-generated name,
    # and test_migrations.py's drop/re-add-by-name helpers borrow 0011's.
    #
    # ONE allowed source value, and that is a scope decision recorded in plan
    # DR-10 rather than a placeholder. F33's walk-in opt-in lives on
    # `queue_tickets.marketing_opt_in_at` and stays there: promoting it into
    # `customers.marketing_consent_at` would launder an UNVERIFIED form
    # submission into a provable consent, and this column's whole value is that
    # every row in it survives "prove she owned that number".
    op.execute(
        "ALTER TABLE customers ADD CONSTRAINT customers_marketing_consent_source_check "
        "CHECK (marketing_consent_source IN ('booking_form'))"
    )
    # The incoherent state, fenced: a withdrawal standing over a consent that
    # never existed. `withdraw_marketing_consent` carries
    # `AND marketing_consent_at IS NOT NULL` in its WHERE, so this is unreachable
    # through the application — it is the fence against a hand-written UPDATE.
    op.execute(
        "ALTER TABLE customers ADD CONSTRAINT customers_marketing_withdraw_check "
        "CHECK (marketing_consent_withdrawn_at IS NULL OR marketing_consent_at IS NOT NULL)"
    )

    # ADD CONSTRAINT validates existing rows, so neither ALTER can fail on live
    # data: every pre-0024 customer row has four NULLs and satisfies both
    # trivially. Both halves of that claim are proven on a POPULATED table by
    # tests/test_migrations.py::test_adding_the_privacy_checks_validates_existing_rows,
    # following 0011's precedent — a NOT VALID constraint would pass the positive
    # half alone and this comment would be a lie.
    #
    # Deliberately absent, each for a verified reason, stated so a reviewer can
    # check the list is COMPLETE rather than merely short:
    #
    #   * No GRANT. 0008 issued table-level
    #     `GRANT SELECT, INSERT, UPDATE, DELETE ON customers TO app_user`; table
    #     grants are column-agnostic and no column-level grant was ever issued
    #     here. (0002's ALTER DEFAULT PRIVILEGES gotcha is about newly CREATED
    #     tables, not added columns.)
    #   * No enable_tenant_rls. RLS is a table property, forced on `customers`
    #     since 0008. F20 adds no table — test_every_tenant_id_table_has_forced_rls
    #     staying green UNEDITED is the assertion that none snuck in.
    #   * No _updated_at_trigger. trg_customers_updated_at exists from 0008.
    #   * No index. The three retention scans that need one already have one
    #     (idx_message_log_tenant_created 0007, idx_bookings_tenant_starts and
    #     idx_bookings_tenant_customer 0008, idx_sessions_expires_at 0003);
    #     otp_codes rows live <= 15 min so that table never grows past a page,
    #     scheduled_messages is purged by a booking-id set the same statement
    #     already materialised, and queue_tickets is bounded by one boutique-day
    #     of walk-ins. A marketing-audience partial index
    #     (WHERE marketing_consent_at IS NOT NULL AND marketing_consent_withdrawn_at
    #     IS NULL) is deliberately NOT created: nothing sends marketing in v1, and
    #     an index with no reader is a cost on every write.
    #   * No third CHECK pinning `consent implies source`. The single writer
    #     (record_marketing_consent) sets both in one statement, and pinning it
    #     would make any future widening a two-constraint migration.
    #
    # <!-- ponytail: per-tenant seq scan on otp_codes, scheduled_messages and
    #      queue_tickets. Ceiling: tens of thousands of live rows in any of the
    #      three; unreachable at pilot volume. -->


def downgrade() -> None:
    op.execute("ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_marketing_withdraw_check")
    op.execute(
        "ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_marketing_consent_source_check"
    )
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS erased_at")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS marketing_consent_withdrawn_at")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS marketing_consent_source")
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS marketing_consent_at")
