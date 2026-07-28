# Paper Futures Liquidation Definition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ Paper Futures Policy v1 ใช้ price-crossing เป็น Liquidation verdict เพียงแบบเดียว และลบ `FuturesMarginSnapshot.is_liquidated` ที่ไม่มี production consumer

**Architecture:** Paper Futures ให้ `trading` เป็นเจ้าของสูตรและ price-crossing rule, `application` เป็นผู้ orchestrate และ `execution` สร้าง fill เท่านั้น ส่วน Live Futures ถือค่า Liquidation จาก Binance เป็น authoritative account facts และไม่ใช้สูตร Paper ตัดสินแทน Exchange

**Tech Stack:** Python 3.12, frozen dataclasses, Decimal, pytest, Ruff, Mypy, Markdown

## Global Constraints

- เลือกทางเลือก A: LONG ใช้ `candle.low <= liquidation_price` และ SHORT ใช้ `candle.high >= liquidation_price`
- snapshot เก็บเฉพาะ `account_equity` และ `liquidation_price` ซึ่งมี production consumer จริง
- ห้ามเปลี่ยนสูตร `liquidation_price`, equity, fill price, fee, slippage, terminal state หรือ `close_reason`
- Live Futures ต้องใช้ Binance liquidation-related account facts เป็น authoritative source; ห้ามนำสูตร Paper ไปใช้เป็น Live verdict
- ห้ามเพิ่ม Live order, Binance private API, credentials หรือ network test
- ใช้ TDD: RED ก่อน production code และบันทึกผล RED/GREEN ใน task report
- สนทนา เอกสารอธิบาย และรายงานเป็นภาษาไทย; identifiers, code และ code comments เป็นภาษาอังกฤษ

---

### Task 1: Remove the duplicate equity-based Liquidation verdict

> **หมายเหตุ:** snapshot contract และ execution ownership ใน Task 1 เป็น intermediate
> implementation ที่ถูกแทนที่ด้วย final contract ใน Task 2 เพื่อแก้ final-review findings
> ห้ามใช้ snippets ของ Task 1 เป็นเป้าหมายสุดท้ายของ branch

**Files:**
- Modify: `tests/unit/trading/test_futures_margin.py`
- Modify: `src/tiewtrade/trading/futures_margin.py`
- Modify: `CONTEXT.md`

**Interfaces:**
- Consumes: `FuturesMarginModel.snapshot(...) -> FuturesMarginSnapshot`
- Produces: `FuturesMarginSnapshot(account_equity, maintenance_margin, liquidation_price)` โดยไม่มี `is_liquidated`
- Preserves: `PaperFuturesExecutor.fill_liquidation(basket, candle, *, liquidation_price)` และ price-crossing behavior เดิม

- [ ] **Step 1: เพิ่ม regression test สำหรับ snapshot contract ที่ต้องการ**

เพิ่ม test ต่อไปนี้ใน `tests/unit/trading/test_futures_margin.py` โดยใช้ `model()` และ `margin_inputs()` ที่มีอยู่:

```python
def test_snapshot_does_not_duplicate_liquidation_verdict() -> None:
    snapshot = model().snapshot(
        **margin_inputs(),  # type: ignore[arg-type]
        current_price=Decimal("90"),
    )

    assert not hasattr(snapshot, "is_liquidated")
```

- [ ] **Step 2: รัน test เพื่อยืนยัน RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_futures_margin.py::test_snapshot_does_not_duplicate_liquidation_verdict -q
```

Expected: FAIL เพราะ snapshot ปัจจุบันยังมี `is_liquidated`

- [ ] **Step 3: ลด `FuturesMarginSnapshot` contract และลบ calculation ซ้ำ**

แก้ `src/tiewtrade/trading/futures_margin.py` ให้ dataclass เหลือ:

```python
@dataclass(frozen=True, slots=True)
class FuturesMarginSnapshot:
    account_equity: Decimal
    maintenance_margin: Decimal
    liquidation_price: Decimal | None
```

และแก้ return ใน `snapshot()` เป็น:

```python
return FuturesMarginSnapshot(
    account_equity=account_equity,
    maintenance_margin=maintenance_margin,
    liquidation_price=liquidation_price,
)
```

- [ ] **Step 4: ปรับ tests ที่อ้าง boolean เดิมโดยคง coverage ของตัวเลข**

ใน `tests/unit/trading/test_futures_margin.py`:

- ลบ `assert not snapshot.is_liquidated` ออกจาก tests ที่ตรวจ equity และ maintenance margin
- เปลี่ยนชื่อ `test_snapshot_marks_position_liquidated_when_equity_reaches_maintenance` เป็น `test_snapshot_keeps_equity_and_maintenance_margin_at_adverse_price`
- คง assertions ต่อไปนี้ไว้ใน test ที่เปลี่ยนชื่อ และลบ `assert snapshot.is_liquidated`

```python
assert snapshot.account_equity == Decimal("0")
assert snapshot.maintenance_margin == Decimal("0.450")
```

- [ ] **Step 5: รัน focused GREEN และ Liquidation behavior tests**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_futures_margin.py \
  tests/unit/execution/test_paper_futures.py \
  tests/unit/application/test_paper_futures_session.py -q
```

Expected: PASS และ tests ของ executor/session ยืนยันว่า price-crossing behavior เดิมยังทำงาน

- [ ] **Step 6: บันทึกกฎเดียวใน Domain Context**

แทนหัวข้อ `### Liquidation` ใน `CONTEXT.md` ด้วยข้อความ:

```markdown
### Liquidation

Liquidation เป็นผลลัพธ์แบบ deterministic ของ Paper Futures Policy v1 ที่ปิด Basket
และห้ามสร้าง Entry ใหม่ โดยใช้ price-crossing เป็นเกณฑ์ตัดสินเพียงแบบเดียว:

- LONG เกิด Liquidation เมื่อ `candle.low <= liquidation_price`
- SHORT เกิด Liquidation เมื่อ `candle.high >= liquidation_price`
- หากราคาแตะระดับ Liquidation ระหว่าง completed Candle แล้วฟื้นกลับก่อน Candle ปิด
  ให้ถือว่าเกิด Liquidation แล้ว

`account_equity` และ `maintenance_margin` เป็นข้อมูลสำหรับแสดงผลและตรวจสอบย้อนหลัง
ไม่ใช่ Liquidation verdict
```

- [ ] **Step 7: ตรวจว่าไม่มี duplicate verdict เหลืออยู่**

Run:

```bash
rg -n "is_liquidated" src CONTEXT.md
rg -n "is_liquidated" tests/unit/trading/test_futures_margin.py
```

Expected: คำสั่งแรกไม่มี output ส่วนคำสั่งที่สองพบเฉพาะ regression assertion
`assert not hasattr(snapshot, "is_liquidated")` หนึ่งจุด เพื่อป้องกันไม่ให้ duplicate
verdict กลับเข้ามาใน snapshot contract

- [ ] **Step 8: รัน full verification**

Run:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix ../../docs-site test
npm --prefix ../../docs-site run check:content
git diff --check
```

Expected: ทุกคำสั่งผ่าน

- [ ] **Step 9: Commit implementation**

```bash
git add CONTEXT.md \
  src/tiewtrade/trading/futures_margin.py \
  tests/unit/trading/test_futures_margin.py
git commit -m "refactor: use one Paper Futures liquidation rule"
```

---

### Task 2: Resolve final review findings and enforce module ownership

**Files:**
- Modify: `PRODUCT.md`
- Modify: `CONTEXT.md`
- Modify: `docs/superpowers/specs/2026-07-27-paper-futures-core-execution-design.md`
- Modify: `tests/unit/trading/test_futures_margin.py`
- Modify: `tests/unit/execution/test_paper_futures.py`
- Modify: `tests/unit/application/test_paper_futures_session.py`
- Modify: `src/tiewtrade/trading/futures_margin.py`
- Modify: `src/tiewtrade/execution/paper_futures.py`
- Modify: `src/tiewtrade/application/paper_futures_session.py`

**Interfaces:**
- Produces: `FuturesMarginSnapshot(account_equity, liquidation_price)`
- Produces: side-aware Paper price-crossing predicate owned by `trading`
- Preserves: gap-aware `PaperFuturesExecutor.fill_liquidation(...)` fill construction
- Preserves: Liquidation priority, terminal state, close reason, fee, slippage และ idempotency

- [ ] **Step 1: แก้ Source of Truth ก่อน production code**

แก้ `PRODUCT.md` ก่อน แล้วจึง `CONTEXT.md` ให้ระบุว่า:

- Paper Futures ใช้ inclusive completed-Candle price crossing เป็น deterministic verdict
- Live Futures ใช้ `liquidationPrice`, `markPrice` และ maintenance-margin facts จาก Binance
  เป็น authoritative; local Paper formula ใช้ตัดสิน Live ไม่ได้
- DEV-123 ไม่เชื่อม Binance และไม่ส่ง Live order

แก้ design วันที่ 2026-07-27 ให้ equity inequality เป็นสมการ derive threshold ไม่ใช่ runtime
Liquidation verdict

- [ ] **Step 2: เพิ่ม failing contract และ boundary tests**

เพิ่ม test ก่อนแก้ production codeให้ยืนยันว่า:

- `FuturesMarginSnapshot` ไม่มี `maintenance_margin`
- LONG ที่ `candle.low == liquidation_price` ให้ `True`
- SHORT ที่ `candle.high == liquidation_price` ให้ `True`
- ราคาที่ยังไม่แตะ threshold ให้ `False`
- session ไม่เรียก executor จนกว่า trading predicate จะผ่าน
- executor ไม่ปฏิเสธ fill ด้วย price-crossing rule ของตัวเอง

- [ ] **Step 3: รัน RED และบันทึก failure ที่คาดไว้**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_futures_margin.py \
  tests/unit/execution/test_paper_futures.py \
  tests/unit/application/test_paper_futures_session.py -q
```

Expected: FAIL ด้วย contract/predicate/orchestration ใหม่ ก่อนแก้ production code

- [ ] **Step 4: ลด snapshot contract**

ลบ `maintenance_margin` field และ calculation ออกจาก `FuturesMarginSnapshot.snapshot()`
โดยคง `maintenance_margin_rate` ใน policy และสูตร `liquidation_price` เดิมไว้ เพราะ rate ยังเป็น
input ของ threshold model

- [ ] **Step 5: ย้าย price-crossing rule ไป `trading`**

เพิ่ม focused method หรือ function ใน `trading/futures_margin.py` โดยไม่สร้าง generic abstraction:

- LONG: `candle_low <= liquidation_price`
- SHORT: `candle_high >= liquidation_price`
- validate threshold เป็น finite และ positive

- [ ] **Step 6: ให้ application orchestrate และ execution สร้าง fill เท่านั้น**

แก้ `PaperFuturesSession._fill_liquidation()` ให้เรียก predicate จาก `trading` ก่อน หากไม่ผ่าน
return `None`; หากผ่านจึงเรียก executor

ลบ low/high crossing checks ออกจาก `PaperFuturesExecutor.fill_liquidation()` แต่คง
gap-aware fill price, validations, fee, slippage, symbol check และ idempotency เดิม

- [ ] **Step 7: รัน focused GREEN**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_futures_margin.py \
  tests/unit/execution/test_paper_futures.py \
  tests/unit/application/test_paper_futures_session.py -q
```

Expected: PASS

- [ ] **Step 8: ตรวจ contracts และ full verification**

```bash
rg -n "maintenance_margin|is_liquidated" src
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix ../../docs-site test
npm --prefix ../../docs-site run check:content
git diff --check
```

Expected: `rg` พบ `maintenance_margin_rate` ได้ แต่ไม่พบ snapshot field/calculation หรือ
`is_liquidated` ใน production; quality gates ทุกคำสั่งผ่าน

- [ ] **Step 9: Commit review fixes**

```bash
git add PRODUCT.md CONTEXT.md \
  docs/superpowers/specs/2026-07-27-paper-futures-core-execution-design.md \
  src/tiewtrade/trading/futures_margin.py \
  src/tiewtrade/execution/paper_futures.py \
  src/tiewtrade/application/paper_futures_session.py \
  tests/unit/trading/test_futures_margin.py \
  tests/unit/execution/test_paper_futures.py \
  tests/unit/application/test_paper_futures_session.py
git commit -m "refactor: clarify Paper Futures liquidation ownership"
```

---

### Task 3: Clarify cross-mode architecture and close regression gaps

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `tests/unit/trading/test_futures_margin.py`

**Interfaces:**
- Clarifies: shared post-Liquidation lifecycle/risk policies versus mode-specific authority
- Preserves: Paper predicate and all production behavior

- [ ] **Step 1: แก้ Architecture Source of Truth**

ปรับ `ARCHITECTURE.md` ให้ระบุชัดเจนว่า:

- Paper และ Live ใช้ Strategy, capital, Basket, Entry Pair, risk limits และ
  post-Liquidation lifecycle rules ร่วมกัน
- Paper Futures deterministic threshold/predicate อยู่ใน `trading`
- Live Futures ใช้ Binance position/account facts และ Binance Liquidation Engine เป็น
  authoritative; local Paper formula ไม่ใช่ Live verdict
- Live integration/reconciliation เป็นเจ้าของการอ่านและสะท้อน exchange facts โดยไม่ทำให้
  `trading` import Binance SDK

- [ ] **Step 2: เพิ่ม failing validation test**

เพิ่ม parameterized test ให้ `FuturesMarginModel.is_liquidation_crossed()` ปฏิเสธ
`NaN`, `Infinity`, `0` และค่าติดลบของ `liquidation_price`

- [ ] **Step 3: รัน RED แล้วทำ minimal fix เฉพาะเมื่อจำเป็น**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_futures_margin.py -q
```

Expected: หาก implementation validation เดิมถูกต้อง test อาจ PASS ทันที ให้บันทึกเป็น
characterization evidence และห้ามแก้ production codeโดยไม่จำเป็น

- [ ] **Step 4: รัน full verification และ commit**

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix ../../docs-site test
npm --prefix ../../docs-site run check:content
git diff --check
```

```bash
git add ARCHITECTURE.md tests/unit/trading/test_futures_margin.py
git commit -m "docs: clarify Live Futures liquidation authority"
```
