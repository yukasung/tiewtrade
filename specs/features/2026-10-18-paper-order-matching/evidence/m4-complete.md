# F-15 M4 — Reset/readiness/API/UI integration checkpoint

วันที่: 2026-10-18; branch `feature/f-15-paper-order-matching`; base HEAD
`2eb3000711353e76d81f32e9c9c08287f6788702`; ยังไม่ commit/push

M4 ตาม plan §8 เสร็จที่ development checkpoint แล้ว หลักฐานนี้ต่อจาก
[M3 complete](m3-complete.md) และยังไม่แทน candidate/release validation ของ M5/M6

## Implementation ที่ปิดใน checkpoint นี้

- `get_wallet` คำนวณ `reset_available/reset_reason` จาก position/order source proof,
  projection/revision, open position/order, reservation และ pending order command ใน coherent snapshot;
  API ได้เฉพาะ owner-scoped readiness function ภายใต้ FORCE RLS และยังอ่าน execution payload
  หรือเขียน financial tables ไม่ได้
- RESET ตรวจ terminal replay ก่อน expected episode, serialize ด้วย financial advisory lock เดิม,
  คืน `EPISODE_CONFLICT`, `ACTIVITY_UNKNOWN` หรือ `RESET_UNSAFE` แบบ typed และไม่ย้ายคำขอ stale
  ไปยัง episode ใหม่
- reset สำเร็จ append closure, episode/capital ledger, pinned execution profile, position/order source
  initialization, pointer revision, terminal result และ `PAPER_WALLET_RESET` audit ใน transaction เดียว;
  history/PnL เดิมไม่ถูกย้ายหรือแก้ และ retry ใช้ deterministic economic identities
- migration `0037_paper_wallet_reset_audit.py` เพิ่ม typed audit shape และ owner-scoped
  security-definer readiness function; downgrade ว่างทำได้ แต่ reset audit history ปฏิเสธก่อนลบ contract
- UI ใช้ reset readiness จาก server, shared modal ที่ปรับจาก TailAdmin template, แสดงเหตุผลแปลภาษา,
  episode/ทุนใหม่, focus trap/Escape/focus restore, pending/double-submit guard, exact idempotency
  key+payload+expected episode retry และ refetch เมื่อ success/conflict
- browser flow เดิมขยายเป็น create → real internal source initialization → cancel confirmation → reset
  ผ่าน API/durable worker/PostgreSQL → reload เห็น episode 2 และทุน exact โดยไม่เรียก Live venue

## Verification

Environment: Windows Python 3.12.3, Node 22, PostgreSQL 16 ที่ `127.0.0.1:55435`,
Redis ที่ `127.0.0.1:56379`, runtime roles จริง และ Chromium Playwright

| ตรวจ | ผล |
|---|---|
| focused reset/API/initialization/worker integration | **58 passed** |
| affected regression: execution market, paper wallet, positions, audit, core, Paper isolation, API transaction | **597 passed, 1 deselected** (`server_log_policy_still_applies` ต้องใช้ PostgreSQL logging config ของ CI; container local คืน `-1`) |
| reset fault injection: closure/episode/position/ledger/pointer/order initialization/result/audit แล้ว retry | **8 passed**; ทุก fault คง episode เดิมและไม่มี partial reset |
| real reset/reset workers, stale episode, pending order, filled/open position, owner isolation และ terminal replay | **PASS** |
| fresh migration 0037: upgrade head → downgrade 0036 → upgrade head; populated reset downgrade refusal | **PASS** |
| frontend wallet component | **8 passed**; exact retry, cancel, conflict/refetch, Escape/focus trap/restore |
| Chromium `e2e/paper-wallet.spec.ts` | **1 passed** (9.1s) |
| frontend typecheck, ESLint และ production build | **PASS** |
| Ruff check/format, mypy | **PASS**; latest Ruff pass covered 482 files, mypy typed 195 source files |
| import-linter (Windows executable พร้อม UTF-8) | **7 contracts kept / 0 broken**, 239 files / 1528 dependencies |
| `git diff --check` | **PASS** |

การรัน gate รวมครั้งแรกพบข้อจำกัด environment เดิมสองรายการ: test harness มองหา
`.venv/bin/lint-imports` บน Windows และ subprocess output ใช้ cp1252; รัน executable Windows จริงพร้อม
UTF-8 แล้วผ่าน 7/7. PostgreSQL local ไม่ได้ตั้ง `log_parameter_max_length=0`; จึงตัดเฉพาะ test
server-log policy ออกจาก affected regression และไม่อ้างว่า gate นี้ผ่านจาก container ดังกล่าว

## Coverage ณ M4

- V-13 มี new-episode source/profile initialization, concurrent initialization, missing source fail-closed
  และ rollback/retry แล้ว; controlled init/fill race กับ corrupt/conflicted source matrix ยังอยู่ M5
- V-14 เปลี่ยนจาก Not Run เป็น Partial: real-source reset success, pending/open activity block,
  owner-scoped API readiness, reset/reset serialization, exact replay และ browser flow ผ่าน;
  controlled admission/fill/GET barriers และ candidate matrix ยังอยู่ M5
- V-15 เพิ่ม reset write/audit rollback matrix; unknown commit, cancellation/timeout/kill และ Redis
  failure matrix เต็มยังคง Partial
- V-17 เพิ่ม migration 0037/grants/RLS/downgrade evidence; manual/candidate checks ยัง Partial
- V-18 ยัง Not Run จน M5 final diff/dependency review, full regression, OpenAPI drift และ required CI
- V-19 ยัง Pending Full Validation สำหรับ M6 release workload/endurance/restore

งานถัดไปตาม approved plan คือ M5 stable candidate, ปิด controlled races/faults ที่เหลือ,
deep review Critical/High, full regression/contracts/OpenAPI/browser และ required CI
