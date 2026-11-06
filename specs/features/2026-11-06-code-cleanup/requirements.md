# Code cleanup และ shared frontend helpers — Requirements

สถานะ: **Approved — เจ้าของอนุมัติ requirements หลังรีวิว 2026-11-06**
วันที่: 2026-11-06

## ทำไมต้องมี

การตรวจ static ของ repository พบ declaration ที่ไม่พบผู้ใช้ และ frontend helpers
ที่ทำงานซ้ำกัน การเก็บไว้เพิ่มภาระดูแลและความเสี่ยงที่พฤติกรรมแต่ละสำเนาจะเปลี่ยนไม่ตรงกัน
เจ้าของเลือกขอบเขต **Cleanup + helper** และให้เริ่ม implementation หลัง F-17 merge
จากนั้นสั่งดำเนินการตามแผนซึ่งยังคงจุดอนุมัติ requirements และ plan/validation แยกกัน

เป้าหมายคือเอาส่วนที่ไม่มีผู้ใช้ออกและรวมกลไกซ้ำ โดยรักษาพฤติกรรม API, error,
recovery, security และการเทรดเดิม ไม่ใช่งานเพิ่มความสามารถของผลิตภัณฑ์
สถานะการดำเนินงานและ dependency checkpoint ติดตามที่ [roadmap](../../roadmap.md)

## ขอบเขต

### รายการที่จะลบ

ผลตรวจปัจจุบันอ้างอิง source บน `feature/f-17-tp-sl` ที่ `52a00fe`;
ต้องตรวจ references, configuration, tests และ spec ซ้ำบน main หลัง F-17 merge
ก่อนลบจริง การไม่พบผู้ใช้จาก static analysis ไม่ใช่หลักฐานให้ลบ declaration
ที่ framework เรียกอัตโนมัติหรือ spec บังคับให้เก็บ

| รายการ | ตำแหน่ง | สิ่งที่ต้องรักษา |
|---|---|---|
| `read_monitor_owner()` | `backend/src/tiewtrade/infra/risk_limits/storage.py` | `read_monitor_snapshot()` และ `decode_monitor_owner()` ที่ runtime ใช้ |
| `IssuedSession` | `backend/src/tiewtrade/infra/auth/sessions.py` | การออก ตรวจ ต่ออายุ และเพิกถอน session ใน PostgreSQL |
| `ApiKeyStatus.is_final` | `backend/src/tiewtrade/infra/api_keys/records.py` | enum และพฤติกรรมตรวจ/แสดงสถานะ API key เดิม |
| `RiskLimitUnsetError` | `backend/src/tiewtrade/core/risk_limits.py` | รหัส `RISK_LIMIT_UNSET` และชนิดข้อผิดพลาดอื่นที่ยังใช้อยู่ |
| `fetchOrder()` | `frontend/src/manualOrders.ts` | `fetchOrders()`, type `PaperOrder` และ endpoint หลังบ้าน |
| `fetchHealth()` | `frontend/src/api.ts` | type `Health`, health endpoint และ API-contract/E2E tests |
| type alias `CatalogPair` | `frontend/src/marketCatalog.ts` | schema `CatalogPairView`, `CatalogEntry` และ `core.market_catalog.CatalogPair` ฝั่ง backend |

ลบเฉพาะ declaration ข้างต้นและ import ที่หมดความจำเป็นจากการลบ
ไม่ขยายไปลบ exported types หรือ helpers อื่นโดยอัตโนมัติ

### กลไกที่จะใช้ร่วมกัน

- การกรอง API error ของ `apiKeys.ts`, `tradingAccount.ts`, `paperWallet.ts`,
  `manualOrders.ts`, `protections.ts`, `riskLimits.ts` และ `killSwitch.ts`
  ต้องใช้ implementation กลาง โดยแต่ละ module รักษา policy เดิมของตัวเอง
- การตรวจว่าเป็น object ใน `manualOrderJournal.ts`, `riskLimitJournal.ts`
  และ `protectionJournal.ts` ต้องใช้ type guard กลาง
- เปลี่ยน unused parameter `url` เป็น `_url` ในสาม callbacks ที่ตรวจพบ:
  `ApiKeyPanel.test.tsx` หนึ่งจุด และ `RiskLimitPanel.test.tsx` สองจุด
  โดยคงตำแหน่ง argument และ assertions เดิม

### ไม่รวมในงานนี้

เก็บ `StopActor` ตาม F-19, โค้ดกราฟเดิม, helpers ที่ยังใช้ใน tests/profiling,
risk monitor สำหรับ rollback และ protocol/fake/implementation ที่แยกโดยเจตนา
ไม่รวม formatter เวลา, task cleanup, risk receipt routes, venue REST หรือ stop policy
ไม่เปลี่ยน UI, HTTP API/OpenAPI, database schema/migration, infrastructure,
dependencies, TypeScript configuration, session storage หรือเอกสารหลักฐานย้อนหลัง

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | ลบเฉพาะเจ็ดรายการในตารางหลังตรวจยืนยันว่าไม่พบผู้ใช้และไม่ขัด spec บนฐานหลัง F-17 merge; ถ้าพบ caller หรือข้อกำหนดใหม่ ให้หยุดรายการนั้นเพื่อทบทวนขอบเขตก่อนแก้ | แผนที่เจ้าของให้ดำเนินการ; AGENTS.md |
| RQ-02 | API error wrappers ทั้งเจ็ดใช้กลไกเดียวกันโดยคง allowlist, fallback, status, AbortError และ Retry-After ของแต่ละ module ตามตารางด้านล่าง; ไม่ถือว่าการรวม helper อนุญาตให้ปรับ policy | แผน cleanup; security §3–4 |
| RQ-03 | ใช้ `ApiRequestError` และตัวส่ง `send()` เดิม; success ต้องคืนค่าเดิม และ signature ของ API functions ที่ยังใช้อยู่ต้องไม่เปลี่ยน | แผน cleanup; tech-stack §3 |
| RQ-04 | รหัสใน allowlist มีลำดับก่อน fallback ตาม status; risk limits คง fallback เฉพาะ 403/429 และ API keys คง `API_KEY_REQUEST_FAILED`; unknown/network errors ใช้ fallback เดิมพร้อม status 0 เมื่อไม่ใช่ `ApiRequestError` | พฤติกรรมเดิมที่เจ้าของระบุให้รักษา |
| RQ-05 | ไม่เพิ่ม request, retry, logging หรือการแนบ error ดิบ/secret ใน sanitized error ที่ส่งต่อ; การ pass-through AbortError คงเงื่อนไขและ object เดิมสำหรับ modules ที่มีพฤติกรรมนี้ | แผน cleanup; security §4 |
| RQ-06 | object guard กลางให้ผล true เฉพาะ object ที่ไม่ใช่ null หรือ array ตามพฤติกรรมเดิม; ไม่เพิ่มการตรวจ prototype หรือเปลี่ยนการยอมรับ payload ของ journal | แผน cleanup |
| RQ-07 | คง journal validation, owner/mode isolation, storage prefix, version, request key, payload precision, readback และ fail-closed behavior เดิม; ไม่เปลี่ยนการกู้คำขอหรือ idempotency | แผน cleanup; trading-safety §4/7 |
| RQ-08 | รักษา Money/Quantity, trading rules, Paper/Live isolation, risk, transaction/locking และ session ใน PostgreSQL; ไม่เปิด Live หรือเพิ่ม persistent state ใน process memory | AGENTS.md; architecture; trading-safety; security |
| RQ-09 | เขียน characterization tests ผ่าน API functions จริงก่อนย้าย error handling; ใช้ tests เดิมสำหรับ journal/components และเพิ่มเฉพาะความเสี่ยงที่ยังไม่มีหลักฐาน โดยเฉพาะ risk journal | แผน cleanup; testing §7 |
| RQ-10 | ระหว่างพัฒนาใช้ targeted checks; ก่อน merge ต้องผ่าน frontend regression เต็มบน candidate ที่นิ่ง, frontend lint/typecheck/build/unused checks, backend Ruff/mypy/import-linter/targeted regression, review และ required CI | แผน cleanup; testing §6–7 |
| RQ-11 | ไม่ลด tests/assertions/thresholds เพื่อให้ผ่าน และไม่เพิ่ม workload/endurance หรือ Live orders สำหรับ cleanup; คงสถานะ validation ค้างของ feature เดิมตามจริง | แผน cleanup; testing §4–7 |
| RQ-12 | ใช้ branch `feature/code-cleanup` จาก main ล่าสุดหลัง F-17 merge; รักษางานค้างของเจ้าของ; requirements และ plan/validation ต้องได้รับอนุมัติครบก่อนแก้ source; commit/push/merge เฉพาะเมื่อเจ้าของสั่ง | ตัวเลือกเจ้าของเรื่องลำดับงาน; AGENTS.md |

### พฤติกรรม error ที่ต้องรักษา (RQ-02..05)

| กลุ่ม | AbortError (`DOMException` ที่ name เป็น `AbortError`) | Retry-After | การเลือกรหัส |
|---|---|---|---|
| API keys | แปลงตาม fallback เดิม | รักษา | `API_KEY_REQUEST_FAILED` เสมอ |
| Trading account / Paper wallet | แปลงตาม fallback เดิม | รักษา | allowlist เดิม แล้ว fallback ของ module |
| Manual orders / Protections | ส่งต่อ object เดิม | รักษา | allowlist เดิม แล้ว fallback ของ module |
| Risk limits | ส่งต่อ object เดิม | รักษา | allowlist เดิม ก่อน 403 → `RISK_AUTHORIZATION_REQUIRED`, 429 → `RISK_RATE_LIMITED`; กรณีอื่น `RISK_REQUEST_FAILED` |
| Kill switch | ส่งต่อ object เดิม | ไม่รักษา ตามพฤติกรรมเดิม | allowlist เดิม แล้ว `TRADING_STOP_REQUEST_FAILED` |

Retry-After ที่รักษาคือค่า `retryAt` ซึ่ง `ApiRequestError` เดิมแปลงแล้ว
ไม่สร้างกฎ parsing ใหม่และไม่เริ่มนับเวลารอใหม่ การทดสอบต้องตรึงเวลาเมื่อจำเป็น
เพื่อแยกพฤติกรรมที่เปลี่ยนจริงจากเวลาที่ผ่านไประหว่างการตรวจ

## กฎความปลอดภัยที่เกี่ยวข้อง

- [Architecture](../../standards/architecture.md): dependency boundaries และ persistent state เดิม
- [Trading safety](../../standards/trading-safety.md): Paper/Live isolation, credential protection,
  order safety และ idempotency; automated validation ห้ามส่ง Live orders
- [Security](../../standards/security.md): session ใน PostgreSQL และไม่เปิดเผย secret/raw errors
- [Backend](../../standards/backend.md) และ [Frontend](../../standards/frontend.md):
  ใช้โค้ดกลางซ้ำและไม่คำนวณเงินใหม่; งานนี้ไม่แก้ appearance/components ของ UI
- [Testing](../../standards/testing.md) §6–7: plan/validation ถัดไปต้องจัดเกณฑ์เป็น
  Feature/Batch/Release และระบุหลักฐานที่ใช้ซ้ำตามผลกระทบ

## ยังไม่ชัด / จุดหยุด

- ไม่มี Needs Clarification ด้านธุรกิจหรือกฎเทรดสำหรับขอบเขตนี้
- เจ้าของอนุมัติ requirements ฉบับนี้แล้ว; ต้องขออนุมัติ `plan.md` และ `validation.md`
  แยกก่อน implementation ตาม [AGENTS.md](../../../AGENTS.md)
- ต้องยืนยัน F-17 merge ก่อนสร้าง implementation branch จาก main ล่าสุด
  การอนุมัติ spec ไม่ใช่คำสั่ง merge F-17 หรือ commit/push/merge cleanup
- เมื่อ implementation ครบ ให้แจ้ง Ready for Code Review และหยุดรอ `review code`;
  review/refactor และด่านก่อน merge ใช้จุดหยุดตาม AGENTS.md เดิม
