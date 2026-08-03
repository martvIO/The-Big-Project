"""`checkin_link()` and the QR render as pure functions — no app, no Postgres.

The link half is `test_booking_comms_templates.py`'s shape: `manage_link()` is
the only other place in the backend where a slug and a domain compose into a
URL, and this is its exact sibling.

The render half exists because BOTH obvious segno spellings are wrong and one of
them fails silently — see the docstring on the xmlns test.
"""

from app.queue.qr import checkin_link, checkin_qr_svg

SVG_NAMESPACE = 'xmlns="http://www.w3.org/2000/svg"'


# --- the link ---------------------------------------------------------------


def test_checkin_link_is_the_slug_host_and_the_printed_path() -> None:
    assert checkin_link(slug="bella", base_domain="modryn.co.il") == (
        "https://bella.modryn.co.il/checkin"
    )


def test_checkin_link_is_never_http_even_on_the_dev_domain() -> None:
    """A QR is scanned by a camera and followed without a chance to inspect it,
    so an http:// code printed on a poster is a downgrade nobody can see."""
    assert checkin_link(slug="bella", base_domain="localtest.me").startswith("https://")


def test_the_dev_base_domain_is_included_rather_than_stripped() -> None:
    assert "localtest.me" in checkin_link(slug="bella", base_domain="localtest.me")


def test_there_is_no_double_slash_anywhere_after_the_scheme() -> None:
    link = checkin_link(slug="bella", base_domain="modryn.co.il")
    assert "//" not in link.removeprefix("https://")


def test_the_slug_survives_composition_unescaped() -> None:
    """The slug is the tenant's own subdomain label, and it reaches the poster
    verbatim. A percent-encoded or lower-cased one would print a URL that
    resolves to a different host, or to none."""
    assert checkin_link(slug="bella-bridal", base_domain="modryn.co.il") == (
        "https://bella-bridal.modryn.co.il/checkin"
    )


# --- the render -------------------------------------------------------------


def test_the_svg_starts_with_its_own_root_element_and_no_xml_declaration() -> None:
    """segno's default `save(buf, kind="svg")` emits `<?xml version="1.0" …`
    first. Through `<img src="data:image/svg+xml;utf8,…">` that is a second
    thing the browser has to parse before it reaches the drawing, and the
    console's `encodeURIComponent` round trip has no reason to carry it."""
    assert checkin_qr_svg("https://bella.modryn.co.il/checkin").startswith("<svg")


def test_the_svg_carries_the_namespace_and_this_is_the_assertion_that_matters() -> None:
    """`svg_inline()` satisfies the test above and renders BLANK: an SVG
    delivered through a `data:` URI is parsed as a standalone XML document and
    draws nothing without the namespace. A green suite and an empty square on a
    printed poster — which is why the two halves are asserted separately and
    neither is sufficient alone."""
    assert SVG_NAMESPACE in checkin_qr_svg("https://bella.modryn.co.il/checkin")


def test_the_render_is_a_pure_function_of_its_url() -> None:
    """No cache, no persistence, no clock: two calls on one URL are the same
    bytes, and two different URLs are different bytes. That is the whole reason
    D14 declined to store it."""
    first = checkin_qr_svg("https://bella.modryn.co.il/checkin")
    assert first == checkin_qr_svg("https://bella.modryn.co.il/checkin")
    assert first != checkin_qr_svg("https://vered.modryn.co.il/checkin")
