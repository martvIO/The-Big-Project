# Log

Chronological record of all operations. **Append-only — never edit an existing entry.**

## [2026-07-23] setup | .brain initialized
Created the code wiki at `.brain/` for the Boutique Platform repo: 1:1 page coverage of all
350 tracked files (`.brain/` itself excluded from its own corpus).

Machinery: `brain-page-path.sh` (the canonical repo-path ↔ page-path mapping),
`brain-scan.sh` (missing/stale/orphan, keyed on per-file `git hash-object` rather than repo
HEAD), `brain-index.sh` (generates `wiki/index.md`), six page templates, and SessionStart /
SessionEnd hooks registered in `.claude/settings.json`.

Behavioral wiring: Principle 8 "Consult the Second Brain First (Orientation, Not Truth)" added
to `.claude/CLAUDE.md`; `/brain-ingest` and `/brain-sync` commands added; `brain-scan`,
`brain-index`, `brain-lint`, `brain-check` targets added to the `Makefile`.

Vault: `.brain/` symlinked to `/Users/mrwen/second-brain/boutique-platform`. Verified that qmd
does **not** follow the symlink, so a dedicated collection is registered separately rather than
relying on the vault's `**/*.md` glob.

## [2026-07-23] ingest | Wave 0 — foundation, and Wave 1 partial (backend/)
Wrote 3 synthesis pages ([[Documented Stack Vs Actual Stack]], [[Repo Hazards]],
[[Frontend Scaffold Reality]]), 12 entity pages, and 9 concept pages including
[[Row Level Security]].

Wave 1 (backend/, 70 pages) was dispatched as 4 parallel batches but all four terminated on an
API session limit after writing 10 source pages: `backend/app/{__init__,main,cli,worker}.py`,
`backend/app/core/{__init__,config}.py`, `backend/app/auth/__init__.py`,
`backend/app/db/{rls,session}.py`, and `backend/tests/conftest.py`.

No state was corrupted — the pages *are* the checkpoint, so `brain-scan.sh --missing`
recomputed the remaining 340 from git with nothing to repair. Resume with `/brain-ingest`.

Verified this pass: drift detector (CURRENT → STALE → CURRENT, `touch` correctly does not flag,
`kind: generated` excluded), SessionStart baseline + JSON context injection, SessionEnd queue
writing and its degenerate cases, `make brain-check`, and `--lint` (0 broken links, 0 structural
failures).

## [2026-07-27] sync | 4 stale reconciled, 0 orphans removed
Rewrote the 4 pages that drifted when F7 (boutique settings) and F8 (catalog + media)
shipped (commits d05a2d4, 22234c4, 8c7aeb9, d9441d1, cbce979): backend/app/core/config.py
(media-storage + terms-throttle settings, third boot validator), backend/app/db/session.py
(role guard now also refuses table ownership), backend/app/main.py (boutique + catalog
routers, CsrfOriginMiddleware, media-storage wiring, full domain/media exception-handler set,
RequestValidationError→400 house shape), backend/tests/conftest.py (real-MinIO
Testcontainers fixture). Stale 4→0. 417 files still have no page — all missing, none orphaned;
resume documentation of the new boutique/catalog/storage code with /brain-ingest.

## [2026-07-28] sync | 4 stale reconciled, 0 orphans
Reconciled backend/app/core/config.py, backend/app/main.py (F10: storefront service/limiter on app.state, SecurityHeadersMiddleware outermost, docs/openapi dark outside dev, StorefrontThrottledError handler, /storefront router), and rewrote backend/app/storefront/{router,schemas}.py.md whose pages predated the F10 spec-conformance pass (per-tenant throttle, StorefrontService, renamed flat wire models). Queue at 123 entries — no rotation.

## [2026-07-29] sync | 4 stale reconciled, 0 orphans
Reconciled the drift left by all four E3 features landing since 3bf3795. backend/app/core/config.py
(F11/F13 SMS + OTP + booking knobs, and the fourth boot validator — fake sender and OTP_DEV_CODE are
now production boot failures); backend/app/main.py (NotificationService/OtpService/BookingService on
app.state, _build_sms_sender mirroring _build_media_storage, seven fixed error bodies, and the
one-budget-one-limiter-instance constraint); backend/app/storefront/{router,schemas}.py (F12's slot
grid and F14's GET /terms — three → six public GETs, eight → twelve wire models). Recorded three
omissions worth keeping: why SlotRow drops `remaining` (it equals capacity whenever nothing is booked,
smuggling a fenced field past a key-based absence walk), why StorefrontTerms cannot subclass the manage
schema, and why verify is throttled separately from send. Stale 4→0. 577 files still have no page —
all missing, none orphaned. Queue at 367 entries — no rotation (threshold 500).

## [2026-07-30] sync | 5 stale reconciled, 0 orphans
Reconciled the drift from F16 (booking comms lifecycle, PR #21) plus F30 (MODRYN branding, PR #20).
All five stale pages traced to one commit, 7a2380b. backend/app/worker.py needed a full rewrite rather
than a patch: it stopped being a job-less placeholder that slept forever and imported nothing from app,
and became the real scheduled-message poller (build_sender / poll_once / main, ensure_safe_database_role
at boot, enumerate-then-claim because scheduled_messages carries FORCE RLS while tenants is deliberately
RLS-free, per-tenant failure containment so one bad row cannot silence every boutique). Its old page had
predicted the first real poller "should add the database role check and a graceful-shutdown path before
this file gets a test" — the role check and the tests arrived, the graceful shutdown did not, so that gap
is now recorded as the deliberate at-least-once posture. backend/app/main.py (BookingCommsService and
ManageBookingService on app.state; three POST endpoints rather than GETs, because a manage token in a
request line reaches access logs, Referer and history; ONE body for unknown/rotated/malformed tokens so
the lookup is not an oracle for token shape). backend/app/cli.py (backfill-booking-links, a re-runnable
one-time deploy step on the audited command layer). backend/app/core/config.py (the booking-lookup
anti-scrape budget — the one endpoint that answers a secret — and worker_poll_interval_seconds, a tick
rather than a limit). backend/app/storefront/router.py (the ""-to-null WCAG 2.4.4 collapse moved out to
profile_text in storefront/validation.py, shared with F16's manage page).
Corrected two pre-existing inaccuracies while in the affected sections: main.py's "seven rate limiters
on app.state" was wrong in both number and placement — there are ten instances, only two parked on
app.state — and cli.py's four subcommands are now five. Stale 5→0. 621 files still have no page, none
orphaned; largest unbuilt clusters are .claude/commands/spartan (70, vendored) and backend/tests (51).
Queue at 379 entries — no rotation (threshold 500).

## [2026-07-30] sync | 2 stale reconciled, 0 orphans, E3 epic boundary
Ran at the E3 epic boundary, after F15 (owner booking management, PR #24) closed the epic. Both stale
pages were made stale by that merge and both were rewritten from their diffs rather than regenerated.

backend/app/core/config.py — one additive change: `booking_owner_sms_*`, a single per-tenant window
shared by the three owner taps that spend real SMS credit (resend, phone correction, reschedule). Owner
cancel is deliberately off it, because `cancelled` is terminal and its ceiling is therefore the number of
bookings the boutique has. Reschedule is the one that needed it — a booking can be walked between two
legitimately offered slots indefinitely, one SMS and one token rotation per hop.

backend/app/main.py — F31 and F15 landed together and the page now carries their interaction, because it
is the kind of thing a page is for. Both features had independently invented a `NotAuthorizedError`; the
rebase merged with no textual conflict, Python's second binding won, and both handlers registered against
F15's class — leaving F31's unhandled, so every role-gated 403 in already-merged code would have returned
a bare 500. Ruff's F811 on CI caught it. The page now states the general rule plainly: there is no error
registry in this module, an unmapped typed error is a 500, and a *duplicate* one is worse than a missing
one because it fails silently. Also records F15's fourth /manage router, its three new error bodies, and
why the owner slot grid injects StorefrontService instead of re-materializing the grid.

Stale 2→0. 646 files still have no page and none are orphaned — the backlog grew from 621 as F15 and F31
added files, and it needs a dedicated /brain-ingest pass rather than an epic-boundary chore; largest
unbuilt clusters remain .claude/commands/spartan (vendored) and backend/tests. Queue at 385 entries — no
rotation (threshold 500).

## [2026-07-31] ingest | Wave 1 — the application layers (264 source + 49 directory + 53 topic pages)
Scope chosen by the user: `backend/app/**` (99 files) and `frontend/{apps,packages,e2e}/**` (155) — the
code actually written here, deliberately excluding the 209 vendored `.claude`/`.agents` files, the 78
`.planning` docs and `backend/tests`. Coverage went 13 pages → 277. Every one verified CURRENT.

Run as 26 parallel leaf-writing batches (10 backend, 16 frontend), then a 4-agent topic wave, with the
index, the log and all 49 `_index.md` files written by the orchestrator alone, per writing rule 10.

**Directory pages are generated from the leaf pages, not re-derived.** Each `_index.md` extracts its
per-file one-liner from that page's own `**Role.**` sentence, so an index entry cannot drift from the page
it points at; only the `**Purpose.**` line is hand-authored. `blob` is `git ls-files -s <dir> | shasum`,
so adding or removing a file marks the directory stale.

**Synonym collapse.** Parallel writers independently coined competing names for the same idea — `Advisory
Lock` / `Advisory Locks` / `Advisory Lock Serialization`, `Partial Unique Index` / `…Claims`, `RTL And
Bidi Isolation` / `RTL Bidi Isolation` / `Hebrew RTL Bidi`, `Audit Log` / `Audit Trail`, `boto3` / `Boto3`
and seven more. 14 aliases were merged into canonical titles across 72 pages before any topic page was
written; without that step the wiki would have shipped with a dozen near-duplicate concepts. **This is the
predictable failure mode of a parallel ingest and the next wave should expect to repeat the pass.**

New concepts (33) and entities (20) are grounded in this repo rather than generic: `Advisory Lock` names
the four distinct `hashtext` key spaces and the three writers that deliberately take no lock; `Partial
Unique Index` records that nothing ties `seat_index` to its slot's capacity (0008's CHECK is a flat
1..1000 and capacity is enforced in Python only); `Rate Limiting` states the one-budget-one-instance trap
and login's legitimate two-keys-on-one-instance exception; `Tailwind CSS` records that `cn()` is a plain
join with no class-merge, so a call-site utility override does not reliably win.

Two things landed mid-wave and were reconciled by hand afterwards: F51 merged (PR #25), mounting a fifth
`/manage` router and re-staling `backend/app/main.py`, which now carries its three new error bodies and
the `StaffService`-beside-`AuthService` reasoning.

402 files still have no page — `.claude`/`.agents` (209, vendored), `.planning` (78), `backend/tests`
(56), `backend/migrations` and assorted roots. The 167 remaining lint lines are all `page-not-built`
forward links into that set, which is the correct state, not a defect. Zero stale, zero orphans, zero dead
topic links, zero broken file links. Queue at 385 entries — no rotation (threshold 500).
