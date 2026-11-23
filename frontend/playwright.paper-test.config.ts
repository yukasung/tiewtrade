import { defineConfig } from "@playwright/test";
import { e2eEnvironment } from "./e2e/helpers/environment";
const environment = { ...e2eEnvironment(process.env, ["INDICATOR_BUILDER", "PLATFORM_BOOTSTRAP"]),
  API_URL: "http://127.0.0.1:18022", TIEWTRADE_PRICE_ORIGINS: "http://127.0.0.1:15122",
  TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED: "1" };
export default defineConfig({
  testDir: "./e2e", testMatch: "paper-test-strategy.spec.ts", workers: 1, timeout: 180_000,
  use: { baseURL: "http://127.0.0.1:15122", trace: "retain-on-failure", viewport: { width: 1440, height: 1000 } },
  webServer: [
    { command: "uv run uvicorn tests.e2e_paper_test_app:app --host 127.0.0.1 --no-proxy-headers --port 18022",
      cwd: "../backend", url: "http://127.0.0.1:18022/health", env: environment, reuseExistingServer: false },
    { command: "npm run dev -- --host 127.0.0.1 --port 15122 --strictPort", url: "http://127.0.0.1:15122", env: environment, reuseExistingServer: false },
  ],
});
