"""F25 D5 — the console lifecycle end to end, as `boutique_app`.

⚠ db-marked: no Docker locally, so this runs on CI only.

⚠ THIS IS THE PARITY PROOF THE CLI DELETION RESTS ON. The four subcommands leave
`app/cli.py` in the very next commit, and what makes that safe is not the
router's shape — it is that the same four operations, driven over HTTP by an
authenticated operator under the same database role, write the same
`platform_audit_log` rows the shell wrote, with the operator column now carrying
an identity somebody had to authenticate as.

Every audit assertion reads through an OWNER-role connection, because
`platform_audit_log` is INSERT-only for the role under test and genuinely cannot
be SELECTed by it (`test_provisioning.py`'s technique).
"""

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.service import AuthService, InvalidCredentialsError
from app.core.config import Settings
from app.db.repositories.tenants import TenantsRepository
from app.main import create_app
from app.platform.service import ProvisioningService

pytestmark = pytest.mark.db

CONSOLE = "http://admin.localtest.me"
OPERATOR_PASSWORD = "console-operator-pw-2026"
OWNER_PASSWORD = "bella-owner-first-pw"
NEW_OWNER_PASSWORD = "bella-owner-second-pw"


def _settings() -> Settings:
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


def _slug() -> str:
    return f"shop-{uuid.uuid4().hex[:8]}"


def _operator_email() -> str:
    return f"op-{uuid.uuid4().hex[:10]}@modryn.example"


def _audit(owner_url: str, operator: str) -> list[tuple[str, dict]]:
    async def read() -> list[tuple[str, dict]]:
        engine = create_async_engine(owner_url)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT action, details FROM platform_audit_log "
                            "WHERE operator = :operator ORDER BY created_at"
                        ),
                        {"operator": operator},
                    )
                ).all()
                return [(str(r[0]), dict(r[1])) for r in rows]
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _signed_in(app: FastAPI, factory: async_sessionmaker, email: str) -> TestClient:
    result = asyncio.run(
        ProvisioningService(factory).create_operator(
            email=email,
            display_name="Console Operator",
            password=OPERATOR_PASSWORD,
            operator="cli-bootstrap",
        )
    )
    assert result.ok, result.message
    client = TestClient(app, base_url=CONSOLE)
    client.__enter__()
    login = client.post(
        "/platform/auth/login", json={"email": email, "password": OPERATOR_PASSWORD}
    )
    assert login.status_code == 200, login.text
    return client


def test_the_whole_console_lifecycle_writes_the_same_book_the_cli_wrote(
    app: FastAPI, factory: async_sessionmaker, migrated_db: str
) -> None:
    """provision → the new owner logs in → suspend → reset → she logs in with the
    new password. F6's end-to-end, now over HTTP.

    The owner login in the middle is the assertion that matters most: it is what
    proves the console did not merely write rows but actually created a working
    boutique with a working owner, under RLS, as the app role.
    """
    operator_email = _operator_email()
    slug = _slug()
    owner_email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
    auth = AuthService(factory, _settings())

    client = _signed_in(app, factory, operator_email)
    try:
        provisioned = client.post(
            "/platform/tenants/provision",
            json={
                "slug": slug,
                "name": "Bella Bridal",
                "owner_email": owner_email,
                "owner_password": OWNER_PASSWORD,
            },
        )
        assert provisioned.status_code == 200, provisioned.text

        tenant = asyncio.run(TenantsRepository(factory).by_slug(slug))
        assert tenant is not None
        staff, _ = asyncio.run(auth.login(tenant.id, owner_email, OWNER_PASSWORD))
        assert staff.email == owner_email

        listed = client.get("/platform/tenants")
        assert listed.status_code == 200
        rows = {row["slug"]: row for row in listed.json()["tenants"]}
        assert rows[slug]["name"] == "Bella Bridal"
        assert rows[slug]["status"] == "active"

        assert client.post("/platform/tenants/suspend", json={"slug": slug}).status_code == 200

        reset = client.post(
            "/platform/tenants/reset-owner-password",
            json={
                "slug": slug,
                "owner_email": owner_email,
                "new_password": NEW_OWNER_PASSWORD,
            },
        )
        assert reset.status_code == 200, reset.text

        # The reset is REAL: the new password authenticates and — the half that
        # would otherwise go untested — the old one no longer does.
        staff, _ = asyncio.run(auth.login(tenant.id, owner_email, NEW_OWNER_PASSWORD))
        assert staff.email == owner_email
        with pytest.raises(InvalidCredentialsError):
            asyncio.run(auth.login(tenant.id, owner_email, OWNER_PASSWORD))
    finally:
        client.__exit__(None, None, None)

    # ⚠ EVERY ROW CARRIES THE AUTHENTICATED OPERATOR'S EMAIL. On the CLI this
    # column held whatever `$USER` was on the box; D5's whole substance is that
    # it now holds an identity somebody had to authenticate as.
    actions = [action for action, _ in _audit(migrated_db, operator_email)]
    assert actions == [
        "operator_login",
        "tenant_provisioned",
        # conflict 4: a GET that writes a row, and the only one. F21 D6 made
        # `list_tenants` the single audited read — a full cross-tenant
        # enumeration — and the console carries that row from shell to HTTP
        # verbatim rather than dropping it on the way.
        "tenants_listed",
        "tenant_suspended",
        "owner_password_reset",
    ]
    details = dict(_audit(migrated_db, operator_email))
    assert details["tenant_provisioned"] == {"slug": slug}
    # The password is nowhere in the book — not the owner's initial one, not the
    # reset one.
    for _, row in _audit(migrated_db, operator_email):
        assert OWNER_PASSWORD not in str(row)
        assert NEW_OWNER_PASSWORD not in str(row)


def test_the_console_reset_ends_the_owners_live_sessions(
    app: FastAPI, factory: async_sessionmaker, migrated_db: str
) -> None:
    """⚠ THE RESET IS THE DOOR AN OPERATOR OPENS WHEN AN OWNER IS COMPROMISED, so
    a new hash alone does not close it.

    The lifecycle test above proves the credential changed; it cannot prove the
    takeover ended. `resolve_session` never consults `password_hash`, and
    `settings.session_ttl_seconds` is twelve hours — so an attacker holding the
    phished owner's cookie keeps full owner privileges for the rest of that TTL
    while the console reports «הסיסמה אופסה». `auth/staff.py` pays for the same
    claim with `revoke_for_staff_user` on the tenant-side password change; the
    console's reset is the same operation at higher stakes and must do the same.

    No acting-cookie exception here, unlike the staff path: the operator holds no
    session of the owner's, so every one of them goes."""
    operator_email = _operator_email()
    slug = _slug()
    owner_email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
    auth = AuthService(factory, _settings())

    client = _signed_in(app, factory, operator_email)
    try:
        provisioned = client.post(
            "/platform/tenants/provision",
            json={
                "slug": slug,
                "name": "Bella Bridal",
                "owner_email": owner_email,
                "owner_password": OWNER_PASSWORD,
            },
        )
        assert provisioned.status_code == 200, provisioned.text
        tenant = asyncio.run(TenantsRepository(factory).by_slug(slug))
        assert tenant is not None

        # The stolen cookie: minted before the reset, live and unexpired.
        _, token = asyncio.run(auth.login(tenant.id, owner_email, OWNER_PASSWORD))
        assert asyncio.run(auth.resolve_session(tenant.id, token)) is not None

        reset = client.post(
            "/platform/tenants/reset-owner-password",
            json={
                "slug": slug,
                "owner_email": owner_email,
                "new_password": NEW_OWNER_PASSWORD,
            },
        )
        assert reset.status_code == 200, reset.text

        assert asyncio.run(auth.resolve_session(tenant.id, token)) is None
    finally:
        client.__exit__(None, None, None)


def test_a_reserved_slug_is_refused_with_its_code_and_its_failure_audit(
    app: FastAPI, factory: async_sessionmaker, migrated_db: str
) -> None:
    """THE F5 LESSON, over HTTP. The refusal is a returned `CommandResult`, not a
    raised exception, so the `TENANT_PROVISION_FAILED` row commits — a router that
    validated the slug itself and raised first would answer the same 400 with a
    silently thinner book."""
    operator_email = _operator_email()
    client = _signed_in(app, factory, operator_email)
    try:
        refused = client.post(
            "/platform/tenants/provision",
            json={
                "slug": "admin",
                "name": "Impostor",
                "owner_email": "o@x.example",
                "owner_password": OWNER_PASSWORD,
            },
        )
        assert refused.status_code == 400
        assert refused.json()["error"]["code"] == "invalid_or_reserved_slug"
    finally:
        client.__exit__(None, None, None)

    rows = _audit(migrated_db, operator_email)
    assert [action for action, _ in rows] == ["operator_login", "tenant_provision_failed"]
    assert rows[-1][1] == {"slug": "admin", "reason": "invalid_or_reserved_slug"}


def test_a_duplicate_slug_is_a_409_that_also_commits_its_failure_audit(
    app: FastAPI, factory: async_sessionmaker, migrated_db: str
) -> None:
    """409 and not 400: the request is well-formed and another boutique is what
    refuses it — possibly a SUSPENDED one, which still holds its slug and which
    the operator cannot see in the list."""
    operator_email = _operator_email()
    slug = _slug()
    client = _signed_in(app, factory, operator_email)
    body = {
        "slug": slug,
        "name": "First",
        "owner_email": f"a-{uuid.uuid4().hex[:8]}@x.example",
        "owner_password": OWNER_PASSWORD,
    }
    try:
        assert client.post("/platform/tenants/provision", json=body).status_code == 200
        again = client.post("/platform/tenants/provision", json={**body, "name": "Second"})
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "slug_taken"
    finally:
        client.__exit__(None, None, None)

    assert [action for action, _ in _audit(migrated_db, operator_email)] == [
        "operator_login",
        "tenant_provisioned",
        "tenant_provision_failed",
    ]


def test_row_actions_against_a_boutique_that_is_not_there_are_404s(
    app: FastAPI, factory: async_sessionmaker
) -> None:
    """The race the console's local row-patching makes possible: an operator acts
    on a row that was fetched once at mount. Both refusals map to the code the
    console has a sentence for."""
    client = _signed_in(app, factory, _operator_email())
    try:
        missing = _slug()
        suspend = client.post("/platform/tenants/suspend", json={"slug": missing})
        assert suspend.status_code == 404
        assert suspend.json()["error"]["code"] == "tenant_not_found"

        slug = _slug()
        assert (
            client.post(
                "/platform/tenants/provision",
                json={
                    "slug": slug,
                    "name": "Bella",
                    "owner_email": f"owner-{uuid.uuid4().hex[:8]}@bella.example",
                    "owner_password": OWNER_PASSWORD,
                },
            ).status_code
            == 200
        )
        wrong_owner = client.post(
            "/platform/tenants/reset-owner-password",
            json={
                "slug": slug,
                "owner_email": "not-the-owner@bella.example",
                "new_password": NEW_OWNER_PASSWORD,
            },
        )
        assert wrong_owner.status_code == 404
        assert wrong_owner.json()["error"]["code"] == "owner_not_found"
    finally:
        client.__exit__(None, None, None)
