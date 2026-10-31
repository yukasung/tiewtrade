import { createInstance } from "i18next";
const th = {
  heading: "บัญชีเทรด",
  limitation: "Paper Trading ใช้เงินจำลองและไม่เปิด Live Trading โดยอัตโนมัติ",
  unselected: "ยังไม่ได้เลือกประเภทการใช้งาน",
  use: "ประเภทการใช้งานบัญชี",
  placeholder: "เลือกประเภท",
  manual: "เทรดมือ",
  bot: "บอท",
  select: "เลือกประเภทการใช้งาน",
  selecting: "กำลังเลือก…",
  selected: "เลือกประเภทการใช้งานแล้ว",
  paperReadyTitle: "Paper Trading ไม่ต้องใช้ API key หรือ 2FA",
  paperReady:
    "เลือกเทรดมือหรือบอทเพื่อทดลองด้วยเงินจำลองได้ การเพิ่ม API key และ 2FA จะจำเป็นเมื่อเตรียมใช้ Live Trading",
  prepareLive: "ตั้งค่า 2FA สำหรับ Live",
  disconnected: "ยังไม่เชื่อมต่อ",
  loading: "กำลังดึงข้อมูลบัญชี…",
  refresh: "ดึงข้อมูลบัญชีใหม่",
  change: "เปลี่ยนประเภท",
  immutable:
    "ยังเปลี่ยนประเภทไม่ได้ เพราะยังไม่มีหลักฐานสถานะบอท ออเดอร์ และ position ครบ",
  stale: "ดึงข้อมูลล่าสุดไม่ได้ ข้อมูลบัญชีที่แสดงอาจไม่ตรงกับสถานะปัจจุบัน",
  unauthorized: "session หมดอายุ กรุณาเข้าสู่ระบบใหม่",
  forbidden: "คำขอไม่ได้รับอนุญาต กรุณาโหลดหน้าใหม่แล้วลองอีกครั้ง",
  invalid: "ข้อมูลไม่ถูกต้อง ตรวจประเภทการใช้งานแล้วลองอีกครั้ง",
  unavailable: "ข้อมูลบัญชียังไม่พร้อม กรุณาดึงข้อมูลล่าสุดแล้วลองอีกครั้ง",
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
