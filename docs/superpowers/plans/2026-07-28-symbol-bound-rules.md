# Symbol-Bound Trading Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ผูก `SymbolRules` กับ market symbol และทำให้ Paper Spot/Futures ปฏิเสธ Candle ของคนละ symbol ก่อนคำนวณหรือสร้าง Fill

**Architecture:** `trading.SymbolRules` เป็น immutable value object ที่ถือ identity และ exchange filters ร่วมกัน ส่วน Paper execution adapters เป็น safety boundary ที่เปรียบเทียบ `Candle.symbol` กับ `SymbolRules.symbol` ในทุก method ที่ใช้ Candle การสร้าง replay ใช้ `MarketDataConfig.symbol` เป็นแหล่ง identity เดียว โดยยังไม่เพิ่ม Binance `exchangeInfo` adapter

**Tech Stack:** Python 3.13, dataclasses, Decimal, pytest, Ruff, Mypy

## Global Constraints

- Internal Alpha รองรับ BTCUSDT เพียง symbol เดียว; ห้ามเปิด symbol ที่สองใน Issue นี้
- `symbol` มาจาก Session/market configuration และห้าม hard-code ใน business logic
- เปรียบเทียบ symbol แบบ exact equality; ห้าม trim, uppercase หรือแก้ identity เงียบ ๆ
- Paper และ Live ใช้ business rules ร่วมกัน แต่ Issue นี้แตะเฉพาะ concrete Paper executors
- ใช้ Paper และ fake data เท่านั้น ห้ามเรียก Binance network หรือ Live execution
- คงค่า BTCUSDT V1 `tick_size=0.01`, `step_size=0.001`, `min_notional=5` ใน replay จนกว่าจะมี Level 2 Issue สำหรับ `exchangeInfo`
- ไม่สร้าง interface, factory, registry หรือ generic symbol-rules provider
- เอกสารออกแบบต้นทาง: `docs/superpowers/specs/2026-07-28-symbol-bound-rules-design.md`

---

## ผังไฟล์

### ไฟล์ Production

- `src/tiewtrade/trading/symbol_rules.py` — เพิ่ม immutable symbol identity และ validation
- `src/tiewtrade/execution/paper_spot.py` — ตรวจ identity ก่อน Spot Entry/Take Profit
- `src/tiewtrade/execution/paper_futures.py` — ตรวจ identity ก่อน Futures Entry/Take Profit/Liquidation
- `src/tiewtrade/paper_replay_main.py` — ส่ง `MarketDataConfig.symbol` เข้า `SymbolRules`

### จุดเรียกใช้ใน Test และ fixture

- `tests/unit/trading/test_capital.py`
- `tests/unit/execution/test_paper_spot.py`
- `tests/unit/execution/test_paper_futures.py`
- `tests/unit/application/test_paper_spot_session.py`
- `tests/unit/application/test_paper_futures_session.py`
- `tests/unit/replay/test_paper_spot_runner.py`
- `tests/acceptance/test_paper_spot_replay.py`
- `tests/acceptance/test_paper_spot_trade_history.py`
- `tests/acceptance/test_paper_futures_session.py`
- `tests/acceptance/test_paper_futures_trade_history.py`
- `tests/acceptance/test_public_market_data_runtime.py`

---

### Task 1: เพิ่ม Symbol Identity ให้ `SymbolRules`

**Files:**

- Modify: `src/tiewtrade/trading/symbol_rules.py:5-17`
- Modify: `src/tiewtrade/paper_replay_main.py:45-50`
- Modify: ทุกจุดเรียกใช้ test/fixture ที่ระบุในผังไฟล์
- Test: `tests/unit/trading/test_capital.py:98-130`
- Acceptance: `tests/acceptance/test_paper_replay_cli.py`

**Interfaces:**

- Consumes: `MarketDataConfig.symbol: str`
- Produces: `SymbolRules(symbol: str, tick_size: Decimal, step_size: Decimal, min_notional: Decimal)`
- Invariant: `SymbolRules.symbol` ไม่ว่างหลังตรวจด้วย `str.strip()` แต่ค่าที่เก็บจะไม่ถูก normalize

- [ ] **Step 1: เขียน test validation ของ symbol ที่ต้องล้มเหลวก่อน**

เพิ่มใน `tests/unit/trading/test_capital.py`:

```python
@pytest.mark.parametrize("symbol", ["", "   "])
def test_symbol_rules_require_a_non_blank_symbol(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol must not be blank"):
        SymbolRules(
            symbol=symbol,
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        )


def test_symbol_rules_preserve_a_nonblank_padded_symbol() -> None:
    rules = SymbolRules(
        symbol=" BTCUSDT ",
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )

    assert rules.symbol == " BTCUSDT "
```

- [ ] **Step 2: รัน test และยืนยัน RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_capital.py::test_symbol_rules_require_a_non_blank_symbol -q
```

ผลที่คาดหวัง: FAIL เพราะ `SymbolRules` ยังไม่รับ argument `symbol`.

- [ ] **Step 3: เพิ่ม contract ของ immutable symbol เท่าที่จำเป็น**

แก้ `src/tiewtrade/trading/symbol_rules.py`:

```python
@dataclass(frozen=True, slots=True)
class SymbolRules:
    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_notional: Decimal

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be blank")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.step_size <= 0:
            raise ValueError("step_size must be positive")
        if self.min_notional <= 0:
            raise ValueError("min_notional must be positive")
```

- [ ] **Step 4: ปรับ constructor ทุกจุดโดยไม่เปลี่ยนค่า filter**

แทรก `symbol="BTCUSDT",` ก่อน argument `tick_size=` ที่มีอยู่ทันทีใน constructor
ของ test/fixture ทุกจุดที่ระบุในผังไฟล์ ตัวอย่างเช่น constructor ใน
`tests/unit/trading/test_capital.py::test_symbol_rules_round_quantity_and_price_down`
ต้องเป็นดังนี้:

```python
SymbolRules(
    symbol="BTCUSDT",
    tick_size=Decimal("0.10"),
    step_size=Decimal("0.001"),
    min_notional=Decimal("5"),
)
```

ใน `src/tiewtrade/paper_replay_main.py` market identity ต้องมาจาก configuration ที่ผ่าน validation แล้ว:

```python
symbol_rules=SymbolRules(
    symbol=market_data.symbol,
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.001"),
    min_notional=Decimal("5"),
),
```

ห้ามแทนที่ `market_data.symbol` ด้วย `arguments.symbol` หรือ literal `"BTCUSDT"` อีกชุดหนึ่ง

- [ ] **Step 5: รัน tests ที่ระบุและยืนยัน GREEN**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/trading/test_capital.py \
  tests/acceptance/test_paper_replay_cli.py
```

ผลที่คาดหวัง: tests ที่ระบุทั้งหมด PASS และ replay JSON ต้องไม่เปลี่ยนแม้แต่ byte เดียว

- [ ] **Step 6: ค้นหา constructor ที่อาจตกหล่น**

รัน:

```bash
rg -n "SymbolRules\\(" src tests
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
```

ผลที่คาดหวัง: constructor ทุกจุดส่ง `symbol` และ test suite ทั้งหมดผ่าน

- [ ] **Step 7: Commit Task 1**

```bash
git add \
  src/tiewtrade/trading/symbol_rules.py \
  src/tiewtrade/paper_replay_main.py \
  tests
git commit -m "feat: bind symbol rules to market identity"
```

---

### Task 2: ปฏิเสธ Candle ที่ symbol ไม่ตรงใน Paper Spot

**Files:**

- Modify: `src/tiewtrade/execution/paper_spot.py:39-94`
- Test: `tests/unit/execution/test_paper_spot.py`

**Interfaces:**

- Consumes: `Candle.symbol` และ `SymbolRules.symbol`
- Produces: `PaperSpotExecutor._require_matching_symbol(candle: Candle) -> None`
- Error: `ValueError("candle symbol must match SymbolRules.symbol: candle='ETHUSDT', rules='BTCUSDT'")`

- [ ] **Step 1: เพิ่ม import และ Entry mismatch test ที่ต้องล้มเหลวก่อน**

เพิ่มใน `tests/unit/execution/test_paper_spot.py`:

```python
from dataclasses import replace

import pytest
```

จากนั้นเพิ่ม:

```python
def test_entry_fill_rejects_a_lowercase_near_match() -> None:
    executor = PaperSpotExecutor(spot_session(), spot_rules())
    signal_candle = candle_at(0, open_price="100", high="102", low="99", close="101")
    fill_candle = replace(
        candle_at(5, open_price="101", high="103", low="100", close="102"),
        symbol="btcusdt",
    )

    with pytest.raises(ValueError) as error:
        executor.fill_entry(intent(spot_session(), signal_candle), fill_candle)

    assert str(error.value) == (
        "candle symbol must match SymbolRules.symbol: "
        "candle='btcusdt', rules='BTCUSDT'"
    )
```

เพิ่ม helper สำหรับ configuration ที่ถูกต้องต่อไปนี้ในไฟล์ test โดยไม่เปลี่ยน setup
ที่ tests เดิมใช้อยู่:

```python
def spot_session() -> SessionConfig:
    return SessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        preset_version="rsi-step-grid-v1",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("0"),
        entry_policy=EntryPolicy(max_entries=4),
        spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.6")),
    )


def spot_rules() -> SymbolRules:
    return SymbolRules(
        symbol="BTCUSDT",
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )
```

- [ ] **Step 2: รัน Entry test และยืนยัน RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_spot.py::test_entry_fill_rejects_a_lowercase_near_match -q
```

ผลที่คาดหวัง: FAIL เพราะ executor สร้าง Fill แทนที่จะ raise `ValueError`.

- [ ] **Step 3: เพิ่ม Take Profit mismatch test ที่ต้องล้มเหลวก่อน**

เพิ่ม:

```python
def test_take_profit_rejects_a_padded_near_match() -> None:
    rules = spot_rules()
    basket = Basket(
        UUID("00000000-0000-0000-0000-000000000092"),
        EntryPolicy(max_entries=4),
        Decimal("1"),
    )
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("1"),
        tick_size=rules.tick_size,
    )
    candle = replace(
        candle_at(5, open_price="100", high="101", low="99", close="100"),
        symbol=" BTCUSDT ",
    )

    with pytest.raises(ValueError) as error:
        PaperSpotExecutor(spot_session(), rules).fill_take_profit(basket, candle)

    assert str(error.value) == (
        "candle symbol must match SymbolRules.symbol: "
        "candle=' BTCUSDT ', rules='BTCUSDT'"
    )
```

- [ ] **Step 4: รันทั้งสอง tests และยืนยัน RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_spot.py \
  -k "near_match" -q
```

ผลที่คาดหวัง: ทั้งสอง tests FAIL เพราะยังไม่มี symbol guard.

- [ ] **Step 5: เพิ่ม Paper Spot guard เท่าที่จำเป็น**

แก้ `src/tiewtrade/execution/paper_spot.py`:

```python
    # Add as the first statement in fill_entry.
    self._require_matching_symbol(candle)

    # Add as the first statement in fill_take_profit.
    self._require_matching_symbol(candle)

    def _require_matching_symbol(self, candle: Candle) -> None:
        if candle.symbol != self._symbol_rules.symbol:
            raise ValueError(
                "candle symbol must match SymbolRules.symbol: "
                f"candle={candle.symbol!r}, rules={self._symbol_rules.symbol!r}"
            )
```

วาง helper หลัง public fill methods และห้าม return `None` เมื่อ identity ไม่ตรงกัน

- [ ] **Step 6: รัน Paper Spot tests และยืนยัน GREEN**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/execution/test_paper_spot.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/acceptance/test_paper_spot_replay.py \
  tests/acceptance/test_paper_spot_trade_history.py
```

ผลที่คาดหวัง: Paper Spot tests ทั้งหมด PASS โดย Fill ของ symbol ที่ถูกต้องไม่เปลี่ยน

- [ ] **Step 7: Commit Task 2**

```bash
git add \
  src/tiewtrade/execution/paper_spot.py \
  tests/unit/execution/test_paper_spot.py
git commit -m "fix: reject mismatched Paper Spot candles"
```

---

### Task 3: ปฏิเสธ Candle ที่ symbol ไม่ตรงใน Paper Futures

**Files:**

- Modify: `src/tiewtrade/execution/paper_futures.py:43-176`
- Test: `tests/unit/execution/test_paper_futures.py`

**Interfaces:**

- Consumes: `Candle.symbol` และ `SymbolRules.symbol`
- Produces: `PaperFuturesExecutor._require_matching_symbol(candle: Candle) -> None`
- ต้องทำก่อนคำนวณราคา Entry, ประเมินเป้าหมาย Take Profit และ validate Liquidation

- [ ] **Step 1: เขียน Entry mismatch test ที่ต้องล้มเหลวก่อน**

`tests/unit/execution/test_paper_futures.py` import `dataclasses.replace` และ
`pytest` อยู่แล้ว เพิ่ม:

```python
def test_entry_rejects_a_lowercase_near_match() -> None:
    current = replace(candle(minute=5, open="100"), symbol="btcusdt")

    with pytest.raises(ValueError) as error:
        make_executor().fill_entry(long_intent(), current)

    assert str(error.value) == (
        "candle symbol must match SymbolRules.symbol: "
        "candle='btcusdt', rules='BTCUSDT'"
    )
```

- [ ] **Step 2: รัน Entry test และยืนยัน RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_futures.py::test_entry_rejects_a_lowercase_near_match -q
```

ผลที่คาดหวัง: FAIL เพราะ return Fill แทนที่จะ raise `ValueError`.

- [ ] **Step 3: เขียน Take Profit และ Liquidation mismatch tests ที่ต้องล้มเหลวก่อน**

เพิ่ม:

```python
def test_take_profit_rejects_a_padded_near_match() -> None:
    current = replace(
        candle(open="105", high="107", low="104"),
        symbol=" BTCUSDT ",
    )

    with pytest.raises(ValueError) as error:
        make_executor().fill_take_profit(
            long_basket(entry_price="100", take_profit="106"),
            current,
        )

    assert str(error.value) == (
        "candle symbol must match SymbolRules.symbol: "
        "candle=' BTCUSDT ', rules='BTCUSDT'"
    )


def test_liquidation_rejects_a_candle_from_another_symbol() -> None:
    current = replace(
        candle(open="70", high="110", low="60"),
        symbol="ETHUSDT",
    )

    with pytest.raises(ValueError) as error:
        make_executor().fill_liquidation(
            long_basket(entry_price="100", take_profit="106"),
            current,
            liquidation_price=Decimal("80"),
        )

    assert str(error.value) == (
        "candle symbol must match SymbolRules.symbol: "
        "candle='ETHUSDT', rules='BTCUSDT'"
    )
```

- [ ] **Step 4: รัน mismatch tests ทั้งหมดและยืนยัน RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_futures.py \
  -k "lowercase_near_match or padded_near_match or liquidation_rejects_a_candle_from_another_symbol" -q
```

ผลที่คาดหวัง: ทั้งสาม tests FAIL เพราะยังไม่มี Futures symbol guard.

- [ ] **Step 5: เพิ่ม Paper Futures guard เท่าที่จำเป็น**

แก้ `src/tiewtrade/execution/paper_futures.py`:

```python
    # Add as the first statement in fill_entry.
    self._require_matching_symbol(candle)

    # Add as the first statement in fill_take_profit.
    self._require_matching_symbol(candle)

    # Add as the first statement in fill_liquidation.
    self._require_matching_symbol(candle)

    def _require_matching_symbol(self, candle: Candle) -> None:
        if candle.symbol != self._symbol_rules.symbol:
            raise ValueError(
                "candle symbol must match SymbolRules.symbol: "
                f"candle={candle.symbol!r}, rules={self._symbol_rules.symbol!r}"
            )
```

วาง helper ข้าง `_slippage` และ `_exit_fill`; ห้ามเปลี่ยน pricing ที่รับรู้ side,
ลำดับ liquidation, quantity, fee หรือ Fill identity

- [ ] **Step 6: รัน Paper Futures tests และยืนยัน GREEN**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/execution/test_paper_futures.py \
  tests/unit/application/test_paper_futures_session.py \
  tests/acceptance/test_paper_futures_session.py \
  tests/acceptance/test_paper_futures_trade_history.py
```

ผลที่คาดหวัง: Paper Futures tests ทั้งหมด PASS โดยพฤติกรรมของ symbol ที่ถูกต้องไม่เปลี่ยน

- [ ] **Step 7: รัน verification gate ทั้งหมด**

รัน:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
../../.venv/bin/python -m mypy src
npm --prefix ../../docs-site test
npm --prefix ../../docs-site run check:content
git diff --check
```

ผลที่คาดหวัง: tests และ quality gates ทั้งหมด PASS; ไม่มีการใช้ Binance network หรือ Live order

- [ ] **Step 8: Commit Task 3**

```bash
git add \
  src/tiewtrade/execution/paper_futures.py \
  tests/unit/execution/test_paper_futures.py
git commit -m "fix: reject mismatched Paper Futures candles"
```

---

## รายการตรวจสอบ final review

- [ ] `SymbolRules` ปฏิเสธ symbol `""` และ symbol ที่เป็น whitespace อย่างเดียว
- [ ] constructor ทุกจุดของ `SymbolRules` ส่ง symbol ที่ต้องการ
- [ ] Replay ใช้ `market_data.symbol` ไม่ใช่ identity literal ที่ซ้ำกัน
- [ ] Spot Entry และ Take Profit ปฏิเสธ Candle ที่ symbol ไม่ตรงก่อนคำนวณ
- [ ] Futures Entry, Take Profit และ Liquidation ปฏิเสธ Candle ที่ symbol ไม่ตรงก่อนคำนวณ
- [ ] output ของ BTCUSDT replay ที่ถูกต้องและ Fill identities ไม่เปลี่ยน
- [ ] ไม่ได้เพิ่ม `exchangeInfo`, Live execution, generic provider หรือการรองรับ symbol ที่สอง
- [ ] รัน `code-review` เทียบกับ branch base และแก้ทุก finding ระดับ Critical/Important
- [ ] บันทึกคำสั่ง RED/GREEN และผล final gate ใน DEV-120 Linear comment
