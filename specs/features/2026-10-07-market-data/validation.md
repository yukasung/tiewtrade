# F-09 — Candle history Validation

**Pair-scope amendment — Approved 2026-10-15:** ใช้ F-38 เป็นเกณฑ์ปัจจุบัน:
runtime รองรับ BTCUSDT และ ETHUSDT เท่านั้น ส่วนผลตรวจจำนวนคู่เดิมด้านล่างเป็นหลักฐาน
historical และไม่ใช้รับรอง candidate หลัง F-38.

สถานะ: **Approved** — เจ้าของตอบ approve วันที่2026-10-07 พร้อม plan.md หลังแก้ไขและรีวิว; รวมNC-35 amendmentsที่เจ้าของอนุมัติเมื่อ2026-10-10
วันที่: 2026-10-07
requirements.md: Approved; NC-09/T-04 Closed

เกณฑ์amendmentF-09 NC-35อยู่ใน [R2-1..12](../2026-10-10-backend-indicators/performance-plan-v2.md)
เป็น **Approved** โดยเฉพาะlogical/physicalretention, sourcejournal/partitionproof,
permissions/migration/rollbackและregressioningestion; เกณฑ์amendmentได้รับอนุมัติ2026-10-10; ยังไม่ได้รันและไม่ถือว่าผลผ่าน
เพิ่มR2-L1..L6สำหรับsourcewrite/maintenance lockorder รวมbarrier testของF-09
preselect/upsertจริง, root/leaf, timeout/cancel/rollbackและscopeข้ามtransaction
เพิ่มR2-D1..D7ในแผนรอบ2สำหรับmixed-versionF-09cleanup/triggeractivation,
drainsourcewriters/readerและrollbackretention supportwindow; Approved/ยังไม่ได้รัน

## เสร็จหมายถึง

| เกณฑ์ | ข้อกำหนด | วิธีพิสูจน์ |
|---|---|---|
| V-1 | RQ1/3/18 | network/endpoint gates: โค้ดนอกvenuesไม่เรียกตลาด; factory/HTTPclientcompositionเฉพาะmarket-data entrypoint; ไม่มีsigned/key/withdraw/transfer/orders |
| V-2 | RQ2 | 5คู่/6timeframesที่อนุมัติใช้งานได้; unknownpair/timeframe/extrafieldsถูกปฏิเสธ fixedcodeโดยไม่ส่งHTTP |
| V-3 | RQ4 | OHLC Moneyquote/volume Quantitybase, unitscanonical, exactdecimalroundtripเกินfloatprecision; ใช้domainsเดิม ไม่เงียบround/truncate |
| V-4 | RQ4/6 | awareUTC/openinclusive/endexclusive; probe12fieldfixturesครบ6intervals; SITE/GLOBAL mappingทำตามexchangeInfo ไม่เดาจากคู่ที่ต่อกัน |
| V-5 | RQ6 | RESTทุกrowเป็นUNCONFIRMED แม้closeTimeผ่านแล้ว/มีแท่งถัดไป/อ่านซ้ำเหมือนเดิม; มีtestsสามสถานะและไม่downgradeCLOSEDจากlateUNCONFIRMED; partial-observation refresh ได้ OHLCV ใหม่จริงตามเกณฑ์30s/end_at โดยไม่ยก finality |
| V-6 | RQ5/16 | directDB/worker duplicate และconcurrentinsert/upsertได้แถวเดียวต่อseries/open_at รวมpartitionboundary; tupleunits/date/timeframeถูกcheck |
| V-7 | RQ7/8 | startup5x6 idempotent, เริ่มไม่เกิน1,000แท่งล่าสุดและไม่ก่อนas_of-365วัน; 1d1000rowsไม่ทำให้เก็บ1000วัน |
| V-8 | RQ8/14 | leap-year/calendar boundaryใช้timedelta365วัน ไม่date-year subtraction; GET/POST/ingest/cleanupใช้UTCcutoffเดียวกันและinject as_ofในpurecode |
| V-9 | RQ9 | explicitstartTime/endTimeทุกrequest; half-openmappingend_ms-1; 1000rows paginationต่อด้วยlastopen+interval ไม่skip/duplicateboundary |
| V-10 | RQ9/15 | no-progress/short/empty/out-of-order/conflictingduplicates/responseนอกrangeไม่ทำให้infinitefetchหรือwholewindowcompleteผิด |
| V-11 | RQ10/11/16 | forward ข้าม leading/interior/trailing gap แล้ว REPAIR fetch ช่วงที่ขาดและเติมสำเร็จจริง; ทดสอบ repair sweeps สูงสุด2รอบ/30s/60s, UNAVAILABLE+GAP_REPAIR_EXHAUSTED+120s eligibility เมื่อยังขาด; ไม่มี fakebars/volume0/PRE_LISTING หรือการอ้าง365วันครบ |
| V-12 | RQ12 | GETเป็นreadonly; POSTcoalesceเดิม202/complete200เฉพาะไม่มี refresh ที่ถึงกำหนดหรือค้าง; requestหลายuserไม่สร้างqueueหลายแถว; POST ใหม่ข้าม end_at เก็บ pending refresh watermark และทำ follow-up; ไม่ลดretryclock/steallease/เปลี่ยนleasedwindow |
| V-13 | RQ12 | GETreadwindowสูงสุด1000intervals/1000rows, POSTสูงสุด365วัน; invalidrange/naivetime/from>=end/outsidecutoff/limitoverflowเป็นfixed422 |
| V-14 | RQ12/16 | workerclaimSKIPLOCKED, commitก่อนHTTP; lease120s/token+generationfence; responseเก่าหลังleaseexpired/reclaimเขียนpageหรือcursorไม่ได้ |
| V-15 | RQ16 | failureระหว่างupsertpageกับcursor/status rollbackทั้งสอง; crashก่อน/หลังcommit restartcontinueได้; COMPLETE/PRESENTไม่เกิดก่อนdurablecommit |
| V-16 | RQ13 | actualtiewtrade_apiอ่าน/enqueueได้เฉพาะcolumnsกำหนด; directOHLC/claim/generation/delete/DDLไม่มีสิทธิ์; ไม่ใช้superuserพิสูจน์permissiondenial |
| V-17 | RQ13 | actualmarket_data CRUDเฉพาะmarkettables/metadata; ใส่wrongrole/superuser/bypassหรือUser/ScanSessionผิดชนิดต้องfailก่อนquery; user/secret/auditยังแตะไม่ได้ |
| V-18 | RQ14 | monthlyUTCpartitionsย้อนหลัง365วัน+ล่วงหน้า12เดือน/PKรวมpartitionkey/parent-childgrants; ไม่มีDEFAULTหรือruntimeDDL; missingpartitionfailfixedโดยไม่เขียนข้างทาง |
| V-19 | RQ14 | cleanupbounded10,000rows, expireddataไม่อ่านผ่านAPIแม้cleanupยังไม่ทัน; child/auditpartitionprotectionsและข้อมูลผู้ใช้คงเดิม |
| V-20 | RQ14/17 | migrationemptyupgrade/downgradeผ่าน; populateddowngradeปฏิเสธและrollbackversion/schema/dataครบ; ไม่มีrolegrantsหลุดไปsecret/user tables |
| V-21 | RQ15 | klinesส่ง published CallCost(1,0) แต่ candle-source limiter floor10 จอง10ก่อนHTTPในledgerเดียว; factoryเดิม default1 คงผลเดิม; headersobserveใช้maxไม่ลดspentผิด; delta5ไม่ใช่guaranteedtariff; NoRateLimitใช้เฉพาะfake |
| V-22 | RQ15 |429/418หยุดroundและpersistdeferทุกseriesในsource; Retry-Afterยาวกว่าต้องชนะbackoff; missingheaderunknown+120s; restart/APIenqueueไม่resetwait |
| V-23 | RQ15 | timeout/transientรวม3attemptsต่อ fetch unit (รวมครั้งแรก) ไม่ใช่ต่อ job/lease; unitใหม่หลังหน้าสำเร็จเริ่ม0; reclaim/POSTซ้ำไม่reset; 1→30s/2→60s/3→FAILED+120seligibility; malformed/permanentไม่autoretry ไม่มีsleep/HTTPretryในtransport |
| V-24 | RQ15/16 | ไม่เกิน4HTTPpages/round, timeout10s, fairseriesselection; HTTPนอกDBtransaction; queuedlongrangepaginateข้ามround ไม่โหลดทุกhistoryทันที |
| V-25 | RQ12/13 | GET/POSTauthenticated nonrenew/noTOTP/recovery, POSTCSRF; crossuserpublicdatasharedได้โดยไม่เปิดuser_id/credentials/privatejobpayload |
| V-26 | RQ17/18 | FakeVenue/recordedfixturesครอบsuccess/failure/concurrency/finality; normalpytest/E2E/Dockerไม่มีprivatekeyหรือliveexchangecalls |
| V-27 | RQ1/4/17 | OpenAPI/backendและgeneratedfrontendtypesตรงกัน byteidentical regeneration; readerrorsไม่มีrawSQL/DSN/secret/driverdetails |
| V-28 | ทุกRQ | backend/frontend/E2E/static/Docker checks ผ่าน; scopedspec/standardsreviewปิด findings; README/validation/audit/roadmapสะท้อนผลจริง |

## เทสต์ที่ต้องมี

- Partial-observation refresh: อ่านแท่ง1m/1dก่อน end_at แล้ว source เปลี่ยน OHLCV;
  POST ช่วงเดิมหลัง end_at ต้อง202 แม้ coverage PRESENT; worker อัปเดตแถวเดิมแบบ exact
  Money/Quantity และ GET เห็นค่าใหม่แต่ finality ยัง UNCONFIRMED
- Refresh boundaries: ทดสอบก่อน30s/ที่30sขณะ interval ยังเปิด, ที่ end_at,
  HTTP เริ่มก่อน end_at แต่ตอบหลัง end_at และกรณี observation เริ่มหลัง end_at แล้ว
  ไม่ refresh ซ้ำเพียงเพราะ UNCONFIRMED; GET ไม่มี enqueue และส่งเวลาของแถวเดิมตามจริง
- Refresh recovery: POST ซ้ำหลายผู้ใช้, restart, lease reclaim และ late worker
  ไม่ reset frozen refresh_as_of/cursor/backoff หรือเขียนทับ observation ใหม่;
  crash ระหว่าง OHLCV/timestamps/progress ต้อง rollback ทั้งชุด
- Refresh during active work: อ่านแท่งก่อน end_at แล้วหน่วงงานด้วย controlled barrier;
  ส่ง POST ช่วงเดิมหลัง end_at ขณะ RUNNING ต้องเก็บ refresh_requested_at ใหม่และคืน202
  active refresh_as_of/cursor ไม่เปลี่ยน; หลังจบรอบต้องทำ follow-up ได้ OHLCV ใหม่จริง
  โดยไม่ต้องให้ผู้ใช้ POST ครั้งที่สาม และยัง UNCONFIRMED
- Refresh completion race: บังคับทั้ง POST-before-completion และ completion-before-POST
  ด้วย barriers; ไม่มี lost watermark/COMPLETE ก่อนตอบสนองคำขอที่รับไว้
  รวม POST หลายผู้ใช้เป็นแถวเดียว, restart/reclaim ระหว่างสอง sweeps และ stale worker write
- Refresh follow-up bounds: observation ใหม่ที่ตอบสนอง pending watermark อยู่แล้วไม่ fetch ซ้ำ;
  คำขอก่อนเกณฑ์30sไม่สร้าง follow-up, คำขอที่เข้าเกณฑ์ใหม่เก็บได้, ไม่มี POST ใหม่ไม่วนเพิ่ม
  follow-up ใช้งบ4pages/round/fairness เดิม ไม่ reset gap repair budget/backoff;
  failure คง requested watermark และไม่ advance served watermark หรือเลื่อน eligibility ให้เร็วขึ้น
- Refresh failure: empty/partial response ไม่ลบแถวเดิม/ไม่เลื่อน last_checked_at ของแท่งที่ไม่ได้รับ;
  หมด3attemptsเป็น FAILED+120s, permanentไม่retry, Retry-After ชนะ;
  GET ยังคง coverage PRESENT ได้แต่แสดง refresh failure และเวลาเดิม
- Refresh scope: ครบทั้ง gap repair และ refresh ใน window เดียว, งบรวม4pages/round,
  scanไม่เกิน1,000slotsต่อหน้า, fair selection, retention expiry และ CLOSED ไม่ถูก downgrade
  ทดสอบ COMPLETE เฉพาะไม่มี gap/refresh ค้าง และไม่มี sweep ไม่จบเมื่อ clock เดินต่อ


- Puretypes/window: concreteUTCvaluesและproperties intervalsteps/cutoff/idempotentgapmerge,
  เงิน/volume highprecision/invalidunits/nonfinite/เกินF-02limitsไม่เปลี่ยนกฎปัดเดิม
- Retry unit: งานอย่างน้อย5หน้าต้องสำเร็จข้ามหลาย rounds; หน้า1–3สำเร็จไม่กินงบหน้า4
  จำลองหน้า4 timeoutสองครั้งแล้วสำเร็จครั้งที่3 จากนั้นหน้า5เริ่ม count0;
  ตรวจ unit identity/count/cursor จริง และงบรวมไม่เกิน4attemptsต่อround
- Retry exhaustion: unit เดิมล้ม3ครั้งเป็น FAILED+120s; POST ก่อน eligibility,
  lease reclaim/restart/desiredwindow ขยาย/retention clamp ไม่ reset count;
  explicit request หลัง eligibility reset ได้โดยคง progress/repair_pass เดิม
- Retry crash: crash หลังจอง attempt ก่อน HTTP และหลัง HTTP ก่อน commit ต้องไม่คืน attempt;
  count3 ที่ไม่มี durable success ต้อง FAILED; commit rows/progress/ปิด unit เป็น atomic
  และ stale worker ห้ามใช้ unit/generation เดิมเขียนผลหลัง reclaim
- Phase retry: partial REFRESH คง unit/count แม้บันทึกบางแท่งแล้ว; valid empty REPAIR
  เลื่อน cursor และ gap เดิมเปิด unit ใหม่ได้เฉพาะ sweep ถัดไปภายในงบ2sweeps
  ตรวจ malformed/permanent หยุดทันที, local rate-limit นับ attempt ตาม policy,
  source Retry-After/backoff ไม่ถูกลดจาก unit ใหม่หรือการเปลี่ยน phase
- Reservation policy: spy ที่ transport/guard เห็น klines CallCost(weight=1, orders=0),
  แต่ limiter ledger เพิ่ม10ครั้งเดียว; exchangeInfo cost10 ยังเพิ่ม10 ไม่ใช่20
  floor default1 คงผลเทสต์เดิม; cost ที่สูงกว่า floor ใช้ cost จริง ไม่ถูกลดลง
  invalid floor (bool/ศูนย์/ติดลบ/non-integer) ถูกปฏิเสธ และ orders>0 ยังถูกปฏิเสธ
- Reservation boundaries: ทดสอบทั้งสอง windows, wait time ที่ใช้ reserved_weight,
  budget เกิน window limit/no HTTP, และหน้าต่างที่สองปฏิเสธไม่ทิ้ง partial reservation
  header ต่ำกว่าไม่คืนงบ/สูงกว่าเพิ่มเฉพาะส่วนต่าง, HTTP failure ไม่คืนงบก่อนหมดอายุ
  ตรวจ factory wiring ว่า candle ใช้ floor10 และ factory ราคา/บัญชีเดิมคง default1
- Venuecontract: knownrecordedfixtureและFakeVenueจากชนิดกลาง; HTTPmockเท่านั้นในCI
  primarypublicprobe17ครั้งเป็นresearch evidence ไม่ใช่normaltest dependency
- Storage/actualroles: directSQLuniqueness/grants/childpartitions, expiredlease,
  latecompletionสองworkers, overlappingrequestunionและpartialpage rollback
  ใช้controlledbarriers/events แทนsleepเพื่อให้race testทำซ้ำได้
- Gap repair: FakeVenue ครั้งแรกคืนแท่งที่ t0/t2 แต่ขาด t1; หลัง forward cursor ผ่าน t2
  source คืน t1 ได้ ให้ worker ซ่อมโดยไม่ต้อง POST เพิ่ม แล้วตรวจแถวจริง/coverage PRESENT
  รวมกรณี leading/trailing gap และหลาย gap ข้ามหน้า โดยอ่านทีละไม่เกิน1,000 slots
- Gap exhaustion: valid empty/partial response ทั้ง2 repair sweeps ต้องเดินผ่าน gap อื่นได้
  จบเป็น UNAVAILABLE พร้อม gap/checked_at/reason และ eligibility120s; เมื่อขอใหม่หลังเวลา
  source มีข้อมูลแล้วต้องเติมได้ ไม่แปล UNAVAILABLE เป็นการไม่มีข้อมูลถาวร
- Repair recovery: crash ก่อน/หลัง page+repair_cursor commit, lease reclaim, late old worker,
  POST ซ้ำ/desiredwindow ขยายระหว่าง repair ต้องไม่สูญเสีย gap/reset pass/ลด retry clock;
  transient failure retry active_fetch_window เดิมและหมดงบเป็น FAILED ไม่เลื่อน cursor
  ทดสอบ permanent failure ไม่วนต่อ และ retention ที่เลื่อนผ่าน gap ระหว่าง restart
- Repair budget: ทั้ง forward/repair ใช้งบรวม4pages/round และ fair selection เดิม;
  ตรวจ30s/60sด้วย injected clock, Retry-After ที่ยาวกว่าชนะ และ COMPLETE หลัง durable coverage ครบเท่านั้น
- API: routesจริงผ่านmiddleware ไม่เรียกhandlerลัด; sessionage/CSRF/inputbounds,
  200/202/422 semantics และcoverage/finalityไม่ถูกผูกเป็นสถานะเดียวกัน
- E2E: browserauth → missingGET → POSTrequest → actualworker+FakeVenue → GETstoredrows,
  failedpage/gap/retry/coalescing และดูว่าGETไม่เติมqueueเอง; ไม่มีUIกราฟใหม่
- Regression: F-02money, F-03roles, F-04auditpartitions, F-05/F-06auth,
  F-07keyverification, F-08logout/cache/keyfeedback ยังผ่าน

## ตรวจด้วยมือ

1. รันbootstrap/migrationบนdisposableDB; CLIworker--onceกับFakeVenue
2. อ่านmissingwindowผ่านAPI ตรวจrequestedrange/coverage/finality
3. ส่งrequestซ้ำสองครั้ง ตรวจcoalescedjob; workerดึงpageแล้วGETมีข้อมูลจริง
4. จำลองsourcegap/timeout/429/partitionmissing ตรวจfixederror, wait, no fakebars
5. เลื่อนinjectedclockเกิน365วัน ตรวจread/ingest/cleanupcutoffตรงกัน
6. ตรวจroleSQLpermissionsและดูว่าข้อมูลauth/key/auditในDBtestไม่เปลี่ยน

ไม่จำเป็นต้องใช้บัญชีBinance TH/APIkeyจริงหรือส่งคำสั่งซื้อขายเพื่อผ่านvalidation
การตรวจprimarypubliccontractเพิ่มก่อนdeployถ้าตลาดเปลี่ยนให้บันทึกวัน/params/ข้อจำกัด
ไม่สรุปcost/finalityจากresponseเดียวแล้วเปลี่ยนpolicyเงียบ ๆ

## ด่านที่ต้องเขียว

Backend: Ruff lint/format, mypy, import-linter, fullpytest พร้อมdisposablePostgreSQL
Frontend: ESLint, TypeScript, fullVitest, productionbuild และPlaywrightE2E
Generatedcontract: exportOpenAPI/typesแล้วbyteidenticalรอบสอง
Docker: Linuxbuild, API/UIproxyhealth, CLI--onceFakeVenue smoke
Review: source/protocol/storage/roles/transactions/races/idempotency/retention/retry

## ข้อจำกัดที่ต้องระบุในการส่งงาน

REST finalityยังUNCONFIRMED, quotaobserverไม่ใช่shared-IP reservationข้ามprocess,
ไม่รับรองประวัติ365วันทุกคู่, partitionmigrationสร้างล่วงหน้า12เดือนและไม่มีruntimeDDL,
deployment/scheduler/rollingpartitionmaintenanceเป็นF-31; F-10/F-11/F-12ยังไม่implemented

## ผลตรวจ implementation วันที่2026-10-07

สถานะผลตรวจ: **Passed** — issue1–5แก้แล้ว; final deep review APPROVED และ backend/frontend/E2E/contract/Docker ตรวจใหม่ผ่านครบก่อนส่ง PR
ผลผ่านด้านล่างเป็นประวัติการตรวจ implementation ก่อน deep review; ยังไม่ commit/push/merge

- Backend full suite: **1,618 passed**, 1 live-contract test deselected ตาม policy; 99.31s
- Ruff lint/format, strict mypy (220 files), import-linter (6 contracts): ผ่าน
- Frontend ESLint/TypeScript, Vitest **113 passed**, production build: ผ่าน
- Browser E2E บนฐานใหม่ที่ว่าง: **9 passed**, 26.0s รวม market-data request/worker/GET
- OpenAPI/types regenerate รอบสอง: SHA checks byte-identical ทั้งสองไฟล์
- Docker Linux build, API/UI proxy health: ผ่าน; CLI --once กับ FakeVenue commit **1,000 observations**
- Spec/standards reviews: findings ที่พบแก้และมี regression tests แล้ว; ไม่มีข้อค้างที่ยืนยันได้

รายละเอียด coverage, findings และข้อจำกัดอยู่ใน
[validation audit](../../reviews/2026-10-07-f09-market-data-validation-audit.md)
ผลนี้มาจากการรัน F-09 ใหม่ ไม่ใช้ผล F-08 แทน

Follow-up issue1: regression ขยายช่วงซ้าย/ขวา/ทั้งสองก่อน repair pass2 จบ
ยืนยัน UNAVAILABLE/งบเดิม/120s/leasedwindow และการเติมช่วงรวมหลังคำขอใหม่ที่ถึง eligibility
Relevant tests **77 passed**, 17.40s; Ruff/format/mypy/import checks และ scoped re-reviews ผ่าน

Follow-up issue2: POST ตรวจ presence/refresh ด้วย metadata aggregate หนึ่ง query ต่อ checkpoint
มีสอง checkpoints ก่อน/ภายใต้ demand lock; ไม่อ่าน OHLC หรือสร้าง Candle/Money เพื่อวางงาน
Actual query-count ของ365วัน/1mและคำขอซ้ำผ่าน พร้อม parity ของ refresh/half-open slots
Relevant tests **91 passed**, 18.15s; Ruff/format/mypy/import checks และ scoped re-reviews ผ่าน

Follow-up issue3: batch write1,000แท่งใช้5SQL callsรวม fence/clock แทน3,002callsเดิม
ตรวจ distinct partitions และ locked existing rows เป็นชุด แล้ว upsert ด้วย bound parameters
precision/version ordering/CLOSED/conflict/atomic rollback คงเดิม
Relevant tests **96 passed**, 11.29s; Ruff/format/mypy/import checks และ scoped re-reviews ผ่าน

Follow-up issue4: retention_cutoff แปลง referenceเป็น UTC ก่อนหัก timedelta365วัน
read/initial/coalescing/ingest/write/cleanup ใช้ร่วมกัน; cleanup bind cutoff แทน calendar-day interval
Actual DB tests ใน UTC/New York/Paris ข้าม spring/fall DST เก็บ boundary และข้อมูลใหม่กว่าได้ถูกต้อง
Relevant tests **103 passed**, 11.61s; Ruff/format/mypy/import checks และ scoped re-reviews ผ่าน

Follow-up issue5: `_window` แปลง OverflowError เฉพาะการสร้างช่วงจาก input เป็น ValueError
GET/POST จึงตอบ fixed422 `INPUT_REJECTED` เมื่อ timezone offset ทำให้ UTC เกินปี1–9999
Authenticated API regression4กรณีแดงก่อนแก้และผ่านหลังแก้; ไม่เปลี่ยน auth/CSRF หรือ retention
Related core/venue/storage/worker/API tests **141 passed**, 12.63s; Ruff/format/mypy/import checks ผ่าน
มี inherited Starlette deprecation warning1รายการ; ไม่มี commit/push และยังไม่ใช่ผล full suite หลังแก้ทั้งหมด

Backend final verification หลังแก้ issue1–5: **1,652 passed**, live-contract deselected1
ตาม policy, inherited deprecation warnings3, 94.50s บนฐานทดสอบใหม่
Ruff lint/format239files, strict mypy221files, architecture/import-linter6contracts ผ่าน
Frontend/E2E/generated contract และ final review ยังต้องตรวจใหม่ก่อน merge; ไม่มี commit/push

Frontend final verification หลังแก้ issue1–5: lint/type checks ผ่าน, Vitest **113 passed**
13suitesใน4.36s และ production build145modulesผ่านใน421ms
E2E **9 passed**, 44.5s บนฐานใหม่ที่ว่าง พร้อม API/frontend servers ใหม่และ FakeVenue workers
Generated contract และ final review ยังต้องตรวจใหม่ก่อน merge; ไม่มี commit/push

Generated API contract final verification หลังแก้ issue1–5: exportOpenAPI/types2รอบ
SHA256ทั้งสองไฟล์ตรงกับ snapshotก่อนตรวจ (byte-identical) และไม่มี generated drift
TypeScript checks และ contract gate **2 passed** (positive/negative canary), 3.51s
ข้อ1–3backend/frontend/E2E/contractตรวจใหม่ผ่านแล้ว; เหลือ final review ไม่มี commit/push

Final review: Standards และ Spec reviewers ไม่พบ actionable findings; ผล **APPROVED**
Docker final verification หลังแก้ issue1–5: Linux images build/migrate/APIhealth/UIproxyhealthผ่าน
actual CLI `--once` ผ่าน FakeVenue บันทึก1,000observations ไม่มีตลาดจริง
ครบทุกด่าน local validation; เจ้าของสั่งดำเนินการ commit/push/PR/CI/merge ต่อ
