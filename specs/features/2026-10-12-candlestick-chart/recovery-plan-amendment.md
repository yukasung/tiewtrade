# F-12 — History recovery / source request limits

สถานะ: **Proposed** — ต้องอนุมัติการเปลี่ยนแผน F-09 ก่อนแก้ source contract/ingestion
วันที่: 2026-10-13
Requirements F-09/F-12 เดิมยังมีผล; ไม่เปลี่ยนคู่/timeframes/retention/finality.

## ปัญหาที่พิสูจน์แล้ว

Development DB มี historical candles เฉพาะ 1m/5m; 15m/1h/4h/1d demands
เป็น FAILED/SOURCE_FAILURE. Chart default 1h จึงไม่มี historical OHLC.
Public GET ของ BTCUSDT/1h ช่วง 1,000 ชั่วโมงคืน HTTP 400, code -4088,
message `Maximum time interval is 7 days.`; ช่วง 24 ชั่วโมงคืน HTTP 200 / 24 rows.
Adapter จริงอ่านช่วงล่าสุดสามแท่งของ 1m และ 1h ได้ทั้งคู่.

เอกสาร [Binance TH](https://www.binance.th/api-docs/en/#kline-candlestick-data)
ระบุ limit สูงสุด 1,000 rows แต่ไม่พบรายละเอียด error -4088/เพดานเจ็ดวัน
ในเอกสารที่เปิดตรวจ. เพดานช่วงเวลานี้อ้างอิงจาก public response ที่สังเกตจริง.

## แนวทางที่เสนอสำหรับอนุมัติ

1. เพิ่มขีดจำกัดช่วงเวลาคำขอในสัญญา CandleSource แบบทั่วไปใน `venues/candles.py`.
   Binance TH adapter ประกาศ max request span เจ็ดวัน; service ไม่รู้ชื่อตลาด
   และไม่ฝัง endpoint/error code/เพดานของ Binance ลงใน core หรือ service.
2. Ingestion แบ่ง fetch window ให้ไม่เกินทั้ง 1,000 slots และ source max span
   **ก่อน** reserve fetch unit/ส่ง HTTP; actual requested range, persisted fetch unit,
   response validation และ cursor progress ต้องตรงกัน. ไม่ clip เฉพาะ HTTP endTime
   แล้วอ้างว่าโหลด window ใหญ่ครบ เพราะจะข้ามข้อมูลและทำให้ repair ผิด.
3. ใช้ demand/claim/fencing/transaction/cursor/repair/backoff เดิม. ไม่ reset attempts,
   worker leases หรือ desired history เพื่อให้ดูเหมือนสำเร็จ; ไม่แก้ DB แท่งเทียนด้วยมือ.
   FakeVenue/test sources รองรับ contract เดียวกันและเลือก limits ของ fixture ได้.
4. คง admission/rate-limit guard, four-attempt round bound (??? implementation ????) และ timeout เดิม;
   ไม่เพิ่ม inner HTTP loop ที่ซ่อนจำนวน requests หรือขยาย timeout เพื่อโหลด 365 วัน.
   บริการจะทยอยโหลดผ่านหลาย units/rounds โดยใช้สถานะ coverage ตามจริง.
5. ทดสอบ exact seven-day boundary, longer windows หลาย units และ sparse/empty pages,
   cursor/repair continuation, overlapping demands, rollback/fencing และ limiter
   โดยใช้ isolated DB. รันเฉพาะ affected adapter/ingestion tests ก่อน deployment.
   ใช้ fixture Money/Quantity เดิม; ไม่มี Live orders.

## ผลต่อแผนเดิม

F-09 plan กำหนดการแบ่ง fetch window ตาม 1,000 slots และมี CandleSource contract
ที่ยังไม่ประกาศ max span. แผนนี้เพิ่ม source capability และให้ service แบ่ง units
ตาม capability นั้น. จึงต้องอนุมัติก่อนแก้ code ตาม AGENTS.md เรื่องเปลี่ยน approved plan.

## Preview ORDER_UNCONFIRMED

ยังไม่อนุมัติให้เปลี่ยน dominance/conflict rules หรือเลือก snapshot ตาม timestamp.
Development feed สลับ disconnected/ORDER_UNCONFIRMED; bounded capture ต้องระบุ
คู่ snapshots ที่ขัดกันและสาเหตุก่อนเสนอแก้. ถ้าเจอ gap ใน ordering contract
ให้เสนอข้อแก้แยกพร้อมหลักฐาน; ไม่ลด fail-closed เพื่อให้แสดง READY.
