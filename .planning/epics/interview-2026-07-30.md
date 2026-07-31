# Program interview — E3 close-out through E10

**Date**: questions drafted 2026-07-29, answered 2026-07-30 · **Scope**: every remaining feature, F15 through F49 · **Purpose**: one upfront sitting so the autonomous build loop (`/modryn-loop`) never has to stop and ask.

17 questions were asked. A further 49 decisions were **pre-decided** by research rather than asked — the rule applied was: if the answer is forced by this repo, by Israeli law, or by public research, and the alternatives exist only to look balanced, it is not a question. Those are recorded in §3 and carry the same authority as an answered question.

Specs cite these as `Interview Q<n>`. Where an answer conflicts with shipped reality at spec time, the spec records the conflict, takes the codebase-consistent reading, and continues — it does not stop.

---

## 1. Standing approvals

These govern the loop itself.

**Q1 — Spec gate (Gate 1): blanket approval, except money and legal.**
The loop writes each remaining spec, checks it against this interview plus the roadmap, approves it itself, and proceeds. **Exception — these stop for the user:** anything touching payments, refunds, privacy-law text, or tenant billing. Concretely that means F17, F18, F19, F20, F29 and F48 present their spec and wait; every other feature self-approves.
*Basis: every v1 risk that a follow-up PR cannot recover is a money or legal one.*

**Q2 — Design gate: self-approve the familiar, show the novel.**
Screens assembled from existing components self-approve (designer + `design-critic` must both accept). Genuinely new interaction patterns come to the user as a clickable prototype first. **Named as novel: the staff shift board (F34) and the seamstress capacity matrix (F42).** Token and contrast compliance is mechanically checkable, so a form carries no design risk; a novel matrix does.

**Q49 (pre-decided) — branch/PR strategy unchanged.** One feature per branch off `main`, spec → plan → TDD → dual review → PR.

**Auto-merge** — a PR merges when all three blocking CI jobs are green: `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`. The two `continue-on-error` jobs are ignored. `main` is unprotected, so `.claude/scripts/merge-gate.sh` is the gate; never `gh pr merge --auto`.

**Blocked features** — park it, record the blocker, move to the next unblocked feature. Re-check external blockers every iteration.

---

## 2. Answered questions

### E3 close-out

**Q4 — Short-notice reminder: send immediately, drop «מחר».**
One date-led body serves every timing band:
`{{boutique}}: תזכורת — התור שלך ביום {{weekday}}, {{date}} בשעה {{time}}. לאישור הגעה או ביטול: {{link}}`
The bride gets two texts within minutes on a same-notice booking; that is accepted (~$0.77 for the second at Twilio's verified +972 rate) because the confirm-attendance signal is the whole no-show defence. The 24h / 2–24h / under-2h bands stay as approved at Gate 1 (see pre-decided #6).

**Q5 — F16 Hebrew: approved as drafted.**
All 19 manage-page strings, all 4 SMS bodies, the cancel-cost line and the softened confirmation-screen line in `.planning/design/screens/manage-booking/copy.md` are approved and may be built on. Any later wording change is a one-line edit in one file. **Counsel sign-off on the SMS bodies is still required before a real provider goes live** — that gate is unchanged.

**Q6 — F15 scope: status management plus owner reschedule.**
In: day-filtered booking list, booking detail, mark confirmed / cancelled / no-show / completed, resend the manage link, correct a wrong phone number, **and reschedule a booking to another slot** (needs a slot picker inside the manage app).
Out: **owner-created bookings.** A booking the owner creates has no bride-verified phone and no accepted terms, so the SMS control link would target an unverified number — new legal and security ground that earns its own spec, not a corner of F15.

### E4

**Q7 — Payments: build against a fake gateway now.**
Build the provider-agnostic payment port **and** F19's deposit flow (hold, expiry sweeper, webhook → confirmed) against a fake gateway. This is the play F11 already ran for SMS, and it is why F16 is buildable today with no SMS account. The parts most likely to be wrong — hold expiry racing a late webhook — do not depend on Grow.
Consequences for the queue: **F17 (the port) and F19 (deposit flow) are buildable now. F18 (the real Grow adapter) stays parked** on the merchant account. E5 features ship deposit-free and grow their deposit branch when Grow lands.

**Q8 — F20 privacy text: platform-written Hebrew default, replaceable per boutique.**
Ship a platform default for both the collection notice and the data-processing agreement; each boutique can override it from settings. This is the only option that leaves the pilot legal on day one — Amendment 13 (in force 14 Aug 2025) requires notice at the moment of collection. The default is **not lawyer-reviewed**; swapping in counsel's text later edits one settings field per tenant. Retention periods are pre-decided (#10).

### E5

**Q9 — Reserved dress means RENTAL.**
The dress leaves for a wedding date and comes back. `מוזמן לתאריך מסוים` becomes a real date range — wedding date plus a cleaning/return buffer — so the storefront can say "unavailable 12–18 Aug" while still taking fittings on every other date. Needs a reservations table with dates and an overlap check. Rental is the dominant Israeli model and the only reading where "reserved for a specific date" means anything; it can absorb sale and made-to-order later.

**Q10 — Signup: INVITE CODES ONLY.** ⚠️ *User chose against the recommendation (which was open signup with operator approval before go-live).*
Boutiques join only via a code the operator issues. No open self-serve registration, no public subdomain claiming. This removes almost the entire abuse surface — no captcha, no rate-limit-the-world, no slug reclamation in F26's scope — and accepts that growth runs at operator pace. **F26 is therefore smaller than the roadmap assumed**: an invite-code redemption flow plus gateway-connect onboarding, not a public signup funnel.

### E6–E9 (staff, in-store, workshop)

**Q11 — Staff login: PHONE + SMS CODE.** ⚠️ *User chose against the recommendation (which was email + password per person).*
Staff sign in with the same OTP primitive customers use (F11). No work emails, no passwords, no reset helpdesk. Accepted costs: **every staff login costs an SMS and a ~30-second round trip**, and a second login path exists alongside the owner's email/password. Two things the specs must handle: production staff login depends on the same SMS sender-ID registration as customer messaging, and per-person attribution must still be recorded for the PII audit trail Amendment 13 expects — the OTP identifies a named `staff_users` row, so attribution survives. Roles reuse the existing `staff_users.role` column (pre-decided #24).

**Q12 — E7 before E8.**
Fitting rooms + SOS ship before the weekly scheduler. E6 already provides a manual way to mark who is on shift, so E8 removes a chore; nothing substitutes for a staffer in a fitting room being able to call for help. E7 is 2 features against E8's 3. The owner keeps ticking "on shift" by hand until E8 lands.

**Q13 — Workshop workload measured in HOURS, from preset bands.**
Each job carries an effort estimate tapped from bands — 30 min / 1h / 2h / half-day / full-day — and each seamstress has an hourly capacity. Only a time-based unit can be subtracted from a wedding date, which is the entire point of the overload alert. Risk accepted: consistently bad estimates make the alerts lie. Priority enforcement stays advisory (pre-decided #40).

### E10

**Q14 — SMS stays the default channel; WhatsApp is a per-boutique toggle.** ⚠️ *User chose against the recommendation (which was WhatsApp-default with SMS fallback).*
SMS remains authoritative for confirmations and reminders. WhatsApp is opt-in per boutique. Nothing existing changes behaviour and one channel stays the source of truth; the accepted cost is that most brides keep receiving the channel they are least likely to read, while both codepaths exist anyway. Delivery goes through Twilio rather than Meta's Cloud API (pre-decided #43), and Meta business verification should be filed now regardless (pre-decided #42).

**Q15 — Billing: flat base fee plus metered messaging.**
Messaging is the only cost that scales with a tenant's behaviour, and the per-tenant message log needed to meter it already exists. Invoices carry 18% VAT from the operator's Israeli entity; the tax-authority allocation-number API is explicitly out of scope (pre-decided #45).

**Q16 — Video: short clips on dress pages only.**
The owner uploads, the platform transcodes and serves, via Cloudflare Stream (pre-decided #44). Movement is the honest reason a gown needs video, and it attaches to a page that already exists rather than a new feed that depends on a weekly content habit. No storefront reels feed.

**Q17 — The storefront sits alongside her existing site.**
Her Wix site and Instagram link into the booking storefront. No per-boutique custom domains, no certificate management, no DNS support surface. SEO shrinks to being findable and fast — build-time prerender plus sitemap and per-tenant robots.txt (pre-decided #46). Custom domains become a paid upgrade once the pilot proves out.

### Cross-cutting

**Q3 — Arabic: ship the keys now, translate later.**
Every feature from here on adds Arabic resource keys alongside Hebrew, left untranslated. Arabic is not live for the pilot. The expensive half — RTL layout — is already paid for by Hebrew, so this turns the eventual launch into a translation job rather than a retrofit across ~28 features. Mechanics are pre-decided (#47).

---

## 3. Pre-decided (not asked)

Full text below. These bind the loop exactly as answered questions do. Where one names `*.ourbrand.co.il`, read `*.modryn.co.il` — the placeholder was retired by F30.

> **SUPERSEDED 2026-07-31 by the floor-management program** (`LOOP-STATE.md` → `rulings_2026_07_31`). Read these four rows through that ruling, and do not treat the rows below as still binding on the points named:
> - **#29** (SOS: role fanout, *no escalation timer*, no name picker) — **overridden**. A 30-second unacknowledged escalation to the shift manager is reinstated, and targeting is a specific colleague *or* the shift-manager role. First-accept-owns and never-silently-dropped survive.
> - **#27** (a reception tablet is just one more signed-in device; kiosk board "a small follow-up if the pilot asks") — the **public wall board is now in scope**. The device-identity half of #27 *stands*: no device picker, everyone signs in as herself.
> - **#39** (five state names received/measured/in_work/ready/collected) — the **labels** are replaced by intake/in_progress/qc/ready/delivered. The **mechanism** (five nullable timestamps, no enum) is untouched.
> - **#24** (`sales` role slug) — the slug is **`sales_assistant`**.
>
> Also settled the same day and not a row here: **Q2's design gates for F34 and F42 are self-approved for this run**, and the program's language scope is **Hebrew only** (Q3/E10 unchanged — `ar` keys keep shipping untranslated, and English is not planned).

| # | Topic | Decision | Basis |
|---|-------|----------|-------|
| 1 | Auto-merge policy for the remaining run (was a question) | Keep the existing pipeline exactly: a feature PR merges when the three blocking CI jobs are green AND a second agent's code review passes. No merge on CI alone; no waiting on the owner's inbox. | This is the process that produced all 16 merged PRs in this repo, so it is proven here rather than assumed — and it is the only option that compensates for main having no branch protection. Verified in .github/workflows/ci.yml: 'Backend (lint, types, tests)', 'Frontend (lint, types, build)' and 'Frontend E2E (Playwright + axe)' are the only blocking jobs. |
| 2 | What the loop does when a feature is blocked (was a question) | Park it — record the blocker, leave a draft PR, move to the next unblocked feature; stop the whole run after 3 consecutive parks. | Most remaining blockers are external accounts the owner must file (Grow, Twilio sender ID, Meta verification, the domain); external-applications.md lists 4 unfinished items, 3 of them multi-week and mutually independent — so stopping on any one wastes the days the others are waiting anyway. The 3-park cap prevents grinding through the backlog leaving wreckage. |
| 3 | F16 confirmation-screen 'keep this screen' line (was a question) | Use the drafted «פרטי התור נשמרו אצלנו, וכדאי בכל זאת לצלם את המסך. אנחנו נחכה לך.» — never promise a text. | The shipped line ('this is your only confirmation') stops being true the moment F16 lands, and naming the SMS explicitly breaks the copy rule against promising something the product may not do — no provider is connected yet and kosher phones never receive SMS at all. Only this wording is true in every case. Folded into the F16 copy approval. |
| 4 | F16 cancel-cost sentence (was a question) | Ship the drafted «לא נגבה תשלום על התור, כך שהביטול אינו כרוך בעלות.» It answers the question she opened the screen to ask, and the in-window / out-of-window split already ships as structure, so E4 swaps one key when deposits exist. | The only alternatives either state something untrue or withhold the one fact the screen exists to give. If late cancellations are the real worry, the deposit is the fix and it is already E4 #19. Folded into the F16 copy approval. |
| 5 | F16 attendance-confirmed micro-copy (was a question) | «ההגעה אושרה. נתראה.» — no exclamation mark. | Mechanically checkable: Frontend/apps/storefront/src/i18n/he.ts and the approved F14 copy deck contain zero exclamation marks, so an exclamation here would be the one string that breaks the product's punctuation register. Pure craft call, no business trade-off. |
| 6 | F16 reminder timing bands (D3) | Kept as approved — 24h+ → send at starts_at minus 24h; 2–24h → send now; under 2h → no reminder. Only the immediate band's wording is re-asked. | Gate 1 approved D1–D10 as proposed (commit d4409c5); re-asking settled decisions wastes the owner's turns. |
| 7 | Manage-page design proposals P2–P5 | Accepted as designed: fact labels reuse the approved booking-screen Hebrew; cancel stays available after attendance is confirmed; the cancelled state carries a rebook link; the red button appears only on the final confirm-cancel click. | The design critic ACCEPTed the deck across two rounds; craft calls with no business trade-off attached. |
| 8 | Boutique name in SMS bodies | Truncate the interpolated boutique name to 25 characters inside SMS templates. | tenants.name is unbounded free text but the 3-segment budget arithmetic assumes 25 chars; truncation is the only way production matches the tested fixture (design finding F-M3). |
| 9 | F16 backfill mechanism (D10) | A one-time command on the existing audited CLI, run once at F16 deploy, minting a link token and scheduling a reminder for every already-confirmed future booking. | D10 approved the backfill and left the mechanism to the plan; the CLI already exists with audit logging. |
| 10 | Retention periods per data class (F20) | OTP codes 15 minutes, sessions at existing TTL, message log 24 months, bookings 7 years, scheduled messages purged with their booking — all as tunable settings, flagged for counsel confirmation at the F21 audit. | The security checklist already fixes the orders of magnitude; exact numbers are one-line settings changes. |
| 11 | F21 sequencing | Checklist rows that need no production environment (dependency scanning, security headers, accessibility pass, tenant-isolation suite) get picked off as features land; F21 as a feature waits on production stand-up, which waits on the domain. | The production domain is still unfiled (external-applications item #2), so F21 cannot start regardless. |
| 12 | Waitlist offer window and quiet hours (was a question) | Default 2-hour claim window with quiet hours 21:00–08:00 (night offers wait for morning), both shipped as per-boutique settings. | Two hours clears a realistic 4–5 person queue inside one day; overnight offers expire unseen anyway, so quiet hours cost nothing. Both are settings defaults, not architecture — changing either later is one config row. Israel's Spam Law restricts marketing only, so a requested waitlist offer is legal at night; this is a conversion choice. |
| 13 | Offer cascade shape | Offers go out one at a time with an expiry cascade; the claim is an atomic conditional update guarded by the existing partial unique index on active bookings per slot. No broadcast blast. | architecture.md's locked-decisions table pins this exact design, and e5-growth.md says F22/F23 start from it. |
| 14 | What a waitlist entry is bound to, and queue ordering | One entry = (tenant, day, appointment type) joined to an OTP-verified phone; FIFO by join time. No 'any day this month', no per-dress waitlists, no priority scoring. | e5-growth.md Feature 22 states the day+type binding and OTP reuse; nothing in the PRD asks for prioritisation and FIFO is one ORDER BY. |
| 15 | When the cascade gives up on a freed slot | Stop offering once the slot starts in under ~2 hours, and truncate the final offer window so it can never expire after the appointment began. | Pure mechanics; prevents an offer expiring at 10:05 for a 10:00 appointment. |
| 16 | How offer SMS are sent | Offers ride F16's existing scheduled_messages table and worker poller, widening its `kind` CHECK by migration. No new scheduler. | specs/booking-comms.md reserves exactly this; NotificationService.send_sms is already the single writer of message_log. |
| 17 | Client portal login and calendar | OTP-only login (no email, password or social); per-booking .ics download only, no two-way Google/Apple sync. | Both recorded as stakeholder decisions in ROADMAP and architecture.md. |
| 18 | Client notification bell liveness (was a question) | Refresh on page open/reload. No polling loop, no realtime service pulled forward. | Every event the bell would show already sends an SMS the same second, so the bell is a history list, not the alert channel. 60-second polling is a one-line change if the pilot disagrees, and E6 replaces it properly regardless. |
| 19 | Where F27's toggle matrix is stored | tenants.settings JSONB under a `toggles` key, written through F7's atomic single-statement merge. No toggles table, no flag service. | specs/owner-settings.md built that merge specifically so sibling keys added by later features are never clobbered. |
| 20 | Scope of the F25 platform console | Reuses the v1 CLI's audited command layer as its service layer and exposes the same operations (provision / suspend / list / owner password reset); the CLI is deleted at parity. No console-only powers. | e5-growth.md Feature 25; extra capabilities would fork the audit surface E1 #6 established. |
| 21 | F29 caching and refund safety rails | Slug/config lookups cached with tenant-scoped keys plus a bounded short-TTL negative cache for unknown hosts. Every automated refund carries an idempotency key, asserts its amount against the recorded payment row, and writes an audit_log entry — no extra owner-confirmation UI beyond the existing refund-due task. | The bounded negative cache is a Feature 4 security-review requirement; the refund rails are called non-negotiable spec scope in e5-growth.md. |
| 22 | k6 load-pass targets | Derived at spec time from staging metrics multiplied to the roadmap's 50-tenant horizon, not chosen as a product question. | Thresholds come from measurement of real pilot traffic, not opinion. |
| 23 | Realtime transport for the staff board (was a question) | Start with ~5-second refresh, no vendor. Add Pusher later only if the pilot shows refresh is too slow — E9's workshop board assumes Pusher exists by then. | The architecture already mandates versioned events + full-state refetch, so the API shape is identical either way and swapping in Pusher later is near-free; a 10-staff boutique needs under 20 concurrent connections and a bridal queue does not change faster than a human reads it. Starting with Pusher buys a vendor, a bill and a channel-auth layer up front. |
| 24 | Staff role set and identity storage | Reuse the existing `staff_users.role` column and `StaffRole` enum: owner, shift_manager, reception, seamstress, sales. No second identity table. | Backend/app/models/constants.py already declares StaffRole reserving it for E6, and sessions already key on staff_user_id. |
| 25 | Realtime correctness model | Events are versioned hints, the server is the truth: full refetch on reconnect/version gap; channels tenant-prefixed with server-side authorisation against the session's tenant. | Locked in .planning/architecture.md ('Sockets are hints, server is truth') and its tenant-isolation defence list. |
| 26 | Walk-in check-in data handling (was a question) | Queue ticket by default, auto-deleted a few days after the visit, plus one opt-in checkbox on the check-in form that promotes it to a full customer record. | A bridal walk-in is a high-value lead so discarding all of them is expensive, but Amendment 13's minimisation duty makes 'keep everyone by default' wrong — and Israel's spam law already requires a separate unbundled marketing opt-in, so the checkbox has to exist regardless. Both code paths are trivial. |
| 27 | Where the live board runs (was a question) | Each staff member's own phone, signed in as herself. A reception tablet is simply one more signed-in device on day one; a read-only display mode is a small follow-up if the pilot asks. | One screen, one auth story, and it is the only option that puts an SOS page in the pocket of the person who must answer it. Costs nothing to reverse. |
| 28 | E6 done bar (was a question) | E6 is finished at queue + dispatch — the manager assigns a named staffer and that staffer is notified. No wait-time analytics in E6. | Dispatch is what turns a queue into a product, and it produces the staff↔client assignment record that E7 (fitting rooms) and E9 (alterations) both depend on. Reporting has no data to stand on yet. |
| 29 | SOS routing and delivery (was a question) | She picks a role ('I need a seamstress'); it pages every on-shift staffer with that role and the first to accept owns it. In-app only, no SMS paging, no escalation timer. | On a shop floor you need a skill, not a specific person — and role targeting needs no name-picker, no timer and no new data, since E6 already records role and on-shift status. Escalation can be layered on the same alert record later if the pilot ever drops a page. |
| 30 | QR check-in code and queue position | One static QR per boutique pointing at {slug}.ourbrand.co.il/checkin, printed once. Queue position computed on read (arrival order within the day), never stored. | Per-visit codes need a screen or printer at the door; stored positions must be renumbered on every insert — a race for no benefit. |
| 31 | Fitting-room occupancy | One active assignment per room, enforced by a partial unique index on the room where the assignment is active — the same structure booking already uses for slots. | The double-book-proof pattern is already spec'd and tested in E3 #13; reusing it costs one index. |
| 32 | Staff notification bell | In-app bell only — no browser/mobile push, no APNs/FCM. | A push stack is E10-scale work; the bell's consumers are people already looking at the app. |
| 33 | Shift tiers for the roster (was a question) | Owner-defined shift templates per weekday, pre-filled from the boutique's existing opening hours. | The booking engine already stores opening hours per weekday per tenant, so seeding shifts from them asks the owner for nothing new and is correct on day one — while hard-coding three tiers bets that every boutique works the same week. E3 #12's availability engine stays the single source of the tenant's week (Sun–Thu, short Friday, Saturday closed). |
| 34 | Ex-staff PII retention (was a question) | Auto-erase personal fields 7 years after last day, running on the E4 #20 retention job; operational history (dispatches, room assignments, roster) retained permanently but de-identified. Flagged for the owner's lawyer to confirm the number — the platform only enforces it. | 7 years is the general Israeli practice for employment documents (10 for tax), so the platform enforces the clock the bookkeeper already keeps; 'never automatic' is the pattern regulators look for and 12 months loses a year-three wage claim. The number is a settings value, changeable in one line. |
| 35 | Offboarding mechanics | Soft-delete the staff record, retain operational history, scheduled scrub blanks personal fields at the retention deadline via E4 #20's machinery. | ROADMAP E8 #1 per PRD §11.3; the job already exists for customer data. |
| 36 | Availability submission window | Weekly, Sunday-start, deadline stored as a tenant setting rather than hardcoded. | Standard rota mechanics; a hardcoded deadline becomes a support ticket per tenant. |
| 37 | Feature order inside E6/E7/E8/E9 | E6: F31 staff records/roles → F32 live-update substrate → F33 QR check-in → F34 shift board → F35 staff bell. E7: F36 fitting-room registry + assignment → F37 SOS. E8: F38 HR → F39 availability → F40 roster. Only the E7-vs-E8 ordering is asked. | Forced by dependency, not preference. |
| 38 | Accessibility and language for staff screens | Check-in form, shift board, SOS and roster all ship Hebrew-first RTL against existing design tokens and must pass IS 5568 / WCAG 2.0 AA. | Legal requirement in the roadmap's standing risks; not a per-epic choice. |
| 39 | E9 job lifecycle and scheduling | Five states (received → measured → in_work → ready → collected), each a nullable timestamp column on the job row; alteration fittings reuse the E3 slot engine as an appointment type, with multi-fitting jobs linked by alteration_job_id. No event table, no second scheduler. | The roadmap fixes the five states; the slot-engine spec already supports capacity and concurrency-safe claims, and a parallel scheduler would duplicate the hardest-won code in the repo. |
| 40 | Workshop priority enforcement (was a question) | Advisory — the system flags conflicts and ranks the queue by wedding date; every reassign / split / expedite stays a human click. | ROADMAP E9 #2 already words this as 'manual reallocation: reassign / split load / expedite from the matrix'. Reassigning a job is a staffing decision, not a scheduling one, and the system has no view of skill, sick days or who is halfway through a garment. |
| 41 | Seamstress identity, availability and workshop analytics | Seamstresses are E6 staff_users with the seamstress role; daily availability comes from the E8 published roster. Analytics = jobs completed per seamstress per week + median time-in-state, computed as SQL over the timestamped job rows. No new tables, no BI tool. | E6 #1 defines the role; E8 #3's published roster is already the source of truth for 'current shift'; state timestamps make both metrics a single query. |
| 42 | Meta business verification timing | File the Meta Business / WhatsApp verification now regardless of the channel answer, and move that tracker row to 'filed'. | Free, multi-week worst case, and the roadmap already commits to starting it during v1. |
| 43 | WhatsApp integration shape | Go through Twilio as the WhatsApp provider rather than Meta's Cloud API directly — WhatsApp becomes a second channel on the existing NotificationService port. | F11 already shipped NotificationService as a provider port and Twilio is the chosen SMS vendor with an account in flight; a direct Cloud API integration means a second set of credentials, webhooks and billing for the same messages. |
| 44 | Video vendor (if video ships) | Cloudflare Stream — not Mux, not self-hosted ffmpeg. | Bundled encoding, storage, delivery and CDN in one per-minute price with no egress fees; at a handful of clips per boutique the alternatives cost more in operations than they save. |
| 45 | Billing invoicing mechanics | F48 issues invoices with 18% VAT from the operator's Israeli entity and does NOT integrate the tax authority's allocation-number clearance system. | Allocation numbers are required only above ₪10,000 (Jan 2026), falling to ₪5,000 (Jun 2026); a monthly per-boutique fee sits far below both. Revisit only if a tenant invoice approaches the threshold. |
| 46 | SEO technique | Build-time prerender of the storefront's public routes plus sitemap.xml and per-tenant robots.txt — not SSR. | The storefront is a Vite SPA and catalog changes are owner-triggered, so re-prerendering on publish is far cheaper than operating an SSR process per tenant. |
| 47 | Arabic implementation mechanics | Add `ar` resource bundles to the existing i18next setup and reuse the current RTL layout wholesale; no direction-switching logic, no second stylesheet. | Hebrew already makes RTL the default and Arabic is also RTL — only strings, number/date formatting and a language switcher are missing. |
| 48 | Owner calendar view | A month/week rendering layered over the existing bookings list API. No new endpoints, no extra calendar library. | F15 already ships the list plus day filter; a calendar is a different arrangement of data the API already returns. |
| 49 | Branch and PR strategy for the remaining run | Unchanged — one feature per branch off main, spec → plan → TDD → dual review → PR. | All 16 merged PRs used it; changing process mid-run costs more than it could save. |

