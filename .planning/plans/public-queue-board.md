# Plan: Feature 59 — Public wall-screen queue board (`/queue`) (Epic E6, floor-management program)

**Status**: Gate 2 self-approved 2026-08-03 under Interview Q1. The corrections **C1–C13** below are amended into the spec and the design deck in Task 0; **those two documents are the binding statement of each resolution, this file the reasoning.**

**Spec**: `.planning/specs/public-queue-board.md` (936 lines, D1–D14, 34 review findings — 31 applied, 3 rejected) · **Design**: `.planning/design/screens/public-queue-board/design.md` (498 lines, W-1…W-15, F-1…F-14) + `copy.md` (167 lines) · **Critic verdict**: REVISE, ten required changes, folded in below as **C1–C10** · **Branch**: `feature/public-queue-board` · **Worktree**: `.worktrees/public-queue-board` · **Created**: 2026-08-03

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files (✚ = new), then how to verify, then the commit message.

**`db`-marked tests RUN LOCALLY on this feature, and that is what has made the last five features green on their first CI run.** Postgres 16.14 is live via Homebrew (socket `/tmp`, superuser `mrwen`, no Docker). The mechanism is a temporary `LOCAL_TEST_PG_URL` escape hatch in `Backend/tests/conftest.py`.

> ⚠ **THE conftest ESCAPE HATCH IS LOCAL-ONLY AND MUST BE REVERTED BEFORE EVERY COMMIT.** It is **not applied** on this tree right now — `git status --short` is clean of `backend/tests/conftest.py`, verified 2026-08-03. Every committing task below carries `git diff --stat` + an explicit `git checkout -- backend/tests/conftest.py` in its Done-when checklist. A commit carrying those lines ships a `LOCAL_TEST_PG_URL` escape hatch into the test harness on main.

**Path hygiene.** The repo path contains a space and a `+`. **Quote every shell path.** And git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` silently skips modified tracked files. Lowercase every pathspec and verify every commit with `git show --stat`.

**`make lint` runs `frontend/scripts/qa-greps.sh`, which greps WHOLE FILES INCLUDING COMMENTS.** Verified: bare `grep -rnE` at `qa-greps.sh:23` over `apps/storefront/src` (`:17`). English prose can fail the build with no code defect. Three live hazards for this feature's comment-heavy style: the literal `localStorage` (`:33`), the physical-direction pattern `[^a-zA-Z-](ml-|mr-|pl-|pr-|left-|right-|text-left|text-right|border-l-|border-r-)` (`:40`) which matches ordinary English like «left-hand» and «right edge», and a bare 6-digit hex (`:42`) — and this deck's §6 quotes `#F6F0E6` and `#FDFBF7`, so **no colour hex may be copied into a source comment.** Every task that writes storefront source or comments repeats this warning.

---

## What moved since the spec was written — re-verified against `main` at PR #36's merge commit

The spec and the deck were written the same day against the merged F33 tree, and **most of their citations hold.** I re-opened every load-bearing one. What follows is only what is wrong or newly true.

| The document says | Actually, on this tree | Correction |
|---|---|---|
| Deck §1.3: "Spacing utilities (`pt-6`, `gap-6`, `py-2`) are px literals from `theme.css` and do **not** grow under the root-font-size boost" | **False twice.** `--space-*` (`packages/ui/src/theme.css:55-62`) is not a Tailwind v4 theme namespace and drives no utility — it is consumed only through `var()` (e.g. `--space-a11y-footprint`, `StorefrontLayout.tsx:146`). The utilities come from Tailwind's own `--spacing: 0.25rem` (`node_modules/.pnpm/tailwindcss@4.3.3/…/tailwindcss/theme.css:325`), and the repo's own e2e comment says so: *"the viewport does NOT shrink, so every rem-sized box grows"* (`e2e/storefront.spec.ts:1391-1392`) | **C1** |
| Deck §1.2: 1366×768 at "0.595 mm/px (32" panel)" | 0.595 is 812.8/1366, and 812.8mm is a 32" **diagonal**. A 32" 16:9 panel is **708.4mm wide** → **0.5186 mm/px**. (The 1920 row is right: the deck correctly uses 1217.7mm of *width* for 55".) | **C2** |
| `copy.md` §2 + §7: "`{{count}}` renders inside `<bdi dir="ltr">`", citing `BoardSection.tsx:603` | That call site is `isolateLtr(t("board.truncated", …), …)`, and `isolateLtr` is `apps/manage/src/lib/booking.tsx` — **manage-only.** Verified by grep: every storefront `<bdi dir="ltr">` (`QueuePositionPage.tsx:307`, `:332`; `StorefrontLayout.tsx:168`, `:178`) is a value appended *beside* a `t()` label, never a numeral embedded *inside* one | **C3** |
| Deck §0 and §7.3: `prefers-reduced-motion` at `theme.css:165-173` | That block is **`:155-163`**. `:165-173` is the A11yMenu boost group (`:166-169` contrast, **`:170-172` text-size**). Every `:170-172` citation in both documents is correct | **C8** |
| Deck §6 / F-10: `Skeleton variant="text"` renders "five of them pulsing" | `Skeleton.tsx:16` — `lines = 3` by default. The finding holds at three; the number is wrong | **C9** |
| Spec Testing: `test_queue_repositories.py`'s `_seed()` helper at `:55-64`, hardcoding `name="נועה"` at `:72` | Signature is **`:55-65`**; `name="נועה"` is at **`:73`**. The widening instruction itself is right | **C11** |
| Spec D2 / Risk: the migration situation | `Backend/migrations/versions/` head is **`0018_queue_tickets.py`** (F33's). F19's `0016_deposit_flow`, F53's `0017_customer_crm_fields` and F57's `0015_floor_roles` are all merged. **F59 adds no migration**, so this number is context, not an instruction | **C12** |
| Spec D1: `main.py`'s include comment "becomes false and this PR rewrites it" | Confirmed at `:1206-1211` — but note it opens **"The FIFTH /storefront sibling"**, and that ordinal is **still correct**: F59 adds a route to an existing router, not a sibling. Only the "*its position read, both POSTs*" half becomes false | **C13** |

### Citations re-captured — ✅ verified on this tree, do not re-check

- ✅ `Backend/app/queue/router.py` — module docstring `:1-33` (its "two anonymous, tenant-scoped POSTs" at `:1`, "**BOTH** routes are POSTs" at `:10`, the capability paragraph at `:18-22`), `get_queue_service` `:46-48`, `_no_store` `:51-56`, `router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])` `:59`, `Queue` alias `:61`, `get_current_tenant(request)` as the first statement of each handler at `:69` and `:81`.
- ✅ `Backend/app/queue/schemas.py` — module docstring `:1-8`, `TicketView` `:44-70` with the **NAME omission rationale at `:52-55`** (conflict 8's target) and the capability comment `:61-63`.
- ✅ `Backend/app/queue/validation.py` — module docstring `:1-7` ("the two error classes and the **one** bound F33 owns" at `:1`), `CheckinThrottledError` `:18-32` with the never-about-a-person rule at `:29-31`, `QueueTicketNotFoundError` `:35-43`.
- ✅ `Backend/app/queue/service.py` — module docstring `:1-26` ("**Three** limiter instances" at `:20`), `__init__` `:48-62`, `_now()` `:64-66`, the one-clock-read comment `:100-102` and `now = self._now()` `:103`, `today_jerusalem(lambda: now)` `:108`, the hit/miss asymmetry docstring `:120-134`.
- ✅ `Backend/app/db/repositories/queue_tickets.py` — class docstring `:11-19` with the **no-read-keyed-on-`phone`** promise at `:15-18`, `insert` `:21-47` (its "F58 owns every one of them" docstring `:32-35`), `by_id` `:49-57`, `position` `:59-89`: docstring `:62-77`, `sort_key` `:80`, `mine` `:81`, the four predicates `:82-88`, `+ 1` `:89`.
- ✅ `Backend/app/models/queue_ticket.py:23-26` — Ruling 3's consequence on the shipped table, verbatim.
- ✅ `Backend/app/core/config.py` — the storefront read budget `:159-171`, the `checkin_*` block **`:173-196`** (the comment F59's two fields copy is `:184-187`, "A 5-second poll is 12/60s, so 30 is 2.5x headroom"), the fields at `:182-183`, `:188-189`, `:195-196`.
- ✅ `Backend/app/main.py` — the `QueueService` construction `:729-752` under the **THREE limiter instances** comment `:714-728`, the miss-limiter trap comment `:743-746`, `CheckinThrottledError` handler `:1131-1134`, the `queue_router` include comment `:1206-1211` and the include itself `:1212`, `_register_spas(app)` **last** at `:1215`, `_RESERVED_SEGMENTS = frozenset({"manage", "storefront"})` at `:345`.
- ✅ `Backend/tests/test_storefront_api.py` — `ROUTES` **derived** `:186-192` with the non-vacuity assert `:195`; **five** `@pytest.mark.parametrize("path", ROUTES)` sites at `:519`, `:544`, `:554`, `:689`, `:1222`; `_client(` at **`:494`**; the explicit `/storefront` literal `:564-...` with its "adding a public surface must fail one test on purpose" docstring `:569-571`; `test_the_read_throttle_is_not_inert` `:1222-1234`.
- ✅ `Backend/tests/test_spa_serving.py` — `SHELL_PATHS` `:70-85` (already carrying `/checkin` `:82` and `/q/tick3t` `:83`); `test_the_manage_dev_proxy_names_every_manage_api_segment` `:377-405`, reading **`apps/manage/vite.config.ts`** against `r'"\^/manage/\(([a-z|-]+)\)"'` at `:403`.
- ✅ `Frontend/apps/storefront/vite.config.ts:11-18` — proxies `"/storefront"` and `"/health"` **wholesale**, no alternation, and an explicit "No /manage entry" comment. **This is why F59 needs no vite edit.**
- ✅ `Frontend/apps/storefront/src/routes/QueuePositionPage.tsx` — `pageClass` `:19` (`max-w-[640px]`, `pb-16`), `POLL_INTERVAL_MS` `:23`, `MAX_BACKOFF_MS` `:29`, `CLOSED_STATUSES` `:35`, the multi-line `Intl.DateTimeFormat` `:41-46`, `schedule()` **the one arming site** `:105-118` with `document.hidden` at `:111`, `load()` `:125-181` with the generation compared at **`:129`, `:151` and `:177`**, the closed terminal `:139-143`, the called announce `:144-149`, the `isNotFound` terminal `:158-163`, `loadedRef` stale-not-blank `:166-170`, backoff `:138`/`:171`, `tick()` `:183-188` with `document.hidden` at `:184`, `tickRef` with **no dependency array** `:191-193`, **`runningRef.current = true` as the first line of the mount effect `:201` under the StrictMode comment `:196-200`**, **`runningRef.current = false` at `:211` BEFORE `clearTick()` at `:212`** under the orphan-loop comment `:204-210`, `visibilitychange` `:217-237`, `pause`/`resume`/`retry` `:239-263`, the freshness derivation `:270-275`, the loading `role="status"` + `Skeleton` `:281-288`, the **`live &&` gate `:295`**, the freshness span `:297-308` with the `text-warning-text` escalation at **`:305`** and `<bdi dir="ltr">{freshTime}</bdi>` at `:307`, the pause `<Button variant="ghost" size="md">` `:309-315`, the error arm `:351-362` with **`checkin.retry`** at `:358`, the one cue region `:372-379`.
- ✅ `Frontend/apps/storefront/src/router.tsx` — `RouteName` `:25-33`, `RouteMatch` `:43-56`, `DOC_TITLE_KEYS` `:66-83`, the **/queue disjointness comment** `:91-96` and `QUEUE_PATH` `:96`, `matchRoute` `:112` with the exact matches `:114-116`, the switch `:332-355` with the ⚠ at `:347-352` and `default: return <CatalogPage />` `:353-354`.
- ✅ `Frontend/apps/storefront/src/components/StorefrontLayout.tsx` — `<main id={MAIN_ID} tabIndex={-1} className="flex-1">` `:127-129`, the footer `:146` (`border-t border-border px-4 pt-6 [padding-block-end:var(--space-a11y-footprint)]`) under the "belongs HERE and not on a page div" comment `:132-145`. **It renders footer links only — no boutique name on any route** (F-5 confirmed).
- ✅ `Frontend/packages/ui/src/theme.css` — `--space-*` `:55-62`, `--space-a11y-footprint: calc(44px + var(--space-4) + var(--space-2))` **`:93`**, `--text-3xl: 2.25rem` `:52`, `prefers-reduced-motion` **`:155-163`**, `:root[data-a11y-text-size] { font-size: 1.2rem }` **`:170-172`**.
- ✅ `Frontend/packages/ui/src/components/Button.tsx` — `ghost: "bg-transparent text-ink hover:bg-surface"` `:31`, `sizes` `:35-39` with **`md: "min-h-11 px-4 text-base"` at `:37`**. `Frontend/packages/ui/src/lib/styles.ts:4-6` — `cn()` is a plain `.filter(Boolean).join(" ")`, **no tailwind-merge**; `focusRing` `:11-12`.
- ✅ `Frontend/packages/ui/src/components/Skeleton.tsx` — `lines = 3` `:16`, the `text` arm `:17-25` (`h-4` bars), the **`block` arm `:29` (`h-full w-full`, `aria-hidden`)**.
- ✅ `Frontend/e2e/storefront.spec.ts` — `BookingEndpoint` `:217-231`, `BOOKING_PATHS` `:233-244`, `gotoSettled`'s chain with the `/q/` arm `:545-548` and the final `else` waiting on `BOUTIQUE.name` at **`:555`**, `AXE_ROUTES` `:681`, `ROUTES` `:713`, the `toBeInViewport()` precedent `:758`, `RESIZE_ROUTES` `:1363`, `TEXT_RESIZE_BROKEN_AT_375` **empty** `:1383`, `resizeTextTo200Percent` `:1385-1389`, the rem-grows comment `:1391-1392`, the three 1.4.4 tests `:1396`/`:1421`/`:1443`, F33's **bespoke axe journey `:2407-2425`**.
- ✅ `Frontend/apps/storefront/src/i18n/he.ts:421-424` — `checkin.notice`'s interim comment and value. `ar.ts:86-87` — the identical value, no comment.
- ✅ `Frontend/apps/storefront/src/__tests__/i18n-keys.test.ts:19-22` — `SECTIONS` from `Object.keys(he.translation)`, `DOTTED_LITERAL` at `:22`.
- ✅ `Frontend/scripts/qa-greps.sh` — `SRC` `:17`, bare `grep -rnE` `:23`, `localStorage` `:33`, physical directions `:40`, raw hex `:42`.
- ✅ `Makefile` — `test` `:18`, `test-db` `:21`, `lint` `:27-30` (**runs `qa-greps.sh` as its third line**), `qa-greps` `:33`, `fe-build` `:44`, `fe-test` `:47`, `e2e` `:51`.

---

## Thirteen corrections — recorded, resolved, amended into the spec and the deck in Task 0

D1–D14 and W-1…W-15 are **not** re-litigated. These are the places where a document disagrees with the tree, or where a critic finding survived. **Every resolution is the smaller edit.**

### C1 — BLOCKING. Tailwind spacing utilities **are** rem-based, so F-13's mechanism sentence and its three numbers are wrong

The deck's §1.3 preamble is false on both halves. `--space-*` drives no Tailwind utility (it is `var()`-only); `pt-6`/`gap-6`/`py-2` resolve through Tailwind's default `--spacing: 0.25rem`, which is a rem and grows 20% under `:root[data-a11y-text-size]`.

**The 1080p default column is unaffected** — 24 / 8 / 4px either way — so the **445 / 635 / 567 budget and `BOARD_ROW_LIMIT = 5` stand exactly as written.** The boosted column does not. Re-derived at a 19.2px root (`--spacing` = 4.8px, `1vh` still 10.8px):

| Band | Deck (F-13) | Correct | Derivation |
|---|---|---|---|
| Chrome | 468 | **501** | footer 1 + 28.8 + 25.2 + **68** (`--space-a11y-footprint` is a calc of px literals and does **not** grow) = 123; page padding 57.6; heading band 77.1; `gap-6` 28.8; freshness row 78.5; `gap-6` 28.8; overflow band 107.3 |
| Rows band | 612 | **579** | 1080 − 501 |
| One row | 116 | **119.6** | 83.6 × 1.2 = 100.4 + `py-2` 19.2 |
| Five rows | 612 | **636.4** | 5 × 119.6 + 4 × 9.6 |

So the fifth row sits **~57px below the fold** under the boost, not "its last pixel on the fold", and **row 4 is the last one that fits** (507.2 ≤ 579).

**F-13's conclusion survives and its wording changes.** The boost needs a pointer; the wall has none (the A11yMenu trigger is a fixed button nobody in the room can reach); the population that presses it is on a phone, where the page scrolls. **There is no unscrollable victim.** What this makes *stronger*, not weaker, is **A30's `toBeInViewport()` on `row.nth(4)`** — `scrollHeight <= innerHeight` alone names nothing.

Declined: shrinking the row to buy the boosted case back (it would spend the configured case for a state with no victim, which is F-2's declined trade in the other direction).

### C2 — BLOCKING. The 1366×768 legibility row uses the panel's DIAGONAL as its width; corrected, the name fails the brief there too

0.595 mm/px is 812.8 ÷ 1366, and 812.8mm is a 32" **diagonal**. Width = 812.8 × 16/√(16²+9²) = **708.4mm** → **0.5186 mm/CSS px**.

| Element | 1366×768 size | Cap (×0.70) | mm | Comfortable to |
|---|---|---|---|---|
| Position number | 65.3px | 45.7px | 23.7mm | **3.6m** |
| First name | 51.2px | 35.8px | 18.6mm | **2.8m ✗** |
| Freshness / overflow | 51.2px | 35.8px | 18.6mm | **2.8m ✗** |

**This changes F-3's character.** `BOARD_ROW_LIMIT = 3` fixes the row *count* and does **nothing** for legibility — the same failure as F-2, on the panel F-3 already flags. **Resolution: the remedy is stated as the one checklist line that binds both axes — the kiosk browser must present a viewport at least 1080 CSS px tall** (which on a 768 panel means page zoom below 100%, or a different panel), **with `BOARD_ROW_LIMIT = 3` as the fallback only if a 768 panel ships anyway.** The deck's F-3 and §5 rows are edited to say so; W-15's second checklist line is reworded from "a 1080-CSS-px minimum viewport height" to name the reason as legibility *and* row count.

### C3 — `queueBoard.overflow`'s `{{count}}` has no `<bdi>` mechanism in the storefront. **Drop the claim; state the true reason**

`copy.md` §2's Status cell and §7's last row assert the count "renders inside `<bdi dir="ltr">`", citing `BoardSection.tsx:603`. That call site is `isolateLtr(t("board.truncated", {count}), String(count))`, and `isolateLtr` lives in `apps/manage/src/lib/booking.tsx`. **The storefront has no equivalent** — verified by grep, every storefront `<bdi dir="ltr">` wraps a value the call site appends *beside* a `t()` label (`QueuePositionPage.tsx:307`, `:332`; `StorefrontLayout.tsx:168`, `:178`), never a numeral embedded inside one.

**Resolution — the free and honest option:** delete the claim and record why no isolation is needed. «ועוד {{count}} בתור» puts a digit run between two Hebrew runs; under the Unicode Bidi Algorithm a European-number run between two strong-RTL runs resolves LTR on its own. Isolation earns its keep at a **neutral or Latin** boundary, and this string has neither. **Declined: porting `isolateLtr` into `apps/storefront/src/lib/`** — a file nobody asked for, on a page that renders one interpolation.

### C4 — F-6 cites the house rule but does not follow its shape; give the real reason

`apps/manage/src/i18n/he.ts:67-69` is **label-then-number** — «תורים ביום זה: {{count}}» — which works because the noun never sits after the numeral. «ועוד {{count}} בתור» is **number-then-label**. It is grammatical, but for a different reason: **«בתור» is a prepositional phrase that does not inflect for number.**

**Resolution:** the revision ships; `copy.md` §2 and design F-6 state *that* reason, keeping the house rule as a precedent for *why counts get scrutinised* rather than as the mechanism. Otherwise the next editor "restores" the precedent's shape and reintroduces the agreement problem the finding exists to remove.

### C5 — the empty state's headline justification is contradicted three rows below it in the same table

`W-EMPTY` is sold four times as "the state the screen is in for most of the day". That is true only **post-F58**. §4's own «Every entry `called: false`, forever» row establishes that in the interim nothing leaves `waiting`, so the board is empty from midnight until the first check-in **and never again** — and D10(4) says the interim is the only world F59 ships into.

**Resolution — qualify by world, everywhere the phrase appears** (deck §0's `EmptyState` note, §4's `W-EMPTY` row, W-7, `copy.md` §5's `queueBoard.empty` row, spec Goal + «Every state»): *"post-F58 this is the state the screen is in for most of the day; pre-F58 it is the first hour."* The design investment is right either way. This is precisely the two-halves-arguing-opposite-things defect the spec's own D10 review already caught once, and it must not reappear in the deck that reviewed it.

### C6 — `min-h-[567px]` is a raw px literal in app code, and it is the **default-root** number

`tokens.md` usage law 5: *"All spacing/typography from tokens — a raw px value in app code is a review defect."* The deck's exemption argument covers the container `max-w-[…]` precedent (`QueuePositionPage.tsx:19`, `StorefrontLayout.tsx:147`) — a **container width**, not a derived band height. And after C1 the real band is ~612px under the boost while the skeleton box stays 567.

**Resolution:** drop the fixed height. `Skeleton variant="block"` is `h-full w-full` (`Skeleton.tsx:29`), it is `aria-hidden`, it is on screen for under a second at boot, and nothing measures it. The wrapper is `flex-1` inside the page's `flex flex-col`, or the wrapper goes entirely and the `Skeleton` takes `className="h-full"`. **F-10's substance is unchanged** — one block, not N text bars.

### C7 — the arbitrary-typography escape is unprecedented here and must be **ruled**, not assumed

`grep -rn "text-\[" apps/storefront/src apps/manage/src packages/ui/src` returns **zero hits**, verified. F59 ships the **first `text-[…]` in the product**, and `tokens.md` law 5 covers typography as well as spacing. The deck defends the px half (containers) and never states that it is also stepping outside the `--text-*` ramp.

**Resolution — one line in §0's binding inheritances, with the ruling and the arithmetic:** the token ramp tops out at `--text-3xl: 2.25rem` = **36px** (`theme.css:52`), which is less than half the smallest number on this board; a 3–5m viewing distance needs 75.6px for the position and 59.0px for the name; **so `/queue` is the one route in the product that renders arbitrary font-size values, and A34's class pins are the enforcement that keeps them from drifting.** Stated so a reviewer reads it as a decision rather than an oversight.

### C8 — two wrong `theme.css` citations for the same block

Deck §0 and §7.3 cite `theme.css:165-173` for `prefers-reduced-motion`. That block is **`:155-163`**; `:165-173` is the A11yMenu boost group. **Resolution:** two edits. The `:170-172` text-size citations throughout both documents are correct and are not touched.

### C9 — `Skeleton variant="text"` defaults to `lines = 3`, not 5

`Skeleton.tsx:16`. F-10's "five of them pulsing is five times the page's entire motion budget" describes a `lines={5}` nobody would write. **Resolution:** the finding holds at three — three `h-4` bars on a 107px-row screen still does not resemble the state it stands in for, and three pulses is still the page's whole motion budget — and the number is corrected so the argument is not carrying a wrong fact.

### C10 — `w-[2ch]`'s stated justification names a case the endpoint cannot produce

"so a two-digit number does not shift the name column" — with `BOARD_ROW_LIMIT = 5` the position is **always** one digit. **Resolution:** keep the width, rejustify it as a **fixed gutter** that keeps the name column's inline-start edge on one axis, plus headroom against a future `BOARD_ROW_LIMIT` change (F-3's fallback moves it down, a pilot bump could move it up). As written it teaches the next reader a constraint that does not exist, on the one page where the row cap is itself a minimisation control.

### C11 — `_seed()`'s citations are off by one, and the widening instruction is right

Signature `:55-65`, `name="נועה"` at `:73` (spec says `:55-64` / `:72`). The two kwargs it must gain — `called_at: datetime | None = None` and `name: str = "נועה"` — are unchanged.

### C12 — there is **NO MIGRATION**, and main's head is `0018`

`Backend/migrations/versions/` ends at `0018_queue_tickets.py` (F33's). **F59 creates no revision file.** Said again in the scope fence, in Task 2 and in the manifest, because a builder who reflexively runs `alembic revision` produces an empty revision that collides with whatever is in flight and reddens `test_exactly_one_migration_head` for nothing. **If a builder concludes a migration IS needed, that is a significant finding: stop and record it, do not build it.** D2 names the only three shapes it could take and declines all three.

Consequently: **the head+1 rule, the last-commit-on-the-branch rule and the do-not-open-a-PR-below-an-unmerged-migration rule all have no subject on this feature.** They are stated here only so their absence is deliberate.

### C13 — `main.py:1206-1211` stays "The FIFTH", and only its second sentence is rewritten

The comment opens *"The FIFTH /storefront sibling: F33's walk-in check-in and its position read, both POSTs."* F59 adds a **third route to that fifth sibling**, not a sixth sibling. **Resolution:** the ordinal is left alone; the sentence becomes "…its position read and F59's public board, all three POSTs", with the board's POST attributed to the derived-`ROUTES` argument (D1) and **not** to F33's capability argument.

---

## Scope fence — read this before every task

**F59 only reads. It writes nothing, anywhere.**

| Not in F59 | Whose |
|---|---|
| **Dispatch of every kind** — call, take-next, push-assign, skip, finish, remove, merge; every `status` write; every `called_at`, `requeued_at`, `skip_count` write | **F58** |
| The staff waitlist panel at `/manage/floor`; **anything on `/manage` at all** — no section, no nav row, no preview | **F58** |
| A ticket id on the wire, in any field, ever | **D7, absolutely** |
| Server-side deduplication of a woman's two tickets | **Ruling 3 / F58's merge** |
| A migration, an index, a column | **D2 — none exists** |
| `customers.marketing_opt_in_at`, the promotion, the retention sweep, the per-boutique notice override, **final privacy wording** | **F20** |
| A feature flag, a `queue_board_enabled` setting, a board-only URL token | **declined — F33's Ruling 4 gate covers it** |
| Wait-time estimates, «הבאה בתור», any analytics over `created_at → called_at` | pre-decided #28, D10(1) |
| Per-IP or distributed rate limiting, `Retry-After` | **F21** |
| A shared `usePoll` in `packages/ui` | **D9 / F33's D9** |
| `sessionStorage` of any kind; any import from `lib/checkinTicket.ts` | — |
| A storefront `ar.ts` parity guard; a storefront register guard for `/נשלח|תישלח|בדרך/` | Risk 7 / F-9, inherited |

If a task's diff grows a status write, a `/manage` file, a migration, an `id` field on the board payload or a second poll target, **it has left F59.**

---

# Part 0 — the plan

## Task 0 — This plan, and the thirteen amendments to the spec and the deck
`.planning/plans/public-queue-board.md` (**✚ this file**), `.planning/specs/public-queue-board.md`, `.planning/design/screens/public-queue-board/design.md`, `.planning/design/screens/public-queue-board/copy.md`

No test, no code. Amend the three documents so each is the binding statement of its own resolutions:

- **`design.md` §1.3** — rewrite the spacing-mechanism sentence and F-13's three numbers per **C1**; keep the default-root budget and `BOARD_ROW_LIMIT = 5` byte-identical.
- **`design.md` §1.2, §5, F-3, W-15** — the 1366×768 mm/px figure and its three legibility cells per **C2**; restate F-3's remedy as the viewport-height checklist line that binds both axes.
- **`design.md` §0 binding inheritances** — add **C7**'s arbitrary-typography ruling (the `--text-3xl` = 36px ceiling, the 75.6px requirement, A34 as the enforcement).
- **`design.md` §0 + §7.3** — `theme.css:165-173` → **`:155-163`** for `prefers-reduced-motion` (**C8**).
- **`design.md` §6 + F-10** — drop `min-h-[567px]` for `flex-1` (**C6**); "five of them" → **three** (**C9**).
- **`design.md` §2.1** — `w-[2ch]`'s justification (**C10**).
- **`design.md` §0/§4/W-7 + `copy.md` §5** — qualify «most of the day» by world (**C5**).
- **`design.md` F-6 + `copy.md` §2** — the real grammatical reason (**C4**); delete the `<bdi>` claim and state the UBA reason (**C3**, also `copy.md` §7's last row).
- **`spec` D2 + Risk + the Testing section's `_seed` paragraph** — **C11**, **C12**.
- **`spec` D1 + «Backend changes»** — **C13**'s ordinal rule for the `main.py:1206-1211` rewrite.
- **`spec` header** — one line recording that the design deck's §1.1 supersedes D8's type-scale table (F-1) and that F-2/F-4/F-5/F-7/F-8/F-10/F-14 are folded into this plan's tasks.

- **Done when**: `grep -n "165-173" .planning/design/screens/public-queue-board/design.md` returns nothing; `grep -n "0.595\|min-h-\[567px\]\|five of them" .planning/design/screens/public-queue-board/design.md` returns nothing; `grep -n "bdi dir=\"ltr\">" .planning/design/screens/public-queue-board/copy.md` returns nothing.
- **Commit**: `docs(planning): F59 implementation plan and thirteen spec and design amendments — Gate 2 self-approved`

---

# Part I — the backend

## Task 1 — `board_display_name`, the two bounds, the two wire models, and the `TicketView` docstring rewrite (D5, D7, conflicts 6 and 8)
`Backend/app/queue/validation.py`, `Backend/app/queue/schemas.py`, `Backend/tests/test_queue_board_service.py` (**✚**)

### The failing tests first (**fast**, no Postgres)

`tests/test_queue_board_service.py`, the `test_storefront_validation.py` scaffold. **The first-name table, every row of D5** — and the boundary comes from **D5's rule**, never from D7's example payload:

| Input | Expect | Why the case is here |
|---|---|---|
| «נועה כהן» | «נועה» | the ordinary case |
| «נועה מרים כהן» | «נועה» | three tokens |
| «נועה» | «נועה» | a one-word name is shown **in full** |
| **«כהן נועה»** | **«כהן»** | ⚠ asserted as the **DECIDED behaviour**, with a comment saying it is an accepted ceiling and **not a bug to "fix" with a heuristic** |
| «  נועה   כהן\n» | «נועה» | `str.split()` with no argument |
| «גב' כהן» | «גב'» | honorific first — declined a stop-list |
| «נועה-מרים כהן» | «נועה-מרים» | hyphens are not whitespace |
| a 12-character token | unchanged | the boundary, from `first[:BOARD_NAME_MAX - 1] + "…"` with `BOARD_NAME_MAX = 12` |
| a 13-character token | 11 chars + «…» | the other side of it |

Plus **`name.split()[0]` cannot raise on a stored row** — `validate_customer_name` rejects `not name.strip()` before the insert (`app/booking/validation.py:82-83`), asserted here so a future loosening of that validator fails a test rather than a wall screen.

And **`QueueBoardEntry.model_fields.keys() == {"position", "first_name", "called"}`** — pydantic introspection, **not** a source grep, so it fails the moment anyone adds a field (A7).

### The code

- `app/queue/validation.py` — `BOARD_ROW_LIMIT = 5`, `BOARD_NAME_MAX = 12`, `board_display_name(name: str) -> str`. **The module docstring is rewritten** ("the two error classes and the **one** bound F33 owns" is now false — conflict 6). The combining-mark ceiling goes in a `ponytail:`-style comment on the function, **not** into a dependency.
- `app/queue/schemas.py` — `QueueBoardEntry {position: int, first_name: str, called: bool}` and `QueueBoardView {entries: list[QueueBoardEntry], waiting_total: int}`. **Plain `BaseModel`, not `ForbidExtraModel`** — there is no request model to forbid extras on. `QueueBoardEntry`'s docstring states that **no `id` field may ever be added**, and why. The **module docstring is widened** from "the public check-in surface".
- **`TicketView`'s NAME paragraph (`:52-55`) is rewritten** (conflict 8): from F59 onward the first name of a top-`BOARD_ROW_LIMIT` ticket is derivable by combining `POST /storefront/checkin/position` with `POST /storefront/queue`, both anonymous — so the omission is **defence-in-depth rather than a closed channel**, and the residual is bounded by `board_display_name` having already run (one token, ≤12 characters, never a surname, never a phone). ⚠ **This is a security rationale, not a stale count. Leaving it standing would mislead a reviewer, which is worse than misleading a reader.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `BOARD_NAME_MAX - 1` truncation | truncate at `BOARD_NAME_MAX` | the 13-character case **RED** (12 + «…», one character too many) |
| `.split()[0]` | `.split(" ")[0]` | the doubled-whitespace case **RED** (returns `""`) |
| the three-field model | add `id: uuid.UUID` | `model_fields.keys()` **RED** |

- **Done when**: `make lint` + `make test` green locally. `git diff --stat`; conftest untouched; `git show --stat`.
- **Commit**: `feat(queue): the board's first-name rule, its two bounds and its wire models`

## Task 2 — `QueueTicketsRepository.board()` — a column projection, and the order that must equal `position()` (D3, A8–A11, C11, C12)
`Backend/app/db/repositories/queue_tickets.py`, `Backend/tests/test_queue_repositories.py`

> ⚠ **NO MIGRATION (C12).** `queue_tickets` already carries `tenant_id`, `queue_day`, `name`, `status`, `called_at`, `requeued_at`, `created_at`, `deleted_at`, and `idx_queue_tickets_tenant_day_active (tenant_id, queue_day) WHERE deleted_at IS NULL` (`0018_queue_tickets.py:93-96`) is already the exact access path. **Do not run `alembic revision`.** `test_migrations.py` already pins this table's CHECK definitions and index `indexdef` byte-identically, so a column or an index added here reddens a shipped test — which is also why F59 writes **no migration test.**

### The failing tests first (`db`-marked, **run locally**)

**⚠ Widen the shipped `_seed()` helper FIRST, and that is a change to a shipped helper rather than a new one (C11).** `tests/test_queue_repositories.py:55-65` takes `created_at, queue_day, status, requeued_at, deleted_at, phone` and **no `called_at`**, and hardcodes `name="נועה"` at `:73`. It gains **two kwargs — `called_at: datetime | None = None` and `name: str = "נועה"`**. Without the first the `called` case cannot be seeded at all; without the second every db-seeded ticket carries an identical name, which makes Task 5's "no string from A's names appears in B's payload" have nothing distinctive to look for.

- **`test_the_board_order_agrees_with_the_position_count`** — **the highest-value test in the feature.** Seed five waiting tickets with distinct `created_at`, call `board()`, and for **every** returned row assert `position(session, tenant, ticket) == index + 1`. This is what stops the wall and her phone from ever disagreeing, and it is what goes red if F58 later changes the status filter on one side only (Risk 6).
- `requeued_at` on the earliest ticket moves it to the back **and** shifts every other row by one, agreeing with `position()` throughout.
- Four exclusion cases: `in_service` / `done` / `removed` absent; soft-deleted absent; another `queue_day` absent; another tenant absent.
- The cap returns exactly `limit` rows while `waiting_total` is the **full** count, including the boundary at exactly `BOARD_ROW_LIMIT` (A11).
- **`test_a_second_ticket_for_the_same_phone_is_a_second_row`** — Ruling 3. Seed two waiting tickets with the same `phone` **and the same `name`**; assert **two** rows at consecutive positions and `waiting_total == 2`, with a comment saying the board **must not** deduplicate because the only key that would is `phone` and `queue_tickets.py:15-18` forbids reading on it.
- A tie on the sort key produces **the same order on two consecutive calls** (the `, id ASC` clause), with a comment naming the wall/phone disagreement on a tie as an accepted residual, not a bug to fix by editing `position()`.
- An empty day returns `([], 0)`, never `None`.
- **`called_at` set on a seeded row surfaces as `called: true`** — seeded **directly in the fixture**, because nothing in the product writes it (D10).
- **The db-marked surname sibling**: seed `name="NOA COHEN"`, assert the view's `first_name` is `"NOA"` and that `"COHEN"` appears **nowhere** in the serialised payload. ⚠ **This is the real home of "no surname reaches the wire"** — the e2e version of that assertion cannot fail and is deliberately not written (Task 8).

### The code

```python
async def board(
    self, session: AsyncSession, tenant_id: UUID, queue_day: datetime.date, *, limit: int
) -> tuple[Sequence[Row[tuple[str, datetime.datetime | None]]], int]:
```

**`select(QueueTicket.name, QueueTicket.called_at)` — a COLUMN PROJECTION, never `select(QueueTicket)`.** `select(QueueTicket)` would pull five normalised Israeli mobiles and five `marketing_opt_in_at` consent timestamps into the process on **every** poll, twelve times a minute, forever, for a view that renders `name` and `called_at is not None`. Nothing would leak — the schema narrows — but D4's own argument ("a client-side cap would ship forty names to a browser and render five") is exactly this argument one layer up, and the projection makes the class docstring's promise true in the stronger sense: **the phone never enters the process on this path at all.**

Four predicates, **byte-identical to `position()`'s** (`:82-88`) with the day bound differently and for a stated reason, then `ORDER BY COALESCE(requeued_at, created_at) ASC, id ASC LIMIT :limit`, then a **second statement** — `count(*)` over the same four predicates — in the same session.

The docstring states: the predicate-identity rule against `position()`; that `:day` is **today** here and the **ticket's own day** there, deliberately; the `, id ASC` tiebreak's reason (board-order stability across polls, **not** the wall/phone agreement, which it cannot buy); and that **`count(*)` counts TICKETS, not women** (Ruling 3). **The class docstring's "no read keyed on `phone`" promise stays true and needs no edit** — verified.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `status == WAITING` | widen to all four | the exclusion cases **RED**, and `test_the_board_order_agrees_with_the_position_count` **RED** — which is the Risk-6 alarm |
| `queue_day == today` | bind to `ticket.queue_day` (there is no ticket — bind to a fixed date) | the other-day exclusion **RED** |
| `, id ASC` | drop it | the two-consecutive-calls case **flakes**; if it stays green on ten runs the seed is not producing a tie and the test is worthless — **fix the seed, not the assertion** |
| the second `count(*)` statement | return `len(rows)` | the cap/total case **RED** with a total of 5 against 8 |
| the projection | `select(QueueTicket)` | nothing goes red — this one is a **review** item, and the docstring is what carries it |

- **Done when**: the local db suite green, baseline + the new cases. `make lint` clean. **Revert `backend/tests/conftest.py`; `git diff --stat`; `git show --stat`.**
- **Commit**: `feat(queue): the board read — today's waiting rows, projected, in position order`

## Task 3 — `QueueService.board()`, the **fourth** limiter, and the two `Settings` fields (D6, conflict 6)
`Backend/app/queue/service.py`, `Backend/app/core/config.py`, `Backend/app/main.py`, `Backend/tests/test_queue_board_service.py`

### The failing tests first (**fast**, fakes)

- **the budget is charged on every call including an empty board**, and blocks with `CheckinThrottledError`;
- **the board budget is a distinct object from all three shipped instances** — `assert len({id(x) for x in (create, ticket, miss, board)}) == 4` off the constructed service. ⚠ **This one can fail, and it is the assertion that catches a builder reaching for an existing instance**;
- **`called` is derived from `called_at is not None` and the timestamp never reaches the view**;
- **the entry positions are `1..n` in list order**, so a future refactor cannot renumber them client-side;
- **there is no miss branch** — every resolvable tenant has a board, empty or not — asserted as: an empty result charges the budget and returns `{"entries": [], "waiting_total": 0}`.

### The code

- `app/core/config.py` — `queue_board_max_per_window: int = 600`, `queue_board_window_seconds: int = 60`, appended to the `checkin_*` block (`:173-196`), **with the concurrent-viewer arithmetic written out in the comment in the `:184-187` style — screens PLUS phones.** A screens-only comment is how the number came out 5× too small the first time:

  | Population | Pollers | req/min at a 5s beat |
  |---|---|---|
  | Wall screens (salon + fitting area) | 2 | 24 |
  | Phones in the room on a busy Sunday | up to 18 | 216 |
  | **Design target** | **20 concurrent viewers** | **240** |
  | **Ceiling, 2.5× the target** | — | **600** |

  Why not any of the four shipped budgets, in one line each and all four in the comment: `create_limiter` (200/3600s) is spent **seventeen minutes** into the shop day by one screen and would 429 every woman scanning the QR at the door; `position_ticket_limiter` (30/60s) is sized for one client holding one ticket and a per-tenant board key trips it at **three screens**; `position_miss_limiter` (120/60s) is the trap `main.py:743-746` names in writing; `storefront_rate_limiter` (6000/60s) is the catalog brake and `main.py:720-722` states that failure verbatim.

- `app/queue/service.py` — one `board_limiter` kwarg; `async def board(self, tenant_id) -> QueueBoardView`. Metering order: **consult and record `board_limiter` → open the `tenant_session` → two `SELECT`s.** One clock read, `today_jerusalem(lambda: now)`, the `:103`/`:108` shape. **No `try` block**, consistent with the file. **The module docstring's "Three limiter instances" (`:20`) is rewritten to four.**
- `app/main.py` — a fourth `FixedWindowRateLimiter(...)` inside the existing `QueueService(...)` construction (`:729-752`), with a comment naming **why it is not any of the three above it** (the `create_limiter` arithmetic is the vivid one) and **why its number is different from `position_miss_limiter`'s rather than the same** — a limiter ceiling is sized by traffic, and the didactic "same shape, different instance" argument belongs to the `:743-746` comment, not to a number. **The "THREE limiter instances" comment at `:714-728` is rewritten in the same edit.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the fourth instance | pass `position_miss_limiter` as `board_limiter` | the four-distinct-objects test **RED** |
| the charge on an empty board | skip `record_failure` when `entries` is empty | the empty-board budget case **RED** |
| `called_at is not None` | put `called_at` on the entry | `model_fields.keys()` (Task 1) **RED** |

- **Done when**: `make lint` + `make test` green locally. `git diff --stat`; conftest untouched; `git show --stat`.
- **Commit**: `feat(queue): the board service and its own fourth rate-limit budget`

## Task 4 — The third route on F33's router, and the two shipped test files it edits (D1, D14, C13)
`Backend/app/queue/router.py`, `Backend/app/main.py`, `Backend/tests/test_queue_board_api.py` (**✚**), `Backend/tests/test_storefront_api.py`, `Backend/tests/test_spa_serving.py`

### The failing tests first (**fast**)

**`tests/test_queue_board_api.py`**, on the `test_checkin_api.py` posture template. A local `_client()` builds a real app with `create_app(resolver=…)`, swaps **one** `app.state` attribute (`queue_service`) for a stub, and installs `FakeAuthService` both on `app.state` and via `dependency_overrides[get_auth_service]` so an owner cookie is genuinely resolvable. It proves:

- **200 anonymously with no `set-cookie`** (A1); **cookie-blindness on the FULL `.json()`** across two separate clients — no field excluded, because a stubbed service returns a deterministic body;
- an unresolvable Host → the **generic 404 `TENANT_NOT_FOUND`** (A2) — i.e. the path is **not** in `EXEMPT_PATHS`, and never add a `/storefront` path there;
- `cache-control: no-store` (A3), inherited from the router's `Depends(_no_store)` with **zero new code**;
- **`GET /storefront/queue` stays a 405** (A4);
- the tenant reaches the service as the **host-derived** id;
- `CheckinThrottledError` leaves as **429 with the byte-identical shared body** (`main.py:137-139`, handler `:1131-1134`) — **no new error class, no new handler**;
- `SPEC_ERROR_CODES == {"TENANT_NOT_FOUND", "TOO_MANY_ATTEMPTS"}` for this file, a subset of the four already pinned at `test_storefront_api.py:234-237`.

**`tests/test_storefront_api.py::test_no_route_is_registered_twice_across_routers`** — the explicit `/storefront` literal gains `"/storefront/queue"` with a comment naming F59 and `test_queue_board_api.py`. **This is the one test F59 is meant to break**, and its docstring at `:569-571` says so. ⚠ **The five `ROUTES`-parametrized guards need NO edit, and that is the assertion (A5):** `ROUTES` is derived over `method == "GET" and path.startswith("/storefront")` (`:186-192`), F59 registers no GET, so nothing joins it. If a builder converts the route to a GET, **`test_the_read_throttle_is_not_inert` (`:1222-1234`) goes red with a 200**, and the only two fixes are the ones D1 declines (share the catalog's 6000/60s budget, or weaken a guard protecting six shipped public reads).

**`tests/test_spa_serving.py`'s `SHELL_PATHS` (`:70-85`) gains `"/queue"`** with a comment naming F59 — a **data** edit, not a test edit; `test_every_storefront_router_path_serves_the_shell` is parametrized over it and picks it up for free. Serving already works (`_RESERVED_SEGMENTS` at `main.py:345` does not contain `queue`), so this closes a **silent coverage hole**, not a red build (A31).

### The code

`app/queue/router.py` — four lines:

```python
@router.post("/queue")
async def queue_board(request: Request, service: Queue) -> QueueBoardView:
    tenant = get_current_tenant(request)
    return await service.board(tenant.id)
```

`get_current_tenant(request)` as the **first statement**, never a `Depends()` — the shape at `:69` and `:81`. **No request body at all.** **The module docstring is rewritten**: it opens "two anonymous, tenant-scoped POSTs" (`:1`) and says "**BOTH** routes are POSTs" (`:10`), both now false. ⚠ **The rewrite must keep the capability paragraph (`:18-22`) intact** and add that the board carries **no** capability and therefore no id — which is why *its* POST is argued from the derived `ROUTES` collision and **not** from the log-leak rule. Mis-citing F33's argument here would be a security rationale that does not apply.

`app/main.py` — **one comment edit and nothing else.** The route is a decorator on the router `:1212` already includes. `:1206-1211` becomes "…its position read and F59's public board, **all three POSTs**", keeping **"The FIFTH"** (C13).

**No `vite.config.ts` edit, on either side, and this contradicts the brief — see «The dev proxy» below.**

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `@router.post` → `@router.get` | swap it | `test_the_read_throttle_is_not_inert` **RED** with a 200 — *run this one deliberately; it is D1's whole argument* |
| `get_current_tenant(request)` | take the tenant from anywhere else | the host-derived test **RED** |
| registering on a **new** router without `Depends(_no_store)` | do it | the `no-store` case **RED** |

- **Done when**: `make lint` + `make test` green locally. **This is the milestone**: the full public surface and its wire shape are exercised end to end with no Postgres. `git diff --stat`; conftest untouched; `git show --stat`.
- **Commit**: `feat(queue): the public wall-board route, the third on F33's queue router`

## Task 5 — The RLS isolation case (**`db`-marked, run locally**) (A9, A10)
`Backend/tests/test_queue_isolation.py`

**Non-negotiable, because this is the endpoint that returns names.** Connected **only as the app role** over the **`app_role_url`** fixture — **never `migrated_db`**, because the container superuser bypasses RLS and every assertion would pass vacuously.

### The failing tests first

- **`test_a_board_never_carries_another_tenants_names`** — tenant A writes three tickets through the widened `_seed(name=…)` with **three DISTINCTIVE multi-token names — «אביגיל רוזנבלט», «תמר בן-ציון», «שולמית פרידמן»** — so "no string from A's names appears anywhere in B's serialised payload" has something that can actually be found. ⚠ **The distinctive names are the whole point**: against the shipped hardcoded «נועה» the assertion is near-vacuous, which is exactly the Risk 4 class.
- **Tenant B's board returns `([], 0)`**; B writes its own and **A's board is unchanged**.
- Tenant B's `waiting_total` never counts A's tickets.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `app_role_url` fixture | swap to `migrated_db` | every probe goes **GREEN vacuously** — run this once, deliberately, confirm it, then restore. That is the proof the suite measures RLS and not nothing |
| the distinctive names | revert to the `_seed` default | the cross-tenant string search **still passes** against a leak — which is why C11's `name` kwarg exists |

- **Done when**: local db suite green; both mutation-checks performed and restored. `make lint` clean. **Revert `backend/tests/conftest.py`; `git diff --stat`; `git show --stat`.**
- **Commit**: `test(queue): forced RLS isolation for the public board read`

---

# Part II — the frontend

> ⚠ **CAPTURE THE `qa-greps` BASELINE BEFORE THE FIRST FRONTEND TASK, and diff against it afterwards.**
> ```
> cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen" && make qa-greps \
>   > "/private/tmp/claude-501/-Users-mrwen-Documents-Github-Ryan---rawad---mrwen/5dea0fd4-6d4a-4e0f-9d87-7b74299b72d6/scratchpad/qa-greps-baseline.txt" 2>&1
> ```
> The script greps **whole files including comments** (`qa-greps.sh:23`) over `apps/storefront/src` (`:17`). Tasks 6 and 7 are the two most comment-heavy in the feature and both quote English prose about screen edges and inline directions. `left-`, `right-`, `pl-`, `pr-`, `ml-`, `mr-` in a comment fail at `:40`; a bare 6-digit hex fails at `:42`; the literal `localStorage` fails at `:33`. **The output must be byte-identical to the baseline at the end of every frontend task.** A new `FAIL` line from F59 is prose, not a code defect, and the fix is the prose.

## Task 6 — Storefront i18n, the D13 notice amendment, the API client and the one router entry (D13, D14, C3, C4, C5, F-8, F-12)
`Frontend/apps/storefront/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/api.ts`, `…/router.tsx`, `…/__tests__/router.test.tsx`, `…/__tests__/api.test.ts`, `…/__tests__/i18n-keys.test.ts`

> ⚠ qa-greps baseline captured. **No colour hex in a comment** — the deck's §6 quotes `#F6F0E6` and `#FDFBF7` and `:42` bans both.

### The failing tests first

**`__tests__/router.test.tsx`** — `/queue` matches `queueBoard`; **`QueueBoardPage` mounts AND the catalogue does not** (A15). ⚠ **That pair is the whole test**: `router.tsx:347-352` says in the shipped file that a missing `case` compiles clean, typechecks clean and renders the dress grid under the new route's own title, and that `checkin` shipped that way for one commit with every title assertion green. Plus: `/q/abc` still matches `queuePosition` and `/queue` does not (the disjointness `:91-96` claims, now simply true); `document.queueBoard` resolves.

**`__tests__/api.test.ts`** — `getQueueBoard()` POSTs to `/storefront/queue` **with no body**, and returns the payload **verbatim with no case conversion** (this client never converts).

**A32b — the only assertion in the PR that fails the moment D13 is forgotten or reverted.** In `i18n-keys.test.ts` (or a sibling), assert **`he.translation.checkin.notice` and `ar.translation.checkin.notice` each contain `"עמוד אינטרנט ציבורי"`** — read **off the resource bundle, never through `t()`**, in the style that file already uses to read `he.ts` values directly. One `expect` each.

**A32a — `CheckinPage.test.tsx:297-306` is unchanged and still green.** The amendment adds a clause and does not touch the `{{boutique}}` interpolation. ⚠ **That test cannot detect whether the amendment happened** — it renders `t("checkin.notice", { boutique })` and compares against the same bundle, so it passes byte-identically against the unamended value. **That is precisely why A32b exists**, and A32b must not be written through `t()` or it inherits the same vacuity.

### The code

- **`i18n/he.ts` — eight new keys, and eight reused** (`copy.md`'s ledger):
  - `document.queueBoard` = «לוח התור»;
  - a `queueBoard` section: `heading` = «ממתינות בתור», `empty` = «אין כרגע ממתינות», `emptyHint` = «אפשר להצטרף לתור בסריקת הקוד שבבוטיק.», `overflow` = **«ועוד {{count}} בתור»**, `called` = «גשי לדלפק», `loading` = «טוענות את לוח התור», `loadFailed` = «לא הצלחנו להציג את לוח התור כרגע.»;
  - ⚠ **`queueBoard.retry` is NOT declared** (F-8). The error arm resolves the shipped **`checkin.retry`** («ניסיון נוסף», `QueuePositionPage.tsx:358`). The spec's Frontend-changes table lists `retry` under `queueBoard`; **a builder following it literally ships a ninth key duplicating a shipped value.**
  - ⚠ **The seven freshness/pause keys are RESOLVED from `checkin.*`, never re-declared** — `updatedAt`, `staleAt`, `pausedAt`, `pause`, `resume`, `pausedCue`, `resumedCue`. `i18n-keys.test.ts` resolves `"checkin.pause"` out of `QueueBoardPage.tsx` exactly as it does out of `QueuePositionPage.tsx`.
  - **`overflow`'s comment carries C3 and C4**: the count is grammatical at every value because «בתור» is a **prepositional phrase that does not inflect for number** (not because of the label-then-number shape at `apps/manage/src/i18n/he.ts:67-69`, which is a different mechanism); and it counts **places**, because under Ruling 3 the quantity counts tickets and the product cannot count women without a read keyed on `phone`. **No `<bdi>` claim** — a digit run between two Hebrew runs resolves LTR under the UBA with no isolation, and the storefront has no `isolateLtr`.
- **`checkin.notice` amended in BOTH files** — the whole diff is in `copy.md` §6. One clause inserted after the retention sentence, and **«הם» → «הפרטים»** (F-12): the insertion puts «מספר הטלפון שלך» between «הפרטים» and the pronoun, so «הם לא ישמשו לפניות שיווקיות» would read as *the phone number will not be used*. The clause says her **place in the queue** and **the first word of the name she entered** appear on the boutique's queue board; that the board is **a public web page anyone who knows the boutique's web address can open, not only a screen inside the shop**; and that her **phone number is not shown there**. ⚠ **It does NOT say "her first name, not her surname"** — D5's derivation is `name.split()[0]` and «כהן נועה» is ordinary Israeli form-filling. **The notice must not claim more than the code delivers.** It stays **INTERIM and counsel-gated**; the `in_run_gates` F33 entry **stays open** and gains a **fifth item**.
- **`i18n/ar.ts`** — the same eight keys and the same amended notice, **Hebrew standing in untranslated, never `""`** (i18next's `returnEmptyString` default renders the empty string rather than falling back and would blank the page). ⚠ **No storefront parity guard exists** (Risk 7) — A32b is the one exception and covers `ar.ts`'s notice specifically.
- **`api.ts`** — `QueueBoardEntry` / `QueueBoardView` interfaces (snake_case verbatim) and `getQueueBoard(): Promise<QueueBoardView>` on the exported `api` object, `POST`, no body. **No new `case` in `errorMessageKey` (`:48-77`)** — F59 adds no error code.
- **`router.tsx`** — four edits, only one compiler-forced: `RouteName` +`"queueBoard"`; `RouteMatch` +`{ name: "queueBoard" }`; `DOC_TITLE_KEYS` +`queueBoard: "document.queueBoard"` (**the forced one**); one exact `if (path === "/queue") return { name: "queueBoard" };` beside `:114-116`; **one `case` in the switch, which is NOT forced.** The `:91-96` disjointness comment is **left exactly as it is** — it stops being forward-looking and becomes true.

⚠ **Risk 8, and it bites immediately:** once `queueBoard` is a section of `he.ts`, **any quoted `"queueBoard.…"` literal anywhere in `apps/storefront/src` is scraped as an i18n key** (`i18n-keys.test.ts:19-22`) and must resolve to a defined, non-empty Hebrew string. **The testids are `queue-board`, `queue-board-row`, `queue-board-empty`, `queue-board-overflow`, `queue-board-freshness`, `queue-board-cue`, `queue-board-loading-status`.** F33 carried this as its Risk 8; it is now a repeat.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the switch `case` | delete it (leave `DOC_TITLE_KEYS`) | the router test's **"the catalogue did not render"** half **RED** — the title half stays green, which is the trap |
| the notice amendment | revert `checkin.notice` in `he.ts` only | **A32b RED on the `he` bundle** — and A32a stays green, which is why A32b exists |
| A32b written through `t()` | rewrite it that way | it goes **green against the unamended value** — do this once, confirm it, restore |

- **Done when**: `make fe-test` + `make fe-build` + `make qa-greps` green, the greps **byte-identical to the baseline**; `pnpm -r lint && pnpm -r typecheck` clean. `git show --stat`.
- **Commit**: `feat(storefront): the queue-board route, its copy and the amended collection notice`

## Task 7 — `QueueBoardPage` — the copied poll, the 2.2.2 pause, the freshness line and the big-type layout (D8, D9, D11, D12, C1, C6, C7, C9, C10, F-4, F-7)
`Frontend/apps/storefront/src/routes/QueueBoardPage.tsx` (**✚**), `Frontend/apps/storefront/src/__tests__/QueueBoardPage.test.tsx` (**✚**)

> ⚠ qa-greps warning as Task 6. **This file carries the most copied prose in the feature**, which is exactly where an English comment about a screen's «right edge» trips `:40`.

### ⚠ COPY THE POLL FROM THE SHIPPED `QueuePositionPage.tsx`. DO NOT WRITE A FOURTH BESPOKE LOOP.

This is the **third** copy of these mechanisms in the repo (`BoardSection.tsx` → `apps/manage/src/lib/usePoll.ts` → `QueuePositionPage.tsx` → here). D9 and F33's D9 both decline extraction: `usePoll.ts` is inside `apps/manage` and is unreachable from `apps/storefront` under pnpm's isolated `node_modules`, and `packages/ui`'s review surface is the design system. **Read the mechanisms off `QueuePositionPage.tsx` at the ✅ line numbers above and copy the comments with the code** — Risk 5's whole mitigation is that the copies are greppable by their own prose.

**Copy verbatim, all five:**

1. **Schedule-after-settle, one arming site** (`:105-118`). At most one request in flight per tab **by construction**. Not `setInterval` + `AbortController`.
2. **One monotonic `generationRef`, compared at three points** — success `:129`, catch `:151`, **and the `.finally()` `:177`**. The third is the one that gets dropped; without it a superseded load arms a second timer and the at-most-one property is gone.
3. **`tickRef` updated on every render with NO dependency array** (`:191-193`).
4. **`document.hidden` guarded twice** — `schedule()` `:111` and `tick()` `:184` — with `visibilitychange` bumping the generation and fetching **immediately** (`:217-237`).
5. **Failure backoff, 5s doubling to a 60s cap, reset on the first success** (`:138`, `:171`, `MAX_BACKOFF_MS` `:29`).

**⚠ The two lines that leaked once, and on this screen they are worse than anywhere else:**

- **`runningRef.current = true` as the FIRST line of the mount effect** (`:201`, comment `:196-200`). The cleanup sets it false and nothing else sets it true except `resume()`, so without this line a setup → cleanup → setup cycle — which StrictMode performs on purpose — leaves the loop **permanently dead behind a pause button that still looks like it works.** On a wall that is **a TV showing a correct board frozen at the moment of mount, with nobody in the room to notice.** F57's review found this exact bug inherited from `BoardSection`.
- **`runningRef.current = false` BEFORE `clearTick()` in the cleanup** (`:211` before `:212`, comment `:204-210`). `clearTick()` alone cancels only the timer armed right now; the arming site is a `.finally()` that runs *after* cleanup, and nothing in `tick → load → finally → schedule` touches React state. **This has shipped as a defect twice in this repo.**

**⚠ What must NOT be copied: the terminal branch** (`:139-143`, `:158-163`). There is no ticket, so no `CLOSED_STATUSES` and no `status` field on the payload; no capability, so **no `clearCheckinTicket()` and no `sessionStorage` at all**; and **`isNotFound` must not stop this loop** — a 404 here is `TENANT_NOT_FOUND`, a fact about the *server*, not a dead link the user holds, and **an unattended screen that gives up permanently needs a human to notice and reload, and there is none.** **F59's loop has no terminal.** Every failure backs off to 60s and keeps trying until the server heals it. **One exception, and it is `document.hidden`** (Risk 10): `schedule()` refuses to arm while the tab reports hidden and `visibilitychange` is the only wakeup, so a kiosk reporting hidden while the panel is lit freezes indefinitely. Accepted as a ceiling; the mitigation is the kiosk checklist.

Also **not copied**: mutation-in-flight suppression and its re-arm, the pointer-hold skip, the stranded-row rescue, the scroll-once guard, and the failure-path focus restoration — no subject on a page with no submit and no row control.

### The failing tests first — `vi.useFakeTimers()`, every advance wrapped in `act()`

- **exactly one request per tick and never two in flight** — advance while a fetch is unresolved and assert the call count did not grow (A17);
- **`the poll stops when the page unmounts mid-request`** (A18) — request in flight, unmount, resolve the pending promise, advance ten intervals, **no further calls**;
- **`the poll survives a StrictMode remount`** (A19) — drive setup → cleanup → setup, advance one interval, assert a call happens;
- **`the wall board carries a working pause control (SC 2.2.2)`** (A20) — ⚠ **THE NAMED TEST, and axe cannot see any of it.** Tap pause, advance several intervals, assert **zero** calls. Tap resume, assert a call lands **before** a full interval elapses **and** that a backed-off gap was reset. Assert **one** button whose accessible **name** flips between the two Hebrew strings, with **no `aria-pressed`** and no `aria-label`; that it is the **first control in the section and precedes the rows in the DOM**; `toHaveClass("min-h-11")` and `toHaveClass("focus-visible:outline-focus")` — **never a measurement**, jsdom has no layout engine (`vitest.config.ts:9`); that it **has a text label** (`min-h-11` covers the height half only; the ×44 width half is the label); that it **keeps focus across the press**; and that it is present in the **empty** state **and in the error state**;
- `document.hidden` pauses; `visibilitychange` back to visible fetches **immediately** rather than after the interval;
- **the three freshness states read differently AS TEXT** (A21) — `toHaveTextContent`, **never a class**, because a class-only assertion *is* the colour-alone defect it is supposed to catch — with **paused beating stale**;
- **the freshness line is present, not `aria-hidden`, and `closest('[role="status"],[role="alert"],[aria-live]')` is `null`** (A22) — ⚠ **WITH A NEGATIVE CONTROL** rendering it inside a `role="status"` and asserting the selector **does** match. Every live region in this repo is a bare `role="status"` with **no `aria-live` attribute**, and `closest()` matches attributes rather than implicit ARIA, so `closest('[aria-live]')` returns `null` **even from inside one**. F33's review caught this exact vacuity; F59 does not re-earn it;
- **the CUE region does not change on a poll tick** (A23) — ⚠ scope the `MutationObserver` to `getByTestId("queue-board-cue")`, **never to `[role="status"]` broadly**: the loading region is a **second** `role="status"` that legitimately **unmounts** on the first settled response, so a broad observer goes red against correct code and gets loosened into the vacuous form. Populate the cue first, observe across **three** ticks, assert **both** that the ticks happened **and** that `takeRecords()` is empty — an identical string still replaces the Text node, so the naive version passes against broken code;
- **no content is ever announced** — no `called` cue, deliberately unlike `QueuePositionPage.tsx:144-149`;
- consecutive failures back the interval off and a success resets it — walk the ladder and pin the 60s cap in **both** directions;
- **`a 404 does not stop the loop`** (A24) — 404, advance ten intervals, assert the calls **kept coming**. Fails against a copy-paste of `:158-163`, which is exactly what a builder will have open beside them;
- **429 does not stop the loop either**;
- **a failed tick after a good load keeps the rows on screen** and only the freshness line changes (A25);
- **the error arm announces once across several consecutive failures** — the loop has no terminal, so `W-fail` can re-render for hours; assert one announcement rather than one failure and none;
- the **empty** state renders `queueBoard.empty`, the freshness line **and the pause control** (A26); **the ERROR state renders both too** — the assertion that catches a builder copying the `live &&` gate at `:295` wholesale;
- **the overflow line's arithmetic** (A27) — `waiting_total: 40` with 5 entries renders «35», **computed rather than echoed**;
- **the client renders 1, 5 and 8 entries** without asserting a count, so raising `BOARD_ROW_LIMIT` needs no frontend change (D4);
- **two entries with an IDENTICAL `first_name` both render**, at their two positions — Ruling 3's duplicate, and the test that fails if anyone keys the list by name;
- **`called: true` renders a WORD** in `text-warning-text` (A28), seeded through the **stubbed API client** — the only way it can be produced, since nothing in the product writes `called_at`;
- **the type-scale classes are pinned** (A34) — the freshness line and the overflow line carry the **name** scale, not the small bucket; the pause label carries the **small** one and **A34 must not promote it** (W-5); every `clamp()` on the page has a **`rem` term in its preferred value**. Class assertions, never measurements — **axe has no rule for font size or viewing distance**;
- **the page leaves the title and focus to the Router** (A16) — sentinel form, rendered **in isolation** inside `<StorefrontLayout>`, **never through `<Router />`** (rendering through the Router to satisfy "the title is whatever the Router set" produces an assertion that cannot fail);
- an **axe pass** on the live, empty and error states — **explicitly not sufficient**: axe has **no SC 2.2.2 rule** and cannot see a font size, so A20 and A34 are the only automated coverage of two Level-A/AA criteria on this screen and **must not be dropped as redundant with the axe row**.

### The code — the exact markup decisions

| Element | Class / shape |
|---|---|
| Page container | `<div data-testid="queue-board" className="mx-auto flex w-full max-w-[1400px] flex-col gap-6 px-4 pt-6 pb-6 md:px-8">` — **`pb-6`, not `QueuePositionPage.tsx:19`'s `pb-16`**: that value is the fixed A11yMenu trigger's footprint stated on the page, and the footer at `StorefrontLayout.tsx:146` already reserves `--space-a11y-footprint` for it (its comment `:132-145` says the reservation "belongs HERE and not on a page div"). A second reservation double-counts 68px. |
| Heading | `<h1 className="font-display text-[clamp(1.5rem,1.5rem+1.8vh,4rem)] text-ink">` + `<span aria-hidden="true" className="h-1 w-32 bg-gold" />` — the ornament **grown from `h-px w-12` to `h-1 w-32`**: at 0.634 mm/CSS px a 1px rule is 0.63mm and is not seen from a seat. |
| Freshness line | `<span data-testid="queue-board-freshness" className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink">` + `<bdi dir="ltr">{freshTime}</bdi>`. ⚠ **`text-ink`, never `text-ink-muted`, and the `text-warning-text` escalation at `QueuePositionPage.tsx:305` does NOT come across** (F-7): on a panel it drops the page's only honesty signal from **15.24:1 to 5.70:1** at the exact moment it matters most. **`font-semibold` stays; the colour swap does not.** |
| Freshness + pause row | `<div className="flex flex-wrap items-center gap-6">` — `items-center`, because baseline-aligning a 44px button against a 59px line drops it out of the line's box. |
| Pause control | `<Button variant="ghost" size="md">` with **the clamp on an inner `<span>`** (F-4). ⚠ `sizes.md` bakes `text-base` into the component (`Button.tsx:37`) and `cn()` is a plain join with no tailwind-merge (`lib/styles.ts:4-6`), so a `className="text-[…]"` on the `Button` ships **both** utilities and Tailwind's stylesheet order decides — F15's F-6 trap. **The clamp goes on a descendant, not a competitor.** Identically for the retry button. |
| List | `<ul className="flex flex-col gap-2">` — **no `Card`, no `divide-y`.** A `Card` spends 48px of vertical budget on a frame nobody sees at four metres; a divider is a hairline at 0.63mm. Whitespace is the separator. |
| Row | `<li className="flex flex-wrap items-baseline gap-6 py-2">`, called rows adding `border-s-8 border-gold-strong bg-surface ps-4`. ⚠ **`border-s-`/`ps-`, never `border-l-`/`pl-`** — `qa-greps.sh:40`. **`items-baseline`, not `items-center`**: a 75.6px number and a 59.0px name centred against each other float apart. |
| Position | `<bdi dir="ltr" className="w-[2ch] shrink-0 text-center tabular-nums font-display text-[clamp(2.5rem,2.5rem+3.3vh,9rem)] text-ink">` — `w-[2ch]` is **a fixed gutter that keeps the name column on one axis**, plus headroom against a future `BOARD_ROW_LIMIT` change (C10). It is not about two-digit numbers; at a cap of 5 the position is always one digit. |
| Name | `<bdi className="min-w-0 font-display text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink [overflow-wrap:anywhere]">` — **bare `<bdi>`, no `dir`**. `dir="ltr"` on a Hebrew name is itself a bidi defect and the worse one, because it looks deliberate. |
| Called word | `<span className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-warning-text">{t("queueBoard.called")}</span>` — **the word is what keeps the highlight out of SC 1.4.1**; the rule and the field are the other two signals, and the number and name **stay `text-ink`**. |
| Overflow line | `<p data-testid="queue-board-overflow" className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink">` — the **name** scale, never the small bucket. |
| Empty title / hint | title at the **position** scale, hint at the **name** scale, both `text-center` (`text-center` is not a banned physical-direction utility). **Not `EmptyState`** — its title is `text-xl` (23px → 1.5m), a caption on a wall. |
| Loading | **one** `<Skeleton variant="block" />` in a **`flex-1`** wrapper (**C6** — no `min-h-[567px]`; `variant="block"` is `h-full w-full` and `aria-hidden` at `Skeleton.tsx:29`). `variant="text"` is wrong twice: `h-4` bars on a 107px-row screen, and its default **three** pulses (`Skeleton.tsx:16`) are the page's whole motion budget (**C9**). |
| Error | `<p role="alert" className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink">` — the **name** scale, because the room must be able to tell a broken board from an empty one — plus `<Button variant="secondary" size="md">` resolving **`checkin.retry`**, clamp on an inner span. |
| Live regions | two `<VisuallyHidden><span role="status" data-testid="queue-board-loading-status|queue-board-cue" /></VisuallyHidden>` — the `:283-285` and `:375-379` shapes. |
| Time formatter | a module-level **multi-line** `Intl.DateTimeFormat("en-GB", { timeZone: JERusalem, … })`, `:41-46` copied. `qa-greps.sh` flags a single-line formatter without a zone, and a zoneless one reads the **device** clock — on a TV nobody has ever set the clock on. |

**No motion of any kind** beyond the boot skeleton and `Button`'s shipped hover transition: no transition, crossfade, flash, pulse, marquee, auto-scroll, carousel or highlight-on-change. **A number that changes changes in place.** This is enforced by construction — there is nothing to reduce — which discharges SC 2.3.1 and `prefers-reduced-motion` (`theme.css:155-163`) without a media query.

⚠ **The React key is `position`**, never the name and never an index-with-meaning. A name key would **collide** — on two different women with the same first name **and** on one woman holding two tickets.

### Mutation-checks (mandatory — these six are the named list)

| Mechanism | Remove it | Expect |
|---|---|---|
| **`runningRef.current = true` first in the mount effect** | move it after `void load()` | the StrictMode-remount test **RED** |
| **the unmount ordering** | move `runningRef.current = false` **after** `clearTick()` | the unmount test **RED** |
| **the pause control** | delete the button | the A20 assertions **RED** — and **axe stays green, which is the point** |
| **the `isNotFound` terminal** | copy `:158-163` across | `a 404 does not stop the loop` **RED** |
| **the live-region negative control** | render the freshness line inside `role="status"` in the main fixture | the outside-the-region test **RED**; and the control fixture must be **GREEN** — run both |
| **the clamp on the Button itself** | move it from the `<span>` onto the `Button`'s `className` | the class assertion still passes and **the rendered size is decided by stylesheet order** — this one is a **review** item, and the inner-span shape is what carries it |

- **Done when**: `make fe-test` + `make fe-build` + `make qa-greps` green with the greps **byte-identical to the baseline**; axe at **zero** violations on all three states; every mutation-check performed and restored. `git show --stat`.
- **Commit**: `feat(storefront): the wall-screen queue board, its 5s poll and its 2.2.2 pause control`

## Task 8 — The e2e journeys, the two route lists, and the 1080p fit (A29, A30, A34, F-5)
`Frontend/e2e/storefront.spec.ts`

**Three coordinated `installApi` edits or the fixture falls through to its dress-detail branch and answers a 404 that reads as a product bug**: the `BookingEndpoint` union (`:217-231`), the `BOOKING_PATHS` map (`:233-244`), and the `bookingFixture()` reply queue.

**⚠ The `/queue` arm in `gotoSettled` (`:524-558`) waits on `queue-board-freshness`, NOT on `queue-board-row`.** The helper is one `if/else` chain on `path`, so `/queue` gets **exactly one** tell for **every** journey that visits it — and this feature requires an **empty-board** journey, which renders no row at all, so a row-based tell times out and that journey cannot run. Falling through to the final `else` is worse: it waits on `page.getByText(BOUTIQUE.name)` (`:555`), and **`StorefrontLayout` renders the boutique name on no route** — it fetches it into context; the name that arm resolves against is rendered by `/accessibility`'s own page body (**F-5**, verified) — so the fallthrough would **hang**. The freshness line is present in **every** non-loading state, is written **only** on a settled response, and is therefore exactly the "the data landed" property the helper asks for.

### The journeys

- **The live board** — goto `/queue`; assert three rows with positions 1–3 and the fixture's first names; assert the rendered row text **equals** each fixture `first_name` exactly, and that no `title`, `aria-label` or `data-*` on a row carries more than the visible text; assert **`ctaBar(page)` has count 0** (`hasBookingBar()` is catalog-and-dress only); press pause and assert the freshness **sentence** changed; `axeViolations(page)` → `toEqual([])`.
- **The empty board** — its own render and its own axe pass. *Post-F58 this is the state the screen is in for most of the day; pre-F58 it is the first hour* (C5).
- **`the wall board fits a 1080p screen`** (A30) — `page.setViewportSize({ width: 1920, height: 1080 })`, five seeded entries, **`await expect(row.nth(4)).toBeInViewport()`** — ⚠ **`toBeVisible()` is the wrong matcher and must not be used**: a row 300px below the fold satisfies it (non-empty box, not `display:none`). `:758` already uses `toBeInViewport()` for exactly this question about the A11yMenu trigger. **And** `document.documentElement.scrollHeight <= window.innerHeight`. Both halves: `scrollHeight` catches the document overflowing, `toBeInViewport` names the row that did it. **After C1 this is the only mechanical guard on the boosted-root case as well** — under the A11yMenu boost row 5 sits ~57px below the fold, which `scrollHeight` alone would not name.
- **⚠ DELETED, deliberately: "assert no surname text appears anywhere on the page".** **It cannot fail.** The wire is `{position, first_name, called}` — there is no field that could carry a surname — the truncation is server-side, and `installApi` is a route stub supplying the board body directly, so **the derivation under test never runs in this journey.** Its real homes are the two backend tests (Task 1's fast table and Task 2's db-marked `name="NOA COHEN"` case). This is exactly the class Risk 4 exists for.
- **No journey may drive `called: true`** — there is no product path to it (D10).

### The three route lists — individually, because they are three different constants

| List | Line | Joins? | Why |
|---|---|---|---|
| `ROUTES` — the 375/768/1440 horizontal-scroll sweep | `:713` | **YES** | The phone is the same page and F33's two public routes are both already in it. "This is not the responsive sweep" means *the brief is a viewing distance, not a set of breakpoints* — it never meant the page skips a horizontal-overflow check. |
| `RESIZE_ROUTES` — the three SC 1.4.4 sweeps (`:1396`/`:1421`/`:1443`) | `:1363` | **YES**, and it is a **new** step | F33 joined neither. The whole point of putting a `rem` term in every preferred value is that the A11yMenu boost now has an effect worth sweeping. **`TEXT_RESIZE_BROKEN_AT_375` (`:1383`) stays empty** — `min-w-0` + `[overflow-wrap:anywhere]` on the row is what keeps it empty, and at 375 with a 32px root the row is a 106.8px number beside an 84.3px name in a 311px box. |
| `AXE_ROUTES` | `:681` | **NO** | Its `[name, path, list, boutique?]` 4-tuple **cannot pass `installApi`'s 4th (`booking`) or 5th (`tickets`) argument**, so a member would scan the empty state and nothing else. F59's axe coverage is a **bespoke journey in the shape of `:2407-2425`** — F33's own precedent for `/checkin` and `/q/`. |

> ⚠ **The e2e run builds the apps and serves them via `vite preview` with no backend**, so every journey runs against `installApi`'s interception. **No `/manage` e2e is promised** — the console's interception harness does not exist and F58 is scheduled to build it.

- **Done when**: `make e2e` green; the existing storefront and console specs stay green. `git show --stat`.
- **Commit**: `test(e2e): the wall-board journeys, the 1080p fit and the 1.4.4 sweep`

## Task 9 — Gates, the run report, and shipping
No files.

Run the full verification below, report what ran and what passed, and carry forward:

- **⚠ F59 IS NOT DEPLOYABLE TO A CUSTOMER-FACING WALL UNTIL F58 SHIPS**, and that is the headline of the run report. Nothing writes `called_at` or any status transition, so nothing is ever highlighted, no ticket ever leaves `waiting`, the board only grows all day, and — because D3 orders by arrival and D4 caps at five on the server — **the five names on the wall are the day's five earliest check-ins, unchanged from about 09:15 until midnight.** Publishing the first names of women who left hours ago, all day, on a public URL, is not «לצורך ניהול התור בלבד», which is what the shipped `checkin.notice` promises her. **F59 adds no second gate and no feature flag** — F33's Ruling 4 already covers it, and its third finding is exactly this one. F59 adds **four** lines to that checklist:
  1. The TV does not go on the wall until F58 ships.
  2. The kiosk browser runs **one full-screen tab with screen-blanking disabled** (D9's `document.hidden` ceiling, Risk 10).
  3. On a 4K panel the browser must present a **1920×1080 CSS viewport** — DPR 2, or page zoom at 200% (F-2; unzoomed, the name reads to ~2.9m against a 3–5m brief).
  4. The panel must present a viewport **at least 1080 CSS px tall** — this binds both the row count **and** legibility (C2; at 1366×768 only three rows fit *and* the name reads to 2.8m). The `BOARD_ROW_LIMIT = 3` server constant is the fallback only if a 768 panel ships anyway.
- **Risk 2 / D13 — the counsel gate, re-nagged.** `in_run_gates` F33 stays **open** and gains a **fifth item**, phrased as the public-URL question: ***what must the notice say about a first name published on a public, unauthenticated web page?*** — **not** "displayed on a public screen", which invites an answer about signage. The amended `checkin.notice` is **interim** and the Hebrew remains the user's. *Owner: the user, via counsel.*
- **Risk 1 — the board publishes first names to anyone with the slug**, and that is the ruled design. Three residuals named: a 5s poller reconstructs arrival times no timestamp is on the wire for; `waiting_total` is per-minute footfall and, pre-F58, literally the day's arrival count; and **the id → name correlation** — a ticket id plus this endpoint yields the holder's first name in two anonymous requests, which is why `schemas.py:52-55`'s rationale was rewritten (conflict 8). Upgrade path recorded, not built: a signed board URL or a per-tenant setting. *Owner: the user.*
- **Risk 13 — an anonymous flooder can hold the board permanently stale.** `queue:board:{tenant_id}` at 600/60s is spent in **12 seconds at 50 rps** and can be held spent. The board then shows a correct-but-frozen queue labelled «העדכון האחרון היה 14:07» **in room-legible type** — stale, never blank, never wrong. That bound is only true because the freshness line is at the **name** scale rather than at 24px. *Owner: F21.*
- **Risk 6 — F58 can break this board with one predicate.** A called ticket must stay `waiting`, or `position()` and the board query change **together**. `test_the_board_order_agrees_with_the_position_count` is what goes red if only one side moves. *Owner: F58.*
- **Risk 4 — two Level-A/AA criteria on this screen are invisible to axe**: SC 2.2.2 (no rule at all) and SC 1.4.4 (axe measures neither font size nor whether the root-font-size boost has any effect). A20 and A34 are the only automated coverage and **may never be dropped as covered by the axe row**. Every assertion added later to this feature must come with the same proof that it can fail.
- **C1 — the deck's F-13 mechanism was wrong and the numbers moved.** Under the A11yMenu text-size boost the fifth row sits ~57px below the fold, not on it. No unscrollable victim; A30's `toBeInViewport()` is what carries it.
- **Risk 5 — this is the third copy of the poll** and a fix to one does not reach the others. The copied comments are the mitigation.
- **Risk 7 — `ar.ts` on the storefront has no parity guard**, and F59 invents none. **F-9 — the `/נשלח|תישלח|בדרך/` register ban lives in `apps/manage` and does not govern this app**; the deck complies voluntarily and nothing enforces it.
- **NO MIGRATION shipped, and none was needed.** Say this in the run report in those words.

No push, no PR from this task — the orchestrator owns review and shipping.

---

## The dev proxy — **no `vite.config.ts` edit, on either side**, and this contradicts the brief

The brief warns that `test_spa_serving.py` asserts set equality between the live route table and a Vite proxy's segment alternation, so a new path segment needs the config edit. **Verified, and it does not apply here:**

- `frontend/apps/storefront/vite.config.ts:11-18` proxies `"/storefront"` and `"/health"` **wholesale**, with no segment alternation and an explicit "No /manage entry" comment. F59's API path is **`/storefront/queue`**, already inside that prefix.
- The set-equality test is `test_the_manage_dev_proxy_names_every_manage_api_segment` (`test_spa_serving.py:377-405`), and it reads **`frontend/apps/manage/vite.config.ts`** against `r'"\^/manage/\(([a-z|-]+)\)"'` (`:403`). **F59 adds no `/manage` route**, so it does not go red.
- The `/queue` **page** path needs no proxy entry either: it is served by the SPA catch-all, because `_RESERVED_SEGMENTS` (`main.py:345`) is `{"manage", "storefront"}` and `queue` is neither. `SHELL_PATHS` gains `"/queue"` (Task 4) to close the coverage hole.

**The warning is still live for a different reason and is recorded rather than dismissed:** the storefront proxy has **no derived guard at all**, so any future feature that adds a top-level API prefix outside `/storefront` breaks only on a developer's machine, silently, serving the SPA shell where the API should be. **F59 deliberately stays inside `/storefront` so as not to be that feature.**

---

## Verification — the full local gate sequence

```
make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q
make test-db   # Backend: pytest -m db -q
               # ⚠ needs the LOCAL_TEST_PG_URL escape hatch in backend/tests/conftest.py
               # ⚠ REVERT backend/tests/conftest.py afterwards, EVERY TIME
make fe-test   # Frontend: pnpm -r --if-present test
make fe-build  # Frontend: pnpm -r build
make e2e       # Frontend: pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`** (F59 adds no dependency, so no `[[tool.mypy.overrides]]` block and none is added), `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0 printing exactly the Part II baseline** — capture it before Task 6 and diff.
- **`make test`** — all fast tests pass. `test_queue_board_api.py` and `test_queue_board_service.py` green; `test_storefront_api.py` green with its **one deliberate literal edit** and its **five `ROUTES` guards unedited**; `test_spa_serving.py` green with its **one `SHELL_PATHS` data row**; `test_migrations.py`, `test_staff_role_gating.py` and `test_frontend_constant_parity.py` pass **unedited**; the `db`-marked modules **collected and deselected**. ⚠ **Two `test_config.py` failures are always false locally** — `Backend/.env` leaks `MEDIA_BUCKET`. CI is green. Do not chase them.
- **`make test-db`** — the baseline plus F59's new cases in `test_queue_repositories.py` and `test_queue_isolation.py`. Re-read the baseline count at build time; do not hardcode one. The `test_media_upload_s3.py` cases need MinIO and stay red locally — **expected; F59 touches no S3.**
- **`make fe-test`** — `router.test.tsx`, `api.test.ts`, `i18n-keys.test.ts`, `QueueBoardPage.test.tsx` all green; **axe at zero violations on the live, empty and error states**; **A20 and A34 present and named**; every mutation-check in Tasks 6–7 performed and restored.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error.
- **`make e2e`** — the two new storefront journeys plus `the wall board fits a 1080p screen` green; `/queue` passing all three 1.4.4 sweeps with `TEXT_RESIZE_BROKEN_AT_375` **still empty**; existing specs unchanged.
- **CI additionally** — the same db suite against Testcontainers. ⚠ **A first CI red on a test bug is budgeted** (`.memory/boutique-ci-first-run-surprises.md`); check `continue-on-error` on the job before believing it.

---

## What a local run cannot prove

| Task | The local run proves | CI-only, or not provable at all |
|---|---|---|
| 2, 5 | the board query, the order-agreement with `position()`, the exclusions, the cap-vs-total, Ruling 3's duplicate, the RLS isolation — **all of it, against real Postgres 16.14** | the same on CI's container superuser / app-role split |
| 8 | the journeys and the 1920×1080 fit against `vite preview` | the same on CI's Chromium |
| 7 | every poll mechanism, the 2.2.2 control, the freshness sentences, the class pins | **nothing** proves the type is legible from four metres. jsdom has no layout engine, CI has no TV, and Playwright's 1920×1080 viewport is 24 inches from a developer's face. **The honest checks are the millimetre arithmetic in the deck's §1.2 and A30's `toBeInViewport()`; the third is a photograph on the pilot day, which is not a CI artefact.** |
| 7 | that the freshness line renders | **not** that a woman four metres away can read it. That is C2's and F-2's whole subject and it is discharged by a **kiosk checklist line**, not by a test. |
| — | — | `called: true` reaching a real screen. **There is no product path to it until F58** — every assertion is against a stub, and **no e2e journey may attempt it.** |

**Task 4 is the milestone**: the full public surface, its posture and its wire shape are exercised end to end with no Postgres.

---

## Task-by-task file manifest

| Task | New (✚) | Modified |
|---|---|---|
| 0 | `.planning/plans/public-queue-board.md` | `.planning/specs/public-queue-board.md`, `.planning/design/screens/public-queue-board/design.md`, `…/copy.md` |
| 1 | `backend/tests/test_queue_board_service.py` | `backend/app/queue/validation.py`, `backend/app/queue/schemas.py` |
| 2 | — | `backend/app/db/repositories/queue_tickets.py`, `backend/tests/test_queue_repositories.py` |
| 3 | — | `backend/app/queue/service.py`, `backend/app/core/config.py`, `backend/app/main.py`, `backend/tests/test_queue_board_service.py` |
| 4 | `backend/tests/test_queue_board_api.py` | `backend/app/queue/router.py`, `backend/app/main.py`, `backend/tests/test_storefront_api.py`, `backend/tests/test_spa_serving.py` |
| 5 | — | `backend/tests/test_queue_isolation.py` |
| 6 | — | `frontend/apps/storefront/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/api.ts`, `…/router.tsx`, `…/__tests__/router.test.tsx`, `…/__tests__/api.test.ts`, `…/__tests__/i18n-keys.test.ts` |
| 7 | `frontend/apps/storefront/src/routes/QueueBoardPage.tsx`, `…/src/__tests__/QueueBoardPage.test.tsx` | — |
| 8 | — | `frontend/e2e/storefront.spec.ts` |
| 9 | — | — |

**NO migration file. NO `vite.config.ts` edit. NO new dependency, on either side** (`axe-core` is already a storefront devDependency — F33 added it), **so NO `uv.lock` and NO `pnpm-lock.yaml` churn.**

**Never modified, and that is an assertion:** `backend/tests/conftest.py` (local-only escape hatch), `backend/migrations/**`, `backend/tests/test_migrations.py`, `backend/tests/test_staff_role_gating.py`, `backend/tests/test_frontend_constant_parity.py`, `backend/app/storefront/router.py`, `backend/app/models/queue_ticket.py`, `frontend/scripts/qa-greps.sh`, `frontend/apps/storefront/vite.config.ts`, `frontend/apps/manage/vite.config.ts`, `frontend/apps/storefront/src/routes/QueuePositionPage.tsx`, `frontend/apps/storefront/src/lib/checkinTicket.ts`, `frontend/apps/storefront/src/__tests__/CheckinPage.test.tsx`, `frontend/packages/ui/**`, everything under `frontend/apps/manage/`.

---

## Testing plan → acceptance criteria

| Criterion | Where |
|---|---|
| **A1–A4** anonymous, cookie-blind, `no-store`, GET 405, generic 404 on an unknown Host | `test_queue_board_api.py` (fast) |
| **A5** `ROUTES` does not grow — F59 registers no GET | the **five** existing `ROUTES` guards, **unedited** (`test_the_read_throttle_is_not_inert` is the one that would redden) |
| **A6** the explicit `/storefront` literal gains `/storefront/queue` | `test_storefront_api.py` (fast, **one deliberate edit**) |
| **A7** no ticket id, no fourth field | `test_queue_board_service.py` — `model_fields.keys()`, pydantic introspection, **never a source grep** |
| **A8** the board's row order equals `position()`'s numbering for every row | `test_queue_repositories.py` (db) — **the highest-value test in the feature** |
| **A9, A10** today's waiting non-deleted rows of this tenant only; another tenant's names never appear | `test_queue_repositories.py` (db) + `test_queue_isolation.py` (db, **app role only, distinctive names**) |
| **A11** the cap truncates rows and not the total, **including two tickets for one woman** | `test_queue_repositories.py` (db) |
| **A12** the first-name rule, every row of D5 including «כהן נועה» | `test_queue_board_service.py` (fast) + the db-marked `name="NOA COHEN"` sibling — **the real home of "no surname on the wire"** |
| **A13** the board budget is its own instance and blocks with the shared 429 | `test_queue_board_service.py` (four-distinct-objects) + `test_queue_board_api.py` |
| **A14** **no migration** — the pinned CHECK and index literals are unchanged | `test_migrations.py`, shipped, **unedited** |
| **A15** `/queue` mounts `QueueBoardPage` **and the catalogue does not** | `router.test.tsx` |
| **A16** no `document.title`, no focus move — **sentinel form, rendered in isolation** | `QueueBoardPage.test.tsx` |
| **A17–A19** one request per tick; **the loop dies on unmount**; **the loop survives a StrictMode remount** | `QueueBoardPage.test.tsx` (fake timers) |
| **A20** **SC 2.2.2** — pause stops, resume restarts early and resets the backoff, one button, name flips, no `aria-pressed`, first in the section, `min-h-11`, focus ring, text label, keeps focus, **present in the empty AND error states** | `QueueBoardPage.test.tsx` — **THE NAMED TEST; axe has no rule for any of it** |
| **A21, A22** three freshness states as **text**; the line outside every announced region **with a negative control** | `QueueBoardPage.test.tsx` |
| **A23** the poll never writes into the **cue** region, scoped **by testid**, loading's first-tick unmount named as expected | `QueueBoardPage.test.tsx`, `MutationObserver` across three ticks |
| **A24, A25** a 404 **does not** stop the loop; a failed tick keeps the board and relabels it | `QueueBoardPage.test.tsx` |
| **A26–A28** the empty state's own copy + freshness + pause; the overflow arithmetic; `called` renders a **word** | `QueueBoardPage.test.tsx` (`called: true` stubbed — **no e2e may drive it**) |
| **A29** zero axe violations on every materially different state | `QueueBoardPage.test.tsx` + a **bespoke** `storefront.spec.ts` journey (**not** an `AXE_ROUTES` entry) |
| **A30** the whole board fits 1920×1080 **and the last row is in the viewport** | `storefront.spec.ts` — `toBeInViewport()`, **never `toBeVisible()`** |
| **A31** `/queue` serves the SPA shell | `test_spa_serving.py` `SHELL_PATHS` (fast, **data edit**) |
| **A32a / A32b** the `CheckinPage` assertion unchanged and green; **the amendment actually happened**, asserted against the resource bundle **never through `t()`** | `CheckinPage.test.tsx` (untouched) + `i18n-keys.test.ts` — **the only assertion in the PR that fails if D13 is forgotten** |
| **A33** `ar.ts` carries every new key non-empty | reviewed by hand; **no guard exists** (Risk 7). A32b is the one exception |
| **A34** **SC 1.4.4** — freshness and overflow at the **name** scale, the pause label at the **small** one, every `clamp()` carrying a `rem` term, `/queue` in `RESIZE_ROUTES`, `TEXT_RESIZE_BROKEN_AT_375` still empty | `QueueBoardPage.test.tsx` class pins + `storefront.spec.ts:1396/1421/1443` — **axe sees none of it** |

---

## What could go wrong in review

Every item here is a **recorded ruling**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"The brief says public GET and this is a POST."** **D1, conflict 1.** `ROUTES` (`test_storefront_api.py:186-192`) is **derived** over every GET under `/storefront`, and `test_the_read_throttle_is_not_inert` (`:1222-1234`) asserts 429 on each against a limiter installed on `app.state.storefront_rate_limiter`. A GET on the queue sibling answers 200 and reddens it. The two available fixes are worse: share the catalog's 6000/60s budget (the failure `main.py:720-722` names in writing), or weaken a guard protecting six shipped public reads. ⚠ **This is NOT F33's POST argument** — F33's routes carry a capability in the body; F59's request carries nothing.
2. **"There is no migration."** **D2, C12.** `queue_tickets` already carries every column and `idx_queue_tickets_tenant_day_active` is already the exact access path. F33's pinned literals in `test_migrations.py` are the guard, which is why F59 writes no migration test either. **A builder who concluded one was needed should have stopped and recorded it.**
3. **"The type-scale table in the spec differs from the deck's."** **F-1.** The spec's D8 table transposes two columns: its "4K @1×" column carries caps that never bind and its "200% text-only" column carries the true 4K values. The **1080p default column is right to a tenth**, so the height budget and `BOARD_ROW_LIMIT = 5` are unaffected. The deck's §1.1 supersedes it, and the correction is what exposed F-2.
4. **"The deck says spacing utilities do not grow under the boost."** **C1, and the deck is wrong.** Tailwind v4's `--spacing` is `0.25rem` and every spacing utility grows. The default column is unaffected; the boosted numbers move to chrome 501 / band 579 / five rows 636, so row 5 sits ~57px below the fold and row 4 is the last that fits. **No unscrollable victim** — the boost needs a pointer the wall does not have — and A30's `toBeInViewport()` on `row.nth(4)` is what carries it.
5. **"`text-[clamp(…)]` is the first arbitrary typography in the product."** **C7, and it is ruled rather than assumed.** `grep -rn "text-\["` over the three source trees returns zero. The `--text-*` ramp tops out at `--text-3xl: 2.25rem` = 36px (`theme.css:52`), less than half the smallest number on this board, against a 3–5m viewing distance that needs 75.6px. A34's class pins are the enforcement.
6. **"The clamp class is on a `<span>` inside the Button instead of on the Button."** **F-4, deliberately.** `sizes.md` bakes `text-base` (`Button.tsx:37`) and `cn()` is a plain join with no tailwind-merge (`lib/styles.ts:4-6`), so both utilities would ship and Tailwind's stylesheet order would decide. A descendant is not a competitor.
7. **"The freshness line does not use the shipped `text-warning-text` escalation."** **F-7.** On a panel that swap drops the page's only honesty signal from **15.24:1 to 5.70:1** at the exact moment it matters most. The state is already carried by three distinguishable **sentences**, which is what the rule against colour-alone asks for. `font-semibold` stays.
8. **"The pause label is the smallest text on a screen designed for four metres."** **W-5, on purpose.** A control the room can read is a control the room will eventually press, and a wall frozen by a passer-by reads as *live* to the next woman who sits down — D11(c) calls that actively harmful. The users the control is for (the kiosk operator, every woman who opens the same public URL on her phone, any keyboard user) are all within arm's reach of a pointer. **A34 must not promote it.**
9. **"axe passes, so the a11y work is done."** **Risk 4.** Axe has **no SC 2.2.2 rule** and measures **no font size**. A20 and A34 are the only automated coverage of two criteria that are **legally** required here, and the live-region assertion ships a **negative control** because its first specification could not fail.
10. **"The loop never stops on a 404."** **D9, deliberately, and it diverges from a shipped file the builder had open.** A 404 here is `TENANT_NOT_FOUND` — a fact about the server, not a dead link the user holds — and an unattended screen that gives up permanently needs a human to notice and reload. There is none. Pinned by a named test.
11. **"The board shows «נועה» twice."** **Ruling 3, and the board must not fix it.** The only key that would identify her is `phone`, and `queue_tickets.py:15-18` promises no read is keyed on it and calls the absence "the security property, not an omission". **F58 owns the merge.** A frontend test and a db test both assert the duplicate renders.
12. **"«ועוד 1 בתור» — why not «ממתינה»?"** **F-6 / C4.** «בתור» is a prepositional phrase that does not inflect for number, so the string is grammatical at every count without four Hebrew plural forms — and it counts **places**, which is what `waiting_total` is, rather than **women**, which under Ruling 3 the product cannot count.
13. **"The count is not wrapped in `<bdi>`."** **C3.** The storefront has no `isolateLtr` (it is `apps/manage`-only), and a digit run between two Hebrew runs resolves LTR under the UBA with no isolation. Porting a manage helper for one interpolation is a file nobody asked for.
14. **"A shipped counsel-gated string was edited."** **D13, and it is the one privacy-law deliverable in the PR.** The slot exists to be swapped and its own comment says so. The clause names **a public web page**, not "a screen in the boutique" — a notice narrower than the truth at the moment of collection is worse than silence, because it becomes an express representation she can rely on. It says **the first word of the name she entered**, never "her first name, not her surname", because D5 cannot keep that promise. «הם» → «הפרטים» is a **required** collateral edit (F-12), not a tidy.
15. **"Two shipped test files were edited."** `test_storefront_api.py`'s explicit `/storefront` literal (deliberate — `:569-571` says adding a public surface must fail one test on purpose) and `test_spa_serving.py`'s `SHELL_PATHS` (a **data** row). `test_migrations.py`, `test_staff_role_gating.py` and `test_frontend_constant_parity.py` are **unedited**, and that is the assertion.
16. **"`schemas.py`'s `TicketView` docstring was rewritten."** **Conflict 8, and it is a security rationale rather than a stale count.** From F59 onward a ticket id plus this endpoint yields the holder's first name in two anonymous requests — the caller the product already names in `he.ts`'s `checkin.lastFromDevice` comment. Leaving the sentence standing would leave a security rationale the product no longer keeps.
17. **"The board is useless until F58 ships."** **D10, said out loud rather than shipped quietly.** Nothing is ever highlighted, the board only grows, and the top five names freeze at the day's first five check-ins. **The interim claim of usefulness was deleted**, and D10(4)'s gate is the only interim position: the interim exists so the code is reviewed, tested and merged — **not so a customer reads it.**

---

## Out of scope (unchanged from the spec)

Every dispatch action — call, take-next, push-assign, skip, finish, remove, merge — **F58** · the staff waitlist panel and anything at all on `/manage` — **F58** · a ticket id on the wire in any spelling — **D7, absolutely** · server-side deduplication — **Ruling 3 / F58's merge** · any migration, column or index — **D2, none exists** · `customers.marketing_opt_in_at`, the promotion, the retention sweep, the per-boutique notice override and **final privacy wording** — **F20** · wait-time estimates and any analytics over `created_at → called_at` — pre-decided #28 · bride-priority ordering (`visit_type` is not on the wire and nothing sorts on it) · any per-boutique control over the board — no `queue_board_enabled`, no board-only URL token, no theme · a shared `usePoll` in `packages/ui` — **D9** · auto-scroll, pagination or a carousel for long queues — **D8**, declined on 2.2.2 and wire-size together · a second board layout for a portrait screen · announcing the queue to a screen reader as it changes — **D12**, declined for noise and for disclosure · per-IP or distributed rate limiting and `Retry-After` — **F21** · a storefront `ar.ts` parity guard and a storefront register guard — Risk 7 / F-9, inherited · SMS of any kind.
