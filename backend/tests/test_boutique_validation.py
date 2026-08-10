"""Pure-validation units for Feature 7 — no database, no event loop. These are
the write-time gate for stored-XSS (maps_url), money bounds (agorot), and the
weekly-grid invariants the slot engine (E3) will rely on."""

import datetime
from typing import Any
from unittest import mock

import pytest

from app.atelier.stages import MAX_BAND_MINUTES, MAX_WEEKLY_CAPACITY_HOURS
from app.boutique import validation
from app.boutique.toggles import TOGGLE_DEFAULTS, TOGGLE_KEYS, TOGGLES, ToggleDef
from app.boutique.validation import (
    MAX_DEPOSIT_AMOUNT_AGOROT,
    MAX_PROFILE_DESCRIPTION_LENGTH,
    MAX_PROFILE_PHONE_LENGTH,
    MAX_TERMS_TEXT_BYTES,
    SCHEDULING_DEFAULTS,
    BoutiqueValidationError,
    WeeklyRuleInput,
    validate_appointment_type,
    validate_atelier_settings,
    validate_exception_times,
    validate_maps_url,
    validate_phone,
    validate_profile,
    validate_scheduling_settings,
    validate_terms,
    validate_toggles,
    validate_weekly_rules,
)
from app.models.constants import AppointmentAudience, EffortBand


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


# --- F27 D1: the registry is the single declaration point ---


def test_the_registry_declares_exactly_the_shipped_toggles() -> None:
    """Every entry is a toggle with a SHIPPED CONSUMER and nothing else (spec
    conflict 1). A row for an unshipped feature belongs in that feature's own PR
    — F23's `waitlist_enabled`, F46's `whatsapp_enabled` — so this list growing
    without a consumer landing beside it is the failure this pins."""
    assert TOGGLE_KEYS == ("deposits_enabled", "brides_only")
    assert all(toggle.default is False for toggle in TOGGLES)
    assert TOGGLE_DEFAULTS == {"deposits_enabled": False, "brides_only": False}


def test_validate_toggles_derives_its_key_set_from_the_registry() -> None:
    """⚠ DERIVATION, NOT A DUPLICATED LITERAL, AND THIS IS THE ASSERTION THAT
    PROVES IT. `_TOGGLE_FIELDS = frozenset({...})` beside `TOGGLES` would pass
    every other test in this file while making D8's growth protocol a lie — the
    feature adding a row would get a 400 from a validator that never heard of it.

    Monkeypatching the registry is the only way to tell the two apart: a derived
    validator accepts the patched key, a duplicated literal rejects it.
    """
    extra = ToggleDef(key="waitlist_enabled", default=False)
    with mock.patch.object(validation, "TOGGLES", (*TOGGLES, extra)):
        validate_toggles({"waitlist_enabled": True})
    # And it is gone again once the registry is — no module-level cache.
    with pytest.raises(BoutiqueValidationError):
        validate_toggles({"waitlist_enabled": True})


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


# --- F42's atelier block: the two rules pydantic cannot express ---
#
# The TYPE refusals are `AtelierSettingsUpdate`'s (`StrictInt`, and an unknown
# band key against `dict[EffortBand, StrictInt]`) and run BEFORE this function.
# What lives here is what a request model cannot see: the MISSING key, and the
# two numeric ranges.


def _bands(**overrides: int) -> dict[str, int]:
    bands = {
        EffortBand.THIRTY_MIN.value: 30,
        EffortBand.ONE_HOUR.value: 60,
        EffortBand.TWO_HOURS.value: 120,
        EffortBand.HALF_DAY.value: 300,
        EffortBand.FULL_DAY.value: 540,
    }
    bands.update(overrides)
    return bands


def _atelier(bands: dict[str, int] | None = None, default: int | None = 36) -> dict[str, Any]:
    return {
        "effort_bands": _bands() if bands is None else bands,
        "default_weekly_capacity_hours": default,
    }


def test_the_five_bands_are_accepted() -> None:
    validate_atelier_settings(_atelier())


def test_a_missing_band_key_is_refused() -> None:
    """⚠ THE HALF PYDANTIC CANNOT SEE. `dict[EffortBand, StrictInt]` refuses an
    UNKNOWN key; nothing but a set equality refuses a MISSING one.

    The read side tolerates a partial mapping — `effort_bands` falls back per
    band (`stages.py`) — and that tolerance is a backstop against a hand-edited
    JSONB blob, not a contract for the API. A writer that could post three bands
    would let the other two silently revert to the platform's numbers with no
    visible act and nothing in the payload to show it.
    """
    partial = _bands()
    del partial[EffortBand.HALF_DAY.value]
    with pytest.raises(BoutiqueValidationError):
        validate_atelier_settings(_atelier(partial))


def test_an_unknown_band_key_is_refused_here_too() -> None:
    """The request model refuses this first; the validator refuses it as well so
    a non-router caller gets the same 400 rather than writing a sixth band."""
    with pytest.raises(BoutiqueValidationError):
        validate_atelier_settings(_atelier({**_bands(), "three_hours": 180}))


@pytest.mark.parametrize("minutes", [0, -1, MAX_BAND_MINUTES + 1])
def test_a_band_outside_the_stored_bound_is_refused(minutes: int) -> None:
    """`1..1440`, the DDL CHECK on `alteration_tickets.effort_minutes`. A stored
    5000 would reach the INSERT and answer a 500 on intake instead of a ticket.
    """
    with pytest.raises(BoutiqueValidationError):
        validate_atelier_settings(_atelier(_bands(half_day=minutes)))


@pytest.mark.parametrize("minutes", [1, MAX_BAND_MINUTES])
def test_both_ends_of_the_band_bound_are_admitted(minutes: int) -> None:
    validate_atelier_settings(_atelier(_bands(half_day=minutes)))


def test_the_bands_need_not_be_distinct_or_increasing() -> None:
    """An owner may flatten her two longest bands onto one number.
    `bandLabel`'s first-match-wins already handles it, and refusing it would be
    the platform having an opinion about her workroom. ⚠ D4 records the
    consequence — a flattened band silently RELABELS old cards — and accepts it.
    """
    validate_atelier_settings(_atelier(_bands(half_day=240, full_day=240)))
    validate_atelier_settings(_atelier(_bands(thirty_min=480, full_day=30)))


def test_no_default_at_all_is_a_legal_block() -> None:
    """`null` is a VALUE and it CLEARS the boutique's default. It is required on
    the wire, never optional."""
    validate_atelier_settings(_atelier(default=None))


@pytest.mark.parametrize("hours", [0, 1, MAX_WEEKLY_CAPACITY_HOURS])
def test_a_default_inside_the_columns_own_bound_is_accepted(hours: int) -> None:
    """⚠ INCLUDING `0`, which is «the boutique is stood down this week» and not
    an unset value."""
    validate_atelier_settings(_atelier(default=hours))


@pytest.mark.parametrize("hours", [-1, MAX_WEEKLY_CAPACITY_HOURS + 1, 1000])
def test_a_default_outside_the_columns_own_bound_is_refused(hours: int) -> None:
    """The bound is imported from `app/atelier/stages.py` — the same magnitude
    the 0022 CHECK pins on `staff_users.weekly_capacity_hours`, so the settings
    bound and the column bound cannot drift."""
    with pytest.raises(BoutiqueValidationError):
        validate_atelier_settings(_atelier(default=hours))


@pytest.mark.parametrize("bands", ["nope", None, [30, 60], 30])
def test_a_bands_value_that_is_not_a_mapping_is_refused(bands: Any) -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_atelier_settings({"effort_bands": bands, "default_weekly_capacity_hours": None})


# --- F39: the submission deadline (D6) ---------------------------------------


def test_the_scheduling_defaults_are_wednesday_at_six() -> None:
    """O1: a GUESS at the pilot's norm, recorded so the guess is visible. It
    leaves Thursday–Saturday to build the roster before Sunday, and a wrong
    default costs one dialog rather than a migration."""
    assert SCHEDULING_DEFAULTS == {
        "submission_deadline_day_of_week": 3,
        "submission_deadline_time": "18:00",
    }


def test_the_defaults_pass_their_own_validator() -> None:
    """A default that its validator would refuse is a tenant nobody can save
    without first changing something — asserted, not assumed."""
    validate_scheduling_settings(dict(SCHEDULING_DEFAULTS))


@pytest.mark.parametrize("day", [-1, 7, 100])
def test_a_deadline_day_outside_the_week_is_refused(day: int) -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_scheduling_settings(
            {"submission_deadline_day_of_week": day, "submission_deadline_time": "18:00"}
        )


def test_a_bool_day_is_refused_here_too() -> None:
    """⚠ BELT AND BRACES, AND BOTH ARE LOAD-BEARING. `SchedulingSettingsUpdate`'s
    `StrictInt` is what stops `true` becoming `1` on the REQUEST path; this check
    is what stops it on the hand-edited-JSONB path, which no request model can
    see. `isinstance(True, int)` is True in Python, so without the explicit bool
    test the range check would admit it."""
    with pytest.raises(BoutiqueValidationError):
        validate_scheduling_settings(
            {"submission_deadline_day_of_week": True, "submission_deadline_time": "18:00"}
        )


@pytest.mark.parametrize("value", ["24:00", "18:0", "6:00", "18:60", "18:00:00", "", "evening"])
def test_a_malformed_deadline_time_is_refused(value: str) -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_scheduling_settings(
            {"submission_deadline_day_of_week": 3, "submission_deadline_time": value}
        )


@pytest.mark.parametrize("value", ["00:00", "09:30", "18:00", "23:59"])
def test_a_well_formed_deadline_time_is_accepted(value: str) -> None:
    validate_scheduling_settings(
        {"submission_deadline_day_of_week": 3, "submission_deadline_time": value}
    )


def test_an_unknown_scheduling_key_is_refused() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_scheduling_settings({**SCHEDULING_DEFAULTS, "submission_deadline_zone": "UTC"})


def test_a_partial_scheduling_block_is_refused_by_the_validator_too() -> None:
    """⚠ THE DATA-LOSS BUG, GUARDED TWICE. `merge_settings` is a top-level `||`,
    so a patch naming one of the two fields DELETES the other. The schema makes
    the partial unconstructible on the request path; this makes it a 400 on every
    other path into the service."""
    for partial in (
        {"submission_deadline_day_of_week": 3},
        {"submission_deadline_time": "18:00"},
        {},
    ):
        with pytest.raises(BoutiqueValidationError):
            validate_scheduling_settings(partial)
