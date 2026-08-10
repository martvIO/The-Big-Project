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
    sort_order: int = 0


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
