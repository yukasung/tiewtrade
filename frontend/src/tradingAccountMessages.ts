import { createInstance } from "i18next";
const th = {
  heading: "บัญชีเทรด",
  limitation: "บัญชีนี้ยังใช้เทรดไม่ได้",
  unselected: "ยังไม่ได้เลือกประเภทการใช้งาน",
  use: "ประเภทการใช้งานบัญชี",
  placeholder: "เลือกประเภท",
  manual: "เทรดมือ",
  bot: "บอท",
  select: "เลือกประเภทการใช้งาน",
  selecting: "กำลังเลือก…",
  selected: "เลือกประเภทการใช้งานแล้ว",
  totp: "รหัส TOTP สำหรับเลือกประเภท",
  totpHelp: "ยืนยันด้วยรหัส TOTP ใหม่ รหัสสำรองใช้แทนไม่ได้",
  totpRequired: "เปิด TOTP ก่อนเลือกประเภทการใช้งาน",
  keyRequired: "เพิ่ม API key แล้วรอผลตรวจให้ใช้งานได้ก่อนเลือกประเภท",
  disconnected: "ยังไม่เชื่อมต่อ",
  loading: "กำลังดึงข้อมูลบัญชี…",
  refresh: "ดึงข้อมูลบัญชีใหม่",
  change: "เปลี่ยนประเภท",
  immutable:
    "ยังเปลี่ยนประเภทไม่ได้ เพราะยังไม่มีหลักฐานสถานะบอท ออเดอร์ และ position ครบ",
  stale: "ดึงข้อมูลล่าสุดไม่ได้ ข้อมูลบัญชีที่แสดงอาจไม่ตรงกับสถานะปัจจุบัน",
  unauthorized: "session หมดอายุ กรุณาเข้าสู่ระบบใหม่",
  forbidden: "ยืนยัน TOTP ไม่ผ่าน หากใช้รหัสเดิมแล้วให้รอรหัสชุดใหม่",
  invalid: "ข้อมูลไม่ถูกต้อง ตรวจประเภทการใช้งานแล้วลองอีกครั้ง",
  unavailable: "API key ยังไม่พร้อม ดึงข้อมูลล่าสุดก่อนลองอีกครั้ง",
  limited: "คำขอถูกจำกัด กรุณารอแล้วดึงข้อมูลใหม่",
  uncertain: "ยังยืนยันผลคำขอไม่ได้ กรุณาตรวจข้อมูลบัญชีก่อนเลือกซ้ำ",
};
const tradingAccountI18n = createInstance();
void tradingAccountI18n.init({
  lng: "th",
  fallbackLng: "th",
  initAsync: false,
  resources: { th: { translation: th } },
  interpolation: { escapeValue: false },
});
export const tradingAccountText = tradingAccountI18n.t.bind(tradingAccountI18n);
