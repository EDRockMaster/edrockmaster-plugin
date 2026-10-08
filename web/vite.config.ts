// The interface of the desktop application (ADR 0021): built into one self-contained HTML file,
// handed to pywebview as a page, with no server.
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vitest/config";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [svelte(), viteSingleFile({ removeViteModuleLoader: true })],
  build: {
    outDir: "../edrockmaster/desktop/interface",
    emptyOutDir: true,
    target: "es2022",
  },
  // Svelte's browser build in the tests too (Testing Library mounts components)
  ...(process.env["VITEST"] ? { resolve: { conditions: ["browser"] } } : {}),
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    include: ["tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,svelte}"],
      exclude: ["src/main.ts", "src/**/*.d.ts"],
      thresholds: { lines: 90, functions: 90, branches: 90, statements: 90 },
    },
  },
});
