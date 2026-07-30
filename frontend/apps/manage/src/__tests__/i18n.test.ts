import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { ar } from "../i18n/ar";
import { he } from "../i18n/he";

// F15's copy is transcribed into he.ts as DOTTED LITERAL keys, one per row of
// .planning/design/screens/owner-bookings/copy.md. i18next resolves those
// through `ignoreJSONStructure` (default true), which falls back to a flat
// lookup when the nested path misses — this suite is the proof, because a
// silently unresolved key renders the key itself into the console.
// The bundle also holds the pre-F15 nested namespaces, so narrow to the flat
// string entries this feature added.
function f15Entries(bundle: object): [string, string][] {
  return Object.entries(bundle).filter(
    (entry): entry is [string, string] =>
      (entry[0] === "nav.bookings" || entry[0].startsWith("booking.")) &&
      typeof entry[1] === "string",
  );
}

const HE = f15Entries(he.translation);

describe("F15 keys resolve", () => {
  it("carries the whole copy deck", () => {
    expect(HE.length).toBeGreaterThan(70);
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

// copy.md §0 rules 1 and 2, mechanically. Rule 2 is the Risk 3(a) discharge:
// _deliver swallows both send errors, so there is no evidence row at all and no
// string may claim, imply or hedge that a message went out.
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
});
