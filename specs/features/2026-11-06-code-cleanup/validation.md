# Code cleanup และ shared frontend helpers — Validation

สถานะ: **Approved — เจ้าของอนุมัติ validation 2026-11-06**
วันที่: 2026-11-06

อ้างอิง [requirements](requirements.md), [plan](plan.md) และ
[testing §6–7](../../standards/testing.md); สถานะงานอยู่ที่ [roadmap](../../roadmap.md)
ทุกเกณฑ์ด้านล่างเป็น Feature เพราะพิสูจน์ความถูกต้องของ cleanup ก่อน merge
ผล implementation validation บันทึกใน [checkpoint](evidence/implementation-checkpoint.md); ผล audit ก่อนงานไม่ใช้แทนผล candidate

## 1. เกณฑ์ตรวจรับ

| รหัส | ข้อกำหนด | เกณฑ์และวิธีพิสูจน์ | ระยะ | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | RQ-01/12 | บันทึก base SHA จาก main หลังยืนยัน F-17 merge, approval ครบ, branch แยก และ reference/spec audit ของเจ็ด declarations ไม่มี caller ที่ต้องรักษา; working tree เดิมของเจ้าของไม่ถูกแก้ทับ | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-02 | RQ-01/03 | ลบครบเจ็ด declarations และเฉพาะ import ที่หมดผู้ใช้; retained symbols/endpoint/Health/backend CatalogPair ยังอยู่; ตรวจ diff, references และ static checks ไม่ใช้เทสต์ assert deletion | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-03 | RQ-02..05/09 | policy tests ผ่าน public APIs ทั้งเจ็ด modules บน code เดิมก่อน extraction และผ่านชุดเดียวกันหลัง extraction โดยไม่เปลี่ยน expected results | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-04 | RQ-02..05 | success/204, ทุก allowed code, fallback, status, 403/429 precedence, AbortError และ Retry-After ครบตาม matrix §2; assertions ไม่อ่าน expected policy จาก production config | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-05 | RQ-03/05/08 | error sentinel ไม่หลุดใน sanitized error และไม่มี raw cause; helper ไม่เรียก fetch/log/storage เอง; mutation cases คง URL/method/body/signal/credentials/CSRF/TOTP/idempotency headers และมี request เดียวเมื่อเกิด failure | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-06 | RQ-06/07 | object guard ยอมรับและปฏิเสธค่าเท่าเดิม; journals ทั้งสามไม่มี local object-guard copy และ validations อื่นไม่เปลี่ยน ตรวจ cases และ diff | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-07 | RQ-07/09 | journal recovery tests ผ่าน: precision, owner/mode scope, persisted key, corruption, readback/write/remove failure และ clear เฉพาะ expectedKey; risk journal ครบ §3 | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-08 | RQ-02..09 | targeted component/caller regression ตาม §4 ผ่าน โดยคง unknown outcome recovery, TOTP gates, stop/error states และไม่ส่ง mutation ซ้ำ | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-09 | RQ-01/08 | backend core risk regression ตาม §4 ผ่าน และ diff ไม่มีการเปลี่ยน SQL/session/transaction/trading policy; ถ้าไม่ใช่ deletion-only ตามแผน ให้หยุดทบทวนผลกระทบและ spec | Feature | Passed — local; [checkpoint](evidence/implementation-checkpoint.md) |
| V-10 | RQ-10 | frontend lint/typecheck/build และ noUnusedLocals/noUnusedParameters ผ่าน; backend Ruff check/format check, mypy, import-linter ผ่าน | Feature | Passed — full static/type/unused/build หลัง refactor; [checkpoint](evidence/implementation-checkpoint.md) |
| V-11 | RQ-01/03/10 | frontend Vitest regression เต็มผ่านบน candidate ที่นิ่ง รวม API-contract positive/negative cases; backend OpenAPI และ generated frontend contract ไม่มี diff จากงานนี้ | Feature | Passed — 662 tests / 39 files รวม API-contract gate หลัง refactor; [checkpoint](evidence/implementation-checkpoint.md) |
| V-12 | RQ-08/10/11 | code review ตามคำสั่งเจ้าของและ findings ที่เกี่ยวข้องปิดครบ; retained behavior มีหลักฐาน ไม่มี scope creep/Live orders และ pending validation ของ feature อื่นไม่ถูกปิด | Feature | Passed — owner-directed review และตรวจ authorized refactor 2026-11-06 ไม่พบ actionable findings; [checkpoint](evidence/implementation-checkpoint.md) |
| V-13 | RQ-10/12 | required CI ของ PR บน SHA ล่าสุดผ่านทุก required check ตาม configuration ณ เวลานั้น; บันทึก SHA และ run URLs แยกจาก local results ก่อน merge | Feature | Not Run — ยังไม่มี cleanup commit/PR/CI |
| V-14 | RQ-12 | เมื่อเจ้าของสั่ง merge: ตรวจ Feature gates, merge และติดตาม post-merge CI บน merge SHA จนจบ; บันทึกผลจริงก่อนปิด checkpoint ไม่ถือว่าเปิด PR อนุญาต merge | Feature | Not Run — ยังไม่ได้รับคำสั่ง merge |

V-01..V-13 เป็นด่านก่อน merge; V-14 เป็นด่านปิด checkpoint หลัง owner-authorized merge
ถ้ารายการลบถูกพักเพราะพบ caller ใหม่ V-02 ยังไม่ Passed จนเจ้าของอนุมัติขอบเขตใหม่
ไม่ใช้การผ่านรายการอื่นกลบ blocker นั้น

## 2. API error characterization matrix

เพิ่ม `frontend/tests/apiRequestPolicies.test.ts` ก่อน extraction ใช้ real API functions
และ `send()` จริง Stub `globalThis.fetch` ด้วย Vitest เพื่อไม่ต่อ backend/exchange
Response/throw fixtures เป็นข้อมูลสังเคราะห์ ไม่มี credential จริง
ไม่ mock `createSafeRequest` หรือ `send` และไม่ใช้ helper config สร้าง expected results

เลือก GET หนึ่งตัวต่อ module ตาม plan §3.4 แล้วตรวจกรณีต่อไปนี้:

| กลุ่มกรณี | สิ่งที่ต้อง assert |
|---|---|
| 200 และ 204 | JSON value ไม่ถูกแปลง; `deleteApiKey` คืน undefined เมื่อ 204; request เดียว |
| allowed codes | แต่ละสมาชิกของ allowlist เดิมส่งต่อ code/status ถูกต้อง; API keys ไม่มี allowed code และใช้ fallback เสมอ |
| unknown code / non-JSON proxy / network failure | fallback ของ module; HTTP status คงเดิม ส่วน thrown non-ApiRequestError ใช้ 0; ไม่เปิดเผย raw message |
| status 403/429 | ทดสอบทั้ง allowed และ unknown code; เฉพาะ risk ใช้ status fallback และ allowed code ต้องชนะ mapping |
| AbortError | ใช้ DOMException จริง; สี่ modules ที่ pass-through ต้องคืน error object เดิม; อีกสามใช้ fallback/status 0; Error ที่แค่ชื่อ AbortError ต้องไม่ถูก pass-through |
| Retry-After | missing, invalid, delta-seconds, HTTP date และ ISO ที่ parser เดิมรับ; ตรึงเวลาและ assert retryAt exact; kill switch ต้องเป็น null |
| ไม่ขยายเวลา Retry-After | สร้าง ApiRequestError ที่มี retryAt แล้วให้ fetch reject หลังเลื่อน clock; modules ที่ preserve ต้องคง deadline เดิม ไม่บวก delay ใหม่ |
| error isolation | ใส่ synthetic sentinel ในข้อความ unknown HTTP/network error; ตรวจ message, own fields/serialization และ cause ของ sanitized error ไม่เก็บ sentinel/raw error; ไม่ใช้เงื่อนไขนี้เปลี่ยน intentional AbortError pass-through |

เพิ่ม mutation fixture ต่อ module: `addApiKey`, `selectTradingUse`, `createPaperWallet`,
`postNewOrder`, `postProtection`, `postRisk`, `postStop` และ `deleteApiKey`
ตรวจ request arguments เดิมด้วย fake credentials/CSRF/TOTP ใน tests เท่านั้น;
ใช้ unknown/network failure ตรวจว่าหนึ่ง invocation ส่งหนึ่ง request ไม่ retry/duplicate
แนบ AbortSignal ใน GET case และตรวจว่า sender ได้ signal object เดิม
หลังแต่ละ test คืน mocks, clock, cookies และ storage ที่ fixture ใช้

UI tests เดิมที่ตรวจ secrets ไม่ลง mutation cache และ pending command recovery ต้องผ่าน
ไม่เพิ่มการ snapshot stack trace เพราะตำแหน่ง helper เปลี่ยนโดยธรรมชาติของ refactor

## 3. Journal และ object guard

ใช้ `manualOrderJournal.test.ts` และ `protectionJournal.test.ts` เดิม
เพิ่มเฉพาะ coverage ที่ขาด และเพิ่ม `riskLimitJournal.test.ts` ก่อน extraction:

- Paper SET/DECREASE/INCREASE และ RESET round-trip ด้วย owner/mode/key/episode/revision
  เดิมและจำนวนเงินเป็น string ที่มีความละเอียดสูง; Live ใช้ null wallet/episode ตาม schema เดิม
- owner อื่นและ Paper/Live อีก scope อ่านไม่เห็น intent; value ที่ประกาศ scope ไม่ตรง
  storage key ต้อง fail closed ไม่ถือว่าไม่มี pending request
- JSON เสีย, root/payload เป็น null/array/primitive, key/version/action/revision ไม่ผ่าน
  และ keys เกิน/ขาดตาม validator เดิม ต้องให้ผลเดิม ไม่เพิ่ม payload validation ใหม่
- อ่านข้ามการโหลด module ใหม่โดยใช้ sessionStorage เดิมแล้ว key/payload ยังตรง
  ไม่สร้าง request key ใหม่เมื่อ recovery
- denied get/set/remove, silent write/remove failure, malformed readback ต้องคง
  JournalUnavailable semantics; missing entry ยังคง null และ expectedKey ไม่ตรงต้องไม่ลบ
- bracket/explicit sale allocation fixtures ใน protectionJournal tests เดิมยังผ่าน
  และไม่เปลี่ยน UUID regex ที่ต่างกันระหว่าง journals

`isRecord.test.ts` ตรวจ null/undefined, string/number/boolean/bigint/symbol,
array และ function เป็น false; plain object, Object.create(null), Date และ class instance
เป็น true ตาม predicate เดิม ตรวจว่า input ไม่ถูกแก้หรือ normalize
ไม่สร้างเทสต์รูปแบบ AST เพื่อบังคับ syntax ของ guard

## 4. ชุดตรวจตามผลกระทบและคำสั่ง

ใช้ Python/Node versions และ dependencies ตาม lockfiles ของฐานหลัง F-17 merge
ไม่อัปเกรด dependencies ระหว่าง cleanup คำสั่งด้านล่างรันจาก directory ที่ระบุ
ไม่ต้องรัน runtime tests ในรอบอนุมัติเอกสารนี้

### ระหว่างพัฒนา

จาก `frontend/` ก่อนและหลัง extraction:

```sh
npm run test -- tests/apiRequestPolicies.test.ts tests/manualOrderJournal.test.ts tests/protectionJournal.test.ts tests/riskLimitJournal.test.ts
```

หลังสร้าง guard ให้เพิ่ม `tests/isRecord.test.ts` ในรอบเดียวกับ affected journal rerun
หลังย้าย callers รัน:

```sh
npm run test -- tests/ApiKeyPanel.test.tsx tests/TradingAccountPanel.test.tsx tests/PaperWalletPanel.test.tsx tests/ManualOrderForm.test.tsx tests/ManualOrderSession.test.tsx tests/PaperOrderList.test.tsx tests/RiskLimitPanel.test.tsx tests/KillSwitchControls.test.tsx
```

จาก `backend/` หลังลบ declarations:

```sh
uv run pytest tests/core/test_risk_limits.py tests/core/test_risk_matching.py
```

Backend diff เป็น deletion-only ของ declarations ที่ไม่มี caller จึงไม่สร้าง DB tests
หรือ mock transaction เพิ่ม การทำงาน session/API keys/monitor เดิมยังถูกครอบโดย required CI
ถ้า diff เกินขอบเขตนี้ ไม่ใช้เหตุผล deletion-only ยกเว้น DB/concurrency safety tests
ให้หยุดทบทวนแผนตามกฎ spec ก่อนเปลี่ยน runtime เพิ่ม

### Candidate ก่อน merge

จาก `frontend/`:

```sh
npm run lint
npm run typecheck
./node_modules/.bin/tsc --noEmit --noUnusedLocals --noUnusedParameters
npm run build
npm run test
```

`npm run test` คือ Vitest suite เต็ม รวม `tests/gates/api-contract.test.ts`;
ไม่หมายถึงรัน Playwright ทุก config ซ้ำบนเครื่อง local โดยอัตโนมัติ
ก่อน full regression แจ้งสิ่งที่จะพิสูจน์และเวลาประมาณตามเครื่องจริง
กรอบวางแผนเบื้องต้น 5–15 นาทีสำหรับ frontend regression/static/build รวมกัน
ไม่ใช่ timeout/SLA หรือผลวัด และไม่ใช้ตัดการตรวจที่จำเป็น

จาก `backend/`:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run lint-imports
```

ใช้ผล targeted backend tests ที่ยัง valid; ไม่รันซ้ำเป็นพิธี
ตรวจว่า backend/openapi.json และ frontend/src/api-types.ts ไม่มี cleanup diff
API contract CI ยังคงตรวจ generated contract จริง ไม่แก้ schema เพื่อให้ tests ผ่าน

### Required CI และหลักฐาน

หลังเจ้าของสั่งเปิด PR ติดตาม checks ตาม branch protection/CI บน SHA ล่าสุด
workflow ที่ตรวจตอนร่างมี config, backend, api-contract, frontend, e2e และ docker
โดย browser CI มี Paper manual/protection/risk suites และ isolated test databases
ไม่ข้าม browser/DB safety checks เหล่านี้เพราะ local tests ใช้ fetch stubs
ไม่แก้ workflow หรือ reset ฐานข้อมูลที่เจ้าของใช้งานเพื่อรัน cleanup

หาก CI configuration เปลี่ยนก่อน implementation ให้ตรวจ required checks จริง
ไม่ใช้รายชื่อข้างต้นเป็นเหตุให้ข้าม gate ใหม่ และไม่ใช้ local pass แทน CI
บันทึก candidate SHA, commands/results, run URLs และ limitations ใน
`evidence/implementation-checkpoint.md` เมื่อมีผลจริง; รวบผลที่ปิดหลายเกณฑ์ในครั้งเดียวได้

## 5. การตรวจด้วยมือ การใช้ผลเดิม และงานค้าง

- ตรวจ diff ว่าไม่มี HTTP endpoint/signature/UI/SQL/storage/policy/dependency changes
  นอก approved deletions และไม่แตะ source ของ feature อื่นนอกขอบเขต helper migration
- ไม่มี UI appearance change จึงไม่กำหนด visual/manual-browser acceptance ใหม่;
  ใช้ component regression และ required browser CI สำหรับ behavior ที่ได้รับผลกระทบ
- ใช้ผลเดิมได้เมื่อ source/callers/dependencies/contracts/environment/harness ที่มัน
  พิสูจน์ยังไม่เปลี่ยน หลัง review/refactor รันซ้ำเฉพาะชุดที่ได้รับผลกระทบ
- ไม่มี Batch/Release gate ใหม่ของ cleanup; full workload/endurance และ pending gates
  ของ feature เดิมยังอยู่ใน validation/roadmap ของแต่ละงาน ไม่ยกเป็น Passed จาก cleanup
- ทุก Not Run/Failed/Partial ต้องคงตามจริง ถ้าขาด approved baseline หรือพบ conflict
  ให้บันทึก Needs Clarification และส่วนที่บล็อก ไม่ปรับ expected results ให้เข้ากับ refactor
- Ready for Code Review, จุดถาม refactor, Git authorization และการปิด checkpoint
  ใช้ [AGENTS.md](../../../AGENTS.md) และ testing §7 โดยไม่ข้ามขั้น
