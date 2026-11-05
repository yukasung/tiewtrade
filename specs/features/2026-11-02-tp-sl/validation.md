# F-17 — TP/SL และ Bracket — Validation

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-04; NC-F17-06 Approved 2026-11-04**
วันที่: 2026-11-04
อ้างอิง: requirements.md Approved 2026-11-04; plan.md Approved 2026-11-04

## เกณฑ์ตรวจรับ

ทุก Feature criterion ต้องผ่านบน candidate สุดท้ายก่อน merge; ไม่มีผล runtime ในรอบเอกสารนี้
Not Run ไม่ใช่ Passed และห้ามส่ง Live order ใน automated validation

| ID | เกณฑ์ / requirements | ตรวจอย่างไร | ระยะ | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | trigger last trade, equality, single/dual legs และ input validation — NC-02 | golden traces ราคาใต้/เท่า/เหนือระดับ, TP/SL ที่ข้ามแล้วตอนตั้งถูกปฏิเสธ, bracket fill ข้ามแล้วเข้าสู่ trigger; ไม่ใช้ bid/candle | Feature | Passed local targeted — core59 รวม equality/single legs/crossed setup; real DB bracket fill หลัง crossing TP/SL2กรณีผ่านและสร้าง exit เดียว; last-trade/feed proof เดิมยัง valid |
| V-02 | precision และ non-overlap — RQ-09/NC-03 | Money/Quantity property tests: allocation + ordinary reservation ไม่เกิน held; TP/SL ไม่จองสองเท่า; fee/net acquired และ minimum/step boundary ใช้กฎเดิม | Feature | Passed local targeted — allocation conservation/18-digit quantum/fee-net/minimum-step tests เดิมและ core59 ผ่าน; disjoint groups + actual partial entry/exit มี financial conservation proof; ไม่เปลี่ยนสูตรเงิน |
| V-03 | shared domain deterministic — RQ-08/10 | input/clock/identities เดียวกันได้ transition/intent เดียวกันผ่าน Paper/Live fixture; core purity/import gates; ไม่เรียกเงินจริง | Feature | Passed local targeted — Paper/Live fixtures ให้ replace/selected sale/cancel/trigger/revision/quantities/evidence ตรงกัน; import-linter7 contracts ผ่าน; ไม่มี Live execution |
| V-04 | lifecycle — NC-03/04 | multiple disjoint groups, partial entry/exit, revision replace/cancel ก่อน trigger, แก้หลัง EXITING ไม่เปลี่ยน exit, residual/dust ไม่ปัดขึ้นและไม่วน MARKET ใหม่ | Feature | Passed local targeted — multiple standalone groups/new entry ไม่ขยายชุดเดิม/over-allocation rejected ผ่าน; ใช้ partial/late entry, revision/EXITING, residual/no retry/dust proofs เดิมร่วมกับ browser partial→exit ล่าสุด |
| V-05 | fill/protection atomicity — RQ-03/10 | PostgreSQL จริง fault ก่อน/หลัง commit ของ financial checkpoint: fill/ledger/position/allocation/work/audit ไม่แยกครึ่ง; retry ไม่เพิ่ม effect | Feature | Passed local targeted — bracket และ exit kill ก่อน/หลัง commit/takeover ผ่าน รวมเงินจริง/position/allocation/audit และไม่เพิ่ม execution; ดู evidence รอบ Feature validation |
| V-06 | races และเงินไม่หาย — NC-03/04 | PostgreSQL หลาย connections/workers: trigger vs manual SELL/replace/cancel, TP vs SL, entry cancel vs fill, competing allocations; barrier จัดลำดับทั้งสองทาง ยืนยันหนึ่ง winner และ conservation | Feature | Passed local targeted — เจ้าของเลือก A 2026-11-05; แก้ fixture ตาม durable due/single-owner claim แล้ว entry fill/cancel และ TP/SL สองลำดับผ่าน; targeted protection regression39 ผ่าน; ดู evidence |
| V-07 | trigger ทำงานเมื่อไม่มี ordinary active order — NC-02/05 | real worker + DB + controlled last trade feed, มี protection อย่างเดียว; crossing สร้าง exit intent ครั้งเดียวและ F-15 จับคู่ด้วย liquidity เดิม | Feature | Passed local targeted — scanner/trigger/real exit; final CI ค้าง |
| V-08 | SLA และ feed recovery — NC-05 | วัด necessary-input-ready → processing-start <= 1s ด้วย real worker/DB ใน controlled scenario; ใช้ timestamps ของ input จริง ไม่ใช้ enqueue แทน start; stale/gap ไม่ trigger, fresh gap-through trigger, gap-back ไม่เดา OHLC | Feature | Passed local controlled — real serve loop 0.270230s/0.175432s; stale/disconnected/old generation ไม่ trigger; fresh gap-through/gap-back ถูกต้อง; ไม่ใช่ workload guarantee |
| V-09 | durable recovery/retry — RQ-04/10/11 | process restart, claim takeover, response/commit ACK หาย, DB error, duplicate source; initial + 3 retry หลัง 1/2/4s โดยทดสอบ clock และ DB due state; unknown reconcile ก่อน, permanent failure ไม่ยิงซ้ำ | Feature | Passed local targeted — persisted retries + browser receipt recovery + bracket/exit kill/takeover + real dropped COMMIT ACK ของ trigger/exit ผ่าน; ดู evidence |
| V-10 | terminal/late fill/correction — NC-04 | entry fill เพิ่มระหว่าง cancel แยกจาก terminal exit residual; ตรวจไม่มี duplicate exit/oversell; correction/replay ใช้ authoritative facts ไม่แก้ประวัติหรือปล่อย quantity เกินถือจริง | Feature | Passed local targeted — late entry/cancel สองลำดับ, residual/no retry, correction REPLACE/VOID ขณะ exit unknown → actual rejection → explicit repair/cancel และ replay ผ่าน; ไม่เพิ่ม SELL fill |
| V-11 | risk/stop/catalog — RQ-06/07 | F-18 loss latch + F-19 user/platform stop + inactive pair ยังรักษา protection และอนุญาต proven reduce-risk; ordinary opening คงถูกบล็อก; bot failure decision tests ไม่อ้าง bot runtime ผ่าน | Feature | Passed local targeted — loss/user/platform stop และ inactive catalog รักษา protection/ปิดผ่าน TransactionalRiskPolicy; platform stop ปฏิเสธ opening จริง; bot failure ใช้ domain tests เดิม ไม่อ้าง bot runtime |
| V-12 | isolation/reset/stateless — RQ-08/10 | DB RLS/grants ด้วย actual runtime roles, cross owner/mode/episode FK, GET/mutate คนอื่น 404; reset แข่ง pending protection ถูกกันตาม proof; worker/browser restart ใช้ DB ไม่พึ่ง local session/cache | Feature | Passed local targeted — RLS/grants/restart/reset races, immutable scope UPDATE denied, mode CHECK/owner RLS/episode FK INSERT และ real HTTP other-owner/missing-target/wrong-episode404 ผ่าน; revision ไม่เปลี่ยน |
| V-13 | API/idempotency — RQ-10/11/12 | API tests canonical fingerprint รวม bracket/allocations; exact retry/key conflict/stale revision; strict string amounts/CSRF/auth/throttle; status/by-key/discovery กู้ผล; OpenAPI generated contract check | Feature | Passed local targeted — HTTP matrix6 + attachment fingerprint2 ผ่าน: canonical retry, changed key payload/revision, stale worker refusal, auth/CSRF, throttle/pagination/recovery; generated contract evidence เดิมยัง valid |
| V-14 | UI truth/accessibility — RQ-11/12 | component tests + browser Paper/Live, ไทย/อังกฤษ, keyboard/focus, mobile/desktop; ARMING/partial/unprotected/feed unavailable/unknown/residual ไม่แสดง protected/closed เกินจริง; admin template state/computed style เมื่อจำเป็น | Feature | Passed local targeted — component27 และ browser6 ผ่าน; ARMING/feed unavailable/EXITING/residual/unknown/failure ไม่แสดง protected/closed เกินจริง; ไทย/อังกฤษ keyboard trap/Escape/return focus, desktop/mobile/light/dark และ Live no mutation; reused shared controls/template |
| V-15 | Paper complete flow — NC-01 | targeted browser→API→DB→worker→UI: bracket partial fill→trigger→exit, ตั้งทีหลัง→replace→ขายส่วนที่เลือก, cancel, failure/reload recovery; มี assertions เงิน/audit; Live ไม่มี mutation route ไป Paper/venue | Feature | Passed local targeted — browser6 ครอบ bracket partial→trigger→entry cancel→exact exit/cash/audit/replay, standalone replace/cancel, selected two-group SELL→cancel แบบ A, lost receipt/reload และ failure ไม่มี auto-sell; ดู evidence |
| V-16 | migration/deployment — plan DB | upgrade จาก current head + existing ordinary orders, constraints/grants/immutable history, no protection backfill; protocol disabled ก่อน compatible writer พร้อม, unsafe downgrade ไม่ลบ history | Feature | Passed local targeted — owner-approved empty-only rollback amendment 2026-11-05; F-03 migration7 tests รวม empty down/up สองรอบผ่าน, populated upgrade/default-off/no-backfill/old-writer และ rollback refusal16กรณีผ่าน พร้อมเงิน/position/history/RLS unchanged; ดู evidence |
| V-17 | affected regressions/static/CI | core matching/positions, real DB F-13–F-19 ที่กระทบ, risk/stop/catalog, API/UI; ruff/format/mypy/import-linter/frontend checks/build/generated types ที่เกี่ยวข้อง; required CI บน final SHA และ review | Feature | Partial — affected targeted backend/API/UI/browser และ static checks ผ่าน local; full backend mypy642 files + import-linter7 ผ่าน; build/generated contracts เดิมไม่ถูก runtime diff กระทบ; final review CI-composition finding ปิดแล้ว; required CI diagnostic2407df2 backend20 failed/4270 passed ทั้งpush/PR; snapshots40ชุดพบคิวforeign ownersบังtest owner; เจ้าของเลือก A ให้แยก F-17 integration ใช้ฐานว่างในCI โดยคงtests/assertions/productionเดิม; collectionครบ4290 (main4242 + F1748), local isolated F1748passed; รอ required CI บนcandidateใหม่ก่อนmerge |
| V-18 | integrated Paper acceptance | full regression/cross-feature E2E ท้ายชุดที่ 4; ใช้ profiles/thresholds ที่อนุมัติของ F-14/F-15/F-16 และหลักฐานที่ยัง valid; protection coverage เพิ่มผ่าน Feature cases ไม่แทน baseline volume/SLA | Batch | Not Run — Pending Full Validation |
| V-19 | bot/notifications integration | หลัง F-20/F-21 และช่องทางแจ้งเตือนพร้อม: bot protection failure→close intent→stop, manual failure ไม่ auto-close, ส่งทุกช่องทางที่เปิดจริง; fake/paper execution | Release | Not Run — Pending Dependency / Full Validation; ชุดที่ 9 |
| V-20 | Live readiness และระบบรวม | F-22–F-24 integration/reconciliation, venue per-pair support/protection mapping, isolation, recovery และ safety gaps ของ Live ต้องปิดตาม spec งาน Live; automated tests ใช้ fixtures/FakeVenue เท่านั้น | Release | Not Run — Pending Dependency / Full Validation; ก่อน Live/ชุดที่ 9 |

## การเลือกตรวจตามผลกระทบ

เริ่มจาก Tests เดิม ไม่สร้างสำเนา suite:

| ส่วนที่เปลี่ยน | Tests/หลักฐานเดิม และช่องว่างที่จะเพิ่ม |
|---|---|
| core/financial | `backend/tests/core/test_paper_matching.py`, `test_positions.py`, `test_position_parity.py`, `test_risk_matching.py`, `money/`; เพิ่ม protection golden/property traces V-01–04 |
| transactional execution | `backend/tests/infra/execution_market/{test_worker,test_executions,test_dispatch,test_matching_storage,test_process_recovery,test_review_regressions}.py`; เพิ่ม protection allocation/trigger fault/race tests V-05–10 |
| intake/reset/safety | `backend/tests/infra/manual_orders/`, `paper_wallet/`, `risk_limits/` และ kill-switch tests ที่ callers กระทบ; เพิ่ม RLS/reset/stop protection coverage V-11–13 |
| UI/API | `backend/tests/api/test_manual_order_routes.py`, `frontend/tests/{ManualOrderForm,PaperTradePage,PaperOrderList}.test.tsx`, `manualOrderJournal.test.ts`; เพิ่ม protection scenarios และ targeted browser V-14/15 |

ผลเก่าใช้ต่อได้เฉพาะสิ่งที่พิสูจน์ไม่ถูก diff/dependency/schema/config/harness กระทบ
การเปลี่ยน financial checkpoint/reservation เป็นส่วนกลาง: ประเมิน full regression ก่อน merge
ตาม testing §7 และต้องรันเมื่อกระทบหลายระบบหรือ targeted evidence ไม่พอ
ห้ามเลื่อน correctness/safety/concurrency ไป Batch เพื่อลดเวลา
หลัง patch รัน failed tests + affected regressions เท่านั้น ไม่รันทั้งชุดซ้ำเป็นพิธี

## ตัวเลขและ failure fixtures

- ตัวอย่าง last trade 100, TP 110, SL 90: 109.99 ไม่ trigger TP, 110 trigger;
  90 trigger SL; gaps ไป 120/80 ยัง trigger; ทุกค่ารับผ่าน Money ตามหน่วยคู่
- partial BUY gross/fee ใช้ expected net จาก fixtures F-15/F-14 เดิม ไม่คิดสูตร fee ใหม่
  ตรวจ bracket allocation โตเท่ากับสุทธิที่ได้จริง และไม่เปลี่ยน position ของกลุ่มอื่น
- หลาย protection groups + ordinary SELL ต้องรักษาผลรวมปริมาณที่ถือจริงทุก transition
- replay ทุก event/commit boundary ให้ ledger/position/audit/link ไม่เกิดซ้ำ
- permanent failure/attempt exhausted แสดงไม่มีการป้องกันสำหรับ manual และไม่ auto-close;
  bot failure ทดสอบ shared close/stop decisions โดย runtime acceptance อยู่ V-19

## ตรวจด้วยมือ

1. เข้า Paper Trade ตั้ง BUY พร้อม TP/SL แล้วตรวจสถานะก่อน fill/partial/full และ exit จริง
2. ตั้ง protection ทีหลัง แก้ราคา/จำนวน ยกเลิก และขายส่วนที่ระบุจากหลายชุด
3. จำลอง feed gap/unknown response/failure แล้ว reload: ผลและงานค้างต้องกลับจาก server
4. ตรวจภาษา, tab order/focus, error association, mobile/desktop และ template states
5. เปิด Live page: เห็นโหมด/ข้อจำกัดจริง ไม่มี Paper balances หรือ mutation ข้ามโหมด

ใช้ controlled Paper feed/fixtures เท่านั้น ไม่ใช้ Live เพื่อสร้างหลักฐาน

## Checkpoint และการบันทึกผล

เก็บหลักฐานร่วมใน `evidence/feature-candidate.md` เมื่อมีผลจริง: SHA/diff, environment,
คำสั่ง/ผล/เวลา, criteria ที่ครอบคลุม, failures และ pending dependencies; ไม่สร้างผล Passed ล่วงหน้า
targeted checks รันตาม milestone ใน plan; V-08 เป็น timed diagnostic ต้องแจ้งขอบเขต
และประมาณเวลาก่อนรัน รวม setup/teardown ไม่เพิ่ม timed smoke ทุก milestone
ก่อน full regression/cross-feature E2E/Batch แจ้งสิ่งที่จะพิสูจน์และเวลารวม; วางแผน Batch
ประมาณ 1–2 ชั่วโมงต่อรอบตาม testing §7 โดยไม่ลด duration/threshold เดิมให้พอดีเวลา
หากยังไม่ผ่านหลังแก้ 3 รอบให้หยุดและเสนอทางเลือกตาม AGENTS.md

implementation ครบให้แจ้ง Ready for Code Review และรอ `review code`
ก่อน merge: Feature ทั้งหมด, review และ required CI บน final candidate ต้องผ่าน
หลัง authorized refactor ตรวจ validation ที่ถึงกำหนดต่อ; ไม่ต้องอนุมัติซ้ำการทดสอบนั้น
ก่อน Completed/release: Batch/Release ที่เกี่ยวข้องต้องผ่านครบ; CI เขียวไม่ปิด dependencies

## NC-F17-06 — Approved integration amendment

Correction ที่ทำให้ protection allocation ไม่ปลอดภัยเข้าสู่ conflict/unavailable
ตาม requirements NC-F17-06; ผู้ใช้จัดสรรใหม่อย่าง explicit ผ่าน revision-checked
replace/cancel เดิม ไม่จัดลำดับตัดชุดเอง ไม่แตะ exit ที่ส่งแล้วโดยเดา
V-10 ต้องตรวจ conflict → authoritative reconciliation → explicit allocation repair
→ resume รวม duplicate repair, stale revision, unknown exit และหลาย instance
ก่อนเปิดรับคำสั่งที่อาศัย quantity นั้น; ห้ามแสดง protected ระหว่างยังขัดกัน

## Implementation checkpoint 2026-11-04

Implementation ครอบคลุม domain/DB/API/worker/UI ตาม plan แล้ว และพร้อมแจ้ง
Ready for Code Review โดยยังไม่พร้อม merge; มี backend79, frontend32 และ targeted
browser/static evidence ตาม [candidate evidence](evidence/feature-candidate.md)
เกณฑ์ Feature ที่ยัง Partial/Not Run ต้องตรวจต่อ ไม่เลื่อนไป Batch/Release
NC-F17-07 แบบ A มี actual partial fill/cancel และ rejected admission rollback evidence
ขั้นถัดไปหยุดรอเจ้าของสั่ง `review code` ตาม AGENTS.md; ไม่ commit/push/merge

## NC-F17-07 — Approved amendment

V-04/V-06/V-15 ต้องพิสูจน์ตัวอย่าง 1 BTC protected → accepted SELL 0.4 → fill 0.1
→ cancel 0.3: held 0.9 / protected 0.6 / available unprotected 0.3
รวม accepted→cancel แบบไม่ fill, partial→expired, rejected admission rollback,
exact retry ไม่ลด protection ซ้ำ และส่วนที่ไม่ได้เลือกยังมีการป้องกัน
UI ต้องแจ้งแบบ A ก่อนส่งและใช้ authoritative terminal facts หลังส่ง

## Feature validation matrix update — 2026-11-05

V-01–V-16 ผ่าน local targeted ตาม [evidence ล่าสุด](evidence/feature-candidate.md)
รอบนี้เพิ่มเฉพาะ tests/test-only composition และเอกสาร ไม่เปลี่ยน production trading logic
เจ้าของอนุมัติแบบ A ของ keyboard fixture หลัง3รอบตามกฎ: ใช้ Modal เดิม focus ช่องจำนวน,
Tab trap/Escape/return focus; ไม่เปลี่ยน shared Modal หรือเพิ่ม UI pattern
V-17 ยัง Partial: ไม่มี final committed candidate/required CI และยังไม่อนุญาต merge
Batch/Release ยังคง Not Run — Pending Full Validation/Dependency ตามตาราง
ขั้นถัดไป: owner สั่ง commit/push/เปิด PR แล้วติดตาม required CI บน SHA ล่าสุด;
review gate/final Feature evidence ต้องผ่านก่อนขอ merge ไม่ใช้ local results แทน CI

## Final review finding closure — 2026-11-05

แก้ High CI composition finding แล้ว: default config ไม่เก็บ F-17 และ CI เรียก dedicated
npm script; selection proof0/6 และ local CI-command browser6 tests ผ่านใน58.2s
หลักฐาน: [review closure](evidence/feature-candidate.md#final-review-ci-composition-finding-resolved--2026-11-05)
V-17 ยังคง Partial เฉพาะ final committed candidate/required remote CI; ไม่มีคำสั่ง Git
ขั้นถัดไปต้องรอเจ้าของสั่ง commit/push/เปิด PR ก่อนติดตาม required CI ไม่ต้อง refactor ซ้ำ

## Publication authorization — 2026-11-05

เจ้าของสั่ง commit/push/เปิด PR แล้ว; V-17 ยัง Partial ระหว่างรอ required CI บน SHA ล่าสุด
ติดตาม CI ต่อจนจบและรายงาน SHA/run URL โดยไม่สร้างเอกสาร commit วน; ยังไม่ merge

## Required CI repair checkpoint — 2026-11-05

Candidate6998c22 บน PR#46: backend24failed/4263passed ทั้งpushและPR run; อีก5jobsผ่าน
แก้เฉพาะ test contracts/gate roots/loop doubles และ F-17 owner scheduling teardown;
[หลักฐาน root cause และ targeted74+7](evidence/feature-candidate.md#required-ci-first-candidate-failure-and-test-integration-repair--2026-11-05)
V-17 ยังไม่ผ่านจน required CI บน repair SHA ผ่าน; บันทึกผลจริงไว้ ไม่ถือว่า targeted แทน CI

## Expanded CI regression checkpoint — 2026-11-05

385bce8 required CI backendยังFailed20/4267passed ทั้งpushและPR; contract/gate/doublesผ่าน
แก้ F-17 seed helperที่เรียกglobal inboxโดยไม่ตั้งใจให้targetเฉพาะrequestของfixture;
negative cross-owner proofยืนยันก่อนแก้ แล้ว expanded API→scheduler111/serve SLA2/
rollback guards16ผ่านหลังแก้; [รายละเอียด](evidence/feature-candidate.md#second-ci-candidate-remaining-scheduler-fixture-leak--2026-11-05)
V-17 ยังPartialพร้อมประวัติFailed คงรอ required CIบนcandidateใหม่ ไม่ถือว่าlocalผ่านแทนCI

## Approved diagnostic checkpoint — 2026-11-05

888cdff push/PR CIยัง20failed/4268passed; อีก5jobsผ่าน เจ้าของเลือก A หลัง3รอบให้เพิ่ม
failure-only read-only scanner diagnostic โดยคงcriteria/limits/production logic;
[fresh diagnostic31 passed และhistorical failures](evidence/feature-candidate.md#owner-approved-read-only-ci-diagnostic--2026-11-05)
V-17 ยังคงPartialพร้อมFailed CI evidence; รอบถัดไปเก็บsnapshotจากfull-suite context
ไม่ถือว่าlocal111หรือdiagnostic31ผ่านแล้วทำให้ required CI ผ่าน

## Owner-approved CI isolation checkpoint — 2026-11-05

2407df2 diagnostic CI finished20failed/4270passedทั้งpush/PR; snapshots40ชุดยืนยัน
bounded candidate batch20เต็มด้วยforeign ownersจึงไม่ถึงtest owner แหล่งราคาในตัวอย่างพร้อม
เจ้าของเลือก A ให้แยก F-17 integration หลังreset/migrationในrequired backend job
ตาม patternเดิม ไม่เปลี่ยนproduction/tests/assertions/limits/retry; collectionครบ4290
เท่าเดิม (main4242 + F1748, overlap0); local freshDB isolated48passed56.11s และ
API/bridge/same-pair/source-resumption105passed57.78s รวม20กรณีที่ล้มในCIก่อนหน้า
actionlintผ่าน; rollback16ยังอยู่stepแยกเดิม V-17ยังPartialรอrequiredCIบนcandidateใหม่
รายละเอียดและหลักฐานอยู่ใน evidence/feature-candidate.md; ไม่อนุญาตmerge/Live
