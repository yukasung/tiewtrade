# Code cleanup และ shared frontend helpers — Plan

สถานะ: **Approved — เจ้าของอนุมัติ plan 2026-11-06**
วันที่: 2026-11-06

อ้างอิง [requirements](requirements.md) ที่เจ้าของอนุมัติ 2026-11-06
และ [validation](validation.md); สถานะงานติดตามที่ [roadmap](../../roadmap.md)

## 1. แนวทางและฐาน implementation

เปลี่ยนโครงสร้างโดยรักษาพฤติกรรม: ลบเฉพาะเจ็ด declaration ตาม RQ-01,
รวม API error handling และ object guard ตาม RQ-02..07 และแก้ unused parameters
สามจุด การคำนวณเงิน การเทรด SQL/transaction, HTTP contract และ UI ไม่เปลี่ยน

ก่อนแก้ source ต้องผ่านเงื่อนไขทุกข้อ:

1. requirements, plan และ validation อนุมัติครบ และไม่มี Needs Clarification ที่เกี่ยวข้อง
2. ยืนยัน F-17 merge จาก PR/merge SHA และ main ที่อัปเดตแล้ว; ตรวจว่า main มีผล F-17
   จริง รวมกรณี squash merge ไม่ใช้การเทียบชื่อ branch อย่างเดียว
3. สร้าง `feature/code-cleanup` จาก main ล่าสุดใน worktree แยก เพื่อรักษา working tree
   เดิมของเจ้าของ ไม่ stash/reset/ย้ายงานอื่นเข้ามา; ย้ายเฉพาะเอกสาร cleanup และ
   เพิ่มเฉพาะรายการ cleanup ใน roadmap ของฐานใหม่ ไม่คัดลอก roadmap ทั้งไฟล์ทับ main
4. บันทึก base SHA และตรวจ references ซ้ำทั้ง source, tests, scripts, migrations,
   configuration/entrypoints และ specs ของเจ็ด declaration; ตรวจ policy ของ wrappers
   และ journal เทียบ audit `52a00fe` ด้วย ถ้า base ใหม่เปลี่ยน behavior จนขัด requirements
   ให้บันทึก Needs Clarification และหยุดส่วนที่เกี่ยวข้องก่อนลงมือ

spec นี้ไม่อนุญาต merge F-17, commit/push/PR/merge cleanup หรือแตะงานค้างอื่น
ถ้าพบ implementation branch ชื่อนี้อยู่แล้ว ให้ตรวจ provenance และใช้ต่อเมื่อเป็นงานเดียวกัน;
ไม่เขียนทับ branch ที่มีงานอื่น

## 2. ของเดิมที่จะใช้ซ้ำ

| ของเดิม | Path | การใช้ |
|---|---|---|
| `ApiRequestError`, `send()` | `frontend/src/auth.ts` | ใช้ error type, Retry-After parser, cookies/CSRF/TOTP และ HTTP sender เดิมโดยไม่แก้ไฟล์นี้ |
| allowlist/fallback ของเจ็ด modules | `frontend/src/{apiKeys,tradingAccount,paperWallet,manualOrders,protections,riskLimits,killSwitch}.ts` | ย้ายข้อมูล policy เข้า configuration ภายใน module เดิม; ไม่รวม allowlist ของหลาย feature |
| `sessionJournal`, `JournalUnavailable` | `frontend/src/attemptJournal.ts` | ใช้ storage/readback/clear semantics เดิม ไม่สร้าง journal engine ใหม่ |
| journal validators | `frontend/src/{manualOrderJournal,riskLimitJournal,protectionJournal}.ts` | เปลี่ยนเฉพาะการเรียก object guard ส่วนกฎ payload คงเดิม |
| journal regression | `frontend/tests/{manualOrderJournal,protectionJournal}.test.ts` | ใช้ assertions เดิมเรื่อง precision, scope และ recovery |
| UI/API regression | `frontend/tests/{ApiKeyPanel,TradingAccountPanel,PaperWalletPanel,ManualOrderForm,ManualOrderSession,PaperOrderList,RiskLimitPanel,KillSwitchControls}.test.tsx` | พิสูจน์ callers และ workflow ที่รับ sanitized errors |
| API contract gate | `frontend/tests/gates/api-contract.test.ts`, `frontend/e2e/health.spec.ts` | ยังคง type `Health` และตรวจ contract เดิมหลังลบ wrapper ที่ไม่มีผู้ใช้ |
| core risk tests | `backend/tests/core/test_risk_limits.py`, `backend/tests/core/test_risk_matching.py` | ตรวจ risk behavior เดิมหลังลบ exception class ที่ไม่มีผู้ใช้ |

ค้นแล้วไม่พบ shared error sanitizer หรือ object guard กลางที่ใช้แทนได้ในขอบเขตนี้
ไม่มีการแก้ layout/component/style จึงไม่ต้องสร้าง component จาก admin template

## 3. การเปลี่ยนแปลง

### 3.1 ลบ declarations ตาม RQ-01

ใช้ตารางรายการและสิ่งที่ต้องรักษาใน requirements เป็นบัญชีเดียว ไม่เพิ่มรายการลบ
ลบ definition และ import ที่เหลือ unused เพราะการลบนั้นเท่านั้น
คง module files ที่ยังมีผู้ใช้ โดยเฉพาะ `frontend/src/api.ts` ซึ่งยัง export `Health`
และคง backend `core.market_catalog.CatalogPair` ซึ่งเป็นคนละชนิดกับ frontend alias

หากพบ caller ใหม่ ห้ามลบ caller หรือเปลี่ยน business behavior เพื่อทำให้รายการนั้น
กลายเป็น unused; หยุดรายการนั้นเพื่อทบทวนตาม RQ-01 และบันทึกเกณฑ์ที่ยังปิดไม่ได้
ไม่เพิ่มเทสต์ที่เพียง assert ว่าสัญลักษณ์ถูกลบ ใช้ reference audit, static checks
และ regression ของระบบเดิมเป็นหลักฐาน

### 3.2 Shared API error helper

เพิ่ม `frontend/src/apiRequest.ts` โดย import `ApiRequestError` จาก `auth.ts` เท่านั้น
ไม่มี network/storage access ใน helper และไม่มี import ย้อนจาก `auth.ts` มาที่ helper

```ts
export type ApiErrorPolicy = Readonly<{
  allowedCodes: readonly string[];
  fallbackCode: string;
  statusFallbacks?: ReadonlyMap<number, string>;
  preserveAbort: boolean;
  preserveRetryAfter: boolean;
}>;

export function createSafeRequest(policy: ApiErrorPolicy):
  <T>(request: Promise<T>) => Promise<T>;
```

แต่ละ module สร้าง `const safe = createSafeRequest({...})` หนึ่งครั้งแทน local function
และคง call sites `safe(send(...))` เดิม ใช้ array ของรหัสจาก allowlist เดิม;
กรณีไม่มีรหัสที่ยอมรับ เช่น API keys ให้ส่ง empty array
policy เป็น module-local configuration ที่ไม่มีข้อมูลผู้ใช้ ไม่ export singleton
สำหรับ session/request state และไม่ mutate policy หลังสร้าง helper

ลำดับทำงาน:

1. `await` Promise ที่ผู้เรียกส่งมาและคืน success value เดิม รวม `undefined` จาก HTTP 204
2. ถ้า `preserveAbort` และเป็น `DOMException` ชื่อ `AbortError` ให้ throw object เดิม
   ไม่ขยายเงื่อนไขเป็นเพียง object ที่มี property `name`
3. ตรวจ `instanceof ApiRequestError` เพื่ออ่านเฉพาะ `message`, `status`, `retryAt`;
   กรณีอื่นใช้ status 0 โดยไม่อ่าน field ของ arbitrary thrown value
4. เลือก code จาก allowlist ก่อน; ถ้าไม่อยู่ ให้ใช้ `statusFallbacks.get(status)`
   สำหรับ API error ที่มี mapping แล้วจึง `fallbackCode`
5. สร้าง `ApiRequestError` ใหม่ด้วย code/status และ `retryAt` เดิมเมื่อ policy ให้รักษา
   มิฉะนั้นส่ง null ไม่ parse Retry-After เอง ไม่แนบ `cause`, raw error หรือ payload

ค่าของ `preserveAbort`/`preserveRetryAfter` ยึดตาราง RQ-02..05 ใน requirements
เฉพาะ risk limits มี statusFallbacks: 403 → `RISK_AUTHORIZATION_REQUIRED`,
429 → `RISK_RATE_LIMITED`; modules อื่นไม่ใส่ property นี้
คง fallback codes และสมาชิก allowlist จากแต่ละ source module บน approved baseline
แบบหนึ่งต่อหนึ่ง ไม่อนุมาน allowlist จาก OpenAPI หรือข้อความแปล

เอา `ApiRequestError` imports ออกจาก wrappers เมื่อหมดผู้ใช้ แต่คง `send()` import
ไม่แก้ exported API function signatures, URL, method, body, signal หรือ headers
ไม่เพิ่ม retries, logging, cache, timers หรือ request queue

### 3.3 Shared journal object guard

เพิ่ม `frontend/src/isRecord.ts` มี export เดียว:
`isRecord(value: unknown): value is Record<string, unknown>`
เงื่อนไขตรงกับ `typeof value === "object" && value !== null && !Array.isArray(value)`
ไม่ตรวจ prototype/own properties เพิ่ม และไม่ clone/normalize/mutate input

แทนการเรียก `record()` ด้วย `isRecord()` ใน journal ทั้งสามและลบ local guards
คง body ของ `valid()` ส่วนอื่นทุกเงื่อนไข รวม UUID regex ที่ต่างกันและจำนวน keys
ไม่เปลี่ยน `sessionJournal`, `killSwitchJournal`, storage scope หรือ version

### 3.4 Tests และ unused parameters

- เพิ่ม `frontend/tests/apiRequestPolicies.test.ts` ทดสอบ public API functions ของ
  ทั้งเจ็ด modules ผ่าน `send()` จริง โดย stub เฉพาะ `fetch` และใช้ Response fixtures
  ไม่ mock helper หรือ `send()`; expected codes/policies ใน tests ไม่อ่านจาก helper config
- ใช้ representative GET: `fetchApiKeys`, `fetchTradingAccount`, `fetchPaperWallet`,
  `fetchTrade`, `fetchProtections`, `fetchRisk`, `fetchStopStatus`; เพิ่ม mutation case
  ของแต่ละ module และ `deleteApiKey` สำหรับ HTTP 204 ตาม validation
- เพิ่ม `frontend/tests/riskLimitJournal.test.ts` ปิดช่องว่างของ Paper/Live scope,
  persisted intent, corruption และ clear/readback failures; ขยาย journal tests เดิม
  เฉพาะกรณีที่ object guard extraction ยังไม่มีหลักฐาน
- เพิ่ม guard behavior cases ใน `frontend/tests/isRecord.test.ts` เพื่อรักษาการยอมรับ
  object ที่ไม่ใช่ plain object และปฏิเสธ array/null/primitives/functions
- เปลี่ยน `url` เป็น `_url` เฉพาะสาม callbacks ตาม requirements;
  ไม่เปลี่ยน ESLint/TypeScript rules และไม่ย้ายตำแหน่ง parameters

## 4. ผลต่อฐานข้อมูล ความปลอดภัย และความเสี่ยง

ไม่มี migration, SQL, RLS, session lifecycle, transaction/lock หรือ persistent-data changes
การลบ `IssuedSession` ไม่ใช่การเปลี่ยน shared session storage;
PostgreSQL ยังคงเป็น authority สำหรับ session/business data และ journal เดิมเป็น
client recovery intent ไม่ใช่ authority ของยอดเงินหรือสถานะ execution

| ความเสี่ยง | หลักฐานที่จะใช้ปิด |
|---|---|
| รวม error policy จน AbortError/Retry-After หรือ 403/429 เปลี่ยน | ชุด characterization เดียวกันผ่านก่อนและหลังย้าย; ทดสอบ precedence และ object identity |
| ข้อความ error หรือ secret หลุดเข้า UI/cache | unknown/server/proxy/network sentinel cases ผ่าน public APIs และ component tests เดิม |
| journal รับข้อมูลต่างจากเดิมหรือทำ request key หาย | predicate boundary cases และ recovery/storage regression รวม risk journal |
| ลบ code ที่ main หลัง F-17 มีผู้ใช้เพิ่ม | preflight reference/spec audit; ไม่ใช้ผลเก่าแทน candidate ใหม่ |
| backend import หรือ API contract เสียจากการลบ | static checks, core risk tests, API contract gate และ required CI |

## 5. ลำดับ implementation และ checkpoints

1. หลังผ่าน preconditions จัดทำ tests สำหรับ policy/journal แล้วรันบน production code
   เดิม บันทึก base SHA, คำสั่ง และผลก่อน extraction
2. ลบเจ็ด declarations, รวม helper สองกลุ่ม และแก้สาม parameters ตามขอบเขต
3. รัน targeted tests/static checks ตาม validation; ถ้าล้มแก้เฉพาะเหตุที่เกี่ยวข้อง
   และรันซ้ำชุดที่ได้รับผลกระทบ ไม่รันเต็มทุก patch
4. เมื่อ implementation ครบและ targeted checks มีหลักฐาน ให้แจ้ง **Ready for Code Review**
   สรุป diff, ผลตรวจ, validation ค้าง และ risks แล้วหยุดรอ `review code`
   frontend full regression/build/final CI ที่ยังไม่ถึง checkpoint ต้องระบุ Not Run ตามจริง
5. หลัง owner-directed review/fixes ให้ถามเรื่อง `refactor the code` ตาม AGENTS.md
   หลัง refactor ที่อนุมัติให้ทำ validation ต่อ; หากเจ้าของไม่ต้องการ refactor
   ให้ทำ candidate validation ต่อโดยไม่เพิ่มการ refactor เอง
6. บน candidate ที่นิ่ง รัน frontend regression เต็มหนึ่งรอบ, static checks/build
   และ targeted backend regression ที่ยังไม่มีผล valid พร้อมแจ้งเวลาประมาณก่อนชุดเต็ม
   ถ้ารันไปแล้วและมี diff ใหม่ ให้ใช้กฎ reuse evidence ของ testing §7
7. เมื่อเจ้าของสั่ง Git actions ให้ทำตามขอบเขตนั้น; เปิด PR แล้วติดตาม required CI
   บน SHA ล่าสุด; merge เฉพาะเมื่อสั่งและ gates ผ่าน แล้วติดตาม post-merge CI

บันทึกหลักฐานรวมใน `evidence/implementation-checkpoint.md` เมื่อมีผลจริง ไม่สร้าง
ไฟล์ผลว่างหรือ commit เพื่อไล่บันทึก CI ซ้ำ; อัปเดต validation/roadmap ตาม checkpoint
หากตรวจแก้เกณฑ์เดิมไม่ผ่านสามรอบให้หยุดเสนอทางเลือกตาม testing §7

ไม่เพิ่ม Batch/Release workload สำหรับ cleanup; เกณฑ์เดิมของ F-17/F-18/F-19 และ
งานอื่นยังคงสถานะเดิม งานนี้ไม่ปิด pending gates เหล่านั้นแทน
หากเกิด regression ก่อน merge ให้คืนเฉพาะ cleanup diff ใน branch นี้;
หลัง merge การ revert/deploy ต้องมีคำสั่งเจ้าของ และไม่มี database rollback สำหรับงานนี้
