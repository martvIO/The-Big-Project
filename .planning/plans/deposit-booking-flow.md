# Plan: Feature 19 — Deposit booking flow (Epic E4)

**Status**: **Gate 2 self-approved** 2026-08-03 under the recorded pre-authorization — `.planning/LOOP-STATE.md`'s F19 `gate_1_preauthorized` field, the USER RULING of 2026-07-31 that waived the **pause** and not the **scrutiny**. **The design gate is self-approved too**: Interview Q2 named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix — and F19's payment step is neither; F57 set that precedent in its own spec header on 2026-07-31 and this feature inherits it. **There is no prototype and no `design-critic` pass, deliberately.** A design deck and a copy deck are nevertheless authored in Task 1 and are binding from Task 15 onward. The corrections C1–C7 below are amended into the spec in Task 0; the spec text is the binding statement of each resolution, this file the reasoning.

**Spec**: `.planning/specs/deposit-booking-flow.md` (Gate 1 self-approved 2026-07-31, MD1–MD5 + D1–D21, 771 lines, adversarial review round 2 — 32 findings, 9 BLOCKER, **all 32 applied, 0 rejected**) · **Design**: `.planning/design/screens/deposit-payment/design.md` (**authored in Task 1**) · **Copy**: `.planning/design/screens/deposit-payment/copy.md` (**authored in Task 1**; it is the canonical key list, not this file's prose) · **Branch**: `feature/deposit-booking-flow` · **Created**: 2026-08-03

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks; `make fe-test` + `make fe-build` for frontend ones; `make e2e` from Task 15 onward (this feature touches the storefront's built output). **`db`-marked tests are written here and normally execute only on CI** — but see §"Run the db suite locally anyway", which is the single highest-leverage instruction in this document and is what made F34 green on its first CI run and F57 green on its first.

F19 ships **one migration** — five statements, all of them widenings or additions, none destructive — and its four `constants.py` members plus one ORM column in the same atomic task (Task 2).

**Path hygiene.** The repo path contains a space and a `+`. Quote every shell path. And git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` silently skips modified tracked files. Lowercase every pathspec and verify with `git show --stat`.

---

## Interview and spec rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **The 2026-07-31 pre-authorization** (`LOOP-STATE.md`, F19 `gate_1_preauthorized`) | Gate 1 and Gate 2 self-approve. The five money decisions are **positions already taken** (MD1–MD5) and are not re-litigated by this plan. Exactly one item is **parked** — MD3's two approved Hebrew sentences — and it blocks **two strings**, not the feature. |
| **Interview Q2 / the 2026-07-31 design ruling** — only F34 and F42 are novel | **No prototype, no `design-critic` pass, no user gate.** A deck is authored anyway (Task 1) because the five payment states, MD3's interim sentence and D18's markers need one place where their copy lives; the deck's status line records what self-approval costs. F57's header is the precedent. |
| **Interview Q7** — *"the race most likely to be wrong (hold expiry vs a late webhook) does not depend on Grow, so it gets built and race-tested now"* | Task 13 is the reason this feature is being built before any merchant account exists. It is **not** the last task by accident: it is written after every writer it drives exists, and it is the only task whose failure means the feature is wrong rather than late. |
| **F17's Gate 1 Q1** (a dead calendar is worse than silently not collecting) | Inherited as a **binding input** for the not-connected case (D10/D19). MD4 resolves the *unavailable* case here rather than re-asking it, on F17's own re-ask condition (`gateway-port.md:512`). |
| **F17's Gate 1 Q4** (*"HONOUR IT… the deposit is marked paid"*) | Inherited verbatim as **D17**. F19 discovered the shipped code has **no writer** for it; `settle_late` is that writer. Not a reopened ruling. |
| **pre-decided #23** — no realtime vendor | Task 15's return page polls on a plain interval with a bounded attempt count. No socket, no SSE, no data-fetching dependency. |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is a **legal** requirement. The five payment states are on the storefront, which is the public surface — axe-clean is a gate on Tasks 15–17, not polish. |
| **pre-decided #47 / Q3** | Every new key lands in **both** `he.ts` and `ar.ts`, Arabic values = the approved Hebrew standing in untranslated, **never `""`**. F17 added a he/ar key-parity assertion to `i18n.test.ts`; F19's keys are asserted by it. |
| **MD3's park** | `manage.cancelConsequenceDeposit` ships the neutral interim; **`manage.cancelConsequenceFree` MUST NOT survive the merge on a deposit booking.** The park does not block Task 16 — the interim satisfies the hard constraint. |

---

## What moved since the spec was written (2026-07-31 → 2026-08-03)

F34 merged as PR #32 during what the spec expected to be a quiet window, and **three features are now in flight in three worktrees at once** — F57 (floor staff roles), F33 (QR walk-in queue) and this one. That is the single fact that shapes this plan more than any other: two of the seven corrections and the whole scope fence exist because of it.

**Everything below is verified against the tree at this commit.** Where a spec citation still holds it is marked ✅ so the builder does not re-check it.

### Migrations — HEAD is **0014**, and three features are queued behind it

```
$ ls "<repo>/Backend/migrations/versions/"      →  0001 … 0014
$ grep -n '^revision\|^down_revision' 0014_booking_check_in.py
  revision = "0014"     down_revision = "0013"
```

`0014_booking_check_in.py` is **F34's, already on main**. The spec says "Migration 0014" throughout and is **wrong on every occurrence** — see **C1**, which is the largest correction in this document and the only one that changes what gets committed.

### `Backend/app/db/repositories/bookings.py` — F34 shifted every citation the spec makes into it

| Spec says | Actually | What it is |
|---|---|---|
| `:56-104` | **`:89`** | `insert` (and its advisory-lock obligation docstring) |
| `:130` | **`:149`** | `active_at` — 0009's index mirror, D5 step 2's second read |
| `:145` | **`:168`** | `active_seats_at` — 0008's index mirror |
| `:150-166` | **`:183`** | `by_manage_token_hash` (no status predicate at all) |
| `:196-203` | **`:201`** | `set_manage_token_hash` |
| `:258` | **`:278`** | `confirm_attendance` |
| — | **`:300` / `:367`** | `check_in` / `undo_check_in` (F34's, new) |
| `:267-307` | **`:431`** | `set_status` |
| **`:346`** | **`:473`**, its `== 'confirmed'` guard at **`:510`** | **`cancel` — the seat-release writer D2 widens** |
| `:389-391` | **`:525`**, its predicate at **`:551-556`** | `reschedule` — MD1's writer |
| `:449` | **`:601`** | `list_live_for_customer` |
| `:467` | **`:621`** | `list_confirmed_without_manage_token` |
| `:495` | **`:641`** | `count_by_start` |
| `:502-560` | **`:666`** | `list_window_facts` — D14's "EVERY status" contract |
| `:588` | **`:727`** | `history_by_customer` |

**The RULINGS are unaffected.** `cancel` is still guarded `== 'confirmed'`; `set_status` still writes `.values(status=to)` and nothing else; both partial unique indexes still exclude only `cancelled`. Only line numbers moved.

### `Backend/app/dashboard/service.py` — same story, same cause

`cancellation` **`:133`** (the `len(cancelled) / len(facts)` at `:147`), `top_types` **`:175`**, `customer_mix` **`:224`**, `DashboardService.dashboard` **`:335`**, the `list_window_facts` call **`:361`**, the `cohort_ids` fold **`:370`**. **D14's ruling is unchanged and still correct**: filter `pending_payment` out of `facts` **once**, immediately after `list_window_facts` returns — one predicate, six sites.

### `Backend/app/main.py` — the placeholder comment moved, and the file grew

- The deliberately-unbuilt `PaymentService` singleton comment is at **`:709-712`**, not `:698-701`. Its text is verbatim: *"PaymentService is deliberately NOT on app.state: nothing reads it until F19 builds the deposit flow and the webhook route, and a wired singleton with no consumer is a thing a reviewer has to check rather than a thing that works."* **Task 5 deletes it in the same commit that wires the singleton.**
- There are **13** `FixedWindowRateLimiter` instances (`:563`–`:707`). F19 adds **none** — the webhook route is deliberately unmetered (D9; Redis-backed limiting is F21's).
- `_register_spas(app)` is at **`:1057`** and must **stay the LAST registration**; its own comment says why (*"LAST, after every router: the mounts and the catch-all only ever see what no API route claimed"*). The new payments sibling router registers **before** it, after `booking_router` at `:1054`.

### Citations that still hold exactly — ✅ do not re-verify

- ✅ `payments/service.py:449-525` — `open_deposit`, D23's five ordered steps, verbatim in its own docstring: `credentials_for` → `pg_advisory_xact_lock(hashtext(:tenant_id))` → `live_pending_for_booking` converge → `create_session` → insert → `IntegrityError → PaymentAlreadyHeldError`. The converge return at **`:500-505`** is `DepositHold(payment=existing, redirect_url=None, created=False)` and its comment names D8's obligation.
- ✅ `payments/service.py:527-536` — `settle_from_webhook`'s *"Deliberately does NOT touch `bookings`… F19's transaction"*. ✅ `:640-704` `_explain_missed_settlement`, whose final branch is an `else` on `status == 'paid'`, so `failed`/`refund_due`/`refunded`/`forfeited` all land in the late-settlement branch (Risk 7).
- ✅ `db/repositories/payments.py` — `insert` `:15`, `live_pending_for_booking` `:44`, `by_provider_transaction_id` `:59`, `by_provider_session_id` `:70`, `settle` `:81` (its *"ONE guarded UPDATE, never a read-modify-write"* docstring and its `.returning(Payment.id)` comment), `record_error` `:125`, `by_id` `:146`. **There is no batch read and no `mark_expired`** — D18 and D6 each add one.
- ✅ `models/payment.py:12-13` — *"`PaymentService` is its single writer — no adapter and no future caller can skip this row."* This is D20's whole basis. `provider_session_id` at `:34`, `hold_expires_at` at `:38`; **no `redirect_url`** (Task 2 adds it).
- ✅ `payments/fake.py:50-70` — `sign_fake_webhook` / `fake_webhook_body`, both module-level with **no production caller**; `:121` `redirect_url=f"{FAKE_PAY_PATH}?session={session_id}"`; `:124-131` real HMAC through `hmac.compare_digest`. `FAKE_PAY_PATH = "/fake-pay"` at `payments/validation.py:31`. A repo-wide grep finds **exactly**: that definition, that use, and `tests/test_payments_adapters.py:33, :94`. **Nothing posts a webhook to anything** — D21 and Risk 2.
- ✅ `payments/service.py:312-319` `credentials_for` (requires `row.status == 'valid'`); `:342-348` `_require_provider` (requires `gateway.is_configured` **and** `secret_box.is_configured`, and **raises** rather than returning a bool); `:350-354` `_active` → `db/repositories/gateway_credentials.py:55-63` `active_for_provider`, which filters **only** tenant + provider + `deleted_at IS NULL`. D10's argument is exactly this gap.
- ✅ `main.py:938-1004` — all nine payment error → status mappings, including `GatewayWebhookInvalidError` → **400, never 503** at `:995-1001` with D25's reasoning in the comment. **`grep IntegrityError Backend/app/main.py` returns nothing** — so D5 step 4 catching its own is not optional.
- ✅ `booking/router.py:1-25` — the sibling-router-on-`/storefront` docstring, the anonymous/cookie-blind/CSRF-N/A posture, and *"The confirmation SMS is fired HERE, after the transaction commits"*. `:79-113` the create handler; **`:95-101` the inline `if claim.created and claim.manage_token is not None:`** that D11 gates; `:106-113` the response build. `:117-121` `POST /booking/lookup` — the POST-for-a-read precedent D13 cites.
- ✅ `booking/service.py:94-109` `BookingClaim(booking, created, manage_token)`; `:141-154` `create_booking`'s signature; the nine ordered steps and the lock spanning step 4 → COMMIT.
- ✅ `booking/comms.py:89-98` `upsert_reminder(session, *, tenant_id, booking_id, starts_at, now, bookings, scheduled)` — **takes a session precisely so a caller can fold it into its own transaction** (`:107-112`); `:121-136` reads the pending row's token and carries it, minting only when there was nothing to inherit. D13's new `token: str | None = None` keyword goes here.
- ✅ `booking/schemas.py:40-49` `BookingCreateResponse` — **six fields, no token**, which is half of why D13's poll cannot use one. `:107-123` `OwnerBookingRow` (F34's `checked_in_at` at `:119-123`), `:133` `OwnerBookingDetail(OwnerBookingRow)`.
- ✅ `booking/owner_router.py:99-112` `_row_fields`, `:114-116` `_row`, `:118+` `_detail`. ✅ `booking/owner.py:147-189` `list_day`; **`:535-591` `reschedule`, whose step-2 guard is `if booking.status != BookingStatus.CONFIRMED.value: raise BookingTransitionInvalidError`** at `:588-589` — MD1's precondition, and the spec's `:483-484` is stale only in number.
- ✅ `booking/manage.py:131-141` `confirm_attendance`'s `CANCELLED` branch, `:143-180` `cancel` — which writes the status, the cancel evidence and the reminder cancel **and never touches `payments`** (Risk 9, MD3).
- ✅ `storefront/schemas.py:171-186` `AppointmentTypeRow` and its docstring: *"`deposit_*` ships now because a customer is entitled to see a deposit before choosing a time… E4's payment step reads the same fields."* ✅ `storefront/service.py:229-240` `list_appointment_types`, the session D10's `is_connected` rides.
- ✅ `storefront/router.py:103-137` `_throttle` — per-tenant, `record_failure` on **success**, mounted router-level at `:139`. This is why D9 refuses to hang the webhook off this router.
- ✅ `worker.py:65-103` `poll_once` — one `try/except … continue` per tenant, its docstring stating *"A failure for one tenant must not stop the others"*. `core/config.py:124` `worker_poll_interval_seconds: int = 60`.
- ✅ `models/constants.py:47-54` `BookingStatus` with *"E4 widens it with 'pending_payment'"* **as a comment only — the member does not exist**; `:57-61` `BookingCancelledBy` (two members); `:32-38` `MessageKind`; `:90-103` `PaymentStatus` (all seven, `EXPIRED` at `:97`); `:105+` `AuditAction`.
- ✅ `0012_payments.py:127-132` `idx_payments_hold_expiry`, labelled *"F19's expiry sweeper"* in its own comment. ✅ `0013_lemonsqueezy_provider.py:24-30` — the **drop/re-add of the auto-named `<table>_<column>_check`**, the exact shape Task 2's CHECK widenings copy, with its "the DROP carries no `IF EXISTS` in either direction on purpose" reasoning.
- ✅ `tests/test_booking_comms_db.py:1-20` + `pytestmark` at `:78` — the NullPool db-race discipline Task 13 copies.
- ✅ Frontend: `storefront/src/router.tsx:26` `BOOK_STEPS = ["slot","details","terms","verify","confirm"]` **as a closed set** with the comment saying why; `storefront/src/api.ts:306-316` `ManageBookingFacts` with the four-value comment at `:308-310`; `storefront/src/routes/ManageBookingPage.tsx:38` `const CANCELLED = "cancelled"`, `:390` the unconditional `manage.cancelConsequenceFree`; `he.ts:297` / `ar.ts:37` that key's value. `manage/src/lib/booking.tsx:15-26` the four-entry `STATUS` Map and its **documented raw-value fallback** at `:22-26`; `manage/src/components/BookingDetail.tsx:201-205` the five booleans over four statuses.

---

## Seven corrections — recorded, resolved, amended into the spec in Task 0

The spec is binding and MD1–MD5 / D1–D21 are **not** re-litigated. These are places where the document disagrees with the tree, or is silent on something a builder cannot proceed through. Every resolution is the smaller edit.

### C1 — the migration number is wrong, three features are racing for it, and git cannot see the collision

The spec says **"Migration 0014"** throughout — the header of its own migration section, D1, D2, D8, MD2 statement 4, MD5's CHECK, D6 claim 2's index. **All wrong.** `0014` is F34's shipped `0014_booking_check_in.py`, on main since PR #32.

Worse, this is a **three-way race**, not a stale number:

| Feature | Worktree | Migration |
|---|---|---|
| F57 floor staff roles | in flight | holds **0015** (`0015_floor_roles.py`) |
| F33 QR walk-in queue | in flight | takes **0016** |
| **F19 (this)** | this worktree | lands **0017**, `down_revision = "0016"` |

**So F19 MUST NOT OPEN ITS PR until F57 and F33 merge.** That is a sequencing constraint on the orchestrator, recorded in the run report at Task 18, not something the builder can resolve.

**But F19 cannot build against 0017 either**, because 0016 does not exist yet and alembic would refuse to run at all — every `db`-marked test in this feature would fail to reach a schema. **Resolution, in two halves:**

1. **BUILD against `revision = "0015"` / `down_revision = "0014"`**, so the branch is self-coherent and its db tests can run against a real cluster today.
2. **RENUMBER at rebase time**: two literals in the migration file (`revision`, `down_revision`) and the filename — `0015_deposit_booking_flow.py` → `0017_deposit_booking_flow.py`. Three edits, and Task 18's run report names them so the rebase is not a rediscovery.

**And the collision this creates is one git cannot see.** Two files claiming `revision = "0015"` with different filenames is not a merge conflict — git merges them cleanly, both land, and alembic then reports **multiple heads** at runtime. There is no test for it: `Backend/tests/test_migrations.py` has **12 tests** and **no head-count test**.

So F19 adds one, and it is **fast, not `db`-marked**, because it needs no database at all:

```python
def test_the_migration_history_has_exactly_one_head() -> None:
    """Two files claiming one revision id is an alembic multiple-heads error
    that GIT CANNOT SEE — the filenames differ, so the merge is clean and the
    failure surfaces at runtime in whichever environment runs alembic first.
    Three features are in flight in three worktrees as of 2026-08-03; this is
    the guard that turns that from a CI mystery into a `make test` red."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    assert len(ScriptDirectory.from_config(cfg).get_heads()) == 1
```

It reads the filesystem only, runs in `make test`, and costs milliseconds. It ships in Task 2 beside the migration it protects. Declined: a CI-only check (the whole point is that it fails **before** the push); a filename convention (filenames are already distinct — the ids are what collide).

### C2 — every `db/repositories/bookings.py` line the spec cites has shifted

F34 moved the file. The table in §"What moved" has every new location. **The content each citation points at is all still there** — `cancel`'s identity-map docstring included, now `:473-511`, whose governing sentence is verbatim: *"reading it off the `.returning()` scalar is the ONLY way to know that… `update(Booking)` is ORM-enabled DML whose default `evaluate` synchronization stamps the SET values onto the identity-mapped instance whatever the database matched, and `by_id` hands that same instance back."*

**Resolution:** the spec's D1 table and D2/D5's inline citations are re-pointed in Task 0. **No ruling moves.** Named as a correction rather than a footnote because D1's table is the feature's blast-radius inventory and a reviewer will check it line by line.

### C3 — `dashboard/service.py`'s citations shifted; D14's ruling did not

`cancellation` `:133`, `top_types` `:175`, `customer_mix` `:224`, `dashboard` `:335`, the `list_window_facts` call `:361`, the `cohort_ids` fold `:370`. The spec's `:109, :127, :146, :206, :251, :371` are stale.

**Resolution:** re-pointed in Task 0. **D14's ruling — one predicate immediately after `list_window_facts` returns, six sites, `list_window_facts` itself untouched — is unchanged and still correct.** The count of six is also unchanged; it is the same six functions at new addresses.

### C4 — `main.py`'s placeholder comment is at `:709-712`, and two structural facts come with it

The spec cites `:698-701`. **Resolution:** re-pointed. Two things travel with it and both are build constraints:

- **13** `FixedWindowRateLimiter` instances at `:563-707`. F19 adds **none**, and that is a decision (D9: a limiter on the webhook route turns a provider's retry burst into permanently unconfirmed bookings). Recorded so a reviewer counting limiters finds a ruling.
- **`_register_spas(app)` at `:1057` must stay last.** The new sibling router registers immediately after `booking_router` (`:1054`) and before it. Getting this backwards makes the SPA catch-all swallow `POST /storefront/payments/webhook` and returns HTML to a payment provider.

### C5 — `models/constants.py` is a LIVE MERGE SURFACE and F57 is editing it right now

F57's branch is widening `StaffRole` from two members to five **in this same file**. F19 adds, in four different enums:

| Enum | Member | Line today |
|---|---|---|
| `BookingStatus` | `PENDING_PAYMENT = "pending_payment"` | the comment at `:47-54` **reserves it; the member does not exist** |
| `BookingCancelledBy` | `EXPIRED = "expired"` | `:57-61` |
| `MessageKind` | `PAYMENT_RECEIVED_NO_SLOT = "payment_received_no_slot"` | `:32-38` |
| `AuditAction` | six members (D9, D21's set, MD4) | end of file |

**Resolution — the rule, and it is the whole of C5:** **append only, rebase before every push, and never touch F57's role values.** Different enums in one file is the easiest possible three-way merge *if* nobody reorders or reformats; it is a conflict on every hunk if somebody runs a formatter across the file. `ruff format` is already clean on it, so `make lint` will not reformat it — but a hand-tidy will. Declined: a second constants module (it would be the first split in the file's life, to dodge a merge that append-only already dodges); waiting for F57 (it blocks Task 2, which blocks all of Part I).

### C6 — F17's late-settlement test reaches its branch by hand, and F19's tests must not copy it

`Backend/tests/test_payments_service.py:921-925`:

```python
        # F19's sweeper got there first.
        async with tenant_session(factory, tenant) as session:
            row = await repo.by_id(session, tenant, hold.payment.id)
            assert row is not None
            row.status = PaymentStatus.EXPIRED.value
```

That was correct for F17: the sweeper did not exist, so the only way to reach `_explain_missed_settlement`'s late branch was to fake its precondition. **It is not correct for F19.** F19 *is* the sweeper. A late-settlement test that hand-sets `EXPIRED` proves that `honour_late_settlement` works against a row somebody wrote by hand, and proves **nothing** about the thing under test — whether the sweeper produces that row, in that transaction, with the booking cancelled beside it.

**Resolution: every F19 test that needs an expired hold drives expiry THROUGH `poll_once`.** Advance the injected `WallClock` past `hold_expires_at`, run the sweeper, then deliver the webhook. F17's test is **left exactly as it is** — it is another feature's test of another feature's branch, and editing it would be F19 rewriting F17's evidence. Named here so a reviewer who greps for the pattern finds a ruling rather than an inconsistency.

### C7 — `bookings.source` does not exist; do not invent it

`grep -rn 'source' Backend/app/models/booking.py Backend/migrations/versions/0008_bookings.py Backend/migrations/versions/0009_*.py` returns nothing. There is no column, no ORM field, no schema field. It is **F50's** (walk-in create from the board), unbuilt.

**Resolution:** F19 writes nothing to it and reads nothing from it. Recorded because the deposit flow is the obvious first place a reviewer would expect a channel discriminator, and inventing one here would put a column on `bookings` that F50's spec has not designed yet.

All seven are amended into the spec in **Task 0**, in the same PR — the F15 / F34 / F57 Task-0 precedent for a plan-phase spec amendment.

---

## Scope fence — read this before every task

**F19 ships a booking that is created first, held, paid for, swept, honoured late, and shown to the owner.** It is the first feature in the product that moves a customer's money, and it attaches nothing else.

### Three features, three worktrees, one tree

| Surface | Owner | Rule |
|---|---|---|
| `app/auth/`, `models/staff_user.py`, `db/repositories/staff_users.py`, `migrations/versions/0015_floor_roles.py` | **F57** | **DO NOT TOUCH.** Not one line, not a formatter pass, not an import re-sort. |
| `app/storefront/router.py`'s **GET-only contract**, `queue_tickets`, any `/checkin` route | **F33** | **DO NOT TOUCH.** F19's webhook is a **new sibling router** (D9) precisely so it never needs an edit here. |
| `app/models/constants.py`, `app/main.py`, both apps' `i18n/he.ts` + `ar.ts`, `storefront/src/router.tsx` | **SHARED** | **Append only.** Never reorder, never reformat, never re-wrap another feature's lines. Rebase on `main` before every push. |
| Migration revision id | **contested** | Claimed at Task 2 as **`0015` / `down_revision = "0014"`** for branch coherence. **RENUMBERED to `0017` / `"0016"` at rebase** (C1). |

### Not in F19

| Not in F19 | Whose |
|---|---|
| A real hosted payment page, a provider adapter, `lemonsqueezy` wiring | **F18** — a sibling, not a dependency. It also **deletes** Task 14's `/fake-pay` page |
| `refund()`, `refund_due` / `refunded` / `forfeited` writers, any actual refund | **F29** (D16) |
| A `/manage/payments` console section, a payments nav row, an `OWNER_ONLY` edit | **F29's shape** (D18) — F19 adds **one field** to a shipped row |
| A never-received-webhook warning, `last_webhook_at`, a registration check | **the pilot operator's checklist** (Risk 1, decided) |
| Partial payments, instalments, saved cards, owner-side "mark as paid" | not in the product |
| Receipt / קבלה generation | the boutique's; **F21's audit row** |
| KMS, the retention sweep, an encryption seam | **F20** (F17 Gate 1 Q2/Q3) |
| A Redis-backed limiter for the webhook route | **F21** |
| Wait-time analytics, `bookings.source`, walk-in create | **F50 / pre-decided #28** |
| A realtime vendor, a socket, a websocket for the return page | **pre-decided #23** |

If a task's diff grows a staff role, a queue ticket, a refund status or a second poll target, it has left F19.

---

## Run the db suite locally anyway — this is the highest-leverage instruction in this plan

The run's standing constraint is "no Docker locally", and `tests/conftest.py:81-94` fails the whole db suite with `DOCKER_HELP` when the daemon is down. **F34's builder did not accept that and got all three gating jobs green on the first CI run; F57's builder followed it.** F19 has more `db`-marked surface than either — five race tests, two crash recoveries, a five-statement migration and a sweeper — so the payoff is larger, and so is the cost of skipping it.

**F19 has three deparse hazards, not one.** Task 2 widens the `bookings.status` CHECK, which **red-fails F34's shipped `_STATUS_CHECK_DEF` pin by design** (see Task 2), and Postgres does not store the text you wrote: it deparses `CHECK (status IN (…))` into `CHECK ((status = ANY (ARRAY['…'::text, …])))`. Transcribing the migration's own SQL into that assertion pins **nothing**. Same for `bookings_cancelled_by_check`, `message_log_kind_check` and `idx_bookings_pending_payment`'s `indexdef`.

**Do this, in order:**

1. **Try Docker first.** `make test-db`. If the daemon is up, testcontainers just works and nothing below is needed.
2. **Otherwise stand up a throwaway cluster OUTSIDE the repo** — never inside it, or the data directory lands in `git status`:
   ```
   PGDIR="$TMPDIR/f19-pg"            # or the session scratchpad; NOT the repo
   initdb -D "$PGDIR" -U postgres
   pg_ctl -D "$PGDIR" -o "-p 55433 -k $PGDIR" -l "$PGDIR/log" start
   createdb -h "$PGDIR" -p 55433 -U postgres boutique
   ```
   Use a port F57's builder is not already on (they used 55432).
3. **Point the session fixture at it with a LOCAL, UNCOMMITTED edit** to `tests/conftest.py:81-94` — `postgres_url` is session-scoped in a conftest, so a plugin cannot override it.
4. `make test-db`. **Capture every deparsed literal by running it**, not by typing what you think it says:
   ```sql
   SELECT pg_get_constraintdef(oid) FROM pg_constraint
    WHERE conrelid = 'bookings'::regclass AND conname IN ('bookings_status_check','bookings_cancelled_by_check');
   SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_bookings_pending_payment';
   ```
5. **Revert the conftest edit and tear the cluster down before committing.** `git diff --stat backend/tests/conftest.py` must print nothing.

**And one mutation check per race claim**, the F34/F57 precedent that matters most here: fold D6's two claims into two transactions and confirm race row #13's test turns red **and nothing else does**. A concurrency test that stays green with its mechanism removed proves nothing, and this feature has five of them.

⚠ If step 2 is skipped, expect a first CI red on a test bug and budget for it (`.memory/boutique-ci-first-run-surprises.md`). Check `continue-on-error` on the job before believing a red.

---

## Task 0 — This plan, and the seven spec amendments
`.planning/plans/deposit-booking-flow.md` (this file), `.planning/specs/deposit-booking-flow.md`

- Amend **every occurrence of "0014"** in the spec — the migration section header, D1, D2, D6 claim 2, D8, MD2, MD5, the API-contract note — to **"this feature's migration"**, with one paragraph carrying C1's build-vs-rebase rule and the three-way race table. **Do not substitute the literal `0017`**: it is wrong the moment a fourth feature lands one first.
- Amend the migration section with the **single-head guard** (C1) as a sixth deliverable, and record that it is **fast, not `db`-marked**.
- Amend **D1's blast-radius table** and D2/D5's inline citations with the shifted `bookings.py` addresses (**C2**); amend **D14** with the shifted `dashboard/service.py` addresses (**C3**), keeping the ruling and the count of six.
- Amend the **Wiring** line and D11a with `main.py:709-712`, and add the `_register_spas` ordering constraint and the 13-limiter count (**C4**).
- Amend **D1** with C5's append-only rule on `constants.py` and the four enums F19 touches, naming F57's concurrent `StaffRole` edit.
- Amend the **Testing** section's late-settlement bullets: expiry is driven **through `poll_once`**, never by hand-setting `row.status`, and F17's `test_payments_service.py:921-925` is left as it is (**C6**).
- Amend the spec to state that **`bookings.source` does not exist** and F19 neither reads nor writes it (**C7**).
- Add a **Design** line to the spec header pointing at `.planning/design/screens/deposit-payment/`, and record that **no prototype and no `design-critic` pass** are run, under Interview Q2 and F57's precedent.
- **Done when**: all seven are in the spec and this file is committed. No code, no tests.
- Commit: `docs(planning): F19 implementation plan — Gate 2 self-approved`.

## Task 1 — The design deck and the copy deck (no prototype, no `design-critic`)
`.planning/design/screens/deposit-payment/design.md` (**new**), `.planning/design/screens/deposit-payment/copy.md` (**new**)

**First, because Tasks 15–17 consume the copy table and nothing else is the canonical key list.** Interview Q2 named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix — and a hand-off screen plus a poll plus three terminal states is neither. **F57 set the precedent in its own spec header**: the *gate* goes away (the prototype, the `design-critic` pass, the user's pause), the *design work* does not.

**`design.md`** — the states, and every one of them is a state the storefront can actually be in:

- **The five payment states** (spec "Frontend changes"): hand-off (with the manual-link fallback for a blocked redirect), awaiting-webhook, paid, declined, expired. For each: what it says, what it does, what it polls, and what stops it.
- **The bride's manage page**, two branches: `pending_payment` (awaiting payment, carrying the checkout link, cancel and confirm-attendance **suppressed**) and MD3's cancel-consequence swap.
- **The owner console**, three markers on one field (D18): a `payment_status` badge, action-needed for **paid-with-no-seat**, action-needed for **MD4's booked-without-a-deposit**, and MD1's reschedule action on a cancelled-but-paid booking.
- **The a11y floor**: `<bdi dir="ltr">` on every agorot amount (D15) and on every session id ever rendered; 44×44 on the pay CTA and the retry; the poll's `role="status"` region changes on a **terminal** state only, never per tick — the F34 D11 rule, for the F34 reason, on a screen a bride watches while her card is being charged.
- **§8 P-decisions, each resolved here rather than parked**: the poll interval and its attempt ceiling; whether the awaiting screen shows the amount (**yes** — she is looking at a page about money); whether the declined state shows the provider's reason (**no** — `payments.error` is scrubbed and truncated and never reaches a body, `main.py`'s containment rule).

**`copy.md`** — one table per surface, `he` column canonical, every row also giving the `ar` value (= the approved Hebrew, never `""`). It carries **at minimum**:

- the five payment-state strings;
- **`manage.cancelConsequenceDeposit`** = **הפיקדון מטופל בהתאם למדיניות הביטולים של הסלון.** — MD3's neutral interim, with a ⚠ row recording that the **two window-specific variants are the one PARKED item** and that this key's *value* is what they replace, a string swap and nothing structural;
- **`booking.statusPendingPayment`** for `manage/src/lib/booking.tsx`'s badge — without it a fifth status renders the **literal LTR string `pending_payment`** inside a Hebrew RTL console, via that file's documented raw-value fallback (`:22-26`);
- MD2's `PAYMENT_RECEIVED_NO_SLOT` SMS body, transcribed **verbatim from spec MD2** — it is already approved there and re-drafting it would be re-deciding a money decision;
- the owner-console marker strings.

**No prototype.** Recorded in `design.md`'s status line beside what that costs: there is no clickable artifact, so the ASCII state diagrams are the sole visual source, and a note above them says **the diagrams are drawn LTR for legibility in a Markdown file — the rendered pages are RTL, so inline-start is the physical right.** F57's Task 1 had to add that note retroactively; F19 writes it the first time.

- **Done when**: every string Tasks 15–17 render exists in `copy.md` with both columns; `design.md` §8 carries a resolution for every `P-`; the MD3 park is recorded as a **value** swap on a key that ships; `grep -n "TODO\|PROPOSED" .planning/design/screens/deposit-payment/` returns nothing.
- Commit: `docs(design): the deposit payment states, the manage branches and the owner markers`.

---

# Part I — the backend

## Task 2 — The migration and the enums/models, as ONE atomic change (C1, C5, D1, D8, MD2, MD5)
`Backend/migrations/versions/00NN_deposit_booking_flow.py` (**new**), `Backend/app/models/constants.py`, `Backend/app/models/payment.py`, `Backend/tests/test_migrations.py`

**The halves ship together and this is not a preference.** Without `BookingStatus.PENDING_PAYMENT` every `allowed_from=('pending_payment',)` in Tasks 3–10 is an `AttributeError`; without `Payment.redirect_url` every `.values(redirect_url=…)` fails to compile; and `models/payment.py` declares every column explicitly with **no model↔migration parity test anywhere in `Backend/tests/`**. Migration + constants + model is the `0008_bookings.py` / `models/booking.py` pattern and F34's Task 2 shape.

**Resolve the revision id at build time.** `cd "<repo>/Backend" && uv run python -m alembic heads` → **`0014 (head)`** as of 2026-08-03. **Per C1 the file is written as `revision = "0015"` / `down_revision = "0014"` and renumbered to `0017` / `"0016"` at rebase** — three edits, named again in Task 18.

**Five statements**, and the column-add style is `0014_booking_check_in.py:23-36`'s: a comment block stating each deliberate absence so a reviewer can check the list is **complete** rather than merely short.

```sql
-- 1. D1. Both partial unique indexes and every occupancy read use
--    `status <> 'cancelled'`, so a held seat is an occupied seat with NO index
--    change and NO occupancy-query change. That is the whole design.
ALTER TABLE bookings DROP CONSTRAINT bookings_status_check;
ALTER TABLE bookings ADD CONSTRAINT bookings_status_check
  CHECK (status IN ('confirmed','cancelled','no_show','completed','pending_payment'));

-- 2. MD5. A third attribution bucket, so an abandoned checkout is not
--    customer flakiness. The rate exclusion is a SEPARATE edit (Task 12).
ALTER TABLE bookings DROP CONSTRAINT bookings_cancelled_by_check;
ALTER TABLE bookings ADD CONSTRAINT bookings_cancelled_by_check
  CHECK (cancelled_by IN ('customer','owner','expired'));

-- 3. D8. The hosted-page URL beside the session id, so the converge path
--    returns a WORKING link instead of None (D11b).
ALTER TABLE payments ADD COLUMN redirect_url TEXT;

-- 4. MD2, UNCONDITIONAL. The question form made this conditional on a ruling;
--    MD2 is that ruling.
ALTER TABLE message_log DROP CONSTRAINT message_log_kind_check;
ALTER TABLE message_log ADD CONSTRAINT message_log_kind_check
  CHECK (kind IN ('otp','confirmation','reminder','owner_cancel','owner_reschedule',
                  'payment_received_no_slot'));

-- 5. D6 claim 2's orphan sweep. Partial on a status that holds a handful of
--    live rows, so it costs nothing and turns a per-tick table scan into an
--    index scan.
CREATE INDEX idx_bookings_pending_payment ON bookings (tenant_id, created_at)
  WHERE deleted_at IS NULL AND status = 'pending_payment';
```

**CHECK widening is DROP + ADD, per `0013_lemonsqueezy_provider.py:24-30`** — a CHECK's expression cannot be altered in place, and 0008/0010 declared theirs inline on the column so PostgreSQL auto-named them `<table>_<column>_check`. Spell each name once as a module constant, and **carry no `IF EXISTS` on the DROP in either direction**, for 0013's stated reason: a rename upstream must fail loudly instead of quietly leaving the column unconstrained.

**`downgrade()` is always written**, and it narrows honestly: drop the index, drop the column, and re-add all three CHECKs at their **old** value sets **without** `IF EXISTS`. A row holding `pending_payment` or `cancelled_by='expired'` must **block** the narrowing rather than sit past a constraint its own value violates — 0013's downgrade comment is the precedent and says so in its own words.

**Deliberately absent**, each as a comment:
- **No `GRANT`.** 0008 and 0007 issued table-level grants; table grants are column-agnostic and no column-level grant was ever issued on either table. (The `ALTER DEFAULT PRIVILEGES` gotcha in `.claude/CLAUDE.md` is about newly **created** tables.)
- **No `enable_tenant_rls`.** RLS is a table property, already forced. **F19 adds no table — `test_every_tenant_id_table_has_forced_rls` staying green unedited is the assertion that none snuck in.**
- **No `_updated_at_trigger`.** Both triggers exist.
- **No change to `idx_bookings_slot_seat_unique` or `idx_bookings_tenant_customer_starts_unique`**, and that is D1's entire argument made mechanical.

**Same commit — `constants.py`, append-only per C5:** `BookingStatus.PENDING_PAYMENT` (rewriting the `:47-54` comment from *"E4 widens it"* to the past tense, F57's precedent for recording that a reserved slot was filled rather than deleting the reservation); `BookingCancelledBy.EXPIRED`; `MessageKind.PAYMENT_RECEIVED_NO_SLOT`; and six `AuditAction` members with the block comment every prior block carries (*`audit_log.action` is plain TEXT with no CHECK (0003), so these need no migration*): `DEPOSIT_HOLD_OPENED`, `DEPOSIT_HOLD_EXPIRED`, `DEPOSIT_LATE_HONOURED`, `DEPOSIT_LATE_UNRESOLVED`, `GATEWAY_WEBHOOK_UNMATCHED`, `GATEWAY_UNAVAILABLE_AT_CHECKOUT`.

**Same commit — `models/payment.py`:** `redirect_url: Mapped[str | None] = mapped_column(Text, nullable=True)` beside `provider_session_id` (`:34`), carrying D8's one-line reason.

**Tests (`db`-marked unless stated, appended to `test_migrations.py`)** — that file's conventions: round-trips go **last among the schema-mutating tests**, own no fixtures, and wrap the downgrade in `try/finally: command.upgrade(cfg, "head")`.

1. **⚠ THE ONE THAT RED-FAILS BY DESIGN.** `test_the_booking_check_in_migration_leaves_the_status_check_and_both_unique_indexes_alone` (`:453-474`) pins `_STATUS_CHECK_DEF` (`:400-403`) byte-identical to the **four-value** deparsed CHECK. **F34 wrote it predicting this exact moment**, in its own docstring: *"when E4 widens the CHECK for 'pending_payment' it collides with a pinned literal and a deliberate review, instead of colliding with nothing."* This task is that deliberate review. **Update `_STATUS_CHECK_DEF` to the five-value deparsed literal, captured by running `pg_get_constraintdef`, never transcribed.** The two index literals (`:404-414`) are **NOT** touched — them staying byte-identical is D1's promise, and the test's name and docstring gain one sentence recording that the widening was reviewed here.
2. `pg_get_constraintdef` for **`bookings_cancelled_by_check`** and **`message_log_kind_check`** pinned byte-identical **after this feature's migration** (keyed to `head`, never a revision id).
3. `payments.redirect_url` is a **nullable `text`** on `payments`, from `information_schema.columns` — the `_check_in_column` helper's shape.
4. `idx_bookings_pending_payment` **exists and is partial**, `indexdef` carrying both `deleted_at IS NULL` and `status = 'pending_payment'` — captured, not typed.
5. The widened CHECKs **admit** `'pending_payment'` / `'expired'` / `'payment_received_no_slot'` and **still reject** an unknown value — the `:74-93` two-probe shape, **every probe rolled back** (F57's C6 rule: a committed `pending_payment` row would redden the downgrade tests of every feature sharing the session-scoped container).
6. `test_migration_00NN_round_trips` — upgrade applies, downgrade removes **all five**, upgrade re-applies. **Both directions**, 0013's rule: a downgrade that silently no-ops stays green while shipping an irreversible migration.
7. **The downgrade's honest failure**: with a `pending_payment` booking present, the narrowing re-`ADD CONSTRAINT` is refused. Rolled back.
8. **`test_the_migration_history_has_exactly_one_head` — NOT `db`-marked** (C1). Goes beside `test_running_env_py_does_not_disable_the_app_logger` (`:502`), the file's other fast test.

- **Done when**: `make lint` clean (ruff + `mypy app tests`), `make test` green **including the new head guard**. ⚠ The real proof runs on CI, or locally per the § above; without it, mypy resolving `BookingStatus.PENDING_PAYMENT` and `Payment.redirect_url` at every new call site is the whole local signal.
- Commit: `feat(payments): pending_payment, the expired attribution, redirect_url and the hold-orphan index`.

## Task 3 — The repository writers (TDD, `db`-marked) (D2, D5, D8, D17)
`Backend/app/db/repositories/bookings.py`, `Backend/app/db/repositories/payments.py`, `Backend/tests/test_booking_repositories.py`, `Backend/tests/test_payment_repositories.py`

**This is the subtlest backend part and it gets its own task.** Everything else in Part I is orchestration over these five statements.

### `BookingsRepository.cancel` gains one defaulted keyword (D2)

```python
async def cancel(self, session, tenant_id, booking_id, *, at, by,
                 not_before: datetime | None = None,
                 allowed_from: tuple[str, ...] = (BookingStatus.CONFIRMED.value,)) -> Booking | None
```

The `set_status` shape (`:431-440`). `Booking.status == CONFIRMED` at `:510` becomes `Booking.status.in_(allowed_from)`. **Defaulted, so every existing caller is byte-identical** — `owner.cancel`, `manage.cancel`, and F34's tests all keep passing unedited, which is the assertion that the widening changed nothing it should not have. The sweeper passes `(PENDING_PAYMENT,)`.

**Declined**: a new `expire_hold` method — a *second* writer of `cancelled_at`/`cancelled_by`, which is exactly what D2 refuses. **Declined**: `set_status(to='cancelled')` — it never writes the cancel evidence, **by design**, and its docstring says so.

### `BookingsRepository.rebind` — NEW, and it is ONE statement (D5)

```python
async def rebind(self, session, tenant_id, booking_id, *, seat_index: int,
                 allowed_from: tuple[str, ...], not_before: datetime) -> Booking | None:
    #  UPDATE bookings
    #     SET status='confirmed', seat_index=:seat_index,
    #         cancelled_at=NULL, cancelled_by=NULL
    #   WHERE tenant_id AND id AND status IN :allowed_from
    #     AND starts_at > :not_before AND deleted_at IS NULL
    #  RETURNING id
```

**It is NOT `set_status`, and the reason is a live-seat bug rather than a style preference.** `set_status` writes `.values(status=to)` and nothing else (`:469`), **by design** — its docstring makes "never writes `cancelled_at` / `cancelled_by`" a commitment shared with three other callers. It cannot carry `seat_index`. Splitting the rebind into two statements would open a window where the row reads `confirmed` at a **stale seat index** — and because `create_booking` picks the **lowest free index** and therefore hands freed seat numbers back out (`booking/service.py:320-327`), that stale index is very likely **another bride's seat**. One statement or nothing.

The other three properties, each with its own reason:
- **The cancel evidence is cleared.** A row reading `confirmed` while carrying cancel evidence is the exact defect D2 declines `set_status` over, and both columns feed F52's attribution and F20's compliance read. The *record* of the cancellation survives in the `GATEWAY_LATE_SETTLEMENT` audit row, in `payments.error` (*"late settlement: hold was expired"*), and in the new `DEPOSIT_LATE_HONOURED` row.
- **`not_before=now`.** Every sibling writer that reinstates or re-authorises carries a clock bound — `cancel`'s (`:519`), `set_manage_token_hash`'s (whose docstring says a booking that stopped being confirmed-and-future *"cannot be handed a fresh LIVE control token"*), `reschedule`'s (`:554`), `set_status`'s (`:461-466`). Without it a delivery days late flips a **past** booking to `confirmed`, mints a fresh manage token, and texts the bride "your appointment is confirmed" for a date that has passed while silently re-occupying a seat in a past slot.
- **`allowed_from=('cancelled','pending_payment')`.** `cancelled` is the ordinary case. `pending_payment` is the **belt** for D6's ordering race: if the sweeper's payments UPDATE has committed but its booking cancel has not been observed, the booking is still `pending_payment`, and a narrow `('cancelled',)` would match nothing and file a **false "seat taken" alert** on a seat that is in fact free. Still one guarded statement, still exactly-once.

### `PaymentsRepository` — three additions and one edit (D8, D17, D18)

- **`settle_late(session, tenant_id, payment_id, *, provider_transaction_id, paid_at) -> Payment | None`** — the `settle` shape verbatim (`:81-123`) with `WHERE status = 'expired'` and `.values(status='paid', paid_at=…, provider_transaction_id=…, redirect_url=None)`. It both performs F17's Q4 ruling and **re-arms `by_provider_transaction_id` for every subsequent redelivery**.
- **`by_booking_ids(session, tenant_id, booking_ids) -> dict[UUID, Payment]`** — D18's batch read. `PaymentsRepository` has **no batch read today**; its whole surface is the seven methods listed in §"Citations". One `WHERE booking_id = ANY(:ids)`, riding `idx_payments_tenant_booking` (`0012:123-126`), returning a dict keyed by `booking_id`. **Empty list in ⇒ empty dict out, with no statement issued** — `list_day` on an empty day must not emit `IN ()`.
- **`insert` gains `redirect_url: str | None = None`** — defaulted, so F17's own callers and tests are byte-identical.
- **`settle` gains `redirect_url=None` in the SAME `.values()`** (D8). Every exit from `pending` blanks it: `settle`, `settle_late`, and the sweeper's claim 1. F20 inherits **no new blanking obligation**.

### The rule that governs all five statements

**ALWAYS read the `.returning()` scalar. NEVER re-read the row to decide who won.** `cancel`'s own docstring (`:497-511`) documents why, verbatim: ORM-enabled DML with `evaluate` synchronization stamps the SET values onto the identity-mapped instance **whatever the database matched**, `expire_on_commit=False` (`db/session.py:66`) keeps it loaded, and `by_id` hands that same instance back. A caller inspecting the returned row cannot distinguish its own write from anyone else's. Cite that docstring in each new method's comment so the next reader does not rediscover it.

**Tests written first**, all `db`-marked, in the existing modules on their `_factory` / `tenant_session` idioms:

- `cancel` with the **default** `allowed_from` behaves byte-identically on `confirmed`, `cancelled`, `no_show`, `completed` — the widening-changed-nothing assertion;
- `cancel(allowed_from=('pending_payment',))` fires on a held booking and **matches nothing on a `confirmed` one** — the sweeper must never free a paid seat;
- `rebind` on `cancelled` → `confirmed` at the given seat with **`cancelled_at` and `cancelled_by` both NULL** (the assertion that fails if the writer forgets D5's second property);
- `rebind` on `pending_payment` → same (the D6 belt);
- `rebind` on `confirmed`, on `no_show`, on a **past** `starts_at`, and on an unknown id → **`None`**, nothing written;
- `rebind` into an occupied seat raises **`IntegrityError`** from `idx_bookings_slot_seat_unique`, and into the bride's own re-booked instant raises it from `idx_bookings_tenant_customer_starts_unique` — **both are asserted here**, because Task 8 catches them and the catch must be proven to have something to catch;
- `settle_late` on `expired` → `paid` + `paid_at` + txn id + `redirect_url IS NULL`; on `pending` → `None`; on `paid` → `None`;
- `insert(redirect_url=…)` stores it; `settle` blanks it;
- `by_booking_ids` returns only this tenant's rows, keyed correctly, **empty in ⇒ empty out**.

- **Done when**: `make lint` clean, `make test` green (`db`-marked → deselected locally), `make test-db` green **on CI or against the local cluster**.
- Commit: `feat(booking): the rebind writer, a widened cancel guard and the late-settlement statement`.

## Task 4 — `is_connected` and the `deposit_due` predicate (TDD, fast) (D10, D19)
`Backend/app/payments/service.py`, `Backend/app/storefront/service.py`, `Backend/app/booking/service.py`, `Backend/tests/test_payments_service.py`, `Backend/tests/test_storefront_service.py`

**This task gives `deposits_enabled` its FIRST backend reader, ever.** `grep -rn 'deposits_enabled' Backend/app` returns exactly two hits and both are about *validating* the toggle — `boutique/schemas.py:50` and the allow-list at `boutique/validation.py:58`. Nothing reads it. Without this task a boutique's own deposit off-switch still does nothing after F19 ships.

**`GatewayCredentialService.is_connected(tenant_id, session) -> bool`** runs the **USE path's three checks**, not a weaker one:

1. `gateway.is_configured` **and** `secret_box.is_configured` — what `_require_provider` (`:342-348`) checks, but read as booleans rather than by calling it, because `_require_provider` **raises** `GatewayNotConfiguredError` / `SecretBoxNotConfiguredError` and this is a predicate, not a gate;
2. `active_for_provider(session, tenant_id, provider=settings-derived)` returns a row;
3. **`row.status == GatewayCredentialStatus.VALID.value`** — what `credentials_for` (`:316-318`) additionally requires.

**The bare `active_for_provider` read the spec's previous draft specified filters only tenant + provider + `deleted_at IS NULL`** (`gateway_credentials.py:55-63`). A boutique whose credential was flipped to `invalid` by `revalidate`, or a deployment with the secret box unconfigured, would be **shown the deposit and then meet a 409 or a 503 at create** — the dead-calendar outcome F17's Q1 ruling exists to prevent, and **not** covered by MD4, which is about `GatewayUnavailableError` on a healthy account.

It takes the caller's session rather than opening one — `StorefrontService.list_appointment_types` already has one open (`storefront/service.py:239-240`), so this is **one extra indexed statement on an already-open connection** on an already-`_throttle`d anonymous endpoint. It takes neither limiter, touches no key material, and returns no ciphertext.

**One helper computes `deposit_due`**, and both callers use it:

```
deposit_due = tenant.settings.toggles.deposits_enabled
          AND appointment_type.deposit_required
          AND appointment_type.deposit_amount_agorot > 0
          AND is_connected(tenant_id, session)
```

Called by **`public_appointment_type`** (the disclosure) and by **`create_booking`** (the flow), **so the two cannot disagree**. The master toggle wins over the per-type flag: a boutique who switches deposits off keeps taking bookings and stops collecting, exactly as F17's Q1 ruled for the not-connected case.

**Declined**: injecting the full `GatewayCredentialService` surface into the storefront (it owns two rate limiters and the secret box). **Declined**: caching the flag on `TenantContext` (`tenancy/resolver.py:8-9` defers caching to E5, in its own docstring). **Declined**: hiding the deposit client-side.

⚠ **Flagged to the reviewer**: `deposit_required` / `deposit_amount_agorot` are disclosed to anonymous visitors **today** (`storefront/schemas.py:171-186`), so hiding them is a visible change to a live public contract. It is F17's Q1 applied, not a new decision.

**Tests here** (fakes, no Postgres, on `test_storefront_validation.py`'s fake-session scaffold — a statement escaping to a real session raises rather than passing silently):
- deposit fields **omitted** with no credential row; **omitted** with a row whose status is `invalid`; **omitted** with an unconfigured secret box; **emitted** with a valid row and a configured pair — the four cases, and the middle two are the ones the previous draft got wrong;
- **`deposit_due` is false with `deposits_enabled` off**, on a `deposit_required` type with a connected gateway — **the toggle's first test, ever**;
- `deposit_due` false with `deposit_amount_agorot` 0 or NULL;
- the disclosure and the flow return the **same** answer for the same tenant/type — asserted by calling both helpers in one test, which is what makes "cannot disagree" mechanical.

- **Done when**: `make lint` + `make test` green, **locally and on CI**.
- Commit: `feat(payments): is_connected on the use path, and deposit_due's single predicate`.

## Task 5 — `PaymentService`: `honour_late_settlement`, `redirect_url`, and the singleton (TDD, fast) (D8, D11b, D20)
`Backend/app/payments/service.py`, `Backend/app/main.py`, `Backend/tests/test_payments_service.py`

**`PaymentService.honour_late_settlement(tenant_id, *, payment_id, transaction_id, paid_at) -> Payment | None`** wraps Task 3's `settle_late`. **The route calls the SERVICE, never the repository** — `models/payment.py:12-13` states *"`PaymentService` is its single writer — no adapter and no future caller can skip this row"*, and F19 is the first feature that could break that invariant. It would break it on day one if the webhook route reached into `PaymentsRepository`. Same rule as `open_deposit` and `settle_from_webhook`.

`None` back means a prior delivery already honoured it → the caller stops. That is D5 step 1.

**`open_deposit` stores and returns the link (D8).** Two edits inside the existing method:
- the insert at `:509-517` passes `redirect_url=payment_session.redirect_url`;
- **the converge return at `:500-505` returns the STORED one** — `DepositHold(payment=existing, redirect_url=existing.redirect_url, created=False)`. Its current comment explains that `None` was deliberate *"to force F19 to decide what a retry does"*; **rewrite it to record the decision** rather than deleting it. This one line is what makes D11b's replay return a working link instead of `None`, and it is what the storefront's declined-state retry copy actually rests on.

**The singleton, same commit** (`main.py`):

```python
app.state.payment_service = PaymentService(
    get_session_factory(),
    gateway=app.state.payment_gateway,
    credentials=app.state.gateway_credential_service,
)
```

and **DELETE the placeholder comment at `:709-712`** in the same commit. Its own text is the reason: *"a wired singleton with no consumer is a thing a reviewer has to check rather than a thing that works"* — leaving it beside a wired singleton inverts it into a lie.

**Tests** (fast, fakes): `honour_late_settlement` on an `expired` row returns the settled row; on `pending` and on `paid` returns `None` and writes nothing; `open_deposit` stores the redirect on insert and **returns the stored value on the converge path with no `create_session` call at all** (assert on the fake gateway's call count — the converge path's whole promise); and `app.state.payment_service` is present after `create_app()`.

- **Done when**: `make lint` + `make test` green, **locally and on CI**.
- Commit: `feat(payments): honour_late_settlement, the stored redirect and the PaymentService singleton`.

## Task 6 — The two new public routes on a new sibling router (TDD, fast) (D9, D13)
`Backend/app/payments/webhook_router.py` (**new**), `Backend/app/payments/schemas.py`, `Backend/app/main.py`, `Backend/tests/test_payment_webhook_api.py` (**new**)

**A NEW SIBLING ROUTER on `/storefront`, not routes on `storefront_router`.** That router carries a per-tenant `_throttle` (`storefront/router.py:103-137`) which counts **successes** (`record_failure` on the happy path, by design) — it would 429 a provider's retry burst and turn a transient outage into **permanently unconfirmed bookings and unrefunded charges**. The `otp_router` / `booking_router` precedent is exactly this shape and `booking/router.py:1-9` states the pattern in its own docstring. Registered in `main.py` after `booking_router` (`:1054`) and **before `_register_spas(app)` (`:1057`)** — C4.

### `POST /storefront/payments/webhook`

**Raw body bytes, HMAC only, anonymous, cookie-blind, CSRF structurally N/A.** The handler takes `await request.body()` and hands those bytes to `settle_from_webhook` — **never a re-serialized model**; `payments/base.py` types it `body: bytes` for exactly this reason, and a re-serialization changes byte order and breaks every signature. Tenant from Host, so each boutique registers `https://{her-slug}.modryn.co.il/storefront/payments/webhook` in her own provider account, which works *because* credentials are per-tenant.

**200 on EVERY non-forgery outcome** — paid, decline, redelivery, duplicate transaction, late settlement. A provider reads a non-2xx as "retry", and retrying a decline forever is what D25's 400-vs-503 argument is made of.

**400 on three conditions, and they are three different events** (D9's table):

| Condition | Site | Evidence today | F19 |
|---|---|---|---|
| Bad/forged signature | `service.py:542-555` | `GATEWAY_WEBHOOK_REJECTED`, committed before the raise | **400.** Correct as shipped. |
| Amount mismatch | `:706-728` | `GATEWAY_AMOUNT_MISMATCH` + `payments.error`, own transaction | **400**, unchanged. |
| **`by_provider_session_id` returned `None`** | `:571-575` | **nothing at all** | **400 + a NEW audit action** |

That third row is the dangerous one and it is the one F19 fixes. It raises **inside `async with tenant_session`**, which is `session.begin()` (`db/tenant.py:25`) — so **the transaction rolls back and real money moves with nothing but a 400 in an access log**. F19 adds **`GATEWAY_WEBHOOK_UNMATCHED`**, written with the **commit-before-raise** pattern (`.memory/patterns/commit-before-raise-in-tenant-session.md`), the same shape as `GATEWAY_WEBHOOK_REJECTED` — three lines in `payments/service.py`, no migration. It stays **400** deliberately: a provider that retries is exactly what you want when the row might yet appear (a redirect that beat the insert), and the audit row is what makes the permanent case findable.

### `POST /storefront/booking/payment-status`

Body `{ payment_session_id }` → `{ booking_status, payment_status, paid_at }`. POST for a read, the `/booking/lookup` precedent (`booking/router.py:117-121`).

**Keyed on `payment_session_id`, NOT the manage token, and the token cannot work three times over:**
1. **`BookingCreateResponse` carries no token** (`booking/schemas.py:40-49` — six fields, verified);
2. **the deposit path SUPPRESSES the confirmation SMS** (Task 9), so she never receives the manage link either;
3. **`set_manage_token_hash` overwrites the hash unconditionally** while `by_manage_token_hash` is the only lookup — so the poll would **start 404-ing at precisely the moment it should return `paid`**. A bride who paid, sitting on a spinner forever, on the money surface.

The session id costs no new column, no new secret and no rotation hazard: it is **already client-visible by construction** (embedded in the hosted-page URL her browser is about to visit — `payments/fake.py:121`, and real providers do the same), `by_provider_session_id` already exists and is tenant-scoped (`payments.py:70`), guessing one means guessing a provider-minted opaque id, the response carries **no PII**, and the converge path returns the same id so a retry polls the same hold.

**Tests here** (fast, on the `test_booking_api.py` anonymous-route template):
- the webhook route is **anonymous** (200 with no cookie), sets no cookie, and is **not** under `CsrfOriginMiddleware.PROTECTED_PREFIX = "/manage"` (`csrf.py:16`);
- **it reads the raw body** — the regression guard is a test that re-serializes the JSON and asserts the signature then **fails**;
- **D9's full status table**: 200 on paid, decline, redelivery, duplicate txn, late settlement; **400 on bad signature, 400 on amount mismatch, 400 on an unmatched session id — and the last writes `GATEWAY_WEBHOOK_UNMATCHED`**, asserted on `audit_log` (which is what proves the commit-before-raise, since a rolled-back transaction leaves nothing);
- payment-status returns the triple for a known session id, **404 for an unknown one**, and **nothing about any other tenant's** session id;
- the route is **not** in `OWNER_ONLY` and needs no edit to it — `test_staff_role_gating.py`'s default-deny walker filters on `path.startswith("/manage")` (`:149, :196`), so this route is structurally outside it and will not red-fail the build;
- `test_no_route_is_registered_twice_across_routers` passes **unedited** — four routers already mount `/storefront` and a duplicated `(method, path)` would silently shadow.

- **Done when**: `make lint` + `make test` green, **locally and on CI**.
- Commit: `feat(payments): the webhook route, the payment-status poll and GATEWAY_WEBHOOK_UNMATCHED`.

## Task 7 — The confirm transaction (TDD, `db`-marked) (D3, D4, D12, D13)
`Backend/app/payments/webhook_router.py`, `Backend/app/booking/comms.py`, `Backend/tests/test_payment_webhook_db.py` (**new**)

**Branch on `settlement.payment.status`, NOT on `newly_settled`.** `Settlement` carries two fields and no discriminator (`payments/service.py:108-111`), and **four distinct outcomes return `newly_settled=False`**: a redelivery of an already-settled txn (`:569`), a decline, a concurrent delivery that lost, a *different* txn against a paid row, and a late settlement. An amount mismatch **does not return at all** — it commits its evidence in its own transaction and raises.

| `settlement` | F19 does |
|---|---|
| `True`, status `paid` | confirm, rewrite the reminder, send the confirmation SMS |
| **`False`, status `paid`** | **run the SAME guarded confirm anyway** — the crash recoverer |
| `False`, status `pending` | nothing — a decline. The sweeper frees the seat on its own clock |
| `False`, status `expired` | the honour path (Task 8) |
| `False`, anything else | nothing, and log. Unreachable today; Risk 7 names why it may not stay so |

### The confirm is one guarded UPDATE, and *that* is the idempotency key

```python
set_status(session, tenant_id, booking_id,
           to=BookingStatus.CONFIRMED.value,
           allowed_from=(BookingStatus.PENDING_PAYMENT.value,))
```

`None` back means **a prior delivery already won** → no SMS, no reminder rewrite, no audit row, no owner alert. Exactly one delivery of N can win, because the predicate is evaluated by Postgres under the row lock — not by our bookkeeping.

**And running it on `newly_settled=False` + status `paid` too is the crash recoverer for race row #11.** `settle_from_webhook` commits `payments → paid` inside **its own** `tenant_session` and returns; `PaymentService` opens sessions from its own factory and the route gets only a `Settlement` back, so F19's confirm is **necessarily a second transaction**. If the process dies in that window, the payment is `paid` and the booking is stuck at `pending_payment`: her card is charged, her seat is held forever (`active_seats_at` counts it), no SMS, no reminder, no alert, and 0009's per-customer index blocks her from rebooking that instant. Against an **already-confirmed** booking the same statement matches nothing and does exactly nothing; against a **stranded** one it fires once and repairs it. **Idempotent by construction, and the repair is free.**

**F17's replay guard does not cover this.** `provider_transaction_id` is written by exactly one statement — `settle`'s guarded UPDATE (`payments.py:112-118`) — so `by_provider_transaction_id` only ever short-circuits a redelivery of an **already-settled** transaction. The decline, mismatch, duplicate and late branches all call `record_error` and nothing else.

### Inside the SAME transaction: the token and the reminder (D12, D13)

Mint one manage token, `set_manage_token_hash`, and call `upsert_reminder(..., token=token)` through **a NEW defaulted keyword** `token: str | None = None` on `booking/comms.py:89` — defaulted, so F15's `reschedule_reminder` caller is unchanged.

**Why a token has to be minted rather than carried.** `upsert_reminder` normally carries the pending row's token forward (`:121-136`). But **D12 establishes that in the common deposit case the worker has already cancelled that row**: `create_booking` always inserts the reminder regardless of status, `reminder_send_after` returns `now` for any lead between 2 h and 24 h, and `drain_due` re-reads the booking and on `status != 'confirmed'` flips the row to `cancelled` and sends nothing, with `mark` clearing `manage_token` on the way. So a bride booking a deposit-required appointment **3 hours out** gets a reminder scheduled immediately, cancelled within 60 seconds — long before she has finished paying — and then **silently never gets her reminder**. For a >24 h appointment the bug does not fire, which is what makes it the kind that ships green.

`manage_token_hash` is sha256 and `BookingClaim.manage_token` carries the raw value only at creation, so a confirmation deferred to webhook time **cannot reuse it** — `comms.py:130-133` says so: *"the hash is one-way, so the new row needs a new token."*

**Declined**: `reissue_manage_token` (opens its own `tenant_session`, so it cannot join the confirm transaction, and calling it after would mint a **second** token on top of the one the reminder row just took). **Declined**: reading the raw token off `scheduled_messages.manage_token`. **Declined**: a `bookings.manage_token_plain` column.

**Post-commit**: the shipped `send_confirmation(tenant, booking=…, manage_token=token)`, from the route, the `booking/router.py:95-107` position and for its stated reason.

**Tests written first**, `db`-marked, on `test_booking_comms_db.py`'s discipline:
- paid webhook → booking `confirmed`, **exactly one** confirmation SMS on the fake outbox, **and** a reminder row pointing at the **new** token;
- **redelivery → no second SMS, no second audit row** — asserted through the guarded UPDATE, not through `newly_settled`;
- **the crash-recovery case (race row #11)**: settle, **skip the confirm entirely**, then redeliver — assert **exactly one** confirm, **exactly one** SMS, and that the booking left `pending_payment`;
- **the abandoned-reminder case end to end**: create a deposit booking **3 hours out**, run `poll_once` before settlement, assert the reminder row is `cancelled` (F16's shipped behaviour), then settle and assert **a fresh reminder exists carrying the new token**;
- declined → booking stays `pending_payment`, **no SMS**;
- a confirm against an already-`confirmed` booking → `None`, no SMS, no audit row.

- **Done when**: `make lint` + `make test` green; `make test-db` green on CI or the local cluster.
- Commit: `feat(payments): the guarded confirm, the re-minted token and the reminder rewrite`.

## Task 8 — The honour path (TDD, `db`-marked) (D5, MD1, MD2)
`Backend/app/payments/webhook_router.py` or a thin `app/payments/honour.py`, `Backend/tests/test_payment_webhook_db.py`

Reached only from Task 7's `False` / `expired` branch.

1. `honour_late_settlement` (Task 5). `None` → a prior delivery already honoured it; **stop**.
2. Under **`pg_advisory_xact_lock(hashtext(tenant_id))`** — the same key as every other seat decision, `create_booking`'s verbatim — read **BOTH** occupancy facts, because the rebind re-enters **both** partial unique indexes:
   - **`active_seats_at(starts_at)`** → the lowest free index below the slot's capacity, exactly as `create_booking:320-327` picks one. That is 0008's index.
   - **`active_at(customer_id, starts_at)`** → **0009's index, and the read the spec's previous draft never made.** If the bride already rebooked the same instant after her seat was freed — the ordinary consequence of race row #3, and the case 0009's own comment names (*"a customer who cancels can rebook the very same time"*) — reinstating the cancelled row makes two non-cancelled rows for `(tenant, customer, starts_at)` and raises `IntegrityError`. **A hit here routes to step 4: one deposit must not buy two live appointments.**
3. **Seat free AND no other live booking AND a FUTURE `starts_at`** → `rebind(seat_index=…, allowed_from=('cancelled','pending_payment'), not_before=now)`, then the reminder rewrite (D12), the confirmation SMS (D13), and a **`DEPOSIT_LATE_HONOURED`** audit row.
4. **Otherwise** — seat taken, or she already rebooked, or the appointment is past, or `rebind` returned `None`, or `rebind` **raised `IntegrityError`** → the booking stays `cancelled`, the payment stays `paid`, a **`DEPOSIT_LATE_UNRESOLVED`** audit row is written, the row is flagged to the owner (D18), and **MD2's `PAYMENT_RECEIVED_NO_SLOT` SMS is sent**.

**`IntegrityError` is caught HERE and mapped to step 4, never left to become a 500.** `grep IntegrityError Backend/app/main.py` returns **nothing** — there is no handler — and a 500 on this path is **unrecoverable**: `settle_late` already committed and wrote `provider_transaction_id`, so every provider retry from that moment hits `by_provider_transaction_id`'s early return and never reaches this code again. This is the `create_booking:353` backstop pattern applied to a path where the correct answer **is not an error at all**.

**Rebinding never moves her to a different time.** A late payment buys back the slot she chose or it buys nothing. What the boutique does with the money at that point is **MD1** — the deposit stays hers and the owner reschedules her off this very row (Task 11's widened `owner.reschedule` is the button behind the marker). What the bride hears is **MD2**, sent from this branch, within one worker tick.

**One thing this must not guess.** The hold may have outlived a terms republication. F19 **does not** re-ask for acceptance and **does not** rewrite `terms_version_accepted`: the column is NOT NULL evidence of what she actually agreed to. Recorded as spec Risk 5.

**Tests** (`db`-marked): late settlement, seat free → **rebound at the same time and seat, with `cancelled_at`/`cancelled_by` both cleared**, one SMS, `DEPOSIT_LATE_HONOURED`; seat taken → booking stays `cancelled`, payment `paid`, `DEPOSIT_LATE_UNRESOLVED`, **exactly one `PAYMENT_RECEIVED_NO_SLOT`** on the outbox, owner-visible; **the rebind refuses a PAST appointment** (`not_before`) and **refuses when the bride already rebooked that instant** (`active_at`, race row #15), **both routing to step 4 rather than a 500** — the `IntegrityError` catch asserted, not assumed; **the seat-free branch enqueues no `PAYMENT_RECEIVED_NO_SLOT`** (MD2's negative half).

⚠ **Per C6, every one of these drives expiry through `poll_once`** — never by hand-setting `row.status = EXPIRED`.

- **Done when**: `make lint` + `make test` green; `make test-db` green on CI or the local cluster.
- Commit: `feat(payments): the late-settlement honour path, its rebind and MD2's SMS`.

## Task 9 — Booking-create integration and MD4's compensation (TDD, `db`-marked) (D11, D11a, D11b, D19, MD4)
`Backend/app/booking/router.py`, `Backend/app/booking/service.py`, `Backend/app/booking/schemas.py`, `Backend/app/db/repositories/bookings.py`, `Backend/tests/test_booking_api.py`, `Backend/tests/test_booking_service.py`

**Order: create then pay.** Paying first cannot hold the seat, so two brides could pay for the same slot; creating first means the seat is claimed by F13's existing advisory-lock protocol and the payment becomes a state transition on a row that already exists.

**`open_deposit` is called from `booking/router.py`'s create handler, POST-COMMIT** — the same position and for the same reason as the shipped `send_confirmation` call: `PaymentService` opens its own sessions, so a provider hang inside the booking transaction would block commits (`booking/router.py:18-23`). Called when `claim.deposit_due` is true, on **BOTH** the `created=True` and the `created=False` replay branches.

**The replay branch matters and the previous draft never said it called `open_deposit` at all** (D11b). `create_booking` returns `BookingClaim(booking=replayed, created=False, manage_token=None)` at step 4b when a live booking exists for this proven phone at this instant, and **`active_at`'s predicate is `status != 'cancelled'`, so a `pending_payment` booking matches it**. The lost-201 retry and any re-submission inside the hold window take that path. There, `open_deposit` **converges** — `live_pending_for_booking` returns the existing row with **no gateway call at all** — and Task 5's stored `redirect_url` is what makes that converge return a working link.

**Three shipped things move:**
- **`BookingsRepository.insert` has no `status` parameter today** (`:89-104`); the value comes from `server_default 'confirmed'` (`models/booking.py:31`). Add **`status: str = BookingStatus.CONFIRMED.value`** — a defaulted keyword, so no existing caller moves.
- **`BookingClaim` gains `deposit_due: bool`**; `BookingCreateResponse` gains **`redirect_url: str | None`** and **`payment_session_id: str | None`**, both null unless a deposit is due.
- **The inline confirmation-SMS condition gains `and not claim.deposit_due`** (`:95`). Left alone, **a deposit-required booking texts the bride a confirmation before a single agora is taken.**

### MD4's compensation — every exception from `open_deposit`

The booking is **already committed** as `pending_payment` when `open_deposit` raises, so every exception needs a compensating transaction. MD4 decided **(a): book without the deposit, and mark the row.**

```
set_status(to='confirmed', allowed_from=('pending_payment',))   # a NEW transaction
→ the ordinary post-commit send_confirmation(..., manage_token=claim.manage_token)
→ a GATEWAY_UNAVAILABLE_AT_CHECKOUT audit row
→ the owner-visible marker (D18, Task 11)
→ response: deposit_due=false, redirect_url=null, status="confirmed"
```

**The exception set**: `GatewayUnavailableError`, `SecretDecryptError`, `SecretBoxNotConfiguredError`, `GatewayNotConnectedError`. The last should be unreachable because Task 4's predicate ran first, but it can lose a race with a disconnect, **and a raced disconnect must not leak a seat either**. **`PaymentAlreadyHeldError` is NOT in this set** — it means a hold already exists, which is the converge case D11b covers.

**MD4's two costs, stated not mitigated**, because they are the decision rather than a footnote: the owner **will not** learn of it from the audit row (`AuditLogRepository` exposes only `record` and `list_actions` and **no router reads it**), which is why the marker is part of the decision; and **that bride gets a confirmation SMS for an appointment on which no deposit was taken**, with the boutique's forfeit policy having no money behind it for those bookings.

**The declined branch stays specified** so reversing MD4 costs no re-derivation: **(b) refuse** = `cancel(allowed_from=('pending_payment',))` in a new transaction, then re-raise for the 503. **The cancel is not optional under (b)** — without it the refusal leaks the seat, which is the failure (b) exists to avoid.

If the compensating transaction itself fails or the process dies, **Task 10's claim 2 sweeps the row one hold-plus-a-tick later.** That is the belt; this is the braces.

**Tests**: the create response carries `redirect_url` + `payment_session_id` **only** when a deposit is due, and `status == "pending_payment"` **exactly** then; **the replay branch (`created=False`) on a `pending_payment` booking returns the SAME `redirect_url` and `payment_session_id`** with **no gateway call**; the router does **not** call `send_confirmation` on the deposit path and **does** on the non-deposit path — asserted on the fake comms outbox, never a mock's call count; **`open_deposit` raising `GatewayUnavailableError` leaves the booking `confirmed` and sends the confirmation SMS, and the row carries MD4's marker** — the marker has no other failing test, which is why it is asserted here; each of the four exceptions compensates and `PaymentAlreadyHeldError` does **not**.

- **Done when**: `make lint` + `make test` green; `make test-db` green on CI or the local cluster.
- Commit: `feat(booking): create-then-hold, the replay converge and MD4's compensating confirm`.

## Task 10 — The sweeper (TDD, `db`-marked) (D6, D7)
`Backend/app/worker.py`, `Backend/app/payments/sweeper.py` (**new**), `Backend/app/core/config.py`, `Backend/tests/test_payment_sweeper_db.py` (**new**), `Backend/tests/test_config.py`

**A SECOND `await` inside the existing per-tenant loop in `poll_once` (`worker.py:76-88`), with its OWN `try/except … continue`.** Sharing the reminder drain's would let one bad payment row **silence every boutique's reminders** — which is precisely the failure that loop's docstring exists to prevent. **Declined**: a second process; a cron.

### Two claims, ONE transaction

**Claim 1 — the ordinary expiry:**
```sql
UPDATE payments SET status = 'expired', redirect_url = NULL
 WHERE tenant_id = :t AND status = 'pending'
   AND hold_expires_at <= :now AND deleted_at IS NULL
 RETURNING id, booking_id
```

**No locking clause, deliberately, and there are three reasons.** Locking clauses are permitted only on `SELECT` — the spec's earlier `UPDATE … FOR UPDATE SKIP LOCKED` **does not parse**, and `claim_due`, the idiom it cited, is a **SELECT** with `.with_for_update(skip_locked=True)` followed by a **separate** guarded `mark()` UPDATE. The guarded `WHERE status='pending'` **already gives exactly-once**, evaluated by the database under the row lock. And **blocking** behind an in-flight `settle` is the **desired** serialization: it is what makes the ordering argument below true, where `SKIP LOCKED` would defer a contended row a full poll interval and buy nothing at one worker replica. Rides `idx_payments_hold_expiry` (`0012:127-132`).

**Then, and only for rows that UPDATE actually returned**, `cancel(..., allowed_from=('pending_payment',))` on the booking, **IN THE SAME TRANSACTION**. This is not stylistic: **if the payments UPDATE commits first**, a webhook blocked on that row lock wakes, sees `expired`, honours it, and finds a booking still at `pending_payment` — filing a **false "seat taken" alert on a seat that is in fact free** — and then the sweeper cancels the booking anyway. One transaction closes it; Task 3's widened `allowed_from=('cancelled','pending_payment')` is the belt.

**Claim 2 — the orphan and crash backstop, on `bookings`:**
```sql
UPDATE bookings SET status='cancelled', cancelled_at=:now, cancelled_by='expired'
 WHERE tenant_id = :t AND status = 'pending_payment' AND deleted_at IS NULL
   AND created_at <= :now - (:hold_seconds + :poll_interval)
   AND NOT EXISTS (SELECT 1 FROM payments p
                    WHERE p.booking_id = bookings.id
                      AND p.deleted_at IS NULL AND p.status = 'pending')
 RETURNING id
```

**Without this, EVERY checkout-time gateway failure leaks a seat PERMANENTLY.** Task 9 commits the booking first, in `pending_payment`, and **`open_deposit` opens its OWN session** (`payments/service.py:484`) taking only `tenant_id` — it cannot join `create_booking`'s, and it **re-takes the same advisory lock `create_booking` holds to COMMIT**, so folding the two is impossible. Everything between the two commits leaves **a committed `pending_payment` booking with no `payments` row at all** — invisible to claim 1, which sweeps `payments`. And **D2 makes the sweeper the ONLY writer that can move `pending_payment` to `cancelled`**, since every owner and customer path 409s on an unpaid hold. The seat is then held forever by `active_seats_at` and `idx_bookings_slot_seat_unique`, and 0009's index also stops the bride rebooking her own instant.

The **`+ poll_interval` grace** guarantees claim 2 never races the ordinary path. It rides Task 2's `idx_bookings_pending_payment`, so it is an index scan over a handful of rows rather than a per-tick table scan.

**`SWEEP_BATCH_SIZE = 500`** — the `backfill.py:36-38` shape rather than `DRAIN_BATCH_SIZE`'s 50, **because this statement holds no provider call**. The reminder drain's 50 is sized around an SMS round trip per row; this one is two SQL statements.

**`deposit_hold_seconds: int = 900`** — new in `Settings` (`core/config.py`), 15 minutes, beside `worker_poll_interval_seconds`. Not one of the recorded money decisions: one env var, reversible in a deploy, no data migration, and its only irreversible consequence — the width of the race — is precisely what Task 13 parameterizes. `test_config.py` gains it.

**⚠ THE SWEEPER TAKES THE SAME INJECTED `WallClock` AS `open_deposit`** (`payments/service.py:51-57`) — calendar time, distinct from the rate limiters' monotonic clocks and from the booking layer's boutique-timezone `Clock`. **Without this the race test in Task 13 cannot pin both sides of it**, which makes five tests unwritable. It is a constructor parameter, not a module-level `datetime.now`.

**Declined**: widening `ScheduledMessageKind` and riding `scheduled_messages` (`kind` is CHECK-pinned to `('reminder')`, and `drain_due` is hard-wired to SMS and marks a row **FAILED** when a token or phone is missing). **Declined**: reading the payment, deciding in Python, then writing. **Declined**: re-reading the row after the UPDATE to decide whether it won — `cancel`'s docstring documents exactly why that cannot answer the question.

**Tests** (`db`-marked): an expired hold is swept and **the seat is bookable by another bride, proved by an actual second `create_booking` succeeding**; **the sweeper never touches a paid booking** — settle first, then sweep, then assert the booking is still `confirmed`; `cancelled_by == 'expired'` on every swept row; **the orphan case (race row #12)** — commit a `pending_payment` booking with **no payment row**, run `poll_once` after hold + grace, assert claim 2 cancelled it and another bride can take the seat; the grace window is respected (a fresh orphan is **not** swept); `SWEEP_BATCH_SIZE` bounds one tick; **a raised exception in the payments sweep does not stop the reminder drain for that tenant or any other** — D7's containment, asserted.

- **Done when**: `make lint` + `make test` green (`test_config.py`'s two known-false local failures excepted); `make test-db` green on CI or the local cluster.
- Commit: `feat(worker): the hold-expiry sweep and its orphan backstop`.

## Task 11 — The owner surface and MD1's button (TDD, mixed) (D18, MD1)
`Backend/app/booking/schemas.py`, `Backend/app/booking/owner_router.py`, `Backend/app/booking/owner.py`, `Backend/app/db/repositories/bookings.py`, `Backend/tests/test_booking_owner_api.py`, `Backend/tests/test_booking_owner_service.py`, `Backend/tests/test_booking_owner_db.py`

**There is no owner-facing payment surface anywhere in the product.** `GatewayStatusResponse` is exactly six fields and its docstring says *"Nothing else, ever"*; the booking console renders no payment data; and `AuditLogRepository` exposes only `record` and `list_actions` with **no router reading it** — so the audit log is not an owner surface either.

**`OwnerBookingRow` gains `payment_status: str | None`** (`booking/schemas.py:107-123`, beside F34's `checked_in_at` at `:119-123`), which **`OwnerBookingDetail` inherits by subclassing** (`:133`). There is **no `OwnerBookingResponse`** — the spec's previous draft named that class three times and it does not exist.

**Honest cost, and it is not "one repository read":** Task 3's new **`by_booking_ids`** batch read, **one call in `OwnerBookingService.list_day`** (`owner.py:147-189`), and **one field in `owner_router._row_fields`** (`:99-112`). **No new route, no `OWNER_ONLY` edit, no nav row.**

⚠ **Two shipped whole-payload literals red-fail the moment the field lands**, and that is what pinning them is *for*: `test_booking_owner_api.py:422-432` (the list-row literal) and `:502` (the detail literal), which F34 edited for `checked_in_at` and which now gain `"payment_status": None`. A wire-shape change that broke no literal would mean the literal was not pinning the wire shape.

### MD1 — the button behind the marker

**Without MD1 the marker is a dead end**: it tells the owner *that* something is wrong with **no button behind it**, which is the precise defect this spec refuses everywhere else.

`owner.reschedule`'s step-2 guard (`owner.py:588-589`) widens from `!= CONFIRMED → raise` to **admitting `cancelled`**, and `BookingsRepository.reschedule`'s UPDATE predicate (`:551-556`) widens the same way. **On the `cancelled` branch that statement must additionally, in the SAME UPDATE:**

1. **restore `status = 'confirmed'`**, and
2. **clear `cancelled_at` / `cancelled_by`** — D5's requirement for D5's reason: a row reading `confirmed` while carrying cancel evidence is the exact defect D2 declines `set_status` over, and both columns feed F52's attribution and F20's compliance read; and
3. **catch `IntegrityError` and surface it as `SlotUnavailableError`**, because a reschedule off `cancelled` re-enters **both** partial unique indexes — the `create_booking:353` backstop pattern.

**`pending_payment` is NOT admitted.** The owner's remedy for a stuck hold is to wait one tick.

**This is not D5's rebind and does not touch it.** D5 automatically restores her **original seat at her original time** when it is still free. MD1 is what the owner does afterwards, by hand and by phone, when it is not. "Rebinding never moves her to a different time" stands unchanged; moving her is the owner's act, not the webhook's.

**Tests**: `list_day` returns `payment_status` on the row, `None` for a booking with no payment; the two pinned literals updated; **MD1 — `owner.reschedule` accepts a `cancelled` booking whose payment is `paid`, and the resulting row is `confirmed` with `cancelled_at` and `cancelled_by` BOTH NULL** (the assertion that fails if the widened writer forgets property 2); it still **refuses** a `cancelled` booking with **no** payment, and still **refuses** `pending_payment`; a collision on the reschedule off `cancelled` surfaces as `SlotUnavailableError`, **not a 500** (`db`-marked); `SPEC_ERROR_CODES` gains **no member** and stays set-equal.

- **Done when**: `make lint` + `make test` green; the `db`-marked collision case green on CI or the local cluster.
- Commit: `feat(booking): payment_status on the owner row and MD1's reschedule off cancelled`.

## Task 12 — Dashboard (TDD, fast) (D14, MD5)
`Backend/app/dashboard/service.py`, `Backend/app/dashboard/schemas.py`, `Backend/tests/test_dashboard_service.py`

**One predicate, six sites.** Filter `pending_payment` out of `facts` **once**, immediately after `list_window_facts` returns at `dashboard/service.py:361` — leaving `list_window_facts`'s **"EVERY status" contract intact for F20 and F52**, which is why the filter goes in the service and not the repository.

**Enumerate why all six matter**, because the previous draft prescribed *"one extra `continue` in `week_buckets` and one field on `StatusTotals`"* and that leaves four sites wrong:

| Site | What goes wrong unfiltered |
|---|---|
| `cancellation()` `:133`, dividing by `len(facts)` at `:147` | **a live checkout sits in the DENOMINATOR of the headline rate** |
| `week_buckets()` `:96` | "bookings last week" moves as brides open and abandon payment pages |
| `status_totals()` `:117` | an unpaid hold counted as an appointment |
| `top_types()` `:175` | an unpaid hold counted as a booking in the chart |
| `customer_mix()` `:224` | a bride who never paid enters the customer cohort |
| the `cohort_ids` fold `:370` | …and the **repeat-rate denominator** |

**A checkout in progress is not an appointment.**

**`StatusTotals` gains a `pending_payment` field fed from the UNFILTERED count**, so the pure-tested invariant **`sum(weeks.bookings) == confirmed + no_show + completed`** keeps balancing and the number is visible somewhere rather than vanishing.

**MD5 is a SEPARATE edit on top of this one**, and the distinction is load-bearing: filtering `pending_payment` does **not** exclude abandoned checkouts, because **an expired hold has already become `cancelled`**. So `cancellation()` additionally drops `cancelled_by == 'expired'` rows from **both** the numerator **and** `len(facts)`. Attribution alone changes nothing about the headline number — the owner's rate would read *"31%"* where the truth is *"cancellation rate 8% · 12 checkouts never completed"*, and she would steer a boutique on the wrong number.

⚠ **The exclusion must reach the DENOMINATOR as well as the numerator** — that is the half that silently does nothing if it is missed, and it is what F21's audit re-derives.

**Tests** (fast, pure functions with hand-built `BookingFact` lists — this module's existing shape): a `pending_payment` fact is absent from every one of the six; `StatusTotals.pending_payment` counts it; the sum invariant still balances; **MD5 — a `cancelled_by='expired'` fact is in neither `cancellation()`'s numerator nor its denominator**, asserted as a rate change and not just a count; a `cancelled_by='customer'` fact still is in both; `by_customer + by_owner <= cancelled` still holds.

- **Done when**: `make lint` + `make test` green, **locally and on CI**.
- Commit: `feat(dashboard): exclude live checkouts from every number, and abandoned ones from the rate`.

## Task 13 — The race suite (written here, executed on CI) (`db`-marked)
`Backend/tests/test_payment_race_db.py` (**new**)

**This is the reason the feature is being built now** (Interview Q7). NullPool engines in `try/finally`, `asyncio.gather` **so every racer gets its own connection** — the `test_booking_comms_db.py:1-20` discipline. **Bodies and signatures are built ONLY through `fake_webhook_body` and `sign_fake_webhook`** (`payments/fake.py:56-70`), never hand-assembled, so a change to the fake's scheme cannot leave a test signing a shape `verify_webhook` does not parse.

**Five races:**

1. **Sweeper vs webhook on the same hold.** Exactly one of {seat freed, booking confirmed} — **never both, never neither**, asserted on the `.returning()` scalars and **never on a re-read** (`cancel`'s docstring is why a re-read cannot answer it).
2. **Two concurrent deliveries of one transaction.** One confirm, **one SMS**, one audit row.
3. **Two concurrent brides for the last seat, one mid-payment.** Exactly one holds it; the loser gets `SlotUnavailableError`.
4. **A late delivery racing another bride's create for the freed seat.** Either she gets the seat and the rebind falls to the owner-alert path, **or** the rebind wins and her create 409s. **A third outcome is not correct** — and the assertion is written as that disjunction rather than pinning one branch, because either is right and pinning one makes the test flaky by construction.
5. **Race row #13 — sweeper vs late webhook, gathered on separate connections.** Assert the outcome is **NEVER** *"payment paid + booking cancelled + seat free + owner alerted"*. **This is the test that proves D6's single transaction and D5's widened `allowed_from`** — and it is the mutation-check target: fold claim 1 into two transactions and this must turn red **and nothing else may**.

**PLUS the two BLOCKER recoveries the review found**, which are windows rather than races and are asserted here beside them:

6. **The crash window (race row #11)** — settle, **skip the confirm entirely**, then redeliver → **exactly one** confirm, **exactly one** SMS, and the booking left `pending_payment`. This is the assertion the previous draft's D4 table would have made impossible.
7. **The orphan (race row #12)** — a committed `pending_payment` booking with **no payment row** → claim 2 cancels it and **another bride takes the seat**, proved by a real `create_booking`.

⚠ **Per C6, expiry is driven through `poll_once` in every one of these**, with the sweeper and `open_deposit` sharing the **same injected `WallClock`** (Task 10). Hand-setting `row.status = EXPIRED` — F17's `test_payments_service.py:921-925` — means the sweeper is never the thing under test.

- **Done when**: `make test-db` green **on CI or the local cluster**. Locally without a cluster these collect and skip; `make lint` (mypy over `tests`) is the only signal.
- Commit: `test(payments): the five deposit races and the two crash recoveries`.

## Task 14 — The dev-only `/fake-pay` page (D21)
`Frontend/apps/storefront/src/routes/FakePayPage.tsx` (**new**), `Frontend/apps/storefront/src/router.tsx`

**Without this, NOTHING in this feature can be seen.** `FakeGateway.create_session` returns `redirect_url = "/fake-pay?session={id}"` built from `FAKE_PAY_PATH` (`payments/validation.py:31`), and a repo-wide grep finds **only** that definition, that use, and two lines in `test_payments_adapters.py`. **There is no route, no page and no task that ever POSTs the webhook endpoint** — `sign_fake_webhook` and `fake_webhook_body` are module-level helpers with **no production caller**.

So on staging, as the spec's earlier Risk 2 had it backwards: every deposit booking would redirect to a **404**, sit on the awaiting screen forever, and be swept a tick later. None of Task 15's five states could be exercised and F21's UAT could not see the flow at all.

**~20 lines**: read `?session=`, offer "pay" and "decline", build the body with `fake_webhook_body`'s shape, sign it with the tenant's webhook secret, POST `/storefront/payments/webhook`. **Guarded off in production by the same condition that already boot-fails `payment_provider="fake"` there** — one build-time flag, checked in `router.tsx` so the route does not even exist in a production bundle. **F18 deletes it** when a real hosted page replaces it.

**Recorded risk, unchanged**: with this page the fake settles **on a human's click**, which does mean staging can mark money received that was never charged — bounded by the same three guards F17 recorded (two production boot failures and 0012's `provider` CHECK).

- **Done when**: `make fe-build` green; the page is **absent** from a production build (asserted by a grep on the built output, the cheapest possible check).
- Commit: `feat(storefront): the dev-only fake-pay page that signs and posts the webhook`.

---

# Part II — the frontend

## Task 15 — The storefront pay step (TDD)
`Frontend/apps/storefront/src/router.tsx`, `…/src/routes/BookPage.tsx` (or the pay-step component it hosts), `…/src/api.ts`, `…/src/i18n/he.ts`, `…/src/i18n/ar.ts`, `…/src/__tests__/`

**`BOOK_STEPS` gains `"pay"`** (`router.tsx:26`). It is **a closed set** — that file's own comment says why: *"no dress id can ever be read as a step"* — so adding a member is the whole mechanism and nothing else in the router changes.

**Five states**, from Task 1's copy deck:

| State | What it does |
|---|---|
| hand-off | redirects, **with a manual link fallback for a blocked redirect** |
| awaiting the webhook | polls `payment-status` with `payment_session_id`. **THE WEBHOOK IS AUTHORITATIVE, NOT THE REDIRECT** — a bride returning from a provider page has not necessarily been settled, and the redirect is a navigation event, not evidence |
| paid | the existing confirmed screen, unchanged |
| declined | retry, which **converges onto the same hold and returns the SAME link** (D11b + D8) |
| expired | rebook, from the storefront's normal slot picker |

**The poll**: a **bounded** attempt count, a **terminal-state stop**, and a **plain interval** — pre-decided #23 rules no realtime vendor. The next tick is armed from the previous request's `.finally()` (F34's arm-on-settle shape), so **at most one poll is in flight by construction** and there is nothing to abort.

**A11y**, and it is a legal surface (pre-decided #38): the `role="status"` region changes on **terminal states only, never per tick** — a region that re-announces every few seconds while a bride watches her card being charged is an AA failure however green the automated check comes back. `<bdi dir="ltr">` on the amount and on any session id ever rendered. 44×44 on the pay CTA and the retry. Axe at **zero** violations.

**Tests** (vitest + `vi.useFakeTimers()`, the `CatalogSection.test.tsx`/`BoardSection.test.tsx` pattern): each of the five states renders its own copy; **the poll stops on `paid`, on `expired`, and after the attempt ceiling** — three separate assertions, advancing timers past the ceiling and asserting **no further calls**; a declined retry issues the create again and renders the **same** link; **the announced region does not change on a non-terminal tick**; the manual fallback link is present and points at the same URL; axe zero.

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean.
- Commit: `feat(storefront): the pay step, its five states and the bounded status poll`.

## Task 16 — The bride's manage page (TDD)
`Frontend/apps/storefront/src/routes/ManageBookingPage.tsx`, `…/src/api.ts`, `…/src/i18n/he.ts`, `…/src/i18n/ar.ts`, `…/src/__tests__/`

**Two edits, both required, and the second one is the hard constraint of the whole feature.**

**1 — a `pending_payment` branch beside the shipped `cancelled` one** (`:38` `const CANCELLED = "cancelled"`, `:291` the single `booking.status === CANCELLED` derivation). An awaiting-payment state carrying the checkout link, with **cancel and confirm-attendance SUPPRESSED**. **Without it an unpaid hold renders as a standing appointment with a LIVE CANCEL BUTTON** — on the bride's own page, on a booking she has not paid for. The backend 409s on both actions anyway (Task 7's manage-page guards), so the suppression is honesty rather than enforcement.

**2 — MD3.** **`manage.cancelConsequenceFree` (`:390`, `he.ts:297`, `ar.ts:37`) MUST NOT SURVIVE THE MERGE on a deposit booking.** The shipped sentence — *"no payment was charged for the appointment, so cancelling carries no cost"* — **becomes false for every deposit booking the day F19 merges**. Its own source comment says the swap belongs to E4 (*"The split ships as structure; E4 swaps the out-of-window key"*), and `.planning/design/screens/manage-booking/copy.md:22` and interview pre-decided #4 both assign it here.

A new key **`manage.cancelConsequenceDeposit`** carries MD3's neutral interim on **any** booking with a deposit; **`cancelConsequenceFree` survives only where no deposit exists**:

> **הפיקדון מטופל בהתאם למדיניות הביטולים של הסלון.**
> *The deposit is handled according to the boutique's cancellation policy.*

**The parked copy does not block this.** MD3's two window-specific Hebrew variants are the one parked item in the feature; the interim is true under **every possible answer** to them, promises nothing in either direction, and the boutique's policy line is already on that page. When they land it is a **string swap** — two values in `he.ts`/`ar.ts` and one branch on D16's already-computed number. No schema, no API, no logic, no migration.

`api.ts`'s `ManageBookingResponse` gains whatever the branch needs to know a deposit exists — the smallest field that answers it, not a payment object.

**Tests**: the awaiting-payment branch renders, carries the link, and **neither the cancel button nor the confirm-attendance button is in the document**; **`cancelConsequenceDeposit` renders on a deposit booking and `cancelConsequenceFree` does NOT** — and the converse on a no-deposit booking; **both keys resolve in both bundles** (F17's he/ar parity assertion in `i18n.test.ts`); axe zero on the new state.

- **Done when**: `make fe-test` + `make fe-build` green; `grep -n "cancelConsequenceFree" Frontend/apps/storefront/src/routes/ManageBookingPage.tsx` shows it inside a **conditional**, never unconditional.
- Commit: `feat(storefront): the awaiting-payment manage state and MD3's deposit cancel sentence`.

## Task 17 — The manage console (TDD) (D14, D18, MD1, MD4)
`Frontend/apps/manage/src/lib/booking.tsx`, `…/src/components/BookingDetail.tsx`, `…/src/components/BookingsSection.tsx`, `…/src/api.ts`, `…/src/i18n/he.ts`, `…/src/i18n/ar.ts`, `…/src/__tests__/`

- **`statusBadge` gains a real `pending_payment` entry** (`lib/booking.tsx:15-26`). Today a fifth status falls through the documented raw-value fallback (`:22-26`) and renders **the literal LTR string `pending_payment` inside a Hebrew RTL console**. The variant follows that file's stated rule — **the Hebrew word carries the state and the colour is redundant reinforcement**; `danger` stays reserved for something the owner must fix, and an unpaid hold is not that. New `he.ts` / `ar.ts` keys, flat dotted literals per the console's post-F15 shape.
- **`BookingDetail.tsx:201-205` gains a sixth branch.** Its five booleans (`liveConfirmed`, `pastConfirmed`, `isNoShow`, `isCompleted`, `isCancelled`) are derived from the four statuses, so **a `pending_payment` booking satisfies NONE of them and renders with no state and no action set**. The new branch is an awaiting-payment state with **NO owner actions** — the backend 409s on all of them anyway, so an enabled control would be the client asserting a rule the server refuses.
- **Under D18**: a `payment_status` badge on the row; an **action-needed marker** for **paid-with-no-seat** (a `cancelled` booking whose payment is `paid`); and the same field carrying **MD4's "booked without a deposit"** marker. Both markers are **words, never colour alone** — the same rule as the status chip, and they compete for meaning in one region, so the deck's §6 decides which sits where.
- **Under MD1**: the **reschedule action on a cancelled booking whose payment is `paid`** — the button behind the marker. This is the console condition MD1 buys, and it is what stops D18's marker being a dead end.
- **`api.ts`**: `payment_status: string | null` on `OwnerBookingRow` (inherited by `OwnerBookingDetail` via `extends`). No case conversion — this app speaks the backend's snake_case verbatim.
- **`storefront/src/api.ts:308-310`** — the comment documenting the four-value assumption gains the fifth. One line, and it is the only edit that file needs from this task.

**Tests**: the badge renders Hebrew for `pending_payment` and **never the raw value**; the detail's sixth branch renders and **exposes no owner action** (asserted by absence, the F57 shape); the paid-with-no-seat marker renders and the reschedule action **is** present on it; MD4's marker renders on a `confirmed` booking with no payment; a `confirmed` booking with a `paid` payment shows **neither** marker; every new key resolves in **both** bundles; fixtures gain `payment_status` with **no assertion edits** elsewhere; axe zero.

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean.
- Commit: `feat(manage): the pending_payment badge, the payment markers and MD1's reschedule action`.

## Task 18 — Gates and the run report
No files.

Run the full verification below, report what ran and what passed, and state **explicitly** whether the `db`-marked suites were executed locally against a throwaway cluster or are debuting on CI. Carry forward in the run report:

- ⚠ **C1 — DO NOT OPEN THE PR UNTIL F57 AND F33 MERGE.** Then renumber: `revision` `"0015"` → `"0017"`, `down_revision` `"0014"` → `"0016"`, and the filename. **Three edits.** Run `alembic heads` after the rebase and confirm it prints one head; the new fast guard also asserts it in `make test`.
- ⚠ **`_STATUS_CHECK_DEF` in `test_migrations.py:400-403` was edited, deliberately.** F34 wrote that pin **predicting this exact moment** and said so in its docstring. The two index literals were **not** touched, and that is D1's promise holding.
- **MD3's two approved Hebrew sentences are the ONE PARKED item.** The neutral interim shipped; `cancelConsequenceFree` no longer renders on a deposit booking. When the two variants land it is a **value swap on a key that already ships** — two lines in `he.ts`/`ar.ts` and one branch on D16's number. **F21 records the interim as still-shipping rather than treating it as a closed finding if they have not landed.**
- **Risk 1 — the never-registered webhook URL has NO technical detection**, and the pilot takes an **operator checklist step** (decided under the pre-authorization). `GATEWAY_WEBHOOK_UNMATCHED` covers the *wrong*-URL case only; the *never-registered* case is caught by the operator verifying one successful test-mode webhook at onboarding. **F21 must re-derive this and decide whether the checklist survives the second boutique.**
- **Risk 4 — MD2's SMS promises a phone call the product cannot make.** MD1 and MD2 shrink the risk from what it was, but the remedy still terminates in a human. **F21 UAT: watch whether stranded deposits are actually rescheduled, and how long it takes.**
- **Risk 5 — a rebind can reinstate a booking under a superseded terms version.** D5 rules the snapshot is never rewritten, because rewriting it destroys the only evidence of her actual agreement. **F20's compliance read; F21's audit.**
- **Risk 7 — `payments` still ships with more statuses than writers.** F19 adds a writer for `expired` and keeps `paid` as the single terminal success. `failed`, `refund_due`, `refunded`, `forfeited` remain unwritten, **and a webhook against any of them currently files as a late settlement** (`payments/service.py:696-704`). **Whoever gives one of them a writer must re-read that branch AND Task 8's honour path**, which would otherwise try to rebind against it. **F29's.**
- **Risk 9 / MD3 — a bride who paid then cancelled leaves an orphaned `paid` payment row.** `ManageBookingService.cancel` never touches `payments` and F19 does not change that (D16 writes no refund status). The only thing between the boutique and a silent liability is D18's marker and the interim sentence. **F29's.**
- **The privacy hand-off, re-nagged.** `payments` now carries a hosted-page URL and a settlement clock against a named person's appointment. **F20 (`spec_gate: user`) must carry a deposit entry in both the collection notice and the processing-activities record** — purpose = taking and holding a deposit, retention = F17's Gate 1 Q3 7-year clock. No build work here.
- **`deposit_hold_seconds = 900` was set by this plan**, not the user. One env var, reversible in a deploy. Its only irreversible consequence is the width of the race, which Task 13 parameterizes.
- **D21's `/fake-pay` page ships and F18 deletes it.** On staging the fake settles on a human's click, which means staging can mark money received that was never charged — bounded by two production boot failures and 0012's `provider` CHECK.

No push, no PR — the orchestrator owns review and shipping.

---

## What a local run cannot prove

**NO DOCKER LOCALLY**, so `pytest -m db` collects and skips and **every `db`-marked test in this feature debuts on CI** unless the throwaway cluster is stood up first.

| Task | Proof that is CI-only (or cluster-only) | What the local run still gives |
|---|---|---|
| **2** (migration + enums + column) | the five statements' round trip both ways, **the three deparsed literals**, the widened CHECKs' probes, the partial index's `indexdef`, the downgrade's honest failure | ruff + `mypy app tests` resolving `BookingStatus.PENDING_PAYMENT`, `BookingCancelledBy.EXPIRED`, `MessageKind.PAYMENT_RECEIVED_NO_SLOT`, the six `AuditAction` members and `Payment.redirect_url` at every call site — **plus the new single-head guard, which is fast and runs in `make test`** |
| **3** (the writers) | **every assertion** — the `.returning()` scalar against a real identity map is not reproducible with a fake, and neither is an `IntegrityError` from a partial unique index | `mypy` over the new signatures |
| **7, 8, 9, 10** (confirm, honour, create, sweeper) | all of the `db`-marked halves | the fast halves are real coverage: Tasks 4, 5, 6, 11's service layer and 12 verify **entirely** locally |
| **13** (the whole race module) | **all of it**, including both crash recoveries | `mypy` over `tests` |

**Budget ONE red CI run and ONE fix commit** — house experience with F11, F16 and F17, recorded in `.memory/boutique-ci-first-run-surprises.md`. Check `continue-on-error` on the job **before believing a red**.

**If Postgres 16 is installed locally, stand up a throwaway cluster OUTSIDE the repo and run them before pushing** — that is what bought F34 three green jobs on its first run and F57 the same. See §"Run the db suite locally anyway". This feature has five race tests and three deparse hazards; it is the run where that instruction pays the most.

Everything in Tasks 0, 1, 4, 5, 6, 12 and 14–17 verifies locally. **Task 6 is the backend milestone**: the first point at which both new routes, the webhook's full status table and the anonymous/raw-body posture are exercised end to end with **no Postgres**.

⚠ **Two backend test failures are always false locally** — `test_config.py` picks up `Backend/.env` leaking `MEDIA_BUCKET` (`.memory/local-env-breaks-config-tests.md`). **CI is green. DO NOT CHASE THEM.**

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| Five migration statements, up and down, both directions probed | `test_migrations.py` (`db`) |
| The widened `status` CHECK pinned byte-identical **after this feature's migration**; **both unique indexes still byte-identical** | `test_migrations.py` (`db`) — ⚠ **capture the deparsed literal, do not transcribe it** |
| `cancelled_by` and `message_log.kind` CHECKs pinned; each admits its new value and still rejects an unknown one | `test_migrations.py` (`db`, probes **rolled back**) |
| `payments.redirect_url` is nullable `text`; `idx_bookings_pending_payment` exists and is **partial** | `test_migrations.py` (`db`) |
| No table snuck in | `test_every_tenant_id_table_has_forced_rls` (`db`, **unedited**) |
| **Exactly one alembic head** | `test_migrations.py` (**fast** — the guard C1 adds; catches what git cannot see) |
| `cancel`'s default `allowed_from` leaves every existing caller byte-identical | `test_booking_repositories.py` (`db`) + every F15/F34 owner test passing **unedited** |
| `rebind` writes status + seat + **cleared cancel evidence** in one statement; refuses past / wrong-status / unknown; raises from **both** indexes | `test_booking_repositories.py` (`db`) |
| `settle_late` fires only on `expired`; `redirect_url` blanked on every exit from `pending` | `test_payment_repositories.py` (`db`) |
| `by_booking_ids` is tenant-scoped and **empty in ⇒ empty out** | `test_payment_repositories.py` (`db`) |
| Deposit fields omitted with **no row / an `invalid` row / an unconfigured secret box**, emitted with a valid connected pair | `test_storefront_service.py` (fast) — the predicate the previous draft got wrong |
| **`deposit_due` is false with `deposits_enabled` off** on a connected `deposit_required` type | `test_storefront_service.py` (fast) — **the toggle's first test, ever** |
| The disclosure and the flow answer identically for the same tenant/type | `test_storefront_service.py` (fast) — one test calling both helpers |
| The converge path returns the **stored** link with **no `create_session` call** | `test_payments_service.py` (fast, on the fake gateway's call count) |
| `app.state.payment_service` wired; the placeholder comment gone | `test_payments_service.py` (fast) + the diff |
| Webhook route is anonymous, cookie-blind, CSRF-exempt by structure, and **reads the raw body** | `test_payment_webhook_api.py` (fast) — the re-serialization test is the regression guard |
| **D9's full status table**: 200 ×5, 400 ×3, and the unmatched case **writes `GATEWAY_WEBHOOK_UNMATCHED`** | `test_payment_webhook_api.py` (fast, asserted on `audit_log` — which proves the commit-before-raise) |
| The poll answers on `payment_session_id`, 404s an unknown one, leaks no other tenant's | `test_payment_webhook_api.py` (fast) |
| Paid → confirmed + **exactly one** SMS + a reminder on the **new** token | `test_payment_webhook_db.py` (`db`) |
| **Redelivery → no second SMS, no second audit row** — through the guarded UPDATE, not `newly_settled` | `test_payment_webhook_db.py` (`db`) |
| **The crash window (#11)**: settle, skip the confirm, redeliver ⇒ one confirm, one SMS | `test_payment_race_db.py` (`db`) |
| **The 3-hour reminder is cancelled then re-created** on confirm (D12) | `test_payment_webhook_db.py` (`db`) |
| Late + seat free ⇒ rebound same time and seat, **cancel evidence cleared**; late + seat taken ⇒ cancelled + paid + owner-visible + **one** `PAYMENT_RECEIVED_NO_SLOT` | `test_payment_webhook_db.py` (`db`) |
| The rebind refuses a **past** appointment and refuses when she **already rebooked** — both to the alert branch, **never a 500** | `test_payment_webhook_db.py` (`db`) |
| Create response fields only when due; **the replay returns the SAME link** | `test_booking_api.py` (fast) |
| **No `send_confirmation` on the deposit path**, and one on the non-deposit path | `test_booking_api.py` (fast, on the fake outbox) |
| **MD4** — `GatewayUnavailableError` ⇒ booking `confirmed`, SMS sent, **marker present**; `PaymentAlreadyHeldError` does **not** compensate | `test_booking_api.py` (fast) — the marker's only failing test |
| Sweeper frees a seat (proved by a **real** second create); **never touches a paid booking**; `cancelled_by='expired'` | `test_payment_sweeper_db.py` (`db`) |
| **The orphan (#12)** — no payment row ⇒ claim 2 cancels, another bride takes the seat | `test_payment_race_db.py` (`db`) |
| The payments sweep's failure does **not** silence the reminder drain (D7) | `test_payment_sweeper_db.py` (`db`) |
| `deposit_hold_seconds` in `Settings` | `test_config.py` (fast — ⚠ its two local failures are the known `.env` leak) |
| `payment_status` on the row and the detail; **the two pinned literals updated**; `SPEC_ERROR_CODES` unchanged | `test_booking_owner_api.py` (fast) |
| **MD1** — reschedule accepts `cancelled`+`paid` and lands `confirmed` with **both** cancel columns NULL; still refuses `cancelled` with no payment and refuses `pending_payment` | `test_booking_owner_service.py` (fast) + `test_booking_owner_db.py` (`db`, the collision case) |
| **D14** — `pending_payment` absent from all six dashboard sites; `StatusTotals` still balances | `test_dashboard_service.py` (fast, pure) |
| **MD5** — `cancelled_by='expired'` out of the **numerator AND the denominator** | `test_dashboard_service.py` (fast) — asserted as a **rate** change |
| **The five races**, each on its own connections via NullPool + `gather`, bodies through `fake_webhook_body` only | `test_payment_race_db.py` (`db`) |
| The five payment states, the poll's **terminal stop and attempt ceiling**, the announced region silent on a tick | storefront vitest (fake timers) |
| The manage page's awaiting-payment branch with **cancel and confirm suppressed** | storefront vitest |
| **MD3** — `cancelConsequenceDeposit` renders on a deposit booking and `cancelConsequenceFree` does **not**, in **both** bundles | storefront vitest + `i18n` parity |
| The `pending_payment` badge renders Hebrew, never the raw value; `BookingDetail`'s sixth branch; both D18 markers; MD1's action | manage vitest |
| Zero axe violations on every new surface | storefront + manage vitest (`axe-core`, **already a devDependency**) |
| Every new formatter is zoned | **nothing new to check** — F19 adds no formatter; `qa-greps.sh` output must be **byte-identical to the baseline** |

**No new E2E is promised**, and the reason is structural rather than a shortcut: **the storefront booking flow now ends at a third-party redirect, which Playwright cannot follow.** The existing suite must stay green and unchanged. Recorded rather than silently skipped.

---

## What could go wrong in review

Every item here is a **recorded ruling**, not an open question. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"A shipped, pinned test literal was changed — `_STATUS_CHECK_DEF`."** **Deliberate, predicted, and the point.** F34 wrote that pin in its own docstring naming this exact moment: *"when E4 widens the CHECK for 'pending_payment' it collides with a pinned literal and a deliberate review, instead of colliding with nothing."* This is that review. **The two index literals beside it were NOT touched**, and them staying byte-identical is D1's whole argument holding. **The most likely finding in the review.**
2. **"The migration is numbered 0015 but the spec says 0014 and main is at 0014."** **C1.** 0014 is F34's, shipped. Three features are in flight; F19 builds against 0015 for branch coherence and **renumbers to 0017 at rebase** — two literals and a filename, named in Task 18. **The PR does not open until F57 and F33 merge.**
3. **"Why a fast test that just counts alembic heads?"** **C1.** Two files claiming one revision id is **not a git conflict** — the filenames differ, so the merge is clean and the failure surfaces at runtime. With three worktrees live, this is the cheapest possible guard and it runs in `make test`, not CI.
4. **"`rebind` duplicates `set_status` — widen `set_status` with an optional `seat_index` and a `clear_cancel_evidence` flag."** Offered by the spec's own review (findings 3, 19, 26) and **declined there**: `set_status`'s docstring makes *"never writes the cancel evidence"* a design commitment shared with three other callers, and a flag that inverts it is a trap for the next reader. **And splitting the rebind in two would open a window where the row is `confirmed` at a stale seat index — which, because `create_booking` hands freed seat numbers back out, is very likely another bride's seat.**
5. **"The sweeper's UPDATE has no `FOR UPDATE SKIP LOCKED` — the queue idiom does."** **D6, and the spec's earlier SQL did not parse.** Locking clauses are permitted only on `SELECT`; `claim_due` is a SELECT plus a **separate** guarded UPDATE. Here the guarded `WHERE status='pending'` already gives exactly-once, and **blocking behind an in-flight `settle` is the DESIRED serialization** — it is what makes the ordering argument true.
6. **"Claim 1's two statements could be two transactions — it would be simpler."** It would be **wrong**. If the payments UPDATE commits first, a webhook blocked on that row lock wakes, sees `expired`, honours it, and finds the booking still `pending_payment` — **a false "seat taken" alert on a seat that is in fact free**. Race row #13, and test 5 in Task 13 is the mutation-check target that proves it.
7. **"The webhook returns 200 on a declined payment — that hides a failure."** **D9.** A provider reads non-2xx as "retry", and retrying a decline forever is what D25's 400-vs-503 argument is made of. **400 is reserved for the three forgery-or-malformed conditions**, one of which (`GATEWAY_WEBHOOK_UNMATCHED`) F19 adds precisely because real money moves there today with no trace but an access log.
8. **"The poll should use the manage token like every other tokenized route."** **D13 — it cannot work three times over**: `BookingCreateResponse` carries no token, the deposit path suppresses the SMS that would carry the link, and the confirm rotates the hash while `by_manage_token_hash` is the only lookup — **so the poll would start 404-ing at precisely the moment it should return `paid`.**
9. **"Redelivery of an already-settled transaction should short-circuit."** **D3, and the previous draft ruled exactly that and was factually wrong.** `allowed_from=('pending_payment',)` matches a **stranded** booking precisely, so running the confirm anyway is a no-op in the normal case and **the crash recoverer for race row #11** in the abnormal one. Exactly-once is the UPDATE's predicate, not our bookkeeping.
10. **"`is_connected` duplicates `active_for_provider` — just call the repository."** **D10.** `active_for_provider` filters **no status**, so a boutique whose credential was flipped to `invalid` would be shown the deposit and then meet a 409 at create — the dead-calendar outcome F17's Q1 exists to prevent, and **not** covered by MD4.
11. **"MD4 books an appointment with no deposit and texts her a confirmation."** **Decided, deliberately, with both costs stated rather than mitigated.** "Not connected" is permanent and the owner's to fix; "unavailable" is transient and **nobody's** — refusing would kill the calendar for a fault she cannot see, diagnose or wait out. **The marker is part of the decision, not a nicety**, because the audit row is reconstructable by an operator and by nobody else.
12. **"`owner.reschedule` now admits `cancelled` — that breaks F15's transition graph."** **MD1**, and it is the button behind D18's marker. Without it the marker is a dead end. **`pending_payment` is still refused**, the widened statement clears the cancel evidence in the same UPDATE, and it catches its own `IntegrityError`.
13. **"The dashboard filter belongs in `list_window_facts`."** **D14.** That method's contract is **"EVERY status"** and F20 and F52 read it. One predicate in the service reaches all six consumers and leaves the repository's contract intact.
14. **"MD5's exclusion looks like it double-counts with the `pending_payment` filter."** It does not, and that is why they are two edits: **an expired hold has already become `cancelled`**, so filtering `pending_payment` excludes nothing from `cancellation()`. **The exclusion must reach the denominator as well** — the half that silently does nothing if it is missed.
15. **"A dev-only page shipped in the frontend."** **D21.** `FakeGateway` posts nothing and `/fake-pay` has no route — verified by a repo-wide grep returning two definitions and two test lines. Without it **every staging deposit 404s and is swept a tick later**, and none of the five payment screens or F21's UAT can see the flow. ~20 lines; **F18 deletes it**.
16. **"F17's late-settlement test sets `row.status` by hand — F19's don't. Inconsistent."** **C6.** That was correct for F17 (the sweeper did not exist). F19 **is** the sweeper, so copying it would mean the sweeper is never the thing under test. **F17's test is left exactly as it is** — editing another feature's evidence is not F19's to do.
17. **"`bookings.source` should record that this booking came through checkout."** **C7.** No such column, no such field, anywhere. It is F50's and unbuilt.
18. **"Every line number the spec cites into `bookings.py` and `dashboard/service.py` is wrong."** **C2 and C3.** F34 shifted them. §"What moved" has every new address; **the content each citation points at is all still there and no ruling moved.**
19. **"`constants.py` will conflict with F57."** **C5**, and the rule is append-only + rebase before every push. Different enums, same file — an easy three-way merge unless somebody reformats. **Never touch F57's role values.**
20. **"The audit rows are write-only."** Unchanged from F15's Risk 7, F34's and F57's. F19 adds **six** more actions nothing renders, and `GATEWAY_WEBHOOK_UNMATCHED` is the one that most wants a reader. **F53's activity log is the first read surface.**
21. **"`ar.ts` gained hand-copied Hebrew values with nothing checking the translation."** Inherited from F15 through F34 and F57. **No parity guard is invented here**; the mitigation is that both columns come from one `copy.md` table, and F17's key-parity assertion catches a **missing** key even though nothing catches an untranslated one. **F45 owns the real fix.**

---

## Verification

```
make lint      # cd Backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
               #   + cd Frontend && pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # cd Backend && uv run pytest -m "not db" -q
make test-db   # cd Backend && uv run pytest -m db -q     <- CI, or locally per the § above
make fe-test   # cd Frontend && pnpm -r --if-present test
make fe-build  # cd Frontend && pnpm -r build
make e2e       # cd Frontend && pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** printing **exactly the pre-existing baseline** (seven `ok` lines, then `review  date reads` listing `HoursSection.tsx:15` and `TermsSection.tsx:9` **and nothing else**). F19 adds no formatter, so **any third line is F19's regression**.
- **`make test`** — all fast tests pass, **including the new single-head guard**; `test_payment_webhook_api.py`, `test_payments_service.py`, `test_storefront_service.py`, `test_booking_api.py`, `test_booking_owner_api.py` and `test_dashboard_service.py` green; the `db`-marked modules **collected and deselected** with the summary line saying so. `test_staff_role_gating.py`, `test_no_route_is_registered_twice_across_routers`, `test_frontend_constant_parity.py` and every F15/F34 owner test pass **unedited**. ⚠ Two `test_config.py` failures are the known local `.env` leak — **CI is green, do not chase them**.
- **`make test-db`** — green, including all five migration assertions with their **captured** deparsed literals, the round trip both ways, the downgrade's honest failure, both repository writer suites, the confirm and honour transactions, the sweeper and its orphan backstop, **the five races and the two crash recoveries**. **A first red on a test bug here is budgeted** if the local cluster was skipped — check `continue-on-error` before believing it.
- **`make fe-test`** — the storefront's five payment states, the poll's terminal stop and attempt ceiling, the manage page's awaiting-payment branch, **MD3's copy swap asserted in both bundles**, the console's badge / sixth branch / two markers / MD1 action; **axe at zero violations on every new surface**.
- **`make fe-build`** — both apps build; **no unused-import or unused-variable TS error**; the `/fake-pay` route is **absent** from a production build.
- **`make e2e`** — the existing storefront and console specs stay green **unchanged**. **F19 adds no e2e spec** — the flow now ends at a third-party redirect Playwright cannot follow — so an unchanged e2e count is the expected result, not a gap.
- **Working tree clean of the pre-run**: `git status` shows no `tests/conftest.py` diff and no cluster data directory.
- **Before the PR opens**: `alembic heads` prints exactly one head **after** the rebase onto F57 and F33, and the three renumbering edits are in the diff.

---

## Out of scope (unchanged from the spec)

**No refunds** and no `refund()` on the port (D12, reaffirmed at F17's Gate 1) — F29's · **no `refund_due` / `refunded` / `forfeited` writer** (D16) · no partial payments, no instalments, no saved cards · **no owner-side "mark as paid"** — a money mutation with no provider evidence · **no owner remedy beyond MD1's reschedule** — ~~previously a non-goal~~, MD1 puts one in scope, and the reasoning stays visible because two earlier drafts claimed "F15's reschedule is one click away" when `booking/owner.py:588-589` refuses every non-`confirmed` booking outright · **no receipt generation** — the provider issues its own and the Israeli קבלה duty sits with the boutique (F21's audit row) · **no KMS, no retention job, no encryption seam** (F17 Gate 1 Q2/Q3; F20 owns the sweep) · **no Redis-backed limiter** for the webhook route (F21) · **no `/manage/payments` console section, no nav row, no `OWNER_ONLY` edit** (F29's shape — D18) · **no never-received-webhook warning, no `last_webhook_at` column, no registration check** (Risk 1 — the pilot's operator checklist) · **no real provider adapter and no `lemonsqueezy` wiring** (F18, a sibling and not a dependency) · **no `bookings.source`** (C7 — F50's) · **no realtime vendor, no socket, no SSE** on the return page (pre-decided #23) · **no new E2E spec** — the flow ends at a third-party redirect · **no he/ar parity guard** (F45's) · **no `provider_session_id` lookup fallback** if F18's adapter reads the identifier back from a different place — F19 must **not** paper over a mismatch, and `GATEWAY_WEBHOOK_UNMATCHED` is what makes it visible instead of silent.
