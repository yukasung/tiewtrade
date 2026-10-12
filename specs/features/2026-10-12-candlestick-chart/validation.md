# F-12 — กราฟแท่งเทียนบนหน้าเว็บ — Validation

สถานะ: **Approved** — เจ้าของอนุมัติพร้อม plan.md วันที่ 2026-10-12; ผลแต่ละด่านติดตามตามหลักฐานจริง
วันที่: 2026-10-12
Branch: feature/f-12-candlestick-chart
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [หลักฐานต้นทาง](source-evidence.md)

## เสร็จหมายถึงอะไร

ก่อน Completed/release ทุก V ด้านล่างต้องมีหลักฐานและผ่าน
ไม่ใช้การอนุมัติ spec หรือ smoke แทนผลทดสอบชุดเต็ม.
ก่อน merge ต้องผ่านด่านความถูกต้อง/ความปลอดภัยและ V-18 ที่ไม่เลื่อนตามมาตรฐาน.
จุดเข้า/ออกจริงไม่เป็นด่านรอบนี้ตาม NC-40 แต่ติดตามใน roadmap ต่อไป.
F-12 ไม่รับรอง production PREPARED หรือ Live readiness แทน F-11/ชุด9.

| รหัส | เกณฑ์ / วิธีตรวจ | Requirements | ผล |
|---|---|---|---|
| V-01 | Public contract/fixture, adapter partial ordering และ dependency/license checks ตามรายละเอียดด้านล่าง | 2/9/22/25/26 | Partial |
| V-02 | Parser/feed state properties: หน่วย/UTC/รูปร่าง/ordering/conflict/duplicate/reconnect/epoch | 2/3/9/25/26 | Partial |
| V-03 | Bundle OHLC/indicator อ่าน snapshotเดียวและค่าตรง F-11 แบบ LEGACY/PREPARED | 3/6/7/9 | Partial |
| V-04 | Proof ครอบ seed/gap/finality/retention/DDL; CHANGED/UNKNOWN ไม่มี overlay/tooltip | 7/8/11 | Partial |
| V-05 | Cursor/display proof tamper/MAC/purpose/session/expiry/cross replica;ไม่มี token log | 7/11/17/19 | Partial |
| V-06 | Budget/abort/timeout cleanup, no partial bundle; endpoint F-11 เดิมไม่เปลี่ยน | 10/11/16/18 | Partial |
| V-07 | Actual-role migration/grants/lease/fenced preview≤60 rows และ rollback | 1/17/23/25 | Partial |
| V-08 | Internal demand coalescing กับ F-09 users/worker; end boundary/fetch proof/commit | 9/12/13/25/28 | Partial |
| V-09 | Freshness/recovery/Restart/Redis failure/slowconsumer/control limits | 14/15/25/26/27 | Partial |
| V-10 | Auth/CSRF/routingไม่ต่อ session/machine/hidden/401/unsupported input | 1/2/18/19/23 | Partial |
| V-11 | Readiness/refresh controller finite state และเงื่อนไข retry/stop | 11/12/13/16/18/28 | Partial |
| V-12 | Exact text/numeric boundary/renderer whitespace/continuoussegments | 3/5/7/8/17/21 | Partial |
| V-13 | Viewport/page load/history cap/series switch/late response/StrictMode cleanup | 2/5/10/18/20 | Partial |
| V-14 | จริงใน Chromium: chart/panes/crosshair/keyboard/resize/ไทยอังกฤษ/attribution | 4/5/6/20/21/22 | Partial |
| V-15 | Browser→API→PG→fake venue worker→bundle/preview/refresh ครบทาง ไม่ mock APIทั้ง flow | 1/3/7/12/13/25/27/28 | Partial |
| V-16 | ภาพ/ข้อความ loading/empty/partial/unconfirmed/stale/failure แยก และไม่มี trading action | 8/9/14/15/23/24 | Partial |
| V-17 | วัดทรัพยากร/latency/budgets ตาม workload ที่กำหนด ไม่มี starvation จาก chart | 10/16/18/25/27/28 | Pending Full Validation |
| V-18 | ด่าน CI/full regression/security/architecture/generated API/build + review/manualผ่าน | ทุกข้อ | Partial |

ผล Partial อ้างอิง [สรุปผลและรายการค้างล่าสุด](evidence/checkpoint.md),
[รายงาน local preview รอบก่อน](evidence/dev-preview.md) และ snapshot ที่ระบุในรายงาน
ยังไม่ถือว่าผ่านทั้งด่าน; V-17 และเกณฑ์ที่ยังขาดต้องตรวจครบตามระยะรันด้านล่าง

## ระยะรัน — เจ้าของอนุมัติปรับ workflow 2026-10-12

ที่มา: คำสั่งเจ้าของ “Defer full performance validation to release checkpoints”
และ “Record deferred criteria as Pending Full Validation” ในรอบปรับ workflow.
การอนุมัตินี้เปลี่ยนเวลารัน ไม่เปลี่ยน requirements/plan หรือเกณฑ์รับรองผล.

| ระยะ | เกณฑ์ที่ตรวจ |
|---|---|
| ระหว่างพัฒนา | V-01..16 ตามผลกระทบของ code/dependencies รวม correctness/security/concurrency และ smoke ของ bounds/cleanup/recovery ที่จำเป็น |
| Candidate ก่อน merge | V-01..16 ครบพร้อม review/manual ที่กำหนด และ full regression/static/build/contracts/required CI ใน V-18 เมื่อโค้ดนิ่ง |
| Release checkpoint / ชุดที่ 9 | V-17 ชุดเต็มทั้ง LEGACY/PREPARED และส่วนสรุปผล V-18 ที่พึ่ง V-17 ก่อน Completed/production activation/ใช้เงินจริง/เปิดให้คนนอก |

V-17 เป็น `Pending Full Validation` จนรันครบ workload/ระยะเวลา/thresholds เดิม.
หากพบความเสี่ยงจากการเปลี่ยนแปลงที่ smoke พิสูจน์ไม่ได้ ให้ตรวจส่วนที่จำเป็นเร็วขึ้น
ตาม `standards/testing.md` หัวข้อ 7 โดยไม่เลื่อน correctness/trading safety ตาม benchmark.
เก็บ Failed/Partial เดิมและหลักฐานไว้ ไม่ใช้สถานะ Pending กลบผลที่ล้ม.
ทะเบียนงานค้าง: [roadmap ชุดที่ 9](../../roadmap.md#ทะเบียนงานค้างสำหรับชุดที่-9).

## V-01: หลักฐานต้นทางก่อน implementation

- เก็บ raw public fixture จำกัดไม่เกิน2connections/60s รวม≤100frames/file
  สำหรับคู่อย่างน้อย BTC/ETH และ six intervals; ไม่ใช้ key ไม่ส่งออเดอร์.
  บันทึก request/subscription, ack, UTC/timeouts/counters และ raw decimal strings.
- รอบที่เก็บ x=true ถ้าสังเกตไม่ได้ให้ระบุ Not Observed ใช้ synthetic fixture
  ทดสอบ path โดยไม่อ้างว่า source CLOSED ถูกพิสูจน์. รอบนี้ history ยังคง UNCONFIRMED.
- ตรวจ undocumented fields/absence, combined envelope, inclusive end, progress
  และเหตุที่ไม่ใช้ E เป็น total order. If actual observation ขัด acceptance rule
  ต้องแก้ Proposed plan/ขออนุมัติใหม่ก่อน decoder ห้าม relaxparserเอง.
- ตรวจรุ่น Lightweight Charts5.0.9 จาก official package/release/license จริง
  pin exact lockfile; React18/Vite6/Node22 buildผ่านก่อนรับdependency.
  ตรวจ panes API/whitespace behavior ด้วย real library ไม่ผ่าน mockอย่างเดียว.

## Fixtures / properties ที่จำเป็น

Fixture เงิน/ปริมาณเป็น string และ timestamps explicit ไม่ใช้ค่าตลาดจริงเป็นสูตรอ้างอิง.
ตัวอย่าง OHLC: open=100.000000000000000001, high=101.000000000000000001,
low=99.000000000000000001, close=100.500000000000000001,
volume=2.000000000000000001; tooltipต้องอ่านข้อความเดิมทุกหลัก.
วาดเป็น approximation ได้ตาม NC-41 แต่ exact cache ต้องไม่ถูกเปลี่ยน.
เพิ่ม underflow/overflow, zero/negative Scalar ที่ validตามF-11 และหน่วยต่างกัน.
ไม่เอา validator ของ renderer มาใช้สร้าง expected values.

V-02 ใช้ Hypothesis ใน Pythonสร้าง sequences ที่ valid/invalid:
duplicateไม่เปลี่ยน revision, frameเก่าไม่ทับใหม่, sameprogress/conflictingOHLC
ทำให้ไม่พร้อม, epochเก่าหลังreconnect/leasehandoffไม่publish,
unknownseries/boolแทนint/endalignment/invalidunit/malformeddecimal failclosed.
ทดสอบกฎ dominance โดยสร้างลำดับคงที่แล้วสับ/ซ้ำ และพิสูจน์ว่าไม่มีการเลือก
conflictด้วย timestamp/arrival. ไม่เพิ่มกฎ monetary range ใหม่.

V-03/04 ใช้ PostgreSQL snapshot barriers จริงกับ rolesจริง:
- writercommitก่อน/ระหว่าง/หลังbundle; bundleหนึ่งหน้าเป็นชุดเดียวครบ
  และ values/statusตรง F-11 parity reference เดิม ทั้งสอง mode.
- เปลี่ยน seedก่อนviewport, backfillgap, finality/fetch_started_at,
  เปลี่ยน OHLC ใน output, source reset, journalGC, generationexpiry และcleanup
  ต้อง CHANGED/UNVERIFIABLE ไม่ได้ค่ารุ่นใหม่แทรกเข้า tokenเก่า.
- แท่งที่อยู่นอก [L,U) ไม่เปลี่ยนค่าหรือ invalidates historyที่ยังพิสูจน์ได้;
  การเลื่อน cutoff/partitionมีผลตามF-11เดิม ไม่ reseedเพื่อให้ตรวจผ่าน.
- LEGACYตรวจrevisionเต็มด้วยreaderเดิม; ไม่เปิดgate PREPAREDในtestเพื่อหลบfallback.
  PREPAREDใช้generation/checkpoint/sourcejournalจริง ไม่stub proof_valid.
- multi-page 409 หลังมีหน้าสะสมต้องทิ้งทุกหน้า; ไม่มี candleหน้าใหม่ทับเส้นเก่า.

## V-05..10: Backend integrity

- Tokenคนละpurposeต้องใช้แทนกันไม่ได้; loginคนเดิมต่างsession, userอื่น,
  current/previous kid, invalid/retired kid, whitespace/oversize/MACผิด,
  expiryตรงขอบ6h/session/generation ตรวจแบบ frozen DBtime; errorไม่echo input.
- cancellationระหว่าง scan/source query/serialization และ repeated cancel
  cleanup≤2s/connectioninvalidate; slotยังheldจนงานหยุดจริง พิสูจน์reuseได้.
  response2MiBพอดี/เกิน และ input1000/1001slots; ไม่มี partial arrayเมื่อผิดพลาด.
- preview ownerสองตัวแข่ง, leaseหมด, ownerเก่ากลับช้า, commitrollback,
  Redis lost publish และ restart. actorเก่าไม่มีwriteจากepochที่หมดสิทธิ์.
  actualAPIเขียนpreviewไม่ได้; rolesอื่น/secret/audit/orderไม่มีgrantเพิ่ม.
- demandอัตโนมัติ+user requestช่วงเดียวกันมีjob/workerleaseเดิม;
  ไม่resetactivecursor/attempt/backoff; transactionrollbackไม่ประกาศสำเร็จ.
  RESTfetchเริ่มก่อนend_atแม้ตอบหลังยังไม่ผ่าน; หลังend_atcommitแล้วจึงเข้าF-11.
- stream xtrueไม่สร้างCLOSED, previewไม่เข้าตารางsourceF-11;
  ไม่มี financialfloatingpoint ในbackend/DB/newparser.
- freshness6sตรงขอบ/เกิน1µs, eventอนาคต2sตรงขอบ/เกิน, frameค้าง,
  heartbeatโดยไม่มีข้อมูล, Eเก่าแต่receivedใหม่; statusesอิงsnapshotserver.
  เวลาในbrowserถูกปรับ±1hต้องไม่เปลี่ยนfinality/READYของserver.
- REST/backfillล้ม recoveryต้องไม่READY;
  latestslots/coalescing/backpressure ไม่ทำให้queueโตตามframecount.
- แยก Redis failure สองกรณี: (1) notification/invalidation หายหรือ publish
  ล้มหลัง commit แต่ admission ยังใช้ได้ ให้ Live GET อ่าน preview ล่าสุดจาก PG
  ได้; ไม่ rollback commit หรือเปลี่ยน feed readiness เพียงเพราะ notification หาย.
  (2) admission timeout/Redis ใช้งานไม่ได้ รวม Redis ล่มทั้งระบบ ให้ Live GET
  คืน503 CHART_ADMISSION_UNAVAILABLE โดยไม่เรียก preview reader/ไม่ bypass
  admission/ไม่ใช้ local counter; browser หยุด auto poll และไม่เริ่ม readiness
  episode. History/verify ต้องคง admission/error contract ของ F-11 เดิม.
- no-session/expired/revoked, POSTverifyขาดCSRF/invalidorigin,
  machine GET/POSTทั้งหมดไม่ต่อexpiry; manualF-09POSTคงroutingเดิม.
  testsenumerate routepolicyเพื่อจับ endpointใหม่ที่เผลอpublic/renewing.

## V-11..16: Controller และ browser

ใช้ fake timers ที่ monotonic + controlled HTTP delays ตรวจ actual query calls:
- initial503notready→poll≥10s/Retry-After→200bundleที่MATCH แสดงได้;
  503รหัสอื่น/429/504/422หยุด ไม่มีrefetchจากfocus/networkมาเปิดงานเอง.
- episodeรวม12คำขอ/300sตรงขอบ; request30sและลดdeadlineตามremaining;
  คำขอช้ากับevent100ครั้งไม่resetbudgetและไม่ส่งrequestซ้อน.
- 409จากหน้าถัดไปหรือexpiryได้restartเพียง1ครั้งทั้งepisode;
  numericfailureต่อด้วยeventรุ่นเดิมไม่retry; token/codeต่างกันไม่เพิ่มrestartquota.
- exhaustedepisode+streamใหม่ยังstopped; manualtryใช้admission/cooldown;
  successfulREFRESH_REQUIREDจบรอบโดยไม่มีPOSTหรือreadinessloopต่อ.
- POST202→pollF-09ไม่เกิน6ครั้ง/60s→bundle; POST200อ่านbundleใหม่;
  FAILED/UNAVAILABLE/pollerror/401/timeoutหยุด ไม่มีค่าค้างอ้างว่าล่าสุด.
- proofเปลี่ยน/UNKNOWN/TTL45s ต้องไม่มีindicatorseriesและtooltipเก่า;
  OHLCของbundleยังผูกas_ofชัด; livepreviewoutsideUไม่invalidateshistoryเอง.
- switch A→B→A/delayedA, unmount, hidden→visible, logout/remount,
  StrictMode doubleeffect; stalecallbackไม่เขียนcache/render.
- 12,000slotscap: pagination/evictionรักษาviewportและseed; เปิดช่วงเก่าได้ใหม่
  ไม่เดาว่าข้อมูลตลาดหมดเพราะbrowsercacheevict.
- realchartอ่านexacttextกับapproximateaxisถูกต้อง; Gaps/WARM_UP/
  REFRESH_REQUIREDไม่ลากเส้นเชื่อม; volumezeroจริงต่างจากmissing.
- widths375/768/1440และthemeเดิม, pane scale/legend/keyboardlabels/ThaiEnglish,
  timezoneขอบวันUTC→Bangkok, attribution/logo/linkไม่ถูกUIทับ.

E2Eขั้นต่ำ 6 flows: (1) login→เลือกคู่/timeframe→chart+ราคาสด,
(2) previewupdate/แท่งใหม่→RESTcommit→indicatorbundle,
(3) seedmutation→hide→boundedrebuild, (4) refresh+gap+failure,
(5) network/Redis/workerrestart→recovery, (6) revoke/logout→stoprequests.
อย่างน้อยflows1/2/3/5ใช้DBจริงและFakeVenue/streamserverที่ควบคุมได้
ไม่mockGETchart/indicatorเพื่อแทนbackendทั้งflow. Fixturesmockเฉพาะfailure
ที่ต้องทดสอบclientและมีbackendintegrationแยกพิสูจน์สัญญาเดียวกัน.
Browser networkassertไม่มี Binance requests หรือ order/modechange endpoints.

## V-17: Workload / acceptance — Pending Full Validation ที่ release checkpoint

สภาพแวดล้อม Linux2vCPU/1GiB สำหรับAPI/market-data ตามฐานF-11,
PG/RedisแยกตามComposeเดิม; ChromiumNode22 บันทึกversion/seed/digest.
รันisolatedไม่ใช้ตลาดจริง 10นาทีหลังwarmup60s:
30candle series, 15events/sปกติและburst150events/s10sทุกนาที,
20authenticatedclientsมีlivepoll2s, 5clientsสลับhistoryทุก30s
และproofตาม15s; 5seriesมีsourcecommit/seedmutation/gaps/failedrefresh.

| เกณฑ์ | วิธีตัดสิน |
|---|---|
| Previewreceive→PGcommit | p95≤3s; requestsourceevent→browsertext p95≤5sในcontrollednetwork; ไม่เอาระยะeventproductionต้นทางมาปน |
| LiveGET | p95≤500ms, max≤2sหรือtypedtimeout; slowqueryไม่แย่งF-11pool |
| Queues/rows | preview≤60rows, processqueueslatest≤30series; browser≤12,000slotsและไม่มีgrowthหลัง100mount/unmount |
| Resource | market-data/API incrementalRSSรวมแต่ละprocess≤128MiB, no leakedconnections/listeners/slotsหลังcancel |
| History/proof | ทุกคำขอ≤30sหรือtypedfailureและไม่มีpartial; preparedready workload history p95≤3s; LEGACY1,000sourcefixtureต้องสำเร็จใน30sและsame-snapshotถูกต้อง |
| Starvation | F-10 snapshot/controlและF-09 activejobsยังprogress; sourcewritesไม่blockedเกินtimeoutsเดิม; burstไม่สร้างfeedconnectionต่อuser |
| Max-input correctness | ใช้F-11fixture525,600slotsเดิมตรวจnoout-of-bounds/noallocationallrows/timeoutcleanup; ไม่อ้างว่าปิดcapacity/loadgateF-11จากผลนี้ |

วัด LEGACY/PREPAREDแยก; PREPAREDใช้จริงในisolatedDBพร้อมrolloutinventory/evidence
ไม่activateproduction. เลื่อนเวลารันตามการอนุมัติ workflow ข้างต้นเท่านั้น
ห้ามลดเกณฑ์ ลบผลที่ล้ม หรือใช้ smoke รับรองว่าผ่าน V-17.
ถ้าLEGACYmaxinputอ่านไม่ได้ในงบ ให้แสดงข้อจำกัดตามจริงและติดตามในผล ไม่เรียก
ว่าavailabilityพร้อมครบ365วัน; ต้องเสนอวิธีแก้/ขอคำตัดสินก่อนรับรองพร้อมใช้งานจริง.

## ตรวจด้วยมือและด่านก่อนส่งงาน

รายการด้านล่างเป็นด่าน candidate ก่อน merge ไม่ใช่คำสั่งให้รันครบหลังทุก patch/ทุกงาน
ระหว่างพัฒนาเลือกตามผลกระทบ และใช้ผลเดิมได้เฉพาะเมื่อ inputs ที่เกี่ยวข้องยัง valid.
V-17 และส่วนสรุป V-18 ที่พึ่งรอบนั้นรอ release checkpoint ตามตารางระยะรัน.

เจ้าของตรวจchartจริงผ่านdevenvironmentพร้อมfixture: viewport/เลือกแท่ง/ทุกpane,
ทั้งภาษา/มือถือ, disconnect/stale/unconfirmed, refresh/stopและไม่มีtradingaction.
เก็บ screenshot/time/environment/failure ตามจริง ไม่ใช้mockupเป็นหลักฐานผ่าน.
ผลแต่ละVต้องระบุคำสั่ง/exitcode/artifactpath; failed/partialไม่เปลี่ยนเป็นpassed.

Backend: `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy`, `uv run lint-imports`, `uv run pytest` พร้อมPG/Redisจริง.
Frontend: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`,
`npm run build`, `npm run test:e2e` ตามCIจริง.
Export `uv run python -m tiewtrade.services.api.openapi_export`,
`npm run gen:api` แล้วตรวจgenerateddiffว่าตรงcommitก่อนmerge.
venue_contractแยกจากเทสต์ปกติ ไม่มีkeyและใช้boundedpublicrequestsเท่านั้น.
review/finalcheckต้องผ่านแล้วจึงอัปเดตroadmapตามผลจริง;
commit/push/mergeยังต้องเจ้าของสั่งแยกต่างหาก.
