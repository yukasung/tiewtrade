import { expect, test } from "./helpers/test";

test("หน้าเว็บแสดงข้อมูลที่ได้จาก API จริง", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "TiewTrade" })).toBeVisible();

  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(page.locator('footer[aria-label="สถานะระบบ"]')).toBeVisible();

  // ต้องเป็นข้อมูลจาก API ไม่ใช่ข้อความที่ฝังไว้ในหน้า
  await expect(page.getByTestId("status")).toHaveText("ok");
  // ไม่ผูกกับเลขรุ่นที่เขียนไว้ เพราะรุ่นเปลี่ยนตามงาน — ที่ต้องพิสูจน์คือค่ามาจาก API
  await expect(page.getByTestId("version")).toHaveText(/^\d+\.\d+\.\d+$/);

  const serverTime = await page.getByTestId("server-time").textContent();
  expect(serverTime).toBeTruthy();
  expect(Number.isNaN(Date.parse(serverTime ?? ""))).toBe(false);
});
