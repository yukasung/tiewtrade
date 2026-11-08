import { createInstance } from "i18next";
export const killSwitchI18n = createInstance();
const en = {
  checkingPrevious: "Checking previous stop request…",
  storageUnavailable: "Browser storage is unavailable. Stop can still be requested; after reload, verify the server stop status before acting again.",
  paperStop: "Stop Paper bot", liveStop: "Stop Live bot", details: "View details", close: "Close", loading: "Checking stop status…",
  STOPPING: "Stopping", STOPPED: "Stopped", PROBLEMS: "Problems", pending: "pending", failed: "failed", reconciledAt: "Reconciled at",
  retry: "Retry the same stop request", requestFailed: "The stop outcome is unknown. Retry uses the same request key.",
  platformTitle: "Platform trading stop", platformMessage: "Opening orders are blocked by the platform", summary: "Stop summary", positions: "Open positions", noPositions: "No open positions", resume: "Resume bot", resumePending: "The resume request is being checked", resumeUnavailable: "Resume is unavailable until reconciliation and all stop effects are complete.", liveUnavailable: "Live execution is not available; target discovery remains incomplete.",
  lossTitle: "Loss-limit stop", lossMessage: "Opening remains blocked until the loss-limit cause is reset and resumed from its stop summary.",
  systemTitle: "System trading stop", systemMessage: "Opening remains blocked until recovery is verified and this stop is resumed.",
  adminTitle: "System safety", reason: "Reason shown to users", platformStop: "Stop the platform", platformResume: "Resume the platform", ownerOnly: "Only a Platform Owner can resume.",
};
const th: typeof en = {
  checkingPrevious: "กำลังตรวจคำขอหยุดเดิม…",
  storageUnavailable: "เบราว์เซอร์บันทึกคำขอไม่ได้ แต่ยังส่งคำขอหยุดได้ หลังโหลดหน้าใหม่ให้ตรวจสถานะจากระบบก่อนทำรายการต่อ",
  paperStop: "หยุดบอท Paper", liveStop: "หยุดบอท Live", details: "ดูรายละเอียด", close: "ปิด", loading: "กำลังตรวจสถานะหยุด…",
  STOPPING: "กำลังหยุด", STOPPED: "หยุดแล้ว", PROBLEMS: "หยุดแล้วแต่มีปัญหา", pending: "ค้าง", failed: "ล้มเหลว", reconciledAt: "กระทบยอดเมื่อ",
  retry: "ส่งคำขอหยุดเดิมซ้ำ", requestFailed: "ยังไม่ทราบผลการหยุด การลองอีกครั้งจะใช้ request key เดิม",
  platformTitle: "ระบบหยุดการเทรดทั้งแพลตฟอร์ม", platformMessage: "แพลตฟอร์มกำลังบล็อกออเดอร์เพิ่มความเสี่ยง", summary: "สรุปการหยุด", positions: "สถานะที่ยังถือ", noPositions: "ไม่มีสถานะที่ถือ", resume: "เปิดบอทกลับ", resumePending: "ระบบกำลังตรวจคำขอเปิดกลับ", resumeUnavailable: "ยังเปิดกลับไม่ได้จนกว่าจะกระทบยอดและจัดการงานหยุดครบ", liveUnavailable: "Live execution ยังไม่พร้อม การค้นหาเป้าหมายจึงยังไม่ถือว่าครบ",
  lossTitle: "หยุดเพราะถึงเพดานขาดทุน", lossMessage: "ออเดอร์เปิดยังถูกบล็อกจนกว่าจะรีเซ็ตสาเหตุและเปิดกลับจากหน้าสรุปการหยุด",
  systemTitle: "หยุดการเทรดโดยระบบ", systemMessage: "ออเดอร์เปิดยังถูกบล็อกจนกว่าระบบยืนยันการกู้คืนและเปิดกลับจากหน้าสรุปการหยุด",
  adminTitle: "ความปลอดภัยระบบ", reason: "เหตุผลที่แสดงต่อผู้ใช้", platformStop: "หยุดทั้งแพลตฟอร์ม", platformResume: "เปิดแพลตฟอร์มกลับ", ownerOnly: "เฉพาะ Platform Owner เท่านั้นที่เปิดกลับได้",
};
void killSwitchI18n.init({ lng: "th", fallbackLng: "th", initAsync: false, resources: { th: { translation: th }, en: { translation: en } }, interpolation: { escapeValue: false } });
export const killSwitchText = killSwitchI18n.t.bind(killSwitchI18n);
