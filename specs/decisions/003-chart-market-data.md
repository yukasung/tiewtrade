# ADR-003 — Preview และชุดข้อมูลกราฟที่สอดคล้องกัน

สถานะ: **Approved** — เจ้าของอนุมัติพร้อม plan/validation ของ F-12 วันที่ 2026-10-12
วันที่: 2026-10-12
อ้างอิง: [F-12 requirements](../features/2026-10-12-candlestick-chart/requirements.md),
[รายละเอียดแผน](../features/2026-10-12-candlestick-chart/plan.md)

## ปัญหา

F-09 history กับ F-11 indicators อ่านคนละ HTTP request อาจเห็นคนละ DB revision.
Kline ระหว่างกำลังก่อตัวมีการแก้ OHLCV และไม่ผ่านเกณฑ์คำนวณของ F-11 เดิม.
ถ้าเอาข้อมูลสามทางมา merge โดยไม่กำหนด provenance จะวาดเส้นที่คำนวณจาก
คนละข้อมูลกับแท่งที่ผู้ใช้เห็น หรือทำให้ preview เปลี่ยน input ของ indicator.

## แนวทางที่เสนอ

เก็บ public preview แบบ bounded ผ่าน market-data/PG แยกจาก durable history
และให้ F-09 worker เดิมบันทึก REST observations ที่ F-11 อ่าน.
เพิ่ม API bundle ที่อ่าน OHLC และ indicator ใน transaction snapshot เดียวกัน
พร้อม signed display proof เพื่อยืนยัน dependencies ทั้งชุดเมื่ออ่านต่อ/ตรวจใหม่.
รายละเอียด schema/budgets/lifecycle/proof modes อยู่ใน F-12 plan แห่งเดียว.

ใช้ reader/source journal/cursor infrastructure เดิม ไม่สร้างสูตรหรือ journal
อีกชุด และไม่เปิด PREPARED เพื่อให้กราฟผ่าน. ถ้า proof ไม่ผ่านให้ระงับ overlay.
LEGACY verification ยอมรับต้นทุนที่มีจริงภายใต้งบเดิม แสดงความไม่พร้อมเมื่อถึงงบ.

## ทางเลือกที่ไม่เลือกและผลกระทบ

การ join จากสอง endpoint ด้วย timestamp อย่างเดียวไม่ครอบ seed/revision.
การเขียน provisional OHLC ลง source history ทุก update เพิ่มภาระ invalidation
และต้องเปลี่ยน semantics/finality ของ F-09/F-11 จึงไม่เสนอในรอบนี้.

แนวทางนี้เพิ่ม public preview tables และ API consumer contracts
แต่ไม่เพิ่มสิทธิ์ข้อมูลผู้ใช้หรือเปลี่ยนทิศทางการพึ่งพา. ต้องพิสูจน์ actual-role,
snapshot races, signer purpose isolation และ resource bounds ก่อนรับงาน.
การอนุมัติครอบแนวทางในแผน F-12; ไม่ใช่ผลผ่าน validation หรือสิทธิ์เปิด production PREPARED.
