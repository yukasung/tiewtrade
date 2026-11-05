import { manualOrderLocale } from "./manualOrderMessages";
const words = {
  title: ["TP / SL", "TP / SL"], create: ["ตั้ง TP/SL ให้เหรียญที่ถือ", "Protect held assets"],
  quantity: ["จำนวนเหรียญ", "Quantity"], tp: ["ราคา Take Profit", "Take profit price"], sl: ["ราคา Stop Loss", "Stop loss price"],
  save: ["บันทึก", "Save"], edit: ["แก้ไข", "Edit"], cancel: ["ยกเลิกการป้องกัน", "Cancel protection"], close: ["ปิด", "Close"],
  remaining: ["ปริมาณที่ผูกไว้", "Allocated quantity"], covered: ["ปริมาณที่ป้องกันแล้ว", "Protected quantity"],
  exit: ["ออเดอร์ปิดล่าสุด", "Latest exit order"], exitFilled: ["ปริมาณที่ปิดแล้ว", "Exit filled quantity"],
  unknown: ["ยังไม่ทราบผล กำลังตรวจสอบคำขอเดิม", "Outcome unknown; checking the original request"],
  check: ["ตรวจผลเดิม", "Check original request"], retry: ["ส่งคำขอเดิมอีกครั้ง", "Retry original request"],
  failed: ["ดำเนินการไม่ได้ ตรวจข้อมูลล่าสุดแล้วลองใหม่", "Unable to apply; refresh and check current data"],
  unavailable: ["ข้อมูลหรือการเฝ้าราคายังไม่พร้อม", "Data or price monitoring unavailable"],
  warning: ["เหรียญส่วนที่เลือกขายจะออกจาก TP/SL เดิม เมื่อยกเลิกขาย ส่วนที่ขายไม่ออกจะไม่มี TP/SL ต้องตั้งใหม่เอง", "Selected assets leave their TP/SL when the sale is admitted. Canceling the sale will not restore protection; set it again for unsold assets."],
  release: ["จำนวนที่จะนำออกจากชุดนี้เพื่อขาย", "Quantity to release from this protection for sale"],
  storage: ["บันทึกคำขอในเบราว์เซอร์ไม่ได้ โปรดตรวจคำขอค้างก่อนดำเนินการ", "Cannot save request recovery information; check pending requests"],
  WAITING_ENTRY: ["รอออเดอร์เข้า", "Waiting for entry"], ARMING: ["กำลังตั้งการป้องกัน", "Setting protection"],
  ARMED: ["กำลังเฝ้าราคา", "Monitoring price"], EXITING: ["กำลังดำเนินคำสั่งปิด", "Exit in progress"],
  CLOSED: ["ปิดครบแล้ว", "Closed"], CANCELED: ["ยกเลิกการป้องกันแล้ว", "Protection canceled"], FAILED: ["มีปริมาณที่ยังไม่ป้องกัน", "Unprotected quantity remains"],
  conflict: ["ข้อมูลขัดกัน ต้องกระทบยอดและจัดสรรใหม่", "Conflicting data; reconcile and reallocate"],
  pending: ["มีคำขอที่กำลังดำเนินการ", "A request is pending"], empty: ["ยังไม่มี TP/SL", "No protections"],
  unprotected: ["พร้อมใช้และไม่มี TP/SL", "Available without TP/SL"],
} as const;
export function protectionText(key: keyof typeof words): string { return words[key][manualOrderLocale().startsWith("th") ? 0 : 1]; }
