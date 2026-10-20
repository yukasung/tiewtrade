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
