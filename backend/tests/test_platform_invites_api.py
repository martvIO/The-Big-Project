"""F26's HTTP surface, introspected rather than described.

Fast lane: no database. What these tests pin is the SHAPE of the route table —
which routes carry `get_current_operator` and which deliberately do not, and
that no response model can carry an invite code. Both are properties a reviewer
can only otherwise check by reading, and both are exactly the kind of thing a
later refactor breaks silently.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.main import create_app
from app.platform.auth import get_current_operator
from app.platform.router import _REFUSAL_STATUS, ConsoleCommandRefused
from app.platform.schemas import InviteCreatedResponse, InviteListResponse, InviteRow

OPERATOR_ROUTES = {
    ("POST", "/platform/invites"),
    ("GET", "/platform/invites"),
    ("POST", "/platform/invites/revoke"),
}


async def _null_resolver(slug: str) -> None:
    return None


@pytest.fixture
def app() -> FastAPI:
    return create_app(resolver=_null_resolver)


def _leaf_routes(node: Any) -> Iterator[Any]:
    """FastAPI wraps an included router in `_IncludedRouter` rather than
    flattening it — recurse through `original_router`, or this walker sees only
    the docs routes and every assertion below passes vacuously."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def _routes(app: FastAPI) -> list[APIRoute]:
    return [route for route in _leaf_routes(app) if isinstance(route, APIRoute)]


def _gates(route: APIRoute) -> bool:
    """Walks the whole dependant tree, not just the route's own list: the gate is
    declared on the ROUTER, so it arrives as an inherited dependency and a check
    against `route.dependencies` alone would report every one of these as
    ungated."""
    seen: list[Any] = [route.dependant]
    while seen:
        dependant = seen.pop()
        if dependant.call is get_current_operator:
            return True
        seen.extend(dependant.dependencies)
    return False


def test_the_three_operator_invite_routes_exist_and_are_gated(app: FastAPI) -> None:
    found = {
        (method, route.path)
        for route in _routes(app)
        for method in route.methods or ()
        if route.path.startswith("/platform/invites") and method not in ("HEAD", "OPTIONS")
    }
    assert found == OPERATOR_ROUTES
    for route in _routes(app):
        if route.path.startswith("/platform/invites"):
            assert _gates(route), f"{route.path} carries no operator gate"


def test_no_invite_list_response_can_carry_a_code(app: FastAPI) -> None:
    """⚠ THE ONE-TIME PROPERTY, asserted structurally. The console's table is
    rendered from `InviteRow`; if a `code` or `code_hash` field ever appeared on
    it, every live invite's credential would be re-rendered on every mount and
    the one-time panel would be theatre (design A2 rule 7)."""
    forbidden = {"code", "code_hash"}
    assert forbidden.isdisjoint(InviteRow.model_fields)
    assert forbidden.isdisjoint(InviteListResponse.model_fields)
    # …and exactly one response model in the product may carry it.
    assert "code" in InviteCreatedResponse.model_fields

    listing = next(
        route
        for route in _routes(app)
        if route.path == "/platform/invites" and "GET" in (route.methods or ())
    )
    assert listing.response_model is InviteListResponse


def test_the_invite_refusals_map_to_the_statuses_the_console_keys_on() -> None:
    """`invalid_invite` is ONE code for unknown / expired / redeemed / revoked,
    at 404 (D5). A second code for "already redeemed" would tell an anonymous
    caller that a code was real."""
    assert _REFUSAL_STATUS["invalid_invite"] == 404
    assert _REFUSAL_STATUS["invite_not_found"] == 404
    assert ConsoleCommandRefused("invalid_invite").status == 404
    assert ConsoleCommandRefused("slug_taken").status == 409
    assert ConsoleCommandRefused("password_too_short").status == 400
    # Unmapped still degrades to 400 with its own code, never a 500.
    assert ConsoleCommandRefused("something_new").status == 400
