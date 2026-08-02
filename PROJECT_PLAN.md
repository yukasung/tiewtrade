# TiewTrade Project Plan

## วัตถุประสงค์

เอกสารนี้กำหนดลำดับการส่งมอบ dependencies และ quality gates ของ TiewTrade
Internal Alpha โดยใช้ `PRODUCT.md` เป็นขอบเขตผลิตภัณฑ์, `CONTEXT.md` เป็นคำศัพท์และ
กฎโดเมน และ `ARCHITECTURE.md` เป็นเจ้าของ Module กับ dependency rules

หาก implementation plan ราย issue ขัดกับเอกสารทั้งสามชุด ต้องแก้แผนให้ตรงก่อนเริ่ม
production code

## Delivery Principles

- ส่งมอบแบบ Paper-first: พิสูจน์ flow ด้วย Paper Trading ก่อนเปิด Live
- Paper-first ไม่ใช่ Paper-only business logic; Strategy, capital, Basket, Entry Pair,
  risk policy และ PnL ใช้ implementation ร่วมกันทุก Trade Mode
- Paper, Live Spot และ Live Futures ใช้ execution adapters แยกกัน
- ค่าใน form ต้องผ่าน validation และกลายเป็น immutable Session configuration/policy
- `trading_capital_ratio`, `max_entries`, symbol และ timeframe ห้าม hard-code ใน
  business logic
- 80% และ 10 Entries เป็นค่าเริ่มต้นของ form เท่านั้น
- หนึ่ง installation ใช้ Binance Account เดียวและมี Active Bot Session ได้สูงสุดหนึ่ง Session
- สร้าง Module หรือ seam เมื่อมีพฤติกรรมและ consumer จริง ไม่สร้างโครงว่างล่วงหน้า
- ระหว่างพัฒนาใช้ Paper และ fake adapters เท่านั้น ห้ามส่ง Live order

## Delivery Order

```mermaid
flowchart LR
    F[Shared Core Foundation]
    T[Paper Spot Tracer Bullet]
    P[Paper Trading Complete]
    S[Live Spot]
    U[Live USDⓈ-M Futures]
    F --> T --> P --> S --> U
```

แต่ละ milestone ต้องผ่าน acceptance และ verification ของตนเองก่อนเริ่ม milestone
ถัดไป การผ่าน technical gate ไม่ได้เปิด Live อัตโนมัติ; Live ต้องผ่าน Preflight และ
การยืนยันจากผู้ใช้เสมอ

## Milestone 1 — Shared Core Foundation

Foundation ที่พร้อมใช้งานแล้วประกอบด้วย:

- shared immutable `SessionConfig` สำหรับ Paper และ Live
- `MarketDataConfig`, immutable Candle และ completed-candle continuity
- `EntryPolicy` และ `SpotTradingPolicy` ที่รับค่าจาก Session setup
- Spot capital allocation, symbol quantization และ minimum-notional check
- Basket weighted average, Take Profit, realized PnL และ atomic state transitions
- Entry Pair และ Cooldown Month lifecycle แบบ UTC

Foundation ไม่เลือก execution adapter และไม่มี side effect ไปยัง Binance

## Milestone 2 — Paper Spot Tracer Bullet

Tracer Bullet เป็น headless flow สำหรับพิสูจน์ shared core ผ่าน Paper Spot โดยใช้
BTCUSDT 5m เป็น acceptance scenario ที่ส่งผ่าน configuration ไม่ใช่ค่าคงที่ใน
business logic

ลำดับงานที่เหลือ:

1. DEV-78 — สร้าง RSI Step Grid Preset, Wilder RSI/ATR และ deterministic Entry Intent
2. DEV-79 — เชื่อม Strategy, Capital, Basket และ lifecycle ใน application
   orchestration กับ concrete Paper Spot execution adapter
3. DEV-80 — Replay CSV 40 Candles, สร้าง stable JSON summary และพิสูจน์ว่า
   replay ข้อมูลเดิมสองครั้งได้ output ตรงกันทุกตัวอักษร

Implementation details อยู่ใน
`docs/superpowers/plans/2026-07-20-paper-spot-core-tracer-bullet.md`

Tracer Bullet ยังไม่ถือว่า Paper Trading Complete เพราะยังไม่มี persistence,
Recovery, Paper Futures, public market-data runtime และ Desktop UI

## Milestone 3 — Paper Trading Complete

ส่งมอบ vertical slices ต่อจาก tracer ตามลำดับ dependency:

1. บังคับ one Active Bot Session สำหรับ installation และ Session ownership โดยตรง
2. เพิ่ม SQLite migrations, durable trade history, audit trail และ Recovery state
3. Public Binance market-data adapter, reconnect, backfill และ stale-data fail closed
4. Paper Futures Core: shared Futures PnL policy, immutable session policy, leverage, Cross Margin, Collateral Buffer, liquidation และ Funding Fee `0.00`
5. Paper Futures Execution: concrete executor และ deterministic Paper fills
6. DEV-95 — เชื่อม Paper Futures เข้ากับ Trade History ด้วย normalized
   Basket/Fill schema, immutable leverage context, Funding Fee `0.00` และ
   atomic/idempotent SQLite flow เดียวกับ Spot
7. Desktop Session Setup vertical slice: สร้าง immutable Active Paper Session แบบ
   atomic, แสดง durable Overview และวาง Thin PySide6 worker boundary
8. DEV-96 — เพิ่ม Trade History UI หลัง Desktop Session Setup acceptance gate ผ่าน
9. Desktop UI สำหรับ Dashboard, Orders, Positions และ Notifications
10. Stop Session, startup Recovery และ deterministic reconciliation ด้วย fake adapters
11. Paper acceptance ครบทั้ง business rules, persistence, UI และ Recovery

สถานะ DEV-92–DEV-95: durable SQLite Trade History รองรับ normalized Basket/Fill
ของ Paper Spot และ Paper Futures, exact Decimal/UTC round-trip, deterministic IDs,
atomic writes, idempotent duplicate handling, ownership/lifecycle validation,
fail-closed Session state และ immutable Futures leverage context รวมทั้ง application
query สำหรับ filter, deterministic ordering, pagination, total count และ
closed-Basket Net Realized PnL แล้ว ส่วน Desktop UI และ startup Recovery ยังคงอยู่ใน
ลำดับถัดไปของ milestone นี้

สถานะ DEV-99: public Binance market-data Runtime รองรับ Historical Warm-up,
completed-candle live flow, gap backfill, stale-data fail closed, bounded reconnect
และการเลือก Spot หรือ USDⓈ-M Futures public endpoint จาก Session configuration แล้ว
งานนี้ยังไม่ทำให้ Paper Trading Complete; Paper Futures persistence ถูกส่งมอบใน
DEV-95 แล้ว แต่ Desktop UI, Stop Session และ startup Recovery ยังคงอยู่ในลำดับถัดไป
ของ milestone นี้

สถานะ DEV-115/DEV-116 (กู้คืนผ่าน DEV-130): Desktop Session Setup acceptance
พิสูจน์ Paper Spot และ Paper Futures ตั้งแต่ form, durable create, Overview,
restart/restore, duplicate suppression และ fail-closed paths โดยไม่เริ่ม Market Data,
Strategy หรือ Execution แล้ว Background-task lifecycle ถูกย้ายจาก `MainWindow` ไปอยู่
ใน focused `SessionWorkflow` ซึ่งดูแล startup load, create, busy state, sanitized error
mapping, task cleanup และ late-callback invalidation โดยไม่เปลี่ยน SQLite schema,
application contract, UI copy หรือ business rules

สถานะ DEV-96: Desktop Trade History แสดง Basket History และ Trade Fills ของทุก
Session ผ่าน application query แบบ filter/pagination บน background worker พร้อม
Total Net PnL, UTC date range, accessible PnL state และ scoped unavailable states แล้ว
งานนี้ปลด prerequisite ด้าน UI เพื่อเริ่ม DEV-97 แต่ยังไม่ทำให้ Paper Trading Complete
จนกว่า acceptance, Stop Session และ startup Recovery ที่เหลือจะผ่าน

สถานะ DEV-97: real Paper Spot/Futures execution เข้าสู่ durable SQLite และ Desktop
Trade History แล้ว โดย restart คง Basket, Fills และ exact closed Net PnL เดิมไว้ครบ;
ครอบคลุม Open Basket, duplicate, Partial Fill และ SQLite fail-closed semantics โดยไม่
เพิ่มพฤติกรรม Live, network หรือ credentials งานนี้ปิด Trade History acceptance slice
เท่านั้น และยังไม่ทำให้ Stop Session, startup Recovery หรือเกณฑ์ Paper Trading Complete
ทั้งหมดเสร็จ

สถานะ Unified Trading Workspace slice 1: Desktop UI ใช้ Full Dark Theme และรวม
Session Setup, configured Session summary และ Trade History ไว้ใน Workspace หน้าเดียว
พร้อม responsive Bot Control แล้ว ส่วน dynamic Runtime read model, Start/Stop/Recovery,
Notifications และ Chart ยังคงส่งมอบตาม Sub-issues ถัดไป

สถานะ DEV-133: ส่งมอบ immutable Trading Workspace read model พร้อม exact
Decimal/UTC contracts, background generation-safe refresh และ persistent status header
แล้ว ส่วน Bot lifecycle controls, durable Orders/Basket integration, Runtime
Start/Stop/Recovery, Notifications และ Chart ยังคงอยู่ใน Sub-issues ถัดไป

สถานะ DEV-134: ส่งมอบ Bot Control แบบ state-driven ที่ render immutable Session
Overview และ Workspace snapshot เดียวกับ Header, พร้อม fake lifecycle seam สำหรับ
Start/Stop/Recovery, repeated-action guard และ stale-callback suppression แล้ว
production desktop จะแสดง Configured Start ที่ปิดใช้งานอย่างซื่อสัตย์จนกว่าจะมี
integration จริง; Runtime Start/Stop/Recovery จริงยังคงเป็น DEV-136 โดยไม่มี
network, SQLite Basket/Fill หรือ execution side effect ใน slice นี้

สถานะ DEV-135: ส่งมอบ Open Orders และ Position / Basket tabs ที่แยก state และ render
immutable application facts โดยหนึ่ง Order ที่มีหลาย Partial Fills แสดงหนึ่ง row และ
Paper Spot Basket คง `entry_count` หนึ่งครั้งต่อ Order ส่วน durable Trade History
ยังเปิดดูได้โดยไม่มี Active Bot Session พร้อมรักษา filters, pagination, Fill details และ
last-known rows เมื่อ refresh ล้มเหลว งานนี้ไม่เพิ่ม Runtime source, Open Orders schema,
network หรือ Live execution; authoritative Runtime refresh และ lifecycle ownership
ยังคงเป็นขอบเขต DEV-136

## Milestone 4 — Live Spot

เริ่มได้เมื่อ Paper Trading Complete ผ่านทั้งหมด:

- เก็บ credentials ใน OS Keyring เท่านั้น
- เพิ่ม Live Spot adapter ที่ consumer Module ใช้งานจริง
- เพิ่ม execution interface ที่ consumer เป็นเจ้าของเมื่อมี Paper และ Live adapters
  อย่างน้อยสองแบบ
- บังคับ Preflight, explicit confirmation, idempotency, Reconciliation และ safe shutdown
- ทดสอบด้วย fake transport และ contract tests ก่อนเชื่อมบัญชีจริง

การทดสอบเงินจริงต้องได้รับคำสั่งจากผู้ใช้แยกต่างหาก

## Milestone 5 — Live USDⓈ-M Futures

เริ่มได้เมื่อ Live Spot gate ผ่าน:

- ใช้ Futures adapter แยกจาก Spot
- บังคับ Cross Margin, leverage cap, Futures capital policy และ Collateral Buffer
- รองรับ funding และ liquidation-related account facts
- ผ่าน Preflight, idempotency, Reconciliation และ Recovery สำหรับ Futures semantics

## Module Ownership

| Concern | Owner Module | หมายเหตุ |
| --- | --- | --- |
| Candle และ continuity | `market_data` | รับ symbol/timeframe จาก configuration |
| Session และ immutable policies | `trading` | ไม่เลือก adapter |
| RSI Step Grid | `strategies/rsi_step_grid` | ไม่รู้จัก Paper หรือ Live |
| Basket, capital, Entry Pair, Futures PnL และ margin policy | `trading` | ใช้ร่วมกันทุก Trade Mode; policy เป็น side-aware |
| Session และ completed-candle orchestration | `application` | จัดลำดับ shared business rules กับ execution adapter |
| Paper execution | `execution` | จำลอง deterministic Paper fills และ side effects โดยไม่เรียก Binance |
| Binance public market data | `integrations/binance` | ส่งมอบใน Paper Trading Complete โดยไม่ใช้ credentials |
| Binance Live execution | `integrations/binance` | เพิ่มตาม Live gates เท่านั้น |
| Persistence | `integrations/sqlite` | จัดการ transaction, durable mapping และ persistence-specific fail-closed coordinator; ไม่เก็บ secrets |
| Desktop UI | `ui` | ไม่ถือ business rules |

`execution` เป็นเจ้าของ deterministic simulation ภายในโปรแกรม ส่วน side effects ที่
ออกไปยังระบบภายนอกเป็นของ `integrations/<provider>` เสมอ

## Quality Gates

ทุก Issue ต้องรัน checks ที่เกี่ยวข้องกับขอบเขตงาน และ integration gate ของแต่ละ
milestone ต้องรัน checks ทั้งหมดต่อไปนี้:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

Issue ที่กระทบ application flow ต้องเพิ่ม deterministic acceptance test Issue ที่กระทบ
docs-site ต้องผ่าน production build และ Issue ที่แตะ execution/recovery ต้องใช้ fake
adapter หรือ fake transport ระหว่าง verification

## Change Control

- เปลี่ยน business rule หรือ safety gate ต้องแก้ `PRODUCT.md` ก่อน
- เปลี่ยนคำศัพท์หรือ ownership ต้องแก้ `CONTEXT.md` หรือ `ARCHITECTURE.md`
- เปลี่ยน Strategy behavior ที่มีผลต่อ Session ต้องสร้าง Preset version ใหม่
- เปลี่ยนลำดับการส่งมอบหรือ dependency ต้องแก้เอกสารนี้และ implementation plan ที่เกี่ยวข้อง
- ห้ามเปลี่ยนผลของ Session เดิมโดยเงียบ ๆ
