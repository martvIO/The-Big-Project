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
