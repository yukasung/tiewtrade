# NC-F17-OBS-03 — Observer timing ขณะรับโหลดสั้น 20 บัญชี

สถานะ: **Approved A — implementation/tests; review/refactor ก่อนหนึ่ง campaign**
วันที่: 2026-11-16
ขอบเขต: amendment F-17 ใน branch เดิม ไม่มี production/strategy feature ใหม่
ฐาน: [OBS-02 result](evidence/endurance20-20261115/obs02-result.md),
[LEASE-02](publisher-lease-load-diagnostic-plan.md),
[FENCE-01](publisher-fence-observation-plan.md),
[OBS-01](observed-w3-fail-fast-plan.md)

## หลักฐานและเหตุผล

OBS-02 เก็บครบ30fixture captures ไม่มี timeout; cold median76.765ms/max80.649ms,
reused median11.678ms/max56.147ms, known-blocker median13.355ms/max38.153ms
ไม่มี20worker load จึงยังแยกสาเหตุ TimeoutError ของ OBS-01 ไม่ได้
OBS-01 ล้มตอน activity capture หลัง publisher statement จบแล้ว ไม่มี blocker rows
จึงห้ามสรุปว่า lease/financial fence หรือ server commit เป็นสาเหตุ

A — แนะนำ: เพิ่ม timing เฉพาะ sampler จริง แล้วหนึ่ง SMOKE เดิม ไม่เปลี่ยน trigger
B — หยุดที่หลักฐาน OBS-02: ไม่เสียเวลาทดลองเพิ่ม แต่สาเหตุใต้โหลดจริงยังไม่ทราบ
การรัน4hซ้ำตอนนี้ไม่ใช่ทางเลือกที่แนะนำ เพราะยังไม่มีหลักฐานแก้สาเหตุ

## Requirements

- `PAPER_INTERNAL20_V1 / SMOKE`:20บัญชีจำลอง,400baseline orders,20workers,
  6cycles/บัญชี รวม600commands ที่2/s วัด5นาที ไม่มี scheduled faults
  ใช้ poll4/claim coordination,source cadence,financial/final-tail/resource checks เดิม
- หนึ่ง preflight120s/7samples ก่อน fixture แล้วสร้างฐานว่าง/Redisติด ownership label
  ใช้ simulated accounts ทั้งหมด ไม่แตะบัญชีเจ้าของ/Live หรือหยุดบริการอื่น
- เพิ่ม `--publisher-fence-timing` defaultoff เฉพาะ SMOKE นี้ ต้องเปิด lease observer,
  fence observer และ fail-fast ครบ; ปฏิเสธ clock recovery/controlled delay/diagnostics
  อื่น,worker-only,W3,profileอื่น ก่อน fixture; W3 flags/default เดิมไม่เปลี่ยน
- ขยายการยอมรับ fail-fast เฉพาะชุด flags ใหม่ข้างต้น ใช้ failure signal และ cleanup
  ของ OBS-01 เดิม ไม่เพิ่ม retry/reacquire หรืออนุญาต SMOKE fail-fast ทั่วไป
- เรียก sample เดิมครั้งเดียวใน monitor task เดิม วัด checkout/setup,SETสองครั้ง,
  clock,activity,locks,session exit โดยไม่ global patch หรือย้าย task
- คง trigger เฉพาะ publisher statement ที่ยังไม่จบตั้งแต่1s และ monitor cadenceเดิม
  ไม่มี forced/periodic captures เพื่อทำให้มีข้อมูล หากไม่มี trigger ให้บอกไม่มีเหตุการณ์
- คง collector timeout1s,statement500ms,lock200ms,rowlimits128/8192,
  readonly/isolation/pool inventory,lease5s,SQL/fences/guard และสูตรเงินเดิมทั้งหมด
- ผูก timings กับ actual PID/stage/tick และ statement association เดิม เก็บ64ล่าสุด
  พร้อม failed capture แรก รวม counters ทุก outcome ไม่เขียน diskทุกtick
  loop-lag ใช้ bounded aggregate แบบ OBS-02 และระบุว่าไม่ใช่ per-query attribution
- Missing/invalid timing หรือ IO failure เป็น Incomplete; รักษา primary exception
  และ Failed ที่พิสูจน์แล้ว เก็บ failure receipt แยกแม้ normal summary เขียนล้ม
- เวลา spans รวม driver/scheduling/network ไม่เรียกว่า server-only time
  เป็น diagnostic overhead ไม่ใช้แทน performance acceptance หรือแก้เกรดรอบก่อน

## Plan / reuse

1. ย้าย timing primitives ของ OBS-02 ไป helper harness ที่ใช้ร่วมกันได้หากจำเป็น
   โดยคง standalone tests/behavior; ไม่ import runner orchestration เข้า sampler
   ใช้ instance-scoped adapter ใน FenceObservation monitor เท่านั้น ไม่มี global patch
   idle capture ยังปฏิเสธ concurrent access ตามเดิม; ไม่ bypass guard ของ OBS-02
2. ต่อ flag ผ่าน workload/campaign parent-only และ LoadLeaseObserver; reuse
   `with_publisher`, `finish_observed_cleanup`, `signal_failure`, sampler done callback,
   `finalize_evidence`, exact pool inventory และ independent failure witness เดิม
   ป้องกัน task ลูกเขียน timings ของ monitor; temporary diagnostic state ไม่ใช่
   persistent session/business storage และไม่เพิ่ม infrastructure
3. Targeted tests: invalid flag matrix/default/W3 regression, once-only/result/exception,
   timing task isolation/retention/partial errors/IO failure; fail-fast พร้อม real source
   error,cancellation/startup/final-tail และ primary priority
   real PostgreSQL read-only/actual blocker/rollback/lock-release และ pool return
   ตรวจ Ruff/format/mypy เฉพาะส่วนที่กระทบ ใช้เงิน/safety evidence ที่ยัง valid ต่อ
4. ผ่าน owner review → แก้ findings → owner refactor → affected checks ตาม AGENTS
5. Pin candidate/config/migrations/copied runner แล้วหนึ่ง preflight หากไม่ผ่านหยุด
   ไม่รอวน; ผ่านแล้วสร้าง owned DB/Redis และรันหนึ่ง SMOKE ตาม profile ข้างต้น
6. เมื่อ sampler/publisher ล้มให้ safe-stop ด้วย supervision เดิม เก็บ timings,
   committed cursor/owner/generation ผ่าน independent witness ก่อน cleanup
   ไม่ส่ง publication/คำสั่งทดแทนเพื่อให้ครบ600
7. Join owned tasks/processes ตรวจ connection/locks/source bindings และ cleanup
   เฉพาะ resources ที่พิสูจน์ ownership ได้; ถ้า childยังอยู่หรือล้างไม่ได้ retain/report
   ไม่ force drop/kill หรือหยุดบริการอื่น

คาด experiment รวม10–15นาที จำกัด1200sตั้งแต่เริ่มpreflight รวมcleanup
สำรองcleanup120s; เวลานี้ไม่รวมพัฒนา/review/refactor/targeted tests
ติดตาม campaign ต่อเนื่องจน result/cleanup เสร็จ แจ้ง progress ระหว่างรอ
ไม่เริ่ม4h,commit/push/CI/merge ในขอบเขตนี้

## Validation / ผลที่ยอมรับได้

Feature: tests/static ครบตามข้อ3ก่อน campaign; ไม่มี default/production behavior change
Diagnostic: รายงาน workloadจำนวนจริง/ระยะจริง,เงิน/ออเดอร์/positions/final-tail/
resource ทุกข้อเดิม,ทุก sampler outcome,retained bounds/source stability/cleanup
ถ้า sampler ไม่ถูกเรียกเลย ให้รายงาน zero triggers/Not Reproduced ไม่ใช่ timing Passed
ถ้า timeout เกิด ให้ระบุ last completed/current phase และเวลาเท่าที่วัดได้จริง
ถ้าไม่เกิดซ้ำใน5นาที ไม่ถือว่าแก้สาเหตุหรือผ่าน4h และไม่เพิ่มเวลาหรือรันอีกอัตโนมัติ
Batch/Release: คง W3/OBS-01 Incomplete และ final financial/rebuild/Release ที่ค้าง
ผล diagnostic ไม่ทำให้ F-17 Completed

## จุดหยุด / การอนุมัติ

OBS-02 อนุมัติเพียงหนึ่ง campaignและหยุด/report ซึ่งทำครบแล้ว
OBS-03 เพิ่มการต่อ timing เข้ากับ monitor และขยาย fail-fast ไป SMOKE เฉพาะทาง
จึงเสนอขอบเขตให้เจ้าของอนุมัติก่อนแก้ source/เริ่ม experiment ตามจุดหยุดเดิม
การจัดทำแผนนี้ยังไม่ใช่ approval ไม่มี source change หรือ campaign ใหม่
เมื่ออนุมัติ ให้ทำ implementation/checks ต่อเนื่องถึง review gate
หลังหนึ่ง campaign ให้หยุด/report พร้อมข้อเสนอจากหลักฐาน ไม่แก้ publisher/เกณฑ์เอง

## Implementation binding ก่อนแก้

เจ้าของ approve แล้ว ย้าย CaptureTiming/TimedConnection/TimedEngine/LoopLag จาก OBS02
ไป profile_observer_timing.py และ re-export ผ่าน import เดิมเพื่อคง standalone callers
FenceObservation เพิ่ม timing=False แบบ instance scoped; monitor เรียก timed wrapper
ใน task เดิม เก็บ64ล่าสุด/failedแรก/countsและ actual observation metadata
lag task มี ownership/join และส่งความล้มเหลวผ่าน monitor/fail-fast เดิม
คง query/trigger/cadence/defaultpool เดิม ไม่แก้ production หรือเริ่ม campaign ขั้นนี้

### Test fixture correction ก่อนแก้

Expanded regression รอบสอง:211Passed/2Failed เฉพาะ SMOKE fault/duration เพราะ
mock_parent เดิมเป็น legacySMOKE ไม่มี fault schedule และไม่มี internal duration wait
ไม่ใช่ผลของ SMOKE20 จริง แก้ matrix ให้ fault เฉพาะW3 และเพิ่ม duration test
ด้วย internal20 profileจริงใน parent/fakeI/O ตาม pattern test_workload_latency เดิม
คง fail-fast/no-next-phase/cleanup assertions ไม่แก้ runtime/timeout หรือเกรดรอบล้ม

## Implementation checkpoint

[ผล](evidence/endurance20-20261115/obs03-implementation.md):79affectedPassed+
133unchangedPassed=212distinct;static8files/independentcleanupPassed
คง prior211Passed/2fixtureFailed ตามหลักฐาน แก้testsให้ตรงเส้นทางโดยไม่แก้เกณฑ์
รอ owner review code; preflight/campaignยังNotRun ไม่มีGit/CI/merge

## Review M1 fix — ก่อนแก้ source

เจ้าของสั่งแก้ไข: fault injection ยืนยัน lag_task.cancel แล้ว close ทันทีทำให้ callback
เห็น stop=True และยอมรับ NO_TRIGGER ทั้งที่ lag task ถูกยกเลิก
normal close ของ lag ใช้ stop Event ไม่ใช้ cancel จึงให้ cancellation เป็น evidence loss
เสมอ ใช้อำนาจแก้ harness ภายใน AGENTS โดยคง timeout/production/SQL เดิม
เพิ่มหลักฐาน lag_task_completed แยกจาก joined และบังคับ flush ต้องสำเร็จจริง
report ตรวจ terminal cancellation/exception โดยตรงไม่รอ callback order
เพิ่ม tests cancelก่อนtaskเริ่ม/ก่อนclose/หลังcallback และ normalclose
ตรวจ sampler/receipt/primary regression; ไม่รัน campaignก่อน review/refactor gate เดิม

### ผลแก้ M1

[Checkpoint](evidence/endurance20-20261115/obs03-m1-fix.md):170affectedPassed,
5regression casesใหม่,static3files/independentcleanupPassed
รอ owner refactor; campaignNotRun คง timeout/SQL/เงิน/ผลเดิม

## Refactor M1 — ก่อนแก้

เจ้าของสั่ง refactor: runtime guard/completion check ชัดเจนและใช้ของเดิมแล้ว คงไว้
ลดการอ่าน report ซ้ำใน tests M1 ให้ snapshot หนึ่งครั้งแล้วตรวจ timing จาก snapshot เดียว
คง assertions/callback ordering/cleanup เดิม ไม่สร้าง abstraction เพิ่ม
ตรวจ tests ที่กระทบและ static; reuse170realPG/regressionsที่ runtimeไม่เปลี่ยน
จากนั้นเตรียม coordinator จากOBS01 เปลี่ยนเป็นSMOKE600commands/300s/1200s cap,
flags timing+lease+fence+failfast ไม่มีclockrecovery; onepreflight/owned DB+Redis/pins/
source checks/120s cleanup reserve เดิม ก่อนหนึ่ง campaign ตามอนุมัติ

## Completed campaign checkpoint

[OBS-03 result](evidence/endurance20-20261115/obs03-result.md): refactor4tests/static Passed; one SMOKE completed600commands in460.986s including preflight/cleanup. Workload/global/resource Passed, timing NO_TRIGGER (0 samples), not reproduced in5minutes. Independent cleanup/source binding Passed. Stop/report; W3Incomplete/F17notCompleted unchanged. No further campaign/Git.
