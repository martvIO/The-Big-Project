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

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.security_headers import (
    CSP_HEADER,
    HSTS_HEADER,
    HSTS_VALUE,
    SECURITY_HEADERS,
    build_csp,
    media_csp_origin,
)
from app.tenancy.middleware import TenantContext

HSTS = "Strict-Transport-Security"
CSP = "Content-Security-Policy"

REPO_ROOT = Path(__file__).resolve().parents[2]
# Lowercase because git tracks it lowercase; macOS resolves case-insensitively
# and Linux CI checks it out that way (test_frontend_constant_parity's precedent).
CSP_FIXTURE = REPO_ROOT / "frontend/e2e/fixtures/csp.txt"

# The settings the committed e2e fixture declares in its own header comment.
# Spelled here rather than parsed out of the file on purpose: a parser would let
# the fixture's comment and the fixture's payload drift apart while the parity
# assertion kept passing. These two values and the fixture's policy line are
# pinned to each other byte-for-byte below, so changing either without the other
# is a red test.
FIXTURE_BUCKET = "boutique-media"
FIXTURE_REGION = "il-central-1"


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
    meaning.

    Note what those seven do NOT catch, which is why this test carries the
    weight: joining a header to this dict makes the middleware's `setdefault`
    loop emit it UNCONDITIONALLY, so their comparison keeps passing while
    quietly ceasing to describe a constant header. Verified by mutation."""
    assert SECURITY_HEADERS == {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    # Request-derived; cannot be constant.
    assert HSTS_HEADER not in SECURITY_HEADERS
    # Settings-derived; cannot be constant either.
    assert CSP_HEADER not in SECURITY_HEADERS


# --- the CSP: built at create_app() time from Settings (D3) ---


def _parse(policy: str) -> dict[str, list[str]]:
    directives = {}
    for chunk in policy.split(";"):
        parts = chunk.strip().split()
        if parts:
            directives[parts[0]] = parts[1:]
    return directives


def _settings(**kwargs: object) -> Settings:
    return Settings(app_env="dev", **kwargs)  # type: ignore[arg-type]


def test_the_csp_pins_the_directive_set() -> None:
    """D3's ten directives, exactly. `style-src` gets no `'unsafe-inline'`: the
    build emits an external stylesheet and Tailwind v4 compiles at build time. If
    that ever changes the CSP reds in e2e, which is the correct place for it."""
    directives = _parse(build_csp(_settings()))
    assert list(directives) == [
        "default-src",
        "script-src",
        "style-src",
        "img-src",
        "font-src",
        "connect-src",
        "form-action",
        "frame-ancestors",
        "base-uri",
        "object-src",
    ]
    assert directives["style-src"] == ["'self'"]
    assert "'unsafe-inline'" not in directives["style-src"]
    assert "'unsafe-inline'" not in directives["script-src"]
    # frame-ancestors is what actually stops clickjacking on the shells;
    # X-Frame-Options: DENY stays as the defence-in-depth it was described as.
    assert directives["frame-ancestors"] == ["'none'"]
    assert directives["base-uri"] == ["'none'"]
    assert directives["object-src"] == ["'none'"]
    assert directives["form-action"] == ["'self'"]


def test_the_csp_admits_data_uris_on_img_src_and_nowhere_else() -> None:
    """**Found by the browser, not by a header string.** Spec D3 named
    `assetsInlineLimit` (default 4096) as a live tripwire, and it was already
    tripped when `csp.spec.ts` first ran: `apps/manage/src/assets/modryn-mark.svg`
    is 973 bytes, so Rolldown emits it as a `data:image/svg+xml` URI inside the
    console bundle, and `<img src={markUrl}>` on the login screen
    (`LoginForm.tsx:37`) is refused by an `img-src` of `'self'` alone. The MODRYN
    lockup — the console's own h1 — would have gone blank in production.

    Widened by exactly ONE source on exactly ONE directive, which is what D3's
    tripwire prescribes. `data:` is a real weakening and it is bounded: a data
    URI cannot execute, cannot be a script and cannot exfiltrate, so on `img-src`
    it costs the ability to distinguish an inlined build asset from an attacker's
    inlined pixel — and nothing else. It must stay off every other directive,
    because `script-src data:` or `connect-src data:` would be a different
    property entirely. That negative half is the assertion below."""
    directives = _parse(build_csp(_settings(media_bucket="b", media_region="il-central-1")))
    assert "data:" in directives["img-src"]
    for name, sources in directives.items():
        if name != "img-src":
            assert "data:" not in sources, f"{name} must not admit data: URIs"


def test_the_csp_names_the_media_origin_when_a_bucket_is_configured() -> None:
    """Path-style addressing (storage/s3.py:73-78) is why the bucket never
    appears in the host: an explicit endpoint_url forces path style, and the
    default endpoint is the regional host itself. So the origin is a one-line
    derivation and never `bucket.s3.<region>.amazonaws.com`."""
    directives = _parse(
        build_csp(_settings(media_bucket="boutique-prod", media_region="il-central-1"))
    )
    origin = "https://s3.il-central-1.amazonaws.com"
    assert directives["img-src"] == ["'self'", "data:", origin]
    assert directives["connect-src"] == ["'self'", origin]
    # The bucket name is not a host component and must never leak into a header
    # every response carries.
    assert "boutique-prod" not in build_csp(
        _settings(media_bucket="boutique-prod", media_region="il-central-1")
    )


def test_the_csp_omits_the_media_origin_when_no_bucket_is_configured() -> None:
    """A deployment with no bucket gets a strictly TIGHTER policy, never a broken
    one. No bucket is a supported deployment (config.py:265-269), so the policy
    must degrade in the safe direction."""
    directives = _parse(build_csp(_settings(media_bucket=None)))
    # `data:` survives the bucket-less case because it is about the BUNDLE, not
    # about the deployment: the inlined mark ships in every build regardless of
    # whether media is configured.
    assert directives["img-src"] == ["'self'", "data:"]
    assert directives["connect-src"] == ["'self'"]
    assert media_csp_origin(_settings(media_bucket=None)) is None


@pytest.mark.parametrize(
    ("endpoint_url", "expected"),
    [
        ("http://localhost:9000", "http://localhost:9000"),
        # A trailing slash is what an operator pastes out of a console.
        ("http://localhost:9000/", "http://localhost:9000"),
        # A path suffix is what an S3-compatible provider's docs show.
        ("https://minio.example.test/s3/v1", "https://minio.example.test"),
        ("https://s3.eu-west-1.wasabisys.com:8443/", "https://s3.eu-west-1.wasabisys.com:8443"),
    ],
)
def test_the_media_origin_is_normalised_to_scheme_host_port(
    endpoint_url: str, expected: str
) -> None:
    """A CSP source is an ORIGIN. A trailing slash or a path turns it into a path
    match with different semantics, and a browser silently applies the different
    one — there is no error to observe."""
    settings = _settings(media_bucket="b", media_endpoint_url=endpoint_url)
    assert media_csp_origin(settings) == expected
    assert _parse(build_csp(settings))["img-src"] == ["'self'", "data:", expected]


def test_the_csp_is_emitted_on_every_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Four surfaces, and the fourth is the one an inner middleware would miss:
    the TENANT_NOT_FOUND 404 that TenantResolutionMiddleware returns from its own
    dispatch without reaching a handler."""
    tenant = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה", settings={})

    async def resolver(slug: str) -> TenantContext | None:
        return tenant if slug == tenant.slug else None

    static_root = tmp_path / "static"
    for name in ("manage", "storefront"):
        (static_root / name / "assets").mkdir(parents=True)
        (static_root / name / "index.html").write_text(
            f'<!doctype html><div id="root">{name}</div>', encoding="utf-8"
        )

    settings = Settings(app_env="dev", media_bucket=FIXTURE_BUCKET, media_region=FIXTURE_REGION)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.STATIC_ROOT", static_root)
    app = create_app(resolver=resolver)
    expected = build_csp(settings)

    with TestClient(app, base_url="http://bella.localtest.me") as client:
        manage_shell = client.get("/manage")
        storefront_shell = client.get("/")
        json_api = client.get("/health")
    with TestClient(app, base_url="http://nosuch.localtest.me") as stranger:
        tenant_404 = stranger.get("/storefront/boutique")

    assert manage_shell.status_code == 200
    assert storefront_shell.status_code == 200
    assert json_api.status_code == 200
    assert tenant_404.status_code == 404
    assert tenant_404.json()["error"]["code"] == "TENANT_NOT_FOUND"
    for resp in (manage_shell, storefront_shell, json_api, tenant_404):
        assert resp.headers.get(CSP) == expected


def test_the_e2e_fixture_matches_the_emitted_policy() -> None:
    """C2's parity assertion, and the whole reason Task 6's browser test can be
    trusted. `playwright.config.ts` serves both apps via `vite preview`, so
    FastAPI is never in the e2e request path — the browser test injects the
    policy from this fixture instead. Drift between the fixture and what the
    middleware actually emits is therefore invisible to the browser and must be a
    RED BACKEND TEST. Precedent: test_frontend_constant_parity.py."""
    lines = CSP_FIXTURE.read_text(encoding="utf-8").splitlines()
    payload = [line for line in lines if line.strip() and not line.startswith("#")]
    assert len(payload) == 1, f"csp.txt must carry exactly one policy line, found {len(payload)}"
    expected = build_csp(_settings(media_bucket=FIXTURE_BUCKET, media_region=FIXTURE_REGION))
    assert payload[0] == expected
