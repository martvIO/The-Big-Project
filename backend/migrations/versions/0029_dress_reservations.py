"""date-bound dress reservation: dress_reservations (F28's rental windows)

Revision ID: 0029
Revises: 0027

⚠ RE-PARENTED AT REBASE, WHICH IS THE PROTOCOL AND NOT AN ACCIDENT. This was
built against the head visible in the F28 worktree (0026) while F24 held 0027 in
an open PR and F25 held 0028 in a live one. F24 has since merged, so `alembic
heads` against rebased main answers 0027 and that is the real parent named here.
0028 is still F25's and unmerged: 0029 stays this migration's number, and if F25
lands first nothing here moves — whichever of the two merges SECOND re-parents
onto the other, because two siblings pointing at one parent is two heads.
0020's header records what a duplicated revision STRING costs instead: alembic
keys by it, dedupes to one script and silently drops the other, so one of the
two tables is simply never created on a fresh database.
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0029"
down_revision = "0028"
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
    # DATE ON BOTH ENDS, NOT TIMESTAMPTZ, and `ends_on` is INCLUSIVE (spec D2). A
    # rental leaves and returns on calendar DAYS; the boutique operates in one
    # timezone (BOUTIQUE_TIMEZONE), so DATE makes the overlap arithmetic exact
    # and DST-proof, and "unavailable 12-18" means the 18th is unavailable too.
    # Every reader that compares an INSTANT against these columns must convert
    # to the boutique-local date first — never `starts_at.date()` in UTC, which
    # is off by a day for anything from 22:00 UTC onwards.
    #
    # dress_id: no FK, house rule; the service validates the parent dress is
    # live before it inserts. customer_id is a POINTER and OPTIONAL (D7,
    # alteration_tickets' precedent verbatim): an erase scrubs the `customers`
    # row and every reservation renders the scrubbed name automatically, so F20's
    # export/erase surfaces need zero changes. There are deliberately NO
    # name/phone TEXT columns — a renter not in CRM goes in `notes`, the same
    # accepted owner-text class as bookings.notes.
    #
    # NAMED CHECKs, not inline anonymous ones: pinned by
    # test_the_reservation_definitions_are_pinned, and a later ALTER can only
    # drop by name. The span ceiling is 10x MAX_RESERVATION_SPAN_DAYS (0005's
    # convention), so tightening product policy never needs a migration while
    # widening the DB's absurdity ceiling stays a visible act.
    op.execute(
        f"""
        CREATE TABLE dress_reservations (
            {_STANDARD},
            dress_id    UUID NOT NULL,
            starts_on   DATE NOT NULL,
            ends_on     DATE NOT NULL,
            customer_id UUID,
            notes       TEXT,
            CONSTRAINT dress_reservations_order_check CHECK (ends_on >= starts_on),
            CONSTRAINT dress_reservations_span_check CHECK (ends_on - starts_on <= 3650)
        )
        """
    )
    # ONE index, partial, and NOT unique. `(tenant_id, dress_id, ends_on)` is
    # exactly what both readers do: the overlap SELECT filters one dress's live
    # rows and compares `ends_on >= :starts_on`, and the storefront projection
    # filters `ends_on >= today`. `WHERE deleted_at IS NULL` keeps it off
    # soft-deleted rows, which every reader in this feature excludes.
    #
    # NO EXCLUDE CONSTRAINT AND NO btree_gist (D3), and this is the decision most
    # likely to be re-litigated. Range overlap is not expressible as a partial
    # unique btree index, and the repo has zero btree_gist precedent — enabling
    # an extension for one table is a deployment fact every environment then has
    # to carry. The tenant advisory lock the service takes before the overlap
    # SELECT is sufficient here because the writers are staff sessions on a
    # CSRF-fenced console, not the anonymous internet.
    # ponytail: advisory lock only; `EXCLUDE USING gist (tenant_id WITH =,
    # dress_id WITH =, daterange(starts_on, ends_on, '[]') WITH &&) WHERE
    # (deleted_at IS NULL)` is the upgrade if reservation writers ever multiply.
    op.execute(
        "CREATE INDEX idx_dress_reservations_dress "
        "ON dress_reservations (tenant_id, dress_id, ends_on) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("dress_reservations"))

    # Table-level and column-agnostic (0003_auth.py:83-84's precedent). Ordinary
    # CRUD, so no REVOKE-first dance — that is terms_versions' and
    # platform_audit_log's append-only shape.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON dress_reservations TO app_user")
    for statement in enable_tenant_rls("dress_reservations"):
        op.execute(statement)


def downgrade() -> None:
    # The index, trigger and policy go with the table. F28 adds no column to any
    # existing table — `dresses.reserved` is KEPT exactly as shipped (D5) and no
    # data migration moves `reserved = true` rows in here — so there is nothing
    # else to un-touch.
    op.execute("DROP TABLE IF EXISTS dress_reservations")
