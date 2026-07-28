import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import i18n from "../i18n";
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

function resolve(key: string): unknown {
  return key
    .split(".")
    .reduce<unknown>(
      (node, segment) =>
        typeof node === "object" && node !== null
          ? (node as Record<string, unknown>)[segment]
          : undefined,
      he.translation,
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
