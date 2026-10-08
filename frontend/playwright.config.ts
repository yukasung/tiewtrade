import { defineConfig } from "@playwright/test";
import { e2eEnvironment } from "./e2e/helpers/environment";

const environment = e2eEnvironment();

/**
 * e2e ของ F-01 — พิสูจน์ว่าเบราว์เซอร์จริงเห็นข้อมูลจาก API จริง (V-8)
 *
 * รัน backend กับ frontend เองทั้งคู่ เพื่อให้เทสต์นี้ไม่ต้องพึ่งว่ามีใครรันไว้ก่อน
 */
export default defineConfig({
  testDir: "./e2e",
  // FakeVenue workers scan shared pending jobs; serialize with per-test DB throttle isolation.
  workers: 1,
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command: "uv run uvicorn tiewtrade.services.api.app:app --no-proxy-headers --port 8000 --ws tiewtrade.services.api.price_protocol:PriceWebSocketProtocol",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      env: environment,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --strictPort",
      url: "http://localhost:5173",
      env: environment,
      reuseExistingServer: false,
    },
  ],
});
