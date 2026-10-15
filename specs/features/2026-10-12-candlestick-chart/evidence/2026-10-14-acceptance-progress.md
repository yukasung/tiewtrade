# F-12 acceptance progress — 2026-10-14

สถานะ: **Partial; deep history ผ่าน 40/40 และ C2 ผ่านแล้ว แต่ live preview กับ release gates ยังเหลือ**

ตรวจบน merge tree `761a2cb36f26ba2c726e105c93c1c2e42b789044` ต่อจาก required CI ของ
source PR #11 และ documentation CI ของ PR #12 ที่ผ่านแล้ว ไม่รัน full suite ซ้ำเพราะไม่มี
production source เปลี่ยนในรอบนี้ การตรวจทั้งหมดใช้บัญชีแยก, public market data และฐานทดสอบ;
ไม่มี API key, order request, mode change หรือ Live Trading action.

## Browser จริง

รัน Chromium กับ `http://localhost:5173` ผ่าน UI registration แล้วตรวจ default `1h`,
สลับ `1m/5m/15m/1h/4h/1d/1w/1M`, exact OHLCV summary, canvas, theme และขนาด
375/768/1440. ทุก timeframe ได้ candle response HTTP 200 และแสดงแท่ง/ค่า OHLCV,
ไม่มี page error หรือ request ไป order/live-trading endpoint. ที่ 1440×900 workspace พอดีหน้า;
375/768 ไม่มี horizontal overflow แต่มี vertical scroll ตาม form/history ที่เรียงลงด้านล่าง.

หลักฐาน: [ผล JSON](2026-10-14-browser-acceptance/result.json),
[375 px](2026-10-14-browser-acceptance/chart-375.png),
[768 px](2026-10-14-browser-acceptance/chart-768.png),
[1440 px](2026-10-14-browser-acceptance/chart-1440.png).

## Deep history และ backfill

หลัง 15 series ที่เหลือ backfill จบ ได้ snapshot หนึ่งรอบที่ 40/40 series `COMPLETE`, 0
`FAILED`. ตรวจฐานข้อมูล read-only พบ stored history 40/40 มี expected rows = actual rows =
unique identities และ internal gaps = 0 ทุก series.

จากนั้น client แยกร้องขอทุกหน้าจริงสำหรับ 5 คู่ × 8 TF ถึง `display_start`. จำนวนหน้า
ต่อคู่คือ 166 (`1m`), 33 (`5m`), 11 (`15m`), 3 (`1h`) และ 1 สำหรับ
`4h/1d/1w/1M`; ทุก historical page เป็น HTTP 200 / `PRESENT`, gaps ว่าง, ไม่เกิน
1,000 rows, boundary เลื่อนไปทางเก่าทุกครั้ง และ row ที่ซ้อนกัน 200 แท่งมี payload
ตรงกันทั้งหมด. รวม 40/40 series ผ่านและไม่มี page error.

ระหว่าง traversal API ขยาย demand ไปยังเวลาปัจจุบัน จึงทำให้สถานะคิวล่าสุดแกว่งเป็น
`PENDING/RUNNING` ได้อีกแม้ deep history ผ่านแล้ว. ช่องว่างที่พบหลัง backfill อยู่เฉพาะ
live tail ของแท่งกำลังก่อตัว; log มี `candle preview writer unavailable` และ
`price producer lease lost`. Checker จึงบันทึก live-tail exclusions แยก และเริ่ม deep-history
traversal ก่อนช่องว่างนั้น ไม่ตีความว่าการผ่านประวัติเป็นการผ่าน freshness ของแท่งสด.

หลักฐาน: [demand snapshot](2026-10-14-acceptance/demand-snapshot.json),
[continuity 40/40](2026-10-14-acceptance/continuity-complete.json) และ
[API deep-history traversal](2026-10-14-acceptance/deep-history-api.json). สถานะคิวเป็น
snapshot; worker ของ application ยังทำงานต่อหลังจบรอบตรวจ.

## Capacity/release checkpoint

แก้ capacity harness ให้ยึด workload ที่อนุมัติ 30 series, ไม่สร้าง source write เมื่อไม่มี
boundary ใหม่ และตั้ง rollout/codec ของฐานแยกให้ตรง candidate ปัจจุบัน. C1 ผ่าน 30/30
ภายในนาที 6. C2 rerun ผ่านช่วงวัดเต็ม 3,600.016 วินาที: valid 360/360 และ correct
probe 60/60 ทุก series, API max lag 75.283ms, API max RSS 63.219MiB และ worker
max attempt 50.053008s. C3/C5 ยังไม่รัน; R2-7 cold/warm resource และ C6 ยัง Failed.

หลักฐานอยู่ใน [release checkpoint](../../2026-10-10-backend-indicators/profiling/release-20261014/README.md).
F-12 V-17 ยังไม่รัน workload 10 นาทีทั้ง LEGACY/PREPARED และคง
`Pending Full Validation`; C2 ไม่เป็น blocker แล้ว แต่ห้ามเปิด production PREPARED
จน C3/C5, R2-7/C6 และ release gates ที่เกี่ยวข้องผ่านครบ. ไม่มีการใช้เงินจริงหรือ order API.

## สถานะเกณฑ์

| เกณฑ์ | ผลรอบนี้ |
|---|---|
| V-H1 | **Passed** — stored history และ API traversal ของ 1m–1d ครบสามเดือนทุกคู่ถึง display bound, contiguous/unique |
| V-H2 | **Passed สำหรับข้อมูลจริงที่ดึงได้** — 5 คู่ของ `1w/1M` ครบถึง per-series source boundary, contiguous/unique และ browser 200 |
| V-H3 | **Passed** — actual traversal เกิน 1,000 แท่งถึงขอบทุกคู่, boundary เดินย้อนหลัง, overlap payload ตรงกัน และ anchor regression ผ่านเดิม |
| V-H4 | **Partial** — cancellation/dedup/LRU/Retry-After tests ผ่านเดิมและ browser สลับ 8 TF ผ่าน; rapid switch/failure browser matrix ยังอาศัย E2E เดิม |
| V-H5 | **Partial** — migration/restart/lease/fence/rollback tests ผ่านใน final CI; old-row checksum และ full partition/grant inventory ยังไม่ได้ปิด |
| V-H6 | **Passed ในขอบเขต F-12** — exact OHLCV/finality แสดงจริง, formula source ไม่เปลี่ยน, ไม่มี order request; indicator capacity ไม่ได้ผ่านจากผลนี้ |
| V-H7 | **Passed** — page ≤1,000 slots, bounded five-page cache/eviction/refetch tests เดิม และ initial browser ไม่รอทุกหน้า |
| V-H8 | **Partial** — API deep traversal 40/40 และ browser 8 TF/screenshots ผ่าน; ยังต้องปิด browser actual pan/retry/reset หลัง backfill และ live-preview freshness risk |
| V-01..16/V-18 | **Partial ตามตารางเดิม** — automated CI/browser evidence เพิ่มขึ้น แต่ owner manual และ criterion closure ยังไม่ครบ |
| V-17 | **Pending Full Validation** — C2 ผ่านแล้ว; F-12 LEGACY/PREPARED workload และ release dependencies ที่เหลือยังไม่รันครบ |

## งานค้างที่ตัดสินผล

1. แก้/พิสูจน์ `candle preview writer unavailable` และ `price producer lease lost`, แล้วตรวจ
   live tail กับ browser actual pan/retry/reset เพื่อปิด V-H8 โดยไม่ใช้ deep-history pass แทน.
2. รัน C3/C5, ปิด R2-7/C6 และ F-12 V-17 workload ตาม threshold เดิม.
3. ปิด migration old-row checksum/partition-grant inventory และ owner manual criteria ที่ยัง Partial.
