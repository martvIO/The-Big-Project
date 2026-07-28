"""Wire shapes for the public OTP surface. None of these subclass anything from
a manage schema, per the F10 rule — the public wire is defined by narrow models,
never by inheritance from a richer one."""

import datetime

from pydantic import BaseModel, Field

# Generous ceilings, not formats: real validation (charset, Israeli-mobile
# shape) lives in normalize_israeli_mobile, and the DB never stores a raw value.
# These only stop a megabyte body from reaching the service layer.
MAX_PHONE_INPUT_LENGTH = 32
MAX_CODE_INPUT_LENGTH = 16


class OtpSendRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)


class OtpVerifyRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
    code: str = Field(min_length=1, max_length=MAX_CODE_INPUT_LENGTH)


class OtpVerifyResponse(BaseModel):
    verification_token: str
    expires_at: datetime.datetime
