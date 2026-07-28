# Paper Futures Liquidation Definition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ Paper Futures Policy v1 ใช้ price-crossing เป็น Liquidation verdict เพียงแบบเดียว และลบ `FuturesMarginSnapshot.is_liquidated` ที่ไม่มี production consumer

**Architecture:** `FuturesMarginModel` ยังคำนวณ `liquidation_price`, `account_equity` และ `maintenance_margin` ส่วน `PaperFuturesExecutor` เป็นผู้ตัดสิน Liquidation จากช่วงราคา completed Candle เหมือนเดิม การเปลี่ยนแปลงจำกัดอยู่ที่การลด snapshot contract, ปรับ tests และระบุกฎใน Domain Context โดยไม่แตะ execution behavior

**Tech Stack:** Python 3.12, frozen dataclasses, Decimal, pytest, Ruff, Mypy, Markdown

## Global Constraints

- เลือกทางเลือก A: LONG ใช้ `candle.low <= liquidation_price` และ SHORT ใช้ `candle.high >= liquidation_price`
- `account_equity` และ `maintenance_margin` คงเป็นข้อมูลสำหรับแสดงผลและตรวจสอบย้อนหลัง แต่ไม่ใช่ Liquidation verdict
- ห้ามเปลี่ยนสูตร `liquidation_price`, equity, maintenance margin, fill price, fee, slippage, terminal state หรือ `close_reason`
- ห้ามเพิ่ม Live order, Binance private API, credentials หรือ network test
- ใช้ TDD: RED ก่อน production code และบันทึกผล RED/GREEN ใน task report
- สนทนา เอกสารอธิบาย และรายงานเป็นภาษาไทย; identifiers, code และ code comments เป็นภาษาอังกฤษ

---

### Task 1: Remove the duplicate equity-based Liquidation verdict

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
rg -n "is_liquidated" src tests CONTEXT.md
```

Expected: ไม่มี output

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
