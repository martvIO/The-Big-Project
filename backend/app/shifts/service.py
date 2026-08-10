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
from collections.abc import Callable, Mapping
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.roster_assignments import RosterAssignmentsRepository
from app.db.repositories.rosters import RostersRepository
from app.db.repositories.shift_templates import ShiftTemplatesRepository
from app.db.repositories.staff_availability import StaffAvailabilityRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.constants import AuditAction, AvailabilityState, StaffRole
from app.models.roster_assignment import RosterAssignment
from app.models.shift_template import ShiftTemplate
from app.models.staff_availability import StaffAvailability
from app.models.staff_user import StaffUser
from app.shifts.schemas import (
    AvailabilityEntryResponse,
    CreateAssignmentRequest,
    PublishedRosterResponse,
    RosterAssignmentResponse,
    RosterShiftResponse,
    RosterStaffRefResponse,
    RosterWeekResponse,
    SeedTemplatesResponse,
    ShiftTemplateInput,
    ShiftTemplateListResponse,
    ShiftTemplateResponse,
    ShiftWeekResponse,
    SubmitAvailabilityRequest,
    TemplateWriteResponse,
    WeekSubmissionRowResponse,
    WeekSubmissionsResponse,
)
from app.shifts.validation import (
    WeekOutOfRangeError,
    assert_readable_week,
    assert_template_capacity,
    assert_writable_week,
    current_week_start,
    deadline_at,
    default_week_start,
    scheduling_pair,
    validate_template,
    validate_week_start,
    week_end,
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

# The partial unique index behind D12. Matched against the driver's own error
# text so the manager conflict can be told apart from the assignment triple's:
# one is a genuine 409 and the other is a race worth retrying once, and a
# handler that could not tell them apart would answer the wrong code for both.
_MANAGER_INDEX = "idx_roster_assignments_manager_unique"


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


class SubmissionClosedError(Exception):
    """The deadline for that week has passed and the caller is NOT elevated.
    409 `SUBMISSION_CLOSED`.

    ⚠ THERE IS NO REOPEN (spec C3). An elevated actor is simply not subject to
    the deadline and may record for anyone, at any time before the week starts,
    with `recorded_by` on the row and `after_deadline` in the audit entry. The
    brief's reopen mechanism needed per-week state — a row, a clock, a who, an
    expiry — to express something the shipped role model already expresses for
    free, and state that does not exist cannot drift.

    Same non-subclassing rule as its neighbours: a coded error without its own
    handler must answer a loud 500.
    """


class AvailabilityConflictError(Exception):
    """F40 D11: she submitted `unavailable` for this shift and the request did not
    carry `acknowledge_override: true`. 409 `AVAILABILITY_CONFLICT`.

    ⚠ THE ASSIGNMENT IS NOT REFUSED — the ACKNOWLEDGEMENT is. «A real Thursday
    needs cover regardless of what was submitted on Sunday» is the brief's own
    sentence and it is right; what D11 buys is that an override is always a
    second, deliberate act rather than a slip.

    Same non-subclassing rule as its neighbours: a coded error without its own
    handler answers a quiet, plausible 400 the console has no Hebrew string for.
    """


class NotShiftManagerEligibleError(Exception):
    """F40 D12: `staff_users.shift_manager_eligible` is false. 400
    `NOT_SHIFT_MANAGER_ELIGIBLE`.

    ⚠ THE COLUMN ALONE, NEVER `role`. F38 shipped that boolean specifically to
    separate «may be assigned as shift manager» from «her job is shift manager»,
    and deriving one from the other deletes the distinction it was created to
    make. The visible cost is real and accepted: on a fresh boutique NOBODY is
    eligible and the slot is unfillable until the owner ticks a box on «צוות» —
    one action, once, versus a permanent silent conflation.
    """


class ShiftManagerSlotTakenError(Exception):
    """F40 D12: another live assignment on that (roster, shift) already carries
    the flag. 409 `SHIFT_MANAGER_SLOT_TAKEN`.

    ⚠ RAISED FROM `idx_roster_assignments_manager_unique`'s `IntegrityError`,
    never from a read that raced. A service that read first and then wrote would
    let two managers through under exactly the interleaving this exists for.
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
        self._rosters = RostersRepository()
        self._assignments = RosterAssignmentsRepository()
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
    ) -> TemplateWriteResponse:
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
            return TemplateWriteResponse(
                template=self._template_response(row, {template_id: 0}),
                invalidated_submissions=invalidated,
            )

    async def delete_template(
        self, tenant_id: UUID, template_id: UUID, *, actor: StaffContext
    ) -> TemplateWriteResponse:
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
            return TemplateWriteResponse(template=None, invalidated_submissions=invalidated)

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

    # --- the week ------------------------------------------------------------

    async def week(
        self,
        tenant_id: UUID,
        *,
        actor: StaffContext,
        settings: dict[str, object],
        week_start: datetime.date | None = None,
    ) -> ShiftWeekResponse:
        """HER OWN week. `week_start` is optional and defaults to NEXT week (D1),
        which is the week she opened the section to answer.

        ⚠ `locked` IS ACTOR-RELATIVE (design F-1) AND ALSO WEEK-RELATIVE. D5
        exempts elevated actors from the deadline entirely, so a `locked` computed
        from `(setting, week)` alone would remove the owner's save button on a
        write that would have succeeded. It is equally true in the other
        direction: an elevated actor reading a PAST week can write nothing either,
        because D1's window is forward-only for writes — so `locked` is «this
        actor cannot write this week», computed by the same two guards
        `submit` runs. `deposit_due`'s rule: the page a person reads and the flow
        she then enters cannot disagree.
        """
        today = today_jerusalem(self._clock)
        current = current_week_start(today)
        target = (
            validate_week_start(week_start) if week_start is not None else default_week_start(today)
        )
        assert_readable_week(target, current=current)
        resolved_deadline = self._deadline(target, settings)
        async with tenant_session(self._sessions, tenant_id) as session:
            templates = await self._templates.list_live(session, tenant_id)
            entries = await self._availability.live_for_week(
                session, tenant_id, week_start=target, staff_user_id=actor.id
            )
            names = await self._recorder_names(session, tenant_id, entries)
            roster_published, rostered = await self._her_published_shifts(
                session, tenant_id, week_start=target, staff_user_id=actor.id
            )
        return ShiftWeekResponse(
            week_start=target,
            week_end=week_end(target),
            deadline_at=resolved_deadline,
            locked=self._locked(
                target, current=current, actor=actor, resolved_deadline=resolved_deadline
            ),
            templates=[self._template_response(row, None) for row in templates],
            entries=[self._entry_response(row, names) for row in entries],
            roster_published=roster_published,
            rostered_template_ids=rostered,
        )

    async def submit(
        self,
        tenant_id: UUID,
        *,
        actor: StaffContext,
        settings: dict[str, object],
        body: SubmitAvailabilityRequest,
    ) -> ShiftWeekResponse:
        """D11's whole-week replace for ONE staffer, in one request.

        The three refusals that depend on the REQUEST ALONE run before any session
        opens (`floor/service.py:11-16`'s rule) — a 403 raised after a read is an
        existence oracle:

            1. the self-or-elevated guard (403);
            2. the week window, forward-only for writes (400);
            3. the deadline, for a non-elevated actor only (409).

        ⚠ RETRIED EXACTLY ONCE ON `IntegrityError`. Two devices saving the same
        pair at the same moment both see zero rows on the UPDATE and both INSERT;
        `idx_staff_availability_unique` refuses the loser, whose transaction is
        then unusable, so the retry runs in a FRESH `tenant_session` and the
        second pass finds the row and updates it
        (`_insert_next_terms_version`'s shipped optimistic shape). No advisory
        lock: the tenant-wide key is far too coarse for a per-tap write and the
        index is a structural guarantee where the lock is only a serialisation.
        """
        target_staff_id = body.staff_user_id or actor.id
        self._authorize(target_staff_id, actor)
        today = today_jerusalem(self._clock)
        current = current_week_start(today)
        assert_writable_week(body.week_start, current=current)
        resolved_deadline = self._deadline(body.week_start, settings)
        after_deadline = self._clock() >= resolved_deadline
        elevated = actor.role in ELEVATED_ROLES
        if after_deadline and not elevated:
            raise SubmissionClosedError

        try:
            await self._apply(
                tenant_id,
                actor=actor,
                target_staff_id=target_staff_id,
                body=body,
                after_deadline=after_deadline,
            )
        except IntegrityError:
            # Lost the per-pair race. The aborted transaction cannot be reused —
            # a FRESH tenant_session re-reads and retries exactly once.
            await self._apply(
                tenant_id,
                actor=actor,
                target_staff_id=target_staff_id,
                body=body,
                after_deadline=after_deadline,
            )

        async with tenant_session(self._sessions, tenant_id) as session:
            templates = await self._templates.list_live(session, tenant_id)
            entries = await self._availability.live_for_week(
                session, tenant_id, week_start=body.week_start, staff_user_id=target_staff_id
            )
            names = await self._recorder_names(session, tenant_id, entries)
            roster_published, rostered = await self._her_published_shifts(
                session, tenant_id, week_start=body.week_start, staff_user_id=target_staff_id
            )
        return ShiftWeekResponse(
            week_start=body.week_start,
            week_end=week_end(body.week_start),
            deadline_at=resolved_deadline,
            locked=self._locked(
                body.week_start, current=current, actor=actor, resolved_deadline=resolved_deadline
            ),
            templates=[self._template_response(row, None) for row in templates],
            entries=[self._entry_response(row, names) for row in entries],
            roster_published=roster_published,
            rostered_template_ids=rostered,
        )

    async def _apply(
        self,
        tenant_id: UUID,
        *,
        actor: StaffContext,
        target_staff_id: UUID,
        body: SubmitAvailabilityRequest,
        after_deadline: bool,
    ) -> None:
        """One transaction: validate the parents, diff against what is live, write
        only what moved, and audit only if anything did."""
        # `recorded_by` is the ACTOR when she is recording for somebody else and
        # NULL when it is her own week — including when a staffer corrects a row an
        # elevated actor recorded for her, which must clear the column or her
        # screen keeps saying somebody else gave the answer she just gave.
        recorded_by = actor.id if target_staff_id != actor.id else None
        async with tenant_session(self._sessions, tenant_id) as session:
            staffer = await self._staff.by_id(session, tenant_id, target_staff_id)
            if staffer is None or not is_available_for_week(
                staffer, week_end_date=week_end(body.week_start)
            ):
                raise ShiftNotFoundError
            live_templates = {row.id for row in await self._templates.list_live(session, tenant_id)}
            requested = {entry.shift_template_id: entry.state for entry in body.entries}
            unknown = set(requested) - live_templates
            if unknown:
                raise ShiftNotFoundError

            existing = {
                row.shift_template_id: row
                for row in await self._availability.live_for_week(
                    session,
                    tenant_id,
                    week_start=body.week_start,
                    staff_user_id=target_staff_id,
                )
            }
            changed, cleared = plan_week_write(
                existing={
                    template_id: (row.state, row.recorded_by)
                    for template_id, row in existing.items()
                },
                requested=requested,
                recorded_by=recorded_by,
            )
            if not changed and not cleared:
                # ⚠ A SAVE THAT CHANGES NOTHING WRITES NO AUDIT ROW (the shipped
                # no-op rule). A row asserting otherwise names an act nobody
                # performed — and «who recorded whose availability» is exactly the
                # question this table gets asked.
                return

            for template_id in changed:
                await self._availability.set_state(
                    session,
                    tenant_id=tenant_id,
                    staff_user_id=target_staff_id,
                    shift_template_id=template_id,
                    week_start=body.week_start,
                    state=requested[template_id].value,
                    recorded_by=recorded_by,
                )
            await self._availability.soft_delete_pairs(
                session,
                tenant_id,
                staff_user_id=target_staff_id,
                week_start=body.week_start,
                template_ids=cleared,
            )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.AVAILABILITY_SUBMITTED.value,
                actor_id=actor.id,
                entity=str(target_staff_id),
                # ⚠ IDS AND COUNTS ONLY, NEVER A DISPLAY NAME (CUSTOMER_UPDATED's
                # rule): `audit_log` has no retention class and platform operators
                # read across tenants. `on_behalf_of` is None for her own save, so
                # «who recorded this, for whom, past the deadline» stays one
                # `WHERE action = 'availability_submitted'` and not a JSONB walk.
                details={
                    "week_start": body.week_start.isoformat(),
                    "on_behalf_of": str(target_staff_id) if recorded_by is not None else None,
                    "after_deadline": after_deadline,
                    "counts": _state_counts(list(requested.values())),
                    "cleared": len(cleared),
                },
            )

    async def submissions(
        self,
        tenant_id: UUID,
        *,
        week_start: datetime.date | None = None,
    ) -> WeekSubmissionsResponse:
        """Roster readiness: every staffer who will still be here that week, with
        what she said. TWO statements plus one name resolution.

        `submitted` is «at least one live row» and NOT «answered every template»
        (design P8): D8 has no way to distinguish a deliberate blank from a
        refusal, so making it the stricter thing would punish a staffer who
        answered eleven of twelve on purpose.
        """
        today = today_jerusalem(self._clock)
        current = current_week_start(today)
        target = (
            validate_week_start(week_start) if week_start is not None else default_week_start(today)
        )
        assert_readable_week(target, current=current)
        ends_on = week_end(target)
        async with tenant_session(self._sessions, tenant_id) as session:
            staff = [
                row
                for row in await self._staff.list_live(session, tenant_id)
                if is_available_for_week(row, week_end_date=ends_on)
            ]
            entries = await self._availability.live_for_week(session, tenant_id, week_start=target)
            names = await self._recorder_names(session, tenant_id, entries)
        by_staff: dict[UUID, list[AvailabilityEntryResponse]] = {row.id: [] for row in staff}
        for entry in entries:
            # An answer belonging to an offboarded staffer is dropped rather than
            # given a row of its own: D10's whole point is that she is never asked,
            # and a name on this list is a name F40 would roster.
            if entry.staff_user_id in by_staff:
                by_staff[entry.staff_user_id].append(self._entry_response(entry, names))
        rows = [
            WeekSubmissionRowResponse(
                staff_user_id=row.id,
                display_name=row.display_name,
                submitted=bool(by_staff[row.id]),
                entries=by_staff[row.id],
            )
            for row in staff
        ]
        return WeekSubmissionsResponse(
            week_start=target,
            week_end=ends_on,
            submitted_count=sum(1 for row in rows if row.submitted),
            total=len(rows),
            rows=rows,
        )

    # --- F40: the roster ------------------------------------------------------

    async def roster(
        self,
        tenant_id: UUID,
        *,
        actor: StaffContext,
        week_start: datetime.date | None = None,
    ) -> RosterWeekResponse:
        """The builder's payload — ELEVATED, because it carries every colleague's
        submitted state (F39's own reason for gating `/shifts/week/submissions`).

        ⚠ `assert_readable_week`, NOT `assert_writable_week`, AND THAT IS THE
        LIKELIEST BUILD ERROR IN THIS FEATURE. F39's forward-only guard is about
        SUBMISSIONS; the roster reaches ±4 weeks so a RUNNING week can still be
        edited (D7) — which is exactly what the same-day override exists NOT to
        have to substitute for. Every backend test on future weeks passes under
        the wrong one.
        """
        self._assert_elevated(actor)
        today = today_jerusalem(self._clock)
        current = current_week_start(today)
        target = (
            validate_week_start(week_start) if week_start is not None else default_week_start(today)
        )
        assert_readable_week(target, current=current)
        ends_on = week_end(target)
        async with tenant_session(self._sessions, tenant_id) as session:
            templates = await self._templates.list_live(session, tenant_id)
            staff = [
                row
                for row in await self._staff.list_live(session, tenant_id)
                if is_available_for_week(row, week_end_date=ends_on)
            ]
            entries = await self._availability.live_for_week(session, tenant_id, week_start=target)
            roster = await self._rosters.by_week(session, tenant_id, target)
            assignments = (
                []
                if roster is None
                else await self._assignments.by_roster(session, tenant_id, roster.id)
            )
            published_by_name = None
            edited = False
            if roster is not None and roster.published_at is not None:
                # ⚠ THE SAME PREDICATE PUBLISH'S NO-OP BRANCH USES. Two
                # implementations of «has the set moved since the stamp» is two
                # answers to one question — the header saying «בוצעו שינויים מאז
                # הפרסום» while publish refuses to write, or the reverse.
                edited = await self._assignments.changed_since(
                    session, tenant_id, roster.id, roster.published_at
                )
                if roster.published_by is not None:
                    row = await self._staff.by_id(session, tenant_id, roster.published_by)
                    published_by_name = None if row is None else row.display_name

        staff_by_id = {row.id: row for row in staff}
        return RosterWeekResponse(
            week_start=target,
            week_end=ends_on,
            published_at=None if roster is None else roster.published_at,
            published_by_name=published_by_name,
            edited_since_publish=edited,
            shifts=[
                self._shift_response(template, assignments, staff_by_id) for template in templates
            ],
            staff=[self._staff_ref(row, entries) for row in staff],
        )

    async def assign(
        self, tenant_id: UUID, *, actor: StaffContext, body: CreateAssignmentRequest
    ) -> RosterShiftResponse:
        """D11/D12's write, and an UPSERT on the live `(roster, template, staffer)`
        triple (design F-2) — so it answers 200 on both paths.

        ⚠ RETRIED EXACTLY ONCE ON THE TRIPLE'S `IntegrityError`, F39's shipped
        optimistic shape: two devices assigning the same woman at the same moment
        both see no live row and both INSERT, and the loser's transaction is then
        unusable, so the retry runs in a FRESH `tenant_session` and finds the row.
        NO ADVISORY LOCK — a tenant-wide key is far too coarse for a per-tap
        write, and the index is a structural guarantee where the lock would only
        be a serialisation.

        ⚠ THE MANAGER INDEX'S `IntegrityError` IS NOT RETRIED. It is a genuine
        conflict — somebody else holds that shift's slot — and retrying would
        answer 409 one round-trip later having written nothing either way.
        """
        self._assert_elevated(actor)
        current = current_week_start(today_jerusalem(self._clock))
        validate_week_start(body.week_start)
        assert_readable_week(body.week_start, current=current)
        try:
            return await self._apply_assignment(tenant_id, actor=actor, body=body)
        except IntegrityError as exc:
            if _MANAGER_INDEX in str(exc.orig):
                raise ShiftManagerSlotTakenError from None
            return await self._apply_assignment(tenant_id, actor=actor, body=body)

    async def _apply_assignment(
        self, tenant_id: UUID, *, actor: StaffContext, body: CreateAssignmentRequest
    ) -> RosterShiftResponse:
        async with tenant_session(self._sessions, tenant_id) as session:
            template = await self._templates.by_id(session, tenant_id, body.shift_template_id)
            if template is None:
                raise ShiftNotFoundError
            staffer = await self._staff.by_id(session, tenant_id, body.staff_user_id)
            if staffer is None or not is_available_for_week(
                staffer, week_end_date=week_end(body.week_start)
            ):
                raise ShiftNotFoundError
            assert_manager_eligible(staffer, is_shift_manager=body.is_shift_manager)

            roster = await self._rosters.by_week(session, tenant_id, body.week_start)
            if roster is None:
                # Created lazily by the FIRST assignment, IN THIS TRANSACTION, so
                # an owner who opens the builder and closes it leaves no row.
                roster = await self._rosters.create(
                    session, tenant_id=tenant_id, week_start=body.week_start
                )
            live = await self._assignments.live_for_triple(
                session,
                tenant_id,
                roster_id=roster.id,
                shift_template_id=template.id,
                staff_user_id=staffer.id,
            )
            if live is not None:
                # ⚠ THE UPSERT MOVES `is_shift_manager` AND NOTHING ELSE.
                # `override_of_state` is the stamp from ASSIGNMENT time (design
                # F-5) and re-deriving it here would erase the record of what the
                # owner knowingly did — or invent one she never made.
                if live.is_shift_manager != body.is_shift_manager:
                    await self._assignments.set_manager_flag(
                        session, tenant_id, live.id, is_shift_manager=body.is_shift_manager
                    )
                    await self._audit_assignment(
                        session,
                        tenant_id=tenant_id,
                        actor=actor,
                        assignment_id=live.id,
                        week_start=body.week_start,
                        template_id=template.id,
                        staff_user_id=staffer.id,
                        is_shift_manager=body.is_shift_manager,
                        override_of_state=live.override_of_state,
                    )
                # else: a write that changes nothing writes no audit row.
            else:
                submitted = await self._availability.live_for_week(
                    session,
                    tenant_id,
                    week_start=body.week_start,
                    staff_user_id=staffer.id,
                )
                state = next(
                    (row.state for row in submitted if row.shift_template_id == template.id),
                    None,
                )
                override = override_stamp(state, acknowledged=body.acknowledge_override)
                row = await self._assignments.insert(
                    session,
                    tenant_id=tenant_id,
                    roster_id=roster.id,
                    shift_template_id=template.id,
                    staff_user_id=staffer.id,
                    assigned_by=actor.id,
                    is_shift_manager=body.is_shift_manager,
                    override_of_state=override,
                )
                await self._audit_assignment(
                    session,
                    tenant_id=tenant_id,
                    actor=actor,
                    assignment_id=row.id,
                    week_start=body.week_start,
                    template_id=template.id,
                    staff_user_id=staffer.id,
                    is_shift_manager=body.is_shift_manager,
                    override_of_state=override,
                )
            return await self._shift_payload(session, tenant_id, template, roster.id)

    async def unassign(
        self, tenant_id: UUID, *, actor: StaffContext, assignment_id: UUID
    ) -> RosterShiftResponse:
        """Soft delete, and it answers the affected shift so the pane patches one
        block in place rather than refetching a week."""
        self._assert_elevated(actor)
        async with tenant_session(self._sessions, tenant_id) as session:
            removed = await self._assignments.soft_delete(session, tenant_id, assignment_id)
            if removed is None:
                raise ShiftNotFoundError
            roster = await self._rosters.by_id(session, tenant_id, removed.roster_id)
            template = await self._templates.by_id(session, tenant_id, removed.shift_template_id)
            if roster is None or template is None:
                raise ShiftNotFoundError
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.ROSTER_UNASSIGNED.value,
                actor_id=actor.id,
                entity=str(assignment_id),
                details={
                    "week_start": roster.week_start.isoformat(),
                    "shift_template_id": str(removed.shift_template_id),
                    "staff_user_id": str(removed.staff_user_id),
                    "is_shift_manager": removed.is_shift_manager,
                },
            )
            return await self._shift_payload(session, tenant_id, template, roster.id)

    async def _audit_assignment(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        actor: StaffContext,
        assignment_id: UUID,
        week_start: datetime.date,
        template_id: UUID,
        staff_user_id: UUID,
        is_shift_manager: bool,
        override_of_state: str | None,
    ) -> None:
        """⚠ IDS AND FLAGS ONLY, NEVER A DISPLAY NAME (`CUSTOMER_UPDATED`'s rule):
        `audit_log` has no retention class and platform operators read across
        tenants."""
        await self._audit.record(
            session,
            tenant_id=tenant_id,
            action=AuditAction.ROSTER_ASSIGNED.value,
            actor_id=actor.id,
            entity=str(assignment_id),
            details={
                "week_start": week_start.isoformat(),
                "shift_template_id": str(template_id),
                "staff_user_id": str(staff_user_id),
                "is_shift_manager": is_shift_manager,
                "override_of_state": override_of_state,
            },
        )

    async def _shift_payload(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        template: ShiftTemplate,
        roster_id: UUID,
    ) -> RosterShiftResponse:
        """⚠ ONE SHIFT, NEVER THE WHOLE WEEK (plan §0.1). A whole-week payload per
        tap breaks under the pane's deliberate per-control concurrency: two writes
        in flight from one dialog, the earlier-issued response arriving second,
        and the later assignment silently lost."""
        assignments = await self._assignments.by_roster(session, tenant_id, roster_id)
        staff_by_id = {row.id: row for row in await self._staff.list_live(session, tenant_id)}
        return self._shift_response(template, assignments, staff_by_id)

    @staticmethod
    def _shift_response(
        template: ShiftTemplate,
        assignments: list[RosterAssignment],
        staff_by_id: dict[UUID, StaffUser],
    ) -> RosterShiftResponse:
        """⚠ AN ASSIGNMENT WHOSE STAFFER HAS BEEN OFFBOARDED IS DROPPED rather
        than rendered nameless — F39's `submissions` rule, and for its reason: a
        name on this list is a name the owner would roster."""
        rows = [
            row
            for row in assignments
            if row.shift_template_id == template.id and row.staff_user_id in staff_by_id
        ]
        assigned_by_role: dict[str, int] = {}
        for row in rows:
            role = staff_by_id[row.staff_user_id].role
            assigned_by_role[role] = assigned_by_role.get(role, 0) + 1
        return RosterShiftResponse(
            template=ShiftsService._template_response(template, None),
            assignments=[
                RosterAssignmentResponse(
                    id=row.id,
                    staff_user_id=row.staff_user_id,
                    display_name=staff_by_id[row.staff_user_id].display_name,
                    role=staff_by_id[row.staff_user_id].role,
                    is_shift_manager=row.is_shift_manager,
                    override_of_state=(
                        None
                        if row.override_of_state is None
                        else AvailabilityState(row.override_of_state)
                    ),
                )
                for row in rows
            ],
            coverage_targets=dict(template.coverage_targets),
            assigned_by_role=assigned_by_role,
        )

    @staticmethod
    def _staff_ref(row: StaffUser, entries: list[StaffAvailability]) -> RosterStaffRefResponse:
        return RosterStaffRefResponse(
            id=row.id,
            display_name=row.display_name,
            role=row.role,
            shift_manager_eligible=row.shift_manager_eligible,
            # An ABSENT key is «not answered» (D8). There is no fourth state.
            states={
                str(entry.shift_template_id): AvailabilityState(entry.state)
                for entry in entries
                if entry.staff_user_id == row.id
            },
        )

    @staticmethod
    def _assert_elevated(actor: StaffContext) -> None:
        """C4/D13: build, publish and the same-day override are ALL elevated, and
        none of them is owner-only. A shift manager who may assign but not publish
        has built a roster nobody can see, and this console has no
        submit-for-approval concept to give her.

        The router carries the same gate; this is the repositories' redundant
        `tenant_id` predicate applied to authorization — a second, agreeing guard
        that makes the 403 provable with no HTTP in the way.
        """
        if actor.role not in ELEVATED_ROLES:
            raise NotAuthorizedError

    async def publish(
        self, tenant_id: UUID, *, actor: StaffContext, week_start: datetime.date
    ) -> RosterWeekResponse:
        """D7, and every one of its four clauses is here:

        * an UNPUBLISHED week is stamped and audited;
        * an already-published week whose assignment set has NOT moved since the
          stamp is a **no-op — no write, no audit row** — answering 200 with the
          same payload (the shipped no-op rule: F51's per-field audit, F39's D11,
          `_transition`'s `changed=False`);
        * an already-published week that HAS been edited is re-stamped and
          audited with `republish: true`;
        * THERE IS NO UNPUBLISH, and a running week is not special-cased.

        ⚠ A WEEK WITH NO ROSTER ROW AT ALL IS PUBLISHABLE, and the row is created
        here. «Published with nobody on it» is a real, deliberate statement (D5)
        — it is how an owner says the boutique is closed that Saturday — and
        refusing it would leave her no way to say so at all.

        ⚠ EDITS AFTER A PUBLISH DO NOT MOVE `published_at` (D3's failure mode).
        Only this route does.
        """
        self._assert_elevated(actor)
        current = current_week_start(today_jerusalem(self._clock))
        validate_week_start(week_start)
        assert_readable_week(week_start, current=current)

        async with tenant_session(self._sessions, tenant_id) as session:
            roster = await self._rosters.by_week(session, tenant_id, week_start)
            if roster is None:
                roster = await self._rosters.create(
                    session, tenant_id=tenant_id, week_start=week_start
                )
            stamped_at = roster.published_at
            republish = stamped_at is not None
            if stamped_at is not None and not await self._assignments.changed_since(
                session, tenant_id, roster.id, stamped_at
            ):
                # ⚠ NO WRITE AND NO AUDIT ROW. The pane still shows its cue:
                # telling her «nothing happened» when the outcome she wanted is
                # the outcome that holds would be telling her she was wrong when
                # she was right (`floor.breakStartedCue`'s recorded argument).
                return await self.roster(tenant_id, actor=actor, week_start=week_start)

            await self._rosters.stamp_published(session, tenant_id, roster.id, by=actor.id)
            assignments = await self._assignments.by_roster(session, tenant_id, roster.id)
            templates = await self._templates.list_live(session, tenant_id)
            staff_by_id = {row.id: row for row in await self._staff.list_live(session, tenant_id)}
            shifts = [
                self._shift_response(template, assignments, staff_by_id) for template in templates
            ]
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.ROSTER_PUBLISHED.value,
                actor_id=actor.id,
                entity=str(roster.id),
                # Counts and a week key. IDS ONLY, NEVER A DISPLAY NAME
                # (`CUSTOMER_UPDATED`'s rule).
                details={
                    "week_start": week_start.isoformat(),
                    "assignments": sum(len(shift.assignments) for shift in shifts),
                    "shortages": shortage_count(shifts),
                    "republish": republish,
                },
            )
        return await self.roster(tenant_id, actor=actor, week_start=week_start)

    async def published(
        self,
        tenant_id: UUID,
        *,
        week_start: datetime.date | None = None,
    ) -> PublishedRosterResponse:
        """The read-only week, OPEN TO EVERY ROLE (D13): the floor board already
        names every colleague, a roster discloses nothing new, and a staffer who
        cannot see the published roster cannot plan.

        ⚠ NEVER A 404 FOR AN UNPUBLISHED WEEK (D6). «No roster yet» is a real,
        renderable answer and a 404 would make the console branch on a status code
        to say it. A DRAFT answers exactly as no roster does — `published: false`,
        an empty list — because a draft is invisible to staff.
        """
        today = today_jerusalem(self._clock)
        current = current_week_start(today)
        target = (
            validate_week_start(week_start) if week_start is not None else default_week_start(today)
        )
        assert_readable_week(target, current=current)
        async with tenant_session(self._sessions, tenant_id) as session:
            roster = await self._rosters.by_week(session, tenant_id, target)
            if roster is None or roster.published_at is None:
                return PublishedRosterResponse(
                    published=False,
                    published_at=None,
                    week_start=target,
                    week_end=week_end(target),
                    shifts=[],
                )
            templates = await self._templates.list_live(session, tenant_id)
            assignments = await self._assignments.by_roster(session, tenant_id, roster.id)
            staff_by_id = {row.id: row for row in await self._staff.list_live(session, tenant_id)}
        return PublishedRosterResponse(
            published=True,
            published_at=roster.published_at,
            week_start=target,
            week_end=week_end(target),
            shifts=[
                self._shift_response(template, assignments, staff_by_id) for template in templates
            ],
        )

    async def _her_published_shifts(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        week_start: datetime.date,
        staff_user_id: UUID,
    ) -> tuple[bool, list[UUID]]:
        """D17's block: whether the week is PUBLISHED, and which shifts are hers.

        ⚠ A DRAFT ANSWERS `(False, [])` EVEN WITH HER ON IT (D6). A draft is
        invisible to staff, and telling her «you work Sunday morning» off a week
        the owner has not published yet is exactly the promise this feature must
        not make.

        ⚠ THE BOOLEAN AND THE LIST ARE BOTH NEEDED, because published-and-empty
        and not-published-at-all are different facts (D5) and the panel says so
        in two different sentences.

        Two statements on the session the week read already holds, and the second
        is skipped entirely when the week is not published.
        """
        roster = await self._rosters.by_week(session, tenant_id, week_start)
        if roster is None or roster.published_at is None:
            return False, []
        rows = await self._assignments.by_staff_and_roster(
            session, tenant_id, roster_id=roster.id, staff_user_id=staff_user_id
        )
        return True, [row.shift_template_id for row in rows]

    # --- shared --------------------------------------------------------------

    def _deadline(
        self, week_start: datetime.date, settings: dict[str, object]
    ) -> datetime.datetime:
        day_of_week, deadline_time = scheduling_pair(settings)
        return deadline_at(week_start, day_of_week=day_of_week, deadline_time=deadline_time)

    def _locked(
        self,
        week_start: datetime.date,
        *,
        current: datetime.date,
        actor: StaffContext,
        resolved_deadline: datetime.datetime,
    ) -> bool:
        """«this actor cannot write this week» — the exact predicate `submit`
        enforces, so the button the panel renders and the request it then sends
        cannot disagree (design F-1)."""
        try:
            assert_writable_week(week_start, current=current)
        except WeekOutOfRangeError:
            return True
        if actor.role in ELEVATED_ROLES:
            return False
        return self._clock() >= resolved_deadline

    async def _recorder_names(
        self, session: AsyncSession, tenant_id: UUID, entries: list[StaffAvailability]
    ) -> dict[UUID, str]:
        """⚠ A REMOVED RECORDER RESOLVES TO NOTHING, and the line simply does not
        render — `floor/service.py`'s `_staff_display_name` rule: «{{name}} כבר
        מגיעה.» with an empty interpolation is worse than a sentence that admits
        it does not know."""
        wanted = {entry.recorded_by for entry in entries if entry.recorded_by is not None}
        resolved: dict[UUID, str] = {}
        for staff_id in wanted:
            row = await self._staff.by_id(session, tenant_id, staff_id)
            if row is not None:
                resolved[staff_id] = row.display_name
        return resolved

    @staticmethod
    def _entry_response(
        row: StaffAvailability, names: dict[UUID, str]
    ) -> AvailabilityEntryResponse:
        return AvailabilityEntryResponse(
            id=row.id,
            shift_template_id=row.shift_template_id,
            state=AvailabilityState(row.state),
            recorded_by_name=None if row.recorded_by is None else names.get(row.recorded_by),
        )

    @staticmethod
    def _authorize(staff_user_id: UUID, actor: StaffContext) -> None:
        """The acting identity is `StaffContext`, resolved from the session cookie
        by `get_current_staff`. It is NEVER read from the body: the request names
        only WHOM to record, never WHO is asking. A body-supplied `staff_user_id`
        doubling as the caller's identity is the one shape that turns "any staffer
        on herself" into "any staffer on anyone".

        Compares IDS. A display name or an email would be a mutable string two
        people can share.
        """
        if staff_user_id != actor.id and actor.role not in ELEVATED_ROLES:
            raise NotAuthorizedError

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


def plan_week_write(
    *,
    existing: Mapping[UUID, tuple[str, UUID | None]],
    requested: Mapping[UUID, AvailabilityState],
    recorded_by: UUID | None,
) -> tuple[list[UUID], list[UUID]]:
    """D11's diff, as a total function: `(to write, to clear)`.

    Four cases, and every one is asserted in `test_shifts_service.py`:

        ADDED      requested, no live row      -> write
        CHANGED    requested, different state  -> write
        REASSIGNED requested, same state but a
                   different `recorded_by`     -> write
        REMOVED    live but not requested      -> clear (D8's soft delete)
        UNCHANGED  same state, same recorder   -> neither

    ⚠ THE `recorded_by` COMPARISON IS NOT DECORATION. A staffer correcting a row
    an elevated actor recorded for her sends the SAME state — and without this
    clause that is "unchanged", the column keeps the stale id, and her own screen
    goes on saying «נרשם על ידי דנה» about an answer she just gave herself.

    The lists drive the write; whether they are BOTH empty drives whether an audit
    row is written at all (the shipped no-op rule).
    """
    changed = [
        template_id
        for template_id, state in requested.items()
        if existing.get(template_id) != (state.value, recorded_by)
    ]
    cleared = [template_id for template_id in existing if template_id not in requested]
    return changed, cleared


def shortage_count(shifts: list[RosterShiftResponse]) -> int:
    """How many shifts are short of a coverage target the owner actually set.

    ⚠ THE SAME PREDICATE THE PANE'S STANDING LINE USES, so the number in the
    publish audit row and the number she was looking at when she pressed the
    button are the same number.

    A role with NO target is never short — an absent key is «no target» and not
    «zero» (D10) — and a missing shift manager is deliberately NOT counted: on a
    fresh boutique nobody is eligible at all, so counting it would park a
    permanent accusation on every screen (design P8).

    Publish never consults this. It is flagged and never blocked (pre-decided
    #40).
    """
    return sum(
        1
        for shift in shifts
        if any(
            shift.assigned_by_role.get(role, 0) < target
            for role, target in shift.coverage_targets.items()
        )
    )


def assert_manager_eligible(staffer: StaffUser, *, is_shift_manager: bool) -> None:
    """D12's gate, as a total function so the whole of it is provable with no
    database in the way.

    ⚠ `shift_manager_eligible` ALONE, AND NEVER `role`. F38 shipped the boolean
    specifically to separate «may be assigned as shift manager» from «her job is
    shift manager» (F38 O4 hands the enforcement here), so a `seamstress` whose
    column is true IS eligible and a `shift_manager` whose column is false is
    NOT. Deriving one from the other deletes the distinction the column was
    created to make, and the deletion is invisible until the day a boutique has
    a shift manager it does not want running a Saturday.
    """
    if is_shift_manager and not staffer.shift_manager_eligible:
        raise NotShiftManagerEligibleError


def override_stamp(submitted_state: str | None, *, acknowledged: bool) -> str | None:
    """What `roster_assignments.override_of_state` gets, if anything (D11).

    Exactly three outcomes, and the middle one is the feature:

        she said `unavailable`, acknowledged      -> stamp it
        she said `unavailable`, NOT acknowledged  -> 409, nothing written
        anything else, INCLUDING no answer at all -> None

    ⚠ NOT-ANSWERED IS NOT AN OVERRIDE (D8's absence-is-not-a-state). A staffer
    with no `staff_availability` row assigns with no ceremony; so does one who
    said `available` or `preferred`. F39 O2 leaves the preferred cap to F40 and
    F40 declines to impose one — a boutique that wants everyone's preferred shift
    honoured does not need the platform to count for it.
    """
    if submitted_state != AvailabilityState.UNAVAILABLE.value:
        return None
    if not acknowledged:
        raise AvailabilityConflictError
    return submitted_state


def is_available_for_week(staffer: StaffUser, *, week_end_date: datetime.date) -> bool:
    """D10: an offboarded staffer is NEVER asked, and never rostered.

    The `deleted_at IS NULL` half is the live one — F38's offboarding sets
    `last_day` and `deleted_at` in one transaction and `UpdateStaffRequest` cannot
    set `last_day` alone, so the second clause never fires TODAY. It is written
    anyway because the day F38's panel gains a "leaving on" field, the silent
    failure is asking a staffer for a week she will not work — and F40 then
    rostering her.

    A Python filter over a single-digit staff list rather than a SQL predicate:
    both readers already hold the rows, and one spelling of the rule is what makes
    it testable in one place.
    """
    return staffer.deleted_at is None and (
        staffer.last_day is None or staffer.last_day >= week_end_date
    )


def _state_counts(states: list[AvailabilityState]) -> dict[str, int]:
    """Per-state counts for the audit row, every member present including the
    zeroes — a reader comparing two rows must not have to guess whether a missing
    key means «none» or «this row predates the member»."""
    return {
        member.value: sum(1 for state in states if state is member) for member in AvailabilityState
    }


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
