"""Feature 8 fast API tests: route wiring, 401s, house-shape validation 400s,
the complete error-code table, storage degradation and the two key call-site
invariants — fake service + InMemoryMediaStorage + a hardcoded TenantContext,
no database (test_boutique_api.py style).

The error-code table is the load-bearing part. Starlette resolves handlers by
walking `type(exc).__mro__`, so a handler left bound to a concrete boutique class
turns every catalog 404 and domain-400 into an unhandled 500. Asserting each code
against its exact status and house shape is the only thing that catches it.
"""

import dataclasses
import datetime
import time
import uuid
from typing import Any

import pytest
from botocore.exceptions import NoCredentialsError
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.catalog.keys import build_media_key
from app.catalog.router import get_media_storage
from app.catalog.service import (
    CatalogNotFoundError,
    DressListResult,
    DressView,
    DuplicateSizeError,
    MediaLimitReachedError,
    MediaMismatchError,
    MediaNotUploadedError,
    MediaOrderMismatchError,
    MediaPresignThrottledError,
    MediaView,
    PresignResult,
    StockSummary,
)
from app.catalog.validation import (
    PRESIGN_TTL_SECONDS,
    CatalogValidationError,
    VariantInput,
)
from app.core.config import Settings
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.dress import Dress
from app.models.dress_media import DressMedia
from app.models.dress_variant import DressVariant
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorage,
    MediaStorageUnavailableError,
)
from app.storage.memory import InMemoryMediaStorage
from app.storage.s3 import S3MediaStorage
from app.storage.unconfigured import UnconfiguredMediaStorage
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

DRESS_ID = uuid.uuid4()
VARIANT_ID = uuid.uuid4()
MEDIA_ID = uuid.uuid4()

JPEG = "image/jpeg"
STORAGE_KEY = f"tenants/{TENANT.id}/dresses/{DRESS_ID}/media/{MEDIA_ID}.jpg"
SIGNED_URL = f"https://media.test/{STORAGE_KEY}?X-Amz-Signature=abc"

CREATED_AT = datetime.datetime(2026, 7, 24, 10, 0, tzinfo=datetime.UTC)
UPDATED_AT = datetime.datetime(2026, 7, 24, 11, 30, tzinfo=datetime.UTC)
URL_EXPIRES_AT = datetime.datetime(2026, 7, 24, 10, 15, tzinfo=datetime.UTC)

DRESS_CREATE_BODY = {"name": "Aurora"}
DRESS_UPDATE_BODY: dict[str, Any] = {
    "name": "Aurora",
    "description": "Silk A-line",
    "price_agorot": 120_000,
    "price_visible": True,
    "reserved": False,
    "sort_order": 3,
}
VARIANTS_BODY = {"variants": [{"size_label": " 38 ", "quantity": 2}]}
PRESIGN_BODY = {"content_type": JPEG, "byte_size": 4096}
REORDER_BODY = {"media_ids": [str(MEDIA_ID)]}

LIST_PATH = "/manage/dresses"
DETAIL_PATH = f"/manage/dresses/{DRESS_ID}"
RESTORE_PATH = f"/manage/dresses/{DRESS_ID}/restore"
VARIANTS_PATH = f"/manage/dresses/{DRESS_ID}/variants"
PRESIGN_PATH = f"/manage/dresses/{DRESS_ID}/media/presign"
CONFIRM_PATH = f"/manage/dresses/{DRESS_ID}/media/{MEDIA_ID}/confirm"
MEDIA_PATH = f"/manage/dresses/{DRESS_ID}/media/{MEDIA_ID}"
ORDER_PATH = f"/manage/dresses/{DRESS_ID}/media/order"

# Every /manage route this feature adds, with a body that passes schema
# validation — so 401 (and CSRF) failures are attributable to the guard alone.
# Both routers mount prefix="/manage", so a duplicated path would silently
# shadow: this table is the wiring guard, not decoration.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", LIST_PATH, None),
    ("POST", LIST_PATH, DRESS_CREATE_BODY),
    ("GET", DETAIL_PATH, None),
    ("PATCH", DETAIL_PATH, DRESS_UPDATE_BODY),
    ("DELETE", DETAIL_PATH, None),
    ("POST", RESTORE_PATH, None),
    ("PUT", VARIANTS_PATH, VARIANTS_BODY),
    ("POST", PRESIGN_PATH, PRESIGN_BODY),
    ("POST", CONFIRM_PATH, None),
    ("DELETE", MEDIA_PATH, None),
    ("PUT", ORDER_PATH, REORDER_BODY),
]

# The spec's error table, verbatim. test_every_spec_error_code_is_asserted
# checks this set against what the module actually exercises, so adding a row to
# the spec without a test here fails CI.
SPEC_ERROR_CODES = {
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "DUPLICATE_SIZE",
    "MEDIA_LIMIT_REACHED",
    "MEDIA_NOT_UPLOADED",
    "MEDIA_MISMATCH",
    "MEDIA_ORDER_MISMATCH",
    "MEDIA_NOT_CONFIGURED",
    "MEDIA_STORAGE_UNAVAILABLE",
    "TOO_MANY_ATTEMPTS",
    "NOT_AUTHENTICATED",
    "CSRF_ORIGIN_MISMATCH",
    "NOT_AUTHORIZED",
}


def _dress_row(*, archived: bool = False) -> Dress:
    return Dress(
        id=DRESS_ID,
        tenant_id=TENANT.id,
        name="Aurora",
        description="Silk A-line",
        price_agorot=120_000,
        price_visible=True,
        reserved=False,
        sort_order=3,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
        deleted_at=CREATED_AT if archived else None,
    )


def _variant_row() -> DressVariant:
    return DressVariant(
        id=VARIANT_ID,
        tenant_id=TENANT.id,
        dress_id=DRESS_ID,
        size_label="38",
        quantity=2,
        sort_order=0,
        created_at=CREATED_AT,
    )


def _media_row() -> DressMedia:
    return DressMedia(
        id=MEDIA_ID,
        tenant_id=TENANT.id,
        dress_id=DRESS_ID,
        storage_key=STORAGE_KEY,
        content_type=JPEG,
        byte_size=4096,
        status="ready",
        sort_order=0,
        created_at=CREATED_AT,
    )


def _media_view(*, url: str | None = SIGNED_URL) -> MediaView:
    return MediaView(
        row=_media_row(),
        url=url,
        url_expires_at=URL_EXPIRES_AT if url is not None else None,
    )


def _dress_view(
    *,
    url: str | None = SIGNED_URL,
    uploads_enabled: bool = True,
    archived: bool = False,
    detail: bool = True,
) -> DressView:
    media = [_media_view(url=url)]
    return DressView(
        row=_dress_row(archived=archived),
        summary=StockSummary(variant_count=1, total_quantity=2, out_of_stock=False),
        media_count=1,
        cover=media[0],
        uploads_enabled=uploads_enabled,
        slots_remaining=11,
        variants=[_variant_row()] if detail else [],
        media=media if detail else [],
    )


MEDIA_JSON: dict[str, Any] = {
    "id": str(MEDIA_ID),
    "sort_order": 0,
    "content_type": JPEG,
    "byte_size": 4096,
    "url": SIGNED_URL,
    "url_expires_at": "2026-07-24T10:15:00Z",
}
DRESS_JSON: dict[str, Any] = {
    "id": str(DRESS_ID),
    "name": "Aurora",
    "description": "Silk A-line",
    "price_agorot": 120_000,
    "price_visible": True,
    "reserved": False,
    "sort_order": 3,
    "out_of_stock": False,
    "total_quantity": 2,
    "variant_count": 1,
    "media_count": 1,
    "cover": MEDIA_JSON,
    "archived": False,
    "created_at": "2026-07-24T10:00:00Z",
    "updated_at": "2026-07-24T11:30:00Z",
}
DETAIL_JSON: dict[str, Any] = {
    **DRESS_JSON,
    "variants": [{"id": str(VARIANT_ID), "size_label": "38", "quantity": 2, "sort_order": 0}],
    "media": [MEDIA_JSON],
    "media_uploads_enabled": True,
    "media_slots_remaining": 11,
}


class FakeAuthService:
    def __init__(self, role: str = "owner") -> None:
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=TENANT.id,
            email="owner@bella.example",
            display_name="Owner",
            role=role,
        )

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


class FakeCatalogService:
    """Duck-typed CatalogService: records every call, raises on demand, returns
    canned frozen views over ORM rows (instantiable without a database).

    `storage` is optional and, when present, the presign path delegates to it
    exactly as the real service does — that composition is what turns a botocore
    NoCredentialsError into MediaNotConfiguredError, and the 503 must survive it.
    """

    def __init__(self, *, storage: MediaStorage | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.raise_on: dict[str, Exception] = {}
        self.storage = storage
        self.view = _dress_view()

    def _record(self, method: str, /, **kwargs: Any) -> None:
        self.calls.append((method, kwargs))
        exc = self.raise_on.get(method)
        if exc is not None:
            raise exc

    def call(self, method: str) -> dict[str, Any]:
        matches = [kwargs for called, kwargs in self.calls if called == method]
        assert len(matches) == 1, f"expected exactly one {method} call, saw {self.calls}"
        return matches[0]

    def called(self, method: str) -> int:
        return sum(1 for name, _ in self.calls if name == method)

    async def list_dresses(
        self,
        tenant_id: uuid.UUID,
        *,
        archived: bool = False,
        search: str | None = None,
        offset: int = 0,
        limit: int = 24,
    ) -> DressListResult:
        self._record(
            "list_dresses",
            tenant_id=tenant_id,
            archived=archived,
            search=search,
            offset=offset,
            limit=limit,
        )
        return DressListResult(
            items=[_dress_view(detail=False)], total=1, offset=offset, limit=limit
        )

    async def create_dress(self, tenant_id: uuid.UUID, **kwargs: Any) -> DressView:
        self._record("create_dress", tenant_id=tenant_id, **kwargs)
        return self.view

    async def get_dress(self, tenant_id: uuid.UUID, dress_id: uuid.UUID) -> DressView:
        self._record("get_dress", tenant_id=tenant_id, dress_id=dress_id)
        return self.view

    async def update_dress(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, **kwargs: Any
    ) -> DressView:
        self._record("update_dress", tenant_id=tenant_id, dress_id=dress_id, **kwargs)
        return self.view

    async def archive_dress(self, tenant_id: uuid.UUID, dress_id: uuid.UUID) -> None:
        self._record("archive_dress", tenant_id=tenant_id, dress_id=dress_id)

    async def restore_dress(self, tenant_id: uuid.UUID, dress_id: uuid.UUID) -> DressView:
        self._record("restore_dress", tenant_id=tenant_id, dress_id=dress_id)
        return self.view

    async def replace_variants(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, variants: list[VariantInput]
    ) -> DressView:
        self._record("replace_variants", tenant_id=tenant_id, dress_id=dress_id, variants=variants)
        return self.view

    async def presign_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, *, content_type: str, byte_size: int
    ) -> PresignResult:
        self._record(
            "presign_media",
            tenant_id=tenant_id,
            dress_id=dress_id,
            content_type=content_type,
            byte_size=byte_size,
        )
        key = build_media_key(
            tenant_id=tenant_id, dress_id=dress_id, media_id=MEDIA_ID, content_type=content_type
        )
        if self.storage is not None:
            self.storage.presigned_post(
                key=key,
                content_type=content_type,
                exact_bytes=byte_size,
                expires_in=PRESIGN_TTL_SECONDS,
            )
        return PresignResult(
            media_id=MEDIA_ID,
            url="https://media.test/upload",
            fields={"key": key, "Content-Type": content_type, "x-amz-signature": "sig"},
            expires_in=PRESIGN_TTL_SECONDS,
            max_bytes=byte_size,
        )

    async def confirm_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_id: uuid.UUID
    ) -> DressView:
        self._record("confirm_media", tenant_id=tenant_id, dress_id=dress_id, media_id=media_id)
        return self.view

    async def delete_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_id: uuid.UUID
    ) -> DressView:
        self._record("delete_media", tenant_id=tenant_id, dress_id=dress_id, media_id=media_id)
        return self.view

    async def reorder_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_ids: list[uuid.UUID]
    ) -> DressView:
        self._record("reorder_media", tenant_id=tenant_id, dress_id=dress_id, media_ids=media_ids)
        return self.view


def _client(
    fake: FakeCatalogService,
    *,
    authed: bool = True,
    storage: MediaStorage | None = None,
    role: str = "owner",
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.state.catalog_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    # Always substituted: create_app() picks its storage from the ambient .env,
    # so without this the media routes would answer 503 or not depending on
    # whose machine runs the suite.
    resolved = storage if storage is not None else InMemoryMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: resolved
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring + authentication guard ---


def test_every_route_requires_authentication() -> None:
    fake = FakeCatalogService()
    with _client(fake, authed=False) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []  # the guard fires before any service call


def test_an_unadmitted_role_is_403_on_every_route() -> None:
    """The catalog router's default posture is require_role(OWNER, SHIFT_MANAGER),
    so a role the enum does not know fails closed on every route with the ONE
    generic body (no role names on the wire). This is what earns NOT_AUTHORIZED
    its row in SPEC_ERROR_CODES — without it the set was a claim, not a test.
    The admitted-role side of the matrix lives in test_staff_role_gating.py."""
    fake = FakeCatalogService()
    with _client(fake, role="reception") as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
            assert resp.json() == NOT_AUTHORIZED_BODY
    assert fake.calls == []  # the gate fires before any service call


def test_every_route_is_wired_and_reaches_the_service() -> None:
    """The boutique and catalog routers both mount prefix="/manage": a path
    collision would silently shadow, and a 404 here is what catches it."""
    for method, path, body in ROUTES:
        fake = FakeCatalogService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert fake.calls, f"{method} {path} never reached the service"


# --- dresses ---


def test_list_dresses_applies_the_documented_defaults() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.get(LIST_PATH)
    assert resp.status_code == 200
    # Spelled out because Feature 7's default==max shortcut does not generalise.
    assert fake.call("list_dresses") == {
        "tenant_id": TENANT.id,
        "archived": False,
        "search": None,
        "offset": 0,
        "limit": 24,
    }
    body = resp.json()
    assert body["total"] == 1
    assert body["items"] == [DRESS_JSON]


def test_list_dresses_passes_paging_search_and_archive_filter() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.get(
            LIST_PATH, params={"offset": 24, "limit": 100, "search": "aurora", "archived": True}
        )
    assert resp.status_code == 200
    assert fake.call("list_dresses") == {
        "tenant_id": TENANT.id,
        "archived": True,
        "search": "aurora",
        "offset": 24,
        "limit": 100,
    }


def test_list_dresses_rejects_out_of_range_paging_and_over_long_search() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        for params in ({"offset": -1}, {"limit": 0}, {"limit": 101}, {"search": "x" * 101}):
            resp = client.get(LIST_PATH, params=params)
            assert resp.status_code == 400, params
            assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_create_dress_applies_defaults() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.post(LIST_PATH, json=DRESS_CREATE_BODY)
    assert resp.status_code == 200
    assert fake.call("create_dress") == {
        "tenant_id": TENANT.id,
        "name": "Aurora",
        "description": None,
        "price_agorot": None,
        "price_visible": True,
        "reserved": False,
        "sort_order": 0,
    }
    assert resp.json() == DRESS_JSON


def test_create_dress_rejects_an_out_of_range_price() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.post(LIST_PATH, json={"name": "Aurora", "price_agorot": 0})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_get_dress_returns_the_full_detail_shape() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.get(DETAIL_PATH)
    assert resp.status_code == 200
    assert resp.json() == DETAIL_JSON
    assert fake.call("get_dress") == {"tenant_id": TENANT.id, "dress_id": DRESS_ID}


def test_update_dress_requires_every_field() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.patch(DETAIL_PATH, json=DRESS_UPDATE_BODY)
    assert resp.status_code == 200
    call = fake.call("update_dress")
    assert call["dress_id"] == DRESS_ID
    assert call["price_agorot"] == 120_000

    # Full-replace semantics: the nullable scalars are required WITH NO DEFAULT.
    # Copying CreateDressRequest's default=None into the update model would let
    # an omitted key silently clear a value — the exact bug this rule exists for.
    omissions: list[dict[str, Any]] = [{"name": "Aurora"}]
    omissions += [
        {key: value for key, value in DRESS_UPDATE_BODY.items() if key != omitted}
        for omitted in DRESS_UPDATE_BODY
    ]
    for partial in omissions:
        with _client(FakeCatalogService()) as client:
            resp = client.patch(DETAIL_PATH, json=partial)
        assert resp.status_code == 400, partial


def test_update_dress_accepts_explicit_nulls() -> None:
    fake = FakeCatalogService()
    body = {**DRESS_UPDATE_BODY, "description": None, "price_agorot": None}
    with _client(fake) as client:
        resp = client.patch(DETAIL_PATH, json=body)
    assert resp.status_code == 200
    call = fake.call("update_dress")
    assert call["description"] is None
    assert call["price_agorot"] is None


def test_archive_dress_returns_ok() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.delete(DETAIL_PATH)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert fake.call("archive_dress") == {"tenant_id": TENANT.id, "dress_id": DRESS_ID}


def test_restore_dress_returns_the_detail_view() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.post(RESTORE_PATH)
    assert resp.status_code == 200
    assert resp.json() == DETAIL_JSON


# --- variants ---


def test_replace_variants_converts_to_inputs() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.put(VARIANTS_PATH, json=VARIANTS_BODY)
    assert resp.status_code == 200
    call = fake.call("replace_variants")
    # The router transports the raw label; normalisation is the service's job.
    assert call["variants"] == [VariantInput(size_label=" 38 ", quantity=2, sort_order=0)]
    assert resp.json() == DETAIL_JSON


def test_replace_variants_rejects_an_over_long_matrix() -> None:
    fake = FakeCatalogService()
    body = {"variants": [{"size_label": str(size), "quantity": 1} for size in range(61)]}
    with _client(fake) as client:
        resp = client.put(VARIANTS_PATH, json=body)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_replace_variants_rejects_an_out_of_range_quantity() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.put(VARIANTS_PATH, json={"variants": [{"size_label": "38", "quantity": -1}]})
    assert resp.status_code == 400
    assert fake.calls == []


# --- media ---


def test_presign_key_comes_from_the_resolved_tenant_never_the_body() -> None:
    """tenant_id is host-derived and dress_id comes from the URL: no field the
    client can send influences the key."""
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.post(PRESIGN_PATH, json=PRESIGN_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["fields"]["key"].startswith(f"tenants/{TENANT.id}/")
    assert body["fields"]["key"] == STORAGE_KEY
    assert body["media_id"] == str(MEDIA_ID)
    assert body["expires_in"] == PRESIGN_TTL_SECONDS
    assert body["max_bytes"] == 4096


@pytest.mark.parametrize("field", ["key", "storage_key", "tenant_id"])
def test_presign_rejects_a_body_that_tries_to_influence_the_key(field: str) -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.post(PRESIGN_PATH, json={**PRESIGN_BODY, field: "tenants/evil/x.jpg"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_presign_rejects_a_byte_size_outside_the_declared_bounds() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        for byte_size in (1023, 10_485_761):
            resp = client.post(PRESIGN_PATH, json={**PRESIGN_BODY, "byte_size": byte_size})
            assert resp.status_code == 400, byte_size
            assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_confirm_is_idempotent_over_the_wire() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        first = client.post(CONFIRM_PATH)
        second = client.post(CONFIRM_PATH)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == DETAIL_JSON
    assert fake.called("confirm_media") == 2


def test_storage_outage_on_confirm_is_503_not_409() -> None:
    """503 MEDIA_STORAGE_UNAVAILABLE, not 409 — MediaGallery deliberately does
    NOT call deleteMedia on a 503 and re-confirms the same media_id on retry.

    Scope: this asserts the status and the house body only. That the ROW
    survives the outage and stays confirmable is a service-level property the
    route cannot observe — confirm_media is the only call this handler makes, so
    an assertion here that delete_media was not called would hold no matter what
    the service did. It is proven for real in test_catalog_integration.py's
    test_storage_outage_on_confirm_leaves_the_row_confirmable.
    """
    fake = FakeCatalogService()
    fake.raise_on["confirm_media"] = MediaStorageUnavailableError()
    with _client(fake) as client:
        resp = client.post(CONFIRM_PATH)
    assert resp.status_code == 503
    assert resp.json() == {
        "error": {
            "code": "MEDIA_STORAGE_UNAVAILABLE",
            "message": "Image storage is temporarily unavailable.",
        }
    }


def test_delete_media_returns_the_detail_view() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.delete(MEDIA_PATH)
    assert resp.status_code == 200
    assert fake.call("delete_media") == {
        "tenant_id": TENANT.id,
        "dress_id": DRESS_ID,
        "media_id": MEDIA_ID,
    }


def test_reorder_media_passes_the_permutation() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.put(ORDER_PATH, json=REORDER_BODY)
    assert resp.status_code == 200
    assert fake.call("reorder_media")["media_ids"] == [MEDIA_ID]


def test_reorder_media_rejects_more_ids_than_the_gallery_can_hold() -> None:
    fake = FakeCatalogService()
    body = {"media_ids": [str(uuid.uuid4()) for _ in range(13)]}
    with _client(fake) as client:
        resp = client.put(ORDER_PATH, json=body)
    assert resp.status_code == 400
    assert fake.calls == []


# --- Cache-Control ---


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [pytest.param(*route, id=f"{route[0].lower()}-{route[1]}") for route in ROUTES],
)
def test_signed_url_carrying_responses_are_never_cached(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Signed URLs and POST-policy fields are bearer material for their whole
    TTL — they must not reach a shared cache or a bfcache entry.

    Parametrized over the WHOLE route table rather than the three routes that
    happened to set the header: nine of these answer with a DressResponse or a
    DressDetailResponse carrying `cover.url` / `media[].url`, so enumerating
    them by hand is how six of them were missed. Driving it from ROUTES means a
    route added later cannot ship without the header.
    """
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- storage degradation ---


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        pytest.param("POST", PRESIGN_PATH, PRESIGN_BODY, id="presign"),
        pytest.param("POST", CONFIRM_PATH, None, id="confirm"),
        pytest.param("DELETE", MEDIA_PATH, None, id="delete"),
    ],
)
def test_media_writes_are_503_without_a_bucket(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    fake = FakeCatalogService()
    with _client(fake, storage=UnconfiguredMediaStorage()) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 503
    assert resp.json() == {
        "error": {"code": "MEDIA_NOT_CONFIGURED", "message": "Image uploads are not available."}
    }
    # Refused before any database work: a row we write can never be uploaded
    # against when there is no bucket.
    assert fake.calls == []


def test_reads_and_dress_writes_keep_working_without_a_bucket() -> None:
    """The whole catalog stays usable with no bucket: only the media WRITE
    endpoints answer 503, and reads serialise a null url."""
    fake = FakeCatalogService()
    fake.view = _dress_view(url=None, uploads_enabled=False)
    with _client(fake, storage=UnconfiguredMediaStorage()) as client:
        detail = client.get(DETAIL_PATH)
        created = client.post(LIST_PATH, json=DRESS_CREATE_BODY)
        reordered = client.put(ORDER_PATH, json=REORDER_BODY)
    assert created.status_code == 200
    assert reordered.status_code == 200
    assert detail.status_code == 200
    body = detail.json()
    assert body["media"] == [{**MEDIA_JSON, "url": None, "url_expires_at": None}]
    assert body["cover"] == {**MEDIA_JSON, "url": None, "url_expires_at": None}
    assert body["media_uploads_enabled"] is False


def test_presign_with_unusable_credentials_is_503_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bucket with no usable credentials is operationally identical to no
    bucket — the exact state F8 ships into. The port maps NoCredentialsError to
    MediaNotConfiguredError, and the composition must answer 503, never 500."""

    class _NoCredentialsClient:
        def generate_presigned_post(self, **kwargs: Any) -> dict[str, Any]:
            raise NoCredentialsError

    monkeypatch.setattr(
        "app.storage.s3.boto3.client", lambda *args, **kwargs: _NoCredentialsClient()
    )
    storage = S3MediaStorage(
        Settings(app_env="dev", media_bucket="boutique-media", media_region="il-central-1")
    )
    fake = FakeCatalogService(storage=storage)
    with _client(fake, storage=storage) as client:
        resp = client.post(PRESIGN_PATH, json=PRESIGN_BODY)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MEDIA_NOT_CONFIGURED"


# --- the complete error-code table ---


@dataclasses.dataclass(frozen=True)
class ErrorCase:
    """One row of the spec's error table: the service method that raises, the
    route that reaches it, and the status + code the handler must produce."""

    method_name: str
    verb: str
    path: str
    body: dict[str, Any] | None
    error: Exception
    status: int
    code: str


ERROR_CASES: list[ErrorCase] = [
    ErrorCase(
        "presign_media",
        "POST",
        PRESIGN_PATH,
        PRESIGN_BODY,
        CatalogValidationError("byte_size is out of bounds"),
        400,
        "VALIDATION_ERROR",
    ),
    ErrorCase("get_dress", "GET", DETAIL_PATH, None, CatalogNotFoundError(), 404, "NOT_FOUND"),
    ErrorCase(
        "replace_variants",
        "PUT",
        VARIANTS_PATH,
        VARIANTS_BODY,
        DuplicateSizeError(),
        409,
        "DUPLICATE_SIZE",
    ),
    ErrorCase(
        "presign_media",
        "POST",
        PRESIGN_PATH,
        PRESIGN_BODY,
        MediaLimitReachedError(),
        409,
        "MEDIA_LIMIT_REACHED",
    ),
    ErrorCase(
        "confirm_media",
        "POST",
        CONFIRM_PATH,
        None,
        MediaNotUploadedError(),
        409,
        "MEDIA_NOT_UPLOADED",
    ),
    ErrorCase(
        "confirm_media", "POST", CONFIRM_PATH, None, MediaMismatchError(), 409, "MEDIA_MISMATCH"
    ),
    ErrorCase(
        "reorder_media",
        "PUT",
        ORDER_PATH,
        REORDER_BODY,
        MediaOrderMismatchError(),
        409,
        "MEDIA_ORDER_MISMATCH",
    ),
    ErrorCase(
        "presign_media",
        "POST",
        PRESIGN_PATH,
        PRESIGN_BODY,
        MediaNotConfiguredError(),
        503,
        "MEDIA_NOT_CONFIGURED",
    ),
    ErrorCase(
        "confirm_media",
        "POST",
        CONFIRM_PATH,
        None,
        MediaStorageUnavailableError(),
        503,
        "MEDIA_STORAGE_UNAVAILABLE",
    ),
    ErrorCase(
        "presign_media",
        "POST",
        PRESIGN_PATH,
        PRESIGN_BODY,
        MediaPresignThrottledError(),
        429,
        "TOO_MANY_ATTEMPTS",
    ),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=[case.code for case in ERROR_CASES])
def test_every_domain_error_maps_to_its_status_and_house_shape(case: ErrorCase) -> None:
    """A forgotten handler registration returns 500, not the documented status —
    and the 404 and 400 handlers are registered on the app/errors.py BASES, so
    without that re-registration every row below is a 500."""
    fake = FakeCatalogService()
    fake.raise_on[case.method_name] = case.error
    with _client(fake) as client:
        resp = client.request(case.verb, case.path, json=case.body)
    assert resp.status_code == case.status
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == case.code
    assert body["error"]["message"]


def test_presign_throttle_maps_to_429() -> None:
    fake = FakeCatalogService()
    fake.raise_on["presign_media"] = MediaPresignThrottledError()
    with _client(fake) as client:
        resp = client.post(PRESIGN_PATH, json=PRESIGN_BODY)
    assert resp.status_code == 429
    assert resp.json() == {
        "error": {"code": "TOO_MANY_ATTEMPTS", "message": "Too many attempts. Try again later."}
    }


def test_domain_validation_error_carries_its_own_message() -> None:
    fake = FakeCatalogService()
    fake.raise_on["replace_variants"] = CatalogValidationError("size_label is too long")
    with _client(fake) as client:
        resp = client.put(VARIANTS_PATH, json=VARIANTS_BODY)
    assert resp.status_code == 400
    assert resp.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "size_label is too long"}
    }


def test_no_error_body_leaks_storage_identity() -> None:
    """No bucket, region, endpoint or AWS text may appear in a user-facing
    message — the fixed 503 bodies are the whole contract."""
    fake = FakeCatalogService()
    for error in (MediaNotConfiguredError(), MediaStorageUnavailableError()):
        fake.raise_on["presign_media"] = error
        with _client(fake) as client:
            resp = client.post(PRESIGN_PATH, json=PRESIGN_BODY)
        message = resp.json()["error"]["message"]
        for needle in ("bucket", "il-central-1", "s3", "aws", "amazon"):
            assert needle not in message.lower(), message


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness: a row added to the spec's error table without a
    test here fails immediately, rather than shipping as a 500."""
    covered = {case.code for case in ERROR_CASES}
    # Hand-unioned, not ErrorCase rows: all three are raised during dependency
    # solving or in middleware, never by a service method, so no ErrorCase can
    # express them. Their tests are the three walks above.
    covered |= {"NOT_AUTHENTICATED", "CSRF_ORIGIN_MISMATCH", "NOT_AUTHORIZED"}
    assert covered == SPEC_ERROR_CODES


# --- CSRF origin middleware (already covers every mutating /manage route) ---


def test_mutating_catalog_request_with_mismatched_origin_is_403() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.post(
            PRESIGN_PATH, json=PRESIGN_BODY, headers={"origin": "http://evil.localtest.me"}
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.calls == []


def test_catalog_read_with_mismatched_origin_is_allowed() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.get(DETAIL_PATH, headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 200


# --- house-shape request validation ---


def test_unknown_key_in_any_catalog_body_is_a_400() -> None:
    fake = FakeCatalogService()
    bodies: list[tuple[str, str, dict[str, Any]]] = [
        ("POST", LIST_PATH, {**DRESS_CREATE_BODY, "evil": 1}),
        ("PATCH", DETAIL_PATH, {**DRESS_UPDATE_BODY, "evil": 1}),
        ("PUT", VARIANTS_PATH, {"variants": [{"size_label": "38", "quantity": 1, "evil": 1}]}),
        ("PUT", ORDER_PATH, {**REORDER_BODY, "evil": 1}),
    ]
    with _client(fake) as client:
        for verb, path, body in bodies:
            resp = client.request(verb, path, json=body)
            assert resp.status_code == 400, (verb, path)
            assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_invalid_json_body_is_house_shape_400() -> None:
    fake = FakeCatalogService()
    with _client(fake) as client:
        resp = client.post(
            LIST_PATH, content=b"{not json", headers={"content-type": "application/json"}
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
