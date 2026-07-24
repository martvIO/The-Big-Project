from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.storage.base import MediaStorage

router = APIRouter()

# Settings.model_config is extra="ignore", so a typo'd MEDIA_BUKCET is discarded
# silently. This field is how Feature 2's staging smoke learns the app came up
# without a bucket before it attempts a presign.
MEDIA_CONFIGURED = "configured"
MEDIA_UNCONFIGURED = "unconfigured"


class HealthResponse(BaseModel):
    status: str
    version: str
    # State only, never identity: /health is unauthenticated and host-agnostic,
    # so no bucket, region or endpoint may appear here.
    media: str


@router.get("/health")
async def health(request: Request) -> HealthResponse:
    storage: MediaStorage = request.app.state.media_storage
    return HealthResponse(
        status="ok",
        version=get_settings().app_version,
        media=MEDIA_CONFIGURED if storage.is_configured else MEDIA_UNCONFIGURED,
    )
