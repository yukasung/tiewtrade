# Backend — แผนที่สำหรับผู้พัฒนาและ reviewer

uv workspace (Python 3.12) 10 members: `packages/` 4 ตัว + `services/` 6 ตัว
เอกสารนี้เป็น**แผนที่** บอกว่าอะไรอยู่ตรงไหน ควรเริ่มอ่านจากไหน และอะไรรันได้จริงแล้ว

ไม่ใช่ source of truth ของกติกาหรือสูตร — ดู [§6](#6-source-of-truth)
สูตรคำนวณอยู่ใน [calculation.md](../docs/specs/calculation.md) ที่เดียว เอกสารนี้ไม่คัดลอกมา

---

## 1. เริ่มอ่านตรงไหน

ถ้าเพิ่งเข้าโปรเจกต์ อ่านตามลำดับนี้ ใช้เวลาไม่นานเพราะ core ทั้งหมดมีแค่ ~857 บรรทัด

| ลำดับ | ไฟล์ | ทำไมต้องเริ่มตรงนี้ |
|---|---|---|
| 1 | [`packages/core/src/tiewtrade_core/_decimal.py`](packages/core/src/tiewtrade_core/_decimal.py) | อธิบายว่าทำไมทุกการคำนวณต้องอยู่ใน `DECIMAL_CONTEXT` (50 หลัก) และ decorator `@calc` ทำอะไร — เห็น `@calc` อยู่แทบทุกไฟล์หลังจากนี้ |
| 2 | [`market/enums.py`](packages/core/src/tiewtrade_core/market/enums.py) | คำศัพท์พื้นฐาน `Venue`, `MarketType`, `OrderSide`, `MarginMode` และ convention สำคัญ: `OrderSide.sign` = +1/-1 ซึ่งใช้เป็น signed quantity ทั้งระบบ |
| 3 | [`portfolio/futures_position.py`](packages/core/src/tiewtrade_core/portfolio/futures_position.py) | ไฟล์ใหญ่สุด (133 บรรทัด) และเป็นหัวใจ: state transition ของ position รวม flip และการจบ/เริ่ม Position Episode |
| 4 | [`margin/exposure.py`](packages/core/src/tiewtrade_core/margin/exposure.py) → [`margin/account.py`](packages/core/src/tiewtrade_core/margin/account.py) | จาก position หนึ่งตัว → margin state ของทั้ง Portfolio; `MarginState.is_liquidatable` คือเงื่อนไข liquidation ที่ถือเป็นทางการ |
| 5 | [`margin/liquidation.py`](packages/core/src/tiewtrade_core/margin/liquidation.py) | ส่วนที่ยากที่สุด docstring อธิบายวิธีแก้สมการข้าม bracket และเหตุผลที่คืน `None` ได้ 2 กรณีตรงข้ามกัน |
| 6 | [`packages/core/tests/conftest.py`](packages/core/tests/conftest.py) | fixture `margin_gap` คือการเขียนสูตร §2.4 ใหม่แบบอิสระเพื่อตรวจคำตอบ — อ่านแล้วเข้าใจวิธีทดสอบของโปรเจกต์นี้ |
| 7 | [`execution/fills.py`](packages/core/src/tiewtrade_core/execution/fills.py) | Paper Fill Model — จุดเดียวที่ตอบว่า "order นี้ fill ที่ราคาเท่าไร" อ่าน docstring ของ `limit_fill_on_submit` เรื่องลำดับ ปัด→cap |

**ถ้ามา review เรื่องเงิน** อ่าน 1 → 3 → 5 แล้วเทียบกับ
[calculation.md](../docs/specs/calculation.md) โดยตรง
**ถ้ามาดูว่าระบบรันยังไง** ตอนนี้มีแค่ [`services/api/src/tiewtrade_api/app.py`](services/api/src/tiewtrade_api/app.py) (16 บรรทัด) — ดู [§3](#3-สถานะ-implemented-และ-scaffold)

---

## 2. Dependency direction

ทิศทางนี้บังคับด้วย import-linter 6 contracts ใน [`pyproject.toml`](pyproject.toml) และ CI จะแดงถ้าผิด

```
                    ┌──────────────┐
                    │ tiewtrade_   │   ไม่ขึ้นกับใครเลย
                    │    core      │   pure: ไม่มี I/O, clock, randomness
                    └──────┬───────┘
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────▼─────┐   ┌──────▼─────┐   ┌──────▼─────┐
   │ strategies │   │  binance   │   │   infra    │
   └──────┬─────┘   └──────┬─────┘   └──────┬─────┘
          │                │                │
          └────────────────┼────────────────┘
                           │   services ประกอบทุกอย่างเข้าด้วยกัน
   ┌───────────────────────▼────────────────────────┐
   │  api   engine   market_data   execution   jobs   notifier  │
   │        services ห้าม import กันเอง                          │
   └─────────────────────────────────────────────────────────────┘
```

`binance` กับ `infra` เป็นอิสระต่อกัน (independence contract) และมีแค่ `execution` กับ
`market_data` ที่ import `tiewtrade_binance` ได้ — บังคับ P-01 และ ADR-0005 ว่า
Strategy/engine เรียก Binance ตรงไม่ได้

**ภายใน core ก็มีชั้นเช่นกัน** (layers contract ตาม architecture §4.2) ชั้นบนเรียกชั้นล่างได้
ทางเดียว: `execution` → `orders` → `margin` → `portfolio` → `market` → `_decimal`
นี่คือสิ่งที่บังคับว่า type ที่ใช้ร่วมกันอย่าง `LiquidityRole` ต้องอยู่ `market/` ไม่ใช่เพราะมีคนจำได้

dependency ที่ประกาศจริงใน `pyproject.toml` ของแต่ละ member:

| Member | ขึ้นกับ |
|---|---|
| `core` | — |
| `strategies`, `binance`, `infra` | `core` |
| `api` | `core`, `infra`, fastapi, uvicorn |
| `engine` | `core`, `strategies`, `infra` |
| `execution`, `market_data` | `core`, `binance`, `infra` |
| `jobs`, `notifier` | `core`, `infra` |

---

## 3. สถานะ implemented และ scaffold

**Scaffold** = มีแค่ `pyproject.toml` + `__init__.py` (docstring) + `py.typed` ไม่มี runtime ไม่มี tests
ตารางเต็มพร้อมรายละเอียดอยู่ที่ [implementation-status.md](../docs/implementation-status.md)

| Member | สถานะ | หน้าที่ (ย่อ — รายละเอียดที่ [architecture §3](../docs/architecture/architecture.md#3-processes-containers)) |
|---|---|---|
| `packages/core` | **Implemented (บางส่วน)** | กฎธุรกิจ pure: market, portfolio, margin, execution (Paper Fill Model), orders (lifecycle + port) |
| `packages/strategies` | Scaffold | Built-in Strategy → Order Intent (P-01) |
| `packages/binance` | Scaffold | REST/WS client, payload mapping, Venue config |
| `packages/infra` | Scaffold | Postgres repos, Redis bus, lease, key provider, settings |
| `services/api` | **Implemented (เริ่มต้น)** | มีแค่ `GET /api/v1/health` |
| `services/engine` | Scaffold | เจ้าของ Workspace: Strategy host, Risk, OMS, Paper execution |
| `services/market_data` | Scaffold | public stream ต่อ Venue, Candle |
| `services/execution` | Scaffold (Phase 2) | Live gateway, ถือ Secret ที่ถอดรหัสแล้ว (P-10) |
| `services/jobs` | Scaffold | งานตามรอบแบบ idempotent |
| `services/notifier` | Scaffold | แจ้งเตือน In-app / Email / Telegram |

**ใน core เองก็ยังไม่ครบ** ส่วนที่ยังไม่มี: Risk rules, Strategy
interfaces และ Paper liquidation (§4.4) ที่ติด marker **Verify** — ทั้งที่ [architecture §4.3](../docs/architecture/architecture.md#43-key-interfaces-pseudo-code) ร่าง interface ไว้แล้ว

---

## 4. Trading Core — แผนผังไฟล์

`packages/core/src/tiewtrade_core/` ทุกอย่างเป็น pure function หรือ frozen dataclass
เวลาและ ID (เช่น `episode_id`) รับจาก caller เสมอ ไม่ได้สร้างเอง

### `market/` — reference data
| ไฟล์ | Public API | หมายเหตุ |
|---|---|---|
| `enums.py` | `Venue`, `MarketType`, `OrderSide`, `MarginMode` | `OrderSide.sign` เป็น convention ที่ใช้ทั้ง core |
| `rounding.py` | `Rounding`, `round_to_increment` | รองรับ increment ที่ไม่ใช่กำลังสิบ |
| `symbol.py` | `Symbol`, `SymbolFilters`, `FilterViolation` | `violations()` คืน **ทุก** filter ที่ผิด ไม่ใช่ตัวแรก |
| `brackets.py` | `LeverageBracket`, `LeverageBrackets` | ตรวจว่า bracket ต่อเนื่องและเริ่มที่ 0 ตอนสร้าง |

### `portfolio/` — accounting
| ไฟล์ | Public API | หมายเหตุ |
|---|---|---|
| `futures_position.py` | `FuturesPosition`, `FLAT`, `apply_futures_fill`, `FuturesFillResult` | จัดการ same-direction / partial close / flip; `FuturesFillResult` บอกว่า episode ไหนปิดและไหนเปิด |
| `spot_holding.py` | `SpotHolding`, `NO_HOLDING`, `apply_spot_buy`, `apply_spot_sell`, `SpotBuyResult`, `SpotSellResult` | กติกา Average Cost และ fee: [calculation §3.1](../docs/specs/calculation.md) |
| `charges.py` | `trading_fee`, `funding_payment` | `funding_payment` ติดลบ = ได้รับ |
| `_fill.py` | *(private)* | guard เดียวที่ทั้งสองฝั่งใช้ร่วมกัน |

### `margin/` — USDⓈ-M margin และ liquidation
| ไฟล์ | Public API | หมายเหตุ |
|---|---|---|
| `exposure.py` | `FuturesExposure` | position เดียววัดที่ Mark Price; `quantity` เป็น signed |
| `account.py` | `MarginState`, `MarginRatio`, `cross_margin_state`, `isolated_margin_state` | ใช้ `is_liquidatable` ไม่ใช่ `margin_ratio` — เหตุผลอยู่ใน docstring และ [calculation §2.4](../docs/specs/calculation.md) |
| `requirement.py` | `margin_requirement`, `order_margin`, `open_loss`, `frozen_margin`, `available_balance`, `assuming_price`, `PendingOrder`, `MARKET_ORDER_PRICE_BUFFER` | `order_margin` = ส่วนต่างของ requirement + `open_loss` — **อย่าเหมาว่า order ที่ลด position ได้ 0 เสมอ** ทั้งสองส่วนไม่เป็นศูนย์ได้ สูตรอยู่ใน [calculation §2.7](../docs/specs/calculation.md) |
| `liquidation.py` | `liquidation_price` | แก้ทุก bracket แล้วเลือกคำตอบที่ notional ตกในตัวเอง; คืน `None` ได้ 2 กรณีตรงข้ามกัน — อ่าน docstring ก่อนใช้ |

### `execution/` — Paper Fill Model (§4.1–4.3)
| ไฟล์ | Public API | หมายเหตุ |
|---|---|---|
| `book.py` | `TopOfBook` | snapshot best bid/ask จาก caller · ใช้ `is_abnormal` กรอง snapshot เสีย **ไม่ใช่ `is_crossed`** ซึ่งพลาดกรณี locked (`bid == ask`) |
| `fills.py` | `PaperFill`, `market_fill`, `is_marketable`, `limit_fill_on_submit`, `resting_limit_fill`, `resting_limit_fills` | ปัดราคาไปทางเสียเปรียบผู้ใช้เสมอ (C-11) · marketable limit **ปัดก่อนแล้วค่อย cap** ห้ามปัดซ้ำ |
| `triggers.py` | `BracketLeg`, `stop_loss_triggered`, `take_profit_triggered`, `triggered_leg`, `closing_side` | **comparison ล้วน ห้ามใส่เลขคณิต** — จะรันใน context ของ caller · SL ชนะเมื่อ trigger ทั้งคู่ |
| `adapter.py` | `ExecutionAdapter` | **port ที่ทำให้ Paper กับ Live ใช้ core ร่วมกัน** (P-03/P-04, architecture §4.2) · ไม่คืนค่า ผลมาเป็น execution report ทีหลัง · อ้างด้วย `client_order_id` ไม่ใช่ exchange id |
| `paper.py` | `PaperExecutionAdapter`, `MarketSnapshot`, `ReportSink`, `resting_fill_report` | **ต่อ port เข้ากับ fill model** — Paper เดินได้ครบวง · **ไม่เก็บ Order เอง** engine เป็นเจ้าของ (C-20) · `submit` รับเฉพาะ `PENDING_NEW` และคืน report เสมอ 1 ใบ — idempotency เป็นของ Order Manager (C-22) · `resting_fill_report` เป็น **free function** ไม่ใช่ method เพราะการขับ order ค้างไม่ใช่งานของ port (FR-ORD-04) |
| `report.py` | `ExecutionReport`, `ReportKind` | ผลลัพธ์จาก venue ใช้ร่วมกันทั้ง Paper และ Live (C-19) · ไม่มี timestamp เพราะเวลามากับ event |
| *(ไม่มีไฟล์ guard แยก)* | — | `0 ≤ s < 1` อยู่ใน `fills.py` ส่วนกฎ "ราคาต้องเป็นบวก" เป็นของ `PaperFill.__post_init__` เองตาม C-18 |

**กับดักที่ต้องรู้:** resting limit ต้องให้ราคา**ทะลุ** (`<`/`>`) ส่วน trigger ของ §4.3 **แตะก็ยิง**
(`<=`/`>=`) ความไม่สมมาตรนี้เป็นไปตาม spec ไม่ใช่ bug

### `orders/` — Order lifecycle และ Execution Adapter port (FR-ORD)
| ไฟล์ | Public API | หมายเหตุ |
|---|---|---|
| `intent.py` | `OrderIntent` | สิ่งเดียวที่ Strategy/UI ส่งออกได้ (P-01) · ไม่มี id ไม่มีสถานะ · สร้าง intent ที่ขัดแย้งในตัวเองไม่ได้ |
| `order.py` | `Order`, `order_from_intent` | state machine 7 สถานะ · **immutable** ทุก transition คืน `Order` ตัวใหม่ · ตรวจ lifecycle ก่อนตรวจจำนวนเสมอ · `remaining_quantity` มี `@calc` เพราะการอ่านคือการลบ Decimal |
| `client_order_id.py` | `build_client_order_id`, `is_platform_client_order_id` | prefix มาจาก caller ไม่ hardcode · แยก order นอกระบบด้วย**รูปร่าง** ไม่ใช่ `startswith` (D-14) |
| `enums.py` | `OrderStatus`, `OrderType`, `OwnerType`, `TimeInForce`, `BracketRole` | ตรงกับ `orders` table ใน data-model §6.5 |
| `bracket.py` | `Bracket`, `BracketPlan`, `ProtectLeg`, `CancelLeg`, `on_entry_fill`, `on_leg_fill`, `on_entry_finished`, `on_position_closed` | **คืนแผน ไม่สั่งงานเอง** (C-23) · ป้องกันเท่า `filled_quantity` เท่านั้น (FR-ORD-14) · resize เป็น action เดียวผ่าน `replaces` ห้ามแยก cancel+place เพราะจะมีช่วงที่ไม่มีการป้องกัน · **Bracket จบแล้วต้องไม่เหลือ order ค้าง** ทั้งขาที่เหลือและ Entry — ทั้งตอนขาป้องกัน fill และตอน Position ถูกปิดด้วยวิธีอื่น (R-16, C-24) |

**ยังไม่มี:** FR-ORD-16 fail-safe ตอนวาง SL ไม่สำเร็จ — ต้องนับเวลา/นับครั้ง จึงเป็นงานของ engine ไม่ใช่ core

### จุดที่ยังไม่ยืนยันกับ Binance
โค้ดที่มี comment `Verify` คือสูตรที่ยังไม่ confirm — อย่านำไปเสนอว่า verified แล้ว
หาได้ด้วย:

```sh
grep -rn "Verify" packages/core/src
```

ปัจจุบันมี 6 จุด: `margin/requirement.py` (C-01 buffer), `margin/liquidation.py` (C-02),
`margin/exposure.py` (initial margin ใช้ Mark Price), `market/brackets.py` (C-02 ขอบ bracket)
และ `portfolio/spot_holding.py` 2 จุด (C-06 การหัก fee ของ Spot buy/sell)

---

## 5. คำสั่งรันและทดสอบ

ต้องมี [uv](https://docs.astral.sh/uv/) รันจาก `backend/`

```sh
uv sync                  # สร้าง .venv และติดตั้งทุก workspace member
```

ชุดที่ต้องเขียวทั้งหมดก่อนส่งงาน — **เหมือน CI ทุกคำสั่ง** ([ci.yml](../.github/workflows/ci.yml)):

```sh
uv run ruff check .          # lint
uv run ruff format --check . # format (ตัด --check ออกเพื่อให้แก้ไฟล์ให้)
uv run mypy                  # strict สำหรับ tiewtrade_core และ tiewtrade_strategies
uv run lint-imports          # dependency rules 7 contracts (§2)
uv run pytest                # ปัจจุบัน 344 tests
```

รัน API:

```sh
uv run uvicorn tiewtrade_api.app:app --reload
# http://127.0.0.1:8000/api/v1/health
```

Postgres + Redis สำหรับ local อยู่ที่ [`deploy/`](../deploy/) — ถ้าเคยรัน Compose project
ชื่อเดิม `fasttrade` มาก่อน อ่าน [runbook](../docs/runbooks/rename-compose-project.md) ก่อน

### เขียนเทสต์ยังไง

โค้ดคำนวณต้องมีทั้ง unit test ที่มีตัวอย่างคำนวณจริง **และ** property-based test (hypothesis)
สำหรับ invariant ดูรูปแบบที่ใช้อยู่:

- ตัวอย่างมีเลขจริง: [`test_margin.py`](packages/core/tests/test_margin.py)
- invariant: [`test_margin_properties.py`](packages/core/tests/test_margin_properties.py)
  ตรวจว่าราคาที่ได้แก้สมการจริง โดยเทียบกับ `margin_gap` ที่เขียนสูตรใหม่อย่างอิสระ

`conftest.py` เรียก `setcontext(DECIMAL_CONTEXT.copy())` — ค่าที่คาดหวังในเทสต์ต้องคำนวณ
ด้วย precision เดียวกับ core ไม่งั้นผลต่างกัน

### กฎของ core ที่บังคับด้วยเทสต์

[`test_core_purity.py`](packages/core/tests/test_core_purity.py) อ่าน AST ของทุกไฟล์ใน core
แล้วบังคับ 4 ข้อที่ import-linter มองไม่เห็น: ฟังก์ชันที่ทำเลขคณิตต้องอยู่ใน `@calc` ·
ห้าม import clock/randomness/filesystem · ห้ามเรียก `open`/`print`/`eval` · ห้ามใช้ `float`

เขียนขึ้นเพราะ `@calc` ถูกลืมมาแล้ว **สองครั้ง** และทั้งสองครั้งหลุด review ไปจนถึงรอบถัดไป —
การจำกฎไม่พอ ต้องให้เครื่องตรวจ

---

## 6. Source of truth

อย่าเขียนกติกาหรือสูตรซ้ำในโค้ดหรือใน README นี้ ให้ลิงก์ไปที่ต้นทาง

| เรื่อง | ไฟล์ |
|---|---|
| Requirements, decisions (D-xx), Glossary | [`docs/requirements/mvp.md`](../docs/requirements/mvp.md) |
| Architecture, process model, flows | [`docs/architecture/architecture.md`](../docs/architecture/architecture.md) |
| Architecture decisions | [`docs/architecture/adr/`](../docs/architecture/adr/) |
| สูตร margin, PnL, liquidation, Paper Fill Model | [`docs/specs/calculation.md`](../docs/specs/calculation.md) |
| PostgreSQL schema | [`docs/specs/data-model.md`](../docs/specs/data-model.md) |
| REST / WebSocket contract, error codes | [`docs/specs/api.md`](../docs/specs/api.md) |
| กติกาสำหรับ coding agents | [`AGENTS.md`](../AGENTS.md) |

**ถ้าโค้ดกับ spec ไม่ตรงกัน ให้หยุดแล้วถามเจ้าของ** อย่าแก้ตามฝั่งใดฝั่งหนึ่งเงียบ ๆ

---

## 7. การดูแลเอกสาร

- **README นี้** อัปเดตเมื่อ public interface, dependency direction, สถานะ
  implemented/scaffold หรือคำสั่งรัน/ทดสอบเปลี่ยน
- **module README** เพิ่มเฉพาะ module ที่ซับซ้อนพอจนแผนที่ระดับบนไม่พอ — ตอนนี้ยังไม่มี
  module ไหนถึงเกณฑ์ (ดู [§8](#8-ทำไมยังไม่มี-module-readme))
- **docstring** ใช้สำหรับข้อจำกัดเฉพาะไฟล์หรือเฉพาะฟังก์ชัน เช่น เหตุผลที่ `liquidation_price`
  คืน `None`, ที่ `open_details()` ไม่ใช้ `assert` หรือ marker `Verify`
- ไม่ต้องสร้าง `.md` อธิบายทุกไฟล์ และไม่คัดลอกสูตรจาก specs มาไว้ในโค้ดหรือ README

---

## 8. ทำไมยังไม่มี module README

core ทั้งก้อนมี ~857 บรรทัดใน 3 module ที่มี `__init__.py` ประกาศ public API ชัดเจนอยู่แล้ว
และ docstring ในไฟล์ครอบคลุมข้อจำกัดเฉพาะจุด — README ย่อยตอนนี้จะซ้ำกับ §4 หรือกับ
calculation.md ซึ่งขัดกับกติกาใน §7

เกณฑ์ที่ควรเพิ่ม module README:

- module มีหลาย flow ที่ต้องอธิบายลำดับการเรียก ไม่ใช่แค่รายการฟังก์ชัน (เช่น engine
  ตอนมี Strategy host + Risk + OMS ครบ)
- มี state machine หรือ lifecycle ที่ docstring ไฟล์เดียวอธิบายไม่ครบ (เช่น
  Durable Command lifecycle ตาม ADR-0011)
- มี integration boundary ที่มีกับดักเฉพาะ เช่น `binance` ตอนมี rate limit, reconnect
  และ error mapping จริง

`margin/` เป็นตัวที่ใกล้เกณฑ์ที่สุดเพราะ liquidation ซับซ้อน แต่ตอนนี้ docstring ของ
`liquidation_price` อธิบายครบแล้ว ถ้าเพิ่ม Isolated/Multi-Assets หรือ Hedge mode เข้ามาอีก
ค่อยพิจารณาใหม่
