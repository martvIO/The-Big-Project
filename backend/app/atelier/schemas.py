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

from pydantic import BaseModel

from app.atelier.stages import stage_of
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
    """A name and a flag. `assignable` is NOT a column — it is a pure function of
    the row (live AND still a seamstress), which is what lets the repository's
    union return the row unchanged and needs no extra type.

    It is on the wire so the console's «תופרת שאינה פעילה» branch is data-driven
    instead of inferred from absence. F42 adds `weekly_capacity_hours` and
    `assigned_minutes` to exactly these objects.
    """

    id: uuid.UUID
    display_name: str
    assignable: bool

    @classmethod
    def from_row(cls, row: StaffUser) -> "SeamstressRef":
        return cls(
            id=row.id,
            display_name=row.display_name,
            assignable=row.deleted_at is None and row.role == StaffRole.SEAMSTRESS.value,
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
        """
        names = {customer.id: customer.name for customer in customers}
        return cls(
            tickets=[
                AtelierTicket.from_row(
                    row, customer_name=names.get(row.customer_id, ""), today=today
                )
                for row in tickets
            ],
            seamstresses=[SeamstressRef.from_row(row) for row in assignees],
            # Iteration over the ENUM and never over the stored mapping, so a
            # hand-edited settings blob cannot put a sixth band on the wire or
            # reorder the five.
            effort_bands=[EffortBandRef(band=band, minutes=bands[band]) for band in EffortBand],
            truncated=truncated,
        )
