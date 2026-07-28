import { describe, expect, it } from "vitest";
import { wazeUrl, whatsappDigits } from "../lib/contact";

// This module is the survivor of four near-identical copies, and the copy it
// replaced (inlined in DressDetail) was missing BOTH the empty-digits guard and
// the "already 972" passthrough. Every phone fixture in the repo is a
// 0-prefixed Israeli mobile, so without these cases only one branch of the
// function ever executes and either guard could be deleted with a green suite.
describe("whatsappDigits", () => {
  it("replaces the national trunk prefix with the country code", () => {
    expect(whatsappDigits("052-1234567")).toBe("972521234567");
    expect(whatsappDigits("0521234567")).toBe("972521234567");
  });

  it("passes through a number that already carries the country code", () => {
    expect(whatsappDigits("+972-52-1234567")).toBe("972521234567");
    expect(whatsappDigits("972521234567")).toBe("972521234567");
    // The startsWith("972") check is what stops a written-out international
    // form from being mangled: these digits already lead with 972, so the
    // trunk-prefix rewrite must not fire.
    expect(whatsappDigits("+972 (0)52 123 4567")).toBe("9720521234567");
  });

  it("returns undefined rather than a wa.me link to nowhere", () => {
    expect(whatsappDigits(null)).toBeUndefined();
    expect(whatsappDigits(undefined)).toBeUndefined();
    expect(whatsappDigits("")).toBeUndefined();
    // Punctuation-only input strips to zero digits — the guard the deleted copy
    // lacked. Without it this returns "" and renders href="https://wa.me/".
    expect(whatsappDigits("---")).toBeUndefined();
  });
});

describe("wazeUrl", () => {
  it("encodes the address into a Waze query", () => {
    expect(wazeUrl("הרצל 12, תל אביב")).toBe(
      `https://waze.com/ul?q=${encodeURIComponent("הרצל 12, תל אביב")}`,
    );
  });

  it("returns undefined for a missing or blank address", () => {
    expect(wazeUrl(null)).toBeUndefined();
    expect(wazeUrl(undefined)).toBeUndefined();
    expect(wazeUrl("")).toBeUndefined();
  });
});
