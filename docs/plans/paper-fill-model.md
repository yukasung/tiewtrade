# Plan: Paper Fill Model §4.1–4.3 — Trading Core

สถานะ: **อนุมัติแล้ว** 2026-09-23 · ยังไม่เริ่ม implement
ขอบเขต: calculation spec §4.1–4.3 · module `tiewtrade_core/execution/`


## Context

Phase 1 ของ TiewTrade เป็น **Paper trading อย่างเดียว** แต่ `tiewtrade_core` ยังไม่มี Paper Fill Model เลย
ตอนนี้ core มี `market/`, `portfolio/`, `margin/` (~857 บรรทัด) ซึ่งครอบคลุม reference data, การบันทึก
position และ margin/liquidation แล้ว แต่ยัง **ไม่มีอะไรตอบคำถามว่า "order นี้ fill ที่ราคาเท่าไร"**

ไม่มีชิ้นนี้ engine ประกอบ flow ของ Paper ไม่ได้เลย จึงเป็นงานที่อยู่บน critical path ของ Phase 1

`docs/specs/calculation.md` §4.1–4.3 กำหนดสูตรไว้ครบและเป็น **Decided ทั้งหมด ไม่มี marker Verify**
จึง implement ได้ทันทีโดยไม่ต้องรอยืนยันอะไรกับ Binance

**ผลลัพธ์ที่ต้องการ:** ฟังก์ชัน pure ที่รับ market data + พารามิเตอร์ แล้วคืนราคา fill และบอกว่าเป็น
Maker หรือ Taker — ทดสอบได้โดยไม่ต้องมี Binance credentials ตามที่ IMP-04 ใน review ระบุไว้

## ขอบเขต

**ทำ:** §4.1 Market · §4.2 Limit (marketable + resting) · §4.3 TP/SL trigger

**ไม่ทำรอบนี้ และเหตุผล:**

| ส่วน | เหตุผล |
|---|---|
| §4.4 Paper Liquidation | ติด **Verify** 2 จุด: clearance rate ต่อ symbol และการริบ isolated wallet — ต้องยืนยันกับ Binance ก่อน **อย่า stub ทิ้งไว้** |
| §4.5 Replay ด้วย Candle | ขึ้นกับ §4.1 **และ** §4.4 และต้องมี type `Candle` ใน `market/` ซึ่งยังไม่มี |
| `ExecutionAdapter` port + `PaperExecutionAdapter` class | ต้องใช้ `Order` / `ClientOrderId` จาก module `orders` ซึ่งยังไม่มี — **นี่คือข้อจำกัดด้านลำดับงานหลัก** ใส่เพิ่มใน package เดิมได้เมื่อ `orders` มา |
| ยกเลิกขาที่เหลือของ Bracket, reduce-only | เป็นงานของ Order Manager (FR-ORD-03/15, R-16) module นี้บอกแค่ว่า**ขาไหน trigger** |
| จำนวนเงิน fee และ ledger | `portfolio.trading_fee` + caller — module นี้คืนแค่ **role** ไม่ใช่ rate หรือจำนวนเงิน |
| ค่า `s`, maker/taker rate, ที่มาของ best bid/ask | เป็น config / service side (FR-ORD-07, 10, 13) |

## โครงสร้าง — `packages/core/src/tiewtrade_core/execution/`

ชื่อ `execution` มาจาก [architecture §4.2](../architecture/architecture.md)
ที่กำหนดไว้แล้วว่า module นี้เก็บ "port ExecutionAdapter + PaperExecutionAdapter (Paper Fill Model) +
trigger TP/SL/liquidation ของ Paper" และ §4.3 ระบุว่า `PaperExecutionAdapter` อยู่ใน core เพราะเป็น
การคำนวณล้วน — **ยืนยันกับเจ้าของแล้วว่าใช้ชื่อตาม architecture ไม่ใช่ `paper/`**

| ไฟล์ | เนื้อหา | Public |
|---|---|---|
| `__init__.py` | docstring อ้าง §4.1–4.3 + หมายเหตุแยกตัวเองจาก `tiewtrade_execution`; absolute import; `__all__` เรียง ASCII; ไม่มี logic | facade |
| `book.py` | `TopOfBook` (best bid/ask + `is_crossed`) | ✅ |
| `fills.py` | §4.1 + §4.2 และ `PaperFill` | ✅ |
| `triggers.py` | §4.3 `BracketLeg`, trigger predicates, `closing_side` | ✅ |
| *(เดิมวางไว้เป็น `_guards.py`)* | **ตัดออกตอน refactor** — `0 ≤ s < 1` เป็น private ใน `fills.py` ส่วนกฎราคาเป็นบวกย้ายไปเป็นของ `PaperFill.__post_init__` ตรงกับที่ `margin/` ไม่มี guard module | — |

แยก 4 ไฟล์ตามขอบเขตของ spec — §4.1 กับ §4.2 ใช้เลขคณิตชุดเดียวกันจึงอยู่ด้วยกัน ส่วน §4.3 เป็น
comparison ล้วนและไม่ import อะไรจาก `fills.py` เลย (`market/` ก็ 4 ไฟล์เหมือนกัน)

**ความเสี่ยงเรื่องชื่อ:** `tiewtrade_core.execution` (คณิตศาสตร์ล้วน) กับ package บริการ
`tiewtrade_execution` (Live gateway Phase 2 ถือ secret ที่ถอดรหัสแล้ว, P-10) เป็นคนละอย่างแต่ใช้คำเดียวกัน
บรรเทาด้วย: เขียนความต่างไว้ใน module docstring, import เต็มรูปเสมอ และ import-linter contract เดิม
ห้าม `tiewtrade_core` import `tiewtrade_execution` อยู่แล้ว ความสับสนจึงกลายเป็น dependency จริงไม่ได้

## Public API

### `LiquidityRole` → วางใน `market/enums.py`

```python
class LiquidityRole(StrEnum):      # calculation spec §1 (f_m / f_t), FR-ORD-08/10
    MAKER = "MAKER"
    TAKER = "TAKER"
```

ไม่มี maker/taker อยู่ที่ไหนในโค้ดเลยตอนนี้ — ต้องสร้างใหม่ วางใน `market/` เพราะ:
เป็นคำศัพท์ของ venue เหมือน `OrderSide` (Live fill ก็มี role นี้ ไม่ใช่เรื่องเฉพาะ Paper) ·
`execution` **ผลิต** ส่วน `portfolio` **บริโภค** และ `market` เป็น module เดียวที่ทั้งคู่ขึ้นด้วยกันอยู่แล้ว
ตาม architecture §4.2 (`market → portfolio`, `market → execution`) · ไม่มี edge `portfolio → execution`
และ**ไม่ควรสร้างขึ้นมาเพียงเพื่อ enum ตัวเดียว**

`portfolio/charges.py:trading_fee` **ไม่เปลี่ยน** (ยังรับ `fee_rate: Decimal` ที่ resolve มาแล้ว)

### `book.py`

```python
@dataclass(frozen=True, slots=True)
class TopOfBook:
    best_bid: Decimal
    best_ask: Decimal
    def __post_init__(self) -> None: ...   # ทั้งคู่ > 0 ไม่งั้น ValueError
    @property
    def is_crossed(self) -> bool: ...      # best_bid > best_ask  (ไขว้)
    @property
    def is_locked(self) -> bool: ...       # best_bid == best_ask (ล็อก)
    @property
    def is_abnormal(self) -> bool: ...     # is_crossed or is_locked  <- ตัวที่ service ควรใช้
```

**⚠️ ต้องมี 3 ตัวไม่ใช่ตัวเดียว (แก้จาก review):** Decision 2 พูดถึง `bid ≥ ask` แต่ร่างแรกมีแค่
`is_crossed` ที่นิยามเป็น `bid > ask` — **service ที่เช็กตัวเดียวจะพลาดกรณี `bid == ask`**
ซึ่งอยู่ในขอบเขตที่ตัดสินไว้ · แยกตามศัพท์ตลาดจริง (crossed ≠ locked) แล้วให้ `is_abnormal`
เป็นตัวที่ service เรียกใช้ · ทุกตัวเป็น comparison ล้วน ไม่ใส่ `@calc` · **ต้องมีเทสต์ `bid == ask` ชัดเจน**

### `fills.py`

```python
@dataclass(frozen=True, slots=True)
class PaperFill:
    price: Decimal
    liquidity: LiquidityRole

@calc
def market_fill(side: OrderSide, book: TopOfBook, *,
                slippage_rate: Decimal, tick_size: Decimal) -> PaperFill          # §4.1 → TAKER เสมอ

def is_marketable(side: OrderSide, limit_price: Decimal, book: TopOfBook) -> bool  # ไม่ใส่ @calc

@calc
def limit_fill_on_submit(side: OrderSide, limit_price: Decimal, book: TopOfBook, *,
                         slippage_rate: Decimal, tick_size: Decimal) -> PaperFill | None
                                                      # None = order ไปค้าง; ถ้า fill เป็น TAKER

def resting_limit_fills(side: OrderSide, limit_price: Decimal, last_price: Decimal) -> bool
def resting_limit_fill(side: OrderSide, limit_price: Decimal,
                       last_price: Decimal) -> PaperFill | None                    # ราคา = limit, MAKER
```

`slippage_rate` และ `tick_size` เป็น keyword-only ที่ caller ส่งมา — `s` ปรับได้โดย Platform Admin
(FR-ORD-07) **ห้าม hardcode หรืออ่าน config ใน core** · รับ `tick_size: Decimal` ไม่ใช่ `SymbolFilters`
เพราะไม่ได้ใช้ step/qty/notional เลย และตรงกับ signature ของ `round_to_increment` เอง

### `triggers.py`

```python
class BracketLeg(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"

def stop_loss_triggered(position_quantity, last_price, stop_price) -> bool
def take_profit_triggered(position_quantity, last_price, take_profit_price) -> bool
def triggered_leg(position_quantity, last_price, *,
                  stop_loss_price: Decimal | None,
                  take_profit_price: Decimal | None) -> BracketLeg | None
def closing_side(position_quantity: Decimal) -> OrderSide     # Long→SELL, Short→BUY
```

`position_quantity` เป็น signed ตาม spec §1 และ `FuturesPosition.quantity` · position ที่เป็น 0
โยน `ValueError("position is flat")`

### ⚠️ ต้องเป็น comparison ล้วน ห้ามมีเลขคณิต (แก้จาก review)

ร่างแรกเสนอย่อ 4 แถวของ §4.3 ด้วย `side * (last_price - stop_price) <= 0` — **ใช้ไม่ได้**
นั่นคือการลบและคูณ Decimal ซึ่งรันใน context ของ caller ไม่ใช่ `CALC` (เพราะไม่ได้ใส่ `@calc`)
พิสูจน์แล้ว: ภายใต้ context ที่ trap `Inexact` สูตรนี้ **โยน `Inexact`** ขณะที่การเปรียบเทียบตรง ๆ
คืนค่าปกติ

เขียนเป็นการเปรียบเทียบตรงตาม §4.3 ทั้ง 4 แถว ไม่แตะเลขคณิตเลย:

```python
is_long = position_quantity > 0
# SL: Long LP <= SL, Short LP >= SL
return last_price <= stop_price if is_long else last_price >= stop_price
# TP: Long LP >= TP, Short LP <= TP
return last_price >= take_profit_price if is_long else last_price <= take_profit_price
```

ยาวกว่าสองบรรทัดเล็กน้อย แต่ตรงกับตารางใน spec แบบอ่านแล้วเทียบได้ทันที และ**ไม่มีเลขคณิตให้
context ของ caller มามีผล** ทั้งสี่ฟังก์ชันจึงเป็น comparison ล้วนจริง → ไม่ใส่ `@calc` ได้อย่างถูกต้อง

**บทเรียนที่ใช้กับทั้ง module:** "ไม่ใส่ `@calc`" ถูกต้องเฉพาะเมื่อฟังก์ชันนั้น**ไม่มีเลขคณิต Decimal
จริง ๆ** ตรวจแล้วว่าตัวอื่นปลอดภัย: `closing_side`, `is_crossed`, `is_locked`, `is_marketable`,
`resting_limit_fills`, `resting_limit_fill` เป็นการเปรียบเทียบหรือส่งค่าผ่านทั้งหมด

## จุดที่ต้องระวังตอน implement

### §4.2 ประกอบกับ §4.1 โดยไม่เขียนสูตรซ้ำ

`_market_fill_price` เป็น**ที่เดียว**ที่มี `× (1 ± s)` และการปัด tick

```python
@calc
def _market_fill_price(side, book, *, slippage_rate, tick_size) -> Decimal:
    # §4.1 ล้วน ๆ ไม่ validate ผลลัพธ์ เพราะอาจเป็นค่ากลางทางของ §4.2

@calc
def market_fill(side, book, *, slippage_rate, tick_size) -> PaperFill:
    price = _market_fill_price(...)
    require_positive_price(price)          # ราคาสุดท้ายของ §4.1 -> validate ตรงนี้
    return PaperFill(price, TAKER)

@calc
def limit_fill_on_submit(side, limit_price, book, *, slippage_rate, tick_size) -> PaperFill | None:
    if not is_marketable(...):
        return None
    capped = _cap_to_limit(side, _market_fill_price(...), limit_price)
    require_positive_price(capped)         # validate เฉพาะราคาสุดท้าย
    return PaperFill(capped, TAKER)
```

### ⚠️ validate ราคาสุดท้ายเท่านั้น ห้าม validate ค่ากลางทาง (แก้จาก review)

ร่างแรกให้ `limit_fill_on_submit` เรียก `market_fill` ตรง ๆ แล้วค่อย cap — **ใช้ไม่ได้** เมื่อรวมกับ P-3
ที่เสนอให้โยน error ถ้าราคาปัดลงเป็น 0 เพราะค่ากลางทางที่เป็น 0 จะบล็อก fill ที่ถูกต้อง

เคสจริงที่พิสูจน์แล้ว: `bid = 1`, `s = 0.02`, `tick = 1`, Sell limit = 1
→ marketable (`limit ≤ bid`) → §4.1 ให้ `floor_tick(0.98) = 0` → P-3 โยน error
→ **แต่ §4.2 กำหนดว่า `max(limit, 0) = 1` ซึ่งเป็นราคาที่ถูกต้องสมบูรณ์**

แก้ด้วยการแยก `_market_fill_price` (ไม่ validate) ออกจาก `market_fill` (validate) ตามโค้ดข้างบน
ค่า 0 กลางทางจึงผ่านไปให้ cap จัดการได้ ส่วนราคาที่ออกจาก module จริง ๆ ยังถูกตรวจทุกเส้นทาง

**ลำดับสำคัญ: ปัดก่อน แล้วค่อย cap** — การ cap คือสิ่งที่ทำให้ FR-ORD-08 ("fill ไม่แย่กว่าราคา Limit")
เป็นจริงแม้การปัด tick จะดันราคาเลย limit ไป · **ห้ามปัดซ้ำหลัง cap** เพราะการปัดไปทางเสียเปรียบ
จะทำลาย cap ที่เพิ่งทำ · precondition: `limit_price` ต้องตรง tick อยู่แล้ว (บังคับ upstream ด้วย
`SymbolFilters.violations` → `FilterViolation.TICK`) เมื่อเป็นเช่นนั้น min/max ของพหุคูณ tick สองตัว
ยังเป็นพหุคูณ tick — **เขียน precondition ไว้ใน docstring ไม่ต้อง validate ซ้ำใน core**

แยก `_cap_to_limit(side, price, limit)` เป็น private ให้การเลือก min/max อยู่ที่เดียว

### "ทะลุ ไม่ใช่แตะ"

ให้ฟังก์ชันเดียวเป็นเจ้าของการเปรียบเทียบ แล้ว `resting_limit_fill` เรียกต่อ เพื่อไม่ให้ความเข้มงวด
เพี้ยนกันระหว่าง predicate กับตัว fill:

```python
return last_price < limit_price if side is OrderSide.BUY else last_price > limit_price
```

**เขียนคอมเมนต์ทั้งใน `fills.py` และ `triggers.py`** ว่า resting limit ใช้ `<`/`>` แบบเข้ม ส่วน trigger
ของ §4.3 ใช้ `<=`/`>=` แบบรวมการแตะ — ความไม่สมมาตรนี้ดูเหมือน bug สำหรับคนอ่านในอนาคต ทั้งที่เป็นไปตาม spec

## Decisions ที่เจ้าของเคาะแล้วในรอบวางแผนนี้

| # | ประเด็น | ผลการตัดสิน |
|---|---|---|
| 1 | ชื่อ module | ใช้ `execution` ตาม architecture §4.2 ไม่ใช่ `paper` |
| 2 | Book ผิดปกติ (`bid ≥ ask`) | **รับไว้และคำนวณตามข้อมูลที่ได้** เปิด `is_crossed` (`>`), `is_locked` (`==`) และ `is_abnormal` (รวมทั้งสอง) ให้ service ทิ้ง snapshot ที่ผิดปกติเอง — core ไม่ตัดสินว่าข้อมูลดีหรือเสีย |
| 3 | tick เดียวกัน TP และ SL จริงพร้อมกัน | **SL ชนะเสมอ** สอดคล้องกับ §4.5 (Decided C-09) และหลัก D-05 ว่าผล Paper ต้องไม่ดูดีเกินจริง |
| 4 | ขอบเขตของ `s` (เดิม P-1) | **บังคับ `0 ≤ s < 1` ใน core** โยน `ValueError` ถ้าหลุดช่วง · `s < 0` จะ fill ดีกว่าราคาตลาด ขัด D-05 · `s ≥ 1` ทำให้ราคาขาย ≤ 0 · `s = 0` อนุญาต (FR-ORD-07 ระบุแค่ค่า default) |
| 5 | ราคาปัดลงจนเป็น 0 หรือติดลบ (เดิม P-3) | โยน `ValueError("fill price must be positive")` และ**ตรวจเฉพาะราคาสุดท้าย** ไม่ใช่ค่ากลางทางของ §4.2 · บันทึกเป็น **C-18** ใน calculation.md §8 · implement โดยให้ `PaperFill.__post_init__` เป็นเจ้าของกฎ ผู้ผลิต fill รายใหม่ (§4.4, §4.5) จึงได้การตรวจโดยไม่ต้องจำ |

## Proposed — ยังต้องให้เจ้าของเคาะก่อน merge

ตาม AGENTS.md ห้ามตัดสินข้อกำหนดที่กำกวมเอง ข้อที่ตกลงแล้วให้บันทึกเป็น `C-xx` ใน calculation.md §8

สถานะของข้อที่เหลือ: **โค้ดทำตาม spec ตรงตัวแล้ว** และไม่ได้บล็อกอะไร สิ่งที่ขอคือให้เจ้าของ
ยืนยันว่าอ่าน spec ตรงกัน (P-2, P-4) หรือยืนยันขอบเขตที่ตัดออก (P-5, P-6) — ถ้ายืนยันแล้วค่อย
เลื่อนขึ้นไปเป็น Decision และบันทึก `C-xx` เหมือน P-1 กับ P-3

| # | ประเด็น | ข้อเสนอ |
|---|---|---|

| P-2 | marketable limit ที่ราคาเท่ากับ BestAsk พอดี | ตาม spec ตรงตัว: marketable แล้ว cap ผูกพัน → fill ที่ limit **โดยไม่โดน slippage เลย** เป็นไปตาม FR-ORD-08 ที่ปรับในรีวิว 2026-09-22 แต่เป็นจุดอ่อนของหลัก "ไม่ดูดีเกินจริง" — ขอให้ยืนยันว่าตั้งใจ |
| P-4 | resting limit ดูแค่ Last Price | ตาม §4.2 และ FR-ORD-13 ตรงตัว — ขอให้ยืนยัน เพราะ book จริงเทรดทะลุ limit ได้โดย LP ไม่ print ทะลุ |
| P-5 | clamp จำนวน reduce-only ตอน TP/SL trigger | เป็นงานของ Order Manager (FR-ORD-14..17) อยู่นอก fill model — ขอให้ยืนยัน |
| P-6 | `FeeSchedule(maker_rate, taker_rate)` พร้อม `rate_for(role)` | ไม่จำเป็นสำหรับ §4.1–4.3 เสนอทำตอนต่อสาย Order Manager และวางไว้ข้าง `trading_fee` ใน `portfolio/charges.py` เพื่อให้ `execution` ไม่รู้จักเรื่อง fee เลย |

## ของเดิมที่ต้องใช้ซ้ำ (อย่าเขียนใหม่)

| ของเดิม | ที่อยู่ |
|---|---|
| `round_to_increment(value, increment, rounding)` · `Rounding.UP/DOWN` | `market/rounding.py:12` และ `:7` — `UP`=ceiling, `DOWN`=floor **ไปทาง ±infinity** รองรับ increment ที่ไม่ใช่กำลังสิบ |
| `OrderSide` + `.sign` (+1/−1) | `market/enums.py` |
| `@calc`, `ZERO`, `ONE` | `_decimal.py:21` |
| `SymbolFilters.violations` (บังคับ tick upstream) | `market/symbol.py:32` |
| แบบแผน private guard | `portfolio/_fill.py:4` |
| `trading_fee(quantity, price, fee_rate)` | `portfolio/charges.py:6` — **ไม่แก้** |

## ข้อบังคับด้านสไตล์

`@dataclass(frozen=True, slots=True)` + validate ใน `__post_init__` · ใส่ `@calc` ทุกฟังก์ชันที่ทำเลขคณิต
Decimal และ **ไม่ใส่**กับ comparison/accessor ล้วน (ตามแบบ `require_positive_fill`, `is_flat`,
`is_liquidatable`) · property ใช้ `@property` แล้ว `@calc` (calc อยู่ใน) · `__init__.py` มี docstring
บรรทัดเดียวอ้าง spec, absolute import, `__all__` เรียง ASCII, ไม่มี logic

## Test plan

`tests/test_execution.py` (ตัวอย่างมีเลขจริง) และ `tests/test_execution_properties.py` (hypothesis) —
AGENTS.md บังคับว่าโค้ดคำนวณต้องมี**ทั้งสองแบบ** · import จาก facade สาธารณะเท่านั้น ·
`from decimal import Decimal as D` · `conftest.py` ตั้ง `setcontext(DECIMAL_CONTEXT.copy())` ให้แล้ว

### ตัวอย่างที่ **ตรวจกับ `round_to_increment` จริงแล้วทั้งหมด** (tick 0.1, s 0.02% เว้นที่ระบุ)

| เคส | input | คาดหวัง |
|---|---|---|
| Buy ลงตัวพอดี | ask 60000.0 | 60012.0 TAKER |
| Buy ปัดขึ้นเสียเปรียบ | ask 60000.1 → 60012.10002 | **60012.2** TAKER |
| Sell ปัดลงเสียเปรียบ | bid 60000.1 → 59988.09998 | **59988.0** TAKER |
| tick 0.5, s 0.1% buy | ask 101.5 → 101.6015 | 102.0 |
| tick 0.5, s 0.1% sell | bid 101.5 → 101.3985 | 101.0 |
| s = 0 | ask 60000.1 | 60000.1 |
| **cap ผูกพัน (รีวิวข้อ 8)** | Buy limit 60012.1, ask 60000.1 (§4.1 = 60012.2) | **60012.1** TAKER |
| cap ไม่ผูกพัน | Buy limit 60013.0, ask 60000.1 | 60012.2 TAKER |
| marketable พอดีที่ touch | Buy limit 60000.1 == ask | 60000.1 TAKER |
| ไม่ marketable | Buy limit 59000, ask 60000.1 | `None` |
| resting Buy แตะ | limit 59000, LP 59000 | `None` |
| resting Buy ทะลุ | limit 59000, LP 58999.9 | 59000 MAKER |
| SL ครบวงจร | Long, SL trigger, bid 57990.0 → SELL | **57978.4** TAKER |

§4.3: Long `q=+0.5`, SL 58000, TP 62000 → LP 58000 = `STOP_LOSS` (แตะก็ยิง) · LP 58000.1 = `None` ·
LP 62000 = `TAKE_PROFIT` · ทั้งคู่จริง = `STOP_LOSS` · Short `q=−0.5` กลับด้าน

### Property tests

strategies ระดับ module: `prices = st.decimals(min_value="1", max_value="200000", places=2)` ·
`slippages = st.decimals(min_value="0", max_value="0.05", places=6)` ·
`ticks = st.sampled_from([D("0.0001"), D("0.01"), D("0.1"), D("0.5"), D("1")])` ·
limit ที่ตรง tick สร้างในเทสต์ด้วย `round_to_increment`

**⚠️ ต้องกันเคสที่ guard ปฏิเสธออกจาก property ที่ยืนยันราคา (แก้จาก review):** generator ข้างบน
สร้าง `bid = 1`, `tick = 1`, `s > 0` ได้ ซึ่งทำให้ Market Sell ปัดลงเป็น 0 แล้ว P-3 โยน error →
property ข้อ 1–4 ที่ยืนยันราคาแบบไม่มีเงื่อนไขจะ **error ไม่ใช่ falsify** แยกเป็นสองกลุ่ม:

- **กลุ่ม fill สำเร็จ** (ข้อ 1–11) ใส่ `assume(round_to_increment(bid*(1-s), tick, DOWN) > 0)`
  เพื่อตัดเคสที่ราคาเป็นศูนย์ออก เขียน comment กำกับว่าตัดออกเพราะอะไร ไม่ใช่ซ่อนปัญหา
- **กลุ่มปฏิเสธ** (ข้อ 12) เป็นเทสต์แยกที่**ตั้งใจ**ป้อนเคสราคาปัดลงเป็นศูนย์แล้วยืนยันว่า raise

1. Market Buy fill ≥ `best_ask` และ Sell fill ≤ `best_bid` เสมอ ทุก `s ≥ 0` — **การจำลองห้ามดีกว่าราคาตลาด**
2. เข้มกว่า: `ask×(1+s) ≤ buy_fill < ask×(1+s) + tick` และกลับด้านสำหรับ sell — ปัดได้ไม่เกิน 1 tick และเสียเปรียบเสมอ
3. ราคา fill ทุกค่าเป็นพหุคูณของ `tick_size`
4. Buy fill ไม่ลดลงเมื่อ `s` เพิ่ม · Sell fill ไม่เพิ่มขึ้น
5. marketable limit ไม่เคย fill แย่กว่า limit: Buy `fill ≤ limit`, Sell `fill ≥ limit`
6. limit ที่ทะลุลึกมาก → `limit_fill_on_submit == market_fill` เป๊ะ และเป็น TAKER
7. **แตะ resting limit ไม่เคย fill**: `resting_limit_fill(side, p, p) is None` ทุก `p` ทั้งสองข้าง
8. เมื่อ resting limit fill ราคา `== limit` เป๊ะ และเป็น MAKER (maker ไม่โดน slippage)
9. `resting_limit_fills` monotone ตาม `last_price`
10. trigger สมมาตรแบบกระจก Long/Short และ monotone ตาม `last_price`
11. bracket ที่ตั้งถูก (Long `SL < TP`) → predicate ทั้งสองไม่มีทางจริงพร้อมกัน ลำดับความสำคัญจึงไม่มีผลจริง
12. input ผิดต้อง raise ไม่ใช่คืนค่าเงียบ ๆ: `s` ติดลบ, tick ≤ 0, quote ≤ 0, position flat,
    และ**ราคาที่ปัดลงเป็นศูนย์** (เทสต์แยกตามข้างบน)

### เทสต์ caller context (เพิ่มจาก review)

ฟังก์ชันที่ไม่ใส่ `@calc` ต้องพิสูจน์ได้ว่าไม่มีเลขคณิต Decimal ซ่อนอยู่ — เรียกทุกตัว
(`closing_side`, `is_crossed`, `is_locked`, `is_abnormal`, `is_marketable`, `resting_limit_fills`,
`resting_limit_fill`, `stop_loss_triggered`, `take_profit_triggered`, `triggered_leg`) ภายใต้
context ที่เป็นศัตรู:

```python
with localcontext(Context(prec=5, traps=[Inexact, Rounded])):
    ...   # ต้องไม่ raise และให้ผลเดียวกับตอนรันใน DECIMAL_CONTEXT
```

เทสต์นี้คือสิ่งที่จับ bug สูตร trigger ของร่างแรกได้ ถ้าไม่มีจะหลุดไปถึง production

## ลำดับงาน

1. `LiquidityRole` เข้า `market/enums.py` + export + เทสต์บรรทัดเดียวใน `test_market.py`
2. `execution/book.py` (guard ของ slippage ลงเอยเป็น private ใน `fills.py` ไม่ได้แยกไฟล์)
3. `execution/fills.py` — §4.1 ก่อน แล้ว §4.2 ต่อยอด
4. `execution/triggers.py` (อิสระจากข้อ 2–3 ทำคู่ขนานได้)
5. `execution/__init__.py` facade — `__all__` เรียง ASCII: `["BracketLeg", "PaperFill", "TopOfBook", "closing_side", "is_marketable", "limit_fill_on_submit", "market_fill", "resting_limit_fill", "resting_limit_fills", "stop_loss_triggered", "take_profit_triggered", "triggered_leg"]` (`_market_fill_price`, `_cap_to_limit`, `require_positive_price` เป็น private ไม่ export; `is_crossed`/`is_locked`/`is_abnormal` เป็น property ของ `TopOfBook` จึงไม่อยู่ใน `__all__`)
6. `tests/test_execution.py` แล้ว `tests/test_execution_properties.py` — รวมเทสต์ caller context และเทสต์ `bid == ask`
7. บันทึก decision 2–3 และ Proposed ที่เจ้าของเคาะ เป็น `C-xx` ใน calculation.md §8 + อัปเดตเอกสารที่ขึ้นต่อกันตามกฎ AGENTS.md
8. อัปเดต `docs/implementation-status.md` และ `backend/README.md` (§4 ตาราง module + §1 ลำดับการอ่าน)

**ไม่ต้องแก้ `backend/pyproject.toml`** — ไม่มี top-level package ใหม่ และ core ยังไม่มี layered contract
ภายใน (ถ้าจะเพิ่มทีหลัง `execution` อยู่เหนือ `market`)

## Verification

```sh
cd backend
uv run ruff check . && uv run ruff format --check .
uv run mypy                # strict สำหรับ tiewtrade_core
uv run lint-imports        # ต้องยังเป็น 6 contracts kept, 0 broken
uv run pytest              # 62 tests เดิมต้องไม่พัง + เทสต์ใหม่
```

ตรวจเพิ่มว่า:

- `uv run pytest --collect-only -q | tail -3` เก็บเทสต์ใหม่ได้จริง (testpaths ครอบคลุมอยู่แล้ว)
- `lint-imports` ยังเขียว — พิสูจน์ว่า `execution` ไม่ได้ลาก dependency ต้องห้ามเข้า core
- เทสต์ property ข้อ 1 และ 7 คือสองตัวที่สำคัญที่สุด: ข้อ 1 กันไม่ให้ผล Paper ดูดีเกินจริง (D-05)
  ข้อ 7 กันไม่ให้ "แตะ" กลายเป็น fill (FR-ORD-08)
- ตรวจด้วยตาว่า `grep -rn "0.0002" packages/core/src` **ไม่เจออะไร** — ยืนยันว่าไม่มีการ hardcode `s`
