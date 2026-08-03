"""The tenant effort-band resolver — pure, fast, no Postgres.

D8: the wire carries a BAND KEY, the server resolves it to minutes, the row
stores minutes. The mapping lives at `tenants.settings["atelier"]["effort_bands"]`
and F41 ships a READER and no editor — F42 owns the writer, because F42 is the
feature whose capacity arithmetic a re-tune actually changes.

Every case below is about the same property: **every tenant always has exactly
five bands**. That is what lets the intake form render with no empty branch and
what lets `alteration_tickets.effort_minutes NOT NULL` hold.
"""

from typing import Any

import pytest

from app.atelier.stages import DEFAULT_EFFORT_BANDS, effort_bands
from app.models.constants import EffortBand


def _settings(bands: Any) -> dict[str, Any]:
    return {"profile": {"name": "Boutique"}, "atelier": {"effort_bands": bands}}


def test_the_five_platform_defaults_are_q13s_five() -> None:
    assert DEFAULT_EFFORT_BANDS == {
        EffortBand.THIRTY_MIN: 30,
        EffortBand.ONE_HOUR: 60,
        EffortBand.TWO_HOURS: 120,
        EffortBand.HALF_DAY: 240,
        EffortBand.FULL_DAY: 480,
    }


def test_a_brand_new_boutique_with_no_atelier_key_resolves_the_platform_defaults() -> None:
    """THE NORMAL CASE, not an error path. No shipped writer can reach the
    `atelier` key at all — `merge_settings` takes only `profile=` and `toggles=`
    — so on the day F41 ships, EVERY tenant is this case."""
    assert effort_bands({}) == DEFAULT_EFFORT_BANDS
    assert effort_bands({"profile": {}, "toggles": {}}) == DEFAULT_EFFORT_BANDS


def test_an_atelier_key_with_no_effort_bands_resolves_the_defaults() -> None:
    """F42 may add a sibling key under `atelier` before it adds the editor."""
    assert effort_bands({"atelier": {}}) == DEFAULT_EFFORT_BANDS
    assert effort_bands({"atelier": {"effort_bands": None}}) == DEFAULT_EFFORT_BANDS


def test_a_fully_tuned_mapping_is_taken_verbatim() -> None:
    tuned = {band.value: 15 for band in EffortBand}
    assert effort_bands(_settings(tuned)) == dict.fromkeys(EffortBand, 15)


def test_a_partial_mapping_tunes_only_the_named_band() -> None:
    """PER BAND, never all-or-nothing. A boutique whose shifts are six hours
    tunes `half_day` and leaves the other four alone; discarding the whole stored
    mapping because one band is absent would silently revert her one edit."""
    resolved = effort_bands(_settings({EffortBand.HALF_DAY.value: 180}))
    assert resolved[EffortBand.HALF_DAY] == 180
    assert resolved[EffortBand.THIRTY_MIN] == DEFAULT_EFFORT_BANDS[EffortBand.THIRTY_MIN]
    assert resolved[EffortBand.FULL_DAY] == DEFAULT_EFFORT_BANDS[EffortBand.FULL_DAY]


@pytest.mark.parametrize(
    "stored",
    [
        -30,  # a negative estimate is not a shorter job
        0,  # zero minutes of work is not a band
        1441,  # past the DB CHECK's ceiling — see below
        "sixty",  # JSONB holds whatever was written into it
        60.5,  # a float would round somewhere nobody chose
        True,  # bool is an int subclass in Python; it is not a duration
        None,
        [],
        {"minutes": 60},
    ],
)
def test_a_junk_value_falls_back_to_that_bands_platform_default(stored: Any) -> None:
    """PER BAND again: one bad value costs that band its tuning and nothing else.

    The upper bound matters more than it looks. `effort_minutes` carries a DB
    CHECK of `> 0 AND <= 1440`, and this resolver is the only thing between a
    hand-edited JSONB blob and that constraint — without the ceiling here, a
    stored 5000 reaches the INSERT and answers a 500 on intake rather than a
    ticket. Without the lower bound, a negative estimate poisons every capacity
    number F42 derives from the column."""
    resolved = effort_bands(_settings({EffortBand.ONE_HOUR.value: stored}))
    assert resolved[EffortBand.ONE_HOUR] == DEFAULT_EFFORT_BANDS[EffortBand.ONE_HOUR]
    assert set(resolved) == set(EffortBand)


def test_the_ceiling_admits_exactly_the_checks_bound() -> None:
    """1440 is legal and 1441 is not, on the same boundary the DB CHECK pins —
    two places that must agree, asserted from both sides."""
    assert effort_bands(_settings({EffortBand.FULL_DAY.value: 1440}))[EffortBand.FULL_DAY] == 1440
    assert (
        effort_bands(_settings({EffortBand.FULL_DAY.value: 1441}))[EffortBand.FULL_DAY]
        == DEFAULT_EFFORT_BANDS[EffortBand.FULL_DAY]
    )
    assert effort_bands(_settings({EffortBand.THIRTY_MIN.value: 1}))[EffortBand.THIRTY_MIN] == 1


def test_an_unknown_band_key_in_the_stored_mapping_is_ignored() -> None:
    """The resolver iterates the ENUM, never the stored dict, so a key F42
    renames or a typo in a hand-edited blob cannot put a sixth band on the wire
    — which is what keeps the console's five choices five."""
    resolved = effort_bands(_settings({"a_week": 4800, "THIRTY_MIN": 1, "": 1}))
    assert resolved == DEFAULT_EFFORT_BANDS


def test_a_non_dict_settings_shape_still_resolves_five_bands() -> None:
    """`settings` is JSONB and nothing constrains its shape. A poll must not be
    able to 500 on it."""
    assert effort_bands({"atelier": "not a dict"}) == DEFAULT_EFFORT_BANDS
    assert effort_bands({"atelier": {"effort_bands": "not a dict"}}) == DEFAULT_EFFORT_BANDS
    assert effort_bands({"atelier": {"effort_bands": []}}) == DEFAULT_EFFORT_BANDS
