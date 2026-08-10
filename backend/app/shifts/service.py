"""F39's shift templates and the weekly availability write.

**The authorization rule that no `RoleGate` can express lives here.** The
router's gate answers "may this role open the section at all" — all five, because
every staffer answers her own week. This service answers "may this person record
for THAT staffer", which depends on the target rather than on the role:

    submit    herself                      -> any role
              somebody else                -> owner, shift_manager ONLY

`floor/service.py:1911-1921` is the shipped shape and this is the fourth
instance: the request names WHOM to record, never WHO is asking.

**`ELEVATED_ROLES` is spelled locally**, as its own two-member frozenset citing
`floor/service.py:101` as the twin, rather than importing `FloorService`'s module
to save two lines — the same call `_no_store`'s five local copies record.
Spelled from the enum and not as literals, so a sixth `StaffRole` is NOT elevated
by default, which is the safe direction to fail.

**D4's invalidation rides the edit's own transaction.** A material template edit
soft-deletes every live answer against it in every FUTURE week; past and current
weeks are history and F40 may already have published off them. The count is
returned to the caller, carried in the audit row, and predicted before the fact
by `future_submission_count` on the templates read — the prediction and the write
run the same predicate, so they cannot disagree about which rows they mean.
"""

import datetime
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.shift_templates import ShiftTemplatesRepository
from app.db.repositories.staff_availability import StaffAvailabilityRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.constants import AuditAction, StaffRole
from app.models.shift_template import ShiftTemplate
from app.shifts.schemas import (
    SeedTemplatesResponse,
    ShiftTemplateInput,
    ShiftTemplateListResponse,
    ShiftTemplateResponse,
)
from app.shifts.validation import (
    assert_template_capacity,
    current_week_start,
    validate_template,
)
from app.storefront.validation import today_jerusalem

# Spelled from the enum rather than as literals, `floor/service.py:101`'s rule
# and its twin: a sixth role added to StaffRole is NOT elevated by default.
ELEVATED_ROLES = frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value})

# 0=Sunday … 6=Saturday — `availability_rules.day_of_week`'s encoding, and the
# same seven words `apps/manage/src/lib/week.ts` renders. Used ONLY for D3's
# auto-label; nothing on any read path formats a day name server-side (the
# console owns its own rendering, `TIMEZONE.md`'s rule).
HEBREW_DAY_NAMES = ("ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת")

# The three fields whose movement makes an edit MATERIAL (D4). `label` and
# `sort_order` are deliberately absent: renaming «משמרת בוקר» to «בוקר» changes
# nothing a staffer answered, and invalidating on it would make the owner's
# typo fix cost other people's answers.
MATERIAL_FIELDS = ("day_of_week", "starts_at_time", "ends_at_time")


class ShiftNotFoundError(DomainNotFoundError):
    """No live template or staffer by that id for this tenant — including another
    tenant's id (RLS plus the explicit predicate make foreign rows
    indistinguishable from missing ones, by design)."""


class TemplatesAlreadySeededError(Exception):
    """D3's refusal. 409 `TEMPLATES_ALREADY_SEEDED`.

    A re-sync that silently destroyed the owner's splits is the failure this
    exists to prevent — she splits Thursday into a morning and an evening, then
    presses a button she half-remembers and gets one full-day Thursday back.

    Deliberately NOT a `DomainValidationError` subclass, `ReservationOverlapError`'s
    recorded rule: a coded error shipped without its own handler must answer a
    loud 500 rather than a quiet, plausible 400 the console has no Hebrew string
    for.
    """


class NoOpeningHoursError(Exception):
    """D3's other refusal: there is nothing to seed FROM. 409 `NO_OPENING_HOURS`.

    ⚠ The console does NOT pre-check this — it renders the seed button
    unconditionally and maps this code (design F-9). A pre-check would mean a
    second reader of `availability_rules` that can disagree with the writer, one
    request earlier, to hide a control the server already guards.
    """


class ShiftsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._templates = ShiftTemplatesRepository()
        self._availability = StaffAvailabilityRepository()
        self._rules = AvailabilityRulesRepository()
        self._staff = StaffUsersRepository()
        self._audit = AuditLogRepository()
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))

    # --- templates -----------------------------------------------------------

    async def list_templates(
        self, tenant_id: UUID, *, actor: StaffContext
    ) -> ShiftTemplateListResponse:
        """TWO statements for an elevated reader, ONE for everybody else.

        `future_submission_count` is D4's pre-commit number and only the editor
        needs it, so a staffer's own panel never pays for the aggregate — and the
        field is `None` rather than `0` for her, because "not asked" and "no
        answers exist" are different facts and a `0` would let a later reader
        build a confirm dialog on a number nobody computed.
        """
        current = current_week_start(today_jerusalem(self._clock))
        async with tenant_session(self._sessions, tenant_id) as session:
            rows = await self._templates.list_live(session, tenant_id)
            counts: dict[UUID, int] = {}
            if actor.role in ELEVATED_ROLES:
                counts = await self._availability.future_counts_by_template(
                    session, tenant_id, after_week=current
                )
        return ShiftTemplateListResponse(
            templates=[
                self._template_response(row, counts if actor.role in ELEVATED_ROLES else None)
                for row in rows
            ]
        )

    async def create_template(
        self, tenant_id: UUID, *, actor: StaffContext, body: ShiftTemplateInput
    ) -> ShiftTemplateResponse:
        label = validate_template(
            day_of_week=body.day_of_week,
            label=body.label,
            starts_at_time=body.starts_at_time,
            ends_at_time=body.ends_at_time,
        )
        async with tenant_session(self._sessions, tenant_id) as session:
            counts = await self._templates.counts(session, tenant_id)
            assert_template_capacity(
                day_count=counts.get(body.day_of_week, 0), total_count=sum(counts.values())
            )
            row = await self._templates.insert(
                session,
                tenant_id=tenant_id,
                day_of_week=body.day_of_week,
                label=label,
                starts_at_time=body.starts_at_time,
                ends_at_time=body.ends_at_time,
                sort_order=body.sort_order,
            )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.SHIFT_TEMPLATE_CREATED.value,
                actor_id=actor.id,
                entity=str(row.id),
                details={"day_of_week": row.day_of_week},
            )
            return self._template_response(row, None)

    async def update_template(
        self,
        tenant_id: UUID,
        template_id: UUID,
        *,
        actor: StaffContext,
        body: ShiftTemplateInput,
    ) -> ShiftTemplateResponse:
        """D2's full replace plus D4's invalidation, in ONE transaction.

        ⚠ THE MATERIALITY TEST READS THE ROW BEFORE THE WRITE. SQLAlchemy's
        ORM-enabled UPDATE synchronises by `evaluate`, which stamps the new values
        onto the very instance a later comparison would read — the identity-map
        trap `SOS_RESOLVED`'s `from_status` records, and here it would make every
        edit look immaterial and invalidate nothing at all.
        """
        label = validate_template(
            day_of_week=body.day_of_week,
            label=body.label,
            starts_at_time=body.starts_at_time,
            ends_at_time=body.ends_at_time,
        )
        current = current_week_start(today_jerusalem(self._clock))
        async with tenant_session(self._sessions, tenant_id) as session:
            before = await self._templates.by_id(session, tenant_id, template_id)
            if before is None:
                raise ShiftNotFoundError
            material = is_material_edit(
                before={field: getattr(before, field) for field in MATERIAL_FIELDS},
                after={
                    "day_of_week": body.day_of_week,
                    "starts_at_time": body.starts_at_time,
                    "ends_at_time": body.ends_at_time,
                },
            )
            row = await self._templates.replace(
                session,
                tenant_id,
                template_id,
                day_of_week=body.day_of_week,
                label=label,
                starts_at_time=body.starts_at_time,
                ends_at_time=body.ends_at_time,
                sort_order=body.sort_order,
            )
            if row is None:
                raise ShiftNotFoundError
            invalidated = 0
            if material:
                invalidated = await self._availability.soft_delete_future_by_template(
                    session, tenant_id, template_id, after_week=current
                )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.SHIFT_TEMPLATE_UPDATED.value,
                actor_id=actor.id,
                entity=str(template_id),
                details={"material": material, "invalidated_submissions": invalidated},
            )
            return self._template_response(row, {template_id: 0})

    async def delete_template(
        self, tenant_id: UUID, template_id: UUID, *, actor: StaffContext
    ) -> int:
        """Soft delete plus D4's invalidation, in one transaction. Returns the
        count so the console can announce the number that really moved rather
        than the one it predicted."""
        current = current_week_start(today_jerusalem(self._clock))
        async with tenant_session(self._sessions, tenant_id) as session:
            if not await self._templates.soft_delete(session, tenant_id, template_id):
                raise ShiftNotFoundError
            invalidated = await self._availability.soft_delete_future_by_template(
                session, tenant_id, template_id, after_week=current
            )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.SHIFT_TEMPLATE_DELETED.value,
                actor_id=actor.id,
                entity=str(template_id),
                details={"invalidated_submissions": invalidated},
            )
            return invalidated

    async def seed_templates(
        self, tenant_id: UUID, *, actor: StaffContext
    ) -> SeedTemplatesResponse:
        """D3: ONE template per live `availability_rules` row, once, refusably.

        ⚠ `capacity` IS DELIBERATELY DROPPED. It is the slot engine's
        parallel-appointments number, not a headcount — copying it would make a
        "capacity 2" window read as "two staff needed", which is a coverage target
        and therefore F40's, and would be wrong the day a boutique takes two
        fittings with one assistant.

        ⚠ SATURDAY GETS NOTHING BECAUSE IT HAS NO RULE, as an emergent consequence
        of the tenant's own data and never as a hardcoded Shabbat rule. A boutique
        that entered Saturday hours gets Saturday shifts.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            if await self._templates.list_live(session, tenant_id):
                raise TemplatesAlreadySeededError
            rules = await self._rules.list_active(session, tenant_id)
            if not rules:
                raise NoOpeningHoursError
            ordered = sorted(rules, key=lambda rule: (rule.day_of_week, rule.open_time))
            created: list[ShiftTemplate] = []
            for sort_order, rule in enumerate(ordered):
                created.append(
                    await self._templates.insert(
                        session,
                        tenant_id=tenant_id,
                        day_of_week=rule.day_of_week,
                        label=seed_label(
                            day_of_week=rule.day_of_week,
                            starts_at_time=rule.open_time,
                            ends_at_time=rule.close_time,
                        ),
                        starts_at_time=rule.open_time,
                        ends_at_time=rule.close_time,
                        sort_order=sort_order,
                    )
                )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.SHIFT_TEMPLATES_SEEDED.value,
                actor_id=actor.id,
                entity=str(tenant_id),
                details={"created": len(created)},
            )
            return SeedTemplatesResponse(
                created=len(created),
                templates=[self._template_response(row, {}) for row in created],
            )

    # --- shared --------------------------------------------------------------

    @staticmethod
    def _template_response(
        row: ShiftTemplate, counts: dict[UUID, int] | None
    ) -> ShiftTemplateResponse:
        return ShiftTemplateResponse(
            id=row.id,
            day_of_week=row.day_of_week,
            label=row.label,
            starts_at_time=row.starts_at_time,
            ends_at_time=row.ends_at_time,
            sort_order=row.sort_order,
            future_submission_count=None if counts is None else counts.get(row.id, 0),
        )


def is_material_edit(*, before: dict[str, object], after: dict[str, object]) -> bool:
    """D4's predicate, as a pure function so both the service and the console can
    be tested against the same rule (the client compares the same four fields to
    decide whether to open the confirm dialog at all).

    `label` and `sort_order` are not in `MATERIAL_FIELDS` and therefore cannot
    reach this — renaming a shift changes nothing anybody answered.
    """
    return any(before[field] != after[field] for field in MATERIAL_FIELDS)


def seed_label(
    *, day_of_week: int, starts_at_time: datetime.time, ends_at_time: datetime.time
) -> str:
    """«ראשון 09:00–17:00» — D3's auto-label.

    An EN DASH, not a hyphen, matching every other time range in this product.
    The owner replaces this string the moment she splits a day, which is exactly
    why the console never relies on it to say which weekday a shift is on
    (design F-19).
    """
    return (
        f"{HEBREW_DAY_NAMES[day_of_week]} "
        f"{starts_at_time.strftime('%H:%M')}–{ends_at_time.strftime('%H:%M')}"
    )
