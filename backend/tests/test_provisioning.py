import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.service import AuthService, InvalidCredentialsError
from app.core.config import Settings
from app.models.constants import StaffRole
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
        # ProvisioningService still names no role at its call site; since F51,
        # StaffUsersRepository.insert defaults the kwarg to OWNER in Python, so
        # the INSERT emits it explicitly and staff_users' server_default is belt
        # rather than the sole mechanism. 0011's CHECK and the whole default-deny
        # posture rest on a freshly provisioned tenant's founder being an owner,
        # and this assertion is still what pins it.
        assert staff.role == StaffRole.OWNER.value
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
                    owner_password="owner-first-pw",
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
                owner_password="owner-first-pw",
                operator="t",
            )
        )
        assert first.ok
        second = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Second",
                owner_email="b@x.example",
                owner_password="owner-first-pw",
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


def test_every_password_this_service_sets_carries_the_staff_floor(app_role_url: str) -> None:
    """⚠ THE SAME 10 CHARACTERS `/manage/staff` ENFORCES, on the three passwords
    that were exempt.

    `MIN_STAFF_PASSWORD_LENGTH`'s own comment argues that length is the only
    control surviving a password one person chooses and speaks to another — which
    is the trip all three of these make. Until this check, an operator could
    provision a boutique whose owner password was `a`, reset an existing owner to
    `a`, or seed the credential that controls EVERY tenant with `a`, through a
    console the boutique's own staff screen would have refused. It also underwrites
    spec D6's decision to decline TOTP on the strength of the operator credential
    being "argon2-hashed, un-enumerable, rate-limited".

    Blank keeps its own code (tested above) so the console's existing sentence and
    the CLI's message are unchanged.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    try:
        slug = _slug()
        short = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Nine",
                owner_email="o@x.example",
                owner_password="nine-char",  # 9
                operator="t",
            )
        )
        assert short.ok is False and short.message == "password_too_short"

        assert asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Ten",
                owner_email="o@x.example",
                owner_password="ten-charss",  # 10, the floor itself
                operator="t",
            )
        ).ok

        reset = asyncio.run(
            provisioning.reset_owner_password(
                slug=slug,
                owner_email="o@x.example",
                new_password="nine-char",
                operator="t",
            )
        )
        assert reset.ok is False and reset.message == "password_too_short"

        seeded = asyncio.run(
            provisioning.create_operator(
                email=f"{uuid.uuid4().hex[:8]}@modryn.example",
                display_name="Short",
                password="a",
                operator="cli",
            )
        )
        assert seeded.ok is False and seeded.message == "password_too_short"
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
                owner_password="owner-first-pw",
                operator="t",
            )
        ).ok
        assert asyncio.run(provisioning.suspend(slug=slug, operator="t")).ok

        second = asyncio.run(
            provisioning.provision(
                slug=slug,
                name="Second",
                owner_email="b@x.example",
                owner_password="owner-first-pw",
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

    provisioning._staff.insert = _boom  # type: ignore[method-assign,assignment]
    try:
        slug = _slug()
        with pytest.raises(RuntimeError):
            asyncio.run(
                provisioning.provision(
                    slug=slug,
                    name="Orphan?",
                    owner_email="o@x.example",
                    owner_password="owner-first-pw",
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
                owner_password="owner-old-pw",
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
                owner_password="owner-first-pw",
                operator="t",
            )
        )
        assert asyncio.run(provisioning.suspend(slug=slug, operator="t")).ok

        rows = asyncio.run(provisioning.list_tenants(operator="t"))
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
                owner_password="owner-old-pw",
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
            asyncio.run(auth.login(tenant_id, "owner@shop.example", "owner-old-pw"))
        staff, _ = asyncio.run(auth.login(tenant_id, "owner@shop.example", "brand-new-pw"))
        assert staff.email == "owner@shop.example"

        assert (
            asyncio.run(
                provisioning.reset_owner_password(
                    slug=_slug(),
                    owner_email="nobody@x.example",
                    new_password="owner-next-pw",
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
                owner_password="owner-first-pw",
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


def test_listing_tenants_writes_a_platform_audit_row(app_role_url: str, migrated_db: str) -> None:
    """F21 D6 / row R38. `list` is a FULL cross-tenant read — every boutique's
    slug, trading name and status in one output — and before F21 it was the one
    privileged CLI operation that left no trail at all. `--operator` was already
    parsed (`cli.py:68-69`) and thrown away.

    The row's `target_tenant_id` is NULL because no single tenant is the subject,
    and `details` carries the COUNT and never the slugs: reproducing the
    enumeration inside the audit table would be the leak twice over.
    """
    engine = _engine(app_role_url)
    factory = _factory(engine)
    provisioning = ProvisioningService(factory)
    # app_user has INSERT-only on platform_audit_log; the read is privileged.
    reader_engine = _engine(migrated_db)
    reader_factory = _factory(reader_engine)
    operator = f"lister-{uuid.uuid4().hex[:8]}"
    try:
        rows = asyncio.run(provisioning.list_tenants(operator=operator))

        async def audit_rows() -> list[tuple[str, object, object]]:
            async with reader_factory() as session:
                res = await session.execute(
                    text(
                        "SELECT action, target_tenant_id, details FROM platform_audit_log "
                        "WHERE operator = :op ORDER BY created_at"
                    ),
                    {"op": operator},
                )
                return [(r[0], r[1], r[2]) for r in res.all()]

        written = asyncio.run(audit_rows())
        assert len(written) == 1, f"expected exactly one row, got {len(written)}"
        action, target, details = written[0]
        assert action == "tenants_listed"
        assert target is None
        assert details == {"tenants": len(rows)}
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
