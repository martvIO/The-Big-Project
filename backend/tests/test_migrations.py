import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.db
def test_migrations_apply_and_uuid_ossp_available(migrated_db: str) -> None:
    async def check() -> tuple[str, int]:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                generated = await conn.execute(text("SELECT uuid_generate_v4()::text"))
                versions = await conn.execute(text("SELECT count(*) FROM alembic_version"))
                return str(generated.scalar_one()), int(versions.scalar_one())
        finally:
            await engine.dispose()

    uuid_value, version_rows = asyncio.run(check())
    assert len(uuid_value) == 36
    assert version_rows == 1


_STAFF_INSERT = (
    "INSERT INTO staff_users (tenant_id, email, password_hash, display_name, role) "
    "VALUES (uuid_generate_v4(), 'probe@check.example', 'hash', 'Probe', :role)"
)


@pytest.mark.db
def test_staff_role_check_pins_the_role_set(migrated_db: str) -> None:
    """0011's CHECK admits exactly the StaffRole members. Both probes roll back —
    nothing leaks into other tests sharing the container."""

    async def check() -> None:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                await conn.execute(text(_STAFF_INSERT), {"role": "shift_manager"})
                await trans.rollback()
            async with engine.connect() as conn:
                trans = await conn.begin()
                with pytest.raises(IntegrityError):
                    await conn.execute(text(_STAFF_INSERT), {"role": "reception"})
                await trans.rollback()
        finally:
            await engine.dispose()

    asyncio.run(check())
