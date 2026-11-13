import { manualOrderLocale } from "./manualOrderMessages";

const en = {
  title: "Paper Spot", strategy: "Choose a bot", budget: "Total budget (USDT)",
  start: "Start bot", unavailable: "Bot trading is not available yet",
  notice: "You can prepare a budget here. No bot or order will be started.",
  loading: "Loading balance…", updating: "Updating…", reduce: "Reduce / close holdings", sell: "Submit Paper sell request",
};
const th: typeof en = {
  title: "Paper Spot", strategy: "เลือกบอท", budget: "งบรวม (USDT)",
  start: "เริ่มบอท", unavailable: "ระบบบอทยังไม่เปิดใช้งาน",
  notice: "กรอกงบเพื่อเตรียมไว้ได้ ยังไม่มีการเริ่มบอทหรือส่งออเดอร์",
  loading: "กำลังโหลดข้อมูลยอดเงิน…", updating: "กำลังอัปเดต…", reduce: "ลด/ปิดสถานะ", sell: "ส่งคำขอขาย Paper",
};
export const paperBotText = (key: keyof typeof en) => (manualOrderLocale() === "en" ? en : th)[key];
