# F18-R8 — ข้าม candidate ที่ claim ไม่ได้ โดยคง1 claimed work ต่อ phase

สถานะ: **Approved** — เจ้าของตอบ “อนุมัติ R8” วันที่2026-10-27 ก่อน implementation

## หลักฐานใหม่หลัง R7

- W1r12 ผ่าน100×20 baseline และpartial-fill oracle แต่ selected-owner
  breach/reset/reseed cycleเกิน60s: offered494/admitted463/completed445/cycles70
- คำขอที่ค้าง transferได้ราว.1–.2s แต่รอ command processingอีก3–4s
- Probe10s บน frozenr12 clone, same source/runtime/roles/aggregate4CPU/2GiB:
  Paper956rounds,375processed,3deferred,578skipped (**60.46% skipped**)
  manual953rounds,65processed,0deferred,70skipped ที่เหลือไม่มีงาน
  skippedรวมclaimNoneและclaim-lost ไม่ได้แยกสองกรณีหรือระบุว่าเป็นownerเดิมทั้งหมด
  เป็น diagnostic ไม่ใช่ W1 acceptance ไม่มี job อื่นซ้อน
- เมื่อใช้ limit1, workerที่ได้ hintซึ่ง ownerยังbusy หรือ hintเก่า claimไม่ผ่าน
  จะจบphaseและsleep20ms แม้มี ownerอื่นพร้อมอยู่ในคิว ส่วนคิวที่เลือกยังคง
  ถูกจัดอันดับแบบเดิม การเพิ่มจำนวน workers/CPU ไม่ได้อยู่ในข้อเสนอนี้

## วิธีที่เสนอให้อนุมัติ

1. แยก **candidate limit20** จาก **successful claim limit1** ของแต่ละphase
   manualและmatching ใน F18-integrated runtime/harness
2. อ่าน hintsไม่เกิน20ตาม due/fairness order เดิม ใช้claim/CAS/owner lockเดิม
   หากclaimคืนNone ให้ลอง hintถัดไปในชุดเดิมจนclaimได้1รายการ หรือหมด20
3. เมื่อclaimได้1แล้วต้องจบphaseหลังprocess/defer/claim-lostของรายการนั้น
   ไม่ไล่claim20รายการเมื่อprocessผิดพลาด ไม่มี retry/sleepในtransaction
4. เปลี่ยนเฉพาะการเลือก hintที่ยังทำงานได้ ไม่ข้ามงานที่ claimได้ก่อนหน้า
   ไม่เลื่อน dueเวลา/ล้าง leaseของcandidateที่ถูกskip ไม่ข้าม FIFO ภายในowner
5. Default ของ bounded round functions และ F15 standalone harnessยังเหมือนเดิม
   (candidate20,ไม่มีclaimed limitเพิ่มเติม) ตัวเลือกใหม่ใช้เฉพาะF18 runtime
6. Productionและ F18 workloadใช้limitsเดียวกันและบันทึกในmanifest
7. คง10Paper+1risk, CPU/RAM/pools/roles, input/command rates, owner concurrency,
   tick20ms, claim30s, source/replay budgets, backoff และfencesทุกตัวตามเดิม
8. ไม่เปลี่ยน Money/Quantity/fee/quantity/PnL/risk/reset/stop/idempotency หรือเปิดLive
9. คงW1/W2/W3 10/5/30นาที,100×20, progress60s,p95<=250ms/p99<=1s,
   every ready evaluation<=1s และ financial/resource/fault/restore oracles

R7อนุมัติให้แต่ละphaseพิจารณาเพียง1candidate ข้อเสนอนี้เปลี่ยนเป็นเลือกใน20
แต่ทำงานได้เพียง1claimed item จึงขออนุมัติใหม่ตาม F18 plan301 ก่อนเขียนcode
ไม่ตีความการอนุมัติ R7 ว่าอนุมัติวิธีเลือกใหม่นี้ด้วย

## ขอบเขตและการตรวจหลังอนุมัติ

- `services/engine/{manual_order,paper_order}.py`: optional bounded claim budget;
  defaultbehaviorเดิม และ skipที่claimNoneไม่กินclaimed budget
- `paper_order_main.py` กับ F18 harness: explicit20candidates/1claim
- reused F15 workload worker: optional claim budget defaultNone ไม่เปลี่ยนF15
- Tests: busy/stale first candidateไม่กันownerถัดไป, claimเดียวต่อphaseรวมerror,
  ownerเดียว/ต่างowner/CAS/lease/FIFO, originaldefault20 และ cancellationcleanup
- Reuse correctness evidenceที่ไม่เปลี่ยน; ตรวจ affectedclaim/worker/manual/risk/
  stop/rollback/idempotency และcompositionให้ครบ
- เปรียบเทียบcounterprobeแบบเดิมทีละชุด; หลังprogressดีขึ้นจึงfullW1→W2→W3
  พร้อมเก็บoldFailed/Partial ไม่ถือprobeแทนacceptance
- W4r9 reuseได้หากไม่เปลี่ยนrestore/replay/financial contracts; หากพบผลกระทบใหม่
  ให้ตรวจเฉพาะส่วนนั้นเพิ่ม ไม่สร้างfixtureใหม่โดยไม่มีเหตุผล
- ถ้าไม่ดีขึ้นให้ย้อนเฉพาะscheduling experimentนี้ บันทึกผล และขอamendmentก่อน
  เปลี่ยนวิธีอื่น ไม่มีการเพิ่มbudgetหรือลดthresholdเพื่อทำให้ผ่าน

ผนวก R8 ใน plan ก่อน implementation ตามการอนุมัติของเจ้าของ
