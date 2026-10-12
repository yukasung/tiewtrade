# F-12 implementation evidence

Owner authorized plan/validation and implementation on 2026-10-12.
Results below are evidence for individual checks, not a claim that F-12 is complete.

ผลทดสอบและรายการค้างล่าสุดอยู่ใน [checkpoint.md](checkpoint.md), รวม candidate
full runs, targeted follow-ups และผลตรวจ frontend ที่ deploy ล่าสุด.
หลังจาก checkpoint นั้นได้แยก module pages ตามการอนุมัติเพิ่มเติม;
ดู [navigation implementation](navigation-implementation.md) สำหรับโค้ดและผลตรวจล่าสุด.
เจ้าของขอ URL ไม่มี hash เพิ่มเติม; ผลล่าสุดของการแก้เป็น path routing อยู่ใน
[path navigation correction](path-navigation.md).
การปรับ UI ตาม source admin-template ล่าสุดดู [template UI update](template-ui.md).
ผลเพิ่มเติมของ toggle sidebar และ palette ตรง template อยู่ใน [sidebar/theme](sidebar-theme.md).
คำสั่งลบ footer และผลตรวจล่าสุดอยู่ใน [footer removal](footer-removal.md).
งานตรวจประวัติว่าง/preview STALE ล่าสุดอยู่ใน [diagnosis](history-preview-diagnosis.md);
การแก้ history รออนุมัติ recovery plan ตาม NC-42.
NC-42 ได้รับอนุมัติและแก้ history แล้ว; ผลล่าสุดกับ preview blocker NC-43 อยู่ใน
[history recovery checkpoint](history-recovery.md).
NC-43 ได้รับอนุมัติและแก้ empty→first-trade ordering แล้ว; ดู
[ผลตรวจล่าสุด](first-trade-recovery.md). Local live API ยังแสดง RECOVERING ตามจริง;
ยังไม่รับรอง READY หรือเสร็จครบทุก validation.
รายงาน local preview ด้านล่างเป็นหลักฐานรอบก่อน ไม่ใช่สถานะปัจจุบันทั้งหมด.

## V-01 — contract/dependency (Partial)

- Command: `uv run python ../specs/features/2026-10-12-candlestick-chart/evidence/capture_kline.py` from backend; exit 0.
- Artifact: [kline-public.json](kline-public.json), one connection, 100 raw frames,
  12 series (BTC/ETH × six intervals), raw decimal text preserved.
- Ordering analysis: [kline-ordering.json](kline-ordering.json), 87 adjacent same-candle
  comparisons, no conflicting cumulative progression observed. This is bounded
  observational support, not a guarantee that the venue never corrects a candle.
  Ambiguous/corrected snapshots must still invalidate preview instead of choosing by arrival.
- `x=true`: Not Observed; synthetic closure tests remain required.
- `npm install --save-exact lightweight-charts@5.0.9`: exit 0, exact package/lock pin.
  Official package Apache-2.0 license and README attribution checked. Package omits
  NOTICE; upstream tagged NOTICE copied into frontend/THIRD_PARTY_NOTICES.md.
- Initial `npm run build`: exit 0 on host Node 24; Node 22 and real panes/whitespace
  checks remain required before V-01 can be Passed.

## Local preview and subsequent checks

[Local-preview report](dev-preview.md) records the updated containers, selected
backend/frontend checks, browser results and input snapshot. These are partial
validation evidence; see validation.md for outstanding criteria. The older
Node 24 build above is historical, not the current Node 22 verification.
