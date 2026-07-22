import asyncio
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent

DOCKER_HELP = (
    "DB tests need a running Docker daemon (Docker Desktop, OrbStack, or Colima). "
    "See README → Prerequisites. Fast tests only: `make test` (or `pytest -m 'not db'`)."
)

# Test-container-only credentials for the non-owner application role. Isolation
# tests MUST run as this role: the container superuser bypasses RLS unconditionally,
# which would make every isolation assertion vacuously pass.
APP_ROLE_NAME = "boutique_app"
APP_ROLE_PASSWORD = "test-only-app-role-pw"


def _docker_running() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


async def _execute_all(url: str, statements: list[str]) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def run_sql() -> Callable[[str, list[str]], None]:
    """Run DDL/DML statements against a URL, outside any test event loop."""

    def _run(url: str, statements: list[str]) -> None:
        asyncio.run(_execute_all(url, statements))

    return _run


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Real Postgres 16 via Testcontainers, connected as the container superuser.
    RLS behavior must be tested against the real engine — SQLite would lie to us."""
    if not _docker_running():
        pytest.fail(DOCKER_HELP, pytrace=False)

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        yield f"postgresql+asyncpg://{pg.username}:{pg.password}@{host}:{port}/{pg.dbname}"


@pytest.fixture(scope="session")
def migrated_db(postgres_url: str, run_sql: Callable[[str, list[str]], None]) -> str:
    """Superuser URL for a database with all migrations applied and the
    boutique_app login role provisioned (member of the app_user group role
    created by migration 0002)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(cfg, "head")

    run_sql(
        postgres_url,
        [
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE_NAME}') THEN
                CREATE ROLE {APP_ROLE_NAME} LOGIN PASSWORD '{APP_ROLE_PASSWORD}';
              END IF;
            END
            $$
            """,
            f"GRANT app_user TO {APP_ROLE_NAME}",
        ],
    )
    return postgres_url


@pytest.fixture(scope="session")
def app_role_url(migrated_db: str) -> str:
    """Connection URL for the non-owner application role — what production uses."""
    scheme, rest = migrated_db.split("://", 1)
    _, host_part = rest.split("@", 1)
    return f"{scheme}://{APP_ROLE_NAME}:{APP_ROLE_PASSWORD}@{host_part}"
