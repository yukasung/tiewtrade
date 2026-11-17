# NC-F17-REBUILD20-02 — full rebuild หลังปรับ fixture preparation

สถานะ: **Approved — owner replied approve 2026-11-16; one campaign after affected checks**
วันที่: 2026-11-16 (Asia/Bangkok)
ขอบเขต: amendment ของ F-17 ใน branch เดิม ไม่ใช่ feature ใหม่
ฐาน: [REBUILD20-01](rebuild20-isolated-plan.md),
[PREP20-01](fixture-preparation-capacity-plan.md),
[ผล capacity](evidence/endurance20-20261115/prep20-checkpoint.md) และ
[review fixes/refactor](evidence/endurance20-20261115/prep20-review-fixes.md)

## 1. Requirements ที่คงเดิม

ตรวจ offline full rebuild หนึ่งรอบก่อนพิจารณารันสี่ชั่วโมงอีกครั้ง ไม่ตรวจ HTTP/risk
throughput หรือรับรอง endurance ในรอบนี้ และไม่ทำให้ F-17 Completed

- 20 บัญชีจำลอง กระเป๋าใหม่ บัญชีละ 20 baseline LIMIT orders รวม 400
- บัญชีละ 282 cycles ตาม cycle เดิม 5 คำสั่ง รวม 28,200 คำสั่ง: 11,280 fills,
  5,640 cancels, 5,640 idempotent replays; รวม 5,640 cycles และไม่มีคำสั่งถูกปฏิเสธ
- ประวัติตลาด public ที่ commit จริง 96,000 รายการ และ private source records
  บัญชีละ 96,000 รวม 1,920,000 รายการ ไม่ใช้ position ว่างแทนประวัติการเงิน
- ใช้ Money/Quantity และ financial/global oracle เดิมทั้งหมด: เงิน ค่าธรรมเนียม
  reservation, held/cost, position, cash/trade/correction ledger และ duplicate effects
- 20 final snapshots, concurrency 4, p95 ≤250ms และ p99 ≤1s ตาม PositionChecks เดิม
- full replay ทั้ง 20 บัญชีทีละบัญชี ≤60s/บัญชี ครอบทั้ง session/query/driver/decode/
  position/cash/evidence/checkpoint/exit ไม่ reset timer หรือตัดช่วงอ่านหลักฐานออก
- RSS ≤1 GiB ต่อ process, pool capacity/คืน connection ตาม contract เดิม,
  source head/private history ตรงกัน และ final lag 0; disk headroom ≥2 GiB
- ไม่แก้ production SQL, API/schema/session/สิทธิ์ สูตรเงิน admission/risk/Live,
  lease 5s, fencing, source guard, cycle 60s หรือ retry policy

## 2. สิ่งที่เปลี่ยนจาก REBUILD20-01

### 2.1 Runtime ของ fixture

ใช้ prepare_economics(parallel_runtime=True) ที่ผ่าน short capacity แล้ว:
20 worker processes, R8 limit 20/claim 1/claim coordination, 20 owner flows,
parent polling limit 4 และ fixture publisher 10Hz แบบเดิม ค่า default ของโปรไฟล์อื่นคงเดิม
F15 AllowPaperPolicy ใช้เฉพาะ fixture ที่ guard ฐาน local internal20; ไม่อ้างว่าตรวจ
integrated TransactionalRiskPolicy หรือ authenticated HTTP ผ่านแล้ว

ราคา refresh ทุก book tick ตาม implementation ที่ตรวจแล้ว ไม่ใช่ W3 ราคา 1Hz
ผลรอบนี้จึงเป็น offline rebuild proof เท่านั้น ไม่มีการแก้ cadence เพิ่มในขอบเขตนี้

### 2.2 ลำดับ handoff ของ public history

โค้ดเดิมคืนจาก prepare_economics หลัง stop/join publisher และ workers แล้ว จึงเหลือ
book lease อายุไม่เกิน 5s แผน/runner เดิมอ่าน financial/global และ economic digest
ก่อน extend public history ซึ่งอาจใช้ lease window หมดโดยไม่เกี่ยวกับ rebuild SLA

ให้เรียก publisher.extend(96000) ทันทีหลัง prepare_economics สำเร็จ ก่อนการอ่าน oracle
ที่อาจนาน โดยคงทุก oracle: ตรวจ financial/global และบันทึก economic digest หลังต่อ
public historyแต่ก่อน private fanout แล้วตรวจซ้ำหลัง fanoutและก่อน timed rebuild
การต่อ public history ใช้ MARKET_DATA เดิม ไม่มีสิทธิ์แก้เงิน/ออเดอร์

ไม่แก้ lifecycle ของ publisher เพิ่มในรอบนี้: หาก worker shutdown หรือการ flush ทำให้
lease หมดก่อน handoff, renew/guard เดิมต้องปฏิเสธและจบรอบ Incomplete เก็บ witness
ห้าม reacquire, ข้าม guard, เพิ่ม heartbeat ลับ หรือส่ง publication ทดแทน
จุดนี้ยังเป็นความเสี่ยงที่อาจทำให้รอบไม่ครบ ไม่ถือว่า short capacity พิสูจน์แล้ว

### 2.3 หลักฐานและ cleanup

Runner ฉบับใหม่อยู่ในโฟลเดอร์ผลใหม่ ไม่แก้ runner/ผลย้อนหลัง และต้อง bind:
HEAD + working-tree diff/source inventory รวม untracked source, configuration,
migrations/schema, runner copy/hash และ external helper copy/hash ที่ตรวจแล้ว
ใช้ load_fixture_helpers กับ expected SHA-256 ที่ระบุไว้ก่อน execution ไม่มีการคำนวณ
expected hash จาก source แล้วเชื่อเองในจุดเรียก ตรวจ pinned helper และ runner ซ้ำตอนจบ
helper/environment มีข้อมูล local configuration ให้เก็บแบบ private ไม่เผยแพร่ทั้งต้นไม้

ใช้ fixed five-pool parent inventory และ worker inventory เดิม; ต้องมี 20 runtime PIDs,
exit receipts และ worker pool reports ครบ รวม parent เป็น 21 reports ไม่ยอมรับแค่ parent
sample RSS ของ parent + live owned workers เก็บ phase/timing/progress และ partial counts
ใช้ bounded fixture shutdown ที่แก้แล้ว รวม startup failure; signal failure ไม่ข้าม sibling
เก็บ primary exception และ remaining PIDs ห้ามลบฐานถ้า owned worker/connections/locks
ยังไม่หมด เก็บ resource identifier และรายงาน Incomplete แทน force drop

## 3. ลำดับและงบเวลา

### เตรียมพร้อมก่อนนับเวลา campaign

1. เมื่ออนุมัติแล้ว ทำ runner ใหม่จาก runner REBUILD20/PREP20 และ helpers ที่มีอยู่
   ไม่สร้าง orchestration framework ใหม่ แก้เฉพาะ binding/options/ลำดับ/receipts ที่จำเป็น
2. ตรวจ targeted tests ของ handoff order, counters/options, partial failure/cancellation,
   worker/pool aggregate, helper pin/hash และการรักษา exception/cleanup ไม่ลด assertions
3. ใช้ real-DB small fixture default/parallel ที่มีอยู่สำหรับ economic/no-write/source/
   full replay และ actual worker proof ที่ได้รับผลกระทบ; ไม่ใช้ mock แทน DB proof
   ใช้ evidence decoder/lifecycle tests ที่ยัง valid ต่อ ไม่รัน full suite เป็นพิธี
4. Ruff/format/mypy เฉพาะส่วนที่เปลี่ยน และ whitespace ตรวจ runner AST/binding ให้ตรง
   candidate จริง ก่อน runtime หากต้องเพิ่ม source นอก amendment ให้บันทึกก่อน

### Campaign หนึ่งรอบ

- ประเมิน campaign 30–60 นาที รวม preflight/seed/history/rebuild/cleanup;
  cap เดิม 3,600s นับตั้งแต่เริ่ม preflight กันช่วง cleanup 120s ภายในงบเดียวกัน
  ใช้เวลาที่เหลือลดงบงาน ไม่ reset deadline ทุก phase หรือเริ่ม owner ใหม่เกินงบที่เหลือ
- การเตรียมแผน/runner/tests และสรุปนอก campaign รวมประเมิน 45–85 นาทีทั้งหมด
  เป็นงบวางแผน ไม่รับรองเวลาจากการคูณ short capacity 54s เพราะ SQL/history โตต่างกัน
- บันทึก monotonic และ wall timestamps ราย phase พร้อม deadline/cleanup elapsed;
  cancellation/unwind หรือระบบปฏิบัติการอาจทำให้คืน control ช้า ต้องรายงาน elapsed จริง
  หากเกิน budget ห้าม grade Passed; ห้ามรอ cleanup ไม่สิ้นสุดหรือ force resource removal
- Preflight 120s/7 samples เดิมหนึ่งครั้งก่อนสร้าง fixture: load1 ≤ logical CPU,
  disk ≥2GiB ทุก sample, PG healthy/Redis ready/no restart loop ก่อนและหลังช่วงตรวจ
  ค่าขาด/ผิดรูป/ไม่ผ่านให้ Incomplete และหยุด ไม่วนรอจนเครื่องว่าง
- ไม่หยุดโปรแกรมหรือบริการของเจ้าของเอง หากมี competing workload ให้รายงานเป็น
  environment limitation ตามหลักฐาน ไม่ตัด slow samples หรือเปลี่ยนเกณฑ์
- Fresh owned local DB/migrations; ไม่สร้าง Redis ใหม่ ไม่มีบัญชีเจ้าของหรือ Live
- Economic fixture → join mutators → public extension ทันที → financial/global/digest
  → private fanout (500-record batches, original RLS/constraints) → exact source/head/
  counts/digest และ financial/global → snapshots/full rebuild → resource/pools → cleanup
- Public extension ใช้ original publish_input/renew/fence ใน transaction ละไม่เกิน20inputs;
  journal หลัง normal commit เท่านั้น ห้าม raw READY/head update หรือสร้าง source ปลอม
- ต้องบันทึก financial ผลสำเร็จก่อนขั้น full rebuild ราคาแพง ถ้า replay ล้มยังเก็บผลนั้นไว้
  แต่ไม่เปลี่ยน campaign ให้ Passed ไม่อ่านผลข้าม owner หรือข้าม error เพื่อทำจำนวนให้ครบ
- หาก publisher/worker/IO/source proof ล้ม หยุดตาม flow เดิม เก็บ partial counters,
  stage/owner/timing และอ่าน source owner/generation/cursor ด้วย independent connection
  ถ้าทำได้โดยปลอดภัย ไม่ retry/reacquire แล้ว normal cleanup เฉพาะที่พิสูจน์ ownership
- หลัง dispose/join ตรวจ independent DB connections/advisory locks และ worker exit;
  ลบเฉพาะฐาน owned ที่พิสูจน์แล้ว ตรวจ DB absent อีกครั้ง พร้อม health บริการเดิม

## 4. Validation matrix

| ระดับ | เกณฑ์และหลักฐาน |
|---|---|
| Feature | Options/default isolation, immediate history handoff และไม่มี oracle ถูกตัด, exact counters, original-call/commit-before-journal, exception/cancellation/IO, bounded owned-child cleanup/remaining PIDs, pinned helper mismatch/reuse, fixed parent+20 worker pool reports, scoped static |
| Feature | Existing small real PostgreSQL fixture: exact Money/Quantity/global/RLS/source digests, private padding ไม่เปลี่ยน economic facts, full small replay; เก็บผลที่ยัง valid และ rerun เฉพาะที่โค้ด/runner กระทบ |
| Batch — scoped offline | หนึ่ง campaign 20×282 cycles, 96,000 public + 20×96,000 private, money/global/digest ก่อน full replay, snapshots/rebuild ครบ20ownerตามเกณฑ์เดิม, resource/pool/source/cleanup ครบในงบ |
| Release — คงค้าง | Four-hour W3, original100-account Release, lease root-cause/sampler gaps และ F17 bot/notification/Live dependencies ไม่ถูกปิดด้วยผลนี้ |

Passed ได้เฉพาะเมื่อทุกเกณฑ์ของ scoped run ครบ หลักฐานขาด/commitไม่ชัด/fixtureผิดรูป/
preflightหรือenvironmentไม่พร้อมเป็น Incomplete; เกณฑ์ที่วัดครบแต่เกิน bound ต้องรายงาน
Failed ตามขอบเขตที่วัด พร้อมเหตุผล ไม่ใช้จำนวนคำสั่งครบแทน financial correctness

## 5. จุดอนุมัติและจุดหยุด

เอกสารนี้เป็น amendment ข้อเสนอ ไม่ใช่ผล campaign และคำสั่งเริ่มจัดทำแผนไม่ใช่การ
อนุมัติรายละเอียดใหม่ล่วงหน้า เมื่อเจ้าของ approve ให้ทำ runner/checks และ campaign
หนึ่งรอบต่อเนื่องเมื่อด่านก่อนหน้าผ่าน โดยไม่ขอเริ่มงานย่อยซ้ำ แต่ยังรักษา AGENTS.md:
หากเพิ่ม source ครบตาม scope ต้องแจ้ง checkpoint ที่เหมาะสม ไม่ข้าม owner review/
refactor เมื่อกฎนั้นบังคับ และหยุดเมื่อความปลอดภัยพิสูจน์ไม่ได้/เกณฑ์เดิมล้ม3รอบ

เมื่อ campaign จบหรือไม่ผ่าน ให้สรุปหลักฐาน completeness/cleanup และข้อเสนอถัดไป
แล้วหยุด ไม่แก้ performance หรือรันใหม่/full history รอบทดแทน/สี่ชั่วโมงเอง
ไม่มี commit/push/CI/merge ในขอบเขตนี้ คง REBUILD20-01 Incomplete, PREP20 scoped
Passed พร้อม provenance limitation และผล W3 Incomplete ทั้ง4รอบตามเดิม


## Readiness — before the approved single campaign

Owner approved 2026-11-16. New runner only; no repository runtime source changes in
this execution scope. 93 targeted tests Passed in 37.789s including fresh owned real
PostgreSQL, actual20-process fixture, financial/source/full small replay and fixed
pool inventories; normal test DB cleanup complete. Three extracted-runner orchestration
checks Passed: successful immediate source-extension order, lease rejection before
oracles, monetary failure before padding/rebuild. Five-file Ruff/format/mypy Passed;
retained tests exercised the reviewed/refactored shutdown/helper binding implementation.
Runner uses exact reviewed external-helper digest and exclusive pinned copy; source,
runner/config/helper/migrations binding and one120s preflight will precede fixture.
No production or financial rule change. One campaign now starts under approved3600s
budget with120s cleanup reserve. No automatic second attempt or four-hour follow-on.


2026-11-16 [REBUILD20-02 campaign](evidence/endurance20-20261115/rebuild20-02-checkpoint.md)
Incomplete after1149.152s at economic fixture: terminal traceback maps to the existing
100000-row in-memory ParentPollGate trace guard; full-rebuild60s not measured.
17530/28200commands completed by partial counters,7006fills,10170journalrecords;
finalfinancial/global/96000history/snapshots/rebuildNotRun. 93targetedrealDB/process tests,
3runnerorchestration checks/scopedstatic Passed beforehand. Source/helper binding stable;
20workers exited0,poolsPassed;parent/aggregatepool Failed/Incomplete from unwind
ConnectionResourceError retained despite allfinalborrows0/disposed. Independent ownedDB
absent/0connections/locks/nochildPIDs,existingservicesunchanged. Next proposal use existing
streamed poll evidence +finalsummary,retain guard/defaults andtest IO/cancel/100k+ attempts;
no sourcefix/rerun authorized by this endedonecampaign scope. Priorgrades/F17pendingunchanged.
