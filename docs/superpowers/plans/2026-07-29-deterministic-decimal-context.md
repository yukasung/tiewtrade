# Deterministic Decimal Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** กำหนด Decimal arithmetic policy เดียวกันสำหรับ Desktop, Paper Replay และ worker threads พร้อมแปลง Binance Kline timestamp ด้วย integer arithmetic โดยคง deterministic replay output เดิม

**Architecture:** เพิ่ม focused runtime policy module `tiewtrade.decimal_context` ซึ่ง entry point สองตัวเรียกก่อน composition และไม่ผูกกับ Paper/Live ส่วน Binance parser ยังคงเป็นเจ้าของ timestamp validation และใช้ public payload-error boundary เดิม

**Tech Stack:** Python 3.12+, `decimal`, `concurrent.futures`, Pytest, Ruff และ Mypy strict

## Global Constraints

- Decimal policy ต้องใช้ `prec=28`, `ROUND_HALF_EVEN` และเปิด traps สำหรับ `InvalidOperation`, `DivisionByZero`, `Overflow`
- ต้องกำหนดทั้ง `decimal.DefaultContext` สำหรับ threads ที่สร้างภายหลังและ current context ด้วย `decimal.setcontext()`
- `desktop_main.run_desktop()` และ `paper_replay_main.main()` ต้องเรียก configuration ก่อน application/runtime composition
- Binance Kline timestamp ต้องใช้ integer arithmetic และปฏิเสธ milliseconds ที่หาร `1000` ไม่ลงตัว
- public parser ต้องรายงาน malformed timestamp เป็น `BinanceMarketDataPayloadError("invalid Binance market-data payload")`
- ห้ามใช้ float arithmetic กับราคา ปริมาณ PnL indicator หรือ Kline timestamp; float สำหรับ timeout/retry/asyncio duration อยู่นอก scope
- deterministic replay ต้องคง output `{"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"13.84062222"}` แบบตรงทุกตัวอักษร
- ไม่เปลี่ยน Session, Strategy, capital, Basket, execution หรือ persistence behavior
- ใช้ Paper/fake data เท่านั้น ห้ามเรียก Binance private API หรือส่ง Live order

---

### Task 1: กำหนด Decimal policy กลางและเรียกจาก entry points

**Files:**
- Create: `src/tiewtrade/decimal_context.py`
- Modify: `src/tiewtrade/desktop_main.py`
- Modify: `src/tiewtrade/paper_replay_main.py`
- Create: `tests/unit/test_decimal_context.py`
- Modify: `tests/unit/test_desktop_main.py`
- Create: `tests/unit/test_paper_replay_main.py`

**Interfaces:**
- Produces: `configure_decimal_context() -> None`
- Consumes: `desktop_main.run_desktop(database_path: Path | None = None) -> int`
- Consumes: `paper_replay_main.main(argv: Sequence[str] | None = None) -> int`

- [ ] **Step 1: เขียน failing test สำหรับ main thread และ worker thread**

สร้าง `tests/unit/test_decimal_context.py`:

```python
import decimal
from concurrent.futures import ThreadPoolExecutor

from tiewtrade.decimal_context import configure_decimal_context


def _decimal_policy() -> tuple[int, str, bool, bool, bool]:
    context = decimal.getcontext()
    return (
        context.prec,
        context.rounding,
        context.traps[decimal.InvalidOperation],
        context.traps[decimal.DivisionByZero],
        context.traps[decimal.Overflow],
    )


def test_decimal_policy_is_shared_by_current_and_future_worker_threads() -> None:
    decimal.setcontext(decimal.Context(prec=7, rounding=decimal.ROUND_DOWN))

    configure_decimal_context()

    main_policy = _decimal_policy()
    with ThreadPoolExecutor(max_workers=1) as pool:
        worker_policy = pool.submit(_decimal_policy).result()

    assert main_policy == (28, decimal.ROUND_HALF_EVEN, True, True, True)
    assert worker_policy == main_policy
```

- [ ] **Step 2: เขียน failing tests สำหรับ entry-point call order**

เพิ่มใน `tests/unit/test_desktop_main.py` โดยใช้ `raising=False` เพื่อให้ test ล้มด้วย
ลำดับ event ก่อน production import/function มีอยู่:

```python
def test_desktop_configures_decimal_context_before_composition(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    events: list[str] = []
    original_database = desktop_main.SQLiteDatabase

    def capture_database(path: Path) -> object:
        events.append("database")
        return original_database(path)

    monkeypatch.setattr(
        desktop_main,
        "configure_decimal_context",
        lambda: events.append("decimal"),
        raising=False,
    )
    monkeypatch.setattr(desktop_main, "SQLiteDatabase", capture_database)
    monkeypatch.setattr(desktop_main, "run_desktop_ui", lambda **kwargs: 0)

    assert desktop_main.run_desktop(tmp_path / "tiewtrade.sqlite3") == 0
    assert events == ["decimal", "database"]
```

สร้าง `tests/unit/test_paper_replay_main.py`:

```python
import pytest
from pytest import MonkeyPatch

import tiewtrade.paper_replay_main as paper_replay_main


class ParsingStopped(RuntimeError):
    pass


class RecordingParser:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def parse_args(self, argv: object) -> object:
        self._events.append("parse")
        raise ParsingStopped


def test_replay_configures_decimal_context_before_argument_parsing(
    monkeypatch: MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        paper_replay_main,
        "configure_decimal_context",
        lambda: events.append("decimal"),
        raising=False,
    )
    monkeypatch.setattr(
        paper_replay_main,
        "_build_parser",
        lambda: RecordingParser(events),
    )

    with pytest.raises(ParsingStopped):
        paper_replay_main.main([])

    assert events == ["decimal", "parse"]
```

- [ ] **Step 3: รัน tests และตรวจสอบ RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/test_decimal_context.py \
  tests/unit/test_desktop_main.py::test_desktop_configures_decimal_context_before_composition \
  tests/unit/test_paper_replay_main.py -q
```

ผลที่คาดหวัง: context module ยังไม่มี และ entry points ยังไม่เรียก configuration ก่อน
composition/parsing

- [ ] **Step 4: implement Decimal policy ขั้นต่ำ**

สร้าง `src/tiewtrade/decimal_context.py`:

```python
import decimal


def configure_decimal_context() -> None:
    decimal.DefaultContext.prec = 28
    decimal.DefaultContext.rounding = decimal.ROUND_HALF_EVEN
    decimal.DefaultContext.traps[decimal.InvalidOperation] = True
    decimal.DefaultContext.traps[decimal.DivisionByZero] = True
    decimal.DefaultContext.traps[decimal.Overflow] = True
    decimal.DefaultContext.clear_flags()
    decimal.setcontext(decimal.DefaultContext)
```

เพิ่ม import และเรียกเป็น statement แรกของ function body ใน `desktop_main.py`:

```python
from tiewtrade.decimal_context import configure_decimal_context


def run_desktop(database_path: Path | None = None) -> int:
    configure_decimal_context()
    resolved_database_path = database_path or default_database_path()
```

เพิ่ม import และเรียกก่อนสร้าง parser ใน `paper_replay_main.py`:

```python
from tiewtrade.decimal_context import configure_decimal_context


def main(argv: Sequence[str] | None = None) -> int:
    configure_decimal_context()
    arguments = _build_parser().parse_args(argv)
```

- [ ] **Step 5: รัน tests และตรวจสอบ GREEN**

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest \
  tests/unit/test_decimal_context.py \
  tests/unit/test_desktop_main.py \
  tests/unit/test_paper_replay_main.py \
  tests/acceptance/test_paper_replay_cli.py -q
```

ผลที่คาดหวัง: tests ผ่าน และ CLI replay output คงเดิม

- [ ] **Step 6: รัน static checks สำหรับ Task 1**

```bash
../../.venv/bin/python -m ruff check \
  src/tiewtrade/decimal_context.py \
  src/tiewtrade/desktop_main.py \
  src/tiewtrade/paper_replay_main.py \
  tests/unit/test_decimal_context.py \
  tests/unit/test_desktop_main.py \
  tests/unit/test_paper_replay_main.py
../../.venv/bin/python -m ruff format --check \
  src/tiewtrade/decimal_context.py \
  src/tiewtrade/desktop_main.py \
  src/tiewtrade/paper_replay_main.py \
  tests/unit/test_decimal_context.py \
  tests/unit/test_desktop_main.py \
  tests/unit/test_paper_replay_main.py
PYTHONPATH=src ../../.venv/bin/python -m mypy src
git diff --check
```

ผลที่คาดหวัง: ทุก check ผ่าน

- [ ] **Step 7: commit Task 1**

```bash
git add \
  src/tiewtrade/decimal_context.py \
  src/tiewtrade/desktop_main.py \
  src/tiewtrade/paper_replay_main.py \
  tests/unit/test_decimal_context.py \
  tests/unit/test_desktop_main.py \
  tests/unit/test_paper_replay_main.py
git commit -m "fix: pin decimal context at startup"
```

### Task 2: ปฏิเสธ Kline timestamp ที่มีเศษด้วย integer arithmetic

**Files:**
- Modify: `src/tiewtrade/integrations/binance/kline_parser.py`
- Modify: `tests/unit/integrations/binance/test_kline_parser.py`

**Interfaces:**
- Consumes: `parse_rest_kline(payload: object, config: MarketDataConfig) -> Candle`
- Preserves: `BinanceMarketDataPayloadError("invalid Binance market-data payload")`
- Internal: `_utc_datetime(milliseconds: int) -> datetime`

- [ ] **Step 1: เขียน failing parser-boundary test**

เพิ่มใน `tests/unit/integrations/binance/test_kline_parser.py`:

```python
def test_rest_kline_rejects_timestamp_with_subsecond_remainder() -> None:
    with pytest.raises(
        BinanceMarketDataPayloadError,
        match="invalid Binance",
    ) as captured:
        parse_rest_kline(
            [1767225600001, "100.10", "102.20", "99.90", "101.30", "12.50"],
            config(),
        )

    assert isinstance(captured.value.__cause__, ValueError)
    assert str(captured.value.__cause__) == (
        "timestamp milliseconds must align to a whole second"
    )
```

- [ ] **Step 2: รัน test และตรวจสอบ RED**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/binance/test_kline_parser.py::test_rest_kline_rejects_timestamp_with_subsecond_remainder -q
```

ผลที่คาดหวัง: public error type ถูกต้องอยู่แล้ว แต่ cause เดิมมาจาก `Candle` และมีข้อความ
`open_time must align to a minute` แทน parser timestamp validation

- [ ] **Step 3: implement integer timestamp validation ขั้นต่ำ**

แทน `_utc_datetime()` ด้วย:

```python
def _utc_datetime(milliseconds: int) -> datetime:
    seconds, remainder = divmod(milliseconds, 1000)
    if remainder:
        raise ValueError("timestamp milliseconds must align to a whole second")
    return datetime.fromtimestamp(seconds, tz=UTC)
```

- [ ] **Step 4: รัน parser และ deterministic replay tests**

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/binance/test_kline_parser.py \
  tests/acceptance/test_paper_spot_replay.py \
  tests/acceptance/test_paper_replay_cli.py -q
```

ผลที่คาดหวัง: parser tests ผ่าน และ replay JSON ยังตรงกับค่าเดิมทุกตัวอักษร

- [ ] **Step 5: ตรวจว่าไม่มี float conversion ใน financial/Kline paths**

```bash
rg -n "milliseconds / 1000|float\(" \
  src/tiewtrade/integrations/binance \
  src/tiewtrade/trading \
  src/tiewtrade/execution \
  src/tiewtrade/strategies \
  src/tiewtrade/replay
```

ผลที่คาดหวัง: ไม่พบ match; timeout/retry floats ใน `market_data/runtime.py` อยู่นอก
financial/Kline scope ตาม design

- [ ] **Step 6: รัน full verification gates**

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest -q
../../.venv/bin/python -m ruff check src tests
../../.venv/bin/python -m ruff format --check src tests
PYTHONPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

ผลที่คาดหวัง: ทุก gate ผ่านและ deterministic replay output ไม่เปลี่ยน

- [ ] **Step 7: commit Task 2**

```bash
git add \
  src/tiewtrade/integrations/binance/kline_parser.py \
  tests/unit/integrations/binance/test_kline_parser.py
git commit -m "fix: parse Binance timestamps without float"
```
