import dataclasses
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_password
from app.auth.schemas import MIN_STAFF_PASSWORD_LENGTH
from app.booking.backfill import ManageLinkBackfill
from app.core.config import get_settings
from app.db.repositories.platform_operators import PlatformOperatorsRepository
from app.db.repositories.platform_sessions import PlatformSessionsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.constants import PlatformAuditAction, StaffRole, TenantStatus
from app.models.staff_user import StaffUser
from app.models.tenant import Tenant
from app.platform.repository import PlatformAuditLogRepository
from app.privacy.retention import RetentionRunner
from app.tenancy.slugs import is_valid_slug


def _password_problem(password: str) -> str | None:
    """⚠ THE SAME FLOOR `/manage/staff` ENFORCES, on the three passwords that were
    exempt from it.

    `MIN_STAFF_PASSWORD_LENGTH` argues (auth/schemas.py) that length is the only
    control surviving a password one person chooses and speaks to another — which
    is exactly the trip every password below makes: an operator types it, then
    hands it to a boutique owner or keeps it as the credential that controls every
    tenant on the platform. `a` passed all three until this check, while the
    boutique's own staff screen refused it.

    It matters more than usual here because spec D6 declines TOTP on the strength
    of the operator credential being "argon2-hashed, un-enumerable, rate-limited"
    — a floor is the leg of that argument the code did not implement.

    HERE and not in `schemas.py`: the service owns the failure audit rows
    (router.py's opening note), so a schema-level refusal would answer with a
    422→400 the console has no sentence for AND skip the `*_FAILED` row the CLI
    writes for the same refusal. This also covers `create-operator`, which no
    schema sees at all.

    Length is measured on the RAW value, matching `CreateStaffRequest`'s
    `min_length`; blank keeps its own code so the console's existing sentence and
    the CLI's own tests are unchanged.
    """
    if not password.strip():
        return "empty_password"
    if len(password) < MIN_STAFF_PASSWORD_LENGTH:
        return "password_too_short"
    return None


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
        # F25's bootstrap pair. ON THIS CLASS rather than in a second service,
        # because pre-decided #20 says there is ONE audited command layer and a
        # fork of it is how the audit posture drifts between two files.
        self._operators = PlatformOperatorsRepository()
        self._operator_sessions = PlatformSessionsRepository()

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
        password_problem = _password_problem(owner_password)
        if password_problem is not None:
            # A blank password (e.g. `echo -n | … provision`) would create a
            # loginable owner with a hashed empty string; a one-character one is
            # loginable in five guesses. Both refused, with their own codes.
            return await self._fail_provision(operator, slug, password_problem)
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
            # ⚠ NOT an unconditional True. `RetentionRunner` contains a failing
            # tenant so one boutique cannot stop another's clocks — which means
            # the ONLY signal that a tenant failed is this exit code, and an
            # `ok=True` that mentioned failures in prose alone reported a clean
            # run to cron, to `$?` and to every wrapper. `retention.py`'s own
            # docstring names that exact failure ("a silently degraded retention
            # job still reports 'ran fine' to the only operator who would ever
            # look") and the CLI layer was doing it.
            ok=result.failed_tenants == 0,
            message=(
                f"{verb} {touched} row(s) across {result.tenants} tenant(s){failures}: "
                f"{result.rows or 'nothing due'}"
            ),
        )

    async def list_tenants(self, *, operator: str) -> list[TenantSummary]:
        """⚠ THE ONLY READ IN THIS FILE THAT WRITES A ROW, and F21's D6 says why:
        it is a FULL CROSS-TENANT read — every boutique's slug, trading name and
        status in one output — and before F21 it was the one privileged operation
        in the CLI that left no trail at all. `--operator` was already parsed
        (`cli.py:68-69`) and then discarded, which is the shape of a decision
        nobody made.

        Checklist row 38 reads "data ACCESS by operators", not "data changes",
        and D19 already settled that reading once for `PRIVACY_SUBJECT_EXPORTED`:
        assembling a whole record into one view IS the access it means. The
        standing rule that no GET handler writes a row (`dashboard/service.py`
        :373) is untouched — that rule is about a tenant's staff reading their own
        boutique through HTTP, and this is a platform operator reading across all
        of them from a shell.

        Bare `self._session_factory()`, not `tenant_session`: the row is
        platform-scoped and belongs to no tenant, so `target_tenant_id` stays
        NULL. `session.begin()` is explicit for `_fail_provision`'s reason — the
        read alone needed no transaction, and the write does.
        """
        async with self._session_factory() as session, session.begin():
            stmt = select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.created_at)
            rows = (await session.execute(stmt)).scalars().all()
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.TENANTS_LISTED,
                details={"tenants": len(rows)},
            )
        return [
            TenantSummary(slug=t.slug, name=t.name, status=t.status, created_at=t.created_at)
            for t in rows
        ]

    async def reset_owner_password(
        self, *, slug: str, owner_email: str, new_password: str, operator: str
    ) -> CommandResult:
        password_problem = _password_problem(new_password)
        if password_problem is not None:
            return CommandResult(ok=False, message=password_problem)
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

    async def create_operator(
        self, *, email: str, display_name: str, password: str, operator: str
    ) -> CommandResult:
        """The ONLY way a platform operator comes into existence (spec D2).

        No HTTP route calls this and none ever should: the console's own
        compromise must not be able to mint a second operator, which is why the
        credential that controls every boutique is seeded from a shell and
        nowhere else.
        """
        normalized = email.strip().lower()
        password_problem = _password_problem(password)
        if password_problem is not None:
            # The `provision` argument one table over, at higher stakes: this
            # credential controls every tenant on the platform, and 5 guesses per
            # 15 min is ample for a one-character secret.
            return await self._fail_operator(operator, normalized, password_problem, created=True)
        if not display_name.strip():
            return await self._fail_operator(
                operator, normalized, "empty_display_name", created=True
            )

        async with self._session_factory() as session:
            existing = await self._operators.by_active_email(session, normalized)
        if existing is not None:
            return await self._fail_operator(
                operator, normalized, "operator_email_taken", created=True
            )

        try:
            async with self._session_factory() as session, session.begin():
                await self._operators.insert(
                    session,
                    email=normalized,
                    password_hash=hash_password(password),
                    display_name=display_name.strip(),
                )
                await self._audit.record(
                    session,
                    operator=operator,
                    action=PlatformAuditAction.OPERATOR_CREATED,
                    details={"email": normalized},
                )
        except IntegrityError:
            # The partial unique index is the real control; the read above is
            # the ergonomic one. `provision`'s shape exactly.
            return await self._fail_operator(
                operator, normalized, "operator_email_taken", created=True
            )
        return CommandResult(ok=True, message="operator_created")

    async def deactivate_operator(self, *, email: str, operator: str) -> CommandResult:
        """Soft delete + revoke every live session, in ONE transaction.

        Both halves matter and neither is enough alone: the soft delete is what
        `get_current_operator`'s re-read notices on the next request, and the
        revoke is what closes the window between now and that request on a
        console tab already open.

        REFUSES THE LAST ACTIVE OPERATOR. There is no HTTP route that creates
        one, so an empty `platform_operators` is a platform whose console can
        only be reopened from a shell — recoverable, but not by anyone looking
        at the login screen.
        """
        normalized = email.strip().lower()
        # Compute the outcome INSIDE the transaction, raise nothing, and write
        # the failure audit outside it — the F5 lesson: a refusal reported by an
        # exception rolls back the row that reports it.
        async with self._session_factory() as session, session.begin():
            found = await self._operators.by_active_email(session, normalized)
            if found is None:
                reason: str | None = "operator_not_found"
            elif await self._operators.count_active(session) <= 1:
                reason = "last_operator"
            else:
                await self._operators.soft_delete(session, found.id)
                await self._operator_sessions.revoke_all_for_operator(session, found.id)
                await self._audit.record(
                    session,
                    operator=operator,
                    action=PlatformAuditAction.OPERATOR_DEACTIVATED,
                    details={"email": normalized},
                )
                reason = None

        if reason is not None:
            return await self._fail_operator(operator, normalized, reason, created=False)
        return CommandResult(ok=True, message="operator_deactivated")

    async def _fail_operator(
        self, operator: str, email: str, reason: str, *, created: bool
    ) -> CommandResult:
        """`_fail_provision` for the operator pair, and it writes its OWN action
        rather than reusing the success one. `TENANT_PROVISION_FAILED` exists for
        this reason: a row reading `operator_created` when no operator was created
        is not a weaker record, it is a false one — and this book is the only
        evidence anybody has about who touched the platform's credentials.

        `details` carries the address and the reason. NEVER the password or its
        hash — the whole point of reading the password from stdin is that it does
        not get written down.
        """
        details: dict[str, Any] = {"email": email, "reason": reason}
        action = (
            PlatformAuditAction.OPERATOR_CREATE_FAILED
            if created
            else PlatformAuditAction.OPERATOR_DEACTIVATE_FAILED
        )
        async with self._session_factory() as session, session.begin():
            await self._audit.record(session, operator=operator, action=action, details=details)
        return CommandResult(ok=False, message=reason)

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
