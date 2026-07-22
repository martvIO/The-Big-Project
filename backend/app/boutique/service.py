import dataclasses
import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.boutique.validation import (
    WeeklyRuleInput,
    validate_appointment_type,
    validate_exception_note,
    validate_exception_times,
    validate_profile,
    validate_terms,
    validate_toggles,
    validate_weekly_rules,
)
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.tenants import TenantsRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.constants import AppointmentAudience
from app.models.terms_version import TermsVersion

TERMS_HISTORY_DEFAULT_LIMIT = 50


class NotFoundError(Exception):
    """Target row doesn't exist for this tenant — including another tenant's id
    (RLS + the explicit predicate make foreign rows indistinguishable from
    missing ones, by design)."""


class DuplicateNameError(Exception):
    """Active appointment-type name already taken (partial unique index)."""


class DuplicateDateError(Exception):
    """Active availability exception already exists for that date."""


class TermsVersionConflictError(Exception):
    """Both the optimistic insert and its fresh-session retry lost the
    version race — the caller should retry the whole request."""


class TermsThrottledError(Exception):
    """Per-tenant terms-creation throttle tripped (append-only spam guard)."""


@dataclasses.dataclass(frozen=True)
class SettingsResult:
    profile: dict[str, Any]
    toggles: dict[str, Any]


@dataclasses.dataclass(frozen=True)
class AvailabilityResult:
    rules: list[AvailabilityRule]
    exceptions: list[AvailabilityException]


@dataclasses.dataclass(frozen=True)
class TermsHistoryResult:
    current: TermsVersion | None
    versions: list[TermsVersion]
    total: int
    offset: int
    limit: int


def _settings_result(settings: dict[str, Any]) -> SettingsResult:
    return SettingsResult(
        profile=dict(settings.get("profile") or {}),
        toggles=dict(settings.get("toggles") or {}),
    )


class BoutiqueSettingsService:
    """Owner-settings business logic. Tenant-table access always goes through
    tenant_session (FORCE RLS would return zero rows without the context);
    tenants.settings goes through the platform-scoped TenantsRepository."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        terms_rate_limiter: FixedWindowRateLimiter,
    ) -> None:
        self._session_factory = session_factory
        self._tenants = TenantsRepository(session_factory)
        self._appointment_types = AppointmentTypesRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()
        self._terms = TermsVersionsRepository()
        self._terms_limiter = terms_rate_limiter

    # --- profile + toggles (tenants.settings JSONB) ---

    async def get_settings(self, tenant_id: UUID) -> SettingsResult:
        tenant = await self._tenants.by_id(tenant_id)
        if tenant is None:
            raise NotFoundError
        return _settings_result(tenant.settings)

    async def update_settings(
        self,
        tenant_id: UUID,
        *,
        profile: dict[str, Any] | None = None,
        toggles: dict[str, Any] | None = None,
    ) -> SettingsResult:
        if profile is not None:
            validate_profile(profile)
        if toggles is not None:
            validate_toggles(toggles)
        merged = await self._tenants.merge_settings(tenant_id, profile=profile, toggles=toggles)
        if merged is None:
            raise NotFoundError
        return _settings_result(merged)

    # --- appointment types ---

    async def list_appointment_types(self, tenant_id: UUID) -> list[AppointmentType]:
        async with tenant_session(self._session_factory, tenant_id) as session:
            return await self._appointment_types.list_active(session, tenant_id)

    async def create_appointment_type(
        self,
        tenant_id: UUID,
        *,
        name: str,
        duration_minutes: int,
        audience: str = AppointmentAudience.ALL,
        deposit_required: bool = False,
        deposit_amount_agorot: int | None = None,
        sort_order: int = 0,
    ) -> AppointmentType:
        validate_appointment_type(
            name=name,
            duration_minutes=duration_minutes,
            audience=audience,
            deposit_required=deposit_required,
            deposit_amount_agorot=deposit_amount_agorot,
        )
        try:
            async with tenant_session(self._session_factory, tenant_id) as session:
                return await self._appointment_types.insert(
                    session,
                    tenant_id=tenant_id,
                    name=name,
                    duration_minutes=duration_minutes,
                    audience=audience,
                    deposit_required=deposit_required,
                    deposit_amount_agorot=deposit_amount_agorot,
                    sort_order=sort_order,
                )
        except IntegrityError:
            # Validation already covered the CHECK bounds, so an IntegrityError
            # here is the (tenant_id, name) partial unique index.
            raise DuplicateNameError from None

    async def update_appointment_type(
        self,
        tenant_id: UUID,
        type_id: UUID,
        *,
        name: str,
        duration_minutes: int,
        audience: str,
        deposit_required: bool,
        deposit_amount_agorot: int | None,
        sort_order: int,
    ) -> AppointmentType:
        validate_appointment_type(
            name=name,
            duration_minutes=duration_minutes,
            audience=audience,
            deposit_required=deposit_required,
            deposit_amount_agorot=deposit_amount_agorot,
        )
        try:
            async with tenant_session(self._session_factory, tenant_id) as session:
                updated = await self._appointment_types.update_fields(
                    session,
                    tenant_id,
                    type_id,
                    name=name,
                    duration_minutes=duration_minutes,
                    audience=audience,
                    deposit_required=deposit_required,
                    deposit_amount_agorot=deposit_amount_agorot,
                    sort_order=sort_order,
                )
        except IntegrityError:
            raise DuplicateNameError from None
        if updated is None:
            raise NotFoundError
        return updated

    async def archive_appointment_type(self, tenant_id: UUID, type_id: UUID) -> None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            archived = await self._appointment_types.soft_delete(session, tenant_id, type_id)
        if not archived:
            raise NotFoundError

    # --- availability: weekly rules + exception dates ---

    async def get_availability(self, tenant_id: UUID) -> AvailabilityResult:
        async with tenant_session(self._session_factory, tenant_id) as session:
            rules = await self._rules.list_active(session, tenant_id)
            exceptions = await self._exceptions.list_active(session, tenant_id)
        return AvailabilityResult(rules=rules, exceptions=exceptions)

    async def replace_weekly_rules(
        self, tenant_id: UUID, rules: list[WeeklyRuleInput]
    ) -> list[AvailabilityRule]:
        # Validate FIRST — a rejected replacement must leave state untouched.
        validate_weekly_rules(rules)
        async with tenant_session(self._session_factory, tenant_id) as session:
            # Per-tenant serialization: without it, two concurrent replaces
            # under READ COMMITTED would both pass validation and UNION their
            # sets. hashtext() keys the xact-scoped lock on the tenant id; it
            # releases with the transaction.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                {"tenant_id": str(tenant_id)},
            )
            await self._rules.soft_delete_all(session, tenant_id)
            return [
                await self._rules.insert(
                    session,
                    tenant_id=tenant_id,
                    day_of_week=rule.day_of_week,
                    open_time=rule.open_time,
                    close_time=rule.close_time,
                    capacity=rule.capacity,
                )
                for rule in rules
            ]

    async def add_availability_exception(
        self,
        tenant_id: UUID,
        *,
        date: datetime.date,
        open_time: datetime.time | None,
        close_time: datetime.time | None,
        note: str | None = None,
    ) -> AvailabilityException:
        validate_exception_times(open_time, close_time)
        validate_exception_note(note)
        try:
            async with tenant_session(self._session_factory, tenant_id) as session:
                return await self._exceptions.insert(
                    session,
                    tenant_id=tenant_id,
                    date=date,
                    open_time=open_time,
                    close_time=close_time,
                    note=note,
                )
        except IntegrityError:
            raise DuplicateDateError from None

    async def remove_availability_exception(self, tenant_id: UUID, exception_id: UUID) -> None:
        async with tenant_session(self._session_factory, tenant_id) as session:
            removed = await self._exceptions.soft_delete(session, tenant_id, exception_id)
        if not removed:
            raise NotFoundError

    # --- cancellation-policy terms (append-only versions) ---

    async def create_terms_version(
        self,
        tenant_id: UUID,
        *,
        terms_text: str,
        refundable_until_hours_before: int,
        forfeit_percent: int = 100,
        created_by: UUID,
    ) -> TermsVersion:
        validate_terms(
            terms_text=terms_text,
            refundable_until_hours_before=refundable_until_hours_before,
            forfeit_percent=forfeit_percent,
        )
        throttle_key = f"terms:{tenant_id}"
        if self._terms_limiter.is_blocked(throttle_key):
            raise TermsThrottledError
        try:
            created = await self._insert_next_terms_version(
                tenant_id,
                terms_text=terms_text,
                refundable_until_hours_before=refundable_until_hours_before,
                forfeit_percent=forfeit_percent,
                created_by=created_by,
            )
        except IntegrityError:
            # Lost the version race. The aborted transaction cannot be reused —
            # recompute max in a FRESH tenant_session and retry exactly once.
            try:
                created = await self._insert_next_terms_version(
                    tenant_id,
                    terms_text=terms_text,
                    refundable_until_hours_before=refundable_until_hours_before,
                    forfeit_percent=forfeit_percent,
                    created_by=created_by,
                )
            except IntegrityError:
                raise TermsVersionConflictError from None
        # Every successful creation counts toward the throttle: rows on this
        # append-only path are permanent, so spam here is permanent bloat.
        self._terms_limiter.record_failure(throttle_key)
        return created

    async def _insert_next_terms_version(
        self,
        tenant_id: UUID,
        *,
        terms_text: str,
        refundable_until_hours_before: int,
        forfeit_percent: int,
        created_by: UUID,
    ) -> TermsVersion:
        async with tenant_session(self._session_factory, tenant_id) as session:
            version = await self._terms.max_version(session, tenant_id) + 1
            return await self._terms.insert(
                session,
                tenant_id=tenant_id,
                version=version,
                terms_text=terms_text,
                refundable_until_hours_before=refundable_until_hours_before,
                forfeit_percent=forfeit_percent,
                created_by=created_by,
            )

    async def get_terms_history(
        self, tenant_id: UUID, *, offset: int = 0, limit: int = TERMS_HISTORY_DEFAULT_LIMIT
    ) -> TermsHistoryResult:
        # History is unbounded by design — the page size is capped, not the data.
        offset = max(offset, 0)
        limit = min(max(limit, 1), TERMS_HISTORY_DEFAULT_LIMIT)
        async with tenant_session(self._session_factory, tenant_id) as session:
            current = await self._terms.current(session, tenant_id)
            versions = await self._terms.list_versions(
                session, tenant_id, offset=offset, limit=limit
            )
            total = await self._terms.count(session, tenant_id)
        return TermsHistoryResult(
            current=current, versions=versions, total=total, offset=offset, limit=limit
        )
