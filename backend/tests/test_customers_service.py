"""F53 CustomersService against fake repositories — no Postgres, so this suite
runs in the fast local pass.

**Two claims here are the ones a reviewer should check first.**

The no-op rule (D8): a PATCH whose fields did not actually move writes no
UPDATE and — the half that matters — NO AUDIT ROW. Tags are normalized BEFORE
the diff, so a chip list the owner did not edit is a no-op rather than a write
plus an audit row claiming something changed.

The PATCH answers a FULLY BUILT detail (D6), on the write path and the no-op
path alike, because the console does `setDetail(updated)` unconditionally. A
handler that reasoned "the mutation touches `customers` only" and answered
`bookings: []` / `messages: []` would blank both panels the instant the owner
pressed «שמירה». `_build_detail` is one private method precisely so the two
paths cannot disagree; the assertions below are what fail if it stops being.

The audit payload carries FIELD NAMES ONLY. `test_the_audit_row_carries_no_note
_text_no_tag_string_and_no_identity` is the value walk — a `repr` over every
recorded `details`, the `test_staff_management_db.py:604-606` shape moved into a
fast module because this is where a bride's free text would leak.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Self

import pytest

from app.auth.service import StaffContext
from app.customers.schemas import CustomerDetail, SmsLogRow
from app.customers.service import CustomerNotFoundError, CustomersService
from app.customers.validation import (
    BOOKING_HISTORY_LIMIT,
    CUSTOMER_LIST_MAX_LIMIT,
    MAX_CUSTOMER_NOTES_LENGTH,
    MAX_LIST_OFFSET,
    CustomerValidationError,
)
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingStatus, MessageKind, MessageStatus, StaffRole
from app.models.customer import Customer
from app.models.message_log import MessageLog

TENANT_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
OWNER_ID = uuid.uuid4()
PHONE = "+972501234567"
NAME = "מיכל לוי"
NOTES = "מגיעה עם אמא"
TAG = "VIP-סודי"
STARTS_AT = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def _customer(*, notes: str | None = None, tags: list[str] | None = None) -> Customer:
    return Customer(
        id=CUSTOMER_ID,
        tenant_id=TENANT_ID,
        phone=PHONE,
        name=NAME,
        notes=notes,
        tags=tags if tags is not None else [],
    )


def _booking() -> Booking:
    return Booking(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        customer_id=CUSTOMER_ID,
        appointment_type_id=uuid.uuid4(),
        starts_at=STARTS_AT,
        seat_index=1,
        status=BookingStatus.CANCELLED.value,
        terms_version_accepted=1,
        terms_accepted_at=STARTS_AT,
        appointment_type_name="מדידה ראשונה",
        dress_name="שמלה 12",
        dress_size="38",
        notes="הערה על ההזמנה",
    )


def _message() -> MessageLog:
    """Carries the two columns D4 refuses to publish, populated with sentinels:
    `SmsLogRow` has no slot for either, and the mapping is the only place that
    could grow one."""
    return MessageLog(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        phone=PHONE,
        kind=MessageKind.CONFIRMATION.value,
        body="הפגישה שלך אושרה",
        status=MessageStatus.SENT.value,
        provider_message_id="SM-provider-correlation-handle",
        error="Twilio 30003 unreachable destination",
        created_at=STARTS_AT,
    )


def _actor() -> StaffContext:
    return StaffContext(
        id=OWNER_ID,
        tenant_id=TENANT_ID,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


class FakeSession:
    """Enough AsyncSession to satisfy tenant_session — the test_staff_service.py
    shape: an async context manager whose begin() is another one."""

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def begin(self) -> Self:
        return self

    async def execute(self, statement: object, params: object = None) -> None:
        return None


class FakeCustomersRepository:
    def __init__(self, row: Customer | None) -> None:
        self.row = row
        self.page: list[Customer] = []
        self.total = 0
        self.searches: list[dict[str, Any]] = []
        self.writes: list[dict[str, Any]] = []

    async def by_id(
        self, session: object, tenant_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Customer | None:
        return self.row if self.row is not None and self.row.id == customer_id else None

    async def search(
        self,
        session: object,
        tenant_id: uuid.UUID,
        *,
        q: str | None,
        offset: int,
        limit: int,
    ) -> list[Customer]:
        self.searches.append({"q": q, "offset": offset, "limit": limit})
        return self.page

    async def count_search(self, session: object, tenant_id: uuid.UUID, *, q: str | None) -> int:
        return self.total

    async def set_notes_and_tags(
        self,
        session: object,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> Customer | None:
        self.writes.append({"customer_id": customer_id, "notes": notes, "tags": tags})
        if self.row is None:
            return None
        if notes is not None:
            self.row.notes = notes
        if tags is not None:
            self.row.tags = tags
        return self.row


class FakeBookingsRepository:
    def __init__(self) -> None:
        self.rows = [_booking()]
        self.calls: list[dict[str, Any]] = []

    async def list_recent_for_customer(
        self, session: object, tenant_id: uuid.UUID, *, customer_id: uuid.UUID, limit: int
    ) -> list[Booking]:
        self.calls.append({"customer_id": customer_id, "limit": limit})
        return self.rows


class FakeMessageLogRepository:
    def __init__(self) -> None:
        self.rows = [_message()]
        self.total = 97
        self.calls: list[dict[str, Any]] = []

    async def list_for_customer(
        self, session: object, tenant_id: uuid.UUID, customer_id: uuid.UUID, *, phone: str
    ) -> list[MessageLog]:
        self.calls.append({"customer_id": customer_id, "phone": phone})
        return self.rows

    async def count_for_customer(
        self, session: object, tenant_id: uuid.UUID, customer_id: uuid.UUID, *, phone: str
    ) -> int:
        return self.total


class FakeAuditRepository:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def record(self, session: object, **kwargs: Any) -> None:
        self.rows.append(kwargs)


def _service(
    row: Customer | None,
) -> tuple[
    CustomersService,
    FakeCustomersRepository,
    FakeBookingsRepository,
    FakeMessageLogRepository,
    FakeAuditRepository,
]:
    service = CustomersService(lambda: FakeSession())  # type: ignore[arg-type]
    customers = FakeCustomersRepository(row)
    bookings = FakeBookingsRepository()
    messages = FakeMessageLogRepository()
    audit = FakeAuditRepository()
    service._customers = customers  # type: ignore[assignment]
    service._bookings = bookings  # type: ignore[assignment]
    service._messages = messages  # type: ignore[assignment]
    service._audit = audit  # type: ignore[assignment]
    return service, customers, bookings, messages, audit


def _assert_panels_are_populated(detail: CustomerDetail) -> None:
    """The anti-vacuity half of every PATCH assertion below. `bookings == []`
    and `messages == []` is exactly what a response built from the `customers`
    row alone looks like, and it is indistinguishable from a correct one unless
    the fake holds something."""
    assert [row.appointment_type_name for row in detail.bookings] == ["מדידה ראשונה"]
    assert [row.body for row in detail.messages] == ["הפגישה שלך אושרה"]
    assert detail.messages_total == 97


# --- the list ---


async def test_the_list_maps_rows_and_echoes_the_page_it_actually_read() -> None:
    service, customers, _, _, _ = _service(None)
    customers.page = [_customer(tags=["VIP"])]
    customers.total = 3

    answer = await service.list_customers(TENANT_ID, q=" מיכל ", offset=10, limit=20)

    assert [(row.name, row.phone, row.tags) for row in answer.items] == [(NAME, PHONE, ["VIP"])]
    assert (answer.total, answer.offset, answer.limit) == (3, 10, 20)
    assert customers.searches == [{"q": " מיכל ", "offset": 10, "limit": 20}]


async def test_the_page_bounds_are_clamped_below_the_routers_own_bounds() -> None:
    """`booking/owner.py:52-58`'s rule restated: `offset` binds into
    `OFFSET $n::BIGINT`, so an unbounded int from a NON-router caller dies in
    asyncpg's int8_encode as a 500 rather than as a 400."""
    service, customers, _, _, _ = _service(None)

    answer = await service.list_customers(
        TENANT_ID, q=None, offset=MAX_LIST_OFFSET * 9, limit=CUSTOMER_LIST_MAX_LIMIT * 9
    )

    assert customers.searches == [
        {"q": None, "offset": MAX_LIST_OFFSET, "limit": CUSTOMER_LIST_MAX_LIMIT}
    ]
    assert (answer.offset, answer.limit) == (MAX_LIST_OFFSET, CUSTOMER_LIST_MAX_LIMIT)


# --- the detail, and the one private builder both paths go through ---


async def test_the_detail_reads_the_log_by_the_customers_current_phone() -> None:
    service, _, bookings, messages, _ = _service(_customer(notes=NOTES, tags=["VIP"]))

    detail = await service.detail(TENANT_ID, CUSTOMER_ID)

    assert (detail.id, detail.name, detail.phone) == (CUSTOMER_ID, NAME, PHONE)
    assert (detail.notes, detail.tags) == (NOTES, ["VIP"])
    _assert_panels_are_populated(detail)
    assert bookings.calls == [{"customer_id": CUSTOMER_ID, "limit": BOOKING_HISTORY_LIMIT}]
    assert messages.calls == [{"customer_id": CUSTOMER_ID, "phone": PHONE}]


async def test_an_unknown_customer_is_a_domain_404_and_writes_nothing() -> None:
    """Unknown, soft-deleted and another tenant's id are one indistinguishable
    miss — the repository answers `None` for all three."""
    service, customers, _, _, audit = _service(None)

    with pytest.raises(CustomerNotFoundError):
        await service.detail(TENANT_ID, CUSTOMER_ID)
    with pytest.raises(CustomerNotFoundError):
        await service.update(TENANT_ID, CUSTOMER_ID, notes="x", tags=None, actor=_actor())

    assert customers.writes == []
    assert audit.rows == []


async def test_the_sms_row_carries_five_fields_and_neither_fenced_column() -> None:
    """The mapping boundary, with a real MessageLog carrying both sentinels.
    `error` is fenced by a shipped comment on the column itself — "never reaches
    a response body" — and `provider_message_id` is an operator's Twilio
    correlation handle that means nothing to a boutique owner."""
    service, _, _, _, _ = _service(_customer())

    detail = await service.detail(TENANT_ID, CUSTOMER_ID)

    assert set(SmsLogRow.model_fields) == {"id", "created_at", "kind", "status", "body"}
    dumped = detail.messages[0].model_dump()
    assert "provider_message_id" not in dumped
    assert "error" not in dumped
    assert "SM-provider-correlation-handle" not in repr(dumped)
    assert "Twilio 30003" not in repr(dumped)


# --- the no-op rule (D8) ---


async def test_a_patch_that_moves_nothing_writes_no_update_and_no_audit_row() -> None:
    service, customers, _, _, audit = _service(_customer(notes=NOTES, tags=["VIP"]))

    detail = await service.update(TENANT_ID, CUSTOMER_ID, notes=NOTES, tags=["VIP"], actor=_actor())

    assert customers.writes == []
    assert audit.rows == []
    assert (detail.notes, detail.tags) == (NOTES, ["VIP"])
    # The no-op path is a full detail too: the console does setDetail(updated)
    # whatever the server decided not to write.
    _assert_panels_are_populated(detail)


async def test_tags_are_normalized_before_the_diff() -> None:
    """`[" VIP ", "VIP"]` trims to `["VIP"]` and dedups to one element, which is
    exactly what is stored. Diffing the RAW input instead would write an UPDATE
    and an audit row claiming something changed, on every save of an unedited
    chip list — the console posts what its editor holds, whitespace and all.

    ⚠ The plan's worked example for this rule is `["vip"]` against a stored
    `["VIP"]`, and that one is NOT a no-op: `normalize_tags` dedups
    case-insensitively but KEEPS THE FIRST OCCURRENCE'S CASING (pinned in
    test_customers_validation.py), so `["vip"]` normalizes to `["vip"]` and
    differs from what is stored. Making it a no-op would need a casefolded diff,
    which would silently discard an owner deliberately re-casing a chip and
    leave her screen showing the old spelling after a successful save.
    """
    service, customers, _, _, audit = _service(_customer(tags=["VIP"]))

    await service.update(TENANT_ID, CUSTOMER_ID, notes=None, tags=[" VIP ", "VIP"], actor=_actor())

    assert customers.writes == []
    assert audit.rows == []


async def test_recasing_a_tag_is_a_real_edit_and_is_written() -> None:
    """The other half of the paragraph above, asserted rather than argued: the
    owner's chosen spelling is the value, so `["vip"]` over `["VIP"]` moves."""
    service, customers, _, _, audit = _service(_customer(tags=["VIP"]))

    detail = await service.update(TENANT_ID, CUSTOMER_ID, notes=None, tags=["vip"], actor=_actor())

    assert customers.writes == [{"customer_id": CUSTOMER_ID, "notes": None, "tags": ["vip"]}]
    assert [row["details"] for row in audit.rows] == [{"fields": ["tags"]}]
    assert detail.tags == ["vip"]


async def test_a_field_left_unsupplied_is_never_compared_and_never_written() -> None:
    """`None` means NOT SUPPLIED. A tags-only patch must leave notes alone —
    the console's notes box and its chips are two independent controls."""
    service, customers, _, _, audit = _service(_customer(notes=NOTES, tags=["VIP"]))

    await service.update(TENANT_ID, CUSTOMER_ID, notes=None, tags=["כלה"], actor=_actor())

    assert customers.writes == [{"customer_id": CUSTOMER_ID, "notes": None, "tags": ["כלה"]}]
    assert [row["details"] for row in audit.rows] == [{"fields": ["tags"]}]


# --- the audit row (D8) ---


async def test_both_fields_moving_is_one_row_whose_field_list_is_sorted() -> None:
    service, customers, _, _, audit = _service(_customer())

    detail = await service.update(TENANT_ID, CUSTOMER_ID, notes=NOTES, tags=[TAG], actor=_actor())

    assert len(audit.rows) == 1
    row = audit.rows[0]
    assert row["action"] == AuditAction.CUSTOMER_UPDATED
    assert row["actor_id"] == OWNER_ID
    assert row["entity"] == str(CUSTOMER_ID)
    assert row["details"] == {"fields": ["notes", "tags"]}
    assert customers.writes == [{"customer_id": CUSTOMER_ID, "notes": NOTES, "tags": [TAG]}]
    assert (detail.notes, detail.tags) == (NOTES, [TAG])
    # The write path answers the same fully-built detail the read does. This is
    # the assertion that fails if update() builds its response from the
    # `customers` row alone.
    _assert_panels_are_populated(detail)


async def test_the_audit_row_carries_no_note_text_no_tag_string_and_no_identity() -> None:
    """The value walk. F51's STAFF_UPDATED ships {from, to} and is right to —
    a display name is a label a staffer chose for herself. Customer notes are
    free text about a third party who never sees them, `audit_log` has no
    retention policy, and platform operators read across tenants."""
    service, _, _, _, audit = _service(_customer())

    await service.update(TENANT_ID, CUSTOMER_ID, notes=NOTES, tags=[TAG], actor=_actor())

    rendered = repr([row["details"] for row in audit.rows])
    assert NOTES not in rendered
    assert TAG not in rendered
    assert NAME not in rendered
    assert PHONE not in rendered


# --- validation runs before anything is written ---


@pytest.mark.parametrize(
    ("notes", "tags"),
    [
        ("x" * (MAX_CUSTOMER_NOTES_LENGTH + 1), None),
        ("שורה\x0bעם בקרה", None),
        (None, ["טוב", "רע\x00"]),
        (None, [f"tag-{index}" for index in range(11)]),
    ],
)
async def test_a_refused_field_reaches_neither_the_update_nor_the_audit_row(
    notes: str | None, tags: list[str] | None
) -> None:
    service, customers, _, _, audit = _service(_customer())

    with pytest.raises(CustomerValidationError):
        await service.update(TENANT_ID, CUSTOMER_ID, notes=notes, tags=tags, actor=_actor())

    assert customers.writes == []
    assert audit.rows == []
