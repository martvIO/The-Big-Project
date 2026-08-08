# Spec: F27 — Full feature-toggle matrix UI (Epic E5)

**Created**: 2026-08-06 · **Status**: **Gate 1: standing approval — interview-2026-07-30.md §Standing approvals** (Q1: F27 touches neither payments, refunds, privacy-law text nor billing — it self-approves; the named exceptions are F17/F18/F19/F20/F29/F48. `deposits_enabled` *gates* the deposit flow but F27 changes no payment code path — F7 shipped the same switch under the same rule) · **Epic**: E5 · **Effort**: S
**Depends on**: F7 (settings JSONB, atomic merge, `/manage/settings`) · **Feeds**: F23 (waitlist row), F46 (WhatsApp row), every later toggleable feature
**Pre-decided**: #19 — tenants.settings JSONB under the `toggles` key, via F7's atomic merge. No toggles table, no flag service.

---

## Problem

E2 #7 shipped the v1 subset of the PRD §2 toggle grid: two switches (`deposits_enabled`, `brides_only`) hard-coded into `ProfileSection.tsx`, a hard-coded `_TOGGLE_FIELDS` frozenset in `boutique/validation.py`, and a top-level-replace write path that silently clobbers sibling toggles on a partial write. Growing a row today means editing four unrelated files by hand and hoping nobody forgets one. F27 turns the subset into a registry-rendered matrix so a later feature (F23's waitlist, F46's WhatsApp — e10's brief already says "surfaced in F27's matrix") adds one registry entry plus one consumer and the UI, validation, defaults, and tests all follow by construction.

## Goal

The owner opens settings and sees the complete matrix of feature toggles — every toggle the platform actually honors, each with its label, its state, and an immediate per-row save that can never clobber a sibling. Hebrew-first RTL, `ar` keys untranslated, no exclamation marks, axe zero-violation (IS 5568 / WCAG 2.0 AA).

## Conflicts between the brief and shipped reality (recorded, codebase-consistent reading taken)

1. **"The full §2 grid" is not reproducible from the repo.** The 11-section PRD itself was never checked in; only architecture.md was ported. The operational definition taken (and the brief's own "grows a row whenever a later epic ships a toggleable feature" supports exactly this): **the matrix shows every toggle that has a shipped consumer, and nothing else.** No dead switches; unshipped features add their row in their own PR.
2. **`brides_only` is ALREADY a dead switch.** Verified: `_TOGGLE_FIELDS` declares it, `ProfileSection` renders it, and **no code reads it** — `storefront/service.py:250` explicitly declines the audience filter, `storefront/schemas.py:117` says "`toggles` is not read at all", and the "real enforcement waits for a client identity (E5)" note was never picked up by F24. Worse, the shipped hint copy («כל סוגי התורים יוצגו לכלות בלבד», `he.ts:44`) promises disclosure behavior that does not exist. F27 wires the promised **disclosure** consumer (D5) rather than dropping a shipped owner control.
3. **The waitlist row belongs to F23, not F27.** `specs/waitlist-join.md` Out-of-scope rules it in as many words: "F27's matrix grows a row when F23 makes the feature externally visible; an entries model with no offers needs no switch." F22 is building now; F23 is queued unspec'd — if F23 has merged by F27's build slot, its row simply already exists in the registry and the matrix renders it.

## What already exists to build on (verified against code)

- **Write path**: `TenantsRepository.merge_settings` (`db/repositories/tenants.py:69`) — one atomic `settings = settings || :patch::jsonb`, top-level keys `profile/toggles/atelier/privacy`. Its own docstring names both the shallow-merge trap and the prescribed deep-merge expression for "the day a genuine deep merge is forced": `settings || jsonb_build_object('toggles', coalesce(settings->'toggles','{}'::jsonb) || :patch)`. F27 is that day (D2).
- **API**: `GET/PUT /manage/settings` (`boutique/router.py:49-74`), router-level `require_role(OWNER, SHIFT_MANAGER)`. `TogglesUpdate` (two optional fields, `exclude_unset`) — **latently unsafe**: a partial toggles patch replaces the whole `toggles` key; only the convention that `ProfileSection` always sends both fields protects it today.
- **Validation**: `validate_toggles` (`boutique/validation.py:134`) — unknown-key rejection + `isinstance(value, bool)` (the anti-coercion check the atelier docstring proved necessary).
- **Consumers of `toggles` today**: `booking/service.py:112-113` — `deposits_enabled`, read at booking-create only, absent=OFF, ANDed with per-type `deposit_required`, amount > 0, and gateway connected+valid; plus the storefront deposit disclosure (`storefront/service.py list_appointment_types`). ⚠ **THIS CLAIM WAS WRONG AND THE CORRECTION IS A PUBLIC BEHAVIOR CHANGE — see "Blast radius" below.** The spec asserted the route "already receives `settings`"; it did not. `storefront/router.py list_appointment_types` called the service with no `settings=` at all, so the argument arrived `None`, `deposit_due` answered False for every row, `hide_deposit()` cleared the pair, and the deposit disclosure D10 shipped has been dead on the live storefront since F17. Webhook and sweeper do **not** read toggles (verified — only reader is booking/service.py:112), so in-flight `pending_payment` bookings resolve unchanged after any flip.
- **Audit precedent**: `_record_atelier_settings` (`boutique/service.py:161-196`) — post-merge audit row in its own transaction, a recorded one-directional bounded compromise. `profile`/`toggles` are unaudited today by F42's "don't widen a gap you didn't create" — F27 *owns* the toggles key now, so the same «nobody can say who or when» argument applies to it (D6).
- **Frontend**: `ProfileSection.tsx` renders the two switches inside the profile form (saved by the one «שמירת פרופיל והגדרות» button); `ToggleSettings` in `api.ts:111` is two optional fields; `@boutique/ui` `Toggle` is a native checkbox with `role="switch"` (shipped through the a11y audit). Nav/`SectionKey` is a closed 15-member union with a `satisfies Record<SectionKey, steps>` guide gate — a new section costs a guide entry (avoided, D7).
- **Provisioning seeds no toggles** — absent keys are the norm; defaults must come from the registry.
- **No migration needed** — JSONB, keys live in code. (No number to reserve; the renumber-at-rebase protocol is moot for F27.)

## Scope

**IN**
- Typed toggle registry, backend + frontend, single declaration point per side (D1).
- Deep merge for the `toggles` key in `merge_settings` — single-key writes never clobber siblings, structurally (D2).
- Registry defaults merged into `GET /manage/settings` responses (D3).
- `UpdateSettingsRequest.toggles` becomes registry-validated `dict[str, StrictBool]` (D4).
- The `brides_only` disclosure consumer F7 promised and the shipped hint copy already claims (D5).
- Audit row on toggle changes (D6).
- Matrix UI: `TogglesMatrix.tsx` card in the profile section, per-row immediate save; `ProfileSection` drops its two inline switches (D7).
- i18n `togglesMatrix.*` (he + ar untranslated), fixtures, tests, e2e + axe.

**OUT
- Per-feature configuration beyond on/off (deposit amounts stay on appointment types; atelier bands, privacy text stay in their own blocks).
- Platform-operator overrides (owner-facing only; the console is F25's territory).
- Rows for unshipped features: waitlist (F23 adds it — recorded ruling), WhatsApp (F46, e10 brief already assigns it), reservations (F28), and any F47/F48 surface.
- Retrofit kill-switches for shipped un-toggled features (walk-in queue, floor, portal, catalog…) — each is consumer wiring with its own in-flight semantics and earns its own PR; the registry makes that PR small.
- Role-gate changes: `/manage/settings` stays router-level OWNER + SHIFT_MANAGER, as F7 shipped it (recorded, not re-argued).

## Design

### D1 — The registry: one declaration point per side, a missing consumer impossible by construction

- **Backend** `app/boutique/toggles.py`: `@dataclass(frozen=True) class ToggleDef: key: str; default: bool` and `TOGGLES: tuple[ToggleDef, ...]`. Each entry's docstring/comment **must name its consumer path** — the registry test suite renders that contractual: a toggle key present in the registry but absent from the wire, the validation, or the FE registry reds a test. Initial contents:
  - `deposits_enabled` (default False) — consumer `booking/service.py` deposit gate + storefront disclosure.
  - `brides_only` (default False) — consumer `storefront/service.py` audience disclosure (D5, wired by this feature).
- `validate_toggles`'s `_TOGGLE_FIELDS` is **derived from the registry** (the frozenset literal is deleted); unknown-key and isinstance-bool behavior unchanged.
- **Frontend** `apps/manage/src/lib/toggles.ts`: `TOGGLE_KEYS = ["deposits_enabled", "brides_only"] as const` (+ derived `ToggleKey` type). The matrix renders **from this list**, labels/hints resolved as `togglesMatrix.{key}.label` / `.hint`. A Vitest asserts every key has both he strings (a registry row without copy is a red test, not a raw-key render).
- The two lists are asserted equal indirectly: the e2e interception fixture's `settingsPayload()` carries the full backend registry as its `toggles` block, and the FE matrix test renders one row per wire key — drift shows up as an extra/missing row assertion.

### D2 — Deep merge for `toggles`: partial writes become structurally safe

`merge_settings` gains the docstring's own prescribed expression **for the toggles key only**: when a toggles patch is present, the SET expression wraps it as `jsonb_build_object('toggles', coalesce(settings->'toggles', '{}'::jsonb) || :toggles_patch)` merged over the rest of the top-level patch — still ONE atomic statement, still no Python read-modify-write. `profile`/`atelier`/`privacy` keep whole-block-replace semantics (their "one writer always sends the whole block" models are load-bearing and untouched).

Why now and not "one writer sends all keys": the matrix saves per-row (one key per PUT), and the whole-block convention has a silent failure mode the moment the registry grows — a browser running a **stale cached bundle** saves the keys it knows and wipes a newer feature's toggle back to absent. Deep merge kills that class of bug permanently and makes the shipped `TogglesUpdate` partial semantics *correct* instead of latently wrong. Concurrent single-key writers of two different toggles both survive — proven by a db-marked test, the F7 sibling-key concurrency test one level down.

### D3 — Defaults on the wire

`_settings_result` returns `toggles` as **registry defaults overlaid by stored values** — the wire always carries every registry key with a concrete bool. The FE `?? false` fallbacks disappear; the matrix renders wire truth. Consumers (booking deposit gate) keep reading the raw stored JSONB with absent=OFF — behavior identical, so no consumer changes ride along **from D3 itself**.

> ⚠ **BLAST RADIUS — ONE CONSUMER DOES CHANGE, AND IT IS A PUBLIC MONEY SURFACE. NAME IT IN THE PR BODY AND AT THE E5 GATE.** D5 needs `toggles` on `GET /storefront/appointment-types`, and wiring `settings=tenant.settings` into that route (see the corrected fact above) also revives the F17/D10 deposit disclosure that has been dead since it shipped. From this deploy onward, a boutique with `deposits_enabled=true`, a connected gateway and a `deposit_required` appointment type shows «נדרשת מקדמה» plus the amount to every anonymous visitor on types that showed nothing yesterday (`TypePicker.tsx`). That is the intended, correct behavior and the fix stands — but it is a change to what the public page says about money, it was not in scope when this spec was written, and storefront e2e mocks the network so no gate catches it. It is disclosed here rather than merged as a side effect of a settings card.

### D4 — Request model: the registry is the schema

`UpdateSettingsRequest.toggles` becomes `dict[str, StrictBool] | None` (replacing the `TogglesUpdate` class — same JSON on the wire). `StrictBool` because plain `bool` coerces `1`/`"true"` before `validate_toggles`' isinstance check runs, making it unreachable — the exact vacuity trap the `AtelierSettingsUpdate` docstring documents. Unknown keys pass pydantic and are rejected by registry-derived `validate_toggles` → house 400 `VALIDATION_ERROR` (existing path, unchanged shape). F46 then adds a toggle by touching the registry, its consumer, and copy — **no schema edit**.

### D5 — The `brides_only` consumer: disclosure, exactly as promised

In `storefront/service.py list_appointment_types` (settings already in hand for the D10 gateway read): when `toggles.brides_only` is truthy, every returned type's `audience` is disclosed as `brides_only`. That is the semantics F7's spec wrote ("when true … treat every appointment type as brides-only regardless of per-type `audience`") and the shipped hint copy already tells the owner. **Disclosure-level, not enforcement** — consistent with the shipped position (`storefront/schemas.py:192`: "`audience` is DISCLOSED, not enforced: an anonymous visitor cannot be classified"); booking-create keeps not checking audience. Flip semantics: label changes on next storefront load; nothing in-flight is touched; no booking is blocked.

### D6 — Audit: `TOGGLES_UPDATED`

`AuditAction` gains `TOGGLES_UPDATED`; `update_settings` records a row when a toggles patch was applied — same post-merge, own-transaction, one-directional-loss compromise as `_record_atelier_settings`, same justification verbatim: `deposits_enabled` changes whether money is collected, and «nobody can say who or when» is the worse state. `details` = the patch (the changed keys only — the trail is the history, previous value is the previous row, no diff computation). `profile` stays unaudited (F42's boundary respected: F27 audits the key it now owns).

### D7 — Frontend: a matrix card, not a new section

New `components/TogglesMatrix.tsx`, rendered by `ProfileSection` as its own `Card` + `SectionHeading` under the profile form. **No new `SectionKey`** — a sixteenth member costs a nav row, a guide-steps entry (the `satisfies` gate makes its absence a type error), and e2e walker churn, for zero owner benefit; the profile section is already the settings home.

- One row per FE-registry key: label, hint, `@boutique/ui` `Toggle` (native checkbox, `role="switch"` — correct semantic here, unlike the consent case the walk-in spec records). Row hit target ≥ 44px (F-W1 floor; `Toggle` shipped through the a11y audit).
- **Per-row immediate save**: flip → `api.updateSettings({ toggles: { [key]: value } })` → re-sync from the response (server truth, D3). While in flight the row is locked (by a handler guard, not `disabled` — design P1: disabling a focused checkbox drops focus to `<body>`); on failure the house error toast shows and the card **re-fetches `getSettings` and repaints from server truth**, reverting to the pre-flip value only if that re-fetch also fails (`FloorPanel`'s no-optimistic-patch discipline, without the poll machinery — settings has no poll). ⚠ Amended at review round 1: a blind revert was wrong because the audit row is written *after* the merge commits, so a 500 can arrive with the toggle already persisted.
- `ProfileSection` sheds `TogglesForm`, the two inline `Toggle`s, and toggles from its save payload (`updateSettings({ profile })` only). The profile save button copy drops «והגדרות» → «שמירת פרופיל».
- `api.ts`: `ToggleSettings` becomes `Record<string, boolean>` (wire carries all registry keys per D3); `UpdateSettingsRequest.toggles?: Partial<Record<ToggleKey, boolean>>`.
- **i18n** (`he.ts` + `ar.ts` untranslated): `togglesMatrix.heading`, `.hint`, and per key `.label`/`.hint`. Reuse the shipped Hebrew verbatim: `deposits_enabled` ← «גביית מקדמות מופעלת» (+ new hint naming the gateway precondition: a deposit is only demanded when a gateway is connected — GatewaySection is the pointer), `brides_only` ← «בוטיק לכלות בלבד» / «כל סוגי התורים יוצגו לכלות בלבד» (hint becomes TRUE with D5). Old `profile.depositsEnabled`/`bridesOnly`/`bridesOnlyHint` keys removed with their renderer. Zero exclamation marks.
- Guide (`lib/guide.ts`): profile section's step copy mentions settings — verify at build time; if a step names the switches, reword within the existing steps (no `SectionKey` change).

### D8 — Growth protocol (the contract later features build against)

A feature shipping a new toggle lands, in its own PR: ① backend registry entry (key, default, consumer named), ② the consumer read (absent=default), ③ FE registry key + `togglesMatrix.{key}.*` he/ar strings, ④ `settingsPayload()` fixture key. Nothing else — no schema edit (D4), no merge edit (D2), no matrix edit (D1 renders it), no migration (JSONB). The registry tests red on any forgotten step. First customers: F23 (`waitlist_enabled` — its spec owns disable-with-waiting-entries semantics; the recorded shape is hide the join CTA, keep the manage list readable), F46 (`whatsapp_enabled`, per e10's brief).

## API summary

No new endpoints, no vite/proxy changes, no `_RESERVED_SEGMENTS` change, no migration. `GET /manage/settings` (toggles now default-complete) and `PUT /manage/settings` (toggles now dict-typed, deep-merged) — wire-compatible with every shipped caller.

## Test plan

- **Fast lane (unit)**: registry↔`validate_toggles` derivation (unknown key, non-bool rejected); `_settings_result` default overlay (absent key → default, stored value wins); D5 audience-override shaping (on → all `brides_only`, off → per-type verbatim).
- **db-marked**: deep-merge proof — **concurrent single-key writes to two different toggles both survive** (gather two `merge_settings` calls, assert both keys in final JSONB); toggles write preserves `profile`/`atelier`/`privacy` siblings (F7's concurrency test extended); `TOGGLES_UPDATED` audit row with actor id + patch details, none on profile-only writes; GET after a partial write returns the full default-complete block.
- **API (fake service, `test_auth_api.py` style)**: PUT with single-key toggles dict wires through; `1`/`"true"` → 400 (StrictBool); unknown key → 400 house shape; 401 without cookie; role gate unchanged (router-level test untouched — assert no route lost it).
- **Storefront API**: `brides_only` on/off against the type-list disclosure.
- **FE Vitest**: `TogglesMatrix.test.tsx` — one row per registry key; flip calls `updateSettings` with exactly one key; in-flight disable; failure reverts + toast; i18n coverage (every registry key has he label+hint). `ProfileSection.test.tsx` updated: switches gone, save payload profile-only.
- **e2e (Playwright + axe, extend `manage.spec.ts` + fixtures)**: `settingsPayload()` grows the full toggles block; flip a row → interception asserts the single-key PUT body → row reflects response; **axe zero-violation** on the profile section with the matrix rendered (the a11y sweep covers the section — assert the matrix is present when it runs); RTL; visible focus on every switch.

## Traps (for the plan)

- `git add` pathspecs lowercase (`backend/…`, `frontend/…`); reads capitalized.
- The deep-merge expression must use `coalesce(settings->'toggles','{}'::jsonb)` — bare `jsonb_set` silently no-ops when the key is absent (that is every un-touched tenant); the `merge_settings` docstring documents this exact failure.
- Do not let plain `bool` back into the request model — coercion makes `validate_toggles`' isinstance check unreachable (shipped precedent: `StrictInt` on atelier).
- Removing `TogglesUpdate` touches its import sites and the FE `ToggleSettings` type — grep both trees, run both builds.
- `ProfileSection`'s existing tests assert the toggles-in-form behavior — they change, deliberately; the D2/D3 backend tests are the ones that must not weaken.

## Decisions log

| # | Decision | Basis |
|---|---|---|
| D1 | Typed registry each side; matrix renders from it; consumer named per entry | brief's "grows a row" protocol; dead switches impossible |
| D2 | Deep merge for `toggles` key only; per-key writes structurally safe | merge_settings docstring's own prescribed expression; stale-bundle clobber |
| D3 | Wire carries default-complete toggles; consumers keep absent=OFF reads | one truth on the wire, zero consumer churn |
| D4 | `dict[str, StrictBool]` + registry validation replaces the field-per-toggle model | one declaration point; F46 adds no schema edit |
| D5 | Wire brides_only's promised disclosure consumer instead of shipping/keeping a dead switch | shipped hint copy already claims it; F7 spec defined it |
| D6 | Audit toggle changes (`TOGGLES_UPDATED`), atelier's bounded pattern | deposits_enabled moves money-collection behavior |
| D7 | Matrix is a card in the profile section; per-row immediate save; no new SectionKey | guide-gate + nav cost for zero benefit; FloorPanel mutation discipline |
| D8 | Unshipped rows OUT; F23/F46 add their own (recorded in their briefs/specs) | waitlist-join OUT ruling; e10 F46 brief; no dead switches |

## Open questions (non-blocking)

- Should SHIFT_MANAGER keep write access to the matrix, or should toggle writes tighten to OWNER-only when a genuinely dangerous row (WhatsApp channel switch) lands? Shipped gate kept for F27; F46 revisits.
- Whether the pilot wants kill-switches for the walk-in queue or portal — if asked, each is a small registry-protocol PR (D8), not a matrix change.
