"""Wire models for the /manage owner-settings API. Requests forbid unknown
keys and carry Field bounds mirroring the migration CHECKs; deeper domain rules
(overlaps, deposit interplay, byte caps, URL/phone formats) live in
app/boutique/validation.py and surface as house-shape 400s."""

import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.atelier.stages import MAX_WEEKLY_CAPACITY_HOURS
from app.boutique.validation import (
    MAX_APPOINTMENT_TYPE_NAME_LENGTH,
    MAX_DEPOSIT_AMOUNT_AGOROT,
    MAX_DURATION_MINUTES,
    MAX_EXCEPTION_NOTE_LENGTH,
    MAX_PROFILE_ADDRESS_LENGTH,
    MAX_PROFILE_DESCRIPTION_LENGTH,
    MAX_PROFILE_ESSENCE_LENGTH,
    MAX_PROFILE_INSTAGRAM_LENGTH,
    MAX_PROFILE_MAPS_URL_LENGTH,
    MAX_PROFILE_PHONE_LENGTH,
    MAX_REFUNDABLE_HOURS,
    MAX_RULE_CAPACITY,
    MAX_SORT_ORDER,
    MAX_TERMS_TEXT_BYTES,
    MAX_WEEKLY_RULES,
)
from app.models.constants import AppointmentAudience, EffortBand

# Both now live in app/schemas.py so app/catalog/ does not import a boutique
# schema. Re-exported here — the `as` form is the re-export idiom ruff accepts —
# so no import site and no wire shape changed.
from app.schemas import ForbidExtraModel as ForbidExtraModel
from app.schemas import OkResponse as OkResponse

# --- settings (profile + toggles) ---


class ProfileUpdate(ForbidExtraModel):
    phone: str | None = Field(default=None, max_length=MAX_PROFILE_PHONE_LENGTH)
    address: str | None = Field(default=None, max_length=MAX_PROFILE_ADDRESS_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_PROFILE_DESCRIPTION_LENGTH)
    maps_url: str | None = Field(default=None, max_length=MAX_PROFILE_MAPS_URL_LENGTH)
    essence: str | None = Field(default=None, max_length=MAX_PROFILE_ESSENCE_LENGTH)
    instagram: str | None = Field(default=None, max_length=MAX_PROFILE_INSTAGRAM_LENGTH)


class TogglesUpdate(ForbidExtraModel):
    deposits_enabled: bool | None = None
    brides_only: bool | None = None


class AtelierSettingsUpdate(ForbidExtraModel):
    """⚠ A FULL REPLACE OF THE WHOLE `atelier` BLOCK — every field REQUIRED, no
    default anywhere. `UpdateAppointmentTypeRequest`'s shipped rule, and here it
    is load-bearing for a second reason: `merge_settings` merges at the TOP LEVEL
    ONLY, so a patch carrying a PARTIAL `atelier` object replaces the whole thing
    and deletes the key it did not name. One writer, one dialog, one save, both
    keys, always — structural rather than a convention.

    ⚠ `StrictInt`, NOT `int`, AND THE ANTI-`bool` RULE IS VACUOUS WITHOUT IT.
    `ForbidExtraModel` sets `extra="forbid"` and NOTHING ELSE (`app/schemas.py:13-18`
    — there is no `strict=True` on it), so a plain `dict[EffortBand, int]`
    COERCES before any validator runs: `{"half_day": true}` becomes `1`, `"300"`
    becomes `300`, `30.0` becomes `30`. `validate_atelier_settings` would then
    never see a bool, its type check would be unreachable code, and a ONE-MINUTE
    «חצי יום» would be a 200 — silently understating every load bar downstream.

    Keying on `EffortBand` rather than `str` also makes an UNKNOWN band key
    pydantic's refusal; the validator still owns the MISSING one, which no
    request model can see.
    """

    effort_bands: dict[EffortBand, StrictInt]
    # `null` CLEARS the boutique's default. Required with no schema default:
    # `AssignTicketRequest.staff_user_id`'s rule — an optional field would make a
    # bands-only save silently clear it, which is the shallow-merge trap above
    # wearing a different hat.
    default_weekly_capacity_hours: StrictInt | None = Field(ge=0, le=MAX_WEEKLY_CAPACITY_HOURS)


class UpdateSettingsRequest(ForbidExtraModel):
    profile: ProfileUpdate | None = None
    toggles: TogglesUpdate | None = None
    atelier: AtelierSettingsUpdate | None = None


class SettingsResponse(BaseModel):
    profile: dict[str, Any]
    toggles: dict[str, Any]
    # F42. On the READ so the console's settings dialog opens with the tenant's
    # own bands and default already in hand and costs no second request.
    atelier: dict[str, Any]


# --- appointment types ---


class CreateAppointmentTypeRequest(ForbidExtraModel):
    name: str = Field(min_length=1, max_length=MAX_APPOINTMENT_TYPE_NAME_LENGTH)
    duration_minutes: int = Field(ge=1, le=MAX_DURATION_MINUTES)
    audience: str = AppointmentAudience.ALL
    deposit_required: bool = False
    deposit_amount_agorot: int | None = Field(default=None, ge=1, le=MAX_DEPOSIT_AMOUNT_AGOROT)
    sort_order: int = Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)


class UpdateAppointmentTypeRequest(ForbidExtraModel):
    """Full replace — every field is required so an omitted key can never
    silently clear a value."""

    name: str = Field(min_length=1, max_length=MAX_APPOINTMENT_TYPE_NAME_LENGTH)
    duration_minutes: int = Field(ge=1, le=MAX_DURATION_MINUTES)
    audience: str
    deposit_required: bool
    deposit_amount_agorot: int | None = Field(ge=1, le=MAX_DEPOSIT_AMOUNT_AGOROT)
    sort_order: int = Field(ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)


class AppointmentTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    duration_minutes: int
    audience: str
    deposit_required: bool
    deposit_amount_agorot: int | None
    sort_order: int


# --- availability ---


class WeeklyRuleRequest(ForbidExtraModel):
    day_of_week: int = Field(ge=0, le=6)
    open_time: datetime.time
    close_time: datetime.time
    capacity: int = Field(default=1, ge=1, le=MAX_RULE_CAPACITY)


class ReplaceWeeklyRulesRequest(ForbidExtraModel):
    rules: list[WeeklyRuleRequest] = Field(max_length=MAX_WEEKLY_RULES)


class AvailabilityRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    day_of_week: int
    open_time: datetime.time
    close_time: datetime.time
    capacity: int


class CreateAvailabilityExceptionRequest(ForbidExtraModel):
    date: datetime.date
    open_time: datetime.time | None = None
    close_time: datetime.time | None = None
    note: str | None = Field(default=None, max_length=MAX_EXCEPTION_NOTE_LENGTH)


class AvailabilityExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: datetime.date
    open_time: datetime.time | None
    close_time: datetime.time | None
    note: str | None


class AvailabilityResponse(BaseModel):
    rules: list[AvailabilityRuleResponse]
    exceptions: list[AvailabilityExceptionResponse]


# --- cancellation-policy terms ---


class CreateTermsRequest(ForbidExtraModel):
    # Char cap blocks multi-MB bodies at the schema; the byte-precise 50 KB cap
    # (Hebrew is 2 bytes/char) stays in validate_terms.
    terms_text: str = Field(min_length=1, max_length=MAX_TERMS_TEXT_BYTES)
    refundable_until_hours_before: int = Field(ge=0, le=MAX_REFUNDABLE_HOURS)
    forfeit_percent: int = Field(default=100, ge=0, le=100)


class TermsVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    terms_text: str
    refundable_until_hours_before: int
    forfeit_percent: int
    created_by: UUID
    created_at: datetime.datetime


class TermsHistoryResponse(BaseModel):
    current: TermsVersionResponse | None
    versions: list[TermsVersionResponse]
    total: int
    offset: int
    limit: int
