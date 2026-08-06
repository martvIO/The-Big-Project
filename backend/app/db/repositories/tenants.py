from typing import Any
from uuid import UUID

from sqlalchemy import Text, cast, func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.constants import TenantStatus
from app.models.tenant import Tenant


class TenantsRepository:
    """Platform-scoped repository — the tenants table has no tenant_id and no RLS.
    updated_at is maintained by the DB trigger, never set here.

    Requires a session factory built with expire_on_commit=False (as
    get_session_factory() provides): methods return ORM entities after their
    transaction commits, which would otherwise raise DetachedInstanceError."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def insert(self, slug: str, name: str) -> Tenant:
        async with self._session_factory() as session, session.begin():
            tenant = Tenant(slug=slug, name=name)
            session.add(tenant)
            await session.flush()
            await session.refresh(tenant)
            return tenant

    async def by_id(self, tenant_id: UUID) -> Tenant | None:
        async with self._session_factory() as session:
            stmt = select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
            return (await session.execute(stmt)).scalar_one_or_none()

    async def by_slug(self, slug: str) -> Tenant | None:
        """Active tenants only — suspension and soft-deletion both make a slug
        unresolvable (Feature 4 serves 404 for those)."""
        async with self._session_factory() as session:
            stmt = select(Tenant).where(
                Tenant.slug == slug,
                Tenant.deleted_at.is_(None),
                Tenant.status == TenantStatus.ACTIVE,
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def suspend(self, tenant_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            stmt = (
                update(Tenant)
                .where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
                .values(status=TenantStatus.SUSPENDED)
                .returning(Tenant.id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def soft_delete(self, tenant_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            stmt = (
                update(Tenant)
                .where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
                .values(deleted_at=func.now())
                .returning(Tenant.id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def merge_settings(
        self,
        tenant_id: UUID,
        *,
        profile: dict[str, Any] | None = None,
        toggles: dict[str, Any] | None = None,
        atelier: dict[str, Any] | None = None,
        privacy: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """ONE atomic `settings = settings || :patch::jsonb` — never a Python
        read-modify-write — so a concurrent writer of a sibling top-level key
        (F42's `atelier` is the first) can never be clobbered. Only the provided
        keys enter the patch. Returns the merged settings, or None when the
        tenant is missing or soft-deleted.

        ⚠ `||` IS A SHALLOW MERGE AND THAT IS WHY `atelier` ARRIVES WHOLE. The
        top level is safe by this statement — `profile` and `atelier` are
        different keys and `||` merges them — but a patch carrying a PARTIAL
        `atelier` object replaces the entire key and deletes what it did not
        name. The fix is not a deeper SQL expression: it is ONE WRITER THAT
        ALWAYS SENDS THE WHOLE BLOCK, which `AtelierSettingsUpdate` makes
        structural by requiring every field.

        ⚠ AND `jsonb_set` IS THE WRONG REACH, named so nobody takes it.
        `jsonb_set(settings, '{atelier,effort_bands}', :v, true)` looks like the
        deep-merge answer and silently returns `settings` UNCHANGED when the
        `atelier` key is absent — `create_missing` creates the leaf, not the
        intermediate object. That is every tenant on day one, and it fails with
        no error.

        ⚠ THE DAY ARRIVED, FOR `toggles` AND FOR `toggles` ONLY (F27 D2). The
        expression this docstring prescribed above is now built below, with the
        mandatory `coalesce`. What forced it: the toggle matrix saves PER ROW —
        one key per PUT — so "one writer always sends the whole block" stopped
        being true by construction, and it had a silent failure mode the moment
        the registry grew anyway (a browser on a STALE CACHED BUNDLE saves the
        keys it knows and wipes a newer feature's toggle back to absent).

        Still ONE atomic statement and still no Python read-modify-write: the
        `settings` on the right-hand side of a SET is the row's OLD value, so
        `coalesce(settings->'toggles','{}'::jsonb) || :toggles` merges against
        what is really in the column at UPDATE time. Concurrent single-key
        writers of two different toggles both survive.

        `profile`/`atelier`/`privacy` KEEP whole-block-replace, deliberately:
        their "one writer sends the whole block" models make an omitted field a
        CLEAR, and deepening them would silently turn every clear into a no-op.
        """
        patch: dict[str, Any] = {}
        if profile is not None:
            patch["profile"] = profile
        if atelier is not None:
            patch["atelier"] = atelier
        # F20's fourth key, and it obeys the ⚠ above rather than escaping it:
        # `PrivacyUpdate` requires BOTH of its fields, exactly as
        # `AtelierSettingsUpdate` requires all of its, so the one writer always
        # sends the whole block. That is what makes the shallow `||` safe here.
        if privacy is not None:
            patch["privacy"] = privacy
        merged_settings = Tenant.settings.op("||", return_type=JSONB)(cast(patch, JSONB))
        if toggles is not None:
            # Appended LAST so it wins the `||` chain for the `toggles` key.
            # ⚠ BOTH `'toggles'` OPERANDS ARE `cast(..., Text)` AND NEITHER IS
            # DECORATION. `jsonb_build_object` is `variadic "any"`, which gives
            # Postgres nothing to resolve an untyped parameter against — a bare
            # bind there fails outright with «could not determine data type of
            # parameter $1». The `->` operand is cast for the neighbouring
            # reason: `jsonb -> $1` has `-> text` and `-> integer` candidates in
            # different type categories. The key is a compile-time constant, so
            # the cast costs nothing and removes both inference questions.
            key = cast("toggles", Text)
            merged_settings = merged_settings.op("||", return_type=JSONB)(
                func.jsonb_build_object(
                    key,
                    func.coalesce(
                        Tenant.settings.op("->", return_type=JSONB)(key),
                        cast({}, JSONB),
                    ).op("||", return_type=JSONB)(cast(toggles, JSONB)),
                )
            )
        async with self._session_factory() as session, session.begin():
            stmt = (
                update(Tenant)
                .where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
                .values(settings=merged_settings)
                .returning(Tenant.settings)
            )
            result = await session.execute(stmt)
            merged: dict[str, Any] | None = result.scalar_one_or_none()
            return merged

    async def list_active(self) -> list[Tenant]:
        async with self._session_factory() as session:
            stmt = (
                select(Tenant)
                .where(Tenant.deleted_at.is_(None), Tenant.status == TenantStatus.ACTIVE)
                .order_by(Tenant.created_at)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def list_all(self) -> list[Tenant]:
        """EVERY tenant row — no status filter and no deleted_at filter. The
        retention runner's enumeration, and nothing else's (F20 D21).

        The missing filters are the point, not an oversight. `suspend()` and
        `soft_delete()` are shipped operator commands, so `list_active()` would
        freeze a suspended or off-boarded boutique's data with no clock ever
        applied — forever. The retention duty does not lapse when the
        controller's account does, and "a boutique may not choose its own
        retention" has to bind through suspension too.

        `list_active()` stays the SMS poller's: skipping a suspended tenant
        there is correct, because a suspended boutique should not be texting.
        """
        async with self._session_factory() as session:
            stmt = select(Tenant).order_by(Tenant.created_at)
            return list((await session.execute(stmt)).scalars().all())
