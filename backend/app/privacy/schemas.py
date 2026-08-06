"""The privacy surface's wire shapes.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=`
(the shipped house form — `dashboard/schemas.py:3-5`), and `ForbidExtraModel`
on every request.

**The export response's omissions are STRUCTURAL, not filtered late.**
`message_log.provider_message_id` and `message_log.error` have no field on
`ExportedMessage` at any depth, so no future edit to the service can leak them
by forgetting a `del`. They are operator diagnostics about a carrier, not the
subject's personal data, and F53's `SmsLogRow` already settled the posture for
the console. `body` IS included: it is the message she received, and a §13
access request that withheld it would be answering a different question.
"""

import datetime
import uuid

from pydantic import BaseModel, Field, model_validator

from app.privacy.validation import MAX_PHONE_INPUT_CHARS
from app.schemas import ForbidExtraModel


class PrivacyResponse(BaseModel):
    """Everything the manage privacy section renders, in one GET.

    The two `*_is_default` flags are what let the console say "this is the
    platform wording" instead of making the owner diff two documents by eye.

    `subprocessors_text`, `disclaimer_text` and `erase_reason_hint` ride along
    rather than being hardcoded in the frontend, and that is the same rule F33's
    `checkin.notice` comment states: **no second copy may exist anywhere**. All
    three are platform Hebrew whose approved source is `copy.md`; a duplicate in
    `he.ts` would be a second place for a legal string to drift, and the
    sub-processor list drifting is exactly what D14 exists to prevent.
    """

    notice_text: str
    notice_is_default: bool
    dpa_text: str
    dpa_is_default: bool
    subprocessors_text: str
    disclaimer_text: str
    erase_reason_hint: str


class PrivacyUpdate(ForbidExtraModel):
    """BOTH KEYS REQUIRED, and that is a correctness requirement rather than a
    style choice (D16).

    `merge_settings` is one `settings = settings || :patch::jsonb`, and `||`
    replaces WHOLE top-level keys. A patch of `{"privacy": {"notice_text": X}}`
    therefore replaces the entire `privacy` object and `resolve_privacy` reads
    the now-absent `dpa_text` as "use the platform default" — so an owner who
    overrode her DPA clause on Monday and edits only her notice on Tuesday
    silently loses Monday's clause, with no error anywhere and un-reviewed
    platform Hebrew back on `/privacy`.

    Required-with-a-nullable-type is exactly the shape that expresses it: `None`
    is a VALUE the owner can send (revert this field to the default), and
    omitting the key is a 422. `AtelierSettingsUpdate` is the shipped precedent
    for the same problem one level down.

    ⚠ Any future third field under `privacy` must either also be required here
    or force the nested merge `settings || jsonb_build_object('privacy',
    coalesce(settings->'privacy','{}'::jsonb) || :patch)`. The cost is recorded
    rather than discovered.
    """

    notice_text: str | None
    dpa_text: str | None


class SubjectExportRequest(ForbidExtraModel):
    """The §13 access request, and ALSO the lookup step for the other two routes
    (D17): its `subject.id` is the `customer_id` they take.

    `reason` is optional here and audited, same rule and same cap as the erase's.

    The cap is a TRUST-BOUNDARY bound, not a format rule.
    `normalize_israeli_mobile` runs a `fullmatch` and a `re.sub` over whatever
    arrives, so an unbounded field regexes a multi-megabyte body before
    rejecting it — every other free-text field on this surface is capped
    (8 KB documents, 500-byte reason) and this one was the hole.
    """

    phone: str = Field(max_length=MAX_PHONE_INPUT_CHARS)
    reason: str | None = None


class ExportedSubject(BaseModel):
    """Her row, including the CRM columns F53 added (plan DR-12). `notes` is a
    free-text paragraph the console writes ABOUT her and accretes across a year
    of fittings — it is her personal data held by the controller and §13 reaches
    it, so an export that withheld it would be incomplete."""

    id: uuid.UUID
    phone: str
    name: str
    created_at: datetime.datetime
    notes: str | None
    tags: list[str]
    marketing_consent_at: datetime.datetime | None
    marketing_consent_source: str | None
    marketing_consent_withdrawn_at: datetime.datetime | None
    erased_at: datetime.datetime | None


class ExportedBooking(BaseModel):
    """`manage_token_hash` and `seat_index` are deliberately absent — a token
    hash is a credential, not personal data, and the seat is the boutique's
    room-management detail. `checked_in_at` IS here (F34's column, plan DR-15):
    it records that she attended, which is a fact about her."""

    id: uuid.UUID
    starts_at: datetime.datetime
    status: str
    # F50, and it ships for the SAME reason the nullable terms pair below does.
    # Making those two nullable put an ambiguity into this payload that the owner
    # console was given the discriminator for and the Privacy Protection Authority
    # — the audience F20 names for this route — was not: a null version alone
    # cannot say whether nobody accepted anything or a storefront booking lost its
    # evidence. `source` is what tells those apart, in the CHECK and here.
    source: str
    appointment_type_name: str
    dress_name: str | None
    dress_size: str | None
    notes: str | None
    attendance_confirmed_at: datetime.datetime | None
    checked_in_at: datetime.datetime | None
    # NULLABLE since F50: a walk-in booking genuinely has no terms evidence, and
    # the §13 answer must SHOW THAT ABSENCE rather than invent a version or refuse
    # to serialise. `ExportedBooking(...)` is constructed explicitly in the service,
    # and a plain BaseModel validates on construction — non-optional here is a
    # ValidationError, i.e. a 500 on the one route the Privacy Protection Authority
    # is the audience for.
    terms_version_accepted: int | None
    terms_accepted_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    cancelled_by: str | None


class ExportedMessage(BaseModel):
    """FOUR fields. `provider_message_id`, `error`, `phone` and `booking_id` are
    absent BY CONSTRUCTION — there is no field to populate, so the disclosure
    walk in `test_privacy_api.py` is asserting a property of this class rather
    than of one code path through the service."""

    kind: str
    status: str
    created_at: datetime.datetime
    body: str


class ExportedQueueTicket(BaseModel):
    """Her walk-in check-ins (DR-9's fourth collection point). `queue_tickets`
    holds a real name and a normalised E.164 number, so a §13 answer that
    omitted it would understate what the boutique holds about a bride who both
    booked online and walked in.

    `skip_count`, `called_at` and `requeued_at` are absent for the reason
    `ExportedBooking` omits `seat_index` — they are the boutique's
    queue-management state, not a fact about her.
    """

    id: uuid.UUID
    queue_day: datetime.date
    created_at: datetime.datetime
    name: str
    phone: str
    visit_type: str
    status: str
    marketing_opt_in_at: datetime.datetime | None


class ExportedWaitlistEntry(BaseModel):
    """Her booking-waitlist joins (F22, spec D4's enumerated set): the day she
    asked about, the appointment type's NAME (the id is boutique bookkeeping and
    says nothing to the subject), the entry's status and when she joined.

    No `phone` — it is the lookup key the whole export is answered by — and no
    `id`: there is no customer-side management surface for it to address.
    """

    day: datetime.date
    # None if the type row is gone entirely; an ARCHIVED type still names what
    # she asked for, so the resolution below does not filter on deleted_at.
    appointment_type_name: str | None
    status: str
    created_at: datetime.datetime


class ExportedTerms(BaseModel):
    """What she actually agreed to, at the version she agreed to it. The
    boutique's terms are hers to have a copy of — she accepted them."""

    version: int
    terms_text: str
    refundable_until_hours_before: int
    forfeit_percent: int


class SubjectExportResponse(BaseModel):
    subject: ExportedSubject
    bookings: list[ExportedBooking]
    messages: list[ExportedMessage]
    queue_tickets: list[ExportedQueueTicket]
    waitlist_entries: list[ExportedWaitlistEntry]
    accepted_terms: list[ExportedTerms]


class SubjectEraseRequest(ForbidExtraModel):
    """Keyed on `customer_id`, never on the phone (D17). Step 2 of the erase
    overwrites `customers.phone` and `by_phone` is exact equality, so a
    phone-keyed erase destroys its own lookup key: the documented idempotent
    repeat would be unreachable, and the two available answers were a 404 that
    contradicts the contract or a 200-with-zero-counts that cannot tell "already
    done" from "you mistyped a digit" — the latter writing a
    `privacy_subject_erased` audit row for a subject who was never touched,
    which is a fabricated §14 record on the one path where the record IS the
    deliverable."""

    customer_id: uuid.UUID
    reason: str | None = None


class SubjectEraseResponse(BaseModel):
    """Counts, so the console can show what happened, and `already_erased` so a
    second tap reads as "done" rather than as "nothing happened, try again".

    All five counts are zero on the idempotent repeat, which is a TRUE statement
    about that call rather than a fiction: the row was already scrubbed.
    """

    customer_id: uuid.UUID
    already_erased: bool
    bookings_scrubbed: int
    messages_scrubbed: int
    queue_tickets_scrubbed: int
    waitlist_entries_scrubbed: int
    otp_codes_purged: int
    scheduled_messages_purged: int


class MarketingWithdrawRequest(ForbidExtraModel):
    """EXACTLY ONE of `customer_id` / `phone` (plan DR-10).

    Two arms because there are two stores. A bride who booked online has a
    `customers` row and her consent lives there; a walk-in has only a
    `queue_tickets` row, because F33 never writes `customers` and F20 declines
    to promote an unverified counter opt-in into provable consent. The notice
    she was shown at the counter promises she may revoke — so without the phone
    arm the promise is unkeepable for exactly the women who cannot be looked up.

    The phone arm NEVER writes `customers`: nothing is laundered, which is the
    whole point of the split.
    """

    customer_id: uuid.UUID | None = None
    #: Same trust-boundary cap as `SubjectExportRequest.phone` — see its docstring.
    phone: str | None = Field(default=None, max_length=MAX_PHONE_INPUT_CHARS)

    @model_validator(mode="after")
    def _exactly_one(self) -> "MarketingWithdrawRequest":
        if (self.customer_id is None) == (self.phone is None):
            raise ValueError("Send exactly one of customer_id or phone.")
        return self


class MarketingWithdrawResponse(BaseModel):
    """`changed` is false for a subject who had no live consent — including a
    phone with no ticket at all, which is deliberately NOT a 404: a walk-in who
    never ticked the box and a number the boutique has never seen are the same
    outcome she asked for, and telling them apart would turn a front-desk
    revocation into a presence oracle over the queue."""

    changed: bool
