# F-19 — ปุ่มหยุดบอท (Kill Switch) — Validation

สถานะ: **Approved 2026-10-31** — รวม deep-review fixes และ dependency gates V-21..24
วันที่: 2026-10-31

## 1. “เสร็จ” หมายถึง

| รหัส | เกณฑ์ | ตรวจอย่างไร | Checkpoint | ผล/หลักฐาน |
|---|---|---|---|---|
| V-01 | RQ-02/03/18/19: scope และ cause precedence | pure table tests ทุก USER/SYSTEM/LOSS/PLATFORM × Paper/Live × MANUAL/BOT × opening/reduction/cancel; Paper stopไม่แตะLiveและกลับกัน; active causeหนึ่งไม่ถูก resumeของอีกcauseล้าง | M1 | **Passed (local)** — policy matrix + mode-isolated API/storage tests; 2026-10-31 |
| V-02 | RQ-12/14: progress/restart | property tests counts/completeness: STOPPED เฉพาะ discoveryครบและทุกtargetรู้ผล, PROBLEMSเก็บfailed list, restart/duplicate/reordered factsให้projectionเดิม, missing cause fail-closed | M1/M3 | **Passed (local)** — progress matrix, reordered projection, child completeness และ retry tests |
| V-03 | RQ-06/15: resume CAS/proof | stale stop/summary/reconciliation revision, stopใหม่ระหว่างเปิดmodalกับsubmit, exact retry, MANUAL account, unreconciled, unresolved cause proof, active platform/loss cause; เปิดได้เฉพาะ expected cause และไม่ต้อง TOTP | M1/M2/M3 | **Passed (local)** — owner/platform exact-snapshot resume integration + stale proof tests |
| V-04 | RQ-11/16/17: DB isolation/immutability | real PostgreSQL roles/RLS/FK/CHECK/append-only; cross-owner/mode uniform404; APIเขียนได้เฉพาะ immutable inbox+request audit และแก้ result/projection/effectsไม่ได้; STOP inbox commitเป็นfenceก่อน202; audit/commit failureไม่ตอบsuccess; secret/rawreasonไม่เข้าlog | M2 | **Passed (local)** — real-role/RLS/append-only, cross-owner/mode 404, projection write denial, real audit rollback+same-key retry และ error/log hygiene ผ่าน |
| V-05 | RQ-07/08/11: idempotency, repeated stop และ unknown commit | same key+same payloadคืน generationเดิม, same keyต่างpayload conflict, concurrent/lost response/by-key recoveryใช้ keyเดิม; keyใหม่ระหว่าง USER cause activeสร้าง generation/cutoffใหม่; stop/resume retryไม่สร้าง intent/event/audit effectซ้ำและ stale retryไม่ปลดstopใหม่ | M2/M3 | **Passed (local)** — conflict/new generation/concurrent replay และ browser lost-ack key recovery ผ่าน |
| V-06 | RQ-05/06/16: platform authority | Admin/Owner stopได้, userปฏิเสธ, Ownerเท่านั้นresume; global fence durableก่อน202; reason1/500ผ่าน blank/501ปฏิเสธ; admin resume/user forged role ปฏิเสธ; audit actor/reason code+stop referenceถูกต้องและ user-facing reasonอ่านจาก stop view | M2 | **Passed (local)** — Owner/Admin browser flow, role checks, reason validation/escaping และ audit integration ผ่าน |
| V-07 | schema/rolling upgrade และ writer authority | up→down→up empty; downgrade guard เมื่อมีhistory; backfill F-18 loss stopsคงIDs/effects/views; API roleเขียน projection/resultไม่ได้; old writerที่ไม่ถือ global/owner locks และไม่ตรวจ historical revisions ถูกgateก่อนauthority activation; migrationไม่สร้าง/ล้างstopเอง | M2/candidate | **Passed (local)** — empty round-trip, history guard, latched/unlatched F-18 backfill และ rollout gate ผ่าน |
| V-08 | API/routing/contracts | auth/CSRF/throttle/safe typed errors/extra fields/forgedowner-mode; GETไม่renewsession; OpenAPI/clientตรง; Live routeไม่แตะPaper; route policyครบ; no secret/raw SQL | M2/M4 | **Passed (local)** — API/routing tests 21, generated OpenAPI/client และ mode isolation ผ่าน |
| V-09 | RQ-04/07: user Paper effects | real F-16/F-15 lifecycle: queued-unsent manual+bot ก่อน/เท่ากับcutoff terminalเพราะstop; sent/unknownไม่ถูกเขียนทับและreconcile; active manual+bot remainder cancel; terminal historyคงเดิม; หลังcutoff MANUALผ่านgatesเดิมและ BOTปฏิเสธ; positionไม่ถูกแตะ; protective targetถูกคัดออกตาม contract โดย real TP/SL รอ V-21 | M3 | **Passed (local contract)** — affected Paper lifecycle/worker regression ผ่าน; real TP/SL คง V-21 |
| V-10 | RQ-05/09: platform Paper effects | queued-unsent manual+bot terminalเพราะplatform stop; active bot remainder cancel; sent/active manual orderคงอยู่; request workerและmatching workerใช้ shared eligibility เดียวกันและไม่ยกเลิก manual; fill/partial raceบันทึกจริง; global aggregateไม่STOPPEDก่อนowner inventory+child jobsครบ | M3 | **Passed (local contract)** — real BOT_ONLY child cancel/release active BOT แต่คง sent MANUAL; shared fill/cancel lifecycle และ child completeness regression ผ่าน |
| V-11 | RQ-07/08: concurrency ordering | real PostgreSQL barriers พิสูจน์ lock order `global shared → owner → pair` กับ platform exclusive lock: submit-vs-stopทั้งก่อน/หลังcommit, stop→resumeก่อนworker, repeated stop, reset-vs-stop, cancel-vs-fill, two workers/lease takeover; executionตรวจ historical revisions ทำให้ pre-stop intentไม่ฟื้นหลังresume; ไม่มี duplicate fill/cancel/release | M3 | **Passed (local targeted)** — platform/shared admission + targeted concurrency/lease/historical 14/14, reset-vs-stop ทั้งสอง commit orders × BUY/SELL 4/4 และ fresh cancel-vs-fill owner-claim matrix 2/2 ผ่าน; committed STOP historical fence ชนะโดยไม่มี duplicate money/position/cancel/release |
| V-12 | RQ-08..10/13/17: fault/recovery | kill/connection loss ก่อน/หลัง stop/cancel/resume commit, DB/Redis/audit failure, worker restart; unknown order queryต่อ, unfilled eligible cancel, filledบันทึกจริง, protective continuation contractไม่ถูกstop policyบล็อก, retry backoff, ครบ1นาที alertแต่ยังretry; real TP/SL behaviorรอ V-21 | M3; fault durationเฉพาะเกณฑ์1นาที | **Passed (local targeted)** — lost-ack/audit/restart recovery, fresh STOP/RESUME atomic outcome rollback+restart และ cancel before/after-commit matrix 3/3 ผ่าน; FAILED→backoff→1-minute alert→retry โดย target ไม่ซ้ำผ่าน; real TP/SL คง V-21 |
| V-13 | RQ-18/19: F-18 integration | loss breachสร้างshared cause+effectsเดิม; loss resetไม่เปิดbot, user/platform resumeไม่ล้างlatch; resetแล้ว cause-specific proof+summaryจึงresumeได้; price pause recoveryไม่ปลด durable stop | M3 | **Passed (local)** — F-18 monitor/stop integration และ admission fail-closed หลัง breach ผ่าน |
| V-14 | fairness/resource bounds | bounded scan/page/claim, ownerหนึ่งlock/failureไม่starveคนอื่น, platform discovery restartจากcursor, effects pagination >100 targets stable watermark/no duplicate/scan planใช้index | M3; full scale V-20 | **Passed (local targeted)** — 105-target stable watermark/no duplicate, composite stop-sequence index plan, bounded limits, cursor rounds และ locked-owner fairness ผ่าน; workload scale คง V-20 |
| V-15 | RQ-01/02/12/20: ปุ่มทุกหน้าและ repeated stop | component+browser ทุก account page desktop/mobile: Paper/Live buttonsเห็นพร้อมกัน, label/modeชัด, stopส่งในclickเดียว, อีกmodeไม่เปลี่ยน; stop→MANUAL orderหลังcutoff→stop keyใหม่สร้าง generationใหม่; detailsเป็นcontrolแยก; UNKNOWN retryใช้ keyเดิม; states/countsไม่กล่าวsuccessก่อนจริง | M4 | **Passed (local browser)** — controls ครบทุก account page desktop/mobile; clean expanded owner E2E ผ่าน UNKNOWN replay→MANUAL FILLED หลัง cutoff→key/request/generation ใหม่→nonempty summary และ Paper/Live isolation |
| V-16 | RQ-15/20: summary/resume UI | positions+canceled+failed+pending+reconciled timeแสดงจากsnapshotเดียว; stale update disable/refresh; focus trap/return focus/keyboard/live region; exact retry recovery; light/dark ไทย/อังกฤษ | M4 | **Passed (local targeted)** — component PROBLEMS snapshot แสดง position/FAILED/CANCELED/PENDING/reconciled time; stale rejection refetch แล้ว disable resume; browser exact retry, focus/Escape, light/dark และไทย/อังกฤษผ่าน |
| V-17 | RQ-05/06/20: platform UI/banner | Admin/Owner reason+stop, Owner resume, Admin disabled resume, userไม่มีหน้า; persistent bannerทุกหน้าแสดงreason/source; responsive/template states และ free-text escaped ไม่เป็นHTML | M4 | **Passed (local browser)** — Owner/Admin stop/resume rights, ordinary-user isolation, escaped reason และ persistent banner พร้อม separate Paper/Live controls ผ่านครบ 10 account routes ทั้ง desktop/mobile |
| V-18 | RQ-21/NC-F19-03: capability isolation | Liveแสดงunavailable/pendingโดยไม่ส่งorderและคง `target_set_complete=false`/`resume_ready=false` แม้ capabilityปิดหรือ queryได้ศูนย์; Paper browser→API→engine→DB/effectsจริง; bot/notification adapters fail-closedเมื่อdependencyไม่มี; ไม่มี production activation จาก feature flag/client payload | M4 | **Passed (current capability)** — browser→API→engine→DB; Live incomplete และ DB ยืนยันไม่มี order request |
| V-19 | candidate gates | review diff/dependencies Critical/High, affected backend/frontend regression, ruff+format, mypy, lint-imports, frontend lint/types/build, generated OpenAPI diff และ required CI บน candidate สุดท้าย | M5 ก่อน merge | **Passed — merged `ccc3ce1` (2026-11-01)** — review findings 2 High/1 Medium แก้แล้วพร้อม refactor; local backend4056/frontend343/browser2 และ affected rechecks ผ่านตาม [evidence](evidence/implementation-checkpoint.md); final candidate `de25852` ผ่าน required [push CI](https://github.com/yukasung/tiewtrade/actions/runs/41305111782)/[PR CI](https://github.com/yukasung/tiewtrade/actions/runs/41305117314) ครบ 6/6 jobs ต่อ run; [PR #41](https://github.com/yukasung/tiewtrade/pull/41) merge เป็น `ccc3ce1` และ [post-merge CI](https://github.com/yukasung/tiewtrade/actions/runs/41306706760) ผ่านครบ 6/6 รวม backend4056/browser33; generated contracts/static gates ผ่าน; V-20..24 ยัง pending ตาม scope เดิม |
| V-20 | ท้ายชุดที่5 Paper integration/full validation | candidate รวม F-18/F-19 ที่นิ่งผ่าน full backend/frontend regression, browser→API→engine, fault/recovery, backup/restore และ W1–W4 ที่เกี่ยวข้องโดยคง F-18 thresholds/profileเดิม; stop oraclesด้านล่างครบ | ท้ายชุดที่5 | **Failed — Set5 W1 r1 (2026-11-01)**; Pending Full Validation ตาม [execution checkpoint](evidence/implementation-checkpoint.md); W2/W3/W4 รอบ Set5 ยัง Not Run |
| V-21 | real protective TP/SL integration | หลัง F-17 มี protective orders จริง ตรวจ user/platform stopไม่เลือก TP/SL, fill/partial fillยังสร้าง/ซ่อม protection ตาม policyที่อนุมัติ และไม่สร้าง protection ที่ไม่ได้ขอ | หลัง F-17/ชุด5 | Pending Dependency |
| V-22 | real bot lifecycle | F-20 botจริงหยุด/ไม่ตื่นเอง/resumeตามcauseและ account use; queued signalsไม่กลายเป็นorderหลังfence | หลัง F-20 | Pending Dependency |
| V-23 | real Live authority/execution | F-22/F-23/F-24 ตรวจ durable activation inventory, fence/reconciliation/unknown/cancel/protection ด้วย environment ที่อนุมัติ ห้าม automated Live order | ชุด7/ชุด9 | Pending Dependency |
| V-24 | notification channels | F-26/F-36/F-27 ส่ง platform stop, late fill, cancel >1นาที และ abnormal stop ทุกช่องทางที่ผู้ใช้เปิด พร้อม dedup/retry | ชุด8/ชุด9 | Pending Dependency |

## 2. การเลือกตรวจตามผลกระทบ

- pure policy ใช้ table/property tests เพราะพิสูจน์ cause matrix และ invariants ได้เร็ว
- cutoff, locks, roles, RLS, idempotency, migration และ concurrency ใช้ PostgreSQL จริง;
  mock ไม่พิสูจน์ transaction ordering หรือ privilege boundary
- Paper effects ใช้ F-15/F-16 facts และ F-18 consumer จริง ไม่สร้าง fake order state เป็น oracle
- frontend ใช้ component tests สำหรับ state/a11y และ browser smoke สำหรับทุกหน้า,
  responsive, focus, computed style และ end-to-end one-click behavior
- ใช้ผล F-18/F-16 ที่ยัง valid ต่อ แต่การขยาย stop authority/writer fence ทำให้ผลด้าน
  admission, stop consumer, routing, schema/roles และ UI composition ต้องตรวจใหม่
- ไม่รัน workload/endurance/timed smoke ระหว่าง milestone เว้น targeted tests พิสูจน์
  ordering/fairness ไม่พอและแจ้งเหตุผล/เวลาไว้ก่อนตาม testing §7

## 3. Oracles สำคัญ

1. **Cutoff/lifecycle:** ทุก opening intent มี durable order เทียบกับ stop cutoff ได้หนึ่งคำตอบเสมอ;
   queued-unsent ก่อน/เท่ากับ cutoff terminalize เพราะ stop, sent/unknown ตามผลจริง, active remainder
   ใช้ user/platform eligibility และ terminal historyไม่เปลี่ยน; หลัง user cutoff เฉพาะ MANUAL ผ่าน
   gates เดิม และ stop ที่เกิดหลัง admission ยังบล็อก execution แม้ resume ก่อน worker
2. **No cross-mode:** Paper event/effect IDs ไม่ปรากฏใน Live queries และกลับกัน
3. **No unintended release:** resume event เปลี่ยน active cause ได้สูงสุดหนึ่ง identity/revision;
   causes/latches อื่นและ stop ครั้งใหม่เหมือนเดิม
4. **No unsafe cancellation:** user stop targets manual+bot; platform targets bot sent ordersเท่านั้น;
   TP/SL/position ไม่เป็น cancellation target
5. **Truthful progress:** `target_count = terminal + pending`; STOPPED ต้อง discovery complete,
   pending=0, failed=0; PROBLEMS แสดง failed จริง; empty page ไม่แปลว่า complete
6. **Idempotency:** retries ไม่เพิ่ม stop/resume/cancel/fill/reservation release/audit outcome ซ้ำ
7. **Fail closed:** authority/revision/proof อ่านไม่ได้บล็อก opening/resume แต่ reduction/cancel
   ยังใช้ durable-intent exception ของ NC-F16-01 และไม่อ้าง success เมื่อ DB commit ไม่ได้
8. **Repeated stop:** retry keyเดิมไม่เปลี่ยน cutoff; keyใหม่สร้าง generation/cutoffใหม่และจับ
   MANUAL orders ที่เกิดหลัง generationก่อน โดยไม่เขียนทับ history/effects เดิม

## 4. ตรวจด้วยมือและ visual QA

บน candidate ที่ targeted checks ผ่านแล้ว:

1. เปิดทุกหน้าบน desktop และ mobile ยืนยันว่าปุ่ม Paper/Live เห็นพร้อมกันและ mode ชัด
2. กด Paper stop ตรวจว่า Live state ไม่เปลี่ยนและเห็น progress/effects จริง จากนั้นสร้าง MANUAL
   order หลัง cutoff แล้วกด Paper stop อีกครั้ง ต้องได้ generation ใหม่; “ดูรายละเอียด” แยกจากปุ่มหยุด
3. เปิด summary หลัง STOPPED และ PROBLEMS ตรวจ position/canceled/failed/reconcile time
   จากนั้นทำ snapshot stale ก่อน resume ต้องถูกปฏิเสธและโหลดข้อมูลใหม่
4. เข้าด้วย Admin/Owner ตรวจ platform reason/banner/สิทธิ์ resume และ user ทั่วไปไม่มี control
5. สลับไทย/อังกฤษ light/dark และ keyboard-only ตรวจ focus/announcement/contrast/responsive
6. Live แสดง Pending Dependency โดยไม่มี order/venue mutation และไม่ใช้เงินจริงทดสอบ

บันทึก screenshot หรือ browser evidence เฉพาะ state ที่พิสูจน์ interaction/layout ไม่ใช้ภาพแทน
server/audit/order oracle

## 5. Full validation ท้ายชุดที่ 5

ใช้ candidate รวมและ environment ของ F-18 `F18_F15_F16_INTEGRATED_V2` ที่ยัง valid
โดยไม่ลด 100 owners ×20 orders, W1 600s/W2 300s/W3 1800s, command/book/price rates,
Paper risk 99.9%≤3s และทุก ready input≤5s, F-15 latency/resource/financial thresholds
หรือ W4 backup/restore criteria

เพิ่ม deterministic stop schedule ใน harness โดยคง workload เดิม:

- W1: user Paper stops ก่อน/ระหว่าง queued+partial orders, MANUAL post-cutoff และ resume
  หลัง complete summary/reconciliation รวม stop→MANUAL post-cutoff→stop generationใหม่;
  ตรวจ scope/cutoff/history/financial digest
- W2: concurrent stops หลาย owner, duplicate/lost-ack/resume conflict และ bounded fairness;
  ไม่ใช้ stop phase ลบ miss ของ workload เดิมออกจาก denominator
- W3: worker/DB/Redis fault ระหว่าง discovery/cancel/resume, platform fence phase และ recovery;
  matching workerต้องคง manual sent order ระหว่าง platform stop; alert 1นาทีต้องเกิดตามเวลาจริง
  และ retryต่อหลัง alert
- W4: restore active user/system/platform causes, cursors, effects, idempotency receipts และ audit;
  canonical order/financial/stop digest เท่าก่อน backup ไม่มี duplicate effect

platform stop phase แยก measurement window ที่ตั้งใจบล็อก opening ออกจาก non-fault throughput
แต่ยังเก็บผล blocked commands เป็น positive oracle ห้ามจัด failure เป็น expected โดยไม่มี schedule marker

### V-20 workload schedule amendment — Approved 2026-10-31

- คง core workload เดิม 100 owners ×20 baseline orders, offered schedule, W1–W3 duration/rates
  และ thresholds ทุกข้อ; เพิ่ม dedicated stop owners แยกจาก counters ของ core workloadได้ แต่ต้องรวม
  ใน stop discovery/fairness/resource/connection oracles และห้ามใช้แทน core owner
- schedule ต้องสร้าง manifest พร้อม offsets, owner identities, expected action/fault overlap และ SHA-256
  ก่อนเริ่ม load; runtime evidence ต้องอ้าง schedule marker เดียวกัน ห้ามเปลี่ยน expected outcome ตามผลจริง
- W1 ใช้ dedicated owners สร้าง queued/partial state แล้วเริ่ม user stop ที่ +60s, ส่ง MANUAL
  post-cutoff ที่ +90s, repeated stop keyใหม่ที่ +120s และ resume หลัง summary/reconciliation complete;
  ทุกขั้นมี deadline แบบ bounded และตรวจ generation/cutoff/history/financial digest
- W2 ที่ +30s สั่ง user stop พร้อมกันอย่างน้อย 10 dedicated owners โดยครอบคลุม exact duplicate,
  lost-ack lookup และ stale resume; รอบ resume เริ่มได้หลัง target complete เท่านั้น และ ownerหนึ่งช้า
  ต้องไม่ทำให้ ownerอื่นพ้น fairness bound
- W3 platform stop window แรกเริ่ม +210s ให้คร่อม WORKER_RESTART +225s; window ที่สองเริ่ม
  +660s ให้คร่อม REDIS_OUTAGE +675s และคง targetหนึ่งล้มเกิน 60s เพื่อพิสูจน์ alert จริงกับ retry;
  resume ต้องเกิดหลัง recovery/summary complete และ sent MANUAL orderต้องคงผลจริง
- core conservation คง `offered == expected`; นอก marked platform-stop window ต้อง
  `admitted == completed == expected_nonblocked` และ rejected=0. ภายใน marked platform-stop window
  เก็บ `blocked_by_scheduled_platform_stop` เป็น positive oracle และบังคับ
  `completed + blocked_by_scheduled_platform_stop == offered`; failure/rejection อื่นเป็น failure
- latency/throughput ของ non-fault workload แยก platform-stop window ตาม marker แต่ห้ามลบ blocked command
  ออกจาก offered/conservation denominator หรือใช้ window นั้นกลบ miss ที่เริ่มนอก schedule

### V-20 core-loss amendment — Approved 2026-10-31

- core 100-owner denominator, baseline count, offered/completed commands, rates, durations และ thresholds
  ต้องไม่เปลี่ยน; selected core owner ยังคง partial-fill และ exact-correction oracles
- ก่อน measured load dedicated MANUAL loss owner ต้องผ่าน partial exposure → LOSS_LIMIT stop →
  effects/reconciliation complete → risk RESET → fresh opening ถูกปฏิเสธด้วย
  `ORDER_SAFETY_UNAVAILABLE`; status ต้องยังเป็น active LOSS_LIMIT และ `resume_ready=false`
- คำสั่ง dedicated owner ไม่รวม core counters แต่ owner/process ต้องรวม resource, connection และ stop
  evidence; ถ้า opening ผ่าน, stop หาย, auto-resume หรือ core denominator เปลี่ยน ให้ถือว่า Failed

### NC-F19-05 reconciliation clock amendment — Approved 2026-10-31

- real PostgreSQL ต้องยืนยันว่า position activity ขณะไม่มี active platform stop ไม่เปลี่ยน clock
  และ API/engine ยัง UPDATE clock โดยตรงไม่ได้
- ระหว่าง active platform stop position activity commit ต้องเพิ่ม clock ใน transaction เดียวกัน;
  rollback ต้องไม่เปลี่ยน revision และ resume ด้วย reconciliation revision เก่าต้องถูก
  `TRADING_STOP_NOT_READY` ก่อนที่ exact snapshot ใหม่จะ resume ได้
- W1 rerun ต้องใช้ explicit child publisher ตาม F-18 R33 โดยคง duration/rates/SLA เดิม;
  ผล inline r5/r6 ไม่ใช้ลดเกณฑ์หรือเป็น acceptance evidence

### NC-F19-06 stop-worker cadence amendment — Approved 2026-10-31

- unit scheduler ต้องพิสูจน์ idle sequence 20/40/80/160/250ms, cap 250ms และ reset เป็น 20ms
  เมื่อ round ใดมี processed/deferred/discovered/pending work หรือ active platform stop
- real PostgreSQL ต้องยืนยัน request ที่มาถึงตอน idle ยังใช้ durable cutoff/result เดิม,
  active platform discovery หลัง restart เดินต่อ, owner failure ไม่ starve ownerอื่น และไม่มี duplicate effect
- short diagnostic ไม่ใช่ acceptance ต้องแสดง steady idle scan pressure ลดลงโดยไม่เปลี่ยน source/financial
  oracles; W1 หลังจากนั้นยังใช้ 100×20, child publisher, rates/duration/SLA และ stop schedule เดิมทั้งหมด

### NC-F19-08 R6-compatible workload readiness hint — Approved 2026-10-31

- targeted query tests ต้องผ่าน matrix: lag 0/1/100 เป็น hint ได้เมื่อ state ครบ; lag ติดลบ/101,
  evaluation-owner cursor ไม่ตรง, pending ฝั่งใดฝั่งหนึ่ง, setting revision ไม่ตรง, latched,
  owner/wallet/episode ไม่ตรง ต้องไม่เป็น hint
- harness control-flow test ต้องพิสูจน์ว่า hint ทำได้เพียงปลุก retry และทุก retry เรียก full
  `manual_policy_for`/`checked.check` ใหม่ก่อน admit; hint true แต่ R6 พบ transient breach,
  corrupt/missing frame, stale financial boundary หรือ source unavailable ต้องไม่มี order request
- rerun affected R6 policy/view tests, workload scheduling-hint tests, Ruff และ Mypy; production diff
  ต้องเป็นศูนย์นอก validation harness/tests/spec evidence
- หลัง targeted checks ใช้ fresh schema0061 + explicit child publisher ทำ short source diagnostic 60s
  หนึ่งรอบ โดยคง 100×20/setup/resources/rates; ต้องสร้าง baseline ครบ, ไม่มี worker/source crash,
  ไม่มี unintended request และไม่เปลี่ยน acceptance verdict ของ diagnostic
- diagnostic ล้มให้เก็บ Failed และหยุดเสนอ amendment ใหม่ก่อน rerun; ผ่านแล้วจึงอนุญาต W1 ตาม
  V-20/NC-F19-05/06 เดิม โดยไม่ถือ short diagnostic แทน W1

### NC-F19-09 bounded dedicated RESET retry — Approved 2026-10-31

- unit tests ต้องพิสูจน์ unavailable→unavailable→applied ใช้ request IDs ใหม่สามรายการและ sleep
  250ms สองครั้ง; non-source failure ไม่ retry; unavailable ครบสามครั้งล้มพร้อม evidence ครบ
- overall retry deadline คง 60s, max attempts=3 และ production source diff ต้องเป็นศูนย์;
  request/result/audit identities ของแต่ละ attempt ต้องไม่ซ้ำหรือเขียนทับกัน
- short diagnostic fresh schema0061/child publisherหนึ่งรอบต้องทำ baseline20/20, dedicated RESET
  สำเร็จภายในขอบเขต, opening probe ยัง fail closed, ไม่มี worker/source crash แล้วจึงเข้า source window;
  failure ใด ๆ ให้หยุดก่อน W1 ตามเดิม

### NC-F19-10 dedicated-loss fixture ordering and diagnostic — Approved 2026-10-31

- post-mortem ต้องผูก partial NEW request/command/result/audit identity และพิสูจน์ failure branch:
  r7 มี request transfer สำเร็จ, command terminal reject `RISK_SOURCE_UNAVAILABLE`, financial
  boundary/source proof ตรง แต่ price replay state ไม่ authoritative ตอน worker recheck
- unit/control-flow tests ต้องพิสูจน์ dedicated scenario รันหลัง workers ready และก่อน core baseline,
  core baseline ยัง 100×20, measured counters/rates/durations ไม่เปลี่ยน และ NEW ไม่มี retry path
- isolated dedicated diagnostic บน fresh schema0061/child publisher/real workersหนึ่งรอบต้องผ่าน
  partial fill → LOSS_LIMIT stop/effects complete → RESET (NC-F19-09) → opening fail closed;
  balance/position/reservation/order/event/audit conservation ต้องครบและไม่มี duplicate identity/fill
- diagnostic evidence ต้องมี snapshot ก่อน/หลังแต่ละ transition พร้อม request/command/result times,
  cursor/pending/watermark/lag, boundary/source proof และ terminal failure snapshot; ผลนี้ไม่แทน W1
- จากนั้น integrated short diagnostic fresh schemaหนึ่งรอบต้องคง 100×20/setup/resources/rates,
  dedicated proof ผ่านก่อน baseline, baseline20/20 ผ่าน, ไม่มี crash/unintended trade แล้วจบ source window
- ผ่านทั้งสอง diagnostic แล้วจึงรัน W1; failure ใด ๆ ให้เก็บ Failed และวิเคราะห์ branch ก่อน amendment
  หรือรอบถัดไป ห้ามเพิ่ม NEW retry/ลด fail-closed/ลด workload เพื่อทำให้ผ่าน
ผลล้มของ F-18 profile เดิมต้องคงไว้ตามจริง ใช้ผลผ่านเดิมได้เฉพาะส่วนที่ source/schema/composition
ไม่ถูก F-19 เปลี่ยน

ผล 2026-11-01: isolated dedicated r2 และ integrated short r2 ผ่านเกณฑ์ข้างต้น; W1 r1 ผ่าน
dedicated proof กับ core baseline 20/20 แต่ Failed ก่อน measured window ที่ BOT setup order ของ
stop-owner slot 1 ถูก downstream command ปฏิเสธ `RISK_SOURCE_UNAVAILABLE`. ปลายทาง owner cursor
4314 / publication watermark 4427 / lag 113 และ replay pending ยืนยัน capacity/backlog branch;
ไม่มี rejected-order financial effect หรือ duplicate execution. หยุดก่อน W2/W3 และ V-20 ยังคง
Pending Full Validation จนมี owner-approved amendment สำหรับ bottleneck นี้

### NC-F19-11 setup-only stop-owner readiness gate — Approved 2026-11-01

- control-flow tests ต้องพิสูจน์ false→true แล้วส่ง setup NEW เพียงครั้งเดียว, timeout ไม่สร้าง
  request/command/order และ terminal `RISK_SOURCE_UNAVAILABLE` หลัง submit ไม่ retry/resubmit
- reuse NC-F19-08 matrix: hint เป็นเพียง scheduling precondition; full production command policy
  และ worker recheck ยังเป็น authority และ lag101/pending/mismatched revision/owner ต้องไม่ผ่าน gate
- diff ต้องจำกัดที่ validation harness/tests/spec evidence; production source/schema ต้องเป็นศูนย์
  และ core baseline/measured counters/rates/durations/SLA/resources/stop schedule ต้องไม่เปลี่ยน
- W1 fresh schema/child publisherหนึ่งรอบต้องผ่าน dedicated proof, core100×20, stop-owner setup,
  measured 600s, RESET100/100, stop schedule, source/risk/latency/resource/financial invariants เดิม;
  timeout หรือ terminal reject เก็บ Failed และหยุดก่อน W2 โดยไม่เพิ่ม timeout/NEW retry
- ผ่าน W1 แล้วจึงเดิน W2/W3 ตาม V-20 เดิม; เจ้าของอนุมัติ implementation และ conditional W1
  เมื่อ 2026-11-01

ผล 2026-11-01: targeted 8/8, workload-profile 19/19, Ruff/Mypy/diff check ผ่าน; W1 fresh-schema
ผ่าน dedicated proof และ core100×20 แต่ Failed ที่ MANUAL stop-owner readiness timeout ก่อน measured
window. WAIT_START/TIMEOUT ไม่มี durable risk rows และฐานข้อมูลยืนยัน request/command/order 0 จึงผ่าน
no-submit safety criterion แต่ไม่ผ่าน W1 acceptance; หยุดก่อน W2/W3

### NC-F19-12 initialize MANUAL stop-owner risk state — Approved 2026-11-01

- targeted test ต้องพิสูจน์ MANUAL stop-owner `SET 1000` terminal `APPLIED` ก่อน WAIT_START และ
  readiness query เห็น current non-pending setting/owner/evaluation state; NEW submit ยังคงครั้งเดียว
- timeout/terminal rejection ต้องคง no-retry/no-resubmit และเก็บ identity/financial absence ตามเดิม
- diff จำกัด validation harness/tests/spec evidence; production/schema/load/SLA/resources ไม่เปลี่ยน
- หลังอนุมัติและ targeted/static checks ให้รัน W1 fresh-schemaหนึ่งรอบ; failure หยุดก่อน W2/W3

เจ้าของอนุมัติ implementation และ conditional W1 เมื่อ 2026-11-01

ผล 2026-11-01: targeted 4/4, Ruff/Mypy ผ่าน; W1 ผ่าน dedicated proof, core100×20 และ readiness
ของ MANUAL/BOT แต่ Failed ที่ +172.51s เพราะ scheduled BOT partial order ถูก fill เต็ม 1 BTC แทน
0.5 BTC แล้ว wait status timeout. ไม่มี duplicate fill/position execution หรือ negative reservation;
หยุดก่อน W2/W3

### NC-F19-13 isolate scheduled partial-fill source window — Approved 2026-11-01

- targeted/control-flow tests ต้องพิสูจน์ source ask quantity 0.5 ถูกติดตั้งก่อน partial NEW และ restore
  หลัง stop effects terminal รวม failure/cancellation path; publication rate/cadence ต้องไม่เปลี่ยน
- real-worker diagnostic ต้องเห็น exactly one 0.5 fill, remaining reservation ถูก cancel/release,
  stop/resume identity ตรง และ source กลับ regular fixtureก่อน core workload เดินต่อ
- diff จำกัด validation harness/tests/spec evidence; production/schema/load/duration/SLA/RESET schedule
  ไม่เปลี่ยน และไม่มี retry/resubmit NEW
- หลังอนุมัติและ targeted/static checks ให้รัน W1 fresh-schemaหนึ่งรอบ; failure หยุดก่อน W2/W3

เจ้าของอนุมัติ implementation และ conditional W1 เมื่อ 2026-11-01

ผล 2026-11-01: unit/control-flow5/5, real-DB schedule3/3 และ Ruff/Mypy ผ่าน; W1 scheduled
partial0.5 → stop cancel/release → restore → resume ผ่าน แต่ global quantity0.5 window ทำ core MARKET
BUY รายหนึ่ง partial0.833/EXPIRED และ cycle60s timeout ที่ +159.73s. ไม่มี duplicate execution หรือ
negative reservation; เก็บ Failed และหยุดก่อน W2/W3

### NC-F19-14 owner-isolated one-shot partial trade — Approved 2026-11-01

- publisher/control-flow tests ต้องพิสูจน์ one-shot trade ถูก acknowledge/consumeครั้งเดียวหลัง dedicated
  order `ACCEPTED`, unknown/duplicate control ถูกปฏิเสธ และ cancellation/failure clear pending injection
- real-worker matrix ต้องเห็น dedicated order exactly one fill0.5 และ core ordersที่ overlapยัง FILLED ตาม
  original workload; stop effects cancel/release remainder ก่อน resume และ financial identitiesไม่ซ้ำ
- source cadence/rate, owners, offered load, duration, SLA, RESET schedule และ production/schemaไม่เปลี่ยน
- หลังอนุมัติและ targeted/static checks ให้รัน W1 fresh-schemaหนึ่งรอบ; failure หยุดก่อน W2/W3

**Pending Full Validation — ท้ายชุดที่ 5:** เจ้าของสั่ง 2026-11-01 ให้หยุดรันซ้ำใน feature
checkpoint และรวม NC-F19-14 → targeted checks → W1 → W2 → W3 เป็นลำดับเดียวที่ checkpoint
ท้ายชุด โดยใช้หลักฐานเดิมที่ยัง valid, คง Failed artifacts และไม่ลดเกณฑ์/load/duration/SLA

## 6. ด่านและหลักฐาน

### Review-remediation checks — 2026-11-01

- V-03/11: clock เก่าถูก reject; clock ใหม่กับ summary เก่าก็ต้อง reject;
  position CONFLICTED ต้องไม่ resume แม้ใช้ revision ล่าสุด; refresh หลัง READY จึง resume ได้
  clock-row lock serialize transactions จริง และ API เรียก definer lock/UPDATE clock ไม่ได้
- V-14: held owner lock ต้อง defer ภายใน bound และ enroll owner อื่นในรอบเดียวกัน;
  ปล่อย lock แล้วสอง workers retry ต้องได้ target เดียว ไม่ตกหล่นและไม่ complete ก่อนครบ
- V-01/03/15: USER กับ LOSS_LIMIT/SYSTEM ทั้งสองลำดับยังแสดง unresolved cause หลัง USER resume;
  banner ยังเห็น durable loss/system เมื่อ risk latch=false โดยไม่ปลด cause อื่น
- V-07/08/19: migration 0062 empty round-trip, snapshot-history downgrade guard, narrow grants,
  schema/client generation, affected financial/concurrency tests และ required CI บน candidate ใหม่
- ผล/คำสั่ง/limitations บันทึกใน `evidence/implementation-checkpoint.md`
  หัวข้อ Post-CI deep-review remediation; local backend4056/frontend343/browser2 ผ่าน
  และ required CI ของ `f00bac0` ผ่านแล้วทั้ง push/PR; checks นี้ไม่ปิด V-20..24
- หลัง owner-authorized refactor: affected backend67/frontend4 พร้อม lint/types ผ่าน;
  ใช้ full regression/browser evidence เดิมในส่วนไม่กระทบ ตามหัวข้อ refactor ใน checkpoint

- ก่อนทุกชุดตรวจแจ้งขอบเขต สิ่งที่พิสูจน์ และเวลารวมโดยประมาณ; จบแล้วบันทึกเวลาจริง
- แต่ละ milestone อัปเดต `evidence/mN-*.md` เดิมพร้อม commit/worktree state,
  commands/results/environment และ Pending/Failed/Partial ตามจริง
- เมื่อ implementation ครบ plan ทั้ง feature ให้แจ้ง **Ready for Code Review** พร้อมไฟล์สำคัญ,
  tests, validation ค้าง และ reviewer risks แล้วหยุดรอคำสั่ง `review code`
- หลัง review/fixes สรุปและถามว่าจะ `refactor the code` ต่อหรือไม่ตาม AGENTS.md
- ก่อน merge V-19 และ correctness/safety ที่ไม่เลื่อนต้องผ่าน; required CI ต้องเป็น candidate เดียวกัน
- Development Complete ใช้ได้เมื่อ implementation/review และด่านไม่เลื่อนผ่าน แต่ V-20..24
  ยัง Pending; Completed ต้อง V-01..24 ผ่านครบตาม dependency/release จริง
- commit/push/merge ทำเฉพาะเมื่อเจ้าของสั่ง

ผล local เริ่มต้นผูกกับ worktree ณ 2026-10-31; หลักฐาน review-remediation/refactor และ
required CI ล่าสุดผูกกับ `f00bac0` ตาม V-19 และ checkpoint. รายการ Partial/
Pending Full Validation/Pending Dependency ยังคงผลตามจริง ไม่ถือว่าผ่านหรือ Completed.
หาก candidate เปลี่ยน ต้องตรวจผลกระทบและ required CI บน candidate ที่จะ merge ตามกฎเดิม

## 7. Set-5 execution crosswalk — Approved 2026-11-01

สถานะส่วนนี้: **Approved — เจ้าของสั่ง `approve Set-5 plan including NC-F19-14 and NC-F19-15`; ยังไม่รันชุดยาว**
ลำดับ/ไฟล์ reuse/เวลารวมอยู่ใน [plan §11](plan.md#11-full-validation-ท้ายชุดที่-5--approved-2026-11-01)
การวางแผนไม่เปลี่ยนผล V-20 หรือ dependencies และไม่อนุญาตให้ใช้ F-18 R34 verdictแทน F-19

| ด่าน | หลักฐานที่ต้องมี | ผลปัจจุบัน |
|---|---|---|
| NC14 preflight | ราคา2ผ่าน constraints/covered gap/queue0; order ACCEPTEDก่อน injection; one control→one committed trade→one fill0.5; unknown/duplicate/ACK-loss/cleanup paths; core BUY/SELL overlapยัง FILLED; exact cancellation/release/financial identities | Passed targeted — host/Linux real-worker matrix; under-load proofยังไม่ครบเพราะ W1ล้มก่อน injection |
| NC15 evaluator | Explicit F-19 profile owner99.9%≤3s/run99.9%≤3s/all≤5s, complete acknowledgements/clock/source nominal counts; F-18 R34ไม่เปลี่ยน; boundary casesแยก verdictได้ | Approved / Passed targeted — explicit F19_SET5 owner99.9%/allowance0; W1ไม่ครบจึงไม่มี final SLA verdict |
| W4 coverage preflight | Real DB fixtureมี USER/SYSTEM/PLATFORM causes, pending cursor/targets/effects, receipts/audit/reconciliation revision; digests/roles/RLS/grantsและ recovery assertionsครบ F-19 | Passed targeted — staging/recovery/stale-resume; full backup/restore Not Run |
| W1 | Dedicated LOSS partial→breach→effects complete→RESETตามNC09→opening blocked; core baseline100×20; schedule +60/+90/+110/+120/+150ตาม manifest; 600s/10commands/s; complete source/SLA/resource/financial/counter oracles | Failed — Set5 W1 r1 TimeoutErrorที่+121.09s; คง NC13 Failedเดิม |
| W2 | หลัง W1ผ่าน; 300s/100commands/s; 10 concurrent dedicated stops, exact duplicate/lost ACK/stale resume/fairness/overflow; offered conservationและ core denominatorคงเดิม | Not Run |
| W3 | หลัง W2ผ่าน; 1800s/10commands/s; 7 faults/JSON digestเดิม, platform windows +210/+660, target failed≥60sพร้อม alert/retry, manual sent ordersคงจริง, recovery/RSSและ financial oracles | Not Run |
| W4 | หลัง W3ผ่าน; fresh source/restore targets schemaเดียวกัน; pre-recovery canonical/role digestตรง; pending work recoveryและ replay/stale-resumeไม่สร้างผลเศรษฐกิจซ้ำ | Not Run — F-18 W4เดิมไม่ปิด F-19 |
| Final coverage | Map affected regression/production composition→F-16 V-18/F-18 V-21/F-19 V-20แยกรายข้อ; ใช้ CIเดิมเฉพาะส่วนที่ไม่กระทบ; report source/config/schema/environment/manifestและ candidate identity | Pending Full Validation |

ก่อนรันต้องตรวจ VM/container/CPU/RAM/worker/pool inventory กับ approved runnerเดิมจริง
เครื่องหรือ DBที่ใช้ CI ไม่ใช่ workload profileโดยอัตโนมัติ ห้ามเพิ่ม resourceเพื่อให้ผ่าน
cadenceนับ periodic BOOK/PRICE receiptsตาม nominal [start,end) โดยไม่ padding/setup/drain;
one-shot tradeมี identity/effect evidenceแยก ไม่ใช่ periodic book receiptเพิ่มหรือสิทธิ์หัก miss
dedicated ownersไม่แทน core100owners แต่รวม resource/connection/fairness inventory

ทุกขั้นมี outputใหม่/manifest hash/เวลา setup+measurement+drain และ failure branch
ไม่ใช้ short diagnosticหรือ CIเขียวแทน acceptance. ล้มให้เก็บ Failed และหยุดก่อนขั้นถัดไป
ไม่ retry NEW/rerun unchangedหรือแก้เกณฑ์เพื่อให้ผ่าน; bounded RESET retryคงNC09เท่านั้น
หากจำเป็นต้องเปลี่ยน production/resource/sourceวิธีอื่นให้เสนอ amendmentก่อนแก้

เมื่อครบให้ปิด V-20 เฉพาะ scopeที่มีหลักฐานจริง V-21..24ยัง Pending Dependencyตามเดิม
F-16/F-18ยังไม่ Completedจากการผ่านชุดนี้เพียงอย่างเดียว ไม่อนุญาต production/Live activation
ไม่มีผลทดสอบใหม่เกิดขึ้นจากการเพิ่ม crosswalkนี้

### NC-F19-16 pool/transaction diagnostic — Approved 2026-11-01

เจ้าของตอบ `approve` ต่อข้อเสนอ NC-F19-16 ใน plan.md อนุญาต diagnosticหนึ่งรอบ
fresh DB, W1 profileเดิม (core100×20, command10/s, child5Hz), observation180s
หลัง targeted instrumentation checks. แยก INTAKE/READY_HINT/REQUEST_VIEW และ worker
pool acquisition/transaction/query timing ด้วย identities, SQL hashesเท่านั้น ไม่เก็บ params
หรือ exception text. ใช้ pool inventory/dispatch/cycle evidenceเดิม พร้อม DB wait metadata
และ VM/container samples; NULL metadataถือว่า unknown ไม่ใช่ไม่มี wait

ไม่เปลี่ยน pool/resource/deadline/polling/retry/production และไม่ใช้ผลแทน W1 600s acceptance
ทุกผลต้อง `acceptance_result=false`; หยุดที่ failureแรก เก็บ trace/DB/manifestแล้ววิเคราะห์
ไม่เริ่ม W2/W3/W4 และไม่ rerun W1. V-20คง Failed/Pending Full Validation

ผล NC16: targeted76/Linux17ผ่าน, Ruff/mypyผ่าน; diagnosticหนึ่งรอบ **Failed**
ที่+172.298sใน stop scenario ซึ่งรอ partial fill60s ไม่ใช่ core cycle timeout.
one-shot input1568 commitสำเร็จ แต่ owner REBASE1566→1575ข้าม tradeเมื่อกลับมา
ประมวลผลหลัง freshness window; pool waitของ transactionนั้น0.000659s.
เก็บ failed DB/trace/source hash และข้อจำกัดใน evidence/implementation-checkpoint.md.
acceptance_result=false; ไม่รันซ้ำ/W2/W3/W4. ต้องเสนอ amendmentก่อนเปลี่ยน harness
หรือ production; ผลนี้ไม่ปิดสาเหตุ API-pool timeoutของ W1รอบก่อนย้อนหลัง

### NC-F19-17 consumer-barrier validation — Approved 2026-11-01

เจ้าของอนุมัติพร้อม NC17ใน plan.mdด้วยคำตอบ `apprve`; ไม่เปลี่ยน requirementsหรือเกณฑ์ V-20เดิม
ผล NC17: harness targeted100/real-worker3/Linux16ผ่าน; W1หนึ่งรอบ **Failedที่risk SLA**
รายละเอียดผล/ข้อจำกัดอยู่ท้ายส่วนนี้และใน implementation-checkpoint; ไม่เริ่มW2/W3/W4

| ระยะ | เกณฑ์ | หลักฐานที่ต้องได้ |
|---|---|---|
| Feature (harness correctness) | Delivery protocol | Arm/READY/COMMITTED identitiesตรง owner/episode/order/pair/generation/key; duplicate READYไม่เพิ่ม publication; mismatch/lost ACK/unknown commit/disconnectไม่ retry NEWหรือtrade |
| Feature (harness correctness) | Real consumer path | Original workerเลือก recoveryเอง; captured bookจริง→one committed tradeใน following batchเดิม→persisted INPUT/evidence→exactly one fill0.5/spent1; ไม่ fake decisions/แก้ timestamp/ขยาย limit19 |
| Feature (safety) | Fail-closed preserved | Delayed/stale inputยังถูก reject/rebase; no-natural-recovery/ข้าม deadlineต้อง Failed; ไม่ refresh/replayและไม่ซ่อน failureด้วย fixture fallback |
| Feature (safety) | Financial/overlap | Real workers/childบนPostgreSQL; core BUY/SELL FILLEDขณะtargetpartial; stop cancels remainder/reservation releasedตามoracleเดิม, balance/position/feesตรง Money/Quantity และ audit/request identitiesไม่ซ้ำ |
| Feature (harness regression) | Isolation/cleanup | Unarmed/other-owner/non-recovery/F18/dedicated LOSS pathsไม่ถูก gate; cancellation/process lossคืน patches, IPC/tasksและpoolsครบ ไม่ลบ facts; affected tests/Ruff/format/mypyผ่าน |
| Batch (V-20 เดิม) | W1หนึ่งรอบ | Fresh DB, core100×20,10commands/s,5Hz child,600s; schedule/SLA/source/resource/financial criteriaเดิมทั้งหมด. Barrier durationนับจริง; ไม่เลื่อน stop/resume offsetsหรือหักเวลาเพื่อให้ผ่าน |
| Batch (V-20 เดิม) | W2/W3/W4 | เริ่มตาม P3–P6เมื่อ W1ผ่านครบเท่านั้น; ใช้ approved workload/restore criteriaเดิมและ reuseหลักฐานที่ยังตรง |

ทุก receiptต้องแยก armed/READY/publication requested/committed/consumed/fill committed;
ACKไม่เท่ากับ financial effect. บันทึก captured book, source input/trade, worker/claim/backend,
owner/order/request/key, wall/monotonic timestampsและdeadline โดยไม่ใส่ secrets/SQL params.
ถ้าโค้ดจริงต้องเปลี่ยน production, scheduling priority, source cadence, resourceหรือ assertion
นอก NC17 ให้หยุดขอ amendmentก่อน. W1/NC16 Failedเดิมยังคงอยู่; ผลหลังอนุมัติอยู่ด้านล่าง

ผลหลัง implementation (ไม่เปลี่ยนเกณฑ์): delivery/real-consumer path/safety/financial overlap/
cleanupผ่าน targeted checks. W1รันครบ600sและตรวจท้ายรอบแล้ว โดย partial0.5/spent1,
stop/cancel/release/resume, source3000/3000ทุกchannel, commands6000/cycles1200,
RESET100/100, per-owner financial/global invariants, resource/returned pools/cleanupผ่าน

**Batch V-20 W1 Failed:** risk SLAมี1302/918703 samplesเกิน3s (99.858278%≤3s
เทียบเกณฑ์99.9%); owner quotaไม่ผ่าน56/100. Hard limitเกิน5sจำนวน3samplesจากownerเดียว
max5.034698s; unacknowledged0/clock_errors0. ไม่ลดเกณฑ์หรือใช้ผลfunctionalแทนSLA
Engine transaction p95/p99 0.218810/0.339924sผ่าน. W2/W3/W4ยังNot Run
ผลpreflightแรกFailedและ failed DBทุกรอบเก็บไว้; ไม่เขียนทับหรือrerun unchanged

### NC-F19-18 diagnostic evidence — Approved 2026-11-02

Ownerอนุมัติ `approve NC-F19-18` พร้อม NC18ในplanแล้ว; ไม่เปลี่ยนV-20criteria
ผลinstrumentation tests/300sdiagnostic **Not Run**. Analysisเดิมเสร็จแล้ว:
independent reconstructionตรง1302late/918703expected/3hardทุกidentity, rawfilesไม่เปลี่ยน;
owner-lock timeoutsยืนยันได้ แต่ causal stage/actor attributionยังไม่พอเลือกproduction fix
ดู [analysis](evidence/risk-latency-analysis-2026-11-02.md)

| ระยะ | สิ่งที่ต้องพิสูจน์ | เกณฑ์ |
|---|---|---|
| Feature (observer correctness) | Scoped stage/queue/pool/lock/snapshot/replay/persist/commit observers | original rows/results/owner selection/slotcount/timeoutsไม่เปลี่ยน; identitiesและtimestampsครบ, disabled pathเดิม, caps/redaction/cleanup/cancellationผ่าน |
| Feature (measurement correctness) | Commit proof | Real DB success/rollback/savepoint/mismatch/NULL/collector failure; pgcommitต้องมีmatching writer identity, unknownแสดงตามจริงและไม่ใช้restoretimestamp; ไม่เพิ่มackหรือrefreshcursor |
| Feature (regression safety) | Impacted existing tests/static | Scheduler fairness/slow owner, replay/transient breach/fence/idempotencyตามdiff พร้อมRuff/format/mypyผ่าน; ไม่ใช้mockพิสูจน์DBlocking/commit |
| Diagnostic only (ไม่ใช่Batch acceptance) | One fresh-DB300s observation | W1resources/load/core100×20/child5Hz/NC17barrierเดิม; originalW1duration600, allartifacts `acceptance_result=false`; stopแรกที่failure, cutoff cancellationระบุแยก |
| Diagnostic evidence | Latency attribution | input→round/selection/queue/pool/lock/snapshot/replay/persist/commit/observationผูกidentity; coverage/residual/observeroverhead/unknownsครบ. Traceขาดหรือtruncatedไม่สมบูรณ์; ไม่เรียกPassedเพราะไม่เกิดmiss |

ไม่มีW1rerun/production fixในapprovalนี้. หลังได้ผลให้เสนอข้อแก้ที่มีหลักฐานหรือหยุดพร้อม
ข้อมูลที่ขาด ไม่rerununchanged/ปรับเกณฑ์. ผลFailedเดิมและV-21..24Pending Dependencyคงเดิม

ผล NC18: targeted116/Linux38/staticผ่าน, one300sdiagnostic **OBSERVATION_COMPLETE**
และacceptance_result=false. Stage/commitstreams13ชุดปิดครบไม่truncated.933observedlate/
451280nominalinputs,155groups,552ยังไม่ackตอนcutoff; ไม่ใช้เป็นSLA/W1pass.8linkedgroups
รอsemaphoreอย่างเดียว≥3s; verifiedservercommitยืนยันactual3sdelay.0hard5sในprobe
ไม่ปิดhard5sจากNC17ย้อนหลัง.23648verified/1272unknownproofs; details/overhead/metadata
correctionและcutoffwarningsอยู่ใน [report](evidence/risk-stage-diagnostic-2026-11-02.md)

### NC-F19-19 rolling monitor validation — Approved 2026-11-02

เจ้าของอนุมัติ `approve NC-F19-19` พร้อม plan; implementation/targeted checks complete; W1 **Failed / environment invalid**.

| ระยะ | เกณฑ์ |
|---|---|
| Feature | LegacyroundAPI/empty-excludeselectionequivalent;4inflightmaximum/selected≤free/noownerduplicate;newreadyownerprogressระหว่างslowpeerโดยไม่รอfullpage |
| Feature | >100-ownerfairness/wraparound,locked/failed/newlyeligible/continuouslyeligibleowner,settingsdisappear,activeexclusionก่อนLIMIT;scan/taskfailurepropagationและcancel/join/poolcleanup |
| Feature (real DB) | Two-instanceownerlockserialization,timeout/rollback/cancellation,no duplicatebreach/stop/audit/cursorcorruption;RLS/fence/replay/transientbreach/pending-source/RESET/financial/idempotencyregressionsตามdiff |
| Feature | Harness/observerrollingturnidentityandmanifestcoverage;Ruff/format/mypy/importchecksที่กระทบผ่าน |
| Batch (V-20 เดิม) | OnefreshDBW1600s/100owners×20/10commands/s/child5Hz/NC17barrier,allF19SLA/source/stop/financial/resourcecriteriaเดิม;targetedผ่านก่อนเริ่ม |

W1ผ่านครบจึงW2/W3/W4/P6ตามแผนเดิม; failureหยุดเก็บผลก่อนขั้นถัดไป. ไม่ใช้NC18
diagnosticหรือcontrolledcounterexampleแทนacceptance;ไม่มีthreshold/resource/deadline
relaxation. Rollbackคืนlegacyloopโดยไม่ลบfacts/ปลดstop.ไม่มีproductionactivation/Gitauthorization

NC19 results: targeted35 passed; regression95 passed/1 failed from global STOP fixture
backlog beyond20. Fresh-DB concurrency/pending/financial26 passed with unchanged assertions.
Linux43 passed plus explicit fresh-global4 passed after correcting default marker selection;
final targeted9 passed. Ruff/format/mypy seven changed files and seven import contracts pass.
The initial setup abort and original fixture failure remain recorded, not overwritten.

Batch W1 `nc19-w1-r2`: **Failed / environment invalid**, before the measured window.
Baseline100x20 and dedicated LOSS_LIMIT/RESET passed, subsequent BOT resting NEW rejected
SOURCE_UNAVAILABLE. All nine role URLs incorrectly referenced the preflight DB instead
of the newly created intended DB. No600s/SLA conclusion or proven production cause.
Max in-flight4; all pools finalized/checked_out0, remaining connections0; partial duplicate
fill/negative position/reservation checks0. W2/W3/W4 remain Not Run in Set5.

Parsed URL/actual connected database/fresh-schema guard prepared and tested. One
replacement W1 on a verified fresh DB was authorized under the failure stop rule:
`approve W1 fresh DB rerun` on 2026-11-02. Its outcome is recorded below; no acceptance pass.
V-20 remains Failed / Pending Full Validation, preserving NC17's prior Failed verdict.
Details and limitations: [NC19 report](evidence/rolling-monitor-2026-11-02.md).

Replacement W1 `nc19-w1-r3` executed on verified fresh DB with all nine roles checked,
empty fixture/schema0062/tested source confirmed. Setup/baseline100x20/dedicated LOSS_LIMIT
and manual/BOT resting setup passed. **Failed** at recorded+37.594s: BOOK child source
SourceUnavailableError; no completed600s/source/SLA verdict. Wall-time recorder reversal
-16.857ms with monotonic+18.732ms is confirmed near failure; exact leaf guard timing
and causal link remain unproved. Partial financial/cleanup checks and original72files,
dump/hashes are retained. See [fresh rerun report](evidence/w1-fresh-rerun-2026-11-02.md).
W2/W3/W4 not started; no rerun/production change after failure.

### NC-F19-20 diagnostic validation — Approved 2026-11-02

Owner authorized `approve NC-F19-20` together with the plan. Implemented and checked;
one diagnostic finished **Not Reproduced / non-acceptance**, as recorded below.

| Phase | Criterion |
|---|---|
| Feature | Original BOOK readiness return/exception unchanged for ready, future received/verified/source, stale and not-ready cases; exact captured condition flags and caller clock argument |
| Feature | Child-only scoped observer restoration, redaction/no financial values or SQL parameters, bounded failure output and explicit incomplete evidence on observer error |
| Feature | Diagnostic CLI exclusive W1/F19_SET5/child60s; guard asserts all nine actual role DB identities and empty fresh schema; original resources/workers/pools/source cadence preserved |
| Feature | Relevant publisher regressions and changed-file Ruff/format/mypy pass |
| Batch diagnostic, non-acceptance | One60s observation after100x20 setup under original load; complete failure timings or Not Reproduced; overhead/limits reported; acceptance_result=false always |

No future-time tolerance/freshness/lease/timeout/resource/quota relaxation, NEW retry or
production fix. A diagnostic does not pass V-20 or authorize a new acceptance run. Stop
after failure or no reproduction, and propose next scope only from evidence. Work beyond
the observation window remains Not Exercised; previous Failed/Pending statuses are kept.

NC20 results:94Linux tests passed, zero skips,10.044s; changed-file Ruff/format/mypy pass.
Real child observer/restart/cleanup and unchanged guard outcomes/exception identity,
reason flags, cap/write incompleteness/redaction/restoration and CLI exclusivity covered.
Original production/runtime code unchanged; existing safety evidence reused.

`nc20-r1`: all nine actual role connections/fresh schema/empty fixture checked, schema0062;
baseline100x20/dedicated LOSS_LIMIT/RESET/manual-BOT setup completed. One60s observation
(recorded60.600486s) **OBSERVATION_COMPLETE**, acceptance_result=false.1203guard calls,
0failure records, closed/complete. **Not Reproduced**. No new publisher error or observed
receipt clock reversal, neither establishes a fix or global clock stability. Original
r3 failing guard arguments remain missing. No W1/SLA/source-window acceptance verdict.

All13pools finalized/checked_out0, remaining connections0. Partial194FILL identities with
0duplicates/nulls/negative positions/reservations;103wallets no negative balances; retained
14termination warnings. Scheduled RESET and later one-shot/barrier/full stop work Not
Exercised, not Passed. Raw73files/dump18,051,985bytes/hashes retained. Stop on no reproduction;
no repeat/W1/W2/W3/W4. V-20 Failed/Pending Full Validation and dependencies unchanged.
See [NC20 report](evidence/book-clock-diagnostic-2026-11-02.md) for limits and next scope.

Read-only clock environment review completed at owner request: host NTP operation
confirmed, no matching09:41:25host apply/sleep/wake/VM-restart record, no guest clock setter
identified. No configuration fix proved or applied. UI value unavailable after denied
Computer Use retry; operational timed evidence retained. No runtime tests/workloads run.
[Review](evidence/clock-environment-review-2026-11-02.md). Existing statuses unchanged.

### NC-F19-21 clock-only validation — Approved 2026-11-02

Owner instructed `เริ่มทำ` after the NC21 proposal. Implementation/checks/one trace authorized;
one trace completed as recorded below. No acceptance or environment fix implied.

| Phase | Criterion |
|---|---|
| Feature | Per-domain bracketed wall/monotonic reads distinguish step/no-step and expose slow-read/transport uncertainty; no cross-domain absolute-monotonic subtraction |
| Feature | Bound30000records/buffers, missing samples/cap/write failure marked incomplete; cancellation closes observer; no clock-setting or trading/DB operations |
| Feature | Guest observer nonprivileged/read-only/network-none/no capabilities/no secrets;0.1CPU/64MiB cap; original VM/profile settings unchanged; static checks pass |
| Batch diagnostic, non-acceptance | One20min10Hz trace plus existing-log correlation; report localization or Unknown/Not Reproduced with uncertainty; no repeat or automatic W1 |

No clock-only result passes V-20 or proves r3's missing guard arguments. Configuration
or production fix needs a separate evidence-backed proposal. Preserve all prior results.


### NC-F19-21 execution checkpoint — 2026-11-02

22 probe regressions passed, zero skips; Ruff/format/mypy two files passed. One20min10Hz
trace completed:12000 contiguous exchanges, no gaps, guest exit0/noOOM, source verified.
40 guest offset movements recur at median29.999772s, including24 decreases(max2.994309ms).
Host has no offset decrease;504 increase intervals align with logged positive NTP adjtime,
not504 discrete steps.11930 conditional transport bounds/70 retained Unknowns; selected
sequence400 supports guest-relative backward offset movement beyond uncertainty.
Exact setter and original r3 guard cause remain unproved; no trading failure reproduced.
No setting/production/criteria changes or W1 rerun. Diagnostic complete/non-acceptance;
V-20 Failed/Pending Full Validation, dependencies unchanged. Next: separate environment
remediation proposal/approval; no automatic further diagnostic. See
[NC21 evidence](evidence/clock-comparison-2026-11-02.md).


### NC-F19-22 environment transition — Superseded 2026-11-02

ประวัติข้อเสนอเดิม: เจ้าของปฏิเสธใช้เครื่องอื่นแล้ว ไม่ต้องจัดหาLinux target และไม่รันตามตารางนี้
ใช้replacement same-machine measurement auditด้านล่างแทน;เก็บNot Runเดิมตามจริง
ดูขอบเขตและNeeds Clarificationในplan.mdหัวข้อNC-F19-22

| Phase | เกณฑ์ | ผล |
|---|---|---|
| Feature / environment gate | Owner-approved disposable target/access/budget, sanitized inventory; candidate content/image/schema/dependency hashes; architecture/resource/enforcement differences disclosed and approved before execution | Not Run — target/approval missing |
| Feature / affected safety | Existing scheduler/concurrency/DB/fresh-global/publisher tests selected by environment impact; same9actual-role DB/fresh-schema guards, no unexpected skips; relevant static checks only if code changes | Not Run; reuse prior evidence only where unaffected |
| Batch diagnostic, non-acceptance | One300s10Hz bounded existing clock probe, completeness/uncertainty/overhead and existing logs retained; no detectable backward offset beyond bracket bounds; incomplete/ambiguous evidence blocks W1; acceptance_result=false | Not Run; no new SLA/clock tolerance |
| Batch / V-20 W1 | Conditional onefreshDB600s approvedF19_SET5 run with baseline100×20/dedicatedLOSS_RESET, source/counter/schedule/financial/resource oracles and owner/run99.9%≤3s/all≤5s unchanged | Not Run on proposed target; previous Failed retained |
| Batch / checkpoint | Report actual timings, identities/manifest/hashes and exactfailurebranch; preserve Failed, stop without unchanged rerun; W2/W3/W4 wait until W1passes and next authorized scope | Pending Full Validation |

Clock preflight passing is limited observation, not stable-clock guarantee or W1pass.
NativeLinux does not by itself prove timing reliability or comparability. Changed CPU/I/O/
clock environment cannot establish NC19's performance improvement by comparison with
oldMac results; any W1verdict applies to its documented approved target only. No implicit
resource increase, NEWretry, fail-closed relaxation, trading tolerance or production fix.
V-20 Failed/Pending Full Validation, V-21..24 Pending Dependency remain unchanged.


### NC-F19-22 replacement validation — Approved / Audit complete 2026-11-02

| Phase | Criterion | Result |
|---|---|---|
| Feature / audit | Raw integrity and source provenance across NC17/18/19-r3/20/21; no restored commit substitution |261 hash entries matched;9 source files matched;3 original source contents unavailable, explicitly recorded |
| Feature / offline regression |3/5s boundaries, owner quota, missing/pending acknowledgements and cross-worker earliest acknowledgement/clock handling without services |18 existing tests passed, zero skips;5 controlled cases retained |
| Feature / measurement review |All workers, commit versus observation, denominator/setup/load/drain and scoped clock uncertainty |NC17 exact timestamp reconstruction;44 acknowledgement files/zero regressions;23,648 VERIFIED proofs/1,272 UNKNOWN; historical physical-clock bounds incomplete |
| Feature / defect checkpoint |Document/propose harness defect before fixing |Medium: stream ordering not validated; controlled regression can pass with clock_errors=0. No runtime patch; awaiting approval |
| Batch / V-20 |Original SLA/load/resource/source/financial criteria |Failed/Pending Full Validation unchanged; no new workload or regrade |

No thresholds, schema, public API, authorization, financial rules or settings changed.
Existing DB rollback/savepoint evidence reused; not rerun offline. Diagnostics retain
acceptance_result=false and partial scope. Missing source prevents full historical source
recertification; NC21 bounds cannot correct old runs. Audit outputs are separate from raw
results. See [measurement audit](evidence/measurement-audit-2026-11-02.md) for findings,
proposed patch, uncertainty and commands. Next: owner approval of the narrow stream-order
guard; no automatic W1 or diagnostic.


### NC22 stream-order guard checkpoint — 2026-11-02

Owner approved the narrow guard fix. Implemented in `profile_workload.py::sla_summary`
and covered in `test_workload_sla.py`. Each stream is validated before pending/owner
filtering, including trailing rows after all inputs have acknowledgements. Parsed datetime
keys keep validation and merge ordering consistent. Equal timestamps remain valid; every
row is preserved, with no sorting/dropping/clamping/clock correction. All regressions are
counted; only the first20 file/line/timestamp diagnostics are retained. Additive fields
`stream_order_errors` and `first_stream_order_errors` are separate from `clock_errors`.
Any ordering error forces overall passed=false; existing numerical SLA counters remain.

27 non-DB regressions passed, zero skips (18 existing +9 cases): would-be pass/miss under
F18/F19, filtered pending/foreign-owner rows, equality, earliest interleaved worker results,
and bounded diagnostics with full error count. Ruff/check, format/check and mypy two files
passed. Initial mypy invocation could not resolve local src and reported235 import/type
errors; corrected invocation `MYPYPATH=src` passes without source/config suppression.
DB rollback/savepoint tests reused; no services/workload/settings/production changes.

Artifacts: `validation-artifacts/f19-set5-20261101/nc22-stream-order-guard/` contains test
XML, static log/summary, exact evaluator patch and candidate hashes. Original audit/run
artifacts remain unchanged. Historical audit.py expects the prepatch evaluator (matched
NC20 snapshot retained in audit snapshots); its counterexample assertions must not be
rerun against the patched evaluator as though they were new acceptance criteria.

Guard defect fixed, not an environment/latency fix. Existing44 real acknowledgement files
were ordered, so this does not explain or regrade original failures. V-20 remains Failed /
Pending Full Validation; W2/W3/W4 and dependencies unchanged. Next recommendation: review
this narrow patch before deciding the next clock/acceptance amendment; no automatic timed
run or new diagnostic. No commit/push. This subtask does not trigger full-feature Ready
for Code Review or authorize refactor/full validation.


### NC22 guard refactor checkpoint — 2026-11-02

Owner-authorized refactor complete, limited to the guard and its new tests. Named previous
observed/raw timestamp fields replace tuple indexes; adjacent line identity comes from
enumeration and filename is computed once per stream. Local `write_risk_stream` removes
repeated JSONL serialization in the new tests; existing fixtures/ack builders remain in
use. Preservation test compares original bytes. Verdicts, counters, cap20, diagnostics,
merge/filter order and all SLA/financial behavior unchanged; no new infrastructure.

27 non-DB tests passed, zero skips; two-file Ruff/check, format/check and mypy passed
(`MYPYPATH=src`). Validation after refactor covers only the affected Feature/evaluator
criteria; DB/safety evidence remains valid. Approved stop on timed runs still applies:
no W1, other workload, new diagnostic or settings change. No production change.

Artifacts in `validation-artifacts/f19-set5-20261101/nc22-stream-order-refactor/` retain
before-source copies, exact refactor diff, test XML, final hashes and check summary.
This finishes the authorized guard/refactor checkpoint. Next: owner may instruct commit/
push of this checkpoint under Git rules; no Git action occurred. V-20 Failed/Pending Full
Validation and clock/old-latency/source-evidence limitations remain; do not infer a W1pass.


### NC-F19-23 clock-setter diagnostic — Approved 2026-11-02

| Phase | Criterion | Initial result |
|---|---|---|
| Feature / capability gate | Pinned image and exact VM resources; read-only tracefs preflight finds private instances, `mono`, and entry/exit events for all four approved time syscalls under the approved root/host-PID/CAP_SYS_ADMIN-only container profile | Pending |
| Feature / observer | Paired/redacted bounded records, non-realtime/failed/missing identities, uncertainty, gaps/drops/cap, cancellation/death and own-instance-only cleanup covered by controlled tests plus relevant Ruff/format/mypy | Conditional on capability gate |
| Batch diagnostic, non-acceptance | One clock-only trace, maximum90s at10Hz; completeness, overhead, hashes and cleanup reported; result classified without causal overclaim and always `acceptance_result=false` | Conditional on capability gate |
| Feature / NC19 review | Existing local rolling scheduler matches its approved amendment/candidate hashes for authoritative transaction, lock order, concurrency4, fairness and cleanup | Pending read-only comparison |
| Batch / V-20 | Original owner/run99.9% within3s and every ready input within5s, plus all load/resource/safety criteria | **Failed/Pending Full Validation unchanged; no W1** |

Failure of the capability gate stops before full observer implementation and tests. Do not
restart/install, relax seccomp/AppArmor, add capabilities, change settings, use another
tracer, run trading/PG/Redis, or repeat the diagnostic. Any clock or production remedy and
any W1 run require a separately approved amendment. Preserve NC17/18/19-r3/20/21/22
results and W2/W3/W4 dependencies exactly as recorded.


### NC-F19-23 execution checkpoint — Incomplete 2026-11-02

| Phase | Result |
|---|---|
| Feature / capability gate | **Failed / Incomplete** — unchanged VM/image and approved observer profile verified, but read-only tracefs bind lacked `trace_clock`; private instances, `mono` and required syscall events could not be established |
| Feature / observer tests | **Not Run by gate** — no full instrumentation was created |
| Batch diagnostic | **Not Run by gate** — no90s trace, trading, PG/Redis or W1 |
| Feature / NC19 review | **Passed (read-only source identity)** — both production files and scheduler tests exactly match the measured NC19 candidate hashes; prior transaction/lock/concurrency4/fairness/cleanup evidence remains valid |
| Batch / V-20 | **Failed/Pending Full Validation unchanged**; W2/W3/W4 remain Not Run |

Observer exited1/noOOM after0.565s and created no tracing instance/events, so instance
cleanup was not applicable. No fallback/configuration/runtime change occurred. The setter
remains Unknown; this is not evidence that no userspace setter exists. Raw sanitized
artifacts and analysis are in [NC23 evidence](evidence/clock-setter-preflight-2026-11-02.md).
A newly approved amendment is required before tracing enablement, another diagnostic,
environment/production changes or W1.


### NC-F19-24 ephemeral tracefs mount validation — Approved 2026-11-02

| Phase | Criterion | Status |
|---|---|---|
| Approval gate | Owner approves temporary in-container tracefs mount and its rollback; same-machine/runtime/resources and no persistent settings change | **Passed — `approve NC-F19-24`** |
| Feature / security | privileged=false; CAP_SYS_ADMIN only; no SYS_TIME/SYS_PTRACE; host PID, network none, read-only root, bounded tmpfs/CPU/memory/PIDs; default seccomp/AppArmor and no Docker socket/host filesystem/secrets | Not Run |
| Feature / mount gate | Exact inventory plus proc capability/seccomp/LSM evidence; tracefs filesystem present; namespace-local mount exposes private instances, `mono` and all required entry/exit events; denial/mismatch stops without fallback | Not Run |
| Feature / observer | Paired event parsing, failed/non-realtime calls, missing identity, redaction, sequence/cap/drop/write failure, uncertainty, cancellation/death and exact-instance cleanup covered; Ruff/format/mypy pass | Not Run |
| Batch diagnostic, non-acceptance | At most one90s/10Hz trace after the mount gate in the same execution; bounded records/overhead/hashes/cleanup reported; `acceptance_result=false` | Not Run |
| Batch / V-20 | Original SLA/load/resource/source/financial criteria | **Failed/Pending Full Validation unchanged; no W1** |

Owner approval covers implementation, controlled tests and one conditional execution.
Default confinement
denial, missing events or unverified cleanup ends NC24 as Incomplete without privileged
mode, seccomp/AppArmor relaxation, restart/install, alternative tracer or repeat. A result
may identify a current-run caller only; it cannot retroactively prove NC19-r3 causality.
Any clock/environment/production repair and W1 still require a later approved amendment.


### NC-F19-24 execution checkpoint — Incomplete 2026-11-02

| Phase | Result |
|---|---|
| Feature / security and observer | **Passed controlled** —45 tests, zero skips; Ruff check/format and mypy pass; exact privileges, pairing/redaction/caps/errors and cleanup branches covered |
| Feature / mount gate | **Incomplete** — authorized container exit2/noOOM after5.772s; first result lost with container tmpfs, so exact stage is unavailable |
| Cleanup-only helper | **Incomplete** — CAP_SYS_ADMIN-only/NoNewPrivs1/Seccomp2 verified, then pre-mount LSM read failed; exact prior instance absence not verified; no second helper |
| Batch diagnostic | **Not valid** — no captured90s trace/result; no setter classification; `acceptance_result=false`; no repeat |
| Feature / NC19 identity | **Passed unchanged** — measured production/scheduler hashes still match |
| Batch / V-20 | **Failed/Pending Full Validation unchanged**; W2/W3/W4 Not Run |

The post-run result-transport/LSM/cleanup-report corrections passed final checks but were
not executed. Preserve the original missing-result failure and helper output as Incomplete;
do not infer no trace/no setter or successful cleanup from absence of records. See
[NC24 evidence](evidence/clock-setter-nc24-2026-11-02.md). A new approved amendment is
required for any further helper, mount/diagnostic, environment/production change or W1.


### NC-F19-25 final same-machine validation — Stopped 2026-11-02

| Phase | Criterion | Status |
|---|---|---|
| Approval / choice | Owner chooses Option A final combined cleanup+conditional trace, or Option B stop clock tracing | **Option B selected — stopped before implementation/execution** |
| Feature / authoritative security gate | Unchanged VM/base; daemon built-in seccomp and no advertised LSM; empty container AppArmor profile; exact Docker restrictions plus guest SYS_ADMIN-only/NoNewPrivs1/Seccomp2. Missing guest LSM file accepted only under this exact combination | Not Run |
| Feature / durable evidence | Unbuffered bounded stdout stages and final result retained in Docker logs; sequence/cap/write/final-loss fail closed; tmpfs secondary only | Not Run |
| Feature / residue and cleanup | Check/remove only literal NC24 path, verify absent before new instance; exact NC25 cleanup/unmount; no enumeration/other-instance mutation; one death-only cleanup helper at most | Not Run |
| Feature / regression | Inventory/LSM combinations, old residue, stdout protocol, mount/events, death/two-name cleanup plus existing NC21/24 tests and Ruff/format/mypy pass | Not Run |
| Batch diagnostic, non-acceptance | One conditional maximum90s/10Hz trace with existing caps/redaction/uncertainty; no repeat; `acceptance_result=false` | Not Run |
| Batch / V-20 | Original SLA/load/resource/source/financial criteria | **Failed/Pending Full Validation unchanged; no W1** |

Option A stops before mount on inventory drift and before trace on residue-cleanup/preflight
failure. Any missing/dropped evidence or unverified cleanup is Incomplete. NC25 is the last
same-machine ftrace attempt regardless of outcome; no automatic NC26. Option B performs no
runtime action. Owner's SLA amendment selected Option B; no NC25 code/mount/helper/trace,
and this historical table is superseded by the amendment below.


### F-19 revised SLA and activation validation — Approved / Feature passed 2026-11-02

Owner-approved acceptance criteria replace the earlier F19 strict numerical gate for
future/derived evaluations; historical verdicts remain labeled under their original rules.

| Phase | Criterion | Result |
|---|---|---|
| Feature / evaluator limits | Explicit F19_SET5 only: per-owner and run-wide≥99.5%≤3s,≥99.9%≤5s,every ready input≤6s; complete acknowledgements, zero clock/stream-order errors; F-18/default unchanged | **Passed** — separate service/tail/absolute counters and verdicts; F18 result schema retained |
| Feature / boundaries | Exact3/5/6-second boundaries, aggregate/owner disagreement, multi-input acknowledgements, missing/pending/clock/order failures and unchanged F-18 behavior | **Passed** — 40 non-DB evaluator tests; missing/pending cover F18 and F19 explicitly |
| Feature / offline evidence | Re-evaluate immutable NC17 raw inputs with hashes and current ordering guard; separate derived result; verify run99.858278%/worst owner99.575487%≤3s, run99.999673%/worst affected owner99.967346%≤5s,max5.034698s≤6s | **Passed as derived Feature evidence only** — 918703/918703 acknowledged, zero clock/order errors; original Failed unchanged |
| Feature / unchanged safety | All functional, stop, idempotency, fail-closed, financial, source/resource/counter criteria and prior production/DB tests remain valid because runtime code is unchanged | **Passed by unchanged-runtime diff and retained evidence**; all 30 non-SLA acceptance terms crosswalked (26 Passed, 4 W1 Not Applicable) |
| Development gate | Affected evaluator regression and Ruff/format/mypy pass; diagnostic observer excluded from release candidate; no workload rerun | **Passed** — 40 tests; Ruff format/check and mypy clean; NC23/24 setter observer source/tests removed, artifacts retained |
| Batch / System Ready | One workload on final integrated candidate after Paper+Live dependencies complete; all revised SLA plus existing safety/load/source/resource gates pass before simultaneous activation | Pending Full Validation / Dependencies |

Do not use NC17's derived pass as a release pass: NC19 scheduler and final integrated
candidate postdate that run. Do not run W1 during this amendment. Paper/Live remain off
together until all release gates pass; automated validation still sends no real Live order.
NC25 and further clock tracing are stopped. The derived result is in
`validation-artifacts/f19-set5-20261101/revised-sla-20261102/derived-result.json`; analysis
and immutable-source hashes are summarized in
`evidence/revised-sla-evaluation-2026-11-02.md`.
