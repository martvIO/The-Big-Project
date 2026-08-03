# Spec: F53 — Customers CRM (SMC-4)

**Created**: 2026-08-03 · **Status**: **Gate 1: standing approval — `interview-2026-07-30.md` §Standing approvals** (Q1's stop-list is F17, F18, F19, F20, F29 and F48; F53 is on none of them — it touches no money, no billing and no privacy-law text). **The design gate self-approves under Q2**: the screen is `SectionHeading` / `Card` / `Input` / `TextArea` / `Button` / `Badge` / `Skeleton` / `EmptyState`, every one shipped and exported from `packages/ui/src/index.ts`, and Q2 names exactly two novel patterns — F34's shift board and F42's capacity matrix. F53 is neither. Designer and `design-critic` must still both accept. · **Epic**: SMC (`.planning/epics/shift-manager-console.md`), phase SMC-4 · **Effort**: **M** (3 endpoints, one two-column migration, one new backend package, three repository appends, two console components — F51's M was four endpoints and F52's was one plus a new package)
**Depends on**: #31 (`require_role`, the `RoleGate`, the generic 403 body, the default-deny route walker) and #51 (the role-filtered `NAV` table this feature inserts a row into) · **Feeds**: nothing queued. F53 is the last unbuilt SMC entry.

---

## Corrections to the plan

The approved plan (`~/.claude/plans/two-sessions-are-building-spicy-lynx.md`) is authoritative on every decision it took, and this spec transcribes those decisions unchanged. Eight of its supporting *facts* did not survive re-verification against the worktree. Where research and plan disagree, **this spec follows the research** and the plan's version is recorded here so a reader who has both open knows which one to believe.

| # | The plan says | The code says | What changes |
|---|---|---|---|
| C1 | Import the control-char regex from `booking/validation.py:70` for tags | **Line 70 is `_CONTROL_CHARS_EXCEPT_WS`, which permits `\t \n \r`.** Line **69** is `_CONTROL_CHARS`, the whole C0 set. `booking/validation.py:62-68` states the split: a one-line value bars newlines because F16 templates it into an SMS; `notes` is a paragraph and keeps them | Tags import **line 69**; notes imports **line 70**. Importing 70 for tags lets a newline into a `TEXT[]` element (D5) |
| C2 | `test_customers_api.py` asserts **422** on `limit=0` / `limit=201` / `offset=-1` | **There are no 422s in this app.** `main.py:738-745` normalizes `RequestValidationError` to a **400 `VALIDATION_ERROR`**, with the comment *"House shape + 400 platform-wide — no default 422s anywhere"* | Those rows assert **400** and the two-key envelope `{"error": {"code": "VALIDATION_ERROR", "message": …}}` (D9) |
| C3 | `0008_bookings.py:47-50` is where `customers` got its GRANT and RLS | :46-50 is the unique index plus the `updated_at` trigger. The grant/RLS loop is **`0008_bookings.py:107-110`** | The migration comment cites **:107-110** for the grant, **:50** for the trigger (D1) |
| C4 | `command.downgrade(cfg, "0013")` in F57's `test_migrations.py` block is "the exact rot `test_migrations.py:465`'s comment warns against" | :465-468 governs the **assertion target** (`head`), not the downgrade argument. **All four shipped round-trips hardcode their downgrade target** — 0011→`"0010"` (:215), 0012→`"0011"` (:341), 0013→`"0012"` (:372), 0014→`"0013"` (:494) | F53 still uses `command.downgrade(cfg, "-1")`, but as a **deliberate departure with a stated reason** (order-independence under a three-way migration race), not as a correction of F57. A reviewer who checks the four precedents would otherwise reject the framing (D12) |
| C5 | `_no_store` is "the fifth" local copy | Seven copies exist repo-wide; **four are on `/manage`**, so F53's is the fifth on `/manage` and the **eighth overall**. `dashboard/router.py:39`'s own "a fourth local three-line copy" is already stale prose | F53's docstring carries **no ordinal at all** and cites `auth/staff_router.py:22-27`, the decision of record (D6) |
| C6 | The tags regex is "already the shared class, mirrored to the frontend by `test_frontend_constant_parity.py`" | The mirror exists, but `test_control_character_classes_match_the_backend` scrapes **`frontend/apps/storefront/src/validation.ts` only**. The manage console mirrors no regex today | F53 declares both classes in `apps/manage/src/validation.ts` and parametrizes that test over both files (D5, Frontend Changes) |
| C7 | The migration is "0016 at the earliest, 0017 if F33 lands first" | `alembic heads` on this branch prints **`0014 (head)`**; F57 holds 0015 uncommitted-to-main, F33 will take 0016 and F19 renumbers to 0017 | **Today's expectation is 0018**, and the rule is unchanged: never hardcode — re-read `alembic heads` on the rebased branch (D1, Collision map) |
| C8 | Repository work appends to `customers.py` and `message_log.py` — "no new repository files" | True, but **incomplete**: the booking-history panel has no reader. `BookingsRepository` has 20 methods and the closest, `list_live_for_customer` (`bookings.py:601-619`), pins `status = 'confirmed'` and `starts_at > after` — it is F15's re-mint feed, not a history | A **third** repository append, `BookingsRepository.list_recent_for_customer`, in `bookings.py`. Still no new repository file (D4) |

One further thing the plan does not mention and the Collision map does: **`vite.config.ts` carries two conflicting hunks, not one.** Line 19 is the alternation; lines 13-17 are prose reading *"The eleven names"* and *"a twelfth router added without touching this file"*, and F57 must bump the same two words for `floor`.

---

## Problem

The console has ten sections and not one of them is about a **person**. `BookingsSection` lists one Jerusalem day and renders `customer_name` as a label on a row (`BookingsSection.tsx:163`); `BookingDetail` renders one booking's phone and its own `notes`. There is no way to answer "who is מיכל לוי, when has she been here before, and what did we agree last time" without knowing the date of every visit and opening each one.

The data has been there since F13 and nothing reads it that way. `CustomersRepository` has five methods — `by_phone`, `by_id`, `by_ids`, `set_phone`, `upsert` (`db/repositories/customers.py:14,24,34,49,77`) — and every one takes an id or an exact phone. **Nothing searches.** `customers` carries exactly three domain columns: `tenant_id`, `phone`, `name` (`models/customer.py:17-19`). There is nowhere to write down that a bride is coming with her mother, or that she is a rental, or that she cancelled twice.

The third half is the SMS log, and it is the one with teeth. `message_log` is the **Spam-Law evidence trail** — the model docstring says so (`models/message_log.py:11-13`) — and its only shipped read is `list_by_phone` (`db/repositories/message_log.py:55-67`), which matches a phone string, sorts ascending and has no limit. Nothing in the product renders it. When a bride says "I never got a confirmation", nobody in the boutique can check, and when the regulator asks, the evidence is only reachable through `psql`.

And `list_by_phone` is not the read F53 wants, for a reason that is the sharpest thing in this document: **phone numbers are corrected and phone numbers are recycled**, and a per-customer view keyed on the phone string alone would render one customer's message bodies — carrying her name and her appointment time — on a different customer's screen (D3).

## Goal

`apps/manage` gains an eleventh section, **visible to both roles**, that answers four questions about one person:

- who is she, and which of my customers match what I typed
- when has she been here, and what happened at each visit
- what do we know about her that no column holds — free text, and a handful of tags
- what did this boutique actually send to her, and did it arrive

and one it refuses: **it cannot un-send, re-send, edit or delete a message.** The SMS log is read-only, in the API and in the UI, because a mutable evidence trail is not evidence.

Two columns land on `customers` (`notes`, `tags`) and **nothing else changes shape**. No new table, no new index, no new error code, no new exception handler.

---

## What already exists to build on (verified against code)

- **The list→detail in-panel swap is a shipped pattern with a recorded ruling.** `BookingsSection.tsx:53-82` early-returns `<BookingDetail …/>` before the list JSX, and its comment names the ruling: *"An in-panel state swap, the CatalogSection -> DressEditor shape: apps/manage has no router and F15 does not introduce one for one view."* F53 introduces none either.
- **`CustomersRepository`'s invariants are uniform and F53's appends copy them exactly.** Signature order is always `(self, session, tenant_id, <positional id>, *, <kwargs>)`; every `select` carries all three predicates (`tenant_id ==`, the narrowing one, `deleted_at.is_(None)`); reads end `scalar_one_or_none()` or `list(... .scalars())`; `by_ids:40-41` short-circuits empty input because *"`IN ()` is a syntax error in Postgres"*; `set_phone:63-75` is the UPDATE shape — `.returning(Customer.id)`, `None` for "no live row", then a re-read through `by_id`. **No repository method ever opens its own transaction**, and `updated_at` is never assigned (the `trg_customers_updated_at` trigger owns it, `0008_bookings.py:50`).
- **`message_log` already stores OTP bodies masked.** `mask_otp_body(body, code)` replaces the digits with `MASK_CHAR * OTP_CODE_LENGTH` and its docstring states the ruling: *"The log lives forever, the code is worthless in five minutes, and the Spam-Law evidence value is 'an OTP was sent to this phone at this time' — never the digits"* (`notifications/validation.py:61-65`). That is what makes D3's decision to include OTP rows free rather than a disclosure.
- **`message_log.error` is already fenced by a comment.** *"Provider failure detail for operators; **never reaches a response body**"* (`models/message_log.py:23-24`). `SmsLogRow` excluding it is the shipped ruling, not a new one.
- **The `/manage` router template, six shipped copies.** `APIRouter(prefix="/manage", dependencies=[Depends(_no_store), Depends(require_role(...))])`, a local three-line `_no_store`, no `response_model=` anywhere (the return annotation *is* the model), and a docstring recording the include-order shadowing hazard and naming its own `ROUTES` table as the guard. `dashboard/router.py:38-39`, `auth/staff_router.py:27-30` and `booking/owner_router.py:16-18` each state in identical words that **real HTTP verbs and path parameters are the shipped convention and the `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate for another codebase.**
- **Seven routers are mounted under `/manage` today, and `main.py`'s own ordinal chain counts all seven.** Six declare the exact string `prefix="/manage"` — `boutique/router.py:32`, `catalog/router.py:58`, `booking/owner_router.py:79`, `auth/staff_router.py:62`, `dashboard/router.py:65`, `payments/router.py:29` — and the seventh is `auth/router.py:13`, `APIRouter(prefix="/manage/auth")`. A string match on `prefix="/manage"` misses it; `main.py`'s registration comments do not, and they are the convention F53 has to be consistent with: `owner_booking_router` is *"The fourth /manage router"* (`:1024`), `staff_router` *"The fifth"* (`:1029`), `dashboard_router` *"The sixth"* (`:1034`), `gateway_router` *"The SEVENTH"* (`:1039`) — a chain that only closes if `auth_router` (`:1018`) is number one. **F53 is therefore the EIGHTH on `origin/main` and the NINTH after F57 merges**, which is what the Collision map and the Rebase drill say. The include goes after `gateway_router` (`main.py:1043`) and before `storefront_router` (`:1046`), with `_register_spas(app)` staying last (`:1055-1057`).
- **Services raise, repositories return `None`, routers do neither.** `StaffNotFoundError(DomainNotFoundError)` (`auth/staff.py:87-91`) is raised as a bare class — no parentheses, no message — and *"Subclasses the app/errors.py base, so it needs no handler of its own."* `OwnerBookingService.detail` (`booking/owner.py:191-199`) is the read-path form, with the `raise` **outside** the `async with`. There is no `if x is None: raise HTTPException` anywhere in this codebase.
- **The error envelope is two keys.** `{"error": {"code", "message"}}` — no `status`, no `details` array (`main.py:145-148, 728-759`). `DomainValidationError` → 400 `VALIDATION_ERROR` carrying **the exception's own message**; `DomainNotFoundError` → 404 `NOT_FOUND` with a fixed body; the generic 403 is one body for every unadmitted role, *"naming the required role would tell a probe which roles exist"* (`main.py:143-144`).
- **Pure validation modules are a shipped shape.** `boutique/validation.py:1-6` — *"Pure domain validation for owner settings — no I/O, unit-tested locally … write-time gates … so bad input fails with a clean 400 instead of an IntegrityError."* Module-local error subclass, `MAX_*` SCREAMING_SNAKE constants with a why-comment, `validate_<thing>(...) -> None` raising on first failure, and messages that are lowercase, snake_case-field-first, no trailing period: `"maps_url is too long"`, `"name must not be blank"`. `MAX_PROFILE_DESCRIPTION_LENGTH = 2000` (`:30`) is the peer D5 borrows.
- **`boutique/validation.py:110` is the ruling `""` / `[]` = clear rides on**: *"Empty string = cleared field; format checks apply only to non-empty values."*
- **The query-bounds line, verbatim.** `offset: Annotated[int, Query(ge=0, le=MAX_LIST_OFFSET)] = 0`, `limit: Annotated[int, Query(ge=1, le=BOOKING_LIST_MAX_LIMIT)] = BOOKING_LIST_DEFAULT_LIMIT` (`booking/owner_router.py:168-169`), with `MAX_LIST_OFFSET = 1_000_000` **restated** at `booking/owner.py:52-58` rather than imported — restatement is the house call, and the reason recorded there is that an unbounded caller-supplied offset reaches asyncpg's `int8_encode` and answers 500.
- **`bookings.list_day` is the in-repo precedent for an all-status read**, and its docstring is the argument F53's history reuses: *"**Every status, cancelled included.** This deliberately does NOT inherit `count_by_start`'s `status <> 'cancelled'` predicate: that method mirrors the occupancy indexes, while a cancelled row here is the owner's evidence that the slot re-opened"* (`db/repositories/bookings.py:578-581`).
- **`idx_bookings_tenant_customer ON bookings (tenant_id, customer_id) WHERE deleted_at IS NULL`** already exists (`0008_bookings.py:101-104`) and carries both F53's booking-history read and the `IN (…)` subquery in D3's SMS join.
- **`AuditAction` is a `StrEnum` over plain-TEXT `audit_log.action` with no CHECK** (`models/constants.py:105`, ruling at `:109-112`), so a new member needs no migration. The split criterion this repo actually applies is recorded twice: *"those are the two questions a security audit actually asks of this table … and each stays one `WHERE action = …`"* (`:129-134`).
- **`AuditLogRepository.record`** takes five keyword-only arguments after `session` — `tenant_id`, `action`, `actor_id`, `entity`, `details` — returns `None`, and every shipped caller passes `entity=str(<uuid>)` (`auth/staff.py:150,241,250,271,307`).
- **`tenant_session(factory, tenant_id)`** opens `session_factory() … session.begin()` and binds the transaction-local RLS context in one `SELECT set_config(…, true)` (`db/tenant.py:16-30`). One `async with` is one transaction, committed on clean exit; there is no explicit `commit()` anywhere in the product.
- **`test_staff_role_gating.py` needs no edit.** Both walkers derive from the **live** route table. Walker 1 sees a router-level gate as `gated=True`; walker 2 takes the `elif` branch and `all(SHIFT_MANAGER in roles)` holds. `dashboard/router.py:15-16` already states the corollary in prose: *"It must NOT be added to that module's OWNER_ONLY set: a both-roles route there reports as `unenforced_owner_only`."*
- **`test_every_tenant_id_table_has_forced_rls`** keys on the presence of a `tenant_id` **column**, not a table list (`test_tenant_isolation.py:203-230`), so adding two columns to an already-forced table cannot move it. Its staying green **unedited** is the assertion that F53 snuck no table in — the same sentence `0014_booking_check_in.py` uses.
- **`test_spa_serving.py:372-400` derives the vite proxy alternation from the live FastAPI route table** and asserts set equality against `re.search(r'"\^/manage/\(([a-z|-]+)\)"', source)`. A `/manage/customers` router with no `customers` in that alternation **fails a Python test**, not just a dev machine.
- **`api.ts` speaks the backend's snake_case verbatim** — *"There is no case-conversion layer in this repo … a camelCase interface compiles fine and reads `undefined` at runtime on every field"* (`api.ts:1-5, 417-419`). Methods are object-literal shorthand on `export const api = {…}`, one line, returning `apiFetch`, never `async`.
- **`lib/booking.tsx` exists precisely because a list and its detail must not import helpers from each other** (`:1-5`): *"BookingsSection imports BookingDetail and BookingDetail imports RescheduleDialog — hanging shared helpers off either end would close that chain into a cycle."* F53's pair has the same shape. `statusBadge` (`:22`) and `isolateLtr` (`:32`) are reused verbatim; `he.ts:456-457` records why — *"a second spelling of «בוטל» in one console is a defect."*
- **The copy guard.** `i18n.test.ts:247` rejects any `HE` value matching `/נשלח|תישלח|בדרך/`, and its own comment (`:233-238`) says *"a copy deck that has to dodge its own guard is copy that is one edit away from lying."* D11 is F53's answer.

---

## Design

### The migration: two columns on `customers`, and it is the LAST commit on the branch (D1)

```sql
ALTER TABLE customers ADD COLUMN notes TEXT;
ALTER TABLE customers ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}';
```

**`tags` is `NOT NULL DEFAULT '{}'`, and that is not a style preference.** "This customer has no tags" and "this customer's tag list is empty" are one fact. A nullable array gives that one fact two representations, and every predicate over it then becomes silently three-valued: `array_length(NULL, 1)` is `NULL`, not `0`; `'vip' = ANY(NULL)` is `NULL`, not `false`; `NULL || '{x}'` is `NULL`, not `{x}`. None of those raise. They return wrong answers quietly, which is the failure mode a spec exists to prevent. On the Python side the difference is `Mapped[list[str]]` versus `Mapped[list[str] | None]` and a `?? []` at every read site forever.

**The rewrite objection is false on PostgreSQL 11+.** A non-volatile column default on `ADD COLUMN` is stored in `pg_attribute.atthasmissing` / `attmissingval` and materialized lazily on read; the `ALTER` is catalog-only and takes an `ACCESS EXCLUSIVE` lock for the duration of a catalog write, not a table rewrite. `'{}'::text[]` is non-volatile. There is no table scan.

**`notes` is plain `TEXT NULL`.** The array argument does not transfer: a string has no "empty vs absent" ambiguity that hurts — `''` and `NULL` are distinguishable and both mean "nothing written" to every consumer — and `NULL` matches the sibling free-text column exactly, `bookings.notes: Mapped[str | None] = mapped_column(Text, nullable=True)` (`models/booking.py:54`). Two spellings of "a free-text note on a row" in one schema would be the defect.

**`tags TEXT[]` is the first array column in this codebase.** `grep -rn "ARRAY" Backend/app/models/` returns zero hits, and `TEXT[]` appears in no migration. The only Postgres-dialect type in use is `JSONB`. So the ORM line is new ground and is spelled out here rather than left to be guessed:

```python
tags: Mapped[list[str]] = mapped_column(
    ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
)
```

with `from sqlalchemy.dialects.postgresql import ARRAY`. `warn_unused_ignores = true` in `pyproject.toml`, so a speculative `# type: ignore` on that line is itself a mypy error.

Declined: **a `JSONB` column for tags.** It is the shape already in this repo (`tenant.settings`, `audit_log.details`), which is the only argument for it, and it is the wrong one: JSONB gives no element type, so `["vip", 3, null]` is storable; the containment operators need a GIN index to be usable; and the future tenant-tag query is `unnest(tags)`, which `TEXT[]` answers natively. The epic already ruled the type — *"CRM with notes + tags (`TEXT[]` on customers)"* (`epics/shift-manager-console.md:32`).

**Deliberately absent — the complete list, in `0014_booking_check_in.py`'s style**, so a reviewer can check it is complete rather than merely short:

- **No GRANT.** `0008_bookings.py:107-110` issued table-level `GRANT SELECT, INSERT, UPDATE, DELETE ON customers TO app_user`. Table grants are column-agnostic; no column-level grant was ever issued on this table. (The `ALTER DEFAULT PRIVILEGES` gotcha in `.claude/CLAUDE.md` is about newly **created** tables, not added columns.)
- **No `enable_tenant_rls`.** RLS is a table property, forced on `customers` since `0008_bookings.py:109-110`. `test_every_tenant_id_table_has_forced_rls` staying green **unedited** is the assertion that no table snuck in here.
- **No `_updated_at_trigger`.** `trg_customers_updated_at` exists from `0008_bookings.py:50`.
- **No index, no CHECK, no backfill.** `NOT NULL DEFAULT '{}'` is the backfill. The search index is declined on its own merits in D2; a tag index is declined in D5.

**Revision number: never hardcoded, and this is the last commit on the branch.** `alembic heads` on this worktree prints `0014 (head)`. F57 holds `0015_floor_roles.py` unmerged, F33 will claim 0016 and F19 renumbers to 0017, so **today's expectation is 0018** — but the rule is the rule: run `cd Backend && uv run alembic heads` on the **rebased** branch and use what it prints. Keeping the migration last means any rebase costs one `git commit --amend` touching one file that nothing else references.

### Search is `icontains(term, autoescape=True)` over name and a **digit-normalized** phone, and there is no index (D2)

```python
term = q.strip()
...
stmt = select(Customer).where(
    Customer.tenant_id == tenant_id,
    Customer.deleted_at.is_(None),
)
if term:
    legs = [Customer.name.icontains(term, autoescape=True)]
    phone_term = phone_search_term(term)          # app/customers/validation.py, pure
    if phone_term is not None:
        legs.append(Customer.phone.icontains(phone_term, autoescape=True))
    stmt = stmt.where(or_(*legs))
stmt = stmt.order_by(Customer.name, Customer.id).offset(offset).limit(limit)
```

**The phone leg runs on a digits-only variant of the term, and that is the difference between a working search box and a broken one.** `customers.phone` only ever holds strict E.164 — `normalize_israeli_mobile` rewrites a typed `05X…` to `972` + the rest and then rejects anything that does not fullmatch `^\+9725\d{8}$` (`notifications/validation.py:25, 43-45`), and both writers of the column pass its output (`booking/service.py:176` → `:313`; `booking/owner.py:756` → `:802`). So the stored string for an Israeli mobile is `+972501234567`, and **the leading `0` a human types has been destroyed before storage**. An unanchored ILIKE on the raw term therefore never matches the local spelling: `'+972501234567' ILIKE '%0501234567%'` is false, and so is `%050%` — the stored string contains no `0`,`5`,`0` run at all. The two most natural desk actions — read the number off a card and type `0501234567`, or type the prefix `050` — would return «אין תוצאות» for a customer who demonstrably exists, on a screen whose own label promises search by phone and whose no-results copy tells the owner to try «ספרות מתוך מספר הטלפון».

`phone_search_term` is six pure lines in `app/customers/validation.py`, reusing the shipped rule verbatim rather than re-deriving it: `digits = re.sub(r"\D", "", term)`; if `digits.startswith("05")` then `digits = "972" + digits[1:]`; return `None` when `digits` is empty. `None` is what skips the leg entirely, so a pure-Hebrew term costs no second predicate. **The name leg stays on the raw term** — normalizing it would be the defect, since a name is not digits. `autoescape=True` stays on **both** legs.

A prefix survives the same rule, which is the point: `"050"` → `"97250"`, a genuine substring of `+972501234567`. Pinned in both suites. `test_customers_validation.py` takes the table `"0501234567" → "972501234567"`, `"050-123-4567" → "972501234567"`, `"050" → "97250"`, `"972501234567" → "972501234567"`, `"מיכל" → None`, `"" → None`. `test_customers_db.py` asserts that a customer stored as `+972501234567` is found by `q="0501234567"`, by `q="050-123-4567"` and by `q="050"`, **and** that a name term is still matched literally — the second half matters, because an author picking a term that happens to be a real substring of the stored E.164 is exactly how this bug stays green.

**`autoescape=True` is load-bearing, not decoration.** `icontains` without it interpolates the term straight into a `LIKE` pattern, so a customer typing `_` matches every row and `%` matches every row — a search box that silently returns the whole tenant. Hand-rolling `f"%{term}%"` ships exactly that bug. SQLAlchemy is pinned `>=2.0.36` and `uv.lock` resolves **2.0.51**, so `ColumnOperators.icontains(..., autoescape=True)` exists and escapes `%`, `_` and the escape character itself in the bound parameter. The `db` suite pins both literals.

**`ORDER BY name, id` — the `id` tiebreak is what makes OFFSET paging stable.** Two customers named «מיכל לוי» under one tenant is not hypothetical in a bridal boutique, and with `ORDER BY name` alone Postgres may return them in either order across plans, so page 1 and page 2 can show the same row and hide another. One extra sort column, no query change.

**A blank or whitespace-only `q` is not a filter.** `q.strip() == ""` drops the predicate entirely rather than searching for the empty string — `icontains("")` matches every row, so the two are equivalent in result but not in plan, and more importantly the *service* must treat "she cleared the box" as "show me everyone" rather than as a search that happened to match everyone. `q` is bounded at the boundary with `Query(max_length=MAX_SEARCH_TERM_LENGTH)` where `MAX_SEARCH_TERM_LENGTH = 80`, mirroring `MAX_CUSTOMER_NAME_LENGTH` (`booking/validation.py:40`): an unbounded term is one annotation away from being a free ILIKE-pattern knob on a role-gated but session-cheap route.

**No index, deliberately.** A btree on `name` or on `lower(name)` cannot serve an **unanchored** `%term%` predicate at all — btree can only range-scan a known prefix. The only index that helps is a `pg_trgm` GIN index, and that needs a `CREATE EXTENSION pg_trgm`, which is a database-level privilege this migration does not have and a dependency nothing else in the product needs. At pilot scale — hundreds of RLS-filtered rows against one human keystroke — the sequential scan is the right answer and the index would be a cost on every write to serve a screen nobody has opened. **The upgrade path is recorded in the migration comment** in `0014`'s style: `CREATE EXTENSION pg_trgm; CREATE INDEX idx_customers_name_trgm ON customers USING gin (name gin_trgm_ops) WHERE deleted_at IS NULL;` plus the same on `phone`, at roughly 50k live customer rows per tenant.

Declined: **a separate exact-phone fast path.** `by_phone` already exists for the OTP flow and is the right method there; adding a branch to the search that dispatches to it when the term "looks like a phone" is a heuristic, and it is unnecessary once the term is digit-normalized — `phone_search_term` turns every spelling of a number into the one form the column stores, so an exact match is just the substring case with nothing left over. (An earlier draft declined the fast path on the grounds that it "is wrong the first time someone searches `050` expecting a prefix match". That reason was **factually wrong on this codebase**: under a raw-term predicate `050` does not prefix-match anything, it matches nothing at all. The fast path is still declined, on the correct grounds.)

### The SMS log join, and why the phone leg carries `AND booking_id IS NULL` (D3)

**This is the single most important paragraph in this document.** Everything else in F53 is a screen; this is the part that can leak one customer's personal information onto another customer's page, inside one tenant, on the one screen whose entire brief is personal-information hygiene.

```python
booking_ids = select(Booking.id).where(
    Booking.tenant_id == tenant_id,
    Booking.customer_id == customer_id,
    Booking.deleted_at.is_(None),
)
stmt = (
    select(MessageLog)
    .where(
        MessageLog.tenant_id == tenant_id,          # <- never omit; see below
        MessageLog.deleted_at.is_(None),
        or_(
            MessageLog.booking_id.in_(booking_ids),
            and_(MessageLog.phone == phone, MessageLog.booking_id.is_(None)),
        ),
    )
    .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
    .limit(SMS_LOG_LIMIT)
)
```

**`MessageLog.tenant_id == tenant_id` is on the predicate, and it is the one predicate this query cannot be allowed to inherit from RLS alone.** The repository's own docstring calls the explicit tenant predicate *"redundant defense-in-depth (house pattern — see StaffUsersRepository)"* (`message_log.py:10-11`) and the sibling read this method is modelled on carries it (`:60-64`), so omitting it here would be F53's single departure from the invariant this spec records for `CustomersRepository` — *every* `select` carries all three predicates. It would also be the worst place to take that departure: this is the only query in the feature keyed on a **phone number** rather than on a customer id, and `0008_bookings.py:41-44` designs the collision in — *"The SAME phone under two tenants is two customers, deliberately: a bride who visits two boutiques is not one cross-tenant identity."* RLS is not universally in force either: `app/core/config.py:250` falls back to `DEV_DATABASE_URL` (`:7`, the `postgres` superuser) whenever `DATABASE_URL` is unset, and a superuser bypasses `FORCE ROW LEVEL SECURITY` unconditionally (`db/rls.py:14-18`). Under `app_role_url` — where `test_customers_db.py` runs — the omission is invisible; everywhere else it is a cross-tenant message-body leak. **`MessageLog.deleted_at.is_(None)` is on the predicate for the same reason** — house rule, and `list_by_phone` carries it too, even though nothing in the product soft-deletes a log row.

`message_log` has **no `customer_id`**. It has a `phone` (always written) and a `booking_id` (nullable, populated by F16 for lifecycle sends — `models/message_log.py:26`). So there are exactly two ways to attribute a row to a person, and only one of them is safe on its own.

**Why the phone leg must be fenced.** Phones are corrected — `CustomersRepository.set_phone` (`customers.py:49-75`) exists precisely for the bride who gave a wrong number — and phones are **recycled** by carriers. Put those two facts together:

1. Bride A books on phone X. F16 writes her confirmation and her reminder into `message_log` with `phone = X` and `booking_id = <A's booking>`. Both bodies carry **A's name and A's appointment time** — that is what a confirmation SMS is.
2. The owner corrects A's number to Y. `set_phone` updates `customers.phone`; **`message_log` is not rewritten**, and correctly so — the log is evidence of what was actually sent, to what number, at what time. Rewriting it would destroy the thing it exists to prove.
3. Months later, bride B registers with phone X — either because the carrier reassigned it, or because A's original number was a typo of B's real one, which is the *more* likely path since `set_phone` is invoked exactly when a number was mistyped.
4. B's customer detail is opened. Under a phone-only predicate, **B's screen renders A's confirmation bodies.** A cross-customer disclosure inside one tenant, invisible to RLS (both rows belong to the same boutique), invisible to every isolation test in the repo, and visible to whoever is standing at the front desk.

**With the fence, attribution is exact.** A `message_log` row that *has* a `booking_id` belongs to that booking's customer, full stop — `bookings.customer_id` is authoritative and survives both correction branches, including F15's collision branch which re-points `bookings.customer_id` and leaves `customers.phone` alone (`booking/owner.py:641-695`). A row that has no `booking_id` is an OTP or another non-lifecycle send, and for those the phone at send time is the only identity that exists. The fence says: *use the booking link where there is one; fall back to the phone only where there cannot be one.* Without `AND booking_id IS NULL`, the phone leg re-admits every lifecycle row that the booking leg already attributed correctly — which is exactly the set that can belong to someone else.

**The residual, named rather than assumed away.** A masked OTP row written to phone X before the recycle still surfaces on B's screen: it has no `booking_id`, so the fence cannot reach it, and its `phone` genuinely was X. What that discloses is a timestamp and the string «קוד האימות שלך: ••••••» — no name, no appointment, no digits (`notifications/validation.py:61-65`). Closing it needs `message_log.customer_id`, populated at write time, which is a schema change plus a change to `NotificationService`'s write path plus a backfill that cannot be correct for historical rows (the customer that phone belonged to at send time is exactly the thing not recorded). **Out of scope, Risk 1, upgrade path recorded.**

**One statement, one round trip — and specifically not `UNION`.** A lifecycle SMS sent to the customer's *current* phone matches **both** legs. `UNION ALL` would render it twice; `UNION` deduplicates by sorting the whole result, which is a sort this query does not otherwise need. `or_` needs neither: the row is returned once, and the planner is free to answer it with a single scan.

**`kind='otp'` rows are included, unfiltered**, for four reasons, each sufficient on its own:

1. **The masking ruling already made them safe to store and to read.** `mask_otp_body` exists because the code is worthless in five minutes and the evidence value is "an OTP went to this phone at this time". A screen that stores masked rows and then hides them is honoring neither half.
2. **`message_log` is the Spam-Law evidence trail** (`models/message_log.py:11-12`). A view of it that understates send volume is the one thing it must not do. An owner asked "how many messages did you send this person" must be able to read the answer off the screen.
3. **For a customer with no bookings yet — she verified her phone and then abandoned the flow — the OTP rows are the only evidence that anything was sent at all.** Filtering them empties her log and makes the screen say "we never contacted her", which is false.
4. **Excluding them costs a filter and a rule to remember.** Including them costs nothing. This is the lazy answer and it is also the correct one.

**`LIMIT 50`, newest-first, no pagination — and a `messages_total` count beside it, because the window alone cannot answer the question the log exists for.** `SMS_LOG_LIMIT = 50`, ordered `created_at DESC, id DESC`; this inverts `list_by_phone`'s ascending order (`message_log.py:66`), which is why F53 cannot reuse that method and appends its own.

**The `id` tiebreak is not decoration.** `MessageLog.created_at` is `server_default=text("now()")` (`models/base.py:21-23`) and Postgres `now()` is `transaction_timestamp()` — constant for every row written inside one transaction. Fixture rows inserted through a single `tenant_session` therefore all carry an *identical* `created_at`, so `ORDER BY created_at DESC LIMIT 50` over fifty-one of them returns an arbitrary fifty and both "newest first" and "which row was dropped" become coin flips. `MessageLogRepository.insert` exposes no `created_at` (`message_log.py:14-33`), so the test cannot fix this from the repository side. Two things close it: the tiebreak here — the same reasoning D2 already applies to `ORDER BY name, id` — and, in `test_customers_db.py`, constructing the fifty-one fixture rows as `MessageLog(...)` with explicit, distinct `created_at` values rather than through `insert()`. This module has never run (no Docker locally), so an unstable assertion would surface as a flaky red on its CI debut, which is precisely the blast radius Risk 6 is trying to keep small.

**`messages_total` is a second `select(func.count())` over the identical `where`** — the same shape D6 specifies for the list's `total`, and the same shape `bookings.py:596-598` already ships. It exists because the fifty-row window is **not** a bound on the bride's own behaviour: `kind='otp'` rows are written by an *anonymous* endpoint (`notifications/router.py:45,50-53` — *"two anonymous, tenant-scoped POSTs"* that *"read no cookie and carry no ambient credential"*), they never carry a `booking_id` so they always land in the phone leg (`notifications/service.py:242-248`), and they are always the newest. At `otp_send_max_per_phone_window = 5` per `otp_send_phone_window_seconds = 3600` (`core/config.py:76-77`) that is 120 rows per phone per day **per process**, and the `FixedWindowRateLimiter` budget is in-memory, per-instance and resets on restart. Fifty OTP rows evict every confirmation, reminder, owner-cancel and owner-reschedule row from the view — permanently, since there is no pagination and no `kind` filter. Without a total, the screen would then answer *"how many messages did you send this person"* with "fifty", which is the understatement D3's own second reason forbids. With it, the truncation line reads «מוצגות {{count}} מתוך {{total}} רשומות ביומן» and the evidence question is answerable whether or not the window truncated. Both numbers sit mid-sentence bounded by Hebrew on either side, so neither needs `isolateLtr` (D11). Raising the shared cap is **not** the fix — it moves the eviction threshold without removing it; bounding the OTP contribution separately (a second constant, at most ten `kind='otp'` rows) is the recorded upgrade if the panel itself stops being useful. Named as Risk 15.

**No new indexes on `message_log`, and the reason is structural rather than a scale bet.** An `OR` across two columns can only be served by a **BitmapOr**, which requires an index on **both** legs — one alone buys nothing at all, because the planner still has to sequentially scan for the other leg and may as well do one scan for both. So the upgrade is a *pair* or it is nothing: `CREATE INDEX idx_message_log_tenant_phone ON message_log (tenant_id, phone) WHERE deleted_at IS NULL;` **and** `CREATE INDEX idx_message_log_tenant_booking ON message_log (tenant_id, booking_id) WHERE deleted_at IS NULL;`, at roughly 100k rows per tenant. Recorded in the migration comment beside the search-index upgrade path.

### `SmsLogRow` ships five fields, and the omissions are rulings (D4)

```python
class SmsLogRow(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    kind: str
    status: str
    body: str
```

| Omitted | Why |
|---|---|
| `provider_message_id` | An operator's correlation handle for a support ticket with Twilio. It means nothing to a boutique owner and it is a third-party identifier this product has no reason to publish. |
| `error` | **Already fenced by a shipped comment** — *"never reaches a response body"* (`models/message_log.py:23-24`). Provider failure detail is operator-facing and frequently names infrastructure. The UI shows `status = 'failed'`, which is the fact the owner can act on. |
| `phone` | It is on the parent object already (`CustomerDetail.phone`). Repeating it per row invites exactly the mental model D3 exists to destroy — that a log row is identified by its phone number. |
| `tenant_id`, `booking_id`, `deleted_at`, `updated_at` | Internal keys and lifecycle columns; nothing on the screen renders them. |

`kind` and `status` are the raw enum values (`MessageKind`, `MessageStatus` — `models/constants.py:32-44`); the console maps each to Hebrew through its own key table and falls back to rendering the raw value for an unknown one, the `statusBadge` shape (`lib/booking.tsx:22-26`).

**The log rides inside `CustomerDetail`.** One click, one fetch, one round trip. A separate `GET /manage/customers/{id}/messages` would be a fourth route, a second loading state and a second failure mode on a screen where the log is never wanted without the customer. Split it out when a log outgrows a screen — which, at `LIMIT 50` with no pagination, is the same trigger as adding pagination.

**Booking history is the third panel and needs the third repository append (correction C8).**

```python
async def list_recent_for_customer(
    self, session: AsyncSession, tenant_id: UUID, *, customer_id: UUID, limit: int
) -> list[Booking]:
```

`tenant_id ==`, `customer_id ==`, `deleted_at.is_(None)`, `.order_by(Booking.starts_at.desc()).limit(limit)`, riding `idx_bookings_tenant_customer`. **Every status, cancelled included** — `list_day`'s docstring is the argument (`bookings.py:578-581`): a cancelled row is the owner's evidence that something happened, and on a CRM screen "she cancelled twice" is precisely the fact the screen exists to surface. `BOOKING_HISTORY_LIMIT = 50`, and the UI says so when it truncates.

`CustomerBookingRow` = `{id, starts_at, status, appointment_type_name}`. `dress_name`, `dress_size`, `seat_index`, `notes`, `manage_token_hash` and `phone` are all on `Booking` and none of them ship: the booking detail screen already renders them to the same two roles, one click away through the bookings section, and a CRM row that duplicates a detail view is a second place for the same fact to drift. `appointment_type_name` is the deliberate snapshot (`models/booking.py:19-22`) and is correct here for the same reason it is correct there — history must render as what the customer agreed to.

**`created_at` is not on `CustomerRow` or `CustomerDetail`, and that is deliberate.** F52's D7 established that `customers.created_at` is meaningless as a "first seen" date after F15's phone-correction collision branch: the branch re-points a booking to an existing customer row and leaves both rows alive, so a customer's row can post-date her own first booking. Shipping it would put a plausible, wrong "customer since" date on a CRM screen — the exact class of number a boutique owner would quote back to a bride. If a first-visit date is ever wanted, it is `min(bookings.starts_at)`, which is a different query with a different meaning. Recorded here because `created_at` on a list resource is otherwise so standard that its absence is the thing a reader stops on (F51's rejected review finding, inverted).

### Tags and notes: one pure module, no controlled vocabulary (D5)

`Backend/app/customers/validation.py`, the `boutique/validation.py` shape — no SQLAlchemy, no session, no I/O, unit-tested in the fast suite.

```python
class CustomerValidationError(DomainValidationError):
    """Domain-rule violation on a customer notes/tags write; the router maps it
    to the house-shape 400.

    Re-parented onto the shared base so one handler serves every domain module;
    behaviour-neutral, since Starlette still matches this class through its MRO."""
```

| Constant | Value | Why |
|---|---|---|
| `MAX_TAG_LENGTH` | `24` | A tag is a chip on a 720px-capped column. Longer than this and it is a note, and there is a field for notes. |
| `MAX_TAGS` | `10` | Ten chips is the most that reads as a set rather than a paragraph. It is also what makes "no autocomplete" honest — see below. |
| `MAX_CUSTOMER_NOTES_LENGTH` | `2000` | The **profile-description** peer (`boutique/validation.py:30`), **not** `MAX_BOOKING_NOTES_LENGTH = 500` (`booking/validation.py:45`). A booking note is about one appointment; a CRM note accretes across every visit a bride makes over a year of fittings. |
| `MAX_SEARCH_TERM_LENGTH` | `80` | Mirrors `MAX_CUSTOMER_NAME_LENGTH` (`booking/validation.py:40`) — the longest thing that can legitimately be searched for. |

**`normalize_tags(tags: list[str]) -> list[str]`**, in this exact order:

1. `strip()` each element.
2. Drop empties — a trailing blank chip from the UI is not a tag.
3. **Reject control characters, using `_CONTROL_CHARS` from `booking/validation.py:69`** — the whole C0 set including `\t \n \r`. **Not line 70** (`_CONTROL_CHARS_EXCEPT_WS`), which permits them; that is the correct import for `notes` and the wrong one here. A tag is a one-line label, and a newline inside a `TEXT[]` element renders as a chip that is two lines tall and copies wrong. `booking/validation.py:62-68` states the split.
4. Length check against `MAX_TAG_LENGTH`, per element.
5. **Case-insensitive dedup, first occurrence wins and keeps its casing.** `["VIP", "vip"]` → `["VIP"]`. The owner typed the first one deliberately; lowercasing everything would turn a boutique's «VIP» into «vip» on save, which reads as the product correcting her.
6. **Cap at `MAX_TAGS` *after* dedup** — capping first would let ten duplicates crowd out a real eleventh tag.
7. **Preserve caller order. Do not sort.** The order the owner arranged them in is information; alphabetizing on save is the product rearranging her screen.

Both `_CONTROL_CHARS` and `_CONTROL_CHARS_EXCEPT_WS` are underscore-private and there is no shipped precedent for importing either across modules — `grep` finds uses only inside `booking/validation.py`. So this is a new, deliberate act and carries **one line of comment at the import site** naming which class and why that one.

Messages follow the house register — lowercase, field name first, no trailing period: `"tags: at most 10 tags are allowed"`, `"tags: a tag is too long"`, `"tags: a tag contains invalid characters"`, `"notes is too long"`, `"notes contains invalid characters"`.

**No controlled tag vocabulary.** A vocabulary means a `customer_tags` table, a management screen, a second migration, a rename story and an orphan story — for a pilot where nobody yet knows what the tags are. Free text is how you find out what the vocabulary should be. **Upgrade path recorded**: promote the observed set into a table once a boutique has been using it for a quarter, with `unnest(tags)` as the seed query.

**No tenant-level distinct-tags endpoint, and no autocomplete.** With a 10-tag cap and one pilot boutique, autocomplete saves a handful of keystrokes and costs: an endpoint, an unindexable `SELECT DISTINCT unnest(tags)`, a staleness question (does a tag disappear from the list the moment its last customer loses it?), and a WCAG-conformant combobox — which is a real component with a real keyboard contract, not an `<input list>`. **Upgrade path recorded**: `GET /manage/customers/tags`, one repository method, no migration.

**No index on `tags`.** Nothing queries it — the search predicate is name and phone only (D2). A GIN index on an array nothing filters by is a write cost with no reader. The day tag filtering ships, `CREATE INDEX idx_customers_tags ON customers USING gin (tags) WHERE deleted_at IS NULL` is the one-line upgrade, and it is recorded in the migration comment.

### The API (D6)

New package `Backend/app/customers/` — `__init__.py`, `router.py`, `schemas.py`, `service.py`, `validation.py`. `app/notifications/` is the in-repo precedent for the `service.py` / `router.py` / `schemas.py` trio in a package that owns no table of its own, and F52's D8 cites the same one. Not two files in `app/booking/`: F53 reads across `customers`, `bookings` **and** `message_log` and writes to `customers`, so it belongs to no existing domain, and `booking/schemas.py` would gain five response models for an API that is not the booking API.

**Repository work appends to three existing files and creates none**: `db/repositories/customers.py` (search + the notes/tags update), `db/repositories/message_log.py` (the D3 join), `db/repositories/bookings.py` (`list_recent_for_customer`).

`CustomersService(get_session_factory())` is constructed in `create_app()` onto `app.state.customers_service`, beside the `DashboardService` line (`main.py:562`), and reached through `get_customers_service(request)` behind a `Service = Annotated[…]` alias — the pattern that lets the fast API test swap in a duck-typed `FakeCustomersService`. **No clock**; nothing here is time-derived.

Router: `APIRouter(prefix="/manage", dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))])`. Both roles at **router** level, and it must **not** be added to `test_staff_role_gating.py`'s `OWNER_ONLY` — `dashboard/router.py:15-16` records why in as many words. `_no_store` is a local three-line copy: this response renders a person's phone number and free text about her, so it takes the header for the same reason `booking/owner_router.py` does. The docstring cites `auth/staff_router.py:22-27` (the decision of record — *"the alternative points the dependency arrow backwards"*) and **states no ordinal**, because every ordinal written into this codebase so far has gone stale (correction C5).

Included in `create_app()` after `gateway_router` (`main.py:1043`) and before `storefront_router` (`:1046`), carrying the shadowing comment every `/manage` include after the first carries, and naming `test_customers_api.py`'s `ROUTES` table as its guard.

| Method | Path | Input | Answers |
|---|---|---|---|
| `GET` | `/manage/customers` | `q?`, `offset=0`, `limit=50` | `CustomerListResponse` |
| `GET` | `/manage/customers/{customer_id}` | — | `CustomerDetail` |
| `PATCH` | `/manage/customers/{customer_id}` | `UpdateCustomerRequest` | `CustomerDetail` |

**Real HTTP verbs and a path parameter.** Three shipped router docstrings say so in identical words (`dashboard/router.py:38-40`, `auth/staff_router.py:27-30`, `booking/owner_router.py:16-18`) and F15's D7 ruled it. The `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate for another codebase; a `POST /list` here would be the first in the product.

Handler shapes, following `auth/staff_router.py:104-127` exactly — bare `customer_id: UUID` (no `Path(...)`), bare `body: UpdateCustomerRequest`, tenant from `get_current_tenant(request).id` and **never** from `staff.tenant_id`, the router unpacking the request model into keyword arguments so the service never sees a pydantic object, no try/except and no error mapping anywhere in the router:

```python
@router.get("/customers")
async def list_customers(
    request: Request,
    service: Service,
    q: Annotated[str | None, Query(max_length=MAX_SEARCH_TERM_LENGTH)] = None,
    offset: Annotated[int, Query(ge=0, le=MAX_LIST_OFFSET)] = 0,
    limit: Annotated[int, Query(ge=1, le=CUSTOMER_LIST_MAX_LIMIT)] = CUSTOMER_LIST_DEFAULT_LIMIT,
) -> CustomerListResponse:
    return await service.list_customers(
        get_current_tenant(request).id, q=q, offset=offset, limit=limit
    )


@router.patch("/customers/{customer_id}")
async def update_customer(
    request: Request,
    staff: Staff,
    service: Service,
    customer_id: UUID,
    body: UpdateCustomerRequest,
) -> CustomerDetail:
    return await service.update(
        get_current_tenant(request).id,
        customer_id,
        notes=body.notes,
        tags=body.tags,
        actor=staff,
    )
```

**The two GETs declare no `staff` parameter; the `PATCH` does.** The `RoleGate` runs router-level and needs no binding, so the only reason to inject `StaffContext` is a use for the acting identity — and the `PATCH` has exactly one: `actor_id` on its audit row (D8). Declaring it on the GETs would be a parameter with no reader, and it would put the session-derived `tenant_id` in reach on the two routes that have no other reason to want it. `MAX_LIST_OFFSET = 1_000_000`, `CUSTOMER_LIST_DEFAULT_LIMIT = 50` and `CUSTOMER_LIST_MAX_LIMIT = 200` are **restated** in `app/customers/validation.py` rather than imported from `app.booking` — `booking/owner.py:52-58` shows restatement is the house call, and the reason `MAX_LIST_OFFSET` exists at all (an unbounded offset reaches asyncpg's `int8_encode` and answers 500) is restated with it.

**`UpdateCustomerRequest(ForbidExtraModel)`** — `extra="forbid"`, so an unknown key is a house-shape 400 rather than a silently ignored field (`app/schemas.py:13-18`):

```python
class UpdateCustomerRequest(ForbidExtraModel):
    """Every field optional. `None` means NOT SUPPLIED — leave the column alone.
    `""` and `[]` mean CLEAR, the `boutique/validation.py:110` ruling."""

    notes: str | None = None
    tags: list[str] | None = None
```

**`None` = not supplied, `""` / `[]` = clear.** That is the one ambiguity a partial `PATCH` over nullable columns has, and it is resolved the way `boutique/validation.py:110` already resolved it for owner settings. `notes=""` writes `""`, not `NULL` — one representation of "cleared", chosen because `""` round-trips through the `TextArea` with no `?? ""` at the render site. `tags=[]` writes `'{}'`.

Response models are plain `BaseModel`s used as **return-type annotations**, never `response_model=` — `dashboard/schemas.py:3-5` states the house form, and there is no `response_model=` anywhere in this repo.

```json
GET /manage/customers?q=מיכל&offset=0&limit=50
{
  "items": [
    { "id": "…", "name": "מיכל לוי", "phone": "+972501234567", "tags": ["VIP", "השמלה הוזמנה"] }
  ],
  "total": 3,
  "offset": 0,
  "limit": 50
}
```

```json
GET /manage/customers/{customer_id}
{
  "id": "…",
  "name": "מיכל לוי",
  "phone": "+972501234567",
  "notes": "מגיעה עם אמא. מעדיפה תורים בבוקר.",
  "tags": ["VIP"],
  "bookings": [
    { "id": "…", "starts_at": "2026-08-04T07:00:00Z", "status": "completed",
      "appointment_type_name": "מדידה ראשונה" }
  ],
  "messages": [
    { "id": "…", "created_at": "2026-08-01T09:12:00Z", "kind": "confirmation",
      "status": "sent", "body": "…" }
  ],
  "messages_total": 7
}
```

**`messages_total` is the count under D3's identical `where`, not `len(messages)`** — the fifty-row window can be entirely consumed by OTP rows written through an anonymous endpoint, so the count is the only field that answers the evidence question when it truncates (D3). Same second-`select(func.count())` shape as the list's `total`.

**`CustomerRow` carries `phone`, and that is a departure from a shipped ruling, so it is argued rather than inherited.** `booking/schemas.py:107-114` keeps `customer_phone` off `OwnerBookingRow` on purpose — *"the list is a glance at the day, the phone and the free text are what the owner opens a booking to see. Keeping them off the row means the list response is not a bulk PII export of the boutique's whole day"* (D18, mirrored on the client at `api.ts:308-312`). F53's list pages the whole customer base at `limit` up to 200, which is a strictly **larger** export than the one that ruling refused, so the burden is on F53:

- **A day list is a schedule; a customer directory is an index of people.** D18 can drop the phone because the row's identity is the appointment — the time and the status are what the owner scans. Here the row's identity *is* the person, and the whole screen exists to find one.
- **The phone is the disambiguator D2 says is not hypothetical.** *"Two customers named «מיכל לוי» under one tenant is not hypothetical in a bridal boutique"* — that is why `ORDER BY name, id` carries a tiebreak. Without the phone on the row, two identically-named rows are indistinguishable and the owner must open both to find out which bride she has on the phone.
- **The search itself promises it.** `customers.searchLabel` is «חיפוש לפי שם או טלפון» and the phone leg is digit-normalized (D2). A result set matched on a number that then refuses to show the number is a screen that cannot be checked.
- **`notes` is not on the row**, and that is where D18's actual force lands: the free text about a person is detail-only, exactly as D18 keeps `notes` off `OwnerBookingRow`. F53 declines the half of the export that has no reader on the list and keeps the half that is the list's whole job.

Consequently `phone` is **not** in `CUSTOMER_FORBIDDEN_KEYS` for either response half — a key the feature deliberately ships cannot also be a disclosure tripwire, and splitting the walk per-response to forbid it on the list only would be a guard against the decision just taken rather than against a regression. What pins the decision is this paragraph and the `CustomerRow` field list; what pins the *detail-only* fields is D4's `SmsLogRow` equality.

`{items, total, offset, limit}` is the shipped paginated envelope (`booking/owner_router.py`, mirrored in `api.ts`'s `OwnerBookingListResponse`). This list **is** paginated, unlike F51's staff list, because a boutique's customer count grows without bound while its staff count does not — so the bare-array precedent (`GET /manage/appointment-types`) does not transfer.

**`total` is the count under the same predicate as the page**, computed with a second `select(func.count())` over the identical `where` — the `list_day` shape (`bookings.py:596-598`). A `total` computed without the search term would tell the owner she has 400 customers on a screen showing three.

**One `tenant_session` per detail request, and one private builder that both the `GET` and the `PATCH` go through.** `_build_detail(session, tenant_id, customer_id)` is `by_id` → the customer (or `CustomerNotFoundError`) → the booking-history read → the D3 message read → the `messages_total` count. `session.begin()` makes the whole handler body one transaction, so those reads see one consistent snapshot — which matters here: a booking created between the customer read and the message read would otherwise produce a log row whose `booking_id` matches nothing in the history panel beside it.

**The `PATCH` returns the same fully-built detail, on the write path and on the no-op path alike.** It declares `-> CustomerDetail`, and the client does `setDetail(updated)` unconditionally (UI behaviour), so a handler that reasoned *"the mutation touches `customers` only"* and answered `bookings: []`, `messages: []`, `messages_total: 0` would blank the booking-history and SMS-log panels the moment the owner pressed «שמירה», until she navigated away and back. It is the same rule `BookingsSection.tsx:72-78` states for the row — *"the row is patched from the response, so the two views cannot disagree — same object"* — and it only holds if the response really is the same object. So: inside the one transaction, the `UPDATE` and the audit row first, then `_build_detail`; and on the D8 no-op path, `_build_detail` alone. `test_customers_service.py` pins it — a `PATCH` that moves `tags` returns a detail whose `bookings` and `messages` are the same non-empty lists the fake repositories hold, and whose `messages_total` is the fake's count.

### No advisory lock (D7)

F51's D3 took a namespaced per-tenant advisory lock because its invariant was **at-least-one live owner** — a minimum, which no index can express and which a `count(*)` subquery cannot enforce under READ COMMITTED. F53 has no invariant of that shape. A notes/tags edit is a single-row `UPDATE` on `customers`, and two owners editing the same customer's notes concurrently is last-write-wins — which is the correct answer for free text and the answer every text field in this product already gives.

Stated as a decision so its absence reads as decided rather than forgotten. Declined: optimistic concurrency via an `updated_at` precondition (it turns a rare, recoverable overwrite into a frequent, confusing 409 on a field where the loser can simply retype), and a lock (serializing every CRM edit for a tenant to protect nothing).

### Audit: one action, field names only (D8)

One new `AuditAction` member. `audit_log.action` is plain TEXT with no CHECK (`0003`), so this needs **no migration** — the same fact `AuditAction.BOOKING_*`, `STAFF_*` and `GATEWAY_*` already lean on.

```python
CUSTOMER_UPDATED = "customer_updated"
```

**One value, not `CUSTOMER_NOTES_UPDATED` + `CUSTOMER_TAGS_UPDATED`.** The split criterion this repo actually applies is recorded three times in `models/constants.py` and it is not "is this a distinct field" — it is **"is this a distinct question a security or ops audit asks of this table"**. `:129-134` states it for the closest case: *"Role change and password reset keep their own values rather than folding into `STAFF_UPDATED`, because those are the two questions a security audit actually asks of this table — 'who was made an owner' and 'whose password did someone else change' — and each stays one `WHERE action = …`."* Nobody will ever ask this table "who edited tags but not notes". They will ask "who touched this customer's record", and that is one `WHERE action = 'customer_updated'`. The member goes in its own `# --- F53 …` block appended after `GATEWAY_LATE_SETTLEMENT` (`:171`) and before `PlatformAuditAction` (`:174`) — the least-contended seam in a file F57 also edits (at `StaffRole`, `:9-15`).

```python
details = {"fields": sorted(changed)}   # e.g. {"fields": ["notes", "tags"]}
entity  = str(customer_id)
actor_id = actor.id
```

**Field names only. No `from`/`to`, no note text, no tag strings, no name, no phone.** This is a deliberate departure from F51's `STAFF_UPDATED`, which ships `{"display_name": {"from": …, "to": …}}` — and F51 is **correct there**, which is why the difference has to be argued rather than assumed:

- A `display_name` is a label the staffer chose for herself inside a product she works in. Customer notes are **free text written about a third party who never sees them**, by one member of staff, potentially about her behaviour.
- `audit_log` has **no retention policy** in this product. Nothing prunes it. Whatever lands in `details` is there for the life of the database.
- `audit_log` rows are read by **platform operators**, not only by the boutique — `PlatformAuditAction` exists (`models/constants.py:174-181`) and the platform surface reads across tenants. Copying a bride's notes into that table exports them out of the tenant that owns them.
- The audit question here is *who changed this record and when*. The old value is not needed to answer it, and the new value is on the row itself.

`entity` is `str(customer_id)`, **never the name** — the id is the identity the row is about, and a name in an audit row is one more copy of a person's data with no retention policy behind it. Emails do appear in F51's staff audit rows for the mirror-image reason (the email *is* the staff identity); a customer's identity is her id.

**F51's no-op rule carries.** The service compares the incoming values against what is stored: if `notes` did not move and `tags` did not move (list equality after `normalize_tags`), it writes **no `UPDATE` and no audit row**, and answers 200 with the unchanged detail. An all-unchanged patch that wrote a row would make the table meaningless, which is the reason the frontend also sends only what moved (Frontend Changes).

### Errors: nothing new anywhere (D9)

| Raised | Code | Status | Handler |
|---|---|---|---|
| unknown, soft-deleted or another tenant's `customer_id` | `NOT_FOUND` | 404 | existing (`DomainNotFoundError`) |
| tag too long / too many / control char; notes too long or with a control char | `VALIDATION_ERROR` | 400 | existing (`DomainValidationError`) |
| `limit=0`, `limit=201`, `offset=-1`, `q` over 80 chars, unknown body key, non-UUID path segment | `VALIDATION_ERROR` | 400 | existing (`RequestValidationError`) |
| `PATCH` from a mismatched origin | `CSRF_ORIGIN_MISMATCH` | 403 | existing (`CsrfOriginMiddleware`) |
| an out-of-enum role on any route | `NOT_AUTHORIZED` | 403 | existing (F31, fails closed) |
| no session cookie | `NOT_AUTHENTICATED` | 401 | existing |

**No new error code, no new body constant, no new `@app.exception_handler`, no `main.py` change beyond the service wiring and the include.** `CustomerNotFoundError(DomainNotFoundError)` and `CustomerValidationError(DomainValidationError)` subclass the `app/errors.py` bases, and Starlette walks `type(exc).__mro__`, so the handlers bound to those bases already answer them — `app/errors.py:1-9` exists for exactly this, and `auth/staff.py:87-91` says so out loud.

**`shift_manager` is admitted on all three routes**, so it raises nothing; the 403 in the table is reachable only for a role string the enum does not know, which `RoleGate` fails closed on.

**`CSRF_ORIGIN_MISMATCH` *is* in F53's set, and this is where F53 diverges from F52's template.** `CsrfOriginMiddleware` fences `request.method in MUTATING_METHODS` (`csrf.py:48`); F52's route is a GET, so its `SPEC_ERROR_CODES` cannot contain the code and `test_dashboard_api.py:343-352` asserts the GET-with-mismatched-origin case is *allowed*. F53's `PATCH` is fenced. `test_customers_api.py` therefore ships a real mismatched-origin `PATCH` assertion and unions the code, and **must not** copy the dashboard module's inverse test.

**The wire envelope is two keys** — `{"error": {"code", "message"}}`. No `status`, no `details` array. `.claude/rules/frontend-react/FRONTEND.md` describes a four-key shape; it is wrong for this repo.

**No audit row on either GET.** `dashboard/service.py:344-349` states the rule: *"No GET handler in this product writes one — not the booking day list, not the booking detail that renders a bride's phone and free-text notes, not the owner-only staff list."* F53's detail renders exactly that material and writes nothing.

**No rate limiter.** No `/manage` router carries one; the storefront limiters exist because that surface is anonymous. The protection here is the session cookie and the role gate.

### The console section (D10)

`NAV` gains a row with `roles: ALL`, positioned **after `board` and before `staff`** — index 8. Two constraints fix that position and both are recorded in the shipped code:

- **Not index 0.** `App.tsx:59-65` states the rule: row 0 is the landing section, and *"nothing inserted below it can displace either the initial `section` or the `reachable[0]` fallback."*
- **Above the two owner-only rows.** `Nav.test.tsx:66-68` records the coupling: *"The two owner-only rows, last. Everything above is `roles: ALL`, which is what keeps the shift_manager assertions below a `.slice(0, 8)`."* Inserting at 8 turns both `.slice(0, 8)` into `.slice(0, 9)` and leaves the owner-only rows last.

**No router**, in-panel state swap (`BookingsSection.tsx:53-55`). **No new `packages/ui` component and no promotion** — that is the Q2 self-approval hinge. **No new npm dependency**: the tag editor is an `Input` plus an add `Button` plus `Badge` chips, and the search debounce is `useEffect` + `setTimeout(…, 300)` + a cleanup that clears it — six lines. Not a debounce package, and specifically **not F57's unmerged `lib/usePoll.ts`**, which is a different concern on an unmerged branch.

**Patch from the mutation response, never refetch** (`StaffSection.tsx:126-128`, `BookingsSection.tsx:74-78`). `PATCH` returns the whole `CustomerDetail`, so the detail state is replaced with the response object and the list row is patched from it — *"two views that render one object cannot disagree."* The list is **not** refetched: `name` and `phone` cannot move through this endpoint, so list membership and the `ORDER BY name, id` order are both invariant under the only mutation F53 ships. That is the inverse of BookingsSection's reschedule case, and it is worth stating because the next mutation added here (a name edit) *would* need the refetch.

### Copy: Hebrew only, and «יומן הודעות» is not a style choice (D11)

**The deck is 51 keys** (§Hebrew copy deck), and it is the only place the strings exist — the table is scrapeable verbatim, so no rejected wording appears inside it. Every user-visible string is Hebrew, in `he.ts`, as **flat dotted keys**; `ar.ts` carries the identical key set with the approved Hebrew standing in verbatim and **never `""`** — the 2026-07-31 LANGUAGES ruling (`LOOP-STATE.md:1138`, verified: the file is 1146 lines and Pre-decided #46 sits at `:1063`, not here) and Q3 / pre-decided #47. The mechanical guard is `i18n.test.ts`'s `describe("the ar bundle")` (`:251-265`): `:258` rejects any `ar` value equal to `""` — i18next's `returnEmptyString` default renders `""` rather than falling back, so an empty placeholder blanks the page instead of showing Hebrew — and `:262` asserts every `HE` key exists in `ar.translation`. That second one is why the `HE_F53` fold is not optional. `lng` and `fallbackLng` stay `"he"`. No switcher.

**The SMS-log heading is «יומן הודעות» — "message log" — and never «הודעות שנשלחו».** Two independent reasons, and the second is the one that matters:

1. **The mechanical one.** `i18n.test.ts:247` filters every `HE` value through `/נשלח|תישלח|בדרך/` and asserts the result is empty. «הודעות שנשלחו» contains נשלח and red-fails the build the moment `HE_F53` is folded into `HE` — which it must be, because the file's own comment (`:32-34`) records that a constant declared but *not* folded in silently skips the resolve check, both register guards **and** the `ar` parity guard.
2. **The honest one.** The log renders `status = 'failed'` rows. A heading that says "messages that were sent" over a table containing messages that were not sent is a lie, and it is precisely the lie that guard was written to prevent — the guard's own comment says *"a copy deck that has to dodge its own guard is copy that is one edit away from lying"* (`:237-238`). «יומן הודעות» is not a dodge; it is the accurate name for the thing, and it is accurate *because* the log is a record of attempts rather than of deliveries.

The same reasoning fixes the status words. `status = 'sent'` means the provider accepted the message and returned a `provider_message_id`; it does not mean the handset received it. So the Hebrew is **«הועברה לספק»** — handed to the provider — which is true, contains no banned root, and does not promise a delivery the product cannot observe. `queued` is «בהמתנה», `failed` is «נכשלה».

**Zero exclamation marks** (pre-decided #5), mechanically enforced over `HE`.

**Numbers inside `help` strings sit mid-sentence, bounded by Hebrew on both sides, and are not isolated.** `InputProps.help` and `TextAreaProps.help` are typed `string`, so `isolateLtr` — which returns a `ReactNode` — **cannot** be used there at all. A numeric run with strong RTL characters on both sides renders in place under the bidi algorithm; the hazard `isolateLtr` exists for is a number adjacent to a string edge or to punctuation. `customers.count` is announced in a `role="status"` paragraph that renders a `ReactNode`, and it **does** go through `isolateLtr` — the `BookingsSection.tsx:120` idiom — because its number sits at the string's edge. The **two truncation lines do not**, and for the stated reason rather than by omission: their numbers are mid-sentence with Hebrew on both sides (`customers.messagesTruncated` carries two, «מוצגות {{count}} מתוך {{total}} רשומות ביומן»), which is the case the bidi algorithm already handles. The only user-visible number that would have needed isolation and had no key was the tag-row `+N` token, and that is deleted rather than isolated (§`CustomersSection.tsx` item 7).

**The copy deck lives in this spec (§Hebrew copy deck), not in `.planning/design/screens/manage-customers/`.** That is a departure from F51 and F52, which each authored a `{screen}.md` + `copy.md` pair as Task 1, and it is recorded rather than silently taken: F53's screen introduces no novel pattern (Q2), so the deck's only load-bearing content is the string table, and one copy of every string in the artifact the builder actually reads is better than two copies in two files that can drift. If the design gate asks for the folder, it is a mechanical extraction of the table below.

### One fetch per view, and no poll (D12)

`useEffect` + `let cancelled = false` + `.then`/`.catch` guarded by `if (!cancelled)` + a cleanup that sets `cancelled = true` — `BookingsSection.tsx:27-49` verbatim in shape. **No async/await in the effect, no `AbortController`.** The list effect additionally carries the 300 ms debounce keyed on the search term; the detail effect is keyed on `[customerId, t]`.

No poll, no auto-refresh, no `me()` refresh. A customer record changes when someone in the room changes it. F51's Risk 3 (the nav is filtered once at bootstrap) stays with F34, where D11 of F52 sent it.

**`command.downgrade(cfg, "-1")` in the migration round-trip, as a departure.** All four shipped round-trip tests hardcode a downgrade target (correction C4), so this is not a bug fix — it is a choice made for one specific reason: F53's block lands in `test_migrations.py` alongside F57's, and three unmerged migrations are racing for numbers. `"-1"` means "one step back from head", which survives renumbering, which makes F53's block order-independent, which makes the merge resolution a plain concatenation instead of a hand edit. The `try/finally: command.upgrade(cfg, "head")` is not decoration either — `0014`'s own comment says why: leaving the schema down drops columns the ORM still maps, and every later `db` test in the shared session-scoped container then fails with `UndefinedColumn` somewhere unrelated to itself.

---

## Frontend Changes

### Files

| File | Change |
|---|---|
| `Frontend/apps/manage/src/components/CustomersSection.tsx` | **new** — search field, count region, list, in-panel detail swap |
| `Frontend/apps/manage/src/components/CustomerDetail.tsx` | **new** — header, notes editor, tag editor, booking history, SMS log |
| `Frontend/apps/manage/src/api.ts` | wire types + three methods, inserted **after `listManageSlots` (`:656`)**, not at the object end |
| `Frontend/apps/manage/src/App.tsx` | import after `CatalogSection`; `\| "customers"` in `SectionKey` after `"bookings"`; `NAV` row after `board` / before `staff`; render line after the `board` line |
| `Frontend/apps/manage/src/validation.ts` | **`export const`** `MAX_TAG_LENGTH`, `MAX_TAGS`, `MAX_CUSTOMER_NOTES_LENGTH`, `MAX_SEARCH_TERM_LENGTH`; **unexported `const`** `CONTROL_CHARS`, `CONTROL_CHARS_EXCEPT_WS`; `validateTag`, `validateCustomerNotes` |
| `Frontend/apps/manage/src/i18n/he.ts` | `// --- F53, customers CRM ---` block appended after `:537`, before the closing `},` at `:538` |
| `Frontend/apps/manage/src/i18n/ar.ts` | the same keys, the Hebrew verbatim, appended after `:303` |
| `Frontend/apps/manage/vite.config.ts` | `customers` into the alternation at `:19`, **and** the prose at `:13-17` ("eleven names" → twelve, "a twelfth router" → thirteenth) |
| `Frontend/apps/manage/src/__tests__/Nav.test.tsx` | api-mock row, `NAV_LABELS` entry, two `.slice(0, 8)` → `(0, 9)`, two test names, the `:66-68` comment, one new describe |
| `Frontend/apps/manage/src/__tests__/i18n.test.ts` | `HE_F53` constant, folded into the `HE` spread at `:39`, own describe block |
| `Frontend/apps/manage/src/__tests__/CustomersSection.test.tsx` | **new** |
| `Backend/tests/test_frontend_constant_parity.py` | a fourth `MIRRORS` param, and `test_control_character_classes_match_the_backend` parametrized over both `validation.ts` files |

**The two declaration forms in `validation.ts` are not interchangeable, and getting them backwards is a red CI round for nothing.** `test_frontend_constant_parity.py` scrapes the two kinds with two mutually exclusive regexes: `_CONST_RE` (`:93`) requires `^export const NAME = <digits>;`, while `_TS_REGEX_RE` (`:130`) requires a line-start **`const NAME = /…/;`** with no `export`. The shipped mirror does exactly this — `apps/storefront/src/validation.ts:19-20` exports the numerics, `:32,34` declares both regexes with a bare `const`. So the four numeric constants are exported and the two regexes are not, copied byte-for-byte from `booking/validation.py:69-70`. A builder who writes `export const CONTROL_CHARS = /…/;` red-fails the newly parametrized `test_control_character_classes_match_the_backend` with an assertion message that names the *storefront* file (`:148`, hardcoded) — see the test plan, which requires that message to stop naming one file once the test is parametrized over both.

**`packages/api-client` is not touched** — it is a three-file stub and each app ships its own `src/api.ts`.

### TypeScript type changes

All **snake_case**, mirrored field-for-field. There is no case-conversion layer in this repo (`api.ts:1-5`); a camelCase interface compiles and reads `undefined` at runtime on every field.

```ts
// --- customers wire types (mirror backend/app/customers/schemas.py) ---

export interface CustomerRow {
  id: string;
  name: string;
  phone: string;
  tags: string[];
}

export interface CustomerListResponse {
  items: CustomerRow[];
  total: number;
  offset: number;
  limit: number;
}

export interface CustomerBookingRow {
  id: string;
  starts_at: string;
  status: string;
  appointment_type_name: string;
}

export interface SmsLogRow {
  id: string;
  created_at: string;
  kind: string;
  status: string;
  body: string;
}

// Named `…Response`, not `CustomerDetail`, because `CustomerDetail` is the
// COMPONENT in components/CustomerDetail.tsx. The shipped pair avoids exactly
// this: the component is `BookingDetail` and the wire type is
// `OwnerBookingDetail` (api.ts:311 vs BookingDetail.tsx:6). Under the
// workspace's `isolatedModules: true` (tsconfig.base.json:10) a colliding
// value import is a hard error — TS2865 — and any file needing both names at
// once cannot import them at all. The backend model stays `CustomerDetail`;
// there is no component in Python to collide with.
export interface CustomerDetailResponse {
  id: string;
  name: string;
  phone: string;
  notes: string | null;
  tags: string[];
  bookings: CustomerBookingRow[];
  messages: SmsLogRow[];
  messages_total: number;
}

export interface UpdateCustomerRequest {
  notes?: string;
  tags?: string[];
}

export interface CustomerListQuery {
  q: string;
  offset: number;
  limit: number;
}
```

`UpdateCustomerRequest`'s fields are **optional, not nullable** — an omitted key is "unchanged" on the wire, and the client must never send `null` for a field it did not touch.

### API-client methods

Inserted after `listManageSlots` closes at `api.ts:656`, with a `customerPath` helper beside `staffPath` (`:411-413`). Object-literal shorthand, not `async`, one line each.

```ts
function customerPath(customerId: string): string {
  return `/manage/customers/${encodeURIComponent(customerId)}`;
}

listCustomers(query: CustomerListQuery): Promise<CustomerListResponse> {
  const params = new URLSearchParams({
    offset: String(query.offset),
    limit: String(query.limit),
  });
  // Omitted rather than sent empty: a blank box means "everyone", and the
  // server drops a whitespace-only term anyway — sending `q=` would make the
  // two spellings of one intent visible in the access log for no gain.
  if (query.q.trim() !== "") {
    params.set("q", query.q.trim());
  }
  return apiFetch(`/manage/customers?${params.toString()}`);
},

getCustomer(customerId: string): Promise<CustomerDetailResponse> {
  return apiFetch(customerPath(customerId));
},

// Partial by design — an omitted key means "unchanged", and the server reads an
// all-unchanged patch as a no-op that writes no audit row. The response is the
// WHOLE detail, panels included, so the caller can replace state with it.
updateCustomer(
  customerId: string,
  body: UpdateCustomerRequest,
): Promise<CustomerDetailResponse> {
  return apiFetch(customerPath(customerId), { method: "PATCH", body });
},
```

The conditional-`q` branch is `listDresses`'s shipped shape (`api.ts:549-559`).

### `CustomersSection.tsx` — layout and state

State, the `BookingsSection` shape: `term: string` (the raw input value), `rows: CustomerRow[] | null` (**null = not yet loaded, never `[]` on failure**), `total: number`, `loadError: string | null`, `selectedId: string | null`. `loading` is **derived**, never stored: `rows === null && loadError === null`.

Layout, top to bottom inside `<div className="space-y-6">`:

1. `<h2 className="text-lg font-semibold text-ink">{t("customers.heading")}</h2>` — the `BookingsSection.tsx:86` shape.
2. A `Card` holding one `Input` — `label={t("customers.searchLabel")}`, `placeholder`, `className="max-w-[320px]"`, **`maxLength={MAX_SEARCH_TERM_LENGTH}`**, `dir` **unset** (the term is usually Hebrew; `dir="ltr"` on Hebrew free text is itself a bidi defect, `BookingsSection.tsx:157-158`). This is where `DateField` sits in `BookingsSection`.

   **`maxLength` here is the mirror that makes the "no client-produced `VALIDATION_ERROR`" claim true.** `MAX_SEARCH_TERM_LENGTH = 80` is enforced at the router as `Query(max_length=…)` and the API test asserts a 200-character `q` answers 400 — so without a client bound, a pasted over-long term 400s, the catch sets `loadError`, and the list renders `customers.loadFailed`: «לא ניתן לטעון את רשימת הלקוחות כרגע. אפשר לנסות שוב בעוד רגע.» An "it'll be fine in a moment" message for an input error that will fail identically on every retry until she deletes characters she has no reason to suspect. The constant is therefore also mirrored into `validation.ts` and into the fourth `MIRRORS` param — belt and braces, the same pair the notes `TextArea` already gets.
3. `<p role="status" tabIndex={-1} data-testid="customers-count" className="text-sm text-ink-muted">` — the section's **single announced region**, carrying the loading text, the count, and the post-back focus destination. `isolateLtr(t("customers.count", { count: total }), String(total))`.
4. A muted `<p role="alert" className="text-sm text-ink-muted">` for a load failure — the **outage** register, never `text-danger`, and **no retry control** (editing the search box refetches).
5. `{loading && <Skeleton variant="text" lines={4} />}` — `variant="text"`, never the default `"block"`, which renders `h-full w-full` and collapses to zero height in a parent with no intrinsic height.
6. A `Card` holding either `<EmptyState/>` or a `<ul className="divide-y divide-border">`. **Two different empty states**: `term === ""` → `customers.emptyTitle` / `customers.emptyBody` ("no customers yet"); `term !== ""` → `customers.noResultsTitle` / `customers.noResultsBody` ("nothing matched"). Collapsing them would tell a boutique with 200 customers that it has none.
7. Each row is **one** affordance — a full-width `<button type="button" className="flex w-full items-start gap-3 py-4 text-start">` opening the detail. `py-4 + text-base` clears the 44px target with no `min-h` literal. Inside: `<bdi className="font-semibold text-ink">{row.name}</bdi>` (bare `bdi`), `<bdi dir="ltr">{row.phone}</bdi>` (a numeric run), and **every** tag as a `Badge variant="neutral"` in a `flex flex-wrap` row.

   **No truncation, no `+N` token.** `MAX_TAGS = 10` already bounds the set and the row wraps, so rendering all of them deletes three problems at once: a piece of rendered user-visible text with **no copy-deck key** (the deck claims to be the only place the strings exist, D11), a bidi case D11 explicitly names as the hazard — a digit run adjacent to a `+`, sitting between Hebrew chips — and the truncation rule itself. If truncation is ever wanted back it costs `customers.tagsMore` = «ועוד {{count}}» rendered through `isolateLtr` in a `ReactNode` slot; it is not wanted now.

The `Card`'s baked-in `p-6` is **not** overridden — `cn()` is a plain join with no conflict resolution, so a consumer `p-0` and `p-6` are same-specificity rules and `.p-0` is emitted first, making the override silently inert (`BookingsSection.tsx:134-136`).

**Debounce.** The fetch effect depends on `[term]` and opens with `const handle = setTimeout(() => { … }, SEARCH_DEBOUNCE_MS)`; the cleanup clears it **and** sets `cancelled = true`. `SEARCH_DEBOUNCE_MS = 300`. A five-key burst therefore fires exactly one request, which the vitest suite pins with fake timers.

**The detail swap** is an early `return <CustomerDetail customerId={selectedId} onBack={() => setSelectedId(null)} onCustomerChanged={next => …}/>` before the list JSX. `onCustomerChanged` patches the matching row from the response — `setRows(current => current?.map(r => r.id === next.id ? { ...r, tags: next.tags } : r) ?? current)` — and **never refetches**, because neither mutable field can change list membership or the `name, id` order (D10).

### `CustomerDetail.tsx` — layout and state

Props are exactly `{ customerId, onBack, onCustomerChanged }` — the `BookingDetailProps` shape (`BookingDetail.tsx:11-15`).

State: `detail: CustomerDetailResponse | null`, `loadError: string | null`, `notesDraft: string`, `tagDraft: string`, `fieldError: string | null` (client-side, rendered in the offending control's own `error` slot), `saveError: string | null` (server-side, the shared alert), `saving: boolean`. `loading` is **derived**, never stored: `detail === null && loadError === null`. Refs: `headingRef` on the `<h2>`, focused on mount keyed by `customerId` — *"the owner hears where she landed"* (`BookingDetail.tsx:91-93`); `saveAlertRef` on the save alert.

Layout:

0. **The null branch, and it is part of the layout rather than an afterthought.** Items 1 and 2 render **unconditionally** — the back `Button` and the `<h2>` — so there is always a way out of a failed load, and the heading focus on mount has something to land on. `detail.name` is guarded: the heading renders `t("customers.detailLoading")`'s subject only through the status region below, and the `<bdi>` is `{detail?.name ?? ""}`. Beneath them, in this order:
   - `<p role="status" tabIndex={-1} className="text-sm text-ink-muted">` — the detail view's **single announced region**, carrying `customers.detailLoading` while loading and empty once loaded. (One `role="status"` per view is the a11y rule; this is the detail's.)
   - `{loading && <Skeleton variant="text" lines={6} />}` — `variant="text"`, never the default `"block"`, for the reason item 5 of `CustomersSection` gives.
   - a muted `<p role="alert" className="text-sm text-ink-muted">` carrying `customers.notFound` for a `NOT_FOUND` and `customers.detailFailed` for anything else — the **outage** register, never `text-danger`, and no retry control.
   - items 3-6 are suppressed entirely while `detail === null`.

   This is `BookingDetail.tsx:219-242`'s shape, which renders heading, `role="status"` region and the muted `role="alert"` outage line around exactly this case. Without it, `customers.detailLoading` and `customers.detailFailed` are two deck keys with no render site, and two builders produce visibly different screens — one of them with no way back from a 404. `CustomersSection.test.tsx` asserts the loading string and the not-found string, and that the back `Button` is present in both.
1. A ghost `Button` — `{t("customers.back")}` — calling `onBack`.
2. `<h2 ref={headingRef} tabIndex={-1} className="font-display text-xl text-ink"><bdi>{detail?.name ?? ""}</bdi></h2>`. The name is the heading; a bare `<bdi>`, never `dir="ltr"`. (`SectionHeading` exports no `ref` and therefore cannot be a focus destination — `StaffSection.tsx:209-211` is the precedent for the raw `<h2>`.)
3. A `Fact`-style row for the phone: muted label `customers.phoneLabel`, value `<bdi dir="ltr">{detail.phone}</bdi>`. `Fact` and `Instant` are local un-exported helpers in this file, the `BookingDetail.tsx:22-38` shape — **not** imported from `BookingDetail`, which would close the list→detail import chain into a cycle (`lib/booking.tsx:1-5`).
4. **Card: notes + tags**, the only mutable region.
   - `<TextArea label={t("customers.notesLabel")} help={t("customers.notesHelp")} showCount maxLength={MAX_CUSTOMER_NOTES_LENGTH} rows={5} value={notesDraft} error={…}/>`. `showCount` + `maxLength` renders the `<bdi dir="ltr">used / max</bdi>` counter and wires it through `aria-describedby` — no key needed.
   - Below it, the tag editor: an `<Input label={t("customers.tagAddLabel")} help={t("customers.tagsHelp", { max: MAX_TAGS, length: MAX_TAG_LENGTH })}/>` with a secondary `Button` `{t("customers.tagAdd")}` beside it, and the chips **above** the input as a `flex flex-wrap gap-2` of `Badge variant="neutral"` each carrying a small ghost `<button aria-label={t("customers.tagRemoveAria", { tag })}>` whose visible text is `{t("customers.tagRemove")}`. The aria-label **starts with** the visible label — WCAG 2.5.3, and `i18n.test.ts` asserts it with `new RegExp('^' + t(visible))`, the F34 template (`:221-230`).
   - One primary `Button` `{t("customers.save")}` with `loading={saving}`.
   - The save alert: `<p ref={saveAlertRef} role="alert" tabIndex={-1} className="text-sm text-danger">` — the **fix-this** register, because a rejected save is something she can correct, unlike an outage. **`tabIndex={-1}` is load-bearing and is the whole reason the focus move works**: a `<p>` is not focusable, so `saveAlertRef.current?.focus()` on a plain paragraph is a silent no-op that leaves focus on the re-enabled Save button or drops it to `<body>` — a bug axe cannot see, and one this repo has already shipped and fixed. The shipped alert carries it: `BookingDetail.tsx:424-426` is `role="alert" tabIndex={-1} ref={actionAlertRef}`, and `:103-115` records what the missing case cost — focus *"sat on `<body>`: the next Tab restarted at the skip link (WCAG 2.4.3)"*.
5. **Card: booking history.** `<h3>{t("customers.bookingsHeading")}</h3>`, then a `<ul className="divide-y divide-border">` of rows: `<Instant value={b.starts_at}/>` (`d.m.yyyy · HH:MM`, both Jerusalem, one `<bdi dir="ltr">` per numeric run), the `appointment_type_name`, and a `Badge` from **`statusBadge(b.status)`** — reused verbatim from `lib/booking.tsx:22`, never re-declared, because *"a second spelling of «בוטל» in one console is a defect"* (`he.ts:456-457`). Empty → one muted line. At exactly `BOOKING_HISTORY_LIMIT` rows, `customers.bookingsTruncated` below the list.
6. **Card: the SMS log.** `<h3>{t("customers.messagesHeading")}</h3>` — «יומן הודעות» — with `customers.messagesHelp` beneath it stating in one line that the log is read-only. Rows: `<Instant value={m.created_at}/>`, the Hebrew for `kind`, a `Badge` for `status` (`sent → neutral`, `queued → muted`, `failed → danger`), and the `body` as `<p className="text-sm text-ink"><bdi>{m.body}</bdi></p>`. **No control of any kind on a log row** — no resend, no delete, no expand. Empty → one muted line; when `detail.messages_total > detail.messages.length`, `customers.messagesTruncated` with **both** numbers, `{ count: messages.length, total: messages_total }`, so the send volume stays readable even when the window truncated (D3).

**Colour never carries the state alone**: the Hebrew word is inside the `Badge` and the variant is redundant reinforcement — the `lib/booking.tsx:10-14` rule.

### UI behaviour

| Trigger | Behaviour |
|---|---|
| Typing in the search box | 300 ms debounce, then one `listCustomers` with the trimmed term. A whitespace-only term is sent as no `q` at all. |
| Clearing the search box | Same path — the list returns to everyone, `total` updates, the announced region re-reads. |
| Clicking a row | `setSelectedId(row.id)`; the section swaps to the detail and the detail focuses its heading. |
| «חזרה לרשימה» | `onBack()` → `setSelectedId(null)`. The list state was never unmounted, so no refetch fires. **Focus is moved explicitly, not hoped for**: `CustomersSection` holds `countRef` on its `role="status"` paragraph and `returningRef` (a `useRef(false)` set true by `onBack`), and runs `useEffect(() => { if (selectedId === null && returningRef.current) { returningRef.current = false; countRef.current?.focus(); } }, [selectedId])`. Without the effect, `CustomerDetail` unmounts with focus on its `<h2>` and focus goes to `<body>` — the next Tab restarts at the skip link, WCAG 2.4.3, the failure `BookingDetail.tsx:103-115` already records. The paragraph carries `tabIndex={-1}`, which is why it can receive focus at all. |
| Typing in notes | Local draft only. `maxLength={MAX_CUSTOMER_NOTES_LENGTH}` caps at the control; the length message is a belt-and-braces case for paste. |
| «הוספה» / Enter in the tag input | `validateTag(draft)` runs client-side: blank → no-op (not an error); over `MAX_TAG_LENGTH` → `customers.tagTooLong` in the input's `error` slot; a control character → `customers.tagInvalid`; a case-insensitive duplicate of an existing chip → `customers.tagDuplicate`; already at `MAX_TAGS` → `customers.tagsFull`. On success the chip is appended **to the end** (order is preserved server-side, D5) and the input clears. |
| «הסרה» on a chip | Removes it from the draft list. Nothing is saved until «שמירה». |
| «שמירה» | **`validateCustomerNotes(notesDraft)` runs first**, and a non-null result renders in the `TextArea`'s own `error` slot (`customers.notesInvalid` for a control character, `customers.notesTooLong` for the cap) and **returns without a request**. Only then the **diff body** — `const body: UpdateCustomerRequest = {}`, `if (notesDraft !== (detail.notes ?? "")) body.notes = notesDraft;`, `if (!sameTags(tagsDraft, detail.tags)) body.tags = tagsDraft;`. If the body is empty, no request fires at all. |
| Save success | `setDetail(updated)`, drafts re-seeded from the response (the **form-state-sync** rule — the server normalizes tags, so the chips can legitimately come back deduped and re-cased), `onCustomerChanged(updated)`, and a `useToast()` success — `toast({ message: t("customers.saved") })`, called as a **function**, not `toast.success(…)` (`ProfileSection.tsx:93-95`). |
| Save failure | `setSaveError(customerErrorText(error, t))`, focus moves to the alert. |
| Any `ApiError` on the detail load | `NOT_FOUND` → `t("customers.notFound")` (a 404 and another tenant's id are indistinguishable by design, `BookingDetail.tsx:76-82`); anything else → `customerErrorText`. |

**The save handler is validate-then-diff, and the two halves have two different citations.** The diff body is `StaffSection.tsx:152-167` verbatim in shape, and the comment there states the reason: *"An all-unchanged patch is a no-op the server answers 200 without writing an audit row, so sending less is not an optimisation — it is what keeps the audit table meaningful."* The **guard in front of it** is `StaffSection.tsx:139-148`'s `validateStaffDraft` — outside that range, which is exactly why it has to be named separately: without it the pattern is not safe. `maxLength` on a `<textarea>` bounds length but does **not** filter control characters, so a note pasted out of Word carrying U+000B reaches the server, raises `CustomerValidationError`, and `customerErrorText` falls through to `errorMessage(error)` — the server's **English** message rendered into a Hebrew console. `StaffSection.tsx:149-151` and `:173-175` state the contract F53 inherits — *"Every other 400 is caught client-side by a mirrored bound"* — and `customers.notesInvalid` («ההערות מכילות תווים שאי אפשר לשמור.») has no other trigger in the whole feature. `CustomersSection.test.tsx` carries the case beside the tag cases: a pasted `\x0b` in the notes renders `customers.notesInvalid` in the `TextArea`'s `error` slot and fires **zero** `updateCustomer` calls. This is the claim F51's 2026-07-30 review found false once; it is only true because the guard runs.

**`customerErrorText(error, t)` lives in `lib/booking.tsx`'s sibling position**, not in either component: `CustomersSection` imports `CustomerDetail` and both need the map, which is exactly the cycle `lib/booking.tsx:1-5` was created to avoid. It maps `NOT_FOUND` and `NOT_AUTHORIZED` to Hebrew and falls through to `errorMessage(error)` for everything else — including `VALIDATION_ERROR`, whose server message is English and which **the client is responsible for never producing**, because every bound the server checks is mirrored and checked first (`validation.ts`). "Every bound" is a closed list and it is worth writing out, because the review that produced this spec found one missing: `MAX_TAG_LENGTH`, `MAX_TAGS`, `MAX_CUSTOMER_NOTES_LENGTH`, **`MAX_SEARCH_TERM_LENGTH`**, and the two control-character classes. All four numerics ride the fourth `MIRRORS` param; the search bound is additionally applied as `maxLength` on the search `Input`. That claim is what the fourth `MIRRORS` param and the parametrized control-char test make true rather than hopeful — F51's 2026-07-30 review found this exact claim false once, when the manage console had no email check.

The map is kept **by hand** and nothing pins it; the comment beside it says so and names the failure mode, the correction F51's review forced onto `StaffSection.tsx:9-22`.

### Accessibility — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

- One `h1` (the shell's, `sr-only`); the section heading is `h2`; the three detail panels are `h3`. No skipped levels, asserted in the vitest suite.
- One `role="status"` region per view; `role="alert"` for errors, muted for outages and `text-danger` for fixable ones.
- 44×44 minimum targets via `py-4 + text-base`, no `min-h` literals. Visible focus ring from `focusRing`.
- Every `Input` / `TextArea` carries a real `<label>`; the chip remove buttons carry `aria-label` starting with their visible label.
- **Bidi**: bare `<bdi>` around names, tags and message bodies; `<bdi dir="ltr">` around phones, dates and times. `dir="ltr"` on Hebrew free text is itself a defect.
- Content capped at 720px, which is why the history and the log are rows and not tables.
- An `axe-core` pass in `CustomersSection.test.tsx`, rendered through the `renderInShell` frame so the `<h1>` heading order is real, with the 20 000 ms per-test timeout the shipped suites use.

---

## Hebrew copy deck

Flat dotted keys. `ar.ts` carries this key set with **these exact values** (2026-07-31 LANGUAGES ruling). Zero exclamation marks. No value contains `נשלח`, `תישלח` or `בדרך`. `HE_F53` floor: **`toBeGreaterThanOrEqual(48)`** — three rows of headroom under the 51 the deck ships.

| Key | Hebrew | Notes |
|---|---|---|
| `nav.customers` | לקוחות | the eleventh nav row, index 8 |
| `customers.heading` | לקוחות | `h2` |
| `customers.searchLabel` | חיפוש לפי שם או טלפון | visible `<label>` |
| `customers.searchPlaceholder` | שם או מספר טלפון | |
| `customers.listLoading` | טוען את רשימת הלקוחות… | in the `role="status"` region |
| `customers.count` | לקוחות ברשימה: {{count}} | base key only — no `_one`/`_other`, the `booking.dayCount` shape |
| `customers.loadFailed` | לא ניתן לטעון את רשימת הלקוחות כרגע. אפשר לנסות שוב בעוד רגע. | outage register |
| `customers.emptyTitle` | אין עדיין לקוחות | `term === ""` |
| `customers.emptyBody` | לקוחה נוספת לרשימה אחרי שהיא מאמתת את מספר הטלפון שלה וקובעת תור. | states the actual mechanism |
| `customers.noResultsTitle` | אין תוצאות לחיפוש הזה | `term !== ""` |
| `customers.noResultsBody` | אפשר לנסות שם חלקי או ספרות מתוך מספר הטלפון. | |
| `customers.back` | חזרה לרשימה | |
| `customers.detailLoading` | טוען את פרטי הלקוחה… | |
| `customers.detailFailed` | לא ניתן לטעון את פרטי הלקוחה כרגע. | outage register |
| `customers.notFound` | הלקוחה הזו לא נמצאה. ייתכן שהכרטיס הוסר. | also the `NOT_FOUND` map target |
| `customers.phoneLabel` | טלפון | |
| `customers.notesLabel` | הערות | |
| `customers.notesHelp` | ההערות נשמרות בכרטיס ונראות לצוות הבוטיק בלבד. | the one honest thing to say about who reads them |
| `customers.notesPlaceholder` | מה כדאי לזכור לפעם הבאה | |
| `customers.notesTooLong` | ההערות יכולות להכיל עד {{length}} תווים. | number mid-sentence |
| `customers.notesInvalid` | ההערות מכילות תווים שאי אפשר לשמור. | |
| `customers.tagsLabel` | תגיות | |
| `customers.tagsHelp` | עד {{max}} תגיות, עד {{length}} תווים לתגית. | both numbers bounded by Hebrew |
| `customers.tagAddLabel` | תגית חדשה | visible `<label>` |
| `customers.tagAdd` | הוספה | |
| `customers.tagRemove` | הסרה | visible label on the chip button |
| `customers.tagRemoveAria` | הסרה של התגית {{tag}} | **starts with** `customers.tagRemove` — WCAG 2.5.3 |
| `customers.tagsEmpty` | אין תגיות בכרטיס הזה. | |
| `customers.tagsFull` | אי אפשר להוסיף עוד תגיות. אפשר להסיר תגית קיימת ולנסות שוב. | names the remedy |
| `customers.tagTooLong` | תגית יכולה להכיל עד {{length}} תווים. | |
| `customers.tagDuplicate` | התגית הזו כבר קיימת בכרטיס. | |
| `customers.tagInvalid` | התגית מכילה תווים שאי אפשר לשמור. | |
| `customers.save` | שמירה | |
| `customers.saved` | השינויים נשמרו | toast |
| `customers.saveFailed` | לא ניתן לשמור את השינויים כרגע. | fix-this register |
| `customers.bookingsHeading` | היסטוריית תורים | `h3` |
| `customers.bookingsEmpty` | אין עדיין תורים בכרטיס הזה. | |
| `customers.bookingsTruncated` | מוצגים {{count}} התורים האחרונים. | |
| `customers.messagesHeading` | **יומן הודעות** | D11 — the rejected alternative is named there, not here, so this table can be scraped verbatim |
| `customers.messagesHelp` | יומן לקריאה בלבד. אי אפשר לערוך או למחוק רשומה. | states the read-only contract |
| `customers.messagesEmpty` | אין עדיין רשומות ביומן ההודעות. | |
| `customers.messagesTruncated` | מוצגות {{count}} מתוך {{total}} רשומות ביומן. | **two** numbers, both mid-sentence and bounded by Hebrew on either side, so neither is isolated (D11). `{{total}}` is `messages_total` — the send volume the 50-row window cannot show (D3) |
| `customers.messageKindOtp` | קוד אימות | `kind = 'otp'` |
| `customers.messageKindConfirmation` | אישור תור | `kind = 'confirmation'` |
| `customers.messageKindReminder` | תזכורת | `kind = 'reminder'` |
| `customers.messageKindOwnerCancel` | ביטול מטעם הבוטיק | `kind = 'owner_cancel'` |
| `customers.messageKindOwnerReschedule` | שינוי מועד מטעם הבוטיק | `kind = 'owner_reschedule'` |
| `customers.messageStatusQueued` | בהמתנה | `status = 'queued'` |
| `customers.messageStatusSent` | הועברה לספק | `status = 'sent'` — **the accurate claim**, and it carries no banned root. `sent` means the provider accepted it, not that a handset received it |
| `customers.messageStatusFailed` | נכשלה | `status = 'failed'` — the row the log exists to be able to show |
| `customers.error.NOT_AUTHORIZED` | אין הרשאה לצפות בכרטיסי הלקוחות כרגע. לבירור אפשר לפנות לבעלת הבוטיק. | names no role and nothing that changed — the server ships **one** 403 body so a probe cannot learn which roles exist (`main.py:143-144`). «כרגע» is load-bearing: a re-promotion restores access, so a sentence implying a permanent door would be a guess the server never made. The F34 `board.accessEnded` rules, applied |

An unknown `kind` or `status` from a backend that grew a sixth value renders the **raw value** rather than a blank — the `statusBadge` fallback shape (`lib/booking.tsx:22-26`).

---

## Test plan

Tests marked `db` run **only on CI** — there is no Docker locally, so both `db` modules below are first exercised on the CI runner. `make test` is `-m "not db"` and passing it proves nothing about them. **None of F53's tests are `s3`-marked.** `make lint` runs `mypy app tests` under `disallow_untyped_defs = true`, so **every test function needs `-> None`** and every fake needs full annotations including `__init__`. Ruff `line-length = 100`, and `select` includes `SIM` — write `normalize_tags`'s guards as combined conditions rather than nested `if`s, or the linter will rewrite them for you.

### `Backend/tests/test_customers_validation.py` — fast, no marker

The module that carries the feature's definitions. Pure functions, no app, no database.

- `normalize_tags`: whitespace trimmed; empty elements dropped; **first occurrence wins and keeps its casing** (`["VIP", "vip", " Vip "]` → `["VIP"]`); **order preserved, never sorted** (asserted against an input whose sorted order differs); **cap applied after dedup** (eleven inputs of which two are duplicates yield ten, and the eleventh distinct tag is present — this red-fails if the cap runs first); over-length rejected; each of `\x00`, `\x0b`, `\t`, `\n`, `\r` rejected — **the `\t\n\r` cases are the ones that fail if the wrong regex was imported** (correction C1).
- `validate_notes`: at the cap passes, one over fails; `\n` and `\t` **pass** (`_CONTROL_CHARS_EXCEPT_WS`); `\x0b` fails; `""` passes and means cleared.
- Every raised error is a `CustomerValidationError` and therefore a `DomainValidationError`; message text matches the house register (lowercase, field first, no trailing period).
- `q` handling: `"  "` normalizes to absent, `" מיכל "` to `"מיכל"`.
- **`phone_search_term`** (D2): `"0501234567" → "972501234567"`, `"050-123-4567" → "972501234567"`, `"050" → "97250"`, `"972501234567" → "972501234567"`, `"מיכל" → None`, `"" → None`. The `None` cases are what keep the phone leg off a pure-Hebrew term.

### `Backend/tests/test_customers_service.py` — fast, fakes

Duck-typed fake repositories; no database, no app.

- **The no-op rule**: a `PATCH` whose `notes` and `tags` both match what is stored performs **no `UPDATE`** and writes **no audit row**, and answers 200 with the unchanged detail. A `PATCH` that moves only `tags` writes one row with `details == {"fields": ["tags"]}`; one that moves both writes one row with `{"fields": ["notes", "tags"]}` — **sorted**.
- `entity == str(customer_id)`; `actor_id == actor.id`; `action == AuditAction.CUSTOMER_UPDATED`.
- **The value walk**: with `notes = "מגיעה עם אמא"` and `tags = ["VIP-סודי"]`, `repr([row.details for row in audit_rows])` contains **neither** string, and contains neither the customer's `name` nor her `phone`. The shape is `test_staff_management_db.py:604-606`'s (`repr(...)` + `not in`) — noted because that precedent lives in a **`db`** module and no value walk exists in any fast module today, so this is a new act rather than a borrowed one.
- **The `PATCH` returns a fully-built detail** (D6): a patch that moves `tags` answers a `CustomerDetail` whose `bookings` and `messages` are the same **non-empty** lists the fake repositories hold and whose `messages_total` is the fake's count — and the same on the no-op path. This is the assertion that fails if `update()` builds its response from the `customers` row alone, which would blank both panels the moment the owner pressed «שמירה».
- Tag normalization is applied **before** the diff, so `["vip"]` against a stored `["VIP"]` is a no-op rather than a write.
- An unknown / soft-deleted / foreign `customer_id` raises `CustomerNotFoundError`, and the repository stub is asserted never to have been called for the update.

### `Backend/tests/test_customers_api.py` — fast, fake service

The `test_dashboard_api.py` template: duck-typed `FakeCustomersService` on `app.state.customers_service`, `FakeAuthService` whose `StaffContext.tenant_id` **deliberately disagrees** with the host-resolved `TENANT.id`, `dependency_overrides[get_auth_service]` only, `TestClient(app, base_url="http://bella.localtest.me")` with the `boutique_session` cookie set on that domain. Every test is a **sync `def`** — `asyncio_mode = "auto"` would give an async test its own loop and `TestClient` starts a second inside it.

```python
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/manage/customers", None),
    ("GET", f"/manage/customers/{CUSTOMER_ID}", None),
    ("PATCH", f"/manage/customers/{CUSTOMER_ID}", {"notes": "x"}),
]
```

- `test_every_route_requires_authentication` — 401 `NOT_AUTHENTICATED` on all three, and the fake records **zero** calls (the guard fires before any service call).
- `test_every_route_is_wired_and_reaches_the_service` — 200 on all three. **This table is the shadowing guard for the eighth `/manage` router** (ninth once F57 merges — §What already exists to build on has the count); a 404 here is what catches a duplicated `(method, path)`. The ordinal lives in `main.py`'s include comment and in this docstring only, and the two must agree.
- Both roles get 200 on all three (parametrized over `OWNER` / `SHIFT_MANAGER`).
- An out-of-enum role gets **exactly** `NOT_AUTHORIZED_BODY` with 403, and the fake records zero calls (the gate raises during dependency solving).
- `cache-control: no-store` on all three, parametrized over `ROUTES`.
- **The tenant comes from the HOST** — `FakeCustomersService` records the `tenant_id` it was called with; the test asserts `== TENANT.id`. This is the only place the trust path is observable; the `db` isolation test runs below the router.
- **400, not 422** (correction C2): `limit=0`, `limit=201`, `offset=-1`, `offset=1_000_001`, a 200-character `q`, an unknown body key, and a non-UUID path segment each answer **400** with `{"error": {"code": "VALIDATION_ERROR", "message": …}}`.
- **`CSRF_ORIGIN_MISMATCH`**: a `PATCH` with a mismatched `Origin` is 403 with that code. The dashboard module's GET-is-allowed inverse (`test_dashboard_api.py:343-352`) must **not** be copied.
- `SPEC_ERROR_CODES = {"NOT_AUTHENTICATED", "NOT_AUTHORIZED", "VALIDATION_ERROR", "NOT_FOUND", "CSRF_ORIGIN_MISMATCH"}`, re-derived from live responses in `test_every_spec_error_code_is_asserted`.
- **`set(SmsLogRow.model_fields) == {"id", "created_at", "kind", "status", "body"}`** — an equality, not a subset. This is the assertion that fails if someone adds `provider_message_id` or `error` "for debugging".
- **The disclosure walk, keys and values, against a fully populated fake.** `_all_keys` is reused verbatim (`test_dashboard_api.py:107-115`); the forbidden set is F53's own, because F52's contains `phone`, `notes`, `customer_name` and `customer_id` — all four of which F53 legitimately ships:

  ```python
  CUSTOMER_FORBIDDEN_KEYS = frozenset(
      {"provider_message_id", "error", "manage_token_hash", "password_hash",
       "tenant_id", "booking_id", "deleted_at", "dress_name", "dress_size",
       "seat_index", "email"}
  )
  ```

  **The fake response must be fully populated** (non-empty `items`, `tags`, `bookings`, `messages`), with the anti-vacuity assertion beside the walk, because a key that never appears cannot leak.

  **There is no value half in this module, and that is a correction rather than an omission.** An earlier draft put one here — sentinel `provider_message_id` / `error` strings asserted absent from `resp.text` — and called it the assertion that catches a rename to `sid`. It cannot be. The handler's contract is its return annotation, FastAPI serializes the returned object against it, and `SmsLogRow` has no slot for either field, so a sentinel is unreachable through a duck-typed fake behind `-> CustomerDetail`: the assertion passes vacuously today, and it would still pass after a rename to `sid`, because the fake is written against today's five fields and never sets `sid`. What actually catches a rename is **`set(SmsLogRow.model_fields) == {"id", "created_at", "kind", "status", "body"}`** — the equality above, which must **not** be relaxed to a subset — plus `"provider_message_id" not in _all_keys(...)`. The precedent this walk borrows from is key-based for exactly this reason (`test_dashboard_api.py:107-115` walks a fully-populated `DashboardResponse` built by `_response()` at `:117-127`): it catches a new **field on the schema**, not a value the schema has no slot for. The value walk is moved to where a real `MessageLog` row actually crosses the mapping boundary — one assertion in `test_customers_db.py`, below.

### `Backend/tests/test_customers_db.py` — **`db`, CI debut**

`pytestmark = pytest.mark.db` at module level. `app_role_url` fixture, **never** the superuser (the container superuser bypasses RLS unconditionally and would make every isolation assertion vacuously pass). `create_async_engine(url, poolclass=NullPool)` in `try/finally: await engine.dispose()`. Every test mints its own tenant id — the container is session-scoped and nothing truncates.

**Search:**
- matches on `name`, with a literal name term;
- **matches a customer stored as `+972501234567` from `q="0501234567"`, from `q="050-123-4567"` and from `q="050"`** — the digit-normalization leg (D2). These are the rows that red-fail if the phone leg runs on the raw term, and picking a term that happens to be a substring of the stored E.164 is how that bug otherwise stays green;
- a Hebrew term matches a Hebrew name (this is what catches an accidental `lower()`/collation assumption);
- a term containing a literal `%` and one containing a literal `_` each match **only** the customers whose value actually contains that character — **the `autoescape=True` assertion** (D2);
- a soft-deleted customer never appears, in the page or in `total`;
- `total` is the count under the search predicate, not the tenant total;
- order is stable under `OFFSET`: two customers with the identical `name`, paged one at a time, yield two distinct ids across the two pages.

**SMS log:**
- a lifecycle row with `booking_id` set surfaces on its customer's detail **after her phone has been corrected** — i.e. the booking leg, not the phone, is what attributes it;
- the phone leg matches **only** rows with `booking_id IS NULL`;
- **the recycled-phone case, the headline**: customer A holds phone X with two lifecycle rows; A's phone is corrected to Y via `set_phone`; customer B is created on phone X; **B's detail contains none of A's rows**, and A's detail still contains both. This is the test that fails if `AND booking_id IS NULL` is dropped, and it is the reason this module exists;
- an OTP row (no `booking_id`, phone match) **is** included;
- **the under-report, characterised rather than discovered**: an OTP row written to phone X, then `set_phone` to Y, no longer appears on that customer's log — and the test says in one comment that this is Risk 1's second direction and is accepted, not a bug to be fixed here;
- a customer with fifty-one rows gets fifty, newest first, **and `messages_total` reads 51** — the rows are constructed as `MessageLog(...)` with explicit, distinct `created_at` values, **not** through `MessageLogRepository.insert`, which exposes no `created_at` and would give all fifty-one the same `transaction_timestamp()` and make both assertions coin flips (D3);
- a soft-deleted log row is excluded, and is excluded from `messages_total` too;
- **the non-disclosure value walk, here rather than in the API module**: a `MessageLog` row written with a sentinel `provider_message_id` and a sentinel `error` string yields an `SmsLogRow` whose `model_dump()` contains neither string. This is the one place a real row crosses the mapping boundary, so it is the only place the assertion is not vacuous;
- **tenant isolation, two assertions and the second is the one the plan could not see**:
  - tenant B's detail read for tenant A's `customer_id` raises `CustomerNotFoundError`, asserted **together with tenant A's own read returning non-empty panels in the same test** — an all-empty pass is exactly what a missing `tenant_session` produces and would otherwise read as green;
  - **two tenants, one shared phone**: tenant A and tenant B each hold a customer on `+972501234567` (`0008_bookings.py:41-44` designs this in — *"The SAME phone under two tenants is two customers, deliberately"*), each with `booking_id IS NULL` log rows. Tenant B's detail contains **none** of tenant A's rows, and `messages_total` counts only B's. Run under `app_role_url` for RLS, and **paired with a compiled-statement assertion** — `str(stmt.compile())` contains `message_log.tenant_id`, or the equivalent — so the defense-in-depth predicate is pinned independently of the DB role. Without that second half, the explicit `tenant_id` filter can be dropped and every suite stays green: the fast modules issue no SQL, and this module runs where RLS masks the omission (D3).

**Notes and tags:**
- `tags` round-trips as `list[str]` through the ORM; the default on an untouched row reads `[]`, never `None`;
- clearing with `[]` and `""` writes `'{}'` and `''`, and both read back as such.

### `Backend/tests/test_migrations.py` — **`db`, CI debut**, appended block

Appended **between line 499 and line 502** — after `test_migration_0014_round_trips` and before `test_running_env_py_does_not_disable_the_app_logger`, which the file's ordering convention keeps terminal. Section banner `# --- NNNN: the customer CRM columns ---`.

`_customer_crm_columns(url)` is `_check_in_column`'s shape (`:416-426`), returning `(data_type, is_nullable, column_default, udt_name)` per column from `information_schema.columns`. **The `udt_name` element is not padding**: `data_type` returns the bare string `'ARRAY'` for any array column, so `text[]` and `int[]` are indistinguishable without `udt_name == '_text'`. Asserted:

| Column | `data_type` | `is_nullable` | `column_default` | `udt_name` |
|---|---|---|---|---|
| `notes` | `text` | `YES` | `None` | `text` |
| `tags` | `ARRAY` | `NO` | `'{}'::text[]` | `_text` |

`test_migration_00NN_round_trips` follows `0014`'s verbatim, with `command.downgrade(cfg, "-1")` instead of a hardcoded target (D12) and the mandatory `finally: command.upgrade(cfg, "head")`.

`test_every_tenant_id_table_has_forced_rls` in `test_tenant_isolation.py` **is not edited**. Its staying green is the assertion.

### Frontend (vitest, `apps/manage/src/__tests__/`)

Run under `TZ=America/New_York` (`package.json:11`), which is what gives every Jerusalem assertion bite. `globals: false`, so every `describe`/`it`/`expect`/`vi` is imported explicitly. `vi.mock("../api", …)` with `vi.importActual` re-exporting the **real** `ApiError` and `errorMessage` so `instanceof` works in the component under test.

**`CustomersSection.test.tsx`** (new): loading skeleton and the announced loading string; the outage alert with **no stacked empty state** (the catch sets only `loadError`); a populated list; the **two distinct empty states** (no customers vs no results); **a five-keystroke burst fires exactly one `listCustomers`** (fake timers, then `expect(listCustomers).toHaveBeenCalledTimes(1)` with the final term); list → detail → back; the notes round-trip patching from the response; tag add / remove / duplicate / over-length / client cap each rendering their own Hebrew in the right slot; **a `status = 'failed'` row reads as נכשלה** and carries a `danger` badge; the `NOT_FOUND` and `NOT_AUTHORIZED` maps; a bare `<bdi>` on the name and `<bdi dir="ltr">` on the phone; exactly one `H2` with no skipped levels; and an `axe-core` pass through `renderInShell` with the 20 000 ms timeout. Plus the five cases this spec's review added, each of which pins something no other assertion reaches:

1. **The detail's own null branch**: while the detail load is pending, `customers.detailLoading` is announced and the back `Button` is already present; on a `NOT_FOUND`, `customers.notFound` renders in the muted alert and the back `Button` is **still** present — the only way out of a 404.
2. **`document.activeElement` is the save alert after a failed save.** This red-fails if `tabIndex={-1}` is missing from the `<p>`, which is the whole point of asserting it rather than trusting the `.focus()` call.
3. **`document.activeElement` is `[data-testid="customers-count"]` after «חזרה לרשימה».** Pins the explicit back-focus effect; without it focus is on `<body>` and the assertion fails.
4. **A pasted control character in notes** renders `customers.notesInvalid` in the `TextArea`'s `error` slot and fires **zero** `updateCustomer` calls.
5. **A pasted over-80-character search term** is truncated by `maxLength` and never produces a request the server would 400.

**`Nav.test.tsx`** — five coupled edits, all in the same commit as the `App.tsx` change:
1. `listCustomers: pending` into the `vi.mock` factory (`:20-33`) — without it **every** nav test red-fails on mount with `TypeError: api.listCustomers is not a function`, an error that names the nav rather than the customers section. The comment at `:27-30` records exactly this failure for `getDashboard`.
2. `"לקוחות"` into `NAV_LABELS` at index 8, between `"לוח היום"` and `"צוות"`.
3. Both `NAV_LABELS.slice(0, 8)` (`:95`, `:148`) → `slice(0, 9)`.
4. Both test names — "all ten sections" → eleven, "eight sections" → nine.
5. The `:66-68` comment's `.slice(0, 8)` reference.
Plus one new describe, the `:160-172` template: click «לקוחות», assert the heading and the `role="status"` loading text.

**`i18n.test.ts`** — `const HE_F53 = entries(he.translation, (key) => key === "nav.customers" || key.startsWith("customers."));` **folded into the `HE` spread at `:39`**. Without the fold, the resolve check, both register guards **and** the `ar` parity guard silently skip every F53 key — the file's own comment at `:32-34` records that failure. Own describe: the `>= 48` floor; `nav.customers` resolves to «לקוחות»; `customers.messagesHeading` is **exactly** «יומן הודעות»; every `customers.messageKind*` and `customers.messageStatus*` resolves; `customers.tagRemoveAria` matches `new RegExp('^' + i18n.t("customers.tagRemove"))`; `customers.error.NOT_AUTHORIZED` contains «כרגע» and none of `["אחראית משמרת", "תפקיד", "בוטלו", "הוסרה", "שונה"]`.

**`Backend/tests/test_frontend_constant_parity.py`** — a fourth `MIRRORS` param, `(MANAGE_VALIDATION_TS, customers_validation, ("MAX_TAG_LENGTH", "MAX_TAGS", "MAX_CUSTOMER_NOTES_LENGTH", "MAX_SEARCH_TERM_LENGTH"))` — **four names, not three**: the search bound is the one the client can hit by paste and the only server bound the mirror-everything claim would otherwise leave unmirrored. Plus `test_control_character_classes_match_the_backend` parametrized over `(STOREFRONT_VALIDATION_TS, MANAGE_VALIDATION_TS)` so the manage console's two regex literals are held byte-for-byte against `booking/validation.py`'s (correction C6). Two consequences of parametrizing it, both mechanical: the manage file must declare its regexes **unexported** (`_TS_REGEX_RE` at `:130` matches a line-start bare `const`, and `_CONST_RE` at `:93` matches `export const NAME = <digits>;` — mutually exclusive, §Frontend Changes), and the assertion message at `:148` — currently the hardcoded string `"storefront validation.ts does not declare {ts_name}"` — must name the file under test instead, or a manage failure sends the builder to the wrong file. Both tests read the TS as **text**, so they stay in the fast no-Node suite.

### Not written, and why

- **No `test_customers_isolation.py`.** F53 adds no table; `test_every_tenant_id_table_has_forced_rls` already sweeps both tables it touches, and the cross-tenant cases ride in `test_customers_db.py` beside the queries they protect.
- **`test_staff_role_gating.py` is not edited.** Both walkers derive from the live route table, and adding a both-roles route to `OWNER_ONLY` would report it as `unenforced_owner_only` and go **red** (`dashboard/router.py:15-16`).
- **No e2e spec.** `Frontend/e2e/` holds two storefront specs and **there is no manage-console harness at all** — building one means a login fixture, a seeded tenant and Playwright auth state. That is a capability, not a test, and it belongs to the first console feature with a genuine multi-page flow (F58 is already slated to build it). Recorded rather than quietly skipped.
- **No `packages/ui` test.** Nothing is added to `packages/ui`.

### The manual check no test can make

Run the manage app against a seeded tenant. Open a customer whose phone was corrected and confirm her SMS log shows **her own** lifecycle messages and not the previous holder's. That is D3's whole thesis, and the `db` test proves it in SQL; this proves it end to end through the screen the owner actually reads.

---

## Collision map

Three sibling features are in flight off the same `main` (`877587c`):

| | Branch | State | Migration |
|---|---|---|---|
| **F57** floor-staff-roles | `feature/floor-staff-roles` | 12 commits | `0015_floor_roles.py` |
| **F33** qr-walkin-queue | `feature/qr-walkin-queue` | 0 commits, spec only | 0016 (will add `customers.marketing_opt_in_at`) |
| **F19** deposit-booking-flow | `feature/deposit-booking-flow` | 0 commits | 0017 |

F53 therefore lands **0018**, resolved from `alembic heads` at push time.

| File | F53's edit | Also touched by | Shape |
|---|---|---|---|
| `Backend/app/models/customer.py` | two column lines appended after `name` | **F33** (`marketing_opt_in_at`) | append — union, but only if both append at the same anchor. F33 has zero commits, so F53 will likely land first; **do not assume it** |
| `Backend/app/main.py` | one `app.state.customers_service` line at `:562`, one `include_router` at `:1043-1046`, one import at `:72`ff | **F57** (its own service + router) | append at two seams. F53's include comment says **"the EIGHTH"** on `origin/main` and must be renumbered to **ninth** if F57 lands first |
| `Backend/app/models/constants.py` | one `AuditAction` member in a new block after `:171` | **F57** (`StaffRole`, `:9-15`) | different hunk, ~160 lines apart — clean |
| `Backend/tests/test_migrations.py` | banner + constants + probe + round-trip, appended at line 500 | **F57** (same seam) | two blocks at one seam. `"-1"` is what makes F53's block order-independent, so the resolution is plain concatenation (D12) |
| `Frontend/apps/manage/src/App.tsx` | import after `CatalogSection`; `\| "customers"` after `"bookings"`; NAV row after `board`; render line after the `board` line | **F57** (appends after `TermsSection`, after `"gateway"`, inserts after board) | four one-line inserts at four anchors, all "keep both" |
| `Frontend/apps/manage/src/api.ts` | types before `// --- endpoints ---`, three methods **after `listManageSlots` (`:656`)** | **F57** (appends at the object end) | deliberately different anchors — F53 must **not** append at the end |
| `Frontend/apps/manage/vite.config.ts` | `customers` into the `:19` alternation **and** the `:13-17` prose | **F57** (`floor`, same two hunks) | **two guaranteed conflicts.** Resolution is the union of both segments, alphabetically, and the count words bumped twice. `test_spa_serving.py:397-400` catches a bad resolution — the regex is `[a-z|-]+`, so a segment with a digit or an underscore would not even match |
| `Frontend/apps/manage/src/i18n/{he,ar}.ts` | a banner-delimited block appended before the closing `},` | **F57** (append) | union |
| `Frontend/apps/manage/src/__tests__/i18n.test.ts` | `HE_F53` constant, the `HE` spread at `:39`, a describe | **F57** (the same spread line) | the spread line is one conflict; the resolution is both names |
| `Frontend/apps/manage/src/__tests__/Nav.test.tsx` | mock row, `NAV_LABELS`, two slices, two names, one comment | **F57** (the same three numbers) | **three coupled numeric edits.** Whoever rebases second fixes them by hand. Loud, not silent — the test names contradict the assertions if half-done |
| `Frontend/apps/manage/src/validation.ts` | four **exported** numeric constants + two **unexported** regexes + two validators | **F57** (unknown) | append |
| `Backend/tests/test_frontend_constant_parity.py` | one `MIRRORS` param + one parametrize | — | append |

### Commit order (most-independent first)

| # | Commit | Conflicts with |
|---|---|---|
| 1 | `.planning/specs/customers-crm.md` | — |
| 2 | `app/customers/validation.py` + `test_customers_validation.py` | — |
| 3 | `models/customer.py` + the three repository appends | **F33** on `customer.py` |
| 4 | `app/customers/{__init__,schemas,service}.py` + `test_customers_service.py` | — |
| 5 | `models/constants.py` (one `AuditAction`) | F57 — different hunk |
| 6 | `app/customers/router.py` + `main.py` + `test_customers_api.py` | **F57** on `main.py` |
| 7 | frontend: `api.ts`, both components, `validation.ts`, `i18n/{he,ar}.ts`, parity test | F57 (append points) |
| 8 | frontend routing: `App.tsx`, `vite.config.ts`, `Nav.test.tsx`, `i18n.test.ts`, `CustomersSection.test.tsx` | **F57**, heavily |
| 9 | **LAST:** the migration + its `test_migrations.py` block | F57 on `test_migrations.py`; the number vs F57/F33/F19 |

### Rebase drill

```bash
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/customers-crm"
git fetch origin && git rebase origin/main
# resolve the contended files — every one is "keep both"
# renumber main.py's include comment (F53 becomes the NINTH /manage router post-F57)
# re-run the two Nav.test.tsx slice numbers and both test names by hand
cd Backend && uv run alembic heads      # the ONLY source of down_revision
# amend commit 9: down_revision + the filename
cd .. && make lint
uv --directory Backend run pytest -m "not db"
make fe-test && make fe-build && make e2e
```

**Every `git add` pathspec must be lowercase** (`backend/…`, `frontend/…`) — git tracks them lowercase while the on-disk directories are capitalised, and an uppercase pathspec silently skips modified tracked files. Verify with `git show --stat`.

**Do not open the PR while another branch holds an unmerged migration at F53's number.** Ship per `/modryn-loop` step 8: push, `gh pr create`, `gh pr checks --watch`, then `bash .claude/scripts/merge-gate.sh <n> && gh pr merge <n> --merge`. `main` is unprotected; the merge gate is the only gate.

---

## Out of scope

- **Creating, renaming, merging or deleting a customer.** A customer row is minted by the OTP flow and only by it — `models/customer.py:11-13`: *"created ONLY after OTP verification proved possession of that number — an unverified phone would strand a paying customer behind an SMS link that can never arrive."* A console-created customer would have an unverified phone, which is new legal and security ground, exactly as Q6 ruled for owner-created bookings.
- **Editing `name` or `phone` from this screen.** `set_phone` exists and has one caller — `OwnerBookingService.correct_phone`, which re-mints manage tokens for every live booking and has a collision branch that re-points a booking (`booking/owner.py:641-695`). Exposing the column without that machinery would silently break every outstanding SMS link. The remedy lives on the booking detail, where it already ships.
- **Merging two customer rows** (the phone-correction split-history case, F52's Risk 12). It needs a re-point of every booking, a decision about which name and phone win, and an answer for the case where the two rows really are two people — which is precisely what `set_customer_id`'s docstring says it keeps both rows for.
- **`message_log.customer_id` and any rewrite of the log's write path** (D3's residual, Risk 1).
- **Any mutation of a message row** — resend, delete, edit, mark-as-read. The log is evidence; a mutable evidence trail is not evidence.
- **The SMS log on the *booking* detail.** The epic's Locked feature decisions table rules the log *"read-only per customer/booking"* (`epics/shift-manager-console.md:33`) and F53 ships only the customer half. Nothing renders a per-booking log today — `BookingDetail.tsx` imports `errorMessage` and nothing message-shaped — so this is a reduction against an authority document and is recorded as one rather than left to read as an oversight. **The reason it is acceptable**: `CustomerDetail`'s log already contains every lifecycle row for every one of her bookings, because the booking leg of D3's predicate is `booking_id IN (all her bookings)` — the booking-detail view would be a strictly narrower slice of a panel that is one click away through the history list. **The consequence, which must not be swallowed**: the epic's SMC-4 row does **not** fully close that locked decision, and the remainder — `MessageLog.booking_id == booking_id`, the same `SmsLogRow`, rows appended to the existing `BookingDetail` response, no new route and no new copy beyond the four `customers.messages*` keys this deck already carries — belongs to whichever feature next touches `booking/owner_router.py`. It is cheap; it is simply not F53's, and F53 being the last unbuilt SMC entry is exactly why saying so here matters.
- **A controlled tag vocabulary, a tag-management screen, a distinct-tags endpoint or tag autocomplete** (D5). Upgrade paths recorded.
- **Filtering or sorting the list by tag** (D5). No index, no reader, no request.
- **A `pg_trgm` extension and any search index** (D2). Upgrade path recorded in the migration comment.
- **Any message-log index** (D3). The upgrade is a *pair* or it is nothing, and it is recorded as a pair.
- **Reading `audit_log`** — the same ruling as F15's D2, F51's D8 and F52's D9. Written, not rendered.
- **A customer count on the dashboard, or reconciling this list's `total` with `dashboard.customers.total`.** They answer different questions — F52 counts a **booking-derived cohort** over twelve weeks and F53 counts **live customer rows**, and F52's Risk 9 named this discrepancy in advance and asked F53 to define its own number deliberately. This spec does: `total` is live, non-soft-deleted `customers` rows matching the search. No copy on either screen implies the two should agree.
- **An e2e spec and a manage-console Playwright harness** (Test plan). F58's.
- **Retrofitting the four hardcoded-Hebrew console sections to i18n** — inherited from F15's D16, unchanged.

---

## Risks & open items

1. **Non-lifecycle rows are mis-attributed in BOTH directions after a phone changes hands, and the under-report is the one D3 calls the thing the log must not do.** One root cause — `message_log` has no `customer_id`, so a row with no `booking_id` is attributed by the phone string alone — with two symptoms, and an earlier draft of this list named only the first:
   - **Over-report.** A masked OTP row written to phone X before a recycle surfaces on the new holder's log: it has no `booking_id`, so the fence cannot reach it, and its `phone` genuinely was X. What leaks is a timestamp plus «קוד האימות שלך: ••••••» — no name, no appointment, no digits (`notifications/validation.py:61-65`).
   - **Under-report.** The phone leg matches the customer's **current** phone. `set_phone` is a single `update(Customer).values(phone=phone)` touching no other table (`customers.py:49-75`) and D3 insists `message_log` is never rewritten — so the moment her number is corrected, every non-lifecycle row sent to her previous number stops matching. Those rows have no `booking_id`, so the booking leg cannot recover them either: they become invisible on her log, and invisible everywhere unless some other customer later registers the old number. **This is the under-report D3 forbids** — *"A view of it that understates send volume is the one thing it must not do"* — and it bites hardest in the case that matters most for the evidence trail: a mistyped number means the OTP went to a stranger, which is precisely the send a regulator would ask about.

   **Mitigation**: the masking caps the magnitude of the over-report; `messages_total` (D3) at least keeps the *visible* volume honest about the window, though it cannot conjure rows the predicate never matched; and both directions are named here rather than assumed away. **The upgrade path is identical for both** — `message_log.customer_id` populated at write time — and it is blocked on the same fact: a backfill cannot be correct for historical rows, because which customer owned a phone at send time is exactly what was never recorded. One `db` assertion characterises the current behaviour rather than leaving it to be discovered. *Owner: team. Trigger: the F21 security audit, or the first pilot boutique that recycles or corrects a number.*
2. **`vite.config.ts` is a guaranteed two-hunk conflict with F57.** Both features add a segment to the same alternation and both must bump the same two count words in the prose above it. **Mitigation**: `test_spa_serving.py:372-400` derives the expected set from the live route table and asserts set equality, so a bad resolution fails a Python test in the fast suite rather than 404-ing on one developer's machine. Note the regex is `[a-z|-]+` — a segment with a digit or an underscore silently fails to match at all. *Owner: whoever rebases second. Trigger: the F57 merge.*
3. **`Nav.test.tsx` carries three coupled numeric edits and two test names.** A half-done rebase leaves a test whose name says "ten sections" asserting eleven. **Mitigation**: all five edits ship in one commit (#8), the failure is a red build rather than a silent pass, and the file's own `:66-68` comment names the coupling. *Owner: whoever rebases second. Trigger: the F57 merge.*
4. **`down_revision` rot.** Three unmerged migrations are racing for numbers and F53's is the fourth. **Mitigation**: the migration is the **last** commit on the branch, so a rebase costs one amend to one file nothing references; `alembic heads` on the rebased branch is the only source; and `command.downgrade(cfg, "-1")` makes F53's `test_migrations.py` block order-independent so the merge with F57's is concatenation (D12). *Owner: team. Trigger: every rebase.*
5. **`models/customer.py` collides with F33**, which adds `marketing_opt_in_at` to the same table and will claim 0016. **Mitigation**: both edits are appends after `name`, so the resolution is the union; F33 has zero commits so F53 will likely land first. **Do not assume it** — re-read `alembic heads` regardless. *Owner: team. Trigger: F33 landing first.*
6. **Two `db` modules debut on CI.** Neither `test_customers_db.py` nor F53's `test_migrations.py` block has ever run — there is no Docker locally. **Mitigation**: every non-SQL assertion is kept out of both modules (definitions live in `test_customers_validation.py`, wiring in `test_customers_api.py`), so a red round has a small blast radius. Budget one. *Owner: team. Trigger: the first CI run.*
7. **The `נשלח` copy guard rejects the natural SMS-log heading and the natural status word.** «הודעות שנשלחו» and «נשלחה» both red-fail `i18n.test.ts:247` the moment `HE_F53` is folded into `HE`. **Mitigation**: D11 picks «יומן הודעות» and «הועברה לספק», both of which are *more* accurate than the words they replace — the log renders failures, and `sent` means the provider accepted rather than that a handset received. The guard is not widened; a deck that has to dodge its own guard is copy one edit from lying, and this deck does not dodge it. *Owner: team. Trigger: none; the guard is the mitigation.*
8. **Search is a sequential scan over one tenant's live customers on every keystroke burst.** **Mitigation**: the 300 ms debounce caps request rate per typist; RLS plus the tenant predicate cap the scan to one boutique; hundreds of rows is microseconds. The `pg_trgm` pair is recorded in the migration comment with its threshold (~50k live rows per tenant, which would mean the product is no longer a boutique platform). *Owner: team. Trigger: that threshold, or a pilot report of a slow search.*
9. **The SMS-log join is an `OR` across two unindexed columns and can only be a sequential scan.** **Mitigation**: it is bounded by `LIMIT 50` and by one tenant's `message_log`, and the upgrade is recorded as a **pair** of partial indexes because a single one buys nothing (a BitmapOr needs both legs). Threshold ~100k rows per tenant. *Owner: team. Trigger: that threshold.*
10. **Free-text notes about a named third party are now stored with no retention policy, no export and no erasure path.** Israel's Amendment 13 gives a data subject rights this product cannot yet serve for this column, and F20 is the feature that owns that surface. **Mitigation**: the audit row carries **field names only** (D8) so notes do not propagate into a second table that platform operators read; the column is `TEXT NULL` and clearable from the UI; and the copy states plainly who can read it («ההערות נשמרות בכרטיס ונראות לצוות הבוטיק בלבד»). Named here so F20 inherits it explicitly rather than discovering it. *Owner: **user** (to overturn, not to authorise). Trigger: F20, or the F21 security audit.*
11. **Tags are free text, so one boutique will end up with «VIP», «vip » and «וי איי פי».** The case-insensitive dedup catches the first two within one customer but nothing reconciles across customers. **Mitigation**: accepted for the pilot — free text is how the vocabulary gets discovered, and the promotion path (`unnest(tags)` → a table) is recorded in D5. *Owner: team. Trigger: a quarter of pilot usage.*
12. **Two staff editing one customer's notes concurrently is last-write-wins and the loser is not told.** **Mitigation**: D7 accepts it explicitly — it is the answer every text field in this product already gives, the loser can retype, and the alternative (an `updated_at` precondition) turns a rare recoverable overwrite into a frequent confusing 409. *Owner: team. Trigger: a pilot report, which would need two people editing one bride's card inside one save cycle.*
13. **`SmsLogRow.body` renders a raw provider-bound string into the DOM.** React escapes it, so this is not an injection risk — it is a *layout* one: an SMS body can be long, can carry a URL, and mixes Latin and Hebrew. **Mitigation**: the body renders inside `<bdi>` in a `text-sm` paragraph with natural wrapping, and the same bodies already render in the storefront's own SMS previews. *Owner: team. Trigger: a pilot screenshot with a broken line box.*
14. **The 403 Hebrew string is reachable only for an out-of-enum role, which `0011`'s CHECK makes impossible in the database.** So `customers.error.NOT_AUTHORIZED` is copy that in practice never renders. **Mitigation**: it is four lines of deck and one map entry, and the alternative — falling through to `errorMessage()` — renders the server's **English** body into a Hebrew console, which is F51's Risk 4 exactly. Keeping it is cheaper than the defect it prevents. *Owner: team. Trigger: none.*
15. **`kind='otp'` rows share the un-paginated `LIMIT 50` with lifecycle rows, and OTP rows are written by an anonymous endpoint — so the panel can be filled entirely with them.** `/storefront/otp/send` reads no cookie and carries no ambient credential (`notifications/router.py:1,45,50-53`), OTP rows never carry a `booking_id` so they always land in the phone leg, and they are always the newest. At 5 sends per phone per hour per process, in-memory and per-instance, fifty of them evict every confirmation, reminder, owner-cancel and owner-reschedule row from the view — permanently, since there is no pagination, no `kind` filter and no date range. It does not need an attacker: every booking costs at least one OTP send. **Mitigation**: `messages_total` (D3) is computed under the identical predicate and rendered in the truncation line, so *"how many messages did you send this person"* — D3's own second reason for including OTP rows at all — stays answerable when the window truncates. The **recorded upgrade** if the panel itself stops being useful is a separate bound on the OTP contribution (a second constant, at most ten `kind='otp'` rows), **not** a higher shared cap, which only moves the eviction threshold. *Owner: team. Trigger: a pilot screenshot of a log that is nothing but «קוד אימות» rows.*

---

## Rejected review findings

Findings raised in review that this spec declines, with the evidence for declining. Rejection here carries the same burden the finding did.

- **"The LANGUAGES ruling is cited at the wrong line — `LOOP-STATE.md:1138` is F44's Pre-decided #46 about SEO/prerender; the ruling is at `:1214`."** **Rejected: the citation in D11 is correct and the finding's replacement does not exist.** `.planning/LOOP-STATE.md` is **1146 lines long** (`wc -l`), so there is no line 1214 to cite. Line **1138** is the ruling, verbatim: `- "LANGUAGES: Hebrew only for now. No language switcher, no en/ar toggle — the brief's tri-lingual top bar is deferred. Q3 and E10 are unchanged: every feature keeps shipping ar keys untranslated, and English is not in the plan at all."` Pre-decided #46 (*"build-time prerender + sitemap + per-tenant robots.txt, not SSR"*) is at line **1063**, seventy-five lines earlier. The file is unmodified in this worktree — its last commit is `877587c`, the same `origin/main` the branch was cut from — so there is no version skew to explain the discrepancy. D11 keeps `LOOP-STATE.md:1138`. The finding's one useful half is adopted, because it costs nothing and names the guard that actually enforces the rule at build time: D11 now also cites `i18n.test.ts`'s `ar` bundle describe, which rejects any `ar` value equal to `""` and asserts every `HE` key exists in `ar.translation`.

---

## Decisions Log

- **D1 — Two columns on `customers`, and the migration is the LAST commit on the branch.** `notes TEXT` nullable, matching `bookings.notes`; `tags TEXT[] NOT NULL DEFAULT '{}'`, because "no tags" and "empty list" are one fact and a nullable array gives it two representations that make every predicate silently three-valued (`array_length(NULL,1)` is NULL, `'x' = ANY(NULL)` is NULL — wrong answers that raise nothing). The rewrite objection is false on PG 11+: a non-volatile default lands in `pg_attribute.atthasmissing` and the `ALTER` is catalog-only. `tags` is the **first array column in this codebase** — `ARRAY(Text)`, `Mapped[list[str]]`, `server_default=text("'{}'::text[]")`, spelled out because there is nothing to copy. No GRANT (table grants are column-agnostic, `0008_bookings.py:107-110`), no `enable_tenant_rls` (a table property, already forced), no trigger (`trg_customers_updated_at` exists, `0008_bookings.py:50`), no index, no CHECK, no backfill — the `0014_booking_check_in.py` "deliberately absent" list, complete. Revision resolved from `alembic heads` on the rebased branch, **never hardcoded**; today's expectation is **0018** (F57 holds 0015, F33 takes 0016, F19 renumbers to 0017). Declined: `JSONB` for tags (no element type, needs GIN for containment, and the future query is `unnest`).
- **D2 — Search is `icontains(term, autoescape=True)` over `name` OR a digit-normalized `phone`, ordered `name, id`, with no index.** **The phone leg runs on `phone_search_term(term)`, not on the raw term**, because `customers.phone` only ever holds E.164: `normalize_israeli_mobile` rewrites `05X…` to `972…` before storage (`notifications/validation.py:25,43-45`) and both writers pass its output, so `'+972501234567' ILIKE '%0501234567%'` is false and `%050%` matches nothing at all — the two most natural desk inputs would return «אין תוצאות» for a customer who exists, on a screen whose own label promises search by phone. The helper is six pure lines reusing the shipped rule (`re.sub(r"\D", "", term)`; `05…` → `972…`; `None` when empty), `None` skips the leg, the name leg keeps the raw term, and `autoescape=True` stays on both. Pinned in the fast suite as a table and in `db` against a customer stored as `+972501234567`. `autoescape=True` is load-bearing: without it a typed `_` or `%` returns the whole tenant, and hand-rolling `f"%{term}%"` ships exactly that. SQLAlchemy resolves 2.0.51, so the kwarg exists. The `id` tiebreak is what makes OFFSET paging stable when two customers share a name. A blank `q` drops the predicate rather than searching for `""`. `MAX_SEARCH_TERM_LENGTH = 80` bounds the term at the boundary. **No index, deliberately**: btree cannot serve an unanchored `%term%` at all — only a `pg_trgm` GIN index can, and that needs a `CREATE EXTENSION` this migration does not have. At pilot scale the seq scan is right; the upgrade path is recorded in the migration comment with its threshold. Declined: an exact-phone fast path — not because `050` prefix-matches (it does not; an earlier draft's reason was factually wrong on this codebase) but because digit normalization makes an exact-phone branch redundant.
- **D3 — The SMS log is `or_(booking_id IN (this customer's bookings), and_(phone == …, booking_id IS NULL))`, and the `AND booking_id IS NULL` is the correctness of the feature.** `message_log` has no `customer_id`, so attribution has exactly two possible keys. Phones are **corrected** (`set_phone`) and **recycled**, so a phone-only predicate renders bride A's confirmation bodies — carrying A's name and appointment time — on bride B's screen: a cross-customer disclosure inside one tenant, invisible to RLS and to every isolation test in the repo, on the one screen whose brief is personal-information hygiene. With the fence, a row that *has* a `booking_id` belongs to that booking's customer, full stop, and the phone leg is a fallback only where no booking link can exist. Residual: masked OTP rows with a stranger's timestamps — magnitude is a timestamp and «קוד האימות שלך: ••••••», accepted as Risk 1, and closing it needs `message_log.customer_id` plus a backfill that cannot be correct. **One statement, one round trip, and specifically not `UNION`** — a lifecycle SMS to the current phone matches both legs, so `UNION ALL` double-renders and `UNION` sorts to dedupe; `or_` needs neither. **OTP rows included, unfiltered**, for four reasons: the masking ruling already made them safe to store and read; `message_log` is the Spam-Law evidence trail and a view that understates send volume is the one thing it must not do; for a customer with no bookings they are the only evidence anything was sent; and excluding them costs a filter plus a rule to remember while including them costs nothing. `LIMIT 50`, ordered **`created_at DESC, id DESC`** (inverting `list_by_phone`'s ASC, which is why that method cannot be reused; the `id` tiebreak is mandatory because `created_at` defaults to `now()` = `transaction_timestamp()`, so fixture rows written in one transaction are indistinguishable and a 51→50 assertion without it is a coin flip on this module's CI debut). **`tenant_id ==` and `deleted_at IS NULL` are both on the predicate** — the explicit tenant filter is the house defense-in-depth pattern the repository's own docstring names and `list_by_phone` carries, and this is the one query in the feature keyed on a phone rather than a customer id, on a column where the same phone under two tenants is a designed-in collision (`0008_bookings.py:41-44`); RLS is not a substitute, since `config.py:250` falls back to the superuser `DEV_DATABASE_URL` whenever `DATABASE_URL` is unset. **Plus `messages_total`**, a second `select(func.count())` over the identical `where`: the fifty-row window can be filled entirely by `kind='otp'` rows written through an anonymous endpoint at 5/hour/phone/process, which would evict every lifecycle row and make the screen understate send volume — the one thing reason #2 says it must not do (Risk 15). **No index on `message_log`** — a BitmapOr needs an index on **both** legs or neither, so the upgrade is recorded as a pair, at ~100k rows per tenant.
- **D4 — `SmsLogRow` is `{id, created_at, kind, status, body}`, and the log rides inside `CustomerDetail`.** `provider_message_id` is an operator's correlation handle; `error` is **already fenced by a shipped comment** (*"never reaches a response body"*, `models/message_log.py:23-24`); `phone` is on the parent and repeating it per row invites the exact mental model D3 destroys. One click, one fetch — a fourth route would be a second loading state and a second failure mode for something never wanted alone. Booking history needs the **third** repository append (`BookingsRepository.list_recent_for_customer`, correction C8): the closest shipped method, `list_live_for_customer`, pins `status = 'confirmed'` and `starts_at > after` and is F15's re-mint feed. All statuses, `list_day`'s ruling — a cancelled row is evidence. `CustomerBookingRow` ships four fields; `dress_name`, `seat_index` and the rest already render on the booking detail one click away, and a CRM row duplicating a detail view is a second place for one fact to drift. **`created_at` ships on neither model**: F52's D7 established that `customers.created_at` is meaningless as "first seen" after the phone-correction collision branch, so it would be a plausible wrong "customer since" date on the one screen an owner would quote from.
- **D5 — One pure validation module: `MAX_TAG_LENGTH = 24`, `MAX_TAGS = 10`, `MAX_CUSTOMER_NOTES_LENGTH = 2000`.** The notes cap is the **profile-description** peer (`boutique/validation.py:30`), not booking-notes' 500 — a booking note is about one appointment, a CRM note accretes across a year of fittings. `normalize_tags` is strip → drop empties → reject control chars → length → **case-insensitive dedup, first occurrence wins and keeps its casing** → **cap after dedup** (capping first would let ten duplicates crowd out a real eleventh) → **preserve caller order, never sort** (alphabetizing on save is the product rearranging her screen). The control-char class is **`_CONTROL_CHARS` from `booking/validation.py:69`** for tags — the whole C0 set, because a tag is a one-line label — and **`_CONTROL_CHARS_EXCEPT_WS` from `:70`** for notes, which is a paragraph. The plan cited line 70 for both; line 70 permits `\t\n\r` (correction C1). Both names are underscore-private with no cross-module precedent, so the import carries one line of comment. `DomainValidationError` subclass → the shipped 400 handler, **no new handler in `main.py`**. **No controlled vocabulary** (a table, a screen, a rename story and an orphan story, for a pilot where nobody knows the tags yet — free text is how the vocabulary gets discovered), **no distinct-tags endpoint and no autocomplete** (a 10-tag cap makes the saving trivial while the cost is an endpoint, an unindexable `SELECT DISTINCT unnest(tags)`, a staleness question and a WCAG-conformant combobox), **no index on `tags`** (nothing filters by it). Three upgrade paths recorded.
- **D6 — New package `app/customers/`, three real-verb routes, both roles at router level, three repository appends and no new repository file.** `app/notifications/` is the precedent for the `service.py`/`router.py`/`schemas.py` trio in a package owning no table; F53 reads across three tables and belongs to no existing domain. `GET /manage/customers` (paginated `{items,total,offset,limit}` — a customer count grows without bound, so F51's bare-array precedent does not transfer, and `total` is computed under the **same** predicate as the page), `GET /manage/customers/{customer_id}`, `PATCH /manage/customers/{customer_id}`. Path parameters and real verbs are the shipped convention, stated in three router docstrings; the `.claude/rules` RPC guidance is Kotlin boilerplate. Bounds mirror `booking/owner_router.py:168-169` with `MAX_LIST_OFFSET` **restated** locally (`booking/owner.py:52-58` shows restatement is the house call, and the reason — asyncpg `int8_encode` answering 500 — is restated with it). `UpdateCustomerRequest(ForbidExtraModel)` with `None` = not supplied and `""`/`[]` = clear, the `boutique/validation.py:110` ruling. **The two GETs declare no `staff` parameter; the `PATCH` does**, because the acting id has exactly one reader — the audit row. Tenant from `get_current_tenant(request)` on all three, never `staff.tenant_id`. `_no_store` is a local three-line copy citing `auth/staff_router.py:22-27` and **stating no ordinal**, because every ordinal written into this codebase so far has gone stale (correction C5); the one ordinal F53 does write is `main.py`'s include comment, and it is the **EIGHTH** on `origin/main` / **NINTH** post-F57 — seven `/manage` routers exist today, six with the exact prefix plus `auth/router.py:13`'s `"/manage/auth"`, which `main.py`'s own chain counts (`:1039` labels the gateway router "The SEVENTH"). **`CustomerRow` carries `phone`**, which is a departure from `OwnerBookingRow`'s D18 bulk-PII-export ruling (`booking/schemas.py:107-114`) and is argued in the body rather than inherited: a day list is a schedule and a customer directory is an index of people, the phone is the disambiguator for the shared-name case `ORDER BY name, id` already exists for, and the half D18's force actually lands on — `notes` — stays detail-only. **`CustomerDetail` also carries `messages_total`** (D3). **The `PATCH` returns the same fully-built detail as the `GET`, on the write path and the no-op path alike**, through one private `_build_detail` inside one `tenant_session`: the client does `setDetail(updated)` unconditionally, so a response with empty panels would blank the booking history and the SMS log on save. On the wire the TS interface is **`CustomerDetailResponse`**, not `CustomerDetail`, because that name belongs to the component — the shipped `OwnerBookingDetail` / `BookingDetail` pair avoids exactly this, and `isolatedModules: true` makes a colliding value import a hard TS2865.
- **D7 — No advisory lock.** F51's D3 took one for an **at-least-one** invariant that no index can express and that a `count(*)` subquery cannot enforce under READ COMMITTED. F53 has no invariant of that shape: a notes/tags edit is a single-row `UPDATE`, and concurrent edits are last-write-wins, which is the answer every text field in this product already gives. Declined: an `updated_at` precondition (turns a rare recoverable overwrite into a frequent confusing 409 on a field where the loser can retype) and a lock (serializing every CRM edit to protect nothing).
- **D8 — One `AuditAction.CUSTOMER_UPDATED`, `details = {"fields": sorted(changed)}`, `entity = str(customer_id)`.** One value rather than notes+tags variants, because the split criterion this repo actually applies — recorded three times in `models/constants.py`, most sharply at `:129-134` — is *"is this a distinct question a security audit asks of this table"*, and nobody will ever ask it "who edited tags but not notes". **Field names only, and this is a deliberate departure from F51's `STAFF_UPDATED` `{from,to}`**, which is correct *there*: a display name is a label a staffer chose for herself, while customer notes are free text written **about a third party who never sees them**, `audit_log` has **no retention policy**, and platform operators read across tenants — so copying a bride's notes there exports them out of the tenant that owns them. The audit question is who changed the record and when; the old value does not answer it and the new value is on the row. `entity` is the id, never the name. **F51's no-op rule carries**: neither field moved → no `UPDATE`, **no audit row**, 200 unchanged, and the client sends only what moved.
- **D9 — No new error code, no new body, no new handler, no `main.py` change beyond wiring and the include.** `CustomerNotFoundError(DomainNotFoundError)` → 404 and `CustomerValidationError(DomainValidationError)` → 400 both ride handlers bound to the `app/errors.py` bases through Starlette's MRO walk — `app/errors.py:1-9` exists for this and `auth/staff.py:87-91` says so. **The envelope is two keys** (`code`, `message`); the four-key shape in `.claude/rules` is wrong for this repo. **There are no 422s** — `main.py:738-745` normalizes `RequestValidationError` to a 400 `VALIDATION_ERROR` (correction C2). **`CSRF_ORIGIN_MISMATCH` IS in F53's set** and this is where F53 diverges from F52's GET-only template: `csrf.py:48` fences `MUTATING_METHODS` and the `PATCH` is one, so the API test ships a real mismatched-origin assertion and must not copy the dashboard module's allowed-GET inverse. No audit row on either GET (`dashboard/service.py:344-349`). No rate limiter — no `/manage` router carries one.
- **D10 — Eleventh nav row at index 8, in-panel swap, no router, no new dependency, patch-from-response.** Index 8 is fixed by two shipped comments: not row 0, which is the landing section (`App.tsx:59-65`), and above the two owner-only rows, which is what keeps the shift-manager assertions a `.slice` (`Nav.test.tsx:66-68`). The list→detail swap is `BookingsSection.tsx:53-55`'s early return, whose comment states the ruling — *"apps/manage has no router and F15 does not introduce one for one view."* The tag editor is `Input` + `Button` + `Badge` chips and the debounce is six lines of `setTimeout` + cleanup — **not** a package and **not** F57's unmerged `lib/usePoll.ts`. The `PATCH` response replaces the detail and patches the list row; the list is **not** refetched, because `name` and `phone` cannot move through this endpoint so neither membership nor the `name, id` order is affected — the inverse of BookingsSection's reschedule case, stated because the next mutation added here would need the refetch.
- **D11 — Hebrew only, `ar` verbatim, and the SMS-log heading is «יומן הודעות».** Two independent reasons, and the second is the one that matters: `i18n.test.ts:247` rejects `/נשלח|תישלח|בדרך/` so «הודעות שנשלחו» red-fails the build the moment `HE_F53` is folded into `HE` (which it must be — `:32-34` records that an unfolded constant silently skips the resolve check, both register guards **and** the `ar` parity guard); and the log **renders `status='failed'` rows**, so a heading claiming they were sent is the exact lie that guard exists to prevent. The same reasoning fixes the status word: `sent` means the provider accepted the message, so the Hebrew is «הועברה לספק», not «נשלחה». The guard is not widened. Zero exclamation marks. Numbers inside `help` strings sit mid-sentence bounded by Hebrew and are **not** isolated — `InputProps.help` is typed `string`, so `isolateLtr` (a `ReactNode`) cannot be used there at all; announced counts in `role="status"` regions do go through it. **The deck lives in this spec**, not in `.planning/design/screens/manage-customers/` — a departure from F51 and F52, recorded rather than silently taken: no novel pattern means the deck's only load-bearing content is the string table, and one copy of every string in the artifact the builder reads beats two copies that can drift.
- **D12 — One fetch per view, no poll, and `command.downgrade(cfg, "-1")` as a stated departure.** `useEffect` + `let cancelled = false` + `.then`/`.catch`, `BookingsSection.tsx:27-49` verbatim in shape; no `AbortController`, no interval, no `me()` refresh — F51's Risk 3 stays with F34 where F52's D11 sent it. The `"-1"` downgrade is **not** a correction of F57: all four shipped round-trip tests hardcode their target (correction C4), so this is a departure taken for one reason — three unmerged migrations are racing for numbers, and `"-1"` makes F53's `test_migrations.py` block order-independent so the merge resolution is plain concatenation. The `try/finally: command.upgrade(cfg, "head")` is mandatory for the reason `0014`'s own comment gives: leaving the schema down drops columns the ORM still maps, and every later `db` test in the shared container then fails with `UndefinedColumn` somewhere unrelated to itself.
