import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL auto-cleanup hooks onto global afterEach, which we don't expose
// (globals: false) — register it explicitly.
afterEach(() => {
  cleanup();
});
