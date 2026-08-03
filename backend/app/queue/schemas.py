"""Wire shapes for the public check-in surface. Narrow models, never inherited
from a richer manage schema — the F10 rule.

Generous ceilings here, not product policy: the real bounds (the 80-char name,
the Israeli-mobile shape, the two visit types) live in `validation.py` and
answer a clean domain 400. The `Field` limits only stop a megabyte body from
reaching the service layer.
"""

import datetime
import uuid

from pydantic import BaseModel, Field

from app.notifications.schemas import MAX_PHONE_INPUT_LENGTH
from app.schemas import ForbidExtraModel

MAX_NAME_INPUT_LENGTH = 200
# Two literals of five and seven characters; the bound is the CHECK, not this.
MAX_VISIT_TYPE_INPUT_LENGTH = 32


class CheckinCreateRequest(ForbidExtraModel):
    """ForbidExtraModel, the house convention on a public write: an unknown key
    is a 400 rather than a silently ignored field."""

    name: str = Field(min_length=1, max_length=MAX_NAME_INPUT_LENGTH)
    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
    visit_type: str = Field(min_length=1, max_length=MAX_VISIT_TYPE_INPUT_LENGTH)
    # Absent is false, and unchecked is the default on the form: Amendment 13's
    # minimisation duty is why she stays a person in a queue rather than a
    # marketing contact unless she says otherwise.
    marketing_opt_in: bool = False


class PositionRequest(ForbidExtraModel):
    """The ticket id is in the BODY and never in a path or query parameter: a
    GET would put the capability into every access log, proxy trace and Referer
    header on the path, once every five seconds for the length of her visit."""

    ticket_id: uuid.UUID


class TicketView(BaseModel):
    """The WHOLE body of both public routes, and it is four fields.

    The create answers this and only this, 201, every time — there is no
    envelope and no null branch, because Ruling 3 removed server-side dedup and
    the response is IDENTICAL whether or not that phone was already in today's
    queue.

    What it deliberately omits, each for its own reason: her NAME (she typed
    it; echoing it back over an anonymous endpoint keyed by a guessable-in-
    principle id is a PII disclosure for zero product value), her PHONE (same,
    worse), her VISIT_TYPE (nothing renders it), CREATED_AT (the freshness
    signal is the client's own last-fetch time), MARKETING_OPT_IN_AT (nothing
    in F33 reads consent), anything about any OTHER ticket, and every operator
    provenance column — tenant_id, queue_day, skip_count, requeued_at.
    """

    # The capability. Issued exactly once, at creation, in the response to the
    # request that created it, and by no other server path ever.
    id: uuid.UUID
    status: str
    # 1-based among this ticket's OWN queue_day's waiting tickets; null unless
    # the ticket is itself waiting.
    position: int | None
    # ISO-8601 UTC once a manager calls her forward. F58 writes it; F33 reads it
    # so the screen can say "go to the counter" instead of showing 1 forever.
    called_at: datetime.datetime | None


class CheckinQrResponse(BaseModel):
    """The whole body of `GET /manage/checkin-qr`, and it is two strings.

    JSON carrying the SVG SOURCE, not an `image/svg+xml` response.
    `apps/manage/src/api.ts`'s `apiFetch<T>` unconditionally ends in
    `(await response.json()) as T`; the page needs the human-readable URL as
    text anyway, because a printed QR with no legible URL beside it strands
    anyone whose camera fails; and an image response would be the first
    non-JSON body in the entire API, with `nosniff` on every response and no
    precedent to copy if the media type came out wrong.

    Nothing here is secret. The URL is printed on a sign in the shop window.
    """

    checkin_url: str
    # Rendered as `<img src={"data:image/svg+xml;utf8," + encodeURIComponent(...)}>`
    # — an image context, so no scripts and no external references, which is
    # strictly safer than an inline <svg> or dangerouslySetInnerHTML.
    qr_svg: str
