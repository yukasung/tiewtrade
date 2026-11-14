import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/browserSetup.ts"],
    globals: true,
    include: ["tests/**/*.test.tsx", "tests/**/*.test.ts"],
  },
});
