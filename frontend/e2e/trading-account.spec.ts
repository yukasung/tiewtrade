import { backendPython, e2eEnvironment } from "./helpers/environment";
import { execFileSync } from "node:child_process";
import { expect, test } from "./helpers/test";
import { PASSWORD, codeFor, secretOf, stepAt } from "./helpers/totp";
/** Actual verification worker against FakeVenue; never updates key status by SQL. */
function verify(): void {
  execFileSync(
    backendPython,
    [
      "-B",
      "-c",
      `
import asyncio
from datetime import UTC, datetime
from tiewtrade.infra.crypto import KeyPurpose, KeySource
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.services.engine.verification import run_round
from tiewtrade.venues.fake import FakeVenue
from tiewtrade.venues.wallets import WalletHoldings
async def check():
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    venue = FakeVenue(holdings=WalletHoldings(received_at=datetime.now(UTC), holdings=()))
    try:
        result = await run_round(engine=engine, scan_engine=scan,
            keys=KeySource.from_environment(KeyPurpose.VENUE_API_SECRET),
            wallet_for=lambda signer: venue, worker="e2e-account-worker")
        assert result.verified == 1, result
    finally:
        await engine.dispose()
        await scan.dispose()
asyncio.run(check())
`,
    ],
    { cwd: "../backend", stdio: "pipe", env: e2eEnvironment() },
  );
}
test("fake key → explicit account use → reload → key deletion retains preference", async ({
  page,
}, testInfo) => {
  test.setTimeout(60000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/security");
  await expect(page.getByTestId("submit")).toHaveClass(/account-button/);
  const authStyle = await page.getByTestId("submit").evaluate((element) => {
    const style = window.getComputedStyle(element);
    return [
      style.fontFamily,
      style.fontSize,
      style.borderRadius,
      style.backgroundColor,
    ];
  });
  await page.getByTestId("switch-mode").click();
  await page
    .getByLabel("อีเมล")
    .fill(`e2e-account-${String(Date.now())}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();
  await page.getByLabel("รหัสผ่านปัจจุบัน").fill(PASSWORD);
  await page.getByTestId("start-totp").click();
  const secret = secretOf(
    (await page.getByTestId("otpauth-uri").textContent()) ?? "",
  );
  await page
    .getByLabel("รหัสจากแอป", { exact: true })
    .fill(codeFor(secret, stepAt(Date.now()) - 1));
  await page.getByTestId("confirm-totp").click();
  await expect(page.getByTestId("totp-state")).toHaveText("เปิดอยู่");
  await page.goto("/api-keys");
  const keys = page.getByTestId("api-key-panel");
  await keys.getByLabel("ชื่อ key").fill("บัญชีทดสอบ F08");
  await keys
    .locator("#api-key-key")
    .fill(`e2e-account-${String(Date.now())}-ABCD`);
  await keys
    .getByLabel("API secret", { exact: true })
    .fill("synthetic-account-secret");
  const keyStep = stepAt(Date.now());
  await keys
    .getByLabel("รหัส TOTP สำหรับเพิ่ม key")
    .fill(codeFor(secret, keyStep));
  await keys.getByRole("button", { name: "เพิ่ม key", exact: true }).click();
  await expect(keys.getByText("กำลังตรวจ", { exact: true })).toBeVisible();
  verify();
  await expect(keys.getByText("ใช้งานได้", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await page.goto("/trading-account");
  const panel = page.getByTestId("trading-account-panel");
  await panel.getByRole("button", { name: "ดึงข้อมูลบัญชีใหม่" }).click();
  await expect(
    panel.getByText("ยังไม่ได้เลือกประเภทการใช้งาน", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByLabel("ประเภทการใช้งานบัญชี")).toHaveValue("");
  await expect(
    panel.getByRole("button", { name: "เลือกประเภทการใช้งาน", exact: true }),
  ).toBeDisabled();
  await panel.getByLabel("ประเภทการใช้งานบัญชี").selectOption("BOT");
  await expect
    .poll(() => stepAt(Date.now()), { timeout: 35000, intervals: [250] })
    .toBeGreaterThan(keyStep);
  await panel
    .getByLabel("รหัส TOTP สำหรับเลือกประเภท")
    .fill(codeFor(secret, stepAt(Date.now())));
  await panel
    .getByRole("button", { name: "เลือกประเภทการใช้งาน", exact: true })
    .click();
  await expect(
    panel.getByText("เลือกประเภทการใช้งานแล้ว", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByRole("heading", { name: "บอท", exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText("บัญชีนี้ยังใช้เทรดไม่ได้", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByLabel("รหัส TOTP สำหรับเลือกประเภท")).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "เริ่มบอท" })).toHaveCount(0);
  await page.reload();
  await expect(
    panel.getByRole("heading", { name: "บอท", exact: true }),
  ).toBeVisible();
  await panel.screenshot({
    path: testInfo.outputPath("trading-account-desktop.png"),
  });
  await page.setViewportSize({ width: 360, height: 812 });
  expect(
    await panel.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  await panel.screenshot({
    path: testInfo.outputPath("trading-account-mobile.png"),
  });
  const menu = page.getByRole("button", { name: "เปิดเมนูบัญชี" });
  await menu.click();
  await expect(menu).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByRole("navigation", { name: "จัดการบัญชี" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await expect(menu).toBeFocused();
  await menu.click();
  await page
    .getByRole("button", { name: "ปิดเมนูบัญชี", exact: true })
    .click({ position: { x: 350, y: 400 } });
  await expect(menu).toBeFocused();
  await page.goto("/api-keys");
  await keys.getByRole("button", { name: "ลบ key", exact: true }).click();
  await keys.getByRole("button", { name: "ยืนยันลบ", exact: true }).click();
  await page.goto("/trading-account");
  await expect(
    panel.getByText("ยังไม่เชื่อมต่อ", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByRole("heading", { name: "บอท", exact: true }),
  ).toBeVisible();
  await expect(panel.getByText("•••• ABCD", { exact: true })).toHaveCount(0);
  expect(
    await page.evaluate(() => [
      Object.keys(window.localStorage),
      Object.keys(window.sessionStorage),
    ]),
  ).toEqual([["theme"], []]);
  await page.goto("/account");
  await page.getByTestId("log-out").click();
  await expect(panel).toBeHidden();
  await expect(page.getByTestId("submit")).toBeEnabled();
  await expect.poll(() => page.getByTestId("submit").evaluate((element) => {
      const style = window.getComputedStyle(element);
      return [
        style.fontFamily,
        style.fontSize,
        style.borderRadius,
        style.backgroundColor,
      ];
    }),
  ).toEqual(authStyle);
  expect(errors).toEqual([]);
});
