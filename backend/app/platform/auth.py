"""Operator authentication — the platform's highest-privilege surface.

The staff pattern (`app/auth/`), substituted for one global scope: argon2 with a
dummy verify on the unknown-address path, a sha256-stored session token, a
host-only HttpOnly SameSite=Lax cookie under its own name, and both outcomes
audited. What is NOT shared is the lookup path: `platform_operators` /
`platform_sessions` are separate tables reached by separate repositories, because
two auth populations resolving through one query is a single missing predicate
away from a staff cookie answering as an operator (spec D3).
"""

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.cookies import PLATFORM_SESSION_COOKIE
from app.auth.dependencies import NotAuthenticatedError
from app.auth.passwords import verify_password, verify_password_dummy
from app.auth.service import InvalidCredentialsError
from app.auth.tokens import generate_session_token, hash_token
from app.core.config import Settings
from app.db.repositories.platform_operators import PlatformOperatorsRepository
from app.db.repositories.platform_sessions import PlatformSessionsRepository
from app.models.constants import PlatformAuditAction
from app.platform.repository import PlatformAuditLogRepository


@dataclasses.dataclass(frozen=True)
class OperatorContext:
    id: UUID
    email: str
    display_name: str


class OperatorAuthService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], settings: Settings
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._operators = PlatformOperatorsRepository()
        self._sessions = PlatformSessionsRepository()
        # The PLATFORM's book, not a tenant's `audit_log`: the console's front
        # door belongs to no boutique. Stricter than the staff login by design
        # (spec D4). Everything goes through `record`, whose client-side id and
        # created_at are what keep the INSERT-only grant satisfiable — a
        # `session.add(PlatformAuditLog(...))` with server defaults would emit
        # RETURNING, which needs the SELECT this role does not have.
        self._audit = PlatformAuditLogRepository()

    async def login(self, email: str, password: str) -> tuple[OperatorContext, str]:
        normalized = email.strip().lower()
        # The whole login — INCLUDING the failure audit — must COMMIT. Raising
        # inside `session.begin()` rolls the transaction back and would silently
        # discard the row that reports the failure. So: compute the outcome, let
        # the transaction close, then raise outside it (the F5 lesson).
        async with self._session_factory() as session, session.begin():
            operator = await self._operators.by_active_email(session, normalized)
            if operator is None:
                # Unknown address still pays for an argon2 verify — no timing
                # channel distinguishing "no such operator" from "wrong password",
                # and the response body is identical either way.
                verify_password_dummy(password)
                outcome: tuple[OperatorContext, str] | None = None
            elif not verify_password(password, operator.password_hash):
                outcome = None
            else:
                token = generate_session_token()
                await self._sessions.insert(
                    session,
                    operator_id=operator.id,
                    token_hash=hash_token(token),
                    expires_at=datetime.now(UTC)
                    + timedelta(seconds=self._settings.platform_session_ttl_seconds),
                )
                outcome = (_context(operator.id, operator.email, operator.display_name), token)

            await self._audit.record(
                session,
                # The attempted address on BOTH paths, and it is the only identity
                # available on the failure one. `details` never carries the
                # password — reading it from stdin at bootstrap would be pointless
                # if the login path wrote it down.
                operator=normalized,
                action=(
                    PlatformAuditAction.OPERATOR_LOGIN
                    if outcome is not None
                    else PlatformAuditAction.OPERATOR_LOGIN_FAILED
                ),
                details={"email": normalized},
            )

        if outcome is None:
            raise InvalidCredentialsError
        return outcome

    async def resolve_session(self, token: str) -> OperatorContext | None:
        async with self._session_factory() as session:
            row = await self._sessions.live_by_token_hash(
                session, hash_token(token), datetime.now(UTC)
            )
            if row is None:
                return None
            # ⚠ THE OPERATOR ROW IS RE-READ ON EVERY REQUEST, and that is the
            # whole deactivation mechanism: `by_id` filters `deleted_at IS NULL`,
            # so a deactivated operator's still-live session is refused on the
            # very next call with no session state to sweep. `RoleGate`'s
            # property, at higher stakes.
            operator = await self._operators.by_id(session, row.operator_id)
            if operator is None:
                return None
            return _context(operator.id, operator.email, operator.display_name)

    async def logout(self, token: str) -> None:
        async with self._session_factory() as session, session.begin():
            await self._sessions.revoke(session, hash_token(token))


def _context(operator_id: UUID, email: str, display_name: str) -> OperatorContext:
    return OperatorContext(id=operator_id, email=email, display_name=display_name)


def get_operator_auth_service(request: Request) -> OperatorAuthService:
    service: OperatorAuthService = request.app.state.platform_auth_service
    return service


async def get_current_operator(request: Request) -> OperatorContext:
    """Every console handler depends on this, and it refuses for four separate
    reasons that all produce ONE body:

    1. the request was not marked `platform_host` — the BELT beside the tenancy
       middleware's braces, so a route registered outside `/platform`, or a
       middleware ordering mistake, still cannot hand an operator context to a
       tenant host;
    2. no cookie;
    3. no live session row (missing, expired, revoked — indistinguishable);
    4. the operator behind that session is deactivated.

    `NotAuthenticatedError` is the shipped house 401, reused rather than
    reinvented: one body for all four is what keeps the refusal from telling a
    prober which of them it hit.
    """
    if not getattr(request.state, "platform_host", False):
        raise NotAuthenticatedError
    token = request.cookies.get(PLATFORM_SESSION_COOKIE)
    if not token:
        raise NotAuthenticatedError
    operator = await get_operator_auth_service(request).resolve_session(token)
    if operator is None:
        raise NotAuthenticatedError
    return operator
