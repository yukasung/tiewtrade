# F-17 — TP/SL และ Bracket — Validation

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-04; NC-F17-06 Approved 2026-11-04**; **NC-SET4-12 Approved A 2026-11-06; §16/18 Approved 2026-11-07 - separate internal checkpoint**
วันที่: 2026-11-04

NC-F17-MANUAL-01: [validation amendment MF-01–14](manual-acceptance-fix-validation.md)
**Approved 2026-11-08**; local implementation/check results are recorded in
[evidence](evidence/manual-acceptance-fix/implementation-checkpoint.md). Owner manual
replacement/review/remote CI remain pending; requirement approval is not a test pass.
Local manual round 2026-11-08: **Failed** — two partial BUY orders ended EXPIRED,
two protections FAILED/PROTECTION_SETUP_REJECTED; pure existing constraint check on
stored net quantities returned QUANTITY_NOT_ON_STEP. Local stop launcher lacked
authority flag; no durable stop request found. All four activation gates now off;
positions/history retained. Diagnosis/proposal are not a successful replacement run.
อ้างอิง: requirements.md Approved 2026-11-04; plan.md Approved 2026-11-04

NC-F17-SEC-01: **Approved A 2026-11-08** — [six exact public-checksum exceptions](security-checksum-publication-proposal.md), existing policy tests, normal commit/push and one replacement required CI round. No scanner or trading-rule change; CI results remain pending until observed.

**Post-merge pool-evidence amendment Approved A 2026-11-08:** [atomic diagnostic publication](postmerge-pool-evidence-atomic-proposal.md), preserving schema/resource/financial criteria. New follow-up branch, fault/real-DB tests and one PR/CI round approved; no automatic merge. Local12 tests/static checks Passed ([checkpoint](evidence/manual-acceptance-fix/postmerge-pool-atomic/checkpoint.md)); required CI remains Pending.

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
| V-17 | affected regressions/static/CI | core matching/positions, real DB F-13–F-19 ที่กระทบ, risk/stop/catalog, API/UI; ruff/format/mypy/import-linter/frontend checks/build/generated types ที่เกี่ยวข้อง; required CI บน final SHA และ review | Feature | Passed on recovery merge f15596d — review/fixes/refactor and current-SHA CI6/6 + Security7/7 passed; backend4761 main +95 isolated cases. Retained workload reuse and remaining admission/Release limits are recorded in the merged-candidate reconciliation below; historical runs are preserved. |
| V-18 | integrated Paper acceptance | full regression/cross-feature E2E ท้ายชุดที่ 4; ใช้ profiles/thresholds ที่อนุมัติของ F-14/F-15/F-16 และหลักฐานที่ยัง valid; protection coverage เพิ่มผ่าน Feature cases ไม่แทน baseline volume/SLA | Batch | Partial / Failed — standaloneF15W1 failed at60s cycle bound; W2/W3NotRun. W4 revalidated Passed on0065, with F-15-only coverage. Integrated profile NC-SET4-01 Approved A; execution pending under the consolidated plan. |
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

## Required CI isolation result and base synchronization — 2026-11-05

a7c4bee94f2fefd7d84e268f7a67b78698b6096b passed all required CI jobs:
- push https://github.com/yukasung/tiewtrade/actions/runs/42056045217
- PR https://github.com/yukasung/tiewtrade/actions/runs/42056057034
- Both runs: main4242 + isolatedF1748 + writer-fence1 + optional-limit1 +
  fresh-global-state27 + rollback16 passed, total4335 backend tests; frontend,
  API contract, container and browser E2E also passed. No tests/assertions reduced.

Main advanced to security patch a3a8652 (#47); strict required status checks require
base synchronization before merge. Keep the a7c4bee isolation evidence; V-17 remains
Partial pending required CI on the synchronized candidate. This evidence is combined
with the actual main synchronization, not a CI-documentation-only commit. No PR merge.

## Set-4 Batch checkpoint — 2026-11-06

F17 merged as98ff2f8; [post-merge CI](https://github.com/yukasung/tiewtrade/actions/runs/42063166018)
passed all6jobs/4335backend tests on the exact candidate tree. V17 now Passed.
Owner selected standalone F15 W1–W4 first and integrated-profile preparation later.
V18 remains Partial/Failed: W1 cycle timeout, W4 passed, W2/W3 Not Run. NC-SET4-01
blocks integrated F14/F16/F17 workload acceptance until its missing profile is approved.
V19/V20 retain Pending Dependency/Full Validation. Do not mark Completed.
Evidence: [Batch ledger](evidence/batch-20261106/README.md). No production source changes or Git publication.

Latest standalone diagnostic captured the actual failed cycle without changing
profile/pool/scheduler:38targeted tests/static checks passed, W1 still Failed60s
after215cycles. Queue/processing waits accumulate; final fill committed0.187s after
the deadline. Post-stop safety checks do not replace the complete financial oracle.
W2/W3 remain Not Run, W4 Passed0064; V18 stays Partial/Failed. NC-SET4-02 now also
requires an owner decision before the proposed standalone R8 opt-in runtime.

Owner subsequently approved standalone R8 opt-in and its explicit acceptance
mapping (NC-SET4-02 closed). Targeted safety/config checks and static checks passed.
One full W1 trial prepared2000baseline orders and reached2021cycles, then Failed
`WriterLeaseLost` in the publisher,1378.654s including setup. Observed processing
p95=0.571253s also exceeds the unchanged0.250s bound. No full financial/PnL oracle
or30-minute acceptance; post-stop safety snapshot is not a pass. V18 stays
Partial/Failed; W2/W3NotRun, W4Passed0064, integrated NC-SET4-01 still open.
The authorized trial stopped; no new workload or production change followed.

Subsequent NC-SET4-03 A authorized test-only heartbeat and one bounded diagnostic.
89targeted/static checks passed; diagnostic prepared2000baseline orders but stopped
Incomplete after440.559s due to observer metadata publication errors affecting
claims. All streams/pools closed and post-stop safety counts zero; full oracle
was not produced. Atomic metadata repair passed8affected checks/static; NC-SET4-04
awaits replacement-run permission. V18 stays Partial/Failed; no production change,
full W1 retry, W2/W3 or Git publication. See the Batch ledger for limitations.

NC-SET4-04 latest A explicitly authorized one replacement. It completed600cycles/
3000commands with all100owner financial oracles passed, but Failed processing
p95=469.526ms >250ms and input_lag22 >20. No observer/lease/worker errors; streams/
pools closed with no workers left. Instrumented diagnostic only; full W1 and F17
integrated coverage remain unproved. V18Partial/Failed, W2/W3NotRun, W4Passed0064
and NC-SET4-01 unchanged. Stop/report after the replacement; no further run or
production change. See the Batch ledger for source identity and timing limits.


### Historical consolidated closure checkpoint — before integrated approval

Owner requested continuous work to close F-17. NC10 review completed; one Medium
test-coverage gap was fixed using the existing commit-loss oracle, with both owner
and coordinator commit replies lost. Both cases passed; no extra claim/processing,
and existing lease/fencing recovery remained valid. No runtime defect established.
Current protection integration passed48/48 on a fresh0065 DB; changed test Ruff,
format and mypy passed. Prior applicable NC10 safety/static evidence remains valid.

W4 revalidated the actual0065 writer: canonical cash/position/history and RLS/grants
matched after restore,23 evidence records replayed, expired claim1→0 with no extra
economic effects. This closes the new-writer F-15 W4 revalidation gap only; the
fixture does not populate F-17 history. Four scratch DBs retained with0 sessions/
advisory locks. Source hashes remained unchanged during all checks.

V18 still fails on workload acceptance and lacks the approved integrated profile.
The [consolidated proposal](integrated-paper-acceptance-plan.md) is now reviewable;
it is not self-approved by the implementation. V19/V20 remain Not Run/Pending
Dependency. Current Set-4 changes are not published and need final candidate CI.
Next: owner decision on NC-SET4-01 before the newly defined integrated campaign;
do not lower thresholds or declare F-17 Completed. See Batch ledger for raw evidence.

### Latest integrated Paper checkpoint — profile approved, diagnostic failed

The owner approved the [consolidated Paper plan](integrated-paper-acceptance-plan.md),
closing NC-SET4-01. Earlier statements that the profile is Draft/missing are historical.
The initial diagnostic gate has not passed: first run failed during setup; after
an observation repair the second completed baseline2000 but only188/600 cycles,
1191 offered/admitted and1091 completed of3000 planned before60.001s timeout.
Partial processing p95=441.6ms;18/20 worker processes exited on selection deadlines.
A complete financial/final-tail/resource acceptance result was not produced.

Harness tests133 and later affected45 passed (overlapping scopes), with Ruff/format/
mypy passed before timing. The48-case fresh0065 protection result and standalone
W4 restore result remain valid for their stated scopes. No production source was
changed by the diagnostic harness work. Cleanup verified; both failures retained.
V18 remains Partial/Failed; later W1–W3/HTTP/snapshot/extended restore phases cannot
advance. V19/V20 stay Not Run/Pending Dependency; current changes still need final
published-candidate CI. No Completed or merge-ready claim is made.

Next: owner decision on [NC-SET4-11](../2026-10-18-paper-order-matching/worker-claim-contention-amendment.md)
before changing the approved blocking coordinator protocol. The profile's existing
criteria and conditional later phases remain binding. Raw evidence: Batch ledger.


### Latest NC-SET4-11 checkpoint

NC11 is Approved A and implemented. V2 safety135/static/import checks passed; its
one diagnostic failed before measurement on book `WriterLeaseLost` after165.058s.
Baseline394/2000 orders succeeded; measured0/3000 commands and0/600 cycles. Full
financial/final-tail/resource acceptance Not Reached. Cleanup verified; raw evidence
retained. Detailed baseline publisher/DB latency cause remains unproved because
only aggregate timing survives setup. No repeat or W1 launched.

V18 remains Partial/Failed; V19/V20 remain Not Run/Pending Dependency. Prior48-case
protection and0065 restore results retain their historical scope and do not certify
the subsequently changed V2 worker; affected final-candidate checks/CI are pending.
Next step is a bounded publisher-baseline trace plan before a new authorized run.
The approved NC11 stop/report checkpoint has been reached, not F-17 Completed.

### Recovered candidate and publisher diagnostic checkpoint — 2026-11-06

Temporary Set-4 worktree/raw artifacts were lost. Source was reconstructed into the
permanent sibling `TiewTrade-paper-set4-recovery`; old narrative is historical, not
replacement raw evidence. Fresh recovery303+2 tests passed, all28 recovered Python
files type-checked; follow-up78 affected cases and scoped static checks passed,
7 import contracts kept. The retained original0065 DB function matches recovery.

The owner-approved publisher timing follow-up and exactly one diagnostic are complete:
566.039s, baseline2000/2000, measured917/3000 commands and145/600 cycles before
60.002s cycle timeout. Partial measured worker p95=470.510ms>250ms. Publisher lease
loss did not reproduce; no worker exited abnormally. Full financial/final-tail/resource
acceptance Not Reached. All pools/streams/processes and DB connections/locks closed;
839 candidate hashes stable. No repeat/W1/publication. See [new raw evidence](evidence/recovery-20261106/README.md).

V18 remains Partial/Failed; V19/V20 Pending Dependency; final candidate CI Pending.
Integrated profile NC-SET4-01 remains Approved A. Next recommended step: a concrete
runtime-fix plan for queue/processing/polling progress using these traces, before any
new timed run. Preserve60s and250ms criteria; this checkpoint does not close F-17.

## Internal Paper checkpoint - NC-SET4-12 Approved A

Owner approved the [internal-pilot requirements/plan/validation amendment](internal-paper-acceptance-amendment.md)
on2026-11-06. Use its parameters as the single source of truth. Scoped harness/checks
and conditional campaign are authorized. Existing100-account results, Release gates,
Completed definition and Git/deploy permissions remain unchanged.

NC12 scoped correctness checks passed:2 new UUID-boundary regressions,48 affected
F17 tests, the replacement restore safety fixture,192 harness/HTTP/observation checks,
and33 checks after the controlled20 poll-gate correction; scoped static checks passed.

The approved controlled20 replacement **Passed** in132.922s:400 baseline orders,
20/20 owners start≤1s (slowest444.013ms), exact exit/financial/retry checks passed.
D20 subsequently **Failed** in341.074s:600/600 commands and all20 financial oracles
passed, processing p95=170.932ms/p99=313.010ms passed, but the final resource sample
had68connections against initial57+2. First60 samples were57–59; the final spike
coincides with final-tail reads that retain concurrency20 by the original design.
Cleanup0 connections/0 advisory locks does not prove absence of an in-run leak.
Keep the Failed result. At that checkpoint W1/W2/W3/W4 were Not Run; snapshots/
rebuild for those phases are not covered by D20. See
[amendment§10–12](internal-paper-acceptance-amendment.md) for subsequent approvals
and outcomes. F17 and the internal pilot remain open;
financial/resource thresholds and Git/deploy gates are unchanged.

Section11 was subsequently Approved A and implemented in the harness only;126
related tests/3.08s and scoped static checks passed. Its one D20 replacement was
**Incomplete** after205.784s measured/247.817s total:395/600 commands completed,
publisher readiness rejected a book before final-tail. Exact guard clock/fields
are missing, so stale input versus future-time rejection is not distinguished.
Cleanup0/0 and all3803 poll permits returned. The final-tail correction was not yet
campaign-proven at that checkpoint. Section12 was subsequently approved A.

Section12:154 targeted checks plus12 observer rechecks and scoped static checks
passed. D20 readiness-observation run **Passed**341.660s total/303.398s measured:
600/600commands, all20 financial oracles/global invariants, p95=192.754ms,
p99=325.518ms, connections57→58 (peak59), final-tail0.947s. Cleanup0/0;
candidate unchanged. Readiness rejection did not recur; its prior cause remains
unproven. Evidence: `evidence/recovery-20261106/nc12-d20-readiness/`.
W1 then **Incomplete** under the approved continuation:1227.598s measured,
2384/3600completed,60s cycle deadline while waiting for final sell FILLED.
Financial/global oracle, final-tail and snapshot/rebuild were not reached.
Partial p95=487.319ms/p99=1184.654ms; connections57→63,peak64. These are diagnostic
statistics, not completed acceptance. A separate terminal-history SELECT timed out;
read-only plans show a1294-event scan and a proposed8-event lookup using the same
index. No production edit. Cleanup0/0; candidate unchanged; no parent readiness
rejection. Evidence: `evidence/recovery-20261106/nc12-w1/`.
Section13 subsequently Approved A; the scoped query fix passed44 worker/storage
cases and6 TP/SL cases plus static checks. The authorized next gate is a new D20,
then W1 on a separate fresh DB if D20 passes. W2/overflow/W3/fullW4 remain Not Run. Controlled20/D20 remain Passed on their
recorded candidate; F17 remains Pending Full Validation.


Section13 query optimization is implemented;50 targeted real-DB safety cases and
scoped Ruff/format/mypy passed. First D20 launcher was Incomplete at disk preflight
before any workload. After owner continuation/environment recovery, D20 **Failed**:
600/600commands and20/20 financial/global/resource oracles passed; p95=531.809ms
failed250ms and measured book inputs2976failed3000. p99=981.639ms passed1s;
connections57→59,cleanup0/0, candidate unchanged. At-run host load1min24.84 on8CPUs
and unrelated Node/Next work confound comparison with the prior pass; sole cause
is not established. No W1 replacement or later phase started. Evidence:
`evidence/recovery-20261106/nc12-section13-d20-resumed/`.
Next: owner decision on amendment§14's bounded environment preflight and one D20;
no additional production fix or threshold relaxation is proposed.


Section14 revised plan was approved and implemented;211 unique targeted cases are
covered by passing results, Ruff/format passed5files, mypy passed4repo harness files,
and runner CLI help passed. Production code is unchanged from§13. The one authorized
preflight **Incomplete** at first sample in0.437s:load1=19.29>8CPU; PostgreSQL/Redis
ready and17.11GBfree. It stopped before creating`run/`, fixture, workers or measured
commands. Cleanup0/0; candidate and pinned runner unchanged. Real passing120s
window/D20 runtime host sampling and W1 replacement onward remain Not Run.
Evidence: `evidence/recovery-20261106/nc12-section14-d20/`.
Next: owner-triggered preflight after host activity subsides, with the same approved
criteria; no automatic retry. F17 remains Pending Full Validation.


The owner requested section14 readiness revision2 on2026-11-07. Future admission
uses mean sampled CPU idle≥20% across7readings and pressure Normal/Warning allowed,
Critical/unknown rejected; load is informational. Fixed120s sample starts, disk,
services and all financial/latency/input-rate criteria remain.108 targeted tests
passed/0.81s; Ruff/format/mypy passed2files; native sensor read worked. No new
preflight/D20 acceptance run; preserve the old load-gated Incomplete and previous
Failed results. Evidence: `evidence/recovery-20261106/nc12-section14-v2/`.
Next: owner-triggered preflight/D20 under the revised environmental rule.


NC12§14 revision2 D20 **Passed** on2026-11-07:7-sample preflight mean idle49.481%,
600/600commands,20/20financial oracles/global/resource checks; p95=116.400ms,
p99=164.199ms, book3000/3000, connections57→58 (peak59),cleanup0/0, candidate
unchanged. Evidence: `nc12-section14-v2-d20/`. Next: approved fresh-DB W1 with
preflight and30min authenticated HTTP workload, then conditional remaining phases.
F17/internal-pilot acceptance remain open until all required gates pass.


NC12§14 revision2 W1 **Failed solely the connection-growth predicate**:3600/3600
commands, all20 financial/global checks, engine p95/p99=133.580/191.986ms,
book18017/18000,20 snapshots p95/p99=32.977/33.661ms and20rebuilds max7.052s
passed. Connections57→60 against59allowed (peak61); increase occurs at first use,
but per-pool API ownership/return evidence is missing. Cleanup0/0; candidate
unchanged. Preserve Failed. Evidence: `nc12-section14-v2-w1/`.
Next: owner decision on amendment§15's direct pool-resource contract and one W1;
no W2/overflow/W3/fullW4 or automatic retry started. F17 remains not Completed.


NC12 §15 implementation checkpoint — 2026-11-07: owner approved A. Added NC12-only
owned-pool inventory/periodic samples/pre-disposal return checks, reusing PoolEvidence.
Production and other profile predicates unchanged. Affected regression:214 passed,
4 initial failures corrected; scoped rechecks35/35 passed. Ruff/format and scoped
mypy passed. Existing production50 safety checks remain applicable. One approved
fresh-DB W1 is next; no new timed result yet. Historical §14-v2 W1 remains Failed.


NC12 §15 W1 — Incomplete (2026-11-07),274.262s total. Preflight passed(meanCPUidle66.817%).
Stopped early because new pool instrumentation omitted the existing read-only admin
engine used by require_empty_database; DatabaseRole conversion recorded ValueError.
No30min/performance acceptance. All20 workers stopped cleanly; registered loans
returned, final DB cleanup0connections/0advisory locks; candidate/runner unchanged.
Evidence:`nc12-section15-w1/analysis.md`. Historical Failed results retained.
W2/overflow/W3/W4 not started. Next: owner approval of amendment§16 before correction
and one replacement W1; no automatic retry.


NC12 §16 criteria revision — Proposed,2026-11-07, at owner's request after repeated
unsuccessful attempts. Proposal separates environment/harness Incomplete from proven
system Failed; uses complete owned pool capacity/return evidence including the existing
admin observer. It preserves financial/safety/latency/workload thresholds, prior
Failed/Incomplete results and conditional phase gates. Actual startup/shutdown coverage
must pass targeted real-DB tests before another long campaign. Specific revised criteria
and one replacement W1 await approval in internal-paper-acceptance-amendment.md§16.
Documentation only this turn; no source change or new campaign.


NC12 §16 revised pilot latency proposal (owner requested less strict criteria):
engine p95≤500ms/p99≤2s for invited20-account Paper pilot only; retain250ms/1s as
reported target with explicit warning when missed. Keep financial/order/position
correctness, TP/SL start≤1s, snapshot/recovery/feed/workload/durations and full Release
requirements unchanged. Specific thresholds await approval; no runtime change or
new campaign. Admin-observer instrumentation defect still requires correction.


NC12 §16 implementation/checks complete,2026-11-07. Owner approved500ms/2s
engine processing for20-account Paper pilot only; original250ms/1s target remains
reported with performance_warning. Default profiles, protection start, snapshots,
workload duration and production unchanged. Complete parent inventory13(including
read-only ADMIN_OBSERVER5+10), workers2 each. Unknown identity/read-write admin
options/missing evidence fail closed; real resource failures remain distinct from
Incomplete observer evidence, including simultaneous failures.

Targeted182 passed8.46s; classification8 passed1.00s(5 overlapping,3 additional).
Ruff/format passed5repo files; mypy passed5files. Private campaign runner scoped Ruff
passed ignoring only its pre-existing BLE001 catch used to retain cleanup evidence;
format passed. Production source hashes unchanged from§15 candidate. No new financial
code or persistent/session state. Existing50 production safety cases remain applicable.

Next: one approved fresh-DB W1, same3600commands/30min withpreflight (~35–40min total).
Passing continues W2/overflow/W3/W4; failure/incomplete stops without retry. Earlier
results retained. This checkpoint is not F17 Completed.


NC12 §16 — owner approved2026-11-07: internal20-account engine processing acceptance
is p95≤500ms/p99≤2s; retain250ms/1s as a separately reported target with warning.
This supersedes IP-R4 only for internal engine-processing acceptance. TP/SL start≤1s,
snapshot limits, financial/safety correctness, workload/duration and100-account Release
criteria remain unchanged. Complete owned pool inventory includes the read-only admin
observer; missing evidence is Incomplete and proven violations remain Failed. See
[approved §16](internal-paper-acceptance-amendment.md#16-revised-acceptance-and-complete-owned-inventory--approved2026-11-07).


NC12 §16 W1 — Passed,2026-11-07. Total2080.281s; measured1800.965s.
3600/3600commands,720cycles,1440fills,720cancels,720replays,0rejects; all20financial
oracles/global invariants passed. Engine p95=144.262ms/p99=211.241ms: both original
250ms/1s targets and approved pilot500ms/2s ceilings passed; no performance warning.
Measured inputs18010/18000. Snapshots20/20 passed p95=36.377ms/
p99=36.468ms; all20rebuilds passed,max6.359s.
Owned inventory complete(parent13,workers20×2); all21process reports passed, no
pool violations/incomplete evidence, all loans returned before disposal. Raw aggregate
connections57→61,peak61 retained; no initial+2 proxy used. Final cleanup0connections/
0advisory locks. Candidate/runner unchanged. Evidence:nc12-section16-w1/.

Next: approved fresh-DB W2, then overflow/W3/W4 conditional on passing. Historical
Failed/Incomplete runs retained. This is W1 internal-pilot acceptance only; F17 stays open.


NC12 §16 W2 — Failed throughput duration,2026-11-07. Total1136.363s;
measurement963.571s exceeds600s target+60s allowance=660s. This is the sole failed
acceptance predicate. Completed12000/12000commands,2400cycles,4800fills,2400cancels,
2400replays,0rejects; all20financial/global/snapshot/rebuild checks passed.
Engine p95=363.782ms/p99=492.133ms passes approved pilot500ms/2s; original250ms
p95 target missed and performance_warning=true retained. This does not waive the
separate throughput/duration criterion. Measured inputs9635/6000, workers no failures,
resource/pool checks all passed; all registered loans returned before disposal.
Parent13pools/workers20×2 inventory complete, observer errors none. Snapshots20/20
p95=18.214ms/p99=18.502ms; rebuild max1.068s. Input lag4 remained within the existing
bound. Final cleanup0connections/0advisory locks; candidate/runner unchanged.

The cohort's effective completed throughput is12.454commands/s over963.571s. This
closed-loop observation does not establish an absolute capacity or prove which
query/queue/worker stage is the bottleneck. No causal root-cause claim is made.
Evidence:campaign-result.json, run/result.json, gate-assessment.json, raw samples/logs.

Stop checkpoint: W1 Passed is retained; W2 Failed retained. No W2_OVERFLOW/W3/fullW4
started, no automatic rerun, source fix or further threshold relaxation. F17 remains
Pending Full Validation. Next requires owner decision on the next scope: retain the
20commands/s burst requirement and investigate/fix throughput, or explicitly approve
a distinct lower-load internal profile while retaining the20commands/s requirement
for the original release gate. Any concrete profile requires declared rate/counts/
duration before execution; do not choose numbers from this failed run to relabel it.




NC12 W2 existing-evidence analysis complete,2026-11-07. Owner-approved read-only
scope only: W2 owner cycle interval7.971s versus5s planned; dominant observed gaps
follow HTTP intake, while poll-permit p95≤2.5ms and bridge attempts=1 for all9600
unique requests. Worker scan/coordination/claim/process division remains unmeasured;
no causal SQL/backoff conclusion. W2 remains Failed; no new campaign/source fix.
Evidence:nc12-section16-w2/throughput-analysis.md and offline timing/timestamp JSON.
Next: approve proposed§17 bounded worker-phase diagnostic, or choose another scope.




NC12 §18 lower-burst proposal,2026-11-07: owner requested criteria revision instead
of another diagnostic. Defer unapproved§17. Propose explicit internal V2 W2 target
10commands/s, retaining20owners/400baseline/120cycles-per-owner/12000commands, hence
1200s target/1260s completion bound and≥12000book inputs. Financial/safety and all
other gates unchanged; reuse valid W1 evidence. Specific profile values/campaign
still await approval. No source change or new run. W2 V1 remains Failed; full F17
remains open separately from internal pilot acceptance.


NC12 §18 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V2 changes
W2 only to10commands/s/1200s with120cycles-per-owner/12000commands unchanged.
Completion allowance1260s; required book inputs12000 at10Hz. V1/defaults, money,
worker/pool/coordinator/retry and other phase definitions unchanged. Actual V2 name
is forwarded to worker subprocesses and recorded in manifests/timing revision.
Tests233 passed8.77s;5 profile rechecks passed0.31s after test typing correction.
Scoped Ruff/format passed5repo files and private runner; mypy passed5files. Private
runner retains its pre-existing broad cleanup exception with BLE001 excluded only
for that file. Production source hashes unchanged; prior safety evidence remains
valid. W1§16 passing evidence reused only for unchanged assertions. All earlier
Failed/Incomplete runs retained. No§17 diagnostic added or executed.

Next: one approved fresh-DB V2 W2 withpreflight (~25–30min including20min measured),
then overflow/W3/W4 conditional on passing each gate. No repeated W1/D20. A failed/
incomplete gate stops without retry. Internal pilot and F17 remain open pending gates.


NC12 §18 V2 W2 — Failed resource contract,2026-11-07. Total1445.897s;
measured1241.602s passes1200s+60s allowance=1260s. All12000commands completed,
2400cycles,4800fills,2400cancels,2400replays,0rejections. All20financial/global/
position checks passed; snapshot p95=16.945ms/p99=17.360ms,20rebuilds,max3.415s.
Engine p95=363.444ms/p99=541.362ms passes500ms/2s pilot ceilings; performance_warning
retained because original250ms target missed. Inputs12395/12000,input lag9 within
existing bound, no worker failures. The relaxed throughput/duration gate passed.

The only failed gate is the owned-pool contract: parent recorded4 active-work
ConnectionResourceError entries, all original_exception=CancelledError,sqlstate empty,
quiescing=false. Inventory complete(parent13,workers20×2); all borrowed connections
returned before final disposal; all20worker reports passed. Final cleanup0connections/
0advisory locks and candidate/runner unchanged. No proven connection leak is reported.

The evidence does NOT identify which pool/task/query was cancelled or at what time.
Do not silently treat these as normal shutdown cancellations or assume a trading
transaction failed. Parent completed normally; this alone does not establish the
origin/safety of those4cancellations. Existing API price-read code has bounded read
deadlines, so deliberate read cancellation is one candidate, not a proven cause.

Stop checkpoint: preserve Failed and all prior results. No overflow/W3/fullW4,
replacement W2, further threshold change, production edit or Git/deploy action.
Existing§16 W1 remains Passed. Internal pilot and F17 remain open.

Recommended next scope: add test-only cancellation provenance(timestamp,pool role/
identity,task or named operation,quiescence/deadline context; never SQL,binds,secrets),
and targeted real-DB regressions distinguishing a known read-only deadline from
worker/financial cancellation, disconnect and leaked borrow. Reuse OwnedPools and
existing API lifecycle/readers. Establish a specific rule only after the origin is
known; no new timed campaign is proposed or authorized at this checkpoint. Current
source/harness is unchanged after the failed gate. A next implementation/campaign
requires a concrete approved scope under§18's stop rule.


NC12 §19 completed,2026-11-07. Test-only OwnedPools resource-error provenance
now includes UTC/monotonic timestamps, pid, engine/current-pool identity/generation,
role/capacity/configured-readonly, task id/cancellation count and bounded project
coroutine file/function/line locations. It never captures task names, SQL/binds,
URLs, payloads, locals or exception text. Unknown task/deadline stays unknown. Pool
identity is labelled current-engine-pool or original-registration fallback; after
churn this is not proof of the invalidated connection's original pool. Details are
bounded to16 with omitted count; all errors remain counted. No extra SQL queries.

Real-DB short regressions distinguish an explicit read-only query deadline from an
explicitly cancelled ENGINE query, preserve TimeoutError/CancelledError, show loans
returned and hooks restored, and prove neither secret binds nor task names appear.
Existing disconnect simulation, leaked-borrow, lifecycle/generation/classification
cases still pass. No financial state/session storage or production change.
Final affected suite82passed14.38s; scoped Ruff/format/mypy passed2files. Existing
production safety evidence remains valid; production hashes unchanged from§18.
Evidence: nc12-section19-final-targeted.xml/.log and nc12-section19-final-mypy.log.

Limitation: these controlled regressions do not identify the4historical W2 query
cancellations; the old artifact lacks source identity/time. Active cancellations
still fail under current acceptance; no warning waiver or retrospective Passed.
No workload/campaign was run. §18 V2 W2 remains Failed, W1 remains Passed; overflow/
W3/fullW4 and F17 acceptance remain pending. §19 stop/report checkpoint reached.


NC12 §20 approved2026-11-07. Reuse§19 final82targeted tests and scoped checks;
no further harness/production change. One fresh-DB PAPER_INTERNAL20_V2 W2 withbounded
cancellation provenance is starting; preflight and all existing gates remain binding.
Pin source/config/runner/schema; no retrospective status changes. Passing permits
existing overflow→W3→W4; failure/incomplete stops/report without retry. W1 reused.


NC12 §20 V2 W2 — Passed,2026-11-07. Total1398.032s; measured1205.681s≤1260s.
Completed12000/12000commands,2400cycles,4800fills,2400cancels,2400replays,0rejects;
all20financial/global/position checks passed. Engine p95=364.028ms/p99=516.442ms
passes pilot500ms/2s; performance_warning remains for original250ms p95 target.
Inputs12056/12000. Snapshots20/20 p95=50.690ms/p99=50.920ms; rebuildmax1.974s.
Owned inventory complete(parent13,workers20×2); all21process reports passed, no
resource errors/cancellations, all loans returned before disposal. Final cleanup
0connections/0advisory locks, candidate/runner unchanged. Evidence:nc12-section20-w2/.
No historical Failed/Incomplete status changed; the4old cancellations remain
unattributed because none recurred here. One passing run is not a causal fix claim.

Next: approved fresh-DB overflow case, then W3/W4 conditional on each gate passing.
W1§16 evidence reused. F17/internal pilot remain open until remaining gates pass.


NC12 §20 V2 overflow — Passed,2026-11-07. Total175.184s includingpreflight;
4097inputs overflow case recovered in20.155s≤60s, before/after economic snapshots
identical for all20owners (no fill/ledger/position change); baseline financial/global
checks passed. Parent plus initial/recovery workers' owned pool reports complete,
all loans returned, no resource errors; final cleanup0connections/0advisory locks,
candidate/runner unchanged. Evidence:nc12-section20-overflow/.
Next: approved W3 with unchanged4h/282cycles-per-owner/7fault schedule and periodic
position checks, then W4 only on passing. W1/W2 accepted in their existing scope;
F17/internal acceptance not yet closed. No further criteria or source change.


NC12 §20 W3 — Incomplete/owner time objection,2026-11-07. Owner said4hours was
too long and interrupted the turn. Stopped only the owned W3 campaign via SIGINT
at53.842s during preflight(3samples), before run/fixture/workers/measurement existed.
No W3 financial/performance/endurance acceptance claimed. Cleanup0connections/
0advisory locks; candidate/runner unchanged. Preserve raw Incomplete/CancelledError.
W1§16,W2§20 and overflow§20 passing evidence retained. No W3 retry/W4 started.
Next: specific shorter internal checkpoint proposal§21 requires approval before code
or execution; original4h Release requirement remains Pending Full Validation.


NC12 §21 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V3 changes
W3 only to1800s/30cycles-per-owner/3000commands;7pinned fault kinds/durations retained
at180..1260s offsets. Selected duration drives hold/minimum, RSS window and30periodic
snapshot rounds(620total includingfinal20), with15000inputs and1830s completion
ceiling. V1/V2/default4h/282cycles/original schedule and240periodic rounds unchanged.
Short stability is labelled separately;4h Release remains Pending Full Validation.

Targeted220passed10.73s;6affected final rechecks passed1.50s; scoped Ruff/format and
mypy passed5repo files(private runner scoped Ruff excludes pre-existing BLE001 only).
Actual parent/reporting regression verifies1800s hold/minimum,30snapshot rounds,
short RSS and unchanged financial/counter/latency/resource predicates. Production
source hashes unchanged. Applicable W1/W2/overflow/production safety evidence reused;
no ceremonial reruns. See nc12-section21-*.xml/logs for evidence.

Next: approved one fresh-DB V3 short W3 with existing preflight, estimated35–45min
including30min measured/final replay/cleanup; passing permits W4. A failed/incomplete
gate stops without retry. Prior owner-stopped W3 remains Incomplete; no4h acceptance.


NC12 §21 V3 short W3 — Incomplete after observer resource alarms,2026-11-07.
Stopped the owned campaign after connection churn exposed invalid retired-pool
observations, saving the remaining planned runtime. Total596.076s includes preflight/
fixture/cleanup;30min measurement was not completed.755HTTP records and160snapshot
records retained; no full financial/oracle/fault/endurance acceptance is claimed.
Only initial restart and connection-churn faults had begun; remaining faults/W4 not run.

Parent observer recorded9PoolCapacityViolation and4PoolDisappearedBeforeReturn.
Raw snapshots show disposed ENGINE pool native checkedout=-1/-4 while independent
checkout/checkin event counts changed3→1→0. Installed SQLAlchemy QueuePool.dispose
sets _overflow=-size, and checkedout computes size-checkedin+overflow; late returns
can therefore make the retired pool's native counter negative. This is not an
actual negative/over-capacity connection count. Retired MARKET_DATA pool weakref
was collected while event count1 was still pending; its event count later reached0
before final shutdown. All registered loans returned in final parent proof; cleanup
0connections/0advisory locks and candidate/runner unchanged. Retain raw Incomplete/
CancelledError and original resource flags, not retrospective Passed.

The existing real-DB generation test disposed only after its borrow was returned;
it missed held loans across churn. This evidence identifies an observer accounting
defect, not a justification to waive lost-borrow/capacity safety or claim30min passed.
Evidence:retired-pool-observations.json, parent pool streams/summary, campaign log.

Next: proposed§22 fixes only retired-generation measurement semantics, adds real-DB
held-loan/GC regressions, then one replacement V3 W3 if approved and checks pass.
No source fix/new run after the failed gate. W1§16/W2§20/overflow§20 remain Passed;
4h Release remains Pending Full Validation and F17 remains open.


NC12 §22 implemented/checked,2026-11-07. Retired generations retain raw native
counters as informational after declared intermediate dispose; live pools still
require native bounds/configuration and every generation's event-tracked active/
peak borrow bounds remain binding. Retired weakref loss with pending returns is
recorded as pending, never waived at quiescence. Final zero-return/inventory/error
criteria unchanged; unexpected live pool loss and capacity mutation still fail.

Real-DB regression holds2loans across dispose, observes nativecheckedout=-1 while
one event-tracked loan remains, then returns both and proves oldpool GC without
observer retention. Simulated missing-native-view cases keep real DB loans and
checkin callbacks; returned passes, deliberately unreturned fails. Live pool loss/
retired configuration mutation and prior API/worker/disconnect/cancellation tests
pass. Initial2failures were reused nonempty DB and double-cleanup of a closed loan;
fixed test cleanup and used a fresh isolated test DB, preserving initial logs.
Final88targeted cases passed14.17s; scoped Ruff/format/mypy passed2files. Production
source unchanged and prior applicable financial/safety proofs retained.

Next: one approved fresh-DB PAPER_INTERNAL20_V3 short W3, same30min/3000commands/
7faults and§19provenance (~35–45min total), then W4 only on passing. Reuse W1/W2/
overflow. Earlier incomplete W3 and all Failed results retained;4h Release remains
Pending Full Validation. No criteria/production/Git/deploy change or automatic retry.


NC12 §22 V3 short W3 — Passed,2026-11-07. Total2089.437s; measured1800.001s.
3000/3000commands,600cycles,1200fills,600cancels,600replays,0rejects; all20financial/
global checks passed. Engine p95=132.721ms/p99=201.237ms passed original targets too.
All7faults RECOVERED:3worker restarts,2connection churns,2Redis outages. Snapshots
620/620 p95=48.893ms/p99=109.821ms;20rebuilds,max7.145s. Inputs18000/15000.
RSS window1800s growth−5.019% passed; this is short-window evidence, not4h endurance.
All81process pool reports complete, retired/live generations returned, no observer
resource errors; cleanup0connections/0advisory locks, candidate/runner unchanged.
Evidence:nc12-section22-w3/. Earlier Failed/Incomplete runs preserved.

Next: approved integrated W4 backup/restore/recovery on fresh source/target DBs.
W1§16,W2§20 and overflow§20 evidence retained; no repeat. Four-hour Release remains
Pending Full Validation and full F17 dependencies/review/CI gates remain open.


NC12 §22 W4 — Incomplete overall / integrated recovery Failed,2026-11-07.
Total206.839s; preflight passed. Real pg_dump/restore canonical data/RLS/grants checks
passed; domain replay21episodes,59evidence records,20checkpoints,18positions; one
expired legacy claim recovered without economic effects. Backup1816699bytes.
F16/F17 integrated recovery then timed out at60s, leaving its result Failed. Outer
campaign records Incomplete/TimeoutError; preserve both scopes and all raw evidence.
Source and target cleanup0connections/0advisory locks; candidate/runner unchanged.

Root cause identified from code and read-only DB evidence: recover() passes target
engines to publisher/parent readers, but f15.run_worker_process() constructs its own
ENGINE/ENGINE_SCAN using ambient source-role URLs. Thus parent waited for target
while worker serviced source. On source, the staged pending receipt and retry became
REJECTED/ORDER_SAFETY_UNAVAILABLE and retry attempt advanced to4; on target both
results remained absent and retry attempt2. These are isolated synthetic fixture
DBs, not user/live data. Never treat target non-progress as a need for larger timeout.
Evidence:source-versus-restored-worker-effects.json/restored-state-snapshot.json,
traceback atprofile_internal_restore.py recover andprofile_workload.py worker setup.

No final integrated pending/exit/retry/idempotency acceptance claimed. No source fix
or new run after this failed gate. W1§16/W2§20/overflow§20/shortW3§22 remain Passed;
4h Release and fullF17 dependencies/required CI remain pending. Next proposed§23
routes only W4 worker engines explicitly to target with unchanged factory defaults,
checks source unchanged, targeted real-DB/default-path regressions and one W4 rerun.
No repeated long workload is proposed.


NC12 §23 implemented/checked,2026-11-07. Optional synchronous test-worker engine
factory defaults to the original role factory lookup. Restored recovery constructs
independent worker-owned target ENGINE/ENGINE_SCAN using scoped role URLs during
synchronous construction only; source env restored before any await. Pool/credential/
scheduling/financial defaults unchanged. Verify compares full source canonical data
(including extensions) before/after target recovery and requires source_unchanged.

Targeted125unique cases covered:124passed in shared suite; the empty-source test
was run after a seeding test and failed its isolation prerequisite, then passed on
a separate fresh DB. Six routing/digest cases rechecked after test import correction
passed1.66s; empty prerequisite passed1.65s. Real two-DB SELECT current_database
proof for both roles plus normal stop/error/cancel cleanup and constructor/config
restoration passed. Scoped Ruff/format/mypy passed3files. Preserve initial logs.
No production change; prior long workload/safety evidence remains applicable to
unchanged default worker path. Required CI/full-regression not replaced by these
partitioned local checks; database-empty cases require isolated fixture execution.

Next: one approved fresh-source/fresh-target W4 with same preflight/fixtures/
backup/restore/60s recovery criterion and strengthened source-unchanged proof,
estimated5–10min. Do not repeat W1/W2/overflow/shortW3. Failed/incomplete stops;
pass closes this local integrated validation checkpoint only, with existing
review/CI/4h Release/bot/notification/Live obligations still separately pending.


NC12 §23 W4 — Passed,2026-11-07. Total148.403s including120s preflight.
Real backup/restore canonical data and RLS/grants match. Domain replay21episodes,
61evidence records,20checkpoints,18positions; one expired legacy claim recovered
with no economic effects. Backup1817181bytes. F16/F17 integrated recovery Passed:
restored-owner RLS,pending receipt identity,exact retry and0duplicate exit/fill.
Source canonical data unchanged=True. Source/target cleanup0connections/0advisory
locks, candidate/runner unchanged. Evidence:nc12-section23-w4/.

W1§16,W2§20,overflow§20,shortW3§22 and W4§23 local campaign gates now all Passed in
their declared internal profiles. This is not the100-account/4h Release profile or
F17 Completed. Current recovery candidate still requires final review/required CI
and production-admission/opening-gate audit/authorization; original bot/notification/
Live dependencies remain. No Git/deploy/activation performed. See aggregate receipt.

Aggregate:[internal local campaign receipt](evidence/recovery-20261106/internal-pilot-local-checkpoint-20261107.md).

Recovery review Medium finding (NC12 test isolation): locally resolved2026-11-07.
207distinct cases have passing applicable evidence (206 in CI-compatible mixed run
+1 affected unit recheck); Ruff/format/mypy passed7files. Final remote CI pending.
[Fix and exact outcomes](evidence/recovery-20261106/review-fixture-fix.md).

Owner-authorized fixture refactor: affected mixed suite207/207passed together in
37.17s; Ruff/format/mypy passed changed conftest,0 fixture databases left. No
production/workload criterion change. Prior campaign proofs reused; remote CI and
other acceptance gates remain pending. Details in the same fix receipt.

Recovery candidate publication authorized after refactor. Main integrated; scoped
Ruff/format/mypy56files passed. Local secret probe flags evidence UUID/checksum
values; these are not approved exceptions and security acceptance remains blocked.
Required CI must be reported on the published SHA; no merge/completion claim.
[Publication checkpoint](evidence/recovery-20261106/publication-checkpoint.md).

Published0961f78 /PR59: required CI42362300917 **Failed** (4756passed/5failed;
later isolated backend steps Not Run); browser E2E and other5CIjobs passed. Security
42362300837 **Cancelled at15min**, no secrets manifest; aggregate gate Failed.
Additional test-config fixes have105passing targeted local cases, not remote CI.
[Exact result and next approval checkpoint](evidence/recovery-20261106/publication-final-ci.md).

Owner approved the exact100tree-occurrence extension. Local full secret scan and
strict registry validation Passed on6d021c4 in146.640s:0blocked/triage, exact48218
artifact identities. CI-fixture local fixes105passed remain prepared. Current-head
remote required CI still Pending; all F17 opening/Release/dependency gates retain
their actual status. [Checkpoint](evidence/recovery-20261106/tree-extension-local-checkpoint.md).

Published12e6204: Security Passed7/7, run42367203731. Application CI Failed on push
and PR:4759passed/2failed/31deselected in main backend suite; isolated later steps
Not Run. Other5jobs passed, including full E2E. Stop after third non-passing CI round
pending owner decision on [remaining fixture/config plan](remaining-ci-fixtures-plan.md).
[Evidence](evidence/recovery-20261106/extension-remote-ci-checkpoint.md).

Owner approved remaining CI fixture Option A. Exact two-line config/fixture change
implemented;51targeted cases passed in27.22s, workflow/static checks passed. Full
secret scan and the one authorized latest-candidate CI round still pending. No
assertion/production/criteria change. [Local checkpoint](evidence/recovery-20261106/remaining-ci-fixtures-local.md).

Remaining-fixture full pre-publication scan Passed on4d997e9 in132.892s with
0blocked/triage/unresolved, unchanged security configuration and no new exception.
Combined latest-head required CI now next; later isolated backend gates still
require actual success. Historical failed12e6204 CI is not relabelled.


## Merged recovery checkpoint — 2026-11-07

PR59 merged as `f15596df0b1ced53107964a8ed9bb657fda9d336` after owner instruction.
V-17 current-candidate CI blocker is closed: post-merge CI6/6 and Security7/7Passed;
backend4761main +95isolated cases passed. Candidate-to-merge tree diff is empty.
The [merged-candidate reconciliation](evidence/recovery-20261106/internal-pilot-local-checkpoint-20261107.md#merged-candidate-evidence-reconciliation--2026-11-07)
binds run URLs and retained local campaign evidence to its exact reuse boundary:
994W4-manifest entries checked,968same/26changed, plus later frontend helpers.
No historical failure was rewritten and no workload rerun occurred.

Internal D20/W1/amendedW2/overflow/shortW3/W4 remain Passed in their declared scope;
original100-account/4h obligations and V-19/V-20 dependencies remain Pending Full
Validation/Dependency. IP-V3 production-admission audit and IP-V9 internal opening
are not accepted by CI alone. F17 is not Completed. Step1 documentation reconciliation
is complete; step2 admission audit requires the owner's next instruction.


## Internal pilot step2 — 2026-11-07

Production Paper admission/risk source-and-CI audit Passed on f15596d: actual
TransactionalRiskPolicy at API/bridge/matching and6/6 risk-composition browser tests
on post-merge CI, alongside financial/retry/isolation regressions. See the
[step2 audit](evidence/recovery-20261106/internal-pilot-local-checkpoint-20261107.md#step2--paper-admissionrisk-integration-audit--2026-11-07).
This closes the IP-V3 code/CI integration audit, not target-environment activation
or IP-V9 opening. F16 V-18 is integration Passed / activation Pending. No source,
protocol flag, environment or requirement changed; no test/load rerun. Next step3
access preparation awaits owner instruction; Release/dependency gates remain pending.


## Compact protection table UI — 2026-11-08

Owner approved [UI plan/validation](protection-table-ui-plan.md). Implementation
checkpoint: [table evidence](evidence/manual-acceptance-fix/table-ui/checkpoint.md).
43component tests, typecheck/scoped lint and isolated light/dark bilingual browser
proof passed. Real-DB browser cases not rerun (Docker unavailable); owner local
startup and final UI review/required CI pending. No trading/Release pass invented.


## Unified order / TP-SL activity UI — 2026-11-08

Owner-approved [plan and Feature criteria](unified-trading-activity-ui-plan.md).
[Evidence](evidence/manual-acceptance-fix/unified-ui/checkpoint.md):52distinct
component/session/journal tests passed across affected checks;8isolated browser
scenarios passed, zero mutation requests/page errors; lint/types passed. No new
financial real-DB/owner acceptance claimed. Final UI review/required CI pending,
Batch/Release/dependencies unchanged. Local health200, all four gates off.


## Single-row activity UI — 2026-11-08

Owner-approved [plan/Feature validation](single-row-activity-ui-amendment.md).
[Checkpoint](evidence/manual-acceptance-fix/single-row-ui/checkpoint.md):56distinct
targeted component/session/journal cases,8isolated bilingual/theme/viewport browser
scenarios, final typecheck/scoped lint passed. One desktop toolbar row and one
mixed table verified; cross-symbol edit/create identity covered. No new economic
real-DB/owner acceptance claimed; required review/CI/Release gates remain pending.


## Review corrections after single-row UI — 2026-11-08

Review found High stale STOP receipt consuming a fresh click and Medium queued
exit quantity not displayed. Owner instructed fixes;
[checkpoint](evidence/manual-acceptance-fix/review-corrections/checkpoint.md) records
64affected passing tests, final lint/types and6synthetic browser cases. Prior
source manifests/results retained on their original candidates. Final source
awaits owner-authorized refactor and eventual required CI; Batch/Release/dependency
requirements remain pending, no Completed claim.


## Post-review refactor validation — 2026-11-08

Owner-authorized refactor complete; [checkpoint](evidence/manual-acceptance-fix/review-corrections/refactor-checkpoint.md).
64affected tests and6synthetic browser cases passed after refactor; lint/types
passed. Financial/server contracts unchanged; prior valid evidence retained in
scope. Required CI on final published SHA and Release/dependency gates pending.
No owner account campaign, trading activation or Git publication performed.


## Publication authorization — 2026-11-08

Owner answered “เริ่มทำ” to the explicit next commit/push/required-CI step.
Publish the reviewed/fixed/refactored F17 candidate on fix/f17-manual-acceptance
with related source, tests and existing evidence; no dependency links/private
operator state. Base e6b32bb equals origin/main at prepublication check. Required
CI results will be reported with exact SHA/run links after publication per AGENTS;
local proof is not substituted. Merge remains separately owner-authorized.
Release/dependency gates and historical failures remain unchanged.
