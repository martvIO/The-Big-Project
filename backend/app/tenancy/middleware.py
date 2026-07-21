import dataclasses
from typing import Any, Protocol
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.tenancy.slugs import extract_slug, is_valid_slug

# Host-agnostic paths: infra probes hit /health by IP; the OpenAPI schema feeds
# api-client generation. Docs exposure is revisited at the Feature 21 hardening gate.
# /docs/oauth2-redirect is auto-registered by FastAPI whenever docs are enabled —
# it must stay in sync with this set or Swagger's Authorize flow silently breaks.
EXEMPT_PATHS = frozenset({"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})

# One body for every failure kind (unknown, suspended, deleted, reserved, apex) —
# responses must not reveal whether a slug exists.
TENANT_NOT_FOUND_BODY = {
    "error": {"code": "TENANT_NOT_FOUND", "message": "No active boutique at this address."}
}


@dataclasses.dataclass(frozen=True)
class TenantContext:
    id: UUID
    slug: str
    settings: dict[str, Any]


class TenantResolver(Protocol):
    async def __call__(self, slug: str) -> TenantContext | None: ...


def _not_found() -> JSONResponse:
    return JSONResponse(TENANT_NOT_FOUND_BODY, status_code=404)


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """Binds the tenant from the request hostname — never from client input
    beyond the Host header, which yields nothing more than DNS already does."""

    def __init__(self, app: ASGIApp, resolver: TenantResolver, base_domain: str) -> None:
        super().__init__(app)
        self._resolver = resolver
        self._base_domain = base_domain

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        slug = extract_slug(request.headers.get("host"), self._base_domain)
        if slug is None or not is_valid_slug(slug):
            return _not_found()
        tenant = await self._resolver(slug)
        if tenant is None:
            return _not_found()
        request.state.tenant = tenant
        return await call_next(request)


class TenantNotResolvedError(Exception):
    """A tenant-scoped route ran without a resolved tenant (route mounted on an
    exempt path). create_app registers a handler converting this to the same
    generic 404 as every other resolution failure — the anti-enumeration
    invariant holds even for this misconfiguration path."""


def get_current_tenant(request: Request) -> TenantContext:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise TenantNotResolvedError
    return tenant
