# Spec: Feature 19 — Deposit booking flow (Epic E4)

**Created**: 2026-07-31 · **Revised**: 2026-07-31 (adversarial review round 2 — 32 findings, 9 BLOCKER; all 32 applied, 0 rejected; see "Review findings" at the foot) · **Status**: **Gate 1 SELF-APPROVED 2026-07-31 under the recorded pre-authorization — `.planning/LOOP-STATE.md`'s F19 `gate_1_preauthorized` field. F19 BUILDS. The five money decisions are RECORDED below as MD1–MD5, not gated; exactly one item is parked (MD3's approved Hebrew), and it blocks two strings, not the feature.** · **Epic**: E4 · **Effort**: **L**
**Depends on**: F7 (`tenants.settings.toggles.deposits_enabled`), F13 (the slot claim, the advisory lock, the partial unique indexes), F16 (`scheduled_messages`, the worker process, `send_confirmation`, `upsert_reminder`), F17 (the `PaymentGateway` port, `PaymentService`, migration 0012) · **Feeds**: F20 (inherits whatever columns this adds to `payments`), F21 (hardening/UAT), F29 (refunds), F52 (MD5 moves its cancellation-rate number)

> **On the second gate F17 scheduled, and why this file no longer waits for it. Read this before "discovering" a conflict — there isn't one, and an earlier revision of this file wasted a review round on it.**
>
> F17 really did schedule a second gate for this feature, in two places — `gateway-port.md:512` (*"F19 implements; re-asked at its Gate 1 only if the flow contradicts it"*) and `:495` (*"Owner: user. Trigger: Gate 1, and again at F19's Gate 1"*) — and `.planning/LOOP-STATE.md`'s F19 entry still carries `spec_gate: user`. All three are accurate about themselves and **all three are superseded**. The same entry carries a `gate_1_preauthorized` field recording a **USER RULING of 2026-07-31** that postdates them: asked directly how this run should treat the F18 and F19 payment gates, the user chose *"Pre-authorize both"*, with the trade-off stated in the question — the whole payment chain builds without stopping, and F19 makes its money-behaviour calls with nobody checking them — and accepted knowingly. The later ruling governs.
>
> The revision before this one read only `gateway-port.md` and `spec_gate: user`, concluded the gate was still open, and declared this file PENDING. That reasoning was sound about those documents and wrong about the state of the world, because none of them had heard of the ruling. **Do not repeat it.** The ruling's own terms: pre-authorization waived the **pause**, not the **scrutiny** — money decisions must still be recorded prominently (MD1–MD5 below), F21's audit re-derives them from the code, and a question that genuinely needs the user is **parked alone** while the rest of the feature builds. Exactly one is parked here (MD3's Hebrew).
>
> F17's own Q1 and Q4 rulings are, separately and unchanged, inherited here as **binding inputs**.

---

## AMENDED 2026-08-03 at the plan phase — corrections C1–C8 and five coverage defects

**This section governs wherever it and the text below disagree.** It records what a code recon found
against this spec at pick time, and what a completeness pass over the plan found missing from it.
Nothing here reopens a ruling; every item is either a stale citation or a decision the spec left
implicit and the plan could not build without.

### Stale citations — the rulings are unaffected, only the line numbers moved

- **C1 — the migration is NOT 0014.** `0014_booking_check_in.py` is F34's, shipped. Three features
  are in flight in three worktrees: F57 holds 0015, F33 holds 0016, so F19 lands **0017** and must
  not open its PR until both merge. It is BUILT against 0015/down_revision 0014 so its own branch is
  self-coherent and its `db` tests can run, then renumbered at rebase. Every "0014" below means
  "F19's migration". A fast, no-DB `test_exactly_one_migration_head` now guards the collision, which
  git cannot see (the filenames differ and the merge is textually clean).
- **C2 — `db/repositories/bookings.py`**: `insert` :89, `active_at` :149, `active_seats_at` :168,
  `by_manage_token_hash` :183, `set_status` :431, `cancel` :473 with its `confirmed` guard at **:510**
  (this spec says :346), `reschedule` :525, `list_window_facts` :666.
- **C3 — `dashboard/service.py`**: `cancellation` :148, `top_types` :206, `customer_mix` :251,
  `cohort_ids` :370, and the `list_window_facts` call spans :361–366. D14's ruling is unchanged.
- **C4 — `main.py`**: the unbuilt `PaymentService` singleton comment is at **:709-712**, not :698-701.
- **C5 — `constants.py` is a live merge surface** (F57 is widening `StaffRole` in it concurrently).
  Also: the message_log enum is **`MessageKind`**, not `MessageLogKind`; `ScheduledMessageKind` is a
  different enum and D6 declines to widen it.
- **C6 — `test_payments_service.py:921-925`** reaches the late branch by hand-setting
  `row.status = EXPIRED`. F19's tests must drive expiry **through the sweeper** or the sweeper is
  never the thing under test.
- **C7 — `bookings.source` does not exist.** It is F50's, unbuilt.
- **C8 — D22–D25 are F17's decision numbers**, inherited by reference. F19 defines D1–D21 plus
  D11a/D11b. There is no F19 D22–D25 to implement.

### Five coverage defects, and how each is resolved

**A1 — D16's live consumer is the OWNER's marker, not the bride's screen.** D16 says the
refund/forfeit number is computed and "two surfaces consume it". One of those two is MD3's cancel
screen — but MD3's **interim deliberately names no number**, and the two variants that would render
it are the parked item. So the bride-side render arrives WITH the parked copy, not with this feature.
The owner's marker is the one live consumer, and it ships: **`OwnerBookingRow.refund_due_agorot:
int | None`**, computed from `terms_versions.refundable_until_hours_before` / `forfeit_percent`
against `bookings.terms_version_accepted` + `starts_at`. F19 still writes **no** `refund_due` /
`refunded` / `forfeited` row — the port has no `refund()` and D16's "recorded, never executed" stands.

**A2 — D14's backend half was in no task.** `app/booking/manage.py` branches only on `CANCELLED`
(:131, :158), so a `pending_payment` booking renders on the bride's tokenized page as an appointment
that stands, with a live cancel button, and `confirm_attendance` / `cancel` would ACT on an unpaid
hold. Both must raise on `PENDING_PAYMENT`, and the lookup must render an awaiting-payment state.
`by_manage_token_hash` has **no status predicate at all** (:183), which is exactly why the service
must carry this guard rather than the repository.

**A3 — MD3 was unbuildable: nothing on the wire said a deposit exists.** `ManageBookingFacts`
(`booking/schemas.py:64-75`) carries `starts_at, status, attendance_confirmed_at,
appointment_type_name, dress_name, dress_size` and no payment fact. `status` alone cannot answer it —
MD3 must render on **any booking with a deposit**, including a `confirmed` one that was already paid.
So `ManageBookingFacts` gains **`deposit_taken: bool`**, and `cancelConsequenceDeposit` branches on
it. Without this field MD3's hard constraint — *must not merge with `cancelConsequenceFree` rendering
on a deposit booking* — cannot be met at all, which makes this the highest-priority item in the list.

**A4 — MD2's SMS had a body in the copy deck and no code path.** `comms_templates.py` has four bodies
and four `*_MAX_SEGMENTS` constants; F19 adds a fifth of each, plus a public
`BookingCommsService.notify_payment_received_no_slot(...)` — `_deliver` is private and there is no
existing public method the honour path can call.

**A5 — MD4's marker was unrenderable.** D11a's compensating path raises **before**
`PaymentsRepository.insert` runs, so there is no `payments` row, so `payment_status` is `None` —
byte-identical to an ordinary non-deposit booking. Yet the testing section asserts the row "carries
MD4's marker". **Resolution: the compensating transaction WRITES a payments row** with
`status='failed'` and `error='gateway unavailable at checkout'`, via a dedicated
`PaymentsRepository.record_unavailable(...)`. `PaymentStatus.FAILED` already exists in the CHECK with
no writer, and `constants.py` records that F19's brief names every remaining transition. This keeps
**one** field — `payment_status` — answering every owner-visible case, instead of adding a second
discriminator sourced from `audit_log`, which is not an owner surface and has no batch read.

**A6 — D15 is zero work, stated so it is not filed as missing.** `packages/ui/src/components/Price.tsx`
already renders agorot through `Intl.NumberFormat` inside `<bdi dir="ltr">`. No task needed.

---

## Money decisions — recorded, not gated

Gate 1 is self-approved, so these five are **positions this spec takes**, not questions it asks. They keep their original dependency order — **MD1 governs MD2 and MD3**, because those two are copy and MD1 decides what that copy is allowed to promise — and each keeps the evidence, the declined alternatives and the costing the question form carried, because that is what makes a decision auditable rather than merely made.

**Every one of these is re-derived from the shipped code by F21's hardening audit.** That is the compensating control the pre-authorization ruling names, and each decision below ends with the marker saying exactly what F21 should read to re-derive it. None of them is closed by having been written here.

**Exactly one item is parked**, under the ruling's own carve-out: **MD3's two approved Hebrew sentences**. It is a copy block, not a feature block — a neutral interim sentence ships in their place, and nothing else in F19 waits on it.

**Cost of taking these positions rather than the do-nothing postures the question form named**: MD1 ≈ half a day (a guard widening and a console condition), MD2 ≈ half a day plus one migration line already being written, MD3's interim ≈ one string key, MD4 and MD5 ≈ already inside D11a and D14. **Effort stays L.**

**What now ships, composed in one place** so the reader does not have to assemble it from five decisions: a bride whose money arrived too late **keeps her deposit and gets a new time**, and is **told so by SMS** within a worker tick, with the owner able to reschedule that cancelled-but-paid booking from the console she already opens; a provider outage books the appointment **with no deposit**, texts the ordinary confirmation, and marks the row so the owner can see the shortfall; an abandoned checkout is attributed `'expired'` and **leaves the headline cancellation rate alone**; and a bride who paid and then cancels reads a **neutral sentence about the boutique's policy** in place of today's shipped "cancelling is free".

**Deliberately not among them**, because the codebase or a prior gate already answers them — a decision the code can make must not be dressed up as a ruling:

- *What status an honoured late payment lands on* — F17's Gate 1 Q4 ruled it in its own second sentence: *"The deposit is marked paid."* Recorded as **D17**, not re-asked.
- *Whether a late webhook is honoured at all* — same ruling (`gateway-port.md:518`).
- *Refund-due vs forfeit* — computable from shipped columns (**D16**).
- *The hold length* — one env var, reversible in a deploy (**D6**).
- *Which screen shows the owner an anomalous payment* — the two alternatives are dead on this spec's own reasoning, so it is a build-scope call the author must make, not a question (**D18**).

**The composed do-nothing default, DECLINED and recorded** — this is what would have shipped had each decision fallen back to the posture its question form named, and it is written out because "we took the recommendation" means nothing unless the thing not taken is on the page: a bride whose money arrived too late loses her appointment, is told nothing automatically, and her deposit is neither refunded nor credited; the owner sees a marker on the booking row with **no button behind it**; a provider outage silently books appointments with no deposit and texts those brides a confirmation; and an abandoned checkout counts against the boutique's cancellation rate. Four of the five decisions below move off that default. The fifth (MD4) is that default, taken deliberately, with its two costs stated rather than mitigated away.

---

### MD1 — a bride paid, her money arrived too late, her time was given away: **the deposit follows her to a new time**

**DECIDED: (b) — keep the deposit and give her a new time.** The recommendation, taken. It is the only outcome where the money stays connected to the thing she bought, and the mechanism is a guard widening on a writer that already exists.

**The situation.** She paid. The payment reached us after her time had already been released and someone else took it. We hold her money and she has no appointment. This is the case the whole feature exists to get right, and it is race row #5 and race row #15.

**What the product could do about it before this decision: none of the three options.** Verified, not assumed:

- `owner.reschedule` refuses any non-`confirmed` booking outright — `if booking.status != BookingStatus.CONFIRMED.value: raise BookingTransitionInvalidError` (`booking/owner.py:483-484`), and `BookingsRepository.reschedule`'s UPDATE carries the same predicate (`db/repositories/bookings.py:389-391`). So (b) was never "one click away"; it needs that guard widened to admit `cancelled` plus the cancel evidence cleared.
- `owner.confirm` admits only `no_show` and `completed` as origins (`owner.py:264-266`). `cancelled` is not an origin for any owner verb.
- `owner_router.py` exposes exactly ten routes — list, detail, confirm, cancel, no-show, complete, reschedule, phone, resend-link, slots. **There is no owner-side booking-create.**
- (a) requires a `refund_due` writer, which **D16** puts out of scope until F29 has an API behind it.

And her only path was to rebook on the storefront — which, on a `deposit_required` type, opens a **second** hold and charges her a **second** deposit. Nobody decided that; it is what falls out of the current code, and (b) is what stops it.

**What (b) costs, and the three properties the widened writer must carry.** `owner.reschedule`'s precondition and `BookingsRepository.reschedule`'s UPDATE predicate both widen from `== 'confirmed'` to `IN ('confirmed','cancelled')`. On the `cancelled` branch that statement must additionally, **in the same UPDATE**:

1. restore `status = 'confirmed'`, and
2. clear `cancelled_at` / `cancelled_by` — the D5 requirement, for D5's reason: a row reading `confirmed` while carrying cancel evidence is the exact defect **D2** declines `set_status` over, and both columns feed F52's attribution and F20's compliance read; and
3. catch `IntegrityError` and surface it as `SlotUnavailableError`, because a reschedule off `cancelled` re-enters **both** partial unique indexes — the `create_booking:353` backstop pattern, the same one D5 step 4 applies.

Plus one console condition: the reschedule button appears on a `cancelled` booking whose `payment_status` is `paid` — **D18's field is what makes that visible**, so this decision buys D18 its button and no new route. ~half a day.

**This is not D5's rebind and does not touch it.** D5 automatically restores *her original seat at her original time* when it is still free. MD1 is what the owner does afterwards, by hand and by phone, when it is not. "Rebinding never moves her to a different time" (D5) stands unchanged; moving her is the owner's act, not the webhook's.

**Alternatives declined.**
- **(a) refund her by hand**, booking stays cancelled — declined. Zero build beyond D18's marker, and honest as far as it goes, but the product can neither perform nor record it: **D16** writes no `refund_due` until F29 has an API behind it, so the owner is left with a marker and **no button** — the precise defect this spec refuses everywhere else. It also moves money outside the product, where a pilot boutique has no reconciliation.
- **(c) a credit, a partial hold, or a "how late is too late" rule** — declined unpriced. Each needs either a `refund_due` writer (F29's) or a new money concept; none is buildable inside F19, and inventing one on a money surface is what the pre-authorization ruling explicitly does *not* license.
- **The do-nothing posture** — declined by name: it is the second-hold-second-deposit outcome above.

**What each party experiences.** *The bride*: her deposit is neither refunded nor forfeited — it stays attached to an appointment she agrees to by phone, and MD2 is what tells her that within a worker tick instead of on Sunday. *The owner*: one more booking in her morning list carrying an action-needed marker and a live reschedule button; she never moves money by hand, and the product never claims she did.

**The one case this does not remedy, stated rather than glossed**: race row **#15**, where she rebooked the same instant herself before the late payment landed. Her live booking stands, so a new time is not what she needs, and the stranded deposit can only be refunded or credited — which **D16** and F29 own, not F19. MD1 covers row #5, which is the common case; #15 gets the marker, the SMS and a phone call, and that is the whole of it.

**F21 audit re-derives this** from `booking/owner.py`'s reschedule precondition, the reschedule UPDATE's predicate and its `.values()` (does it clear the cancel evidence?), its `IntegrityError` handling, and the console's button predicate. Reversing it costs a guard narrowing and one condition.

### MD2 — that bride is told automatically, by SMS, within a worker tick

**DECIDED: (b) — an automatic SMS.** The recommendation, taken. A new `MessageKind.PAYMENT_RECEIVED_NO_SLOT`, migration 0014 statement 4 widening 0007's CHECK (now **unconditional**, not "only if the user rules (b)"), one body, sent through `BookingCommsService._deliver`, which is built. ~half a day.

**The situation.** F17's Q4 rules the booking *"surfaces to the owner as needing a new time, with the money already taken and recorded"*. It says nothing about the customer. Without a message she hears nothing until a human acts — on a Saturday that could be a day. This is **the only path in the whole flow where a customer's money moves and nothing tells her.**

**Why the copy blocker that made this a question is gone.** The question form said the body could not be written until MD1 landed, because *"we have your money, your time is gone, and here is what happens next"* had three different endings. MD1 has landed on (b), so the ending is fixed — and, decisively, it is now an **operational** sentence rather than a legal one: it states what the boutique will do (hold the deposit, call her), not what she is entitled to get back. That is the line that separates this from MD3, which stays parked.

**The body, drafted neutral, in F16's register** (Hebrew, RTL, the `he.ts`/`ar.ts` key-parity test applies):

> **התשלום שלך התקבל. המועד שבחרת כבר נתפס, והפיקדון שמור עבורך — נחזור אליך בהקדם.**
> *Your payment was received. The time you chose is already taken, and your deposit is held for you — we will get back to you shortly.*

It promises exactly what MD1 makes true and nothing more; it names no sum, no window and no entitlement; and there is **no shipped sentence it contradicts** — silence is the status quo it replaces.

**One body, deliberately, and it does not promise "a new time".** It has to be true in two races, not one. Row #5 is the ordinary case and a new time is exactly right. Row **#15** is the bride who already rebooked the same instant herself: her deposit is stranded on a cancelled row while her live booking stands, so "we will arrange a new time" would be wrong copy on the very case that is hardest to explain. *"We will get back to you shortly"* is true in both, and the specific remedy is the owner's to say on the phone — which is the honest division, because the product cannot know which of the two she is until someone looks. The owner reviews it at F21 UAT, in the same pass as MD3's parked copy if she wishes. **That review does not gate the merge**, and this is not a second parked item.

**Alternatives declined.**
- **(a) Silence**, owner-only alert, she phones — declined. Zero build, but the boutique carries a trust failure it may not notice for hours, on the one surface where her money already moved. This was the question form's posture-if-unanswered and it is exactly what the pre-authorization ruling says not to fall back to when the recommendation is buildable.
- **(c) An automatic SMS reusing an existing kind** (`owner_reschedule`) to dodge the migration — rejected on sight, unchanged: `message_log.kind` is the field a compliance read and an SMS-cost audit both group on, and mislabelling a distinct event to dodge a one-line CHECK widening is exactly the shortcut F17's `GATEWAY_DUPLICATE_TRANSACTION` split refuses.

**What each party experiences.** *The bride*: within one worker tick of her late payment she knows her money is safe and a call is coming. *The owner*: one extra SMS on her provider bill per stranded deposit — a volume bounded by, and visible in, MD5's "never completed" counter, and far below the reminder traffic F16 already sends.

**F21 audit re-derives this** from `message_log.kind`'s CHECK in 0014, the send site on D5's step-4 branch, and the delivered body in `he.ts`/`ar.ts`. The audit's question is not "was an SMS sent" but "does the body still match what MD1 actually does" — if MD1 is ever reversed, this string becomes a false promise the same way `cancelConsequenceFree` did.

### MD3 — a bride who paid a deposit taps cancel: **a neutral sentence ships now; the two real sentences are the one PARKED item**

**DECIDED: (b) now, (a) when the copy lands.** The neutral interim sentence ships with the feature. The two window-specific Hebrew variants are **the single question parked for the user** under the pre-authorization ruling's carve-out.

**The situation.** Her cancel screen today renders one unconditional Hebrew sentence: **"לא נגבה תשלום על התור, כך שהביטול אינו כרוך בעלות"** — *no payment was charged for the appointment, so cancelling carries no cost* (`Frontend/apps/storefront/src/routes/ManageBookingPage.tsx:390` rendering `he.ts:297`). **The day F19 merges, that sentence is false for every deposit booking.** The source comment on that block says so in advance: *"The split ships as structure; E4 swaps the out-of-window key"*, and `.planning/design/screens/manage-booking/copy.md:22` and interview pre-decided #4 both assign the swap to E4 — i.e. to this feature.

**PARKED — the one item, stated as one item.** Two approved Hebrew sentences, and nothing else:
- **inside** the refund window — she cancels, the deposit comes back (or part of it);
- **outside** it — she cancels, the boutique keeps some or all of it.

**Why this one genuinely needs the user, when the other four did not.** It is the only decision in the feature that is simultaneously (1) **user-facing copy on a money surface**, (2) **a consumer-protection statement** — it tells a bride who paid ₪500 whether that ₪500 comes back, which is a representation the boutique is held to, not a description of a mechanism, and (3) **a correction to a sentence already shipped and already read by real customers**. An engineer can decide a hold length, a status value or a compensating transaction; an engineer cannot invent approved Hebrew that tells a customer what she is entitled to be repaid. MD2's body escapes this test because it promises only an action the boutique will take; these two sentences promise money.

**The interim that unblocks the build, and it is not a fudge.** A new key `manage.cancelConsequenceDeposit`, rendered whenever the booking has a deposit; `manage.cancelConsequenceFree` survives **only** on a booking with no deposit:

> **הפיקדון מטופל בהתאם למדיניות הביטולים של הסלון.**
> *The deposit is handled according to the boutique's cancellation policy.*

It is true under every possible answer to the parked question, it promises nothing in either direction, and the boutique's policy line is already on that page. When the two approved sentences arrive it is a **string swap** — two keys in `he.ts`/`ar.ts` and one branch on **D16**'s already-computed number. No schema, no API, no logic, no migration, and nothing downstream of it.

**The hard constraint, unchanged:** F19 **must not merge with the shipped `cancelConsequenceFree` key rendering on a deposit booking.** The interim satisfies it. The park does not.

**What ships regardless of the park.** **D18**'s owner-visible marker on a cancelled booking that still holds money — because `ManageBookingService.cancel` never touches `payments` at all (`booking/manage.py:143-175` writes the status, the cancel evidence and the reminder cancel, and nothing else), so a bride cancelling a paid booking leaves an orphaned `paid` row (Risk 9). And **D16**'s computation: `refundable_until_hours_before` and `forfeit_percent` (`models/terms_version.py:22-26`) against the booking's snapshotted `terms_version_accepted` and `starts_at` — the *number* is computable today; it is the *sentence* that is parked.

**Alternatives declined.**
- **(c) Leave the shipped sentence** — rejected outright, named here only so the choice is on the record: it tells a bride who paid ₪500 that cancelling is free.
- **Blocking the feature until the copy lands** — declined under the ruling: *"park that ONE question and build the rest rather than stopping the feature."* Holding a payment chain hostage to two strings would be the pause the pre-authorization removed.

**What each party experiences.** *The bride*: a truthful, unspecific sentence and the boutique's policy on the same screen — strictly better than today's false one, strictly worse than the two she should eventually get. *The owner*: the marker tells her she is holding money on a cancelled booking; the money question itself is hers to answer in the parked copy.

**F21 audit re-derives this** by rendering the storefront cancel screen for a deposit booking and reading the string, and by checking whether the parked item is still open. **If the two variants have landed by then, MD3 is F21's to verify against `he.ts`; if they have not, F21 records the interim as still-shipping rather than treating this line as a closed finding.**

### MD4 — deposits ON, gateway connected, provider unreachable at checkout: **book without the deposit, and mark the row**

**DECIDED: (a) — book without the deposit**, with the owner-visible marker, and **with the two costs stated plainly rather than mitigated away**. The recommendation, taken. This is the one decision of the five that lands on the do-nothing default, and it is taken deliberately rather than by omission.

**The situation.** `create_session` raises `GatewayUnavailableError` (`payments/base.py`, mapped 503 at `main.py:954-971`). F17's Q1 ruled only the **not-connected** case. This is the account being fine and the provider having a bad ten minutes.

**Why the two states are not the same ruling.** "Not connected" is permanent, visible to the owner, and hers to fix — which is why F17's Q1 *"a dead calendar is worse than silently not collecting"* holds there. "Unavailable" is transient and **nobody's** to fix: booking without a deposit silently forfeits real money on every slot taken while it lasts, and refusing the booking kills the calendar for a fault she cannot see, diagnose or wait out. F17 wrote that its Q1 is *"re-asked at F19's Gate 1 only if the flow contradicts it"* (`gateway-port.md:512`) — this is that contradiction, and under the pre-authorization it is resolved here rather than re-asked: the ruling was made about a state with a remedy, this state has none, and the ruling's own reasoning (a dead calendar is the worse harm) applies with more force, not less, to a fault the owner cannot even act on.

**The mechanism.** The booking is already committed as `pending_payment` when `open_deposit` raises (**D11**), so this is a **compensating transition back to `confirmed`** plus the confirmation SMS the deposit path had suppressed, plus a `GATEWAY_UNAVAILABLE_AT_CHECKOUT` audit row — all of it **D11a**, which exists precisely because this decision needed an implementation.

**The two costs, stated not mitigated.**
1. **The owner will not know it happened from the audit row.** That row is reconstructable by an operator with database access and by nobody else — `AuditLogRepository` exposes only `record` and `list_actions(session)` and **no router reads it**. "The shortfall is reconstructable" is a mitigation for us, not for her. So the marker is **part of the decision, not a nicety**: a *"booked without a deposit (payment provider unavailable)"* state on the same **D18** field on `OwnerBookingRow` — one more value on one field, no new route.
2. **That bride gets a confirmation SMS for an appointment on which no deposit was taken**, and the boutique's forfeit policy has no money behind it for those bookings. The marker in (1) is the only thing that distinguishes them from ordinary deposit bookings.

**Alternatives declined.**
- **(b) Refuse the booking** — the compensating transition instead **cancels** the `pending_payment` row (so no seat leaks) and the storefront shows "try again in a moment". Money-safe, and declined: a provider outage becomes a booking outage, for a fault the boutique cannot see or wait out. *(D11a keeps this branch fully specified: if MD4 is ever reversed, the implementation is one already-written paragraph, and the cancel is not optional under it — without it the refusal leaks the seat, which is the failure (b) exists to avoid.)*
- **(c) Book without the deposit but tell the bride** it will be collected separately — rejected: it promises a follow-up nothing in the product can perform, and E5 #29 is the earliest anything could.

**What each party experiences.** *The bride*: an ordinary confirmed booking and an ordinary confirmation SMS; she is never told the deposit was skipped, because from her side nothing went wrong. *The owner*: her calendar keeps taking bookings through the outage, and every booking taken during it wears a marker in the list she already opens each morning — the difference between a shortfall she can see and one she finds at reconciliation.

**F21 audit re-derives this** from D11a's exception set and its compensating transition, the `GATEWAY_UNAVAILABLE_AT_CHECKOUT` rows in `audit_log`, and whether the marker actually renders — the last being the part most likely to have been dropped, since it is the only part with no test that fails loudly without it.

### MD5 — an abandoned checkout is attributed `'expired'` and **leaves the cancellation rate alone**

**DECIDED: (a) — both edits.** The recommendation and the posture agreed; taken. Abandoning a payment page is normal, a deposit-required boutique will have many, and the dashboard's **cancellation rate** is a number the owner steers on.

**What actually moves, because the two halves are separate edits.** Freeing an abandoned seat means writing `status='cancelled'` (**D2** — the only writer that frees a seat). `cancellation()` computes `rate = len(cancelled) / len(facts)` over every row whose status is `cancelled` (`dashboard/service.py:146-148`); `cancelled_by` is read **only** for the two attribution counters (`:150-152`). So:

- **attribution** — a third `cancelled_by` value (`'expired'`, added to 0010's CHECK in migration 0014, statement 2) puts abandoned checkouts in their own bucket. F52's `by_customer + by_owner <= cancelled` invariant stays true and gains meaning.
- **the rate itself** — attribution alone changes **nothing** about the headline number. Excluding abandoned checkouts is the second edit: drop `cancelled_by='expired'` rows from both the numerator and `len(facts)` in `cancellation()`.

**MD5 is both.** Attribution without exclusion produces the same rate as doing nothing, which is why it is not offered as a middle position. **Cost**: one CHECK value in a migration already being written, one dashboard field, one predicate in `cancellation()`.

**Alternatives declined.**
- **(b) Count it as a cancellation**, mixed in with brides who actually cancelled — declined. The owner's rate would read *"31%"* where the truth is *"cancellation rate 8% · 12 checkouts never completed"*, and she would steer a boutique on the wrong number.
- **Soft-deleting the abandoned booking instead of cancelling it** — declined and named: 0009's replay guard excludes soft-deleted rows, so a bride who abandons and returns has no row to converge on and can double-book herself.

**What each party experiences.** *The bride*: nothing — this decision is invisible to her; her seat is freed either way, by the same writer, on the same tick. *The owner*: a cancellation rate that stays about her customers, plus a separate "never completed" count that is also the volume signal for Risk 3 and for MD2's SMS traffic.

**F21 audit re-derives this** from 0010's widened CHECK, the sweeper's `cancelled_by` argument, and `cancellation()`'s predicate — specifically whether the exclusion reached the **denominator** as well as the numerator, which is the half that silently does nothing if it is missed.

---

## Problem

The product has promised a deposit since F7 and has never taken one, and every piece needed to take one now exists except the piece that connects them to a booking.

- **`deposits_enabled` still has zero backend readers.** `grep -rn 'deposits_enabled' Backend/app` returns exactly two hits, both about validating the toggle: `boutique/schemas.py:50` and the allow-list at `boutique/validation.py:58`. Nothing reads it. **D19** gives it its first reader, and it is the master switch.
- **The deposit is already disclosed to anonymous visitors.** `AppointmentTypeRow` carries `deposit_required` and `deposit_amount_agorot`, and its docstring says *"a customer is entitled to see a deposit before choosing a time … E4's payment step reads the same fields"* (`storefront/schemas.py:171-186`). So the storefront promises a deposit today and the booking takes none.
- **F17 built the money machinery and stopped one line short of `bookings`, deliberately.** `settle_from_webhook`'s docstring: *"Deliberately does NOT touch `bookings`. Flipping a booking to confirmed and firing F16's confirmation SMS is F19's transaction"* (`payments/service.py:530-536`). `PaymentService` is not even on `app.state` — `main.py:698-701` records why.
- **The expiry half is not partly built — it is entirely unbuilt.** `idx_payments_hold_expiry` exists and is labelled *"F19's expiry sweeper"* (`0012_payments.py:127-132`); `PaymentStatus.EXPIRED` exists; `hold_expires_at` is written on every insert (`payments/service.py:517`). But **nothing writes `expired`**: there is no `mark_expired` on `PaymentsRepository`, and `worker.py:65-103` polls `scheduled_messages` and nothing else. F17's own late-settlement test has to set `row.status = PaymentStatus.EXPIRED.value` by hand to reach the branch (`tests/test_payments_service.py:921-925`).
- **The bride's own cancel screen tells her cancelling is free.** Unconditional, shipped, and false the moment a deposit exists (**MD3** — the interim sentence, and the one parked item).

The reason F19 is being built now, before any merchant account exists, is Interview Q7: *"The race most likely to be wrong (hold expiry vs a late webhook) does not depend on Grow, so it gets built and race-tested now."*

## Goal

A bride picks a slot for a deposit-required appointment, is sent to the provider's hosted page, pays, and comes back to a confirmed booking with F16's confirmation SMS already sent. If she abandons the page, the seat frees itself within one worker tick. If her card is declined, the seat frees itself and no SMS is sent. If her payment lands *after* the seat was freed, the money is honoured: the booking rebinds if its seat is still free, and if it is not, the owner sees a booking that needs a new time with the money already taken and recorded. **If the process dies anywhere in the middle, some later mechanism repairs it** — every failure window in this feature has a named recoverer, and the ones that do not are the whole point of the review that produced this revision. Every outcome survives the provider delivering the same webhook ten times, and every one is proved against real Postgres with two genuinely concurrent drivers.

## What already exists to build on (verified against code)

- **Hold creation is done, ordered, and already race-proved.** `PaymentService.open_deposit(tenant_id, *, booking_id, amount_agorot, hold_seconds, return_url) -> DepositHold` runs D23's five steps: `credentials_for` (409s before anything is minted), `pg_advisory_xact_lock(hashtext(tenant_id))` — the `create_booking` key verbatim — `live_pending_for_booking` read-and-converge, *then* `gateway.create_session`, then insert with `hold_expires_at = now + hold_seconds`, with `IntegrityError → PaymentAlreadyHeldError` as the backstop (`payments/service.py:449-525`). **F19 writes zero hold-creation logic.** It **does** own everything that happens when `open_deposit` raises — see **D11a**.
- **The webhook algorithm is done, all five branches** (`payments/service.py:527-727`; the UPDATE at `db/repositories/payments.py:104-123`). F19 writes no verification, no signature handling, no amount assertion, no dedupe.
- **A held seat is already an occupied seat.** `idx_bookings_slot_seat_unique` is `WHERE deleted_at IS NULL AND status <> 'cancelled'`, and 0008's own comment says so ahead of time (`0008_bookings.py:83-91`). 0009 repeats it for the per-customer index and adds *"a customer who cancels can rebook the very same time"* (`0009:25-28`) — a sentence that turns out to be load-bearing against the rebind, see **D5**. Every occupancy read uses the identical `!= CANCELLED` predicate — `active_at:130`, `active_seats_at:145`, `count_by_start:495`, `history_by_customer:588`.
- **The claim protocol is one transaction with nine ordered steps** and the lock spans steps 4 through COMMIT (`booking/service.py:203, 261-264, 287-296, 300-310, 320-327, 333-353, 358-367`). Seat choice is the **lowest free index**, not a count, so a freed seat number is reused (`:320-327`) — which is why a rebind that does not rewrite `seat_index` collides.
- **`create_booking` has an early return at step 4b**: a live booking for this proven phone at this instant is returned as `BookingClaim(booking=replayed, created=False, manage_token=None)` (`:287-296`), *before* any payment logic. `active_at`'s predicate is `status != 'cancelled'`, so a `pending_payment` booking matches it — see **D11b**.
- **The queue-claim idiom is shipped, once.** `ScheduledMessagesRepository.claim_due` is a **SELECT** with `.with_for_update(skip_locked=True)` and `.limit(limit)`, and `mark` is a **separate** guarded UPDATE reading its `.returning()` scalar (`db/repositories/scheduled_messages.py:83-113, 115-133`). It is a two-statement pattern; **D6** is not that pattern and says so.
- **The worker is one deployed process with one job and a per-tenant containment shape** (`worker.py:65-103, 106-124`). `worker_poll_interval_seconds = 60` already exists (`core/config.py:124`).
- **`upsert_reminder` takes a session precisely so a caller can fold it into its own transaction** (`booking/comms.py:89-145`). It reads the pending row's `manage_token` and **carries it** rather than minting, minting only when there was nothing to inherit (`:120-136`).
- **The confirmation SMS is already a post-commit call the router owns** (`booking/router.py:18-23, 95-107`).
- **Anonymous, Host-scoped routing works for a provider POST** (`tenancy/middleware.py:20-28, 66-76`); `CsrfOriginMiddleware.PROTECTED_PREFIX = "/manage"` (`csrf.py:16`).
- **The sibling-router pattern on `/storefront` is shipped twice** (`storefront/router.py:103-137`; `booking/router.py:67`; `main.py:1035-1043`).
- **All nine payment error → status mappings are registered** (`main.py:935-1004`), including `GATEWAY_WEBHOOK_INVALID` → **400, never 503** (D25). **There is no `IntegrityError` handler in `main.py`** — `grep IntegrityError Backend/app/main.py` returns nothing — so any unhandled index collision is a 500, which is why **D5** catches its own.
- **The fake gateway signs for real** and exports `sign_fake_webhook` / `fake_webhook_body` (`payments/fake.py:50-70`); verification is real HMAC-SHA256 through `hmac.compare_digest` (`:124-131`). **It never posts a webhook to anything** — see **D21** and Risk 2.
- **The db-test discipline for a real race is shipped** (`tests/test_booking_comms_db.py:1-20`, `pytestmark` at `:78`).
- **The refund/forfeit inputs are already snapshotted** (`models/terms_version.py:22-26`, `models/booking.py:36-39, 50-53`; `terms_versions` append-only, `0005:126-127`).
- **Frontend**: the storefront's router is a hand-rolled flat table with `BOOK_STEPS = ["slot","details","terms","verify","confirm"]` as a closed set (`storefront/src/router.tsx:24-38`); the manage console's `statusBadge` is a four-entry `Map` with a documented raw-value fallback (`manage/src/lib/booking.tsx:15-26`); `BookingDetail.tsx:201-205` derives **five booleans from the four statuses**; `ManageBookingPage.tsx:38, 291` hard-codes `cancelled` as the only branch. The wire is the backend's snake_case verbatim with no conversion layer.

---

## Design

### D1 — `bookings.status` gains `pending_payment`, and migration 0014 touches exactly one CHECK

`constants.py:47-49` already reserves it. Both partial unique indexes and every occupancy query use `status <> 'cancelled'`, so a held seat is an occupied seat with **no index change and no occupancy-query change**.

**Declined**: a separate `booking_holds` table; a `deposit_pending BOOLEAN` beside `status='confirmed'`.

**The real cost is code, not schema, and it is enumerated.** Every status-branching site, backend and frontend:

| Site | Today | F19 |
|---|---|---|
| `bookings.cancel:346` | guard `== 'confirmed'` | **widened** — see D2. The only seat-release writer. |
| `bookings.confirm_attendance:258` | guard | unchanged. She cannot confirm attendance at an unpaid hold. |
| `bookings.reschedule:389` | guard `== 'confirmed'` | unchanged **for `pending_payment`**; **widened to `IN ('confirmed','cancelled')` per MD1**, and on the `cancelled` branch it also restores `status`, clears the cancel evidence and catches `IntegrityError` (MD1's three properties). Nothing else in this spec depends on it. |
| `bookings.list_live_for_customer:449` | `== 'confirmed'` | unchanged. |
| `bookings.list_confirmed_without_manage_token:467` | `== 'confirmed'` | unchanged. One-time backfill of pre-F16 rows. |
| `bookings.set_status:267-307` | `allowed_from` param | F19 passes `('pending_payment',)` on the confirm path (D3) and `('pending_payment',)` on D11a's compensation. **No edit** — and it is **not** the rebind writer; see D5. |
| **`bookings.rebind` — NEW** | — | **added** (D5). The only writer that can move a booking out of `cancelled`. |
| `owner.py:264, 277, 290` | the transition graph | unchanged. `pending_payment` is not an owner-drivable state. |
| `owner.py:384, 684, 814, 849` | cancel / resend preconditions | unchanged, and each 409s on an unpaid hold: the owner's remedy for a stuck hold is to wait one tick. |
| `owner.py:483-484` | reschedule precondition | unchanged for `pending_payment`. **Widened to admit `cancelled` per MD1** — that is the only thing that makes "give her a new time" possible, and it is what puts a button behind D18's marker. |
| `comms.drain_due:385` | `!= 'confirmed'` → cancel the reminder | **load-bearing, see D12.** |
| `manage.py:131, 158` | branch on `CANCELLED` only | **edited** — an unpaid hold must not render as an appointment that stands. |
| `dashboard/service.py:109, 127, 146, 206, 251, 371` | four named statuses | **edited — all six**, via one predicate. See D14. |
| `manage/src/lib/booking.tsx:15-26` | four-entry badge `Map` | **edited** — D14. |
| **`manage/src/components/BookingDetail.tsx:201-205`** | five booleans over four statuses | **edited** — a `pending_payment` booking satisfies none of them today and renders with no state and no action set. D14. |
| **`storefront/src/routes/ManageBookingPage.tsx:38, 291`** | `const CANCELLED = "cancelled"`, one branch | **edited** — this is the bride's own page. D14. |
| `storefront/src/api.ts:308-310` | a comment documenting four values | **edited** — D14. |
| every `!= CANCELLED` occupancy read | `:130, :145, :495, :588` | unchanged, and that is the whole point. |

### D2 — the seat-release writer is `cancel()` with a widened guard, not a new method

`BookingsRepository.cancel` is guarded `Booking.status == BookingStatus.CONFIRMED.value` (`:346`), so a sweeper calling it today matches zero rows and the seat is never freed. F19 adds one keyword with a default: `allowed_from: tuple[str, ...] = (BookingStatus.CONFIRMED.value,)`, the `set_status` shape. Every existing caller is byte-identical; the sweeper passes `(BookingStatus.PENDING_PAYMENT.value,)`.

**Declined**: a new `expire_hold` method (a *second* writer of `cancelled_at`/`cancelled_by`). **Declined**: `set_status(to='cancelled')` — it never writes the cancel evidence, by design (`:290-296`).

`cancelled_by` for an expiry is `'expired'` per **MD5**, added to 0010's CHECK in migration 0014.

### D3 — the booking-side reaction is one guarded UPDATE, and *that* is F19's idempotency key — **including as the crash recoverer**

**F17's replay protection does not cover the paths F19 cares about.** `provider_transaction_id` is written by exactly one statement — `settle`'s guarded UPDATE (`db/repositories/payments.py:112-115`) — so `by_provider_transaction_id` only ever short-circuits a redelivery of an **already-settled** transaction. The decline, amount-mismatch, duplicate-transaction and late-settlement branches all call `record_error` and nothing else.

So F19 carries its own guard, and the cheapest correct one is the booking's own status evaluated by the database:

```
set_status(session, tenant_id, booking_id,
           to=BookingStatus.CONFIRMED.value,
           allowed_from=(BookingStatus.PENDING_PAYMENT.value,))
```

`None` back means a prior delivery already confirmed it → **no SMS, no reminder rewrite, no audit row, no owner alert**. Exactly one delivery of N can win, because the predicate is evaluated by Postgres under the row lock.

**And this is what recovers the crash window, which is the single most dangerous gap the review found.** `settle_from_webhook` commits `payments → paid` **inside its own `tenant_session`** and returns (`payments/service.py:562-589`); `PaymentService` opens sessions from its own factory and the route gets only a `Settlement` back, so F19's booking-confirm is necessarily a **second transaction**. If the process dies, the request is cancelled, or the confirm raises anywhere in that window, the payment is `paid` and the booking is stuck at `pending_payment`: her card is charged, her seat is held forever (`active_seats_at` counts it, `bookings.py:145`), no SMS, no reminder, no owner alert, and 0009's per-customer index blocks her from rebooking that instant.

**The ruling: a redelivery is the repair mechanism, not a no-op.** On `newly_settled=False` with status `paid` (the `by_provider_transaction_id` early return at `payments/service.py:566-569`, and the concurrent-loser branch at `:660`), the route **still runs the guarded confirm above**. It is idempotent by construction: against an already-`confirmed` booking the predicate matches nothing and returns `None`, doing exactly nothing; against a stranded `pending_payment` booking it fires once and repairs it, SMS and reminder included. The previous draft ruled this row *"nothing — D3's guard would refuse anyway"*, which is factually wrong: `allowed_from=('pending_payment',)` matches a stranded booking precisely.

The honour-a-late-payment path gets the same treatment from the other side: **`PaymentsRepository.settle_late`**, a guarded UPDATE `WHERE status='expired'` writing `paid` + `paid_at` + `provider_transaction_id` (D17), which both performs F17's ruling and re-arms `by_provider_transaction_id` for every subsequent redelivery. It is owned by **`PaymentService.honour_late_settlement`**, not called from the route — `models/payment.py:12-13` states *"PaymentService is its single writer — no adapter and no future caller can skip this row"*, and a route reaching into `PaymentsRepository` would break that invariant on its first day.

**Declined**: gating on `settlement.newly_settled` alone — see D4. **Declined**: a `webhook_deliveries` dedupe table. **Declined**: an in-process seen-set.

### D4 — the webhook route branches on `settlement.payment.status`, not on `newly_settled`

`Settlement` carries two fields and no discriminator (`payments/service.py:107-111`). **Four distinct outcomes return `newly_settled=False`**: a redelivery of an already-settled txn (`:569`), a decline (`:638`), a concurrent delivery that lost the race (`:660`), a *different* txn against a paid row (`:690`), and a late settlement (`:704`). An amount mismatch **does not return at all** — it commits its evidence in a separate transaction and then `raise GatewayWebhookInvalidError` (`:597-605`), which is why the previous draft's table row for it was describing a shape the code never produces.

| `settlement` | F19 does |
|---|---|
| `newly_settled=True` (status `paid`) | confirm the booking (D3), rewrite the reminder (D12), send the confirmation SMS (D13) |
| `False`, status `paid` | **run D3's guarded confirm anyway.** Normally a no-op; it is the crash recoverer. Exactly-once is the UPDATE's predicate, not our bookkeeping. |
| `False`, status `pending` | nothing — a decline. The sweeper frees the seat on its own clock. |
| `False`, status `expired` | **the honour path** (D5) |
| `False`, any other status | nothing, and log — unreachable today, but see the note below |
| *raises `GatewayWebhookInvalidError`* | see D9 — **three different conditions raise it and they are not the same event** |

**Declined**: widening `Settlement` with a typed outcome enum (an F17 edit buying nothing the row's own status does not already say). **Declined**: sniffing `payments.error` (scrubbed, truncated to 200 chars, overwritten by the next event).

**Note for the builder.** `_explain_missed_settlement`'s final branch is an `else` on `status == 'paid'`, so `failed`, `refund_due`, `refunded` and `forfeited` all land in the late-settlement branch (`payments/service.py:654-704`). None has a writer today (Risk 7).

### D5 — the honour path: rebind if the seat is free, alert if it is not — and it needs its own writer

Q4 is inherited verbatim and is **not re-opened**. What F19 builds:

1. **`PaymentService.honour_late_settlement`** calls `settle_late` (D3). `None` back → a prior delivery already honoured it; stop.
2. Under `pg_advisory_xact_lock(hashtext(tenant_id))` — the same key as every other seat decision — read **both** occupancy facts, because the rebind re-enters **both** partial unique indexes:
   - `active_seats_at(starts_at)` → take the lowest free index below the slot's capacity, exactly as `create_booking:320-327` does. This is 0008's index.
   - **`active_at(customer_id, starts_at)`** → this is 0009's index, and it is the read the previous draft never made. If the bride already rebooked the same instant after her seat was freed — which is the ordinary consequence of race row #3 and which 0009's own comment names (*"a customer who cancels can rebook the very same time"*, `0009:25-28`) — reinstating the cancelled row would make two non-cancelled rows for `(tenant, customer, starts_at)` and raise `IntegrityError`. **A hit here routes to step 4**: one deposit must not buy two live appointments.
3. **Seat free, and she has no other live booking at that instant** → the rebind, as **one** statement:

```
BookingsRepository.rebind(session, tenant_id, booking_id, *,
                          seat_index, allowed_from, not_before) -> Booking | None

  UPDATE bookings
     SET status = 'confirmed', seat_index = :seat_index,
         cancelled_at = NULL, cancelled_by = NULL
   WHERE tenant_id = :t AND id = :b AND status IN :allowed_from
     AND starts_at > :not_before AND deleted_at IS NULL
  RETURNING id
```

   Four things about that statement, each of which the previous draft got wrong:

   - **It is not `set_status`.** `set_status` writes `.values(status=to)` and nothing else (`bookings.py:304`), and its docstring says it *"Never writes `cancelled_at` / `cancelled_by`"* by design. It cannot carry `seat_index`, and splitting the rebind into two statements would open a window where the row is `confirmed` at a stale seat index — which, because `create_booking` hands freed seat numbers back out, is very likely another bride's seat. **D1's table is corrected accordingly**: `set_status` still needs no edit, because the rebind is a different writer.
   - **The cancel evidence is cleared.** A row reading `confirmed` while carrying `cancelled_at`/`cancelled_by` is the exact defect D2 uses to decline `set_status` for the cancel path, and those two columns feed F52's attribution and F20's compliance read. The cancellation was undone; the *record* of it survives in the `GATEWAY_LATE_SETTLEMENT` audit row, `payments.error` (*"late settlement: hold was expired"*), and the new `DEPOSIT_LATE_HONOURED` row.
   - **`not_before=now`.** Every sibling writer in this repo that reinstates or re-authorises carries a clock bound — `cancel`'s `not_before` (`:349-350`), `set_manage_token_hash`'s (`:196-197`, whose docstring says a booking that stopped being confirmed-and-future *"cannot be handed a fresh LIVE control token"*), `reschedule`'s `starts_at > not_before` (`:390`), `set_status`'s (`:300-303`). Without it a delivery hours or days late — and the retry budget versus a 15-minute hold is explicitly unknowable until a real provider — would flip a **past** booking to `confirmed`, mint a fresh manage token, and text the bride "your appointment is confirmed" for a date that has passed, while silently re-occupying a seat in a past slot. A past `starts_at` routes to step 4.
   - **`allowed_from=('cancelled','pending_payment')`.** `cancelled` is the ordinary case. `pending_payment` is the belt for the ordering race in D6: if the sweeper's payments UPDATE has committed but its booking cancel has not yet been observed, the booking is still `pending_payment` and a narrow `('cancelled',)` would match nothing and file a **false** "seat taken" alert. It is still one guarded statement and still exactly-once.

   Then: reminder rewrite (D12), confirmation SMS (D13), a `DEPOSIT_LATE_HONOURED` audit row.

4. **Seat taken, or she already rebooked, or the appointment is past, or `rebind` returned `None`, or `rebind` raised `IntegrityError`** → the booking stays `cancelled`, the payment stays `paid`, a `DEPOSIT_LATE_UNRESOLVED` audit row is written, and the row is flagged to the owner (D18). **`IntegrityError` is caught here and mapped to this branch, not left to become a 500** — there is no `IntegrityError` handler in `main.py`, and a 500 on this path is unrecoverable: `settle_late` committed in a prior transaction and wrote `provider_transaction_id`, so every provider retry now hits `by_provider_transaction_id`'s early return. This is the `create_booking:353` backstop pattern (`except IntegrityError → SlotUnavailableError`) applied to a path where the correct answer is not an error at all.
   **What the boutique does with the money at this point is MD1: the deposit stays hers and the owner reschedules her off this very row** (which is why MD1 widens `owner.reschedule` to admit `cancelled` — the button lives on the booking this branch just flagged). **What the bride hears is MD2**, the `PAYMENT_RECEIVED_NO_SLOT` SMS, sent from this branch. Both are recorded decisions, not open questions; neither is smuggled into a design decision.

**Rebinding never moves her to a different time.** A late payment buys back the slot she chose or it buys nothing. **Declined**: auto-rebinding to the next free slot. **Declined**: overbooking the seat.

**One thing this cannot decide and must not guess.** The hold may have outlived a terms republication. F19 **does not** re-ask for acceptance and **does not** rewrite the snapshot: the column is NOT NULL evidence of what she actually agreed to. Recorded as Risk 5.

### D6 — the sweeper: two claims, one transaction, real SQL

**The previous draft's statement does not parse.** It wrote `UPDATE payments … RETURNING …` "claimed with `FOR UPDATE SKIP LOCKED`". Locking clauses are permitted only on `SELECT`; and `claim_due`, the idiom it cited, is a **SELECT** with `.with_for_update(skip_locked=True)` followed by a **separate** guarded `mark()` UPDATE (`scheduled_messages.py:83-113, 115-133`). Both halves of the citation were wrong. What F19 actually issues, per tenant, **inside one `tenant_session`**:

**Claim 1 — the ordinary expiry.**
```sql
UPDATE payments SET status = 'expired', redirect_url = NULL
 WHERE tenant_id = :t AND status = 'pending'
   AND hold_expires_at <= :now AND deleted_at IS NULL
 RETURNING id, booking_id
```
No locking clause, deliberately. The guarded `WHERE status='pending'` already gives exactly-once, and **blocking** on a row an in-flight `settle` holds is the *desired* behaviour: it serializes the sweeper behind the webhook, which is what makes the ordering argument below true. `SKIP LOCKED` would defer a contended row a full poll interval and buys nothing at one worker replica. Rides `idx_payments_hold_expiry` (`0012_payments.py:127-132`). Bounded by `SWEEP_BATCH_SIZE = 500`, the `backfill.py:36-38` shape rather than `DRAIN_BATCH_SIZE`'s 50, because this statement holds no provider call.

Then, and **only** for rows that UPDATE actually returned, `cancel(..., allowed_from=('pending_payment',))` on the booking — **in the same transaction as claim 1**. This is not a stylistic preference: if the payments UPDATE commits before the booking cancel, a webhook blocked on that row lock wakes up, sees `expired`, honours it, and then finds a booking still at `pending_payment` — which under a narrow `allowed_from` files a false "seat taken" alert on a seat that is in fact free, and then the sweeper cancels the booking anyway. One transaction closes it; D5's widened `allowed_from` is the belt.

**Claim 2 — the orphan and crash backstop, on `bookings`.**
```sql
UPDATE bookings SET status = 'cancelled', cancelled_at = :now, cancelled_by = :expired
 WHERE tenant_id = :t AND status = 'pending_payment' AND deleted_at IS NULL
   AND created_at <= :now - (:hold_seconds + :poll_interval)
   AND NOT EXISTS (SELECT 1 FROM payments p
                    WHERE p.booking_id = bookings.id
                      AND p.deleted_at IS NULL AND p.status = 'pending')
 RETURNING id
```
**Without this, every gateway failure at checkout leaks a seat permanently.** D11 commits the booking first, in `pending_payment`, and `open_deposit` opens its **own** session (`payments/service.py:484`) taking only `tenant_id` — it cannot join `create_booking`'s (`booking/service.py:203`), and it re-takes the same advisory lock `create_booking` holds to COMMIT, so folding them is impossible. Everything between the two commits is a seat leak: `credentials_for` and `gateway.create_session` can raise `GatewayNotConnectedError`, `GatewayUnavailableError`, `SecretDecryptError` or `PaymentAlreadyHeldError`, and the process can simply die. Each leaves a committed `pending_payment` booking with **no `payments` row at all** — invisible to claim 1, which sweeps `payments`; and D2 makes the sweeper the only writer that can move `pending_payment` to `cancelled`, since every owner and customer path 409s on an unpaid hold. The seat is then held forever by `active_seats_at` and `idx_bookings_slot_seat_unique`, and 0009's index also stops the bride rebooking her own instant. D11a's compensating transaction handles the common case; claim 2 handles the crash.

The `+ poll_interval` grace guarantees claim 2 never races the ordinary path. It rides a new partial index (migration 0014, statement 5) so it is an index scan over a handful of rows, not a per-tick table scan.

**Ordering is the safety property.** The payment guard is evaluated by the database, so a row a webhook settled a microsecond earlier is `paid`, matches nothing, and its booking is never touched. **Declined**: reading the payment, deciding in Python, then writing. **Declined**: re-reading the row after the UPDATE to decide whether it won — `cancel`'s docstring (`:330-342`) documents that ORM-enabled DML with `evaluate` synchronization stamps the SET values onto the identity-mapped instance whatever the database matched. Read the `.returning()` scalar.

**Hold length: `deposit_hold_seconds`, default 900** (15 minutes). No such setting exists today (`core/config.py:124-149`). It is **not** one of the recorded money decisions: one env var, reversible in a deploy, no data migration, and its only irreversible consequence — the width of the race — is precisely what the db test parameterizes.

**Declined**: widening `ScheduledMessageKind` and riding `scheduled_messages` (`kind` is CHECK-pinned to `('reminder')`, `0010:69`; and `drain_due` is hard-wired to SMS and marks a row **FAILED** when a token or phone is missing, `comms.py:393-413`).

### D7 — the sweeper is a second `await` inside the existing `poll_once`

One more call inside the same per-tenant loop, wrapped in **its own** `try/except … continue` — sharing the reminder drain's would let a bad payment row silence every boutique's reminders (`worker.py:85-88`). Both claims in D6 are inside that one `await` and one transaction. `worker_poll_interval_seconds` governs the cadence, so the maximum a freed seat sits invisible is one tick (60 s default) after the hold expires. **Declined**: a second process; a cron.

### D8 — `payments.redirect_url TEXT` in 0014, and it is blanked on every exit from `pending`

`DepositHold.redirect_url` is `None` on the converged path — deliberately, and F17's comment says it exists *"to force F19 to decide what a retry does"* (`payments/service.py:90-104`, converge return at `:492-500`). F19 stores the hosted-page URL beside the session id: `insert` takes it, the converge path returns it.

**Declined**: re-minting a session on the converge path (the orphaned-payable-session bug D23's ordering exists to prevent). **Declined**: returning `None` and asking her to wait out the hold.

The column is blanked in the same `.values()` as every transition out of `pending` — `settle`, `settle_late`, and the sweeper's claim 1. F20 inherits **no new blanking obligation**.

### D9 — `POST /storefront/payments/webhook` on a new sibling router, and its real status contract

Anonymous, tenant-from-Host, no cookie, no CSRF. Each boutique registers `https://{her-slug}.modryn.co.il/storefront/payments/webhook` in her own provider account, which works *because* credentials are per-tenant. Authenticity is the HMAC signature and nothing else, so the route reaches `verify_webhook` before it touches anything — and it reads the **raw body bytes**, never a re-serialized model (`payments/base.py` types it `body: bytes` for this reason).

**It is a new sibling router, not a route on `storefront_router`.** That router carries a per-tenant `_throttle` (`storefront/router.py:103-137`) which would 429 a provider's retry burst and turn a transient outage into permanently unconfirmed bookings. The `otp_router` / `booking_router` precedent is exactly this shape (`main.py:1035-1043`).

**Declined**: a `/manage` route; a tenant id in the path; an `EXEMPT_PATHS` entry (`tenancy/middleware.py:20-28`).

**The status contract, per outcome — because "200 for every non-forgery outcome" is false against shipped F17 code.** `GatewayWebhookInvalidError` has **three** raise sites and they are three different events:

| Condition | Site | Evidence written | F19's answer |
|---|---|---|---|
| Bad/forged signature | `service.py:542-555` | `GATEWAY_WEBHOOK_REJECTED`, committed before the raise | **400.** Forgery. Correct as shipped. |
| Amount mismatch | `:597-605` | `GATEWAY_AMOUNT_MISMATCH` + `payments.error`, committed in its own transaction | **400**, unchanged. A mismatched amount is attacker-reachable input behind a valid signature; a provider hammering it is the lesser harm, and the evidence exists. |
| **`by_provider_session_id` returned `None`** | `:571-575` | **nothing at all** — it raises *inside* `async with tenant_session`, which is `session.begin()`, so the transaction rolls back | **400, and F17 gains one audit action.** |

That third row is the dangerous one: it is a genuinely-paid webhook that matches no payment row — the identifier-space mismatch named under "What this feature does and does not de-risk", and the unregistered / wrong-subdomain webhook URL of Risk 1. Real money moves and the platform's only trace is a 400 in an access log. **F19 adds `GATEWAY_WEBHOOK_UNMATCHED`** on that path, written with the commit-before-raise pattern, same shape as `GATEWAY_WEBHOOK_REJECTED` — three lines in `payments/service.py`, no migration. It stays **400** deliberately: a provider that retries is exactly what you want when the row might yet appear (a redirect that beat the insert), and the audit row is what makes the permanent case findable.

**Everything else is 200**, including a decline and a late settlement: a provider reads a non-2xx as "retry", and retrying a decline forever is what D25's 400-vs-503 argument is made of.

The default-deny walker filters on `path.startswith("/manage")` (`tests/test_staff_role_gating.py:149, 196`; the `OWNER_ONLY` literal set is at `:69-79`), so this route needs no `OWNER_ONLY` edit and will not red-fail the build.

### D10 — the storefront's gateway-connected read mirrors `credentials_for` exactly

F17's Q1 is inherited: with no connected gateway the storefront hides the deposit entirely and books as if deposits were off. Nothing in the storefront can ask that question today — `GatewayCredentialService.status()` is reachable only through `app.state.gateway_credential_service` (`payments/router.py:36-41`).

**The predicate must be the use path's, not a weaker one.** The previous draft specified a bare `GatewayCredentialsRepository.active_for_provider` read, which filters only tenant + provider + `deleted_at IS NULL` (`db/repositories/gateway_credentials.py:55-63`). `credentials_for` — the call `open_deposit` actually makes — additionally requires `row.status == 'valid'` (`payments/service.py:312-319`), and `_require_provider` additionally requires `gateway.is_configured` **and** `secret_box.is_configured` (`:341-348`). A boutique whose credential was flipped to `invalid` by `revalidate`, or a deployment with the secret box unconfigured, would have been shown the deposit and then met a 409 or a 503 at create — the dead-calendar outcome F17's Q1 ruling exists to prevent, and not covered by **MD4**, which is about `GatewayUnavailableError`.

So: **`GatewayCredentialService.is_connected(tenant_id, session) -> bool`**, a new method that runs the same three checks and takes neither limiter nor key material and returns no ciphertext. `StorefrontService` calls it inside the session it already opens for `list_appointment_types` (`storefront/service.py:229-240`) — one extra indexed statement on an already-open connection, on an already-`_throttle`d anonymous endpoint. The provider string comes from `settings.payment_provider`, the same source `_require_provider` reads. The **same** helper is called by the booking-create path (D19), so the disclosure and the flow cannot disagree.

**Declined**: injecting the full `GatewayCredentialService` surface into the storefront (it owns two rate limiters and the secret box). **Declined**: caching the flag on `TenantContext` (`tenancy/resolver.py:8-10` defers caching to E5). **Declined**: hiding it client-side.

**Flagged to the reviewer**: `deposit_required` / `deposit_amount_agorot` are already disclosed to anonymous visitors today (`storefront/schemas.py:171-186`), so hiding them is a visible change to a live public contract.

### D11 — the booking is created first, in `pending_payment`, and its SMS moves

**Order.** Create then pay. Paying first cannot hold the seat, so two brides could pay for the same slot; creating first means the seat is claimed by F13's existing advisory-lock protocol and the payment is a state transition on a row that already exists. The cost is a row that outlives an abandoned checkout by up to one tick, which is what `pending_payment` is for — and the orphan window, which D6 claim 2 and D11a close.

**The call site, named.** `open_deposit` is called by **`booking/router.py`'s create handler**, after `create_booking` returns and before the response is built — the same position and for the same reason as the shipped post-commit `send_confirmation` call: `PaymentService` opens its own sessions, so a provider hang inside the booking transaction would block commits (`booking/router.py:18-23`). It is called when `claim.deposit_due` is true, on **both** the `created=True` and the `created=False` replay branches (D11b).

Two blockers in one handler, both verified:

- **`BookingsRepository.insert` has no `status` parameter** (`bookings.py:56-104`); the value comes from `server_default 'confirmed'` (`models/booking.py:31`). F19 adds `status: str = BookingStatus.CONFIRMED.value` — a defaulted keyword, so no existing caller moves.
- **The router fires the confirmation SMS inline**: `if claim.created and claim.manage_token is not None: await comms.send_confirmation(...)` (`booking/router.py:95-107`). Left alone, a deposit-required booking texts the bride a confirmation before a single agora is taken. The condition gains `and not claim.deposit_due`.

**Declined**: a second insert method for the deposit path. **Declined**: inserting `confirmed` and flipping afterwards.

`BookingClaim` gains `deposit_due: bool`; the create response gains `redirect_url: str | None` and `payment_session_id: str | None` (D13).

### D11a — what happens when `open_deposit` raises, and it is MD4's mechanism

The booking is already committed as `pending_payment`. Every exception from `open_deposit` therefore needs a **compensating transaction**, and which one is **MD4**, decided (a):

- **MD4 (a) — book without the deposit** (**this is what F19 builds**): `set_status(to='confirmed', allowed_from=('pending_payment',))` in a new transaction, then the ordinary post-commit `send_confirmation` with `claim.manage_token`, plus a `GATEWAY_UNAVAILABLE_AT_CHECKOUT` audit row and the owner-visible marker (MD4's cost 1, D18). Response: `deposit_due=false`, `redirect_url=null`, `status="confirmed"`.
- **(b) — refuse**: **declined at MD4**, kept specified because reversing MD4 must not require re-deriving it: `cancel(..., allowed_from=('pending_payment',))` in a new transaction, then re-raise so the storefront gets its 503. **The cancel would not be optional under (b)**: without it the refusal leaks the seat, which is the failure (b) exists to avoid.

This applies to `GatewayUnavailableError`, `SecretDecryptError`/`SecretBoxNotConfiguredError` and `GatewayNotConnectedError` alike. The last should be unreachable because D19's predicate ran first, but it can lose a race with a disconnect, and a raced disconnect must not leak a seat either. `PaymentAlreadyHeldError` is **not** in this set — it means a hold already exists, which is the converge case D11b covers.

If the compensating transaction itself fails or the process dies, D6 claim 2 sweeps the row one hold-plus-a-tick later. That is the belt; this is the braces.

### D11b — the replay branch calls `open_deposit` too

`create_booking` returns `BookingClaim(booking=replayed, created=False, manage_token=None)` at step 4b when a live booking exists for this proven phone at this instant (`booking/service.py:287-296`), and `active_at`'s predicate is `status != 'cancelled'`, so a `pending_payment` booking matches. The lost-201 retry and any re-submission inside the hold window take that path.

So the deposit path runs on **both** branches. On the replay branch `open_deposit` converges — `live_pending_for_booking` returns the existing row with **no gateway call at all** — and D8's stored `redirect_url` is what makes that converge return a working link instead of `None`. This is what D8's promise and the storefront's declined-state copy ("retry, which converges onto the same hold and returns the same link") actually rest on; the previous draft never said the replay branch called `open_deposit` at all.

### D12 — the reminder must be rewritten on confirm, and the failure it prevents is invisible

`create_booking` **always** inserts the reminder row regardless of status (`booking/service.py:358-367`), and `reminder_send_after` returns `now` — immediate — for any lead between 2 h and 24 h (`booking/comms.py:68-86`). `drain_due` then re-reads the booking and, on `status != 'confirmed'`, flips the row to `cancelled` and sends nothing (`:383-392`), with `mark` clearing `manage_token` on the way (`scheduled_messages.py:128`).

So: a bride who books a deposit-required appointment **3 hours out** gets a reminder scheduled for immediately, and the very next worker tick — within 60 seconds, long before she has finished paying — cancels it permanently. She pays, gets confirmed, and silently never gets her reminder. For a >24 h appointment `send_after = starts_at − 24 h`, so the bug does not fire — which is what makes it the kind that ships green.

F19 calls `upsert_reminder` inside its confirm transaction, the F15/D8 precedent the helper was given a `session` parameter for (`comms.py:99-116`).

**Declined**: not calling it. **Declined**: suppressing the reminder insert at create time for deposit bookings (a >24 h booking that pays instantly then has no reminder at all — the same bug, moved).

### D13 — the confirmation SMS re-mints the manage token; the poll uses `provider_session_id`, not a token

**The SMS token.** `manage_token_hash` is sha256 and `BookingClaim.manage_token` carries the raw value only at creation, so a confirmation deferred to webhook time cannot reuse it — `comms.py:128-136`: *"the hash is one-way, so the new row needs a new token."* `upsert_reminder` would normally carry the pending row's token forward, but D12 has just established that in the common deposit case (2–24 h out) the worker already cancelled that row and `mark` cleared its token. So F19 mints one token in its confirm transaction, calls `set_manage_token_hash`, and passes it to `upsert_reminder` through a new optional `token: str | None = None` keyword — defaulted, so F15's `reschedule_reminder` caller is unchanged. Post-commit the router calls the shipped `send_confirmation(tenant, booking=…, manage_token=token)`.

**Declined**: `reissue_manage_token` (opens its own `tenant_session`, so it cannot join the confirm transaction, and calling it after would mint a second token on top of the one the reminder row just took). **Declined**: reading the raw token off `scheduled_messages.manage_token`. **Declined**: a `bookings.manage_token_plain` column.

**The poll credential is NOT the manage token.** The previous draft specified `POST /storefront/booking/payment-status { token }`, which cannot work, three times over: `BookingCreateResponse` carries no token (`booking/schemas.py:40-49`); on the deposit path the confirmation SMS is suppressed so the bride never receives the manage link either; and `set_manage_token_hash` overwrites `manage_token_hash` unconditionally (`bookings.py:198-203`) while `by_manage_token_hash` is the only lookup (`:150-166`) — so the poll would start 404-ing at precisely the moment it should return `paid`. A bride who paid would sit on a spinner forever, on the money surface.

**F19 polls by `provider_session_id`**, returned in the create response on the deposit path. It costs no new column, no new secret and no rotation hazard:
- it is already client-visible **by construction** — it is embedded in the hosted-page URL the browser is about to visit (`FakeGateway` builds `/fake-pay?session={session_id}`, `payments/fake.py:121`; real providers do the same);
- `PaymentsRepository.by_provider_session_id` already exists and is tenant-scoped (`payments.py:70`);
- guessing one means guessing a provider-minted opaque id;
- the response carries `{ booking_status, payment_status, paid_at }` and no PII, so possession authorises nothing but a status read;
- the converge path returns the stored id too (D11b), so a retry polls the same hold.

### D14 — the surfaces a fifth status changes, all of them

**Backend.**
- **`manage.py`** (the bride's tokenized page) branches on `CANCELLED` and treats everything else as an appointment that stands (`:131, :158`); `by_manage_token_hash` has **no status predicate at all** (`bookings.py:150-166`). A `pending_payment` booking must render as awaiting payment, and `confirm_attendance` / `cancel` must 409 on it rather than acting.
- **`dashboard/service.py` — one predicate, all six sites.** The previous draft prescribed *"one extra `continue` in `week_buckets` and one field on `StatusTotals`"*, which leaves four sites wrong: `cancellation():146` divides by `len(facts)`, so a live checkout sits in the denominator of the headline rate; `top_types():206` counts an unpaid hold as a booking in the chart; `customer_mix():251` and the `cohort_ids` fold at `:371` put a bride who never paid into the customer cohort and the repeat-rate denominator. **F19's ruling: `pending_payment` rows are filtered out of `facts` once, at `DashboardService.dashboard():362`, immediately after `list_window_facts` returns** — one predicate, six sites, and `list_window_facts`'s "EVERY status" contract (`bookings.py:502-560`) is left alone for F20 and F52. `StatusTotals` still gains a `pending_payment` field, fed from the unfiltered count, so the pure-tested invariant `sum(weeks.bookings) == confirmed + no_show + completed` keeps balancing and the number is visible somewhere. A checkout in progress is not an appointment; counting it would make "bookings last week" move as brides open and abandon payment pages.
  **MD5** is a **separate** edit on top of this one: it removes `cancelled_by='expired'` rows from `cancellation()`'s numerator and denominator. Filtering `pending_payment` does not do that, because an expired hold has already become `cancelled`.

**Frontend — five files, not three.**
- **`storefront/src/api.ts:308-310`** documents the four-value assumption in a comment; it gains the fifth.
- **`manage/src/lib/booking.tsx:15-26`** — a four-entry `Map` with a raw-value fallback, so a fifth status today renders the literal LTR string `pending_payment` inside a Hebrew RTL console. It gains a real entry and `he.ts` / `ar.ts` keys.
- **`manage/src/components/BookingDetail.tsx:201-205`** derives `liveConfirmed` / `pastConfirmed` / `isNoShow` / `isCompleted` / `isCancelled` from the four statuses. A `pending_payment` booking satisfies **none** of them, so the owner's detail panel renders with no state and no action set. It gains a fifth branch showing an awaiting-payment state with **no owner actions** (the backend 409s on all of them anyway) and, under D18, the payment marker.
- **`storefront/src/routes/ManageBookingPage.tsx:38, 291`** — `const CANCELLED = "cancelled"` and `const cancelled = booking.status === CANCELLED` are the only status branch on **the bride's own page**. As shipped it would render an unpaid hold as a standing appointment with a live cancel button. It gains an awaiting-payment state carrying the checkout link, with cancel and confirm-attendance suppressed.
- **`storefront/src/routes/ManageBookingPage.tsx:390`** — the unconditional `manage.cancelConsequenceFree` sentence. **MD3**: it is replaced on a deposit booking by the new `manage.cancelConsequenceDeposit` key carrying MD3's neutral interim sentence, and `cancelConsequenceFree` survives only where no deposit exists. This is the one frontend edit F19 must not merge without, and the interim satisfies it — **the parked copy does not block it**.

All four new strings need `he.ts` and `ar.ts` keys, asserted by the he/ar key-parity test F17 added to `i18n.test.ts`.

### D15 — money is integer agorot end to end

`amount_agorot INTEGER NOT NULL CHECK (amount_agorot > 0)` (`0012_payments.py:96`), snapshotted onto the payment row at hold time (`models/payment.py:16-18`). The wire carries `amount_agorot: int`; no float, no decimal, no string, nowhere. The frontend divides by 100 at render only, through `Intl.NumberFormat`, inside `<bdi dir="ltr">`. D10's no-`currency`-column ruling stands.

### D16 — refund-due vs forfeit is computed, not asked; only its *execution* is blocked

Every input is already on the row: `terms_versions.refundable_until_hours_before` and `forfeit_percent` (`models/terms_version.py:22-26`) against `bookings.terms_version_accepted` + `starts_at` (`models/booking.py:36-39`), with the table append-only (`0005:126-127`). `models/booking.py:50-53` names this computation as F19's.

What F19 does **not** do is *perform* a refund: the port ships no `refund()` (D12, reaffirmed at F17's Gate 1), and `forfeit_percent` is a percentage, so a partial refund could only ever be **recorded** as `refund_due`, never executed. F19 therefore writes no `refund_due` / `refunded` / `forfeited` row at all.

**The computation is not, however, invisible.** Two surfaces consume it and both are in scope: the bride's cancel screen (**MD3** — the number is what the two parked variants will render; the interim sentence does not name it), and the owner's marker (D18) on a cancelled booking that still holds money. Computing a number that is never shown would be the decision skipped rather than made — which is what the previous draft did.

### D17 — an honoured late settlement lands on `paid` (F17's ruling, not a new question)

F17's Gate 1 Q4 states it in its second sentence: *"HONOUR IT, and alert the owner. **The deposit is marked paid.**"* (`gateway-port.md`, Gate 1 resolutions; `.planning/LOOP-STATE.md:153-154` records the same). F17 also set the re-ask condition — *"F19 implements; re-asked at its Gate 1 only if the flow contradicts it"* — and nothing in this flow contradicts it. What F19 discovered is that the shipped code has **no writer** for it (`settle` is guarded `WHERE status='pending'` and matches nothing against an `expired` row), which is an implementation gap, not a reopened ruling.

`PaymentsRepository.settle_late` is that writer: a guarded UPDATE `WHERE status='expired'` writing `paid` + `paid_at` + `provider_transaction_id` + `redirect_url = NULL`, owned by `PaymentService.honour_late_settlement`.

**Declined: a distinct `late_paid` status**, and the honest reason — not the one the previous draft gave. The previous draft argued that flipping to `paid` is *"the only option that also fixes the replay hole"*; that is **false**. The replay guard keys on `provider_transaction_id` alone, with no status predicate (`payments/service.py:562-569`), and 0012's unique index is likewise status-agnostic — so `settle_late` writes the transaction id and re-arms the guard whichever status value it sets. The real comparison: `late_paid` costs one CHECK value in 0014 and forces every present and future "money is in" reader to name two values (F19's own guards, F20's retention read, F29's refund path), and buys a distinction that `paid_at > hold_expires_at` already carries structurally on the row itself, plus a permanent `GATEWAY_LATE_SETTLEMENT` audit row. That comparison still lands on `paid`.

### D18 — the owner sees an anomalous payment on the booking row she already opens

Q4 says "alert the owner". There is no owner-facing payment surface anywhere in the product: `GatewayStatusResponse` is exactly six fields and its docstring says *"Nothing else, ever"* (`payments/schemas.py:8-27`), the owner booking console renders no payment data, and `AuditLogRepository` exposes only `record` and `list_actions` with **no router reading it** — so the audit log is not an owner surface either.

**`OwnerBookingRow` gains `payment_status: str | None`**, and `OwnerBookingDetail` inherits it (`booking/schemas.py:107, 133` — there is no `OwnerBookingResponse`; the previous draft named a class that does not exist, three times). The console renders a badge, and a booking whose payment is `paid` while its status is `cancelled` gets an **action-needed** marker in the list the owner already loads every morning. The same field carries **MD4**'s *"booked without a deposit"* marker.

**Honest cost, corrected.** This is *not* "one repository read, no code": `PaymentsRepository` has no batch read — its whole surface is `insert`, `live_pending_for_booking`, `by_provider_transaction_id`, `by_provider_session_id`, `settle`, `record_error`, `by_id`. So it is **a new `by_booking_ids(session, tenant_id, booking_ids) -> dict[UUID, Payment]` batch read**, one call in `OwnerBookingService.list_day`, and a field in `owner_router._row_fields:99`. Still no new route, no `OWNER_ONLY` edit, no nav row — roughly a third of a day.

**Declined**: a new `/manage/payments` console section — it is the right shape once refunds exist (F29), and building it now is a router, a `ROUTES` table entry, an `OWNER_ONLY` row (`tests/test_staff_role_gating.py:69-79`), a nav row and i18n for a section with one row in it. **Declined**: out-of-band only (the audit row and a log line) — the pilot boutique's owner cannot see her own money.

**Stated plainly, because it is the honest limit of this decision**: the marker tells her *that* something is wrong. The **button** behind it is **MD1**'s — the reschedule that MD1 widens `owner.reschedule` to allow on a cancelled-but-paid booking. Without MD1 this marker is a dead end, which is exactly why MD1 was not left on its do-nothing posture.

### D19 — `deposit_due` is one predicate, evaluated in one place

The field D11 branches on has to be defined, and the previous draft never defined it — which meant a boutique's own deposits off-switch, shipped since F7 and the stated premise of this whole feature, still had no reader after F19.

```
deposit_due = tenant.settings.toggles.deposits_enabled
          AND appointment_type.deposit_required
          AND appointment_type.deposit_amount_agorot > 0
          AND gateway_credentials.is_connected(tenant_id)     # D10's helper
```

Evaluated **once**, by one helper, called by both `public_appointment_type` (the disclosure) and `create_booking` (the flow), so the two cannot disagree — which is the same argument D10 makes and the same helper. The master toggle wins over the per-type flag: a boutique who switches deposits off keeps taking bookings and stops collecting, exactly as F17's Q1 ruled for the not-connected case.

Not one of the recorded money decisions — the toggle obviously wins — but a decision, and it belongs here rather than in an unwritten assumption.

### D20 — the late-settlement transition is a `PaymentService` method, not a repository call from a route

`models/payment.py:12-13`: *"`PaymentService` is its single writer — no adapter and no future caller can skip this row."* F19 is the first feature that could break that, and it would break it on day one if the webhook route called `PaymentsRepository.settle_late` directly. So `settle_late` (the repository statement) is wrapped by `PaymentService.honour_late_settlement(tenant_id, *, payment_id, transaction_id, paid_at)`, and the route calls **only** the service. Same rule as `open_deposit` and `settle_from_webhook`.

### D21 — a dev-only `/fake-pay` page, because otherwise nothing in this feature can be seen

**`FakeGateway` never posts a webhook to anything.** `create_session` returns `redirect_url = "/fake-pay?session={id}"` (`payments/fake.py:121`) built from `FAKE_PAY_PATH = "/fake-pay"` (`payments/validation.py:31`), and a repo-wide grep for either finds **only** those two definitions plus one test assertion — **there is no route, no page and no task that ever POSTs the webhook endpoint.** `sign_fake_webhook` and `fake_webhook_body` are module-level helpers with no production caller.

So on staging, as previously specified, every deposit booking redirects to a 404, sits on the "awaiting the webhook" screen forever, and is expired and cancelled by the sweeper one tick later — the exact inverse of what Risk 2 claimed. None of the five storefront payment states past hand-off could be exercised, and the F21 UAT this feature feeds could not see the flow at all.

F19 ships a **dev/staging-only** `/fake-pay` page: it reads `?session=`, offers "pay" and "decline" buttons, builds the body with `fake_webhook_body`, signs it with `sign_fake_webhook`, and POSTs `/storefront/payments/webhook`. ~20 lines, guarded off in production by the same condition that already boot-fails `payment_provider="fake"` there. **F18 deletes it** — a real hosted page replaces it.

---

## The race, enumerated

The centrepiece. Every interleaving of a 15-minute hold against a webhook, with what each party experiences. `now` is `PaymentService`'s injected `WallClock` (`payments/service.py:51-57`) — calendar time, distinct from the rate limiters' monotonic clocks and from the booking layer's boutique-timezone `Clock`. **The sweeper takes the same injected clock as `open_deposit`, or the race test cannot pin both sides of it.**

| # | Interleaving | Payment row | Booking | Bride sees | Boutique sees |
|---|---|---|---|---|---|
| 1 | Webhook before expiry, paid | `pending → paid`, `newly_settled=True` | `pending_payment → confirmed`, reminder rewritten | confirmation SMS + confirmed page | a normal booking |
| 2 | Webhook before expiry, **declined** (`paid=false`) | stays `pending`, `GATEWAY_PAYMENT_DECLINED` | untouched; swept at expiry → `cancelled` | "payment not completed", no SMS | nothing; the seat comes back |
| 3 | No webhook ever (abandoned) | `pending → expired` at the first tick after `hold_expires_at` | `pending_payment → cancelled`, `cancelled_by='expired'` (MD5) | seat released; she may rebook | the seat reappears in the grid; the row lands in "never completed", not in the cancellation rate (MD5) |
| 4 | Webhook **after** expiry, **seat still free** | `expired → paid` via `settle_late` | `cancelled → confirmed`, same seat, same time (D5's `rebind`) | confirmation SMS, appointment stands | `GATEWAY_LATE_SETTLEMENT` + `DEPOSIT_LATE_HONOURED`; nothing to do |
| 5 | Webhook **after** expiry, **seat resold** | `expired → paid` | stays `cancelled`; flagged | the `PAYMENT_RECEIVED_NO_SLOT` SMS — deposit held, a call is coming (**MD2**) | a paid booking needing a new time, with an action-needed marker (D18) **and a live reschedule button behind it (MD1)** |
| 6 | Two deliveries of the **same** txn, concurrent | exactly one `pending → paid` (DB-evaluated guard) | exactly one confirm (D3's guard) | **one** SMS | one audit row |
| 7 | Delivery of an already-settled txn (sequential redelivery) | `by_provider_transaction_id` early return | **D3's guarded confirm runs anyway** — normally a no-op | nothing, normally | nothing, normally |
| 8 | A **second, different** txn on a paid row | `GATEWAY_DUPLICATE_TRANSACTION`, row unchanged | untouched | nothing | two real charges, one recorded here to reconcile against |
| 9 | Webhook lands **exactly as** the sweeper claims the row | the sweeper's guarded UPDATE and `settle` contend for the same row lock; whichever loses matches nothing | one of #1 or #4, never both | consistent either way | consistent either way |
| 10 | Amount mismatch | evidence committed, status stays `pending`, then **400** | untouched; swept at expiry | "payment could not be verified" | `GATEWAY_AMOUNT_MISMATCH` |
| **11** | **Crash between `settle`'s commit and F19's confirm** | `paid` (committed) | stuck at `pending_payment` | spinner, then nothing | — |
| | *→ recovered by* | — | the next provider redelivery runs D3's guard (row #7) and repairs it: one confirm, one SMS | confirmation SMS, late | one `BOOKING_CONFIRMED` row |
| **12** | **`open_deposit` raises (503/409/crash) after the booking committed** | **no row at all** | `pending_payment` orphan — invisible to the payments sweep | — | a seat that never comes back |
| | *→ recovered by* | — | D11a's compensating transaction (immediate), or D6 claim 2 (hold + one tick) | an ordinary confirmed booking and confirmation SMS, no deposit taken (**MD4**) | the booking stands, wearing a "booked without a deposit" marker (**MD4**) |
| **13** | **Sweeper expires the payment, commits, then the late webhook lands before the booking cancel** | `expired → paid` | still `pending_payment`, not yet `cancelled` | — | — |
| | *→ prevented by* | — | D6's single transaction; D5's `allowed_from=('cancelled','pending_payment')` is the belt | correct either way | **never** a false "seat taken" alert |
| **14** | **She paid, then cancels her own booking** | stays `paid`, orphaned — `manage.cancel` never touches `payments` (`manage.py:143-175`) | `cancelled`, `cancelled_by='customer'`, reminder cancelled | **MD3's interim sentence** — "the deposit is handled per the boutique's policy", replacing today's shipped "cancelling is free"; the two window-specific variants are the parked item | the owner is holding money she may owe back; D18's marker is what tells her |
| **15** | Late delivery, **and she already rebooked the same instant** | `expired → paid` | rebind refused by D5 step 2's `active_at` check — one deposit must not buy two live appointments | the `PAYMENT_RECEIVED_NO_SLOT` SMS (**MD2**) | marker plus reschedule button (**MD1**) — but note the honest limit: her live booking already stands (and on a `deposit_required` type she paid a *second* deposit for it), so moving the cancelled row to another time is not what she wants. This is the one case MD1's button does not actually remedy; the deposit sits stranded until a human decides, and F29 is the earliest anything can refund it |

**#9 and #13 are the ones only Postgres can settle**, which is why the tests are db-marked with two `asyncio.gather`ed drivers on separate connections. **#5, #14 and #15 are the ones with no obviously safe default**, which is why each carries a recorded money decision (MD1/MD2 for #5 and #15, MD3 for #14) rather than a guess buried in a design line. **#11 and #12 were the review's two BLOCKER findings**: both were windows with no recoverer at all, and both now have a named one.

**Atomicity of the seat, under two concurrent brides.** Unchanged from F13: seat choice happens under `pg_advisory_xact_lock(hashtext(tenant_id))` against `active_seats_at`, whose predicate is `status <> 'cancelled'` — so a `pending_payment` row is counted, and `idx_bookings_slot_seat_unique` refuses the write of any racer that skipped the lock. The rebind at #4 takes the **same** lock, reads **both** occupancy facts, and catches `IntegrityError` from **both** indexes.

## API contract

```
POST /storefront/bookings                  (existing; response gains three fields)
  201 -> { id, starts_at, status, appointment_type_name, dress_name, dress_size,
           deposit_due: bool, redirect_url: string | null,
           payment_session_id: string | null }
       status is "pending_payment" when deposit_due, else "confirmed".
       redirect_url and payment_session_id are null unless deposit_due.
       Under MD4, a provider outage returns deposit_due=false
       and status="confirmed" (D11a) — the booking stands, no deposit taken.

POST /storefront/booking/payment-status     (new; anonymous)
  body { payment_session_id }  ->  { booking_status, payment_status, paid_at }
       The return page polls this. POST for a read, the /booking/lookup precedent
       (booking/router.py:123-125). Keyed on the provider session id, NOT the
       manage token — D13 explains why the token cannot work here.

POST /storefront/payments/webhook           (new; anonymous, HMAC-authenticated)
  raw body + signature header
       -> 200 {}    every non-forgery outcome: paid, declined, redelivery,
                    duplicate transaction, late settlement
       -> 400 GATEWAY_WEBHOOK_INVALID   bad signature | amount mismatch |
                                        no matching payment row  (D9's table)

GET  /fake-pay                              (new; dev/staging only, D21)
```

No new `/manage` routes — `OwnerBookingRow` gains one field on a shipped route (D18).

New `AuditAction` members, **no migration** (`audit_log.action` is unconstrained TEXT, 0003): `DEPOSIT_HOLD_OPENED`, `DEPOSIT_HOLD_EXPIRED`, `DEPOSIT_LATE_HONOURED`, `DEPOSIT_LATE_UNRESOLVED` (the seat-taken case), **`GATEWAY_WEBHOOK_UNMATCHED`** (D9), and `GATEWAY_UNAVAILABLE_AT_CHECKOUT` (MD4). All are no-actor failure/system-path writes and follow `.memory/patterns/commit-before-raise-in-tenant-session.md`.

**Wiring**: `app.state.payment_service = PaymentService(get_session_factory(), gateway=app.state.payment_gateway, credentials=app.state.gateway_credential_service)` — the singleton `main.py:698-701` deliberately left unbuilt, and the comment there is deleted in the same commit.

## Migration 0014

F18 has claimed 0013 (`lemonsqueezy-adapter.md:23`), so 0014 is the next free number. Five statements:

1. `bookings.status` CHECK → `('confirmed','cancelled','no_show','completed','pending_payment')`.
2. `bookings.cancelled_by` CHECK → `('customer','owner','expired')` *(MD5)*.
3. `payments` gains `redirect_url TEXT`.
4. `message_log.kind` CHECK gains `PAYMENT_RECEIVED_NO_SLOT` *(MD2 — **unconditional**; the question form made this statement conditional on a user ruling, and MD2 is that ruling)*.
5. `CREATE INDEX idx_bookings_pending_payment ON bookings (tenant_id, created_at) WHERE deleted_at IS NULL AND status = 'pending_payment'` — D6 claim 2's orphan sweep. Partial on a status that holds a handful of live rows, so it costs nothing and turns a per-tick table scan into an index scan.

No other index is created, altered or dropped — the two partial unique indexes and every occupancy query already have the right predicate, and `idx_payments_hold_expiry` was built for this feature in 0012. `payments` inherits **F17's** Gate 1 Q3 7-year retention clock, and D8 means F20 gets no new blanking obligation.

## Frontend changes

**Storefront — the booking flow.** `BOOK_STEPS` gains `"pay"` (`router.tsx:26`) — a closed set, so no dress id can be read as a step. Five states, all Hebrew, RTL, `<bdi dir="ltr">` on amounts, axe-clean against the standing IS 5568 / WCAG 2.0 AA gate:

| State | Copy register |
|---|---|
| hand-off | "מעבירים אותך לתשלום" + the redirect, with a manual link fallback for a blocked redirect |
| returned, awaiting the webhook | "מאשרים את התשלום" — polls `payment-status` with `payment_session_id`; **the webhook is authoritative, not the redirect** |
| paid | the existing confirmed screen, unchanged |
| declined | "התשלום לא הושלם" + retry, which converges onto the same hold (D11b) and returns the **same** link (D8) |
| expired | "הזמן שמור לך פג" + rebook, from the storefront's normal slot picker |

The polling stops on a terminal state and after a bounded number of attempts; a plain interval, not a websocket (pre-decided #23 rules no vendor).

**Storefront — the bride's manage page (`ManageBookingPage.tsx`).** Two edits, both required:
- a `pending_payment` branch beside the shipped `cancelled` one (`:38, :291`): an awaiting-payment state carrying the checkout link, with cancel and confirm-attendance suppressed. Without it, an unpaid hold renders as a standing appointment with a live cancel button.
- **`manage.cancelConsequenceFree` (`:390`, `he.ts:297`) — MD3.** The shipped sentence tells a bride who paid a deposit that cancelling is free. It must not survive this merge. A new `manage.cancelConsequenceDeposit` key carries MD3's neutral interim sentence on any booking with a deposit; `cancelConsequenceFree` is left rendering only where none exists. When the two approved window-specific variants land (the parked item), they replace the interim key's value and branch on D16's number — a string change, nothing structural.

**Manage console.** `statusBadge` gains a `pending_payment` entry with a real Hebrew label and `he.ts`/`ar.ts` keys (Arabic is Hebrew standing in, per that file's header and pre-decided #47). `BookingDetail.tsx:201-205` gains a fifth branch — awaiting payment, no owner actions. Under D18: a `payment_status` badge on the booking row and an action-needed marker for a paid booking with no seat, plus MD4's "booked without a deposit" marker, and — per **MD1** — a reschedule action on a cancelled booking whose payment is `paid`.

**Dev only (D21).** A `/fake-pay` page, guarded off in production, deleted by F18.

## Testing

**Fast suite** (no Docker, no provider, no network):

- the storefront omits `deposit_required` / `deposit_amount_agorot` with no connected gateway and emits them with one (D10) — and **omits them when the credential row exists but its status is `invalid`, or the secret box is unconfigured**, which is the predicate the previous draft got wrong;
- **`deposit_due` is false with `deposits_enabled` off even on a `deposit_required` type with a connected gateway** (D19) — the toggle's first test, ever;
- the create response carries `redirect_url` + `payment_session_id` only when a deposit is due, and `status == "pending_payment"` exactly then;
- **the replay branch** (`created=False`) on a `pending_payment` booking returns the **same** `redirect_url` and `payment_session_id` (D11b);
- **`open_deposit` raising `GatewayUnavailableError` leaves the booking `confirmed` and sends the confirmation SMS** (MD4 / D11a), asserted on the fake comms outbox, **and the row carries MD4's "booked without a deposit" marker** — the marker has no other failing test, which is why it is asserted here;
- **MD1: `owner.reschedule` accepts a `cancelled` booking whose payment is `paid`**, and the resulting row is `confirmed` with `cancelled_at` / `cancelled_by` **both NULL** — the assertion that fails if the widened writer forgets MD1's property 2; it still refuses a `cancelled` booking with no payment, and it still refuses `pending_payment`;
- **MD2: the seat-taken branch enqueues exactly one `PAYMENT_RECEIVED_NO_SLOT` message** and the seat-free rebind branch enqueues none;
- the create router does **not** call `send_confirmation` on the deposit path, and does on the non-deposit path (D11) — asserted on the fake comms service's outbox, not on a mock's call count;
- the webhook route is anonymous (no cookie, 200 without one), forbids nothing on CSRF, and reads the raw body — a test that re-serializes the JSON and fails is the regression guard;
- **D9's full status table**: 200 on paid, 200 on decline, 200 on redelivery, 200 on late settlement, **400 on a bad signature, 400 on an amount mismatch, 400 on an unmatched session id — and the last writes `GATEWAY_WEBHOOK_UNMATCHED`**;
- the D4 branch table, one case per row, driven by a fake `PaymentService` returning each `newly_settled=False` shape;
- the five storefront payment states and the poll's terminal-state stop;
- `test_config.py` gains `deposit_hold_seconds`. *(Note for the builder: this file shows two false local failures caused by `Backend/.env` leaking `MEDIA_BUCKET`; CI is green. Do not chase them.)*

**`db`-marked** — CI only, no Docker locally, so these debut on the first CI run; budget one fix commit, per house experience with F11, F16 and F17:

- paid webhook → booking `confirmed` **and exactly one** confirmation SMS enqueued **and** a reminder row pointing at the new token (D12/D13);
- **redelivery → no second SMS, no second audit row** — asserted through D3's guarded UPDATE, not through `newly_settled`;
- **the crash-recovery case (race row #11)**: settle, **skip the confirm entirely**, then redeliver — assert exactly one confirm and exactly one SMS, and that the booking left `pending_payment`. This is the assertion the previous draft's D4 table would have made impossible;
- **the orphan case (race row #12)**: commit a `pending_payment` booking with no payment row, run `poll_once` after hold + grace, assert D6 claim 2 cancelled it and another bride can take the seat;
- declined → booking stays `pending_payment`, no SMS, and the next sweep frees the seat;
- **the abandoned case end to end**: create a deposit booking 3 hours out, run `poll_once` before settlement, assert the reminder row is `cancelled` (the F16 behaviour at `comms.py:383-392`), then settle and assert a fresh reminder exists;
- sweeper frees an expired hold → the seat is bookable by another bride, proved by an actual second `create_booking` succeeding;
- **the sweeper never touches a paid booking** — settle first, then run the sweep, then assert the booking is still `confirmed`;
- late settlement, seat free → rebound at the same time and seat, **with `cancelled_at`/`cancelled_by` cleared**; late settlement, seat taken → booking stays `cancelled`, payment `paid`, owner-visible;
- **the rebind refuses a past appointment** (`not_before`) and **refuses when the bride already rebooked that instant** (`active_at`, race row #15), routing both to the owner-alert branch rather than a 500;
- 0014 up/down round-trips; the widened CHECKs admit `'pending_payment'` / `'expired'` and still reject an unknown value; index 5 exists and is partial.

**The race tests, and they are the reason this feature is being built now.** `pytest.mark.db`, NullPool + `asyncio.gather` so every racer gets its own connection — the `test_booking_comms_db.py:1-20` discipline. Bodies and signatures are built **only** through `fake_webhook_body` and `sign_fake_webhook`.

1. **Sweeper vs webhook on the same hold, concurrent** — exactly one of {seat freed, booking confirmed} happens, never both, never neither; asserted on the `.returning()` scalars, never on a re-read.
2. **Two concurrent deliveries of the same transaction** — one confirm, one SMS, one audit row.
3. **Two concurrent brides for the last seat, one mid-payment** — exactly one holds it; the loser gets `SlotUnavailableError`.
4. **A late delivery racing another bride's create for the freed seat** — either she gets the seat and the rebind fails to the owner-alert path, or the rebind wins and her create 409s. A third outcome is not correct.
5. **Sweeper vs late webhook, gathered on separate connections (race row #13)** — assert the outcome is **never** "payment paid + booking cancelled + seat free + owner alerted". This is the test that proves D6's single transaction and D5's widened `allowed_from`.

**Frontend**: the five payment states, the poll's terminal stop, the `pending_payment` badge and its i18n key present in **both** bundles (F17's he/ar key-parity assertion), the `BookingDetail` fifth branch, the `ManageBookingPage` awaiting-payment state, and **MD3's cancel copy — `cancelConsequenceDeposit` renders on a deposit booking and `cancelConsequenceFree` does not, in both bundles**; axe pass on each. **No new E2E** — the storefront flow now ends at a third-party redirect, which Playwright cannot follow; the existing suite must stay green.

## What this feature does and does not de-risk

Stated plainly, because Interview Q7's whole argument is that the race can be proved without a merchant account.

**Provable now, against `FakeGateway` (and, for anything a human must watch, against D21's `/fake-pay` page):** every interleaving in the table above including the two crash windows; the DB-evaluated guards on both sides of the race; the exactly-once confirmation and SMS under redelivery; the sweeper's inability to cancel a paid booking; the seat invariant under concurrency; the whole `pending_payment` blast radius; that a forged or tampered signature is refused by a real `hmac.compare_digest`.

**Not provable until a real provider (F18) and, beyond it, a production PSP:** that the provider actually posts a webhook for every charge; that it retries an unacknowledged one; whether its retry budget outlives a 15-minute hold (which decides how often #4, #5 and #15 actually happen); the real latency between redirect-return and webhook (which decides how long the polling screen sits); whether declines are posted at all or only successes; and the receipt duty, which is the boutique's and is named in F21's audit.

**F19 names no provider anywhere and builds on `PaymentGateway` / `PaymentService` only.** F18 is a sibling, not a dependency. One constraint on every adapter, stated in F19's own words rather than attributed to a document that does not contain it *(the previous draft cited "F18's own D3a finding"; `grep -rn 'D3a'` across the repo returned exactly that one sentence, and `lemonsqueezy-adapter.md` has no such note)*: **`provider_session_id` is ONE identifier space across `create_session` and `verify_webhook`.** F18's adapter reads it back from `meta.custom_data` / the order's `first_order_item`, which is a different place from where `create_session` got it, so the risk is real. F19 must **not** paper over a mismatch with a lookup fallback — a verified, genuinely-paid webhook that matched no row takes the charge, leaves the payment `pending`, lets the sweeper free the seat, and confirms the bride nowhere. **D9's `GATEWAY_WEBHOOK_UNMATCHED` is what makes that case visible instead of silent.**

## Non-goals

- **No refunds**, and no `refund()` on the port (D12 stands, reaffirmed at F17's Gate 1). F29's.
- **No `refund_due` / `refunded` / `forfeited` writer** — D16.
- **No partial payments, no instalments, no saved cards.**
- **No owner-side "mark as paid"** — a money mutation with no provider evidence.
- ~~**No owner remedy for a paid-but-cancelled booking**~~ — **no longer a non-goal: MD1 puts one in scope** (the widened `owner.reschedule`). *(Kept visible rather than deleted because the reasoning still matters: the previous draft twice claimed "F15's reschedule is one click away"; `booking/owner.py:483-484` refuses any non-`confirmed` booking outright, so it was false then, and MD1 is the work that makes it true — a guard widening, a cancel-evidence clear, an `IntegrityError` catch and a console condition, not one click.)*
- **No receipt generation.** The provider issues its own; the Israeli קבלה duty sits with the boutique and is F21's audit row.
- **No KMS**, no retention job, no encryption seam (F17 Gate 1 Q2 and Q3; F20 owns the sweep).
- **No Redis-backed limiter** for the webhook route (F21).

## Risks

1. **The webhook URL is per-boutique and self-registered, and nothing in the platform knows whether it was ever registered.** A boutique who never registers it takes real money on checkouts that never confirm a booking, and the sweeper cancels every one of them. `GatewayStatusResponse` is six fields and its docstring says "Nothing else, ever" (`payments/schemas.py:8-27`); there is no `last_webhook_at` column on `tenant_gateway_credentials` (`0012_payments.py:38-65`). This is the one failure mode in the feature with **no technical detection today** beyond D9's new `GATEWAY_WEBHOOK_UNMATCHED` row, which only fires if the URL points somewhere *wrong* rather than nowhere. Either F19 builds the display and a never-received warning (a `payments`-side timestamp, a response field, console copy) or the pilot accepts a manual operator checklist step. **DECIDED under the same pre-authorization: the pilot takes the checklist step.** It is a one-boutique pilot with an operator present at onboarding; the never-received warning needs a column, a response field, console copy and a threshold nobody can calibrate before a real provider has ever posted (see "does not de-risk" — the retry budget is unknowable until F18), and calibrating it wrong produces either a warning that never fires or one that cries wolf on every quiet morning. D9's `GATEWAY_WEBHOOK_UNMATCHED` covers the wrong-URL case; the never-registered case is caught by the operator verifying one successful test-mode webhook at onboarding. *Owner: team, then F21 — which must re-derive this from the code and decide whether the checklist survives the second boutique. Trigger: F18 (first real registration), F21 UAT.*
2. **The fake gateway settles nothing, and until D21's page exists the flow is unexercisable end to end on staging.** *(This risk was stated backwards in the previous draft — it claimed "on staging every deposit settles instantly and F19 will confirm bookings and text brides off it". `FakeGateway.create_session` returns a `/fake-pay` URL for which **no route exists**, and nothing anywhere POSTs the webhook. The real staging behaviour was a 404 followed by a sweep.)* With D21 the fake settles **on a human's click**, which does mean staging can mark money received that was never charged — bounded by the same three guards F17 recorded: two production boot failures and 0012's `provider` CHECK. *Owner: team. Trigger: F18 (which deletes the page).*
3. **A deposit-required boutique will accumulate `pending_payment` rows at the rate people abandon payment pages**, which is high. Bounded by the hold length **for rows that have a payment row**, and by D6 claim 2 for those that do not — the previous draft's "bounded by the hold length" was false for the orphan class, which had no sweeper at all. D14 keeps them out of every dashboard number, but a boutique watching her own grid will see seats blink out and back for 15 minutes at a time, and nothing on the storefront explains why a slot she can see is unbookable. *Owner: team. Trigger: F21 UAT.*
4. **A bride whose late payment lands against a resold seat depends on a phone call the product cannot make for the owner.** MD1 and MD2 shrink this risk from what it was — she is told automatically within a worker tick, her deposit is held, and the owner has a live reschedule button rather than a dead marker — but the remedy still terminates in a human placing a call. If the owner does not call, MD2's SMS has promised one, which is a **new** and narrower failure mode: a promise made by the product and kept by a person. *(For the record: the do-nothing composite this replaced was money taken, no message, and a marker with no button.)* *Owner: team. Trigger: F21 UAT — watch whether stranded deposits are actually rescheduled, and how long it takes.*
5. **A rebind (#4) can reinstate a booking under a superseded terms version.** D5 rules the snapshot is never rewritten. Recorded rather than asked because rewriting it destroys the only evidence of her actual agreement. *Owner: team. Trigger: F20's compliance read; F21's audit.*
6. **The sweeper's worst-case latency is one poll interval (60 s default) plus the drain's own duration**, and the drain holds its claimed rows' locks for the length of the SMS provider call (`scheduled_messages.py:86-97`). Bounded because the two sweeps are separate `await`s with separate containment (D7), so the payments sweep does not sit behind the SMS call — but they share the tick. *Owner: team. Trigger: E5 #29's scale pass.*
7. **`payments` still ships with more statuses than writers.** F19 adds a writer for `expired` and keeps `paid` as the single terminal success (D17). `failed`, `refund_due`, `refunded` and `forfeited` remain unwritten — and a webhook against any of them currently files as a late settlement (`payments/service.py:654-704`). Whoever gives one of them a writer must re-read that branch **and D5's honour path**, which would otherwise try to rebind against it. *Owner: F29. Trigger: the first refund.*
8. **The storefront's gateway-connected read is one more statement on the highest-traffic anonymous endpoint**, uncached because `tenancy/resolver.py:8-10` defers caching to E5. *Owner: team. Trigger: E5's caching pass.*
9. **A bride who paid and then cancelled leaves an orphaned `paid` payment row**, because `ManageBookingService.cancel` never touches `payments` (`manage.py:143-175`). F19 does not change that — D16 writes no refund status — so the only thing standing between the boutique and a silent liability is D18's marker and MD3's copy — which ships as the **neutral interim** sentence, i.e. truthful but unspecific about what she gets back. *Owner: user (the parked MD3 variants), then F29. Trigger: the parked copy landing; F21 UAT if it has not.*

---

## Decisions Log

- **D1 — `bookings.status` gains `pending_payment`; migration 0014 widens exactly one CHECK.** Both partial unique indexes and every occupancy query use `status <> 'cancelled'`, so a held seat is already an occupied seat. The blast radius is enumerated across 18 sites, five of them frontend. Declined: a `booking_holds` table; a `deposit_pending` boolean beside `confirmed`.
- **D2 — the seat-release writer is `cancel()` with a defaulted `allowed_from`, not a new method.** Declined: an `expire_hold` method (a second writer of the cancel evidence); `set_status` (never writes it at all).
- **D3 — F19's idempotency key is a guarded UPDATE on the booking's own status, and it is also the crash recoverer.** Only `settle` writes `provider_transaction_id`, so F17's replay guard does not cover these paths. `settle` commits in its own transaction, so F19's confirm is necessarily a second one; a redelivery therefore **runs the guarded confirm anyway** rather than short-circuiting, which makes the crash window self-healing. Declined: gating on `newly_settled`; a `webhook_deliveries` table; an in-process seen-set.
- **D4 — the webhook route branches on `settlement.payment.status`, which is total over `PaymentStatus`.** An amount mismatch is not in the table at all: it raises rather than returning. Declined: an outcome enum on `Settlement`; reading `payments.error`.
- **D5 — the honour path rebinds to her original seat or alerts; it never moves her to a different time — and it needs its own writer.** `BookingsRepository.rebind` writes status + `seat_index` + cleared cancel evidence in one statement, guarded `allowed_from=('cancelled','pending_payment')` and `not_before=now`, reading **both** `active_seats_at` and `active_at` first and catching `IntegrityError` from both partial unique indexes. Declined: `set_status` (writes status only, and D1's table said "no edit" for a reason); auto-rebinding to another slot; overbooking; leaving `IntegrityError` to become a 500.
- **D6 — the sweeper is two guarded UPDATEs in one transaction: `payments` on `idx_payments_hold_expiry`, and `bookings` for orphans and crashes.** The previous draft's SQL did not parse (`FOR UPDATE SKIP LOCKED` on an UPDATE) and misdescribed `claim_due` (a SELECT plus a separate UPDATE). No locking clause: blocking behind an in-flight `settle` is the desired serialization. Batch-limited. The booking-side claim exists because `open_deposit` opens its own session and takes the same advisory lock, so a booking committed with no payment row is invisible to the payments sweep and leaks a seat forever. Declined: widening `ScheduledMessageKind`; read-then-write; re-reading the row to decide who won.
- **D7 — the sweeper is a second `await` inside `poll_once` with its own `try/except`.** Declined: a second process; a cron; sharing the reminder drain's exception guard.
- **D8 — `payments.redirect_url TEXT`, blanked on every exit from `pending`.** A returning bride gets her own link back. Declined: re-minting a session on the converge path; returning `None`.
- **D9 — `POST /storefront/payments/webhook` on a new sibling router; 200 on every non-forgery outcome and 400 on three distinct conditions, one of which currently leaves no evidence at all.** `GATEWAY_WEBHOOK_UNMATCHED` is added for the unmatched-session case. Declined: mounting on `storefront_router` (its `_throttle` would 429 a retry burst); a `/manage` route; a tenant id in the path; an `EXEMPT_PATHS` entry.
- **D10 — the storefront's connected read mirrors `credentials_for`'s predicate exactly**, through a new `is_connected` helper, shared with the create path. A bare `active_for_provider` read filters no status and would show a deposit that 409s. Declined: injecting the full credential service into a public read; caching on `TenantContext`; hiding it client-side.
- **D11 — the booking is created first in `pending_payment`; `insert` gains a defaulted `status`; the router's inline SMS is gated on `deposit_due`; and the create handler is the named call site for `open_deposit`.** Declined: pay-first; a second insert method; insert-then-flip.
- **D11a — every exception from `open_deposit` gets a compensating transaction**, and which one is **MD4**'s mechanism (decided: transition back to `confirmed`). Without it, MD4 has no implementation and every gateway failure leaks a seat. The declined refuse-branch stays specified so reversing MD4 costs no re-derivation.
- **D11b — the replay branch (`created=False`) calls `open_deposit` too**, converging onto the same hold and returning the same stored link. This is what D8's promise actually rests on.
- **D12 — `upsert_reminder` is called inside the confirm transaction.** Without it, every deposit booking 2–24 h out silently loses its reminder on the first worker tick. Declined: not calling it; suppressing the create-time insert.
- **D13 — the manage token is re-minted inside the confirm transaction; the payment poll is keyed on `provider_session_id`, not on the manage token.** The token cannot work: it is not in the create response, the SMS that would carry it is suppressed on the deposit path, and the confirm rotates its hash, so the poll would 404 exactly when it should succeed. The session id is already client-visible by construction and authorises nothing but a status read. Declined: `reissue_manage_token`; reading the raw token off `scheduled_messages`; a plaintext token column.
- **D14 — `pending_payment` is excluded from every dashboard number by one predicate at `DashboardService.dashboard()`, and gains a real label at every one of the five frontend sites.** The previous draft named two backend sites of six and three frontend files of five, missing the owner's detail panel and the bride's own page. Declined: counting it as confirmed; leaving the raw value to fall through the badge map.
- **D15 — integer agorot end to end; no float, no decimal, no `currency` column.**
- **D16 — refund-due vs forfeit is computed from shipped columns, not asked; only its execution is blocked, and F19 writes none of those three statuses — but the computed number is rendered on two surfaces.** Declined: sending the user a question the schema answers; recording `refund_due` before F29 can act on it; computing a number nothing displays.
- **D17 — an honoured late settlement lands on `paid`, per F17's Gate 1 Q4, and `settle_late` is the guarded UPDATE that performs it.** Not a Gate 1 question here: F17 ruled it and the flow does not contradict it. Declined: a `late_paid` status — and declined on the honest ground (it forces every "money is in" reader to name two values for a distinction `paid_at > hold_expires_at` already carries), not on the previous draft's false claim that only `paid` re-arms the replay guard.
- **D18 — the owner sees an anomalous payment as a field on `OwnerBookingRow` and a marker on the row she already opens.** Costed honestly: a new `PaymentsRepository.by_booking_ids` batch read, a `list_day` change and a `_row_fields` field — not "one repository read". `OwnerBookingResponse`, which the previous draft named three times, does not exist. Declined: a `/manage/payments` section (F29's shape); out-of-band only.
- **D19 — `deposit_due = deposits_enabled AND deposit_required AND amount > 0 AND gateway connected`, evaluated once by one helper shared with the disclosure.** Gives `deposits_enabled` its first backend reader since F7 — without it, a boutique's own deposit off-switch does nothing after this feature ships.
- **D20 — the late-settlement transition is `PaymentService.honour_late_settlement`, not a repository call from the route**, preserving `payments`' single-writer invariant.
- **D21 — a dev/staging-only `/fake-pay` page that signs and POSTs the webhook.** `FakeGateway` posts nothing and `/fake-pay` has no route, so without it every staging deposit 404s and is swept, and none of the five payment screens or F21's UAT can see the flow. ~20 lines; F18 deletes it.

### 2026-07-31 — Gate 1 realignment: the gate was pre-authorized, and this file did not know

This spec was written, adversarially reviewed twice and declared **PENDING USER APPROVAL** on the strength of `gateway-port.md:495/512` and `.planning/LOOP-STATE.md`'s `spec_gate: user`. Those three citations are accurate and **superseded**: the same LOOP-STATE entry carries a `gate_1_preauthorized` field recording a **USER RULING of 2026-07-31** that postdates all of them — asked how this run should treat the F18 and F19 payment gates, the user chose *"Pre-authorize both"*, trade-off stated and knowingly accepted. The later ruling governs, so **Gate 1 is self-approved and F19 builds.**

What changed in this file, and nothing else did:

- The status line and the opening note now state the pre-authorization and name the `gate_1_preauthorized` field, so the next reader cannot re-derive the conflict the previous revision derived. That revision's reasoning is preserved in substance rather than deleted, because being right about the documents and wrong about the world is a failure worth leaving legible.
- The five Gate 1 questions became **MD1–MD5**, same numbering (Qn → MDn), same evidence, same declined alternatives, each now **taking a position** — four of them the recommendation the question form already argued for, one (MD4) the do-nothing default taken deliberately with its two costs restated. Pre-authorization waived the pause, not the scrutiny, so each carries an explicit **"F21 audit re-derives this"** marker naming what to read.
- **One question is parked** under the ruling's carve-out — **MD3's two approved Hebrew cancel sentences**, the only decision that is user-facing copy *and* a consumer-protection representation *and* a correction to a sentence real customers have already read. A neutral interim sentence ships in their place; the feature does not wait. Nothing else is parked, and MD2's SMS body is explicitly not a second park: it promises an action, not an entitlement.
- Risk 1 carried a sixth undecided call in its tail (*"Either F19 builds the never-received warning or the pilot accepts a checklist step"*). It is decided in place — checklist for the pilot — because a risk is not a place to hide a ruling.
- Every in-body pointer that read "Gate 1 Qn" now reads MDn, and three conditionals that hung on an open gate are resolved: D1's two reschedule rows, D11a's branch, and D18's "whether there is a button behind it". **F17's** Gate 1 references are untouched — they were always a different gate.
- **No design decision D1–D21 was reversed, no race row removed, no migration statement dropped, no test weakened, no risk deleted.** MD1 adds a widened `owner.reschedule`, MD2 makes migration statement 4 unconditional, and each adds one test. The 32 review findings this spec absorbed all still stand.

---

## Review findings

Round 2, three reviewers, 32 findings (9 BLOCKER, 15 MAJOR, 8 MINOR). **All 32 were verified against the code and applied. None rejected.** Three were applied with a different remedy than the one proposed, and those differences are recorded here rather than silently taken:

1. **The poll credential** (finding 13). The reviewer proposed returning the raw manage token in the create response, or minting a new short-lived poll token beside the payment row. F19 uses **`provider_session_id`** instead: zero new columns, zero new secrets, already client-visible by construction, immune to D13's rotation, and it works unchanged on the converge path.
2. **The rebind writer** (findings 3, 19, 26). The reviewer offered "widen `set_status` with optional `seat_index` and a `clear_cancel_evidence` flag" as an alternative to a new method. F19 adds **`BookingsRepository.rebind`** rather than widening `set_status`, because `set_status`'s docstring makes "never writes the cancel evidence" a design commitment shared with three other callers, and a flag that inverts it is a trap for the next reader.
3. **The staging gap** (finding 28). The reviewer offered "correct Risk 2" *or* "add a dev-only `/fake-pay` page". F19 does **both** — the risk was stated backwards and had to be corrected, and without the page the five storefront payment states ship untestable by any human before F18.

Two findings turned on claims this spec had asserted and that the code contradicts; both assertions are now deleted rather than softened: *"F15's reschedule is one click away in the same row"* (`owner.py:483-484` refuses every non-`confirmed` booking) and *"(a) is the only option that also fixes the replay hole"* (the replay guard keys on `provider_transaction_id` with no status predicate).

Three questions left the gate because the codebase or a prior gate already answers them (old Q1 → **D17**, old Q3 → **D18**, the undefined `deposit_due` predicate → **D19**), and three entered it because the previous draft had silently guessed them: what the boutique does with a stranded deposit (**new Q1**), what the bride who paid and then cancels is told (**new Q3**), and the two consequences of Q4's recommended answer that were previously mitigated away rather than stated.

*(This section records round 2 as it happened and is left as written. The five questions it refers to are now the recorded money decisions at the head of the file — the numbering did not move: Qn → MDn. See the Gate 1 realignment entry above for why they stopped being questions.)*
