"""F27 D3 — the `toggles` block on the wire is DEFAULT-COMPLETE.

⚠ THIS FILE EXISTS BECAUSE `test_boutique_service.py` IS `pytestmark =
pytest.mark.db` AT MODULE LEVEL. `_settings_result` is a pure function and its
overlay rule needs no database, so a test placed there would be deselected by
the fast lane and would only ever run on CI — a unit test hiding in the slow
lane. The db half of D3 (a GET after a partial write) stays over there, where it
belongs.
"""

from app.boutique.service import _settings_result
from app.boutique.toggles import TOGGLE_DEFAULTS, TOGGLE_KEYS


def test_an_absent_toggle_reads_as_its_registry_default() -> None:
    """Provisioning seeds no toggles at all, so `{}` is every boutique on day
    one. The wire carries a concrete bool for every registry key regardless —
    which is what lets the matrix render wire truth with no `?? false`."""
    result = _settings_result({})
    assert result.toggles == TOGGLE_DEFAULTS
    assert set(result.toggles) == set(TOGGLE_KEYS)


def test_a_stored_toggle_value_wins_over_its_default() -> None:
    result = _settings_result({"toggles": {"deposits_enabled": True}})
    assert result.toggles == {"deposits_enabled": True, "brides_only": False}


def test_the_wire_key_set_is_exactly_the_registry_key_set() -> None:
    """⚠ BOTH DIRECTIONS, AND THE SECOND IS THE ONE THAT MATTERS. A registry key
    missing from the wire is a row the matrix cannot render; a STALE stored key
    surviving onto the wire is a row the matrix WOULD render, from a toggle
    nothing reads any more — the dead-switch failure F27 exists to make
    impossible. A retired toggle leaves the registry and must leave the wire with
    it, whatever is still sitting in the JSONB."""
    result = _settings_result({"toggles": {"retired_toggle": True, "brides_only": True}})
    assert set(result.toggles) == set(TOGGLE_KEYS)
    assert "retired_toggle" not in result.toggles
    assert result.toggles["brides_only"] is True


def test_the_other_settings_blocks_are_untouched_by_the_overlay() -> None:
    """D3 is scoped to `toggles`. `profile` and `atelier` keep the shipped
    `or {}` idiom — no defaults, absent means empty."""
    result = _settings_result({"profile": {"phone": "03-5550100"}})
    assert result.profile == {"phone": "03-5550100"}
    assert result.atelier == {}
