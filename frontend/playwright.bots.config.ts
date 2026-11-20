import { defineConfig } from "@playwright/test";
import { e2eEnvironment } from "./e2e/helpers/environment";
const environment = { ...e2eEnvironment(), API_URL: "http://127.0.0.1:18020" };
export default defineConfig({
  testDir: "./e2e", testMatch: "bots.spec.ts", workers: 1, timeout: 90_000,
  use: { baseURL: "http://127.0.0.1:15120", trace: "retain-on-failure", viewport: { width: 1440, height: 1000 } },
  webServer: [
    { command: "uv run uvicorn tests.e2e_bot_app:app --host 127.0.0.1 --no-proxy-headers --port 18020", cwd: "../backend", url: "http://127.0.0.1:18020/health", env: environment, reuseExistingServer: false },
    { command: "npm run dev -- --host 127.0.0.1 --port 15120 --strictPort", url: "http://127.0.0.1:15120", env: environment, reuseExistingServer: false },
  ],
});
