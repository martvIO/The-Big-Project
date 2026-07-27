import { describe, expect, it } from "vitest";
import { safeHref } from "../lib/url";

describe("safeHref", () => {
  it("passes http(s), tel and mailto through", () => {
    expect(safeHref("https://maps.google.com/x")).toBe("https://maps.google.com/x");
    expect(safeHref("http://waze.com/ul")).toBe("http://waze.com/ul");
    expect(safeHref("tel:0501234567")).toBe("tel:0501234567");
  });

  it("drops javascript: and other unsafe schemes (returns undefined)", () => {
    expect(safeHref("javascript:alert(document.cookie)")).toBeUndefined();
    expect(safeHref("  javascript:alert(1)")).toBeUndefined();
    expect(safeHref("JAVASCRIPT:alert(1)")).toBeUndefined();
    expect(safeHref("data:text/html,<script>alert(1)</script>")).toBeUndefined();
    expect(safeHref("vbscript:msgbox")).toBeUndefined();
  });

  it("drops empty / nullish input", () => {
    expect(safeHref(undefined)).toBeUndefined();
    expect(safeHref(null)).toBeUndefined();
    expect(safeHref("   ")).toBeUndefined();
  });
});
