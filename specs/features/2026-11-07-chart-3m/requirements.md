# F-12 extension — กราฟ timeframe 3m — Requirements

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-07; plan/validation อนุมัติแล้ววันที่ 2026-11-07**
วันที่: 2026-11-07
Branch: `feature/f-12-3m`
Base: `f15596df0b1ced53107964a8ed9bb657fda9d336`
ที่มา: เจ้าของสั่ง “เพิ่ม timeframe 3m”

## เป้าหมาย

ให้ผู้ใช้เลือกกราฟแท่งเทียน 3 นาทีได้จริง ทั้งประวัติและข้อมูลสด โดยใช้เส้นทาง
จัดเก็บ/อ่าน/แสดงผลเดียวกับ timeframe เดิม ไม่เพิ่มเฉพาะตัวเลือกที่ backend รับไม่ได้

## ข้อกำหนดที่อนุมัติ

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-3M-01 | เพิ่ม `3m` ระหว่าง `1m` และ `5m` สำหรับคู่ที่อนุมัติอยู่แล้ว BTCUSDT/ETHUSDT; timeframe เดิมและค่าเริ่มต้น `1h` คงเดิม | คำสั่งเจ้าของ; F-12/F-38 ขอบเขตคู่เดิม |
| RQ-3M-02 | ใช้แท่ง native `3m` จาก Binance TH ทั้ง REST และ candle stream; ไม่รวมแท่ง `1m` เอง และไม่ใช้ข้อมูลตลาดอื่นแทน | F-12 RQ-42; เอกสารต้นทาง |
| RQ-3M-03 | แท่งยาว 180 วินาที จัดขอบด้วย UTC schedule เดิม เช่น 00:00, 00:03, 00:06; กฎ open/end, finality, gap และการแทน preview ด้วยแท่งที่ยืนยันแล้วใช้ของเดิม | core/timeframes.py; F-12 finality contracts |
| RQ-3M-04 | ประวัติที่แสดงของ `3m` ใช้ขอบเขตสามเดือนปฏิทินเช่น intraday เดิม โหลดล่าสุดก่อนและเติมย้อนหลังเป็นหน้า; ใช้กฎ retention/indicator seed เดิม ไม่เพิ่ม horizon ใหม่ | F-12 RQ-37/39/40/42; เจ้าของอนุมัติขยายไปยัง 3m วันที่ 2026-11-07 |
| RQ-3M-05 | รองรับ `3m` ตลอดสัญญา core, venue adapter, database constraints/schedule functions, ingestion/preview, API/OpenAPI/generated types และ chart timeline; backend indicator/prepared paths ที่ใช้ enum ร่วมต้องรับค่าใหม่ได้โดยไม่เปลี่ยนสูตร | architecture; Timeframe เป็น shared contract |
| RQ-3M-06 | เปลี่ยนคู่/TF แล้วต้องกันผลของคำขอเก่า ไม่แสดงค่าเก่าว่าสด; ต้นทางล้ม/ข้อมูลขาดต้องแสดงสถานะตามจริง โดยคง deadline/retry/rate-limit/freshness/error policy เดิม | F-12 lifecycle/error contracts |
| RQ-3M-07 | การเปลี่ยน schema ต้องรักษา source/business facts, job identities และประวัติทั้งหมด; อนุญาตผล derived-state invalidation/rebuild ของ maintenance เดิมตาม NC-3M-01 A เท่านั้น และการย้อน schema ที่รับ 3m ไม่ได้ต้องปฏิเสธเมื่อมีข้อมูล/งาน 3m อยู่ ห้ามลบข้อมูลหรือแปลงเป็น timeframe อื่นเพื่อให้ downgrade ผ่าน | database safety; F-12 migration0026 pattern |
| RQ-3M-08 | การเลือกกราฟไม่ส่งออเดอร์ ไม่เปิด Live ไม่เปลี่ยน risk/account/session rules หรือสูตรเงิน; ใช้ Money/Quantity และกฎ exact OHLCV เดิม | trading-safety; AGENTS.md |

## ขอบเขตและการใช้หลักฐาน

- งานนี้ขยาย F-12/F-09/F-10/F-11 contracts เท่าที่ shared timeframe กระทบ ไม่เปลี่ยนสถานะ F-17
- ไม่เพิ่มคู่/timeframe อื่น หรือปรับ UI style; ใช้ตัวเลือกและ component เดิม
- เมื่อ requirements อนุมัติแล้วจึงจัดทำ plan/validation พร้อมผลกระทบ SQL และ targeted checks
- การเปิดใช้บนฐาน local ต้องผ่านการตรวจ migration/contract ก่อน; ไม่ถือว่าคำสั่งนี้อนุญาต commit/push/merge

## แหล่งอ้างอิง

- [F-12 requirements](../2026-10-12-candlestick-chart/requirements.md)
- [F-12 plan](../2026-10-12-candlestick-chart/plan.md)
- [F-12 validation](../2026-10-12-candlestick-chart/validation.md)
- [Binance TH official API](https://www.binance.th/api-docs/en/): Kline intervals ระบุ `3m` ทั้ง REST และ WebSocket; ตรวจเอกสาร 2026-11-07

## คำตัดสิน NC-3M-01

**Resolved — Approved A (2026-11-07):** ใช้ maintenance เดิมและ rebuild derived results
ตาม [amendment](source-maintenance-amendment.md). ยอมให้ source epoch/revision/journal_floor
เปลี่ยน, eligible generations เป็น EXPIRED และลบ heads ตามกลไกเดิมเท่านั้น
คง source/business facts, generations/checkpoints/history และ job identities ไว้
ไม่มี Needs Clarification ค้างสำหรับขอบเขตนี้; runtime เจ้าของยังไม่เพิ่ม3m
