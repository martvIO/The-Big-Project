"""platform operators and sessions (F25's console identity, platform-scoped)

Revision ID: 0028
Revises: 0026

⚠ NUMBERED 0028 OVER A HEAD OF 0026, ON PURPOSE, and the gap is the safer of the
two failure modes rather than an oversight. F24 was landing `0027` in a parallel
worktree while this branch was cut. Two files declaring the SAME `revision` id
breaks `alembic upgrade` outright and reds every db-marked test with a message
about nothing in the diff; two files declaring the same `down_revision` merely
branches the history, which `test_exactly_one_migration_head` catches in the FAST
lane with instructions. So the collision was avoided and the branch was accepted.

Re-resolve immediately before the pre-push rebase: if `0027` is on main by then,
this file's `down_revision` becomes `"0027"` in one `fix(platform):` commit
(`.memory/parallel-alembic-numbering`).

NEITHER TABLE CARRIES `tenant_id` (spec D7). That is 0004's `target_tenant_id`
lesson applied again: an operator belongs to the platform, not to a boutique, and
a `tenant_id` column would drag both tables into
`test_every_tenant_id_table_has_forced_rls`'s metadata scan and demand an RLS
policy over rows no tenant owns. No `enable_tenant_rls` here, therefore, and no
GRANT either — 0002's ALTER DEFAULT PRIVILEGES already gives `app_user` the CRUD
these two need (login SELECTs, the CLI bootstrap INSERTs, logout/deactivation
UPDATEs). That is the OPPOSITE of 0004's posture and deliberately so: the audit
book must not be readable by the web process, these two must.

`platform_audit_log` is untouched. F25's four new `PlatformAuditAction` members
need no migration — 0004 made `action` plain TEXT with no CHECK.
"""

from alembic import op

revision = "0028"
down_revision = "0026"
branch_labels = None
depends_on = None

# The house standard block MINUS tenant_id — see the module docstring.
_STANDARD = """
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
        CREATE TABLE platform_operators (
            {_STANDARD},
            email         TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            display_name  TEXT NOT NULL
        )
        """
    )
    # `lower(email)` and not a plain column index: addresses are compared
    # case-insensitively at login, so a plain unique index would admit
    # `Dana@x` beside `dana@x` as two accounts that one typed password reaches
    # one of at random.
    #
    # `WHERE deleted_at IS NULL` is what makes deactivation reversible in the
    # only way this feature supports it — deactivate, then re-create the same
    # address (staff_users' F51 D5 note, one table over). Soft delete IS
    # deactivation here (spec D2).
    op.execute(
        "CREATE UNIQUE INDEX idx_platform_operators_email_unique "
        "ON platform_operators (lower(email)) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("platform_operators"))

    op.execute(
        f"""
        CREATE TABLE platform_sessions (
            {_STANDARD},
            operator_id UUID NOT NULL,
            token_hash  TEXT NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL
        )
        """
    )
    # Its OWN table rather than a widening of `sessions`: that table's
    # `tenant_id` and `staff_user_id` are both NOT NULL, and staff auth and
    # operator auth must never share a lookup path (spec D3, the F24
    # `customer_sessions` precedent). A shared path is one predicate away from a
    # staff cookie resolving as an operator.
    op.execute(
        "CREATE INDEX idx_platform_sessions_token "
        "ON platform_sessions (token_hash) WHERE deleted_at IS NULL"
    )
    # The revoke-all-for-operator sweep deactivation runs. Partial for the token
    # index's reason: a revoked row is never looked up again.
    op.execute(
        "CREATE INDEX idx_platform_sessions_operator "
        "ON platform_sessions (operator_id) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("platform_sessions"))


def downgrade() -> None:
    # The indexes and triggers go with the tables. F25 touches no existing table,
    # so there is nothing to un-touch — `platform_audit_log` above all.
    op.execute("DROP TABLE IF EXISTS platform_sessions")
    op.execute("DROP TABLE IF EXISTS platform_operators")
