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
    // A floor, not an exact count: F25's §1–§6 rows plus the two recorded
    // crash-state keys, plus F26's invites and join decks. It exists so a bundle
    // gutted by a bad merge fails here rather than rendering key names onto the
    // screen.
    expect(HE.length).toBeGreaterThanOrEqual(100);
  });

  it("carries every key F26's two surfaces render", () => {
    // Named rather than counted. A missing key renders as itself, and on the
    // JOIN screen — the one screen in this app a non-operator opens — that is a
    // dotted identifier where a Hebrew sentence should be.
    const required = [
      "platform.invites.heading",
      "platform.invites.createHeading",
      "platform.invites.createdFor",
      "platform.invites.linkOnce",
      "platform.invites.linkLabel",
      "platform.invites.linkExpires",
      "platform.invites.linkDeliver",
      "platform.invites.copy",
      "platform.invites.copied",
      "platform.invites.copyFailed",
      "platform.invites.dismiss",
      "platform.invites.revokeTitle",
      "platform.invites.revokeBody",
      "platform.invites.revokeConfirm",
      "platform.invites.revokeCancel",
      "platform.invites.statusOpen",
      "platform.invites.statusRedeemed",
      "platform.invites.statusExpired",
      "platform.join.title",
      "platform.join.headingCode",
      "platform.join.heading",
      "platform.join.headingDone",
      "platform.join.codeLabel",
      "platform.join.codePrompt",
      "platform.join.codeSubmit",
      "platform.join.claiming",
      "platform.join.boutiqueLabel",
      "platform.join.addressLabel",
      "platform.join.emailLabel",
      "platform.join.password",
      "platform.join.submit",
      "platform.join.success",
      "platform.join.successBody",
      "platform.join.toManage",
      "platform.join.loadFailed",
      "platform.join.retry",
      "platform.error.invalid_invite",
      "platform.error.rate_limited",
      "platform.join.error.slug_taken",
      "platform.join.error.invalid_or_reserved_slug",
    ];
    const missing = required.filter((key) => !(key in he.translation));
    expect(missing).toEqual([]);
  });

  it("carries the isolate markup INSIDE the three interpolated strings", () => {
    // ⚠ THE <Trans> CONTRACT, mechanised. These three sentences interpolate a
    // Latin run into RTL text beside neutral characters (a comma, parentheses),
    // and without the isolate the run reorders on screen. A later editor
    // "simplifying" them back to t() would drop the tags and nothing else in the
    // suite would notice — the string would still render, just wrongly.
    //
    // Two tag names, because the two isolates differ: <bdi> takes dir="ltr" at
    // the call site (always-Latin), <name> is a bare <bdi /> (a boutique name
    // may be Hebrew).
    const trans: Record<string, string[]> = {
      "platform.invites.createdFor": ["<name>{{name}}</name>", "<bdi>{{url}}</bdi>"],
      "platform.invites.revokeBody": ["<name>{{name}}</name>", "<bdi>{{slug}}</bdi>"],
      "platform.join.successBody": ["<bdi>{{email}}</bdi>"],
    };
    for (const [key, fragments] of Object.entries(trans)) {
      const value = (he.translation as Record<string, string>)[key];
      for (const fragment of fragments) {
        expect(value).toContain(fragment);
      }
      // No token OUTSIDE a tag — that is the defect shape. Whole tagged
      // segments are removed, so anything left holding a token was bare.
      expect(value.replace(/<(\w+)>.*?<\/\1>/g, "")).not.toMatch(/\{\{/);
    }
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
