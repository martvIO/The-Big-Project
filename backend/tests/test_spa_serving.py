"""F55 fast tests for same-origin SPA serving: the storefront at `/`, the owner
console at exactly `/manage`, both out of `app/static/` and both behind every
middleware the API already runs.

Three things here are load-bearing; everything else is scaffolding.

**The fallback is guarded, not merely last.** A bare catch-all would claim
`/docs` (turning "docs are dark outside dev" into a 200 storefront shell) and
`GET /storefront/otp/send` (turning a POST-only route's 405 into `200
text/html`, which `apps/storefront/src/api.ts` would then try to parse as JSON).
Both are asserted below against the same production settings the real deploy
uses.

**The fallback must DECLINE to match, not answer 404.** Starlette remembers only
the FIRST partial match and a later FULL match short-circuits the whole loop, so
a catch-all that matches `GET /storefront/otp/send` and then raises 404 inside
the handler still destroys the 405 — the partial never gets handled. The route
class in app/main.py returns `Match.NONE` for exactly this reason, and
`test_a_post_only_api_path_keeps_its_405` is what pins it.

**No static directory is a supported deployment.** A dev box that has not run
`pnpm -r build` has none; `create_app()` must boot and `/health` must answer, so
a mis-built deploy is diagnosable rather than dead. Every test here builds its
own tree under `tmp_path` and never reads the real `app/static/` — conftest's
autouse `spa_static_absent` guarantees that for the rest of the suite too, which
is what makes the whole suite identical with and without a local SPA build.
"""

import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import STATIC_ROOT as REAL_STATIC_ROOT
from app.main import _SpaFallbackRoute, create_app
from app.security_headers import SECURITY_HEADERS
from app.storefront.service import StorefrontDressListView
from app.storefront.validation import STOREFRONT_LIST_DEFAULT_LIMIT
from app.tenancy.middleware import EXEMPT_PATHS, TenantContext

HOST = "bella.boutique.example"

REPO_ROOT = Path(__file__).resolve().parents[2]

# Spelled lowercase because git tracks it lowercase; macOS resolves it
# case-insensitively and Linux CI checks it out that way
# (test_frontend_constant_parity.py's precedent).
MANAGE_VITE_CONFIG = REPO_ROOT / "frontend/apps/manage/vite.config.ts"
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})

# Distinct on purpose: a mount wired to the wrong tree serves a valid HTML
# document, and only the marker says which app it came from.
MANAGE_HTML = '<!doctype html><title>MODRYN — ניהול</title><div id="root">manage</div>'
STOREFRONT_HTML = '<!doctype html><title>בלה כלות</title><div id="root">storefront</div>'

MANAGE_JS = "/manage/assets/index-manage.js"
STOREFRONT_JS = "/assets/index-storefront.js"

# Every path apps/storefront/src/router.tsx can match, plus the bare root. Each
# one is a URL a bride can be sent directly (Instagram bio, SMS manage link), so
# each one has to arrive as the shell rather than as a 404.
SHELL_PATHS = [
    "/",
    "/about",
    "/accessibility",
    "/dress/7f1b0e2c",
    "/b/tok3n",
    "/book",
    "/book/slot",
    "/book/slot/7f1b0e2c",
    # F33's walk-in queue. /checkin is printed on a physical sign in the shop
    # window, which makes it the most deep-linked URL the product has, and
    # /q/{ticket_id} is what the printed QR's response sends her to.
    "/checkin",
    "/q/tick3t",
    # F59's public wall board. Typed into a kiosk browser once, on a screen that
    # then stays mounted for months — so arriving as a 404 is a failure nobody in
    # the room is in a position to diagnose.
    "/queue",
    "/anything-a-stale-link-points-at",
]


async def _resolver(slug: str) -> TenantContext | None:
    return TENANT if slug == TENANT.slug else None


def _settings() -> Settings:
    """Production, deliberately: the docs must be dark and the tenant middleware
    must be doing real host→slug work, which is the state the guards below are
    about. database_url and a non-localtest.me base_domain are both REQUIRED
    outside dev or the config validators raise; the media fields are pinned so a
    local .env cannot change what this builds.
    """
    return Settings(
        app_env="production",
        database_url="postgresql+asyncpg://app:pw@db:5432/boutique",
        base_domain="boutique.example",
        media_bucket=None,
        media_endpoint_url=None,
        media_force_path_style=False,
    )


class _EmptyStorefrontService:
    """Only `list_dresses`, because only GET /storefront/dresses is used here —
    to prove a real API route still answers JSON with the fallback installed."""

    async def list_dresses(
        self,
        tenant_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = STOREFRONT_LIST_DEFAULT_LIMIT,
    ) -> StorefrontDressListView:
        return StorefrontDressListView(items=[], total=0, offset=offset, limit=limit)


# A dist-root file that app/main.py has never heard of. Vite copies public/
# verbatim, so this is what "someone adds an og-image" looks like from the
# backend's side — see test_a_public_file_the_backend_never_heard_of_is_served.
DRIFT_FILE = "og-image.png"


def _build_static(root: Path) -> None:
    """The exact shape `pnpm -r build` + the CI copy leave behind: each app's
    `dist/` contents at `app/static/{app}/`, manage's assets under its own
    `base: "/manage/"` prefix so the two trees are disjoint."""
    for name, html in (("manage", MANAGE_HTML), ("storefront", STOREFRONT_HTML)):
        app_dir = root / name
        (app_dir / "assets").mkdir(parents=True)
        (app_dir / "index.html").write_text(html, encoding="utf-8")
        (app_dir / "assets" / f"index-{name}.js").write_text("export {};\n", encoding="utf-8")
        for public in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png", DRIFT_FILE):
            (app_dir / public).write_bytes(b"\x00binary\x00")
    (root / "storefront" / "robots.txt").write_text("User-agent: *\n", encoding="utf-8")


def _app(monkeypatch: pytest.MonkeyPatch, static_root: Path) -> FastAPI:
    monkeypatch.setattr("app.main.get_settings", _settings)
    monkeypatch.setattr("app.main.STATIC_ROOT", static_root)
    return create_app(resolver=_resolver)


def _client(monkeypatch: pytest.MonkeyPatch, static_root: Path) -> TestClient:
    app = _app(monkeypatch, static_root)
    app.state.storefront_service = _EmptyStorefrontService()
    return TestClient(app, base_url=f"http://{HOST}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    static_root = tmp_path / "static"
    _build_static(static_root)
    yield _client(monkeypatch, static_root)


@pytest.fixture
def bare_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    """No app/static/ at all — a dev machine, this suite, or a deploy whose copy
    step failed."""
    yield _client(monkeypatch, tmp_path / "never-built")


# --- the shells ---


def test_manage_shell_is_served_at_exactly_slash_manage(client: TestClient) -> None:
    resp = client.get("/manage")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == MANAGE_HTML
    # SecurityHeadersMiddleware is registered LAST = OUTERMOST, so the shell gets
    # X-Frame-Options: DENY and nosniff for free. This is the open item
    # storefront-browse.md:380 recorded against "whatever eventually serves the
    # SPA index.html", closed here rather than by a static host's config.
    for header, value in SECURITY_HEADERS.items():
        assert resp.headers[header] == value


@pytest.mark.parametrize("path", SHELL_PATHS)
def test_every_storefront_router_path_serves_the_shell(client: TestClient, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code == 200, path
    assert resp.headers["content-type"].startswith("text/html"), path
    assert resp.text == STOREFRONT_HTML, path


@pytest.mark.parametrize("path", [MANAGE_JS, STOREFRONT_JS])
def test_hashed_assets_are_served_from_their_own_tree(client: TestClient, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code == 200, path
    assert resp.text == "export {};\n", path
    assert "javascript" in resp.headers["content-type"], path


@pytest.mark.parametrize(
    "path",
    [
        "/favicon.svg",
        "/favicon-32.png",
        "/apple-touch-icon.png",
        "/robots.txt",
        "/manage/favicon.svg",
        "/manage/favicon-32.png",
        "/manage/apple-touch-icon.png",
    ],
)
def test_public_files_are_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200, path


@pytest.mark.parametrize("path", [f"/{DRIFT_FILE}", f"/manage/{DRIFT_FILE}"])
def test_a_public_file_the_backend_never_heard_of_is_served(client: TestClient, path: str) -> None:
    """The dist-root files are DERIVED from the built tree, never listed in
    app/main.py. A hardcoded list drifts the moment anyone drops a file into
    either app's `public/`: on the storefront side the unlisted file falls to
    the catch-all and comes back 200 `text/html` — the shell — which nosniff
    then makes the browser refuse, so the asset is silently dead with no error
    anywhere. F49 will add a sitemap.xml, and it must not need a backend commit.
    """
    resp = client.get(path)
    assert resp.status_code == 200, path
    assert not resp.headers["content-type"].startswith("text/html"), path


@pytest.mark.parametrize(
    "path", ["/", "/about", "/manage", "/favicon.svg", "/robots.txt", "/manage/favicon.svg"]
)
def test_the_shells_and_public_files_must_be_revalidated(client: TestClient, path: str) -> None:
    """These responses carry ETag and Last-Modified and nothing else, which
    RFC 9111 §4.2.2 makes heuristically cacheable — browsers use ~10% of the
    document's age. A shell cached that way outlives a deploy and then asks for
    the hashed bundle names it was built against; the `/assets` Mount is a FULL
    match, so it answers a hard 404 and the bride gets a blank page with no
    recovery short of a manual hard reload. `no-cache` still permits the 304 on
    an unchanged ETag, so the cost is one conditional request, not the bytes.

    The hashed files under `/assets/` are deliberately NOT covered: their names
    change with their contents, so heuristic caching cannot serve a stale one.
    """
    assert client.get(path).headers["cache-control"] == "no-cache", path


# --- the guards ---


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_stay_dark_outside_dev(client: TestClient, path: str) -> None:
    """Without the EXEMPT_PATHS guard the catch-all claims these and answers the
    storefront shell with a 200, which would break
    test_storefront_api.test_openapi_is_unreachable_outside_dev — and, worse,
    read as "docs are dark" to anyone who only checks the route table."""
    assert client.get(path).status_code == 404, path


def test_the_guard_covers_every_exempt_path(client: TestClient) -> None:
    """Pinned against the frozenset itself, so a sixth EXEMPT_PATH added later
    cannot be silently swallowed by the fallback. /health is registered and must
    still answer 200; the rest must not become HTML."""
    for path in EXEMPT_PATHS:
        resp = client.get(path)
        assert not resp.headers["content-type"].startswith("text/html"), path
    assert client.get("/health").status_code == 200


def test_a_post_only_api_path_keeps_its_405(client: TestClient) -> None:
    """GET /storefront/otp/send has no GET handler. A catch-all that FULL-matches
    it wins over the POST route's partial match and answers 200 text/html —
    which apps/storefront/src/api.ts would then try to JSON.parse. Pinned here
    as well as in test_notifications_api.py because the failure is introduced
    from this file's side."""
    assert client.get("/storefront/otp/send").status_code == 405


@pytest.mark.parametrize("method", ["HEAD", "OPTIONS"])
def test_head_and_options_on_a_manage_route_stay_405(client: TestClient, method: str) -> None:
    """The reason the fallback is a FastAPI route and never a
    Mount("/", StaticFiles(html=True)): a Mount matches EVERY method and every
    path, so it would look for a file and answer 404 where
    test_staff_role_gating.py:519 expects 405. What keeps this 405 is the
    reserved-segment guard in `_SpaFallbackRoute.matches`, which declines
    `manage/...` before methods are ever consulted — so the fallback carrying
    HEAD (see the test below) cannot reach this path either way.
    """
    assert client.request(method, "/manage/settings").status_code == 405


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/about",
        "/manage",
        "/favicon.svg",
        "/robots.txt",
        "/manage/favicon.svg",
        MANAGE_JS,
        STOREFRONT_JS,
    ],
)
def test_head_answers_wherever_get_serves_a_document(client: TestClient, path: str) -> None:
    """FastAPI's APIRoute — unlike Starlette's Route — does NOT add HEAD to a
    GET route, so every route here answered 405 to HEAD while the two
    StaticFiles Mounts in the same function answered 200: one origin, two
    answers. RFC 9110 §9.3.2 says a server supporting GET should support HEAD,
    and the storefront root is a public URL that uptime monitors, CDN origin
    checks and link-preview crawlers all reach with HEAD first.
    """
    assert client.head(path).status_code == 200, path


def test_the_fallback_is_the_last_route_create_app_registers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Starlette returns on the first FULL match, so anything registered after
    the catch-all is unreachable — and it fails silently, answering 200
    text/html (the storefront shell) rather than erroring. `_register_spas` is
    the last statement of `create_app()` for that reason, and this is what keeps
    it there: F17, F52 and F53 each append an `include_router` to that function,
    and one added a line too far down would ship a storefront shell where an API
    used to be, with nothing else going red.
    """
    static_root = tmp_path / "static"
    _build_static(static_root)
    routes = _app(monkeypatch, static_root).router.routes
    assert isinstance(routes[-1], _SpaFallbackRoute), (
        f"the SPA fallback must be registered last; {routes[-1]} comes after it"
    )


def test_a_real_get_api_route_still_answers_json(client: TestClient) -> None:
    resp = client.get("/storefront/dresses")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["items"] == []


def test_an_unknown_manage_path_is_a_404_not_the_console_shell(client: TestClient) -> None:
    """apps/manage has no client-side router (App.tsx drives sections from
    useState), so exactly one URL is the console. A subtree fallback would invent
    deep links that the app cannot restore."""
    assert client.get("/manage/not-a-section").status_code == 404


# --- no static directory ---


def test_the_app_boots_and_health_answers_without_a_static_dir(bare_client: TestClient) -> None:
    assert bare_client.get("/health").status_code == 200


@pytest.mark.parametrize("path", ["/", "/manage", "/about"])
def test_nothing_is_registered_without_a_static_dir(bare_client: TestClient, path: str) -> None:
    assert bare_client.get(path).status_code == 404, path


# --- the dev proxy has to know the same route table ---


def _leaf_routes(node: Any) -> Iterator[Any]:
    """FastAPI wraps an included router in `_IncludedRouter` rather than
    flattening it — recurse through `original_router`, or the walker sees only
    the docs routes and passes vacuously."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def test_the_manage_dev_proxy_names_every_manage_api_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`base: "/manage/"` puts the console's own shell and assets under the same
    prefix as its API, and Vite's proxy middleware runs before the static and
    transform middlewares — so apps/manage/vite.config.ts can no longer proxy a
    bare "/manage" (it would forward the app itself to the backend) and instead
    names the API's second path segments explicitly.

    That list is a copy of the backend's route table, so it can drift: add a
    tenth /manage router and the console keeps working in production, in this
    suite and in CI, and breaks only on a developer's machine — the slowest
    possible way to find out. Derived from the live route table here for the
    same reason test_frontend_constant_parity.py exists.

    Read as text so this stays in the fast, no-Node suite.
    """
    monkeypatch.setattr("app.main.get_settings", _settings)
    expected = {
        route.path.split("/")[2]
        for route in _leaf_routes(create_app(resolver=_resolver))
        if getattr(route, "path", "").startswith("/manage/")
    }
    assert expected, "no /manage API route was discovered — the walker is broken"

    source = MANAGE_VITE_CONFIG.read_text(encoding="utf-8")
    match = re.search(r'"\^/manage/\(([a-z|-]+)\)"', source)
    assert match is not None, f"no ^/manage/(...) proxy key found in {MANAGE_VITE_CONFIG}"
    assert set(match.group(1).split("|")) == expected


def test_the_ci_copy_target_is_exactly_static_root() -> None:
    """`STATIC_ROOT`'s real value is read by nothing else under test — every
    test here patches it to a tmp_path, and so does conftest. So renaming the
    directory (`static` -> `spa`, say) leaves this whole file green, leaves
    ruff and mypy green, leaves the CI copy and its assert green (they hardcode
    `backend/app/static/` and would still find the files they put there), lets
    `railway up` succeed and lets Railway's healthcheck pass on /health — while
    every HTML request in production 404s. That is precisely the silent-failure
    class F55 exists to close, and the copy step's own assert does not cover
    this half of it.

    Pinned by text, so the two literals cannot drift apart. Same technique and
    same reason as test_frontend_constant_parity.py.
    """
    targets = set(re.findall(r"cp -R \S+ (\S+)/(?:manage|storefront)\b", CI_WORKFLOW.read_text()))
    assert targets, f"no SPA copy step found in {CI_WORKFLOW}"
    # .lower() because git tracks `backend/` lowercase while the directory on
    # disk is `Backend/` — the same casing trap MANAGE_VITE_CONFIG documents.
    assert targets == {REAL_STATIC_ROOT.relative_to(REPO_ROOT).as_posix().lower()}


# --- documented expectation, not a fix ---


def test_the_console_shell_is_intentionally_ungated(client: TestClient) -> None:
    """RECORD, not a guard. test_staff_role_gating.test_every_manage_route_is_role_gated
    walks routes that carry a `dependant`, and it never sees the two StaticFiles
    Mounts at all — a Mount has no dependant. It also never sees `GET /manage`:
    conftest's autouse `spa_static_absent` points STATIC_ROOT at an empty
    directory for every test that does not build its own, so `_register_spas`
    registers nothing there. (Before that fixture this was an environment
    accident — the gating walker went red on any machine that had run
    `pnpm -r build`.) So NOTHING in the gating suite covers what this asserts.

    And what it asserts is correct: the console shell is public HTML. It renders
    a login form, and every API call behind it is authenticated and role-gated
    (that is what the gating suite proves). Anyone may fetch it, exactly as
    anyone may fetch the storefront on the same origin. Recorded as spec F55
    Risk 3 so a future reader does not mistake the gating suite's green for
    coverage of this, and does not "fix" it into a redirect.
    """
    resp = client.get("/manage")
    assert resp.status_code == 200
    assert not resp.cookies
    assert "manage" in resp.text
