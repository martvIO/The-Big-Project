import dataclasses
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_password
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.constants import PlatformAuditAction, StaffRole, TenantStatus
from app.models.staff_user import StaffUser
from app.models.tenant import Tenant
from app.platform.repository import PlatformAuditLogRepository
from app.tenancy.slugs import is_valid_slug


@dataclasses.dataclass(frozen=True)
class CommandResult:
    ok: bool
    message: str
    tenant_id: UUID | None = None


@dataclasses.dataclass(frozen=True)
class TenantSummary:
    slug: str
    name: str
    status: str
    created_at: datetime


class ProvisioningService:
    """Platform-operator orchestration for the tenant lifecycle. Business
    failures are returned (never raised), so failure audits commit rather than
    rolling back with the exception that reports them (the Feature 5 lesson)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._tenants = TenantsRepository(session_factory)
        self._staff = StaffUsersRepository()
        self._audit = PlatformAuditLogRepository()

    async def provision(
        self,
        *,
        slug: str,
        name: str,
        owner_email: str,
        owner_password: str,
        operator: str,
    ) -> CommandResult:
        if not is_valid_slug(slug):
            return await self._fail_provision(operator, slug, "invalid_or_reserved_slug")
        if not owner_password.strip():
            # A blank password (e.g. `echo -n | … provision`) would create a
            # loginable owner with a hashed empty string — reject it.
            return await self._fail_provision(operator, slug, "empty_password")
        if await self._tenants.by_slug(slug) is not None:
            return await self._fail_provision(operator, slug, "slug_taken")

        tenant_id = uuid4()
        try:
            # Atomic: tenant + owner + audit commit together, or none of them.
            async with tenant_session(self._session_factory, tenant_id) as session:
                session.add(Tenant(id=tenant_id, slug=slug, name=name))
                await session.flush()
                await self._staff.insert(
                    session,
                    tenant_id=tenant_id,
                    email=owner_email.lower(),
                    password_hash=hash_password(owner_password),
                    display_name=owner_email,
                )
                await self._audit.record(
                    session,
                    operator=operator,
                    action=PlatformAuditAction.TENANT_PROVISIONED,
                    target_tenant_id=tenant_id,
                    details={"slug": slug},
                )
        except IntegrityError:
            # Race/suspended-slug backstop behind the partial unique index.
            return await self._fail_provision(operator, slug, "slug_taken")

        return CommandResult(ok=True, message="provisioned", tenant_id=tenant_id)

    async def suspend(self, *, slug: str, operator: str) -> CommandResult:
        tenant = await self._tenants.by_slug(slug)
        if tenant is None:
            return CommandResult(ok=False, message="tenant_not_found")
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(Tenant)
                .where(Tenant.id == tenant.id, Tenant.deleted_at.is_(None))
                .values(status=TenantStatus.SUSPENDED)
            )
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.TENANT_SUSPENDED,
                target_tenant_id=tenant.id,
                details={"slug": slug},
            )
        return CommandResult(ok=True, message="suspended", tenant_id=tenant.id)

    async def list_tenants(self) -> list[TenantSummary]:
        async with self._session_factory() as session:
            stmt = select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.created_at)
            rows = (await session.execute(stmt)).scalars().all()
        return [
            TenantSummary(slug=t.slug, name=t.name, status=t.status, created_at=t.created_at)
            for t in rows
        ]

    async def reset_owner_password(
        self, *, slug: str, owner_email: str, new_password: str, operator: str
    ) -> CommandResult:
        if not new_password.strip():
            return CommandResult(ok=False, message="empty_password")
        tenant = await self._tenants.by_slug(slug)
        if tenant is None:
            return CommandResult(ok=False, message="tenant_not_found")
        async with tenant_session(self._session_factory, tenant.id) as session:
            # updated_at is set by the DB trigger — never assign it here.
            result = await session.execute(
                update(StaffUser)
                .where(
                    StaffUser.tenant_id == tenant.id,
                    StaffUser.email == owner_email.lower(),
                    StaffUser.role == StaffRole.OWNER,
                    StaffUser.deleted_at.is_(None),
                )
                .values(password_hash=hash_password(new_password))
                .returning(StaffUser.id)
            )
            if result.scalar_one_or_none() is None:
                return CommandResult(ok=False, message="owner_not_found")
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.OWNER_PASSWORD_RESET,
                target_tenant_id=tenant.id,
                details={"slug": slug, "email": owner_email.lower()},
            )
        return CommandResult(ok=True, message="password_reset", tenant_id=tenant.id)

    async def _fail_provision(self, operator: str, slug: str, reason: str) -> CommandResult:
        details: dict[str, Any] = {"slug": slug, "reason": reason}
        async with self._session_factory() as session, session.begin():
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.TENANT_PROVISION_FAILED,
                details=details,
            )
        return CommandResult(ok=False, message=reason)
