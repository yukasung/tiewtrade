import { createInstance } from "i18next";

const th = {
  heading: "กระเป๋า Paper",
  description: "เงินจำลองแยกจากเงินจริงและไม่ส่งคำสั่งไปตลาด",
  initialCapital: "ทุนตั้งต้น (USDT)",
  capitalHelp: "ระบุจำนวนมากกว่า 1,000 USDT",
  create: "สร้างกระเป๋า Paper",
  creating: "กำลังส่งคำขอ…",
  pending: "รับคำขอแล้ว กำลังสร้างกระเป๋า…",
  retry: "ลองส่งคำขอเดิมอีกครั้ง",
  loading: "กำลังอ่านกระเป๋า Paper…",
  refresh: "ดึงข้อมูลล่าสุด",
  mode: "โหมด",
  balance: "ยอดคงเหลือ",
  capital: "ทุนตั้งต้น",
  episode: "รอบ",
  started: "เริ่มรอบ",
  snapshot: "ข้อมูล ณ",
  reset: "เริ่มรอบใหม่",
  resetUnavailable: "ยังเริ่มรอบใหม่ไม่ได้ เพราะระบบยังตรวจสอบ position และออเดอร์ค้างได้ไม่ครบ",
  stale: "ดึงข้อมูลล่าสุดไม่ได้ ยอดที่แสดงเป็น snapshot ก่อนหน้า",
  loadError: "ดึงข้อมูลกระเป๋า Paper ไม่ได้ กรุณาลองใหม่",
  unauthorized: "session หมดอายุ กรุณาเข้าสู่ระบบใหม่",
  invalid: "จำนวนเงินไม่ถูกต้อง กรุณาระบุเป็นข้อความตัวเลข USDT",
  tooSmall: "ทุนตั้งต้นต้องมากกว่า 1,000 USDT",
  exists: "มีกระเป๋า Paper อยู่แล้ว กรุณาดึงข้อมูลล่าสุด",
  conflict: "คำขอซ้ำมีข้อมูลต่างจากเดิม กรุณาสร้างคำขอใหม่",
  limited: "ส่งคำขอบ่อยเกินไป กรุณารอก่อนลองอีกครั้ง",
  uncertain: "ยังยืนยันผลคำขอไม่ได้ คุณสามารถลองส่งคำขอเดิมอีกครั้งได้อย่างปลอดภัย",
};

const en: typeof th = {
  heading: "Paper wallet",
  description: "Simulated funds stay separate from real funds and never reach an exchange.",
  initialCapital: "Initial capital (USDT)",
  capitalHelp: "Enter an amount greater than 1,000 USDT.",
  create: "Create Paper wallet",
  creating: "Submitting…",
  pending: "Request accepted. Creating the wallet…",
  retry: "Retry the same request",
  loading: "Loading Paper wallet…",
  refresh: "Refresh",
  mode: "Mode",
  balance: "Balance",
  capital: "Initial capital",
  episode: "Episode",
  started: "Started",
  snapshot: "Snapshot at",
  reset: "Start a new episode",
  resetUnavailable: "A new episode is unavailable until positions and open orders can be verified.",
  stale: "Refresh failed. The displayed balance is an older snapshot.",
  loadError: "The Paper wallet could not be loaded. Try again.",
  unauthorized: "Your session expired. Sign in again.",
  invalid: "Enter the USDT amount as valid decimal text.",
  tooSmall: "Initial capital must be greater than 1,000 USDT.",
  exists: "A Paper wallet already exists. Refresh to view it.",
  conflict: "This request key was already used with different data. Start a new request.",
  limited: "Too many requests. Wait before trying again.",
  uncertain: "The result is uncertain. You can safely retry the same request.",
};

const messages = createInstance();
void messages.init({
  lng: globalThis.navigator.language.startsWith("th") ? "th" : "en",
  fallbackLng: "th",
  initAsync: false,
  resources: { th: { translation: th }, en: { translation: en } },
  interpolation: { escapeValue: false },
});

export const paperWalletText = messages.t.bind(messages);
export const paperWalletLocale = messages.language;
