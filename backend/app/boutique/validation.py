"""Pure domain validation for owner settings — no I/O, unit-tested locally.

These are write-time gates: maps_url scheme allowlisting blocks stored XSS on
the public storefront (F10 escapes at render time too — defense in depth), and
the money/percent bounds mirror the migration's CHECK constraints so bad input
fails with a clean 400 instead of an IntegrityError."""

import dataclasses
import datetime
import itertools
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from app.atelier.stages import MAX_BAND_MINUTES, MAX_WEEKLY_CAPACITY_HOURS
from app.boutique.toggles import TOGGLES
from app.errors import DomainValidationError
from app.models.constants import AppointmentAudience, EffortBand


class BoutiqueValidationError(DomainValidationError):
    """Domain-rule violation on an owner-settings write; the router maps it to
    the house-shape 400.

    Re-parented onto the shared base so one handler serves every domain module;
    behaviour-neutral, since Starlette still matches this class through its MRO."""


MAX_PROFILE_PHONE_LENGTH = 32
MAX_PROFILE_ADDRESS_LENGTH = 500
MAX_PROFILE_DESCRIPTION_LENGTH = 2000
MAX_PROFILE_MAPS_URL_LENGTH = 1000
# One line under a --text-3xl display heading at 375px.
MAX_PROFILE_ESSENCE_LENGTH = 120
# Instagram's own handle ceiling.
MAX_PROFILE_INSTAGRAM_LENGTH = 30
MAX_APPOINTMENT_TYPE_NAME_LENGTH = 200
MAX_DURATION_MINUTES = 24 * 60
MAX_EXCEPTION_NOTE_LENGTH = 500
MAX_TERMS_TEXT_BYTES = 50 * 1024
# 1,000,000 ILS in agorot — sanity cap on money input, well inside INTEGER range.
MAX_DEPOSIT_AMOUNT_AGOROT = 100_000_000
# Upper bounds keeping INT4 columns and request bodies inside sane ranges; the
# service mirrors the schema Field caps so non-router callers get the same 400s
# instead of DataError 500s (terms rows are immutable evidence — a bad value
# can never be corrected in place).
MAX_WEEKLY_RULES = 50
MAX_RULE_CAPACITY = 1000
MAX_REFUNDABLE_HOURS = 24 * 365 * 10
MAX_SORT_ORDER = 1_000_000

# F39 D6. The FIFTH `tenants.settings` top-level key, and the only one that is a
# submission DEADLINE rather than a description of the boutique.
#
# `(3, "18:00")` — Wednesday 18:00 — leaves Thursday–Saturday to build the roster
# before Sunday. It is a GUESS at the pilot's norm (spec O1) and costs one dialog
# to change, never a migration.
#
# ⚠ THE WHOLE PAIR IS ALWAYS PRESENT ON THE WIRE (`{**SCHEDULING_DEFAULTS,
# **stored}`, the `toggles` D3 shape), so neither the console nor the lock
# predicate needs `?? default` anywhere and the two cannot disagree about what an
# absent key means.
SCHEDULING_DEFAULTS: dict[str, Any] = {
    "submission_deadline_day_of_week": 3,
    "submission_deadline_time": "18:00",
}

ALLOWED_MAPS_URL_SCHEMES = frozenset({"http", "https"})
_PHONE_SAFE_CHARS = frozenset("0123456789 ()-")
_PROFILE_FIELDS = frozenset({"phone", "address", "description", "maps_url", "essence", "instagram"})
# Instagram's own rule: letters, digits, period, underscore. Anchored, so a
# handle with a slash or an @ is rejected outright rather than stored as a dead
# link — ContactPanel builds https://instagram.com/{handle} from this verbatim.
_INSTAGRAM_HANDLE = re.compile(r"^[A-Za-z0-9._]{1,30}\Z")
_ATELIER_FIELDS = frozenset({"effort_bands", "default_weekly_capacity_hours"})
_SCHEDULING_FIELDS = frozenset({"submission_deadline_day_of_week", "submission_deadline_time"})
# `HH:MM`, 24-hour, anchored. A LOCAL wall-clock time and never an instant
# (D6): "18:00 Wednesday" is 16:00Z in winter and 15:00Z in summer, so a
# stored UTC value drifts an hour twice a year. `app/shifts/validation.py`
# resolves the instant per week from this pair and the target week's date.
_DEADLINE_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d\Z")
_BAND_KEYS = frozenset(band.value for band in EffortBand)
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


def validate_instagram_handle(handle: str) -> None:
    """Rejects a leading @ rather than stripping it. The stored value is
    interpolated straight into https://instagram.com/{handle}, so silently
    accepting "@bella" and normalising it would make the column's contract
    depend on which write path wrote it; one canonical form, enforced at the
    only gate, is what keeps the storefront's link builder a pure join."""
    if _INSTAGRAM_HANDLE.match(handle) is None:
        raise BoutiqueValidationError(
            "instagram must be a handle without the @ — letters, digits, period and underscore only"
        )


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
    essence = profile.get("essence")
    if essence is not None and len(essence) > MAX_PROFILE_ESSENCE_LENGTH:
        raise BoutiqueValidationError("essence is too long")
    instagram = profile.get("instagram")
    if instagram:
        validate_instagram_handle(instagram)


def validate_toggles(toggles: dict[str, Any]) -> None:
    """⚠ THE KEY SET IS DERIVED FROM `app/boutique/toggles.py` AT CALL TIME, NOT
    COPIED. F27 D1: the registry is the single declaration point, so a feature
    adding a toggle touches the registry and its consumer and this validator
    follows. A frozenset literal here — which is what F7 shipped — would make
    D8's growth protocol quietly false, and the feature adding a row would get a
    400 from a validator that had never heard of its key.

    Reading the module global rather than a precomputed set is what makes the
    derivation *provable*: `test_validate_toggles_derives_its_key_set_from_the_
    registry` patches `TOGGLES` and this function must follow it.
    """
    unknown = set(toggles) - {toggle.key for toggle in TOGGLES}
    if unknown:
        raise BoutiqueValidationError(f"unknown toggles: {', '.join(sorted(unknown))}")
    for field, value in toggles.items():
        # isinstance check, not truthiness: 1/"true" must not masquerade as bools.
        if not isinstance(value, bool):
            raise BoutiqueValidationError(f"{field} must be a boolean")


def validate_atelier_settings(atelier: dict[str, Any]) -> None:
    """F42's `atelier` block (D5). It owns EXACTLY what a request model cannot
    express, and nothing else.

    ⚠ THE INT-NESS AND THE ANTI-`bool` RULE ARE `AtelierSettingsUpdate`'s, NOT
    THIS FUNCTION'S. `ForbidExtraModel` is `extra="forbid"` and nothing else, so
    without `StrictInt` up there pydantic would coerce `{"half_day": true}` to
    `1` before this function ever ran and an `isinstance(v, bool)` check here
    would be unreachable code. The refusal has to happen at the type, which is
    why this validator does not attempt it.

    What it does own:

    - the MISSING band key. `dict[EffortBand, StrictInt]` refuses an UNKNOWN key;
      only a set equality refuses an absent one. The read side tolerates a
      partial mapping as a backstop against a hand-edited blob (`stages.py`
      falls back per band) — that is not a contract for the API, because a
      three-band save would silently revert the other two to platform numbers.
    - the two ranges, both imported from `app/atelier/stages.py` so the settings
      bound and the DDL CHECK cannot drift. That import edge is acyclic:
      `atelier.stages` imports only `app.models`.

    Bands are deliberately NOT required to be distinct or increasing — an owner
    may flatten her two longest onto one number, and refusing it would be the
    platform having an opinion about her workroom (D4 owns the consequence).
    """
    unknown = set(atelier) - _ATELIER_FIELDS
    if unknown:
        raise BoutiqueValidationError(f"unknown atelier keys: {', '.join(sorted(unknown))}")

    bands = atelier.get("effort_bands")
    if not isinstance(bands, dict) or set(bands) != _BAND_KEYS:
        raise BoutiqueValidationError(
            f"effort_bands must name exactly: {', '.join(sorted(_BAND_KEYS))}"
        )
    for band, minutes in bands.items():
        if not isinstance(minutes, int) or not 1 <= minutes <= MAX_BAND_MINUTES:
            raise BoutiqueValidationError(f"{band} must be between 1 and {MAX_BAND_MINUTES}")

    default = atelier.get("default_weekly_capacity_hours")
    if default is not None and (
        not isinstance(default, int) or not 0 <= default <= MAX_WEEKLY_CAPACITY_HOURS
    ):
        raise BoutiqueValidationError(
            f"default_weekly_capacity_hours must be between 0 and {MAX_WEEKLY_CAPACITY_HOURS}"
        )


def validate_scheduling_settings(scheduling: dict[str, Any]) -> None:
    """F39's `scheduling` block (D6). It owns EXACTLY what a request model cannot
    express, and nothing else.

    ⚠ THE INT-NESS AND THE ANTI-`bool` RULE ARE `SchedulingSettingsUpdate`'s, NOT
    THIS FUNCTION'S — `AtelierSettingsUpdate`'s recorded argument, one key over.
    `ForbidExtraModel` is `extra="forbid"` and nothing else, so without
    `StrictInt` up there pydantic would coerce `{"submission_deadline_day_of_week":
    true}` to `1` before this function ever ran and an `isinstance` check here
    would be unreachable code.

    What it does own: the DAY RANGE and the TIME SHAPE, both of which reach this
    blob from a hand-edited JSONB as well as from the console — which is why they
    are checked on the way in rather than trusted on the way out.
    """
    unknown = set(scheduling) - _SCHEDULING_FIELDS
    if unknown:
        raise BoutiqueValidationError(f"unknown scheduling keys: {', '.join(sorted(unknown))}")

    day = scheduling.get("submission_deadline_day_of_week")
    if not isinstance(day, int) or isinstance(day, bool) or not 0 <= day <= 6:
        raise BoutiqueValidationError("submission_deadline_day_of_week must be between 0 and 6")

    deadline_time = scheduling.get("submission_deadline_time")
    if not isinstance(deadline_time, str) or not _DEADLINE_TIME.match(deadline_time):
        raise BoutiqueValidationError("submission_deadline_time must be HH:MM")


def validate_appointment_type(
    *,
    name: str,
    duration_minutes: int,
    audience: str,
    deposit_required: bool,
    deposit_amount_agorot: int | None,
    sort_order: int = 0,
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
    if abs(sort_order) > MAX_SORT_ORDER:
        raise BoutiqueValidationError("sort_order is out of bounds")


def validate_weekly_rules(rules: Sequence[WeeklyRuleInput]) -> None:
    if len(rules) > MAX_WEEKLY_RULES:
        raise BoutiqueValidationError(f"at most {MAX_WEEKLY_RULES} weekly windows are allowed")
    for rule in rules:
        if not 0 <= rule.day_of_week <= 6:
            raise BoutiqueValidationError("day_of_week must be between 0 and 6")
        if rule.close_time <= rule.open_time:
            raise BoutiqueValidationError("close_time must be after open_time")
        if not 0 < rule.capacity <= MAX_RULE_CAPACITY:
            raise BoutiqueValidationError(f"capacity must be between 1 and {MAX_RULE_CAPACITY}")
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
    if not 0 <= refundable_until_hours_before <= MAX_REFUNDABLE_HOURS:
        raise BoutiqueValidationError(
            f"refundable_until_hours_before must be between 0 and {MAX_REFUNDABLE_HOURS}"
        )
    if not 0 <= forfeit_percent <= 100:
        raise BoutiqueValidationError("forfeit_percent must be between 0 and 100")
