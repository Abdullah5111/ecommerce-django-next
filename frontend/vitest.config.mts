import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit tests run in Node; component tests opt into jsdom per file with
// `// @vitest-environment jsdom`.
export default defineConfig({
  // tsconfig keeps JSX as-is for Next.js, so the test transform compiles it.
  // Vite 8 transforms with Oxc (the old `esbuild` option is ignored).
  oxc: { jsx: { runtime: "automatic" } },
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  test: {
    include: ["**/__tests__/**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**"],
  },
});
