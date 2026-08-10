"""platform invites (F26 D3 — the operator-issued signup code)

Revision ID: 0034
Revises: 0033

Numbered 0034 over a then-head of 0032 because `.worktrees/waitlist-auto-
reallocation` holds `0033` while this branch is cut. 0028's note states the rule
this follows: two files declaring the SAME `revision` id break `alembic upgrade`
outright and red every db-marked test with a message about nothing in the diff,
whereas a gap costs nothing. `down_revision` is re-resolved to the real head at
the pre-push rebase (`.memory/parallel-alembic-numbering`).

RE-PARENTED 0032 -> 0033 AT THAT REBASE, which is that rule firing rather than
being quoted. F23 merged while this branch was open and its 0033 also named 0032
as parent. Two revisions naming ONE parent BRANCHES the history: `alembic heads`
reports two heads and every db-marked test reds with a message that points at
nothing in the diff. The renumber alone would have looked like a passing edit —
the re-parent is what makes it correct. Chain is linear: 0032 -> 0033 -> 0034.

NO `tenant_id` (spec D3), 0028's argument a third time: an invite belongs to the
platform, and the tenant it creates does not exist yet. A `tenant_id` column
would drag this table into `test_every_tenant_id_table_has_forced_rls`'s metadata
scan and demand an RLS policy over rows no tenant owns. The tenant that a
redemption produces is recorded as `redeemed_tenant_id` — 0004's
`target_tenant_id` lesson, applied again.

`code_hash` IS THE ONLY FORM OF THE CODE THAT EXISTS HERE. The raw value is
`secrets.token_urlsafe(32)`, returned exactly once in the create response and
never stored, so a leaked database yields no usable invite (spec D3). There is
deliberately no `code` column for a later reader to "add for support".

`redeemed_by` is deliberately absent: it could only ever equal `owner_email`,
because that is the only identity a redemption can produce (D2). The request IP
is not stored either — nothing decides on it, and Amendment 13's minimisation
duty makes collecting it because we could the wrong default. The
`INVITE_REDEEMED` row in `platform_audit_log` is the record.

`platform_audit_log` is untouched: F26's five new `PlatformAuditAction` members
need no migration, because 0004 made `action` plain TEXT with no CHECK. The
fourth feature in a row to lean on that.
"""

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

# The house standard block MINUS tenant_id — see the module docstring.
_STANDARD = """
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE platform_invites (
            {_STANDARD},
            code_hash          TEXT NOT NULL,
            slug               TEXT NOT NULL,
            name               TEXT NOT NULL,
            owner_email        TEXT NOT NULL,
            created_by         TEXT NOT NULL,
            expires_at         TIMESTAMPTZ NOT NULL,
            redeemed_at        TIMESTAMPTZ,
            redeemed_tenant_id UUID
        )
        """
    )
    # NOT partial, unlike every other index in 0028. A soft-deleted or redeemed
    # invite must keep occupying its hash: the lookup path reads this table by
    # hash to shape a refusal for a code that is revoked or already spent, and a
    # partial index would let the same 256-bit value be issued twice — improbable
    # from `token_urlsafe(32)`, and not a property worth leaving to probability
    # on a credential that creates a boutique.
    op.execute("CREATE UNIQUE INDEX idx_platform_invites_code_hash ON platform_invites (code_hash)")
    # The console's list and any future expiry sweep. Partial on the two
    # predicates that make a row still actionable — an invite that is spent or
    # revoked is never looked up this way again.
    op.execute(
        "CREATE INDEX idx_platform_invites_open ON platform_invites (expires_at) "
        "WHERE redeemed_at IS NULL AND deleted_at IS NULL"
    )
    op.execute(
        """
        CREATE TRIGGER trg_platform_invites_updated_at BEFORE UPDATE ON platform_invites
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        """
    )

    # ⚠ REVOKE FIRST, 0004's reason exactly: 0002's ALTER DEFAULT PRIVILEGES
    # auto-grants full CRUD on every new table created by the migration role, so
    # a plain GRANT would leave DELETE in place and the "no DELETE" below would
    # be decoration. Revoke IS a soft delete here — an invite that was issued and
    # then withdrawn is evidence, and a row the app can erase is evidence the app
    # can erase.
    #
    # SELECT and UPDATE are both required and neither is optional: SELECT is the
    # by-hash read that shapes a refusal, UPDATE is the atomic single-use claim.
    op.execute("REVOKE ALL ON platform_invites FROM app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE ON platform_invites TO app_user")


def downgrade() -> None:
    # The indexes and the trigger go with the table. Nothing else was touched.
    op.execute("DROP TABLE IF EXISTS platform_invites")
