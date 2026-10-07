import { captureUi } from "./helpers/ui";
import { expect, test } from "./helpers/test";

/**
 * เส้นทางยืนยันตัวตนบนเบราว์เซอร์จริง (F-05 validation V-56.1)
 *
 * พิสูจน์ของที่เทสต์ย่อยพิสูจน์ไม่ได้: cookie เดินทางจริง, โทเคนกัน CSRF ถูกส่งกลับ
 * และสถานะบนหน้าจอเปลี่ยนตามความจริงที่หลังบ้านบอก
 */
test("สมัคร เข้าสู่ระบบ แล้วออกจากระบบได้บนเบราว์เซอร์จริง", async ({
  page,
}, testInfo) => {
  const email = `e2e-${String(Date.now())}@example.com`;
  const password = "รหัสผ่านที่ยาวพอใช้งานจริง";

  await page.goto("/");
  await expect(page.locator(".auth-layout")).toBeVisible();
  await expect(page.getByTestId("submit")).toHaveClass(/account-button/);
  await page.getByRole("link", { name: "TiewTrade" }).focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("อีเมล")).toBeFocused();
  expect(
    await page
      .getByLabel("อีเมล")
      .evaluate((element) => window.getComputedStyle(element).outlineStyle),
  ).toBe("solid");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("รหัสผ่าน")).toBeFocused();
  await captureUi(page, testInfo, "login");
  await page.getByTestId("switch-mode").click();
  await captureUi(page, testInfo, "register");
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน").fill(password);
  let releaseRegistration = () => {};
  const registrationGate = new Promise<void>((resolve) => {
    releaseRegistration = resolve;
  });
  await page.route("**/api/auth/register", async (route) => {
    await registrationGate;
    await route.continue();
  });
  try {
    await page.getByTestId("submit").click();
    await expect(page.getByTestId("submit")).toBeDisabled();
    expect(
      await page
        .getByTestId("submit")
        .evaluate((element) => window.getComputedStyle(element).opacity),
    ).toBe("0.6");
    await captureUi(page, testInfo, "register-pending");
  } finally {
    releaseRegistration();
  }

  await expect(page.getByTestId("signed-in")).toBeVisible();
  await page.unroute("**/api/auth/register");
  await captureUi(page, testInfo, "account");
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

test("บอกเหตุผลเมื่อรหัสผ่านไม่ถูกต้อง และไม่พาเข้าระบบ", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await page.getByLabel("อีเมล").fill("nobody-e2e@example.com");
  await page.getByLabel("รหัสผ่าน").fill("รหัสผ่านที่ไม่ถูกต้องเลย");
  await page.getByTestId("submit").click();

  await expect(page.getByTestId("refusal")).toHaveText(
    "อีเมลหรือรหัสผ่านไม่ถูกต้อง",
  );
  await expect(page.getByTestId("signed-out")).toBeVisible();
  await captureUi(page, testInfo, "auth-error");
});
