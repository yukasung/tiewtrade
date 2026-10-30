# F18-UI — ซ่อนรายละเอียด Recovery จากฟอร์มเพดาน — Plan Amendment

สถานะ: **Approved — เจ้าของตอบ “pprove recovery plan and validation amendment” วันที่ 2026-10-30**
วันที่: 2026-10-30
อ้างอิง: [Requirements Amendment](compact-risk-recovery-ui-requirements-amendment.md) **Approved 2026-10-30**

## 1. แนวทาง

คง `useDurableAttempt`, journal, lookup, receipt matching และ mutation adapter เดิม แต่
รวม recovery interaction เข้ากับ input และปุ่ม Save ของ `RiskLimitPanel`. ไม่มี recovery
region/disclosure/technical copy บนหน้าหลัก. UI แยกสามสถานะ:

1. ไม่มี attempt: form ทำงานตาม compact-form amendment เดิม.
2. attempt กำลัง lookup/pending: input แสดง amount ของ attempt, readonly/disabled,
   Save disabled และมี status สั้นหนึ่งบรรทัด.
3. attempt ยังไม่ยืนยันผลและพร้อม retry: inputยังล็อก amountเดิม; Save ส่ง attempt/keyเดิม.

## 2. การใช้ของเดิม

- ใช้ `useDurableAttempt.ts`, `riskLimitJournal.ts`, `riskLimits.ts` และ exact `RiskAttempt`
  เดิม ไม่สร้าง recovery store หรือ key generator ใหม่.
- ใช้ `Input`, `Label`, `Button`, `Alert`, `Modal` กลางตาม admin template.
- ใช้ modal TOTP เดิมเฉพาะ INCREASE ที่ยังต้อง reauthorize; AUTHORIZATION_ONLY ไม่ขอใหม่.
- ใช้ receipt/snapshot synchronization เดิมสำหรับ APPLIED/REJECTED.

## 3. State และ interaction

- เมื่อ mount พบ journal ให้ draft แสดง `attempt.payload.amount` สำหรับ SET/DECREASE/
  INCREASE และห้าม polling snapshot เขียนทับจน terminal.
- `lookup.isPending`, REQUEST_PENDING หรือ mutation pending: input disabled, Save disabled,
  แสดง `กำลังตรวจสอบคำขอก่อนหน้า…` ด้วย `role=status`.
- lookup errorแบบ not-found/unknown: inputยัง disabled; Save enabledเป็น recovery trigger.
  Triggerเรียก `recovery.send(recovery.attempt, true)` ด้วย object/keyเดิม. ไม่มี UUIDใหม่.
- AUTHORIZATION_ONLY: Save retry intent/keyเดิมโดยไม่ใช้ TOTP ตาม server contract.
- INCREASE ที่ยังไม่มี authorization: Save เปิด TOTP modalและ retry attemptเดิมหลังยืนยัน;
  codeอยู่ transient ref/headerเหมือนเดิม.
- storage error, mismatch หรือ conflict: Save disabledและข้อความสั้นปลอดภัย; ไม่ล้าง journal.
- terminal effectคง logicเดิม: APPLIEDรอ applied revision; REJECTEDล้าง durable attemptแต่
  ไม่เปลี่ยน authoritative amountแบบ optimistic.
- ลบ render ของ `requestDetails`, request key, check/retry buttons และ protocol states.
  เก็บ translation keysเฉพาะที่ caller/diagnosticอื่นยังใช้.

## 4. ไฟล์และขอบเขต

- `frontend/src/RiskLimitPanel.tsx`: รวม recovery stateเข้ากับ form/Save.
- `frontend/src/riskLimitMessages.ts`: เพิ่ม copyสั้นและลบ copy UIที่ไม่มี caller.
- `frontend/tests/RiskLimitPanel.test.tsx`: ปรับ recovery assertionsและ no-technical-copy.
- E2E selectorsเฉพาะกรณี recoveryถ้า fixtureพร้อม.

ไม่แก้ backend, public API, schema, Money, risk calculation, TOTP policy หรือ worker.

## 5. ความเสี่ยงและการควบคุม

| ความเสี่ยง | การควบคุม |
|---|---|
| Saveสร้างคำขอใหม่ขณะ UNKNOWN | assert object/keyเดิมและ `randomUUID` ไม่ถูกเรียก |
| Draftใหม่ถูกส่งแทน intentเดิม | inputล็อกและ render amountจาก journal |
| INCREASEข้าม TOTP | แยก AUTHORIZATION_ONLY ที่ serverยืนยันแล้ว; unknownอื่นเปิด modal |
| ซ่อนสถานะจนผู้ใช้คิดว่า Saveเสีย | statusสั้นหนึ่งบรรทัดและ disabled semantics |
| ล้าง attemptจาก snapshotที่บังเอิญเท่ากัน | terminal receipt matchingเท่านั้น |

## 6. เวลา

Implementationและ targeted verificationประมาณ **25–40 นาที**. ไม่รัน backend workload,
W1–W4 หรือ performance เพราะไม่เปลี่ยน runtime/business logic.

## 7. Needs Clarification

ไม่มีข้อที่บล็อกหลัง plan/validationได้รับอนุมัติ.
