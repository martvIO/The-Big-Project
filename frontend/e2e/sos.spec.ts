import { test, expect } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  MANAGE,
  assignment,
  floorPayload,
  installManageApi,
  ok,
  raisedAlert,
  refuse,
  room,
  sosAlert,
  sosPath,
  sosPayload,
  staff,
  staffCard,
  SELF_ID,
} from "./fixtures/manage";
import type { Reply } from "./fixtures/manage";

// F37, the emergency channel, in a real browser — on F58's harness rather than a
// parallel one.
//
// ⚠ **EVERY TEST BELOW EXISTS BECAUSE jsdom CANNOT ANSWER IT.** The unit suite
// (`SosOverlay.test.tsx`, `SosCentre.test.tsx`, `SosRaiseDialog.test.tsx`,
// `sos.test.tsx`) already pins every branch these journeys walk. What it CANNOT
// pin, and what each block here measures instead:
//
//   1. `@boutique/ui`'s Button is `disabled={disabled || loading}`. A real
//      browser BLURS a control the instant it is disabled and
//      `document.activeElement` drops to <body>; jsdom does not, and leaves
//      focus sitting on the disabled button. That difference is the precondition
//      of MOVES D, F and G, and this repo has shipped a focus-drops-to-<body>
//      defect five times.
//   2. Real key delivery through a document-level CAPTURE listener, with a real
//      caret in a real text field — the Esc route-in (spec BLOCKER 4).
//   3. axe's `color-contrast` rule, which is SKIPPED ENTIRELY in jsdom because
//      Tailwind's stylesheet is never applied there. The whole «the red is the
//      FIELD; each card is PAPER» argument is four measured contrast ratios, and
//      this is the only place in the repo where they are actually measured.
//   4. That the overlay reaches a section which mounts no `FloorPanel` at all —
//      `SosProvider` sits above `ConsoleShell`, and eleven sections poll nothing
//      else.
//
// ⚠ **Risk 6, restated at the point of use: the harness stubs the API, so these
// prove the CONSOLE and not the CONTRACT.** A renamed payload key passes every
// test in this file; `test_sos_api.py`'s set-equality assertions are what catch
// that.

// --- copy, verbatim from apps/manage/src/i18n/he.ts --------------------------

const LOGIN_SUBMIT = "כניסה";
const NAV_PROFILE = "פרופיל והגדרות";
const NAV_BOARD = "לוח היום";
const PROFILE_HEADING = "פרופיל הבוטיק";
const PROFILE_PHONE = "טלפון";
const FLOOR_HEADING = "צוות בקומה";
const ROOMS_HEADING = "חדרי מדידה";
const CENTRE_HEADING = "קריאות עזרה";
const CENTRE_EMPTY = "אין עכשיו קריאות פתוחות.";
const ACCEPT = "אני מגיעה";
const DISMISS = "הסתרה";
const RAISE = "קריאה לעזרה";
const SEND = "שליחת הקריאה";
const REROUTED_ACK = "הבנתי";
const ESCALATED = "ללא מענה";
const NO_ROOM = "לא בחדר מדידה";
const RAISER_GONE = "אשת צוות שאינה ברשימה";
const CHANNEL_DOWN = "ערוץ הקריאות אינו פעיל.";
const CHANNEL_RELOAD = "רענון הדף";
const TARGET_MANAGER = "מנהלת המשמרת";

const calling = (name: string) => `${name} קוראת לעזרה`;
const acceptAria = (name: string) => `${ACCEPT} — הקריאה מ${name}`;
const dismissAria = (name: string) => `${DISMISS} — הקריאה מ${name}`;
const raiseAria = (roomLabel: string) => `${RAISE} — ${roomLabel}`;
const dismissedCount = (n: number) => `${CENTRE_HEADING} · ${n}`;
const alreadyAccepted = (name: string) => `${name} כבר מגיעה.`;
const rerouted = (name: string) =>
  `${name} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.`;

// --- fixture data ------------------------------------------------------------

// Names distinct from each other AND from the harness default «רונית», so a card
// rendered for the wrong alert is NAMED by the failure rather than counted.
const RONIT = "רונית";
const DANA = "דנה";
const MAYA = "מאיה";

const MANAGER = staff({ id: SELF_ID, display_name: DANA, role: "shift_manager" });

// --- helpers -----------------------------------------------------------------

// ⚠ THE TAG IS PART OF THE SELECTOR, and finding that out cost a strict-mode
// violation. On the floor section BOTH surfaces are mounted and both carry
// `data-alert-id`, so a bare attribute selector matches two nodes for one alert
// — and «אני מגיעה — הקריאה מרונית» is genuinely the accessible name of two
// different controls at once. The overlay renders `<article>`, the centre
// renders `<li>`, and every assertion below says which one it means.
function card(page: Page, alertId: string): Locator {
  return page.locator(`article[data-alert-id="${alertId}"]`);
}

function row(page: Page, alertId: string): Locator {
  return page.locator(`li[data-alert-id="${alertId}"]`);
}

// The floor's "the data landed" tell on THIS branch. Not the h2 — it renders
// over the skeleton while the first fetch is in flight, so measuring it would
// measure nothing. `SosCentre`'s h3 is written from the SOS provider and the
// rooms h3 from the floor payload, so waiting on the rooms one proves both
// loops have answered.
async function floorSettled(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { level: 3, name: ROOMS_HEADING }),
  ).toBeVisible();
}

async function gotoFloor(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await floorSettled(page);
}

// ⚠ THE POINT OF FOUR OF THESE TESTS. The two elevated roles land on «סקירה»;
// «פרופיל והגדרות» mounts a plain settings form and NOTHING that polls. If the
// alert reaches this screen it reaches all fourteen.
async function gotoProfile(page: Page): Promise<void> {
  await page.goto(MANAGE);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: NAV_PROFILE })
    .click();
  await expect(
    page.getByRole("heading", { level: 2, name: PROFILE_HEADING }),
  ).toBeVisible();
}

// Replaces a queue's contents in place. `installManageApi` spreads the OPTIONS
// OBJECT but keeps each queue's array reference, so this is what a test uses to
// say «from the next tick on, the server answers THIS» at a moment of its own
// choosing — which a fixed queue cannot express, because the number of ticks
// that elapse while Playwright clicks is not knowable.
function retarget(queue: Reply[], next: Reply): void {
  queue.length = 0;
  queue.push(next);
}

// Only the rule id and the offending selectors say anything useful; the raw
// violation objects dump ~10 KB of axe internals into the failure.
async function axeViolations(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  return results.violations.map(
    (v) => `${v.id} — ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
}

const SETTINGS = ok({
  profile: {
    phone: "",
    address: "",
    description: "",
    maps_url: "",
    essence: "",
    instagram: "",
  },
  toggles: { deposits_enabled: false, brides_only: false },
});

// --- 1. the channel reaches a section that polls nothing, and takes nothing --

test("sos: a page arrives on a section with no poll of its own and does NOT take the caret", async ({
  page,
}) => {
  const alerts: Reply[] = [ok(sosPayload([]))];
  await installManageApi(page, {
    staff: MANAGER,
    replies: { "/manage/settings": [SETTINGS], "/manage/floor/sos": alerts },
  });

  await gotoProfile(page);
  // No alert yet, so nothing is over the form.
  await expect(page.getByText(calling(RONIT))).toHaveCount(0);

  // She is mid-sentence in a real text field, with a real caret.
  const phone = page.getByLabel(PROFILE_PHONE);
  await phone.click();
  await phone.fill("054-123");
  await expect(phone).toBeFocused();

  retarget(
    alerts,
    ok(sosPayload([sosAlert({ raised_by_name: RONIT, room_label: "חדר 2" })])),
  );

  // ⚠ THE OVERLAY IS THE ONLY F37 SURFACE ON ELEVEN OF THE FOURTEEN SECTIONS.
  // `SosProvider` is mounted above `ConsoleShell` in App.tsx precisely so this
  // is true; `SosCentre` is a child of `FloorPanel` and would reach 2.
  // 15s: the idle gap is 5s and the first tick had already fired.
  await expect(page.getByText(calling(RONIT))).toBeVisible({ timeout: 15_000 });
  await expect(card(page, "sos-1").getByText("חדר 2")).toBeVisible();

  // ⚠ THE ASSERTION. MOVE A fires ONLY when activeElement is <body>. Visually
  // blocking, interactively non-blocking: her caret has not moved and not one
  // keystroke is gone. jsdom can assert `document.activeElement`, but it cannot
  // assert that a REAL caret in a REAL field survived a React commit that
  // painted `position: fixed; inset: 0` over it.
  await expect(phone).toBeFocused();
  await expect(phone).toHaveValue("054-123");

  // And she can still type into the field she can no longer see — the hazard
  // the design takes deliberately, pinned rather than assumed.
  await phone.pressSequentially("4");
  await expect(phone).toHaveValue("054-1234");
});

// --- 2. the refusal, measured where a disabled control really is blurred -----

test("sos: a 409 accept names the owner and focus lands in the card's own alert", async ({
  page,
}) => {
  await installManageApi(page, {
    replies: {
      "/manage/floor/sos": [
        ok(
          sosPayload([
            sosAlert({ raised_by_name: RONIT, target_staff_user_id: SELF_ID }),
          ]),
        ),
      ],
      [`${sosPath("sos-1")}/accept`]: [
        refuse(409, "SOS_ALREADY_ACCEPTED", { staff_display_name: DANA }),
      ],
    },
  });

  await page.goto(MANAGE);
  // Scoped to the OVERLAY's card. The reception identity lands on the floor, so
  // `SosCentre` has mounted a second «אני מגיעה» for the same alert — which is
  // the design (D16) and is why nothing here may say `page.getByRole(...)`.
  const accept = card(page, "sos-1").getByRole("button", { name: acceptAria(RONIT) });
  await expect(accept).toBeVisible();
  await expect(row(page, "sos-1").getByRole("button", { name: acceptAria(RONIT) })).toBeVisible();

  // MOVE A landed focus on the CARD CONTAINER and not on the ack control:
  // activeElement is <body> on load, which is exactly the state in which the
  // next Space is a page scroll — and there is no un-accept verb.
  await expect(card(page, "sos-1")).toBeFocused();
  await expect(accept).not.toBeFocused();

  await accept.click();

  const alert = card(page, "sos-1").getByRole("alert").last();
  await expect(alert).toHaveText(alreadyAccepted(DANA));

  // ⚠ THE ASSERTION THIS FILE EXISTS FOR. `loading` → `disabled`, so Chromium
  // blurred the tapped control and `document.activeElement` really did drop to
  // <body> — the precondition MOVE D branches on. In jsdom focus never leaves
  // the button, so the unit test reaches this only through the `inside` branch.
  await expect(alert).toBeFocused();

  // Nothing was claimed: the card is still rising and «אני מגיעה» is still there
  // for the next person. A failed accept is not a failed emergency.
  await expect(accept).toBeVisible();
  await expect(page.getByText(calling(RONIT))).toBeVisible();

  // ⚠ AND THE 409 DID NOT LEAK ACROSS THE TWO SURFACES. `SosCentre` keeps its
  // OWN `rowError`/`rowAlertRef` pair (MOVE H) rather than sharing
  // `FloorPanel`'s, whose `cardError.id` is a STAFF-CARD id — shared, this
  // refusal would render nowhere and steal focus into a staff card on the way.
  await expect(row(page, "sos-1").getByRole("alert")).toHaveCount(0);
});

// --- 3. BLOCKER 4 — the ack control must be REACHABLE from outside -----------

test("sos: Esc from a text field moves focus onto the ack control, and Esc again hides the card", async ({
  page,
}) => {
  const alerts: Reply[] = [ok(sosPayload([]))];
  await installManageApi(page, {
    staff: MANAGER,
    replies: { "/manage/settings": [SETTINGS], "/manage/floor/sos": alerts },
  });

  // ⚠ THE ALERT ARRIVES AFTER THE NAVIGATION, DELIBERATELY, and the first draft
  // of this test had it the other way round and could not click the nav at all:
  // the overlay is `fixed inset-0` and INTERCEPTS POINTER EVENTS. That is the
  // product working — «visually blocking» is literal, and her next tap is meant
  // to land on the emergency — and it means every journey here has to reach its
  // section before the page does.
  await gotoProfile(page);

  // She is mid-form. Forward Tab from here walks every remaining field;
  // Shift+Tab walks the whole ConsoleShell chrome. Announcing an alert perfectly
  // to someone who cannot then REACH «אני מגיעה» is not an accessible alert —
  // the entire justification for the document-level capture listener, which is
  // not something jsdom's synthetic event model reproduces faithfully.
  const phone = page.getByLabel(PROFILE_PHONE);
  await phone.click();
  await expect(phone).toBeFocused();

  retarget(alerts, ok(sosPayload([sosAlert({ raised_by_name: RONIT })])));
  await expect(page.getByText(calling(RONIT))).toBeVisible({ timeout: 15_000 });
  // MOVE A did not fire, so the caret is still hers — which is the state this
  // whole mechanism exists for.
  await expect(phone).toBeFocused();

  await page.keyboard.press("Escape");

  // ⚠ THE CONTROL, not the container: Esc from outside is a DELIBERATE keypress
  // and not an involuntary arrival, which is the whole of DC-1.
  await expect(page.getByRole("button", { name: acceptAria(RONIT) })).toBeFocused();

  // Esc AGAIN — now from inside — keeps its ordinary meaning: dismiss.
  await page.keyboard.press("Escape");
  await expect(page.getByText(calling(RONIT))).toHaveCount(0);

  // ⚠ BLOCKER 3. On this section there is no `SosCentre`, so without a
  // persistent affordance the dismissal would be total and permanent for a live
  // emergency. It is neither.
  await expect(page.getByRole("button", { name: dismissedCount(1) })).toBeVisible();
});

// --- 4. BLOCKER 3 — escalation re-raises a dismissed card, exactly once ------

test("sos: a dismissed alert re-rises when it escalates, and the re-open affordance restores it", async ({
  page,
}) => {
  const alerts: Reply[] = [ok(sosPayload([]))];
  await installManageApi(page, {
    staff: MANAGER,
    replies: { "/manage/settings": [SETTINGS], "/manage/floor/sos": alerts },
  });

  // Before the page, so the nav is reachable — see the Esc journey above.
  await gotoProfile(page);
  retarget(
    alerts,
    ok(sosPayload([sosAlert({ raised_by_name: RONIT, escalated: false })])),
  );
  await expect(page.getByText(calling(RONIT))).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(ESCALATED)).toHaveCount(0);

  await page.getByRole("button", { name: dismissAria(RONIT) }).click();
  await expect(page.getByText(calling(RONIT))).toHaveCount(0);

  // The affordance restores it by hand at any time — she does not have to wait
  // for the net.
  await page.getByRole("button", { name: dismissedCount(1) }).click();
  await expect(page.getByText(calling(RONIT))).toBeVisible();
  await page.getByRole("button", { name: dismissAria(RONIT) }).click();
  await expect(page.getByText(calling(RONIT))).toHaveCount(0);

  // Nobody came. Thirty seconds later the server derives `escalated` at READ
  // time — no worker, no write, no column.
  retarget(
    alerts,
    ok(sosPayload([sosAlert({ raised_by_name: RONIT, escalated: true })])),
  );

  // ⚠ THE SAFETY NET. The dismiss key is `${id}:${escalated}:${stalled}` and NOT
  // the bare id, so escalation re-rises this card exactly once. With a bare id a
  // shift manager's t=2s dismissal would hide a role-targeted page FOREVER —
  // and in a boutique with one shift manager on the floor that is the whole
  // audience gone on one tap, before the net can fire.
  await expect(page.getByText(calling(RONIT))).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(ESCALATED)).toBeVisible();

  // …and once. A second dismiss silences it again rather than looping.
  await page.getByRole("button", { name: dismissAria(RONIT) }).click();
  await expect(page.getByText(calling(RONIT))).toHaveCount(0);
  await expect(page.getByRole("button", { name: dismissedCount(1) })).toBeVisible();
  await page.waitForTimeout(6_000);
  await expect(page.getByText(calling(RONIT))).toHaveCount(0);
});

// --- 5. BLOCKER 2 — a terminal poll must not kill the channel silently -------

test("sos: a 403 renders the persistent channel-down strip and does NOT drop the console to login", async ({
  page,
}) => {
  await installManageApi(page, {
    staff: MANAGER,
    replies: {
      "/manage/settings": [SETTINGS],
      "/manage/floor/sos": [refuse(403, "FORBIDDEN")],
    },
  });

  await gotoProfile(page);

  // ⚠ «Nothing renders» is not an acceptable state for an emergency receiver
  // that has stopped receiving, and on eleven sections this strip is the ONLY
  // app-level surface that can say so. The spec's original claim — that the
  // login form would appear on the next navigation — was simply FALSE: App.tsx
  // has no fetch interceptor and `onNavigate` is `setSection`.
  const strip = page.getByRole("alert").filter({ hasText: CHANNEL_DOWN });
  await expect(strip).toBeVisible();
  await expect(
    page.getByRole("button", { name: CHANNEL_RELOAD }),
  ).toBeVisible();

  // A 403 is terminal ACCESS, not a dead session: the console keeps working and
  // she is NOT logged out. Only a 401 fires `onSessionEnded`.
  await expect(page.getByRole("button", { name: LOGIN_SUBMIT })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { level: 2, name: PROFILE_HEADING }),
  ).toBeVisible();

  // PERSISTENT — it survives navigation, because the provider is above the
  // shell and the strip is not a toast.
  await page.getByRole("navigation").getByRole("button", { name: NAV_BOARD }).click();
  await expect(strip).toBeVisible();
});

// --- 6. the colour argument, measured rather than asserted -------------------

test("sos: zero axe A/AA violations on the red field with two cards, one escalated", async ({
  page,
}) => {
  await installManageApi(page, {
    replies: {
      "/manage/floor/sos": [
        ok(
          sosPayload([
            sosAlert({
              id: "sos-1",
              raised_by_name: RONIT,
              room_label: "חדר 2",
              note: "צריך סיכות לתחרה",
              target_staff_user_id: SELF_ID,
            }),
            sosAlert({
              id: "sos-2",
              // The ghost raiser: her staff row is gone and the card says so
              // rather than rendering an empty name.
              raised_by_name: null,
              room_label: null,
              created_at: "2099-01-04T07:58:00Z",
              escalated: true,
            }),
          ]),
        ),
      ],
    },
  });

  await page.goto(MANAGE);
  await expect(page.getByText(calling(RONIT))).toBeVisible();
  await expect(page.getByText(calling(RAISER_GONE))).toBeVisible();
  // «לא בחדר מדידה» and «ללא מענה» each render TWICE — once on the overlay card
  // and once on the centre row for the same alert, which is the two surfaces
  // agreeing and is exactly what this scan wants in frame.
  await expect(page.getByText(NO_ROOM)).toHaveCount(2);
  await expect(page.getByText(ESCALATED)).toHaveCount(2);

  // Oldest first on BOTH surfaces, so the two screens can never disagree about
  // which emergency is next.
  const cards = page.locator("article[data-alert-id]");
  await expect(cards).toHaveCount(2);
  await expect(cards.nth(0)).toContainText(calling(RONIT));
  const rows = page.locator("li[data-alert-id]");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText(RONIT);

  // An ABSOLUTE instant, never a countdown — which is what keeps the SC 2.2.2
  // argument true rather than merely claimed.
  await expect(cards.nth(0)).toContainText(/מאז \d\d:\d\d/);

  // ⚠ THE ONLY PLACE THE DECK'S CENTRAL CLAIM IS ACTUALLY MEASURED. «The red is
  // the FIELD; each card is PAPER» rests on four contrast ratios — --color-ink
  // on --color-danger is 2.25:1, `Button danger`'s own fill 1.00:1,
  // --color-surface-raised 7.01:1 — and axe's `color-contrast` rule is SKIPPED
  // ENTIRELY in jsdom, where Tailwind's sheet is never applied. Move the words
  // back onto the red and the unit-suite axe scan stays green while this reds.
  expect(await axeViolations(page)).toEqual([]);
});

// --- 7. the raise: two of four outcomes KEEP the dialog open -----------------

test("sos: a rerouted raise keeps the dialog open, tells her so, and focuses the acknowledgement", async ({
  page,
}) => {
  const held = assignment({ id: "as-1", staff_user_id: SELF_ID });
  const api = await installManageApi(page, {
    replies: {
      "/manage/floor": [
        ok(
          floorPayload({
            staff: [
              staffCard(),
              staffCard({ id: "st-maya", display_name: MAYA, role: "seamstress" }),
            ],
            rooms: [room({ id: "rm-1", label: "חדר 1", assignment: held })],
          }),
        ),
      ],
      "POST /manage/floor/sos": [
        ok(
          raisedAlert(
            sosAlert({
              id: "sos-new",
              raised_by: SELF_ID,
              target_staff_user_id: null,
              target_name: MAYA,
              room_label: "חדר 1",
              // Her OWN page never rises on her own device.
              for_me: false,
            }),
            true,
          ),
        ),
      ],
    },
  });

  await gotoFloor(page);

  // The centre is the quiet state — one muted line, no EmptyState block, and a
  // trigger that all five roles get.
  await expect(page.getByRole("heading", { level: 3, name: CENTRE_HEADING })).toBeVisible();
  await expect(page.getByText(CENTRE_EMPTY)).toBeVisible();

  // ⚠ The tile's control, rendered ONLY on the tile SHE is standing in, and
  // FIRST in the action row — dom order is tab order is wrap order.
  const trigger = page.getByRole("button", { name: raiseAria("חדר 1") });
  await expect(trigger).toBeVisible();
  await trigger.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  // Herself excluded, the shift-manager ROLE first and default.
  await expect(dialog.getByRole("combobox")).toHaveValue("");
  await expect(dialog.getByRole("option", { name: TARGET_MANAGER })).toBeAttached();
  await expect(dialog.getByRole("option", { name: RONIT })).toHaveCount(0);
  await dialog.getByRole("combobox").selectOption("st-maya");

  await dialog.getByRole("button", { name: SEND }).click();

  // ⚠ AC2. The alert IS created and rerouted to the shift manager, and the
  // dialog STAYS OPEN to say so. A page is never silently dropped, and she is
  // never told a named colleague was reached when she was not.
  await expect(dialog.getByText(rerouted(MAYA))).toBeVisible();

  // ⚠ MOVE E, and it is a real-browser fact: «הבנתי» REPLACES the send control,
  // so the element that held focus has just unmounted. Chromium leaves focus on
  // the <dialog> or on <body>; without the move the one message the ruling
  // mandates is unreachable by keyboard.
  const ack = dialog.getByRole("button", { name: REROUTED_ACK });
  await expect(ack).toBeFocused();

  // The body travelled verbatim: the room she is standing in, the colleague she
  // picked, and NO `raised_by` — the acting identity is the session cookie and
  // nothing on this body may stand in for it.
  const sent = api.of("/manage/floor/sos").filter((one) => one.method === "POST");
  expect(sent).toHaveLength(1);
  expect(sent[0].body).toEqual({
    target_staff_user_id: "st-maya",
    fitting_room_assignment_id: "as-1",
    note: null,
  });

  await ack.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // ⚠ MOVE G. `RoomsPanel`'s own MOVE-4 effect is keyed on ITS `openDialog`
  // state, which never changes for a dialog `FloorPanel` owns — so the trigger
  // ELEMENT travels up instead. Chromium's native <dialog> close drops focus to
  // <body>, which is the precondition; jsdom's does not.
  await expect(trigger).toBeFocused();

  // The centre is no longer empty: the raise merged its own alert at once, which
  // is what the paused freeze's raise exemption depends on.
  await expect(page.getByText(CENTRE_EMPTY)).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 2, name: FLOOR_HEADING })).toBeVisible();
});

// --- 8. the harness's own default, and why it is not optional ---------------

test("sos: an unstubbed section still renders no channel-down strip, because the poll is stubbed by default", async ({
  page,
}) => {
  // ⚠ THIS IS A REGRESSION GUARD ON `fixtures/manage.ts`, NOT ON F37. Delete
  // the `/manage/floor/sos` default and the harness answers its house 404 on
  // every tick of every journey in this directory; two failures paint a
  // persistent role="alert" over the bottom of the screen and red every axe
  // scan and every `getByRole("alert")` here and in `manage.spec.ts`.
  await installManageApi(page, { staff: MANAGER, replies: { "/manage/settings": [SETTINGS] } });

  await gotoProfile(page);
  // Three failed ticks' worth of wall clock at the 5s idle gap.
  await page.waitForTimeout(11_000);

  await expect(page.getByText(CHANNEL_DOWN)).toHaveCount(0);
  await expect(page.locator("[data-alert-id]")).toHaveCount(0);
  expect(await axeViolations(page)).toEqual([]);
});
