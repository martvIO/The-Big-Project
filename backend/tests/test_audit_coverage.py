"""F21 B4 / row R38: one walker over the LIVE route table, so the NEXT unaudited
mutating route is a test failure rather than a silence nobody notices.

Row 38's text is "administrative actions are audited". Before F21 that was true
of most of the console and quietly false of `app/catalog/` — the one owner-facing
mutation module with zero `AuditLogRepository` usage, and the module whose writes
are the ones customers actually see. D6's resolution is not a longer hand-list:
it is this walker plus an explicit, reasoned exemption set. Every mutating
`/manage` route either reaches an audit write or appears in
`UNAUDITED_BY_DECISION` with a one-line reason naming where that decision was
recorded in the shipped code.

HOW "REACHES AN AUDIT WRITE" IS DECIDED. Statically, from source, with no
database and no HTTP: for each mutating route, every class-annotated parameter of
the endpoint (FastAPI's `Annotated[XService, Depends(...)]` idiom) is paired with
the method names the endpoint's own source calls on it, and that method's source
— plus, transitively, the `self.<name>(...)` methods it delegates to — is
searched for `_audit.record(`. That is why `BoutiqueSettingsService.update_settings`
resolves as audited through `_record_settings_audit`, one hop down (that helper
was `_record_atelier_settings` until F27 D6 gave it a second action to serve).

WHAT IT PROVES, AND WHAT IT DOES NOT. It proves a *call exists on the path*. It
does not prove a row lands, that the row carries the right action, or that the
row rides the mutation's transaction — `test_catalog_audit_db.py` drives real
Postgres for that, one case per mutation plus the no-op. Verified by mutation:
deleting the `_audit.record(...)` call from `CatalogService.restore_dress` reds
this module (restore falls out of `audited` and is not exempt) AND reds
`test_catalog_audit_db::test_restore_writes_one_row`. Neither is redundant: this
one catches a route that was never wired, the db one catches a row that never
commits.

⚠ THREE PLAN CORRECTIONS, all found by running the walker rather than by reading.
The plan (§5 Task 7) predicts the exemption set is "boutique's profile/toggles/
appointment-types/availability/terms-creation and queue's check-in". Against the
live route table:

1. **`queue`'s check-in is not a `/manage` route.** `POST /checkin` is declared on
   `app/queue/router.py:86` under `prefix="/storefront"` — it is the public,
   unauthenticated customer surface, and no `/manage`-scoped walker can ever see
   it. The recorded decision the plan cites (`queue/manage_router.py:29`) is about
   `GET /manage/checkin-qr`, which is a READ and therefore out of scope for a
   walker over mutating routes. `queue` contributes **zero** exemptions, and that
   is not the plan being sloppy — it is the plan reasoning from the spec's prose
   instead of from the route table, which is the whole reason this file walks one.
2. **`floor` has four unaudited mutating routes** the plan did not predict, every
   one of them carrying its own recorded "no audit row" decision in a docstring
   (D13's rule: the ROW is the record). They are exempt with those citations.
3. **`privacy`'s `PUT /manage/privacy` is unaudited and had NO recorded decision.**
   It is the one genuinely invisible gap this walker turned up. F21 does not close
   it — D6 scopes F21's new rows to `catalog` and `list_tenants`, and widening that
   inside a hardening feature is the move D6 exists to refuse — so it is exempt
   with the reason stating plainly that the silence is now a written decision and
   naming who owns closing it.

`PUT /manage/settings` is a fourth shape and gets its own set. It resolves as
audited, truthfully — but not for every key. `atelier` writes its row (F42) and
`toggles` writes one since F27 D6; `profile` alone stays unaudited by F42's
recorded decision (`boutique/service.py:163-165`), and a per-route walker
structurally cannot see a per-key gap. Dropping the fact would lose the exact
item D6's opening sentence names, so it is asserted as a subset of the audited
set rather than smuggled into the exemption list, where it would be a lie in the
other direction.

⚠ THE GAP NARROWED AT F27 AND THE NOTE WAS EDITED RATHER THAN LEFT LYING —
which is precisely what `test_the_partially_audited_route_is_audited_and_named`'s
docstring says should happen when someone audits one of the two keys it named.
"""

import inspect
import re
import typing
from collections.abc import Iterator
from typing import Any

from citations import assert_citations_open

from app.main import create_app
from app.tenancy.middleware import TenantContext

# ⚠ THE SENTENCE THAT USED TO BE HERE — "`platform_audit_log` is the CLI's
# cross-tenant table and has no HTTP route at all, so it is out of this walk" —
# WAS TRUE UNTIL F25 AND IS NOW FALSE. The platform console put the audited
# provisioning command layer behind HTTP, so /platform's mutating routes reach
# `self._audit.record(...)` through `ProvisioningService` and
# `OperatorAuthService`, and the delegation-following below already detects them.
# They are IN this walk (see `_mutating_audited_routes`) rather than quietly
# outside it, which is the whole point: the console must not keep a thinner book
# than the shell it replaced.
_AUDIT_WRITE = re.compile(r"\b_?audit\.record\(")

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Follows `self.<name>(...)` delegation inside the resolved class. Four hops is
# well past the deepest real chain (endpoint -> service method -> one private
# helper) and bounds a cycle without needing a second guard.
_MAX_DELEGATION_DEPTH = 4


async def _null_resolver(slug: str) -> TenantContext | None:
    """No host resolves. Enough to build the app and read its route table."""
    return None


def _leaf_routes(node: Any) -> Iterator[Any]:
    """FastAPI wraps an included router in `_IncludedRouter` rather than
    flattening it — recurse through `original_router` like test_staff_role_gating,
    or the walker sees only the docs routes and passes vacuously."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def _annotated_class(annotation: Any) -> Any:
    """`Annotated[CatalogService, Depends(get_catalog_service)]` -> CatalogService."""
    if typing.get_origin(annotation) is typing.Annotated:
        return typing.get_args(annotation)[0]
    return annotation


def _method_writes_audit(cls: type, name: str, seen: set[tuple[type, str]], depth: int) -> bool:
    if depth > _MAX_DELEGATION_DEPTH:
        return False
    method = getattr(cls, name, None)
    if method is None or (cls, name) in seen:
        return False
    seen.add((cls, name))
    try:
        source = inspect.getsource(method)
    except (OSError, TypeError):
        return False
    if _AUDIT_WRITE.search(source):
        return True
    return any(
        _method_writes_audit(cls, delegate, seen, depth + 1)
        for delegate in set(re.findall(r"self\.(\w+)\(", source))
    )


def _route_writes_audit(endpoint: Any) -> bool:
    source = inspect.getsource(endpoint)
    hints = typing.get_type_hints(endpoint, include_extras=True)
    for param, annotation in hints.items():
        collaborator = _annotated_class(annotation)
        if not inspect.isclass(collaborator):
            continue
        called = set(re.findall(rf"\b{re.escape(param)}\.(\w+)\(", source))
        if any(_method_writes_audit(collaborator, name, set(), 0) for name in called):
            return True
    return False


# The two prefixes whose mutations must leave a trail: the tenant console writes
# to its own `audit_log`, the platform console to `platform_audit_log`. The
# storefront is deliberately absent — an anonymous bride booking is not an
# operator action, and F13's own rows are the record of it.
_AUDITED_PREFIXES = ("/manage", "/platform")


def _mutating_audited_routes() -> dict[tuple[str, str], Any]:
    app = create_app(resolver=_null_resolver)
    found: dict[tuple[str, str], Any] = {}
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        endpoint = getattr(route, "endpoint", None)
        if path is None or endpoint is None or not path.startswith(_AUDITED_PREFIXES):
            continue
        for method in (getattr(route, "methods", None) or set()) - _READ_METHODS:
            found[(method, path)] = endpoint
    return found


# --- the reviewed decisions ---
#
# Every entry is a route that mutates tenant data and deliberately writes no
# audit row. The reason names where the decision lives in the shipped code, so a
# reviewer can check the reasoning rather than take this file's word for it.
UNAUDITED_BY_DECISION: dict[tuple[str, str], str] = {
    # F25's console logout, and it is the ONE console mutation with no row. The
    # staff twin DOES write LOGOUT into its tenant's audit_log; this one
    # deliberately does not, because spec D4 enumerates the platform book's new
    # actions as login and login-failed only. What that book answers is "who
    # touched the platform, and when did somebody try" — a session ending is
    # neither, and the login row already bounds the window it closes. Recorded
    # here rather than closed, so a later reader who wants OPERATOR_LOGOUT finds
    # the argument instead of a silence (platform/auth_router.py:95-105).
    ("POST", "/platform/auth/logout"): (
        "spec D4 names only OPERATOR_LOGIN and OPERATOR_LOGIN_FAILED for the "
        "platform book; a session ending is bounded by the login row that opened "
        "it (platform/auth_router.py:95-105)"
    ),
    # boutique — F42 audited the key it owned (`atelier`) and refused to widen a
    # pre-existing gap it did not create (`boutique/service.py:163-165`). These
    # six carry that same decision: they are the boutique's own configuration of
    # itself, visible on the screen that changed them, and every row is timed.
    ("POST", "/manage/appointment-types"): (
        "boutique configures its own service menu; the row's created_at is the record "
        "(boutique/service.py:163-165's rule, unwidened by F21 per D6)"
    ),
    ("PATCH", "/manage/appointment-types/{type_id}"): (
        "boutique configures its own service menu; updated_at is the record "
        "(boutique/service.py:163-165's rule, unwidened by F21 per D6)"
    ),
    ("DELETE", "/manage/appointment-types/{type_id}"): (
        "soft delete: deleted_at IS the record, and the type stays readable "
        "(boutique/service.py:163-165's rule, unwidened by F21 per D6)"
    ),
    ("POST", "/manage/availability/exceptions"): (
        "boutique configures its own opening hours; the exception row is the record "
        "(boutique/service.py:163-165's rule, unwidened by F21 per D6)"
    ),
    ("DELETE", "/manage/availability/exceptions/{exception_id}"): (
        "boutique configures its own opening hours; the removed exception is the record "
        "(boutique/service.py:163-165's rule, unwidened by F21 per D6)"
    ),
    ("PUT", "/manage/availability/rules"): (
        "boutique configures its own opening hours; the replaced rule set is the record "
        "(boutique/service.py:163-165's rule, unwidened by F21 per D6)"
    ),
    ("POST", "/manage/terms"): (
        "terms versions are append-only and immutable: the VERSION ROW is the audit "
        "trail — it carries the actor (boutique/router.py:233 passes created_by) and "
        "its own created_at, which is also why the path is throttled rather than "
        "logged twice (boutique/service.py:434-436). Sits under F42's standing rule "
        "for the boutique configuring itself (boutique/service.py:163-165)"
    ),
    # floor — D13's rule, stated in each method's own docstring: where a durable
    # row already answers who/when, a second row in audit_log is noise that would
    # swamp the four floor actions that genuinely need one.
    ("POST", "/manage/floor/assignments/{assignment_id}/dresses"): (
        "the binding ROW is the record (D13, floor/service.py:1166-1167 states it); "
        "a dozen per fitting would swamp the four floor actions that are audited"
    ),
    ("DELETE", "/manage/floor/assignments/{assignment_id}/dresses/{binding_id}"): (
        "soft delete plus removed_by IS the audit record "
        "(floor/service.py:1193-1195 states it, and no FITTING_DRESS_REMOVED action exists)"
    ),
    ("POST", "/manage/floor/rooms"): (
        "non-destructive, visible on the screen that did it, already timed by created_at "
        "(floor/service.py:1218-1219 states it)"
    ),
    ("PATCH", "/manage/floor/rooms/{room_id}"): (
        "room label/order/active are floor furniture, not tenant data about a person; "
        "the room row and its updated_at are the record — D13's rule, stated for this "
        "surface in create_room's own docstring (floor/service.py:1218-1219) and "
        "unchanged by the update path"
    ),
    # privacy — the one gap this walker FOUND rather than confirmed.
    ("PUT", "/manage/privacy"): (
        "FOUND BY THIS WALKER, not previously recorded anywhere: publishing the "
        "boutique's own legal notice writes no audit row. Same class as boutique's "
        "profile/toggles — the tenant editing its own text — and D6 scopes F21's new "
        "rows to catalog + list_tenants, so F21 records the silence rather than "
        "widening its own charter. Owner: F62, alongside the audit READ surface."
    ),
    # F26's invite preview: a POST that READS, so the method-based walk above
    # cannot tell it from a mutation. It is a POST because a `?code=` would put a
    # live boutique-creation credential into every access log and proxy trace on
    # the path — `queue/router.py:14` argues the identical trade for the walk-in
    # ticket. It changes nothing and therefore writes nothing; its REFUSALS still
    # spend the shared limiter, and the redemption it precedes is fully audited.
    ("POST", "/platform/join/invite"): (
        "a POST that is a read: the code travels in the body so it never reaches an "
        "access log, and a read of one's own invite is not a platform event — the "
        "caller already holds the 256-bit secret for that single row, so "
        "TENANTS_LISTED's enumeration argument does not reach it, and a row per read "
        "would let an anonymous caller fill an INSERT-only table nothing prunes "
        "(platform/join_router.py:104)"
    ),
    ("POST", "/manage/floor/notifications/read"): (
        "a person marking her OWN notification read is not an administrative act: it "
        "changes nothing anybody else can see, it is scoped to her own rows by the "
        "statement's own predicate, and read_at IS the record — F35's decision, stated "
        "at the writer (floor/notifications.py:66-69). The four acts that CAUSE these "
        "rows are each audited already, one line beside the insert."
    ),
}

# The one exemption whose decision is recorded HERE and nowhere else, because
# nowhere else had it. See test_the_exemption_list_is_exactly_the_recorded_decisions.
RECORDED_ONLY_HERE: frozenset[tuple[str, str]] = frozenset({("PUT", "/manage/privacy")})

# Audited, but only in part, and the part that is not audited is a recorded
# decision that a per-route walker structurally cannot express.
PARTIALLY_AUDITED_BY_DECISION: dict[tuple[str, str], str] = {
    ("PUT", "/manage/settings"): (
        "the `atelier` key writes ATELIER_SETTINGS_UPDATED (boutique/service.py:182) and "
        "the `toggles` key writes TOGGLES_UPDATED since F27 D6 (boutique/service.py:189); "
        "`profile` alone stays UNAUDITED by F42's recorded decision, which F27 narrowed "
        "rather than widened when it took ownership of the toggles key "
        "(boutique/service.py:163-165)"
    ),
}


def test_every_mutating_manage_route_writes_an_audit_row_or_is_exempt() -> None:
    routes = _mutating_audited_routes()
    audited = {key for key, endpoint in routes.items() if _route_writes_audit(endpoint)}
    unaudited = set(routes) - audited

    # Three anti-vacuity legs. An empty walk, a walk that resolved nothing as
    # audited, or an exemption naming a route that no longer exists would each
    # make the real assertion below pass while proving nothing.
    assert routes, "no mutating audited route was discovered — the walker is broken"
    assert audited, "no route resolved as audited — the source detector is broken"
    assert set(routes) >= set(UNAUDITED_BY_DECISION), (
        "the exemption list names a route that no longer exists — prune it: "
        f"{sorted(set(UNAUDITED_BY_DECISION) - set(routes))}"
    )

    assert unaudited == set(UNAUDITED_BY_DECISION), (
        "a mutating /manage route neither writes an audit row nor is a recorded "
        f"decision: {sorted(unaudited - set(UNAUDITED_BY_DECISION))}; "
        "and these are exempt but now audited (drop them from the list): "
        f"{sorted(set(UNAUDITED_BY_DECISION) - unaudited)}"
    )


def test_the_exemption_list_is_exactly_the_recorded_decisions() -> None:
    """D6's rule: F21 converts an invisible coverage gap into a REVIEWED one. A
    reason that is blank, or that does not say where the decision lives, is the
    gap wearing a list's clothing.

    ⚠ THIS TEST USED TO CHECK ONLY `len(reason) > 40`, which is not the rule this
    module's docstring states, and two entries had drifted past it with a
    rationale but no citation (found by the 2026-08-05 review). It then checked
    the SHAPE of a citation, which `totally/fake.py:999999` satisfies — found by
    the round-2 review. It now enforces what the docstring claims: a
    `file.py:line` a reviewer can OPEN (`citations.py`).

    `PUT /manage/privacy` is the one exemption with nothing to cite, and that is
    the finding rather than a lapse — the walker FOUND it, no decision to that
    effect existed anywhere in the tree, and this file is now where it is
    recorded. It is named rather than waved through, so a citation appearing
    there later means someone recorded the decision properly and this exception
    should go.
    """
    assert set(UNAUDITED_BY_DECISION) >= RECORDED_ONLY_HERE, (
        f"prune the citation exception: {sorted(RECORDED_ONLY_HERE - set(UNAUDITED_BY_DECISION))}"
    )
    # The escape hatch is ONE route, pinned the way `(56, 54)` and
    # `len(UNWALKABLE) == 6` are pinned elsewhere in this feature. Without a
    # count, any future exemption opts out of the citation rule by containing the
    # phrase below — an unbounded hatch inside the test that exists to bound one.
    assert len(RECORDED_ONLY_HERE) == 1, (
        f"RECORDED_ONLY_HERE is now {len(RECORDED_ONLY_HERE)} entries. A second "
        "exemption with nothing to cite is a second silence nobody recorded — close "
        "it or record the decision in the shipped code, do not widen this set."
    )
    for route, reason in UNAUDITED_BY_DECISION.items():
        assert len(reason) > 40, f"{route} carries no real reason"
        if route in RECORDED_ONLY_HERE:
            assert "not previously recorded anywhere" in reason, (
                f"{route} is exempt from the citation rule and must say why in its reason"
            )
            continue
        assert assert_citations_open(reason, route), (
            f"{route}'s reason names no file:line. This module's rule is that an "
            "exemption cites where the decision was recorded in the shipped code — "
            "a rationale a reviewer cannot open is prose, not a record."
        )
    modules = {path.split("/")[2] for _, path in UNAUDITED_BY_DECISION}
    # "auth" joined them in F25 and it is the PLATFORM's auth, not the tenant's —
    # /manage/auth/logout still writes its row. "join" joined in F26 and is the
    # only entry here that is not a mutation at all: the invite preview is a READ
    # posted rather than got, so that the code stays out of every request line.
    # The shape assertion is what makes a new silent module a review rather than
    # a diff nobody read.
    assert modules == {
        "appointment-types",
        "availability",
        "terms",
        "floor",
        "privacy",
        "auth",
        "join",
    }, (
        "the exemption set changed shape — a new module went quiet, or one was closed "
        f"and not removed: {sorted(modules)}"
    )


def test_the_partially_audited_route_is_audited_and_named() -> None:
    """`PUT /manage/settings` must stay on the audited side of the walk while its
    unaudited half stays written down. If someone audits profile/toggles, this
    entry is what tells them to delete the note rather than leave it lying."""
    routes = _mutating_audited_routes()
    for route, reason in PARTIALLY_AUDITED_BY_DECISION.items():
        assert route in routes, f"{route} no longer exists — prune the note"
        assert _route_writes_audit(routes[route]), f"{route} lost its audit write entirely"
        assert "UNAUDITED" in reason, f"{route}'s note must name what is NOT audited"


def test_catalog_is_no_longer_the_module_with_zero_audit_rows() -> None:
    """The R38 finding in one assertion. Before F21 every one of catalog's nine
    mutating routes was unaudited and unrecorded; `grep -n audit
    catalog/service.py` returned nothing at all.

    ELEVEN since F28 added reservation create and delete, and the number is
    asserted rather than dropped: it is the tripwire that makes a NEW catalog
    mutation land as a decision. Both new routes reach `_audit.record` — the
    walker proved that before this count was touched, which is the only order in
    which raising it is honest."""
    routes = _mutating_audited_routes()
    catalog = {key for key in routes if key[1].startswith("/manage/dresses")}
    assert len(catalog) == 11, f"catalog's mutating route count moved: {sorted(catalog)}"
    unaudited = {key for key in catalog if not _route_writes_audit(routes[key])}
    assert not unaudited, f"catalog mutations with no audit row: {sorted(unaudited)}"


# --- F26: the two console READS, and why they differ from each other ----------


def test_the_anonymous_invite_read_writes_no_row_while_the_tenant_list_still_does() -> None:
    """⚠ THREE GET READS UNDER `/platform`, TWO OF WHICH DELIBERATELY WRITE NOTHING.
    The walk above only sees mutations, so without this test the decision would
    live nowhere a reviewer could find it.

    `GET /platform/tenants` writes `TENANTS_LISTED` — F21's D6 made it the single
    audited read in the product because it is a FULL cross-tenant enumeration:
    every boutique's slug, trading name and status in one answer
    (`platform/service.py`'s `list_tenants` docstring).

    `GET /platform/invites` writes nothing, and for a second reason: it lists
    authorisations the operator population issued itself and names no boutique
    that exists (`platform/service.py`'s `list_invites`).

    `GET /platform/auth/me` writes nothing for the third: it reads the caller's
    own session back to her.

    ⚠ **THE INVITE PREVIEW IS NOT IN THIS SET AND MUST NOT BE.** It is a read,
    but it is a `POST /platform/join/invite` so that the code travels in a body
    rather than a request line, which puts it on the MUTATION walk above — its
    "writes nothing" decision therefore lives in `UNAUDITED_BY_DECISION`, and the
    assertion below is what stops it drifting back to a GET without that note
    moving too.
    """
    app = create_app(resolver=_null_resolver)
    reads = {}
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        endpoint = getattr(route, "endpoint", None)
        if path is None or endpoint is None or not path.startswith("/platform"):
            continue
        if "GET" in (getattr(route, "methods", None) or set()):
            reads[path] = endpoint

    assert set(reads) == {
        "/platform/auth/me",
        "/platform/tenants",
        "/platform/invites",
    }, sorted(reads)
    assert _route_writes_audit(reads["/platform/tenants"]), (
        "GET /platform/tenants stopped writing TENANTS_LISTED — F21's D6 row R12 "
        "travelled from the shell to HTTP on the strength of that write"
    )
    assert not _route_writes_audit(reads["/platform/invites"])
    assert not _route_writes_audit(reads["/platform/auth/me"])


def test_the_four_new_mutating_platform_routes_all_reach_the_audit_repository() -> None:
    """F26's three operator routes and its one anonymous mutation, resolved
    through delegation rather than asserted by inspection. The redemption route
    is the one that matters most: it creates a whole boutique from an
    unauthenticated request, and the row naming the operator who authorised it is
    the only accountability the act has."""
    routes = _mutating_audited_routes()
    for key in (
        ("POST", "/platform/invites"),
        ("POST", "/platform/invites/revoke"),
        ("POST", "/platform/join/redeem"),
    ):
        assert key in routes, f"{key} is no longer a mutating /platform route"
        assert _route_writes_audit(routes[key]), f"{key} writes no audit row"
