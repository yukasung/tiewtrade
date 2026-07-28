# Paper Spot Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ transition ของ Paper Spot Entry เป็น atomic, fail closed เมื่อ execution invariant ล้มเหลว, ผูก persistence เข้ากับ Session identity แบบ immutable, สร้าง close snapshot แยกต่อ Candle และปฏิเสธ capital ที่ไม่เป็น finite โดยไม่เปลี่ยน deterministic replay output

**Architecture:** คง `PaperSpotSession` ให้แยกจาก `PaperFuturesSession` พร้อมนำ candidate-copy และ fail-closed patterns ที่พิสูจน์แล้วจาก Futures มาใช้ Application เป็นเจ้าของ Session orchestration และ identity; SQLite integration ตรวจสอบ identity และ snapshot invariants; ส่วน shared `trading` capital policy ตรวจสอบ input ที่ boundary ของตน

**Tech Stack:** Python 3.12, immutable dataclasses, `Decimal`, Pytest, Ruff, Mypy และ SQLite integration adapters

## Global Constraints

- คง Paper Spot และ Paper Futures เป็น application orchestrators ที่แยกจากกัน ห้ามสร้าง shared base class, generic interface, registry หรือ factory
- Paper และ Live ยังคงใช้ business policies ร่วมกัน แต่ห้ามใช้ execution adapters ร่วมกัน
- การเปลี่ยน production behavior ต้องใช้ TDD แบบ failing-test-first
- Whole-Candle commit ใช้ candidate copies ของ Basket, Entry Pair lifecycle, Strategy, Indicator state, pending intent และ counters; original objects ต้องไม่รับ partial mutation จาก accepted Candle ที่ล้มเหลว
- Session identity ประกอบด้วย `session_id`, `symbol`, `timeframe` และ `preset_version` เท่านั้น
- Paper Spot execution ที่ล้มเหลวต้องเข้าสู่ terminal `FAILED_CLOSED`, ล้าง pending intent และปฏิเสธ Candles ถัดไป
- `take_profit_fill` และ `closed_basket` ต้องมีทั้งคู่เฉพาะ Candle ที่ปิด Basket และต้องไม่มีทั้งคู่ในกรณีอื่น
- Deterministic 40-Candle replay output ต้องคงเป็น `{"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"13.84062222"}` แบบตรงทุกตัวอักษร
- ใช้เฉพาะ Paper และ fake objects ห้ามเรียก Binance private APIs หรือส่ง Live orders

---

### Task 1: ปฏิเสธ Paper Spot capital ที่ไม่เป็น finite

**Files:**
- Modify: `src/tiewtrade/trading/capital.py`
- Test: `tests/unit/trading/test_capital.py`

**Interfaces:**
- Consumes: `SpotCapitalPlan.from_available(available: Decimal, spot_policy: SpotTradingPolicy, entry_policy: EntryPolicy) -> SpotCapitalPlan`
- Produces: public method เดิมซึ่งต้อง raise `ValueError("available capital must be finite and positive")` เมื่อ input ไม่เป็น finite หรือไม่เป็นค่าบวก

- [ ] **Step 1: เขียน failing parameterized test**

แทนที่ Spot test ที่ตรวจเฉพาะศูนย์ด้วย invalid-input contract ที่ครบถ้วน:

```python
@pytest.mark.parametrize(
    "available",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_spot_capital_plan_rejects_invalid_available_capital(
    available: Decimal,
) -> None:
    with pytest.raises(ValueError, match="available capital"):
        SpotCapitalPlan.from_available(
            available,
            SpotTradingPolicy(trading_capital_ratio=Decimal("0.80")),
            EntryPolicy(max_entries=10),
        )
```

- [ ] **Step 2: รัน test และตรวจสอบ RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/trading/test_capital.py::test_spot_capital_plan_rejects_invalid_available_capital -q
```

ผลที่คาดหวัง: `NaN` เกิด error เป็น `decimal.InvalidOperation` หรือกรณี Infinity ไม่ raise `ValueError` ที่กำหนด

- [ ] **Step 3: implement boundary validation ขั้นต่ำ**

แก้ `SpotCapitalPlan.from_available()` เป็น:

```python
if not available.is_finite() or available <= 0:
    raise ValueError("available capital must be finite and positive")
```

คง allocation calculations ทั้งหมดไว้โดยไม่เปลี่ยนแปลง

- [ ] **Step 4: ตรวจสอบ GREEN และ capital module**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest tests/unit/trading/test_capital.py -q
```

ผลที่คาดหวัง: capital tests ทั้งหมดผ่าน

- [ ] **Step 5: สร้าง commit**

```bash
git add src/tiewtrade/trading/capital.py tests/unit/trading/test_capital.py
git commit -m "fix: validate Paper Spot capital boundary"
```

### Task 2: ผูก Paper Spot persistence เข้ากับ Session identity แบบ immutable

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `src/tiewtrade/integrations/sqlite/paper_spot_history.py`
- Modify: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Test: `tests/unit/application/test_paper_spot_session.py`
- Test: `tests/unit/integrations/sqlite/test_paper_spot_history.py`
- Test: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`

**Interfaces:**
- Produces: `PaperSpotSessionIdentity(session_id: UUID, symbol: str, timeframe: str, preset_version: str)` แบบ immutable
- Produces: `PaperSpotSession.identity -> PaperSpotSessionIdentity`
- Produces: `PaperSpotHistoryContext.session_identity -> PaperSpotSessionIdentity` และ `PaperSpotSQLiteHistory.session_identity -> PaperSpotSessionIdentity`
- Consumes: `PersistentPaperSpotSQLiteSession` เปรียบเทียบ `session.identity` กับ `history.session_identity` ก่อนเก็บ dependency ทั้งสอง

- [ ] **Step 1: เขียน failing identity exposure tests**

เพิ่ม application import และ test:

```python
from tiewtrade.application.paper_spot_session import (
    PaperSpotSession,
    PaperSpotSessionIdentity,
)


def test_session_exposes_immutable_persistence_identity() -> None:
    application = paper_session()

    assert application.identity == PaperSpotSessionIdentity(
        session_id=UUID("00000000-0000-0000-0000-000000000079"),
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )
```

ใน `test_paper_spot_history.py` ให้ใช้ `history` fixture เดิมและเพิ่ม:

```python
def test_history_exposes_session_identity(
    history: PaperSpotSQLiteHistory,
) -> None:
    assert history.session_identity == PaperSpotSessionIdentity(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )
```

เพิ่มเฉพาะ import `PaperSpotSessionIdentity` ที่ยังขาด โดย history fixture และ import
`PaperSpotSQLiteHistory` มีอยู่แล้ว

- [ ] **Step 2: เขียน failing persistence mismatch test**

เพิ่ม identity helper และ mismatch test ที่เจาะจง:

```python
def session_identity() -> PaperSpotSessionIdentity:
    return PaperSpotSessionIdentity(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
    )


def test_constructor_rejects_mismatched_session_and_history_identity() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = replace(  # type: ignore[misc]
        session_identity(),
        timeframe="15m",
    )

    with pytest.raises(ValueError, match="identity"):
        PersistentPaperSpotSQLiteSession(session, history)
```

เพิ่ม `replace` ใน dataclasses import และเพิ่ม helper นี้สำหรับ mock-based constructor
calls ที่มีอยู่ทั้งหมด:

```python
def persistent_session(
    session: PaperSpotSession,
    history: PaperSpotSQLiteHistory,
) -> PersistentPaperSpotSQLiteSession:
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = session_identity()  # type: ignore[misc]
    return PersistentPaperSpotSQLiteSession(session, history)
```

แทน direct mock-based calls ของ `PersistentPaperSpotSQLiteSession(session, history)`
ที่มีอยู่ด้วย `persistent_session(session, history)` เพื่อให้ tests เหล่านั้นผ่าน boundary
ใหม่อย่างชัดเจน

- [ ] **Step 3: รัน identity tests และตรวจสอบ RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_session_exposes_immutable_persistence_identity \
  tests/unit/integrations/sqlite/test_paper_spot_history.py::test_history_exposes_session_identity \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_constructor_rejects_mismatched_session_and_history_identity -q
```

ผลที่คาดหวัง: imports/properties ยังไม่มี หรือ mismatch constructor ไม่ raise

- [ ] **Step 4: implement immutable identity contracts**

ใน `paper_spot_session.py` ให้เพิ่ม:

```python
@dataclass(frozen=True, slots=True)
class PaperSpotSessionIdentity:
    session_id: UUID
    symbol: str
    timeframe: str
    preset_version: str
```

บันทึก identity เป็น snapshot ใน `PaperSpotSession.__init__`:

```python
self._identity = PaperSpotSessionIdentity(
    session_id=session.session_id,
    symbol=market_data.symbol,
    timeframe=market_data.timeframe,
    preset_version=session.preset_version,
)
```

เปิดให้อ่านแบบ read-only:

```python
@property
def identity(self) -> PaperSpotSessionIdentity:
    return self._identity
```

ใน `paper_spot_history.py` ให้เพิ่ม application identity import และ properties:

```python
@property
def session_identity(self) -> PaperSpotSessionIdentity:
    return PaperSpotSessionIdentity(
        session_id=self.session_id,
        symbol=self.symbol,
        timeframe=self.timeframe,
        preset_version=self.preset_version,
    )
```

บน `PaperSpotHistoryContext` และ:

```python
@property
def session_identity(self) -> PaperSpotSessionIdentity:
    return self._context.session_identity
```

บน `PaperSpotSQLiteHistory`

ใน persistent constructor ให้ validate ก่อน assignment:

```python
if session.identity != history.session_identity:
    raise ValueError("Paper Spot Session and Trade History identity differ")
```

- [ ] **Step 5: ตรวจสอบ GREEN และ Spot persistence tests ทั้งหมด**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/acceptance/test_paper_spot_trade_history.py -q
```

ผลที่คาดหวัง: selected tests ทั้งหมดผ่าน

- [ ] **Step 6: สร้าง commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  src/tiewtrade/integrations/sqlite/paper_spot_history.py \
  src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_paper_spot_history.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py
git commit -m "feat: bind Paper Spot persistence identity"
```

### Task 3: ทำให้ Paper Spot Entry เป็น atomic และ fail closed

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Test: `tests/unit/application/test_paper_spot_session.py`
- Test: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`

**Interfaces:**
- Produces: `PaperSpotSessionState` พร้อม `ACTIVE` และ `FAILED_CLOSED`
- Produces: `PaperSpotFailureReason.EXECUTION_ERROR` และ `PaperSpotSessionError`
- Produces: `PaperSpotSession.snapshot -> PaperSpotSessionSnapshot`
- Changes: `PaperSpotSessionSnapshot` เพิ่ม fields `state` และ `failure_reason` ที่จำเป็น
- Preserves: minimum-notional rejection ต้อง re-arm Strategy และไม่นับเป็น failure

- [ ] **Step 1: เขียน failing atomicity และ failure-cause test**

เพิ่ม imports สำหรับ `EntryPairLifecycle` และ contracts ใหม่ แล้วเพิ่ม:

```python
def test_entry_transition_is_atomic_when_lifecycle_rejects_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent),
        open_price="120",
        close_price="121",
    )
    first_fill = application.process_completed_candle(
        first_fill_candle,
        received_at=first_fill_candle.close_time,
    )
    assert first_fill.basket_entry_count == 1

    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    second_fill_candle = candle(
        minute_after(second_intent),
        open_price="100",
        close_price="101",
    )

    def reject_fill(self: EntryPairLifecycle, filled_at: datetime) -> None:
        raise ValueError("entry is blocked by pair lifecycle")

    monkeypatch.setattr(EntryPairLifecycle, "record_fill", reject_fill)

    with pytest.raises(PaperSpotSessionError, match="execution failed") as captured:
        application.process_completed_candle(
            second_fill_candle,
            received_at=second_fill_candle.close_time,
        )

    assert isinstance(captured.value.__cause__, ValueError)
    assert str(captured.value.__cause__) == "entry is blocked by pair lifecycle"
    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.failure_reason is PaperSpotFailureReason.EXECUTION_ERROR
    assert application.snapshot.pending_intent is None
    assert application.snapshot.basket_entry_count == 1
    assert application._lifecycle.entry_count == 1
```

- [ ] **Step 2: เขียน failing tests สำหรับ terminal rejection และ warm-up**

เพิ่ม:

```python
def test_failed_closed_session_rejects_later_candles_and_warm_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    failed_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )

    def raise_execution_error(*args: object, **kwargs: object) -> None:
        raise ValueError("broken execution invariant")

    monkeypatch.setattr(application._executor, "fill_entry", raise_execution_error)
    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        application.process_completed_candle(
            failed_candle,
            received_at=failed_candle.close_time,
        )

    before = application.snapshot
    following = candle(
        minute_after(pending) + 5,
        open_price="121",
        close_price="122",
    )
    after = application.process_completed_candle(
        following,
        received_at=following.close_time,
    )

    assert after.accepted is False
    assert after.state is before.state
    assert after.basket_id == before.basket_id
    assert after.basket_entry_count == before.basket_entry_count
    with pytest.raises(PaperSpotSessionError, match="not active"):
        application.warm_up_completed_candles(
            [following],
            received_at=following.close_time,
        )
```

- [ ] **Step 3: รัน focused tests และตรวจสอบ RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_entry_transition_is_atomic_when_lifecycle_rejects_fill \
  tests/unit/application/test_paper_spot_session.py::test_failed_closed_session_rejects_later_candles_and_warm_up -q
```

ผลที่คาดหวัง: contracts ใหม่ยังไม่มี และ/หรือยังเหลือ partial Basket mutation

- [ ] **Step 4: เพิ่ม Spot-specific state และ snapshot contracts**

เพิ่ม imports `deepcopy` และ `StrEnum` แล้วกำหนด:

```python
class PaperSpotSessionState(StrEnum):
    ACTIVE = "active"
    FAILED_CLOSED = "failed_closed"


class PaperSpotFailureReason(StrEnum):
    EXECUTION_ERROR = "execution_error"


class PaperSpotSessionError(RuntimeError):
    """Paper Spot stopped because an execution invariant failed."""
```

เพิ่ม fields ที่จำเป็นต่อไปนี้ใน `PaperSpotSessionSnapshot`:

```python
state: PaperSpotSessionState
failure_reason: PaperSpotFailureReason | None
```

กำหนดค่าเริ่มต้นของ state ใน Session:

```python
self._state = PaperSpotSessionState.ACTIVE
self._failure_reason: PaperSpotFailureReason | None = None
```

เปิดให้ใช้งาน snapshot:

```python
@property
def snapshot(self) -> PaperSpotSessionSnapshot:
    return self._snapshot(accepted=self._state is PaperSpotSessionState.ACTIVE)
```

ส่ง `state=self._state` และ `failure_reason=self._failure_reason` เมื่อสร้าง snapshot
ทุกครั้ง และแก้ direct `PaperSpotSessionSnapshot` fixtures ใน persistent-session tests
ด้วย:

```python
state=PaperSpotSessionState.ACTIVE,
failure_reason=None,
```

- [ ] **Step 5: เพิ่ม fail-closed execution boundary**

ที่จุดเริ่มของ `process_completed_candle()`:

```python
if self._state is not PaperSpotSessionState.ACTIVE:
    return self._snapshot(accepted=False)
```

คง completed-candle acceptance ไว้นอก execution `try` และครอบ orchestration หลังจากนั้น
ทั้งหมด:

```python
try:
    # existing Entry, Take Profit, indicator, and Strategy flow
except PaperSpotSessionError:
    raise
except Exception as error:
    self._fail_closed()
    raise PaperSpotSessionError("Paper Spot execution failed") from error
```

ป้องกัน warm-up ก่อน iteration:

```python
if self._state is not PaperSpotSessionState.ACTIVE:
    raise PaperSpotSessionError("Paper Spot session is not active")
```

เพิ่ม:

```python
def _fail_closed(self) -> None:
    self._state = PaperSpotSessionState.FAILED_CLOSED
    self._failure_reason = PaperSpotFailureReason.EXECUTION_ERROR
    self._pending_intent = None
    self._strategy = RsiStepGridStrategy(self._session.session_id, self._preset)
```

- [ ] **Step 6: implement candidate-copy Entry commit**

แทน successful Fill mutation block ด้วย:

```python
intent = self._pending_intent
fill = self._executor.fill_entry(intent, candle)
if fill is None:
    self._strategy.on_entry_rejected(intent.intent_id)
    self._pending_intent = None
    return None

if self._basket is None:
    basket_id = uuid5(
        self._session.session_id,
        f"basket:{self._closed_basket_count + 1}",
    )
    candidate_basket = Basket(
        basket_id,
        self._session.entry_policy,
        self._preset.take_profit_atr_multiplier,
    )
else:
    candidate_basket = deepcopy(self._basket)
candidate_lifecycle = deepcopy(self._lifecycle)
candidate_strategy = deepcopy(self._strategy)

candidate_basket.add_entry(
    price=fill.price,
    quantity=fill.quantity,
    fee=fill.fee,
    filled_at=fill.filled_at,
    atr=intent.atr,
    tick_size=self._symbol_rules.tick_size,
)
candidate_lifecycle.record_fill(fill.filled_at)
candidate_strategy.on_entry_filled(intent.intent_id)

self._basket = candidate_basket
self._lifecycle = candidate_lifecycle
self._strategy = candidate_strategy
self._pending_intent = None
return fill
```

- [ ] **Step 7: ตรวจสอบ GREEN และ Spot Session integration**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/acceptance/test_paper_spot_replay.py \
  tests/acceptance/test_paper_spot_trade_history.py -q
```

ผลที่คาดหวัง: selected tests ทั้งหมดผ่านและ replay output ไม่เปลี่ยนแปลง

- [ ] **Step 8: สร้าง commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py
git commit -m "fix: make Paper Spot entry fail closed atomically"
```

### Task 4: ทำให้ Paper Spot close snapshots แยกต่อ Candle และปลอดภัยตาม invariant

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- Test: `tests/unit/application/test_paper_spot_session.py`
- Test: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`
- Test: `tests/acceptance/test_paper_spot_replay.py`

**Interfaces:**
- Preserves: คงชื่อ `PaperSpotSessionSnapshot.take_profit_fill` สำหรับ consumers เดิม
- Changes: `take_profit_fill` และ `closed_basket` อธิบายเฉพาะ Candle ปัจจุบัน
- Strengthens: persistent close ต้องมีทั้งสอง fields และ Basket IDs ต้องตรงกัน

- [ ] **Step 1: เขียน failing non-sticky snapshot test**

ใน multi-Basket test เดิม ให้เปลี่ยน assertion หลัง Basket Entry ถัดไปจาก:

```python
assert new_fill.take_profit_fill is not None
```

เป็น:

```python
assert new_fill.take_profit_fill is None
assert new_fill.closed_basket is None
```

ส่วนนี้ใช้ flow เดิมที่ปิด Basket หนึ่งแล้วประมวลผล Candles ถัดมา เพื่อพิสูจน์ว่า
`_latest_take_profit_fill` เดิมไม่รั่วไปยัง snapshot ถัดไปอีก

เพิ่มความเข้มงวดให้ `test_replaying_the_tracer_fixture_is_deterministic()` ด้วย stable
serialization contract แบบตรงทุกตัวอักษร:

```python
assert first.to_json() == (
    '{"accepted_candles":40,"closed_baskets":1,'
    '"current_entries":0,"realized_pnl":"13.84062222"}'
)
```

- [ ] **Step 2: เขียน failing persistent snapshot invariant tests**

เพิ่ม:

```python
def test_take_profit_fill_without_closed_basket_blocks_persistence() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = replace(
        entry_snapshot(),
        entry_fill=None,
        take_profit_fill=exit_fill(),
        closed_basket=None,
    )
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="present together"):
        persistent.process_completed_candle(candle, received_at=candle.close_time)

    history.record_close.assert_not_called()


def test_closed_basket_with_mismatched_snapshot_basket_id_blocks_persistence() -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.process_completed_candle.return_value = replace(
        close_snapshot(),
        basket_id=UUID("00000000-0000-0000-0000-000000000199"),
    )
    persistent = persistent_session(session, history)
    candle = completed_candle()

    with pytest.raises(ValueError, match="matching Basket ID"):
        persistent.process_completed_candle(candle, received_at=candle.close_time)

    history.record_close.assert_not_called()
```

- [ ] **Step 3: รัน focused tests และตรวจสอบ RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_closed_two_entry_basket_resets_lifecycle_for_a_new_basket \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_take_profit_fill_without_closed_basket_blocks_persistence \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_closed_basket_with_mismatched_snapshot_basket_id_blocks_persistence -q
```

ผลที่คาดหวัง: snapshot ถัดมายังมี Fill เดิม และ persistent pair/identity checks ยังไม่
raise ครบทุกกรณี

- [ ] **Step 4: ทำให้ Take Profit Fill เป็น local Candle result**

ลบ `_latest_take_profit_fill` และเปลี่ยน processing flow เป็น:

```python
take_profit_fill: PaperSpotExitFill | None = None
closed_basket: ClosedBasket | None = None
if basket_existed_at_candle_open and not entry_filled_on_current_candle:
    take_profit_fill = self._fill_take_profit(candle)
    if take_profit_fill is not None:
        closed_basket = self._close_basket(take_profit_fill)
```

เปลี่ยน `_fill_take_profit()` ให้คืน executor result โดยไม่มี mutation:

```python
def _fill_take_profit(self, candle: Candle) -> PaperSpotExitFill | None:
    assert self._basket is not None
    return self._executor.fill_take_profit(self._basket, candle)
```

ย้าย close mutation เข้าไปใน:

```python
def _close_basket(self, exit_fill: PaperSpotExitFill) -> ClosedBasket:
    assert self._basket is not None
    closed = self._basket.close(
        exit_price=exit_fill.price,
        exit_fee=exit_fill.fee,
        closed_at=exit_fill.filled_at,
    )
    self._basket = None
    self._lifecycle.reset()
    self._closed_basket_count += 1
    return closed
```

เพิ่ม `take_profit_fill: PaperSpotExitFill | None = None` ใน `_snapshot()` และส่ง local
value จาก `process_completed_candle()` สร้าง snapshots ด้วย parameter นี้เท่านั้น ห้ามใช้
previous Fill ที่เก็บไว้

- [ ] **Step 5: บังคับ persistent pair และ Basket ID contract**

แทน close branch ใน `_record_snapshot()` ด้วย:

```python
if snapshot.take_profit_fill is None and snapshot.closed_basket is None:
    return
if snapshot.take_profit_fill is None or snapshot.closed_basket is None:
    raise ValueError("Take Profit Fill and closed Basket must be present together")
if snapshot.basket_id != snapshot.closed_basket.basket_id:
    raise ValueError("closed Basket requires a matching Basket ID")
self._history.record_close(
    basket_id=snapshot.closed_basket.basket_id,
    fill=snapshot.take_profit_fill,
    closed=snapshot.closed_basket,
)
```

- [ ] **Step 6: ตรวจสอบ GREEN, deterministic replay และ repository gates ทั้งหมด**

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

ผลที่คาดหวัง: commands ทั้งหมด exit `0`; replay assertion ยังคงตรงกับ JSON ใน
Global Constraint ทุกตัวอักษร

- [ ] **Step 7: สร้าง commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/acceptance/test_paper_spot_replay.py
git commit -m "fix: scope Paper Spot close snapshots per Candle"
```

### Task 5: ขยาย atomicity ให้ครอบคลุม accepted Candle ทั้งแท่งและแก้ review findings

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `tests/unit/application/test_paper_spot_session.py`
- Modify: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`
- Modify: `docs/superpowers/plans/2026-07-28-paper-spot-hardening.md`

**Interfaces:**
- Produces: private `_PaperSpotTransition` ที่เป็นเจ้าของ candidate Basket, lifecycle,
  Strategy, Indicator, pending intent และ closed-Basket count สำหรับ accepted Candle หนึ่งแท่ง
- Changes: `PaperSpotSession` commit candidate state หลังจาก Entry, Take Profit,
  Indicator และ Strategy steps สำเร็จทั้งหมดเท่านั้น
- Preserves: คง public Session, snapshot, identity, persistence, replay และ fail-closed
  contracts จาก Tasks 1–4

- [ ] **Step 1: เขียน failing late-Entry และ late-close durability tests**

เพิ่ม helper ที่สร้าง persistent coordinator จาก real Session กับ mock History โดยกำหนด
identity ให้ตรงกัน:

```python
def persistent_spot_session(
    application: PaperSpotSession,
) -> tuple[PersistentPaperSpotSQLiteSession, PaperSpotSQLiteHistory]:
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    history.session_identity = application.identity  # type: ignore[misc]
    return PersistentPaperSpotSQLiteSession(application, history), history
```

เพิ่ม test ที่ทำให้ Indicator ล้มหลัง Entry Fill candidate ถูกสร้างแล้ว:

```python
def test_late_entry_failure_does_not_commit_or_persist_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    persistent, history = persistent_spot_session(application)
    entry_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )

    def raise_indicator_error(*args: object, **kwargs: object) -> None:
        raise ValueError("indicator transition failed")

    monkeypatch.setattr(WilderIndicators, "update", raise_indicator_error)

    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        persistent.process_completed_candle(
            entry_candle,
            received_at=entry_candle.close_time,
        )

    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.basket_id is None
    assert application.snapshot.basket_entry_count == 0
    history.record_entry.assert_not_called()
    history.record_close.assert_not_called()
```

เพิ่ม test ที่บันทึก Entry สำเร็จก่อน แล้วทำให้ Indicator ล้มหลัง candidate Basket close:

```python
def test_late_close_failure_keeps_open_basket_and_does_not_persist_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    pending = arm_entry_intent(application)
    persistent, history = persistent_spot_session(application)
    entry_candle = candle(
        minute_after(pending),
        open_price="120",
        close_price="121",
    )
    entry = persistent.process_completed_candle(
        entry_candle,
        received_at=entry_candle.close_time,
    )
    assert entry.session.basket_entry_count == 1

    def raise_indicator_error(*args: object, **kwargs: object) -> None:
        raise ValueError("indicator transition failed after close")

    monkeypatch.setattr(WilderIndicators, "update", raise_indicator_error)
    close_candle = candle(
        minute_after(pending) + 5,
        open_price="125",
        close_price="130",
        high="1000",
    )

    with pytest.raises(PaperSpotSessionError, match="execution failed"):
        persistent.process_completed_candle(
            close_candle,
            received_at=close_candle.close_time,
        )

    assert application.snapshot.state is PaperSpotSessionState.FAILED_CLOSED
    assert application.snapshot.basket_id == entry.session.basket_id
    assert application.snapshot.basket_entry_count == 1
    history.record_entry.assert_called_once()
    history.record_close.assert_not_called()
```

เพิ่ม imports สำหรับ `create_autospec`, `WilderIndicators`, `PaperSpotSQLiteHistory` และ
`PersistentPaperSpotSQLiteSession` ใน test file เดียวกัน

- [ ] **Step 2: เขียน failing Strategy-candidate rollback regression**

เพิ่ม test ที่ callback บน candidate Strategy mutate ก่อน raise:

```python
def test_strategy_callback_failure_does_not_commit_candidate_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = paper_session()
    first_intent = arm_entry_intent(application)
    first_fill_candle = candle(
        minute_after(first_intent),
        open_price="120",
        close_price="121",
    )
    application.process_completed_candle(
        first_fill_candle,
        received_at=first_fill_candle.close_time,
    )
    second_intent = arm_entry_intent(
        application,
        start_minute=minute_after(first_intent) + 5,
        downtrend_candles=60,
    )
    original_strategy = application._strategy
    original_callback = RsiStepGridStrategy.on_entry_filled

    def mutate_then_raise(
        self: RsiStepGridStrategy,
        intent_id: str,
    ) -> None:
        original_callback(self, intent_id)
        raise ValueError("strategy transition failed")

    monkeypatch.setattr(RsiStepGridStrategy, "on_entry_filled", mutate_then_raise)
    second_fill_candle = candle(
        minute_after(second_intent),
        open_price="100",
        close_price="101",
    )

    with pytest.raises(PaperSpotSessionError) as captured:
        application.process_completed_candle(
            second_fill_candle,
            received_at=second_fill_candle.close_time,
        )

    assert str(captured.value.__cause__) == "strategy transition failed"
    assert application.snapshot.basket_entry_count == 1
    assert application._lifecycle.entry_count == 1
    assert original_strategy._pending_intent == second_intent
    assert application._strategy is not original_strategy
```

- [ ] **Step 3: ทำ identity mismatch coverage แบบ parameterized สำหรับทั้งสี่ fields**

แทน test mismatch เดิมด้วย:

```python
@pytest.mark.parametrize(
    "mismatched_identity",
    [
        replace(
            session_identity(),
            session_id=UUID("00000000-0000-0000-0000-000000000199"),
        ),
        replace(session_identity(), symbol="ETHUSDT"),
        replace(session_identity(), timeframe="15m"),
        replace(session_identity(), preset_version="rsi-step-grid-v2"),
    ],
)
def test_constructor_rejects_mismatched_session_and_history_identity(
    mismatched_identity: PaperSpotSessionIdentity,
) -> None:
    session = create_autospec(PaperSpotSession, instance=True)
    history = create_autospec(PaperSpotSQLiteHistory, instance=True)
    session.identity = session_identity()  # type: ignore[misc]
    history.session_identity = mismatched_identity  # type: ignore[misc]

    with pytest.raises(
        ValueError,
        match="Paper Spot Session and Trade History identity differ",
    ):
        PersistentPaperSpotSQLiteSession(session, history)
```

- [ ] **Step 4: รัน focused tests และตรวจสอบ RED**

รัน:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_session.py::test_late_entry_failure_does_not_commit_or_persist_entry \
  tests/unit/application/test_paper_spot_session.py::test_late_close_failure_keeps_open_basket_and_does_not_persist_close \
  tests/unit/application/test_paper_spot_session.py::test_strategy_callback_failure_does_not_commit_candidate_transition \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py::test_constructor_rejects_mismatched_session_and_history_identity -q
```

ผลที่คาดหวัง: late Entry/close tests แสดงว่า state จริงถูก mutate ก่อน error; Strategy test
หรือ identity matrix ยังไม่ผ่าน contract ใหม่ทั้งหมด

- [ ] **Step 5: เพิ่ม whole-Candle candidate state**

เพิ่ม private mutable dataclass ใน `paper_spot_session.py`:

```python
@dataclass(slots=True)
class _PaperSpotTransition:
    indicators: WilderIndicators
    strategy: RsiStepGridStrategy
    lifecycle: EntryPairLifecycle
    basket: Basket | None
    pending_intent: EntryIntent | None
    closed_basket_count: int
```

สร้าง candidate จาก state เดิม:

```python
def _new_transition(self) -> _PaperSpotTransition:
    return _PaperSpotTransition(
        indicators=deepcopy(self._indicators),
        strategy=deepcopy(self._strategy),
        lifecycle=deepcopy(self._lifecycle),
        basket=deepcopy(self._basket),
        pending_intent=self._pending_intent,
        closed_basket_count=self._closed_basket_count,
    )
```

และ commit พร้อมกันหลังทุก fallible step สำเร็จ:

```python
def _commit_transition(self, transition: _PaperSpotTransition) -> None:
    self._indicators = transition.indicators
    self._strategy = transition.strategy
    self._lifecycle = transition.lifecycle
    self._basket = transition.basket
    self._pending_intent = transition.pending_intent
    self._closed_basket_count = transition.closed_basket_count
```

- [ ] **Step 6: ทำ accepted-Candle behavior ทั้งหมดบน candidate**

หลัง Candle acceptance ให้สร้าง `transition = self._new_transition()` แล้วเปลี่ยน private
helpers ให้รับ transition เป็น argument:

```python
entry_fill = self._fill_pending_intent(transition, candle)
take_profit_fill = self._fill_take_profit(transition, candle)
closed_basket = self._close_basket(transition, take_profit_fill)
indicators = transition.indicators.update(candle)
self._evaluate_strategy(transition, candle, indicators)
self._commit_transition(transition)
```

`_fill_pending_intent()` ต้อง mutate `transition.basket`, `transition.lifecycle`,
`transition.strategy` และ `transition.pending_intent` โดยตรง และลบ candidate-copy ชั้นใน
ที่ซ้ำซ้อนจาก Task 3

`_fill_take_profit()`, `_close_basket()` และ Strategy evaluation ต้องอ่าน/เขียน state
ผ่าน transition เท่านั้น โดยเพิ่ม `transition.closed_basket_count` เมื่อ close สำเร็จ

`_commit_transition()` ต้องถูกเรียกหลัง Indicator/Strategy step และก่อนสร้าง success
snapshot เท่านั้น หาก exception เกิดก่อนหน้านั้นให้ใช้ fail-closed boundary เดิมโดยไม่
commit candidate

- [ ] **Step 7: แปล implementation-plan prose เป็นภาษาไทย**

แปล narrative, instructions, expected results และ explanatory text ในไฟล์แผนนี้เป็น
ภาษาไทยทั้งหมด คง required writing-plans header, section labels (`Goal`,
`Architecture`, `Tech Stack`, `Global Constraints`, `Task`, `Files`, `Interfaces`,
`Step`), identifiers, code, commands, paths และ exact error strings เป็นอังกฤษ

- [ ] **Step 8: ตรวจสอบ GREEN และ repository gates ทั้งหมด**

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

ผลที่คาดหวัง: ทุก command exit `0`, late-failure tests ไม่พบ memory/durable divergence และ
replay JSON ยังคงตรง Global Constraint ทุกตัวอักษร

- [ ] **Step 9: สร้าง commit**

```bash
git add src/tiewtrade/application/paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  docs/superpowers/specs/2026-07-28-paper-spot-hardening-design.md \
  docs/superpowers/plans/2026-07-28-paper-spot-hardening.md
git commit -m "fix: make Paper Spot Candle transitions atomic"
```
