import uuid
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.tenancy.middleware import (
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
            return TenantContext(id=BELLA_ID, slug="bella", settings={})
        return None


def _probe_app(resolver: RecordingResolver) -> FastAPI:
    app = create_app(resolver=resolver)

    @app.get("/whoami")
    async def whoami(
        tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    ) -> dict[str, str]:
        return {"tenant_id": str(tenant.id), "slug": tenant.slug}

    return app


def test_known_slug_resolves_and_binds_tenant() -> None:
    resolver = RecordingResolver()
    with TestClient(_probe_app(resolver), base_url="http://bella.localtest.me") as client:
        resp = client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json() == {"tenant_id": str(BELLA_ID), "slug": "bella"}
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
