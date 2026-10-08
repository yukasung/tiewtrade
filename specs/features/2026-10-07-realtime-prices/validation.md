# F-10 — รับราคาเรียลไทม์และต่อกลับเมื่อหลุด — Validation

สถานะ: **Approved** — เจ้าของตอบ approve วันที่2026-10-07 พร้อมplan.mdฉบับแก้ตามNC-26/NC-27
วันที่: 2026-10-07

เอกสารนี้กำหนดเกณฑ์ก่อนเขียนโค้ด; ผลlocalfunctionalvalidationล่าสุด2026-10-07
ผ่าน V-1..V-32 ตาม [final-validation](../../reviews/2026-10-07-f10-realtime-prices/final-validation.md)
public fixturesเพียงอย่างเดียวไม่ใช่ผลผ่านimplementation; externalCIยังไม่รัน

## “เสร็จ” หมายถึง

| รหัส | เกณฑ์ | วิธีตรวจ | Requirements |
|---|---|---|---|
| V-1 | ตลาดถูกเรียกผ่าน venue และเฉพาะ public TH ไม่ใช้ key/secret/บัญชี | import/AST network/vocabulary gates + fake transport assertions | RQ-1/2/3 |
| V-2 | backend/UI รับเฉพาะ5คู่; client ไม่ทำ arbitrary upstream subscription | GET/WS input, forged symbols, subscribe-count tests | RQ-3 |
| V-3 | เก็บ/ส่งราคา exact decimal string, หน่วย USDT และสองเวลา UTC | fixture roundtrip ผ่าน Money/DB/API/DOM; timezone offset tests | RQ-4 |
| V-4 | อายุ10sผ่าน; 10s+1µsเก่า; received_at/E/pongใหม่ไม่รีเซ็ตอายุ | controlled clock + property tests | RQ-4/6 |
| V-5 | ไม่มี trade ใหม่ → STALE แยกจาก socketหลุด; เวลาmissing/future/malformedไม่READY | core/adapter/API tests | RQ-5/6 |
| V-6 | upstream known disconnect → backendไม่พร้อมทันที; เว็บรับ snapshotแล้วแสดงผล ณเวลาserver พร้อมdeliverystatus | fake disconnect worker/PG/API/DOM ตรวจreference timeและไม่อ้างcurrentREADY | RQ-5/8 |
| V-7 | ack/handshakeไม่พร้อม; snapshotผ่าน generationใหม่และราคาใหม่พอจึงพร้อมรายคู่ | delayed/failed snapshot fake feed | RQ-8 |
| V-8 | snapshotเก่า, duplicate, tradeย้อนลำดับ และ callbackเก่าไม่ทับใหม่ | partial-order/ambiguity/recovery casesด้านล่าง; ห้ามnumeric-IDtie-breaker และarrivalorderเลือกwinner | RQ-9 |
| V-9 | reconnectมีbackoff+jitter+cap; เคารพRetry-After; attemptsไม่resetจากack | injected sleep/random; 429/418/timeout/protocol fixtures | RQ-7 |
| V-10 | explicit subscribe ack ต้องผ่านก่อน deadline5s; timeoutเข้าbackoffแม้pongผ่าน; frame limits/ping/rotationทำงาน | fake WSS server + controlled timers และ ack casesด้านล่าง ไม่รอ24h | RQ-7/8 |
| V-11 | migration/grantsตามactual roles; market-dataแตะuser/secretไม่ได้ APIเขียนราคาไม่ได้ | disposablePostgreSQL, actual runtime sessions, upgrade/downgrade | RQ-1/2/10 |
| V-12 | workerสองตัวมีupstream writerเดียว stale generation/leaseเขียนไม่ได้ | concurrent worker takeover test; pause writerหลังอ่านleaseก่อนcommit | RQ-8/9/10 |
| V-13 | crashไม่มีcloseไม่ค้างREADY หลังlease5s; startupไม่พร้อมจนกู้จริง | terminate fake producer, restart และAPI read | RQ-8/10 |
| V-14 | DB rollbackไม่publish; publishพลาดไม่ย้อนPG; Redisหายไม่ใช้cacheREADY | actual PG/Redis fail/restart test | RQ-10 |
| V-15 | subscribe-before-snapshot, missed message และ periodic reconciliationไม่สูญlatest revision | publishระหว่างsubscribe/read, Pub/Sub loss, multi-API broadcaster | RQ-9/10 |
| V-16 | HTTPและWSใช้จุดตรวจตัวตนเดียว ไม่มีunclassified WSผ่าน | route inventory/ASGI guard tests; ปิดsocketก่อนacceptเมื่อไม่มีsession | RQ-11 |
| V-17 | WSไม่renew; หมดidle/absoluteหรือrevoke → ปิด4401 ภายในรอบตรวจ1s | actual session DB, update/deleteหลังaccept; assert deadlineไม่เปลี่ยน | RQ-11 |
| V-18 | Originผิด/ไม่มีถูกปฏิเสธ; URL tokenใช้ไม่ได้; authDBล่มไม่ส่งข้อมูลต่อ | handshake integration, configured dev proxy, forbiddenOrigin | RQ-11 |
| V-19 | WSframesตรงPricesView/GETschema; เงินเป็นstring revisionไม่ล้นJS; ไม่มีproof/request command | Pydantic validateทุกresponse + TSdecode/generated contract; application messageปิด1008และframe≤256bytes | RQ-4/12 |
| V-20 | clientช้า queuebounded/close1013 ไม่ทำworker/clientอื่นช้า; cleanupไม่leak | blockedsend/pushslot1/canceledtasks/connections/timers ไม่มีcorrelatedresponsequeue | RQ-12 |
| V-21 | HTTPช้ากว่าWS/socketเก่าไม่ย้อนcache; logoutสลับidentityปิดsocketและล้างcache | deferredfetch/messages + AccountSession componenttests | RQ-9/12 |
| V-22 | deliveryfailureที่ตรวจพบแสดงwarning/statusพร้อมsnapshotค้าง; reconnectรับfullviewใหม่ | JScontrolledscheduler + realbrowseroffline/close/heartbeatdeadline; ไม่อ้างOSsleep detectionครบ | RQ-5/12 |
| V-23 | เว็บแสดงreported status ณserver_timeเสมอ ไม่อ้างcurrentfreshness; backendตรวจ10sด้วยเวลาใหม่ | delayedHTTP/WS/sleep/clockchange/ordering casesด้านล่าง; ไม่มีbrowserclockcapability gate | RQ-5/6/12/13 |
| V-24 | serveralertครบ60s/59.999s/restartถูกต้อง; deliverywarningทันทีที่ตรวจพบและรอsnapshotใหม่ก่อนclearing | durablePGinterval + offline/close/heartbeat/reconnect/UI testsตามcasesด้านล่าง ไม่มีlocal60sclock | RQ-15 |
| V-25 | ราคาค้างมีเวลา/สถานะ/เหตุผล; missingไม่แสดง0; warningไม่พึ่งสีและไม่อ่านทุกtick | Thai/English UItests + keyboard/screenreader markup + screenshot360/1440 | RQ-5/15 |
| V-26 | fullflow fakeproducer→PG→Redis→API→browser ใช้กระบวนการและrolesจริง | Playwright E2E ไม่mock APIquote/ไม่ยิงตลาด | RQ-14 |
| V-27 | F-09 ingestion/retention/coverage และ auth/TOTP/APIkeys/account ไม่regress | existingfullsuite + concurrentcandle/price worker test | scope |
| V-28 | ไม่มีLive/ออเดอร์/บอทใหม่; เว็บreportedREADYไม่ใช้อนุญาตexecution | scope/routes/grants review; backendconsumerอ่านราคา/leaseและreferenceเวลาใหม่ก่อนreadiness | RQ-13 |
| V-29 | per-user3leasesบังคับข้ามsession/device/APIprocess; process100/pending16ไม่มีwaitingqueue | concurrentactualPGclaims+twoAPIworkers และboundary100/101,16/17; servergeneratesownerID | RQ-11/12 |
| V-30 | handshakeglobal200/60s,IP30/60sก่อนsessionlookup; userbucketburst6/refill10sนับทุกauthenticatedattempt | actualRedisLua/controlledtime+PGtokenbucket; rejectedacceptไม่rollbackquota; backendDBlookupspy | RQ-11/12 |
| V-31 | ทุกexitpathคืนquota; crashคืนslotเมื่อ5sหมด; oldownerrenew/releaseไม่กระทบnewowner | cancel/failedaccept/disconnect/logout/revoke/sendtimeout/schemaerror/restart+CASrace/RLSactualroles | RQ-11/12 |
| V-32 | WSworkไม่กินinteractiveHTTPpool; DB/Redistimeoutsfailclosed ไม่มีunboundedtasks/keys | pool_size3/overflow0,task/queuecount,load/contentiontestและlimitsคำสั่งRedisACL; coreHTTPยังผ่าน | RQ-11/12 |

## ตัวเลขและคุณสมบัติที่ต้องมี

F-10 ไม่เพิ่มสูตรPnLหรือคำนวณเงิน แต่ต้องพิสูจน์ exact parsing/roundtrip
ใช้ราคา `83348.47000000` และ `0.08892000` จาก public fixtures
กับค่า precisionสูงสุดที่ Money/DB domainรองรับ; ต้องไม่เกิดการปัดเงียบ
หน่วยผิด/price0/ติดลบ/เกินprecision → reject; ไม่coercefloat

ใช้ hypothesis:
- permutationของobservationsที่เวลาแตกต่างกันหรือราคาเดียวกันในbucketเดียว
  ให้scalarprice/timeล่าสุดเดียวกัน โดยไม่ใช้numericIDจัดลำดับ
- equal-time/different-priceในbucketล่าสุดให้ORDER_UNCONFIRMEDทั้งสองลำดับ
  และquoteใหม่ไม่ล้างlatchเองก่อนrecoveryผ่าน
- duplicateไม่เปลี่ยนwinner/อายุ แม้received_at/Eต่าง
- acceptedrevisionไม่ลดลง; oldgenerationเขียนไม่ได้
- ageเพิ่มเมื่อnowเพิ่มโดยไม่มีtradeใหม่; offsetเวลาแทนinstantเดียวกันให้ผลเดียว
- string→Money→DB→API roundtripให้ค่าและหน่วยเดิม

expected answersในเทสต์ต้องคำนวณจากเวลาตั้งต้นและค่าfixtureเอง
ไม่เรียกฟังก์ชันที่กำลังทดสอบเพื่อสร้าง expected
เพิ่มfuturetime/clockย้อน tests ให้failclosed ไม่ประกาศfresh

## V-29..32 — Admission และ resource bounds

- เปิด3connectionsของuserเดียวจากต่างsessionและสองAPIprocess แล้วคำขอที่4
  ต้องไม่accept; userอื่นมีquotaแยก; ไม่มีการลบsocketเดิมเพื่อให้socketใหม่แย่งช่อง
- user cap คงที่3: runtime ใช้ USER_CONNECTION_SLOTS=(1,2,3) ที่เดียว;
  settings/schema/config documentation ไม่มีตัวเลือก override เพดานต่อผู้ใช้
- actual-DB contract: slots1/2/3 เขียนได้เมื่อข้อมูลอื่นถูกต้อง; slots0/4
  ถูก CHECK ปฏิเสธ ใช้ runtime slots เทียบ constraint ที่ migration สร้างจริง
  โดย migration ไม่ import runtime constant; คำขอที่4ยังถูกปฏิเสธข้ามAPIprocess
- barrierพร้อมกันที่slotclaim: มีunexpiredleasesได้ไม่เกิน3 ไม่ใช่COUNTแล้วraceINSERT
- ต่อprocess: pending+acceptedรวม100, pendingไม่เกิน16; เกินcapต้องreject
  ก่อนDBlookup ไม่มีtasksรอsemaphoreเพิ่มไม่จำกัด
- globalattemptที่201ในwindowเดียวกัน/IPattemptที่31ต้องไม่lookupsession;
  ดักOrigin/sessionผิดก็ยังถูกนับเมื่อผ่านlocaladmission; ตรวจboundarywindowและTTL
- sourceIPจากpeer/trustedproxyที่ตั้งค่าเท่านั้น; forgedX-Forwarded-Forเปลี่ยนquotaไม่ได้
- Redisล่มหรือscripttimeoutปฏิเสธnewWS; Redisrestartไม่ทำให้PGactiveusercapหาย
  globalหมดแล้วส่งunknownIPจำนวนมากต้องไม่สร้างIPkeysเพิ่ม
- userbucketburst6และrefill1/10sใช้โค้ดเดิม; failedslotclaim/failedacceptไม่คืนtoken
  ไม่แก้bucket/login/TOTP/APIkeyเดิม; cross-userRLSอ่าน/เขียนslotไม่ได้
- failedaccept/close/cancel/revoke/timeoutทุกจุดต้องคืนlocalcountและPGslot
  cancellationระหว่างclaimกับacceptมีfinally; crashrowsreuseเมื่อDBleaseหมด
- pauseoldsocketจนslotหมดและnewsocketclaim แล้วoldrenew/releaseต้องno-op
  expiredownerไม่ส่งframe/ไม่ต่ออายุด้วยidentityเก่า; restartAPIไม่resetusercap
- allWSrevalidation/renewใช้coordinatorเดียว; messageburstไม่สร้างauthqueryต่อติก
  บังคับcoordinator≤2DBtransactions/s/socket และ sharedreads≤10/s/process
  ไม่มีinboundsnapshotcommands; แยกpool3/overflow0/timeout≤500ms
  ไม่อ้างperformanceผ่านจากสูตรupperbound ต้องloadtestพร้อมinteractiveHTTPจริง
- slowdownDB/lock/Redisและslowreceiverไม่สร้างunboundedwaiters; authsession
  หมดอายุ/revokeยังปิดในรอบ1s; ถ้าตรวจไม่สำเร็จต้องปิดfailclosed
- migrationupgrade/downgradeเพิ่ม/ลบเฉพาะconnectiontable/bucketใหม่
  oldbuckets/tokenbalanceและcandledataคงเดิม; market-dataไม่มีสิทธิ์slot/admissionkeys

## V-10 — Subscription acknowledgement deadline

ใช้ fake WSS server และ controlled monotonic clock; ไม่ยิงตลาดจริง
นับ deadline5s ก่อนส่ง SUBSCRIBE รวมเวลารอ limiter/send ไม่ใช่หลัง send เสร็จ

| กรณี | Expected |
|---|---|
| success ack ตรง id/generation ตรวจเสร็จก่อน5s | เริ่ม REST recovery หนึ่งครั้ง; ack อย่างเดียวไม่ READY |
| handshake สำเร็จและ pong ต่อเนื่อง แต่ไม่มี ack | ที่5s invalidate attempt และ FeedDisconnected/SUBSCRIPTION_ACK_TIMEOUT; ไม่เริ่ม REST; ปิดแล้วเข้า backoff |
| มีแต่ ack ผิด id หรือ trade frames ต่อเนื่อง | ไม่เลื่อน deadline; timeout เดิมและไม่มี unbounded buffer |
| limiter/send ค้าง | deadline รวมยัง5s; cancel งานค้าง ไม่เริ่มนับใหม่หลัง send |
| ack ตรวจเสร็จตรง5sหรือหลัง5s รวม race กับ timer | timeout ชนะ; ไม่เริ่ม recovery/READY และ failure transition ไม่ซ้ำ |
| ack ก่อน deadline แล้ว ack ซ้ำ | recovery หนึ่งครั้ง ไม่ reset retry attempt หรือสร้างงานซ้อน |
| ack เก่ามาหลัง timeout หรือเมื่อ generation ใหม่เริ่มแล้ว | ทิ้ง callback; ไม่ปลด gate หรือเริ่ม recovery ของรอบใหม่ |
| ack error หรือ malformed payload | protocol-error path/พัก30s ไม่ถือว่า subscribe สำเร็จ |
| peer ไม่ยอมปิดหลัง ack timeout | cleanup จำกัด5s; งานรอถูกยกเลิกและเข้าสู่ backoff โดยไม่มี task/connection leak |
| ack timeout หลายรอบโดย handshake/pong สำเร็จทุกครั้ง | retry attempts เพิ่มตามเดิม เคารพ jitter/cap; ไม่รอ23h50mและไม่ retry storm |

ตรวจ boundary ด้วยเวลาที่กำหนดเอง รวม just-before/at/after deadline
และตรวจ failure_code โดยไม่บันทึก raw payload; V-9 ยังบังคับนโยบาย retry เดิม

## V-8 — ลำดับที่พิสูจน์ได้และ ambiguity recovery

| กรณี | Expected |
|---|---|
| Tใหม่กว่าแต่IDตัวเลขน้อยกว่า; Tเก่ากว่าแต่IDมากกว่า | เลือกTใหม่กว่า ไม่ใช้numericalIDตัดสิน |
| Tเท่ากัน/ราคาต่าง/IDเพิ่ม ลด หรือสลับarrivalorder | ORDER_UNCONFIRMEDทั้งสองลำดับ; ไม่เผยquoteใหม่เป็นconfirmed/READY |
| Tเท่ากัน/ราคาเท่ากัน/IDต่าง หรือE/received_atเปลี่ยน | ราคา/อายุเดิม ไม่อ้างว่าเป็นtradeเดียวกันเพียงเพราะราคาเท่ากัน |
| STREAMduplicateIDในscopeที่เทียบอยู่แต่เวลา/ราคาเปลี่ยน | VENUE_PROTOCOL/RECOVERING ไม่เลือกpayloadที่มาทีหลัง |
| RESTidและWStต่างกันสำหรับT/ราคาเดียวกัน | ไม่rejectด้วยIDและไม่ใช้IDข้ามท่อเป็นproof; scalarpriceเปรียบเทียบด้วยT/amount |
| ambiguityเกิดในdirtybatchก่อนflush | latch/invalidationต้องคงอยู่ ไม่ถูกcoalesceเหลือwinnerปลอม |
| RESTrequestเริ่มก่อนพบlatch แล้วตอบหลังพบlatch | ไม่resolve แม้HTTP200และpriceสด |
| RESTrequestใหม่ตอบTเก่ากว่าหรือเท่ากับlatch | ไม่resolve ไม่มีnumericIDหรือarrayorderข้ามท่อช่วยทำให้พร้อม |
| RESTarrayมีIDไม่เรียงตัวเลขแต่เรียงoldest-firstตามสัญญา | เลือกสมาชิกท้าย ไม่sort/maxด้วยID |
| RESTใหม่Tมากกว่าlatch แต่เท่ากับSTREAMcandidateที่ราคาต่างกัน | คง/ขยายlatch ไม่READY |
| RESTใหม่Tมากกว่าlatch และmergeไม่มีambiguity; winnerสด | transactionเดียวล้างlatch/ตั้งreconciled/revision แล้วจึงpublishREADY |
| STREAMTใหม่หลังlatchโดยRESTยังไม่ผ่าน | เก็บcandidateได้ แต่ยังไม่READY |
| restart/reconnectขณะlatchค้าง | อ่านlatchPGเดิม ไม่ล้างจากhandshakeหรือgenerationใหม่ |
| ทั้งสองท่อส่งbucketเดิมต่อเนื่อง | คงไม่พร้อม; backoff/deduprecoveryrequests/เตือน60s ไม่มีpollingstorm |

ใช้controlledREST/WS interleavingsและactualPGrestart ไม่อ้างว่าpermutationtest
พิสูจน์numerical-IDorderingจากตลาด; propertytestsต้องไม่ใช้IDเป็นexpectedwinner
เทสต์unknown/futuretimestampและgenerationเก่ายังคงบังคับตามเกณฑ์เดิม

## V-23 — สถานะตาม snapshot ที่อนุมัติ NC-26

expectedอิงserver timeline แยกจากเวลารับbrowser; ไม่มีproof/capability gate
หรือtestที่อ้างว่า performance.nowต้องเดินข้ามsleep

| กรณี | Expected |
|---|---|
| serverอ่านราคาอายุ9.9sและREADY, responseกลับช้า500ms | เว็บแสดง“พร้อม ณเวลาที่ตรวจ”กับserver_time/trade_atเดิม; ไม่อ้างพร้อม ณreceiptหรือcurrentREADY |
| responseหน่วง/parse/renderช้า/asymmetricRTT | timestamp/สถานะตามsnapshotไม่ถูกre-anchor; backendreadinessประเมินจากเวลาสร้างviewจริง |
| ราคาที่backend10s/10s+1µs | ณreferenceนั้นexact10sผ่านและเกิน10sSTALE; snapshotใหม่สะท้อนผลใหม่ |
| serverhandshake/pong/newreceived_atแต่ราคาเก่า | backendไม่READYจากเหตุนี้; viewมีreasonและเวลา |
| devicewallclockเปลี่ยน/monotonicหยุดระหว่างsleep | ไม่ใช้browserclockรับรองfreshnessหรือเปลี่ยนsnapshottime; ราคายังรับได้ |
| tabhidden/freeze/resume/pageshowที่ตรวจพบ | deliverystatusรอsnapshotใหม่; oldconnectioncallbackไม่คืนCONNECTED/ไม่ย้อนcache |
| OSsleepโดยไม่มีlifecycleevent | snapshotที่แสดงยังระบุ“ณเวลาที่ตรวจ” ไม่อ้างdetectsleepหรือcurrentREADY; เมื่อได้รับviewใหม่ใช้ordering guards |
| initialGETตอบหลังWSviewที่ใหม่กว่า | ไม่ย้อนgeneration/revision/checkedtime/deliverystate |
| backendSTale/disconnected/leaseexpired/Redisdown | snapshotแสดงnonREADYตามbackendพร้อมreference; ไม่เอาbrowserconnectedมาช่วยREADY |
| browseroffline/close/heartbeatmissที่ตรวจพบ | localdeliverywarningทันที, cachedsnapshotแสดงเป็นข้อมูลค้างพร้อมเวลา |
| reconnect/identitychange/sessionexpiry | รับfullviewใหม่ก่อนstatusของconnectionใหม่; identityเก่าไม่เขียนcache; expiryflowเดิม |
| futurebackendconsumerอ่านsnapshotเก่าที่เคยREADY | ต้องใช้referenceเวลาใหม่ตรวจage/lease/recovery; เก่าเกิน10sห้ามreadyแม้เว็บเคยแสดงreportedREADY |

E2Eใช้proxyหน่วงresponseและmockclockเฉพาะbrowserเพื่อยืนยันความหมายนี้
DOMต้องมีทั้งreference time/trade timeและstatuscopyที่บอกณsnapshot
scope reviewต้องไม่พบ trusted/current-readyboolean จากwebcacheไปอนุญาตคำสั่ง
rawpreflightในresearchเป็นหลักฐานเหตุผลที่ยกเลิกแนวclockproof ไม่ใช่mergegate

## V-24 — Server interval และ delivery warning ที่อนุมัติ NC-27

expectedจากserver timelineและเหตุการณ์deliveryที่สังเกตได้ ไม่ใช้browserclock
รับรองelapsed60s รวมกรณีclockหยุดหรือwallปรับโดยไม่ทำให้serverintervalเปลี่ยน

| กรณี | Expected |
|---|---|
| marketไม่พร้อม59.999s/ครบ60sที่DBreference | alert_due=false/trueตามขอบ; frontendแสดงตามsnapshotพร้อมเวลา |
| restart/reconnect/handshakeขณะmarketยังไม่พร้อม | unavailable_sinceเดิม ไม่เริ่ม60sใหม่ |
| backendREADYจริงคั่นระหว่างสองoutage | resetinterval; outageถัดไปเริ่มใหม่ไม่รวมสองช่วง |
| leaseexpired/RedisnotificationหายและAPIreadใหม่ | snapshotประเมินreadiness/intervalใหม่ ไม่ใช้cachedREADYหรือcachedfalseเป็นผลปัจจุบัน |
| browseroffline/close/heartbeatmissที่ตรวจพบ โดยmarketยังพร้อม | deliverywarningทันทีที่ตรวจพบ ไม่รอ60s ไม่มีlocalcountdown |
| browserclockหยุด20s/80sในsleep ไม่มีevent | ไม่อ้างว่าelapsedครบ60s; snapshotยังระบุเวลาที่ตรวจ; เมื่อdetectdeliveryfailureจึงเตือน |
| reconnectเปิดtransportแต่snapshotยังค้าง | AWAITING_SNAPSHOT และข้อความรอสถานะใหม่; ไม่เคลียร์จากhandshake |
| reconnectแล้วfullsnapshotใหม่ผ่านguards | แสดงstatus/marketalertตามsnapshotใหม่; เคลียร์deliverywarningเมื่อได้รับสถานะใหม่จริง |
| marketsnapshotalert=trueอยู่ก่อนbrowserหลุด | คงmarketwarningพร้อมเวลาและเพิ่มdeliverywarning ไม่กลบเหตุเดิม |
| delayedGET/socketเก่า/identityเก่ามาพร้อมalert=false | guardsปฏิเสธ ไม่เคลียร์warning/ย้อนsnapshot |
| currentvalidsnapshotalert=falseหลังmarketพร้อม | marketwarningเคลียร์ได้ตามผลserverใหม่; ไม่ตีความว่าdeliveryพร้อมหากlocalยังหลุด |
| logout/revoke/unmount | cache/timers/socketcleanupเดิม ไม่มีwarningข้ามidentityหรือaria-liveทุกtick |

actualPG/RedisintegrationและE2Eใช้proxyตัดbrowserdeliveryโดยไม่ตัดupstream
เพื่อพิสูจน์ว่าmarketoutage60sกับdeliverywarningเป็นคนละเหตุ
ทดสอบThai/English, reference timeและwarningไม่พึ่งสี

## หลักฐานสัญญาตลาดและข้อจำกัด

[publiccontract](../../research/2026-10-07-f10-stream-contract.md)
เก็บRESTทั้ง5คู่และtrade streamครบ5คู่แล้ว ไม่ใช้APIkey
มีduplicate/equaltrade-timeและfieldsที่หายจากตัวอย่างเอกสาร
parserต้องผ่านfixturesจริงและnegativefixturesที่สร้างโดยระบุว่าเป็นsynthetic
ไม่อ้างว่าfake reconnectหรือshortcaptureพิสูจน์SLA/24hrotationของตลาดจริง

เพิ่ม bounded publicstream contract test ภายใต้ marker `venue_contract`
ในงานรายวันเดิม ใช้THendpointเท่านั้น timeoutรวม30s และรับเฉพาะ5คู่
ขาดtradeในcapture → รายงาน inconclusive/failedcontractตามเหตุจริง
ห้ามfabricatepayloadหรือเอาtrade Binance.comมาทำให้ผ่าน
เทสต์ปกติไม่เรียกlivefactory/ตลาดจริง และCImergeไม่ขึ้นกับตลาดออนไลน์

## ตรวจด้วยมือหลัง implementation

1. เปิดcomposeที่มีPostgreSQL/Redis/API/frontend/market-data; loginด้วยบัญชีทดสอบ
   ยืนยันราคาทั้ง5คู่และเวลา พร้อมข้อความ“พร้อม ณเวลาที่ตรวจ”และserver_timeเมื่อbackendผ่านเงื่อนไข
2. ดูที่1440pxและ360px ทั้งไทย/อังกฤษ ไม่มีoverflowหรือราคาโดนตัด
   missing/เก่า/หลุดแสดงคนละความหมาย; keyboardเข้าถึงข้อมูลได้
3. ตัดupstreamด้วยlocaltestproxyที่ควบคุมได้ → สถานะไม่พร้อมทันทีที่ตรวจพบ
   ค่าล่าสุดยังอยู่แต่มีป้าย/เวลา; ต่อกลับแล้วไม่พร้อมจนกู้และราคาผ่านเกณฑ์
4. ใช้fakeproducerหยุดส่งtradeแต่socketยังต่อ → เกิน10sแสดงราคาเก่า
   heartbeatต้องส่งผลประเมินserverใหม่ ไม่รีเซ็ตtrade_at; คู่หนึ่งเก่าไม่ทำให้คู่สดหายไป
5. serverตลาดไม่พร้อม60s → marketwarningตามsnapshot; handshakeไม่resetinterval
   ตัดเฉพาะbrowserdelivery → deliverywarningทันทีที่ตรวจพบ ไม่รอ60s; ต่อกลับรอfullviewใหม่
6. browserofflineแล้วonline → ไม่พร้อมขณะหลุด รับfullviewใหม่ก่อนกลับพร้อม
7. restartRedisและkillproducer → cacheไม่ค้างREADY; กู้คืนโดยไม่สร้างworkerซ้อน
8. logout/revokeจากอีกsession → socketปิดและกลับexpiryflow; ราคาที่ไหลไม่ต่ออายุsession

บันทึกผล/screenshotsภายใต้ specs/reviews/2026-10-07-f10-realtime-prices/
ห้ามบันทึกcookie/token/key/secretหรือURLที่มีคำรับรอง
ไม่ใช้การแก้DBproductionเพื่อจำลองเหตุเสียหาย

## คำสั่งและด่านที่ต้องเขียว

เครื่อง/CIใช้dependencyจากlockและDBrolesตามconfigเดิม; เพิ่มRedisACLทดสอบ
ก่อนรันintegration/E2E ไม่skipเพราะไม่ได้ตั้งRedis

ใน backend:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run alembic upgrade head
uv run pytest
uv run python -m tiewtrade.services.api.openapi_export
```

ใน frontend:

```sh
npm ci
npm run gen:api
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

root:

```sh
git diff --check
env -u POSTGRES_VERSION docker compose --env-file config/postgres.env config
env -u POSTGRES_VERSION docker compose --env-file config/postgres.env up -d --build --wait
```

ตรวจgeneratedbackend/openapi.jsonและfrontend/src/api-types.tsตรงกับcode
หลังสร้างแล้วต้องไม่มีdiffใหม่จากgenerationซ้ำ
CI backend/APIcontract/frontend/E2E/dockerและconfigurationjobต้องเขียวก่อนmerge
dailyvenue-contractแยกจากmergegateตามมาตรฐานเดิม
scope reviewต้องตรวจrequirements15ข้อกับV-1..32และไม่มีunrelatedcodechange

## สถานะผลตรวจ

บันทึกclockproof/certificationก่อนNC-26 approvalด้านล่างเป็นประวัติที่superseded
เกณฑ์ปัจจุบันอยู่ในตารางและV-23/V-24ข้างต้น

- requirements/plan/validation Approvedครบวันที่2026-10-07; NC-24..27Closed
- การอนุมัติเกณฑ์ไม่ใช่ผลทดสอบ: V-1..V-32 ยังไม่ตรวจ
- issue2: แก้ข้อกำหนดวิธีตรวจเวลาในplanและเพิ่มกรณีV-23แล้ว; ยังไม่ได้พิสูจน์runtime
- issue3: เอาnumeric-IDorderingออก เพิ่มpartialorder/latch/recoveryและV-8; ยังไม่ได้พิสูจน์runtime
- issue4: เพิ่มconnection/admission/cleanup/poolboundsและV-29..32; ยังไม่ได้พิสูจน์runtime
- review รอบสอง issue1: เพิ่ม ack deadline5s/cleanup bound และ V-10 cases; ยังไม่ได้พิสูจน์ runtime
- review รอบสอง issue2: เพิ่ม clock guard/epoch/capability gate และ no-event sleep cases; ยังไม่รับรอง platform/runtime
- review รอบสอง issue3: user cap คงที่3 ตรง runtime/schema และเพิ่ม V-29 contract checks; ยังไม่ได้พิสูจน์ runtime
- review รอบสาม issue2: แยก clock proof gate จาก transport/data พร้อม V-23 cold-start/recovery/resource tests; ยังไม่ได้พิสูจน์ runtime
- review รอบสาม issue3: แยก alert-clock/backend interval/local record และเพิ่ม V-24 sleep cases; target/runtimeยังไม่รับรองภายใต้ NC-26
- implementation/unit/integration/E2E/manual/CI: **ยังไม่ตรวจ**
- publiccontract evidence: เก็บแล้วตามresearch ไม่ใช่ผลผ่านของV-1..32
- ไม่อัปเดตroadmapเป็นCompletedหรือSpecReadyจากการมีเอกสารเท่านั้น

- owner approve NC-26: snapshot semanticsและbackendfreshnessใหม่ก่อนใช้จริง; ยังไม่มีruntimeผลผ่าน
- NC-27: local-onlyalertproposalรอคำตอบ; ไม่ถือว่าownerอนุมัติplan/validationจากการapproveNC-26

- owner approve NC-27: servermarketoutage60s/browserdeliverywarningทันทีที่ตรวจพบ; V-24ปรับแล้ว ยังไม่มีruntimeผลผ่าน
- NC-26/NC-27Closed ไม่ถือเป็นการอนุมัติplan/validationทั้งฉบับ

- 2026-10-07 owner approve plan/validationทั้งฉบับแล้ว; gateก่อนimplementationครบ


## Implementation checkpoint — 2026-10-07

- Backend full suite1755passed/2venue_contractdeselected; strictmypy259files,
  Ruff/format และ7importcontractsผ่าน
- Frontend lint/typecheck/build และVitest132testsผ่าน
- ActualfullflowE2E10testsผ่าน; screenshotsThai/English360/1440 inspected
- ActualPG/Redis roles, grants, writerfencing, ambiguityrecovery, slotCAS,
  RedisACL, notificationACK, migrationdowngrade/replay และcoldstartalert tested
- OpenAPI/frontendtypes regenerateidentically; isolatedComposebuild/startuppassed
- V-17 strictwatchdog/cadenceรอNC-28 approval; V-29..32 actualtwoAPIprocess/
  load/contentionยังไม่ครบ ไม่ถือว่าvalidationทั้งหมดผ่านหรือCompleted
- รายละเอียดอยู่ใน specs/reviews/2026-10-07-f10-realtime-prices/implementation-status.md
- ไม่มีcommit/pushหรือexternalCIrun


2026-10-07 — NC-28 Approved: เจ้าของอนุมัติcoordinator500ms/เพดาน2transactions
ต่อวินาทีต่อsocket พร้อมstart-anchored1s watchdog ก่อนแก้โค้ด
เพิ่มกรณีV-17/V-32: delayedauthqueryและblockedsendต้องถูกยกเลิกเมื่อauthorization
หมด ไม่ต่อdeadlineจากquerycompletion; pool3/overflow0 และ200transactions/s
upperboundที่100sockets ต้องพิสูจน์ร่วมกับinteractiveHTTPในloadtest


## ผลสุดท้าย — 2026-10-07

Local functional validation V-1..V-32 ผ่านครบ ดู
[coverageและหลักฐาน](../../reviews/2026-10-07-f10-realtime-prices/final-validation.md)
Backend1780/Frontend132/Playwright10 passed; Ruff/format/mypy/imports/generated
contracts/Compose build-startup ผ่าน รวมactual resource/recovery probes
NC-24..28ปิด; ไม่มีimplementationที่รออนุมัติจากNC-28แล้ว
ยังไม่มีcommit/push/merge; externalCIเป็นgateก่อนmerge ไม่อ้างผลที่ยังไม่รัน
checkpointก่อนหน้านี้เป็นประวัติ ไม่ใช่ผลปัจจุบัน


## Deep review follow-up — issue1 fixed (2026-10-07)

Owner requested fixing High: WebSocket URL query tokens in Uvicorn logs.
Added `services/api/safe_logging.py`; filter is installed at API import and lifespan
before serving. Covers uvicorn.error WebSocket logs and uvicorn.access structured
arguments, plus exception query text. All request queries are redacted rather than
maintaining a potentially incomplete list of credential parameter names.

`tests/test_price_logging.py`:7passed including real Uvicorn accepted/rejected
handshakes, formatter compatibility, exception redaction and idempotent installation.
Logging/secret/WebSocket/safety regressions:47passed; mypy263files and7import
contracts passed; targetedRuff/format andgitdiffcheckpassed.
This fixes issue1 only. Other deep-review findings are not marked resolved by this change.


## Deep review follow-up — issue2 fixed (2026-10-07)

Owner requested API fixture preserve the CI Redis endpoint. `_api_environment`
now keeps explicit TIEWTRADE_REDIS_URL_API; if absent uses TIEWTRADE_TEST_REDIS_URL,
then the existing local56379 default. An explicitly empty API value is preserved
so misconfiguration fails rather than silently selecting a different endpoint.

`tests/test_api_environment.py`:6 regression cases passed after reproducing5 failures.
Actual WS/auth/admission tests plus fixture regressions:25passed against task-owned
Redis6381, proving the old56379 override is gone. CI6379 is covered by the exact-value
regression; local6379 was occupied and that existing service was not modified.
Ruff/format and fullmypy264files passed. No GitHubCI execution is claimed.
Other review findings remain separate; this change edits test fixtures only.


## Deep review follow-up — issue3 fixed (2026-10-08)

Owner requested Thai display time per database standard §2. MarketTime now formats
with Asia/Bangkok in both Thai and English; original UTC instant remains unchanged
in the time element datetime attribute and transport/storage.

MarketValue.test.tsx adds two regression cases crossing the UTC date boundary:
2026-10-07T20:30:00Z displays 2026-10-08 03:30 in Bangkok, including default Thai
and explicit English locale. Both reproduced the UTC display failure before the fix.
Frontend134tests passed, including the11 realtime panel tests and API contract gate;
lint, typecheck and production build passed. Other review findings remain pending.


## Deep review follow-up — issue4 fixed (2026-10-08)

Owner requested translating reason codes per frontend standard §6 and plan UI i18n.
RealtimePricePanel now renders reason text through the existing i18next instance.
All11 codes emitted by API snapshot_view have Thai and English translations in
realtimePriceMessages.ts; unknown codes use a translated generic reason without
rendering the raw code. Trade data ordering is explicitly distinguished from orders.
API payload, readiness decisions and cache behavior are unchanged.

Added24 panel regression cases (11 known codes plus an unknown code, each in both
languages). All24 reproduced raw-code display before the fix. Full frontend158tests
passed, including35 panel tests and API contract gates; lint, typecheck and build
passed. Remaining review findings5–7 are not resolved by this change.


## Deep review follow-up — issue5 fixed (2026-10-08)

Owner requested preventing an expired writer lease from being revived after SQL
lock waits. Feed mutations now include source/owner/generation/DB-clock expiry
predicates, with a zero-row result raising WriterLeaseLost. Price updates use the
same fence. Post-mutation checks cover price-row waits and generation/connection
price invalidation; exceptions escape market_data_session and roll back the full
transaction. Supervisor handling remains the existing stop/reacquire path.
This implements the approved transactional owner/generation/lease fencing rule;
lease duration, takeover and trading rules are unchanged.

Seven actual PostgreSQL lock races reproduced failure before the fix: feed table
locks for renew/generation/connection; price table locks for write/generation/
connection; a price row lock for write. Assertions confirm unchanged durable feed
and prices, rollback of an earlier successful row write, takeover with a new owner
and next generation, and rejection of the old lease. Normal renewal, connection,
write and no-op behavior also pass.

Verification: backend1800passed,2live venue tests deselected, no skips,116.07s;
full Ruff/format, mypy264files and7import contracts passed. Storage/supervisor/API
focused regressions also passed (27cases). The first full-suite invocation omitted
required Redis environment and failed ACL/health setup; the final full run above
used the isolated test DB and Redis56379 and passed. Existing Starlette deprecation
warnings remain. Findings6–7 remain pending; no commit/push/merge.


## Deep review follow-up — issue6 fixed (2026-10-08)

Owner requested rejecting trade identifiers that cannot fit the approved BIGINT
column. QuoteObservation now accepts integer IDs in0..2**63-1, rejecting bool as
before. MAX_TRADE_ID declares that persistence constraint once in the pure type;
REST and WebSocket mapping both reuse the existing _readable boundary to translate
invalid observations into VenueProtocolError. No database migration or numeric-ID
ordering assumption is introduced. Financial amounts and trading rules are unchanged.

Seven regression cases reproduced the bug before the fix: oversized IDs in core
and REST/WS mapping, plus a stream frame that previously emitted an invalid quote.
Boundary cases accept0and2**63-1;2**63and10**100 are rejected. Stream transport emits
VENUE_PROTOCOL without a quote, then closes. The durable storage test writes and
reads back2**63-1 exactly through PostgreSQL.

After the fix:48core/mapping/stream tests,34storage/supervisor/API/feed regressions,
and27purity/venue-isolation/money-movement gate tests passed (109total). Full Ruff/
format, mypy264files and7import contracts passed. Full backend1800passed is the
previous issue5 baseline, not a new full-suite result for this fix. Finding7remains
pending; no commit/push/merge.


## Deep review follow-up — issue7 draft, NC-29 pending (2026-10-08)

Native Uvicorn decoder reproduced1009for oversized frames in10cases (2normal-limit
cases already returned1008). Draft adapter retains256byte decoding and changes
only native size-failure to1008. Six wire cases each with/without compression cover
256bytes,257bytes text/binary,258UTF-8 bytes, fragmented257bytes and64KiB decoded
messages. Oversized messages never reach ASGI; native ping/pong and1002/1007/1011
are preserved.16protocol plus7logging tests passed. Docker Linux frozen build and
protocol loader smoke passed; full Ruff/format, mypy266files,7import contracts and
lockfile freshness passed.

Full backend result:1828passed,1failed,2live venue tests deselected. Failure is the
NC-17 network boundary rejecting the two new websockets imports. No gate exception
has been added; issue7 remains unresolved pending the explicit NC-29 plan decision.

Proposed validation after approval: narrow import/use exception only for the
server decoder and close-code enum in the stated file; negative fixtures for other
files/members, outbound connect/socket/HTTP/asyncio calls, re-export and market URLs
must still fail. Re-run all backend gates and regressions before claiming completion.

Browser evidence for the draft: all10Playwright tests passed (52.0s), including
a real authenticated browser WebSocket through the Vite proxy sending257bytes
and observing close1008. Existing realtime recovery/revocation paths passed.
Frontend lint/typecheck passed. This does not waive the failed NC-17 gate.


## NC-29 Approved follow-up (2026-10-08)

Owner explicitly approved the decoder exception before changing the boundary
checker. The preceding draft failure is historical. Only price_protocol.py may
import ServerProtocol as a decoder base class and CloseCode for annotations or
read-only MESSAGE_TOO_BIG/POLICY_VIOLATION constants. Direct instantiation of the
imported base, alias/re-export and __all__ exports, other members/locations, enum
mutation, outbound clients, socket/HTTP/asyncio calls and market URLs remain denied.

Added22boundary fixtures (1positive plus21negative). The positive case failed
before the exception; the __all__ re-export case also exposed a missing check and
was fixed before the final regression run.253boundary/purity/venue/asyncio/wire/
logging tests passed; frontend158tests/lint/typecheck/build passed. Final full backend:1851passed,2live venue tests deselected,no skips,114.36s.
Full Ruff/format, mypy266files and7import contracts passed. Wire/logging23tests,
Docker Linux frozen build/loader smoke and lock freshness passed; browser10tests
(52.0s) include actual authenticated257byte close1008. The runtime adapter was
unchanged after that browser/Docker verification; the approved final changes are
the narrow boundary checker and its fixtures. Existing3Starlette deprecation
warnings remain. Issue7 is fixed; all7reported findings have fixes and local
regression evidence, but a new deep review and externalCI remain before merge.
No commit/push/merge.


### 2026-10-08 — Review follow-up: verbose transport logging

ก่อนแก้ issue1: ใช้ real Uvicorn + PriceWebSocketProtocol ทดสอบ accepted/rejected
handshake ที่ DEBUG/TRACE ด้วย Cookie/Authorization canary; ต้องไม่มี canary ใน log
และยังมี INFO path/status. ตรวจว่า verbose payload ถูกกรองก่อน formatter,
INFO/WARNING/ERROR ยังอยู่ และ query/exception redaction เดิมยังผ่าน.
ใช้ safe_logging.py เดิม ไม่เปลี่ยน protocol หรือข้อยกเว้น NC-29.

ผล: ก่อนแก้ 6 regression cases แดงจาก cookie/header leak และ verbose payload;
หลังแก้ logging + protocol **34 passed**. Ruff/format/mypy ผ่านทั้งสองไฟล์ที่แก้.
ตัวกรองเดิมตัดระดับต่ำกว่า INFO ที่ uvicorn/error/access/asgi ก่อนส่ง handler
จึงไม่พิมพ์ DEBUG wire dumps หรือ TRACE ASGI scope/messages แม้เปิดระดับดังกล่าว;
INFO/WARNING/ERROR และ query/exception redaction เดิมยังทำงาน.
ไม่ได้รัน full backend/frontend/CI ซ้ำ; review รอบล่าสุดข้อ2 recovery และข้อ3 forwarded IP ยังไม่แก้.


### 2026-10-08 — Review follow-up: rejected recovery

ก่อนแก้ issue2: regression ควบคุม feed/DB time ให้ราคาเดิมสด แต่ REST future60s;
ต้องคง RECOVERING, เก็บราคาเดิม, retry แล้ว READY เฉพาะเมื่อ reconciliation ผ่าน.
ตรวจ core ผลสำเร็จแยกจาก state สำหรับ future/stale/conflict/pre-latch และ valid winner.

ผล: regression แดงก่อนแก้เพราะ pair ถูกเพิ่มเข้า reconciled หลัง REST future;
หลังแก้ core + supervisor/projection ที่ไม่ใช้ DB **21 passed**, Ruff/mypy ผ่าน4ไฟล์.
reconcile คืน ReconciliationResult(state, succeeded) ชัดเจน; supervisor ยอมรับเฉพาะ
ผลสำเร็จจาก attempt ปัจจุบัน โดยคง state เดิมและ retry เมื่อ winner ใช้ไม่ได้.
เพิ่ม core cases stale/future rejection และ successful reconciliation ที่ค่า state ไม่เปลี่ยน.
PostgreSQL integration ยังไม่ได้รันซ้ำ: Docker daemon ไม่ทำงานและไม่มี isolated test DB URL
ใน session นี้; full suite/CI ยังไม่ถือว่าผ่านรอบใหม่. ข้อ3 forwarded IP ยังค้าง.

### 2026-10-08 — Review follow-up: forwarded IP admission

ก่อนแก้ issue3: ตรวจ launch commands ใน README/Dockerfile/Compose/Playwright
และ real Uvicorn + price protocol ด้วย TCP peer เดิมแต่ forwarded headers ต่างกัน;
ต้องเห็น peer เดิมทั้งสองครั้ง เพื่อให้ admission ใช้ IP bucket เดิมตาม plan §4.

ผล: ก่อนแก้ทั้ง4 launch configurations แดง (TCP peer เดียวถูกแปลงเป็น2 IP
จากผู้เรียก); หลังเพิ่ม --no-proxy-headers ทั้ง4จุด regression ผ่าน เห็น127.0.0.1
ทั้งสองครั้ง. รวม proxy/logging/protocol **38 passed**, Ruff/format/mypy ผ่าน.
README ระบุ proxy peers ใช้ bucket ร่วมกัน และต้องตั้ง trusted proxy/sanitize
headers อย่างชัดเจนก่อนเปิด forwarded client IP ตาม plan เดิม. ไม่เปลี่ยน Redis
limits, authentication หรือ price protocol; ไม่ได้รัน Redis/PG integration,
Docker image build, browser E2E หรือ full CI ซ้ำในรอบนี้.


### 2026-10-08 — PostgreSQL/Redis integration after final review fixes

รัน `pytest tests/infra tests/api tests/services/market_data -q -o addopts='' --tb=short`
กับ PostgreSQL16 และ Redis7 ใน disposable containers แยกจาก application containers
ทุกบทบาทชี้ test PostgreSQL; API/market-data/test Redis ชี้ test Redis เดียวกัน.
bootstrap ทุก SQL ตาม CI แล้ว migrate ถึง head ก่อนเริ่ม; ไม่เรียกตลาดจริง.

ผล **805 passed, 0 failed, 0 skipped, 3 warnings, 104.54s**. ครอบคลุม
writer lease expiry ระหว่าง table/row-lock wait ทั้ง7กรณี, rollback writes ก่อนหน้า,
connection-slot concurrency/expiry/CAS cleanup, Redis atomic limits/ACL/pubsub,
API session/revocation/authorization และ ingestion/recovery integration.
Warnings เป็น Starlette/httpx และชื่อ HTTP422 ที่ deprecated เดิม.
ลบเฉพาะ disposable test containers หลังจบ ไม่กระทบข้อมูล application.
ผลนี้ปิดข้อจำกัด integration ของ review fixes; browser E2E และ full CI
หลัง fixes ล่าสุดยังเป็นด่านแยก ไม่ถือว่าผ่านจากผลชุดนี้.


### 2026-10-08 — Full local validation after latest review fixes

- Full backend: **1870 passed, 2 live venue-contract tests deselected, no skips**,
  123.07s; 3 existing Starlette deprecation warnings.
- Frontend: **158 passed**; ESLint, TypeScript and Vite production build passed.
- Playwright: **10 passed (1.1m)** against isolated `tiewtrade_e2e_f10`,
  real API/Vite/PostgreSQL/Redis and controlled fixture producers; no live orders.
- Backend Ruff/format (268 files), mypy (267 files), 7 import contracts,
  offline lock freshness (55 packages), and in-memory OpenAPI/schema comparison passed.
- PostgreSQL16/Redis7 used disposable containers, separate from application data.
  Original API/frontend were temporarily stopped for ports8000/5173 and restored;
  API health and frontend HTTP200 verified. Test containers/volumes removed.

Local validation after the three latest fixes is complete. Deep code review was
APPROVED before this run; no implementation changes were required by these tests.
Remote CI and merge remain pending; no commit/push/merge performed. Docker image
rebuild and live venue-contract probes were not rerun as part of this test task.


### 2026-10-08 — Remote CI and integration approval

Implementation commit `e8796f97d2de35d8cfc7c37f065591d17d30dc3a` passed all6
[remote CI jobs](https://github.com/yukasung/tiewtrade/actions/runs/37743108753):
configuration, frontend, API contract, container builds, backend, browser E2E.
Owner authorized PR, merge, main CI verification and branch cleanup. The Done
roadmap change is included in the closing PR; branch deletion follows successful
main CI and confirmed remote merge.
