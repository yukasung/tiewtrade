# F18-R9 — same-pair admission แทน resting poll ที่ทำงานซ้ำ

สถานะ: **Approved** — เจ้าของตอบ “อนุมัติ R9” วันที่2026-10-28 ก่อน implementation

## หลักฐานและขอบเขต

W1r15 บน0055/currentR8 ผ่าน baseline100×20 และ partial-fill loss0.05
แต่ Failed60s ขณะรอ reseed:525offered/505admitted/491completed/84cycles;
เจ้าของที่ใช้ทดสอบมี20stop targets และ39unique requests (20baseline+1BUY+
18reseed) ตอนหยุด ทุก command ของ7requestsล่าสุดมีผลSUCCEEDED จึงมี progress
แต่ยังสร้างreseed20ใบไม่ทัน deadline ไม่ใช่หลักฐานว่าคิวสูญหายหรือเงินผิด

ตัวเลขนี้ไม่พิสูจน์ root cause เดียวหรือรับประกันผลของ R9: `due_orders` ปัจจุบัน
เลือกตามnext_attempt_at ต่อowner; accepted resting NEW ที่ยังมีงานmatching
สามารถอยู่หน้าคำขอNEWที่ยังไม่admit การเลือกNEWของคู่เดียวกันอาจทำทั้งadmission
และงานmatchingของออเดอร์เดิมผ่าน checkpointเดียว ลดรอบที่ทำงานคู่เดิมแยกกัน
`_process_new` และ `reschedule_processed_orders` ทำงานรวมต่อpairอยู่แล้ว
นี่เป็น hypothesis ที่ต้องวัด ไม่เพิ่มdeadlineหรือกล่าวว่าแก้แล้วจะผ่าน

สามMedium findings ซ่อมแล้วและมีหลักฐานใน [M5](evidence/m5-final-candidate.md)
แต่ High integrated progress/SLA ยังเปิด; คง production admissionปิด

## วิธีที่เสนอให้อนุมัติ

1. ใช้เฉพาะ F18 runtime/harness ด้วย explicit selector option; F15 standalone
   และ default functions คงเดิม จำนวน20candidate hints/1successful claimต่อphase
   แบบR8,10Paper+1risk, pools, tick, CPU/RAM/rates และทุกthresholdคงเดิม
2. หาoriginal due headต่อownerตามR8ก่อน เก็บnext_attempt_at/command_idของhead
   เป็นanchorสำหรับลำดับfairnessข้ามowner ห้ามใช้เวลาNEWใหม่มาเปลี่ยนลำดับowner
3. พิจารณาแทนheadได้เฉพาะheadที่เป็นNEWซึ่งadmitสำเร็จแล้ว มีactive remainder
   และยังต้องpoll matching; ไม่แทนCANCEL หรือคำสั่งที่ยังไม่มีผลadmission
4. candidateที่จะใช้แทนต้องเป็นdue NEWที่ยังไม่admit ของepisode/pairเดียวกับhead
   และเป็นคำสั่งที่ยังไม่เสร็จซึ่งมาก่อนตามลำดับเดิม ห้ามข้ามpending NEWคู่อื่น
   หรือCANCEL; หากมีdue CANCELใดในowner ให้ใช้original selection
5. จำกัดpreferenceกับownerที่มีconfigured/unlatched setting และnonpending READY
   monitor hint เท่านั้น Hintไม่ใช่authorization: workerยังอ่านauthoritative facts
   และทำAPI/bridge/admission/final fenced risk gatesครบตามเดิม
6. อนุญาตpreferred claimไม่เกิน1ครั้งต่อoriginal anchor(command_id,next_attempt_at)
   บันทึกguard `preferred_for_due` ของhead atomicกับcandidate claim ภายใต้owner lock
   โดยไม่เลื่อนhead.next_attempt_at หากpreferredงานไม่ครอบคลุมจนexisting reschedule
   เลื่อนheadจริง รอบถัดไปต้องกลับoriginal head ไม่prefer NEWอื่นซ้ำที่anchorเดิม
   ครอบคลุมrefusal/defer/crash/lostack ไม่ใช้successของNEWเป็นข้อยกเว้นล้างguard
   เพื่อไม่ให้risk/source failureหรือคิวNEWขวางreduction/cancel/resting workซ้ำๆ
7. hintต้องผูกactual candidate due/CASและoriginal anchor; claimภายใต้owner lock
   ตรวจanchorและเงื่อนไขแทนซ้ำ หากstale/มีcancel/claimอื่น/episodeเปลี่ยนให้คืนNone
   แล้วใช้bounded fallbackเดิม ไม่บังคับclaimหรือแก้scheduleของcandidateที่skip
8. เมื่อเลือกได้ ใช้claim/process/checkpoint/rescheduleเดิมเพียง1งาน ไม่เพิ่ม
   งานต่อtransaction ไม่merge financial events ไม่skip/coalesce priceหรือbook inputs
   ไม่ข้ามmatching FIFOของออเดอร์เดิม ไม่เปลี่ยนeligible_at/fees/quantity/IDs
9. เพิ่มเฉพาะrouting projectionในdispatchแบบadditive: command kind/pair,
   admitted/active classification ที่nullable UNKNOWN→fallback และanchor guard
   อัปเดตatomicจากcommand/header/result/status factsเดิมใต้ENGINE owner/RLS;
   statusไม่เปลี่ยนไม่เขียนhintซ้ำทุกcheckpoint ไม่คัดลอกเงิน/quantity/payload
   SCANได้เฉพาะrouting metadata และconfigured/latch/reason/pending hint columns
   ที่จำเป็น ห้ามgrant SELECT raw payload/amount/book/secret หรือwriteแก่SCAN
   ไม่เพิ่มruntime BYPASSRLS role และไม่ใช้global functionเปิดfinancial payload
   Engine recheckอ่านfactsจริง ไม่รับhintเป็นauthorization; hintไม่ครบ/stalefallback
   migration backfill/old-new overlapต้องปลอดภัย; rolloutเพิ่มschemaก่อนoption,
   downgradeปิดoption/กลับR8ก่อนลบrouting projection ไม่ลบfinancial history
10. เปิดใช้เฉพาะหลังaffected tests ผ่าน บันทึกoption/schema/runner/sourceในmanifest
    หากไม่ช่วยหรือเกิดsafety/fairness regression ปิดoptionกลับR8และเก็บFailedเดิม
    ไม่มีการเพิ่มbudget/ลดSLA/เปลี่ยนสูตรหรือเปิดLiveเพื่อให้ผ่าน

## สิ่งที่ต้องพิสูจน์หลังอนุมัติ

- selector/claim raceบนPostgreSQLจริง: same-pair/no-other-pair preference,
  original owner fairness anchor, earlier pending command/CANCEL, stale hint,
  two workers, lease expiry/CAS, owner/episode isolation และdefault F15 unchanged
- source/risk unavailable, failed preferred NEW, breach/reset/stop/fill races:
  reduction/cancelไม่starve, oldstopยังมีผล, ไม่ฟื้นqueued BUYหรือคืนreservationซ้ำ
- checkpointของNEWต้องconsume input sequenceเดิมให้ทุกactive orderของpair;
  maker FIFO/eligible_at/partial fills/UUIDs/ledger/positionsตรงoraclesเดิม
- routing hints/guard atomicกับclaim/result/status transitions, missing hints,
  guardsหลังcrash/rollback/lostack; migration/rolling overlapและaffectedrestore/
  grants contracts ไม่มีSCANNfinancial/secret accessหรือwrite rightsใหม่
- ตรวจเฉพาะdependenciesที่กระทบ ใช้evidenceเดิมส่วนที่ยังvalid จากนั้นsame60s
  selected-owner scenarioและfullW1; ผ่านแล้วจึงW2→W3ทีละชุด ไม่รันdiagnosticซ้อน
- คง100×20,10Hz,rates10/100/10,W1/W2/W3 600/300/1800s,progress60s,
  p95≤250ms/p99≤1s,every ready evaluation≤1s และfinancial/resource/fault gates

## เหตุที่ต้องอนุมัติใหม่

[R8ในplan](plan.md#r8--bounded-hint-fallback-and-one-claim-per-phase-approved2026-10-27)
อนุมัติให้ใช้ordered due/claim selectionเดิมและรักษาFIFO/fairness การเลือกNEW
แทนaccepted resting headเป็นวิธีเลือกใหม่ จึงไม่ถือว่าการอนุมัติR6/R7/R8หรือ
คำสั่งแก้findingsอนุมัติรายละเอียดนี้แล้ว ต้องอนุมัติamendmentก่อนเปลี่ยนselector
ตามplan§5บรรทัด301และAGENTSหัวข้อการเปลี่ยนแผน; ส่วนแก้ที่อนุมัติแล้วไม่ต้องขอซ้ำ
