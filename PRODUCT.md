# TiewTrade V2 Product Definition

## 1. สถานะเอกสาร

- สถานะ: อนุมัติสำหรับเริ่มวางแผน Internal Alpha
- กลุ่มผู้ใช้: เจ้าของผลิตภัณฑ์และผู้ทดสอบภายในกลุ่มเล็ก
- แพลตฟอร์มแรก: macOS
- ภาษาของ UI: อังกฤษ
- ภาษาของเอกสารและ Linear: ไทย

เอกสารนี้กำหนดขอบเขตและพฤติกรรมของผลิตภัณฑ์ หากเอกสารด้านสถาปัตยกรรมหรือแผนงานขัดกับข้อกำหนดในเอกสารนี้ ต้องแก้เอกสารเหล่านั้นให้สอดคล้องกับ `PRODUCT.md` ก่อนเริ่มพัฒนา

## 2. Product Vision

TiewTrade V2 คือ Desktop Binance Trading Bot สำหรับใช้งานแบบ Internal Alpha โดยให้ความสำคัญกับความถูกต้อง ความสามารถในการตรวจสอบย้อนหลัง การกู้คืนหลังโปรแกรมหยุดทำงาน และการป้องกันคำสั่งซื้อขายซ้ำหรือผิดสถานะ มากกว่าการรองรับฟีเจอร์จำนวนมาก

ระบบเริ่มจาก Paper Trading ที่ทำงานครบตลอดเส้นทาง ก่อนเปิดใช้งาน Live Spot และ Live USDⓈ-M Futures ตามลำดับ แต่ละระดับต้องผ่าน acceptance criteria ของระดับก่อนหน้า

## 3. ขอบเขต Internal Alpha

### 3.1 สิ่งที่รองรับ

- macOS เป็นแพลตฟอร์มแรก โดยสถาปัตยกรรมต้องไม่ปิดทางการรองรับ Windows และ Linux ในอนาคต
- BTCUSDT เพียง Symbol เดียว
- completed candle ช่วงเวลา 5 นาทีเท่านั้น
- ใช้ UTC สำหรับเวลา candle, Entry Pair และ Cooldown Month
- RSI Step Grid พร้อม Versioned Preset เพียงกลยุทธ์เดียว
- Paper Spot และ Paper Futures
- Live Spot หลัง Paper acceptance ผ่าน
- Live USDⓈ-M Futures หลัง Live Spot acceptance ผ่าน
- Binance Sub-account ที่ผู้ใช้สร้างไว้แล้วสูงสุด 5 Account Profiles
- แต่ละ Account Profile ใช้ API credentials แยกกัน
- แต่ละ Account Profile มี Active Bot Session ได้สูงสุดหนึ่ง Session
- Local single-user application

### 3.2 ลำดับการส่งมอบ

1. Paper Trading Complete
2. Live Spot
3. Live USDⓈ-M Futures

แต่ละ milestone ใช้ vertical slice ที่ทำงานครบตั้งแต่ข้อมูลตลาด กลยุทธ์ การจัดการ Basket การส่งคำสั่ง การบันทึกข้อมูล UI และ Recovery ไม่สร้างโมดูลทั่วไปหรือ abstraction ล่วงหน้าหากยังไม่มีผู้ใช้จริงอย่างน้อยสองราย

## 4. RSI Step Grid Versioned Preset

### 4.1 ค่าเริ่มต้น

| Parameter | ค่า |
| --- | ---: |
| RSI period | 14 |
| RSI reset threshold | ต่ำกว่า 30 |
| RSI entry threshold | สูงกว่า 50 |
| ATR period | 14 |
| Take Profit ATR multiplier | 3 |
| Maximum entries per Basket | ค่าเริ่มต้น 10; ผู้ใช้เลือกเลขคู่ 2–20 ก่อนเริ่ม Session |
| Candle interval | 5 นาที |

Preset ทุกชุดต้องมี version แบบ immutable เมื่อ Session เริ่มทำงาน Session ต้องอ้างถึง version ที่แน่นอน การแก้ค่าในภายหลังต้องสร้าง version ใหม่และไม่มีผลย้อนหลังต่อ Session เดิม

### 4.2 Entry Signal

กลยุทธ์เป็น Long-only และประเมินสัญญาณจาก completed candle เท่านั้น

1. เมื่อ RSI ต่ำกว่า 30 ให้บันทึก reset signal และราคาปิดของ reset signal candle
2. รอ completed candle ที่ผ่านเงื่อนไขทั้งหมดต่อไปนี้:
   - RSI สูงกว่า 50
   - `close > open`
   - `close > ราคาปิดของ reset signal candle`
   - Basket ยังไม่ครบ `max_entries` ของ Session
   - Session และ lifecycle อนุญาตให้เพิ่ม Entry
3. เมื่อ Entry ถูก Fill ให้ใช้ reset signal นั้นเสร็จสิ้น และต้องรอ reset signal ใหม่ก่อนสร้าง Entry ถัดไป

ระบบต้องไม่ประเมิน candle ที่ยังไม่ปิด และต้องไม่ประมวลผล completed candle เดิมซ้ำ

## 5. Basket Take Profit

Basket Take Profit คำนวณด้วยสูตร:

```text
weighted_average_entry_price + (ATR(14) * 3)
```

กติกา:

- ใช้ ATR จาก completed candle 5 นาทีล่าสุด ณ เวลาที่ Entry ถูก Fill
- คำนวณราคา Take Profit ใหม่หลังทุก Entry Fill
- ปัดราคาตาม Binance tick size ของ BTCUSDT
- Take Profit ครอบคลุมขนาด Position ที่ Bot เป็นเจ้าของทั้งหมดใน Basket
- เมื่อ Take Profit ถูก Fill ให้ปิด Entries ทั้งหมดใน Basket พร้อมกัน
- เมื่อ Basket ปิดสมบูรณ์ สามารถเริ่ม Basket ใหม่ในเดือน UTC เดียวกันได้ทันที
- ค่าธรรมเนียมไม่ถูกบวกเข้าไปในราคา Take Profit แต่ต้องถูกนำไปคำนวณ realized PnL

## 6. Entry Pair และ Cooldown Month

Entries ถูกจัดเป็นคู่ตามลำดับ โดย Pair ลำดับที่ `n` ประกอบด้วย Entries
`(2n - 1)` และ `2n` จนครบ `max_entries` ของ Session

Lifecycle:

1. ถ้ามีเพียง Entry แรกของ Pair ค้างข้ามสิ้นเดือน UTC ระบบยังเปิด Entry ที่สองในเดือนถัดไปได้เมื่อมีสัญญาณ
2. เมื่อ Pair มีครบสอง Entries และ Basket ยังไม่ปิดจนผ่านสิ้นเดือน UTC เดือนถัดไปเป็น Cooldown Month
3. ระหว่าง Cooldown Month ห้ามเพิ่ม Entry แต่ Basket Take Profit ยังคงทำงาน
4. เมื่อพ้น Cooldown Month จึงเริ่ม Pair ถัดไปได้
5. วน lifecycle นี้จน Basket ปิดหรือครบ `max_entries` ของ Session
6. การปิด Basket จะ reset Entry Pair และ Cooldown state สำหรับ Basket ใหม่

## 7. Capital Allocation

ผู้ใช้กำหนด Available Capital และ `max_entries` สำหรับแต่ละ Session ระบบแบ่งขนาด Entry เท่ากันจาก Trading Capital ของ Mode นั้น `max_entries` ต้องเป็นเลขคู่ตั้งแต่ 2–20 และถูกตรึงตลอด Session

### 7.1 Spot

- ผู้ใช้กำหนด `trading_capital_ratio` ก่อนเริ่ม Session โดยค่าเริ่มต้นเท่ากับ 80%
- Spot Reserve Ratio คำนวณจาก `1 - trading_capital_ratio`
- Quote notional ต่อ Entry: Trading Capital หาร `max_entries`
- Reserve ไม่ถูกนำไปคำนวณขนาด Entry

### 7.2 Futures

- Trading Capital: 50% ของ Available Capital
- Collateral Buffer: 50% ของ Available Capital
- Initial margin budget ต่อ Entry: Trading Capital หาร `max_entries`
- Target notional ต่อ Entry: Initial margin budget ต่อ Entry คูณด้วย leverage ของ Session
- ใช้ Cross Margin
- Leverage ต้องไม่เกิน 5x
- Collateral Buffer ไม่ถูกใช้สร้าง Entry ใหม่ แต่ถือเป็นเงินที่ผู้ใช้ยอมเสี่ยงทั้งหมดเพื่อเลื่อน liquidation

ระบบต้องบังคับ immutable Session policy, capital allocation, leverage cap และ `max_entries` ใน Paper และ Live ด้วยกติกาชุดเดียวกัน

## 8. Paper Execution Model

Paper Trading ใช้ conservative candle fill เพื่อให้ replay ได้และป้องกัน look-ahead bias

- สัญญาณจาก completed candle `N` สร้าง Entry Intent
- Entry Fill ที่ราคาเปิดของ candle `N+1`
- คำนวณ fee และ slippage ด้วยค่าที่กำหนดใน Session
- Take Profit เริ่มทำงานหลัง Entry Fill และ Fill เมื่อช่วงราคาของ candle ถัดจาก candle ที่ Entry Fill แตะระดับ Limit เพื่อหลีกเลี่ยงการสมมติลำดับราคา intrabar
- Paper Futures ใช้ funding rate และ funding timestamp จากข้อมูล Binance ที่ระบบบันทึกไว้ หาก replay ให้ใช้ข้อมูลชุดที่บันทึกเดียวกัน
- fee, slippage และ funding configuration ต้องถูกตรึงตลอด Session
- เมื่อใช้ข้อมูลตลาดและ Preset version เดิม Paper replay ต้องให้ผลลัพธ์เดิม

Paper, Live Spot และ Live Futures ใช้ strategy, capital และ lifecycle policies ร่วมกัน แต่ใช้ execution adapter แยกกัน

### 8.1 Shared Policies และ Execution Boundary

Paper และ Live ต้องใช้ business rules ชุดเดียวกันสำหรับ Session, Strategy, capital allocation, Basket, Entry Pair, risk policy และ PnL calculation เพื่อให้ผลการตัดสินใจสอดคล้องกันทุก Mode

Execution ต้องแยกเป็น adapter ตาม Mode และ Market Type:

- Paper ใช้ adapter สำหรับจำลอง Fill และ execution costs โดยไม่ส่งคำสั่งไป Binance
- Live Spot ใช้ adapter สำหรับ Spot และต้องผ่าน Preflight ก่อน execution
- Live Futures ใช้ adapter สำหรับ Futures และต้องจัดการ margin, leverage, funding และ reconciliation ตาม semantics ของ Futures

การตั้งค่า `TradeMode.LIVE` เพียงอย่างเดียวไม่เพียงพอที่จะเริ่มการเทรดจริง และห้ามทำให้ Paper adapter เรียก Live adapter หรือ Live endpoint ได้

## 9. Live Execution Safety

- ไม่มี Binance Testnet
- ห้ามเปลี่ยนจาก Paper เป็น Live อัตโนมัติ
- Live ทุก Session ต้องผ่าน Preflight และการยืนยันจากผู้ใช้ก่อนเริ่ม
- Preflight ต้องตรวจ:
  - API credentials และ permissions
  - Account Profile ที่เลือก
  - BTCUSDT symbol rules
  - Balance
  - Open orders และ positions
  - Margin mode
  - Leverage
- ทุกคำสั่งต้องมี idempotency key ที่คงที่และตรวจสอบย้อนหลังได้
- Live Spot และ Live Futures ต้องใช้ execution adapter แยกกัน
- ระบบไม่ใช้ Master Account API
- API key และ secret เก็บใน OS Keyring เท่านั้น ห้ามบันทึกใน SQLite, log หรือ source control

## 10. Risk Policy

Internal Alpha ยังไม่มี:

- Stop Loss
- Maximum Drawdown hard limit
- Max Daily Loss
- Consecutive-loss stop

ระบบแสดง PnL และ Drawdown พร้อมแจ้งเตือนเพื่อการเฝ้าระวัง แต่ไม่บังคับปิด Position จากค่าเหล่านี้ ระบบยังต้องบังคับ capital allocation, maximum entries และ Futures leverage cap เสมอ

## 11. Connection Safety

เมื่อ market data ไม่สดหรือ WebSocket ขาดการเชื่อมต่อ:

- ห้ามสร้าง Entry ใหม่
- คง Take Profit ที่ส่งไว้บน Binance
- แสดงสถานะข้อมูลไม่สดและแจ้งเตือนผู้ใช้
- พยายามเชื่อมต่อใหม่ด้วยนโยบาย retry ที่จำกัดและตรวจสอบได้
- เมื่อเชื่อมต่อสำเร็จต้อง backfill completed candles ที่ขาด
- ต้อง deduplicate candles ก่อนส่งให้ Strategy
- Resume การสร้าง Entry ได้เมื่อข้อมูลต่อเนื่องและ state ผ่านการตรวจสอบแล้วเท่านั้น

## 12. Shutdown และ Recovery

### 12.1 Stop Session

Stop Session หมายถึง:

- หยุดสร้าง Entry ใหม่
- บันทึก state ปัจจุบัน
- คง Basket Take Profit ที่มีอยู่
- ไม่บังคับปิด Basket

### 12.2 Startup Recovery

เมื่อเปิดโปรแกรมใหม่:

1. โหลด Session, Basket, Entry, Order และ Fill state จากฐานข้อมูล
2. ดึง exchange state สำหรับ Live Session
3. Reconcile local state กับ exchange state
4. Resume ได้เมื่อ state ตรงกัน
5. หาก state ไม่ตรงกัน ให้บล็อก Entry ใหม่ แสดงรายละเอียด และรอให้ผู้ใช้แก้ไข

ระหว่าง Recovery ระบบห้ามยกเลิกคำสั่ง เปิด Basket ใหม่ หรือแก้ state โดยอัตโนมัติ

## 13. User Interface

UI เป็นภาษาอังกฤษและใช้ light theme โทน neutral/blue ที่อ่านง่ายและน่าเชื่อถือ งาน network, engine และ persistence ต้องไม่บล็อก UI thread

หน้าจอหลัก:

- Account Profiles
- Session Setup และ Paper/Live Mode
- Operations Dashboard
- BTCUSDT Chart
- Orders
- Positions และ Basket Lifecycle
- Notifications
- Settings และ Live Preflight
- Recovery/Reconciliation

UI ต้องแยก Paper และ Live อย่างชัดเจน แสดง Account Profile, Market Type, Mode, Preset Version, data freshness และ Bot Session state ตลอดเวลาที่เกี่ยวข้องกับการตัดสินใจซื้อขาย

## 14. Data และ Auditability

SQLite เก็บข้อมูลที่ไม่ใช่ secret ได้แก่:

- Account Profile metadata
- Versioned Preset
- Session configuration และ state
- Basket และ Entry Pair state
- Entry Intent
- Order และ Fill
- PnL, fee, slippage และ funding
- Notification
- Recovery/Reconciliation record
- Operational audit event

ข้อมูลทุก record ที่เกี่ยวกับการซื้อขายต้องผูกกับ Account Profile และ Session อย่างชัดเจน Durable audit trail ต้องอธิบายได้ว่า Bot ตัดสินใจอะไร เมื่อใด ใช้ candle/preset ใด และผลการส่งคำสั่งเป็นอย่างไร

## 15. Acceptance Criteria

### 15.1 Paper Trading Complete

- completed candle 5 นาทีต่อเนื่อง ไม่ขาดและไม่ซ้ำหลัง backfill
- RSI Step Grid ทำงานตรงตาม Versioned Preset
- Basket Take Profit, Entry Pair และ Cooldown Month ผ่าน automated tests
- Paper Fill ไม่มี look-ahead bias และ replay ได้ผลเดิม
- fee, slippage และ funding ถูกคำนวณและบันทึก
- Restart แล้วกู้ Session และ Basket ได้โดยไม่สร้าง Entry หรือ Order ซ้ำ
- Account Profiles สูงสุดห้ารายการแยกข้อมูลและ Active Session ออกจากกัน
- UI แสดง state, PnL, Drawdown, data freshness และเหตุการณ์สำคัญ
- business rules, persistence, recovery และ execution boundaries มี automated tests

### 15.2 Live Spot Gate

- Paper Trading Complete ผ่านทั้งหมด
- Preflight, idempotency, reconciliation และ safe shutdown ผ่านการทดสอบด้วย fake adapter
- ผู้ใช้อนุมัติเริ่มทดสอบ Live Spot โดยชัดแจ้งในอนาคต

### 15.3 Live Futures Gate

- Live Spot Gate และ acceptance ผ่าน
- Cross Margin, leverage cap, Collateral Buffer, funding และ liquidation-related account facts ผ่านการตรวจสอบ
- ผู้ใช้อนุมัติเริ่มทดสอบ Live Futures โดยชัดแจ้งในอนาคต

## 16. สิ่งที่ไม่อยู่ใน Internal Alpha

- Symbol อื่นนอกจาก BTCUSDT
- หลายกลยุทธ์หรือ Strategy Plugin System
- Generic base strategy/registry ที่ยังไม่มี consumer ตัวที่สอง
- Master Account API
- Binance Testnet
- Manual order terminal
- Advanced chart tools
- Backtest UI
- Automatic Stop Loss และ automatic loss limits
- Login และระบบสมาชิก
- License flow
- Cloud Sync
- Web application
- Mobile application

## 17. หลักการเปลี่ยนขอบเขต

การเปลี่ยน business rule, risk policy, live gate หรือ acceptance criteria ต้องแก้ `PRODUCT.md` และสร้าง Preset version ใหม่เมื่อการเปลี่ยนแปลงมีผลต่อ Strategy Session ห้ามเปลี่ยนพฤติกรรมของ Session เดิมโดยเงียบ ๆ
