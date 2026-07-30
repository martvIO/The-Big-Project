"""F31 on real Postgres: the role column round-trips through the database and is
what decides the gate over HTTP.

The fast suite (test_staff_role_gating.py) proves the gate GIVEN a role — every
one of its tests hands the gate a role string built in Python. This module proves
the ROLE: a 'shift_manager' row written past 0011's CHECK comes back out through
login -> resolve_session -> StaffContext.role, reaches the browser, and is what
the RoleGate reads. Real AuthService, real BoutiqueSettingsService, real
RepositoryTenantResolver, real login over HTTP; the app-wiring recipe is
test_tenancy_integration.py's, plus the two state services those tests do not
need. create_app()'s own env-driven session factory is never reached because
every service the exercised routes touch is replaced with a container-backed one,
and SQLAlchemy opens no connection at build time.

Sync `def` tests, never `async def`: asyncio_mode="auto" would give an async test
its own loop and TestClient starts a second one inside it. Seeding therefore goes
through asyncio.run, and every engine is NullPool because TestClient uses it from
its own loop.

Runs as boutique_app (`app_role_url`), the production principal — so _promote
below doubles as proof that production CAN write 'shift_manager' past the new
CHECK under forced RLS with only its GRANTs.

Nothing in production writes staff_users.role: StaffUsersRepository.insert does
not accept it and the column rides its server_default. _promote is therefore a
test-only raw UPDATE, the same shape as test_auth_integration's soft-delete
trick. F51 owns the repository writer; when it lands, _promote becomes a call to
it rather than a hand-written statement.

Every test mints its own tenant slug and staff email: the Postgres container is
session-scoped and nothing here truncates.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.passwords import hash_password
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import AuthService
from app.boutique.service import BoutiqueSettingsService
from app.core.config import Settings
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.main import NOT_AUTHENTICATED_BODY, NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffRole
from app.models.staff_user import StaffUser
from app.tenancy.resolver import RepositoryTenantResolver

pytestmark = pytest.mark.db

PASSWORD = "s3cret-staff-pw"
SETTINGS = Settings(app_env="dev", session_ttl_seconds=3600)
TERMS_BODY = {"terms_text": "Cancel 48h before.", "refundable_until_hours_before": 48}
SETTINGS_PATH = "/manage/settings"
TERMS_PATH = "/manage/terms"


@dataclass(frozen=True)
class Seed:
    tenant_id: uuid.UUID
    slug: str
    email: str
    staff_id: uuid.UUID


def _engine(app_role_url: str) -> AsyncEngine:
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _app(factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    """create_app() with the real resolver and the two state services these
    routes touch repointed at the container. The real resolver matters: the
    tenant comes from a real tenants row via the request Host, so the seam under
    test starts where a browser's request does."""
    app = create_app(resolver=RepositoryTenantResolver(factory))
    app.state.auth_service = AuthService(factory, SETTINGS)
    app.state.boutique_service = BoutiqueSettingsService(
        factory,
        # Generous on purpose: throttling is not the variable under test, and a
        # 429 here would read as a gating failure.
        terms_rate_limiter=FixedWindowRateLimiter(
            max_attempts=100, window_seconds=3600, clock=lambda: 0.0
        ),
    )
    return app


async def _promote(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    role: str,
) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(update(StaffUser).where(StaffUser.id == staff_id).values(role=role))


async def _soft_delete(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, staff_id: uuid.UUID
) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(
            update(StaffUser).where(StaffUser.id == staff_id).values(deleted_at=datetime.now(UTC))
        )


async def _seed(factory: async_sessionmaker[AsyncSession], *, role: str) -> Seed:
    slug = f"gate{uuid.uuid4().hex[:8]}"
    tenant = await TenantsRepository(factory).insert(slug=slug, name="Bella Bridal")
    email = f"staff-{uuid.uuid4().hex[:8]}@bella.example"
    async with tenant_session(factory, tenant.id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(PASSWORD),
            display_name="Staff",
        )
        staff_id = staff.id
    if role != StaffRole.OWNER.value:
        await _promote(factory, tenant.id, staff_id, role)
    return Seed(tenant_id=tenant.id, slug=slug, email=email, staff_id=staff_id)


def _login(client: TestClient, email: str) -> Response:
    return client.post("/manage/auth/login", json={"email": email, "password": PASSWORD})


def _client(app: FastAPI, slug: str) -> TestClient:
    return TestClient(app, base_url=f"http://{slug}.localtest.me")


def test_a_shift_manager_row_round_trips_from_login_to_the_gate(app_role_url: str) -> None:
    """The seam nothing covered before: the role leaves Postgres, crosses login ->
    resolve_session -> StaffContext.role -> RoleGate, and decides admit vs refuse
    over real HTTP. Every other F31 test asserts the gate given a role, or the
    CHECK given a role — none joined the two."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    try:
        seed = asyncio.run(_seed(factory, role=StaffRole.SHIFT_MANAGER.value))
        with _client(_app(factory), seed.slug) as client:
            login = _login(client, seed.email)
            assert login.status_code == 200, login.text
            # DB-sourced, not a fake's constant.
            assert login.json()["role"] == StaffRole.SHIFT_MANAGER.value
            assert client.cookies.get("boutique_session")

            assert client.get("/manage/auth/me").json()["role"] == StaffRole.SHIFT_MANAGER.value
            assert client.get(SETTINGS_PATH).status_code == 200  # admitted
            refused = client.post(TERMS_PATH, json=TERMS_BODY)  # owner-only
            history = client.get(TERMS_PATH)

        assert refused.status_code == 403
        assert refused.json() == NOT_AUTHORIZED_BODY
        # The refusal was total: the gate ran before the service, so nothing was
        # published. A 403 with a written row would be the worse bug.
        assert history.status_code == 200
        assert history.json()["total"] == 0
    finally:
        asyncio.run(engine.dispose())


def test_an_owner_row_still_publishes_terms_over_real_postgres(app_role_url: str) -> None:
    """The control. Without it, the 403 above is indistinguishable from a terms
    path that is simply broken against a real database."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    try:
        seed = asyncio.run(_seed(factory, role=StaffRole.OWNER.value))
        with _client(_app(factory), seed.slug) as client:
            assert _login(client, seed.email).json()["role"] == StaffRole.OWNER.value
            published = client.post(TERMS_PATH, json=TERMS_BODY)
            history = client.get(TERMS_PATH)

        assert published.status_code == 200, published.text
        assert history.json()["total"] == 1
    finally:
        asyncio.run(engine.dispose())


def test_a_demotion_bites_on_the_very_next_request(app_role_url: str) -> None:
    """RoleGate's docstring claims role changes take effect on the next request
    because resolve_session re-reads staff_users — no session state to sweep.
    That claim is why F51 needs no invalidation pass, and nothing tested it.
    Same cookie throughout: no re-login."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    try:
        seed = asyncio.run(_seed(factory, role=StaffRole.OWNER.value))
        with _client(_app(factory), seed.slug) as client:
            assert _login(client, seed.email).status_code == 200
            assert client.post(TERMS_PATH, json=TERMS_BODY).status_code == 200

            asyncio.run(
                _promote(factory, seed.tenant_id, seed.staff_id, StaffRole.SHIFT_MANAGER.value)
            )

            refused = client.post(TERMS_PATH, json=TERMS_BODY)
            still_admitted = client.get(SETTINGS_PATH)
            me = client.get("/manage/auth/me")

        assert refused.status_code == 403
        assert refused.json() == NOT_AUTHORIZED_BODY
        # Demoted, not locked out — the rest of the console still answers.
        assert still_admitted.status_code == 200
        assert me.json()["role"] == StaffRole.SHIFT_MANAGER.value
    finally:
        asyncio.run(engine.dispose())


def test_a_session_from_another_tenant_is_401_not_403(app_role_url: str) -> None:
    """The gate never sees a cross-tenant session: RLS makes the session row
    invisible to resolve_session, so get_current_staff raises first. 401 vs 403
    matters — a 403 would confirm to a prober that the token is a live session
    somewhere on the platform."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    try:
        here = asyncio.run(_seed(factory, role=StaffRole.SHIFT_MANAGER.value))
        elsewhere = asyncio.run(_seed(factory, role=StaffRole.OWNER.value))
        app = _app(factory)
        with _client(app, here.slug) as client:
            assert _login(client, here.email).status_code == 200
            token = client.cookies["boutique_session"]

        with _client(app, elsewhere.slug) as other:
            other.cookies.set("boutique_session", token, domain=f"{elsewhere.slug}.localtest.me")
            admitted_route = other.get(SETTINGS_PATH)
            owner_only_route = other.post(TERMS_PATH, json=TERMS_BODY)

        assert admitted_route.status_code == 401
        assert admitted_route.json() == NOT_AUTHENTICATED_BODY
        # Even the owner-only route answers 401: authentication fails before the
        # gate is reached, so the role never enters the decision.
        assert owner_only_route.status_code == 401
        assert owner_only_route.json() == NOT_AUTHENTICATED_BODY
    finally:
        asyncio.run(engine.dispose())


def test_a_soft_deleted_shift_managers_live_cookie_is_401_not_403(app_role_url: str) -> None:
    """StaffUsersRepository.by_id filters deleted_at IS NULL, so resolve_session
    returns None and the RoleGate is never reached: deactivation is an
    authentication failure, not an authorization one, on the very next request.
    F51's deactivate button rests on this — there is no session sweep."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    try:
        seed = asyncio.run(_seed(factory, role=StaffRole.SHIFT_MANAGER.value))
        with _client(_app(factory), seed.slug) as client:
            assert _login(client, seed.email).status_code == 200
            assert client.get(SETTINGS_PATH).status_code == 200

            asyncio.run(_soft_delete(factory, seed.tenant_id, seed.staff_id))

            admitted_route = client.get(SETTINGS_PATH)
            owner_only_route = client.post(TERMS_PATH, json=TERMS_BODY)

        assert admitted_route.status_code == 401
        assert admitted_route.json() == NOT_AUTHENTICATED_BODY
        assert owner_only_route.status_code == 401
    finally:
        asyncio.run(engine.dispose())
