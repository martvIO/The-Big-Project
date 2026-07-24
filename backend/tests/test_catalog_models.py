"""Schema-shape assertions for the Feature 8 catalog models — pure SQLAlchemy
metadata, no database. The real DDL (CHECKs, indexes, grants, RLS) is exercised
in CI by test_catalog_integration.py + the RLS metadata scan; these keep the ORM
layer honest locally.
"""

from sqlalchemy import Table

from app.models.base import Base
from app.models.constants import DressMediaStatus
from app.models.dress import Dress
from app.models.dress_media import DressMedia
from app.models.dress_variant import DressVariant

STANDARD_COLUMNS = {"id", "tenant_id", "created_at", "updated_at", "deleted_at"}


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def test_dress_media_status_values() -> None:
    assert DressMediaStatus.PENDING == "pending"
    assert DressMediaStatus.READY == "ready"
    assert {member.value for member in DressMediaStatus} == {"pending", "ready"}


def test_all_catalog_tables_carry_standard_columns() -> None:
    for model in (Dress, DressVariant, DressMedia):
        missing = STANDARD_COLUMNS - set(_table(model.__tablename__).columns.keys())
        assert missing == set(), f"{model.__tablename__} missing {missing}"


def test_dress_shape() -> None:
    assert Dress.__tablename__ == "dresses"
    cols = _table("dresses").columns
    assert not cols["name"].nullable
    # Nullable description and price both mean "not recorded" — the storefront
    # renders a price-on-request treatment for a null price or price_visible false.
    assert cols["description"].nullable
    assert cols["price_agorot"].nullable
    assert not cols["price_visible"].nullable
    assert not cols["reserved"].nullable
    assert not cols["sort_order"].nullable


def test_dress_variant_shape() -> None:
    assert DressVariant.__tablename__ == "dress_variants"
    cols = _table("dress_variants").columns
    assert not cols["dress_id"].nullable
    assert not cols["size_label"].nullable
    assert not cols["quantity"].nullable
    assert not cols["sort_order"].nullable


def test_dress_media_shape() -> None:
    assert DressMedia.__tablename__ == "dress_media"
    cols = _table("dress_media").columns
    assert not cols["dress_id"].nullable
    assert not cols["storage_key"].nullable
    assert not cols["content_type"].nullable
    assert not cols["byte_size"].nullable
    assert not cols["status"].nullable
    assert not cols["sort_order"].nullable
