"""F20 fast API tests: the five /manage/privacy routes' wiring, the 401s, the
per-role matrix Gate 1 Q4 rules, the D16 whole-object contract, the disclosure
walk over the export model and the three rate-limit budgets.

A duck-typed `FakePrivacyService` on `app.state.privacy_service` plus a
hardcoded `TenantContext` resolver, no database (test_customers_api.py style).

**This module is the shadowing guard for the ELEVENTH /manage router**, and it
owns `PRIVACY_ROUTES` — which `test_staff_role_gating.py` imports rather than
this module reaching into that one, because the dependency cannot run the other
way (that module already imports every API test module).

⚠ **`PRIVACY_ROUTES` is deliberately NOT added to `test_boutique_api.ROUTES`.**
That table is the boutique router's own, and `_client()` there wires
`app.state.boutique_service` unconditionally while wiring its catalog/floor/
atelier fakes only on request — so a privacy route in that list would be reached
by the unknown-role walk with `app.state.privacy_service` unset and answer an
`AttributeError` rather than a 403, which is exactly the decoy-gate blow-up
those comments say they want. The shift-manager walk imports this table and
gets a `privacy=` fake; the unknown-role walk imports it and deliberately does
not.
"""

import datetime
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import MessageKind, MessageStatus, StaffRole
from app.privacy.schemas import (
    ExportedBooking,
    ExportedMessage,
    ExportedQueueTicket,
    ExportedSubject,
    ExportedTerms,
    MarketingWithdrawResponse,
    PrivacyResponse,
    SubjectEraseResponse,
    SubjectExportResponse,
)
from app.privacy.service import (
    SubjectHasActiveBookingError,
    SubjectNotFoundError,
    privacy_response,
)
from app.privacy.text import (
    PLATFORM_DISCLAIMER_HE,
    PLATFORM_NOTICE_HE,
    PLATFORM_SUBPROCESSORS_HE,
    resolve_privacy,
)
from app.privacy.validation import (
    MARKETING_WITHDRAW_MAX_PER_WINDOW,
    MAX_PRIVACY_TEXT_BYTES,
    SUBJECT_ERASE_MAX_PER_WINDOW,
    SUBJECT_EXPORT_MAX_PER_WINDOW,
)
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"
CUSTOMER_ID = uuid.uuid4()
CREATED_AT = datetime.datetime(2026, 1, 4, 8, 0, tzinfo=datetime.UTC)
STARTS_AT = datetime.datetime(2026, 6, 1, 9, 0, tzinfo=datetime.UTC)

PRIVACY_GET = ("GET", "/manage/privacy")
PRIVACY_PUT = ("PUT", "/manage/privacy")
SUBJECT_EXPORT = ("POST", "/manage/privacy/subject-export")
SUBJECT_ERASE = ("POST", "/manage/privacy/subject-erase")
MARKETING_WITHDRAW = ("POST", "/manage/privacy/marketing-withdraw")

PUT_BODY: dict[str, Any] = {"notice_text": None, "dpa_text": None}

# The FIVE, in the FLOOR_ROUTES / ATELIER_ROUTES / GATEWAY_ROUTES idiom:
# concrete spellings with real bodies, for the HTTP walks. Eleven routers now
# mount prefix="/manage", so a duplicated (method, path) would silently win or
# lose on include order — a 404 in the walk below is what catches a shadow.
PRIVACY_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    (*PRIVACY_GET, None),
    (*PRIVACY_PUT, PUT_BODY),
    (*SUBJECT_EXPORT, {"phone": "0501234567"}),
    (*SUBJECT_ERASE, {"customer_id": str(CUSTOMER_ID)}),
    (*MARKETING_WITHDRAW, {"customer_id": str(CUSTOMER_ID)}),
]

SPEC_ERROR_CODES = {
    "NOT_AUTHENTICATED",
    # ⚠ The 409 the console MAPS. It reaches HTTP through main.py's exception
    # handler and nothing asserted the spelling over the wire, so the frontend
    # shortened it to `BOOKING_ACTIVE` and rendered the API's English sentence
    # in an RTL Hebrew console while the Hebrew stayed a dead key.
    "SUBJECT_HAS_ACTIVE_BOOKING",
    "NOT_AUTHORIZED",
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "TOO_MANY_ATTEMPTS",
    "CSRF_ORIGIN_MISMATCH",
}

# ⚠ `phone` is deliberately NOT here: the export SHIPS her phone, because a §13
# access request that withheld the identifier the whole record is keyed on would
# be answering a different question. `provider_message_id` and `error` are the
# two this walk exists for — they are operator diagnostics about a carrier, they
# have no field on `ExportedMessage` at any depth, and this assertion is what
# makes that structural rather than incidental.
EXPORT_FORBIDDEN_KEYS = frozenset(
    {
        "provider_message_id",
        "error",
        "manage_token_hash",
        "password_hash",
        "tenant_id",
        "deleted_at",
        "code_hash",
        "seat_index",
    }
)

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole. Duplicated because that module
# imports the API test modules, so the dependency cannot run the other way.
UNKNOWN_ROLE = "no-such-role"


def _all_keys(node: Any) -> Iterator[str]:
    """Every key at every depth — test_dashboard_api.py's walker, reused."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_keys(item)


def _export() -> SubjectExportResponse:
    """A FULLY POPULATED export — one booking AND one message, which is what
    ARMS the disclosure walk.

    Against `bookings: []` / `messages: []` the "no `provider_message_id` at any
    depth" assertion passes on nothing at all, exactly as
    `test_storefront_api.py:103`'s `secret_note` row exists to arm that file's
    equivalent. Deleting either row here makes this module's disclosure test
    vacuous while staying green, which is why they are here.
    """
    return SubjectExportResponse(
        subject=ExportedSubject(
            id=CUSTOMER_ID,
            phone="+972501234567",
            name="מיכל לוי",
            created_at=CREATED_AT,
            notes="מגיעה עם אמא",
            tags=["VIP"],
            marketing_consent_at=CREATED_AT,
            marketing_consent_source="booking_form",
            marketing_consent_withdrawn_at=None,
            erased_at=None,
        ),
        bookings=[
            ExportedBooking(
                id=uuid.uuid4(),
                starts_at=STARTS_AT,
                status="confirmed",
                appointment_type_name="מדידה ראשונה",
                dress_name="Aurora",
                dress_size="38",
                notes="מגיעה עם אמא",
                attendance_confirmed_at=None,
                checked_in_at=STARTS_AT,
                terms_version_accepted=3,
                terms_accepted_at=CREATED_AT,
                cancelled_at=None,
                cancelled_by=None,
            )
        ],
        messages=[
            ExportedMessage(
                kind=MessageKind.CONFIRMATION.value,
                status=MessageStatus.SENT.value,
                created_at=CREATED_AT,
                body="הפגישה שלך אושרה",
            )
        ],
        queue_tickets=[
            ExportedQueueTicket(
                id=uuid.uuid4(),
                queue_day=CREATED_AT.date(),
                created_at=CREATED_AT,
                name="מיכל לוי",
                phone="+972501234567",
                visit_type="bride",
                status="done",
                marketing_opt_in_at=CREATED_AT,
            )
        ],
        accepted_terms=[
            ExportedTerms(
                version=3,
                terms_text="תנאי הבוטיק",
                refundable_until_hours_before=48,
                forfeit_percent=100,
            )
        ],
    )


class FakeAuthService:
    def __init__(self, role: str = StaffRole.OWNER.value) -> None:
        # The session's tenant_id DELIBERATELY disagrees with the host-resolved
        # TENANT.id, so a handler reaching for StaffContext.tenant_id is
        # distinguishable from a correct one.
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=uuid.uuid4(),
            email="owner@bella.example",
            display_name="Owner",
            role=role,
        )

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


class FakePrivacyService:
    """Duck-typed PrivacyService: records what every route was called with and
    answers one fully populated payload.

    ⚠ It carries REAL `FixedWindowRateLimiter` instances and really spends them,
    because the budgets are what the 429 tests are about — a fake that only
    recorded calls would make those tests assert nothing.
    """

    def __init__(
        self, *, missing: bool = False, has_active_booking: bool = False, clock: Any = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.missing = missing
        self.has_active_booking = has_active_booking
        tick = clock if clock is not None else (lambda: 0.0)
        self.export_limiter = FixedWindowRateLimiter(SUBJECT_EXPORT_MAX_PER_WINDOW, 3600.0, tick)
        self.erase_limiter = FixedWindowRateLimiter(SUBJECT_ERASE_MAX_PER_WINDOW, 3600.0, tick)
        self.withdraw_limiter = FixedWindowRateLimiter(
            MARKETING_WITHDRAW_MAX_PER_WINDOW, 3600.0, tick
        )

    def _spend(self, limiter: FixedWindowRateLimiter, tenant_id: uuid.UUID) -> None:
        from app.privacy.validation import PrivacyThrottledError

        key = f"privacy:{tenant_id}"
        if limiter.is_blocked(key):
            raise PrivacyThrottledError
        limiter.record_failure(key)

    async def update_privacy(
        self, tenant_id: uuid.UUID, *, notice_text: str | None, dpa_text: str | None
    ) -> PrivacyResponse:
        self.calls.append(
            {
                "route": "update",
                "tenant_id": tenant_id,
                "notice_text": notice_text,
                "dpa_text": dpa_text,
            }
        )
        merged = {"privacy": {"notice_text": notice_text or "", "dpa_text": dpa_text or ""}}
        return privacy_response(resolve_privacy(merged))

    async def export_subject(
        self, tenant_id: uuid.UUID, *, raw_phone: str, actor: StaffContext, reason: str | None
    ) -> SubjectExportResponse:
        self.calls.append(
            {
                "route": "export",
                "tenant_id": tenant_id,
                "phone": raw_phone,
                "actor_id": actor.id,
                "reason": reason,
            }
        )
        self._spend(self.export_limiter, tenant_id)
        if self.missing:
            raise SubjectNotFoundError
        return _export()

    async def erase_subject(
        self,
        tenant_id: uuid.UUID,
        *,
        customer_id: uuid.UUID,
        actor: StaffContext,
        reason: str | None,
    ) -> SubjectEraseResponse:
        self.calls.append(
            {
                "route": "erase",
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "actor_id": actor.id,
                "reason": reason,
            }
        )
        self._spend(self.erase_limiter, tenant_id)
        if self.missing:
            raise SubjectNotFoundError
        if self.has_active_booking:
            raise SubjectHasActiveBookingError
        return SubjectEraseResponse(
            customer_id=customer_id,
            already_erased=False,
            bookings_scrubbed=2,
            messages_scrubbed=4,
            queue_tickets_scrubbed=1,
            otp_codes_purged=1,
            scheduled_messages_purged=2,
        )

    async def withdraw_marketing(
        self,
        tenant_id: uuid.UUID,
        *,
        customer_id: uuid.UUID | None,
        raw_phone: str | None,
        actor: StaffContext,
    ) -> MarketingWithdrawResponse:
        self.calls.append(
            {
                "route": "withdraw",
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "phone": raw_phone,
                "actor_id": actor.id,
            }
        )
        self._spend(self.withdraw_limiter, tenant_id)
        if self.missing and customer_id is not None:
            raise SubjectNotFoundError
        return MarketingWithdrawResponse(changed=True)


def _client(
    fake: FakePrivacyService,
    *,
    authed: bool = True,
    role: str = StaffRole.OWNER.value,
    settings: dict[str, Any] | None = None,
) -> TestClient:
    tenant = (
        TENANT
        if settings is None
        else TenantContext(id=TENANT.id, slug=TENANT.slug, name=TENANT.name, settings=settings)
    )

    async def _resolver(slug: str) -> TenantContext | None:
        return tenant if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.state.privacy_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring ---


def test_every_route_is_wired_and_no_route_is_shadowed() -> None:
    """Eleven routers on `prefix="/manage"`. A 404 here is a shadow — an earlier
    router already owning one of these (method, path) pairs — and nothing else
    in the suite would notice."""
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        for method, path, body in PRIVACY_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code != 404, (method, path, resp.text)
            assert resp.status_code < 400, (method, path, resp.text)


def test_every_route_is_401_without_a_session() -> None:
    fake = FakePrivacyService()
    client = _client(fake, authed=False)
    with client:
        for method, path, body in PRIVACY_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, (method, path, resp.text)
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_every_route_answers_no_store() -> None:
    """`subject-export` returns a whole person in one document; a cached copy of
    that in a shared boutique browser is the disclosure the route exists to
    control."""
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        for method, path, body in PRIVACY_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.headers["cache-control"] == "no-store", (method, path)


def test_the_tenant_is_host_derived_never_session_derived() -> None:
    """`FakeAuthService.staff.tenant_id` deliberately disagrees with the
    host-resolved tenant, so a handler reading `StaffContext.tenant_id` would be
    visible here as a mismatch."""
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        client.post("/manage/privacy/subject-export", json={"phone": "0501234567"})
    assert fake.calls[-1]["tenant_id"] == TENANT.id
    assert fake.calls[-1]["tenant_id"] != FakeAuthService().staff.tenant_id


# --- Gate 1 Q4: the per-role matrix ---


def test_a_shift_manager_is_refused_on_the_three_owner_only_routes() -> None:
    fake = FakePrivacyService()
    client = _client(fake, role=StaffRole.SHIFT_MANAGER.value)
    with client:
        for method, path, body in [
            (*PRIVACY_PUT, PUT_BODY),
            (*SUBJECT_EXPORT, {"phone": "0501234567"}),
            (*SUBJECT_ERASE, {"customer_id": str(CUSTOMER_ID)}),
        ]:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json() == NOT_AUTHORIZED_BODY
    # The gate raises during dependency solving, so the service is never
    # reached — which is also what proves the refusal is the GATE's and not a
    # service-side check that a later refactor could drop.
    assert fake.calls == []


def test_a_shift_manager_reads_the_documents_and_withdraws_consent() -> None:
    """⚠ GATE 1 Q4, ASSERTED POSITIVELY. A 403 on either of these is the
    regression, and a default-deny walker cannot see it: a route that lost its
    admission looks identical to a route that never had it.

    Both arms of the withdraw are walked, because DR-10's phone arm is the half
    that serves a walk-in — the woman the shipped `checkin.optIn` string
    promises can revoke, who has no `customers` row at all.
    """
    fake = FakePrivacyService()
    client = _client(fake, role=StaffRole.SHIFT_MANAGER.value)
    with client:
        assert client.get("/manage/privacy").status_code == 200
        by_id = client.post(
            "/manage/privacy/marketing-withdraw", json={"customer_id": str(CUSTOMER_ID)}
        )
        assert by_id.status_code == 200, by_id.text
        assert by_id.json() == {"changed": True}
        by_phone = client.post("/manage/privacy/marketing-withdraw", json={"phone": "0501234567"})
        assert by_phone.status_code == 200, by_phone.text
    assert [call["route"] for call in fake.calls] == ["withdraw", "withdraw"]
    assert fake.calls[0]["customer_id"] == CUSTOMER_ID and fake.calls[0]["phone"] is None
    assert fake.calls[1]["phone"] == "0501234567" and fake.calls[1]["customer_id"] is None


def test_an_unknown_role_is_403_on_every_route() -> None:
    fake = FakePrivacyService()
    client = _client(fake, role=UNKNOWN_ROLE)
    with client:
        for method, path, body in PRIVACY_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json() == NOT_AUTHORIZED_BODY


# --- the documents ---


def test_the_get_serves_the_platform_defaults_with_no_service_and_no_round_trip() -> None:
    """D13: `RepositoryTenantResolver` already read the tenants row to route
    this request, so the documents are a pure function over `TenantContext`.

    The assertion that this is real: the fake records NOTHING for a GET.
    """
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        body = client.get("/manage/privacy").json()
    assert fake.calls == []
    assert body["notice_text"] == PLATFORM_NOTICE_HE
    assert body["notice_is_default"] is True
    assert body["dpa_is_default"] is True
    assert body["subprocessors_text"] == PLATFORM_SUBPROCESSORS_HE
    assert body["disclaimer_text"] == PLATFORM_DISCLAIMER_HE


def test_the_get_serves_a_boutiques_override_and_still_the_platform_subprocessors() -> None:
    """D14 / Gate 1 Q3 over HTTP: the sub-processor list is platform-owned and
    structurally un-overridable, so a settings blob that tries to set it changes
    nothing. That is what makes adding a processor reach every tenant."""
    fake = FakePrivacyService()
    client = _client(
        fake,
        settings={
            "privacy": {
                "notice_text": "הנוסח שלנו",
                "dpa_text": "",
                "subprocessors_text": "רשימה מזויפת",
            }
        },
    )
    with client:
        body = client.get("/manage/privacy").json()
    assert body["notice_text"] == "הנוסח שלנו"
    assert body["notice_is_default"] is False
    # "" is the revert sentinel — `||` can never REMOVE a JSONB key, so a blank
    # textarea is the only revert an owner can actually reach.
    assert body["dpa_is_default"] is True
    assert body["subprocessors_text"] == PLATFORM_SUBPROCESSORS_HE


@pytest.mark.parametrize("omitted", ["notice_text", "dpa_text"])
def test_a_put_omitting_either_key_is_refused(omitted: str) -> None:
    """⚠ D16, AND THE TEST THAT STOPS A LATER AUTHOR MAKING ONE FIELD OPTIONAL
    AGAIN.

    `merge_settings` is one `settings || :patch::jsonb` and `||` replaces WHOLE
    top-level keys, so a patch carrying only `notice_text` deletes the boutique's
    `dpa_text` override and `/privacy` silently reverts to un-reviewed platform
    Hebrew. There is no error anywhere in that sequence — this 422 is the only
    thing standing in front of it.

    400 rather than 422: `create_app` registers a `RequestValidationError`
    handler that answers the house-shape `VALIDATION_ERROR` body. The plan says
    422 — that is FastAPI's default, and this app overrides it.
    """
    body = {key: "x" for key in ("notice_text", "dpa_text") if key != omitted}
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        resp = client.put("/manage/privacy", json=body)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_a_put_sends_both_fields_through_and_null_means_revert() -> None:
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        resp = client.put("/manage/privacy", json={"notice_text": "חדש", "dpa_text": None})
    assert resp.status_code == 200, resp.text
    assert fake.calls == [
        {
            "route": "update",
            "tenant_id": TENANT.id,
            "notice_text": "חדש",
            "dpa_text": None,
        }
    ]
    assert resp.json()["dpa_is_default"] is True
    assert resp.json()["notice_is_default"] is False


def test_a_put_with_an_unknown_key_is_a_house_shape_400() -> None:
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        resp = client.put(
            "/manage/privacy",
            json={"notice_text": None, "dpa_text": None, "subprocessors_text": "לא"},
        )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


# --- the subject routes ---


def test_the_export_response_carries_no_carrier_diagnostic_at_any_depth() -> None:
    """The `FORBIDDEN_KEYS` idiom (test_storefront_api.py:203), armed by
    `_export()`'s non-empty booking and message lists.

    `provider_message_id` and `error` are absent BY CONSTRUCTION — there is no
    field on `ExportedMessage` to populate — so this walk asserts a property of
    the model rather than of one code path, and it holds for a service that has
    not been written yet.
    """
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        payload = client.post("/manage/privacy/subject-export", json={"phone": "0501234567"}).json()
    # Anti-vacuity: the walk must have something to walk.
    assert payload["bookings"] and payload["messages"]
    leaked = EXPORT_FORBIDDEN_KEYS & set(_all_keys(payload))
    assert not leaked, f"the export leaks {sorted(leaked)}"
    # And the fields the export MUST carry (DR-12 / DR-15), so a later slimming
    # of the model is a red rather than a silent §13 shortfall.
    assert "notes" in payload["subject"] and "tags" in payload["subject"]
    assert payload["bookings"][0]["checked_in_at"] is not None
    assert payload["messages"][0]["body"]


def test_the_export_passes_the_phone_through_unnormalised_and_audits_the_actor() -> None:
    """Normalisation is the SERVICE's — one place, beside the `by_phone` exact
    equality it exists to satisfy. The router must not pre-chew it, or there
    would be two spellings of the rule."""
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        client.post(
            "/manage/privacy/subject-export", json={"phone": "050-123-4567", "reason": "בקשה"}
        )
    assert fake.calls[-1]["phone"] == "050-123-4567"
    assert fake.calls[-1]["actor_id"] == STAFF_ID
    assert fake.calls[-1]["reason"] == "בקשה"


def test_an_unknown_subject_is_404_on_export_and_erase() -> None:
    fake = FakePrivacyService(missing=True)
    client = _client(fake)
    with client:
        export = client.post("/manage/privacy/subject-export", json={"phone": "0501234567"})
        erase = client.post("/manage/privacy/subject-erase", json={"customer_id": str(CUSTOMER_ID)})
    assert export.status_code == 404, export.text
    assert erase.status_code == 404, erase.text
    assert export.json()["error"]["code"] == "NOT_FOUND"


def test_the_erase_is_keyed_on_the_customer_id_and_returns_counts() -> None:
    """D17: the id, never the phone. The route cannot even accept a phone —
    `SubjectEraseRequest` is `ForbidExtraModel` and has no such field — so the
    "erase by phone" mistake is a refusal rather than a plausible-looking call."""
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        resp = client.post(
            "/manage/privacy/subject-erase",
            json={"customer_id": str(CUSTOMER_ID), "reason": "בקשה טלפונית שאומתה"},
        )
        by_phone = client.post("/manage/privacy/subject-erase", json={"phone": "0501234567"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["bookings_scrubbed"] == 2
    assert resp.json()["already_erased"] is False
    assert fake.calls[0]["customer_id"] == CUSTOMER_ID
    assert by_phone.status_code == 400, by_phone.text


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"customer_id": str(CUSTOMER_ID), "phone": "0501234567"},
    ],
    ids=["neither", "both"],
)
def test_marketing_withdraw_rejects_neither_and_both(body: dict[str, Any]) -> None:
    """EXACTLY one arm. `neither` would be a request with no subject at all;
    `both` would let the caller silently pick which store gets written, and the
    two arms mean different things — one is provable consent, the other is a
    counter submission."""
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        resp = client.post("/manage/privacy/marketing-withdraw", json=body)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


# --- the three budgets ---


def test_each_subject_route_has_its_own_budget_and_one_does_not_block_another() -> None:
    """⚠ ONE BUDGET, ONE INSTANCE — never a shared limiter with three keys.
    `FixedWindowRateLimiter.max_attempts` is per INSTANCE, so a shared one would
    give all three routes a single ceiling: an owner's morning of lookups would
    429 the erase she was working towards, on a route that had been called once.

    The proof is the second half — the erase and the withdraw still answer 200
    after the export budget is spent to exhaustion.
    """
    fake = FakePrivacyService()
    client = _client(fake)
    with client:
        for _ in range(SUBJECT_EXPORT_MAX_PER_WINDOW):
            assert (
                client.post(
                    "/manage/privacy/subject-export", json={"phone": "0501234567"}
                ).status_code
                == 200
            )
        spent = client.post("/manage/privacy/subject-export", json={"phone": "0501234567"})
        assert spent.status_code == 429, spent.text
        assert spent.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"

        assert (
            client.post(
                "/manage/privacy/subject-erase", json={"customer_id": str(CUSTOMER_ID)}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/manage/privacy/marketing-withdraw", json={"customer_id": str(CUSTOMER_ID)}
            ).status_code
            == 200
        )


def test_every_spec_error_code_is_asserted() -> None:
    """Every code this module claims is re-derived from a LIVE response, so the
    set above cannot drift into a list of codes nothing produces."""
    seen: set[str] = set()
    fake = FakePrivacyService(missing=True)

    anon = _client(fake, authed=False)
    with anon:
        seen.add(anon.get("/manage/privacy").json()["error"]["code"])

    wrong_role = _client(fake, role=StaffRole.SHIFT_MANAGER.value)
    with wrong_role:
        seen.add(wrong_role.put("/manage/privacy", json=PUT_BODY).json()["error"]["code"])

    client = _client(fake)
    with client:
        seen.add(
            client.post("/manage/privacy/subject-export", json={"phone": "0501234567"}).json()[
                "error"
            ]["code"]
        )
        seen.add(
            client.post(
                "/manage/privacy/subject-export",
                json={"phone": "0501234567"},
                headers={"origin": "https://evil.example"},
            ).json()["error"]["code"]
        )
        seen.add(client.put("/manage/privacy", json={"notice_text": "x"}).json()["error"]["code"])
        blocked = _client(FakePrivacyService(has_active_booking=True))
        with blocked:
            refused = blocked.post(
                "/manage/privacy/subject-erase", json={"customer_id": str(CUSTOMER_ID)}
            )
        assert refused.status_code == 409
        seen.add(refused.json()["error"]["code"])
        fresh = FakePrivacyService()
        throttled = _client(fresh)
        with throttled:
            for _ in range(MARKETING_WITHDRAW_MAX_PER_WINDOW + 1):
                last = throttled.post(
                    "/manage/privacy/marketing-withdraw", json={"customer_id": str(CUSTOMER_ID)}
                )
            seen.add(last.json()["error"]["code"])

    assert seen == SPEC_ERROR_CODES, (
        f"missing={SPEC_ERROR_CODES - seen} extra={seen - SPEC_ERROR_CODES}"
    )


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (SUBJECT_EXPORT[1], {"phone": "0" * 200}),
        (MARKETING_WITHDRAW[1], {"phone": "0" * 200}),
    ],
)
def test_an_oversized_phone_is_refused_at_the_boundary(path: str, body: dict[str, Any]) -> None:
    """A TRUST-BOUNDARY bound, not a format rule. `normalize_israeli_mobile` runs
    a `fullmatch` and a `re.sub` over whatever arrives, so an unbounded field
    hands a body-limit-sized string to a regex before rejecting it. Every other
    free-text field on this surface is capped; these two were the hole."""
    client = _client(FakePrivacyService())
    with client:
        response = client.post(path, json=body)

    # The house shape: a refused request body is a 400 `VALIDATION_ERROR`, the
    # same answer `test_a_put_with_an_unknown_key_is_a_house_shape_400` pins.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_the_byte_cap_is_what_the_console_counts_against() -> None:
    """The console's byte counter mirrors this constant; a character cap would
    silently halve the allowance for Hebrew, which is the only language these
    documents exist in."""
    assert MAX_PRIVACY_TEXT_BYTES == 8 * 1024
    assert len(PLATFORM_NOTICE_HE.encode("utf-8")) < MAX_PRIVACY_TEXT_BYTES
