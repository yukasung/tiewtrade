# F-18 R36 — Paper optional-limit quiet UI — Plan Amendment

สถานะ: **Approved — เจ้าของอนุมัติ R36 quiet UI plan/validation วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [R36 Requirements](paper-optional-limit-quiet-ui-requirements-amendment.md) — Approved 2026-10-31

## Implementation

1. ปรับ `RiskLimitPanel` ให้ `RISK_LIMIT_UNSET` ใน mode Paper และ draft ที่ยังไม่แก้
   ไม่สร้าง helper text หรือพื้นที่ว่างใต้ input; validation, stale และ Live unset ใช้ flow เดิม.
2. ใช้ `ComponentCard`, `Label`, `Input` และ `Button` กลางเดิม ซึ่งอ้างอิง
   `references/admin-template/src/components/form/example-form/BasicForm.tsx`,
   `components/form/example-form/ExampleFormOne.tsx` และ `components/ui/button/Button.tsx`.
3. จัด form ด้วย responsive grid: mobile หนึ่งคอลัมน์และปุ่มเต็มความกว้าง;
   ตั้งแต่ `sm` เป็นคอลัมน์ input ที่ยืดได้กับ action column; ปุ่มใช้ความสูง 44px
   ให้ตรงกับ shared `Input` (`h-11`) และไม่แก้ global Button behavior.
4. ลบ key `paperUnset` ที่ไม่ถูกใช้จากข้อความไทย/อังกฤษ; คง `liveUnset` และข้อความ
   validation/recovery/error ทั้งหมด.
5. ปรับ tests ที่เคยคาดข้อความ optional ให้ตรวจว่าไม่แสดง และเพิ่ม assertion ต่อโครง form,
   Live-required copy, label association และ enabled/disabled behavior เดิม.

## ขอบเขตผลกระทบ

- เปลี่ยนเฉพาะ presentation ของ `RiskLimitPanel`; ไม่แก้ API, risk policy, request journal,
  recovery, Money, matching, database หรือ Paper/Live order behavior.
- Caller `TradingAccountPanel` ใช้ component เดิมโดยไม่เพิ่ม branch หรือ style เฉพาะหน้า.
- ไม่รัน backend workload; ผล R35 backend และ W1–W4 ยัง valid.

## Verification

- `RiskLimitPanel` component tests และ `TradingAccountPanel` caller test ที่เกี่ยวข้อง.
- Frontend ESLint, TypeScript typecheck และ production build.
- ตรวจ desktop/mobile ด้วย browser หาก browser automation พร้อม; หากไม่พร้อมให้ระบุ Pending
  โดยไม่ใช้ unit tests แทน visual acceptance.
- ประมาณเวลา implementation และ targeted verification **10–20 นาที**.

## Needs Clarification

ไม่มี.
