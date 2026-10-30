# F18 — เพิ่มเพดาน Paper โดยไม่ใช้ TOTP — Plan Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Requirements](paper-increase-no-totp-requirements-amendment.md) **Approved 2026-10-31**

## 1. Route และ authentication

- เปลี่ยน `POST /paper/risk-limit/increase` เป็น authenticated+CSRF+renewing mutationที่
  `reverify=false`; คง `/live/risk-limit/increase` เป็น `reverify=true`.
- `authenticate_request` ทำ exact-payload authorization flowเฉพาะ LIVE path; Paperไม่อ่าน
  TOTP header, ไม่ consume stepและไม่สร้าง authorization row.
- คง throttle, safe-input, owner sessionและ route classificationเดิม.

## 2. Request/DB contract

- เพิ่ม migration `0059` แก้ request constraintเป็น mode-sensitive:
  authorization_idต้องมี iff `mode='LIVE' AND action='INCREASE'`.
- แทน `risk_submit_request` โดยคง advisory lock/idempotency/scope/revision/auditเดิม;
  ตรวจ proofเฉพาะ LIVE INCREASE. PAPER INCREASEต้อง authorization nullและ amount>current.
- `submit_request` ยอมให้ previous=nullสำหรับ PAPER INCREASE; LIVEยังต้อง authorization-only
  receiptก่อน intake.
- engine `_process_request` ตรวจ authorizationเฉพาะ LIVE INCREASE; Paperยังตรวจ revision,
  active episode, publication/risk sourceและ amount orderingเต็มชุด.
- downgradeต้องปฏิเสธหากมี Paper increase rowที่ไม่มี authorizationซึ่ง schemaเก่ารับไม่ได้;
  ห้ามสร้าง proofปลอมหรือทำข้อมูลหาย.

## 3. Frontend/recovery

- `RiskLimitPanel`: PAPER INCREASEเรียก `sendAttempt`ตรง; LIVEเท่านั้นเปิด TOTP modal.
- Paper unknown retryส่ง exact keyเดิมโดยไม่ code; Live unknownเพิ่มยังใช้ modal,
  AUTHORIZATION_ONLYใช้ authorizationเดิม.
- Copy modalระบุ Live context; normal Paper formไม่มีข้อความ TOTP.
- `riskLimits.ts` pathเดิม ไม่เปลี่ยน generated API types.

## 4. Tests และผลกระทบ

- Route/auth: Paper missing/wrong TOTPยัง submitได้โดยไม่ consume; Live missing/wrong/reused
  codeปฏิเสธและ correct codeผ่าน; CSRF/auth/throttleยังบังคับ.
- Real PostgreSQL: constraint/function/role testsสำหรับ Paper auth-nullและ Live exact proof,
  same-key equal/different payload, concurrency, rollback, migration up/down guard.
- Engine: Paper increase APPLIEDครั้งเดียว, stale revision/scope/amount/source rejected;
  Live forged/missing proof rejected.
- Frontend: Paper no modal/header, Live modal/header, recovery/owner-mode isolation.
- ปรับ profile fixtureที่สร้าง Paper INCREASEไม่ให้สร้าง AUTH proof; คง financial oraclesและ
  measured workloadเดิม. ไม่รัน W1–W4ใหม่เพราะ cadence/worker/financial calculationไม่เปลี่ยน;
  หาก diffล้ำเข้า schedulingหรือ Moneyให้ประเมินใหม่.
- รัน affected backend tests, route classification, migration/static/import/mypy,
  frontend targeted tests/lint/typecheck/buildและ production composition risk E2Eเมื่อ
  isolated fixtureพร้อม.

## 5. เวลา

ประมาณ **45–75 นาที** หากผ่านครั้งแรก ไม่รวม required remote CIหรือการแก้ findingใหม่.

## Needs Clarification

ไม่มี.
