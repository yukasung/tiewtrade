# F-12 — Empty candle → first trade ordering

สถานะ: **Approved** — เจ้าของตอบ approve วันที่ 2026-10-13
วันที่: 2026-10-13
อ้างอิง: requirements RQ-25/26, plan §3 และ recovery-plan-amendment ส่วน preview

## หลักฐานและปัญหา

Sanitized log ของ supervisor ที่ใช้งานจริง:
`DOGE/USDT 1m old=(0, -1, -1) new=(1, 1625345571, 1625345571)`
tuples คือ trade_count / first_trade_id / last_trade_id. ไม่มี API credentials.
Core compare กำหนด first_trade_id ต้องเท่ากันสำหรับ cumulative dominance;
จึงคืน CONFLICT เสมอเมื่อเปลี่ยนจากแท่งไม่มี trades ไป trade แรก.
Supervisor invalidate connection และรอ reconnect 30s ตาม contract;
ผลคือ preview STALE/ORDER_UNCONFIRMED แม้เป็นการเริ่ม trade ของแท่งใหม่.

## กฎที่เสนอ

เพิ่มกรณี explicit empty baseline สำหรับ **series/open time เดียวกัน**:

- Baseline มี trade_count=0, first_trade_id=last_trade_id=-1, volume=0 exact
  และยังไม่มี closed_hint; ค่า OHLC ช่วงนี้ยังไม่ถือเป็น cumulative head ของ trades.
- เมื่อ snapshot มี trade_count>0 และ IDs valid ให้ snapshot นั้นเป็น head แรก
  ของแท่ง โดยใช้ OHLCV exact ที่ adapter ตรวจแล้ว และเพิ่ม revision.
  ไม่บังคับให้ open ของ baseline เท่ากับ open ของ trade แรก.
- เมื่อมี head ที่มี trades แล้ว snapshot empty baseline ที่มาช้าต้องไม่ทับ head.
- หลังตั้ง head แรกใช้ cumulative dominance เดิมทุกข้อ; conflicting nonempty
  snapshots, malformed empty baseline, closure/reconnect ambiguity ยัง fail closed.
- ไม่ใช้ event timestamp/arrival เป็นหลักฐานเรียง conflict ไม่เปลี่ยน CLOSED,
  REST settlement, Money/Quantity rules, freshness หรือ admission.

## แผนและ validation ส่วนเพิ่ม

ใช้ `core/candle_preview.py` เป็นจุดเดียวของ ordering; adapter ยังตรวจ input และ
supervisor ใช้ compare เดิม. ตรวจ volume ด้วย Quantity เดิม ไม่มี float/Decimal เปล่า.
ไม่เปลี่ยน order execution และไม่สร้างข้อมูลแทนตลาด.

เพิ่ม unit/property cases: empty→first positive โดย open เปลี่ยน, late empty,
duplicates, invalid sentinel/positive volume with zero trades, closed hint,
nonempty conflict ที่ timestamp ใหม่กว่า และ permutations เมื่อเริ่ม head แล้ว.
ตรวจ supervisor/preview integration ตามผลกระทบ และ bounded actual feed observation
หลัง deploy พร้อม chart READY/RECOVERING ที่อิง PG จริง; ไม่ใช้การล้าง error flag
หรือปลอมสถานะ READY แทนการตรวจ.

## จุดหยุด

Recovery plan ที่เจ้าของเพิ่ง approve ระบุว่ายังไม่อนุญาตให้เปลี่ยน dominance.
เจ้าของอนุมัติ requirement/plan/validation ในเอกสารส่วนเพิ่มนี้แล้ว วันที่ 2026-10-13;
อนุญาตเฉพาะ transition ที่ระบุ. NC-43 ปิดแล้ว; ต้องตรวจ implementation ตามหลักฐานจริง.
