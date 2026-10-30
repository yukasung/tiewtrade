# F18 — เพิ่มเพดาน Paper โดยไม่ใช้ TOTP — Validation Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Requirements](paper-increase-no-totp-requirements-amendment.md),
[Plan](paper-increase-no-totp-plan-amendment.md)

## เกณฑ์ตรวจรับ

| รหัส | เกณฑ์ |
|---|---|
| PIT-V-01 | Paper increaseไม่มี TOTP header/modal/consume/authorization rowและผ่าน authenticated+CSRF intake |
| PIT-V-02 | Live increaseยังต้อง fresh TOTP exact intent; missing/wrong/reused/recovery grant/forged proofปฏิเสธ |
| PIT-V-03 | DB constraint/functionยอม auth-nullเฉพาะ Paper increase; action/modeอื่นผิดรูปถูกปฏิเสธด้วย real roles |
| PIT-V-04 | Paper workerตรวจ revision/scope/source/amountและ applyหนึ่งครั้ง; stale/conflict/rollback/concurrent duplicateไม่เปลี่ยน settingซ้ำ |
| PIT-V-05 | Paper exact-key recoveryไม่ขอ code; Live unknown/AUTHORIZATION_ONLY recoveryและ secret cleanupเดิมผ่าน |
| PIT-V-06 | Migration up/down/upผ่าน; downgradeที่มี auth-null Paper increaseหยุดพร้อมคำอธิบายโดยไม่ทำข้อมูลหาย |
| PIT-V-07 | Paper/Live UI, owner/mode isolation, route classification, audit/OpenAPI/static/buildและ no-Live-order gatesผ่าน |

## ชุดตรวจ

1. `api/test_risk_limit_routes`, route policy/classification, authentication/TOTP regressions.
2. `infra/risk_limits` request/storage/worker/concurrency/authorizationและ migration tests.
3. F-18 profile fixture authorization testที่ได้รับผลกระทบ โดยไม่รัน timed workload.
4. Frontend RiskLimitPanel/account/session testsและ risk E2Eเมื่อ isolated fixtureพร้อม.
5. Backend ruff/format/mypy/import/staticที่เกี่ยวข้อง, frontend lint/typecheck/build,
   migration up/down guardและ `git diff --check`.

Critical failureคือ Paperยัง consume TOTP, Liveข้าม proof, authorizationผิด mode,
duplicate apply, direct setting write, cross-owner/modeหรือ downgradeทำข้อมูลหาย.

Browser/remote CIที่ไม่มีหลักฐานคง Pendingและไม่เปลี่ยนสถานะ F-18 Completed.
