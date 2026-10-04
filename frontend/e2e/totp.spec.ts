import { createHmac } from "node:crypto";
import { Buffer } from "node:buffer";

import { expect, test } from "@playwright/test";

/**
 * การยืนยันสองชั้นบนเบราว์เซอร์จริง (F-06 validation M-2)
 *
 * พิสูจน์ของที่เทสต์ย่อยพิสูจน์ไม่ได้: cookie ของ challenge เดินทางจริง,
 * มันไม่ได้กลายเป็น session และหน้าจอขอขั้นที่สองจริงก่อนปล่อยเข้า
 *
 * **เทสต์คำนวณรหัสเองจาก secret ใน URI** คือทำตัวเหมือนแอป authenticator
 * ไม่ใช่เรียกฟังก์ชันของหลังบ้าน — ถ้าเรียกของหลังบ้าน เทสต์จะผ่านแม้สองฝั่ง
 * คิดอัลกอริทึมเหมือนกันผิด ๆ
 */

const PASSWORD = "รหัสผ่านที่ยาวพอใช้งานจริง";

/** ลำดับช่วงเวลาของ TOTP ณ เวลานั้น — ช่วงละ 30 วินาทีตาม RFC 6238 */
function stepAt(moment: number): number {
  return Math.floor(moment / 1000 / 30);
}

/** รหัสหกหลักจาก secret และลำดับช่วงเวลา — HOTP ของ RFC 4226 */
function codeFor(secret: Buffer, step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", secret).update(counter).digest();
  const offset = (digest.at(-1) ?? 0) & 0x0f;
  const chunk = digest.readUInt32BE(offset) & 0x7fffffff;
  return String(chunk).padStart(6, "0").slice(-6);
}

/** secret ที่อยู่ใน otpauth URI */
function secretOf(uri: string): Buffer {
  const encoded = (uri.split("secret=")[1] ?? "").split("&")[0] ?? "";
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const letter of encoded) {
    bits += alphabet.indexOf(letter).toString(2).padStart(5, "0");
  }
  const bytes: number[] = [];
  for (let at = 0; at + 8 <= bits.length; at += 8) {
    bytes.push(Number.parseInt(bits.slice(at, at + 8), 2));
  }
  return Buffer.from(bytes);
}

test("เปิดการยืนยันสองชั้น แล้วเข้าสู่ระบบต้องผ่านสองขั้น", async ({ page }) => {
  const email = `e2e-totp-${String(Date.now())}@example.com`;

  await page.goto("/");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน").fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();

  // ── เปิดใช้ ──
  await expect(page.getByTestId("totp-state")).toHaveText("ปิดอยู่");
  await page.getByLabel("รหัสผ่านปัจจุบัน").fill(PASSWORD);
  await page.getByTestId("start-totp").click();

  // **QR ต้องมีจริงบนเบราว์เซอร์** ไม่ใช่แค่มีโค้ดที่สร้างมัน (plan หัวข้อ 9)
  await expect(page.getByTestId("otpauth-qr")).toBeVisible();

  const uri = await page.getByTestId("otpauth-uri").textContent();
  expect(uri).toContain("otpauth://totp/");
  const secret = secretOf(uri ?? "");

  // ยืนยันด้วยรหัสของ **ช่วงก่อนหน้า** ซึ่งยังอยู่ในหน้าต่างที่ระบบยอมรับ
  // เพื่อให้รหัสของช่วงปัจจุบันเหลือไว้ใช้ตอนเข้าสู่ระบบ — RQ-4 ห้ามใช้รหัสซ้ำ
  await page.getByLabel("รหัสจากแอป").fill(codeFor(secret, stepAt(Date.now()) - 1));
  await page.getByTestId("confirm-totp").click();

  await expect(page.getByTestId("recovery-codes")).toBeVisible();
  await expect(page.getByTestId("totp-state")).toHaveText("เปิดอยู่");

  // ── เข้าสู่ระบบใหม่ต้องผ่านสองขั้น ──
  await page.getByTestId("log-out").click();
  await expect(page.getByTestId("signed-out")).toBeVisible();

  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน").fill(PASSWORD);
  await page.getByTestId("submit").click();

  // **รหัสผ่านถูกแล้วยังไม่เข้า** — หน้าจอขอขั้นที่สอง
  await expect(page.getByTestId("second-step")).toBeVisible();
  await expect(page.getByTestId("signed-in")).toBeHidden();

  await page.getByLabel("รหัสจากแอป").fill(codeFor(secret, stepAt(Date.now())));
  await page.getByTestId("submit-second-step").click();

  await expect(page.getByTestId("signed-in")).toBeVisible();
});

test("รหัสยืนยันผิดไม่พาเข้าระบบ และยังอยู่ที่ขั้นที่สอง", async ({ page }) => {
  const email = `e2e-totp-bad-${String(Date.now())}@example.com`;

  await page.goto("/");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน").fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();

  await page.getByLabel("รหัสผ่านปัจจุบัน").fill(PASSWORD);
  await page.getByTestId("start-totp").click();
  const uri = await page.getByTestId("otpauth-uri").textContent();
  const secret = secretOf(uri ?? "");
  await page.getByLabel("รหัสจากแอป").fill(codeFor(secret, stepAt(Date.now()) - 1));
  await page.getByTestId("confirm-totp").click();
  await expect(page.getByTestId("totp-state")).toHaveText("เปิดอยู่");

  await page.getByTestId("log-out").click();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน").fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("second-step")).toBeVisible();

  await page.getByLabel("รหัสจากแอป").fill("000000");
  await page.getByTestId("submit-second-step").click();

  await expect(page.getByTestId("refusal")).toHaveText("รหัสยืนยันไม่ถูกต้อง");
  // ลองใหม่ได้โดยไม่ต้องกรอกรหัสผ่านอีก — challenge ยังอยู่ (V-24.1)
  await expect(page.getByTestId("second-step")).toBeVisible();
});
