"""F26's HTTP surface, introspected rather than described.

Fast lane: no database. What these tests pin is the SHAPE of the route table —
which routes carry `get_current_operator` and which deliberately do not, and
that no response model can carry an invite code. Both are properties a reviewer
can only otherwise check by reading, and both are exactly the kind of thing a
later refactor breaks silently.
"""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.auth.tokens import hash_token
from app.core.config import get_settings
from app.main import create_app
from app.platform.auth import get_current_operator
from app.platform.join_router import _keys
from app.platform.router import _REFUSAL_STATUS, ConsoleCommandRefused
from app.platform.schemas import InviteCreatedResponse, InviteListResponse, InviteRow

CONSOLE = "http://admin.localtest.me"

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


# --- C2: the anonymous pair ---------------------------------------------------

JOIN_ROUTES = {
    ("POST", "/platform/join/invite"),
    ("POST", "/platform/join/redeem"),
}


def test_the_join_routes_exist_and_carry_no_operator_dependency(app: FastAPI) -> None:
    """⚠ INTROSPECTED, NOT ASSERTED BY COMMENT (spec test plan). D6 puts these
    two in their own module precisely so they cannot acquire an operator context
    by somebody editing the console router's dependency list — and this is what
    would notice if they did."""
    found = {
        (method, route.path)
        for route in _routes(app)
        for method in route.methods or ()
        if route.path.startswith("/platform/join") and method not in ("HEAD", "OPTIONS")
    }
    assert found == JOIN_ROUTES
    for route in _routes(app):
        if route.path.startswith("/platform/join"):
            assert not _gates(route), f"{route.path} acquired an operator gate"


def test_the_join_limiter_is_its_own_instance_with_its_own_ceiling(app: FastAPI) -> None:
    """`.memory/limiter-max-is-per-instance`: `max_attempts` lives on the
    LIMITER, so a key on the console login's budget would give signup the login
    ceiling and let a flood of bad codes close the platform's front door."""
    settings = get_settings()
    state = app.state
    assert state.invite_redeem_rate_limiter is not state.platform_login_rate_limiter
    assert state.invite_redeem_rate_limiter is not state.platform_login_global_rate_limiter
    assert state.invite_redeem_global_rate_limiter is not state.invite_redeem_rate_limiter
    assert state.invite_redeem_rate_limiter._max == settings.invite_redeem_max_attempts
    assert (
        state.invite_redeem_global_rate_limiter._max == settings.invite_redeem_global_max_attempts
    )


def test_the_join_budget_is_keyed_on_the_hash_and_never_on_the_raw_code() -> None:
    """A limiter holds its keys in memory for the whole window. A raw code there
    is a live boutique-creation credential sitting in a process-wide dict."""
    code = "some-invite-code-value"
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    keys = _keys(cast(Any, request), code)
    assert keys == [f"code:{hash_token(code)}"]
    assert code not in repr(keys)


def test_both_join_routes_share_one_budget_and_only_failures_spend_it(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shared, because a caller who has exhausted `redeem` must not be able to
    keep hammering `preview` — they refuse the same codes and write the same
    rows. Failures only, because an owner redeeming her own link would otherwise
    throttle herself out of her own boutique for fifteen minutes."""
    code = "aaaa-bbbb-cccc"

    # The lifespan's role guard is the only thing in this app that opens a
    # connection, and the fast lane points DATABASE_URL at a closed port on
    # purpose (F21). Nothing below reaches the service — `_spend` raises first.
    async def _no_role_check() -> None:
        return None

    monkeypatch.setattr("app.main.ensure_safe_database_role", _no_role_check)
    with TestClient(app, base_url=CONSOLE) as client:
        limiter = app.state.invite_redeem_rate_limiter
        for _ in range(get_settings().invite_redeem_max_attempts):
            limiter.record_failure(f"code:{hash_token(code)}")
        # The code is in the BODY on both routes now — a `?code=` would put a
        # live boutique-creation credential into every access log on the path.
        assert client.post("/platform/join/invite", json={"code": code}).status_code == 429
        redeemed = client.post(
            "/platform/join/redeem", json={"code": code, "owner_password": "a-long-enough-pw"}
        )
        assert redeemed.status_code == 429
        # The house 429 body, shared with the staff and console logins.
        assert redeemed.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    # A DIFFERENT code is untouched — the budget is per key, not one global
    # bucket. Asserted on the limiter rather than over HTTP: an unblocked request
    # would reach the service and the fast lane has no database by design (F21).
    assert not limiter.is_blocked(f"code:{hash_token('a-different-code')}")
