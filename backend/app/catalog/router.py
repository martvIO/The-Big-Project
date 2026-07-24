"""HTTP layer for the catalog: a thin translator over CatalogService's frozen
views. Every route resolves the tenant from the host-derived context and the
dress from the URL — no client-supplied value reaches a storage key.

Mounted at prefix="/manage" like the boutique router, and registered after it.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.auth.dependencies import get_current_staff
from app.auth.service import StaffContext
from app.catalog.schemas import (
    CreateDressRequest,
    DressDetailResponse,
    DressListResponse,
    DressResponse,
    MediaResponse,
    PresignRequest,
    PresignResponse,
    ReorderMediaRequest,
    ReplaceVariantsRequest,
    UpdateDressRequest,
    VariantResponse,
)
from app.catalog.service import CatalogService, DressView, MediaView
from app.catalog.validation import (
    DRESS_LIST_DEFAULT_LIMIT,
    DRESS_LIST_MAX_LIMIT,
    MAX_SEARCH_LENGTH,
    VariantInput,
)
from app.schemas import OkResponse
from app.storage.base import MediaNotConfiguredError, MediaStorage
from app.tenancy.middleware import get_current_tenant

# Signed URLs (900 s) and POST-policy fields (300 s) are bearer material: they
# must not land in a shared cache or a bfcache entry.
NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    """Set on the ROUTER, not per route. Nine of these eleven endpoints answer
    with a DressResponse or a DressDetailResponse, whose `cover.url` and
    `media[].url` are signed GETs valid for SIGNED_GET_TTL_SECONDS — and the
    tenth returns the POST policy itself. Setting the header centrally is what
    makes the invariant structural: a route added later cannot forget it, and
    the one route with nothing to protect (archive → OkResponse) pays nothing
    for carrying it.
    """
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/manage", dependencies=[Depends(_no_store)])

Staff = Annotated[StaffContext, Depends(get_current_staff)]


def get_catalog_service(request: Request) -> CatalogService:
    return request.app.state.catalog_service


def get_media_storage(request: Request) -> MediaStorage:
    return request.app.state.media_storage


Service = Annotated[CatalogService, Depends(get_catalog_service)]
Storage = Annotated[MediaStorage, Depends(get_media_storage)]


def _require_media_storage(storage: MediaStorage) -> None:
    """Refuse a media write before any database work when no bucket is
    configured: a pending row written now could never be uploaded against. The
    service checks too — it is called directly by the isolation suite — but this
    is where the 503 belongs."""
    if not storage.is_configured:
        raise MediaNotConfiguredError


def _media_response(view: MediaView) -> MediaResponse:
    return MediaResponse(
        id=view.row.id,
        sort_order=view.row.sort_order,
        content_type=view.row.content_type,
        byte_size=view.row.byte_size,
        url=view.url,
        url_expires_at=view.url_expires_at,
    )


def _dress_fields(view: DressView) -> dict[str, Any]:
    row = view.row
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "price_agorot": row.price_agorot,
        "price_visible": row.price_visible,
        "reserved": row.reserved,
        "sort_order": row.sort_order,
        "out_of_stock": view.summary.out_of_stock,
        "total_quantity": view.summary.total_quantity,
        "variant_count": view.summary.variant_count,
        "media_count": view.media_count,
        "cover": _media_response(view.cover) if view.cover is not None else None,
        # deleted_at is the archive flag; the timestamp itself never ships.
        "archived": row.deleted_at is not None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _dress_response(view: DressView) -> DressResponse:
    return DressResponse(**_dress_fields(view))


def _dress_detail_response(view: DressView) -> DressDetailResponse:
    return DressDetailResponse(
        **_dress_fields(view),
        variants=[VariantResponse.model_validate(row) for row in view.variants],
        media=[_media_response(item) for item in view.media],
        media_uploads_enabled=view.uploads_enabled,
        media_slots_remaining=view.slots_remaining,
    )


# --- dresses ---


@router.get("/dresses")
async def list_dresses(
    request: Request,
    staff: Staff,
    service: Service,
    # Spelled out rather than reusing Feature 7's shortcut, which only works
    # where the default equals the maximum.
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=DRESS_LIST_MAX_LIMIT)] = DRESS_LIST_DEFAULT_LIMIT,
    search: Annotated[str | None, Query(max_length=MAX_SEARCH_LENGTH)] = None,
    archived: bool = False,
) -> DressListResponse:
    tenant = get_current_tenant(request)
    result = await service.list_dresses(
        tenant.id, archived=archived, search=search, offset=offset, limit=limit
    )
    return DressListResponse(
        items=[_dress_response(view) for view in result.items],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.post("/dresses")
async def create_dress(
    request: Request, staff: Staff, service: Service, body: CreateDressRequest
) -> DressResponse:
    tenant = get_current_tenant(request)
    view = await service.create_dress(
        tenant.id,
        name=body.name,
        description=body.description,
        price_agorot=body.price_agorot,
        price_visible=body.price_visible,
        reserved=body.reserved,
        sort_order=body.sort_order,
    )
    return _dress_response(view)


@router.get("/dresses/{dress_id}")
async def get_dress(
    request: Request, staff: Staff, service: Service, dress_id: UUID
) -> DressDetailResponse:
    tenant = get_current_tenant(request)
    return _dress_detail_response(await service.get_dress(tenant.id, dress_id))


@router.patch("/dresses/{dress_id}")
async def update_dress(
    request: Request,
    staff: Staff,
    service: Service,
    dress_id: UUID,
    body: UpdateDressRequest,
) -> DressResponse:
    tenant = get_current_tenant(request)
    view = await service.update_dress(
        tenant.id,
        dress_id,
        name=body.name,
        description=body.description,
        price_agorot=body.price_agorot,
        price_visible=body.price_visible,
        reserved=body.reserved,
        sort_order=body.sort_order,
    )
    return _dress_response(view)


@router.delete("/dresses/{dress_id}")
async def archive_dress(
    request: Request, staff: Staff, service: Service, dress_id: UUID
) -> OkResponse:
    tenant = get_current_tenant(request)
    await service.archive_dress(tenant.id, dress_id)
    return OkResponse()


@router.post("/dresses/{dress_id}/restore")
async def restore_dress(
    request: Request, staff: Staff, service: Service, dress_id: UUID
) -> DressDetailResponse:
    tenant = get_current_tenant(request)
    return _dress_detail_response(await service.restore_dress(tenant.id, dress_id))


# --- variants ---


@router.put("/dresses/{dress_id}/variants")
async def replace_variants(
    request: Request,
    staff: Staff,
    service: Service,
    dress_id: UUID,
    body: ReplaceVariantsRequest,
) -> DressDetailResponse:
    tenant = get_current_tenant(request)
    inputs = [
        VariantInput(
            size_label=variant.size_label,
            quantity=variant.quantity,
            sort_order=variant.sort_order,
        )
        for variant in body.variants
    ]
    return _dress_detail_response(await service.replace_variants(tenant.id, dress_id, inputs))


# --- media ---


@router.post("/dresses/{dress_id}/media/presign")
async def presign_media(
    request: Request,
    staff: Staff,
    service: Service,
    storage: Storage,
    dress_id: UUID,
    body: PresignRequest,
) -> PresignResponse:
    tenant = get_current_tenant(request)
    _require_media_storage(storage)
    result = await service.presign_media(
        tenant.id, dress_id, content_type=body.content_type, byte_size=body.byte_size
    )
    return PresignResponse(
        media_id=result.media_id,
        url=result.url,
        fields=result.fields,
        expires_in=result.expires_in,
        max_bytes=result.max_bytes,
    )


@router.post("/dresses/{dress_id}/media/{media_id}/confirm")
async def confirm_media(
    request: Request,
    staff: Staff,
    service: Service,
    storage: Storage,
    dress_id: UUID,
    media_id: UUID,
) -> DressDetailResponse:
    tenant = get_current_tenant(request)
    _require_media_storage(storage)
    return _dress_detail_response(await service.confirm_media(tenant.id, dress_id, media_id))


@router.delete("/dresses/{dress_id}/media/{media_id}")
async def delete_media(
    request: Request,
    staff: Staff,
    service: Service,
    storage: Storage,
    dress_id: UUID,
    media_id: UUID,
) -> DressDetailResponse:
    tenant = get_current_tenant(request)
    _require_media_storage(storage)
    return _dress_detail_response(await service.delete_media(tenant.id, dress_id, media_id))


@router.put("/dresses/{dress_id}/media/order")
async def reorder_media(
    request: Request,
    staff: Staff,
    service: Service,
    dress_id: UUID,
    body: ReorderMediaRequest,
) -> DressDetailResponse:
    # Reorder is a pure database operation: it keeps working with no bucket.
    tenant = get_current_tenant(request)
    return _dress_detail_response(await service.reorder_media(tenant.id, dress_id, body.media_ids))
