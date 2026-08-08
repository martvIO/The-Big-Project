// F27 D1 — the feature-toggle registry. ONE declaration point for the console.
//
// `TogglesMatrix` renders one row per entry, in this order, grouped by `area`;
// labels and hints resolve as `togglesMatrix.{key}.label` / `.hint`, and
// `i18n.test.ts` reds if either is missing — a row without copy is a failing
// test, never a raw key in the owner's console.
//
// ⚠ THIS LIST AND `Backend/app/boutique/toggles.py` MUST AGREE, AND NOTHING
// IMPORTS ACROSS THE TREES. What binds them is the e2e fixture: `settingsPayload()`
// carries the backend registry's full default-complete block (D3 puts every key
// on the wire), and the matrix renders one row per WIRE key — so a key added on
// one side only shows up as an extra or missing row assertion.
//
// Area order is fixed and shipping it at two rows is deliberate (design P2): the
// grouped skeleton is the contract D8's future rows land into, so F23's waitlist
// row and F46's messages area cost copy and a registry entry, never layout.
export const TOGGLES = [
  { key: "brides_only", area: "storefront" },
  { key: "deposits_enabled", area: "booking" },
] as const;

export type ToggleKey = (typeof TOGGLES)[number]["key"];
export type ToggleArea = (typeof TOGGLES)[number]["area"];

export const TOGGLE_KEYS: readonly ToggleKey[] = TOGGLES.map((toggle) => toggle.key);

// Groups render only when they have rows, and in this order.
export const TOGGLE_AREAS: readonly ToggleArea[] = [
  ...new Set(TOGGLES.map((toggle) => toggle.area)),
];
