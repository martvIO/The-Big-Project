import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Develop at http://{slug}.localtest.me:5173. Vite's host check only allows
    // localhost by default — permit the wildcard-DNS dev domain.
    allowedHosts: [".localtest.me"],
    proxy: {
      // changeOrigin: false is load-bearing. The backend resolves the tenant
      // from the Host header, so rewriting it to localhost:8000 would make every
      // storefront request answer 404 TENANT_NOT_FOUND.
      "/storefront": { target: "http://localhost:8000", changeOrigin: false },
      "/health": { target: "http://localhost:8000", changeOrigin: false },
      // No /manage entry: the storefront never calls the owner console.
    },
  },
});
