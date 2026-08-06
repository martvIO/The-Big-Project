import { defineConfig, devices } from "@playwright/test";

// Runs against `vite preview` of both built apps. CI builds first, then serves.
export default defineConfig({
  testDir: ".",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: "line",
  use: {
    locale: "he-IL",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "pnpm --filter storefront preview --port 4173 --strictPort",
      url: "http://localhost:4173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "pnpm --filter manage preview --port 4174 --strictPort",
      // /manage/, not /: apps/manage builds with base: "/manage/", so that is
      // where preview serves the shell and the readiness probe must look.
      url: "http://localhost:4174/manage/",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      // F25's platform console. Same base-path rule as manage, one app over:
      // apps/platform builds with base: "/platform/", so the shell — and the
      // readiness probe — live under that prefix and not at the root.
      command: "pnpm --filter platform preview --port 4175 --strictPort",
      url: "http://localhost:4175/platform/",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
