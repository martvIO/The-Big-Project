import asyncio
import dataclasses
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent

DOCKER_HELP = (
    "DB and media tests need a running Docker daemon (Testcontainers Postgres + MinIO): "
    "Docker Desktop, OrbStack, or Colima. "
    "See README → Prerequisites. Fast tests only: `make test` (or `pytest -m 'not db'`)."
)

# Pinned like postgres:16-alpine — bumping it is a deliberate commit, not a
# silent drift in what the POST-policy assertions run against.
MINIO_IMAGE = "minio/minio:RELEASE.2025-04-22T22-12-26Z"
MEDIA_BUCKET = "boutique-test-media"

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


@dataclasses.dataclass(frozen=True)
class MinioEndpoint:
    """Everything a test needs to point an S3MediaStorage at the container —
    and nothing that would make this fixture hold an open client."""

    url: str
    access_key: str
    secret_key: str
    bucket: str


def _create_bucket(endpoint: MinioEndpoint) -> None:
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=endpoint.url,
        aws_access_key_id=endpoint.access_key,
        aws_secret_access_key=endpoint.secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    client.create_bucket(Bucket=endpoint.bucket)


@pytest.fixture(scope="session")
def minio_container() -> Iterator[MinioEndpoint]:
    """Real MinIO via Testcontainers. MinIO over moto by binding decision: it
    performs genuine SigV4 verification and actually enforces POST-policy
    conditions, so the upload assertions mean something.

    Yields an endpoint and credentials, never a client — a module-level client
    anywhere would start this container during collection, including under
    `-m 'not db'`. The bucket is created with the boto3 client we already depend
    on rather than the minio SDK, so tests grow no second untyped import."""
    if not _docker_running():
        pytest.fail(DOCKER_HELP, pytrace=False)

    from testcontainers.minio import MinioContainer

    with MinioContainer(MINIO_IMAGE) as container:
        config = container.get_config()
        endpoint = MinioEndpoint(
            url=f"http://{config['endpoint']}",
            access_key=config["access_key"],
            secret_key=config["secret_key"],
            bucket=MEDIA_BUCKET,
        )
        _create_bucket(endpoint)
        yield endpoint
