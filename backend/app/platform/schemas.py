from datetime import datetime
from uuid import UUID

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
# `secrets.token_urlsafe(32)` is 43 characters. The cap is generous rather than
# exact because the join field accepts a PASTED FULL LINK and strips the code
# client-side (design B1) — a paste that arrives unstripped should be refused by
# the code lookup, not by a length error the screen has no sentence for.
MAX_INVITE_CODE_LENGTH = 512


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


# --- F26 invites -------------------------------------------------------------


class CreateInviteRequest(ForbidExtraModel):
    """`ProvisionRequest` MINUS the password (spec D2). The operator pre-assigns
    the address, the trading name and the owner's email; the redeemer contributes
    only a password, which is what makes a leaked link harmless — it can create
    the boutique the operator authorised and nothing else.

    Slug validation stays where F25 put it: `is_valid_slug` inside the service."""

    slug: str = Field(min_length=1, max_length=MAX_SLUG_LENGTH)
    name: DisplayName
    owner_email: EmailStr = Field(max_length=320)


class RevokeInviteRequest(ForbidExtraModel):
    """By id and not by slug, unlike every tenant route. A slug can carry several
    invites over its life (revoke-and-reissue is the whole fix for a mistyped
    one), so the id is the only handle that names exactly one."""

    id: UUID


class InviteRow(BaseModel):
    """⚠ NO `code` AND NO `code_hash`, and that absence is asserted by a test.

    The raw code exists in exactly one response — `InviteCreatedResponse` below,
    once. If it appeared here the console's table would re-render every live
    invite's credential on every mount, which is the whole thing the one-time
    panel is built to prevent."""

    id: UUID
    slug: str
    name: str
    owner_email: str
    created_by: str
    expires_at: datetime
    redeemed_at: datetime | None
    created_at: datetime


class InviteListResponse(BaseModel):
    invites: list[InviteRow]


class InviteCreatedResponse(BaseModel):
    """⚠ THE ONLY RESPONSE IN THIS PRODUCT THAT CARRIES A LIVE INVITE CODE, and
    the only time it is ever on the wire. It is not stored, not logged and not
    audited; a reload of the console cannot recover it (spec D3, design A2)."""

    code: str
    join_url: str
    invite: InviteRow


class InvitePreviewResponse(BaseModel):
    """What an ANONYMOUS caller holding the code sees before spending it: the
    three facts the operator pre-assigned, so a mistyped invite is visible before
    it is claimed and the fix is revoke-and-reissue (D2).

    No `id`, no `created_by`, no `expires_at`: none of them is actionable by the
    redeemer, and every field here is disclosed to a caller who authenticated
    with nothing but a 256-bit secret."""

    slug: str
    name: str
    owner_email: str


class RedeemInviteRequest(ForbidExtraModel):
    code: str = Field(min_length=1, max_length=MAX_INVITE_CODE_LENGTH)
    # No MIN length HERE for `ProvisionRequest`'s reason, restated because this
    # is the one form a non-operator fills in: `_password_problem` in the service
    # owns the floor, because the service owns the failure audit row and because
    # a schema-level 422 has no Hebrew sentence on the join screen.
    owner_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class RedeemInviteResponse(BaseModel):
    slug: str
    manage_url: str
