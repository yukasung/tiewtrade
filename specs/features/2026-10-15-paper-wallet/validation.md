# F-13 — กระเป๋า Paper และเงินตั้งต้น — Validation

สถานะ: **Approved** — เจ้าของอนุมัติวันที่ 2026-10-15; F-15 M4 เพิ่ม authoritative reset success ที่ development checkpoint แล้ว แต่ candidate integration gates ยังค้าง

วันที่: 2026-10-15

อ้างอิง [requirements](requirements.md), [plan](plan.md) และ
`specs/standards/testing.md` §7 ไม่ใช้ผล focused tests แทนการตรวจรับที่ยังไม่ครบ

**Integration amendment อนุมัติ 2026-10-18:** ใช้ [F-15 validation §4](../2026-10-18-paper-order-matching/validation.md#4-การปิดงาน-f-13f-14-ที่เกี่ยวข้อง)
สำหรับ source/reset/API/UI integration และ races/faults; ผล Partial/Not Run เดิมคงไว้จนมี
หลักฐานใหม่จริง และหลักฐาน M4 อัปเดตเฉพาะเกณฑ์ที่ทดสอบแล้ว

## “เสร็จ” หมายถึง

ผลเริ่มต้นทุกข้อคือ **Not Run** เพราะยังไม่มี implementation
NC-F13-02 บล็อกเกณฑ์ reset ที่ต้องมีแหล่งจริง; fixture/mock idle อย่างเดียวไม่ปิดเกณฑ์

| # | Requirements | เกณฑ์ / วิธีตรวจ | ระยะรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-1 | RQ-2/10 | strict string → Money, USDT, ทุน >1000, precision/range เดิม, input ผิดไม่เหลือเงิน/episode; golden cases และ Hypothesis | พัฒนา + candidate | **Passed 2026-10-15** — Money boundary/precision และ invalid-input rollback ผ่านใน targeted และ candidate backend |
| V-2 | RQ-2/4/9 | DB round-trip exact, ledger fold ผ่าน Money; ทุนเป็น EXTERNAL_CAPITAL ไม่ใช่ PnL; ไม่ปัดที่ insert | พัฒนา + candidate | **Passed 2026-10-15** — exact PostgreSQL round-trip, ledger fold และ browser amount ทุกหลักผ่าน |
| V-3 | RQ-1/11/13 | real PostgreSQL roles/RLS/FORCE RLS; missing user context และ foreign UUID อ่าน/เขียนไม่ได้; composite FK/mode/unit/unique constraints | พัฒนา + candidate | **Passed 2026-10-15** — real PostgreSQL RLS/ownership/FK/constraints และ migration cycle ผ่าน |
| V-4 | RQ-4/5/9 | UPDATE/DELETE/TRUNCATE ledger/episode/closure/result/input ไม่ได้; reset ไม่เปลี่ยนประวัติ; ไม่มี top-up endpoint/UI หรือ mutable balance | พัฒนา + candidate | Partial — M4 reset เก็บ episode/ledger/closure/audit history และไม่มี top-up surface; candidate ค้าง |
| V-5 | RQ-1/8/12 | retry เดิม/parallel same key → command/admission result/terminal result/ทุน/audit ชุดเดียว; canonical payload เท่ากัน replay, ต่างกัน conflict และ rejection audit ครั้งเดียว; key แยก user/action | พัฒนา + candidate | **Passed 2026-10-15** — parallel admission, canonical replay/conflict, terminal replay และ audited rejection ผ่าน |
| V-6 | RQ-3/7/12 | fault injection ทุกจุดก่อน commit และ audit failure รวม API admission rejection; CREATE/RESET rollback ทั้งชุด ไม่มี dangling command/dispatch/wallet/episode/closure/pointer/ledger/result/audit ครึ่งชุด | พัฒนา + candidate | Partial — CREATE/RESET write/audit rollback และ M5 cancellation/timeout หลัง capital write recover ผ่าน; unknown commit ยังรอ |
| V-7 | RQ-6/7/8 | real connections/workers reset พร้อมกันต่าง key จาก episode เดิม → สำเร็จไม่เกินหนึ่ง; writer แข่ง reset ใช้ lock เดียวกัน; old episode ปฏิเสธ | พัฒนา + candidate | Partial — reset/reset, stale admission และ controlled fill/reset ใช้ lock เดียวกันผ่าน; explicit init/fill/process-kill matrix ยังรอ |
| V-8 | RQ-6/15 | authoritative idle สำเร็จได้; position/open order/unknown/source error/revision เปลี่ยนตรวจแล้ว fail-closed; ไม่มี false-safe fallback | พัฒนา + candidate | Partial — authoritative idle/absent/pending/open และ M5 proof mismatch/CONFLICTED position+order 4 cases fail closed ผ่าน; full candidate ยังรอ |
| V-9 | RQ-3/7/8/15 | restart ก่อน/หลัง commit, lost response, duplicate delivery, cancellation/timeout/worker สองตัว; claim expiry/backoff/fairness และคำขอล้มซ้ำไม่ขวางผู้ใช้อื่น; recovery ไม่เพิ่มทุนซ้ำ; scan ไม่เขียน/อ่านยอด | พัฒนา + candidate | Partial — restart/claim expiry, duplicate scan, workers, backoff/fairness, unknown failure และ M5 cancellation/timeout ผ่าน; post-commit unknown/process kill ยังรอ |
| V-10 | RQ-4/9/14 | GET แข่ง reset ได้ snapshot เก่าหรือใหม่ที่ครบชุด; ไม่มี pointer/ทุน/ยอดปน episode; replay คืนผลเดิมแม้เปลี่ยนรอบแล้ว | พัฒนา + candidate | Partial — terminal replay ข้าม episode, M5 controlled production GET/reset barrier และ final clean backend full run 2934 tests ผ่าน; required CI ยังรอ |
| V-11 | RQ-12/13/15 | success/rejection audit ถูก owner/action/mode/outcome, ไม่มี secret/log echo; Paper entrypoint ทำงานโดยไม่มี venue key และไม่เรียก network/credential; negative gate fixtures ต้องแดง | พัฒนา + candidate | **Passed 2026-10-15** — audit/secret canary/Paper isolation gate ผ่าน และ E2E ทำงานโดยไม่มี venue key/TOTP |
| V-12 | RQ-1/2/10/15 | component tests exact amounts, loading/pending/error/stale/disabled/retry, no optimistic balance, no Number/float, i18n และ admin-template states | พัฒนา + candidate | **Passed 2026-10-15** — frontend full suite 244 tests, lint/type/build และ responsive screenshots ผ่าน |
| V-13 | RQ-1..15 | browser → API → durable command → real Paper worker → PG → UI: create/reload/retry/reset/retained history และสอง user; ไม่ mock ledger หรือ idle proof เพื่อรับรอง reset | พัฒนา smoke + candidate E2E | Partial — real source browser reset/reload, M5 full Chromium 18 tests และ final clean backend full run 2934 tests ผ่าน; DB retained history/owner isolation และ component retry/conflict ผ่าน แต่ explicit browser สอง user ยังค้าง |
| V-14 | RQ-11/14/15 | identity swap/logout/401/late response, generated OpenAPI types, CSRF/auth/route policy, safe errors และ PAPER_WALLET_MUTATION quota/replay semantics; no API key/TOTP เป็นเงื่อนไขใช้ Paper | พัฒนา + candidate | **Passed 2026-10-15** — identity isolation, route policy/quota, safe errors และ generated contract gate ผ่าน |
| V-15 | ทุกข้อ | review diff/dependencies, full regression, lint/types/imports/build/generated contracts/required CI ครบสำหรับ candidate สุดท้าย | ก่อน merge | **Passed 2026-10-16** — final review, local full candidate และ required push/PR/post-merge CI ผ่าน |

Completed ต้องผ่าน V-1..15 ครบ ไม่มี Needs Clarification ที่บล็อกและไม่มี reset success
ที่รับรองด้วย fake source หากส่ง create/read ก่อนตามข้อเสนอ ต้องระบุ partial checkpoint
และคง F-13 In Progress ไม่ใช้คำว่า Completed หรือทำเครื่องหมาย reset Passed

## ตัวเลขจริงและคุณสมบัติ

เทียบคำตอบที่คำนวณอิสระจาก implementation ห้ามเรียก helper ที่กำลังทดสอบสร้าง oracle

- `"1000"`, `"1000.000000000000000000"`, ศูนย์, ค่าลบ และค่าต่ำกว่า 1000 → ปฏิเสธ
- `"1000.000000000000000001"` → รับและ round-trip ตรงทุกหลัก
- `"1001.25"` → รอบแรกทุนและยอด `"1001.25"`; ledger external capital หนึ่งรายการ
- reset ทุน `"2500.125"` เมื่อหลักฐานปลอดภัย → ยอดรอบใหม่ `"2500.125"`
  ไม่ใช่ `"3501.375"`; รอบแรกและทุนเดิมยังเท่าเดิมทุกช่อง
- `"99999999999999999999.999999999999999999"` → รับตาม Money storage boundary;
  `"100000000000000000000"` → ปฏิเสธ ไม่มีเพดานธุรกิจใหม่
- ค่าที่มีเศษเกิน storage scale จริง, NaN/Infinity, bool/null, JSON number และ extra
  fields → ปฏิเสธ; trailing zeros ที่ Money ยอมรับต้องไม่ถูก validator ใหม่ปฏิเสธเอง
- ทดสอบภายใต้ Decimal ambient context ที่ถูกรบกวนให้ผลเหมือนเดิม
- Hypothesis: canonical parse/serialize/DB round-trip คงค่า; fold ledger ไม่ขึ้นกับ
  input ordering; retry จำนวนใดก็ไม่เพิ่มแถวเงิน; sequence หลาย reset รักษา history
  และยอด active เท่าทุนของรอบนั้นเท่านั้น ใช้จำนวนเงินจากข้อความ ไม่ใช้ float generator
- ไม่จำลอง debit/trade/PnL เป็นข้อมูล production เพื่อให้มีตัวอย่างผลกำไร
  การตรวจ PnL จริงยังเป็น F-14; F-13 พิสูจน์ capital classification และขอบเขตรอบ

## Transactions, races และ recovery

ใช้ PostgreSQL จริง บทบาท runtime จริงและอย่างน้อยสอง connection
ใช้ barriers คุมจังหวะ race ไม่อาศัย sleep ให้ชนกันโดยบังเอิญ:

1. CREATE ต่าง key ของ owner เดียวกัน: หนึ่ง wallet/active episode/ทุนสำเร็จ,
   คำขอที่เหลือ rejected และ audit ตามผลจริง; หลาย user ไม่ติดสิทธิ์ข้ามกัน
2. key เดียวกัน payload เดียวกันระหว่าง API requests/worker processes:
   response terminal เดียวและไม่มี audit สำเร็จซ้ำ; key เดิม payload ต่างไม่แก้คำขอเดิม
   และ repeated conflict เดิมมี admission result/rejection audit เพียงชุดเดียว
3. reset ต่าง key + expected episode เดียวกัน: ไม่สามารถชนะต่อกันสองรอบ
   reset จาก stale tab ต้อง EPISODE_CONFLICT และไม่มี closure/ทุนใหม่
4. activity writer แข่ง reset, authoritative check error/missing/stale และ order ที่กำลัง
   pending/unknown: ต้องพิสูจน์ single-writer protocol ตามคำตอบ NC-F13-02 ก่อนรับรอง
5. kill/fault หลังแต่ละ INSERT, หลังย้าย pointer, ก่อน/หลัง audit และก่อน commit:
   pre-commit rollback ทั้งชุด; post-commit lost response replay ของเดิม
6. audit write ล้ม: ไม่มี terminal result/ทุนสำเร็จ; rejection audit ต้องไม่หายจาก
   exception ที่ rollback transaction; DB ไม่พร้อมไม่อ้างว่าบันทึก audit สำเร็จ
7. engine restart และ duplicate scan ของสอง worker: คำขอที่รับไว้ต้องกลับมาประมวลผลได้
   โดยไม่มีเงินซ้ำ; cancel/timeout คืน connection/lock และคำขอเดิมยัง recover ได้
   ทดสอบ known infrastructure failure ตาม backoff 1s/5s/30s/5m, claim หมดอายุ,
   unknown exception และแถวล้มซ้ำควบคู่แถวปกติหลาย user; แถวปกติต้องไม่ starvation
8. snapshot readers แข่ง reset แบบคุมจังหวะ: episode/ทุน/ยอด/revision/เวลา snapshot
   ต้องสอดคล้องกัน และ result replay ไม่ถูกแทนด้วย snapshot ของรอบใหม่
9. migration upgrade บนฐานที่มี user/audit/F-08 data; runtime grants และ append-only
   ตรงทุกตาราง รวม api_throttle CHECK/bucket ใหม่; downgrade เมื่อมี F-13 data ต้องปฏิเสธ
   โดยไม่ลบประวัติ

## Admission rejection และ rate limit

- authenticated request ที่มี action/idempotency key ถูกต้องแต่ทุน `<= 1000`, Money parse
  ไม่ผ่าน หรือ key เดิมกับ payload ต่างกัน ต้องได้ fixed error, admission result และ
  rejection audit ใน transaction เดียว; retry/parallel retry เดิมไม่เพิ่ม result/audit
- audit failure ต้อง rollback admission result ด้วย ส่วน infrastructure failure ต้องไม่ถูกบันทึก
  เป็น domain rejection และ retry ด้วย key เดิมยังดำเนินต่อได้
- 401/403, malformed body/header และ 429 ไม่สร้าง immutable financial audit/command/result;
  error response ห้ามสะท้อน body/header และ throttle ต้องจำกัดการยิงซ้ำจริง
- PAPER_WALLET_MUTATION ใช้ถังเดียวต่อ user ทั้ง CREATE/RESET/conflict: capacity 3,
  refill 20 นาที; เปลี่ยน action/key ไม่ได้โควตาใหม่ exact replay ภายใต้ admission lock
  ไม่กิน token เพิ่ม และ concurrent exact replay ไม่หักซ้ำเพราะ race
- request ใหม่ทุกผลลัพธ์ใช้ token รวม domain rejection; หมดโควตาคืน 429 และ client
  ไม่ auto-retry ทดสอบว่าการปฏิเสธ/exception ไม่ rollback ตัวนับ และผู้ใช้อื่นแยกถัง

## Automated Paper isolation gate

เพิ่ม gate ครอบ core/infra/API/worker ของ Paper พร้อม negative fixtures:
ห้าม direct/transitive venue factory, credential decrypt/read และ external HTTP/WS/socket
ใน path ที่รับผิดชอบ Paper ไม่อ้างว่า import-linter ทั่วไปพิสูจน์ข้อห้ามนี้ครบแล้ว
fixture ที่ alias import หรือเรียกผ่าน helper ต้องถูกจับด้วย

dynamic integration ใช้ real PostgreSQL แต่ติด tripwire ที่ credential access และ
venue/external-client entrypoints ทดสอบ create/read/replay/reject/reset/restart
ต้องไม่มี tripwire ถูกเรียก ไม่ห้าม DB socket ที่จำเป็นต่อ persistence
เริ่ม isolated Paper worker โดยไม่มี venue sealing key ได้ ไม่เริ่ม key verifier เพื่อทดสอบ Paper
ไม่มี automated validation ที่ส่ง Live order หรือเรียก Binance จริง

## ตรวจด้วยมือและ browser

1. บัญชี Paper ไม่มี API key/TOTP เปิด panel ได้ เห็น PAPER ชัดและยังไม่มี wallet
2. กรอก 1000 ถูกปฏิเสธ; กรอก exact decimal ที่มากกว่า 1000 ผ่าน
   ระหว่างรอ worker เห็น pending; หลัง commit/reload เห็นทุน ยอด รหัสรอบและเวลาเริ่มตรง DB
3. ตัดการตอบกลับหลังส่งคำขอ แล้ว retry ด้วย key เดิม: ไม่เกิดทุน/กระเป๋าซ้ำ
   ไม่กิน mutation token เพิ่มเมื่อ server รับคำขอเดิมไว้แล้ว
4. เมื่อ reset unavailable เห็นเหตุผลและกดไม่ได้; server ต้องปฏิเสธเช่นกันแม้เรียกเอง
   reset success ตรวจหลัง NC-F13-02 ปิด โดยใช้แหล่งจริงพร้อมดูประวัติจาก DB
5. ข้อมูลเก่า/refetch error ต้องเห็น snapshot time และคำเตือน ไม่แสดง 0 หรือยอดใหม่เอง
6. logout/login อีกบัญชีขณะ mutation/poll ค้าง: ไม่มีเงินหรือข้อความสำเร็จของ user เดิมหลุดมา
7. ตรวจ keyboard, labels/error association, modal focus/escape/focus return,
   light/dark และ mobile/desktop; เทียบ template default/hover/focus/disabled/error/loading
   รวม computed styles เมื่อ assertion ทั่วไปแยกสี/border/focus ring ไม่ได้
8. ตรวจ TH/EN exact amount ไม่สูญเสียทศนิยม และเวลาไทยแปลงเฉพาะการแสดงผล

## ด่านที่ต้องเขียวและหลักฐาน

**ระหว่างพัฒนา:** ก่อนเลือก tests ประเมิน diff/callers/contracts/DB/concurrency/เงิน
แล้วรัน targeted domain/property/roles/audit/API/worker/UI/E2E ตามผลกระทบ
core purity, idempotency, reset safety และ money precision ห้ามเลื่อนเพราะเป็น smoke

**Candidate ก่อน merge:** จาก `backend/` รัน `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest`
พร้อม PostgreSQL/Redis/config/bootstrap ตาม CI; จาก `frontend/` รัน `npm run lint`,
`npm run typecheck`, `npm run test`, `npm run build`, `npm run test:e2e`
regenerate `backend/openapi.json` ด้วย `python -m tiewtrade.services.api.openapi_export`
และ `npm run gen:api` แล้วตรวจไม่มี contract drift
required CI รวม backend/frontend/api-contract/E2E/container ต้องเขียวบน final commit
ไม่ใช้ local tests แทน CI และไม่ commit/push/merge เอง

**Release checkpoint:** แผน F-13 นี้ยังไม่เพิ่ม benchmark ชุดยาวหรือเกณฑ์ throughput
ที่ requirements ไม่ได้กำหนด; concurrency/recovery tests ข้างต้นยังบังคับก่อน merge
หากพบความเสี่ยงที่ต้องเพิ่ม full workload/resource ให้เสนอ workload/threshold/duration
และขออนุมัติก่อน แล้วติดตาม `Pending Full Validation` ใน validation/roadmap
ไม่อ้าง smoke แทน full และไม่เปลี่ยนผล Failed/Partial เดิมของ feature อื่น

บันทึกคำสั่ง, runtime/environment, revision+uncommitted diff, เวลา, ผลจริงและ V ที่ครอบคลุม
ใน checkpoint เดิม อัปเดต Not Run เป็น Passed เฉพาะเมื่อหลักฐานครบสำหรับ candidate
สุดท้าย; รีวิว diff กับ dependencies เน้น Critical/High แล้วแก้และตรวจเฉพาะผลกระทบใหม่
การส่งเอกสารชุดนี้ไม่ได้รัน tests หรือยืนยันว่า feature ใช้งานได้แล้ว

## Development checkpoint — 2026-10-15

สถานะรวม: **Partial / Pending Full Validation** — create/read และ reset fail-closed เป็น baseline; F-15 M4 เพิ่ม real-source reset success แล้ว แต่ยังไม่ใช่ candidate ก่อน merge และยังไม่ปิด F-13

- ผ่าน targeted backend 42 tests: Money boundary/precision, PostgreSQL RLS และ owner isolation, composite ownership FK, append-only ledger, concurrent idempotent admission, audited rejection, API → durable command → worker → ledger/snapshot, rate limit, route policy, secret canary และ Paper isolation gate
- ผ่าน frontend full suite 242 tests, ESLint, TypeScript และ production build; ครอบ exact amount, initial-load error, retry ด้วย key/payload เดิม และ identity switch ที่ทิ้ง late response ของ user เดิม
- ผ่าน `ruff check`, `ruff format --check`, mypy 389 files และ import-linter 7 contracts; OpenAPI กับ generated TypeScript ถูกสร้างใหม่และ contract gate ผ่าน
- migration ฉบับสุดท้ายผ่าน `0030 → 0031 → 0030 → 0031` บนฐานใหม่ และยืนยัน FK `(source_command_id,user_id)`; ฐานทดสอบชั่วคราวถูกลบแล้ว
- full backend suite บน Windows ยังไม่ผ่านเพราะ test harness เดิมผูก `.venv/bin`, อ่าน UTF-8 ด้วย locale cp1252 และ venue fixture patch `socket` จน Windows asyncio สร้าง loop ไม่ได้; regression จริงจาก route ใหม่หนึ่งจุดถูกแก้และ test เฉพาะผ่านแล้ว ผลนี้ไม่ใช้แทน required CI บน Linux
- บันทึกนี้เป็นหลักฐานเดิมก่อน F-15 M4; หลักฐานใหม่ปิด RESET write/audit fault matrix,
  reset/reset serialization, pending/open activity และ reset-success browser flow แล้ว ส่วน unknown commit,
  worker cancellation/timeout และ controlled activity/GET writer barriers ยังเป็น `Pending Full Validation`
- รอบแก้ deep-review วันที่ 2026-10-15 ปิด findings เรื่อง rejection rollback,
  canonical idempotency, uncertain UI retry/status polling, snapshot integrity,
  Paper dependency gate และ API-pool contention; targeted Paper unit/gate/API/PG/
  route classification รวม 44 tests ผ่าน และ migration ใหม่บนฐานเปล่ายืนยันว่า API
  อ่าน episode closure ได้
- frontend ฉบับหลังแก้ผ่าน ESLint, TypeScript, production build และ full suite 244 tests;
  full run ครั้งแรกมี AccountNavigation timing failure 2 รายการที่ไม่เกี่ยวกับ diff จากนั้น
  focused 4 tests และ full rerun 244 tests ผ่านโดยไม่แก้ navigation code
- backend ฉบับหลังแก้ผ่าน `ruff check`, `ruff format --check`, mypy 392 files,
  import-linter 7 contracts และ `git diff --check`; broad relevant run ผ่าน 28 tests
  แต่ secret-canary หนึ่ง parameter ยังล้มเพราะ Redis admission ติดต่อไม่ได้และคืน
  `INDICATOR_ADMISSION_UNAVAILABLE` แทน fixture expectation `INDICATOR_DATA_NOT_READY`
  จึงยังไม่ถือว่า full validation/required CI ผ่าน
- รอบ refactor วันที่ 2026-10-15 ตัด exception/re-export/ค่าจาก SQL ที่ไม่ได้ใช้,
  รวม dependency error และรหัส reset ที่ซ้ำ โดยไม่เปลี่ยน contract หรือ business logic;
  Paper core/isolation/API transaction/PostgreSQL integration ผ่าน, frontend full suite
  244 tests ผ่าน พร้อม ESLint, TypeScript, production build, ruff, mypy 392 files,
  import-linter 7 contracts และ `git diff --check`
- Candidate backend Linux รอบวันที่ 2026-10-15 ใช้ Python 3.12, PostgreSQL 16 และ
  Redis 7 บนฐานใหม่: full suite ผ่าน 2,745 tests, skipped 1 และ deselected 2 ใน
  9:19 นาที หลังแก้ให้ F-13 downgrade guard อ่านข้อมูลใต้ RLS ได้จริง, รักษา audit
  history ด้วย old constraints แบบ `NOT VALID` และให้ destructive migration tests
  รันก่อน immutable integration fixtures; ruff, mypy 393 files, import-linter 7
  contracts และ `git diff --check` ผ่าน ข้อ 1 ของ candidate validation จึงผ่าน
- Candidate browser E2E รอบวันที่ 2026-10-15 ใช้ PostgreSQL 16 และ Redis 7 บนฐานใหม่:
  Playwright full suite ผ่าน 18 tests ใน 2.0 นาที; flow ใหม่ยืนยัน browser → API →
  durable command → real Paper worker → PostgreSQL → UI, ปฏิเสธทุนต่ำกว่า minimum,
  รักษาจำนวน `1500.000000000000000001` ตรงทุกหลัก, แสดง pending/disabled reset และ
  คงผลหลัง reload โดยไม่ต้องมี API key หรือ TOTP; focused rerun หลังปรับ screenshot
  helper ผ่าน 1 test ใน 6.7 วินาที ตรวจภาพ desktop 1440 px และ mobile 360 px แล้ว
  พร้อมผ่าน ESLint และ TypeScript
- Recovery/concurrency checkpoint วันที่ 2026-10-15 ใช้ PostgreSQL 16 ฐานใหม่และ
  Redis 7: เพิ่ม real-DB integration 15 tests ครอบ fault หลัง admission/dispatch และ
  CREATE ทุก financial write รวม audit, rollback ไม่มีข้อมูลครึ่งชุดแล้ว retry เดิม recover,
  restart ก่อน process พร้อม claim expiry, duplicate scan หลัง commit, backoff
  `1s/5s/30s/5m` ที่เพดาน 5 นาที, unknown failure ไม่ทำให้ผู้ใช้อื่น starvation,
  CREATE ต่าง key ด้วย worker สองตัว และ snapshot pointer race ด้วย barrier; snapshot
  เป็น old หรือ new episode ที่ครบชุดและ terminal result เดิมไม่ถูกแทน ผล targeted
  Paper storage/recovery/API transaction/routes รวม 27 tests ผ่าน; focused final 15 tests
  ผ่าน พร้อม ruff, format, mypy 394 files, import-linter 7 contracts และ
  `git diff --check`; F-15 M4 ภายหลังเพิ่ม reset success และ write/audit rollback-retry ส่วน
  controlled activity writer, cancellation/timeout และ unknown commit ยังคง pending ตามขอบเขตข้างต้น
- Contract regeneration checkpoint วันที่ 2026-10-15: export `backend/openapi.json`
  จากแอปและสร้าง `frontend/src/api-types.ts` ด้วย openapi-typescript 7.13.0 ใหม่แล้ว;
  SHA-256 ก่อน/หลัง generation ตรงกันทั้งสองไฟล์ จึงไม่มี generated contract drift
  จาก source ปัจจุบัน; frontend API contract gate ผ่าน 2 tests และ TypeScript ผ่าน
- Final local candidate checkpoint วันที่ 2026-10-15 หลังแก้ snapshot result และ test
  isolation: backend full suite บน Linux/Python 3.12/PostgreSQL 16/Redis 7 ฐานใหม่ผ่าน
  2,760 tests, skipped 1 และ deselected 2 ใน 9:27 นาที; backend ผ่าน ruff check,
  ruff format, mypy 394 files และ import-linter 7 contracts. Frontend ผ่าน ESLint,
  TypeScript, full Vitest 244 tests, production build และ Playwright E2E 18 tests ใน
  1.8 นาที. OpenAPI/TypeScript generation มี SHA-256 ตรงกันก่อนและหลัง regeneration,
  `git diff --check` ผ่าน และ Compose rebuild/health พร้อม host HTTP smoke ผ่านทั้ง API
  และ frontend; hosted required CI บน final commit ยังรอ commit/push ตามกฎ Git จึงไม่ใช้
  local checkpoint นี้แทนผล CI

## Post-merge checkpoint — 2026-10-16

- [PR #14](https://github.com/yukasung/tiewtrade/pull/14) merge เข้า `main` ที่ `2243675`
  หลัง candidate สุดท้ายผ่าน review และ validation ในหัวข้อก่อนหน้า
- Required push CI [run 38769152865](https://github.com/yukasung/tiewtrade/actions/runs/38769152865),
  PR CI [run 38773429163](https://github.com/yukasung/tiewtrade/actions/runs/38773429163) และ
  post-merge CI [run 38775780115](https://github.com/yukasung/tiewtrade/actions/runs/38775780115)
  ผ่านครบ; post-merge container job ผ่านเมื่อ rerun หลัง transient startup race โดยไม่มีการแก้ code
- V-15 จึงผ่านสำหรับ source ที่ merge แล้ว แต่สถานะรวมยังเป็น **Partial / Pending Full Validation**;
  F-15 M4 ภายหลังเพิ่ม authoritative reset success และ rollback-retry แล้ว ขณะที่ controlled
  activity-writer/GET races, worker cancellation/timeout, unknown commit และ integration candidate
  ยังไม่มีหลักฐานครบ
- F-13 จึงคง **In Progress** และยังไม่ใช่ Development Complete หรือ Completed
