"""Response security headers, applied to every response the app emits.

**Registered LAST in create_app(), which makes it OUTERMOST.** Starlette runs
the most-recently-added middleware first, so being last is what puts this
outside TenantResolutionMiddleware — and that matters for one specific
response: the `404 TENANT_NOT_FOUND` that TenantResolutionMiddleware returns
from its own dispatch, without ever reaching a handler. On a public storefront
that is the single most-served response to anyone probing the domain, and an
inner middleware would miss it entirely.

**X-Frame-Options: DENY is API defense-in-depth, not the clickjacking fix for
the manage console.** The framable document is `index.html`, served by Vite in
dev and by a static host in production — neither passes through this
middleware. That requirement belongs to the frontend-deploy pipeline and is
recorded in the F10 spec's Risks 2. Embedding a tenant storefront in a
third-party site is not supported in v1; a per-tenant `frame-ancestors`
allowlist is E10's if a boutique ever asks for one.

**HSTS and CSP are deliberately absent, not forgotten.** HSTS needs the real
domain and a TLS-termination decision that `external-applications.md` #2 still
blocks, and stamping a `max-age` against a `.invalid` staging host is
meaningless. A CSP for a Vite bundle needs a nonce or hash story authored
against a deployed artifact, and there is no frontend deploy pipeline to author
it against yet. Owner: F21. Trigger: the domain is purchased.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    # Genuinely load-bearing on JSON: without it a browser may sniff a response
    # body into a content type the endpoint never intended to serve.
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        # setdefault, not assignment: a route that has a documented reason to
        # differ keeps its own value rather than being silently overwritten.
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
