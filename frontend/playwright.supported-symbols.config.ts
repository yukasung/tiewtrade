import { defineConfig } from "@playwright/test";
import { e2eEnvironment } from "./e2e/helpers/environment";

const environment = {
  ...e2eEnvironment(),
  API_URL: process.env.TIEWTRADE_E2E_BACKEND_URL ?? "http://127.0.0.1:18037",
};
const frontendUrl = process.env.TIEWTRADE_E2E_FRONTEND_URL ?? "http://127.0.0.1:15173";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "supported-symbols.spec.ts",
  workers: 1,
  timeout: 120_000,
  use: { baseURL: frontendUrl },
  webServer: {
    command: "npm run dev -- --host 0.0.0.0 --port 15173 --strictPort",
    url: frontendUrl,
    env: environment,
    reuseExistingServer: true,
  },
});
