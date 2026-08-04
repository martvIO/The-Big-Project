import dataclasses
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_password
from app.booking.backfill import ManageLinkBackfill
from app.core.config import get_settings
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.constants import PlatformAuditAction, StaffRole, TenantStatus
from app.models.staff_user import StaffUser
from app.models.tenant import Tenant
from app.platform.repository import PlatformAuditLogRepository
from app.privacy.retention import RetentionRunner
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

    async def backfill_booking_links(self, *, operator: str) -> CommandResult:
        """F16's one-time deploy step (D10, mechanism per Interview pre-decided
        #9): mint a manage token and schedule a D3-band reminder for every
        already-confirmed future booking.

        It lives on the audited command layer rather than in a standalone script
        because that layer is what F25's platform console will reuse as its
        service layer (pre-decided #20), and because a one-shot operator action
        that touches every tenant's bookings should leave an audit row.

        Safe to re-run: the feed is `manage_token_hash IS NULL`, which the first
        run fills.
        """
        result = await ManageLinkBackfill(self._session_factory).run()
        async with self._session_factory() as session, session.begin():
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.BOOKING_LINKS_BACKFILLED,
                details={
                    "tenants": result.tenants,
                    "tokens_minted": result.tokens_minted,
                    "reminders_scheduled": result.reminders_scheduled,
                },
            )
        return CommandResult(
            ok=True,
            message=(
                f"backfilled {result.tokens_minted} manage link(s) and scheduled "
                f"{result.reminders_scheduled} reminder(s) across {result.tenants} tenant(s)"
            ),
        )

    async def run_retention(self, *, operator: str, dry_run: bool) -> CommandResult:
        """F20's operator-invoked retention run, on the audited command layer for
        `backfill_booking_links`' reasons: it touches every tenant's data and a
        one-shot operator action of that size leaves a row.

        `--dry-run` is how the first real run is inspected before the scheduled
        one is trusted — `retention_enabled` ships off (Gate 1 Q2), so the very
        first armed run in production is a deliberate act and this is its
        rehearsal.

        DELIBERATELY NOT GATED ON `retention_enabled`. That flag is the kill
        switch on the UNATTENDED scheduler; an operator typing this command with
        an explicit `--operator` has already made the decision the flag exists to
        defer, and a CLI that silently did nothing because of an env var is how a
        rehearsal gets mistaken for a clean run.

        The platform row is written for BOTH modes. It records that a human
        pointed an irreversible multi-tenant job at production, which is worth
        recording whether or not anything moved — unlike the per-tenant
        `audit_log` rows, which are the tenant's evidence about its own data and
        are therefore written only for work that actually happened.
        """
        result = await RetentionRunner(self._session_factory, settings=get_settings()).run(
            dry_run=dry_run
        )
        touched = sum(result.rows.values())
        async with self._session_factory() as session, session.begin():
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.RETENTION_RUN,
                details={
                    "dry_run": dry_run,
                    "tenants": result.tenants,
                    "failed_tenants": result.failed_tenants,
                    "rows": result.rows,
                },
            )
        verb = "would touch" if dry_run else "touched"
        failures = f", {result.failed_tenants} tenant(s) FAILED" if result.failed_tenants else ""
        return CommandResult(
            ok=True,
            message=(
                f"{verb} {touched} row(s) across {result.tenants} tenant(s){failures}: "
                f"{result.rows or 'nothing due'}"
            ),
        )

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
