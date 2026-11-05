# F-17 — Implementation checkpoint 2026-11-04

สถานะ: ผ่าน deep review, runtime fixes และ owner-approved refactor; validation ยัง Partial ไม่พร้อม merge
Candidate: uncommitted worktree บน `feature/f-17-tp-sl`
Base HEAD: `6545b4ba8182dc4b4010357f8d06470f65b58cb4`
ผล local ด้านล่างไม่ใช่ required CI และไม่ใช่ผลบน committed final SHA

## ขอบเขต implementation

- `core/protections.py`: Money/Quantity, pair-bound last-trade evidence, equality/gap trigger,
  single winner, bracket own-entry cap, revision replacement/cancel, terminal zero allocation,
  explicit selected allocation release แบบ A และ initial + 3 retry decisions
- migration `0063_protections.py`: additive owner RLS requests/results/groups/history/exit links,
  immutable events/audit, engine-only projections, read-only scanner, reset readiness และ
  protocol/writer guard; disabled โดยปริยาย; downgrade ได้เฉพาะ protocol ปิด/ไม่มี F-17 data ตาม amendment ที่อนุมัติ 2026-11-05
- `infra/protections/{codec,storage,worker}.py`: durable intake/replay, wallet/episode locks,
  allocation/reservation integration, setup deadlines, feed cursor, trigger/exit identity,
  correction conflict และ explicit repair; terminal MARKET residual ไม่ auto-retry
- F-15/F-16 integration: bracket intent/fingerprint, fill checkpoint, net base fee allocation,
  selected manual SELL release เมื่อ admission สำเร็จเท่านั้น, correction และ server availability
- engine protection round ค้นงานแม้ไม่มี ordinary active order; owner-scoped processing,
  bounded timeouts และ fair due ordering; state ที่ต้องคงอยู่เก็บ PostgreSQL
- API: strict Paper-only intake, auth/CSRF/throttle route registration, key/status/discovery,
  owner/episode keyset pagination, entry/exit linkage และ authoritative exit status/quantity
- frontend: optional BUY TP/SL, manual SELL allocation แบบ A พร้อมคำเตือน,
  protection create/replace/cancel/status, server discovery + same-key unknown recovery,
  generated types, shared admin-template controls และ snapshot summaries รวม attachments

ไม่เปิด Live หรือ bot runtime; bot/notification/Live integration คง Pending Dependency
ไม่มีการ commit/push/merge และไม่แตะ default development database ที่มีข้อมูลเดิม

## Environment และคำสั่ง

macOS, Python 3.12 `.venv`, local Docker PostgreSQL/Redis, real runtime roles/RLS;
ฐานข้อมูลแยก `tiewtrade_e2e_f17` schema0064 ที่สร้างเพื่องานนี้ ไม่ใช่ production
Browser harness guard บังคับชื่อ DB `tiewtrade_e2e*` และ localhost ก่อนเริ่มงาน
E2E ใช้ recorded market feed, real API/DB/F-15 writer และ test AllowPolicy;
จึงไม่ใช่หลักฐานว่า production risk/stop policy integration ผ่าน
Sealing keys ใช้ ephemeral test keys; ไม่มี Live orders/venue credentials

จาก backend/ โดยตั้ง role URLs ให้ชี้ฐานข้อมูลแยกดังกล่าว:

- `pytest tests/core/test_protections.py tests/infra/protections tests/api/test_protection_routes.py tests/api/test_manual_order_routes.py -o addopts= -q`: **79 passed**, 18.75s
  (54 domain + 8 PostgreSQL protection + 2 protection HTTP + 15 existing manual HTTP)
- targeted exit variants หลังเพิ่ม scanner/race/public exit-link assertions และ protection HTTP:
  `pytest tests/infra/protections/test_lifecycle.py::test_price_trigger_exit_replay_and_exact_financial_effects tests/api/test_protection_routes.py -o addopts= -q`: **4 passed**, 4.76s
- existing regressions `core/{test_paper_matching,test_risk_matching,test_position_parity}.py` ผ่าน
  ในรอบ targeted; `api/{test_route_policy,test_route_classification,test_manual_order_routes}.py`,
  `infra/manual_orders/test_requests.py`, `infra/execution_market/test_initialization.py`: **68 passed**
  หลังเพิ่ม deliberate mutation route expectations
- Ruff check/format ผ่าน 28 changed/new Python files; mypy ผ่าน 27 files
- import-linter: **7 contracts kept / 0 broken**
- OpenAPI export + `npm run gen:api` ผ่าน; TypeScript typecheck และ scoped ESLint ผ่าน
- frontend targeted Vitest **32 tests / 5 files passed**; หลังเพิ่ม receipt summary ตรวจ
  affected subset **27 tests / 3 files passed**
- frontend production build ผ่าน; warning bundle >500kB ยังมีอยู่ ไม่ใช่ acceptance performance proof

## PostgreSQL / browser facts ที่พิสูจน์แล้ว

1. BUY100 USDT → gross1 BTC, fee0.001 BTC → protection0.999 BTC โดยใช้ F14/F15 facts
2. SELL0.4 → fill0.1 → cancel0.3: protection0.599 / available unprotected0.3;
   ไม่คืน protection ให้อัตโนมัติหลัง accepted SELL ตาม NC-F17-07 แบบ A
3. SELL ที่ rejected admission ไม่ลด allocation/revision เดิม
4. concurrent same-key intake/application ให้ receipt/result/revision เดียว;
   concurrent trigger connections ให้ immutable exit เดียว
5. durable protection scanner trigger หลัง entry FILLED; real MARKET exit fill0.999 ที่99
   คืน wallet9998.802099 USDT หลัง quote fee0.098901; ไม่มี PnL credit ซ้ำ
6. MARKET partial exit0.1 คง FAILED residual0.899; replay ไม่สร้าง exit เพิ่ม
7. setup retry deadlines1/2/4s อยู่ DB; reload session ก่อน due ไม่ใช้ attempt;
   ครบ4 known attempts คง FAILED0.999 และไม่มี manual auto-close
8. fault ก่อน immutable creation event rollback group/history/result; retry สร้างเพียงครั้งเดียว
   ข้อนี้เป็น request atomicity ไม่ใช่หลักฐาน fill financial checkpoint fault ครบ V-05
9. API role แก้ protection projection ไม่ได้, engine ลบ history ไม่ได้, ownerอื่นอ่านไม่พบ
10. Playwright `--config=playwright.protections.config.ts`: bracket→fill→ARMED→reload→replace→cancel ผ่าน;
    receipt lost after commit→reload→same-key discovery→APPLIED ผ่านแยก targeted run
    (ไม่อ้าง aggregate final run ทั้ง2 tests หลังทุก patch)
    Desktop/mobile PNGs ใน `evidence/ui/` ตรวจด้วยตาแล้ว; ไม่มี Live mutations

## ความครอบคลุมและงานค้าง

| Validation | สถานะและขอบเขตที่เหลือ |
|---|---|
| V-01–04 | Passed local targeted: core59, real bracket after-crossing2, standalone multiple groups/new entry/overlap1 และ partial→exit browser proof ผ่าน; ใช้ late-fill/residual/precision evidence เดิมร่วมกัน |
| V-05 | Passed local targeted: bracket/exit financial kill ก่อน/หลัง commit และ takeover ผ่าน รวม audit/เงิน/position/allocation/link conservation |
| V-06 | Passed local targeted: เจ้าของเลือก A 2026-11-05; entry fill/cancel, TP/SL, opposing mutations และ competing allocations ผ่านสองลำดับ commit; ใช้ actual dispatcher skip-busy และ durable deadline |
| V-07 | Passed local targeted scanner→trigger→real exit; ต้องยืนยันบน final candidate/CI |
| V-08 | Passed local controlled: real serve loop + PostgreSQL, stale/gap/generation fence และ fresh recovery ผ่าน; processing upper bound0.270230s/0.175432s; ไม่ใช่ stress/workload acceptance |
| V-09 | Passed local targeted: persisted retries, browser receipt recovery, process kill/takeover และ real COMMIT ACK loss ที่ trigger/exit ผ่าน; known permanent failure ไม่ยิงซ้ำ |
| V-10 | Passed local targeted: late entry/cancel, residual/no retry, correction/replay และ REPLACE/VOID ขณะ exit unknown → rejection proof → explicit repair/cancel ผ่าน; ไม่เกิด SELL fill เพิ่ม |
| V-11 | Passed local targeted: loss/user/platform stop + inactive catalog คง protection และปิดผ่าน TransactionalRiskPolicy; platform opening ถูกปฏิเสธจริง; ไม่อ้าง bot runtime หรือ E2E AllowPolicy ว่าเป็น production gate proof |
| V-12 | Passed local targeted: RLS/grants/restart/reset races + immutable scope UPDATE denied, mode CHECK/owner RLS/episode FK INSERT และ real HTTP scope404 ผ่าน |
| V-13 | Passed local targeted: API matrix6 + manual attachment fingerprint2 ผ่าน; canonical retry/key conflict/stale revision/throttle/keyset recovery และ monetary non-mutation; generated contract evidence เดิมยัง valid |
| V-14–15 | Passed local targeted: component27/browser6 ผ่านครบ partial→trigger→entry cancel→exit, two-group selected sale→cancel, failure/receipt loss/reload, Thai/English keyboard/focus/mobile/light/dark/Live no mutation |
| V-16 | Passed local targeted: populated upgrade/default-off/no-backfill/writer guards, empty rollback สองรอบ และ refusal16กรณีผ่าน; financial/history/RLS คงเดิม |
| V-17 | Partial: migration guards/static/core/API/DB/UI/browser local targeted ผ่าน; full mypy642/import contracts7 ผ่าน; build/generated contracts เดิมยัง valid; final review finding เรื่อง CI composition ปิดแล้ว; final committed candidate/required remote CI ค้าง |
| V-18 | Not Run — Pending Full Validation (Batch) |
| V-19–20 | Not Run — Pending Dependency / Full Validation (Release) |

Requirements มี implementation สำหรับ Paper TP/SL/bracket/manual selected release,
precision/scope/idempotency/durable worker/recovery; รายการที่ยัง Partial ด้านบนเป็นช่องว่าง
หลักฐานที่ห้ามใช้คำว่า Passed/Completed หรือพร้อม merge มาปิดแทน
Bot/notification/Live runtime acceptance ไม่อยู่ในผล local นี้

## จุดที่ reviewer ควรเน้น

financial checkpoint และ allocation ต้อง commit เดียวกัน; correction ขณะ exit unknown;
late entry fill เทียบ residual; oversell ภายใต้ competing workers; actual safety gates;
protocol guard/mixed deployment/reset proof; และ UI ไม่แสดง coverage เกินจริง

เจ้าของอนุมัติ refactor 2026-11-04 และทำ targeted/system validation รอบนี้แล้วตามผลด้านล่าง
ขั้นถัดไปของ feature: ปิดรายการ Feature ที่ยัง Partial/Not Run ข้างต้นต่อได้ตาม authorization
เดิม โดยไม่ขออนุมัติ validation ซ้ำ; Batch/Release คงตาม checkpoint เดิม
ก่อน merge ต้องผ่าน Feature gates และ required CI ทั้งหมด; ยังไม่มีอนุญาต Git operations

## Review fixes — 2026-11-04

เจ้าของสั่งแก้ findings หลัง deep review; requirements/plan เดิมยังเป็น source of truth

- R1: fold effective SELL facts กลับเข้า exit progress/disposed/remaining รวม CLOSED groups;
  corrected residual กลับ FAILED/conflicted ไม่สร้าง MARKET ใหม่เอง และไม่ queue late-entry
  exit ขณะ conflict; explicit repair/cancel ล้างเฉพาะ unsent late-entry work
- R2: replace ตรวจราคา/quantity/market constraints ก่อน atomic install เป็น ARMED;
  permanent failure คง revision เดิม; transient source failure คงคำขอ PENDING และ protection
  เดิมไว้ระหว่าง initial+3 attempts/deadline1/2/4s ใช้ core decide_setup_result เดิม
- migration0064 เพิ่ม request progress projection ใต้ owner RLS สำหรับ attempt/due time;
  engine เขียนได้เฉพาะ progress, scanner อ่าน request identity/due เท่านั้น ไม่มี process cache
  และ reset proof เดิมยังนับคำขอ unresolved; additive upgrade0063→0064 ผ่านบน DB แยก
- R3: allocation conflict คืน wallet/holdings/allocation ตามจริง แต่ available เป็น null,
  admission_ready=false และ source_availability=UNKNOWN; ไม่ clamp ยอดเป็นศูนย์เพื่อแสดง ready
  เปิด repair UI ได้หลัง reload; ปรับ OpenAPI/generated TypeScript ให้ตรง nullable contract
- R4: capability หายระหว่างกรอก BUY TP/SL คง draft/ช่องกรอกและบล็อก submit พร้อมข้อความ;
  ส่ง ordinary BUY ได้เมื่อผู้ใช้ลบราคาเองเท่านั้น หรือส่ง bracket เดิมหลัง capability กลับมา
- R5: เพิ่ม financial process kill ก่อน/หลัง commit, takeover, mutation races สองทิศทาง,
  correction/reload/repair, replacement retry และ actual-role grants; ยังไม่ปิด finding นี้
  เป็นทั้งหมด เพราะ Feature matrices/required CI ที่ระบุข้างบนยังค้าง

หลักฐานรอบนี้:

- F17 core + PostgreSQL protection + protection/manual HTTP: **90 passed**, 31.51s
- หลังเพิ่ม loss-latched production-risk exit และ migration progress isolation:
  targeted exit variants + progress grants + migration single-head: **4 passed**, 4.91s
- frontend ManualOrderForm/PaperTradePage: **27 passed** รวม capability loss/recovery และ
  conflict reload→repair submission; nullable OpenAPI export/generated types ผ่าน
- หลัง patch สุดท้ายที่ล้าง unsent late-entry work เมื่อ explicit repair/cancel:
  `pytest tests/infra/protections -o addopts= -q`: **20 passed**, 24.69s;
  frontend affected2 files **27 passed**, 1.84s
- scoped Ruff ผ่าน, format **12 files** ผ่าน, mypy **7 source files** ผ่าน,
  TypeScript/scoped ESLint และ `git diff --check` ผ่านบน candidate รอบแก้ล่าสุด
  ไม่รัน full regression หรือส่ง Live order

ผลเดิมที่ไม่ถูกแก้ยังใช้ต่อได้; ไม่ใช้ผล local แทน required CI และยังไม่พร้อม merge

## Owner-approved refactor — 2026-11-04

ขอบเขตเฉพาะโค้ดในรอบแก้ findings ล่าสุด; ไม่แก้กฎเงิน, allocation, trigger, retry,
revision, transactions, schema0064 หรือ API contract

- รวม duplicated read_latest_book + validate_setup เป็น `_validate_market_setup`
  ใน `infra/protections/worker.py`; initial setup และ atomic replacement ใช้เส้นทางเดียวกัน
- รวม duplicated execution-link query/filter เป็น `_effective_order_executions`;
  ยังคงใช้ F-14 effective facts และคำนวณ BUY net/SELL gross ด้วยกฎเดิม
- เปลี่ยนชื่อ `active` เป็น `tracked_groups` เพราะรวม CLOSED และตั้งชื่อ
  `exit_quantity_delta` ให้ชัดว่าเป็นผลต่างจาก correction
- `ManualOrderForm` แยก hasProtectionPrices/showProtectionFields ใช้ร่วมกับ guard
  เพื่อคง draft และการบล็อก submit ตาม behavior เดิม โดยไม่เพิ่ม component/abstraction ใหม่
- ตรวจส่วนล่าสุดที่เหลือ (migration0064, storage include_closed, nullable balances,
  request scheduling, generated contract และ regression tests) แล้ว คงโครงสร้างที่มีอยู่

ผลบน candidate หลัง refactor:

- `pytest tests/infra/protections tests/core/test_protections.py -o addopts= -q`:
  **74 passed**, 28.22s รวมเงินจริง, correction/replay/repair, kill ก่อน/หลัง commit,
  actual RLS/grants, retries และ races ทั้งสองทิศทาง
- Vitest ManualOrderForm/PaperTradePage: **27 passed**, 3.29s
- Ruff check/format ผ่าน; mypy protection worker ผ่าน; TypeScript และ scoped ESLint ผ่าน
- ต่อ system validation ตาม V-14/15 ทันที: Playwright protection2 cases **2 passed**,
  19.4s บน PostgreSQL schema0064/real API/worker/browser; assertions/screenshot flow เดิม
- browser รอบแรก **2 failed** ที่ signup เพราะ invocation ขาด environment สำหรับ local test;
  เพิ่ม TIEWTRADE_SIGNUP_OPEN=1 และ TIEWTRADE_COOKIE_SECURE=0 เฉพาะ process ทดสอบ
  แล้วทั้งสองกรณีผ่านด้วยโค้ดเดิม ไม่เปลี่ยน production defaults

ผลนี้ปิด refactor checkpoint เท่านั้น ไม่ใช้แทน V-05/06/08/09/10/11/12/16 matrices
ที่ยังเหลือ, required CI หรือ Batch/Release และไม่มี commit/push/merge

## Feature validation continuation — 2026-11-04

เจ้าของสั่งเริ่มปิด Feature validation หลัง refactor; รอบนี้เพิ่มเฉพาะ tests/หลักฐาน
ไม่แก้ runtime/business policy และไม่มี Live orders/commit/push/merge

ใช้ `tests/infra/protections/test_validation.py` ประกอบ helpers เดิม:
F-15 process-kill child/COMMIT-ACK proxy, F-18 serialize barrier ที่ตรวจ pg_blocking_pids,
F-17 buy/execute/transfer และ PostgreSQL runtime roles จริง ไม่เพิ่ม infrastructure
เก็บข้อมูลทดสอบใน DB แยก `tiewtrade_e2e_f17_validation` schema0064;
upgrade และ global platform stop ใช้ DB แยก `_upgrade`/`_platform` เพื่อไม่ปะปนกับกรณีอื่น

หลักฐาน:

- [feature-validation.xml](feature-validation.xml): **14 passed / 2 deselected**, 16.47s
  โดย 2 cases ที่ไม่รันคือ late-entry/cancel ที่พักหลัง 3 รอบ ไม่ใช่ Passed/Skipped acceptance
- [exit-atomicity-validation.xml](exit-atomicity-validation.xml): **2 passed**, 4.54s
  หลังเพิ่ม assertion audit FILL ก่อน/หลัง commit; BUY และ exit SELL ไม่เกิด financial effect ซ้ำ
- [commit-ack-validation.xml](commit-ack-validation.xml): **2 passed**, 3.30s
  PostgreSQL proxy ตัดเฉพาะ COMMIT reply หลัง server commit จริง ทั้ง trigger และ exit fill;
  reload พบ identity/result เดิม, old claim ถูก fence และไม่มี exit/trade ซ้ำ
- [serve-sla-validation.xml](serve-sla-validation.xml): **2 passed**, 3.50s
  รัน production `paper_order_main.serve()` ต่อเนื่องก่อน publish fresh observation;
  วัดหลัง owner/episode lock และอ่านราคาจริงสำเร็จ เป็น upper bound ของ processing start
  (0.270230s / 0.175432s) ใช้ producer timestamp ก่อน commit จึงรวม publication delay ด้วย
  ไม่ใช้ enqueue time และไม่ปรับ SLA/freshness thresholds; stale/disconnected/old generation
  ไม่ trigger, fresh gap-through trigger ครั้งเดียว, gap-back ไม่ใช้ข้อมูลย้อนหลังเดา trigger
- [upgrade-validation.json](upgrade-validation.json): archive source HEAD6545b4b ที่ยังไม่มี F-17
  มาสร้างจริงบน schema0062: BUY filled1 gross/net0.999 + LIMIT active0.5 ที่90;
  upgrade0064 คง balance9900, holdings0.999, reservation45 และ statuses เดิม,
  protection0/default-off; เปิด protocol แล้ว old writer ถูกปฏิเสธ; downgrade0064 ถูกกัน
  Initial probe assertion เปรียบเทียบ numeric text `45.000...` กับ `45` ไม่ผ่าน;
  ตรวจซ้ำด้วย Money equality บนข้อมูลเดิม ไม่แก้ financial rows
- [platform-stop-validation.json](platform-stop-validation.json): DB แยกเจ้าของทดสอบหนึ่งคน,
  membership fixture ตาม F38/F19 เดิม, ใช้ API stop + real engine/discovery;
  manual opening ใหม่ถูกปฏิเสธ แต่ protection คง ARMED และ exit ผ่าน TransactionalRiskPolicy
  จน CLOSED/balance9998.802099; ไม่ล้าง global stop ของฐานข้อมูลอื่น

การทดลอง late-entry/cancel หยุดหลัง 3 รอบตาม AGENTS.md:

1. fixture ใช้ input ID ที่ publish แล้วซ้ำ (ExecutionInputGapError)
2. หลังแก้ cursor ยังไม่ได้สร้าง LIMIT resting queue ด้วย post-eligibility book จึงไม่มี fill
3. หลังเพิ่ม book เรียก claim ก่อน durable next_attempt_at จึงได้ claim=None

ทั้งสามรอบยังไม่ถึง assertion late-fill/cancel ของธุรกิจ จึงไม่สรุปว่า runtime มีบั๊กหรือผ่าน
ยังไม่รันรอบที่4 ไม่ disable/xfail tests และไม่เปลี่ยน deadline เพื่อให้ผลผ่าน
ส่งตัวเลือกให้เจ้าของแล้ว: A วิเคราะห์ claim/deadline และปรับ fixture เดิม (แนะนำ),
B ประกอบจาก partial-fill fixture F-15 ที่มีอยู่พร้อมตรวจ scenario parity
เกณฑ์ V-06/V-10 พักรอคำตอบนี้; Feature ยังไม่พร้อม merge และ required CI ยังไม่มีผล

## Option A — owner-approved continuation 2026-11-05

เจ้าของเลือก A ให้ตรวจ claim/deadline และแก้ fixture เดิมก่อนทดลองต่อ
บันทึกความล้มเหลว3รอบด้านบนคงไว้เป็นประวัติ ไม่ใช่สถานะปัจจุบัน

- ยืนยัน `claim_order` ตรวจ next_attempt_at และมี live claim ได้หนึ่งรายการต่อ owner
  เดิม fixture เรียกก่อน due และพยายาม pre-claim fill/cancel พร้อมกัน จึงไม่ตรง F-15
- เพิ่ม fixture-local due hint ที่อ่าน DB clock/deadline แล้วรอโดยไม่ถือ owner transaction
  ใช้ pattern เดิมจาก F-15 `test_worker.py`; ไม่แก้ deadline/lease/backoff ใน DB
- Race ใช้ worker แรก stage financial changes แล้วถือ transaction ที่ barrier; worker ที่สอง
  ใช้ dispatcher จริงและได้ busy-owner/None; หลัง first commit อ่าน due/state ใหม่
  แล้วรับงานต่อ หรือยืนยัน TERMINAL เมื่อ cancel ชนะ ไม่ pre-claim สองงานต่อ owner
- [late-entry-validation.xml](late-entry-validation.xml): **2 passed**, 6.34s
  fill-first มี net1.998 และ exits2 ใบ ใบละ0.999 หลังรู้ผลใบเดิมเท่านั้น;
  cancel-first มี net0.999 และ exit1 ใบ; หลังปิด holdings0 และ balances ตาม exact Money
- เพิ่ม correction REPLACE/VOID ของ entry ระหว่าง exit PENDING: คง quantity/conflict
  ไม่ยอม premature cancel/repair; financial writer พิสูจน์ REJECTED จริงก่อน explicit
  revision-checked repair/cancel; correction replay ไม่เปลี่ยน revision/สร้าง SELL fill
- รวม single RECORD-fill lookup ของ fixtures เป็น `test_lifecycle.single_fill` ใช้ร่วมกัน
  แทน duplicated execution-link/codec SQL ของ correction tests
- [unknown-exit-correction-validation.xml](unknown-exit-correction-validation.xml):
  **3 passed**, 3.80s (2 unknown-exit correction + existing entry repair regression)
- [opposite-trigger-validation.xml](opposite-trigger-validation.xml): **2 passed**, 2.65s
  last-trade TP→SL และ SL→TP ผ่าน real connections/pg_blocking_pids barriers มี winner/exit เดียว
- [option-a-regressions.xml](option-a-regressions.xml): **39 passed / 2 deselected**, 46.56s
  ครบ PostgreSQL protection suite ยกเว้น serve SLA2 cases ที่ runtime/dependencies ไม่ถูกแก้
  ใช้หลักฐานเดิมต่อ; single-fill helper exit correction regressions รวมอยู่ใน39 testsนี้
- Ruff check/format และ git diff --check ผ่าน; ไม่แก้ runtime/business policy หรือใช้ Live

V-06/V-10 ผ่าน local targeted แล้ว; เกณฑ์ scope/API/UI ที่ยัง Partial และ required CI
ยังต้องตรวจต่อก่อน merge ไม่ถือว่า option A ทำให้ feature Completed

## Additional scope validation and migration blocker — 2026-11-05

- [projection-scope-validation.xml](projection-scope-validation.xml): **3 passed**, 3.53s
  UPDATE owner/mode/episode ถูก column grants ปฏิเสธ; INSERT ทดสอบ mode CHECK23514,
  owner RLS42501 และ episode composite FK23503 แยกจาก UPDATE grants/deferred history FK
  ทุก attempt rollback แล้ว projection เดิมไม่เปลี่ยน อีก owner อ่านไม่พบ
  รอบแรกคาด CHECK/FK จาก UPDATE แต่ถูก column grants ปฏิเสธก่อน จึงแยก proof ของ INSERT
- [http-scope-validation.xml](http-scope-validation.xml): **1 passed**, 2.06s
  HTTP sessions จริงสองเจ้าของใน TestClient lifespan เดียวตาม cookies_now/use_cookies เดิม;
  request/by-key ของอีก owner404, discovery/list ไม่รั่ว, cancel/replace ของอีก ownerกับ
  random target ได้404เหมือนกัน และ owned groupกับwrong episode404/revisionไม่เปลี่ยน
- ตรวจ CI contract เดิมบน DB ว่างแยก `tiewtrade_e2e_f17_migration_ci` schema0064
  ไม่มี protection history และไม่แตะ default/validation/history databases
- [migration-ci-preflight.xml](migration-ci-preflight.xml): **1 failed**, 0.74s
  `tests/infra/db/test_migrations.py::test_downgrade_then_upgrade_rebuilds_the_same_structure`
  ล้มที่ `alembic downgrade base` เพราะ0064 downgrade raise RuntimeError ทุกกรณี
  และ0063มีนโยบายเดียวกัน เป็น local reproduction ของ test ที่อยู่ใน required CI
  ไม่ใช่ผล remote CI; ยังไม่แก้ migration หรือ skip/ลดเกณฑ์ test

ประเด็นตัดสินใจ: F-03 validation V-32/V-33 ตรวจ empty downgrade/upgrade roundtrip;
F-17 migration implementation ประกาศ forward-only ทุกกรณี แม้ไม่มีประวัติ
Database standard ยอมให้ย้อนกลับไม่ได้เมื่อมีเหตุผลชัดเจน แต่สอง contract นี้ยังไม่สอดคล้อง
จึงหยุดก่อนเปลี่ยนแนวทาง migration ตามกฎ AGENTS.md เรื่อง code/spec conflict

แนวทางแนะนำเพื่อขอคำตัดสิน: ให้0063/0064 downgrade ได้เฉพาะ protocol ปิดและไม่มี F-17
requests/attachments/protections/progress/history/audit; ใช้ locking/owner visibility guards
ตาม pattern0061เดิม ปฏิเสธเมื่อมีข้อมูลและ rollback คง RLS/history ทั้งหมด
แล้วตรวจ empty down/up ซ้ำสองรอบ + populated-history refusal บน PostgreSQL จริง
นี่เป็นข้อเสนอ ยังไม่ใช่การแก้ migration ที่ได้รับอนุมัติ

Option A ของ late-fill ปิดแล้ว ไม่มี runtime/business changes ในรอบนี้
V-16/V-17 ยังมี blocker ข้างต้น; V-01–04/V-13–15 ที่คง Partial ยังไม่ถือว่าผ่านทั้งหมด
และไม่มี commit/push/merge หรือ Live trading


## Approved empty-only rollback implementation — 2026-11-05

เจ้าของอนุมัติข้อเสนอ migration ข้างต้นแล้ว ก่อนแก้โค้ดได้บันทึก amendment ใน plan.md
ผล Failed local preflight ด้านบนเป็นประวัติเดิม; blocker นั้นแก้แล้วตามหลักฐานต่อไปนี้

- migrations0063/0064 ใช้ ACCESS EXCLUSIVE locks ก่อนตรวจ protocol และทุกแหล่งข้อมูล
  F-17 รวม manual attachments/audit; migration-owner visibility เห็นทุก owner;
  เมื่อปฏิเสธ transaction rollback คืน RLS/DDL ทั้งหมด ไม่แก้ financial runtime policy
- เมื่อว่างจริง0063 คืน shared reset/audit contracts และถอด schema ตาม dependency order;
  0064 ถอดเฉพาะ durable retry projection ที่ว่าง ภายใต้ guard เดียวกัน
- [migration-roundtrip-validation.xml](migration-roundtrip-validation.xml): **1 passed**, 12.16s;
  F-03 test เดิม head→base→head สองรอบ ได้ schema snapshot เดิมทุกครั้ง
- [migration-contract-validation.xml](migration-contract-validation.xml): **7 passed**, 43.56s;
  F-03 migration module ทั้งชุด รวม empty roundtrip สองรอบ, older shared audit/reset
  contracts และ populated-history refusal เดิม ผ่านบน dedicated DB ที่รื้อสร้างได้
- [migration-history-guards.xml](migration-history-guards.xml): **16 passed**, 6.852s;
  ทดสอบ0063/0064กับ protocol enabled, request, retry progress, canceled history,
  bracket attachment, selected allocations, protection audit และ actual filled Paper BUY;
  ใช้ current-user context คนอื่นขณะ downgrade เพื่อพิสูจน์ all-owner visibility;
  เทียบ row hashes และ FORCE RLS ก่อน/หลัง rejection รวม actual cash9900USDT,
  held0.999BTC/reserved0 โดยไม่ลบประวัติหรือเปลี่ยนยอด
- เพิ่ม CI isolated-migration step ตาม reset pattern เดิม เพื่อให้16 guards ใช้ DB ว่างแยก
  และไม่ถูก normal pytest marker exclusion ข้าม; remote CI ยัง Not Run
- สองรอบแรกของ guard fixture ล้มจาก deferred trigger events/payload identity และ
  UUID bind type ตามลำดับ; แก้ fixture ให้ flush deferred constraints และผูก typed UUID
  ให้ตรง DB contract; ไม่ลด guard/เกณฑ์ตรวจรับ รอบที่สามผ่านครบ16
- ruff check/format ของ migrations และ protection infra/API tests ผ่าน;
  **full backend mypy: 642 files passed** (รวมsrc/tests); แก้ type annotations ใน
  F-17 tests ให้ตรง existing typed helpers โดยไม่เปลี่ยน trading behavior

V-16 ผ่าน local targeted; V-17 ยัง Partial เพราะ required CI/final candidate ยังไม่ผ่าน
V-01–04/V-13–15 ยัง Partial และ Batch/Release ยัง Pending Full Validation
ขั้นถัดไป: ปิด Feature validation matrices ที่ค้างได้ต่อทันทีในขอบเขตที่อนุมัติ;
commit/push/PR/merge ต้องรอคำสั่ง Git จากเจ้าของ


## Remaining Feature matrix closure — 2026-11-05

Candidate: worktree บน feature/f-17-tp-sl, base HEAD เดิม ไม่ได้ commit/push/merge
เพิ่มเฉพาะ F-17 tests/test-only HTTP composition และ validation docs; ไม่มี production
trading logic, migration หรือ financial policy เปลี่ยนในรอบนี้

### API/core/database

- [api-matrix-validation.xml](api-matrix-validation.xml): **6 passed**; authenticated
  HTTP create/replace/cancel, numeric canonicalization, same-key changed prices/quantity/
  revision conflict, APPLIED retry และ new-key stale-revision worker rejection;
  balance9900/held0.999/reserved0 คงเดิม ไม่มี duplicate mutation;
  shared throttle429 ไม่สร้าง inbox row และ lookup/keyset pagination ยังอ่านครบ20ไม่มีซ้ำ
- [api-attachment-validation.xml](api-attachment-validation.xml): **2 passed**;
  manual bracket TP/SL และ selected allocations identity/revision/quantity อยู่ใน
  canonical fingerprint; equivalent string amounts replay request เดิม, เปลี่ยน/ลบ
  attachment ได้409 ไม่มีคำขอใหม่หรือการลด protection ก่อน financial writer
- [core-parity-validation.xml](core-parity-validation.xml): **59 passed**;
  เพิ่ม full replace→selected sale และ cancel/trigger branches สำหรับ Paper/Live;
  normalize เฉพาะ mode แล้ว identities/revisions/quantities/trigger evidence เท่ากัน;
  crossed/equal standalone levels ปฏิเสธ4กรณี ร่วมกับ golden/property/quantum เดิม
- [standalone-groups-validation.xml](standalone-groups-validation.xml): **1 passed**;
  standalone0.4 ไม่ขยายเมื่อ BUY ใหม่เพิ่ม net0.999, held1.998; เพิ่มอีกชุด0.6
  แล้ว available0.998; ขอชุด1เพิ่มถูกปฏิเสธโดยไม่เปลี่ยนสองชุดเดิม
- [bracket-crossing-validation.xml](bracket-crossing-validation.xml): **2 passed**;
  ราคา last trade ข้าม110/90 ก่อนรับรู้ entry fill; net0.999 ได้ trigger ตามขาที่ตรง
  ไม่ใช้ standalone creation validation ปฏิเสธย้อนหลัง; process ซ้ำไม่เพิ่ม exit;
  cash9900 หลัง BUY ยังไม่ถือว่า SELL สำเร็จ

### UI and real browser

- [ui-state-validation.xml](ui-state-validation.xml): **27 passed**;
  เพิ่ม WAITING_ENTRY/ARMING/feed-unavailable ARMED/EXITING/FAILED residual snapshots;
  protected0, ไม่แสดง CLOSED, EXITING แก้/ยกเลิก protection ไม่ได้;
  แสดง actual pending/expired exit และ remaining quantity ตาม server contract
- [browser-matrix-validation.xml](browser-matrix-validation.xml): **6 passed**, 45.7s
  บน real PostgreSQL + API + F-16 bridge + F-15 writer, one browser worker;
  test-only AllowPolicy ใช้เหมือน F-16 เดิม ไม่แทน production risk evidence V-11
  1. bracket fill→reload→replace→cancel
  2. response lost หลัง commit→reload→same original key/request→APPLIED โดย POSTเดียว
  3. ไทย/อังกฤษ keyboard initial quantity focus, Shift+Tab/Tab trap, Escape/return focus;
     desktop1440/mobile375 light/dark ไม่มี horizontal page overflow;
     Live ไม่แสดง protection panel/ไม่ส่ง order/protection mutation
  4. prior BUY1000 ได้ net9.99 unprotected; bracket LIMIT11 partial fill10 @100 ได้
     net9.99 protected, อีก1entryถูก cancel หลัง trigger; MARKET exit ใช้ recorded
     bids2 @99 +7.99 @1 (ไม่รับประกัน trigger price), gross205.99/fee0.20599;
     final cash8205.78401, held9.99เดิม/reserved0, exits1/triggers1/RECORD fills4;
     CLOSED เฉพาะชุดที่ออกครบ, replay ไม่เพิ่มเงิน/fill/audit
  5. standalone0.4+0.3, SELL0.5 ใช้ free0.299 กับ explicit selections0.1+0.101;
     canceled sale คง held0.999/protection0.499/available0.5/reserved0/cash9900;
     มีคำเตือนแบบ A ก่อนส่ง ไม่คืน protection อัตโนมัติ
  6. standalone quantity2 มากกว่า held0.999: HTTP202→worker REJECTED→UI alert;
     reload แสดงไม่มี TP/SL, cash9900/held0.999/available0.999 และไม่มี SELL order
- ตรวจ PNG `ui/paper-en-keyboard-dialog.png`, `ui/paper-en-dark-375.png` ด้วยตา:
  shared modal/input/button/focus และ protection card แสดงผลอ่านได้;
  chart ใน test composition ยัง disabled ตาม baseline ไม่ใช่หลักฐาน chart acceptance

### Failures resolved and checks

- Browser keyboard3รอบแรกหยุดตาม AGENTS: missing test keys, signup flag, แล้ว fixture
  คาด close button ภายใน dialog; เจ้าของเลือก A ให้เทสต์ตรง shared Modal เดิม
  หลังแก้ focus expectation ผ่าน ไม่แก้ production Modal
- New partial-entry browser fixture รอบแรกใช้ selectOption กับ Tabs จึงแก้ตาม F-16
  test เดิม; รอบถัดไป expected proceeds ผิดเพราะสมมติ bidทั้งหมด99 แต่ recorded book
  มี2 @99 แล้ว @1; คำนวณ golden traceจากfixtureจริงและรอบที่สามผ่าน
  ไม่เปลี่ยน matching/fee/trigger policy หรือเพิ่ม liquidity เพื่อให้เทสต์ผ่าน
- Standalone DB fixture เดิมเทียบ ARMING กับ ARMED จึงประมวลผล setup ให้ครบก่อน
  snapshot; crossing fixture input cursor เดิมอ้าง leaseก่อน initial publication
  จึงแก้เป็น book.input_id+1; ไม่ลด generation/cursor fences
- ruff check/format สำหรับ changed Python tests ผ่าน; **mypy642 files passed**;
  **import-linter7 contracts kept**; scoped frontend ESLint และ TypeScript check ผ่าน
- Build/generated API evidence เดิมยัง valid เพราะ production contracts/source ไม่เปลี่ยน
  ไม่รัน full regression/Batch/Release ซ้ำในรอบ test-only changes นี้

V-01–V-16 ผ่าน local targeted; V-17 ยัง Partial รอ final committed candidate/review gate
และ required CI; Batch/Release ยัง Pending Full Validation/Dependency
ขั้นถัดไปคือ owner สั่ง Git commit/push/เปิด PR แล้วติดตาม required CI บน SHA ล่าสุด;
ยังห้าม merge จน Feature/review/CI gates ผ่านและเจ้าของสั่ง merge


## Final review CI composition finding resolved — 2026-11-05

Final review ของ migration/latest tests พบ High1: default Playwright config เลือก F-17
แต่เริ่ม production API8000 ขณะที่ spec ต้องการ test-only composition18017;
local suite ที่ใช้ dedicated config ผ่านไม่ได้พิสูจน์ required CI wiring

แก้ในขอบเขต F-17 เท่านั้น:
- `frontend/playwright.config.ts`: เพิ่ม protections.spec.ts ใน testIgnore เช่น dedicated suites เดิม
- `frontend/package.json`: เพิ่ม test:e2e:protections เรียก dedicated config ที่มีอยู่
- `.github/workflows/ci.yml`: เพิ่ม F-17 Paper protection E2E หลัง F-16 ก่อน reset ของ F-18/F-19;
  ใช้ job environment/DB/roles เดิม ไม่เพิ่ม infrastructure หรือเปลี่ยน production trading logic

หลักฐานหลังแก้:
- [ci-protection-selection.json](ci-protection-selection.json): npm run test:e2e -- --list
  เลือก F-17 **0 tests**; npm run test:e2e:protections -- --list เลือกครบ **6 tests**
- [ci-protection-composition.xml](ci-protection-composition.xml): npm run test:e2e:protections
  -- --reporter=line,junit **6 passed**, 58.2s บน local isolated Paper DB;
  CI=1, chart flags enabled และ catalog generation ตาม CI; ใช้ loopback test services/
  fixture keys ไม่ใช่ remote CI หรือการตรวจรับระบบ chart/Redis เต็มรูปแบบ
- scoped config ESLint + frontend TypeScript ผ่าน, workflow YAML parse ผ่านและมี
  F-17 npm step เดียว; git diff --check ผ่าน
- ตรวจ final diff: default composition ไม่เก็บ F-17 ซ้ำ, dedicated port/app ตรง tests,
  F-18/F-19 ยังคง clean reset เดิมหลังจบ F-17; ไม่พบ blocker เพิ่มในขอบเขต finding นี้

High CI composition finding ปิดแล้ว; ไม่เริ่ม refactor รอบใหม่เพราะการแก้เฉพาะ wiring
ใช้ pattern เดิมและ owner-approved refactor ของ feature เสร็จแล้ว
V-17 ยังคง Partial รอ final committed SHA/required remote CI; ไม่ commit/push/PR/merge
ขั้นถัดไป: รอเจ้าของสั่ง commit/push/เปิด PR แล้วติดตาม required CI บน SHA ล่าสุดจนจบ
Batch/Release และ pending dependencies คงตามเดิม ไม่ถือว่า feature Completed


## Publication checkpoint — 2026-11-05

เจ้าของสั่งเริ่ม commit/push/เปิด PR และติดตาม required CI แล้ว หลังปิด final review finding
จัด branch ต่อ origin/main c8d8ca7 ซึ่งมี tree ตรงกับฐาน6545b4bเดิม (F-19 squash merge);
ไม่มี production content เปลี่ยนจากการจัด ancestry จึงใช้ local evidence เดิมที่ยัง valid
commit เฉพาะ F-17 ไม่รวม AGENTS.md, standards/testing.md, CI-feedback feature หรือ
validation-artifacts ที่เป็นงานนอกขอบเขต; V-17 รอ required CI บน candidate SHA จริง
ผล CI ที่เกิดหลังเปิด PR จะรายงานพร้อม SHA/run URL ไม่สร้างเอกสาร commit วนเพื่อบันทึกผล
ยังไม่อนุญาต merge และไม่ถือว่า Batch/Release/dependencies ผ่าน


## Required CI first candidate failure and test integration repair — 2026-11-05

PR [#46](https://github.com/yukasung/tiewtrade/pull/46), candidate6998c22d5af552ab84f64932177c4be84ca249f7:
- [push CI](https://github.com/yukasung/tiewtrade/actions/runs/42037924735), backend:
  **24 failed, 4263 passed, 47 deselected**, 993.08s
- [PR CI](https://github.com/yukasung/tiewtrade/actions/runs/42037960302), backend:
  **24 failed, 4263 passed, 47 deselected**, 1067.95s
- ทั้งสอง runs ผ่าน5jobsอื่น รวม browser/dedicated F-17; isolated backend steps ยังไม่ถึง
  เพราะ main pytest ล้ม ไม่ถือว่าทั้ง CI ผ่าน

Root causes and repair (tests only; no production financial/scheduling behavior change):
1. API secret canary ไม่มี F-17 UUID substitution/required query arguments และ404 contract;
   เพิ่ม complete route inputs และ PROTECTION_NOT_FOUND โดยยังตรวจทุก response ห้าม secret รั่ว
2. Paper isolation gate ยังไม่รู้จัก modules ของ F-17; เพิ่ม core/infra/API protection roots
   และ exact reviewed internal dependencies รวม audit.events; FORBIDDEN imports/markers
   กับ alias/transitive helper rejection tests คงเดิม ไม่อนุญาต Live/network dependency
3. Production-loop unit doubles ยังไม่รองรับ protection phase; เพิ่ม mock และตรวจลำดับ
   protection→manual→matching กับ dispose ตาม interfaceจริง โดยไม่แก้ runtime
4. F-17 trigger fixtures ทิ้ง PENDING entry CANCEL20เจ้าของ (รวม pending NEW13commands)
   ทำให้ bounded20 global due scanner ไม่เห็น owners ใน F-18 scheduler tests ถัดไป;
   source-resumption รันแยกผ่าน แต่รันหลัง F-17 ล้ม19กรณีตาม
   [reproduction](ci-scheduler-reproduction.xml) (**19 failed, 53 passed**, 71.06s)
   เพิ่ม owner-scoped teardown ของ mutable dispatch ใน F-17 conftest ตาม pattern
   tests/infra/risk_limits/test_same_pair_dispatch.py; ไม่ลบ ledger/order/audit facts,
   ไม่คืน reservations, ไม่เพิ่ม scanner limit หรือเปลี่ยน production scheduling rules

หลักฐานหลังแก้:
- [contract regressions](ci-contract-regressions.xml): **7 passed**, 12.35s;
  ครอบ secret canary, isolation positive/negative gate และ loop doubles
- [scheduler regressions](ci-scheduler-regressions.xml): **74 passed**, 74.54s;
  F-17 infra suite (ยกเว้น unchanged feed SLA และ isolated guards) → same-pair runtime
  ทั้งr9/r10 → source-resumptionทั้งmodule บน real PostgreSQL DB ใหม่ที่แยกจาก development
- local canary รอบแรก Redisไม่ทำงาน จึงได้ INDICATOR_ADMISSION_UNAVAILABLE ของ baseline;
  เปิด test Redis container ที่มีอยู่แล้วและใช้ URLของมัน ไม่ลด expected security contract
- [migration guard regressions](ci-migration-guard-regressions.xml): **16 passed**, 7.55s;
  ตรวจ fixture teardown ใหม่กับ isolated rollback guards บน freshly migrated DB
- ruff/format ของ changed tests และ full backend mypy642 files ผ่าน

จะ push repair commit และติดตาม required CI บน SHA ใหม่จนจบ;
V-17 ยังคง Partial (first candidate CI Failed) pending final candidate CI ไม่ใช้ผล targeted แทน CI
ไม่มี merge, ไม่มี Live order; ไฟล์นอกงานยังอยู่นอก commit


## Second CI candidate: remaining scheduler fixture leak — 2026-11-05

Candidate385bce83dda4bcd277ee9cdd3b15df65a04b9413:
- [push CI](https://github.com/yukasung/tiewtrade/actions/runs/42042134191):
  **20 failed, 4267 passed, 47 deselected**, 783.66s
- [PR CI](https://github.com/yukasung/tiewtrade/actions/runs/42042143130):
  **20 failed, 4267 passed, 47 deselected**, 1069.77s
- Secret canary, Paper isolation and loop doubles ที่แก้ผ่านแล้ว; failures ที่เหลือคือ
  same-pair r9 และ source-resumption19; อีก5jobsผ่าน รวม browserทั้งหมด

Owner teardown รอบก่อนแก้ orphan CANCEL ของ F-17เอง แต่ยังไม่ครอบ fixture setup
ที่เรียก run_manual_order_round แบบ global: helper transfer() ของ F-17 seed entry
และรับคำขอค้างของเจ้าของอื่นจาก API fixtures มาด้วย เป็นสาเหตุที่ sequence local74
ซึ่งเริ่มจากDBใหม่โดยไม่มี API inbox backlog ยังไม่เทียบเท่าบริบท CI ทั้ง suite

- [cross-owner reproduction](ci-cross-owner-fixture-reproduction.xml): **1 failed**;
  สร้าง foreign owner/request pending จริง, เรียก seedของownerอีกคน แล้วพบ foreign
  requestถูกTRANSFERRED (count1 แทน0) โดยไม่ได้เป็นงานที่ fixtureนี้ต้องการประมวลผล
- เปลี่ยนเฉพาะ transfer helper ให้ใช้ DueRequest/claim_request/real request worker
  เจาะrequestของfixture ตาม pattern tests/api/test_manual_order_routes.py;
  ไม่แก้ production global scanner, limits, scheduling, fees หรือ trading policy
- [cross-owner regression](ci-cross-owner-fixture-regression.xml): **1 passed**,
  requestของforeignownerยังไม่มีresult/financialcommand; fixtureownerได้net fillปกติ
- [expanded regression](ci-expanded-fixture-regressions.xml): **111 passed**, 91.21s;
  API manual orders → API protections → real manual bridge → F-17 infra → same-pair
  r9/r10 → source-resumptionทั้งmodule; เพิ่มบริบทAPI/inboxก่อนschedulerที่ชุด74เดิมขาด
- [real serve SLA](ci-owned-seed-sla.xml): **2 passed**, 4.23s; ตรวจ controlled <=1s
  processing-start และ stale/gap recovery หลังเปลี่ยนhelper; ไม่ใช่ workload SLA
- [isolated guards](ci-owned-seed-migration-guards.xml): **16 passed**, 6.70s;
  ตรวจ helperเปลี่ยนกับ populated preservation/rollback guards บน freshly migrated DB
- ruff/format และ full backend mypy642 files ผ่าน; diffเปลี่ยนเฉพาะtest helper/regression
  กับเอกสาร ไม่ใช้ผลlocalเหล่านี้แทน required CI ของcandidateถัดไป

จะติดตาม required CI บน SHA ใหม่ต่อ; หากการแก้และตรวจเกณฑ์เดิมยังไม่ผ่านครบ3รอบ
ให้หยุดเสนอทางเลือกตาม AGENTS.md ก่อนทดลองรอบถัดไป; ยังไม่มี merge/Live orders


## Owner-approved read-only CI diagnostic — 2026-11-05

Third candidate888cdffc485aeb9707e508e493966cb5415e6fcb:
- [push CI](https://github.com/yukasung/tiewtrade/actions/runs/42046195862):
  **20 failed, 4268 passed, 47 deselected**, 1091.08s
- [PR CI](https://github.com/yukasung/tiewtrade/actions/runs/42046541839):
  **20 failed, 4268 passed, 47 deselected**, 1084.84s
- Same-pair r9 และ source-resumption19 ยังล้ม; อีก5jobsผ่านรวม browserทั้งหมด
  Local111ยังไม่เทียบเท่าบริบท full CI จึงยังห้ามถือว่า cause ถูกปิดหรือพร้อม merge

หยุดตามกฎ3รอบ แล้วเจ้าของเลือก A อย่าง explicit: เพิ่ม diagnostic แบบอ่านอย่างเดียว
ก่อนจุดที่ล้มเพื่อดู queue owners, candidate ranking และ source freshness โดยคงทุกเกณฑ์

Implementationเฉพาะtests:
- `tests/infra/risk_limits/scheduler_diagnostics.py` ใช้ existing ENGINE_SCAN role
  ซึ่งเขียนไม่ได้และอ่าน secret/order payload/balance ไม่ได้; SELECTเฉพาะ scheduling
  columns ที่มีสิทธิ์อยู่แล้ว, own rows10, queue sample25, actual bounded candidates20,
  queue counts และ BTC book/price/feed timestamps/generations/readiness
- เรียกเฉพาะหลังพบ missing hint ใน same-pair/source-resumption helpers;
  log marker `F17_SCHEDULER_DIAGNOSTIC` ผ่าน loggerเดิมของpytest captured logs
- ไม่เปลี่ยน selector, limit, due, retry, protocol หรือ original assertions;
  ถ้า diagnostic ล้ม logเฉพาะ exception type แล้วปล่อย original test failure ต่อ
- [fresh validation](ci-diagnostic-fresh-validation.xml): **31 passed**, 15.40s;
  real scanner role อ่านsnapshotได้/dispatch rowsไม่เปลี่ยน และ error-detail redactionผ่าน
- [populated local reproduction](ci-diagnostic-populated-reproduction.xml): **22 failed,
  9 passed** บน DBที่มีประวัติจากก่อนหน้า; รวม2expected migration guard refusals
  เนื่องจากเลือกฐานไม่ว่าง และ20missing hints; เป็น historical diagnostic context
  ไม่ใช่ acceptance run หรือเหตุให้ลด migration guard
- [local bounded sample](ci-diagnostic-local-sample.json): อ่านจาก retained test queue
  ผ่าน read-only scanner, actual candidates20; หลัง local real-serve runs พบ pending
  CANCEL14ownersมีprotection และNEW22commands/21ownersมีprotection; ยังต้องใช้
  snapshotก่อนfailureจริงของ CIระบุบริบท ไม่สรุปว่า owner cleanup/seed fixes ปิดปัญหาแล้ว
- ruff/format ผ่าน; full backend mypy **643 files** ผ่านหลังเพิ่ม diagnostic helper

Owner-approved diagnostic CI runถัดไปมีจุดประสงค์เก็บevidenceจากfull-suite context;
required CIยังFailedจนแก้สาเหตุและcandidateจริงผ่าน ไม่มี mergeหรือLive order

## Owner-approved CI database isolation — 2026-11-05

Diagnostic SHA `2407df2b66e7cf43385a69fe42542c2180da6ef9` finished:
- [push CI](https://github.com/yukasung/tiewtrade/actions/runs/42051567850):
  **20 failed, 4270 passed, 47 deselected**, 735.27s
- [PR CI](https://github.com/yukasung/tiewtrade/actions/runs/42051582552):
  **20 failed, 4270 passed, 47 deselected**, 881.01s; other five jobs passed in both runs
- [diagnostic summary and source snapshot](ci-scheduler-diagnostic-summary.json):
  20 snapshots per run, every actual batch contained20 foreign-owner candidates and
  excluded the test owner. Inspected source-resumption snapshot had fresh READY
  book/price/feed evidence; 23/25 sampled queue rows had protection-owner history.
  This establishes queue interference, not a complete proof of which prior test
  produced each command. Global protection/serve tests can process retained owners.

Owner explicitly chose A: run F-17 integration on a freshly migrated CI test database.
- Only workflow composition changes: main pytest ignores `tests/infra/protections`,
  then a required step reuses `scripts/reset_ci_test_database.sh` and runs that folder.
  Existing isolated migration16 tests and all other steps retain their original commands.
  Production logic, test bodies/assertions, scanner limits and retry policy are unchanged.
- [collection equality](ci-isolation-collection.json): original4290 = main4242 +
  protection48; exact node-ID union matches, overlap0. Marker defaults unchanged.
- [isolated protection integration](ci-isolated-protection-integration.xml):
  **48 passed, 16 deselected**, 56.11s on a newly bootstrapped/migrated PostgreSQL DB;
  includes real serve/feed-gap/start<=1s and all non-isolated F-17 integration cases.
  The16 deselected rollback guards remain in their existing dedicated CI step.
- [main affected regressions](ci-isolated-main-regressions.xml): **105 passed**,57.78s
  on a separate newly migrated DB: manual/protection API, real manual bridge, complete
  same-pair dispatch and source-resumption modules, including the20 CI failures.
- Workflow actionlint and diff whitespace checks passed. No Python/TS source changed;
  previous lint/type evidence remains applicable and required CI still runs all gates.

V-17 remains Partial until required CI on the new candidate finishes. Batch/Release
remain Pending Full Validation/Dependency. No merge or Live orders authorized.
