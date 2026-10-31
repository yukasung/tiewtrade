# F-18 R36 — Paper optional-limit quiet UI — Validation Amendment

สถานะ: **Approved — เจ้าของอนุมัติ R36 quiet UI plan/validation วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [R36 Requirements](paper-optional-limit-quiet-ui-requirements-amendment.md),
[R36 Plan](paper-optional-limit-quiet-ui-plan-amendment.md)

## เกณฑ์ตรวจรับ

| ID | เกณฑ์ |
|---|---|
| PQUI-V-01 | Paper unset ไม่แสดง optional helper, unset badge หรือ unset alert และไม่เหลือพื้นที่ helper ว่าง. |
| PQUI-V-02 | สถานะปกติมี label, input และ Save; ค่า unset เป็นช่องว่างและ Save ทำ SET ตาม contract เดิม. |
| PQUI-V-03 | Desktop input กับ Save อยู่แถวเดียวกันและสูงเท่ากัน; mobile เรียงลงโดย Save เต็มความกว้าง ไม่มี horizontal overflow. |
| PQUI-V-04 | Live unset ยังแสดงข้อความบังคับตั้งเพดาน; warning/error/latch/stop/stale/invalid/loading เดิมยังเข้าถึงได้. |
| PQUI-V-05 | Label ผูก input, Enter submit, focus/keyboard, aria-describedby และ sr-only recovery status ไม่ถดถอย. |
| PQUI-V-06 | SET/DECREASE/INCREASE, pending/UNKNOWN exact-key retry และ disabled-state behavior ไม่เปลี่ยน. |
| PQUI-V-07 | Frontend lint, typecheck, affected tests และ build ผ่าน; visual desktop/mobile บันทึกผลหรือระบุ Pending ตามจริง. |

## ชุดตรวจ

1. `frontend/tests/RiskLimitPanel.test.tsx` สำหรับ Paper unset, Live unset, validation,
   recovery และ submit behavior.
2. `TradingAccountPanel` tests ที่ยืนยัน component composition และไม่มีข้อความซ้ำจาก caller.
3. ESLint เฉพาะ affected dependencies, TypeScript typecheck และ Vite production build.
4. Browser desktop/mobile ทั้ง light/dark เฉพาะ layout ที่เปลี่ยน เมื่อเครื่องมือพร้อม.

## หลักฐานเดิมที่ใช้ต่อ

- R35 boundary/request/order/fill tests, backend static checks และ W1–W4 ไม่ได้รับผลกระทบ.
- Required remote CI และ manual visual acceptance ของ current head ยังคง Pending จนมีหลักฐานใหม่.
