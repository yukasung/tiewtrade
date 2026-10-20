# F-15 M3 — Order worker / financial integration checkpoint

วันที่: 2026-10-18; branch `feature/f-15-paper-order-matching`; base HEAD
`2eb3000711353e76d81f32e9c9c08287f6788702`; ยังไม่ commit/push

M3 ตาม plan §8 เสร็จที่ development checkpoint แล้ว หลักฐานนี้ต่อจาก
[M3 progress](m3-progress.md) โดยไม่เขียนทับผลตรวจเดิม และรวม amendment NC-F15-08
ที่เจ้าของอนุมัติระหว่าง implementation

## Implementation ที่ปิดใน checkpoint นี้

- Durable `NEW`/`CANCEL` commands ใช้ canonical fingerprint, owner/mode/episode scope,
  immutable result และ exact replay; submission เรียก proven source initialization ก่อนสร้างคำสั่งแรก
  และไม่ใช้ immutable receipt อ้าง READY เมื่อ live source conflicted
- DB dispatcher เลือกไม่เกินหนึ่งคำสั่งต่อ owner ต่อรอบ, batch สูงสุด 20, claim 30 วินาที,
  DB-clock lease/revision/token fence และ retry 1s/5s/30s/5m; worker tick 20ms และทำงานได้จาก
  PostgreSQL polling เมื่อไม่มี Redis hint
- worker serialize กับ reset ผ่าน wallet lock และปิดคำสั่งของ episode ที่ปิดแล้วเป็น
  `EPISODE_CONFLICT` แบบ terminal โดยไม่สร้าง order/reservation หรือ retry ค้าง
- Matching checkpoint เก็บ queue, shadow liquidity, source cursor, exact constraints/profile และ active
  orders แบบ bounded ใน immutable order event พร้อม digest; restart โหลด checkpoint และตรวจ projection/
  reservation ก่อนใช้ ไม่แปล row หายเป็น empty
- Full fill transaction รวม private input evidence, order event, F-14 RECORD, exact quote-cash ledger,
  order/reservation projection, activity/wallet revisions, typed audit และ claim fence; failure ก่อน commit
  rollback ทั้งชุด และ deterministic identity ป้องกัน duplicate fill ข้าม retry/restart/คู่เทรด
- Admission ตรวจ F-10 latest-price readiness, current public execution source/capability, shared safety policy,
  Money/Quantity constraints, quote/base reserves และ authoritative position ภายใต้ per-wallet lock เดียวกัน;
  production composition ส่ง policy เป็น `None` จึงปฏิเสธคำสั่งใหม่แบบ fail closed จน F-18 พร้อม
- Cancel ไม่พึ่ง market feed, คืนเฉพาะ remaining reservation และตัดสินใต้ lock เดียวกับ fill;
  cancel หลัง FILLED คืน immutable FILLED result โดยไม่เขียน CANCELED fact เท็จ
- Gap/generation recovery ใช้ latest verified public book เป็น consumer rebase, เก็บ source record เดิมและ
  rebase decision แยกกัน; queue/shadow consumption ที่ commit แล้วไม่ถูกสร้างใหม่
- Internal correction ใช้ F-14 REPLACE/VOID และ compensating cash โดยไม่แก้ history เดิม;
  exact replay ไม่มีผลเพิ่ม. ตาม NC-F15-08 terminal order ที่ fill ลดลงปิด remainder เป็น CANCELED
  และไม่ rematch; active LIMIT คำนวณ queue-ahead ใหม่จาก current verified book/older orders พร้อม
  immutable rebase fact. Reservation solvency ถูกพิสูจน์ก่อน commit
- Migration `0036_paper_matching_decisions.py` เพิ่ม checkpoint indexes/shape, technical
  `INPUT_APPLIED`, typed `PAPER_ORDER_DECISION` audit และ populated downgrade refusal;
  Paper worker ไม่มี venue, HTTP, credential หรือ sealing-key dependency และยังไม่มี public order/correction route

## Verification

Environment: Windows Python 3.12.3, PostgreSQL 16 ที่ `127.0.0.1:55435` และ runtime roles จริง

| ตรวจ | ผล |
|---|---|
| affected regression: `tests/infra/execution_market`, `paper_wallet`, `positions`, `audit`, `core`, core purity และ Paper isolation gate | **583 passed** |
| focused worker/dispatch/core reruns | ผ่าน: missing policy, durable replay/conflict, fair scan, expired claim takeover, restart fill, multi-level fill, cancel ก่อน/หลัง fill, concurrent quote reservation, REPLACE/VOID และ replay |
| fresh DB migration 0036: upgrade head → downgrade 0035 → upgrade 0036 → downgrade 0034 → upgrade head | **PASS** |
| Ruff check + format check production/migrations/affected tests | **PASS** |
| mypy `src/tiewtrade` | **195 source files passed** |
| import-linter | **7 contracts kept / 0 broken**, 239 files / 1527 dependencies |
| `git diff --check` | **PASS** |

การทดสอบใช้ fake/read-only market source และไม่ส่ง Live order ไม่มีการเปิด public admission,
ไม่มี commit หรือ push และไม่ลบฐานข้อมูลหลักฐานเดิม

## Coverage ณ M3

- V-10 มี full persisted command→matching→F-14→ledger transaction และ replay evidence แล้ว;
  คง Partial จน fault matrix/candidate ครบ
- V-11 มี real multi-connection claim fencing, concurrent quote reservation, cancel/fill ordering และ
  core base-reservation oracle; คง Partial จน candidate concurrency matrix ครบ
- V-12 มี caller จริงสำหรับ RECORD/REPLACE/VOID, compensating ledger และ exact replay;
  downstream-invalid caller injection ยังต้องเพิ่มก่อน candidate จึงเป็น Partial
- V-13/V-15 มี initialization, restart/rebase, immutable result recovery และ writer/claim fencing;
  reset integration, Redis outage/unknown-commit/failure matrix เต็มยังอยู่ใน M4/M5
- V-16 persisted fake-source→matching→ledger และ transitive isolation gate ผ่านแล้ว
- V-14 ยัง Not Run เพราะเป็น M4 reset/API/UI integration; V-18 ยัง Not Run; V-19 ยัง
  Pending Full Validation ตาม release checkpoint

งานถัดไปตาม approved plan คือ M4 reset/new-episode readiness และ API/UI integration โดยยังคง
production admission ปิดจน shared F-18 policy พร้อม
