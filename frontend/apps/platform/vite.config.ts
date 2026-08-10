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
// A leading "^" is what makes Vite read the key as a RegExp. The two names are
// exactly the second path segments the backend's /platform routers declare, and
// Backend/tests/test_spa_serving.py derives that set from the live route table
// and asserts this line matches it — a third segment added without touching this
// file fails there rather than silently 404ing in dev only.
const PLATFORM_API = "^/platform/(auth|invites|join|tenants)";

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
