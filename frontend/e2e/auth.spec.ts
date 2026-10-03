import { expect, test } from "@playwright/test";

/**
 * เส้นทางยืนยันตัวตนบนเบราว์เซอร์จริง (F-05 validation V-56.1)
 *
 * พิสูจน์ของที่เทสต์ย่อยพิสูจน์ไม่ได้: cookie เดินทางจริง, โทเคนกัน CSRF ถูกส่งกลับ
 * และสถานะบนหน้าจอเปลี่ยนตามความจริงที่หลังบ้านบอก
 */
test("สมัคร เข้าสู่ระบบ แล้วออกจากระบบได้บนเบราว์เซอร์จริง", async ({ page }) => {
  const email = `e2e-${String(Date.now())}@example.com`;
  const password = "รหัสผ่านที่ยาวพอใช้งานจริง";

  await page.goto("/");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน").fill(password);
  await page.getByTestId("submit").click();

  await expect(page.getByTestId("signed-in")).toBeVisible();
  const userId = await page.getByTestId("user-id").textContent();
  expect(userId).toMatch(/^[0-9a-f-]{36}$/);

  await page.getByTestId("log-out").click();
  await expect(page.getByTestId("signed-out")).toBeVisible();

  // เข้าสู่ระบบอีกครั้งด้วยบัญชีเดิมต้องได้ผู้ใช้คนเดียวกัน
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน").fill(password);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("user-id")).toHaveText(userId ?? "");
});

test("บอกเหตุผลเมื่อรหัสผ่านไม่ถูกต้อง และไม่พาเข้าระบบ", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("อีเมล").fill("nobody-e2e@example.com");
  await page.getByLabel("รหัสผ่าน").fill("รหัสผ่านที่ไม่ถูกต้องเลย");
  await page.getByTestId("submit").click();

  await expect(page.getByTestId("refusal")).toHaveText("อีเมลหรือรหัสผ่านไม่ถูกต้อง");
  await expect(page.getByTestId("signed-out")).toBeVisible();
});
