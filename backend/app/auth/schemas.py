import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.boutique.validation import MAX_PROFILE_PHONE_LENGTH
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

# Stripped BEFORE the bounds, which is the whole point: `Field(min_length=1)`
# alone admits "   ", and every sibling name field in this backend rejects blank
# (boutique/validation.py, catalog/validation.py, booking/validation.py — the
# first of which is where MAX_DISPLAY_NAME_LENGTH itself was borrowed from). A
# whitespace name renders as an empty <bdi> in the console, identifiable only by
# its email. Stripping additionally makes " Dana" and "Dana" one name, so
# StaffService.update's no-op comparison cannot be fooled by an edge space.
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH),
]


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
    # F38. `phone` is a CONTACT field and never a login identifier (spec C1) —
    # Interview Q11 was overridden by F31, staff sign in with email + password,
    # and no auth path reads this.
    phone: str | None
    # `date`, never an instant: "her start date" and "her last day" are Jerusalem
    # CALENDAR days, and an instant would make the retention boundary depend on
    # what o'clock somebody pressed the button.
    start_date: date | None
    # Present on the wire but NOT writable — it is set by DELETE (offboarding),
    # so the console can render it on a row it is showing rather than guessing
    # from `deleted_at`, which the list never carries.
    last_day: date | None
    shift_manager_eligible: bool
    # Signed per read with the degrade-to-null posture: a storage outage
    # serialises `null` here and never fails the list (app/auth/photo.py).
    photo_url: str | None
    # The console's cache key. It changes exactly when the image behind the URL
    # changes, which is what lets the floor board pin a signed URL across its
    # five-second poll instead of re-downloading every face on every tick.
    photo_confirmed_at: datetime | None


class CreateStaffRequest(ForbidExtraModel):
    email: EmailStr = Field(max_length=320)
    display_name: DisplayName
    # Typed as the enum, so an unknown value is a house 422→400 at the boundary
    # and can never reach 0011's CHECK.
    role: StaffRole
    password: str = Field(min_length=MIN_STAFF_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    # Length only. The CHARSET rule is `validate_phone`'s, applied in the
    # service, so the console gets one domain 400 with its own Hebrew rather than
    # a schema error about a regex — and so the boutique profile's number and a
    # staffer's number keep agreeing through exactly one gate.
    phone: str | None = Field(default=None, max_length=MAX_PROFILE_PHONE_LENGTH)
    start_date: date | None = None
    # Defaults to False rather than None: an unanswered "may she be slotted as
    # shift manager" is a no, not a third state. F38 stores it and enforces
    # nothing — F40 is its only consumer (spec O4).
    shift_manager_eligible: bool = False


class UpdateStaffRequest(ForbidExtraModel):
    """Every field optional. `email` is deliberately absent: the unique index is
    partial on deleted_at IS NULL, so deactivate + re-create is the remedy for a
    typo'd or changed address, and a login identity must not move under a live
    session (spec D5)."""

    display_name: DisplayName | None = None
    role: StaffRole | None = None
    password: str | None = Field(
        default=None, min_length=MIN_STAFF_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH
    )
    # Required only when the acting staffer changes her OWN password (spec D4).
    # No min_length: a wrong value must be a domain 400 with the console's own
    # Hebrew, not a schema error about its length.
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_LENGTH)
    # ⚠ `""` IS MEANINGFUL HERE and is the one way to REMOVE a number: `None` is
    # already spoken for by this API's send-only-what-moved rule, so without it a
    # staffer who asks for her number to come off the system could not be obliged
    # until the seven-year scrub. An emptied `<input>` posts `""` natively, so
    # this needs no sentinel type anywhere in the stack. NO `min_length`, for
    # that reason.
    phone: str | None = Field(default=None, max_length=MAX_PROFILE_PHONE_LENGTH)
    # `start_date` has NO such clear arm, and the asymmetry is deliberate rather
    # than an oversight: a blank date input is indistinguishable from an absent
    # one in JSON, and nothing in the product needs to un-record a start date.
    # ponytail: add a clear when somebody actually needs one.
    start_date: date | None = None
    # `bool | None` and not `bool`: on a PATCH, absent must mean "leave it
    # alone", and a `False` default would silently un-tick eligibility on every
    # save of any other field.
    shift_manager_eligible: bool | None = None


class StaffPhotoPresignRequest(ForbidExtraModel):
    """The declared type and size. Both are CLAIMS the client makes and neither
    is trusted: the type is checked against the accepted set here, pinned into
    the POST policy, re-read off the stored object at confirm and matched against
    its magic bytes; the size is pinned as an EXACT content-length range in the
    policy, so the browser may post precisely what it declared and nothing else.
    """

    content_type: str = Field(max_length=100)
    byte_size: int = Field(ge=0)


class StaffPhotoPresignResponse(BaseModel):
    url: str
    # Bearer material for its whole TTL — carries `policy` and `x-amz-signature`.
    # Never logged, never in an error.
    fields: dict[str, str]
    expires_in: int
    max_bytes: int
