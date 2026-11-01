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
| V-19 | candidate gates | review diff/dependencies Critical/High, affected backend/frontend regression, ruff+format, mypy, lint-imports, frontend lint/types/build, generated OpenAPI diff และ required CI บน candidate สุดท้าย | M5 ก่อน merge | **Partial** — local gates/149 safety tests/340 frontend tests/2 baseline E2E, expanded owner story และ platform route matrix ผ่าน; required remote CI ยังรอ |
| V-20 | ท้ายชุดที่5 Paper integration/full validation | candidate รวม F-18/F-19 ที่นิ่งผ่าน full backend/frontend regression, browser→API→engine, fault/recovery, backup/restore และ W1–W4 ที่เกี่ยวข้องโดยคง F-18 thresholds/profileเดิม; stop oraclesด้านล่างครบ | ท้ายชุดที่5 | Pending Full Validation |
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

### NC-F19-14 owner-isolated one-shot partial trade — Proposed / Needs Clarification

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
  แต่ required CI ของ candidate ใหม่ยังค้าง และ checks นี้ไม่ปิด V-20..24
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

ผล local ข้างต้นผูกกับ worktree ที่ยังไม่ commit ณ 2026-10-31; รายการ Partial และ
Pending Full Validation/Pending Dependency ไม่ถือว่าผ่านหรือ Completed และ required CI ยังต้องรันบน candidate เดียวกัน
