# F-17 — ข้อเสนอการตรวจรับ Paper ภายใน: 10 ผู้ทดลอง / 20 บัญชี

สถานะ: **Approved A - owner approved NC-SET4-12 requirements amendment, plan and validation on2026-11-06; section9 production-fix amendment Approved A on2026-11-06; section10/11 Approved A on2026-11-07; section12 Approved A on2026-11-07; section13 Approved A on2026-11-07; section14 revised plan Approved on2026-11-07; section15/16/18 Approved on2026-11-07**
วันที่: 2026-11-06
Authorization: scoped harness/checks and conditional campaign in section5; Git/deploy/Live still require their existing gates.
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [validation](validation.md),
[แผนรวม 100 บัญชีที่อนุมัติแล้ว](integrated-paper-acceptance-plan.md),
[roadmap จุดปล่อยที่ 1](../../roadmap.md), [testing §7](../../standards/testing.md)

## 1. เหตุผลและทางเลือก

Roadmap กำหนดจุดปล่อยแรกเป็น Paper สำหรับเจ้าของและคนที่รู้จัก ห้ามเปิดรับสมัครทั่วไป
เจ้าของยังไม่ทราบจำนวนผู้ใช้พร้อมกัน จึงเสนอเชิญผู้ทดลองรวมไม่เกิน10คน และตรวจรับ
20บัญชีที่มีออเดอร์ทำงานพร้อมกัน ตัวเลขนี้เป็นขนาดกลุ่มทดลองที่เสนอและส่วนเผื่อจำนวนบัญชี
ไม่ใช่การคาดการณ์ผู้ใช้จริงหรือผลพิสูจน์ความจุแล้ว ความหนักต่อบัญชียังคงตาม fixture เดิม

ผลล่าสุดที่100บัญชี: baseline2000สำเร็จ แต่รอบวัดหยุดที่60s cycle bound;
completed917/3000 commands,145/600 cycles และ partial p95=470.510ms>250ms
การแก้ตัวสรุปผลผ่าน66 targeted tests แต่การคำนวณข้อมูลเดิมใหม่ยังไม่ผ่านp95
จึงไม่มีหลักฐานว่าปรับจำนวนบัญชีแล้วจะผ่านโดยอัตโนมัติ ดู
[ผลรอบล่าสุด](evidence/recovery-20261106/README.md) และ
[การแก้ตัววัด](../2026-10-18-paper-order-matching/evidence/latency-population-20261106/README.md)
รอบล่าสุดใช้566.039s; เวลารวมทุกการทดลองย้อนหลังยืนยันไม่ได้ เพราะ raw artifacts เดิมสูญหาย

| ทางเลือก | ผลต่อผู้ใช้และความเสี่ยง | ต้นทุน/คำแนะนำ |
|---|---|---|
| คง100บัญชีเป็นด่านก่อนทดสอบภายใน | ต้องแก้ implementation จนผ่านความจุเดิมก่อน; ไม่เปลี่ยนช่วงตรวจรับ | ยังประเมินเวลาแก้คอขวดให้ผ่านไม่ได้; เก็บเป็นทางเลือกได้ |
| เพิ่มโปรไฟล์ภายใน20บัญชี โดยคงเป้าหมาย100เดิม | จำกัดกลุ่มทดลอง10คน; ผล20ไม่รับรอง100หรือการใช้งานสาธารณะ; ยังต้องแก้หาก20ไม่ผ่าน | **แนะนำ** ให้ตรงจุดปล่อยภายใน; ต้องพัฒนา/ตรวจ harness และทดสอบใหม่ตามเอกสารนี้ |

ไม่เสนอเพิ่ม250msเป็นค่าที่ครอบผลล้มล่าสุด หรือเพิ่ม60sเพื่อให้ cycle จบช้าลง
ระยะ30นาที/10นาที/4ชั่วโมงและกฎการเงินเดิมยังอยู่ จึงไม่ได้ลดเวลาทดสอบทั้งหมดตามจำนวนบัญชี

## 2. Requirements amendment ที่เสนอ

| รหัส | ข้อเสนอ | ที่มา |
|---|---|---|
| IP-R1 | เพิ่ม checkpoint `Paper Internal Pilot — Accepted` สำหรับกลุ่มที่เจ้าของเชิญรวมไม่เกิน10คน ใช้ Paper เท่านั้น | roadmap จุดปล่อยที่1; ข้อเสนอขนาดกลุ่มทดลองในบทสนทนา |
| IP-R2 | ตรวจความจุ20บัญชีภายใต้โปรไฟล์ `PAPER_INTERNAL20_V1` ใน§3; ไม่ใช้จำนวนสมาชิกที่ล็อกอินแทนจำนวนบัญชีที่มีงานจริง | รักษาความหนักต่อบัญชีของ F15 baseline เดิม |
| IP-R3 | คง Money/Quantity, exact ledger/PnL/reservations, owner/mode/episode isolation, idempotency และ safety gates ทุกข้อ | F14–F17 requirements; trading-safety; testing |
| IP-R4 | คงprocessing p95≤250ms/p99≤1s, cycle/recovery60s และ F17 necessary-input-ready→processing-start≤1s | F15 validation §6; F17 NC-F17-05/V-08 |
| IP-R5 | ผลโปรไฟล์20ปิดเฉพาะ checkpoint ภายใน ไม่ปิด F17 V-18 ของ100บัญชีหรือ V-19/V-20 และไม่เปลี่ยนนิยาม F17 Completed | แยกขอบเขตหลักฐาน; คง Release dependencies |
| IP-R6 | ก่อนให้ผู้ทดลองใช้ ต้องพิสูจน์ F16/F18 production Paper admission และกฎความเสี่ยงจริง; test policy หรือการปิด safety ไม่ใช้แทน | F16 V-17/V-18; integrated plan |

10คนเป็นนโยบายจำกัดกลุ่มเชิญสำหรับรอบทดลอง ไม่เพิ่ม production order cap, session cap,
rate-limit ใหม่ หรือระบบ entitlement ในงานนี้ ต้องบันทึกรายชื่อ/จำนวนผู้ได้รับสิทธิ์ตามระบบ
ควบคุมสิทธิ์เดิมก่อนเปิดรอบ ถ้ายังจำกัดการเข้าถึงเฉพาะกลุ่มไม่ได้ ต้องหยุดก่อนเปิดให้ใช้
การอนุมัติเกณฑ์ไม่ใช่การอนุมัติ deployment หรือเปิด Live

## 3. โปรไฟล์และตัวเลขที่ตรึงก่อนเริ่ม

ใช้20 core owners/episodes แยกกัน แต่ละคนมี20 active resting LIMIT orders บนBTCUSDT
(รวม400รายการ) ตามทุน ราคา ปริมาณ สภาพคล่อง และ five-command oracle ของ
[F15 validation §6](../2026-10-18-paper-order-matching/validation.md) เดิมทุกค่า
ใช้book inputs10Hz และ recorded/fake deterministic feed; ไม่ส่งคำสั่งไปตลาดจริง

| Phase | Owners | Baseline/owner | Commands/s รวม | Cycles/owner | Commands รวม | ช่วงวัด |
|---|---:|---:|---:|---:|---:|---|
| D20 diagnostic |20|20|2|6|600|5นาที; cap รวม20นาที |
| W1-20 steady |20|20|2|36|3600|30นาที |
| W2-20 burst |20|20|20|120|12000|10นาที + overflow/slow-consumer แยก |
| W3-20 endurance |20|20|2 ในช่วง non-fault|282|28200|4ชั่วโมงต่อเนื่อง รวม fault windows |

2และ20commands/s คือการลดโหลดรวมของโปรไฟล์100บัญชีด้วยสัดส่วน20/100
ไม่ใช่การคาดว่าคนจริงจะส่งคำสั่งด้วยอัตรานี้ ความหนักและจำนวน cycles ต่อบัญชีเท่าเดิม
หนึ่งcycleต้องจบก่อนเริ่มcycleถัดไปของบัญชีนั้น ไม่อนุญาตซ้อนเพื่อให้ throughput ผ่าน

ทุกcycleใช้3new orders,2fills,1cancel,1replayตาม independent financial oracle เดิม
ผลรวมที่ต้องครบ: D20=120cycles/240fills/120cancels/120replays;
W1-20=720/1440/720/720; W2-20=2400/4800/2400/2400;
W3-20=5640/11280/5640/5640 ไม่หักคำสั่งที่ไม่สำเร็จออกจากตัวหาร
ผลเงินต่อownerของ W1/W2 เท่าโปรไฟล์เดิม เพราะจำนวนcyclesต่อownerเท่าเดิม
W3 ใช้ N=282 ที่ประกาศก่อนรัน; ห้ามคำนวณ N ย้อนจากจำนวนที่สำเร็จ

W3 ใช้ `backend/tests/infra/execution_market/w3_fault_schedule.json` เดิม
(14400s,282cycles/owner และ7eventsเดิม) พร้อม pin digest ก่อนรัน
ไม่ย้ายเวลา fault ลดระยะขัดข้อง หรือลดช่วง endurance เพื่อให้ผ่าน

W4-20 ใช้ backup/restore ลงฐานแยก พร้อม canonical cash/position/history/source/grants/RLS
และ fixture ของ F16 receipt/transfer กับ F17 pending/armed/exit/retry ตามแผนรวมเดิม
ผล W4 เดิมที่ครอบเฉพาะ F15 ยังใช้ได้เฉพาะขอบเขตนั้น ไม่แทน integrated restore

### เครื่องและ runtime

- ใช้เครื่อง local ที่ตรง reference ขั้นต่ำ4logical CPU/8GiB RAM, PostgreSQL16,
  Python3.12/frozen lockfiles ตามโปรไฟล์เดิม ไม่เสนอซื้อเครื่องหรือเพิ่ม infrastructure
- ก่อนรันต้องบันทึก host CPU/RAM/OS, Docker VM CPU/RAM, container limits, DB settings,
  free disk, host load, processes/containersที่ใช้ร่วม, source/schema/config/dataset digests
  และรายชื่อ20บัญชี ห้ามใช้ข้อมูลเครื่องปัจจุบันแทนหลักฐานสภาพเครื่องตอนรันย้อนหลัง
- ใช้20workers, round_limit20/claim_limit1, NC11 V2 nonblocking coordination,
  busy backoff250ms, per-book heartbeat, parent poll limit4 และ final-tail drain
  แบบ opt-in ใน harness ตามแผนรวมเดิม ไม่ปรับ pool/worker count ระหว่าง phases
- บันทึก API/bridge process counts และ pool configuration จาก composition เดิมเป็น manifest
  ก่อนตรวจ; ถ้าจำเป็นต้องเปลี่ยนเพื่อให้ผ่าน ให้เสนอ amendment ก่อน ห้ามปรับเงียบ
- ต้อง preflight ว่าDocker/DBทำงาน พื้นที่ไม่เต็ม และไม่มีบริการ restartวนที่ยังไม่จัดการ
  ถ้าenvironmentไม่พร้อม ให้รายงาน Incomplete ไม่รันซ้ำเพื่อสุ่มได้เครื่องว่าง
  ห้ามหยุดบริการอื่นหรือลบ cache/containers/volumes โดยถือว่าเอกสารนี้อนุญาต

### การวัด

ใช้ตัวเลือกช่วง `measured_transaction_seconds` ที่ตรวจแล้ว: เลือกตามเวลาเริ่มในช่วงวัด
เก็บ duration เต็มแม้ข้ามจุดจบ แยกsetup/fault-start/final-drain และเก็บrawทุกตัวอย่าง
faultใช้actual started/restored ไม่มี extra warm-up หรือ recovery grace ที่เพิ่มเอง
queue/pool/polling waits ยังนับใน60sเดิม; ไม่ลบเวลาซ้อนออกเพื่อทำให้ผ่าน
เก็บoffered/admitted/completed/rejected/fill/cancel/replayแยก และผลล้ม/ข้อมูลขาดตามจริง
คงRSS≤1GiBต่อprocess, W3 growth≤20%, no connection/claim/lock leak และbacklog/recoveryเดิม

## 4. เส้นทางรวมที่ต้องพิสูจน์

1. **API:** ทุกคำสั่งที่วัดในW1-20–W3-20 ผ่าน authenticated F16 HTTP→durable inbox→bridge→worker
   ใช้ auth/CSRF/session/RLS และ risk policy จริง แยกเวลาตอบรับ/ผลcommand/processing/projection
   direct intake หรือD20ที่ใช้test policyไม่รับรองเส้นทางใช้งานจริง
2. **Position:** หลังแต่ละW1/W2/W3หยุดmutations แล้วreplayและตรวจsnapshotครบ20episodes
   เทียบ exact financial oracle, revision และhistory ไม่เลือกเฉพาะownerที่สำเร็จ
   คงrebuild≤60sต่อowner, snapshot p95≤250ms/p99≤1s, concurrent readers≤4
   ระหว่างW3อ่านครบ20snapshotsนาทีละครั้ง และใช้ resource/rebuild criteria เดิม
3. **TP/SL:** ใช้ Feature lifecycle/race/failure/financial/browser cases เดิมบนcandidateที่ตรงกัน
   เพิ่มหลักฐานที่ยังขาดสำหรับกลุ่ม20บัญชี: controlled20-owner scenario, ownerละ1armed
   protection group โดย reuse buy/trigger fixture ของ `backend/tests/infra/protections/test_validation.py`
   ทั้ง20มี20resting baseline ordersเดิม วัด fresh input ready→actual processing start
   ครบทุกowner≤1s และตรวจexit/ledger/idempotencyครบ ไม่ใช้ค่าเฉลี่ยหรือenqueueแทนstart
   ใช้ real DB/worker composition ของ candidate, ค่าเงินและtriggerจากfixtureเดิม
   เป็นกรณี20groupsที่กำหนด ไม่อ้างว่ารองรับจำนวนgroupsหรือtrigger rateไม่จำกัด
4. **UI:** ใช้ browser→API→DB→worker→UI flows เดิมสำหรับ bracket/replace/cancel/reload/
   unknown receipt/owner switch บนcandidateเดียวกัน จำนวน20บัญชีใน workload ไม่ใช่หลักฐาน
   ว่าbrowser20หน้าหรือทุกchart/widgetผ่าน performance แล้ว; เกณฑ์frontendเดิมยังมีผล
5. **Restore/recovery:** หลังrestoreต้องไม่มีexit/fillซ้ำ ไม่สูญเสียintent/audit และreconcile
   งานpendingได้โดยไม่ส่งNEWซ้ำเพื่อเดาผล; คง real-DB locking/concurrency safety tests

## 5. Plan: ของเดิมและขอบเขต implementation ที่เสนอ

| ของเดิม | ใช้ทำอะไร |
|---|---|
| `backend/tests/infra/execution_market/profile_workload.py` | fixture/cycles/counts, timestamp selector, fault schedule, resource/financial oracle และcleanup |
| `backend/tests/infra/execution_market/profile_parent_poll.py`, `profile_diagnostics.py` | opt-in poll budget และหลักฐาน timeout เดิม |
| `backend/tests/infra/risk_limits/profile_workload.py` | reuse intake/policy composition; แก้2callback typing issuesที่ต้องใช้ โดยไม่เปลี่ยนpolicy |
| `backend/tests/infra/manual_orders/`, `backend/tests/api/` | HTTP auth/CSRF, receipt/idempotency และproduction intake/bridge |
| `backend/tests/infra/positions/` | snapshot/rebuild/exact financial comparison |
| `backend/tests/infra/protections/test_validation.py` และ `frontend` command `npm run test:e2e:protections` | protection lifecycle, real-worker1s observation และbrowser flows |
| `backend/tests/infra/execution_market/profile_restore.py` | backup/restore fixture และcanonical digest; ขยายเฉพาะตารางF16/F17ที่แผนเดิมกำหนด |

หลังอนุมัติจึงเพิ่ม named profile ที่ตรึงค่าใน§3 และoption validation/restart forwarding
ใน harness เดิม ใช้แหล่ง profile เดียว ไม่คัดลอกcycle/oracleหรือสร้าง runnerอีกชุด
ไม่เปลี่ยนค่าdefaultหรือแทนโปรไฟล์100ด้วย20เมื่อไม่ได้ระบุprofileชัด
ไม่มีbusiness schema migration, production capacity cap, trading formula หรือinfraใหม่
ถ้าพบว่าต้องแก้production protocol/architecture/ข้อกำหนดเพื่อให้ผ่าน ให้หยุดเสนอจุดแก้ก่อน

ลำดับทำงานหลังอนุมัติ:

1. อัปเดตสถานะNC12และเอกสารอ้างอิงให้ตรงคำอนุมัติ; pin candidate/config/evidence
2. แก้harnessตามขอบเขตนี้ รวมHTTP/position/restore wiringที่แผนรวมเดิมยังไม่เสร็จ
   ตรวจtargeted correctness/safety/real-DB concurrencyและstatic checksก่อนtiming
   ใช้ผลเก่าที่ไม่ถูกกระทบต่อ ไม่รันsuiteซ้ำโดยไม่มีช่องว่าง
3. ตรวจcontrolled20-owner protection case และD20อย่างละหนึ่งรอบตามprofileที่ตรึง
   เมื่อครบและผ่านจึงเดินต่อW1-20→W2-20/fault→W3-20→W4-20 โดยไม่ขออนุมัติย่อยซ้ำ
4. แต่ละphaseใช้ฐานแยกที่เตรียมใหม่ เก็บmanifest/results/cleanupครบ ผูกทุกผลกับcandidate
   ถ้าphaseล้ม หยุดphaseถัดไป วิเคราะห์จากหลักฐาน แล้วเสนอทางแก้/ขอบเขตต่อไป
   ไม่รันcandidateเดิมซ้ำหรือลดowners/rate/criteriaอีกโดยอัตโนมัติ
5. จบaffected regression/review/required CI และด่านเปิดภายใน ก่อนให้สถานะAccepted
   commit/push/PR/merge/deploy ยังต้องมีคำสั่งเจ้าของตามกฎGitเดิม

ระยะวัดรวมอย่างน้อย4ชั่วโมง45นาที บวกcontrolled protection/overflow/restore;
ตั้งงบการตรวจประมาณ6–8ชั่วโมงหลังharnessพร้อม รวมเตรียมข้อมูล วิเคราะห์และcleanup
จำนวนบัญชีลดแต่4h enduranceยังเดิม จึงไม่รับประกันว่าจะจบเร็วหรือผ่าน
เวลาพัฒนาHTTP/restore wiringและแก้บั๊กยังประเมินอย่างน่าเชื่อถือไม่ได้; แจ้งประมาณการใหม่
หลังตรวจinterfacesแล้ว ก่อนเริ่มชุดยาว ไม่รวมเวลานี้ไว้ใน6–8ชั่วโมงโดยไม่บอก

## 6. Validation และความหมายของการปิด checkpoint

All criteria below are approved; execution results remain **Not Run / Pending Validation** until evidence exists.

| เกณฑ์ | ระยะ | ต้องมีหลักฐานอะไร |
|---|---|---|
| IP-V1 profile contract | Feature |20/100แยกชัด, counts/fault digestถูกต้อง, defaultsไม่เปลี่ยน, unknown profileถูกปฏิเสธ, restartใช้ค่าเดิม |
| IP-V2 correctness/safety | Feature |เงิน/quantity/PnLตรง, duplicate=0, auth/RLS/isolation, transaction/locking/idempotency/retry และfail-closedตามF14–F17เดิม |
| IP-V3 production admission | Feature ก่อนเปิดภายใน |ผ่านF16 V-18/F18 policy integrationที่เกี่ยวข้องจริง; test-policy admissionและสถานะPendingเดิมใช้แทนไม่ได้ |
| IP-V4 protection/UI | Feature |lifecycle/browserเดิมพร้อมcontrolled20-owner≤1sครบทุกowner, exact exit/effects, restart/reload/unknown recovery |
| IP-V5 diagnostic | Batch |D20ครบ600commandsและfinancial/final-tail/resourceทั้งหมด; Partial/Incompleteไม่ให้เดินต่อ |
| IP-V6 load/endurance | Batch |W1-20/W2-20/W3-20ครบduration/counts/latency/resource/faultเกณฑ์ใน§3–4 |
| IP-V7 snapshots/restore | Batch |rebuild/snapshotครบ20episodes และF16/F17 integrated restore/identity/history/grants/recoveryผ่าน |
| IP-V8 final candidate | Feature + Batch |review/affected regression/static/required CIตรงcandidateสุดท้าย; หลักฐานระบุsource/config และผลที่ใช้ต่อได้ |
| IP-V9 internal access | Release เฉพาะการเปิดภายใน |กลุ่มเชิญไม่เกิน10, ไม่มีpublic signup/access, Paperเท่านั้น, คำเตือนระบบยังไม่เสร็จ, production safetyพร้อม และมีคำสั่งเปิดใช้งานตามขั้นตอน |

**ปิด `Paper Internal Pilot — Accepted` ได้เมื่อ IP-V1–V9 ผ่านครบเท่านั้น**
ถ้าlocalครบแต่รอCI/Git/deploy/access gate ให้รายงาน `Pilot validation complete — Pending opening gates`
พร้อมรายการที่รอ ไม่ถือว่าเปิดให้ใช้ได้แล้ว ไม่ตั้งcheckpointเป็นPassedจากการอนุมัติเอกสาร

| งานเดิม | ผลของamendmentหากอนุมัติ |
|---|---|
| F14 V-17 / F15 V-19,W1–W4 / F16 V-20 / F17 V-18 ตามโปรไฟล์100 |ผลเดิมFailed/Partial/Not Runคงไว้;20-profileเป็นหลักฐานขอบเขตใหม่ ไม่ปิดเกณฑ์100 |
| การอนุญาตPaperกลุ่มภายใน |ใช้IP-V1–V9แทนการรอ100-profileสำหรับจุดปล่อยภายในเท่านั้น เป็นข้อยกเว้นที่ต้องอนุมัติชัดในNC12 |
| เป้าหมาย100บัญชี |คงเป็นงานตรวจรับความจุที่ค้าง ต้องผ่านก่อนขยายเกินกลุ่ม10คนหรือเปิดสาธารณะ และก่อนCompletedตามด่านเดิม; ไม่ย้ายไปอนาคตโดยไม่มีcheckpoint |
| F17 V-19/V-20 บอท/แจ้งเตือน/Live |ยังPending Dependency/Full Validation; ไม่ย้าย ตัด หรือรับรองด้วยPaper |
| F17 Completed |นิยามเดิมไม่เปลี่ยน ต้องผ่านBatch/Releaseที่เกี่ยวข้องครบ |

## 7. คำตัดสินที่ขอจากเจ้าของ

**A — อนุมัติNC-SET4-12ทั้งrequirements amendment, planและvalidationนี้:** เพิ่มโปรไฟล์20
เพื่อปิดcheckpointPaperภายในสำหรับ10ผู้ทดลอง คงความเร็ว/เงิน/durationเดิมและงาน100/Release
อนุญาตharnessและtargeted checksตาม§5 แล้วทำcampaignต่อเนื่องตามด่านเมื่อผ่าน
โดยยังคงจุดหยุดเมื่อมีfailure/ข้อกำหนดใหม่ และกฎGit/deployเดิม

**B — คง100บัญชีเป็นด่านเปิดภายใน:** ไม่implementหรือรันโปรไฟล์20; จัดทำแผนแก้คอขวด
ของcandidate100ก่อนการทดลองใหม่ตามกฎสามรอบ

Owner selected **A** with `approve` on2026-11-06 after reviewing this complete proposal.
Implementation and conditional progression in section5 are authorized. Option B was
not selected. No approval itself constitutes a passing result or Git/deploy permission.

## 8. Implementation checkpoint — 2026-11-06

**Incomplete; no controlled20/D20/W1/W2/W3/W4 campaign has started.**
The approved profile is being implemented in the recovered worktree. Production,
migrations and frontend sources match all427 hashes captured before NC12. No
commit/push/merge/deploy occurred. The owner-authorized three restarting ui-check
workers were stopped; PostgreSQL remains healthy. The existing test Redis on
port56418 was started for the production API lifespan; no volumes were deleted.

Implemented but not fully validated: pinned profile/options and restart forwarding;
real authenticated ASGI HTTP intake and durable receipt identities; real risk-policy
worker composition; streamed parent polling evidence; shared exact position replay;
snapshot observations; controlled protection observer and scenario; F16/F17 restore
fixture and recovery extension. Defaults and financial rules are preserved.

Evidence is under [nc12](evidence/recovery-20261106/nc12/):

| Check | Result / measured time | Scope |
|---|---|---|
| Initial targeted regression |190 Passed /9.34s|Profile/options, HTTP mocks, latency attribution, poll/diagnostic/final-tail; later affected harness edits still need regression |
| Real authenticated API cycle |1 Passed /4.00s|Five-command oracle, exact retry, foreign-owner404 and missing-CSRF403; does not prove load |
| Observation guards |3 Passed|Missing20th owner/late SLA cannot pass; canceled polling retained; missing snapshot fails |
| Restore harness attempt1 |Failed /13.76s|asyncpg UUID subtype was not normalized in the extracted replay helper; fixed |
| Restore harness attempt2 |Failed /13.56s|Fixture executed before the publisher was ready; fixed using the existing readiness rule |
| Restore harness attempt3 |Failed /15.77s|MIGRATOR cannot bypass forced RLS; global coverage falsely read0; stopped after three attempts |
| Owner-approved replacement |Failed /77.06s|Read-only admin enforcement, fixture coverage, receipt retry and owner RLS checks passed; recovery timed out because pending bracket NEW was terminally rejected |

The owner explicitly approved the observer fix and one replacement after attempt3.
The observer now uses the existing W4 admin connection only for global reads, with
`REPEATABLE READ` and `postgresql_readonly=true`; an attempted no-op UPDATE is
rejected. API/worker credentials and RLS are unchanged. Scoped Ruff/mypy passed
before the replacement. Preserve every failed attempt; this is not W4 acceptance.

Read-only diagnosis after the replacement found both staged exit groups CLOSED,
the replacement request APPLIED, and the pending F16 receipt TRANSFERRED with the
same identity. Its underlying NEW is `REJECTED / ORDER_INPUT_INVALID`; no pending
bracket group was created. The current harness waits for ARMED and therefore used
the full60s bound. The specific domain rejection is not yet known; do not classify
it as either a harmless fixture error or a production defect without evidence.
No campaign/pytest processes or connections to that test DB remained afterward.

### Rejection diagnostic — A approved and executed

**A:** Add a test-only observer around the existing order rejection path. Capture
only exception class/code and traceback file/function/line, without payloads,
credentials or exception text; delegate to the unchanged rejection implementation.
Have the restore harness report a terminal rejection immediately rather than wait
for an impossible ARMED state; retain the original60s deadline and passing oracle.
Check this observer with targeted/static checks, then run the same restore safety
fixture once on a fresh isolated DB. Preserve prior results and stop/report if it
fails. If it passes, finish the already-approved harness checks before controlled20
and D20; there is no permission to skip to a workload campaign.

**B:** Keep this incomplete checkpoint and all evidence without another experiment.

Owner selected A. The diagnostic observer passed4 targeted tests /0.31s and scoped
Ruff/mypy before the single fresh-DB restore run. That run failed in16.64s, reporting
the terminal rejection immediately instead of waiting60s. Trace:
`paper_orders/worker.py:_process_new` → `protections/worker.py:commit_admission` →
`protections/storage.py:create` → `core/orders.py:OrderScope.__post_init__`.
The driver returns `asyncpg.pgproto.pgproto.UUID`; it passes `isinstance(..., UUID)`
but fails the domain's intentional `type(...) is UUID` check. Read-only reconstruction
reproduced `ORDER_INPUT_INVALID`, while `UUID(str(value))` preserves the identity and
satisfies the domain contract. See `rejections.jsonl`, `terminal-rejection.json` and
`uuid-readonly-proof.json` in the evidence directory. This is a production F17
boundary defect, not a load-capacity result. The subsequently approved fix and its
results are recorded in section9 below.

Before timing, remaining implementation checks include immediate propagation of
periodic snapshot failures, full per-owner rebuild query/resource observations,
fresh/source/restore-target guards and final candidate regression. Full restore,
controlled20 SLA, D20 and all sustained phases remain Not Run. F17 remains open.

## 9. Scoped production fix — Approved A,2026-11-06

The diagnostic identifies a valid bracket rejected during worker admission. The
same unsafe construction exists in standalone protection CREATE. F17 requires
both paths to preserve owner/episode isolation and create a valid protection;
no requirements or financial criteria change is proposed.

**Files and change:** normalize the database owner's UUID using the existing
`UUID(str(...))` boundary pattern before constructing `OrderScope` in
`backend/src/tiewtrade/infra/protections/storage.py:create` and
`backend/src/tiewtrade/infra/protections/worker.py:process_request` (CREATE branch).
Retain the original UUID value, scope comparison, PAPER mode and episode checks.
Do not weaken `core.orders.OrderScope`, change shared session semantics, add a
migration or broaden database permissions. No trading formula or retry policy changes.

**Validation:** add real-DB regressions that obtain the owner identifier through
the driver/scanner and exercise bracket admission and standalone CREATE through
the real worker paths. Assert one protection/order effect and exact identity;
retain wrong-owner/episode denial. Run affected F17 lifecycle/financial/isolation
and worker regression plus scoped lint/types. Then run the unchanged restore
safety fixture once on a fresh DB with the diagnostic retained. If it passes,
finish remaining NC12 harness validation and proceed through the original gated
controlled20/D20/campaign sequence. If it fails, preserve evidence and stop/report.

**A:** Approve this two-boundary production fix, related regression and the one
replacement restore safety run. This is an explicit narrow exception to§5's
harness-only scope; other production/architecture changes still need an amendment.

**B:** Keep production unchanged and leave the internal pilot blocked by the
confirmed valid-order rejection. Existing successful narrower tests remain valid.

Neither option authorizes commit/push/merge/deploy or changes F17 Completed gates.

Owner selected A for section9: the two-boundary fix, real-DB regression/static checks
and one replacement restore safety run are authorized; passing gates allow
continuation under the original plan. Other production changes and Git/deploy
remain subject to their existing approval boundaries.

### Section9 execution — 2026-11-07

The two approved UUID conversions are implemented. The new real-DB regressions
passed2 tests (2.99s); affected F17 protection regression passed48 tests (60.24s).
Scoped Ruff/format/mypy passed. The single replacement restore safety check on a
fresh database passed1 test (15.93s), including read-only observer enforcement,
receipt/protection retry identity and exact financial checks. Prior failed attempts
remain preserved. This safety fixture is not the full W4 backup/restore campaign.

The remaining harness changes propagate periodic observation failures immediately,
record per-owner replay query/row/RSS metrics, enforce fresh/source/target guards,
and compare ACL/RLS for all extension tables. The affected harness/HTTP/observation/
publisher/polling/final-tail/latency checks passed192 tests (18.44s; the already-passed
restore fixture was not repeated). Scoped Ruff/format and mypy for12 files passed.
Next: controlled20 once, then D20 and the original sequence only if each gate passes;
this continuation is already authorized. No Git/deploy or acceptance status change.

## 10. Controlled20 interruption and replacement — Approved A,2026-11-07

The first controlled20 campaign was stopped during baseline preparation after
136.483s, before trigger/SLA measurement. The harness omitted the approved parent
poll gate from its baseline call. Preserve this as **Incomplete**, not a failed
20-owner SLA or financial result. Source stayed unchanged during the attempt;
cleanup found zero remaining connections and advisory locks. A preceding launcher
path error never entered the campaign or mutated its database; its log is retained.

The harness now reuses `ParentPollGate` for baseline and trigger-result polling,
keeps the original pool and60s deadline, and persists all attempts/cleanup. The
orchestration test exercises20 waiting reads, proves at most4 admitted together,
and verifies cleanup after interruption. Related checks passed33 tests/2.28s;
Ruff/format/mypy passed for the2 changed harness/test files. Production remains
limited to the2 approved UUID changes. No replacement campaign or D20 has run.

Host disk declined from about2.3GiB before the attempt to1.3GiB afterward; swap
usage was about7.4GiB. There was no observed disk-full exception, but the next
campaign does not meet the existing2GiB preflight floor. Do not attribute the
Incomplete result to capacity/SLA, and do not start another phase on this host state.

**A — proposed next action:** remove only the5 unused TiewTrade image IDs pinned in
[the read-only inventory](evidence/recovery-20261106/nc12-controlled20-1/unused-project-images-proposal.json),
then unused Docker build cache if needed. Recheck references from all running and
stopped containers immediately before removal; skip any referenced image and use
no force. The selected images have about1.97GB unique layers according to Docker;
actual host reclamation is not guaranteed. Old validation runners may require
rebuilding those images. Do not stop/delete containers, databases or volumes.
Recheck host/Docker/DB health and space. Only if ready, run one controlled20
replacement on a fresh DB with the corrected harness (estimated3–8min). Preserve
the original Incomplete. If the replacement passes, continue D20 and the existing
conditional sequence; if it fails, stop/report. No changed criteria, production
logic, Git or deployment authorization is requested.

**B:** keep this checkpoint and evidence; do not delete images or run again.

Approval is needed because§3 disallows assuming permission to delete other
resources, previous cleanup permission excluded images, and§5 stops following
phases when a campaign is incomplete/failed. The next run is a replacement of
the single controlled20 attempt, not a newly approved acceptance threshold.

Owner selected A for section10 on2026-11-07: the pinned image cleanup, optional
unused build-cache cleanup and one controlled20 replacement are approved. Passing
gates allow the original conditional D20/campaign continuation; other scopes stay unchanged.

### Section10 execution — 2026-11-07

Removed the5 pinned images after checking all running/stopped container references;
no containers/databases/volumes were removed. Cache cleanup was unnecessary once
headroom recovered. See `evidence/recovery-20261106/nc12-section10-cleanup.json`.
The controlled20 replacement **Passed** in132.922s on a fresh database:400 baseline
orders,20/20 observed owners, maximum input-ready-to-processing-start0.444013s
(criterion≤1s), exact financial/exit/retry checks passed, no worker failures.
All5516 polling attempts finished; peak4 and active0. Cleanup:0 connections/0
advisory locks. Candidate unchanged. Preserve the original Incomplete.
Next: proceed with the already-authorized D20 on a fresh database; only continue
W1/W2/W3/W4 if each preceding gate passes. This does not close F17 or opening gates.

## 11. D20 result and final-tail polling amendment — Approved A,2026-11-07

D20 **Failed** in341.074s total, despite completing600/600 commands over302.590s:
120cycles,240fills,120cancels,120replays,0rejections. All20 owner financial oracles
and global invariants passed; duplicate/unlinked effects and invalid positions/
reservations were zero. Processing p95=170.932ms and p99=313.010ms passed. Final
input lag2 and tail drain1.382s passed. No worker failed. Preserve this Failed
result; W1–W4 have not started. D20 does not cover W1–W3 snapshot/rebuild criteria.

The sole failing resource predicate is `connections_end <= connections_start+2`:
57→68 (allowed≤59). All first60 samples were57–59; the last sample was68. RSS,
lock waits and input lag predicates passed. Final cleanup found0 connections and
0 advisory locks. See [raw result and analysis](evidence/recovery-20261106/nc12-d20-1/analysis.json).
The final observation overlaps tail drain based on the recorded clocks. The
original `wait_for_input_recovery` and final cursor collection allow20 concurrent
owner reads; NC09 explicitly left final-tail behavior unchanged. This is consistent
with transient parent pool expansion, but existing evidence lacks per-pool attribution
and cannot prove the absence of a leak during operation. Do not relabel Failed as
Passed, exclude this sample or increase the connection allowance.

**A — proposed harness-only change:** for `PAPER_INTERNAL20_V1`, pass the existing
`ParentPollGate` explicitly into `drain_final_tail` and `wait_for_input_recovery` in
`backend/tests/infra/execution_market/profile_workload.py`. Gate owner reads in live
recovery, stopped-source tail recovery and final cursor verification before opening
the existing ENGINE session. Release session before permit. Keep the one outer60s
deadline including permit waits, same source identity/head/cursor checks, failures,
owner coverage, financial predicates and cleanup. Defaults/other profiles remain
unchanged. This explicitly amends NC09's unchanged-final-tail boundary only for NC12.

Add read-only parent-pool and connection-count observations at drain stages and
cleanup using the existing pool properties/`PoolEvidence` pattern in
`backend/tests/infra/risk_limits/profile_resources.py` and existing migrator reads.
Keep unknown cross-role state explicit; do not add credentials, pools, warm-up,
extra grace time or production changes. The existing resource verdict—including
initial+2 and the existing final-sample selection—must stay unchanged. These
additional observations diagnose a failure; they cannot override its verdict.

Reuse `test_final_tail_drain.py`, `test_parent_poll.py` and supervision cases. Add
coverage for20 owner reads capped at4, release before sleeping, error/cancellation
joins, queued wait counting toward the same60s deadline, all20 final cursors and
unchanged default callers. Run targeted safety/regression and scoped Ruff/format/
mypy before timing. The successful controlled20 case remains valid because its
code path and runtime composition are unchanged; do not repeat it as ceremony.

After those checks pass, authorize one D20 replacement on a fresh database:
20owners×20baseline orders,600commands/120cycles,2commands/s, measured5min,
20min total cap, estimated8–12min including setup. Preserve all earlier results.
If it passes, continue the original W1/W2/W3/W4 conditional sequence; if it fails,
stop/report. No changes to business logic, acceptance thresholds, workers/pools,
Git or deployment. No further storage cleanup is requested.

**B:** keep this checkpoint; do not change the harness or run another campaign.

This section required owner approval before implementation because NC09 retained
final-tail behavior and NC12§5 stops before another campaign after a failed gate.
The subsequent approval, implementation and result are recorded below.

Owner selected A for section11 on2026-11-07: scoped harness changes, targeted
safety/static checks and one D20 replacement are approved. Passing gates allow
the original conditional campaign continuation. No production/Git/deploy change.

Section11 implementation checks passed126 targeted cases/3.08s, including the
existing-pool real-DB observation. Ruff/format/mypy passed for2 affected files.
Only `profile_workload.py` and `test_final_tail_drain.py` changed from the D20
candidate. The resource predicate/final-sample selection, production and pool
configuration remain unchanged. Proceed with the one authorized D20 replacement.

### Section11 replacement result — Incomplete,2026-11-07

The single authorized D20 replacement stopped in247.817s total,205.784s into the
measured interval. Observed401offered/admitted,395completed of600planned,
77completed cycles,158fills,79cancels,79replays and0rejections. These partial
counters are not the complete financial/global oracle. The publisher raised
`SourceUnavailableError: book readiness cannot be proved` at
`order_book_storage.publish_input` → `core.order_book.BookState.require_ready`.
Section11's final-tail stage was **not reached**, so the new resource behavior
has126 targeted checks but still no completed campaign proof. No W1 was started.

41 resource samples showed connections57–59; all3803 polling attempts finished,
peak4/active0. Cleanup found0 connections/0 advisory locks; candidate unchanged.
The SQLAlchemy connection-termination cancellation was reported during shutdown;
it is not substituted for the publisher's original failure. Raw logs, read-only
post-stop source state and `analysis.json` are retained under
`evidence/recovery-20261106/nc12-d20-replacement/`.

The readiness message does not uniquely mean stale data. `MAX_BOOK_AGE` is30s,
and the guard also rejects future timestamps. Host logs show only29.906ms between
last successful publication and failure. The harness constructs ready=True with
received_at=verified_at from PostgreSQL clock; source_at is absent. The last durable
input is2118 with received_at17:49:34.384576UTC and a lease until17:49:39.379158UTC.
The failed2119 transaction rolled back; its exact book timestamps and guard's
`db_now` were not recorded. Clock reversal is a hypothesis, not a proven cause.
The successful-publication maximum1.008s cannot identify the failed guard or be
compared as if it were the30s book age. Do not refresh timestamps, widen freshness,
retry the rejected publication or label this an ordinary capacity failure.

## 12. Publisher readiness observation — Approved A,2026-11-07

**A — proposed diagnostic-only amendment:** capture the exact readiness inputs at
the existing parent publisher guard, without changing its decision. Use a test-only
opt-in observer for `PAPER_INTERNAL20_V1`, following `profile_diagnostics.py`'s
publisher operation identity and the existing `observe_rejections` delegation/
exception-preservation pattern. Record tick/input ID, owner/generation, ready/rebase,
received_at, verified_at, optional source_at, the `now` actually passed to the guard,
and monotonic time. Keep only a bounded recent window and flush it on the original
failure/end; explicitly label the retained window. No SQL/bind values, credentials,
full order-book payload or exception text. Observe existing arguments; add no DB
query and do not substitute a later clock sample for the guard's actual value.

The observer must call the unchanged guard exactly once and preserve its return/
exception identity. Do not skip/repair inputs, alter timestamps/leases/readiness,
add retries, modify production files or change money/safety/latency/resource rules.
Scope it to the parent publisher; default callers and worker runtime stay unchanged.
Keep it enabled in subsequent NC12 phases only if the approved D20 gate passes,
so a later failure can retain the same evidence without changing the workload.

Before timing, test exact delegation for valid, stale and future-time inputs,
exception preservation, bounded-window/secret omission, opt-in isolation and
restoration on cancellation. Reuse publisher heartbeat/supervision and final-tail
regression plus scoped Ruff/format/mypy. Existing controlled20 and unchanged
production safety results remain valid; do not repeat them without an impact.

Then run one D20 diagnostic replacement on a fresh database with the same20owners,
400baseline orders,600commands,2commands/s,5min measurement and20min total cap;
estimated8–12min including setup. This may not reproduce the readiness failure.
Preserve both the original Failed resource run and section11's Incomplete. If all
unchanged D20 gates pass, continue the existing W1/W2/W3/W4 sequence; otherwise stop
and use the exact guard/pool evidence before proposing a fix. No extra retry/run,
new hardware, cleanup, production fix, Git or deployment is included.

**B:** stop experiments here and keep all passing narrower evidence and open gates.

Owner approval was required for another timed run: section11 authorized one D20
replacement and NC12§5 stops after its failed/incomplete gate. The owner selected A
on2026-11-07, authorizing this observer, safety/static checks and one D20 run, with
conditional continuation on passing gates. No readiness/production fix is authorized.

Implementation reuse note: inspected
`backend/tests/infra/risk_limits/profile_book_clock.py::observe_book_clock` and
reuse its `patch.object` restoration pattern plus `test_book_clock.ready_book`
fixture. That existing F19 observer records only failures across child guards and
can replace the original error on evidence I/O failure; it does not provide this
approved parent-operation scope or recent-success window. Keep it unchanged and
place the scoped NC12 observer in `profile_publisher_readiness.py`, with workload
and internal restore CLI entrypoints opting in.

Section12 implementation checks passed154 targeted cases/4.09s. After switching
to the existing `patch.object` pattern, all12 observer cases passed again/0.69s;
Ruff/format/mypy passed for4 affected harness files. Evidence: `nc12-section12/`.
No production file, timestamp, threshold, query, pool setting or retry changed.
Proceed with the single approved D20 readiness-observation run on a fresh database.

### Section12 D20 result — Passed,2026-11-07

The single approved run passed in341.660s total/303.398s measured:600/600commands,
120cycles,240fills,120cancels,120replays,0rejections. All20 financial oracles and
global invariants passed. Engine transaction p95=192.754ms/p99=325.518ms.
Final-tail drain completed in0.947s; resource predicate passed with connections
57→58 (peak59),0end lock waits. Cleanup0connections/0advisory locks and candidate
unchanged. Observer delegated3108 guards, retained64 recent checks and restored
originals. Readiness failure was not reproduced; the old failure's cause remains
unproven. Preserve the original Failed and section11 Incomplete evidence.

Evidence: `evidence/recovery-20261106/nc12-d20-readiness/`. The approved next step
is W1 on a fresh database:20owners×36cycles=3600commands,2/s through authenticated
HTTP,30min measurement plus setup/final snapshot/rebuild; estimated35–40min.
Continue W2/overflow/W3/W4 only on passing gates. F17 remains Pending Full Validation.

### Section12 conditional W1 result — Incomplete,2026-11-07

After D20 passed, the authorized W1 ran on a new isolated database with the same
candidate. It stopped after1227.598s measured/1269.198s total (about20m28s measured)
on the unchanged60s owner-cycle deadline, at `cycle`'s final MARKET SELL
`submit_new` → `wait_status(FILLED)`. Counters:2404offered,2402admitted,
2384completed of3600planned,468cycles,951fills,475cancels,479replays,0rejections.
All2404 HTTP responses were200/202, but2 result observers were cancelled during
shutdown, so HTTP acceptance must not be confused with2384 completed commands.

Deterministic keys and HTTP timing identify owner
`73bbb747-bfda-4471-8326-4528ae1f32bd`, zero-based cycle23 as the oldest cycle:
60.085s from its first HTTP call to failure observation. This is an inference from
existing evidence, not a directly recorded cycle timeout identity. Its final sell
was FILLED in post-stop state; that does not satisfy the cycle deadline or prove
the full financial oracle. Financial/global oracle, final-tail and snapshot/rebuild
were not reached. Readiness was not the failure:11776 parent guard calls, no
rejection, last64 retained. All24172 parent polling permits finished,peak4/active0.
Cleanup0connections/0advisory locks; candidate unchanged.

The partial interval contains23663 transactions: p95=487.319ms, p99=1184.654ms;
these are diagnostic statistics, not a completed W1 result. Five-minute p95 values
were309.288/332.451/635.200/867.952ms, then3657.360ms for the final27.598s.
Connections started57, last incomplete sample63, peak64; sampled lock waits0.
Neither the latency issue nor resource criterion can be declared resolved.

A separate command, `212ac2d5-f771-438a-b0ec-f90f7f87a67b`, logged SQLSTATE57014
while `matching_storage.load_order_state` read terminal history. It belongs to
another owner and later had a CANCELED projection; do not call it the same order
as the cycle timeout. Post-stop EXPLAIN ANALYZE under the original engine role,
owner RLS and unchanged timeout took1437.229ms: the existing owner checkpoint
index returned1294 history events, then JSON terminal arrays were expanded and
sorted before LIMIT1. One proposed read-only correlated-LATERAL SELECT used the
same index and stopped after8 events (10.106ms). The first draft probe failed due
to parameter type inference; correlating to `o.id` resolved that prototype error.
These sequential single-query observations are not a controlled speedup estimate,
semantic regression proof or proof that this query explains all workload delay.
No production code was changed and no timed campaign was repeated.

Evidence: `evidence/recovery-20261106/nc12-w1/`, including raw campaign log,
partial metrics, deterministic-key cycle attribution, read-only post-stop state,
old/proposed query plans, probe scripts/logs and post-diagnosis cleanup0/0.
W2/overflow/W3/fullW4 are Not Run. D20 and controlled20 remain Passed for their
recorded candidate; F17 and the internal pilot are not completed/accepted.

## 13. Terminal-history lookup — Approved A,2026-11-07

**A — proposed scoped production amendment:** optimize only the terminal-history
SELECT in `backend/src/tiewtrade/infra/paper_orders/matching_storage.py::load_order_state`.
Resolve the order through its existing primary key/RLS, then use a correlated
LATERAL subquery with the existing `paper_matching_owner_checkpoint` index to
search that episode/pair by descending decision_sequence and stop at the latest
matching terminal record. Keep the same JSON predicate, returned payload,
provenance/terminal validation, missing-order behavior and legacy fallback. No
migration, new index, cache, infrastructure, pool/worker change, financial rule,
clock/readiness change, retry, timeout increase or acceptance relaxation.

Reuse existing real-DB cases in `execution_market/test_review_regressions.py`
(immutable terminal history must win over a corrupted rebuildable projection),
`execution_market/test_worker.py` (late cancel/terminal command/retry), and
`risk_limits/test_matching_recovery.py` plus correction coverage for callers in
`paper_orders/worker.py` and `paper_orders/corrections.py`. Add only missing cases:
latest of multiple historical terminal snapshots, missing/active legacy fallback,
wrong-owner RLS isolation and exact old/new result equality for representative
filled/canceled/expired orders. Inspect the real query plan on a nontrivial history
fixture; test correctness rather than adding a new fragile wall-clock threshold.
Run scoped Ruff/format/mypy and affected financial/idempotency/real-DB regression
before workload. Keep independent controlled20 protection evidence unless a caller
impact requires repeating it. Preserve all previous Failed/Incomplete results.

After checks pass, authorize one D20 on a fresh database (600commands,5min,20min cap)
for the changed production candidate, then one W1 on another fresh database
(3600commands,30min) only if D20 passes. Estimated45–55min including setup/results,
excluding development. If both pass, continue the original W2/overflow/W3/W4
conditional sequence without another intermediate approval. Stop/report on a
failed/incomplete gate; do not automatically rerun or change criteria. Performance
and connection growth must still pass independently; this query change is not a
promise that all W1 blockers are solved. Existing Git/CI/review/deploy gates remain.

**B:** keep this checkpoint and stop experiments without a production change.

Owner selected A on2026-11-07, authorizing the scoped query change, safety/static
checks and one D20→W1 sequence with conditional onward continuation. This approval
extends section12's harness-only scope. Stop/report on a failed gate as above.
The prior read-only SELECT probe remains diagnostic evidence only.

Section13 implementation: only the terminal-history SELECT changed. A pinned
pre-change query in `order_history_assertions.py` verifies equivalent OrderState
results in existing worker/correction/expiry tests. The existing full fill→replace
→void scenario proves latest-version selection with exact Money/Quantity values;
2 new cases cover active fallback, missing order and wrong-owner RLS for active/
terminal orders. No production cache/session state or financial logic was added.

Checks passed44 real-DB worker/storage/recovery cases/40.75s and6 affected TP/SL
financial/replay/correction cases/11.48s. Ruff/format/mypy passed5 files. Actual
production SELECT on archived W1 history returned the same state as the old query
and used the existing index to visit8 events; post-stop execution0.699ms is a
warm/read-only diagnostic, not workload acceptance. Evidence: `nc12-section13/`.
Controlled20 start-detection code is unchanged; affected terminal exit effects
were rechecked above. Proceed with the single approved section13 D20 on a fresh DB.

Section13 first launcher stopped **Incomplete during preflight** in0.408s because
free space was1.16GB, below the unchanged2GiB harness headroom guard. No baseline,
worker or measured command started; candidate unchanged and cleanup0/0. Preserve
`nc12-section13-d20/`. On2026-11-07 the owner subsequently instructed “ทำต่อ”.
Docker was then stopped and free space6.2GiB; normal launch/start restored only
the existing PostgreSQL/Redis used here. The earlier explicit unused-build-cache
cleanup permission was reused (not an image/container/database/volume cleanup);
recorded output and resulting headroom are in `nc12-section13/environment-recovery.json`.
Resume the approved measured D20 on a new database after preflight, then W1 only
if it passes. No candidate change or acceptance relaxation; preserve the unmeasured
preflight failure separately and do not reinterpret it as a trading/performance test.

### Section13 resumed D20 result — Failed,2026-11-07

After the owner's “ทำต่อ” and environment recovery, the measured D20 ran on a new
isolated database with the unchanged section13 candidate. It completed in364.376s
total/307.119s measured:600/600commands,120cycles,240fills,120cancels,120replays,
0rejections. All20 financial oracles and global invariants passed. Resource checks
passed:connections57→59 (peak59), no sampled lock waits, all7314 poll permits
finished,peak4/active0. Final-tail3.879s; cleanup0connections/0advisory locks.
No worker failure or parent readiness rejection;3081 guards, last64 retained.

The result is **Failed** for p95=531.809ms (>250ms) and2976measured book inputs
(<3000required). p99=981.639ms remained within1s. No W1 replacement was started.
The original section12 D20 Passed and W1 Incomplete remain scoped to their recorded
candidate; neither substitutes for acceptance of the optimized query candidate.

At-run manifest shows8 logical CPUs,1/5/15-minute host load24.84/39.87/27.96,
versus2.85/3.07/4.34 before the earlier passed D20. Node/Next and the Docker VM were
using substantial CPU at preflight; read-only cwd/port inspection identified the
Next server as another project (`eod-frontend-baseline/frontend-sit1`,127.0.0.1:3191),
not this campaign. The host booted at01:52:49Asia/Bangkok between the runs. Post-stop
swap was about5.85GiB; this is not a measurement of swap activity during the run.
Hardware, DB/pool/worker settings were unchanged, but these runs are not a controlled
old/new query comparison. Shared-host contention is an observed confounder, not a
proven sole cause of the failed latency/input-rate gates. Do not claim regression
or resolution solely from these two differently loaded runs.

The current launcher records load but only gates disk/health/restart loops. It
therefore admitted this heavily loaded environment. Evidence, raw results,
manifest comparison and post-stop-only environment observations are retained in
`evidence/recovery-20261106/nc12-section13-d20-resumed/`. No other process was stopped.
F17/internal-pilot acceptance remain open; W1 replacement/W2/overflow/W3/fullW4 Not Run.

## 14. Bounded environment preflight — Revised plan Approved,2026-11-07

**A — proposed harness-only amendment:** arrange a test window in which the owner
pauses unrelated build/test/workload campaigns. Do not terminate other projects,
editors, system services or containers automatically. Keep the same host, Docker
limits, DB/pools,20workers, workload and all existing correctness/performance rules.

Before fixture/workers start, inspect the host for one bounded120s window with7
sample starts at0/20/40/60/80/100/120s. The original revision1 load1≤logicalCPU rule
is retained in the execution history below and is superseded for future runs by
revision2's CPU/memory rule:mean sampled CPU idle≥20%, pressure Normal/Warning
allowed and Critical rejected. Retain≥2GiB free-disk and healthy-service/no-restart-
loop guards. Record1/5/15-minute load informationally, CPU count, free bytes and
actual timestamps. Missing/invalid observations or a failed readiness condition
stop as Incomplete before workload; no wait-until-quiet loop or automatic retry.
This is an environment admission heuristic, not a trading/performance acceptance
change or proof that the host cannot contend later.

Reuse the existing `os.getloadavg`/`shutil.disk_usage` observation pattern in
`profile_checkpoint_isolation.py` and existing campaign manifest/preflight. Put
scoped NC12 readiness logic with `profile_internal.py` and its existing tests;
default/other profiles remain unchanged. At the existing resource sample interval
in `profile_workload.py`, record the lightweight host load tuple alongside current
metrics so later interference can be investigated. Do not exclude bad measurement
windows, change sample selection, infer a pass from low host load, or add queries/
full process command lines. Test readiness boundaries, missing readings, fixed
window/cancellation, default isolation and existing supervision; scoped static
checks before timing. Production code remains the already-tested section13 query.

Authorize one D20 after that preflight passes: same20owners/400baseline/600commands,
2commands/s,5min measured,20min total cap including preflight; estimated10–14min
including setup/results. If preflight fails, stop before the timed attempt and
report; if D20 fails/incomplete, stop/report without another run. If D20 passes,
continue the already-approved W1 and remaining conditional campaign, retaining
this preflight/observation for each subsequent phase. Preserve all earlier results.
No further production fix, storage cleanup, hardware change or Git/deploy action.

**B:** preserve the query fix,50 passing safety tests and all evidence; stop timed
experiments here until a suitable test window is available.

The owner instructed implementation of the revised section14 plan on2026-11-07
and confirmed unrelated build/test/workloads are paused. Before/after service
checks include PostgreSQL healthy/accepting, Redis responding and no restart loops.
Keep preflight evidence at campaign root, pin runner copy/hash before measurement,
and count preflight within the D20 total20min cap. No phase retry on failure.

Section14 implemented: the campaign calls the bounded gate before manifest/fixture
setup, saves `preflight.json` outside `run/`, checks services before/after, and pins
runner bytes/hash before the first sample. Only NC12 resource sampling adds host
load; diagnostic wrappers preserve the keyword and unchanged default call shape.
D20's outer1200s deadline starts at preflight and an over-budget completion cannot
be Passed; cleanup is recorded in the final elapsed time. No production change.

211 unique targeted cases are covered by passing results:201 initially passed,
9 were blocked by a stopped PostgreSQL service, and76 affected rechecks passed
after normal Docker/two-service startup, including those9 and a new cancellation
case. Ruff/format passed5files; mypy passed4repo harness files; runner CLI help
passed. Evidence: `nc12-section14/`. The owner confirmed unrelated work is paused.
Proceed with one preflight/D20 campaign on a new empty database, estimated10–14min,
20min total cap; stop/report if readiness or the measured gate fails.

### Section14 execution checkpoint — Implemented; preflight Incomplete,2026-11-07

The one authorized preflight stopped after0.437s at the first sample,10:16:20
Asia/Bangkok. Load1/5/15=19.29/18.37/17.02 on8logicalCPUs exceeded the unchanged
load1≤CPU guard. Free space17.11GB exceeded2GiB; PostgreSQL was healthy/accepting,
Redis returnedPONG and no restart loop was observed. The failed sample and reason
were recorded at campaign root. `run/` was never created: no fixture, worker or
measured command started. The real120s passing window and D20 host-load sampling
remain Not Run; their behavior has targeted test evidence, not campaign acceptance.

Cleanup0connections/0advisory locks; source and pinned runner remained unchanged.
Evidence: `evidence/recovery-20261106/nc12-section14-d20/`. Read-only post-stop
inspection showed high CPU in Spotlight (`mds_stores`), the Docker VM and other
system tasks after the host boot at09:51:19. This does not imply the owner failed
to pause other builds or prove that one process alone caused the initial load.
No system service/process was stopped; no new campaign or automatic retry began.

The section14 implementation and its211 unique targeted tests/static checks are
complete. Internal Paper acceptance and F17 remain open. Next is an owner-triggered
new preflight when host activity has subsided; the same code/profile/criteria apply,
so no new production fix or threshold amendment is proposed at this checkpoint.
A passing preflight permits D20, then the approved conditional campaign; another
failed gate still stops/reports. No Git/deploy action is authorized by this result.

### Section14 revision2 — CPU/memory readiness, owner requested2026-11-07

The owner reported no other applications in use and instructed “ปรับเกณฑ์” after
read-only inspection found Spotlight activity, load16.08 and about48.62% CPU idle.
Replace only the environment admission rule for future runs. Preserve the original
load-based Incomplete result, all workload Failed results and production safety
criteria. This instruction authorizes the readiness correction and targeted checks;
it does not relabel an old run or initiate another timed campaign in this change.

Operational readiness defaults: retain the one120s observation window with7 sample
starts at0/20/40/60/80/100/120s, ≥2GiB disk per sample and service checks before/after.
Load1/5/15 remains recorded, with no load/CPU-count admission ceiling. On this macOS
campaign host, sample aggregate CPU idle using the second report of
`LC_ALL=C top -l 2 -s 1 -n 0` (discard the first since-boot report); require the mean
of the7 interval readings to be≥20%. Brief busy readings are retained in that mean.
Read `sysctl -n kern.memorystatus_vm_pressure_level` for each sample:1Normal or
2Warning are admitted,4Critical stops immediately, unknown/missing readings fail
closed. Warning is explicitly visible in evidence, not renamed Normal. These are
operational heuristics for this test host, not claims of trading capacity.

Use only read-only native commands with bounded5s command timeouts, join/terminate
only these observer child processes on cancellation, and preserve original errors.
Each CPU reading takes about1s; scheduled sample starts remain fixed relative to
monotonic time, actual timestamps are recorded, and read overhead remains within
D20's existing20min total cap. No wait-until-ready loop or automatic workload retry.
Other platforms fail as unsupported for this local readiness sensor; other profiles
and runtime resource sampling remain unchanged. No OS service is disabled.

Apple source for the read-only pressure sysctl maps internal levels to dispatch
notification values:
https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_memorystatus_notify.c
(`sysctl_memorystatus_vm_pressure_level`/`convert_internal_pressure_level_to_dispatch_level`).
The local SDK `dispatch/source.h` defines Normal=0x01,Warn=0x02,Critical=0x04.
Never run memory_pressure's allocating/simulation modes as an observer.

Before reporting this revision, test high load with available CPU, exact20% mean,
below-threshold mean, Warning/Critical/unknown memory levels, invalid CPU readings,
first-report exclusion, native command error/timeout/cancellation, and prior fixed
window/default-caller behavior. Run scoped Ruff/format/mypy. The50 production safety
checks remain valid because no production code is changed. A future timed run must
be separately initiated after reporting these revised criteria and checks.

Revision2 implementation/checks completed:108 targeted cases passed/0.81s and scoped
Ruff/format/mypy passed2files. Read-only native sensor smoke returned41.68% interval
CPU idle and pressure2Warning; one reading is not the7-sample mean or a passing
preflight. Evidence: `evidence/recovery-20261106/nc12-section14-v2/`. No production
file changed and no new preflight/workload was started. Next is an owner-triggered
preflight/D20 using this revision; the prior stop/report/no-auto-retry rule remains.

### Section14 revision2 D20 — Passed,2026-11-07

Owner instructed “เริ่มทำ”. The single new campaign passed in453.904s total,
including the120s readiness window, and300.000s measured. Preflight mean CPU idle
49.481%, all7pressure readings2Warning, services/disk ready. D20 completed600/600
commands,120cycles,240fills,120cancels,120replays,0rejections; all20 financial oracles,
global invariants and resource assertions passed. Engine p95=116.400ms,
p99=164.199ms; measured book inputs3000/3000. Connections57→58 (peak59), final-tail
0.570s; cleanup0connections/0advisory locks and candidate/runner unchanged.
All60 runtime resource samples include informational host load. Evidence:
`evidence/recovery-20261106/nc12-section14-v2-d20/`.

This is acceptance of D20 only, not a controlled attribution of improvement to
one change or F17 Completed. Preserve all earlier Failed/Incomplete results.
Proceed with approved W1 on a new DB:preflight,3600commands through authenticated
HTTP over30min, final financial/snapshot/rebuild checks; estimated35–40min total.
Subsequent phases remain conditional on each gate passing.

### Revision2 conditional W1 — Failed resource predicate,2026-11-07

The authorized W1 completed3600/3600commands over1801.745s measured,2085.927s total
including preflight/setup and final checks. All20 financial oracles/global invariants
passed:720cycles,1440fills,720cancels,720replays,0rejections. Engine p95=133.580ms,
p99=191.986ms, book18017/18000. All20 final snapshots passed:p95=32.977ms,
p99=33.661ms;20 rebuilds passed,max7.052s/owner. Final-tail1.500s, no worker or
readiness failures, all20041poll permits finished/peak4/active0. Candidate/runner
unchanged; cleanup0connections/0advisory locks.

The overall result remains **Failed**, solely because connections_end60 exceeded
connections_start57+2=59. Peak61;358samples distributed57×1,59×8,60×295,61×54.
The increase appears within the first5s and does not grow monotonically over30min.
At final-tail, API role had9connections; parent engine pool checkedout0/checkedin5/
overflow0. App lifespan creates distinct lazy API/auth/mutation/price/indicator/chart
pools; current evidence does not distinguish every API pool or prove all outstanding
borrows returned before disposal. Thus normal lazy pool expansion is a supported
hypothesis, not a proven no-leak result. Do not silently change+2 to+3 or retroactively
call this W1 Passed. Evidence: `evidence/recovery-20261106/nc12-section14-v2-w1/`.
W2/overflow/W3/fullW4 were not started after the failed gate.

## 15. Owned pool resource contract — Approved A,2026-11-07

**A — proposed harness/resource-validation amendment for NC12 only:** replace the
aggregate initial+2 proxy with direct bounded-pool/return-of-connection evidence.
The safety requirement remains no leaked connections/claims/locks. Keep existing
pool sizes/overflow/timeouts, worker count, workload, all financial/latency/feed/
RSS/recovery/snapshot/rebuild criteria and every historical Failed result.

Reuse `profile_pool_timing.py`'s checkedout/size observation and
`profile_workload.py::parent_pool_state` pattern. Inventory all engines actually
created by the parent/ASGI lifespan and worker processes, label process/role/pool,
and record configured size/max_overflow plus checkedin/checkedout/overflow at the
existing resource interval and after owned work stops, before final disposal.
Use scoped test-only registration/observation, restored on cancellation; registry
holds diagnostic state only. Record intermediate disposal/restart generations so
intentional W3 fault actions do not masquerade as leaks or lost final evidence.
No new production/session cache, infrastructure or business database writes.

New NC12 resource pass conditions must all hold:
- Complete expected parent/ASGI/worker pool inventory and finite unchanged capacities;
  missing observations/unknown capacities fail closed, never fall back to+2/+3.
- Each pool's observed checkedin+checkedout stays within its configured size+overflow;
  all raw aggregate PostgreSQL samples, including the first, remain in evidence.
- After all owned work/background tasks join, every gracefully stopped pool has
  checkedout=0 before final disposal. Planned killed/restarted workers retain their
  existing fault/recovery checks; final surviving workers and parent still require
  complete return evidence. Unexpected worker exits fail under existing rules.
- No pool timeout, connection-resource error or unaccounted failed observer; final
  database cleanup remains0connections/0advisory locks. Existing lock/claim/RSS/input-
  lag/recovery checks remain independently binding.

Default/100-account profiles retain their current predicates. Idle connections
retained within a registered pool's configured capacity are not classified as a
leak merely because the pool opened them after the first sample. This proposed
contract is not a claim that the previous W1 already has the required pool evidence.

Before timing, run targeted real-DB tests through the actual ASGI lifespan and
worker cleanup: lazy pool expansion within configured capacity passes; an outstanding
borrow at quiescence fails even below capacity; excessive capacity/unknown or missing
inventory fails; cancellation/error/disposal restore observers and preserve primary
errors; planned worker restart remains distinguishable from unexpected exit. Run
scoped static checks and affected harness regression. Existing production50safety
checks and completed W1 financial/position observations remain valid for those
specific assertions; they do not replace the missing resource acceptance evidence.

Then authorize one fresh-DB W1 with revised instrumentation/contract:20owners,
400baseline,3600commands via authenticated HTTP,2/s,30min plus the same revised
preflight and final checks; estimated35–40min after harness checks. Do not repeat D20
as ceremony: production, workload and latency-selection code remain unchanged,
and W1 directly rechecks timing/resource risks of added observation. If W1 passes,
continue the original W2/overflow/W3/W4 conditional sequence without another minor
approval. If a gate fails/incomplete, stop/report with no automatic retry. No Git/
deploy action, extra warm-up, sample deletion or baseline replacement is included.

**B:** retain initial+2 unchanged and authorize only a short read-only pool-ownership
diagnostic proposal before deciding whether to amend acceptance; no W1 rerun yet.

The owner selected A on2026-11-07: pool contract/instrumentation, targeted real-DB
checks and one W1 are approved, with onward continuation on passing gates only.
Keep all previous results and stop/report on any failed/incomplete gate.

Implementation reuse: extend the existing
`tests/infra/risk_limits/profile_resources.py::PoolEvidence` checkout/checkin tracking
without changing that shared F19 utility. NC12 adds periodic native pool snapshots,
pre-disposal observations, generation tracking and complete expected inventories.
Parent runtime inventory is12 engines:API6,AUTH2,ENGINE1,ENGINE_SCAN1,MARKET_DATA1,
MIGRATOR1, using unchanged configured capacities. Each paper worker owns2 engines:
ENGINE1/ENGINE_SCAN1. Forced W3 kills/restarts follow the original declared fault
checks; no worker evidence may disappear without a recorded planned termination.

The existing ASGI lifespan cancels and joins its reader/broadcast tasks on shutdown.
Mark this quiescent shutdown before closing the intake stack and record expected
CancelledError invalidations separately; they are not spontaneous connection errors.
Still require every borrow returned before disposal, preserve any primary exception,
and reject pool timeouts/disconnects during active work. No task is cancelled earlier
than the existing lifecycle and no new cancellation/grace period is introduced.


## 16. Revised acceptance and complete owned inventory — Approved,2026-11-07

Status:Approved. Owner approved the revised500ms/2s internal pilot thresholds,
complete pool instrumentation, targeted checks and one replacement W1 on2026-11-07.
Passing W1 permits the existing conditional W2/overflow/W3/W4 sequence.
§15 campaign remains Incomplete; preserve its evidence.

### เกณฑ์ที่เสนอให้ใช้แทนการสรุปรวมว่า “ไม่ผ่าน”

| ส่วน | เกณฑ์ตรวจรับที่เสนอ | การตีความเมื่อไม่ครบ |
|---|---|---|
| ความพร้อมเครื่อง | ใช้ CPU/memory/disk/services ตาม§14 revision2; load เก็บประกอบการวิเคราะห์ | Incomplete ก่อนเริ่ม workload; ไม่ใช่ผลความจุระบบ |
| ความพร้อม harness | tests ต้องครอบคลุมเส้นทางตรวจฐานว่างจริง + ASGI lifespan + worker shutdown พร้อม inventory ของทุก pool | ข้อมูลขาดหรือ observer error เป็น Incomplete; ไม่ใช้สรุปว่าระบบช้าหรือมี connection leak |
| Connection pool | ตรวจขนาดที่ตั้งจริงของทุก pool รวม admin observer; ทุก loan ต้องคืนก่อน disposal และ cleanup ต้อง0connections/0advisory locks | หลักฐานครบและพบ loan ค้าง/เกิน capacity/timeout เป็น Failed; ไม่ใช้ initial+2 และไม่เพิ่มเป็น+3 |
| เงิน/ออเดอร์/position | exact oracle เดิม, ไม่มีคำสั่งซ้ำ, owner/mode isolation, idempotency และ safety เดิม | หลักฐานยืนยันผิดเป็น Failed และหยุด; หลักฐานไม่พอเป็น Incomplete |
| ความเร็ว/จำนวนงาน | เสนอเฉพาะ engine processing ของ Paper Internal Pilot: p95≤500ms, p99≤2s; คง cycle/recovery≤60s และจำนวนงาน/ช่วงวัดเดิม | เป้าหมายเดิม250ms/1sยังรายงานเป็น target; ผ่านเกณฑ์ pilot แต่เกิน target ให้รายงาน Accepted with performance warning; เกินเกณฑ์ pilot เป็น Failed; ห้ามตัดตัวอย่างช้าทิ้ง |

Incomplete ไม่ใช่ Passed และยังบล็อก phase ถัดไปเช่นเดิม หากมีทั้งหลักฐานยืนยัน
ความผิดพลาดของระบบและข้อบกพร่องของ harness ต้องรายงานทั้งสอง ไม่ใช้ Incomplete
ลบล้างข้อผิดพลาดที่พิสูจน์ได้ ผลย้อนหลังและนิยาม F17 Completed ไม่เปลี่ยน

รอบ§14-v2 W1 มีหลักฐานว่าเงิน/ออเดอร์/position/snapshot/rebuild และความเร็วผ่าน
แต่ยังขาดหลักฐาน pool แบบใหม่ จึงใช้ผลนั้นต่อได้เฉพาะ assertions ที่ไม่ถูกกระทบ
ไม่เปลี่ยนผลรวม Failed ให้ Passed ส่วนรอบ§15 จบก่อนครบช่วงวัดเพราะ harness
จึงคง Incomplete การล้มสองกรณีนี้ไม่ใช่หลักฐานว่าการผ่อน p95 จะแก้ต้นเหตุได้
ข้อเสนอ500ms/2sเป็นทางเลือกยอมรับความหน่วงเพิ่มสำหรับกลุ่มทดลองตามคำขอเจ้าของ
ยังต้องได้รับอนุมัติตัวเลขนี้ก่อนแก้ harness ไม่ใช่ค่าที่พิสูจน์แล้วว่าเหมาะกับผู้ใช้จริง

ก่อนรอบยาวให้ targeted real-DB tests พิสูจน์ startup/shutdown ที่ตกหล่นให้ครบ
โดยไม่เพิ่ม timed diagnostic อีกชุด และไม่รัน D20 ซ้ำเมื่อสิ่งที่ D20 พิสูจน์
ไม่ถูกกระทบ ต้องตรวจผล tests/static checks จบก่อนเริ่ม campaign

### ขอบเขตแก้และรอบทดแทนหลังอนุมัติ

Change only the NC12 harness criteria/evidence after approval. The existing empty-database check creates one
read-only admin engine inside the observed parent runtime. Include that pool as an
explicit ADMIN_OBSERVER entry with its existing bounded default capacity5+10, in
addition to the12 application pools; each worker still has2 pools. Do not exclude
this engine, change its capacity/privileges or silently accept arbitrary usernames.
Match only the configured isolated test admin identity and existing read-only engine
options; unknown roles/configurations and missing observations continue to fail.
Require admin loans returned before final disposal and preserve all error conditions.
No production, financial, workload or trading-safety threshold changes.
Only the internal pilot engine-processing latency acceptance changes to500ms/2s.
The100-account/Release250ms/1s target, snapshot latency, TP/SL input-ready→start≤1s,
feed counts and recovery bounds remain unchanged. Do not report this as full F17
acceptance or change historical results; label future evidence with this pilot revision.
Update only NC12 result classification to distinguish observer/inventory evidence
failures from proven resource violations, retaining underlying failures separately.
Unknown observations must never produce Passed.

Add a targeted real-DB regression invoking the actual require_empty_database path
inside the pool observer, checking complete13-pool parent inventory plus the existing
ASGI lifespan, and negative cases for unknown admin identity/configuration and an
outstanding observer loan. Reuse prior valid tests; run affected regressions and
scoped Ruff/format/mypy. Before timing confirm actual startup-path coverage, not only
component construction. No new diagnostic campaign is needed for this test coverage.

If approved and checks pass, authorize one fresh-DB replacement W1 using the same
§14-v2 preflight and full3600commands/30min profile (~35–40min). Preserve this initial
Incomplete result; pass continues W2/overflow/W3/W4, failed/incomplete stops/report
without retry. No Git/deploy/other-service changes. No implementation of§16 yet.


### ข้อเสนอผ่อนปรนเพิ่มเติมตามคำขอเจ้าของ — 2026-11-07

เฉพาะ20บัญชี Paper ภายในที่เชิญไม่เกิน10คน เสนอแยกเป้าหมายความเร็วเดิมออกจาก
เกณฑ์หยุดรับงาน: engine p95≤500ms/p99≤2s เป็นเพดาน pilot และ250ms/1sเป็น target
ที่ต้องรายงาน หากผ่านเพดานใหม่แต่พลาด target ต้องแจ้งเตือนด้าน performance ชัดเจน
การยอมรับนี้ไม่เพิ่มรอบ retry ไม่ลดจำนวนงาน/ระยะวัด และไม่ทำให้ safety failure
กลายเป็น warning ไม่เพิ่มเวลาปล่อย TP/SL ให้เริ่มช้ากว่า1s ไม่เปลี่ยนราคาหรือกฎเงิน

ตัวเลขนี้เป็นข้อเสนอทางเลือกสำหรับการยอมรับความหน่วงเพิ่ม ไม่ได้อนุมานจากจำนวน
รอบที่ล้ม และไม่รับประกันว่ารอบใหม่จะผ่าน สถานะยังรออนุมัติเกณฑ์เฉพาะนี้
พร้อมขอบเขตแก้ harness และหนึ่งรอบทดแทนใน§16 ก่อนลงมือ

Owner approval2026-11-07 supersedes the proposal/awaiting-approval wording above
for§16 only. No Git/deploy or automatic failed-phase retry is authorized.


### §16 execution checkpoint — W1 Passed; W2 Failed,2026-11-07

Implementation and targeted checks complete. W1 passed all criteria, including
original250ms/1s timing targets and owned pools. Conditional W2 completed all12000
commands with exact financial/position/resource checks passed and approved pilot
latency passed, but measured963.571s>660s allowed. Preserve performance_warning for
p95=363.782ms exceeding original250ms target. Stop before overflow/W3/W4. See
[evidence](evidence/recovery-20261106/nc12-section16-w2/analysis.md).
No replacement run/further implementation is authorized by the failed gate.


## 17. Bounded W2 worker-phase diagnostic — Deferred, not authorized

Owner approved existing-evidence analysis after§16. That analysis is complete:
[report](evidence/recovery-20261106/nc12-section16-w2/throughput-analysis.md).
This new campaign/implementation scope requires approval; no production fix is yet
supported by an identified expensive phase/query.

Reuse existing `tests/infra/risk_limits/profile_dispatch_timing.py::traced_worker`
and Recorder through an NC12/W2-only opt-in. Keep the original20owners/400baseline/
12000commands/20s^-1/120cycles-per-owner fixture, API/bridge/worker composition,
coordination/claim budget/backoff/pools, all safety checks and§16 latency ceilings.
Do not create a new lower-load acceptance profile or change approved thresholds.

At the existing measured start, emit the existing dispatch-trace-control contract
with started=measurement monotonic start, seconds=60, owners=[], detail_limit=0.
Collect aggregated per-second worker scan/gate/acquired/busy/selection/claim/process
counts/times for that60s window plus the bounded late-completion bucket. Keep
ACTIVE/PENDING/CANCEL classifications. No detailed order records, SQL trace or extra
live-DB/host poller; avoid the broader diagnostics wrapper. Restore all monkeypatches
and join the observer on shutdown/cancellation; retain complete existing pool proof.
The full W2 cohort still finishes and runs financial/replay/resource checks; do not
stop with orders pending merely when the60s trace window closes.

Before timing run scoped tests for option validation/worker forwarding, common
measurement start across workers,60s boundaries/late completions, empty owners and
zero detail limit retaining aggregates, exception/cancellation restoration and
unchanged defaults, then scoped Ruff/format/mypy. Reuse applicable existing tests.
Do not modify production code or other profiles.

If approved, run this diagnostic once on a fresh DB after§14-v2 preflight, estimate
20–25min total, with a25min overall deadline including preflight/results/cleanup.
On deadline cancel/join owned work and record Incomplete with cleanup; never mark
acceptance Passed from this diagnostic. Pin candidate/config/runner/schema and
preserve the prior W2 Failed. Stop/report after this one campaign regardless of
outcome, before a performance fix, acceptance rerun, overflow/W3/W4 or Git/deploy.
Use the measured phase division to propose the smallest justified next change.


## 18. Lower internal-pilot burst profile — Approved,2026-11-07

Owner requested less demanding acceptance after W2 did not meet20commands/s.
Defer the unapproved§17 diagnostic. This is a new capacity-policy proposal; the
specific10commands/s value is not yet approved and is not a claim of measured
maximum capacity. No source changes or new campaign are authorized until approval.

For the invited Paper pilot only, propose explicit `PAPER_INTERNAL20_V2`:

| Criterion | V1 internal burst | Proposed V2 internal burst |
|---|---|---|
| Active owners / resting baseline |20 /400|20 /400 unchanged|
| W2 offered target |20commands/s|10commands/s|
| Cycles per owner / total commands |120 /12000|120 /12000 unchanged|
| Target measurement / allowed completion |600s /660s|1200s /1260s|
| Book inputs at10Hz |≥6000|≥12000|
| Engine processing p95/p99 |500ms /2s|500ms /2s unchanged|
| Financial/order/position/idempotency/isolation |exact original oracle|unchanged; any proven violation fails|
| Pools / claims / locks / RSS / cycle/recovery bounds |§15–16 and originals|unchanged|

The proposed burst remains5×the2commands/s W1 steady rate.10commands/s is a
conservative trial target below the observed12.454commands/s cohort completion,
not an inference that this run proves10commands/s with every acceptance condition.
Actual usage requirements and capacity remain uncertain. The lower rate can also
change source freshness/queue behavior, so a fresh run is mandatory. Increasing the
measurement target follows12000/10; do not merely extend a20commands/s deadline or
relabel its old Failed result. Preserve that result and all raw evidence.

W1's20owners/400baseline/2commands/s/36cycles/30min are unchanged; reuse§16 W1's
passing evidence for those unchanged assertions. Controlled protection/D20 evidence
remains valid in its existing scope. W3's4h/endurance/fault schedule and W4 restore
are unchanged; all other original Release/100-account and F17 dependency gates
remain. Do not rename any old run as V2. New artifacts identify profile/revision and
both pilot ceilings and original performance targets explicitly.

Implementation scope after approval: harness/configuration/docs only. Reuse the
central profile definition/validation and existing cycle oracle, HTTP composition,
owned-pool observer and campaign runner. Add V2 opt-in selection while retaining V1
and default behavior. Do not change production, worker/pool sizes, coordinator,
retry/backoff or money/risk logic. Forward explicit V2 selection to workers and
retain owner/mode/session storage semantics. No new infrastructure or public API.

Targeted checks before timing: V1/default unchanged; V2 phase manifest/option
validation/worker forwarding; exact12000command/120cycle oracle and1200s/1260s bounds;
10Hz input-count calculation; unchanged pool/safety/latency/protection/snapshot gates.
Run affected tests and scoped Ruff/format/mypy; reuse valid production safety proof.

If approved and checks pass, authorize one fresh-DB V2 W2 after the existing preflight,
expected25–30min including setup/final checks. No ceremonial W1/D20 rerun. Passing
continues the original overflow→W3→W4 conditional sequence with preflight per phase.
A failed/incomplete gate still stops/report without automatic retry or another silent
threshold change. No§17 diagnostic, Git, deploy or Live action is included.

Closure remains `Paper Internal Pilot — Accepted` only after all its gates pass.
F17 Completed still requires its remaining review/CI/Batch/Release/dependency gates,
including bot/notification/Live criteria; a lighter burst does not satisfy those.


Owner approved§18 on2026-11-07: explicit V2 profile, targeted harness checks and one
fresh-DB W2 are authorized, with overflow/W3/W4 continuation on passing gates.
This supersedes proposal/awaiting-approval language in§18 only. Preserve all prior
results; no automatic failed-phase retry, production/Git/deploy/Live change.


### §18 execution checkpoint — V2 workload passed; overall Failed resource contract

V2 implemented and233targeted tests/scoped checks passed. The one approved W2
completed all12000commands in1241.602s≤1260s, withfinancial/position and pilot
latency passed. Overall Failed solely because4 active-work CancelledError events
were classified ConnectionResourceError; every borrowed connection returned and
cleanup0connections/0advisory locks. Their originating pool/task/deadline was not
recorded, so their cause cannot be certified. Preserve Failed and stop before
any further campaign/phase or source change. See
[evidence](evidence/recovery-20261106/nc12-section18-w2/analysis.md).


## 19. Cancellation provenance and short regressions — Approved scope,2026-11-07

Owner instructed “เริ่มทำ” after the§18 checkpoint recommended test-only cancellation
provenance and short regressions before another campaign. This authorizes only that
scope. Reuse OwnedPools/PoolEvidence/SQLAlchemy handle_error and current lifecycle.
No production, acceptance classification/threshold, workload or campaign change.

Add bounded resource-error provenance: UTC/monotonic timestamps, process and registered
engine/current-pool generation identity, role/capacity, configured read-only option,
current task identity/cancellation count and bounded project-code coroutine locations.
Never record task names, SQL/binds, request/exception text, URLs, credentials or locals.
Current-pool identity is explicitly labelled as such after disposal/generation churn;
unknown origin/deadline stays unknown rather than inferred from CancelledError.
Retain first16details plus total/truncation count, preserving every error in counters.
No new database queries from the observer. Preserve primary errors and scoped cleanup.

Targeted tests: real-DB read-only query cancelled by an explicit short deadline versus
ENGINE-role query explicitly cancelled; prove original TimeoutError/CancelledError
and task/pool attribution, no secret output, return accounting and listener restoration.
Reuse existing disconnect simulation, outstanding-loan, ASGI/worker lifecycle,
generation and classification regressions. Check unavailable task context and bounded
records. Every active-work cancellation remains a resource failure under current rules;
no tests can certify the origin of the4historical events that lacked this metadata.
Run affected tests plus scoped Ruff/format/mypy, then stop/report. No workload rerun,
production change, Git/deploy action, overflow/W3/W4 or changed warning policy authorized.


### §19 implementation checkpoint — short checks passed; no campaign

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


## 20. One V2 W2 with cancellation provenance — Approved,2026-11-07

Prerequisite§19 scoped tests/static checks passed. No further code change is planned.
Authorize one fresh-DB PAPER_INTERNAL20_V2 W2 with current source/runner pinned:
20owners/400baseline/120cycles-per-owner/12000commands,10commands/s,1200s target and
1260s completion bound,≥12000book inputs, engine500ms/2s with250ms/1s target warning,
all existing financial/position/pool/RSS/cycle/recovery rules. Run§14-v2 preflight
first. Capture§19 bounded error provenance only; no SQL trace or extra live sampler.
Estimated25–30min including preflight/setup/final verification/cleanup. No W1/D20
repeat, criteria waiver, backoff/pool/worker/production change or§17 diagnostic.

Any active cancellation remains a failure; do not infer a read-only exception solely
from the role or coroutine name. If failed/incomplete, stop/report without retry,
using the new details to identify the origin before proposing a rule/fix. If all gates
pass, continue the previously approved overflow→W3→W4 sequence with preflight before
each phase. Pin all evidence and preserve historical results. No Git/deploy/Live
permission or F17 Completed claim. This proposed replacement run has not started.


Owner approved§20 on2026-11-07: one fresh-DB V2 W2 with§19 provenance; pass permits
the existing conditional overflow/W3/W4 sequence. Failed/incomplete stops/report
without retry. This supersedes proposal wording in§20 only; no other permission.


## 21. Short internal stability gate; retain four-hour Release gate — Approved,2026-11-07

Owner objected to the4h runtime; §20 W3 was stopped during preflight with no workload.
This proposes a scoped internal requirement/plan/validation amendment. Specific
30min duration/fault schedule and moving the internal prerequisite require owner
approval before implementation. Original4h Release/100-account criteria remain
unchanged and Pending Full Validation; never label30min as4h endurance Passed.

Add explicit PAPER_INTERNAL20_V3, reusing V2 parameters except W3. Reuse completed
W1/W2/overflow evidence only for unchanged assertions; do not repeat them as ceremony.
Proposed short W3:20owners/400baseline,2commands/s,30cycles-per-owner/3000commands,
1800s continuous measured. Exact oracle600cycles/1200fills/600cancels/600replays,
0rejects; original money/position/isolation/idempotency and active-error rules remain.
Retain engine500ms/2s with250ms/1s target warning, snapshot250ms/1s, rebuild60s/owner,
RSS≤1GiB/process and growth≤20% over observed window, complete pool returns/cleanup,
cycle/recovery60s. Do not infer long-term leak absence from this shorter window.

Use a separate pinned internal fault schedule with all7existing event kinds and
durations; shorten only quiet intervals: offsets180/360/540/720/900/1080/1260s,
durations30/30/60/30/30/60/30s, kinds WORKER_RESTART/CONNECTION_CHURN/REDIS_OUTAGE/
WORKER_RESTART/CONNECTION_CHURN/REDIS_OUTAGE/WORKER_RESTART. No fault overlap or extra
grace. Actual fault started/restored timestamps govern engine sample exclusions.
Pause owner cycles during faults as before; at most one cycle per owner at a time.
Target active workload3000/2=1500s +270s faults +60s allowance gives1830s ceiling;
require at least1800s measured and≥15000book inputs using original formula.
Read20snapshots each minute at0..1740s(600periodic samples), plus20final snapshots;
expected620samples, final exact replay for every owner. All fault recovery checks
remain binding. Not an acceptance claim for the longer quiet intervals of Release.

Harness/docs only: reuse central profiles, scheduler/cycle oracle, worker forwarding,
OwnedPools/provenance, PositionChecks, fault runner and campaign. Keep V1/V2/default
14400s/282cycles/original schedule and240periodic snapshots unchanged. V3 explicitly
selects its own duration/cycles/schedule and30periodic snapshots from one profile
source. No production/money/backoff/pool/worker-count/Git/deploy/Live change.

Before timing test exact profile/counts/duration bounds/input denominator, pinned
fault kinds/durations/order/non-overlap, selected duration in hold/fault validation/
snapshot count, worker forwarding, unchanged defaults and financial/resource gates.
Run targeted tests/scoped Ruff/format/mypy; reuse valid safety tests.

If approved/checks pass: one fresh-DB V3 short W3 with existing preflight and current
bounded provenance, estimated35–45min total including setup/final replay/cleanup.
Passing permits W4 restore per existing plan; failed/incomplete stops/report without
retry. No new§17diagnostic or repeated W1/W2. Internal pilot may be Accepted only
after all its remaining gates; full4h validation remains a separately visible
Release obligation and full F17 Completed still requires its other dependencies.


Owner approved§21 on2026-11-07: V3 short stability profile/schedule, targeted checks
and one fresh-DB30min W3 are authorized; pass permits existing W4. Preserve the4h
Release obligation, prior results and failed/incomplete stop rule. This approval
supersedes proposal/awaiting-approval wording in§21 only. No other permission.


## 22. Correct retired-pool observation across held loans — Approved,2026-11-07

§21 short W3 stopped after the first connection-churn fault exposed an observer
accounting defect. See[evidence](evidence/recovery-20261106/nc12-section21-w3/analysis.md).
This is a harness-only correction; no production, financial, profile/rate/duration,
claim/backoff/pool-size or acceptance waiver. Preserve all prior results.

Reuse OwnedPools and PoolEvidence checkout/checkin tracking. Before disposal/live
pools still require finite unchanged capacity and native bounds. After a declared
intermediate disposal, mark the old generation retired and retain raw native values
as informational: SQLAlchemy resets its overflow counter, so native checkedout can
be negative during late returns. Do not apply live-pool arithmetic to that retired
counter. Continue bounding event-tracked active/peak borrows by frozen capacity and
require every generation's active borrows0 at quiescence. Unknown/live pool loss,
actual capacity changes, resource errors and outstanding final borrows remain failures.

A weakref-collected retired pool with pending tracked loans is not yet proof that
the loans cannot return. Record it as pending until quiescence, without retaining
strong references that change pool lifetime. If its tracked borrows remain nonzero
at final proof, fail. Collected unretired pools still fail; no missing inventory,
unknown counters or dropped final report can become Passed. Preserve labels that
separate live native counts, retired native counts and event-tracked return evidence.

Before timing, real-DB regressions must hold loans across intermediate dispose,
observe late returns/negative old native counts, open the new generation, and
exercise weakref/GC while a retired borrow remains pending then returns. Positive
case passes only after all returns; deliberately unreturned borrow fails despite
collection and below-capacity totals. Verify live over-capacity/config mutation/
unexpected pool loss and resource errors still fail, and listener/task/cancellation
cleanup remains intact. Reuse existing API/worker/generation/default regressions,
then scoped Ruff/format/mypy. No production or normal worker scheduling change.

If approved/checks pass, authorize one fresh-DB PAPER_INTERNAL20_V3 W3 with the same
§21 profile/schedule/criteria and§19 provenance; estimate35–45min total including
30min measured plus preflight/final replay/cleanup. Reuse W1/W2/overflow evidence.
Passing permits existing W4; failed/incomplete stops/report without retry or further
criterion change. No§17 diagnostic, Git/deploy/Live or4h run. No implementation or
replacement campaign under§22 has started.


Owner approved§22 on2026-11-07: harness correction, targeted held-loan/GC safety
regressions and one replacement V3 short W3, then W4 only if passed. No criteria
waiver/production/Git/deploy/Live change or automatic failed-gate retry. This approval
supersedes proposal wording within§22 only.


## 23. Route W4 worker to restored database — Approved,2026-11-07

§22 W4 backup/data/security/legacy recovery passed, but integrated F16/F17 recovery
waited on target while the worker connected to source. See
[evidence](evidence/recovery-20261106/nc12-section22-w4/analysis.md). Fix harness
wiring only; keep all financial/risk/retry/time/capacity/resource criteria and raw
historical results. No production change or larger60s recovery timeout.

Reuse profile_workload.run_worker_process and existing create_engine_for defaults.
Add an optional synchronous test-worker engine factory(defaultNone preserves current
role factory lookup/callers). W4 supplies a factory that constructs independent,
worker-owned ENGINE/ENGINE_SCAN engines for the target URLs already defined by its
restored engine mapping. Reuse create_engine_for with only the role URL temporarily
scoped during synchronous construction(no await); immediately restore ambient env.
Preserve pool5+10/timeouts/role credentials; never share/dispose parent-owned engines,
log URLs, or leave process configuration retargeted while other tasks execute.
No new infrastructure, production config surface, worker scheduling or session store.

Add real-DB two-database regressions proving actual SELECT current_database() in both
worker engines sees target despite ambient source URLs, source configuration restored
before worker awaits, same role/pool defaults, shutdown/cancellation cleanup and
original errors preserved. Existing default/CLI/worker/pool tests must still pass.
Strengthen W4 proof: source canonical data(including F16/F17 extensions) unchanged
across target recovery; all changes occur in the restored fixture. Retain pending/
exit/retry exact-once and RLS assertions. Check affected tests/Ruff/format/mypy.

If approved/checks pass, one fresh-source/fresh-target W4 with existing preflight,
fixtures,real pg_dump/restore and60s integrated recovery budget; estimate5–10min.
Pin code/config/runner/schema and cleanup both DBs. Reuse W1/W2/overflow/shortW3 and
unchanged production safety evidence; do not repeat30min workload. On failed/
incomplete stop/report without retry. On pass report this local integrated checkpoint
and remaining review/CI/Release/dependency gates; do not claim fullF17 Completed.
No Git/deploy/Live action. No§23 implementation or replacement campaign has started.


Owner approved§23 on2026-11-07: harness routing/factory and source-unchanged proof,
affected regressions/checks, then one fresh-source/fresh-target W4. Use prior valid
W1/W2/overflow/shortW3; failed/incomplete stops without retry. No other permission.


### §23 execution checkpoint — local W4 Passed

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

[Aggregate local receipt](evidence/recovery-20261106/internal-pilot-local-checkpoint-20261107.md).

### Recovery review finding fix — owner authorized,2026-11-07

Owner requested `แก้ไข` after the Medium test-isolation finding. Reuse existing
bootstrap/Alembic and role-engine fixtures with fresh session-template/function-clone
databases only for affected NC12 tests. Keep production guards and assertions;
restore scoped configuration and remove only databases created by these fixtures.
The mocked V3 parent supplies valid fake configuration. No production/criterion
change or new campaign. [Fix/check evidence](evidence/recovery-20261106/review-fixture-fix.md).

Owner authorized the separate refactor (`refactor the code`). Reuse
`backend/tests/infra/execution_market/profile_restore.py::database_url` in fixture
URL routing and centralize existing bootstrap in `_internal_scratch_database` for
template and clones. No behavior/guard/criterion change. Post-refactor scoped
validation:207tests passed together; Ruff/format/mypy passed the affected fixture.
See the same evidence receipt for exact scope and remaining gates.
