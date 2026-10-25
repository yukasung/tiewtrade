# F-15 M5 — Candidate review and validation checkpoint

วันที่: 2026-10-19–20; branch `feature/f-15-paper-order-matching`; base HEAD
`2eb3000711353e76d81f32e9c9c08287f6788702`; candidate commit
`77210cdf71a6d93003c18fcaced9b170ef28105e`; [Draft PR #19](https://github.com/yukasung/tiewtrade/pull/19)

M5 ทำ deep review, ปิด Critical/High finding ที่พบ และรัน candidate gates ในเครื่องแล้ว
backend full regression ผ่านใน invocation เดียวเมื่อ 2026-10-20 และ required CI ของ
candidate commit ผ่านครบ 6 jobs; fault matrix ที่ระบุใน V-13/V-15 และ V-19 ยังคงตามสถานะเดิม

## Review findings ที่แก้แล้ว

- **High — F-14 conflict ถูก rollback พร้อม transaction ของ fill:** เมื่อ
  `stage_fill_cash()` คืน `CONFLICTED` worker เดิมโยน integrity error ทำให้ conflict
  fingerprint/audit ที่ F-14 บันทึกถูก rollback ไปด้วย แก้โดย rollback fill/order/cash/checkpoint
  ทั้ง batch ก่อน แล้ว replay เฉพาะ deterministic F-14 conflict ใน transaction ใหม่ ตรวจว่า
  status เป็น `CONFLICTED` และมี `failure_code` ก่อน mark order activity/dispatch terminal
- **Medium — migration safety test เทียบ command ก่อน worker กับ terminal result:** แก้ให้ยืนยัน
  terminal command ที่อ่านก่อน downgrade จึงตรวจว่า downgrade refusal ไม่เปลี่ยน durable result จริง
- **Medium — network isolation allowlist ไม่รู้จัก F-15 feed composition:** เพิ่ม
  `order_book.py` เป็นผู้เรียก HTTP/WSS transport กลางที่อนุญาต โดย gate ยังห้าม direct network
  client และ transport bypass เช่นเดิม
- **Low — controlled fill/reset test นับงานทุก owner แบบ exact:** worker ทำ fair batch ข้าม owner
  ตาม contract จึงเปลี่ยน assertion เป็นอย่างน้อยหนึ่งงาน พร้อมยืนยัน command, episode, cash,
  execution link และ reset result ของ owner เป้าหมายแบบ exact

รอบสุดท้ายไม่พบ Critical/High ค้างจาก diff และ dependencies ที่เกี่ยวข้อง

## Controlled safety coverage ที่เพิ่มใน M5

- reset/admission ใช้ advisory lock เดียวกัน; stale intent ไม่ถูกย้ายเข้า episode ใหม่
- fill/reset ใช้ financial lock เดียวกัน; fill ที่ commit ก่อนทำให้ reset เห็น open position และ
  ปฏิเสธ `RESET_UNSAFE` โดย cash/position/order อยู่ใน episode เดิมครบชุด
- repeatable GET/reset barrier คืน snapshot เก่าหรือใหม่ที่สอดคล้องกัน ไม่ผสม pointer/capital/revision
- cancellation และ timeout หลัง reset เขียน capital ledger แล้ว rollback closure/episode/ledger/result/audit
  ทั้งชุด และ command เดิม recover สำเร็จ
- source proof ที่ถูกทำให้ mismatch และ source activity ที่ถูกทำให้ `CONFLICTED` ทั้งฝั่ง position/order
  รวม 4 กรณีคืน `ACTIVITY_UNKNOWN` ไม่รายงาน reset-ready
- downstream F-14 conflict ผ่าน caller จริง: conflict/audit คงอยู่หนึ่งชุด ขณะที่ order fill,
  trade cash และ checkpoint ของ batch ที่ล้มไม่ commit

## Verification

Environment: Windows host, Linux Python 3.12 container, PostgreSQL 16/Redis 7,
runtime roles จริง และ Chromium Playwright; clean full rerun ใช้ PostgreSQL/Redis containers ใหม่
ที่ ports 55436/56380 โดยไม่มี worker, diagnostic หรือ test container อื่นทำงานซ้อน
รอบยืนยันสุดท้ายใช้ PostgreSQL/Redis ชุดใหม่บน Docker bridge network เดียวกับ test container
เพื่อตัด Windows host NAT และไม่มี workload อื่นทำงานซ้อน

| ตรวจ | ผล |
|---|---|
| focused M5 races/faults/conflict/migration/network gate | **PASS** หลังแก้; source matrix 4 cases และ fill/reset barrier ผ่าน |
| fresh migration regression | **7 passed** สำหรับ migration suite; 0037 cycle/downgrade refusal ที่เกี่ยวข้องผ่าน |
| backend broad full run | **2931 passed, 1 skipped, 2 deselected; 2 failed, 1 setup error** ใน invocation เดียว; F-15 assertion ถูกแก้และผ่านซ้ำ ส่วน database-unavailable 2 จุดผ่านซ้ำบน fresh DB รวม rerun **3/3 passed**; จึงบันทึก full gate เป็น Partial ไม่อ้างว่าเขียวครบ |
| clean backend full rerun 2026-10-19 | **2929 passed, 1 skipped, 2 deselected; 3 failed, 2 errors** ใน **1393.10s (23:13)**; ทั้ง 5 จุดเป็น PostgreSQL connection timeout/`DatabaseUnavailableError`, PostgreSQL ไม่ restart/OOM และยัง ready หลังจบ; isolated fresh DB rerun ของ exact 5 node IDs ผ่าน **5/5 ใน 3.90s**. Full gate ยังคง Partial เพราะ invocation เดียวไม่เขียว |
| bridge-network full rerun ก่อนแก้ fixture | **2933 passed, 1 skipped, 2 deselected; 1 failed** ใน **598.07s (9:58)**; ตัด database timeout ออกแล้วและพบ ring-wrap fixture ใช้ timestamp เกิน freshness 1 วินาทีระหว่าง workload |
| ring-wrap regression หลังแก้ fixture | **1 passed** ใน **11.84s**; retry input ID เดิมด้วย server timestamp ใหม่โดยไม่ขยับ sequence และไม่เปลี่ยน production freshness rule; Ruff/format ผ่าน |
| final clean backend full run 2026-10-20 | **PASS — 2934 passed, 1 skipped, 2 deselected** ใน **562.02s (9:22)** บน PostgreSQL/Redis ใหม่และ Docker bridge network; ไม่มี test/diagnostic/worker ซ้อน |
| post-review refactor 2026-10-20 | รวม wallet revision SQL 8 จุดไว้ใน helper เดียว, รวม UI success cleanup และย้าย correction imports/type ให้ชัดเจนโดยไม่เปลี่ยน transaction/business logic; execution-market **49 passed**, PaperWalletPanel **8 passed**, Ruff/format, mypy **443 files**, ESLint, TypeScript และ import-linter **7 kept / 0 broken** ผ่าน |
| post-review fixes 2026-10-20 | duplicate order ID จบแบบ `ORDER_CONFLICT`; CANCEL ผูกกับ NEW command ที่ตรงรายการ; CREATE/RESET initialize position/order sources ใน transaction เดียวกัน; แยก legacy/production wallet fixtures และแก้ async role-test harness โดยไม่เปลี่ยน production behavior |
| post-review final clean backend full run 2026-10-20 | **PASS — 2935 passed, 1 skipped, 2 deselected** ใน **560.07s (9:20)** บน PostgreSQL/Redis ชุดใหม่; รัน test runner เดียวโดยไม่มี diagnostic/worker ซ้อน |
| Ruff check/format | **PASS**, 482 files formatted |
| mypy | **PASS**, 443 source files |
| import-linter | **7 kept / 0 broken**, 239 files / 1529 dependencies |
| frontend lint/typecheck/unit/build | **PASS**, unit **246 passed / 26 files** |
| Chromium full E2E | **18 passed** โดยเปิด chart flags ตาม CI; Paper wallet ยืนยันว่า CREATE initialize sources และ RESET ใช้งานได้ทันทีหลัง worker commit |
| OpenAPI/generated TypeScript | OpenAPI SHA-256 คงเดิม `C66CDC88D54C80EA67A874278DDD68B31B15F734E5430F0813AED4E089A8F021`; generated diff ไม่มี semantic drift |
| Docker Compose build | **PASS**: api, migrate, market-data, paper-wallet-worker และ frontend images |
| `git diff --check` | **PASS**; มีเฉพาะคำเตือน LF/CRLF ของไฟล์ frontend เดิม |
| required CI บน candidate commit | **PASS** — [run #116 / 39398771492](https://github.com/yukasung/tiewtrade/actions/runs/39398771492) ผ่านครบ 6 jobs บน `77210cdf71a6d93003c18fcaced9b170ef28105e` |

full run ที่ mount เฉพาะ `backend` ถูกตัดทิ้งเพราะ tests อ่าน `/repo/specs`, `.github` และ
`compose.yaml`; diagnostic ที่ชนกับ container full run บน DB เดียวกันถูกตัดทิ้งเช่นกัน
ไม่ใช้สองรอบนี้เป็นหลักฐานผ่านหรือล้ม. Clean rerun ข้างต้นเป็น invocation ที่ valid และเก็บผลล้มไว้
ตามจริง; exact-five rerun ใช้ database และ Redis namespace ใหม่หลัง full container หยุดแล้ว

## Coverage ณ checkpoint นี้

- V-12 ปิด downstream-invalid caller และ atomic conflict persistence แล้ว
- V-13 เพิ่ม corrupted/conflicted source matrix; initialization/rebuild ยังคง fail closed
- V-14 เพิ่ม controlled admission/fill/GET barriers และ browser full regression
- V-15 เพิ่ม cancellation/timeout recovery; unknown commit/process kill และ Redis/generation matrix
  แบบเต็มยังคง Partial แม้ Paper workers ใช้ PostgreSQL scan และไม่มี Redis dependency
- V-18 ผ่าน: review/static/frontend/contracts/browser/container, backend full invocation
  เดียว และ required CI run #116 ผ่านครบแล้ว
- V-19 คง Pending Full Validation สำหรับ M6 workload/endurance/restore

final diff review/checkpoint หลัง full run ไม่พบ Critical/High ใหม่; M6 ยังแยกเป็น release
checkpoint ตามแผน และ fault matrix ที่ระบุ Partial ต้องเก็บสถานะเดิมจนมีหลักฐานครบ

## Post-M5 dispatch fairness — 2026-10-20

HEAD ขณะตรวจ `555bb8cac66857b7ddc7ca59b8d80d77d052618e` พร้อม working-tree changes;
ผล candidate/CI ข้างต้นเป็นหลักฐานของ revision เดิม ไม่ครอบคลุม production diff หลัง M5 ทั้งหมด

NC-F15-09 อนุมัติให้แก้ตามแผนเดิมแล้ว: ลบ UPDATE ที่เลื่อน due time ของทุก PENDING
command เมื่อรับคำสั่งใหม่ เพราะ arrivals ต่อเนื่องเลื่อนงานเดิมออกไปซ้ำได้
คง due-order scanner และ claim fencing เดิม ไม่มี priority policy ใหม่
เพิ่ม regression ตรวจ due time และ scanner หลัง enqueue ซ้ำ; worker tests ยอมให้งานเก่า
ได้รับหนึ่งรอบก่อนงานใหม่ โดยยังตรวจ duplicate rejection, cancel และ reservations ตามเดิม

หลักฐานใช้ PostgreSQL container เดิมที่ port 55447 แต่สร้าง DB แยก
`tiewtrade_f15_dispatch_review`, bootstrap ทั้งสอง scripts และ migrate ถึง head ด้วย runtime roles จริง
ไม่มี Python test/worker process อื่นตอนเริ่ม; ไม่ใช้ข้อมูล workload DB และไม่ต้องใช้ Redis ในชุดนี้
Alembic CLI อ่าน config ด้วย Windows locale ไม่สำเร็จสองครั้งก่อน migration จึงใช้
Alembic Config API ตั้ง `script_location=migrations` แล้ว upgrade head สำเร็จ
ไม่ได้เปลี่ยน migration หรือ tooling ของโปรเจกต์

| ตรวจ | ผล |
|---|---|
| regression `test_new_arrivals_do_not_postpone_existing_pending_commands` ก่อนแก้ | Failed ตามคาด: due time ของงานเก่าถูกเปลี่ยนเมื่อรับคำสั่งใหม่ |
| `uv run pytest tests/infra/execution_market/test_dispatch.py tests/infra/execution_market/test_worker.py tests/infra/execution_market/test_evidence.py -q --tb=short` หลังแก้ | 22 passed / 1 failed; test duplicate terminal command คาดว่าแซงงานเดิมทันที |
| exact failing node หลังแก้ test ให้ drain งานเก่าก่อน | Passed; assertions REJECTED/ORDER_CONFLICT และ cancel success คงเดิม |
| Ruff check + format check สำหรับ dispatch.py, test_dispatch.py, test_worker.py | Passed; 3 files formatted |
| `uv run mypy src/tiewtrade/infra/paper_orders/dispatch.py` | Passed |

ใช้ผล 22 tests เดิมต่อเพราะการแก้รอบสุดท้ายแตะเฉพาะ test node ที่ล้ม ไม่รันทั้งชุดซ้ำ
ยังไม่มี full regression/required CI สำหรับ working tree นี้

งานค้างก่อน Development Complete: ตรวจ batch rollback/retry และ bulk persistence/replay
ที่เปลี่ยนหลัง M5, V-13 explicit init/fill barrier, V-15 unknown-commit/process-kill
และ recovery matrix ที่ยังขาด, reconcile V-1..18 กับหลักฐานเดิมและ final candidate checks
W1–W4 คง Pending Full Validation; smoke ไม่ปิดเกณฑ์ชุดเต็ม

## Post-M5 batch rollback and init/fill barrier — 2026-10-20

ตรวจต่อบน HEAD/working tree และ DB แยกเดียวกับ dispatch checkpoint ข้างต้น
รอบนี้แก้เฉพาะ test_worker.py และเอกสาร ไม่พบเหตุให้เปลี่ยน production logic ในกรณีที่ตรวจ
ใช้ scenario accept/restart/fill/correction เดิมเพิ่ม fault cases โดยไม่สร้าง harness อีกชุด

- หลัง input แรกลง fill/F-14/cash แล้ว inject failure หลังเขียน input ที่สอง:
  evidence, execution links, ledger และ order events rollback กลับ baseline ทั้ง batch
- inject failure หลัง bulk projection และหลัง bulk reservation write:
  wallet revision/balance, order status/filled และ reservation ไม่เปลี่ยนจากก่อนรอบ
- retry ใช้ command และ inputs เดิม; ตรวจ fill link หนึ่งรายการ, cash 9900,
  evidence สามรายการ และ INPUT_APPLIED หนึ่งรายการ พร้อม correction/replay เดิม
- ตรวจ projection/reservation/activity revision ตรงกัน และ last_event_id ตรง immutable event ล่าสุด
- init/fill ใช้ asyncio Events บนสอง transactions: พัก fill หลัง reservation write ใต้ financial lock,
  เริ่ม initialization จนถึง lock attempt แล้วปล่อย fill; initialization หลัง commit เห็น cash 9900
  และ reset unavailable ไม่ล้าง source ให้กลายเป็น empty/idle
  มี timeout สำหรับจับ deadlock และ cleanup tasks ทุกทาง ไม่ใช้ sleep จัด interleaving

ผล: targeted parameterized scenario **5 passed** หลัง assertions สุดท้าย
(`uv run pytest tests/infra/execution_market/test_worker.py -k accept_restart_fill -q --tb=short`);
Ruff check ผ่าน, Ruff format จัดรูปแบบแล้ว และ mypy ของ worker/storage/matching_storage ผ่าน 3 files
ใช้ผลชุดอื่นจาก checkpoint ก่อนต่อ เพราะ production code ไม่เปลี่ยนในรอบนี้

ขอบเขตที่ยังไม่รับรอง: bulk persistence หลายคู่/หลายออเดอร์และ replay matrix ทั้งหมด,
unknown commit/process kill จริง และ recovery matrix เต็มของ V-15
V-13 มี explicit fill-before-init barrier แล้ว แต่ยังไม่ยกทั้ง criterion เป็น Passed
V-18/required CI สำหรับ candidate ใหม่และ V-19 ยังคงค้างตามเดิม

## Post-M5 multi-pair persistence and lost reply — 2026-10-20

ใช้ DB/HEAD เดิมจาก dispatch checkpoint พร้อม working-tree tests ใหม่
ไม่มี production code เปลี่ยนในรอบนี้

- `test_matching_storage.py` สร้าง BTC สองออเดอร์และ ETH สองออเดอร์ผ่าน command,
  domain admission และ storage writers จริง แล้ว cancel BTC หนึ่งรายการและอ่านใหม่
  ยืนยัน ETH checkpoint ไม่เปลี่ยน, BTC ที่เหลือ rebuild ได้, reservation ตรง 0/100/100/100,
  revision ของทั้งสี่ projections/reservations ตรง activity และ last_event_id ตรง events ล่าสุด
  ขอบเขตนี้เป็น storage integration ใช้ explicit test-only policy/constraints ไม่ใช่ public feed end-to-end
- เพิ่ม `lost_commit_reply` ใน worker scenario เดิม: wrapper ปล่อย PostgreSQL commit จริงก่อน
  โยน ConnectionResetError ที่ขอบ transaction return ให้ production error handling รับ
  จากนั้นสแกน/replay คำสั่งเดิม; ยืนยัน cash=9900, fill link=1, evidence=3,
  INPUT_APPLIED=1 และ correction/replay เดิมยังผ่าน
  เป็น fault injection ที่จำลอง acknowledgement สูญหาย ไม่ใช่ network disconnect/process kill จริง

คำสั่ง targeted:
`uv run pytest tests/infra/execution_market/test_matching_storage.py tests/infra/execution_market/test_worker.py -k 'bulk_checkpoint or lost_commit_reply' -q --tb=short`
ผล **2 passed**; Ruff check/format check ของสองไฟล์ผ่าน และ diff check ผ่าน
ใช้ mypy production และ tests อื่นจากรอบก่อนต่อ เพราะเปลี่ยนเฉพาะ tests branches ใหม่

ปิดช่องว่าง bulk multi-order/multi-pair สำหรับกรณีข้างต้นและ commit-success/reply-loss branch
แล้ว; V-15 ยัง Partial สำหรับ process-kill จริง, commit transport uncertainty และ recovery
matrix ส่วนที่ยังไม่มีหลักฐาน ไม่ใช้ผลนี้ยกทั้ง V-15 หรือ V-18 เป็น Passed

## Post-M5 real worker process kill — 2026-10-20

`test_process_recovery.py` ใช้ subprocess Python จริงและ runtime engine role บน DB แยกเดิม
child claim คำสั่งที่รับแล้ว จากนั้น parent ส่ง fresh market input และปล่อย stdin barrier
child ยืนยันว่าเขียน execution link แล้วก่อนแจ้ง BEFORE_COMMIT หรือ AFTER_COMMIT
parent รอ marker แล้ว kill process จริง ไม่ใช้ exception แทน process death

- ก่อน commit: เงินยัง 10000 หลัง kill; lease expiry ถูกเร่งเฉพาะ dispatch metadata
  แล้ว worker ใหม่กู้คำสั่งเดิมด้วย fresh inputs ได้
- หลัง commit: เงิน 9900 คงอยู่ และ scan/replay คำสั่งเดิมไม่ลงผลซ้ำ
- ทั้งสองทางจบ FILLED, reservation=0, execution link=1, TRADE_CASH entry=1,
  position=0.999 BTC และ cost=100 USDT; terminal command replay คืนผลเดิม
- ใช้ stdout/stdin markers คุม kill boundary; sleep 120ms ใช้เฉพาะ eligibility floor
  มี timeout/kill cleanup สำหรับ child ไม่ปล่อย worker ค้าง

`uv run pytest tests/infra/execution_market/test_process_recovery.py -q --tb=short`
**2 passed** หลังเพิ่ม position assertions; Ruff check/format check และ diff check ผ่าน
ไม่มี production code เปลี่ยน ใช้ static/type-check production เดิมต่อ

ปิด process-kill ก่อน/หลัง fill commit ใน V-15 สำหรับกรณีนี้เท่านั้น
ยังไม่ครอบคลุม wallet RESET process-kill, transport disconnect ระหว่าง COMMIT
หรือ recovery matrix ทั้งหมด จึงยังคง V-15/F-13 closure เป็น Partial

## Post-M5 RESET process kill — 2026-10-20

ขยาย child/barrier ใน `test_process_recovery.py` เดิมให้เรียก wallet claim/process จริง
kill ก่อน/หลัง RESET commit บน PostgreSQL DB แยกเดิม ไม่เปลี่ยน production code

- ก่อน commit: active episode และทุน 10000 เดิมคงอยู่ มี episode เพียงหนึ่งรายการ
  หลังเร่ง claim expiry เฉพาะ dispatch metadata แล้ว recovery สร้างรอบใหม่ทุน 2000
- หลัง commit: recovery ไม่เปลี่ยน episode ที่ commit แล้ว
- ทั้งสองทางจบด้วย 2 episodes, 1 closure, 2 capital ledger entries และ reset success audit 1
  snapshot รอบใหม่ reset-ready; `inspect_submission` ด้วย key/payload/expected episode เดิม
  คืน terminal result เดิมตามเส้นทาง API

รอบแรกของไฟล์รวม: fill-kill เดิม **2 passed**, RESET **2 failed** เพราะ test เรียก
`admit_command` ซ้ำโดยข้าม `inspect_submission` ซึ่งเป็น replay lookup ที่ API เรียกก่อน admission
แก้เฉพาะ test ให้ใช้ contract เดิม จากนั้น
`uv run pytest tests/infra/execution_market/test_process_recovery.py -k reset -q --tb=short`
**2 passed**; Ruff check/format check และ diff check ผ่าน
ไม่รัน fill-kill ซ้ำเพราะการแก้สุดท้ายอยู่ใน RESET replay branch เท่านั้น

ปิด RESET process-kill ก่อน/หลัง commit สำหรับกรณีข้างต้น
V-15 และ F-13 closure ยัง Partial: commit transport uncertainty และ recovery matrix ที่เหลือ
ต้อง reconcile กับหลักฐานเดิมก่อนรับรองครบ; ไม่รัน full regression/workload ในรอบนี้

## Closure pass — real COMMIT disconnect and affected regression — 2026-10-20

- execution_market/paper_wallet/positions regression ทั้งสาม directories ผ่านบน DB
  `tiewtrade_f15_dispatch_review` ก่อนเพิ่ม proxy case
- เพิ่ม local plaintext PostgreSQL proxy เฉพาะ test: หลัง upstream ส่ง CommandComplete(COMMIT)
  proxy ปิด TCP โดยไม่ส่ง acknowledgement ให้ worker จริง; production database error handling
  รับ connection loss แล้ว scan/replay ไม่สร้าง execution link/ledger/fill เพิ่ม
  ไม่มีการส่ง traffic ไป venue หรือเปิด TLS exception ใน production
- proxy case รอบแรกพบ assertion เดิมตรวจ deferred ของทุก owner ใน shared scan
  จึงเปลี่ยน assertion ให้ตรวจ idle command เป้าหมายว่า PENDING และไม่เข้า failure backoff
  หลังแก้ scenario accept/restart/fault ทั้ง **7 cases passed** รวม TCP disconnect จริง
- W3 harness เพิ่มการคง feed/workers/resource sampler จนครบ 4 ชั่วโมง พร้อม minimum-duration
  assertion; cycle count ตาม fixture เดิมอย่างเดียวไม่รับรองระยะเวลา จึงยังไม่ใช้ smoke ปิด W3
- เริ่ม readiness smoke ที่ขนาด 100 episodes × 20 baseline orders ก่อนเริ่ม W1–W3
  ใช้ DB ใหม่ `tiewtrade_f15_release_review` ใน PostgreSQL container เดิม
  ผลและสถานะดู `m6-release-readiness-20261020/`; ยังไม่ถือเป็น release acceptance

## Closure pass — restore and recovery harness — 2026-10-20

- Real concurrent BUY/SELL reservation tests ผ่าน **2 cases**; SELL seed holdings จาก
  MARKET BUY จริงแล้วแข่ง LIMIT SELL สองใบที่รวมเกิน base ที่ถือ ป้องกันใช้ base ซ้ำ
- W4 ผ่านใน `m6-w4-final-20261020/result.json`: backup/restore DB แยก,
  canonical digest และ RLS/grants ตรง; fixture มี capital 4, fills 3, partial 1,
  cancel 1, correction 1, reset 1 และ evidence 20; replay position 2 รายการจาก effective
  executions ด้วย core พร้อมเทียบ cash effects กับ ledger; expired claim 1 กู้จนเหลือ 0
  โดย economic snapshot ไม่เปลี่ยน ไม่ใช้ผลนี้แทน W1–W3
- Recovery smoke `m6-w3-closure-smoke-20261020-v3/result.json` ผ่าน 15 commands,
  6 fills, 3 cancels, 3 replays; worker restart/connection churn/Redis outage RECOVERED,
  duplicate effects/invalid reservations/invalid positions/input lag เป็นศูนย์
  ใช้ 1 owner × 1 baseline เท่านั้น ไม่รับรอง capacity หรือ endurance
- แก้ harness ให้วัด runtime PID ของ Python บน Windows แทน venv launcher และเก็บ
  transaction samples ลงดิสก์ระหว่างรัน โดยวัดจน commit context จบจริง
  v2 ล้มจากอ่าน PID file ขณะยังว่าง; เปลี่ยนเป็น atomic rename และ cleanup startup failure
  แล้ว v3 ผ่าน; เก็บ failure เดิมไว้ ไม่ลบหลักฐาน
- Ruff check/format และ mypy **449 source files** ผ่านหลัง PID fix;
  production code ไม่เปลี่ยนจาก dispatch fairness checkpoint

## Closure pass — contended claim regression — 2026-10-20

- readiness `m6-release-readiness-20261020` ล้มระหว่าง baseline wave 18:
  1800 admitted commands, 1780 successful admissions; claim UPDATE พบ PostgreSQL
  statement timeout สองครั้ง และ setup รอ command จน timeout
  ไม่มี measured workload จึงไม่ใช้เป็น W1 result; มี targeted tests บน DB อื่นใน container
  เดียวกันช่วงท้าย setup จึงไม่อ้างรอบนี้เป็น isolated performance evidence
- เพิ่ม regression สอง connections: เก็บ claim แรก uncommitted แล้วให้ worker ที่สอง
  ใช้ stale scan candidate เดิม ผลก่อนแก้ timeout; แก้ `claim_order` ให้เลือก row
  ด้วย `FOR UPDATE SKIP LOCKED` ก่อน atomic UPDATE ตาม pattern
  `infra/market_data/claims.py` ไม่เปลี่ยน lease/fencing/owner scope หรือ trading semantics
- เพิ่ม fault injection หลัง input registry, fill/checkpoint events, projection/reservation
  revision updates, order activity, wallet revision และ finish claim อีก **8 cases passed**;
  ทุกกรณี rollback เงิน/order/evidence แล้ว retry command/input เดิมได้
- หลัง claim fix รัน `test_dispatch.py`, `test_worker.py`, `test_process_recovery.py`
  รวมผ่านทั้งหมด; Ruff format/check และ mypy **449 source files** ผ่าน
- ใช้ fixture เดิมทำ diagnostic resume ใน `m6-readiness-resume-20261020-v2`:
  อ่าน owner IDs ด้วย scanner role แล้วใช้ original run ID/idempotency keys seed baseline
  ที่ยังขาด ไม่สร้าง owners/ทุนซ้ำ; รอบ v1 ล้มก่อนเริ่ม workers เพราะ migrator อยู่ใต้ FORCE RLS
  จึงอ่าน owner IDs ไม่ได้ เก็บ failure ไว้; resume ไม่ใช่ clean release acceptance

## Closure pass — ETH pipeline and workload harness alignment — 2026-10-20

- ขยาย synthetic order-book fixtures เดิมด้วย optional symbol (default BTC เดิม)
  และ parameterize real feed/PG → matching → F-14 calculation → disconnect เป็น BTC/ETH
  `test_pipeline.py` ผ่าน **3 cases** รวม bootstrap overflow; ไม่ถือว่าเป็น ETH capacity test
- Windows resume ล้มใน measured cycle จาก command timeout; แยกไว้ใน
  `m6-readiness-resume-20261020-v2/failure.json` ไม่ลด load หรือเพิ่ม timeout ให้ผ่าน
- เพิ่ม Linux `/proc` RSS/CPU sampling เพื่อใช้ network แบบ Docker bridge เดียวกับ CI
  และลดการสรุป peak RSS จาก quadratic scan เป็นหนึ่งรอบผ่าน samples
- พบ harness ไม่พัก 20ms หลัง worker round แบบ production entrypoint และ poll result ทุก 10ms:
  แก้ worker ให้พักตาม `services/engine/paper_order_main.py`, poll เฉพาะการอ่านผลทุก 50ms
  คง command/book rates, expected economic effects และ acceptance thresholds เดิม
  ลบ in-process worker helper ที่ไม่มี caller เพื่อไม่เหลือ loop สองชุด
- หยุด Linux setup รอบแรกหลัง wave 16 เพราะ harness mismatch (มี `stopped.json`);
  `m6-linux-readiness-20261020-v2` ใช้ DB/run ID/idempotency keys เดิมเพื่อ diagnostic ต่อ
  มี hardware/provenance hashes แยก ไม่อ้างเป็น clean release acceptance
- เพิ่ม timeout ต่อ positive cycle 60s ตาม validation; W3 pause เฉพาะ cycle ใหม่
  ไม่ drain active cycles ก่อน fault และบันทึก active-cycle count ตอน fault
  recovery smoke เดิมไม่รับรอง semantics ของ harness รุ่นใหม่นี้ ต้องตรวจซ้ำก่อน W3 เต็ม
- Ruff check/format และ mypy **449 source files** ผ่านหลังแก้ harness/fixtures

## Closure pass — verified reusable baseline and active-cycle recovery — 2026-10-20

- Linux diagnostic `m6-linux-readiness-20261020-v2` ยัง timeout ที่ positive-cycle bound
  ไม่ใช้ผลนี้ปิด workload; มี `checkpoint-profile.txt` และ `worker-profile.txt`
  จาก cProfile แยกหลังหยุด workload แล้ว แสดงต้นทุน checkpoint reconstruction/verification,
  persistence และ input processing; ไม่อ้างเวลาของ profiled run เป็น latency acceptance
- เพิ่ม `BASELINE` phase เตรียมและ verify เงิน/position/reservation/order counts โดยไม่มี
  measured cycles; export owner/episode IDs สำหรับ DB clone แล้ว `--baseline-manifest`
  ตรวจจำนวน/ความไม่ซ้ำของ owners, profile และ economics ก่อนใช้ซ้ำ
  ผล PREPARED ไม่ใช่ผล acceptance และไม่เปลี่ยน positive oracle หรือ workload thresholds
- เตรียม baseline smoke 1 owner × 1 order แล้ว clone เป็น DB แยก:
  `m6-w3-closure-smoke-20261020-v4` ผ่านครบ 15 commands/6 fills/3 cancels/3 replays
  worker restart และ connection churn มี active cycle 1 ตอน fault; recovery ไม่ลงผลเงินซ้ำ
  drain 0.25s, p95 0.063s, p99 0.110s, reservation/position/input-lag/duplicate violations=0
- ใช้ lock เฉพาะ harness ประสาน resource PID sampling กับ worker restart เพื่อไม่อ่าน
  process ที่กำลังถูกแทนที่; ไม่ครอบ financial transactions หรือเปลี่ยน production locks
- เริ่ม baseline 100 owners × 20 orders ใน `m6-baseline-final-20261020`
  บน DB ใหม่ `tiewtrade_f15_baseline_final`, Linux bridge network และ 20 workers
  ไม่รัน full backend regression หรือ measured workload อื่นซ้อน

## Approved revision amendment — NC-F15-10 — 2026-10-20

`matching_storage.persist_checkpoint` อัปเดต revision ของ projection/reservation **ทุก row
ใน episode รวม terminal history** ทุกครั้งที่ใช้ market input; F-13 snapshot function
ใน migration 0037 ตรวจ revision ของทุก row เท่ากับ order activity
ดังนั้นงานเขียนต่อ input เพิ่มตามประวัติสะสม แม้ active baseline คง 20 orders
ยังไม่ได้รัน W3 เต็มเพื่อวัดผลปลาย 4 ชั่วโมง จึงไม่อ้างว่าพิสูจน์ failure ของ W3 แล้ว

เสนอให้อนุมัติขอบเขตต่อไปนี้ก่อนแก้ implementation:

1. Bulk revision update เฉพาะ active rows; rows ของ transition ปัจจุบันยัง upsert ทั้งชุด
   รวม order ที่เพิ่ง terminal และ release reservation ใน transaction เดียวกัน
2. Terminal history เดิมเก็บ revision ตอนจบไว้; reservation ต้องเป็นศูนย์,
   revision ต้องไม่เกิน current activity และ provenance/event linkage ต้องยังตรวจได้
3. เพิ่ม migration สำหรับ F-13 coherence function โดยไม่แก้ migration ที่ใช้แล้ว;
   active revision mismatch, incomplete source, corrupt provenance, terminal nonzero reserve
   และ conflicts ยังคงทำให้ reset unavailable ไม่เปลี่ยน business reset policy
4. เพิ่ม real PG tests: หลายคู่พร้อม terminal history ไม่ถูก rewrite, current transition
   revision ตรง, corruption ของ active/terminal ยัง fail closed, correction/replay/reset
   และ rollback/race paths เดิมผ่าน; ตรวจ query/write counts ไม่โตตาม terminal history
5. คง matching/fee/quantity/cash/position semantics และ W1–W4 thresholds ทั้งหมด
   แล้วตรวจ affected safety/candidate gates ก่อนรับรอง performance ของ revision ใหม่

เจ้าของอนุมัติ NC-F15-10 ผ่านคำตอบใน session วันที่ 2026-10-20; บันทึก amendment ใน requirements/plan/validation และปิด clarification ก่อนเริ่มแก้โค้ด.

## NC-F15-10 implementation and safety checkpoint — 2026-10-20

- Owner-approved amendment recorded before implementation. Active projection/reservation revisions advance; old terminal rows keep their terminal revision. New migration 0038 changes only readiness predicates, preserves SECURITY DEFINER/owner/RLS/ACL and rejects downgrade when historical revisions cannot satisfy 0037.
- Real PostgreSQL checks pass: old terminal xmin/revisions unchanged across same/different pair transitions; active/new-terminal revisions remain coherent; terminal future/mismatched revisions and nonzero reserves fail closed; active revision mismatch fails closed; all closed orders with completed dispatch report reset ready.
- Empty database upgrade → downgrade 0037 → upgrade head passed. Populated downgrade guard and FORCE RLS rollback checked.
- Regression directories execution_market, paper_wallet, positions passed on fresh DB `tiewtrade_f15_nc10_safety`; final seven changed storage/migration checks passed again after adding active-corruption/FORCE-RLS assertions. Ruff check/format (492 files) and mypy (449 files) passed.
- Initial regression attempt used old diagnostic DB and failed: direct storage fixture left commands pending without admission receipts, poisoning later global worker scans. Fixed fixture with existing complete_command/claim_order/finish_claim; interrupted attempt is not counted as passed. Clean rerun above passed.
- Reusable baseline `m6-baseline-final-20261020` prepared and verified 100 owners × 20 orders on schema 0037, no measured cycles; source DB kept pristine. Cloned to `tiewtrade_f15_nc10_readiness`, migrated clone to 0038, and started isolated 100-owner readiness smoke with 20 Linux workers. No parallel test/diagnostic workload during this measurement.
- W1–W3, final candidate full gates and current-schema W4 remain Pending Full Validation; no Completed claim.

### NC-F15-10 readiness result — Failed / next checkpoint

- `m6-nc10-readiness-20261020`: isolated Linux 20-worker smoke on the migrated 100-owner × 20-order baseline hit the required 60s positive-cycle bound. Preserve failure.json and worker samples; do not start long W1–W3 runs on this candidate.
- 7,035 processing transactions recorded: p50 0.111225s, p95 0.173324s, p99 0.220413s. These samples do not establish workload acceptance because positive cycles did not finish.
- Post-stop read-only inspection: dispatch PENDING=2,173 / TERMINAL=39; projections FILLED=76 / ACCEPTED=2,038; 36 CANCEL commands all attempts=0. This identifies dispatch progress/backlog as the next investigation; it does not by itself prove a particular scheduling fix.
- Baseline source remains pristine; measured clone contains partial cycles and must not be reused as a pristine fixture. All worker/diagnostic containers stopped; only PostgreSQL/Redis remain.
- Final strengthened active-corruption assertion sets projection and reservation to the same stale revision, proving the activity comparison itself rejects it. Six storage cases passed after this assertion change; lint/format/type checks passed. No production changes after the failed smoke.
- NC-F15-10 implementation/safety checkpoint complete. F-15 remains In Progress / Pending Full Validation; final-candidate W4 on schema 0038 and full gates remain outstanding.

## Dispatch progress remediation — 2026-10-20

- Reproduced stale-scan reclaim in a real PostgreSQL regression before changing production: after another worker finished/rescheduled a command, a delayed scanner batch could claim its next round. DueOrder now carries the already-permitted next_attempt_at metadata and claim_order compares it atomically. Expired-lease recovery and SKIP LOCKED remain intact; no new priority lane or grants.
- Isolated smoke `m6-dispatch-fence-20261020` still Failed: 113 offered/13 completed, no completed cycles, publisher 169 inputs; parent load generator consumed about 47 CPU seconds over 57 wall seconds. Preserve this failure.
- Reduced observer polling from 50ms to 250ms without changing command rates, positive oracle or 60s progress bound. `m6-dispatch-observer-20261020` still Failed: 252 offered, 152 completed, 76 fills, 37 replays, 2 cancels, zero completed cycles; publisher 462 inputs. No acceptance claim. Failure artifacts now retain counters/resources; sibling cycle tasks are canceled and awaited before database disposal to prevent post-failure fixture writes.
- Reuse the already persisted matching state to reschedule redundant admitted NEW jobs covered by the same pair transition. Only PENDING jobs with successful admission receipts and explicitly processed order IDs qualify; terminal orders close dispatch, active orders get the existing 200ms next round. New admissions/CANCEL commands, other pairs and CLAIMED jobs remain untouched. Financial writer/claim checks, order matching, timing eligibility and queue fairness remain unchanged; this is completion of already processed pair work, not postponement on new arrivals (NC-F15-09).
- Added coverage for protected schedules, live claim tokens, terminal cleanup, active rescheduling and transaction rollback. Added post-pair-dispatch write fault to existing financial rollback/retry matrix.
- Reused safety DB exposed an unrelated stale wallet-dispatch fixture (global deferred count 2 instead of 1); preserve failed result, do not modify wallet behavior/tests to hide it. Final affected suite runs on fresh DB `tiewtrade_f15_dispatch_safety`, with JUnit artifact.

### Dispatch checkpoint results

- Final affected safety suite: **118 passed, 0 failed, 0 skipped**, 61.668s on fresh `tiewtrade_f15_dispatch_safety`; JUnit `m6-dispatch-safety-20261020.xml`. Ruff check/format (492 files), mypy (449 files), diff whitespace checks passed.
- `m6-pair-dispatch-20261020` completed **500/500 commands, 100 cycles, 200 fills, 100 cancels, 100 replays**, zero rejected commands. It then Failed input drain because the harness stopped the market feed before waiting for the final watermark; retained the Failed result.
- Post-stop read-only financial verification of that database: **100/100 owners passed** exact cash/reserve/holding/cost expectations; 2,300 orders, 200 linked fills, 100 cancels, 2,000 baseline pending jobs; duplicate fills, invalid reservations/positions, unlinked fills and wrong mode all zero. Evidence `post_failure_economics.json` is explicitly not acceptance.
- Harness now keeps dependencies alive while draining a fixed measured watermark and captures measured input count before drain, so drain inputs cannot inflate the workload-rate result.
- Reconfirmation `m6-pair-dispatch-final-20261020` **Failed** earlier: 100 admitted/0 completed, publisher only 24 inputs, max publish duration 13.55s, three wallet advisory-lock statement timeouts. Root cause of this inconsistent publisher/progress result is **not yet established**; do not label it infrastructure-only or claim capacity passed. Both runs have source hashes; no concurrent validation/diagnostic container during measurements.
- Production dispatch changes and targeted safety checkpoint are complete, but workload stability remains unresolved. Do not start W1–W3 long runs or mark F-15 Completed. Next investigation: publisher lifecycle/long publish interval and concurrent worker progress, preserving all timing/safety thresholds. No commit/push performed.

## Publisher / worker concurrency inspection — 2026-10-20

Scope: inspection and bounded diagnostic only; no production or workload-harness source edits in this inspection. Diagnostic script/artifacts: `m6-concurrency-diagnostic-20261020/`. Fresh clone `tiewtrade_f15_concurrency_diag`, migrated 0038, 100 owners × 20 baseline orders, 20 workers; deliberately stop after 40 seconds, **not acceptance**. Startup attempt initially failed import resolution before any workload and was corrected in the diagnostic script.

Findings:

1. `profile_workload.py:1307,1426,1552,1578`: publisher task runs independently of cycle supervision. If it fails after startup, run_scheduled_cycles can wait until its 60s bound; failure.json captures the cycle exception, and finally's gather(return_exceptions=True) discards the publisher result. This hides the initiating error. Recommend supervise publisher and cycle tasks together, preserve publisher exception type/stage and progress timestamp, and distinguish intentional cleanup cancellation. Do not alter feed freshness/lease thresholds.
2. `dispatch.py:223,243` / `paper_order.py:32` / `worker.py:132`: one candidate per owner is enforced per scan batch, not across workers. Different pending commands of an owner can be leased concurrently; wallet lock then serializes them while other workers hold leases/connections. PostgreSQL snapshots confirm waiting advisory-lock chains, up to four blockers. Recommend an atomic per-owner in-flight claim check under the existing owner lock (nonblocking), with scanner busy-owner exclusion only as a hint; preserve expired-lease recovery and validate same-owner races, other-owner progress, reset and rollback before rollout. This is a recommendation, not implemented here.

Diagnostic observations: 369 published inputs, max publish 0.440594s, max event-loop lag 0.169325s; eight market-data SQL calls exceeded 100ms, maximum 0.209340s. No publisher error before the intentional cancellation at 40s. In 22 PG snapshots, 12 contained advisory-lock waiters (53 sampled waiter rows, not 53 distinct events); maximum sampled wait age 0.237585s. No sampled publisher lock blocker. Cancellation cleanup warnings occurred at the deliberate diagnostic timeout; not evidence of a preceding publisher failure.

The prior 13.55s publication stall was **not reproduced**, so CPU saturation, WAL/storage stalls, event-loop delays and publisher lease loss remain unproven explanations for that specific run. No claim that the financial wallet lock directly blocks publisher rows. Keep F-15 Pending Full Validation; all diagnostic processes stopped, only PostgreSQL/Redis remain.


## Publisher supervision and owner claim completion — 2026-10-20

- Closed both findings from the preceding inspection. The harness supervises publisher startup, baseline, cycles, fault completion and recovery; producer failures preserve the original exception and record stage/progress/failure timestamps. Intentional cancellation remains cleanup.
- Claims acquire the existing owner wallet advisory lock nonblockingly and atomically reject another unexpired owner claim. Scanner excludes busy owners using a materialized busy-owner set; this is a hint, while the transaction enforces safety. Expired leases remain recoverable. Matching, financial rules and workload thresholds are unchanged.
- Fresh PostgreSQL affected order/wallet safety: **125 passed**, JUnit `m6-supervision-safety-20261020.xml`. After scanner query optimization, dispatch and supervision tests: **12 passed**. Ruff check/format (493 files), mypy (450 source files) and diff whitespace checks passed.
- Full-size nominal **SMOKE PASSED**, `m6-supervised-smoke-20261020`: 100 owners × 20 baseline orders, 20 workers; 500/500 commands, 100 cycles, 200 fills, 100 cancels, 100 replays, zero rejections. Drain 1.874s; transaction p95 0.186s / p99 0.230s. All owner financial oracles and global invariants passed; no duplicate fills, invalid reservations/positions, worker failures or sampled lock waits.
- **W3_SMOKE PASSED**, `m6-supervised-recovery-20261020`: 15/15 commands, 3 cycles, worker restart/connection churn/Redis outage recovered, no duplicate financial effects; drain 0.055s, transaction p95 0.041s / p99 0.069s. Worker restart overlapped one active cycle; churn/outage did not overlap an active cycle in this run, so this does not prove every fault interleaving.
- Both smoke artifacts include source hashes. Runs were serial with no concurrent diagnostics or validation runners. At completion only the PostgreSQL and Redis service containers remain, Redis unpaused.
- These results supersede the unresolved implementation-findings checkpoint, not the retained Failed workload evidence. The earlier 13.55s publication stall was not reproduced and its specific root cause is not established. **Pending Full Validation** remains for W1–W3, current-schema W4, final candidate gates and CI; smoke is not release acceptance. No commit/push/merge performed.


## Owner-directed deferral of long validation — 2026-10-20

W1 release run `m6-release-w1-20261020` was started, then interrupted at the owner request to avoid long validation. The dedicated runner container was stopped; PostgreSQL/Redis and partial evidence/database were retained. No acceptance result is claimed. W1-W3 and final-schema W4 remain Pending Full Validation at the release checkpoint. Existing passing affected safety and smoke evidence remains valid; no production code changed during this attempt. Do not automatically restart long validation under the earlier completion instruction.

## Final development candidate — 2026-10-20

Commit `47281ad7d10f64be207dc75a04d2b87fcc1d6181` carries the final runtime changes and a bounded frontend readiness retry after CI exposed the same startup race twice; docs-only candidate head was `9a3b6c878074c41f79ba93a5dffe80db4e7ac963`. Required CI run #124 attempt 2 passed backend full regression, static/import gates, frontend lint/types/unit, OpenAPI generation, browser E2E and containers; run #125 passed all six jobs again after merge commit `dcaffe10b99360c7344b90283effa54fbd82bddd`. V-1..V-18 are reconciled as Passed for Development Complete. W1–W3 and W4 on schema 0038 remain Pending Full Validation and prevent Completed status.


## Deep-review remediation — 2026-10-25

Scope: owner requested fixes for the two High and one Medium findings from the F-15
implementation review. Base `96bae0e`; uncommitted branch `fix/f15-review-findings` in
`../TiewTrade-f15-review`. The original `fix/f13-review-findings` working tree is preserved.
The approved requirements/plan/validation remain the implementation contract; no new
matching, fee, quantity-sizing or admission policy is introduced.

- Correction queue rebase now records its consumed input boundary and both capability
  variants in the durable checkpoint. A current book ahead of the old cursor skips older
  backlog; a current book preceding an already-consumed trade retains the newer cursor.
  Existing queue/consumption rules, F-14 compensation and financial locks are reused.
- Matching receives MARKET and LIMIT capabilities separately, preserves both for replay,
  selects the order-specific quantity step/capability, and uses existing
  `trading_limits.unmet_constraints` to reject cumulative maximum quantity/notional
  violations before financial persistence. Partial executions retain their approved
  minimum/step semantics. A failed execution transaction retains reservations and can
  be canceled through the existing path; it does not silently resize or invent a fill.
- MARKET remainder expiry appends an `EXPIRED` event with
  `MARKET_REMAINDER_UNMATCHED`, final cumulative amounts and source evidence in the
  same transaction as fills/reservation release. Immutable checkpoint terminal snapshots
  support historical reads and corrections without trusting a modified projection.
  Legacy checkpoint reads remain supported; old history is not rewritten.
- Regression coverage includes serialize/reload after rebase, historical trade rejection,
  newer valid trade, price movement and cumulative multi-level maximum quantity,
  distinct MARKET steps/unavailable capability/replay mismatch, real-DB active correction
  and cash invariants, constraint rollback/cancel, expiry reason and terminal history
  despite projection corruption. Existing codec/order serialization and event schema are
  reused; no migration, route, grant, credential or Live activation change.

Validation environment: Python 3.12.15, PostgreSQL 16.15 in dedicated container
`tiewtrade-f15-review-pg`, database `tiewtrade`, Docker-assigned loopback port 59318;
bootstrap scripts and migrations through head, actual MIGRATOR/API/ENGINE/ENGINE_SCAN/
MARKET_DATA roles using the repository's development credentials. Runner
`/tmp/tiewtrade-f15-review-run.py` sets the corresponding role URLs and PYTHONPATH to
this worktree, then executes the backend venv Python. No Binance requests or Live orders.

Initial core/new integration subset: 50 passed. Affected safety suite: 246 passed,
0 failed/skipped in 97.962s (`/tmp/tiewtrade-f15-review-safety.xml`). Full-backend static
checks passed: Ruff check/format (522 files), mypy (477 source files), and all seven
import contracts. `Ready for Code Review` was reported before final diff review.
Review also added the existing matching-index predicate to the terminal-history query.

Retained unsuccessful validation attempts (not acceptance): the first container port
was occupied and a later invocation had no published port; those DB results were not
used as evidence. The first correction fixture consumed its entire order because its
visible queue was smaller than intended; the fixture now pins external queue=10.
An expanded follow-up initially lacked the worktree-local venv console-script path and
ran after a legacy migration test had left schema 0038; the harness now links the venv
and migrates a fresh database. Two follow-up invocations were accidentally concurrent,
causing WriterLeaseLost/claim failures; neither run is acceptance. Their JUnit files
remain `/tmp/tiewtrade-f15-review-followup.xml`,
`/tmp/tiewtrade-f15-review-followup-final.xml` and
`/tmp/tiewtrade-f15-review-final-regressions.xml`. Final confirmation runs serially on a
new database, with all affected suites and gates in one invocation.

Final serial safety result: **302 passed, 0 failed/errors/skipped** in
90.517s on the final runtime/test source, JUnit
`/tmp/tiewtrade-f15-review-final-safety.xml`. Command (through the runner):

```text
python -m pytest -p no:cacheprovider tests/infra/execution_market tests/infra/positions
  tests/infra/paper_wallet tests/core/test_paper_matching.py tests/core/test_positions.py
  tests/core/test_position_parity.py tests/core/test_paper_wallet.py tests/gates
  tests/services/market_data/test_order_book.py tests/venues/binance_th/test_order_books.py
  -q --tb=short --junitxml=/tmp/tiewtrade-f15-review-final-safety.xml
```

The command above is one invocation (line-wrapped for readability). Final source SHA-256
(sorted seven changed runtime/test paths, each path + NUL + file bytes + NUL):
`53c0bdc7e3efeb3bd7f98b4531fbeaf8d5bd21f17986e1a4ac666702113cca3c`.
Final diff/dependency review found no remaining Critical/High finding within this
remediation. Ruff check/format and diff whitespace checks passed again after the final
query predicate/reason change; full mypy/import results remain valid (no type/import
change since those checks). V-3/V-4/V-5/V-8/V-10/V-12/V-15 have affected safety evidence.

Full backend regression and
required CI on a final commit remain Pending Candidate Validation; no commit/push/merge
has been requested. V-19 remains Pending Full Validation under the approved release
checkpoint; no timed workload smoke is used as a substitute. Reading/editing/review time
was not separately measured; test durations come from JUnit.


## Full backend candidate continuation — 2026-10-25

Owner requested the next candidate step after the local 302-test safety checkpoint.
Same branch/base and approved F-15 scope. Runtime source remains unchanged; the only
additional code change is stabilization of the existing process-kill recovery test.

Environment: dedicated PostgreSQL 16.15 container `tiewtrade-f15-review-pg` and dedicated
Redis 7 container `tiewtrade-f15-review-redis`; ports are obtained with `docker port` at
invocation time (container restart reassigns the random loopback bindings). Fresh DBs
`tiewtrade_f15_candidate_20261025` and `tiewtrade_f15_candidate_20261025_r2` preserve the
first-attempt state separately. Bootstrap and Alembic through head use actual role URLs;
API/signup/cookie/origin/Redis settings match CI using development-only values.
`/tmp/tiewtrade-f15-candidate-run.py` runs backend commands with the worktree PYTHONPATH
and records output in `/tmp/tiewtrade-f15-candidate-full-20261025.log`. Only one test
invocation uses these dependencies at a time. No Binance/Live order validation.

- Full attempt 1: `python -m pytest -p no:cacheprovider -x --tb=short
  --junitxml=/tmp/tiewtrade-f15-candidate-full-20261025.xml` stopped with **1300 passed,
  1 failed, 2 deselected** in **548.72s**. Retained JUnit copy:
  `/tmp/tiewtrade-f15-candidate-full-20261025-attempt1.xml`.
- Failure: process recovery `test_worker_kill_recovers_without_duplicate_economic_effects`
  at `before_commit`. Read-only diagnosis found ACCEPTED/filled=0/spent=0, balance=10000,
  quote reservation=100, and dispatch attempts=3 with next retry at +30s. The first
  recovery book was received at 05:55:24.765316 UTC; deferral occurred by
  05:55:26.103695 UTC. Global scanning processed unrelated owners before the target,
  exhausting the approved 1s freshness window. The following two 30ms retry loops could
  not reach the real 30s retry schedule. This is preserved as a failed acceptance attempt;
  the safe absence of a fill is not labeled a passed recovery criterion.
- The kill test now admits/reclaims its target using actual `DueOrder`/`claim_order` and
  session-bound `process_claimed_order`, with claim committed separately. It publishes
  fresh input after the recovery claim barrier. Real child process kill before/after
  commit, lease-expiry simulation, immutable command replay and exact money/position/
  reservation/history assertions remain. Scanner/fairness coverage stays in dispatch/
  worker tests. No production timing, freshness, retry or matching rule was changed.
- Process recovery + dispatch regression: **12 passed** in **5.696s** on the first-attempt
  database, JUnit `/tmp/tiewtrade-f15-candidate-recovery-20261025.xml`. Ruff check/format
  for the changed test and full mypy (**477 source files**) passed. A tests-only mypy
  invocation initially resolved source imports as installed/untyped; full configured
  mypy resolved the source tree correctly and passed. Diff whitespace check passed.
- `Ready for Code Review` was reported for the test stabilization. Diff review confirms
  real role/claim/transaction/kill barriers and exact safety assertions remain; no
  production bypass or weakened criterion. Existing runtime static/import evidence is
  still valid because runtime code/dependencies have not changed.
- Full attempt 2 was started serially on the new `_r2` database with the same full pytest
  invocation and JUnit `/tmp/tiewtrade-f15-candidate-full-20261025-attempt2.xml`; its retained
  result and complete-suite continuation are recorded below.

The checkpoint above was pending until the full run finished; final local results follow.
Required CI still needs
an owner-directed commit/push; V-19 remains at the approved release checkpoint. No Git
commit/push/merge operation is authorized by this validation continuation.


### Full attempt 2 and complete-suite confirmation

Full attempt 2 stopped at the unrelated prepared-indicator test
`tests/api/test_prepared_indicators.py::test_empty_derived_scheduler_refresh_and_rebuild`:
**228 passed, 1 failed, 2 deselected** in **310.79s**. The refresh consumer returned
STOPPED rather than READY after one candle-status poll. This same test passed in full
attempt 1 and passed unchanged when re-run alone on the `_r2` database; JUnit
`/tmp/tiewtrade-f15-candidate-indicator-recheck-20261025.xml`. The exact cause of this
intermittent failure is not established; no F-11 source/test or timeout was changed,
and the failed full run is retained rather than relabeled Passed.

Full attempt 3 runs on fresh `tiewtrade_f15_candidate_20261025_r3`, without fail-fast so
that every collected backend test has a result. Command:
`python -m pytest -p no:cacheprovider --tb=short
--junitxml=/tmp/tiewtrade-f15-candidate-full-20261025-attempt3.xml`.
Final runtime/test SHA-256 uses the same path/NUL/bytes/NUL procedure above over eight
changed runtime/test paths, now including `test_process_recovery.py`:
`f8a69ddb42b06c743c3152e33ffa00a9ce04fec940f4e193ce9ce832ed1a80b9`.
Result: **Passed — 3267 passed, 0 failed/errors/skipped, 2 venue-contract tests deselected**
in **795.874s (13m15s)**. Five deprecation warnings came from existing Starlette/TestClient
usage. No runtime/test edits during the run; the eight-file fingerprint above was
rechecked after completion and matches. Both earlier full-run failures remain retained;
the prepared-indicator test passed in this complete run and its earlier intermittent
failure's exact cause remains unresolved.

Local backend candidate regression is now passed. The current test stabilization has
Ruff/format and full mypy evidence; all other static/import results remain valid on the
unchanged runtime/dependencies. Final scoped diff review found no new Critical/High
finding. Required CI on the eventual final commit is still pending, and V-19 remains
Pending Full Validation. No commit/push/merge and no production activation occurred.
The temporary worktree venv link is removed; only this task's dedicated PostgreSQL/Redis
containers are stopped after validation, retaining their databases for inspection.


## Owner-directed commit / PR / CI handoff — 2026-10-25

After the passing local full backend checkpoint, the owner instructed continuation of
the proposed commit/push and required-CI step. The runtime/test fingerprint still matches
`f8a69ddb42b06c743c3152e33ffa00a9ce04fec940f4e193ce9ce832ed1a80b9`.
Remote main advanced to `f6bd712` (F-13 review remediation, PR #31); its five changed files
do not overlap this F-15 branch. The PR CI merge candidate will verify their integration;
the existing local full result remains evidence for the F-15 branch source.

This handoff authorizes commit/push, opening the scoped F-15 PR and checking required CI.
Required CI is pending until the pushed candidate finishes. Merge has not been requested;
V-19 and production activation remain subject to their approved checkpoints.


## Required CI and main synchronization — 2026-10-25

Runtime/test commit `f2240a46e9140e5872e667dd42d90ab9e62133c4` was pushed and
[PR #33](https://github.com/yukasung/tiewtrade/pull/33) opened against main `f6bd712`.
Both CI runs passed all six jobs without reruns:

- [Push CI 40169303759](https://github.com/yukasung/tiewtrade/actions/runs/40169303759):
  backend **3267 passed, 2 deselected** in **737.31s**, plus config, API contract,
  frontend, container and browser E2E jobs.
- [PR CI 40169323746](https://github.com/yukasung/tiewtrade/actions/runs/40169323746):
  backend **3270 passed, 2 deselected** in **746.87s**, plus the same five jobs.
  This includes the main-branch F-13 remediation. Mypy checked 477 files and all seven
  import contracts passed. Earlier local failures remain recorded above.

GitHub then reported the head as BEHIND main. Main was merged into the F-15 feature
branch using the owner's authorized commit/push continuation. Before documentation
updates, `git write-tree` exactly matched the PR merge tree that CI had just tested:
`84ce403365ad4a27b6059a539969736f1dec9a17`. No additional runtime/test changes were
made in the synchronization; the evidence/validation/roadmap updates only record these
results. Required CI for the synchronized head is tracked on PR #33 and must complete
before merging that PR. The feature PR remains open; no merge into main or production
activation is part of this continuation. V-19 remains Pending Full Validation.


## Synchronized-head CI and subsequent F-14 integration — 2026-10-25

Head `1160a4a13d76493696df8161ada47fa9fb46c14a` passed all six push CI jobs
([40170345394](https://github.com/yukasung/tiewtrade/actions/runs/40170345394));
backend **3270 passed, 2 deselected** in **775.98s**. PR CI
[40170347596](https://github.com/yukasung/tiewtrade/actions/runs/40170347596)
passed all six jobs after one backend-only rerun: **3270 passed, 2 deselected**
in **723.61s**. Mypy checked 477 files and all seven import contracts passed.

The PR's first backend attempt had **1 failed, 3269 passed, 2 deselected** in
**728.36s**: `test_account_summary_is_isolated_from_the_previous_owner` failed
inside unchanged `enable_totp`, returning an invalid-code 403 before account
assertions. That helper creates the previous-step TOTP before obtaining CSRF;
crossing the 30s boundary can expire that code. A deterministic core check confirmed
this mechanism, but CI logs do not prove that exact cause. No auth runtime/test
was changed; this failed attempt remains evidence, not relabeled Passed.

During CI, main advanced to `eb8c7d8` via F-14 PR #32. Its position replay fix and
regression tests merge automatically; the only conflict is adjacent F-14/F-15
roadmap rows, resolved by preserving each feature's own row. Main is synchronized
again within the owner-directed commit/push continuation. The final combined
candidate requires fresh required CI on PR #33 because position storage is a
matching dependency. No merge into main or production activation is authorized;
V-19 remains Pending Full Validation.
