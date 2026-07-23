# TiewTrade Domain Context

## Trade Mode

- `PAPER` — จำลอง execution ด้วยข้อมูลที่ควบคุมได้ ไม่ส่งคำสั่งไป Binance
- `LIVE` — execution กับ exchange จริงได้เฉพาะหลัง Preflight และผู้ใช้ยืนยันอย่างชัดเจน

## Market Type

- `SPOT` — ซื้อขาย Spot และใช้ Spot capital policy
- `FUTURES` — ใช้ Futures margin, leverage, funding และ liquidation-related account facts

## Shared Policy Rule

Paper และ Live ใช้ business rules ชุดเดียวกันสำหรับ Strategy, capital, Basket, Entry Pair, risk policy และ PnL แต่ใช้ execution adapter แยกกัน

ห้ามสรุปว่า Paper กับ Live ใช้ execution code เดียวกัน การใช้ร่วมกันอยู่ที่กฎการตัดสินใจ ไม่ใช่ side effect ของการส่งคำสั่ง

## Session Configuration

`SessionConfig` เป็น configuration แบบ immutable ที่ระบุ Session, Preset version, Market Type, Trade Mode, Available Capital, `EntryPolicy`, market-specific capital policy, fee และ slippage

การตั้งค่า `LIVE` ไม่ใช่คำสั่งเริ่มการเทรด และไม่ข้าม Preflight, explicit confirmation หรือ reconciliation

## Account และ Session Ownership

หนึ่ง installation ใช้ Binance Account เดียวและมี Active Bot Session ได้สูงสุดหนึ่ง Session โดย Session เป็น ownership boundary โดยตรงสำหรับ Basket, Entry, Order, Fill, PnL และ audit records ระบบไม่สร้าง abstraction สำหรับหลายบัญชีหรือ Binance sub-account

## Configuration และ Policy Boundaries

ค่าที่ผู้ใช้หรือ session เลือกได้ต้องส่งผ่าน configuration ไม่ hardcode ใน business logic:

- `symbol` — สัญลักษณ์ตลาด เช่น `BTCUSDT`
- `timeframe` — ช่วงเวลาของ candle เช่น `5m`
- `market_type` — `SPOT` หรือ `FUTURES`
- `trade_mode` — `PAPER` หรือ `LIVE`
- `available_capital` และ `preset_version`
- `trading_capital_ratio` และ `max_entries` — เลือกจาก form ก่อนเริ่ม Session

ระบบใช้ `UTC` เป็น timezone กลางเสมอ และไม่เปิดให้เปลี่ยน timezone ใน session configuration

ค่าจาก form ต้องผ่าน validation แล้วสร้างเป็น immutable Session policy ห้ามเปลี่ยนระหว่าง Session โดย `trading_capital_ratio` ต้องมากกว่า 0 และน้อยกว่า 1 ส่วน `max_entries` ต้องเป็นเลขคู่ตั้งแต่ 2–20

RSI parameters, take-profit rule, Entry Pair และ Cooldown Month ยังคงอยู่ใน Strategy Preset หรือ product policy และไม่ใช่ค่าที่ผู้ใช้เปลี่ยนระหว่าง Session

กฎเฉพาะตลาดต้องถูกตรวจสอบที่ boundary ก่อนเริ่ม session:

- Spot ใช้ Spot capital policy
- Futures ใช้ Cross Margin, leverage และ collateral buffer ตาม preset/policy
- Paper และ Live ใช้ business/risk policy เดียวกัน แต่ใช้ execution adapter แยกกัน
