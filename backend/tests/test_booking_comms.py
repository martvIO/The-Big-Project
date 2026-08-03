"""F19 A4: MD2's SMS — the fifth body, its budget, and the public send that the
honour path's alert branch calls.

Fast by construction. The body is a constant, so its copy constraints are
assertable with no I/O at all; the send is exercised only on the branch that
returns BEFORE touching a session, which is the one branch `notify_owner_cancel`
also has and the only one provable without Postgres. The delivery itself is
proved in `test_deposit_confirm_db.py`.

The three copy assertions are not decoration. MD2's body is the ONLY thing the
bride hears on a path where her money already moved, and it was approved on
exactly three promises it does not make: no refund, no new time, and no claim
that anything has already been done. A body edit that quietly adds one of those
is a false promise the product cannot keep — the same failure mode as the
shipped `cancelConsequenceFree` sentence MD3 exists to remove.
"""

import datetime
import uuid
from typing import Any

from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.comms_templates import (
    PAYMENT_RECEIVED_NO_SLOT_BODY,
    PAYMENT_RECEIVED_NO_SLOT_MAX_SEGMENTS,
    ucs2_segments,
)
from app.models.booking import Booking
from app.models.constants import MessageKind

TENANT = CommsTenant(id=uuid.uuid4(), slug="bella", name="בלה כלות", phone="052-1234567")


class _Unconfigured:
    """F11's pre-provider posture: `send_sms` raises before any insert, so the
    service must not reach it — and must not open a session either."""

    is_configured = False

    async def send_sms(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("send_sms must not be reached when no provider is configured")


def _booking() -> Booking:
    return Booking(
        id=uuid.uuid4(),
        tenant_id=TENANT.id,
        customer_id=uuid.uuid4(),
        appointment_type_id=uuid.uuid4(),
        starts_at=datetime.datetime(2099, 1, 1, 8, 0, tzinfo=datetime.UTC),
        seat_index=1,
    )


def _service() -> BookingCommsService:
    # `None` for the session factory is load-bearing: any code path that opened a
    # session would raise a TypeError here rather than pass quietly.
    return BookingCommsService(
        None,  # type: ignore[arg-type]
        notifications=_Unconfigured(),  # type: ignore[arg-type]
        base_domain="modryn.co.il",
    )


# --- the body ---------------------------------------------------------------


def test_the_body_fits_its_segment_budget() -> None:
    assert ucs2_segments(PAYMENT_RECEIVED_NO_SLOT_BODY) <= PAYMENT_RECEIVED_NO_SLOT_MAX_SEGMENTS


def test_the_body_promises_no_refund() -> None:
    """MD1 holds the deposit against a NEW appointment; it does not return it.
    D16 writes no `refund_due` row and the port ships no `refund()`, so any word
    from the money-back family here would promise something the product cannot
    perform."""
    for word in ("החזר", "זיכוי", "יוחזר", "נחזיר"):
        assert word not in PAYMENT_RECEIVED_NO_SLOT_BODY


def test_the_body_names_no_new_time() -> None:
    """Race row #15 is the bride who already rebooked herself: her deposit is
    stranded on a cancelled row while a live booking of her own stands. "We will
    arrange a new time" would be wrong copy on precisely the case that is
    hardest to explain, so one body has to be true in both races."""
    assert "מועד חדש" not in PAYMENT_RECEIVED_NO_SLOT_BODY
    for digit in "0123456789":
        assert digit not in PAYMENT_RECEIVED_NO_SLOT_BODY


def test_the_body_claims_nothing_was_already_done() -> None:
    """It is sent from the branch where the product did NOT rebind her. Past
    tense about an action the boutique has not taken is the one thing the owner
    cannot walk back on the phone."""
    assert "קבענו" not in PAYMENT_RECEIVED_NO_SLOT_BODY
    assert "שריינו" not in PAYMENT_RECEIVED_NO_SLOT_BODY


def test_the_body_carries_no_manage_link() -> None:
    """No token, so `_deliver` is called with `token=None` and `log_body` stays
    None — which is only safe because there is nothing in this body to mask."""
    assert "https://" not in PAYMENT_RECEIVED_NO_SLOT_BODY


# --- the public send --------------------------------------------------------


def test_the_kind_exists_on_the_enum() -> None:
    assert MessageKind.PAYMENT_RECEIVED_NO_SLOT.value == "payment_received_no_slot"


async def test_no_provider_means_no_send_and_no_session() -> None:
    """`notify_owner_cancel`'s guard, for `notify_owner_cancel`'s reason: F11
    raises before any insert, so there would be no `message_log` evidence to
    lean on and the one app-log warning is the only trace."""
    assert await _service().notify_payment_received_no_slot(TENANT, booking=_booking()) is False
