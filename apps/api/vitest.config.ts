import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["src/__tests__/**/*.test.ts"],
    setupFiles: ["src/__tests__/setup.ts"],
    testTimeout: 15000,
    hookTimeout: 15000,
    env: {
      NODE_ENV: "test",
    },
  },
  resolve: {
    alias: {
      "@iyisiniye/db": new URL(
        "../../packages/db/src/index.ts",
        import.meta.url
      ).pathname,
      "@iyisiniye/shared": new URL(
        "../../packages/shared/src/index.ts",
        import.meta.url
      ).pathname,
    },
  },
});
