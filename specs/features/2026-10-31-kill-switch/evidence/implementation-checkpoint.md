# F-19 — Implementation checkpoint

วันที่: 2026-10-31
Branch: `feature/f-19-kill-switch`
Candidate: F-19 development checkpoint; Pending Full Validation / Required CI

## ขอบเขตที่เขียนครบ

- shared stop policy, durable user/platform STOP/RESUME inbox, append-only audit และ
  PostgreSQL shared/exclusive admission fences
- Paper target discovery/effects/retry โดย reuse F-18 consumer, historical revision fence,
  repeated stop generation และ platform bounded owner discovery
- owner/platform API, recovery lookups, stable effects pagination, strict inputs และ generated OpenAPI
- ปุ่ม Paper/Live แยกกันทุกหน้า, durable unknown-outcome journal, summary/effects/resume,
  platform admin page และ persistent platform/loss banners
- Live authority คง fail-closed โดยไม่มี executor และไม่มี automated Live order

## หลักฐานที่ผ่านบน source ปัจจุบัน

- isolated PostgreSQL database `tiewtrade_f19_test`: affected backend regression 184 tests ผ่าน
  (`core/trading_stops`, trading-stop persistence, audit/API routing, F-18 stop/concurrency,
  manual-order bridge และ execution worker)
- F-19 + F-18 stop focused rerun 29 tests ผ่านหลัง final RLS/cursor/empty-inventory fixes
- frontend 35 files / 340 tests ผ่าน; `typecheck`, ESLint และ production build ผ่าน
  (build มี warning chunk >500 kB เดิม ไม่มี build failure)
- backend `ruff format --check`, `ruff check`, `mypy src` (244 files) และ
  import-linter 7 contracts ผ่าน
- generated `backend/openapi.json` และ `frontend/src/api-types.ts` ใหม่จาก source ปัจจุบัน
- isolated database `tiewtrade_f19_migration`: `upgrade head → downgrade 0060 → upgrade head` ผ่าน;
  database ที่มี stop history ปฏิเสธ downgrade ด้วย `trading stop history prevents downgrade`

## Defects ที่ targeted validation พบและแก้

- engine ขาดสิทธิ์อ่าน immutable inbox และเคยใช้ row lock ที่ต้องมี UPDATE privilege
- platform resume result ถูก RLS ซ่อนจาก owner อื่น ทำให้ global stop ไม่เคยปลดสำหรับคนอื่น
- platform operator คนถัดไปอัปเดต global cause เดิมไม่ได้ และ scan role ขาดคอลัมน์ resume proof
- platform audit ใช้ `NOT_APPLICABLE` ไม่ผ่าน generic trading invariant
- platform progress ไม่ refresh หลัง discovery complete และ cursor เคยข้าม owner ที่สร้าง target ล้มเหลว
- platform resume ส่ง stop revision แทน progress snapshot revision
- F-18 loss-stop writer ไม่ระบุ shared `LOSS_LIMIT/ALL` หลัง migration
- user stop ที่ไม่มี Paper wallet เคยค้าง `STOPPING` แม้ inventory ว่างได้รับการพิสูจน์แล้ว
- UI เคยปิด resume modal ตั้งแต่ receipt ยังเป็น `REQUEST_PENDING`

## Validation ที่ยังค้าง

- required remote CI บน committed candidate ตาม V-19
- full set-5 validation V-20
- V-21 real TP/SL, V-22 bot lifecycle, V-23 Live execution และ V-24 notification channels
  ยังคง Pending Dependency ตาม validation ที่อนุมัติ

### V-20 workload stop schedule amendment — Approved 2026-10-31

- เจ้าของอนุมัติ amendment ให้คง core 100-owner workload, ใช้ dedicated stop owners, เก็บ
  platform-blocked commands เป็น positive oracle และใช้ conservation
  `completed + blocked_by_scheduled_platform_stop == offered`
- `validation.md` ระบุ W1/W2/W3 offsets, fault overlap, manifest binding และ non-fault denominator แล้ว;
  combined harness/targeted checks เป็นงานถัดไปก่อนเริ่ม timed workload

### V-20 resolved defect — repeated stop status resurrection

- `trading_stops.views.read_status` หา STOP ทุก generation ที่ยังไม่มี RESUME อ้าง exact ID แล้วเลือก
  revision ล่าสุด; หลัง repeated STOP generation ใหม่ถูก resume จึงย้อนกลับไปเลือก generation เก่าได้
- admission fence ใช้ latest generation ต่อ cause ก่อนตรวจ resume ทำให้ถือว่าปลดแล้ว; status/summary กับ
  authoritative opening policy จึงไม่ตรงกัน และ stale generation อาจกลับมาแสดงเป็น active
- ขัด RQ-07 repeated generation และ RQ-15 ที่ resume ต้องปิดเฉพาะ expected latest stop โดยคำสั่งเก่า
  ห้ามเปลี่ยน stop ใหม่; บล็อก W1 repeated-stop→resume oracle
- เจ้าของอนุมัติ production fix แล้ว; status เลือก latest STOP generation ของ cause ก่อนตรวจ APPLIED
  resume เช่นเดียวกับ authoritative admission query
- regression `test_resuming_latest_generation_does_not_resurrect_an_older_stop` ผ่าน และ storage
  regression ทั้งไฟล์ผ่าน 16/16; repeated-generation W1 targeted schedule ผ่าน

### V-20 workload harness checkpoint — 2026-10-31

- immutable W1/W2/W3 stop schedule, SHA-256 manifest, nested fault/stop gate และ conservation oracle
  เพิ่มแล้ว; real-DB W1/W2 schedule suite รวม schedule contracts ผ่าน 12/12
- W1 สร้าง queued MANUAL ก่อน cutoff แบบ owner-scoped และพิสูจน์ terminal
  `ORDER_SAFETY_UNAVAILABLE`, สร้าง partial BOT จริงก่อน stop และคง MANUAL post-cutoff oracle;
  W2 ครอบคลุม concurrent owners, exact duplicate, lost ack และ stale resume
- Ruff ผ่าน และ Mypy strict ผ่าน 612 source files; production behavior ไม่ถูกลดเกณฑ์
- raw evidence อยู่ที่ `validation-artifacts/f19-20261031/`: `w1-r1` หยุดที่ environment gate
  เพราะ shared PostgreSQL ไม่เปิด commit timestamps; `w1-r2` และ `w1-r3` Failed/Partial ก่อน
  measurement หลัง core baseline 20/20 จาก harness setup omissions (BOT origin/account-use และ
  dedicated BOT risk setting ตามลำดับ)
- dedicated PostgreSQL `tiewtrade-f18-release-f19-v20-postgres` ใช้ PostgreSQL 16,
  `track_commit_timestamp=on`, `max_connections=200`, 4 CPU/3 GiB และ Redis แยก;
  timed W1–W3 ยัง Pending Full Validation
- targeted `--stop-preflight` ระบุ `acceptance_result=false` และไม่เปลี่ยน W1 จริง: r1 หยุดก่อน
  worker เพราะ diagnostic conditional ผูกผิดกับ reset plan, r2 พบ F-18 breach/reset cycle ชนกับ
  compressed stop schedule จึงตัด cycle ที่ไม่อยู่ใน scope ของ preflight, r3 พิสูจน์ queued MANUAL
  rejection และ dedicated MANUAL/BOT baselines แล้ว แต่ post-cutoff MANUAL budget 100 USDT ไม่ถึง
  `FILLED` ภายใต้ partial fixture 0.5 BTC และ timeout ตาม bounded deadline
- แก้ post-cutoff oracle เป็น budget 10 USDT ซึ่งยังเป็น opening หลัง durable cutoff และเติมเต็มได้
  ภายใต้ fixture เดิม; เจ้าของอนุมัติรอบถัดไป และ preflight r4 ผ่านใน 20 วินาที
  (measured 10.11s) โดย `stop_preflight_only=true`, `acceptance_result=false`: queued MANUAL
  ถูก reject, post-cutoff MANUAL สำเร็จ, BOT partial/repeated generation/resume ผ่าน, MANUAL
  generation 2 ยังคง active และ invariants/cadence/resources ผ่าน
- Linux W1-r4 ผ่าน setup 100 owners ×20 baseline + dedicated MANUAL/BOT แล้วเริ่ม measured load;
  Failed/Partial ที่ +20s ก่อน F-19 schedule +50s ด้วย selected core owner LOSS_LIMIT generation 1
  เพียง cause เดียว: F-18 `breach → reset → reseed` ถูก durable system-stop fence ปฏิเสธตาม
  RQ-13/15/18 และ regression `test_loss_reset_does_not_resume_shared_stop_cause`
- เจ้าของปิด **NC-F19-04** โดยอนุมัติตัวเลือก 1: ย้าย loss proof ไป dedicated MANUAL owner
  นอก core counters และบังคับ `breach → reset → opening ยังถูกบล็อก`; คง core volume/rates,
  partial/correction เดิม และไม่เปลี่ยน MANUAL resume หรือ production stop policy
- แก้ harness ตาม amendment แล้ว: core 100 owners คง 5-command cycle/volume/rates โดย selected
  owner ยังทำ partial-fill + exact-correction; dedicated MANUAL loss owner อยู่คนละ dataset/counters
  และสร้าง `dedicated-loss.json` พร้อม stop identity/generation/reset/probe/financial marker/digest
- preflight r5 หยุดก่อน oracle เพราะนำ `recovery_stage` ที่ต้องอยู่ใน active core cycle มาใช้กับ
  dedicated pre-load scenario; เอาเฉพาะ timing wrapper ที่ผิดบริบทออกโดยคง bounded timeouts แล้ว
  preflight r6 ผ่านใน 10.10s measured (`acceptance_result=false`): partial จริง, LOSS_LIMIT generation 1,
  effects complete pending/failed=0, reset แล้ว opening ถูก `ORDER_SAFETY_UNAVAILABLE`, stop ยัง active,
  `resume_ready=false` และ compressed W1 stop schedule/conservation ผ่าน
- Linux W1-r5 ใช้ runner จำกัด 4 CPU ต่างจาก profile เดิมและ Failed/Partial ระหว่าง setup ที่
  1,627/2,000 baseline orders เพราะ inline publisher ต่อ writer lease 5s ไม่ทัน (`WriterLeaseLost`);
  ไม่มี measured/core/stop commands เริ่มและไม่ใช้ผลเป็น acceptance
- Linux W1-r6 คืน runner resource profile เดิม: setup 100 owners ×20, dedicated stop baselines,
  dedicated loss proof และ core partial/correction ผ่าน; W1 schedule พิสูจน์ queued MANUAL ก่อน cutoff
  ถูก `ORDER_SAFETY_UNAVAILABLE` แล้ว แต่ core F-18 gate Failed/Partial ระหว่าง measured load เพราะ
  owner cycle หนึ่งครบ timeout 60.016s (หลาย cycle 40–53s), ณ จุดหยุด offered=957,
  admitted/completed=867, rejected=0; ไม่ใช่ durable-stop rejection จึงคง W1 Failed และไม่รัน
  W2/W3 ต่อจนทบทวน capacity/core SLA โดยไม่ผ่อน threshold เอง
- read-only postmortem พบว่า W1-r6 เรียก default `publisher_mode=inline` แต่ F-18 validation
  ปัจจุบันอนุมัติ explicit child publisher ตาม R33; หลักฐาน R33 child เดิมทำ 6000/6000 commands,
  p95 320ms/p99 548ms บนเกณฑ์เดิม จึงยังไม่มีเหตุให้ลด SLA และ W1 ถัดไปต้องใช้ child mode
- พบ correctness gap แยกจาก throughput: schema 0061 มี position events 335 รายการแต่
  `trading_reconciliation_clock.revision=0`; controlled clone ยืนยัน trigger ไม่เพิ่ม revision เพราะ
  SECURITY DEFINER owner ติด FORCE RLS ขณะที่ clock มีเพียง SELECT policy เปิด NC-F19-05 เพื่อเลือก
  conditional active-platform-stop clock หรือ revision architecture อื่นก่อน W3/acceptance
- เจ้าของปิด **NC-F19-05** โดยอนุมัติ conditional active-platform-stop clock: normal trading
  ไม่ UPDATE singleton; trigger owner อ่าน active PLATFORM cause และเพิ่ม clock ใน transaction เดียวกับ
  position activity ผ่าน role-scoped FORCE RLS policies ต้องตรวจ inactive/active/rollback/stale resume
  ก่อน W3 และ W1 ถัดไปใช้ explicit child publisher ตาม F-18 R33 โดยไม่ลดเกณฑ์
- แก้ schema 0061 ตาม NC-F19-05 แล้ว: fresh PostgreSQL upgrade→downgrade 0060→upgrade 0061
  ผ่านใน 6.2s; targeted Ruff/Mypy ผ่าน และ `test_storage.py` ผ่าน 17/17 ใน 3.9s ครอบคลุม
  inactive no-write/API no-update, active increment, rollback atomicity, stale resume rejection และ
  exact fresh snapshot resume
- child preflight r7 ผ่านใน 29.3s โดย `publisher_mode=child`, schedule ผ่าน, dedicated LOSS_LIMIT
  ยังบล็อก opening และ artifact คง `acceptance_result=false` ตามข้อกำหนด
- Linux W1-r7-child ใช้ fresh schema0061, explicit child, core 100×20 และเกณฑ์เดิม แต่ Failed/Partial
  ระหว่าง setup ที่ baseline 17/20 ก่อน measured window (~368.5s): child source จบด้วย
  `F18_SOURCE_CHILD_FAILED:PRICE:OTHER`; PostgreSQL log ยืนยัน price writer รอ advisory lockจน
  statement timeout ขณะ Paper command หนึ่งรายการเกิด DB timeout ไม่ใช่ stop rejection
  (`offered/admitted/completed=0` เพราะ measured load ยังไม่เริ่ม) และ clock คง 0 เพราะยังไม่มี
  active platform stop ตาม inactive no-write contract
- ตาม R33 stop-on-failure ไม่ rerun W1 และไม่เริ่ม W2/W3; เก็บ artifact ที่
  `validation-artifacts/f19-20261031/w1-linux-r7-child/` ต้องวิเคราะห์ lock holder/resource
  composition หรือเพิ่ม bounded failure attribution ก่อนขอรัน acceptance รอบถัดไป ไม่ลด SLA
- bounded lock diagnostic r2 ใช้ fresh schema0061, child publisher, 100×20 setup และเปิด
  `log_lock_waits` เฉพาะฐาน diagnostic (`deadlock_timeout=100ms`); เป็น diagnostic เท่านั้น
  ไม่ใช่ acceptance และไม่มี measured commands เริ่ม
- PostgreSQL ระบุ lock key เดียวกับ W1 โดยตรง: source publisher PID 15719 ขอ ExclusiveLock จาก
  `risk_publication_fence()` ขณะที่ engine PID 15725 ถือ ShareLock จาก `risk_financial_fence()`;
  observed waits 4 ครั้ง สูงสุด 374.566ms (share รอ exclusiveหนึ่งครั้ง และ exclusive รอ shareสามครั้ง)
  จึงยืนยันว่าจุดชนคือ F-18 risk-publication/financial transaction boundary ไม่ใช่
  `trading_reconciliation_clock` singleton
- diagnostic ทำงาน 36.7s แล้วจบด้วย `BOOK:SourceUnavailableError` ระหว่าง setup หลัง source
  committed BOOK/PRICE อย่างละ 137 ticks; trace ก่อนจบมี book cycle max525.0ms, price max568.7ms,
  publication-fence query max354.2ms และ post-rollback source stateยัง READY ไม่มี deadlock
- ฐาน diagnostic มี 14,426 commits/14,136 rollbacks ระหว่าง migration+setup และ risk telemetry
  บันทึก 5,164 committed owner evaluations; container ไม่มี CPU throttle/OOM, peak usage521MiB,
  memory pressure avg=0 ขณะที่ reconciliation clock=0 และไม่มี PLATFORM cause ดังนั้นหลักฐานชี้
  transaction/owner-lock retry pressure และ publisher-vs-financial fence contention มากกว่า resource
  exhaustion หรือ NC-F19-05 hot-row regression
- diagnostic r1 ที่หยุดก่อน workload เพราะขาด `F18_PARENT_CONTAINER` เป็น runner-configuration
  precondition failure (users=0) ไม่นับเป็น workload result; r2 artifacts อยู่ที่
  `validation-artifacts/f19-20261031/source-lock-diagnostic-r2/`
- เปิด **NC-F19-06** ก่อนแก้ performance: แนะนำ bounded adaptive idle backoff/active wake-up
  สำหรับ stop/platform scans ใน risk worker เดิม แล้วพิสูจน์ stop-response bound, restart discovery,
  fairness และ F-18 workload เดิม; ทางเลือกแยก worker/pool ขยาย architecture/connection budget
  จึงไม่แก้หรือ rerun W1 จนเจ้าของเลือก
- เจ้าของปิด **NC-F19-06** โดยอนุมัติ risk worker เดิม, active tick 20ms และ idle sequence
  20→40→80→160→250ms (cap 250ms) พร้อม immediate reset เมื่อมี work/deferred/active platform;
  ไม่เพิ่ม worker/pool ไม่เปลี่ยน durable stop/retry/fairness และต้องผ่าน scheduler/PostgreSQL checks
  กับ short diagnostic ก่อน W1
- implementation เพิ่ม activity aggregation ใน stop loop เดิมและ `StopRound.active` สำหรับ active
  platform stop; scheduler unit tests, Ruff และ Mypy ผ่าน และ clean PostgreSQL regression ของ
  scheduler + trading-stop storage 21/21 ผ่าน รวม rollback/restart, fairness, discovery และ stale resume
- short diagnostic r3 บน fresh schema0061 หยุดระหว่าง setup ที่ baseline 18/20: idle counter ที่เพิ่ม
  ไม่จำกัดถูกนำไป bit-shift ก่อน cap จน `OverflowError` ทำให้ risk worker ตาย; publisher จบด้วย
  `PRICE:OTHER` และไม่มี measured command เริ่ม จึงไม่ใช่ acceptance result
- แก้ regression โดยคืน cap ก่อน shift และ saturate idle counter ที่ 5; เพิ่ม oracle ค่า idle ขนาด
  `10**100`; scheduler 4/4, Ruff และ Mypy ผ่านบน source หลังแก้
- short diagnostic r4 บน fresh schema0061 ยืนยันว่า overflow ไม่เกิดซ้ำตลอด setup 461.3s แต่หยุดก่อน
  source window เพราะ baseline submit รอ risk policy available เกิน 60s (`TimeoutError`);
  source ระหว่าง setup commit BOOK 2,291 / PRICE 1,472, publication-fence max 2,417.5ms,
  book-cycle max 1,553.5ms และ price-cycle max 3,852.3ms; DB มี 106,518 commits / 104,875
  rollbacks, deadlock 0, reconciliation clock=0 และ PLATFORM cause=0
- r3/r4 artifacts อยู่ที่ `validation-artifacts/f19-20261031/nc06-source-lock-diagnostic-r3/`
  และ `nc06-source-lock-diagnostic-r4/`; ตาม R33 ไม่เริ่ม W1 และตามกฎแก้หลายรอบต้องทบทวน
  approach/เกณฑ์กับเจ้าของก่อนทดลองรอบถัดไป โดยห้ามลด correctness หรือ safety gate
- เจ้าของอนุมัติ **NC-F19-07** เป็น bounded read-only post-mortem โดยไม่ rerun workload หรือเปลี่ยน
  trading behavior; r4 มี state/evaluation ครบทั้ง 111 owners แต่ทั้งหมดเป็น
  `RISK_SOURCE_UNAVAILABLE`, `replay_pending=true` และ lag 107–352 price frames
- risk telemetry มี 15,098 committed owner evaluations ใน 454.342s (ประมาณ 33.23 commits/s);
  cursor delta รวม 453,876 หรือประมาณ 999 frame-owner/s ขณะที่ watermark 4,424 frames ใน
  458.0s × 111 owners เป็น demand ประมาณ 1,072 frame-owner/s จึงขาด sustained capacity ราว 7%
- PostgreSQL log ในช่วงเดียวกันมี owner-lock timeout 776, statement timeout 1, deadlock 0;
  lock contention ซ้ำเติม throughput แต่ไม่อธิบายเป็น initialization/state loss และผล 8-slot R21
  เดิมก็ไม่ผ่าน SLA จึงห้ามถือว่าการเพิ่ม pool/concurrency เป็นคำตอบที่พิสูจน์แล้ว
- NC-F19-07 ปิด diagnosis โดยไม่ต้องเพิ่ม instrumentation: blocker คือ standalone monitor replay
  capacity ต่ำกว่า continuous publisher demand; ยังไม่อนุมัติ production optimization/criteria change
  และยังไม่เริ่ม W1 จนเจ้าของเลือกแนวทางแก้ใหม่
- พบ F18 plan ย่อหน้าเดิมกล่าวว่า standalone scheduler opt-in final publication fence แต่ Approved
  R14, implementation และ evidence ใช้ captured watermark โดยทั้งสอง fence flags เป็น false;
  เจ้าของยืนยันให้ R14 เป็น source of truth จึงแก้เฉพาะ plan ให้ตรง runtime ไม่มี code/behavior change
- วิเคราะห์ retry path ต่อพบว่า r4 มี committed monitor rows ที่ `pending=false` 14,719/15,098
  แต่ harness hint รอ `evaluation.cursor = owner.cursor = current publication watermark`; เงื่อนไข
  exact-current นี้เข้มกว่า Approved API R6 ซึ่ง full policy ตรวจ immutable tail ได้ถึง 100 frames
- เปิด **NC-F19-08** เป็น proposed plan+validation amendment: เปลี่ยนเฉพาะ read-only harness hint
  ให้ใช้ matched durable cursor + non-pending + lag 0..100 แล้ว full policy recheck ทุกครั้ง;
  ยังไม่แก้ code/rerun diagnostic จนเจ้าของอนุมัติ amendment
- เจ้าของอนุมัติ NC-F19-08; implementation แยก `risk_retry_ready` ใน validation harness และเปลี่ยน
  predicate เป็น evaluation cursor ตรง owner cursor, non-pending และ current lag 0..100 โดย retry
  path เดิมยัง full policy recheck ก่อน intake ไม่มี production source/schema/runtime change
- targeted workload/R6 suite ผ่าน 43/44 ก่อนแก้ test owner context; failure เป็น migrator RLS fixture
  มองไม่เห็น row ไม่ใช่ behavior จากนั้น exact matrix test ผ่านหลังตั้ง owner context ตามมาตรฐาน
- static หลัง NC-F19-08 ผ่าน Ruff, Mypy 246 source files และ diff check; targeted evidence รวม
  44/44 โดย reuse 43 ผลที่ implementation ไม่ได้เปลี่ยนหลัง fixture fix และ rerun exact matrix จนผ่าน
- short diagnostic r5 fresh schema0061/child publisher ทำ core baseline ครบ 20/20
  (`paper_order_projections=2,011`, core requests=2,001 รวม dedicated setup) จึงยืนยันว่า
  exact-watermark hint starvation ของ r4 ถูกปลด แต่หยุดก่อน source window ที่ dedicated loss RESET
  ถูก terminal reject `RISK_SOURCE_UNAVAILABLE`; measured counters ยัง 0 และไม่ใช่ acceptance
- post-mortem มี evaluation 110 owners เป็น source-unavailable/pending; dedicated loss ownerหนึ่งรายยัง
  `RISK_LOSS_LIMIT_REACHED`, latched, non-pending, cursor lag39; RESET results 101 APPLIED จาก setup
  และ dedicated request 1 REJECTED โดย failure code เดียวไม่จำแนก replay/book/frame source gap
- เปิด **NC-F19-09** และหยุดตาม amendment: ต้องตัดสินว่าจะคง first-attempt strict, อนุญาต bounded
  new-request retry ใน validation หรือเปลี่ยน production request lifecycle; ไม่ rerun W1/diagnosticเอง
  artifact อยู่ที่ `validation-artifacts/f19-20261031/nc08-r6-hint-diagnostic-r5/`
- เจ้าของอนุมัติ NC-F19-09 ตัวเลือก bounded validation-only retry; implementation เพิ่ม attempt
  evidence และสร้าง durable RESET request/key ใหม่รวมสูงสุด 3 ครั้งเฉพาะ terminal
  `RISK_SOURCE_UNAVAILABLE`, เว้น 250ms ภายใน 60s; failure อื่นและ attempt ที่สามยัง unavailable
  ล้มทันที โดย production RESET/source/runtime ไม่เปลี่ยน
- unit retry matrix ผ่าน 3/3 (unavailable→unavailable→applied, non-source failure และ unavailable
  ครบสามครั้ง); workload profile file ผ่าน 14/14 บน real DB; Ruff/format, Mypy 246 source files และ
  `git diff --check` ผ่าน
- short diagnostic r7 บน fresh schema0061/child publisher ใช้เวลา setup จริง 616.34s และ baseline
  ครบ 20/20 แต่มี owner monitor `DATABASE_TIMEOUT` ต่อเนื่อง แล้ว dedicated partial NEW ถูกปฏิเสธ
  `RISK_SOURCE_UNAVAILABLE` ก่อนสร้าง loss breach/RESET; counters measured=0, RESET attempts=0 และ
  ไม่มี dedicated proof จึงเป็น **Failed**, ไม่ใช่ acceptance และหยุดก่อน W1
- post-mortem ของ dedicated owner พบ evaluation/owner cursor=6615, publication=6668 (lag53),
  `reason=RISK_SOURCE_UNAVAILABLE`, owner/evaluation `replay_pending=true`; order request ถูก durable
  transfer แต่ downstream risk authorization fail closed ไม่มี unintended measured trade
- infrastructure artifact r6 เก็บแยก: ครั้งแรก isolation guard ปฏิเสธ hostname และครั้งถัดมาชน
  telemetry path เดิมจนถูก cancel ระหว่าง setup; database ยังมี wallets=0/counters=0 จึงไม่ใช่
  diagnostic attempt ที่พิสูจน์ behavior. หลักฐานรอบจริงอยู่ที่
  `validation-artifacts/f19-20261031/nc09-reset-retry-diagnostic-r7/`
- NC-F19-09 implementation ผ่าน targeted checks แต่ diagnostic criterion ยังไม่ผ่านเพราะ failure
  เกิดก่อน retry scope; ตามกฎหลายรอบต้องทบทวนเกณฑ์/fixture composition ก่อนทดลองใหม่ ห้ามเพิ่ม retry
  ให้ NEW, ลด fail-closed หรือรัน W1 ต่อโดยไม่มี amendment ที่เจ้าของอนุมัติ
- bounded r7 post-mortem ผูก partial NEW ได้ครบ: request
  `b11b6fde-4424-4b44-8050-c09b083b4414` recorded 16:38:53.758Z ถูก transfer เป็น command
  `ff812dea-4c32-4925-b3b2-84884b5e5739` เวลา 16:38:54.164Z; command terminal reject
  `RISK_SOURCE_UNAVAILABLE` เวลา 16:38:57.074Z และมี request/decision audit อย่างละหนึ่ง
- financial source ไม่ใช่สาเหตุที่พบ: owner boundary cursor=latest boundary=313,
  owner source revision=position revision=2 และ source/position proof ตรงกัน; ไม่มี position,
  reservation หรือ order ถูกสร้างจาก command ที่ล้ม
- price/replay branch เป็น blocker: telemetry ล่าสุดก่อน request เป็น cursor6461/non-pending เวลา
  16:38:52.775Z; monitor commit ถัดไปหลัง command failure เป็น cursor6615/pending เวลา
  16:38:57.162Z และ final publication=6668. Continuous source กับ DB timeout ทำให้ authoritative
  replay state ไม่พร้อมตอน paper worker ตรวจซ้ำ แม้ request worker เคยผ่านและ transfer แล้ว
- เปิด **NC-F19-10** เป็น proposed validation-only amendment: isolated dedicated diagnostic และ
  reorder integrated dedicated scenario ให้มาก่อน core baseline โดยคง production semantics/โหลด/เกณฑ์;
  หยุดรอ owner approval ก่อนแก้ harnessหรือรันรอบใหม่
- เจ้าของอนุมัติ NC-F19-10; implementation เปลี่ยนได้เฉพาะ validation harness/evidence ตาม amendment
  และต้องตรวจ isolated → integrated short diagnostic → W1 ตามลำดับโดยหยุดที่ failure แรก

## Post-refactor verification — 2026-10-31

- รวม owner/platform journal read/write/cleanup, pending receipt และ known-failure handling ไว้ใน
  `frontend/src/killSwitchJournal.ts`; component คง storage key/payload และ retry behavior เดิม
- รวม API idempotency lookup, throttle, immutable submit และ HTTP replay status ของทั้งสี่ mutation
  endpoint ไว้ใน `_submit`; authorization, transaction boundary และ error mapping เดิมไม่เปลี่ยน
- ลบ frontend request-by-key wrapper ที่ไม่มีผู้เรียก และ local helper/dead branch ที่ไม่จำเป็น
- API regression `test_kill_switch_routes.py` + `test_route_classification.py`: 21 tests ผ่าน
- frontend full suite: 35 files / 340 tests ผ่าน; TypeScript, ESLint และ production build ผ่าน
- backend Ruff format/check และ Mypy 244 source files ผ่าน; `git diff --check` ผ่าน
- Vite ยังคงมี warning chunk >500 kB เดิม; ไม่ใช่ failure และ refactor นี้ไม่ขยาย scope ไปแก้ bundling

## Validation checkpoint — 2026-10-31

- isolated PostgreSQL `tiewtrade_f19_validation`: affected correctness/safety suite 149 tests;
  พบ oracle F-18 เดิมหนึ่งกรณีที่คาดรับ BUY หลัง loss breach จึงแก้ให้พิสูจน์ shared
  `LOSS_LIMIT` fence ก่อนสร้าง inbox แล้ว targeted file 5/5 ผ่าน โดยไม่รันชุดที่ผ่านซ้ำ
- architecture contracts 7/7, generated OpenAPI/client, Ruff, Mypy 244 source files,
  TypeScript และ ESLint ผ่านบน source ล่าสุด; frontend full suite 340 tests/build จาก
  post-refactor checkpoint ยัง valid
- real browser→API→engine→DB E2E ผ่าน 2 stories:
  1. Paper/Live controls แยกกัน, lost-ack reload ใช้ idempotency key เดิม, Paper summary/focus,
     Live คง incomplete และไม่มี order request
  2. Platform Owner stop/reason/banner/resume, Admin resume disabled และ free-text escaped
- DB oracle ของ owner story: PAPER/USER STOP และ LIVE/USER STOP เป็น `APPLIED` อย่างละหนึ่ง,
  `paper_order_requests=0`; ไม่มี automated Live order
- visual evidence:
  `evidence/ui/paper-live-separated-th-light-desktop.png`,
  `evidence/ui/paper-live-separated-en-dark-mobile.png`,
  `evidence/ui/platform-owner-resumed-th-light-desktop.png`
- browser verification boundary ผ่าน: UI trigger → immutable API request → engine result → DB fact
  → rendered status; หลัง expected lost-connection fault ไม่มี console/page error ใหม่
- V-19 ยัง Partial ตามรายละเอียดใน `validation.md`;
  V-20..24 คง Pending Full Validation/Pending Dependency และ required remote CI ยังไม่รัน

### V-04 DB isolation / immutability

- เพิ่ม real-role/API coverage สำหรับ cross-owner และ cross-mode request/effects/summary ซึ่งคืน
  uniform 404 โดย owner เดิมยังอ่าน resource ของตนได้
- API role ถูกฐานข้อมูลปฏิเสธ UPDATE/DELETE immutable inbox และการเขียน event, cause,
  platform progress/target projection รวม 6 รูปแบบ
- fault injection ที่ `audit_events` ทำให้ security-definer submit transaction ล้มทั้ง inbox,
  dispatch และ audit; หลังเอา fault ออก retry ด้วย idempotency key เดิมสร้าง intent+audit เดียว
- invalid body marker ไม่ปรากฏทั้ง response และ captured log; raw reason marker ไม่ปรากฏใน
  translated database error
- targeted evidence ใหม่ 9/9 ผ่าน; Ruff format/check และ Mypy `src tests` 608 files ผ่าน
- การรันรวมกับฐาน validation เดิมมี test เดิม 2 ข้อชน durable pending rows ที่ค้างจากรอบก่อน;
  หลักฐาน clean-run 149 tests เดิมยัง valid และไม่ได้แก้ production behavior จาก test contamination นี้

### V-10/V-11 platform effects and ordering

- clean PostgreSQL `tiewtrade_f19_m3_validation`: `test_stops.py` 7/7 ผ่าน รวม platform
  `BOT_ONLY` child ที่ cancel active BOT/release reservation แต่คง sent MANUAL เป็น `ACCEPTED`
- test ใช้ production target selection, stop consumer และ F-15 cancel worker โดยสร้าง child authority
  แบบ owner-scoped fixture จึงไม่ทิ้ง global platform stop ปนเปื้อน test อื่น
- real advisory barrier ยืนยัน platform exclusive fence รอ transaction ที่ถือ shared opening-admission
  fence จน admission commit; targeted reset/admission, fill/reset, inbox transition, risk concurrency,
  claim takeover, owner fairness และ reordered historical projection ผ่านเพิ่ม 14/14
- V-10 ปิดเป็น Passed (local contract); หลักฐาน ordering เดิมรวมกับ direct matrices ด้านล่าง
  ปิด V-11 เป็น Passed (local targeted)
- Ruff format/check, Mypy `src tests` 608 files และ `git diff --check` ผ่าน

### V-12 fault/recovery increment

- real DB fault injection ทำ target handler ล้มหลัง enrollment: latest effect เป็น `FAILED`,
  attempt เพิ่ม, `next_attempt_at` backoff และ progress ตั้ง `alert_due=true` เมื่อ cutoff เกิน 1 นาที
- เมื่อ retry ถึงกำหนด worker ทำต่อจน terminal `REJECTED`; target คงหนึ่งรายการและ progress กลับ
  pending/failed/alert เป็นศูนย์/false แสดงว่า alert ไม่หยุด recovery
- `test_stops.py` clean regression 8/8 และ Mypy 608 files ผ่าน
- เพิ่ม engine outcome fault injection: audit `STOP_UPDATED`/`RESUMED` ล้มแล้ว result, event,
  cause projection และ child job rollback ใน transaction เดียว; ปลด fault แล้ว worker ใหม่ retry
  สำเร็จ และ replay หลัง commit ไม่เพิ่มผล/audit/job ซ้ำ
- ขยาย real F-15 cancel lifecycle เป็น before-commit rollback/lease takeover กับ after-commit
  lost-ack; ทั้งสองแบบลงท้าย cancel command เดียว ปล่อย reservation ครั้งเดียว และ claim ซ้ำไม่ได้
- clean fresh PostgreSQL `tiewtrade_f19_v12_matrix` ผ่าน STOP/RESUME + cancel boundary matrix 3/3;
  Ruff, Mypy `src tests` 608 files และ `git diff --check` ผ่าน จึงปิด V-12 เป็น Passed
  (local targeted); notification delivery จริงคง V-24 และ real TP/SL คง V-21 Pending Dependency

### V-14 fairness/resource bounds

- `EXPLAIN` เดิมใช้ global `enrolled_sequence` index แล้ว filter `stop_id` ภายหลัง ซึ่งไม่ bounded
  ต่อ stop เมื่อหลาย owner/stop สะสม จึงเพิ่ม migration index
  `risk_stop_targets_stop_sequence(stop_id,enrolled_sequence)`
- 105-target effect pagination ยืนยัน page limit 20/100, stable watermark/snapshot, ไม่มี duplicate,
  owner/mode isolation และ query plan เลือก composite index ใหม่
- locked owner ไม่ starve owner ถัดไป; bounded stop/discovery/claim limits และ durable cursor rounds
  ใช้หลักฐานเดิมที่ยัง valid
- fresh migration `upgrade head → downgrade 0060 → upgrade head` ผ่าน และ index definition ถูกต้อง
- V-14 ปิดเป็น Passed (local targeted); workload/scale ระยะยาวยังคงรวมใน V-20

### V-15..17 browser matrix increment

- expanded platform story ผ่านใน 16.3 วินาที: platform Owner stop/reason/resume, Admin resume
  disabled, free-text escaped และ persistent banner พร้อมปุ่ม Paper/Live แยกกันครบ 10 account
  routes ที่ viewport 1440px และ 375px; V-17 ปิดเป็น Passed (local browser)
- expanded owner story exercise ครบถึง lost-ack retry ด้วย key เดิม, MANUAL BTC/USDT budget 11
  หลัง cutoff เดิมได้ `FILLED`, stop key ใหม่ให้ request/generation ใหม่, nonempty summary,
  Paper/Live isolation, focus return และ mobile English/dark state
- DB read-only oracle หลังรอบ browser พบ MANUAL BTC/USDT budget 11 จำนวนสองรอบเป็น `FILLED`
  ด้วย filled quantity `0.11` และ spent `11`; ไม่มี automated Live order ใน flow
- clean expanded-owner rerun หลังจำกัด HTTP listener หลัง register ผ่าน 1/1 ใน 13.8 วินาที;
  V-15 ปิดเป็น Passed (local browser)
- trace ของรอบก่อนหน้าระบุ generic 404 มาจาก expected chart-data absence และ request-key
  probe ก่อน create; test เปลี่ยนไปตรวจ unexpected HTTP URL/status โดยตรงและยังจับ
  JavaScript/page errors แยกกัน
- เพิ่ม component coverage สำหรับ PROBLEMS snapshot ซึ่งแสดง position, FAILED/CANCELED/PENDING,
  reconciliation time และปิด resume รวมถึง stale resume receipt ที่ refetch summary แล้วปิด submit
  โดย request เดิมส่ง expected stop/revision/summary/reconciliation จาก snapshot ที่ผู้ใช้เห็น
- targeted `KillSwitchControls.test.tsx` ผ่าน 3/3; TypeScript, ESLint ของ component/E2E และ
  `git diff --check` ผ่าน จึงปิด V-16 เป็น Passed (local targeted)

### V-11 direct ordering increment

- fresh PostgreSQL matrices ยืนยัน real owner lock block และ reset-vs-stop ครบ reset-first กับ
  stop-first สำหรับ BUY/SELL รวม 4/4; loss reset ไม่ลบ durable stop และ cancellation ปล่อย
  reservation ครั้งเดียวโดยไม่เปลี่ยน position/wallet ผิดลำดับ
- cancel/fill investigation ยืนยัน scheduler ให้ active claim ต่อ owner ได้ครั้งละหนึ่ง: claim ที่สอง
  คืน `None` จน claim แรก terminal จึงไม่มีสอง worker เขียนเงิน/position พร้อมกัน
- หลัง STOP commit แล้ว historical revision fence ทำให้ pre-stop opening fill ลงท้าย `CANCELED`
  แม้ fill command ได้ worker claim ก่อน cancel; oracle เดิมคาด `FILLED` จึงผิดตาม RQ-08
- แก้ expected invariant เป็น `CANCELED`, filled `0`, reservation `0`, wallet `10000`, ไม่มี
  position/execution link และมี cancel command/event อย่างละหนึ่ง จากนั้น clean rerun บน fresh
  PostgreSQL `tiewtrade_f19_v11_matrix5` ผ่าน cancel-vs-fill ทั้งสอง claim orders 2/2
- รวมกับ fresh reset-vs-stop 4/4 และหลักฐาน concurrency/lease/historical เดิม 14/14 จึงปิด
  V-11 เป็น Passed (local targeted)

เอกสารนี้เป็น implementation checkpoint ไม่ใช่การประกาศ Completed หรือพร้อม merge

## NC-F19-10 validation checkpoint — 2026-11-01

- validation-only implementation เพิ่ม isolated dedicated LOSS_LIMIT diagnostic, bounded snapshots
  ของ request/command/risk/financial state และบังคับ integrated setup order เป็น
  `DEDICATED_LOSS → CORE_RISK_SETTINGS → CORE_BASELINE`; production API/engine/schema,
  fail-closed policy, NEW retry, owners/load/duration/SLA ไม่เปลี่ยน
- targeted workload tests ผ่าน 5/5, workload-profile file ผ่าน 16/16 และ Ruff/Mypy ผ่าน;
  isolated r1 หยุดก่อน scenario เพราะ diagnostic reader ใช้ API role เกินสิทธิ์ จึงแก้ harness
  ให้ใช้ owner-scoped ENGINE role ตาม contract โดยไม่มี trading behavior change
- isolated r2 บน fresh schema0061/child publisher/real workers ผ่านในประมาณ 34 วินาที:
  partial fill 0.5, LOSS_LIMIT cancel/release complete, RESET attempt 1 `APPLIED`, opening probe
  fail closed, wallet 9950/position 0.4995 cost 50 คงเดิม, reservation กลับศูนย์ และไม่มี duplicate
  order/fill/position event
- integrated short r2 ใช้ fresh schema0061 และ resource profile เดิม ผ่าน dedicated proof ก่อน
  core baseline 20/20 แล้วจบ source window 60.725 วินาที; counters 461 offered / 371 admitted /
  370 completed, pool evidence finalized และไม่มี duplicate fill/position execution หรือ unintended
  dedicated trade. `WINDOW_COMPLETE` คง `acceptance_result=false` ตาม diagnostic contract
- W1 r1 เริ่มบน fresh schema0061, child publisher, parent 3 CPU/1536 MiB, core 100×20 และเกณฑ์เดิม;
  dedicated proof และ core baseline 20/20 ผ่าน แต่ล้มระหว่างสร้าง BOT setup order ของ stop-owner
  slot 1 ก่อน measured window: command `efc42593-a24b-4402-a9bd-b7561a9b7de6` terminal reject
  `RISK_SOURCE_UNAVAILABLE` หลัง owner non-pending cursor ล่าสุด 4214; ปลายทาง cursor 4314,
  publication watermark 4427, lag 113 และ replay pending จึงเกิน R6 tail budget 100
- rejected command ไม่สร้าง order/fill/position/reservation; ทั้งฐานมี duplicate fill execution 0,
  duplicate position execution 0, negative reservation 0 และ cleanup เหลือ database connection 0.
  measured counters/RESET schedule ยัง 0 เพราะ load window ไม่เริ่ม
- เก็บ W1 เป็น **Failed** และหยุดก่อน W2/W3 ตาม NC-F19-10; หลักฐานชี้ monitor replay capacity
  ภายใต้ continuous source/setup pressure ใน stop-owner อีกกลุ่ม ไม่ใช่ dedicated LOSS_LIMIT branch.
  ห้าม rerun, เพิ่ม NEW retry, ลด fail-closed/load/SLA หรือแก้ production throughput ก่อนมี amendment
  ที่เจ้าของอนุมัติ

### NC-F19-11 implementation — 2026-11-01

- เจ้าของอนุมัติ setup-only stop-owner readiness gate; implementation reuse `risk_retry_ready`
  เดิมก่อน dedicated stop-owner MANUAL/BOT NEW ใน W1/W2/W3 แล้วเรียก submit ครั้งเดียว
- WAIT_START/READY/TIMEOUT บันทึก owner/evaluation cursor+pending, setting revision, watermark/lag
  ลง `setup-readiness.json`; timeout ล้มด้วย `F19_SETUP_RISK_NOT_READY` โดยไม่สร้างคำสั่ง
- production source/schema/monitor/API, core100×20, measured commands, load/duration/SLA/pools และ
  stop schedule ไม่เปลี่ยน; terminal rejection หลัง submit ยังล้มทันทีและไม่มี NEW retry
- control-flow targeted 8/8 ผ่าน; Ruff และ Mypy 246 source files ผ่านก่อน full file/DB regression
- full workload-profile regression บน fresh schema0061 ผ่าน 19/19; `git diff --check` ผ่าน
- W1 r1 บน fresh schema0061/child publisher/resource profile เดิมใช้เวลาประมาณ 7 นาที 21 วินาที:
  dedicated LOSS_LIMIT proof และ core baseline 100×20 ผ่าน แต่ setup MANUAL stop-owner รายแรก
  รอ readiness 60 วินาทีแล้วจบ `F19_SETUP_RISK_NOT_READY` ก่อน measured window
- `setup-readiness.json` มี `WAIT_START → TIMEOUT` และไม่มี cursor/evaluation/setting เพราะ owner นี้
  ยังไม่มี `risk_limit_settings`, `risk_owner_state` หรือ `risk_limit_evaluations`; database post-mortem
  ยืนยัน request 0 / command 0 / order 0 และ risk state ทั้งสามกลุ่ม 0 จึงพิสูจน์ timeout no-submit
  ของ NC-F19-11 แต่ยังไม่พิสูจน์ stop-owner setup success
- เก็บ W1 เป็น **Failed** และหยุดก่อน W2/W3. สาเหตุคือ precondition ที่อนุมัติไม่มีทางเป็นจริง
  สำหรับ MANUAL stop-owner ซึ่งเดิมไม่ได้สร้าง risk setting/state ก่อน setup order; ห้าม rerun หรือเพิ่ม
  timeout. ต้องขอ amendment แยกก่อนเพิ่ม initialization ที่แตะ risk state

### NC-F19-12 implementation and W1 — 2026-11-01

- เจ้าของอนุมัติให้ MANUAL/BOT dedicated stop owners ทุกคนใช้ mutation `SET 1000` เดิมก่อน
  readiness gate; setup sequence เพิ่ม `STOP_OWNER_RISK_SETTINGS` ระหว่าง core settings กับ baseline
  โดยไม่เปลี่ยน production/schema/load/SLA หรือ NEW retry
- targeted setup/readiness tests ผ่าน 4/4, Ruff ผ่าน และ Mypy 246 source files ผ่าน
- runner configuration attempt แรกหยุดที่ import ก่อนสร้าง artifact/state เพราะ image ไม่เห็น mounted
  candidate source; เพิ่ม `PYTHONPATH` เท่านั้นและยืนยันฐานยังมี wallet 0 ก่อนเริ่ม acceptance จริง
- W1 r1 จริงบน fresh schema0061/child publisher/resource profile เดิมใช้เวลาประมาณ 7 นาที 36 วินาที:
  dedicated LOSS_LIMIT ผ่าน, core baseline 100×20 ผ่าน และ MANUAL/BOT readiness ผ่าน
  `WAIT_START → READY` ที่ current revision 1, lag 24/15 ตามลำดับ จึงปิด failure branch ของ NC-F19-11
- measured window เริ่มแล้วล้มที่ +172.51s ระหว่าง W1 stop schedule: BOT partial setup ที่ +110s
  ถูก fill เต็ม 1 BTC/100 USDT ใน execution เดียว แทน `PARTIALLY_FILLED` 0.5 BTC เพราะ core partial
  oracle เปลี่ยน global ask@100 จาก 0.5 เป็น 1,000,000 ก่อน event นี้; harness รอ status เดิมครบ
  60s แล้วเกิด `TimeoutError`
- ตอนล้ม counters 1,623 offered / 1,573 admitted+completed / 0 rejected / 294 cycles;
  scheduled RESET ยัง 0/100 เพราะยังไม่ถึงช่วงนั้น. stop journal ผ่าน queued MANUAL reject และ
  post-cutoff MANUAL success แต่ยังไม่ถึง partial-stop/resume
- post-mortem ยืนยันคำสั่ง partial terminal `SUCCEEDED`, projection `FILLED` quantity 1/spent 100,
  position 0.999 cost 100, reservation ของออเดอร์เป็นศูนย์; duplicate fill execution 0,
  duplicate position execution 0 และ negative reservation 0. เก็บ W1 เป็น **Failed** และหยุด W2/W3

### NC-F19-13 implementation and W1 — 2026-11-01

- validation harness เพิ่ม failure-safe scheduled partial source context: ติดตั้ง ask@100 quantity0.5
  ก่อน BOT partial NEW, บันทึก input identity และ restore previous quantity หลัง durable stop effects
  complete ก่อน resume; `finally` restore เมื่อ scenario ล้ม/cancel โดยไม่เปลี่ยน production/schema/rate
- unit/control-flow ผ่าน 5/5, fresh-schema real-DB W1/W2 schedule tests ผ่าน 3/3, Ruff ผ่าน และ
  Mypy 248 source files ผ่าน; real-DB attempt แรกที่ไม่มี role URLs เป็น configuration error ก่อน setup
- W1 r1 fresh schema0061/child publisher ผ่าน dedicated LOSS_LIMIT, core baseline100×20 และ readiness;
  source install quantity0.5 ที่ input1880 เวลา +110.09s, scheduled BOT order partial fill 0.5,
  generation1 stop cancel/release complete, restore quantity1,000,000 ที่ input2084 เวลา +151.00s,
  resume applied และ MANUAL generation2 ยังคง activeตาม oracle
- W1 ยัง **Failed** ที่ +159.73s: global partial source windowนานประมาณ40.9s กระทบ core owner
  `f85d89ab-ec60-4299-b099-0af767254287` cycle1; MARKET BUY budget100 ถูก fill 0.833/spent99.96
  แล้ว `EXPIRED` แทน `FILLED`, cycle deadline 60s จึง `TimeoutError`. ตอนล้ม counters 1,127 offered /
  1,027 admitted+completed / 0 rejected / 203 cycles และ scheduled RESET ยัง 0/100
- scheduled stop order ถูกต้องเป็น CANCELED/fill0.5/spent50/reservation0, position0.4995 cost50;
  duplicate fill execution0, duplicate position execution0 และ negative reservation0. หยุดก่อน W2/W3
  และห้าม rerun global-window implementation

### Full-validation deferral checkpoint — 2026-11-01

- ตามคำสั่งเจ้าของ หยุดแก้ NC-F19-14 และหยุดรัน W1/W2/W3 เพิ่มใน feature checkpoint นี้
- เก็บ NC-F19-14 เป็น Needs Clarification และย้าย implementation/targeted checks กับ timed W1–W3
  ไปทำครั้งเดียวที่ checkpoint ท้ายชุดที่ 5; ไม่เปลี่ยนเกณฑ์ owners/load/duration/SLA/safety
- ผล targeted/local V-01..18 ที่ยัง valid ใช้ต่อ; W1 Failed ทุก attempt และ W2/W3 ไม่ได้เริ่มยังคง
  บันทึกตามจริง. F-19 อยู่สถานะ Development Complete — Pending Full Validation / Required CI,
  ไม่ใช่ Completed และยังไม่พร้อม merge

### Post-CI deep-review remediation — 2026-11-01

Owner requested fixes for the two High and one Medium findings on `5620843`.
Results below apply to the uncommitted remediation worktree on that base.

- High / platform snapshot: migration 0062 records the reconciliation revision
  used by each aggregate. Counts, child readiness, inventory completeness and
  clock are read in one snapshot; publication checks both progress revision and
  current clock. API exposes the captured revision and disables stale readiness.
  Resume locks the clock row through commit using an engine-only definer function
  and verifies both captured/current clock and expected summary. API/engine still
  have no direct clock UPDATE grant. Pre-upgrade snapshots start NULL and require
  verification; downgrade refuses persisted snapshot history.
- High / owner starvation: target enrollment sets 100ms lock / 700ms statement
  bounds. Discovery rotates over owners without durable targets, continues after
  a failed owner and retries it later. Completion requires no missing owner.
  Concurrent projection updates use revision CAS; a timed-out projection write
  is deferred rather than terminating the stop loop.
- Medium / mixed causes: latest STOP is selected independently per cause before
  filtering APPLIED resumes. The primary summary falls back to an older unresolved
  cause. Additive `active_causes` keeps loss/system banners visible after latch
  reset, with generated OpenAPI/client types updated. Cause-specific resume and
  financial policies are unchanged.
- The platform schedule harness now uses the same captured revision/currentness
  check as the API. No timed W1–W3 workload was run or reclassified.

Verification on disposable PostgreSQL 16.15 with commit timestamps enabled,
Redis 7, Python 3.12.15 and frozen dependencies:

| Check | Result |
| --- | --- |
| Targeted real-DB stop regressions | 23 passed, 4.74s |
| Full normal backend suite | 4031 passed, 27 deselected, 900.88s |
| Fresh isolated writer-fence guard | 1 passed, 3.25s |
| Fresh isolated optional-limit guard | 1 passed, 2.17s |
| Fresh global-state suite | 23 passed, 4035 deselected, 6.52s |
| Frontend | 343 passed / 35 files; lint, types and build passed |
| F-19 browser stories, independent E2E database | 2 passed, 24.5s |
| Backend static checks | Ruff/check+format 681 files, mypy 614 source files, import contracts 7/7 |

Collection partition and JUnit audit confirm 4056 distinct executed backend
tests, each exactly once, with no failures/errors/skips in the final full run.
Schema remains 0062. Checks include stale clock, fresh clock with stale summary,
CONFLICTED→READY, engine-only clock lock with actual PostgreSQL blocking,
LOSS_LIMIT/SYSTEM×both cause orders, locked-owner recovery, two concurrent
discovery workers and the snapshot-history downgrade guard.

The first targeted run had 21 passed / 2 failed: a missing scanner revision grant
and a Platform Admin fixture without required creator identity. Both were fixed;
the logs remain preserved. Existing deprecation and frontend bundle-size warnings
remain; these are not new functional failures.

Commands, logs, JUnit reports and new browser screenshots are retained in
`validation-artifacts/f19-review-remediation-20261101/`; the screenshots written
over tracked historical evidence by E2E were restored after preserving this run.
Disposable test containers were removed after verification. Required CI must
run on a new committed candidate; green CI for `5620843` does not cover these
production/schema changes. V-20..24 remain pending at their approved checkpoints.

### Owner-authorized refactor — 2026-11-01

Reviewed only the preceding remediation diff. Consolidated the two identical
discovery timeout setups into `_set_discovery_timeouts` and three new platform
resume test payloads into `_submit_platform_resume`. Renamed the unresolved-stop
collection and simplified banner/mock setup. SQL predicates, timeout values,
transaction/lock ordering, generated contracts and all test assertions remain
unchanged; no financial or trading behavior changed.

Post-refactor verification on disposable PostgreSQL 16 / Redis 7:

- Targeted API, stop/concurrency, schedule-runtime, core and scheduler tests:
  **44 passed**, 17.64s.
- Fresh global-state tests, including all remediation cases: **23 passed**, 7.73s.
- Kill-switch frontend component tests: **4 passed**, 1.47s.
- Backend Ruff/check+format, mypy and seven import contracts; frontend ESLint and
  TypeScript; `git diff --check`: **Passed**.

The prior full backend4056/frontend343 and browser2 evidence remains reusable
for unaffected behavior, with the 67 backend / 4 frontend targeted rechecks
covering this refactor. No full suite, browser or workload rerun was required
for unchanged SQL/schema/API contracts and behavior. V-20..24 remain pending.
Logs/JUnit are retained in `validation-artifacts/f19-refactor-20261101/`.
Disposable containers were removed. Commit/push and required CI on the final
candidate remain pending the owner's Git instruction.

### Required CI and pre-merge evidence sync — 2026-11-01

Owner committed and pushed remediation/refactor as
`f00bac0fb0748ba5cab00efe020c708ff8d17f9c`. Both
[push CI 41300359252](https://github.com/yukasung/tiewtrade/actions/runs/41300359252)
and [PR CI 41300363009](https://github.com/yukasung/tiewtrade/actions/runs/41300363009)
completed successfully on that exact SHA, with all six required jobs green.

| Backend phase | Push CI | PR CI |
| --- | --- | --- |
| Normal suite | 4031 passed / 986.20s | 4031 passed / 842.65s |
| Isolated writer-fence guard | 1 passed / 3.29s | 1 passed / 2.56s |
| Isolated optional-limit guard | 1 passed / 2.50s | 1 passed / 1.91s |
| Fresh global state | 23 passed / 8.04s | 23 passed / 6.17s |

Backend total is 4056 passed in each run. Frontend lint/types/tests, API contract,
container and browser E2E jobs also passed. The remote head matches the local
candidate; PR #41 is Ready for review and reports CLEAN/MERGEABLE. GitHub has no
submitted PR review; the owner-requested review, remediation and refactor
evidence is recorded above, rather than represented as a GitHub approval.

This closes the previously pending required-CI portion of V-19 for `f00bac0`.
It supersedes earlier pending-CI statements for that runtime candidate while
preserving historical failures and scope limits. NC-F19-14/W1–W3 remain deferred
to Set-5 full validation; V-20 remains Pending Full Validation and V-21..24 remain
Pending Dependency. No release/Live activation or Completed status is asserted.

The owner requested this documentation/PR-description sync after the final gate
check. Only evidence/status text changes in this sync; content/link consistency
and `git diff --check` are sufficient local checks. A new commit, if requested,
still requires CI for the final merge SHA. Merge itself requires an explicit
owner instruction and has not been performed.

### F-16 browser CI race remediation — 2026-11-01

The documentation candidate `dac8deb` has mixed CI evidence: push run
41302429881 failed the F-16 storage-denial browser test before its POST-blocking
assertion, while PR run 41302434060 passed on the same SHA. The failed push
uploaded no artifacts because its upload path omitted Playwright `test-results`.
The earlier successful CI remains historical evidence, not a pass for the next
candidate.

An isolated original storage-denial test passed (9.3s total). A controlled late
trade-snapshot response reproduced the disabled-submit failure: trace snapshots
showed the filled amount changing from `100` to empty when the wallet scope
arrived and remounted the form. This demonstrates a harness timing gap; the
original remote branch cannot be established conclusively without its lost trace.

Owner authorized the harness/artifact fix. `frontend/e2e/manual-orders.spec.ts`
now reuses `reloadPaperPair` for registration and source refresh, waiting for the
BTC trade response with wallet/episode identities and the rendered wallet value
before filling. The response waiter is armed before reload because the existing
chart automatically selects the first supported pair. The storage-denial test
delays snapshots to retain regression coverage while preserving its storage error
and zero-POST assertions. `.github/workflows/ci.yml` also uploads
`frontend/test-results/` on failure. No production, trading, schema, timeout or
safety-assertion changes were made.

The first helper iteration failed because its waiter was armed after the chart
could select BTC, delaying completion until polling and allowing source expiry.
That run was stopped and retained as Failed/interrupted, not retried unchanged.
After moving the waiter before reload, the complete F-16 suite passed on a fresh
disposable PostgreSQL 16 / Redis 7 database: **7 passed (1.2m)**, including delayed
snapshot/storage denial, exact financial effects, receipt-loss recovery,
cancel/fill/reset races and DB-loss same-key recovery. Frontend ESLint and
TypeScript, workflow YAML/artifact-path checks and `git diff --check` passed.

Logs, failed traces and generated screenshots are retained locally under
`validation-artifacts/f19-f16-e2e-fix-20261101/`. Tracked UI screenshots were
restored from their pre-run copies and disposable containers were removed.
Commit/push and required CI on the resulting candidate are pending owner Git
instructions; no GitHub rerun or merge was performed. V-20..24 remain pending
under their existing full-validation/dependency scopes.

### Merge and post-merge CI checkpoint — 2026-11-01

This checkpoint supersedes earlier pending commit/push/merge statements for the
F-16 harness fix while preserving historical failures and validation limits.
Owner committed and pushed the three-file fix as
`de25852cd5b88edd5c0acf214c3a6dc2c172685b`. Both
[push CI 41305111782](https://github.com/yukasung/tiewtrade/actions/runs/41305111782)
and [PR CI 41305117314](https://github.com/yukasung/tiewtrade/actions/runs/41305117314)
passed all six jobs on that exact SHA. Each run passed 4,056 backend tests and
33 browser tests, including the delayed-snapshot storage-denial regression.

On the owner's explicit merge instruction,
[PR #41](https://github.com/yukasung/tiewtrade/pull/41) was squash-merged into
`main` at 2026-11-01 12:28:57 UTC as
`ccc3ce152061d9f38784ffe66e593f5aeefba068`. The final head and required checks
were verified before merge; GitHub reported CLEAN/MERGEABLE. No branch was
deleted and unrelated local changes were preserved.

[Post-merge CI 41306706760](https://github.com/yukasung/tiewtrade/actions/runs/41306706760)
completed successfully on that merge SHA, with all six jobs passing: backend,
frontend, browser E2E, API contract, PostgreSQL version and containers.

| Backend phase | Post-merge result |
| --- | --- |
| Normal suite | 4031 passed / 703.54s |
| Isolated writer-fence guard | 1 passed / 2.46s |
| Isolated optional-limit guard | 1 passed / 1.93s |
| Fresh global state | 23 passed / 5.97s |

Backend total: **4056 passed**. Browser total: **33 passed** (main 18, F-37 2,
F-16 7, F-18/F-19 6). No automated Live orders were sent. CI logs downloaded
during monitoring are retained under `/tmp/f19-ccc3ce1-postmerge-backend.log`
and `/tmp/f19-ccc3ce1-postmerge-e2e.log`; the linked GitHub runs are the remote
evidence.

V-19's final-candidate and post-merge CI evidence is now complete. V-20 remains
Pending Full Validation, including NC-F19-14 and timed W1–W3 at the approved
Set-5 checkpoint; V-21..24 remain Pending Dependency. Historical Failed/Partial
results are unchanged. The merge does not mark F-19 Completed or authorize
production/Live activation.

The owner requested this evidence/validation/roadmap sync after monitoring.
It changes documentation only; content/link consistency and `git diff --check`
are the relevant checks. The owner subsequently authorized commit/push of this
sync on a documentation branch; its candidate still requires CI before merge.

### Set-5 NC-F19-14/15 implementation and failed W1 checkpoint — 2026-11-01

Owner approved the Set-5 plan including NC-F19-14 and NC-F19-15. Work is on
`validation/f-19-set5`, without commit/push authorization. Unrelated local
AGENTS/testing-policy edits remain excluded. No production code, public API,
schema, financial formula, owner/load/rate/duration or resource limits changed.

Implemented bounded one-shot publisher controls with consumed identities,
unknown-ACK cleanup, committed trade receipts separate from transport ACKs,
and rejection of duplicate/conflicting controls. Strict F-19 preparation waits
for a durable resting BUY at2 with zero queue ahead before a single trade0.5;
F-18's global-window compatibility path is retained for its existing selection.
Explicit `F19_SET5` selects owner99.9%/aggregate99.9%≤3s, hard5s and no missing
source allowance; default F-18 R34 remains owner99.5%/one-observation allowance.
W4 adds shared stop/clock/membership digests, active USER/SYSTEM/PLATFORM staging,
pending cursor recovery, exact-key replay, stale-resume rejection, balances and
reservation checks to the existing restore tools. Full backup/restore is not
claimed from the targeted recovery tests.

P0 evidence, all retained under `validation-artifacts/f19-set5-20261101/p0/`:

- Harness publisher/SLA/profile regression: **64 passed**,10.40s; CLI checks:
  **6 passed**,0.27s. These groups overlap some earlier checks; no sum is used
  as a unique full-suite coverage claim.
- Fresh global-state suite: **25 passed**,15.16s. Includes the real-worker
  overlapping core BUY/SELL and single partial fill/cancel/resume case, plus
  restore staging/recovery/stale-resume with financial checks.
- Frozen Linux runner preflight: **2 passed**,7.28s on a fresh database.
- Ruff/check+format and mypy for the four modified profile modules passed;
  existing unaffected regression/CI evidence is reused. No full backend/frontend
  rerun was added for harness-only changes.
- The initial one-shot preflight failed because ACCEPTED preceded the resting
  projection; bounded observation was added without resubmitting NEW. A reused-DB
  exploratory recheck passed, followed by the fresh-DB matrix above.
- Combined global-state attempts initially failed from a new immutable platform
  membership exposing an existing test setup's single-owner SELECT assumption.
  A teardown DELETE attempt was rejected/rolled back by append-only protection.
  The final fixture keeps immutable membership history, resumes its global fence,
  and the affected existing setup selects one owner deterministically. All
  original fairness assertions remain. Both failed suite logs are retained.
  Collection-only marker/syntax setup failures are retained as Not Run, not passes.

P1 froze a separate read-only candidate checkout from base `2322d86`, with tree
SHA-256 `8da984f63d73c70f9fafed2f6810ad4e640efdf11acc805a9163a618727c3633`.
The candidate file hashes, tracked patch and container/image/lock inventory are
retained next to the run. The runner derives from the existing image, adds the
Docker CLI needed by W3 and locked dev tooling for Linux preflight; `uv.lock`
hash matches the existing image. PostgreSQL uses the prior image identity,
4CPU/3GiB, commit timestamps and max_connections200. Redis uses the prior image
and ACL; runner remains uncapped as in the accepted prior resource profile.
VM reports3043373056bytes/8CPUs. A runner-scoped caffeinate assertion covered W1
and released on exit. No unrelated containers were stopped or reconfigured.

W1 used fresh schema0062,100 core owners×20 baseline orders,10workers,
explicit child5Hz, command10/s and strict F-19 criteria. The dedicated LOSS
partial0.5→breach→effects complete→RESET attempt1 APPLIED→fresh opening rejected
`ORDER_SAFETY_UNAVAILABLE` passed, with active LOSS_LIMIT/resume_ready=false.
Core settings/READY evaluations reached100/100 and baseline completed before load.
Setup phase was15:36:17.087620→15:40:14.457781 UTC (237.37s).

**W1 Failed**, not Partial/Passed: failure phase was15:42:15.555433 UTC,
**+121.0946s** into the required600s window. The failed owner's cycle1 consumed
**60.0094s**; traceback ends at `Fixture.request`'s REQUEST_VIEW `user_session`
entry, canceled while waiting for a parent API pool connection. API peak was15
against capacity15; all pools finalized at0checked-out. Exact identities and
timestamps are in `w1-r1/failed-cycle-identities.json`: BUY FILLED, LIMIT later
CANCELED; SELL request `e629ad9b-6fab-404a-b7e5-97a50ea44888` transferred to command
`fbcb760d-76b5-4e51-be0b-bb48c6dd78e1`, command SUCCEEDED at15:42:05.601656 UTC,
but order `ede46d9e-a5e3-54dc-b214-41493e2b7600` remained ACCEPTED at shutdown.
This establishes the terminal failure branch, not the ultimate cause of queueing.

At failure counters were891offered/792admitted/792completed/0rejected and126cycles;
the other99active cycles were canceled during failure cleanup. Only the queued
MANUAL stop/rejection marker completed. No one-shot committed receipt exists,
so neither the scheduled partial nor its under-load isolation is certified.
W2/W3/W4 were not started, and strict full-window source/SLA acceptance remains
unproved. No automatic rerun, NEW retry, pool increase or deadline change followed.

Read-only post-failure diagnostics are explicitly labeled `not_acceptance`:
1867 worker transaction samples in the observed window give processing p95=1.571s,
p99=2.965s. Partial risk evidence has90144acknowledgements/103512expected,
17322above3s,4932above5s,13368unacknowledged and max16.3448s, with0clock errors.
Shutdown truncates this evidence; it is not a completed-window verdict or proof
that API pool size alone caused the failure. The timing exceeds the limits on
observed inputs and requires causal investigation, not a threshold adjustment.
Raw resource samples peak at923230208RSS bytes/57connections/0sampled lock waits;
the sampling cannot exclude waits between samples. No OOM occurred.

Safety snapshot: duplicate fill execution0, duplicate RECORD position execution0,
negative reservations0 and negative position quantity/cost0. This is a partial-run
snapshot, not all full-validation financial/conservation oracles. W1 container
ran15:36:13.126379→15:42:18.948864 UTC (~6m06s) and exited1. Remaining DB connections
were0 after worker cleanup. A failed DB dump, raw logs, diagnostics and candidate
are preserved; task-owned PostgreSQL/Redis containers were stopped with data kept.

V-20 stays Failed/Pending Full Validation; V-21..24 stay Pending Dependency.
NC-F19-16 in plan§11 is only a proposed bounded pool/transaction diagnostic to
separate harness, downstream and environment causes. It requires owner approval
before instrumentation or another run. No code for that proposal was implemented.

### NC-F19-16 — Approved diagnostic executed once, Failed (2026-11-01)

Owner approved NC16. Added opt-in harness-only pool/transaction tracing, using existing
PoolEvidence, dispatch and cycle timing. API INTAKE/READY_HINT/REQUEST_VIEW and worker
transactions carry identities, acquisition/held/query timings and backend PIDs. SQL is
represented only by SHA256; parameters and exception messages are never serialized by
the tracer. Existing dispatch defaults remain60s/100 details; NC16 explicitly selects
180s/aggregate-only dispatch and bounded transaction records. No production, migration,
resource, pool, polling, deadline, authorization, retry or financial rules changed.

Targeted checks:76 passed/10.131s, zero skips; frozen Linux runner17 passed. Ruff check,
format and mypy on four affected profile modules passed. XML/logs are in
`validation-artifacts/f19-set5-20261101/nc16-targeted-final.*` and `nc16-linux-checks.*`.

One fresh-DB diagnostic only: `tiewtrade_f18_release_set5_nc16_r1`, F19_SET5 W1 child,
100 core owners×20 baseline,10 paper workers,10 commands/s,5Hz publisher. W1 duration
remains600s in the profile; diagnostic bounds observation at180s and never accepts it.
Frozen candidate `/tmp/tiewtrade-set5-nc16-candidate-20261101` is based on2322d86 with
runtime source hash `1abe3f5343f2ad11353a9c0b24a336cb774a517790f366dc2007fc0816e9c4f1`.
Same VM3043373056 bytes/8 CPUs, PG4CPU/3GiB, uncapped runner and original pool inventory.
Container16:04:21.272669→16:10:39.456928 UTC, exit1/no OOM; setup200.277s.

**Failed at measured+172.298s, acceptance_result=false.** Dedicated LOSS_LIMIT→RESET
passed (attempt1 APPLIED, opening probe ORDER_SAFETY_UNAVAILABLE, no auto-resume).
This failure is the stop scenario's60s `wait_status(PARTIALLY_FILLED)` timeout, not a
core cycle deadline. Counters:1690 offered/1674 admitted and completed/0 rejected,
329 completed cycles. No W1 rerun and no W2/W3/W4 execution followed.

Failure identities and timeline, preserved in `nc16-r1/failure-branch.json`:

- Owner `17e9dba1-4380-4288-9036-db17a3711db8`, order
  `9de0d84b-3b30-57c8-b034-bbc0da1a91a9`, command
  `75c44660-b41b-4759-8bb8-a559b3dfda8f`; accepted16:09:36.367437 UTC.
- Resting BUY limit2, quantity1, queue_ahead0. One-shot key
  `ac055ec2-becf-4e06-b769-f77fef0f340b`, input1568/trade1545/quantity0.5,
  received16:09:38.377082 and committed16:09:38.380122 UTC exactly once.
- Owner persisted REBASE1566 at16:09:38.233593, then REBASE1575 at16:09:39.945148;
  no persisted decision consumes trade1568. Buffer1566..1575 is contiguous and retained.
  Input1567 was received16:09:38.365071, over1.5s before the next owner processing call.
  This evidence fits the stale-input recovery branch in
  `infra/paper_orders/worker.py:_next_or_recovery_inputs`: oldest input>1s selects latest
  book recovery, skipping the intervening trade. It is not a missing publisher commit.
- Worker process transaction16:09:39.921335→39.959870 waited0.000659s for pool and
  held connection0.037846s. Final order stays ACCEPTED, filled0/spent0. Re-publication
  would change the one-shot scenario and was not attempted.

Thus this run identifies an incompatible harness assumption: one ephemeral trade is
expected to remain executable until the loaded owner returns, while execution safely
rebases stale inputs. It does **not** prove that the earlier W1 API-pool failure has the
same cause, or that all underlying scheduling/performance problems are solved.

Transaction evidence: parent15446, paper69490, risk17107; all12 streams CLOSED without
truncation. Parent acquisition p99/max0.099687/0.816092s; paper0.008834/0.267298s;
risk0.038430/0.335116s. Risk includes102 DatabaseTimeoutError transactions.85 DB samples
observed34 blocking relationships;3862 state observations are unknown due role visibility,
so NULLs cannot establish absence of locks/waits.77 VM samples show no OOM increase,
minimum available1097543680 bytes; maximum sample collection1.0773s. Observation itself
adds overhead; comparison across runs is not controlled performance attribution.

All pools finalized with checked_out0; remaining database connections0. Partial-run
safety snapshot: duplicate fill execution0, duplicate RECORD execution0, negative
reservation0, negative position quantity/cost0. These do not replace full conservation
or other acceptance oracles. Failed DB dump+SHA256, candidate hashes, raw telemetry,
trace summary, environment/pool closure and branch receipts are retained under the
same artifact root (`nc16-*`, `nc16-r1/`). Task PG/Redis stopped with data preserved.

**Next checkpoint / Needs Clarification:** propose an approved harness amendment for
deterministic delivery of the scheduled one-shot to its target under load, preserving
the1s freshness rule, real workers, one publication, quantity0.5 and all safety checks.
The design must distinguish fixture coordination from a genuine worker-service delay;
if it requires production scheduling changes, propose a separate production amendment.
Do not add a NEW retry, replay the trade, relax freshness, change resources, or rerun
W1 before the scope is approved. V-20 stays Failed/Pending Full Validation;
V-21..24 stay Pending Dependency. No commit/push has been authorized for this checkpoint.

### NC-F19-17 — Harness fix verified; full W1 Failed on risk SLA (2026-11-01)

Owner approved NC17 with `apprve`. Implemented `profile_partial_barrier.py` using publisher
IPC encode/receive and existing real-worker recovery functions. Explicit F19_SET5 child
scheduled partial scenario arms owner/wallet/episode/order/pair/generation/key. A naturally
selected recovery reads the real latest book, publishes once through the parent and child,
then uses the original bounded following read. No production return values/timestamps,
matching decisions, recovery eligibility, scheduling priorities or locks are replaced.
Worker waits within captured-book1s freshness budget and W1 partial-stop+120s bound;
periodic source and core workload continue. Unknown commit/disconnect/duplicates fail
without another publication. Patch, IPC and pending control cleanup are bounded.

Changes are limited to this helper, workload wiring and targeted tests/specs. Public API,
schema, production code, pool/resource/load, financial and authorization rules, source
cadence and existing NEW/RESET retries remain unchanged. Transient harness IPC state is
not application session/business storage; persistent authority still resides in PostgreSQL.

Checks: targeted regression100 passed/24.627s, real-worker matrix3 passed/12.705s,
frozen Linux runner16 passed/14.531s; zero skips. Includes protocol faults/cancellation,
stale/unarmed/other-owner paths, existing matching-fence and process-recovery tests.
Real PostgreSQL/child/workers prove source visibility without isolation changes or
publication deadlock, one persisted trade/fill0.5/spent1, overlapping core BUY/SELL,
wallet9999/position0.4995/cost1, cancel reservation0 and stop/resume. Ruff/format and
mypy on four affected profile modules passed. Logs/XML and preflight receipts are
`validation-artifacts/f19-set5-20261101/nc17-*`.

First preflight Failed: restarted workers ran before parent arm, consumed the natural
recovery boundary and produced no READY. No trade was requested. The failed fixture's
remaining active orders also caused the later restore check to time out. Preserved
`nc17-real-worker-checks.log/xml` and DB `tiewtrade_f18_release_set5_nc17_checks`;
changed only test ordering (arm before restart) and reused run_scheduled_work to cancel/
join peers on failure. Corrected fresh-DB matrix (`..._checks2`) passes including restore;
no restore/production assertion was relaxed.

One W1 acceptance attempt, no extra short diagnostic: fresh DB
`tiewtrade_f18_release_set5_nc17_w1_r1`, core100×20 baseline,10commands/s,5Hz child,
10paper workers, original dedicated owners/schedules and600s measurement. Candidate
`/tmp/tiewtrade-set5-nc17-candidate-20261101` based on2322d86, runtime source hash
`dfd4cce5d4702afcb6dfee1e80347b6783bf035be0e1480201ede9ac1ec17a13` (working runtime
files still match). VM3043373056 bytes/8CPUs; PG4CPU/3GiB; runner uncapped; pools unchanged.
Runner16:30:41.738636→16:43:39.403146 UTC (~12m58s), exit1/no runner OOM.
Setup152.858s, measured elapsed including drain610.629s.

Functional/financial/resource/source evidence passed:

- Dedicated LOSS_LIMIT→RESET attempt1 APPLIED, opening blocked and no auto-resume.
- 6000 offered/admitted/completed,0 rejected;1200 cycles,2400 core fills,1200 cancels/
  replays;100/100 scheduled RESETs and stop conservation passed.
- Barrier target `b4053f1f-5e15-549f-b309-b0fd57883b73`, owner
  `03aaeb51-c45f-4e22-b161-4ed80afa27a2`: book1323→trade1325, generation1,
  key `0a7ec244-8084-4867-83e9-ac9f60b47c4e`; trade commit16:35:11.750880 UTC.
  Original following read consumed[1323,1324,1325]. Single publication, partial prepared,
  stop/cancel/release/resume completed; manual stop on other owner remains active.
- BOOK BTC and PRICE BTC/ETH each3000/3000 receipts in nominal600s, no allowance/exemption.
- All100 per-owner financial oracles and global invariants passed: expected5600 orders,
  2401 fills including scenario fill,1200 cancels/2000 baseline pending dispatch;
  unlinked fills/invalid reservations/invalid positions/wrong mode/duplicate effects0,
  input lag0. Engine transaction p95/p99=0.218810/0.339924s within0.5/1s.
- Resource assertions passed: peak per-process RSS89645056 bytes,55connections,
  sampled peak/end lock waits0. All pools returned and remaining connections0.

**Acceptance FAILED solely at the observed risk-SLA gate** (see result/analysis):
918703/918703 samples acknowledged,0 unacknowledged/clock errors;1302 samples exceed3s,
service99.8582784643% versus required99.9%, and56/100 owners fail their quota.3 samples
from one owner exceed hard5s, max5.034698s. The three correspond to inputs3069/3070/3071
ready16:34:12.308923 and acknowledged16:34:17.343621 UTC, before barrier activation.
Owner `3baa7030-605b-4b29-a2fe-ef1d1da5fc47` acknowledgment cursor3068 at
16:34:12.263526→3143 at16:34:17.343621, boundary473 unchanged. This owner has6
DATABASE_TIMEOUT log entries across the run; untimestamped logs do not attribute those
entries to this exact gap. Late samples occur in multiple windows, including well after
the completed barrier. No claim that removing barrier wait solves risk latency is supported.

Risk transaction SQL/lock/queue attribution is still unknown on this candidate. NC16
instrumentation was disabled for acceptance, so its different-run timings cannot close
that gap. No retry, threshold relaxation, resource increase or unchanged W1 rerun followed.
W2/W3/W4 and P6 were not started. Preserve Failed, not Partial/Passed.

Evidence: `nc17-w1-r1/result.json`, risk-late-inputs/worker/source/cycle/stop/barrier logs,
`nc17-w1-failure-analysis.json`, candidate/resource inventory, container outcome and
88,350,914-byte failed DB dump+SHA256. Task PG/Redis stopped with all DBs retained.
Next: use this full-run evidence to propose targeted risk-service latency investigation/
fix scope before production edits or another timed run. V-20 stays Failed/Pending Full
Validation; V-21..24 Pending Dependency. No commit/push, CI or merge performed.

### Risk latency analysis checkpoint — 2026-11-02

Executed the owner-requested analysis plan against existing NC17 artifacts only.
[Detailed analysis](risk-latency-analysis-2026-11-02.md) and reproducible derived scripts/
JSON are under `validation-artifacts/f19-set5-20261101/risk-latency-audit-20261102/`.
All21 raw evidence hashes remain unchanged. Independent first-eligible-ack reconstruction
matches all1302 late identities/918703 expected/3hard/56owner quota failures. No duplicate
measured inputs, stream timestamp regression or missing ack was found. All11 writers
were included;1239 late samples first qualify in risk-worker telemetry,63 in paper telemetry.

Measured-flag denominator includes902475 load samples (1293late/3hard) and16228 drain
samples (9late); no new exemption/verdict change was introduced. Stored successful
acknowledgements are post-commit observations, not exact historical server commit times.

Read-only retained PostgreSQL logs confirm137 configured owner-advisory-lock timeouts in
the inspected interval, including11/25 in +50..65/+240..270s. Saved only timestamp/PID/
classification/hash. These establish contention, not which owner's scheduler/lock/SQL
stage caused the5.08s ack gap. No production fix/evaluator defect is established.

NC-F19-18 is now a concrete **Proposed / Needs Clarification** amendment in plan/validation:
one300s fresh-DB diagnostic, risk-only stage spans plus commit-identity proof, unchanged
profile/thresholds and explicit non-acceptance. The owner's execution request preserves
its separate approval before instrumentation/run. No new runtime code/tests/services/
workload/W1, production edit, commit/push/CI or Live activity occurred in this checkpoint.
Next: owner approval of NC18; V-20 remains Failed/Pending Full Validation.

### NC-F19-18 execution checkpoint — 2026-11-02

Owner approved NC18. Harness-only risk-stage/transaction/commit observers implemented;
targeted116 passed/30.788s, frozenLinux38 passed/22.555s, zero skips. Ruff/format/mypy
passed. [Full report](risk-stage-diagnostic-2026-11-02.md) includes raw/derived artifacts,
coverage, observer overhead, UNKNOWN proofs, planned-cutoff warnings and metadata fix.

One300s fresh-DB diagnostic, unchanged profile, source hash
`03e4bb431cc77fafbcf55ce9f457446a10f8790707a061a341a7a3a0a0ce29b4`, exit0,
OBSERVATION_COMPLETE/acceptance_result=false. Core counters intentionally partial;
100RESETs APPLIED, one-shot/stop/resume complete.13streams CLOSED/no truncation,
24920proofs (23648VERIFIED/1272UNKNOWN),22547owner spans/234rounds.933observedlate
samples/155groups;0hard5s,552not-yet-acknowledged atcutoff. No W1 acceptance claim.

Measured sufficient cause of true3s violations:100selected owners queued behind4slots
and whole-page completion before rescan. Attempt10129/round106 waits3.161157s on
semaphore; pool0.013317s/ownerlock0.000890s/snapshot0.012062s/replay0.010731s.
Actualserverlatency3.411689s, clientdelay0.000940s.8groups wait≥3s on semaphore alone.
150linkedriskgroups allocate97.48%ofoldest-input budgets topreselection/slotwait;
these are overlapping latency budgets, not CPU seconds.170serverlocktimeouts,
168linked byPID/time. Prior same-owner timeouts amplify some gaps, not every gap.

148/152verifiedlategroups remainlate atservercommit;4groups/12samples are late only
atclientobservation.3groups/18samples haveUNKNOWNcommitproof. OldNC17hard5s didnot
reproduce, so it is not marked solved. No threshold/resource/polling/production change
was made by the diagnostic, and no unchanged rerun occurred.

Future diagnostic report metadata corrected toreflectactualRESETprogress/counters;
original300sartifact's `scheduled_resets_not_exercised=true` is inaccurate and retained
with correction documented inderivedreport. Only those reporting lines differ from
frozenruntime after the run; staticchecks pass and no diagnostic rerun is warranted.

Allpoolsfinalized/checked_out0, remainingDBconnections0; duplicatefill/RECORDexecution0,
negativeposition/reservation0 inpartial snapshot. Two cancellation warnings atcutoff
retained, not hidden. DBdump52678912bytes+SHA256/runnerlog/manifest/candidate/resource
inventories/rawtraces andderivedanalysis retained. TaskPG/Redisstoppedwithdata kept.

NC-F19-19 is now **Proposed / Needs Clarification**: boundedrollingmonitoradmission
usingtheexistingownertransaction,4activeslots/faircursor, noretry/resourceincrease.
Approval would cover production schedulerchange+targetedchecks+oneW1aftercheckspass;
Git/deployment not included. No production edits/W1/W2/W3/W4/CI/commit/push inNC18.
V-20 remainsFailed/PendingFullValidation; V-21..24PendingDependency. Next: NC19approval.

## NC-F19-19 checkpoint — approved/implemented, W1 blocked (2026-11-02)

Owner approved NC19. Rolling four slots/shared owner transaction/SQL active exclusion/
observer inventory implemented. Targeted35, fresh-DB safety26, Linux43 plus explicit
fresh-global4 and final targeted9 passed. Regression95 passed/1 fixture backlog failure
preserved and diagnosed; unchanged concurrency assertions pass on a fresh DB.
Ruff/format/mypy seven changed files and seven import contracts pass. Owner transaction
AST unchanged.

[NC19 report](rolling-monitor-2026-11-02.md) records a setup abort from missing marker
selection and subsequent W1 Failed/environment invalid: intended DB differed from all
nine connected role URLs. Baseline100x20/dedicated LOSS_LIMIT/RESET/opening-blocked passed;
later BOT resting NEW rejected SOURCE_UNAVAILABLE before load. No risk SLA conclusion
or proven production cause from this invalid environment. Raw69 files, DB dumps/hashes,
exact command identity, pending window, slot counts and cleanup evidence retained.

Runner guard now checks parsed URLs/all nine actual database identities/empty schema
before migration; self-test and real read-only verification passed. Stop after failure;
await authorization for one replacement W1 on a verified fresh DB with this guard.
No W2/W3/W4, further production fix, Git or deployment. V-20 Failed/Pending Full Validation;
V-21..24 Pending Dependency. Next: owner authorization for the replacement W1.

## Authorized replacement W1 — verified fresh DB, Failed (2026-11-02)

Owner authorized `approve W1 fresh DB rerun`; executed `nc19-w1-r3` on the intended
new DB, all nine actual role identities and empty schema/fixture verified. Same tested
source/hash/resources. Setup211.108s, baseline100x20/dedicated LOSS_LIMIT/RESET/opening
blocked and manual/BOT setup completed. At recorded+37.594s of load, child BOOK publisher
failed with SourceUnavailableError. No600s source/SLA verdict; counters277offered,
234admitted/233completed/0rejected,29cycles; interruption leaves incomplete work.

Single-recorder wall time reversed16.857ms while monotonic advanced18.732ms immediately
near the failure. Last committed book was READY/lease valid. This supports a clock/future
timestamp hypothesis, not proof of the exact failing guard condition or VM/NTP cause.
All13pools finalized/checked_out0, remaining connections0;92FILL identities no duplicates,
negative positions/reservations0; get_wallet/Money snapshot103wallets no negative balances.
These are partial checks, not full financial acceptance. Preserve cancellation warnings,
raw72files/hashes/fresh DB dump16,414,891bytes. No production edit or repeated tests/static
checks; no W2/W3/W4/Git/deployment. Task PG/Redis stopped with data retained.

See [fresh rerun evidence](w1-fresh-rerun-2026-11-02.md). Proposed NC-F19-20 scopes exact
BOOK readiness/clock failure arguments in a test-only observer plus one60s non-acceptance
diagnostic; awaiting owner approval. Alternative is read-only environment clock review
before choosing any further experiment. V-20 Failed/Pending Full Validation; dependencies
unchanged. Next: owner chooses next diagnostic scope, not another unchanged W1.

## NC-F19-20 — approved/implemented, one diagnostic Not Reproduced (2026-11-02)

Child-only BOOK failure-argument observer, bounded/complete trace and explicit exclusive
60s non-acceptance mode implemented.94Linux tests/zero skips, Ruff/format/mypy six files
pass; no production changes. All-nine-role/fresh-schema/empty-fixture guards pass.

One `nc20-r1` on tested hash `aa3fcb7009f53678ebe8b9b8765966a49b302ed29740f7df7270ffe094650cc8`:
setup181.451s, baseline100x20/dedicated LOSS_LIMIT/RESET/manual-BOT setup completed;
observation60.600486s,1203guard calls,0failures, trace closed/complete. **Not Reproduced**,
acceptance_result=false. No receipt clock reversal observed, not proof the old issue is
fixed. Original failed SQL-clock/book arguments remain unknown; no further fix chosen.

Partial safety:194FILL identities no duplicate/null IDs/negative positions/reservations;
103wallets no negative balances, one breach/audit match. All13pools finalized/checked_out0,
remaining connections0;14cancellation/termination warnings retained. No full financial/SLA
acceptance. RESET/later stop/barrier work Not Exercised.73original files/hashes,
DB dump18,051,985bytes, command/guard/source/resource evidence retained. Task PG/Redis
stopped with data kept. No rerun/W1/W2/W3/W4/Git/deployment.

[NC20 report](book-clock-diagnostic-2026-11-02.md). Next recommendation: read-only host/VM
clock configuration and existing-log review (10–20min), awaiting owner instruction under
the stop-on-no-reproduction rule. V-20 Failed/Pending Full Validation; dependencies unchanged.

## Clock environment review — read-only, no fix selected (2026-11-02)

Owner requested `เริ่มตรวจ clock environment`; reviewed selected host/Docker settings,
existing timed/kernel/powerd/pmset/VM logs and container privilege inventory. Host timed
records NTP receipt/apply activity09:29/09:45/10:01; no apply event at the r3 failure09:41:25.
Startup settimeofday adjustment at09:13 predates VM start09:16:53. No recorded sleep/wake
or VM restart near failure; caffeinate assertions span the run. Resource bounds match.
Guest logs lack clock-setter telemetry; exact origin and failing guard condition remain
unproved. UI switch unreadable: Computer Use denied twice, including owner-requested
retry; no setting changed. Operational NTP evidence does not depend on that UI read.

[Environment review](clock-environment-review-2026-11-02.md), selected events/scripts/hashes
in `clock-environment-review/`. No runtime code, new container/services, clock probe,
workload, system setting, Git or deployment changes. Documentation consistency checks only.

Proposed NC-F19-21 scopes one bounded clock-only host/VM comparison with uncertainty
and existing-log correlation; no trading/DB workload or privileged clock changes. Await
owner approval before implementation/sampling. Alternative: environment administrator
investigates retained evidence. V-20 Failed/Pending Full Validation; dependencies unchanged.


### NC-F19-21 execution checkpoint — 2026-11-02

22 probe regressions passed, zero skips; Ruff/format/mypy two files passed. One20min10Hz
trace completed:12000 contiguous exchanges, no gaps, guest exit0/noOOM, source verified.
40 guest offset movements recur at median29.999772s, including24 decreases(max2.994309ms).
Host has no offset decrease;504 increase intervals align with logged positive NTP adjtime,
not504 discrete steps.11930 conditional transport bounds/70 retained Unknowns; selected
sequence400 supports guest-relative backward offset movement beyond uncertainty.
Exact setter and original r3 guard cause remain unproved; no trading failure reproduced.
No setting/production/criteria changes or W1 rerun. Diagnostic complete/non-acceptance;
V-20 Failed/Pending Full Validation, dependencies unchanged. Next: separate environment
remediation proposal/approval; no automatic further diagnostic. See
[NC21 evidence](clock-comparison-2026-11-02.md).


## NC-F19-22 environment plan prepared — 2026-11-02

Owner instructed `เริ่มทำ` to prepare the next plan. Proposed isolated Linux validation
target, explicit candidate/resource/architecture comparison, reuse of bootstrap/guards/
clock probe, affected safety checks and one conditional W1 under unchanged criteria.
No machine purchased/provisioned, configuration/runtime/code/test changed, or workload run.
Needs Clarification: authorized disposable target/access/budget and approved inventory.
Plan/validation are Proposed, not approved by this preparation instruction. Next: owner
provides target and approves NC22 scope/manifest; may approve preflight plus conditional
W1 together. Stop on mismatch/failure; no automatic extra diagnostic rounds. Existing
Failed/Pending statuses preserved. Documentation consistency/diff checks only.


### NC22 local preparation — owner instructed เริ่มทำ (2026-11-02)

เริ่ม preparation ตามคำสั่งเจ้าของ: ตรวจ connection inventory แบบread-only พบเฉพาะ
local Docker contexts `default`/`desktop-linux` (active) และไม่มี `~/.ssh/config`;
ไม่พบ target ที่ยืนยันสิทธิ์ใช้เป็นdisposable Linux validation environment จากข้อมูลที่ตรวจ
นี่ไม่ใช่ข้อพิสูจน์ว่าเจ้าของไม่มีเครื่องอื่น จึงขอชื่อhost/SSH aliasและสิทธิ์ใช้งานไว้แล้ว

สร้าง local content-hash inventory ของsource/tests/schema/lock/config ที่เกี่ยวข้องใน
`validation-artifacts/f19-set5-20261101/nc22-preparation/`; ยังไม่ใช่final candidate freeze
ต้องตรวจซ้ำก่อนexecution ระบุreuse runner/DB guard/clock probeเดิม ไม่มีremote connection,
service/config/code changesหรือtest/workloadเพิ่ม การเริ่มทำไม่ยกเลิกtarget/manifest gates
ของNC22; ยังไม่ถือว่าอนุมัติเครื่อง/งบ/profileที่ไม่ระบุ และไม่ต้องขอเริ่มpreparationซ้ำ
ขั้นถัดไปที่บล็อก: รอเจ้าของระบุtarget/accessและยืนยันdisposable scope แล้วตรวจinventory
เพื่อเสนอmanifestจริงก่อนเปลี่ยนenvironmentหรือtimed run ผลFailed/Pendingเดิมไม่เปลี่ยน


## NC22 same-machine measurement audit — complete (2026-11-02)

Owner declined external machines and explicitly approved the replacement audit. Linux
target is no longer a prerequisite; earlier preparation is historical.261 raw hash entries
verified,9 source files matched; original NC17/18 workload and NC18 observer source contents
unavailable (gap retained).18 non-DB regressions and5 controlled cases completed; no services,
settings, production or harness changes. NC17 counts match the original; NC18 has source
commit proofs and3.161s monotonic queue wait. No evidence supports relaxing SLA, regrading
Failed, or subtracting NC21 offsets from old latencies.

Medium evaluator guard defect reproduced: a regressing stream can pass with clock_errors=0.
All44 actual acknowledgement files are ordered, so this does not explain the old failure.
A fail-closed per-stream ordering guard is proposed, not implemented. Next: owner approval
of that patch, not another workload. V-20 Failed/Pending Full Validation and dependencies
unchanged; no Git actions. [Report](measurement-audit-2026-11-02.md). Documentation/diff
checks passed; runtime files preserved.


### NC22 stream-order guard checkpoint — 2026-11-02

Owner approved the narrow guard fix. Implemented in `profile_workload.py::sla_summary`
and covered in `test_workload_sla.py`. Each stream is validated before pending/owner
filtering, including trailing rows after all inputs have acknowledgements. Parsed datetime
keys keep validation and merge ordering consistent. Equal timestamps remain valid; every
row is preserved, with no sorting/dropping/clamping/clock correction. All regressions are
counted; only the first20 file/line/timestamp diagnostics are retained. Additive fields
`stream_order_errors` and `first_stream_order_errors` are separate from `clock_errors`.
Any ordering error forces overall passed=false; existing numerical SLA counters remain.

27 non-DB regressions passed, zero skips (18 existing +9 cases): would-be pass/miss under
F18/F19, filtered pending/foreign-owner rows, equality, earliest interleaved worker results,
and bounded diagnostics with full error count. Ruff/check, format/check and mypy two files
passed. Initial mypy invocation could not resolve local src and reported235 import/type
errors; corrected invocation `MYPYPATH=src` passes without source/config suppression.
DB rollback/savepoint tests reused; no services/workload/settings/production changes.

Artifacts: `validation-artifacts/f19-set5-20261101/nc22-stream-order-guard/` contains test
XML, static log/summary, exact evaluator patch and candidate hashes. Original audit/run
artifacts remain unchanged. Historical audit.py expects the prepatch evaluator (matched
NC20 snapshot retained in audit snapshots); its counterexample assertions must not be
rerun against the patched evaluator as though they were new acceptance criteria.

Guard defect fixed, not an environment/latency fix. Existing44 real acknowledgement files
were ordered, so this does not explain or regrade original failures. V-20 remains Failed /
Pending Full Validation; W2/W3/W4 and dependencies unchanged. Next recommendation: review
this narrow patch before deciding the next clock/acceptance amendment; no automatic timed
run or new diagnostic. No commit/push. This subtask does not trigger full-feature Ready
for Code Review or authorize refactor/full validation.


### NC22 guard refactor checkpoint — 2026-11-02

Owner-authorized refactor complete, limited to the guard and its new tests. Named previous
observed/raw timestamp fields replace tuple indexes; adjacent line identity comes from
enumeration and filename is computed once per stream. Local `write_risk_stream` removes
repeated JSONL serialization in the new tests; existing fixtures/ack builders remain in
use. Preservation test compares original bytes. Verdicts, counters, cap20, diagnostics,
merge/filter order and all SLA/financial behavior unchanged; no new infrastructure.

27 non-DB tests passed, zero skips; two-file Ruff/check, format/check and mypy passed
(`MYPYPATH=src`). Validation after refactor covers only the affected Feature/evaluator
criteria; DB/safety evidence remains valid. Approved stop on timed runs still applies:
no W1, other workload, new diagnostic or settings change. No production change.

Artifacts in `validation-artifacts/f19-set5-20261101/nc22-stream-order-refactor/` retain
before-source copies, exact refactor diff, test XML, final hashes and check summary.
This finishes the authorized guard/refactor checkpoint. Next: owner may instruct commit/
push of this checkpoint under Git rules; no Git action occurred. V-20 Failed/Pending Full
Validation and clock/old-latency/source-evidence limitations remain; do not infer a W1pass.


### NC-F19-23 clock-setter preflight — Incomplete 2026-11-02

Owner approved the same-machine read-only tracefs gate and one conditional90s trace.
The unchanged VM remained8CPU/3,043,373,056bytes and the pinned runner image ID matched.
The preflight observer was root/host-PID with only CAP_SYS_ADMIN after cap-drop ALL,
privileged=false, network none, read-only root and0.1CPU/64MiB. Only tracefs and frozen
source were read-only mounted; no Docker socket or application/database service was used.

The observer exited1/noOOM after0.565s because `/tracefs/trace_clock` was absent. It could
not establish private instances, mono or the eight required syscall events. Classification
is **Incomplete**, not Not Reproduced. No trace instance/event/buffer was created, so there
was no instance cleanup; no instrumentation/tests/90s run/W1 followed. No install, restart,
fallback tracer, extra capability, confinement relaxation or setting change was attempted.

Independent current hashes for `risk_limit.py`, `risk_limit_main.py` and the scheduler
test match the measured NC19 manifest exactly; its prior authoritative transaction/lock,
concurrency4, UUID fairness and cancellation/engine-cleanup evidence remains valid. No
production/test source changed or reran. Evidence: [NC23 report](clock-setter-preflight-2026-11-02.md)
and `validation-artifacts/f19-set5-20261101/nc23-clock-setter/preflight/`.
V-20 stays Failed/Pending Full Validation. Next requires owner direction and approval of
a new amendment; NC23 does not authorize tracing enablement, another method/run, settings,
production changes or W1. No commit/push.


### NC-F19-24 amendment prepared and approved — 2026-11-02

At the owner's `เริ่มทำ` instruction, prepared a same-machine amendment only; no
environment or runtime action was taken. Official kernel documentation confirms tracefs
must be mounted to expose its controls, while Docker documents SYS_ADMIN/default-seccomp
capability handling. The proposal uses one ephemeral mount inside the observer's private
mount namespace, retains privileged=false/CAP_SYS_ADMIN-only/default confinement and all
NC23 resource/redaction/output/cleanup bounds, and adds an exact rollback verification.

Execution is gated: a confinement denial or missing capability stops without fallback;
the90s trace is conditional on a passing mount/event preflight in the same execution.
No restart, install, settings/NTP, production/schema/scheduler, DB/trading service, SLA or
W1 change is included. V-20 remains Failed/Pending Full Validation. Owner subsequently
approved `NC-F19-24`; implementation, controlled tests and one conditional execution may
proceed. No repeat, W1, remediation, production change or Git action is authorized.


### NC-F19-24 execution — Incomplete, stopped 2026-11-02

Added the bounded stdlib observer and controlled tests. Final result:45 tests passed,
zero skips; Ruff check/format and mypy passed. One conditional execution used the exact
approved container profile and unchanged VM, ran5.772s, exit2/noOOM. Its result was stored
only on tmpfs and unavailable after exit, so exact mount/trace/cleanup evidence is missing.
The execution is Incomplete and was not repeated.

The single cleanup-only helper confirmed CAP_SYS_ADMIN-only, NoNewPrivs1 and Seccomp2,
then hit OSError reading unavailable `/proc/self/attr/current` before mount. Thus its
reported no-op cleanup values do not verify absence of the exact prior instance; cleanup
remains unverified and no helper2/fallback was used. Executed source ordering and identical
profile strongly support the same pre-mount branch for the original, but lost output
prevents claiming proof.

Fixed only the harness evidence path afterward: stdout result, explicit LSM gate and
fail-closed cleanup-before-mount; tests/static pass, no execution followed. No production,
schema/API/financial/scheduler/settings, DB/trading/workload or W1 change. NC19 hashes
still match. Evidence: [NC24 report](clock-setter-nc24-2026-11-02.md) and
`validation-artifacts/f19-set5-20261101/nc24-clock-setter/`.
Setter remains Unknown; V-20 Failed/Pending Full Validation, dependencies unchanged.
Next action requires a new owner-approved amendment. No commit/push.


### NC-F19-25 plan prepared — awaiting owner choice 2026-11-02

At owner instruction `เริ่มทำ`, performed read-only inventory only. Docker advertises
built-in seccomp/cgroup namespaces but no AppArmor/SELinux; both prior containers have
empty AppArmorProfile and the approved restrictions. This explains why the guest LSM
file is not an appropriate standalone gate without relaxing confinement.

Proposed Option A combines exact NC24-residue cleanup, preflight, one conditional90s trace
and verified cleanup in one execution with durable stdout/Docker-log evidence; missing LSM
is accepted only under an exact host+guest security match. Tests/static checks precede it;
no repeated trace follows. Option B stops clock tracing with current Unknown/Incomplete
evidence. NC25 is explicitly terminal for same-machine ftrace: no automatic NC26.

No code, mount, helper, container, service, setting, workload or W1 action occurred in this
planning step. V-20 remains Failed/Pending Full Validation. Next: owner chooses and, for
Option A, explicitly approves `NC-F19-25`. No Git action.


### F-19 SLA amendment — requirements approved; plan/validation awaiting approval 2026-11-02

Owner approved per-owner and run-wide99.5%≤3s,99.9%≤5s and every input≤6s, with
complete acknowledgements and all correctness/safety gates unchanged. Owner selected stop
NC25 before implementation/execution and requires all-or-nothing Paper+Live production
activation after the full integrated candidate passes release/dependency gates.

Offline inspection of immutable NC17 result gives run99.858278% and worst owner99.575487%
within3s; only3/918703inputs exceed5s, giving run99.999673% and affected-owner99.967346%
within5s; max5.034698s. These support the proposed tiers but do not certify the later NC19
scheduler/final candidate. Original Failed evidence remains unchanged.

Prepared plan/validation to update only the explicit F19 evaluator and boundary tests,
derive a separate NC17 re-evaluation, exclude diagnostic observer code from release, and
defer one workload to the final integrated candidate. No evaluator/test/runtime/mount/
service/workload change was made at this checkpoint. Next: owner approval of amended
plan/validation before implementation. No Git action.


### F-19 revised SLA amendment — Feature passed 2026-11-02

Owner approved the amended plan/validation. Updated only the explicit F19 evaluator and
its regression: per-owner/run-wide99.5%≤3s,99.9%≤5s and every input≤6s are independent
gates; missing/pending/clock/stream-order evidence remains fail-closed. F18 behavior and
result schema remain unchanged. The final affected non-DB suite passed40 tests; Ruff
format/check and mypy passed. No production/API/schema/trading code or W1 changed.
Post-review refactor consolidated repeated price-input and risk-acknowledgement fixtures
into the existing test helpers; the same40 tests/static checks passed without behavior change.

Re-evaluated NC17 from a temporary copy:918703/918703 acknowledgements, zero clock/order
errors, run/worst-owner 3s fractions0.998582784643/0.995754871013, run/worst-owner 5s
fractions0.999996734527/0.999673451616 and max5.034698s. The derived Feature result passes;
all30 non-SLA acceptance terms are crosswalked (26Passed/4W1 N/A). Original raw hashes and Failed verdict remain
unchanged. NC23/24 setter observer source/tests were excluded while historical artifacts
remain; NC25/further tracing stay stopped.

Evidence: [revised SLA report](revised-sla-evaluation-2026-11-02.md) and
`validation-artifacts/f19-set5-20261101/revised-sla-20261102/derived-result.json`.
This does not pass Batch/System Ready: final integrated Paper+Live workload and V-20..24/
release dependencies remain Pending, and both production modes remain off. No Git action.
