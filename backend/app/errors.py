"""Domain error bases the platform-wide exception handlers bind to.

Starlette resolves a handler by walking `type(exc).__mro__`, so a handler
registered on a concrete class matches that class and its subclasses only. With
the 404 and domain-400 handlers bound to `app.boutique`'s own classes, a second
domain module raising its own same-named errors would return an unhandled **500**
for every one of them. These two bases are what let `app/catalog/` reuse the
house 404 and 400 without redeclaring — or silently missing — a handler.
"""


class DomainNotFoundError(Exception):
    """Target row doesn't exist for this tenant — including another tenant's id
    (RLS + the explicit predicate make foreign rows indistinguishable from
    missing ones, by design)."""


class DomainValidationError(Exception):
    """Domain-rule violation on a write; the handler maps it to the house-shape
    400 carrying the exception's own message."""
