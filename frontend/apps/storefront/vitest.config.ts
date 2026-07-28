// Standalone Vitest config on purpose: the app's vite.config.ts carries the
// dev proxy + tailwind/react dev plugins, none of which belong in the test
// pipeline. Vitest 4 peer-supports Vite 8 (rolldown), so TSX transforms work
// without the react plugin.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
