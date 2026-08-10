"""F31 fast tests: the default-deny role walker, the admitted-set policy test,
the RoleGate unit matrix, and an HTTP matrix proving the wiring — shift_manager
admitted on every /manage route except the OWNER_ONLY set. Fake services +
hardcoded TenantContext resolver, no database (test_boutique_api.py style).

Coverage split: the structural tests derive from the LIVE route table, so every
/manage route — present and future — is policy-checked without a fake; the HTTP
matrix reuses the hand-maintained ROUTES tables of test_boutique_api and
test_catalog_api, so it covers exactly what those modules cover."""

import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_atelier_api import ATELIER_ROUTES, FakeAtelierService
from test_boutique_api import (
    ROUTES,
    TENANT,
    TERMS_BODY,
    TOKEN,
    FakeAuthService,
    FakeBoutiqueService,
)
from test_catalog_api import ROUTES as CATALOG_ROUTES
from test_catalog_api import FakeCatalogService
from test_floor_api import FLOOR_ROUTES, FakeFloorService
from test_payments_api import ROUTES as GATEWAY_ROUTES
from test_privacy_api import PRIVACY_ROUTES, FakePrivacyService

from app.auth.dependencies import (
    NotAuthorizedError,
    get_auth_service,
    require_role,
)
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.catalog.router import get_media_storage
from app.csrf import CSRF_ORIGIN_MISMATCH_BODY
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffRole
from app.storage.memory import InMemoryMediaStorage
from app.tenancy.middleware import TenantContext

TERMS_PUBLISH = ("POST", "/manage/terms")

# Spelled as ROUTE-TABLE TEMPLATES, not concrete URLs: the walkers below read
# route.path, so a literal /manage/staff/<uuid> would never match and
# test_route_table_matches_the_permission_matrix would red-fail with "routes lock
# shift_manager out but are not in OWNER_ONLY".
STAFF_LIST = ("GET", "/manage/staff")
STAFF_CREATE = ("POST", "/manage/staff")
STAFF_PATCH = ("PATCH", "/manage/staff/{staff_id}")
STAFF_DELETE = ("DELETE", "/manage/staff/{staff_id}")
# F38's three. They inherit the router-level gate rather than carrying one of
# their own, so what makes that inheritance a TESTED fact rather than a hopeful
# one is their presence in OWNER_ONLY below — the walker reads `allowed_roles`
# off the mounted route and compares.
STAFF_PHOTO_PRESIGN = ("POST", "/manage/staff/{staff_id}/photo/presign")
STAFF_PHOTO_CONFIRM = ("POST", "/manage/staff/{staff_id}/photo/confirm")
STAFF_PHOTO_DELETE = ("DELETE", "/manage/staff/{staff_id}/photo")

# F17's four. The first router in the repo that is owner-only IN FULL (D13): a
# shift manager has no relationship to the boutique's merchant account, and the
# READ itself discloses whether the business can take money — which is why even
# GET is here.
GATEWAY_GET = ("GET", "/manage/gateway")
GATEWAY_SET = ("PUT", "/manage/gateway/credentials")
GATEWAY_VALIDATE = ("POST", "/manage/gateway/validate")
GATEWAY_DISCONNECT = ("DELETE", "/manage/gateway/credentials")

# F20's three. The FOURTH privacy route, POST /manage/privacy/marketing-withdraw,
# is DELIBERATELY ABSENT — Gate 1 Q4 admits the shift manager there, and
# test_marketing_withdraw_is_not_owner_only_in_the_route_table below asserts that
# absence POSITIVELY. Adding it here to make the set look symmetric would silently
# revoke a permission the user explicitly granted, and would pass BOTH branches of
# test_route_table_matches_the_permission_matrix while doing it.
PRIVACY_PUT = ("PUT", "/manage/privacy")
PRIVACY_EXPORT = ("POST", "/manage/privacy/subject-export")
PRIVACY_ERASE = ("POST", "/manage/privacy/subject-erase")
PRIVACY_WITHDRAW = ("POST", "/manage/privacy/marketing-withdraw")

# The routes a shift_manager must NOT reach — the spec's permission matrix,
# pinned. F51's staff router added its four rows and F17's gateway router adds
# these four; adding an owner-only tightening anywhere else fails
# test_route_table_matches_the_permission_matrix, so narrowing the shift
# manager's surface stays a deliberate, reviewed act.
OWNER_ONLY = {
    TERMS_PUBLISH,
    STAFF_LIST,
    STAFF_CREATE,
    STAFF_PATCH,
    STAFF_DELETE,
    STAFF_PHOTO_PRESIGN,
    STAFF_PHOTO_CONFIRM,
    STAFF_PHOTO_DELETE,
    GATEWAY_GET,
    GATEWAY_SET,
    GATEWAY_VALIDATE,
    GATEWAY_DISCONNECT,
    PRIVACY_PUT,
    PRIVACY_EXPORT,
    PRIVACY_ERASE,
}

# ROUTE-TABLE TEMPLATES, for the same reason STAFF_PATCH is one: the classifier
# below reads `route.path`, so a concrete /manage/floor/staff/<uuid>/... would
# never match and would fail on the `missing` assertion instead.
# test_floor_api.FLOOR_ROUTES is the CONCRETE spelling of the same three, used by
# the HTTP walks (plan C4).
FLOOR_READ = ("GET", "/manage/floor")
FLOOR_BREAK_START = ("POST", "/manage/floor/staff/{staff_id}/break/start")
FLOOR_BREAK_END = ("POST", "/manage/floor/staff/{staff_id}/break/end")
# F36's six. The claim and the release carry a TARGET-dependent rule (self, or
# elevated on anyone) which no RoleGate can express, so they are open here and
# refused in the service. The two dress verbs carry no ownership rule at all
# (D4). The two GETs are the pickers the floor roles cannot otherwise reach,
# because the catalog and bookings routers admit two roles and RoleGate narrows
# only.
FLOOR_CLAIM = ("POST", "/manage/floor/rooms/{room_id}/claim")
FLOOR_RELEASE = ("POST", "/manage/floor/assignments/{assignment_id}/release")
FLOOR_DRESS_ADD = ("POST", "/manage/floor/assignments/{assignment_id}/dresses")
FLOOR_DRESS_REMOVE = (
    "DELETE",
    "/manage/floor/assignments/{assignment_id}/dresses/{binding_id}",
)
FLOOR_DRESS_LIST = ("GET", "/manage/floor/dresses")
FLOOR_CLIENT_LIST = ("GET", "/manage/floor/clients")
# F58's three. The two dispatch verbs carry the CLAIM's target-dependent rule
# verbatim — herself, or elevated on anyone — which no RoleGate can express, so
# they are open here and refused in the service. `call` has no target staffer at
# all: a summons is not destructive, and reception, a sales assistant and a
# seamstress all legitimately call the next woman forward.
FLOOR_TAKE_NEXT = ("POST", "/manage/floor/rooms/{room_id}/take-next")
FLOOR_ASSIGN = ("POST", "/manage/floor/rooms/{room_id}/assign")
FLOOR_QUEUE_CALL = ("POST", "/manage/floor/queue/{ticket_id}/call")
# F37's five, and NOT ONE of them is tightened. Every rule in that feature reads
# the ROW before it can decide — `target_staff_user_id`, `raised_by`,
# `accepted_by` — and a `RoleGate` can express only a PURE role predicate. There
# is no gate that can say "the person this alert names", so all five refusals are
# 404s from the service and all five paths belong here.
FLOOR_SOS_READ = ("GET", "/manage/floor/sos")
FLOOR_SOS_RAISE = ("POST", "/manage/floor/sos")
FLOOR_SOS_ACCEPT = ("POST", "/manage/floor/sos/{alert_id}/accept")
FLOOR_SOS_RESOLVE = ("POST", "/manage/floor/sos/{alert_id}/resolve")
FLOOR_SOS_CANCEL = ("POST", "/manage/floor/sos/{alert_id}/cancel")
# F35's two. POPULATED here rather than exempted anywhere: the bell's audience
# IS every signed-in staffer, so they belong in every non-elevated role's row,
# and a route that quietly failed to appear would be a route nobody proved the
# gate on. Neither is tightened — there is no narrower gate that would be right.
FLOOR_BELL_READ = ("GET", "/manage/floor/notifications")
FLOOR_BELL_MARK = ("POST", "/manage/floor/notifications/read")

# ⚠ The SIX tightened routes are DELIBERATELY ABSENT — the three registry verbs
# (`POST`/`PATCH`/`DELETE /manage/floor/rooms…`), `handover`, and F58's `skip`
# and `remove`. Their absence is the assertion that the tightening is real, and
# it is what keeps the comment above ("the exhaustive list of what they may
# reach") true. Adding `handover` here to make a red go away would make this
# table assert that a seamstress may reach a route she always gets a 403 on.
#
# ⚠ **AND THE MIDDLE OPTION FOR SKIP AND REMOVE IS STRUCTURALLY FORBIDDEN, not
# merely declined.** `require_role(OWNER, SHIFT_MANAGER, RECEPTION)` lands in
# `admits_floor` (the intersection is non-empty) AND in `partial` (it is not a
# superset of FLOOR_ROLES), so assertion 2 below red-fails on a route that is
# arguably correct — and the fix a reviewer reaches for is relaxing the very
# assertion this table exists for. So every route in this product is all-five or
# exactly-two, skip and remove are ELEVATED, and the product cost is RECORDED
# rather than engineered around: a reception staffer cannot skip a no-show or
# remove a duplicate, and calls a shift manager. The upgrade path if a pilot asks
# is the service-side target-dependent form; it does not apply today because skip
# has no "target" that can be the caller.
FLOOR_OPEN = {
    FLOOR_READ,
    FLOOR_BREAK_START,
    FLOOR_BREAK_END,
    FLOOR_CLAIM,
    FLOOR_RELEASE,
    FLOOR_DRESS_ADD,
    FLOOR_DRESS_REMOVE,
    FLOOR_DRESS_LIST,
    FLOOR_CLIENT_LIST,
    FLOOR_TAKE_NEXT,
    FLOOR_ASSIGN,
    FLOOR_QUEUE_CALL,
    FLOOR_SOS_READ,
    FLOOR_SOS_RAISE,
    FLOOR_SOS_ACCEPT,
    FLOOR_SOS_RESOLVE,
    FLOOR_SOS_CANCEL,
    FLOOR_BELL_READ,
    FLOOR_BELL_MARK,
}

# F41's seven plus F42's capacity write, same templates-not-urls rule.
# test_atelier_api.ATELIER_ROUTES is the CONCRETE spelling, used by the HTTP
# walks below.
#
# ⚠ BOTH TIGHTENED ROUTES ARE SPLIT OUT, AND THIS IS NOT TIDINESS. The walker
# classifies on `effective = frozenset.intersection(*role_sets)`, and each of
# these carries a per-route require_role(OWNER, SHIFT_MANAGER) on top of the
# router's three — so its effective set is {owner, shift_manager} and seamstress
# is NOT in it. A seamstress row that named either would be one element larger
# than reality and would RED A CORRECT BUILD on the one test F57's Risk 1
# declares untouchable, which is the exact situation that gets a test relaxed.
ATELIER_DELETE = ("POST", "/manage/atelier/tickets/{ticket_id}/delete")
# ⚠ F42's, and it is the SECOND instance of exactly the shape that breaks under
# `any(...)`. She may not set her own weekly hours or anybody else's: they are
# the DENOMINATOR every other bar in the workroom is read against, which makes
# it a staffing decision about the whole board's arithmetic rather than a record
# of work she has done.
ATELIER_CAPACITY = ("POST", "/manage/atelier/seamstresses/{staff_user_id}/capacity")
ATELIER_ELEVATED = {ATELIER_DELETE, ATELIER_CAPACITY}
ATELIER_OPEN = {
    ("GET", "/manage/atelier/tickets"),
    ("POST", "/manage/atelier/tickets"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/update"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/assign"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/stage/advance"),
    ("POST", "/manage/atelier/tickets/{ticket_id}/stage/undo"),
    *ATELIER_ELEVATED,
}

# F39's eight, same templates-not-urls rule. `test_shifts_api.ROUTES` is the
# CONCRETE spelling, used by the HTTP walks below.
#
# ⚠ NOTHING HERE ENTERS `OWNER_ONLY`, and that is the one edit that would
# silently make spec D5 false. A shift manager is admitted EVERYWHERE in this
# feature: she is `ELEVATED_ROLES`, so she configures the templates, reads the
# roster-readiness list and records on a staffer's behalf past the deadline. Both
# gates on all five tightened routes admit her, so
# `test_route_table_matches_the_permission_matrix`'s `all(...)` branch passes
# unedited.
#
# ⚠ THE FIVE TIGHTENED ROUTES ARE SPLIT OUT for `ATELIER_ELEVATED`'s reason,
# which is not tidiness: the walker classifies on
# `frozenset.intersection(*role_sets)`, and each of these carries a per-route
# require_role(OWNER, SHIFT_MANAGER) on top of the router's five — so its
# effective set is {owner, shift_manager} and the three floor roles are NOT in
# it. A reach row naming one of them would be larger than reality and would RED A
# CORRECT BUILD.
SHIFTS_TEMPLATES_READ = ("GET", "/manage/shifts/templates")
SHIFTS_WEEK_READ = ("GET", "/manage/shifts/week")
# ⚠ OPEN AT THE GATE AND NARROWED IN THE SERVICE. Its real rule is
# target-dependent — herself, or elevated on anyone — which no `RoleGate` can
# express, so the 403 comes from `ShiftsService._authorize`. This is the same
# shape as the floor claim and release, and it belongs in every non-elevated
# role's row because every staffer legitimately saves her own week.
SHIFTS_WEEK_WRITE = ("PUT", "/manage/shifts/week/availability")
SHIFTS_TEMPLATE_CREATE = ("POST", "/manage/shifts/templates")
SHIFTS_TEMPLATE_UPDATE = ("PATCH", "/manage/shifts/templates/{template_id}")
SHIFTS_TEMPLATE_DELETE = ("DELETE", "/manage/shifts/templates/{template_id}")
SHIFTS_TEMPLATE_SEED = ("POST", "/manage/shifts/templates/seed")
# Carries every colleague's display name and what she said, which is why it is
# the one READ in this feature that narrows.
SHIFTS_SUBMISSIONS = ("GET", "/manage/shifts/week/submissions")

SHIFTS_ELEVATED = {
    SHIFTS_TEMPLATE_CREATE,
    SHIFTS_TEMPLATE_UPDATE,
    SHIFTS_TEMPLATE_DELETE,
    SHIFTS_TEMPLATE_SEED,
    SHIFTS_SUBMISSIONS,
}
SHIFTS_OPEN = {SHIFTS_TEMPLATES_READ, SHIFTS_WEEK_READ, SHIFTS_WEEK_WRITE}


# ⚠ THE EXHAUSTIVE REACH OF EACH NON-ELEVATED ROLE, one row each, asserted as a
# SET EQUALITY per role.
#
# This replaces F57's single `FLOOR_ROLES`/`FLOOR_OPEN` pair, and the reason is
# F41: the old model was that the three non-elevated roles MOVE AS A BLOCK, and
# an atelier router that admits `seamstress` and not the other two makes that
# false — deliberately and visibly. Under the old pair that is CORRECT CODE
# FAILING A CORRECT TEST, which is precisely the situation Risk 1 warns leads to
# a reviewer relaxing the assertion.
#
# What the per-role table gives up: only the assumption that the three are
# interchangeable. What it keeps, every word of it: still an exact set equality,
# still derived from the LIVE route table, still catches a route that quietly
# lost its gate (an ungated route's `effective` is empty, so it drops out of
# every row and the equality fails), still fails the day some future router
# copy-pastes a wide gate, and now ALSO fails if one of these roles is admitted
# to a route the other two reach.
NON_ELEVATED_REACH: dict[str, frozenset[tuple[str, str]]] = {
    StaffRole.RECEPTION.value: frozenset(FLOOR_OPEN | SHIFTS_OPEN),
    StaffRole.SALES_ASSISTANT.value: frozenset(FLOOR_OPEN | SHIFTS_OPEN),
    StaffRole.SEAMSTRESS.value: frozenset(
        FLOOR_OPEN | SHIFTS_OPEN | (ATELIER_OPEN - ATELIER_ELEVATED)
    ),
}

# The probe for "a role the enum does not know", shared verbatim by
# test_catalog_api and test_migrations. Deliberately NOT 'reception' (or
# seamstress/sales_assistant): 0011's comment named those three as the next roles
# to join StaffRole, and F57 IS the day they did — so a test using one of them as
# the unknown-role probe would now silently assert the opposite of its own name.
# The sentinel was chosen for exactly this day and it held; the tripwire below is
# what makes that a fact rather than a hope.
UNKNOWN_ROLE = "no-such-role"
# The tripwire that keeps the sentence above true.
assert UNKNOWN_ROLE not in {role.value for role in StaffRole}, (
    "UNKNOWN_ROLE became a real StaffRole — every unknown-role test now asserts "
    "the opposite of its name; pick a new sentinel"
)

# The ONLY /manage routes allowed to carry no RoleGate — and NOT for the same
# reason, which an earlier version of this comment got wrong:
#   POST /manage/auth/login  — anonymous by definition.
#   POST /manage/auth/logout — ANONYMOUS TOO, not "any authenticated staff". It
#       carries no auth dependency at all (app/auth/router.py): with no cookie
#       the revoke is skipped and the caller still gets 200 {"ok": true}. That is
#       deliberate — gating the one action a staffer takes when her session is
#       already broken would 401 it. Pinned by the two logout tests below.
#   GET  /manage/auth/me     — genuinely any-authenticated-staff: get_current_staff
#       with no RoleGate, so it 401s without a session and never 403s with one.
# Everything else must refuse or admit each role deliberately. Pinned so pruning
# a route here is a visible act.
UNGATED_ALLOWLIST = {
    ("POST", "/manage/auth/login"),
    ("POST", "/manage/auth/logout"),
    ("GET", "/manage/auth/me"),
}


async def _null_resolver(slug: str) -> TenantContext | None:
    """No host resolves. Enough to build the app and read its route table."""
    return None


def _leaf_routes(node: Any) -> Iterator[Any]:
    """FastAPI wraps an included router in `_IncludedRouter` rather than
    flattening it — recurse through `original_router` like test_storefront_api,
    or the walker sees only the docs routes and passes vacuously."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def _operator_gates(dependant: Any) -> Iterator[bool]:
    """F25's console gate, found however deep — router-level `dependencies=[...]`
    and a per-route `Depends` both surface here. `_gate_role_sets`' shape for a
    dependency that carries no attribute to introspect: the identity of the
    callable IS the gate."""
    from app.platform.auth import get_current_operator

    for dep in getattr(dependant, "dependencies", []):
        if dep.call is get_current_operator:
            yield True
        yield from _operator_gates(dep)


def _gate_role_sets(dependant: Any) -> Iterator[frozenset[str]]:
    """Every RoleGate in the dependency tree, however deep — router-level gates
    and per-route tightenings both surface here via `allowed_roles`."""
    for dep in getattr(dependant, "dependencies", []):
        roles = getattr(dep.call, "allowed_roles", None)
        if roles is not None:
            yield roles
        yield from _gate_role_sets(dep)


# --- default-deny: structural proof over the live route table ---


def test_every_manage_route_is_role_gated() -> None:
    app = create_app(resolver=_null_resolver)
    seen: set[tuple[str, str]] = set()
    ungated: list[tuple[str, str]] = []
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or not path.startswith("/manage"):
            continue
        gated = bool(list(_gate_role_sets(dependant)))
        for method in getattr(route, "methods", None) or ():
            seen.add((method, path))
            if (method, path) in UNGATED_ALLOWLIST:
                continue
            if not gated:
                ungated.append((method, path))
    # An empty walk would make this guard vacuous — the storefront suite's
    # derivation lesson applies here too.
    assert seen - UNGATED_ALLOWLIST, "no gated /manage route was discovered — walker is broken"
    assert seen >= UNGATED_ALLOWLIST, "allowlist names a route that no longer exists — prune it"
    assert not ungated, f"role-ungated /manage routes: {sorted(ungated)}"


def test_gates_admit_only_known_roles() -> None:
    # Guards against drift: if RoleGate ever stops normalizing through
    # StaffRole (e.g. frozenset(allowed) instead of .value), a gate built from
    # a stale or removed member would silently lock that role out — this pins
    # every admitted string to the live enum.
    known = {role.value for role in StaffRole}
    app = create_app(resolver=_null_resolver)
    checked = 0
    for route in _leaf_routes(app):
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for roles in _gate_role_sets(dependant):
            assert roles, "an empty RoleGate admits nobody"
            assert roles <= known, f"gate admits unknown roles: {roles - known}"
            checked += 1
    assert checked, "no RoleGate was discovered — walker is broken"


def test_route_table_matches_the_permission_matrix() -> None:
    """The spec's matrix, asserted over the LIVE route table: every /manage
    route admits shift_manager unless OWNER_ONLY pins it, and every OWNER_ONLY
    route carries a gate that excludes shift_manager. Catches the mutation the
    walker cannot — a gate that is present and well-formed but admits the wrong
    set (e.g. an accidental owner-only catalog router)."""
    app = create_app(resolver=_null_resolver)
    wrongly_narrowed: list[tuple[str, str]] = []
    unenforced_owner_only: list[tuple[str, str]] = []
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or not path.startswith("/manage"):
            continue
        role_sets = list(_gate_role_sets(dependant))
        if not role_sets:
            continue  # ungated routes are the walker test's job
        for method in getattr(route, "methods", None) or ():
            if (method, path) in OWNER_ONLY:
                if not any(StaffRole.SHIFT_MANAGER.value not in roles for roles in role_sets):
                    unenforced_owner_only.append((method, path))
            elif not all(StaffRole.SHIFT_MANAGER.value in roles for roles in role_sets):
                wrongly_narrowed.append((method, path))
    assert not wrongly_narrowed, (
        f"routes lock shift_manager out but are not in OWNER_ONLY: {sorted(wrongly_narrowed)}"
    )
    assert not unenforced_owner_only, (
        f"OWNER_ONLY routes with no gate excluding shift_manager: {sorted(unenforced_owner_only)}"
    )


# ⚠ F57's Risk 1 names this test `test_the_floor_roles_reach_exactly_the_floor_routes`.
# F41 renamed it — the reach is no longer the same for all three — WITHOUT
# relaxing anything: read `test_each_non_elevated_role_reaches_exactly_its_own_routes`
# below and the NON_ELEVATED_REACH table above. This comment exists so a grep for
# the old name lands here rather than on nothing, which would read as a deletion.
def test_each_non_elevated_role_reaches_exactly_its_own_routes() -> None:
    """⚠ THE TEST THE FLOOR ROUTER'S AND THE ATELIER ROUTER'S SAFETY RESTS ON
    (F57 spec Risk 1, F41 spec D10 / plan C1).

    The floor router's gate is `require_role(*StaffRole)` — every role the
    product has, spelled from the enum so a sixth is admitted by default. That is
    safe ONLY because this test pins the non-elevated roles OUT of every route
    their own table row does not name. Both halves ship together or neither
    should. The atelier router is the converse case: it names THREE LITERALS
    precisely so a sixth role is refused there by default, and this test is what
    proves the literals are the ones intended.

    IT MUST NEVER BE RELAXED TO A SUBSET CHECK, and no row of NON_ELEVATED_REACH
    may gain a route without the reviewer asking why. F36 and F58 will both
    extend the floor router; F42 will extend the atelier one. Each new row is a
    deliberate, reviewed act.

    ⚠ WHAT F41 CHANGED AND WHAT IT KEPT, stated because the point of the
    restructure is that it gives nothing up. It was `admits_floor == FLOOR_OPEN`
    over one frozen `FLOOR_ROLES` set, plus a `partial` list asserting that no
    route admits only SOME of the three. That second assertion's model is that
    the three move as a BLOCK, and F41 ends that: the atelier admits `seamstress`
    alone. So `partial` is DELETED rather than adapted — its intent, "admits only
    some of them", is now expressible only as a row naming a route the table does
    not, which IS the per-role equality. Three set equalities in place of one
    equality and one block assumption is strictly stronger, not weaker: it still
    catches a route that quietly lost its gate (an ungated route's `effective` is
    empty, so it drops out of every row), still catches a future router that
    copy-pastes a wide gate, and now also catches one of the three being admitted
    somewhere the other two are not.

    ⚠ CLASSIFY ON THE INTERSECTION, NEVER `any(...)` OVER THE GATES. `RoleGate`
    composes by intersection (`auth/dependencies.py:44-45`) and `_gate_role_sets`
    yields EVERY gate in the tree, router-level and per-route both — which is why
    the shipped matrix test above uses `all(...)`. F41's own
    `POST /manage/atelier/tickets/{ticket_id}/delete` is exactly the shape that
    breaks under `any`: the router admits the seamstress and the per-route gate
    does not, so `any` would put it in her reach and red-fail a CORRECT route. A
    reviewer facing that red on a test declared untouchable is most likely to
    "fix" it by relaxing the assertion, which is precisely the outcome Risk 1
    exists to prevent.
    """
    app = create_app(resolver=_null_resolver)
    reach: dict[str, set[tuple[str, str]]] = {role: set() for role in NON_ELEVATED_REACH}
    seen: set[tuple[str, str]] = set()

    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or not path.startswith("/manage"):
            continue
        role_sets = list(_gate_role_sets(dependant))
        # An UNGATED route's effective set is empty and therefore admits nobody.
        # That is what makes the equalities catch a route which quietly lost its
        # gate: it drops out of every row and the equality fails.
        effective: frozenset[str] = frozenset.intersection(*role_sets) if role_sets else frozenset()
        for method in getattr(route, "methods", None) or ():
            seen.add((method, path))
            for role in NON_ELEVATED_REACH:
                if role in effective:
                    reach[role].add((method, path))

    assert seen, "no /manage route was discovered — the walker is broken"

    # 1. Per role, an EXACT set equality against its table row. Nothing else in
    #    the product admits that role — including a future router that
    #    copy-pastes require_role(*StaffRole) — and no route on its row lost its
    #    gate.
    for role, expected in NON_ELEVATED_REACH.items():
        assert reach[role] == expected, (
            f"{role} reaches the wrong set of routes: "
            f"unexpected={sorted(reach[role] - expected)} "
            f"missing={sorted(expected - reach[role])}"
        )

    # 2. The anti-vacuity half (the `seen >= UNGATED_ALLOWLIST` shape above),
    #    WIDENED to the full union INCLUDING delete: delete does exist and the
    #    owner reaches it, and the point of this half is that no row of either
    #    table names a path the route table has lost.
    #
    #    ⚠ WHAT THE WIDENING ACTUALLY CATCHES, verified by mutation rather than
    #    assumed. Every route in a role's reach row is already caught by that
    #    role's equality above — deleting it makes `reach[role]` one element
    #    short. The two ATELIER_ELEVATED routes are the declared routes in
    #    NOBODY's row, so they are invisible to all three equalities: narrow
    #    `declared` back to FLOOR_OPEN, delete /delete or F42's /capacity from
    #    the router, and this test stays GREEN. That is the vacuity this line
    #    exists to prevent, and it is the same reason both had to be named as
    #    constants at all.
    #    F39's five tightened routes join ATELIER_ELEVATED as routes in NOBODY's
    #    reach row — invisible to all three equalities, so they must be named
    #    here or deleting one from the router keeps this test GREEN.
    declared = FLOOR_OPEN | ATELIER_OPEN | SHIFTS_OPEN | SHIFTS_ELEVATED
    missing = declared - seen
    assert not missing, f"the tables name routes that no longer exist: {sorted(missing)}"


def test_every_elevated_shifts_route_is_tightened_in_the_route_table() -> None:
    """F39's structural half, `test_the_capacity_route_is_tightened_in_the_route_table`'s
    idiom and for its stated reason: a route in nobody's reach row is invisible to
    all three per-role equalities, and the anti-vacuity half only notices it
    disappearing entirely. This asserts the per-route gate is THERE and narrows to
    exactly {owner, shift_manager}.

    ⚠ NONE of them is in `OWNER_ONLY`, and that is not an omission: both gates on
    each admit the shift manager, so
    `test_route_table_matches_the_permission_matrix`'s `all(...)` branch passes
    unedited. Putting one there would silently revoke a permission spec D5
    explicitly grants — a shift manager configures the shifts and records on a
    staffer's behalf.

    ⚠ THE `pytest.fail` FALLTHROUGH IS NOT DECORATION. Without it a renamed or
    removed route makes this test pass by never entering the loop.
    """
    app = create_app(resolver=_null_resolver)
    elevated = frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value})
    for method, path in sorted(SHIFTS_ELEVATED):
        for route in _leaf_routes(app):
            if getattr(route, "path", None) != path:
                continue
            if method not in (getattr(route, "methods", None) or ()):
                continue
            role_sets = list(_gate_role_sets(route.dependant))
            assert elevated in role_sets, f"{method} {path} lost its per-route tightening"
            assert frozenset.intersection(*role_sets) == elevated, (
                f"{method} {path} admits {sorted(frozenset.intersection(*role_sets))}"
            )
            break
        else:
            pytest.fail(f"{method} {path} not found in the route table")


def test_the_weekly_availability_write_stays_open_to_every_role() -> None:
    """⚠ THE MIRROR IMAGE, asserted POSITIVELY —
    `test_marketing_withdraw_is_not_owner_only_in_the_route_table`'s idiom.

    `PUT /manage/shifts/week/availability` carries the CLAIM's target-dependent
    rule verbatim: herself, or elevated on anyone. No `RoleGate` can express it,
    so the route is open and the 403 comes from `ShiftsService._authorize`. A
    default-deny walker cannot tell a deliberate omission from a forgotten one, so
    tightening this route to the two elevated roles would pass every other test in
    this file while silently taking her own week away from three of the five roles.
    """
    app = create_app(resolver=_null_resolver)
    method, path = SHIFTS_WEEK_WRITE
    for route in _leaf_routes(app):
        if getattr(route, "path", None) != path:
            continue
        if method not in (getattr(route, "methods", None) or ()):
            continue
        effective = frozenset.intersection(*_gate_role_sets(route.dependant))
        assert effective == {role.value for role in StaffRole}, (
            f"{method} {path} admits only {sorted(effective)}"
        )
        return
    pytest.fail(f"{method} {path} not found in the route table")


def test_the_capacity_route_is_tightened_in_the_route_table() -> None:
    """The structural half of F42's per-route gate, `test_atelier_api`'s
    end-to-end seamstress-403 being the other.

    It asserts the gate is THERE and narrows to exactly {owner, shift_manager} —
    the per-role equalities above cannot, because a route in nobody's reach row
    is invisible to all three of them, and the anti-vacuity half only notices the
    route disappearing entirely.

    ⚠ NOT in OWNER_ONLY, and that is not an omission: both gates on this route
    admit shift_manager, so `test_route_table_matches_the_permission_matrix`'s
    `all(...)` branch passes unedited.
    """
    app = create_app(resolver=_null_resolver)
    method, path = ATELIER_CAPACITY
    for route in _leaf_routes(app):
        if getattr(route, "path", None) != path:
            continue
        if method not in (getattr(route, "methods", None) or ()):
            continue
        role_sets = list(_gate_role_sets(route.dependant))
        assert frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}) in role_sets, (
            f"{method} {path} lost its per-route tightening"
        )
        effective = frozenset.intersection(*role_sets)
        assert effective == frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}), (
            f"{method} {path} admits {sorted(effective)}"
        )
        return
    pytest.fail(f"{method} {path} not found in the route table")


def test_marketing_withdraw_is_not_owner_only_in_the_route_table() -> None:
    """⚠ GATE 1 Q4, ASSERTED POSITIVELY — the mirror image of
    `test_the_capacity_route_is_tightened_in_the_route_table` above, and written
    in its idiom for the reason that test's own docstring gives.

    `test_route_table_matches_the_permission_matrix` is default-deny FOR THE
    WRONG DIRECTION here. A route that admits the shift manager and is not in
    OWNER_ONLY passes its `all(...)` branch silently — and so does a route that a
    later author adds to OWNER_ONLY *and* gives an owner-only gate: both branches
    pass cleanly while a permission the user explicitly granted is revoked. Only
    a named test that asserts the ABSENCE catches that, because a default-deny
    walker cannot tell a deliberate omission from a forgotten one.

    ⚠ NOT in OWNER_ONLY, and that is not an omission: withdrawing a marketing
    consent destroys nothing, it is the lesser action short of erasure (D15), and
    routing it through the owner would mean telling a woman exercising a §30A
    right on the telephone to ring back tomorrow. Its three siblings stay
    owner-only — two assemble or destroy a whole person, the third publishes the
    boutique's legal notice.

    ⚠ THE `pytest.fail` FALLTHROUGH IS NOT DECORATION. Without it, a renamed or
    removed route makes this test pass by never entering the loop, which is
    exactly the vacuity the precedent above was written to avoid.
    """
    app = create_app(resolver=_null_resolver)
    method, path = PRIVACY_WITHDRAW
    for route in _leaf_routes(app):
        if getattr(route, "path", None) != path:
            continue
        if method not in (getattr(route, "methods", None) or ()):
            continue
        role_sets = list(_gate_role_sets(route.dependant))
        assert frozenset({StaffRole.OWNER.value}) not in role_sets, (
            f"{method} {path} gained an owner-only tightening — Gate 1 Q4 says the "
            "shift manager keeps this one"
        )
        effective = frozenset.intersection(*role_sets)
        assert effective == frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}), (
            f"{method} {path} admits {sorted(effective)}"
        )
        return
    pytest.fail(f"{method} {path} not found in the route table")


def test_terms_publishing_is_owner_only_in_the_route_table() -> None:
    app = create_app(resolver=_null_resolver)
    for route in _leaf_routes(app):
        if getattr(route, "path", None) != "/manage/terms":
            continue
        if "POST" not in (getattr(route, "methods", None) or ()):
            continue
        role_sets = list(_gate_role_sets(route.dependant))
        assert frozenset({StaffRole.OWNER.value}) in role_sets, (
            "POST /manage/terms lost its owner-only tightening"
        )
        return
    pytest.fail("POST /manage/terms not found in the route table")


# --- RoleGate unit matrix ---


def _staff(role: str) -> StaffContext:
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="staff@bella.example",
        display_name="Staff",
        role=role,
    )


async def test_gate_admits_listed_roles() -> None:
    gate = require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)
    for role in ("owner", "shift_manager"):
        staff = _staff(role)
        assert await gate(staff) is staff


async def test_the_all_roles_gate_admits_every_role() -> None:
    """F57's floor router spells its gate `require_role(*StaffRole)` and nothing
    else in the codebase does.

    ⚠ A SECOND CASE, not three roles added to the one above. That test builds
    `require_role(OWNER, SHIFT_MANAGER)`, so adding 'reception' to its loop would
    assert that a TWO-ROLE gate admits a floor role — false, and dangerous in the
    direction that matters. The shipped assertion is untouched (plan C1).
    """
    gate = require_role(*StaffRole)
    for role in StaffRole:
        staff = _staff(role.value)
        assert await gate(staff) is staff


async def test_the_three_role_gate_admits_exactly_the_atelier_roles() -> None:
    """F41's atelier router spells its gate with THREE LITERALS and nothing else
    in the codebase does.

    ⚠ A SECOND CASE, not three roles added to `test_gate_admits_listed_roles`.
    That test builds `require_role(OWNER, SHIFT_MANAGER)`, so adding 'seamstress'
    to its loop would assert that a TWO-ROLE gate admits her — false, and
    dangerous in the direction that matters. The shipped assertion is untouched
    (F57's own note on the `*StaffRole` case directly above, verbatim reasoning).

    The refusal half is the load-bearing one: literals rather than `*StaffRole`
    is what makes a receptionist — and a sixth role added later — refused BY
    DEFAULT.
    """
    gate = require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER, StaffRole.SEAMSTRESS)
    for role in ("owner", "shift_manager", "seamstress"):
        staff = _staff(role)
        assert await gate(staff) is staff
    with pytest.raises(NotAuthorizedError):
        await gate(_staff(StaffRole.RECEPTION.value))


async def test_owner_only_gate_refuses_shift_manager() -> None:
    with pytest.raises(NotAuthorizedError):
        await require_role(StaffRole.OWNER)(_staff("shift_manager"))


async def test_unknown_role_fails_closed_on_every_gate_shape() -> None:
    # A role the enum does not know (a future migration slipped in early, a
    # hand-edited row) must be refused, not admitted by accident.
    gates = (
        require_role(StaffRole.OWNER),
        require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER),
    )
    for gate in gates:
        with pytest.raises(NotAuthorizedError):
            await gate(_staff(UNKNOWN_ROLE))


# --- HTTP matrix: the wiring, end to end over the boutique ROUTES table ---


class CountingAuthService(FakeAuthService):
    def __init__(self, role: str) -> None:
        super().__init__()
        self.staff = StaffContext(
            id=self.staff.id,
            tenant_id=self.staff.tenant_id,
            email=self.staff.email,
            display_name=self.staff.display_name,
            role=role,
        )
        self.resolve_calls = 0
        self.logout_calls = 0

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        self.resolve_calls += 1
        return await super().resolve_session(tenant_id, token)

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        self.logout_calls += 1
        return await super().logout(tenant_id, token)


def _client(
    fake: FakeBoutiqueService,
    role: str,
    *,
    authed: bool = True,
    catalog: FakeCatalogService | None = None,
    floor: FakeFloorService | None = None,
    atelier: FakeAtelierService | None = None,
    privacy: FakePrivacyService | None = None,
) -> tuple[TestClient, CountingAuthService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = CountingAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.state.boutique_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    if catalog is not None:
        # Wired ONLY when a test needs the catalog surface to answer 2xx. Left
        # unset otherwise on purpose: test_unknown_role_is_403_on_every_gated_route
        # depends on the real (ambient-env) service never being reached, so a
        # decoy gate that carries allowed_roles without raising blows that test up
        # instead of quietly passing.
        app.state.catalog_service = catalog
        app.dependency_overrides[get_media_storage] = lambda: InMemoryMediaStorage()
    if floor is not None:
        # Wired ONLY when a test needs the floor surface to answer 2xx — the
        # catalog asymmetry directly above, and it matters MORE here. The floor
        # router is the one gate in the codebase spelled require_role(*StaffRole),
        # so it is where a decoy gate that carries `allowed_roles` without
        # raising would be most consequential.
        # test_unknown_role_is_403_on_every_gated_route deliberately does NOT
        # pass one: reaching the real (unset) app.state.floor_service blows that
        # test up instead of quietly passing.
        app.state.floor_service = floor
        # F35: the same fake duck-types NotificationsService, so the bell's two
        # routes answer 2xx here for the same reason the other twenty-three do.
        # Deliberately inside this branch: the unknown-role walk must still blow
        # up rather than quietly pass if a decoy gate lets it through.
        app.state.notifications_service = floor
    if atelier is not None:
        # Same asymmetry as the catalog and floor fakes, for the same reason.
        # test_unknown_role_is_403_on_every_gated_route deliberately does NOT
        # pass one: with app.state.atelier_service never set, a gate that carried
        # `allowed_roles` without raising would fall through to an AttributeError
        # and blow that test up rather than quietly passing.
        app.state.atelier_service = atelier
    if privacy is not None:
        # The fourth instance of the same asymmetry, and F20's is the one where it
        # carries the most weight. POST /manage/privacy/marketing-withdraw is the
        # ONE /manage route deliberately left at its router's (owner,
        # shift_manager) gate while its three siblings tighten (Gate 1 Q4), so the
        # shift-manager walk below has to reach it and get a real 200 — which
        # needs this fake. test_unknown_role_is_403_on_every_gated_route
        # deliberately does NOT pass one: with app.state.privacy_service unset, a
        # gate that carried `allowed_roles` without raising falls through to an
        # AttributeError and blows that test up rather than quietly passing.
        app.state.privacy_service = privacy
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client, auth


def test_shift_manager_is_admitted_everywhere_except_terms_publishing() -> None:
    # ALL THREE route tables, so this is symmetric with the unknown-role walk
    # below: the spec's matrix grants the shift manager the catalog surface, and
    # without the catalog half an accidental owner-only catalog router would only
    # be caught structurally.
    #
    # GATEWAY_ROUTES is here for the opposite reason — all four are in
    # OWNER_ONLY, so this walk is what gives them a real end-to-end 403. Adding
    # the OWNER_ONLY rows alone would silence the structural test while leaving
    # the HTTP wiring unproven, which is exactly the gap this import closes. No
    # gateway fake is wired, deliberately: the gate raises during dependency
    # solving, so reaching the real (unconfigured) service would blow this up
    # rather than quietly pass.
    #
    # FLOOR_ROUTES joins for a third reason again: the floor gate admits all five
    # roles, so a shift manager must reach every one of them. A floor fake IS
    # wired here (unlike the unknown-role walk below) because these three must
    # answer 2xx to prove admission rather than merely "not 403".
    #
    # PRIVACY_ROUTES joins for a FOURTH reason, and it is the sharpest: three of
    # the five are in OWNER_ONLY and get their end-to-end 403 here, while
    # marketing-withdraw is the one /manage route in the product that its own
    # router admits and its siblings refuse. A privacy fake IS wired, because
    # that route must answer a real 200 rather than merely "not 403" — the
    # positive half of Gate 1 Q4.
    fake = FakeBoutiqueService()
    client, _ = _client(
        fake,
        "shift_manager",
        catalog=FakeCatalogService(),
        floor=FakeFloorService(),
        atelier=FakeAtelierService(),
        privacy=FakePrivacyService(),
    )
    with client:
        for method, path, body in [
            *ROUTES,
            *CATALOG_ROUTES,
            *GATEWAY_ROUTES,
            *FLOOR_ROUTES,
            *ATELIER_ROUTES,
            *PRIVACY_ROUTES,
        ]:
            resp = client.request(method, path, json=body)
            if (method, path) in OWNER_ONLY:
                assert resp.status_code == 403, (method, path, resp.text)
                # The whole body, so every route answers the SAME refusal. Note
                # what this cannot do: both sides are the imported constant, so
                # renaming the code or leaking role names into the message would
                # move them together and pass. The literals are pinned once, in
                # test_the_not_authorized_contract_is_pinned_by_literal.
                assert resp.json() == NOT_AUTHORIZED_BODY
            else:
                assert resp.status_code < 400, (method, path, resp.text)


def test_owner_still_publishes_terms() -> None:
    fake = FakeBoutiqueService()
    client, _ = _client(fake, "owner")
    with client:
        resp = client.post("/manage/terms", json=TERMS_BODY)
        assert resp.status_code == 200, resp.text


def test_unknown_role_is_403_on_every_gated_route() -> None:
    # Catalog routes ride along with only the boutique fake in place: the gate
    # raises during dependency solving, BEFORE any service dependency resolves,
    # so a 403 here proves the catalog gate's __call__ actually enforces — a
    # decoy gate that carries allowed_roles but never raises would fall through
    # to the real (unconfigured) CatalogService and blow the test up.
    #
    # ⚠ FLOOR_ROUTES ride along with NO floor fake, and that is the point. The
    # floor router's gate is require_role(*StaffRole) — the widest gate in the
    # codebase — so it is precisely where "the gate carries allowed_roles" could
    # be true while "the gate raises" is false. With app.state.floor_service
    # never set, a gate that failed to enforce would fall through to an
    # AttributeError and blow this test up rather than quietly passing.
    #
    # ⚠ PRIVACY_ROUTES ride along with NO privacy fake, for the same reason, and
    # F20 is where the shape is easiest to get wrong: four of its five routes
    # carry a gate that would have to raise, and one of them
    # (marketing-withdraw) has NO per-route gate at all, so it depends entirely
    # on the router-level one enforcing. With app.state.privacy_service never
    # set, a router gate that failed to enforce falls through to an
    # AttributeError and blows this test up rather than quietly passing.
    fake = FakeBoutiqueService()
    client, _ = _client(fake, UNKNOWN_ROLE)
    with client:
        for method, path, body in [
            *ROUTES,
            *CATALOG_ROUTES,
            *GATEWAY_ROUTES,
            *FLOOR_ROUTES,
            *ATELIER_ROUTES,
            *PRIVACY_ROUTES,
        ]:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, (method, path, resp.text)
            assert resp.json() == NOT_AUTHORIZED_BODY


def test_the_not_authorized_contract_is_pinned_by_literal() -> None:
    """The one test that reads the LITERALS. Every other 403 assertion on this
    branch compares resp.json() against NOT_AUTHORIZED_BODY imported from
    app.main, so both sides move together: renaming the wire code, or leaking
    role names into the message, passes all of them. This is what actually holds
    the contract — and what makes F15's rebase fail loudly if its role-naming
    variant of the same-named constant wins the merge.

    The role-name scan iterates StaffRole rather than listing today's two, so a
    role added later is covered without touching this test. The reason the body
    must stay generic is that naming the required role tells a prober which
    roles exist."""
    fake = FakeBoutiqueService()
    client, _ = _client(fake, StaffRole.SHIFT_MANAGER.value)
    with client:
        resp = client.post("/manage/terms", json=TERMS_BODY)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"
    assert resp.json()["error"]["message"] == "This action is not available for your account."
    for role in StaffRole:
        assert role.value not in resp.text, f"the 403 body names the role {role.value}"


def test_auth_me_stays_reachable_for_shift_manager() -> None:
    fake = FakeBoutiqueService()
    client, _ = _client(fake, "shift_manager")
    with client:
        resp = client.get("/manage/auth/me")
        assert resp.status_code == 200
        assert resp.json()["role"] == "shift_manager"


def test_gate_does_not_resolve_the_session_twice() -> None:
    # The router gate and the route's own Staff dependency both depend on
    # get_current_staff; FastAPI's per-request dependency cache must collapse
    # them to ONE resolve_session call — the spec's recorded risk.
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "shift_manager")
    with client:
        resp = client.get("/manage/settings")
        assert resp.status_code == 200
    assert auth.resolve_calls == 1


def test_two_gates_on_one_route_still_resolve_the_session_once() -> None:
    """POST /manage/terms carries BOTH the router gate and its own owner-only
    tightening. The test above uses a ONE-gate route, so it cannot see a cache
    miss between two separate RoleGate instances — this one can. Must run as
    owner: a 403 would short-circuit before the second gate ever resolves."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "owner")
    with client:
        assert client.post("/manage/terms", json=TERMS_BODY).status_code == 200
    assert auth.resolve_calls == 1


# --- the ungated allowlist, pinned ---


def test_logout_is_reachable_with_no_session_at_all() -> None:
    """Logout carries no auth dependency: an anonymous POST gets 200, nothing is
    resolved, no revoke is attempted, and the cookie is cleared anyway. This is
    the behaviour UNGATED_ALLOWLIST's comment describes."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "owner", authed=False)
    with client:
        resp = client.post("/manage/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert auth.resolve_calls == 0
    assert auth.logout_calls == 0
    assert "boutique_session=" in resp.headers["set-cookie"]


def test_logout_revokes_the_session_for_any_role() -> None:
    """The inverse of every gated route: logout admits owner, shift_manager AND a
    role the enum does not know. A RoleGate added here would 403 exactly the
    caller who most needs to get rid of her cookie.

    logout_calls is the load-bearing assertion, not the 200: the route answers
    200 whether or not it revoked anything, so status alone would still pass if
    the revoke were skipped — which is a live risk, because the route reads the
    cookie by hardcoded literal while everything else reads SESSION_COOKIE. A
    rename of that constant leaves a stolen token valid until TTL with the user
    told she logged out."""
    for role in (StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value, UNKNOWN_ROLE):
        fake = FakeBoutiqueService()
        client, auth = _client(fake, role)
        with client:
            assert client.post("/manage/auth/logout").status_code == 200, role
        assert auth.logout_calls == 1, role


def test_me_echoes_an_out_of_enum_role_verbatim() -> None:
    """Recorded honestly, both halves: the serializer applies NO allowlist, so
    StaffContext.role reaches the browser exactly as staff_users.role held it.
    What makes that safe is the DATABASE, not this code path — since 0011 no such
    row can exist, and test_migrations.py's app-role UPDATE probe is what keeps
    that true. If a role filter is ever wanted on the wire, this is the test that
    must change."""
    fake = FakeBoutiqueService()
    client, _ = _client(fake, UNKNOWN_ROLE)
    with client:
        resp = client.get("/manage/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == UNKNOWN_ROLE


# --- precedence and the anonymous surface ---


def test_a_forged_origin_beats_the_role_gate_on_the_same_route() -> None:
    """Two different 403s can answer POST /manage/terms. CsrfOriginMiddleware is
    added after the tenant middleware, so it runs BEFORE routing and a forged
    Origin can never surface NOT_AUTHORIZED. resolve_calls is what makes this a
    precedence test rather than two status-code tests: the forged request never
    reached dependency solving at all."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "shift_manager")
    with client:
        forged = client.post(
            "/manage/terms", json=TERMS_BODY, headers={"origin": "http://evil.localtest.me"}
        )
        honest = client.post("/manage/terms", json=TERMS_BODY)
    assert forged.status_code == 403
    assert forged.json() == CSRF_ORIGIN_MISMATCH_BODY
    assert honest.status_code == 403
    assert honest.json() == NOT_AUTHORIZED_BODY
    assert auth.resolve_calls == 1
    assert fake.calls == []


def test_no_route_outside_manage_carries_a_role_gate() -> None:
    """The inverse of test_every_manage_route_is_role_gated. /storefront* and
    /health are anonymous by contract; a RoleGate copy-pasted onto one of them
    would refuse the open internet — a dead public page rather than a security
    hole, and the kind of failure no gating test would otherwise notice."""
    app = create_app(resolver=_null_resolver)
    checked = 0
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or path.startswith("/manage"):
            continue
        checked += 1
        assert not list(_gate_role_sets(dependant)), f"anonymous route is role-gated: {path}"
    assert checked, "no non-/manage route was discovered — walker is broken"


def test_head_and_options_on_a_gated_route_are_405_before_the_gate() -> None:
    """A framework CHARACTERIZATION test, not a gating test — it cannot fail for
    any gate-related reason, and it is here to record why no gate is needed on
    these two verbs.

    In the locked fastapi 0.139.2, APIRoute.__init__ never calls
    super().__init__(): it calls _populate_api_route_state, which sets
    route.methods = {m.upper() for m in methods} and never reaches Starlette's
    `if "GET" in self.methods: self.methods.add("HEAD")`. So a GET route carries
    methods == {"GET"} exactly, matching returns PARTIAL, and 405 is answered
    before any dependency — gate included — is solved. OPTIONS 405s for the
    simpler reason that no CORS middleware is installed to handle it.

    Backstop, stated precisely because it is only partial: if a FastAPI bump
    restored the HEAD augmentation, GET /manage/auth/me would gain HEAD, which is
    absent from UNGATED_ALLOWLIST, so test_every_manage_route_is_role_gated would
    go red. Nothing catches a new OPTIONS handler that way — a CORS middleware
    added later would flip this test's second assertion instead, which is the
    review such a change deserves."""
    fake = FakeBoutiqueService()
    client, auth = _client(fake, "shift_manager")
    with client:
        assert client.request("HEAD", "/manage/settings").status_code == 405
        assert client.request("OPTIONS", "/manage/settings").status_code == 405
    assert auth.resolve_calls == 0


# --- F25's console: the same default-deny walk, for the other population -------


def test_every_platform_route_but_the_four_public_ones_requires_an_operator() -> None:
    """The `/manage` RoleGate walker's analogue for the platform console, and it
    exists for the identical reason: a console route added later WITHOUT
    `Depends(get_current_operator)` must be a red build, not a convention nobody
    re-read.

    STAFF ROLES ARE MEANINGLESS HERE — an operator is not a staffer of anything,
    which is why `test_no_route_outside_manage_carries_a_role_gate` above stays
    green with seven new routes in the table. The console's gate is a different
    dependency guarding a different population against a different table (spec
    D3), and this is that gate's walk.

    FOUR routes are deliberately open, and each must be. ⚠ THIS TEST'S WHOLE JOB
    IS TO MAKE A NEW ANONYMOUS ROUTE ON THE PLATFORM'S HOST A DELIBERATE ACT, so
    the count is in the name: renaming it is the cost of opening a fifth, and the
    rename is what a reviewer sees in the diff.
    """
    open_by_design = {
        # Login has nobody to authenticate yet.
        ("POST", "/platform/auth/login"),
        # Logout must answer the same 200 with or without a live cookie, or it
        # becomes an oracle for "was that token live".
        ("POST", "/platform/auth/logout"),
        # F26's redeemer holds a 256-bit invite code and NO account — the account
        # is what redemption creates. Gating this on an operator session would
        # mean the operator typing the owner's password again, which is the exact
        # gap F26 exists to close (spec Problem). The controls that replace a
        # session are: the code itself, single-use by an atomic conditional
        # UPDATE, an expiry, a failures-only limiter on its own instance, and the
        # host fence that keeps both off every boutique's subdomain.
        ("POST", "/platform/join/invite"),
        # The preview read, on the same footing and the same budget. It discloses
        # a boutique name to a caller holding the secret for that one row, which
        # is what lets an owner see what she is claiming BEFORE she spends it.
        ("POST", "/platform/join/redeem"),
    }
    app = create_app(resolver=_null_resolver)
    walked: set[tuple[str, str]] = set()
    ungated: set[tuple[str, str]] = set()
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        dependant = getattr(route, "dependant", None)
        if path is None or dependant is None or not path.startswith("/platform"):
            continue
        gated = any(_operator_gates(dependant))
        for method in getattr(route, "methods", None) or ():
            if method in ("HEAD", "OPTIONS"):
                continue
            walked.add((method, path))
            if not gated:
                ungated.add((method, path))

    assert walked, "no /platform route was discovered — the walker is broken"
    assert ungated == open_by_design, (
        "console routes with no operator gate: "
        f"{sorted(ungated - open_by_design)}; and routes listed as open by design "
        f"that are now gated (prune them): {sorted(open_by_design - ungated)}"
    )
