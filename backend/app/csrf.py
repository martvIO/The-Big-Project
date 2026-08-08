"""CSRF defense-in-depth for every cookie-authenticated surface.

SameSite=Lax already blocks classic cross-SITE CSRF, but once public tenant
pages exist (F10) a sibling subdomain is same-SITE — Lax does nothing there.
So mutating requests under a protected prefix whose Origin header names a
different host than the request Host are rejected. Requests without an Origin
header pass: they are not browser cross-origin submissions (curl,
server-to-server, tests).

The prefix list is COOKIE-DRIVEN, not layout-driven: a prefix belongs here when
a router under it reads an ambient credential the browser attaches by itself.
`/manage` is the staff surface. `/storefront/portal` is F24's client portal —
the first cookie reader outside `/manage`, and the exact case the paragraph
above describes: `evil.<base_domain>` is same-site with `victim.<base_domain>`,
so a body-less `<form method=post>` at `/storefront/portal/logout` or
`/storefront/portal/bell/seen` is a CORS-simple request that Lax happily signs.
The rest of `/storefront` stays out — those routers read no cookie, which their
cookie-blindness tests hold true."""

from urllib.parse import urlsplit

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# A tuple because `str.startswith` takes one directly — no loop, no join.
PROTECTED_PREFIXES = ("/manage", "/storefront/portal")

CSRF_ORIGIN_MISMATCH_BODY = {
    "error": {
        "code": "CSRF_ORIGIN_MISMATCH",
        "message": "Origin header does not match the request host.",
    }
}


def _hostname(netloc: str) -> str | None:
    try:
        return urlsplit(f"//{netloc}").hostname
    except ValueError:
        return None


def _origin_matches_host(origin: str, host: str | None) -> bool:
    if host is None:
        return False
    try:
        origin_host = urlsplit(origin).hostname
    except ValueError:
        return False
    # Hostname comparison only: the dev proxy serves the app on :5173 while the
    # API sees the same hostname, and the sibling-subdomain attack this blocks
    # is a hostname property. "null" and malformed Origins yield None → reject.
    return origin_host is not None and origin_host == _hostname(host)


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in MUTATING_METHODS and request.url.path.startswith(PROTECTED_PREFIXES):
            origin = request.headers.get("origin")
            if origin is not None and not _origin_matches_host(origin, request.headers.get("host")):
                return JSONResponse(CSRF_ORIGIN_MISMATCH_BODY, status_code=403)
        return await call_next(request)
