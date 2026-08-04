import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { ar } from "../i18n/ar";
import { he } from "../i18n/he";
import { GUIDE_STEPS } from "../lib/guide";
import { ROLE_LABEL_KEY } from "../lib/roles";
import { STAGE_LABEL_KEY } from "../lib/stages";

// Console copy is transcribed into he.ts as DOTTED LITERAL keys, one per row of
// the feature's copy.md. i18next resolves those through `ignoreJSONStructure`
// (default true), which falls back to a flat lookup when the nested path misses
// — this suite is the proof, because a silently unresolved key renders the key
// itself into the console.
//
// The bundle also holds the pre-F15 nested namespaces, so each feature's flat
// entries are selected by their own prefix. TWO constants rather than one
// widened filter, deliberately: F15's floor asserts its deck is whole, and
// folding F51's ~29 keys into the same list would let F15's 76 rows shrink by 29
// and still pass — a guard that quietly stops guarding.
function entries(bundle: object, match: (key: string) => boolean): [string, string][] {
  return Object.entries(bundle).filter(
    (entry): entry is [string, string] => match(entry[0]) && typeof entry[1] === "string",
  );
}

const HE_F15 = entries(
  he.translation,
  (key) => key === "nav.bookings" || key.startsWith("booking."),
);
const HE_F51 = entries(he.translation, (key) => key === "nav.staff" || key.startsWith("staff."));
const HE_F52 = entries(
  he.translation,
  (key) => key === "nav.dashboard" || key.startsWith("dashboard."),
);
// Folded in, not just declared: without this the resolve check, BOTH register
// guards and the `ar` parity guard silently skip every F52 key.
// F17 gets its own constant for the reason the comment above gives: folding
// these into an existing list would let that feature's rows shrink by this many
// and still pass. Every block keeps its own floor.
const HE_F17 = entries(he.translation, (key) => key === "nav.gateway" || key.startsWith("gateway."));
const HE_F34 = entries(he.translation, (key) => key === "nav.board" || key.startsWith("board."));
// F57. Its three `staff.role*` keys are deliberately NOT selected here — they
// are `staff.`-namespaced and ride in HE_F51, which is where they belong: the
// namespace names the payload, not the feature that added the key.
const HE_F57 = entries(he.translation, (key) => key === "nav.floor" || key.startsWith("floor."));
const HE_F53 = entries(
  he.translation,
  (key) => key === "nav.customers" || key.startsWith("customers."),
);
// F33's printable check-in code. Its own constant and its own floor, for the
// reason the comment above gives — folded into an existing list, that feature's
// rows could shrink by this many and still pass.
const HE_F33 = entries(
  he.translation,
  (key) => key === "nav.checkinQr" || key.startsWith("checkinQr."),
);
// F36. NO `nav.` term in this selector, and that is an assertion rather than an
// omission — the rooms are content of the floor, not a twelfth console section,
// so F36 adds no nav row. `floor.statusOccupied` is likewise absent: it is
// `floor.`-namespaced and rides in HE_F57 by prefix, inheriting that block's
// digit guard and its `> 28` floor for free.
const HE_F36 = entries(he.translation, (key) => key.startsWith("rooms."));
// F58. No `nav.` term either, and for the same reason F36 has none: the queue is
// CONTENT of the floor, not a thirteenth console section, so F58 adds no nav
// row. Its five `rooms.*` keys are likewise absent — the namespace names the
// surface, not the feature that added the key (see the HE_F57 comment), so they
// ride in HE_F36 by prefix and inherit its digit guard, its 2.5.3 loop and its
// `ar`-value guard for free.
const HE_F58 = entries(he.translation, (key) => key.startsWith("waitlist."));
// F41's atelier. Its own constant and its own floor, same reason again.
const HE_F41 = entries(
  he.translation,
  (key) => key === "nav.atelier" || key.startsWith("atelier."),
);
// F37's SOS page. NO `nav.` term in this selector either, and here that is the
// sharpest assertion in the file: an alert is an INTERRUPTION, not a
// destination, so F37 adds no console section and no nav row (spec D11).
const HE_F37 = entries(he.translation, (key) => key.startsWith("sos."));
// F60's guided walkthrough. NO `nav.` term in this selector either, and that is
// an assertion rather than an omission: the guide adds no console section and no
// nav row — `SectionKey` stays fourteen, `NAV` stays fourteen, `Nav.test.tsx`
// needs no edit — and `guide.trigger` is a header control beside «יציאה», not
// `nav.guide`.
const HE_F60 = entries(he.translation, (key) => key.startsWith("guide."));
const HE = [
  ...HE_F15,
  ...HE_F51,
  ...HE_F52,
  ...HE_F17,
  ...HE_F34,
  ...HE_F57,
  ...HE_F53,
  ...HE_F33,
  ...HE_F36,
  ...HE_F58,
  ...HE_F41,
  ...HE_F37,
  ...HE_F60,
];

describe("F15 keys resolve", () => {
  it("carries the whole copy deck", () => {
    expect(HE_F15.length).toBeGreaterThan(70);
  });

  it("resolves every dotted literal key to its own Hebrew", () => {
    for (const [key, value] of HE) {
      expect(i18n.t(key)).toBe(value);
    }
  });

  it("resolves the nav item beside the nested nav object it sits next to", () => {
    expect(i18n.t("nav.bookings")).toBe("תורים");
    expect(i18n.t("nav.catalog")).toBe("שמלות");
  });

  it("resolves a three-segment error key", () => {
    expect(i18n.t("booking.error.SLOT_UNAVAILABLE")).toBe("המועד הזה נתפס הרגע. אפשר לבחור מועד אחר.");
  });

  it("interpolates the count, version and phone placeholders", () => {
    expect(i18n.t("booking.dayCount", { count: 3 })).toBe("תורים ביום זה: 3");
    expect(i18n.t("booking.termsVersion", { version: 2 })).toBe("גרסה 2");
    expect(i18n.t("booking.phoneModalBody", { phone: "+972501234567" })).toContain(
      "המספר שהוזן: +972501234567.",
    );
  });
});

describe("F51 staff keys resolve", () => {
  it("carries the whole copy deck", () => {
    expect(HE_F51.length).toBeGreaterThan(25);
  });

  it("resolves the seventh nav item beside the nested nav object", () => {
    expect(i18n.t("nav.staff")).toBe("צוות");
  });

  it("resolves the four error codes the section maps to Hebrew", () => {
    for (const code of [
      "DUPLICATE_EMAIL",
      "LAST_OWNER_REQUIRED",
      "STAFF_SELF_MANAGE",
      "NOT_AUTHORIZED",
    ]) {
      const key = `staff.error.${code}`;
      expect(i18n.t(key)).not.toBe(key);
    }
  });

  it("interpolates the deactivated staffer's name into the confirm body", () => {
    expect(i18n.t("staff.deactivateBody", { name: "דנה" })).toContain("דנה");
  });
});

describe("F52 dashboard keys resolve", () => {
  it("carries the whole copy deck", () => {
    expect(HE_F52.length).toBeGreaterThan(40);
  });

  it("resolves the eighth nav item beside the nested nav object", () => {
    expect(i18n.t("nav.dashboard")).toBe("סקירה");
  });

  it("resolves the three strings that keep zero, unknown and too-small apart", () => {
    // Three facts, three strings (copy.md §0 rule 3). `0.0%` is rendered
    // arithmetic and has no key; these two are the other two facts, and a
    // screen that collapsed them would tell a boutique it had no cancellations
    // when it had one.
    expect(i18n.t("dashboard.notEnoughData")).toBe("אין עדיין מספיק נתונים לחישוב.");
    expect(i18n.t("dashboard.rateUnderFloor")).toBe("פחות מ־0.1%");
  });

  it("interpolates the announced total through the base key", () => {
    // {{count}} is i18next's plural trigger. It resolves through the base key
    // because no dashboard.summary_one/_other exist — the shape booking.dayCount
    // already ships. Suffixed variants must NOT be added: Hebrew's dual would
    // then need a third and the announced sentence would fork.
    expect(i18n.t("dashboard.summary", { count: 23 })).toBe("סך התורים שלא בוטלו בתקופה: 23");
  });
});

describe("F17 gateway keys resolve", () => {
  it("carries the whole block", () => {
    expect(HE_F17.length).toBeGreaterThan(25);
  });

  it("resolves the ninth nav item beside the nested nav object", () => {
    expect(i18n.t("nav.gateway")).toBe("סליקה ותשלומים");
  });

  it("resolves the five error codes the section maps to Hebrew", () => {
    for (const code of [
      "GATEWAY_CREDENTIALS_REJECTED",
      "GATEWAY_NOT_CONFIGURED",
      "GATEWAY_NOT_CONNECTED",
      "GATEWAY_UNAVAILABLE",
      "TOO_MANY_ATTEMPTS",
    ]) {
      const key = `gateway.error.${code}`;
      expect(i18n.t(key)).not.toBe(key);
    }
  });

  it("resolves a field label but MISSES an unkeyed field name", () => {
    // Both halves. The miss is what GatewaySection's fallback branches on, and
    // asserting it here keeps that branch reachable — but the RENDERING of the
    // fallback (<bdi dir="ltr" lang="en">) is GatewaySection.test.tsx's job:
    // this suite cannot see a key it never renders.
    expect(i18n.t("gateway.field.api_key")).toBe("מפתח API");
    expect(i18n.t("gateway.field.store_id")).toBe("gateway.field.store_id");
  });
});

describe("F34 board keys resolve", () => {
  it("carries the whole copy deck", () => {
    // 34 rows: nav.board plus 33 under board.* (copy.md:30).
    expect(HE_F34.length).toBeGreaterThanOrEqual(34);
  });

  it("resolves the tenth nav item beside the nested nav object", () => {
    expect(i18n.t("nav.board")).toBe("לוח היום");
  });

  it("resolves the one error string the board owns", () => {
    // F-2: F15's BOOKING_TRANSITION_INVALID Hebrew tells the owner to go back to
    // a list this screen does not have. The board owns a replacement for that
    // one code and delegates every other code to bookingErrorText unchanged.
    expect(i18n.t("board.error.transitionInvalid")).toBe(
      "מצב התור השתנה. השורה תתוקן בעדכון הבא.",
    );
  });

  it("names no retry interval anywhere (§0 rule 9)", () => {
    // D4(6) stretches the retry 5s -> ~60s, so any string quantifying the wait
    // becomes a lie the board silently stops keeping. «מיד» is the word that
    // was removed; the stale copy states what is unknown, never when.
    //
    // Whole words, not substrings: «מידע» (information) contains «מיד» and is
    // the legitimate word in board.staleBody. A naive /מיד/ fails the one string
    // this rule was written to protect, which is the wrong way round.
    for (const [, value] of HE_F34) {
      expect(value).not.toMatch(/(^|[\s"«])(מיד|שניות|חמש)([\s".,»]|$)/);
    }
  });

  it("keeps the 403 body generic — no role, and nothing about what changed", () => {
    const body = i18n.t("board.accessEnded");
    expect(body).toBe("אין הרשאה לצפות בלוח כרגע. לבירור אפשר לפנות לבעלת הבוטיק.");
    // §0 rule 10: the server ships ONE 403 body for every unadmitted role
    // (auth/dependencies.py:17-21) so a probe cannot learn which roles exist.
    // The client therefore may not say which role she now holds, nor that
    // anything changed — and on the demotion path, telling a staffer she was
    // demoted is her manager's sentence to say, not a screen's. «בעלת הבוטיק»
    // is who to ask, which is the one thing the screen can honestly offer.
    for (const word of ["אחראית משמרת", "תפקיד", "בוטלו", "הוסרה", "שונה"]) {
      expect(body).not.toContain(word);
    }
    // «כרגע» is load-bearing: a re-promotion restores the board, so a sentence
    // implying the door is shut for good would be a guess the server never made.
    expect(body).toContain("כרגע");
  });

  it("interpolates the freshness, ratio and idle-window placeholders", () => {
    expect(i18n.t("board.updatedAt", { time: "14:07" })).toBe("עודכן 14:07");
    expect(i18n.t("board.staleAt", { time: "14:07" })).toBe("אין עדכון מאז 14:07");
    expect(i18n.t("board.pausedAt", { time: "14:07" })).toBe("מושהה · עודכן 14:07");
    expect(i18n.t("board.summary", { ratio: "3/12" })).toBe("הגיעו 3/12");
    expect(i18n.t("board.idleStopped", { minutes: 10 })).toContain("10");
  });

  it("spells the arrival FACT differently from the arrival VERB", () => {
    // P-7. «לא הגיעה» is a shipped status word, so the button is its exact
    // positive and the record is spelled apart from both — a booking marked
    // no_show after a check-in must read as two true facts, not a contradiction.
    expect(i18n.t("board.checkIn")).toBe("הגיעה");
    expect(i18n.t("booking.statusNoShow")).toBe("לא הגיעה");
    expect(i18n.t("board.checkedInAt", { time: "09:24" })).toBe("נרשמה הגעה · 09:24");
  });

  it("starts each accessible name with its visible label (WCAG 2.5.3)", () => {
    expect(i18n.t("board.pauseAria")).toMatch(new RegExp(`^${i18n.t("board.pause")}`));
    expect(i18n.t("board.resumeAria")).toMatch(new RegExp(`^${i18n.t("board.resume")}`));
    expect(i18n.t("board.checkInAria", { name: "מיכל לוי", time: "09:30" })).toMatch(
      new RegExp(`^${i18n.t("board.checkIn")}`),
    );
    expect(i18n.t("board.undoAria", { name: "מיכל לוי", time: "09:30" })).toMatch(
      new RegExp(`^${i18n.t("board.undo")}`),
    );
  });
});

describe("F53 customers keys resolve", () => {
  it("carries the whole copy deck", () => {
    // 52 rows: nav.customers plus 51 under customers.*.
    expect(HE_F53.length).toBeGreaterThanOrEqual(49);
  });

  it("is FOLDED into HE, not merely declared", () => {
    // Declaring the constant and forgetting the spread is the failure the
    // comment above HE_F17 records: the resolve check, both register guards and
    // the `ar` parity guard would all silently skip every key in this block and
    // stay green. Nothing else in this file notices — so this asserts the fold
    // itself rather than trusting it.
    expect(HE.map(([key]) => key)).toContain("nav.customers");
  });

  it("resolves the eleventh nav item beside the nested nav object", () => {
    expect(i18n.t("nav.customers")).toBe("לקוחות");
  });

  it("names the log a LOG and not a send history", () => {
    // The heading is the one string that decides what the panel claims to be.
    // «היסטוריית הודעות» would read as a delivery record; the log is a record
    // of what this product ASKED a provider to send, which is a different fact
    // — and the register guard below only catches the verb, not the noun.
    expect(i18n.t("customers.messagesHeading")).toBe("יומן הודעות");
  });

  it("resolves every message kind and status the log renders", () => {
    // The section maps MessageKind/MessageStatus through these; an unresolved
    // key would render `customers.messageKindOtp` into a cell and no other
    // assertion in the suite would see it.
    for (const suffix of [
      "KindOtp",
      "KindConfirmation",
      "KindReminder",
      "KindOwnerCancel",
      "KindOwnerReschedule",
      "StatusQueued",
      "StatusSent",
      "StatusFailed",
    ]) {
      const key = `customers.message${suffix}`;
      expect(i18n.t(key)).not.toBe(key);
    }
  });

  it("starts the tag-remove accessible name with its visible label (WCAG 2.5.3)", () => {
    expect(i18n.t("customers.tagRemoveAria", { tag: "כלה" })).toMatch(
      new RegExp(`^${i18n.t("customers.tagRemove")}`),
    );
  });

  it("keeps the 403 body generic — no role, and nothing about what changed", () => {
    const body = i18n.t("customers.error.NOT_AUTHORIZED");
    // The same rule F34's board body follows: the server ships ONE 403 body for
    // every unadmitted role so a probe cannot learn which roles exist, and a
    // screen may not say which role the reader now holds.
    for (const word of ["אחראית משמרת", "תפקיד", "בוטלו", "הוסרה", "שונה"]) {
      expect(body).not.toContain(word);
    }
    // «כרגע» is load-bearing: a re-promotion restores access.
    expect(body).toContain("כרגע");
  });
});

// copy.md §0 rules 1 and 2, mechanically. For F15 rule 2 discharged a swallowed
// send-error risk; for F51 it is literally true — there is no mailer and no SMS
// sender ID, so the owner speaks the password herself and no string may hint
// otherwise. That is why the notice is phrased «יש למסור…» and not «אינה
// נשלחת…»: the latter contains נשלח and would trip this guard, and a copy deck
// that has to dodge its own guard is copy that is one edit away from lying.
describe("F57 floor keys resolve", () => {
  it("carries the whole copy deck", () => {
    // 30 `floor.*` keys plus `nav.floor`; the other three of the deck's 32 are
    // `staff.role*` and land in HE_F51. The thirtieth is F36's
    // `floor.statusOccupied` — the namespace names the payload, not the feature
    // that added the key, so it rides here by prefix.
    expect(HE_F57.length).toBeGreaterThan(28);
  });

  it("resolves the eleventh nav item beside the nested nav object", () => {
    expect(i18n.t("nav.floor")).toBe("הצוות בקומה");
  });

  it("resolves every role label the record names", () => {
    // The Record<StaffRole, string> type catches a MISSING MEMBER at compile
    // time; this catches a member pointing at a key that does not exist, which
    // types cannot see. Both halves are needed — a seamstress rendering the raw
    // slug and a seamstress rendering «אחראית משמרת» are different bugs.
    for (const key of Object.values(ROLE_LABEL_KEY)) {
      expect(i18n.t(key)).not.toBe(key);
    }
    expect(i18n.t(ROLE_LABEL_KEY.seamstress)).toBe("תופרת");
    expect(i18n.t(ROLE_LABEL_KEY.reception)).toBe("קבלה");
    expect(i18n.t(ROLE_LABEL_KEY.sales_assistant)).toBe("יועצת מכירות");
  });

  it("keeps the pause control's accessible name containing its visible label", () => {
    // WCAG 2.5.3 label-in-name, and the reason the deck overrode spec D12's
    // «השהיית עדכון הצוות»: a speech-input user saying the visible «השהיה»
    // must match. Asserted rather than trusted, because the two word forms
    // differ by one letter and a later copy edit would not look wrong.
    expect(i18n.t("floor.pauseAria")).toContain(i18n.t("floor.pause"));
    expect(i18n.t("floor.resumeAria")).toContain(i18n.t("floor.resume"));
  });

  it("names its own region in the idle notice, unlike the board's", () => {
    // Both write into a role="status" region and both idle windows reset
    // together, so on the board screen a screen-reader user would otherwise
    // hear one sentence twice (design.md §9 F-4).
    const floor = i18n.t("floor.idleStopped", { minutes: 10 });
    expect(floor).not.toBe(i18n.t("board.idleStopped", { minutes: 10 }));
    expect(floor).toContain("הצוות");
  });

  it("interpolates the colleague's name into both toggle labels and both cues", () => {
    for (const key of [
      "floor.breakStartAria",
      "floor.breakEndAria",
      "floor.breakStartedCue",
      "floor.breakEndedCue",
    ]) {
      expect(i18n.t(key, { name: "נועה לוי" })).toContain("נועה לוי");
    }
  });

  it("does not ship floor.outage — the shipped staff.loadFailed is reused", () => {
    // design.md §9 F-10. The precedent this sets for F37/F41/F42/F59: reuse a
    // key whose NAMESPACE NAMES ITS SUBJECT, never one whose namespace names a
    // screen. `staff.loadFailed` is one sentence about the staff list, which is
    // exactly what this panel failed to load.
    expect("floor.outage" in he.translation).toBe(false);
    expect(i18n.t("staff.loadFailed")).toBe("לא הצלחנו לטעון את רשימת הצוות כרגע.");
  });

  it("names no retry interval anywhere in the deck", () => {
    // copy.md §0 rule 9: the backoff falsifies any number the moment it doubles.
    // `floor.idleStopped` carries {{minutes}}, which is the IDLE window and not
    // a retry interval, so it is excluded by key rather than by pattern.
    const values = HE_F57.filter(([key]) => key !== "floor.idleStopped").map(([, value]) => value);
    expect(values.filter((value) => /\d/.test(value))).toEqual([]);
  });

  it("names no role in the access-ended sentence", () => {
    // copy.md §0 rule 10, and for the three floor roles this sentence is the
    // entire product going dark — naming the role would teach the permission
    // model at the worst possible moment.
    const accessEnded = i18n.t("floor.accessEnded");
    for (const word of ["קבלה", "יועצת מכירות", "תופרת", "אחראית משמרת"]) {
      expect(accessEnded).not.toContain(word);
    }
  });
});

describe("F36 fitting-room keys resolve", () => {
  it("carries the whole copy deck", () => {
    // copy.md's 68 `rooms.*` rows plus DC-8's two paused variants of the two
    // 404s. `floor.statusOccupied` is the deck's sixty-ninth key and is NOT
    // counted here — it rides in HE_F57 by prefix.
    //
    // ⚠ 71 today, and F58 adds FIVE: the tile's «קחי את הבאה» plus its aria,
    // `rooms.error.QUEUE_EMPTY`, and DC-3's two self-form STAFF_OCCUPIED
    // sentences. The floor moves to 76 — spec D16 says the namespace gains one
    // key and design.md F-6 says three; both are wrong, in different
    // directions, and the count is what settles it.
    expect(HE_F36.length).toBeGreaterThanOrEqual(76);
  });

  it("is FOLDED into HE, not merely declared", () => {
    // ⚠ Declaring the constant and forgetting the spread is the failure the
    // comment above HE_F17 records, and for this block it is the whole of the
    // design critic's DC-3: without the fold the resolve check, BOTH register
    // guards and the `ar` guards silently skip all seventy hand-transcribed
    // strings and stay green. Nothing else in this file notices.
    expect(HE.map(([key]) => key)).toContain("rooms.heading");
  });

  it("adds no nav row, and that is an assertion rather than an omission", () => {
    // The rooms are content of the floor, not a destination: F36 adds no
    // console section, no route and no nav item (spec D15). Every other
    // feature's selector opens `key === "nav.x" || …`; this one does not, and
    // this is the one-line proof that the omission was chosen.
    expect(HE_F36.filter(([key]) => key.startsWith("nav."))).toEqual([]);
    expect("nav.rooms" in he.translation).toBe(false);
  });

  it("names no literal digit anywhere in the namespace", () => {
    // DC-3. The shipped guard at the end of the F57 block is `HE_F57`-scoped,
    // so before this line there was NO digit guard over `rooms.*` at all and
    // copy.md §11's «0» row for rule 4 was a hand-count wearing a citation.
    // No exemption is needed: every number on this panel is an interpolation,
    // and a literal one would be a retry interval or a server-owned limit the
    // screen cannot keep true.
    const values = HE_F36.map(([, value]) => value);
    expect(values.filter((value) => /\d/.test(value))).toEqual([]);
  });

  it("starts each accessible name with its visible label (WCAG 2.5.3)", () => {
    // Five tiles all offering a button named «שחרור» is a screen-reader dead
    // end, so each *Aria appends the room (or the dress) after an em-dash — but
    // it must still OPEN with the visible word, or a speech-input user saying
    // what she can see matches nothing.
    // F58 adds "takeNext" to this SHIPPED loop rather than writing a parallel
    // one, which is the whole mechanical argument for keeping the tile's two
    // new strings in `rooms.*` (design.md F-6).
    for (const name of ["claim", "release", "handover", "addDress", "takeNext"]) {
      expect(i18n.t(`rooms.${name}Aria`, { room: "חדר 2" })).toMatch(
        new RegExp(`^${i18n.t(`rooms.${name}`)}`),
      );
    }
    expect(i18n.t("rooms.removeDressAria", { dress: "ורוניק" })).toMatch(
      new RegExp(`^${i18n.t("rooms.removeDress")}`),
    );
  });

  it("spells the ROOM's occupancy masculine and the STAFFER's feminine", () => {
    // Two different subjects one line apart. «תפוס» agrees with «חדר» and
    // «תפוסה» with a woman; collapsing them into one word would make the tile
    // and the card look like one fact inflected by accident.
    expect(i18n.t("rooms.free")).toBe("פנוי");
    expect(i18n.t("rooms.occupied")).toBe("תפוס");
    expect(i18n.t("floor.statusOccupied")).toBe("תפוסה");
    expect(i18n.t("floor.statusAvailable")).toBe("פנויה");
  });

  it("ships a paused variant of both 404s that promises no next update", () => {
    // DC-8. `pause()` stops the loop and nothing else — a claim stays fully
    // available while paused — so «הרשימה תתוקן בעדכון הבא» is a promise the
    // screen will not keep. §0 rule 4 was written against durations; this is
    // the same failure in the EVENT form. The paused pair points at «חידוש»,
    // which is the control that is actually on screen.
    for (const key of ["rooms.error.notFound", "rooms.error.assignmentGone"]) {
      expect(i18n.t(key)).toContain("בעדכון הבא");
      expect(i18n.t(`${key}Paused`)).not.toContain("בעדכון הבא");
      expect(i18n.t(`${key}Paused`)).toContain(i18n.t("floor.resume"));
    }
  });

  it("gives each 409 code a sentence AND an unknown-occupant twin", () => {
    // `details` is optional on both codes, so each needs two strings: the
    // occupant can release between the index violation and the occupant read,
    // and «{{name}} כבר בחדר הזה.» rendering with an empty interpolation on a
    // legally binding surface is worse than a sentence that admits it does not
    // know.
    expect(i18n.t("rooms.error.ROOM_OCCUPIED", { name: "דנה" })).toContain("דנה");
    expect(i18n.t("rooms.error.STAFF_OCCUPIED", { room: "חדר 5" })).toContain("חדר 5");
    expect(i18n.t("rooms.error.deleteOccupied", { name: "דנה" })).toContain("דנה");
    for (const key of [
      "rooms.error.roomOccupiedUnknown",
      "rooms.error.staffOccupiedUnknown",
      "rooms.error.deleteOccupiedUnknown",
    ]) {
      expect(i18n.t(key)).not.toContain("{{");
    }
    // The unknown-occupant form is a strict PREFIX of the named one, so the two
    // can never read as two different facts.
    expect(i18n.t("rooms.error.STAFF_OCCUPIED", { room: "חדר 5" })).toContain(
      i18n.t("rooms.error.staffOccupiedUnknown").replace(/\.$/, ""),
    );
  });
});

describe("F33 check-in QR keys resolve", () => {
  it("carries the whole block", () => {
    // nav.checkinQr plus nine under checkinQr.*.
    expect(HE_F33.length).toBeGreaterThanOrEqual(10);
  });

  it("resolves the thirteenth nav item beside the nested nav object", () => {
    expect(i18n.t("nav.checkinQr")).toBe("קוד סריקה");
  });

  it("keeps the image's alt distinct from every string printed beside it", () => {
    // The alt sits on a poster next to the poster line, the address label and
    // the fallback hint. An alt that repeats adjacent visible text makes a
    // screen reader say the same sentence twice and describes nothing — and axe
    // has no rule for it, because every individual string is present and
    // non-empty. This is the only place that can catch it.
    const alt = i18n.t("checkinQr.imageAlt");
    expect(alt).not.toBe("");
    for (const key of ["checkinQr.posterLine", "checkinQr.urlLabel", "checkinQr.urlHint"]) {
      expect(alt).not.toBe(i18n.t(key));
    }
  });

  it("promises no message anywhere in the block", () => {
    // F33 sends nothing. F20 adds the queue SMS; until it lands, a string
    // hinting at one is a promise the product cannot keep to a woman who has
    // just handed over her phone number. The global guard below covers the
    // folded HE list; this states the rule where the block is read.
    for (const [, value] of HE_F33) {
      expect(value).not.toMatch(/נשלח|תישלח|בדרך|SMS|הודעה/);
    }
  });
});

describe("F58 waitlist keys resolve", () => {
  it("carries the whole copy deck", () => {
    // copy.md's 37 `waitlist.*` rows. The deck's other five keys are `rooms.*`
    // and are counted by HE_F36's floor above, not here.
    expect(HE_F58.length).toBeGreaterThanOrEqual(37);
  });

  it("is FOLDED into HE, not merely declared", () => {
    // ⚠ On THIS feature the fold is load-bearing twice. Declaring the constant
    // and forgetting the spread is the failure the comment above HE_F17
    // records — the resolve check, BOTH register guards and the `ar` parity
    // guard would silently skip all thirty-seven hand-transcribed strings — and
    // the send-ban below is the guard that actually BIT here: spec D16's
    // `waitlist.calledCue` was «נשלחה קריאה.», which contains the banned root
    // and is also false, because `call` stamps a timestamp and F58 sends
    // nothing to anybody.
    expect(HE.map(([key]) => key)).toContain("waitlist.heading");
  });

  it("adds no nav row, and that is an assertion rather than an omission", () => {
    // The queue is content of the floor, not a destination: F58 adds no console
    // section, no route and no nav item (spec D15).
    expect(HE_F58.filter(([key]) => key.startsWith("nav."))).toEqual([]);
    expect("nav.waitlist" in he.translation).toBe(false);
    expect("nav.queue" in he.translation).toBe(false);
  });

  it("names no literal digit anywhere in the namespace", () => {
    // Every number on this panel is an interpolation — the position, the wait
    // minutes and the skip count all arrive from the payload — so no exemption
    // is needed. A literal digit here would be a retry interval or the server's
    // own LIMIT 100, and the screen can keep neither true.
    const values = HE_F58.map(([, value]) => value);
    expect(values.filter((value) => /\d/.test(value))).toEqual([]);
  });

  it("starts each accessible name with its visible label (WCAG 2.5.3)", () => {
    // DC-1. Forty rows all offering a button named «דלגי» is a screen-reader
    // dead end, so each *Aria appends the customer after an em-dash — but it
    // must still OPEN with the visible word, or a speech-input user saying what
    // she can see matches nothing at all. FOUR of spec D16's five proposals
    // failed this, and «הסרת {{name}} מהתור» failed on a different WORD FORM
    // from «הסרה», which is the version she cannot recover from.
    for (const name of ["call", "assign", "skip", "remove"]) {
      expect(i18n.t(`waitlist.${name}Aria`, { name: "נועה בר" })).toMatch(
        new RegExp(`^${i18n.t(`waitlist.${name}`)}`),
      );
    }
  });

  it("gives the NOT_WAITING 409 three sentences, one per remedy", () => {
    // design.md F-5. D12 gives one code two Hebrew sentences and D16 declares
    // one key; the remedies differ (go and find her in a fitting room / there
    // is nothing to do), and `details` is optional on the wire, so F36's
    // *Unknown precedent adds the third.
    expect(i18n.t("waitlist.error.QUEUE_TICKET_NOT_WAITING")).toBe("היא כבר בטיפול.");
    expect(i18n.t("waitlist.error.ticketClosed")).toBe("הכניסה הזו נסגרה.");
    expect(i18n.t("waitlist.error.ticketNotWaitingUnknown")).toBe("הכניסה הזו כבר לא ממתינה.");
  });

  it("ships a paused twin of every sentence that promises a next update", () => {
    // DC-8, inherited. pause() stops the loop and NOTHING else — every verb on
    // this panel stays fully available while paused — so «הרשימה תתוקן בעדכון
    // הבא» is then a promise the screen will not keep. The paused pair points at
    // «חידוש», the control that IS on screen.
    for (const key of ["waitlist.error.notFound", "waitlist.error.QUEUE_TICKET_CHANGED"]) {
      expect(i18n.t(key)).toContain("בעדכון הבא");
    }
    for (const key of [
      "waitlist.error.notFoundPaused",
      "waitlist.error.queueTicketChangedPaused",
    ]) {
      expect(i18n.t(key)).not.toContain("בעדכון הבא");
      expect(i18n.t(key)).toContain(i18n.t("floor.resume"));
    }
  });

  it("names the ACT in every cue and NEVER a customer", () => {
    // copy.md §7 and the deck's sharpest privacy line. The region is PERSISTENT
    // — FloorPanel's <p role="status"> is overwritten only by the next cue and
    // cleared by nothing — so «נועה הוסרה מהתור.» would sit in a five-role
    // screen's DOM after her row has left the payload AND after she has left the
    // shop, making the cue the only place her name survives. D16 put a customer
    // in all four.
    for (const key of [
      "waitlist.calledCue",
      "waitlist.skippedCue",
      "waitlist.removedCue",
      "waitlist.dispatchedCue",
    ]) {
      expect(he.translation[key as keyof typeof he.translation]).not.toContain("{{name}}");
    }
    // The one interpolation among the four is a ROOM label.
    expect(i18n.t("waitlist.dispatchedCue", { room: "חדר 2" })).toBe("הלקוחה שובצה: חדר 2.");
  });

  it("spells the bride arm the way the form she filled in spells it", () => {
    // ⚠ CORRECTS D16's «שמלת כלה», which would be a THIRD spelling of a
    // two-value enum. The storefront check-in form labels this arm «מדידת כלה»,
    // and a manager reading a different word beside a customer who ticked that
    // one has no way to know they are the same fact. The two apps have separate
    // bundles, so the key cannot be shared; the VALUE must agree.
    expect(i18n.t("waitlist.visitBride")).toBe("מדידת כלה");
    expect(i18n.t("waitlist.visitEvening")).toBe("שמלת ערב");
  });

  it("keeps the tile's empty-queue alert one full stop away from the panel's own", () => {
    // A deliberate near-duplicate and not a miss (copy.md §11): the alert
    // answers her tap and the EmptyState one panel below answers the screen, so
    // one fact gets one vocabulary in two registers rather than two sentences.
    expect(i18n.t("rooms.error.QUEUE_EMPTY")).toBe(`${i18n.t("waitlist.empty")}.`);
  });

  it("gives the dispatch verbs a SELF form of the staff-occupied 409", () => {
    // DC-3 / C13. The shipped third-person «היא כבר בחדר אחר: {{room}}.» is
    // asserted verbatim in RoomsPanel.test.tsx, RoomHandoverDialog.test.tsx and
    // this file, so editing its value reds four shipped assertions — hence two
    // NEW keys rather than the two-line he/ar edit the critic asked for. A
    // take-next or a push-assign carries no target staffer, so the refusal is
    // about the caller herself and «היא» would name nobody on screen.
    expect(i18n.t("rooms.error.staffOccupiedSelf", { room: "חדר 5" })).toBe(
      "את כבר בחדר אחר: חדר 5.",
    );
    expect(i18n.t("rooms.error.staffOccupiedSelfUnknown")).toBe("את כבר בחדר אחר.");
    // The shipped third-person pair is UNTOUCHED.
    expect(i18n.t("rooms.error.STAFF_OCCUPIED", { room: "חדר 5" })).toBe("היא כבר בחדר אחר: חדר 5.");
  });
});

describe("F41 atelier keys resolve", () => {
  it("carries the whole copy deck", () => {
    // 94 rows: nav.atelier plus 93 under atelier.*. copy.md counts 96; the plan
    // subtracts four and adds two. Out: `form.dress` and `form.dressNone` (C3
    // — the catalog picker is cut, there is no payload for it and its route
    // refuses a seamstress), `form.error.dueDateHorizon` (C5 — 730 is a
    // SERVER bound and no client constant may mirror one), and
    // `form.existingCustomer`, REMOVED AT REVIEW: the returning-customer notice
    // needs the STORED name before submit, which needs a lookup, and the plan
    // forbids a new endpoint while the whole customers router refuses the
    // seamstress this dialog admits. It shipped declared and never rendered in
    // two locales, which reads to the next reviewer as evidence the mitigation
    // exists. The rename is audited instead (`atelier_customer_renamed`). In:
    // `error.rejected`, the default branch that keeps main.py's English 400
    // body out of a Hebrew console, and `form.error.server`, the dialog-level
    // alert §7.3 specifies and no deck declares.
    expect(HE_F41.length).toBeGreaterThanOrEqual(94);
  });

  it("is FOLDED into HE, not merely declared", () => {
    // The same assertion F53 added, for the same reason: `HE` is a
    // hand-assembled union and FOUR shipped guards iterate it — the resolve
    // check, both register guards and the `ar` parity guard. A block declared
    // and not spread is skipped silently and greenly, and the parity guard
    // would pass over 95 missing `ar` keys.
    expect(HE.map(([key]) => key)).toContain("nav.atelier");
  });

  it("resolves the fourteenth NAV row's label beside the nested nav object", () => {
    expect(i18n.t("nav.atelier")).toBe("תפירה");
  });

  it("resolves the five stage words the columns, the rail and the cues are named by", () => {
    // The words themselves, not merely that the keys resolve: these five are
    // spec-APPROVED values and they are the product's vocabulary for the
    // state machine. `atelier.emptyBody` teaches all five in one sentence and
    // must not drift from them.
    expect(i18n.t("atelier.stage.intake")).toBe("התקבל");
    expect(i18n.t("atelier.stage.inProgress")).toBe("בעבודה");
    expect(i18n.t("atelier.stage.qc")).toBe("בקרה");
    expect(i18n.t("atelier.stage.ready")).toBe("מוכן");
    // NOT «נשלח» — nothing is shipped, she collects — and the register guard
    // below would reject it outright.
    expect(i18n.t("atelier.stage.delivered")).toBe("נמסר");
    const body = i18n.t("atelier.emptyBody");
    for (const stage of ["intake", "inProgress", "qc", "ready", "delivered"]) {
      expect(body).toContain(i18n.t(`atelier.stage.${stage}`));
    }
    // And through the map the board actually reads, so a key present here but
    // absent from `lib/stages.ts` — or the reverse — is caught. The
    // `Record<TicketStage, string>` type catches a MISSING MEMBER; only this
    // catches a member pointing at a key that does not exist.
    for (const key of Object.values(STAGE_LABEL_KEY)) {
      expect(i18n.t(key)).not.toBe(key);
    }
  });

  it("starts every accessible name with its visible label (WCAG 2.5.3)", () => {
    // Twelve pairs, not four. A board of 30 cards otherwise exposes 30 controls
    // all named «לשלב הבא» — but the name that disambiguates them must still
    // BEGIN with the visible string, or a speech-input user saying the label
    // matches nothing. `floor.pauseAria` is «השהיה — …» and not «השהיית…» for
    // exactly this reason, and the two word forms differ by one letter, so a
    // later copy edit would not look wrong.
    const pairs: [string, string][] = [
      ["atelier.pause", "atelier.pauseAria"],
      ["atelier.resume", "atelier.resumeAria"],
      ["atelier.advance", "atelier.advanceAria"],
      ["atelier.undo", "atelier.undoAria"],
      ["atelier.skip", "atelier.skipAria"],
      ["atelier.skipCommit", "atelier.skipCommitAria"],
      ["atelier.assignLabel", "atelier.assignAria"],
      ["atelier.assignCommit", "atelier.assignCommitAria"],
      ["atelier.claim", "atelier.claimAria"],
      ["atelier.release", "atelier.releaseAria"],
      ["atelier.edit", "atelier.editAria"],
      ["atelier.delete", "atelier.deleteAria"],
    ];
    for (const [visible, aria] of pairs) {
      // `^`-anchored, not toContain: «העברה — {{name}}» contains «העברה לשלב»
      // nowhere but «העברה לשלב — {{name}}» does contain «העברה», so
      // containment alone would pass a skipCommit name that started with the
      // wrong label. None of these Hebrew labels carries a regex metacharacter.
      expect(i18n.t(aria, { name: "מיכל לוי" })).toMatch(new RegExp(`^${i18n.t(visible)}`));
    }
  });

  it("gives the two controls in one card two different accessible names", () => {
    // D18 spelled the assign `Select`'s label «שיוך», which is also the commit
    // `Button` beside it — two controls in ONE card carrying one accessible
    // name (WCAG 4.1.2), and a speech-input user saying «שיוך» could not tell
    // them apart. The `Select` names WHAT is chosen and the `Button` the act.
    expect(i18n.t("atelier.assignLabel")).not.toBe(i18n.t("atelier.assignCommit"));
    expect(i18n.t("atelier.skip")).not.toBe(i18n.t("atelier.skipCommit"));
  });

  it("interpolates the freshness, idle-window, count and effort placeholders", () => {
    expect(i18n.t("atelier.updatedAt", { time: "14:07" })).toBe("עודכן 14:07");
    expect(i18n.t("atelier.staleAt", { time: "14:07" })).toBe("אין עדכון מאז 14:07");
    expect(i18n.t("atelier.pausedAt", { time: "14:07" })).toBe("מושהה · עודכן 14:07");
    expect(i18n.t("atelier.idleStopped", { minutes: 10 })).toContain("10");
    // ⚠ `{{total}}`, NEVER `{{count}}` — `count` is i18next's plural-resolution
    // trigger and this string renders ten times per paint. This assertion is
    // half a guard: it reds if the KEY is switched to `{{count}}` and the call
    // site is not, and it cannot see the coordinated change. The rule is in the
    // copy deck and is a review item.
    expect(i18n.t("atelier.stageCount", { stage: "בעבודה", total: 4 })).toBe("בעבודה · 4");
    expect(i18n.t("atelier.bandOption", { band: "חצי יום", minutes: 240 })).toBe(
      "חצי יום · 240 דק׳",
    );
    expect(i18n.t("atelier.effortMinutes", { minutes: 300 })).toBe("300 דק׳");
  });

  it("names the bride in every string that outlives her card", () => {
    // §4.1's naming rule: a cue names the TICKET only when the ticket moved out
    // from under the user. The advance, the undo, the create and the delete all
    // move or remove the card; the assign and the release leave it under focus.
    for (const key of [
      "atelier.cue.created",
      "atelier.cue.advanced",
      "atelier.cue.undone",
      "atelier.cue.deleted",
      "atelier.deleteConfirmBody",
    ]) {
      expect(i18n.t(key, { name: "מיכל לוי", stage: "בקרה" })).toContain("מיכל לוי");
    }
    // At most ONE user-supplied value per string, which is what lets the
    // shipped isolateBidi(text, value) and { text, name } cue state work
    // unmodified. The assign cue names the new value alone.
    expect(i18n.t("atelier.cue.assigned", { seamstress: "נועה לוי" })).toBe("שויך לנועה לוי.");
    expect(i18n.t("atelier.cue.released")).toBe("השיוך בוטל.");
  });

  it("names no retry interval anywhere in the deck", () => {
    // copy.md §0 rule 5: the backoff stretches 5s -> ~60s, so any string
    // quantifying the wait becomes a lie the board silently stops keeping. The
    // three card errors name the next EVENT («בעדכון הבא»), never a duration.
    //
    // No key is excluded, unlike F57's: this deck's `{{minutes}}` runs are all
    // interpolations, so not one value carries a literal digit.
    const values = HE_F41.map(([, value]) => value);
    expect(values.filter((value) => /\d/.test(value))).toEqual([]);
    // And the word form, which carries no digit at all. Whole words: «מידע» in
    // `atelier.staleBody` contains «מיד» and is the legitimate word there.
    for (const value of values) {
      expect(value).not.toMatch(/(^|[\s"«])(מיד|שניות|חמש)([\s".,»]|$)/);
    }
  });

  it("names no role in the access-ended sentence", () => {
    // copy.md §0 rule 6: the server ships ONE 403 body for every unadmitted
    // role so a probe cannot learn which roles exist, and on the demotion path
    // telling a staffer she was demoted is her manager's sentence, not a
    // screen's.
    const accessEnded = i18n.t("atelier.accessEnded");
    for (const word of ["קבלה", "יועצת מכירות", "תופרת", "אחראית משמרת", "תפקיד", "שונה"]) {
      expect(accessEnded).not.toContain(word);
    }
    // «כרגע» is load-bearing: a re-promotion restores the board.
    expect(accessEnded).toContain("כרגע");
  });

  it("declares its own outage string rather than reusing a screen-named one", () => {
    // F57's F-10: reuse a key whose NAMESPACE NAMES ITS SUBJECT, never one
    // whose namespace names a screen. `staff.loadFailed` is the staff list and
    // `board.*` names a screen; `atelier.*` IS the subject here, so declaring
    // is F-10 obeyed rather than ignored.
    expect(i18n.t("atelier.loadFailed")).toBe("לא הצלחנו לטעון את לוח התפירה כרגע.");
    expect(i18n.t("atelier.idleStopped", { minutes: 10 })).not.toBe(
      i18n.t("board.idleStopped", { minutes: 10 }),
    );
    expect(i18n.t("atelier.idleStopped", { minutes: 10 })).not.toBe(
      i18n.t("floor.idleStopped", { minutes: 10 }),
    );
  });
});

describe("F37 sos keys resolve", () => {
  it("carries the whole copy deck", () => {
    // copy.md's 49 rows (48 plus DC-4's `sos.roomA11yPrefix`, now recorded
    // there). Its own floor, for
    // the reason the comment above HE_F17 gives: folded into an existing list,
    // this feature's rows could shrink by this many and still pass.
    expect(HE_F37.length).toBeGreaterThan(44);
  });

  it("is FOLDED into HE, not merely declared", () => {
    // ⚠ THE ONE ASSERTION THE «אני מגיעה» WORDING DECISION RESTS ON. Declare the
    // constant and forget the spread and the resolve check, BOTH register
    // guards and the `ar` guards silently skip all 49 hand-transcribed strings
    // and stay green — including the send-ban that cost this feature «בדרך»,
    // its most natural button word. Nothing else in this file notices.
    expect(HE.map(([key]) => key)).toContain("sos.calling");
  });

  it("adds no nav row, and that is an assertion rather than an omission", () => {
    expect(HE_F37.filter(([key]) => key.startsWith("nav."))).toEqual([]);
    expect("nav.sos" in he.translation).toBe(false);
  });

  it("never claims, promises or hedges a send, scoped to this namespace", () => {
    // ⚠ THE THREE-TERM REGEX — the global guard's — and NOT the HE_F33-scoped
    // five-term /נשלח|תישלח|בדרך|SMS|הודעה/ sitting a few blocks above. «הודעה»
    // is in the approved `sos.error.noteTooLong` («ההודעה ארוכה מדי.»), so F33's
    // block copied wholesale reds this suite on a string the copy deck approved.
    //
    // Belt-and-braces over the global guard the fold restores, not a substitute
    // for it: this one states the rule where the block is read, and it is the
    // rule that made the ack «אני מגיעה» rather than «אני בדרך».
    const values = HE_F37.map(([, value]) => value);
    expect(values.filter((value) => /נשלח|תישלח|בדרך/.test(value))).toEqual([]);
    // «שליחת» is ש-ל-י-ח-ת and trips neither term. Checked here because it LOOKS
    // like it should, and a later editor "fixing" it would lose the send verb.
    expect(i18n.t("sos.send")).toContain("שליחת");
  });

  it("names no literal digit anywhere in the namespace", () => {
    // copy.md §0 rule 5. Escalation and stall are named as STATES — «ללא מענה»,
    // «אין תזוזה מאז שאושרה» — never as durations, because `escalated` is an
    // unbounded boolean and a flat «30 שניות» would be a lie to a shift manager
    // looking at a four-minute-old page. This guard is what makes D17's refusal
    // to mirror ESCALATION_AFTER a complete argument rather than one with a
    // literal 30 sitting in the bundle contradicting it.
    const values = HE_F37.map(([, value]) => value);
    expect(values.filter((value) => /\d/.test(value))).toEqual([]);
  });

  it("starts each accessible name with its visible label (WCAG 2.5.3)", () => {
    // Level A, and therefore inside IS 5568's binding scope. Several cards can
    // be up at once, so each control's name appends the raiser after an
    // em-dash — but it must still OPEN with the visible word or a speech-input
    // user saying what she can see matches nothing. D17's «הסתרת ההתראה — …»
    // failed exactly this against a visible «הסתרה».
    for (const name of ["accept", "dismiss", "resolve", "cancel"]) {
      expect(i18n.t(`sos.${name}Aria`, { name: "דנה כהן" })).toMatch(
        new RegExp(`^${i18n.t(`sos.${name}`)}`),
      );
    }
  });

  it("says «אני מגיעה» on the button and the same verb back to the raiser", () => {
    // One word across two screens with no translation between them: she presses
    // «אני מגיעה» and the raiser reads «דנה כהן מגיעה.». The symmetry is the
    // reason the string survived the send-ban rather than being reworded away.
    expect(i18n.t("sos.accept")).toBe("אני מגיעה");
    expect(i18n.t("sos.acceptedBy", { name: "דנה כהן" })).toBe("דנה כהן מגיעה.");
    expect(i18n.t("sos.acceptedByUnknown")).toBe("מישהי כבר מגיעה.");
  });

  it("declares the two keys whose values a reused key could not carry", () => {
    // `sos.channelReload` copies `floor.reload`'s WORD and not its key: the
    // strip renders on the eleven sections where no `floor.*` string otherwise
    // appears. ⚠ It is «רענון הדף» and NOT «רענון» — that is `floor.refresh`, a
    // different act (refetch the list) offered by a different control, and a
    // button labelled with it that reloads the page is a promise the word does
    // not make.
    expect(i18n.t("sos.channelReload")).toBe(i18n.t("floor.reload"));
    expect(i18n.t("sos.channelReload")).not.toBe(i18n.t("floor.refresh"));
    // And the cue that must not say «נסגרה»: the alert is untouched on the
    // server, so it stays open, keeps escalating and comes back on reload.
    expect(i18n.t("sos.dismissedCue")).not.toBe(i18n.t("sos.resolvedCue"));
  });

  it("reuses rather than re-declares the four shipped strings it needs", () => {
    // copy.md §8. `SosCentre` lives inside `FloorPanel`'s poll and must not
    // spell any of its states a second way, and `lib/elapsed.ts` HARDCODES the
    // two elapsed keys — so the alternative to cross-namespace reuse is a
    // second elapsed implementation, which D17's no-date-library rule forbids.
    for (const key of ["sos.dismissCancel", "sos.targetOnBreak", "sos.centreRaise"]) {
      expect(key in he.translation).toBe(false);
    }
    expect(i18n.t("rooms.cancel")).toBe("ביטול");
    expect(i18n.t("rooms.handoverOnBreak", { name: "דנה כהן" })).toBe("דנה כהן — בהפסקה");
  });

  it("interpolates the time, room and count placeholders", () => {
    expect(i18n.t("sos.since", { time: "11:20" })).toBe("מאז 11:20");
    expect(i18n.t("sos.raiseAria", { room: "חדר 2" })).toBe("קריאה לעזרה — חדר 2");
    // `{{count}}` is i18next's plural trigger, and the base key is what
    // resolves when no plural form is declared — pinned here rather than
    // assumed, because a missing form renders the KEY into an emergency strip.
    expect(i18n.t("sos.dismissedCount", { count: 3 })).toBe("קריאות עזרה · 3");
    expect(i18n.t("sos.rerouted", { name: "דנה כהן" })).toBe(
      "דנה כהן לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.",
    );
  });

  it("keeps the ghost raiser feminine so every sentence still agrees", () => {
    // «אשת צוות שאינה ברשימה» substitutes into {{name}}, so «{{name}} קוראת
    // לעזרה» stays grammatical and the removed-raiser case needs no second key
    // anywhere in the deck.
    expect(i18n.t("sos.calling", { name: i18n.t("sos.raiserGone") })).toBe(
      "אשת צוות שאינה ברשימה קוראת לעזרה",
    );
  });

  it("names the manual fallback on the RAISE and deliberately not on the rest", () => {
    // A failed raise means nobody was called and the emergency is invisible, so
    // «או קראי בקול» is the correct instruction. A failed accept means only that
    // SHE did not claim it — the alert is still open, still rising on every
    // other targeted device and still escalating — so nothing was dropped and
    // «נסי שוב» is exactly right.
    expect(i18n.t("sos.error.raiseFailed")).toContain("קראי בקול");
    expect(i18n.t("sos.error.actionFailed")).not.toContain("קראי בקול");
  });

  it("carries a details-less twin for BOTH 409s that name a person", () => {
    // The winner's staff row can be removed between her accept and this read,
    // so `details` is optional on both — and without the twins the console
    // renders «‎ כבר מגיעה.» with an empty interpolation on a legally binding
    // surface. The cancel twin is the key spec D17 does not list at all.
    expect(i18n.t("sos.error.alreadyAcceptedUnknown")).not.toContain("{{");
    expect(i18n.t("sos.error.cancelAfterAcceptUnknown")).toContain("«נפתר»");
  });
});

describe("F60 guide keys resolve", () => {
  it("carries the whole copy deck", () => {
    // 7 chrome + 36 steps. Its own floor, for the reason every block above has
    // one: folded into an existing list without it, this feature's rows could
    // shrink by 43 and the suite would stay green.
    expect(HE_F60.length).toBeGreaterThanOrEqual(43);
  });

  it("is FOLDED into HE, not merely declared", () => {
    // Declare the constant and forget the spread and the resolve check, BOTH
    // register guards and the `ar` value guard silently skip all 43
    // hand-transcribed strings and stay green. Nothing else in this file
    // notices.
    expect(HE.map(([key]) => key)).toContain("guide.trigger");
  });

  it("adds no nav row, and that is an assertion rather than an omission", () => {
    // `SectionKey` stays fourteen and `NAV` stays fourteen: the guide is a
    // header control beside «יציאה», not a fifteenth section.
    expect(HE_F60.filter(([key]) => key.startsWith("nav."))).toEqual([]);
    expect("nav.guide" in he.translation).toBe(false);
  });

  it("resolves every key GUIDE_STEPS names, not merely every key he.ts holds", () => {
    // ⚠ THIS IS THE ONE DIRECTION THE FOLD CANNOT COVER, and it is AC2 as
    // written. The resolve check above walks HE — i.e. the keys that EXIST in
    // he.ts — so a step key mistyped in `guide.ts` (`guide.floor.33` beside a
    // shipped `guide.floor.3`) leaves the floor at 43, leaves every register and
    // parity guard green, and renders the raw key into a Hebrew dialog. This
    // walks the table instead.
    for (const steps of Object.values(GUIDE_STEPS)) {
      for (const key of steps) {
        expect(i18n.t(key)).not.toBe(key);
      }
    }
  });

  it("resolves the nav label the dialog title is built from, for all fourteen", () => {
    // P-1. `GuideOverlay` derives the title's section name as `t(`nav.${section}`)`
    // rather than taking it as a prop, and this is the one test that proves the
    // lookup is TOTAL: five of the fourteen resolve through the nested `nav:`
    // object (he.ts:14-20) and nine through `ignoreJSONStructure`'s flat
    // fallback. Neither path may be "fixed" against the other.
    //
    // Derived from GUIDE_STEPS deliberately: its completeness against the
    // fourteen shipped sections is pinned by GuideOverlay.test.tsx §1's
    // spelled-out set, so deriving here cannot silently cover thirteen.
    for (const key of Object.keys(GUIDE_STEPS)) {
      expect(i18n.t(`nav.${key}`)).not.toBe(`nav.${key}`);
    }
  });

  it("interpolates the section, step and total placeholders", () => {
    expect(i18n.t("guide.title", { section: i18n.t("nav.board") })).toBe("מדריך — לוח היום");
    // ⚠ THE TRAILING «במדריך» IS LOAD-BEARING TWICE (copy.md C-1): it keeps both
    // digits between Hebrew words, which is D5's bidi rule and is unsatisfiable
    // for a two-number Hebrew counter without a trailing noun; and the live
    // region utters this line alone, so one word naming WHICH of the console's
    // role="status" regions is speaking is the floor.idleStopped-vs-
    // board.idleStopped argument applied here.
    //
    // ⚠ `isolateLtr` is NOT the alternative and would be actively wrong: it
    // splits on `text.indexOf(value)` (lib/booking.tsx:76), so on «שלב 3 מתוך 3»
    // it isolates the FIRST 3 and leaves the trailing one bare — on the
    // most-visited step of every three-step section.
    expect(i18n.t("guide.progress", { step: 2, total: 3 })).toBe("שלב 2 מתוך 3 במדריך");
  });

  it("names no 2.5.3 loop, because there is no *Aria key in this block", () => {
    // DL20, stated rather than left to be discovered as an omission. The
    // trigger's accessible name IS its visible «מדריך», so WCAG 2.5.3 is true
    // here by construction and an aria-label over visible text — the one shape
    // 2.5.3 can fail — never enters the bundle.
    expect(HE_F60.filter(([key]) => key.endsWith("Aria"))).toEqual([]);
  });
});

describe("the register, mechanically", () => {
  const values = HE.map(([, value]) => value);

  it("contains no exclamation mark", () => {
    expect(values.filter((value) => value.includes("!"))).toEqual([]);
  });

  it("never claims, promises or hedges a send", () => {
    expect(values.filter((value) => /נשלח|תישלח|בדרך/.test(value))).toEqual([]);
  });
});

describe("the ar bundle", () => {
  it("carries no empty string", () => {
    // i18next's returnEmptyString default renders "" rather than falling back,
    // so an empty placeholder would blank the page instead of showing Hebrew.
    // Widened to `string` deliberately: with the literal types `as const` gives,
    // tsc calls the comparison unreachable and the guard would be dead the day
    // someone actually adds an empty value.
    const empty = Object.entries<string>(ar.translation).filter(([, value]) => value === "");
    expect(empty).toEqual([]);
  });

  it("carries every key every feature added to he.ts", () => {
    const missing = HE.map(([key]) => key).filter((key) => !(key in ar.translation));
    expect(missing).toEqual([]);
  });

  it("carries the approved Hebrew VALUE for every rooms key, not merely the key", () => {
    // DC-3 / AC13. The presence guard above cannot see a WRONG value, and the
    // empty-string guard passes on an English string, a `TODO`, or a different
    // Hebrew wording — a live hazard when seventy keys are transcribed by hand
    // into two files with no he/ar parity guard anywhere in this repo. The rule
    // is `ar[key] === he[key]` and it is scoped to this namespace deliberately:
    // widening it would be a different feature's decision to take.
    const arTranslation = ar.translation as Record<string, string>;
    const drifted = HE_F36.filter(([key, value]) => arTranslation[key] !== value).map(
      ([key]) => key,
    );
    expect(drifted).toEqual([]);
  });

  it("carries the approved Hebrew VALUE for every waitlist key, not merely the key", () => {
    // The guard above is scoped to HE_F36 BY NAME, so without this twin F58's
    // thirty-seven hand-transcribed strings would ship with only the presence
    // check — which passes on an English string, a `TODO`, or a different
    // Hebrew wording. There is still no he/ar parity guard anywhere in this
    // repo (F15's Risk 5), so each block declares its own.
    const arTranslation = ar.translation as Record<string, string>;
    const drifted = HE_F58.filter(([key, value]) => arTranslation[key] !== value).map(
      ([key]) => key,
    );
    expect(drifted).toEqual([]);
  });

  it("carries the approved Hebrew VALUE for every sos key, not merely the key", () => {
    // AC23. `ar[key] === he[key]`, NOT "non-empty" — which passes on an English
    // string, on a `TODO`, and on a DIFFERENT Hebrew wording, and 49 keys are
    // transcribed by hand into two files. On this namespace a different wording
    // is not cosmetic: «בדרך» could re-enter the product through ar.ts alone.
    const arTranslation = ar.translation as Record<string, string>;
    const drifted = HE_F37.filter(([key, value]) => arTranslation[key] !== value).map(
      ([key]) => key,
    );
    expect(drifted).toEqual([]);
  });

  it("carries the approved Hebrew VALUE for every guide key, not merely the key", () => {
    // AC3, and the fourth twin beside HE_F36, HE_F58 and HE_F37 — each block
    // declares its own because the guards above are scoped BY NAME. The rule is
    // `ar[key] === he[key]`, NOT "non-empty": presence alone passes on an
    // English string, on a `TODO`, and on a DIFFERENT Hebrew wording, and 43
    // keys are transcribed by hand into two files. On this namespace a
    // different wording is not cosmetic — «נשלח» could re-enter the product
    // through ar.ts alone, on 36 sentences the register guards only read in
    // he.ts.
    const arTranslation = ar.translation as Record<string, string>;
    const drifted = HE_F60.filter(([key, value]) => arTranslation[key] !== value).map(
      ([key]) => key,
    );
    expect(drifted).toEqual([]);
  });
});
