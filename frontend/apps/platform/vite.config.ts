import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// apps/manage's problem, one app over, with the same answer. `base: "/platform/"`
// puts this app's OWN shell and assets under the same prefix as its API, and
// Vite's proxy middleware runs BEFORE the static and transform middlewares — so
// a bare "/platform" proxy key would forward `/platform/`, `/platform/assets/*`
// and every HMR request to the backend and the console would simply never load.
// That applies to `vite preview` too, which inherits `server.proxy`, so the e2e
// run breaks the same way.
//
// A leading "^" is what makes Vite read the key as a RegExp. The names are
// exactly the second path segments the backend's /platform routers declare, and
// Backend/tests/test_spa_serving.py compiles this very string and drives it over
// the live route table — a segment added without touching this file fails there
// rather than silently 404ing in dev only.
//
// ⚠ **`join/` CARRIES ITS SLASH AND THE OTHERS MUST NOT.** F26 D1 serves the
// join SCREEN at exactly `/platform/join`, so a bare `join` alternative matches
// the shell and the proxy — which runs first — forwards the screen to the
// backend, where a dev machine with no built bundle answers 404. `vite preview`
// inherits `server.proxy`, so the e2e run breaks the same way. The slash cannot
// be added to the others: `GET /platform/tenants` is a real route with nothing
// after it.
const PLATFORM_API = "^/platform/(auth|invites|tenants|join/)";

export default defineConfig({
  // The console lives at admin.{domain}/platform. Without this it would emit
  // absolute /assets/… URLs and collide with the storefront's tree; with it,
  // the backend mounts three disjoint trees with no URL rewriting.
  base: "/platform/",
  plugins: [react(), tailwindcss()],
  server: {
    // ⚠ 127.0.0.1, NOT the default. Vite binds IPv6-only on this machine and
    // `admin.localtest.me` then refuses the connection with no useful error
    // (.memory/vite-dev-binds-ipv6-only).
    host: "127.0.0.1",
    // Develop at http://admin.localtest.me:5175 — the proxy forwards API calls
    // with the ORIGINAL Host header preserved (changeOrigin: false), so the
    // tenancy middleware's label branch sees `admin` and the host-only cookie
    // works unchanged. Same-origin in production too; CORS must never be added.
    allowedHosts: [".localtest.me"],
    proxy: {
      [PLATFORM_API]: { target: "http://localhost:8000", changeOrigin: false },
      "/health": { target: "http://localhost:8000", changeOrigin: false },
    },
  },
});
