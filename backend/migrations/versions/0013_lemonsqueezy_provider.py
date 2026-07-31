"""payments: admit 'lemonsqueezy' into the gateway provider CHECK

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_TABLE = "tenant_gateway_credentials"
# 0012 declared the CHECK inline on the column, so PostgreSQL named it. Spelled
# once rather than at four call sites, and the DROP carries no IF EXISTS in
# either direction on purpose: a rename upstream must fail this migration loudly
# instead of quietly leaving the column unconstrained, which is exactly the state
# the CHECK exists to prevent.
_CONSTRAINT = f"{_TABLE}_provider_check"


def _drop() -> str:
    return f"ALTER TABLE {_TABLE} DROP CONSTRAINT {_CONSTRAINT}"


def _add(providers: str) -> str:
    return f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_CONSTRAINT} CHECK (provider IN ({providers}))"


def upgrade() -> None:
    # 0012's comment states why this CHECK is a SECURITY CONTROL rather than
    # merely D8's no-speculative-values rule: it is what makes "no real merchant
    # credential can be stored behind an adapter that has not shipped" a
    # property of the schema. So it widens by EXACTLY the one value F18's
    # adapter adds, in F18's own migration, and no further.
    #
    # 'lemonsqueezy' is admitted to the TABLE but not to production: the
    # Settings guard boot-fails on APP_ENV=production + this provider, because
    # Lemon Squeezy is merchant-of-record and can never carry a boutique's
    # deposit. A row here is a dev or staging credential set by construction.
    #
    # `payments.provider` deliberately gets nothing. 0012 left that column
    # unconstrained — it is a snapshot of whichever gateway took the money —
    # and inventing a CHECK for it here would be a schema change no writer in
    # this feature is asking for.
    op.execute(_drop())
    op.execute(_add("'fake', 'lemonsqueezy'"))


def downgrade() -> None:
    # Narrowing VALIDATES the existing rows, so this raises if any lemonsqueezy
    # credential set is present — including a soft-deleted one, since D6's
    # rotation trail keeps those rows. That is the intended behaviour: the
    # alternative is a downgrade that silently leaves rows the schema then
    # claims are impossible. Clearing them is a deliberate act for whoever runs
    # the downgrade, not something a migration should do to money-adjacent data
    # on its way past.
    op.execute(_drop())
    op.execute(_add("'fake'"))
