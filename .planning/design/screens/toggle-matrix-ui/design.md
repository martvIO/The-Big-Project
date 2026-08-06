# Screen: Feature-toggle matrix (F27 — manage settings, Epic E5)

**Date**: 2026-08-06 · **Status**: DESIGN GATE OPEN — awaiting critic + copy approval · **Designer**: Claude (subagent)
**Consumes**: `.planning/specs/toggle-matrix-ui.md` (Gate 1 self-approved, D1–D8) · tokens rev 1 · `packages/ui` as shipped
**Copy**: every Hebrew row below needs APPROVAL before the gate closes. Register: calm, no exclamation marks (pre-decided #5).

---

## 0. Scope

One surface: `TogglesMatrix.tsx`, a new `Card` rendered by `ProfileSection` under the profile form (spec D7 — **no new `SectionKey`**, no nav row). It replaces the two inline switches; `ProfileSection` keeps its form, sheds `TogglesForm`, and its save button copy drops «והגדרות». Out of scope: rows for unshipped features (waitlist = F23, WhatsApp = F46 — spec D8), platform-operator overrides, any per-feature config beyond on/off.

**Extends, never invents**: the shipped `@boutique/ui` `Toggle` (verified `Toggle.tsx` — native `<input type="checkbox" role="switch">` wrapped in a `<label>`, `label`/`description` props, hint wired via `aria-describedby`, house `focusRing`, `disabled` prop). No new form-control pattern. Error path = house error `Toast` (`FloorPanel`'s no-optimistic-patch discipline, spec D7). Announcements = the nested `VisuallyHidden > span[role="status"]` shape (manage-booking §0 ruling), **one cue per card** (FloorPanel's one-cue precedent).

## 1. Save model — F7's shipped pattern, verified, and the recorded departure

Verified at `ProfileSection.tsx:88`: F7 shipped **page-level save** — one button «שמירת פרופיל והגדרות», one PUT carrying `{ profile, toggles }` with both toggle keys always present (the convention that protects the top-level-replace write path today).

The matrix departs deliberately (spec D2+D7): **per-row immediate save** — flip → `api.updateSettings({ toggles: { [key]: value } })` → row re-syncs from the response (server truth, D3). Safe only because D2's deep merge makes a single-key PUT structurally unable to clobber siblings. The profile form above keeps its shipped page-level button, copy «שמירת פרופיל». The matrix hint line («כל מתג נשמר מיד עם השינוי», §7) is what tells the owner the two halves of the screen save differently.

## 2. Layout — grouped by area (mobile 375; identical structure at 768/1440)

Groups render **only when they have rows**; area order is fixed: storefront → booking → (future areas — floor, messages — ship with their first row, D8). FE registry rows carry their area: `TOGGLES = [{ key, area }] as const` (`lib/toggles.ts`; `TOGGLE_KEYS` derived from it, D1 tests unchanged).

```
|  +----------------------------------------+ |
|  | Card, p-6, flex flex-col gap-4         | |
|  |  הפעלת תכונות                          | |  SectionHeading as="h2" — togglesMatrix.heading
|  |  כל מתג נשמר מיד עם השינוי.            | |  --text-sm --color-ink-muted — togglesMatrix.hint
|  |                                        | |
|  |  האתר הפומבי                           | |  h3, --text-sm font-medium — togglesMatrix.area.storefront
|  |  [✓] בוטיק לכלות בלבד      נשמר לפני רגע| |  Toggle row, min-h-11; saved cue inline-end
|  |      כל סוגי התורים יוצגו לכלות בלבד   | |  hint = Toggle description (aria-describedby)
|  |  ······· hairline --color-border ····· | |
|  |  תורים ותשלומים                        | |  h3 — togglesMatrix.area.booking
|  |  [ ] גביית מקדמות מופעלת               | |
|  |      מקדמה תיגבה בפועל רק אחרי         | |
|  |      שחשבון הסליקה של הבוטיק יחובר.    | |
|  |      כיבוי המתג אינו משפיע על תורים    | |
|  |      שנמצאים כבר בתהליך תשלום.         | |
|  +----------------------------------------+ |
```

- **One column at every width.** A settings list scans top-to-bottom; a multi-column grid at 1440 would be a new pattern for zero benefit and an RTL/tab-order hazard. 768/1440 change nothing but line length (hints cap at `max-w-prose`).
- Row = the shipped `Toggle` exactly: switch at inline-start (RTL: right), label + hint stacked after it. `min-h-11` + `py-1` on the row so the whole `<label>` hit area meets the 44px floor (F-W1; the 20px checkbox box is not the target — the label is, see F-T2).
- Data: the matrix takes its initial `toggles` from `ProfileSection`'s existing `getSettings()` fetch (one fetch, no second GET) and owns row state from there. Wire is default-complete (D3), so no `?? false` fallbacks.

## 3. The per-row hint IS the flip-consequence line (the warning-copy contract)

Every registry row's `.hint` must state, in one calm line, what a flip does and does not touch — verified against the spec's consumer audit (webhook and sweeper never read toggles; in-flight `pending_payment` bookings resolve unchanged after any flip; `brides_only` is disclosure on next storefront load, nothing in-flight):

- `deposits_enabled` — hint names the gateway precondition (reusing `guide.profile.3`'s shipped phrasing) **and** the in-flight guarantee: turning it off does not touch bookings already mid-payment. That sentence is true because only `booking/service.py:112` reads the toggle, at create time.
- `brides_only` — shipped hint verbatim («כל סוגי התורים יוצגו לכלות בלבד»), which D5 finally makes TRUE. Flip consequence is the hint itself; no in-flight state exists to warn about.
- **D8 contract for future rows**: a new registry row ships with a hint naming its flip consequence, written by the feature that owns the semantics. Illustrative shape only (F23 owns the real copy): disabling waitlist with waiting entries → «כיבוי מסתיר את ההצטרפות לרשימה באתר. נרשמות קיימות נשארות ברשימה.» ("Turning off hides the site's join option. Existing entries stay on the list.")

## 4. States — the single source

| # | State | Trigger | What the owner sees | Test hook |
|---|---|---|---|---|
| L | loading | section mounting | `ProfileSection`'s existing whole-section `Skeleton` — the matrix adds **no** loading UI | shipped path |
| LE | load error | `getSettings` fails | `ProfileSection`'s existing `role="alert"` line — matrix never mounts | shipped path |
| D | loaded | settings arrived | §2 card, every registry row, wire truth (D3) | one row per registry key |
| F | row in flight | flip → PUT pending | that row locked (flips ignored, `data-busy` dimming — P1, NOT the `disabled` attribute); other rows stay live | double-flip guarded |
| K | row saved | 200 | row re-syncs from response; «נשמר לפני רגע» (`common.saved`, reused) at the row's inline-end; card's one status region announces it; cue clears on the next flip anywhere | `role="status"` once |
| E | row save failed | non-200 / network | switch **reverts to its pre-flip state**; house error `Toast` (`errorMessage(error)`); no inline row error | revert asserted |

## 5. Keyboard, focus, aria (IS 5568 / WCAG 2.0 AA — legal floor)

- **Operation**: Tab reaches every switch in DOM order = visual order (groups top-to-bottom); **Space toggles** (native checkbox; Enter is a no-op — acceptable for `role="switch"`, Space is the required key); clicking anywhere on the label row toggles.
- **Aria**: the shipped `Toggle` contract as-is — `role="switch"` on the native input, native `checked` conveys on/off (no `aria-checked` duplication), label via wrapping `<label>`, hint via `aria-describedby`. Group headings are real `h3`s under the card's `h2`.
- **Focus**: the house rule (the mover is the state change) — a flip mounts nothing, so **focus stays on the switch** through in-flight, saved, and failed states. This is exactly why the in-flight lock must not be the `disabled` attribute (P1): disabling a focused native input drops focus to `<body>`, an SC 2.4.3 regression the spec's word "disabled" did not intend.
- **Announcements**: discrete outcomes only — saved (status region, `common.saved`), failure (the Toast's own alert). Never per keystroke, never on load.
- **axe-zero** in e2e on the profile section with the matrix rendered (spec test plan), visible `focusRing` on every switch, all-Hebrew copy so no `<bdi>` islands needed.

## 6. RTL + responsive notes

Logical properties only (qa-grep ban). The shipped `Toggle` lays out RTL natively — checkbox at inline-start, text after; the saved cue sits at inline-end via `ms-auto`. No LTR islands (no numerals, dates, or phones anywhere on this card). 375: rows wrap naturally, hints run multi-line. 768/1440: identical structure, `max-w-prose` on hints. Reduced motion: the saved cue and busy dimming are instant show/hide; only shipped `--motion-fast` transitions animate.

## 7. i18n — `togglesMatrix.*` (he.ts; `ar.ts` mirrors with Hebrew values, pre-decided #47)

| Key | Hebrew | English annotation |
|---|---|---|
| `togglesMatrix.heading` | הפעלת תכונות | "Feature switches" — card h2, replaces `profile.settingsHeading` |
| `togglesMatrix.hint` | כל מתג נשמר מיד עם השינוי. | "Each switch saves immediately when changed." — the per-row-save disclosure |
| `togglesMatrix.area.storefront` | האתר הפומבי | "The public site" — group h3 |
| `togglesMatrix.area.booking` | תורים ותשלומים | "Appointments and payments" — group h3 |
| `togglesMatrix.deposits_enabled.label` | גביית מקדמות מופעלת | "Deposit collection enabled" — shipped verbatim, no drift |
| `togglesMatrix.deposits_enabled.hint` | מקדמה תיגבה בפועל רק אחרי שחשבון הסליקה של הבוטיק יחובר. כיבוי המתג אינו משפיע על תורים שנמצאים כבר בתהליך תשלום. | "A deposit is only actually collected once the boutique's payment account is connected. Turning the switch off does not affect bookings already mid-payment." — gateway precondition (guide.profile.3 phrasing) + flip guarantee (§3) |
| `togglesMatrix.brides_only.label` | בוטיק לכלות בלבד | "Brides-only boutique" — shipped verbatim |
| `togglesMatrix.brides_only.hint` | כל סוגי התורים יוצגו לכלות בלבד | "All appointment types will be shown as brides-only" — shipped verbatim; TRUE with D5 |
| `profile.save` (changed) | שמירת פרופיל | "Save profile" — drops «והגדרות», spec D7 |

Reused, not minted: `common.saved` («נשמר לפני רגע») for the row cue and its announcement — the shipped he.ts comment already blesses this exact reuse. Removed with their renderer: `profile.depositsEnabled`, `.bridesOnly`, `.bridesOnlyHint`, `.settingsHeading` (grep before delete, F-T4). Vitest asserts every registry key has both `.label` and `.hint` (D1 — a row without copy is a red test, not a raw-key render).

**Guide copy verified now, not at build**: `guide.profile.2` and `.3` name both switches and say «נשמר כאן» — both remain true (the switches stay in the profile section; «נשמר» is truer under immediate save). **No reword needed, no `SectionKey` change.**

## 8. What this card deliberately does not have

No new nav section (D7) · no waitlist/WhatsApp rows (D8 — F23/F46 add their own) · no page-level save for toggles (D2 makes per-row safe; two save models on one screen is the point, disclosed by the hint line) · no optimistic UI (FloorPanel discipline — revert on failure) · no confirm dialog on any flip (every shipped row's flip is reversible and touches nothing in flight — §3; a future dangerous row argues for its own confirm in its own PR) · no per-row spinner (the busy dim + re-sync is enough; a poll-less settings card resolves in one round trip) · no second GET (parent's fetch feeds it) · no `<bdi>` islands (all-Hebrew card).

## 9. PROPOSED (user confirms at the gate)

- **P1 — in-flight lock is a handler guard, not the `disabled` attribute.** Spec D7 says "the row's switch is disabled" while in flight; literally disabling a just-flipped (therefore focused) native checkbox throws keyboard focus to `<body>`. Proposed: ignore flips while that row's PUT is pending, dim via `data-busy` styling, keep the input enabled and focused. Same observable lock, no focus loss. If the critic insists on literal `disabled`, focus must be restored to the input on re-enable.
- **P2 — group headings even at two rows.** Two groups of one row each looks sparse today, but the grouped skeleton is the D8 contract future rows land into (F23 → booking, F46 → a new messages area) — shipping it now means their PRs touch copy + registry only, never layout.
- **P3 — the saved cue is `common.saved` reused**, one Hebrew, no new key — and it doubles as the announced text (manage-booking P2 no-drift precedent).

## 10. ⚠ FINDINGS

- **F-T1**: the two save models coexist on one screen — the profile button's «נשמר לפני רגע» and the row cue use the same key and meaning; e2e must assert a row flip does NOT light the profile form's saved cue (separate state).
- **F-T2**: the `Toggle` checkbox box is `size-5` (20px). The 44px floor (F-W1) is met by the wrapping `<label>` row — enforce `min-h-11` on the row and verify the rendered hit box in e2e, not by eyeballing the checkbox.
- **F-T3**: flipping `deposits_enabled` ON with no gateway connected is legal and useful (owner prepares before connecting) — the hint plus the shipped `gateway.depositsWithoutGateway` banner already cover it; the matrix must NOT block or warn beyond the hint.
- **F-T4**: `profile.settingsHeading` («הגדרות») may be referenced outside `ProfileSection` — grep both apps before removal; if any other surface uses it, keep the key and remove only this renderer's use.

Design Gate: accepted by design-critic, 2026-08-06
