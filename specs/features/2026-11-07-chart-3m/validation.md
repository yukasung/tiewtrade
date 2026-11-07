# F-12 extension — กราฟ timeframe 3m — Validation

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-07**
วันที่: 2026-11-07
อ้างอิง: [requirements](requirements.md) Approved; [plan](plan.md) Approved
Implementation: **Owner review completed; two Medium findings addressed and affected checks passed**.
NC-3M-01 A อนุมัติและ implement แล้ว; ผล Failed เดิมคงอยู่ใน evidence/candidate.md
เจ้าของอนุมัติ refactor แล้วและ affected validation ผ่าน; required CI/local activation ยังไม่ได้ทำ และ Release workloads ยัง Pending Full Validation

| ID | เกณฑ์ / requirement | วิธีตรวจและหลักฐานที่ใช้ | ระยะ | ผล |
|---|---|---|---|---|
| V3-01 | schedule/retention — RQ03/04 | ขยาย tests/core/test_market_data.py, test_chart_history_bounds.py:180s, floor/ceil/advance/count, UTCข้ามวัน/ขอบเดือน/leap year, display3เดือน; ทุกTFเดิมเหมือนเดิม | Feature | Passed local targeted — core/time boundaries and SQL parity; see evidence/candidate.md |
| V3-02 | native source — RQ02/03/06 | tests/venues/binance_th/test_candles.py, test_candle_stream_mapping.py, test_candle_feed.py: request/subscription3mตรง, bound1000/7วันเดิม, wrong interval/series/OHLCV/finality/gap/reconnect; ใช้ fixtures/local fake stream ไม่ยิงLive order | Feature | Passed local targeted — native REST/feed/mapping regressions and real browser3m |
| V3-03 | SQL parity/validity — RQ03/05 | PostgreSQLจริงเทียบ floor/advance/slots/calculation bounds กับ PythonทุกTF; actual market-data/builder roles รับ180saligned ปฏิเสธendผิด/unaligned/unknownTF; core enum/OpenAPI/typesตรงกัน | Feature | Passed local targeted —9TF SQL/Python parity, actual-role constraints and populated migration |
| V3-04 | migration preservation/downgrade — RQ07/08 | populated0065→ใหม่→guarded downgrade: digest source/business facts, job identities/claims/checkpoints/grants/function owners/search_path/RLS ไม่เปลี่ยน; maintenance เดิมเปลี่ยน source fence, expire eligible generations และลบ heads เพื่อ rebuild ได้ตาม NC-3M-01 A; injected fault ต้อง rollback ทั้งหมด; non-IDLE writer ต้องปฏิเสธ; ว่าง3m down/upได้, มี3mในแต่ละตาราง/metadataแล้วปฏิเสธทั้งtransaction; concurrent insert vs downgradeต้องไม่สูญข้อมูล ใช้ฐานทดสอบแยก | Feature | Passed local targeted under Approved A — populated0065 upgrade/roundtrip, facts/ACL/schema, rollback, claimed writer/fence and concurrent downgrade guards |
| V3-05 | scheduling/readiness — RQ05 | ขยาย tests/services/indicator_builder/test_scheduler.py, infra/indicators/test_rollout.py และ infra/catalog/test_lifecycle.py: exact9TF/คู่ตามcatalog, baseline18series, cursorเดิม/wrap/new slots, หลายworkersไม่claimซ้ำ, stale revision/8TFเดิมไม่ผ่านreadiness9TF; ไม่เปลี่ยนcatalog/risk flags | Feature | Passed local targeted —18-series seed/fairness and fresh-schema catalog lifecycle; existing multi-writer claims regression passed; populated0065 cursor14/15 resume and18-series wrap passed |
| V3-06 | persistence/live/API — RQ02/05/06 | tests/services/market_data/test_candle_realtime.py, infra/market_data/test_chart_preview.py, api/test_candle_routes.py/test_chart_routes.py: native3m→stored→preview→confirmed→response, restart/fence/replayไม่ซ้ำ, safe input/auth/CSRF/session revocation, expiry/rate-limit/timeoutยังเดิม | Feature | Passed local targeted —native3m browser/history/live, preview/restart/fence and API auth/CSRF/admission regressions |
| V3-07 | UI/lifecycle — RQ01/04/06 | frontend/tests/CandlestickChartPanel.test.tsx, chart-candleTimeline.test.ts, chart-api/useChartData/useChartPages: option3mอยู่ระหว่าง1m/5m ค่าเริ่มต้น1h,180s/gaps, switch1m→3m→5m/คู่เร็ว/late response/logoutไม่ทับcacheหรือviewportเดิม; shared Select/admin-templateไม่เปลี่ยน | Feature | Passed local targeted —50 frontend tests, TypeScript and scoped ESLint passed |
| V3-08 | browser integration — RQ01..06/08 | ขยาย browser harnessเดิมให้ใช้PostgreSQL/APIจริงและrecorded/fake native3m: login→เลือกBTC/ETH3m→history/live→confirmed, pan/backfill/retry/switch/reload; exactOHLCVและno order/mode mutation; ไม่mockchart GETแทนทั้งflow | Feature | Passed local targeted —native3m BTC/ETH plus3 existing browser regressions; exact OHLCV/no order mutations |
| V3-09 | affected safety/static/review/CI — RQ05/08 | scoped Ruff/format/mypy, frontend ESLint/types/related tests, generated contract check, import boundaries; financial/risk/auth affected regressionsบนcandidateสุดท้าย; required CI/full regressionเพราะenum+SQLแชร์หลายfeature; review/finding closureและauthorized refactorตามAGENTS | Feature | Partial — scoped static/targeted tests passed; two review findings addressed; authorized refactor/affected validation passed; required CI pending |
| V3-10A | Chart workload/resource — RQ05/06 | F-12 V-17: BTC9TF, LEGACY/PREPAREDแยก, warmup60s+วัด600sต่อmode; profile/threshold/evidenceตามรายละเอียดด้านล่าง | Release | Not Run — Pending Full Validation |
| V3-10B | Prepared capacity/readiness — RQ05 | F-11 R2-C1..C6/R2-7 ตามF-38 RC-03..09: readiness BTC+ETH18series, workload BTC9series; C2+C5-steady3600s แล้ว C3+C5-dirty3600sเมื่อphaseก่อนผ่าน; fairness/resource/aggregateตามรายละเอียดด้านล่าง | Release | Not Run — Pending Full Validation |

## V3-10A — Profile กราฟและเกณฑ์ตัดสินที่ผูกกับต้นทาง

ต้นทาง: [F-12 validation V-17](../2026-10-12-candlestick-chart/validation.md#v-17-workload--acceptance--passed-หลัง-deterministic-rerun-2026-10-23)
และ [final deterministic profile/evidence](../2026-10-12-candlestick-chart/evidence/2026-10-23-v17-full-rerun.md).
ใช้ pair-scope amendment F-38 ที่หัว F-12 validation แทน30seriesในbaselineเก่า
ข้อเสนอ3mเปลี่ยนเฉพาะBTC workload8→9TF ไม่ขยายเป็นETH workloadด้วยโดยอัตโนมัติ

- ใช้ `backend/tests/services/market_data/profile_chart_workload.py` และ browser
  harness เดิม; isolated Linux/PG/Redis, APIและmarket-data processละ2CPU/1GiB
- ทั้ง9TF คือ1m/3m/5m/15m/1h/4h/1d/1w/1M; ข้อมูล3mเป็นnative fixture
  การสมัครstream/รายงานต้องรวม3m ไม่แปลงจากแท่ง1m
- แยก LEGACY/PREPARED เริ่มจากfixtureที่ควบคุมได้ต่อmode; warmup60sและวัด600sจริง
  ต่อmode,20authenticated clients/live poll2s,15events/sและburst150events/s10sทุกนาที
  พร้อม5history clientsกระจายทุก6sในรอบ30s, proof cadence15sและ100mount/unmount
- Controlled source failure/repair ครบ5seriesเดิม1m/5m/15m/1h/4hตามsource profile;
  failure/recoveryเฉพาะ3mต้องผ่าน V3-02/V3-06/V3-08 ก่อน ไม่ใช้workloadมาทดแทน

| เกณฑ์ | ต้องผ่านตามF-12 V-17เดิม |
|---|---|
| Latency | preview receive→commit p95≤3s; controlled source event→browser text p95≤5s; Live GET p95≤500ms และmax≤2sหรือtyped timeoutตามcontract |
| History/proof | success≤30s; PREPARED ready history p95≤3s; LEGACY1000-source fixtureสำเร็จ≤30sและsame-snapshotถูกต้อง; ห้ามpartial response |
| Resources | API/market-data incremental RSSแต่ละprocess≤128MiB; preview≤60rows; browser≤12000slotsและไม่growthหลัง100lifecyclecycles; process latest/queue slots≤18ตามruntime2คู่×9TF ไม่เพิ่มqueueต่อclient |
| Correctness/availability | countsต่อseriesและclientsครบ; typedfailureไม่ถูกนับเป็นsuccess; preserveexactOHLCV/finality, no leak, F09jobs/F10snapshotยังprogress, no order/mode mutations |
| Max input | F-11 R2-7 exact525600slotsเดิมและcleanup/parity/resource guards; ไม่เพิ่มseed horizonหรือใช้smokeแทน |

ผ่านเมื่อทั้งสองmodeครบduration/coverageและทุกthresholdผ่านบนcandidateที่ระบุ
ต้องเก็บraw request/failure/latency/resource/source-fault tracesและper-series inventory
ผล8TFเดิมคงเป็นหลักฐานของ8TFเดิม ไม่รับรองcapacity9TFจากการเปลี่ยนexpected counts

## V3-10B — Profile PREPARED และเกณฑ์ตัดสินที่ผูกกับต้นทาง

ต้นทาง: [F-11 performance-plan-v2 R2-C1..C6/R2-7](../2026-10-10-backend-indicators/performance-plan-v2.md),
[F-38 release checkpoint plan](../2026-10-15-supported-pairs-reduction/release-checkpoint-plan.md)
และ [F-38 RC-03..09/combined-phase amendment](../2026-10-15-supported-pairs-reduction/release-checkpoint-validation.md).
ใช้amendmentรวมC2/C5กับC3/C5เป็นสองphaseที่อนุมัติ2026-10-25 แทนแผนเก่าสี่phase
ข้อเสนอ3mขยายinventoryจาก2/16/1/8เป็น2/18/1/9เท่านั้น คงdenominator/เวลา/thresholdเดิม

| Checkpoint | Profile และวิธีตัดสิน |
|---|---|
| RC-03/R2-C1 | derived tablesว่าง, sourcefixturesพร้อม, ไม่มีprewarmนอกเวลา; readiness BTC+ETH9TFรวม18seriesและprobeGET200ครบภายในT0+600s, headage≤600s, แต่ละbuild≤120s |
| RC-04/R2-C2+C5-steady | หลังC1ผ่าน วัด3600sจริงบนBTC9TFพร้อมrejectedloadเดิม; sourceappendตามขอบTF; valid/freshREADYและacceptedGET200=100%ต่อseries; scheduledobservations/probesครบตามcadence10s/60s |
| RC-05/R2-C3+C5-dirty | เริ่มหลังsteadyทั้งสองgateผ่าน; invalidateBTC9TFพร้อมกันด้วยcommittedhistoricalOHLCupdatesในbounds, วัด3600sพร้อมrejectedload; recover≤600s, availability≥80%ต่อseries และหลังrecoverพร้อม100%จนจบ |
| RC-06/R2-C4 | per-series queue/claim/build/retry/publish/freshness traces; R2-S1..S5ผ่าน, ไม่starveเกิน600sและretry/pollไม่resetdeadline |
| RC-07/R2-C5 | ใช้สองcombinedphaseข้างต้น ไม่เพิ่มphaseซ้ำ; rejectedloadครบตามsourceprofileและถูกปฏิเสธก่อนcandlequery; ไม่ปนrejectedloadที่ตั้งใจกับacceptedavailabilitydenominator |
| RC-08/R2-C6 | C1..C5และR2-7/parityผ่านครบ; worker≤120s, RSSdelta≤128MiB, event-looplag≤100ms, ไม่มีmissing/skippedseries; failureในcombinedphaseทำให้gateคู่Failedทั้งคู่ |
| RC-09/metadata | ทุกphaseระบุ supported_runtime_pairs=2, runtime_readiness_series=18, profile_pairs=1, profile_series=9 พร้อมexplicitTFset; BTCworkloadไม่รับรองETHcapacity |

ใช้ `backend/tests/services/indicator_builder/profile_capacity.py`,
`profile_capacity_steady.py`, `profile_capacity_evidence.py` และfairness harnessเดิม
เก็บrevision/image/config/schema/fixture digests, observations/probes/rejected/worker
metricsและmachine-evaluatedaggregateครบตามต้นทาง; ไม่ใช้smokeหรือpartialปิดfullgate

## ระยะรัน การใช้หลักฐานเดิม และจุดหยุด

- V3-10A/B เป็น **Release** ที่checkpointชุดที่9ตามtesting workflow ไม่รันในรอบแก้เอกสาร
  หรืออัตโนมัติหลังทุกpatch; การอนุมัติแผนพัฒนาไม่ใช่คำสั่งเริ่มcampaignชุดยาวทันที
- การปรับinventory/harness9TFเป็นข้อเสนอในplan/validationฉบับนี้ รออนุมัติก่อนimplement
  ไม่แก้เอกสารF-11/F-12/F-38หรือผลเก่าให้กลายเป็นผล9TF
- F-09 correctness/concurrency/retry/finality/permissions ที่กระทบยังเป็นFeature gates
  V3-02/03/04/06 โดยtraceไปF-09 V-3..6/V-9..16/V-18..27 ไม่เลื่อนไปRelease
  [F-09 validation](../2026-10-07-market-data/validation.md) ไม่ได้กำหนดtimedcapacitycampaignใหม่สำหรับงานนี้
- ก่อนcampaignให้ทำprovenance auditแบบF-38 RC-02: อ้างSHA/config/schema/harness
  และระบุผลเดิมที่ยังvalidรายเกณฑ์; เปลี่ยนseries inventoryทำให้ใช้ผล8/16series
  ปิด9/18seriesไม่ได้ แต่ใช้proofเดิมที่ไม่ขึ้นกับinventoryได้เมื่อพิสูจน์dependencyครบ
- ต้องตรวจisolation/network/evaluatorก่อนรัน; phaseล้มหรือหลักฐานไม่ครบให้หยุดphaseถัดไป
  เก็บFailed/Incompleteและเสนอทางแก้ ไม่retryอัตโนมัติหรือเปลี่ยนdenominator/threshold
- ระยะวัดเมื่อจำเป็นต้องรันทั้งชุดใหม่: chart2×(60+600)s=22นาที;
  preparedcombined2×3600s=120นาที เพิ่มC1≤600sตามเกณฑ์ผ่านและR2-7/fairness/setup/cleanup
  ที่ยังต้องประเมินจากcandidateจริง ตัวเลขนี้ไม่ใช่เวลาจบทั้งหมดหรือคำสั่งเริ่มรัน

## วิธีเลือกและรัน checks

- เริ่มจาก suites เดิม เพิ่มเฉพาะเคส3m/ความเสี่ยงที่ยังไม่มีหลักฐาน
- Locking/RLS/transaction/downgrade guard ต้องใช้PostgreSQLจริง ไม่ใช้mockแทน
- ใช้ฐานว่างหรือisolated fixturesตามpatternเดิมสำหรับtestsที่ต้องคุมglobal state
  ห้ามรันทดสอบที่ seed/reset/downgrade ลงฐานlocalที่เจ้าของใช้งาน
- ระหว่างพัฒนารันtargetedชุดเล็กสุดที่ครอบdiff; หลังfixรันfailed+affected regression
  และคงผลเดิมที่ยังvalid ไม่เพิ่มfull local suiteเพียงเพื่อความมั่นใจ
- Native public-data smokeถ้าจำเป็นให้แยกจากautomated fixture tests ระบุขอบเขต/เวลา
  ไม่ให้การขาดnetworkกลายเป็นPassed หรือใช้ลดเกณฑ์finality/freshness
- ไม่มีtimed workloadใหม่ในscopeพัฒนา; ก่อนcross-feature E2E/ชุดยาวแจ้งขอบเขต/เวลารวม
- ประมาณการเบื้องต้นtargeted regression/DB/browser/staticหลังcandidateนิ่ง15–30นาที ขึ้นกับเครื่อง
  ไม่รวมพัฒนา/แก้failure; required CIใช้รอบล่าสุดราว25–30นาทีเมื่อเจ้าของอนุญาตGit

## บันทึกผลและความหมายของเสร็จ

บันทึกลง evidence/candidate.md เมื่อมีผลจริง: SHA/diff, source/config/schema,
คำสั่ง/จำนวนcases/เวลา, failureและข้อจำกัด, coverage V3-01..09/V3-10A/B และการใช้ผลเดิมต่อ
ยังไม่สร้างPassedล่วงหน้าหรือเปลี่ยนผลเก่าเป็นPassed

Feature gates V3-01..09ต้องผ่านก่อนmerge พร้อมreview/required CIบนSHAสุดท้าย
V3-10A/BคงPending Full ValidationจนRelease checkpointถึงกำหนดและผ่านจริง
Ready for Code Reviewเป็นจุดหยุดรอเจ้าของตามAGENTS; commit/push/mergeแยกคำสั่ง
ย้ายruntimeและmigrateฐานlocalได้หลังผ่านด่านตามplan ไม่อ้างว่าตรวจสำเร็จเพียงเพราะ
ธงเปิดหรือmigrationผ่าน; งานนี้ไม่ทำให้F17หรือF12Completedเอง

## Review finding closure — 2026-11-07

Medium เรื่องworkloadtraceabilityแก้ในเอกสารแล้ว: แยกV3-10A/Bเป็นReleaseชัดเจน
ผูกprofile, inventory, duration, thresholdsและartifactกับF-12 V-17/F-11/F-38
โดยใช้combinedphaseamendmentล่าสุด ไม่เพิ่มรอบ4ชั่วโมงตามbaselineที่ถูกแทนแล้ว
ยังเป็นProposedและไม่มีcampaignถูกเรียก ผลทุกข้อยังNot Run

High เรื่องยังไม่มีimplementationคง **Open — awaiting plan/validation approval**.
คำสั่งแก้findingเอกสารไม่ถูกบันทึกว่าเป็นการอนุมัติplanหรือผลtestผ่าน
ขั้นถัดไปให้เจ้าของอนุมัติplan/validationฉบับนี้ แล้วจึงimplementP1–P3และตรวจFeature gates


## Implementation checkpoint / approval stop — 2026-11-07

Owner approved plan/validation before implementation. Prior awaiting-approval text
in the review closure above is historical; implementation is now Partial/Failed.
[Current evidence](evidence/candidate.md) retains failures and the exact scope of
passing checks. NC-3M-01 blocks populated migration/local activation; no source guard
was bypassed. Next requires owner A/B decision on the maintenance amendment before
changing this contract. No Ready for Code Review, Git publication or long campaign.

## NC-3M-01 A approval — 2026-11-07

เจ้าของอนุมัติ maintenance เดิมพร้อม derived rebuild; เปลี่ยน preservation contract
ตาม RQ-3M-07/P2.5 ก่อนแก้ implementation ผล Failed เดิมคงเป็นประวัติ
ผลทดแทนยัง Not Run ณ จุดอนุมัติ ไม่ใช้คำอนุมัติแทนผลทดสอบ

## NC-3M-01 A implementation result — 2026-11-07

Replacement migration checks passed14/14 on newly migrated isolated databases.
Old failure retained; not reclassified as a pass. Source maintenance runs only after
writer drain and, for downgrade, after every3m inventory guard. Derived heads are
removed and eligible generations expire as approved; source rows, jobs/checkpoints
and function privileges persist. Rollback and old source-fence rejection passed.

Fresh-schema regression310, native/preview/candleAPI113 and chartAPI39 passed.
ChartAPI first setup lacked its test Redis URL;39 setup errors retained, then corrected
isolated test environment and reran only the affected suite on another fresh DB.
Browser native3m1 plus existing regressions3 passed; seed fixture uses bounded regular
rounds without changing production fetch limits. Frontend50/static evidence remains valid.
See [candidate receipt](evidence/candidate.md) for scope and retained historical failures.
Next: owner `review code`; stop before review/refactor/local activation/commit.

## Review correction checkpoint — 2026-11-07

M1: distinct rendered native3m series + real browser response assertions passed1/1;
shared fixture/browser regressions passed3/3. M2: populated0065 cursor14/15 preservation,
remaining-round fairness and complete18-series next round passed2/2 after fixing unequal
fixture deadlines; initial14existing cases passed. Retain the initial2failed tests as
fixture failures in candidate evidence. Scoped static checks passed.

Next requires owner `refactor the code` per AGENTS. Do not infer merge/CI/Release
acceptance from this correction; production source and owner runtime were not changed.

## Authorized refactor validation — 2026-11-07

Owner authorized refactor; affected cursor cases2/2, native3m browser1/1 and shared
browser regressions3/3 passed. Scoped Ruff/format/mypy, frontend ESLint/TypeScript and
whitespace checks passed. Existing correctness evidence remains valid where unchanged.
V3-09 remains Partial until required CI on final candidate; V3-10A/B remains Not Run /
Pending Full Validation. No runtime activation or Git mutations. Next: owner Git command
for commit/push/PR, then required CI; local activation follows successful Feature gates.
