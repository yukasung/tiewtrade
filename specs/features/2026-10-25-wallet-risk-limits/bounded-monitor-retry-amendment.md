# F18-R24 — Bounded monitor owner-lock retry within a sweep

สถานะ: Approved — เจ้าของสั่ง “เริ่มทำ” หลังเสนอ R24 วันที่ 2026-10-29; ข้อเสริม R24-A อนุมัติด้วยคำสั่ง “เริ่มทำ” วันที่ 2026-10-29
วันที่: 2026-10-29

## หลักฐานและข้อจำกัด

อ้างอิง checkpoint `evidence/m5-final-candidate.md` หัวข้อ rolling diagnostic:
owner6442c1ed… frames8925–8927 ใช้3.187217s มี owner-lock timeoutสองครั้ง
และรอระหว่าง failed attempt กับครั้งถัดไปรวม1.766724s; ครั้งสำเร็จใช้42.663ms.
ไม่พบ risk CPU throttle เพิ่มในช่วงนี้ แต่ยังไม่ทราบ lock holder/เวลาปล่อยlock.
ดังนั้นพิสูจน์ว่ามี revisit delay แต่ยังพิสูจน์ไม่ได้ว่า retry จะจับlockได้เร็วขึ้น.

R15 ใช้ try-lock และตรวจownerครั้งเดียวต่อsweep; ทดลองแล้วไม่ช่วยและย้อนกลับ.
R24 คง blocking acquisition100ms และ scanner/ordering ปัจจุบัน เปลี่ยนเฉพาะ
โอกาส retry หลัง failed acquisition; ไม่เพิ่ม concurrency หรือใช้ try-lock.
ห้ามอ้างว่าจะลดทั้ง1.767s: retries ต้องรอ first attempts อื่น และอาจยังติดlock.

## วิธีทดลองที่เสนอ

- เฉพาะ standalone run_risk_monitor_round; financial writers/request/stop ไม่เปลี่ยน.
- ใช้ scanner eligibility, UUID fairness cursor, due_at ordering, limit100,
  semaphore/pool4 และ sleep20ms เดิม ไม่สแกนฐานข้อมูลเพิ่มเพื่อเลือก retry.
- Retry เฉพาะ DatabaseTimeoutError ที่เกิดระหว่าง lock_risk_owner ก่อนอ่านsnapshot
  และต้องออกจาก transaction/rollback สำเร็จแล้วเท่านั้น หากcleanupผิดพลาดไม่ retry.
  Timeout ใน replay/snapshot/commit หรือ source unavailable ไม่เข้าทางนี้.
- ทุกownerได้ first attempt ตามลำดับเดิม ห้าม retry แซง owner ที่ยังไม่ได้เริ่ม
  first attempt. เก็บ failed owners ตามลำดับใน selected page เดิม.
- เมื่อ first attempts ทั้งหมดเริ่มแล้ว เปิด retry ได้ขณะที่งานท้ายpageยังทำอยู่:
  ใช้ semaphoreเดิม, ไม่เกิน4retry attemptsต่อpage และแต่ละownerไม่เกิน1retry.
  Ownerอื่นยังคง eligible สำหรับ sweepถัดไปตามcursorเดิม; ไม่รอ busyowner วนซ้ำ.
- Retry เริ่มไม่เร็วกว่า100msหลัง failed attempt สิ้นสุด; รอนอก transaction
  และนอก semaphore. หากถึงเวลาที่ทุก first attempt จบแล้วก่อน retry เริ่ม
  ให้ข้าม retry ที่ยังไม่เริ่มและเข้าสู่รอบปกติ ไม่เพิ่มการรอหลังpageเพื่อ retry.
  Retry ที่เริ่มแล้วต้องจบ/rollbackตามสัญญาเดิมก่อนออกจากround.
- เปิด transaction ใหม่ อ่านข้อมูลใหม่และทำ full checks เดิม จับownerlock
  ผ่านcommit; publication fence/replay/latch/idempotency ไม่ลดหรือข้าม.
- Result processed/deferred/skipped นับแต่ละcandidateครั้งเดียวตามผลสุดท้าย
  ไม่เพิ่มตัวนับซ้ำจาก attempts. next_owner มาจากselected pageเดิม.
- ไม่เปลี่ยน public API/schema, Money/Quantity, resources, rates/deadlines,
  p95<=500ms/p99<=1s, every-ready-input<=3s หรือเกณฑ์เงินอื่น.

## ใช้ของเดิมและขอบเขตโค้ด

ใช้ `backend/src/tiewtrade/services/engine/risk_limit.py::run_risk_monitor_round`,
`infra/risk_limits/dispatch.py::lock_risk_owner`, `infra/db/session.py::user_session`
และ replay/acknowledgement pathเดิม. ไม่สร้าง worker, connection pool หรือ
scheduler frameworkใหม่. เพิ่มเฉพาะ bookkeepingของfirst attempt/retryในround.
ตรวจ callers ที่ `services/engine/risk_limit_main.py` และ metrics contracts.

## Tests และจุดหยุดก่อน workload

ใช้/ขยาย `backend/tests/infra/risk_limits/test_scheduler.py` และ
`test_monitor_price_hint.py` ตามผลกระทบ:

- barrier-controlled busyownerปล่อยlockระหว่างpage: retryสำเร็จก่อนpageจบ;
  หากยังbusyให้defer ไม่วนเพิ่ม และไม่อ่าน/แก้stateก่อนlockสำเร็จ.
- ownerที่ยังไม่เริ่มไม่ถูกretryแซง, ไม่เกิน4active transactions/4extraattempts,
  budget exhaustion/fairness across pages, first attemptsจบก่อนcooldown,
  cancellation/rollback failure ไม่ทิ้งtask/lockหรือretryหลังround.
- แยก acquisition timeout ออกจาก snapshot/replay/commit timeoutอย่างถูกต้อง;
  results/cursor นับcandidateครั้งเดียวและค่าปกติไม่เปลี่ยน.
- owner isolation, concurrent financial writers, publication fencing,
  transient breach/durable latch, request/stop progress และ duplicate effects.
- lint/format/types ของdiff/callers ที่เกี่ยวข้อง.

ก่อนรันทดสอบให้แจ้งเวลาตามมาตรฐาน ไม่มีเพดานเวลาที่ใช้ข้าม safety.
หาก deterministic test แสดงว่า retry ไม่มีช่องทำงานก่อนpageจบ หรือ fairness
แย่ลง ให้หยุดและทบทวน ไม่เริ่ม workload เพื่อหวังให้ผ่าน.

## วิธีพิสูจน์ผลและ rollback

ใช้ rolling instrumentation ชุดเดียวกับหลักฐานล่าสุด ทั้งก่อน/หลัง,
100owners×20orders,600s,resources/configurationเดิม มีตัวแปรเดียวคือR24.
บันทึก source/helperhash และข้อมูลที่evict; ต้องครอบคลุมfailure window.
รัน candidateทดลองเพียง1ชุด หลังsafetyผ่าน ไม่รันซ้อน. หยุดเมื่อhard failure.
เปรียบเทียบ input latency/owner revisit และother-owner/request/stopprogress;
ใช้หน้าต่างและinstrumentationเดียวกัน ไม่อ้างเหตุจากmetricต่างrunที่เทียบไม่ได้.
ถ้าไม่มีlock-deferredเหตุให้ใช้retry ผลเป็นInconclusive ไม่ใช่proof of improvement.
ถ้าผลไม่สนับสนุนหรือเกิดregression ให้ย้อนเฉพาะR24 เก็บfailureและตรวจrollback
ตามผลกระทบ ไม่รันซ้ำอัตโนมัติ. แม้diagnosticผ่าน ยังต้องnativeW1–W4ตามแผนเดิม.

## Approval boundary

เป็นวิธี retry/scheduling ใหม่ที่ต่างจาก once-per-sweep เดิม จึงต้องอนุมัติ
ตาม plan.md:301 “ขอ plan amendment ก่อนเปลี่ยนวิธี” และ AGENTS.md.
เอกสารนี้ไม่อนุมัติด้วยตัวเอง และยังไม่มีการแก้runtimeหรือเริ่มtests/workload.


## R24-A — Explicit rollback outcome for the monitor (Approved 2026-10-29)

ตรวจcallerก่อนimplementationพบ `infra/db/session.py::_begin` suppresses
SQLAlchemyError/OSError ระหว่าง transaction.__aexit__ หลังbodyerror แล้วraise
bodyerrorเดิม. ดังนั้น DatabaseTimeoutError ที่ monitorเห็นไม่พิสูจน์ว่าrollback
สำเร็จ ซึ่งไม่พอกับข้อกำหนดR24 “rollback สำเร็จแล้วเท่านั้น” ข้างต้น.
นี่ไม่ใช่หลักฐานว่ามีrollbackfailureเกิดในdiagnostic แต่เป็นช่องว่างของcontract.

เสนอขยายขอบเขตอย่างจำกัด:

1. เพิ่ม keyword-only opt-in `require_rollback_success=False` ที่user_session
   และส่งถึง_begin; เปิดเฉพาะ standalone monitor ที่ใช้R24. Defaultcallersคงเดิม.
2. Opt-inนี้: เมื่อbodyเกิดExceptionและrollbackสำเร็จ ยังคงraise originalerror;
   หากrollbackเกิดSQLAlchemyError/OSError ให้ส่ง typed `DatabaseCleanupError`
   ที่มีข้อความคงที่และตัดdriverexceptionchainด้วยfromNone. Monitordeferทันที
   ไม่ใช้errorนี้เข้าretry. ไม่เพิ่มSQL,ไม่สร้างconnectionหรือmanualROLLBACK.
3. Cancellation/BaseException ยังคงถูกpropagate ไม่แปลงเป็นretryableerror;
   cleanupยังใช้เส้นทางเดิมและไม่มีretryหลังcancel. Connectioninvalidations/
   poolcleanup ต้องคงสัญญาของSQLAlchemyและsessionเดิม.
4. ไม่เปลี่ยนHTTP/publicAPI/schema, financialwriters หรือindicator_read_session
   ที่ใช้boundedcleanup; ไม่เปลี่ยนtimeoutค่าอื่น. เป็นinternalDBcontractเพิ่ม
   จึงต้องขออนุมัติขอบเขตส่วนกลางนี้ก่อนแก้code.

Testsก่อนworkload: successrollbackคงoriginaltimeout; injectedrollbackfailure
ไม่retry/no driversecrets; defaultcallersคงเดิม; cancellationและpoolreuse;
realDB timeout/RLS/isolation ที่test_sessions.py และR24schedulerbarriers.
ตรวจcallers/types/architectureที่เกี่ยวข้อง; sharedDBchangeต้องรวมregression
ตามtesting§7เมื่อcandidateนิ่ง ไม่ถือtargetedแทนด่านส่วนกลางที่ต้องตรวจ.

ยังไม่ได้แก้runtimeหรือเริ่มtests/workload. หากไม่อนุมัติขยายcontract ต้องคงR24
เป็นยังไม่implemented ไม่ลดข้อกำหนดrollback-successหรือเดาว่าcleanupสำเร็จ.


## Experiment outcome — 2026-10-29

R24/R24-A implemented and tested after owner approval. Full backend regression
coverage3828 passed with documented resumes/test-isolation corrections. The single
matched600s diagnostic still Failed:3ready-inputmisses,max3.586173s;
connections_end55 > start44+2. All6000commands and financial oracles passed,
processingp95352.387ms/p99528.084ms,all746104inputsacknowledged, but these do not
replace failed gates. Trace confirms retries occurred and were still blocked.
Per stop rule restored pre-R24 scheduler/session/errors byte-for-byte and removed
experimental test/wrapper additions (archived with candidate). Rollback56checks,
mypy571,ruff/format passed. R24/R24-A are inactive; approval remains history.
Retained only valid Paper-isolation dependency registration and test-fixture input
range isolation fixes. See M5 for hashes and evidence; no second trial started.
