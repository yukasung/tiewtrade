# F18 M5 — candidate review and release validation

วันที่ 2026-10-27; branch `feat/f18-wallet-risk-limits`. In Progress; ยังไม่ Completed,
ไม่ใช่ production activation และยังไม่มีคำสั่ง commit/push/merge.

## Resume and review checkpoint

เจ้าของให้รอ F38 ก่อน workload. กลับมาทำต่อหลัง roadmap ระบุ F38 Completed
และไม่พบ workload/pytest process ค้าง. ใช้ PostgreSQL/Redis แยกของ F18;
ไม่หยุดหรือแก้ services ของ worktree อื่น. รัน checks/workloads ตามลำดับ ไม่ซ้อนกัน.
แจ้ง **Ready for Code Review** แล้วใน M4 ก่อนเริ่มรีวิว; checkpoint นี้ไม่ขออนุมัติซ้ำ.

### Findings ที่ตรวจในรอบนี้

- Medium: risk evidence singleton joins มี estimate 2,550,000 rows บน fresh DB
  ทำให้เปิด JIT โดยไม่จำเป็นและยืด financial fence. จำกัด input ของ singleton tables
  ด้วย LIMIT1 ตาม PK/CHECK ที่รับประกันหนึ่งแถวอยู่แล้ว; ไม่เปลี่ยน source/holdings/
  revision/price/latch checks. EXPLAIN ANALYZE query เดิม ~64.963ms (JIT23.06ms),
  query หลังแก้ ~9.605ms ไม่มี JIT. ยังต้องผ่าน affected safety/full regression/SLA.
- ข้อสงสัย manual request cutoff ถูกถอน: migration0041 ใช้ clock_timestamp() อยู่แล้ว.
  คง implementation เดิมและเพิ่ม real DB regression: API transaction เริ่มก่อน stop,
  INSERT หลัง reset ต้องไม่ถูก enroll/reject จาก stop เก่า. Test ผ่านพร้อม old-cut test.
  Migration0055 ทดลองถูกถอน ไม่ใช่ schema candidate. Scratch DB ที่มี0055ไม่ใช้ตรวจรับ.
- Harness: normalize driver UUID ก่อนเข้า strict domain scope; partial resting GTC
  ต้องมี ordered trade evidence แทนการหวังให้ replenished depth fill เอง.
- Harness: F15 resource sampler เดิมรองรับ Windows/Linux; เพิ่ม macOS ps sampler
  ใช้ accumulated CPU seconds/RSS bytes และคง thresholds เดิม. Unit test ตรวจ units,
  day/time conversion และ missing process ต้อง fail ไม่หายจาก resource accounting.
- Harness provenance เพิ่ม source commit/tree digest, market fixture digest, runtime,
  host logical CPUs และ configured risk pool sizes. Schema/settingsอยู่ manifest เดิม.

## Checks ล่าสุด

- stop/execution/manual bridge affected: 23 passed (รวม post-reset/older transaction).
- SLA proof + workload supervision/resource parser: 8 passed,0.78s.
- Backend mypy550files passed; ruff check passed; ruff format609files passed.
- Import contracts7kept/0broken,280files/1960dependencies.
- M4 frontend296และbrowser3flowsยังเป็นหลักฐานเดิม; financial oracle assertionsที่เพิ่ม
  และbackend evidence change ต้อง rerun affected compositionก่อนรับรอง final candidate.

## Failed/Partial ที่คงไว้

เก็บ manifest/failure/result ของ CHECK ใน `release-20261027/check-r*`;
raw logs/input/worker metrics อยู่ `/tmp/f18-check-20261027-r*` ระหว่างรัน.
CHECK เป็น harness validation เท่านั้น ไม่แทน W1/W2/W3/W4.

- M4 full regressionครั้งก่อน: Failed/Partial (historical schema producer/canary inventory,
  Redis ของ worktree อื่นถูก pause); ยังต้อง replacement full บน DB ใหม่.
- รอบ targetedแรก 2026-10-27 ล้มหลังทดลอง cutoff columnที่ยังไม่มี; ถอนการแก้นั้นแล้ว.
  แยก first-fill stale-book failureออก; affected23casesผ่านรอบหลัง.
- CHECK r1: RiskScope driver UUID type mismatch, ไม่มี positive command.
- CHECK r2/r3: first partial BUY ค้างเพราะ harnessไม่มี resting trade evidence;
  lock contention/monitor timeoutsถูกเก็บไว้ ไม่อ้างว่าผ่าน SLA.
- CHECK r4: positive10/10commands,2cycles,partial/breach/reset/correction scenarios
  ผ่านจนถึง resource sampler แต่ไม่มี /proc บนmacOS จึง Failed ไม่ใช่ acceptance.

## Remaining gates

- CHECKสุดท้าย, focused historical-migration/secret-canary regressionsและbackend fullใหม่.
- Full final UI/contracts/config/Chromium gates และ final review findings/coverage mapping.
- W1→W2→W3→W4 ชุดเต็มบนfinalschema0054/actualpolicy, DBใหม่ต่อphase;
  บันทึก actual input commit→successful evaluation commit, ทุก miss ต้องนับ.
- V22/V23 คง Pending Dependency ตาม spec (bot/Live/notification features), ไม่เพิ่ม
  featureเหล่านี้เองและไม่เปิด production admission/Live executor.

## Follow-up 2026-10-27

Current base คือ `57626d8` (main รวม F38 PR39); ไม่มี commit ของ F18 ในรอบนี้.
Host8logicalCPU/8GiB; F18 PostgreSQL16 container4CPU/3GiB, Redis1CPU/256MiB.
Scratch databasesแยกแต่ละattempt. พื้นที่ว่างก่อนworkloadประมาณ86GiB.

- Focused historical producer: first rerun1failed/2canarypassed18.15s เพราะ legacy
  5-pair monkeypatchยังค้างตอนใช้ current catalog. คืน runtime_pairsก่อน current
  producerแล้ว migration test1passed6.75s; ไม่แก้ production catalog/producer.
- UI focus finding: หลัง confirmปุ่มเปิดdialogถูกdisabledเพราะpending จึงคืนfocus
  ไปยัง labelled feedback region; Escapeยังคืนปุ่มเดิม. RiskUI6passed0.956s,
  types/lint/buildผ่าน (203modules,0.858s). ตัวเลขการเงินไม่เปลี่ยน.
- CHECK r5: commands10/10,2cycles,financial/global invariantsผ่าน;
  SLA616/616,max0.383416s,0miss; transactionP95~0.1639s/P99~0.4830s.
  **Overall Failed** เพราะconnections15→19เกินstart+2.
- เตรียม bounded risk pools4/1/2/3ด้วย role-checked SELECT1 ก่อนเริ่มloops;
  ไม่assumeowner/แก้เงิน/เปลี่ยนprotocolflagsและไม่เพิ่มpoolsize/overflow.
  Scheduler2passed2.12s; strict typing/lint/formatผ่านหลังแก้typingและexplicitimport.
- CHECK r6: commands10/10/scenarios3/financial invariantsผ่าน,resourcesผ่าน
  (connections20→21,peakRSS~60.3MB); SLA610/610,max0.822476s,0miss.
  **Overall Failed** เพราะ transactionP95~0.3261sเกิน0.250s, P99~0.7138s.
  ไม่ rerunสั้นซ้ำเพื่อเลือกเฉพาะผลผ่าน และไม่นับCHECKเป็นfull acceptance.
- Full regression replacement r1: **Failed/Partial**,35failed/186passed/2venue
  deselected,220.76sก่อนหยุด. Runnerตั้งAPI RedisDB11แต่fixtureล้างDB12;
  traceยืนยัน429 INDICATOR_RATE_LIMITED. แก้runnerทุกrole/testเป็นDB11เดียวกัน;
  ไม่แก้productionquota. รอบr2กำลังรันใหม่บนDBใหม่3574selected/2venueexcluded.

### Coverage limits found in review

V15กำหนด TP/SL-tagged fixtureแต่F15domain/schemaปัจจุบันรองรับเพียงMARKET/LIMIT
และไม่มีprotectiveidentitycontract. Ordinary-orderSQLallowlistไม่ใช่หลักฐาน
TP/SL integration. คงส่วนนี้Partial/Pending Dependencyร่วมกับF19/F20ในV22;
ไม่สร้างชนิดคำสั่ง/กฎprotectiveขึ้นเองและไม่อ้างว่าผ่าน.
Required remote CIยังไม่เกิดบนF18candidateเพราะไม่มีคำสั่งcommit/pushจากเจ้าของ;
local equivalentsไม่ถูกเรียกว่าremoteCIpassed.

## Local candidate gates closed before W1

- Full backend r2 ran all3574selected:3557passed/17failed/2venueexcluded,745.18s.
  Failure root: populated F13 downgrade test did not recognize0053guard and did not
  restore0054 after per-migration commit. Missing mutable-pair DELETE then caused
  the16risk failures (42501). Corrected exact guard inventory and finally-upgrade;
  restored the same DB to head and ran migration→risk/API/bridge/core:128passed33.78s,
  covering all17failures plus stricter revision cases. Preserve r2 as Failed; reuse
  unaffected3557passes, rather than pretend that the failed invocation passed.
- Added real PostgreSQL barriers: reset-vs-BUY/SELL/correction, decrease-vs-queuedBUY,
  wallet reset-vs-loss reset both orders, old active BUY/SELL cancel-vs-reset.
  Seven initial cases passed4.67s; after adding SELL/pending-reserve assertions the
  affected two cases passed2.89s. Eight barrier cases total; actual pg_blocking_pids,
  unchanged immutable reset cutoff, no duplicate financial facts/reserve release.
- Low input issue: expected_revision beyond PostgreSQL bigint was accepted by input
  parsing; bound it to existing DB representation in shared receipt/schema. Strict
  malformed revisions tested, generated OpenAPI/client refreshed. No new money limit.
- Stop checkpoint path now uses the same MARKET/LIMIT allowlist as enrollment.
  Protective fixture still lacks a current F15 identity/type; V15 remains Partial.
- High Compose issue closed: Paper worker SCAN credential did not match bootstrap.
  Fixed config and built/started dedicated candidate project (no external market
  producer). API/frontend healthy, ENGINE_SCAN login verified, workers0restarts;
  schema0054/protocolflagsfalse,false,false. Stopped only this test project's services.
  Initial network creation failed because Docker default pools exhausted; used a
  dedicated unused10.203.18.0/24, without pruning any existing network.
- Final backend ruff/format610files, mypy551files, imports7kept/0broken passed.
  Frontend types/lint/build passed (203modules,0.857s); existing full296passes reused
  with affected riskUI6passed after focus change.
- Chromium general18cases covered by11passes,3chartpasses and4affected chartpasses
  (26.7s). Local runner initially missed both chart flags; then macOS uvloop clock
  offset26609.344006s made absolute deadlines expire. Standard asyncio offset0;
  Linux container uvloop offset-0.000394s. Local UVICORN_LOOP=asyncio keeps all
  deadlines unchanged; chart/product code was not modified.
- F16 Chromium7cases covered by4passes and3affected financial/recovery passes24.2s.
  Reusing an activated F18 DB correctly refused legacy AllowPolicy fixture writes
  (TT028); reran affected cases on fresh preactivation DB, as in CI ordering.
- Catalog Chromium2cases: trader isolation passed; owner case passed34.0s on fresh
  DB with CI deployment generation UUID. Initial missing/invalid generation and
  already-created-owner attempts remain Failed, not bypassed.
- F18 Chromium:3initial flows passed33.3s; new outage/cache-gap/reduction/correction
  flow passed13.2s. Independent oracle uses F14 released-cost AWAY_FROM_ZERO,
  risk allowance remains TOWARD_ZERO; a one-unit oracle mistake was corrected in
  test only. Additional queued BUY is held after real engine claim/before transfer;
  monitor/stop consumer reject it without an order/financial effect, then active
  cancellation and remaining oracle pass (affected flow20.3s). No AllowPolicy.
- Workload fixture waits for committed0.5BTC depth before starting measurement;
  full duration/rates/thresholds unchanged. Adds dataset identities/digest.

Durable raw logs/environment are in
`/Users/chainarongjaykeaw/Projects/TiewTrade/validation-artifacts/f18-20261027/`.
Old review PNGs generated by generic browser tests were restored; only F18 UI
artifacts remain in this feature's evidence. No commit/push/merge or Live order.

W1 uses a fresh dedicated PostgreSQL instance (4CPU/3GiB,commit timestamps on,
max_connections200) and isolated Redis; older F18 regression instance stopped
with history preserved. Candidate source digest is in environment.json and phase
manifest. W1–W4 remain Pending Full Validation until actual final results.

### W1 r1 — failed before measured interval (2026-10-27)

Dedicated PostgreSQL `tiewtrade-f18-release-w1-postgres`, port55461,
4CPU/3GiB, max_connections200, track_commit_timestamp=on, fresh schema0054.
Stopped own regression/candidate containers before launch; other worktrees untouched.
Raw evidence: `/Users/chainarongjaykeaw/Projects/TiewTrade/validation-artifacts/f18-20261027/w1-r1/`
and adjacent `w1-r1.log`; candidate digest recorded in `environment.json`.

- **Failed/Partial**, baseline setup request exceeded60s. Measured30min interval never
  began; all recorded inputs have measured=false. No W1 acceptance claim.
- 100 settings;78 READY and22 source-unavailable/replay-pending after cleanup.
  Publication watermark1172; owner cursors915..1172;58 transferred requests,
  55 orders,60 pending dispatches,0 stops. Roughly599 monitor lock-timeout warnings.
- Paper transaction363 samples: P95~1.195095s, P99~1.741850s,
  max~1.905146s. Keep failures; do not relax wallet/order/input/SLA thresholds.
- Sequential post-failure diagnostics: API evidence EXPLAIN execution4.185ms
  with jit on /2.626ms off, estimated cost87.23, neither uses JIT. Idle replay
  under rollback: two READY owners~57.7/18.6ms; most-behind owner~71.5ms,
  bounded100-frame replay remains unavailable. This does not prove loaded latency.
- A single instrumented100-owner baseline diagnostic is in progress to identify
  loaded SQL/lock cost before production changes or another full W1 attempt.

### W1 follow-up — API hint parity and monitor fence scope

- Instrumented100-owner baseline diagnostic (25s setup timebox, **not acceptance**)
  collected per-process SQL timing; raw logs in `w1-sql-diagnostic/` and
  `sql-diagnostic-timings/` in the persistent artifact directory. No concurrent
  workload/diagnostic. Financial fence wait max~0.975s; publisher fence wait
  max~0.816s. Neither idle EXPLAIN nor this diagnostic proves the full SLA.
- Harness omission: refused opening retried without the durable evaluation hint
  that the real API commits. Match the real API catch/commit/refusal sequence;
  never admit when policy fails. Regression proves committed hint and zero
  `paper_order_requests` while source stays unavailable. SLA/harness tests4passed;
  lint/format passed, mypy source+affected tests236files passed.
- W1r2 with hint parity: **Failed before measurement**, baseline60s timeout;
 583 completed Paper transactions, P95~1.146579s/max~3.186415s. Hint parity alone
  does not solve full-scale contention. Keep raw `w1-r2/` and log.
- Standalone monitor previously took the publication SHARED fence across its
  entire replay, blocking the publisher despite changing no financial state.
  The approved plan already separates owner-locked journal replay from the
  financial final fence. Standalone scheduler now replays committed immutable
  frames through its captured watermark under the owner lock without that gate.
  Same-owner financial markers/holdings stay stable; concurrent later price
  frames remain in the journal for the next round. API evidence still verifies
  current watermark; no new opening may use a stale projection.
- Default replay behavior and every financial caller retain the publication
  fence; matching execution context explicitly fences before replay, and
  financial-boundary/reset writes keep the existing DB protocol guards.
- Affected safety/concurrency/monitor/scheduler/financial-boundary/execution/API
  regressions:30passed. New barrier test proves publisher can commit a transient
  loss then recovery while standalone monitor holds its owner lock at an older
  watermark, and the next monitor round still durably latches exactly one stop.
  Existing publisher-vs-financial commit barrier tests remain green.
  Ruff check/format passed; mypy source+affected tests238files passed.
- W1r3 started on fresh schema0054 DB `tiewtrade_f18_release_w1_r3_20261027`,
  same dedicated4CPU/3GiB PostgreSQL, unchanged100owners/20baseline/W1duration/
  input rate/transaction/resource/SLA acceptance criteria. Result pending.

### W1 runtime topology follow-up

- macOS W1r3 **Failed/Partial before measurement**: completed15/20 baseline
  batches (100owners/batch); next request exceeded60s. Full30min period never
  began. Raw `w1-r3/` and `w1-r3.log` preserved; no threshold waiver.
- Next full attempt `w1-linux-r1` runs the **same current source** read-only at
  `/workspace` in a Linux Python3.12 container based on the previously built
  candidate backend image, with its production locked dependencies. Added only
  git for real source provenance and Docker CLI for explicitly scheduled owned
  fault resources. `PYTHONPATH=/workspace/backend/src` selects current source;
  no application code copied from the older image is selected instead.
- Linux runner shares the dedicated PG container network namespace (localhost
 5432), eliminating the host↔VM DB hop. App limit4CPU/2GiB; PG limit4CPU/3GiB;
  original host8logicalCPU/8GiB and Docker VM limits remain recorded separately.
  Fresh isolated schema0054 DB `tiewtrade_f18_release_w1_linux_r1_20261027`.
- Real git HEAD/tree digest, runtime, pools and fixture metadata are in this
  attempt's own manifest.100owners/20baselineorders,10Hz market/price inputs,
 10commands/s,1800s measured period and all acceptance thresholds unchanged.
  Role isolation is unchanged; worker children retain only ENGINE/SCAN URLs.
- This is a separate result, never a replacement of Failed/Partial macOS history.
  No parallel workload/diagnostic. At this checkpoint baseline10/20 batches;
  acceptance remains pending until measured interval/oracles/SLA/resources finish.

### Full-dataset failure and checkpoint read fix (schema0055)

- `w1-linux-r1` completed all20 baseline batches (2,000activeLIMIT orders), then
  **Failed** in the first measured positive cycle:60s waiting for FILLED. Failure
  counters offered1/admitted1/completed0. PostgreSQL has one real partial fill
  of0.5, so the cycle-level fills counter0 must **not** be read as no financial fact.
- Selected order stayed PARTIALLY_FILLED0.5; its later execution evidence used
  REBASE at roughly3–4s intervals. F15 correctly skips stale source inputs older
  than1s; the single contra-trade was not a license to fabricate the remainder.
  No freshness/recovery/matching rule was changed to force a fill.
- Sequential diagnostic on a separate clone of the full dataset: actual production
  F15 round86SQLs, initially~0.651s. JIT off/on timings were confounded by cache
  warming and accumulated diagnostic samples; **JIT is not established as root
  cause**. Warm default-JIT-on round~0.206s; no JIT/server-cost configuration change
  was adopted. This diagnostic does not replace a full workload.
- PostgreSQL auto_explain showed latest-checkpoint read bitmap-scanning/sorting
 284historical large JSON checkpoints (~43ms in that cold round). Controlled
  EXPLAIN on the same owner/data saw285rows/850bufferhits/~9.366ms warm. Existing
  expression index omits the leading owner equality used by every RLS read.
- Trial expression statistics did not change the bad plan and were not adopted.
  An owner-leading partial index changes the **unchanged query** to ordered
  Index Scan with LIMIT1, ~0.301ms and32buffers in the recorded proof. RLS, immutable
  source history, decision ordering/digests, financial state and money math stay
  unchanged. Default PostgreSQL planner/JIT settings remain unchanged.
- Added additive `0055_risk_matching_owner_index.py`, reusing the existing
  `(payload->>'decision_sequence')::bigint` expression and matching predicate,
  prefixed by `(user_id,episode_id,base,quote)`. No new business/source contract.
  Migration up→down0054→up0055 passed; final schema/index confirmed in real PG.
- Affected F13 migration, F15 matching/worker, all F18 infra and risk API admission:
  **97passed**. Ruff check/format passed for the new migration. Earlier corrected
  full-regression coverage remains valid outside these affected SQL paths.
- W4 independent fixture/restore validation started sequentially on fresh schema
 0055 source DB `tiewtrade_f18_release_w4_source_20261027`; result pending. W1/W2/W3
  acceptance remains open. No other workload/diagnostic runs concurrently.

### W4 backup/restore — PASSED (2026-10-27)

Sequential native-Python build/verification on the dedicated PostgreSQL16,
final schema0055. Source fixture `w4-build-r3`, successful verify `w4-verify-r5`
in the persistent artifact directory; `result.json`, `risk-recovery.json`,
`candidate.json`, raw logs and the real custom-format pg_dump are retained.
Fixture build stops all producers/consumers before backup. No Live execution.

Failures retained and corrected within the harness:
- r1 verify refused incomplete expired-claim coverage: the real adoption worker
  had already recovered the old claim. Reuse the legacy real claim helper **after
  stopping all consumers**; preserve this required case rather than waive it.
- r2 build found missing adopted legacy owners. A migrator query was silently
  filtered by owner RLS. Use owner IDs from the original generated fixture and
  ordinary API owner sessions; do not broaden grants or bypass RLS for adoption.
- r3 supplemental verify correctly denied API reads of ENGINE-only immutable
  order events. Move internal assertions to the ENGINE owner role, no grant change.
- r4 found an invalid per-anchor-event cancellation oracle. F15 can cancel multiple
  orders in one checkpoint; immutable `terminal_orders` supplies each order's
  canonical terminal state. Verify exactly one canceled terminal state and one
  CANCELED stop effect per target, plus zero remaining reservations. Replay both
  real consumers once more before asserting no duplicate effects. No product
  consumer behavior or acceptance quantity was changed to satisfy the oracle.

Successful r5 (base restore~7.88s; supplemental recovery also completed):
- Real fixture:5capital entries,4fills,1partial order,1cancel,1correction,1reset,
 78execution evidence rows and1expired claim. Five financial episodes/four active
  wallet checkpoints, three nonempty position replays.
- Canonical table data and RLS/grants/function security match after pg_dump/restore.
- Expired claims1→0 through actual TransactionalRiskPolicy, financial facts unchanged.
- AUTHORIZATION_ONLY retains its exact receipt; repeated intake creates one request
  and the real engine applies the authorized increase while preserving the latch.
- Pending stop completes2/2 targets;2immutable terminal canceled states,
  zero duplicate cancel effects after replay, zero target quote reservations.
- Ledger/positions/execution links unchanged; reset baselines unchanged.
- `risk-recovery.json` status PASSED. Ruff check/format passed; mypy source+restore
  harness235files passed. Last edit only splits an unchanged SQL literal for lint;
  it does not invalidate the successful behavioral proof.

W4 alone does not close V21. New full W1 attempt `w1-linux-r2` started on fresh
`tiewtrade_f18_release_w1_linux_r2_20261027` schema0055 with the owner checkpoint
index and unchanged100owners×20orders/1800s/10commands/s/10Hz/thresholds. No parallel
workload or diagnostic. W2/W3 and final acceptance remain pending.

### Matching batch follow-up — correctness gates green; capacity still open

- `w1-linux-r2` on0055 completed2,000baseline orders but failed60s waiting for
  first partial BUY to become FILLED. One admitted command, zero completed cycles;
  no full30min acceptance. Owner index improves the checkpoint query but alone
  does not establish integrated throughput/SLA. Raw failure and logs retained.
- Within one actual matching transaction, reuse a complete immutable risk context
  while owner lock and BUY publication fence pin settings/holdings/prices. Core
  still checks risk/freshness before every fill. Invalidate after **any** BUY/SELL
  fill; incomplete replay keeps catching up. Never reuse across transactions/owners.
- Global publication/admission controls are not pinned by owner lock: retain a cheap
  fresh control read before each input using a cached READY context. Real-DB test
  disables admission between two inputs and proves zero fill/zero position event.
- Matching scope now uses an owner-scoped active wallet/episode/closure lookup.
  It does not recompute cash/reset presentation on every input. Position proof/
  book agreement remain checked, and the actual F15 cash writer still reads and
  validates the full ledger before **every** fill. API intake/admission remain on
  the full wallet snapshot. A guard-failure test proves rollback of fill event,
  position event, execution link and money even after a hypothetical fill was computed.
- Existing first-fill-breach test now consumes two inputs in one transaction and
  proves the first fee breach prevents both later depth and the following input.
- Initial affected batch suite96passed. Later scope/control suite96passed/1failed
  (reservation test seed was still ACCEPTED). Fixed its setup to wait for both
  actual dispatch deadline and core OrderState.eligible_at, then assert real FILLED
  before SELL reservation race; affected BUY/SELL cases2passed. The interim attempt
  waiting only for dispatch was insufficient and is not accepted evidence.
  Current execution safety7passed; full mypy551files and source/test/migration
  ruff check/format608files passed before the final harness-only PID extraction.
  Import contracts7kept/0broken,280files/1963dependencies.
- Partial fixture now publishes distinct fresh contra trades until actual FILLED
  is observed. F15 may correctly discard an older input during recovery; a single
  pulse is not a reliable fixture. Keep strict gross quantity1, exactly2fills for
  the selected partial case, and all original price/book/command rates/durations/
  financial/resource/SLA thresholds. No financial or freshness rule was relaxed.
- Targeted cloned full-dataset diagnostics are **not acceptance**. The first two
  timeout-only runs lacked producer supervision and cannot establish capacity.
  The next supervised run caught a PID publication race before the trade stage:
  launcher could see an empty PID file. Reuse the existing F15 atomic write/rename
  helper for both F15/F18 workers. Interrupted-publication tests preserve absence
  or prior valid PID; supervision7passed, affected harness mypy237files passed.
- Current supervised diagnostic runs on a separate0055 clone of the previously
  failed100-owner/2,000-order dataset. It uses the real producer and all10Paper
  workers; only an actual final fill with exact cash/held/fill-count oracle can
  pass this diagnostic. It cannot replace W1/W2/W3.
- Earlier W4 canonical restore/RLS/data proof remains valid. Because the shared
  matching path changed, final claim/cancel recovery will be rechecked against a
  fresh restored target before accepting W4 for the final candidate; reuse the
  already valid source fixture, without rebuilding unchanged financial history.

## Approved runtime amendment and final W4 recheck — 2026-10-27

- Owner approved W1/W2/W3 measured durations10/5/30minutes. Updated plan/validation
  and harness profile `F18_F15_F16_INTEGRATED_V2`; F15 four-hour default unchanged.
  New F18 schedule retains all7faults and their30/60s severity; offsets compressed
  to fit1800s,30positivecycles per owner. RSS windows scale to112.5s warmup and
  450s averages, growth<=20% unchanged. All dataset/rate/financial/SLA/resource
  thresholds retained. Short run does not prove four-hour leak resistance.
- Duration/growth/fault-budget tests plus producer/PID supervision:14passed.
  Affected harness and src mypy237files passed; ruff check passed. Initial mypy
  invocation omitted src and failed import discovery; corrected invocation includes
  src, with no ignored errors. New test formatting corrected before passing tests.
- `w4-verify-r6/result.json`: canonical data/RLS/grants match;5episodes,78evidence,
  4checkpoints,3positions replayed; expired claim1→0; economic effects unchanged.
  `risk-recovery.json`: PASSED, exact authorization retry,2terminal cancellations,
  zero duplicate cancel effects; financial facts/reset baselines unchanged.
  Artifacts: `/Users/chainarongjaykeaw/Projects/TiewTrade/validation-artifacts/`
  `f18-20261027/w4-verify-r6/`. This closes the earlier final affected W4 recheck.
- Supervised2 partial diagnostic FAILED/TimeoutError: selected PARTIAL0.5 did not
  become FILLED;586transactions p50 .272485s/p95 1.031072s/max2.085003s.
  It is not acceptance and does not establish a single causal bottleneck.
  No new full workload is launched while this known prerequisite remains broken.
- New profileV2 W1/W2/W3 remain pending; old profileV1 failures remain failures.
  Proposed change to fence timing is separately reviewable in
  [F18-R5](../publication-fence-amendment.md), **Needs Owner Approval** per plan's
  explicit publication-contention amendment rule. No R5 implementation applied.
  V22/V23 dependency gates remain pending; F18 is not Completed or activated.

## R5 approved implementation and affected verification — 2026-10-27

Owner instructed to proceed after the R5 proposal. Incorporated the complete
amendment in plan and closed NC-F18-09 before continuing implementation.
Pure matching preview cannot authorize BUY: every possible BUY order-state
change/fill is recomputed with fresh time/context under publication fence.
Unclassifiable preview falls back to that path. Proven unchanged BUY inputs
avoid publication fence and evidence replay. Context is reused only after the
actual fence, invalidated after every fill; global controls checked per input.

- Barrier tests cover committed transient breach/recovery, disconnection,
  disabling admission, and expiry between preview and final fence; zero extra
  fills/cash effects. No-op resting BUY completes while publisher holds its fence.
- A SELL command can drive existing BUYs in the same pair checkpoint; resolve
  using an actual active BUY intent, preserving its valid side/size convention.
  New positive/latched mixed-order tests verify exact cash/held/fill counts.
  Initial side-only replacement violated MARKET size rules; both new cases
  failed and were corrected, then affected fence/stop/execution19tests passed.
- Broad affected run:188passed/1failed in125.27s. Stop fixture used a global
  bounded20-owner round and did not establish its own accepted order before
  breach (stored result REJECTED, no paper_orders row). Claim/process that owner
  explicitly and assert ACCEPTED first. Stop/recovery oracle unchanged; the
  failed broad invocation remains Failed, not retagged as all-passed.
- `r5-partial-diagnostic` remains FAILED/TimeoutError (100owners/2,000orders,
 10Paper workers, same4CPU/2GiB app and4CPU/3GiB PG).1340transactions
  p50 .111170s/p95 .305105s/max1.052468s; selected order stillPARTIAL0.5,
  queue0, latest checkpoint only a BookState, risk cursor8230/watermark8599.
  Improved timings alone are not acceptance or proof of SLA compliance.
- Postmortem identified repeated rebase returning only latest book and omitting
  already committed fresh trades after it. Reuse read_inputs after that snapshot
  within the same20-input budget. Do not execute inputs from the missing interval
  or relax one-second execution freshness. New actual stale-consumer partial
  test passes exactly2fills/gross1BTC/net.999BTC/cash9900USDT.
- Recovery/fence/execution15tests passed19.88s; fresh-DB F15worker/storage/risk
  financial-boundary40tests passed48.13s. Full src/affected mypy237files passed.
  Final static pass: ruff checks passed;611files already formatted.
- Full backend regression on fresh isolated schema0055 DB
  `tiewtrade_f18_release_r5_full_20261027` is running sequentially before new W1.
  Log `f18-20261027/r5-full-regression.log`; no concurrent workload/diagnostic.
  ProfileV2 W1/W2/W3 and affected W4 recheck after R5 remain pending.

### Final R5 full regression result

`r5-full-regression.log`: **3607passed,2venue-contractdeselected**,5warnings,
759.75s (12m39s), fresh isolated0055 DB. No failures. Full mypy554files passed;
ruff checks and formatting611files passed; architecture contracts7kept/0broken.
This is a new complete successful invocation; previous failed attempts remain
recorded above. Frontend/UI and API contracts were unchanged by R5, so reuse their
existing passing regression/browser evidence instead of repeating it without a
new impact. W4 claim/cancel recovery is affected and will be rechecked.

W1 `w1-v2-r5` now runs alone on fresh0055 database
`tiewtrade_f18_release_w1_v2_r5_20261027`, same Linux runtime/current mounted
source,4CPU/2GiB app and4CPU/3GiB PG. ProfileV2 is100owners×20baselineLIMIT,
book/price10Hz,10commands/s,600s measured duration, all financial/SLA/resource
thresholds unchanged. Result pending; do not count setup or full regression as
proof of W1. No concurrent diagnostic/workload.

### W1 baseline failures and monitor follow-up

- `w1-v2-r5` FAILED/Partial before measurement: baseline request timeout60s.
  Postmortem found96owners with1accepted order each and4withnone; all100 latest
  evaluations SOURCE_UNAVAILABLE/replay_pending, max cursor lag321frames.
  No measured600s interval, so this does not pass any W1 acceptance gate.
- Keep the same owner key/four monitor slots, but use nonblocking try-lock for
  standalone scans and fair retry instead of waiting100ms on a busy owner.
  Blocking financial-writer locks unchanged. Capture owner state/watermark in
  one SQL snapshot and reuse the final verified frame in the transaction.
  Affected risk/API89tests passed46.96s; type checks passed. Updated concurrency
  barrier to pause after the combined snapshot rather than a removed SQL call.
- Resumed after interruption with no leftover test/workload process. Docker
  daemon was stopped; started it and only the two owned F18 PG/Redis containers.
  Waited for PG recovery. Data and existing runtime image persisted. VM reports
 8CPUs/4106604544bytes; app/PG limits unchanged. Temporary helper files had gone,
  so runner scripts are now retained alongside artifacts under `runner/`.
- `w1-v2-r6` also FAILED/Partial in baseline request timeout60s, before measurement.
  Try-lock/query reductions alone are insufficient; no immediate blind rerun.
- Separate non-acceptance CPU diagnostic on the frozen failed r6 dataset ran
 100owner monitor transactions with4slots, each rolled back.1.192s wall;
 4276frame decodes cost.558s of1.118s profiled time,4376risk evaluations.
  Kept raw `w1-v2-r6/monitor-cpu.log`/`.prof`. This isolates repeated decoding;
  it does not establish loaded capacity or satisfy SLA.
- Added bounded256-entry cache of immutable public frame decoding. Every call
  still queries DB and validates contiguous count/id/checksum before using it;
  id/time/proof/full payload text form the key. No owner data, READY, policy or
  financial result cached; every frame remains individually evaluated.
  Two new tests warm a frame then inject missing-row/bad-checksum reads: both
  fail closed despite cache. Affected risk/API91tests passed45.96s.
  Static checks passed, mypy236files; test variable-name type issue corrected.
- Same frozen-data diagnostic after decoding reuse:0.524s wall/.500s profiled;
 523decodes,.062s,3753cachehits, bounded256entries; **4376risk evaluations remain**.
  Separate `monitor-cpu-decoded.log`/`.prof`, no overwrite of earlier evidence.
  This supports the optimization; actual W1 still required.
- `w1-v2-r7` now runs alone on fresh0055 DB
  `tiewtrade_f18_release_w1_v2_r7_20261027`, original100×20/load/SLA/resource gates
  with approved600s runtime. Full3607-test invocation predates this monitor-only
  tuning: reuse its unaffected results plus the91affected passing tests; do not
  describe the old invocation as rerun on this new source. W2/W3 and final
  post-R5 W4 recovery recheck remain pending. Admission remains closed.

### Startup follow-up after decoding optimization

`w1-v2-r7` FAILED before baseline: parent observed `.pid` metadata, then reading
the file returned FileNotFoundError during Paper worker8 startup. PID was visible
after cleanup; there was no measured load result. F18 Paper workers also invoked
PID publication twice (wrapper and reused F15 runner). Publish once per worker,
and reuse a bounded read/retry helper instead of separate exists/read operations.
Reject nonpositive PID/dead worker; do not accept an old readiness file for an
already exited process. Financial logic, worker counts and runtime gates unchanged.

Supervision/runtime-profile19tests passed0.23s; mypy237files/ruff checks passed.
New cases cover transient missing/empty reads, invalid PIDs and dead-worker stale
PID reuse. No full regression repeat for this harness-only change. `w1-v2-r8`
now runs alone on fresh0055 DB `tiewtrade_f18_release_w1_v2_r8_20261027`; result
pending. Old r5/r6/r7 failures remain recorded and do not satisfy V21.

### Loaded contention evidence and existing-service isolation

- `w1-v2-r8` also FAILED/Partial at baseline60s, no measured interval. Keep this
  failure. Do not claim unloaded decode profiler results proved loaded capacity.
- A single short contention diagnostic at a time cloned r8's frozen data and ran
  the actual producer/risk/10Paper workers plus20API requests. Three SQL wait
  snapshots showed no long blocked query/lock chain. Many backends were waiting
  for clients while the aggregate app consumed nearly4CPU. In the CPU diagnostic
  the risk process got.337core, API parent.442, Paper workers.274..344each.
 20requests yielded13completed after9s; this is **not acceptance**.
- Baseline refusal retries were an uncounted20ms loop. Reuse F15 RESULT_POLL_SECONDS
  (.25s) only while `started=false`; retain20ms during measurement. Expose both
  in manifest; no change to offered command/input rates, dataset, duration, SLA
  or financial/resource oracles. The short comparison alone was insufficient
  (10/20completed), so retry pacing was not declared the sole fix.
- Mirror the existing separate risk service: API/Paper3CPU/1536MiB plus risk
 1CPU/512MiB. **Total remains4CPU/2GiB**, PG remains4CPU/3GiB. Same workers/pools,
  source/runtime/roles. Shared PID namespace lets the existing sampler include
  all processes despite separate CPU groups. First diagnostic used inherited
  HOSTNAME for PID namespace and failed resource lookup; preserved that failure,
  then used explicit known parent container identity. No production-rule change.
- Corrected isolated-risk diagnostic `r5-contention-isolated-risk-r2`:20/20actual
  API requests completed by the9s snapshot, same data/aggregate resource budget.
  Source/profiler/role metadata and wait/CPU snapshots remain in artifacts. This
  supports the topology, but does not pass W1 or prove the1s SLA at full scale.
- `runner/isolated_workload.py` drives unchanged profile/domain/oracles, records
  topology and runner hashes, gives risk only ENGINE/SCAN URLs, and supervises
  its actual runtime PID through the shared namespace. `w1-v2-r9` now runs alone
  on fresh0055 `tiewtrade_f18_release_w1_v2_r9_20261027` with this topology.
  Full600s/100×20/SLA/financial/resource result remains pending. W2/W3 and final
  post-R5 W4 recovery remain pending; no activation/Completed/Git mutation.


### R5 final drain and R6 approved follow-up — 2026-10-27

- W1 `w1-v2-r9` is **Failed/Partial**, after all 2,000 baseline orders and
  the partial-fill oracle passed. Measured counters: offered304/admitted215/
  completed210/fills92/cancels36/replays40/cycles15. The 60s positive-cycle bound
  expired while reseeding 20 baseline orders after breach/reset. This was not a
  baseline setup failure. Original results remain preserved; W2/W3 have not run.
- Matching checkpoint persistence now updates current-pair and other-pair rows in
  disjoint writable CTEs. Owner locking retains the bounded blocking protocol;
  the try-lock experiment was reverted. Affected projection/caller regression:
  `r5-projection-regression.log`, 244 passed/130.48s.
- Monitor replay proves historical frames outside publication lock, then drains
  the final tail under the shared fence through commit, within the same total
  100-frame budget. Financial callers retain fully fenced defaults; reductions
  do not gain a publication wait. `r5-final-drain-safety.log`:36 passed;
  `r5-final-risk-regression.log`:95 passed/51.13s. Static checks: ruff611files,
  mypy554files, import contracts7 kept. These extend the existing full3607-test
  evidence; that older full invocation is not claimed to run on the new source.
- Five-command/reset diagnostic passed21.5226s, exact cash delta -1.197901,
  held0/two fills/five completed commands. Both 20-order reseed diagnostics
  (before/after final drain) still failed60s. Diagnostics do not pass V21.
- W4 `w4-verify-r7` **Passed** on schema0055/final R5: restored canonical data,
  RLS/grants, five episodes/78 evidence rows/four checkpoints/three positions;
  expired claim1→0. Recovery passed two terminal cancellations, zero duplicate
  effects, unchanged financial facts/baselines and authorization-only retry.
- Owner approved **R6** explicitly on2026-10-27. Requirements/plan incorporated
  the amendment before implementation. API NEW under owner lock and GET Paper
  under repeatable snapshot may read <=100 verified public price frames only
  after all financial boundaries/source/revision/pending checks pass. A cursor
  before the latest financial boundary's price watermark also fails closed.
  Any transient breach refuses even after recovery; API writes no latch/stop/
  financial facts. ENGINE retains fully fenced replay before money mutation.
- Initial R6 test invocation:10 passed/2 failed, both test assertions (different
  evaluation timestamps; API intentionally lacks position-event SELECT grant).
  No grant expanded. Corrected assertions; `r6-price-tail-safety-r2.log`:
  **13 passed/12.88s**, including the financial-boundary watermark guard.
  Affected regression and short reseed reproduction are in progress; do not
  interpret this safety test result as workload acceptance.


R6 affected verification: `r6-affected-regression.log` **123 passed/69.80s**
(all risk infra, risk admission/routes and manual order routes). Ruff passed;
mypy236 source/test files passed. The scheduling-hint negative fixture now uses
financial replay-pending, because an otherwise valid benign price tail is
explicitly supported by R6; a false READY hint still cannot bypass the policy.
Read-only review confirmed API permission grants/financial writes unchanged,
NEW owner-lock/GET repeatable-snapshot callers, same core Money/Quantity
calculations, contiguous verified frame budget, durable transient-breach refusal,
and ENGINE resolve/execution-context defaults remain fully fenced. W4 recovery
is unaffected by R6's API-only read protocol; retain r7 rather than rerun it.


### R6 loaded progress and bounded evidence-copy tuning

- `r6-reseed` **Failed** the unchanged60s bound:19 new requests admitted over
 57.72s, with18 completed ACCEPTED and the last transferred command still
  pending at shutdown. API catch-up progressed; ENGINE queue/processing remains
  insufficient. Keep `failure.json`/worker metrics/logs and source hash.
  Its2,749 processing transactions had p50.14684s/p95.37398s/p99.56271s;
  this diagnostic is not acceptance and does not relax the workload/SLA gates.
- A single pending command was profiled after stopping every workload worker.
  `r6-matching-profile`: .53971s wall/.30442s SQL,135 queries. Six copied inputs
  repeated owner/active-episode locks and immutable execution-profile reads.
  Reuse those checks once in the same owner-locked transaction via bounded
  `append_execution_inputs` (1..20), keeping all source identity/content/digest,
  permanent registry conflict checks, individual immutable evidence and per-input
  fresh-time matching/risk decisions. No publication-gate protocol, scheduling,
  count/rate/resource/financial rule or authority changes. Existing single-input
  API delegates to the same validated path; no process/global authorization cache.
- Added concurrent20-input batch replay/identity and invalid-tail whole-transaction
  rollback coverage. Broad execution/manual/risk/API regression first used an
  already populated safety DB:6 failed/133 passed before interrupt, stale global
  fair scans selected other invocations' pending commands. Preserve that failed
  invocation. Recheck on a new empty schema0055 DB `...r6_safety_20261027` now
  in progress, stopping at the first failure rather than rerunning blindly.


Fresh-schema follow-up `r6-batch-affected-regression-r2.log`: **262 passed/142.08s**,
covering all execution-market, manual inbox, risk infra, risk/API and manual API
routes after evidence-batch tuning. Mypy237 source/test files passed. This includes
all six earlier failures and the new concurrent batch/replay/rollback test. No
financial/role/schema/frontend contract changed. `r6-reseed-r2` now runs alone on
an independent clone of the same r9 donor data with the unchanged60s bound;
result pending. No acceptance claim from this diagnostic.


`r6-reseed-r2` still **Failed60s**:20 admitted/19 completed. Processing3031
transactions: p50.12045s/p95.31973s/p99.57337s. This is progress, not acceptance.
The evidence writer now sends the unchanged per-input facts in bounded bulk SQL:
all identities/digests checked, existing keys read once, new evidence rows inserted
once, permanent registry rows inserted once. Same owner lock, pinned profile,
row contents, provenance, per-input decisions and outer financial transaction;
no change to publication-gate protocol or scheduling. Conflicting/missing/corrupt
proofs still fail; no ON CONFLICT bypass or frame coalescing. Original single-input
call uses the same path. `r6-bulk-evidence.log`:9 passed.

`r6-bulk-affected-regression.log`:67 passed/1 failed (stopped at first failure).
The existing second-input failure injection counted two INSERT *statements*;
bulk writes now issue one statement for multiple rows. Adapt the injection to
count input rows, retaining the exact rollback/cash/order/evidence oracles.
`r6-bulk-rollback-recheck.log`:**32 passed/30.07s** for the entire worker suite
and batch test, including failure after evidence insertion/before registry write.
Ruff/type issues were formatting/import ordering only and corrected. Remaining
manual/risk/API/supervision cases are running on a fresh schema; reuse the first
67 results for production source unchanged since that invocation.


### R6 safety closed; W1 final candidate running

The rollout-disable race test also counted per-input INSERT statements. Its
injection now disables the global admission control between the first and second
fresh-time matching decisions, after the bulk copy; the zero-fill/unchanged-cash
oracle is unchanged. `r6-bulk-followup.log`:77 passed/1 failed (this fixture),
then `r6-bulk-risk-execution-recheck.log`:**8 passed/8.00s**. The remaining
matching/recovery/monitor/prices/requests/scheduler/stops/worker/workload and API
cases passed: `r6-bulk-remaining-regression.log`, **91 passed/39.92s**.
Use these results with the earlier67 passed,32 worker/batch passed and77 passed
for unchanged production source, covering the same affected suites; no claim
that the intermediate failed invocations were green. Ruff passed; mypy238files
passed after both fault-injection updates.

`r6-reseed-r3` **Passed58.17654s**,20 completed ACCEPTED, exact unchanged cash/held
and +20 USDT reservation. It remains `acceptance_result=false`, not V21 acceptance.
All workloads/workers stopped before the next set. W1 `w1-v2-r10` now runs alone
on fresh0055 DB `tiewtrade_f18_release_w1_v2_r10_20261027`, final R6 read protocol
and bulk evidence writer, same 100×20 dataset/rates/600s/60s cycle/SLA/safety/resource
oracles and same aggregate4CPU/2GiB topology. W2/W3 still pending. W4 r7 recovery
remains valid: API read path and copying identical execution evidence do not
change schema/roles/serialized replay facts/ENGINE recovery authority. No new
restore invocation without an identified recovery impact. Production admission
remains closed; dependencies/remote CI/Git actions are not marked completed.


W1 r10 was intentionally stopped during setup after final review identified
full payloads redundantly serialized into key-only lookup/registry queries.
The original `failure.json` retains CancelledError/counters0; classify as
**Partial/aborted before measurement**, not a capacity pass. All owned workers
exited. Those two queries now send only the columns they consume; immutable
payload/digest is still inserted in full once and decode/checks are unchanged.

`r6-evidence-columns-recheck.log`:16 evidence/batch/risk-execution passed, then
worker fixture failed because global fair scan on reused DB did not service its
own new command. Fresh worker invocation `r6-columns-worker-recheck.log`:15 passed,
one acceptance fixture deferred SourceUnavailable before any projection/result;
source age at submission40ms, so do not assert that a >1s stale source was proved.
No production bypass or timing threshold changed. Recheck `...worker-recheck-r2`:
**31 passed/31.66s** on the same source. Preserve the intermittent failed result;
loaded final acceptance remains required.

A stronger single selected-owner diagnostic exercises the actual partial fill,
price breach/stop/reset,20-order reseed, five-command cycle, correction/replay and
final reset against the full frozen dataset with the original60s progress bound.
First `r6-full-cycle` failed in setup: lowering the limit after starting all Paper
workers was refused SOURCE_UNAVAILABLE, before the measured cycle. Move setup
mutations before Paper startup to match the approved full profile's ordering;
no refusal retry/bypass and no measured timeout increase. `r6-full-cycle-r2`
now runs alone on another clone; result pending. It is diagnostic, not V21.


### Review finding — healthy claims inflate failure backoff (High)

`r6-full-cycle-r2` failed60s after the first partial fill, before breach/reset.
The order remained PARTIALLY_FILLED (.5gross/50spent), risk READY/loss.05, current
publication/source metadata intact. Successful checkpoint15:49:57, but seven
covered dispatch commands carried attempts4/8/15/17/89/102/222 and were deferred
until15:55:14..22. `paper_orders/dispatch.py::claim_order` increments attempts for
all claims, while `finish_claim`/`reschedule_processed_orders` never reset it;
`defer_claim` uses that lifetime count for 1s/5s/30s/5m backoff. Thus a long-lived
healthy command can wait5min after its first transient error, violating loaded
progress/recovery expectations. This is a retry bookkeeping defect, not proof
of incorrect Money/Quantity results or a reason to loosen the financial fence.

Fix: reset only the failure-backoff counter after a committed successful/idle
round and for admitted sibling commands covered by the same persisted checkpoint.
Keep claim_revision monotonic, owner locks/CAS/leases, dispatch fairness, economic
IDs, source/risk checks and the existing 1s/5s/30s/5m failure sequence. No shorter
failure-delay values or synthetic success. Tests exercise healthy polls followed
by four real deferrals, stale successful claim rejection, and pair-covered
counter resets without changing pending/cancel/other-pair/claimed schedules.
Initial dispatch9 tests passed2.32s; expanded checks in progress. First expanded
invocation collected no tests due to a nonexistent explicit manual-worker test
path; corrected to the existing manual-order directory without changing code.

This follow-up touches retry recovery, so W4 r7 is no longer sufficient by impact
analysis alone: recheck the affected restore/recovery path on final source after
these checks. The earlier R6 read/bulk-only reuse decision remains historical.


Backoff fix affected check `r6-backoff-affected-r2.log`:**100 passed/66.83s**
(dispatch, cross-pair/checkpoint/rollback, full matching worker, failure streak/
stale claim, real risk execution/fence/recovery/stops, all manual inbox tests).
Ruff passed; mypy236 files passed. Retry delay values/claim_revision are unchanged;
reset is limited to successfully committed work, including covered pair siblings.

W4 `w4-verify-r8` **Passed** on final0055/current retry code, same approved frozen
source fixture restored to `tiewtrade_f18_release_w4_restored_r8_20261027`.
`risk-recovery.json` confirms real risk policy, authorization-only exact retry,
pending stop completed, two terminal cancellations, zero duplicate effects and
unchanged financial facts/reset baselines. No Live action. After W4 stopped,
`r6-full-cycle-r3` now runs alone, same full frozen100×20 data and original60s
cycle bound, with healthy-round retry-counter fix. Result pending.


### R7 approved and implementation checkpoint — 2026-10-27

Important diagnostic correction: cloned full-cycle r2/r3 restarted fixture trade
IDs at1 although immutable checkpoints had seen3456. Core correctly rejects
backward trades; those two failed diagnostics **do not prove a capacity or
financial-authority defect**. The retry counter defect above is independently
proved by source/dispatch state and safety tests, but must not be called the
sole cause of their partial-fill stall. Corrected external publisher continues
IDs from frozen public source; `publisher-continuity.json` records the offset.
First r4 startup had an external helper import-path error before any DB work;
its log is preserved separately. Corrected `r6-full-cycle-r4-run.log` genuinely
failed60s after partial/breach/stop/reset:20 NEW requests including initial buy,
19 completed and the last reseed still pending. No V21 pass.

Owner explicitly approved [R7](../worker-round-amendment.md). F18/F15 plans and
missionNC-F18-11 updated before implementation. Runtime alternates manual1 then
matching1 and retains20ms sleep. F18 worker reuses that same constant through an
optional bounded harness argument, records both limits; F15 standalone/default
remains20. No new concurrency/worker/pool/schema/financial/price authority.
Ready for Code Review announced with scope/tests/pending acceptance/risk notes.

`r7-worker-composition.log`:22 passed/one setup error because the DB-backed
scheduling-hint test lacked role URLs; use the existing role wrapper, not a skip.
`r7-worker-composition-r2.log`:**24 passed/1.16s**. Includes production phase
limits, cancellation disposal, explicit F18 limit handoff, standalone20 default,
worker supervision and false READY hint full-policy refusal. Mypy import-export
assertions were corrected in tests; `r7-mypy-r2.log`:**558files passed**.
R6 coverage gap closed while waiting for approval: price outage→recovery is
read-only, and a real risk reset invalidates an old setting snapshot. First
invocation14 passed/one test-constructor key typo; corrected (`key`, not
`idempotency_key`); reset recheck passed1/1.59s. Current full mypy includes both.

Review of the R7 diff/callers found no new authority/counter/lease/FIFO/financial
change. Runtime configuration, harness default/explicit settings and manifest
agree. Core safety100 and W4r8 results remain valid because their contracts are
unchanged; actual scheduling progress/starvation/resource/SLA remain unproved.
`r7-full-cycle` now runs alone with source-continuous IDs, same frozen100×20,
same60s timeout and exact financial/scenario oracles. If it fails to improve,
revert only R7 scheduling per its approved scope and preserve the result.


R7 selected-owner full cycle returned from the unchanged `wait_for(...,60)`
before deadline, then failed a helper postcondition that incorrectly expected
three total execution links: the scenario also commits one idempotent REPLACE
correction. Preserve original AssertionError/failure.json. Read-only recheck
`r7-cycle-postcondition-r2.log`/`postcondition-recheck.json` on its frozen result
passed: RECORD3/REPLACE1; cash9998.802099USDT, held0/cost0, reservation20USDT,
20stop cancellations, manual requests44 (20original+24new),64successful commands
including20stop cancels, final reset revision7/unlatched. Initial read-only
recheck also omitted the20stop commands in its expected command total; corrected
only that diagnostic expectation, preserving its failed log. No financial facts
changed and the whole workload was not rerun for an assertion-only mistake.
This is diagnostic progress proof, **not** V21 or a measured W1 capacity pass.

R7 final static: ruff passed,559files formatted, mypy558files passed,
7import contracts kept/0broken. W1 `w1-v2-r11` now runs alone on fresh0055
`tiewtrade_f18_release_w1_v2_r11_20261027`, final R7 source/manifest phase limits1,
same100×20/600s/rates/60s/SLA/resource/financial oracles. W4r8 remains current for
retry/recovery; frontend296tests/types/lint/build/browser evidence reused because
no frontend/API shape change. Old fullbackend3607 invocation is reused only for
unaffected coverage plus affected final checks, not relabeled as a new invocation.
W2/W3 and final acceptance remain pending. No Git or Live action.


### W1r11 baseline rejection; same-protocol monitor SQL tuning

W1 `w1-v2-r11` **Failed/Partial** during baseline10/20, before measurement:
`F18_POSITIVE_REQUEST_REJECTED:ORDER_SAFETY_UNAVAILABLE:None`.
Two requests were rejected16:23:50.87/51.10UTC. Their final evidence was
SOURCE_UNAVAILABLE/pending with cursor4917/4920 vs latest4922. API preflight
success is not final financial authority; ENGINE's refusal remains correct and
must not be bypassed or turned into a fake positive result. No W2/W3 started.

Reduce redundant SQL under the unchanged owner/financial/publication protocol:
`storage.read_monitor_owner` joins wallet, setting and initialization in one owner
statement, replacing three reads; shared pure setting decoder retains both missing
and configured behavior. `_save_cursor` compares the prior book/source/episode and
upserts the cursor in one SQL statement/CTE, replacing a client-side reread/JSON
decode. Same before/after comparison, derived pair writes, roles, owner lock,
100-frame/20-boundary budgets, four monitor slots, CPU/RAM/pools and gates; no
owner-book/result cache, skipped frame or financial-rule change.

`r7-monitor-sql-safety.log`:**116 passed/66.60s** (all risk infra plus risk/API
admission/routes). `r7-monitor-projection-recheck.log`:**1 passed/1.72s**,
price-only ticks preserve pair xmin/source, a second actual fill advances them
and exact cash becomes9800USDT. Whole mypy559files and ruff passed.
W4 `w4-verify-r9` **Passed** after changed cursor persistence/recovery path,
canonical restored data/RLS/grants and risk recovery/cancel/no-duplicate/financial
facts/baselines checks retained. After W4 stopped, `r7-baseline-recheck` runs
alone on a clone of r11 at its failure scale: next100-owner baseline batch using
the same request policy/functions and bounded20 concurrency,60s diagnostic bound,
all owners' unchanged cash/no position events/+1USDT reservation assertions.
This is not full W1 acceptance. Full fresh W1 only after the failure reproduction
passes; all old failures remain preserved.


100-owner baseline reproduction returned within the existing60s diagnostic
bound, then its aggregate reservation assertion failed: donor r11 also contained
preexisting pending commands that workers completed during startup, so the total
reservation difference was not solely the100 new orders. Preserve failure.json.
Read-only donor/clone request-ID set comparison and per-new-order recheck passed
(`r7-baseline-postcondition-r2.log`/`postcondition-recheck.json`): exactly one new
request per owner/100total, TRANSFERRED/SUCCEEDED, ACCEPTED/unfilled, zero spent,
exact1USDT reservation each, unchanged owner cash and zero position events.
The first read-only helper used `RequestView.order_id` instead of its existing
`request.order_id`; corrected helper only, preserving its log. No workload rerun
for these postcondition-only corrections and no financial state changed.

W1 `w1-v2-r12` now runs alone on fresh0055
`tiewtrade_f18_release_w1_v2_r12_20261027`, final R7 plus same-protocol monitor SQL
changes, same100×20/600s/rates/60s/financial/SLA/resource gates. Previous W1r11
and every diagnostic Failed/Partial remain recorded; the diagnostic postcondition
recheck is not a substitute for measured W1. W4r9 is current; W2/W3/final acceptance
remain pending. No additional diagnostics, tests or Git/Live action during W1.


### W1r12 measured progress failure — 2026-10-27

W1r12 baseline **2,000/2,000 passed**, including the previous r11 failure point.
Partial-fill risk oracle passed (.05loss). Then **Failed/Partial** in measurement:
selected owner's initial breach/reset/reseed cycle exceeded the unchanged60s
bound while waiting for a transferred reseed command. Counters: offered494,
admitted463,completed445,fills171,cancels84,replays95,cycles70,rejected0. This
improves prior progress but does not pass W1 or justify W2/W3.

Postmortem only (after workload stopped):15,250 processing samples pooled across
setup and partial measurement p50.07767s/p95.21737s/p99.35295s/max.94690s. These
are **not a final measured-only percentile pass**, and cannot pass V21. Recent
selected-owner requests transferred in.13–.23s, but command processing completed
roughly3–4s later. Keep the60s bound and every failed sample/scenario; no counter,
fixture load or acceptance threshold relaxed.

A single10s round-counter probe now runs on a frozen r12 clone under the same
4CPU/2GiB aggregate app budget, risk service and10Paper workers. Count unchanged
manual/Paper round results (processed/deferred/skipped) only inside a marked10s
window while the existing100-owner baseline producer offers real requests. This
adds observability in an external wrapper, not a runtime scheduling change.
Hypothesis to test: limit1 repeatedly offers a busy/stale head candidate rather
than allowing another owner to use an otherwise idle worker. Do not call this
proven before the probe result. No other diagnostic/tests/workloads overlap.


10s `r7-round-probe` result (window.json and per-worker .rounds.json retained):
Paper956rounds/375processed/3deferred/578skipped (~60.46%); manual953rounds/
65processed/0deferred/70skipped, remainder empty. `skipped` includes claimNone
and claim-lost, not an exact busy-vs-stale breakdown and not proof every worker
selected the same owner. The existing limit1 stops after an unclaimable hint;
code inspection plus the high skip fraction supports testing bounded fallback
selection. Do not label this a throughput/financial/latency acceptance pass.

Prepared [R8](../claim-budget-amendment.md), **Needs Owner Approval**: separate
20candidate hints from1successful claim per phase, same due/claim/CAS/owner FIFO,
consume budget even when a claimed item defers/fails/loses lease, and keep every
worker/pool/CPU/RAM/rate/frame/timeout/SLA/financial gate. Defaults/standaloneF15
unchanged. No R8 runtime/harness code written before approval. Owner question is
pending; R6/R7 remain Approved and their scope is not being re-requested.
Code changes currently stop at tested R7+monitor SQL; production activation
remains closed, W1Failed/Partial, W2/W3notrun, W4r9Passed and V22/23dependencies
pending. No background diagnostic/workload remains running.


### R8 approved implementation — 2026-10-27

Owner explicitly approved R8; F18/F15 plans and missionNC-F18-12 updated before
implementation. Manual/Paper round functions accept an optional successful-claim
budget; defaults remain20hints/unlimited within that batch. Integrated runtime
and F18 worker use20hints/1claim, same20ms tick. ClaimNone continues to another
ordered hint; a non-None claim consumes the budget before committing its claim
transaction, so lost commit acknowledgement cannot allow a second claim in the
phase. Deferral/failure/claim-lost also consume it. No financial/claim SQL,
FIFO/owner/CAS/lease/backoff/resource/rate/threshold changed.

`r8-selector-unit.log`:24passed before the unknown-commit edge case was added.
`r8-selector-unit-r2.log`:**26passed/.29s**, covers both phases/busy first hint/
ordered fallback/default20/claimed errors and lost claim-commit reply, runtime/
F18/standalone wiring, cancellation disposal and supervision. Mypy560files passed
before the additional commit-edge test; final static recheck follows. Broad
real-DB dispatch/checkpoint/worker/manual/risk/API safety is running alone on
fresh0055 `tiewtrade_f18_release_r8_safety_20261027`; no counter probe until it
finishes. W1 still Failed/Partial, W2/W3notrun, W4r9 remains valid for unchanged
restore/financial contracts. R8 is not a capacity pass merely because code exists.


### R8 verification and W1r13 — 2026-10-28

`r8-affected-safety.log`:**221 passed/110.85s** on fresh0055 (dispatch/pair
checkpoint/full matching worker/manual inbox/all risk infra/risk+manual API).
Final ruff/format passed, mypy560files passed,7import contracts kept0broken.
Ready for Code Review announced; review confirmed candidate/claim budgets and
unknown-commit accounting preserve owner/FIFO/CAS/lease/financial authority.

Same donor/caps/10s probe after R8: Paper427rounds/**427processed**/0deferred/
590skipped; manual427rounds/70processed/0deferred/83skipped. Compare R7:
375processed/956Paper rounds. A phase now skips multiple hints before one claim,
so590skipped/427rounds is **not a skipped-round percentage**. Every sampled Paper
phase did useful processing; processed count rises375→427 (~13.9%) at the same
resource budget. This is a diagnostic improvement, not W1 or an SLA pass.

Client observation detail: F18's measured command-result polling still slept
250ms, longer than the existing200ms resting-order schedule. Following serial
requests can therefore arrive after old resting work is due. Use20ms for
**read-only result observation during measurement**; retain250ms setup and F15
standalone behavior. Expose setup/measured result polling separately from refusal
retry cadence in manifest. Command/input rates, deadlines, per-command policy,
server commit timestamps and all financial/SLA/resource oracles unchanged; more
frequent read load must pass those same gates. Old probe/percentile results keep
their original polling provenance, not relabeled as the new workload.
`r8-harness-poll-recheck.log`:**26passed/1.95s** (workload scheduling-hint/SLA,
worker composition and selection/commit-edge contracts). No engine code changed
for this status-observation adjustment; reuse221domain-safety/W4r9 results.

W1 `w1-v2-r13` ran alone on fresh0055 DB
`tiewtrade_f18_release_w1_v2_r13_20261028`, current R8 and declared result polling,
same100×20/600s/rates/60s/financial/SLA/resource gates. W2/W3 still pending; no
other workload/diagnostic/test job during W1 and no Git/Live action.


### Deep-review fixes — 2026-10-28 (owner instructed “แก้ไข”)

W1r13 finished **FAILED**, not running: TimeoutError at the existing60s
selected-owner breach/reset/reseed bound (`profile_workload.py:681`),
508offered/479admitted/466completed/77cycles. Preserve failure.json and all
previous failures; W2/W3 remain Pending Full Validation. No new capacity pass.

Review repair scope (same approved R6/financial/stop protocols):
- `risk_limits/views.py` carries current evaluation provenance and replays price
  pause continuity read-only; risk GET uses that evaluation's time/watermark,
  input readiness and pause status. Recheck freshness after bounded API tail.
- `risk_limits/stops.py` probes the existing lifecycle order_id index for active
  MARKET/LIMIT IDs in the current matching checkpoint with a LATERAL LIMIT1 probe; no whole
  episode lifecycle result set, no new index/schema or change to old-stop cuts.
- Reuse F15 worker telemetry with timestamped transaction records; F18 selects
  transactions starting in the declared measured window and retains their full
  duration even if completion follows the cut. Setup/drain/overflow samples do
  not enter that percentile. F15 default aggregate result remains available.

Tests add real-DB HTTP snapshot/recovery/pause continuity/no-GET-write evidence
and percentile regression with many fast setup samples and slow measured work.
Existing stop/reset/cancel/matching safety suites cover preserved financial,
old-stop and reservation contracts. Affected suite runs sequentially on a fresh
isolated0055 DB `tiewtrade_f18_review_fixes_20261028`; results recorded below.
No frontend appearance, trading formulas, thresholds, resources, Live, Git
commit/push or unrelated feature changes are authorized by these repairs.


Initial repair validation: `review-fixes-safety.log`: **199 passed/65.10s**
(risk infra/core/API, matching storage and workload supervision); whole mypy
**560 files passed**; affected ruff passed; import contracts **7 kept/0 broken**.
The later bounded-probe SQL refinement is rechecked separately below.
The real-DB HTTP regression proves current watermark/input/evaluation timestamps,
recovered READY with no stale pause alert, a restarted pause period after a
recovered intermediate frame, and byte-equivalent durable monitor evaluation
before/after GET. No schema/OpenAPI/frontend presentation changes.

`review-fixes-cycle` preserved **Failed60s**, diagnostic only: on a fresh clone
of the frozen W1r9 dataset with unchanged10+1 workers/4CPU/2GiB/price protocol,
selected-owner breach/stop/reset and20reseed finished; timeout occurred inside
F14 correction before commit. All24 new unique requests have SUCCEEDED command
results and only3 RECORD position events remain, no partial correction commit.
This is not a W1 pass and does not prove a timing improvement against a paired
baseline. Original r7 helper's known total-link assertion was corrected from3 to4
(3 RECORD fills+1 REPLACE) before this diagnostic; it was not reached.

Read-only EXPLAIN on the stopped clone found PostgreSQL decorrelated the initial
EXISTS form into a lifecycle Seq Scan. Refine it to a correlated LATERAL LIMIT1
lookup: real plan uses risk_lifecycle_cut(order_id) once per active candidate,
no full lifecycle Seq Scan. Observed execution1.308ms (EXISTS) vs0.603ms (LATERAL)
for the same20 current orders, single diagnostic observations only; no SLA claim.


Final LATERAL SQL recheck: `review-fixes-stop-recheck.log`: **27 passed/26.38s**
(stop/cancel/reset/concurrency/fill/preview fences). Final API/timestamp/harness
recheck: `review-fixes-final-recheck.log`: **29 passed/16.32s**. Final affected
ruff/format and whole mypy560 passed; no import-contract dependency changed
since7-kept check. Reviewed the repaired paths and their changed callers again;
three Medium findings repaired, High integrated-progress finding stays open.

`review-fixes-cycle-r2` **PASSED59.127s**, diagnostic only, after the indexed
LATERAL refinement, same frozen donor/current source/R8 resources and60s bound.
All3 scenarios completed: partial-fill loss0.05,20-target breach/stop/reset/reseed,
exact correction/replay. Cash delta−1.197901USDT, final held0BTC,4 new execution
links (3 RECORD+1 REPLACE),5 completed cycle commands. No acceptance_result.
Keep the previous60s failure; a single passing diagnostic is not capacity/SLA.

Only after that progress proof and final affected checks completed, start fresh
`w1-v2-r14` on0055 DB `tiewtrade_f18_release_w1_v2_r14_20261028` with final repaired
source and timestamp-window metrics. Reuse the same isolated runner/CPU/RAM/
workers/pools/rates/polling/600s/60s/financial/SLA gates. Runs alone; no overlapping
workload, diagnostic or test. W1 result pending; W2/W3 not started.


W1r14 **FAILED/Partial** after the2,000-order baseline and partial-fill oracle:
unchanged60s selected-owner reseed timeout,508offered/479admitted/467completed/
78cycles, no other scenario complete. Keep all artifacts; no W2/W3 invocation.
The three repaired Medium defects remain fixed, but this is direct evidence the
query repair alone does not close High throughput/progress under integrated load.

Restore F15's original250ms command-result observation in the F18 harness and
manifest, replacing the prior R8-internal20ms read-poll experiment. Preserve the
20ms refusal-hint retry, workers/runtime rounds, actual command/input rates,
financial/commit clocks and all thresholds. This is original observer pacing,
not an extension of any deadline or a financial/runtime scheduling change. Do not
relabel older20ms results. Validate affected harness and repeat same60s frozen
cycle before considering another fullW1. Treat any benefit as unproven until
measured; no diagnostic overlaps another job.


Observer restoration check: `review-fixes-observer-recheck.log`:17passed/1.64s.
`review-fixes-cycle-r3` remainedFailed60s (waiting for the final SELL fill), so
observer pacing alone does not close High. No W1 was started from that result.

Further High-scope implementation repair reuses `_identity` and the pure
`advance_matching` protocol in `infra/paper_orders/worker.py`: do not construct
an input's maximum UUID5 tuple when it produces no fill. A typed core
`ExecutionIdentityBudgetError` occurs before constructing the first fill fact;
the infrastructure catches it, allocates exactly the old full tuple and repeats
only the immutable pure calculation with the same input/time/setting/IDs.
No DB retry, extra claim, input skip, fake ID, changed fill/quantity/fee, new
trading cap, authorization bypass, scheduling/resource/rate/deadline change.
SELL fallback stays independent of opening readiness. Every authoritative
write still happens only after a complete transition returns, with R5's final
fenced recomputation unchanged. This removes unused UUID allocation, not a
financial precondition or a requirement. Exact deterministic identity prefix
matches the previous `fill:pair:generation:input:index` scheme.

Safety evidence history preserved: initial combined run201passed/3failed107.87s:
one new oracle compared BUY base-asset fee to USDT (fixed expected unit only);
two global-scanner F15 tests ran behind old pending owners in a reused DB.
Fresh DB and original F15-before-risk suite ordering confirmed204passed/103.47s
for the first short-prefix implementation. Final zero-ID no-fill implementation
then passed `review-fixes-identity-probe.log`:17passed/18.90s and the fresh-DB
`review-fixes-final-matching-r2.log`:104passed/66.25s, including full F15 worker,
fill/rollback/correction/cancel/reset/concurrency, unavailable SELL, preview/fence
and core purity/Paper-isolation gates. An earlier gate-path collection command
ran0tests and is not safety evidence. Final mypy561files and affected ruff/format
10files passed. Prior unrelated coverage remains reused, not relabeled as a new
full backend run. Three Medium fixes remain closed locally; High still open.

The new oracle verifies33 BUY and33 unavailable-risk SELL fills, exact gross
quantities/quote values/base-or-quote fees, unique UUID5 identities and complete
transition equality with the original full-identity call. A no-fill input
allocates0IDs and produces the original complete transition. No partial pure
attempt mutates the input or writes financial effects.

Only after the final104 safety/static checks, `review-fixes-cycle-r4` runs alone
on a fresh frozen donor clone to test the unchanged60s progress scenario with
final zero-ID code and original250ms result polling. No acceptance claim yet.


`review-fixes-cycle-r4` **PASSED53.863s**, diagnostic only, final zero-ID matcher
and restored250ms observation. Same3 scenarios,−1.197901USDT cash,0held,
4execution links (3 RECORD+1 REPLACE),5 cycle commands and20stop targets.
A single passing round does not establish integrated capacity/SLA. Preserve r3.
After final104 safety/static checks and this progress proof, launch fresh0055
`w1-v2-r15` on `tiewtrade_f18_release_w1_v2_r15_20261028`. Final source frozen
throughout, same600s/100×20/rates/60s/4CPU/2GiB/10Paper+1risk/fences/formulas/
financial/resource/SLA thresholds. Only result-observer cadence is restored to
originalF15; manifest records250ms. No workload/diagnostic/test overlaps W1.
W1r15 pending; W2/W3 not started. No capacity, Completed or activation claim.


W1r15 final outcome: **FAILED/Partial60s at selected-owner reseed**, after full
2,000-order baseline/partial-fill oracle.525offered/505admitted/491completed/
191fills/97cancels/101replays/84cycles.3 planned risk scenarios not complete.
Read-only stopped-DB check: selected owner39requests (20baseline+1BUY+18reseed),
20stop targets; latest7requests all SUCCEEDED. No capacity/SLA acceptance claim,
no W2/W3 invocation. All runtime containers stopped; only owned PG/Redis remain.
No Live/Git mutation. Preserve r14/r15 failures and all diagnostic results.

Repair review checkpoint: three Medium findings closed locally, plus deterministic
no-fill identity allocation optimization safe under final104 tests/mypy561/static.
High remains open under actual integrated load; diagnostic53.863s is not a pass.
Proposed [R9](../same-pair-dispatch-amendment.md) makes a concrete, bounded
same-pair selector experiment reviewable; no R9 selector/routing-projection/migration has
been implemented. It changes the R8 ordered selection method and therefore
requires new owner approval under plan301 before dependent implementation.
Do not ask again for existing R6/R7/R8 or completed correctness repairs.


Final source identity check (read-only, after W1 stopped) matches W1r15 manifest:
`078f6f1aa1faa25a51d522e2cbdee84ca7abc0d26a267e2a20a3ca02759eb4b0`.
`git diff --check` passed. No active workload/diagnostic/test container remains.
Owner approval question sent only for Proposed R9's changed selection method;
existing R6/R7/R8 approval and completed repair authority persist. No R9 code
or migration is authorized/implemented before the answer. Required CI remains
pending a separately instructed Git action; no commit/push/merge performed.


### R9 approved implementation/review — 2026-10-28

Owner explicitly approved R9 before implementation. Earlier Proposed/unauthorized
entries above are historical. Added schema0056 nonfinancial routing projection,
optional same-pair selector, canonical owner-locked claim proof, atomic guard
once per original head/due anchor, and explicit production/F18 composition.
Standalone F15 default remains R8. No financial formula, claim budget, workers,
rates,60s deadline, SLA or resource threshold changed.

Real PostgreSQL affected safety:225passed127.67s (`r9-affected-safety.log`).
Enabled composition plus R9 selector/recovery/permissions/rollback coverage:
49passed12.94s (`r9-enabled-composition-r2.log`). Mypy563files and7 import
contracts passed; diff whitespace clean. Initial fixture/test-oracle failures
remain in artifact logs; no failing product check relabelled. Populated
0056→0055→0056 roundtrip preserves exact financial facts, invoker/RLS grants,
legacy rolling-writer compatibility, busy migration atomic refusal and retry.
Recovery includes lost commit acknowledgement, concurrent claim winner, lease
takeover/stale fence, due CANCEL fallback and SELL under unavailable risk.

Ready for Code Review announced with tests/pending/risk summary. Targeted R9
review examined selection FIFO/fairness, canonical proof/guard transaction,
privileges/RLS, additive migration and runtime/harness composition. No new
Critical/High correctness finding identified. Existing integrated-progress High
remains open until unchanged full workload passes. Next run only the unchanged
selected-owner60s reproduction on a fresh frozen100-owner/2000-order clone,
then fresh W1 if it succeeds; W2/W3 not started. Disable preference back to R8
if the experiment does not improve progress; preserve all failures. No Live
orders or Git mutation. Full prior regression3607predates R9;225+49 are affected
checks and do not replace pending integrated validation.

R9 frozen progress reproduction **PASSED52.300s**, diagnostic only
(`r9-full-cycle/result.json`), same3scenarios/20stop targets/20reseed/5commands,
−1.197901USDT/held0/4execution links. Monitor lock refusals remain logged and
are not evidence of SLA success. Launch fresh0056 W1r16 with final R9 enabled,
same600s/rates/100×20/60s/4CPU2GiB/10+1 and all financial/SLA gates unchanged.
No diagnostic/test overlaps W1. W2/W3 pending; High integrated progress open.

W1r16 **aborted setup**, runner started before new DB migration committed and
failed on missing risk_protocol_control. Orchestration error, no acceptance or
financial failure conclusion. Preserve `w1-v2-r16.log`; not rerun blindly.
Waited for fresh W1r17 migration success, explicitly verified0056/control/index
before launch. W1r17 is the R9 integrated candidate; resources/rates/gates/source
unchanged, workload runs alone.


R9 W1r17 **FAILED/Partial60s at selected-owner reseed**, despite complete
2000-order baseline/partial loss0.05 oracle.527offered/506admitted/495completed/
196fills/95cancels/102replays/87cycles; only first risk scenario completed.
Stopped-DB read-only check:301heads used preference (so option actually ran),
selected owner40requests/39headers/20stop targets. These facts are progress,
not deadline/capacity/SLA acceptance. Preserve `w1-v2-r17/failure.json` and log.

As required by R9§10, explicitly disabled production/F18 preference back to
R8; optional selector and additive0056 stay available but do not activate.
Affected disabled-composition29tests passed (`r9-disabled-composition.log`).
No blind W1 retry and no W2/W3 run after failed W1. High remains open; a different
selection/architecture method requires a new concrete approved amendment.

Affected W4 on cloned frozen fixture migrated0056 **PASSED**
(`w4-r9-schema56/result.json`, `risk-recovery.json`). Existing restore verifier
plus external read-only schema comparison covers exact canonical rows, financial
facts/baselines, pending-stop recovery, RLS/table AND column grants, R9 invoker
function definitions/grants, triggers and partial index across pg_dump/restore.
Original source fixture preserved. Initial external-helper import-path launch
error kept separately; corrected sys.path before successful verification, no
product change. No Live order.

Final backend full regression now runs alone on fresh schema0056 DB with
preference disabled; prior3607result predates current R9/financial matching
changes and is not relabelled as final validation. Existing frontend remains
unchanged by R9 and its earlier evidence is reused.

Full regression initial run interrupted after1failed/104passed105.93s to
inspect failure. `test_catalog_downgrade_uses_source_maintenance_for_protected_candles`
failed because the newly created test DB omitted CI bootstrap event triggers.
Setup omission, not repaired by changing source/test expectations. Preserved
`r9-full-regression.log`. Created fresh r2 DB, installed existing
`db/bootstrap/10-event-trigger.sql`, migrated0056 and verified all3bootstrap
event triggers enabled before final full run. Role/bootstrap contracts unchanged.
`r9-full-regression-r2.log` now running alone; no workload/diagnostic overlaps.


### R9 final repair checkpoint — 2026-10-28

**R9 experiment closed with fallback; F18 not Completed / not ready to merge.**
The approved same-pair implementation and failure path were executed. W1r17
still fails the original60s reseed gate; production/F18 option is false (R8),
not silently activated. No W2/W3 capacity claim. Existing High remains open.

Full backend coverage on final immutable source: **3675 unique tests PASSED**,
with2 unchanged venue_contract tests excluded by normal CI marker. This is a
resumed full regression, not one uninterrupted green process:1192passed from
`r9-full-regression-r2.log` remain valid after only per-DB logging bootstrap
correction; `r9-regression-remaining.log` passed2502in438.70s including19already
passed redaction checks repeated as affected. Ordered collection and exact
selected/result sets verify1192+2502−19=3675, missing0/unexpected0 in
`r9-full-regression-coverage-result.json`; full node map and individual remaining
results saved. Initial failures/interruptions remain Failed/Partial logs.
No source/test assertion changed to resolve either environment failure.

Final static: ruff/format10affected files, mypy563files, diff whitespace passed;
7 import contracts remain valid (no imports changed after that check). Final
source `ce1904d2bfc7780072cc867a9103bf5570c6254b97a08cd6074c3ea9cc6a251b`
in `r9-final-source.json`, explicit prefer_same_pair_admission=false. W1r17's
enabled-source manifest is historical failed evidence, not a pass on final
disabled source. W4final0056 passed with disabled composition. Frontend unchanged
by R9; reuse prior frontend296/type/lint/build/browser evidence. Required remote
CI remains pending separately instructed Git action. No commit/push/merge.

After all suites stopped, read-only stopped-W1 timeline checks show18successful
reseed results plus1transferred request without final engine result at shutdown.
For those18, request→bridge commit median138.7ms and bridge→engine-result commit
median1809.8ms/max5027.6ms (`r9-w1-selected-timeline.csv` and summary). These
intervals include queue wait/processing and do not isolate a root cause or prove
SLA. They do identify the remaining investigation boundary as engine progress
after transfer, rather than justify another blind selector retry. No new
selection/protocol/architecture change has been invented or implemented. Any
different method remains subject to plan§5/R9's amendment-before-code rule.

Final review rechecked disabled production/harness composition, claim guard and
canonical proof, migration/rolling/restore privileges, recovery/idempotency,
financial oracles and complete test coverage. No new Critical/High correctness
finding; **High integrated progress remains unresolved**. V21W1failed/W2W3notrun;
V22/V23 external dependencies remain pending. All test/workload/diagnostic runtime
processes stopped; only owned PostgreSQL/Redis base services remain.

Result: **CHANGES REQUIRED**.


### Owner-requested R9 maintenance refactor — 2026-10-28

Reviewed only latest-task R9 additions/call sites. Changed2code files:
0056_same_pair_dispatch.py now defines scanner hint grants and refresh-trigger
tables once for upgrade/downgrade; routing.py private SQL fragment names identify
busy owners, READY risk hints and cancel/unknown-hint exclusions explicitly.
Reuses existing static metadata/`op.execute` loops; no new helper layer, behavior,
financial rule, query predicate, ordering, privilege or activation change.
Other R9 guards/checks remain necessary for failure recovery and are retained.

Verification:34upgrade+15downgrade statements exactly equal before/after ignoring
whitespace; all3runtime SQL strings byte-identical (`r9-refactor/sql-equivalence.json`).
Fresh PostgreSQL DB includes both existing bootstrap scripts before0056migration.
Relevant existing legacy dispatch/R9/round composition/claim budget/isolation
tests **44passed** (`r9-refactor/tests.log`), including real financial reservations,
SELL under unavailable risk, race/lease/lost-ack fencing, grants and populated
0056→0055→0056 rollback/recovery. Ruff/format2changed code files passed; configured
mypy563files passed. No new tests duplicate implementation assertions.

Ready for Code Review announced with scope/results/pending risk; final review
confirmed only metadata deduplication/private renames, same expanded SQL and
option=false. Reuse earlier3675full regression and restore evidence because no
emitted SQL, contracts or logic changed; no repeated workload/diagnostic/full
regression without an affected risk. Source identity after refactor:
`7611ebf08a8241f56a1b52dfb0708455c2e123f3ec5712f889a8eee948808a10` (`r9-refactor/source.json`).

Refactor checkpoint passed. Existing W1Failed/High and W2/W3Pending are unchanged;
this cleanup does not resolve integrated progress or make F18Completed/merge-ready.
No Live/Git mutation; no unrelated code changed.


### Engine queue/process/commit diagnosis — 2026-10-28

Owner requested next-step analysis/repair. External-only timing runner executed
alone on fresh0056 `tiewtrade_f18_release_engine_timing_20261028` with both
bootstrap scripts, original100×20/10+1/4CPU2GiB/R8/rates and owner60s. No domain
code or financial rule changed. Instrumentation records static SQL templates,
not parameters/payload/secrets. Outer65s observation cap is diagnostic only.
`engine-timing/failure.json`:2000baseline/partial0.05 passed, then original60s
reseed timeout;496offered/469admitted/455completed/73cycles. All runtimes stopped
before stopped-DB timing correlation; no overlapping diagnostics/tests.

For12completed reseed requests, native successful-claim queue wait median
2699.03ms, claim transaction7.32ms, process function196.74ms/transaction234.17ms,
commit-close1.64ms, SQL166.51ms. Bridge229.97ms; engine-result2988.22ms.
Independent medians do not sum. Outputs: `engine-timing/selected-commits.csv`,
`selected-breakdown.json`, per-worker timing and `timing-aggregate.json`.
Instrumentation overhead is visible (old uninstrumented W1r17 engine median
1809.8ms), so this is not a capacity/SLA pass or proof of a single root cause.
2467matching transactions over the60s window across100owners are consistent
with an order-of-seconds original fairness pass. No evidence justifies another
blind within-owner R9 retry or changing commit/financial semantics.

Concrete [R10 proposal](../admission-lane-amendment.md) alternates exact R8 rounds
with bounded admission-priority rounds using unchanged R9 canonical eligibility,
CAS/guard and checkpoints; ranks preferred owners before the20hint cut, preserves
normal fairness attempts and all budgets/gates. It changes cross-owner selection
and is Proposed pending owner approval under plan§5/AGENTS, not implemented.
No repeated approval for R6–R9, earlier correctness repairs or refactor. Current
R8 remains active/R9disabled; existing High/W1Failed/W2W3Pending unchanged.


### R10 approved implementation/safety — 2026-10-28

Owner explicitly approved R10 before code; amendment Approved and plan appended
with reuse paths/validation. Added separate admission_first selector option
with R9 candidate/proof/guard shared unchanged; orders preferred heads before
20hint cutoff, other heads retain original order. Existing R8/R9/proof SQL
semantically identical (whitespace-normalized equivalence checked). No migration
or financial input/calculation/gate/claim/worker/rate/resource/deadline change.

Production/harness share small standard-library cycle/repeat iterator, choosing
mode before native call so success/skip/defer/error do not hold a priority phase.
Starts R8 on each process creation; legacy/F15 defaults preserved; R9 option
remains disabled. New R10 explicit ALTERNATE_ADMISSION_PRIORITY initiallyfalse,
enabledtrue only after253affected real-DB safety passed140.58s. Existing20R9
recovery/permission/financial tests exercise both R9/R10 (40cases). New tests
cover excluded21stowner, sustainedNEW/resting normal progress, cross-owner cancel
and unavailable-risk reduction with exact cash/held oracles; both actual
production/harness loops cover alternation/restart after success/skip/defer/
scan failure. No duplicate claim/fill or financial oracle failure.

Initial selector63passed30.60s; affected253passed1warning (`r10-affected-safety.log`).
Enabled composition26passed8.85s (`r10-enabled-composition.log`); mypy564files,
ruff/format9files and diff whitespace passed. Early lint long string and unused
type-ignore corrected in test only, no runtime/test behavior altered. No failing
product test was relabelled. Prior3675full regression reused for unchanged
financial/domain/legacy contracts, with affected callers/dependencies rechecked.

Ready for Code Review announced with scope/tests/pending/risks. Targeted final
review confirms oneclaim guard, canonical recheck, first/R8/failure alternation,
legacy mode and runtime/harness flag consistency. No new Critical/High correctness
finding; existing integrated-progress High open until actual full gates pass.
Next run only uninstrumented frozen60s progress, then fresh W1 if it succeeds;
W2/W3 conditional on full W1 passing. If R10 does not help, disable back to R8
and preserve failure per approved amendment. No Live/Git mutation.

R10 frozen progress **PASSED43.4648s**, diagnostic only
(`r10-full-cycle/result.json`): same3scenarios/20stop/20reseed/5commands,
−1.197901USDT/held0/4execution links. Lock refusals remain in logs, no SLA claim.
After runtime stopped, prepare fresh0056 W1r18 with both bootstrap scripts.
Same600s/100×20/rates/60s/10+1/4CPU2GiB/fences/financial/SLA/resource gates;
R10 enabled, R9 standalone option disabled. Source frozen; no diagnostic/test
overlap W1. W1pending, W2W3notstarted. No capacity/Completed/activation claim.


R10 W1r18 **FAILED/Partial at approximately172.5measured seconds**, after
complete2000baseline AND all3planned risk scenarios (partial0.05,breach20stop/
reset20reseed,exact correction/replay). This confirms progress beyond the old
selected-owner60s failure, not full W1 acceptance.1658offered/1639admitted/
1626completed/644fills/324cancels/329replays/312cycles. No W2/W3 invocation.
The later owner-cycle60s deadline expired inside its final RESET poll/connection
close. Post-stop inspection found no accumulated reset inbox: only1pending
RESET freshly submitted near shutdown. That owner's four recent requests show
LIMIT SELL bridge01:49:24.103392→result01:50:03.962894 (~39.86s), native claim
revision5; other three requests completed. Claim count alone cannot identify
why it retried. Preserve `w1-v2-r18-timeout-owner.csv`, pending snapshots and
fullfailure/logs. No deadline/financial/SLA gate changed or failed run relabelled.

R10 improved the original bottleneck and completed planned scenarios, with no
identified financial or fairness regression; remaining High is sustained cycle
progress. Keep the approved experimental mode while diagnosing this distinct
retry delay; production NEW admission stays gated, no acceptance claim.
External SourceUnavailable-location diagnostic (no messages/parameters, existing
10+1/resources/claim/retry policy) ran alone on a frozen donor clone. Initial
helper failed before useful sampling because an old snapshot owner remained
latched (correct ORDER_SAFETY_UNAVAILABLE refusal). Preserve that failure.
R2fresh clone resets any old latched owner using real API/risk-worker RESET
before positive cycles, not direct state edits or bypasses. It resumes100owners/
2000baseline with source trade-ID continuity, schedules selected pristine owner
first and bounds observation65s (owner60s unchanged). Diagnostic only, cannot
replace W1. No domain/runtime code changed after frozen W1 candidate.


### R10 final experiment checkpoint — 2026-10-28

**CHANGES REQUIRED — full W1 not passed.** R10 implementation/review/safety and
approved experiment completed; feature notCompleted/merge-ready. W1r18 passed
the formerly blocked selected-owner scenario and all3planned risk scenarios,
but a later owner-cycle60s expired after approximately172.5measured seconds.
Preserve1658offered/1639admitted/1626completed/312cycles and completefailed logs.
No W2/W3 execution, no financial/SLA/resource acceptance inferred.

Additional diagnostic controls and limitations: frozen source-error helpers r1
and r2 both stopped on positive-order safety refusal from inherited snapshot
state and produced no useful matching SourceUnavailable samples. R2used real
RESET for old latches but inherited outstanding business state still invalidated
that positive-cycle fixture; no gate bypass or repeated blind use of that fixture.
Fresh sameW1 fixture diagnostic then failed baseline3/20 on
RISK_PRICE_UNAVAILABLE before measured observation. It recorded343baseline
SourceUnavailable locations:310inorder_book_storage.read_inputs:310,33in
BookState.require_ready:82 (see `r10-fresh-source-errors/classification.json`).
These observations establish source-freshness failures during that diagnostic;
**they do not identify the exact exception for W1r18's ~39.86sSELL result**.
Claimrev5 alone also does not prove exponential retry was its cause. No retry
policy, source-age gate, publication protocol or financial calculation was changed.

Offline price-frame commit-gap inspection: W1r18 measured p99gap1224.6ms,
max1773.5ms; fresh-error diagnostic baseline p99gap767.5ms/max2909.1ms. Multiple
frames can share a commit, and gaps alone do not isolate publisher CPU, lock
wait or transaction cause. They are not a full ingestion/SLA evaluation. A
different retry/recovery/publication method needs its own grounded amendment;
none invented or implemented here. All partial/failed diagnostic logs retained.

Because R10did not establish fullW1/progress acceptance, disabled experimental
ALTERNATE_ADMISSION_PRIORITY back tofalse (R8) under approved fallback; earlier
keep-enabled-during-diagnosis entry is superseded by this final decision.
PREFER_SAME_PAIR_ADMISSION remainsfalse. Optional R9/R10 code/tests remain, no
new schema or actual trading rule. Production NEW activation stays gated.
Disabled composition **26passed9.28s** (`r10-disabled-composition.log`); final
ruff/format9files, mypy564files,7import contracts and diff whitespace passed.
Affected253safety and unchanged3675regression/0056restore facts retained with
explicit scope; no repeated full/workload pass claimed on disabled final code.

Final source identity:
`36b14e2f23a9524a0e982805852274e2039d832521df7958b6ac08b24b41d8ac` (`r10-final-source.json`), both options false.

Final review rechecked default selection, mode/guard/CAS, financial invariants,
rollback/defaultF15 compatibility and flag/harness coherence. Existing High is
sustained cycle progress/full validation, with exact slow-SELL cause unresolved.
All experiment/test runtimes stopped; only owned PostgreSQL/Redis base services
remain. No Live order, commit, push or merge. V21Failed/Pending and V22/V23
dependencies remain open; no Completed/activation claim.

### Source-resumption diagnosis — 2026-10-28 (no application change)

Continued the authorized slow-SELL investigation sequentially; no diagnostic,
workload or test jobs overlapped. All paths below are under external artifact
root `/Users/chainarongjaykeaw/Projects/TiewTrade/validation-artifacts/f18-20261027`.

- Trace adapter real-query self-test preserved returned mappings (apart from
  naturally changing database time); helper compilation passed. Observations
  record timing/source provenance, not order payloads, financial values or secrets.
- `retry-trace` failed baseline16/20 with WriterLeaseLost before measured SELL.
  SourceUnavailable samples included book verification older than1s and source
  age crossing1s between reading and processing. Publisher operations sometimes
  exceeded2s; synchronous observer I/O may perturb these figures. Neither this
  nor after-stop host swap/memory readings isolates historical W1's cause.
- `target-sell-trace`: all8 funded native LIMIT SELL/cancel pairs succeeded with
  no retry while background baseline had reached2/20. Diagnostic stop was
  intentional, not acceptance. Its cloned resume fixture failed source readiness
  at baseline4 before the target sequence; not repeated as a valid positive run.
- `sell-only-retry-trace` was intentionally aborted during baseline because R8
  did not match the historical R10 experiment context. Buffered R10-only replay
  `r10-sell-retry-trace` failed baseline13/20 with TimeoutError before measured
  SELL. Runtime override existed only in the diagnostic subprocess; application
  R9/R10 flags stayed false. Preserve failures and aborted records.
- `controlled-sell-retry` used a fresh0056 database and actual role/claim/native
  worker flow, funded BUY followed by LIMIT SELL. First Docker attempt failed
  missing test-only pytest before data creation. Native dev replay deliberately
  paused execution verification while maintaining lease/latest-trade publication
  through public APIs, then resumed verified books after7.018s. Persisted original
  defer was0.978s/4.986s/29.987s; SELL result arrived36.555s after first failure,
  **29.454s after source resumed**. Exactly one order header, no additional SELL
  fill and unchanged cash/held were asserted. This is a controlled component
  reproduction, not the resource-constrained capacity or SLA acceptance run.
  Evidence: `controlled-sell-retry/result.json`, `controlled-sell-retry-native.log`.

The controlled result proves a post-resumption scheduling wait in the existing
backoff. It **does not prove the exact historical W1r18 slow-SELL exception** or
solve publisher throughput. No money, risk, source-age, retry or application code
was changed; no further full test result claimed. R8 remains the final runtime;
V21Failed/Pending, V22/V23 dependencies and the High progress finding remain open.

A concrete bounded source-resumption probe is documented in
`../source-resume-amendment.md` as **R11 Proposed**, awaiting approval. It changes
retry selection and therefore must not be implemented under R6–R10 approval.
No R11 schema, grants or code exist yet. All diagnostic actors stopped; no Live
orders, commit, push or merge.

### R11 implementation and affected verification — 2026-10-28

Owner approved R11 before code. Implemented0057 wait/probe metadata and narrow
SCAN publication grants; routing source-progress hints and owner-locked canonical
proof; one consumed probe guard with unchanged attempts/original due and a lease
capped at that due. Existing native execution/risk/reference checks remain in
place. Healthy attempts=0 writes clear metadata atomically through the0057trigger,
including old writers and covered-pair reschedules. Default-off SQL works on0056.
Production/harness source-resumption option is explicit and shared in manifests.

Ready for Code Review was announced with changed areas, test state, pending
comparison/restore/workload and CAS/lease/old-writer/SCAN risks. Review checked
claim/defer/commit boundaries, normal-query reuse, R9 early-head exclusion,
financial isolation and narrow privileges. Real-role checks cover source-only
classification, both-feed progress, direct probe in R8/R9/R10, stale due/revision/
pair/cancel/unknown/source hints, competing claims, rollback, crash/expired lease,
real dropped COMMIT reply, generic/source defer preserving due, one probe per
streak, original next retry5m after the fourth ordinary failure, old writer reset,
latch refusal, pending-order reset safety and closed-episode identity. No Critical
or High code defect found in this review; full acceptance remains open.

Evidence under the same external artifact root:
- `r11-affected-safety-r3.log`:111 tests passed (R11, R9/R10, worker rounds,
  dispatch and native worker dependencies).
- `r11-lost-ack.log`: real proxy-dropped probe COMMIT response passed.
- `r11-enabled-composition.log`:13 passed, including2 new source-aware ordinary
  R9/R10 differential cases. Other11 cases overlap prior safety evidence.
- `r11-latch-reset.log`: latch case passed; reset fixture incorrectly expected
  pending-order reset to succeed. Existing RESET_UNSAFE was correct. Test now
  asserts refusal, settles through native latched admission, retries reset with
  a new key and rejects the old probe. `r11-reset-r2.log` passed. No business code
  changed for this test correction.
- Initial source test runs retained: test-only direct price status mutation was
  rejected by the existing publication fence; changed to public writer API.
  Permission-denial assertion was corrected to the repository's translated
  NotPermittedError. No bypass or production fix was needed.
- Relevant ruff passed; mypy565files and7import contracts passed. One test-only
  Optional narrowing corrected after initial mypy failure; diff whitespace clean.

`r11-controlled-sell/result.json`: same actual funded SELL and deliberately7s
execution-verification gap as prior diagnostic; ordinary persisted waits still
0.977s/4.993s/29.990s. R11 completed at7.280s,0.131s after source resumed (baseline
36.555s/29.454s respectively). Exactly one header; unchanged cash/held, no extra
SELL execution, exact0.999BTC reservation. Native isolated component comparison,
not workload/SLA acceptance or proof of historical W1r18's exact exception.

After these checks enabled SOURCE_RESUMPTION and already-approved R10 alternation
for candidate qualification. R9 standalone preference stays false. No financial
activation gate opened. Preparing frozen100×20/60s cycle; freshW1 follows only
progress proof. W2/W3,0057restore and final regression/acceptance remain pending.
No concurrent diagnostic/test/workload runs, Live orders, commit, push or merge.

R11 qualification update: source-aware ordinary R9/R10 selection matches the
original selector and executes through canonical proof; latch and reset cases
bring affected safety to116 unique passing tests. The pending-order reset refusal
was retained, not bypassed. Final mypy565/ruff/diff checks pass.

Frozen100×20 comparison `r11-full-cycle` failed during initial DECREASE with
RISK_SOURCE_UNAVAILABLE before Paper workers started; inherited risk projection
was still replay-pending. No timed cycle result. Initial migration launch raced
clone creation and failed database-not-found; after clone/bootstrap completed,
migration retry succeeded and0057/3event triggers/commit timestamps were verified.
All setup failures retained; no source/gate change was used to relabel a pass.

Fresh fullW1 `w1-v2-r19` failed while seeding baseline after Paper workers
started: WriterLeaseLost, zero measured counters/scenarios. Later snapshot check
confirmed272native commands/253SUCCEEDED,69source waits and0consumed probes.
Risk-monitor financial-fence lock timeouts appeared during setup. This run does
not establish R11 performance regression or acceptance; its source-resumption
mode was active during baseline, but no extra probe was consumed. No repeated workload/diagnostic was launched to chase a pass. Both
SOURCE_RESUMPTION and ALTERNATE_ADMISSION_PRIORITY are back tofalse under approved
fallback, pending successful full qualification. R11 implementation/component
benefit remains evidence; W1 failure and W2/W3 dependencies remain open.

Final disabled-source full backend regression is running alone on fresh0057 with
both bootstrap scripts and all3event triggers; final0057W4 restore follows it.

Final review found one Medium rollout issue: dropping0057 discards a consumed
probe guard; a later upgrade must not rearm the same still-failing command.
0057 now conservatively marks pre-existing attempts>0 as probe-used, preserving
all schedules/attempts and restoring FORCE RLS in the same locked transaction.
Healthy checkpoints clear it normally. This implements R11's conservative
mixed-version behavior; no additional probe method or financial rule. Roundtrip
tests cover both unused and already-consumed failure streaks.

Initial full regression `r11-full-regression.log/xml`:2217 passed,1 failed,
2 venue contracts deselected,727.35s. Failure was the new exception-classification
test selecting a different retained owner's command through the global scanner.
The test now supplies its own candidate to the native round (real claim/defer/CAS),
while separate real scanner/claim tests retain routing coverage. No production
selector or business rule changed for this isolation correction.

Resume uses exact JUnit pass identities and rechecks modified source-resumption
cases, full migration contracts and existing R9 roundtrip. Unaffected passed
cases are reused; all unrun/failed cases remain selected. Collection/result maps
are `r11-regression-coverage.json` and `r11-regression-remaining-results.jsonl`.
Initial failure remains preserved; no uninterrupted full-pass claim.

Resume setup correction: attempting destructive migration rechecks on the used
full-suite DB correctly hit the existing immutable risk-history downgrade guard
(`r11-regression-remaining.log`,2passed/1failed). No history or guard was removed.
Created a fresh r2 database, ran both bootstrap scripts/migrations, and resumed the
same1537 selected cases there (`r11-regression-remaining-r2.log/xml`).2192
unaffected original passes remain reused. Retain the failed setup attempt.

Resume r2 passed580, then existing unrelated ingestion completion test failed
(3 COMPLETE instead of4). Persisted BTC/15m state was PENDING/SOURCE_FAILURE with
attemptcount1; PostgreSQL logs in its04:42:47–50UTC window contain exactly one
statement timeout, no lock timeout/deadlock (`r11-ingestion-failure-state.txt`,
`r11-ingestion-timeout-log-counts.json`). No R11 code touches candle ingestion.
A bounded read-only exception observer reran that case plus its preceding timeout
case:2passed1.82s; only the preceding test's four intentional TimeoutErrors were
observed. No ingestion code, assertion, timeout or resource change. Initial
transient failure remains recorded, not an uninterrupted green run.

Resume r3 rechecks the entire ingestion module and all still-unrun cases, reusing
exact passed node IDs from the prior checkpoints; collection set must match the
3729-case current suite. See `r11-regression-coverage-r3.json` and remaining-r3
results/log/XML. No diagnostic/test/workload overlap.

### R11 final implementation checkpoint — 2026-10-28

**R11 implemented/reviewed with component benefit; F18 remains Pending Full
Validation, not Completed or ready for production activation.**

- Full backend coverage: **3729 unique cases passed**, exact current collection
  matched with missing0/unexpected0. Resumed verification, not one uninterrupted
  green run:2724 valid passes reused plus1005 final selected passes (36.71s).
  Modified rollout tests and the complete ingestion module were rechecked.
  Two venue-contract cases excluded by unchanged normal CI policy. Initial
  test-isolation, used-DB downgrade and transient ingestion failures remain in
  their original logs. `r11-full-regression-coverage-result.json` contains the
  exact coverage result; collection/node-result/XML artifacts preserve provenance.
- **W4 final0057 passed** (`r11-w4/result.json`, `risk-recovery.json`). Cloned the
  original financial/risk fixture; seeded only two reconstructible dispatch
  projections (unused source wait and consumed guard), with financial digest
  unchanged. Exact canonical data including these fields, RLS/column grants,
  routing/reset functions/triggers/indexes match after backup/restore. One expired
  claim recovered to zero; real risk-policy recovery completed pending stop and
  authorization-only exact retry. Zero duplicate cancel effects; financial facts
  and reset baselines unchanged. Synthetic marker fixture explicitly recorded in
  `r11-restore-marker-fixture.json`; no invented financial history.
- Final ruff and format9files, mypy565files, diff whitespace passed.7 import
  contracts remain valid (no source imports changed after that check). Prior
  frontend296/type/lint/build/browser evidence is unaffected; no frontend changes.
- Final review closed the Medium downgrade/re-upgrade guard rearming finding:
  existing attempts>0 conservatively suppress optional probes until healthy
  checkpoint. Both used/unused rolling-streak cases and FORCE RLS verified.
  Native claims, retries, source gates and financial code otherwise unchanged.

Final source identity:
`03a0114ef9843983fe24983341d31970a9ffb0ece24b2fb52154dbb23fc962b5`
(`r11-final-source.json`,735files,0057). Both SOURCE_RESUMPTION and
ALTERNATE_ADMISSION_PRIORITY are false, and standalone R9 preference is false.
The earlier enabled candidate/hash and controlled comparison remain historical
experiment evidence, not full acceptance on the final disabled runtime.

Remaining: High integrated progress/source-liveness gate. FreshW1r19 failed with
WriterLeaseLost during baseline seeding after Paper workers started, before measured commands;
financial-fence lock timeouts were observed. This does not establish an R11
performance regression or solve historical W1r18's exact delayed-SELL exception.
No W2/W3 run or capacity/SLA pass claimed. V21 remains Failed/Pending Full
Validation; V22/V23 dependencies and production admission gates remain open.
Any different retry/publication/scheduling method needs its own grounded approved
amendment. No new method, weakened source freshness or extra resource was applied.

All test/diagnostic/workload actors stopped; only owned PostgreSQL/Redis base
services remain. No Live order, commit, push or merge. Close this implementation
checkpoint without adding further speculative diagnostics or refactors.


### W1 publisher-lease investigation — 2026-10-28 (continued)

Corrected earlier setup classification: traceback at profile_workload.py:983 is
seed_baseline after Paper workers start. Snapshot confirms272commands/253successes,
69source-wait markers/0consumed probes; zero counters refer only to the measured
window. The expired lease is execution-book renewal, at order_book_storage.py:171
(UPDATE returns no row after its preceding locked validation), not price renewal.
Existing logs alone cannot distinguish client scheduling/resource stalls from
server execution delay. One bounded instrumented W1 setup will record publisher
SQL timings/server-clock observations, event-loop lag, sampled parent Python
stacks and parent cgroup pressure, with unchanged10+1/4CPU2GiB and no concurrent
workload/diagnostic. No trading/source/retry gate or application code changed.

Bounded publisher-stall diagnostic completed at its150s cap (not acceptance):
no WriterLeaseLost reproduced. Parent cgroup was throttled984/1538periods;
CPU pressure full avg10 reached36.97%, memory peak637415424bytes with no OOM
or memory-pressure events. Publisher SQL delays included clock queries289ms
and publication fence595ms; maximum event-loop gap846ms. Sampled stacks mostly
showed asyncpg socket writes/waits, not financial calculation. These observations
support reducing client roundtrips but do not prove the historical failure cause.
Artifacts: publisher-stall/{publisher.jsonl,stacks-pressure.jsonl,observation.json}.

Equivalent source lease SQL tuning: reuse existing `_locked` functions in
infra/market_data/{order_book_storage,realtime_storage}. Materialize the locked
row before reading clock_timestamp in the outer SELECT, eliminating one client
roundtrip per check. Price exclusive fence remains a separate preceding command;
owner/generation checks,5s expiry, final checks, immutable frames and retry policy
are unchanged. No lease reacquisition or resource changes. Added actual row-lock
expiry coverage for both sources; existing mutation-wait rollback and financial
publication-fence tests are retained. First focused21tests passed; additional
book/risk/matching/service regressions:206passed in105.692s, zero failures/errors/skips
(source-clock-tests.{log,xml}). Final diff review found no new Critical/High issue
in this SQL-only change; post-lock clocks, separate fence ordering and terminal
checks are preserved. New assertions exercise real lock waits against PostgreSQL.
Ruff passed4files; mypy passed2changed sourcefiles. W1/W2/W3 remain unqualified.

Same150s bounded comparison (`source-clock-stall`, separate fresh0057 DB):
1255successful commands/1262admitted versus1099/1100before; observed progress
+14.2% in this single diagnostic. Maximum loop gap233.6ms versus846.0ms;
maximum publisher SQL452.3ms versus629.7ms. Both reached the intentional150s cap
during baseline; neither reproduced WriterLeaseLost. Financial-fence timeouts
persist. This is partial improvement, not W1/SLA qualification or a proven fix
for the original lease loss. Keep the equivalent SQL tuning with safety coverage;
do not infer capacity from diagnostic counters. Original diagnostic invocation
was rejected by the isolated-release-database name guard before workload startup;
renamed the newly created owned DB to the required release prefix and retained
both logs (source-clock-stall.log and source-clock-stall-r2.log).
Final actor check: only owned PostgreSQL/Redis remain, no overlapping workload.
Earlier3729-test and W4 evidence still covers unchanged areas; final source now
includes this source-lease change, with affected coverage above. Full source
identity is in source-clock-stall/manifest.json. No Live orders, commit or push.

### Fresh W1r20 — source-clock SQL candidate, 2026-10-28

Ran one uninstrumented W1 with native R8/default-off R9/R10/R11, fresh0057 DB
`tiewtrade_f18_release_w1r20_20261028`, unchanged10Paper+1risk/4CPU2GiB aggregate
and approved thresholds. Baseline2000completed; measured workload failed its60s
owner-cycle deadline. failure.json:418offered,363admitted,342completed,133fills,
63cancels,72replays,42cycles. Only PARTIAL_FILL_RISK_ORACLE recorded; remaining
scenarios and full600s were not completed. No W2/W3 invocation.

Trace identifies breach_reset→new→request line427 waiting for an API connection
while polling a submitted request result at cancellation. This is the observed
terminal wait, NOT evidence it spent the entire60s in pool checkout or proof of
a pool leak. Financial-fence and owner-lock timeouts persist in worker logs.
No WriterLeaseLost terminated this run. Source-clock tuning alone is insufficient
for integrated progress; do not claim the original lease problem universally fixed.

Artifacts: w1r20/{manifest.json,failure.json,inputs.jsonl,worker metrics/logs},
w1r20.log. All actors stopped; only owned PG/Redis remain. No code changes or
repeated safety tests in this continuation; prior affected206+focused21 remain
valid. Next investigation must distinguish API pool occupancy/holding time from
engine queue/result latency using this failed DB before changing pool sizes,
retry schedules or financial fences. No unapproved method/resource/threshold
change, Live order, commit or push. V21 remains Failed/Pending Full Validation.

### W1r20 persisted queue review (read-only continuation)

Selected scenario owner reseed requests transferred to native commands in
0.02–0.39s. Completed examples took2.47–10.63s from request to result; latest
request at06:13:15.633936 transferred at06:13:16.024362 but remained unclaimed
(claim_revision=0,attempts=0,no source-wait marker). Thus the terminal API pool
wait cannot explain the native command delay by itself. Across the stopped DB,
32of41commands lacking a result had never been claimed. No pool leak established.

Executed exact existing R8/R10 scanner SQL under ENGINE_SCAN in READ ONLY
transaction, limit20, after workers stopped. R8 did not include selected owner;
R10 admission lane included that owner at16, with20guarded substitutions.
Artifact w1r20-queue-review.json and runner/w1r20_queue_review.py. This is a
post-stop scheduling observation, not reconstruction of every live claim or
proof R10 satisfies60s/SLA. R10 remains an approved experiment, default off.

Important comparison limitation: prior150s source-clock diagnostics explicitly
used R10/R11 overrides, whereas W1r20 ran default R8. Only the paired150s runs
isolate the SQL tuning; do not attribute the R8W1 outcome to that tuning alone.
Next concrete candidate is the approved R10 lane with source-clock optimization,
keeping ordinary retry/fences/resources intact. No evidence supports increasing
pool size, changing retry delays, or weakening financial locks. No application
code, defaults, or test gates changed in this read-only investigation.

### W1r21 — approved R10 + source-clock SQL, 2026-10-28

Fresh0057 DB, unchanged100x20/10Hz/600s/60s and10Paper+1risk/4CPU2GiB.
External experiment runners r10_clock_workload.py/r10_clock_worker.py set R10true
and R11false for controller and Paper children. Application defaults remain off.
Manifest source c6b7e48c1330abd92d53d571bd6984cc8ab9f23d2aa53c0a0f9669db060d8a9c
matches W1r20. Prior safety evidence reused; no overlapping tests/diagnostics.

Baseline2000completed. Measured owner cycle failed60s during breach_reset/reseed
result polling, at transaction exit/commit cancellation.425completed/66cycles,
477offered/441admitted,162fills/80cancels/91replays; only partial-fill scenario
recorded. No full600s/SLA acceptance and no W2/W3. Cleanup emitted an unexpected
connection_lost future warning after cancellation; retain original log, do not
infer this caused the deadline. Actors stopped; only owned PG/Redis remain.

Selected-owner recent successful NEW timings0.262–0.713s for four entries, with
other earlier entries1.999s/3.459s. Latest request at06:37:16.693590 transferred
at06:37:16.955922, native command7d2e6a09-7c90-44a9-af1d-2e548844b1f7 still
unresolved, attempts3/claim_revision3. Unlike R8's unclaimed command, this one
was retried. No generic command-failed log for this ID. With R11disabled,
source_wait metadata is not populated: absence must NOT be interpreted as proof
of a non-source failure. Exact defer cause is not established by existing logs.
Do not widen pool, weaken source gates or change retry delays from this evidence.

Artifacts w1r21/{manifest.json,failure.json,inputs.jsonl,worker metrics},w1r21.log.
R10 improved some observed progress but did not qualify the candidate. Keep
Failed/Pending Full Validation and production defaults off. Next evidence gap
is per-command typed defer reason and attempt timestamps, not another blind full
workload run. No application code, Live order, commit or push in this checkpoint.

### Typed defer diagnostic after W1r21

Reused metadata-only source_error_worker instrumentation with explicit R10true,
R11false, fresh0057, same topology/budgets. r10-clock-trace failed baseline before
measured commands/scenarios (not a reproduction of W1r21's exact command).701
source errors:610read_inputs readiness and91BookState.require_ready. Persisted
book-commits.jsonl gives1085intervals,43over1s,max3.641188s; summary in
defer-summary.json. Actual stale source intervals exist, while exact individual
predicate and delay origin remain unresolved. No weakened freshness/retry gate.
Serial fixture book→price publication creates a dependency on price fence waits.
Prepared R12 independent-fixture-publication-amendment.md as Proposed; no code
implemented pending this new method's approval. Prior approvals remain valid.
All diagnostic actors stopped. No additional full workload, test rerun, Live
order, commit or push. Do not declare Completed or acceptance on this evidence.

### R12 approved implementation and bounded diagnosis

Owner approved R12 before implementation. Split Fixture.publish into supervised
serial book/price tasks using existing pool/process; startup waits for both.
Source failures preserve original exception and join the other task; close joins
both before disposing pool. Tests:19initial focused checks plus4final new source
checks (3overlap,20unique); real shared-fence blockage, independent book progress,
source failures, price gap/resumption, contiguous IDs and frame evidence. Ruff/
format passed2files; mypy src+changed harness/tests passed237sourcefiles. First
mypy invocation without src had import-untyped configuration errors; corrected
invocation passed. No production code/default/financial policy changes.

R12 diagnostic r12-source-trace (180s outer cap, R10on/R11off) failed baseline
before cap with ORDER_SAFETY_UNAVAILABLE. Book intervals1453,none>1s,max0.472444s;
1429native results. Rejected request/risk owner/evaluation all xmin2072667,
cursor2490/pendingtrue/SOURCE_UNAVAILABLE: bounded replay progress committed with
terminal intake refusal. This narrows the next issue; it does not establish
that every unavailable rejection is temporary or that full acceptance will pass.
R13 intake-replay-pending-amendment.md is Proposed, not implemented. No concurrent
workload/diagnostic and all actors stopped. Keep Failed/Pending Full Validation.

### R13 approved implementation — 2026-10-28

Owner approved before implementation. Bridge now returns RequestOutcome.DEFERRED
for the narrow successful pending-price-replay predicate, atomically committing
cursor/projection and existing claim deferral. Manual service counts deferred
without a second claim. Canonical checks include same wallet/active episode,
MANUAL/configured/unlatched/current setting revision, matching evaluation/source
cursor, active protocol and pinned catalog. Integrity exception fallback records
the captured watermark rather than the successful bounded cursor, so excluded.
Catalog validation reused in both existing transfer and new defer guard.
No new backoff, frame budget, financial authorization or source-freshness rule.

R13 new tests cover progress+exact-once transfer, rollback atomicity, integrity,
wrong use and breach. Isolated new tests passed5. Full affected risk/manual/API
set passed264 in134.904s, zero failures/errors/skips on fresh0057 DB
(tiewtrade_f18_r13_safety_final_20261028; r13-affected-final.{log,xml}).
Earlier failed runs preserved: initial timestamp/revision wallet assertions and
wrong-use fixture update under FORCE RLS corrected; failed tests had left global
scanner dispatch state, so added own-owner candidate filter and terminal cleanup
for only the tests' mutable dispatch, then reran affected set on fresh DB. These
fixture repairs do not modify financial history or runtime scanners. Initial
safety run was interrupted after diagnosis, not counted as a pass.

Ruff/format6changed files passed after import ordering fix; mypy src+changed
harness/tests passed238sourcefiles (r13-static-final.log); import contracts passed.
Final review retained breach/stop/unset/use/catalog refusal paths, existing
owner/fence order and CAS/backoff; no new Critical/High finding in this diff.
Unchanged-area3729baseline coverage/W4 facts remain historical applicable evidence,
not a blanket claim that final integrated acceptance is complete.

Fresh uninstrumented W1r22 started with R12/R13 and approved R10experiment,
R11off, native resources/rates/durations/thresholds. Application default flags
remain off. No concurrent test/diagnostic; do not claim acceptance until result.

### W1r22 and equivalent joined-status observation

W1r22 completed baseline and all THREE risk scenarios (partial-fill oracle,
breach/stop/reset/reseed20, correction/replay), but later60s selected-owner cycle
expired at final RESET polling.472completed/78cycles,514offered/489admitted,
183fills/89cancels/100replays. First measured frame07:27:47.135048UTC; final RESET
submitted07:28:45.940611UTC, leaving little of the original cycle deadline.
No full600s or W2/W3 pass claimed; retain w1r22 failure/log/manifest/metrics.

Inspection found duplicate workload status reads after request_view had already
joined the same owner/order projection. Reuse that existing authoritative view:
Fixture.request accepts expected_status and only returns when BOTH command
SUCCEEDED and observed order status match; new() uses this proof for ordinary
NEW instead of a separate wait_status transaction. Canonical command read stays;
partial-fill fixture still observes PARTIALLY_FILLED, its financial oracle and a
later FILLED after contra-trade activation. Cancel/replay paths unchanged. This
is equivalent observation/query reuse, not new execution/retry/publication logic
or a lowered status/deadline/SLA requirement. Commit-timestamp SLA remains intact.

23focused harness/SLA/supervision tests passed, including successful command
with wrong order state must keep waiting for ACCEPTED/PARTIALLY_FILLED/FILLED.
Ruff/format/type checks passed (237sourcefiles in final focused invocation).
Ready for Code Review announced; no new Critical/High finding in this read reuse.
Fresh uninstrumented W1r23 started with same R10on/R11off and R12/R13,
unchanged resources/rates/durations/gates; no concurrent test/diagnostic.

### W1r23 / monitor capacity investigation

W1r23 stillFailed60s during MARKET SELL FILLED observation:479completed/78cycles,
521offered/479admitted,184fills/93cancels/100replays; partial-fill and breach/reset
scenarios recorded, correction not completed. Selected SELL command itself was
SUCCEEDED within0.252s; do not infer from that receipt that FILLED was confirmed.
Offline SLA in w1r23/partial-risk-sla.json:47305acks,23175late,657unacknowledged,
max14.143885s,0clock errors. Partial/cancelled run remains failure evidence.
Monitor trace-block classification:2035publication fence,458owner-lock failures.

Reduced expected monitor DatabaseTimeout traceback logging to owner+typed code;
unexpected exceptions still keep traceback, immutable audit unchanged. Actual
blocked-owner/fairness and worker tests passed7 (monitor-timeout-logging-tests-r2).
Initial check selected a nonexistent test path and caught a missing import;
corrected before testing/runtime. No timeout/retry/claim behavior changed.

Cloned W1r23 DB for monitor-probe (no new commands offered; original queued
facts remain). Native10Paper+1risk/R12sources/same4CPU2GiB,5s warmup+20s measured.
58602acks/60000expected,11340late,1398unacknowledged,max4.316069s: monitor still
fails1s even without new intake. All actors stopped; no W2/W3. Existing artifacts
preserved. R14 monitor-captured-watermark-amendment.md prepared as Proposed,
not implemented; approval required for this new monitor scheduling method.

### R14 approved implementation / safety

Owner approved before implementation. Only standalone scheduler call now uses
existing captured replay without optional final publication drain. Initializer,
financial writers, reset/bridge/native matching and price writer fences unchanged.
New real scheduler test pauses after watermark capture, commits price update,
then verifies old cursor commit and next-round consumption. Existing parametrized
transient breach test and full financial-fence/API tail/R13 checks reused.
49affected tests passed, zero failures/errors/skips (r14-safety.{log,xml}); ruff/
format and mypy src+scheduler passed (r14-types.log). Ready for Code Review
announced; scope review found no new Critical/High issue. Bounded monitor
comparison running from a separate clone of identical stopped W1r23 source,
5s warmup+20s measured, same resources, no new offered commands. Diagnostic is
not full workload acceptance. No concurrent tests/diagnostics or Git mutations.

### R14 bounded comparison / remaining monitor throughput

R14 same-clone probe:58713acks,3735late,987unack,max2.181985s (compared with
11340late/max4.316069s prior), not acceptance. All100owners had some late inputs;
owner-sla.json contains per-owner counts. No native W1 rerun from this failed SLA.
Equivalent monitor setup SQL batching reuses owner-lock namespace and volatile
MATERIALIZED configuration before lock wait, same100ms/700ms; owner data read
remains a separate next statement.16scheduler/concurrency/worker tests+oneactual
configuration check passed; mypy/ruff passed. No scheduling/financial rule changed.

Same-clone monitor-probe-r14-sql still failed:63141acks/64200expected,5061late,
1059unack,max2.619307s; realized frame count differs, so no causal improvement
claimed. Owner ack intervals median1.0065s,p95 1.598985s,max3.168208s. Idle PG was
288.7MiB/3GiB, no memory-limit/OOM events; don't blame RAM without evidence.
No tests/diagnostics overlapped; actors stopped. R15 nonblocking-monitor-sweep-
amendment.md is Proposed, not implemented, for bounded100hint/four-slot monitor
try-lock scheduling. Existing financial writers and activation gates unchanged.

### R15 approved implementation / safety

Owner approved before implementation. Standalone monitor now tries the same
transaction-level owner lock; on False it returns deferred without read/mutation.
Its service asks for100hints, still semaphore4/pool4/20ms sleep and unchanged
replay/frame/boundary budgets. Blocking financial owner-lock wrappers retain
behavior via the same private helper; function-name SQL uses internal literals.
No timeout/retry/resource/financial-rule change.44scheduler/worker/concurrency/
monitor/matching/R13tests passed (r15-safety.{log,xml}); revised actual limit100
four-slot test rechecked and passed. Busy-owner test verifies cursor/book/pending
unchanged, next owner processed and original owner processed after release.
Mypy src+scheduler passed236sourcefiles, ruff/format passed. Ready for Code Review
announced; no new Critical/High finding in scope review. Same-clone monitor-probe-
r15 running next; no native workload rerun or acceptance claim from diagnostics.

### R15 failed experiment / rollback

Same-clone monitor-probe-r15:34122acks/35100expected,5850late,978unack,max3.289925s;
price publisher289ticks versus book493 over its setup+observation lifecycle.
No acceptance claim; diagnostic shows no benefit and potential contention harm.
Restored blocking monitor/default20 scheduling as promised, removed unused
try-lock helper, retained R14 captured replay and equivalent timeout SQL batching.
Rollback scheduler/worker tests passed7. Historical R15 approval/failed source
and artifacts remain; no silent replacement of failure evidence.

A separate metadata-only monitor-fence-classification run observed ZERO source-
preview failure→financial-fence events and zero source errors. Its actor entry
was verified and10source-error files exist empty. Thus that suspected path is
not established as a cause in this frozen sample; no R5 exception-path change
was made and no new amendment requested for it. The instrumented run still
failed monitor SLA (8511late/max4.564931s), diagnostic only. All actors stopped.
Next diagnostic profiles risk-process SQL durations (including failed statements),
main-thread stack locations and cgroup pressure, buffered metadata only, with
same budgets; no new workload, financial rule or resource change.

### Risk SQL profile and duplicate lock removal

monitor-risk-profile-r2 recorded46304 SQL metadata rows. No CPU throttling/OOM
was observed; SQL time was distributed across owner lock, frames, position
snapshot, boundaries, role checks and persistence. Instrumented SLA failed
12393late/max3.91024s; this is diagnostic, not acceptance or a causal benchmark.
The private _replay_monitor had exactly one caller, public replay_monitor, which
already holds the same owner lock through replay and its exception handler.
Removed only that duplicate acquisition; retained scheduler/public/financial
locks.30 monitor/concurrency/scheduler/matching-fence tests passed in
monitor-dedup-lock-tests.log; ruff and targeted mypy passed, git diff --check clean.

Stopped W1r23 has100 READY evaluations and zero replay_pending owners. No SLA
exemption or oracle relaxation was made. R16 monitor-read-snapshot-amendment.md
is Proposed, not implemented: batch owner-locked standalone reads while reusing
existing validators/replay. Further method changes await its specific approval.
R15 remains rolled back; no new W1/W2/W3 or Completed claim.

### R16 approved implementation / affected verification

Owner approved before code. Added monitor_snapshot transaction-local batch reader;
reused F14 SQL/decoder, fresh checksum/contiguity frame decoder and chronological
replay. Exact JSON numeric tokens decode to strings, never floating-point money.
Standalone owner lock precedes statement snapshot; final clock/writes/commit and
financial fenced callers unchanged. Snapshot owner and standalone-only guards
reject cross-owner/fenced misuse.49 safety tests passed (including7 replay cases
with both read paths and5 corruption/rollback/RLS cases);43 shared position/price/
worker tests passed. Artifacts r16-safety.xml and r16-shared-readers.xml.
Mypy236sourcefiles/ruff/import7/git diff --check passed. Ready for Code Review
announced; scope review found no new Critical/High issue. A sequential same-clone
20s monitor comparison follows; no acceptance or Completed claim.

R16 review retained the original F14 reader for the exceptional non-active
episode case (owner lock still held);2 episode tests rechecked/passed. Normal
initialized path replaces owner/state/boundary/frame/position reads with one
statement, preserving fresh final database clock and original writes. The first
probe launch was refused by the isolated-release DB name guard before any actor
started (monitor-probe-r16.log). Renamed only the owned clone to the required
release prefix and relaunched; guard unchanged, failure retained.

### R16 failed comparison / rollback

R16 probe:61272acknowledged/63900expected,7029late,2628unacknowledged,
max2.657488s; no SLA pass or clear throughput benefit. Owner acknowledgement
interval median1.0055s/p95 1.5303s versus R14-SQL1.0089s/1.5984s; overlapping
distributions are not proof of sufficient improvement. Read-only query plan
used indexed frame lookup; no full history scan established. Restored original
standalone read path and removed unused snapshot/decoder/test additions, keeping
the complete experimental source in monitor-probe-r16/source. Earlier independent
duplicate private-lock removal remains. Rollback checks34passed and mypy235
sourcefiles passed; an initial rollback import typo failed collection and was
fixed before final checks (r16-rollback-tests.log retained). No workload ran on
that intermediate source. R16 is inactive; no W1/W2/W3 acceptance or activation.

Next bounded metadata diagnostic measures PostgreSQL and parent CPU quota usage
in addition to prior risk-process SQL/pressure. Previous profile only ruled out
risk-process throttling, not database saturation. Same actors/resources; no
new trading method or concurrent validation.

### PostgreSQL/parent pressure and Paper CPU attribution

monitor-pressure completed same-budget observation; still failed7179late/
max2.417774s. PG CPU delta49.053s over42.879s (~1.14cores), zero added quota
throttling; parent CPU delta116.027s (~2.71cores of3),344throttled/429periods.
This identifies parent pressure, not sole causality for SLA. Risk SQL/stack
metadata retained; no resource limits changed. Docker reports8CPUs/~3.82GiB
VM RAM; host8logicalCPU/8GiB. No OOM claim from those capacity figures.

Sequential monitor-paper-cpu profiled only one Paper worker:7713constraint
decodes/3.464s cumulative,2808input decodes/1.514s cumulative (overlapping
profiled timings, not additive savings). All actors stopped. R17 execution-
input-decode-amendment.md prepared as Proposed to reuse deterministic immutable
public decoding while keeping every fresh readiness/provenance check. No R17
code implemented; no native W1/W2/W3 or final acceptance claimed.

### R17 approved implementation / safety and review

Owner approved before implementation. read_inputs retains fresh SQL state and
all existing readiness/lease/window/provenance/generation/digest checks; a bounded
256-entry helper caches deterministic public payload+capability decoding and
derived canonical digest. Existing codecs/Money/Quantity unchanged. No owner,
financial or readiness cache. SQL returns exact JSON text, with no extra query.
Tests:16 cache/storage passed,61 matching/checkpoint/process-recovery/financial-
fence/concurrency/R13 passed on fresh0057DB, plus R5 matching-recovery and one
immutability recheck passed (78unique affected cases). Initial missing-row fault
fixture used MARKET_DATA without DELETE permission; fixed to migrator fixture
only. Earlier wrong test path and shared-DB unrelated dispatch failure retained;
clean isolated rerun passed. Mypy src+cache test236files/ruff/format/diff passed.
Ready for Code Review announced; focused review found no new Critical/High issue.
Sequential same-clone20s comparison follows, with all10worker cache counters and
parent/PG CPU deltas. No W1/acceptance/Completed claim from these targeted checks.

### R17 standalone comparison / approved R15 combination

Same-clone R17 diagnostic:64092acks/65100expected,8757late,1008unacknowledged,
max3.03104s. Cache10workers:30041hits/3683misses (~89.1%), eachbounded256.
Paper observed transactions1674→2038, median102.42→81.45ms,p95245.02→191.22ms
versus monitor-pressure (similar lifecycle durations42.88/42.45s). Parent CPU
2.706→2.765cores and344throttled periods in both; higher throughput did not clear
CPU pressure or monitor SLA. No overall benefit/acceptance claim from cache hits.

R15 nonblocking100/four-slot method is re-evaluated with R17 because measured
Paper throughput/owner contention changed materially. Both methods already have
owner approval; no new scheduling method, resource or trading-rule change.
Preserve prior R15/R17 failed results separately. Same blocked-owner no-mutation,
fairness, four-slot and full financial-lock checks run before one sequential
combined comparison. If combined progress/SLA does not improve, restore the prior
blocking/default20 monitor and remove the experimental cache.

R15+R17 combined safety23passed; probe57729acks/59100expected,4836late,
1371unack,max2.359873s. Late fraction8.38% versus R17-alone13.66%; different
realized frames mean no capacity assurance. Still Failed. Because lock-acquisition
and native transaction timing now differ, re-evaluate approved R16 batched reads
with this composition once; all original standalone R16 failures remain.
Restored exact tested R16 source/decoders, retaining its exceptional old-episode
F14 fallback, while R15 controls only acquisition/sweep and R17 only public decode.
Combined scheduler/replay/corruption/rollback/RLS/financial-fence34passed; mypy236
sourcefiles passed. This is an approved-method combination, not a new financial
rule/resource increase; no native W1 invoked before sufficient evidence.

### Combined scheduling/read follow-up and transaction phases

R15try100+R16+R17:62595acks/64800expected,5883late,2205unack,max2.327808s;
Failed. Returned to original blocking100ms owner acquisition while retaining
approved100-hint/four-slot page, R16 reads and R17 decode.16scheduler/worker/
concurrency tests passed. That combination:58947acks/60000expected,3249late,
1053unack,max2.327136s (~5.51% late), still Failed. Source/input rates realized
differ across runs; no capacity pass. Of86owners without timeout, all had late
inputs (2673late,max1.5495s);14timeout owners had576late,max2.3271s. Thus owner
timeouts alone do not explain failure. Round median.5875s,max1.3293s; final
round tails ~30–60ms, no evidence for a new retry/pipeline method.

Metadata-only transaction-phase probe:checkout/begin median1.55ms,p959.87ms;
commit-or-rollback/release median2.05ms,p9512.10ms; body median17.42ms,p9548.65ms.
Costs distributed, not solely commit. Its own SLA failed3444late/max2.303819s.

Equivalent I/O consolidation: optional scoped-lock preparation in user_session
keeps actual _assert_role as a separate preceding statement, then combines
SET LOCAL owner/timeouts with the original blocking owner lock. Default callers
unchanged; monitor uses same namespace/100ms/700ms before any owner read.
R16 replay no longer reacquires a lock already held before its snapshot. No
transaction boundary, retry, financial arithmetic or readiness-rule change.
52 DB-session/isolation/scheduler/replay/corruption/fence tests passed; final
three session tests rechecked after typing-only assertion cleanup, mypy237files/
ruff passed. Full regression for shared helper remains pending until candidate
stabilizes; targeted evidence is not a replacement. Next comparison is sequential
and retains all actors/resources; no acceptance/Completed claim.

### Setup batching failed / rollback / R18 proposal

Setup-batched probe:42519acks/44100expected,4893late,1581unack,max5.575732s;
Failed. Reverted optional db.session lock setup and duplicate-public-lock removal,
removed unused test/helper additions after archiving experimental source.
db/session.py now has no diff from HEAD; default session code is unchanged.
Restored the prior blocking100ms/page100/R16/R17 candidate. Rollback scheduler/
worker8passed; mypy236sourcefiles/ruff/diff passed. Earlier setup tests/failures
remain, but that helper is inactive and its changes no longer require separate
final regression coverage. Full feature regression remains required/pending.

All actors stopped; only owned PG/Redis idle services remain. No W1/W2/W3 rerun
or acceptance claim. R18 monitor-concurrency-amendment.md prepared as Proposed,
not implemented: monitor4→8 transactions/pool, four extra DB connections, same
CPU/RAM/process counts and all financial/SLA gates. Existing role/transaction
proofs reused; request/stop pools stay isolated. Owner approval required only
for this new concurrency/pool ceiling, not prior methods or ordinary checks.

### R18 approved implementation / safety

Owner approved before implementation. MAX_MONITOR_CONCURRENCY=8 is shared by
main pool sizing/warming and scheduler argument; validated direct-call default4
remains. Monitor max_overflow0 and .1s pool timeout, page100, owner lock100ms,
statement700ms,20ms sleep, request1/stop2/scan3 pools and all CPU/RAM/process
counts unchanged. Runtime gains exactly four possible monitor DB connections.
32 affected scheduler/concurrency/stop/matching-fence/worker tests passed
(r18-safety.xml). Real8-slot barrier proves ninth waits; while8slots occupied,
separate request pool applies a queued SET and stop pool rejects queued opening
and completes target enrollment. Existing4-slot behavior and invalid bounds
checked. Mypy src+scheduler237files/ruff/diff passed. Ready for Code Review
announced; no new Critical/High safety finding in focused scope review.

One sequential same-clone R18 comparison follows. New isolated_workload_r18
runner reports actual monitor pool8 from the source constant; historical runner
files remain unchanged. Read-only .5s connection-count observer uses existing
controller migrator pool (one measurement connection, included in count), records
parent memory/CPU plus existing risk/PG metrics; observer failure invalidates run
and actors are joined. No W1 or acceptance/Completed claim from targeted tests.

### R18 comparison failed / runtime restored to four slots

R18 observed comparison (`monitor-probe-r18`):59229 acknowledgements of60300,
1638 late,1071 unacknowledged,max1.765373s. Failed; tail unacknowledged inputs
remain failures, not excluded.82 owners without timeout account for1332late
(max1.765373s);18 with timeout account for306late. Risk observed CPU~0.806CPU,
one throttled period, sampled memory peak79904768bytes. Parent peak643960832bytes,
no observed OOM events. `connections.json` database_connections peaked38; its
`clients` field is INVALID as an aggregate count because the migrator cannot
see other roles' backend_type. Do not cite that field as total connections.

A sequential native-entry comparison removed only optional SQL/stack profiling
hooks (`monitor-probe-r18-native`); ordinary commit telemetry remained. It also
failed:23457 acknowledgements/25200expected,6360late,1743unack,max4.988970s.
Book439/price274 publications over the complete actor lifecycle, not a measured
steady-state rate. Different realized rates and observer configurations prevent
attributing the regression solely to concurrency or instrumentation. Unfiltered
pg_stat_activity rows peaked44 (includes background processes; a conservative
connection bound), database rows39. Parent peak634163200bytes, no observed OOM.
No connection-capacity failure was established; no SLA headroom was established.

Restored runtime pool/warming/scheduler concurrency to4 via one
risk_limit_main.MONITOR_CONCURRENCY constant. The tested bounded scheduler API
still accepts explicit1..8, with default4; eight-slot capability is dormant in
normal runtime. R18 source for engine files and scheduler tests archived under
`r18-candidate-source` before rollback. No financial/retry/fence change.
Rollback scheduler/worker12passed (`r18-rollback.xml`); mypy237files passed;
ruff/diff checks passed after removing an extra import-block blank line.
Only idle owned PG/Redis remain. Native W1–W3 and final full regression/review
remain pending; do not rerun long acceptance against a known failing candidate.
R18 is an approved but unsuccessful experiment, not Completed/activation proof.

### Approved evidence-first closure plan — 2026-10-28

Owner explicitly authorized execution of the five-stage closure plan. Keep Paper
scope; V22/V23 Pending Dependency, no Git publishing or Live orders. Baseline
runtime4, R9/R10/R11 false. Earlier R18/phase diagnostics enabled R10 and cannot
qualify default runtime. Only owned idle PG/Redis active at start.

| Gate | Existing evidence | Reuse / gap |
|---|---|---|
| Safety | R17 78unique, R18 32, rollback12 | Reuse unchanged behavior; select new tests only after a fix |
| Static | mypy237, affected ruff/diff | Recheck changed code only; final full checks still required |
| Full backend | R11 3729 unique node IDs | Historical baseline; map later changes/current collection before reuse |
| UI/contracts/browser | M4/M5 evidence | Reuse if no relevant dependencies/contracts change |
| SLA/progress W1 | Failed | No acceptance; current flags differ from latest diagnostics |
| W2/W3 | Not run | Only after W1 and preflight pass |
| W4 | 0057 restore/grants/recovery passed | Schema unchanged; runtime recovery applicability needs final audit |
| Remote CI/manual | Pending as recorded | Cannot substitute local diagnostics |
| V22/V23 | Pending Dependency | Outside this closure scope |

Read-only correlation of existing monitor-transaction-phases first misses links
owner and commit wall time: about0.999–1.006s before transaction body, body30–36ms,
commit1–5ms, acknowledgement delta~0. Existing58scans/4418owner transactions show
some owners omitted per scan and owner acknowledgement intervals>1s. This points
to scheduling before transaction, but does not distinguish semaphore queue,
due_at exclusion, timeouts or an input arriving after captured watermark.
Existing SQL metadata has no transaction/owner correlation for those stages.

One bounded diagnostic is justified solely to close that gap: current default
flags/runtime4, existing100owner/2000order clone,5s warmup+20s observation;
record round/task/owner queue/acquire, original owner-lock call, snapshot captured
watermark/cursor, original SQL category durations and commit outcome. No new SQL,
no business behavior change, bounded buffer with overflow invalidation, no SQL
parameters/secrets. Retain ordinary commit oracle and source/cgroup observations.
This run is not acceptance or a speed comparison against R10-enabled evidence.

Correlated-default diagnostic completed with110063events/zero buffer overflow,
current4-slot/R10off/R11off composition.3513late/58746acks,1254unack,max2.307968s;
Failed. All3513 late PRICE acknowledgements mapped to their monitor transaction
with<=10ms association tolerance. Separate medians: before candidate queue622.8ms,
semaphore queue468.2ms, acquired-to-commit31.2ms. These are separate distributions,
not a fabricated representative summed transaction. Artifact:
`monitor-correlated-default/late-stage-attribution.json`.

Longest round13:84owners,1.280s elapsed,4.977s aggregate slot occupancy,only.418s
aggregate lock wait,zero owner timeout. Concurrent owners sometimes take~.28–.38s
with delays across pool checkout/SQL/pure snapshot decoding rather than one lock.
Risk CPU~.797CPU,zero cgroup throttle periods. Thus queueing is proven but changing
lock retry alone is not supported. No runtime fix or workload run started.

Read-only host snapshot shows3.4GiB swap in use and heavy historical compression;
that alone does NOT establish contemporaneous host-pressure causation. PG I/O
timing disabled; historical aggregate checkpoint totals cannot attribute stalls.
A second bounded diagnostic closes this newly identified gap only: identical
production-default runtime/resources plus passive GC timestamps/event-loop lag
and host vm_stat deltas. No runtime parameter changes, extra transactional SQL,
new offered commands, or overlapping workloads. Need distinguish interpreter/host
stalls from scheduler capacity before selecting a code or environment fix.

Correlated-runtime diagnostic:110395events,zero overflow,2472late/59436acks,
864unack,max2.039802s; Failed, not an improvement claim (extra instrumentation).
Host vm_stat40s deltas:31923swap-in/27560swap-out pages at16384bytes per page
(~498.8MiB/~430.6MiB),975102compressions/957054decompressions. Event-loop maxlag
209.0ms; two largest neighboring stalls coincide with1502swap-in/5424swap-out
pages in the same~.5s sample. GC spans explain only~5ms of the209ms stall and
none of the142.4ms neighboring stall; other70ms stalls overlap generation2GC.
GC total.653s,largest82.6ms. Evidence supports significant host/runtime stalls,
not a claim that host paging alone causes all misses. Do not change financial
logic or monitor scheduling to compensate before a controlled headroom comparison.

Only owned PG/Redis remain after cleanup. Host snapshot shows user VS Code/Docker
apps; no unrelated application was closed. Asked owner for host headroom (close
unused apps/windows) or an accessible separate test host, retaining all application
CPU/RAM/load/SLA limits. No new resource allocation or R19 method implemented.
While awaiting input, collect current backend node IDs and map prior coverage;
no full workload or further timed diagnostic started. Open acceptance gates remain
Failed/Pending, not Completed. Runtime evidence:
`monitor-correlated-runtime/runtime-attribution.json` and host/stage artifacts.

Current collection audit:3770 cases (same normal exclusion of venue contracts),
versus3729 prior;49 added node IDs,8 removed/renamed IDs (7monitor tests split
into read variants and scheduler barrier renamed/parameterized). Collection-only,
not a test pass. Initial double-quiet collection emitted file counts rather than
node IDs; corrected explicit addopts collection retained separately.
Historical passing XML found for48/49added IDs; this alone is not proof
of source applicability. Exact maps in closure-collection-delta.json and
closure-added-test-evidence.json. Final regression applicability audit remains
required after a stable candidate; no tests silently removed from coverage.

The one added case lacking prior passing XML was checked directly after all
actors stopped: test_expiry_during_sql_wait_rolls_back_writer_mutation
[renew-market_price_feed-True],1passed1.63s, closure-missing-case.xml/log.
This closes that evidence-discovery gap, not full final-source regression.
No production code changed during this closure investigation; only checkpoint/
plan records and external bounded diagnostic helpers/artifacts. Diff check clean.
Next dependent step: owner-provided host headroom or separate accessible host,
then same-resource/default-runtime comparison before selecting an application fix.
Do not run W1–W3 while the preflight remains known failing.

### Owner-ready headroom comparison / Docker VM reset

Owner reported ready after reclaiming host RAM. Same default4-slot/runtime/
instrumentation clone comparison still failed3294late/58989acks,1011unack,
max2.264544s. Host swap-in809.0MiB/swap-out393.6MiB over38.95s, looplag185.7ms;
zero observer overflow. Reclaiming apps did not achieve a low-paging comparison;
no code tuning or acceptance claim follows. `headroom-comparison.json` retains
before/after data. Diagnostic tails remain unacknowledged and are not discarded.

Only the two owned PG/Redis services were running. Their persistent volume IDs
were inspected, both gracefully stopped, Docker Desktop restarted, then the SAME
containers restarted. No volume/database deletion or resource-limit change.
F18 database names match exactly before/after restart (saved comparison files).
Host swap in use fell~3.47GiB→.99GiB; occupancy alone is not proof of less paging.
One same-config/instrumentation comparison now measures under reset VM state;
retains ordinary warmup and clone setup. Need measured paging/stall/SLA outcome
before deciding whether another application change is warranted.

VM-reset comparison completed:405late/58587acks,1413unack,max1.580120s. Swap-in
1.66MiB,swap-out0,maxlooplag49ms. This supports environment cleanup as material,
not a sole-cause or acceptance claim. All405late inputs mapped to monitor tasks;
18 have an intervening failed attempt. Separate medians:beforequeue687.1ms,
queue365.7ms,active24.8ms. The worst non-failed owner skipped a scan at the200ms
eligibility boundary, then ran LAST in the next UUID-rotated page and waited
779.6ms before17.6ms active work. Exact trace and bounded fix proposal are in
monitor-page-order-amendment.md (R19 Proposed only).

Re-evaluated previously approved R18 after the host condition changed, preserving
all instrumentation/default flags except concurrency4→8. Scheduler/worker12passed,
ruff and module mypy passed. Low-paging8-slot run still failed1209late/59229acks,
771unack,max2.162473s;swap-in.375MiB/swap-out0,looplag83.5ms. Active-stage median
65.9ms vs24.8ms in4-slot late cohort (different cohorts; not paired speed proof).
Restore4 per R18 terms; rollback12passed4.69s,ruff/diff passed. No further tuning
or W1 invocation. Only idle owned PG/Redis remain. R18 source capability stays
available, but normal runtime4. Historical failures remain unchanged.

R19 prepared as concrete approval-only proposal: keep original eligible UUID page
and next_owner cursor, order its execution by oldest due_at(NULL first,stable
ties). No new query/schema, eligibility/200ms/retry/sleep/budget/resource change.
This addresses observed extra within-page delay while retaining page fairness;
success still requires measured proof and all closure gates. No R19 code written.

R19 owner approved before implementation. Scanner adds only o.due_at metadata;
Python stable sorted execution list retains original candidate list/next_owner.
37scheduler/concurrency/stop/fence/worker cases passed24.90s, including5new
priority/NULL/tie/eligibility/hint/page-continuation scenarios. Mypy237files and
ruff passed. Code review of changed selection/gather/cursor confirms original
page boundaries and financial guards retained. No feature-completion claim.
One same-instrumentation/default4-slot low-paging comparison follows; this is the
approved R19 decision gate, not W1 acceptance. Prior source and failures retained.

R19 first comparison failed918late/59103acks,897unack,max1.339450s. Late cohorts
cluster at rounds43/44 and66/67; round66 has134ms loop stall without a matching
GC pause and contemporaneous host compression activity. A same-first-after-VM-
restart comparison (explicit environment-equivalence check, not a blind retry)
also failed879late/59067acks,933unack,max1.940027s,loopmax69ms,swap-in14.31MiB and
zero swap-out. Exact owner/task association for all879 late inputs;54had a failed
attempt during the delay. Eligibility still excludes owners with pending newly
committed prices until200ms due; ordering alone did not establish sufficient
benefit. R19 source/test archive saved, original scanner/execution order restored.
Rollback scheduler/worker12passed; ruff/mypy237/diff passed. Runtime remains4,
no R19 selection or ordering code active. R19 historical37safety passes/failures
remain, but reverted tests do not count as active candidate coverage.

R20 pending-price-monitor-amendment.md prepared Proposed only. Concrete narrow
change: add committed-watermark-ahead eligibility, preserve due/NULL/hint paths,
original UUID page/cursor and all budgets/resources;0058 adds only cursor and
watermark SELECT column grants to scanner (read-only privilege check confirmed
both currently absent). No R20 code/migration written. New approval required for
eligibility and grants, not for previous safety/review steps. W1–W3 remain unrun;
final W4 would need0058grant/recovery evidence if R20 is approved and retained.

R20 explicitly approved before implementation.0058 adds only the two approved
column grants; scanner adds one scalar-subquery OR predicate. No new statement,
R19ordering, financial algorithm, retry, worker/pool/CPU/RAM or publicAPI change.
Migration before runtime; admission remains gated.69affected tests passed35.22s:
committed/uncommitted hint, original due/NULL/explicit hint, missing frame fail-
closed, narrow grants+fullschema snapshot downgrade/upgrade, scheduler/concurrency/
stop/matching-fence/replay/snapshot/prices/worker. Mypy237/ruff/format/diff passed.
Focused source review confirms scalar NULL leaves original predicates intact and
hint never substitutes authoritative replay. Next is one fresh-VM same-clone
comparison after upgrading cloned DB0057→0058. No W1 or acceptance claim yet.

R20 correlated fresh-VM comparison:105late/59256acks,744unack,max1.218807s;
Failed, but lower than the comparable original4-slot405late/max1.580120s.
All105 late samples mapped;9had a preceding failed attempt. Separate late-cohort
medians:beforequeue335.2ms,queue665.7ms,active31.7ms; cohorts differ, so do not
claim a paired distribution improvement. Host swap-in.4375MiB/swap-out0,loopmax91ms,
no observer overflow. R20 provisionally retained because it improves the identified
eligibility delay; not acceptance, no activation. Remaining105late forbid W1.

Next check removes ONLY optional SQL/stage/GC/heartbeat observer from risk process,
retaining normal commit oracle, default runtime/resources/flags and host sampling.
Use existing full-profile authoritative final drain so measured tail inputs remain
counted and late acknowledgements still fail. No test threshold or transaction
changed. This checks instrumented-vs-native feasibility rather than blindly
repeating the same run; no speedup claim across different observer configurations.
Same fresh-VM precondition, cloned0057fixture upgraded0058 before service start.

Native R20+authoritative drain:60300/60300acknowledged,zero unack,30late,
max1.494068s; Failed. Swap-in.1875MiB/zero swap-out. Optional trace removal is
not a speed claim; native oracle still fails and W1 is blocked. Native worst
owner62e599b0 has no timeout log and cursor4411@13:18:56.616380Z then4459@
13:18:58.199770Z. Existing correlated R20 gives the precise remaining race for
owner22d66971/input4634: round51captures4633@t=-.071, commits-.066; absentround52;
round53queues+.494 at rank98/99, starts+1.200,commits+1.219. R20 cannot see a price
publication that happens after the scan snapshot; original UUID execution can
then add another full queue delay after that missed scan.

Re-enable exactly the previously approved R19 within-page stable due ordering
under R20 eligibility (both owner-approved). Different eligible-page condition
now addresses the R19-alone experiment's unresolved eligibility gap. No new
priority key, retry, early authority, grant, resource, or repeated approval step.
Restore archived R19 tests unchanged, preserving their failed standalone history.
Run composed safety and one same-native-oracle/drain comparison after the same
VM reset. If composed order does not improve the identified delay, restore R20
original execution order. No new experimental method is authorized by this note.

R19+R20 composed safety74passed38.79s;ruff/mypy238passed. Native20s comparison
with final authoritative drain PASSED its SLA oracle:60300/60300acks,zero late,
zero unack,max.997677s. This is a bounded preflight only (acceptance_result=false),
near the threshold and not a full-scale release claim. Native flags R9/R10/R11off,
monitor4, actual0058schema and same resource bounds. Do not repeat this passed
check without a change or identified concern.

Next authorized gate: existing selected-owner full cycle within60s, under100owners/
2000baselineorders and10Paper+1risk. Reuse r11_full_cycle helper against sameW1r23
clone with dynamic actual pool manifest. Source trade-id continuity uses measured
prior_max_trade_id2086 (the older source fixture's3456minimum is inapplicable);
require positive prior ID and offset every new trade by that exact value. Financial
postconditions unchanged: four added execution links, zero BTC held and exact
cash delta-1.197901USDT. This is not W1 acceptance; no new trading rule or budget.

Full-cycle W1r23 clone failed SETUP (no untouched baseline owner); no measured
cycle occurred. Reused original w1-v2-r9 frozen dataset instead (two eligible
untouched owners, prior trade_id3456), clone upgraded0058. Full-cycle-r2 completed
in48.5705s; exact balance delta-1.197901, zero held BTC, four execution links and
all five commands PASSED. SLA FAILED:144907/144907acked,24867late,max2.705409s,
zero unacknowledged/clock errors. Do not promote idle preflight to W1 readiness.
Host66.55s sample shows24swap-in pages/zero swap-out but771912compressions and
548403decompressions; low disk paging alone does not establish host headroom.
Native stream does not split queue/lock/transaction timing. Next bounded diagnostic
reuses exact same clone source/config/cycle and existing bounded correlated runtime
observer to fill that evidence gap; no code tuning, no W1, no performance claim
across observer configurations. Setup failure and financial pass remain preserved.

Cycle-trace aborted before measured commands:ExecutionInputGapError. Trace records
a wall-minus-monotonic backward step84.600ms at1793195776.48, matching rejected
book publication after received_at13:56:16.525091Z. Native ordering guard correctly
fails closed; no bypass. Observer37077events/zerooverflow. This is an identified
post-VM-restart clock issue, not evidence supporting code tuning. Allow clock
synchronization, check wall/monotonic stability, then repeat only the incomplete
trace on another original-source clone; preserve this failed setup.

Clock10s check443samples: wall-minus-monotonic step range−81.8/+76.2microseconds.
Cycle-trace2 then completed46.8172s with exact financial assertions PASSED, but
SLA FAILED23976/140107late,zero unack,max2.647939s.132403events/zerooverflow.
58monitor rounds median1.031169s;33>1s,max1.696489s. Exact ownerd4b86523/input11900
round45:prequeue260.722ms+queue845.706ms+active43.527ms=1.149954s,no prior failure.
23943late inputs associated;33outside monitor10ms tolerance remain unattributed
(not removed from SLA). Risk CPU unthrottled; parent499throttled periods,host
compression remains material. No claimed speedup from native-vs-traced results.
R21 composed-monitor-capacity-amendment.md prepared Proposed only; runtime stays4.
It asks to reuse existing8-slot capability with R19+R20, because newer R20 fixed4.
No blind rerun, no W1, no production mutation in this diagnostic follow-up. Current
financial/deadline evidence passes; input SLA remains blocking. Only owned idle
PG/Redis retained. Next gate requires decision on this concrete method amendment.

Owner explicitly approved R21. Only MONITOR_CONCURRENCY4→8 changed, reusing
existing pool/warm-up/round wiring and four additional connections. No new
financial/scheduling implementation. Running scheduler4/8-slot barriers, page
fairness/publication and request-worker regression before the one comparison.

R21 safety17passed6.395s; ruff/format/mypy entrypoint passed. One correlated trial
completed50.3986s with financial oracle PASSED; SLA FAILED11322/150607late,zero
unack,max2.492380s.174969events/zerooverflow;11319late matched,3unattributed.
77rounds median.797409s,14>1s,max1.546831s. Matched-late active median81.85ms
versus44.96ms at4; these are distinct cohorts, not paired speedup measurements.
Host4225swap-in/zero swap-out pages,886512compressions/932986decompressions;
headroom differs from baseline, so no isolated causal performance claim. Risk
CPU throttle oneperiod5.491ms,loopmax180.4ms. Eight slots reduced observed round
time but did not establish SLA feasibility; restore4 rather than retain increased
connections on incomplete evidence. No W1 invocation. No further slot tuning.
Remaining gap: the replay/write span is broad and current stage timing cannot
attribute its CPU cost to a particular pure function. Existing trace alone does
not justify changing financial calculations or adding another cache.

R21 rollback17passed; only source difference from pretrial runtime is explanatory
comment. No further capacity trial. One cProfile run filled the remaining pure
CPU attribution gap on restored4, original clone source,0058, identical safety
guards. It completed the financial cycle51.7088s, but profiled SLA FAILED badly
(152796late/153907,max66.239262s); never use this as native performance evidence.
Synchronous evaluate_risk196705calls/50.261profile seconds out of77.165overall;
Money context4556052calls. Async cumulative timings overlap and are not input
latency. Artifacts risk-cpu.prof/risk-cpu-summary.txt retained. This supports a
new local-valuation reuse proposal, not a change to Money arithmetic or resources.
R22 replay-local-valuation-amendment.md is Proposed only; no valuation changes
implemented. Await method approval before financial reuse. Runtime4/R19/R20/0058;
W1–W3,0058W4,final regression/review remain pending; V22/V23 dependency unchanged.

Owner approved R22 before implementation. Core now exposes a lazy ≤100-frame
iterator with a call-local loss memo bound to its immutable book; public single
evaluation delegates to shared unchanged valuation arithmetic. Marks are freshly
resolved per frame; decisions/timestamps/latch are never cached. Infra retains
per-frame transition persistence, including breach before later malformed input.
Core/parity70passed, covering changing freshness with identical amounts, scope/
book/reset/closed/empty/mixed positions, transient latch, overflow, generated
sequences and existing hand oracles. Full risk infra/API affected suite follows
because the shared evaluator is used by admission, financial fences and recovery.
Deterministic comparison uses extracted original function as an independent
baseline and identical100books×100frames/profiler; no acceptance shortcut.

R22 affected integration247cases:226passed on reused safetyDB;21scanner cases
failed because >20old pending owner queues occupied the bounded scanner page.
Preserved failure; exact21nodes passed on newly bootstrapped/migrated0058 DB
without selector, limit or test changes. Core70passed; mypy found one test-only
Money <= annotation mismatch, replaced by equivalent existing < pattern and
rechecked8affected cases. Mypy237/ruff/format and7import contracts passed.
Independent extracted pre-R22 evaluate_risk versus batch:100books×100frames,10000
exact equal evaluations. Same-profiler times1.40444s→.18178s; Money context calls
218200→16500. Deterministic repeated-mark case only, not production capacity or
SLA evidence. Native full cycle on original frozen donor clone is next, with
profiler/stage hooks removed and unchanged financial/deadline/all-input oracle.

R22 native cycle financial/deadline PASSED48.2843s, SLA FAILED6822/142807late,
zero unack,max2.224694s. All100owners have misses; cohorts align at10s intervals
with host compression bursts (e.g57585pages in one interval ending14:27:57.158Z).
Host totals1164490compressions/1156911decompressions,1167swap-in/1304swap-out pages.
Correlation alone does not establish causality. This run followed integration and
did not reproduce baseline first-after-VM-restart conditions. One explicit
environment-equivalence check follows on unchanged R22 source/native oracle: same
owned VM restart/caps, wait for clock synchronization before publication. No code
change, no discard of this failure, no repeated parameter tuning.

R22 environment-equivalence check completed after owned VM restart and30s clock
check (1317samples, no material backwards step). Native financial/deadline oracle
PASSED42.2647s; SLA FAILED3933/126007late,max1.700444s,zero unacknowledged.
Host59.94s:24swap-in/zero swap-out pages,418097compressions/269247decompressions,
peak32225compressed pages per sampling interval. Disk paging reduction alone
did not qualify candidate; memory compression remains and is not proven to be
the sole cause. No additional runtime tuning or retry is justified by this run.
R22 retained with proven deterministic parity/work reduction; monitor4 and all
financial rules/caps unchanged. Only idle owned PG/Redis remain; no running test.
Next evidence needed: a controlled environment with sustained host headroom to
separate host stalls from remaining implementation latency. Ask owner for another
test machine or further host cleanup; keep containerCPU/RAM/load/SLA fixed.
No new financial-method proposal based only on these correlated host metrics.
V21 Failed/Pending Full Validation; no W1/W2/W3 or completion/activation claim.

### Owner-approved Paper two-second gate — 2026-10-28

Owner chose2s if testing proves it, replacing the unapproved3s proposal. Updated
NC-F18-05/plan/validation: Paper every ready input<=2s inclusive, target1s; Live1s
and all financial/freshness/fence/stop/F15latency/resource/load/duration gates remain
unchanged. Acceptance still requires final full evidence, not the latest1.700444s
preflight alone. Prior2.224694s failure demonstrates that a pass is not guaranteed.
Oracle now reports hard_limit_seconds2,target_seconds1,target_miss_count>1s and
miss_count>2s separately, with histogram through2000ms plus overflow bucket.
Missing/pending/rollback evidence still fails.21affected oracle/profile checks
passed; ruff/format passed; mypy238passed after correcting invocation to include
src (initial tests-only invocation produced import-untyped errors; no suppressions
or production typing changes). No workload rerun or historical result overwritten.
Current V21 remains Failed/Pending Full Validation. Only acceptance criteria and
test oracle/docs changed in this step; production financial runtime unchanged.

### Owner-approved replacement: Paper three-second gate — 2026-10-28

Owner explicitly instructed “แก้เป็น 3 วินาที”. Supersedes the two-second gate
for Paper background monitor only; target1s,Live1s,financial/freshness/stop checks,
F15commandlatency and all workload/resource/duration gates remain unchanged.
Requirements/plan/validation and review status updated before oracle change.
Oracle hard misses now>3s, target misses>1s; histogram through3000ms plus overflow.
14affected SLA tests passed, including1/2/3second boundaries, missing/pending and
rollback acknowledgement; previous unrelated profile tests reused unchanged.
Ruff/format/mypy238 and diff check passed. No production runtime changes, workload
reruns or historical results rewritten. V21 remains Failed/Pending Full Validation;
changing the gate does not certify W1–W4 or F18 completion.

### Resume acceptance under approved Paper3s gate

Owner instructedเริ่มทำ. Read current checkpoint; only owned idlePG/Redis running.
Re-assessed preserved native R22 preflight inputs with current oracle in separate
paper3s-preflight-reassessment.json:142807/142807 and126007/126007,zero>3s/
unack/clock-errors; >1s counts6822/3933 still reported. Historical Failed files
untouched; reassessment is not full acceptance. Both cover100owners including
99without new selected-owner commands; full cycle/financial assertions already
passed. Since those runs only docs/oracle/tests changed, runtime evidence remains
applicable; no redundant timed preflight. Ready for Code Review announced.
Focused review of R22 diff and callers confirms local immutable-book memo,
per-frame readiness/validation and lazy persistence/latch revision parity; no
new Critical/High finding identified. Existing approved review/refactor/closure
authorization used; no new approval or unrelated refactor. Freeze this candidate
and run native W1 600s on clean0058,4monitor slots,R9/R10/R11off,existing budgets.
Stop on conclusive failure, do not startW2 untilW1passes. All other gates pending.

### W1 Paper3s failure and scoped R10 reuse

Native W1 on clean0058 stopped at original60s owner-cycle deadline during
selected-owner reseed;17/20replacement orders accepted after completed stop/reset.
489completed,83cycles; full600s not reached. No W2 started. All workers exited;
only owned PG/Redis remain. Preserve w1-paper3s-r22/failure.json and log.
Joined immutable request/result/order timestamps for sequence22..38 show intake
0.080..0.389s and bridge-result to accepted1.636..2.841s. These are per-request
intervals, not overlapping transaction totals; they do not isolate queue from
execution. Existing R10 trace isolates matching queue and previous R10 experiment
passed this reseed stage, failing later progress before R12/R13/R22 changes.
Reuse already approved R10 alternation without changing selector or budgets:
ALTERNATE_ADMISSION_PRIORITY=True in production composition, imported by harness;
R9 standalone preference and R11 source retry stayFalse, monitor4. This is a
retest of an authorized method after material intervening changes, not repeated
unchanged W1 or a new queue algorithm. No financial/API/schema/deadline change.
Existing R10/R9 safety and runtime composition tests run on clean0058 to cover
fairness, guards, cancellation/reduction, claims and production/harness agreement.
Then one short concurrent100owner/2000order command-cycle check is required;
prior selected-owner-only preflight did not establish progress under full commands.
All W1-W3 runtime evidence requires new qualification for this composition.

R10 reuse safety51passed,ruff/format/mypy236passed. Short concurrent diagnostic
r10-r22-progress completed500commands/100cycles and all3financial scenarios;
100owner balance/reservation/position oracles passed. No deadline timeout.
60.0014s measured; NOT acceptance (wrapper explicitly marks diagnostic_only).
Risk91204/91204acknowledged,zero clockerrors,12hard misses across4owners sharing
3priceframes3768..3770,max3.115111s; target misses867. Transactionp95.284737s
fails250ms, p99.435045s. Book599/600count is also Failed. No fullW1/W2 started.
Global cancel oracle incorrectly counted checkpoint events101 versus120orders:
immutable terminal_orders contains120distinctCANCELEDorderIDs, matching allowner
projections. F18 bulk stop deliberately persists multiple cancellations in one
checkpoint; fix oracle to countdistinct immutable terminal order identities,
not relax expected120 or rely only on mutable projections. New realDB test
covers2canceledorders in3repeated checkpoints (old oracle incorrectly counts3).
10profiletests passed,ruff/format/mypy238passed. Historical Failed result untouched.
No money/runtime change from oracle fix. R10 retained because it resolves the
specific progress hypothesis without observed financial failures; not qualified.
Remaining performance needs correlation: raw ack has owner/input/commit only,
no queue/lock stages. Reuse bounded400000event observer on one fresh0058 short
concurrent run r10-r22-trace (sameflags/budgets/load; extra timestamp overhead,
noSQL/secrets/parameters). It is diagnostic, not a speed comparison or acceptance.
No overlapping workload/tests. FullW1 blocked until targeted gates pass.

Monitor trace completed100cycles,globalfinancialoracle nowpasses120cancels;
87604/87604riskacks,max2.058944s,zero>3s/unack/clockerrors,p95transaction.298494s
stillfails. Observer retained400000events(dropped432906setup events); retained
window15:41:02..15:42:59 fully covers measured15:41:57..15:42:58. No claim of
complete setup trace. Measured heartbeatmax.11458s,monitorCPUthrottle11.344ms
whole run. This does not explain Paperprocessing p95; collect worker stage gap.
Paper timing run completed500commands/100cycles;2928processingtransactions,
218>250ms. Slow cohort median317.31ms,totalSQL219.93ms/116calls,fence90.33ms,
medianfence-share28.6%,connect.82ms,close2.72ms. No additive parallel latency claim.
Finaldrain failed60s: all100owners cursor4094,notpending,READY; actualwatermark4094
but inputs/last_frame4091. Normal publisher supervisor canceled price recorder
when book loop finished first, after price commit before evidence read. Fixed
normal-stop branch to await both tasks; fault/cancel cleanup preserved.5publication
checks pass including deterministic committed-tail race;ruff/format/mypy240pass.
No workload retry solely for this oracle fix. R23proposal prepared to reuse bounded
final-tail replay for configuredBUY policy preparation; financialmutation remains
fenced. Needs Owner Approval because existing plan restricts this method to
monitor. No R23implementation. CurrentR10+R22 runtime remains unqualified.
Ready for Code Review notified; focused diff review ofR10composition and both
harness fixes found no newCritical/High within those edits.66affectedtests passed
(51selector/composition,10profile,5publication); earlier runtime safety reused.
All workload processes stopped. W1/W2/W3/W4,finalregression/remoteCI/manual remain
pending; V22/V23dependency unchanged. Do not callPaperpassed orF18Completed.

### R23 implementation — owner approved2026-10-28

Approval recorded before code. ConfiguredENGINE BUY resolve and fenced
execution_context now use existing replay_monitor(False,final=True); preview
remains(False,final=False),unconfiguredfallback unchanged. Owner/catalog locks,
financial_boundary protocol and core financial arithmetic unchanged. Finaltail
consumes shared100framebudget and fence remains throughcommit. No monitor/API/
SELL/cancel/defaultreplay change.65targetedcases passed: initial63had2newstale
tests incorrectly using book1s instead of riskMAX_PRICE_AGE10s; corrected tests
to actualconstant,2passed,initialfailurepreserved.2additionalgenerationbarriers
passed. New14cases cover2policycallers×benign/breach-recovery/disconnect/generation/
disable/stale/overflow and publisherblockedthroughcommit. Existingmatching/
financialboundary/concurrency/monitor/execution/prices tests reused in63set.
Ruffpassed,mypy237passed. Intake/retry/APIcallerchecks follow sequentially.
Then same boundedPaperstage observer/controlprofile compares initialR23 effect;
no fullworkload until scopedgates pass. No additionalresource/flag/deadlinechange.

R23callers8passed,total73unique safety/callercases;format/mypy237passed. One
controlledPaperstage run on fresh0058 completed500commands/100cycles/allfinancial
invariants,613bookinputs/600required.76204/76204riskacks,3>3s,max3.293155s,zero
unack/clockerrors;profilep95.337683s/p99.524212s stillfails. Sameobserver cohort
comparison (r23-timing/comparison.json):2928→2852processingtransactions,218→247
>250ms; slowmediantotal317.31→354.37ms,fence90.33→89.93ms; processingp95
289.71→334.11ms. Instrumented single-run observations,notnativeacceptance or
universalregression. No claimedimprovement: historicalreplayrelocation did not
materially reduce fencewait. Stoprule applied;restore originalfullfinancialfence
inpolicy and originalmonitorcomment. Archive experimentalcode/tests under
r23-timing/source before removing onlythe newlycreatedexperimentaltestfile.
No other source reverted; R10+R22 and harnessfixes retained. NoW1/fullregression
started on unsupportedR23. Rollbackaffectedmatching/boundary/intakechecks follow
sequentially; remainderofpreviouscandidateevidence reused unchanged. Nextstep
requiresfencehold-work attribution fromexistingtrace,notanotherblindtrial.

R23rollback16checks passed;ruff/format/mypy236/diffcheckpassed. All workload
containers exited;onlyownedPG/Redis remain. R23closedasFailed/rolledback,not
Paperqualification. No commit/push/merge,Liveorder ornewresources.

### Bounded evidence-only review — 2026-10-28 16:23–16:29 UTC

Owner authorized at most30minutes of existing-evidence analysis, no code or new
workload/diagnostic. Completed in about6minutes. Only this checkpoint edited;
read-only analysis of saved JSON/JSONL, current source, and archived scratch DB
facts. No tests, migrations, workload, diagnostic collection or resource change.

**Decision: evidence insufficient to select a safe performance fix.** Do not
increase thresholds or implement another optimization from these aggregates.

#### Candidate and comparability

Current source-tree digest (same742-file manifest algorithm):
`c389a24fc1d72101426a0eea3ca7c6e9ce36de1a772270f7a9f3119a53e8e320`.
Current code confirms R10on,R9/R11off,monitor4 and original R22 valuation path.
R23 archived policy differs only by its two approved opt-ins; current policy
restores original fenced replay, monitor differs from archive only in comment.

| Evidence | Source digest prefix | Observer / configuration | Valid use |
|---|---|---|---|
| r10-r22-progress | ceb52dc21e7c | native short profile | Original12misses and progress; no stage attribution |
| r10-r22-trace | 7a21485c7b8c | monitor-stage observer | Monitor timeline for its own run only; zero3s misses |
| r10-r22-timing | 7a21485c7b8c | Paper observer | Per-processing-transaction aggregates; final drain failed |
| r23-timing | 81fbb6401420 | Same Paper observer | R23 per-transaction comparison;3misses; not current runtime |

All four manifests retain60s,rate10,100owners×20orders,10Paper,monitor4,
20hints/1claim and aggregate4CPU/2GiB. The two Paper runs record identical observer
hashes: worker70da36d018d865e5541512c6fe46a2c68f9c4ad9c0f517b562a22ae5eb5afbb4,
workload49d95d0dadc7757fa41f6c2e45bd9e021cc188614aec9e17494d304ac2fd55aa.
Source hashes also cover tests/harness: the normal-stop recorder fix intervened,
and R23 adds/removes experimental tests. Thus these are not identical full source
snapshots; do not use source hash differences alone as runtime causality. Earlier
full per-file source snapshots are not available in these manifests. Fresh owner
identities, measured input counts and host conditions differ; one run does not
establish a universal speed regression. No native/monitor-observed/Paper-observed
results are treated as interchangeable acceptance evidence.

#### Symptom → evidence → conclusion → gap

| Symptom | Existing evidence | Supported conclusion | Missing evidence |
|---|---|---|---|
| processingp95>250ms | BeforeR23:218/2928processing transactions>250ms;R23:247/2852. After subtracting each transaction's entire fence-SQL duration,113/218 and147/247 still exceed250ms.40 and43slow transactions have no fence SQL at all; all of these lack an error_type. | Fence-call duration alone cannot account for slow processing. Subtraction is an arithmetic attribution bound, not a predicted optimization or revised SLA. | Ordered per-call timing and callsite, phase before/after first fence, CPU versus DB/network/scheduling attribution. |
| Claimed90ms fence wait | Slow-cohort fence-SQL medians90.33/89.93ms. Observer accumulates multiple calls by SQL template and stores only total seconds/count. | Correct earlier terminology: these are client-observed function-call durations, NOT measured advisory-lock wait. Cannot reconstruct first acquisition or held-through-commit duration from them. | First successful fence acquisition timestamp, separate repeated acquisitions, transaction outcome and publisher/other-holder intervals in the same run. |
| Repeated checks in slow transactions | Median counts:12advisory-lock calls,8clock reads,5episode validations,4execution-source reads;SQL parameters intentionally absent. | Repeated SQL text is not proof of redundant work. lock_episode protects owner/active episode; require_claim rechecks token/lease; per-input clock/source/control checks preserve freshness and readiness. financial_boundary checks exact before/after state; risk context invalidates after fill. Reuse already exists in R5context/R17decode/R22valuation. | Callsite and safe identity category are needed to distinguish same-resource checks from different locks/inputs/revisions. No approved removal/cache follows from counts alone. |
| R23risk3.293155s | Owner74506953-7e07-4147-9737-863e180f106c,frames3957–3959 ready16:15:23.271194,ack16:15:26.564349UTC. Same-owner Paper transaction ended23.164254;next recorded matching transaction starts27.007586. | No recorded matching-process interval overlaps this miss window. This does NOT exclude API,intake,correction,reset,monitor or failed claim transactions. | Those writer/monitor timelines are absent from this Paper trace. |
| Possible correction/reset overlap | Same owner's immutable boundaries514/515CORRECTION recorded24.882054/25.677421 and committed together25.710469;RESET522recorded26.536837,committed26.560041;monitorack follows4.308ms later. | Code and DB establish correction held its transaction owner/publication locks for AT LEAST828.415ms from first boundary record through commit. This is a lower bound, not total correction time or proof of the entire3.293s delay. Correction/replay and reset are real unmeasured paths, not speculative host blame. | Correction first owner/fence acquisition, both replay stages, reset start/acquisition, monitor due/queue/acquisition, publisher exclusive acquisition. |
| Original native12misses | Four other owners shareframes3768–3770 at15:33:23.942067..27.057178UTC. Their next persistedFILL/RESETboundaries occur after the miss window. Native run has no correlated stage trace. | R23selected-owner correction overlap cannot explain these separate native misses by analogy. Absence of committed markers does not exclude waiting/rolled-back/read-only owner transactions. | Same-run all-writer/monitor correlation; do not splice monitor-only trace from another run into this gap. |

The slowest R23 matching transaction is a DIFFERENT owner678e6a2a…/command
f92c3725… at16:15:24.350989..25.950300,1.599308s total with one1.366527s
fence SQL call. It overlaps the selected owner's correction interval. Shared
locks are compatible, so overlap alone cannot identify a blocker; a queued or
held EXCLUSIVE publisher is a hypothesis requiring its actual timeline. No
claim that the correction directly blocked that shared acquisition is made.

#### One proposed bounded measurement — NOT started or implemented

Purpose: distinguish time spent holding the publication fence from acquisition
and monitor scheduling, including the currently invisible correction/RESET paths.
Use the unchanged current candidate, existing100×20/10commands/s/native resource
budgets and one60s concurrent diagnostic; keep original command deadlines and
financial/oracle checks. Setup remains outside the measured window. One run only;
if inconclusive, retain evidence and stop rather than automatically repeating it.

Reuse the existing observer/harness; enable collection only for measured work and
final drain. Correlate process+local transaction sequence, owner, existing command/
request identity and financial boundary identity/kind when available. Capture
monotonic and UTC timestamps for owner-lock attempt/acquired, first shared/exclusive
publication-fence attempt/acquired, replay begin/end, financial mutation begin/end,
transaction commit-observed/rollback, and monitor scan eligibility/queue/acquired/
cursor acknowledgement. Cover matching,manual intake,risk requests/RESET,parent
correction/replay,standalone monitor and price publisher in this SAME run. Record
SQL category/callsite elapsed/count separately before/after first fence; never log
SQL parameters,payloads,secrets or introduce SQL solely to collect timestamps.
Use backend PID only if exposed by the existing driver without a new query.

Bound total in-process collection to32MiB (8MiBmonitor,8MiBparent/publisher,
1MiBperPaperworker; remaining6MiB reserve); explicit overflow counters. Flush after
transaction completion outside lock scope; keep all counts/outcomes even if detail
limit is reached. Overflow or missing correlated stages invalidates attribution,
not silently drops slow inputs. Retain source/per-file hashes of touched runtime,
harness and observer, actual resource/configuration and unchanged source cadence.
A diagnostic result never constitutes acceptance or speedup. A later before/after
comparison must use this same observer/configuration on both candidates.

Success for that measurement: reconstruct at least one complete slow transaction
and every observed>3sinput's timeline, or explicitly identify the missing interval;
only then choose ONE supported code change with its affected safety tests. No
amendment/optimization proposed now because the causal interval is unproven.
The32MiBobserver design and collection have NOT been implemented or run here.

All criteria remain Paper everyreadyinput<=3s,target1s,processingp95<=250ms/p99<=1s,
original deadlines,financial invariants and missing-input accounting. No newAPI,
schema or Live work. W1–W4 remain pending. This closes only the authorized bounded
analysis, not F18 or Paper qualification.

### Required criteria review before another experiment — 2026-10-28

Owner instructed resume after adding the repeated-failure review rule. This step
reviews criteria only; no code,oracle,load,resource or threshold change and no new
workload/diagnostic. F15validation defines250ms/p991s processing; F18inherits it.
Current instrumentation includes transaction acquisition/body/commit and is not
end-to-end order latency. Paper3s was explicitly approved as a product timing
contract, not a Binance requirement.100owners×20orders is the approved capacity
profile; mission specifies multi-user SaaS but does not separately establish the
number of concurrently active users required at initial rollout. Registered-user
count must not be substituted for actively monitored/trading owners.

| Alternative | Proposed decision | Benefit/cost and user impact | Evidence needed |
|---|---|---|---|
| Keep approved100-ownercapacity and all timing gates | One bounded correlated measurement proposed in previous checkpoint before selecting a code fix; no automatic repeats | Preserves service target; implementation time remains unknown, so no promise to finish in another short round | Same-run all-writer/monitor/publisher timeline, then targeted safety and affected full validation |
| Re-scope initial supported capacity | Owner first specifies required simultaneous active owners; only then propose concrete dataset/rates and operational admission/capacity limits | May reduce engineering needed for initial rollout, but supports fewer simultaneous users; a smaller test cannot certify100owners and needs an enforceable operating limit/expansion plan | New approved capacity contract and validation; no estimate of improvement without measurement; retain100-ownerfailure as unqualified expansion target |
| Relax processing latency while retaining capacity | First establish acceptable product delay and measured-stage definition; no unsupported new numeric threshold proposed | Allows slower processing, can increase queue/lock residence; does not resolve independent3s risk misses and must not be sold as a complete fix | Explicit owner tradeoff, complete before/after definitions and all safety/progress/every-input checks |

Recommendation: do not raise risk3s again or merely round thresholds above the
latest misses. First decide whether100concurrently active owners is mandatory at
initial rollout. If it is, retain capacity and review processing response target
with the missing causal timeline; if not, specify the actual initial capacity
before a concrete amendment. This is a product decision, not a discoverable code
fact. No choice has been made on the owner's behalf.

Elapsed total development time is not reliably recorded as a complete aggregate;
owner reports more than2days. Prior evidence-only pass tookabout7minutes. Current
W1–W3 alone require45minutes of measurement after readiness, excluding setup/W4/
regression. Neither changing criteria nor the next measurement guarantees a pass
or a completion date. Any approved revision must update specs before implementation,
preserve oldFailedresults, and revalidate affected final-candidate gates. The
requested initial-capacity decision is pending; no further experiment started.

Owner decision: initial rollout MUST support100concurrently active owners on
the existing resources. Capacity reduction is rejected; retain100×20profile and
existing rates/resources. This answer does not approve changing processing p95,
Paper3s or any other gate, nor start a diagnostic. Remaining product tradeoff is
whether250ms processingp95 is mandatory or a slower explicit target is acceptable.
A500ms option would be a new owner-selected product budget (95%ofmeasured
processingtransactions withinhalfasecond,p99still1s),not a Binance standard,
measuredcapacity guarantee or inferred approval from current300ms failures.
It would not resolve independentrisk3s misses or guarantee earliercompletion.

### Owner retains processing target — 2026-10-28

Owner selected keep processingp95<=250ms and continue bottleneck analysis.
100owners/existingresources,p991s,Paper3s and all safety gates remain unchanged;
500ms option rejected. No threshold/spec/oracle change and no workload started.
Follow-up source inspection narrows the missing measurement: apply_position_event
enters financial_boundary before _apply_position_event detects an exact replay;
therefore the fixture's two identical correction calls both execute boundary
finalization and optional derived risk replay. Existing DB evidence confirms two
CORRECTION boundaries in one committed transaction. This is not evidence of two
financial effects; duplicate-effect oracle passed. correct_fill already avoids
loading matching state on a linked replay, so that optimization exists already.
Risk request processing similarly wraps unappliedRESET in financial_boundary.
The optional replay's SET LOCAL statement_timeout100ms limits each SQL statement,
not the total replay duration or time holding the transaction fence. This explains
why that setting cannot by itself establish a100ms upper bound for the observed
>=828ms correction lock interval; it does not identify which substage consumed it.

Do not remove replay validation or alter timeout/boundary semantics without
measuring those stages and the required amendment. Proposed single collection
from previous checkpoint should explicitly split first correction versus exact
replay, boundary snapshot/marker writes, optional derived replay, and RESET phases,
with the same transaction/owner correlation and shared/exclusive acquisition
intervals. This is still one diagnostic, no parameter trial. Existing authorization
was evidence-only and explicitly forbade starting collection automatically; ask
for the concrete next collection scope. Estimate:60s measured plus approximately
3–5minutes setup based on prior fresh2000order runs, with cleanup/analysis extra;
not an acceptance or completion estimate. Preserve normal60s progress deadline,
stop on failure, do not repeat automatically. No measurement code implemented yet.

### Approved single timeline collection — 2026-10-29 (Asia/Bangkok)

Owner approved one60s collection, no automatic rerun. Prepared external observer
and launchers under f18-20261027/runner only; no application/test runtime source,
criteria,API/schema or trading logic edited. Observer uses existing DB execution
calls, no new SQL, and records transaction/owner/command/correction IDs, monotonic/
UTC anchors, owner/catalog and shared/exclusive fence callsite attempt/completion,
replay/snapshot/matching/manual/risk-request spans and commit/error outcomes.
Monitor queue/round correlation included. Collection starts with measured schedule
and continues through final drain; serialized buffers bounded8MiBparent,8MiBrisk,
1MiBperPaperworker,explicit dropped/truncated counters. Parent/worker imports and
syntax verified locally before launch; this did not cover the child container's
Python script search path, which was the preparation defect below.

FreshDB tiewtrade_f18_release_timeline_20261029 bootstrapped and migrated0058;
PG4CPU/3GiB,Redis1CPU/256MiB confirmed. Attempt all-writer-timeline-20261029 failed
at risk child startup with ModuleNotFoundError:tests, reported by supervision as
F15_WORKLOAD_WORKER_EXITED_BEFORE_READY. NoPaper commands offered/admitted/completed,
no cycles/scenarios and no measured inputs. Preserve failure.json/log/manifest;
this is Failed setup, not a diagnostic performance finding or collectedtimeline.
The script entrypoint had replaced -m's working-directory import resolution.
Fixed external timeline_worker.py to add explicit /workspace/backend/src and
/workspace/backend before importing profile. Container import/wrapper preflight
uses the same image/mounts with networkdisabled and noDB/workload; verified afterfix.
No automatic workload restart, in compliance with the approved stop rule. Actual
60s collection remains pending; approval of thresholds/resources unchanged. All
owned workload/preflight containers exit, leaving idlePG/Redis. No performance
conclusion or further amendment can be justified by this failedsetup.


### Authorized timeline retry: completed collection, Failed gates — 2026-10-29

Owner explicitly instructed restart after the container import fix. Artifact directory:
`validation-artifacts/f18-20261027/all-writer-timeline-20261029-r2` (outside repo),
with adjacent log and host.json. No automatic further run. Source hash
`c389a24fc1d72101426a0eea3ca7c6e9ce36de1a772270f7a9f3119a53e8e320`,
742 files; R10 enabled, R9 preference/source-resumption disabled, monitor4,
migration0058, original resource allocations. This is diagnostic evidence only,
not W1 acceptance and not a before/after performance comparison with older observers.
All12 timeline buffers report dropped=0 and truncated_events=0. Workload containers
exited; only PostgreSQL/Redis remain. No runtime code or threshold changes.

Measured run elapsed63.529s; all500commands/100cycles completed. All100 owner
balance/position oracles and global invariants passed, duplicate_fill_effects=0,
and all3 financial scenarios completed. Risk57904/57904 acknowledged, no clock
errors/unacknowledged inputs;3 misses, max3.171490s. Processingp95=413.835ms,
p99=702.276ms,max1.575972s. Book580/600, resource_assertions_passed=false.
These remain failures; do not use successful financial checks to certify performance.
Host collection spanned about295s including preparation/cleanup; measured timeline
analysis used only the approximately63s window, not cumulative setup counters.

| Symptom | Same-run evidence | Conclusion | Remaining gap |
|---|---|---|---|
| Three price inputs exceed3s | Owner abf2b4e0-7f3b-4ced-8d46-82f3afb98f93, frames3123–3125 ready17:12:54.289539Z, acknowledged17:12:57.461029Z; parenttx5894 correction17:12:54.864273–56.918556Z | Correction overlaps the miss and prevents two monitor attempts from obtaining this owner's lock: risktx9785 and9861 time out after101.953ms/111.053ms; subsequent RESETtx9987 commits at57.460974Z immediately before ack | Correction is a demonstrated contributor, not the whole3.171s: pre-correction scheduling and post-commit recovery also consume time |
| Long financial critical section | tx5894 first shared fence call141.239ms; successful return at55.292407Z to commit56.918556Z=1.626149s | Main cost is after obtaining the fence, not solely acquisition |98 uncategorized post-fence SQL calls total1.061110s; cannot identify a safe SQL consolidation or distinguish server work/network/client stalls from these aggregates |
| Suspected duplicate correction/replay cost | First correct_fill1.857703s; exact duplicate133.870ms. Two optional replay spans63.264ms and40.342ms; four snapshot spans total57.341ms | Removing duplicate replay is not supported as the dominant fix; preserve idempotency and transient-breach checks | Durations overlap enclosing correction spans; never add nested spans as independent latency |
| Publication delayed behind financial writer | Parent publisher tx5958 exclusive call17:12:55.540119–56.917303Z=1.377184s, overlapping correction shared-fence residence and completing near its commit | Consistent with shared/exclusive contention propagating correction residence to publication | Client-observed SQL duration is not an isolated PostgreSQL lock-wait measurement; other shared holders may contribute |
| Processingp95 fails |3002 traced matching/manual transactions;346 exceed250ms, slow median363.568ms, SQL median281.364ms, aggregate shared-fence SQL median89.076ms;84 slow transactions have no successful shared-fence event | Fence alone cannot explain the whole processing tail | This cohort includes different operations; medians are not additive or proof that one optimization fixesp95 |
| Host/instrumentation confounding |124 host samples across63.369s: compression+1,967,985pages,decompression+1,936,120,swapins+4,135; even reentrant owner-lock SQL within tx5894 takes307.245ms | Strong concurrent host memory-pressure evidence; cannot attribute all SQL elapsed time to actual lock contention | No per-process scheduling/server-wait correlation. No controlled observer-overhead estimate. Do not claim host pressure alone explains every miss |

Decision: causal chain is narrower, but evidence is insufficient to select a safe
code optimization. Reject the specific hypothesis that optional replay/exact replay
is the dominant correction cost in this run. Preserve R23 rollback and all gates.
Do not rerun W1–W4 or try another concurrency/cache change.

One proposed next measurement, NOT started or authorized by this checkpoint:
retain this observer/configuration and add bounded static callsite-labelled SQL
elapsed spans for the first correction's mutation phase only, plus a bounded
out-of-transaction PostgreSQL wait-event sampler correlated by backend PID and
transaction interval. No SQL parameters/secrets, no new timing SQL inside financial
transactions. Single hypothesis: the long first-correction mutation consists mainly
of execution/scheduling delay rather than removable duplicate replay. Use this to
separate server waits from client elapsed time before choosing a code change; keep
all owner/fence/rollback/idempotency/balance checks. If a code fix becomes justified,
before/after must use identical instrumentation/configuration and an approved
amendment where required. No promise that another collection or code change passes.

This closes the authorized collection/analysis checkpoint, not Paper validation.
W1–W4/regression/final review remain unqualified; V22/V23 remain dependencies.


### Owner-approved Paper processing p95 revision — 2026-10-29

Owner accepted the proposed Paper-only p95<=500ms criterion. Updated requirements,
plan and validation first, then changed only the F18 integrated workload verdict
comparison from0.250 to0.500seconds. F15 standalone threshold, p99<=1s,
every-ready-input risk<=3s, resources/capacity/deadlines and all financial checks
remain unchanged. No production runtime/API/schema change. This supersedes the
previous owner decision retaining250ms for this Paper profile only.

Validation: ruff check and format check passed for the modified harness;5 existing
duration/endurance contract tests passed. No new type-bearing interface or behavior
beyond the approved numeric comparison; no workload/diagnostic or full regression
rerun for this threshold-only edit. Existing artifact results remain immutable:
414ms diagnostic p95 is numerically below the new threshold, but that run still
failed risk, book cadence and resource assertions and is NOT acceptance evidence.
Next outstanding work remains the correction critical-section investigation and
passing all readiness gates before W1–W4. No further measurement started.


### Authorized correction SQL/server-wait timeline — 2026-10-29

Owner explicitly approved one additional collection and instructed start. Estimate
announced12–21minutes (preparation5–10,run/setup4–6,analysis3–5). Actual approximately
8minutes total including preparation/analysis; host launcher226.188s, measured
elapsed62.044s. Docker was initially stopped; started Docker and only the existing
F18 PostgreSQL/Redis services, preserving resource allocations. Fresh DB0058:
`tiewtrade_f18_release_timeline_sql_20261029`. No production code changed.
External helper copies live in `validation-artifacts/f18-20261027/runner-sql-timeline`;
artifacts in `all-writer-timeline-20261029-sql` and adjacent host/log files.

Preparation verification: observer syntax/import and a read-only SELECT1 transaction
in the actual container passed; backend PID obtained from asyncpg connection metadata,
no extra SQL in financial transactions. Added static callsite/line timing only within
correct_fill; no SQL text/parameters/secrets recorded. A separate PostgreSQL session
sampled pid/xact_start/state/wait_event every200ms during measured/final-drain phase,
with8MiB output cap (actual2,399,380bytes,15,481rows). Sampler has overhead and adds
one observational connection: this remains diagnostic, not acceptance. Its leftover
psql backend2324 was identified and terminated after collection; no workload rerun.

Candidate source hash `a7a309da4cd228deb08a3df4b6c65eda32eadaba33d24f9a1b2d72a0588457b1`;
new approved F18p95<=500ms verdict, p99<=1s/risk<=3s unchanged. R10/R22 and monitor4
configuration retained. No causal speedup claim against the earlier run: different
instrumentation, restarted Docker/host conditions, and changed p95 acceptance threshold.

All short-run oracles PASSED, acceptance_result=false/diagnostic_only=true:
500/500commands,100cycles; risk80,704/80,704acknowledged,0misses>3s,0unacknowledged,
0clockerrors,max1.606143s (396targetmisses>1s); processingp95=304.038ms,p99=435.399ms,
max801.024ms. Book620/600, resource assertions passed, all owner/global financial
oracles passed,0duplicatefill effects,3financialscenarios complete. This does NOT
certify W1/W2/W3/W4 or replace earlier failures.

| Symptom/question | Evidence | Conclusion | Limitation |
|---|---|---|---|
| First correction mutation bottleneck | Parenttx4783,pid2075,owner466ec6a4-8242-45b5-a5fe-d58b17367f82,total868.623ms; firstcorrection720.476ms,duplicate103.920ms; firstfence39.923ms,observedhold620.123ms | Residence still spans many steps; no single dominant SQL identified | Not a controlled before/after comparison |
| Which SQL is slowest? | positions/storage.py:643 INSERT paper_position_events42.946ms; audit/writer.py:57 INSERT33.167ms; boundaries.py:130 claimfinalization32.366ms; walletread30.593ms | Ordinary required financial/audit writes contribute; no evidence justifying removal or consolidation yet | Includes server execution/transport/client scheduling; not pure DB CPU |
| Is duplicate/optional replay dominant? | Duplicate103.920ms,optional replay115.513ms and12.869ms,98otherpost-fenceSQLtotal529.733ms | Does not support removing duplicate replay as a sufficient fix | Nested spans not summed into transaction latency |
| Server lock versus client delay | Four200ms samples within correction:3 idle-in-transaction/ClientRead,1active/no wait; same-owner monitor timeout recorded twice during correction | Server sometimes waiting for client while transaction remains open; owner blocking is real | Sparse samples cannot establish time percentages or rule out short server waits; does not distinguish application work from host scheduling |
| Host pressure | Measured/final-drain host samples:compression+1,401,246pages,decompression+1,360,558,swapins+693,swapouts+7,556 | Pressure remains concurrent even though this short run passes | Cannot assert pressure is sole cause or compare magnitude as controlled optimization |
| Trace completeness | Parent/all10Paper buffers dropped0/truncated0; riskbuffer8MiB dropped2,327records,truncated0; correction interval and nearby monitor attempts present | Correction SQL attribution valid for recorded interval; risk SLA oracle separate and complete | Do not claim complete all-monitor transaction attribution for the tail |

Decision: do not introduce another speculative runtime amendment or change risk3s.
This single run satisfies short diagnostic oracles under the approved500ms threshold;
no reproducible >3s failure to justify a new corrective method here. Next acceptance
candidate should retain current runtime and run native W1 (600s) with diagnostic
wrappers/sampler removed, followed by the already specified sequential gates only
if it passes. Freeze source/config and review affected diff/dependencies first;
announce setup/run/analysis estimates before starting. This checkpoint ends the
specifically authorized one-collection scope; no additional workload automatically
started. All previous Failed/Partial evidence remains. Paper full validation and
V22/V23 dependency status are unchanged.


### Native W1 / approved Paper500ms — Failed, stopped early — 2026-10-29

Owner instructed start W1. Announced15–20minutes including preparation3–5,
measurement10,analysis2–5. Actual launcher664.335s (~11.1min including baseline
and cleanup); total preparation/analysis approximately14minutes. No concurrent
workload/diagnostic. Source hash before/after matches
`a7a309da4cd228deb08a3df4b6c65eda32eadaba33d24f9a1b2d72a0588457b1` (742files).
Native isolated_workload_r18 launcher, no timeline wrapper/PID/wait sampler,
original W1duration600s, R10true/R9false/source-resumptionfalse/monitor4;
PG4CPU3GiB,Redis1CPU256MiB,aggregateapp4CPU2GiB. Fresh0058database
`tiewtrade_f18_release_w1_paper500ms_20261029`. No runtime edits.
Artifacts `validation-artifacts/f18-20261027/w1-paper500ms-20261029`, adjacent
host.json/log; external launcher `runner/run_w1_paper500ms_host.py`.

Baseline2000orders completed. Read-only artifact scans during measurement used
existing input/ack records, not a second diagnostic or added transaction SQL.
Through417.391s of input-ready timestamps no confirmed>3s misses (497790acks,
max2.324667s). At478.108s scan,555262acknowledged inputs included51confirmed
misses across9owners,max4.103704s. First affected owner
`d657ee07-8002-429c-b3e1-0a703afe0aee`,frames8652–8654,
ready2026-10-29T01:46:42.815047Z,ack01:46:46.918751Z. All51misses recorded in
`early-risk-failure.json`; scan is partial and does not discard unacknowledged
inputs or count them as passed. More misses could exist outside this scan.

As required by stop rule, sent one SIGINT to parent, allowing asyncio finally/
Fixture.close to stop publisher/workers. Exit130; failure.json CancelledError is
intentional cleanup, not root cause. `abort-reason.json` links it to confirmed
risk failure. OnlyPG/Rediscontainers remain. Did not start W2/W3/W4 or repeatW1.
Partial counters:4929offered,4901admitted/completed,0rejected,1955fills,977cancels,
984replays,968cycles. All3scenario records present, but final global financial/
resource/latency oracles were not reached: do NOT report them passed or derive
acceptancep95 from setup-mixed worker metrics. Full600s not completed; W1Failed.

The9-owner miss cluster is not proven to share the earlier single correction
cause. Host sampling over failure-window ±1s showedcompression+322817pages,
decompression+311653,swapins+8,swapouts0; this is concurrent pressure evidence,
not proof of sole cause. Short diagnostic pass cannot predict full-window tail
latency. Preserve approved500ms/p991s/risk3s; do not raise thresholds or add
another speculative code trial. Next useful step is bounded analysis of this
existing multi-owner window/preceding acknowledgements before proposing any
further experiment. Paper validation remains incomplete; previous failures and
V22/V23 dependencies retained.


### Existing-evidence analysis of native W1 multi-owner miss — 2026-10-29

Owner instructed analysis. Announced10–15minutes; actual approximately5minutes.
Read existing inputs/acknowledgements/host samples and relevant scheduler code only;
no code change, SQL query, new workload/diagnostic or criterion adjustment.

| Symptom | Evidence | Conclusion | Gap |
|---|---|---|---|
| Nine owners /51 confirmed price misses | Ready01:46:42.815047Z through acknowledgements01:46:47.463593Z; first ownerd657ee07… max4.103704s | Real committed-input latency, not an unacknowledged-input omission or percentile issue | Abort-time scan is not a full-run oracle |
| Earlier correction suspected | Only measured CORRECTION records510/511 commit01:40:19.836769Z for ownerbfd2f00e…; miss cluster begins~383s later, different owners | Earlier correction transaction cannot directly hold its lock during this cluster | Other financial writers can still contribute contention |
| Owners with no new financial boundary | Seven of nine affected owners retain the same boundary across their preceding and delayed acknowledgements; two advance on FILL2811/2815 | A new money mutation on every affected owner is not needed for the failure | Unchanged boundary does not rule out no-op/read-only transactions holding owner locks |
| Broad processing slowdown | Monitor successful acknowledgements64.75/s in01:46:40–44Z,31.33/s in44–47Z,92.5/s in48–52Z. All100owners represented in before/recovery windows | Reduced monitor throughput across many owners, rather than one total process pause | No per-round start/end or owner queue/lock spans in this native run |
| Per-owner delay while other owners continue |19owners have monitor-only acknowledgement gaps>3s spanning this window; longest5.502449s(d657ee07…). Maximum gap between ANY monitor acknowledgements only248ms | Monitor continued making progress; a multi-second global stop is not demonstrated. Per-owner scheduling/deferral matters | Monitor-only gaps are not risk misses by themselves: Paper acknowledgements can satisfy the oracle |
| Price publication also slows | PRICE frame records9.75/s before,3/s in44–47Z,9/s after (these are per-symbol frames, not bookHz) | Shared slowdown reaches publisher too | Need publication execution/fence waits versus client scheduling to attribute cause |
| Host pressure correlates | Compression rates~28138pages/s before,74544pages/s during,18300pages/s after, using sample-to-sample deltas within each window | Host pressure is a supported competing explanation for broad slowdown | Correlation is not causation; no per-container throttling/event-loop/server-wait timeline in this run |

Relevant code: risk_limit_main.monitor waits for each run_risk_monitor_round,
then20ms sleep. risk_limit.py selects up to100owners, sorts within the page bydue_at,
uses semaphore4, and awaits gather for the whole page before the next scan.
Each SQL statement has700ms statement_timeout and ownerlock100ms; these are not
whole-page/whole-transaction deadlines. Therefore variable work/deferrals can
increase revisit gaps, but existing artefacts do NOT prove gather or any particular
SQL is the primary bottleneck. Do not reapply previously failed concurrency changes
or remove locks/replay based only on this structural possibility.

Decision: evidence is insufficient for a justified runtime fix. The specific
hypothesis to resolve next is shared execution/scheduling slowdown versus monitor
page/owner wait: the first predicts concurrent event-loop lag across monitor and
publisher; the second predicts normal heartbeats with long measured queue/lock spans.
A single proposed (not started) bounded collection should retain the native600s
load/configuration and capture rolling monitor round/queue/ownerlock timings,
monitor+publisher monotonic heartbeats and container CPU throttling, preserving only
a short window around the first>3s miss plus prehistory; no financial SQL added,
no secrets/SQLparameters, and no repeated runs if failure does not reproduce.
Existing host samples and input/ack oracle must remain correlated by time/owner;
report overflow and observer overhead. This is a proposal requiring explicit scope
approval before another diagnostic, not permission inferred from evidence analysis.
No claim that relaxing3s, changingSQL or addingworkers will fix it. Existing approved
p95500ms/p991s/risk3s and all financial gates remain; W1Failed/W2–W4not started here.


### Approved bounded rolling monitor/heartbeat diagnostic — 2026-10-29

Owner instructed start proposed collection. Announced20–30minutes; actual about
17minutes including preparation/analysis, launcher693.945s (~11.6min). One run,
no retry, no production code/spec/threshold change. Native600sW1load,100×20,
R10/R22,monitor4,originalCPU/RAM and all financial gates. Fresh0058DB
`tiewtrade_f18_release_rolling_20261029`; source hash
`a7a309da4cd228deb08a3df4b6c65eda32eadaba33d24f9a1b2d72a0588457b1`.
Artifacts `validation-artifacts/f18-20261027/rolling-w1-20261029`, host/log adjacent;
external observers in `runner-rolling` only. Reused existing stage wrappers,
removed per-SQL events, bounded serialized stage ring16MiB, heartbeat5000samples,
pressure200samples,GC1000samples. No new financial SQL/SQLparameters/secrets.
Risk round/queue/user/ownerlock/transaction spans, parent+risk20msheartbeats and
cgroupCPU/memory observed. Import/cleanup/duration preflight passed with networkoff,
no workload. Observer overhead not independently quantified; not acceptance.

At530.918s of observed ready-input span,602308acknowledged inputs included3misses
for owner6442c1ed-afe7-46c0-92a4-9eedfd497df8,frames8925–8927:
ready02:08:44.027219Z,ack02:08:47.214436Z=3.187217s. Sent oneSIGINT,
finally/Fixture.close cleaned up; exit130/CancelledError explained by abort-reason.json.
No other workload or nextphase started; onlyPG/Redis remain. Partial5361commands
completed,1060cycles,3scenario records; final financial/processing/resource oracles
not reached and not claimedPassed.

Ring retained82,254events/16,777,032bytes spanning02:08:13.971822Z through
02:09:24.036081Z.795,598old events intentionally evicted by rolling policy.
Failure window and preceding rounds are fully within retained interval; do not
claim full-run stage coverage. Both heartbeat/pressure series cover failure±1s.

| Non-overlapping stage for this input/owner | Duration | Evidence |
|---|---|---|
| Input ready to first attempted evaluation |1.151611s | Round1059 had capturedwatermark8924 before input; ends+0.732417s. Round1060 starts+0.758483,ownerqueues+0.766461,acquires+1.151588 |
| First evaluation fails ownerlock |0.114990s | Lockattempt+1.156695 to+1.260363; userfailed+1.266601,DatabaseTimeoutError |
| Failed attempt to next owner evaluation |0.952530s | Round1060 ends+2.192797,round1061ownerenter+2.219131 |
| Second evaluation fails ownerlock |0.111229s | Lockattempt+2.225934 to+2.329099; userfailed+2.330360 |
| Failed attempt to successful owner evaluation |0.814194s | Round1061 ends+3.110193,round1062ownerenter+3.144554 |
| Successful evaluation to observed acknowledgement |0.042663s | Lock acquired+3.149377,snapshot+3.163468,commit+3.187190,ack+3.187217 |

This partitions the3.187217s latency without summing concurrent transactions.
Two lock-timeout attempts plus waits for subsequent pages are proven contributors;
~1.767s occurs between failed owner evaluations and their next attempts. Sameowner
boundary remains3258 through successfulack; previousFILL02:08:41.382354Z,
nextFILL02:08:49.006429Z. No correction in this window. Cannot infer absence of
lock-holding no-op/read-only financial transactions from unchangedboundary.

Risk heartbeat maxlag123.853ms and parent85.867ms in failure±1s; risk cgroup
nr_throttled/throttled_usec unchanged. ParentAPI/Paper group shows throttling
(+2,499,013aggregate microseconds over selected±1s sample interval), which must
NOT be added to this owner's latency. NoOOM/high/max memoryevents. Evidence does
not support a seconds-long risk event-loop freeze as the primary explanation of
this captured miss; upstream writer slowness/host effects may still prolong locks.
Unlike the prior native9-owner event, this is a single-owner event: don't claim it
proves the cause of all previous misses.

Next smallest method proposal: investigate a bounded retry of a lock-deferred owner
within the current sweep, re-entering the existing semaphore and full financial
checks, rather than always waiting for page completion and a new scan. Hypothesis:
reduce the measured post-timeout revisit gaps, not risk computation time. This is
NOT implemented/approved here and is not guaranteed to help: holder could remain
busy, retries may delay other owners or cause starvation. Any amendment must fix a
strict retry/hint budget and fairness, preserve4slots/locks/rollback/publication
fences, and test busyowner isolation, retry/idempotency, transientbreach/latch,
request/stopprogress and other-owner latency before one matched comparison. Prior
failedR15/nonblocking/concurrency trials must inform the proposal; do not reapply
them unchanged. Exact lock holder/hold interval remains unknown in this observer.
This ends the one-collection authorization; no new diagnostic or runtime trial.


### R24 proposal prepared — 2026-10-29

Owner instructed proceed after rolling diagnostic. Prepared
`bounded-monitor-retry-amendment.md` as Proposed; no runtime/test/workload change.
Compared R15 and current service/test contracts. Retry proposal explicitly cannot
claim to recover all1.767s: first-attempt fairness and unknown holder release limit
its useful window. Maximum4extra attempts/page,1/owner,4slots unchanged;100ms
cooldown outsidetransaction; no deferred retry starts after first attempts finish.
Deterministic barrier/fairness checks must justify proceeding to one matched trial.
Estimated5–10minutes for document work, actualapproximately4minutes. New method
approval pending; previous testing/threshold approvals remain valid.


### R24 approved; rollback-observability boundary found — 2026-10-29

Owner instructed start R24 implementation. Before code changes inspected session
cleanup and scheduler callers. Existing_begin suppresses rollback SQLAlchemyError/
OSError and rethrows bodyerror, so monitor cannot prove rollback success required
by approvedR24. No observed failure is claimed; this is a contract limitation.
Prepared ProposedR24-A in bounded-monitor-retry-amendment.md: explicitopt-in
rollback-success contract for monitor only, typed sanitizedcleanupfailure, unchanged
defaultcallers/cancellation. Requires sharedDBscope approval before implementation.
No runtime modified/tests/workload run. Initial20–35min implementation estimate
superseded by this scope boundary afterabout4minutes inspection/documentation;
implementation/test timing must be reassessed once the addendum is decided.


### R24/R24-A implemented, tested, one trial Failed and rolled back — 2026-10-29

Owner approved R24-A with “เริ่มทำ”. Initial estimate25–40min forcode/targetedchecks;
then explicitly announced15–25min fullDBregression and15–20min singletrial.
Actual totalabout38min; fullregression test execution803.57s across3segments;
trial launcher786.107s (~13.1min) includingbaseline/cleanup, measured611.828s;
rollbackverification within3–6min estimate. No parallel workloads/tests/diagnostics.

Implementation: boundedmonitor retry1/owner,max4/page,firstattemptfairness,
100msoutside-transactioncooldown,existing4slots,skip unstartedretrywhenfirstpageends;
opt-in user_session rollback confirmation and sanitizedDatabaseCleanupError.
Both F15/F18 measurement wrappers forwarded the new option without changing clocks.
Safety barriers proved actualPostgreSQL ownerlock release/retry beforetailcompletion;
unit tests covered budget,cleanupfailure,cancellation andnoafter-pagecooldownwait.
Initial5unitsetup errors were misplaced testfixture requiringDB; moved pureunit
module toexisting rootunit-test location, no production workaround. Static type
check initially found2measurement-wrapper signature mismatches, fixedforwarding.

Full regression used fresh0058DB tiewtrade_f18_release_r24_regression_20261029:
- r24-regression.xml/log:887passed,1failed,2venuecontracts deselected,303.86s.
  Paper isolation allowlist omitted existing monitor_snapshot dependency; module
  already in scannedPaperfiles and has noLive/network imports. Registered exact
  dependency without weakening forbidden checks.
- r24-regression-resume.xml/log:1280passed,1failed,889deselected,291.59s.
  Fixture publication asserted contiguous IDs over historicalretainedoverflowdata;
  record pre-testmax then check onlythisfixture's newer IDs. Existingretention
  failures not hidden; full assertion still applies to allnewfixtureinputs.
- r24-regression-resume2.xml/log:1665passed,2165deselected,208.12s.
  Union of finalcaseoutcomes3828uniquePassed (r24-regression-coverage.json),2explicit
  venuecontracts excluded perexistingdefault. Resumes preserved oldfailures and
  reused unchangedpassidentities; not an uninterruptedfirst-runpass.
- mypy573files,ruff/format and7architecturecontracts passed onexperimentalcandidate.

Single experiment artifacts `validation-artifacts/f18-20261027/r24-rolling-w1-20261029`,
sourcehash dd2693aa3eccd0cf9e541473af3091e4b782c960aac8c1caad5f85d84c03aed5.
Same rolling stages/heartbeats/budgets andnative600sload asbaseline; externalasyncio
proxy was adapted to forward newasyncioEvent/create_task/wait_for calls (no change
to sampling or clocks). R10/R22/4slots,CPU/RAM/rates/deadlines unchanged.
Results:6000/6000commands,1200cycles,all3scenarios,financialinvariantsPassed,
0duplicateeffects; book6118/6000; processingp95352.387ms,p99528.084ms,max1.265762s.
Risk746104/746104acknowledged,0unacknowledged/clockerrors,3misses,max3.586173s.
ResourceFailed:connections_end55 versusstart44+2;peak56,RSS96,415,744bytes,
lockwaitsend0,inputlag12. This count does not by itself prove a connectionleak.

Miss owner ec9eda3c-154a-40b4-bbc9-391a8401f951,frames10734–10736,
ready02:49:25.746416Z,ack02:49:29.332589Z. Retainedring covers entirefailurewindow.
Round1135firstattempt at+1.467070s timedoutownerlock; same-roundretry+2.564776s
also timedout. Round1136firstattempt+2.696046s timedout; retry+3.567193s finally
succeeded andcommit+3.586155s. Retrymechanism exercised (83extraattempts inretained
window), but didnotmeet hardSLA. Riskheartbeat max98.044ms,parent265.943ms infailure±1s.
Do not claim this run proves regression/improvement acrossallowners relative to
abortedbaseline; differentduration andunknownhost/writercontention remain factors.
Failure arrived duringlastpoll/finalization; result.json alreadyFailed, no rerun.

Per approvedstoprule rolledbackR24andR24-A: scheduler/session/errors match archived
pre-R24 bytes exactly; removed opt-inmeasurementwrappers and experimentaltests,
archived under trial/source. Retained twoF18testfixes above. Finalsourcehash
84103c64b123a95aebf70e8d1a857d2f49d2941d76dc0bdc93195f9e0dff7000 (742files). Rollback r24-rollback.xml/log56Passed; mypy571,
ruff and8fileformatcheck passed,wrapperformatcheckpassed afterwhitespace restoration.
3828fullcoverage applies toexperimentalcandidate; finalrollback has affectedchecks
and reusableunchanged evidence, not a new fullworkload/fullregressionpass claim.
NoW2/W3/W4 orsecondtrial. OnlyidlePG/Redisremain. Paper validation stillFailed/
PendingFullValidation; V22/V23dependencies unchanged. Exact lockholder/holdreason
and finalconnectionscount require evidence-based investigation before anothermethod;
do not change risk3s or replay/fencing to force a pass.


### Criteria flexibility proposal R25 — 2026-10-29

Owner requested product-appropriate flexibility to accelerate delivery. Read existing
sampler/callers and evidence only; no tests/workload/runtime/oracle change. Prepared
Proposedpaper-acceptance-flexibility-amendment.md, not approved criteria. Proposed
per-owner+global99.9%<=3s with everyinput<=5s forPaper; target1s/Live1s and financial
checks preserved. Explicit delayedlatch/stop tradeoff and unknowns; no guaranteepass.
Connectionproposal replaces live start+2 with predeclaredpoolbudget plus postcleanup
appconnections0 (5sdeadline), inventory completeness required before numericbudget.
Sampler already scopescurrentDB; flaw is comparison of live sample phases, not a
provenleak or proof55connectionsnormal. Currentrisk3s remains in force pending
approval. Estimated5–10min proposal preparation,actualabout5min; no new experiment.


### R25 approved, oracle/resource implementation and native W1 Failed — 2026-10-29

Owner instructed start after the R25proposal/likelihood/other-apps discussion;
accepted this as approval of the concrete A/Bproposal. Updated requirementsNC05,
plan/validation and amendmentapproval before harness. No productionruntime,
financialformula/API/schema,workers,pooloptions or resources changed. R24/R24-A
remaininactive. Current Paper contract: perowner/global99.9%<=3s and everyinput<=5s,
target1s,processingp95500ms/p991s. Preserved all oldFailedresults andLive1s/dependencies.

Announced15–30min implementation/targetedvalidation; actualapproximately20min,
includingactualpoolinventory. Thenannounced15–20min nativeW1; launcher299.452s
(~5min,abortedbyexisting60scommanddeadline), read-onlyfailureanalysis/closureabout6min.
No automaticrerun orsecondworkload. No fullregressionrerun: sourcechanges confined
to F18test-harness/oracles; production sources fromR24rollback untouched, targeted
callers/contracts examined; priorunchangedfinancialchecks reused, not substituted
for incompletefullacceptance/remoteCI.

Implementation:
- sla_summary retains chronological input/commit correlation/faultwindows; all>3s
  samples persisted inrisk-late-inputs.jsonl, separatehardmiss>5s, perownercounts,
  exactinteger99.9%quotas andcompleteexpected/unack/clock accounting. No tail removed.
- New tests/infra/risk_limits/profile_resources.py observes actualcreatedpools in
  parent/Paper/risk throughcheckout/checkin events. No financialSQL added. Captures
  configuration atcreation, limitsbudget beforemeasurement usingserverheadroom,
  checks returnedcheckout counts andgenerationconfigurations, then physicalcleanup
  afterstop/disposewithin5s. Onlyownquery/predeclaredobserverPIDs excluded.
- Initialcleanup test caught a realoraclebug: backend_type is hidden for someother
  roles inpg_stat_activity, sofilterwould falselyomitconnections. Fixedto count
  targetDBauthenticatedbackends usingvisible datname/usename, notprivilegedtype;
  detectsactualheldandreturned-but-not-disposedclients. No grants added.
- Hooks/factoriesrestoreonexit; observedpoolrecreation acrossW3churn verified.
  Candidate defaults untouched; no guessed60connectionsbudget orwarmallpoolworkload.

Evidence: r25-targeted.xml initially26pass/1failure(cleanupvisibilityabove),
r25-resources-fixed.xml2pass; r25-final-targeted.xml41pass includingSLAexact3/5,
perownerquota,small-sample/no-rounding,missing/pending/clock/faultwindows,
actualpool/cleanup,actualPaper/riskworkers,factoryrestoration,existingpublication/
workload/supervisioncontracts. r25-final-resources.xml4pass andfinal4casecheckpassed
onfinalqueryfilter/churnguards. Ruff/formatpassed4changedfiles,mypy574passed.
No claim that these replace W1–W4.

Nativecandidate sourcefreeze `r25-source-freeze.json`:
ec563f2c973a25c45cf36fd4f790f48128e75687d3f11bbaae39e25feae1de62 (745files),
unchangedafterrun. Artifacts validation-artifacts/f18-20261027/r25-w1-20261029,
adjacenthost/log. Fresh0058DBtiewtrade_f18_release_r25_w1_20261029.
R10enabled/R9preferencefalse/source-resumptionfalse/monitor4; existingisolated
aggregate4CPU/2GiBapp,PG4CPU3GiB,Redis1CPU256MiB. No diagnosticwrappers.

Frozenpoolinventory beforemeasurement:parent5defaultpools(5+10each),10Paperworkers
withENGINE/ENGINE_SCANdefaults(5+10each),riskactualpools4/1/2/3,max_overflow0.
Declaredcapacity385; PostgreSQLmax200,reserved3,otherDBclients0 -> enforcedbudget197.
This exposes potentialoverprovisionedpoolcapacity and is not a guarantee all385
slotscanbeusedsimultaneously. Recordedbudgetderivedfromconfigurationbeforeobserved
load, not adjustedtopasspeak. Workloadprogress/poolerrors/cleanupstillmustpass.

W1 baseline2000orders completed; measuredowner-cycle deadline60s thenexpired.
failure.jsonTimeoutError (notintentionalSIGINT),443offered/370admitted/completed,
0rejected,137fills,64cancels,83replays,46cycles. OnlyPARTIAL_FILL_RISK_ORACLEscenario
completed; selectedowner0501bc45-60e4-4d7c-b781-4ecb3cea980c wasin
breach_reset→new(reseed)→request atprofile_workload.py:478 whenoutercycle timedout,
waitingforAPIpoolcheckout. APIpeakcheckedout15(itsconfiguredcap); parentENGINEpeak6;
all12pooldocumentsfinalized/allchecked_out0aftershutdown. Logalsocontainsriskinbox
financialfence55P03timeouts; noexceptionfromnewpooltracker/cleanuporacleobserved.
This identifies timeoutlocation/poolpressure, NOT which transactions heldAPIpool
slots or thecausalshareofhost/SQL/hookoverhead. Do not assert harmlessinstrumentation
orprovenruntimeleak fromthisevidencealone.

Lastread-onlyackscan35469inputs,max3.393904s,0observed>5s,readyspan
58.892844s. This ispartial anddoesnotqualifyperownerquota/fullrisk/unackoracles.
Finalfinancial/resource/physicalcleanupverdictsnotreached becauseprimarycyclefailed;
returnedpoolcounters alone are not proof of the5sphysicalcleanupgate. NoR25result
reassessmentofoldartifacts andnoPaperPassedclaim. R25approvedcriteriaremain inforce;
nochange to60sdeadline. OnlyidlePG/Rediscontainersremain;W2/W3/W4notstarted.
Nextanalysis should identify APIpool-slot holders/checkoutduration duringreseeding
fromavailableevidence before anothermethod; do not repeatworkload orraisedeadlines
without a groundedproposal. V21PendingFullValidation/V22–V23PendingDependencyremain.


### Deadline review and concrete R26 proposal — 2026-10-29

Owner requested re-evaluation due to elapseddevelopmenttime. Read F15validation206–239,
F18plan471/R6 andactualfixture/scheduler, no tests/workload/code change.
Confirmed60swasdefinedforF15positive5-commandcycle as harnessprogressbound, not
productionorderexpiry. F18approvedplanexplicitlykeptitincludingrecovery20reseeds;
this is a proposedcontractrevision, not an inferredimplementationdefect.
Prepared Proposedrecovery-scenario-budget-amendment.md: ordinary/normalelapsed60s,
one selectedbreach_resetphase120s,totalguard180s; sameinner30/10/60bounds,
load/rates/durations/finalelapsed/drain/R25/financialgates. Numeric120is a product/
engineeringtradeoff awaitingapproval, not a measurednecessarybound orassuredpass.
Preserve selectedscenario underload andpositivecounts; no pause/exemptionofotherowners.
Reviewestimated5–10min,actualabout5min. No furtherdiagnostic orspec/oracle change;
R25remainsapproved/current andW1Failed. Proposal gives a boundednextdecision rather
than another speculative scheduler trial.


### R26 approved/implemented; native W1 ordinary end-RESET timeout — 2026-10-29

Owner repliedapprove toR26. Updatedrequirements/plan/validation beforeharness.
Implemented optionaltest-onlycycle_scope inF15scheduler (default60s unchanged),
F18profile_timing.py withtask-localbudget/context,oneeligible120srecoveryextension,
normal60s/outer180s guards andperstage/20reseedidentity logs. Originaldeadline
resumeswithonlyactualrecoveryelapsed credited; cannotreviveanexpirednormaldeadline,
re-enterrecoveryoruseitforanotherowner/cycle. Allprocessing/riskelapsed remains
unadjusted. Existing30/10/60innerbounds,rates/due-times/counters/faultgate/financial
runtime/poolconfiguration unchanged. Cancellationrecords stage outcome andresets
context; recoveryaudit cannotbesilentlymissing. R25criteria remaincurrent.

Estimated15–30min implementation/targetedchecks,actualabout9min; estimated15–20min
nativeW1includinganalysis,actualabout12min (launcher388.391s,plusread-onlyanalysis).
Totalapproximately21min. No concurrentworkload/diagnostic andnoautomaticrerun.
Targeted r26-targeted.xml56Passed: controllable-clocknormal61/recovery121 failures,
exact60/120/180inclusive,selectedfirstcycleonly,duplicatephase/missingevidence,
cancellation,F15default60with/withoutfaultgate,callback/countercontracts plusR25/
publication/pool/supervision tests. Mypy576,ruff/format4filesPassed. No fullbackend
rerun becauseproductionfinancialsources unchanged andaffectedharnesscontractscovered;
priorunchanged evidence reused, no acceptance/fullregression claimfromtargetedalone.

Sourcefreeze0ff38ce84d1bb633c5d5646b84d0b87d7c199e3f5865a62fbcc3195e79d78196
(747files),unchangedafterrun. Artifactsvalidation-artifacts/f18-20261027/
r26-w1-20261029,adjacenthost/log,r26-source-freeze.json. Fresh0058DB
`tiewtrade_f18_release_r26_w1_20261029`,R10/R22,monitor4,originalCPU/RAM/10workers,
100×20baseline,book/rates/duration unchanged; no diagnosticwrappers.

Baseline2000orderscompleted. W1Failedafter~61smeasurement,notdue120srecoverybound:
ordinaryowner f7d01544-71a8-4a42-a093-d558eaffce27 cycle0 TimeoutError with
normal_seconds60.052668,recovery_seconds0. Tracecycle→mutation(RESET) at
profile_workload.py695,waitingduringAPItransactioncommit/connectionclose.
This is theextraRESET followingfivecommands, notordinaryNEW/CANCELexecuting at
thatstackframe. Need timestamps ofthefive-commandcompletion tocertifytheir own60s
bound; reachingendRESETalone doesnotproveexacttradingcompletiontime.

Selectedowner39e98553-4f1e-4066-9047-f71f82bc29d6 wascancelledwhenpeerfailed,
normal15.279020s/recovery45.829647s/total61.108667s. Stagescompleted:
breach_stop3.897s,price0.369s,reset2.333s,reseeds1–9(6.988/1.837/2.257/1.985/
5.572/2.750/3.954/8.789/3.117s); reseed10 cancelledafter1.976s. Thisdoesnot
proveall20completewithin120s, but selectedrecoveryitselfdidnotexpire.
cycle-timing.jsonl116records:21completed,1TimeoutError,94CancelledError.
Counterincrements precedeendRESET, explaining30cyclescounterversus21fullyreturned
cyclecontexts; do notsubstitutecountercompletionforfullcontextcompletion.

Partial380offered/295admitted/completed,0rejected,111fills,50cancels,66replays,
30cycles;onlypartial-fillscenariocomplete. Lastackscan37502,max4.950270s,
0observed>5s,readyspan60.411441s. Perownerquota/unack/fullfinancial/resource/
physicalcleanupgatesnotreached; noR25riskPassedclaim. Allpooldocumentsfinalized
withchecked_out0; onlyidlePG/Redisremain. W2/W3/W4notstarted.

New reviewfocus before anothertrial: Fixture.cycle unconditionallyaddsoneRESET
throughsingle-slotriskrequestworker afterEVERYpositivecycle, outsidefivecommand
counts. AtW1/W3nominal10commands/s thisadds~2RESETs/s;W2nominal100commands/s adds
~20RESETs/s, plusselectedriskcase. F18validation saysdeterministicriskmutation
schedule butdoesnotseparatelydeclarethisrate. CurrentR26explicitlykeptendRESET
inside60s,soharnessmatchesapprovedR26; do notsilentlyremoveit/increasetimeout.
Reviewwhetherthisadditionalresetloadmatchesproductcapacityneeds,anddeclareits
ownrate/deadline/counters beforeanynewproposal. No newnumericbudget/changemade.
Oldfailuresretained,R26/R25remainapproved/current; PaperPendingFullValidation,
V22/V23dependencies unchanged. Noadditionalworkload authorized/inferred here.


### R27 decision proposal after R26 failure — 2026-10-29

Owner asked how to proceed after repeatedfailures. Prepared Proposed
`declared-reset-workload-amendment.md` fromexistingevidence only (~5min announced).
No newtest/workload orruntimechange. Proposedexplicit100under-loadRESETs/run,
one/owner,<=1/s due180..279(selectedlast),fault-awarefixedschedule;removeextra
endRESETfrom5-commandcycles whilekeeping60snormal/fullRESETbounds,R26recovery,
R25 andtradingloads/resources. Mustapprovecapacitytradeoff:doesnotcertify20RESET/s
or100simultaneousRESETs. Not a claimedAPIpoolfix/guaranteepass. CurrentR26stillinforce
pendingapproval. Avoid anotherW1beforethisloaddefinitiondecision.

### R27 implementation and first W1 failure — 2026-10-29

Owner approved R27. Implemented the fixed 100-owner scheduled RESET producer,
removed synthetic end-of-cycle RESETs, supervised cancellation/fault propagation,
serialized only per-owner evidence-marker collection, and recorded trading-only
completion separately from selected recovery/restoration. No production financial
code change in this revision. R25 SLA oracle callers were updated to current
approved thresholds; old failed runs remain failed.

Targeted checks: r27-final-targeted.xml 108 passed; mypy src/tests 578 files passed;
ruff/format affected files passed. These did not catch the restoration contract:
the ordering mock incorrectly expected SET. A real PostgreSQL fixture-path test
is required before another workload; targeted success is not acceptance.

Frozen source 908312ca9f48c3787ca2cb489f37c86aeb04e6b704b0a5dcf2de03fec0412b91
(749 files). Artifacts: validation-artifacts/f18-20261027/r27-w1-20261029,
adjacent log/host evidence and r27-source-freeze.json. Fresh database
tiewtrade_f18_release_r27_w1_20261029, migration 0058, R10/R22, monitor 4,
original CPU/RAM/workers, native profile without diagnostic wrappers.

W1 FAILED: selected owner c88dedf0-bd19-4034-bf56-32f88d51b29c reached
post-scenario restoration, then Fixture.cycle called mutation(SET,1000).
Existing settings reject SET; risk scope/revision/authorization conflict stopped
the run. This is an introduced harness bug, not evidence that performance failed.
All three selected risk scenarios completed beforehand: partial-fill oracle,
breach/stop/reset/reseed (20 targets), and exact correction/replay. Selected
normal/recovery times were 20.769s/59.606s; the overall cycle still failed.

Partial counters: 740 offered, 700 admitted/completed, 0 rejected, 270 fills,
136 cancels, 147 replays, 120 trading cycles. Scheduled RESET expected 100,
offered/applied/failed 0/0/0: failure preceded due=180s. Last partial ACK scan
54,998 inputs, max 3.471905s, no observed >5s, ready span 80.281558s; this does
not prove full per-owner/global quotas, unacknowledged-input coverage, final
financial invariants or resource/physical cleanup acceptance. W2/W3/W4 not run.
Worker workload has stopped; only isolated idle PostgreSQL/Redis remain.

Follow-up read-only investigation (~10 minutes, no tests/workload) confirmed
INCREASE needs exact AUTH authorization and F-06 verification. The existing W4
fixture already demonstrates this path. Current parent has five pools and no
AUTH pool; R27 explicitly forbids adding pools. Prepared R27-A in the same
amendment document: one bounded AUTH connection, full inventory/cleanup evidence,
real DB regression before one further W1. R27-A is Proposed; no code changes or
workload rerun in this follow-up. Earlier plan/validation SET wording remains a
known defect pending approval of the corrected method. Paper remains Pending
Full Validation; V-22/V-23 remain Pending Dependency.


### R27-A authorized correction and one W1 — 2026-10-29

Owner instructed เริ่มทำ after R27-A proposal: approved the bounded AUTH pool
and one further W1. Corrected post-oracle restoration to INCREASE with identical
revision/scope/key/amount for F-06-verified AUTH authorization and API intake.
Reused W4's enrollment/verification pattern only for synthetic isolated owners;
no production auth bypass, financial/runtime changes or secrets in evidence.
Existing SET/RESET transaction path retained without an extra API round trip.
AUTH size1/overflow0 added to complete parent inventory (6 pools), close/disposal;
isolated-target guard now includes AUTH and rejects missing/remote/different DB.
Requirements/plan/validation and amendment reflect this approved correction.

Announced total25–40min; correction/targeted phase approximately5min, failed W1
launcher281.990s (~4.7min), post-failure read-only analysis approximately2min;
total approximately12min. No concurrent workload/diagnostic and no automatic retry.

72 unique affected tests passed across r27a-db.xml(21), r27a-unit.xml(37),
r27a-final-db.xml(11), r27a-auth-final.xml(5), with overlaps counted once. Real
PostgreSQL test invokes Fixture.mutation, verifies TOTP state/exact authorization,
processes the real claimed request, observes INCREASE APPLIED, rejects missing
proof/changed payload, proves replay produces one event and unchanged wallet/
position state. Actual AUTH pool checkout/return and six-pool inventory covered;
ordering test keeps limit restoration after all selected risk oracles. Request/
worker rollback/idempotency and general physical cleanup tests reused/run.
Ruff/format 3 affected files passed; mypy src/tests579 files passed.

Initial targeted attempts are preserved: mixed root/infra test argument ordering
produced missing owner-fixture collection errors; running infra tests together
and root tests separately resolved collection without changing production or
shared test setup. New test assertions were corrected to ignore snapshot_at
observation time and use the actual paper_position_projections table. These were
test failures, not trading-runtime failures; subsequent above results are green.
No full regression rerun: changes restricted to harness/fixture contracts and
related affected tests; this does not replace outstanding acceptance/regression.

Source freeze f608b33e5e2d5b8b97bce188a8143c011a5c2adb0fd320f95929ea0436f0e554
(750 files), unchanged after workload. Artifacts under
validation-artifacts/f18-20261027/r27a-w1-20261029, adjacent host/log and
r27a-source-freeze.json. Fresh0058 DB tiewtrade_f18_release_r27a_w1_20261029;
R10 enabled/R22, monitor4, same100owners×20orders,10commands/s,CPU/RAM/workers,
native runner without diagnostic flags. Premeasurement complete actual pool
capacity386, server200/reserved3/other0 -> effective limit197; no gate relaxed.

W1 FAILED shortly after baseline2000 completed. Partial measured price span
10.263383s, offered24/admitted1/completed1, fill1, trading cycles0. Selected
PARTIAL_FILL_RISK_ORACLE(loss0.05) completed; remaining scenarios incomplete.
ScheduledRESET expected100/offered0/applied0/failed0. Restoration receipt null;
AUTH peak checkout0: the corrected restoration path was not reached under load.
Error F18_POSITIVE_REQUEST_REJECTED:None:RISK_PRICE_UNAVAILABLE came from
command execution after intake, not the corrected INCREASE and not a measured
processing-percentile verdict. Two NEW command results carry this rejection.

| Symptom | Evidence | Conclusion | Gap / next decision |
|---|---|---|---|
| Positive NEW rejected for price availability | failure.json, command results026e4092-01ac-4784-8416-02437fdcc2da and84539707-99f2-484f-b29e-082e81b7dd55 | Workload cannot pass its positive-command oracle | Need exact price/read time inside decision to distinguish stale price/lease/snapshot; do not add automatic retry or weaken freshness |
| Publisher commit stalls around rejection | frame3479 commit05:17:38.824338Z ->3480..3482 commit05:17:43.349919Z, gap4.525581s; frame3482 BTC trade05:17:39.546706Z | Source availability under sustained load is not demonstrated | Exact wait location not recorded; cannot attribute whole gap to AUTH/owner locks/host from this alone |
| Long command result transactions | completed_at defaults to transaction time; commits05:17:44.345473Z /45.401640Z versus recorded05:17:38.956752Z /38.913232Z | Stored transaction-start timestamp is not decision/commit time | Do not sum parallel transactions or equate completed_at with actual commit |
| Host paging during same run | host counter deltas: compress13,942,888/decompress13,675,240 pages; swapout527,368/swapin525,754 over281.990s | Severe host memory churn coincides with stalls | Correlation does not establish host as sole cause; stabilize/qualify environment before another acceptance run |

Read-only SQL and derived correlation saved in failure-analysis.json after all
workload processes stopped; no added measurement/workload. All pool documents
finalized with checked_out0, only idle isolated PG/Redis remain. Failed-run path
has no final5s physical-cleanup verdict, full SLA/unack/per-owner quota, processing
percentiles or full financial/resource acceptance; do not claim those pass.

Stop checkpoint reached: one authorized W1 consumed, failure retained; no W2–W4
or automatic rerun. Next needs a bounded environment/source-availability decision
based on these failures before another workload, not another blind R27 tweak.
Do not loosen trading price freshness/safety to mask this failure. Paper remains
Pending Full Validation; V-22/V-23 Pending Dependency; no commit/push/merge.


### Authorized RAM-budget diagnostic — 2026-10-29

Owner requested implementation of the bounded RAM plan: one100x20 setup plus60s
observation, no W1-W4/allocations changed and no repeated diagnostic. Added opt-in
internal --memory-diagnostic-seconds60 to the existing harness and profile_memory
collector. Native dataset/rates/scheduling/R10/R22/monitor4 retained; only observation
cutoff and read-only sampling added. Normal acceptance path remains unchanged.
Collector reads /proc meminfo/vmstat/PSI and Docker API memory/state for parent,
risk, PostgreSQL and Redis, about2s after each collection. Existing publisher
commit evidence reused; no added SQL in financial transactions. Host vm_stat
samples include actual16KiB page size and UTC Unix time. Before/after VM clock
values fall inside corresponding host request bounds (~108/112ms), so no large
clock offset observed. Missing per-container swap/fail counters remain unknown.
Raw cgroup usage includes cache; do not confuse it with anonymous working memory.
VM OOM-kill increments or container OOMKilled/collector errors stop and join work.
A container removed during cleanup is recorded as disappeared, not as zero usage.

Announced15–25min total; actual approximately20min including preparation/tests,
launcher336.695s(~5.6min including setup/60s window/cleanup) and analysis. No other
workload/diagnostic overlapped. 35 targeted tests passed in memory-diag-final-
targeted.xml: byte-unit parsing, container selection/raw cache/unknown counters,
flush/stop, OOM/collector-error cancellation, VM OOM increments, deadline failure
propagation, cutoff join and existing cycle/RESET contracts. Ruff/format3 files
and mypy src/tests581 files passed. No unrelated/full regression rerun: only
opt-in harness observation/lifecycle changed; all acceptance remains outstanding.

Source66ebee7611a412c5a15cc4af44a5ddda1637f0a0f8d383765e72580491a2b9c9
(752files) unchanged after run. Artifacts validation-artifacts/f18-20261027/
memory-diag-20261029, adjacent .memory.jsonl/.log/-host.json/-clock.json,
memory-diag-source-freeze.json (also pins host runner), memory-analysis.json.
Fresh0058 DB tiewtrade_f18_release_memory_diag_20261029; frozen original topology:
app3CPU/1536MiB + risk1CPU/512MiB, PG4CPU/3GiB, Redis1CPU/256MiB; VM observed
MemTotal4,106,604,544bytes (~3.82GiB), physical host8GiB. No allocation changed.

Diagnostic WINDOW_COMPLETE at60.246s (cutoff dispatch/cleanup is not instantaneous),
acceptance_result=false. 549offered/525admitted/completed,0rejected,205fills,
104cancels,108replays,96completedcycles. Pending work cancelled/joined at cutoff;
these counters do NOT meet full acceptance, account for all scheduled future work,
or demonstrate final financial invariants. Scheduled100RESETs were not exercised.
No repetition of the previous price rejection within this short observation.
141memory samples overall/26 within measured input span59.561s. Collector median
0.239s/max2.581s; observations are time intervals, not simultaneous exact snapshots.
Measured price commit gap max0.928597s; no comparison claim of performance improvement
against prior differently instrumented/host-state runs. All pool documents finalized
with checked_out0; only idle isolated PG/Redis remain. No final5s physical-cleanup
acceptance or full SLA/processing-percentile verdict is claimed.

| Layer | Observed evidence | Conclusion / limits |
|---|---|---|
| Docker VM | MemAvailable minimum1893.918MiB overall/1894.328MiB measured; swap used24.238MiB unchanged; measured pswpin/out0/0, OOM-kill delta0 | No guest RAM exhaustion observed over this setup+60s; not a full/endurance capacity guarantee |
| PostgreSQL | Peak raw usage2154.57MiB vs3072MiB cap; peak anonymous397.27MiB; inactive file1543.81MiB | Much of charged memory is cache; no basis to slash PostgreSQL RAM as though raw usage were all unreclaimable working set |
| API/Paper parent | Peak644.44MiB vs1536MiB cap, anonymous621.19MiB | No observed container limit pressure/OOM |
| Risk / Redis | Peak59.99/17.09MiB vs512/256MiB caps; no observed OOMKilled | No observed container limit pressure |
| macOS host | Whole-run compress/decompress13,849,362/13,608,385 pages; swapin/out540,372/470,869. Measured slice compress/decompress1,170,195/1,154,726; swapin7353, swapout0 | Host memory churn remains; measured slice had no new swapout. Traffic counters are not resident RAM requirements and do not establish the cause of the previous failure |

Container peak columns occur at potentially different times: do not sum their
peaks as simultaneous consumption. The guest still had substantial reclaimable/
available RAM while host memory churn occurred. This disproves the simple claim
that summed container caps alone show actual RAM exhaustion; it does NOT prove
host paging caused the previous4.53s source gap. The failure was not reproduced,
and exact previous decision-time/source-wait correlation is still unavailable.

#### One proposed resource experiment (not approved/applied)

If continuing on this8GiB host, propose changing ONLY Docker Desktop VM Memory to
3072MiB, retaining all CPU and existing per-container limits/configurations.
Rationale: current guest availability margin supports investigating a smaller VM
budget to leave more host headroom, rather than reducing PostgreSQL's observed
cache/working-set budget blindly. This is a hypothesis/diagnostic allocation,
not a proven production profile or assurance100-wallet W1-W3 will pass. Lower VM
memory may increase reclaim/I/O or guest swap/OOM and worsen source cadence.
Before changing, record the actual Docker Desktop Memory control value (the local
settings-store contains no explicit memory override); preserve that exact previous
value for rollback. Do not assume MemTotal equals the UI setting.

A future approved trial would reuse the SAME sampler/instrumentation, dataset,
60s window and financial rules, changing only this VM memory budget. Capture a new
source/config manifest; compare aligned setup/measurement phases and normalize
host counter traffic by elapsed time. Stop on rejection/timeout/OOM/collector
failure; roll back the VM setting if guest memory pressure/source behavior worsens.
No automatic second trial or W1 follows. Do not infer causality merely from an
improved one-minute run. Changing VM allocation requires a new approved amendment
before execution; current allocations remain untouched.

Stop checkpoint reached. No W1-W4 or other diagnostic started. Outcome: guest
memory sufficient in the observed window; host pressure persists; previous failure
cause still not proven. Paper Pending Full Validation, V22/V23 Pending Dependency.
No commit/push/merge.


### VM3072MiB experiment authorized; awaiting UI setting — 2026-10-29

Owner เริ่มทำ authorizes the one proposed VM-memory experiment above. Updated
plan/validation before any allocation changes; source/sampler unchanged. Prepared
runner/run_memory_diag_3g_host.py with a distinct fresh DB/output name; not invoked.
No additional tests needed yet: previous35/static evidence still applies unchanged.

Read-only preflight: only isolated idle PG/Redis running; installed docker desktop
CLI has no settings/resource command. Native UI connection failed twice with
Sky Computer Use native pipe startup failed; inventory reports no apps/browsers.
The settings-store had no explicit memory override in the preceding investigation,
and actual prior UI value remains unverified. Do not invent a settings key/default
or assume VM MemTotal is the UI control value. No Docker settings/configurations
changed, no restart, no fresh diagnostic/DB/workload launched in this turn.

Concrete next action: owner records current Docker Desktop Settings > Resources >
Advanced Memory value, changes only Memory to3GiB (3072MiB), applies/restarts and
reports old/new values. Then verify VM total/per-container limits and resume the
one already-authorized diagnostic without asking for approval again. Prior exact
control value is necessary for the authorized rollback. Estimated15-25min for full
trial after UI is available; this preflight took about3min, external wait excluded.
Paper remains Pending Full Validation; no code/financial change/commit/push/merge.


### VM3GiB single diagnostic completed — 2026-10-29

Owner screenshot confirmed previous UI Memory4.0GiB, then owner reported แก้แล้ว
following3GiB instructions. Verified Docker effective MemTotal3,043,373,056bytes
(~2.83GiB), matching reduced VM budget rather than equating UI value with guest
usable memory. Restart left PG/Redis stopped; restarted ONLY the two isolated
release dependencies, preserving data/volumes. No other running workload. Actual
HostConfig PG4CPU/3GiB and Redis1CPU/256MiB unchanged; app/risk remain3CPU/1536MiB
and1CPU/512MiB. PG Docker stats effective limit may be clamped by smaller VM;
this does not mean its configured container cap was changed.

Announced10–15min including setup/analysis; actual approximately6min. Native
launcher205.277s (~3.4min, includes setup/60s observation/cleanup). One diagnostic
only, no concurrent diagnostic/workload, retries, W1-W4 or code changes. Existing
35 sampler/lifecycle tests and ruff/format/mypy evidence reused: source hash
66ebee7611a412c5a15cc4af44a5ddda1637f0a0f8d383765e72580491a2b9c9
(752files) matches preceding4GiB run and remains unchanged. Fresh0058DB
`tiewtrade_f18_release_memory_diag_3g_20261029`; manifest retains R10/R22, monitor4,
100x20,10commands/s, all financial gates; connection budget197 unchanged.

Artifacts validation-artifacts/f18-20261027/memory-diag-3g-20261029 (diagnostic.json,
memory-comparison.json), adjacent .memory.jsonl/.log/-host.json/-clock.json and
memory-diag-3g-source-freeze.json (host runner pinned). Host/VM clocks within
pre/post observation bounds (~163/149ms). Full sampled data retained; no outlier
or unacknowledged-input removal. Comparison uses the measured price-input span
for each run, normalizes host cumulative counters by host sample elapsed time,
and treats collection periods as intervals rather than instantaneous snapshots.

WINDOW_COMPLETE60.078s,acceptance_result=false;566offered/547admitted/completed,
0rejected,215fills,108cancels,112replays,101completedcycles. In-flight tasks joined
at planned cutoff, not treated as completed financial acceptance. Scheduled100
RESETs not exercised. All pool documents finalized with checked_out0; only idle
PG/Redis remain. No final5s physical-cleanup or full risk SLA/processing-percentile
acceptance asserted from this diagnostic.

| Measured observation | Prior4GiB UI run | New3GiB UI run |
|---|---:|---:|
| VM minimum MemAvailable |1894.33MiB|1009.4MiB|
| VM swap-in / swap-out delta |0 /0|0 /0|
| VM OOM-kill delta |0|0|
| VM PSI some stall fraction |0.0842%|0.0849%|
| VM PSI full stall fraction |0.0689%|0.0714%|
| Host compressions pages/s |20748.59|5907.66|
| Host decompressions pages/s |20474.31|5601.35|
| Host swap-in pages/s |130.38|0.21|
| Host swap-out pages/s |0|0|
| Max measured price commit gap |0.928597s|0.376377s|

Host compression/decompression rates were about72%/73% lower in these samples.
Guest PSI is essentially similar (small numeric increases shown, not hidden),
no new guest swap/OOM/rejection, and source gap did not worsen; no rollback trigger
established in this observation. Keep the owner-selected3GiB diagnostic setting;
rollback value remains UI4GiB. This is not a production/default change in repo.

Causality not proven: Docker restart/cold-cache state differs. Guest major faults
were525 across setup+measurement versus10 previously, but0 in new measured slice;
these are not guest swap-ins. This restart effect and different host state prevent
attributing all observed improvements to VM memory alone. Neither short run
reproduced the earlier4.53s source failure. Do not call W1 or100-wallet endurance
passed from higher partial counters/lower publication gaps.

Stop checkpoint reached. A3GiB diagnostic profile is feasible over the observed
window, with about1GiB guest available memory and reduced host churn; long-run
risk/processing SLA, complete cycles, RESETs and W1-W4 remain unproven. No next
trial/full acceptance launched automatically. Paper Pending Full Validation,
V22/V23 Pending Dependency; no commit/push/merge.


### Full W1 on approved VM3GiB — PASSED, 2026-10-29

Owner เริ่มทำ authorized one native full W1 after VM3GiB diagnostic. Plan/validation
updated before execution; no code, financial rules, CPU/per-container RAM/pools,
monitor4/R10/R22 or numeric gates changed. VM UI3GiB/effective3,043,373,056bytes;
only idle isolated PG/Redis present preflight. Fresh0058 DB
`tiewtrade_f18_release_w1_vm3g_20261029`. Native W1 invocation, no diagnostic flags
or cutoff (memory_diagnostic_seconds=null); one workload only, no concurrent
workload/diagnostic, retries or W2-W4. Existing affected tests/static reused because
source unchanged; no unnecessary rerun/full-regression claim.

Source66ebee7611a412c5a15cc4af44a5ddda1637f0a0f8d383765e72580491a2b9c9
(752files), unchanged after run. Artifacts validation-artifacts/f18-20261027/
w1-vm3g-20261029 (manifest.json/result.json/risk-late-inputs.jsonl/complete input,
ACK, cycle, RESET and pool evidence), adjacent log/host JSON and
w1-vm3g-source-freeze.json pinning host runner. Frozen10workers/100owners x20baseline
orders,10commands/s/600s; effective connection budget197. Previous Failed runs
remain Failed; this is new evidence for this source/configuration only.

Announced15–20min total; actual approximately14min including setup/verification.
Host launcher752.605s (~12.5min); measured elapsed608.265s, within600..660s.
Book inputs6083 >=6000 required. Result statusPASSED/acceptance_result=true.

- All6000commands offered/admitted/completed;0rejected.1200/1200cycles completed,
  fills2400,cancels1200,replays1200.2000baseline orders completed before measurement.
- ScheduledRESET expected/offered/applied100/100/100,failed0; all current60s bounds
  passed. Selectedfirstcycle normal10.002s/recovery20.806s,all20reseeds and all3
  risk scenarios complete:partial-fill(loss0.05),breach/stop/reset/reseed,
  exactcorrection/replay. Post-oracle authorized INCREASE restoration APPLIED,
  request15ab6361-cb56-4495-acfd-0f6fcb706690,recorded separately fromscheduledRESETs.
- Processingp950.247938750s,p990.359879334s,max1.955593334s;passesR25p95<=0.5s/
  p99<=1s. Max is retained, not treated as a p99 hard bound or excluded.
- Risk expected/acknowledged1,277,505/1,277,505,unacknowledged0,clockerrors0.
  Everyowner and global99.9%<=3s servicegate passed. Threepriceinputs for oneowner
  took3.044845s; allthree retained in risk-late-inputs.jsonl. No >5s hardmiss.
  Thatowner3/12,775service misses remains below0.1%; do not claim everyinput<=3s.
 1s targetmisses8214 retained;1s is a target underapprovedR25,not Paper hardgate.
- Global and all owner financial invariants passed:orders5620,fills2401,
  cancels1220,expectedpendingbaseline dispatch2000;invalidreservations0,
  invalidpositions0,unlinkedfills0,duplicatedfilleffects0,wrongmode0,inputlag6<=20.
- Resource assertions passed:peakprocessRSS97,406,976bytes,peakconnections56<=197,
  endlockwaits0. Allpoolsreturned;post-disposalphysicalcleanup passed in0.0441s,
  remainingclients[]. Workerexitgates passed;onlyidleisolatedPG/Redisremain.

W1 is Passed for this final source and approved VM3GiB envelope. This does not
complete V21/Paper/F18: W2/W3/W4 applicability, remaining regression/static/final
review/requiredCI/manual evidence must still be reconciled for the final candidate.
V22/V23 remain Pending Dependency. No subsequent workload launched automatically,
no commit/push/merge. Keep approved criteria and historical failures intact.


### W2 VM3GiB — FAILED throughput/total deadline, 2026-10-29

Owner เริ่มทำ authorized one W2 after W1Passed. Plan/validation recorded the
unchanged VM3GiB source/config before launch. Fresh0058DB
`tiewtrade_f18_release_w2_vm3g_20261029`,100owners x20baseline,100commands/s,
300s plus existing60s total drain. Native invocation; no diagnostic flags/cutoff,
concurrent workload/diagnostic, source changes or retries. Original app/risk CPU/
RAM/pools,R10/R22,monitor4 and all R25/R26/R27-A gates unchanged. Source
66ebee7611a412c5a15cc4af44a5ddda1637f0a0f8d383765e72580491a2b9c9
(752files) matches W1 and remains unchanged. No tests/static rerun justified by
unchanged code. W1 evidence remains valid; W2 failure does not erase W1Passed.

Announced10–15min total; actual approximately10min including preparation/analysis.
Launcher518.282s (~8.6min includes setup, failed workload and controlled cleanup).
Artifacts validation-artifacts/f18-20261027/w2-vm3g-20261029, adjacent host/log and
w2-vm3g-source-freeze.json pinning runner. Canonical failed-run verdict is
`deadline-stop.json`; native result.json was not reached and is not fabricated.

Baseline2000 completed. At first observed elapsed361.100s (first-cycle epoch,
approximately measurement start), only1581/6000cycles completed. The current
scheduler enforces each cycle's deadline but evaluates overall elapsed only after
all cycles return, so it would otherwise keep working beyond the360s passing
bound. Stop-on-impossible-pass rule required external controlled interruption.
At signal dispatch370.238s,1621cycles completed; SIGINT allowed asyncio finally
cleanup rather than terminating containers abruptly. Final1622completed/100
CancelledError cycle contexts, exit130 (expected controlled interruption).
Do not credit work after the360s bound as meeting W2; passing was already impossible
at the first observation. This is a failed throughput/deadline gate, not an
unexpected KeyboardInterrupt application failure.

ScheduledRESET expected/offered/applied100/100/100,failed0. Selectedfirstcycle
completed with normal18.062s/recovery34.357s. Completed ordinary cycles had
normal-time median21.455s/max33.681s. W2's intended per-owner interval is5s
(100owners x5commands /100commands/s); owner cycles execute serially, so observed
cycle durations produce overdue schedules/backlog. Do not sum parallel cycle times
or infer exact offered/completed command rates from complete-cycle counts alone:
partial cycles, replay operations and scenario operations differ. Exact end
counters were not persisted by native cancellation; no claimed full30000-command
completion or calculated processing/risk SLA verdict.

This evidence identifies capacity/deadline failure under W2, but does not separate
queue waiting, owner/publication locks, API intake and worker processing. No proven
root cause attributing it to VM RAM, risk math or an authorization defect. No
threshold/load/financial rule changed. Existing host samples/raw transaction and
cycle evidence retained for bounded follow-up analysis; no new diagnostic added.
A future harness total-deadline guard could make the stop automatic, but is not
implemented in this attempt and must not change rates/financial deadlines.

All pool evidence finalized with checked_out0; only idle isolated PG/Redis remain.
No post-disposal5s physical-cleanup verdict, overflow/recovery result, final full
financial invariants, full SLA/unack coverage, resource/p95/p99 acceptance obtained.
These stay unproven; partial RESET/selected progress is not a substitute. W2 is
FAILED/Pending Full Validation, W3/W4 not started. W1 Passed unchanged; V22/V23
Pending Dependency. Stop checkpoint reached; no rerun/optimization/VM rollback
based on unsupported memory causality, no commit/push/merge.


### Bounded W2 evidence analysis — insufficient stage correlation, 2026-10-29

Owner chose keeping100commands/s and explicitly requested the <=15min evidence-
only analysis plan. Started08:27:01UTC; completed approximately08:33UTC (~6min,
below15min). No code/resource changes, Docker startup, tests/static, workloads or
new diagnostics. Only this checkpoint updated. Source read/hash recomputation
confirms66ebee7611a412c5a15cc4af44a5ddda1637f0a0f8d383765e72580491a2b9c9
matches the W2 manifest (752files). VM3GiB,100owners x20baseline,100commands/s,
300s+60s,R10/R22,monitor4,no diagnostic flags all match the existing evidence.

Docker daemon was unavailable at the first read-only DB attempt (cannot connect
at the existing desktop socket). No SQL executed, and no DB/daemon was started
silently. Thus individual durable owner/request/command joins and action-specific
backlog/commit-time samples could not be read. This blocks those portions of the
plan; do not substitute uncorrelated transaction records as command timelines.

CORRECTION to the preceding W2 entry: native `failure.json` DOES contain counters,
written07:24:55.225019UTC on CancelledError. It was missed in the initial W2 summary.
It records offered8429/admitted8329/completed8329/rejected0,fills3306,cancels1662,
replays1678,cycles1622. Three selected risk scenarios complete, all100scheduled
RESETs APPLIED, restoration requestb6b36290-c9d2-485f-8bee-541eecbcff5f present.
Baseline20/20 log proves2000setup orders separately. These are logical harness
operation counters (including replay), not distinct immutable DB request counts.
In Fixture.new, admitted increments after request completion; it is not an exact
API-admission commit timestamp/count. Pending100cyclecontexts were cancelled.
Do not infer NEW-row counts or queue depth by subtracting those counters.

Cycle-timing reconstruction below uses the first cycle's wall timestamp as origin,
nominal scheduler due times and logged durations. It is a cycle-context proxy,
not durable order commit time or DB queue occupancy. Inclusive due-time boundaries
are nominal; no acceptance verdict is recalculated from these estimates.

| Seconds | Nominal due cycles | Started contexts | Completed contexts | Due not started | Started not complete |
|---:|---:|---:|---:|---:|---:|
|60|1201|302|202|899|100|
|120|2401|599|499|1802|100|
|180|3601|888|788|2713|100|
|240|4801|1170|1070|3631|100|
|300|6000|1419|1319|4581|100|
|360|6000|1676|1576|4324|100|

Nominal owner interval=100owners x5commands /100commands/s=5s. Existing scheduler
awaits each owner's whole cycle before starting its next cycle; delayed cycles
therefore delay offering subsequent commands. Ordinary completed cycles1621 had
median21.455374s,max33.681371s; start-lag median122.575s/max274.154s relative to
nominal due times. This establishes growing closed-loop schedule backlog and that
100commands/s is a target, not an achieved offered rate. It does NOT establish
whether API work, queueing, polling, owner/publication locks or execution dominates.
No parallel durations were summed as one item's latency.

Five slowest and five median ordinary CYCLES (same five-command mix, excluding
selected recovery) were inspected as proxies. They are NOT the requested same-
command-type samples: individual command evidence still requires the DB join.

| Cohort | Owner | Cycle | Normal seconds | Nominal start-lag seconds |
|---|---|---:|---:|---:|
|slow|8d4e482d-6da4-4bd7-aa7a-d42a6d68b2fb|8|33.681371|119.495|
|slow|7f97aea6-4078-430e-9675-820a1c6fdc14|13|33.582786|228.779|
|slow|205a834d-daf1-4236-b524-6ac415b4e270|13|33.199815|220.184|
|slow|2f1ca2a1-2882-42da-be92-02960ff8a784|12|31.150235|194.543|
|slow|bc5f597a-42e2-4995-ac5f-45be6ab03690|11|30.919831|186.502|
|median|d1724392-77ad-497a-8cec-340690944f2e|13|21.452218|214.147|
|median|87fd28e6-22e2-4bb4-8028-ed335d9ce57f|11|21.452714|177.677|
|median|ddca273f-f9dc-4a61-93d0-5e5d62804db8|11|21.455374|181.060|
|median|8d5e466a-6acd-4bab-a178-976fc864eee6|8|21.460748|128.070|
|median|3fa90474-78c7-4b92-aed8-664f9cec3729|0|21.461911|0.001|

| Symptom | Evidence | Proven conclusion | Missing evidence |
|---|---|---|---|
|W2 total deadline failed|deadline-stop.json,1622complete/6000target,100cancelled|Target workflow capacity not demonstrated|Stage responsible for cycle duration|
|Growing delayed offers|scheduler awaits owner cycle; table above|Backlog exists in closed-loop harness scheduling|Not equivalent to server queue/lock wait|
|Transactions shorter than whole cycles|21082 processing-tagged worker records, fields only started/finished/seconds; unfiltered median0.11243s,p950.35362s,p990.47995s|Records span setup+measurement and lack identities/stage labels|Cannot subtract/sum these into per-command queue time or claim W2 p95 passed|
|Risk checks appear at several layers|API policy,manual intake transfer,order worker; matching final financial fence|Separate commits/fresh publication can require revalidation|No proof one repeated read dominates; no safe deletion identified|
|No command-specific10-sample cohort|DB daemon unavailable; cycle/risk ACK logs lack linked request/command IDs|Individual stages/action backlog not resolved|Durable request/result/command joins and process-start/lock timing|

Caller review: request_worker already reuses prechecked policy within the same
manual_transfer transaction. API→queued transfer→order execution are independent
transactions and state may change between them; removing checks would introduce
TOCTOU/safety risk. Matching's preview/final execution_context rechecks follow
publication/fence boundaries; owner locking alone does not pin new public prices.
No evidence supports changing worker count, claim budget, retries or financial
fences. No implementation fix is proposed as proven from this analysis.

Outcome: INSUFFICIENT EVIDENCE, specific next step is existing-data retrieval,
not another blind workload. Once Docker/isolated DB is available, first read only
`tiewtrade_f18_release_w2_vm3g_20261029` and join paper_order_requests ->
paper_order_request_results.command_id -> paper_order_commands ->
paper_order_command_results using owner/episode identities. Classify NEW/CANCEL
and NEW side/type; distinguish setup/scenario/trading via run/owner/order identities.
Use pg_xact_commit_timestamp(xmin) for intake/transfer/result commits where retained;
NULLs remain missing. completed_at/recorded_at semantics must be checked individually,
not presumed to equal commit. Select5slowest/5median within one command class.
Compare intake-commit→transfer-commit and transfer-commit→terminal-commit as combined
queue+processing spans; these alone do not separate queue from lock/processing.
Historical completed dispatch claims do not retain complete start/wait timelines.
This retrieval needs no new W2 execution.

If that old-data read still cannot separate the dominant phase, proposal for ONE
future approved measurement: existing W2dataset/rates/resources for60s with the
same financial rules, instrument only five fixed non-selected owners' first two
cycles (50logical commands inclreplays). Capture owner/request/command/cycle/attempt
IDs, UTC plus monotonic start/end for API check/intake commit,manual claim/process
commit and order claim/process commit, owner-lock/fence wait boundaries and commit/
rollback outcomes. Reuse existing harness telemetry wrappers; no extra SQL in
transactions, SQL parameters/secrets or business decisions logged. Cap1000trace
events; truncation/missing terminal outcomes must be explicit and make attribution
incomplete, not silently dropped. Capture setup/clock correlation separately.
One set only; tests must first verify identity mapping/clock units/cancellation/
rollback recording. Do not start this measurement automatically; read old DB first.

Stop reached early rather than spending the remaining budget on unsupported code
hypotheses. W1Passed remains valid; W2Failed, W3/W4notstarted, Paper/F18 Pending
Full Validation and V22/V23 Pending Dependency. No code/resources/tests/workload/
CI/commit/push/merge changes in this analysis.


### W2 existing-DB stage correlation — 2026-10-29

Owner เริ่มทำ after the read-only DB follow-up. Started08:34:30UTC; completed
approximately08:44UTC (~10min, within15min). Initial Docker socket still unavailable;
used installed `docker desktop start` and started ONLY the existing isolated PG
container to perform the already-requested read. No Redis/Paper/risk workers or
workload started, no CPU/RAM/settings changed (VM effective3,043,373,056bytes).
Only PG remains running. All analytical SQL used BEGIN READ ONLY and bounded
statement_timeout10–20s. No tests/static/code/new diagnostics/other doc updates.

Read existing`tiewtrade_f18_release_w2_vm3g_20261029`,track_commit_timestamp=on.
Source/runtime unchanged from preceding hash check. Request/result/command joins
use immutable IDs and owner; composite schema FKs also bind episode/order/action.
All existing8758request,8778command,8758request-result and8769command-result rows
retain commit timestamps (NULL existing-row commits0). No request wrong mode.
2000request rows committed before measurement;6758at/after measurement start.
Measured selectedowner81rows excluded from ordinary timing cohorts, leaving6677
non-selected request rows across99owners.20commands outside manual-inbox links are
CANCEL for selectedowner3ad51e38-52ce-4b0c-9815-633f2c6a01cd, matching the separate
20-target stop scenario, not ordinary manual-request cohort. These counts do not
include logical replay as a new durable request and do not replace logical counters.

Timestamp semantics verified from migrations: command.requested_at and command-
result.completed_at default now() (transaction START, not completion); manual-
result.completed_at defaults clock_timestamp(). For these joins, use command
requested_at as transfer-transaction start, command-result completed_at as execution-
transaction start; pg_xact_commit_timestamp(xmin) for intake/transfer/terminal
commits. Transfer-result and command commits equal for every linked command.
All analysed phase differences nonnegative. These START timestamps locate the
transaction boundary only, not the time a lock is acquired or a decision made.

Definitions: manual-wait=intake commit→transfer transaction start; manual-tx=
transfer start→transfer commit; engine-wait=command commit→execution transaction
start; engine-tx=execution start→terminal command commit. Engine-wait includes
scheduling/scanning/claim/pool effects before the processing transaction; it is
NOT measured owner/publication-lock wait. Owner financial lock occurs after the
execution transaction starts. Terminal command result is NOT the fill timestamp;
market fills can commit in subsequent matching transactions.

| Ordinary command cohort | Rows / terminal rows | Manual wait median | Manual tx median | Engine wait median /p95 | Engine tx median | Intake→terminal median |
|---|---:|---:|---:|---:|---:|---:|
|CANCEL|1662/1654|0.068161s|0.017076s|4.940656s/6.014665s|0.052225s|5.094687s|
|NEW BUY MARKET|1704/1704|0.062670s|0.125547s|0.134189s/0.904571s|0.244107s|0.637680s|
|NEW SELL LIMIT|1668/1668|0.069016s|0.041414s|0.152813s/0.814169s|0.140112s|0.443122s|
|NEW SELL MARKET|1643/1642|0.055559s|0.042214s|0.067736s/4.514960s|0.139476s|0.343345s|

No rejection in these cohorts.8CANCEL and1SELL MARKET had no terminal command
result at stop; preserved as pending, not dropped from row counts or called passed.
New BUY/SELL MARKET terminal-command→last-FILL commit median5.598897s/5.513090s,
p956.575204s/6.467273s,max7.908413s/7.485123s.1679BUY and1616SELL have FILL evidence;
25BUY/27SELL lack FILL at stop. Last FILL does not alone prove fully-filled quantity;
these are event timing observations, not final financial validation. Do not sum
cohort medians to claim an exact decomposition of the21.455s cycle median.

Durable pending-stage counts at relative cycle-start times, non-selected owners
only, reconstructed with commit timestamps. These are actual committed-request
stages, distinct from the thousands of cycles not yet offered by the harness:

|Seconds|CANCEL intake /pending transfer /pending terminal|NEW intake /pending transfer /pending terminal|
|---:|---:|---:|
|60|297/0/44|841/0/5|
|120|576/1/39|1704/2/4|
|180|842/1/32|2545/1/6|
|240|1111/1/25|3359/2/10|
|300|1365/0/20|4119/5/16|
|360|1622/0/26|4886/1/8|

Ten exact same-type CANCEL samples selected by intake→terminal duration:
5slowest and5around median, excluding pending rows but reporting them above.
Each request_id resolves exact owner+command via the retained DB join; full IDs
below permit reproduction. Times are engine-wait/engine-tx/total seconds.

|Cohort|Request ID|Command ID|Engine wait /tx /total|
|---|---|---|---:|
|slow|d350df54-1820-420a-b0ce-dfa3bb173011|4fcc35ac-4988-46d2-93b4-6e64af1ab19c|6.741516/0.069383/7.132292|
|slow|8d2146ad-2557-46d3-8aaf-6bdd065d2f0a|530bbeb4-2014-4846-954a-c972fd8f5b4d|6.781738/0.041176/7.099096|
|slow|07703eed-8c6b-438a-abd2-03d0da886da6|7a840a91-376e-47c8-bcb4-e1b298523674|6.778494/0.093280/7.043492|
|slow|1e2391be-1ed3-46c9-99a7-7a9d26cf6af7|7e6a396f-952e-47a0-aaa4-e7253b6ad72f|6.529607/0.054648/6.675722|
|slow|75ad4cee-dd90-421a-90e5-5d6d7f39e189|43534dd8-786f-4060-bdbf-8c1f5e83a0c2|6.555982/0.032830/6.651499|
|median|639c36f0-912c-402e-a097-51a0b8210d8a|471fb596-3c88-4ea3-9393-074030406aee|4.913171/0.056777/5.092481|
|median|57c2452d-423a-4aeb-90d6-e5aeade45c6f|71e873f4-bf50-468e-be30-6b0d475f5648|5.003308/0.040650/5.094342|
|median|612b3626-1185-44ef-980d-c12d7cd4afcb|1f9c6927-7723-482d-b68d-6f0eb674a61d|4.949369/0.026631/5.095032|
|median|8f672e5e-a3d2-4dd2-9b85-52625f853fc3|d574cc79-d3f9-4635-9853-dd73acec1b9c|4.816522/0.074127/5.095583|
|median|cab5799e-deec-4f1f-934e-9577a1cc6308|63585307-a2d6-4a0d-b721-4d4b16494217|4.900756/0.069589/5.095848|

|Symptom|Evidence|Conclusion|Remaining gap|
|---|---|---|---|
|CANCEL takes seconds despite short processing|All1654terminalCANCEL plus10samples|Primary observed CANCEL delay is before execution transaction|Scan/claim/pool/owner-availability components within that wait|
|MARKET command succeeds before fill appears|BUY/SELL event-commit joins,~5.5s medians|Next matching scheduling is another large wait relevant to full cycles|Which dispatch rounds/candidates occupied that interval|
|Manual inbox has little backlog|1–5pending transfers at sample cuts;medianwait55–69ms|No evidence manual-transfer stage dominates typical CANCEL/SELL latency|BUY policy cost exists but does not explain CANCEL5s wait|
|Current dispatch alternates R8/R10 and one claim perphase|matching_round_modes,run_paper_order_round,routing SQL|Selection/round budget/active polls are plausible causes|No historical selected/rejected candidate or claim-attempt timings; cannot pick a new budget/lane as proven|

Caller review: R10 priority applies guarded NEW behind same-pair ACTIVE head; a
CANCEL disables that preference. R8 ranks one eligible head perowner by due time;
processing includes existing active orders, while CANCEL and MARKET completion
need worker service. But final dispatch rows cannot reconstruct historical FIFO
heads/candidate choices. finish_claim resets attempts=0 and rewrites due time,
so current attempts0 is NOT proof that no retries or skips occurred. Manual
attempts1 is retained for all three inspected cohorts, but does not count failed
try-lock probes. No claim that a specific lock or policy check caused these waits.

Decision: evidence sufficient to LOCALIZE a dispatch/matching scheduling delay,
not sufficient to select a safe implementation fix. Do not remove financial risk
checks or guess a larger batch/worker count. Current evidence does not establish
that prioritizing CANCEL alone would achieve100commands/s or bring cycles to5s.
No code/amendment implementing a new selector is proposed as proven.

Smallest proposed next measurement (not started/authorized here): ONE60s existing
W2 diagnostic with same100x20/rates/VM3GiB/CPU/pools/financial gates. Focus only on
Paper dispatch round time: manual phase,order scan,claim attempt,process-through-
commit and maintenance/sleep. Aggregate perworker once/s during measured window
(<=600records for10workers); distinguish processing already-active versus pending
commands using the existing loaded command result_state, no addedSQL. Count
hints,claimNone,successfulclaims,processed/deferred; claimNone remains unknown-
reason unless existing code exposes its reason. Trace five predetermined ordinary
owners' first cycle with owner/request/command/attempt IDs and monotonic/UTC phase
boundaries (<=1000detail events; explicit truncation -> incomplete attribution).
Capture setup as separate summaries; do not print SQL parameters/secrets. Reuse
existing telemetry and60s cutoff/cleanup. Test mapping/phase accounting/cancel-
join/failure propagation before one run. Keep monetary logic untouched, stop on
failure and do not repeat automatically. Output should distinguish scan/claim
contention versus active-poll work versus useful command processing before choosing
ONE optimization. No such instrumentation, tests or workload executed this turn.

No remaining DB-access blocker; Docker/PG are now available. W1Passed unchanged,
W2Failed/overflow not reached, W3/W4notstarted, F18/Paper Pending Full Validation,
V22/V23 Pending Dependency. No resources, code, thresholds, CI, Git or other spec
status changed. Stop this analysis without expanding into implementation.


### One bounded W2 dispatch timeline completed — 2026-10-29

Owner เริ่มทำ authorized the proposed dispatch/matching timeline. Implemented
opt-in test-harness observation only in profile_dispatch_timing.py and the existing
profile CLI/worker launcher. No production code, SQL, selectors, claim budgets,
worker count, resources or financial rules changed. Existing loaded command
result_state classifies ACTIVE/PENDING; CANCEL has its own tag. Hooks wrap existing
calls and _begin, observing commit/rollback after original context exits. Reuse
existing with_publisher failure supervision and60s diagnostic cancellation/join.
Normal acceptance defaults remain tracing-off; internal dispatch diagnostic is
W2-only, cannot be combined with memory diagnostic. Five fixed ordinary owners,
first-cycle correlation performed offline rather than adding queries to workers.
One record/occupiedworker-second, bounded tail/setup/closed summaries,100details
perPaperworker (<=1000total); truncation makes attribution incomplete and stops.
No SQL parameters, money payloads or secrets logged. Round/call/transaction spans
overlap by design and must not be added as disjoint work.

Announced15–25min; warned during analysis that final correlation would take total
25–28min. Actual approximately28min (08:51–09:19UTC), including implementation,
checks, one launcher340.985s (~5.7min setup+measurement+cleanup), analysis. Initial
unit assertions accidentally captured pre-patch call references and mypy found
fixture attributes/non-reexported test imports; corrected those harness/tests and
retained failed XMLs. Final44 targeted tests passed (35 existing diagnostic/cycle/
RESET contracts plus9 dispatch tests), final dispatch9rerun passed after test-name
lookup/type corrections. Coverage includes IDs/secret exclusion, explicit detail
cap, real PostgreSQL+existing telemetry commit/rollback and pool return, collector
failure/cancel join, wrapper restoration, ACTIVE/PENDING classification and normal
CLI tracing-disabled. Ruff/format3files passed, mypy src/tests583files passed.
No full regression: only opt-in harness changed, business/runtime financial callers
unchanged. W1 runtime behavior and prior safety evidence remain usable by dependency/
contract assessment; do not relabel its old source hash as this new one.

Frozen diagnostic sourcefe3ca6ca2aae2e05aa4e148f294728fce60617f6e4dca2d214a0250915d0fdbb
(754files), unchanged after run. Artifacts validation-artifacts/f18-20261027/
dispatch-trace-20261029 (dispatch-analysis.json,first-cycle-correlation.json,
10worker .dispatch.jsonl,manifest/diagnostic and complete native evidence), adjacent
host/log/clock and dispatch-trace-source-freeze.json pinning runner. Fresh0058DB
`tiewtrade_f18_release_dispatch_trace_20261029`,same VM3GiB/R10/R22/monitor4/
CPU/RAM/pools,100owners x20baseline,100commands/s. Redis restarted as the existing
fixture dependency; no parallel workload/diagnostic or automatic repetition.

WINDOW_COMPLETE,elapsed61.008s including cancellation/join at60s cutoff;
acceptance_result=false. Offered840/admitted747/completed745/rejected0,99cycles.
This is neither W2 acceptance nor a comparative speed claim against the differently
instrumented full W2.100scheduledRESETs not exercised and final financial/risk/
p95/p99/resource acceptance not reached.10SETUP_SUMMARY,593SECOND,10TAIL,
654DETAIL,10CLOSED records; everyworker closed,truncated=false,max90details/worker.
Unused seconds need not emit empty records; phase counts are observations, not proof
of complete full-load timing coverage. Tail keeps transactions completing after
cutoff separate. All pool docs finalized/checked_out0; only isolated idlePG/Redis
remain; no final5s physical-cleanup acceptance claimed.

Offline UUID5(run/owner/cycle0/order-label) correlation joined actual order IDs to
immutable DB request/command IDs for all five sampled ordinary owners.20expected
unique first-cycle commands all present/traced (25logicalcommands include replays),
254detail records in that first-cycle subset. It includes repeated claims/ACTIVE
processing of those command IDs where applicable. Other owner ACTIVE anchors can
process a sampled order's fill, so anchor-command IDs alone do not identify every
financial effect. No new SQL was introduced during measurement.327detailed
transaction observations were COMMIT; this is only the sampled subset, not proof
all transactions committed or no rollback elsewhere.

Worker-time totals below include bounded tail. They sum across ten concurrent
workers and are NOT a single-request latency or CPU profile. Use either call or
transaction envelopes for a comparison, not their sum.

|Observed phase|Count|Worker-seconds|Mean seconds|
|---|---:|---:|---:|
|Manual round call|1543|103.443|0.067040|
|Order round call|1543|455.428|0.295157|
|Loop gap/sleep|1542|40.879|0.026510|
|Order scan transaction|1543|25.141|0.016293|
|Order claim transaction|2768|39.430|0.014245|
|Order process ACTIVE transaction|895|204.726|0.228744|
|Order process PENDING transaction|510|152.207|0.298445|
|Order process CANCEL transaction|138|18.397|0.133309|
|Maintenance transaction envelope|1542|13.784|0.008939|

Order scan function alone mean0.010117s;30860hints observed.2768orderclaim calls
had1543successful/1225None (None reason unknown, not assumed owner-lock conflict).
Manual1544scans/3299hints,1031claims/662successful/369None. Round outcomes record
1523orderprocessed/19deferred,662manualprocessed/0deferred; differences from1543
process calls include boundaries/cancellation, not hidden successes. Deferred
reason is not recorded peraggregate and must not be invented.

|Symptom|Evidence|Conclusion|Remaining gap /next action|
|---|---|---|---|
|Seconds before CANCEL/fill in old W2|Prior durable joins|Need more order worker service|This run isolates service cost, not historical claim causes|
|Order round occupies most observed worker-time|455s versusmanual103s/loop41s|Order side is the larger measured envelope|Not proof scan/priority alone is root cause|
|Scan and claim smaller than processing|Scan25s,claim39s vsprocessing375s|Do not start by rewriting scan or guessing batch2 as a complete fix|No statement-level CPU/I/O/lock split inside processing|
|ACTIVE58.0% of1543process calls and54.5% ofprocessing transaction time|895ACTIVE/204.726s|Existing-order processing is a concrete optimization review target|ACTIVE can create MARKET fills/checkpoint/queue changes; not synonymous with useless poll|
|PENDING also materially costly|510/152.207s|Skipping ACTIVE alone is not a proven100commands/s solution|Need preserve financial consistency and understand shared work|

Outcome: dispatch phase localized further. The smallest justified next activity is
read-only review of ACTIVE processing's call chain and existing reusable paths to
identify ONE redundant read/calculation with a valid consistency boundary. Do NOT
skip ACTIVE orders, drop input frames/checkpoints, remove financial fences, bump
workers/claim budget or change deadlines from this evidence alone. Active handlers
can execute fills for other orders in the same pair; their work cannot be removed
based solely on the anchor's previously successful command result.

No implementation optimization selected as proven yet: transaction envelope still
combines owner/publication waits, SQL round trips, input replay and pure matching.
This run does not justify pretending a queue-priority change will reach100/s.
Do not start another diagnostic/fullW2 automatically; reuse this evidence for a
bounded code review before proposing an amendment. W1Passed unaffected runtime;
W2Failed, W3/W4notstarted, F18/Paper Pending Full Validation,V22/V23 Pending
Dependency. No Git/CI/production API/schema/resource change.


### R28 draft after owner requested criteria review — 2026-10-29

Owner asked to proceed with the overload/scope recommendation. Read existing F15/
F18 W2 and F16 admission/throttle contracts before drafting. Important distinction:
existing W2 is closed-loop, not100incomingAPIrequests/s; per-user20/s throttle
exists but there is no approved global server queue bound. A true open-loop API
overload guarantee would need new admission control and a different plan, not just
a relaxed test assertion. Do not certify it using driver backpressure.

Prepared Proposed w2-bounded-saturation-amendment.md: explicit100owners bounded
saturation,6000fixednominalslots/300s,<=1activecycle/owner,explicitnot-submitted
slots,stopnewcycles300s/drain360s,everystartedcyclecomplete and progressfloor
600cycles/3000logicalcommands/allowners>=1. Preserve all R25/R26/R27-A safety,
RESET/overflow/financial/resource gates; no server/API/schema/throttle changes.
This is a concrete capacity-scope tradeoff for owner approval, not automatic
implementation or guarantee of pass. Bound applies to driver only; no claimed
production globalqueue/100HTTP/s protection. Proposed implementation remains
harness-only, exact identity/perowner financial oracle, failure/unknown accounting
and default-path regression checks. Earlier requirements/plan/validation untouched.

No code, workload, static/test rerun, resources or Git change. Draft review was
read-only plus proposal/checkpoint writes; estimated10–15min, approximately15min
including scope clarification. Need owner approval before applying R28. W1Passed/
W2Failed/W3-W4pending and PaperPendingFullValidation remain unchanged.


### R28 approved and implemented; acceptance waiting for host — 2026-10-29

Owner approve authorizes w2-bounded-saturation-amendment.md requirements/method/
validation. Marked it Approved and applied explicit W2-only override references in
requirements/plan/validation before coding. No production/API/schema/throttle/
financial/worker/claim/resource change. No new acceptance result or historical
Failed relabeling. W1Passed unchanged; old W2Failed; R28W2 pending.

Implemented profile_saturation.py: frozen nominal6000slots,one coordinator/<=100
activecycles/oneperowner; busy slots logged NOT_SUBMITTED_BACKPRESSURE without
creating requests or later catch-up backlog; exact slot decisions/completions and
failure/UNKNOWN accounting. New starts stop at300s; per-cycle R26 scopes preserved;
automatic360s global guard covers cycles AND scheduledRESETs. Cancel/join all
started tasks on failure; cancellation before coroutine start is explicitly failed,
not backpressured. Bad/duplicate plans rejected before work. Demand and actual
logical rates (including replay, denominator includes drain) are separate; no100
incomingAPI/s claim. Start/completion slot IDs remain deterministic despite gaps.

Reused F15 identity/intent constructors and financial oracle formulas. Added an
optional validated per-owner cycle-count map to F15 verify/verify_global; default
uniform semantics unchanged. No raw Decimal/float money calculations introduced.
F18W2 supplies its completed-slot map, checks>=600complete/everyowner>=1/allstarted
complete/conservation/planned6000+100owners+300s+100nominalrate. Exact request keys/
order IDs and terminal outcomes independently checked through actual owner-scoped
SQL, including baseline/reseed identities. R28cancel keys deterministic only in
bounded mode; normalW1/W3 preserve previous behavior. Native W1/W3/F15 default
scheduler untouched. Inapplicable W2/identity result fields are null, not Passed.

Tests:73unique affected tests passed across r28-final-unit.xml (66passed and one
new test initially failed),r28-cancel-key-fixed.xml (that test passed after restoring
its required cycle_scope),r28-db-contracts.xml(6passed). No unresolved failed test.
Original failing test XML retained; the failure was incomplete mock timing context,
not runtime/financial logic. Includes slot conservation/no catch-up/concurrency,
300sstart boundary/360s global cancellation,failed/UNKNOWN not skipped,external
cancel/join,duplicate plan/decision rejection,noncontiguous exact IDs,tampered/
duplicate/missing/unfinished requests,unequal perowner Money reference balances,
uniform/global default contracts and existing recovery/RESET/SLA/supervision tests.
Real PostgreSQL contract tests verify pending immutable request cannot pass identity
oracle and existing authorized restoration remains correct. Ruff/format5affected
files passed; mypy src/tests586files passed; scoped diff whitespace check passed.
No fullbackend regression rerun because production/domain unchanged and harness
callers/contracts covered; no implication that missing final validation/CI passed.

Implementation/checks elapsed approximately25min (started09:51:30UTC); initial
estimate30–55min included the still-unrun W2. Candidate source737e1a9ac0a487e16f994c2169da87d7781334cdd818e758f2641cce7e8a4d38
(757files),manifest preparation in validation-artifacts/f18-20261027/
r28-candidate-freeze.json; prepared runner/run_r28_w2_host.py only. No fresh R28
workload DB, W2, smoke or diagnostic launched. Once host is ready, verify this hash/
VM3GiB and original container limits, prepare fresh DB and run the ONE already-
authorized native R28W2 (expected10–15min with setup/overflow/analysis), stop on fail.

Preflight found7running dcs-local containers (tdr,job,mis,history,debd,dcs,
authentication) sharing the same VM with isolated F18Postgres. Asked asynchronously
whether owner will stop DCS or wait; no response yet. They were still running on
final check. Do not stop unrelated apps silently or certify perf with this extra
load: W2 acceptance remains waiting for host readiness under the no-overlap rule.
No repeat approval of R28 needed; resume acceptance after DCS is stopped/finished.
Pending question remains; no decision inferred from elapsed time.

W1 evidence remains applicable by unchanged production/default caller behavior and
explicit default oracle tests, not by claiming its old source hash equals R28.
R28W2 must have fresh final-source evidence; W3/W4/final review/regression/required
CI/manual gates still need reconciliation. Paper/F18 Pending Full Validation;
V22/V23 Pending Dependency. No feature-wide Ready for Code Review notification for
this harness subtask, no commit/push/merge, no Completed/merge-ready claim.


### R28 W2 single acceptance attempt — 2026-10-29 (Failed/Partial)

Owner reported DCS stopped. Preflight confirmed no other workloads; only isolated
F18 PostgreSQL remained. Redis had been removed, so recreated repo-compose cached
redis:7-alpine (digest sha256:892022f9f18c26c92c30e15194d132f90044af87b94a491a75429bbc3982eab1),
1CPU/256MiB, loopback56418; PING from host and Docker network passed. Historical
Redis digest was not archived, so exact historical image equivalence is unproven.
VM configured3GiB/effective3043373056bytes; PG4CPU/3GiB and app limits unchanged.
Fresh DB tiewtrade_f18_release_r28_w2_vm3g_20261029, schema0058,
track_commit_timestamp enabled. No Live orders or unrelated containers stopped.

Source737e1a9ac0a487e16f994c2169da87d7781334cdd818e758f2641cce7e8a4d38,
R10+R22/monitor4; native acceptance flags, not dispatch diagnostic. Artifact root:
validation-artifacts/f18-20261027/r28-w2-vm3g-20261029 (outside repository),
manifest.json/failure.json/w2-slots.jsonl/scheduled-resets.jsonl/raw input+commit
receipts retained. Freeze and launcher metadata in r28-candidate-freeze.json.

| Symptom | Evidence | Conclusion | Gap / next gate |
|---|---|---|---|
| Bounded saturation completed | 6000 planned slots;1038 started=completed;4962 NOT_SUBMITTED_BACKPRESSURE;active0/failed0;peak100;all100owners completed9–11cycles;conservation true | R28 volume minimum600/all-owner participation and no unfinished started cycles satisfied by recorded accounting | Independent exact-ID/economic final oracles were not reached; do not certify them from counters |
| RESET and logical command progress completed | RESET100expected/offered/applied,0failed;5190logical offered/admitted/completed,0rejected;2076fills/1038cancels/1038replays;all3selected scenario receipts present | Scheduled work completed before pre-overflow verifier | Final financial consistency and processing/resource gates still unverified |
| Pre-overflow verifier crashed | SQLSTATE42703 in F15 economic_snapshot: nonexistent paper_wallet_state.balance, before publish_overflow | Harness schema bug prevented overflow/recovery and remaining final gates; not evidence of wrong trading balance | Fixed canonical reader below; overflow NOT run or passed |
| Per-owner risk service quota failed independently | Offline existing raw receipts:237981expected=acknowledged;unack0/clock_errors0;global3late,0over5s;max3.053604s. Owner1187dc9e-5398-41e7-8c92-144ccfd67916 had3late/2381inputs (99.874%within3s), below99.9% | Global quota passes, per-owner quota fails. W2 remains Failed even after verifier fix | No claim that missing time is lock wait or host paging; correlate existing receipts/cycle records before any further experiment |

Three late PRICE inputs5112/5113/5114 share ready_at10:43:32.978505UTC and
commit_observed_at10:43:36.032109UTC; same owner, same3.053604s acknowledgment.
Offline sla_summary wrote postload-sla.json and risk-late-inputs.jsonl using only
existing files; no workload/diagnostic/DB financial mutations. This is partial
post-load evidence, not replacement W2 acceptance. No processing percentiles or
physical5s connection-cleanup/resource pass inferred from an incomplete run.

Smallest harness fix: economic_snapshot now takes existing canonical wallet_lock,
uses get_wallet ledger-derived balance, checks episode identity, and reads existing
fill/ledger/position counts under that owner lock. No production/API/schema/formula
change; canonical serialization prevents mixed-state snapshots. Added real-DB test
for schema-compatible repeatable canonical balance; both saturation-oracle DB tests
passed (r28-snapshot-fix.xml,2tests). Ruff/format twofiles, mypy586files and scoped
whitespace check passed. No full regression repeated for this test-helper-only fix.
Post-fix source84c57c8bae32ba979f25dc3ac1dfa2a63a3b9c436772715e04820f0b4bb29b7c
(757files); historical run still belongs to its original hash, not this new hash.

Elapsed approximately18min from10:33:08UTC to10:51UTC for preflight/setup/one run/
failure analysis/fix/checks, versus initial10–15min; announced additional5–10min
when verifier bug identified. Workload workers stopped; only isolated idle PG/Redis
remain. No automatic second run, overflow-only workload, W3 or W4 launched.

Next: analyze only the three correlated late inputs from existing evidence and
complete applicability review of unexecuted final gates before proposing one next
measurement. Do not rerun hoping to pass or relax financial/owner SLA implicitly.
W1Passed remains applicable (production/default W1 behavior unchanged); new R28W2
Failed/Partial, W3/W4 not started for this candidate; Paper/V21/F18 Pending Full
Validation; V22/V23 Pending Dependency. Required final review/regression/remoteCI/
manual evidence still require reconciliation. No Completed/merge-ready claim.


### R29 approved; W2 acceptance in progress — 2026-10-29

Owner explicitly approved R29 owner99.5%<=3s only in W2; global99.9%, every
input<=5s and W1/W3/default99.9% retained. Updated approved amendment and
requirements/plan/validation before implementation. sla_summary accepts phase,
selects exact integer995/1000 only for W2, preserves999/1000 globally and default,
records both targets, and is called with native phase. No production/schema/
resource/financial changes. Affected quota/default/hardbound/missingACK/clock/
exact-count and R28scheduler tests42passed in r29-targeted.xml; Ruff/format and
mypy586passed. Reviewed caller/default behavior before acceptance.

Read-only audit of prior R28 failed DB (SERIALIZABLE READ ONLY verified perowner)
reconstructed actual completed slot IDs, compared counts with original failure
receipt and ran existing independent F15 financial/global and R28identity oracles.
All100owner financial oracles and exact request/order identities passed;5134orders,
2077fills,1058cancels,2000pending baseline dispatch,duplicatefill0/unlinkedfill0/
invalidreservation0/invalidposition0/wrongmode0,inputlag19. Canonical snapshot
helper read all100owners without old SQL42703. postload-financial.json and
postload-identities.json belong to old R28 DB/source, not a fresh W2 acceptance.
Overflow/processing/resources/cleanup still not certified by this audit.

New frozen source9b261362c111d455cc391226ad4ae76664b500be8579161e07a74562bfbfa5f1
(757files); r29-candidate-freeze.json and runner/run_r29_w2_host.py in artifact
root pin execution. Fresh DB tiewtrade_f18_release_r29_w2_vm3g_20261029 schema0058,
zero initial orders, track_commit_timestamp on. Preflight only isolated PG/Redis;
VM effective3043373056bytes, PG4CPU/3GiB,Redis1CPU/256MiB unchanged. Parent/risk
limits and R10+R22/monitor4 use existing native runner. One W2 launched; no
diagnostic flags/concurrent workloads. Estimate implementation/checks10–15min
plus W2 setup/run/verification10–15min; if all W2 gates pass, W3 requires30min
measurement (estimate35–45min including setup), then W4/final gates by applicability.
Stop on failure; no automatic rerun. W1 prior Passed retained; F18 still Pending
Full Validation and V22/V23 Pending Dependency.


### R29 W2 final result — Failed; stop before W3 (2026-10-29)

Single approved W2 completed and exited1 with native result.json (no harness
exception). Source/configuration matches r29-candidate-freeze.json. Artifacts:
validation-artifacts/f18-20261027/r29-w2-vm3g-20261029; result/resources/manifest/
allrawreceipts and failure-analysis.json retained. No W2 repeat/W3/W4 launched.

Passed recorded gates:1101started=completedcycles across100owners,4899unsubmitted
backpressure slots,5505logicaloffered/admitted/completed,0rejected;RESET100/100;
normal+selected progress completed within334.819289s (<360s). Exact request/order
identities and all100financial oracles passed.5323orders/2203fills/1121cancels,
2000pendingbaseline orders,0duplicate/unlinkedfills,0invalidpositions/reservations,
0wrongmode. Overflow economics unchanged; all3selected scenario receipts present.
Processingp95=485.244ms/p99=748.186ms passed. RiskR29 passed:255207expected=ack,
9inputs>3s,max3.729835s,0>5s/unack/clockerrors;global99.9% and allowner99.5% quotas
passed. These gates alone do not certify required-load performance when cadence
gate below fails.

| Remaining failure | Evidence | Conclusion / limitation | Next step |
|---|---|---|---|
| Book publication volume | 2299 measured ticks versus required3000; elapsed334.819s | Required10Hz load not established. Publisher uses ordered due+=0.1 already; no evidence of a simple sleep-after-work bug. Cannot attribute to host RAM/CPU/DB from this result alone | Resolve source capacity/cadence before another full workload; do not silently lower source rate or count artificial inputs |
| Overflow timer |82.519629s versus60s. Native timer starts before publish_overflow, then includes recovery. Read-only DB commit receipts for retained injected inputs4462..8516 span75.212307s; first42 injected inputs overwritten. Final8516 inferred independently from final8557 minus41 resumed ticks | Most reported time includes injection. F15 validation§6 states return within60s after dependencies become ready; measurement boundary needs explicit reconciliation. No exact recovery-only duration claimed and no retrospective pass | Before changing method, clarify/amend boundary and retain injection duration separately; do not simply raise60s based on82.5s |
| Final input lag |26 versus20; native code waits through overflow watermark, resumes publisher, then stops publisher/workers before final query against newer tail | Genuine failing recorded gate, but final query is not a steady-state lag measurement and has no explicit final matching-drain wait. Not proven a safety bug or false positive | Specify/check final source watermark and drain/readiness semantics before changing measurement; no unbounded wait or stale-price bypass |

Other resource gates passed:peakRSS120270848bytes (<1GiB/process),peakconnections59
withinbudget197,lockwaitsend0,poolsreturned,physicalcleanup0.036205s/no appclients.
Composite resource flag False is from inputlag26, not a demonstrated RAM/OOM failure.
No change to resources or runtime based on this result. Idle isolated PG/Redis only
after cleanup. Review of failing gates was read-only; no new diagnostics/tests/
workloads or production edits after failure.

Implementation+checks and one W2 plus bounded read-only result review took about
22minutes from11:00UTC; W2 setup/run/finalization about11minutes (launched roughly
11:04:50UTC, native result11:15:50UTC), within announced20–30minute combined estimate.
R29 owner quota change is complete and verified, but F18/Paper/V21 remain Pending
Full Validation. W1Passed retained; W2Failed; W3/W4 current-candidate work pending;
V22/V23 Pending Dependency; final regression/review/requiredCI/manual reconciliation
still pending. No claim of PaperPassed or F18Completed.


### Remaining-gate audit — 2026-10-29, bounded to 20 minutes

Owner approved this audit only: inspect existing source/evidence/DB read-only,
update this checkpoint alone, propose one consolidated amendment/test set and at
most one additional measurement; no implementation/workload/diagnostic/tests/static
reruns. Started11:27:44UTC (18:27:44Asia/Bangkok). Current source still
9b261362c111d455cc391226ad4ae76664b500be8579161e07a74562bfbfa5f1,757files, same as
R29W2. No runtime/resource/API/schema/Git changes in this audit. Historical native
result files remain untouched. Queries against the isolated R29DB used BEGIN READ
ONLY; Python only read artifacts/calculated summaries. No fresh test pass claimed.

#### Findings: harness defects / coverage gaps

Paths below are relative to backend/tests unless stated otherwise.

| ID / severity | Location and evidence | Problem / impact | Proposed fix in R30 |
|---|---|---|---|
| H1 High | infra/risk_limits/profile_workload.py:320,370,1404,1547; R29result + inputs.jsonl | Only book count has a cadence assertion. Price loop creates multiple journal frames per observation batch; counting frames is not counting fresh BTC/ETH updates. Book count includes drain; final publisher counters are reset on W2 restart and overwrite the original phase's report. Underfed prices can make a risk-SLA pass look like required-load proof | Explicit phase/source counters, distinct fresh observations per pair, commit timing, and price cadence assertion; resolve unit NC-R30-01 below before implementation |
| H2 High | profile_workload.py:1429–1441; F15 validation§6 says return within60s after dependencies ready | recovery_seconds includes all4097injections and after-recovery economic verification. R29reported82.519629s includes at least75.212307s of retained injection commits; it does not establish slow recovery | Separate injection/recovery/verification clocks, keep total; conservative60s recovery starts immediately after final injection commit acknowledgement, before source restart; no retrospective pass |
| H3 Medium | profile_workload.py:1433–1449 and F15 verify_global_invariants:962 | Wait targets overflow watermark8516, resumed publisher advances to8557, workers stop, then lag is read against that newer tail.26>20 is a real recorded failure but an unsynchronized shutdown observation cannot locate when backlog returned to baseline | Check captured watermark, READY and current live lag<=20 together within the already-authorized recovery/drain deadline before shutdown; record shutdown lag separately, no extra waiting budget |
| H4 High | profile_workload.py:1008,1480; F15 run_fault_schedule:686–729 | W3 processing percentile collector includes transactions started during declared faults, while spec requires non-fault processing criteria. Fault observations call status RECOVERED after action+sleep/unpause without per-fault readiness/progress proof | Explicit fault/non-fault buckets and per-fault recovery evidence; preserve full duration of every transaction and all correctness checks; proposed attribution below |
| H5 Medium | profile_restore.py:242 and F15 security_shape:157; migration0058 | Restore security digest covers table ACL/RLS booleans and function ACL but not column ACL or policy definitions.0058 adds SELECT(cursor)/SELECT(watermark); latest located W4 was schema0057. Old restore pass cannot cover these grants | Include normalized column grants and policies, expected0058 role allowlist and source/target comparison plus owner/role probes on restored DB |
| H6 Medium | profile_workload.py:1299–1327,1599–1641; F15 resource_sampler:765,endurance_rss:901 | Fault windows/resources largely persist at successful phase end; an exception loses attribution. RSS windows are anchored to first/last sample rather than explicit measured boundaries. Idle owners are included by all-owner SLA but no separate coverage receipt establishes which inputs arrived outside commands | Persist phase/fault transitions and bounded samples as they occur; bind RSS windows to measured1800s; derive idle coverage from existing cycle/RESET intervals without dropping those inputs |

H4 is a measurement/coverage defect, not proof that future W3 processing will fail.
H5 is missing verification, not evidence that PostgreSQL restore actually loses grants.
No newly demonstrated balance/order/PnL corruption was found in this bounded audit.
This is not a full production security/code review.

#### Observed capacity and missing attribution

R29W2 manifest/result/inputs/resources/slots are the source of these calculations.
Start reconstructed from firstslot observed_at-elapsed_seconds is approximately
11:08:45.456586UTC; result elapsed334.819289s gives end11:14:20.275876UTC. This
wall-clock reconstruction is an estimate, not a newly available authoritative phase
commit marker. Native monotonic/UTC phase boundaries must be persisted next time.

| Phase / source | Existing evidence | Conclusion / gap |
|---|---|---|
| Setup prices |3062frames in1017distinctcommit timestamps before estimated measured start | Setup is separate from acceptance. Not a10Hz acceptance proof; state transitions can create extra frames |
| Nominal300s W2 prices |1866frames/622distinctcommit timestamps | Approximately2.07publication transactions/s, not10. Read-only SQL comparing per-pair trade_id changes across all frames confirms fresh observations rather than inferring from equal-price values |
| W2 drain34.819s |660frames/220distinctcommits | Approximately6.32transactions/s; source speed changes with phase. Do not use drain catch-up to hide insufficient nominal-load publication |
| Complete measured interval |2529measured PRICE frames/843commit timestamps; SQL in estimated closed interval finds842freshBTC and842freshETH observations | One final in-flight commit lies ~15.5ms after reconstructed end and is still marked measured. Distinct observations, price frames and phase counters must stay separate |
| Book input load |2299ticks versus3000 required over native334.819s; retainedring after overflow only4462..8557 | Required book load failed. Earlier book source commit timestamps are overwritten; execution/evidence recorded_at is not a substitute for original commit time |
| Source publication cost | API/Paper process group average2.9644CPU cores over293.576895s of measured samples against limit3; parent0.4120, Paperworkers2.5524; separate risk0.6813/1core | Near-saturated API/Paper CPU envelope is established. It does not prove cgroup throttling, per-publication CPU attribution, DB lock waits or sole cause; no cgroup/event-loop/source-stage evidence in this acceptance run |
| Overflow |8516final injectedinput derived from8557finaltail minus41resumedticks. Retained4462..8516 commits11:14:23.792485..11:15:39.004792UTC span75.212307s; first42injections overwritten | Injection dominates reported82.52s. Exact recovery-only timestamps not saved; do not backfill a pass or report an exact recovery-only duration |
| Final lag |26after workers stopped; maxRSS120270848bytes,peakconnections59,budget197,lockwaitsend0,poolreturn/physicalcleanup passed | Composite resource failure is lag, not demonstrated RAM/OOM. No basis to change Docker RAM or worker concurrency from this result |

#### W1 reuse qualification discovered by this audit

Historical W1 result remains PASSED as recorded; it has6083bookticks over608.264522s.
Its raw input evidence contains12750measured priceframes but only4250distinctprice
commit timestamps (~6.987transactions/s); current publisher makes a renew/feed frame
plus BTC and ETH updates in one transaction. Thus it does not by itself prove
10freshupdates/s **per pair**. It exceeds10journalframes/s, which is a different
unit. This is a newly found coverage ambiguity, not a change of historical output.

NC-R30-01: clarify price10Hz as the existing R12 source loop's intended ten fresh
BTC observations and ten fresh ETH observations per second, excluding lease-only
frames and repeated snapshots of the same observation. This is the recommended
interpretation; it requires explicit approval because existing language says
priceframes10Hz and existing oracle did not enforce the unit. If approved, old W1
financial/progress/processing/rawSLA evidence remains useful, but W1 full-load
acceptance must be checked again after the source gate is corrected; do not promise
unconditional W1 reuse. No W1 rerun is authorized or started by this audit.

#### W3 and W4 preflight / applicability

- W3 remains1800s,100owners×20baselineorders,30positivecycles perowner; sevenfaults
  at225/450/675/900/1125/1350/1575s with original30/60sdurations. R27RESET schedule
  avoids plannedfaults and uses actualgate; no arbitrary extension of normal60s
  or selected120s/180s budgets. Mandatory isolated --redis-container must be supplied;
  mechanically changing a W2 launcher to W3 without it fails before setup.
- Restart recreates risk+10Paperworkers and retains metric paths/generations;
  pool inventory supports matching restarted generations and existing tests cover
  recreation on dispose. Source book publication remains running during faults;
  connection churn additionally suspends prices12s as declared. Fault-started
  cycles remain active: gate.pause stops NEWcycles, not all in-flight work.
- Current RECOVERED label certifies action completion only. Add source/risk/order
  progress receipts within60s after restoration; preserve fault end at declared
  event restoration, never expand fault windows to absorb recovery misses.
- W3 Redis pause does not by itself prove API/notification Redis recovery: this
  direct-intake Paper/monitor path uses PostgreSQL and no Redis client was found in
  inspected callers. Preserve PG-authority correctness-during-outage scope; verify
  actual container pause/unpause. Reuse separately applicable API PriceBroadcaster
  disconnect/reconnect tests; do not claim HTTP/notification coverage from this run
  or silently expand the workload to a new Redis-dependent path.
- Idle coverage can be derived from price ACKs and owner intervals outside started
  cycles/RESETs. Report those inputs separately, while all remain in R25/R29 totals.
  Do not create extra owners or remove idle inputs. No claim of completed W3 idle
  coverage before the actual1800s run.
- RSS window criteria remain warmup112.5s, firststable112.5..562.5s and final450s
  of measured1800s, observedcoverage>=1687.5s, growth<=20%. Align measured boundaries
  explicitly and retain all restarted worker RSS; exclude cleanup from window
  anchors, not from resource/cleanup reporting. Current helper's moving sample-end
  anchor can slide with overhead and has only shape/boundary unit evidence so far.
- W4 needs fresh0058 preactivation sourceDB and a distinct empty targetDB, then
  existing legacy F15 fixture adoption + real risk baseline/latch/pendingstop and
  AUTH-only receipt. Do not reuse an already-activated W2 DB as W4 source. Existing
  recovery replays claims/stops/authorization and compares canonical economic/
  baseline digests; keep these. Latest located r11-w4 is schema0057, so no blanket
  reuse for0058. Add columnACL/policy/role verification before final restore run.

#### Gate inventory — use existing evidence only where applicable

| Gate | Evidence / current status | Remaining action |
|---|---|---|
| V01–14 core/input/auth/isolation/financial concurrency | Existing M1–M5 targeted evidence; R20safety69,R22clean21 and other recorded suites; no runtime code changed by this audit | Reuse cases with unchanged dependencies; new harness changes require callers/transaction/supervision rechecks, not a blanket new domain regression |
| V15–17 cancellation/recovery/protection | Paper targeted evidence exists; ordinary matching/cancel invariants pass in R29. Protective TP/SL identity dependency was already explicitly Partial in early M5 | Do not relabel protective/bot/Live coverage Passed. W3 fault/idle/recovery at load remains required |
| V18–19 UI/composition | Earlier Paper browser/TH-EN/theme/layout and real API/engine composition evidence in M4/M5; harness-only R29 has no UI/API contract change | Check applicability to final runtime; manual owner walkthrough is not replaced by automated screenshots; unrecorded acceptance stays pending |
| W1 | Historical nativePassed; book/progress/economics/recordedSLA evidence retained | Price-cadence unit/gate is newly unproven. Conditional reuse only; under recommended per-pair interpretation rerun required after source fix |
| W2 | R29Failed: cadence,overflowtimer,final lag. ExactIDs/financials/R29risk/processing passed only on observed underfed load | Fix harness and establish prescribed source load before a new single acceptance run |
| W3 | Not run on current candidate;7faults/RSS/idle coverage pending | Close H1/H3/H4/H6 and runner preflight first, then one30min run |
| W4 | Prior0057restore Passed;0058current not certified | New0058source/target restore with H5 verification and original claim/stop/TOTP/no-duplicate checks |
| Backend full regression | r24-regression-coverage.json has3828uniquePassed on experimentalR24; rollback56Passed. Current risk_limit.py/session.py/errors.py byte-match archived r24-before versions | Preserve historical failures/reuse unchanged cases; not a current blanketfullpass. Reconcile final pytest collection vs completed nodeIDs and affected dependencies once code is stable, then run only missing/invalidated cases unless scope requires fullsuite |
| Recent harness checks | r29-targeted.xml42Passed; r28-snapshot-fix.xml2Passed; recordedruff/format/mypy586Passed | Valid for unchanged R29; proposedR30 invalidates affected helper/caller checks. None rerun in this audit |
| Static/contracts/build/architecture | Earlier local CI-equivalent evidence exists; R29 only touched harness/spec | Reuse unchanged frontend/contracts; run relevant new lint/format/types and architecture checks when finaldiff known |
| Final code review | Earlier review/fixes/refactor done; no final R30diff yet | Review consolidated harness/runtime dependencies once, Critical/High closed before workloads; feature notification rules still apply if fullfeaturecheckpoint reached |
| Required remoteCI | No F18candidate commit/push authorized; dirty candidate has no qualifying remote run | Pending; local tests are not remoteCI. Git mutations require owner instruction |
| Manual acceptance | Owner's setting/TOTP/decrease/reset/UNKNOWN/reload/mode/stop-effects walkthrough required by validation§4 | No qualifying owner acceptance receipt located in this bounded audit; keep pending |
| V22/V23 | Bot/Live/protective/notification dependency checkpoints | Pending Dependency; no scope expansion, no Live orders, no Completed claim |

### R30 consolidated harness correction — APPROVED 2026-10-29

สถานะ: **Approved — เจ้าของตอบ approve หลังข้อเสนอ R30 วันที่ 2026-10-29**.
NC-R30-01 approved:10freshBTC and10freshETH observations/s; lease-only journal
frames do not count as price observations. Harness work/tests authorized; no new
workload/diagnostic authorization inferred. Historical audit text below retained.
Keep numeric R25–R29/financial/freshness/resource bounds. No production API/schema,
Money/Quantity, trading policy, retry, scheduling, pool/CPU/RAM or source rate change.
The source10Hz unit clarification and measurement/order changes below require
approval under AGENTS.md (spec conflicts/changed approved method) before code.
This section is the amendment, kept here to avoid another duplicated report.

1. **One phase/evidence model.** Reuse existing Fixture publishers, telemetry,
   measured_transaction_seconds, source commit receipts, resource sampler and
   profile_timing contexts. Record setup/load/drain/injection/recovery/verification/
   shutdown transitions with monotonic+UTC anchors. Persist transitions/faults and
   samples on failure too; snapshots/counters keyed by phase, never overwritten by
   publisher restart. Keep original aggregate/raw measurements alongside subtotals.
2. **Cadence contract (NC-R30-01).** Count committed unique book inputs and fresh
   per-pair observations at intended10Hz, not three journal frames from one price
   batch. Add explicit counts/expected/rates/gap distribution per phase. Use fixed
   nominal load window; report drain separately, without counting its catch-up as
   nominal load. Only explicitly scheduled price-suspension intervals are exempt
   from price publication demand; book continues through faults. All committed
   ready inputs still enter riskSLA even in drain; no invented inputs or freshness
   relaxation. Confirm units before changing oracle or W1 reuse decision.
3. **Overflow boundary.** injection starts before source acquisition and ends after
   final4097th input commit acknowledgement. Start the60s recovery deadline there,
   before restarting the normal publisher (a conservative earlier boundary than
   waiting for it to be READY). Record dependencies-ready time separately. Recovery
   completes only when all100owners have reached captured watermark, current source
   readiness is valid, and a consistent live observation shows inputlag<=20. Keep
   that observation/watermark/time. Economic before/after verification has its own
   duration; report total including all phases. Errors/cancellation fail and join
   all tasks; do not claim exact timings from old unrecorded boundaries.
4. **Finalization ordering.** Keep source and workers alive while checking baseline
   progress within the existing deadline: W2overflow uses that same60s budget;
   normal W1/W3 load+drain stays within duration+60. Do not add a second waiting
   allowance or search for favorable samples after deadline. Capture live lag with
   one consistent snapshot of source watermark/owner cursors/READY and complete
   owner inventory. After the first qualifying baseline, stop source and join it,
   capture final risk watermark, retain existing bounded risk ACK drain, then stop
   workers and run immutable financial/identity/cleanup checks. Persist post-stop
   lag as shutdown data, not a replacement for the live recovery gate. No stale-
   source bypass, skipped input or canceled unfinished financial operation.
5. **W3 fault proof.** Record fault start/restored/recovered separately and require
   per-fault source/progress recovery within the same approved60s bound; start an
   observer after restoration without delaying gate resume or enlarging excluded
   fault windows. Only actual restored dependency state ends the fault; no retroactive
   relabeling. Processing rows are attributed by transaction start (existing rule):
   fault-started rows reported in fault bucket; non-fault-started rows retain their
   entire duration even across a fault boundary. Keep all raw rows/outcomes and a
   whole-run summary. Add explicit idle coverage and fixed RSS window evidence.
6. **W4 security coverage.** Extend existing security-shape helpers to compare
   normalized column ACL and policy definitions in addition to existing tables/
   functions; assert expected0058scanner privileges and restored owner/role access
   restrictions using established isolation patterns. Keep fresh source/target,
   digest/domain replay/expiredclaim/stop/idempotentAUTHreceipt/economic invariants.

These are harness corrections, not a proven publisher performance fix. No CPU
allocation or production optimization is chosen without the missing attribution.
Approval of R30 would authorize only its harness work/tests; a further measurement
needs explicit authorization as described next, not an automatic acceptance loop.

#### One proposed bounded measurement if existing evidence is insufficient

Question: which source-publisher stage misses its10Hz due time under W2 saturation
on the frozen3CPU API/Paper group: event-loop scheduling/pool acquisition/source
transaction/commit acknowledgement/evidence recording? Existing artifacts lack
these spans, so they cannot select a proven optimization.

Propose ONE60s measurement using existing diagnostic window,100owners×20orders,
R28bounded W2 demands,R29oracle,R10+R22/monitor4 and unchanged allocations; baseline
observations also during setup. Reuse telemetry/SQLAlchemy event hooks and source
wrappers for due/resumed/pool/transaction/commit/evidence times, keyed by source,
pair,inputID/publication tick and shared clocks. Record no SQL parameters/secrets
and add no SQL inside financial transactions. Retain actual cgroupCPU/throttle and
memory counters plus hostpaging using existing sampler interfaces; label intervals
as wall-time stages, not lock wait without a lock-wait observation. Do not sum
concurrent transactions into one request latency.

Bound detail to at most2400source-cycle records over the60s window (allstagefields
in each record) plus per-second aggregate counters; reaching cap/missing clock/
collectorfailure makes evidence incomplete and ends the run, never silently drops
failures. No acceptance verdict; scheduledRESET180s and W3faults are not covered.
Setup approximately3–5min, measurement1min, analysis5–10min; instrumentation/tests
estimated15–25min first. Report overrun before extending. A subsequent before/after
comparison must use the same configuration/instrumentation and a separately
supported single hypothesis; no automatic repeat. This measurement was NOT run.

#### Tests to run only after the proposed changes are approved/implemented

- Source: lease-only/snapshot duplicates do not inflate observation rate; equal
  amount with new valid observation ID counts; publisher restart preserves phase
  totals; exact window edges/in-flight commits; only declared price gaps exempt;
  book/price independent supervision, cancellation and recorder failure.
- Timing/progress: injection75s+recovery5s reports phases correctly and total>=80s;
  real recovery60s boundary accepted/>60fails; missing/falseREADY owner fails;
  advanced tail after recovery is visible; lag<=20 assessed while live in the same
  deadline; no extra deadline extension; final ACK/worker shutdown retains receipts.
- W3: declared fault vs non-fault-started/straddling transactions retain full raw
  duration; restored-but-not-recovered fails; no fault-window widening; restart
  generation/pool inventory and Redis pause cleanup; idle ACKs included; RSS exact
  112.5/450/1687.5/1800s boundaries and missing samples fail.
- W4: losing0058column grant or changing policy is detected; unauthorized extra
  grant detected; owner/role isolation restored; claim/stop/AUTH-only replay remains
  idempotent and economic/baseline digests unchanged.
- Existing callers/contracts: F15default profile remains unchanged where possible;
  if a shared helper changes, run its original tests alongside F18 ones. Reuse
  test_fixture_publication, test_workload_profile, test_profile_resources,
  test_monitor_price_hint and existing transaction/barrier/isolation suites as
  affected; reuse canonical get_wallet/wallet_lock rather than a second balance
  calculation. Run relevant lint/format/types/import checks after code changes.
- Financial/domain regression is selected from actual changed callers, fences,
  rollback and ledger dependencies, not rerun just because this audit resumed.
  Reconcile final collection and previous evidence before claiming full coverage.

#### Decision and stop

Do not start W1–W4 yet. Recommended next decision is approve/clarify R30's source
unit and measurement semantics, implement/test the consolidated harness, then
explicitly authorize the ONE bounded source-stage measurement if still needed.
Only a source-capable final candidate with all short safety/measurement gates
closed enters full acceptance. Remaining fixed measurement time is35min for W2+W3;
under recommended price-unit correction W1 may add10min. Setup/overflow/W4/review/
regression/remoteCI/manual remain additional; do not promise a fixed finish time.

No criteria have been relaxed or code edited by this audit. W2 remains Failed,
W3/W4 current-candidate pending, historical W1Passed preserved with applicability
qualification above. Paper/F18 Pending Full Validation; V22/V23 Pending Dependency.

W4 result handling note: the base restore helper writes result.json before the
F18 risk recovery assertions. Require exit0 AND both result.json and
risk-recovery.json PASSED; a base-only Passed is incomplete.

Audit closed at 2026-10-29T11:47:07.025073+00:00 (19.38minutes elapsed).
Only this checkpoint was updated. R30 remains Proposed; no code, workload,
diagnostic, tests/static, resources, acceptance status files or Git history changed.

### R30 implementation checkpoint — 2026-10-29 20:02 ICT

Owner approval applied to R30/NC-R30-01 before implementation; requirements,
plan and validation carry the approved override. Work started19:06:37ICT and
finished approximately20:02ICT (~55min; announced40–60min). No workload,
source-stage diagnostic, W1–W4 run, resource change, production code/schema/API
change, Live order, commit/push/merge occurred in this round.

| Cause / gap | Change | Expected effect / actual evidence | Next gate |
|---|---|---|---|
| Journal frames and late drain inflated/obscured source demand | Unique book commit receipts and per-pair observation identities; fixed nominal UTC window, declared price suspensions only, phase counts/rates/gaps; cumulative publisher counters | Unit tests reject duplicate receipts and drain catch-up; real publisher tests preserve independent progress and joined shutdown. No claim that actual10Hz capacity now passes | One separately authorized source-stage measurement |
| Overflow timer mixed injection/recovery/verification | Separate monotonic phase anchors and total; recovery deadline starts immediately after final injection acknowledgement, before restart | Boundary test75s injection +7s recovery does not report82s recovery; actual recovery>60s still fails | Native W2 still Failed; no retrospective pass |
| Post-stop lag substituted for live recovery | Read-only repeatable-read transaction, owner-local RLS, complete owner inventory, captured source/price watermarks, READY/current lag<=20, then source stop/final ACK drain/workers stop | Real DB positive/missing-owner checks pass. Initial migrator query returned no owners under RLS; fixed using existing engine role/local owner context without grants/BYPASSRLS. Deadline also checked after receipt persistence | Validate live baseline under authorized workload; observer cost included |
| W3 fault/recovery and window evidence incomplete | Durable STARTED/RESTORED/RECOVERED events, gate resumed before recovery observer; transaction-start attribution retains full durations; raw/fault/all summaries, idle-owner ACK coverage gate, fixed measured RSS windows; resource/fault evidence retained on failure | Fault recovery failure preserves restored boundary, straddling transactions retain full duration, missing RSS window fails; F15 defaults remain compatible | W3 not run |
| W4 omitted column privileges/policy definitions and could leave base-only PASSED | Compare normalized column ACL and policy definitions for existing restore table inventory; expected0058 grants, actual owner/scanner access checks; combined result remains pending/failed until risk recovery passes | Real DB tests revoke required grant/add forbidden grant/change policy and detect each; finally restore metadata and compare exact original shape | W4 native restore/digests/claim/stop/AUTH replay still not run |

Implementation files: risk_limits/profile_workload.py, profile_observations.py,
profile_restore.py, test_profile_observations.py, test_fixture_publication.py,
and shared execution_market/profile_workload.py (optional fault/resource/RSS
arguments only; existing callers/defaults retained). All paths under backend/tests.
The source receipt observer adds a read-only book commit-timestamp lookup outside
financial transactions; its overhead is part of the candidate and remains to be
measured. The R30 correction is not a demonstrated publisher performance fix.

Validation artifacts under
`/Users/chainarongjaykeaw/Projects/TiewTrade/validation-artifacts/f18-20261027`:
- `r30-final-harness.xml`:120passed,17.095s; source supervision, workload/SLA,
  resource/authorization, F15 supervision, R29 acceptance, cycle budgets, RESET.
- `r30-final-observations.xml`:20passed,1.514s; current R30 focused DB/measurement
  checks including restored permissions and policy-change detection.
- `r30-final-boundaries.xml`:6passed,1.098s; affected cadence/live recovery/phase/
  overflow checks after final captured-price readiness adjustment. Counts overlap;
  they are not140/146unique tests.
- Earlier `r30-final-followup.xml` contains49passed/1failed (driver-specific SQL
  placeholders in the newly parameterized security query); corrected to SQLAlchemy
  text binds and superseded by the passing focused DB tests. Earlier fixture test
  failures exposed missing protocol activation/ETH test data and the RLS read gap;
  no threshold/deadline was increased to resolve them.
- Ruff and format check:6changed Python files passed. Mypy `--no-incremental src tests`:
 588files passed. Import contracts:7kept/0broken (282files/1989dependencies).
- Final runtime/test tree SHA256:
 `9a5f41651f66354cbc73b5947bfd9892532f2017ccf3df0d986c140c4bbc7fff` (759files;
 source_manifest algorithm). This identifies code evidence, not a frozen acceptance
 runtime/configuration or a new acceptance pass.

No more tests/workloads automatically scheduled. Next proposed step remains the
single60s source-stage measurement above, requiring separate authorization:
instrumentation/tests15–25min +setup3–5min +measurement1min +analysis5–10min
(~24–41min total); no automatic repeat. It must answer missing due/resume/pool/
source transaction/commit/evidence attribution before choosing one optimization.

Status remains **Pending Full Validation**. Historical W1nativePassed is retained
but cannot certify the newly explicit fresh-price10Hz gate. W2Failed retained;
W3/W4 not started this round. Final regression/current collection reconciliation,
final review, required remote CI and manual acceptance remain pending. V22/V23
remain Pending Dependency; Paper validation and F18Completed are distinct.

### R30 source-stage measurement — owner approved, started 2026-10-29 20:16 ICT

Owner's next `approve` authorizes the ONE60s measurement proposed above, including
bounded instrumentation/tests. Preflight: only the existing F18PostgreSQL/Redis
containers running; PostgreSQL4CPU/3GiB, Redis1CPU/256MiB, VM2972044KiB total.
API/Paper remains3CPU/1536MiB and isolated risk1CPU/512MiB, monitor4. R10 default
is true in current source and priorR29manifest; no diagnostic-only scheduling flag.

Add opt-in `--source-diagnostic-seconds 60` (W2only, incompatible with other
observations). Source cycle ContextVars and existing SQLAlchemy events record
requested/checkout/entered/body/commit/ack timestamps and SQL round-trip duration,
without SQL parameters/text or any additional SQL. Preserve source commit/input
identities, setup per-second aggregates, at most2400measured cycle detail records,
fail loudly on cap/missing successful-commit timestamps. Source due lag is separate
from scheduling delay after the prior cycle actually finished. SQL round-trip is
contained in body time; neither is asserted to be server time or lock wait.
Reuse memory sampler's existing Docker response for actual CPU/throttle counters;
reuse host paging/clock observer. Production code, schema, rules and allocations
unchanged. Source instrument tests26passed; active/inactive real publisher6passed;
Ruff/format5files and mypy590files passed. Artifacts `r30-source-timing-tests.xml`,
`r30-source-timing-focused.xml`, `r30-source-publisher-tests.xml` under existing root.

Single run: database `tiewtrade_f18_release_r30_source_stage_20261029`, artifact
`r30-source-stage-20261029`, host runner `runner/run_r30_source_stage_host.py`.
Setup3–5min +measured1min +analysis5–10min expected after instrumentation. Stop on
failure; no automatic repeat/W1–W4. Diagnostic is not acceptance and does not cover
scheduledRESET180s, overflow, W3faults or W4restore. Final observations follow here.

### R30 source-stage result — stopped after ONE run, 2026-10-29 20:30 ICT

Result: diagnostic **WINDOW_COMPLETE**, exit0, **acceptance_result=false**.
Setup13:16:26.182–13:20:11.298UTC (~225.116s). Nominal measurement60s;
controller elapsed60.711s includes cancellation/join after cutoff. Fixed60s is
used for source counts, not the longer controller duration. Analysis stopped by
13:30UTC (~8min after completion); approximately25min for this approved round,
within announced24–41min. No second run or W1–W4 started.

Frozen source SHA256 `fa243e6e705468c66debd1a7929f5248353d17cef43ad0cd3c700418a339faf9`
(matches current source after the run). Manifest confirms100owners×20baseline,
R10true/R22, monitor4,3CPU/1536MiB API+Paper and1CPU/512MiB risk. Keep this run
separate from oldR29/R30un-instrumented evidence; no before/after speedup claim.

| Symptom | Evidence from this run | Conclusion | Remaining gap |
|---|---|---|---|
| Source cannot meet10Hz during saturation | Fixed60s:214uniqueBOOK commits (3.567Hz);117freshBTC and117freshETH observations (1.95Hz/pair), required600each | The source-capacity gate is not ready for W2 acceptance | Not an acceptance run; no native W2 verdict or financial pass inferred |
| Price source serial cycle is too long |116completed PRICE cycles: mean512.65ms,median485.19ms,p95 1002.15ms. Its publication transaction always22SQL executions; mean body306.35ms,of which measured SQL round-trips296.71ms. Receipt transaction adds mean131.81ms including acquisition/body/commit | Largest mean stage is price publication's SQL/await interval; evidence recording also has material cost. A100ms source period cannot be sustained with these cycle times | SQL round-trip includes server execution/locks/transport/client scheduling; aggregate22-query timing does not identify which query dominates |
| Book source also overruns period |213completed BOOK cycles:mean274.08ms,median256.63ms,p95 610.53ms.199cycles had2transactions;14also emitted the required partial-fill trade | Book/price failures are measured separately, not explained as one summed latency | Partial-fill cycles are retained and separated in examples |
| Very large due lag |PRICE median due lag138.82s, but scheduling delay AFTER preceding source cycle finished median1.73ms,p95 31.09ms; BOOK median1.55ms,p95 16.80ms | Due lag is accumulated missed periodic deadlines, not evidence of a single140s lock wait. Each serial cycle's work dominates the repeating schedule | Async resume delays inside DB calls are still included in round-trip wall time |
| CPU and memory contention coexist |Measured API/Paper2.95/3cores,543/597periods throttled (~91%); risk0.67/1core andPG2.07/4cores, neither throttled in sampled window. VM minimumMemAvailable797536256bytes,noOOM. Host counts:2029037compressions,1984280decompressions,15354swapins,16832swapouts | Shared API/PaperCPU is saturated and host paging is substantial; both must stay in interpretation | These correlations do not prove that CPU or paging alone caused any particular SQL interval. Do not sum cgroup throttled time as one request's latency |
| Acquisition sometimes slow despite spare pool slots |MARKET_DATA pool size5+overflow10,peak checked-out3; worst PRICE cycle's receipt acquisition692ms. Engine uses pool_pre_ping | An acquisition interval includes pre-ping/driver/dispatch work; this is not proof of exhausted connection capacity | No per-query/pre-ping server timing or owner-correlated lock wait sample |

Correlated examples (same PRICE2transaction shape; no summing concurrent cycles):
- PRICE sequence3135:487.826ms cycle =134.249ms acquisition +296.553ms bodies
 +56.251ms commit acknowledgement intervals +~0.773ms other source work.
 SQL292.273ms is INSIDE body time, not added again.
- Slowest PRICE sequence3155:1519.405ms; publication body280ms but its separate
 receipt read/acquisition/commit dominated this individual cycle. Therefore the
 mean dominant publication stage does not explain every slow sample.
- Slowest BOOK sequence3157:1592.610ms; publication body1169.338ms. Input2080
 committed13:20:52.168325UTC, joined to its cycle/receipt in raw evidence.
- `source-price-examples.json` and `source-book-examples.json` retain5slowest and
 5median-neighborhood examples per same2transaction shape;14BOOKpartial-trade
 cycles remain in raw/aggregate evidence rather than being discarded.

Evidence completeness/cleanup:
-330measured cycle detail rows below2400cap; noINCOMPLETE event. One BOOK cycle
 was canceled at the diagnostic cutoff before a commit acknowledgement and is
 retained explicitly, not counted as a completed cycle. Price commit counts also
 include an in-flight cycle that started before the window and committed inside;
 cycle-start counts and commit-time counts deliberately differ.
-Timeline's synchronous recording time1.877s is cumulative across setup/load/tail;
 it is not a per-request latency, and callback/instrument overhead is not assumed
 zero. No SQL parameters/text/secrets recorded.
-Controller counters at cutoff:offered933/admitted852/completed851/rejected0,
 cycles113. Unfinished work remains visible; this is not a financial oracle pass.
-SQLAlchemy connection-termination CancelledError warnings occurred during cutoff
 cleanup and are retained in log. All12pool inventories finalized with0checked-out;
 read-only post-run PG check found0connections for this isolated database, and
 Docker had only the originalPostgreSQL/Redis containers left. No retry was run.
-Host/VM clock samples bracket VM timestamps within host before/after bounds;
 round trips~89/109ms. Source timings use one Linux monotonic clock; nearest
 MEASURED_WINDOW wall/monotonic anchor used for wall-time joins.

Artifacts under existing root: `r30-source-stage-20261029/source-timeline.jsonl`,
`source-commits.jsonl`, `source-stage-analysis.json`, same-shape example JSONs,
`diagnostic.json`, manifest/pool/worker evidence; adjacent `.memory.jsonl`,
`-host.json`, `-clock.json`, `.log`; analysis script
`runner/analyze_r30_source.py`. Static/targeted checks described above passed.

**Decision:** evidence is sufficient to identify the source publication SQL/await
stage as the largest mean bottleneck, but NOT sufficient to select a particular
SQL/lock/CPU optimization safely. Do not remove repeated lease/fence checks:
`realtime_storage._locked` is used before/after mutations to preserve lock order
and recheck expiry after waiting; renew+two price writes account for six calls.
Nor would eliminating only the receipt-read transaction make a513ms price cycle
fit100ms; it is not presented as a complete fix.

The precise missing evidence is per-SQL safe-label start/end within the existing
22-query publication transaction (especially first publication fence versus later
reentrant fence/row-lock checks), with the same cycle/input identity. Pool-acquire
interval must remain separate and must not be labeled pool exhaustion. A next
measurement, if authorized, should add these bounded fields to the existing
at-most2400cycle records (no SQL text/parameters/new SQL), preserve CPU/memory
observations, run ONE60s set on the same configuration, and stop before choosing
one amendment. Estimate instrumentation/targeted tests5–10min +setup3–5min +60s
measurement +analysis5–10min (~14–26min). **Not authorized or started here.**
No safe source optimization/amendment, resource change or criteria relaxation is
claimed proven by this run. W1historicalPass retains the fresh-price-load gap;
W2Failed, W3/W4pending, F18PendingFullValidation and V22/V23PendingDependency remain.

### 2026-10-29 — approved bounded per-SQL source timeline
Owner's “เริ่มทำ” authorizes the previously proposed ONE60s diagnostic, not a
source optimization or acceptance workload. Round began13:35:03UTC; estimate14–26min.
Added fixed SQL labels/start/end to existing source cycle records, with bounds
64queries/transaction,8transactions/cycle and2400detailed cycles. No SQL text,
parameters, added SQL or financial instrumentation. Concurrent source isolation,
failed/cancelled query retention and real publisher labels tested:19passed plus
1query-cap test passed. Ruff passed3files; mypy passed590files (output retained in
r30-source-sql-mypy.log; repeated only because prior session result was unavailable).
Preflight: only existing PostgreSQL/Redis containers running; isolated fresh database
prepared. Same R10+R22/monitor4/resources and100x20 W2 bounded saturation; no
before/after speedup claim across different instrumentation. Stop after analysis;
W1–W4 not started. Artifacts prefix:r30-source-sql-20261029.

#### Per-SQL diagnostic result — stopped after one run
Source tree0920124ebda7819ac2e1ddbbf7bd7c76157c5028441114bdb13a911fdd09bd1b.
Manifest confirms R10true,monitor4,100ownersx20,100logical-command/s bounded
saturation,API/Paper3CPU1536MiB+risk1CPU512MiB. No runtime/resource changes.
Setup13:45:14.355–13:48:17.063UTC=182.708s; nominal measurement60s,
controller60.380s including cancellation/join. Exit0/WINDOW_COMPLETE is diagnostic
only,acceptance_result=false; scheduled RESET not exercised. Counters:1065offered,
998admitted/completed,0rejected,174cycles; remaining offered work is not discarded
or treated as passed. No acceptance financial/oracle conclusion.

| Symptom | Evidence | Conclusion | Gap |
|---|---|---|---|
| Source does not supply10Hz | Fixed60s commit window:267BOOK,157freshBTC,157freshETH;4.45Hz book,2.617Hz perpricepair | Current fixture still cannot establish the required input load | This short run is not W2 or proof of runtime acceptance |
| PRICEcycle376.216ms mean |156completed cycles; mean acquisition60.275ms+body265.617ms+commitACK48.234ms+other2.090ms | Sequential publication/readback path exceeds100ms budget; removing one small check cannot close gap | Client intervals include server,transport and application scheduling |
| First publication fence is slowest SQL position on average | Queryindex3 mean50.827ms,p95147.607ms,max279.574ms; publication22SQL total223.252ms mean | First fence matters but accounts for only13.5% of whole cycle mean; even hypothetical removal leaves325ms | No server-lock-wait duration; do not equate roundtrip with lock wait |
| Reentrant checks/readback have cost | Five later fence calls total34.768ms mean; separate receipt transaction84.093ms mean | Removing all these hypothetical costs still would not reach100ms, and checks preserve safety | No authorization to remove/reorder checks; receipt commit evidence must remain complete |
| Slowness not confined to first fence | PRICEseq2985=829.06ms with reentrant feed-lock read297.05ms; seq3120=1370.46ms spread across feed-lock/fence calls; BOOK DB_CLOCK max296.071ms | A single initial fence explanation does not fit tails; repeated awaits/scheduling are a supported hypothesis | Need distinguish server execution/wait from client resumption before choosing optimization |
| CPU pressure but no measured OOM | Parent2.969/3cores,532/573throttled periods; risk0.672/1,PG2.079/4,no throttle; VM minimumavailable774938624bytes,noOOM | Shared application CPU pressure is present; RAM allocation change unsupported by this run | Aggregate throttle is not per-SQL latency; host compression alone is not causation |

Per-SQL measured positions, five slowest and five median-neighborhood cycles of
same2transaction shape for each source retained in `source-query-analysis.json`.
No concurrent transaction durations are summed into an individual latency. SQL
roundtrip is contained within body time, not added again. BOOK28extraTRADEcycles
remain in raw/aggregate evidence. Comparison against prior source-stage run is
NOT a speedup claim: instrumentation differs and no optimization was applied.

Safety/correlation review: `realtime_storage._locked` takes publication fence before
feed-row lock and checks owner/generation/expiry after waiting. `renew_writer` and
`write_price` postchecks protect against expiry while waiting on writes. The first
fence cannot be removed; later row checks cannot simply be skipped. Catalog and
role checks are not assumed redundant. No production code or financial logic changed.

Evidence integrity:424cycle records (<2400),noINCOMPLETE,all measured SQL labels
known. Two cutoff-cancelled source cycles retained explicitly (BOOK1/PRICE1).
Recording time1.927s is cumulative setup/load/tail, not a per-item latency and not
zero overhead. Source input receipts use actual commit timestamps; cycles starting
before measurement explain commit-count versus completed-cycle-count differences.
Clockchecks bracket VM within hostsend/receive. Cleanup logs retain CancelledError
warnings;12pool files finalized with0checked-out,postrun database connections0,
only originalPG/Redis containers remain. No repeated diagnostic.

**Outcome: evidence insufficient to choose a safe optimization that addresses the
10Hz gap.** It now rules out “first fence alone” and narrows the missing information
to backend execution/wait versus application resumption for the same query index.
Do not start another workload automatically. If a further measurement is authorized,
use ONE60s same-config set with bounded publisher task/event-loop lag and read-only
backend PID/wait-event observations joined to these query timestamps (no SQL text,
parameters or extra SQL in financial transactions). Validate correlation/bounds
first; sampling cannot claim exact unsampled server durations. Estimate15–25min
including preparation/setup/analysis. This is a proposal, not authorization or a
promise that a further trace will prove a fix. No resource/criteria change proposed
without that attribution; no W1–W4 launched. Existing W1 load-evidence gap,W2Failed,
W3/W4pending,F18PendingFullValidation and V22/V23PendingDependency unchanged.
Round completed13:52UTC,~17min from13:35:03UTC,within14–26min estimate.

### 2026-10-29 — approved backend/loop attribution diagnostic
Owner “เริ่มทำ” authorizes ONE60s same-configuration diagnostic proposed above.
Started13:53UTC; estimate15–25min including setup/analysis. No optimization/W1–W4.
Existing source timeline now obtains backend PID from driver metadata (no SQL),
records10ms heartbeat callbacks bounded6000, and launches one read-only same-role
backend observer in the SAME existing CPU/memory group. Observer connection uses
no new role/grants,20ms target sampling,3000sample/15backend bounds; safe state,
wait-event,query-start/state-change/server-clock fields only, never query text or
parameters. Observer process is needed to see database state during publisher loop
stalls; its additional connection/CPU overhead remains part of measurement, not free.
Observation is optional outside source diagnostic. Tests21passed including real
PID/PgSleep correlation and cleanup; ruff/format4files passed, mypy591passed.
Only annotations/context formatting changed after passing tests (no runtime logic).
Isolated DB ready; preflight only originalPG/Redis. Artifacts:r30-source-waits-20261029.

#### Backend/loop attribution result — one run, no automatic repeat
Source tree8c9a1382d7bf2027db30e0a0ed338da2f26e75db375db56c8969fe8f6de4bf49.
Setup13:56:55.112–13:59:53.993UTC=178.881s; measured nominal60s,
controller61.063s including cancellation/join. WINDOW_COMPLETE,acceptance_resultfalse.
1088offered/1007admitted/1006completed/0rejected/166cycles; unfinished work retained,
RESET not exercised, no financial-oracle or W2-pass claim.

| Symptom | Evidence | Conclusion | Gap/limitation |
|---|---|---|---|
| Source below10Hz |268BOOK and158freshprices perBTC/ETH in fixed60s;4.467Hz/2.633Hz;157completedPRICEcycles mean373.248ms | Source-load gate still fails | No acceptance workload run |
| Real first-fence wait | PID-matched samples show267active/Lock/advisory observations inside measured SQL intervals; PRICEcycle3021 firstfence269.37ms shows advisory wait followed by idle | Initial publication-fence contention exists | Sampling is not continuous lock-duration measurement; do not remove financial fence |
| Client-side waiting is independently visible |146query intervals have post-start idle state with query-start/state-change guards;124are non-fence. BOOKcycle3076ROLE_CHECK106.486ms, backend13601idle/ClientRead at sample95.13ms before return. PRICEcycle3201PRICE_WRITE72.603ms has post-start idle and overlapping89.57ms heartbeat lag | Not all SQL roundtrip time is database computation or lock wait; publisher resumption contributes | Cannot distinguish all GIL/event-loop/driver/OS causes or promise process isolation fixes all |
| Publisher loop delayed while independent observer responsive |2859heartbeats,p50lag6.403ms/p9535.682ms/max131.547ms;2465observer samples,queryroundtrip p500.702ms/p955.690ms/max75.223ms | A dedicated publisher loop/process is an evidence-supported single experiment | Shared cgroup CPU quota remains; observer also has gaps up to75.298ms |
| Resource constraints unchanged |Parent2.966/3CPU,533/574throttled periods;risk0.664/1,PG2.061/4no throttle;VM minavailable773791744bytes,no swap delta/OOM | No RAM allocation increase justified by this result | Throttle aggregate not assigned as per-query latency |

Join method: same Linux monotonic clock and nearest measured wall anchor; observed
server clock mapped into query intervals with5ms guards on both boundaries. Idle
attribution also requires query_started>=clientstart−5ms and state_changed>
clientstart+5ms, excluding stale prior-query states.762/6800retained query intervals
have a sample. Counts are observations, not a latency percentage. SQL text and
parameters never read by observer; only current-role/current-database backends.
The827.878msROLE_CHECK at PRICEcycle3273 begins AFTER nominal window end, in a cycle
that began before cutoff; retained as tail work, with no observer/heartbeat coverage,
and NOT treated as unexplained measured-window evidence or discarded.

Evidence complete within caps:425cycle details,noINCOMPLETE;observerCOMPLETE,
2465<3000samples,2859<6000heartbeats. One PRICEcycle canceled retained. Recorder
2.087s cumulative setup/load/tail, additional observer work included in shared budget.
No before/after speedup claim against prior differently instrumented run. Full
source-stage/query/wait-join JSONs and five slowest/five median same-shape cycles
retained underr30-source-waits-20261029; adjacenthost/clock/memory/log artifacts.
12pool files finalized with0checked-out; postrun DB connections0; only original
PG/Redis containers remain. Cutoff CancelledError warnings remain in log.

**Decision: enough evidence for ONE targeted method proposal; do not keep adding
unfocused diagnostics.** Prepared [R31](../publisher-process-amendment.md), Proposed,
for one dedicated fixture publisher process in the same existing CPU/RAM cgroup,
with bounded acknowledged controls/receipts and explicit shared connection ceiling.
Reuse source loops/storage/fences; no production/business/schema changes. Risk:
shared quota may still dominate; IPC/control ordering, tail evidence and extra
process overhead require targeted checks. Same-instrumentation inline/child pair
only after approval, then stop/rollback if unsupported. Estimate38–62min for that
separate implementation/test/comparison checkpoint, not F18 closure. Existing R12
forbids a new process and plan requires method amendment: do not implement yet.
W1historical evidence retains load gap,W2Failed,W3/W4pending,F18PendingFullValidation,
V22/V23PendingDependency remain. No criteria/resource relaxation or W1–W4 started.
Round finished14:07UTC,~14min from13:53UTC (estimate15–25min). Tests21passed,
ruff/format4files and mypy591passed. Stopped at proposed-method approval boundary.

### 2026-10-29 — R31 approved implementation and paired trial
Owner approved R31; implementation began~14:07UTC, estimate38–62min. Extracted
native publisher loops into profile_publisher.py and bounded process/control
transport into profile_publisher_process.py. Inline remains default; child is
CLI-gated to the source diagnostic until its load gate passes. No production
SQL/fence/formula/API/schema changes. Source pool3/overflow0 and parent5/overflow7
share the prior15connection ceiling; both modes use the identical split.
ACK controls preserve order, fail on sequence gaps/timeout/duplicate start; graceful
stop/restart preserves cursors/identities and commit receipts. Source process PID
is included in full resource inventory, separate from restartable Paper/risk list.
R31 runner copy adds the existing isolated risk process to that sample inventory;
old runner/evidence unchanged. Connection churn includes the moved publisher pool.

Development finding: an initial fail-on-full receipt queue rejected an existing
history burst in the reusable test DB. Replaced with bounded await/backpressure
and5s timeout (no silent drop); cleanup CLOSE acknowledges cleanup even after a
source failure, while run() retains the original failed outcome. No workload ran
on the failing implementation. Initial process tests failed3; corrected tests pass.
74unique targeted tests passed across r31-targeted.xml and r31-safety.xml. The
first combined invocation had17fixture-resolution setup errors (no test execution),
resolved by invoking that risk-only subset with its conftest scope; raw error XML
retained. Coverage includes both publisher modes, control ordering/timeout/bounds,
child death, no duplicate writer, receipts/restart, final readiness, financial
rollback/fence, lease expiry, transient breach/latch and pending replay idempotency.
Ruff/format5affected files passed; mypy594files and7architecture contracts passed.

Before timing: native source loops/storage callers and transport lifecycle reviewed;
no unresolved safety finding identified in this scope. Prepared two fresh isolated
DBs and identical runners differing only output/DB/container identity and mode.
ONE60s inline then ONE60s child sequentially; no acceptance/W1–W4. Estimate remaining
13–22min including both setups and analysis. Do not claim performance improvement
against prior instrumentation or repeat failing runs. Child process/IPC overhead
counts inside existing3CPU/1536MiB group; diagnostic read-only observer also remains.

#### R31 comparison stopped at baseline setup failure
Frozen source77cd04dd9be4477279b444d096e4571b525fc18dcf055b8f8b2039a301a31c10.
Inline setup14:29:28.716–14:32:17.905UTC=169.189s,exit1; SourceUnavailableError:
“book readiness cannot be proved” at native order_book_storage.publish_input →
BookState.require_ready. No MEASURED_WINDOW, no60s diagnostic result, no started
command cycles; baseline did not reach2000orders/load-ready checkpoint. No child
run or automatic retry. Prepared child DB remains unused. Source loop kept native
freshness guard; no weakening or new trading behavior introduced.

| Symptom | Evidence | Conclusion | Gap |
|---|---|---|---|
| Book rejected during setup | Stack +setup167bucket BOOKcycle1.625510s; DB_CLOCK1.033938s; other successful SQL role13.322ms,threebook-lock reads215.128ms total,lease-renew119.209ms | Native source readiness could not be established; paired trial cannot be completed | Setup only has aggregates, no per-query PID/heartbeat/wait samples; do not claim exact server-vs-client attribution |
| Earlier source stalls in same setup | BOOKsetup165cycle1.288879s,commitACK845.492ms; PRICEsetup165cycle2.226310s with onefence1.243896s | Readiness failure occurs amid broader delays, not proof of an IPC regression (inline uses no child IPC) | R31 changed pool split and source extraction; old-run comparisons cannot isolate contribution |
| Host/app pressure | Last15s:6resource samples, parent2.895/3CPU,105/132throttled periods; VM minavailable893837312bytes,zero swap/major-fault/OOM deltas.8host samples with711018compressions,619249decompressions,11818swapins,13724swapouts (16KiBpages) | Multiple pressure signals coexist | Host paging/throttle alone is not a per-item cause; no resource change authorized |
| Cleanup complete |13pool files finalized0checked-out; database connections0; only originalPG/Redis containers remain | No orphan workload left | No acceptance or financial-oracle pass inferred |

Artifacts:r31-inline-20261029/failure.json,source-timeline.jsonl (402setupSECOND
buckets,0CYCLEdetails),source-commits.jsonl,manifest,pools; adjacentlog/memory/host/
clock. Read-only failure analysis in setup-failure-analysis.json. Failed transaction
stage aggregate zeros mean no completed COMMIT, NOT zero elapsed time; safe-label
query counters separately retain its successful calls. All failure evidence kept.

R31 implementation and targeted checks are complete; performance validation is
INCOMPLETE. Inline remains default, child is diagnostic-only. The process hypothesis
was not tested, so neither improvement nor regression of child is claimed.
Appended a Proposed/NOT APPROVED execution exception to R31: one child-only60s
feasibility/source-gate diagnostic on the frozen candidate, no inline retry and
no before/after claim, estimate6–10min. Original paired-trial stop rule requires
owner approval of that exception. No code/resource/criterion amendment proposed.
W1historical load gap,W2Failed,W3/W4pending,F18PendingFullValidation unchanged.
R31 round stopped14:37UTC,~30min elapsed; shorter than38–62min estimate because
baseline setup invalidated the paired trial. No second workload or repeated tests
were launched after this failure.

### 2026-10-29 — approved one child-only feasibility diagnostic
Owner approved execution exception; started14:38:34UTC,estimate6–10min.
Frozen source77cd04dd9be4477279b444d096e4571b525fc18dcf055b8f8b2039a301a31c10
verified before launch. Only originalPG/Redis running. No code/resource/criteria
change, no inline repeat, no before/after performance claim; stop after this set.

#### R31 child-only result — source-load gate FAILED; stopped
Same frozen hash verified in manifest; modechild,R10+R22,monitor4 and original
resource limits. Setup14:38:51.996–14:41:37.406UTC=165.410s. Nominal60s window
14:41:37.406–14:42:37.406UTC; controller elapsed63.350s including delayed completion/
cancellation/join. Exit0/WINDOW_COMPLETE/acceptance_resultfalse; no failure.json.
This is a diagnostic completion, NOT acceptance success. No inline retry, W1–W4,
new optimization, resource/criteria change or further measurement.

Used the existing cadence_summary oracle offline with actual fixed60s boundaries,
not controller elapsed or receipt delivery time. Results in source-load-gate.json:

| Channel | Actual unique commits | Required | Hz | Max commit gap | Result |
|---|---:|---:|---:|---:|---|
| BOOK BTC/USDT |559|600|9.3167|1.224648s|Failed|
| Fresh PRICE BTC/USDT |370|600|6.1667|1.288057s|Failed|
| Fresh PRICE ETH/USDT |370|600|6.1667|1.288057s|Failed|

Completed cycle timing:BOOK559cycles mean60.275ms,p95154.686ms,max903.266ms;
PRICE370cycles mean156.099ms,p95358.060ms,max1946.089ms. These distributions do
not replace per-input/SLA criteria or hide source gaps. Price first publication
fence mean80.638ms,p95210.110ms,max1130.606ms; it is~51.7% of whole price-cycle
mean. Observer joins include1041active/Lock/advisory samples, so there is direct
server-wait evidence. Sample counts are NOT time percentages. Remaining first-
fence interval can also include transport/client scheduling; do not remove fences.

Heartbeat4054samples:lagp500.954ms,p9525.855ms,max327.744ms. Observer2288samples,
queryroundtripp950.007941s/max0.261613s and maxsamplegap0.266215s.390/15149retained
query intervals have samples;25have qualifying post-start idle observations.
NoINCOMPLETE marker,929cycle details<2400; observerCOMPLETE. Recorder3.561s
cumulative setup/load/tail. No speedup or causality claim against prior runs:
the matched inline baseline never reached its measurement window.

Resources include childPID12 in all11full process samples. Parentgroup CPU sampled
3.030core-equivalents (sampling interval approximation, configured limit remains3),
552/569throttled periods; risk0.700/1,PG2.120/4. VM minimumavailable698994688bytes,
noOOM,swapin4pages/swapout0; host compression/swap activity retained separately.
No inference that paging alone caused the remaining misses. No allocation change.

Progress/evidence:974offered,881admitted/881completed,0rejected,123completed cycles.
Offered/uncompleted work remains visible; this does not certify all command-cycle
or stop deadlines. Scheduled RESET and full financial/acceptance oracles were not
exercised. Native error/retry logs retained.6041PRICEframe records are ordered and
unique,IDs1..6041,matching read-only database count/min/max after cleanup: no price-
frame receipt lost in this run.13pool inventories finalized0checked-out; database
connections0; only originalPG/Redis containers remain. Child stopped, no orphan.

Artifacts:r31-child-20261029/source-load-gate.json,source-stage-analysis.json,
source-query-analysis.json,source-wait-join.json,rawtimelines/commits/inputs,
manifest/resources/pools/diagnostic; adjacentmemory/host/clock/log. Analysis import
path initially needed an absolute PYTHONPATH; fixed offline invocation only, no
code/workload retry. No tests/static rerun because code is unchanged.

**Decision:** R31 child feasibility run completed but required source cadence failed.
Keep inline default and child diagnostic-only; do not promote it or claim the
isolation hypothesis proven. Next work should identify financial fence holders/
critical sections from existing evidence before proposing one change; current wait
samples identify the waiting publisher but not the blocking transaction identity.
Do not guess a financial-writer change, repeatR23 blindly, or weaken freshness/
financial checks to pass. Any new measurement or method needs a concrete scoped
proposal; none started here. W1historical load gap,W2Failed,W3/W4pending and
F18PendingFullValidation remain; V22/V23PendingDependency separate from Paper.
Round closed14:46UTC,~7.5min from14:38:34UTC,within6–10min estimate.

### 2026-10-29 — R32 approved cadence change, no workload
Owner “ปรับเกณฑ์ใหม่” confirms the preceding5Hz proposal. Approved
[Paper source cadence amendment](../paper-source-cadence-amendment.md), linked from
requirements/plan/validation and explicitly superseding only the F18fixture10Hz
rule. W1/W2/W3 expected unique source counts without price fault exemptions are
3000/1500/9000 perchannel.100owners×20orders,command rates,R25–R29SLA/freshness/
financial/authentication/fence/resource/duration/overflow gates unchanged.

Implementation: SOURCE_HZ=5 and derived200ms period in existing observation helper;
shared inline/child SourcePublisher uses that period, oracle uses the same target,
manifest and cadence evidence expose5Hz. Existingover_100ms retained as descriptive
legacy metric; over_target_period added separately. No F15standalone/production
feed,storage,financial or schema change. R31child remains diagnostic-only and inline
default. No workload/diagnostic/W1–W4 launched and no historical result relabeled.

Validation:r32-targeted.xml34passed/0errors/0failures (10.265s test execution):
5unique commits pass,4fail,duplicate/drain exclusion,price-only fault exemptions,
live readiness,source/native publication and process controls/restart/tail cleanup.
Ruff/format4changed Python files passed; mypy594files passed;7architecture contracts
kept. Existing callers/dependencies reviewed; no added production behavior. Evidence
r32-mypy.log/r32-imports.log in existing artifact root. Round~5min, within3–8min
estimate; no full regression repeated for this test-only criterion change.

Evidence consequence: prior10Hzresults remainFailed/Partial; even observed6.17Hz
under an attempted10Hzload is NOT certification of a5Hzcandidate. Source-path/load
changed, so W1–W3 need final-candidate evidence when their prerequisites are met;
W4/regression reuse only with unchanged contracts. Any next timed run requires its
explicit scoped checkpoint/preflight and announced estimate; none started here.
F18PendingFullValidation; Paper and Completed/V22/V23 dependencies remain distinct.

### 2026-10-29 — approved R32 acceptance sequence: first short gate
Owner explicitly requested execution of the5Hz acceptance plan: one inline60s W2
source gate, then W1→W2→W3→W4 only if preceding gates pass; stop on failure without
automatic retry. Started14:57:18UTC; first-stage estimate8–12min, conditional total
85–120min excluding fixes/CI/manual waiting. No child fallback or allocation change.
Frozen sourceb03b85789d9448a84b1c225affbc288af65a924b158b48ae0d0b7c21fbae5764;
runner hashes in r32-preflight.json. R32tests34/static evidence reused: no subsequent
code change. OriginalPG4CPU3GiB/Redis1CPU256MiB only before launch; app remains
3CPU1536MiB+risk1CPU512MiB,monitor4,sourcepool3+parent12,100×20,R10+R22.
Fresh isolated DB prepared; run artifactprefixr32-inline-20261029. No workload
already running. Source gate counts300unique commits/channel in nominal60s and
requires complete receipts/no source-control failure/complete cleanup; diagnostic
is not risk/financial/RESET acceptance. No W1 automatically on failure.

#### R32 first short gate FAILED — acceptance sequence stopped
Schema0058 and manifest sourceb03b85789d9448a84b1c225affbc288af65a924b158b48ae0d0b7c21fbae5764
verified; target5Hz,modeinline,monitor4. Setup14:57:59.879–15:01:26.200UTC=
206.321s. Fixed nominal window15:01:26.200–15:02:26.200UTC; controller60.883s
including cancellation/join. Exit0/WINDOW_COMPLETE/acceptance_resultfalse means
diagnostic ended, NOT gate success. No failure.json; source cadence failed below.

| Channel | Unique commits / required | Hz | Max gap | Verdict |
|---|---:|---:|---:|---|
| BOOK BTC/USDT |188/300|3.1333|1.746847s|Failed|
| Fresh PRICE BTC/USDT |122/300|2.0333|2.190814s|Failed|
| Fresh PRICE ETH/USDT |122/300|2.0333|2.190814s|Failed|

Existing cadence_summary used fixed60s and5Hz; no fault exemption, drain extension,
identity duplication or catch-up padding. source-load-gate.json retains all gaps
and counts. BOOK188completed cycles mean302.953ms,p95755.960ms,max1714.683ms;
PRICE121completed cycles mean486.353ms,p95894.226ms,max2764.323ms,plus1cutoff-
cancelled cycle explicitly retained. Nominal200ms period is still exceeded by
source work; changing the target did not establish the required throughput.
First PRICEpublication fence mean63.153ms of486.353ms cycle; it is not the sole
bottleneck.219sampledactive/advisory waits AND192qualifying post-start idle query
intervals show both server waiting and client-resumption components. Heartbeat
lagp95=45.564ms,max418.824ms (rawsource-wait-join.json).
Observer2385samples,p95roundtrip7.598ms,max137.024ms;840/5047query intervals have
samples. Do not assign unsampled time or aggregate throttling to a single item.

Resource observations: parent2.960/3core-equivalents,518/571throttled periods;
risk0.662/1,PG2.040/4. VM minimumavailable765251584bytes,noOOM,swapin1page/out0.
Host1906143compressions/1863564decompressions and3127swapins/1948swapouts at16KiB
pages during window. These coexist with delays, not proof that host paging alone
caused them. No changes to CPU/RAM or concurrent diagnostic.

Evidence/cleanup:310cycle details<2400,noINCOMPLETE,observerCOMPLETE,recorder2.154s
cumulative setup/load/tail.3017ordereduniquePRICEframe receipts IDs1..3017 match
postrun databasecount/min/max;no duplicateBOOKreceipt identities.13pool inventories
finalized with0checked-out; DBconnections0; only originalPG/Redis containers remain.
CutoffCancelledError cleanup warnings retained in log. Offline analysis script
copied a child-PID check inappropriate for inline; removed that analysis-only check
and verified inline cleanup directly, without changing code or rerunning workload.

Counters901offered,814admitted/814completed,0rejected,105completed cycles. Outstanding
offered work is not a successful deadline result. ScheduledRESET and full financial/
risk/stop acceptance oracles were not exercised; no false safety/acceptance pass.
Artifacts:r32-inline-20261029/source-load-gate.json,source-stage-analysis.json,
source-query-analysis.json,source-wait-join.json,rawcommit/timeline/manifest/resource/
pool/diagnostic evidence; adjacenthost/memory/clock/log. No fresh tests/static needed.

**Stop decision per approved plan:** no repeat, no child fallback, no W1/W2/W3/W4,
no regression/final-review acceptance continuation. Inline5Hz source-load gate is
Failed. R31child's10Hzattempt is not a comparable5Hzresult and cannot certify this
candidate. A possible next proposal is a specifically authorized child5Hz feasibility
check using the existing implementation; not started or promoted automatically.
Do not lower freshness/financial criteria or infer another numeric relaxation from
this result. Current plan cannot proceed until source gate has valid evidence.
W1historical evidence retains prior load gap; W2Failed; W3/W4pending; F18PendingFullValidation,
with V22/V23PendingDependency and remoteCI/manual still distinct.
Round stopped15:04UTC,~7min from14:57:18UTC; shorter than8–12min estimate because
the first gate failed and acceptance sequence was not started.

### 2026-10-29 — authorized R32 child5Hz feasibility check
Owner “เริ่มทำ” authorizes the proposed ONEchild5Hz60s diagnostic after inline gate
failed. Started15:05:46UTC,estimate6–10min. This explicit follow-up allows that one
mode check, not automatic acceptance-mode promotion/W1–W4 or retries. Source
b03b85789d9448a84b1c225affbc288af65a924b158b48ae0d0b7c21fbae5764 verified unchanged;
R32tests/static reused. Only originalPG/Redis running. Same3CPU1536MiB parentgroup
+risk1CPU512MiB,monitor4,sourcepool3+parent12,100×20,R10+R22,5Hz/W2bounded plan.
Fresh isolated database and r32-child-20261029 artifacts; no runtime edits.

#### R32 child5Hz short source gate PASSED — acceptance not yet run
Manifest verified unchanged sourceb03b85789d9448a84b1c225affbc288af65a924b158b48ae0d0b7c21fbae5764,
childmode5Hz,monitor4,R10+R22 and original allocations. Setup15:06:12.688–15:08:46.869UTC
=154.181s. Fixed nominal60s15:08:46.869–15:09:46.869UTC; controller60.561s includes
cancellation/join. Exit0,WINDOW_COMPLETE,acceptance_resultfalse,no failure.json.

| Channel | Unique commits / required | Hz | Max gap | Short cadence verdict |
|---|---:|---:|---:|---|
| BOOK BTC/USDT |300/300|5|0.292794s|Passed|
| Fresh PRICE BTC/USDT |300/300|5|0.499703s|Passed|
| Fresh PRICE ETH/USDT |300/300|5|0.499703s|Passed|

Existing cadence_summary oracle used nominal window and realcommit timestamps,
not receipt-delivery/cycle counts. Gap distributions remain in source-load-gate.json;
200ms is the target interval, not a new max-gap exemption. No claim that one run
establishes a reproducible speedup or future acceptance success.

Evidence integrity:600cycle records below2400cap,noINCOMPLETE,observerCOMPLETE;
recorder2.185s cumulative setup/load/tail.3212orderedunique PRICEframe receiptsIDs
1..3212 exactly match postrun DBcount/min/max; source receipts retained. ChildPID12
present in all11process-resource samples.13pools finalized0checked-out; database
connections0; only originalPG/Redis remain. No source/control failure reported.
Counters1289offered,1192admitted,1190completed,0rejected,197completed cycles; two
admitted-but-uncompleted plus other offered work remain visible at diagnostic cutoff.
This is NOT proof of all request/stop deadlines, risk SLA, financial or RESET gates.

27container-resource samples: parent2.994/3core-equivalents,567/578throttled periods;
risk0.695/1,PG2.065/4. VM minimumavailable717070336bytes,noOOM. These are observations,
not a substitute for full resource/endurance acceptance. Source/control and receipts/
cleanup parts of the approved short gate passed; noW1–W4 or further workload run.

Artifacts:r32-child-20261029/source-load-gate.json,source-stage-analysis.json,
source-query-analysis.json,source-wait-join.json,rawtimelines/receipts/inputs,
manifest/resources/pools/diagnostic and adjacenthost/memory/clock/log. Existing
R32tests/static reused; no code changes or repeated tests.

Next concrete proposal:[R33](../child-acceptance-mode-amendment.md),Proposed: explicitly
select existing childmode for acceptance and W4build, remove diagnostic-only CLI
guard, preserve all resources/criteria and run already-approved acceptance sequence
conditionally. Do not apply before approval: R32 and original sequence specified
inline/default and childdiagnostic-only. This is a mode decision, not repeated
permission for R31/R32. Proposed firstW1checkpoint17–22min; fullconditional sequence
85–120min excluding fixes/CI/manual. F18PendingFullValidation; historical failures,
V22/V23PendingDependency and requiredCI/manual remain unchanged.
Round completed~15:12UTC,~6min from15:05:46UTC,within6–10min estimate.

### 2026-10-29 — R33 approved child acceptance, W1 first
Owner approvedR33,including conditionalW1→W2→W3→W4→regression/final review. Began
15:13:08UTC;firstW1checkpointestimate17–22min. Removed workload CLI diagnostic-only
child restriction; explicitchildmode retained (defaultinline compatibility,no fallback).
W4build now accepts/records publishermode/targetHz/sourcehash and uses acknowledged
source_control(price=80) so child receives breach price. Verify reports captured
buildmode. No production/storage/financial behavior change. Specs link R33modeoverride.
14targeted mode/process/restore-role tests passed (r33-mode-tests.xml);ruff/format3files,
mypy595passed. R32source gate reused: only entrypoint/W4metadata/control propagation
changed,not source scheduling or oracles; no repeat diagnostic. Reviewed affected
callers/cleanup/process inventory. Existing architecture checks remain valid; no
new dependency direction introduced. Frozenhash/runner/config in r33-preflight.json.
W1freshDBschema0058,onlyoriginalPG/Redis beforestart;child5Hz,100×20,10commands/s,
600s,original resources/R10+R22/monitor4,NOdiagnosticflags. Run one set and stop on
failure; later gates conditional,not separate approval requests.

#### R33 W1 result — FAILED; stop before W2
Artifact: `/Users/chainarongjaykeaw/Projects/TiewTrade/validation-artifacts/f18-20261027/r33-w1-20261029/result.json`.
Frozen source `c5c240339ca88299459fa043f51b293077bd43b0d4ffef85284f703182226ab4`, explicit child mode, no diagnostic tracing.
Setup 15:15:49–15:18:43 UTC; nominal measurement 15:18:43.621989–15:28:43.621989 UTC (600s); controller/drain elapsed 612.895s. Exit 1 with complete FAILED result, not an interrupted run.

| Symptom/gate | Evidence | Conclusion | Gap/next step |
|---|---|---|---|
| Source cadence | BOOK 3000/3000; BTC and ETH PRICE each 2999/3000; max book gap 0.704652s, price gap 1.508783s | Strict R32 fixed-window price count fails by one/channel | Inspect existing boundary receipts and publisher scheduling before proposing a change; do not pad window or round count |
| Per-owner risk service | 2/100 owners fail 99.9%: 36/9220 misses (99.6095% within3s), 18/9220 (99.8048%) | Separate real acceptance failure, not resolved by source-count correction | Late inputs cluster 15:26:21–15:27:36 UTC; failing owners concentrate 15:26:21.785–15:26:29.717. Existing evidence does not yet isolate lock/CPU/sweep cause |
| Global risk/hard limit | 141/922005 above3s; max4.846914s; 0 above5s, 0 unacknowledged, 0 clock errors; idle coverage complete | Global99.9% and hard5s pass; aggregate cannot replace per-owner gate | Preserve all inputs and late-input evidence |
| Processing | p95 320.478ms, p99 547.506ms | Pass500ms/1s | No processing criterion adjustment justified by this run |
| Commands/financial | 6000 offered/admitted/completed, 0 rejected;1200 cycles; RESET100/100;100/100 owner oracles and global invariants pass; no duplicate fill effects, invalid reservations/positions or wrong mode | These gates pass on this candidate | Not blanket financial acceptance for W2–W4 |
| Drain/resources | live baseline pass, resource assertions pass, pools returned, DB cleanup0 remaining; only original PG/Redis containers remain | Cleanup completed; shutdown lag4 is reported separately from successful live readiness | No workload remains active |
| Report metadata | required_book_inputs still duration*10 (=6000), while actual acceptance uses cadence SOURCE_HZ=5 (=3000) | Stale descriptive field in harness; not the cause of FAILED because it is not in passed expression | Correct in next scoped harness fix with affected report checks; no code changed after freeze |

Stopped acceptance sequence as authorized: no W2/W3/W4, no repeat diagnostic, no allocation/criteria/runtime changes. Next step is one bounded read-only analysis of existing late-input/worker/resource and source-boundary evidence, separating the two failed gates; if timing correlation is insufficient, specify one missing measurement before requesting any new run. Do not rerun hoping for a pass. R33 mode remains approved; historical results unchanged. F18 remains Pending Full Validation; V22/V23 and required CI/manual remain pending.
Round checkpoint recorded 2026-10-29T15:31:23.016595+00:00; elapsed since15:13:08UTC approximately 18.3min (estimate17–22min).

### 2026-10-29 — R34 approved; reuse W1 under explicit revised criteria
Owner accepted the combined proposal (“ตกลงตามนี้”): one missing source commit per
channel/run, per-owner99.5% within3s for Paper W1–W3, global99.9% and everyinput5s
unchanged. Amendment paper-acceptance-tolerance-amendment.md records scope before
implementation. Only cadence_summary, sla_summary/report metadata and tests changed.
R34 current source c859511017d7266cb97061ac9f24cfa7595335dc183e5e3e53fa7607d76d7971.
Reversing precisely those evaluator/test edits in memory reproduces R33 whole-tree
hash c5c240339ca88299459fa043f51b293077bd43b0d4ffef85284f703182226ab4 exactly;
proof r34-source-proof.txt. No publisher/runtime/dependency/schema change.
40 oracle tests +24 quota tests passed (r34-oracles.xml,r34-quotas.xml),ruff/format
passed and mypy595 passed. Default diagnostic/CHECK cadence remains strict; approved
W1–W3 explicitly select one-commit allowance. All actual counts/gaps remain visible.

W1 R34 reassessment PASSED in separate r34-w1-reassessment.json, recomputing source
cadence and SLA from original journals via temporary read-only links; original
result and late-input file untouched. All other result gates checked:6000complete,
RESET100,100ownerfinancial/global oracles,3scenarios,processing,duration,livebaseline,
resources,pools and connectioncleanup. Original R33 verdict remains FAILED under
its original criteria. PRICE2999 is accepted by R34, not rounded to3000; per-owner
36/9220 and18/9220 now pass995/1000; global/hard5s remain passing. No missing inputs.
W1 evidence reused only because runtime is byte-identical; evaluator delta recorded.

Next W2 estimate10–15min including setup,300s bounded100commands/s and overflow/
recovery. Fresh DBtiewtrade_f18_release_r34_w2_20261029 schema0058; explicit child,
no diagnostic flags, original resources. OnlyPG/Redis before start. One run,
stop on any failed gate; no automatic rerun. W3/W4 conditional. F18PendingFullValidation.

#### R34 W2 — PASSED
Artifact r34-w2-20261029/result.json, same c8595110…source. Setup15:41:52–15:44:28UTC;
nominal300s through15:49:28; fullcleanup/result~15:51UTC (~9min, estimate10–15).
R28bounded demand and exact identities pass;6145offered/admitted/completed0rejected,
1229cycles;RESET100/100. Book1500,prices1499/channel meet R34 without padding.
Risk477763/477763acknowledged,60above3s,0above5s,max4.578930s,allowner995/global999
quotas pass. Processingp95=.377204s,p99=.569424s.100ownerfinancial/globaloracles pass,
no duplicate effects/invalidpositions/reservations/wrongmode. Overflow4097inputs:
injection63.2966s,recovery2.3654s,verification2.6295s,total68.2915s; economics unchanged.
Livebaseline,resourceassertions,poolsreturned andcleanup0remaining pass; original
shutdown lag5 retained. W3next35–40min including1800s fault/endurance window; same
candidate,childmode,resources,originalRediscontainer/faultschedule,oneworkload only.

#### R34 W3 — FAILED/INCOMPLETE; sequence stopped, no W4
Artifact r34-w3-20261029/failure.json and original log retained. Setup15:51:51UTC;
1800s nominal load began15:54:40.629733,expected end16:24:40.629733. Last BOOK commit
16:23:11.358993,PRICE BTC/ETH16:23:11.424390; failure journal16:23:24.043412UTC
(~1723.4s of1800,not a completed30min run). Error F18_SOURCE_CHILD_FAILED.
All7scheduled faults RECOVERED;RESET100/100. Counters at stop13911offered,
13875admitted/completed,0rejected,2760completecycles; unfinished work is retained,
not treated as completed/deadlinepassed. No final risk/RSS/financial acceptance
result,so partial observations cannot certify W3. No automatic rerun/W4/regression.

Read-only failure review: profile_publisher_process.py:215–221 sends done/ok=false
when source.publish raises; read_events replaces it with generic CHILD_FAILED;
CLOSE gathers the publication exception with return_exceptions=True. Consequently
its underlying exception type/code is absent from evidence. Earlier worker DB55P03
logs do not prove the publisher's cause. Do not infer CPU/RAM/lock cause from them.
Identified actionable harness gap: preserve a bounded allowlisted exception category
and source stage on child failure, without SQL/parameters/exception messages/secrets,
and test that the parent retains failure classification while failing closed and
cleaning up. This is the next scoped proposal, NOT implemented in this stopped round;
no new workload/diagnostic/settings/criteria changes. Root publisher cause remains
unknown until evidence supports it; lowering acceptance thresholds cannot fix this.

Cleanup verified: publisher pool finalized0checkedout,onlyoriginalPG/Rediscontainers,
0otherDBconnections toW3database. W1R34reassessment andW2PASS remain valid for unchanged
runtime; keep their evidence and do not automatically repeat. W4/finalregression/review,
requiredCI/manual remain pending;V22/V23PendingDependency,F18PendingFullValidation.
W3 round to failure/cleanup~32min,within35–40min estimate; full sequence stopped early.
Checkpoint updated 2026-10-29T16:25:29.585033+00:00.

### 2026-10-29 — approved publisher failure-evidence follow-up
Owner instructed “เริ่มทำ”; scoped to failure evidence and targeted checks, no timed
workload. Reused SourcePublisher.publish and existing done IPC message. Failure-only
publisher-failure.json stores bounded allowlisted category,ACQUIRE/BOOK/PRICE/PUBLISH,
UTC and monotonic timestamps; first failure retained, unknown classes/stages sanitized.
Parent RuntimeError retains validated category/stage. No exception text/chains/SQL/
parameters/secret output; original source exception still raised, sibling cleanup and
normal cancellation preserved. No retry/scheduling/resources/financial/oracle change.
Plan appended approved scope before edits.14publisher/process tests passed,including
stage attribution3cases,redaction,realIPCparent/CLOSE propagation and normal cancellation;
existing inline/child DBreceipt/restart,control ordering/timeouts and boundedqueue checks
included. ruff/format passed,mypy595passed. One test import typing issue fixed; after
expanding fixed categories to actual DB/source classes,6affected evidence tests passed.
Artifact publisher-failure-tests.xml. This fixes observability only,not the unknown
root cause of R34W3; no claim that W3 now passes. No workload/diagnostic launched.

Next measurement proposal: one W3 run on same configuration with this failure-only
reporter, original1800s/faultschedule; captures source stage and safe category if the
failure recurs, or full W3oracles if completed. Estimate35–40min inclsetup/cleanup.
No short diagnostic is proposed because prior failure occurred~28.5min and there is
no shorter proven trigger. Do not repeat automatically if it fails. W1/W2 evidence
retained; exact source delta must be recorded before reuse on final candidate.
W4/regression/finalreview/CI/manual andV22/V23 status remain unchanged.
Follow-up completed 2026-10-29T16:29:16.011453+00:00, approximately5min against10–15min estimate.

### 2026-10-30 — one authorized W3 cause-reporting run; host Idle Sleep confirmed
Run r34-w3-cause-20261029 on hash8afb55a0f564a303be76c7f1e4572cbd54c2bbef88af7a4fef11e5edac745588,
originalchild5Hz100×20/resources/R34criteria, freshschema0058. Beforestart onlyoriginal
PG/Redis. Setup16:31:48UTC,load16:34:15.444483UTC,planned1800s. Failure16:57:37.054945UTC
(~1401.6s measured; FAILED/INCOMPLETE), publisher-failure.json at16:57:36.679714:
PRICE/OTHER. No retry/W4/otherworkload.5/7faultsRECOVERED,RESET100/100;10886offered,
10858admitted/completed,2161cycles,0rejected; incomplete inputs retained,not passed.
Cleanup: onlyPG/Rediscontainers,0otherW3DBconnections. No fullSLA/RSS/financial verdict.

Read-only evidence established a host interruption, not a reason to relax thresholds:
- macOS pmset log:2026-10-29 23:55:22+0700 EnteringSleep due to IdleSleep;wake23:57:07,
  105seconds onAC. Host sampler wall-time gap104.405517s; otherlargestgap2.047502s.
- Last durableprice16:55:54.027214UTC,book16:55:54.225644; lastDBresource sample
 16:55:53.784935. Durablefeedlease expired16:55:59.003173UTC. These DB/host timestamps
  must not be treated as a precise cross-clock lock-duration measurement during sleep.
- Captured raw selected powerlog r34-w3-host-sleep.txt also shows priorW3's host
 IdleSleep23:22:48–23:23:05 (17s),near its publisherfailure23:23:24. Historical failures
 remain unchanged. Evidence supports environment interruption in both runs,not a
 proven exact exception or proof that runtime has no defect.
- PRICE's native WriterLeaseLost is not in the initial diagnostic allowlist; OTHER
 remains unknown. Lease expiry is consistent with sleep but not asserted as captured
 exception. Do not change financial fences or add retry on this inference.

Next concrete proposal: run the sameW3 once with a temporary host idle-sleep assertion
(e.g. caffeinate tied to the runner lifetime), verify assertion beforeload and release
oncleanup; no permanentpmset changes,resources,criteria orruntime changes. Estimate
35–40min. No newrun launched in this round. Do not repeatW1/W2 solely for this host
control; preserve their candidate/evidence mapping. F18PendingFullValidation,W4 and
remaininggatespending. Current authorized one-run checkpoint is closed.
Checkpoint recorded 2026-10-29T17:01:18.933874+00:00; round approximately30min inclfailure analysis, below35–40min full-run estimate.

### 2026-10-30 — awake W3 run failed final recovery; snapshot clock corrected

One authorized W3 run used `caffeinate -dims` tied to the host runner. Before load,
`pmset -g assertions` proved `PreventUserIdleSystemSleep`,
`PreventUserIdleDisplaySleep`, `PreventSystemSleep` and `PreventDiskIdle` belonged
to that runner; the assertions released when it exited. The host sampler's largest
gap was 2.094047s and the power log had no sleep/wake event during the run.

Run `r34-w3-awake-20261030` used source
`8afb55a0f564a303be76c7f1e4572cbd54c2bbef88af7a4fef11e5edac745588`, fresh schema
0058, child 5Hz, original resources and fault schedule. Setup began 00:03:54 ICT;
the 1800s window began 00:06:24. Faults 1–6 recovered. The final worker restart
began 00:32:39, dependencies restored 00:33:20, then `live_baseline` timed out at
00:34:21 before the nominal window ended. RESET was 100/100. At stop: 13604 offered,
13515 admitted, 13514 completed, 0 rejected; unfinished work remains failed evidence.
No publisher failure occurred. The run is FAILED/INCOMPLETE and supplies no final
risk/RSS/financial acceptance verdict. W4 was not started. Cleanup left only the
original PG/Redis containers and zero other connections to the run database.

Read-only failure analysis found all 100 owners READY and beyond the captured input,
with no replay pending, while 23 owner rows reported source freshness false. Book
publication continued at 5Hz. `live_baseline` used one REPEATABLE READ snapshot but
compared its frozen source row against a new `statement_timestamp()` in each of 100
sequential owner SELECTs. Once inventory reading exceeded one second, later rows
aged the harness's own snapshot and the all-owner predicate could not pass. This is
a measurement defect, not evidence for relaxing the trading or performance criteria.

The scoped correction replaces those observed/lease/freshness comparisons with
`transaction_timestamp()`, one database time for the entire recovery snapshot. It
keeps the same 1s freshness rule and does not change production SQL, runtime,
resources, retry, deadline, financial logic or thresholds. A regression test proves
transaction time remains fixed while statement time advances across a 1.05s slow
read. The existing committed-source/owner-progress tests also pass: 12 tests total,
ruff/format pass and mypy 595 files pass (`r34-snapshot-clock-tests.xml`). Final
source hash is `20ebe42f493e463fb68f5a776965583d9685c7cda55b9d09530af5ee7ab4dbb0` (766 files).

W1 R34 and W2 remain valid: their original snapshot checks passed even with the
drifting, stricter observation, and production/runtime dependencies did not change.
Per the explicit stop rule, no automatic W3 retry follows this failed run. The next
candidate action is one W3 run with the same temporary sleep assertion and corrected
snapshot clock, estimated 35–40 minutes. W4/regression/final review remain conditional;
F18 remains Pending Full Validation, with V22/V23 and required CI/manual still pending.

### 2026-10-30 — R34 W3, W4 and local final gates passed

The one authorized corrected W3 run used source tree
`20ebe42f493e463fb68f5a776965583d9685c7cda55b9d09530af5ee7ab4dbb0`, schema 0058,
explicit child publisher, 5Hz, 100 owners x 20 orders, the approved fault schedule and
the original resource limits. A runner-scoped `caffeinate -dims` assertion was verified
before load and released on exit; it did not change container resources. Artifact
`r34-w3-snapshot-20261030/result.json` is PASSED after 1817.302s. Book is 9000/9000;
BTC and ETH price are each 8880/8880 after only the approved 120 seconds of price-fault
exemptions. All seven faults recovered, 15000/15000 commands completed, RESET is
100/100, and all ready inputs are acknowledged. Risk has 2,275,709 expected and observed
inputs, 1,206 above 3 seconds, zero above 5 seconds, zero clock errors and no failing
owner quota; maximum is 4.658721s. Processing p95 is 0.278403s and p99 is 0.415441s.
Financial/global invariants, duplicate-effect, reservation, position, input-lag,
connection/pool cleanup and fixed-window RSS gates pass; RSS growth is 1.1107%.

W4 then used a fresh source database and separate fresh restore target, the same schema,
5Hz and explicit child mode. `r34-w4-verify/result.json` is PASSED: canonical digest,
schema/roles/column grants/RLS policies, risk recovery, authorization-only exact retry,
pending stop completion and economic digest all match. There are zero duplicate cancel
effects; wallet, ledger, reservations, positions and reset baselines are unchanged by
claim/stop recovery. The backup is 1,584,595 bytes. No Live order was submitted.

Final regression reconciled 3,970 current tests against the recorded 3,828-test R24
coverage: 3,800 node identities reuse unchanged passing evidence. Every newly collected
F18 risk/harness item was executed on the current tree. A first risk run on a reused test
database was invalid because 38 old PENDING/CLAIMED rows occupied the bounded scanner;
that run is retained but is not candidate evidence. On a fresh schema-0058 database,
298/299 risk tests passed. The sole failure proved a test-fixture freshness defect:
the reduction setup took 1.778s but published only a new book before asserting a
one-second source gate. The test now publishes its price with that book; the affected
case passes and does not change production code, financial logic, thresholds or runtime.
Thus the final risk result is 299/299 by the clean run plus the corrected affected case.
The separate acceptance-harness suite passes 101/101, and the reconciled API-key
permission test passes 15/15. The two Live venue contract tests remain deliberately
excluded from local automated validation under the existing no-Live rule.

Ruff and format checks pass for all 55 affected risk/harness files, `git diff --check`
passes, and all seven import architecture contracts pass. The earlier mypy result over
595 files remains valid because the only later source change is the typed test fixture
call above. Final source tree is
`ec1c855d2761ba26f273a4b62025c0681bc751012e04bd8e8e684badeb122c53` (766 files);
the delta from the W3/W4 hash is only that non-runtime test publication. Therefore the
W1-W4 acceptance evidence remains valid and no long workload is repeated.

Final review found no open Critical, High, Medium or Low implementation finding in the
F18 diff and affected contracts. Particular checks covered duplicate orders/effects,
quantity and Money precision, balance/position consistency, rollback/commit boundaries,
owner authorization/RLS, retry/idempotency, publication/financial fences, source outage
recovery and restore grants. Paper validation is PASSED locally on the approved R34
criteria. Required remote CI and manual acceptance remain Pending because no remote Git
operation was authorized. V-22/V-23 remain Pending Dependency, so this is not yet
`F-18 Completed` and does not authorize merge or production activation.

## Local Paper manual acceptance activation — 2026-10-30

Owner approved the local-only amendment. On Docker Compose project
`tiewtrade-f18-manual`, schema `0058`, the operator opened the protocol in order:

1. publication: watermark advanced from 0 and both BTC/USDT and ETH/USDT reached READY;
2. financial: the configured Paper owner converged to READY with replay_pending=false;
3. admission: a guarded update required both earlier flags, matching setting/evaluation
   revisions, at least one configured READY owner and no configured non-READY owner.

Post-activation evidence: all three flags true, owner
`f42fbdfb-f3bb-4840-b80c-af1dd81c6a18` setting/evaluation revision 2, READY,
replay_pending=false, publication cursor equal to watermark 11965 (lag 0). BTC/USDT
and ETH/USDT execution books were ready with current leases. Browser automation was
unavailable, so the owner must refresh and perform the manual submit observation.

This is localhost manual-acceptance state only. It is not V-21, production activation,
Completed or release evidence. Close in reverse order after the manual check.

The first browser check was additionally blocked by Binance TH execution capability:
`PERCENT_PRICE`, `MAX_NUM_ORDERS` and MARKET `MIN_NOTIONAL.avgPriceMins` were previously
fail-closed as `ORDER_UNSUPPORTED`. Owner approved NC-F15-13 and the scoped adapter,
weighted-trade window, constraint and metadata changes passed affected tests/static
checks. After rebuilding only market-data, API and Paper order worker, the real BTC
capability has empty MARKET/LIMIT unsupported rules and a complete five-minute weighted
reference. A read-only invocation of the same `/paper/trade` path for the local owner
returned `admission_ready=true`, no admission reasons, MANUAL use and an active Paper
wallet while BTC book, price and all three risk gates were ready. A transient public
price reconnect correctly returned `ORDER_PRICE_UNAVAILABLE` and then recovered; it was
not bypassed. The agent did not submit an order. Browser submit observation remains the
owner's manual action and this evidence does not replace remote/full validation.

Follow-up manual-runtime correction removed two false unavailability loops without
bypassing a safety gate. F-10's approved same-millisecond amendment treats distinct
validated stream trade identities as distinct executions in connection frame order;
same-identity conflicts and cross-generation recovery remain fail closed. F-15
NC-F15-14 accepts at most 100ms public execution source clock skew after raw evidence
showed Binance TH leading the host by 8–10ms. The approved 30-second book boundary is
now used consistently before and after publication. Finally, execution bootstrap loads
capability and the five-minute weighted trade window before taking the current depth
snapshot, then replays the already-buffered stream; this prevents history pagination
from ageing the snapshot before its first bridge.

Affected results are 111/111 core/adapter/matching tests, 10/10 real-role F-10 service
tests and 3/3 real-role execution-pipeline tests, plus ruff/format, mypy over 236 source
files and diff check. On the rebuilt localhost runtime, BTC/ETH books and latest prices
were READY together for every one of 12 samples over 30 seconds. The same read-only
trade-view path returned `admission_ready=true` with no reasons for BTC/USDT. All three
local risk flags remained true. No order was submitted by the agent; the owner still
performs the final browser action.

Final local-gate checkpoint recorded 2026-10-30T00:13:06Z. The regression/static/final
review stage took approximately 13 minutes against the 10–20 minute estimate.

### 2026-10-30 — required CI exposed missing PostgreSQL capability

Commit `a3c141a3d1e2f9f5173cfc0f7ab49ba80a2a9183` was pushed to the F18 branch and
required CI run `40985534822` executed the committed candidate. PostgreSQL version,
frontend lint/types/tests, container composition, API contract and all browser E2E
jobs passed, including the F18 production-composition E2E. Backend ruff, format,
mypy, import contracts, bootstrap and migration also passed. Full backend pytest
finished with 3,961 passed, two deselected and seven failed after approximately
16 minutes.

All seven failures have the same infrastructure root cause. The GitHub Actions
PostgreSQL service did not enable `track_commit_timestamp`; the F18 publication
fixtures therefore received SQLSTATE 55000 from `pg_xact_commit_timestamp(xmin)`.
The child-publisher failures are downstream reports of the same book publisher
exception. This is not a financial, order, risk-policy or production-runtime
failure. The accepted local candidate and workload databases explicitly used commit
timestamps, and the harness preflight already rejects an acceptance run without them.

The scoped correction configures only the backend CI PostgreSQL service: it uses
`ALTER SYSTEM`, restarts that service before bootstrap/migration, and verifies
`SHOW track_commit_timestamp` is `on` before continuing. It does not change the
public API, schema, production business logic, resources, acceptance criteria or
trading behavior. The seven affected tests and workflow syntax/static checks must
pass before the correction is pushed; required CI must then run again on the new
commit. On a fresh schema-0058 database with commit timestamps enabled, both affected
fixture modules pass 20/20 tests in 12.45 seconds; `git diff --check` also passes.
The first remote run remains FAILED evidence and F18 remains pending required
CI/manual acceptance and V22/V23.

### 2026-10-30 — Local Paper protocol reopened for owner manual check

The localhost Docker database was found safely closed after the stack restart: all three
protocol flags were false and the last risk price frame was about 8h27m old. The configured
Paper owner still had a 500 USDT setting and was not latched. Operator activation followed
the approved order rather than forcing admission: publication first, then financial only
after the watermark advanced and the owner evaluated READY, then admission with a guarded
all-configured-Paper-owners READY check.

Post-activation, all three flags are true; the watermark advanced from 101949 to 102175,
the owner setting/evaluation revisions are both 2, evaluation is READY, both replay flags
are false, and the observed frame age was 67ms. The final read caught an ordinary one-frame
publisher/evaluator tail (102175 versus 102174), within the approved API tail check. No
Paper or Live order was submitted by this activation. This remains local manual-acceptance
state only and must be closed in reverse order after the owner finishes the check.

### 2026-10-30 — Loss-limit settings moved to Trading account

The approved UI placement clarification now reuses the existing `RiskLimitPanel` on
`/trading-account`, immediately after the Paper wallet. `/paper/trade` keeps only the
current compact loss-limit value and, when the value is unset, links to Trading account.
The trade page still shows admission blocking and an active risk-stop beside the order
form; no financial rule, API, schema, owner/mode scope, latch or reset behavior changed.

Affected frontend verification passed: seven test files and 96 tests, TypeScript
typecheck, scoped ESLint and the production Vite build. The build retained the existing
large-chunk warning. This UI check does not replace remote CI or outstanding F18
acceptance evidence.

### 2026-10-30 — Trading account risk card simplified

The approved compact-card clarification reduces the ready state to authoritative limit,
adjusted loss, readiness/latch status, last evaluation time and one Adjust limit action.
Allowance, baseline, realized result, revisions, episode and technical timestamps remain
available in an admin-template-derived disclosure. Reset is under More actions; refresh
appears only for failed or unavailable evidence. Pending recovery continues polling with
no action buttons, while UNKNOWN exposes status lookup first and keeps exact-key retry and
the request identity inside Request details. No remaining-limit value is invented in the
browser because the API does not provide one.

Affected verification passed: seven frontend test files and 97 tests, scoped ESLint,
TypeScript typecheck and the production Vite build. The build retained the existing
large-chunk warning. No API, schema, Money, TOTP, latch/reset, polling or idempotency
behavior changed.

### 2026-10-30 — Trading account risk card reduced to one input and Save

The approved compact-form amendment replaces the ready-state summary/actions with one
authoritative loss-limit input and one Save action. Exact fixed-point parsing determines
SET, DECREASE or INCREASE without JavaScript floating point. Only INCREASE opens the
existing TOTP modal. Polling cannot overwrite a dirty draft; a changed revision, wallet
or episode requires the user to accept the latest snapshot. APPLIED remains blocked
until its matching snapshot revision arrives, while REJECTED retains the draft and does
not update the authoritative value optimistically. Reset remains contextual to a latched
limit, and durable UNKNOWN/AUTHORIZATION_ONLY recovery preserves the original intent and
idempotency key.

Affected verification passed in approximately four minutes: 57/57 targeted pure,
component, account-caller and session/recovery tests, frontend ESLint, TypeScript
typecheck, production Vite build and diff whitespace check. The build retained the
existing large-chunk warning. The Playwright risk flow was updated but could not run:
the repository safety guard rejected the local environment before server/browser start
because no isolated `tiewtrade_e2e...` database was configured. Browser automation was
also unavailable even though the localhost dev route returned HTTP 200. Those E2E and
desktop/mobile, theme, language and keyboard screenshots remain Pending and are not
replaced by the passing unit tests. No API, schema, Money, TOTP, latch/reset, polling or
business rule changed.

### 2026-10-30 — Recovery details folded into the compact Save flow

The approved recovery-UI amendment removes UNKNOWN, protocol states, request UUIDs,
status/retry buttons and the request-details disclosure from the main risk-limit card.
An outstanding durable attempt now keeps its exact amount in the disabled input. While
the lookup or engine request is pending, Save is disabled with one short user-facing
status. If the prior result is still unknown, Save retries the original intent and key;
it cannot create a new UUID or substitute the current draft/snapshot amount. Unknown
INCREASE still requires a fresh TOTP, while server-confirmed AUTHORIZATION_ONLY reuses
the existing authorization without collecting another code. APPLIED/snapshot revision,
REJECTED, journal, owner/mode scope and reset safety remain unchanged.

Affected verification passed: 60/60 targeted amount, component, account-caller and
session/recovery tests, frontend ESLint, TypeScript typecheck and the production Vite
build. The build retained the existing large-chunk warning. The previously recorded
isolated-E2E-database and browser-automation limitations remain Pending; unit tests do
not replace those gates. No backend, API, schema, Money, TOTP policy, latch/reset,
polling, order or Live behavior changed.

### 2026-10-30 — Recovery status made visually hidden

The approved hidden-status amendment removes the remaining visible recovery sentence
from the compact form. The same status remains `sr-only` and is referenced by the input
and Save button for assistive technology. Pending still disables both controls, while a
safe exact-key retry enables Save without exposing protocol text. Recovery, TOTP,
idempotency and authoritative snapshot behavior did not change.

Affected verification passed: 60/60 targeted tests, frontend ESLint, TypeScript
typecheck, production Vite build and diff whitespace check. The build retained the
existing large-chunk warning. Browser/E2E limitations remain Pending as previously
recorded.

### 2026-10-30 — Stale local recovery now clears without user action

The approved stale-recovery amendment removes the final recovery step from the normal
user flow. A local attempt is discarded only when the exact-key lookup returns
RISK_REQUEST_NOT_FOUND and the authoritative revision/wallet/episode identity differs
from the attempt's expected identity. The form then synchronizes the authoritative
limit and unlocks without posting the old attempt or allocating a UUID. Matching
identity, network/storage errors, authorization-only, pending and terminal states remain
fail closed and retain exact-key recovery.

Affected verification passed: 62/62 targeted amount, component, shared durable-caller
and account/session tests, frontend ESLint, TypeScript typecheck, production Vite build
and diff whitespace check. The build retained the existing large-chunk warning. No
backend, API, schema, Money, TOTP policy, order, latch/reset or Live behavior changed.

### 2026-10-30 — Fulfilled local recovery now unlocks automatically

The approved fulfilled-recovery amendment extends the safe local discard predicate for
the observed localhost case: when exact-key lookup returns RISK_REQUEST_NOT_FOUND and a
non-RESET attempt's exact fixed-point amount already equals the authoritative limit, the
desired state is already present and the local journal is discarded even if its scope
identity still matches. Comparison uses the existing BigInt-scale parser, not raw text
or floating point. The path performs no POST, UUID allocation or optimistic write.
Different amounts, RESET, invalid data and non-not-found errors retain recovery.

Affected verification passed: 64/64 targeted amount, component, shared durable-caller
and account/session tests, frontend ESLint, TypeScript typecheck, production Vite build
and diff whitespace check. The build retained the existing large-chunk warning. No
backend, API, schema, Money, TOTP policy, order, latch/reset or Live behavior changed.

### 2026-10-31 — Paper increase no longer asks for TOTP

The approved Paper increase amendment keeps the durable request/worker path but makes
second-factor authorization mode-specific. PAPER INCREASE is authenticated and CSRF
protected, writes a normal idempotent inbox request with no authorization row, and is
still checked against revision, wallet/episode scope, current amount, market evidence
and the owner financial lock before the engine applies it. LIVE INCREASE retains its
fresh exact-intent TOTP authorization and authorization-only recovery path. Migration
0059 enforces this split for new rows, preserves legacy Paper authorization links with
a `NOT VALID` transition constraint, and refuses downgrade once an authorization-free
Paper increase exists.

The compact Paper form now sends an increase directly from Save and retries an unknown
Paper increase with the same key without opening a modal or attaching a TOTP header.
The same component still opens the TOTP modal for LIVE. No optimistic setting update,
Money calculation, latch/reset rule, scheduling, order path or Live-order capability
changed.

Verification passed on an isolated PostgreSQL database: 53 affected API, route,
request, worker and profile-fixture tests;
45 frontend risk/account/session tests; backend Ruff and focused strict mypy; frontend
ESLint, TypeScript typecheck and production Vite build; migration 0058→0059→0058→0059;
the downgrade data guard; compile and diff whitespace checks. The existing Vite
large-chunk warning remains. Timed W1–W4 were not rerun because cadence, financial
calculation and worker scheduling did not change. The local API, risk worker and
frontend were rebuilt and healthy on migration 0059.

### 2026-10-31 — READY label hidden in the compact limit form

The approved UI amendment removes the `พร้อม` / `Ready` badge only when the snapshot
reason is READY. Warning, unavailable, stale, latched, stop, loading and error states
remain visible. No request, recovery, TOTP or financial behavior changed.

Verification passed: 20/20 RiskLimitPanel tests, frontend ESLint, TypeScript typecheck,
production Vite build and diff whitespace check. The frontend container was rebuilt;
the existing Vite large-chunk warning remains.

### 2026-10-31 — Manual acceptance isolated from workload data

The previously reused `tiewtrade-f18-manual` database could not safely complete the
browser acceptance. Read-only inspection found one NEW request transferred from intake
but still PENDING in order dispatch after 35 retries. The database contained 20 Paper
risk settings; 19 evaluations were READY and one was latched at
`RISK_LOSS_LIMIT_REACHED`. Risk-monitor logs also contained repeated DATABASE_TIMEOUT
deferrals. The execution source temporarily reported BTC RECOVERING, then both BTC and
ETH were READY for all six samples over a bounded 30-second observation. This is not a
UI-button failure and does not justify bypassing the source or risk gates.

The local protocol was closed in the required order. A guarded reopen stopped after
publication because the existing latched owner meant the all-configured-owner READY
precondition failed; financial and admission were never reopened. Publication was then
closed again. Final old-database flags were all false, and no request, order, wallet or
financial row was deleted or rewritten.

The old Compose project was brought down without removing its volume. A separate
`tiewtrade-f18-manual-clean` project was built from current HEAD with its own fresh
PostgreSQL and Redis volumes. Migration is 0059, all three protocol flags are false,
the users table is empty, and PostgreSQL, API and risk-worker health checks pass. This
clean stack is available at `http://localhost:5173`; the owner must create the local
account, Paper wallet, MANUAL use and loss limit before the approved activation sequence
can be run. The agent will not submit an order on the owner's behalf.

Remote CI run 40987641082 passed for commit 462d424. Current HEAD is three commits ahead,
so that run cannot certify the latest candidate; no push was performed without an
explicit owner command. W1–W4/local Paper evidence remains applicable as previously
recorded, while final current-head CI, browser order observation and V-22/V-23 remain
pending.

### 2026-10-31 — Paper MANUAL loss limit made optional (R35)

The approved optional-limit amendments allow only Paper MANUAL opening orders to proceed
without a configured loss limit. The path does not create a default setting, evaluation,
baseline or audit substitute. Intake and every execution pass re-read the setting; a
setting created after intake immediately returns the order to the configured evaluation,
price, latch and stop rules. Live and BOT retain the existing configured-limit contract.

Production-composition testing exposed the old 0052 database guard, which rejected every
unconfigured BUY before evaluating its financial boundary. Approved R35 migration 0060
removes only that obsolete rejection. The trigger still requires the same F18 publication
shared lock, owner/wallet/episode transaction claim and finalized boundary. A direct
unfenced position writer still receives TT028, while the real request → command → order →
fill path completed exactly one fill with a 9,900 USDT balance and no risk setting,
evaluation or baseline rows. A downgrade with that unconfigured economic history was
refused and left revision 0060 installed. Empty-schema downgrade/upgrade/upgrade replay
and the single-head/order checks passed.

Affected verification passed: 72 core risk/matching tests; the focused closed and optional
API paths; the real unset-to-SET race; request-to-fill, downgrade-data guard and unfenced
writer boundary; 27 of 28 configured boundary/execution/concurrency/fence regressions;
backend Ruff and focused strict mypy; 21 RiskLimitPanel tests, the affected Paper trade UI
test, frontend ESLint, TypeScript typecheck and production build. The remaining configured
regression is the pre-existing wall-clock `stale` variant: its 1.05-second sleep did not
cross the source's stale boundary on this run. The other transient-breach, disconnect and
protocol-disable variants passed. It was not rerun to obtain a timing-dependent pass and
does not indicate a new financial or order mismatch.

Timed W1–W4 were not rerun because this amendment does not change cadence, scheduler,
configured-owner financial calculations or workload resources. Current-head remote CI,
browser observation and V-22/V-23 remain Pending; no Live order was submitted and no
commit or push was performed.

The localhost `tiewtrade-f18-manual-clean` stack was rebuilt on migration 0060. Local
Paper activation then followed the previously approved sequence: publication advanced
the watermark from 2; both BTC/USDT and ETH/USDT execution sources were READY with current
leases; the two configured Paper settings had matching READY evaluations and no replay
pending state; financial was opened; both cursors caught watermark 135; admission was
then opened with the same guarded checks. Final flags are true/true/true, the configured
cursors caught watermark 153, API health is OK and `/paper/trade` returns HTTP 200. This
is local manual-acceptance state only. No Paper or Live order was submitted by the agent;
the owner must perform the browser submit observation, after which flags must be closed
in reverse order.

### 2026-10-31 — R36 quiet optional-limit form

The approved R36 UI amendment removes the normal Paper-unset helper sentence without
replacing it with a badge or alert. The card retains only its heading, associated loss-limit
label, input and Save action in the normal state. The shared admin-template-derived form is
now a one-column/full-width action layout on mobile and a flexible input plus fixed action
column from the `sm` breakpoint; Input and Save both use the existing 44px control height.
Live-unset guidance, validation, stale/conflict, load failure, latch/stop and visually hidden
recovery status remain unchanged.

Affected verification passed in under one minute: 41/41 `RiskLimitPanel` and
`TradingAccountPanel` tests, frontend ESLint, TypeScript typecheck, production Vite build
and whitespace checks. The existing large-chunk build warning remains. The localhost
frontend image was rebuilt and the route is available; browser automation remained
unavailable, so desktop/mobile visual observation is Pending and was not replaced by the
component tests. No API, schema, financial rule, order, recovery or Live behavior changed.

### 2026-10-31 — R35/R36 owner UI observation and affected review

The owner completed the current localhost account flow in a real browser: selected MANUAL,
created a Paper wallet with a valid initial balance and saved a Paper loss limit. The owner
reported the flow passed. This closes the wallet/create-and-save UI observation only; it
does not claim the separate unconfigured-limit browser order-submit criterion, remote CI or
V-22/V-23.

The affected review found one High matching-boundary defect before handoff: intake limited
the unset exception to MANUAL, but matching checked only the global gates and could have
filled a pre-existing BOT BUY while the limit was unset. Matching now requires
`OrderOrigin.MANUAL` for that exception as well. A regression constructs an already queued
BOT order without weakening admission and proves it remains ACCEPTED with no fill.

Post-fix verification passed: 73 core risk/matching tests; 31 isolated real-PostgreSQL API,
boundary and execution tests on migration 0060; backend Ruff, format and focused strict
mypy; 62 affected frontend risk/account/Paper-trade tests; frontend ESLint, TypeScript and
production build. The Paper-trade polling test was corrected to await the React Query DOM
commit before checking its hidden status, removing a test race without changing runtime
behavior. The existing Vite chunk-size warning remains. No workload was rerun because the
fix changes neither scheduler/cadence nor configured-limit calculations.

After the observation, the local manual stack was returned to its safe default in the
required order: admission, financial and publication were disabled in separate commits;
the final control row is `false/false/false`. The isolated review database was then dropped
after confirming it had no active connections. The manual-acceptance volume was preserved.

The owner then approved the affected refactor. The identical three-gate query is now in
`infra.risk_limits.control` and is reused by intake policy, the trade view and the financial
worker; the API risk-reason precedence is expressed as explicit branches instead of a
nested conditional. No policy, SQL predicate or response value changed. Verification passed
31/31 isolated real-PostgreSQL API/boundary/execution tests, focused Ruff/format/mypy,
all seven import-linter contracts and whitespace checks. The temporary refactor database
was dropped after confirming zero active connections; frontend evidence remains valid
because no frontend source changed during refactoring.

### 2026-10-31 — Remote CI remediation after R35/R36 refactor

Remote CI run `41166198702` exposed two deterministic verification issues rather than a
runtime or financial failure. Backend stopped at the format gate because migration 0059
contained one multiline call that the current CI Ruff version formats on one line. Frontend
reached the full Vitest suite, where six `ApiKeyPanel` recovery cases mounted the expanded
account dashboard but their fetch fixture did not model the Paper risk endpoint; the
resulting unrelated risk alert made the account-alert assertion fail.

Migration 0059 now matches Ruff's required formatting. The API-key test fixture returns a
typed, unconfigured Paper risk snapshot for the dashboard dependency, preserving the test's
original focus on API-key and trading-account recovery without suppressing runtime alerts.
Verification passed: the affected API-key file 33/33, the complete frontend suite 339/339,
frontend ESLint and TypeScript typecheck, focused migration Ruff check/format and whitespace
checks. No production behavior, API, schema, trading rule or financial calculation changed.

The next remote run passed those frontend and backend static gates, then exposed four stale
manual-order browser assertions from the approved compact workspace. One selector treated
the chart's accessible data table and the order table as the same element; two assertions
still required request/order UUIDs that the UI intentionally hides; and the storage-denial
shim was lost by the test's own page reload. The E2E now scopes overflow to the order table,
checks the retained idempotency identity in session storage and unresolved-request API
instead of restoring hidden technical UI, and installs the storage shim as a persistent
Playwright init script. Frontend ESLint and TypeScript typecheck pass after these test-only
changes. Production code and the recovery/idempotency protocol are unchanged.

The following CI attempt confirmed the four updated assertions (six of seven manual-order
browser cases passed) and exposed one pre-existing readiness race: the disconnect-before-
commit case attempted to click while the asynchronously refreshed form was still disabled.
All E2E submits now reuse one helper that waits for the existing submit action to become
enabled before clicking. This changes neither the readiness predicate nor its timeout in
the application; it only makes the browser driver observe the same prerequisite a user
must satisfy. Frontend ESLint and TypeScript typecheck remain green.
