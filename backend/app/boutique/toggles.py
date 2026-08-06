"""F27 D1 — the feature-toggle registry. ONE declaration point for the backend.

Everything downstream DERIVES from `TOGGLES`: `validate_toggles`' key set
(`validation.py`), the default-complete `toggles` block on the wire
(`service._settings_result`), and the request model's accepted keys
(`schemas.UpdateSettingsRequest`, via the validator). Nothing re-lists them.

⚠ A ROW WITHOUT A SHIPPED CONSUMER DOES NOT BELONG HERE. `brides_only` spent F7
declared, rendered and validated while NOTHING read it, and its shipped hint copy
promised behaviour that did not exist. The rule this file enforces by convention
and `test_boutique_validation.py` enforces by assertion: every entry names the
code that reads it, and a feature that has not shipped its consumer adds its row
in its own PR.

D8's growth protocol, in full, for the feature adding a toggle:
  1. one entry here, naming the consumer;
  2. the consumer read (absent key = the default below);
  3. the FE registry key + `togglesMatrix.{key}.label`/`.hint` in he.ts and ar.ts;
  4. the `settingsPayload()` e2e fixture key.
No schema edit (D4), no merge edit (D2), no matrix edit (D1 renders it), no
migration — the keys live in `tenants.settings` JSONB.
"""

import dataclasses


@dataclasses.dataclass(frozen=True)
class ToggleDef:
    key: str
    default: bool


TOGGLES: tuple[ToggleDef, ...] = (
    # Consumer: `app/booking/service.py` `deposit_due` — the master deposit gate,
    # read at booking-create and by the storefront's deposit disclosure.
    ToggleDef(key="deposits_enabled", default=False),
    # Consumer: `app/storefront/service.py` `list_appointment_types` — the
    # audience DISCLOSURE (D5). Disclosure-level, not enforcement: booking-create
    # does not check `audience`, because an anonymous visitor cannot be
    # classified as a bride.
    ToggleDef(key="brides_only", default=False),
)

TOGGLE_KEYS: tuple[str, ...] = tuple(toggle.key for toggle in TOGGLES)
TOGGLE_DEFAULTS: dict[str, bool] = {toggle.key: toggle.default for toggle in TOGGLES}
