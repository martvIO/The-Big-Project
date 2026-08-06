import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The backend's /manage API surface, spelled out rather than proxied as a bare
// "/manage" prefix. `base: "/manage/"` puts the console's OWN shell and assets
// under that same prefix, and Vite's proxy middleware runs BEFORE the static and
// transform middlewares — so "/manage" would forward `/manage/`, `/manage/assets/*`
// and every HMR request to the backend and the app would simply never load. That
// applies to `vite preview` too, which inherits `server.proxy`, so the e2e run
// breaks the same way.
//
// A leading "^" is what makes Vite read the key as a RegExp. The seventeen
// names are exactly the second path segments the backend's /manage routers
// declare, and Backend/tests/test_spa_serving.py derives that set from the live
// route table and asserts this line matches it — an eighteenth segment added
// without touching this file fails there rather than silently 404ing in dev
// only.
const MANAGE_API =
  "^/manage/(appointment-types|atelier|auth|availability|bookings|checkin-qr|customers|dashboard|dresses|floor|gateway|privacy|settings|slots|staff|terms|waitlist)";

export default defineConfig({
  // The console lives at {slug}.{domain}/manage, same origin as the storefront
  // at /. Without this the two apps both emit absolute /assets/… URLs and their
  // static trees collide; with it, manage emits /manage/assets/… and
  // /manage/favicon.svg, so the API can mount each tree independently with no
  // URL rewriting. It also moves the dev and preview roots to /manage/ — hence
  // the MANAGE constant in e2e/a11y.spec.ts and the README's dev URLs.
  base: "/manage/",
  plugins: [react(), tailwindcss()],
  server: {
    // Develop at http://{slug}.localtest.me:5173 — the proxy forwards API
    // calls to the backend with the ORIGINAL Host header preserved
    // (changeOrigin: false), so tenant resolution and host-only cookies work
    // unchanged. Same-origin in production too; CORS must never be added.
    // Vite's host check only allows localhost by default — permit the
    // wildcard-DNS dev domain.
    allowedHosts: [".localtest.me"],
    proxy: {
      [MANAGE_API]: { target: "http://localhost:8000", changeOrigin: false },
      "/health": { target: "http://localhost:8000", changeOrigin: false },
    },
  },
});
