# F-15 M1 — Core checkpoint

วันที่: 2026-10-18; environment: Windows/PowerShell, Python 3.12.3, backend uv environment
Branch: `feature/f-15-paper-order-matching`; base HEAD:
`2eb3000711353e76d81f32e9c9c08287f6788702`; implementation ยังไม่ commit
เจ้าของอนุมัติ requirements/NC-F15-07/plan/validation ก่อนเริ่มโค้ดแล้ว

## ขอบเขตที่ตรวจ

- `core/orders.py`: immutable intent/scope/size/profile/constraints/event/state/reservation
- `core/order_book.py`: verified bounded book/trade DTOs และ shadow liquidity transitions
- `core/paper_matching.py`: admission-policy boundary, reserve checks, crossing/resting/FIFO,
  cancel/partial/terminal, input/trade/execution dedupe, gap/rebase และ typed replay
- `core/money/order_arithmetic.py`: guarded budget sizing/step alignment โดยใช้ rounding
  และ storage bounds เดิม; export ผ่าน `core/money/__init__.py`
- `core/trading_limits.py`: additive max quantity/notional และ price bounds/tick checks
  ใช้ร่วมกับของเดิม ไม่เปลี่ยน default behavior ของ callers เดิม
- tests ใหม่ `tests/core/test_paper_matching.py` และ discovery/transitive Paper isolation gate

Tests ใช้ `PAPER_STANDARD_V1`/`PAPER_DEPTH_SHADOW_V1`, deterministic UUID/time inputs,
versioned synthetic constraints และ test-only AdmissionPolicy ไม่มี production READY factory
ใช้ F-14 `apply_execution` เดิมตรวจ cash/cost/PnL; ไม่คำนวณ PnL ชุดใหม่

## ผลตรวจบนโค้ดสุดท้ายของ checkpoint

รันจาก `backend/`:

```text
uv run pytest tests/core tests/test_core_purity.py tests/gates/test_paper_isolation.py
370 passed in 10.59s

uv run mypy src/tiewtrade/core/orders.py src/tiewtrade/core/order_book.py src/tiewtrade/core/paper_matching.py src/tiewtrade/core/money/order_arithmetic.py src/tiewtrade/core/money/__init__.py src/tiewtrade/core/trading_limits.py tests/core/test_paper_matching.py tests/gates/test_paper_isolation.py
Success: no issues found in 8 source files

uv run ruff check src/tiewtrade/core/orders.py src/tiewtrade/core/order_book.py src/tiewtrade/core/paper_matching.py src/tiewtrade/core/money/order_arithmetic.py src/tiewtrade/core/money/__init__.py src/tiewtrade/core/trading_limits.py tests/core/test_paper_matching.py tests/gates/test_paper_isolation.py
All checks passed

uv run ruff format --check src/tiewtrade/core/orders.py src/tiewtrade/core/order_book.py src/tiewtrade/core/paper_matching.py src/tiewtrade/core/money/order_arithmetic.py src/tiewtrade/core/money/__init__.py src/tiewtrade/core/trading_limits.py tests/core/test_paper_matching.py tests/gates/test_paper_isolation.py
8 files already formatted

$env:PYTHONIOENCODING='utf-8'; uv run lint-imports
7 contracts kept, 0 broken

git diff --check
Passed
```

Import graph ไม่เปลี่ยนหลังผล lint-imports ที่ผ่าน; final additions เป็น event validation/tests
ไม่มี network/credential call, PostgreSQL หรือ Redis ในชุดนี้
Core checkpoint มี F-15 tests 39 cases รวม parametrized/Hypothesis และ regression เดิม

Fingerprint ของ code/tests 8 ไฟล์ด้านบน: SHA-256 ของ sorted relative path UTF-8,
NUL, raw file bytes, NUL ต่อไฟล์:
`195cda3d4007ec0bb556f6d3235cfdcbfcd760769d9444adc6d80a15a6339c31`

รอบแรก 2 failed/236 passed จาก fixture step ไม่รองรับ sell 0.999 และ fixture มี ask
อีกระดับที่ test ไม่ได้นับ; แก้ fixtures ตาม oracle แล้วผ่าน ไม่ได้ผ่อนกฎ production
ระหว่างเพิ่ม coverage แก้การ dedupe trade เก่าที่มาซ้ำหลัง trade ใหม่ และเพิ่ม explicit
input-gap/rebase checks พร้อมเก็บ exact admission/input constraints สำหรับ replay
Static รอบแรกมี naming/type/format findings ที่แก้แล้ว; lint-imports รอบแรกเจอ stdout
cp1252 UnicodeEncodeError จึงตั้ง process encoding เป็น UTF-8 แล้วได้ผลผ่านข้างบน

## Coverage และงานค้าง

V-1..V-6 เป็น Partial: core ผ่านตาม golden/property/typed replay/isolation tests
แต่ PostgreSQL round-trip, serialized durable evidence/ledger replay, public feed proof,
F-10 freshness integration และ production policy composition ยังต้องตรวจใน M2/M3
Reviewer ตรวจ diff/dependencies ที่เกี่ยวข้องแล้ว ไม่พบ Critical/High ค้างในขอบเขต core
ไม่ถือเป็น final integration review หรือ candidate approval

ถัดไป M2: public adapter/sequence bridge/input storage/migrations/RLS/evidence และ
fake feed flow ตาม V-7..V-9/V-16; ต่อด้วย M3 writer/ledger/F-14 และ M4 reset API/UI
API/engine ปัจจุบันยังไม่เรียก matcher ใหม่ และ reset runtime ยัง fail closed ตามเดิม
ก่อนใช้ funds กับหลาย pair caller ต้องหัก reservations ของ pair อื่นและใช้ authoritative
cash/holdings ที่ apply F-14 effects แล้วภายใต้ financial lock; core state นี้ต่อหนึ่ง pair

V-7..V-18 ยัง Not Run, V-19 Pending Full Validation; ไม่ปิดผล F-13/F-14 เดิม
ยังไม่รัน backend full suite, database/browser, candidate CI หรือ release workloads
ไม่มี commit/push/merge ใน checkpoint นี้

## เวลา

Final pytest วัด 10.59s; final scoped static command cell วัด 0.56s;
lint-imports/format/environment command cell วัด 0.52s
การอ่าน/เขียน/รีวิวและเวลารออนุมัติไม่ได้จับเวลาแยก จึงไม่อ้างเวลารวม
คำสั่งที่รันพร้อมกันไม่นำเวลามาบวกเป็น wall time
