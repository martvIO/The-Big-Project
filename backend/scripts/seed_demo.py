#!/usr/bin/env python3
"""Seed a walkable demo boutique THROUGH THE REAL HTTP API.

Every write is a request a human could make from the console. Nothing here
touches a table, a repository or a service — which is the point: the script
doubles as a contract test, so an API change that breaks the console breaks this
script too. A seeder that reached past the API would seed around a broken
endpoint and report success.

Two prerequisites it deliberately cannot satisfy for itself (see WARNINGS at the
end of a run for the full list of gaps):

  1. the API is up            —  make dev
  2. the tenant and its first owner exist — provision them in the PLATFORM
     CONSOLE at admin.<base_domain>/platform (F25 deleted the four CLI
     lifecycle subcommands at parity). Seed yourself an operator first, which
     is the one part that is still shell-only because no HTTP route mints one:

       cd backend && python -m app.cli create-operator \\
         --email you@modryn.example --display-name "You" --operator you

Tenancy is HOSTNAME-derived and nothing else: --base-url IS the tenant selector,
because TenantResolutionMiddleware reads the leftmost label of the Host. The
session cookie is host-only (no Domain attribute), so one httpx.Client bound to
the tenant's own URL is what makes both work without a hand-rolled Host header.
localtest.me resolves to 127.0.0.1, so no /etc/hosts entry is needed in dev.
"""

import argparse
import datetime
import getpass
import os
import sys
from typing import Any
from urllib.parse import urlsplit

import httpx

DEFAULT_BASE_URL = "http://demo.localtest.me:8000"
DEFAULT_OWNER_EMAIL = "owner@demo.example"
# Printed in the summary and deliberately weak-but-legal (the API floor is 10
# chars): the whole purpose of this tenant is that a human can sign in as every
# role during a walkthrough. Override with SEED_STAFF_PASSWORD.
DEFAULT_STAFF_PASSWORD = "modryn-demo-2026"
TIMEOUT_SECONDS = 30.0

# 0=Sunday … 6=Saturday — jerusalem_day_index()'s encoding, NOT date.weekday().
# Saturday is absent rather than a closed rule: no rule IS closed.
WEEKLY_RULES: list[dict[str, Any]] = [
    {"day_of_week": 0, "open_time": "10:00", "close_time": "19:00", "capacity": 2},
    {"day_of_week": 1, "open_time": "10:00", "close_time": "19:00", "capacity": 2},
    {"day_of_week": 2, "open_time": "10:00", "close_time": "19:00", "capacity": 2},
    {"day_of_week": 3, "open_time": "10:00", "close_time": "21:00", "capacity": 3},
    {"day_of_week": 4, "open_time": "10:00", "close_time": "21:00", "capacity": 3},
    {"day_of_week": 5, "open_time": "09:00", "close_time": "13:00", "capacity": 2},
]

PROFILE: dict[str, Any] = {
    "phone": "+972 3 555 1234",
    "address": "רחוב שינקין 24, תל אביב",
    "description": (
        "בוטיק כלות בלב תל אביב. אנחנו מלוות כל כלה מהמדידה הראשונה ועד הצעד "
        "האחרון לפני החופה — גזרות קלאסיות לצד קווים נקיים ומודרניים, והכול "
        "מותאם אישית בסטודיו התפירה שלנו."
    ),
    "maps_url": "https://maps.google.com/?q=Sheinkin+24+Tel+Aviv",
    "essence": "שמלות כלה בעבודת יד, בהתאמה אישית מלאה",
    "instagram": "modryn.demo",
}

# Deposits stay OFF on purpose. A deposit-required type commits its booking as
# `pending_payment`, and only a signed provider webhook can move it to
# `confirmed` — so with deposits on, a demo booking gets stuck the moment
# somebody walks the bride flow. See the payments WARNING.
TOGGLES: dict[str, Any] = {"deposits_enabled": False, "brides_only": False}

# A FULL REPLACE of the whole `atelier` block: settings JSONB merges at the top
# level only, so a partial object here would delete the key it omits.
ATELIER: dict[str, Any] = {
    "effort_bands": {
        "thirty_min": 30,
        "one_hour": 60,
        "two_hours": 120,
        # Below the platform's 240/480: a six-hour boutique shift is the E9
        # brief's own example of why these are tunable at all.
        "half_day": 180,
        "full_day": 360,
    },
    "default_weekly_capacity_hours": 30,
}

APPOINTMENT_TYPES: list[dict[str, Any]] = [
    {"name": "פגישת ייעוץ", "duration_minutes": 45, "audience": "all", "sort_order": 10},
    {"name": "מדידה ראשונה", "duration_minutes": 90, "audience": "brides_only", "sort_order": 20},
    {"name": "מדידת התאמה", "duration_minutes": 60, "audience": "brides_only", "sort_order": 30},
    {"name": "מדידת שמלת ערב", "duration_minutes": 60, "audience": "all", "sort_order": 40},
]

STAFF: list[dict[str, Any]] = [
    {"email": "noa@demo.example", "display_name": "נועה ברזילי", "role": "shift_manager"},
    {"email": "shiran@demo.example", "display_name": "שירן כהן", "role": "reception"},
    {"email": "yael@demo.example", "display_name": "יעל מזרחי", "role": "sales_assistant"},
    {"email": "rivka@demo.example", "display_name": "רבקה לוי", "role": "seamstress"},
    {"email": "esther@demo.example", "display_name": "אסתר פרידמן", "role": "seamstress"},
]

# Two seamstresses, ONE override: the other resolves to the boutique default, so
# the capacity panel shows both `capacity_is_default` states side by side.
CAPACITY_OVERRIDE_EMAIL = "rivka@demo.example"
CAPACITY_OVERRIDE_HOURS = 22

# `variants` is not part of the create body — it is a second, full-replace PUT.
# Stock lives only in these rows: `out_of_stock` is derived, never stored, which
# is why "אביגיל" carries sizes at quantity 0 rather than no sizes at all.
DRESSES: list[dict[str, Any]] = [
    {
        "dress": {
            "name": "תמר",
            "description": "תחרה צרפתית, גזרת בת ים, שובל קצר.",
            "price_agorot": 1_290_000,
            "price_visible": True,
            "reserved": False,
            "sort_order": 10,
        },
        "variants": [
            {"size_label": "36", "quantity": 1, "sort_order": 10},
            {"size_label": "38", "quantity": 2, "sort_order": 20},
            {"size_label": "40", "quantity": 1, "sort_order": 30},
        ],
    },
    {
        "dress": {
            "name": "ליאן",
            "description": "משי טבעי, גב חשוף, כתפיות דקות.",
            "price_agorot": 1_590_000,
            "price_visible": True,
            "reserved": False,
            "sort_order": 20,
        },
        "variants": [
            {"size_label": "34", "quantity": 1, "sort_order": 10},
            {"size_label": "36", "quantity": 1, "sort_order": 20},
            {"size_label": "38", "quantity": 1, "sort_order": 30},
        ],
    },
    {
        "dress": {
            "name": "שירה",
            "description": "סאטן כבד, גזרה ישרה, מחשוף לב.",
            "price_agorot": 890_000,
            # The hidden-price path: the storefront shows the gown with no number.
            "price_visible": False,
            "reserved": False,
            "sort_order": 30,
        },
        "variants": [
            {"size_label": "38", "quantity": 2, "sort_order": 10},
            {"size_label": "42", "quantity": 1, "sort_order": 20},
        ],
    },
    {
        "dress": {
            "name": "נועם",
            "description": "טול רך בשכבות, מחוך רקום.",
            "price_agorot": 1_150_000,
            "price_visible": True,
            # The reserved badge.
            "reserved": True,
            "sort_order": 40,
        },
        "variants": [
            {"size_label": "38", "quantity": 1, "sort_order": 10},
            {"size_label": "40", "quantity": 1, "sort_order": 20},
        ],
    },
    {
        "dress": {
            "name": "אביגיל",
            "description": "קרפ מינימליסטי, שרוול ארוך.",
            "price_agorot": 740_000,
            "price_visible": True,
            "reserved": False,
            "sort_order": 50,
        },
        # Every size at zero — the derived out_of_stock badge, with the size
        # matrix still present so a human can see where the badge comes from.
        "variants": [
            {"size_label": "36", "quantity": 0, "sort_order": 10},
            {"size_label": "38", "quantity": 0, "sort_order": 20},
        ],
    },
]

ROOMS: list[dict[str, Any]] = [
    {"label": "חדר מדידה 1", "sort_order": 10},
    {"label": "חדר מדידה 2", "sort_order": 20},
    {"label": "סוויטת כלה", "sort_order": 30},
]

# An atelier ticket is also the ONLY API-level way to create a named customer:
# there is no customer-create endpoint anywhere, and intake upserts (tenant,
# phone) into `customers`. Due dates are relative to the run so the board never
# opens fully overdue.
TICKETS: list[dict[str, Any]] = [
    {
        "customer_name": "מיכל אברהמי",
        "customer_phone": "0521234567",
        "due_in_days": 4,
        "effort_band": "one_hour",
        "dress_name": "שמלה של הכלה מבית אחר",
        "dress_size": "38",
        "notes": "קיצור מכפלת, הרמת כתפיות.",
        "assign": True,
    },
    {
        "customer_name": "דנה שרעבי",
        "customer_phone": "0533456789",
        "due_in_days": 11,
        "effort_band": "half_day",
        "dress_name": "תמר",
        "dress_size": "38",
        "notes": "הצרה במותן, תיקון תחרה בגב.",
        "assign": False,
    },
    {
        "customer_name": "רותם כרמלי",
        "customer_phone": "0545678901",
        "due_in_days": 25,
        "effort_band": "two_hours",
        "dress_name": "ליאן",
        "dress_size": "36",
        "notes": "התאמת חזייה תפורה.",
        "assign": False,
    },
]

TERMS_TEXT = (
    "מדיניות ביטולים\n\n"
    "ביטול או שינוי מועד עד 48 שעות לפני הפגישה — ללא חיוב.\n"
    "ביטול בטווח של פחות מ-48 שעות, או אי-הגעה לפגישה — הפיקדון אינו מוחזר.\n\n"
    "הפגישה שמורה על שם הכלה בלבד. איחור של מעל 20 דקות עלול לקצר את זמן "
    "המדידה כדי לא לפגוע בכלה שאחריה.\n\n"
    "כל מדידה מלווה על ידי יועצת אישית. מלוות נוספות — בתיאום מראש."
)
TERMS_REFUNDABLE_HOURS = 48
TERMS_FORFEIT_PERCENT = 100


class SeedError(RuntimeError):
    """The seed is not what it claims to be — an unnamed non-2xx, or a response
    whose shape we could not read. Always carries the body: a seeder that
    swallows one and keeps going is worse than no seeder, because it reports
    success for a boutique that is half-configured."""


def _error_code(response: httpx.Response) -> str | None:
    """The house error shape is `{"error": {"code", "message"}}` everywhere."""
    try:
        body = response.json()
    except ValueError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    return error.get("code") if isinstance(error, dict) else None


class Api:
    def __init__(self, base_url: str) -> None:
        # base_url rather than a manual Host header: the session cookie carries
        # no Domain attribute, so httpx replays it only for the exact host that
        # set it — which is the same host that selects the tenant.
        self._client = httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Api":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def call(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        tolerate: tuple[str, ...] = (),
    ) -> Any:
        """Returns the decoded body, or None when the call hit one of the
        `tolerate` codes — the "already seeded" conflicts (DUPLICATE_NAME,
        DUPLICATE_EMAIL, …) that a second run must survive. Every other non-2xx
        raises with the real body attached.

        No Origin header is ever sent, which is what keeps CsrfOriginMiddleware
        out of the way: it only refuses a mutating /manage request whose Origin
        names a different hostname than the Host.
        """
        response = self._client.request(method, path, json=json, params=params)
        if response.is_success:
            return None if response.status_code == 204 else response.json()
        code = _error_code(response)
        if code in tolerate:
            return None
        raise SeedError(f"{method} {path} -> HTTP {response.status_code}: {response.text}")


def _obj(payload: Any, where: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SeedError(f"{where}: expected a JSON object, got {payload!r}")
    return payload


def _rows(payload: Any, where: str) -> list[Any]:
    if not isinstance(payload, list):
        raise SeedError(f"{where}: expected a JSON array, got {payload!r}")
    return payload


def _field(payload: Any, key: str, where: str) -> Any:
    body = _obj(payload, where)
    if key not in body:
        raise SeedError(f"{where}: response has no {key!r} — got {body!r}")
    return body[key]


def _slug_of(base_url: str) -> str:
    host = urlsplit(base_url).hostname
    if not host or "." not in host:
        raise SeedError(
            f"--base-url {base_url!r} has no <slug>.<base-domain> host. Tenancy is "
            "resolved from the leftmost DNS label and from nothing else."
        )
    return host.split(".")[0]


def sign_in(api: Api, *, email: str, password: str, slug: str) -> dict[str, Any]:
    """One attempt, never a retry loop: only FAILURES count against the login
    limiter (5 per 15 min per tenant+email), so a seeder that retries a wrong
    password locks the owner out for the window."""
    try:
        payload = api.call(
            "POST", "/manage/auth/login", json={"email": email, "password": password}
        )
    except SeedError as exc:
        raise SeedError(
            f"{exc}\n\n"
            "Login failed — do NOT re-run with a guessed password (see above).\n"
            "  TENANT_NOT_FOUND    no active boutique at this host. Provision it in\n"
            f"                      the platform console (admin.<base>/platform): slug {slug},\n"
            f"                      owner {email}. The four CLI lifecycle subcommands were\n"
            "                      deleted at parity in F25.\n"
            "  INVALID_CREDENTIALS wrong password, or that owner does not exist.\n"
            "  TOO_MANY_ATTEMPTS   the limiter is tripped; wait out the window."
        ) from exc
    staff = _obj(payload, "POST /manage/auth/login")
    role = _field(staff, "role", "POST /manage/auth/login")
    if role != "owner":
        raise SeedError(
            f"signed in as role {role!r}, but the seeder needs the OWNER: /manage/terms "
            "and all of /manage/staff are owner-only."
        )
    return staff


def seed_settings(api: Api) -> str:
    api.call(
        "PUT",
        "/manage/settings",
        json={
            "profile": PROFILE,
            "toggles": TOGGLES,
            "atelier": ATELIER,
        },
    )
    return "settings: profile, toggles (deposits off), atelier bands + 30h default"


def seed_appointment_types(api: Api) -> str:
    where = "GET /manage/appointment-types"
    existing = {
        _field(row, "name", where)
        for row in _rows(api.call("GET", "/manage/appointment-types"), where)
    }
    created = 0
    for spec in APPOINTMENT_TYPES:
        if spec["name"] in existing:
            continue
        if api.call("POST", "/manage/appointment-types", json=spec, tolerate=("DUPLICATE_NAME",)):
            created += 1
    return (
        f"appointment types: {created} created, {len(APPOINTMENT_TYPES) - created} already present"
    )


def seed_availability(api: Api) -> str:
    # A full replace, so it is idempotent by construction — whatever is not sent
    # is gone, which is exactly what re-running should mean here.
    api.call("PUT", "/manage/availability/rules", json={"rules": WEEKLY_RULES})

    where = "GET /manage/availability"
    current = api.call("GET", "/manage/availability")
    # Exceptions are dated, so a rerun on a later day would stack a second one
    # forever. Any existing exception means a human (or an earlier run) has
    # already said something about closures; leave it alone.
    if _field(current, "exceptions", where):
        return f"availability: {len(WEEKLY_RULES)} weekly windows replaced, exceptions left as-is"

    closure = datetime.date.today() + datetime.timedelta(days=30)
    api.call(
        "POST",
        "/manage/availability/exceptions",
        json={
            "date": closure.isoformat(),
            "open_time": None,
            "close_time": None,
            "note": "יום השתלמות צוות — הבוטיק סגור",
        },
        tolerate=("DUPLICATE_DATE",),
    )
    return (
        f"availability: {len(WEEKLY_RULES)} weekly windows (Sun–Fri, Sat closed), "
        f"1 closure on {closure.isoformat()}"
    )


def seed_staff(api: Api, password: str) -> tuple[str, dict[str, str]]:
    created = 0
    for member in STAFF:
        body = dict(member, password=password)
        if api.call("POST", "/manage/staff", json=body, tolerate=("DUPLICATE_EMAIL",)):
            created += 1

    # Read back regardless: on a rerun every POST is a tolerated 409 and this is
    # the only way to learn the seamstress id the capacity write needs.
    where = "GET /manage/staff"
    by_email = {
        _field(row, "email", where): str(_field(row, "id", where))
        for row in _rows(api.call("GET", "/manage/staff"), where)
    }
    missing = [member["email"] for member in STAFF if member["email"] not in by_email]
    if missing:
        raise SeedError(f"{where}: seeded staff missing from the list: {missing}")
    return (
        f"staff: {created} created, {len(STAFF) - created} already present (all five roles)",
        by_email,
    )


def seed_capacity(api: Api, staff_ids: dict[str, str]) -> str:
    staff_user_id = staff_ids[CAPACITY_OVERRIDE_EMAIL]
    payload = api.call(
        "POST",
        f"/manage/atelier/seamstresses/{staff_user_id}/capacity",
        json={"weekly_capacity_hours": CAPACITY_OVERRIDE_HOURS},
    )
    where = f"POST /manage/atelier/seamstresses/{staff_user_id}/capacity"
    resolved = _field(payload, "weekly_capacity_hours", where)
    if resolved != CAPACITY_OVERRIDE_HOURS:
        raise SeedError(
            f"{where}: asked for {CAPACITY_OVERRIDE_HOURS}h, server resolved {resolved!r}"
        )
    return (
        f"seamstress capacity: רבקה לוי at {CAPACITY_OVERRIDE_HOURS}h/week, "
        "אסתר פרידמן left on the boutique default"
    )


def seed_dresses(api: Api) -> tuple[str, dict[str, str]]:
    where = "GET /manage/dresses"
    listing = api.call("GET", "/manage/dresses", params={"offset": 0, "limit": 100})
    by_name = {
        _field(row, "name", where): str(_field(row, "id", where))
        for row in _rows(_field(listing, "items", where), where)
    }

    created = 0
    for spec in DRESSES:
        name = spec["dress"]["name"]
        if name not in by_name:
            payload = api.call("POST", "/manage/dresses", json=spec["dress"])
            by_name[name] = str(_field(payload, "id", "POST /manage/dresses"))
            created += 1
        # A full replace, so re-running restates the same matrix rather than
        # duplicating it (a second POST of the same size would be DUPLICATE_SIZE).
        api.call(
            "PUT",
            f"/manage/dresses/{by_name[name]}/variants",
            json={"variants": spec["variants"]},
        )

    return (
        f"dresses: {created} created, {len(DRESSES) - created} already present; "
        "size matrices replaced on all of them",
        by_name,
    )


def seed_rooms(api: Api) -> str:
    # Room labels carry NO uniqueness constraint, so a blind re-run would stack
    # duplicate rooms — GET-then-skip is the only idempotency available here.
    where = "GET /manage/floor"
    labels = {
        _field(row, "label", where)
        for row in _rows(_field(api.call("GET", "/manage/floor"), "rooms", where), where)
    }
    created = 0
    for room in ROOMS:
        if room["label"] in labels:
            continue
        api.call("POST", "/manage/floor/rooms", json=room)
        created += 1
    return f"fitting rooms: {created} created, {len(ROOMS) - created} already present"


def seed_tickets(api: Api, staff_ids: dict[str, str], dress_ids: dict[str, str]) -> str:
    where = "GET /manage/atelier/tickets"
    board = api.call("GET", "/manage/atelier/tickets")
    known = {
        _field(row, "customer_name", where) for row in _rows(_field(board, "tickets", where), where)
    }

    today = datetime.date.today()
    created = 0
    for spec in TICKETS:
        if spec["customer_name"] in known:
            continue
        # dress_name is legal ONLY when dress_id is null; when the gown IS in the
        # catalog the server copies dresses.name itself, so the snapshot can
        # never disagree with the row it came from.
        dress_id = dress_ids.get(spec["dress_name"])
        body: dict[str, Any] = {
            "customer_name": spec["customer_name"],
            "customer_phone": spec["customer_phone"],
            "due_date": (today + datetime.timedelta(days=spec["due_in_days"])).isoformat(),
            "effort_band": spec["effort_band"],
            "assigned_staff_user_id": staff_ids[CAPACITY_OVERRIDE_EMAIL]
            if spec["assign"]
            else None,
            "dress_id": dress_id,
            "dress_name": None if dress_id else spec["dress_name"],
            "dress_size": spec["dress_size"],
            "notes": spec["notes"],
        }
        api.call("POST", "/manage/atelier/tickets", json=body)
        created += 1
    return (
        f"atelier tickets: {created} created, {len(TICKETS) - created} already present "
        "(each one also upserts its customer row)"
    )


def seed_terms(api: Api) -> str:
    # Insert-only, versioned and rate-limited per tenant: a blind re-run mints
    # version N+1 every time while already-seeded bookings keep pointing at the
    # old one. Publish only when the boutique has no current policy at all.
    where = "GET /manage/terms"
    current = _field(api.call("GET", "/manage/terms"), "current", where)
    if current is not None:
        version = _field(current, "version", where)
        return f"terms: version {version} already published, left alone (the table is insert-only)"

    payload = api.call(
        "POST",
        "/manage/terms",
        json={
            "terms_text": TERMS_TEXT,
            "refundable_until_hours_before": TERMS_REFUNDABLE_HOURS,
            "forfeit_percent": TERMS_FORFEIT_PERCENT,
        },
    )
    version = _field(payload, "version", "POST /manage/terms")
    return f"terms: version {version} published ({TERMS_REFUNDABLE_HOURS}h refundable window)"


def verify_storefront(api: Api) -> tuple[list[str], str]:
    """The seed's own contract assertion, and the runnable check behind every
    write above it. Configuration that does not surface on the public storefront
    is configuration a bride cannot use — and these reads are the cheapest proof
    that the whole chain (host → tenant → availability → slot engine) resolved.

    Also answers the boutique's display name, which the WARNINGS need: it is the
    one field seeded here that no endpoint can write."""
    where = "GET /storefront/appointment-types"
    types = _rows(api.call("GET", "/storefront/appointment-types"), where)
    if not types:
        raise SeedError(f"{where} is empty after seeding — nothing is bookable")

    today = datetime.date.today()
    window_end = today + datetime.timedelta(days=14)
    where = "GET /storefront/slots"
    slots = _rows(
        _field(
            api.call(
                "GET",
                "/storefront/slots",
                params={
                    "from": today.isoformat(),
                    "to": window_end.isoformat(),
                },
            ),
            "slots",
            where,
        ),
        where,
    )
    if not slots:
        raise SeedError(
            f"{where} is empty for {today}..{window_end} — the weekly rules did not "
            "produce a single bookable start. Check the day_of_week encoding (0=Sunday)."
        )

    where = "GET /storefront/dresses"
    dresses = _rows(_field(api.call("GET", "/storefront/dresses"), "items", where), where)
    if not dresses:
        raise SeedError(f"{where} is empty after seeding the catalog")

    terms_version = _field(api.call("GET", "/storefront/terms"), "version", "GET /storefront/terms")

    where = "GET /storefront/boutique"
    boutique_name = _field(api.call("GET", "/storefront/boutique"), "name", where)

    lines = [
        f"storefront: {len(types)} appointment types, "
        f"{len(slots)} bookable slots in the next 14 days",
        f"storefront: {len(dresses)} public dresses, terms version {terms_version}",
        f"storefront <h1>: {boutique_name}",
    ]
    return lines, str(boutique_name)


def warnings(boutique_name: str, base_url: str, slug: str, owner_email: str) -> list[str]:
    """Every gap the API leaves open, named. A seeder that silently skipped one
    would leave a human discovering it mid-walkthrough."""
    return [
        f"BOUTIQUE NAME is {boutique_name!r} and NO endpoint can change it. PUT /manage/settings "
        "merges the settings JSONB only; tenants.name is set once at provision time. If that "
        "name is wrong, re-provision the tenant under a fresh slug or fix it with SQL.",
        "DRESS PHOTOS are not seeded and cannot be: presign/confirm answer 503 "
        "MEDIA_NOT_CONFIGURED without MEDIA_BUCKET, and confirm verifies the object's magic "
        "bytes, so there is no 'attach this URL' shortcut. For imagery, point MEDIA_BUCKET / "
        "MEDIA_ENDPOINT_URL at MinIO and upload through the console.",
        "BOOKINGS are not seeded. The only writer is the anonymous POST /storefront/bookings, "
        "which needs a verification_token from /storefront/otp/verify. To walk it yourself set "
        "SMS_PROVIDER=fake and OTP_DEV_CODE=<code> (both are boot-forbidden in production) and "
        f"book from {base_url}/ — that is the walkthrough's own job, and past/completed bookings "
        "are unreachable through the API in any case.",
        "DEPOSITS are off (toggles.deposits_enabled=false, no deposit_required type). Turning "
        "them on without PAYMENT_PROVIDER + GATEWAY_SECRET_BOX strands every new booking in "
        "pending_payment: only a signed provider webhook can confirm one.",
        "LIVE FLOOR AND QUEUE STATE are deliberately not seeded — an occupied fitting room or a "
        "waiting queue ticket reads differently tomorrow, because both are computed against the "
        "Jerusalem clock at read time. Claim a room and check somebody in during the demo.",
        "SMS HISTORY, AUDIT LOG and SCHEDULED MESSAGES have no write endpoints at all. They "
        "populate only as a side effect of really firing sends through the fake provider.",
        f"OWNER PASSWORD is not managed here. Reset it from the platform console at "
        f"admin.<base_domain>/platform — the row action «איפוס סיסמת בעלים» on {slug}, with "
        f"{owner_email} as the owner address. The `app.cli reset-password` subcommand this "
        "line used to name was deleted at parity in F25.",
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seed_demo",
        description="Seed a walkable demo boutique through the real HTTP API.",
        epilog=(
            "PREREQUISITES (neither is something this script can create):\n"
            "  1. the API is running        —  make dev\n"
            "  2. the tenant and its owner exist — provision them in the platform\n"
            "     console at admin.<base_domain>/platform (seed an operator first with\n"
            "     `python -m app.cli create-operator`; there is no HTTP route that\n"
            "     mints one)\n\n"
            "The owner password is read from SEED_OWNER_PASSWORD or prompted for — never\n"
            "from argv, which would leak it into the process list and shell history.\n\n"
            "TENANCY COMES FROM THE HOSTNAME AND NOTHING ELSE: --base-url selects the\n"
            "boutique via the leftmost DNS label of its host. localtest.me resolves to\n"
            "127.0.0.1, so http://demo.localtest.me:8000 works with no /etc/hosts entry.\n\n"
            "Re-running is safe: full-replace writes are restated, and every create either\n"
            "GETs-then-skips or treats its own duplicate 409 as success."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"default {DEFAULT_BASE_URL}")
    parser.add_argument(
        "--owner-email",
        dest="owner_email",
        default=DEFAULT_OWNER_EMAIL,
        help=f"the owner created when the boutique was provisioned (default {DEFAULT_OWNER_EMAIL})",
    )
    return parser


def read_owner_password() -> str:
    password = os.environ.get("SEED_OWNER_PASSWORD")
    if password:
        return password
    if sys.stdin.isatty():
        return getpass.getpass("Owner password: ")
    return sys.stdin.readline().rstrip("\n")


def seed(
    base_url: str, owner_email: str, owner_password: str, staff_password: str
) -> tuple[list[str], str]:
    slug = _slug_of(base_url)
    with Api(base_url) as api:
        sign_in(api, email=owner_email, password=owner_password, slug=slug)

        lines = [seed_settings(api), seed_appointment_types(api), seed_availability(api)]
        staff_line, staff_ids = seed_staff(api, staff_password)
        lines.append(staff_line)
        lines.append(seed_capacity(api, staff_ids))
        dress_line, dress_ids = seed_dresses(api)
        lines.append(dress_line)
        lines.append(seed_rooms(api))
        lines.append(seed_tickets(api, staff_ids, dress_ids))
        lines.append(seed_terms(api))
        verified, boutique_name = verify_storefront(api)
        lines.extend(verified)
        return lines, boutique_name


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    staff_password = os.environ.get("SEED_STAFF_PASSWORD", DEFAULT_STAFF_PASSWORD)

    try:
        slug = _slug_of(args.base_url)
        lines, boutique_name = seed(
            args.base_url, args.owner_email, read_owner_password(), staff_password
        )
    except httpx.ConnectError as exc:
        print(
            f"FAILED: cannot reach {args.base_url} ({exc}).\n"
            "Is the API up (`make dev`)? localtest.me needs working DNS — it is a public\n"
            "wildcard that resolves to 127.0.0.1.",
            file=sys.stderr,
        )
        return 2
    except SeedError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print("\nSEEDED")
    for line in lines:
        print(f"  - {line}")

    # Derived from --base-url, never a hardcoded dev port: this script's whole
    # tenancy story is that the base URL IS the tenant selector, and printing
    # :5173/:5174 sent a reader to the Vite dev-server layout — a DIFFERENT
    # configuration, usually not even listening — after seeding through :8000.
    origin = args.base_url.rstrip("/")
    print("\nSIGN IN")
    print(f"  console     {origin}/manage")
    print(f"  storefront  {origin}/")
    print(f"  owner       {args.owner_email}  (the password you just entered)")
    for member in STAFF:
        print(f"  {member['role']:<14} {member['email']}  /  {staff_password}")

    print("\nWARNINGS — things no endpoint can do, and a human must")
    for warning in warnings(boutique_name, origin, slug, args.owner_email):
        print(f"  ! {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
