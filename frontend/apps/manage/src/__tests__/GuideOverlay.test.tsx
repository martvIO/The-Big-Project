import { describe, expect, it } from "vitest";
import { GUIDE_STEPS } from "../lib/guide";

/**
 * ⚠ NO TEST IN THIS FILE ASSERTS FOCUS, AND THAT IS A RULE RATHER THAN AN
 * OVERSIGHT (spec DL17).
 *
 * jsdom 29.1.1 ships no `<dialog>` implementation — the impl file is an empty
 * subclass — so `src/test/setup.ts` stubs BOTH `showModal` and `show` with a
 * body that is literally `this.open = true`. No focus move, no trap, no top
 * layer, no `cancel` event on Esc. A vitest assertion about the dialog's focus,
 * its Tab cycle or its Esc route would therefore measure the stub, and would
 * stay green with the component's focus code deleted.
 *
 * Every focus criterion of this feature lives in `e2e/guide.spec.ts`, in real
 * Chromium, each with the named deletion that reddens it. §7 below is the one
 * permitted exception: it is a plain IDREF read with no focus and no `<dialog>`
 * behaviour in it.
 */

// The fourteen are SPELLED OUT here, re-derived from `App.tsx:24-41` by hand on
// 2026-08-04, rather than imported from `SectionKey` or read back off
// `GUIDE_STEPS`: a test that derives its expectation from the thing under test
// proves nothing. A fifteenth section arriving must fail HERE as well as at the
// typecheck.
const SECTIONS = [
  "dashboard",
  "profile",
  "hours",
  "types",
  "terms",
  "catalog",
  "bookings",
  "customers",
  "board",
  "staff",
  "gateway",
  "floor",
  "checkinQr",
  "atelier",
];

describe("the step table", () => {
  it("covers every section, by set equality", () => {
    expect(new Set(Object.keys(GUIDE_STEPS))).toEqual(new Set(SECTIONS));
  });

  it("gives every section at least one step", () => {
    // The type already makes an empty tuple unrepresentable (spec DL4); this is
    // the runtime twin, and it is what catches a section whose steps were
    // emptied through a cast.
    //
    // Widened to `readonly string[]` deliberately, the same move the shipped
    // `ar` empty-string guard makes: with the literal tuple types `as const`
    // gives, tsc types `.length` as `2 | 3`, calls the comparison unreachable
    // and fails the typecheck — so the guard would have to be deleted the day
    // it was needed.
    const empty = Object.entries<readonly string[]>(GUIDE_STEPS).filter(
      ([, steps]) => steps.length === 0,
    );
    expect(empty).toEqual([]);
  });
});
