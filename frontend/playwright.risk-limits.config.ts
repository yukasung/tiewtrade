import { defineConfig } from "@playwright/test";
import { e2eEnvironment } from "./e2e/helpers/environment";
const environment = { ...e2eEnvironment(), API_URL: "http://127.0.0.1:18018" };
export default defineConfig({
  testDir: "./e2e", testMatch: "risk-limits.spec.ts", workers: 1, timeout: 90_000,
  use: { baseURL: "http://127.0.0.1:15118", trace: "retain-on-failure", viewport: { width: 1440, height: 1000 } },
  webServer: [
    { command: "uv run uvicorn tests.e2e_risk_app:app --host 127.0.0.1 --no-proxy-headers --port 18018", cwd: "../backend", url: "http://127.0.0.1:18018/health", env: environment, reuseExistingServer: false },
    { command: "npm run dev -- --host 127.0.0.1 --port 15118 --strictPort", url: "http://127.0.0.1:15118", env: environment, reuseExistingServer: false },
  ],
});
