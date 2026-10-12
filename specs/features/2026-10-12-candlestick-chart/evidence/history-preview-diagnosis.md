# F-12 history / preview diagnosis

วันที่: 2026-10-13 (Asia/Bangkok)
ตรวจ development stack ด้วย read-only SQL และ bounded public market GET/stream;
ไม่ใช้ credentials ของผู้ใช้ ไม่ส่งออเดอร์ ไม่รัน full suites/benchmarks.

## Confirmed

- DB มี market_candles เฉพาะ 1m/5m ทั้งห้าคู่; default chart 1h ไม่มี historical OHLC.
  Demands ของ 15m/1h/4h/1d เป็น FAILED/SOURCE_FAILURE.
- BTCUSDT/1h public request เริ่ม 2026-08-29T13:00Z, ช่วง 1,000 ชั่วโมง,
  limit 1,000: HTTP 400 / code -4088 / `Maximum time interval is 7 days.`
  ช่วง 24 ชั่วโมงจาก start เดียวกัน: HTTP 200 / 24 rows.
  Actual adapter อ่าน latest three candles ของทั้ง 1m/1h ได้; ไม่ใช่ unsupported 1h.
- [Official docs](https://www.binance.th/api-docs/en/) ระบุ max limit 1,000 และ
  supported intervals; ไม่พบเพดานช่วงเวลา/error -4088 ในเอกสารที่ค้น.
  Source-span conclusion จึงอ้างอิงจาก public response ไม่ใช่การตีความ error code
  จาก Binance product อื่น.
- Development feed state ณ read snapshot: disconnected/ORDER_UNCONFIRMED,
  epoch 259. Preview มีครบ 30 series แต่ connection ถูก invalidate.
- Source hashes ของ core/candle_preview, candle_realtime และ candle_stream_mapping
  ใน market-data container ตรง working tree; ไม่ใช่สามไฟล์นี้ deploy เวอร์ชันเก่า.

## Not confirmed / remaining

- ยังไม่พบ snapshots ที่ทำให้ production supervisor ประกาศ conflict.
  Bounded single-connection captures: 300 frames ครั้งแรก; ต่อมา
  [606 frames](live-feed-conflict.json) และ
  [582 frames / ignored older 0](live-feed-conflict-held.json) ไม่พบ conflict.
  รอบสุดท้ายรักษา cumulative head เมื่อพบ OLDER ตาม supervisor.
  ไม่ถือ bounded observations ว่า feed ไม่มีปัญหา; ยังไม่แก้ dominance/finality
  หรือปลอม READY/ลบสถานะ failure เพื่อให้ UI ดูผ่าน.
- [Recovery plan amendment](../recovery-plan-amendment.md) เสนอ generic source-span
  capability และแบ่ง fetch units ก่อน HTTP/claim reservation. NC-42 รออนุมัติ
  เนื่องจากเปลี่ยน approved F-09 plan/contract; ยังไม่ได้แก้ production code/DB.
- ต่อไป: อนุมัติและ implement history fix พร้อม targeted integration tests;
  เพิ่ม bounded/sanitized diagnostics ที่จุด production conflict เพื่อจับเหตุจริง
  แล้วแก้ตาม ordering contract ที่มีหลักฐาน. ไม่ใช้ event timestamp เลือก conflict.
