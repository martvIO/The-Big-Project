"""F21 B3 / row R9: one walker over the LIVE route table, not ninety-five
hand-written endpoint tests.

Row 9's text is "every repository method + API endpoint probed as tenant A
against tenant B's data". Ninety-five hand-written tests would satisfy it on the
day they were written and rot on the next merge. `test_staff_role_gating.py` has
the right shape already — it reads the live route table, so a route added later
is policy-checked with no new test — and this module copies it.

WHAT IT DRIVES. Two real tenants are seeded against real Postgres, as the
non-superuser `boutique_app` role so RLS is genuinely enforced. Tenant B is
populated THROUGH ITS OWN HTTP SURFACE — every seed row is created by the same
production code path a real boutique would use, so no fixture can be more
permissive than the product. Then, authenticated as tenant A's owner and with
`Host` set to tenant A's slug, every walkable route is driven with tenant B's ids
in the path and body. The assertion is **404** — never 200, never a 403 that
leaks existence, never a 500. A 500 is a failure and not an excuse: it means the
route reached code that assumed the row existed.

WHAT IT PROVES, AND WHAT IT DOES NOT. Verified by mutation: delete
`Dress.tenant_id == tenant_id` from `DressesRepository.by_id` and this walker
stays GREEN, because forced RLS carries the tenant scope underneath it. So what
is asserted here is that the HTTP boundary REFUSES — not that the application's
own predicate is what refuses it.

⚠ And the correction the plan's D5 reasoning needs: `test_catalog_isolation.py`
stays green under that same mutation too (re-run and confirmed). Those files run
under RLS as well, so they do not pin the redundant predicate either. **Nothing
in this suite currently fails if the explicit `tenant_id ==` predicates are
removed** — they are defence-in-depth against an RLS misconfiguration, and the
thing that actually guards THAT is `db/session.py`'s boot guard refusing to start
against a superuser or BYPASSRLS role (which row R7 covers, and whose deployment
clause is F62's). Worth knowing before anyone cites this module as proof of the
repository layer: it is not, and neither are the ten isolation files.

THREE CATEGORIES, ALL EXPLICIT. `test_the_walk_and_the_exemptions_are_the_whole
_route_table` asserts that walked | UNWALKABLE | NO_TENANT_OWNED_ID is exactly
the route table, both directions — so a new route is a TEST FAILURE, not a silent
gap, and an exemption naming a route that no longer exists must be pruned rather
than left. The plan asked for two categories; splitting the structural half
(`NO_TENANT_OWNED_ID` — there is no id to substitute) away from the judgement
half (`UNWALKABLE` — there is an id and it cannot be driven generically) is the
one deviation, and it exists so that Risk 4's slope is visible: the list that
could quietly become the interesting half is the small one with a reason on every
line.

⚠ PLAN CORRECTION, and it changes `test_no_module_is_wholly_exempt`. The plan
spells the per-module floor over fourteen modules including `platform` and
`storage`. Neither exposes a single HTTP route — `platform` is the provisioning
CLI and `storage` is the S3 adapter — so a floor of >=1 on them is unsatisfiable
by construction. `auth`, `dashboard` and `payments` DO expose routes but not one
of them carries a tenant-owned id (see `MODULES_WITH_NO_ID_ROUTES` for the
per-module reason). The floor is therefore spelled over the modules that have
id-carrying routes, and it is paired with an assertion that the exempt-module set
is EXACTLY the modules with zero walked routes — so a module cannot drop out of
the floor without someone adding it to a named set with a written reason.
"""

import asyncio
import datetime
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from test_booking_owner_db import (
    # AUTOUSE, imported for its side effect rather than called. `_populate`
    # commits a walk-in booking, and 0025's downgrade re-imposes
    # `terms_accepted_at NOT NULL` deliberately without a pre-clean — one
    # surviving walk-in row reds all eighteen round-trip tests in this suite, in
    # modules that never heard of F50. Its docstring says in as many words that a
    # NEW db module committing a walk-in must import it exactly like this; this
    # is that module.
    _sweep_walk_in_bookings,  # noqa: F401
)

from app.auth.passwords import hash_password
from app.auth.rate_limit import FixedWindowRateLimiter
from app.core.config import Settings
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.main import create_app
from app.storage.memory import InMemoryMediaStorage
from app.tenancy.resolver import RepositoryTenantResolver

pytestmark = pytest.mark.db

PASSWORD = "s3cret-walker-pw"
JPEG_BODY = b"\xff\xd8\xff" + b"\x00" * 1021

# Not tenant-scoped, so nothing to probe: /health is exempt from tenant
# resolution outright (tenancy/middleware.py EXEMPT_PATHS) and the four doc
# routes are FastAPI built-ins that only exist in dev.
NOT_TENANT_SCOPED = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/docs"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/openapi.json"),
        ("GET", "/redoc"),
    }
)


class Kind(StrEnum):
    """One member per tenant-owned entity whose id reaches the wire. Used as a
    placeholder inside `PROBES` bodies and resolved against tenant B's seed."""

    STAFF = "staff"
    DRESS = "dress"
    MEDIA = "media"
    CUSTOMER = "customer"
    BOOKING = "booking"
    APPOINTMENT_TYPE = "appointment_type"
    AVAILABILITY_EXCEPTION = "availability_exception"
    ROOM = "room"
    ASSIGNMENT = "assignment"
    BINDING = "binding"
    QUEUE_TICKET = "queue_ticket"
    ATELIER_TICKET = "atelier_ticket"
    SOS_ALERT = "sos_alert"


# Path-parameter name -> entity kind. An unknown name is a hard failure in
# `_path_kind` rather than a skip: a new path parameter must be classified by a
# human, not silently walked with the wrong fixture.
PATH_PARAM_KIND = {
    "staff_id": Kind.STAFF,
    "staff_user_id": Kind.STAFF,
    "dress_id": Kind.DRESS,
    "media_id": Kind.MEDIA,
    "customer_id": Kind.CUSTOMER,
    "booking_id": Kind.BOOKING,
    "type_id": Kind.APPOINTMENT_TYPE,
    "exception_id": Kind.AVAILABILITY_EXCEPTION,
    "room_id": Kind.ROOM,
    "assignment_id": Kind.ASSIGNMENT,
    "binding_id": Kind.BINDING,
    "alert_id": Kind.SOS_ALERT,
}


def _path_kind(path: str, param: str) -> Kind:
    """⚠ `ticket_id` is the trap. `/manage/floor/queue/{ticket_id}` is a
    `queue_tickets` row and `/manage/atelier/tickets/{ticket_id}` is an
    `alteration_tickets` row — same parameter name, different tables, different
    routers. Feeding the wrong fixture yields a 404 that proves nothing, because
    the id genuinely does not exist in EITHER tenant."""
    if param == "ticket_id":
        if path.startswith("/manage/floor/queue/"):
            return Kind.QUEUE_TICKET
        if path.startswith("/manage/atelier/tickets/"):
            return Kind.ATELIER_TICKET
        raise AssertionError(f"unclassified ticket_id on {path}")
    kind = PATH_PARAM_KIND.get(param)
    if kind is None:
        raise AssertionError(f"unclassified path parameter {param!r} on {path}")
    return kind


# Request bodies for the routes that need one, with `Kind` members standing in
# for tenant B's ids. Every id-bearing field is filled with B's id: the plan's
# rule is that EVERY id in the path, query and body belongs to the other tenant.
# Non-id fields carry the minimum that passes validation — this walk is about the
# tenant check, and a 422 would read as a pass it did not earn.
# Computed, never pinned literals. `reschedule`'s step 0 refuses anything outside
# `now < starts_at <= now + BOOKABLE_HORIZON` (booking/owner.py:805-808) BEFORE it
# loads the booking — so a date chosen for readability rather than for that window
# would 409 on the horizon and the booking_id tenant check would never run. A
# pinned literal also rots into the past and starts masking the same check
# silently, which is exactly the failure this module exists to prevent.
_FUTURE_DATE = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
_FUTURE_INSTANT = (
    datetime.datetime.now(datetime.UTC).replace(microsecond=0) + datetime.timedelta(days=3)
).isoformat()

PROBES: dict[tuple[str, str], dict[str, Any]] = {
    # staff
    ("PATCH", "/manage/staff/{staff_id}"): {"display_name": "Walker"},
    # boutique
    ("PATCH", "/manage/appointment-types/{type_id}"): {
        "name": "Walker fitting",
        "duration_minutes": 60,
        "audience": "all",
        "deposit_required": False,
        "deposit_amount_agorot": None,
        "sort_order": 0,
    },
    # catalog
    ("PATCH", "/manage/dresses/{dress_id}"): {
        "name": "Walker gown",
        "description": None,
        "price_agorot": None,
        "price_visible": True,
        "reserved": False,
        "sort_order": 0,
    },
    ("PUT", "/manage/dresses/{dress_id}/variants"): {
        "variants": [{"size_label": "38", "quantity": 1}]
    },
    ("POST", "/manage/dresses/{dress_id}/media/presign"): {
        "content_type": "image/jpeg",
        "byte_size": len(JPEG_BODY),
    },
    ("PUT", "/manage/dresses/{dress_id}/media/order"): {"media_ids": [Kind.MEDIA]},
    # booking
    ("POST", "/manage/bookings/walk-in"): {
        "customer_id": Kind.CUSTOMER,
        "appointment_type_id": Kind.APPOINTMENT_TYPE,
    },
    ("POST", "/manage/bookings/{booking_id}/reschedule"): {"starts_at": _FUTURE_INSTANT},
    ("POST", "/manage/bookings/{booking_id}/phone"): {"phone": "+972500000111"},
    # customers
    ("PATCH", "/manage/customers/{customer_id}"): {"notes": "walker"},
    # privacy
    ("POST", "/manage/privacy/subject-erase"): {"customer_id": Kind.CUSTOMER},
    ("POST", "/manage/privacy/marketing-withdraw"): {"customer_id": Kind.CUSTOMER},
    # floor
    ("PATCH", "/manage/floor/rooms/{room_id}"): {"label": "Walker room"},
    ("POST", "/manage/floor/rooms/{room_id}/claim"): {
        "staff_user_id": Kind.STAFF,
        "booking_id": Kind.BOOKING,
    },
    ("POST", "/manage/floor/rooms/{room_id}/take-next"): {"staff_user_id": Kind.STAFF},
    ("POST", "/manage/floor/rooms/{room_id}/assign"): {
        "queue_ticket_id": Kind.QUEUE_TICKET,
        "staff_user_id": Kind.STAFF,
    },
    ("POST", "/manage/floor/assignments/{assignment_id}/handover"): {"staff_user_id": Kind.STAFF},
    ("POST", "/manage/floor/assignments/{assignment_id}/dresses"): {"dress_id": Kind.DRESS},
    # The one route whose ONLY tenant-owned ids are optional body fields: with
    # both omitted it raises a legitimate alert for tenant A, so the probe must
    # supply them or this route is untested rather than exempt.
    ("POST", "/manage/floor/sos"): {
        "target_staff_user_id": Kind.STAFF,
        "fitting_room_assignment_id": Kind.ASSIGNMENT,
    },
    # queue
    ("POST", "/manage/floor/queue/{ticket_id}/skip"): {"seen_skip_count": 0},
    ("POST", "/storefront/checkin/position"): {"ticket_id": Kind.QUEUE_TICKET},
    # atelier
    ("POST", "/manage/atelier/tickets"): {
        "customer_name": "Walker",
        "customer_phone": "+972500000222",
        "due_date": _FUTURE_DATE,
        "effort_band": "one_hour",
        "assigned_staff_user_id": Kind.STAFF,
        "dress_id": Kind.DRESS,
    },
    ("POST", "/manage/atelier/tickets/{ticket_id}/update"): {
        "due_date": _FUTURE_DATE,
        "effort_band": "one_hour",
        "dress_id": Kind.DRESS,
        "dress_name": None,
        "dress_size": None,
        "notes": None,
    },
    # `null` — the legal "release the assignee" body — and NOT tenant B's staff
    # id, deliberately. `_validate_assignee` refuses a foreign seamstress with a
    # 400 BEFORE `_load` runs, which would mask the ticket_id check this row
    # exists to make. The body's own cross-tenant refusal is proved twice over by
    # `POST /manage/atelier/tickets` (assigned_staff_user_id, 404) and by the
    # capacity route below, which runs the identical validator.
    ("POST", "/manage/atelier/tickets/{ticket_id}/assign"): {"staff_user_id": None},
    ("POST", "/manage/atelier/tickets/{ticket_id}/stage/advance"): {"stage": "in_progress"},
    # `intake` is refused by a pure argument guard before any session opens
    # (atelier/service.py:366-370); any other stage reaches `_load`.
    ("POST", "/manage/atelier/tickets/{ticket_id}/stage/undo"): {"stage": "in_progress"},
    ("POST", "/manage/atelier/seamstresses/{staff_user_id}/capacity"): {
        "weekly_capacity_hours": 10
    },
}


# The walk's default expectation is 404 on every route. These two answer
# something else and are RIGHT to, each for a reason written out here. This table
# is held to the same standard as UNWALKABLE — an entry with no reason is the
# shape that turns a walker into decoration — and it is additionally fenced by
# `test_no_response_echoes_the_other_tenants_ids`, which applies to every route
# regardless of status: whatever the code, the body may not contain one of tenant
# B's ids.
EXPECTED_STATUS: dict[tuple[str, str], tuple[int, str]] = {
    ("POST", "/manage/atelier/seamstresses/{staff_user_id}/capacity"): (
        400,
        "the path id IS the only id, and `_validate_assignee` resolves it inside "
        "the CALLER's tenant: a foreign seamstress, a deleted one and a random "
        "UUID all answer the same 400, so the refusal carries no existence "
        "oracle. 400 rather than 404 because the id arrives as an argument to be "
        "validated, not as a resource to be fetched.",
    ),
    ("POST", "/manage/floor/sos"): (
        200,
        "F37's REROUTE, and it is the designed behaviour rather than a leak: an "
        "unresolvable target falls back to the shift manager and the alert is "
        "raised for the CALLER's tenant with target_staff_user_id null. Nothing "
        "of tenant B is read, written or echoed — the no-echo test below is what "
        "holds that. Refusing here would mean a staffer in trouble gets an error "
        "instead of a page, which is the wrong way to fail.",
    ),
}


# Has a tenant-owned id and still cannot be driven as a tenant principal. FOUR
# entries, each with its own reason — this is the list Risk 4 says can quietly
# become the interesting half, which is why it is small, commented per line, and
# fenced by the per-module floor below.
UNWALKABLE: dict[tuple[str, str], str] = {
    ("POST", "/storefront/payments/webhook"): (
        "raw bytes verified by HMAC-SHA256 over the exact body; the caller is the "
        "payment gateway, not a tenant principal, and re-serialising the body "
        "breaks every delivery. Isolation is test_payments_isolation.py's."
    ),
    ("POST", "/storefront/bookings"): (
        "requires a single-use, phone-bound verification_token minted only by "
        "POST /storefront/otp/verify; the OTP is never on the wire. The "
        "appointment_type_id/dress_id cross-tenant refusal is "
        "test_booking_isolation.py's."
    ),
    ("POST", "/storefront/booking/lookup"): (
        "the manage token proves POSSESSION, not tenancy — the server stores only "
        "its sha256 and there is no id to substitute. test_manage_token.py owns "
        "this surface."
    ),
    ("POST", "/storefront/booking/confirm-attendance"): (
        "same manage token as lookup; possession, not tenancy. test_manage_token.py."
    ),
    ("POST", "/storefront/booking/cancel"): (
        "same manage token as lookup; possession, not tenancy. test_manage_token.py."
    ),
    ("POST", "/storefront/booking/payment-status"): (
        "keyed on a provider-issued opaque session string on a payments row, not "
        "a UUID we can mint; having one at all means driving a real deposit "
        "against the gateway. test_payments_isolation.py."
    ),
}


# Carries NO tenant-owned id in path, query or body — there is nothing to
# substitute. These are collection, singleton and creation routes whose entire
# answer is scoped by the host-derived tenant, and that scoping is proved
# elsewhere: test_middleware.py (unknown host -> 404 before any handler) and
# test_staff_role_gating_integration.py::
# test_a_session_from_another_tenant_is_401_not_403.
NO_TENANT_OWNED_ID = frozenset(
    {
        ("POST", "/manage/auth/login"),
        ("POST", "/manage/auth/logout"),
        ("GET", "/manage/auth/me"),
        ("GET", "/manage/dashboard"),
        ("GET", "/manage/checkin-qr"),
        ("GET", "/manage/settings"),
        ("PUT", "/manage/settings"),
        ("GET", "/manage/appointment-types"),
        ("POST", "/manage/appointment-types"),
        ("GET", "/manage/availability"),
        ("PUT", "/manage/availability/rules"),
        ("POST", "/manage/availability/exceptions"),
        ("GET", "/manage/terms"),
        ("POST", "/manage/terms"),
        ("GET", "/manage/dresses"),
        ("POST", "/manage/dresses"),
        ("GET", "/manage/bookings"),
        ("GET", "/manage/slots"),
        ("GET", "/manage/staff"),
        ("POST", "/manage/staff"),
        ("GET", "/manage/customers"),
        ("GET", "/manage/privacy"),
        ("PUT", "/manage/privacy"),
        # Keyed on a PHONE, not an id — and the phone is looked up inside the
        # caller's own tenant, so there is no foreign handle to pass.
        ("POST", "/manage/privacy/subject-export"),
        ("GET", "/manage/gateway"),
        ("PUT", "/manage/gateway/credentials"),
        ("POST", "/manage/gateway/validate"),
        ("DELETE", "/manage/gateway/credentials"),
        ("GET", "/manage/floor"),
        ("GET", "/manage/floor/dresses"),
        ("GET", "/manage/floor/clients"),
        ("POST", "/manage/floor/rooms"),
        ("GET", "/manage/floor/sos"),
        ("GET", "/manage/atelier/tickets"),
        ("GET", "/storefront/dresses"),
        ("GET", "/storefront/boutique"),
        ("GET", "/storefront/slots"),
        ("GET", "/storefront/appointment-types"),
        ("GET", "/storefront/terms"),
        ("POST", "/storefront/otp/send"),
        ("POST", "/storefront/otp/verify"),
        ("POST", "/storefront/checkin"),
        ("POST", "/storefront/queue"),
    }
)


# Module -> the minimum number of routes the walk must actually drive for it.
# Spelled out, never derived: a derived floor would fall as UNWALKABLE grew,
# which is precisely the drift it exists to catch.
MODULE_WALK_FLOOR = {
    "staff": 2,
    "boutique": 2,
    "catalog": 9,
    "booking": 10,
    "customers": 2,
    "privacy": 2,
    "floor": 12,
    "queue": 4,
    "atelier": 6,
    "storefront": 1,
}

# Modules that expose no route carrying a tenant-owned id, with the reason. A
# module may only be here — never merely missing from the floor above — and
# `test_no_module_is_wholly_exempt` asserts the two sets partition the route
# table exactly, so demoting a module into this set is a visible, reviewed act.
MODULES_WITH_NO_ID_ROUTES = {
    "auth": "login/logout/me take credentials and a cookie, never an entity id",
    "dashboard": "one route, no parameters at all — deliberately (dashboard/router.py)",
    "payments": (
        "the four gateway routes are tenant-singleton and take no id; the two "
        "storefront payment routes are in UNWALKABLE for their own reasons"
    ),
    "notifications": "OTP send/verify are keyed on a phone number, never an id",
}

# platform/ and storage/ appear in the plan's floor list and are absent here
# because NEITHER REGISTERS AN HTTP ROUTE: platform/ is the provisioning CLI
# (cli.py) and storage/ is the S3 adapter behind catalog's media routes. A floor
# of >=1 on a module with zero routes is unsatisfiable, not unmet.
MODULES_WITHOUT_ROUTES = frozenset({"platform", "storage"})

_MODULE_BY_PREFIX = (
    # Longest-first: /manage/floor/queue must beat /manage/floor, and
    # /storefront/booking/payment-status must beat /storefront/booking.
    ("/manage/floor/queue", "queue"),
    ("/storefront/booking/payment-status", "payments"),
    ("/manage/auth", "auth"),
    ("/manage/staff", "staff"),
    ("/manage/settings", "boutique"),
    ("/manage/appointment-types", "boutique"),
    ("/manage/availability", "boutique"),
    ("/manage/terms", "boutique"),
    ("/manage/slots", "booking"),
    ("/manage/dresses", "catalog"),
    ("/manage/bookings", "booking"),
    ("/manage/dashboard", "dashboard"),
    ("/manage/floor", "floor"),
    ("/manage/gateway", "payments"),
    ("/manage/customers", "customers"),
    ("/manage/privacy", "privacy"),
    ("/manage/checkin-qr", "queue"),
    ("/manage/atelier", "atelier"),
    ("/storefront/otp", "notifications"),
    ("/storefront/payments", "payments"),
    ("/storefront/bookings", "booking"),
    ("/storefront/booking", "booking"),
    ("/storefront/checkin", "queue"),
    ("/storefront/queue", "queue"),
    ("/storefront/dresses", "storefront"),
    ("/storefront/boutique", "storefront"),
    ("/storefront/slots", "storefront"),
    ("/storefront/appointment-types", "storefront"),
    ("/storefront/terms", "storefront"),
)


def _module(path: str) -> str:
    for prefix, name in _MODULE_BY_PREFIX:
        if path.startswith(prefix):
            return name
    raise AssertionError(f"unclassified route path {path!r} — add it to _MODULE_BY_PREFIX")


def _leaf_routes(node: Any) -> Iterator[Any]:
    """FastAPI wraps an included router in `_IncludedRouter` rather than
    flattening it — recurse through `original_router` like test_storefront_api
    and test_staff_role_gating, or the walker sees only the docs routes and
    passes vacuously."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def _route_table(app: FastAPI) -> set[tuple[str, str]]:
    table: set[tuple[str, str]] = set()
    for route in _leaf_routes(app):
        path = getattr(route, "path", None)
        if path is None:
            continue
        for method in getattr(route, "methods", None) or ():
            if method in ("HEAD", "OPTIONS"):
                continue
            if (method, path) in NOT_TENANT_SCOPED:
                continue
            table.add((method, path))
    return table


# --- the harness ---


@dataclass(frozen=True)
class Walk:
    """One walk, shared by every test below."""

    responses: dict[tuple[str, str], Response]
    table: set[tuple[str, str]]
    # Tenant B's ids, so the no-echo test can look for them in any body.
    other: dict[Kind, uuid.UUID]


def _settings() -> Settings:
    # dev, so the boot guard's `app_env != "dev"` exemption applies: this suite
    # connects as boutique_app, which the guard would pass anyway, but the
    # lifespan must not reach for the process-global engine.
    return Settings(app_env="dev", session_ttl_seconds=3600)


def _generous_limiter(*_args: object, **_kwargs: object) -> FixedWindowRateLimiter:
    """Every limiter `create_app()` builds, replaced with one that never trips.

    Throttling is not the variable under test and a 429 would read as an
    isolation failure — the walk fires a hundred-odd requests at surfaces sized
    for a bride with a phone. `.memory/limiter-max-is-per-instance` applies: this
    hands out a SEPARATE instance per call site, never one shared bucket, so the
    substitution cannot itself couple two budgets that production keeps apart."""
    return FixedWindowRateLimiter(max_attempts=100_000, window_seconds=1, clock=lambda: 0.0)


def _app(
    monkeypatch: pytest.MonkeyPatch, factory: async_sessionmaker[AsyncSession]
) -> tuple[FastAPI, InMemoryMediaStorage]:
    storage = InMemoryMediaStorage()
    monkeypatch.setattr("app.main.get_settings", _settings)
    monkeypatch.setattr("app.main.get_session_factory", lambda: factory)
    monkeypatch.setattr("app.main.FixedWindowRateLimiter", _generous_limiter)
    # Patched rather than assigned after the fact: create_app() hands the object
    # to BOTH app.state.media_storage (which the router's dependency reads) and
    # CatalogService (which the presign/confirm path reads), and the two must be
    # the same instance or a confirm never sees what the presign stored.
    monkeypatch.setattr("app.main._build_media_storage", lambda _settings: storage)
    app = create_app(resolver=RepositoryTenantResolver(factory))
    return app, storage


def _client(app: FastAPI, slug: str) -> TestClient:
    # No Origin header: CsrfOriginMiddleware only inspects a request that carries
    # one, and the walk swaps Host per tenant, so sending one would test CSRF
    # instead of isolation.
    return TestClient(app, base_url=f"http://{slug}.localtest.me")


async def _seed_tenant(factory: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, str, str]:
    """Only the two rows that have no HTTP surface to create them: the tenant and
    its first owner. Everything else this module needs is created through the
    product's own API, so no fixture can be more permissive than the code."""
    slug = f"walk{uuid.uuid4().hex[:8]}"
    tenant = await TenantsRepository(factory).insert(slug=slug, name="Bella Bridal")
    email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
    async with tenant_session(factory, tenant.id) as session:
        await StaffUsersRepository().insert(
            session,
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(PASSWORD),
            display_name="Owner",
        )
    return tenant.id, slug, email


def _ok(resp: Response, what: str) -> dict[str, Any]:
    assert resp.status_code in (200, 201), f"seeding {what} failed: {resp.status_code} {resp.text}"
    body = resp.json()
    assert isinstance(body, dict)
    return body


def _populate(client: TestClient, storage: InMemoryMediaStorage) -> dict[Kind, uuid.UUID]:
    """Every entity kind whose id can reach the wire, created over HTTP as this
    tenant's own owner. The order is a dependency order, not a preference:
    an assignment needs a room, a binding needs an assignment, a booking needs a
    customer and an appointment type."""
    ids: dict[Kind, uuid.UUID] = {}

    staff = _ok(
        client.post(
            "/manage/staff",
            json={
                "email": f"seam-{uuid.uuid4().hex[:8]}@bella.example",
                "display_name": "Second staffer",
                # ⚠ shift_manager, NOT a floor role, and that is a constraint
                # this module inherits rather than a preference. `migrated_db` is
                # session-scoped, and test_migrations.py's `_constraint_accepts`
                # re-adds 0011's TWO-value role CHECK over the WHOLE staff_users
                # table — so one committed 'seamstress' row from here reds three
                # of its tests. F57's own note records the same trap and the same
                # answer: the floor-role case is rolled back rather than
                # committed. The role is irrelevant to the walk: every probe
                # against this id expects a refusal either way.
                "role": "shift_manager",
                "password": "second-staffer-pw",
            },
        ),
        "staff",
    )
    ids[Kind.STAFF] = uuid.UUID(staff["id"])

    dress = _ok(client.post("/manage/dresses", json={"name": "Aria"}), "dress")
    ids[Kind.DRESS] = uuid.UUID(dress["id"])

    presign = _ok(
        client.post(
            f"/manage/dresses/{ids[Kind.DRESS]}/media/presign",
            json={"content_type": "image/jpeg", "byte_size": len(JPEG_BODY)},
        ),
        "presign",
    )
    # The browser's POST to S3, simulated: InMemoryMediaStorage has no upload
    # endpoint, so the test puts the object at the key the presign returned.
    storage.put(key=presign["fields"]["key"], content_type="image/jpeg", body=JPEG_BODY)
    _ok(
        client.post(f"/manage/dresses/{ids[Kind.DRESS]}/media/{presign['media_id']}/confirm"),
        "media confirm",
    )
    ids[Kind.MEDIA] = uuid.UUID(presign["media_id"])

    appointment_type = _ok(
        client.post(
            "/manage/appointment-types",
            json={"name": "Fitting", "duration_minutes": 60, "deposit_required": False},
        ),
        "appointment type",
    )
    ids[Kind.APPOINTMENT_TYPE] = uuid.UUID(appointment_type["id"])

    exception = _ok(
        client.post("/manage/availability/exceptions", json={"date": _FUTURE_DATE}),
        "availability exception",
    )
    ids[Kind.AVAILABILITY_EXCEPTION] = uuid.UUID(exception["id"])

    ticket = _ok(
        client.post(
            "/storefront/checkin",
            json={"name": "Noa", "phone": "+972500000333", "visit_type": "bride"},
        ),
        "checkin",
    )
    ids[Kind.QUEUE_TICKET] = uuid.UUID(ticket["id"])

    # The atelier create is what mints the customer row, by a (tenant, phone)
    # upsert (atelier/service.py:130, :254). A public check-in deliberately does
    # NOT — Amendment 13's minimisation duty keeps her a person in a queue rather
    # than a contact — so this ordering is a product fact, not a convenience.
    atelier = _ok(
        client.post(
            "/manage/atelier/tickets",
            json={
                "customer_name": "Noa",
                "customer_phone": "+972500000333",
                "due_date": _FUTURE_DATE,
                "effort_band": "one_hour",
            },
        ),
        "atelier ticket",
    )
    ids[Kind.ATELIER_TICKET] = uuid.UUID(atelier["id"])

    customers = _ok(client.get("/manage/customers"), "customer list")
    assert customers["items"], "no customer row exists to probe with"
    ids[Kind.CUSTOMER] = uuid.UUID(customers["items"][0]["id"])

    booking = _ok(
        client.post(
            "/manage/bookings/walk-in",
            json={
                "customer_id": str(ids[Kind.CUSTOMER]),
                "appointment_type_id": str(ids[Kind.APPOINTMENT_TYPE]),
            },
        ),
        "walk-in booking",
    )
    ids[Kind.BOOKING] = uuid.UUID(booking["id"])

    room = _ok(client.post("/manage/floor/rooms", json={"label": "Room 1"}), "room")
    ids[Kind.ROOM] = uuid.UUID(room["id"])

    # Every floor mutation answers a whole `Room`, never the row it changed, so
    # the assignment and the binding are read out of the nested payload rather
    # than off the top-level `id` — which is the ROOM's.
    claimed = _ok(client.post(f"/manage/floor/rooms/{ids[Kind.ROOM]}/claim", json={}), "room claim")
    ids[Kind.ASSIGNMENT] = uuid.UUID(claimed["assignment"]["id"])

    bound = _ok(
        client.post(
            f"/manage/floor/assignments/{ids[Kind.ASSIGNMENT]}/dresses",
            json={"dress_id": str(ids[Kind.DRESS])},
        ),
        "assignment dress",
    )
    ids[Kind.BINDING] = uuid.UUID(bound["assignment"]["dresses"][0]["id"])

    # `RaisedAlert`, not `SosAlertView`: the raise is the one route that wraps the
    # alert, because `rerouted` is a fact about the request rather than the row.
    raised = _ok(client.post("/manage/floor/sos", json={"note": "help"}), "sos alert")
    ids[Kind.SOS_ALERT] = uuid.UUID(raised["alert"]["id"])

    assert set(ids) == set(Kind), f"unseeded entity kinds: {sorted(set(Kind) - set(ids))}"
    return ids


def _resolve(value: Any, ids: dict[Kind, uuid.UUID]) -> Any:
    if isinstance(value, Kind):
        return str(ids[value])
    if isinstance(value, dict):
        return {key: _resolve(item, ids) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, ids) for item in value]
    return value


def _drive(
    client: TestClient, method: str, path: str, ids: dict[Kind, uuid.UUID]
) -> tuple[Response, str]:
    url = path
    for param in re.findall(r"\{(\w+)\}", path):
        url = url.replace("{" + param + "}", str(ids[_path_kind(path, param)]))
    body = PROBES.get((method, path))
    payload = _resolve(body, ids) if body is not None else None
    return client.request(method, url, json=payload), url


@pytest.fixture(scope="module")
def walk(app_role_url: str) -> Iterator[Walk]:
    """The whole walk, run once. Module-scoped because seeding two tenants over
    HTTP is the expensive part and every test below reads the same result."""
    monkeypatch = pytest.MonkeyPatch()
    engine: AsyncEngine = create_async_engine(app_role_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        app, storage = _app(monkeypatch, factory)
        _, slug_a, email_a = asyncio.run(_seed_tenant(factory))
        _, slug_b, email_b = asyncio.run(_seed_tenant(factory))

        with _client(app, slug_b) as client_b:
            assert (
                client_b.post(
                    "/manage/auth/login", json={"email": email_b, "password": PASSWORD}
                ).status_code
                == 200
            )
            other = _populate(client_b, storage)

        responses: dict[tuple[str, str], Response] = {}
        table = _route_table(app)
        walkable = sorted(table - set(UNWALKABLE) - NO_TENANT_OWNED_ID)
        with _client(app, slug_a) as client_a:
            assert (
                client_a.post(
                    "/manage/auth/login", json={"email": email_a, "password": PASSWORD}
                ).status_code
                == 200
            )
            for method, path in walkable:
                responses[(method, path)], _ = _drive(client_a, method, path, other)
        yield Walk(responses=responses, table=table, other=other)
    finally:
        monkeypatch.undo()
        asyncio.run(engine.dispose())


# --- the three tests ---


def test_every_tenant_scoped_route_refuses_another_tenants_ids(
    walk: Walk,
) -> None:
    """404, and nothing else. A 200 is a read or a write across the tenant
    boundary. A 403 confirms the row exists somewhere on the platform, which is
    the enumeration oracle row 9's text is actually about. A 500 means the route
    reached code that assumed the row existed — a failure, not an excuse."""
    responses = walk.responses
    assert responses, "the walk drove nothing — the walker is broken"
    wrong = {
        route: (resp.status_code, resp.text[:200])
        for route, resp in responses.items()
        if resp.status_code != EXPECTED_STATUS.get(route, (404, ""))[0]
    }
    assert not wrong, "routes that did not refuse another tenant's ids as expected:\n" + "\n".join(
        f"  {method} {path} -> {status} {body}"
        for (method, path), (status, body) in sorted(wrong.items())
    )


def test_no_route_answers_a_server_error(
    walk: Walk,
) -> None:
    """Split out from the status assertion so a 500 reads as what it is. A 500 to
    a foreign id means the route reached code that assumed the row existed — it
    is a failure and not an excuse, and it is the shape most likely to be a leak
    in a traceback rather than in a body."""
    responses = walk.responses
    crashed = {
        route: resp.status_code for route, resp in responses.items() if resp.status_code >= 500
    }
    assert not crashed, f"routes that crashed on another tenant's ids: {sorted(crashed)}"


def test_no_response_echoes_the_other_tenants_ids(
    walk: Walk,
) -> None:
    """The leak check that does not depend on the status code being right, and
    the one that makes the two `EXPECTED_STATUS` entries safe to hold. A route
    could answer 200 for a defensible reason and still hand back a row it read
    across the boundary; this says no response body, on any route, at any status,
    may contain an id belonging to tenant B."""
    responses = walk.responses
    seeded = walk.other
    leaked = {}
    for route, resp in responses.items():
        echoed = sorted(kind for kind, value in seeded.items() if str(value) in resp.text)
        if echoed:
            leaked[route] = (resp.status_code, echoed)
    assert not leaked, "responses echoing tenant B's ids:\n" + "\n".join(
        f"  {method} {path} -> {status} echoed {kinds}"
        for (method, path), (status, kinds) in sorted(leaked.items())
    )


def test_the_walk_and_the_exemptions_are_the_whole_route_table(
    walk: Walk,
) -> None:
    """Both directions. A new route is a TEST FAILURE, not a silent gap; an
    exemption naming a route that no longer exists must be pruned, not left.
    Carries test_every_manage_route_is_role_gated's two anti-vacuity legs."""
    responses, table = walk.responses, walk.table
    walked = set(responses)
    exempt = set(UNWALKABLE) | NO_TENANT_OWNED_ID

    assert walked, "no route was walked"
    assert table, "the route table is empty — _leaf_routes stopped recursing"
    missing = table - walked - exempt
    assert not missing, (
        "routes that are neither walked nor exempted — classify each one:\n"
        + "\n".join(f"  {m} {p}" for m, p in sorted(missing))
    )
    stale = exempt - table
    assert not stale, "exemptions naming routes that no longer exist — prune them:\n" + "\n".join(
        f"  {m} {p}" for m, p in sorted(stale)
    )
    assert walked | exempt == table


def test_no_module_is_wholly_exempt(
    walk: Walk,
) -> None:
    """Risk 4 mechanised. Growing UNWALKABLE until a module contributes nothing
    is the failure mode that would let R9 read green over an unprobed surface —
    `privacy` and `staff` most of all, since one is the §13 subject-erase surface
    and the other is where the console's own accounts live."""
    responses, table = walk.responses, walk.table
    walked_per_module: dict[str, int] = {}
    for _, path in responses:
        walked_per_module[_module(path)] = walked_per_module.get(_module(path), 0) + 1

    short = {
        name: (walked_per_module.get(name, 0), floor)
        for name, floor in MODULE_WALK_FLOOR.items()
        if walked_per_module.get(name, 0) < floor
    }
    assert not short, "modules below their walk floor:\n" + "\n".join(
        f"  {name}: walked {got}, floor {floor}" for name, (got, floor) in sorted(short.items())
    )

    # The floor and the named-exempt set must PARTITION the modules the route
    # table actually has. Without this, a module could drop out of the floor and
    # simply stop being checked.
    in_table = {_module(path) for _, path in table}
    classified = set(MODULE_WALK_FLOOR) | set(MODULES_WITH_NO_ID_ROUTES)
    assert in_table == classified, (
        f"unclassified modules: {sorted(in_table - classified)}; "
        f"classified modules with no routes: {sorted(classified - in_table)}"
    )
    for name in MODULES_WITH_NO_ID_ROUTES:
        assert walked_per_module.get(name, 0) == 0, (
            f"module {name!r} is listed as having no id-carrying routes but the walk "
            f"drove {walked_per_module[name]} of them — move it to MODULE_WALK_FLOOR"
        )
    assert not MODULES_WITHOUT_ROUTES & in_table


def test_the_exemptions_each_carry_a_reason() -> None:
    """A bare route tuple in UNWALKABLE is the shape Risk 4 warns about. The
    structural set needs no per-line reason — its category comment is the
    reason — but the judgement half does, and 40 characters is enough to stop a
    one-word placeholder."""
    assert UNWALKABLE
    for route, reason in UNWALKABLE.items():
        assert len(reason) > 40, f"{route} needs a real reason, not {reason!r}"
    assert EXPECTED_STATUS
    for route, (_, reason) in EXPECTED_STATUS.items():
        assert len(reason) > 40, f"{route} needs a real reason, not {reason!r}"
