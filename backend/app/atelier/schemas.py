"""The atelier's wire shapes, and the pure fold from rows to the board envelope.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=` (the
shipped house form). Every REQUEST model is a `ForbidExtraModel`, so a key the
server does not know is a house-shape 400 rather than a silently ignored field —
which is what makes "the client can never send `effort_minutes`" an assertion
instead of a hope.

**The board is an ENVELOPE, never a bare array.** F42 adds capacity to
`seamstresses`, F43 adds fitting counts to a ticket, and a bare array would make
the first of those a breaking shape change on a screen that polls every five
seconds.

**The fold is here rather than in the service** for the same reason
`StaffCard.from_row` is in `floor/schemas.py`: it is a total function of a row, a
name and a date, so it runs in the fast suite with no Postgres and no fakes.
`test_atelier_board.py` is its whole proof.
"""

import datetime
import uuid
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, Field, StrictInt

from app.atelier.stages import MAX_WEEKLY_CAPACITY_HOURS, resolve_capacity, stage_of
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import EffortBand, StaffRole, TicketStage
from app.models.customer import Customer
from app.models.staff_user import StaffUser
from app.schemas import ForbidExtraModel


class CreateTicketRequest(ForbidExtraModel):
    """Intake. The bride is identified by NAME AND PHONE, never by a
    `customer_id`: F53's customer picker is gated `require_role(OWNER,
    SHIFT_MANAGER)` while this route admits a seamstress, so a picker she could
    never load is not an identification path for the role that most needs one.
    The server resolves `(tenant, phone)` through `CustomersRepository.upsert`.

    `effort_band` is one of the five KEYS and never a number — that is what makes
    "five preset bands, not a minute field" a structural property of the wire
    rather than a UI convention. The server resolves it to minutes from the
    tenant's settings and the row stores the minutes.

    `dress_name` is free text and is legal ONLY when `dress_id` is null: an
    alteration is frequently on a gown the bride already owns, which has no
    catalog row at all. When `dress_id` IS given the SERVER copies
    `dresses.name`, so the snapshot cannot disagree with the row it was taken
    from.
    """

    customer_name: str
    customer_phone: str
    due_date: datetime.date
    effort_band: EffortBand
    assigned_staff_user_id: uuid.UUID | None = None
    dress_id: uuid.UUID | None = None
    dress_name: str | None = None
    dress_size: str | None = None
    notes: str | None = None


class UpdateTicketRequest(ForbidExtraModel):
    """⚠ A FULL REPLACE: every editable field is REQUIRED, with no default
    anywhere in this model. `UpdateAppointmentTypeRequest`'s shipped rule, and
    the reason is that with optional fields an OMITTED key and an explicitly
    cleared one are the same request — so a console that forgets to send
    `notes` silently deletes a bride's measurements.

    The CUSTOMER is not editable: a ticket opened for the wrong bride is a delete
    and a re-open, not an edit that silently re-points a garment at someone else.
    The five STAMPS are not editable either — a stage moves by its own verb,
    under its own predicate.
    """

    due_date: datetime.date
    effort_band: EffortBand
    dress_id: uuid.UUID | None
    dress_name: str | None
    dress_size: str | None
    notes: str | None


class AssignTicketRequest(ForbidExtraModel):
    """`null` RELEASES, and it is a value rather than an omission — which is why
    the field carries no default. An optional `staff_user_id` would make a
    malformed request that dropped the key indistinguishable from a deliberate
    release."""

    staff_user_id: uuid.UUID | None


class StageRequest(ForbidExtraModel):
    """The stage to ENTER on advance, and the stage to CLEAR on undo.

    The client names it from what its LAST POLL showed, and that is what makes a
    stale board harmless: if the ticket moved on between the paint and the tap,
    the write's predicate fails and the caller gets a 409 rather than stamping —
    or clearing — a stage that arrived after it last looked.
    """

    stage: TicketStage


class AtelierTicket(BaseModel):
    """One card. Every mutation answers this, not `{ok: true}`, so the console
    patches its card from the SERVER's own row and cannot disagree with itself —
    and on a 200 no-op that renders the FIRST actor's timestamp rather than this
    request's intent.

    `customer_name` ships and `customer_phone` does NOT (D6). The board is read
    by a seamstress and there is no surface in F41 that calls a bride; that is
    F43's fitting booking, riding F16's shipped comms.
    """

    id: uuid.UUID
    customer_name: str
    due_date: datetime.date
    # Computed on read against `today_jerusalem`, NEVER stored. A stored boolean
    # would need a worker to flip it at Jerusalem midnight, would be stale for up
    # to a tick, and would race a concurrent delivery.
    overdue: bool
    effort_minutes: int
    assigned_staff_user_id: uuid.UUID | None
    dress_id: uuid.UUID | None
    dress_name: str | None
    dress_size: str | None
    notes: str | None
    # DERIVED: the rightmost stamped column of the five below (D2). There is no
    # status column and deliberately not.
    stage: TicketStage
    intake_at: datetime.datetime | None
    in_progress_at: datetime.datetime | None
    qc_at: datetime.datetime | None
    ready_at: datetime.datetime | None
    delivered_at: datetime.datetime | None

    @classmethod
    def from_row(
        cls, row: AlterationTicket, *, customer_name: str, today: datetime.date
    ) -> "AtelierTicket":
        return cls(
            id=row.id,
            customer_name=customer_name,
            due_date=row.due_date,
            # `delivered_at IS NOT NULL` cancels it: a garment delivered late is
            # a fact about the past, not a thing to chase.
            overdue=row.delivered_at is None and row.due_date < today,
            effort_minutes=row.effort_minutes,
            assigned_staff_user_id=row.assigned_staff_user_id,
            dress_id=row.dress_id,
            dress_name=row.dress_name,
            dress_size=row.dress_size,
            notes=row.notes,
            stage=stage_of(row),
            intake_at=row.intake_at,
            in_progress_at=row.in_progress_at,
            qc_at=row.qc_at,
            ready_at=row.ready_at,
            delivered_at=row.delivered_at,
        )


class SeamstressRef(BaseModel):
    """A name, a flag, her capacity and her two load sums. `assignable` is NOT a
    column — it is a pure function of the row (live AND still a seamstress),
    which is what lets the repository's union return the row unchanged and needs
    no extra type.

    It is on the wire so the console's «תופרת שאינה פעילה» branch is data-driven
    instead of inferred from absence.

    **F42's four fields, and why it is four and not F41's predicted two.**
    `weekly_capacity_hours` is RESOLVED (D2) — her own column, else the tenant
    default, else `null`, which is a real answer meaning "no bar".
    `capacity_is_default` is the third because the resolved number and her own
    column are DIFFERENT FACTS: the panel must not present an inherited number as
    hers, and the editor must be able to tell "clear back to the default" from
    "set to the same number". `due_soon_minutes` is the fourth for D3's
    dimensional argument — the bar's numerator needs the denominator's units,
    while `assigned_minutes` keeps the whole undelivered queue on the wire under
    its own name.

    ⚠ `assignable` IS STILL DERIVED FROM THE ROW AND F42 DOES NOT TOUCH IT. A
    retired seamstress with live tickets therefore ships `assignable: false`, a
    real `assigned_minutes` and whatever capacity resolves — F41's Risk 9.2
    anomalous bucket, now carrying a number.
    """

    id: uuid.UUID
    display_name: str
    assignable: bool
    weekly_capacity_hours: int | None
    capacity_is_default: bool
    assigned_minutes: int
    due_soon_minutes: int

    @classmethod
    def from_row(
        cls,
        row: StaffUser,
        *,
        load: Mapping[uuid.UUID | None, tuple[int, int]],
        tenant_default: int | None,
    ) -> "SeamstressRef":
        # ⚠ `.get(..., (0, 0))` AND NOT `load[row.id]`. D3's aggregate has no
        # `HAVING` and no zero rows — a seamstress holding nothing is simply not
        # a group — so the default is the only thing keeping her on the panel
        # with an empty bar instead of 500ing a five-second poll.
        due_soon_minutes, assigned_minutes = load.get(row.id, (0, 0))
        hours, is_default = resolve_capacity(row, tenant_default)
        return cls(
            id=row.id,
            display_name=row.display_name,
            assignable=row.deleted_at is None and row.role == StaffRole.SEAMSTRESS.value,
            weekly_capacity_hours=hours,
            capacity_is_default=is_default,
            assigned_minutes=assigned_minutes,
            due_soon_minutes=due_soon_minutes,
        )


class SetCapacityRequest(ForbidExtraModel):
    """Her weekly hours, or `null` to CLEAR them back to the boutique's default.

    REQUIRED with no schema default, `AssignTicketRequest.staff_user_id`'s rule:
    `null` is a VALUE and an optional field would make a malformed request that
    dropped the key indistinguishable from a deliberate clear.

    ⚠ `StrictInt`, NOT `int`, AND THE BOUND IS VACUOUS WITHOUT IT.
    `ForbidExtraModel` sets `extra="forbid"` and NOTHING else (`app/schemas.py:13-18`
    — there is no `strict=True` on it), so a plain `int` COERCES before any bound
    is checked: `true` becomes `1`, lands inside `0..168`, and is accepted as a
    ONE-HOUR WEEK for a seamstress who works forty. `"24"` and `24.0` go the same
    way. The refusal surfaces as VALIDATION_ERROR through `main.py:936`.
    """

    weekly_capacity_hours: StrictInt | None = Field(ge=0, le=MAX_WEEKLY_CAPACITY_HOURS)


class SeamstressCapacityResponse(BaseModel):
    """Capacity facts only — the answer to D6's write.

    ⚠ IT IS NOT A `SeamstressRef`, and that is the whole point. `SeamstressRef`
    requires `assigned_minutes` and `due_soon_minutes`; this path has no
    aggregate (D3's is a board read inside the poll's session) and buying one
    would be a second business statement on a write. The only value reachable
    without it is `(0, 0)` — which would collapse her bar and drop her «עומס יתר»
    word for up to five seconds on this feature's own primary surface, at the
    moment a manager is looking at it. The console is already holding both
    numbers from the last tick and patches only the keys below.
    """

    id: uuid.UUID
    display_name: str
    assignable: bool
    # RESOLVED (D2) — her column, else the tenant default, else null — and read
    # back through `_refreshed`, so it is the DATABASE's answer and not this
    # caller's intent.
    weekly_capacity_hours: int | None
    capacity_is_default: bool

    @classmethod
    def from_row(
        cls, row: StaffUser, *, tenant_default: int | None
    ) -> "SeamstressCapacityResponse":
        hours, is_default = resolve_capacity(row, tenant_default)
        return cls(
            id=row.id,
            display_name=row.display_name,
            # `SeamstressRef.from_row`'s predicate, spelled again rather than
            # shared: that model's constructor takes the two load numbers this
            # path deliberately has no source for.
            assignable=row.deleted_at is None and row.role == StaffRole.SEAMSTRESS.value,
            weekly_capacity_hours=hours,
            capacity_is_default=is_default,
        )


class EffortBandRef(BaseModel):
    band: EffortBand
    minutes: int


class AtelierBoardResponse(BaseModel):
    tickets: list[AtelierTicket]
    seamstresses: list[SeamstressRef]
    effort_bands: list[EffortBandRef]
    # The ceiling bit. `BOARD_TICKET_LIMIT` is SERVER-ONLY and no client constant
    # mirrors it — this flag is precisely why the console never has to know the
    # number.
    truncated: bool
    # The NULL group of D3's aggregate: work nobody holds. It is the UNFILTERED
    # sum (F-3) — no bar means no rate, so there is nothing to narrow to a week
    # and the panel states it in words.
    unassigned_minutes: int
    # Off `TenantContext.settings`, zero statements. On the envelope so the
    # settings dialog opens with no read of its own, and so the panel can say
    # whose default an inherited number is.
    default_weekly_capacity_hours: int | None
    # ⚠ THE HORIZON D3 FILTERED ON, BECAUSE THE CLIENT CANNOT COMPUTE IT (F-1).
    # `lib/jerusalem.ts` ships six formatters and zero date arithmetic, and a
    # client that invented `new Date() + 7` would print a date in the BROWSER's
    # zone against a filter the SERVER ran in Jerusalem's.
    due_soon_through: datetime.date

    @classmethod
    def build(
        cls,
        *,
        tickets: Sequence[AlterationTicket],
        customers: Sequence[Customer],
        assignees: Sequence[StaffUser],
        bands: Mapping[EffortBand, int],
        truncated: bool,
        today: datetime.date,
        load: Mapping[uuid.UUID | None, tuple[int, int]],
        default_capacity_hours: int | None,
        due_soon_through: datetime.date,
    ) -> "AtelierBoardResponse":
        """⚠ NAMES ARE JOINED BY ID AND THE ORDER IS THE DATABASE'S.

        The two sequences arrive in different orders — tickets by `due_date,
        created_at, id`, customers in whatever the `IN` returned — so a
        positional zip would render one bride's name on another bride's garment.
        And the fold re-sorts nothing: a second ordering here would be a second
        thing to keep in step, and the one the console sees would stop being the
        one the truncation boundary was computed against.

        A ticket whose customer row is absent renders an empty name rather than
        dropping off the board. No shipped writer sets `customers.deleted_at`, so
        that is unreachable today — it exists so F20's retention scrub cannot
        take a garment that is physically in the workroom off the board, or 500 a
        five-second poll.

        ⚠ AND THE SEAMSTRESSES ARE NOT RE-SORTED EITHER, THOUGH D10 SORTS THEM ON
        SCREEN. `assignees()` answers `display_name, id` and that order travels
        untouched; the panel and the assign `<Select>` order by REMAINING
        CAPACITY in `lib/capacity.ts`. Sorting here would be a second ordering
        computed from the same three numbers, and the two would diverge the first
        time either changed. The numbers travel; the ordering is a rendering
        decision.
        """
        names = {customer.id: customer.name for customer in customers}
        return cls(
            tickets=[
                AtelierTicket.from_row(
                    row, customer_name=names.get(row.customer_id, ""), today=today
                )
                for row in tickets
            ],
            seamstresses=[
                SeamstressRef.from_row(row, load=load, tenant_default=default_capacity_hours)
                for row in assignees
            ],
            # Iteration over the ENUM and never over the stored mapping, so a
            # hand-edited settings blob cannot put a sixth band on the wire or
            # reorder the five.
            effort_bands=[EffortBandRef(band=band, minutes=bands[band]) for band in EffortBand],
            truncated=truncated,
            # ⚠ THE SECOND MEMBER — the UNFILTERED sum (F-3).
            unassigned_minutes=load.get(None, (0, 0))[1],
            default_weekly_capacity_hours=default_capacity_hours,
            due_soon_through=due_soon_through,
        )
