# TiewTrade Architecture

## Feature-first Modular Monolith

TiewTrade ใช้ application เดียวที่แบ่ง Module ตาม capability ของผลิตภัณฑ์ โดย business rules ไม่ขึ้นกับ UI, database หรือ exchange SDK

## Shared Business Rules

Paper และ Live ใช้ implementation เดียวกันของ business rules สำหรับ:

- Session identity และ immutable Preset
- Strategy และ Entry Intent
- Capital allocation
- Basket และ Entry Pair/Cooldown Month
- Risk policies และ PnL calculation

การใช้ implementation ร่วมกันทำให้ Paper replay และ Live decision ใช้กติกาเดียวกัน ลดความเสี่ยงที่ผลทดสอบกับผลใช้งานจริงจะแตกต่างกัน

## Execution Adapters

Execution เป็น seam ที่แยก side effects ออกจาก business rules โดยมี adapter แยกตาม Mode และ Market Type:

| Mode | Market Type | Adapter responsibility |
| --- | --- | --- |
| Paper | Spot/Futures | จำลอง Fill, fee, slippage และ funding โดยไม่ส่งคำสั่งจริง |
| Live | Spot | ส่งคำสั่ง Spot หลัง Preflight, idempotency และ reconciliation |
| Live | Futures | จัดการ Futures order, margin, leverage, funding และ reconciliation |

Paper และ Live ห้ามใช้ execution implementation เดียวกัน เพราะ failure modes, account facts และ side effects ต่างกัน แม้จะใช้ business rules ร่วมกัน

## Configuration Boundary

`SessionConfig` เป็น shared configuration ที่เก็บ session ID, Account Profile ID, Preset version, Market Type, Trade Mode, capital และ execution costs

Market identity ต้องเป็นข้อมูลจาก configuration ไม่ใช่ค่าคงที่ใน strategy หรือ market-data pipeline:

| Configuration | เจ้าของ | กติกา |
| --- | --- | --- |
| `symbol` | Session/market configuration | เลือก symbol ที่ exchange รองรับ |
| `timeframe` | Session/market configuration | กำหนด candle interval เช่น `5m` |
| `timezone` | System policy | ใช้ `UTC` เท่านั้น |
| `trade_mode`, `market_type` | `SessionConfig` | ใช้เลือก execution boundary |
| `preset_version` | Strategy preset | กำหนด RSI, TP, entry และ lifecycle rules |

ค่าต้นทุนและความเสี่ยง เช่น fee, slippage, funding, leverage, margin mode และ collateral buffer ต้องถูกแยกตาม market/execution policy และ validate ก่อนสร้าง runtime

Configuration นี้ไม่มี side effect และไม่เลือกหรือเรียก adapter โดยตรง การเลือก adapter ต้องเกิดที่ application composition seam และ `TradeMode.LIVE` ต้องผ่าน Preflight กับ explicit confirmation ก่อนเสมอ

## Dependency Direction

Business rules ไม่ import Binance SDK, SQLite หรือ UI รายละเอียด integration ต้องอยู่ใน adapter ที่ implement interface ของ consumer Module
