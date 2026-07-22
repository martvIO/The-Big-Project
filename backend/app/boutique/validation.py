"""Pure domain validation for owner settings — no I/O, unit-tested locally.

These are write-time gates: maps_url scheme allowlisting blocks stored XSS on
the public storefront (F10 escapes at render time too — defense in depth), and
the money/percent bounds mirror the migration's CHECK constraints so bad input
fails with a clean 400 instead of an IntegrityError."""

import dataclasses
import datetime
import itertools
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from app.models.constants import AppointmentAudience


class BoutiqueValidationError(Exception):
    """Domain-rule violation on an owner-settings write; the router maps it to
    the house-shape 400."""


MAX_PROFILE_PHONE_LENGTH = 32
MAX_PROFILE_ADDRESS_LENGTH = 500
MAX_PROFILE_DESCRIPTION_LENGTH = 2000
MAX_PROFILE_MAPS_URL_LENGTH = 1000
MAX_APPOINTMENT_TYPE_NAME_LENGTH = 200
MAX_DURATION_MINUTES = 24 * 60
MAX_EXCEPTION_NOTE_LENGTH = 500
MAX_TERMS_TEXT_BYTES = 50 * 1024
# 1,000,000 ILS in agorot — sanity cap on money input, well inside INTEGER range.
MAX_DEPOSIT_AMOUNT_AGOROT = 100_000_000

ALLOWED_MAPS_URL_SCHEMES = frozenset({"http", "https"})
_PHONE_SAFE_CHARS = frozenset("0123456789 ()-")
_PROFILE_FIELDS = frozenset({"phone", "address", "description", "maps_url"})
_TOGGLE_FIELDS = frozenset({"deposits_enabled", "brides_only"})
_AUDIENCE_VALUES = frozenset(member.value for member in AppointmentAudience)


@dataclasses.dataclass(frozen=True)
class WeeklyRuleInput:
    day_of_week: int
    open_time: datetime.time
    close_time: datetime.time
    capacity: int = 1


def validate_maps_url(url: str) -> None:
    if len(url) > MAX_PROFILE_MAPS_URL_LENGTH:
        raise BoutiqueValidationError("maps_url is too long")
    parts = urlsplit(url)  # lowercases the scheme, so JavaScript: cannot slip by
    if parts.scheme not in ALLOWED_MAPS_URL_SCHEMES or not parts.netloc:
        raise BoutiqueValidationError("maps_url must be an absolute http(s) URL")


def validate_phone(phone: str) -> None:
    if len(phone) > MAX_PROFILE_PHONE_LENGTH:
        raise BoutiqueValidationError("phone is too long")
    # At most one leading +, then a phone-safe charset only.
    digits = phone.removeprefix("+")
    if (
        "+" in digits
        or not set(digits) <= _PHONE_SAFE_CHARS
        or not any(char.isdigit() for char in digits)
    ):
        raise BoutiqueValidationError("phone contains invalid characters")


def validate_profile(profile: dict[str, Any]) -> None:
    unknown = set(profile) - _PROFILE_FIELDS
    if unknown:
        raise BoutiqueValidationError(f"unknown profile fields: {', '.join(sorted(unknown))}")
    for field, value in profile.items():
        if not isinstance(value, str):
            raise BoutiqueValidationError(f"{field} must be a string")
    # Empty string = cleared field; format checks apply only to non-empty values.
    phone = profile.get("phone")
    if phone:
        validate_phone(phone)
    maps_url = profile.get("maps_url")
    if maps_url:
        validate_maps_url(maps_url)
    address = profile.get("address")
    if address is not None and len(address) > MAX_PROFILE_ADDRESS_LENGTH:
        raise BoutiqueValidationError("address is too long")
    description = profile.get("description")
    if description is not None and len(description) > MAX_PROFILE_DESCRIPTION_LENGTH:
        raise BoutiqueValidationError("description is too long")


def validate_toggles(toggles: dict[str, Any]) -> None:
    unknown = set(toggles) - _TOGGLE_FIELDS
    if unknown:
        raise BoutiqueValidationError(f"unknown toggles: {', '.join(sorted(unknown))}")
    for field, value in toggles.items():
        # isinstance check, not truthiness: 1/"true" must not masquerade as bools.
        if not isinstance(value, bool):
            raise BoutiqueValidationError(f"{field} must be a boolean")


def validate_appointment_type(
    *,
    name: str,
    duration_minutes: int,
    audience: str,
    deposit_required: bool,
    deposit_amount_agorot: int | None,
) -> None:
    if not name.strip():
        raise BoutiqueValidationError("name must not be blank")
    if len(name) > MAX_APPOINTMENT_TYPE_NAME_LENGTH:
        raise BoutiqueValidationError("name is too long")
    if not 0 < duration_minutes <= MAX_DURATION_MINUTES:
        raise BoutiqueValidationError("duration_minutes must be between 1 and 1440")
    if audience not in _AUDIENCE_VALUES:
        raise BoutiqueValidationError("audience must be one of: all, brides_only")
    if deposit_required and (deposit_amount_agorot is None or deposit_amount_agorot <= 0):
        raise BoutiqueValidationError("deposit_amount_agorot is required when deposit_required")
    if deposit_amount_agorot is not None and not (
        0 < deposit_amount_agorot <= MAX_DEPOSIT_AMOUNT_AGOROT
    ):
        raise BoutiqueValidationError("deposit_amount_agorot is out of bounds")


def validate_weekly_rules(rules: Sequence[WeeklyRuleInput]) -> None:
    for rule in rules:
        if not 0 <= rule.day_of_week <= 6:
            raise BoutiqueValidationError("day_of_week must be between 0 and 6")
        if rule.close_time <= rule.open_time:
            raise BoutiqueValidationError("close_time must be after open_time")
        if rule.capacity <= 0:
            raise BoutiqueValidationError("capacity must be positive")
    by_day: dict[int, list[WeeklyRuleInput]] = {}
    for rule in rules:
        by_day.setdefault(rule.day_of_week, []).append(rule)
    for day_rules in by_day.values():
        ordered = sorted(day_rules, key=lambda rule: (rule.open_time, rule.close_time))
        for prev, nxt in itertools.pairwise(ordered):
            # Touching windows (close == next open) are fine; overlap is not.
            if nxt.open_time < prev.close_time:
                raise BoutiqueValidationError("windows on the same day must not overlap")


def validate_exception_times(
    open_time: datetime.time | None, close_time: datetime.time | None
) -> None:
    if (open_time is None) != (close_time is None):
        raise BoutiqueValidationError(
            "open_time and close_time must both be set (special hours) "
            "or both be empty (closed all day)"
        )
    if open_time is not None and close_time is not None and close_time <= open_time:
        raise BoutiqueValidationError("close_time must be after open_time")


def validate_exception_note(note: str | None) -> None:
    if note is not None and len(note) > MAX_EXCEPTION_NOTE_LENGTH:
        raise BoutiqueValidationError("note is too long")


def validate_terms(
    *, terms_text: str, refundable_until_hours_before: int, forfeit_percent: int = 100
) -> None:
    if not terms_text.strip():
        raise BoutiqueValidationError("terms_text must not be blank")
    # Byte cap, not len(): Hebrew is 2 bytes/char in UTF-8 and the 50 KB budget
    # is about storage of immutable evidence, not glyph count.
    if len(terms_text.encode("utf-8")) > MAX_TERMS_TEXT_BYTES:
        raise BoutiqueValidationError("terms_text exceeds 50 KB")
    if refundable_until_hours_before < 0:
        raise BoutiqueValidationError("refundable_until_hours_before must be >= 0")
    if not 0 <= forfeit_percent <= 100:
        raise BoutiqueValidationError("forfeit_percent must be between 0 and 100")
