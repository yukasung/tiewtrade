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

`SessionConfig` เป็น configuration แบบ immutable ที่ระบุ session, Account Profile, Preset version, Market Type, Trade Mode, Available Capital, fee และ slippage

การตั้งค่า `LIVE` ไม่ใช่คำสั่งเริ่มการเทรด และไม่ข้าม Preflight, explicit confirmation หรือ reconciliation
