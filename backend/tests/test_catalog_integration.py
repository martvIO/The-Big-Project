"""Feature 8 catalog on real Postgres as boutique_app — the half of migration
0006 that is unprovable locally: every named index, the app_user CRUD grants,
each CHECK that pins a security or absurdity bound, and the down/up round trip.

Runs as the non-owner application role, never as the container superuser: GRANT
correctness is vacuous when the connecting principal owns the tables.
"""

import asyncio
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.tenant import tenant_connection

pytestmark = pytest.mark.db

BACKEND_DIR = Path(__file__).resolve().parent.parent

TENANT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
DRESS_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")

CATALOG_TABLES = ("dresses", "dress_variants", "dress_media")

CATALOG_INDEXES = {
    "idx_dresses_tenant_active",
    "idx_dresses_tenant_archived",
    "idx_dress_variants_dress_active",
    "idx_dress_variants_dress_size_unique",
    "idx_dress_media_dress_ready",
    "idx_dress_media_pending",
    "idx_dress_media_storage_key_unique",
}

_MEDIA_INSERT = """
    INSERT INTO dress_media (tenant_id, dress_id, storage_key, content_type, byte_size, status)
    VALUES (:tenant_id, :dress_id, :storage_key, :content_type, :byte_size, :status)
"""


def _media_params(*, storage_key: str, **overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "tenant_id": TENANT_ID,
        "dress_id": DRESS_ID,
        "storage_key": f"tenants/{TENANT_ID}/dresses/{DRESS_ID}/media/{storage_key}.jpg",
        "content_type": "image/jpeg",
        "byte_size": 1024,
        "status": "pending",
    }
    params.update(overrides)
    return params


async def test_every_catalog_index_exists(app_role_url: str) -> None:
    engine = create_async_engine(app_role_url)
    try:
        async with engine.connect() as engine_conn:
            present = (
                (
                    await engine_conn.execute(
                        text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()
    assert CATALOG_INDEXES - set(present) == set()


async def test_app_user_holds_crud_on_every_catalog_table(app_role_url: str) -> None:
    """Nothing here is append-only, so all four privileges must be granted —
    a copied REVOKE dance would break every UPDATE the service issues."""
    engine = create_async_engine(app_role_url)
    try:
        async with engine.connect() as engine_conn:
            for table in CATALOG_TABLES:
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    granted = await engine_conn.execute(
                        text("SELECT has_table_privilege('app_user', :table, :privilege)"),
                        {"table": table, "privilege": privilege},
                    )
                    assert granted.scalar_one() is True, f"app_user lacks {privilege} on {table}"
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("statement", "params"),
    [
        pytest.param(
            _MEDIA_INSERT,
            _media_params(storage_key="svg", content_type="image/svg+xml"),
            id="content_type_outside_the_accepted_set",
        ),
        pytest.param(
            _MEDIA_INSERT,
            _media_params(storage_key="oversize", byte_size=20971521),
            id="byte_size_above_the_2x_ceiling",
        ),
        pytest.param(
            _MEDIA_INSERT,
            _media_params(storage_key="processing", status="processing"),
            id="status_outside_the_accepted_set",
        ),
        pytest.param(
            """
            INSERT INTO dress_variants (tenant_id, dress_id, size_label, quantity)
            VALUES (:tenant_id, :dress_id, '38', -1)
            """,
            {"tenant_id": TENANT_ID, "dress_id": DRESS_ID},
            id="negative_quantity",
        ),
        pytest.param(
            """
            INSERT INTO dresses (tenant_id, name, price_agorot)
            VALUES (:tenant_id, 'Free dress', 0)
            """,
            {"tenant_id": TENANT_ID},
            id="zero_price",
        ),
    ],
)
async def test_check_constraints_reject_out_of_bound_writes(
    app_role_url: str, statement: str, params: dict[str, object]
) -> None:
    """An accepted content type and an accepted status are security boundaries,
    not duplication: an image/svg+xml object served from our bucket is stored
    XSS, and a status the confirm path never wrote would expose an unverified
    object. Widening either must be a deliberate migration."""
    engine = create_async_engine(app_role_url)
    try:
        with pytest.raises(IntegrityError):
            async with tenant_connection(engine, TENANT_ID) as conn:
                await conn.execute(text(statement), params)
    finally:
        await engine.dispose()


def _catalog_table_count(url: str) -> int:
    async def count() -> int:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_tables "
                        "WHERE tablename IN ('dresses', 'dress_variants', 'dress_media')"
                    )
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(count())


def test_migration_0006_round_trips(migrated_db: str) -> None:
    """downgrade drops dress_media, dress_variants, dresses in child-first order;
    upgrade puts all three back with their indexes, grants and policies. Runs as
    the migration owner (the app role cannot DROP), and destroys catalog rows —
    so it owns no fixtures and shares no state with the tests above."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)

    assert _catalog_table_count(migrated_db) == 3
    command.downgrade(cfg, "0005")
    assert _catalog_table_count(migrated_db) == 0
    command.upgrade(cfg, "head")
    assert _catalog_table_count(migrated_db) == 3
