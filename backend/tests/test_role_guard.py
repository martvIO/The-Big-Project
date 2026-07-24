import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.session import verify_database_role

pytestmark = pytest.mark.db

OWNER_PROBE_ROLE = "guard_owner_probe"
OWNER_PROBE_PASSWORD = "test-only-owner-probe-pw"
OWNER_PROBE_TABLE = "guard_ownership_probe"


async def test_superuser_role_is_refused(migrated_db: str) -> None:
    # The container superuser also owns every table, but the rolsuper/BYPASSRLS
    # check must trip first — its failure mode (RLS not applied at all) is worse.
    engine = create_async_engine(migrated_db)
    try:
        with pytest.raises(RuntimeError, match="bypass row-level security"):
            await verify_database_role(engine)
    finally:
        await engine.dispose()


async def test_table_owner_role_is_refused(migrated_db: str) -> None:
    """A plain role that OWNS tables in public passes the superuser/BYPASSRLS
    check yet can disable FORCE RLS and ignores REVOKE-based guarantees
    (terms_versions immutability included) — startup must refuse it."""
    admin = create_async_engine(migrated_db)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {OWNER_PROBE_TABLE}"))
            await conn.execute(text(f"DROP ROLE IF EXISTS {OWNER_PROBE_ROLE}"))
            await conn.execute(
                text(f"CREATE ROLE {OWNER_PROBE_ROLE} LOGIN PASSWORD '{OWNER_PROBE_PASSWORD}'")
            )
            await conn.execute(text(f"CREATE TABLE {OWNER_PROBE_TABLE} (id INTEGER)"))
            await conn.execute(text(f"ALTER TABLE {OWNER_PROBE_TABLE} OWNER TO {OWNER_PROBE_ROLE}"))

        scheme, rest = migrated_db.split("://", 1)
        _, host_part = rest.split("@", 1)
        owner_engine = create_async_engine(
            f"{scheme}://{OWNER_PROBE_ROLE}:{OWNER_PROBE_PASSWORD}@{host_part}"
        )
        try:
            with pytest.raises(RuntimeError, match="owns tables"):
                await verify_database_role(owner_engine)
        finally:
            await owner_engine.dispose()
    finally:
        async with admin.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {OWNER_PROBE_TABLE}"))
            await conn.execute(text(f"DROP ROLE IF EXISTS {OWNER_PROBE_ROLE}"))
        await admin.dispose()


async def test_app_role_is_accepted(app_role_url: str) -> None:
    # boutique_app is neither privileged nor an owner of anything in public.
    engine = create_async_engine(app_role_url)
    try:
        await verify_database_role(engine)
    finally:
        await engine.dispose()
