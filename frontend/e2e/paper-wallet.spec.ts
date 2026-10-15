import { execFileSync } from "node:child_process";

import { backendPython, e2eEnvironment } from "./helpers/environment";
import { expect, test } from "./helpers/test";
import { captureUi } from "./helpers/ui";

test.use({ locale: "th-TH" });

function processPaperCommand(): void {
  execFileSync(
    backendPython,
    [
      "-B",
      "-c",
      `
import asyncio
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.engine.paper_wallet import run_paper_wallet_round

async def process():
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    try:
        result = await run_paper_wallet_round(
            engine=engine, scan_engine=scan, worker="e2e-paper-wallet")
        assert result.processed == 1, result
    finally:
        await engine.dispose()
        await scan.dispose()

asyncio.run(process())
`,
    ],
    { cwd: "../backend", stdio: "pipe", env: e2eEnvironment() },
  );
}

test("สร้าง Paper wallet ด้วยจำนวน exact และเห็น snapshot หลัง worker commit", async ({
  page,
}, testInfo) => {
  test.setTimeout(60000);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));

  await page.goto("/trading-account");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(`e2e-paper-${String(Date.now())}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill("รหัสผ่านที่ยาวพอใช้งานจริง");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("paper-wallet-panel")).toBeVisible();

  const panel = page.getByTestId("paper-wallet-panel");
  const capital = panel.getByLabel("ทุนตั้งต้น (USDT)");
  await capital.fill("1000");
  await panel.getByRole("button", { name: "สร้างกระเป๋า Paper" }).click();
  await expect(panel.getByRole("alert")).toHaveText("ทุนตั้งต้นต้องมากกว่า 1,000 USDT");

  await capital.fill("1500.000000000000000001");
  await panel.getByRole("button", { name: "สร้างกระเป๋า Paper" }).click();
  await expect(panel.getByText("รับคำขอแล้ว กำลังสร้างกระเป๋า…")).toBeVisible();

  processPaperCommand();

  await expect(panel.getByText("1,500.000000000000000001 USDT", { exact: true })).toHaveCount(2, {
    timeout: 10000,
  });
  await expect(panel.getByText("PAPER", { exact: true })).toBeVisible();
  await expect(panel.getByText("รอบ", { exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: "เริ่มรอบใหม่" })).toBeDisabled();
  await expect(panel.getByText(/ยังตรวจสอบ position และออเดอร์ค้างได้ไม่ครบ/)).toBeVisible();

  await captureUi(page, testInfo, "paper-wallet");

  await page.reload();
  await expect(panel.getByText("1,500.000000000000000001 USDT", { exact: true })).toHaveCount(2);
  expect(errors).toEqual([]);
});
