import { createInstance } from "i18next";
const thReasons = {
    READY: "ราคาผ่านเกณฑ์ ณ เวลาที่ตรวจ",
    STALE: "ราคาเกินอายุที่กำหนด",
    RECOVERING: "ยังยืนยันความพร้อมของราคาไม่ได้",
    MISSING: "ยังไม่มีราคาซื้อขาย",
    VENUE_PROTOCOL: "ข้อมูลจากตลาดไม่เป็นไปตามรูปแบบที่กำหนด",
    VENUE_RATE_LIMITED: "ตลาดจำกัดอัตราการเรียกใช้งาน",
    VENUE_UNAVAILABLE: "ตลาดไม่พร้อมให้บริการ",
    VENUE_REJECTED: "ตลาดปฏิเสธคำขอรับข้อมูล",
    SUBSCRIPTION_ACK_TIMEOUT: "ตลาดไม่ยืนยันการสมัครรับข้อมูลภายในเวลาที่กำหนด",
    ORDER_UNCONFIRMED: "ยังยืนยันลำดับข้อมูลซื้อขายไม่ได้",
    DELIVERY_UNAVAILABLE: "การส่งข้อมูลราคาไม่พร้อมใช้งาน",
};
const enReasons: Record<keyof typeof thReasons, string> = {
    READY: "Price passed checks at the server check time",
    STALE: "Price exceeded the maximum age",
    RECOVERING: "Price readiness is not yet confirmed",
    MISSING: "No trade price is available",
    VENUE_PROTOCOL: "Exchange data did not match the expected protocol",
    VENUE_RATE_LIMITED: "Exchange rate limit reached",
    VENUE_UNAVAILABLE: "Exchange is unavailable",
    VENUE_REJECTED: "Exchange rejected the market data request",
    SUBSCRIPTION_ACK_TIMEOUT: "Exchange subscription acknowledgement timed out",
    ORDER_UNCONFIRMED: "Trade data ordering is not confirmed",
    DELIVERY_UNAVAILABLE: "Price delivery is unavailable",
};
const th = { heading: "ราคาซื้อขายล่าสุด", checked: "เวลาที่ตรวจโดย server", trade: "เวลาซื้อขาย", missing: "ไม่มีข้อมูล", READY: "พร้อม ณ เวลาที่ตรวจ", STALE: "ราคาเก่า ณ เวลาที่ตรวจ", RECOVERING: "กำลังกู้คืน ณ เวลาที่ตรวจ", MISSING: "ไม่มีข้อมูล ณ เวลาที่ตรวจ", CONNECTED: "เชื่อมต่อการส่งข้อมูลแล้ว", CONNECTING: "กำลังเชื่อมต่อ", AWAITING_SNAPSHOT: "รอสถานะใหม่ ข้อมูลที่แสดงเป็น snapshot ล่าสุด", DISCONNECTED: "การเชื่อมต่อขาด ข้อมูลอาจไม่เป็นปัจจุบัน", marketWarning: "ราคาตลาดไม่พร้อมต่อเนื่องครบ 60 วินาที ณ เวลาที่ตรวจ", reason: "เหตุผลจาก server", delivery: "การส่งข้อมูลจาก server", disclaimer: "สถานะราคาเป็นผล ณ เวลาที่ตรวจ ไม่ใช่การรับรองราคาปัจจุบันหรือความพร้อมบัญชี" };
const en = { heading: "Latest trade prices", checked: "Server check time", trade: "Trade time", missing: "No data", READY: "Ready at last check", STALE: "Stale at last check", RECOVERING: "Recovering at last check", MISSING: "Missing at last check", CONNECTED: "Delivery connected", CONNECTING: "Connecting", AWAITING_SNAPSHOT: "Awaiting new snapshot; showing the last snapshot", DISCONNECTED: "Delivery disconnected; displayed data may be outdated", marketWarning: "Market unavailable for 60 seconds at last check", reason: "Server reason", delivery: "Server delivery", disclaimer: "Price status describes the last check, not current prices or account readiness" };
export const realtimePriceI18n = createInstance();
void realtimePriceI18n.init({ lng: "th", fallbackLng: "th", initAsync: false, resources: { th: { translation: { ...th, reasons: thReasons, unknownReason: "ไม่ทราบเหตุผลจาก server" } }, en: { translation: { ...en, reasons: enReasons, unknownReason: "Unknown server reason" } } }, interpolation: { escapeValue: false } });
export const realtimePriceText = realtimePriceI18n.t.bind(realtimePriceI18n);
