"""Wire models for the /manage owner-settings API. Requests forbid unknown
keys and carry Field bounds mirroring the migration CHECKs; deeper domain rules
(overlaps, deposit interplay, byte caps, URL/phone formats) live in
app/boutique/validation.py and surface as house-shape 400s."""

import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.boutique.validation import (
    MAX_APPOINTMENT_TYPE_NAME_LENGTH,
    MAX_DEPOSIT_AMOUNT_AGOROT,
    MAX_DURATION_MINUTES,
    MAX_EXCEPTION_NOTE_LENGTH,
    MAX_PROFILE_ADDRESS_LENGTH,
    MAX_PROFILE_DESCRIPTION_LENGTH,
    MAX_PROFILE_MAPS_URL_LENGTH,
    MAX_PROFILE_PHONE_LENGTH,
)
from app.models.constants import AppointmentAudience


class ForbidExtraModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- settings (profile + toggles) ---


class ProfileUpdate(ForbidExtraModel):
    phone: str | None = Field(default=None, max_length=MAX_PROFILE_PHONE_LENGTH)
    address: str | None = Field(default=None, max_length=MAX_PROFILE_ADDRESS_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_PROFILE_DESCRIPTION_LENGTH)
    maps_url: str | None = Field(default=None, max_length=MAX_PROFILE_MAPS_URL_LENGTH)


class TogglesUpdate(ForbidExtraModel):
    deposits_enabled: bool | None = None
    brides_only: bool | None = None


class UpdateSettingsRequest(ForbidExtraModel):
    profile: ProfileUpdate | None = None
    toggles: TogglesUpdate | None = None


class SettingsResponse(BaseModel):
    profile: dict[str, Any]
    toggles: dict[str, Any]


# --- appointment types ---


class CreateAppointmentTypeRequest(ForbidExtraModel):
    name: str = Field(min_length=1, max_length=MAX_APPOINTMENT_TYPE_NAME_LENGTH)
    duration_minutes: int = Field(ge=1, le=MAX_DURATION_MINUTES)
    audience: str = AppointmentAudience.ALL
    deposit_required: bool = False
    deposit_amount_agorot: int | None = Field(default=None, ge=1, le=MAX_DEPOSIT_AMOUNT_AGOROT)
    sort_order: int = 0


class UpdateAppointmentTypeRequest(ForbidExtraModel):
    """Full replace — every field is required so an omitted key can never
    silently clear a value."""

    name: str = Field(min_length=1, max_length=MAX_APPOINTMENT_TYPE_NAME_LENGTH)
    duration_minutes: int = Field(ge=1, le=MAX_DURATION_MINUTES)
    audience: str
    deposit_required: bool
    deposit_amount_agorot: int | None = Field(ge=1, le=MAX_DEPOSIT_AMOUNT_AGOROT)
    sort_order: int


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
    capacity: int = Field(default=1, ge=1)


class ReplaceWeeklyRulesRequest(ForbidExtraModel):
    rules: list[WeeklyRuleRequest]


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
    terms_text: str = Field(min_length=1)
    refundable_until_hours_before: int = Field(ge=0)
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


class OkResponse(BaseModel):
    ok: bool = True
