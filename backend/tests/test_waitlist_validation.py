"""F22's pure pieces: the day-window bound and the wire shapes. No database.

The day window is D2 step 1 — `today_jerusalem <= day <= today + SLOT_WINDOW_MAX_DAYS`
— asserted against a FROZEN injectable clock in both directions and at both
edges, because the bound is Jerusalem-calendar and the CI runner, a laptop and
Israel are three different days for part of every day.
"""

import datetime

import pytest
from pydantic import ValidationError

from app.booking.validation import SLOT_WINDOW_MAX_DAYS
from app.errors import DomainValidationError
from app.waitlist.schemas import WaitlistJoinRequest
from app.waitlist.validation import validate_waitlist_day

# 21:30 UTC on Aug 5 is 00:30 on Aug 6 IN JERUSALEM — the frozen instant
# straddles the calendar boundary on purpose, so a naive UTC `.date()` in the
# implementation reads Aug 5 and fails the "today is joinable" case below.
FROZEN = datetime.datetime(2026, 8, 5, 21, 30, tzinfo=datetime.UTC)
TODAY_JLM = datetime.date(2026, 8, 6)


def _clock() -> datetime.datetime:
    return FROZEN


def test_today_and_the_horizon_edge_are_joinable() -> None:
    validate_waitlist_day(TODAY_JLM, clock=_clock)
    validate_waitlist_day(TODAY_JLM + datetime.timedelta(days=SLOT_WINDOW_MAX_DAYS), clock=_clock)


def test_yesterday_and_beyond_the_horizon_are_refused() -> None:
    with pytest.raises(DomainValidationError):
        validate_waitlist_day(TODAY_JLM - datetime.timedelta(days=1), clock=_clock)
    with pytest.raises(DomainValidationError):
        validate_waitlist_day(
            TODAY_JLM + datetime.timedelta(days=SLOT_WINDOW_MAX_DAYS + 1), clock=_clock
        )


def test_the_join_request_is_exactly_four_fields_and_forbids_extras() -> None:
    """ForbidExtraModel, the house convention on a public write: an unknown key
    is a 400 rather than a silently ignored field — and the D1 fields nobody
    asked for (name, marketing consent, dress) cannot ride in unnoticed."""
    body = {
        "phone": "0501234567",
        "verification_token": "tok",
        "day": "2026-08-20",
        "appointment_type_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    parsed = WaitlistJoinRequest.model_validate(body)
    assert parsed.day == datetime.date(2026, 8, 20)

    with pytest.raises(ValidationError):
        WaitlistJoinRequest.model_validate({**body, "name": "נועה"})
    with pytest.raises(ValidationError):
        WaitlistJoinRequest.model_validate({**body, "marketing_opt_in": True})


def test_a_malformed_day_or_missing_field_is_a_schema_error() -> None:
    good = {
        "phone": "0501234567",
        "verification_token": "tok",
        "day": "2026-08-20",
        "appointment_type_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    }
    with pytest.raises(ValidationError):
        WaitlistJoinRequest.model_validate({**good, "day": "not-a-day"})
    for field in good:
        broken = {name: value for name, value in good.items() if name != field}
        with pytest.raises(ValidationError):
            WaitlistJoinRequest.model_validate(broken)
