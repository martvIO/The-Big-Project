import asyncio
import uuid
from datetime import UTC

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.passwords import hash_password
from app.auth.service import AuthService, InvalidCredentialsError
from app.core.config import Settings
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session

pytestmark = pytest.mark.db

TENANT_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SETTINGS = Settings(app_env="dev", session_ttl_seconds=3600)


def _engine(app_role_url: str) -> AsyncEngine:
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed_owner(factory: async_sessionmaker, tenant_id: uuid.UUID, email: str) -> uuid.UUID:
    repo = StaffUsersRepository()
    async with tenant_session(factory, tenant_id) as session:
        staff = await repo.insert(
            session,
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password("s3cret-owner-pw"),
            display_name="Owner",
        )
        return staff.id


def test_login_lifecycle_and_audit(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = AuthService(factory, SETTINGS)
    try:
        email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
        asyncio.run(_seed_owner(factory, TENANT_A, email))

        staff, token = asyncio.run(service.login(TENANT_A, email, "s3cret-owner-pw"))
        assert staff.email == email

        resolved = asyncio.run(service.resolve_session(TENANT_A, token))
        assert resolved is not None and resolved.id == staff.id

        asyncio.run(service.logout(TENANT_A, token))
        assert asyncio.run(service.resolve_session(TENANT_A, token)) is None

        async def actions() -> list[str]:
            async with tenant_session(factory, TENANT_A) as session:
                return await AuditLogRepository().list_actions(session)

        assert set(asyncio.run(actions())) >= {"login", "logout"}
    finally:
        asyncio.run(engine.dispose())


def test_wrong_and_unknown_both_raise_and_audit_login_failed(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = AuthService(factory, SETTINGS)
    try:
        email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
        asyncio.run(_seed_owner(factory, TENANT_A, email))
        with pytest.raises(InvalidCredentialsError):
            asyncio.run(service.login(TENANT_A, email, "wrong"))
        with pytest.raises(InvalidCredentialsError):
            asyncio.run(service.login(TENANT_A, "ghost@nowhere.example", "whatever"))

        # The failure audit must COMMIT despite the raise — it's the durable
        # brute-force record. Both the wrong-password and unknown-email paths log.
        async def actions() -> list[str]:
            async with tenant_session(factory, TENANT_A) as session:
                return await AuditLogRepository().list_actions(session)

        recorded = asyncio.run(actions())
        assert recorded.count("login_failed") == 2
        assert "login" not in recorded
    finally:
        asyncio.run(engine.dispose())


def test_soft_deleted_staff_cannot_authenticate(app_role_url: str) -> None:
    from datetime import datetime

    from sqlalchemy import update

    from app.models.staff_user import StaffUser

    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = AuthService(factory, SETTINGS)
    try:
        email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
        staff_id = asyncio.run(_seed_owner(factory, TENANT_A, email))
        # Establish a live session, then soft-delete the owner underneath it.
        _, token = asyncio.run(service.login(TENANT_A, email, "s3cret-owner-pw"))

        async def soft_delete() -> None:
            async with tenant_session(factory, TENANT_A) as session:
                await session.execute(
                    update(StaffUser)
                    .where(StaffUser.id == staff_id)
                    .values(deleted_at=datetime.now(UTC))
                )

        asyncio.run(soft_delete())

        # New login rejected, and the existing session no longer resolves.
        with pytest.raises(InvalidCredentialsError):
            asyncio.run(service.login(TENANT_A, email, "s3cret-owner-pw"))
        assert asyncio.run(service.resolve_session(TENANT_A, token)) is None
    finally:
        asyncio.run(engine.dispose())


def test_session_is_invisible_across_tenants(app_role_url: str) -> None:
    """The crown-jewel test: a session minted under tenant A must not resolve
    under tenant B's RLS context, even with the exact same token."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = AuthService(factory, SETTINGS)
    try:
        email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
        asyncio.run(_seed_owner(factory, TENANT_A, email))
        _, token = asyncio.run(service.login(TENANT_A, email, "s3cret-owner-pw"))

        assert asyncio.run(service.resolve_session(TENANT_A, token)) is not None
        assert asyncio.run(service.resolve_session(TENANT_B, token)) is None
    finally:
        asyncio.run(engine.dispose())


def test_expired_session_does_not_resolve(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = AuthService(factory, Settings(app_env="dev", session_ttl_seconds=-1))
    try:
        email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
        asyncio.run(_seed_owner(factory, TENANT_A, email))
        _, token = asyncio.run(service.login(TENANT_A, email, "s3cret-owner-pw"))
        assert asyncio.run(service.resolve_session(TENANT_A, token)) is None
    finally:
        asyncio.run(engine.dispose())
