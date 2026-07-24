import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
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
      "/manage": { target: "http://localhost:8000", changeOrigin: false },
      "/health": { target: "http://localhost:8000", changeOrigin: false },
    },
  },
});
