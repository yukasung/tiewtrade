# DEV-97 Paper Trade History Acceptance Implementation Plan

> **สำหรับ Codex:** SUB-SKILL ที่ต้องใช้: ใช้ `subagent-driven-development` เพื่อ
> ดำเนินการตามแผนนี้ทีละ task และใช้ TDD สำหรับการเปลี่ยนแปลง behavior ใน production ทุกครั้ง

**Goal:** พิสูจน์ Paper Spot/Futures Trade History ตั้งแต่ production Paper execution
ผ่าน durable SQLite, restart boundary, application query และ Desktop UI พร้อมหลักฐาน
Open Basket, duplicate/Partial Fill และ persistence fail-closed ครบตาม DEV-97

**Architecture:** ใช้ concrete Paper Spot/Futures Sessions และ SQLite coordinators
ที่มีอยู่สร้าง durable records ใน temporary database เดียว จากนั้นสร้าง database/store
objects ชุดใหม่เพื่ออ่านผ่าน application query และ Desktop composition จริง เพิ่ม
direct normalized persistence scenario เฉพาะ Partial Fill ซึ่ง Paper executor v1
ยังไม่จำลอง และไม่สร้าง production abstraction ใหม่หาก acceptance tests ไม่พบ defect

**Tech Stack:** Python 3.12+, pytest, pytest-qt, PySide6, SQLite, Ruff, mypy,
Nextra documentation checks

---

## Global Constraints

- ใช้ `TradeMode.PAPER`, fake/local data และ temporary SQLite เท่านั้น
- ห้ามเรียก Binance Private API, Live order, OS Keyring หรือ credentials
- ปิด network ใน cross-layer Desktop scenario และ fail test ทันทีหากมี connection
- ใช้ completed candles แบบ deterministic; ไม่มีการดาวน์โหลดข้อมูลระหว่าง test
- ใช้ production Paper Sessions, persistence coordinators, application queries และ
  Desktop composition จริงใน cross-layer scenario
- Open Basket ต้องไม่ถูกรวมใน closed Net PnL
- duplicate Fill ต้องเป็น idempotent no-op; Partial Fills ของ Order เดียวกันต้องคง
  `entry_count` เดิมและเรียง deterministic
- persistence failure ต้อง rollback transaction และ block candle ถัดไปก่อน core
  Session ประมวลผล
- ไม่สร้าง generic interface, repository, factory หรือ acceptance coordinator ใหม่
- การเพิ่ม acceptance test เพื่อพิสูจน์ behavior เดิมอาจผ่านตั้งแต่ครั้งแรกได้; หากต้อง
  แก้ production code ต้องเพิ่ม focused failing test และเห็น RED ที่ตรงสาเหตุก่อนเสมอ
- UI ต้องอ่านผ่าน callables ที่ compose ใน `desktop_main`; ห้าม import SQLite,
  Strategy หรือ Execution เข้า `ui`
- UI error ต้องเป็น sanitized unavailable state และไม่แสดง path/error ภายใน

## Task 1: Cross-layer Paper Execution, Restart and Desktop Proof

**Files:**

- สร้าง: `tests/support/paper_trade_history_acceptance.py`
- สร้าง: `tests/acceptance/test_paper_trade_history_acceptance.py`
- อ่าน/ตรวจสอบ: `tests/acceptance/test_paper_spot_trade_history.py`
- อ่าน/ตรวจสอบ: `tests/acceptance/test_paper_futures_trade_history.py`
- อ่าน/ตรวจสอบ: `tests/acceptance/test_desktop_trade_history.py`

### Step 1: เพิ่ม test builder แบบ deterministic ที่เจาะจง

สร้าง test support พร้อม constants ที่ไม่ชนกับ acceptance tests ที่มีอยู่:

```python
SPOT_SESSION_ID = UUID("00000000-0000-0000-0000-000000000401")
FUTURES_SESSION_ID = UUID("00000000-0000-0000-0000-000000000402")
OPEN_SPOT_SESSION_ID = UUID("00000000-0000-0000-0000-000000000403")
```

เพิ่ม builders ที่มี inputs ชัดเจนและ return types ของ production:

```python
def build_spot_session(session_id: UUID) -> PaperSpotSession: ...
def build_futures_session(session_id: UUID) -> PaperFuturesSession: ...
def spot_history(session_id: UUID, store: SQLiteTradeHistory) -> PaperSpotSQLiteHistory: ...
def futures_history(
    session_id: UUID, store: SQLiteTradeHistory
) -> PaperFuturesSQLiteHistory: ...
def spot_candles() -> tuple[Candle, ...]: ...
def futures_candles() -> tuple[Candle, ...]: ...
```

ใช้ค่าที่อนุมัติแล้วและมีการทดสอบใน acceptance tests ที่มีอยู่:

- Symbol `BTCUSDT`, Timeframe `5m`, Preset `rsi-step-grid-v1`
- Spot capital `1000`, trading ratio `0.6`, `max_entries=4`
- Futures capital `200000`, leverage `3`, `max_entries=10`
- fee rate `0.001`, slippage `2` bps
- Spot symbol rules: tick `0.01`, step `0.001`, min notional `5`
- Futures symbol rules: tick `0.1`, step `0.001`, min notional `5`
- Spot candles from `tests/fixtures/btcusdt_5m_tracer.csv`
- Futures candles ให้คัดลอก deterministic down-then-up series ที่ใช้ใน
  Paper Futures acceptance test ที่มีอยู่

เตรียม helpers ที่คืนค่า closed Basket ID เมื่อพบการ close จริงแล้วเท่านั้น:

```python
def run_closed_spot(store: SQLiteTradeHistory) -> UUID: ...
def run_closed_futures(store: SQLiteTradeHistory) -> UUID: ...
```

แต่ละ helper ต้อง assert ว่า persistent snapshot ทุกตัวที่คืนค่าเป็น `PersistenceState.READY`
และ fail อย่างชัดเจนเมื่อ deterministic sequence ไม่ close Basket

### Step 2: เขียน cross-layer acceptance test

เพิ่ม:

```python
def test_paper_execution_history_survives_restart_and_reaches_desktop(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    qtbot: QtBot,
) -> None:
    ...
```

test ต้อง:

1. สร้าง/migrate temporary SQLite database หนึ่งชุด
2. Block `socket.create_connection`, `socket.socket.connect`, `socket.getaddrinfo`
   และ `socket.gethostbyname` ด้วย functions ที่เรียก `pytest.fail`
3. รัน closed Spot และ Futures sessions จริงลงใน `SQLiteTradeHistory` เดียวกัน
4. อ่าน `before_restart = history.list_baskets(TradeHistoryFilter(), PageRequest())`
5. Assert ผลลัพธ์ durable ที่ตรงตามนี้:
   - closed Baskets สองรายการ
   - Futures Net PnL `Decimal("2259.8497298")`
   - Spot Net PnL `Decimal("13.84062222")`
   - total closed Net PnL `Decimal("2273.69035202")`
   - แต่ละ Basket มี BUY แล้วตามด้วย SELL Fills จาก `PAPER_EXECUTOR`
   - Futures leverage `3` และ Funding Fee `Decimal("0.00")`
6. สร้าง objects `SQLiteDatabase` และ `SQLiteTradeHistory` ใหม่จาก path เดิม
   แล้ว assert ว่า Basket page/Fills ตรงกับค่าก่อน restart ทุกประการ
7. Compose `MainWindow` ผ่าน `desktop_main.run_desktop(path)` โดยใช้
   non-blocking QApplication/captured-window seam เดียวกับ Desktop acceptance ที่มีอยู่
8. เปิด Trade History แล้ว assert ว่ามี Basket rows สองรายการ, total PnL text
   `2273.69035202 USDT · Profit` และ Futures-first ordering แบบ deterministic
9. Assert ค่า Futures row:

```text
2026-01-01 02:05:00 UTC | Paper | Futures | BTCUSDT | 5m | 1 |
29999.9492 USDT | 2322.1718 USDT | 62.3220702 USDT | 0.00 USDT |
2259.8497298 USDT · Profit | Closed
```

10. Assert BUY/SELL Fill rows ของรายการนั้น, เลือก Spot Basket และ assert ว่า fills
    ที่แสดงเปลี่ยนเป็น persisted Spot fills ที่ตรงกันทุกประการ

ให้ Desktop capture helper เป็น private ของ acceptance file นี้ ห้ามเปิดเผย
production test seam หรือเปลี่ยน production composition เพื่อ test นี้เท่านั้น

### Step 3: รัน acceptance test ใหม่

รัน:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  -k execution_history -q
```

หาก test ผ่านทันที ให้บันทึกว่าเป็น cross-layer acceptance evidence ใหม่สำหรับ
production behavior ที่มีอยู่ และไม่ต้องเปลี่ยน production หาก test ล้มเหลวเพราะไม่มี
production behavior ที่ต้องการ ให้เพิ่ม focused failing unit หรือ integration test ที่เล็กที่สุดก่อน,
ยืนยัน RED แล้วจึงใช้ GREEN fix ขั้นต่ำและรัน test นี้อีกครั้ง

### Step 4: รัน acceptance tests ที่อยู่ติดกัน

รัน:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_futures_trade_history.py \
  tests/acceptance/test_trade_history_query_acceptance.py \
  tests/acceptance/test_desktop_trade_history.py \
  tests/acceptance/test_paper_trade_history_acceptance.py -q
```

### Step 5: Commit Task 1

```bash
git add tests/support/paper_trade_history_acceptance.py \
  tests/acceptance/test_paper_trade_history_acceptance.py
git commit -m "test: prove Paper Trade History end to end"
```

## Task 2: Open Basket, Duplicate and Partial Fill Determinism

**Files:**

- แก้ไข: `tests/support/paper_trade_history_acceptance.py`
- แก้ไข: `tests/acceptance/test_paper_trade_history_acceptance.py`
- อ่าน/ตรวจสอบ: `src/tiewtrade/integrations/sqlite/trade_history.py`
- อ่าน/ตรวจสอบ: `tests/unit/integrations/sqlite/test_trade_history.py`
- อ่าน/ตรวจสอบ: `tests/unit/integrations/sqlite/test_trade_history_query.py`

### Step 1: เพิ่ม open-Basket runner ที่ใช้งานจริง

เพิ่ม:

```python
@dataclass(frozen=True, slots=True)
class OpenSpotHistory:
    basket: BasketResult
    fill: TradeFill


def run_spot_until_entry(store: SQLiteTradeHistory) -> OpenSpotHistory: ...
```

ใช้ `OPEN_SPOT_SESSION_ID`, หยุดทันทีหลังจาก persist Paper Spot Entry Fill จริงรายการแรก
จากนั้น load Basket และ Fill จาก SQLite Assert ว่า Basket status เป็น `OPEN`
และมี Fill เพียงหนึ่งรายการก่อนคืนค่า

### Step 2: เขียน Open Basket และ normalized Partial Fill acceptance test

เพิ่ม:

```python
def test_open_basket_duplicate_and_partial_fills_remain_deterministic(
    tmp_path: Path,
) -> None:
    ...
```

สถานการณ์:

1. บันทึก closed Spot Basket หนึ่งรายการผ่าน `run_closed_spot`
2. บันทึก Open Spot Basket หนึ่งรายการผ่าน `run_spot_until_entry`
3. เรียก `record_open_basket(open_basket, first_fill)` ซ้ำและ assert `False`
4. สร้าง `TradeFill` รายการที่สองโดยมี:
   - `fill_id` ใหม่
   - `basket_id`, `session_id`, `order_id` และ `entry_number` เดิม
   - `filled_at_utc = first_fill.filled_at_utc + timedelta(seconds=1)`
   - price `first_fill.price`, quantity `Decimal("0.001")`
   - notional และ commission ที่คำนวณได้ตรงตามค่า โดยใช้ fee rate `0.001`
5. สร้าง Basket ที่เสนอโดยเพิ่ม notional/fee และคง `entry_count=1` ไว้
6. Assert ว่า `record_entry_fill` ครั้งแรกคืน `True` และการ replay ที่ตรงกันทุกประการคืน `False`
7. เปิด SQLite ใหม่แล้ว assert ว่า:
   - Open Basket มี Fills สองรายการที่ใช้ Order/Entry เดียวกัน
   - `entry_count == 1`
   - Fills เรียงตามเวลา แล้วตามด้วย ID
   - unfiltered query รวม Open และ Closed Baskets
   - Net PnL เท่ากับ closed Spot Basket เท่านั้น `Decimal("13.84062222")`
   - `status=OPEN` query มี Net PnL `Decimal("0")`
8. เปิด/query อีกครั้งเป็นครั้งที่สอง และ assert ว่า page และ fills ตรงกันแบบ byte-for-value
   กับการอ่านหลัง restart ครั้งแรก

test นี้ทดสอบ normalized persistence contract โดยตรงสำหรับ partial Fill รายการที่สองที่สร้างขึ้น
ห้ามแก้ Paper execution ให้ emit Fill มากกว่าหนึ่งรายการ

### Step 3: รัน focused tests

รัน:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  tests/unit/integrations/sqlite/test_trade_history.py \
  tests/unit/integrations/sqlite/test_trade_history_query.py -q
```

หาก persistence behavior ล้มเหลว ให้เพิ่ม/ยืนยัน focused RED test ที่ตรงกันก่อนแก้ production
ห้ามลดความเข้มงวดของ conflict หรือ ownership validation ปัจจุบัน

### Step 4: Commit Task 2

```bash
git add tests/support/paper_trade_history_acceptance.py \
  tests/acceptance/test_paper_trade_history_acceptance.py
git commit -m "test: prove durable partial Fill semantics"
```

## Task 3: Real SQLite Failure and Fail-Closed Session Proof

**Files:**

- แก้ไข: `tests/acceptance/test_paper_trade_history_acceptance.py`
- อ่าน/ตรวจสอบ: `src/tiewtrade/integrations/sqlite/persistent_paper_spot_session.py`
- อ่าน/ตรวจสอบ: `src/tiewtrade/integrations/sqlite/session_persistence.py`
- อ่าน/ตรวจสอบ: `tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py`

### Step 1: เขียน SQLite failure acceptance test ที่ใช้งานจริง

เพิ่ม:

```python
def test_sqlite_failure_blocks_new_paper_entry_fail_closed(tmp_path: Path) -> None:
    ...
```

test ต้อง:

1. ทำ migration สำหรับ temporary database
2. สร้าง SQLite trigger บน `trade_fills`:

```sql
CREATE TRIGGER fail_trade_fill_insert
BEFORE INSERT ON trade_fills
BEGIN
    SELECT RAISE(ABORT, 'forced Trade History failure');
END;
```

3. สร้าง `PaperSpotSession`, `PaperSpotSQLiteHistory` และ
   `PersistentPaperSpotSQLiteSession` จริงโดยใช้ Session ID ที่ไม่ซ้ำ
4. วนผ่าน deterministic Spot candles จน Entry persistence raise
   `TradeHistoryUnavailableError`
5. Assert ว่า transaction rollback แล้ว: มองไม่เห็น Basket และ Fill
6. ส่ง candle ถัดไปและ assert `SessionPersistenceBlockedError` ก่อนมี
   persistence attempt ใหม่
7. เปิด SQLite ใหม่แล้ว assert ว่า history ยังคงว่าง

ห้าม mock `PaperSpotSession` หรือ `SQLiteTradeHistory` ใน acceptance test นี้ trigger คือ
deterministic failure injector และต้องอยู่ภายใน temporary DB

### Step 2: รัน RED/GREEN checks

รัน acceptance test เดี่ยวก่อน:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  -k sqlite_failure -q
```

จากนั้นรัน coordinator และ SQLite suites:

```bash
PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/unit/integrations/sqlite/test_persistent_paper_spot_session.py \
  tests/unit/integrations/sqlite/test_trade_history.py -q
```

หาก production flow ที่มีอยู่ผ่านแล้ว ให้คง acceptance proof ไว้โดยไม่เปลี่ยน production
หากไม่ผ่าน ให้เพิ่ม focused RED test ที่เล็กที่สุดก่อนทำ minimal fix

### Step 3: Commit Task 3

```bash
git add tests/acceptance/test_paper_trade_history_acceptance.py
git commit -m "test: prove Trade History fails closed"
```

## Task 4: Delivery Status and Complete Verification

**Files:**

- แก้ไข: `PROJECT_PLAN.md`
- แก้ไข: `docs/superpowers/specs/2026-07-29-dev-97-paper-trade-history-acceptance-design.md`
- เพิ่ม: `docs/superpowers/plans/2026-07-29-dev-97-paper-trade-history-acceptance.md`

### Step 1: บันทึกสถานะ DEV-97 ที่ส่งมอบแล้ว

หลัง acceptance tests ทั้งหมดผ่าน ให้เพิ่ม status paragraph แบบกระชับหลัง DEV-96 ใน
`PROJECT_PLAN.md` โดยระบุว่า:

- Paper Spot/Futures execution จริงไปถึง durable SQLite และ Desktop Trade History
- restart รักษา Basket/Fills และ closed Net PnL ที่ตรงตามค่า
- มี coverage สำหรับ Open Basket, duplicate, Partial Fill และ SQLite fail-closed semantics
- ไม่มีการเพิ่ม Live/network/credential behavior
- DEV-97 ปิด Trade History acceptance slice แต่เพียงลำพังยังไม่ทำให้
  Stop Session, startup Recovery หรือ Paper Trading Complete criteria ทั้งหมดเสร็จสมบูรณ์

ห้ามทำเครื่องหมายว่า Milestone 3 เสร็จสมบูรณ์

### Step 2: ตรวจ focused acceptance coverage

รัน:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest \
  tests/acceptance/test_paper_trade_history_acceptance.py \
  tests/acceptance/test_paper_spot_trade_history.py \
  tests/acceptance/test_paper_futures_trade_history.py \
  tests/acceptance/test_trade_history_query_acceptance.py \
  tests/acceptance/test_desktop_trade_history.py -q
```

### Step 3: รัน project quality gates ทั้งหมด

รัน:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q
PYTHONPATH=src ../../.venv/bin/python -m ruff check src tests
PYTHONPATH=src ../../.venv/bin/python -m ruff format --check src tests
MYPYPATH=src ../../.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check main...HEAD
```

บันทึกจำนวน pass ที่แน่นอนและ warnings ทั้งหมดใน implementation report gate ที่ skipped หรือ
aborted ไม่นับว่าผ่าน

### Step 4: Commit documentation status

```bash
git add PROJECT_PLAN.md \
  docs/superpowers/specs/2026-07-29-dev-97-paper-trade-history-acceptance-design.md \
  docs/superpowers/plans/2026-07-29-dev-97-paper-trade-history-acceptance.md
git commit -m "docs: report DEV-97 acceptance"
```

### Step 5: Review และ issue completion

1. สร้าง review package สำหรับแต่ละ task และต้องได้รับ approval ทั้งด้าน spec-compliance และ
   code-quality ก่อนทำ task ถัดไป
2. สร้าง whole-branch review package จาก branch merge base ถึง `HEAD`
3. แก้ทุก Critical/Important finding และรัน covering tests อีกครั้ง
4. รัน complete gates อีกครั้งหลัง final fixes
5. เพิ่ม Thai Linear comment ที่สรุป changes, tests และ residual risk
6. ย้าย DEV-97 เป็น `Done` เมื่อ implementation และ verification เสร็จจริงเท่านั้น
7. ห้าม push, merge หรือลบ branch/worktree จนกว่าผู้ใช้จะให้ confirmations
   แยกต่างหากตามที่ต้องการ
