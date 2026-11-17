# NC-F17-REBUILD20-04 — งบเวลา offline campaign ให้ครบการตรวจปิดท้าย

สถานะ: **Approved A — owner replied approve 2026-11-16; one campaign after runner checks**
วันที่: 2026-11-16 (Asia/Bangkok)
ขอบเขต: ทบทวนงบ orchestration ของการทดลอง F-17 เดิม ไม่เปลี่ยนเกณฑ์เงินหรือ SLA รายบัญชี
ฐาน: [REBUILD20-03](rebuild20-streamed-execution.md),
[หลักฐานรอบล่าสุด](evidence/endurance20-20261115/rebuild20-03-checkpoint.md),
[ผลตัวเลข](evidence/endurance20-20261115/rebuild20-03-summary.json)

## 1. ข้อสรุปจากหลักฐาน

รอบล่าสุดมี position-result.passed=true: snapshot ครบ20บัญชี p95/p99 23.723/24.215ms
และ full replay ครบ20บัญชี บัญชีละ96000records ใช้34.222–47.742s ทุกบัญชี≤60s
เงิน/global oracle20บัญชีผ่านก่อน replay, final input lag0 และ digest ข้ามขั้น
private padding ผ่าน Streamed poll170913records/countsครบ

ทั้ง campaign ยังเป็น Incomplete เพราะหมดงบงานหลัก3480s(58นาที) แล้ว cancel ระหว่าง
post-rebuild economic_digest ก่อน resource/pool acceptance เสร็จ ยืนยันด้วย partial
verification และ ADMIN_OBSERVER cancellation await-chain จึงห้ามรับรอง post-rebuild
immutability หรือ regrade aggregatepool ที่ Failed/Incomplete ให้ผ่าน

### การแบ่งเวลาที่ใช้จริง

| ขั้น | เวลาจากหลักฐาน |
|---|---:|
| Preflight + migration ก่อน economic fixture | 127.407s |
| Economic fixture20บัญชี/28200คำสั่ง | 1773.883s |
| ต่อ public history ถึง96000 | 181.679s |
| Financial/global ก่อน private history | 2.612s |
| Private padding + ตรวจเตรียมข้อมูลก่อน full rebuild | 651.260s |
| รวมจนเข้าฟังก์ชัน final verification/rebuild | **2736.841s (45นาที36.841วินาที)** |
| ผลรวม elapsed ของ20 serial replays | **737.618s (12นาที17.618วินาที)** |
| ส่วนที่เหลือใน work budget3480s | **5.541s** |

5.541s คือเวลาสำหรับงานอื่นทั้งหมดใน final verification ที่อยู่นอก20replays
รวม financial/global/snapshot/digest ก่อนและหลัง ไม่ใช่เวลา digest หลัง replay ที่วัดแยกได้
ไม่มี span แยกแต่ละ digest จึงไม่อ้างว่าพบ query หรือ server bottleneck ในขั้นนี้
หลักฐานรองรับการแก้ budget/headroom ของ campaign ไม่รองรับการผ่อน60sต่อบัญชี

## 2. ข้อเสนอและทางเลือก

### A — เพิ่มเฉพาะงบรวมเป็น70นาที (แนะนำ)

เปลี่ยน total campaign budget3600→4200s และคง cleanup reserve120s เท่าเดิม
จึงมี work deadline4080s(68นาที) นับต่อจากจุดเริ่มเดียว ไม่ reset ทุก phase

ที่มา: preparation ที่วัด2736.841s + งบ20×60sสำหรับ replay ทุกบัญชี + เผื่อขั้น
verification/ปิดท้าย120s + cleanup120s =4176.841s จึงปัดขึ้นเป็น4200s
เวลาเผื่อ verification120s เป็นงบวางแผน ไม่สร้าง SLA/timeout แยกใหม่ให้ digest
และไม่รับรองว่าจะเพียงพอทุกสภาพเครื่อง หากเกินงบหรือหลักฐานขาดยังต้อง Incomplete

คาดประมาณ58–65นาทีถ้าสภาพเครื่องใกล้รอบก่อน จำกัดรวม70นาทีหลัง runner checksพร้อม
ใช้120s preflight/7samples เดิมหนึ่งครั้งก่อนสร้าง fixture ทุก sample และ service checks
ต้องผ่าน ไม่รอวนหรือปิดโปรแกรม/บริการอื่นแทนเจ้าของ

### B — คงงบรวม60นาที

ไม่รัน profile เดิมซ้ำทันที เพราะหลักฐานแสดงว่าเกือบไม่เหลืองบสำหรับ checksปิดท้าย
หากต้องคง60นาที ให้จัดทำอีกแผนเพื่อลดงานเตรียมซ้ำด้วย checkpoint/restore หรือปรับ
ประสิทธิภาพที่พิสูจน์ได้ ต้องมี ownership/source/financial/evidence proof และ tests
ของวิธีนั้นก่อน ไม่อนุมัติวิธีใหม่หรือเดาเวลาพัฒนาจากเอกสารนี้

ไม่แนะนำการลดจำนวนบัญชี/history, ตัด digest, ยกเว้น pool error,ลด cleanup reserve
หรือเพิ่ม60sรายบัญชีเพื่อให้ผลเดิมผ่าน ไม่มีการแก้เกณฑ์ดังกล่าวในข้อเสนอA

## 3. Requirements / invariants ที่คงเดิม

- 20บัญชีจำลอง,400baseline,282cyclesต่อบัญชี,28200คำสั่ง:11280fills/5640cancels/
  5640idempotentreplays ตามจำนวนเงิน/fee/Money/Quantity/domain rules เดิม
- public committed inputs96000; private source96000ต่อบัญชี รวม1920000;ตรวจdigests/
  constraints/RLS/owner/mode,final lag0 และ economicfactsไม่เปลี่ยนทั้งpaddingและreplay
- exact financial/global oraclesครบก่อน expensive replay และ post-rebuild digest
  ต้องกลับสำเร็จและเท่าก่อนหน้า ไม่ใช้ position-resultอย่างเดียวแทน wholecampaign
- snapshots20/concurrency4/p95≤250ms/p99≤1s;fullreplayทีละowner≤60s ครอบsession/query/
  driver/decoding/fold/evidence/checkpoint/exit;ไม่ยกเว้น slow samples หรือ resetเวลา
- source lease5s/fence/guard/no retry/reacquire;fixture20workers/R8claim1/coordination,
  10Hzbook+price fixture,ownerflows20,poll4/cadence0.25/cycle60s ตามเดิม
- streamedpollครบทุกattempt,finished=attempts=JSONLrows,active0/truncatedfalse;
  defaultmemoryguard100000ไม่เปลี่ยน ต้องผ่าน21pool reports/validatorเดิม
- RSS≤1GiB/process,diskheadroom≥2GiB,owned-child/connection/lock proof และ cleanup
  ต้องครบ ไม่ forceDROP หรือส่งคำสั่งowner/Live ไม่เปิดบริการ/infraใหม่
- ไม่มี public API/schema/session/production query/risk/strategy/exchange change
  เป็น offline rebuild proof ไม่ใช่ D20/W3/endurance/100accountRelease หรือ F17 Completed

## 4. Implementation หลังอนุมัติA

ทำ runner ใหม่ใน outputroot ใหม่จาก REBUILD20-03 เปลี่ยนเฉพาะ runidentity และ4200s
budget โดยเก็บ reserve120s และใช้ remaining() เดียวกันกับ owned helper/subprocess
ไม่แก้ source/harness ที่เพิ่ง review/refactor หรือปรับ SQL เพื่อให้ทันเวลา

Reuse prepare_economics(parallel_runtime=True),ทันทีที่mutatorsjoinให้ extend96000
ก่อนอ่าน receipt/oraclesที่อาจนาน;leaseหมดต้องหยุด ใช้ private fanout และ
verify_rebuild/PositionChecks/economic_digest/OwnedPools เดิมตามลำดับทั้งหมด
หลัง await verify_rebuild คืนสำเร็จจึงตั้ง explicit receipt ว่า final verification
รวม post-rebuild economic digest ผ่าน ห้ามตั้งในfinallyหรือจากจำนวน replaysอย่างเดียว

Pin HEAD+diff+untrackedsource inventory/config/migrations/schema,runnercopy/hash และ
reviewed external-helper copy/hash ก่อน fixture เทียบ source ของ safety/refactor
receiptกับcandidateจริง คง source ตลอดรอบ และตรวจ runner/helper bindingซ้ำตอนจบ

ใช้หลักฐาน113realPG/process/replay +28focusedrefactorที่ยังvalidต่อ;ไม่รันชุดใหญ่ซ้ำ
เมื่อ source/behavior ไม่เปลี่ยน ตรวจ runner AST/ค่าคงที่ budget/reserve และ reuse
orchestration checks:ลำดับhandoff,lease rejection,money/evidence failureหยุดphaseถัดไป,
finalverificationไม่ผ่านต้องไม่มีPassedreceipt และdeadlineหยุดโดยไม่ข้ามcleanup
หากต้องเปลี่ยน runtime source เพิ่ม ต้องบันทึกขอบเขต/ตรวจผลกระทบก่อนตามAGENTS.md

## 5. ลำดับ campaign และ validation

เมื่อ A อนุมัติและ runner checksผ่าน จึงเริ่มหนึ่งรอบต่อเนื่อง:
preflight → freshownedDB/migration → economicfixture → joinedmutators/publicextension
→ streamedtraceproof → financial/global/digest → privatepadding/digest/sourcecounts
→ finalfinancial/global/snapshots/full20replays/postdigest → resource/pool → cleanup

| ระดับ | ด่าน |
|---|---|
| Feature — retained | Reviewed/refactored source safety cases/static และ affected runner checks ตามข้อ4;หลักฐานเดิมใช้ได้เฉพาะส่วนที่candidate/dependencyไม่เปลี่ยน |
| Batch — scoped offline | profileเต็มและทุกoracle/digest/resource/pool/cleanupครบภายใน4200s;source/head/counts/ownerตรงตามจริง |
| Release — คงค้าง | 4h W3,original100accountRelease,leasecause/sampler และ bot/notification/Live dependencies ไม่ปิดด้วยผลนี้ |

เก็บ partialreport/status/phase/timing/counters/financial/position receipts แม้ closingcheck
ล้ม Rooterror/CancelledErrorและevidenceIOต้องไม่กลบกัน หาก publisher/workerล้มให้อ่าน
independentcursor/owner/generationเมื่อปลอดภัย ไม่ส่ง publication/คำสั่งทดแทน

หลังjoin/dispose ตรวจ process/connection/lock;ลบเฉพาะDBที่ownershipและquiescenceพิสูจน์
ได้ แล้วตรวจ DB absent/0connections/locks อิสระ หากล้างไม่ได้เก็บidentifierและรายงาน
อย่าหยุดบริการอื่นหรือ forceDROPเพื่อปิดงาน Resourceobservationsหลังstopไม่ regrade
poolvalidatorที่Failed หรือข้าม digestที่ยังไม่ครบ

## 6. จุดอนุมัติ / จุดหยุด

เอกสารนี้เป็นข้อเสนอเท่านั้น ขณะจัดทำไม่มี source/runner edit,test/workload,
Git/CI/merge ใหม่ ต้องรอเจ้าของเลือกAหรือBก่อนปรับ runner/ทดลอง

หากอนุมัติA ให้เตรียมและตรวจrunnerแล้วรันหนึ่งcampaignโดยไม่ขอเริ่มงานย่อยซ้ำ
เมื่อจบ/ล้มให้เก็บหลักฐาน/cleanupและหยุดรายงาน ไม่แก้ performance/เพิ่มงบ/รันซ้ำ/
เริ่ม4hหรือGit/CI/mergeต่อเอง หากผิดเงื่อนไขความปลอดภัยหรือกฎหยุด3รอบให้รักษาจุดหยุดเดิม

คง REBUILD20-03 IncompleteและaggregatepoolFailed/Incomplete รวมผลsubchecksที่Passed;
ไม่ต่อเวลา/เปลี่ยนcandidateย้อนหลังเพื่อให้รอบเดิมผ่าน และไม่ประกาศ F17Completed


## Approved A execution readiness — 2026-11-16

Owner approve authorizes one4200s campaign after runner checks. No repository runtime
source change; retained113realPG/process/replay and28focusedrefactor proofs bind to
currentcandidate through startuphashchecks. New runner has freshoutput/runidentity,
4200s total/reserve120s and explicit final-verification receipt only after original
verify_rebuild returns successfully. Five extracted-runner cases Passed:success,
lease rejection,money failure,missingpoll evidence,closingdigest failure;AST and
budget/reserve consistency Passed. Begin onepreflight thenfreshDB campaign ifready.
No automaticreplacement/full4h/sourceoptimization/Git/CI/merge after this run.


2026-11-16 [REBUILD20-04 Approved A campaign](evidence/endurance20-20261115/rebuild20-04-checkpoint.md)
Passed scopedofflinefullrebuild20:total3531.425s(58m51.425s),budget4200/reserve120 unchanged.
All28200commands/20financial/globaloraclesPassed,96000public+20x96000private/lag0/
paddingdigest/poll177002recordscomplete.20snapshots p95/p99=8.568/8.580ms;all20fullreplays
Passed≤60s(seeperownerreceipts). Mandatorypostrebuildeconomicdigestcompleted;explicitfinal
verificationreceipttrue. All21poolreports/resourcechecksPassed;normalownedcleanup and
independentDBabsent/0connections/locks/nochildPIDs verified;existingservicesunchanged.
Source/runner/helperbindingstable,production/harnessruntimeunchanged. PriorIncomplete/
poolFailed gradesretained. Offlinegapclosedonthiscandidate;F17PendingFullValidation/
notCompleted (4hW3/Release/dependencies remain). Nextobserver/failure-cleanup readiness
beforeexplicitnew4hproposal;no automatic4h/Git/CI/merge in this stop/reportscope.
