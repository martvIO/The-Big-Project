# Plan: Feature 27 — Full feature-toggle matrix UI (Epic E5)

**Spec**: `.planning/specs/toggle-matrix-ui.md` (2026-08-06, Gate 1 standing-approved, D1–D8)
**Design**: `.planning/design/screens/toggle-matrix-ui/design.md` (§0–§10, accepted by design-critic 2026-08-06; P1/P2/P3 adopted, F-T1–F-T4 owed to this plan)
**Plan written**: 2026-08-06. **NO MIGRATION** — toggles live in `tenants.settings` JSONB, keys in code (spec, verified: no schema change anywhere below). The renumber-at-rebase protocol is moot for F27; reserve no number.
**Depends on**: F7 (settings JSONB, `merge_settings`, `/manage/settings`) — merged.
**Worktree**: `.worktrees/toggle-matrix-ui`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. Backend registry → write-path safety → the D5 consumer → FE registry/types → matrix UI → e2e; the UI needs settled wire shapes. The spec's D1–D8 and the design's §1–§10 are binding and not restated. Every path below was verified against the tree on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| `_TOGGLE_FIELDS` frozenset literal; `validate_toggles` (unknown-key + isinstance-bool) | `Backend/app/boutique/validation.py:59,134` |
| `merge_settings` — one atomic `settings \|\| :patch::jsonb`; its docstring prescribes the deep-merge expression AND names the bare-`jsonb_set` no-op trap | `Backend/app/db/repositories/tenants.py:69-99` |
| `TogglesUpdate` (two optional fields) / `UpdateSettingsRequest.toggles` — `TogglesUpdate` referenced in schemas.py ONLY (backend grep) | `Backend/app/boutique/schemas.py:50,84-86` |
| `_settings_result`, `update_settings`, `_record_atelier_settings` (post-merge own-transaction audit pattern) | `Backend/app/boutique/service.py:89,128,161` |
| `AuditAction` StrEnum (atelier actions as naming precedent) | `Backend/app/models/constants.py:281,516-532` |
| Sole toggles reader: booking-create deposit gate (webhook/sweeper never read toggles) | `Backend/app/booking/service.py:113` |
| `list_appointment_types` already receives settings (D10 gateway read — the D5 seam); "no audience filter" comment to overwrite | `Backend/app/storefront/service.py:243,250` |
| F7 sibling-key concurrency test (db) — the model for the toggles-key version | `Backend/tests/test_boutique_service.py:343` |
| "THE WHOLE BLOCK, ALWAYS" clobber test — documents the OLD trap, changes deliberately under D2 | `Backend/tests/test_boutique_api.py:393` |
| Test homes exist: `test_boutique_validation.py`, `test_boutique_api.py` (fake-service style), `test_boutique_service.py` (db), `test_storefront_service.py`, `test_storefront_api.py` | `Backend/tests/` |
| `ToggleSettings` interface; `getSettings`/`updateSettings` | `Frontend/apps/manage/src/api.ts:111,123,142,1375,1378` |
| `ProfileSection.tsx` — `TogglesForm`, two inline `Toggle`s, `profile.settingsHeading` render | `Frontend/apps/manage/src/components/ProfileSection.tsx:17,43,148-159` |
| Old i18n keys to remove: `profile.settingsHeading/depositsEnabled/bridesOnly/bridesOnlyHint` | `Frontend/apps/manage/src/i18n/he.ts:41-44` (`ar.ts` mirrors) |
| `lib/toggles.ts` does not exist — free; `lib/guide.ts` profile steps (design §7: copy stays true, no reword) | `Frontend/apps/manage/src/lib/` |
| `@boutique/ui` `Toggle` — native checkbox `role="switch"`, label/description, shipped through a11y audit | `Frontend/packages/ui/src/components/Toggle.tsx` |
| `settingsPayload()` fixture with `toggles:` block; used by `manage.spec.ts` incl. the `AXE_SECTIONS` profile entry | `Frontend/e2e/fixtures/manage.ts:345,355`, `Frontend/e2e/manage.spec.ts:751-754,820+` |
| FE test homes exist: `ProfileSection.test.tsx`, `api.test.ts`, `i18n.test.ts`; `TogglesMatrix.test.tsx` free | `Frontend/apps/manage/src/__tests__/` |

## 2. Ordered task list

### Phase A — backend registry, registry-validated request model (commit 1)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | Registry (D1): `@dataclass(frozen=True) ToggleDef(key, default)`, `TOGGLES: tuple[ToggleDef, ...]` — entries `deposits_enabled` (False, consumer `booking/service.py:113` named in comment) and `brides_only` (False, consumer = D5's disclosure, named). `validate_toggles` derives its key set from `TOGGLES`; the `_TOGGLE_FIELDS` frozenset literal is **deleted**. Unknown-key and isinstance-bool behavior unchanged. | `test_boutique_validation.py` — registry has exactly the two keys with default False; `validate_toggles` accepts registry keys, rejects unknown key and non-bool **exactly as today** (existing assertions stay green); a key added to a copy of the registry is accepted (derivation proven, not duplicated literal) | C `Backend/app/boutique/toggles.py`, M `Backend/app/boutique/validation.py`, M `Backend/tests/test_boutique_validation.py` |
| A2 | Request model (D4): `UpdateSettingsRequest.toggles` becomes `dict[str, StrictBool] | None`; class `TogglesUpdate` deleted (schemas.py is its only backend reference — verified). Same JSON on the wire; unknown keys flow to registry-derived `validate_toggles` → house 400 `VALIDATION_ERROR`. | `test_boutique_api.py` (fake service, `test_auth_api.py` style) — PUT with single-key toggles dict wires through; `1` and `"true"` → 400 (StrictBool, the atelier vacuity trap); unknown key → 400 house shape; 401 without cookie; the router-level role-gate test stays green **unedited** | M `Backend/app/boutique/schemas.py`, M `Backend/tests/test_boutique_api.py` |

### Phase B — deep merge, defaults on the wire, audit (commit 2)

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | Deep merge (D2), toggles key ONLY: when a toggles patch is present, `merge_settings` SETs `settings || jsonb_build_object('toggles', coalesce(settings->'toggles','{}'::jsonb) || :toggles_patch)` merged over the rest of the patch — still ONE atomic statement, no Python read-modify-write. `profile`/`atelier`/`privacy` keep whole-block replace. **`coalesce` is mandatory** — bare `jsonb_set` silently no-ops on absent key = every untouched tenant (docstring's own warning). Update the docstring: the "day a deep merge is forced" arrived for `toggles`. | `test_boutique_service.py` (**db**) — **concurrent single-key writes to two different toggles both survive** (gather two `merge_settings` calls, assert both keys in final JSONB — `:343`'s pattern one level down); a toggles write preserves `profile`/`atelier`/`privacy` siblings; single-key patch against a tenant with NO toggles key lands (coalesce proven). The `test_boutique_api.py:393` whole-block-clobber test is **rewritten to assert the new invariant** (partial write preserves the sibling toggle) — a deliberate contract change, named in the commit body | M `Backend/app/db/repositories/tenants.py`, M `Backend/tests/test_boutique_service.py`, M `Backend/tests/test_boutique_api.py` |
| B2 | Defaults on the wire (D3): `_settings_result` returns `toggles` = registry defaults overlaid by stored values — every registry key present with a concrete bool. Consumers keep reading raw stored JSONB (absent=OFF) — zero consumer churn. | `test_boutique_service.py` (fast) — absent key → default; stored value wins; wire block's key set == registry key set; (**db**) GET after a partial write returns the full default-complete block | M `Backend/app/boutique/service.py`, M `Backend/tests/test_boutique_service.py` |
| B3 | Audit (D6): `AuditAction.TOGGLES_UPDATED = "toggles_updated"`; `update_settings` records a post-merge, own-transaction row when a toggles patch applied — `_record_atelier_settings`'s bounded pattern verbatim, `details` = the patch (changed keys only, no diff computation). `profile` stays unaudited (F42 boundary). | `test_boutique_service.py` (**db**) — row with actor id + patch details on a toggles write; **no row** on a profile-only write; audit failure does not roll back the merge (the atelier one-directional compromise) | M `Backend/app/models/constants.py`, M `Backend/app/boutique/service.py`, M `Backend/tests/test_boutique_service.py` |

### Phase C — the brides_only disclosure consumer (commit 3)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | D5: in `list_appointment_types` (settings already in hand), when `toggles.brides_only` is truthy every returned type's `audience` is disclosed as `brides_only`; per-type verbatim when off/absent. Disclosure only — booking-create keeps not checking audience; nothing in-flight touched. Replace the `:250` "no audience filter" comment with the D5 ruling + registry consumer pointer. | `test_storefront_service.py` (fast) — on → all rows `brides_only` regardless of per-type value; off and absent → per-type verbatim; `test_storefront_api.py` — same pair through the HTTP surface | M `Backend/app/storefront/service.py`, M `Backend/tests/test_storefront_service.py`, M `Backend/tests/test_storefront_api.py` |

### Phase D — FE registry, matrix card, i18n (commits 4–5)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | FE registry + types: `lib/toggles.ts` — `TOGGLES = [{ key: "brides_only", area: "storefront" }, { key: "deposits_enabled", area: "booking" }] as const` (design §2 area order: storefront → booking), derived `TOGGLE_KEYS`/`ToggleKey`. `api.ts`: `ToggleSettings` → `Record<string, boolean>` (wire default-complete, D3); `UpdateSettingsRequest.toggles?: Partial<Record<ToggleKey, boolean>>`. i18n `togglesMatrix.*` block lands here (he per design §7 table verbatim; `ar.ts` mirrors Hebrew values, pre-decided #47; zero exclamation marks). | `api.test.ts` — types compile against a single-key update call; `i18n.test.ts` — **every registry key has both `togglesMatrix.{key}.label` and `.hint` in he** (a row without copy is a red test), ar-presence guard binds on the new keys | C `Frontend/apps/manage/src/lib/toggles.ts`, M `Frontend/apps/manage/src/api.ts`, M `Frontend/apps/manage/src/i18n/he.ts`, M `…/ar.ts`, M `Frontend/apps/manage/src/__tests__/api.test.ts`, M `…/i18n.test.ts` |
| D2 | `TogglesMatrix.tsx` per design §2–§6: Card + SectionHeading h2 + hint line; area-grouped rows (h3 headings even at one row each — P2), one row per registry key from `TOGGLES`; row = shipped `Toggle`, `min-h-11` on the row (F-T2); per-row immediate save `updateSettings({ toggles: { [key]: value } })` → re-sync from response. **In-flight lock is a handler guard + `data-busy` dim, NOT the `disabled` attribute** (P1 — focus stays on the switch); failure → revert to pre-flip state + house error toast, no inline error; saved cue `common.saved` at inline-end, one `role="status"` region per card, cue clears on next flip. Initial data from the parent's existing `getSettings()` — no second GET. | `TogglesMatrix.test.tsx` (new) — one row per registry key, grouped under area headings; flip calls `updateSettings` with **exactly one key**; double-flip while pending is ignored (guard, and the input is never `disabled`); failure reverts + toast; saved cue announced once; no flip renders a confirm dialog | C `Frontend/apps/manage/src/components/TogglesMatrix.tsx`, C `Frontend/apps/manage/src/__tests__/TogglesMatrix.test.tsx` |
| D3 | `ProfileSection` integration (D7): render the matrix card under the profile form; shed `TogglesForm`, both inline `Toggle`s, toggles from the save payload (`updateSettings({ profile })` only); save button copy → «שמירת פרופיל» (`profile.save`). Remove dead keys `profile.settingsHeading/depositsEnabled/bridesOnly/bridesOnlyHint` — **grep both apps first (F-T4)**; if `settingsHeading` is referenced elsewhere, keep the key, drop only this renderer's use. Guide copy verified by design §7 — no `SectionKey` change, no guide edit expected; re-verify at build. | `ProfileSection.test.tsx` updated **deliberately** (spec trap: these assertions change; B1/B2's backend tests are the ones that must not weaken) — inline switches gone, save payload profile-only, matrix card mounts, button copy | M `Frontend/apps/manage/src/components/ProfileSection.tsx`, M `Frontend/apps/manage/src/i18n/he.ts`, M `…/ar.ts`, M `Frontend/apps/manage/src/__tests__/ProfileSection.test.tsx` |

### Phase E — e2e + axe + fixtures (commit 6)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | Extend `manage.spec.ts` + fixtures: `settingsPayload()` grows the **full default-complete toggles block** (both registry keys — this fixture is the D1 cross-tree drift tripwire: FE matrix test renders one row per wire key). Journeys: flip a row → interception asserts the **single-key PUT body** → row reflects the response; failed PUT → switch reverts + toast; **a row flip does NOT light the profile form's saved cue (F-T1)**; rendered row hit box ≥ 44px asserted (F-T2, not eyeballed); focus remains on the flipped switch through in-flight→saved (P1). `AXE_SECTIONS` profile entry: settled locator updated so the sweep runs **with the matrix rendered** — axe zero-violation stands (IS 5568 legal floor). RTL: switch at inline-start, saved cue inline-end. No gateway warning beyond the hint when flipping deposits on without a gateway (F-T3 — assert no new banner/dialog). | this IS the test | M `Frontend/e2e/fixtures/manage.ts`, M `Frontend/e2e/manage.spec.ts` |

## 3. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` or `s3` run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`-m 'not db'`) points at a CLOSED Postgres port by design (F21).** A test dialing a real DB without the `db` marker fails locally — that is correct behavior, not a bug. Every new db-touching test MUST carry the `db` marker.
- **The worktree has no `Backend/.env`.** Config-default tests behave differently than the main checkout (`.memory/local-env-breaks-config-tests` — there the failure is REAL if it appears).
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`.
- Write db-marked tests carefully against the spec's test plan; their first run is CI (`.memory/boutique-ci-first-run-surprises`).

## 4. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(boutique): toggle registry, registry-derived validation, dict-typed toggles request` — A1–A2.
2. `feat(boutique): toggles deep merge, default-complete wire, TOGGLES_UPDATED audit` — B1–B3 (body names the deliberate `test_boutique_api.py:393` contract flip).
3. `feat(storefront): brides_only audience disclosure` — C1.
4. `feat(manage): FE toggle registry, api types, togglesMatrix i18n` — D1.
5. `feat(manage): TogglesMatrix card with per-row save; ProfileSection sheds inline switches` — D2–D3.
6. `test(e2e): toggle matrix journeys, single-key PUT interception, axe` — E1.

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm build` before staging any `.ts`/`.tsx`.

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line (`.memory/silently-unexecuted-test-files`).

**Rebase watch**: F22 (`.worktrees/waitlist-join`) and queued F24/F25 may land first. No migration collision exists for F27, but expect conflicts in `he.ts`/`ar.ts`, `manage.ts` fixtures, and possibly `settingsPayload()`; if F23 has merged its `waitlist_enabled` registry row by rebase time, the matrix simply renders it — extend the fixture block, change nothing else (D8 is the proof this costs one line).

## 5. Risks this plan adds to the spec's list

- **R-A**: B1 touches the one write path every settings feature shares. The tripwire is F7's suite: every existing `merge_settings` test EXCEPT the named `:393` clobber test must pass unedited; if a second test wants editing, stop — the merge shape is wrong.
- **R-B**: D3's removal of `profile.settingsHeading` may break an unseen reference (F-T4) — the grep is a task step, not a hope; `i18n.test.ts` red is the backstop.
- **R-C**: jsdom cannot prove the P1 focus behavior (`.memory/jsdom-has-no-dialog` class of vacuity — focus assertions that pre-place focus prove nothing); the focus-stays-on-switch claim is E1's to prove in a real browser, not D2's.
- **R-D**: the `AXE_SECTIONS` profile entry currently settles on a profile-form textbox — if the settled locator is not updated (E1), the axe sweep can pass without the matrix mounted and the legal-floor claim is vacuous.
