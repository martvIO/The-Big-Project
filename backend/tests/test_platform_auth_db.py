"""F25 D3/D4 against real Postgres, as `boutique_app`.

⚠ db-marked: no Docker locally, so these run on CI only.

The fast module next door proves the HTTP shape with a fake service. This one
proves the parts a fake cannot: that argon2 verification, the session lookup's
two predicates and — above all — the audit writes work under the grants the web
process actually holds. `platform_audit_log` is INSERT-only for this role, so
every assertion about a row is read back through an OWNER-role connection
(`test_provisioning.py`'s technique). A test that read the book as the app role
would be asserting something the product cannot do.
"""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.cookies import SESSION_COOKIE, platform_session_cookie_name
from app.auth.rate_limit import FixedWindowRateLimiter
from app.core.config import Settings
from app.db.repositories.platform_operators import PlatformOperatorsRepository
from app.db.repositories.platform_sessions import PlatformSessionsRepository
from app.main import create_app
from app.platform.auth import OperatorAuthService
from app.platform.service import ProvisioningService

pytestmark = pytest.mark.db

CONSOLE = "http://admin.localtest.me"
PASSWORD = "op-console-pw-2026"

# The suite runs with `app_env="dev"`, so `secure_cookies` is False and the name
# has no `__Host-` prefix. The prefixed form is asserted in its own test, driven
# off a non-dev Settings — the prefix is browser-enforced and the browser also
# refuses it without Secure, which dev does not set.
PLATFORM_SESSION_COOKIE = platform_session_cookie_name(secure=False)

OPERATORS = PlatformOperatorsRepository()
SESSIONS = PlatformSessionsRepository()


def _settings() -> Settings:
    # dev, so the lifespan's role guard takes its dev exemption and does not
    # reach for the process-global engine. The TTL is the real default — the
    # expiry test moves the ROW, not the clock, so nothing here needs it shrunk.
    return Settings(app_env="dev")


@pytest.fixture
def factory(app_role_url: str) -> Iterator[async_sessionmaker]:
    engine: AsyncEngine = create_async_engine(app_role_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture
def app(factory: async_sessionmaker, monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    monkeypatch.setattr("app.main.get_settings", _settings)
    monkeypatch.setattr("app.main.get_session_factory", lambda: factory)

    async def _resolver(slug: str) -> None:
        return None

    yield create_app(resolver=_resolver)


def _email() -> str:
    return f"op-{uuid.uuid4().hex[:10]}@modryn.example"


def _seed_operator(factory: async_sessionmaker, email: str, who: str) -> None:
    result = asyncio.run(
        ProvisioningService(factory).create_operator(
            email=email, display_name="Dana", password=PASSWORD, operator=who
        )
    )
    assert result.ok, result.message


def _audit_actions(owner_url: str, operator: str) -> list[str]:
    async def read() -> list[str]:
        engine = create_async_engine(owner_url)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT action FROM platform_audit_log WHERE operator = :operator "
                            "ORDER BY created_at"
                        ),
                        {"operator": operator},
                    )
                ).all()
                return [str(r[0]) for r in rows]
        finally:
            await engine.dispose()

    return asyncio.run(read())


def test_the_login_lifecycle_works_as_the_app_role_and_audits_both_outcomes(
    app: FastAPI, factory: async_sessionmaker, migrated_db: str
) -> None:
    """create-operator → HTTP login → me → logout, end to end, under the grants
    the web process actually holds.

    The failure comes FIRST so its audit row is proved to have COMMITTED — the F5
    lesson at the platform's front door. A refusal reported by an exception raised
    inside the transaction would roll back the very row that reports it, and the
    401 would look identical."""
    email = _email()
    _seed_operator(factory, email, who="cli-bootstrap")

    with TestClient(app, base_url=CONSOLE) as client:
        refused = client.post(
            "/platform/auth/login", json={"email": email, "password": "not-the-password"}
        )
        assert refused.status_code == 401
        assert refused.json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert PLATFORM_SESSION_COOKIE not in refused.cookies

        # An unknown ADDRESS answers the same body — the dummy argon2 verify is
        # what closes the timing half, and this closes the response half.
        unknown = client.post(
            "/platform/auth/login", json={"email": _email(), "password": PASSWORD}
        )
        assert unknown.json() == refused.json()

        ok = client.post("/platform/auth/login", json={"email": email, "password": PASSWORD})
        assert ok.status_code == 200
        assert ok.json()["email"] == email
        assert client.cookies.get(PLATFORM_SESSION_COOKIE)

        me = client.get("/platform/auth/me")
        assert me.status_code == 200
        assert me.json() == {"email": email, "display_name": "Dana"}

        assert client.post("/platform/auth/logout").status_code == 200
        # The revoke is real, not just a cleared cookie: replaying the token the
        # browser was told to forget must fail too.
        assert client.get("/platform/auth/me").status_code == 401

    assert _audit_actions(migrated_db, email) == [
        "operator_login_failed",
        "operator_login",
    ]


def test_a_failed_login_for_an_unknown_address_still_writes_its_row(
    app: FastAPI, migrated_db: str
) -> None:
    """AUDIT BYPASS. The unknown-address path is the one that could quietly write
    nothing — there is no operator row to hang the record on — and it is exactly
    the path a credential-stuffing run spends all its requests in."""
    stranger = _email()
    with TestClient(app, base_url=CONSOLE) as client:
        assert (
            client.post(
                "/platform/auth/login", json={"email": stranger, "password": "guess"}
            ).status_code
            == 401
        )
    assert _audit_actions(migrated_db, stranger) == ["operator_login_failed"]


def test_the_budget_trips_at_the_ceiling_and_touches_no_other_limiter(
    app: FastAPI, factory: async_sessionmaker
) -> None:
    """BRUTE FORCE, end to end. The console's budget is its OWN instance, so
    spending it must leave the staff budget untouched — `max_attempts` lives on
    the limiter (`.memory/limiter-max-is-per-instance`)."""
    email = _email()
    _seed_operator(factory, email, who="cli-bootstrap")
    app.state.platform_login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=lambda: 0.0
    )

    with TestClient(app, base_url=CONSOLE) as client:
        for _ in range(3):
            assert (
                client.post(
                    "/platform/auth/login", json={"email": email, "password": "wrong"}
                ).status_code
                == 401
            )
        blocked = client.post("/platform/auth/login", json={"email": email, "password": PASSWORD})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    # Nothing was recorded against the staff budget.
    assert not app.state.login_rate_limiter.is_blocked(f"e:{email}")


def test_an_expired_session_is_refused(app: FastAPI, factory: async_sessionmaker) -> None:
    """The TTL is a predicate on the ROW, so this test moves the row rather than
    the clock — which is what production actually relies on, since nothing slides
    `expires_at` after the insert."""
    email = _email()
    _seed_operator(factory, email, who="cli-bootstrap")

    with TestClient(app, base_url=CONSOLE) as client:
        assert (
            client.post(
                "/platform/auth/login", json={"email": email, "password": PASSWORD}
            ).status_code
            == 200
        )
        assert client.get("/platform/auth/me").status_code == 200

        async def expire() -> None:
            async with factory() as session, session.begin():
                operator = await OPERATORS.by_active_email(session, email)
                assert operator is not None
                await session.execute(
                    text(
                        "UPDATE platform_sessions SET expires_at = :past "
                        "WHERE operator_id = :operator_id"
                    ),
                    {"past": datetime.now(UTC) - timedelta(seconds=1), "operator_id": operator.id},
                )

        asyncio.run(expire())
        assert client.get("/platform/auth/me").status_code == 401


def test_a_deactivated_operators_live_session_is_refused_immediately(
    app: FastAPI, factory: async_sessionmaker
) -> None:
    """⚠ THE SESSION ROW IS LEFT LIVE ON PURPOSE. `deactivate-operator` revokes
    sessions too, so going through it would prove the revoke and leave the
    re-read untested — and the re-read is the property that makes deactivation
    bite even on a path that forgot to sweep. So this soft-deletes the operator
    only, and asserts the still-live cookie is refused anyway."""
    email = _email()
    _seed_operator(factory, email, who="cli-bootstrap")

    with TestClient(app, base_url=CONSOLE) as client:
        assert (
            client.post(
                "/platform/auth/login", json={"email": email, "password": PASSWORD}
            ).status_code
            == 200
        )
        assert client.get("/platform/auth/me").status_code == 200

        async def deactivate_only() -> str:
            async with factory() as session, session.begin():
                operator = await OPERATORS.by_active_email(session, email)
                assert operator is not None
                await OPERATORS.soft_delete(session, operator.id)
                live = (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM platform_sessions "
                            "WHERE operator_id = :operator_id AND deleted_at IS NULL"
                        ),
                        {"operator_id": operator.id},
                    )
                ).scalar_one()
                return str(live)

        # The session row survives the soft delete — the refusal below is the
        # re-read and nothing else.
        assert asyncio.run(deactivate_only()) == "1"
        assert client.get("/platform/auth/me").status_code == 401


def test_a_staff_cookie_is_worthless_on_the_console_against_the_real_service(
    app: FastAPI, factory: async_sessionmaker
) -> None:
    """HOST CONFUSION's sibling: POPULATION confusion. The staff cookie's value is
    a real live operator token here, sent under the staff NAME — so the only thing
    refusing it is that the console reads a different cookie against a different
    table. Two populations, two lookup paths (spec D3)."""
    email = _email()
    _seed_operator(factory, email, who="cli-bootstrap")

    with TestClient(app, base_url=CONSOLE) as client:
        assert (
            client.post(
                "/platform/auth/login", json={"email": email, "password": PASSWORD}
            ).status_code
            == 200
        )
        token = client.cookies.get(PLATFORM_SESSION_COOKIE)
        assert token is not None
        client.cookies.clear()
        client.cookies.set(SESSION_COOKIE, token, domain="admin.localtest.me")
        assert client.get("/platform/auth/me").status_code == 401


def test_resolve_session_never_answers_for_a_token_it_did_not_mint(
    factory: async_sessionmaker,
) -> None:
    """The service directly, below HTTP: only the sha256 is stored, so a caller
    holding the STORED value rather than the token cannot authenticate with it.
    A lookup that compared the raw string would pass every other test here."""
    email = _email()
    _seed_operator(factory, email, who="cli-bootstrap")
    service = OperatorAuthService(factory, _settings())
    _, token = asyncio.run(service.login(email, PASSWORD))

    from app.auth.tokens import hash_token

    assert asyncio.run(service.resolve_session(token)) is not None
    assert asyncio.run(service.resolve_session(hash_token(token))) is None
    assert asyncio.run(service.resolve_session(uuid.uuid4().hex)) is None
