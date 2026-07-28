import { describe, expect, it } from "vitest";
import { waPhone, wazeUrl } from "../lib/contact";

// This module is the survivor of four near-identical copies, and the copy it
// replaced (inlined in the dress detail) was missing BOTH the empty-digits guard
// and the "already 972" passthrough. Every phone fixture in the repo is a
// 0-prefixed Israeli mobile, so without the cases below only one branch of the
// function ever executes and either guard could be deleted with a green suite.
describe("waPhone", () => {
  it("replaces the national trunk prefix with the country code", () => {
    expect(waPhone("052-1234567")).toBe("972521234567");
    expect(waPhone("0521234567")).toBe("972521234567");
  });

  it("passes through a number that already carries the country code", () => {
    expect(waPhone("+972 52 123 4567")).toBe("972521234567");
    expect(waPhone("972521234567")).toBe("972521234567");
  });

  it("returns undefined for a number that is neither 0- nor 972-prefixed", () => {
    // Regression guard, not a taste call: the previous implementation stripped
    // the punctuation and returned whatever digits were left, so a service line
    // stored as "1-800-555" minted wa.me/1800555 — a real, reachable WhatsApp
    // account belonging to a stranger. No link beats a link to the wrong person.
    expect(waPhone("1-800-555")).toBeUndefined();
    expect(waPhone("+1 415 555 0123")).toBeUndefined();
  });

  it("returns undefined rather than a wa.me link to nowhere", () => {
    expect(waPhone(null)).toBeUndefined();
    expect(waPhone(undefined)).toBeUndefined();
    expect(waPhone("")).toBeUndefined();
    // Punctuation-only input strips to zero digits — the guard the deleted copy
    // lacked. Without it this returns "" and renders href="https://wa.me/".
    expect(waPhone("---")).toBeUndefined();
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
