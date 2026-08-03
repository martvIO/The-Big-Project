"""The printable check-in code: one URL and one SVG, both pure functions.

Nothing here reads a row, spends a budget or looks at a clock. The answer is a
total function of `(slug, base_domain)`, which is why D14 declined to cache it,
to persist it, or to accept an operator-uploaded image: the render is
microseconds and the route is hit when someone prints a sign.
"""

import io

import segno

from app.queue.schemas import CheckinQrResponse


def checkin_link(*, slug: str, base_domain: str) -> str:
    """`/checkin` on the tenant's own storefront host — `manage_link()`'s exact
    sibling (`booking/comms_templates.py:74-81`), and the only other place in
    the backend where a slug and a domain compose into a URL.

    Always https, dev `base_domain` included: a QR is followed by a camera with
    no chance to inspect it first, so an http:// code on a poster is a
    downgrade nobody can see.
    """
    return f"https://{slug}.{base_domain}/checkin"


def checkin_qr_svg(url: str) -> str:
    """`xmldecl=False`, and both other spellings are wrong — one of them
    silently.

    `save(buf, kind="svg")` prepends `<?xml version="1.0" …`. `svg_inline()`
    starts with `<svg` but emits NO namespace, and an SVG delivered through
    `<img src="data:image/svg+xml;…">` is parsed as a standalone XML document
    and draws nothing without it — a green suite and an empty square on a
    printed poster. `test_checkin_qr_link.py` asserts both halves separately
    because neither is sufficient alone.
    """
    buf = io.BytesIO()
    segno.make(url).save(buf, kind="svg", xmldecl=False)
    return buf.getvalue().decode()


class CheckinQrService:
    """`base_domain` injected at construction from `Settings`, never read from a
    global inside a handler; `slug` arrives per request from
    `get_current_tenant(request).slug`, which the Host header bound.

    It holds no session factory, no limiter and no clock, because it needs none
    — which is also why `test_checkin_qr_api.py` runs the real one rather than a
    fake, and gets a non-vacuous assertion about where the domain came from in
    exchange.
    """

    def __init__(self, *, base_domain: str) -> None:
        self._base_domain = base_domain

    def checkin_qr(self, slug: str) -> CheckinQrResponse:
        url = checkin_link(slug=slug, base_domain=self._base_domain)
        return CheckinQrResponse(checkin_url=url, qr_svg=checkin_qr_svg(url))
