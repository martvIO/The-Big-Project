"""F21 B2: the two response headers `SECURITY_HEADERS` cannot hold.

`SECURITY_HEADERS` is a dict of **unconditional constant** headers, and SEVEN
test modules assert `{h: resp.headers.get(h) for h in SECURITY_HEADERS} ==
SECURITY_HEADERS` (test_booking_api, test_booking_manage_api, test_checkin_api,
test_notifications_api, test_payments_webhook_api, test_spa_serving,
test_storefront_api). That comparison is only meaningful while every member is
both unconditional and constant.

HSTS is **request**-derived — it depends on the effective scheme — and the CSP is
**settings**-derived — it names the media origin, which comes from `Settings`. So
neither may join that dict. They are emitted BESIDE it by the same middleware and
are pinned here instead. `test_the_security_headers_dict_is_unchanged` is what
stops a later author from "tidying" them in and quietly turning seven equality
assertions into assertions about a value that varies per request.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.security_headers import HSTS_HEADER, HSTS_VALUE, SECURITY_HEADERS

HSTS = "Strict-Transport-Security"


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(app_env="dev")
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    return TestClient(create_app())


# --- HSTS: one condition, not a config flag (D3) ---


def test_hsts_is_emitted_over_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """Railway terminates TLS and forwards `x-forwarded-proto`, so the app never
    sees an https scheme on `request.url` in production. Reading the header is
    the only way the condition can ever be true on the deployment we have."""
    resp = _client(monkeypatch).get("/health", headers={"x-forwarded-proto": "https"})
    assert resp.status_code == 200
    assert resp.headers.get(HSTS) == "max-age=31536000; includeSubDomains"


def test_hsts_is_absent_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not "emitted and ignored" — absent. A browser ignores HSTS over plain
    HTTP by specification, so emitting it unconditionally would be harmless and
    also indistinguishable from a scheme check that never ran."""
    resp = _client(monkeypatch).get("/health")
    assert resp.status_code == 200
    assert HSTS not in resp.headers


def test_hsts_honours_the_last_forwarded_proto_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A proxy chain appends; the entry the LAST hop wrote is the scheme that hop
    actually served. Reading the first would let a client-supplied `https` in a
    forged prefix decide it."""
    client = _client(monkeypatch)
    downgraded = client.get("/health", headers={"x-forwarded-proto": "https, http"})
    upgraded = client.get("/health", headers={"x-forwarded-proto": "http, https"})
    assert HSTS not in downgraded.headers
    assert upgraded.headers.get(HSTS) == HSTS_VALUE


def test_hsts_carries_no_preload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preload submission is effectively irreversible and belongs to a domain
    that resolves. D3 rules it out explicitly; this is the assertion."""
    resp = _client(monkeypatch).get("/health", headers={"x-forwarded-proto": "https"})
    assert "preload" not in resp.headers.get(HSTS, "")


def test_hsts_reaches_the_tenant_not_found_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """The single most-served response to anyone probing the domain, returned by
    TenantResolutionMiddleware from its own dispatch without reaching a handler.
    The middleware is registered LAST = OUTERMOST precisely so it still lands."""
    settings = Settings(app_env="dev")
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    client = TestClient(create_app(), base_url="http://nosuch.localtest.me")
    resp = client.get("/storefront/boutique", headers={"x-forwarded-proto": "https"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert resp.headers.get(HSTS) == HSTS_VALUE


# --- the constraint the seven importers depend on ---


def test_the_security_headers_dict_is_unchanged() -> None:
    """C6/D3's load-bearing constraint, asserted rather than described. If this
    reds, seven `== SECURITY_HEADERS` comparisons elsewhere have silently changed
    meaning."""
    assert SECURITY_HEADERS == {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    assert HSTS_HEADER not in SECURITY_HEADERS
