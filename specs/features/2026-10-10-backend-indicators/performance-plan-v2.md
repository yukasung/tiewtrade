# F-11 — Performance รอบ 2: prepared generations + checkpoints

สถานะ: **Approved** — เจ้าของอนุมัติทั้งฉบับพร้อมADR-002และamendmentsของF-11/F-09เมื่อ2026-10-10 ตามคำสั่ง “approve”; NC-35 Closed
วันที่: 2026-10-10
Branch: feature/f-11-backend-indicators

## R2-D1 first-release amendment — Approved 2026-10-11

เจ้าของยืนยันว่าไม่เคยdeploy F-11 full-scan เดิม และอนุมัติ
[D1 first-release amendment](d1-amendment-proposal.md) ด้วยคำสั่ง “approve”.
ใช้เกณฑ์ทั้ง5ข้อใน amendment แทน R2-D1 legacy-F-11-binary เดิมเฉพาะส่วนนี้:
ทดสอบ pre-F-11 API/F-09จริงก่อนstrictproof และ compatibleF-11สองreplicas
ในLEGACYด้วยv1cross-replica/restart/fullscanparity พร้อมstagegate/drain/inventory
negativecontrols. ห้ามstubและไม่ผ่อนD2..D7/capacity/productionactivation.
D1เป็นPendingจนหลักฐานครบ ไม่ถือว่าการอนุมัติคือPassed


## เปลี่ยนลำดับการตรวจรับ — Approved 2026-10-11

เจ้าของยืนยันให้เลื่อนการทดสอบโหลดและความเสถียรระยะยาวไปตรวจรับระบบรวม
**ชุดที่ 9 — ตรวจรับระบบก่อนใช้งานจริง หลังพัฒนาชุดที่ 8 เสร็จ** ตาม [roadmap](../../roadmap.md#ชุดที่-9--ตรวจรับระบบก่อนใช้งานจริง)
ข้อความนี้แทนลำดับเดิมที่ให้รันทดสอบยาวทันทีท้าย implementation ของ F-11;
ไม่เปลี่ยนสูตร งบ ระยะเวลาวัด workload หรือเกณฑ์ผ่านของการตรวจรับ

ระหว่างพัฒนายังคงทดสอบความถูกต้อง ความปลอดภัย การคำนวณเงิน และ regression
ที่เกี่ยวข้อง ผล Failed/Partial เดิมและ API lag ที่พบยังเป็นงานค้าง ไม่ถือว่าผ่าน
R2-C2/C3/C5 รอบเต็มและการตรวจรับ capacity/ความเสถียรที่ต้องใช้ผลเหล่านั้น
ให้รวมในชุดที่ 9; การ profile สั้นและการแก้ปัญหาที่ทราบทำได้ระหว่างพัฒนา

เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบ จึงใช้สถานะ
Development Complete (พัฒนาเสร็จ รอตรวจรับระบบ) ตาม roadmap ได้ ไม่ใช่ Completed
เจ้าของอนุมัติ 2026-10-11 ให้ merge เพื่อพัฒนาต่อได้เมื่อ implementation/review และด่านที่ไม่เลื่อนผ่านครบ ตาม [testing standard](../../standards/testing.md#1-ต้องเขียวก่อน-merge);
ข้อความนี้แทนเงื่อนไขก่อน merge ใน baseline ด้านล่างเฉพาะการตรวจรับโหลด/ระยะยาวและผลรวมที่พึ่งรอบนั้น; รายการอยู่ใน [ทะเบียนชุดที่ 9](../../roadmap.md#ทะเบียนงานค้างสำหรับชุดที่-9) ไม่ยกเว้นด่านอื่นหรือผล regression ที่ล้ม และไม่ใช่คำสั่งให้ commit/push/merge ตอนนี้ เงื่อนไข Completed และ production prepared activation เดิมยังมีผล
ต้องผ่านชุดที่ 9 ก่อน F-25 ใช้เงินจริงหรือเปิดให้คนนอก ระหว่างนี้ทดลองภายในด้วย Paper
ก่อนเริ่มทดสอบยาวให้ตกลงเวลากับเจ้าของอีกครั้ง


เจ้าของอนุมัติหลังreviewรอบสุดท้ายที่ได้ผลAPPROVED ด้วยคำสั่ง “approve”
ครอบคลุมรายละเอียดทั้งฉบับ, ADR-002 และrequirements/plan/validation amendments
ของF-11/F-09 รวมnumericwindowrecoveryและsupersessionbudget/durablefairround
เอกสารนี้เป็นแหล่งเดียวของamendmentsที่อนุมัติสำหรับรอบนี้ มีผลแทนbaseline
เฉพาะส่วนที่ระบุเปลี่ยน; ส่วนอื่นและNC-30..34ยังคงเดิม
พร้อมเริ่มimplementationตามลำดับด้านล่าง; approvalไม่ใช่ผลvalidationผ่าน

## ปัญหาที่ต้องแก้

[Batch report](profiling/batch/report.md) ลด lag/RSS แล้ว แต่ cold API ยัง504
และรอบจับเวลาอ่านได้307,240จาก525,600ช่องก่อน30s การเก็บstateเฉพาะในcursor
ไม่ได้แก้หน้าแรก; materializeผลทุกแท่งหลายรุ่นเป็นเวลาหลายชั่วโมงใช้พื้นที่มาก
ข้อเสนอคือworkerสร้างdigestและcheckpointครบชุดล่วงหน้า แล้วAPIตรวจsource fence
และคำนวณเฉพาะช่วงจากcheckpointถึงoutputpage โดยไม่สแกน365วันทุกหน้า

## NC-35 — Closed: การเปลี่ยนสัญญาที่เจ้าของอนุมัติ

| เรื่อง | สัญญารอบนี้ | สิ่งที่เปลี่ยนจากสัญญาเดิม |
|---|---|---|
| Cold miss | GETคืน503 INDICATOR_DATA_NOT_READY/Retry-After:10 เมื่อไม่มีรุ่นพร้อมและไม่มีnumeric failureที่พิสูจน์ได้; numeric failureคง422ตามNC-33; schedulerเป็นผู้สร้าง ไม่มีGETenqueue; ต้องผ่านbootstrap capacityสำหรับทั้ง30seriesตามR2-C1..C6 | หน้าแรกที่ยังไม่มีcheckpointไม่รับรอง200ภายใน30s แต่503ต่อเนื่องเกินเกณฑ์เป็นfailure ไม่ใช่ผลผ่าน |
| ความสดของหน้าแรก | เลือกheadล่าสุดเพียงรุ่นเดียวที่ยังvalidและ `now − generation.as_of <= 600s`; ถ้าไม่ผ่านให้503 ไม่fallbackรุ่นเก่า | as_ofมาจากsnapshotของbuilder ไม่ใช่เวลารับGET; อาจย้อนหลังได้สูงสุด10นาที ต้องแสดงเวลา/ageตามจริง |
| Retentionต้นทาง | Public GET/POST/ingest F-09คงlogical365วัน; physicalcleanupเลื่อนออกอีก6h15mสำหรับตรวจgeneration/continuation | เปลี่ยนนโยบายphysicalcleanupของF-09; ไม่เปิดpublicwindowเกิน365วัน และไม่ดึงข้อมูลเก่ากว่าlogicalcutoffเพิ่ม |
| Proof/invalidation | ใช้committed change journalแทนfullhashทุกGET; relevantwriteทำให้generationใช้ต่อไม่ได้ แม้เปลี่ยนแล้วคืนค่าเดิมก่อนGET | ABAที่contentกลับเหมือนเดิมอาจได้409; contentdigestยังคำนวณจริงตอนbuild แต่journal proofเข้มกว่าcontent equality |
| Resource miss | generation/checkpoint/journalถูกGCหรือพิสูจน์ไม่ได้: continuation409/หน้าแรก503 ไม่มีpartial/fallback | token6hเป็นอายุสูงสุด ไม่รับรองretentionเมื่อstoragepressure; ต้องทิ้งหน้าเก่าตามเดิม |
| Background work | เพิ่มindicator-builder role/process และmetadata/checkpoint tables ตามADR-002 | เพิ่มruntime writerสำหรับpublicderived dataเท่านั้น; APIยังอ่านอย่างเดียวและไม่อ่านsecret |

600sและ6h15mเป็น **เกณฑ์ที่เจ้าของอนุมัติ** สำหรับpreparedindicators ไม่ใช่กฎการเทรด
ถ้าต้องการหน้าแรกสดเท่าDB timeทุกครั้ง หรือcold missต้อง200ภายใน30sเสมอ
ข้อเสนอนี้ไม่ตอบสัญญานั้นและห้ามimplementโดยเลือกค่าใหม่เอง
ผลยังUNCONFIRMEDตามต้นทางและไม่รับรองความพร้อมใช้ส่งออเดอร์

## RQ amendments ที่อนุมัติ

- F-11 RQ-4/5/14: generationระบุid, formula, source/pair/timeframe, L/U/as_of,
  contentdigestและsource epoch/fence; ทุกpageยึดชุดนั้นและshared seedเดิม
  journal proofที่ขาดหรือพบrelevantwriteต้องปฏิเสธ แม้actualcontentอาจกลับค่าเดิม
- RQ-3/9/NC-30/31/33: ใช้F-09 OHLCV/coreเดียวกัน สูตร, rounding, units,
  finality, gap, refreshและMoney/Quantity invariantsไม่เปลี่ยน
- RQ-11/12: APIGETไม่มีwrite/refresh/enqueue/sessionrenewal; builderอ่านข้อมูล
  ตลาดและเขียนเฉพาะmetadata/checkpointที่scopeใหม่นี้อนุมัติ
- RQ-15: output1,000/input365วันต่อชุด/buffer1,000/CPUslice16เหมือนเดิม
  APIคำนวณไม่เกิน1,999ช่องจากcheckpoint แต่inputที่workerใช้สร้างชุดยังเต็ม365วัน
  ไม่ใช้การลดlookbackเปลี่ยนค่าindicator
- F-09 RQ-8/14 และplan/validationretention: แยกlogicalcutoffที่GET/POST/ingest
  ใช้กับphysicaldeletecutoffที่ช้ากว่า6h15m; คำนวณจากDB UTC timeเดิม
  sourceepoch/journalเป็นmetadataใหม่ที่ต้องครอบทุกcandlewrite/cleanup

## Generation กับcheckpoint

1. Builderเลือกseriesจากcatalogเดิมและเริ่ม REPEATABLE READ, READ ONLY
   ตั้งisolationก่อนSELECTแรก อ่านDB as_ofหนึ่งครั้งและsource(epoch,fence)ในsnapshotนี้
   L=align_ceil(as_of−365วัน), U=align_floor(as_of) เช่นเดิม ไม่เลือกseedตามผู้ใช้
2. สแกน[ L,U )ด้วยreader/core batchเดียวกับNC-34; hashทุกslotด้วยcanonical bytes
   เดิม คำนวณทุกstepและnumericerrorsเดิม ไม่ข้ามerrorนอกหน้าที่จะส่ง
3. เก็บinitialstateก่อนL และstateหลังทุก1,000ช่อง รวมท้ายpartialbatch
   checkpoint.next_open_atหมายถึงslotถัดไปที่ยังไม่ได้feed; ห้ามfeedslotสุดท้ายซ้ำ
   full1mเก็บไม่เกิน527checkpoints ไม่เก็บผลตัวเลขทุก525,600ช่อง
4. checkpointเก็บnumeric Money/Scalar state, bounded seed buffers, previousclose,
   lastopen, seed_open, accumulated finality, blockedและrefresh_dependency
   ทั้งหมดผูกgeneration/series/formula/checkpointversion ไม่มีstateจากHTTP
5. strictcodec serializeMoney/Scalarเป็นcanonical stringsและหน่วย ใช้ตัวตรวจ
   เดิมเมื่อdecode; payloadต่อcheckpoint<=16KiB ไม่มีDecimal/coefficientsดิบในJSON
   stateที่ผิดshape/order/unit/boundsต้อง503 ไม่fallbackคำนวณเต็มในAPI
   warm buffersใช้amountstringsกับquoteunitร่วมของarrayที่ตรวจจากMoneyทุกตัว
   เพื่อลดการซ้ำหน่วย; restoreสร้างMoneyด้วยหน่วยนั้นและตรวจทุกค่า ไม่เก็บcoefficients
6. เขียนstagingcheckpointsผ่านwriterconnectionแยก ขณะsourceconnectionยังถือ
   snapshotเดิม; tagทุกแถวด้วยgenerationid/claim token ไม่ปนsnapshots
   ไม่เปิดREAD ONLY transactionแล้วแทรกwriteเข้าไป
7. เมื่อdigest/count/stateครบ ปิดsource transaction แล้วpublishในshorttransaction
   ภายใต้sourceguard ตรวจjournal coverage/epoch/relevantwritesหลังfenceอีกครั้ง
   ไม่ผ่านให้discard STAGING; ผ่านจึงREADYและสลับheadแบบatomic
   APIเห็นเฉพาะREADYผ่านview ไม่อ่านSTAGINGแม้บางcheckpointcommitแล้ว

## Flow API และหน้าแรก/cold miss

- Auth/schema/admissionเดิมก่อนเปิดAPI-role READ ONLY snapshot
- หน้าแรกตรวจnumeric failure manifestตามหัวข้อerror/retryด้านล่างก่อนเลือกhead;
  ถ้าไม่มีfailureที่ใช้กับcandidateนี้ เลือกheadล่าสุดของseries/formulaในsnapshot
  ถ้าไม่มี/หมดอายุ/ageเกิน600s/journalไม่ครอบ/relevantwriteเกิดแล้ว
  ให้503 DATA_NOT_READY ไม่มีindicator rows
  ไม่ลองpreviousheadเพื่อซ่อนความไม่พร้อม และไม่สร้างdemandด้วยGET
- Defaultช่วงผลสิ้นสุดที่generation.U; explicitendที่ใหม่กว่าUให้503 ไม่clamp
  start/endผิดรูปให้422 และผลที่ขอออกนอกlogicalretentionปัจจุบันให้422เดิม
  inputseedอาจเก่ากว่าlogicalcutoffปัจจุบันแต่ยังอยู่ใน365วันของgeneration.as_of
- ตรวจepoch/floorแล้วค้นjournal `revision>fence AND identity=series AND
  L<=open_at<U` รวมglobalreset events; ไม่พบจึงถือว่าชุดเดิมยังตรวจได้
- หาcheckpointที่next_open_at<=page_startใกล้ที่สุด; restorecontroller/numeric
  state แล้วอ่านsourceไม่เกิน999ช่องก่อนpage+1,000output รวม1,999ช่อง
  fetch/decode/core slicesและerrorbudgetsเดิม; gaps/warm-upยังนับoutputslots
- ทุกmetadata/checkpoint/source rows/journalอยู่ในAPI snapshotเดียวกัน
  writercommitหลังsnapshotยังคืนหน้าเก่าที่consistentได้; requestถัดไปตรวจพบ
- ก่อนคืนresponseตรวจDB time/session/token/generationexpiryอีกครั้ง แล้วcommit
  จึงส่งbody ไม่มีpartial response; ไม่มีserverretryDB/409/503อัตโนมัติ
- responseเพิ่มgeneration_id/prepared_at/generation_age_seconds; as_of/L/U/digest/
  seed/finalityยังระบุชัด ค่าageเป็นเวลา ไม่ใช่การคำนวณการเงิน
  generation_ageไม่ใช่อายุราคาล่าสุดหรือการรับรองsourcecoverage; missing/refresh/
  finalityยังรายงานแยก และไม่มีการตีความpreparedREADYว่าmarketdataครบหรือพร้อมเทรด
- continuationไม่ใช้600s freshness gateเพื่อเปลี่ยนชุดกลางทาง แต่ต้องยังไม่หมด
  token/generationexpiryและผ่านjournal proof; mutation/GCทำให้409และทิ้งหน้าสะสม
- F-09POSTrefresh/pollยังเป็นflowเดิม; refreshcommitอาจทำให้generationใช้ไม่ได้
  callerอ่านชุดใหม่เมื่อมีheadREADY ไม่ตีความCOMPLETEว่าpreparedindicatorพร้อม
  UI/bot policyการpollรอprepared dataต้องอนุมัติในงานผู้ใช้ผล; F-11ไม่เพิ่มUI/บอท

## Source epoch/journal และrace safety

รายละเอียดด้านrole/guard/triggerอยู่ใน [ADR-002](../../decisions/002-prepared-indicators.md)
ไม่ใช้sequenceเลขมากสุดแทนcommit-order proof เพราะtransactionที่ได้เลขก่อน
อาจcommitทีหลัง sourcecounterจึงเป็นrowที่sourcewrite scopeล็อกไว้จนcommit
ต้องacquire scopeก่อนF-09caller lock_claimและcandles SELECT FOR UPDATE
statementtriggerตรวจscopeแล้วadvance revision; after-row journal/counter/candlewrite
อยู่transactionเดียวกัน ลำดับrelation/guard/row locksและmaintenanceอยู่ในADR-002
builderpublish/GCใช้guardเดียวกันก่อนตรวจแล้วสลับhead จึงไม่มีช่องwriteระหว่างproofกับpublish

- INSERT/backfillและDELETEต้องlogslot; UPDATElogเฉพาะfieldsของcanonical digest
  ถ้าidentity/open_atย้ายต้องlogทั้งold/new identity; ไม่logqueue/last_checkedอย่างเดียว
- คำสั่งที่ไม่เปลี่ยนrow/duplicate noopมีcountergapได้แต่ไม่มีrelevantjournal
  rollbackไม่เปลี่ยนcounter/entriesที่committed; relevant ABAยังinvalidates
- appendopen_at>=Uไม่invalidateชุดเก่า ต้องทดสอบแม้อยู่UTCdayเดียวกับslotสุดท้าย
- Root/leaf partitionsและfuturepartitionsต้องติดguard/journalครบ; rootupsert,
  ON CONFLICT UPDATE, partitionmove และdirectleafDMLต้องมีactual-PGtests
- TRUNCATE/epochresetคือglobalinvalidation; DDLdrop/detach/rebuildpartitionsเป็น
  maintenanceที่ล็อกsource root/partitionsแบบACCESS EXCLUSIVEก่อนguard แล้วจึง
  expireheads/resetepoch/DDL ไม่ถือguardก่อนขอrelationlock ไม่ทำsilentDDLข้ามproof
- journalGCขยับwatermarkอย่างatomic; fence<watermarkหรือepochต่างคือproofขาด
  ให้409/503 ห้ามถือว่าไม่มีentriesแปลว่าไม่เคยเปลี่ยน
  ภายใต้budgetpressureอาจexpiredependentgenerationsก่อนครบ6h10mพร้อมขยับfloor;
  ไม่ปฏิเสธF-09sourcewriteเพียงเพื่อรักษาcache และไม่อ้างtoken6hรับรองการอ่านครบเสมอ

## Retention ที่เสนอและเหตุผล

- Physicalgrace6h15mรองรับgeneration.as_ofที่อาจเก่ากว่าหน้าแรก600s และtoken6h
  รวมmargin300s; ป้องกันcleanupลบต้นseedทันทีระหว่างbuildหรือpagination
- generation.expires_at = as_of + 600s + 6h (6h10m) ไม่ต่ออายุเมื่ออ่านpage
  tokenexpires=min(issued_at+6h, session.absolute_expires_at, generation.expires_at)
  firstrequestต้องage<=600s จึงไม่ออกtokenที่อ้างgenerationเกินgraceนี้
- เคารพphysicalgraceในการDELETEเฉพาะsource; F-09GET/POST/ingestยังใช้365วัน
  และไม่fetchย้อนหลังเกินlogicalcutoff No extrapolated/ghost candleเมื่อrowหายจริง
- การลบก่อนกำหนดจากmaintenanceหรือstoragepressureยังinvalidates ไม่ใช้checkpoint
  ปิดบังข้อมูลต้นทางที่หาย ห้ามทำgraceไม่มีเพดานเพื่อรักษาtoken

## Worker, capacity, retries และงบที่เสนอ

| ส่วน | แนวทางที่อนุมัติ |
|---|---|
| Scheduler | seed/coalesce30seriesเดิม; poll10s, durablefairroundให้แต่ละseries/formulaได้ไม่เกิน1attempt/round; earliestdeadlineและpersistedround-robinเฉพาะงานที่ยังไม่ถูกserveในroundตามหัวข้อfairnessด้านล่าง; เก็บeligible_at/deadlineเดิม; ไม่มีcustomseries |
| งานbuildพร้อมกัน | 1attemptรวมทุกseries/formula/builder replica: session advisory lock (711,1) บนpinnedwriterก่อนclaim ร่วมกับsingletonslot/fenceตามADR-002; API budget1/processเดิมแยกจากworker |
| Build deadline | 120s/job รวมscan/hash/staging/publish; slice<=16/buffer<=1,000, query500ms/lock200ms, cleanup2s |
| Builder resources | Linux2vCPU/1GiB, RSS delta<=128MiB; DB pool2รวมsourceRO+stagingwriter ไม่มีoverflow |
| Lease | 150s, heartbeat20sด้วยpinnedwriterconn; ทุกwriteต้องmatchglobal slot epoch/fence/owner/backendและjobgeneration/token/lease/deadline; leaseexpiryอย่างเดียวไม่อนุญาตtakeover |
| Retry | transient/SUPERSEDEDใช้budgetร่วมไม่เกิน3attemptsรวมinitial1+retry2ต่อcycle, backoff30s/60s; หมดงบเป็นFAILED_TRANSIENTหรือFAILED_SUPERSEDEDตามเหตุสุดท้าย; numeric failureไม่มีautomatic retry |
| Derived storage | checkpoint+generation+index budget3GiB และgeneration expiryข้างต้น; STAGINGที่leaseตายcleanupเป็นbatch1,000 |
| Journal storage | เป้าหมายretain6h15m; cap2,000,000entries, GCbounded10,000/รอบพร้อมfloor; หากต้องpruneก่อนเวลาexpiredependentgenerationsก่อน ไม่ปฏิเสธsourceingestionเพราะcachebudgetเต็ม |

ทุกตัวเลขใหม่ได้รับอนุมัติเป็นเกณฑ์แล้ว ต้องวัดschedulerครบ30series/ราคาที่เปลี่ยนจริง/refresh-backfill
ยังไม่รับรองว่า120sหรือage600sทำได้ทุกseries ถ้ากำลังไม่พอAPIให้NOT_READYตามจริง
แต่ต้องนับเป็นunavailable/failureตามR2-Cด้านล่าง ไม่ใช่ทางเลือกแทนเกณฑ์ผ่าน
ไม่เพิ่มworkerจำนวนมากหรือยืดage/deadlineเอง การclaimใหม่ไม่ต่ออายุheadหรือtokenเก่า
สูญcheckpointทั้งชุดสร้างจากcandlesใหม่ได้ แต่source lossไม่สร้างข้อมูลเทียม
FAILED_TRANSIENT/FAILED_SUPERSEDEDหลังครบ3attemptsไม่ถูกschedulerปลุกด้วยclock/Uเลื่อนอย่างเดียว;
newrelevantsourceinputหรือoperatorretryเริ่มcycleใหม่ได้หลังcooldown600s
ตามprotocolด้านล่าง; FAILED_NUMERICห้ามใช้กฎretryนี้
ถ้าhistoryเปลี่ยนต่อเนื่องจนpublishproofไม่เคยผ่าน อาจไม่มีREADYheadต่อเนื่อง
ต้องรายงานavailability/time-to-readyตามจริงและกลับมาให้เจ้าของตัดสิน;
ไม่ผ่านworkloadที่กำหนดห้ามmerge/Completed แม้APIที่ใช้fixtureพร้อมแล้วเร็วพอ

### Global build concurrency — แก้reviewข้อ4 (Approved)

กลไก/lockorder/connectionlifecycleและsafehandoffอยู่ใน
[ADR-002](../../decisions/002-prepared-indicators.md) หัวข้อGlobal build slot
เป็นแหล่งเดียวของprotocol; ไม่ใช้per-seriesleaseหรือpublishguardแทนglobalสิทธิ์
scopeครอบตั้งแต่ก่อนเปิดsourcesnapshotจนscan/hash/core/staging/publishและ
cancel/join/cleanupเสร็จ; ผู้ไม่ได้slotห้ามclaim/เริ่มbuildแม้เป็นคนละseries

ใช้writerconnectionเดิมหนึ่งเส้นถือsessionlockและserializestaging/heartbeat/
publication อีกเส้นใช้sourceRO รวมpool2/nooverflowเดิม ไม่มีdedicatedconnectionที่สาม
leaseและfenceป้องกันstaleDBwrites แต่การhandoffที่ไม่ทราบว่าworkerเก่าหยุดหรือยัง
ต้องfailclosedจนoperator/supervisorยืนยันprocessหยุดและreapตามADR ไม่ขยาย
claimcapacityเป็น2เพื่อแก้workerค้าง ไม่ใช้transactionpoolerกับsessionlock
วัดR2-C1..C6ด้วยprotocolจริงทั้งclaim/heartbeat/release ไม่mockglobalbudget
Retry/operatorCLIข้อ3แค่ทำjobeligible ต้องacquireglobalslotใหม่ก่อนbuildเสมอ

### Error/retry contract — แก้reviewข้อ3 (Approved)

NC-33ที่อนุมัติแล้วยังคงเดิม: typed numeric failureยุติทั้งหน้าและคืน
`422 / INDICATOR_NUMERIC_ERROR` ไม่มีpartial success/ค่าเก่ามาแทน/input/secret/
stack trace; input/รุ่นเดิมต้องได้errorเดิมและไม่มีautomatic computation retry
การย้ายการคำนวณไปbuilderไม่เปลี่ยนnumeric failureให้กลายเป็นcold miss503

| Failure | Worker transition | APIเมื่อไม่มีcandidateที่ใช้ได้ |
|---|---|---|
| Typed domain numeric failureจากcoreเดิม เช่น overflow/unit error | RUNNING→FAILED_NUMERICทันที; ไม่มีretry/backoff; discardทุกSTAGING checkpoint | 422 INDICATOR_NUMERIC_ERROR เมื่อfailed candidateยังพิสูจน์ได้ตามscopeด้านล่าง; ไม่มีRetry-After |
| Transient infrastructure เช่น connection loss, lock/query timeout, deadlock, heartbeat failure | retryจากsnapshotใหม่ ไม่reuseabortedtransaction/state; รวมไม่เกิน3attempts แล้วFAILED_TRANSIENT | 503 DATA_NOT_READY/Retry-After:10 ตามreadiness flow; ไม่คืนnumeric422จากexceptionประเภทนี้ |
| Source proofเปลี่ยน/leaseเสียระหว่างbuildหรือpublish | generationเป็นSUPERSEDED; jobretryใช้budgetร่วม3attempts/backoff30/60 แล้วFAILED_SUPERSEDED; reason=SOURCE_CHANGED/OWNERSHIP_LOST; coalesceไม่resetbudget/deadlineและholderเก่าห้ามpublish | หน้าแรก503; continuation409เมื่อproof/รุ่นเดิมใช้ไม่ได้ |
| Checkpointcodecเสีย, permissions/configurationผิด หรือunexpected exception | FAILED_OPERATIONAL; failclosedและแจ้งoperatorด้วยfixedcategory ไม่blind-retry | 503ตามunavailable contractเดิม; ไม่แปลงเป็นtyped numeric failure |

งบ120sต่อattempt, backoff/queueและattemptใหม่ทั้งหมดต้องนับในcapacitydeadline
เดิม; timeoutไม่ให้สิทธิ์ขยายdeadlineหรือเปลี่ยนstatusเป็นnumeric error
ตัวเลข3attemptsหมายถึงinitial1+retry2อย่างชัดเจน ไม่ใช่initial1+retry3
transientกับsupersessionสลับกันก็รวม3 ไม่ได้โควตาชนิดละ3; counterเพิ่มตอนclaim
commitแล้วเท่านั้น ไม่มีattempt chargeเมื่อcontenderไม่ได้globalslot

**Failure manifestและread-only API:**
- FAILED_NUMERICเก็บgenerationid/series/formula/codecversion/L/U/as_of,
  sourceepoch/fence, fixedfailure_codeและfailed_at; digestเป็นNULLเมื่อscanไม่ครบ
  ห้ามสร้างdigest/countที่อ้างว่าfullscanสำเร็จ ไม่มีcheckpointที่APIอ่านได้
- บันทึกfailureและผูกjobกับfailed candidateอย่างatomicผ่านshorttransaction
  ที่ตรวจlease/tokenและsourceproofภายใต้guardเหมือนpublishREADY โดยไม่querycandles
  ถ้าinputเปลี่ยน/proofขาด/claimตายให้SUPERSEDED ไม่เผยfailureของsnapshotเก่า
- APIอ่านเฉพาะsanitizedfailureview ไม่มีexceptionmessage/inputvalues/traceback
  ตรวจseries/formula/bounds, epoch/floor/relevantwritesและjob candidateในsnapshot
  เดียวกับreadyhead/source; proofขาดหรือinputเปลี่ยนให้503และรอbuild ไม่เดา422
- Numeric manifestมีผลเฉพาะfailed candidateที่jobยังอ้างถึง และไม่มีcandidateใหม่กว่า
  publishREADYแล้ว; ถ้าfailed candidateใหม่กว่าheadเดิม ห้ามfallbackheadนั้นเพื่อซ่อน422
  candidate orderใช้job generation sequenceที่เพิ่มตอนclaim ไม่ใช้เวลาfailed_at
  ที่อาจcommitสลับลำดับ; lateholderเปลี่ยนcandidateไม่ได้
- Failed candidateต้องตรงกับdesired calculation keyของschedulerด้วย เมื่อbounds/
  inputversionเปลี่ยนและมีdesired candidateใหม่แล้ว manifestเก่าไม่ใช้แทนerror
  ของชุดใหม่ ระหว่างรอbuildให้503 DATA_NOT_READY ไม่มีold422/oldheadfallback
  ความผิดพลาดของชุดเดิมยังเป็น422เมื่อพิสูจน์และอ้างชุดเดิมตามscopeได้
- Defaultrequestใช้boundsของfailed candidate; explicitrangeต้องผ่านschema/logical
  retentionเดิมและอยู่ในcandidate.Uก่อนส่ง422; explicitendใหม่กว่าUยัง503
  errorนอกoutputpageแต่ในinput[ L,U )ยัง422ทั้งหน้า เหมือนfullscanเดิม
- Manifestไม่ใช้600s freshnessเพื่อลบnumeric errorแล้วคืน503แทน; proofและexpiry
  ของgenerationยังต้องตรวจ เก็บmanifestจนgenerationexpiry/GCตามbudgetเดิม
  หลังproof/manifestถูกGCให้503เพราะพิสูจน์ไม่ได้ ไม่สร้างnumericผลใหม่เอง
- Continuationตรวจtokenและรุ่นที่tokenระบุก่อน: mutation/expiry/GCยัง409
  failureของcandidateอื่นไม่เปลี่ยนvalidcontinuationเป็น422; หากrestore/feed
  ของREADYรุ่นนั้นเกิดtyped numeric failureจริงให้422ทั้งหน้าโดยไม่retry
  malformedcheckpointเป็น503 ไม่จัดเป็นdomainnumeric failure

**การปลุกงานหลังFAILEDและoperator interface:**
- FAILED_NUMERICห้ามretry calculation key/inputversionเดิมด้วยtimer/restart/
  backoff/operatorretry; การตรวจเวลาไม่ได้เป็นเหตุให้คำนวณซ้ำถ้าkeyยังเดิม
  schedulerสร้างชุดใหม่ได้เมื่อalignedL/Uเปลี่ยนตามDBtime, journalยืนยัน
  relevantinputเปลี่ยน หรือมีformula revisionที่ได้รับอนุมัติ ตามกฎด้านล่าง
- FAILED_TRANSIENT/FAILED_SUPERSEDEDเริ่มcycleใหม่ได้เมื่อมีrelevantinput event
  หลังfailed_at (coalesceไว้จนcooldownครบได้) หรือoperatorแก้
  infrastructureแล้วสั่งCLI `indicator-builder retry --job-id <uuid> --request-id <uuid>`
  หลังcooldown600sจากfailed_at; ไม่มีpublicHTTP retry endpoint/GETenqueue
  การกลับมาhealthyหรือprocessrestartเพียงอย่างเดียวไม่resetattempt counter
- CLIใช้buildercredentialและtypedrestrictedDB function ไม่rawSQLresetstatus:
  ล็อกjob, ตรวจFAILED_TRANSIENT/FAILED_SUPERSEDED/FAILED_OPERATIONALและcooldown, บันทึกrequestid
  แบบuniqueและtransitionเป็นQUEUEDในtransactionเดียว; RUNNING/READYหรือnumeric
  inputเดิมต้องreject คำขอซ้ำidเดิมคืนผลเดิมไม่สร้างcycleเพิ่ม; คืนเฉพาะfixedstatus
  การแก้operational faultต้องเสร็จก่อนmanualretry ไม่เปลี่ยนnumeric contract
- Cycleใหม่ล้างattempt counterเฉพาะtransitionที่อนุญาต; ไม่ต่ออายุhead/token
  และไม่reseteligible_at/deadlineของช่วงunavailableที่ยังไม่เคยrecoverเป็นREADY
  ครบ3attemptsยังFAILEDจนมีtriggerข้างต้น ไม่วนอัตโนมัติทุก600s
- Retry-After:10ของ503เป็นคำแนะนำเวลารอreadiness ไม่ใช่คำสั่งให้API/builder
  retrynumericหรือออกF-09refresh/venue request; consumerpollpolicyยังอยู่นอกF-11

**Supersession budgetและfair scheduling — แก้reviewซ้ำข้อ2 (Approved):**
- แยกfirst_eligible_at/availability_deadlineสำหรับรายงานepisode ออกจาก
  retry_not_beforeสำหรับdispatch; elapsed600sไม่ย้ายdeadline/firsteligible
  บันทึกdeadline_missed_atและนับunavailableต่อ แม้งานนั้นต้องถูกพักจากqueue
- Buildcycleมีattempts_usedรวมinitial/transient/supersededสูงสุด3; ทุกclaim
  consume1แบบatomicพร้อมglobaltoken/generation Window/sourceversion/coalesce
  เปลี่ยนระหว่างcycleไม่ล้างcounter ไม่ใช้generationใหม่ปลอมเป็นcycleใหม่
  numericfailureหยุดทันทีตามkeyเดิม; pendingnumericwindowใหม่ยังต้องผ่าน
  fairroundและห้ามข้ามFAILED_SUPERSEDED/cooldownที่ค้างอยู่
- เมื่อattempt1/2ถูกSUPERSEDED: cancel/joinCPU, closesourceและreleaseglobalslot
  ตามADRก่อนรอbackoff30/60s; เก็บpendinglatest<=1 แล้วjobเป็นQUEUEDโดยมี
  retry_not_before งานนี้ไม่ได้สิทธิ์claimซ้ำในfairroundเดิมแม้deadlineเก่าที่สุด
- ครบ3โดยเหตุสุดท้ายเป็นsupersession: jobเป็นFAILED_SUPERSEDEDและพักdispatch
  ไม่วนclaimทุกpoll/ไม่เริ่มcycleใหม่จากclock/Uเลื่อนหรือpendinginputที่มีอยู่
  ก่อนfailed_at; cooldown600sและtriggerหลังfailed_at/manualCLIตามกฎข้างต้น
  เหตุOWNERSHIP_LOSTต้องstop/reapตามADRก่อนbuildใหม่ ไม่ให้CLI/queueล้างowner
- Schedulerใช้dispatch_roundที่persistในsingletonslot และlast_served_round
  ในjob เลือกเฉพาะQUEUED/dueตามretry_not_beforeและยังไม่servedในroundนี้
  ภายในชุดนั้นเรียงavailability_deadlineแล้วpersistedcataloground-robin
  เมื่อไม่มีunservedeligiblejobจึงเพิ่มround และเลือกใหม่; ถ้าไม่มีduejobเลย
  ไม่เพิ่มroundวนเอง ให้unlockและรอpoll ไม่ถือglobalslotระหว่างพัก
- ทำadvance-round/เลือกjob/marklast_served/เพิ่มattemptcounterพร้อมclaimใน
  transactionเดียวตามcontrol→slot→job; หลังclaimrollbackไม่มีservedmarker
  claimcommitที่processล่มยังนับว่าserved/consumeattempt Reapไม่คืนสิทธิ์round
  ทุกreplicaอ่านstateเดียวกัน ไม่ใช้per-processround/RAMsemaphoreแทน
- ต่อseries/formulaมีได้ไม่เกิน1claimในroundแม้desiredkey/formula inputversion
  เปลี่ยนระหว่างRUNNING; coalesce/newwindow/manualretryไม่ล้างlast_served_round
  jobที่dueเพิ่มระหว่างroundเข้าร่วมได้เมื่อยังไม่served; การretryของAต้องรอ
  unservedeligibleBก่อน แม้deadlineAผ่านไปแล้วและdeadlineBใหม่กว่า
- countercycleล้างเมื่อREADYpublishสำเร็จหรือterminalrecoverytriggerที่อนุญาต
  เท่านั้น แยกจากlast_served_roundที่ไม่ล้างด้วยrecovery; pause/deadline-miss
  ไม่ทำให้head/tokenต่ออายุหรือทำavailabilityดีขึ้นในรายงาน
- เมื่อsourceของAเปลี่ยนต่อเนื่อง Aอาจไม่READY แต่ต้องไม่อดสิทธิ์seriesที่ข้อมูล
  นิ่ง; fairroundไม่รับรองว่า30×120sพอดี600s ต้องผ่านcapacityจริงเหมือนเดิม
  เก็บtraceattempt/round/pause/recoveryทุกseries ไม่ผ่อนC1..C6เพราะเพิ่มfairness

**Numeric recoveryเมื่อbounds/seedเปลี่ยน — แก้reviewซ้ำข้อ1 (Approved):**
- Calculation keyคือseries/formula/L/U โดยL/Uมาจากaligned365-daywindowเดิม
  ไม่รับseed/lookbackจากcaller; inputversionอ้างsourceepochและrelevantjournal
  ของwindowนั้น Globalfenceที่เพิ่มจากseriesอื่น/metadata-onlywriteไม่ถือเป็น
  inputversionใหม่ และas_ofที่เปลี่ยนแต่alignedL/Uเท่าเดิมไม่สร้างชุดใหม่
- Schedulerpoll10sยังตรวจdesiredL/Uแม้jobเป็นFAILED_NUMERIC เมื่อLหรือUเปลี่ยน
  เป็นการสร้างcandidateสำหรับชุดใหม่ ไม่resetFAILED_NUMERICของชุดเดิม
  Lเลื่อนอาจเปลี่ยนseedหรือทำให้แท่งที่errorอยู่นอกinputได้ ต้องคำนวณใหม่จาก
  initialstateของLใหม่ ห้ามrestorefailedstate/ใช้manifestเก่าทำนายว่าชุดใหม่ยังerror
- AppendนอกUเดิมไม่เปลี่ยนinputversionของkeyเดิม แต่เมื่อwindowใหม่ขยายU
  ให้ครอบslotนั้นก็เป็นkeyใหม่ที่สร้างได้; appendอย่างเดียวขณะที่L/Uเดิม
  หรือclockขยับไม่ถึงalignment boundaryไม่ปลุกชุดเดิม
- ก่อนclaimบันทึกdesired keyและเปรียบเทียบกับfailed key/inputversionอย่าง
  atomicภายใต้job/globalclaimprotocol; เก็บsuppression identityในjobหลังmanifest
  expiry/GCด้วย การลบcache/restart/claimtokenใหม่ไม่ให้สิทธิ์retrynumericชุดเดิม
  proofขาดเพียงอย่างเดียวไม่ใช่หลักฐานว่าinputเปลี่ยนและไม่ล้างsuppression
- ต่อseriesมีdesired candidateที่รอไม่เกิน1; poll/coalesceเก็บwindowล่าสุด
  ไม่enqueueทุกwindowที่ผ่านระหว่างworkerไม่พร้อม Duplicatepoll/2replicas
  ต้องไม่สร้างinitialcomputeซ้ำสำหรับkey/inputversionที่FAILED_NUMERICแล้ว
  ไม่ใช้as_of/fence/tokenใหม่ปลอมเป็นinputใหม่
- ชุดใหม่ใช้globalbuild1, pool2, scan/hash/staging/publish120sต่อattemptและ
  deadline/time-to-readyเดิม; numericfailureยุติทันที ไม่มีnumericretryภายในชุด
  ถ้าเป็นtransientfailureยังใช้รวม3attempts/backoff30/60ตามเดิม ไม่resetcounter
  เพียงเพราะpoll/coalesceas_ofใหม่ Windowที่เปลี่ยนระหว่างRUNNINGแค่coalesce
  desiredชุดถัดไป ไม่เปิดcomputeซ้อน และsupersessionยังใช้protocolเดิม
- เก็บfirsteligible/deadlineของunavailableepisodeเดิมจนREADYจริง ไม่resetเพื่อ
  ซ่อนเวลาที่รอชุดใหม่; successใหม่ไม่ต่อexpiryหรือเปลี่ยนfailuremanifestเดิม
  กฎนี้ไม่เพิ่มสูตร/ไม่clampoverflow และไม่ทำHTTPGETenqueue/refresh/venuecall

### Capacity acceptance — แก้reviewข้อ2 (Approved)

เกณฑ์ขั้นต่ำที่อนุมัติคือ bootstrap/recoveryทั้ง30seriesภายใน600s,
steady-stateปกติพร้อม100% และphaseที่invalidateพร้อมกันพร้อมไม่น้อยกว่า80%
ต่อseries ทั้งหมดเป็นacceptanceของworkloadด้านล่าง ไม่ใช่คำรับรองSLAทุกเหตุการณ์
ต้องผ่านทุกseries ไม่เฉลี่ยผลคู่/TFที่เร็วกว่าเพื่อซ่อนseriesที่starve

Schedulerกำหนดdeadlineจากเวลาที่เริ่มepisodeจริง:
- headขาด/dirty: first_eligible_at+600s; retainค่าเดิมข้ามpoll/coalesce/retry
- headvalidที่ต้องrefresh: head.as_of+600s; eligibleก่อนdeadlineอย่างน้อย
  build budget120s+poll10s จึงเริ่มเข้าคิวที่head.as_of+470s
- deadlineเท่ากันใช้persistedround-robin cursorของcatalog30series;
  jobdirtyใหม่ห้ามresetdeadlineหรือแซงjobที่รอนานกว่าด้วยpriorityคงที่
  deadlineorderingใช้เฉพาะunservedeligiblejobsในdurablefairround ไม่ใช้deadline
  ที่ผ่านไปแล้วให้retryjobยึดslotซ้ำก่อนseriesอื่น; backoff/FAILEDไม่ใช่งานdue
- การนับ120s/jobเริ่มเมื่อclaim; time-to-ready600sรวมqueue/attempt/backoff/publish
  ไม่มีการต่ออายุdeadlineเมื่อclaimใหม่หรือเลือกas_ofใหม่

Fixturesทุกphaseใช้5คู่×6TFจริงและinputเต็ม365วันทุกseries, ราคามีเศษ/เปลี่ยนทิศ
พร้อมfetchproofที่เข้าเกณฑ์; testปกติไม่เรียกexchangeและไม่ส่งออเดอร์
DB/Redis/workerและsourcecollectorอยู่ในสภาพhealthyของphaseที่วัด ไม่ใช้manualREADY
หรือstubpublisherแทนworkerจริง; ใช้globalbuild1/API1processกับงบเดิมทั้งหมด

| เกณฑ์ | วิธีวัดและเงื่อนไขผ่าน |
|---|---|
| R2-C1 Bootstrap | เริ่มจากderived tablesว่างโดยsourcefixturesพร้อม; T0คือbuilder/schedulerhealthyและรับงานได้ ไม่มีprewarmที่ไม่นับเวลา; ทุก30seriesต้องมีvalidREADYและprobeGET200ภายในT0+600s โดยage<=600s แต่ละbuild<=120s; ช่วงก่อนพร้อม503เป็นcoldmissที่บันทึกได้ แต่seriesใดเกิน600sคือล้ม |
| R2-C2 Steady-state | หลังC1ผ่าน วัด60นาทีจริง; sourceappendเฉพาะแท่งใหม่เมื่อจบตามTF ไม่แก้historyในgenerationเก่า; valid/freshREADYและacceptedGET200ต้อง100%ต่อseries ไม่มีSTALE/NOT_READY gap; ตรวจการrefreshheadหลายรอบ ไม่ใช้fixtureheadค้างตลอดphase |
| R2-C3 Dirty/recovery | เริ่มทั้ง30พร้อมแล้วinvalidate30seriesพร้อมกันด้วยcommittedhistoricalOHLC updatesที่อยู่ในboundsของแต่ละhead; หลังburstมีเพียงappendแบบC2 วัด60นาที; ทั้ง30ต้องกลับvalidREADY/GET200ภายใน600sนับจากcommitburst และavailability>=80%ต่อseriesตลอดphase; หลังrecoverต้องพร้อม100%จนจบphaseภายใต้append-only workload |
| R2-C4 Fairness | รายงานต่อseries: firsteligible, queuewait, claim/build/retry/publish times, dispatchround/served/pause/deadline-miss, maxheadageและmaxunavailable interval; bootstrap/recoveryไม่มีseriesstarveเกิน600s; ผ่านR2-S1..S5และdeadlineไม่ถูกpoll/retryreset |
| R2-C5 Under load | ทำC2และC3ซ้ำพร้อมrejected-request loadตามadmissionเดิม; acceptedprobesยังผ่านเกณฑ์ของphase, resource/readinesstimeoutsนับเป็นfailure; rejectedloadที่ตั้งใจแยกจากavailabilitydenominatorและยังต้องถูกปฏิเสธก่อนcandlequery |
| R2-C6 Gate | ต้องผ่านC1..C5และR2-7/120sworker/resource/parityทั้งหมด; มี30rowsของผลรายseriesทุกphase ไม่มีmissing/skippedseries; ขั้นfinal validationต้องล้มเมื่อseriesใดไม่ผ่านและห้ามเปิดpreparedmode/merge/Completed |

Sampling/denominator:
- ตรวจvalid/freshheadผ่านAPI-role READ ONLY observerทุก10sครบ30series โดยใช้
  epoch/floor/rangeproofแบบAPIจริง ไม่ตรวจREADYflagอย่างเดียว
- เรียกGETจริงครบ30seriesทุก60sแบบไม่overlap ใช้5authenticatedtestusers
  คนละ6seriesเพื่ออยู่ใน6/user/30global fixedwindowเดิม; ทุกroundต้องจบภายใน60s
  ไม่skipprobeที่ช้าหรือresponse503/429/timeoutเพื่อลดdenominator
  จัดroundตามRedis TIME windowและคงtestsessionให้validด้วยlogin flowจริงตาม
  authpolicyในtest harnessเมื่อจำเป็น; ไม่ต่ออายุด้วยindicatorGET ไม่แก้sessionDB
  หรือdisableauth/rate limits ถ้าharnessรักษาsession/ตารางprobeไม่ได้phaseไม่ผ่าน
- rejectedloadของC5ต้องไม่แย่งquotaที่กำหนดให้acceptedprobes: ทดสอบBUSYด้วย
  barrierหลังprobeถือlocal slotแล้ว และทดสอบrate-deniedหลังacceptedroundใช้30
  attemptsของwindowนั้นครบ; ตรวจว่าrejectก่อนcandlequeryและไม่bypassbudgetให้probe
  อย่าส่งbackgroundloadแบบไม่กำหนดแล้วตัด429ของprobeออกจากผล
- probeใช้defaultrequestedrangeที่อยู่ในpreparedboundsตามสัญญาและตรวจbody/
  seed/status/digest/age ไม่ใช้แค่HTTP200; ค่าไม่มีผลที่คาดต้องตรวจจากfixture
- validhead availability = valid/freshobserver samples / samplesที่กำหนดทั้งหมด;
  API availability = correct200responses / acceptedprobesที่กำหนดทั้งหมด
  ต้องผ่านทั้งสองตัวต่อseries; healthy-phase 503/429/BUSY/timeoutไม่ถูกตัดทิ้ง
- bootstrap/dirtyช่วงก่อนrecoverที่กำหนด600sยังอยู่ในรายงานและdenominatorของ
  episode ไม่ขยับT0จนกว่าผลพร้อม; C3ใช้80%กับทั้ง60นาทีรวมrecoverywindow
- outage/continuoushistoricalwritesนอกworkloadนี้ใช้R2-10failclosedtestsแยก;
  ห้ามใช้เหตุว่าsourceเปลี่ยนเพื่อยกเว้นfailureของworkloadC2/C3ที่ตกลงแล้ว

ถ้าไม่ผ่านให้เก็บtrace/profileของseriesที่ติดคิวหรือrebuildไม่ทัน และกลับมาเสนอ
capacity/architecture/requirementsใหม่ก่อนเปลี่ยนจำนวนworker, freshness,
deadlines, workloadหรือthreshold ไม่ลดเกณฑ์ตามผลที่ล้ม

## Migration/grants/rollback

ตามADR-002 เพิ่มsourceguard/journal, generations, checkpoints, heads, buildjobs
กับruntime roleเฉพาะbuilder; ไม่มีuser_id/email/key/order/balance columns
Moneystateอยู่ในcanonicalstring JSONBพร้อมsize/shape validation ไม่เก็บfloat
runtimeไม่มีDDL/owner/superuser/bypassRLS; APIได้SELECTreadyviews/journalproof,
sanitizedfailureviewและrolloutcontrolตามADR-002เท่านั้น
ไม่มีINSERT/UPDATEmetadataจากGETหรือroleAPIในการปรับนี้

ใช้ลำดับexpand/compatibility/drain/activate/rollbackที่ระบุด้านล่าง ห้ามติดstrict
sourceguardtriggerก่อนF-09รุ่นเก่าหยุดทุกตัว หรือออกformat2ก่อนAPIทุกตัวอ่านได้
rolegrant/bootstraprollbackทำด้วยผู้มีสิทธิ์cluster; F-09candles/jobsไม่ลบ
ไม่มีpublicrequest fallbackfullscanที่เคยไม่ผ่าน; modeเก่าใช้diagnosticได้แต่
ไม่ถือว่าrollbackทำให้V-15ผ่านหรืออนุญาตเปิดF-11ให้บริการแบบเดิมโดยอัตโนมัติ

### Rollout ข้ามreplicasต่างเวอร์ชัน — แก้reviewข้อ5 (Approved)

รุ่น **legacy** คือAPIที่อ่าน/ออกv1อย่างเดียวและF-09ที่cleanup365วัน
รุ่น **compatibility** และรุ่นpreparedต้องอ่านv1/v2ด้วยschema/HMACdomainที่ถูกต้อง
ร่วมกัน และF-09ต้องรองรับsourcewrite scope/physicalgraceก่อนเปิดproof
ทั้งสองรุ่นใช้DBrolloutcontrolชุดเดียวตามADR-002 ไม่เปิดด้วยenvflagแต่ละreplica

| Stage | API/cursor | F-09/source และbuilder | Gateก่อนขั้นถัดไป |
|---|---|---|---|
| S0 Expand | control=LEGACY; ไม่มีformat2ออกจากreplicaใด | additive tables/views/functions/grantsเท่านั้น ยังไม่ติดstrictjournal/scope trigger ไม่เปิดbuilder | legacyAPI/F-09ยังทำงานกับexpandedschemaได้จริง |
| S1 Compatibility rollout | legacyและcompatibilityผสมกันได้เฉพาะLEGACY; ทุกตัวออกv1เท่านั้น compatibilityตรวจv1ด้วยdomainเดิม | upgradeF-09ให้acquire scopeก่อนpre-lockและcleanup365วัน+6h15m; ระหว่างยังมีoldcleanupห้ามbuildgeneration | image/capability inventoryครบทุกAPIและsourcewriter/cleanup process; keyringพร้อมอ่านทั้งสองformat |
| S2 Drain และproof activation | ปิดรับindicatorrequestใหม่ที่entrypointก่อนdrain; รอinflight≤30s+cleanup2s ถ้าไม่จบให้stopprocessและยืนยันsourcesnapshotปิด ไม่flipmodeขณะมีrequestเก่า | stop/drainF-09ทุกตัวรวมcleanup/startup/cron/operatorpathและsourcewrite transactions; disableoldimage restart/autoscale แล้วติดstrictscope/journal/root-leaf triggersภายใต้maintenance protocol; restartเฉพาะcompatibleF-09 | ไม่มีlegacyAPIในrouting/directaccessและไม่มีlegacyF-09process/DBtransactionเหลือ; actualroles/triggercoverage/physicalgraceผ่าน |
| S3 Prepare | control=PREPARING; compatibleAPIคืน503 DATA_NOT_READYสำหรับหน้าแรกและ409สำหรับvalidcursor ไม่มีv1/v2 issuance | compatiblebuilderทำงานได้ด้วยglobal slot; backfill30seriesและวัดcapacity/readyAPIในisolatedvalidation ไม่สร้างpubliccursorก่อนผ่าน | R2-L/F/G/C และregression/mixed-version R2-Dครบ; validfreshheadsครบ30 ไม่ใช่เพียงprocesshealth |
| S4 Activate | drainindicatorrequests/buildattemptsอีกครั้งแล้วmigratorเปลี่ยนcontrolเป็นPREPAREDพร้อมrollout_epochใหม่; ทุกcompatibleAPIอ่านmode/epochในrequestsnapshotเดียวกัน จึงเริ่มออกv2 | restart/resumebuilderตามepochใหม่และcompatibleF-09ที่graceยังมีผล | เปิดtrafficเฉพาะimageที่อ่านv2/codecปัจจุบันได้; randomrouting/replica restartไม่ทำvalidv2เป็น422 |
| S5 Compatible rolling updates | compatibility/preparedreplicasผสมได้เมื่อรองรับactiveprotocol/codecเดียวกัน; ทุกตัวใช้PREPAREDและออกv2 ไม่มีreplicaenvfallbackไปv1 | builderreplicasใช้globalkey/slotprotocolเดียวกัน; F-09ทุกตัวใช้scope/grace | เปลี่ยนcodec/protocolที่อ่านร่วมกันไม่ได้ต้องกลับเข้าdrain+upgradecompatibleก่อน ห้ามเปิดnewformatจากcanaryเพียงตัวเดียว |

Deploymentrunbookต้องบันทึกimage digest/capabilityและprocess/container inventory
ของทุกAPI/market-data/cleanup/builder รวมreplicasที่offlineแต่restartได้ ปิดrestart
ของlegacyimageก่อนactivate การhealth200ของoldbinaryไม่ใช่compatibilityproof
gateกลางDBไม่สามารถบังคับoldbinaryที่ไม่อ่านgate จึงต้องตัดrouting/directaccess
และหยุดoldprocessจริง ไม่ถือว่าheartbeatregistryที่oldversionไม่ลงทะเบียนครบแล้ว
Composeปัจจุบันไม่มีloadbalancer/rollingdeployment controller: ใช้stop/drain/start
แทนการอ้างzero-downtime; productionrouting/automationเป็นงานdeploymentที่ต้อง
กำหนดrunbookจริงก่อนนำไปใช้ ไม่เพิ่มplatformใหม่ในF-11

**Rollbackหลังเริ่มออกv2:**
1. ปิดรับindicatorrequestใหม่/drainทุกcompatibleAPI และstop/joinbuilderทุกreplica
   ตามglobalhandoff; sourcesnapshotต้องปิด ถ้าสถานะownerไม่ชัดใช้stop/reapตามADR
2. migratorเปลี่ยนcontrolเป็นPAUSEDและrollout_epochใหม่ บันทึกDBเวลา
   last_v2_issue_cutoffหลังdrain; APIcompatibleหน้าแรก503และvalidv1/v2→409
   เพื่อทิ้งหน้าสะสมก่อนอ่านgeneration ไม่มีlegacyfullscanfallback
3. rollbackapplicationได้เฉพาะcompatibilityimageที่ยังverifyv2ได้ คงkeyring,
   rolloutcontrol/views/schemaและF-09scope/physicalgraceไว้; ห้ามroutelegacyAPI
   หรือstartlegacyF-09cleanup365วันระหว่างยังมีv2ที่ไม่หมดอายุ
4. รอจนไม่มีAPI/builder/sourceROreaderค้าง และDB timeถึงcutoff+6h
   (อายุสูงสุดtokenเดิม ไม่เพิ่มอายุ/รอจากเวลาoperatorประมาณเอง) จึงdrain/stop
   sourcewritersอีกครั้งเพื่อถอนstricttriggers/derivedschemaตามmaintenance protocol
   และคืนphysicalcleanup365วันได้; ทำgrants/bootstrapdowngradeเป็นลำดับท้าย
   คงcompatibilitydecoder/controlจนสิ้นsupportwindowนี้ ไม่มีtableหายให้APIเก่าชน
5. การกลับไปเปิดlegacyF-11แบบfullscanต้องตัดสินperformance/readinessใหม่
   เพราะbaselineยังไม่ผ่านV-15; rollbackจึงไม่รับรองบริการindicator200/Completed

การเปิดกลับPREPAREDหลังrollbackต้องใช้epochใหม่และผ่านgatesเดิม Oldv2ที่MACถูก
แต่epochเก่าคง409แม้generationเดิมยังอยู่ ไม่ฟื้นcursorที่ถูกinvalidateไปแล้ว
READYที่publishเสร็จก่อนdrainยังใช้ได้หลังactivateถ้าproof/codec/freshness/expiry
ผ่านตามเดิม; build_rollout_epochเป็นประวัติ ไม่บังคับให้เท่ากับtokenepochใหม่
ห้ามresumeSTAGING/claimเก่าหรือแก้READY/ต่อexpiryเพื่อข้ามactivation gate
ช่วงmaintenance/readiness503ต้องบันทึกตามจริง ไม่ใช้เป็นข้อยกเว้นcapacityworkload

## Cursor lifecycle

format2/HMACdomainv2ใช้KeyPurpose.INDICATOR_CURSORเดิม ผูกsessionเหมือนเดิม
เพิ่มgeneration_id/checkpoint codecversion/rollout_epoch; clientไม่ส่งstate/fenceเอง
formula_versionของสูตรเดิมคงเดิม dataset_revisionยังเป็นdigestจริงตอนbuild
compatibilitydecoderเลือกv1/v2 schemaและHMACdomainจากformatselectorที่มีขอบ
แล้วverifyMAC/session/canonicalclaimsก่อนตัดสินlifecycle ไม่เชื่อformatfieldที่ยัง
ไม่ได้verify ไม่ลองwrongdomainแล้วfallbackยอมรับอีกformat; v1bytes/domainเดิมไม่เปลี่ยน
LEGACYก่อนactivateยังรับv1ตามสัญญาเดิม; PREPAREDรับvalidv2ของactiveepoch
และvalidv1→409เพื่อเริ่มใหม่; PREPARING/PAUSEDรับvalidv1/v2แล้วคืน409
ไม่จัดvalidv2เป็นunknownformat/tamperเพียงเพราะreplicaอยู่compatibilityversion
tamper/unknownformat/schemaผิด/cross-sessionยัง422; expiry/retiredkeyใช้409เดิม
APIทุกตัวต้องมีverificationkeyringเดียวกันก่อนออกv2 ไม่rotatekeyพร้อมcutover
เก็บkeyที่ต้องverifyจนtoken supportwindowจบ; ไม่เผยMAC/token/keyในcapabilitylogs
ไม่มีmixed-format/mixed-generation pages และไม่มีsecret/tokenในlog
APIที่restartแล้วอ่านgenerationเดิมได้ ไม่ใช้RAMcacheหรือsticky routingเป็นproof

## ของเดิมและไฟล์ที่เสนอให้แก้

ใช้core.indicators/indicator_batch, canonicalhash, catalog, routing/auth, KeySource,
API read-only transaction/budget และF-09claim/lease test patternsซ้ำ
ไม่เรียกmarket-dataหรือAPIserviceผ่านHTTPจากbuilder และไม่reusewriter sessionผิดrole

| พื้นที่ | งาน |
|---|---|
| `core/indicators.py`, `core/money/indicator_batch.py` | strict immutablecheckpoint export/import ใช้Moneystate/controlsเดิม ไม่เพิ่มสูตร |
| `infra/indicators/{records,storage,claims,codec}.py` | sourcefence/gen/checkpoint/jobs, singletonbuildslot/sessionlock/fencing, readonly/pinnedwriter typed sessions, publication/GC |
| `services/indicator_builder/{main,settings,worker}.py` | scheduler/claim/build/heartbeat/retryตามงบ ไม่importserviceอื่น |
| `infra/db/{engine,session,__init__}.py`, `db/bootstrap/00-roles.sql` | role/URLs/sessions/grants/assertionsใหม่ |
| `migrations/versions/<next>_prepared_indicators.py` | metadata/trigger/views/functions/partitionsupgrade-downgrade |
| `infra/market_data/claims.py` | physicalcleanupcutoffและrequireacquiredsourcewrite scopeก่อนwrite_candles/cleanup/pre-locks; publicwindow/ingestlogicalcutoffเดิม |
| `services/market_data/ingestion.py` | acquirewrite scopeก่อนlock_claimในwrite transaction; แยกstartupseed metadataกับcleanupคนละtransaction; ไม่ถือscopeขณะfetchvenue |
| APIindicator routes/cursor/app และCompose/CI/configdocs | readyhead/checkpointread, dualv1/v2 decoder/rollout_epoch, DBrolloutgate, capability/runbook/drain และworkerdeploymentแบบpublicdata |
| testscore/infra/API, OpenAPI/frontendgenerated | R2criteriaและregressionF-09/F-11; ไม่มีUIใหม่ |

## Validation amendments — Approved / ยังไม่ได้รัน

| ID | เกณฑ์ |
|---|---|
| R2-1 | เตรียมDBว่างแล้วGET503ไม่มีDML/partial; schedulerclaim/build/publishจริงและGET200หลังcommit ไม่ใช้202/READYflagก่อนpublishเป็นproof |
| R2-2 | Restoreก่อน/ตรง/หลังcheckpointboundary, batch1/2/16, fetchsizesต่างกัน ให้ค่าทุกindicator/status/seed/digestตรงindependentoracleและfull-scanreference; ไม่มีfeedslotซ้ำหรือข้าม |
| R2-3 | ตั้ง2/3connectionsด้วยbarriers: delayedwritercommit/rollback, writeระหว่างbuild/publish/read, identitymove, appendนอกU, ABA, missingproof; journalcoverage/root-leaf/upsert/cleanupทุกpathไม่ให้falsevalid |
| R2-4 | ตรวจlogical365/physical365+6h15mแยกกันด้วยUTC/fakeclock; oldestseedยังอยู่ระหว่างbuild/validcursor, deleteจริง409; firstrequestage600sขอบ−1µs/ตรง/+1µsและtoken/gen expiryครบ |
| R2-5 | workercrashหลังstagingcommit/ก่อนpublish, leaseexpire/holderกลับมา, 2replicasclaimซ้อนทั้งseriesเดียว/ต่างseries, heartbeattimeoutและretrycap; ผ่านR2-G1..G7 globalprotocolและมีreadyheadatomicเพียงรุ่นที่publishสำเร็จ |
| R2-6 | upgrade/replay/downgrade, actualAPI/builder/market-data roles, directleaf/newpartition/truncate/maintenance, hardeneddefiner search_path/PUBLICEXECUTE; ไม่มีsecret/user/order access |
| R2-7 | ปิดAPIprocessใหม่โดยDBมีpreparedfixture525,600แล้วเปิดใหม่: cold1/warm5 ทุกrequest200/digest/1,000outputถูกต้อง<=30s, lag<=100ms/RSSdelta<=128MiB/body<=2MiB; ห้ามแอบbuildในmeasuredrequest |
| R2-8 | genuinelyempty-derived-datacold503แยกจากR2-7; fullbuilder<=120s และcapacityต้องผ่านR2-C1..C6ครบ30seriesทั้งbootstrap/steady-state/dirty/rejectedload; NOT_READYนับunavailable ไม่มีทางเลือกแค่รายงาน503แล้วผ่าน; เกินtime-to-ready/availabilityที่กำหนดคือFailed |
| R2-9 | สุ่มราคาที่มีเศษ/เปลี่ยนทิศ/gaps/REFRESH_REQUIRED/UNCONF→CLOSEDให้checkpointstateและfutureoutputตรง; Money/Quantity/ambientcontext/overflowเดิมทั้งหมดผ่าน |
| R2-10 | DB/Redis/worker outage, response serialization/expiry race/cancel/disconnect/cleanup2s, journalfloor/GCpressureและdamagedcheckpoint failclosed; budgets/restartcap/sessionnonrenew/cache/logredactionเดิม |
| R2-11 | fixedsizecodec<=16KiB/boundedseedbuffers/source2,000slotอ่าน<=1,999; retention/GC/indexdiskcapจริง; ไม่load525,600inputs/resultsพร้อมกันในAPI/worker |
| R2-12 | F-09storage/ingestion/claim/retention/permissions และF-11full regression, backend/frontend/generated/LinuxAPIcontractgatesผ่านครบก่อนmerge |

เพิ่มเกณฑ์เฉพาะreviewข้อ1 — R2-L1..L6 (Approved/ยังไม่ได้รัน):
- R2-L1: traceSQLของrun_round/write_candles/cleanupจริง: relation locksและguard
  มาก่อนdemand/candle FOR UPDATE; startupseedcommitก่อนcleanup transactionใหม่
  และไม่มีvenuefetchในsourcewrite scope fixture sourceDMLต้องacquire scopeจริง
- R2-L2: PostgreSQL2connections+barriersสำหรับF-09 preselect/upsertกับwriter
  หรือcleanupอีกตัวที่overlap; pathที่แก้แล้วต้องจบ/ถูกboundedtimeoutโดยไม่มี
  lock-order cycle/deadlock รันทั้งroot/leafและmulti-row/partition cases
  negative-controlของลำดับเก่าต้องแสดงcycleที่เคยพบ ไม่disabletriggerเพื่อให้ผ่าน
- R2-L3: maintenanceDROP/DETACH/TRUNCATEพร้อมruntimewriter/reader/publisher:
  ตรวจrelation locksมาก่อนguard และpublisher/GCไม่querycandlesเมื่อถือguard
  ปิดblockerแล้วต้องprogressได้; boundedtimeoutต้องrollbackepoch/heads/DDLร่วมกัน
- R2-L4: sourceDMLนอกregisteredscope/rootหรือleafต้องSOURCE_WRITE_SCOPE_REQUIRED;
  scopeownerปลอม/ข้ามtransaction/WRITE→MAINTENANCE upgradeถูกปฏิเสธ
  SELECTของAPIไม่ต้องและเรียกmutatinghelperไม่ได้; maintenancehelperเฉพาะmigrator
- R2-L5: failedlease/claimหลังscopeentry, helpertimeout, cancel/disconnect/rollback
  ต้องคืนrelation/guard/row locksและไม่มีpartialsource/journal/counter/metadata
  requestต่อไปใช้connectionเดิมได้โดยไม่มีscopemarkerของtransactionเก่ารั่ว
- R2-L6: actualroles/legitimatefixtures/upsert/cleanup/claim/heartbeat/F-09regression
  ผ่านด้วยprotocolใหม่ ไม่ผ่อนexpectedgrantsหรือใช้superuserแทนruntimepath

เพิ่มเกณฑ์เฉพาะreviewข้อ3 — R2-F1..F6 (Approved/ยังไม่ได้รัน):
- R2-F1: typednumericfailureก่อน/หลังstagingcommitและนอกoutputpageต้อง
  FAILED_NUMERIC/GET422 INDICATOR_NUMERIC_ERROR ไม่มีREADY/partial/oldheadfallback;
  retryGETinputเดิมได้errorเดิม ไม่มีbuilderclaim/compute/venue retryหรือRetry-After
- R2-F2: timerที่alignedL/Uยังเดิม/restart/appendนอกUโดยboundsไม่เปลี่ยน/
  metadatawrite/operatorretryห้ามปลุกnumericinputเดิม; relevantwrite/formula
  revisionหรือalignedboundsใหม่สร้างcandidateใหม่ได้ตามscope R2-N1..N4
  barrierwrite/rollback/leaseexpireระหว่างfailurepublishต้องไม่เผยstale manifest
- R2-F3: sanitizedfailureviewพิสูจน์epoch/floor/bounds/candidateorder/expiryจริง;
  newerREADYไม่ถูกoldfailureปิดบัง, validcontinuationไม่ถูกfailureคนละcandidate
  เปลี่ยนเป็น422; invalidtoken/proofยัง409 และGC/proofขาดหน้าแรก503
- R2-F4: injecttransientfaultครบinitial+retry2/backoff30/60 แล้วFAILED_TRANSIENT;
  snapshot/state/connectionไม่reuseหลังabort, clock/restartไม่ปลุกcycleเอง
  queue/backoffทั้งหมดนับdeadlineเดิม; numeric/codec/configerrorไม่เข้าretryloopนี้
- R2-F5: รันCLIด้วยactualroleหลังแก้fault; cooldownขอบก่อน/ตรง/หลัง600s,
  duplicate/concurrentrequestid, RUNNING/READY/numericreject, crashก่อน/หลังcommit
  ต้องมีcycleใหม่ไม่เกิน1ต่อrequestid; recoveryได้READYจริงโดยไม่resetcapacitydeadline
- R2-F6: APIอ่านfailureviewได้แต่baseFAILED/STAGING/requestretryfunctionไม่ได้;
  builderretryfunctionไม่มีPUBLICEXECUTE/SQLinjection, errors/logs/responseไม่มี
  inputs/secrets/traceback; codecerror503แยกจากtypedcoreerror422และregressionNC-33ผ่าน

เพิ่มเกณฑ์เฉพาะreviewซ้ำข้อ1 — R2-N1..N4 (Approved/ยังไม่ได้รัน):
- R2-N1: fakeDBclockก่อน/ตรง/หลังalignmentboundaryทุกTF; as_ofเปลี่ยนแต่L/U
  เดิม, globalfenceจากseriesอื่น, metadata-onlywrite, restartและmanifestGC
  ต้องไม่computeFAILED_NUMERICkeyเดิมซ้ำ API422เมื่อmanifest/proofยังใช้ได้
- R2-N2: fixtureเกิดtypedoverflowในwindowเดิม แต่windowLใหม่ที่เลื่อนพ้นแท่ง
  นั้นคำนวณได้: ไม่มีOHLCupdate/formula change/operatorretry/POSTrefresh
  schedulerต้องสร้างkeyใหม่จากinitialstate, publishREADYและGET200ตรงoracle
  ช่วงpending503 ไม่คืนold422; oldmanifestไม่ถูกแก้/ต่ออายุหรือปิดบังnewREADY
- R2-N3: Uขยายเข้าครอบappendนอกUเดิมและLเลื่อนที่seedเปลี่ยนแต่แท่งerrorยังอยู่;
  ตรวจnewkey/output/errorตามfullscanoracle ไม่ทำนายจากoldmanifest
  appendที่boundsไม่เปลี่ยนไม่ปลุกoldkey; proofขาดอย่างเดียวไม่resetnumericfailure
- R2-N4: 2replicas/pollซ้ำ/หลายwindowผ่านระหว่างRUNNINGหรือoutage, crashและGC:
  desiredpending<=1/series, newestwindowcoalesced ไม่มีduplicateinitialnumericcompute
  ของfailedkey/inputversionเดิม; global1/pool2/120s/transientcap/deadlineยังผ่าน
  firsteligibleไม่ถูกreset และHTTPGETไม่มีDML/venuecall/partialresponse

เพิ่มเกณฑ์เฉพาะreviewซ้ำข้อ2 — R2-S1..S5 (Approved/ยังไม่ได้รัน):
- R2-S1: realPG+2replicas/barriers, Aมีdeadlineเก่ากว่าBและrelevantwriteทุก
  attemptของA; Bนิ่งและdueก่อนAattemptแรกจบ ต้องclaimBก่อนAได้attemptที่2
  ในroundถัดไป แม้Adeadline
  หมดไปแล้ว ตรวจround/claimtrace/CPUintervalจริง ไม่ใช้publishcountอย่างเดียว
- R2-S2: initial+superseded+transientสลับกันรวมไม่เกิน3, backoff30/60,
  terminalFAILED_SUPERSEDEDตามเหตุสุดท้าย; poll/window/source coalesce/restart
  ไม่resetcounterหรือservedmarker เกินงบไม่มีscan/hash/claimใหม่โดยclockอย่างเดียว
- R2-S3: claimrollback/ambiguouscommit/workercrash/reap/roundadvanceพร้อมกัน:
  atomicserved/counter/token, ไม่duplicateclaimต่อseries/roundและไม่refund
  committedattempt; pendinglatest<=1, nohotspin และpool2/global1/120sยังผ่าน
- R2-S4: sourceeventก่อน/หลังfailed_at, cooldownก่อน/ตรง/หลัง600s, duplicate
  manualCLIและlease-loss: resumeได้เฉพาะallowedtrigger+safehandoff ไม่มีreset
  firsteligible/deadline/lastserved; deadline_missedยังคงรายงานทั้งช่วงที่ถูกพัก
- R2-S5: ครบ30seriesตามCfixture; Aมีhistoricalwritesต่อเนื่อง แต่อีก29append-only
  ต้องพร้อม/GET200ภายใน600sจากeligibilityและคงเกณฑ์healthyของแต่ละseriesหลัง
  recovery โดยนับqueue/otherattemptsตามจริง; Aunavailableนับตามจริง ไม่เฉลี่ย
  กับ29series พร้อมกันนี้C1..C6/F4..F5/G7/N4ต้องยังผ่านด้วยfairroundจริง

เพิ่มเกณฑ์เฉพาะreviewข้อ4 — R2-G1..G7 (Approved/ยังไม่ได้รัน):
- R2-G1: realPostgreSQL+2workerprocesses+barriers ต่างseries/ต่างformulaและ
  seriesเดียวกัน; holderAค้างก่อนscan/กลางCPU/หลังstaging/ก่อนpublishแล้วBclaim
  ต้องไม่มีBjobRUNNING/sourcesnapshot/scan/hash/coreก่อนAjoin/close/release
  ตรวจactualpg_locks/job/slotและbuildintervaltrace ไม่ใช้แค่READYcountเป็นproof
- R2-G2: claimcommit/nojob/rollback, success/numericfailure/operationalfailure/
  timeout/cancelทุกทาง: stop/joinCPUและปิดsourceก่อนunlock; poolใช้ไม่เกิน2
  heartbeat/writeserializedบนphysicalwriterเดิม ไม่มีlockleak/reentrantcountสะสม
  poolreuseหลังrollbackต้องไม่ได้sessionlockของattemptเก่าติดมา
- R2-G3: pauseholderนานกว่าlease150sแต่DBsessionยังอยู่ Bห้ามtakeover;
  resumeholderต้องไม่write/publishหลังlease/deadline และต้องsafe-release
  operatorstopprocess/reapจึงเปิดงานใหม่ได้ ไม่มีCPUสองattemptซ้อน
- R2-G4: killprocess/killwriterbackend/networkpartition/DBrestartและambiguous
  commit: แม้advisorylockว่างแต่slotownerยังค้าง Bต้องfailclosed ไม่build
  reapก่อนยืนยันownerprocessสิ้นสุดห้ามทำ; หลังstop+reapจริง Bได้fenceใหม่
  oldconnection/reconnect/tokenส่งheartbeat/checkpoint/READY/failure/releaseไม่ได้
- R2-G5: barriersclaim/heartbeat/publish/manualretry/reap/sourcewriter/GC:
  traceorder sourceguard→rolloutcontrol→slot→jobในpublication,
  control→slot→jobแล้วcommitในclaim
  ไม่มีslot/job→sourceguardwaitหรือbuildslotในF-09; lock/querytimeoutคืนrowlocks
  และไม่ถือguardตลอดscan ต้องผ่านR2-L1..L6ด้วยprotocolรวมกัน
- R2-G6: actualroles/typedfunctions/directDMLbypass/globalkeyidentity, spoofed
  owner/backend/fence/GUC, stalelease, slotfenceoverflow, unsupportedpooler:
  failclosed; API/market-data/builderเรียกmigratorreapไม่ได้ ไม่มีPUBLICEXECUTE
  config/connectionข้อผิดพลาดไม่เพิ่มpooloverflowหรือเปิดbuildแบบไม่มีslot
- R2-G7: rerunR2-C1..C6และR2-F4/F5ด้วย2replicasครบ30series; contenderpoll
  ไม่busyspin/resetdeadline/consumeattemptก่อนclaim, backoffไม่ถือglobalslot
  crashattempt/reapไม่resetretrybudget และfairness/deadline/resourcesยังผ่าน

เพิ่มเกณฑ์เฉพาะreviewข้อ5 — R2-D1..D7 (Approved/ยังไม่ได้รัน):
- R2-D1: runlegacyAPI/F-09binaryกับexpandedschemaจริง ก่อนstricttrigger;
  legacy+compatibilityAPIสลับreplicaในLEGACYด้วยv1page1/continuationได้ตามเดิม
  ไม่มีv2 issuance/builderclaimก่อนstagegate ไม่ใช้teststubแทนolddecoder
- R2-D2: compatibility+preparedAPI2processesบนDBจริงในPREPAREDพร้อมkeysเดียวกัน;
  page1ที่A/v2continuationที่Bและกลับกัน randomrouting/restartยัง200/parity
  หรือ409ตามactualproof ไม่422เพราะversion; v1MACถูก409, tamper/cross-session/
  formatspoof422, expired/retiredkey409 และepochเก่าหลังre-enable409
- R2-D3: oldF-09cleanup365วันในmixedstageต้องบล็อกproof/buildactivation;
  drainsourcewriter/cleanupจริงก่อนinstallstricttriggerแล้วrestartเฉพาะcompatible
  ทดสอบcutoffseed365วัน/365วัน+6h15mทุกreplica, cleanupขณะv2paginateไม่ลบseed
  ตั้งimage/restartnegativecontrolให้gateปฏิเสธ ไม่disabletriggerเพื่อให้oldwriterผ่าน
- R2-D4: barriersinflightAPI/sourcesnapshot/build/cleanupระหว่างactivate/rollback:
  ต้องdrain/stopก่อนcontrolflip/DDL, ไม่ออกtokenepochเก่าหลังcutoff
  PAUSEDหน้าแรก503/validcursor409โดยไม่queryremovedgenerationหรือfallbackfullscan
  mode/epochมาจากDBsnapshotไม่ใช่staleprocessflag และHTTPGETไม่มีDML
- R2-D5: rollbackหลังออกv2, freshv2/olderv2/sessionexpiry, DBclockcutoff+6h
  ขอบก่อน/ตรง/หลัง; ห้ามถอนschema/key/physicalgraceก่อนsupportwindow/readerdrain
  compatibilitybinaryยังdecodevalidv2เป็น409ได้ทุกreplicaระหว่างPAUSED
  legacyimageไม่ถูกroute/restartก่อนgate; re-enableไม่ชุบcursorเก่า
- R2-D6: actualroles/controltransition/replay/ambiguouscommit/cancelของmigration:
  API/F-09/builderแก้mode/epoch/compatibilitypolicyเองไม่ได้, PUBLICEXECUTEไม่มี
  invalidstagetransition failclosed; operatorตรวจstateจริงก่อนresumeไม่blind-flip
  half-installedtrigger/grant/controlหายหรือunsupportedcodecต้องไม่เปิดpreparedmode
  replayไม่เพิ่มepochซ้ำ; rollbackก่อนออกv2ยังต้องdrainwritersก่อนถอนstricttrigger
- R2-D7: rehearsedstop/drain/startในComposeและmulti-replicaharness พร้อมinventory
  image/protocol/keyversionที่ไม่เผยsecret; missing/offlinelegacyreplicaต้องบล็อก
  activationและห้ามอ้างzero-downtime; R2-C/L/F/G/regressionsยังผ่านหลังrollingupdate

R2-7แทนเฉพาะV-15/PV-6ที่เคยรวมfullbuildในcoldAPI; R2-1/8เพิ่มcold miss/build
ข้อV/PVอื่นคงผลที่ต้องพิสูจน์ตามสัญญาเดิมหรือamendmentที่ระบุชัดด้านบน
checkpointcold/warmbenchmarkไม่ทำให้V-15เดิมที่ล้มย้อนหลังกลายเป็นผ่าน

## การอนุมัติและด่านก่อนโค้ด

1. **ผ่านแล้ว2026-10-10:** NC-35 Closed และrequirements amendmentsทั้งF-11/F-09 Approved
2. **ผ่านแล้ว2026-10-10:** plan/validation amendmentsของทั้งสองงานและADR-002 Approved
3. ทำmigration/epoch proofs/actualrolesก่อนworker/APIprepared mode
4. ทำcheckpointcodecและparityก่อนpublish; วัดbuilder/capacityครบR2-C1..C6และ
   READYAPI benchmarkก่อนเปิดpreparedmodeจริง ไม่เปิดด้วยผลAPIที่prewarmไว้เท่านั้น
5. ถ้าขาดcoverageจากtrigger, cold/readinesspolicyไม่ตกลง หรือdeadline/storageไม่ผ่าน
   ให้หยุดเสนอแผนใหม่ ไม่ขยายretention/freshness/budgetsเอง

ขอบเขตที่เจ้าของอนุมัติคือรายละเอียดทั้งหมดในเอกสารนี้พร้อมADR-002 รวมsourcewrite scope/
maintenance lock protocol/R2-L1..L6, error/retry contract/R2-F1..F6,
numericwindowrecovery/R2-N1..N4,
supersessionbudget/durablefairround/R2-S1..S5,
globalbuildslot/safehandoff/R2-G1..G7, mixed-versionrollout/rollback/R2-D1..D7 และcapacity
acceptance R2-C1..C6 โดยเฉพาะcold503,
freshness600s, physicalgrace6h15m และinvalidationที่เข้มขึ้น; ไม่ใช่เพียงอนุมัติว่า
ควรทำให้APIเร็วขึ้น และไม่อนุญาตเปลี่ยนกฎส่งออเดอร์/เปิดLive/เงินผู้ใช้
