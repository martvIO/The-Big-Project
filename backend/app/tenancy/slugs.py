import re

# Subdomains that can never be boutiques. Imported by the Feature 6 provisioning
# CLI too, so reservation is enforced both at request time and at creation time.
RESERVED_SLUGS = frozenset(
    {
        "admin",
        "api",
        "app",
        "assets",
        "cdn",
        "docs",
        "mail",
        "staging",
        "static",
        "status",
        "support",
        "www",
    }
)

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def is_valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.fullmatch(slug)) and slug not in RESERVED_SLUGS


def extract_slug(host: str | None, base_domain: str) -> str | None:
    """Leftmost DNS label of `<label>.<base_domain>` — the ONLY source of tenant
    identity in the platform. Anything else (apex, deeper nesting, foreign
    domains, IP/IPv6 literals, missing header) returns None and fails closed."""
    if not host or "]" in host:
        return None
    hostname = host.rsplit(":", 1)[0] if ":" in host else host
    hostname = hostname.lower().rstrip(".")
    suffix = "." + base_domain.lower()
    if not hostname.endswith(suffix):
        return None
    label = hostname[: -len(suffix)]
    if not label or "." in label:
        return None
    return label
