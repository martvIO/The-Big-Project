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
const F19_KEYS = [
  ...Object.keys(he.translation.booking)
    .filter((name) => name.startsWith("pay"))
    .map((name) => `booking.${name}`),
  "manage.awaitingPayment",
  "manage.cancelConsequenceDeposit",
  "errors.bookingAwaitingPayment",
];

describe("the ar bundle", () => {
  it("carries every key F19 added to he.ts", () => {
    // A scanner that matched nothing would make the assertion below vacuous.
    expect(F19_KEYS.length).toBeGreaterThanOrEqual(12);
    const missing = F19_KEYS.filter((key) => typeof resolve(key, ar.translation) !== "string");
    expect(missing).toEqual([]);
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
