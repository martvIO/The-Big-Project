"""Wire primitives shared by every API module.

These two started in app/boutique/schemas.py and moved here when the catalog
module needed them: a second domain module importing a boutique schema would
make the dependency arrow point sideways for no reason, and F10's generated
client would see two `{"ok": true}` types instead of one. Both are re-exported
from app.boutique.schemas, so the move is not a wire change.
"""

from pydantic import BaseModel, ConfigDict


class ForbidExtraModel(BaseModel):
    """Base for every REQUEST model: an unknown key is a house-shape 400, not a
    silently ignored field. That is what makes "no client-supplied value can
    reach an S3 key" an assertion rather than a hope."""

    model_config = ConfigDict(extra="forbid")


class OkResponse(BaseModel):
    """The response for a mutation with nothing left to return."""

    ok: bool = True
