import { createInstance } from "i18next";

const th = {
  heading: "API key",
  oneKey: "เก็บ API key ได้หนึ่งชุดต่อบัญชี ต้องลบชุดเดิมก่อนเพิ่มใหม่",
  name: "ชื่อ key",
  key: "API key",
  secret: "API secret",
  totp: "รหัส TOTP สำหรับเพิ่ม key",
  add: "เพิ่ม key",
  adding: "กำลังเพิ่ม…",
  list: "รายการ API key",
  loading: "กำลังดึงรายการ API key…",
  empty: "ยังไม่มี API key เพิ่ม key เพื่อให้ระบบตรวจการเชื่อมต่อบัญชี",
  spotWarning:
    "ต้องติ๊ก Enable Spot Trading เมื่อสร้าง key ที่ Binance TH ระบบตรวจสิทธิ์เทรดแทนไม่ได้",
  whitelistWarning:
    "แนะนำให้เปิด whitelist ที่อยู่ถอนเงินที่ Binance TH เพื่อช่วยจำกัดความเสี่ยง",
  totpHelp:
    "ต้องยืนยัน TOTP ซ้ำทุกครั้ง รหัสสำรองใช้แทนไม่ได้ หากใช้รหัสนี้ไปแล้วให้รอรหัสชุดใหม่",
  enableTotp: "เปิดการยืนยันสองชั้นก่อนเพิ่ม key",
  totpRequired: "บัญชีนี้ยังไม่ได้เปิด TOTP จึงเพิ่ม key ไม่ได้",
  pending: "กำลังตรวจ",
  active: "ใช้งานได้",
  rejected: "ตรวจไม่ผ่าน",
  unverifiable: "ตรวจไม่ได้ ลองใหม่ได้",
  unknown: "ไม่รู้สถานะ — ดึงรายการใหม่ก่อนทำต่อ",
  retry: "ลองใหม่",
  remove: "ลบ key",
  confirmation: "ยืนยันการลบ key",
  confirmDelete: "ยืนยันลบ",
  cancel: "ยกเลิก",
  deleteHelp:
    "ลบ {{name}} ({{tail}}) ออกจากระบบหรือไม่? เมื่อลบแล้วต้องกรอก key ใหม่จึงใช้ได้อีก",
  created: "เพิ่มเมื่อ {{at}}",
  verified: "ตรวจผ่านเมื่อ {{at}}",
  waitUntil: "ตลาดให้รอถึง {{at}}",
  nextAttempt: "ระบบจะลองตรวจอีกครั้งหลัง {{at}}",
  noTime: "ไม่ทราบเวลา",
  added: "เพิ่ม key แล้ว กำลังรอตรวจ",
  retried: "ส่งคำขอตรวจใหม่แล้ว",
  deleted: "ลบ key แล้ว",
  refresh: "ดึงรายการใหม่",
  stale: "ดึงข้อมูลล่าสุดไม่ได้ รายการที่แสดงอาจไม่ตรงกับสถานะปัจจุบัน",
  refreshUnconfirmed: "ยังยืนยันข้อมูลล่าสุดไม่ได้ รายการที่แสดงอาจไม่ตรงกับสถานะปัจจุบัน กรุณาดึงรายการใหม่ก่อนทำต่อ",
  unauthorized: "session หมดอายุ กรุณาเข้าสู่ระบบใหม่",
  forbidden: "ยืนยัน TOTP ไม่ผ่าน หากใช้รหัสเดิมไปแล้วให้รอรหัสชุดใหม่",
  invalid:
    "ข้อมูลไม่ถูกต้อง ตรวจชื่อ key และข้อมูลที่กรอก แล้วกรอกคำรับรองใหม่",
  conflict: "ทำรายการไม่ได้ ตรวจชื่อ จำนวน key และสถานะล่าสุดก่อนลองอีกครั้ง",
  missing: "ไม่พบ key นี้ ดึงรายการใหม่ก่อนทำต่อ",
  limited: "คำขอถูกจำกัด ลองได้อีกครั้งหลัง {{at}}",
  limitedUnknown: "คำขอถูกจำกัด กรุณารอแล้วดึงรายการใหม่",
  uncertain: "ยังยืนยันผลคำขอไม่ได้ กรุณาตรวจรายการก่อนเพิ่มซ้ำ",
  expired: "หมดเวลาตรวจ 24 ชั่วโมงแล้ว ต้องเพิ่ม key ใหม่",
  badCredential: "คำรับรองไม่ผ่านการตรวจ ตรวจข้อมูลที่ตลาดแล้วเพิ่ม key ใหม่",
  temporary: "ระบบจะตรวจใหม่อัตโนมัติ หรือกดลองใหม่เมื่อถึงเวลาที่อนุญาต",
  manualRetry:
    "คำขอถูกปฏิเสธโดยยังไม่ทราบสาเหตุ ระบบระงับการตรวจอัตโนมัติและแจ้งผู้ดูแลแล้ว คุณกดลองใหม่ได้เมื่อถึงเวลาที่อนุญาต",
  tail: "•••• {{tail}}",
};
const en: typeof th = {
  heading: "API keys",
  oneKey:
    "One API key per account. Delete the existing key before adding another.",
  name: "Key name",
  key: "API key",
  secret: "API secret",
  totp: "TOTP code for adding a key",
  add: "Add key",
  adding: "Adding…",
  list: "API keys",
  loading: "Loading API keys…",
  empty: "No API keys yet. Add one to verify your account connection.",
  spotWarning:
    "Enable Spot Trading when creating the key at Binance TH. This system cannot verify trading permission.",
  whitelistWarning:
    "Consider enabling the withdrawal address whitelist at Binance TH to help limit risk.",
  totpHelp:
    "Confirm TOTP for every addition. Recovery codes are not accepted. Wait for a new code if this one was already used.",
  enableTotp: "Enable two-factor authentication before adding a key",
  totpRequired: "TOTP is not enabled, so this account cannot add a key.",
  pending: "Checking",
  active: "Usable",
  rejected: "Rejected",
  unverifiable: "Unable to verify; retry available",
  unknown: "Unknown status — refresh before continuing",
  retry: "Retry",
  remove: "Delete key",
  confirmation: "Confirm key deletion",
  confirmDelete: "Confirm delete",
  cancel: "Cancel",
  deleteHelp:
    "Delete {{name}} ({{tail}})? You will need to enter the key again to use it.",
  created: "Added {{at}}",
  verified: "Verified {{at}}",
  waitUntil: "Exchange asks you to wait until {{at}}",
  nextAttempt: "Automatic retry after {{at}}",
  noTime: "Time unavailable",
  added: "Key added; awaiting verification",
  retried: "Verification requested",
  deleted: "Key deleted",
  refresh: "Refresh list",
  stale: "Could not refresh. The displayed list may be out of date.",
  refreshUnconfirmed: "The latest data could not be confirmed. The displayed list may be out of date. Refresh before continuing.",
  unauthorized: "Session expired. Sign in again.",
  forbidden:
    "TOTP confirmation failed. Wait for a new code if the previous one was already used.",
  invalid: "Check the key name and input, then enter credentials again.",
  conflict: "Check the name, key count and current status before retrying.",
  missing: "Key not found. Refresh before continuing.",
  limited: "Request limited. Try again after {{at}}",
  limitedUnknown: "Request limited. Wait and refresh the list.",
  uncertain:
    "The request result is uncertain. Check the list before adding again.",
  expired: "The 24-hour verification deadline passed. Add a new key.",
  badCredential:
    "Credentials were rejected. Check them at the exchange and add a new key.",
  temporary:
    "Verification retries automatically, or you may retry when allowed.",
  manualRetry:
    "The request was rejected without confirming a credential problem. Automatic verification is paused and operators have been notified. You may retry when allowed.",
  tail: "•••• {{tail}}",
};

export const apiKeyI18n = createInstance();
void apiKeyI18n.init({
  lng: "th",
  fallbackLng: "en",
  initAsync: false,
  resources: { th: { translation: th }, en: { translation: en } },
  interpolation: { escapeValue: false },
});
export const keyText = apiKeyI18n.t.bind(apiKeyI18n);
export function keyTime(value: string | null | undefined): string {
  if (!value || !Number.isFinite(Date.parse(value))) return keyText("noTime");
  return new Intl.DateTimeFormat(apiKeyI18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function keyState(status: string): string {
  switch (status) {
    case "PENDING":
      return keyText("pending");
    case "ACTIVE":
      return keyText("active");
    case "REJECTED":
      return keyText("rejected");
    case "UNVERIFIABLE":
      return keyText("unverifiable");
    default:
      return keyText("unknown");
  }
}
