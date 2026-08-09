import { describe, expect, it } from "vitest";
import i18n from "../i18n";
import { ar } from "../i18n/ar";
import { he } from "../i18n/he";

// The manage app's mechanical copy guard, copied because the rules it enforces
// are program-wide and not this feature's.
const HE = Object.entries(he.translation).filter(
  (entry): entry is [string, string] => typeof entry[1] === "string",
);

describe("the platform copy deck", () => {
  it("carries every key the design deck approved", () => {
    // A floor, not an exact count: the deck's §1–§6 rows plus the two recorded
    // crash-state keys. It exists so a bundle gutted by a bad merge fails here
    // rather than rendering key names onto the screen.
    expect(HE.length).toBeGreaterThanOrEqual(45);
  });

  it("resolves every key through i18next rather than echoing it back", () => {
    // Keys are DOTTED LITERALS, which i18next resolves via ignoreJSONStructure's
    // flat fallback. A key that stops resolving renders as itself, and nothing
    // else in the suite would notice.
    for (const [key] of HE) {
      expect(i18n.t(key)).not.toBe(key);
    }
  });

  it("contains no exclamation mark anywhere (#5)", () => {
    // Program-wide register rule. Mechanical, because "no exclamation marks" is
    // exactly the kind of thing review passes over on the fortieth string.
    const shouting = HE.filter(([, value]) => value.includes("!"));
    expect(shouting).toEqual([]);
  });

  it("never claims anything was sent", () => {
    // No channel exists — the operator hands the password over herself (spec
    // D5). A «נשלח» in any tense would promise machinery this product does not
    // have, on the one screen that creates a credential.
    const sent = HE.filter(([, value]) => /נשלח|נשלחה|תישלח|ישלח/.test(value));
    expect(sent).toEqual([]);
  });

  it("ships ar with exactly he's keys, untranslated (#47)", () => {
    expect(Object.keys(ar.translation).sort()).toEqual(Object.keys(he.translation).sort());
    for (const [key, value] of HE) {
      expect((ar.translation as Record<string, string>)[key]).toBe(value);
    }
  });
});
