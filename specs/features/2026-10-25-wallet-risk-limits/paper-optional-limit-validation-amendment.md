# F-18 — Paper MANUAL ไม่บังคับเพดานขาดทุน — Validation Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Requirements](paper-optional-limit-requirements-amendment.md),
[Plan](paper-optional-limit-plan-amendment.md)

## เกณฑ์ตรวจรับ

| รหัส | เกณฑ์ |
|---|---|
| POL-V-01 | Paper MANUAL BUY ที่ unset ผ่าน intake เมื่อ global admission พร้อม; admission ปิด, scope/wallet/episode/MANUAL/catalog/holdings ผิดยังปฏิเสธ |
| POL-V-02 | Unset path ไม่สร้าง setting/evaluation/baseline/audit/default limit และไม่ต้อง valuation price เฉพาเพื่อ loss-limit |
| POL-V-03 | Matching อ่าน setting ซ้ำภายใต้ lock/fence; unset ที่ intake แต่ SET ก่อ fill ต้องใช้ full evaluation ทันที |
| POL-V-04 | Race SET กับ order serialize ได้: READY จึง fill, unavailable/price-missing/latched ห้าม fill; rollback ไม่เหลือ partial setting/order/cash/position |
| POL-V-05 | Configured-limit path เดิมยังผ่าน: READY อนุญาต, breach/latch/source/price unavailable ปิด opening, reduction/cancel คงเดิม |
| POL-V-06 | Retry/same key/concurrent duplicate สร้าง request, command, order และ fill เพียงครั้งเดียว; balance/position/reservation ตรงกัน |
| POL-V-07 | Trade API ไม่ส่ง `RISK_LIMIT_UNSET` เป็น blocker ใน Paper MANUAL แต่ยังแสดง blocker อื่นครบโดยไม่เปลี่ยน schema |
| POL-V-08 | Paper UI แสดงว่าเพดานเป็นทางเลือก, submit ได้เมื่อด่านอื่นพร้อม; Live ยังแสดง/บังคับตามกฎเดิม |
| POL-V-09 | Zero configured Paper settings ไม่ทำให้ activation ล้มเหลว; เมื่อมี setting แล้ว configured-owner readiness ยังบังคับ |
| POL-V-10 | Live/BOT behavior, Money/Quantity, PnL, schema, public API และ no-Live-order gate ไม่เปลี่ยน |

## ชุดตรวจตามผลกระทบ

1. Core/policy tests: unset/SET/configured/latch/source/price/reduction, scope และ global control.
2. Real PostgreSQL concurrency tests: unset intake → concurrent SET → matching, fence/rollback,
   cash/position/reservation และ duplicate effects.
3. Manual-order route/request-worker/matching tests สำหรับ API reason, durable request/command,
   retry/idempotency และ configured-limit regression.
4. Frontend `PaperTradePage`, manual-order messages, `RiskLimitPanel` และ Live-required regression;
   keyboard/light/dark เฉพา component ที่เปลี่ยน.
5. Backend ruff/format/mypy/import/static และ frontend lint/typecheck/tests/build ตาม dependencies ของ diff;
   `git diff --check`.
6. Isolated production-composition manual acceptance: บัญชีใหม่, MANUAL, Paper wallet,
   ไม่ตั้งเพดาน, activate โดย zero configured owners, ส่ง Paper order หนึ่งรายการ
   แล้วยืนยัน request → command → order/fill และ ledger/position โดยไม่มี risk rows ปลอม;
   ปิด protocol flags หลังตรวจ.

## การใช้หลักฐานเดิม

- W1–W4 ไม่รันซ้ำอัตโนมัติ ถ้า scheduler/cadence/configured-limit financial path ไม่เปลี่ยน;
  ตรวจซ้ำเฉพา regression ที่ diff กระทบ.
- ถ้าแก้ shared matching/risk calculation จนผลเดิมไม่ valid ให้ขยาย regression ตามผลกระทบ;
  หากกระทบ runtime/cadence ของ W1–W3 จึงถือว่าผลเดิมหมดอายุ.
- Required remote CI สำหรับ local head และ V-22/V-23 ยัง Pending ตามเดิม;
  targeted/local pass ไม่ทำให้ F-18 Completed.

## กฎหยุด

หยุดทันทีหาก unset ข้าม global control, SET race ทำให้ fill โดยไม่ตรวจ,
มี duplicate/economic inconsistency, Live/BOT ผ่าน unset หรือเกิด synthetic risk evidence.
ไม่ส่ง Live order ใน automated/manual validation.
