import { e2eEnvironment } from "./helpers/environment";
import { execFileSync } from "node:child_process";
import { expect, test } from "./helpers/test";

import { PASSWORD, codeFor, secretOf, stepAt } from "./helpers/totp";

const PUBLIC = "e2e-only-public-key-ABCD";
const SECRET = "e2e-only-secret-not-a-real-credential";

/** เรียก worker จริงกับ FakeVenue เดิม: ไม่มี HTTP ไปตลาดและไม่แก้สถานะด้วย SQL */
function verify(outcome: "temporary" | "success"): void {
  execFileSync(
    ".venv/bin/python",
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
from tiewtrade.venues.errors import VenueUnavailableError

async def check():
    engine = create_engine_for(DatabaseRole.ENGINE)
    scan = create_engine_for(DatabaseRole.ENGINE_SCAN)
    venue = FakeVenue(holdings=WalletHoldings(received_at=datetime.now(UTC), holdings=()))
    if ${outcome === "temporary" ? "True" : "False"}:
        venue.queue_errors([VenueUnavailableError()])
    try:
        result = await run_round(engine=engine, scan_engine=scan,
            keys=KeySource.from_environment(KeyPurpose.VENUE_API_SECRET),
            wallet_for=lambda signer: venue, worker="e2e-worker")
        assert result.${outcome === "temporary" ? "deferred" : "verified"} == 1, result
    finally:
        await engine.dispose()
        await scan.dispose()
asyncio.run(check())
`,
    ],
    { cwd: "../backend", stdio: "pipe", env: e2eEnvironment() },
  );
}

test("เพิ่ม key ยืนยัน TOTP → ตรวจชั่วคราว → ลองใหม่ → ใช้งานได้ → ลบ", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/security");
  await page.getByTestId("switch-mode").click();
  await page
    .getByLabel("อีเมล")
    .fill(`e2e-key-${String(Date.now())}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();
  await page.getByLabel("รหัสผ่านปัจจุบัน").fill(PASSWORD);
  await page.getByTestId("start-totp").click();
  const uri = await page.getByTestId("otpauth-uri").textContent();
  const secret = secretOf(uri ?? "");
  await page
    .getByLabel("รหัสจากแอป", { exact: true })
    .fill(codeFor(secret, stepAt(Date.now()) - 1));
  await page.getByTestId("confirm-totp").click();
  await expect(page.getByTestId("totp-state")).toHaveText("เปิดอยู่");

  await page.goto("/api-keys");
  const panel = page.getByTestId("api-key-panel");
  await panel.getByLabel("ชื่อ key").fill("กระเป๋าทดสอบ");
  await panel.locator("#api-key-key").fill(PUBLIC);
  await panel.getByLabel("API secret", { exact: true }).fill(SECRET);
  await panel
    .getByLabel("รหัส TOTP สำหรับเพิ่ม key")
    .fill(codeFor(secret, stepAt(Date.now())));
  await panel.getByRole("button", { name: "เพิ่ม key", exact: true }).click();
  await expect(panel.getByText("กำลังตรวจ", { exact: true })).toBeVisible();
  await expect(panel.locator("#api-key-key")).toHaveValue("");
  await expect(panel.getByLabel("API secret", { exact: true })).toHaveValue("");
  await expect(panel).not.toContainText(PUBLIC);
  await expect(panel).not.toContainText(SECRET);
  await expect(panel.getByText("•••• ABCD", { exact: true })).toBeVisible();

  verify("temporary");
  await expect(
    panel.getByText("ตรวจไม่ได้ ลองใหม่ได้", { exact: true }),
  ).toBeVisible({ timeout: 10000 });
  const request = page.waitForRequest(
    (item) => item.method() === "POST" && item.url().endsWith("/retry"),
  );
  await panel.getByRole("button", { name: "ลองใหม่", exact: true }).click();
  expect((await request).headers()).not.toHaveProperty("x-tiewtrade-totp");
  await expect(
    panel.getByText("ส่งคำขอตรวจใหม่แล้ว", { exact: true }),
  ).toBeVisible();
  verify("success");
  await expect(panel.getByText("ใช้งานได้", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(
    panel.getByRole("button", { name: "ลองใหม่", exact: true }),
  ).toBeHidden();
  await panel.screenshot({
    path: testInfo.outputPath("api-keys-desktop.png"),
  });
  await page.setViewportSize({ width: 375, height: 812 });
  expect(
    await panel.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  await expect(panel.getByLabel("API secret", { exact: true })).toHaveValue("");
  await panel.screenshot({
    path: testInfo.outputPath("api-keys-mobile-form.png"),
  });
  expect(
    await page.evaluate(() => [
      Object.keys(window.localStorage),
      Object.keys(window.sessionStorage),
    ]),
  ).toEqual([["theme"], []]);

  await panel.getByRole("button", { name: "ลบ key", exact: true }).click();
  await panel.getByRole("button", { name: "ยืนยันลบ", exact: true }).click();
  await expect(panel.getByText(/ยังไม่มี API key/)).toBeVisible();
  await page.goto("/account");
  await page.getByTestId("log-out").click();
  await expect(panel).toBeHidden();
  expect(errors).toEqual([]);
});

test("มือถือ: บัญชีไม่มี TOTP เห็นทางไปเปิดและไม่มีช่องรับ secret", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/security");
  await page.getByTestId("switch-mode").click();
  await page
    .getByLabel("อีเมล")
    .fill(`e2e-key-mobile-${String(Date.now())}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();
  await page.goto("/api-keys");
  const panel = page.getByTestId("api-key-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel("API secret", { exact: true })).toBeHidden();
  await panel.getByRole("link", { name: /เปิดการยืนยันสองชั้น/ }).click();
  await expect(page.getByTestId("totp-panel")).toBeInViewport();
  await page.goto("/api-keys");
  await expect(panel).toBeVisible();
  expect(
    await panel.evaluate(
      (element) => element.scrollWidth <= element.clientWidth,
    ),
  ).toBe(true);
  await panel.screenshot({
    path: testInfo.outputPath("api-keys-mobile.png"),
  });
});
