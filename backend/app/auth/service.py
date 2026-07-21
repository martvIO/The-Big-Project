import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.passwords import verify_password, verify_password_dummy
from app.auth.tokens import generate_session_token, hash_token
from app.core.config import Settings
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import AuditAction
from app.models.staff_user import StaffUser


@dataclasses.dataclass(frozen=True)
class StaffContext:
    id: UUID
    tenant_id: UUID
    email: str
    display_name: str
    role: str


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._staff = StaffUsersRepository()
        self._sessions = SessionsRepository()
        self._audit = AuditLogRepository()

    async def login(self, tenant_id: UUID, email: str, password: str) -> tuple[StaffContext, str]:
        async with tenant_session(self._session_factory, tenant_id) as session:
            staff = await self._staff.by_email(session, email)
            # Unknown email still does argon2 work (dummy verify) — no timing leak.
            if staff is None:
                verify_password_dummy(password)
                await self._audit.record(
                    session, tenant_id=tenant_id, action=AuditAction.LOGIN_FAILED, entity=email
                )
                raise InvalidCredentialsError
            if not verify_password(password, staff.password_hash):
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.LOGIN_FAILED,
                    actor_id=staff.id,
                    entity=email,
                )
                raise InvalidCredentialsError

            token = generate_session_token()
            expires_at = datetime.now(UTC) + timedelta(seconds=self._settings.session_ttl_seconds)
            await self._sessions.insert(
                session,
                tenant_id=tenant_id,
                staff_user_id=staff.id,
                token_hash=hash_token(token),
                expires_at=expires_at,
            )
            await self._audit.record(
                session, tenant_id=tenant_id, action=AuditAction.LOGIN, actor_id=staff.id
            )
            return _to_context(staff), token

    async def resolve_session(self, tenant_id: UUID, token: str) -> StaffContext | None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._sessions.active_by_token_hash(
                session, hash_token(token), datetime.now(UTC)
            )
            if row is None:
                return None
            staff = await self._staff.by_id(session, row.staff_user_id)
            return _to_context(staff) if staff else None

    async def logout(self, tenant_id: UUID, token: str) -> None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            revoked = await self._sessions.revoke_by_token_hash(session, hash_token(token))
            if revoked:
                await self._audit.record(session, tenant_id=tenant_id, action=AuditAction.LOGOUT)


def _to_context(staff: StaffUser) -> StaffContext:
    return StaffContext(
        id=staff.id,
        tenant_id=staff.tenant_id,
        email=staff.email,
        display_name=staff.display_name,
        role=staff.role,
    )
