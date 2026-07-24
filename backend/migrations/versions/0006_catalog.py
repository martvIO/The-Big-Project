"""catalog: dresses, dress_variants, dress_media

Revision ID: 0006
Revises: 0005
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0006"
down_revision = "0005"
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
    # Every numeric CHECK here is an absurdity ceiling at 10x the service constant
    # in app/catalog/validation.py — INT4 headroom, so tightening product policy
    # never needs a migration. dress_media.byte_size is the one exception at 2x,
    # because that bound is also enforced by the presigned POST policy.
    op.execute(
        f"""
        CREATE TABLE dresses (
            {_STANDARD},
            name TEXT NOT NULL,
            description TEXT,
            price_agorot INTEGER
                CHECK (price_agorot IS NULL OR (price_agorot > 0 AND price_agorot <= 1000000000)),
            price_visible BOOLEAN NOT NULL DEFAULT true,
            reserved BOOLEAN NOT NULL DEFAULT false,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # Both indexes carry all four keys of the documented list order
    # (sort_order ASC, created_at DESC, id ASC), so paging stays stable under
    # concurrent inserts. No unique index on (tenant_id, name): one designer
    # model in two colours is legitimate, and a dress is addressed only by id.
    op.execute(
        "CREATE INDEX idx_dresses_tenant_active "
        "ON dresses (tenant_id, sort_order, created_at DESC, id) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_dresses_tenant_archived "
        "ON dresses (tenant_id, sort_order, created_at DESC, id) WHERE deleted_at IS NOT NULL"
    )
    op.execute(_updated_at_trigger("dresses"))

    op.execute(
        f"""
        CREATE TABLE dress_variants (
            {_STANDARD},
            dress_id UUID NOT NULL,
            size_label TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0 AND quantity <= 10000),
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_dress_variants_dress_active "
        "ON dress_variants (tenant_id, dress_id, sort_order) WHERE deleted_at IS NULL"
    )
    # Expression index on lower(size_label), not the raw label: the service
    # normalises whitespace, but only lower() stops "US 6" and "us 6" becoming
    # two stock buckets for one physical size.
    op.execute(
        "CREATE UNIQUE INDEX idx_dress_variants_dress_size_unique "
        "ON dress_variants (tenant_id, dress_id, lower(size_label)) WHERE deleted_at IS NULL"
    )
    op.execute(_updated_at_trigger("dress_variants"))

    # The content_type and status sets are pinned exactly because they are
    # security boundaries, not duplication: an image/svg+xml object served from
    # our bucket is stored XSS on the storefront, and a status the confirm path
    # never wrote would put an unverified object on the gallery read path.
    # uuid_generate_v4() stays the column default for any non-service writer even
    # though the service mints media_id client-side to precompute storage_key.
    op.execute(
        f"""
        CREATE TABLE dress_media (
            {_STANDARD},
            dress_id UUID NOT NULL,
            storage_key TEXT NOT NULL,
            content_type TEXT NOT NULL
                CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
            byte_size INTEGER NOT NULL CHECK (byte_size > 0 AND byte_size <= 20971520),
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ready')),
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_dress_media_dress_ready "
        "ON dress_media (tenant_id, dress_id, sort_order, id) "
        "WHERE deleted_at IS NULL AND status = 'ready'"
    )
    # Tenant-first like every other index here, so one tenant's stale-pending
    # sweep never costs anything proportional to platform-wide upload traffic.
    op.execute(
        "CREATE INDEX idx_dress_media_pending "
        "ON dress_media (tenant_id, dress_id, created_at) "
        "WHERE deleted_at IS NULL AND status = 'pending'"
    )
    # PLAIN unique (no partial predicate): a regression guard on the key builder,
    # nothing more. The key embeds the row's own PK, so a collision is only
    # possible if build_media_key ever drops media_id — which this turns into an
    # IntegrityError in CI rather than two rows pointing at one object.
    op.execute(
        "CREATE UNIQUE INDEX idx_dress_media_storage_key_unique "
        "ON dress_media (tenant_id, storage_key)"
    )
    op.execute(_updated_at_trigger("dress_media"))

    # Nothing here is append-only, so no REVOKE dance (that belongs to
    # terms_versions / platform_audit_log) — copying it would break every UPDATE.
    for table in ("dresses", "dress_variants", "dress_media"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO app_user")
        for statement in enable_tenant_rls(table):
            op.execute(statement)


def downgrade() -> None:
    for table in ("dress_media", "dress_variants", "dresses"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
