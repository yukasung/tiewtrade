# Implementation Status

วันที่อัปเดต: 2026-09-23 · commit อ้างอิง: `3eaeff2` + working tree (rename `fasttrade` → `tiewtrade`)
ปิด finding: [IMP-01](reviews/backend-structure-review.md)

เอกสารนี้ตอบคำถามเดียว: **ตอนนี้อะไรรันได้จริง และอะไรยังเป็น scaffold**
ไม่ใช่ที่เก็บกติกา — ขอบเขตและหน้าที่ของแต่ละ process อยู่ใน
[architecture.md §3](architecture/architecture.md#3-processes-containers) และ
[§10](architecture/architecture.md#10-repository-layout-adr-0006);
dependency rules อยู่ใน [ADR-0006](architecture/adr/0006-monorepo-and-toolchain.md)
และบังคับด้วย import-linter ใน `backend/pyproject.toml`

นิยามสถานะ:

- **Implemented** — มีโค้ดที่ทำงานได้และมี tests
- **Scaffold** — มีแค่ package metadata, `__init__.py` (docstring) และ `py.typed`; ไม่มี runtime, ไม่มี tests
- **Planned** — ยังไม่มี directory

---

> แผนที่โค้ด (หน้าที่, dependency direction, entry points, ควรเริ่มอ่านตรงไหน) อยู่ที่
> [backend/README.md](../backend/README.md) — เอกสารนี้เน้นเฉพาะ**สถานะ**

## Backend packages

| Package | สถานะ | มีอะไรอยู่จริง | ยังไม่มี |
|---|---|---|---|
| [`tiewtrade_core`](../backend/packages/core/src/tiewtrade_core/) | **Implemented (บางส่วน)** | `market/`, `portfolio/`, `margin/`, `execution/` (Paper Fill Model §4.1–4.3), `orders/` (Order lifecycle), `execution/` รวม `PaperExecutionAdapter`, `_decimal.py` (`DECIMAL_CONTEXT`) | Risk rules, Bracket (FR-ORD-14/15), Strategy interfaces, Paper liquidation (§4.4) และ replay (§4.5) |
| [`tiewtrade_strategies`](../backend/packages/strategies/src/tiewtrade_strategies/) | **Scaffold** | `__init__.py` เท่านั้น | Built-in Strategy ทุกตัว (D-06), Order Intent emission |
| [`tiewtrade_binance`](../backend/packages/binance/src/tiewtrade_binance/) | **Scaffold** | `__init__.py` เท่านั้น | REST/WS client, payload mapping, Venue config (D-17) |
| [`tiewtrade_infra`](../backend/packages/infra/src/tiewtrade_infra/) | **Scaffold** | `__init__.py` เท่านั้น | Postgres repositories, Redis bus, lease, key provider, settings |

### `tiewtrade_core` รายละเอียด

| Module | Public API | Tests |
|---|---|---|
| [`market/`](../backend/packages/core/src/tiewtrade_core/market/) | `MarketType`, `MarginMode`, `OrderSide`, `Venue`, `Symbol`, `SymbolFilters`, `FilterViolation`, `LeverageBracket(s)`, `Rounding`, `round_to_increment` | [`test_market.py`](../backend/packages/core/tests/test_market.py) |
| [`portfolio/`](../backend/packages/core/src/tiewtrade_core/portfolio/) | `SpotHolding`, `apply_spot_buy/sell`, `FuturesPosition`, `apply_futures_fill`, `trading_fee`, `funding_payment`, `FLAT`, `NO_HOLDING` | [`test_portfolio.py`](../backend/packages/core/tests/test_portfolio.py), [`test_portfolio_properties.py`](../backend/packages/core/tests/test_portfolio_properties.py) |
| [`margin/`](../backend/packages/core/src/tiewtrade_core/margin/) | `margin_requirement`, `order_margin`, `frozen_margin`, `open_loss`, `available_balance`, `assuming_price`, `cross_margin_state`, `isolated_margin_state`, `liquidation_price`, `FuturesExposure`, `MarginState`, `MarginRatio`, `PendingOrder` | [`test_margin.py`](../backend/packages/core/tests/test_margin.py), [`test_margin_properties.py`](../backend/packages/core/tests/test_margin_properties.py) |
| [`execution/`](../backend/packages/core/src/tiewtrade_core/execution/) | `TopOfBook`, `PaperFill`, `market_fill`, `is_marketable`, `limit_fill_on_submit`, `resting_limit_fill(s)`, `ExecutionAdapter`, `PaperExecutionAdapter`, `ExecutionReport`, `ReportKind`, `MarketSnapshot`, `BracketLeg`, `stop_loss_triggered`, `take_profit_triggered`, `triggered_leg`, `closing_side` | [`test_execution.py`](../backend/packages/core/tests/test_execution.py), [`test_execution_properties.py`](../backend/packages/core/tests/test_execution_properties.py) |
| [`orders/`](../backend/packages/core/src/tiewtrade_core/orders/) | `OrderIntent`, `Order`, `order_from_intent`, `OrderStatus`, `OrderType`, `OwnerType`, `TimeInForce`, `BracketRole`, `build_client_order_id`, `is_platform_client_order_id` | [`test_orders.py`](../backend/packages/core/tests/test_orders.py), [`test_orders_properties.py`](../backend/packages/core/tests/test_orders_properties.py) |

สูตรที่ยังมี marker **Verify** ใน [calculation.md](specs/calculation.md) ยังไม่ยืนยันกับ Binance
ต่อให้มี tests แล้วก็ยังไม่ถือว่า verified

---

## Backend services

ทุก service มี `pyproject.toml` + `src/<pkg>/__init__.py` + `py.typed` เท่านั้น
ยกเว้น `api` ไม่มี service ใดมี `main.py`, bootstrap, settings หรือ lifecycle

| Service | สถานะ | มีอะไรอยู่จริง | Runtime |
|---|---|---|---|
| [`api`](../backend/services/api/src/tiewtrade_api/) | **Implemented (เริ่มต้น)** | [`app.py`](../backend/services/api/src/tiewtrade_api/app.py): `create_app()`, `GET /api/v1/health` → `{"status": "ok"}` | รันได้: `uv run uvicorn tiewtrade_api.app:app --reload` |
| [`engine`](../backend/services/engine/src/tiewtrade_engine/) | **Scaffold** | `__init__.py` | ไม่มี |
| [`market_data`](../backend/services/market_data/src/tiewtrade_market_data/) | **Scaffold** | `__init__.py` | ไม่มี |
| [`execution`](../backend/services/execution/src/tiewtrade_execution/) | **Scaffold** (Phase 2) | `__init__.py` | ไม่มี |
| [`jobs`](../backend/services/jobs/src/tiewtrade_jobs/) | **Scaffold** | `__init__.py` | ไม่มี |
| [`notifier`](../backend/services/notifier/src/tiewtrade_notifier/) | **Scaffold** | `__init__.py` | ไม่มี |

API ที่ implement แล้วมีแค่ health endpoint เดียว — endpoint อื่นทั้งหมดใน
[api.md](specs/api.md) ยังไม่มีโค้ด

---

## ส่วนที่ยังไม่มี directory (Planned)

| ส่วน | อ้างอิง |
|---|---|
| `frontend/` (Vite + React + TS) | [architecture §9](architecture/architecture.md#9-frontend), [§10](architecture/architecture.md#10-repository-layout-adr-0006) |
| `proxy` (Caddy) + `deploy/Caddyfile` | [architecture §3](architecture/architecture.md#3-processes-containers), [§11.1](architecture/architecture.md#111-ช่วงทดลอง-vm-เดียว-adr-0008) |
| Database migrations | [data-model.md](specs/data-model.md); ownership ยังไม่ตัดสิน — IMP-03 |
| Integration / e2e tests | `backend/pyproject.toml` `testpaths = ["packages", "services"]` ยังไม่ครอบคลุม — IMP-03 |

---

## Infrastructure และ tooling

| ส่วน | สถานะ |
|---|---|
| uv workspace 10 members (4 packages + 6 services) | **Implemented** |
| ruff, mypy (strict สำหรับ core + strategies), import-linter 7 contracts, pytest | **Implemented** และเป็นเกณฑ์เดียวกับ CI |
| Core purity checks ([`test_core_purity.py`](../backend/packages/core/tests/test_core_purity.py)) — บังคับ `@calc`, ห้าม clock/randomness/filesystem, ห้าม `float` | **Implemented** — ปิด IMP-02 |
| `deploy/docker-compose.yml` — Postgres 16 + Redis 7 | **Implemented** (local เท่านั้น; ยังไม่มี application services) |
| Application services ใน compose | **Planned** — เพิ่มเมื่อแต่ละ service มี runtime (ADR-0008) |

การมีครบ 6 service directories ไม่ได้แปลว่ามี trading process ที่รันได้ครบ
ตารางข้างบนคือสถานะจริง

---

## วิธีตรวจซ้ำ

```sh
cd backend
uv run pytest --collect-only -q | tail -5        # จำนวน tests ที่ collect ได้
find packages services -path '*/src/*' -name '*.py' | sort   # ไฟล์ source ทั้งหมด
```

service ที่มีแต่ `__init__.py` และ `py.typed` คือ scaffold
