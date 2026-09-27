import { defineConfig } from "@playwright/test";

/**
 * e2e ของ F-01 — พิสูจน์ว่าเบราว์เซอร์จริงเห็นข้อมูลจาก API จริง (V-8)
 *
 * รัน backend กับ frontend เองทั้งคู่ เพื่อให้เทสต์นี้ไม่ต้องพึ่งว่ามีใครรันไว้ก่อน
 */
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command: "uv run uvicorn tiewtrade.services.api.app:app --port 8000",
      cwd: "../backend",
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
