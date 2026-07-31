from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import GatewayCredentialStatus
from app.models.tenant_gateway_credential import TenantGatewayCredential


class GatewayCredentialsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository).

    Two lookups, deliberately, and the difference is a money-loss bug if it is
    collapsed back into one (D20):

    - `active_for_provider` is the USE path — authorisation to move NEW money.
      Partial on `deleted_at IS NULL`, so a disconnect makes it disappear.
    - `newest_for_provider` is the VERIFICATION path — reading evidence about
      money that has ALREADY moved. It ignores `deleted_at` AND `status`,
      because a disconnect (or an `invalid` flip) must not strand an in-flight
      payment whose charge already succeeded at the provider.
    """

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        provider: str,
        ciphertext: str,
        key_ref: str,
        last_validated_at: datetime,
        created_by: UUID,
    ) -> TenantGatewayCredential:
        """Flush surfaces IntegrityError when
        idx_tenant_gateway_credentials_active_unique refuses a second ACTIVE row
        for this (tenant, provider). Deliberately not pre-checked: the index is
        the truth and a pre-check would be a TOCTOU."""
        row = TenantGatewayCredential(
            tenant_id=tenant_id,
            provider=provider,
            ciphertext=ciphertext,
            key_ref=key_ref,
            status=GatewayCredentialStatus.VALID.value,
            last_validated_at=last_validated_at,
            created_by=created_by,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def active_for_provider(
        self, session: AsyncSession, tenant_id: UUID, *, provider: str
    ) -> TenantGatewayCredential | None:
        stmt = select(TenantGatewayCredential).where(
            TenantGatewayCredential.tenant_id == tenant_id,
            TenantGatewayCredential.provider == provider,
            TenantGatewayCredential.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def newest_for_provider(
        self, session: AsyncSession, tenant_id: UUID, *, provider: str
    ) -> TenantGatewayCredential | None:
        """D20. Ignores `deleted_at` and `status` on purpose — see the class
        docstring. Backed by idx_tenant_gateway_credentials_newest, which is
        non-partial for exactly this reason."""
        stmt = (
            select(TenantGatewayCredential)
            .where(
                TenantGatewayCredential.tenant_id == tenant_id,
                TenantGatewayCredential.provider == provider,
            )
            .order_by(TenantGatewayCredential.created_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def mark_status(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        credential_id: UUID,
        *,
        status: str,
        last_validated_at: datetime,
        validation_error: str | None,
    ) -> TenantGatewayCredential | None:
        stmt = (
            update(TenantGatewayCredential)
            .where(
                TenantGatewayCredential.tenant_id == tenant_id,
                TenantGatewayCredential.id == credential_id,
                TenantGatewayCredential.deleted_at.is_(None),
            )
            .values(
                status=status,
                last_validated_at=last_validated_at,
                validation_error=validation_error,
            )
            .returning(TenantGatewayCredential.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.active_for_provider_by_id(session, tenant_id, credential_id)

    async def soft_delete_active(
        self, session: AsyncSession, tenant_id: UUID, *, provider: str, now: datetime
    ) -> int:
        """Supersede whatever is active. Returns the row count so a caller can
        tell "there was one" from "there was none" without a second read — which
        is what lets `disconnect` answer 404 rather than a silent 200.

        The ciphertext SURVIVES here: this is a soft delete, and D20's
        verification path still has to read it so an in-flight charge can settle.
        F20 blanks it at 90 days (D21)."""
        stmt = (
            update(TenantGatewayCredential)
            .where(
                TenantGatewayCredential.tenant_id == tenant_id,
                TenantGatewayCredential.provider == provider,
                TenantGatewayCredential.deleted_at.is_(None),
            )
            .values(deleted_at=now)
            .returning(TenantGatewayCredential.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def active_for_provider_by_id(
        self, session: AsyncSession, tenant_id: UUID, credential_id: UUID
    ) -> TenantGatewayCredential | None:
        stmt = select(TenantGatewayCredential).where(
            TenantGatewayCredential.tenant_id == tenant_id,
            TenantGatewayCredential.id == credential_id,
            TenantGatewayCredential.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()
