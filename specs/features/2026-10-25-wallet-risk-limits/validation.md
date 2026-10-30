# F-18 — เพดานความเสี่ยงต่อกระเป๋า — Validation

สถานะ: **Approved** — เจ้าของตอบ “approve” ต่อ plan/validation ฉบับแก้ F18-R1..R4 วันที่ 2026-10-26; อนุมัติปรับเวลา W1/W2/W3 เป็น 10/5/30 นาที วันที่ 2026-10-27
เกณฑ์ปัจจุบัน: **R32 Approved 2026-10-29 — Paper fixture 5Hz**; ดู [amendment](paper-source-cadence-amendment.md) ซึ่งแทนเฉพาะ 10Hz ในข้อความเก่า
โหมดตรวจรับปัจจุบัน: **R33 Approved 2026-10-29 — explicit child publisher** ตาม [amendment](child-acceptance-mode-amendment.md); ใช้เกณฑ์ล่าสุดด้านล่าง
วันที่: 2026-10-25
เกณฑ์ล่าสุด: **R34 Approved — source count ขาดได้ 1/channel/run และ risk ราย owner 99.5% ภายใน3s สำหรับ W1–W3**; [ขอบเขตและการใช้หลักฐานเดิม](paper-acceptance-tolerance-amendment.md)
ปรับล่าสุด: 2026-10-26 — เพิ่มเกณฑ์ deep-review F18-R1..R4; Approved 2026-10-26
อ้างอิง: requirements.md **Approved 2026-10-25**, NC-F18-01..08; testing §7

## 1. “เสร็จ” หมายถึง

| รหัส | ข้อกำหนด/ความเสี่ยง | ตรวจอย่างไร | ระยะรัน | ผล/หลักฐาน |
|---|---|---|---|---|
| V-01 | RQ-01/02: limit/units/input | Money USDT >0, no default/business max เพิ่ม; smallest accepted unit/max representable, blank/zero/negative/JSON number/NaN/wrong currency/precision/overflow ปฏิเสธ ไม่ปัดแทนผู้ใช้; unset ปิด opening แต่ reduction/cancel ใช้ contract เดิม | M1/M2 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-02 | RQ-04/NC-02: realized/valuation | hand oracle รวม realized สุทธิทุก pair และ partial fills+เฉพาะ unrealizedลบ, clamp0, threshold exact/below/above; closed-pair realized และ delisted exposure ยังนับ; ทุน/RESET credit/reservations ไม่เป็น PnL; ผล F-14 fee treatment คงเดิม | M1 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-03 | RQ-06/NC-03: reset allowance | ตัวเลขใน §2 รวมส่วนปิด/ยังถือ ซื้อเพิ่ม/full close/resetซ้ำ, allowance ที่ขายแล้วหมดไป, ไม่สร้างเครดิตกำไรจาก allowance; ใช้ Money rounding เดิมและไม่เกิด residual หลังปิดหมด | M1 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-04 | RQ-05/06/14: correction | REPLACE/VOID ก่อนและหลัง reset, partial close→correction→replay; reset cutoff/price frame เดิมใช้ rebuild ไม่เอาราคาปัจจุบันไปแก้อดีต; proof/gap missing → unavailable; latch ไม่ล้างเอง; duplicate/reordered correction ไม่ใช้ allowanceซ้ำ | M1/M3 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-05 | RQ-16: shared domain/parity/purity | same input fixture ผ่าน domain/policy เดียวกันของ Paper/Live ให้ loss/latch/reduction decisions เท่ากัน; hypothesis ใน §3; existing purity/import gates ห้าม clock/random/network/float/DB ใน core | M1/candidate | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-06 | RQ-05/10/11/NC-04: lifecycle | ราคาเด้ง/เปลี่ยนวัน/restart/เพิ่มlimit ไม่ล้าง latch; ลดlimitแล้วถึงเกณฑ์ชน; resetฐาน0ไม่ปิดไม้ ไม่สลับBOT→MANUAL/เปิดบอท; price unavailableเป็นพัก กลับพร้อมแล้วประเมินทันทีไม่ล้าง latch; Paper episode ใหม่คง limit/latch และแยก PnL/allowanceจากepisodeเก่า | M1/M3 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-07 | RQ-03/13: DB isolation/immutability | PostgreSQL runtime rolesจริง: missing/cross owner404/no rows, APIแก้ financial/risk projectionไม่ได้, ENGINE_SCANอ่าน hintsเท่านั้นและเขียนไม่ได้, MARKET_DATAไม่อ่านuser/secret; immutable tables UPDATE/DELETE/TRUNCATEถูกปฏิเสธ; FK/mode/unit/shape/revision constraints บังคับจริง | M2 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-08 | RQ-13/14: atomicity/idempotency | DB audit/insert/update/commit failures, same-key concurrent equal/different payload, by-key lookup after receipt loss; immutable request/result/baseline/breach/effectsหนึ่งชุด, keyเดิมไม่ resetซ้ำ, stale expected revision409, unknown commitไม่ตอบว่าปฏิเสธแน่นอน | M2/M3 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-09 | security §1/F-06: expansion TOTP | increaseทุกโหมดต้อง fresh TOTP ไม่มี grace/recovery code, wrong/reused codeและquotaข้ามsession/IPตามF-06; forged proofถูกปฏิเสธ; downgrade/initial-setting routeเปลี่ยนเป็นincreaseที่executionไม่ได้; concurrent setting changes/secret rotationไม่ใช้authorizationผิดpayload/revision; resetไม่requireTOTPและไม่จัดเป็นreduction | M2 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-10 | API/session/contract | all routes classified F-06, auth/CSRF/extra fields/forgedmode/owner, throttle/Retry-After, safe errorsไม่มีTOTP/secret/rawSQL; querypollไม่renewsession; generated OpenAPIตรงclient; Live routeไม่รับPaperwallet/episodeและไม่เรียกPaper mutation | M2/M4 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-11 | schema/rolling upgrade | up→down→up บนข้อมูลว่างและdowngrade guardบนhistoryจริง; existingwalletไม่ถูกตั้งlimit/ล้างlatch/สร้างbaselineเอง; oldwriterที่ไม่รู้riskfenceถูกปฏิเสธหลังactivation; old/new worker overlapไม่doublewrite; sourceไม่พร้อมยังอ่าน/cancelได้ตามcontract | M2/M5 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-12 | NC-05: monitoring/SLA correctness | controlled-clock domainและreal-DB bounded integration: price/fill/correction committed→durableevaluation/latch <=1s เมื่อdependenciesพร้อม; idleaccount/browserปิด, ไม่มีคำสั่งใหม่, 2pairs, lasttradeexpiry/leaseexpiry/disconnect; วัดinput-ready→commit แยกจากbrowser/venueclock ไม่ใช้ค่าเฉลี่ยซ่อนmiss | M3; full scale V-21 | Partial — Paper targeted evidence in [M5](evidence/m5-final-candidate.md); full-scale/fault/protective/dependency criteria remain open as applicable |
| V-13 | price frame completeness/ordering | durablepricejournalในtransactionF-10, price dipผ่านthreshold→recoverระหว่างroundยังlatch; duplicate/gap/generation/restart/Redisloss recovery, priceก่อนresetไม่ชนรอบใหม่, multi-pair consistent revision; unavailableแล้วreplayไม่ใช้ราคาเก่าเป็นfresh; cursor/pruningไม่ลบframeที่ยังต้องใช้ | M3 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-14 | RQ-07/12/14/NC-08: opening gates | APIpreflight/bridge/admission/ก่อนmatchingหรือfillใช้authoritativestate; queuedBUYก่อนbreachห้ามเปิดเพิ่มหลังlatchcommit; testunavailable/expiredprice/sourceconflict/latchunknown/monitorstale→manualและbotopeningปิด ไม่useallowall/cacheREADY; boundedSELLลดได้ทุกaccountuse ส่วนoversizedSELLไม่ผ่านreduction; reduction/cancelไม่requirelossREADY | M3 | Partial — Paper targeted evidence in [M5](evidence/m5-final-candidate.md); full-scale/fault/protective/dependency criteria remain open as applicable |
| V-15 | RQ-09/17/NC-07: actual order effects | real F-15 consumer: queuedNEWterminalมีreason, activeLIMITBUY/SELLและpartialremainderตาม§8ถูกจัดการ, TP/SL-tagged protective fixtureไม่ถูกcancelและpositionไม่ถูกปิด; result links/listsถูกต้อง, stopครบเฉพาะรู้ผลทุกใบ, issueมีtargetรายการจริง; pending stop requestที่ไม่มีconsumerไม่ผ่าน | M3 | Partial — Paper targeted evidence in [M5](evidence/m5-final-candidate.md); full-scale/fault/protective/dependency criteria remain open as applicable |
| V-16 | cancel/fill/reset/concurrency | barriersบนPostgreSQL: breach-vs-fill, reset-vs-fill/correction, decrease-vs-new, reset-vs-oldcancel, two workers/lease takeover และwalletreset-vs-riskcommand; serializeได้ ไม่มีpartial financial/risk state, fillหรือreservationreleaseไม่ซ้ำ, oldcommandsไม่ฟื้นหลังreset | M3 | Targeted evidence passed — M1/M2/M3/[M5](evidence/m5-final-candidate.md); release/CI gates tracked separately |
| V-17 | fault/recovery/botstop contract | killprocess/connectionก่อนและหลังbreach/reset/cancelcommit, lostack, Redisdown, DB/auditfailure, lockedowner; recover latch/reason/cursors/effectsจากPostgreSQL, reconcileก่อนREADY, no cause→openingblocked; cancel retry/backoffเกิน1นาทีแจ้งแต่ยังretry, filled targetไม่รายงานcancelสำเร็จ, accountหนึ่งค้างไม่starveownerอื่น | M3 | Partial — Paper targeted evidence in [M5](evidence/m5-final-candidate.md); full-scale/fault/protective/dependency criteria remain open as applicable |
| V-18 | RQ-15: UI/template/UNKNOWN | component+browserตรวจไทย/อังกฤษ/light/dark/mobile/desktopตาม§4; limit/loss/baseline/source times/mode/latch/stopordersตรงserver, nooptimisticreset; pending/UNKNOWNreload→samekeylookup/replay, storagefailureก่อนsendไม่ส่ง; owner/mode/episodecacheไม่ปน; increasepromptTOTP/resetไม่มีprompt; 5minpausealertแยก60smarketwarning | M4 | Paper composition/browser evidence passed — [M4](evidence/m4-ui-composition.md)/[M5](evidence/m5-final-candidate.md); activation still gated by V-21 |
| V-19 | RQ-17/F-16 V-18: production composition E2E | isolated real PostgreSQL/production API+engine+monitor+cancelconsumer และrecordedpublicfeed ใช้riskpolicyจริงไม่มีtestpolicy: unset→set→BUY/partialSELL→lossbreach→queued/activecancel→boundedreduction→reset→resumeeligiblemanual; unavailable/priceoutage/correction/reload/duplicate flow; assert identities/ledger/positions/allowances/audit/result links ไม่ใช้ภาพอย่างเดียว; liveexecutor/credentials spyต้องไม่ถูกเรียก | M4/M5 ก่อน activation | Paper composition/browser evidence passed — [M4](evidence/m4-ui-composition.md)/[M5](evidence/m5-final-candidate.md); activation still gated by V-21 |
| V-20 | final candidate gates/review | แจ้งReady for Code Reviewก่อนreview แก้Critical/Highและfindingsในscope; backendfullregression/ruffformat+lint/mypy/import-linter/purity/isolation, frontendtests/lint/types/build/generatedcontracts, ChromiumE2E/configComposeและrequiredCIบนfinalcandidate; ใช้evidenceเดิมเมื่อdependenciesยังvalid | M5 ก่อนmerge | Local regression + corrected affected reruns/static/contracts/Chromium/Compose passed; final review/remote CI pending — [M5](evidence/m5-final-candidate.md) |
| V-21 | NC-05/full integrated release | ชุดเต็ม§5บนfinalschema/composition: F-15W1–W4ตามข้อยกเว้นเวลา§5+F-16intake+F-18Paper monitor/R25:99.9%<=3sต่อownerและทุกinput<=5s(target1s)และstop/recovery; correctnessoracleทำงานตลอด ไม่มีmissที่ถูกเฉลี่ยทิ้ง ไม่มีmoneyduplicate/falsefill/retentiongap; บันทึกoldFailed/Partialและผลใหม่แยก | release/ชุดที่9 ก่อนproduction activation/Completed | Pending Full Validation — W1 failures preserved; V2 r9 passed 2,000-order baseline/partial-fill oracle then failed measured reseed cycle60s (15 cycles/210 completed). W4 r8 passed on0055 after R6/retry fix. R6 approved/read-only API catch-up and bulk evidence safety/affected suites passed; reseed20 passed58.18s (diagnostic only). W1 r10 Partial/aborted during setup for redundant-payload fix; final affected checks passed with intermittent worker failure retained. Corrected source-continuous full cycle still Failed60s. R7 approved/interleaved rounds implemented; composition24/mypy558 passed, R7 selected-owner cycle returned within60s; corrected helper postconditions verified (original failure retained). W1 r11 Failed/Partial at baseline10/20 (ENGINE refused pending evidence). Same-protocol monitor SQL checks116+1 passed; W4 r9 passed;100-owner baseline reproduction returned within60s and donor/clone per-request postconditions passed (original helper failure retained). W1 r12 passed2,000 baseline/partial-fill oracle, then Failed60s during selected-owner reseed (445completed/70cycles). 10s probe Paper578/956skipped; R8 bounded fallback approved/implemented; selector26/real-DB safety221passed; probePaper427/427processed; W1r13 Failed60s during selected-owner reseed on fresh0055/currentR8 (508offered/479admitted/466completed/77cycles); measured status polling declared; no capacity pass. Review fixes: API provenance/active-order indexed lookup/measured latency window repaired; affected199tests, SQL27/final29, matching104/purity/isolation and mypy561passed; W1r14Failed60s at reseed (467completed/78cycles). Original250ms result polling restored and unused identity allocation removed without changing IDs/fills; frozen progress cycle53.863s passed, diagnostic only. Final W1r15 Failed60s at reseed (525offered/505admitted/491completed/84cycles); High remains open. R9 approved2026-10-28 and implemented with canonical claim proof, one-preference guard and schema0056; affected225/enabled49 tests, mypy563/import7 passed. Frozen progress52.300s passed (diagnostic only); W1r16 aborted setup, W1r17 Failed60s reseed (495completed/87cycles). Preference disabled back toR8 as approved; disabled composition29tests and W4 final0056 restore/grants passed. High remains open; final full backend coverage3675passed (1192reused+2502remaining−19rechecks;2venue contracts excluded), ruff/format/mypy563passed; no W2/W3 invocation. R10 approved/implemented; safety253/enabled26/mypy564/static passed; frozen43.4648s passed diagnostic only, W1r18Failed/Partial172.5s: all3risk scenarios complete,1626completed/312cycles; later cycle60s expired near RESET after ~39.86s LIMIT SELL result delay/claimrev5; exact slow-SELL cause unresolved; later diagnostic failed baseline on RISK_PRICE_UNAVAILABLE/source freshness, not acceptance. R10 disabled back toR8; disabled26/mypy564/import7/static passed. R11 approved/implemented0057: affected116passed, controlled SELL7.28s/0.13s after source resumption (not SLA acceptance). Frozen cycle failed before Paper startup; freshW1r19 failed baseline seeding after Paper workers started with WriterLeaseLost (272native commands/253successes; zero measured commands). R11/R10 disabled toR8; final0057 backend coverage3729passed via recorded resume (initial failures retained), W4restore/grants/recovery and final static checks passed. W2/W3 pending; see [M5](evidence/m5-final-candidate.md) |
| V-22 | RQ-09/16: bot/Live dependencies | F-19/F-20 stop/resume/reconciliation integrationและtestsกับsharedcontract; Live authority F-23/activation F-24ผ่านตามfeatureเจ้าของงาน ไม่มีliveorderในautomatedvalidation; lossresetไม่เปิดbotที่มีstopสาเหตุอื่น | dependency checkpoint ก่อนรับรองscopeนั้น/Completed | Pending Dependency — F-19/F-20/F-23/F-24 |
| V-23 | NC-06/notification dependencies | Paperแสดงข้อความ/รายการจริงผ่านV-18/19; notification centerและEmail/Telegram/LINEตามF-26/F-36/F-27: durable delivery/retry/locale/pause/breach/cancelissueและscopeต้องมีevidenceจริง ไม่ใช้auditlogแทนnotification | dependency/release ก่อนรับรองscopeนั้น/Completed | Pending Dependency — F-26/F-36/F-27 |

M1–M5 ผ่านไม่ได้แปลว่า Completed เมื่อ V-21..23 ยัง pending การ mergeเพื่อพัฒนาต่อ
ต้องผ่าน V-20 และด่าน correctness/safety ที่เกี่ยวข้องครบ คง production NEW admissionปิด
ก่อนเปิด Paper จริงต้อง V-18/19/21 ผ่านและไม่มีdependencyในเส้นทาง Paperที่เปิดค้าง
V-22/23 ไม่อนุญาตให้เลื่อน consumer/cancellation หรือข้อความจำเป็นของ Paper ไปด้วย
F-16 V-18 จะอัปเดตตามหลักฐานส่วน integration จริง ไม่ใช้ผลนี้ปิด F-16 V-20 หรือ
F-13/F-14/F-15 release gates ที่ยังไม่ตรวจ และไม่ส่ง Live order ใน automated validation

### เกณฑ์เพิ่มเติมจาก deep review — 2026-10-26

รายการนี้เป็นส่วนบังคับของ V ที่อ้างถึง ไม่ใช่ผล Passed จากการแก้เอกสาร
ใช้เพิ่มใน checkpoint เดิมตาม impact โดยไม่สร้าง workload/timed smoke ใหม่ท้าย milestone

| Finding / V | สถานการณ์และผลที่ต้องพิสูจน์ |
|---|---|
| F18-R1 / V-11/13/16 | real PostgreSQL barriers บังคับทั้ง publisherได้EXCLUSIVEก่อนfinancialSHARED และfinancialได้SHAREDก่อนpublisher; กรณีแรก framecommitแล้วต้องประเมินด้วยholdingsก่อนfill/reset กรณีหลังยืนยันด้วยDBlock state/commit visibilityว่าpublishercommitแทรกระหว่างcutกับfinancialcommitไม่ได้; ตรวจboundary marker/cursorกับfinancialrevisionเดียวกันหลังrollback/kill/restart ไม่ใช้sleepคาดลำดับ |
| F18-R1 / V-12/21 | หลายownerถือSHAREDพร้อมกัน, publisherwaiting, F-10lease/disconnect transitionsและold/newpublishersแข่งกัน; ไม่มีdeadlock/starvationหรือunframedpublicationหลังprotocolactivation; oldfinancialwriterที่ไม่สร้างboundaryสำหรับfill/correction/baseline/episode transitionถูกปฏิเสธ แต่compatiblecancelpathยังทำงานตามF18-R2; คงSLA1sและF-10readiness/ingestionguaranteesเดิม หากไม่ผ่านไม่เปิดadmission |
| F18-R2 / V-14/16/17 | authoritativeholdings/reservationsและF-15bookพร้อม แต่riskjournalgap/monitorหยุด/อีกคู่ไม่มีราคาที่ใช้ประเมินloss: boundedSELLต้องไม่รอdrainและfillได้ตามF-15; commitledger/position/boundarymarkerพร้อมUNAVAILABLE/REPLAY_PENDING, latchเดิมไม่หายและopening/resetยังปิด; oversizedSELLยังไม่เป็นreduction |
| F18-R2 / V-04/16/17 | หลังreductionขณะriskgap ให้ซ่อมframesแล้วreplayผ่านfinancialmarkers: priceก่อนboundaryใช้holdingsก่อนfill หลังboundaryใช้holdingsหลังfill, allowances/adjustedrealizedเท่ากับoracleที่เรียงfactsครบตั้งแต่ต้น; replayซ้ำ/killระหว่างrebuildไม่เพิ่มfill/cancel/ledgerผลเดิมและไม่ใช้allowanceซ้ำ |
| F18-R2 / V-15/17 | usercancelและstopconsumer cancelไม่เรียกriskdrainหรือรอpublicationfence: riskmonitor/sourcegapยังค้างแต่cancelสำเร็จได้เมื่อorderstoreพร้อม; reservationคืนครั้งเดียวหลังterminal, cancel/fillraceใช้ผลจริง; requiredDBtransactionfailureยังต้องไม่กล่าวว่าสำเร็จ |
| F18-R3 / V-08/09 | kill/connectionlossก่อนAUTHcommitและหลังAUTHcommitก่อนAPIinboxinsert: ก่อนcommitไม่มีTOTPconsumeหรือreceipt หลังcommitby-keyคืนAUTHORIZATION_ONLYไม่ใช่404/APPLIED; exactsamekey/payloadretryใช้receiptเดิมโดยไม่consumeTOTPซ้ำและสร้างrequest/consume-linkหนึ่งชุด; ถ้าPOSTยังin-flight lookup404ต้องยังUNKNOWNไม่เริ่มkeyใหม่ |
| F18-R3 / V-09/10 | concurrentexactreplay, keyเดิมต่างamount/action/revision/mode/owner, forgedreceiptและAPIroleINSERTauthorization: ไม่ได้สิทธิ์ใหม่และไม่มีfinancialeffect; currentauth/CSRFบังคับแม้replay, receiptที่payloadขัดกัน409, requestใหม่ทุกkeyยังต้องfreshTOTP; staleexecutionrevisionต้องrejectไม่rebaseintent; ทดสอบsecretrotationหลังauthorizationโดยไม่เปลี่ยนfingerprint |
| F18-R3 / V-18/19 | browserUNKNOWN/reloadพบAUTHORIZATION_ONLYแล้วแสดงว่ายังไม่มีinbox/execution; retryintentเดิมโดยไม่สร้างkeyหรือขอรหัสใหม่อัตโนมัติ; หลังinboxcommitแสดงREQUEST_PENDINGและหลังenginecommitเท่านั้นจึงAPPLIED/REJECTED; duplicateHTTPresponseไม่เพิ่มlimitซ้ำ |
| F18-R4 / V-10/18 | สร้างมากกว่า100targets/stopและหลายstops อ่านdefault20/max100/min1และcursorหลายหน้า: ทุกtargetหนึ่งครั้งต่อwatermark, retryeventsไม่ทำให้targetซ้ำ, concurrenteffectupdatesไม่เปลี่ยนหน้าของsnapshotเดิม; refreshwatermarkจึงเห็นผลใหม่; invalidlimit/cursor/filter/scopeถูกปฏิเสธและcrossowner/mode/stopID404ตามcontract |
| F18-R4 / V-18/19/21 | risksnapshotไม่มีorder/eventhistoryarrayและcountsตรงaggregateprojectionที่commitกับeffects; effectsresponseไม่เกินlimitและqueryใช้scope/keysetindex ไม่สแกนคืนhistoryทั้งหมด; UIไม่ผสมcountsใหม่กับpagesเก่า ไม่แปลunloadedpagesเป็นไม่มีpending; target_set_complete=falseต้องไม่STOPPEDแม้knownpendingcount0/หน้าแรกว่าง และSTOPPEDได้ต่อเมื่อauthoritativetargetcompletenessครบ; fullworkloadตรวจpollingไม่ทำSLA/resourceเดิมเสื่อม |

## 2. ตัวเลขจริง — oracle อิสระจาก implementation

หน่วย USDT ใช้ Money/Quantity ที่ขอบเขตการคำนวณ เขียนแหล่งคำตอบใน tests
ห้ามใช้ฟังก์ชัน risk ที่กำลังทดสอบคำนวณ expected result

| กรณี | คำตอบที่ต้องพิสูจน์ |
|---|---|
| realized +100/−80, unrealized BTC−30/ETH+50 | loss10; ETH+50ไม่ชดเชยBTC−30; limit10ชน limitสูงกว่า10หนึ่งstoredunitยังไม่ชน |
| ขาย90%แล้วrealized−100 ส่วนที่เหลือunrealized0 | loss100ทันที ไม่รอpositionเป็น0หรือorderfilledทั้งหมด |
| realized+100/unrealized−30 | loss0 ไม่มีnegative lossหรือเครดิตแสดงเป็นยอดขาดทุน |
| reset ณloss−100แล้วmark−130 | lossใหม่30; mark−70 loss0และไม่ให้เครดิต+30กับpairอื่น |
| reset ณloss−100แล้วปิดที่−130/−70/+20 | adjustedrealized −30/0/+20 ตามลำดับ ข้อยกเว้นไม่เปลี่ยน−70เป็น+30 |
| ไม้เดิม+100ณresetแล้วmark+20/ปิด+20 | markนับloss0, closeนับrealized+20 ไม่ใช่loss80 |
| 1BTCต้นทุน1000, resetที่900, ขาย0.5ที่900 | realizedจริง−50 ถูกยกเว้น50; allowanceเหลือ50และheld0.5; ผลหลังreset0 |
| ต่อจากแถวบน ราคาที่เหลือลงเหลือ800/BTCแล้วขายหมด | unrealizedจริง−100หักallowance50→loss50; ขายหมดadjustedrealized−50และallowance0 ไม่คิดrealized+unrealizedซ้ำ |
| 1BTCต้นทุน1000 resetที่900 แล้วซื้อ1BTCที่900 | held2BTC/cost1900/allowance100 ไม่มีallowanceใหม่; mark900 unrealizedจริง−100→loss0; mark850 unrealizedจริง−200→loss100 |
| partialขายตอนฟื้น: 1BTCต้นทุน1000 resetที่900 ขาย0.5ที่960 | realizedจริง−20/allocatedallowance50→adjusted0; allowance30ที่ไม่ใช้หมดไป เหลือ50สำหรับ0.5BTC ไม่ยกส่วนเกินไปเพิ่มเครดิต/allowance |
| fullclose/resetซ้ำ/one-smallest-unit allocation | allowanceไม่ติดลบ ไม่มีresidualหรือสิทธิ์ยกเว้นเกินฐาน ใช้explicitroundingเดิม; TOWARD_ZEROสำหรับส่วนขาย fullcloseใช้ยอดคงเหลือexact |

เพิ่ม correction/fee examples จาก F-14 fixtures เดิมเมื่อแก้การเรียก transition จริง
การเปลี่ยนคำตอบทางเงินต้องกลับไปขออนุมัติ requirements ไม่แก้ expectedให้ตรงcode

## 3. การเลือกตรวจตามผลกระทบ

- Domain/allowance: handoracles + hypothesisของconservation, no-created-profit,
  per-fill uniqueness, amount/unit bounds, zero-held allowance0, duplicate replay,
  correction rebuildเท่ากับeffectivefacts, resetซ้ำไม่ทบสิทธิ์ และ Paper/Liveparity
- การแบ่ง partial fill อาจมีผลroundingตามF-14 จึงทดสอบconservationและboundsที่อนุมัติ
  ไม่อ้างว่า split/unsplitต้องเท่ากันexactทุกกรณีหรือปรับnumericpolicyเพื่อให้testผ่าน
- Transactions/roles/authorization: ใช้realPostgreSQLและruntime roles assertions
  mockไม่พิสูจน์lock/CAS/commit/immutability/FK/RLS จึงเพิ่มDBtestsเฉพาะinvariantsใหม่
- publication boundary/receipt/effects pagination ใช้ scenarios ใน deep-review mapping
  ข้างต้นเป็น regression obligations ของ V เดิม ไม่เพิ่ม V ซ้ำหรือรายงานผ่านจาก mock
- TOTPใช้middleware/classification/quota/replaytestsเดิมเป็นฐาน ขยายเฉพาะincrease
  receipt/revision TOCTOU; ไม่สร้างเครื่องมือverifyTOTPอีกชุด
- Pricejournal/monitorกระทบF-10 storageและlease/freshness จึงรันaffectedF-10 tests
  กับF-14/15/16 money/order/walletreset/correction/isolation ที่callchainเปลี่ยน
- UIเพิ่มriskpanelกับrecoveryเท่านั้น เลือกcomponenttestsและbrowserflowsที่พิสูจน์
  state/recovery/auth/cache; เปิดfullregressionเมื่อcandidateนิ่งที่V-20
- Proof/reference/source/cursor/migration changes ทำให้evidenceที่พึ่งสิ่งนั้นหมดอายุ
  ตรวจซ้ำชุดที่กระทบ ไม่รันload/soakเพียงเพราะจบmilestoneหรือกลับมาทำต่อ
- V-12timingในbounded correctnessใช้สั้นพอพิสูจน์idle/deadline/concurrency ไม่ถือว่า
  แทนV-21 ถ้าต้องรันtimedworkloadก่อนreleaseให้แจ้งrisk/reason/scopeก่อนตามtesting§7

## 4. ตรวจด้วยมือและ visual QA

ตรวจ Paper/Live mode labels และแยกcache/mutations; UIใช้template mappingในplan§2
ตรวจไทย/อังกฤษ × light/dark ที่desktop1440/mobile375 และtablet768สำหรับlayout
state coverage: unset/loading/error/unavailable/ready/breached/stop-in-progress/problems
พร้อมhover/focus-visible/disabled/error/keyboard/modalfocusreturnและscreen-reader labels
ไม่จำเป็นต้องถ่ายทุกcrossproductถ้าครอบคลุมstateและtokensเดียวกันได้ด้วยหลักฐานเดิม

ownerลองตั้งเพดาน เพิ่มด้วยTOTP ลด/resetโดยไม่ขอTOTP; ถือไม้ลบขณะresetแล้วเห็น
คำอธิบายตรงผลserver; reloadขณะUNKNOWNและสลับownerต้องไม่ส่งซ้ำ/แสดงข้อมูลคนก่อน
เปิดLIMITก่อนbreachแล้วเห็นรายการยกเลิก/filled/มีปัญหาตามจริง ไม่แสดงว่าปิดposition
ลองboundedSELL/cancelเมื่อbreachedหรือข้อมูลlossไม่พร้อม แล้วตรวจผลผ่านเส้นทางเดิม
Liveแสดงsourceunknown/ไม่มีexecutionก่อนdependenciesพร้อม ไม่ใช้เงินจริงทดสอบ

## 5. Full validation ที่ release checkpoint

ใช้baseline environmentของ F-15 validation§6 (อย่างน้อย4logicalCPU/8GiB,
localPostgreSQL/Redis/runtime/lockfilesเดิม) พร้อมCPU/RAM/pools/workerlimits,
datasetdigest/config/schemaและsource commitในevidence ขยายharnessเดิมให้มี
F-16intakeและF-18risk monitor/stop consumer ไม่สร้างworkloadที่ไม่มีpositiveoracle

- **W1:** 100episodes×20activeLIMIT, book5Hz (R32), commands10/s 10นาที เกณฑ์F-15เดิมยกเว้นเวลาที่อนุมัติด้านล่าง
  เพิ่มfreshlast-tradepriceobservations5Hzต่อคู่BTC/ETH (R32), มีlosslimits/baselinesทุกowner,
  schedulebreach/reset/cancel/decrease/partial/correctionที่deterministic
- **W2:** datasetเดิม100commands/s 5นาที คงpositivecyclesและF-15thresholds
  แยกnon-fault phaseที่ต้องผ่านPaper R25 service99.9%<=3s/hard5s(target1s)ออกจากจงใจoverflow/slowdependencyที่ต้องblock
  opening/recoverอย่างถูกต้อง; ห้ามนับmissในnon-faultเป็นfaultเพื่อให้ผ่าน
- **W3:** W1 30นาที พร้อมchurn/restart/Redisoutageตาม F18_W3_FAULTS_V2
  เพิ่มmonitorrestart/pricegapและidleownerช่วงไม่มีcommands ตรวจdurablelatch/stop
  และSLAในnon-fault phasesโดยไม่ลดthresholdsเดิมหรือปิดfinancialoracle
- **W4:** backup/restoreมีrisksettings/resetbaselines/priceframes/cursors/latchesและ
  pendingstop/effects/TOTPauthorizationreceiptsร่วมกับF-15factsจริง ตรวจcanonical
  financial/riskdigest/roles/claimrecovery ไม่มีduplicatefill/cancel/allowanceuse

ทุกPaper evaluationที่inputsพร้อมต้องcommit<=5s และ99.9%<=3sต่อowner/ทั้งrun (R25; target1s)และเก็บdistribution/max/misscountพร้อม
input-ready timestamps ไม่ใช้percentileแทนเกณฑ์ทุกdecision ส่วนlatency/resource/
RSSgrowth/queue/fillcountของ F-15 W1–W4 ใช้thresholdsเดิมครบ ยกเว้น Paper processing p95<=500ms ตาม revision2026-10-29 หากค่าใดล้มต้องคง
Failed/Partialพร้อมสาเหตุ ไม่ลดโหลด/เกณฑ์หรือเปลี่ยนเวลาเพิ่มเติมโดยไม่อนุมัติ
และไม่อ้างtargetedchecksแทนชุดเต็ม
ผลชุดนี้ต้องใช้finalrisk-enabledschema/compositionและรวมF-16V-20ตามintegration
profileนี้ ก่อนรันตรวจharness/cleanupด้วยtargetedtestsที่เกี่ยวข้อง ไม่รันW1smokeท้ายงานอัตโนมัติ

### การปรับเวลาที่เจ้าของอนุมัติ 2026-10-27

ใช้เฉพาะ F-18 integrated profile `F18_F15_F16_INTEGRATED_V2`: W1 600s,
W2 300s, W3 1800s รวมช่วงวัด 45นาที ไม่รวม setup/restore/recovery overhead
และไม่ใช่คำรับรองเวลางานเสร็จ ไม่เปลี่ยน specification ของ F-15
คง 100owners×20orders, book/price5HzตามR32, command rates10/100/10ต่อวินาที,
latency p95<=500ms/p99<=1s (p95 revision2026-10-29), Paper R25:99.9%<=3sต่อowner/ทั้งrun และทุกinput<=5s (target1s), financial/quantity/
retry/idempotency/overflow4097/resource oracles เดิม และ W4 เดิม

W3 ใช้ `backend/tests/infra/risk_limits/w3_fault_schedule.json`: เก็บ fault7ครั้ง
ชนิด/ระยะเวลาครั้งละ30/60sเดิม เลื่อน offsets เป็น225/450/675/900/1125/1350/1575s
และ30positivecyclesต่อownerให้พอดีกับช่วงวัด โดยบันทึก schedule digest ในหลักฐาน
RSS ใช้ warmup112.5s เปรียบเทียบค่าเฉลี่ยช่วง112.5..562.5s กับ450sสุดท้าย
ต้องมี observed samples ครอบคลุมอย่างน้อย1687.5s และ growth<=20%เดิม
F-15ยังใช้ค่าเริ่มต้น4ชั่วโมงและหน้าต่างเดิม ไม่อ้างการตรวจ30นาทีว่าเป็นหลักฐาน
memory leak ระยะ4ชั่วโมง ความเสี่ยงระยะยาวนี้ยังเหลืออยู่

เก็บผล Failed/Partial ของ profileV1 ทุกครั้งตามจริง profileV2ยังไม่ผ่านจนมีผลใหม่
การอนุมัตินี้ปรับเวลาและตาราง fault/RSS ตามเวลานั้นเท่านั้น ไม่เปลี่ยน publication
fence/lock order หรือกฎการเทรดที่อนุมัติไว้

## 6. หลักฐานและด่านก่อนส่ง

ผลข้างต้นยังไม่เกิดขึ้นจริง ไม่มีVใดPassedจากการเขียนเอกสารนี้
ระหว่างพัฒนาอัปเดตcheckpoint/evidenceเดิมพร้อมdiff/commands/environment/เวลา
ก่อนmergeบังคับV-20และcorrectness/safetyที่เกี่ยวข้องครบ ตามtesting§1/7
เจ้าของสั่งcommit/push/mergeแยกตามAGENTS.md ไม่ทำGitmutationsเหล่านี้จากการอนุมัติplan
ก่อนCompletedตรวจทุกเกณฑ์รวมV-21..23 และmanualacceptance ตามscopeจริงของdependencies

Checkpoint 2026-10-26: แก้เอกสารให้ผูกการตรวจ F18-R1..R4 ครบแล้ว ยังไม่มี
application implementation/tests หรือ runtime evidence เพิ่ม ทุกผลในตารางหลักคง
Not Run/Pending ตามเดิม และ plan/validation ฉบับแก้ยังรออนุมัติก่อนลงมือ


### เริ่ม implementation — 2026-10-26

เจ้าของอนุมัติ plan/validation ฉบับแก้ F18-R1..R4 ด้วยคำตอบ “approve” และสั่งทำต่อ
จนผ่านเกณฑ์ รวม full regression/final review และ workload ทีละชุด ไม่รัน diagnostic ซ้อน
checkpoint ขั้นเอกสารก่อนหน้านี้เป็นประวัติ ไม่ใช่จุดอนุมัติที่ยังค้าง
เริ่ม M1 domain/hand-oracle/property/parity ก่อนเชื่อม persistence ใน M2
ผล validation ยังไม่เปลี่ยนเป็น Passed จนมีหลักฐานจริง และ production admission คงปิด


### Implementation checkpoints — 2026-10-26

[M1 core](evidence/m1-core.md): targeted76 passed + static/purity/import gates.
[M2 persistence/API](evidence/m2-persistence-api.md): DB11/API9/worker5/audit regression74 passed.
เป็นหลักฐานบางส่วนของเกณฑ์ ไม่เปลี่ยน V-01..20 เป็น Passed ทั้งข้อก่อน integrationครบ
โดยเฉพาะ authoritative reset/monitor/stop ยังรอ M3; workload/dependencies คง Pending

[M3 monitor/stops](evidence/m3-monitor-stops.md): partial targeted evidence เพิ่มตาม checkpoint
ยังไม่ปิด milestone หรือแทน full regression/workload/browser/dependency criteria

2026-10-28 source-clock follow-up: equivalent lease SQL tuning passed21focused
checks then206affected risk/matching/service checks; ruff/format4files and mypy
2sourcefiles passed. Same150s bounded setup comparison improved successful
commands1099→1255 and maximum loop gap846→234ms, but baseline was unfinished and
financial-fence timeouts persisted. Neither diagnostic reproduced WriterLeaseLost.
This does not replace W1/W2/W3 or change Failed/Pending Full Validation status.
Evidence: [M5 final candidate](evidence/m5-final-candidate.md), source-clock-tests
and source-clock-stall artifacts. Optional R9/R10/R11 runtime defaults remain off.

W1r20 (2026-10-28): final default R8/source-clock SQL candidate passed2000baseline
but failed60s measured owner-cycle deadline during breach/reset reseed result
polling (API pool checkout at cancellation).342completed/42cycles, one of three
risk scenarios recorded. No full600s qualification; W2/W3 not run. Terminal wait
alone does not establish a pool leak or the entire latency cause. Existing
Failed/Pending Full Validation retained; details and artifacts in M5 checkpoint.

W1r21 (R10experiment + source-clock SQL, R11off): baseline2000completed but60s
breach/reset/reseed cycle failed;425completed/66cycles, only partial-fill risk
scenario recorded. Latest unresolved native command had3claims/3attempts; exact
defer cause is not recorded. Same code/resources as W1r20, experiment flags and
runner hashes in manifest. W2/W3 not run; Failed/Pending Full Validation retained.

### 2026-10-28 — R16 follow-up

R16 safety92passed but same-clone diagnostic failed7029late/max2.657488s;
rolled back per approved terms, rollback34passed. Subsequent pressure/CPU
diagnostics are not acceptance. V-21 remains Failed/Pending Full Validation;
W2/W3 remain pending. R17 is Proposed only; see M5 evidence and amendment.

### 2026-10-28 — R17 follow-up

R17 safety78unique cases passed, but diagnostic SLA failed. Approved-method
combinations remain Failed; best observed blocking100ms/page100/R16/R17 had
3249late/max2.327136s. Equivalent setup-batching experiment worsened and was
rolled back (8rollback checks passed). Full regression and W1–W3 remain pending
on a qualifying final candidate. R18 concurrency/pool change is Proposed only.
See M5 evidence; no Completed or production activation claim.

### 2026-10-28 — R18 follow-up

Owner approved R18;32 affected safety cases passed, but both sequential monitor
comparisons failed (max1.765373s with optional profiling;4.988970s native entry).
Runtime restored to4slots; rollback12tests and mypy237files/ruff/diff passed.
V-21 remains Failed/Pending Full Validation. W1–W3 and final regression/review
remain pending. See M5 evidence for connections-observer visibility limitation,
source archives and retained failures. No Completed or activation claim.

### Evidence-first closure / headroom follow-up

After owner-ready comparison, graceful owned-service/Docker restart reduced
host paging substantially. Default4-slot diagnostic still failed405late/max1.580120s;
approved8-slot re-evaluation failed1209late/max2.162473s and was rolled back.
Rollback12passed; no W1–W3 acceptance. A traced due-boundary skip followed by last
position in the next UUID page motivates R19 (Proposed only, not implemented).
V21 remains Failed/Pending Full Validation; V22/V23 Pending Dependency. Full
current collection3770, with historical/new-case evidence mapped in M5; collection
is not regression completion. See M5 for all run limitations and pending gates.

### R19 outcome

R19 approved and37affected safety cases passed. Both bounded comparisons failed
(918late/max1.339450s; first-after-VM-restart879late/max1.940027s); execution-order
change fully reverted per experiment terms, rollback12passed and static checks
passed. V21 remains Failed/Pending Full Validation. R20 is Proposed only; no new
migration or runtime eligibility change implemented. See M5 for complete evidence.

### Current R20–R22 candidate (2026-10-28)

R20 was subsequently approved and implemented with narrow0058 scanner grants.
The approved R19 ordering was re-enabled with R20 eligibility; their native idle
preflight passed60300/60300,zero misses,max.997677s (diagnostic only). Command
cycle remained SLA Failed. Approved R21 eight-slot composition also Failed and
was restored to4; full failure evidence is retained in M5.

R22 approved/implemented replay-local valuation reuse without Money/formula,
source checks, latch, resource or SLA changes. Core70 and affected infra/API247
cases passed (21scanner cases rechecked on clean0058 after reused-DB pollution;
initial failures preserved). Independent pre-change function parity10000inputs
passed; static/import checks passed. Native cycle48.2843s and financial oracle
passed but SLA Failed6822/142807,max2.224694s,zero unack. An explicit environment-
equivalence check is pending; it is not a fresh acceptance claim. Current runtime
4slots/R19/R20/R22/schema0058; V21 remains Failed/Pending Full Validation.
W1–W3,0058W4,final regression/review and remote/manual gates remain pending;
V22/V23 remain Pending Dependency. Authoritative run details stay in M5.

R22 environment-equivalence check also Failed: cycle42.2647s and financial oracle
passed, but3933/126007evaluations late,max1.700444s,zero unack. The native preflight
gate remains closed; no W1–W3 started. Host pressure remains an unresolved
confounder; further environment separation is needed before another method trial.

### Superseded Paper two-second timing gate — 2026-10-28

Paper hard bound2s inclusive ต่อทุก ready input;1sเป็นtarget ไม่ใช้ percentile
แทนhard bound. Oracleต้องเก็บhard_limit_seconds=2,target_seconds=1,
target_miss_count(>1),miss_count(>2),max/distribution และunacknowledgedครบ
ทดสอบขอบ1.000/1.001/2.000/2.001s, missing/pending/rollback และfinancial boundary
checksเดิม. W1/W2/W3 10/5/30นาที/โหลด/ทรัพยากร/F15latency/W4คงเดิม
Liveคง1sและPending Dependency. ทุกผลFailedที่บันทึกก่อนหน้านี้คงเป็นผลตาม
เกณฑ์ขณะรัน ห้ามเขียนทับ; re-assessmentต้องแยก artifactและไม่แทนfull validation

### Paper three-second timing gate — 2026-10-28; superseded by R25

Paperทุก ready inputต้องcommit<=3s inclusive, target1s. Oracleรายงาน
hard_limit_seconds=3,target_seconds=1,target_miss_count(>1s),miss_count(>3s),
max/distribution/unacknowledgedและclock errors; ไม่มีค่าเฉลี่ยหรือpercentile
ยกเว้นhard misses. ตรวจขอบ1.000/1.001/2.000/2.001/3.000/3.001s และmissing/
pending/rollbackเดิม. F15commandlatency,W1–W4,resources/loads/durations,Live1s
และfinancialchecksคงเดิม. Failed/Pendingเดิมยังคงไว้จนมีหลักฐานตรวจรับครบ


### Approved Paper processing latency revision — 2026-10-29

เจ้าของอนุมัติปรับ processing p95 เป็น **<=500ms** สำหรับ F-18 Paper integrated
profile `F18_F15_F16_INTEGRATED_V2` เท่านั้น แทนเกณฑ์ที่สืบทอดจาก F-15 <=250ms.
Processing วัด transaction รวมการรอ connection/lock และ commit ตาม instrumentation
เดิม ไม่ใช่เวลาตั้งแต่ส่งคำสั่งจน fill. คง p99<=1s, Paper timing ตาม R25 ด้านล่าง
(target1s), 100owners×20orders, rates/resources, command deadlines, W1–W4 และ
financial correctness/retry/idempotency ทั้งหมด ไม่เปลี่ยน F-15 standalone หรือ
Live criteria. เก็บผล Failed/Partial เดิม ไม่เปลี่ยนผลย้อนหลังเป็น Passed;
ต้องมีหลักฐาน candidate ใหม่ผ่านเกณฑ์ทั้งหมดก่อนรับรอง Paper validation.


### R25 — Approved Paper acceptance revision (2026-10-29)

Supersedes all earlierPaper3s hardbounds in this document: per-owner and global
atleast99.9%ofexpectedreadyinputs<=3s, everyreadyinput<=5s,target1s. No missingack,
clockerrors or droppedtail samples; existingfaultwindows only. Record all>3sinputs,
count/rates>1/3/5s,distribution/max andperownerverdicts. Exact3/5s pass; exceeding
ownerquota/hard5s fails evenifaggregatepasses. Financialgates/Live1s unchanged.

Connectiongate: freeze actualprocess/role/poolinventory beforemeasurement; budget
boundedbydeclaredpoolcapacity andavailablePostgreSQLheadroom. Everyresource sample
withinbudget; checkoutreturn evidence for allpools/generations complete; afterdrain,
stop/dispose no appclientconnection inisolatedDBwithin5s (excludeonlyownquery and
predeclaredobserverPIDs). Missinginventory/nonreturningcheckout/cleanupfail areFailed.
Retain start/end/peak asmetrics, notlive start+2verdict. Otherresourcegates unchanged.

Tests: SLA boundary/quota perowner/global,small sample,missingack/clockerror/fault;
actualinventory/budget/roleconfig,checkoutreturn,cleanupandobserverexclusion;
existingfinancial/caller tests perimpact. NativeW1/W2/W3/W4remainrequired with
originaldurations45minW1–W3 total and100owners/rates/resources. Oldresults notrelabeled.


R25 implementation evidence2026-10-29: affected41tests/resources4tests andstatic
checks passed; nativeW1Failed60scommandcycle duringselected-ownerreseed after
2000baselineorders,370commands/46cycles. Not a fullrisk/financial/resourcepass;
W2/W3/W4notstarted. See M5; R25criteriaapproved, nooldfailure relabeled.


### R26 — Approved recovery-scenario timing (2026-10-29)

Owner approved [R26](recovery-scenario-budget-amendment.md). Supersedes the60s
inclusive selected-scenario bound only: ordinarycycles andnormalelapsedexcluding
onlyone recordedbreach_reset phase remain<=60s. Thatphase alone<=120s; selected
firstcycleouterguard<=180s. Innerstop30s/price10s/request60s,load/rates/counters,
R25risk/processing/resources,financialchecks andfinalelapsed/drainboundsunchanged.
ReuseF15scheduler withoptionaltest-onlycyclecontext,default60s unchanged; F18
tracksoneeligiblephase and itsstages/20reseedidentities usingmonotonic time.
No productionAPI/schema/pools orruntimechanges. OldFailedresultsnotrelabeled;
targetedbudget/default/cancelcontracts beforeonenativeW1,stoponfailure/noautoretry.


R26 evidence2026-10-29: targeted56/mypy576/staticPassed. NativeW1Failed ordinary
cycle0at60.053s duringextraendRESET;selectedrecoverycancelledbythatfailureat45.830s,
notits120sbound. Baseline2000passed/295commandscompleted/30cyclespartial. Fullgates
notreached;W2–W4notstarted. SeeM5;noautomaticrerun/thresholdincrease.


### R27 — Approved explicit under-load RESET schedule (2026-10-29)

Owner approved [R27](declared-reset-workload-amendment.md). Remove extraendRESET
frompositivecycles; keep5tradingcommands/60s,R26one120srecovery/180stotal and
selectedcorrection. Add100scheduledRESETs/run,one/owner,<=1/s,from180s,selectedlast,
withdeclaredfault-awareoffsets. Requireselectedrecoverycompletebeforefirstoffer;
noautoextension. EachRESET60sincludingAPIpoolwait;independentcounters/IDs/timing,
all100completebyexistingduration+60s;noalteredpositivecounts/rates/durations.
DoesnotcertifyRESET20/s or100simultaneousRESETs,notaproductionratelimit.
R25/financial/authorization/resource/poolgates unchanged;oldFailedretained.
ReuseFixture.mutation/F15FaultGate/producer-supervision andoracles. Serialize only
per-ownerfinancial-marker evidence reads/cursorupdates whenRESET andfillsrecord
concurrently; no newfinancialwriteSQL/locks. CHECK is nonaccepting anddoesnot
substituteitsreducedownerfixtureforthe100RESETacceptanceprofile.


R27 fixture restoration detail: selectedowner temporarilyuseslimit5 forbreach/reset/
correctionoracles. Afterthoseanditsfirstfive-commandcyclecomplete,restoretheexisting
standardfixturelimit1000 viaoneexplicitINCREASEreceiptwithF-06/AUTHauthorization,thenmarkrecoveryreadyforproducer.
RecordthisoneINCREASE separately from100scheduledRESETs;noneofthethreshold5oraclesmove
oruse1000instead. Thisrestoresnormalpositive-fixtureconfiguration afterthetest,
withoutchangingdomainrules/productionlimits oraddingper-cycleRESETs. Itsreceipt
mustbeAPPLIEDandrecordedbeforeacceptance. KeepthisinsideR26normalbudget.

R27-A approved 2026-10-29 (owner: เริ่มทำ): restoration uses F-06 verified AUTH
authorization and INCREASE, not SET. One AUTH pool size1/overflow0 is added to
the complete parent inventory (6 pools, capacity +1), disposal and cleanup.
All other R25/R26/R27 gates remain unchanged. See declared-reset-workload-amendment.md.


### Approved bounded memory diagnostic — 2026-10-29

Owner explicitly requested implementation of the RAM-budget plan. Freeze current
R10/R22, monitor4 and allocations. One diagnostic only: native100x20 setup then
60s observation using the existing W1 dataset/rates/scheduling, not W1 acceptance.
Opt-in internal --memory-diagnostic-seconds60 collects VM meminfo/vmstat/PSI and
Docker actual memory usage/limit/cache/anon/optional swap/OOM state at roughly2s
intervals, alongside host paging and existing publication commit timestamps.
Collector failures/OOM and existing workload rejections/timeouts stop the run.
At60s cancel/join pending work and mark WINDOW_COMPLETE/acceptance_result=false;
that cutoff is not proof of complete cycles, financial gates or RESET coverage.
No added SQL in financial transactions, production code, allocation, API or schema
changes. Run sampler/cancellation tests and related static checks before the one
run. Record actual RAM versus limits and uncertainty; stop with one proposal or
specific missing evidence. No W1-W4, allocation changes or automatic repeats.


### Approved single VM-memory experiment — 2026-10-29

Owner instructed เริ่มทำ after the3072MiB VM-memory proposal. Authorizes changing
only Docker Desktop VM Memory to3072MiB, with prior actual control value recorded
for rollback. Per-container CPU/RAM/pools and R25/R26/R27-A financial gates unchanged.
One fresh100x20/60s diagnostic using the same sampler/source as the previous RAM
run; no W1-W4 or repeats. Record new effective VM memory/configuration and compare
aligned phases/counter rates. Roll back if guest pressure/source behavior worsens.
No claim of causal fix/acceptance from one short trial.


### Approved VM3GiB full W1 attempt — 2026-10-29

Owner instructed เริ่มทำ after the proposal for one full10min W1 on VM3GiB.
Accept this VM envelope for this attempt: UI3GiB, effective Linux MemTotal
3,043,373,056bytes; per-container CPU/RAM/pools, R10/R22/monitor4 and all R25/
R26/R27-A gates unchanged. Fresh0058DB,100owners x20orders,10commands/s,600s,
100 scheduled RESETs and selected restoration/oracles fully required. Native
acceptance invocation with no diagnostic cutoff/flags. Preserve source/config
and all failed historical runs. One W1 only; stop on failure, no automatic retry.
No W2-W4 in this attempt; report W1 evidence before progressing.


### Current W1 evidence — Passed 2026-10-29

Native600s W1 on approved VM3GiB passed for source
66ebee7611a412c5a15cc4af44a5ddda1637f0a0f8d383765e72580491a2b9c9.
100x20 baseline,6000commands/1200cycles,100scheduledRESETs,selectedauthorized
restoration and all3risk scenarios complete. Processingp95=247.939ms/p99=359.879ms.
Risk1,277,505expected=acknowledged,0unack/clockerrors,perowner/globalR25quota
passed;3lateinputs=3.044845s retained,0>5s. Financial/resource/physicalcleanup
gates passed. Full details/artifact linkage in evidence/m5-final-candidate.md.
This supersedes no historical Failed result and does not mark W2/W3/W4 or V21
complete; Paper remains Pending Full Validation,V22/V23 Pending Dependency.


### Approved W2 on unchanged VM3GiB candidate — 2026-10-29

Owner เริ่มทำ after W1Passed authorizes one native W2:100owners x20baseline,
100commands/s for300s with existing scheduledRESETs/selectedoracles/overflow
recovery and unchanged R25/R26/R27-A gates. Same source/VM3GiB/CPU/container
RAM/pools as passed W1; fresh0058DB, no diagnostic flags. Stop on failure,
no automatic retry or W3/W4 in this attempt. Preserve W1/historical evidence.


### Current W2 evidence — Failed 2026-10-29

Same source/config as passed W1 on VM3GiB. Native100commands/s/300s attempted;
at elapsed361.1s only1581/6000cycles complete versus360s total limit. Controlled
SIGINT stopped the still-running scheduler; final1622completed/100cancelled.
ScheduledRESET100/100APPLIED, but full30000commands/overflow/recovery/final SLA,
financial/resource gates not reached. Canonical deadline-stop.json and details
in evidence/m5-final-candidate.md. No automatic rerun or W3/W4; W1Passed remains
valid, V21/Paper Pending Full Validation and V22/V23 Pending Dependency.


### Approved bounded dispatch timeline — 2026-10-29

Owner เริ่มทำ after read-only W2 correlation authorizes one60s diagnostic with
W2 dataset/rates and same VM3GiB/CPU/RAM/pools/R10/R22/monitor4. Instrument only
harness wrappers around existing scan/claim/process/transaction/maintenance calls;
no SQL added or selectors/financial rules changed. Aggregate perworker/sec during
window (<=600SECOND records plus bounded setup/tail/closed summaries), <=100detail
records perPaperworker (<=1000total). Fivefixedordinaryowners; firstcycle subset
identified offline through durable request/order IDs; collected subset may include
latercycles/activepolls for thoseowners within the hard cap. Truncation/collector
failure makes attribution incomplete and stops run. ClaimNone is unclassified,
not assumed lock-busy. Work tags read existing command result_state, no query.
Internal --dispatch-diagnostic-seconds60 only with W2; worker-only --dispatch-trace.
Native acceptance defaults remain disabled. Reuse existing60s cancellation/join
and failure supervision. This is not W2 acceptance; RESETs at180s not covered.
Tests coveridentity/classification/transaction commit/rollback/collector errors/
restoration/cap/default-off before one workload; no automatic repeat or optimization.


### R28 — Approved W2 bounded saturation (2026-10-29)

Owner approve authorizes requirements, harness method and validation in
[w2-bounded-saturation-amendment.md](w2-bounded-saturation-amendment.md). This
supersedes the W2 all30000commands/360s gate only:6000nominalslots,<=100active
cycles/oneperowner, explicit unsubmitted backpressure,300sstartwindow/360sdrain,
allstartedcomplete,>=600completedcycles/everyowner>=1. Actual IDs/perownercounts
drive independent existing oracles; all R25/R26/R27-A safety/RESET/overflow/resource
gates retained. This is client-bounded saturation, not100incomingAPIrequests/s
or a production global queue bound. W1/W3/W4/F15 defaults unchanged; historical
W2Failed retained pending fresh evidence. No production API/schema/trading change.


R28 execution 2026-10-29: W2 **Failed/Partial**.1038cycles completed across all100
owners,5190logicalcommands,RESET100/100; then old economic_snapshot SQL referenced
nonexistent state.balance before overflow. Helper fixed via canonical wallet reader
and lock;2DBtests/lint/format/mypy586 passed. Independent offline receipt audit also
failed per-owner99.9%<=3s: oneowner3/2381late at3.053604s;globalquota passed,
237981/237981acknowledged,none>5s. Overflow/final financial/processing/resources
not certified. No automatic repeat; W1Passed retained, W3/W4 not started for this
candidate. Full details/source hashes/remaining gates in evidence/m5-final-candidate.md.


### R29 — Approved W2 owner service target (2026-10-29)

เจ้าของตอบ “อนุมัติ R29” ตาม [w2-risk-service-target-amendment.md](w2-risk-service-target-amendment.md).
เฉพาะ F18 Paper W2 bounded saturation: ready inputs ต้อง commit ผล/latch ภายใน
3s อย่างน้อย **99.5% ต่อ owner**; รวมทั้ง run คง **99.9%**, ทุก input คง **<=5s**.
ข้อยกเว้นนี้แทน R25/R28 เฉพาะ owner quota ของ W2; W1/W3/default คง99.9%.
นับด้วยจำนวนเต็ม เก็บทุก input/เวลารอ/late receipt; unacknowledged/clock errors
ยังต้องเป็นศูนย์. ยอมรับ quota ที่ล่าช้า3–5sต่อ owner เพิ่มจาก0.1%เป็น0.5%
เฉพาะช่วง saturation. ไม่เปลี่ยน production monitor, เงิน, freshness, fences,
authorization, deadlines, processing500ms/1s, RESET, overflow หรือ resources.
ใช้ sla_summary เดิมแบบระบุ phase และบันทึก owner/global targets แยก;
ทดสอบ boundary/default/missing ACK/hard limit ก่อน W2 ใหม่หนึ่งชุด. ถ้าผ่าน
ทุก gate จึงเริ่ม W3/W4 ตามแผน; หยุดเมื่อ failure ไม่วนรันหรือผ่อนเกณฑ์เอง.
ผล W2 เดิมยัง Failed/Partial; W1 ใช้ต่อได้เมื่อ default/dependencies ไม่เปลี่ยน.
Paper/F18 Pending Full Validation; V22/V23 Pending Dependency.


R29 W2 2026-10-29: **Failed** on native final result.1101cycles/5505logicalcommands,
RESET100/100,exactidentities/financials,processing485ms/748ms and R29risk quotas
passed on observed load. Required book cadence failed2299/3000; overflow timer
82.52s includes injection (retained injection receipts span>=75.21s); final inputlag
26>20. RAM/connection/physicalcleanup gates passed individually. No W3/W4/repeat.
These are remaining acceptance failures, not waived by R29; evidence and next
measurement-boundary/cadence decisions in evidence/m5-final-candidate.md.


### R30 — Approved harness measurement and coverage correction (2026-10-29)

Owner approve authorizes R30 in [M5 checkpoint](evidence/m5-final-candidate.md#r30-consolidated-harness-correction--approved-2026-10-29), including NC-R30-01:
price10Hz means10freshBTC and10freshETH observations/s, not lease-only frames or
repeated snapshots. Count committed source data in the fixed nominal window;
report setup/drain separately. Preserve all ready inputs in risk SLA. Historical
W1Passed remains recorded but cannot certify this missing price-load gate; no
automatic W1 reuse or rerun. R25–R29 numeric/safety/resource bounds remain.

Separate overflow injection/recovery/verification and total durations. Start60s
recovery just after final injection commit acknowledgement, before publisher
restart; complete only on captured-watermark progress, READY and consistent live
lag<=20. Normal final drain remains within duration+60; no extra waiting budget.
Check live recovery before stopping source/workers; retain final risk ACK drain
and record shutdown lag separately. W3 gets durable fault/restored/recovered
receipts, transaction-start fault attribution with full raw durations, idle-owner
coverage and fixed1800s RSS windows. W4 compares columnACL/policies/0058roles and
requires base and risk recovery verdicts plus exit0.

Reuse existing publishers, telemetry, resource/fault helpers and restore verifier;
keep shared F15 defaults compatible. Test-only observation helpers are grouped in
backend/tests/infra/risk_limits/profile_observations.py to avoid growing duplicate
phase/source/readiness logic. No production/API/schema/trading/allocation changes.
Implement and run affected tests/static only; the proposed60s measurement and
W1–W4 still require the stated separate authorization/preconditions.

### R32 — Approved Paper source cadence 5Hz (2026-10-29)

เจ้าของยืนยันปรับตาม [R32](paper-source-cadence-amendment.md): book BTC/USDT และ
fresh price BTC/USDT, ETH/USDT อย่างละ5Hzใน F18 Paper fixture เท่านั้น.
ป้อนทุก200msและนับunique actual commitsใน nominal windowเดิม; ไม่เปลี่ยน
100×20, command load, freshness, risk/processing SLA, safety, durations/resources.
ผล10Hzเดิมไม่เปลี่ยนเป็นPassed; ต้องมีหลักฐาน5Hzสำหรับcandidateสุดท้ายก่อนรับรอง.
R31childยังdiagnostic-only, ไม่เริ่มworkloadจากการปรับนี้.
