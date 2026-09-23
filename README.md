# TiewTrade

Trading SaaS for Binance Spot and USDⓈ-M Futures with Paper and Live trading.

## Documentation
- [MVP Requirements](docs/requirements/mvp.md)
- [Architecture](docs/architecture/architecture.md) and [ADRs](docs/architecture/adr/)
- Specs: [Calculation](docs/specs/calculation.md), [Data Model](docs/specs/data-model.md), [API](docs/specs/api.md)

## Repository layout
```
backend/     uv workspace (Python 3.12)
  packages/  core (pure Trading Core), strategies, binance, infra
  services/  api, engine, market_data, execution, jobs, notifier
deploy/      docker compose for local Postgres and Redis
docs/        requirements, architecture, specs
```

## Backend development
Requires [uv](https://docs.astral.sh/uv/).

```sh
cd backend
uv sync                      # create .venv and install all workspace packages
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy                  # type check (strict for tiewtrade_core)
uv run lint-imports          # architecture rules (ADR-0001, ADR-0006)
uv run uvicorn tiewtrade_api.app:app --reload   # API at http://127.0.0.1:8000/api/v1/health
```

## Local infrastructure
```sh
cd deploy
cp .env.example .env         # set POSTGRES_PASSWORD; change ports if 5432/6379 are taken
docker compose up -d --wait
```
