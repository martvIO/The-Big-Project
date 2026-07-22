import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.service import AuthService, InvalidCredentialsError
from app.core.config import Settings
from app.platform.service import ProvisioningService

pytestmark = pytest.mark.db

SETTINGS = Settings(app_env="dev", session_ttl_seconds=3600)


def _engine(app_role_url: str) -> AsyncEngine:
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


def _slug() -> str:
    return f"shop-{uuid.uuid4().hex[:8]}"


def test_provision_creates_a_loginable_owner(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    auth = AuthService(factory, SETTINGS)
    try:
        slug = _slug()
        result = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Bella Bridal",
                owner_email="owner@bella.example",
                owner_password="s3cret-owner-pw",
                operator="tester",
            )
        )
        assert result.ok and result.tenant_id is not None

        # End-to-end: the freshly provisioned owner can authenticate.
        staff, _ = asyncio.run(
            auth.login(result.tenant_id, "owner@bella.example", "s3cret-owner-pw")
        )
        assert staff.email == "owner@bella.example"
    finally:
        asyncio.run(engine.dispose())


def test_provision_rejects_reserved_and_invalid_slugs(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    try:
        for bad in ("admin", "www", "Bella", "bad_slug"):
            result = asyncio.run(
                provisioning.provision(
                    slug=bad,
                    name="X",
                    owner_email="o@x.example",
                    owner_password="pw",
                    operator="tester",
                )
            )
            assert result.ok is False
    finally:
        asyncio.run(engine.dispose())


def test_provision_rejects_duplicate_slug(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    try:
        slug = _slug()
        first = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="First",
                owner_email="a@x.example",
                owner_password="pw",
                operator="t",
            )
        )
        assert first.ok
        second = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Second",
                owner_email="b@x.example",
                owner_password="pw",
                operator="t",
            )
        )
        assert second.ok is False
    finally:
        asyncio.run(engine.dispose())


def test_provision_rejects_blank_password(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    try:
        result = asyncio.run(
            provisioning.provision(
                slug=_slug(),
                name="Blank",
                owner_email="o@x.example",
                owner_password="   ",
                operator="t",
            )
        )
        assert result.ok is False and result.message == "empty_password"
    finally:
        asyncio.run(engine.dispose())


async def _tenant_row_count(reader_factory: async_sessionmaker, slug: str) -> int:
    async with reader_factory() as session:
        res = await session.execute(
            text("SELECT count(*) FROM tenants WHERE slug = :slug"), {"slug": slug}
        )
        return int(res.scalar_one())


def test_provision_after_suspend_hits_integrity_backstop(
    app_role_url: str, migrated_db: str
) -> None:
    """A suspended tenant still holds its slug in the partial unique index, but
    by_slug (active-only) returns None — so the pre-check passes and the
    IntegrityError backstop is what rejects the re-provision. No 2nd tenant row."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    reader_engine = _engine(migrated_db)
    reader_factory = _factory(reader_engine)
    provisioning = ProvisioningService(factory)
    try:
        slug = _slug()
        assert asyncio.run(
            provisioning.provision(
                slug=slug,
                name="First",
                owner_email="a@x.example",
                owner_password="pw",
                operator="t",
            )
        ).ok
        assert asyncio.run(provisioning.suspend(slug=slug, operator="t")).ok

        second = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Second",
                owner_email="b@x.example",
                owner_password="pw",
                operator="t",
            )
        )
        assert second.ok is False and second.message == "slug_taken"
        assert asyncio.run(_tenant_row_count(reader_factory, slug)) == 1
    finally:
        asyncio.run(engine.dispose())
        asyncio.run(reader_engine.dispose())


def test_provision_rolls_back_the_tenant_on_partial_failure(
    app_role_url: str, migrated_db: str
) -> None:
    """Atomicity: if the owner insert fails after the tenant insert, the whole
    transaction rolls back — no orphan tenant without an owner."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    reader_engine = _engine(migrated_db)
    reader_factory = _factory(reader_engine)
    provisioning = ProvisioningService(factory)

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("owner insert failed mid-transaction")

    provisioning._staff.insert = _boom  # type: ignore[method-assign]
    try:
        slug = _slug()
        with pytest.raises(RuntimeError):
            asyncio.run(
                provisioning.provision(
                    slug=slug,
                    name="Orphan?",
                    owner_email="o@x.example",
                    owner_password="pw",
                    operator="t",
                )
            )
        assert asyncio.run(_tenant_row_count(reader_factory, slug)) == 0
    finally:
        asyncio.run(engine.dispose())
        asyncio.run(reader_engine.dispose())


def test_reset_password_rejects_blank_password(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    try:
        slug = _slug()
        asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Shop",
                owner_email="owner@shop.example",
                owner_password="old-pw",
                operator="t",
            )
        )
        result = asyncio.run(
            provisioning.reset_owner_password(
                slug=slug,
                owner_email="owner@shop.example",
                new_password="   ",
                operator="t",
            )
        )
        assert result.ok is False and result.message == "empty_password"
    finally:
        asyncio.run(engine.dispose())


def test_suspend_flips_status_and_list_reflects_it(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    try:
        slug = _slug()
        asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Paused",
                owner_email="o@x.example",
                owner_password="pw",
                operator="t",
            )
        )
        assert asyncio.run(provisioning.suspend(slug=slug, operator="t")).ok

        rows = asyncio.run(provisioning.list_tenants())
        match = [r for r in rows if r.slug == slug]
        assert match and match[0].status == "suspended"

        assert asyncio.run(provisioning.suspend(slug=_slug(), operator="t")).ok is False
    finally:
        asyncio.run(engine.dispose())


def test_reset_password_changes_credentials(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    auth = AuthService(factory, SETTINGS)
    try:
        slug = _slug()
        result = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Shop",
                owner_email="owner@shop.example",
                owner_password="old-pw",
                operator="t",
            )
        )
        tenant_id = result.tenant_id
        assert tenant_id is not None

        reset = asyncio.run(
            provisioning.reset_owner_password(
                slug=slug,
                owner_email="owner@shop.example",
                new_password="brand-new-pw",
                operator="t",
            )
        )
        assert reset.ok

        with pytest.raises(InvalidCredentialsError):
            asyncio.run(auth.login(tenant_id, "owner@shop.example", "old-pw"))
        staff, _ = asyncio.run(auth.login(tenant_id, "owner@shop.example", "brand-new-pw"))
        assert staff.email == "owner@shop.example"

        assert (
            asyncio.run(
                provisioning.reset_owner_password(
                    slug=_slug(),
                    owner_email="nobody@x.example",
                    new_password="pw",
                    operator="t",
                )
            ).ok
            is False
        )
    finally:
        asyncio.run(engine.dispose())


def test_each_state_change_writes_platform_audit(app_role_url: str, migrated_db: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    # app_user has INSERT-only on platform_audit_log; reading operator history
    # is a privileged action, so the audit read uses the superuser connection.
    reader_engine = _engine(migrated_db)
    reader_factory = _factory(reader_engine)
    try:
        slug = _slug()
        r = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Audited",
                owner_email="o@x.example",
                owner_password="pw",
                operator="opsy",
            )
        )
        asyncio.run(provisioning.suspend(slug=slug, operator="opsy"))

        async def audit_rows() -> list[tuple[str, str]]:
            async with reader_factory() as session:
                res = await session.execute(
                    text(
                        "SELECT action, operator FROM platform_audit_log "
                        "WHERE target_tenant_id = :tid ORDER BY created_at"
                    ),
                    {"tid": str(r.tenant_id)},
                )
                return [(row[0], row[1]) for row in res.all()]

        rows = asyncio.run(audit_rows())
        actions = [a for a, _ in rows]
        assert "tenant_provisioned" in actions
        assert "tenant_suspended" in actions
        assert all(op == "opsy" for _, op in rows)
    finally:
        asyncio.run(engine.dispose())
        asyncio.run(reader_engine.dispose())


def test_app_user_cannot_read_platform_audit(app_role_url: str) -> None:
    """Least privilege: the tenant-facing role writes operator history but must
    never read this cross-tenant table."""
    from sqlalchemy.exc import ProgrammingError

    engine = _engine(app_role_url)
    factory = _factory(engine)

    async def read_as_app_user() -> None:
        async with factory() as session:
            await session.execute(text("SELECT count(*) FROM platform_audit_log"))

    try:
        with pytest.raises(ProgrammingError):
            asyncio.run(read_as_app_user())
    finally:
        asyncio.run(engine.dispose())
