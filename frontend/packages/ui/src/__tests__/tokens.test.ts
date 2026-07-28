import { existsSync, readFileSync, readdirSync } from "node:fs";
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

  // Tailwind v4 never auto-scans node_modules, and both apps reach this package
  // through the pnpm workspace symlink — so every class used only inside
  // packages/ui compiles to nothing unless theme.css declares @source. A wrong
  // relative path fails the same silent way, hence resolving it for real here.
  it("declares an @source glob that actually covers the component sources", () => {
    const match = /@source\s+"([^"]+)"/.exec(themeCss);
    expect(match, "theme.css must declare @source").not.toBeNull();
    const themeDir = resolve(process.cwd(), "src");
    const scanned = resolve(themeDir, match?.[1] ?? "");
    expect(existsSync(resolve(scanned, "components/BookingCTA.tsx"))).toBe(true);
  });

  // Four classes in this package were written as `inset-inline*`, which is the
  // CSS *property*; Tailwind registers it under the *utility* names inset-x /
  // inset-s / inset-e. The property name compiles to nothing at all, so the
  // element silently falls back to its static position — how the CTA bar came to
  // shrink-wrap and both gallery arrows came to stack on one rect. Nothing else
  // in the suite can see a class that simply never existed.
  // Scans the whole workspace, not just this package: apps/manage and
  // apps/storefront write raw utility strings too, and a guard that stops at the
  // package boundary would miss the identical bug one directory over. The
  // package's own suite is the only place with a natural home for it.
  it("never uses a CSS property name where Tailwind wants a utility name", () => {
    const workspace = resolve(process.cwd(), "..", "..");
    const roots = [
      resolve(workspace, "packages/ui/src"),
      resolve(workspace, "apps/storefront/src"),
      resolve(workspace, "apps/manage/src"),
    ].filter((root) => existsSync(root));
    expect(roots.length, "no source roots found — the relative path is wrong").toBe(3);

    const offenders: string[] = [];
    for (const root of roots) {
      for (const entry of readdirSync(root, { recursive: true, withFileTypes: true })) {
        if (!entry.isFile() || !/\.tsx?$/.test(entry.name)) continue;
        const path = resolve(entry.parentPath, entry.name);
        if (path.includes("__tests__")) continue;
        for (const [i, line] of readFileSync(path, "utf8").split("\n").entries()) {
          if (/\binset-inline/.test(line)) {
            offenders.push(`${path.slice(workspace.length + 1)}:${String(i + 1)}`);
          }
        }
      }
    }
    expect(offenders, "use inset-x / inset-s / inset-e — inset-inline* emits no CSS").toEqual([]);
  });

  it("nested tokens object never drifts from the flat mirror", () => {
    const flat: Record<string, string> = themeTokens;
    for (const [name, value] of Object.entries(tokens.color)) {
      const key = `--color-${name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`;
      expect(flat[key], `${key} backs tokens.color.${name}`).toBe(value);
    }
  });
});
