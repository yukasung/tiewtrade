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
- Design source: `docs/superpowers/specs/2026-07-28-symbol-bound-rules-design.md`

---

## File Map

### Production files

- `src/tiewtrade/trading/symbol_rules.py` — เพิ่ม immutable symbol identity และ validation
- `src/tiewtrade/execution/paper_spot.py` — ตรวจ identity ก่อน Spot Entry/Take Profit
- `src/tiewtrade/execution/paper_futures.py` — ตรวจ identity ก่อน Futures Entry/Take Profit/Liquidation
- `src/tiewtrade/paper_replay_main.py` — ส่ง `MarketDataConfig.symbol` เข้า `SymbolRules`

### Test and fixture call sites

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

### Task 1: Add Symbol Identity to `SymbolRules`

**Files:**

- Modify: `src/tiewtrade/trading/symbol_rules.py:5-17`
- Modify: `src/tiewtrade/paper_replay_main.py:45-50`
- Modify: every test/fixture call site listed in File Map
- Test: `tests/unit/trading/test_capital.py:98-130`
- Acceptance: `tests/acceptance/test_paper_replay_cli.py`

**Interfaces:**

- Consumes: `MarketDataConfig.symbol: str`
- Produces: `SymbolRules(symbol: str, tick_size: Decimal, step_size: Decimal, min_notional: Decimal)`
- Invariant: `SymbolRules.symbol` is non-empty after `str.strip()` validation, but the stored value is not normalized

- [ ] **Step 1: Write the failing symbol validation test**

Add to `tests/unit/trading/test_capital.py`:

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
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/trading/test_capital.py::test_symbol_rules_require_a_non_blank_symbol -q
```

Expected: FAIL because `SymbolRules` does not accept the `symbol` argument yet.

- [ ] **Step 3: Add the minimal immutable symbol contract**

Change `src/tiewtrade/trading/symbol_rules.py`:

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

- [ ] **Step 4: Update all constructors without changing filter values**

Insert `symbol="BTCUSDT",` immediately before the existing `tick_size=` argument in
every test/fixture constructor listed in File Map. For example, the constructor in
`tests/unit/trading/test_capital.py::test_symbol_rules_round_quantity_and_price_down`
must become:

```python
SymbolRules(
    symbol="BTCUSDT",
    tick_size=Decimal("0.10"),
    step_size=Decimal("0.001"),
    min_notional=Decimal("5"),
)
```

In `src/tiewtrade/paper_replay_main.py`, market identity must come from the already validated configuration:

```python
symbol_rules=SymbolRules(
    symbol=market_data.symbol,
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.001"),
    min_notional=Decimal("5"),
),
```

Do not replace `market_data.symbol` with `arguments.symbol` or a second `"BTCUSDT"` literal.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/trading/test_capital.py \
  tests/acceptance/test_paper_replay_cli.py
```

Expected: all focused tests PASS and the replay JSON remains byte-for-byte unchanged.

- [ ] **Step 6: Find any constructor that was missed**

Run:

```bash
rg -n "SymbolRules\\(" src tests
PYTHONPATH=src ../../.venv/bin/python -m pytest -q
```

Expected: every constructor supplies `symbol`; the full suite passes.

- [ ] **Step 7: Commit Task 1**

```bash
git add \
  src/tiewtrade/trading/symbol_rules.py \
  src/tiewtrade/paper_replay_main.py \
  tests
git commit -m "feat: bind symbol rules to market identity"
```

---

### Task 2: Reject Mismatched Candles in Paper Spot

**Files:**

- Modify: `src/tiewtrade/execution/paper_spot.py:39-94`
- Test: `tests/unit/execution/test_paper_spot.py`

**Interfaces:**

- Consumes: `Candle.symbol` and `SymbolRules.symbol`
- Produces: `PaperSpotExecutor._require_matching_symbol(candle: Candle) -> None`
- Error: `ValueError("candle symbol must match SymbolRules.symbol: candle='ETHUSDT', rules='BTCUSDT'")`

- [ ] **Step 1: Add imports and failing Entry mismatch test**

Add to `tests/unit/execution/test_paper_spot.py`:

```python
from dataclasses import replace

import pytest
```

Then add:

```python
def test_entry_fill_rejects_a_candle_from_another_symbol() -> None:
    executor = PaperSpotExecutor(spot_session(), spot_rules())
    signal_candle = candle_at(0, open_price="100", high="102", low="99", close="101")
    fill_candle = replace(
        candle_at(5, open_price="101", high="103", low="100", close="102"),
        symbol="ETHUSDT",
    )

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        executor.fill_entry(intent(spot_session(), signal_candle), fill_candle)
```

Add the following focused valid-configuration helpers to the test file without changing
the setup used by existing tests:

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

- [ ] **Step 2: Run the Entry test and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_spot.py::test_entry_fill_rejects_a_candle_from_another_symbol -q
```

Expected: FAIL because the executor creates a Fill instead of raising `ValueError`.

- [ ] **Step 3: Add failing Take Profit mismatch test**

Add:

```python
def test_take_profit_rejects_a_candle_from_another_symbol() -> None:
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
        symbol="ETHUSDT",
    )

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        PaperSpotExecutor(spot_session(), rules).fill_take_profit(basket, candle)
```

- [ ] **Step 4: Run both tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_spot.py \
  -k "another_symbol" -q
```

Expected: both tests FAIL because no symbol guard exists.

- [ ] **Step 5: Add the minimal Paper Spot guard**

Change `src/tiewtrade/execution/paper_spot.py`:

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

Place the helper after the public fill methods. Do not return `None` for identity mismatch.

- [ ] **Step 6: Run Paper Spot tests and verify GREEN**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/execution/test_paper_spot.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/acceptance/test_paper_spot_replay.py \
  tests/acceptance/test_paper_spot_trade_history.py
```

Expected: all Paper Spot tests PASS with unchanged valid-symbol fills.

- [ ] **Step 7: Commit Task 2**

```bash
git add \
  src/tiewtrade/execution/paper_spot.py \
  tests/unit/execution/test_paper_spot.py
git commit -m "fix: reject mismatched Paper Spot candles"
```

---

### Task 3: Reject Mismatched Candles in Paper Futures

**Files:**

- Modify: `src/tiewtrade/execution/paper_futures.py:43-176`
- Test: `tests/unit/execution/test_paper_futures.py`

**Interfaces:**

- Consumes: `Candle.symbol` and `SymbolRules.symbol`
- Produces: `PaperFuturesExecutor._require_matching_symbol(candle: Candle) -> None`
- Applies before Entry price calculation, Take Profit target evaluation and Liquidation validation

- [ ] **Step 1: Write the failing Entry mismatch test**

`tests/unit/execution/test_paper_futures.py` already imports `dataclasses.replace` and
`pytest`. Add:

```python
def test_entry_rejects_a_candle_from_another_symbol() -> None:
    current = replace(candle(minute=5, open="100"), symbol="ETHUSDT")

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        make_executor().fill_entry(long_intent(), current)
```

- [ ] **Step 2: Run the Entry test and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_futures.py::test_entry_rejects_a_candle_from_another_symbol -q
```

Expected: FAIL because a Fill is returned instead of `ValueError`.

- [ ] **Step 3: Write failing Take Profit and Liquidation mismatch tests**

Add:

```python
def test_take_profit_rejects_a_candle_from_another_symbol() -> None:
    current = replace(
        candle(open="105", high="107", low="104"),
        symbol="ETHUSDT",
    )

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        make_executor().fill_take_profit(
            long_basket(entry_price="100", take_profit="106"),
            current,
        )


def test_liquidation_rejects_a_candle_from_another_symbol() -> None:
    current = replace(
        candle(open="70", high="110", low="60"),
        symbol="ETHUSDT",
    )

    with pytest.raises(
        ValueError,
        match="candle symbol must match SymbolRules.symbol",
    ):
        make_executor().fill_liquidation(
            long_basket(entry_price="100", take_profit="106"),
            current,
            liquidation_price=Decimal("80"),
        )
```

- [ ] **Step 4: Run all mismatch tests and verify RED**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/execution/test_paper_futures.py \
  -k "another_symbol" -q
```

Expected: all three tests FAIL because no Futures symbol guard exists.

- [ ] **Step 5: Add the minimal Paper Futures guard**

Change `src/tiewtrade/execution/paper_futures.py`:

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

Place the helper beside `_slippage` and `_exit_fill`; do not change side-aware pricing,
liquidation ordering, quantities, fees or Fill identities.

- [ ] **Step 6: Run Paper Futures tests and verify GREEN**

Run:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest -q \
  tests/unit/execution/test_paper_futures.py \
  tests/unit/application/test_paper_futures_session.py \
  tests/acceptance/test_paper_futures_session.py \
  tests/acceptance/test_paper_futures_trade_history.py
```

Expected: all Paper Futures tests PASS with unchanged valid-symbol behavior.

- [ ] **Step 7: Run the complete verification gate**

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

Expected: all tests and quality gates PASS; no Binance network or Live order is used.

- [ ] **Step 8: Commit Task 3**

```bash
git add \
  src/tiewtrade/execution/paper_futures.py \
  tests/unit/execution/test_paper_futures.py
git commit -m "fix: reject mismatched Paper Futures candles"
```

---

## Final Review Checklist

- [ ] `SymbolRules` rejects `""` and whitespace-only symbol
- [ ] Every `SymbolRules` constructor provides the intended symbol
- [ ] Replay uses `market_data.symbol`, not a duplicate identity literal
- [ ] Spot Entry and Take Profit reject mismatched Candle before calculation
- [ ] Futures Entry, Take Profit and Liquidation reject mismatched Candle before calculation
- [ ] Valid BTCUSDT replay output and Fill identities are unchanged
- [ ] No `exchangeInfo`, Live execution, generic provider or symbol-two support was added
- [ ] Run `code-review` against the branch base and resolve every Critical/Important finding
- [ ] Record RED/GREEN commands and final gate results in the DEV-120 Linear comment
