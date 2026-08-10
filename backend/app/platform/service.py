import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import hash_password
from app.auth.schemas import MIN_STAFF_PASSWORD_LENGTH
from app.auth.tokens import generate_session_token, hash_token
from app.booking.backfill import ManageLinkBackfill
from app.core.config import get_settings
from app.db.repositories.platform_invites import PlatformInvitesRepository
from app.db.repositories.platform_operators import PlatformOperatorsRepository
from app.db.repositories.platform_sessions import PlatformSessionsRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.constants import PlatformAuditAction, StaffRole, TenantStatus
from app.models.platform_invite import PlatformInvite
from app.models.staff_user import StaffUser
from app.models.tenant import Tenant
from app.platform.repository import PlatformAuditLogRepository
from app.privacy.retention import RetentionRunner
from app.tenancy.slugs import is_valid_slug


class _InviteAlreadyClaimed(Exception):
    """Raised INSIDE the redemption transaction when the conditional claim
    matches zero rows, so the whole transaction rolls back rather than
    continuing past a guard that refused.

    Private and caught two frames away: this is a control-flow signal for one
    `async with`, not an error anybody outside this module handles. The business
    refusal it produces is still RETURNED (F5) — see `redeem_invite`."""


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


def _redeemable(row: PlatformInvite) -> bool:
    """The three predicates `by_code_hash` does not carry, in one place so the
    preview and the redemption cannot disagree about what "usable" means.

    This is NOT the single-use guard — `claim`'s conditional UPDATE is, and it
    re-checks every one of these inside the transaction. This decides only which
    refusal a caller is shaped into and, through it, whose name goes on the
    audit row."""
    return row.deleted_at is None and row.redeemed_at is None and row.expires_at > datetime.now(UTC)


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


@dataclasses.dataclass(frozen=True)
class InviteSummary:
    """What the console's table and the join screen's preview both read.

    NO `code` AND NO `code_hash` FIELD, on either surface. The console renders
    this and the raw code has already left the process by then; the join preview
    renders three of these fields to a caller who authenticated with nothing but
    the code itself."""

    id: UUID
    slug: str
    name: str
    owner_email: str
    created_by: str
    expires_at: datetime
    redeemed_at: datetime | None
    created_at: datetime


@dataclasses.dataclass(frozen=True)
class InviteCreated:
    """⚠ THE ONLY TYPE IN THIS PROCESS THAT EVER CARRIES A RAW INVITE CODE, and
    it is spelled as its own class so `grep -r InviteCreated` is the complete
    list of places one can be. It is built once, returned through one route, and
    never persisted, logged or audited (spec D3, R-C)."""

    ok: bool
    message: str
    code: str | None = None
    invite: InviteSummary | None = None


@dataclasses.dataclass(frozen=True)
class RedeemResult:
    ok: bool
    message: str
    slug: str | None = None
    tenant_id: UUID | None = None


def _invite_summary(row: PlatformInvite) -> InviteSummary:
    return InviteSummary(
        id=row.id,
        slug=row.slug,
        name=row.name,
        owner_email=row.owner_email,
        created_by=row.created_by,
        expires_at=row.expires_at,
        redeemed_at=row.redeemed_at,
        created_at=row.created_at,
    )


class ProvisioningService:
    """Platform-operator orchestration for the tenant lifecycle. Business
    failures are returned (never raised), so failure audits commit rather than
    rolling back with the exception that reports them (the Feature 5 lesson)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._tenants = TenantsRepository(session_factory)
        self._staff = StaffUsersRepository()
        # Staff sessions, for the one command that invalidates a boutique
        # credential from outside the boutique — see `reset_owner_password`.
        self._sessions = SessionsRepository()
        self._audit = PlatformAuditLogRepository()
        # F25's bootstrap pair. ON THIS CLASS rather than in a second service,
        # because pre-decided #20 says there is ONE audited command layer and a
        # fork of it is how the audit posture drifts between two files.
        self._operators = PlatformOperatorsRepository()
        self._operator_sessions = PlatformSessionsRepository()
        # F26's invites, on this class for the same pre-decided #20 reason: the
        # operator issues them and a redemption creates a tenant, so both belong
        # to the ONE audited command layer rather than to a second service that
        # would eventually drift from this one's audit posture.
        self._invites = PlatformInvitesRepository()

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
                await self._create_tenant(
                    session,
                    tenant_id=tenant_id,
                    slug=slug,
                    name=name,
                    owner_email=owner_email,
                    owner_password=owner_password,
                    operator=operator,
                )
        except IntegrityError:
            # Race/suspended-slug backstop behind the partial unique index.
            return await self._fail_provision(operator, slug, "slug_taken")

        return CommandResult(ok=True, message="provisioned", tenant_id=tenant_id)

    async def _create_tenant(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        slug: str,
        name: str,
        owner_email: str,
        owner_password: str,
        operator: str,
    ) -> None:
        """⚠ THE ONE PLACE A BOUTIQUE COMES INTO EXISTENCE (spec D4).

        Extracted from `provision` VERBATIM and called by `provision` and
        `redeem_invite` alike, so an invite redemption writes the UNCHANGED
        `TENANT_PROVISIONED` row rather than a parallel one that drifts. That
        row's presence after a redemption is the mechanical proof the two share
        a path — pre-decided #20's one audited command layer, applied to the one
        operation that has two callers.

        Takes an OPEN session and opens no transaction of its own: the caller
        owns the transaction, because redemption's first statement must be the
        single-use claim and a helper that began its own would put the claim in a
        different transaction from the tenant it authorises.

        `operator` is the accountable identity, NOT the caller: for a redemption
        it is the invite's `created_by`, since the redeemer authenticates as
        nobody.
        """
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

    # --- F26 invites -------------------------------------------------------

    async def create_invite(
        self, *, slug: str, name: str, owner_email: str, operator: str
    ) -> InviteCreated:
        """`provision`'s validation order, minus the password (D2 — the redeemer
        supplies that, which is the whole point of the feature).

        The code is a `token_urlsafe(32)`; only `hash_token(code)` is stored, and
        the raw value is returned exactly once, here. It reaches no logger, no
        audit `details` and no error message (R-C)."""
        if not is_valid_slug(slug):
            return await self._fail_invite(operator, slug, "invalid_or_reserved_slug")
        if await self._tenants.by_slug(slug) is not None:
            # An ergonomic pre-check, exactly like `provision`'s. The real
            # control on the address is the partial unique index, and it fires at
            # REDEMPTION — an invite issued today for a slug someone takes
            # tomorrow refuses then, with the invite left unspent (D4).
            return await self._fail_invite(operator, slug, "slug_taken")

        code = generate_session_token()
        expires_at = datetime.now(UTC) + timedelta(seconds=get_settings().invite_ttl_seconds)
        async with self._session_factory() as session, session.begin():
            row = await self._invites.insert(
                session,
                code_hash=hash_token(code),
                slug=slug,
                name=name,
                owner_email=owner_email,
                created_by=operator,
                expires_at=expires_at,
            )
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.INVITE_CREATED,
                # NO target_tenant_id: the tenant does not exist yet. NO code and
                # no hash in details — this book is append-only by DB grant, so
                # anything written here is written forever.
                details={"slug": slug, "owner_email": owner_email.strip().lower()},
            )
            summary = _invite_summary(row)
        return InviteCreated(ok=True, message="invite_created", code=code, invite=summary)

    async def list_invites(self) -> list[InviteSummary]:
        """No audit row, and the asymmetry with `list_tenants` is deliberate.
        That one is a full cross-tenant enumeration of every boutique trading on
        the platform (F21 D6); this is a list of authorisations the operator
        population issued itself, naming no boutique that exists. Recorded in
        `test_audit_coverage.py` rather than left silent."""
        async with self._session_factory() as session:
            rows = await self._invites.list_visible(session)
        return [_invite_summary(row) for row in rows]

    async def revoke_invite(self, *, invite_id: UUID, operator: str) -> CommandResult:
        """Soft delete. The migration REVOKEs DELETE, so this cannot quietly
        become a hard one, and a revoked invite reads as absent everywhere —
        which is what makes it answer the same `invalid_invite` an unknown code
        gets (D5)."""
        async with self._session_factory() as session, session.begin():
            removed = await self._invites.soft_delete(session, invite_id)
            if removed:
                await self._audit.record(
                    session,
                    operator=operator,
                    action=PlatformAuditAction.INVITE_REVOKED,
                    details={"invite_id": str(invite_id)},
                )
        if not removed:
            # NO audit row, and no `INVITE_REVOKE_FAILED` member to write one
            # with. Nothing happened and nothing could have: the id names an
            # invite that is already revoked or never existed, so there is no act
            # to record. The create/redeem refusals DO write rows because those
            # paths refuse a real request against real state — this one refuses a
            # no-op. Recorded here so the asymmetry is a decision rather than an
            # omission.
            return CommandResult(ok=False, message="invite_not_found")
        return CommandResult(ok=True, message="invite_revoked")

    async def preview_invite(self, *, code: str) -> InviteSummary | None:
        """The anonymous read behind `POST /platform/join/invite` (a POST because
        the code must not travel in a request line — see the router).

        Returns None for unknown, expired, redeemed AND revoked alike — one
        refusal for four states, because a distinct "already redeemed" would tell
        an unauthenticated caller that a code was real (D5, `TENANT_NOT_FOUND`'s
        reading).

        Writes no audit row: a read of one's own invite is not a platform event,
        and `TENANTS_LISTED`'s cross-tenant-enumeration argument does not reach
        a caller who already holds the 256-bit secret for this one row."""
        row = await self._readable_invite(code)
        return None if row is None else _invite_summary(row)

    async def redeem_invite(self, *, code: str, owner_password: str) -> RedeemResult:
        """⚠ ONE TRANSACTION, AND IT IS `provision`'S TRANSACTION (spec D4).

        Order matters and is asserted by tests: read to SHAPE the refusal, check
        the password, generate the tenant id, then open the transaction whose
        FIRST statement is the atomic claim. The read above the transaction can
        be arbitrarily stale — it decides nothing. The claim decides.

        A claim that matches zero rows raises, so the whole transaction rolls
        back and the loser of a race leaves no `Tenant`, no `StaffUser` and no
        `TENANT_PROVISIONED` row.
        """
        code_hash = hash_token(code)
        # ⚠ THE REVOKED ROW IS READ ON PURPOSE. The refusal is identical for all
        # four states, but the AUDIT ROW is not: an expired, redeemed or revoked
        # invite has an accountable issuer sitting right here, and dropping the
        # row on the floor would attribute a replay of a REAL authorisation to
        # "anonymous:join" (spec § Audit contract). Only an unknown code has no
        # issuer. `_redeemable` — not the query — decides who may proceed.
        async with self._session_factory() as session:
            row = await self._invites.by_code_hash(session, code_hash, include_revoked=True)
        if row is None or not _redeemable(row):
            return await self._fail_redeem(code_hash, row, "invalid_invite")
        password_problem = _password_problem(owner_password)
        if password_problem is not None:
            return await self._fail_redeem(code_hash, row, password_problem)

        # BEFORE the transaction, so the claim can name the tenant it authorises.
        # A rollback simply discards the value.
        tenant_id = uuid4()
        try:
            async with tenant_session(self._session_factory, tenant_id) as session:
                # ⚠ FIRST STATEMENT. Writing `platform_invites` inside a
                # `tenant_session` is safe — the table carries no RLS policy, so
                # the session's tenant context does not touch it.
                claimed = await self._invites.claim(
                    session,
                    code_hash=code_hash,
                    tenant_id=tenant_id,
                    now=datetime.now(UTC),
                )
                if claimed is None:
                    raise _InviteAlreadyClaimed
                await self._create_tenant(
                    session,
                    tenant_id=tenant_id,
                    slug=row.slug,
                    name=row.name,
                    owner_email=row.owner_email,
                    owner_password=owner_password,
                    # The invite's issuer, NOT the redeemer — she authenticates
                    # as nobody, and this is the accountable identity.
                    operator=row.created_by,
                )
                await self._audit.record(
                    session,
                    operator=row.created_by,
                    action=PlatformAuditAction.INVITE_REDEEMED,
                    target_tenant_id=tenant_id,
                    details={"slug": row.slug, "owner_email": row.owner_email},
                )
        except _InviteAlreadyClaimed:
            return await self._fail_redeem(code_hash, row, "invalid_invite")
        except IntegrityError:
            # The slug was taken between issue and redemption. The claim rolled
            # back with everything else, so the invite is still unspent and a
            # reissue for a free address can still use it.
            return await self._fail_redeem(code_hash, row, "slug_taken")

        return RedeemResult(ok=True, message="redeemed", slug=row.slug, tenant_id=tenant_id)

    async def _readable_invite(self, code: str) -> PlatformInvite | None:
        """by_code_hash plus the predicates it does not carry. Soft-deleted rows
        are already excluded by the repository's default."""
        async with self._session_factory() as session:
            row = await self._invites.by_code_hash(session, hash_token(code))
        return row if row is not None and _redeemable(row) else None

    async def _fail_invite(self, operator: str, slug: str, reason: str) -> InviteCreated:
        """`_fail_provision` for the invite pair. Outside any transaction the
        refusal aborted, so the row COMMITS (F5): a refusal reported by an
        exception rolls back the row that reports it."""
        details: dict[str, Any] = {"slug": slug, "reason": reason}
        async with self._session_factory() as session, session.begin():
            await self._audit.record(
                session,
                operator=operator,
                action=PlatformAuditAction.INVITE_CREATE_FAILED,
                details=details,
            )
        return InviteCreated(ok=False, message=reason)

    async def _fail_redeem(
        self, code_hash: str, row: PlatformInvite | None, reason: str
    ) -> RedeemResult:
        """⚠ THE HASH PREFIX, NEVER THE CODE. `platform_audit_log` is
        append-only by DB grant and no retention policy prunes it, so a raw code
        written here would be a live boutique-creation credential stored forever
        in the one table the app cannot read back or delete from. Eight hex
        characters are enough to correlate a burst of failures against one
        invite and are useless as a credential.

        `operator` is the invite's issuer whenever the code names a real row —
        expired, already-redeemed and revoked included, since the whole question
        the book has to answer is "which authorisation was being replayed, and
        who issued it". ONLY an unknown code has no issuer at all, and only that
        row is attributed to the anonymous surface it arrived on; a row claiming
        an operator who does not exist would be false.
        """
        details: dict[str, Any] = {"reason": reason, "code_hash_prefix": code_hash[:8]}
        if row is not None:
            details["slug"] = row.slug
        async with self._session_factory() as session, session.begin():
            await self._audit.record(
                session,
                operator=row.created_by if row is not None else "anonymous:join",
                action=PlatformAuditAction.INVITE_REDEEM_FAILED,
                details=details,
            )
        return RedeemResult(ok=False, message=reason)

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
        # ⚠ `by_slug_any_status`, NOT `by_slug`. Suspension must not make this
        # command unreachable: suspend-then-reset is the natural order of an
        # account takeover response, and the console renders «איפוס סיסמת בעלים»
        # as the ONLY action left on a suspended row (design §Screen 2). With
        # active-only resolution the reset 404s exactly when an operator needs
        # it. Soft-deleted tenants still resolve to nothing.
        tenant = await self._tenants.by_slug_any_status(slug)
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
            staff_user_id = result.scalar_one_or_none()
            if staff_user_id is None:
                return CommandResult(ok=False, message="owner_not_found")
            # A new hash does not end the takeover it is meant to end:
            # `resolve_session` never reads `password_hash`, so a cookie minted
            # under the OLD password stays good for the rest of
            # `session_ttl_seconds`. `auth/staff.py` pays for the same claim on
            # the tenant-side password change; this is the same operation at
            # higher stakes. Same transaction, so the hash and the revocation
            # commit together. No `except_token_hash`: the operator holds no
            # session of the owner's, so every one of them goes.
            await self._sessions.revoke_for_staff_user(session, tenant.id, staff_user_id)
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
