"""F17 fast API tests: route wiring, 401s, the owner-only gate, the error table,
both budgets, and the containment sweep — fake service + hardcoded TenantContext
resolver, no database (test_boutique_api.py style).

`ROUTES` is exported for test_staff_role_gating.py to import. Without that
import the four gateway routes get no end-to-end 403 assertion at all: the two
HTTP-matrix walks there iterate hand-maintained tables from other modules, so a
route in neither of them keeps them green either way.
"""

import datetime
import re
import time
import typing
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from test_boutique_api import TENANT, TOKEN, FakeAuthService

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.errors import DomainValidationError
from app.main import (
    GATEWAY_CREDENTIALS_REJECTED_BODY,
    GATEWAY_NOT_CONFIGURED_BODY,
    GATEWAY_NOT_CONNECTED_BODY,
    GATEWAY_UNAVAILABLE_BODY,
    NOT_AUTHENTICATED_BODY,
    TOO_MANY_ATTEMPTS_BODY,
    create_app,
)
from app.payments.base import (
    GatewayCredentialsRejectedError,
    GatewayNotConfiguredError,
    GatewayNotConnectedError,
    GatewayUnavailableError,
)
from app.payments.router import get_gateway_service
from app.payments.secretbox import SecretBoxNotConfiguredError, SecretDecryptError
from app.payments.service import GatewayNotFoundError, GatewayStatus, GatewayThrottledError
from app.tenancy.middleware import TenantContext

# The sentinel every containment assertion looks for. Deliberately unlike any
# real value, so a substring hit cannot be a coincidence.
SECRET_SENTINEL = "SUPER-SECRET-MERCHANT-KEY-8f3a"
FIELDS = {
    "merchant_id": "m-1",
    "api_key": SECRET_SENTINEL,
    "webhook_secret": "s-1",
}
CREDENTIALS_BODY = {"fields": FIELDS}
VALIDATED_AT = datetime.datetime(2026, 7, 31, 9, 12, tzinfo=datetime.UTC)

# Every /manage route this feature adds, with a body that passes schema
# validation — so 401, 403 and CSRF failures are attributable to the guard alone.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/manage/gateway", None),
    ("PUT", "/manage/gateway/credentials", CREDENTIALS_BODY),
    ("POST", "/manage/gateway/validate", None),
    ("DELETE", "/manage/gateway/credentials", None),
]

CONNECTED = GatewayStatus(
    provider="fake",
    configured=True,
    connected=True,
    status="valid",
    last_validated_at=VALIDATED_AT,
    credential_fields=["api_key", "merchant_id", "webhook_secret"],
)
UNCONFIGURED = GatewayStatus(
    provider=None,
    configured=False,
    connected=False,
    status=None,
    last_validated_at=None,
    credential_fields=[],
)
# The two MIXED states, and they are the ones that carry the assertion weight:
# `configured` and `connected` are deliberately distinct facts with different
# owners and different remedies, and True/True plus False/False alone cannot tell
# them apart — a `connected=status.configured` mutant survives the rest of this
# file. These are also the two states the service-level assertions live in
# test_payments_service.py for, which is db-marked and therefore CI-only.
CONFIGURED_NOT_CONNECTED = GatewayStatus(
    provider="fake",
    configured=True,
    connected=False,
    status=None,
    last_validated_at=None,
    credential_fields=["api_key", "merchant_id", "webhook_secret"],
)
INVALID = GatewayStatus(
    provider="fake",
    configured=True,
    connected=False,
    status="invalid",
    last_validated_at=VALIDATED_AT,
    credential_fields=["api_key", "merchant_id", "webhook_secret"],
)


class FakeGatewayService:
    """Duck-typed GatewayCredentialService: records every call and raises on
    demand. It never stores a field value, which is what lets the containment
    sweep below mean something — a leak could only come from the route."""

    def __init__(self, status: GatewayStatus = CONNECTED) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.raise_on: dict[str, Exception] = {}
        self._status = status

    def _maybe_raise(self, name: str) -> None:
        error = self.raise_on.get(name)
        if error is not None:
            raise error

    async def status(self, tenant_id: uuid.UUID) -> GatewayStatus:
        self.calls.append(("status", {}))
        self._maybe_raise("status")
        return self._status

    async def connect(
        self, tenant_id: uuid.UUID, *, fields: dict[str, str], actor_id: uuid.UUID
    ) -> GatewayStatus:
        self.calls.append(("connect", {"fields": sorted(fields)}))
        self._maybe_raise("connect")
        return self._status

    async def revalidate(self, tenant_id: uuid.UUID, *, actor_id: uuid.UUID) -> GatewayStatus:
        self.calls.append(("revalidate", {}))
        self._maybe_raise("revalidate")
        return self._status

    async def disconnect(self, tenant_id: uuid.UUID, *, actor_id: uuid.UUID) -> GatewayStatus:
        self.calls.append(("disconnect", {}))
        self._maybe_raise("disconnect")
        return self._status


def _client(fake: FakeGatewayService, *, authed: bool = True, role: str = "owner") -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService()
    auth.staff = type(auth.staff)(
        id=auth.staff.id,
        tenant_id=auth.staff.tenant_id,
        email=auth.staff.email,
        display_name=auth.staff.display_name,
        role=role,
    )
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_gateway_service] = lambda: fake
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring ---


def test_every_route_401s_without_a_cookie() -> None:
    fake = FakeGatewayService()
    client = _client(fake, authed=False)
    with client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, (method, path, resp.text)
            assert resp.json() == NOT_AUTHENTICATED_BODY
    assert fake.calls == []


def test_the_four_happy_paths() -> None:
    fake = FakeGatewayService()
    client = _client(fake)
    with client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 200, (method, path, resp.text)
            payload = resp.json()
            assert payload["provider"] == "fake"
            assert payload["configured"] is True
            assert payload["connected"] is True
            assert payload["status"] == "valid"
            assert payload["credential_fields"] == [
                "api_key",
                "merchant_id",
                "webhook_secret",
            ]
    assert [name for name, _ in fake.calls] == ["status", "connect", "revalidate", "disconnect"]


def test_the_response_carries_no_secret_material_field() -> None:
    """The API has NO read path for a credential value by construction, which is
    what makes the console form write-only rather than write-only-by-convention."""
    fake = FakeGatewayService()
    client = _client(fake)
    with client:
        payload = client.get("/manage/gateway").json()
    assert set(payload) == {
        "provider",
        "configured",
        "connected",
        "status",
        "last_validated_at",
        "credential_fields",
    }
    for forbidden in ("ciphertext", "key_ref", "validation_error", "fields"):
        assert forbidden not in payload


def test_no_response_body_ever_contains_the_secret() -> None:
    """The whole-body substring sweep over EVERY response, success and failure.
    Four independent controls keep credentials unreadable — no response field,
    the __repr__ override, audit details carrying names only, and this."""
    fake = FakeGatewayService()
    client = _client(fake)
    bodies: list[str] = []
    with client:
        for method, path, body in ROUTES:
            bodies.append(client.request(method, path, json=body).text)
        # …and every failure shape too, each carrying the secret in its own
        # message: an error body is the likeliest place for a stray f-string to
        # render what it was handed, and these six all answer FIXED bodies.
        #
        # DomainValidationError is deliberately absent from this list. Its house
        # handler echoes str(exc) BY DESIGN, so a hand-built one carrying the
        # sentinel would only prove that this test can fabricate a leak. The
        # real guarantee — that no message app/payments/validation.py produces
        # ever names a VALUE — is asserted at its source, in
        # test_payments_validation.py::test_no_rejection_message_ever_names_a_value.
        for error in (
            GatewayCredentialsRejectedError(SECRET_SENTINEL),
            GatewayUnavailableError(SECRET_SENTINEL),
            GatewayNotConnectedError(SECRET_SENTINEL),
            GatewayNotConfiguredError(SECRET_SENTINEL),
            SecretDecryptError(SECRET_SENTINEL),
            SecretBoxNotConfiguredError(SECRET_SENTINEL),
        ):
            fake.raise_on = {"connect": error}
            bodies.append(
                client.request("PUT", "/manage/gateway/credentials", json=CREDENTIALS_BODY).text
            )
    assert bodies, "the sweep collected nothing — it would pass vacuously"
    for body_text in bodies:
        assert SECRET_SENTINEL not in body_text


@pytest.mark.parametrize(
    "status",
    [CONNECTED, UNCONFIGURED, CONFIGURED_NOT_CONNECTED, INVALID],
    ids=["connected", "unconfigured", "configured-not-connected", "invalid"],
)
def test_get_is_200_in_every_state_and_renders_it_verbatim(status: GatewayStatus) -> None:
    """200 in EVERY state is the invariant, and the route is a flat passthrough —
    so what this actually pins is the MAPPING, not the status code. Each field is
    read off the status it was given, which is what a mutant that sources
    `connected` from `configured` fails."""
    fake = FakeGatewayService(status=status)
    client = _client(fake)
    with client:
        resp = client.get("/manage/gateway")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["provider"] == status.provider
    assert payload["configured"] is status.configured
    assert payload["connected"] is status.connected
    assert payload["status"] == status.status


def test_get_is_200_in_the_unconfigured_state_never_503() -> None:
    """A console that cannot read its own status cannot explain to the owner why
    deposits are unavailable — which is what D22's answering metadata buys."""
    fake = FakeGatewayService(status=UNCONFIGURED)
    client = _client(fake)
    with client:
        resp = client.get("/manage/gateway")
    assert resp.status_code == 200
    assert resp.json() == {
        "provider": None,
        "configured": False,
        "connected": False,
        "status": None,
        "last_validated_at": None,
        "credential_fields": [],
    }


# --- the error table ---


@pytest.mark.parametrize(
    ("error", "status_code", "expected"),
    [
        (GatewayNotConfiguredError(), 503, GATEWAY_NOT_CONFIGURED_BODY),
        # D18: the same wire code and body — same operational fact to the owner
        # and the same remedy. The two stay distinguishable server-side.
        (SecretBoxNotConfiguredError(), 503, GATEWAY_NOT_CONFIGURED_BODY),
        (GatewayNotConnectedError(), 409, GATEWAY_NOT_CONNECTED_BODY),
        # 400, not 409: the request is well-formed but its CONTENT is wrong, and
        # the owner's remedy is to retype it.
        (GatewayCredentialsRejectedError(), 400, GATEWAY_CREDENTIALS_REJECTED_BODY),
        (GatewayUnavailableError(), 503, GATEWAY_UNAVAILABLE_BODY),
        (SecretDecryptError(), 503, GATEWAY_UNAVAILABLE_BODY),
        (GatewayThrottledError(), 429, TOO_MANY_ATTEMPTS_BODY),
    ],
)
def test_the_error_table(error: Exception, status_code: int, expected: dict[str, Any]) -> None:
    fake = FakeGatewayService()
    fake.raise_on = {"connect": error}
    client = _client(fake)
    with client:
        resp = client.request("PUT", "/manage/gateway/credentials", json=CREDENTIALS_BODY)
    assert resp.status_code == status_code, resp.text
    assert resp.json() == expected


def test_a_bad_credential_shape_is_a_house_400_and_writes_nothing() -> None:
    fake = FakeGatewayService()
    fake.raise_on = {"connect": DomainValidationError("unknown credential fields: extra")}
    client = _client(fake)
    with client:
        resp = client.request(
            "PUT",
            "/manage/gateway/credentials",
            json={"fields": {**FIELDS, "extra": "x"}},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp.json()["error"]["message"] == "unknown credential fields: extra"


def test_a_rejected_ping_records_no_write() -> None:
    """The route-level half of D4: a refusal reaches the owner as a 400 and the
    service was asked to connect exactly once — never twice, and never followed
    by a disconnect."""
    fake = FakeGatewayService()
    fake.raise_on = {"connect": GatewayCredentialsRejectedError()}
    client = _client(fake)
    with client:
        resp = client.request("PUT", "/manage/gateway/credentials", json=CREDENTIALS_BODY)
    assert resp.status_code == 400
    assert [name for name, _ in fake.calls] == ["connect"]


def test_disconnect_with_nothing_stored_is_the_house_404() -> None:
    fake = FakeGatewayService()
    fake.raise_on = {"disconnect": GatewayNotFoundError()}
    client = _client(fake)
    with client:
        resp = client.request("DELETE", "/manage/gateway/credentials")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_the_validate_budget_answers_429() -> None:
    fake = FakeGatewayService()
    fake.raise_on = {"revalidate": GatewayThrottledError()}
    client = _client(fake)
    with client:
        resp = client.post("/manage/gateway/validate")
    assert resp.status_code == 429
    assert resp.json() == TOO_MANY_ATTEMPTS_BODY


def test_the_connect_budget_answers_429() -> None:
    fake = FakeGatewayService()
    fake.raise_on = {"connect": GatewayThrottledError()}
    client = _client(fake)
    with client:
        resp = client.request("PUT", "/manage/gateway/credentials", json=CREDENTIALS_BODY)
    assert resp.status_code == 429
    assert resp.json() == TOO_MANY_ATTEMPTS_BODY


def test_the_two_limiters_are_separate_instances() -> None:
    """max_attempts lives on the LIMITER, not per key — the rule main.py states
    four times. One budget means one instance, or the second key on a shared
    budget could never trip first."""
    app = create_app()
    service = app.state.gateway_credential_service
    connect = service._connect_limiter
    validate = service._validate_limiter
    assert connect is not validate


def test_a_malformed_body_is_the_house_400() -> None:
    fake = FakeGatewayService()
    client = _client(fake)
    with client:
        resp = client.request("PUT", "/manage/gateway/credentials", json={"nope": 1})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_a_forged_origin_is_refused_before_the_route() -> None:
    # /manage is in CsrfOriginMiddleware.PROTECTED_PREFIXES and these are
    # cookie-authenticated state-changing routes. No middleware change needed —
    # this pins that it really covers them.
    fake = FakeGatewayService()
    client = _client(fake)
    with client:
        resp = client.request(
            "PUT",
            "/manage/gateway/credentials",
            json=CREDENTIALS_BODY,
            headers={"origin": "http://evil.localtest.me"},
        )
    assert resp.status_code == 403
    assert fake.calls == []


# --- F21 B5 / row R24: no PAN on our origin, derived from the live route table ---

# Every spelling a card field plausibly takes, including the ones a well-meaning
# "just store the last four for the receipt" change would reach for. `pan` is
# matched as a WHOLE WORD or a snake_case segment: `company` and `panel` are not
# card fields and must not red this.
_CARD_FIELD = re.compile(
    r"(^|_)(card|cardnumber|pan|cvv|cvc|cvv2|ccv|expiry|exp_month|exp_year|"
    r"expmonth|expyear|cardholder|track1|track2)($|_)",
    re.IGNORECASE,
)

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def _null_resolver(slug: str) -> TenantContext | None:
    return None


def _leaf_routes(node: Any) -> Iterator[Any]:
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def _model_fields(model: type[BaseModel], seen: set[type[BaseModel]]) -> Iterator[tuple[str, str]]:
    """Every field name reachable from a request model, nested models included —
    `variants: list[VariantIn]` hides its fields one level down, and a card field
    would hide just as well."""
    if model in seen:
        return
    seen.add(model)
    for name, field in model.model_fields.items():
        yield model.__name__, name
        for arg in (field.annotation, *typing.get_args(field.annotation)):
            for inner in (arg, *typing.get_args(arg)):
                if isinstance(inner, type) and issubclass(inner, BaseModel):
                    yield from _model_fields(inner, seen)


def _request_models() -> dict[type[BaseModel], set[tuple[str, str]]]:
    """Pydantic models bound to a BODY parameter of a mutating route, read off the
    live app. Derived rather than hand-listed: R24's audited property is "no PAN
    reaches our origin", and a hand list is true on the day it is written."""
    app = create_app(resolver=_null_resolver)
    models: dict[type[BaseModel], set[tuple[str, str]]] = {}
    for route in _leaf_routes(app):
        if not (getattr(route, "methods", None) or set()) - _READ_METHODS:
            continue
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        for annotation in typing.get_type_hints(endpoint).values():
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                for owner, field in _model_fields(annotation, set()):
                    models.setdefault(annotation, set()).add((owner, field))
    return models


def test_no_request_schema_carries_a_card_field() -> None:
    """Row 24 as amended by D8: the audited property is "no PAN is proxied, logged
    or stored on our origin", and it is provider-independent — Grow was demoted to
    one candidate on 2026-07-31 and the shipped engine is Lemon Squeezy test mode,
    so a row naming a provider audits nothing.

    True by CONSTRUCTION today: the gateway integration is redirect-only
    (`payments/base.py` returns a `redirect_url` and never a charge payload), and
    no request schema anywhere in `app/` has a card field. Derived from the route
    table so it stays true after the next schema rather than after the next audit.

    Mutation-checked: adding `card_number: str` to any request DTO reds it, and so
    does `pan`, `cvv` and `exp_month`.
    """
    models = _request_models()
    # The pattern is applied to the BARE field name: its `(^|_)…($|_)` anchors are
    # what keep `company` and `panel` out, and prefixing the owner class would
    # silently defeat both of them.
    offenders = sorted(
        f"{owner}.{field}"
        for fields in models.values()
        for owner, field in fields
        if _CARD_FIELD.search(field)
    )
    # Two anti-vacuity legs: an empty walk, or a walk that missed the models this
    # very module posts to, would pass while proving nothing.
    assert models, "no request model was discovered — the walk is broken"
    seen = {f"{owner}.{field}" for fields in models.values() for owner, field in fields}
    assert "SetGatewayCredentialsRequest.fields" in seen, (
        f"the walk missed a known request model; saw {sorted(seen)[:10]}"
    )
    assert not offenders, f"card-shaped fields on request schemas: {offenders}"


def test_the_card_field_pattern_does_not_fire_on_ordinary_names() -> None:
    """`pan` inside `company` and `panel` is not a card number. A pattern that
    reds on those would be relaxed by the first person it inconveniences, and the
    relaxation is where the real field slips through."""
    for benign in ("company", "panel_id", "expanded", "discard", "credential_fields"):
        assert not _CARD_FIELD.search(benign), benign
    for hostile in ("card_number", "card", "pan", "cvv", "exp_month", "cardholder_name"):
        assert _CARD_FIELD.search(hostile), hostile
