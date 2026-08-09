from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.auth.schemas import MAX_PASSWORD_LENGTH, DisplayName
from app.schemas import ForbidExtraModel


class OperatorResponse(BaseModel):
    """What `/platform/auth/me` and the login answer. `id` is deliberately absent:
    the console has no per-operator screen, no operator management UI (spec D2 —
    creation and deactivation are CLI-only), and nothing on the wire needs a
    handle to an operator. A field nobody reads is a field somebody eventually
    keys something on."""

    email: str
    display_name: str


# ⚠ NO CLIENT VALIDATION OF THE SLUG BEYOND ITS LENGTH, deliberately. The
# authority is `is_valid_slug` inside `ProvisioningService` — the same function
# the CLI and the tenancy middleware use — and duplicating its regex here would
# create a second definition of "which addresses exist", refusing at a different
# boundary with a different body. The console mirrors the regex for a live
# per-field hint; the server's refusal is what decides.
MAX_SLUG_LENGTH = 63  # one DNS label
MAX_TENANT_NAME_LENGTH = 200  # staff_users.display_name's cap, same argument


class ProvisionRequest(ForbidExtraModel):
    slug: str = Field(min_length=1, max_length=MAX_SLUG_LENGTH)
    name: DisplayName
    owner_email: EmailStr = Field(max_length=320)
    # No MIN length HERE, but the floor itself is real: `_password_problem` in
    # ProvisioningService enforces `MIN_STAFF_PASSWORD_LENGTH` on this field, on
    # `new_password` below, and on the CLI's operator password — one guard where
    # all three callers route through. It lives there and not here because the
    # service owns the failure audit rows, and because a schema-level refusal
    # would answer with a length error the console has no sentence for.
    owner_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class SuspendRequest(ForbidExtraModel):
    slug: str = Field(min_length=1, max_length=MAX_SLUG_LENGTH)


class ResetOwnerPasswordRequest(ForbidExtraModel):
    slug: str = Field(min_length=1, max_length=MAX_SLUG_LENGTH)
    owner_email: EmailStr = Field(max_length=320)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class TenantRow(BaseModel):
    """`TenantSummary` on the wire. No `id`: the console addresses boutiques by
    SLUG on every route, which is what an operator can read off the table and
    off the address bar — and a tenant id on the platform's wire is a handle to
    a whole boutique's data with no screen that needs it."""

    slug: str
    name: str
    status: str
    created_at: datetime


class TenantListResponse(BaseModel):
    tenants: list[TenantRow]
