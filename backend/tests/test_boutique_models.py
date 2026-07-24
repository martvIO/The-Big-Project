"""Schema-shape assertions for the Feature 7 models — pure SQLAlchemy metadata,
no database. The real DDL (CHECKs, grants, RLS) is exercised in CI by
migrated_db + the RLS metadata scan; these keep the ORM layer honest locally.
"""

from sqlalchemy import Table

from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.base import Base
from app.models.constants import AppointmentAudience
from app.models.terms_version import TermsVersion

STANDARD_COLUMNS = {"id", "tenant_id", "created_at", "updated_at", "deleted_at"}


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def test_appointment_audience_values() -> None:
    assert AppointmentAudience.ALL == "all"
    assert AppointmentAudience.BRIDES_ONLY == "brides_only"
    assert {member.value for member in AppointmentAudience} == {"all", "brides_only"}


def test_all_new_tables_carry_standard_columns() -> None:
    for model in (AppointmentType, AvailabilityRule, AvailabilityException, TermsVersion):
        missing = STANDARD_COLUMNS - set(_table(model.__tablename__).columns.keys())
        assert missing == set(), f"{model.__tablename__} missing {missing}"


def test_appointment_type_shape() -> None:
    assert AppointmentType.__tablename__ == "appointment_types"
    cols = _table("appointment_types").columns
    assert not cols["name"].nullable
    assert not cols["duration_minutes"].nullable
    assert not cols["audience"].nullable
    assert not cols["deposit_required"].nullable
    assert cols["deposit_amount_agorot"].nullable
    assert not cols["sort_order"].nullable


def test_availability_rule_shape() -> None:
    assert AvailabilityRule.__tablename__ == "availability_rules"
    cols = _table("availability_rules").columns
    assert not cols["day_of_week"].nullable
    assert not cols["open_time"].nullable
    assert not cols["close_time"].nullable
    assert not cols["capacity"].nullable


def test_availability_exception_shape() -> None:
    assert AvailabilityException.__tablename__ == "availability_exceptions"
    cols = _table("availability_exceptions").columns
    assert not cols["date"].nullable
    # Both NULL = closed all day; both set = special hours (one-sided → 400 in service).
    assert cols["open_time"].nullable
    assert cols["close_time"].nullable
    assert cols["note"].nullable


def test_terms_version_shape() -> None:
    assert TermsVersion.__tablename__ == "terms_versions"
    cols = _table("terms_versions").columns
    assert not cols["version"].nullable
    assert not cols["terms_text"].nullable
    assert not cols["refundable_until_hours_before"].nullable
    assert not cols["forfeit_percent"].nullable
    assert not cols["created_by"].nullable
    # StandardColumns kept for uniformity: updated_at exists but stays NULL forever
    # (append-only — the DB grants SELECT, INSERT only, so no UPDATE can ever run).
    assert "updated_at" in cols
