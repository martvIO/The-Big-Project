import dataclasses
from typing import Any, Protocol
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.tenancy.slugs import extract_slug, is_valid_slug

# Host-agnostic paths: infra probes hit /health by IP.
#
# The four docs paths stay listed but are now only REACHABLE in dev: F10 makes
# this origin publicly crawlable, so create_app() passes docs_url/redoc_url/
# openapi_url=None outside dev and FastAPI never registers the routes at all.
# The old justification here — "the OpenAPI schema feeds api-client generation"
# — is void: F10 declined the generated client and hand-wrote apps/storefront/
# src/api.ts, and the generated wrapper is re-homed to E3 #14.
# /docs/oauth2-redirect is auto-registered by FastAPI whenever docs are enabled —
# it must stay in sync with this set or Swagger's Authorize flow silently breaks.
#
# STOREFRONT PATHS MUST NEVER BE ADDED HERE. This frozenset skips tenant
# resolution entirely, and a storefront route reaching a handler without
# request.state.tenant raises TenantNotResolvedError. Public is not the same as
# host-agnostic. The set is exact-match rather than prefix, so this cannot
# happen by accident; test_storefront_paths_are_not_exempt asserts it anyway.
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
    # The boutique's display name (tenants.name), which the storefront renders as
    # its <h1>. REQUIRED, not defaulted: a default of "" would let a future
    # resolver that forgets to wire it ship an empty heading to the public page
    # instead of failing at construction.
    name: str
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
