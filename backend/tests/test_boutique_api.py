"""Feature 7 fast API tests: route wiring, 401s, house-shape validation 400s,
409 mappings, CSRF Origin checks, and terms pagination — fake service +
hardcoded TenantContext resolver, no database (test_auth_api.py style)."""

import datetime
import time
import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.boutique.service import (
    AvailabilityResult,
    DuplicateDateError,
    DuplicateNameError,
    NotFoundError,
    SettingsResult,
    TermsHistoryResult,
    TermsThrottledError,
    TermsVersionConflictError,
)
from app.boutique.validation import BoutiqueValidationError, WeeklyRuleInput
from app.main import create_app
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.terms_version import TermsVersion
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

TYPE_ID = uuid.uuid4()
RULE_ID = uuid.uuid4()
EXCEPTION_ID = uuid.uuid4()
TERMS_ID = uuid.uuid4()

TYPE_CREATE_BODY = {"name": "Fitting", "duration_minutes": 60}
TYPE_UPDATE_BODY = {
    "name": "Fitting",
    "duration_minutes": 90,
    "audience": "brides_only",
    "deposit_required": True,
    "deposit_amount_agorot": 15000,
    "sort_order": 2,
}
RULES_BODY = {"rules": [{"day_of_week": 0, "open_time": "09:00", "close_time": "17:00"}]}
EXCEPTION_BODY = {"date": "2026-08-01", "note": "Holiday"}
TERMS_BODY = {"terms_text": "Cancel 48h before.", "refundable_until_hours_before": 48}

# Every /manage route this feature adds, with a body that passes schema
# validation — so 401 (and CSRF) failures are attributable to the guard alone.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/manage/settings", None),
    ("PUT", "/manage/settings", {}),
    ("GET", "/manage/appointment-types", None),
    ("POST", "/manage/appointment-types", TYPE_CREATE_BODY),
    ("PATCH", f"/manage/appointment-types/{TYPE_ID}", TYPE_UPDATE_BODY),
    ("DELETE", f"/manage/appointment-types/{TYPE_ID}", None),
    ("GET", "/manage/availability", None),
    ("PUT", "/manage/availability/rules", RULES_BODY),
    ("POST", "/manage/availability/exceptions", EXCEPTION_BODY),
    ("DELETE", f"/manage/availability/exceptions/{EXCEPTION_ID}", None),
    ("GET", "/manage/terms", None),
    ("POST", "/manage/terms", TERMS_BODY),
]


class FakeAuthService:
    def __init__(self) -> None:
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=TENANT.id,
            email="owner@bella.example",
            display_name="Owner",
            role="owner",
        )

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


class FakeBoutiqueService:
    """Duck-typed BoutiqueSettingsService: records every call, raises on demand,
    returns canned ORM-model rows (instantiable without a database)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.raise_on: dict[str, Exception] = {}
        self.settings_result = SettingsResult(
            profile={"phone": "+972-3-555-0100"},
            toggles={"deposits_enabled": True},
        )
        self.type_row = AppointmentType(
            id=TYPE_ID,
            tenant_id=TENANT.id,
            name="Fitting",
            duration_minutes=60,
            audience="all",
            deposit_required=False,
            deposit_amount_agorot=None,
            sort_order=0,
        )
        self.rule_row = AvailabilityRule(
            id=RULE_ID,
            tenant_id=TENANT.id,
            day_of_week=0,
            open_time=datetime.time(9, 0),
            close_time=datetime.time(17, 0),
            capacity=1,
        )
        self.exception_row = AvailabilityException(
            id=EXCEPTION_ID,
            tenant_id=TENANT.id,
            date=datetime.date(2026, 8, 1),
            open_time=None,
            close_time=None,
            note="Holiday",
        )
        self.terms_row = TermsVersion(
            id=TERMS_ID,
            tenant_id=TENANT.id,
            version=1,
            terms_text="Cancel 48h before.",
            refundable_until_hours_before=48,
            forfeit_percent=100,
            created_by=STAFF_ID,
            created_at=datetime.datetime(2026, 7, 22, 12, 0, tzinfo=datetime.UTC),
        )

    def _record(self, method: str, /, **kwargs: Any) -> None:
        self.calls.append((method, kwargs))
        exc = self.raise_on.get(method)
        if exc is not None:
            raise exc

    def call(self, method: str) -> dict[str, Any]:
        matches = [kwargs for called, kwargs in self.calls if called == method]
        assert len(matches) == 1, f"expected exactly one {method} call, saw {self.calls}"
        return matches[0]

    async def get_settings(self, tenant_id: uuid.UUID) -> SettingsResult:
        self._record("get_settings", tenant_id=tenant_id)
        return self.settings_result

    async def update_settings(
        self,
        tenant_id: uuid.UUID,
        *,
        profile: dict[str, Any] | None = None,
        toggles: dict[str, Any] | None = None,
    ) -> SettingsResult:
        self._record("update_settings", tenant_id=tenant_id, profile=profile, toggles=toggles)
        return self.settings_result

    async def list_appointment_types(self, tenant_id: uuid.UUID) -> list[Any]:
        self._record("list_appointment_types", tenant_id=tenant_id)
        return [self.type_row]

    async def create_appointment_type(self, tenant_id: uuid.UUID, **kwargs: Any) -> Any:
        self._record("create_appointment_type", tenant_id=tenant_id, **kwargs)
        return self.type_row

    async def update_appointment_type(
        self, tenant_id: uuid.UUID, type_id: uuid.UUID, **kwargs: Any
    ) -> Any:
        self._record("update_appointment_type", tenant_id=tenant_id, type_id=type_id, **kwargs)
        return self.type_row

    async def archive_appointment_type(self, tenant_id: uuid.UUID, type_id: uuid.UUID) -> None:
        self._record("archive_appointment_type", tenant_id=tenant_id, type_id=type_id)

    async def get_availability(self, tenant_id: uuid.UUID) -> AvailabilityResult:
        self._record("get_availability", tenant_id=tenant_id)
        return AvailabilityResult(rules=[self.rule_row], exceptions=[self.exception_row])

    async def replace_weekly_rules(
        self, tenant_id: uuid.UUID, rules: list[WeeklyRuleInput]
    ) -> list[Any]:
        self._record("replace_weekly_rules", tenant_id=tenant_id, rules=rules)
        return [self.rule_row]

    async def add_availability_exception(self, tenant_id: uuid.UUID, **kwargs: Any) -> Any:
        self._record("add_availability_exception", tenant_id=tenant_id, **kwargs)
        return self.exception_row

    async def remove_availability_exception(
        self, tenant_id: uuid.UUID, exception_id: uuid.UUID
    ) -> None:
        self._record(
            "remove_availability_exception", tenant_id=tenant_id, exception_id=exception_id
        )

    async def create_terms_version(self, tenant_id: uuid.UUID, **kwargs: Any) -> Any:
        self._record("create_terms_version", tenant_id=tenant_id, **kwargs)
        return self.terms_row

    async def get_terms_history(
        self, tenant_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> TermsHistoryResult:
        self._record("get_terms_history", tenant_id=tenant_id, offset=offset, limit=limit)
        return TermsHistoryResult(
            current=self.terms_row, versions=[self.terms_row], total=1, offset=offset, limit=limit
        )


def _client(fake: FakeBoutiqueService, *, authed: bool = True) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.state.boutique_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- authentication guard ---


def test_every_route_requires_authentication() -> None:
    fake = FakeBoutiqueService()
    with _client(fake, authed=False) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []  # the guard fires before any service call


# --- settings ---


def test_get_settings_returns_profile_and_toggles() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.get("/manage/settings")
    assert resp.status_code == 200
    assert resp.json() == {
        "profile": {"phone": "+972-3-555-0100"},
        "toggles": {"deposits_enabled": True},
    }
    assert fake.call("get_settings") == {"tenant_id": TENANT.id}


def test_put_settings_passes_only_provided_keys() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.put(
            "/manage/settings",
            json={"profile": {"phone": "+972-3-555-0100"}, "toggles": {"brides_only": True}},
        )
    assert resp.status_code == 200
    call = fake.call("update_settings")
    # Unset fields must NOT be sent as explicit keys — the JSONB merge replaces
    # whole top-level keys, and the service treats absent keys as untouched.
    assert call["profile"] == {"phone": "+972-3-555-0100"}
    assert call["toggles"] == {"brides_only": True}


def test_put_settings_toggles_only_leaves_profile_none() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.put("/manage/settings", json={"toggles": {"deposits_enabled": False}})
    assert resp.status_code == 200
    call = fake.call("update_settings")
    assert call["profile"] is None
    assert call["toggles"] == {"deposits_enabled": False}


def test_put_settings_rejects_unknown_profile_key() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.put("/manage/settings", json={"profile": {"evil": "x"}})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"]
    assert fake.calls == []


def test_put_settings_rejects_unknown_top_level_key() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.put("/manage/settings", json={"secrets": {"a": 1}})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_domain_validation_error_maps_to_house_shape_400() -> None:
    fake = FakeBoutiqueService()
    fake.raise_on["update_settings"] = BoutiqueValidationError(
        "maps_url must be an absolute http(s) URL"
    )
    with _client(fake) as client:
        resp = client.put("/manage/settings", json={"profile": {"maps_url": "javascript:alert(1)"}})
    assert resp.status_code == 400
    assert resp.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "maps_url must be an absolute http(s) URL",
        }
    }


# --- appointment types ---


def test_list_appointment_types() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.get("/manage/appointment-types")
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "id": str(TYPE_ID),
            "name": "Fitting",
            "duration_minutes": 60,
            "audience": "all",
            "deposit_required": False,
            "deposit_amount_agorot": None,
            "sort_order": 0,
        }
    ]


def test_create_appointment_type_applies_defaults() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post("/manage/appointment-types", json=TYPE_CREATE_BODY)
    assert resp.status_code == 200
    assert fake.call("create_appointment_type") == {
        "tenant_id": TENANT.id,
        "name": "Fitting",
        "duration_minutes": 60,
        "audience": "all",
        "deposit_required": False,
        "deposit_amount_agorot": None,
        "sort_order": 0,
    }


def test_create_appointment_type_rejects_out_of_bounds_duration() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post(
            "/manage/appointment-types", json={"name": "Fitting", "duration_minutes": 0}
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_duplicate_type_name_maps_to_409() -> None:
    fake = FakeBoutiqueService()
    fake.raise_on["create_appointment_type"] = DuplicateNameError()
    with _client(fake) as client:
        resp = client.post("/manage/appointment-types", json=TYPE_CREATE_BODY)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_NAME"


def test_update_appointment_type_requires_full_body_and_passes_id() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.patch(f"/manage/appointment-types/{TYPE_ID}", json=TYPE_UPDATE_BODY)
    assert resp.status_code == 200
    call = fake.call("update_appointment_type")
    assert call["type_id"] == TYPE_ID
    assert call["deposit_amount_agorot"] == 15000

    with _client(FakeBoutiqueService()) as client:
        partial = client.patch(f"/manage/appointment-types/{TYPE_ID}", json={"name": "X"})
    assert partial.status_code == 400  # full-replace semantics: all fields required


def test_archive_appointment_type_returns_ok() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.delete(f"/manage/appointment-types/{TYPE_ID}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert fake.call("archive_appointment_type")["type_id"] == TYPE_ID


def test_archive_missing_type_maps_to_404() -> None:
    fake = FakeBoutiqueService()
    fake.raise_on["archive_appointment_type"] = NotFoundError()
    with _client(fake) as client:
        resp = client.delete(f"/manage/appointment-types/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --- availability ---


def test_get_availability_returns_rules_and_exceptions() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.get("/manage/availability")
    assert resp.status_code == 200
    assert resp.json() == {
        "rules": [
            {
                "id": str(RULE_ID),
                "day_of_week": 0,
                "open_time": "09:00:00",
                "close_time": "17:00:00",
                "capacity": 1,
            }
        ],
        "exceptions": [
            {
                "id": str(EXCEPTION_ID),
                "date": "2026-08-01",
                "open_time": None,
                "close_time": None,
                "note": "Holiday",
            }
        ],
    }


def test_replace_weekly_rules_converts_to_inputs() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.put("/manage/availability/rules", json=RULES_BODY)
    assert resp.status_code == 200
    call = fake.call("replace_weekly_rules")
    assert call["rules"] == [
        WeeklyRuleInput(
            day_of_week=0,
            open_time=datetime.time(9, 0),
            close_time=datetime.time(17, 0),
            capacity=1,
        )
    ]


def test_replace_weekly_rules_rejects_bad_day() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.put(
            "/manage/availability/rules",
            json={"rules": [{"day_of_week": 7, "open_time": "09:00", "close_time": "17:00"}]},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_add_exception_closed_all_day() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post("/manage/availability/exceptions", json=EXCEPTION_BODY)
    assert resp.status_code == 200
    call = fake.call("add_availability_exception")
    assert call["date"] == datetime.date(2026, 8, 1)
    assert call["open_time"] is None and call["close_time"] is None
    assert call["note"] == "Holiday"


def test_duplicate_exception_date_maps_to_409() -> None:
    fake = FakeBoutiqueService()
    fake.raise_on["add_availability_exception"] = DuplicateDateError()
    with _client(fake) as client:
        resp = client.post("/manage/availability/exceptions", json=EXCEPTION_BODY)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_DATE"


def test_remove_exception_returns_ok() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.delete(f"/manage/availability/exceptions/{EXCEPTION_ID}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert fake.call("remove_availability_exception")["exception_id"] == EXCEPTION_ID


# --- terms ---


def test_get_terms_defaults_to_first_page_of_50() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.get("/manage/terms")
    assert resp.status_code == 200
    body = resp.json()
    assert body["current"]["version"] == 1
    assert body["total"] == 1
    assert fake.call("get_terms_history") == {"tenant_id": TENANT.id, "offset": 0, "limit": 50}


def test_get_terms_passes_pagination_params() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.get("/manage/terms", params={"offset": 10, "limit": 5})
    assert resp.status_code == 200
    assert fake.call("get_terms_history") == {"tenant_id": TENANT.id, "offset": 10, "limit": 5}


def test_get_terms_rejects_out_of_range_pagination() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        for params in ({"offset": -1}, {"limit": 0}, {"limit": 51}):
            resp = client.get("/manage/terms", params=params)
            assert resp.status_code == 400, params
            assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_create_terms_stamps_created_by_from_session() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post("/manage/terms", json=TERMS_BODY)
    assert resp.status_code == 200
    assert fake.call("create_terms_version") == {
        "tenant_id": TENANT.id,
        "terms_text": "Cancel 48h before.",
        "refundable_until_hours_before": 48,
        "forfeit_percent": 100,
        "created_by": STAFF_ID,
    }
    assert resp.json()["version"] == 1


def test_terms_version_race_maps_to_409_conflict() -> None:
    fake = FakeBoutiqueService()
    fake.raise_on["create_terms_version"] = TermsVersionConflictError()
    with _client(fake) as client:
        resp = client.post("/manage/terms", json=TERMS_BODY)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_terms_throttle_maps_to_429() -> None:
    fake = FakeBoutiqueService()
    fake.raise_on["create_terms_version"] = TermsThrottledError()
    with _client(fake) as client:
        resp = client.post("/manage/terms", json=TERMS_BODY)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


# --- CSRF origin middleware ---


def test_mutating_request_with_mismatched_origin_is_403() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post(
            "/manage/appointment-types",
            json=TYPE_CREATE_BODY,
            headers={"origin": "http://evil.localtest.me"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.calls == []


def test_matching_origin_is_allowed_even_with_different_port() -> None:
    # The Vite dev proxy preserves Host, so the browser Origin carries :5173 —
    # the check compares hostnames, not ports.
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post(
            "/manage/appointment-types",
            json=TYPE_CREATE_BODY,
            headers={"origin": "http://bella.localtest.me:5173"},
        )
    assert resp.status_code == 200


def test_absent_origin_is_allowed() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post("/manage/appointment-types", json=TYPE_CREATE_BODY)
    assert resp.status_code == 200


def test_null_origin_is_rejected() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post(
            "/manage/appointment-types", json=TYPE_CREATE_BODY, headers={"origin": "null"}
        )
    assert resp.status_code == 403


def test_read_request_with_mismatched_origin_is_allowed() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.get("/manage/settings", headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 200


def test_auth_login_is_csrf_protected_too() -> None:
    fake = FakeBoutiqueService()
    with _client(fake, authed=False) as client:
        resp = client.post(
            "/manage/auth/login",
            json={"email": "owner@bella.example", "password": "pw"},
            headers={"origin": "http://evil.localtest.me"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"


# --- house-shape request validation (intentionally also covers auth routes) ---


def test_malformed_auth_login_body_is_house_shape_400() -> None:
    fake = FakeBoutiqueService()
    with _client(fake, authed=False) as client:
        resp = client.post("/manage/auth/login", json={"email": "owner@bella.example"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "password" in body["error"]["message"]


def test_invalid_json_body_is_house_shape_400() -> None:
    fake = FakeBoutiqueService()
    with _client(fake) as client:
        resp = client.post(
            "/manage/appointment-types",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
