"""Fast, pure tests for F13's request-shape validation. Everything that needs
the database (real slots, real dresses, races) lives in test_booking_service.py."""

import uuid

import pytest

from app.booking.validation import (
    MAX_BOOKING_NOTES_LENGTH,
    MAX_CUSTOMER_NAME_LENGTH,
    MAX_SEAT_INDEX,
    BookingValidationError,
    validate_booking_request,
)
from app.boutique.validation import MAX_RULE_CAPACITY

DRESS_ID = uuid.uuid4()


def test_generic_path_needs_neither_dress_nor_size() -> None:
    validate_booking_request(name="נועה לוי", notes=None, dress_id=None, dress_size=None)


def test_item_path_carries_both_dress_and_size() -> None:
    validate_booking_request(name="נועה לוי", notes="הערה", dress_id=DRESS_ID, dress_size="38")


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_blank_name_is_rejected(name: str) -> None:
    with pytest.raises(BookingValidationError, match="blank"):
        validate_booking_request(name=name, notes=None, dress_id=None, dress_size=None)


def test_name_bound_is_inclusive() -> None:
    validate_booking_request(
        name="א" * MAX_CUSTOMER_NAME_LENGTH, notes=None, dress_id=None, dress_size=None
    )
    with pytest.raises(BookingValidationError, match="name is too long"):
        validate_booking_request(
            name="א" * (MAX_CUSTOMER_NAME_LENGTH + 1), notes=None, dress_id=None, dress_size=None
        )


def test_notes_bound_is_inclusive_and_none_is_fine() -> None:
    validate_booking_request(
        name="נועה", notes="ה" * MAX_BOOKING_NOTES_LENGTH, dress_id=None, dress_size=None
    )
    with pytest.raises(BookingValidationError, match="notes is too long"):
        validate_booking_request(
            name="נועה", notes="ה" * (MAX_BOOKING_NOTES_LENGTH + 1), dress_id=None, dress_size=None
        )


@pytest.mark.parametrize("dress_size", [None, "", "   "])
def test_dress_without_usable_size_is_rejected(dress_size: str | None) -> None:
    with pytest.raises(BookingValidationError, match="dress_size is required"):
        validate_booking_request(name="נועה", notes=None, dress_id=DRESS_ID, dress_size=dress_size)


def test_size_without_dress_is_rejected() -> None:
    with pytest.raises(BookingValidationError, match="requires dress_id"):
        validate_booking_request(name="נועה", notes=None, dress_id=None, dress_size="38")


@pytest.mark.parametrize("name", ["נועה\x00לוי", "נועה\nלוי", "נועה\tלוי", "נועה\x7f"])
def test_control_characters_are_rejected_in_a_name(name: str) -> None:
    """U+0000 is rejected by Postgres `text` itself — unguarded it is an
    uncaught DataError, i.e. a 500 on an anonymous route. Line breaks are
    barred too: F16 will template this value into an SMS."""
    with pytest.raises(BookingValidationError, match="invalid characters"):
        validate_booking_request(name=name, notes=None, dress_id=None, dress_size=None)


def test_notes_keep_newlines_but_not_nulls() -> None:
    """A note is a paragraph, so newlines and tabs are legitimate content —
    the NUL that Postgres refuses is not."""
    validate_booking_request(
        name="נועה", notes="שורה ראשונה\nשורה שנייה\tעם טאב", dress_id=None, dress_size=None
    )
    with pytest.raises(BookingValidationError, match="invalid characters"):
        validate_booking_request(name="נועה", notes="a\x00b", dress_id=None, dress_size=None)


def test_seat_ceiling_matches_rule_capacity_ceiling() -> None:
    """A seat index above capacity can never be claimed, so the two bounds are
    ONE number by design — 0008's CHECK pins the same value. If someone raises
    rule capacity without widening the seat CHECK, this is the test that says so."""
    assert MAX_SEAT_INDEX == MAX_RULE_CAPACITY
