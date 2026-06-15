# TiewTrade

TiewTrade is a Python 3.13 desktop trading bot application for Binance Spot and Binance Futures.

Version 1 follows the product decisions in `docs/product-decisions.md`.

## Current Task

The project is currently in `TASK-001 Project Foundation`.

## Development Setup

Create a virtual environment and install the project in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the foundation bootstrap check:

```bash
tiewtrade --check
```

Run tests:

```bash
python -m unittest
```

## Configuration

The foundation supports environment-based configuration:

- `TIEWTRADE_ENV`
- `TIEWTRADE_LOG_LEVEL`
- `TIEWTRADE_DATA_DIR`
- `TIEWTRADE_LOG_DIR`
- `TIEWTRADE_CONFIG_FILE`

See `.env.example` and `config/app.example.toml`.
