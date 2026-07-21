import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.session import verify_database_role

pytestmark = pytest.mark.db


async def test_superuser_role_is_refused(migrated_db: str) -> None:
    engine = create_async_engine(migrated_db)
    try:
        with pytest.raises(RuntimeError, match="bypass row-level security"):
            await verify_database_role(engine)
    finally:
        await engine.dispose()


async def test_app_role_is_accepted(app_role_url: str) -> None:
    engine = create_async_engine(app_role_url)
    try:
        await verify_database_role(engine)
    finally:
        await engine.dispose()
