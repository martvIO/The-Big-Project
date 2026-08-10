"""Schema-shape assertions for the Feature 7 models — pure SQLAlchemy metadata,
no database. The real DDL (CHECKs, grants, RLS) is exercised in CI by
migrated_db + the RLS metadata scan; these keep the ORM layer honest locally.
"""

import importlib.util
from pathlib import Path

from sqlalchemy import Table

from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.base import Base
from app.models.constants import AppointmentAudience, AuditAction, AvailabilityState, OnShiftSource
from app.models.roster import Roster
from app.models.roster_assignment import RosterAssignment
from app.models.shift_template import ShiftTemplate
from app.models.staff_availability import StaffAvailability
from app.models.staff_user import StaffUser  # noqa: F401  (registers staff_users on Base)
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


# --- F38: the model<->migration parity gap ----------------------------------

# GLOBBED, not spelled with its number. A migration's number is claim order and
# moves at every rebase — this one shipped as 0031, then F28 merged as
# 0031_dress_reservations.py and it became 0032. A hardcoded filename turns that
# routine renumber into a FileNotFoundError in an unrelated test file.
_HR_MIGRATION = next(
    (Path(__file__).resolve().parent.parent / "migrations" / "versions").glob(
        "*_staff_hr_directory.py"
    )
)


def _migration_columns(path: Path) -> set[str]:
    """The column names the HR migration adds, read out of the migration ITSELF.

    Every other option compares the model against a list retyped in this file,
    which is a list the same hand that forgot the model would have to edit. The
    migration is loaded by path rather than imported, because `migrations/versions`
    is not a package — `op` is a proxy and resolves fine with no alembic context.
    """
    spec = importlib.util.spec_from_file_location("hr_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {declaration.split()[0] for declaration in module._COLUMNS}


def test_staff_user_declares_every_column_the_hr_migration_adds() -> None:
    """THE parity test this repo has never had, and the reason F38's plan says
    "an omitted column is an AttributeError at first read, not a red test" three
    separate times: 0023's and F57's headers both had to spell out by hand that
    the model must be edited in the same PR, because nothing enforced it.

    ⚠ F40 EXTENDS IT TO A SECOND MIGRATION rather than adding a third parity
    test. Scoped to F38's migration alone it is blind to `on_shift_on` /
    `on_shift_override`, and an omitted `Mapped[…]` for either is an
    `AttributeError` on the first floor read — the highest-traffic screen in the
    console — instead of a red test here (plan R-K).
    """
    declared = _migration_columns(_HR_MIGRATION)
    assert len(declared) == 11, declared
    on_shift = {
        declaration.split()[0]
        for declaration in _roster_migration_module()._STAFF_USER_COLUMNS  # type: ignore[attr-defined]
    }
    assert on_shift == {"on_shift_on", "on_shift_override"}, on_shift
    missing = (declared | on_shift) - set(_table("staff_users").columns.keys())
    assert missing == set(), f"StaffUser is missing {missing}"


def test_the_two_on_shift_columns_are_nullable_together() -> None:
    """D4's pair: `(on_shift_on IS NULL) = (on_shift_override IS NULL)` is a named
    DB CHECK, so BOTH columns are nullable and neither carries a default. A
    NOT NULL on either would make "no override" unrepresentable and turn rule 1
    into a rule that always fires."""
    columns = _table("staff_users").columns
    for name in ("on_shift_on", "on_shift_override"):
        assert columns[name].nullable is True, name
        assert columns[name].server_default is None, name


def test_staff_user_photo_columns_are_all_nullable_together() -> None:
    """The live triple and the pending triple are each all-or-nothing, and the
    schema cannot say so — a CHECK spanning three columns would refuse the
    ordinary intermediate state the two-phase confirm creates. So every one of
    the six is nullable and the INVARIANT lives in StaffService, which writes and
    clears each triple as a unit. Asserted here so a later NOT NULL on any one of
    them collides with this sentence rather than with a 500 on confirm."""
    columns = _table("staff_users").columns
    for name in _migration_columns(_HR_MIGRATION):
        if name == "shift_manager_eligible":
            assert columns[name].nullable is False
        else:
            assert columns[name].nullable is True, name


# --- F39: shift_templates + staff_availability ------------------------------

# GLOBBED for the same reason `_HR_MIGRATION` is: a migration's number is claim
# order and moves at every rebase.
_SHIFTS_MIGRATION = next(
    (Path(__file__).resolve().parent.parent / "migrations" / "versions").glob(
        "*_shift_availability.py"
    )
)


def _shifts_migration_module() -> object:
    spec = importlib.util.spec_from_file_location("shifts_migration", _SHIFTS_MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shift_models_declare_every_column_their_migration_creates() -> None:
    """F38's parity mechanism, applied to two whole new tables.

    The lists come out of the MIGRATION ITSELF (`_SHIFT_TEMPLATE_COLUMNS`,
    `_STAFF_AVAILABILITY_COLUMNS`), never out of a copy retyped here — a retyped
    list is a list the same hand that forgot the model would have to edit.

    ⚠ `shift_templates`' declared set is the UNION of F39's CREATE and F40's
    ALTER. The `extra` half below is a set difference, so leaving F40's
    `coverage_targets` out of it would red this test the moment the model
    declares the column — which is the same hand-edit trap the union avoids.
    """
    shifts = _shifts_migration_module()
    roster = _roster_migration_module()
    for table_name, declarations in (
        (
            "shift_templates",
            (
                *shifts._SHIFT_TEMPLATE_COLUMNS,  # type: ignore[attr-defined]
                *roster._SHIFT_TEMPLATE_COLUMNS,  # type: ignore[attr-defined]
            ),
        ),
        ("staff_availability", shifts._STAFF_AVAILABILITY_COLUMNS),  # type: ignore[attr-defined]
    ):
        declared = {declaration.split()[0] for declaration in declarations}
        missing = declared - set(_table(table_name).columns.keys())
        assert missing == set(), f"{table_name} model is missing {missing}"
        # The other direction too: a model column the migration never creates is
        # an UndefinedColumn at first read rather than a red test.
        extra = set(_table(table_name).columns.keys()) - declared - STANDARD_COLUMNS
        assert extra == set(), f"{table_name} model declares {extra}, which no migration creates"


def test_both_shift_tables_carry_standard_columns() -> None:
    for model in (ShiftTemplate, StaffAvailability):
        missing = STANDARD_COLUMNS - set(_table(model.__tablename__).columns.keys())
        assert missing == set(), f"{model.__tablename__} missing {missing}"


# --- F40: rosters + roster_assignments ---------------------------------------

_ROSTER_MIGRATION = next(
    (Path(__file__).resolve().parent.parent / "migrations" / "versions").glob("*_roster.py")
)


def _roster_migration_module() -> object:
    spec = importlib.util.spec_from_file_location("roster_migration", _ROSTER_MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_roster_models_declare_every_column_their_migration_creates() -> None:
    """The twin of F39's, for F40's two tables. Without it every line of the
    repositories and the service is an `AttributeError` at first read rather
    than a red test here."""
    module = _roster_migration_module()
    for table_name, declarations in (
        ("rosters", module._ROSTER_COLUMNS),  # type: ignore[attr-defined]
        ("roster_assignments", module._ROSTER_ASSIGNMENT_COLUMNS),  # type: ignore[attr-defined]
    ):
        declared = {declaration.split()[0] for declaration in declarations}
        missing = declared - set(_table(table_name).columns.keys())
        assert missing == set(), f"{table_name} model is missing {missing}"
        extra = set(_table(table_name).columns.keys()) - declared - STANDARD_COLUMNS
        assert extra == set(), f"{table_name} model declares {extra}, which no migration creates"


def test_all_four_shift_tables_carry_standard_columns() -> None:
    """TWO became FOUR (plan A1). A soft-delete predicate is the whole contract
    of every read in this feature, so a table that quietly lacked `deleted_at`
    would answer every query with rows nobody can remove."""
    for model in (ShiftTemplate, StaffAvailability, Roster, RosterAssignment):
        missing = STANDARD_COLUMNS - set(_table(model.__tablename__).columns.keys())
        assert missing == set(), f"{model.__tablename__} missing {missing}"


def test_roster_shape() -> None:
    """`published_at`/`published_by` are the WHOLE of this table's state (D6) —
    there is no `status` enum, because a second copy of a fact can disagree with
    the first."""
    assert Roster.__tablename__ == "rosters"
    cols = _table("rosters").columns
    assert not cols["week_start"].nullable
    # NULL = draft. Both nullable, paired by a named DB CHECK.
    assert cols["published_at"].nullable
    assert cols["published_by"].nullable


def test_roster_assignment_shape() -> None:
    assert RosterAssignment.__tablename__ == "roster_assignments"
    cols = _table("roster_assignments").columns
    for name in ("roster_id", "shift_template_id", "staff_user_id", "assigned_by"):
        assert not cols[name].nullable, name
    assert not cols["is_shift_manager"].nullable
    # NULL = no override (D11). Only 'unavailable' is ever written today.
    assert cols["override_of_state"].nullable


def test_coverage_targets_is_a_non_null_sparse_map() -> None:
    """D10: absent key means «no target» and `0` means «deliberately nobody», so
    the column must default to an EMPTY object and never to NULL — a nullable
    JSONB would give the sparse map a third, meaningless state."""
    column = _table("shift_templates").columns["coverage_targets"]
    assert column.nullable is False
    assert column.server_default is not None


def test_on_shift_source_has_exactly_three_members_and_no_db_check() -> None:
    """DERIVED on read like `StaffCardStatus`, never stored like
    `AvailabilityState` — so there is no column for a CHECK to constrain and the
    resolver is the only producer."""
    assert {member.value for member in OnShiftSource} == {"manual_today", "roster", "fallback"}


def test_the_five_roster_audit_actions_exist() -> None:
    """An unwritten member is inert; a MISSING one is a `ValueError` at 03:00 on
    the first write of a route nobody exercised in review."""
    assert AuditAction.ROSTER_ASSIGNED == "roster_assigned"
    assert AuditAction.ROSTER_UNASSIGNED == "roster_unassigned"
    assert AuditAction.ROSTER_PUBLISHED == "roster_published"
    assert AuditAction.ON_SHIFT_OVERRIDE_SET == "on_shift_override_set"
    assert AuditAction.ON_SHIFT_OVERRIDE_CLEARED == "on_shift_override_cleared"


def test_shift_template_shape() -> None:
    assert ShiftTemplate.__tablename__ == "shift_templates"
    cols = _table("shift_templates").columns
    for name in ("day_of_week", "label", "starts_at_time", "ends_at_time", "sort_order"):
        assert not cols[name].nullable, name


def test_staff_availability_shape() -> None:
    assert StaffAvailability.__tablename__ == "staff_availability"
    cols = _table("staff_availability").columns
    for name in ("staff_user_id", "shift_template_id", "week_start", "state"):
        assert not cols[name].nullable, name
    # NULL when she recorded it herself (D5) — the whole point of the column.
    assert cols["recorded_by"].nullable


def test_availability_state_has_exactly_three_members() -> None:
    """D8: no fourth `pending`. The console's «לא נרשם» is the rendered name of
    an ABSENT row and never a stored value, so a fourth member here would be the
    exact ambiguity the roster-readiness read exists to remove."""
    assert {member.value for member in AvailabilityState} == {
        "available",
        "unavailable",
        "preferred",
    }
