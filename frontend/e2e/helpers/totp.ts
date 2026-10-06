import { createHmac } from "node:crypto";
import { Buffer } from "node:buffer";

export const PASSWORD = "รหัสผ่านที่ยาวพอใช้งานจริง";

/** ลำดับช่วงเวลาของ TOTP ณ เวลานั้น — ช่วงละ 30 วินาทีตาม RFC 6238 */
export function stepAt(moment: number): number {
  return Math.floor(moment / 1000 / 30);
}

/** รหัสหกหลักจาก secret และลำดับช่วงเวลา — HOTP ของ RFC 4226 */
export function codeFor(secret: Buffer, step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", secret).update(counter).digest();
  const offset = (digest.at(-1) ?? 0) & 0x0f;
  const chunk = digest.readUInt32BE(offset) & 0x7fffffff;
  return String(chunk).padStart(6, "0").slice(-6);
}

/** secret ที่อยู่ใน otpauth URI */
export function secretOf(uri: string): Buffer {
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
