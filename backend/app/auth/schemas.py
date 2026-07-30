import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.constants import StaffRole
from app.schemas import ForbidExtraModel

# argon2 cost scales with input size; cap it so a giant password can't be a CPU DoS.
MAX_PASSWORD_LENGTH = 4096

# NIST SP 800-63B's floor is 8 with no composition rules. 10, because THIS
# password is chosen by one person and spoken to another (spec D2) — length is
# the only control that survives that trip. Declined with it: composition rules
# (800-63B advises against them and they push an owner toward `Boutique1!`),
# rotation, and a breach-list check (a network dependency on the login path for
# a five-account tenant).
MIN_STAFF_PASSWORD_LENGTH = 10

# staff_users.display_name is unbounded TEXT with no CHECK. 200 matches
# app/boutique/validation.py's MAX_APPOINTMENT_TYPE_NAME_LENGTH.
MAX_DISPLAY_NAME_LENGTH = 200


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class StaffResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str


class StaffMember(BaseModel):
    """The staff row on the wire. `password_hash` and `deleted_at` are absent BY
    CONSTRUCTION — never modelled, so no serializer has to remember to filter
    them, and every row the list carries is live by definition."""

    id: uuid.UUID
    email: str
    display_name: str
    role: str
    created_at: datetime


class CreateStaffRequest(ForbidExtraModel):
    email: EmailStr = Field(max_length=320)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    # Typed as the enum, so an unknown value is a house 422→400 at the boundary
    # and can never reach 0011's CHECK.
    role: StaffRole
    password: str = Field(min_length=MIN_STAFF_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class UpdateStaffRequest(ForbidExtraModel):
    """Every field optional. `email` is deliberately absent: the unique index is
    partial on deleted_at IS NULL, so deactivate + re-create is the remedy for a
    typo'd or changed address, and a login identity must not move under a live
    session (spec D5)."""

    display_name: str | None = Field(default=None, min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    role: StaffRole | None = None
    password: str | None = Field(
        default=None, min_length=MIN_STAFF_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )
    # Required only when the acting staffer changes her OWN password (spec D4).
    # No min_length: a wrong value must be a domain 400 with the console's own
    # Hebrew, not a schema error about its length.
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_LENGTH)
