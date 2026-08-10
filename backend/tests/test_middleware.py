import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.tenancy.middleware import (
    EXEMPT_PATHS,
    TenantContext,
    TenantNotResolvedError,
    get_current_tenant,
)

BELLA_ID = uuid.uuid4()


class RecordingResolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, slug: str) -> TenantContext | None:
        self.calls.append(slug)
        if slug == "bella":
            return TenantContext(id=BELLA_ID, slug="bella", name="Bella Bridal", settings={})
        return None


def _probe_app(resolver: RecordingResolver) -> FastAPI:
    app = create_app(resolver=resolver)

    @app.get("/whoami")
    async def whoami(
        tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    ) -> dict[str, str]:
        # `name` is echoed because the storefront renders it as the page <h1>:
        # this is the only test that proves the resolver wires it all the way to
        # request.state.tenant rather than leaving an empty heading.
        return {"tenant_id": str(tenant.id), "slug": tenant.slug, "name": tenant.name}

    return app


def test_known_slug_resolves_and_binds_tenant() -> None:
    resolver = RecordingResolver()
    with TestClient(_probe_app(resolver), base_url="http://bella.localtest.me") as client:
        resp = client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json() == {
        "tenant_id": str(BELLA_ID),
        "slug": "bella",
        "name": "Bella Bridal",
    }
    assert resolver.calls == ["bella"]


def test_unknown_slug_is_404_with_generic_body() -> None:
    resolver = RecordingResolver()
    with TestClient(_probe_app(resolver), base_url="http://nosuch.localtest.me") as client:
        resp = client.get("/whoami")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert resolver.calls == ["nosuch"]


def test_reserved_slug_never_reaches_resolver() -> None:
    resolver = RecordingResolver()
    with TestClient(_probe_app(resolver), base_url="http://admin.localtest.me") as client:
        resp = client.get("/whoami")
    assert resp.status_code == 404
    assert resolver.calls == []


def test_apex_and_foreign_hosts_are_404_without_resolver_call() -> None:
    resolver = RecordingResolver()
    app = _probe_app(resolver)
    for host in ("localtest.me", "evil.com", "a.b.localtest.me"):
        with TestClient(app, base_url=f"http://{host}") as client:
            assert client.get("/whoami").status_code == 404
    assert resolver.calls == []


def test_failure_kinds_are_indistinguishable() -> None:
    """Unknown slug, apex, and reserved must return byte-identical bodies —
    no slug-existence enumeration."""
    resolver = RecordingResolver()
    app = _probe_app(resolver)
    bodies = []
    for host in ("nosuch.localtest.me", "localtest.me", "admin.localtest.me"):
        with TestClient(app, base_url=f"http://{host}") as client:
            bodies.append(client.get("/whoami").json())
    assert bodies[0] == bodies[1] == bodies[2]


def test_exempt_paths_ignore_host() -> None:
    resolver = RecordingResolver()
    app = _probe_app(resolver)
    with TestClient(app, base_url="http://not-a-tenant-host.example") as client:
        assert client.get("/health").status_code == 200
        # create_app() serves the schema only when app_env == "dev", so the 200
        # below is a claim about tenancy exemption ONLY under that condition.
        # Asserted rather than assumed: without this line a suite running with
        # APP_ENV=staging would "pass" the exemption check on a 404 that the
        # middleware never had a chance to produce.
        assert get_settings().app_env == "dev"
        assert client.get("/openapi.json").status_code == 200
    assert resolver.calls == []


def test_backstop_returns_the_same_generic_body() -> None:
    """A tenant-scoped handler running without a resolved tenant must produce
    the identical 404 body — the anti-enumeration invariant has no exceptions."""
    resolver = RecordingResolver()
    app = _probe_app(resolver)

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise TenantNotResolvedError

    with TestClient(
        app, base_url="http://bella.localtest.me", raise_server_exceptions=False
    ) as client:
        resp = client.get("/boom")
        reference = client.get("/whoami", headers={"host": "nosuch.localtest.me"})
    assert resp.status_code == 404
    assert resp.json() == reference.json()


def test_host_header_with_port_and_case_resolves() -> None:
    resolver = RecordingResolver()
    with TestClient(_probe_app(resolver), base_url="http://placeholder.localtest.me") as client:
        resp = client.get("/whoami", headers={"host": "BELLA.LOCALTEST.ME:8443"})
    assert resp.status_code == 200
    assert resp.json()["slug"] == "bella"


# --- F25's console-host fence ------------------------------------------------
#
# ⚠ THE FENCE IS BIDIRECTIONAL AND BOTH DIRECTIONS ARE THE SAME 404 BODY. The
# console host answers nothing but /platform* and the exact EXEMPT_PATHS; tenant
# hosts answer nothing on /platform*. One body either way, so no probe learns
# from a status which surface it found — the anti-enumeration invariant this
# module already holds for slugs, extended to a second axis.
#
# ⚠ AND `/platform` IS DELIBERATELY NOT IN EXEMPT_PATHS. Exemption skips tenant
# resolution on EVERY host, which would open the console's routes on every
# boutique's subdomain — the exact inversion of what the fence is for. The fence
# lives in the label branch; the spec names this as a trap and this comment is
# the tripwire for whoever "simplifies" it.

CONSOLE_HOST = "admin.localtest.me"


def _fenced_app(resolver: RecordingResolver) -> FastAPI:
    app = create_app(resolver=resolver)

    @app.get("/platform/probe")
    async def platform_probe(request: Request) -> dict[str, bool]:
        return {"platform_host": getattr(request.state, "platform_host", False)}

    @app.get("/whoami")
    async def whoami(
        tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    ) -> dict[str, str]:
        return {"slug": tenant.slug}

    return app


def test_the_console_host_serves_platform_paths_and_marks_the_request() -> None:
    """`request.state.platform_host` is the belt `get_current_operator` checks;
    the middleware fence is the braces. A cookie replayed on a tenant host must
    fail for BOTH reasons independently."""
    resolver = RecordingResolver()
    with TestClient(_fenced_app(resolver), base_url=f"http://{CONSOLE_HOST}") as client:
        resp = client.get("/platform/probe")
    assert resp.status_code == 200
    assert resp.json() == {"platform_host": True}
    # No tenant resolution happened at all — `admin` is reserved, and the branch
    # returns before the resolver would ever be reached.
    assert resolver.calls == []


def test_the_console_host_404s_every_path_that_is_not_the_console() -> None:
    """The storefront shell, the tenant console and every tenant API are
    unreachable at admin.{base}. `/platformx` is in the list on purpose: the
    prefix test is `/platform` or `/platform/…`, never `startswith("/platform")`,
    or a route named `/platformer` would be inside the fence."""
    resolver = RecordingResolver()
    app = _fenced_app(resolver)
    with TestClient(app, base_url=f"http://{CONSOLE_HOST}") as client:
        for path in ("/", "/manage", "/manage/auth/me", "/storefront/dresses", "/platformx"):
            resp = client.get(path)
            assert resp.status_code == 404, path
            assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND", path
    assert resolver.calls == []


def test_the_console_does_not_exist_on_a_tenant_host() -> None:
    """The other direction, and it is the one that would be quietly missing: a
    fence that only guards the console host leaves /platform/* answering on every
    boutique's own subdomain, where the CSRF prefix and the cookie name are the
    only things left standing between a tenant's staff and the platform API."""
    resolver = RecordingResolver()
    app = _fenced_app(resolver)
    with TestClient(app, base_url="http://bella.localtest.me") as client:
        for path in ("/platform", "/platform/probe", "/platform/auth/login"):
            resp = client.get(path)
            assert resp.status_code == 404, path
            assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND", path
    # Refused BEFORE resolution — the fence costs no database work and gives no
    # timing signal about whether the boutique exists.
    assert resolver.calls == []


def test_both_directions_of_the_fence_answer_the_same_body_as_an_unknown_slug() -> None:
    """Byte-identical, like the three failure kinds above. A distinguishable body
    would tell a prober which host it is standing on."""
    resolver = RecordingResolver()
    app = _fenced_app(resolver)
    bodies = []
    with TestClient(app, base_url=f"http://{CONSOLE_HOST}") as client:
        bodies.append(client.get("/manage").json())
    with TestClient(app, base_url="http://bella.localtest.me") as client:
        bodies.append(client.get("/platform/probe").json())
    with TestClient(app, base_url="http://nosuch.localtest.me") as client:
        bodies.append(client.get("/whoami").json())
    assert bodies[0] == bodies[1] == bodies[2]


def test_health_still_answers_on_the_console_host() -> None:
    """EXEMPT_PATHS is exact-match and host-agnostic, and it stays that way — an
    infra probe hitting /health by IP must not care which host it landed on."""
    resolver = RecordingResolver()
    with TestClient(_fenced_app(resolver), base_url=f"http://{CONSOLE_HOST}") as client:
        assert client.get("/health").status_code == 200
    assert resolver.calls == []


def test_platform_paths_are_not_exempt() -> None:
    """The trap, asserted rather than described. Adding /platform to EXEMPT_PATHS
    would skip tenant resolution on every host and open the console's routes on
    every boutique's subdomain."""
    assert not any(path.startswith("/platform") for path in EXEMPT_PATHS)


def test_the_anonymous_join_routes_are_fenced_off_every_other_host() -> None:
    """F26's join surface is ANONYMOUS, which makes the host fence the only thing
    standing between it and every boutique's own subdomain. `/platform/join*`
    inherits the same prefix rule as the console's operator routes — it is not
    exempted, and `test_platform_paths_are_not_exempt` above is what keeps it
    that way (exemption would skip resolution on EVERY host).

    The apex is included because it is a genuinely different branch from a tenant
    host: it resolves no slug at all and 404s by design (F4)."""
    resolver = RecordingResolver()
    app = _fenced_app(resolver)
    join_paths = ("/platform/join", "/platform/join/invite", "/platform/join/redeem")
    for host in ("bella.localtest.me", "localtest.me"):
        with TestClient(app, base_url=f"http://{host}") as client:
            for path in join_paths:
                resp = client.get(path)
                assert resp.status_code == 404, f"{host}{path}"
                assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND", f"{host}{path}"
    # Refused BEFORE resolution, so the fence costs no database work and leaks no
    # timing signal about whether a boutique exists.
    assert resolver.calls == []
