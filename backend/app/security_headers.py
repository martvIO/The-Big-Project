"""Response security headers, applied to every response the app emits.

**Registered LAST in create_app(), which makes it OUTERMOST.** Starlette runs
the most-recently-added middleware first, so being last is what puts this
outside TenantResolutionMiddleware — and that matters for one specific
response: the `404 TENANT_NOT_FOUND` that TenantResolutionMiddleware returns
from its own dispatch, without ever reaching a handler. On a public storefront
that is the single most-served response to anyone probing the domain, and an
inner middleware would miss it entirely.

**`frame-ancestors 'none'` is now the clickjacking control, and
`X-Frame-Options: DENY` is the defence-in-depth it was always described as.**
This paragraph used to say the opposite — that the framable `index.html` was
served by Vite in dev and a static host in production and so never passed
through this middleware. **F55 (PR #26) made that false**: FastAPI serves both
SPA shells itself (`main.py`'s `_SpaFallbackRoute` and the `/manage` mount;
`test_spa_serving.py:182-186` asserts the shells carry these headers), and CI
copies each `dist/` into `app/static/`. Both shells therefore pass through here
and get the full policy. Embedding a tenant storefront in a third-party site is
still not supported; a per-tenant `frame-ancestors` allowlist is E10's if a
boutique ever asks for one.

**HSTS and the CSP are emitted here, closing `.planning/security-checklist-v1.md`
row `R33` ("Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options")
and, for the CSP's third-party-script clause, `R28`.** The row was cited here as
"checklist row 33" before F21; the ids are frozen as `R<n>` labels now, so the
citation survives renumbering rather than silently pointing at whatever ends up
on that line. **The two blockers this paragraph used to
name were both wrong.** It said HSTS "needs the real domain and a
TLS-termination decision". It needs neither: a browser applies an HSTS header
only to the host that sent it (plus that host's subtree under
`includeSubDomains`), so it can never reach a sibling of a shared parent and
emitting it from `*.up.railway.app` is safe — and a browser ignores HSTS over
plain HTTP anyway, which is why one scheme condition replaces a config flag. It
also said a CSP "needs a nonce or hash story authored against a deployed
artifact": the deployed artifact has nothing inline (Tailwind v4 compiles at
build time and the build emits an external stylesheet), so there is nothing for
a nonce to cover, and the pipeline it said did not exist has existed since F55.

**Neither header may join `SECURITY_HEADERS`.** That dict is compared with `==`
by seven test modules, which is only meaningful for headers that are
unconditional and constant. The CSP is settings-derived (`build_csp`, built once
at `create_app()` time) and HSTS is request-derived (`_effective_scheme`), so
both are emitted BESIDE the dict by the same middleware and carry their own
tests in `tests/test_security_headers.py`.
"""

from urllib.parse import urlsplit

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import Settings

CSP_HEADER = "Content-Security-Policy"

HSTS_HEADER = "Strict-Transport-Security"
# No `preload`. Submission to the browser preload list is effectively
# irreversible and is a decision for a domain that resolves, not for
# *.up.railway.app.
HSTS_VALUE = "max-age=31536000; includeSubDomains"

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    # Genuinely load-bearing on JSON: without it a browser may sniff a response
    # body into a content type the endpoint never intended to serve.
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def media_csp_origin(settings: Settings) -> str | None:
    """The one origin the policy must admit that is not `'self'` — the media
    bucket, which serves dress photos over presigned GET (`img-src`) and receives
    presigned POST uploads from `apps/manage/src/api.ts` (`connect-src`).

    Reduced to scheme + netloc because a CSP source is an ORIGIN: a trailing
    slash or a path turns it into a path match with different semantics, and the
    browser silently applies the different one.

    The BUCKET NAME never appears. `storage/s3.py:73-78` records that an explicit
    `endpoint_url` forces path-style addressing, and the default endpoint is the
    regional host itself — so the URL is `s3.<region>.amazonaws.com/<bucket>` and
    never `<bucket>.s3.<region>.amazonaws.com`. That is what makes this one line
    rather than a bucket-name-dependent branch.

    `None` when no bucket is configured. No bucket is a supported deployment
    (config.py:265-269), and it gets a strictly TIGHTER policy — never a broken
    one.
    """
    if not settings.media_bucket:
        return None
    raw = settings.media_endpoint_url or f"https://s3.{settings.media_region}.amazonaws.com"
    parts = urlsplit(raw)
    return f"{parts.scheme}://{parts.netloc}"


def build_csp(settings: Settings) -> str:
    """D3's ten directives, built at `create_app()` time from `Settings` — never
    a module constant, because the media origin is a deployment fact.

    `style-src` carries no `'unsafe-inline'`: the build emits an external
    stylesheet and Tailwind v4 compiles at build time. If that ever changes, the
    CSP reds in e2e, which is the correct place for it to red.

    `frame-ancestors 'none'` is what actually stops clickjacking on the shells
    now that FastAPI serves them; `X-Frame-Options: DENY` stays as the
    defence-in-depth it was always described as. `form-action` and `base-uri`
    close the two injection shapes a `default-src` does not.

    **`img-src` carries `data:` and no other directive does.** D3 named
    `assetsInlineLimit` (Vite's default, 4096) as a live tripwire, and it was
    already tripped when the browser test first ran: `modryn-mark.svg` is 973
    bytes, so the build inlines it as a `data:image/svg+xml` URI and the console
    login screen's MODRYN lockup — its own h1 — is refused by an `img-src` of
    `'self'` alone. One source on one directive is the prescribed widening. It
    must never spread: a data URI cannot execute, which is the whole reason it is
    tolerable here and intolerable on `script-src` or `connect-src`.
    """
    media = media_csp_origin(settings)
    img = f"'self' data: {media}" if media else "'self' data:"
    external = f"'self' {media}" if media else "'self'"
    return "; ".join(
        (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            f"img-src {img}",
            "font-src 'self'",
            f"connect-src {external}",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "object-src 'none'",
        )
    )


def _effective_scheme(request: Request) -> str:
    """The scheme the OUTERMOST hop served, which on Railway is never the scheme
    this process sees on `request.url` — TLS terminates at the edge and the app
    is spoken to over plain HTTP.

    `x-forwarded-proto` is read here WITHOUT a `trust_forwarded_for` guard, and
    the asymmetry with `client_ip` (auth/client_ip.py) is deliberate rather than an
    oversight. A spoofed `x-forwarded-for` poisons a rate-limit bucket keyed by
    IP — a real attack with a real budget to spend. A spoofed
    `x-forwarded-proto: https` over plain HTTP makes the app emit an HSTS header
    that the browser then IGNORES, because HSTS delivered over http is ignored by
    specification. There is nothing to spend and nothing to poison, so this needs
    no config flag and no trusted-proxy declaration.

    The LAST entry wins: a proxy chain appends, so the final element is what the
    hop closest to this process actually served. Reading the first would let a
    client-supplied prefix decide it.
    """
    forwarded = request.headers.get("x-forwarded-proto")
    if forwarded:
        return forwarded.split(",")[-1].strip().lower()
    return request.url.scheme


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, csp: str) -> None:
        # Passed in rather than read here: the policy is built ONCE from Settings
        # at create_app() time, so no request pays for a urlsplit and a test can
        # build an app with any deployment's policy without patching globals.
        super().__init__(app)
        self._csp = csp

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        # setdefault, not assignment: a route that has a documented reason to
        # differ keeps its own value rather than being silently overwritten.
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        # Both of these are emitted BESIDE SECURITY_HEADERS and never inside it.
        # Seven test modules compare that dict with `==` on the strength of every
        # member being unconditional and constant; the CSP is settings-derived
        # and HSTS is request-derived, so neither can join it.
        response.headers.setdefault(CSP_HEADER, self._csp)
        if _effective_scheme(request) == "https":
            response.headers.setdefault(HSTS_HEADER, HSTS_VALUE)
        return response
