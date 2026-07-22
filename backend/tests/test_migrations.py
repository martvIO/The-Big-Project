import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.db
def test_migrations_apply_and_uuid_ossp_available(postgres_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(cfg, "head")

    async def check() -> str:
        engine = create_async_engine(postgres_url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT uuid_generate_v4()::text"))
                return str(result.scalar_one())
        finally:
            await engine.dispose()

    generated = asyncio.run(check())
    assert len(generated) == 36
