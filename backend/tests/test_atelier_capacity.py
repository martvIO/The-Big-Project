"""D2's pure capacity core: the tenant default and the two-step resolution.

No Postgres, no fakes, no session — two total functions of their arguments, in
the same module and for the same reason as `effort_bands` (`stages.py:1-13`).

⚠ THE WHOLE FILE EXISTS FOR ONE BOUNDARY: `0` and `None` are DIFFERENT ANSWERS.
`0` is "she is away this week" and it is HERS; `None` is "nobody has said", and
it renders no bar at all. Every short form that collapses them — `or`, `if not
…`, `settings.get(…) or {}` applied one level too deep — is a bug this feature
has a designed, visible, wrong rendering for, which is why D2 is code rather
than a sentence.
"""

import uuid
from typing import Any

import pytest

from app.atelier.stages import (
    MAX_WEEKLY_CAPACITY_HOURS,
    default_capacity_hours,
    resolve_capacity,
)
from app.models.constants import StaffRole
from app.models.staff_user import StaffUser

TENANT_ID = uuid.uuid4()


def _seamstress(hours: int | None) -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT_ID,
        email="noa@bella.example",
        password_hash="not-a-real-hash",
        display_name="נועה",
        role=StaffRole.SEAMSTRESS.value,
    )
    row.id = uuid.uuid4()
    row.deleted_at = None
    row.weekly_capacity_hours = hours
    return row


def _settings(stored: Any) -> dict[str, Any]:
    return {"atelier": {"default_weekly_capacity_hours": stored}}


# --- the tenant default (D2) -------------------------------------------------


def test_a_brand_new_boutique_has_no_default_at_all() -> None:
    """No `atelier` key is the NORMAL case, not an error — until F42's editor
    lands nothing can write one. THE PLATFORM SHIPS NO NUMBER: a fabricated
    denominator would make every bar lie by construction, on day one, on every
    tenant, with nobody having entered a number to be wrong."""
    assert default_capacity_hours({}) is None
    assert default_capacity_hours({"profile": {"phone": "03-555"}}) is None


def test_an_atelier_key_that_is_not_a_mapping_does_not_crash_the_poll() -> None:
    assert default_capacity_hours({"atelier": "40"}) is None
    assert default_capacity_hours({"atelier": [40]}) is None


def test_bands_without_a_default_resolve_to_no_default() -> None:
    """The two sub-keys are independent: a tenant that has tuned its bands and
    never set a house capacity is the ordinary state after F41."""
    assert default_capacity_hours({"atelier": {"effort_bands": {"half_day": 300}}}) is None


@pytest.mark.parametrize("stored", ["40", 40.0, [40], {"hours": 40}, None])
def test_a_corrupt_stored_default_resolves_to_none(stored: Any) -> None:
    assert default_capacity_hours(_settings(stored)) is None


def test_a_boolean_default_is_not_a_one_hour_week() -> None:
    """`bool` is an `int` subclass in Python, so `True` would otherwise resolve
    to a one-hour week and redden every bar in the boutique. `_positive_int`
    already records this trap one function up; this is the same trap on the
    other magnitude."""
    assert default_capacity_hours(_settings(True)) is None
    assert default_capacity_hours(_settings(False)) is None


@pytest.mark.parametrize("stored", [-1, 169, 1000])
def test_a_default_outside_the_ddl_check_resolves_to_none(stored: int) -> None:
    """A stored 200 would otherwise reach the wire and every bar would divide by
    it — and the DDL CHECK that refuses it on `staff_users` does not exist on a
    JSONB blob."""
    assert default_capacity_hours(_settings(stored)) is None


@pytest.mark.parametrize("stored", [0, 1, 40, MAX_WEEKLY_CAPACITY_HOURS])
def test_a_default_inside_the_bound_resolves_to_itself(stored: int) -> None:
    """⚠ INCLUDING `0`. The bound is `0..168`, not `1..168`: a boutique that has
    stood its whole workroom down for a week is a state the product renders."""
    assert default_capacity_hours(_settings(stored)) == stored


def test_the_ceiling_is_the_ddl_checks_own_number() -> None:
    """One magnitude, one place. `0022`'s CHECK is `>= 0 AND <= 168` and this
    constant is what keeps the settings bound and the column bound from
    drifting apart."""
    assert MAX_WEEKLY_CAPACITY_HOURS == 168


# --- the two-step resolution (D2) --------------------------------------------


def test_her_own_hours_win_and_are_not_the_boutiques() -> None:
    assert resolve_capacity(_seamstress(12), 40) == (12, False)


def test_her_missing_hours_fall_back_to_the_boutiques() -> None:
    assert resolve_capacity(_seamstress(None), 40) == (40, True)


def test_hers_stand_alone_when_the_boutique_has_no_default() -> None:
    assert resolve_capacity(_seamstress(12), None) == (12, False)


def test_neither_set_is_a_real_answer_and_it_is_never_a_guess() -> None:
    """`capacity_is_default` is FALSE here and not true — there is nothing to
    have defaulted to. The row renders «לא הוגדרה קיבולת» and no bar."""
    assert resolve_capacity(_seamstress(None), None) == (None, False)


def test_a_zero_capacity_is_hers_and_not_the_boutiques() -> None:
    """⚠ THE NAMED MUTATION (D2). Replace `is not None` with `or` and this line
    reads `(40, True)`: a seamstress marked 0 — "away this week" — gets handed
    the boutique's default, her bar renders at a fraction of the truth in the
    non-overload colour, `capacity_is_default` claims the boutique chose a
    number she set herself, and D10's sort puts her FIRST in the assign Select
    labelled «נותרו 40 שעות»."""
    assert resolve_capacity(_seamstress(0), 40) == (0, False)


def test_a_zero_default_is_a_real_default() -> None:
    """The same boundary one level up: `tenant_default = 0` is a set default, so
    `capacity_is_default` is TRUE. `tenant_default is not None`, never
    truthiness."""
    assert resolve_capacity(_seamstress(None), 0) == (0, True)
