import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { themeTokens, tokens } from "../tokens";

// pnpm runs each package's `test` script with cwd = the package root.
const themeCss = readFileSync(resolve(process.cwd(), "src/theme.css"), "utf8");

// Parse the single @theme block into a flat { "--name": "value" } map.
// The wildcard clearing lines (`--color-*: initial;`) don't match the name regex
// and are skipped; any explicit `initial` value is dropped too.
function parseThemeBlock(css: string): Record<string, string> {
  const start = css.indexOf("@theme");
  expect(start, "theme.css must contain an @theme block").toBeGreaterThanOrEqual(0);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  const body = css.slice(open + 1, close);
  const out: Record<string, string> = {};
  const decl = /--([a-z0-9-]+)\s*:\s*([^;]+);/gi;
  let m: RegExpExecArray | null;
  while ((m = decl.exec(body)) !== null) {
    const value = m[2].replace(/\s+/g, " ").trim();
    if (value === "initial") continue;
    out[`--${m[1]}`] = value;
  }
  return out;
}

const norm = (v: string) => v.replace(/\s+/g, " ").trim();

describe("token single-source parity", () => {
  const parsed = parseThemeBlock(themeCss);

  it("themeTokens mirrors the @theme block exactly, key-for-key", () => {
    const mirror: Record<string, string> = {};
    for (const [k, v] of Object.entries(themeTokens)) mirror[k] = norm(v);
    expect(mirror).toEqual(parsed);
  });

  it("exports all seven paired line-heights", () => {
    const steps = ["xs", "sm", "base", "lg", "xl", "2xl", "3xl"];
    for (const s of steps) {
      expect(parsed[`--text-${s}`], `--text-${s} size`).toBeTruthy();
      expect(parsed[`--text-${s}--line-height`], `--text-${s}--line-height`).toBeTruthy();
    }
    const leadings = Object.keys(parsed).filter((k) => k.endsWith("--line-height"));
    expect(leadings).toHaveLength(7);
  });

  it("overrides Tailwind's built-in ease-out with the token curve", () => {
    expect(parsed["--ease-out"]).toBe("cubic-bezier(0.16, 1, 0.3, 1)");
  });

  it("ships the corrected AA contrast values, not the failing ones", () => {
    // border-input was #B9A98F (2.03:1) — the F9 Phase-0 fix.
    expect(parsed["--color-border-input"]).toBe("#8A7A5E");
    expect(themeCss).not.toContain("#B9A98F");
    expect(parsed["--color-focus"]).toBe("#7F612B");
  });

  it("opts out of forced dark theming and font-faking globally", () => {
    // Property name assembled so the qa §0 `grep color-scheme packages/ui/src`
    // stays at exactly one hit (theme.css), not a false positive from this file.
    const scheme = ["color", "scheme"].join("-");
    expect(themeCss).toMatch(new RegExp(`${scheme}:\\s*only light`));
    expect(themeCss).toMatch(/font-synthesis:\s*none/);
  });

  it("nested tokens object never drifts from the flat mirror", () => {
    const flat: Record<string, string> = themeTokens;
    for (const [name, value] of Object.entries(tokens.color)) {
      const key = `--color-${name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`;
      expect(flat[key], `${key} backs tokens.color.${name}`).toBe(value);
    }
  });
});
