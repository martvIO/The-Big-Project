"""Pure-validation units for Feature 7 — no database, no event loop. These are
the write-time gate for stored-XSS (maps_url), money bounds (agorot), and the
weekly-grid invariants the slot engine (E3) will rely on."""

import datetime

import pytest

from app.boutique.validation import (
    MAX_DEPOSIT_AMOUNT_AGOROT,
    MAX_PROFILE_DESCRIPTION_LENGTH,
    MAX_PROFILE_PHONE_LENGTH,
    MAX_TERMS_TEXT_BYTES,
    BoutiqueValidationError,
    WeeklyRuleInput,
    validate_appointment_type,
    validate_exception_times,
    validate_maps_url,
    validate_phone,
    validate_profile,
    validate_terms,
    validate_toggles,
    validate_weekly_rules,
)
from app.models.constants import AppointmentAudience


def _rule(
    day: int, open_h: int, close_h: int, capacity: int = 1, minute: int = 0
) -> WeeklyRuleInput:
    return WeeklyRuleInput(
        day_of_week=day,
        open_time=datetime.time(open_h, minute),
        close_time=datetime.time(close_h, minute),
        capacity=capacity,
    )


# --- weekly rules: overlap detection + time ordering + bounds ---


def test_non_overlapping_windows_pass() -> None:
    validate_weekly_rules([_rule(0, 9, 12), _rule(0, 13, 17), _rule(1, 10, 14)])


def test_touching_windows_are_not_an_overlap() -> None:
    validate_weekly_rules([_rule(0, 9, 12), _rule(0, 12, 15)])


def test_overlapping_windows_same_day_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(0, 9, 13), _rule(0, 12, 17)])


def test_identical_windows_same_day_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(3, 9, 12), _rule(3, 9, 12)])


def test_same_hours_on_different_days_are_independent() -> None:
    validate_weekly_rules([_rule(0, 9, 12), _rule(1, 9, 12)])


def test_close_must_be_after_open() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(0, 12, 9)])
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(0, 9, 9)])


def test_day_of_week_out_of_range_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(7, 9, 12)])
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(-1, 9, 12)])


def test_capacity_must_be_positive() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(0, 9, 12, capacity=0)])
    with pytest.raises(BoutiqueValidationError):
        validate_weekly_rules([_rule(0, 9, 12, capacity=-1)])


def test_empty_rule_set_is_valid() -> None:
    validate_weekly_rules([])


# --- exception times: one-sided rejection ---


def test_exception_both_times_empty_means_closed_all_day() -> None:
    validate_exception_times(None, None)


def test_exception_both_times_set_means_special_hours() -> None:
    validate_exception_times(datetime.time(10, 0), datetime.time(14, 0))


def test_exception_one_sided_times_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_exception_times(datetime.time(10, 0), None)
    with pytest.raises(BoutiqueValidationError):
        validate_exception_times(None, datetime.time(14, 0))


def test_exception_close_must_be_after_open() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_exception_times(datetime.time(14, 0), datetime.time(10, 0))
    with pytest.raises(BoutiqueValidationError):
        validate_exception_times(datetime.time(10, 0), datetime.time(10, 0))


# --- maps_url: scheme allowlist (stored-XSS write-time gate) ---


def test_http_and_https_maps_urls_pass() -> None:
    validate_maps_url("https://maps.app.goo.gl/abc123")
    validate_maps_url("http://maps.example.com/place?q=1")


def test_javascript_maps_url_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_maps_url("javascript:alert(1)")
    # Scheme matching must be case-insensitive.
    with pytest.raises(BoutiqueValidationError):
        validate_maps_url("JavaScript:alert(1)")


def test_non_http_schemes_rejected() -> None:
    for url in ("data:text/html,x", "ftp://example.com/x", "vbscript:x"):
        with pytest.raises(BoutiqueValidationError):
            validate_maps_url(url)


def test_relative_and_hostless_maps_urls_rejected() -> None:
    for url in ("//evil.example/x", "/place/123", "https://", "not a url"):
        with pytest.raises(BoutiqueValidationError):
            validate_maps_url(url)


def test_oversized_maps_url_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_maps_url("https://maps.example.com/" + "a" * 2000)


# --- phone charset ---


def test_phone_safe_charset_passes() -> None:
    validate_phone("+972 (3) 555-0100")
    validate_phone("035550100")


def test_phone_with_letters_or_injection_chars_rejected() -> None:
    for phone in ("abc", "03-555;drop", "555<script>", "+972+3"):
        with pytest.raises(BoutiqueValidationError):
            validate_phone(phone)


def test_phone_length_cap() -> None:
    validate_phone("1" * MAX_PROFILE_PHONE_LENGTH)
    with pytest.raises(BoutiqueValidationError):
        validate_phone("1" * (MAX_PROFILE_PHONE_LENGTH + 1))


# --- profile / toggles shape and length caps ---


def test_full_valid_profile_passes() -> None:
    validate_profile(
        {
            "phone": "+972-3-555-0100",
            "address": "12 Dizengoff St, Tel Aviv",
            "description": "Bridal boutique.",
            "maps_url": "https://maps.example.com/bella",
        }
    )


def test_profile_unknown_key_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_profile({"phone": "03-555", "website": "https://x.example"})


def test_profile_non_string_value_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_profile({"description": 42})


def test_description_length_cap() -> None:
    validate_profile({"description": "x" * MAX_PROFILE_DESCRIPTION_LENGTH})
    with pytest.raises(BoutiqueValidationError):
        validate_profile({"description": "x" * (MAX_PROFILE_DESCRIPTION_LENGTH + 1)})


def test_empty_profile_strings_are_allowed_as_clears() -> None:
    validate_profile({"phone": "", "maps_url": ""})


def test_toggles_valid_and_unknown_key_rejected() -> None:
    validate_toggles({"deposits_enabled": True, "brides_only": False})
    with pytest.raises(BoutiqueValidationError):
        validate_toggles({"marketing_enabled": True})


def test_toggles_non_bool_value_rejected() -> None:
    # isinstance(1, bool) is False — truthy ints must not sneak through.
    with pytest.raises(BoutiqueValidationError):
        validate_toggles({"deposits_enabled": 1})


# --- appointment type: duration + agorot bounds + deposit interplay ---


def test_valid_appointment_type_passes() -> None:
    validate_appointment_type(
        name="Fitting",
        duration_minutes=60,
        audience=AppointmentAudience.BRIDES_ONLY,
        deposit_required=True,
        deposit_amount_agorot=15_000,
    )


def test_duration_must_be_positive() -> None:
    for duration in (0, -30):
        with pytest.raises(BoutiqueValidationError):
            validate_appointment_type(
                name="Fitting",
                duration_minutes=duration,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=None,
            )


def test_blank_name_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_appointment_type(
            name="   ",
            duration_minutes=30,
            audience=AppointmentAudience.ALL,
            deposit_required=False,
            deposit_amount_agorot=None,
        )


def test_unknown_audience_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_appointment_type(
            name="Fitting",
            duration_minutes=30,
            audience="grooms_only",
            deposit_required=False,
            deposit_amount_agorot=None,
        )


def test_deposit_required_needs_positive_amount() -> None:
    for amount in (None, 0, -100):
        with pytest.raises(BoutiqueValidationError):
            validate_appointment_type(
                name="Fitting",
                duration_minutes=30,
                audience=AppointmentAudience.ALL,
                deposit_required=True,
                deposit_amount_agorot=amount,
            )


def test_agorot_bounds() -> None:
    # Amount on a deposit_required=false type is allowed-but-inert (spec edge 4),
    # but it must still be a sane positive integer.
    validate_appointment_type(
        name="Fitting",
        duration_minutes=30,
        audience=AppointmentAudience.ALL,
        deposit_required=False,
        deposit_amount_agorot=MAX_DEPOSIT_AMOUNT_AGOROT,
    )
    for amount in (0, -1, MAX_DEPOSIT_AMOUNT_AGOROT + 1):
        with pytest.raises(BoutiqueValidationError):
            validate_appointment_type(
                name="Fitting",
                duration_minutes=30,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=amount,
            )


# --- terms: text size + refund-window + forfeit bounds ---


def test_valid_terms_pass() -> None:
    validate_terms(terms_text="Cancel 48h before.", refundable_until_hours_before=48)
    validate_terms(terms_text="No refunds.", refundable_until_hours_before=0, forfeit_percent=100)


def test_empty_terms_text_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_terms(terms_text="   ", refundable_until_hours_before=48)


def test_terms_text_size_cap_is_bytes_not_chars() -> None:
    validate_terms(terms_text="a" * MAX_TERMS_TEXT_BYTES, refundable_until_hours_before=48)
    with pytest.raises(BoutiqueValidationError):
        validate_terms(
            terms_text="a" * (MAX_TERMS_TEXT_BYTES + 1), refundable_until_hours_before=48
        )
    # Hebrew is 2 bytes/char in UTF-8 — byte cap, not len().
    with pytest.raises(BoutiqueValidationError):
        validate_terms(
            terms_text="א" * (MAX_TERMS_TEXT_BYTES // 2 + 1), refundable_until_hours_before=48
        )


def test_negative_refund_window_rejected() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_terms(terms_text="T", refundable_until_hours_before=-1)


def test_forfeit_percent_bounds() -> None:
    validate_terms(terms_text="T", refundable_until_hours_before=1, forfeit_percent=0)
    validate_terms(terms_text="T", refundable_until_hours_before=1, forfeit_percent=100)
    for forfeit in (-1, 101, 150):
        with pytest.raises(BoutiqueValidationError):
            validate_terms(terms_text="T", refundable_until_hours_before=1, forfeit_percent=forfeit)
