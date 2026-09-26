import { expect, test } from "@playwright/test";

test("หน้าเว็บแสดงข้อมูลที่ได้จาก API จริง", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "TiewTrade" })).toBeVisible();

  // ต้องเป็นข้อมูลจาก API ไม่ใช่ข้อความที่ฝังไว้ในหน้า
  await expect(page.getByTestId("status")).toHaveText("ok");
  await expect(page.getByTestId("version")).toHaveText("0.1.0");

  const serverTime = await page.getByTestId("server-time").textContent();
  expect(serverTime).toBeTruthy();
  expect(Number.isNaN(Date.parse(serverTime ?? ""))).toBe(false);
});
