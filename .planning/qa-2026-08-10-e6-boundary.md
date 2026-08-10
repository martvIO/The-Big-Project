# Boundary QA — E6, with F39 verified on merge day

**Date** 2026-08-10 · **Tree** `main` @ F39 merged (PR #58) · **Runbook** `docs/real-world-qa.md`

## Environment — the real one, not the fixtures

Fresh `modryn_demo` database, **all 35 migrations applied cleanly**, `alembic current` == `heads` == `0035`.
The app connects as **`boutique_app`, not `postgres`**, so RLS actually binds — this discharges gap G1
for every journey below. Three SPA bundles served by the real FastAPI app on one origin; SMS and
payments on the `fake` providers.

Both suites that normally cover this code are blind here by construction: the e2e fixtures intercept
every `/manage` call and never authenticate, and the backend suite never opens a browser. Everything
below crossed the real HTTP boundary.

## Verified in a real browser

| Journey | Feature | Result |
|---|---|---|
| Operator signs into the console and provisions a boutique | F25 | ✅ tenant created, listed, success line correct |
| Slug hint and success line show the configured domain | **F26** | ✅ «הכתובת תהיה ….localtest.me» / «https://demo.localtest.me» |
| Shift manager signs into `/manage` | F31 | ✅ 13 nav rows, role-correct |
| Floor board: live clock + pause, rooms, queue, staff list | F34 | ✅ renders against real data; F38's initial-fallback avatars |
| SOS raised against a logged-out colleague | F37 | ✅ **rerouted to the shift-manager role, and says so** |
| SOS raised against a colleague with a live session | F37→F35 | ✅ real `sos_targeted` row served to her bell |
| Notification bell, empty and populated | F35 | ✅ `<dialog>`, focus lands on close |
| Shift templates seeded from real opening hours | **F39** | ✅ 6 templates, **Saturday emergent-empty** per D3 |
| Availability submitted and persisted | **F39** | ✅ 6 rows, `week_start` DOW = **0** (Jerusalem Sunday, D1) |

## The two findings that justify running this at all

**1. F26's domain fix, proven where it mattered.** The console reads «הכתובת תהיה ….localtest.me».
Before this run's fix every one of those five strings was built from a hardcoded `modryn.co.il` — so
in this environment they would each have named a host that does not exist. The tests could not have
caught it: every fixture pinned the same literal the components hardcoded.

**2. F39's deadline line renders «מועד ההגשה: יום רביעי, 12.8, 18:00».** That is the exact string the
design gate rescued from rendering «יום רביעי, NaN.11, 18:00» — `plainDayMonth` splits a plain date on
`-`, and fed an ISO instant it yields `NaN`. Most-viewed string in the feature, on every load.

## One defect found, in the runbook itself

`docs/real-world-qa.md` §2.3 copied **two** SPA bundles; F25's platform console is a **third**. With it
missing, `/platform` answers a bare 404 that is indistinguishable from the host-fence 404 documented
two blocks below — and since F25 retired the provisioning CLI subcommand, that console is the only way
to create a tenant, so the runbook dead-ends. CI has always copied all three. Fixed in this commit's
parent, along with a stale verified-head (0024 → 0035).

## Behaviour confirmed correct that looked wrong at first

- **The SOS dialog stays open after a successful send.** It is not a stuck modal — it becomes a result
  state carrying «שירן כהן לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.», with focus on «הבנתי».
- **A rerouted page writes no bell row.** Deliberate and documented at `floor/service.py:1665` — NULL
  target is an audience, not a row, and a notification for a staffer with no live session would be the
  one row guaranteed never to be seen. Confirmed by reading the code, then by producing the targeted
  case, which *does* write the row.

## Not covered here

- **E4's deposit journey** (gap G2) — deposits are off in the seed and turning them on needs a
  `deposit_required` appointment type. Still owed; not attempted rather than claimed.
- E5's storefront journeys (waitlist join → offer → claim, client portal OTP) — covered by their own
  suites, not yet walked in a browser.

---

## Addendum — the deposit journey (E4's owed item, gap G2)

Walked it, and it found the most serious defect of the run plus a second one still open.

### Defect A — the deposit was uncollectable in the assembled app. FIXED.

`deposit_due()` is `deposits_enabled AND deposit_required AND amount > 0 AND gateway_connected`.
The last conjunct is answered by a `GatewayCredentialService` that `StorefrontService` and
`BookingService` each take as an **optional** argument defaulting to `None` — which reads as *not
connected*. `create_app` built both about two hundred lines **before** it built that service, so both
took the default. With `deposits_enabled`, a 15000-agorot `deposit_required` type and a gateway both
connected and validated, the storefront disclosed **no deposit at all**.

It failed in the safe direction — nobody was charged, nobody was stranded in an unpaid hold — which
is exactly why nothing alerted.

**Why neither suite caught it:** every unit test constructs those services *with* the dependency,
including `test_storefront_hides_the_deposit_with_no_connected_gateway`. The suite proved both
branches while the assembled app was pinned to one forever. The e2e fixtures intercept the API and
never build the object graph at all. `tests/test_deposit_wiring.py` now asserts the graph `create_app`
actually produces, and is red before the fix.

F23's waitlist claim was the **one** caller wired correctly, and its own comment says why: it is
constructed after the payments block on purpose.

**Verified fixed:** the storefront now discloses «מדידה ראשונה = 15000 agorot» where it disclosed
nothing before.

### Defect B — `POST /storefront/bookings` still answers `deposit_due: false`. OPEN.

With Defect A fixed and the process restarted, a booking on that same type still returns
`deposit_due: false, redirect_url: null, payment_session_id: null`, and the booking lands `confirmed`
rather than in a `pending_payment` hold.

This is **not** the wiring bug. Probed directly against the object graph `create_app` builds:

```
storefront wired: True   booking wired: True   is_connected: True
type row: (deposit_required=True, amount=15000)   toggles: {'deposits_enabled': True}
```

Every conjunct of `deposit_due()` is true, both services hold the same gateway service, and both
routes take `settings` from the same `get_current_tenant(request)`. The disclosure path honours it;
the create path does not. Cause not established — recorded rather than guessed at.

**Next step for whoever picks this up:** instrument `BookingService.create_booking` around
`app/booking/service.py:481` and print the four inputs it actually receives, rather than the ones the
object graph holds. The two disagree, and that disagreement is the bug.

⚠ A false lead cost time here and is worth writing down: an intermediate test of Defect B was run
against a uvicorn started **before** the booking-side edit. A stale server reads exactly like a failed
fix — the same trap as Playwright serving a stale `dist/`. Restart before believing any result.
