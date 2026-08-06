# F29 — Pre-scale gate: refund-API automation + k6 load pass + Redis caching

**Epic**: E5 (the epic's ship gate — last feature in the epic) · **Size**: M
**Depends on**: F18 (merged, PR #31 — LS adapter; LS test mode has a refunds API), F21 (merged, PR #48 — hardening pass that recorded the k6 cut). Both deps are satisfied; F29 is pickable.
**Feeds**: nothing. Interview Q10 (invite-codes-only signup) removed the F26 public-launch gate — `LOOP-STATE.md` records F26 is "no longer gated by F29". A red k6 blocks only E5's own success criterion.
**Gate 1: USER — money surface (Interview Q1). Spec stops here until answered.**
**Bindings**: pre-decided #21 (refund rails + tenant-scoped cache keys + bounded negative cache), pre-decided #22 (k6 targets from staging metrics at the 50-tenant horizon), E1 #4 security finding (`ROADMAP.md:233`, `storefront-browse.md:382`).

---

## What exists today (verified against the tree, not the epic brief)

**Refunds — the epic brief is stale.** e5-growth.md says "invoke the refund call E4 #18 wrapped-but-never-invoked". That call does not exist:

- The `PaymentGateway` port ships **no `refund()`** — D12, "no consumer, no method" (`Backend/app/payments/base.py:106`, `gateway-port.md:563`).
- The LS adapter wraps **no refund endpoint** (`lemonsqueezy.py` — methods are `validate_credentials`, `create_session`, `verify_webhook` only; `lemonsqueezy-adapter.md:70`: "**No refunds.** F29's, and it now has an API to build against").
- F19 writes **no** `refund_due`/`refunded`/`forfeited` row anywhere (D16 "recorded, never executed"; `booking/schemas.py:170`).
- `webhook_router.py:114` IGNOREs-and-logs `order_refunded` events.

What DOES exist, and what this feature builds on:

- `refund_due_agorot()` — the terms-derived refund/forfeit computation, display-only (`booking/owner.py:100`), surfaced as the owner console's refund-due marker on cancelled+paid bookings (`OwnerBookingRow.refund_due_agorot`, D18). This marker is "the existing refund-due task" pre-decided #21 names.
- `payments` CHECK (migration 0012) and `PaymentStatus` already carry `REFUND_DUE`, `REFUNDED`, `FORFEITED` — declared speculatively for exactly this feature, writers for none (`models/constants.py:266`).
- `PaymentService` is the single money-writer with an amount-assertion precedent: D14's `settle_from_webhook` asserts webhook amount against the recorded row and refuses mismatches. The refund is the same class of write and copies the doctrine.
- The tenant-scoped `audit_log` `GATEWAY_*` action family, written in the same transaction as the write it describes, with a real `actor_id` (D26).

**So F29 ADDS the refund method to the port and the adapter** — it does not merely invoke one. D12 retires by its own rule: the consumer now exists.

**Tenant resolution.** `app/tenancy/middleware.py` + `resolver.py`: `TenantResolver` protocol (`async (slug) -> TenantContext | None`) injected at `create_app(resolver=...)`; `RepositoryTenantResolver` does one indexed DB lookup per request, docstring: "Caching is deliberately deferred to E5". The seam this feature was designed for already exists. E1 #4's finding: any syntactically valid non-reserved slug costs an un-throttled DB lookup — an unknown-host flood hammers the DB.

**Redis / k6.** `redis` is not in `Backend/pyproject.toml`. No `k6/` or `load/` directory exists anywhere in the repo. No metrics stack exists on staging (Railway: uvicorn API + worker + managed PG16, nothing else — `staging-and-external-apps.md`). **Pre-decided #22's derivation ("targets from staging metrics") is therefore impossible today** — surfaced as Gate 1 Q3.

---

## Workstream A — refund-API automation (separately shippable)

Replaces E4 #19's manual-console step: today the owner sees a refund-due marker and moves money by hand in the provider console, outside the product, unrecorded.

### Design

1. **Port**: `PaymentGateway` gains `async def refund(credentials, *, provider_transaction_id, amount_agorot, idempotency_key) -> RefundResult`. `UnconfiguredGateway` raises (same posture as `create_session`). Exact LS endpoint pinned at plan time from the LS docs (test mode confirmed to expose a refunds API — `lemonsqueezy-adapter.md:4`).
2. **`PaymentService.execute_refund(tenant_id, payment_id, *, actor_id)`** — PaymentService stays the single money-writer:
   - Recompute the refund amount fresh via `refund_due_agorot()` against the booking's accepted terms version. **Assert** `0 < amount <= payments.amount_agorot`; on violation write `REFUND_AMOUNT_MISMATCH` to `audit_log` and refuse **without calling the provider** (D14 doctrine).
   - **Claim by conditional UPDATE**: `SET status='refund_due' WHERE id=? AND status='paid' AND deleted_at IS NULL`. Zero rows = already claimed/refunded → idempotent no-op. This guard is ours and does not rely on the provider.
   - Call `gateway.refund(...)` with **idempotency key = `payments.id`** (stable across retries, so a lost response cannot double-refund even provider-side).
   - Success: `SET status='refunded', provider_refund_id=?, refunded_at=?` (two new columns, one migration) + `REFUND_EXECUTED` audit row, same transaction, real `actor_id`.
   - Provider failure: row stays `refund_due` with scrubbed `error` (never a response body), `REFUND_FAILED` audit row; the task stays open and retry is another click — safe because the idempotency key and the claim guard both hold.
3. **Audit table**: tenant-scoped `audit_log`, per pre-decided #21 and the shipped `GATEWAY_*` precedent. `platform_audit_log` is the operator provisioning trail and gets no rows here.
4. **Trigger surface**: Gate 1 Q1. Recommended: one owner click on the existing refund-due task — no new confirm modal (pre-decided #21: "no extra owner-confirmation UI beyond the existing refund-due task"). Route: `POST` on the owner router taking the booking/payment id.
5. **Frontend (/manage)**: the refund-due marker on a cancelled+paid booking gains a button (בצע החזר); after success it renders the refunded amount and date. Hebrew copy with untranslated `ar` keys, no exclamation marks. Loading/disabled state while in flight; backend error message surfaced per house error-extraction rule.
6. **Out of workstream**: `order_refunded` webhook reconciliation (a hand-issued console refund marking the row) — stays IGNORE-and-log; note for a follow-up. No new SMS to the bride (the cancel SMS already exists). No arbitrary-amount refunds (Q2).

### Acceptance criteria (A)

- [ ] Two concurrent `execute_refund` calls on one payment → exactly one provider call (fake gateway counts), one `refunded` row, one `REFUND_EXECUTED` audit row — a race test in the F19/E3 discipline.
- [ ] Amount mismatch (tampered/absent terms, zero/negative, > `amount_agorot`) → refused before any provider call, `REFUND_AMOUNT_MISMATCH` audited.
- [ ] Provider 5xx → row stays `refund_due`, scrubbed `error`, `REFUND_FAILED` audited; a retry then succeeds and the provider fake saw the same idempotency key twice.
- [ ] Refund on a non-`paid` row (pending/expired/already refunded) → no-op, no provider call.
- [ ] Owner-console e2e: cancelled+paid booking → button → refunded state; axe zero violations; `he` + `ar` keys present.
- [ ] Every audit row carries the real `actor_id` (D26).

---

## Workstream B — k6 load pass (separately shippable)

The pass deliberately cut from v1 (`hardening-audits-uat.md:326`). Nothing exists today; this workstream creates `load/` at the repo root (plain k6 JS, zero backend deps).

### Scenarios

1. **Storefront browse** — home + catalog + dress page, anonymous, tenant `Host` header against staging.
2. **Availability** — month grid + day slots reads (the hottest computed path).
3. **Booking hold** — open a deposit hold at low rate. The OTP wall is a security path and gets **no load-test bypass**; the scenario drives a staging-seeded fixture tenant with pre-issued tokens — mechanics pinned at plan time. If that proves unreasonable, the hold scenario drops to a smoke (1 VU) and the load numbers stand on browse + availability.
4. **Unknown-host flood** — random syntactically-valid slugs; exists to prove Workstream C's negative cache (run before C: baseline; after C: the assertion).

### Where it runs (recommendation, not Gate 1)

A `workflow_dispatch` GitHub Actions job (`load.yml`) targeting staging, also runnable locally (`k6 run`). **Explicitly not** one of the three blocking merge-gate jobs — a load test against shared staging is not a per-PR check. Green = thresholds met on a recorded run; the summary JSON is committed under `.planning/load/` as the gate evidence. Re-run at epic gates, not per PR.

### Targets

Pre-decided #22 wants staging-metrics-derived targets; no metrics exist (see "What exists today"), so defaults are proposed at Gate 1 Q3 and re-derived once real pilot traffic is measurable:

- 50 VUs, 10 min steady: browse p95 < 400 ms, availability p95 < 500 ms, hold-open p95 < 800 ms, error rate < 0.5 %.
- Unknown-host flood, 200 VUs: p95 < 100 ms once the negative cache is warm, zero 5xx.

### Acceptance criteria (B)

- [ ] `load/` scripts exist for the four scenarios with thresholds encoded in-script (k6 `thresholds`), plus a README naming the staging prerequisites.
- [ ] `load.yml` runs them on `workflow_dispatch` against staging and uploads the summary; it is not in the merge-gate job set.
- [ ] One recorded green run at the approved targets, evidence committed.

---

## Workstream C — Redis slug/config caching (separately shippable)

The cache E1 #4 designed `TenantResolver` for, including the bounded negative-result cache its security review required.

### Design

1. **`CachingTenantResolver`** wraps any `TenantResolver` — injected at `create_app`, so tests keep their fake resolvers untouched. Behind it a minimal cache seam (`get/set/delete` with TTL) with two impls:
   - **In-process** (stdlib: dict + monotonic TTL + LRU bound) — the default; dev, tests, and CI need no Redis service.
   - **Redis** (`redis` asyncio client — the feature's only new dependency, added only if Gate 1 Q4 approves the add-on) — selected when `REDIS_URL` is set.
2. **Positive cache**: key `tenant:slug:{slug}` (tenant-scoped per pre-decided #21) → `TenantContext` fields (id, slug, name, settings). **TTL 60 s.**
3. **Invalidation on write**: the owner-settings write path and every tenant mutation (provision/suspend/restore — CLI today, F25 console later) delete the slug's positive **and** negative keys. With Redis this is cross-process; the in-process impl is correct at exactly one API replica (the worker never resolves hosts). `# ponytail:` comment records that ceiling — replica count > 1 requires Redis, full stop.
4. **Bounded negative cache**: key `tenant:miss:{slug}` → sentinel, **TTL 30 s**, only for syntactically valid, non-reserved slugs (invalid syntax never reaches the DB today). Bound: in-process LRU max 10,000 entries; the Redis instance runs `maxmemory` + `allkeys-lru` so a random-slug flood evicts rather than grows. Suspended/deleted tenants are misses (`by_slug` filters active) and land here too — invalidation on restore clears them.
5. Unchanged: the uniform `TENANT_NOT_FOUND` body, `EXEMPT_PATHS`, and every middleware behavior — this is a read-through layer, not a routing change.

### Acceptance criteria (C)

- [ ] Unit: hit serves without a repository call; miss populates; negative hit skips the repository; TTL expiry re-fetches; LRU bound evicts oldest at 10,001; invalidation deletes both keys.
- [ ] Integration: a settings write is visible on the very next storefront request (proves invalidation, not TTL).
- [ ] Integration: after N unknown-host requests for one slug, the repository saw exactly one lookup within the TTL.
- [ ] The k6 unknown-host flood (B4) meets its threshold with the cache on.
- [ ] CI is unchanged: no test requires a Redis service.

---

## Dependency posture

Both deps merged (F18 = PR #31, F21 = PR #48). **Nothing in E5 waits on F29**: Q10 made F26 invite-code-only and removed its F29 gate; F29 is last in the epic and gates only E5's own success criterion. The three workstreams are independently shippable in any order; B's flood scenario is only assertable after C.

## Out of scope

Arbitrary-amount/goodwill refunds beyond Q2's answer · `order_refunded` webhook reconciliation · receipts/קבלה (still blocked on the Grow merchant account — gateway-port.md open item 1) · a staging metrics stack (Railway defaults only; targets get re-derived when pilot traffic exists) · caching anything beyond slug→config (dress pages, availability — measure first) · distributed rate limiting (recorded against E4 #21's follow-ups, not this feature).

---

## Gate 1 questions for the user

Numbered so one word per line answers them.

1. **Refund trigger surface.** Options: (a) fully automatic — a bride cancel inside the refundable window queues the refund with no human action; (b) owner-initiated — one click on the existing refund-due task, no extra confirm modal; (c) hybrid — automatic for in-window bride cancels, owner click for everything else. Pre-decided #21's wording ("no extra owner-confirmation UI beyond the existing refund-due task") reads most naturally as (b); the epic's Risks section ("moves money without a human in the loop") reads as (a). **Recommendation: (b)** — a human stays before every money movement, the provider-console detour still dies, and (a) can be layered on later without rework.
2. **What amounts may be refunded.** Options: (a) the terms-derived `refund_due_agorot` only; (b) also the full deposit for the stranded-late-settlement row (race #15 — bride rebooked herself, deposit stranded on a cancelled row, which F19 explicitly left to F29); (c) any owner-entered amount up to the deposit. **Recommendation: (b)** — (a) leaves race #15 with no remedy again, (c) is a new money-entry surface with new mistake classes.
3. **k6 targets.** Pre-decided #22 derives them from staging metrics; no metrics exist yet, so derivation is impossible today. Approve the defaults (50 VUs steady: browse p95 < 400 ms, availability p95 < 500 ms, hold p95 < 800 ms, error rate < 0.5 %; unknown-host flood at 200 VUs: p95 < 100 ms warm, zero 5xx), to be re-derived from real pilot traffic once it exists — or supply numbers. **Recommendation: approve the defaults.**
4. **Redis spend.** A Redis instance does not exist. Options: (a) provision the Railway Redis add-on now (small monthly cost, usage-based — the epic's success criterion literally says "cached in Redis", and any second API replica requires it for invalidation correctness); (b) ship in-process-only now behind the same interface, add Redis when replicas > 1. Both ship the identical code; (b) spends nothing and flips on via `REDIS_URL` later. **Recommendation: (a)** — the invalidation ceiling of (b) is exactly the kind of latent correctness bug a pre-scale gate exists to close.
