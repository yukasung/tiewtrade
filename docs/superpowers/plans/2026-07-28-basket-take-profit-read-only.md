# Basket Take Profit Read-only Property Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ป้องกันไม่ให้ consumer แก้ `Basket.take_profit_price` โดยตรง ขณะที่การอ่านค่า สูตรคำนวณ การปัดราคา และ deterministic replay ยังคงเหมือนเดิมทุกประการ

**Architecture:** `Basket` ใน `trading` ยังคงเป็นเจ้าของ Take Profit invariant โดยเก็บค่าใน private attribute และเปิดผ่าน read-only property การเปลี่ยนแปลงเป็น mechanical encapsulation ภายใน class เดียว ไม่เปลี่ยน public read contract หรือ execution call sites

**Tech Stack:** Python 3.12, Decimal, pytest, Ruff, Mypy

## Global Constraints

- `take_profit_price` ต้องอ่านได้ผ่าน property เดิมและเขียนจากภายนอกไม่ได้
- เฉพาะ `Basket.add_entry()` เท่านั้นที่เปลี่ยนค่า Take Profit หลัง validation และ quantization สำเร็จ
- ห้ามเปลี่ยนสูตร weighted average, ATR multiplier, LONG/SHORT rounding หรือ Basket lifecycle
- ห้ามแก้ execution/application call sites เพราะเป็น read-only consumers อยู่แล้ว
- ต้องพิสูจน์ RED ก่อนแก้ production code และ deterministic replay ต้องให้ output เดิม
- ห้ามเพิ่ม Live order, Binance private API, credentials หรือ network test

---

### Task 1: Encapsulate Basket Take Profit state

**Files:**
- Modify: `tests/unit/trading/test_basket.py`
- Modify: `src/tiewtrade/trading/basket.py`

**Interfaces:**
- Preserves: `Basket.take_profit_price -> Decimal | None`
- Changes: external assignment to `Basket.take_profit_price` raises `AttributeError`
- Owns mutation: `Basket.add_entry(...)` writes only `self._take_profit_price`

- [ ] **Step 1: เพิ่ม failing test สำหรับ read-only contract**

เพิ่ม test ใน `tests/unit/trading/test_basket.py`:

```python
def test_take_profit_price_is_read_only() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
    )

    with pytest.raises(AttributeError):
        setattr(basket, "take_profit_price", Decimal("999"))

    assert basket.take_profit_price is None
```

- [ ] **Step 2: รัน test เพื่อยืนยัน RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_basket.py::test_take_profit_price_is_read_only -q
```

Expected: FAIL ด้วย `DID NOT RAISE <class 'AttributeError'>` เพราะ field ปัจจุบันเขียนจากภายนอกได้

- [ ] **Step 3: ทำ minimal implementation**

แก้ `Basket.__init__()`:

```python
self._take_profit_price: Decimal | None = None
```

เพิ่ม property ใกล้ property state อื่น:

```python
@property
def take_profit_price(self) -> Decimal | None:
    return self._take_profit_price
```

แก้บรรทัด commit state ใน `add_entry()`:

```python
self._take_profit_price = take_profit_price
```

- [ ] **Step 4: รัน focused GREEN**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/trading/test_basket.py -q
```

Expected: PASS และ tests เดิมของ LONG/SHORT repricing, invalid mutation และ close PnL ผ่าน

- [ ] **Step 5: ตรวจ consumer และ deterministic replay**

```bash
rg -n "take_profit_price\s*=" src tests
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_spot_replay.py \
  tests/acceptance/test_paper_futures_session.py \
  tests/acceptance/test_paper_replay_cli.py -q
```

Expected: production assignment พบเฉพาะ private state ใน `basket.py`; acceptance tests ผ่านและ replay output เดิม

- [ ] **Step 6: รัน full verification**

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

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/plans/2026-07-28-basket-take-profit-read-only.md \
  src/tiewtrade/trading/basket.py \
  tests/unit/trading/test_basket.py
git commit -m "refactor: make Basket take profit read-only"
```
