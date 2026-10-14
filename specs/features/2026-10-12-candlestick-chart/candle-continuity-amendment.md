# Candle continuity during delayed REST settlement

สถานะ: **Approved** — 2026-10-14

ผล implementation และ targeted validation: [continuity checkpoint](evidence/2026-10-14-continuity.md).

## หลักฐานและสาเหตุ

ตรวจฐานข้อมูล development แบบ read-only เวลา 2026-10-14 05:29:15 UTC:

- BTC/USDT 1m: `market_candles` ล่าสุด 05:22 UTC.
- `market_candle_preview`: มีเพียง 05:28 และ 05:29 UTC (2 rows).
- ช่วง 05:23–05:27 UTC จึงไม่มีในแหล่งใดที่ UI อ่านได้ในเวลานั้น.
- `apply_event` ลบ preview ให้เหลือสองแท่งทุกครั้ง ขณะที่ REST worker ใช้งบ
  4 requests/round ร่วมหลาย series; preview จึงหมดอายุก่อน REST ตามทันได้.
- `/chart/live.history_end` ส่งค่าเมื่อ previous slot settled เท่านั้น;
  `useChartData` ใช้ค่านี้เพื่อ refresh history ทำให้หยุด refresh เมื่อ settlement ล่าช้า.
- Frontend แทน snapshot live ทุกครั้ง จึงทิ้งแท่งที่เห็นไปแล้วเมื่อหลุดจากสองแท่งล่าสุด.

## Requirements amendment

1. ระหว่าง REST ตามไม่ทัน ให้หน้ากราฟอ่าน native stream observations ที่ได้รับจริง
   เพื่อเชื่อมช่วงล่าสุดได้ ทั้งเปิดหน้าใหม่และเปลี่ยน TF. ห้ามสร้างแท่งสมมติ/เติมราคาเอง.
2. เก็บ stream observations แบบ bounded สูงสุด 120 แท่งต่อ series แทนสองแท่ง
   เพื่อรองรับช่องว่าง settlement ระยะสั้น; เกินขอบนี้หรือไม่ได้รับ event จริงให้คง gap.
   ไม่อ้างว่า buffer รับประกันข้อมูลครบเมื่อ outage ไม่จำกัดเวลา.
3. Candle page รวม REST และ buffer ตาม open time ใน requested window เดิม ≤1,000 slots.
   ให้ REST ที่ settled แล้วเป็น authoritative; buffer หลัง end_at เป็น UNCONFIRMED,
   ไม่ถือว่า CLOSED หรือ verified. Gap/coverage ของผลที่รวมต้องตรงกับข้อมูลที่ส่งจริง.
4. ไม่เขียน stream ลง canonical `market_candles`, ไม่ส่ง buffer ให้ indicator reader,
   ไม่เปลี่ยน indicator seed, financial precision, order logic หรือ source request budgets.
5. `/chart/live` ยังคงตอบสูงสุดสองแท่ง. การขยาย buffer ไม่ขยาย payload ของ polling.

## Plan amendment

- แทนที่ข้อเก็บ preview สูงสุดสองแท่งใน plan เดิมด้วย buffer 120 แท่งต่อ series
  (40 series ปัจจุบันรวมสูงสุด 4,800 rows). ใช้ตาราง/epoch/fencing/upsert เดิม.
- ตรวจ cleanup/restart/epoch transition ให้ buffer เก็บได้ตามขอบใหม่โดยไม่รับ event
  ผิดลำดับมาทับค่าใหม่; ไม่แอบอ้าง epoch เก่าว่ายังสด.
- เพิ่ม candle-only overlay ใน `/candles/pages`; query แบบ bounded ใน snapshot เดียวกัน.
  ไม่เปลี่ยน canonical reader ที่ indicator ใช้ และไม่เปลี่ยน consistency proof เดิม.
- Frontend เก็บ observations ที่เห็นแล้วภายในขอบ latest page และรวมแท่งด้วย source/time
  precedence ที่ทดสอบได้ จน REST รับช่วง; ล้างเมื่อเปลี่ยน user/series.
- Trigger history refresh ตาม open-time ของ native live candle เมื่อเปลี่ยนแท่ง
  ไม่ใช้ recovery flag เป็นเงื่อนไข; ไม่เกินหนึ่ง automatic page read ต่อ boundary,
  คง terminal error/Retry-After และไม่เพิ่ม polling loop.
- ใช้ REST backfill budget เดิมซ่อมช่วงที่หายอยู่แล้ว; buffer ใหม่ไม่สามารถกู้ event
  ที่ถูกลบทิ้งไปก่อน deploy ได้เอง. ตรวจช่วงนั้นซ้ำหลัง canonical backfill รับช่วง.

## Validation

- จำลอง REST ล่าช้าอย่างน้อย 7 แท่ง: stream ที่ได้รับครบต้องแสดงต่อเนื่อง รวม reload
  และสลับ TF กลับมา; สร้างกรณีหนึ่งแท่งไม่เคยได้รับจริงและยืนยันว่าคง gap.
- ข้ามอย่างน้อย 8 ขอบแท่งใน deterministic test; `history_end=null` ต้องไม่หยุด refresh,
  ไม่มีแท่งที่เคยเห็นหายไป ไม่มี request storm และไม่เรียก indicator/history proof.
- REST รับช่วงด้วยค่าที่แก้ไขแล้ว: ไม่มีแท่งซ้ำ ไม่มี preview เก่าทับ authoritative REST.
- Buffer cap/cleanup/epoch/restart/out-of-order, auth, cancellation, 429 cooldown ผ่าน.
- ตรวจ 1m และ calendar 1w/1M ด้วย exact OHLCV/finality เดิม; canonical indicator input
  ไม่เปลี่ยน. Integration tests ใช้ฐานข้อมูลแยก ห้าม seed ข้อมูลปลอมลง development DB.
- Browser ตรวจช่วงข้ามแท่งและ cold reload เทียบ response กับ DB พร้อมหลักฐานเวลา;
  แยก actual market gaps, REST lag และ rendering gaps ไม่รายงานเพียงว่า chart มีรูป.
- Targeted tests, lint/type checks และ buffer/resource smoke; full release gates เดิม
  ยังคง Pending Full Validation. ไม่ส่ง Live order.
