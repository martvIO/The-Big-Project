import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { ar } from "../i18n/ar";
import { he } from "../i18n/he";

// i18next answers a miss with the bare key, so a deleted or renamed entry
// renders "statement.limitsAlt" into a Hebrew page — and a test written as
// t("statement.limitsAlt") keeps passing, because both sides degrade to the
// same ASCII literal. Rendering tests cannot catch that class of defect at all.
// This one does: it reads the keys out of the source text and resolves them
// against the resource bundle, never through t().

// import.meta.url is not a file: URL under the jsdom environment. Vitest runs
// with the package root as cwd.
const SRC = join(process.cwd(), "src");

// A key is a dotted literal whose first segment is a real section of he.ts —
// which is what separates "statement.doneFonts" from a className or a URL.
const SECTIONS = new Set(Object.keys(he.translation));
const DOTTED_LITERAL = /"([A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z0-9]+)+)"/g;
const HEBREW = /[֐-׿]/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      // Tests are the thing being guarded, not a source of shipped keys.
      return entry === "__tests__" || entry === "test" ? [] : sourceFiles(path);
    }
    return /\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry) ? [path] : [];
  });
}

function keysIn(source: string): string[] {
  return [...source.matchAll(DOTTED_LITERAL)]
    .map((match) => match[1])
    .filter((key) => SECTIONS.has(key.split(".")[0]));
}

function resolve(key: string, bundle: object = he.translation): unknown {
  return key
    .split(".")
    .reduce<unknown>(
      (node, segment) =>
        typeof node === "object" && node !== null
          ? (node as Record<string, unknown>)[segment]
          : undefined,
      bundle,
    );
}

const USED_KEYS = [
  ...new Set(
    sourceFiles(SRC)
      .filter((path) => !path.includes(`${join("src", "i18n")}`))
      .flatMap((path) => keysIn(readFileSync(path, "utf8"))),
  ),
].sort();

describe("i18n keys used by the app", () => {
  it("finds the keys the source actually uses", () => {
    // A scanner that silently matches nothing would make every assertion below
    // vacuous — the exact failure mode this file exists to retire.
    expect(USED_KEYS.length).toBeGreaterThan(40);
    expect(USED_KEYS).toContain("statement.limitsAlt");
    expect(USED_KEYS).toContain("statement.coordinatorNoChannel");
    expect(USED_KEYS).toContain("dress.share");
  });

  it.each(USED_KEYS)("%s resolves to real Hebrew, not the key echoed back", (key) => {
    const value = resolve(key);

    expect(value, `${key} is missing from he.ts`).toBeDefined();
    const strings = Array.isArray(value) ? (value as unknown[]) : [value];
    for (const entry of strings) {
      expect(typeof entry, `${key} is not a string`).toBe("string");
      const text = entry as string;
      expect(text.trim(), `${key} is empty`).not.toBe("");
      expect(text, `${key} renders its own key`).not.toBe(key);
      // A value made only of {{placeholders}} and punctuation carries no words
      // of its own (about.exceptionHours is "{{date}} {{open}}–{{close}}"), so
      // the Hebrew demand applies to the prose the visitor actually reads.
      const prose = text.replace(/{{.*?}}/g, "");
      if (/\p{L}/u.test(prose)) {
        expect(HEBREW.test(prose), `${key} has no Hebrew: ${text}`).toBe(true);
      }
    }
  });

  it.each(USED_KEYS)("%s is registered with i18next, not only present in he.ts", (key) => {
    const value = resolve(key);
    const resolved = Array.isArray(value)
      ? i18n.t(key, { returnObjects: true })
      : i18n.t(key, { interpolation: { skipOnVariables: true } });

    expect(resolved).not.toBe(key);
    if (!Array.isArray(value)) expect(typeof resolved).toBe("string");
  });
});

// pre-decided #47: every feature from F16 on ships its `ar` keys beside its
// Hebrew, left untranslated, so the eventual launch is a translation job rather
// than a retrofit across ~28 features. Enumerated mechanically off he.ts so a
// tenth pay string cannot be added to one bundle and forgotten in the other.
// F24. The `portal.*` block plus its two error rows and the tab title,
// enumerated MECHANICALLY off he.ts so a key added to one bundle and forgotten
// in the other is a red rather than an Arabic page that renders its own key.
const F24_KEYS = [
  ...Object.keys(he.translation.portal).map((name) => `portal.${name}`),
  "document.portal",
  "errors.portalNoBookings",
];

const F19_KEYS = [
  ...Object.keys(he.translation.booking)
    .filter((name) => name.startsWith("pay"))
    .map((name) => `booking.${name}`),
  "manage.awaitingPayment",
  "manage.cancelConsequenceDeposit",
  "errors.bookingAwaitingPayment",
];

// F28's three. Same rule, same file — and the ar mirror is the half that gets
// forgotten, because nothing renders from it today.
const F28_KEYS = [
  "dress.reservedDatesHeading",
  "dress.reservedDatesNote",
  "errors.dressUnavailable",
];

// F59 / spec D13. The check-in notice is the notice AT THE MOMENT OF COLLECTION,
// and F59 makes the shipped value incomplete: the first word of the name she
// types is now published on an unauthenticated URL anyone with the boutique's
// address can open. The amendment says exactly that.
//
// ⚠ THIS IS THE ONLY ASSERTION IN THE FEATURE THAT FAILS IF D13 IS REVERTED, and
// it is written against the resource bundle rather than through t() for the
// reason this whole file exists: CheckinPage.test.tsx renders
// t("checkin.notice", { boutique }) and compares it against the same bundle, so
// it passes byte-identically against the UNAMENDED value and can never detect
// the amendment. Written through t(), this one would inherit that vacuity.
//
// The phrase pinned is the public-web-page clause and not the whole sentence:
// the Hebrew is the user's to edit post-merge, but a rewrite that drops the
// public page and goes back to "a screen in the boutique" is a notice narrower
// than the truth, which is the defect D13 exists to correct.
const PUBLIC_PAGE_CLAUSE = "עמוד אינטרנט ציבורי";

describe("the collection notice names the public web page", () => {
  it.each(["he", "ar"])("%s carries the D13 clause", (locale) => {
    const bundle = locale === "he" ? he.translation : ar.translation;
    const notice = resolve("checkin.notice", bundle);

    expect(typeof notice).toBe("string");
    expect(notice as string).toContain(PUBLIC_PAGE_CLAUSE);
  });
});

// F20 / copy.md findings F4 and F5. The interim value made TWO retention
// representations the system could not keep — that the details are deleted a
// few days after the visit (nothing is hard-deleted anywhere, and F20's
// retention job ships switched OFF by Q2), and that an opted-in bride's name
// and phone are kept until she asks to remove the consent (F20's queue_tickets
// SCRUB blanks both at seven days regardless of the box).
//
// Both are struck. This is the assertion that keeps them struck: a revert of
// either he.ts value reddens it, and so does a "restore the old wording"
// resolution of a future merge conflict on this string.
const STRUCK_RETENTION_PROMISES = [
  // «…ונמחקים כמה ימים לאחר הביקור» — deleted a few days after the visit.
  "ונמחקים כמה ימים לאחר הביקור",
  // «…יישמרו לצורך זה עד שתבקשי להסיר את ההסכמה» — kept until you withdraw.
  "עד שתבקשי להסיר את ההסכמה",
];

// §11(b)(3) and §30A. The interim value stated NO voluntariness, NO consequence
// of refusing and NO revocation method — three elements simply missing from a
// live collection point. The replacement states all three.
const REQUIRED_NOTICE_CLAUSES = [
  // Voluntariness + the consequence of refusing.
  "מסירתם היא מרצון",
  // §30A revocation, servable only because of the marketing-withdraw phone arm.
  "אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת",
];

describe("the collection notice makes no retention promise F20 cannot keep", () => {
  it.each(["he", "ar"])("%s carries the approved F20 replacement", (locale) => {
    const bundle = locale === "he" ? he.translation : ar.translation;
    const notice = resolve("checkin.notice", bundle);

    expect(typeof notice).toBe("string");
    for (const struck of STRUCK_RETENTION_PROMISES) {
      expect(notice as string, `${locale} still promises: ${struck}`).not.toContain(struck);
    }
    for (const required of REQUIRED_NOTICE_CLAUSES) {
      expect(notice as string, `${locale} is missing: ${required}`).toContain(required);
    }
  });

  it.each(["he", "ar"])("%s drops the in-message unsubscribe from the opt-in label", (locale) => {
    // «אפשר להסיר את ההסכמה בכל הודעה» — *you can remove the consent in every
    // message*. F46 owns the in-message opt-out and it does not exist, so the
    // interim label promised an unsubscribe path that is not built.
    const bundle = locale === "he" ? he.translation : ar.translation;
    const optIn = resolve("checkin.optIn", bundle);

    expect(typeof optIn).toBe("string");
    expect(optIn as string).not.toContain("בכל הודעה");
    expect(optIn as string).toContain("אפשר לבקש מאיתנו להסיר את ההסכמה בכל עת");
  });
});

describe("the ar bundle", () => {
  it("carries every key F19 added to he.ts", () => {
    // A scanner that matched nothing would make the assertion below vacuous.
    expect(F19_KEYS.length).toBeGreaterThanOrEqual(12);
    const missing = F19_KEYS.filter((key) => typeof resolve(key, ar.translation) !== "string");
    expect(missing).toEqual([]);
  });

  it("carries every F24 portal key, untranslated", () => {
    // The anti-vacuity floor is the design's §11 table: thirty rows plus the
    // title and the error. A scanner that found nothing would make the walk
    // below pass on an empty bundle.
    expect(F24_KEYS.length).toBeGreaterThanOrEqual(30);
    const missing = F24_KEYS.filter((key) => typeof resolve(key, ar.translation) !== "string");
    expect(missing).toEqual([]);
  });

  it("carries F28's three with the same Hebrew value as he.ts", () => {
    // VALUE parity, not presence: the ar mirror is the half that gets forgotten
    // because nothing renders from it today, and a presence check passes on a
    // TODO or on a different Hebrew wording.
    for (const key of F28_KEYS) {
      expect(resolve(key, ar.translation), `${key} missing from ar.ts`).toBe(
        resolve(key, he.translation),
      );
    }
  });

  it("carries the approved Hebrew VALUE for the four gated checkin keys, not merely the key", () => {
    // ⚠ A VALUE-PARITY CHECK, AND THE STOREFRONT'S FIRST. The F19 block above is
    // a PRESENCE check (`typeof resolve(key, ar.translation) === "string"`) and
    // the empty-string walk below is a non-empty check — both pass on an English
    // string, on a `TODO`, and on a DIFFERENT Hebrew wording. Four keys are
    // transcribed by hand into two files here, and this is the guard that sees
    // the third case.
    //
    // ⚠ F20 ADDED `checkin.notice` AND `checkin.optIn`, and that is the whole
    // gate on the counsel swap. DL21 left them out on the reading that F20's
    // swap is a two-file edit ON PURPOSE — which is true and is exactly why they
    // belong here: NOTHING else in the suite compares their two values. The F19
    // presence walk and the empty-string walk both pass on the OLD Hebrew, and
    // `CheckinPage.test.tsx` renders `t()` and compares it against the same
    // bundle, so it passes byte-identically either way. Without this line a
    // builder swaps `he.ts`, forgets `ar.ts`, and the suite stays green while
    // Arabic serves un-approved interim consent text.
    //
    // Still scoped to four named keys rather than widened across the bundle:
    // that is a different feature's decision, and a blanket parity guard would
    // have to be relaxed the day Arabic is actually translated.
    // ⚠ The `typeof === "string"` leg is not decoration: `resolve` returns
    // `undefined` for a missing key, so an equality check alone passes
    // VACUOUSLY when NEITHER bundle carries the key — which is exactly the state
    // this guard was written in.
    for (const key of [
      "checkin.guideTrigger",
      "checkin.guideHint",
      "checkin.notice",
      "checkin.optIn",
    ]) {
      const hebrew = resolve(key, he.translation);
      expect(typeof hebrew).toBe("string");
      expect(resolve(key, ar.translation)).toBe(hebrew);
    }
  });

  it("carries no empty string at any depth", () => {
    // i18next's returnEmptyString default renders "" rather than falling back to
    // `he`, so an empty placeholder would BLANK the page rather than show
    // Hebrew — which is why every value here is the approved Hebrew standing in.
    const empty: string[] = [];
    const walk = (node: object, path: string) => {
      for (const [name, value] of Object.entries(node)) {
        if (typeof value === "string") {
          if (value.trim() === "") empty.push(`${path}${name}`);
        } else if (typeof value === "object" && value !== null) {
          walk(value as object, `${path}${name}.`);
        }
      }
    };
    walk(ar.translation, "");
    expect(empty).toEqual([]);
  });
});
