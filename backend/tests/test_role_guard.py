import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.session import ensure_safe_database_role, verify_database_role

pytestmark = pytest.mark.db

OWNER_PROBE_ROLE = "guard_owner_probe"
OWNER_PROBE_PASSWORD = "test-only-owner-probe-pw"
OWNER_PROBE_TABLE = "guard_ownership_probe"


class _StubSettings:
    """Only `app_env` is read by `ensure_safe_database_role`, and constructing a
    real `Settings` would make the near-miss values unreachable (the field is a
    Literal) — which is the whole point of driving them."""

    def __init__(self, app_env: str) -> None:
        self.app_env = app_env


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


@pytest.mark.parametrize("app_env", ["staging", "production", "Dev", "DEV", "dev-ish", ""])
async def test_the_boot_guard_is_exempt_for_dev_and_for_nothing_else(
    app_env: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F21 B5 / row R7. `ensure_safe_database_role` (`db/session.py:45-50`) is the
    single source of truth for "when may we skip the RLS-bypass check", and the
    three tests above prove what `verify_database_role` DECIDES without ever
    proving that anything CALLS it. A guard that is correct and unreached is the
    same deployment as no guard.

    Parametrised over the two real non-dev values plus four near-misses. `"Dev"`
    and `"DEV"` are unreachable through `Settings` — `app_env` is a
    `Literal["dev","staging","production"]` — and that is exactly why they are
    driven here against the module's own `get_settings` seam: the mutation this
    catches is an edit to the COMPARISON (`.lower() != "dev"`, `not in ("dev",
    "staging")`, a truthiness test), and a Literal cannot stop someone widening
    the branch. `""` covers the unset-env shape.

    R7's other half — that the DEPLOYED role is genuinely non-superuser — needs a
    deployment and stays amber, owner F62. This is the half provable here, and
    D2's parked table says so in as many words.

    Mutation-checked: `app_env not in ("dev", "staging")` reds the staging leg;
    `app_env.lower() != "dev"` reds `Dev` and `DEV`; dropping the call entirely
    reds every leg.
    """
    called = False

    async def _spy(engine: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.db.session.get_settings", lambda: _StubSettings(app_env))
    monkeypatch.setattr("app.db.session.get_engine", lambda: object())
    monkeypatch.setattr("app.db.session.verify_database_role", _spy)

    await ensure_safe_database_role()
    assert called, f"app_env={app_env!r} skipped the RLS-bypass check"


async def test_the_boot_guard_is_exempt_for_exactly_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other direction, and it is what stops the test above from being
    satisfiable by deleting the exemption: local runs use the container superuser
    and MUST skip, or nothing starts on a laptop."""
    called = False

    async def _spy(engine: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.db.session.get_settings", lambda: _StubSettings("dev"))
    monkeypatch.setattr("app.db.session.get_engine", lambda: object())
    monkeypatch.setattr("app.db.session.verify_database_role", _spy)

    await ensure_safe_database_role()
    assert not called, "dev must stay exempt — a laptop connects as the superuser"
