import asyncio

import pytest
from sqlalchemy import text
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
