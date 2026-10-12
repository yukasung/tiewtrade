# F-11 — Capacity acceptance

วันที่: 2026-10-11
สถานะ: **Failed — C2 API lagเกินงบ; C1ผ่าน; R2-7ยังขาดexact525,600slots; C6ไม่ผ่าน**

อ้างอิง [R2-C1–C6](../performance-plan-v2.md). ไม่เปลี่ยน production code,
worker concurrency, 120s build deadline, 600s freshness หรือ admission limits.

## Environment / isolation

Dedicated PostgreSQL16.15 ที่55434 และ Redis7.4.11 ที่56380,
network `tiewtrade-f11-capacity-net`; ไม่ใช้ application DB หรือ integration-test DB.
Linux x86_64 Docker host มี20logicalCPUs/RAMประมาณ32GiB.
APIหนึ่งprocessและbuilder launcher/supervisorจริงจำกัดตัวละ2vCPU/1GiB;
builderใช้pool2/nooverflow/session global lock เดิม. ไม่มีexchange calls/orders.
Immutable image ID และ Docker limits จริงอยู่ใน
[environment.json](capacity-c1/environment.json).

Fixture ครบ5pairs×6TF มีราคาเป็นเศษและเปลี่ยนทิศ, inputเต็ม365วัน
พร้อมphysical grace. Source inventory ระหว่าง C1รอบแรก รวม appendแล้วมี3,387,825แถว:
[source-fixture.csv](capacity-c1/source-fixture.csv).
Source appendเฉพาะแท่งใหม่ที่จบตามTF; ไม่แก้history/finalityในgenerationเดิม.
Fixture setupใช้migratorในDBแยกก่อนT0; runtime source appendใช้market-data role.

ตั้งPREPAREDเฉพาะcontrolของfixtureแยกเพื่อวัดจริงตั้งแต่ไม่มีhead;
ไม่ใช้syntheticREADY/checkpoint/publisher และไม่สร้างproduction activationbundle.
นี่ไม่ใช่หลักฐานว่าproduction rollout gateเปิดได้แล้ว.

## R2-C1 — Passed

รอบล่าสุด `capacity-c1-v2`: T0 = `2026-10-11 10:27:00.251003 UTC`;
derived jobs/generations/checkpointsว่างก่อนเริ่ม. รอบแรกอยู่ใน `capacity-c1/`.
นับcold process startupรวมใน600s ไม่มีbuilder prewarmนอกเวลา.

| ตัวชี้วัด | ผล |
|---|---:|
| Series ที่มีvalid/freshREADYและcorrectGET200ภายใน600s | 30/30 |
| GET200ที่ถูกต้องครั้งแรกของseriesสุดท้าย | 365.406s |
| Attempt รวม acquire/cleanup สูงสุดในช่วงวัด | 49.026s |
| API-role proof/freshness observer | 60rounds×30series |
| HTTPจริงผ่าน5authenticatedusers คนละ6series | 10rounds×30series |
| Correct200 / cold-miss503 | 190 / 110 |
| Latencyสูงสุดของ200 | 0.328s |
| Bodyสูงสุด | 695,286bytes |

ทุก200เทียบrows/seed/finality/status/value/unit/digestกับfull-scan reference
หลังmeasuredphase; ไม่ใช้HTTP200อย่างเดียว. ตรวจ36generation identitiesที่ถูกserve.
503ก่อนพร้อมยังอยู่ในdenominator; ไม่ตัดseries/probeที่ไม่พร้อมออก.
ไม่มีผลpublicationหลัง600sถูกนำมาช่วยผ่านC1.

หลักฐาน: [ผล30series](capacity-c1-v2/result.json),
[ทุกprobe](capacity-c1-v2/probes.json), [proof samples](capacity-c1-v2/observations.json),
[queue/build/checkpoint trace](capacity-c1-v2/trace.json),
[stateที่cutoff](capacity-c1-v2/cutoff.json), [worker stop](capacity-c1-v2/worker-log.json),
[hashesของharness/source](capacity-c1-v2/source-hashes.json).

WorkerหยุดแบบDRAINED/exit0 หลังจบการวัด. C1 full-scan auditอยู่นอกmeasuredphase;
เวลาauditไม่ถูกบวกให้workerหรือAPIผ่านงบ.

## R2-7 — Partial: response/resourceผ่าน แต่exact input caseยังขาด

Restart APIprocessจริงบนprepared sourceเต็ม365วัน; cold1/warm5เป็น200ครบ,
1,000 output rows/value/seed/status/digestตรงfull-scan. Workerหยุดตลอด6requests.
LatencyรวมHTTPสูงสุด0.281s, lagสูงสุด63.374ms, RSS delta upper bound10,018,816bytes,
body695,215bytes และอ่านcandles2queries/request. ไม่มีbuildในrequest.
[ผลresponse/resourceจากproducerเดิม](capacity-c1-v2/r2-7.json), [parity/hash](capacity-c1-v2/cold-warm.json),
[metrics](capacity-c1-v2/cold-warm-metrics.json).

ตรวจboundsจากDBภายหลังพบว่าgenerationมี525,599minute slots
(`2025-10-11T10:35Z` ถึง `2026-10-11T10:34Z`) แม้sourcefixtureมีครบ365วันพร้อมgrace.
จึงยังไม่ผ่านกรณีpreparedfixture525,600ตามR2-7:
[coverage audit ที่แก้สถานะ](capacity-c1-v2/r2-7-coverage.json).
เก็บraw resultเดิมไว้ให้ตรวจย้อนหลัง; ห้ามใช้คำว่าPASSEDในraw resultนั้นเป็นหลักฐาน
R2-7ครบ. Harnessปัจจุบันassert525,600input/1,000outputและคืนexit1เมื่อไม่ครบแล้ว.

## Resources / fairness — C1 ผ่านงบ แต่ยังไม่ใช่ C4/C6 ครบ

[รายseries/claim](capacity-c1-v2/fairness-resources.json) มีmetadataครบ30series,
39attemptsที่เริ่มในช่วงC1; queuewaitสูงสุด306.855s. API300requests:
lagสูงสุด96.291ms, RSS upper bound65,761,280bytes. Worker attemptสูงสุด49.026s,
combined launcher/worker RSS upper bound2,674,688bytes. Upper boundใช้VmHWMลบ
RSSก่อนrequest/attempt จึงนับpeakก่อนหน้าอย่างconservativeด้วย.
เวลาคิว/claim/publicationใช้DBtimestamps; unavailable intervalมีsampling resolution10s.
ยังต้องผลphaseอื่นและR2-S1..S5ก่อนรับรองC4/C6.

ข้อจำกัดของรอบแรก (เก็บไว้เป็นประวัติ):

[Resource samples](capacity-c1/resources.jsonl) เก็บLinuxRSS/HWM/cgroupCPUทุกประมาณ10s.
ผลsampled sumRSS: builder136,920→สูงสุด139,212KiB;
API94,576→สูงสุด104,672KiB. Baselineนี้หลังprocessเริ่มแล้ว จึงไม่อ้างเป็น
exact RSS deltaตั้งแต่เริ่มattempt และยังไม่รับรองevent-loop lagจากชุดนี้.
47.625826sเป็นsnapshot-to-publish ไม่ใช่เวลาจากclaimcommitแบบละเอียด.
Traceเก็บeligible/deadline/dispatchround/attempt/checkpointตามจริงทุก10s;
buildสั้นอาจอยู่ระหว่างsamples จึงระบุC4เป็นpartialtraceจนมีหลักฐานละเอียดครบ.

## R2-C2 — Failed: API_RESOURCE_LIMIT

วัดจริง3,251.031s (54นาที11วินาที) แล้วหยุดตามfail-fast; ไม่ใช่60นาทีที่ผ่าน.
Observer326rounds×30series validทุกsampleที่วัด; HTTP55rounds×30seriesเป็น200ทั้งหมด.
ยังขาด34observer roundsและ5HTTP roundsจากdenominatorที่กำหนด จึงไม่อ้าง100%ครบphase.
Full-scan auditครบ233unique response signatures และ1,650responsesผ่านparityทั้งหมด.

| ตัวชี้วัด | ผล |
|---|---:|
| API event-loop lagสูงสุด | **109.465ms — เกิน100ms** |
| API RSS upper boundสูงสุด | 65,720,320bytes |
| Worker attemptสูงสุดรวมacquire/cleanup | 48.694s |
| Worker combined RSS upper boundสูงสุด | 1,179,648bytes |
| Claimsในmeasuredphase พร้อมmetadataครบ | 204 |
| Observer schedule skewสูงสุด | 0.796s |

พบrequestที่ผิดงบเมื่อ `2026-10-11 11:45:03.798732 UTC`, HTTP200,
body690,749bytes,2candle queries,server duration0.248s.
Timestampและbody sizeตรงกับprobeเดียวคือDOGE/USDT15m;
[failure witness](capacity-c2-v2/failure-witness.json).
ไม่มีbarrier/rejected loadในphaseนี้. ยังไม่ได้แยกCPUเวลาrestore/compute/render/serialization,
จึงยังไม่สรุปว่าฟังก์ชันใดเป็นต้นเหตุ. จุดที่ควรprofileต่อคือsynchronous response construction
และ`model_dump_json()`ใน`services/api/indicator_routes.py`ควบคู่กับreader.

หลักฐาน: [ผล30series](capacity-c2-v2/result.json),
[fairness/resources](capacity-c2-v2/fairness-resources.json),
[API metrics](capacity-c2-v2/api-metrics.json), [worker attempts](capacity-c2-v2/worker-attempts.json),
[observer](capacity-c2-v2/observations.json), [probes](capacity-c2-v2/probes.json),
[oracle](capacity-c2-v2/oracle.json), [metadata history](capacity-c2-v2/metadata.jsonl).
ทั้งAPI/workerหยุดแล้ว, workerexit0/DRAINED, slotIDLE/globaladvisory0:
[shutdown evidence](capacity-c2-v2/shutdown.json).

## Gate disposition / next action

[Gate summary](capacity-gates.json): C1ผ่าน, C2Failed, C3/C5ไม่ได้รันต่อ,
C4มีphase traceแต่ยังขาดครบทุกphase/R2-S1..S5, R2-7Partial และC6Failed.
ขั้นถัดไปคือprofile/แก้APIblockingภายใต้งบเดิม และทำexact525,600-slot fixture
ก่อนรันacceptanceซ้ำ. ไม่ผ่อนlag/deadline/freshness/concurrency/workloadเพื่อผ่าน.
ไม่สร้างproduction activationbundleและไม่ใช้ผลนี้อนุญาตprepared rollout/merge/Completed.

เก็บsourceของharnessที่ใช้จริงไว้ที่ [capacity-harness-v2](capacity-harness-v2/)
พร้อมhashesรายphase. หลังรันเพิ่มcache identity(source/generation/prepared_at),
ตรวจreported ageกับas_of/observed_at, บันทึกinput/output counts และjoinprobe tasksตอนcleanup.
การเพิ่มchecksนี้ไม่เปลี่ยนผลที่วัดแล้ว และไม่ใช่การรันacceptanceใหม่.
Lint/format358files, mypy330files, importcontracts7ข้อผ่าน;
4in-memorycache-identity negative controlsผ่าน. ไม่อ้างfullbackend regressionใหม่.

## ด่านที่เหลือ

C2 รอบแรกหยุดที่ประมาณ1,110s เพื่อเพิ่มการเก็บ claim/attempt ทุกงานสำหรับ C4/C6.
ผลเป็น `ABORTED_DIAGNOSTIC` ไม่ใช่ acceptance ผ่านครบ60นาที:
[diagnostic result](capacity-c2/result.json). HTTP570ครั้งก่อนหยุดเป็น200;
ข้อมูลช่วงนี้ไม่ใช้แทนการรันเต็มระยะเวลา.
รอบใหม่ใช้ measurement wrapper ของ API และ supervised worker บน imageเดิม,
เก็บเวลาจริง/lag/RSS upper bound โดยไม่แทนที่ admission/claim/scan/publish.
ล้างเฉพาะ derived fixture ใน dedicated DB หลังยืนยัน workerหยุด/slotIDLE/lock0;
เก็บ sourceและผู้ใช้เดิม และเก็บ artifact รอบแรกไว้ครบ.
Instrumentation preflightรอบ `capacity-c1-instrumented` ถูกยกเลิกจากharnessอ่าน
metadataที่builderไม่มีสิทธิ์; ไม่ใช่capacityfailureของimplementation.
แก้โดยเอาqueryออก ไม่เพิ่มgrant และรันC1ใหม่เป็น `capacity-c1-v2` ข้างต้น.

- C2: ต้องแก้resourcefailureแล้ววัด60นาทีจริงใหม่; proofทุก10s/HTTPทุก60sครบทุกseries ต้อง100%ทั้งสองตัว.
  ใช้login flowจริงกับผู้ใช้fixtureเดิม; session idle12hครอบphaseโดยไม่แก้sessionDB.
  เก็บpre-phase refreshหลังC1auditแยกจากsteady-state.
- C3: committedhistoricalOHLC burstครบ30series, recover≤600s และavailability≥80%
  ตลอด60นาที; หลังrecoverต้องพร้อม100%.
- C4: รายงานfairness/deadline/build/retry/maximum-unavailableครบทุกseries/phase.
- C5: ทำsteady-stateและdirty phasesซ้ำภายใต้BUSY/rate-denied loadที่ควบคุมได้.
- C6: ยังไม่ผ่าน; ต้องC1–C5, R2-7, worker/resource/parityครบก่อนactivation/merge/Completed.

Harness: `backend/tests/services/indicator_builder/profile_capacity.py` และ
`profile_capacity_steady.py`; ไม่ถูกcollectในnormaltest suite.
ตั้งMIGRATOR/API/MARKET_DATA URLsไปdedicated55434 และtestRedisไป56380.
รันC1บนfreshmigratedDBด้วย `--output <new-directory>`;
C2ใช้ `--c1 <C1-evidence-directory> --output <new-directory>`.
ใช้ `--metrics <instrumented-metrics-directory>` เพื่อบังคับตรวจresourceระหว่างphase;
C3เพิ่ม `--phase dirty --requires <C2-directory>`;
C5ใช้ `--load-metrics <api-metrics.jsonl>` พร้อมprerequisite phaseที่ผ่าน.
C3/C5paths implementไว้แต่ยังไม่ได้รันผ่านในรอบนี้ เพราะC2failed.
C2ปฏิเสธC1ที่ไม่ผ่าน และถ้าพบgapจะบันทึกFailedพร้อมเวลาจริง ไม่อ้างearlystop
เป็นการวัดผ่านครบ60นาที. เก็บ artifact และ sourceDB สำหรับตรวจหลักฐาน;
runtime containers และ derived fixture อาจสร้างใหม่ระหว่างรอบ โดยเก็บ log/state ก่อนหน้า.
