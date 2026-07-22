# TiewTrade

TiewTrade is an Internal Alpha trading bot. Development is Paper-first: this
repository currently provides a deterministic Paper Spot replay for completed
BTCUSDT 5-minute candles.

The replay CLI does not connect to Binance and does not send Live orders.

## Setup

Create a virtual environment and install the project with its development
dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

## Replay the tracer fixture

Run the deterministic Paper Spot replay from the repository root:

```bash
PYTHONPATH=src .venv/bin/python -m tiewtrade.paper_replay_main \
  tests/fixtures/btcusdt_5m_tracer.csv \
  --available-capital 1000 \
  --trading-capital-ratio 0.6 \
  --max-entries 4
```

The stable JSON result is:

```json
{"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"13.84062222"}
```

## Verification

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
```
