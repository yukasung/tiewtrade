# F-20 — ส่วนต่อประสานกลยุทธ์ + วงจรชีวิตบอท — Validation

สถานะ: **Approved — เจ้าของตอบ “approve” วันที่ 2026-11-19 หลังแก้ผล deep review**
วันที่: 2026-11-19 (Asia/Bangkok)
ฐานข้อกำหนด: requirements.md Approved 2026-11-19 รวม NC-F20-01..04

## 1. “เสร็จ” หมายถึง

ผลในแต่ละแถวอ้างหลักฐานจาก milestone ที่ตรวจแล้ว รายการที่ยังไม่ตรวจใช้ `Not Run`
Feature gates ต้องผ่านก่อน merge; Batch/Release ตาม checkpoint ไม่ถือว่าผ่านจาก mock
หรือการ merge ใช้ requirements เป็นเกณฑ์และไม่สร้างสูตรเทรด/งบ/SLA ใหม่ใน tests

| # | เกณฑ์ / RQ | ตรวจอย่างไร | ระยะรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | strategy/core บริสุทธิ์และ input/output deterministic; RQ-01/05 | purity/import gates และ repeated evaluation ของ fixture เดียวรวมเวลา/config/state; ตรวจ forbidden I/O/random/float และไม่ให้ strategy import infra/services/venues | Feature | Passed — purity/import และ deterministic/parity checks; [latest review evidence](evidence/implementation-checkpoint.md#implementation-fixes-and-deep-code-review--2026-11-19) |
| V-02 | versioned descriptor/config/state และ protection declaration; RQ-02/06 | exact serialization roundtrip, unknown schema/version, missing implementation และ config/state mismatch ต้องไม่ fallback; test registry ไม่อยู่ production registry | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-03 | input readiness/provenance; RQ-03/08/11 | incomplete indicator warm-up, gap/stale source, account unavailable และ mismatched revisions ต้องไม่มี intent; ไม่ใช้ศูนย์แทน; restore ต้อง reconcile/loss recheck ก่อน run | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-04 | pure lifecycle/intent/result separation; RQ-04/09/12 | transition table ทุก edge รวม invalid edges, STARTING ไม่ใช่ RUNNING, stop cause dominance, missing cause หยุด, no-op และ partial/rejected/unknown feedback ไม่สร้าง position จาก signal | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-05 | active slot และ flatness; RQ-07/08/14/17 | PostgreSQL 2 sessions เริ่มพร้อมกันคนละคู่ในโหมดเดียวได้ run เดียว Paper/Live โหมดละ 1 โดย Live ใช้ readiness test seam เท่านั้น ทดสอบ replacement แข่งกับ decision เดิม, fill และ stop ใหม่แยกกัน หาก fill มีผลก่อนและเกิด exposure หรือ stop revision เปลี่ยน ให้ปฏิเสธและคง stop/run เดิม หาก replacement commit ก่อน decision เก่าต้อง commit ไม่ได้ ตรวจว่า run เดิมไม่กลับ RUNNING และ fault ก่อน commit ไม่ทิ้ง stop หรือ slot ค้าง ปฏิเสธเมื่อมี position/order, pending intent หรือ activity unknown และคง resume run เดิมพร้อม exposure ตาม F-19 | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-06 | control idempotency/recovery; RQ-15/16/23 | ทิ้ง response แรกหลัง DB commit แล้วสร้าง client ใหม่โดยรู้เพียง key เดิม อ่าน receipt ผ่าน by-key ทั้งก่อนและหลัง API restart ตรวจว่าคำขอเดิมมีผลครั้งเดียวโดยเทียบจำนวน run/transition/audit เทียบกรณี duplicate start พร้อมกัน, payload ต่างแต่ key เดิมต้อง conflict, lookup ข้าม owner/mode ต้อง 404 และคำขอที่ถูกปฏิเสธต้องคืนผลเดิมเมื่อ retry | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-07 | atomic decision และ crash safety; RQ-16/19/24 | real-DB fault ก่อน commit/หลัง commit-ก่อน ack/ระหว่าง intent-state-audit, process kill และ DB disconnect; rollback ไม่เหลือ progress ลอย, commit สำเร็จกู้ intent เดิม, Redis loss ไม่ทำข้อมูลธุรกิจหาย | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-08 | fencing และ ordering; RQ-16/17/19 | duplicate/reordered input/feedback, stale source/run/claim revision และ two-engine takeover ด้วย barriers; stale worker commit ไม่ได้ ไม่มี duplicate intent/fill/state regression หรือ financial side effect ของอีก owner | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-09 | bot-origin shared admission; RQ-08/18 | ผ่าน Paper dispatch/matcher จริง ตรวจ BOT, current run/config, funds/reservations, filters, catalog, price/account readiness และ risk/latch; forged BOT intent ไม่มี decision link ต้อง reject; manual BUY/SELL/reduction/cancel เดิมไม่เปลี่ยน ไม่มี direct executor bypass | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-10 | F-18/F-19 races และ resume; RQ-10..12/17 | run/decision/admission แข่ง user/platform stop, loss hit/reset และ account-use change; หลัง cutoff ไม่มี opening ใหม่ BOT ไม่กลาย MANUAL, loss reset ไม่ปลด cause อื่น, pause/restart ไม่ล้าง stop; summary stale/cross-mode/new cause ต้อง resume ไม่ได้ คง cleanup 3 สถานะ | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-11 | strategy failure/proof; RQ-06/13/20 | throw, invalid output, missing version/corrupt state หยุดเฉพาะ run ไม่มี partial output/auto retry; snapshot position/protection ก่อนหลังเท่ากันตาม abnormal-stop policy; wrong cause/run/stop generation/config/state proof reject, acknowledgement อย่างเดียวไม่พอ, valid proof+summary+reconciliation+owner acknowledgement จึง resume | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-12 | F-37 withdrawal consumer; RQ-17/21 | ถอนคู่ที่มี run จากอย่างน้อยสอง owner และ run ในอีกโหมดผ่าน isolated seam ทุก run ที่ผูกกับคู่และ withdrawal revision ต้องหยุด ส่วน control run ของคู่อื่นทำงานต่อ ตรวจ admission race ว่าไม่มี opening หลัง removal และคง exposure/TP-SL เดิม หลัง restart, duplicate delivery และ add-back ต้องไม่มีผลซ้ำหรือปลุก run เดิม และ replay event เก่าต้องไม่หยุด run ที่เริ่มอย่างถูกต้องใน revision ใหม่ effect ยังค้างหาก notification/cleanup ยังไม่เสร็จ | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-13 | execution feedback/protection; RQ-04/19/22 | Paper execution จริงของ test strategy ทั้ง rejected/partial/filled/cancel/unknown; feedback identity ถูก order, fill ไม่ซ้ำ, ledger/reservation/position ตรง; protection ขยายตาม filled size และ bot protection failure ใช้ F-17 policy ไม่ถูก policy abnormal stop กลบ | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-14 | API/RLS/mode/security; RQ-15/23/24 | route/body mode mismatch, wrong owner IDs, expired session/CSRF, repeat GET/POST, DB grants และ ENGINE_SCAN read-only; no secret/raw exception; API update run/order โดยตรงไม่ได้ Live unavailable ไม่เปิด capability | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-15 | UI/control/owner acceptance; RQ-09/13/25 | component + isolated browser ใช้สถานะจริงจาก test app; Paper/Live แยกชัด, request pending ต่างจาก running, pause/reason/exposure/protection/stop summary ครบ, start ปกติ disabled เมื่อ F-21/activation ไม่พร้อม; stop/SELL/TP-SL ยังใช้ได้ ผู้ใช้ตรวจรับภาพ/flow ก่อน merge | Feature | Passed - component/actual-API browser and owner UI acceptance 2026-11-20; [acceptance evidence](evidence/implementation-checkpoint.md#owner-ui-acceptance-and-publication---2026-11-20) |
| V-16 | UI scope/recovery/template; RQ-16/23/25 | logout/user/mode/episode/run change และ late response ไม่รั่วข้าม scope หลัง lost ack และ reload ให้ journal คืน key ของ scope ปัจจุบันเพื่ออ่าน receipt เดิมจาก by-key แม้ยังไม่มี request ID ตรวจไทย/อังกฤษ light/dark keyboard/focus และ 375/768/1280/1440px ใช้ template/shared controls และอ่านสถานะธุรกิจจาก server | Feature | Passed - approved scenarios mapped to retained and new targeted evidence; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-17 | migration/privileges; RQ-15/17/23/24 | real PostgreSQL empty upgrade/downgrade/upgrade, populated downgrade refusal และ integrity หลัง refuse; owner/mode FK, unique slot, append-only audit/events, RLS/grants, restart/rolling compatibility และ no activation by migration | Feature | Passed - additive/legacy-shaped facts, migrations/grants and restart/takeover under closed F-20 rollout; enabled production rolling campaign not claimed; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-18 | parity/isolation และ final candidate gates; RQ-05/26/27 | fixture inputs/results เดียวกันผ่าน shared domain Paper/Live ได้ decision/state เท่ากัน; Paper ไม่แตะ Live venue/credential; affected regression, lint/type/import/build/OpenAPI, review/fixes และ required CI บน final SHA; ไม่ส่ง Live order | Feature | Partial - local parity/isolation/static/build/OpenAPI/review passed; **final-SHA required CI Not Run**; [scenario matrix](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20) |
| V-19 | รวม regression ชุดที่ 6; RQ-27 | full backend/frontend regression และ cross-feature integration ของ bot กับ account, risk, stop, catalog, protection บน candidate รวมที่นิ่ง รวม full regression ก่อน merge หากเข้าเงื่อนไข testing §7 | Batch | Not Run — Pending Full Validation; checkpoint ท้ายชุดที่ 6 |
| V-20 | กลยุทธ์จริง F-21 + F-20 UI/engine end-to-end; RQ-02/08/25/27 | ตาม approved F-21 rules/config/trigger ใช้ Paper จริง เริ่ม→input→decision→admission→fill→protection→pause/stop/restart/resume; ตรวจงบ/ขนาดไม้ด้วย oracle ของ F-21; ไม่อ้าง test strategy ผ่านแทน | Batch | Not Run — Pending F-21; checkpoint ท้ายชุดที่ 6 |
| V-21 | integrated release/dependencies; RQ-13/21/27 | F-17/F-18/F-19/F-37 integration receipts และ notification channels ตาม feature เจ้าของ, F-22/F-23 reconciliation/Live isolation และ F-24 activation gates ตาม approved validation; workload/endurance/resource ใช้ profile/เกณฑ์ที่อนุมัติของระบบรวม ไม่เปิด Live ด้วย F-20 และไม่ส่ง Live order ใน automated tests | Release | Not Run — Pending Full Validation/Dependencies; checkpoint ชุดที่ 9/ก่อน activation |

## 2. การเลือกตรวจตามผลกระทบ

| ผลกระทบ | ใช้ของเดิมก่อน / หลักฐานเพิ่ม |
|---|---|
| Pure contracts/state | tests core orders/trading_stops และ purity gates; เพิ่ม transition/version/dedup cases ที่เป็นของ F-20 |
| Financial admission | tests manual trading/orders/risk/protections และ Paper real-DB fixtures เดิม; เพิ่ม BOT authority ไม่คัดลอก financial oracle จาก implementation |
| Multi-instance/transactions | claims/RLS/stop/migration tests เดิม; เพิ่ม barriers, crash windows และ process boundary ที่ขาด Mock ใช้แทน DB locks ไม่ได้ |
| UI/OpenAPI | PaperBotPanel/KillSwitchControls และ isolated app patterns เดิม; เพิ่ม bot states/recovery/scope tests ไม่ย้ายการตรวจ server ไป browser |
| Integrated strategy/Live | รอ F-21/F-22/F-23/F-24; ผล fixture ไม่ปิด dependency และไม่ลด Feature safety gates |

ทุก checkpoint บันทึก commands/environment/revision/working diff, passed/failed counts,
RQ/V ที่ครอบคลุม และข้อจำกัดใน `evidence/implementation-checkpoint.md` ไฟล์เดียวต่อเนื่อง
ผลเดิมใช้ต่อได้เมื่อ contracts/schema/config/harness/dependencies ที่พิสูจน์ไม่เปลี่ยน
หลังแก้รันเฉพาะ failure และ affected regression ไม่ทำ full validation ซ้ำทุก patch

## 3. ตัวเลขและ property tests

- ใช้ Money/Quantity fixtures และอัตรา fee/matching/protection จาก F-14/F-15/F-17 เดิม
  ไม่สร้าง Grid sizing หรือแปลงเงินผ่าน float ตรวจค่าคาดหมายจาก oracle เดิม/การคำนวณอิสระ
- Properties: replay input ไม่เพิ่ม intents, intent เดิมไม่เพิ่ม fill ซ้ำ, feedback เก่าไม่ย้อน
  revision, stop cause เพิ่มแล้ว resume ของ cause อื่นไม่ล้างมัน และ active slot ไม่เกินโหมดละ 1
- Parity ใส่ inputs/time/config/state และ execution feedback เดียวกัน ต้องได้ outputs/state
  ตรงกัน ไม่เปรียบเทียบกำไรจำลองกับกำไร Live หรือรับรองผล fill จริงเท่ากัน
- Fault assertions ต้องตรวจ durable receipts, run state, orders, ledger, reservations และ
  positions พร้อมกัน ไม่ใช้เพียง HTTP status หรือไม่มี exception เป็นหลักฐานการเงินถูกต้อง

## 4. ตรวจด้วยมือและข้อจำกัดการเปิดใช้งาน

ผู้ใช้ตรวจรับแผงเดิมทั้ง Paper/Live, unavailable/start-disabled, pending/running/paused,
เหตุหยุดและ exposure, summary ก่อน resume, keyboard และ mobile บน isolated fixtures
ไม่มีการส่ง order จริง การกด stop ไม่ต้องรอ strategy พร้อม และไม่ทำให้ SELL/protection หาย
การตรวจรับนี้เป็น Feature gate ก่อน merge ไม่แทน end-to-end กลยุทธ์จริงของ V-20

ขณะ F-21 ยังไม่พร้อม ไม่ปลด disabled ของ start ปกติ ไม่เพิ่ม production test strategy
ไม่ใช้ UI seed/mock เป็นหลักฐานว่าระบบเปิดใช้บอทจริงได้ และไม่เปิด Live หรือเปลี่ยนบัญชี BOT
ให้ผู้ใช้เอง การเปิดกลับ SYSTEM cause อื่นที่ไม่มี proof contract คงปฏิเสธ

## 5. ด่านและลำดับตรวจ

1. ระหว่าง M1–M4: targeted tests/static checks ที่เล็กที่สุดตามแผนและตารางผลกระทบ
2. เมื่อ implementation ครบ: แจ้ง Ready for Code Review แล้ว review diff/callers → แก้
   findings → refactor เฉพาะที่มีประโยชน์ → ตรวจ findings/new diff/regression ที่เกี่ยวข้อง
3. ก่อน merge: V-01..18 ผ่าน, owner UI acceptance, required CI บน final candidate SHA
   และเงื่อนไข Git ตาม AGENTS.md; full regression ก่อน merge เมื่อเข้าเกณฑ์ testing §7
4. ท้ายชุดที่ 6: V-19/20 รวม F-21 เมื่อพร้อม ไม่สร้าง timed smoke/workload ท้าย milestone
5. Release/ชุดที่ 9: V-21 และเกณฑ์ค้าง ใช้ profile/threshold/duration ที่อนุมัติแล้ว
   รายการที่ยังไม่มี profile หรือ dependency คง Pending ไม่คิดค่าหรือรัน campaign เอง

ก่อน full regression/cross-feature E2E/workload ให้แจ้งขอบเขต สิ่งที่พิสูจน์และเวลาโดยประมาณ
ตั้งงบรอบตรวจรวม 1–2 ชั่วโมงตาม testing §7 ใช้เป็นงบวางแผนไม่ใช่เกณฑ์ตัดผ่าน
หากคาดเกิน 2 ชั่วโมงแจ้งเหตุผลก่อนเริ่ม ไม่ลด coverage/ระยะต่อเนื่องให้ลงเวลา
เมื่อแก้และตรวจเกณฑ์เดิมยังไม่ผ่าน 3 รอบ หรือเจ้าของแจ้งว่าใช้เวลามากเกินไป ให้หยุดเสนอ
ทางเลือกก่อนทดลองรอบต่อไป คง Failed/Partial/Incomplete เดิมตามจริง

เจ้าของอนุมัติ plan/validation ฉบับหลังรีวิววันที่ 2026-11-19 บันทึกผลตรวจตามหลักฐานของแต่ละ milestone

## Code review checkpoint — 2026-11-19

ผล **CHANGES REQUIRED**: CR-F20-01/02 High และ CR-F20-03/04 Medium ยังเปิดอยู่
ดูรายละเอียด file/location, impact, recommended fix, coverage และผลตรวจจริงใน
[evidence เดิม](evidence/implementation-checkpoint.md#implementation-fixes-and-deep-code-review--2026-11-19)
ยังไม่ Ready for Code Review ทั้ง feature และไม่พร้อม merge; แก้ scoped engineering findings
ต่อได้ตามอำนาจเดิมโดยไม่ขออนุมัติ requirements/plan ซ้ำ คง owner acceptance/required CI
และ Batch/Release gates ตามเดิม ไม่ถือว่า targeted tests ผ่านแทนทั้งหมด

### Review correction checkpoint — 2026-11-20

สถานะ findings ข้างต้นเป็นประวัติ: แก้ indicator assembly, durable fair scheduling,
bounded status และเติม process/connection faults, stop/replacement/fill/loss-reset
races พร้อม reordered feedback แล้ว รวม guard สำหรับ corrupt state ใน duplicate
recovery และ catalog/SYSTEM proof หลัง add-back ที่พบใน review ต่อมา
[หลักฐานและผลตรวจล่าสุด](evidence/implementation-checkpoint.md#review-corrections-verified--2026-11-20)
บันทึกกรณีผ่าน ผลล้มเดิม และขอบเขต review ซ้ำไว้ครบ

Indicator safety tests เดิมผ่าน 3 กรณีในรอบเพิ่มหนึ่งรอบที่เจ้าของอนุมัติหลังแก้ CAST
คง warm-up/source assertions เดิม ไม่รันทดลอง indicator เพิ่มหลังรอบนี้
V-03/05/07/08/10/11/13/17 มีหลักฐานเพิ่ม แต่คง aggregate Partial จนผูกทุก scenario
กับผลตรวจครบ; V-15/16 browser/owner acceptance และ V-18 required CI ยังไม่ผ่านครบ
ผล local review ไม่พบ finding ใหม่ใน correction diff; ยังไม่ใช่การอนุมัติ merge
หรือ Completed และ V-19..21 ยังคง Pending Full Validation/Dependencies ตามเดิม

### Recovery/readiness review corrections — 2026-11-20

ปิด findings รอบถัดมา 2 High/1 Medium: probe ต้อง evaluate จริงและพิสูจน์ failed
feedback เดิม, PAUSED ต้อง reconcile ก่อนพร้อม และ STARTING ต้อง pause/reason เมื่อ
readiness หาย รวม immutable status snapshot หลัง partial→cancel และไม่ออก proof
ให้ legacy failure ที่ขาด input context; [หลักฐานล่าสุด](evidence/implementation-checkpoint.md#recovery-and-readiness-fixes--2026-11-20)
มี 12 new real-DB cases ผ่านร่วมกับ affected regressions/static checks ตามที่บันทึก
เพิ่ม coverage ให้ V-03/08/11 ไม่เปลี่ยน aggregate Partial หรือเกณฑ์ตรวจรับเดิม
รอบแก้ findings นี้ review แล้วไม่มี code finding ค้างใน scope; owner acceptance,
required CI และ Batch/Release dependencies ยังคงเป็นด่านแยก ไม่ถือว่าผ่านโดยอัตโนมัติ

Scoped refactor ตามคำสั่งเจ้าของ: รวม test setup SQL ที่ซ้ำและปรับ branch ให้อ่านชัด
โดยคง behavior/transaction/assertions เดิม; targeted PostgreSQL group 15 passed
พร้อม Ruff/mypy/import checks ดู [หลักฐาน](evidence/implementation-checkpoint.md#scoped-recoveryreadiness-refactor--2026-11-20)
ไม่เปลี่ยนเกณฑ์หรือ aggregate validation status ของ feature

### Feature acceptance checkpoint - 2026-11-20

Ready for Code Review announced; closure diff/callers reviewed with no new code
finding. [Scenario matrix and retained failure history](evidence/implementation-checkpoint.md#feature-validation-closure-and-owner-ui-checkpoint--2026-11-20)
map the Feature criteria individually. V-15 remains Partial for explicit owner UI
acceptance; V-18 remains Partial for required CI on final SHA. V-17 covers the
closed F-20 rollout, additive/legacy-shaped data and restart/takeover,
not an enabled production mixed-version campaign. Activation remains outside
F-20. V-19..21 retain Pending Full Validation/Dependencies; no full regression,
Live order or further indicator campaign was run.

Next: owner reviews concrete UI artifacts, then publication/required CI may
proceed under existing Git authorization. Do not mark merge-ready or Completed
before the applicable gates pass.

Owner accepted the presented UI/flow set on 2026-11-20. V-15 is now Passed;
previous pending entries remain historical. Next: scoped publication and required
CI on final SHA, then conditional merge/post-merge CI under standing authorization.
V-18 is pending until the actual remote run passes; Batch/Release remain pending.
