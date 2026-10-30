import { createInstance } from "i18next";
export const manualOrderI18n = createInstance();
const en = {
  episodeDraftNotice: "Drafts belong to the current wallet episode. If it changes, enter the order again.",
  episodeClosed: "This request was not recorded: its wallet episode is closed. Enter a new order for the current episode.",
  paper: "Paper trading", live: "Live trading", form: "Manual order", pair: "Pair", choosePair: "Select a pair", side: "Side", kind: "Order type",
  BUY: "BUY", SELL: "SELL", MARKET: "MARKET", LIMIT: "LIMIT", GTC: "GTC", budget: "Quote budget (USDT)", quantity: "Base quantity", price: "Limit price (USDT)", submit: "Submit Paper order",
  refresh: "Refresh", retry: "Retry the same request", check: "Check request status", unknown: "UNKNOWN — outcome not confirmed. Check or retry with the same key.",
  storage: "Recovery storage is unavailable. No new request can be sent.", recovery: "Requests and recovery", recovering: "Checking unresolved requests…", recoveryError: "Unable to check unresolved requests. New requests are blocked.",
  loadError: "Unable to refresh this data. Displayed values may be stale.", unavailable: "Unavailable", noWallet: "Create a Paper wallet in Trading account first.",
  liveUnavailable: "Live trading is unavailable. No order will be sent. Manage any existing Live orders directly at your exchange.",
  blocked: "Order admission is unavailable. The server will validate every request again.", sellCheck: "SELL requests are checked against authoritative holdings after reservations. SELL alone does not mean risk reduction.",
  marketObserved: "Price observation received at",
  latestPrice: "Latest price", marketStatus: "Market data", marketReady: "Ready", marketLoading: "Loading market data…",
  riskSummary: "Loss limit", manageRisk: "Set in Trading account",
  riskStopStatus: "Risk stop status",
  openOrders: "Open orders", orderHistory: "Order history", incompleteResults: "More records are available. Load all pages before treating this view as empty.",
  noOpenOrders: "No open orders in the loaded records.", noOrderHistory: "No order history in the loaded records.",
  balance: "Cash", reserved: "Reserved", available: "Available", held: "Held", snapshot: "Data as of", use: "Account use", orders: "Orders", empty: "No recorded orders in this episode.", more: "Load more", cancel: "Request cancel", details: "Order details", close: "Close", order: "Order", episode: "Episode", original: "Original", filled: "Filled", remaining: "Remaining", spent: "Spent", status: "Order status", intake: "Request status", command: "Command status", failure: "Rejection reason", pendingNotice: "A recorded request is not an accepted or filled order. A cancel request is not a confirmed cancellation.",
  PENDING: "Pending", TRANSFERRED: "Transferred to engine", REJECTED: "Rejected", SUCCEEDED: "Command succeeded", ACCEPTED: "Accepted", PARTIALLY_FILLED: "Partially filled", FILLED: "Filled", CANCELED: "Canceled", EXPIRED: "Expired", UNKNOWN: "Unknown",
  RISK_LIMIT_UNSET: "Set a wallet loss limit before opening orders", RISK_LOSS_LIMIT_REACHED: "Wallet loss limit reached", RISK_SOURCE_UNAVAILABLE: "Risk data is unavailable", RISK_PRICE_UNAVAILABLE: "A risk valuation price is unavailable",
  ORDER_INPUT_INVALID: "Invalid order values", ORDER_CONSTRAINT_VIOLATION: "Order does not satisfy market filters",
  ORDER_SAFETY_UNAVAILABLE: "Risk policy is not ready", MANUAL_USE_REQUIRED: "Opening orders require MANUAL account use", PAPER_WALLET_REQUIRED: "Paper wallet required", ORDER_SOURCE_UNAVAILABLE: "Account data is not ready", ORDER_PAIR_REQUIRED: "Select a pair", CATALOG_PAIR_REMOVED: "Pair is no longer supported for opening orders", ORDER_PRICE_UNAVAILABLE: "Price is unavailable or stale", ORDER_BOOK_UNAVAILABLE: "Order book is unavailable", ORDER_UNSUPPORTED: "Execution rules are unsupported", ORDER_INSUFFICIENT_FUNDS: "Insufficient available funds", EPISODE_CONFLICT: "Wallet episode changed", ORDER_CONFLICT: "Order conflict", limited: "Too many requests. Retry the same request after", safeFailure: "The request was rejected. Check server status before continuing.",
};
const th: typeof en = {
  episodeDraftNotice: "ร่างคำสั่งใช้ได้เฉพาะ episode ปัจจุบัน หากเปลี่ยน episode ต้องกรอกคำสั่งใหม่",
  episodeClosed: "คำขอนี้ไม่ได้ถูกบันทึก เพราะ episode ปิดแล้ว กรุณากรอกคำสั่งใหม่สำหรับ episode ปัจจุบัน",
  paper: "เทรด Paper", live: "เทรด Live", form: "สั่งออเดอร์เอง", pair: "คู่เทรด", choosePair: "เลือกคู่เทรด", side: "ฝั่ง", kind: "ประเภทออเดอร์",
  BUY: "BUY", SELL: "SELL", MARKET: "MARKET", LIMIT: "LIMIT", GTC: "GTC", budget: "งบซื้อ (USDT)", quantity: "จำนวนเหรียญ Base", price: "ราคา Limit (USDT)", submit: "ส่งออเดอร์ Paper",
  refresh: "ตรวจข้อมูลอีกครั้ง", retry: "ส่งคำขอเดิมอีกครั้ง", check: "ตรวจสถานะคำขอ", unknown: "UNKNOWN — ยังยืนยันผลไม่ได้ ตรวจสถานะหรือส่งซ้ำด้วย key เดิม",
  storage: "ใช้พื้นที่กู้คืนคำขอไม่ได้ จึงยังส่งคำขอใหม่ไม่ได้", recovery: "คำขอและผลการตรวจ", recovering: "กำลังตรวจคำขอที่ยังรอผล…", recoveryError: "ตรวจคำขอค้างไม่ได้ จึงยังส่งคำขอใหม่ไม่ได้",
  loadError: "โหลดข้อมูลล่าสุดไม่ได้ ข้อมูลที่แสดงอาจเก่าแล้ว", unavailable: "ไม่พร้อมใช้งาน", noWallet: "สร้างกระเป๋า Paper ในหน้าบัญชีเทรดก่อน",
  liveUnavailable: "Live ยังไม่พร้อมใช้งาน จึงไม่มีการส่งออเดอร์ หากมีออเดอร์ Live อยู่ ให้จัดการโดยตรงที่ตลาด",
  blocked: "ยังรับออเดอร์ไม่ได้ เซิร์ฟเวอร์จะตรวจเงื่อนไขทุกคำขออีกครั้ง", sellCheck: "คำขอ SELL ต้องตรวจยอดถือจริงหลังหักยอดจอง การเลือก SELL ไม่ได้แปลว่าลดความเสี่ยงเสมอ",
  marketObserved: "ได้รับข้อมูลราคาล่าสุด ณ",
  latestPrice: "ราคาล่าสุด", marketStatus: "ข้อมูลตลาด", marketReady: "พร้อม", marketLoading: "กำลังโหลดข้อมูลตลาด…",
  riskSummary: "เพดานขาดทุน", manageRisk: "ตั้งค่าในหน้าบัญชีเทรด",
  riskStopStatus: "สถานะหยุดความเสี่ยง",
  openOrders: "ออเดอร์ที่เปิดอยู่", orderHistory: "ประวัติออเดอร์", incompleteResults: "ยังมีข้อมูลหน้าถัดไป ต้องโหลดให้ครบก่อนสรุปว่าไม่มีรายการ",
  noOpenOrders: "ไม่พบออเดอร์ที่เปิดอยู่ในข้อมูลที่โหลดแล้ว", noOrderHistory: "ไม่พบประวัติออเดอร์ในข้อมูลที่โหลดแล้ว",
  balance: "เงินในกระเป๋า", reserved: "ยอดจอง", available: "ยอดใช้ได้", held: "ยอดถือ", snapshot: "ข้อมูล ณ", use: "ประเภทบัญชี", orders: "ออเดอร์", empty: "ยังไม่มีออเดอร์ที่บันทึกใน episode นี้", more: "โหลดเพิ่มเติม", cancel: "ขอยกเลิก", details: "รายละเอียดออเดอร์", close: "ปิด", order: "ออเดอร์", episode: "Episode", original: "ยอดเดิม", filled: "จับคู่แล้ว", remaining: "คงเหลือ", spent: "ใช้เงินแล้ว", status: "สถานะออเดอร์", intake: "สถานะคำขอ", command: "สถานะคำสั่ง", failure: "เหตุปฏิเสธ", pendingNotice: "บันทึกคำขอแล้วไม่ใช่รับออเดอร์หรือจับคู่แล้ว คำขอยกเลิกยังไม่ใช่ยืนยันการยกเลิก",
  PENDING: "กำลังรอ", TRANSFERRED: "ส่งต่อให้ engine แล้ว", REJECTED: "ปฏิเสธ", SUCCEEDED: "คำสั่งสำเร็จ", ACCEPTED: "รับออเดอร์แล้ว", PARTIALLY_FILLED: "จับคู่บางส่วน", FILLED: "จับคู่ครบ", CANCELED: "ยกเลิกแล้ว", EXPIRED: "หมดอายุ", UNKNOWN: "ไม่ทราบ",
  RISK_LIMIT_UNSET: "ตั้งเพดานขาดทุนก่อนเปิดออเดอร์", RISK_LOSS_LIMIT_REACHED: "ขาดทุนถึงเพดานกระเป๋าแล้ว", RISK_SOURCE_UNAVAILABLE: "ข้อมูลความเสี่ยงยังไม่พร้อม", RISK_PRICE_UNAVAILABLE: "ราคาที่ใช้ประเมินความเสี่ยงยังไม่พร้อม",
  ORDER_INPUT_INVALID: "ค่าคำสั่งไม่ถูกต้อง", ORDER_CONSTRAINT_VIOLATION: "คำสั่งไม่ผ่านเงื่อนไขของตลาด",
  ORDER_SAFETY_UNAVAILABLE: "ระบบตรวจความเสี่ยงยังไม่พร้อม", MANUAL_USE_REQUIRED: "เปิดออเดอร์ได้เฉพาะบัญชี MANUAL", PAPER_WALLET_REQUIRED: "ต้องมีกระเป๋า Paper", ORDER_SOURCE_UNAVAILABLE: "ข้อมูลบัญชียังไม่พร้อม", ORDER_PAIR_REQUIRED: "กรุณาเลือกคู่เทรด", CATALOG_PAIR_REMOVED: "คู่เทรดนี้ไม่รองรับการเปิดออเดอร์แล้ว", ORDER_PRICE_UNAVAILABLE: "ราคาไม่พร้อมหรือเก่าแล้ว", ORDER_BOOK_UNAVAILABLE: "Order book ยังไม่พร้อม", ORDER_UNSUPPORTED: "ยังไม่รองรับเงื่อนไขการส่งคำสั่ง", ORDER_INSUFFICIENT_FUNDS: "ยอดใช้ได้ไม่เพียงพอ", EPISODE_CONFLICT: "Episode ของกระเป๋าเปลี่ยนแล้ว", ORDER_CONFLICT: "คำสั่งขัดแย้ง", limited: "ส่งคำขอถี่เกินไป ส่งคำขอเดิมได้อีกหลัง", safeFailure: "คำขอถูกปฏิเสธ กรุณาตรวจสถานะเซิร์ฟเวอร์ก่อนทำต่อ",
};
void manualOrderI18n.init({ lng: "th", fallbackLng: "th", initAsync: false, resources: { th: { translation: th }, en: { translation: en } }, interpolation: { escapeValue: false } });
export const manualOrderText = manualOrderI18n.t.bind(manualOrderI18n);
export const manualOrderLocale = () => manualOrderI18n.resolvedLanguage === "en" ? "en" : "th";
export function manualCode(code: string | null | undefined): string {
  return code && Object.hasOwn(en, code) ? manualOrderText(code) : manualOrderText("UNKNOWN");
}
