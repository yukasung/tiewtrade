# ADR-002 — Prepared indicator generations และsource fence

สถานะ: **Approved** — เจ้าของอนุมัติพร้อมแผนรอบ2และrequirements/plan/validation amendmentsของF-11/F-09เมื่อ2026-10-10 ตามคำสั่ง “approve”; NC-35 Closed
วันที่: 2026-10-10

ที่มาและสัญญาตัวเลข/lifecycleอยู่ใน
[F-11 performance-plan-v2](../features/2026-10-10-backend-indicators/performance-plan-v2.md)
ADRนี้เป็นแหล่งเดียวของrole/guard/trigger architectureที่อนุมัติแล้ว
สิทธิ์/schemaใหม่ยังต้องapplyผ่านmigrationตามแผน; approvalไม่ใช่ผลvalidationผ่าน

## Process และสิทธิ์

| Role/process | สิทธิ์ที่อนุมัติ | ข้อห้าม |
|---|---|---|
| API | SELECTready-generation/checkpointviews, sanitizednumericfailureview, rolloutcontrol และpublicsource/journalproofภายใต้UserSessionเดิม | ไม่มีDMLใหม่, ไม่มีSTAGING/FAILEDbase-tableSELECT, ไม่มีretry/rollouttransitionfunctionEXECUTE, ไม่มีsecret/order/userdataเพิ่ม |
| indicator-builder | SELECTpubliccandles/journal; claim/staging/checkpoint/GCเฉพาะderivedmetadata; publish/failure/manualretryผ่านfunctionที่จำกัด | ไม่เขียนcandles/demandF-09, ไม่แตะusers/auth/key/balance/positions/orders/audit, ไม่มีDDL/owner/bypassRLS |
| market-data | candle/demandเดิม; เริ่มsource write scopeก่อนล็อกแถว/เขียนcandles; triggerบันทึกjournalในtransactionเดียวกัน | ไม่เขียนcheckpoints/heads/sourceversionเอง ไม่เขียนcandlesนอกscope |
| migrator/bootstrap | สร้างschema/role/grants/function/trigger/partition-hookและmaintenance | ไม่ใช้runtimecredentialsของmigratorในAPIหรือworker |

เพิ่มrole `tiewtrade_indicator_builder` กับenvironment URLเฉพาะ
sessionชนิดใหม่แยกsourceROและderivedwriter ไม่ใช้APIUserSessionหรือMarketDataSession
โดยตั้งroleผิด; sourceROตั้งRR/READONLYก่อนSELECTแรก ส่วนwriterใช้shorttransactions
workerไม่คุยserviceอื่นผ่านHTTP และimportdirectionsเดิมยังบังคับด้วยlint-imports
นี่เป็นข้อเสนอขยายarchitecture/database standardsเฉพาะpublicderived indicators
ไม่อนุญาตmarket-data/builderทำงานบัญชีผู้ใช้หรือส่งออเดอร์

## Schema ที่อนุมัติ

- `indicator_rollout_control`: singleton id=1, mode LEGACY/PREPARING/PREPARED/PAUSED,
  rollout_epoch UUID, activecursorformat/codecversion/protocolversion,
  sourceproofstate/retentionpolicy และlast_v2_issue_cutoff TIMESTAMPTZ;
  migratorเปลี่ยนผ่านfixedtypedtransitionfunctionเท่านั้น ไม่มีper-replicamode
  API/builder/F-09อ่านเฉพาะpolicyที่ต้องใช้และห้ามเขียนcontrolโดยตรง
- `indicator_source_guard`: singleton epoch UUID/revision BIGINT/journal_floor
  และscope_owner_xid/scope_kindที่helperตั้งจากtransactionจริง ไม่มีclient-suppliedowner
  implementationเก็บprotected_relationsจากpartitioncatalogเพื่อให้sql_drop hook
  ตรวจDROP/DETACHหลังcatalogเปลี่ยนได้; runtimeเขียนรายการนี้เองไม่ได้
- `indicator_source_changes`: epoch/revision/source/base/quote/timeframe/open_at/kind
  unique event key ป้องกันduplicateในstatement; indexสำหรับseries+revision+open_at
- `indicator_build_slot`: singleton id=1, slot_epoch UUID/fence BIGINT,
  owner_instance UUID/owner_backend_pid/job_id/generation_id/claim_token,
  lease_until/attempt_deadline/last_heartbeat/state และdispatch_round BIGINT;
  CHECK id=1 และไม่มีslotที่สอง
  globalfenceแยกจากsourceepoch/revision ไม่ใช้แทนsourceproof
- `indicator_build_jobs`: coalescedseries/formula, claim token/generation/lease/retry,
  build_rollout_epoch/monotonicgenerationsequence/currentcandidate และtypedfailurecategory/failed_at;
  desiredcalculationkey และfailedcalculationkey/inputversion suppression identity
  แยกจากclaimtoken/as_of/manifest; คงsuppressionเมื่อmanifestถูกGCและไม่มี
  relevantinput/bounds/formula change ไม่ใช้globalrevisionที่เปลี่ยนจากseriesอื่น
  เก็บeligible_at/deadlineเดิมตลอดunavailable episodeตามแผน ไม่resetเมื่อretry
  attempts_used/cycle_id/retry_not_before/last_served_round/deadline_missed_at
  และterminalfailure reason/recoveryevent สำหรับsharedretrybudget+durablefairround
  counter/servedmarkerไม่ล้างด้วยcoalesce/restart/newcandidateหรือmanifestGC
- `indicator_generations`: identity/L/U/as_of, sourceepoch/fence, digest,
  checkpointcount/codecversion/status/expiry, build_rollout_epoch/candidate sequenceและfixedfailure_code;
  failednumericdigestเป็นNULLเมื่อscanไม่ครบ ไม่มีuser/session/inputerrorcolumns
- `indicator_checkpoints`: generationid/next_open_at/payload/size;immutableหลังpublish
- `indicator_heads`: latestpublishedgeneration per series/formula
- `indicator_retry_requests`: uniqueoperatorrequest UUID/job/cycle/fixedresult
  สำหรับatomic/idempotentmanualretry ไม่มีHTTP/userdata; นับในderivedstoragebudget

APIเห็นcheckpointผ่านviewที่joinREADY generationเท่านั้น; proof/expiryยังต้องตรวจ
ในsnapshotเดียวกันตามแผน ส่วนsemanticstatevalidationทำที่typedcodecทั้งwriter/reader
การมีstatusREADYเฉย ๆไม่แทนjournalproofหรือMoney/Quantity validation

แก้reviewข้อ3: APIยังอ่านcheckpointได้เฉพาะREADY แต่ต้องอ่านnumeric failure
ผ่านsanitizedviewแยกเพื่อคง422ตามNC-33 แทนการแปลงFAILEDเป็นcoldmiss503
viewเปิดเฉพาะfixedfailure_code/generationidentity/bounds/formula/codecversion/
sourceepoch/fence/as_of/expiry/candidatesequenceและjobcurrentcandidateที่ต้องใช้proof
ไม่มีexceptionmessage/stacktrace/inputvaluesหรือpayloadของFAILED/STAGING
การตัดสินerror/retry/scope/continuationใช้สัญญาในแผนรอบ2ที่เดียว
แก้reviewซ้ำข้อ1: failedcandidateห้ามใช้กับdesiredcalculationkeyใหม่เมื่อaligned
L/Uเปลี่ยน Schedulerยังpollboundsแม้FAILED_NUMERICและสร้างชุดใหม่จากinitialstate
ตามNumeric recovery/R2-N1..N4ในแผน; ไม่reset/retryfailedkeyเดิมหรือreusefailedstate
desiredcoalesce/claimต้องเปรียบเทียบkey/inputversionแบบatomicในjobprotocolเดิม
มีpendingล่าสุดไม่เกิน1ต่อseries ไม่มีHTTPGETenqueueหรือสิทธิ์APIเขียนsuppression
แก้reviewซ้ำข้อ2: generationSUPERSEDEDแยกจากjobQUEUED/FAILED_SUPERSEDED;
jobใช้attemptbudgetร่วมกับtransientตามSupersession budgetในแผนรอบ2
expiredavailabilitydeadlineเป็นreportingdata ไม่ให้สิทธิ์ข้ามfairround/พักงาน
ทุกclaim/terminalupdate/recoveryตรวจtypedbudget/eligibility ไม่มีdirectDMLreset

Failurepublishใช้guard→rolloutcontrol→slot→job/generation locksตามprotocolเดียวกับREADYpublish
ตรวจclaimtoken/lease/currentcandidate/sourceproofก่อนบันทึกmanifestอย่างatomic;
numericfailureไม่สลับREADYheadและลบSTAGINGผ่านboundedGC ไม่เปิดpartialcheckpoint
ข้อมูลที่commitไปก่อนเกิดerrorจึงอ่านไม่ได้ Lateholderเขียนfailureทับcandidateใหม่ไม่ได้

OperatorCLIใช้buildercredentialเรียกfixedtypedmanualretryfunctionด้วยjob UUID/
request UUIDเท่านั้น; functionล็อกjobแล้วตรวจcategory/cooldown/idempotencyและ
transitionQUEUEDสำหรับFAILED_TRANSIENT/FAILED_SUPERSEDED/FAILED_OPERATIONAL
พร้อมrequestresultในtransactionเดียว ตามแผน ไม่รับSQL/status/
attemptcounter/fenceจากcaller ไม่อนุญาตresetFAILED_NUMERICของinputเดิม
revokePUBLIC/API/market-dataEXECUTEและห้ามdirectDMLresetjobเพื่อข้ามprotocol
นี่เป็นmanualrecoveryหลังแก้fault ไม่ใช่HTTPAPIใหม่หรือautomaticretryทุก600s
retryfunctionไม่resetlast_served_round/episode deadlinesและไม่clearglobalslot;
OWNERSHIP_LOSTยังต้องstop/reapก่อนbuildใหม่แม้jobกลับQUEUEDแล้ว

## Global build slot — แก้reviewข้อ4 (Approved)

หนึ่งdatabaseมีbuild slotเดียวสำหรับทุกseries/formula/replica ใช้สองกลไกร่วมกัน:
session advisory lock `(711, 1)` สำหรับexclusive ownershipตลอดattempt และ
singleton slot rowสำหรับdurableidentity/lease/fencing ไม่ใช้per-seriesjob lease
หรือsourceguardช่วงpublishเป็นตัวจำกัดbuildconcurrency
namespaceนี้สงวนให้F-11; F-09startupใช้transactionlock `(709, 1)` อยู่แล้ว
ห้ามเปลี่ยนkeyตามworker/series/formulaหรือรับkeyจากcaller

1. Workercheckoutและpinphysicalwriterconnectionหนึ่งเส้นจากpoolเดิม แล้วเรียก
   fixedhelperที่ใช้ `pg_try_advisory_lock(711, 1)` เพียงครั้งเดียวก่อนclaimjob
   ไม่ได้lockให้คืนconnectionและรอschedulerpollเดิม โดยไม่claim/เปิดsource
   snapshot/scan/hash; ไม่busy-spin และไม่ถือjobrowขณะรอglobalสิทธิ์
2. ได้lockแล้ว shorttransactionล็อกrolloutcontrol→slot→เลือกunservedeligiblejob
   ตามdurablefairround/deadline/round-robinในแผน→ล็อกjob
   จึงเพิ่มglobalfenceและjobgenerationsequence พร้อมตั้งowner_instanceใหม่ต่อ
   processboot, backendpidจริง, generation/token/lease/attemptdeadlineและRUNNING
   advance dispatch_roundเมื่อจำเป็น/marklast_served_round/consumeattempt
   พร้อมclaimในtransactionเดียว; commitทั้งหมดพร้อมกัน
   ไม่มีduejobหรือclaimrollbackต้องunlockก่อนคืนconnection ไม่advanceรอบวนเอง
   slotที่ยังมีownerเก่าห้ามoverwriteเพียงเพราะleaseหมด ตามhandoffด้านล่าง
3. เปิดsourceROsnapshotได้หลังclaimcommitเท่านั้น Writerconnectionที่ถือadvisory
   lockใช้staging/heartbeat/publishแบบserialized ไม่เปิดheartbeatqueryพร้อมwrite
   บนconnectionเดียวกัน; sourceROเป็นconnectionที่สอง ไม่มีconnectionที่สาม
   ไม่คืนwriterเข้าพูลระหว่างattempt ไม่ผ่านtransaction/statementpooler;
   configที่รักษาphysicalsessionไม่ได้ต้องrejectก่อนรับงาน
4. Heartbeatทุก20sและทุกcheckpointwriteตรวจslot+job identity/lease/deadline
   จากDB clockบนwriterเดิม; lease150sไม่ต่อattemptdeadline120s
   ก่อนทุกCPU slice<=16ตรวจlocaldeadline/ownership-loss flag; lostconnection,
   failedheartbeat/lease/deadlineต้องcancelและjoinbuildtask ปิดsourcesnapshot
   ห้ามreconnectแล้วresumeclaimเดิม แม้workerยังมีstateในRAM
5. Checkpointwrite/heartbeatและREADY/failurepublishต้องตรวจทั้ง
   slot_epoch/fence/owner_instance/backendpid/job/generation/claim_token,
   lease_until>DB clock และattemptdeadline; ตรวจactualadvisorylockที่session
   ถือจากpg_catalog.pg_locks ไม่เชื่อcallerboolean/GUC; callerเลือกfenceใหม่ไม่ได้
   CHECK/typedfunctionsและgrantsห้ามdirectDMLข้ามclaim/ownershipchecks
   terminalreleaseหลังtimeoutอนุญาตclearownerด้วยcompareidentityแม้deadline/
   leaseหมดแล้ว แต่ไม่มีสิทธิ์publishREADY/failuremanifestหรือเปลี่ยนownerใหม่
6. Publicationtransactionใช้ลำดับ **sourceguard→rolloutcontrol→slot→job/generation**;
   claimอ่าน/ล็อกcontrolก่อนslot/job ส่วนheartbeat/stagingใช้ **slot→job/generation**
   และcommitก่อนpublication
   ห้ามถือslot/jobrowแล้วขอsourceguard sourcewriter/GCไม่ขอbuildadvisorylock
   sessionlockค้างได้แต่ไม่มีslotrow/sourceguardtransactionค้างระหว่างfullscan

**Release/handoffและความหมายของconcurrency=1:**
- Attemptจบทุกทางต้องหยุด/joinCPUtaskและปิดsourceROก่อน clearownerในslot
  แบบcompareidentity พร้อมจบjobตามerror/retrycontract แล้วcommit จึงunlock
  sessionlockหนึ่งครั้งและคืนwriter ห้ามunlockก่อนCPUหยุดหรือถือslotระหว่าง
  retrybackoff; attemptถัดไปต้องacquireใหม่และได้fenceใหม่
- Sessionlockไม่ถูกปล่อยด้วยtransactionrollback และacquireซ้ำในsessionเดิม
  เป็นreentrant จึงห้ามเรียกacquireในheartbeat/retrytransaction; cleanupที่ไม่รู้
  lockcountหรือunlockล้มเหลวต้องinvalidate/closephysicalconnection ไม่คืนเข้าพูล
  อ้างพฤติกรรมจาก[PostgreSQL16 advisory locks](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS)
  และ[advisory lock functions](https://www.postgresql.org/docs/16/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS)
- Leaseหมดแต่sessionlockยังอยู่: contenderไม่ได้claimแม้เป็นคนละseries;
  ห้ามsteal/forceunlock/terminatebackendเพื่อเริ่มงานใหม่ทั้งที่CPUtaskเก่าอาจยังรัน
  workerที่ค้างต้องหยุดโดยprocesssupervisor/operatorก่อนส่งต่อ
- ถ้าDBconnectionหาย lockอาจถูกปล่อยทั้งที่processเก่ายังอยู่ จึงห้ามถือว่า
  advisorylockที่ได้ใหม่หรือleaseexpiryพิสูจน์ว่าCPUเก่าหยุดแล้ว Slotownerที่
  ค้างอยู่เป็นorphan: contenderปล่อยlockและfailclosed ไม่เปิดsource/build
  operatorต้องstop/killและยืนยันprocess/containerของowner_instanceเก่าสิ้นสุด
  ก่อนเรียกrestrictedmigrator helper `reap_indicator_build_slot(expected_owner,
  expected_epoch, expected_fence)`; helperต้องtrylockkeyเดิมและcompareslotidentity
  ในtransactionเดียว, fenceinvalidatesoldclaim/markSUPERSEDED/clearowner แล้วunlock
  ไม่มีสิทธิ์reapให้runtimeAPI/builder/market-data; บันทึกfixedoperationalresult
  interruptedattemptยังนับretrybudgetเดิม; reapไม่resetattempt/eligible/deadline
  ไม่resetservedmarker; เมื่อใช้ครบ3ให้jobFAILED_SUPERSEDED reasonOWNERSHIP_LOST
  มิฉะนั้นQUEUEDตามbackoff/retry_not_beforeเดิมหลังsafehandoff ไม่คืนattempt
  jobที่จะretryต้องผ่านbackoff/cap/failurecategoryในแผน ไม่claimcycleใหม่ไม่จำกัด
  ห้ามใช้leaseexpiryหรือpg_backend_pidเพียงอย่างเดียวแทนการยืนยันprocessหยุด
- DBrestart/ambiguouscommit/networkpartitionที่ยืนยันownerหยุดไม่ได้ต้องค้าง
  failclosedและรายงานunavailable ไม่สัญญาautomatictakeoverจากleaseเพียงอย่างเดียว
  cleanup2sไม่สำเร็จให้supervisorstopprocessก่อนreap; recoveryช่วงoutageไม่ยกเว้น
  capacityfailureของworkloadปกติ ไม่reseteligible_at/deadlineเพื่อซ่อนเวลาหยุด
- หลังsafehandoff holderเก่าที่ส่งrequestจากconnectionใหม่ต้องถูกfence/token/pid
  ปฏิเสธทุกwrite/heartbeat/publish/failure/release แม้jobเป็นคนละseriesกับholderใหม่
  fenceoverflowต้องหยุดbuildและเปลี่ยนslot_epochด้วยmaintenanceหลังหยุดowners
  ไม่wrapcounterหรือรีเซ็ตsourceepochเพื่อแก้buildfence
  dispatch_roundoverflowก็ต้องหยุดdispatchและmaintenanceรีเซ็ตroundกับ
  last_served_roundทุกjobแบบatomicหลังownersหยุด ไม่wrapบางแถวหรือresetตอนpoll

globalbuild=1จึงหมายถึงscan/hash/core/STAGINGจนpublication/cleanupของattempt
เดียวทั้งหมด ไม่ใช่เฉพาะREADYwrite; APIadmissionเดิมแยกกันและsourceingestion
ไม่ต้องถือbuildslot การยืนยันprocessหยุดเป็นเงื่อนไขของabnormalhandoffโดยเจตนา
ไม่อ้างว่าDBfencingเพียงอย่างเดียวหยุดCPUของprocessที่ขาดการติดต่อได้

## Commit-ordered source proof

แก้reviewข้อ1: triggerไม่ใช่จุดเริ่มลำดับล็อก เพราะF-09 `write_candles()` มี
SELECT candles FOR UPDATE ก่อนupsert และcaller `run_round()` ล็อกdemandก่อนเรียก
ต้องเปลี่ยนขอบtransactionทั้งเส้นทาง ไม่ใช่เพิ่มguardเฉพาะตอนINSERTหรือในcallee

เพิ่ม `begin_indicator_source_write()` เป็นfixed no-argument helper:
1. ล็อก `market_candles` แบบROW EXCLUSIVEรวมcurrentpartitionsด้วยstatic
   `LOCK TABLE market_candles IN ROW EXCLUSIVE MODE` ก่อนguard ไม่ใช้ONLY
2. ล็อกsourceguard rowและตั้งscope_owner_xidจากcurrenttransaction/scope_kind=WRITE
   ไม่advance revisionที่scopeentryและไม่ใช้customGUCหรือcallerbooleanเป็นproof
3. คืนcontrolให้caller จึงล็อกdemand/job/metadataและcandle rowsตามลำดับเดิม
   จากนั้นwrite/updateclaim/commitในtransactionเดียว ห้ามfetchvenueขณะถือscope

Runtimeลำดับคือ **source relation locks → sourceguard → metadata row locks
→ candle row locks → DML/commit** helperต้องเรียกในfreshwrite transactionก่อน
lock_claim/SELECT FOR UPDATE/metadataDMLใดที่จะตามด้วยcandlewrite
ถ้ามีpre-lockไปแล้ว ให้จบtransactionนั้นแล้วเริ่มใหม่ตามลำดับ ไม่acquireguardย้อนหลัง
ใช้ORDER BYของF-09เดิมสำหรับการล็อกหลายcandle rows

BEFORE STATEMENT ตรวจregisteredscopeของtransactionก่อนadvance revision
และAFTER ROWบันทึกkeysเมื่อcanonicalfieldsเปลี่ยน; triggerไม่พยายามสร้างscope
ย้อนหลังเอง คำสั่งroot/leafที่ไม่มีscopeต้องfailclosedก่อนรอguardด้วย
`SOURCE_WRITE_SCOPE_REQUIRED` ต้องมีtestsว่าปลอมGUC/ownerargumentไม่ได้
schema-qualifiedhelperใช้definerเฉพาะสิทธิ์lock/registerที่ระบุและrevokePUBLIC
scope markerไม่ได้พิสูจน์ว่าcallerไม่เคยpre-lockก่อนเรียกhelper จึงต้องตรวจSQLorder
ของทุกsupportedcallerและไม่รับรองrawSQLที่ละเมิดprotocolว่าจะไม่มีdeadlock

สองstatementในtransactionเดียวมีหลายrevisionได้ แต่rollbackพร้อมsource/guard/
journalทั้งหมด การถือguardจนcommitยังทำให้commit-order proofเดิมมีผล
ต้องวัดserialization/lock contentionจริง ไม่claimว่าไม่มีlock waitsเลย

Rootและleafต้องมีstatementguardเมื่อเป็นtargetโดยตรง และrowjournalครบทั้งexisting/
futurepartitions; ไม่พึ่งparentstatementtriggerว่าจะทำงานเมื่อtargetเป็นchild
upsertอาจเรียกทั้งINSERT/UPDATE statement triggers จึงยอมcountergap/noopและdedupeevents
เพื่อไม่ให้falseproofจากtriggerที่คาดผิด อ้างพฤติกรรมtriggerจาก
[PostgreSQL16 trigger overview](https://www.postgresql.org/docs/16/trigger-definition.html)
และ [CREATE TRIGGER](https://www.postgresql.org/docs/16/sql-createtrigger.html)

publishและjournalGCล็อกguardก่อนmetadataอื่น จึงตรวจepoch/floor/events
และเปลี่ยนREADY/headหรือprunefloorในshorttransactionเดียวได้
เมื่อถือguardแล้วใช้เฉพาะderivedmetadata/journal ไม่query/lockcandlesหรือทำDDL
claim/heartbeatที่ล็อกslot/jobต้องcommitก่อนเข้าหรือใช้publicationtransactionใหม่
ห้ามถือjob/demand rowแล้วรอguardย้อนลำดับ
งานbuildRRไม่ล็อกguardค้าง120s sourceingestionจึงไม่ต้องรอการคำนวณเต็มชุด
lock waitsของpublishยังอยู่ในbudgetที่แผนระบุ ไม่ถือว่าล็อกแล้วรอได้ไม่จำกัด

Maintenanceใช้freshtransactionกับ `begin_indicator_source_maintenance()`:
ล็อกsource root/currentpartitionsแบบACCESS EXCLUSIVEก่อนguard จากนั้นล็อกguard
และregisterMAINTENANCE จึงexpireheads/resetepochและTRUNCATE/DROP/DETACH/rebuild
ในtransactionเดียว ไม่เรียกresetepochที่ถือguardก่อนแล้วค่อยขอrelationlocks
ไม่upgradeWRITE scopeเป็นMAINTENANCEกลางtransaction; helperต้องrejectก่อนรอlock
ใช้staticrootlockเพื่อครอบleaf writesด้วย ไม่รับrelationname/SQLจากclient
DDLที่ยกเลิกต้องrollbackepoch/expiryพร้อมDDL; timeoutต้องคืนlocksและretryทั้ง
maintenance transactionตามนโยบายoperator ไม่ใช้partialDDLหรือretryในtransactionที่abort
roleตรวจmaintenanceเฉพาะmigrator ไม่มีgrantให้API/builder/market-data
revisionoverflowต้องresetepochแบบเดียวกัน ไม่wrapเลขหรือเทียบepochเก่าเป็นรุ่นใหม่
การทำDDLข้ามขั้นตอนนี้ไม่อยู่ในruntimeที่อนุญาต และต้องมีmaintenance regression

## Function hardening

Trigger/rollouttransition/globalclaim/heartbeat/checkpoint/release/reap/publish/failure/manualretry/GC
functionsที่ต้องใช้definer privilegesมีfixed search_pathที่ไม่มี
writable schemas, schema-qualifiedobjects, fixed typedarguments และไม่มีdynamic SQL
revokeEXECUTEจากPUBLIC แล้วgrantเฉพาะrolesที่ต้องใช้ ไม่มีdefiner entry point
ที่ให้clientเลือกSQL/role/metadata revision การpublishต้องตรวจlease/token/counts/proof
ก่อนเปลี่ยนhead; callerแก้READYหรือfenceเองผ่านdirectDMLไม่ได้
ตรวจข้อกำหนดdefiner functionsตาม
[PostgreSQL16 CREATE FUNCTION](https://www.postgresql.org/docs/16/sql-createfunction.html)

## ผลและการย้อนกลับ

role/migration/trigger/retention amendmentsตามแผนF-11/F-09ได้รับอนุมัติแล้ว
ใช้DBเป็นsource of truth; Redisไม่ใช่proofและRedisหายไม่ทำให้checkpointถูกปลอม
rollout/rollbackของreplicasต่างเวอร์ชันยึดS0..S5และR2-D1..D7ในแผนรอบ2ที่เดียว
additiveexpandไม่ติดstrictscope/journaltriggerทันที ต้องdrainlegacyF-09ก่อน
APIcompatibilityต้องverifyทั้งv1/v2ได้ก่อนมีv2issuance; ไม่มีsticky-routingproof
Builderclaim/publishอ่านและตรวจcontrol: รับงานได้เฉพาะPREPARING/PREPAREDที่
sourceproofREADY/retentionGRACEและprotocol/codecรองรับ; ผูกgeneration/claimกับ
rollout_epoch และpublishต้องepochเดิม ไม่resumeSTAGING/claimจากactivationเก่า
generation.build_rollout_epochเป็นประวัติattempt ไม่ใช่cursor.rollout_epoch:
READYที่publishจบก่อนdrainใช้ต่อในactivationใหม่ได้เมื่อcodec/formula/sourceproof/
freshness/expiryยังผ่าน ไม่มีการแก้immutableREADYหรือขยายexpiryเพื่อpromote
tokenใหม่ผูกactivecontrol epoch ส่วนtokenepochเก่ายัง409เสมอ
APIอ่านcontrolในREADONLYsnapshotเดียวกับcursor/generation/source; ไม่มีRAM/env
flagแทนDBmode ไม่ใช้controlrowเป็นแหล่งของsecretหรือcursorpayload

Transitionhelperรับexpectedmode/expectedepoch/targetmodeแบบtyped compare-and-set
เพิ่มepochเมื่อactivate/pause/re-enable ไม่รับrevision/fence/SQL/keyจากcaller
allowedgraphคือLEGACY→PREPARING→PREPARED→PAUSED, PREPARING→PAUSED
และPAUSED→PREPARINGเพื่อผ่านgatesใหม่; ห้ามPREPARED→LEGACYหรือPAUSED→PREPARED
โดยข้ามvalidation ไม่เปลี่ยนepochซ้ำเมื่อretryคำสั่งที่commitสำเร็จไปแล้ว
หลังtraffic/workerdrainเท่านั้น; ตรวจslotว่างและcompatiblepolicy/stricttriggercatalog
ตามstageก่อนtransition ไม่มีสิทธิ์ให้API/builder/F-09/PUBLIC เปลี่ยนmodeเอง
ถ้าต้องล็อกsourceguard/control/slotให้ใช้ลำดับเดียวกับpublish ไม่กลับลำดับ
DBตรวจไม่ได้ว่าoldbinaryที่offlineจะrestartหรือไม่ จึงต้องมีdeploymentinventory/
imageallowlistและoperatordrainตามrunbook ไม่อ้างว่าtransitionhelperพิสูจน์แทนได้
PREPARING/PAUSEDเก็บdecoder/control/schemaและverificationkeysให้validcursorคืน409
Rollbackหยุด/drainreadersและbuilderก่อนเปลี่ยนPAUSED/epochและบันทึกcutoff;
คงphysicalgrace/schema/key supportจนcutoff+6hและไม่มีactive reader จึงถอนstrict
triggers/derivedobjects/controlและคืนcleanupเดิมตามmaintenance protocolได้
คงcandlesและF-09jobsเดิมไว้; rollbackใช้compatibleimageก่อน ไม่routeoldAPIที่อ่านv2ไม่ได้
rollbackก่อนเคยactivate/ออกv2ไม่ต้องใช้v2supportwindow แต่ยังต้องdrain/stopwriters
และถอนstricttriggerด้วยmaintenanceถ้าติดตั้งแล้ว ก่อนคืนlegacyF-09/schema
controlหาย/unknownmode/protocolไม่รองรับต้องfailclosed APIไม่เลือกLEGACYจาก
envdefaultเอง และbuilderไม่claim; schema downgradeทำได้หลังprocessที่อ่านcontrolหยุด
batchfullscanเดิมยังไม่ผ่านperformance ไม่อ้างว่าrollbackแล้วF-11Completed
