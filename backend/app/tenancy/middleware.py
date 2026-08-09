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


# F25's console prefix.
#
# ⚠ THIS IS NOT AN ENTRY IN `EXEMPT_PATHS` AND MUST NEVER BECOME ONE. Exemption
# skips tenant resolution on EVERY host, which would open the console's routes on
# every boutique's own subdomain — the precise inversion of what this fence is
# for. The fence is the label branch below; `test_platform_paths_are_not_exempt`
# is the tripwire.
PLATFORM_PREFIX = "/platform"


def _is_platform_path(path: str) -> bool:
    # Exact, or a real path segment. `startswith(PLATFORM_PREFIX)` alone would put
    # a future `/platformer` route inside the fence on the console host and
    # outside every tenant's reach — a routing decision made by a substring.
    return path == PLATFORM_PREFIX or path.startswith(PLATFORM_PREFIX + "/")


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """Binds the tenant from the request hostname — never from client input
    beyond the Host header, which yields nothing more than DNS already does.

    Since F25 it also fences the platform console, BOTH WAYS and with the one
    `TENANT_NOT_FOUND` body in either direction: on `{platform_host_label}.{base}`
    only `/platform*` (and the exact `EXEMPT_PATHS`) proceed, and on every tenant
    host `/platform*` is refused. One place, one body, no oracle either way.
    """

    def __init__(
        self,
        app: ASGIApp,
        resolver: TenantResolver,
        base_domain: str,
        platform_host_label: str,
    ) -> None:
        super().__init__(app)
        self._resolver = resolver
        self._base_domain = base_domain
        self._platform_host_label = platform_host_label

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in EXEMPT_PATHS:
            return await call_next(request)
        slug = extract_slug(request.headers.get("host"), self._base_domain)

        # The label branch runs BEFORE `is_valid_slug`, and it has to: the label
        # is reserved, so `is_valid_slug` refuses it and the console host would
        # otherwise 404 itself.
        if slug is not None and slug == self._platform_host_label:
            if not _is_platform_path(path):
                return _not_found()
            # No tenant is resolved here and none exists to resolve. The flag is
            # the BELT that `get_current_operator` checks; this branch is the
            # braces, and neither is trusted alone.
            request.state.platform_host = True
            return await call_next(request)

        # Tenant hosts: the console does not exist here. Refused before
        # resolution, so the fence costs no database work and leaks no timing
        # signal about whether the boutique exists.
        if _is_platform_path(path):
            return _not_found()

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
