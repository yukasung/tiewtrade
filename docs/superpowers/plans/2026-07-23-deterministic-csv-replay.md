# Deterministic CSV Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** ส่งมอบ strict CSV loader, deterministic Paper Spot replay runner, stable JSON CLI และ acceptance fixture 40 Candles สำหรับ DEV-80

**Architecture:** \`replay/csv_candles.py\` แปลงไฟล์เป็น immutable Candles, \`replay/paper_spot.py\` สร้าง \`PaperSpotSession\` ใหม่และรวม audit result, และ \`paper_replay_main.py\` เป็น thin composition/CLI boundary โดยไม่มี Binance, network หรือ SQLite dependency

**Tech Stack:** Python 3.12+, standard-library csv/argparse/json, Decimal, pytest, Ruff และ mypy

## Global Constraints

- เวลา Candle และ received_at ต้องเป็น timezone-aware UTC
- ราคา quantity fee slippage capital และ PnL ใช้ Decimal โดยไม่ผ่าน float
- CSV header ต้องตรง open_time,open,high,low,close,volume ตามลำดับ
- symbol และ timeframe มาจาก MarketDataConfig
- replay ต้องสร้าง PaperSpotSession ใหม่ทุกครั้งและยอมรับทุก Candle เท่านั้น
- output ใช้ compact JSON และแปลง PnL เป็น fixed-point string
- CLI รับ available capital, Spot capital ratio และ maximum Entries
- ห้าม import Binance, credentials, Keyring, Live Preflight, network หรือ SQLite
- ใช้ failing test → minimal implementation → refactor ในทุก Task

---

### Task 1: Strict Candle CSV Loader

**Files:**
- Create: \`src/tiewtrade/replay/__init__.py\`
- Create: \`src/tiewtrade/replay/csv_candles.py\`
- Test: \`tests/unit/replay/test_csv_candles.py\`

**Interfaces:**
- Consumes: Path และ MarketDataConfig
- Produces: \`load_candles_csv(path: Path, config: MarketDataConfig) -> tuple[Candle, ...]\`

- [ ] **Step 1: Write failing loader tests**

Tests ต้องครอบคลุม:
- valid UTC row ใช้ symbol/timeframe จาก configuration และคง Decimal scale
- header ขาด เกิน หรือเรียงผิด
- timestamp ไม่มี UTC, Decimal ผิด และจำนวน columns ผิด พร้อมข้อความ CSV row 2
- header-only file ถูกปฏิเสธ

Wished-for API:

    candles = load_candles_csv(
        tmp_path / "candles.csv",
        MarketDataConfig(symbol="ETHUSDT", timeframe="5m"),
    )
    assert candles[0].symbol == "ETHUSDT"
    assert candles[0].open == Decimal("100.10")

- [ ] **Step 2: Verify RED**

Run:

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/replay/test_csv_candles.py -q

Expected: ModuleNotFoundError สำหรับ \`tiewtrade.replay\`.

- [ ] **Step 3: Implement minimal loader**

Implementation contract:

    CSV_HEADER = ("open_time", "open", "high", "low", "close", "volume")

    def load_candles_csv(
        path: Path, config: MarketDataConfig
    ) -> tuple[Candle, ...]:
        with path.open("r", encoding="utf-8", newline="") as source:
            rows = csv.reader(source)
            header = next(rows, None)
            if header != list(CSV_HEADER):
                raise ValueError(
                    "CSV header must be open_time,open,high,low,close,volume"
                )
            candles = tuple(
                _parse_candle(row, row_number, config)
                for row_number, row in enumerate(rows, start=2)
            )
        if not candles:
            raise ValueError("CSV must contain at least one candle")
        return candles

\`_parse_candle\` ต้องตรวจ 6 columns, ใช้ \`datetime.fromisoformat\`, สร้าง Decimal ทั้งห้าค่า และ wrap \`InvalidOperation\`/Candle \`ValueError\` เป็น \`invalid CSV row {row_number}: ...\`.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/replay/test_csv_candles.py -q
    .venv/bin/python -m ruff check src/tiewtrade/replay tests/unit/replay
    .venv/bin/python -m mypy src

- [ ] **Step 5: Commit**

    git add src/tiewtrade/replay tests/unit/replay/test_csv_candles.py
    git commit -m "feat: add strict candle CSV loader"

---

### Task 2: Deterministic Replay Result and Acceptance Fixture

**Files:**
- Create: \`src/tiewtrade/replay/paper_spot.py\`
- Create: \`tests/unit/replay/test_paper_spot.py\`
- Create: \`tests/acceptance/test_paper_spot_replay.py\`
- Create: \`tests/fixtures/btcusdt_5m_tracer.csv\`

**Interfaces:**
- Consumes: Iterable[Candle], SessionConfig, MarketDataConfig, SymbolRules, Preset
- Produces: immutable ReplayResult และ \`run_paper_spot_replay(...) -> ReplayResult\`

- [ ] **Step 1: Add exact 40-Candle fixture**

    open_time,open,high,low,close,volume
    2026-01-01T00:00:00Z,101,102,99,100,1
    2026-01-01T00:05:00Z,100,101,98,99,1
    2026-01-01T00:10:00Z,99,100,97,98,1
    2026-01-01T00:15:00Z,98,99,96,97,1
    2026-01-01T00:20:00Z,97,98,95,96,1
    2026-01-01T00:25:00Z,96,97,94,95,1
    2026-01-01T00:30:00Z,95,96,93,94,1
    2026-01-01T00:35:00Z,94,95,92,93,1
    2026-01-01T00:40:00Z,93,94,91,92,1
    2026-01-01T00:45:00Z,92,93,90,91,1
    2026-01-01T00:50:00Z,91,92,89,90,1
    2026-01-01T00:55:00Z,90,91,88,89,1
    2026-01-01T01:00:00Z,89,90,87,88,1
    2026-01-01T01:05:00Z,88,89,86,87,1
    2026-01-01T01:10:00Z,87,88,85,86,1
    2026-01-01T01:15:00Z,85,87,84,86,1
    2026-01-01T01:20:00Z,86,88,85,87,1
    2026-01-01T01:25:00Z,87,89,86,88,1
    2026-01-01T01:30:00Z,88,90,87,89,1
    2026-01-01T01:35:00Z,89,91,88,90,1
    2026-01-01T01:40:00Z,90,92,89,91,1
    2026-01-01T01:45:00Z,91,93,90,92,1
    2026-01-01T01:50:00Z,92,94,91,93,1
    2026-01-01T01:55:00Z,93,95,92,94,1
    2026-01-01T02:00:00Z,94,96,93,95,1
    2026-01-01T02:05:00Z,95,97,94,96,1
    2026-01-01T02:10:00Z,96,98,95,97,1
    2026-01-01T02:15:00Z,97,99,96,98,1
    2026-01-01T02:20:00Z,98,100,97,99,1
    2026-01-01T02:25:00Z,99,101,98,100,1
    2026-01-01T02:30:00Z,100,102,99,101,1
    2026-01-01T02:35:00Z,101,103,100,102,1
    2026-01-01T02:40:00Z,102,104,101,103,1
    2026-01-01T02:45:00Z,103,105,102,104,1
    2026-01-01T02:50:00Z,104,106,103,105,1
    2026-01-01T02:55:00Z,105,107,104,106,1
    2026-01-01T03:00:00Z,106,108,105,107,1
    2026-01-01T03:05:00Z,107,109,106,108,1
    2026-01-01T03:10:00Z,108,110,107,109,1
    2026-01-01T03:15:00Z,109,111,108,110,1

- [ ] **Step 2: Write failing result and replay tests**

Unit contract:

    result = ReplayResult(40, 0, 1, Decimal("13.84062222"))
    assert result.to_json() == (
        '{"accepted_candles":40,"closed_baskets":1,'
        '"current_entries":0,"realized_pnl":"13.84062222"}'
    )

Acceptance helper ต้องสร้าง object graph ใหม่ทุกครั้งด้วย:
- Session UUID ลงท้าย 80 และ Account UUID ลงท้าย 1
- available_capital 1000
- fee_rate 0.001
- slippage_bps 2
- EntryPolicy(max_entries=4)
- SpotTradingPolicy(trading_capital_ratio=0.6)
- SymbolRules(tick_size=0.01, step_size=0.001, min_notional=5)
- MarketDataConfig(BTCUSDT, 5m)
- RsiStepGridPreset.v1()

Assertions:

    assert first == second
    assert first.accepted_candles == 40
    assert first.current_entries == 0
    assert first.closed_baskets == 1
    assert first.realized_pnl == Decimal("13.84062222")
    assert first.to_json() == second.to_json()

เพิ่ม unit test ส่ง Candle เดิมสองครั้งแล้วต้องได้ ValueError ที่มี \`rejected candle\`.

- [ ] **Step 3: Verify RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/replay/test_paper_spot.py tests/acceptance/test_paper_spot_replay.py -q

Expected: ModuleNotFoundError สำหรับ \`tiewtrade.replay.paper_spot\`.

- [ ] **Step 4: Implement ReplayResult and runner**

Required implementation:

    @dataclass(frozen=True, slots=True)
    class ReplayResult:
        accepted_candles: int
        current_entries: int
        closed_baskets: int
        realized_pnl: Decimal

        def to_json(self) -> str:
            return json.dumps(
                {
                    "accepted_candles": self.accepted_candles,
                    "closed_baskets": self.closed_baskets,
                    "current_entries": self.current_entries,
                    "realized_pnl": format(self.realized_pnl, "f"),
                },
                separators=(",", ":"),
            )

Runner:
- สร้าง PaperSpotSession ภายใน function
- process แต่ละ Candle ด้วย \`received_at=candle.close_time\`
- ถ้า snapshot.accepted เป็น false ให้ raise ValueError
- นับ accepted Candles
- รวม \`snapshot.closed_basket.realized_pnl\`
- ปฏิเสธ iterable ว่าง
- คืน final basket entry count และ cumulative closed basket count

Signature:

    def run_paper_spot_replay(
        candles: Iterable[Candle],
        *,
        session: SessionConfig,
        market_data: MarketDataConfig,
        symbol_rules: SymbolRules,
        preset: RsiStepGridPreset,
    ) -> ReplayResult:

- [ ] **Step 5: Verify GREEN and commit**

    PYTHONPATH=src .venv/bin/python -m pytest tests/unit/replay tests/acceptance -q
    .venv/bin/python -m ruff check src/tiewtrade/replay tests/unit/replay tests/acceptance
    .venv/bin/python -m mypy src
    git add src/tiewtrade/replay/paper_spot.py tests/unit/replay/test_paper_spot.py tests/acceptance tests/fixtures
    git commit -m "feat: replay deterministic Paper Spot candles"

Expected JSON:

    {"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"13.84062222"}

---

### Task 3: Thin Replay CLI and README

**Files:**
- Create: \`src/tiewtrade/paper_replay_main.py\`
- Create: \`tests/acceptance/test_paper_replay_cli.py\`
- Create: \`README.md\`

**Interfaces:**
- Consumes: CLI argv และ CSV path
- Produces: \`main(argv: Sequence[str] | None = None) -> int\`, stdout JSON และ documented commands

- [ ] **Step 1: Write failing CLI subprocess tests**

Happy-path command:

    sys.executable -m tiewtrade.paper_replay_main
      tests/fixtures/btcusdt_5m_tracer.csv
      --available-capital 1000
      --trading-capital-ratio 0.6
      --max-entries 4

Assert return code 0, empty stderr และ exact JSON plus newline. เพิ่ม missing-file case ที่ assert return code 2, empty stdout และ stderr ขึ้นต้น \`error:\`.

- [ ] **Step 2: Verify RED**

    PYTHONPATH=src .venv/bin/python -m pytest tests/acceptance/test_paper_replay_cli.py -q

Expected: subprocess หา \`tiewtrade.paper_replay_main\` ไม่พบ.

- [ ] **Step 3: Implement thin CLI**

\`main\` ใช้ argparse รับ:
- positional csv_path: Path
- --symbol default BTCUSDT
- --timeframe default 5m
- required Decimal --available-capital
- required Decimal --trading-capital-ratio
- required int --max-entries

Composition defaults:
- fee_rate 0.001
- slippage_bps 2
- SymbolRules(0.01, 0.001, 5)
- deterministic Session UUID ลงท้าย 80
- deterministic Account UUID ลงท้าย 1
- Paper + Spot + Preset v1

Catch \`OSError\` และ \`ValueError\`, print \`error: ...\` ไป stderr และ return 2. Success print \`result.to_json()\` และ return 0. Module guard ต้อง \`raise SystemExit(main())\`.

- [ ] **Step 4: Verify GREEN**

    PYTHONPATH=src .venv/bin/python -m pytest tests/acceptance/test_paper_replay_cli.py -q
    .venv/bin/python -m ruff check src/tiewtrade/paper_replay_main.py tests/acceptance
    .venv/bin/python -m mypy src

- [ ] **Step 5: Create README.md**

README ต้องมี:
- Internal Alpha/Paper-first description
- venv และ editable dev install
- exact replay command
- stable JSON example
- explicit statement ว่าไม่เชื่อม Binance และไม่ส่ง Live order
- pytest, Ruff check/format, mypy และ git diff check commands

- [ ] **Step 6: Commit**

    git add src/tiewtrade/paper_replay_main.py tests/acceptance/test_paper_replay_cli.py README.md
    git commit -m "feat: add deterministic replay CLI"

---

### Task 4: Final Verification and Review

**Files:**
- Modify only when an in-scope DEV-80 verification failure requires correction

**Interfaces:**
- Consumes: complete DEV-80 branch
- Produces: verified branch and Linear completion evidence

- [ ] **Step 1: Run complete quality gate**

    PYTHONPATH=src .venv/bin/python -m pytest -q
    .venv/bin/python -m ruff check src tests
    .venv/bin/python -m ruff format --check src tests
    .venv/bin/python -m mypy src
    git diff --check main...HEAD

ก่อนเริ่ม DEV-80 full-repository format check มี baseline failure 6 ไฟล์นอก scope:
`completed_candle_stream.py`, `basket.py`, `spot_policy.py` และ tests ที่เกี่ยวข้อง
สามไฟล์ ห้าม reformat ไฟล์เหล่านี้ใน DEV-80 ให้รัน format check ซ้ำเฉพาะ Python
files ใน DEV-80 diff และบันทึก baseline นี้ใน completion evidence อย่างชัดเจน

- [ ] **Step 2: Run CLI twice**

Run the documented command twice. Both outputs must equal:

    {"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"13.84062222"}

- [ ] **Step 3: Review scope and safety**

Confirm diff has no Binance import, credentials, Live order, SQLite implementation, generic Backtest framework or unrelated formatting changes.

- [ ] **Step 4: Request code review and record evidence**

Resolve all Critical/Important findings, rerun the complete quality gate, then add a Thai Linear comment with commits, test counts, exact JSON and remaining tracer-bullet limits. Do not push or merge without separate user confirmations.
