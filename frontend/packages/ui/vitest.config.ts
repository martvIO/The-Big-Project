// Standalone Vitest config — packages/ui has no vite.config.ts of its own.
// Vitest 4 transforms TSX without the react plugin. jsdom for component tests.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
