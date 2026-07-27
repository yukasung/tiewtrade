# Desktop UI Session Setup Design

## สถานะ

- วันที่: 2026-07-27
- สถานะ: อนุมัติสำหรับจัดทำ implementation plan และ Linear Issues
- Milestone: Paper Trading Complete
- Desktop framework: PySide6

## เป้าหมาย

สร้าง Desktop UI vertical slice แรกที่ผู้ใช้เปิดโปรแกรม กำหนดค่า และสร้าง Paper
Session ได้อย่างปลอดภัย โดยระบบตรวจสอบค่า สร้าง immutable configuration บันทึก
Active Bot Session ลง SQLite และแสดง Session Overview ที่อ่านข้อมูลจริงกลับจาก
application layer

Vertical slice นี้สร้าง Main Window และ navigation เท่าที่ Session Setup กับ Session
Overview ใช้งานจริงเท่านั้น ไม่สร้างหน้า placeholder หรือ abstraction สำหรับหน้าที่ยัง
ไม่มีพฤติกรรม

## ขอบเขต

### รองรับ

- Desktop application สำหรับ macOS ด้วย PySide6
- UI ภาษาอังกฤษและ light theme โทน neutral/blue
- Paper Mode เท่านั้น
- Market Type แบบ Spot และ Futures
- BTCUSDT ตามขอบเขต Internal Alpha
- Timeframe `3m`, `5m`, `15m`, `30m`, `1h`, `4h`
- RSI Step Grid Preset v1
- สร้าง Active Bot Session ได้สูงสุดหนึ่ง Session ต่อ installation
- บันทึก immutable Session และ market configuration ลง SQLite แบบ atomic
- เปิดโปรแกรมใหม่แล้วแสดง Active Session เดิมโดยไม่ auto-resume

### ไม่รองรับใน vertical slice นี้

- Live Mode, API Key, OS Keyring หรือ Live Preflight
- การเริ่ม Market Data Runtime, Strategy หรือ Paper Execution
- Stop Session และ Startup Recovery
- Orders, Positions, Notifications, Chart หรือ Trade History UI
- การแก้ configuration หลังสร้าง Session
- Draft Session หรือ Session template

## การตัดสินใจหลัก

### Thin Qt UI และ Application Use Case

PySide6 ทำหน้าที่ presentation เท่านั้น UI แปลงค่าจาก form เป็น request เรียก
application use case และแสดง result โดยไม่ import SQLite, Strategy หรือ Execution
adapter โดยตรง

Application layer เป็นเจ้าของ use case `Create Paper Session` ซึ่งประสานการสร้าง
`SessionConfig` และ `MarketDataConfig` จาก input ที่ผ่าน validation จากนั้นเรียก
concrete SQLite persistence seam และคืน immutable Session snapshot ให้ UI

SQLite integration เป็นเจ้าของ migration, transaction, durable mapping และ database
constraints แต่ไม่คำนวณ business policy

### ไม่มี MVVM framework ล่วงหน้า

Vertical slice แรกใช้ focused request/result objects และ PySide6 signals เท่าที่จำเป็น
ยังไม่สร้าง generic ViewModel, command bus, repository interface หรือ navigation
registry จนกว่าจะมี consumer จริงอย่างน้อยสองราย

### Create ไม่ใช่ Start

ปุ่มหลักใช้ข้อความ `Create Paper Session` การสร้าง Session หมายถึงบันทึก immutable
configuration และจอง Active Bot Session ownership เท่านั้น ไม่หมายถึงเริ่มรับข้อมูล
ตลาดหรือเริ่มซื้อขาย

หลังสร้างสำเร็จ UI แสดงสถานะ
`Configured — Market Data Not Started` เพื่อไม่ทำให้ผู้ใช้เข้าใจว่า Bot กำลังซื้อขาย

## Component Boundaries

### Desktop Composition Root

- สร้าง `QApplication`
- เปิดและ migrate SQLite ก่อนประกอบ use cases
- ประกอบ Main Window, Session Setup และ concrete persistence dependency
- ไม่มี business rule และไม่เรียก Binance endpoint

### UI Module

- แสดง Session Setup และ Session Overview
- สลับ conditional fields ตาม Market Type
- แสดง field-level validation, loading, unavailable และ duplicate-session states
- เรียก application use case ผ่าน worker เพื่อไม่บล็อก UI thread
- ยกเลิกหรือเพิกเฉย callback อย่างปลอดภัยเมื่อหน้าต่างถูกทำลาย

### Application Module

- รับ typed Create Paper Session request
- แปลง input เป็น domain configuration ด้วย constructors ของ Module เจ้าของกฎ
- กำหนด Session identity และเวลา creation แบบ UTC ผ่าน injected deterministic
  providers ใน tests
- บันทึก configuration ผ่าน concrete SQLite session store
- คืน snapshot ที่ UI ใช้ได้โดยไม่เปิดเผย SQLite rows

### Trading และ Market Data Modules

- `trading` ยังคงเป็นเจ้าของ `SessionConfig`, `EntryPolicy`, Spot/Futures policies และ
  validation ของ market-specific policy
- `market_data` ยังคงเป็นเจ้าของ `MarketDataConfig`, symbol, timeframe และ UTC candle
  configuration
- UI และ SQLite ห้ามทำสำเนากฎ validation ของ Module เหล่านี้

### SQLite Integration

- เพิ่ม migration จาก schema ปัจจุบันโดยรักษา Trade History เดิม
- บันทึก Session และ market configuration ใน transaction เดียว
- เก็บ Decimal เป็นข้อความ canonical และเวลาเป็น UTC
- บังคับ single Active Bot Session ด้วย database constraint
- อ่าน Active Session กลับเป็น application snapshot ได้แบบ exact round-trip

## Session Setup Fields

### Common Fields

| Field | UI behavior | Validation |
| --- | --- | --- |
| Trade Mode | แสดง `Paper` แบบ read-only | ต้องเป็น `PAPER` |
| Market Type | เลือก `Spot` หรือ `Futures` | ต้องเป็นค่าที่รองรับ |
| Symbol | แสดง `BTCUSDT` แบบ read-only | ต้องตรงกับ Internal Alpha scope |
| Timeframe | เลือกจากรายการที่รองรับ | `3m`, `5m`, `15m`, `30m`, `1h`, `4h` |
| Available Capital | decimal input | มากกว่า 0 |
| Max Entries | integer input | เลขคู่ 2–20; ค่าเริ่มต้น 10 |
| Preset Version | แสดง RSI Step Grid v1 แบบ read-only | ต้องตรงกับ preset version ที่ระบบรองรับ |

### Advanced Execution Costs

| Field | UI behavior | Validation |
| --- | --- | --- |
| Trading Fee | รับค่าเป็นเปอร์เซ็นต์และแปลงเป็น rate | ตั้งแต่ 0 และน้อยกว่า 100% |
| Slippage | รับค่าเป็น basis points | ตั้งแต่ 0 และน้อยกว่า 10,000 bps |

ค่าทั้งสองถูกบันทึกใน Session configuration และตรึงตลอด Session

### Spot Fields

- `Trading Capital Ratio` รับค่าเป็นเปอร์เซ็นต์ มากกว่า 0 และน้อยกว่า 100%
- ค่าเริ่มต้น 80% เป็นค่าเริ่มต้นของ form ไม่ใช่ค่าคงที่ใน business logic
- Reserve Ratio แสดงเป็นค่าคำนวณ `100% - Trading Capital Ratio`

### Futures Fields

- `Leverage` เป็นจำนวนเต็ม 1x–5x
- `One-way Mode` และ `Cross Margin` แสดงแบบ read-only
- Trading Capital 50% และ Collateral Buffer 50% แสดงแบบ read-only
- ค่าคงที่เหล่านี้มาจาก `FuturesTradingPolicy` ไม่ใช่การคำนวณของ UI

## Data Flow

1. ผู้ใช้กรอก Session Setup และกด `Create Paper Session`
2. UI ตรวจรูปแบบข้อมูลพื้นฐานและสร้าง typed request
3. UI worker เรียก application use case นอก UI thread
4. Application layer สร้าง `SessionConfig` และ `MarketDataConfig`
5. Domain constructors ตรวจ common, Spot หรือ Futures policy
6. SQLite integration ตรวจว่าไม่มี Active Session และบันทึก configuration แบบ atomic
7. Application อ่าน durable record กลับและคืน immutable snapshot
8. UI แสดง Session Overview และปิดการแก้ form

เมื่อเปิดโปรแกรมใหม่ composition root เรียก read-active-session query ถ้าพบ Session
เดิมให้แสดง Overview และไม่ auto-resume Market Data หรือ Trading Runtime

## Persistence Model

Persistence ต้องเก็บข้อมูลอย่างน้อยดังนี้:

- Session ID
- Trade Mode และ Market Type
- Symbol และ Timeframe
- Preset Version
- Available Capital
- Max Entries
- Trading Fee Rate และ Slippage Bps
- Spot Trading Capital Ratio หรือ Futures leverage ตาม Market Type
- Futures policy version, leverage, Cross Margin, One-way Mode, Trading Capital Ratio,
  Collateral Buffer Ratio และ Maintenance Margin Rate
- Creation time แบบ UTC
- `ended_at_utc` ซึ่งเป็น `NULL` ขณะที่ Session ยังไม่สิ้นสุด

Database constraint ต้องป้องกัน Session ที่ยังไม่สิ้นสุดมากกว่าหนึ่งรายการ แม้มี
caller สองรายพยายามสร้างพร้อมกัน Application pre-check ใช้เพื่อแสดงข้อความที่ดี แต่
ไม่ใช่กลไกความถูกต้องเพียงชั้นเดียว โดยใช้ partial unique constraint สำหรับ record ที่
`ended_at_utc IS NULL`

Vertical slice นี้ยังไม่มี Stop Session จึงไม่เปลี่ยน lifecycle marker เป็นสถานะสิ้นสุด
การเพิ่ม Stop/Recovery จะขยาย lifecycle ใน Issue ภายหลังโดย migration ที่เข้ากันได้

## Error Handling

### Validation Error

- แสดงข้อความใกล้ field ที่ผิด
- ไม่เริ่ม persistence transaction
- รักษาค่าที่ผู้ใช้กรอกเพื่อให้แก้ไขได้

### Active Session Exists

- ไม่สร้าง Session ใหม่
- อ่านและแสดง Session เดิม
- ปิด Session Setup form
- ไม่ auto-resume runtime

### SQLite หรือ Migration Failure

- transaction ต้อง rollback ทั้งหมด
- แสดง unavailable state ที่แยกจาก validation error
- ไม่สร้าง Active Session ใน memory หาก durable write ยังไม่ยืนยัน
- อนุญาตให้ retry หลังผู้ใช้แก้สาเหตุ โดยไม่สร้างข้อมูลซ้ำ

### Window Lifecycle

- Worker result ต้องไม่แก้ widget ที่ถูกทำลาย
- การปิดหน้าต่างไม่ยกเลิก SQLite transaction กลางคันแบบที่ทิ้ง partial record
- ไม่มี background trading process ให้ shutdown ใน vertical slice นี้

## Testing Strategy

### Application Tests

- สร้าง Spot และ Futures request ที่ถูกต้องได้ configuration ตรงกัน
- input ที่ผิดถูก reject ด้วย error ที่ UI map กลับไปยัง field ได้
- Session ID และ creation time deterministic เมื่อใช้ fake providers
- persistence failure ไม่คืนผลสำเร็จ

### SQLite Tests

- migration จาก schema ก่อนหน้าไม่ทำลาย Trade History
- Spot/Futures configuration round-trip Decimal และ UTC ได้ตรง
- transaction failure ไม่ทิ้ง partial record
- database constraint ป้องกัน Active Session ซ้ำและ concurrent create
- restart แล้วอ่าน Active Session เดิมได้ครบ

### UI Tests

- Spot/Futures conditional fields แสดงและซ่อนถูกต้อง
- Paper, BTCUSDT และ Preset v1 เป็น read-only
- field validation, loading, success และ unavailable states ถูกต้อง
- double-click หรือ repeated submit ไม่สร้าง request ซ้ำ
- Active Session เดิมปิด form และแสดง Overview
- ทดสอบ PySide6 แบบ offscreen และไม่เรียก network

### Acceptance Test

พิสูจน์ flow ต่อไปนี้ด้วย temporary SQLite:

1. เปิด Desktop application
2. กรอก Paper Spot หรือ Paper Futures Session
3. สร้าง Session และเห็น durable Overview
4. ปิดและเปิด application ใหม่
5. เห็น Session เดิมและไม่สามารถสร้าง Session ที่สอง

Acceptance test ต้องไม่มี Binance Private API, credentials, Market Data Runtime,
Strategy evaluation หรือ execution side effect

## Quality Gates

- Python unit, integration, UI และ acceptance tests ผ่าน
- Ruff lint และ format ผ่าน
- Mypy strict ผ่าน
- documentation checks ผ่าน
- `git diff --check` ผ่าน
- UI launch smoke test บน macOS ผ่าน

## Dependency และลำดับงาน

Vertical slice นี้เป็น prerequisite ของ DEV-96 Trade History UI เพราะทำให้ Desktop
application shell, navigation, worker boundary และ read-only Session Overview พร้อมใช้

หลัง vertical slice นี้:

1. DEV-96 เพิ่ม Trade History เป็น navigation destination ที่สอง โดยใช้ application
   query ที่มีอยู่
2. Stop Session และ Startup Recovery ขยาย lifecycle ของ Active Bot Session
3. DEV-97 พิสูจน์ Paper Trade History flow หลัง UI prerequisites พร้อม

## ความเสี่ยงที่ควบคุมไว้

- ไม่เปิด Live control ก่อน Live gate
- ไม่เรียก network หรือ execution จาก UI foundation
- ไม่สร้าง generic UI architecture ก่อนมีหน้าจอจริงหลายหน้า
- ไม่ใช้ค่าจาก form เป็น mutable runtime settings
- ไม่ยอมให้ in-memory success มาก่อน durable SQLite success
- ไม่สร้าง Active Session ซ้ำแม้ repeated submit หรือ concurrent caller
