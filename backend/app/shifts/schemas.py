"""F39's wire shapes.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=` (the
shipped house form). Every REQUEST model is a `ForbidExtraModel`, so a key the
server does not know is a house-shape 400 rather than a silently ignored field.

**Every list is an ENVELOPE, never a bare array** — `AtelierBoardResponse`'s
rule. F40 will want a coverage number beside a week, and a bare array would make
that a breaking shape change on a screen five staffers open every Sunday.

⚠ **`week_start` / `week_end` are `datetime.date` and `deadline_at` is a
`datetime`.** They are different kinds of thing and the wire says so: a week is a
page of the boutique's calendar (`YYYY-MM-DD`, no offset to get wrong) and a
deadline is an INSTANT (ISO-8601 UTC, `Instant`'s rule). The console's
`plainDayMonth` refuses to meet a `Date` for exactly this reason.
"""

import datetime
import uuid

from pydantic import BaseModel, Field

from app.catalog.validation import MAX_SORT_ORDER
from app.models.constants import AvailabilityState
from app.schemas import ForbidExtraModel
from app.shifts.validation import MAX_SHIFT_LABEL_LENGTH


class ShiftTemplateResponse(BaseModel):
    id: uuid.UUID
    day_of_week: int
    label: str
    starts_at_time: datetime.time
    ends_at_time: datetime.time
    sort_order: int
    # F40 D10's sparse map, on the read so `ShiftTemplatesPane`'s draft can be
    # SEEDED with the existing targets — the PATCH is a full replace, so a draft
    # that did not carry them would clear them on an unrelated label edit.
    coverage_targets: dict[str, int] = Field(default_factory=dict)
    # D4's pre-commit count, and it exists because NO OTHER ROUTE CAN ANSWER IT
    # (design F-2): `invalidated_submissions` lives only in the audit `details` of
    # a write that has already happened, so without this field D4's binding
    # sentence — "the owner's confirm dialog states the count BEFORE she commits"
    # — is unimplementable.
    #
    # `None` for a non-elevated reader: the staffer's own panel has no editor and
    # no confirm dialog, so the aggregate is not run for her at all.
    future_submission_count: int | None = None


class ShiftTemplateListResponse(BaseModel):
    templates: list[ShiftTemplateResponse]


class ShiftTemplateInput(ForbidExtraModel):
    """⚠ A FULL REPLACE of all five editable fields — `UpdateAppointmentTypeRequest`'s
    shipped rule, so an omitted key can never silently clear a value. `sort_order`
    carries a default only on CREATE (the console never shows the field and the
    list orders by `(day, sort_order, starts_at_time)` anyway); the PATCH resends
    the row's existing value.
    """

    day_of_week: int = Field(ge=0, le=6)
    label: str = Field(min_length=1, max_length=MAX_SHIFT_LABEL_LENGTH)
    starts_at_time: datetime.time
    ends_at_time: datetime.time
    # ⚠ BOUNDED, because the column is `INTEGER` and nothing downstream catches
    # the overflow: `validate_template` does not read this field, and asyncpg's
    # «value out of int32 range» arrives as a `DBAPIError`, which no handler in
    # `main.py` maps — so an unbounded value is a 500 with no code the console can
    # render. Same `MAX_SORT_ORDER` every other sort_order on the wire carries
    # (`catalog/schemas.py`, `floor/schemas.py`); F39 was the one that missed it.
    sort_order: int = Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)
    # F40 D10, and the SIXTH REQUIRED FIELD — no default, deliberately. This
    # PATCH is a full replace, so an omitted key would silently clear the targets
    # on every unrelated label edit, and a `default_factory=dict` here is exactly
    # that omission wearing a default's clothes.
    #
    # ⚠ TYPED `object` AND VALIDATED IN `validate_coverage_targets`, not typed
    # `int`. Pydantic would coerce `true` to `1` before the validator ever saw
    # it (F39's `AtelierSettingsUpdate` finding), and it would answer a generic
    # 422 where the console has a specific Hebrew sentence keyed on
    # `COVERAGE_TARGET_INVALID`.
    coverage_targets: dict[str, object]


class TemplateWriteResponse(BaseModel):
    """The answer to the two template writes that INVALIDATE (D4).

    `invalidated_submissions` is the count that really moved, which may differ
    from the `future_submission_count` the confirm dialog predicted if somebody
    submitted in between — so the console announces THIS one and not the
    prediction it opened with.

    `template` is null on DELETE: there is no row left to render, and returning
    the pre-delete one would put a shift back on a screen that just removed it.
    """

    template: ShiftTemplateResponse | None
    invalidated_submissions: int


class SeedTemplatesResponse(BaseModel):
    """`created` is the count the console announces («משמרות שנוצרו משעות
    הפעילות: {{total}}»), and the templates come back in the same payload so the
    pane repopulates without a second read."""

    created: int
    templates: list[ShiftTemplateResponse]


class AvailabilityEntryResponse(BaseModel):
    id: uuid.UUID
    shift_template_id: uuid.UUID
    state: AvailabilityState
    # NULL when she recorded it herself. A NAME, resolved server-side, so the
    # panel never joins staff rows to render one line — and so a shift manager's
    # on-behalf write is visible on the screen it happened to (D5).
    recorded_by_name: str | None = None


class ShiftWeekResponse(BaseModel):
    week_start: datetime.date
    week_end: datetime.date
    deadline_at: datetime.datetime
    # ⚠ ACTOR-RELATIVE, ALWAYS FALSE FOR AN ELEVATED ACTOR (design F-1). D5
    # exempts owner and shift_manager from the deadline entirely, so a `locked`
    # computed from `(setting, week)` alone would be true for an owner past
    # Wednesday 18:00 — the panel would remove her save button and a write D5
    # explicitly permits would become unreachable from the UI while every backend
    # test stayed green. That is precisely the "the page a person reads and the
    # flow she then enters cannot disagree" failure `deposit_due` is cited for.
    locked: bool
    templates: list[ShiftTemplateResponse]
    # HER OWN entries — the ones for `staff_user_id` if the caller named one and
    # is allowed to, otherwise the actor's.
    entries: list[AvailabilityEntryResponse]
    # F40 D17's read-only block on `MyWeekPanel`. ⚠ THREE DISTINCT SENTENCES FOR
    # THREE DISTINCT FACTS (D5), which is why this is a boolean beside a list and
    # not an empty list standing in for both: «the roster is not published yet»,
    # «it is published and you are on no shift» and «here are your shifts» are
    # different things to be told, and the middle one is the one a staffer needs
    # to see before she makes other plans.
    roster_published: bool = False
    rostered_template_ids: list[uuid.UUID] = Field(default_factory=list)


class AvailabilityEntryInput(ForbidExtraModel):
    shift_template_id: uuid.UUID
    state: AvailabilityState


class SubmitAvailabilityRequest(ForbidExtraModel):
    """D11's whole-week replace, in ONE request: entries present are upserted and
    live rows for that (staffer, week) whose template is NOT named are soft-deleted.

    Fifteen taps on a phone become one request, one transaction and one audit row,
    and it maps exactly to the screen — mark the list, tap «שמירה».

    ⚠ `staff_user_id` NAMES WHOM TO RECORD AND NEVER WHO IS ASKING. The acting
    identity comes from the session cookie, always; a body-supplied id doubling as
    the caller's is the one shape that turns "any staffer on herself" into "any
    staffer on anyone" (`floor/service.py:1911-1921` states it). Absent means
    herself.

    An EMPTY `entries` list is legal and means «clear my whole week» — D8's clear
    path, reached from the console by putting every shift back on «לא נרשם».
    """

    week_start: datetime.date
    staff_user_id: uuid.UUID | None = None
    entries: list[AvailabilityEntryInput] = Field(default_factory=list)


class WeekSubmissionRowResponse(BaseModel):
    staff_user_id: uuid.UUID
    display_name: str
    # "At least one live row" (design P8), NOT "answered every template": D8 has
    # no way to distinguish a deliberate blank from a refusal, so the boolean says
    # SHE STARTED and the per-row count says how far she got.
    submitted: bool
    # `AvailabilityEntryResponse`, not a thinner `{template_id, state}` pair
    # (design F-4). The moment a shift manager records on somebody's behalf,
    # `recorded_by` is visible on the staffer's screen — it must be visible on the
    # manager's too, and one type for one thing removes a divergence rather than
    # adding a field.
    entries: list[AvailabilityEntryResponse]


class WeekSubmissionsResponse(BaseModel):
    week_start: datetime.date
    week_end: datetime.date
    submitted_count: int
    total: int
    rows: list[WeekSubmissionRowResponse]


# --- F40: the roster ----------------------------------------------------------


class RosterAssignmentResponse(BaseModel):
    id: uuid.UUID
    staff_user_id: uuid.UUID
    # A NAME, resolved server-side, so the pane never joins staff rows to render
    # a row — `recorded_by_name`'s rule, and the reason `staff[]` and `shifts[]`
    # can be read independently by the client.
    display_name: str
    role: str
    is_shift_manager: bool
    # NON-NULL = she was assigned against what she had submitted (D11). Stamped
    # at assignment time and never updated: a staffer who goes unavailable AFTER
    # she was rostered is a DIFFERENT fact, rendered from her live
    # `RosterStaffRef.states` entry instead (design F-5). Both are on the wire
    # and neither overwrites the other.
    override_of_state: AvailabilityState | None = None


class RosterShiftResponse(BaseModel):
    """One shift of one week, with everybody on it.

    ⚠ THE UNIT BOTH ASSIGNMENT ROUTES ANSWER WITH, never the whole week (plan
    §0.1). A whole-week payload per tap is the obvious shape and it breaks under
    the pane's deliberate per-control concurrency: two writes in flight from one
    dialog, the earlier-issued response arriving second, and the later assignment
    silently lost.
    """

    template: ShiftTemplateResponse
    assignments: list[RosterAssignmentResponse]
    # SPARSE, keyed by `StaffRole` (D10). A missing key is «no target» and renders
    # as a plain count; `0` is «deliberately nobody» and renders as a target.
    coverage_targets: dict[str, int]
    # Server-computed so the pane's shortage line and the server's own shortage
    # count in the publish audit row cannot disagree about one shift.
    assigned_by_role: dict[str, int]


class RosterStaffRefResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    role: str
    # D12's gate, on the wire so the dialog can render the manager control for
    # exactly the women the server would accept.
    shift_manager_eligible: bool
    # By `shift_template_id`. An ABSENT key is «not answered» (D8's
    # absence-is-not-a-state) and is NOT a fourth state — the console renders it
    # as «לא נרשם», F39's per-shift word.
    states: dict[str, AvailabilityState]


class RosterWeekResponse(BaseModel):
    """The builder's payload. ELEVATED — it carries every colleague's submitted
    state, which is F39's own reason for gating `/shifts/week/submissions`."""

    week_start: datetime.date
    week_end: datetime.date
    # NULL = draft (D6). An ISO-8601 UTC instant when it is not.
    published_at: datetime.datetime | None
    published_by_name: str | None
    # D7: edits after a publish take effect immediately and do NOT move
    # `published_at`, so the pane says so in one muted line rather than pretending
    # the week is locked. Computed from the SAME repository predicate publish's
    # no-op branch uses, so the line and the button cannot disagree.
    edited_since_publish: bool
    shifts: list[RosterShiftResponse]
    staff: list[RosterStaffRefResponse]


class PublishedRosterResponse(BaseModel):
    """The read-only week, open to every role.

    ⚠ NEVER A 404 FOR AN UNPUBLISHED WEEK (D6). «No roster yet» is a real,
    renderable answer — `{published: false, shifts: []}` — and a 404 would make
    the console branch on a status code to say it.
    """

    published: bool
    published_at: datetime.datetime | None
    week_start: datetime.date
    week_end: datetime.date
    shifts: list[RosterShiftResponse]


class CreateAssignmentRequest(ForbidExtraModel):
    """⚠ AN UPSERT ON THE LIVE `(roster, template, staffer)` TRIPLE (design F-2),
    which is why it answers 200 on both paths and not 201 on one of them. A route
    that is sometimes a create and sometimes an update, answering two codes,
    forces the client to branch on a status to decide what it just did.

    `acknowledge_override` is required to be `true` ONLY when the live
    `staff_availability` row for that (staffer, template, week) says
    `unavailable` — else `409 AVAILABILITY_CONFLICT`. An override is always a
    second, deliberate act, never a slip (D11).
    """

    week_start: datetime.date
    shift_template_id: uuid.UUID
    staff_user_id: uuid.UUID
    is_shift_manager: bool = False
    acknowledge_override: bool = False


class PublishRosterRequest(ForbidExtraModel):
    """Idempotent (D7). A publish on a week whose assignment set has not moved
    since the stamp writes nothing and audits nothing, and answers 200 with the
    same payload. THERE IS NO UNPUBLISH."""

    week_start: datetime.date
