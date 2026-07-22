import shutil
import subprocess
from collections.abc import Iterator

import pytest

DOCKER_HELP = (
    "DB tests need a running Docker daemon (Docker Desktop, OrbStack, or Colima). "
    "See README → Prerequisites. Fast tests only: `make test` (or `pytest -m 'not db'`)."
)


def _docker_running() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Real Postgres 16 via Testcontainers. RLS behavior must be tested against
    the real engine — SQLite would lie to us."""
    if not _docker_running():
        pytest.fail(DOCKER_HELP, pytrace=False)

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        yield f"postgresql+asyncpg://{pg.username}:{pg.password}@{host}:{port}/{pg.dbname}"
