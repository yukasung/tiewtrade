# AGENTS.md — TiewTrade

Instructions for coding agents (Codex, Claude Code) and contributors. Keep this file short;
details live in `docs/`.

## Project
Multi-user Trading SaaS for Binance Spot and USDⓈ-M Futures with Paper and Live trading.
Phase 1 is Paper only; Live comes in Phase 2. Target market: Thailand; developed against
Binance.com, Binance TH later (D-17).

## Sources of truth — read before changing related code
| Topic | File |
|---|---|
| Requirements, decisions (D-xx), glossary | `docs/requirements/mvp.md` |
| Architecture, process model, flows | `docs/architecture/architecture.md` |
| Architecture decisions (ADR-0001…) | `docs/architecture/adr/` |
| Formulas (margin, PnL, liquidation, Paper Fill Model) | `docs/specs/calculation.md` |
| PostgreSQL schema | `docs/specs/data-model.md` |
| REST / WebSocket contract, error codes | `docs/specs/api.md` |

If code and a spec disagree, stop and raise it — do not silently follow either.

## Non-negotiable principles (mvp.md §1.4)
- P-01 Strategies/Bots never call Binance; they emit Order Intents only.
- P-02 Every order goes through the Risk Engine and Order Manager.
- P-03/P-04 Paper and Live share the Trading Core; only the Execution Adapter differs.
- P-05 Margin and liquidation are calculated per Portfolio.
- P-07 Money calculations are deterministic code, never AI.
- P-08/P-09 Binance is the source of truth for Live; reconcile with it.
- P-10 API secrets are decrypted only in the `execution` service.

## Code rules
- **Trading Core (`backend/packages/core`) is pure:** no I/O, no network/DB/Redis/files,
  no clock reads, no randomness. Time and IDs (e.g. episode IDs) come from the caller.
- **Money is `Decimal`, never `float`.** Any Decimal arithmetic outside the core (services,
  tests) must run in `tiewtrade_core.DECIMAL_CONTEXT` (50 digits), otherwise results differ.
- Dependency rules are enforced by import-linter (`backend/pyproject.toml`): core depends on
  nothing; strategies → core only; binance/infra → core only and not on each other;
  services do not import each other; only `execution` and `market_data` use `tiewtrade_binance`.
- Services communicate only through Postgres and Redis. Postgres is authoritative; Redis may
  lose data (ADR-0004, ADR-0011). One engine owns a Workspace at a time (ADR-0009).
- Use domain terms from the mvp.md Glossary in code (e.g. `Portfolio`, `Order Intent`,
  `Position Episode`); enums are `UPPER_SNAKE_CASE`.
- Formulas marked **Verify** in calculation.md are unconfirmed against Binance; keep the
  marker and do not present them as verified.

## Testing and checks
Every change keeps all of these green (same as CI):
```sh
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy            # strict for tiewtrade_core and tiewtrade_strategies
uv run lint-imports    # architecture rules
uv run pytest
```
Calculation code needs unit tests with worked examples and property-based tests
(hypothesis) for invariants.

## Decisions and documentation
- Documents are written in Thai with English domain terms and IDs.
- Do not decide ambiguous requirements; mark proposals **Proposed** and ask the owner.
- Record decisions with IDs (D-xx, C-xx, M-xx, A-xx) and update every dependent document.
- Accepted ADRs are not edited in substance; add a new ADR that amends or supersedes them.

## Git
- Commit or push only when the owner asks. After pushing, check that CI passes.
- `astral-sh/setup-uv` has no floating major tags; pin exact versions.

## Local environment
- `cp deploy/.env.example deploy/.env`; if ports 5432/6379 are taken, set
  `POSTGRES_PORT` / `REDIS_PORT` there (the owner's machine already uses 6379).
