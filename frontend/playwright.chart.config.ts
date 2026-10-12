import { defineConfig } from "@playwright/test";
import { e2eEnvironment } from "./e2e/helpers/environment";

const environment = { ...e2eEnvironment(), API_URL: "http://127.0.0.1:18012",
  TIEWTRADE_CHART_ENABLED: "1", VITE_CHART_ENABLED: "1",
  TIEWTRADE_PRICE_ORIGINS: "http://localhost:18174,http://127.0.0.1:18174",
  PYTHONIOENCODING: "utf-8" };
export default defineConfig({ testDir: "./e2e", testMatch: "candlestick-chart.spec.ts",
  workers: 1, timeout: 120_000, use: { baseURL: "http://localhost:18174" },
  webServer: [
    { command: "uv run uvicorn tiewtrade.services.api.app:app --no-proxy-headers --port 18012 --ws tiewtrade.services.api.price_protocol:PriceWebSocketProtocol",
      cwd: "../backend", url: "http://localhost:18012/health", env: environment, reuseExistingServer: false },
    { command: "node node_modules/vite/bin/vite.js --strictPort --port 18174", url: "http://localhost:18174",
      env: environment, reuseExistingServer: false },
  ],
});
