import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// RTL auto-cleanup hooks onto a global afterEach we don't expose (globals: false).
afterEach(() => {
  cleanup();
});
