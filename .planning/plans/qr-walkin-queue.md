# Plan: Feature 33 — QR self-check-in + queue tickets + live position (Epic E6, floor-management program)

**Status**: Gate 2 self-approved 2026-08-03 under Interview Q1 — F33 is not on Q1's enumerated stop-list (F17, F18, F19, F20, F29, F48). The one piece of privacy-law text is parked as an open `in_run_gates` string (`LOOP-STATE.md:1094-1099`), the F19 precedent; it blocks two strings, not the feature. The design gate self-approves under Q2.

**Spec**: `.planning/specs/qr-walkin-queue.md` (revised 2026-08-03 after a three-lens review; D1–D15, Rulings 1 and 2, 792 lines) · **Design deck**: **none exists** — F33 self-approved the design gate, so there is no `design.md`, no `copy.md` and no `prototype.html`. Everything the design pass would have fixed is either in D8/D11/D12 as a contract, or is a builder decision listed in §"What the builder still has to invent". · **Branch**: `feature/qr-walkin-queue`, worktree `.worktrees/qr-walkin-queue` · **Created**: 2026-08-03

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks; `make fe-test` + `make fe-build` for frontend ones; `make e2e` from Task 12. **Unlike every previous feature in this program, the `db`-marked suites RUN LOCALLY** — Postgres 16.14 is live at `/opt/homebrew/bin` and `scratchpad/run-db-tests.sh` recreates a clean `f33_test` and runs them (baseline on main: **353 pass in ~33s**; the 9 `test_media_upload_s3.py` errors need MinIO and stay red locally, F33 touches no S3). That harness is a **local-only patch to `backend/tests/conftest.py` that must be reverted before every commit** — §"The local db harness" and the shipping checklist both carry the line.

**Path hygiene.** The repo path contains a space and a `+`. Quote every shell path. Git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` silently skips modified tracked files (`.memory/git-add-uppercase-pathspec-trap.md`). Lowercase every pathspec and verify with `git show --stat`.

**`.claude/rules/` does not apply to this repo.** It is Kotlin/Micronaut/Exposed boilerplate for a different project. Any review finding phrased in `Either` / `@Serdeable` / `@ExecuteOn` / repository-interface terms is wrong by construction. The DB conventions that *do* apply are the ones this repo already follows: no FK constraints, TEXT not VARCHAR, soft delete via `deleted_at`, `uuid_generate_v4()`, partial indexes for active rows, `TIMESTAMPTZ`, forced RLS per tenant table.

---

## Rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **Ruling 1** — a duplicate check-in returns **no capability** | The create answers `{"ticket": null}` with no id, position or `called_at`. Recovery is client-side `sessionStorage` on the same tab. Tasks 3, 5, 9, 10 and the e2e's second journey. |
| **Ruling 2** — the `customers` write and the `customers` ADD COLUMN are dropped | One migration, one half. Consent lands on `queue_tickets.marketing_opt_in_at`. `app/queue/` imports nothing from `app.db.repositories.customers` — asserted structurally in Task 3, C2. |
| **Q1** — enumerated stop-list is F17/F18/F19/F20/F29/F48 | Gate 2 self-approves. The two counsel-gated strings ship as interim values in named slots and the `in_run_gates` entry stays open and is re-nagged in the run report. |
| **Q2** — only F34 and F42 are novel design | Design gate self-approves. There is no deck; D8/D11/D12 are the binding contract and the arrangement is the builder's. |
| **Q3 / pre-decided #47** | Every new key lands in `he.ts` **and** `ar.ts`, Arabic = the Hebrew standing in untranslated, never `""`. |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is a **legal** requirement. D11's pause and D12's live-region rule are not polish, and **axe has no SC 2.2.2 rule** — the named vitest assertions in Task 10 are the only automated coverage of a Level A criterion. |
| **pre-decided #30** | One static QR per boutique; position computed on read, never stored. |

---

## What was verified against the tree, 2026-08-03

Everything below was read off this worktree at `d67aacd`. Where the spec's citation drifted, **use the number in this table** — the spec's content claim is right in every case.

### `alembic heads` on this branch is **`0014`**, and the migration F33 BUILDS at is not the one it SHIPS at

```
cd "<worktree>/Backend" && ./.venv/bin/python -m alembic heads   →  0014 (head)
```

`0015` lives **only on F57's unmerged branch**. This was probed rather than assumed: dropping a stub `0016_probe.py` with `down_revision = "0015"` into this worktree makes alembic unable to build the revision map at all —

```
File ".../alembic/script/revision.py", line 245, in _revision_map
    down_revision = map_[downrev]
KeyError: '0015'
```

— so `alembic upgrade head` fails, the `migrated_db` fixture fails, and **all 353 db-marked tests fail for the whole life of the branch.** Therefore:

- **BUILD** the migration as **`0015_queue_tickets.py`, `revision = "0015"`, `down_revision = "0014"`** (Task 1), so the branch is self-coherent and its db tests run locally from Task 1 onward.
- **RENUMBER** to **`0016` / `down_revision = "0015"`** at rebase time, after F57 merges. Three edits: the filename, the `revision` literal, the `down_revision` literal. Task 13.
- **Re-resolve from `alembic heads` immediately before push** rather than trusting this paragraph. The recorded four-way assignment is **F57 = 0015 · F33 = 0016 · F19 = 0017 · F53 = 0018**; git cannot see that collision because the filenames differ.
- **The PR does not open until F57's `0015` is on `main`** (D15, spec Risk 9). CI tests the merge result and two `0015`s is an alembic multiple-heads error that reads as a mystery failure in an unrelated job.

### The eight drifted spec citations, re-captured

| Spec says | Actually | What it is |
|---|---|---|
| `db/repositories/customers.py:88` (cited 3×) | **`:89`** | `existing.name = name` |
| `router.tsx:48-60` | **`:49-61`** | `DOC_TITLE_KEYS` |
| `router.tsx:85-86` | **`:86-87`** | the two exact `===` matches (`/about`, `/accessibility`) |
| `apps/manage/src/App.tsx:18-27` | **`:18-28`** | `SectionKey`, ten members |
| `Nav.test.tsx:50-68` | **`:52-69`** | `NAV_LABELS` |
| `app/auth/staff.py:55-64` | **`:57-64`** | the lock-namespacing comment |
| `booking/comms_templates.py:74-81` | **`:73-80`** | `manage_link()` |
| `tests/test_storefront_api.py:591-594` | **`:592-595`** | the POST-including-the-read comment |
| `main.py:1010-1011` | **`:1011-1012`** | the F21-reparenting note |

Everything else the spec cites was spot-checked and holds exactly, including `main.py`'s router-ordinal commentary (`gateway_router` is "The SEVENTH" `/manage` router at `:1039-1043`; F33's is the **eighth**), `qa-greps.sh:23/33`, `test_spa_serving.py:399`'s `set(match.group(1).split("|"))`, `apps/manage/vite.config.ts:13-19`, `Input.tsx:20-24`, `Button.tsx:35-39`, `BoardSection.test.tsx:507-512`.

### The DDL and the two behavioural claims, run on a live Postgres 16.14

D2's `CREATE TABLE` + index were executed. **Captured, not transcribed** — these are the shapes Task 1's test pins, and the builder re-captures them from the CI server rather than pasting these:

```
CREATE UNIQUE INDEX idx_queue_tickets_active_day_phone_unique ON public.queue_tickets
  USING btree (tenant_id, queue_day, phone)
  WHERE ((deleted_at IS NULL) AND (status = ANY (ARRAY['waiting'::text, 'in_service'::text])))

queue_tickets_visit_type_check :: CHECK ((visit_type = ANY (ARRAY['bride'::text, 'evening'::text])))
queue_tickets_status_check     :: CHECK ((status = ANY (ARRAY['waiting'::text, 'in_service'::text, 'done'::text, 'removed'::text])))
queue_tickets_skip_count_check :: CHECK ((skip_count >= 0))
```

**The constraint names are Postgres-generated** — `queue_tickets_{column}_check` — which is what `pg_get_constraintdef` has to be looked up by. The `IN (…)` → `= ANY (ARRAY[…])` normalisation, the injected `::text` casts, the added parentheses and the schema qualification are all real and all observed.

Three behaviours proven by actual statements, not reasoned about:

1. **Dedup fires on a live row.** A second INSERT for the same `(tenant_id, queue_day, phone)` while the first is `waiting` → `duplicate key value violates unique constraint "idx_queue_tickets_active_day_phone_unique"`. *(This is also the mechanism behind C5 — one anonymous POST denies that number a position for the rest of the day.)*
2. **A closed ticket frees the key.** After `UPDATE … SET status='done'`, the same `(tenant, day, phone)` INSERT succeeds. D2's "served in the morning, returns in the evening" is real.
3. **D3's count really does use the partial index.** With 50 rows and `enable_seqscan=off`:
   ```
   Aggregate
     ->  Index Scan using idx_queue_tickets_active_day_phone_unique on queue_tickets
           Index Cond: ((tenant_id = …::uuid) AND (queue_day = '2026-08-03'::date))
           Filter: ((status = 'waiting'::text) AND (COALESCE(requeued_at, created_at) < now()))
   ```
   The predicate-implication prover accepts `status = 'waiting'` ⇒ `status IN ('waiting','in_service')`, and `(tenant_id, queue_day)` is a usable prefix. D2's access-path claim holds.

### Frontend facts that change what Tasks 8–11 can promise

- **`axe-core` is NOT resolvable from `apps/storefront`.** `grep -rn "axe" apps/storefront/src` returns only prose in comments; `apps/storefront/package.json:20-34` has no axe dependency. The e2e suite runs **real-browser** axe through `@axe-core/playwright` (`e2e/package.json`), which is strictly stronger than jsdom axe. See **C16**.
- **`apps/storefront/src/lib/` holds exactly two files** (`contact.ts`, `hoursText.ts`) — `checkinTicket.ts` is a third, not a new directory.
- **`apps/storefront/src/validation.ts` already exports** `MAX_CUSTOMER_NAME_LENGTH` (`:19`), `validateName` (`:36`), `normalizePhone` (`:82`), `validatePhone` (`:86`). No new mirrored constant, so `test_frontend_constant_parity.py` is untouched.
- **`StorefrontLayout` renders `{children}` unconditionally** (`:127-129`) with a context default of `{ boutique: null, loading: true, error: null }` (`:40-45`). The `{{boutique}}` interpolation has a real null window. See **C13**.
- **`apps/manage/src/__tests__/i18n.test.ts` uses per-feature `HE_F**` constants** (`:23-39`, `HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34]`) with a `.length` floor each. F33 adds `HE_F33` and folds it in — never widens an existing filter.
- **`Settings.base_domain` exists** (`core/config.py:20`) and `main.py:645-652` is the shipped injection shape.

---

## Corrections — the sixteen open review findings, each resolved and each owned by a task

The spec is binding and D1–D15 are not re-litigated. These are the places where the revised spec still disagrees with itself, with the tree, or with what F33 can actually ship. **Every one is amended into the spec in Task 0**, the F34 Task-0 / F15 Task-0 precedent; the spec text is the binding statement, this file the reasoning. Four of them change behaviour and are marked ⚙.

### C1 — the Goal's second paragraph still states the pre-Ruling-1 outcome

`spec:33` reads "A second scan from the same phone on the same boutique day … lands her on the same page, showing the position she already had." That is contradicted by `spec:335`, `spec:370`, `spec:627` and Risk 11, and it is the first behavioural sentence a builder reads.

**Resolution.** Rewrite to the post-ruling truth: *"A second scan does not create a second ticket. On the same phone in the same browser tab the page offers her a link straight back to her position with no request at all; on any other device, or after the tab closed, the server tells her only that she is already in the queue (D7, D8, Risk 11)."* Task 0.

### C2 — the Ruling-2 guard test is unwritable, and if forced into existence it cannot fail

`spec:672` requires "assert the fake customers repo recorded zero calls — that assertion *is* Ruling 2". But D5 removed the `customers` write entirely and D1's package list names only `app/db/repositories/queue_tickets.py`, so **`QueueService` has no customers-repository dependency to fake.** A builder either cannot write it, or wires a `CustomersRepository` kwarg into the constructor purely to count zero calls — restoring the exact seam Ruling 2 removed. Either way the count is structurally zero and the assertion cannot fail: the vacuity class spec Risk 4 forbids.

**Resolution — two assertions that can actually fail**, replacing the fake-call-count row:

1. **A source guard in the fast suite** (`tests/test_checkin_service.py`): read every file in `app/queue/` and assert no occurrence of `CustomersRepository` or `app.db.repositories.customers`, **and** assert `inspect.signature(QueueService.__init__)` names no parameter matching `customer`. The repo already reads source in a test (`tests/test_frontend_constant_parity.py`) and the frontend does the same shape (`i18n-keys.test.ts:53-59`).
2. **A db-marked assertion** (`tests/test_queue_isolation.py` or the service-db module): a full check-in with the opt-in **ON** and again with it **OFF** leaves `SELECT count(*) FROM customers` unchanged.

The already-specified `test_migrations.py` row asserting `customers` has no `marketing_opt_in_at` stays. Tasks 3 and 6.

### C3 — `qa-greps.sh` check 2 is a live hazard for this feature's own comments

`spec:661` names checks 6 and 7 as prose hazards and omits check 2 — the one this feature will actually trip. Verified: `qa-greps.sh:23` runs a case-sensitive `grep -rnE` over whole files with no comment stripping, `:17` sets `SRC="apps/storefront/src"`, `:33` is `check "no favorites" 'favorit|localStorage|heart' "$SRC"`. A comment in `checkinTicket.ts` saying "sessionStorage, never localStorage" — which is exactly how this repo carries its reasoning — is a red `make lint` with no code defect.

**Resolution.** Extend the hazard sentence to three checks. The `checkinTicket.ts` comment states the **positive** rule (session scope is one visit, gone when the tab closes) and never names the banned API; the argument for the choice lives in D8, not in the source file. Also flagged on Task 9's checklist because check 6's regex `[^a-zA-Z-](ml-|mr-|pl-|pr-|left-|right-|…)` matches ordinary English prose (" left-hand", " right-to-left") and check 7 matches any bare 6-hex-digit run. Tasks 0, 9, 10.

### C4 ⚙ — the duplicate branch's positive answer is a silent, free, evidence-free oracle, and both halves of the argument that made it acceptable are false

`spec:312` and `spec:761` rest acceptance on evidence: *"the oracle is no longer a silent read — it is a write that leaves evidence"* and *"a junk ticket costs nothing but a line on a screen a staffer can close"*. Neither half holds in F33.

- **Present ⇒ silent.** Submitting a phone that IS in the queue returns `201 {"ticket": null}` after the pre-check — no INSERT, no row, nothing distinguishable from a genuine re-scan in any log. The answer an attacker actually wants is free, repeatable at 10/hour per number forever, against an in-process limiter that resets on deploy and does not aggregate across replicas (`app/auth/rate_limit.py:4-33`). One static QR per subdomain means the attacker always knows which boutique.
- **Absent ⇒ a row nobody can see.** `spec:725` puts the staff panel in F58 and `spec:37` ships no staff action on a ticket. There is no screen and nothing to close it with.

**Resolution — a paragraph and a deployment-ordering constraint, not build work.** State the residual as it is: *present ⇒ silent, free and unbounded across days; absent ⇒ a row no shipped surface renders.* Then carry the same ordering constraint Risk 3 already uses for F20: **F33 is not enabled for a live pilot tenant until F58's panel can show and close a ticket.** The only alternative that closes the oracle itself is the OTP the user already priced and rejected (`spec:296`). Task 0 amends Risk 1 and adds the loop note; Task 13 carries it into the run report.

### C5 — one anonymous POST permanently denies a known number a queue position for the rest of the day

The dedup index frees its key only on a status change or a soft delete, and **F33 writes neither** (`spec:130`, `spec:37`, `spec:731`). Confirmed live in this session: with the first row left `waiting`, a second INSERT for the same `(tenant_id, queue_day, phone)` is refused. Under the pre-revision draft the victim's own scan converged on the existing ticket and she still got her position; under Ruling 1 she gets `{"ticket": null}`, and D8's pointer is on the **attacker's** device. Risk 1 reasons only about volume ("a griefing flood inside the per-tenant ceiling"), never about one targeted request.

**Resolution.** Add the targeted shape to Risk 1 — *one request, one named person, all day, unremediable in F33* — and let it ride C4's F58 ordering constraint. The remedy is a staff remove, which is F58's; no new F33 surface. Task 0.

### C6 ⚙ — a spent per-phone CREATE budget must not answer 429

`app/notifications/service.py:199-206` refuses this exact disclosure in writing for this exact key: *"A tripped PHONE budget is a fact about one person — answering 429 would turn this endpoint into an oracle for 'is this number mid-booking at this boutique'"* — implemented as `if self._phone_limiter.is_blocked(phone_key): return`, while the TENANT ceiling raises. F33's D6 collapses the distinction: all four budgets map to one `CheckinThrottledError` → 429. A prober who has spent only *k* of the 10 and receives 429 learns the number made ≥10−*k* well-formed attempts at this boutique this hour — a second presence channel that keeps working **after** the ticket exists, costs no row, and is named nowhere in D7 or Risk 1.

**Resolution — one line in the service, one row in the test table, zero new response shapes.** A spent **per-phone create** budget answers the `201 {"ticket": null}` the contract already carries. 429 stays for the **per-tenant create ceiling** and for both read budgets. Precedent-identical to the 204. Task 0 amends D6 and the error table; Task 3 implements and tests it.

### C7 ⚙ — the per-ticket read limiter cannot bound a hostile client, because its key comes from the attacker's own body

`spec:258` keys it `checkin:position:{tenant_id}:{ticket_id}` and `spec:261` claims this lets the per-tenant number "go back to being the runaway brake D6 calls it rather than the only control". A client sending a fresh random UUID per request never repeats a key, so `FixedWindowRateLimiter.is_blocked` never fires on it — while every one of those requests charges the tenant key, because `spec:269` meters misses. 3000/60s is 50 rps from one host; real brides then 429 and back off. The per-ticket budget therefore controls only a **buggy** client that reuses one id — which is real (the leaked loop), but is not the scenario D6's paragraph claims to have fixed.

**Resolution — invert what the tenant brake charges.** Consult and charge the **per-tenant** brake on **misses only**; a known ticket id rides its own 30/60s per-ticket budget and never touches the tenant key. A flood of guessed ids then denies only reads no legitimate client makes, and a real bride cannot be 429'd by someone else's id walk. The anti-token-walk property `booking/manage.py:102-117` exists for is preserved exactly (a miss is still charged); what changes is that a **hit** no longer charges the shared ceiling. Task 0 amends D6's metering paragraph; Task 4 implements and tests both directions.

### C8 — the single-slot `sessionStorage` pointer is a live capability handed to the next person on a shared device

`spec:366-369` writes one key on every successful create and offers it as "view your position". `spec:370` already contemplates two people on one device — the mother checking in her daughter — but only as an auto-redirect hazard, never noticing the slot is then occupied by the daughter's ticket. On a shared phone or a door tablet the tab is never closed, so the next arrival is offered a link into a stranger's `/q/{id}`: status, position, `called_at`, a five-second poll, and the id itself. The only clearing path is D10's terminals, none of which can fire in F33 (C11).

**Resolution.** Three parts: (a) the offer is labelled as **the last check-in made from this device**, not "your position"; (b) submitting `/checkin` for a **different phone** clears the pointer before the request; (c) the shared-device residual is named in D8 beside the mother case already written there. Tasks 0, 9, 10.

### C9 — D8 justifies `sessionStorage` by the one case it structurally cannot serve

`spec:366`: *"That is the whole recovery mechanism for the case the old server-side replay existed to serve: **she closed the tab on her own phone.**"* `sessionStorage` is scoped to the top-level browsing context and destroyed when that tab closes — `spec:771` says exactly that. The spec asserts both. Worse for the ordinary path: the Goal makes a printed QR the entry point, and an OS/camera QR open creates a **new** browsing context with an empty store, so `spec:335`'s "She re-scans on the same phone: the storefront never reaches the server" is false for the ordinary re-scan.

**Resolution.** Restate the recovery's real reach — **same tab, same session: a navigate-away-and-back, a reload, a screen lock. Not a tab close and not a QR re-scan.** Move the re-scan case into Risk 11 beside the cross-device loss, and correct `spec:335`. If same-phone re-scan recovery is actually required it needs a store that survives a new browsing context — a different decision, and one only the user who made Ruling 1 can take. Task 0; flagged in the run report.

### C10 — the retention clause is still false by design

`spec:491` claims that under Ruling 2 "nothing is copied into a permanent table". But `spec:733` hands F20 "promoting a consenting queue ticket into a `customers` row", and `customers` has no retention path at all (`app/models/customer.py:10-19` is the whole table). The notice tells the data subject «ונמחקים כמה ימים לאחר הביקור» with no qualification. Ruling 2 changed *which feature* copies her phone into the permanent table, not *whether* the product does — and a collection notice is a statement about her data, not about one feature's diff.

**Resolution.** Except the opted-in contact detail from the retention sentence, and add that exception to the counsel brief at `spec:481` (which today asks only for boutique, purpose and retention window). One clause, in a string that is gated for counsel anyway. Task 0.

### C11 — nothing in F33 can reach a terminal, and the position read's day parameter is unbound

`spec:431` calls the 200-with-`done`/`removed` "F33's real terminal" and `spec:435` calls it the thing a reviewer should check hardest — but `spec:130` gives every status transition to F58, `spec:37` ships no staff action, `spec:731` gives the sweep to F20. Every ticket stays `waiting` indefinitely. Separately, D3's count binds `:day` without saying whether it is the ticket's `queue_day` or `today_jerusalem(clock)`; with today, a ticket left waiting from an earlier day counts zero earlier sort keys and renders **position 1** — "you are next" to someone who left yesterday.

**Resolution.** (a) **Bind `:day` to the ticket's own `queue_day`** and say so in D3 — Task 2 implements it in the repository signature (`position(session, tenant_id, ticket)` derives the day from the row, never from the clock) and Task 2's tests assert an old-day ticket does not render position 1. (b) Record that until F58 ships no ticket reaches a terminal, so D10's headline test **seeds a `done` status at the service/fixture layer** rather than asserting an end-to-end branch the product cannot produce. Tasks 0, 2, 4, 10.

### C12 — the `sessionStorage` key is unbuildable from anything the storefront has

`spec:369` keys on `{tenant_slug}`. `apps/storefront/src/api.ts:225-227` carries `name` with the explicit comment "The tenant's display name, not the slug", and `grep -rn slug apps/storefront/src` returns only comments. The builder will substitute the owner-mutable Hebrew display name — a rename then silently orphans every live pointer — or invent something from `window.location`.

**Resolution.** Key on **`window.location.hostname`**. `spec:369` already concedes that origin partitioning, not the key, is what provides isolation today; the hostname is the closest honest spelling of "this boutique" the storefront actually holds. Tasks 0, 9.

### C13 ⚙ — the counsel-gated strings can render without the controller's name

D13 interpolates `{{boutique}}` from `useBoutique()`. Verified: the context default is `{ boutique: null, loading: true, error: null }` (`StorefrontLayout.tsx:40-45`) and the layout renders `{children}` **unconditionally** (`:127-129`) — it does not gate on `loading`. So on first paint of `/checkin` `boutique` is `null`, and it stays `null` for the whole session if `/storefront/boutique` fails (a suspended tenant answers 404; the read router's own budget can 429 it independently). The notice then renders with a hole, or with a literal `{{boutique}}`, where the data controller's name belongs — at exactly the moment Amendment 13 requires it. The spec's named CheckinPage test (`spec:696`) passes against that broken sentence, because it only asserts the notice is visible and not `aria-hidden`.

**Resolution.** Add two arms to D8's `/checkin` contract: while `useBoutique()` is `loading` the **form is not rendered** (no collection point without a notice); on `error` the page renders the shell's existing boutique-unavailable state rather than a nameless notice. Then strengthen the named test to assert the rendered notice **and** the opt-in label each **contain the boutique name from the fixture** — an assertion that fails against a blank or an unreplaced placeholder. Tasks 0, 9.

### C14 — `test_spa_serving.py`'s `SHELL_PATHS` is missing from the file-change list

`backend/tests/test_spa_serving.py:70-80` enumerates "Every path apps/storefront/src/router.tsx can match", each "a URL a bride can be sent directly". F33 adds two matchable paths — one of them **printed on a physical sign** — and the spec's Frontend-changes table does not list the file. Serving does work (`_RESERVED_SEGMENTS` is `{"manage","storefront"}`), so this is a silent coverage hole, not a red build, which is exactly why it needs listing: the spec enumerates every other mechanical consequence of adding a route and misses this one.

**Resolution.** `SHELL_PATHS` gains `"/checkin"` and `"/q/tick3t"` with a comment naming F33. Task 8.

### C15 — three test assertions are specified in forms that cannot fail

- **`document.title`** (`spec:698`, "assert the title is whatever the Router set"). Storefront page tests never mount the Router (`ManageBookingPage.test.tsx:83-89` renders the page inside `StorefrontLayout` only), so there is nothing to compare against; and a builder who renders through `<Router />` to satisfy the wording produces an assertion that **cannot fail**, because the parent's effect flushes after the child's. **Resolution: the sentinel form**, which is already the shipped precedent (`router.test.tsx:70` sets `document.title = ""` in a `beforeEach`): set a sentinel before rendering the page in isolation, assert it is unchanged after mount. Same for `document.activeElement`, whose half is already non-vacuous when the page is rendered directly.
- **The advisory-lock-namespacing db test** (`spec:691`) names no mechanism. A behavioural version needs a second connection holding `pg_advisory_xact_lock(hashtext(:tenant_id))` plus a bounded wait to prove non-blocking; the xact-scoped lock releases only at commit, so a naive version **hangs the suite** rather than failing it, and no shipped test in this repo does it. **Resolution: drop the db-marked row.** The key is a module-level compile-time constant, so the whole claim is `assert "checkin:" in _CHECKIN_LOCK.text` in the **fast** suite — one line, no Postgres, and it fails the instant someone pastes booking's bare key. D4 itself says the lock buys determinism, not correctness, post-Ruling-2; a two-connection blocking test is a lot of machinery for a constant.
- **The live-region assertion** was already respecified in the spec (`closest('[role="status"],[role="alert"],[aria-live]')` **with a negative control**). Keep both halves; the negative control is not optional. Tasks 9, 10, 3.

### C16 — `axe-core` on `apps/storefront`: shipped as specified, with the cheaper alternative recorded

The spec requires `axe-core` as a storefront devDependency plus a `pnpm-lock.yaml` regeneration, because no storefront source imports it today (verified). **Resolution: build it as specified** — the spec is binding and Risk 10 already budgets the lockfile. Recorded for the reviewer so it is not raised as a finding: the e2e suite already runs **real-browser** axe over the storefront through `@axe-core/playwright`, and Task 12 runs it on each materially different `/checkin` and `/q` state, which is strictly stronger than a jsdom pass (jsdom has no layout engine and no colour contrast). If the lockfile churn collides with another in-flight branch at rebase, dropping the two jsdom axe rows in favour of the e2e coverage is a defensible one-line retreat that loses no real coverage — but it is a spec change, so it goes in the run report, not in a quiet edit.

---

## Scope fence — read this before every task

**F33 ships one table, the customer's own view of her own position, and a printable QR.** It ships no staff surface at all.

| Not in F33 | Whose |
|---|---|
| Dispatch, take-next, push-assign, skip, finish, call — **every writer of `status`, `called_at`, `requeued_at`, `skip_count`** | **F58** |
| The staff-facing waitlist panel; anything that renders a queue ticket to a staffer | **F58** |
| The public wall board at `/queue` | **F59** |
| The retention sweep; `customers.marketing_opt_in_at`; promoting a consenting ticket into a customer; the per-boutique notice override | **F20** |
| OTP on check-in, in either direction | ruled out, `e6-instore-realtime.md:74` |
| Bride-priority ordering (`visit_type` records the fact and nothing sorts on it) | open product question |
| Wait-time estimates or analytics | pre-decided #28 |
| Per-visit QR codes | pre-decided #30 |
| Cross-device recovery of a ticket | **declined outright**, not deferred |
| Editing or cancelling her own ticket from the position page | out |
| A shared `usePoll` in `packages/ui` | D9 — copied, not extracted |
| SMS of any kind | out |

If a task's diff grows a staff action, a status transition, a second poll target or a `customers` import, it has left F33.

---

## The local db harness — how to run it, and the one line that must never be committed

Postgres 16.14 is live locally; there is no Docker on this box. `conftest.py`'s `postgres_url` fixture is Testcontainers-only, so a **local-only patch** adds a `LOCAL_TEST_PG_URL` escape hatch.

```bash
bash "/private/tmp/claude-501/-Users-mrwen-Documents-Github-Ryan---rawad---mrwen/0dba6822-2444-475a-a2aa-18e3d89ceffc/scratchpad/run-db-tests.sh"
# re-applies the patch if reverted, drops and recreates f33_test, runs `pytest -m db`
# (skipping test_media_upload_s3.py, which needs MinIO)
```

Extra pytest args pass through: `… run-db-tests.sh tests/test_queue_repositories.py -x`.

⚠ **`backend/tests/conftest.py` must be reverted before EVERY commit.**

```bash
git -C "<worktree>" checkout -- backend/tests/conftest.py
git -C "<worktree>" diff --quiet -- backend/tests/conftest.py && echo "clean"
```

This is the single most likely way F33 ships a defect: the patch is small, it is applied automatically by the runner, and it is invisible in a `git status` a builder skims. It appears on the checklist of every backend task and again on the shipping checklist. **`git show --stat` on every commit is the verification** — if `tests/conftest.py` appears in a commit that is not about conftest, the commit is wrong.

This harness is why F34 shipped green on its first CI run and is the reason F33's db-marked tests are written to be *executed*, not merely collected.

---

# Part I — the backend

## Task 0 — This plan, and the sixteen spec amendments
`.planning/plans/qr-walkin-queue.md` (this file), `.planning/specs/qr-walkin-queue.md`

Fold C1–C16 into the spec. The spec text is binding; this file is the reasoning. No code, no tests.

- **Goal** — rewrite `:33` per **C1**.
- **D3** — bind `:day` to the ticket's own `queue_day`, per **C11(a)**.
- **D5 / Out-of-scope hand-off** — per **C11-adjacent (Ruling 2 relocation)**: one sentence saying a queue-ticket consent is **UNVERIFIED** and must not be promoted into a marketing permission without possession proof at F20's send time. **Delete the word "evidence"** from `spec:243` — the trail records submissions, not consents.
- **D6** — the metering paragraph gains **C6** (a spent per-phone create budget answers `201 {"ticket": null}`; 429 is the per-tenant ceiling and the two read budgets only) and **C7** (the per-tenant read brake is consulted and charged on **misses only**). Delete the claim at `spec:261` that the fourth limiter restores the tenant number to a runaway brake against a hostile client; state the residual honestly instead.
- **D7** — drop the "total queue length" non-disclosure claim (`spec:327`): `position` on a fresh create *is* that number plus one, so the claim is false and a later reader must not build on it. Keep the field; it is the product.
- **D8** — **C8** (label the offer as the last check-in from this device; clear on a different-phone submit; name the shared-device residual), **C9** (restate the recovery's reach; correct `spec:335`), **C12** (`window.location.hostname` as the key), **C13** (the `loading` and `error` arms of the `/checkin` contract).
- **D13** — **C10** (except the opted-in contact detail from the retention sentence; add the exception to the counsel brief).
- **Frontend changes table** — **C3** (three qa-greps hazards, not two), **C14** (`test_spa_serving.py` row), **C16** (record the e2e-axe alternative), and the `apps/manage/vite.config.ts` row extended: insert `checkin-qr` **between `bookings` and `dashboard`** to keep the list alphabetical, and update the comment above it from "eleven"→"twelve" and "a twelfth"→"a thirteenth".
- **Testing** — **C2** (replace the fake-call-count row with the source guard + the `count(*) FROM customers` row), **C15** (the `document.title` sentinel; drop the advisory-lock db row in favour of a fast source assertion).
- **Risks** — Risk 1 gains **C4**'s honest residual and **C5**'s targeted shape, and both ride the F58 deployment-ordering constraint. Risk 11 gains **C9**'s re-scan case.
- **Citations** — re-point the eight drifted ranges from §"What was verified against the tree".
- **D15** — record the build-at-`0015` / renumber-to-`0016` rule with the `KeyError: '0015'` evidence.
- **Done when**: all sixteen are in the spec, `grep -n "lands her on the same page\|total queue length\|fake customers repo" .planning/specs/qr-walkin-queue.md` returns nothing, and this file is committed.
- Commit: `docs(planning): F33 implementation plan — Gate 2 self-approved, sixteen spec amendments`.

---

## Task 1 — The migration **and** the ORM model, as one atomic change (D2, D15)
`Backend/migrations/versions/0015_queue_tickets.py` (**new**), `Backend/app/models/queue_ticket.py` (**new**), `Backend/tests/test_migrations.py`

**The two halves ship together.** Nothing in this repo derives a mapping from a migration and no model↔migration parity test exists (`models/customer.py` / `0008_bookings.py` are the two-halves pattern). Without the ORM model every backend line D2–D5 specify is an `AttributeError` or an import failure.

**Resolve the revision id at build time.** `cd "<worktree>/Backend" && ./.venv/bin/python -m alembic heads` → **`0014 (head)`** today. Build at `0015` / `down_revision = "0014"`; Task 13 renumbers. Do not read the number off this document at rebase time.

### Tests first (`db`-marked, appended to `test_migrations.py`)

Follow that file's own convention: the round-trip test goes **last in the file**, owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")` because it mutates the live session-scoped schema (`test_migration_0014_round_trips` is the model, and its docstring says why).

1. **`test_migration_00NN_round_trips`** — upgrade applies; `queue_tickets` exists; `queue_day` is `date` `NOT NULL`; `marketing_opt_in_at` is a **nullable `timestamp with time zone` on `queue_tickets`**; `skip_count` is `integer NOT NULL`. Then `downgrade` one revision, assert the table is **gone**, `upgrade` to head, re-assert. **Both directions** — a silently no-op downgrade would stay green while shipping an unrollbackable migration.
2. **The Ruling-2 assertion** — `customers` has **no** `marketing_opt_in_at` column. A later reader who "helpfully" re-adds the ADD COLUMN half reddens a test instead of quietly reopening the write path.
3. **The pinned definitions — CAPTURE, never transcribe.** `pg_get_constraintdef` for `queue_tickets_visit_type_check`, `queue_tickets_status_check`, `queue_tickets_skip_count_check` (Postgres generates those names) and `pg_indexes.indexdef` for `idx_queue_tickets_active_day_phone_unique`, asserted byte-identical **after this feature's migration**, never after a hardcoded revision id. The shapes captured off a live 16.14 are in §"What was verified"; **re-capture on the target server rather than pasting them.** Use `test_migrations.py:388-400`'s `_STATUS_CONSTRAINT_DEF` / `_INDEX_DEF` query constants as the shape. **This is the highest-value test in the feature**: what it guards is a *future* edit — when F58 or a later feature wants a fifth status it collides with a pinned literal and a deliberate review instead of colliding with nothing.
4. **A CHECK probed on four axes**, the `test_migrations.py:73-189` shape: superuser INSERT positive and negative; app-role UPDATE positive, negative, **and a read-back proving the refusal changed nothing**; `ADD CONSTRAINT` against a populated table.
5. **`test_every_tenant_id_table_has_forced_rls` must stay green unedited** — it scans `pg_class` for any `tenant_id` table without `relforcerowsecurity`. Forgetting `enable_tenant_rls` fails *that* file, a long way from F33.

### The code

The migration is `0008_bookings.py`'s idiom verbatim: module-level `_STANDARD`, a local `_updated_at_trigger` helper, raw `op.execute` DDL, the partial unique index with a comment stating **what its predicate buys in both directions** (D2), `_updated_at_trigger("queue_tickets")`, and one trailing loop doing `GRANT SELECT, INSERT, UPDATE, DELETE ON queue_tickets TO app_user` **and** `enable_tenant_rls("queue_tickets")`. The DDL is D2's block exactly. `downgrade()` is `op.execute("DROP TABLE IF EXISTS queue_tickets")` and nothing else — no explicit index, trigger or policy drops (`0008:113-115`). **F33 touches no existing table, so it has nothing to un-touch.**

The model declares every column explicitly as `mapped_column` on `StandardColumns, Base`, `models/customer.py` being the shape. `models/customer.py` is **not edited**.

- **Done when**: `make lint` clean; `make test` green (the new tests are `db`-marked → collected and deselected); **and `run-db-tests.sh` green locally**, which is the real proof and is available here.
- ⚠ Revert `backend/tests/conftest.py` before committing. `git show --stat` must list exactly three files.
- Commit: `feat(queue): queue_tickets — the walk-in ticket table and its ORM model`.

---

## Task 2 — `QueueTicketsRepository` (TDD, `db`-marked)
`Backend/app/db/repositories/queue_tickets.py` (**new**), `Backend/tests/test_queue_repositories.py` (**new**)

**Tests first**, `db`-marked, on `test_booking_repositories.py`'s idioms (NullPool factory in `try/finally`, frozen module-constant instants, `tenant_session`).

| Method | Cases the tests must cover |
|---|---|
| `insert` | round-trips every column; `marketing_opt_in_at` `None` and set; defaults land (`status='waiting'`, `skip_count=0`) |
| `by_id(session, tenant_id, ticket_id)` | present / absent / soft-deleted / **present but owned by another tenant → `None`**. The signature carries `tenant_id` explicitly and puts it in the `WHERE` beside `deleted_at IS NULL` — `CustomersRepository`'s class docstring (`customers.py:11-12`) states the rule: *"Tenant-scoped via RLS; the explicit tenant_id predicate is redundant defense-in-depth."* RLS is safe today only because every path goes through `db/tenant.py`; a future caller reaching the repo outside `tenant_session` would otherwise turn a guessed UUID into a cross-tenant read |
| `active_today(session, tenant_id, *, phone, queue_day)` | present / different day / `done` status / `in_service` status (still live) / soft-deleted |
| `position(session, tenant_id, ticket)` | **C11(a): the day comes from `ticket.queue_day`, never from a clock.** A ticket whose status is not `waiting` → `None`. `done` and `removed` tickets are not counted. Another day's tickets are not counted. **A ticket left `waiting` from an earlier day does not render position 1** — the C11 regression, asserted directly. A `requeued_at` set on the earliest ticket moves it to the back **and shifts every other position by one**. Ties on the sort key do not crash |

The query is D3's `count(*) + 1` over `COALESCE(requeued_at, created_at)`. No `ORDER BY`, no window function — the answer is one number.

- **Done when**: `make lint` clean; `run-db-tests.sh tests/test_queue_repositories.py` green locally; `make test` green (deselected).
- ⚠ Revert `conftest.py` before committing.
- Commit: `feat(queue): the queue-ticket repository and its position count`.

---

## Task 3 — Validation, schemas, the two error classes, and `QueueService.check_in` (TDD, fast)
`Backend/app/queue/__init__.py`, `…/validation.py`, `…/schemas.py`, `…/service.py` (all **new**), `Backend/app/core/config.py`, `Backend/tests/test_checkin_service.py` (**new**)

**Tests first**, against fakes, no Postgres — `test_booking_owner_service.py`'s fake session factory is the scaffold (a statement escaping to a real session raises rather than passing silently).

### The test table

- **Shape validation**: blank name / 80-char boundary / 81 chars / each control-character class (`booking/validation.py:69-70`'s two classes) / every phone form `normalize_israeli_mobile` accepts and rejects / unknown `visit_type`. Reuse the shipped helpers; F33 invents no second name or phone rule.
- **The opt-in branch**: OFF leaves `marketing_opt_in_at` `NULL` on the ticket; ON sets it to the **injected clock's** instant. One INSERT either way.
- **C2 — the Ruling-2 structural guard, in two assertions that can fail**:
  1. read every `*.py` under `app/queue/` and assert no occurrence of `CustomersRepository` or `app.db.repositories.customers`;
  2. `inspect.signature(QueueService.__init__)` names no parameter containing `customer`.
- **The budgets**, one row each: per-tenant create spent → `CheckinThrottledError` (429); **per-phone create spent → `201 {"ticket": null}`, no INSERT, no exception** (**C6**, the `notifications/service.py:199-206` precedent); both charged **after** shape validation; **a 400 charges neither** (a blank name must not burn a real customer's allowance); a well-formed **replay does** charge, because a replay is a request.
- **Dedup**: the Python pre-check finding a live ticket returns `ticket=None` and performs no INSERT; an `IntegrityError` raised by the repository returns **the same value**, and the test asserts the two return values are equal — that equality is what makes D4's two convergence routes indistinguishable.
- **C15 — the lock key**: `assert "checkin:" in _CHECKIN_LOCK.text` (or the module constant's spelling), one fast assertion replacing the unbuildable db-marked row. It fails the instant someone pastes booking's bare `hashtext(:tenant_id)`.

### The code

- **`validation.py`** — `CheckinThrottledError` (its own class, the `StorefrontThrottledError` docstring's argument at `storefront/validation.py:45-54`) and `QueueTicketNotFoundError(DomainNotFoundError)` (inherits the 404 handler at `main.py:757-758`, **so no new handler**). The `visit_type` bound. Name and phone come from the shipped modules.
- **`schemas.py`** — `CheckinCreateRequest(ForbidExtraModel)` (`app/schemas.py:13`), `TicketView`, `CheckinCreateResponse`, `PositionRequest`. Exactly the API-surface block in the spec; no field beyond it.
- **`config.py`** — **eight** new `Settings` fields, each with the arithmetic written out in a comment the way `booking_create_*` (`:88-104`) and `storefront_read_*` (`:152-164`) do: `checkin_create_max_per_window` = 200 / `_window_seconds` = 3600, `checkin_create_max_per_phone_window` = 10 / `_phone_window_seconds` = 3600, `checkin_position_max_per_ticket_window` = 30 / `_ticket_window_seconds` = 60, `checkin_position_max_per_window` = 3000 / `_window_seconds` = 60.
- **`service.py`** — `QueueService` taking the session factory, the repository, an injectable `Clock`, and **four `FixedWindowRateLimiter` constructor kwargs** (never `app.state`, never a second key on an existing instance: `max_attempts` is per **instance** and `main.py:637-639` says so four times).

  `check_in` in order: validate shape → normalise phone → consult both create budgets (**C6**: tenant spent ⇒ raise; phone spent ⇒ return `ticket=None`) → record both → `async with tenant_session(...)`: take `pg_advisory_xact_lock(hashtext('checkin:' || :tenant_id))`, pre-check `active_today`, INSERT, compute the position from the row just written. The `except IntegrityError` wraps the **whole** `async with` — the `auth/staff.py:129-158` shape, because the error may surface at flush or at commit and catching inside would raise from an aborted transaction. **Not** `booking/service.py:333-353`, which catches inside and is the shape D4 argues against.

- **Done when**: `make lint` + `make test` green locally.
- Commit: `feat(queue): the check-in service, its four budgets and the no-oracle duplicate branch`.

---

## Task 4 — `QueueService.position` and the miss-only tenant brake (TDD, fast)
`Backend/app/queue/service.py`, `Backend/tests/test_checkin_service.py`

**Tests first.** The metering table is the whole point of this task and **C7** is what it encodes:

| Scenario | Per-ticket budget | Per-tenant budget |
|---|---|---|
| Known ticket id, ticket found (**hit**) | consulted **and charged** | **not consulted, not charged** |
| Unknown / foreign / soft-deleted id (**miss**) | consulted and charged | **consulted and charged** |
| Per-ticket budget spent | `CheckinThrottledError` → 429 | — |
| Per-tenant budget spent, then a **miss** | — | `CheckinThrottledError` → 429 |
| Per-tenant budget spent, then a **hit** on a known id | charged | **still answers 200** — this is the assertion that fails if someone puts the tenant charge back on the hit path |

The anti-token-walk property is preserved exactly: a miss is still charged, so a walk of guessed ids is not free (`booking/manage.py:102-117`'s reason). What changes is that a real bride polling her own ticket cannot be denied by someone else's id walk.

Also asserted here: a ticket whose status is not `waiting` returns `position: null`; the position's day is the ticket's own `queue_day` (**C11**, proven at the repository in Task 2 and re-asserted through the service); a missing id raises `QueueTicketNotFoundError`; **a foreign-tenant id is a miss, never a 403** (RLS makes it indistinguishable, and that indistinguishability is the security property).

- **Done when**: `make lint` + `make test` green locally.
- Commit: `feat(queue): the position read, metered per ticket with a miss-only tenant brake`.

---

## Task 5 — The fourth `/storefront` sibling router, `main.py` wiring, and the posture suite (TDD, fast) — **milestone**
`Backend/app/queue/router.py` (**new**), `Backend/app/main.py`, `Backend/tests/test_checkin_api.py` (**new**), `Backend/tests/test_storefront_api.py`

**Tests first**, on the F11 posture template (`tests/test_notifications_api.py`), which is the file a mutating public route proves itself in. A local `_client()` builds a real app with `create_app(resolver=…)`, swaps **one** `app.state` attribute for a stub, and installs `FakeAuthService` both on `app.state` and via `dependency_overrides[get_auth_service]` so the owner cookie is genuinely resolvable.

### `tests/test_checkin_api.py` must prove

- both routes answer **anonymously** (201 / 200, and **no `set-cookie`**);
- an unresolvable Host answers the generic 404 `TENANT_NOT_FOUND` — i.e. the paths are **not** in `EXEMPT_PATHS` (`tenancy/middleware.py`'s capitalised warning: never add a `/storefront` path there);
- `cache-control: no-store` on both;
- **GET stays a 405** on both;
- the tenant reaches the service as the **host-derived** id;
- each handler reaches its own service method with the right arguments;
- a service `DomainValidationError` leaves as 400, `QueueTicketNotFoundError` as 404 `NOT_FOUND`, `CheckinThrottledError` as 429 with the **byte-identical** shared body from `main.py:137-139`;
- `SPEC_ERROR_CODES` is **set-equal to the storefront's existing four** — F33 adds no error code;
- **cookie-blindness, byte-level, per route.** For the position read, `.content ==` on two identical reads (`test_notifications_api.py:162-174`). For the **create**, the `test_booking_api.py:220-236` variant: **two separate clients, compared on the FULL `.json()`, no field excluded** — with a stubbed service the two bodies are byte-identical and the full comparison is the stronger assertion. This matters because `test_owner_cookie_changes_nothing` in `test_storefront_api.py` loops a GET-only `ROUTES` and covers neither of F33's routes;
- **the no-oracle assertions, and they are the point of Ruling 1**: a second create for the same (tenant, phone, day) answers **201 with `ticket: null`**; assert on the parsed body that `id`, `position` and `called_at` are **absent from the response entirely**, not merely null-valued, so a future refactor that reintroduces a field with a null cannot pass; assert the status code is **identical** to the fresh-create branch's; assert the service-level `IntegrityError` path returns a body **byte-identical** (`.content ==`) to the pre-check path.

### `tests/test_storefront_api.py`

`test_no_route_is_registered_twice_across_routers`'s explicit `/storefront` path literal (`:585-599`) gains `"/storefront/checkin"` and `"/storefront/checkin/position"` with a comment naming F33 and `test_checkin_api.py`. **This is the one test F33 is meant to break**; the literal stays a literal on purpose (`:569-571`: "adding a public surface must fail one test on purpose") and must not be derived from the route table. **The six `ROUTES`-parametrized guards need no edit** because F33 registers no new GET (D1) — that is the dividend, and it is worth checking it really held.

### The code

`app/queue/router.py` is `notifications/router.py`'s shape: `APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])`, a **local three-line `_no_store` copy** (never an import), one service getter off `request.app.state`, one `Annotated` alias, `get_current_tenant(request)` as the first statement in each handler (never a `Depends()`). **No ordinal in the `_no_store` comment** — the running count in those comments is already out of step and F33 must not add a wrong number to it. The module docstring carries D1's argument and D7's POST-for-a-read ruling.

`main.py`: build `QueueService` in `create_app()` with its four limiter instances (the `main.py:632-644` shape, each with the "its own instance, not a second key" comment), register **one** new `@app.exception_handler(CheckinThrottledError)` returning `TOO_MANY_ATTEMPTS_BODY` verbatim — the **tenth** handler doing so — and `app.include_router(queue_router)` **after `booking_router`** with the numbered shadowing comment naming it the **fourth** `/storefront` sibling. `_register_spas(app)` stays last.

- **Done when**: `make lint` + `make test` green locally. **This is the milestone**: the full public surface, both branches of the create and the whole error table are exercised end to end with no Postgres.
- Commit: `feat(queue): the public check-in and position routes on a fourth /storefront sibling`.

---

## Task 6 — The `db`-marked concurrency and isolation suites, **with mutation checks**
`Backend/tests/test_queue_db.py` (**new**), `Backend/tests/test_queue_isolation.py` (**new**)

NullPool engines in `try/finally`, frozen module-constant clocks injected as `clock=lambda: NOW`, the `app_role_url` fixture for isolation — never `migrated_db`, because the container superuser bypasses RLS and GRANTs unconditionally and **every assertion would pass vacuously**.

### The dedup race — a FORCED INTERLEAVE against the REPOSITORY, never `asyncio.gather`

`gather` does not order two transactions: under it the loser most often loads *after* the winner commits, takes the service's Python pre-check, and **never reaches the insert at all** — so the branch the test exists to prove is green without ever executing (`test_booking_owner_db.py:1313-1336` states this in full).

The mechanism: `tenant_session` is `async with session_factory() as session, session.begin()`, so **exiting the context manager is the commit**, and two nested `tenant_session`s on one NullPool factory take two separate connections. Under READ COMMITTED the loser's statement sees the winner's commit.

Written as a **pair**, because either alone can be passed by a coin flip:

- *loser loaded first, winner commits inside* → the loser's insert raises `IntegrityError`; read back on a **fresh** connection and assert exactly **one** live ticket for that `(tenant, phone, queue_day)`;
- *a ticket already `done` for that phone and day* → the second insert **succeeds** and both rows survive (the partial predicate's `status IN (…)` clause, asserted as a decision rather than an accident — verified live in §"What was verified").

Plus: a **soft-deleted** ticket does not block a new one; the same `(phone, queue_day)` under a **second tenant** does not either.

### ⚠ MUTATION-CHECK, and it is not optional

After the interleave pair passes, **remove the mechanism and confirm the test goes RED, then restore**:

1. Drop the unique index (`DROP INDEX idx_queue_tickets_active_day_phone_unique` in a scratch `f33_test`, or comment the `CREATE UNIQUE INDEX` out of the migration and re-run) → the `IntegrityError` test **must fail**. Restore.
2. Remove the advisory lock from the service → the pre-check test's determinism claim weakens; record what actually changes rather than asserting it does. (Post-Ruling-2 the lock buys determinism, not correctness, so this one may legitimately stay green — **write down which of the two it was**, because a reviewer will ask.)

A race test that passes with its guard removed is vacuous. F34 did this and it is why its concurrency tests were trusted. The same discipline applies in Task 10 to the poll's unmount guard and pause control.

### Also in this module

- **Service-level dedup convergence** — a second `check_in` with the same phone and day returns **`ticket=None`** (never the first ticket's id) and writes exactly one row; a read-back proves the original row is **unchanged**. Asserted at the service layer separately from the interleave, because at the service layer the interleave is unreachable by construction and a "forced interleave" there would assert the Python pre-check and be silently vacuous.
- **The Jerusalem day boundary, driven from the injectable clock** — two check-ins for one phone at `20:00Z` and `21:30Z` on 2026-07-18 (Jerusalem 23:00 on the 18th and 00:30 on the **19th**) are **two** tickets; `05:00Z` on 2026-07-19 (Jerusalem 08:00 on the 19th, a different **UTC** day) is refused as a duplicate of the second. And the same pair across the 2026-03-27 spring-forward. **This test is only writable because `queue_day` is a stored column fed by an injectable clock** (D4) — it cannot be written against a database-clock expression index at all, which is D4's argument made mechanical.
- **C2's second half** — a full check-in with the opt-in ON, and again OFF, leaves `SELECT count(*) FROM customers` unchanged.
- **C11's seed** — since nothing in F33 writes a terminal status, seed `status='done'` directly to exercise the closed-ticket reads (`position` is `None`, `by_id` still returns the row, the dedup key is free).
- **`test_queue_isolation.py`** — connected **only as the app role** over a NullPool engine via `app_role_url`. Tenant A writes a ticket; **tenant B's every reader returns None/empty/0**; **tenant B writes a ticket with the IDENTICAL phone and the identical `queue_day`** (which is what proves the unique index is tenant-scoped — a phone is not a cross-tenant identity); tenant B's position count never counts A's tickets; tenant A re-reads and nothing of hers moved; a foreign-tenant ticket id reads as **missing, never a 403** that would confirm existence. Consent lives on this same table, so "B cannot read or set A's consent" falls out of the same assertions.

- **Done when**: `run-db-tests.sh` green locally **including the mutation check performed and restored**; `make test` green (deselected); `make lint` clean.
- ⚠ Revert `conftest.py` before committing. ⚠ Re-run `run-db-tests.sh` after restoring the index/lock, to prove the restore actually restored.
- Commit: `test(queue): forced-interleave dedup, the Jerusalem day boundary and RLS isolation`.

---

## Task 7 — `segno`, `checkin_link()`, and the eighth `/manage` router (TDD, fast)
`Backend/pyproject.toml`, `Backend/uv.lock`, `Backend/app/queue/manage_router.py` (**new**), `…/schemas.py`, `…/service.py` (or a small `qr.py`), `Backend/app/main.py`, `Backend/tests/test_checkin_qr_api.py` (**new**), `Backend/tests/test_checkin_qr_link.py` (**new**), `Backend/tests/test_spa_serving.py`

**The dependency first, both files together.** CI runs `uv sync --locked` as its very first step, so a `pyproject` edit without a regenerated lockfile fails before lint or tests: `cd Backend && uv add segno`, commit **both**. Pure Python, no transitives, no native build, and it ships `py.typed` (verified against 1.6.6) — **no `[[tool.mypy.overrides]]` block**, so the boto3 precedent at `pyproject.toml:66-70` does not apply.

**Tests first.**

- **`test_checkin_qr_link.py`** — `checkin_link()` as a pure function, the `test_booking_comms_templates.py:70-77` shape: always `https`, dev `base_domain` included, no double slash, the slug is not escaped away.
- **`test_checkin_qr_api.py`** — its own per-router `ROUTES` table (one row), the convention `dashboard/router.py`'s docstring names, because **seven** routers already mount `/manage` and a duplicated `(method, path)` silently wins or loses on include order with no error. Plus: 401 with no session; **200 for a shift manager** (the both-roles decision, asserted rather than assumed); `cache-control: no-store`; the URL is composed from the **host-derived slug** and the injected `base_domain` (two different hosts → two different URLs); the response is JSON and `qr_svg` **starts with `<svg` AND contains `xmlns="http://www.w3.org/2000/svg"`**; `SPEC_ERROR_CODES == {NOT_AUTHENTICATED, NOT_AUTHORIZED}` — **`CSRF_ORIGIN_MISMATCH` deliberately absent**, because `CsrfOriginMiddleware` fences mutating methods only and this is a GET.

  ⚠ **The `xmlns` half is the assertion that matters.** Verified against segno 1.6.6: `save(buf, kind="svg")` emits an XML declaration and fails the `<svg` assertion; **`svg_inline()` passes the `<svg` assertion and emits no `xmlns`, rendering BLANK through a `data:` URI** — a green suite and an empty square on a printed poster. Only `save(buf, kind="svg", xmldecl=False)` is correct.
- **`test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment`** — **no test edit**; it goes red until `vite.config.ts` gains `checkin-qr` (Task 11), which is the intended forcing function. The segment must be **lowercase letters and hyphens only**, or the scraping regex `r'"\^/manage/\(([a-z|-]+)\)"'` returns `None` and the failure reads as "no proxy key found".
- **`test_staff_role_gating.py` — no edit.** Its walker derives from the live route table, so the new route is default-deny-checked and matrix-checked for free. It must **not** join `OWNER_ONLY`, or the walker reports `unenforced_owner_only`; omitting `require_role` entirely is a red build.

### The code

```python
def checkin_link(*, slug: str, base_domain: str) -> str:
    return f"https://{slug}.{base_domain}/checkin"
```

Pure, module-level, keyword-only, unit-testable with no app — `manage_link()`'s exact sibling (`booking/comms_templates.py:73-80`). `base_domain` is injected at construction from `Settings` (`main.py:645-652` is the shipped shape), never read from a global inside a handler; `slug` comes from `get_current_tenant(request).slug`, which the Host header bound. **The frontend cannot do this** — `slug` appears nowhere in `apps/manage`.

```python
buf = io.BytesIO()
segno.make(url).save(buf, kind="svg", xmldecl=False)
qr_svg = buf.getvalue().decode()
```

`manage_router.py` is `app/dashboard/router.py` verbatim — the smallest shipped `/manage` router: `dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))]` at router level, a local three-line `_no_store`, one service getter off `app.state`, one `Annotated` alias, one handler. No audit row, no body, no rate limiter, **no `AuditAction` member** — nothing here writes.

`main.py`: `app.include_router(queue_manage_router)` **after `gateway_router` and before `storefront_router`** (`:1043-1046`), keeping every `/manage` router contiguous and ahead of the anonymous surfaces, carrying the numbered shadowing comment as **"The EIGHTH"** and naming `test_checkin_qr_api.py`'s `ROUTES` table.

- **Done when**: `make lint` + `make test` green locally, except `test_the_manage_dev_proxy_names_every_manage_api_segment`, which is **expected red until Task 11** — say so in the commit body.
- Commit: `feat(queue): the printable check-in QR on an eighth /manage router`.

---

# Part II — the storefront

## Task 8 — Router routes, the API client, the shell-serving row, and both i18n bundles
`Frontend/apps/storefront/src/router.tsx`, `…/api.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/router.test.tsx`, `…/__tests__/api.test.ts`, `Frontend/apps/storefront/package.json`, `Frontend/pnpm-lock.yaml`, `Backend/tests/test_spa_serving.py`

**Tests first.**

- **`router.test.tsx`** — `/checkin` and `/q/abc` match their own routes; an **unknown ticket reaches the position page**, not the catalog (the `/b/{token}` precedent test); a stray `%` decodes to the raw segment rather than throwing; the two `DOC_TITLE_KEYS` resolve; **the ticket id never appears in `document.title`** — no shipped comment states that rule (`router.tsx:59-61` is about outcome copy, not tokens), so **F33 establishes it and this assertion is the only thing holding it**.
- **`api.test.ts`** — `createCheckin()` and `getQueuePosition()` POST to the right paths with the right bodies, snake_case verbatim, **no case conversion ever on this client**.
- **`test_spa_serving.py`** (**C14**) — `SHELL_PATHS` gains `"/checkin"` and `"/q/tick3t"` with a comment naming F33. `test_every_storefront_router_path_serves_the_shell` is parametrized over it and needs no other edit.

### The code

`router.tsx`, the four coordinated edits only one of which the compiler forces:
`RouteName` +2 · `RouteMatch` +2 arms (with the token-is-opaque comment) · `DOC_TITLE_KEYS` +2 (**compiler-forced**) · `QUEUE_PATH = /^\/q\/([^/]+)$/` · two `matchRoute` branches — `/checkin` as an exact `===` beside `/about` and `/accessibility` (`:86-87`), `QUEUE_PATH` **before the unconditional `return { name: "catalog" }`**, that ordering load-bearing for the same reason `/b/{token}`'s is (`:92-96`) · two `case`s in the render switch. ⚠ **`default: return <CatalogPage />` means a missing `case` compiles clean and renders the dress grid under the check-in title** — the router test is the only thing that catches it.

`api.ts` gains `CheckinCreateRequest`, `CheckinCreateResponse`, `TicketView` and the two methods on the exported `api` object. **No new `case` in `errorMessageKey` (`:48-77`)** — F33 adds no error code, and the four already mapped cover this surface.

`package.json` gains `axe-core` as a devDependency at `^4.12.1` (matching `apps/manage/package.json:28`), and `pnpm-lock.yaml` is regenerated (**C16**). Without it Task 9's and Task 10's axe rows do not resolve their import at all, and the failure reads as a broken test file rather than a missing dependency.

`he.ts` gains `document.checkin`, `document.queuePosition` and a new `checkin.*` block; `ar.ts` gains **the same keys**, Hebrew standing in untranslated, **never `""`** (i18next's `returnEmptyString` default renders `""` rather than falling back). The two counsel-gated values — `checkin.notice` and `checkin.optIn` — are D13's interim Hebrew **verbatim**, in named slots, and **no component may hardcode any part of either sentence**.

⚠ **Once `checkin` exists as an `he.ts` section, any quoted `"checkin.…"` literal anywhere in `apps/storefront/src` is scraped as an i18n key** by `i18n-keys.test.ts` and must resolve to a defined, non-empty Hebrew string. A `data-testid` named `checkin.submit` fails the suite with a confusing "missing from he.ts".

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean; `make test` green including the `test_spa_serving.py` row.
- Commit: `feat(storefront): the /checkin and /q routes, their API client and both i18n bundles`.

---

## Task 9 — `checkinTicket.ts` and `CheckinPage`
`Frontend/apps/storefront/src/lib/checkinTicket.ts` (**new**), `…/routes/CheckinPage.tsx` (**new**), `…/__tests__/CheckinPage.test.tsx` (**new**)

**Tests first.**

- Every validator fires **on the forward press only** — never on blur, never on input; all messages appear at once; focus lands on the first failure; **no request is issued** on a failed validation (`BookPage.tsx:566-592`'s house rule).
- The opt-in is **unchecked by default** and its value reaches the request.
- **C13** — the collection notice **and the opt-in label** are rendered as visible text, are not behind a disclosure, are not `aria-hidden`, **and each CONTAINS the boutique name from the fixture**. Plus the two new arms: while `useBoutique()` is `loading` the **form is not rendered**; on `error` the page renders the shell's boutique-unavailable state rather than a nameless notice.
- The phone field's `help` text is wired into its `aria-describedby` (`Input.tsx:20-24`); the submit carries `min-h-11` (`size="md"`; `sm` is `min-h-9` = 36px, **under the 44px floor**).
- A double-tap fires **one** request — guarded by a **re-entrant boolean, not by `disabled`**, because React commits `disabled` asynchronously and a fast double-tap on iOS fires two clicks inside one frame (`BookPage.tsx:769-772`).
- A 429 renders its own copy, **names no duration**, does not auto-retry. **A failed submit moves focus to the error** — a `useEffect` keyed on the error state, **never** a `.focus()` in the `catch`, because the alert node does not exist yet when `setError` runs (`BoardSection.tsx:306-319`).
- **The `sessionStorage` pair (D8, C8, C12):** with **no** entry the page renders the form, **no** recovery link, and **issues no request on mount** — asserted as a call count of **zero**, because "zero server round-trip" is the security property Ruling 1 depends on and a helpful `useEffect` would silently reintroduce a lookup. With an entry it renders the link to `/q/{id}` and **still issues no request**. A successful create **writes** the id; a `{"ticket": null}` response **writes nothing** and renders the already-in-queue copy **with no navigation**. **C8**: submitting a *different* phone from the one that wrote the pointer **clears it before the request**, and the offer's label reads as *the last check-in made from this device*, not "your position".
- **C15** — **the page does not touch `document.title` and does not move focus on mount**, in the **sentinel** form: set `document.title` to a sentinel and record `document.activeElement` before rendering the page **in isolation** (never through `<Router />`), assert both unchanged after mount. `router.tsx:258-273` overwrites both one tick later, so without these the dead code reads as working.
- An axe pass.

### The code

`checkinTicket.ts` is **~6 lines** — read / write / clear one `sessionStorage` entry keyed on `window.location.hostname` (**C12**), its own module so the three call sites (create success, `/checkin` mount, D10's terminals) share one key string.

⚠ **C3 — the comment in this file must state the positive rule** ("session scope: one visit, gone when the tab closes") and must **never name the banned API.** `qa-greps.sh:33` greps whole files including prose for the literal `localStorage` and has no exemption mechanism; the argument for the choice lives in D8. The same file's other prose must avoid ` left-`, ` right-`, `pr-`, `pl-`, `ml-`, `mr-` and any bare 6-hex-digit run, which checks 6 and 7 also match in English comments.

`CheckinPage.tsx`: one `h2` under the shell's `h1`; the recovery offer above the form; three fields (`Input` name, `Input` phone with `help={t("checkin.phoneHint")}`, a two-option `visit_type` chooser); the collection notice above the opt-in; the unbundled **native checkbox** carrying the gated label (**never `@boutique/ui`'s `Toggle`** — it renders `role="switch"`, the wrong semantic for a consent); one primary submit at `size="md"`. The page-owned bottom gutter uses the identical container class the two existing non-catalog routes use (`BookPage.tsx:50-53`, `ManageBookingPage.tsx:31-36`); `hasBookingBar()` is catalog-and-dress only, so this route reserves no CTA space. Numerals get `<bdi dir="ltr">`; owner- or customer-authored text gets a **bare** `<bdi>` (`dir="ltr"` on Hebrew is itself a bidi defect), and because i18next interpolation cannot carry a `<bdi>`, copy splits into lead + isolated value + tail (`ManageBookingPage.tsx:127-138`).

- **Done when**: `make fe-test` + `make fe-build` green; `make lint` green **including `qa-greps.sh` printing exactly the pre-existing baseline** — capture the baseline before this task and diff it.
- Commit: `feat(storefront): the check-in form, its collection notice and the same-device recovery pointer`.

---

## Task 10 — `QueuePositionPage` — the poll, the 2.2.2 pause and the terminals
`Frontend/apps/storefront/src/routes/QueuePositionPage.tsx` (**new**), `…/__tests__/QueuePositionPage.test.tsx` (**new**)

**Tests first**, with `vi.useFakeTimers()` and every advance wrapped in `act()`.

| # | Assertion | Why it cannot be folded away |
|---|---|---|
| 1 | exactly one request per tick and **never two in flight** — advance timers while a fetch is unresolved and assert the call count did not grow | the arm-on-settle property, by construction |
| 2 | **the unmount guard** — with a request in flight, unmount, resolve the pending promise, advance ten intervals, assert **no further calls** | fails against the pre-fix shape and is the only thing that catches it; `0c7015a`'s own regression test is the model |
| 3 | `document.hidden` pauses; `visibilitychange` back to visible fetches **immediately** | browsers throttle background timers to ≥1/min, so an unpaused loop looks live while being a minute stale |
| 4 | **the pause control stops the loop** (tap, advance several intervals, assert no calls) **and resume fetches before the interval elapses** and resets a backed-off gap; **one** button whose accessible **name** flips, **no `aria-pressed`**; it is the **first** control in the section; `toHaveClass("min-h-11")` and `toHaveClass("focus-visible:outline-focus")`; it has a **text label**; it keeps focus across the press | **the only automated coverage of SC 2.2.2, a Level A criterion axe has no rule for.** Never a measurement — jsdom has no layout engine, so `getBoundingClientRect()` is 0 and `getComputedStyle().minHeight` is empty (`vitest.config.ts:9`); `BoardSection.test.tsx:507-512` is the working precedent, and `min-h-11` covers the **height** half only — the ×44 width half is the text label |
| 5 | **the three freshness states read differently as TEXT** — live / paused / stale, `toHaveTextContent`, never a class | a class-only assertion is exactly the colour-alone defect it is supposed to catch |
| 6 | consecutive failures back the interval off and a success resets it — walk the whole ladder and pin the cap in **both** directions (it did not double past 60s, and the next call still comes) | |
| 7 | **404 stops the loop**; **a malformed id stops the loop**; **`status: "done"` stops the loop on a 200** — advance ten intervals, assert no further calls | the success-terminal is the only place in the product where a 200 ends a loop, and getting it wrong is invisible: the page keeps working, it just never stops. **C11**: seed the `done` status in the fixture — nothing in F33 can produce it |
| 8 | **429 does NOT stop the loop** — it backs off and resumes | |
| 9 | **the announced region does not change on a poll tick** — populate the region, observe with a `MutationObserver` across three ticks, assert **both** that the ticks happened and that `takeRecords()` is empty | the naive version passes against the broken code: assigning an identical string still replaces the Text node |
| 10 | **the called transition IS announced, once** — one write on the `waiting → called` edge, no further writes on subsequent ticks observing the same fact | |
| 11 | **the freshness line is outside every announced region** — `closest('[role="status"],[role="alert"],[aria-live]')` is `null`, **with a NEGATIVE CONTROL**: a fixture that renders the line **inside** a `role="status"` and asserts the selector **does** match | the earlier `closest('[aria-live]')` form was vacuous — every live region in this repo is a bare `role="status"` with no `aria-live` attribute (`BoardSection.tsx:556`, `BookPage.tsx:1356`, `ManageBookingPage.tsx:460`) and `closest()` matches attributes, not implicit ARIA. The control is what proves the test can fail |
| 12 | **the terminals clear the `sessionStorage` pointer** — after a 404, after a malformed id and after a `done` status, the entry is gone | so `/checkin` stops offering a link into a dead page |
| 13 | **C15** — the page does not touch `document.title` and does not move focus on mount, **sentinel form** | |
| 14 | an axe pass — **explicitly not sufficient**, and row 4 must not be dropped as redundant with it | |

### ⚠ MUTATION-CHECK, and it is not optional

After rows 2 and 4 pass: **remove the mechanism and confirm the test goes RED, then restore.**

1. Delete `runningRef.current = false` from the cleanup (leaving only `clearTick()`) → **row 2 must fail.** Restore.
2. Make the pause control a no-op (or drop the `stopped` guard from `schedule()`) → **row 4's "assert no calls" must fail.** Restore.

Both are cheap, both take one line, and both are the difference between an assertion and a decoration. F34's concurrency tests were trusted because this was done; the same standard applies to the two client-side guards that ship broken twice in this repo's history.

### The code

The loop is **copied** from `BoardSection.tsx`, not extracted (D9) — the comments come with it verbatim, including the two that name the defects, so the copies are greppable by their own prose. What the copy carries:

1. schedule-after-settle, **one arming site** (`BoardSection.tsx:104-124`) — `schedule(ms)` clears any pending timer, refuses to arm when stopped or `document.hidden`, and is called only from a request's `.finally()` or a user intent. Not `setInterval` + `AbortController`;
2. one monotonic `generationRef` compared at **three** points — success, catch, **and the `.finally()` re-arm**; missing the `.finally()` compare lets a superseded load arm a second timer and the at-most-one property is gone;
3. `tickRef` updated on every render with **no dependency array** (`:78-80, 244-246`);
4. `document.hidden` guarded **twice** (in `schedule()` and in `tick()`), and `visibilitychange` back to visible bumps the generation and fetches immediately;
5. 5s→60s backoff, reset on the first success;
6. **the terminal branch** — D10's set, which is **not** F34's `{401, 403}`: the storefront carries no session, so both of those are unreachable and copying them ships a dead branch while missing the live ones.

**Not copied, because they have no subject**: mutation-in-flight suppression and its re-arm (this page never mutates), the pointer-hold skip, the stranded-row rescue, the scroll-once guard.

The page is a discriminated-union view state (`loading | live | notFound | failed`), the `ManageBookingPage.tsx:41-49` shape. The live arm shows the position as a large number, her status in words, the pause control, and the **non-announced** freshness line. `called_at` set is its own visual state and its own sentence — "go to the counter" is the most valuable thing this screen can say and the only reason `called_at` is read in F33 at all. Three freshness keys derived in one line, `BoardSection.tsx:456`'s shape:

```ts
const freshKey = stopped ? "checkin.pausedAt" : stale ? "checkin.staleAt" : "checkin.updatedAt";
```

All past tense — «עודכן 14:07» says *this was true at 14:07*, never «בזמן אמת», which a poll cannot keep even for one interval.

- **Done when**: `make fe-test` + `make fe-build` green; every row above is a named `it(...)`; both mutation checks performed, observed red, and restored; axe at zero violations; `make lint` green with a `qa-greps.sh` output byte-identical to the baseline.
- Commit: `feat(storefront): the live position page — 5s poll, the 2.2.2 pause and three terminals`.

---

# Part III — the console, the journey, and shipping

## Task 11 — The manage console's QR section
`Frontend/apps/manage/vite.config.ts`, `…/src/App.tsx`, `…/src/api.ts`, `…/src/components/CheckinQrSection.tsx` (**new**), `…/src/i18n/he.ts`, `…/src/i18n/ar.ts`, `…/src/__tests__/CheckinQrSection.test.tsx` (**new**), `…/src/__tests__/Nav.test.tsx`, `…/src/__tests__/i18n.test.ts`

⚠ **Keep this diff APPEND-SHAPED.** F57 is rewriting `App.tsx` and both manage i18n bundles on an unmerged branch and has extracted the poll loop into `lib/usePoll.ts`. These are the two most contended files in the repo right now; expect a rebase conflict and make it trivial to resolve.

**Tests first.**

- **`Nav.test.tsx`** — `NAV_LABELS` gains «קוד סריקה» **in position 8** (after «לוח היום», before «צוות»), and the shift-manager slice becomes `.slice(0, 9)`. Row 0 must stay «סקירה» — `App.tsx`'s initial `section` and its `reachable[0]?.key` fallback both land there. The array is compared with an order-sensitive `toEqual`.
- **`i18n.test.ts`** — a **new `HE_F33` constant with its own floor**, folded into `HE`. **Not merged into an existing constant**: the file's own comment says two constants rather than one widened filter is deliberate, because folding lets a feature's floor shrink and still pass. Plus the ar-parity assertion.
- **`CheckinQrSection.test.tsx`** — the URL renders as selectable text; the `<img>` carries a non-empty `alt`; a load failure renders a `role="alert"`; an axe pass.
- **`test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment`** goes **green** with this task's `vite.config.ts` edit — it has been red since Task 7, deliberately.

### The code

- `vite.config.ts` — `MANAGE_API` gains `checkin-qr` **between `bookings` and `dashboard`** to keep the list alphabetical, **and the comment above it moves from "eleven"→"twelve" and "a twelfth"→"a thirteenth"** (the comment goes stale otherwise, and the spec listed only the constant edit). The test is order-insensitive (`set(match.group(1).split("|"))`) but the file is read by humans.
- `App.tsx` — `SectionKey` +`"checkinQr"`; one `NAV` row `{ key: "checkinQr", labelKey: "nav.checkinQr", roles: ALL }` inserted **after `board` and before `staff`**, keeping the two owner-only rows structurally last; one render branch. The landing constant is **not** touched.
- `api.ts` — `CheckinQrResponse` + one `apiFetch` wrapper. No case conversion; this app speaks the backend's snake_case verbatim.
- `CheckinQrSection.tsx` — heading, the `<img src={"data:image/svg+xml;utf8," + encodeURIComponent(qr_svg)} alt={…} />`, the URL as selectable text (a printed QR with no legible URL beside it strands anyone whose camera fails), a print affordance, and the `StaffSection.tsx` skeleton / alert / `h2 tabIndex={-1}` shape.
- `he.ts` / `ar.ts` — `nav.checkinQr` + a `checkinQr.*` block, **flat dotted keys appended as a per-feature block** (the F15/F51/F52/F17 shape, never the pre-F15 nested `nav: {}` object); **both files**, or the ar-parity guard reddens.

- **Done when**: `make fe-test` + `make fe-build` green; `make test` green **with the SPA-proxy test now passing**; `pnpm -r lint && pnpm -r typecheck` clean.
- Commit: `feat(manage): the printable check-in QR section and the ninth nav row`.

---

## Task 12 — The two e2e journeys
`Frontend/e2e/storefront.spec.ts`

**Three coordinated edits or `installApi` falls through to its dress-detail branch and answers a 404 that reads as a product bug** — verified against `storefront.spec.ts:217-241, 336-395`: the `BookingEndpoint` union, the `BOOKING_PATHS` pathname map, and the `bookingFixture()` default reply queue all gain `checkin` and `checkin/position`.

**Journey 1 — the happy path.** `goto /checkin`; wait for **real content**, never a skeleton (an axe scan against a skeleton passes vacuously — `gotoSettled`'s own rule); fill by Hebrew accessible name; submit; land on `/q/…`; assert the position; **assert `ctaBar(page)` has count 0** (this route reserves no CTA gutter); run `axeViolations(page)` against `toEqual([])` on **each** materially different state — form, form-with-errors, live position, closed.

**Journey 2 — Ruling 1, short.** Submit the **same phone twice** (the fixture's second reply for `checkin` is `{"ticket": null}` — the two-element reply queue is exactly what `take()` exists for). Assert the second submit **stays on `/checkin`**, renders the already-in-queue copy, and shows **no position anywhere on the page**. That is the end-to-end statement that the oracle is closed.

**No `/manage` e2e is promised** — the console's interception harness does not exist and F34's Risk 8 already records the gap; F58 is scheduled to build it.

- **Done when**: `make e2e` green, both new journeys included, every existing spec still green.
- Commit: `test(storefront): the check-in journey and the already-in-queue journey`.

---

## Task 13 — Renumber, gates, and the run report
`Backend/migrations/versions/0016_queue_tickets.py` (renamed), `Backend/tests/test_migrations.py` (revision literals only)

**Precondition, and it is the only hard one in this plan: F57's `0015` must be on `main` before this task runs and before the PR opens.** CI tests the merge result, and two revisions numbered `0015` is an alembic multiple-heads error that surfaces as a mystery failure in a job that has nothing to do with either feature. F33 builds and commits in parallel until then; this is a scheduling constraint on the PR, not on the branch.

1. **Rebase on `main`.** Expect conflicts in `apps/manage/src/App.tsx` and both manage i18n bundles (F57 rewrote them); F33's diff there is append-shaped by design.
2. **Re-resolve the revision id from the tree, not from this document**: `cd Backend && ./.venv/bin/python -m alembic heads`. If it prints `0015 (head)`, rename `0015_queue_tickets.py` → `0016_queue_tickets.py` and change **three literals**: the filename, `revision`, `down_revision`. If it prints something else, take that number. If F19's single-head guard has landed, it will fail loudly in `make test` instead of on CI — inherit it and trust it.
3. **Run the whole local gate** (below) with the renumbered migration, including `run-db-tests.sh`, which recreates `f33_test` from scratch and therefore actually exercises the new revision chain.
4. **Revert `backend/tests/conftest.py` and verify it is clean**, then `git show --stat` every commit on the branch and confirm `tests/conftest.py` appears in none of them.

Carry into the run report:

- **C4 + C5 — the deployment-ordering constraint.** F33 must not be enabled for a live pilot tenant until **F58's panel can show and close a ticket** (a present phone is a silent, free, unbounded oracle; an absent one creates a row no shipped surface renders; and a single anonymous POST denies a named number a position for the rest of the boutique day, with no remedy in F33). This is the same shape as Risk 3's F20 constraint and, like it, is a deployment constraint rather than a merge constraint.
- **Risk 3 — F20's retention job.** F33 must not be enabled for a live pilot tenant before the sweep exists, and **C10**: the retention sentence now carries an exception for the opted-in contact detail, which F20 promotes into `customers` where nothing deletes it.
- **Risk 2 — the two counsel-gated strings**, `checkin.notice` and `checkin.optIn`, still open in `in_run_gates`, re-nagged. The interim values are labelled interim in the spec and in the report.
- **C9** — same-phone QR re-scan does **not** recover a position; only a same-tab return does. If the pilot says that is not good enough, restoring it needs a store that survives a new browsing context, which is a user-level decision, not a build fix.
- **C16** — `axe-core` was added to `apps/storefront` as the spec requires; the e2e already runs stronger real-browser axe over the same states, and dropping the two jsdom rows is a defensible retreat if the lockfile churn hurts at rebase.
- **The mutation checks that were run** (Task 6's index/lock, Task 10's unmount guard and pause), what went red, and — for the advisory lock specifically — whether removing it changed anything, since D4 predicts it might not.

No push, no PR — the orchestrator owns review and shipping.

---

## Task-by-task file manifest

| Task | Files |
|---|---|
| 0 | `.planning/plans/qr-walkin-queue.md`, `.planning/specs/qr-walkin-queue.md` |
| 1 | `backend/migrations/versions/0015_queue_tickets.py`✚, `backend/app/models/queue_ticket.py`✚, `backend/tests/test_migrations.py` |
| 2 | `backend/app/db/repositories/queue_tickets.py`✚, `backend/tests/test_queue_repositories.py`✚ |
| 3 | `backend/app/queue/{__init__,validation,schemas,service}.py`✚, `backend/app/core/config.py`, `backend/tests/test_checkin_service.py`✚ |
| 4 | `backend/app/queue/service.py`, `backend/tests/test_checkin_service.py` |
| 5 | `backend/app/queue/router.py`✚, `backend/app/main.py`, `backend/tests/test_checkin_api.py`✚, `backend/tests/test_storefront_api.py` |
| 6 | `backend/tests/test_queue_db.py`✚, `backend/tests/test_queue_isolation.py`✚ |
| 7 | `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/queue/manage_router.py`✚, `backend/app/queue/{schemas,service}.py`, `backend/app/main.py`, `backend/tests/test_checkin_qr_api.py`✚, `backend/tests/test_checkin_qr_link.py`✚ |
| 8 | `frontend/apps/storefront/src/router.tsx`, `…/api.ts`, `…/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/router.test.tsx`, `…/__tests__/api.test.ts`, `frontend/apps/storefront/package.json`, `frontend/pnpm-lock.yaml`, `backend/tests/test_spa_serving.py` |
| 9 | `frontend/apps/storefront/src/lib/checkinTicket.ts`✚, `…/routes/CheckinPage.tsx`✚, `…/__tests__/CheckinPage.test.tsx`✚ |
| 10 | `frontend/apps/storefront/src/routes/QueuePositionPage.tsx`✚, `…/__tests__/QueuePositionPage.test.tsx`✚ |
| 11 | `frontend/apps/manage/vite.config.ts`, `…/src/App.tsx`, `…/src/api.ts`, `…/src/components/CheckinQrSection.tsx`✚, `…/src/i18n/{he,ar}.ts`, `…/src/__tests__/CheckinQrSection.test.tsx`✚, `…/src/__tests__/Nav.test.tsx`, `…/src/__tests__/i18n.test.ts` |
| 12 | `frontend/e2e/storefront.spec.ts` |
| 13 | migration rename + three literals; `backend/tests/test_migrations.py` revision literals |

✚ = new file. **`backend/tests/conftest.py` appears in NO task and in NO commit.**

Files the spec explicitly leaves **unedited**, and each absence is a decision: `backend/app/models/customer.py` (Ruling 2) · `backend/app/db/repositories/customers.py` (Ruling 2) · `backend/tests/test_staff_role_gating.py` (live-route-table walker; the QR route must **not** join `OWNER_ONLY`) · `backend/tests/test_frontend_constant_parity.py` (no new mirrored constant) · `frontend/apps/storefront/src/validation.ts` (helpers imported as they are) · `frontend/scripts/qa-greps.sh`.

---

## The local gate sequence

```
make lint      # cd backend && ruff check . && ruff format --check . && mypy app tests
               #   + cd frontend && pnpm -r lint && pnpm -r typecheck
               #   + bash frontend/scripts/qa-greps.sh
make test      # cd backend && uv run pytest -m "not db" -q
bash "…/scratchpad/run-db-tests.sh"    # the db-marked suite against local PG 16.14
make fe-test   # cd frontend && pnpm -r --if-present test
make fe-build  # cd frontend && pnpm -r build
make e2e       # build both apps + playwright chromium + the specs
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` / `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0 printing exactly the pre-existing baseline**. ⚠ Capture that baseline **before Task 9** and diff after: F33 writes comment-heavy storefront code and three of the eight checks grep prose (**C3**).
- **`make test`** — all fast tests pass; `test_checkin_api.py`, `test_checkin_service.py`, `test_checkin_qr_api.py` and `test_checkin_qr_link.py` green; the `db`-marked modules collected and deselected. `test_staff_role_gating.py` and `test_frontend_constant_parity.py` pass **unedited**. ⚠ Two `test_config.py` failures are **always false locally** — `backend/.env` leaks `MEDIA_BUCKET` (`.memory/local-env-breaks-config-tests.md`). CI is green. Do not chase them.
- **`run-db-tests.sh`** — baseline 353 + F33's new db-marked tests, all green. The 9 `test_media_upload_s3.py` errors are excluded by the runner and need MinIO.
- **`make fe-test`** — `CheckinPage.test.tsx` and `QueuePositionPage.test.tsx` green with every named assertion present and axe at **zero** violations; `router.test.tsx`, `Nav.test.tsx`, `i18n.test.ts` green.
- **`make fe-build`** — all packages build; no unused-import or unused-variable TS error (`tsc --noEmit` runs as part of storefront's `build`).
- **`make e2e`** — both new journeys green, every existing spec green.

⚠ **A first CI run failing on a test bug is budgeted** (`.memory/boutique-ci-first-run-surprises.md`) — but far less likely here than for F34, because the db-marked suite actually executes locally. Before believing a red, check `continue-on-error` on the job.

---

## What a local run still cannot prove

Almost nothing, which is new for this program. The db harness closes the gap F34 had to live with.

| Task | CI-only | What the local run gives |
|---|---|---|
| 1 | the definitions **as CI's server deparses them** — a different 16.x point release could normalise differently, which is exactly why they are **captured, not transcribed** | the full round trip, the four-axis CHECK probe, the RLS/GRANT assertions |
| 6 | nothing structural | both forced interleaves, the Jerusalem-day pair, the DST case and RLS isolation all run locally |
| 12 | e2e runs locally too (`make e2e` installs chromium) | — |
| — | the alembic revision chain **as merged with F57** | the chain as it stands on this branch |

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| One migration, one `CREATE TABLE`, up and down | `test_migrations.py` (db) |
| The three CHECKs and the partial unique index, **byte-identical from captured definitions** | `test_migrations.py` (db) — the test still earning its keep when F58 wants a fifth status |
| `customers` has no `marketing_opt_in_at` (Ruling 2) | `test_migrations.py` (db) |
| `app/queue/` imports nothing from `customers`; `QueueService.__init__` takes no customers repo (**C2**) | `test_checkin_service.py` (fast, source guard) |
| A full check-in leaves `count(*) FROM customers` unchanged, opt-in ON and OFF (**C2**) | `test_queue_db.py` (db) |
| No table without forced RLS | `test_every_tenant_id_table_has_forced_rls` (db, **unedited**) |
| Position = count+1, `null` when not waiting, scoped to the **ticket's own** `queue_day` (**C11**) | `test_queue_repositories.py` (db) |
| Dedup is the index, not the pre-check; a lost race is an `IntegrityError` | `test_queue_db.py` (db, **forced interleave, mutation-checked**) |
| A `done` ticket frees the key; a soft-deleted one does; another tenant's identical phone does | `test_queue_db.py` (db) |
| The Jerusalem day boundary and the 2026-03-27 spring-forward | `test_queue_db.py` (db, injected clock) |
| The lock key is namespaced (**C15**) | `test_checkin_service.py` (fast, one source assertion) |
| Four budgets; a spent **per-phone create** answers `{"ticket": null}` not 429 (**C6**) | `test_checkin_service.py` (fast) |
| The tenant read brake is charged on **misses only** (**C7**), both directions | `test_checkin_service.py` (fast) |
| Both routes anonymous, `no-store`, GET-405, cookie-blind byte-for-byte | `test_checkin_api.py` (fast) |
| A duplicate answers 201 `{"ticket": null}` with `id`/`position`/`called_at` **absent**, byte-identical on both convergence paths | `test_checkin_api.py` (fast) |
| `SPEC_ERROR_CODES` unchanged and set-equal; no new error code | `test_checkin_api.py` (fast) |
| The two new `/storefront` paths are registered once | `test_storefront_api.py` (fast, the literal F33 is meant to break) |
| The QR route: both roles, host-derived slug, `<svg` **and** `xmlns` | `test_checkin_qr_api.py` (fast) |
| `checkin_link()` as a pure function | `test_checkin_qr_link.py` (fast) |
| The QR route is default-deny-checked and not `OWNER_ONLY` | `test_staff_role_gating.py` (fast, **unedited**) |
| `MANAGE_API` names every `/manage` segment | `test_spa_serving.py` (fast) |
| Both new storefront URLs serve the shell (**C14**) | `test_spa_serving.py` `SHELL_PATHS` (fast) |
| `/q/…` is matched before the catalog fallthrough; the ticket id never reaches `document.title` | `router.test.tsx` |
| Zero server round-trip on `/checkin` mount, both with and without a pointer | `CheckinPage.test.tsx` |
| The notice and the opt-in label render, are not hidden, **and contain the boutique name**; loading and error arms (**C13**) | `CheckinPage.test.tsx` |
| Forward-press-only validation; one request on a double-tap; failure-path focus | `CheckinPage.test.tsx` |
| **SC 2.2.2** — pause stops, resume fetches immediately, one button, name flips, `min-h-11`, text label | `QueuePositionPage.test.tsx` — **the only automated coverage; axe has no rule** |
| The unmount guard | `QueuePositionPage.test.tsx` (**mutation-checked**) |
| Three terminals including the 200-with-`done`; 429 is not terminal | `QueuePositionPage.test.tsx` |
| The announced region is silent on a tick; the called transition is announced once | `QueuePositionPage.test.tsx` (`MutationObserver`) |
| The freshness line is outside every announced region, **with a negative control** | `QueuePositionPage.test.tsx` |
| Terminals clear the recovery pointer | `QueuePositionPage.test.tsx` |
| Neither page sets `document.title` or moves focus on mount (**C15**, sentinel form) | both page tests |
| The journey, and the oracle closed end to end | `e2e/storefront.spec.ts` |

---

## Shipping checklist

Run top to bottom. Every line is something that has actually gone wrong in this repo or was proven to be a live hazard this session.

- [ ] **`git diff --quiet -- backend/tests/conftest.py`** — the local PG harness patch is reverted.
- [ ] **`git log --stat` over the branch** — `tests/conftest.py` appears in no commit.
- [ ] **`git ls-files` sanity** — every new file is tracked. Pathspecs were lowercase (`backend/`, `frontend/`); `git show --stat` confirms each commit contains what it claims.
- [ ] **F57's `0015` is on `main`.** If not, **stop** — do not open the PR.
- [ ] **`alembic heads` re-read after rebase**; the migration filename, `revision` and `down_revision` all match it; `test_migrations.py`'s revision literals match.
- [ ] `make lint` — clean, and `qa-greps.sh` output is **byte-identical to the baseline captured before Task 9**.
- [ ] `make test` — green but for the two known `test_config.py` `.env` false failures.
- [ ] `run-db-tests.sh` — green on a freshly recreated `f33_test`.
- [ ] **Mutation checks performed and restored**: the unique index (Task 6), the advisory lock (Task 6, result recorded either way), the unmount guard (Task 10), the pause control (Task 10).
- [ ] `make fe-test`, `make fe-build`, `make e2e` — green.
- [ ] `uv.lock` and `pnpm-lock.yaml` are both committed beside their manifest edits.
- [ ] The two counsel-gated strings are the interim values **verbatim**, in `he.ts` and `ar.ts`, hardcoded in no component; `in_run_gates` F33 stays **open**.
- [ ] The run report carries: C4+C5's F58 deployment-ordering constraint, Risk 3's F20 constraint, the gated strings, C9's re-scan loss, C16's axe note, and the mutation-check results.
- [ ] Commits are conventional and scoped, one logical change each — no mega-commit.

---

## What could go wrong in review

Every item is a **recorded ruling**, not an open question. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"A stranger can still learn whether a phone is in this boutique's queue, for free, forever."** True, and **C4** states it as the residual rather than arguing it away. The only fix that closes the oracle is the OTP the user already priced and rejected. The mitigation shipped is a **deployment-ordering constraint**: no live pilot tenant until F58 can show and close a ticket.
2. **"One POST denies a named person a position all day and nothing in F33 can undo it."** True, **C5**, same ordering constraint. The remedy is a staff remove, which is F58's.
3. **"The spec says a spent per-phone budget answers 429; the code answers 201."** **C6**, a deliberate amendment: `notifications/service.py:199-206` refuses that exact disclosure for that exact key, in writing, and F33 collapsing the distinction would have been a second presence channel that costs no row.
4. **"The per-tenant read brake is not charged on hits — that weakens the runaway brake."** **C7**, deliberate: keyed on the caller's own body, the per-ticket budget cannot bound a hostile client at all, and charging the shared ceiling on hits is what lets one id-walker 429 every real bride. Misses are still charged, so a token walk is still not free.
5. **"There is no `usePoll` — the loop is duplicated."** D9, argued at length: two callers in two apps behind two `ApiError` classes, two terminal predicates, two mutation stories and two i18n bundles. The only shared home reachable from the storefront is `packages/ui`, whose review surface is the design system. Risk 5 records the cost.
6. **"`sessionStorage` doesn't survive a QR re-scan, so the recovery mechanism doesn't work."** **C9**: correct, and the spec now says so. Its real reach is same-tab return, reload and screen lock. Cross-device and re-scan recovery are declined outright, not deferred.
7. **"The key is `window.location.hostname`, not the slug the spec names."** **C12** — the storefront has no slug anywhere; `BoutiqueResponse.name` is the display name and is owner-mutable.
8. **"`test_no_route_is_registered_twice_across_routers` was edited."** Deliberate and visible: `test_storefront_api.py:569-571` says adding a public surface must fail one test on purpose, and the literal stays a literal.
9. **"Why is the position read a POST?"** D7, overruling the brief's GET on the codebase's own written rule (`booking/router.py:119-126`, restated at `test_storefront_api.py:592-595`). The residual — the id is in the SPA URL once per page load — is stated; the POST turns 360 log lines per visit into 1.
10. **"`skip_count` has neither reader nor writer."** D2, deliberate: `LOOP-STATE.md:241-243` promises F58 needs no migration, and one `INTEGER NOT NULL DEFAULT 0` now is cheaper than a migration in the feature scoped not to have one. Same for `requeued_at`, which F33 **does** read through D3's ordering.
11. **"The Jerusalem-day expression index would have been simpler than a stored column."** It works — probed on live 16.14, `provolatile='i'`, correct across DST and in both UTC/Jerusalem directions — and D4 declines it anyway on three grounds, the load-bearing one being that it makes the dedup key the **database** clock, which is untestable against the injectable `Clock` every service and every db test uses. The Jerusalem-boundary test in Task 6 is that argument made mechanical: it cannot be written at all against an expression index.
12. **"`axe-core` was added to the storefront for two jsdom passes the e2e already covers better."** **C16**, recorded with the cheaper alternative, shipped as the spec requires.
13. **"The advisory lock buys nothing now that the `customers` write is gone."** D4 agrees in writing — post-Ruling-2 it buys determinism, not correctness — and keeps it because it costs microseconds and is the house shape. Task 6's mutation check records what actually changed when it was removed.
14. **"The 2.2.2 pause test is redundant with the axe pass."** It is not, and the test file must say so: **axe has no SC 2.2.2 rule.** Those assertions are the only automated coverage of a Level A criterion that pre-decided #38 makes a legal requirement.

---

## What the builder still has to invent (no design deck exists)

F33 self-approved the design gate under Q2, so there is no `design.md`, no `copy.md` and no prototype. The following are **not** in the spec and the builder decides them, then records them in the run report:

- **Every non-gated `checkin.*` Hebrew string** — the phone hint, the pause/resume pair and their Aria variants, the three freshness sentences (the spec gives their shape and register but not final values), the already-in-queue copy, the recovery-link label (**C8** constrains its meaning: *the last check-in made from this device*), the not-found and closed states, the position sentence, the "go to the counter" sentence, both document titles, and the whole `checkinQr.*` block. Register is set by `apps/manage/src/i18n/he.ts:458-530` and the storefront's existing copy: past tense on freshness, no exclamation marks, no role names.
- **The `visit_type` chooser's markup.** The spec says "the storefront-local radio-composite pattern `SizeChips`/`TypePicker` established" but does not name the element shape. A `fieldset`/`legend` with two native radios is the smallest thing that is correct for a two-value required choice; `SizeChips` is the styling precedent.
- **Where the already-in-queue state renders on `/checkin`** — inline above the form, or replacing it. The spec fixes only that there is **no navigation** and **no position**.
- **The position screen's arrangement** — the large number's typography, what the closed and called states show beyond their sentence, whether `/q/…` renders a boutique-loading arm (C13 specifies the arms for `/checkin` only).
- **The QR section's "print affordance"** — `window.print()`, a print stylesheet, or a download link. Unspecified.
