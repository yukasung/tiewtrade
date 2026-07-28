# TiewTrade Architecture

## Feature-first Modular Monolith

TiewTrade ใช้ application เดียวที่แบ่ง Module ตาม capability ของผลิตภัณฑ์ โดย business rules ไม่ขึ้นกับ UI, database หรือ exchange SDK

## Shared Business Rules

Paper และ Live ใช้ implementation เดียวกันของ business rules สำหรับ:

- Session identity และ immutable Preset
- Strategy และ Entry Intent
- Capital allocation
- Basket และ Entry Pair/Cooldown Month
- Risk limits, PnL calculation และ post-Liquidation lifecycle rules

`trading` เป็นเจ้าของ Futures side-aware PnL และ margin policy รวมถึง One-way Mode,
Cross Margin, leverage, shared risk limits และ post-Liquidation lifecycle rules

อำนาจตัดสิน Liquidation แยกตาม Mode:

- Paper Futures ให้ `trading` คำนวณ deterministic `liquidation_price` และใช้
  completed-Candle price-crossing predicate เพื่อให้ replay และ tests ทำซ้ำได้
- Live Futures ใช้ Binance position/account facts เป็น authoritative state และ Binance
  Liquidation Engine เป็นผู้ตัดสินและดำเนินการ Liquidation จริง สูตร Paper Futures
  ไม่ใช่ Live verdict

การใช้ implementation ร่วมกันทำให้ Strategy, capital, Basket, Entry Pair, risk limits
และการเปลี่ยน lifecycle หลัง Liquidation สอดคล้องกัน แต่ไม่ทำให้ Paper simulation
แทน authority ของ Exchange ใน Live Mode

## Execution Adapters

Execution เป็น seam ที่แยก side effects ออกจาก business rules โดยมี adapter แยกตาม Mode และ Market Type:

| Mode | Market Type | Adapter responsibility |
| --- | --- | --- |
| Paper | Spot/Futures | จำลอง Fill, fee และ slippage โดยไม่ส่งคำสั่งจริง; Paper Futures Phase แรกบันทึก Funding Fee เป็น `0.00` |
| Live | Spot | ส่งคำสั่ง Spot หลัง Preflight, idempotency และ reconciliation |
| Live | Futures | จัดการ Futures order, margin, leverage, funding และ reconciliation |

Paper และ Live ห้ามใช้ execution implementation เดียวกัน เพราะ failure modes, account facts และ side effects ต่างกัน แม้จะใช้ business rules ร่วมกัน

`execution` เป็นเจ้าของ Paper fills และ deterministic simulation โดยไม่คำนวณหรือเปลี่ยน
business policy

## Configuration Boundary

`SessionConfig` เป็น shared configuration ที่เก็บ session ID, Preset version, Market Type, Trade Mode, capital และ execution costs

หนึ่ง installation ใช้ Binance Account เดียวและมี Active Bot Session ได้สูงสุดหนึ่ง Session ทุก Basket, Entry, Order, Fill, PnL และ audit record ผูกกับ `session_id` โดยตรง

Market identity ต้องเป็นข้อมูลจาก configuration ไม่ใช่ค่าคงที่ใน strategy หรือ market-data pipeline:

| Configuration | เจ้าของ | กติกา |
| --- | --- | --- |
| `symbol` | Session/market configuration | เลือก symbol ที่ exchange รองรับ |
| `timeframe` | Session/market configuration | เลือก `3m`, `5m`, `15m`, `30m`, `1h`, `4h` และตรึงตลอด Session |
| `timezone` | System policy | ใช้ `UTC` เท่านั้น |
| `trade_mode`, `market_type` | `SessionConfig` | ใช้เลือก execution boundary |
| `preset_version` | Strategy preset | กำหนด RSI, TP, entry และ lifecycle rules |
| `max_entries` | `EntryPolicy` | ใช้ร่วมกันทุก Market Type และตรึงตลอด Session |
| `trading_capital_ratio` | `SpotTradingPolicy` | ใช้เฉพาะ Spot, รับจาก form และตรึงตลอด Session |

ค่าต้นทุนและความเสี่ยง เช่น fee, slippage, funding, leverage, margin mode และ collateral buffer ต้องถูกแยกตาม market/execution policy และ validate ก่อนสร้าง runtime

Configuration นี้ไม่มี side effect และไม่เลือกหรือเรียก adapter โดยตรง การเลือก adapter ต้องเกิดที่ application composition seam และ `TradeMode.LIVE` ต้องผ่าน Preflight กับ explicit confirmation ก่อนเสมอ

## Dependency Direction

Business rules ไม่ import Binance SDK, SQLite หรือ UI รายละเอียด integration ต้องอยู่ใน adapter ที่ implement interface ของ consumer Module

Live Binance integration และ reconciliation เป็นเจ้าของการอ่าน `liquidationPrice`,
`markPrice` และ maintenance-margin facts จาก Exchange แล้วสะท้อน authoritative state
เข้า application boundary โดย `trading` ห้าม import Binance SDK หรือรู้จัก transport
รายละเอียดนี้

`application` เป็นเจ้าของ completed-candle orchestration ที่จัดลำดับ `trading` policy
และ `execution` adapter ห้ามมี reverse dependency จาก `trading` หรือ `execution` กลับไป
หา `application` และห้าม Module ใดเข้าถึง Binance Private API นอกจาก concrete Live
integration ที่ส่งมอบตาม Live gate

## Desktop UI Boundary

`ui` ใช้ PySide6 เป็น thin presentation layer โดยแปลงค่าจาก form เป็น application
request และแสดง durable result เท่านั้น UI ห้าม import SQLite, Strategy หรือ Execution
adapter โดยตรง และงาน persistence ต้องทำผ่าน focused worker นอก UI thread

Application layer เป็นเจ้าของ `Create Paper Session` use case ซึ่งสร้าง shared immutable
Session/market configuration ก่อนเรียก concrete SQLite adapter การสร้าง Session เป็น
durable configuration step และไม่เริ่ม Market Data, Strategy หรือ Execution

## Persistence Boundary

`application` เป็นเจ้าของ business Session orchestration และลำดับ shared rules
ส่วน `integrations/sqlite` เป็นเจ้าของ transaction, durable mapping และ
persistence-specific fail-closed coordinator ที่ครอบ concrete application Session
โดย coordinator นี้ทำได้เฉพาะเรียก Session, บันทึกผลแบบ synchronous และปิดรับ
candle ถัดไปเมื่อยืนยัน durability ไม่ได้ ห้ามคำนวณหรือเปลี่ยน business decision

ช่วงที่มี persistence adapter เพียงแบบเดียวให้ใช้ concrete coordinator ได้โดยไม่สร้าง
generic interface ล่วงหน้า เมื่อมี consumer ของ persistence adapter อย่างน้อยสองแบบ
จึงค่อยย้าย contract ไปไว้ที่ Module ผู้ใช้งาน
