# F-15 M3 — Initialization / financial linkage progress

วันที่: 2026-10-18; branch `feature/f-15-paper-order-matching`; base HEAD
`2eb3000711353e76d81f32e9c9c08287f6788702`; ยังไม่ commit/push
ใช้ approved plan เดิม ต่อจาก [M2](m2-input-storage.md)
**M3 ยังไม่เสร็จ**; หลักฐานนี้ระบุส่วนที่ทำแล้วและรายการค้างเพื่อกลับมาทำต่อ

## Implementation

- `infra/paper_orders/initialization.py`: ใช้ wallet advisory lock/active episode check เดิม
  พิสูจน์ unique capital ledger, empty F-14 baseline, ไม่มี unknown economic/order/evidence
  history ก่อนตั้ง source เป็น READY; missing F-14 activity ไม่ถือเป็น empty baseline
  F-15 activity ที่ยังไม่มีสร้างได้หลังพิสูจน์ baseline แล้วเท่านั้น
- Initialize F-14/profile/order source และ wallet revision/typed audit ใน transaction เดียว
  มี immutable initialization receipt พร้อม canonical baseline/source proof;
  concurrent retry คืน receipt เดิม ไม่เพิ่ม revision/audit และไม่อ้าง current READY จาก receipt
- Migration `0035_paper_writer_fence.py`: receipt FORCE RLS/append-only และ DB protocol fence
  สำหรับ managed episodes บน wallet state/ledger/closures และ F-14 activity/events/projections/
  fees/conflicts. Marker `F15_V1` เป็น transaction-local; ไม่แทน owner RLS หรือ financial lock
  ไม่มีการเรียก initializer หรือเปิด worker อัตโนมัติขณะ migrate
- `infra/paper_orders/executions.py`: session-bound `stage_fill_cash` ผูก immutable FILL/
  exact execution payload กับ full private evidence, initialized position proof และ current
  public source/generation/eligibility. ตรวจ cumulative intent bounds และ received-asset fee
  ก่อนเรียก F-14 session-bound writer
- APPLIED ใช้ returned quote_cash_delta ของ F-14 ลง linkage/ledger/revision ครั้งเดียว;
  REPLAYED ไม่ลงเงินซ้ำและทำได้หลัง feed unavailable; zero cash เก็บ linkage แต่ไม่เขียน
  ledger amount=0. CONFLICTED ไม่เปลี่ยน cash และเปลี่ยน order availability/financial revision
- ย้าย fee primitive เดิมไป `core/orders.standard_execution_fee` ให้ matcher และ financial
  linkage ใช้ร่วมกัน; ไม่เปลี่ยน rounding/profile และไม่คำนวณ cost/PnL ซ้ำ
- เพิ่ม typed `PAPER_ORDER_SOURCE_INITIALIZED` audit ทั้ง Python และ PostgreSQL shape
  โดยห้าม extra fields/null/non-UUID IDs/non-hex proof; เพิ่ม dependencies ใน Paper isolation
  gate ซึ่งยังตรวจ transitive network/credential paths

`stage_fill_cash` เป็นส่วนประกอบภายใน transaction ของ order writer ที่ยังต้องสร้าง
ไม่ได้ complete command หรือ update order/reservation projection ให้เอง; ห้ามอ้างว่าทดแทน
full financial transaction ของ V-10 ได้. Tests บางส่วน stage immutable order/fill ด้วย SQL
fixture เพื่อทดสอบ boundary นี้โดยตรง ไม่ใช่ production admission path

## Verification

Windows Python 3.12.3 / uv dependencies เดิม; isolated PostgreSQL 16 port 55435
DB ใหม่ `tiewtrade_f15_m3_final` bootstrap roles/event trigger แบบเดียวกับ M2
เก็บ DB ก่อนหน้าไว้ ไม่ลบ immutable history เพื่อให้ migration ผ่าน

| ตรวจ | ผล |
|---|---|
| `pytest tests/infra/execution_market tests/infra/paper_wallet tests/infra/positions tests/infra/audit tests/core tests/test_core_purity.py tests/gates/test_paper_isolation.py --tb=short` | **568 passed / 46.85s** ก่อนเพิ่ม audit-shape/receipt tests และ final closure fence/revision patch |
| Final 0035 upgrade → empty downgrade 0034 → upgrade 0035 บน DB ใหม่ | **PASS**; ใช้ programmatic Alembic Config เช่น M2 เพื่อหลีกเลี่ยง Windows locale ini issue |
| `pytest tests/infra/execution_market/test_initialization.py tests/infra/execution_market/test_executions.py tests/infra/paper_wallet/test_migration.py --tb=short` | **19 passed / 6.21s** หลังเพิ่ม closure fence/receipt digest และ audit shape tests |
| Final affected rerun: execution tests + `test_initialization_receipt_is_private_and_append_only_even_for_owner` | **8 passed / 3.22s** หลัง final conflict revision patch/เพิ่ม receipt mutation test |
| Ruff check / format --check changed/new Python (ยกเว้น fixture trees) | **39 files passed/formatted**; final changed production/test files ตรวจซ้ำตามผลกระทบ |
| Scoped mypy พร้อม production sources/tests | **36 source files passed**; final changed files ตรวจซ้ำ |
| `uv run lint-imports` | **7 kept / 0 broken**, 232 files / 1443 dependencies |
| `git diff --check` | ผ่าน |

Cases: concurrent initialization/retry, audit failure rollback ทุก source และ retry,
wrong owner/wallet, preexisting F-14 history rejection, actual old F-14 writer/state/closure
ถูก DB fence ปฏิเสธ (TT015), marker ไม่ข้าม transaction, source audit malformed/null/extra
field rejection (23514), populated downgrade refusal พร้อม FORCE RLS rollback,
private immutable receipt UPDATE/DELETE/TRUNCATE แม้ใช้ migrator ถูกปฏิเสธ (TT001),
concurrent same-fill APPLIED/REPLAYED มี ledger entry เดียว, cash failure rollback
F-14/link/audit, incorrect fee/oversize/payload mismatch rejection, sequence conflict
ไม่เปลี่ยนเงิน, exact BUY net BTC 0.999, SELL cash/quantity และ zero-cash linkage/replay

Zero-cash fixture เป็น financial-boundary/precision test ใช้ small synthetic execution;
ไม่ได้อ้างว่าผ่าน actual venue minimum notional หรือ production admission
ใช้ผลเดิมต่อเมื่อ dependencies ไม่เปลี่ยน; ไม่บวก counts หลายรอบเป็นจำนวน unique tests

Failed attempt: source audit ใช้ `type(uuid) is UUID` จึงไม่รับ asyncpg UUID subclass
ที่ได้จาก DB (3 failed / 3 passed / 1.54s). แก้เป็น isinstance เฉพาะ UUID fields;
targeted rerun 6 passed / 1.52s และ final rounds ด้านบนผ่าน ไม่มีการ ignore type/test failures

## Remaining M3 work — ทำต่อจากรายการนี้

1. Durable NEW/CANCEL admission/result/dispatch, canonical request fingerprint, claim lease/
   revision/expected episode fencing, fair bounded worker rounds/backoff และ runtime composition
2. Hydrate/replay per-pair shadow liquidity/queue/constraints/cursors จาก durable facts;
   financial transaction ต้องรวม input/order/events/F-14/ledger/reservation/revisions/audit/
   terminal result ทั้งชุด ตรวจ independent concurrent buys/sells และ cross-pair quote reserves
3. Fill/cancel ordering ทั้งสองทาง; REPLACE/VOID พร้อม compensating cash และ order/reservation
   rebuild ต้อง conflict เมื่อ downstream liabilities ไม่ปลอดภัย; ยังไม่มี correction writer
4. Crash/timeout/cancellation/unknown commit/Redis loss/restart/rebase recovery ผ่าน worker จริง
   และ source retention lifecycle; initialization/fill races และ completeness checks ทุก boundary
5. M4 reset/new-episode initialization/readiness/API/UI integration คงรอ; old reset success
   ไม่ถูกเปิดด้วย initialization นี้. F-18 production admission policy ยังไม่มี จึงห้ามรับ order

V-10/V-11/V-13/V-15 เป็น **Partial** เฉพาะ boundary ที่มีหลักฐาน;
V-12/V-14/V-18 ยัง Not Run. M3 milestone/full candidate/CI ยังไม่ผ่าน;
V-19 คง Pending Full Validation. Actual unsupported required venue filters ยัง reject ตาม M2
ไม่มี public order/correction endpoint, ไม่มี Live order และไม่มี worker activation

เวลาที่จับจริงคือ test runtimes ด้านบน; เวลาอ่าน/เขียน/รีวิวไม่ได้จับแยก จึงไม่ประมาณขึ้นเอง
Fingerprint ฉบับนี้อยู่ใน `m3-source-manifest.sha256`; M1/M2 manifests เป็นหลักฐานอดีต
ไม่ถูกเขียนทับให้เหมือนเป็นโค้ดรุ่นปัจจุบัน
Manifest มี 44 backend files; SHA-256:
`9df317688de1bd671582ac8ab496fd6b2b691190303f40f11823c98b11ed3fcd`
