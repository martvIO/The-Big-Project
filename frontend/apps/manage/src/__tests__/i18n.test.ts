import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { ar } from "../i18n/ar";
import { he } from "../i18n/he";

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
const HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34];

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

// copy.md §0 rules 1 and 2, mechanically. For F15 rule 2 discharged a swallowed
// send-error risk; for F51 it is literally true — there is no mailer and no SMS
// sender ID, so the owner speaks the password herself and no string may hint
// otherwise. That is why the notice is phrased «יש למסור…» and not «אינה
// נשלחת…»: the latter contains נשלח and would trip this guard, and a copy deck
// that has to dodge its own guard is copy that is one edit away from lying.
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

  it("carries every key both features added to he.ts", () => {
    const missing = HE.map(([key]) => key).filter((key) => !(key in ar.translation));
    expect(missing).toEqual([]);
  });
});
