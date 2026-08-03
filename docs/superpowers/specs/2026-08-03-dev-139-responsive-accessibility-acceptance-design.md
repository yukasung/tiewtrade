# DEV-139 Responsive, Accessibility และ Paper Workspace Acceptance Design

## เป้าหมาย

พิสูจน์ว่า Unified Trading Workspace ใช้งานได้ครบสำหรับ Paper Spot และ Paper
Futures ทั้งใน wide และ compact layout, ใช้ keyboard ได้, สื่อความหมายโดยไม่พึ่งสี
เพียงอย่างเดียว และคง safety/recovery behavior เมื่อ presentation บางส่วนล้มเหลว

งานนี้เพิ่ม deterministic acceptance coverage และแก้เฉพาะ defect ที่ test พิสูจน์ว่า
จำเป็น ไม่เปลี่ยน Strategy, capital allocation, Basket lifecycle, execution policy,
Session persistence contract หรือกฎ Paper Trading ใน `PRODUCT.md`

## ขอบเขต

งานนี้ครอบคลุม:

- wide layout ที่ความกว้างตั้งแต่ `1,200 px` และ Bot Control drawer ที่ต่ำกว่า
  `1,200 px`
- keyboard navigation, visible focus, focus restoration และ accessible names ของ
  control สำคัญ
- horizontal scrolling ของ Open Orders, Position / Basket และ Trade History tables
- semantic text สำหรับ Runtime State, Data Freshness, PnL และ Notification Severity
- Paper Spot/Futures flow ตั้งแต่ Create, Start, trade update, Stop และ
  restart/recovery
- Trade History availability โดยไม่ขึ้นกับ Active Bot Session
- failure isolation ของ Chart และ Notification presentation
- repository-wide quality gates ที่ระบุใน `ARCHITECTURE.md`

งานนี้ไม่ครอบคลุม:

- Live Spot, Live Futures, Binance Private API หรือ Live credentials
- Manual Buy/Sell หรือ order entry control
- เปลี่ยน visual identity หรือ redesign Workspace
- เพิ่ม accessibility framework หรือ abstraction ใหม่ที่ยังไม่มี consumer จริง
- เปลี่ยน business rule เพื่อทำให้ acceptance test ผ่าน

## แนวทางที่เลือก

ใช้ acceptance matrix ที่แยก scenario ตามพฤติกรรม ร่วมกับ focused UI tests สำหรับ
contract ที่ต้องตรวจในระดับ widget เช่น breakpoint, focus และ scrollbar หาก test พบ
defect ให้แก้ production code เฉพาะ seam ที่เป็นเจ้าของพฤติกรรมนั้น วิธีนี้ให้หลักฐาน
end-to-end โดยไม่รวมทุกอย่างไว้ใน test ขนาดใหญ่ที่วิเคราะห์ failure ยาก

ไม่เลือกการทำ single mega-test เพราะ failure จาก lifecycle, persistence และ UI จะ
ปะปนกัน และไม่เลือก broad accessibility refactor เพราะเกินขอบเขต Integration Gate
ของ `DEV-139`

## Responsive Contract

`TradingWorkspace` เป็นเจ้าของ presentation breakpoint เดิม:

- `width >= 1200`: Bot Control แสดงแบบ docked และปุ่มเปิด compact drawer ถูกซ่อน
- `width < 1200`: Bot Control ถูกถอดจาก docked layout และแสดงผ่าน drawer
- resize ข้าม breakpoint ต้อง reuse `BotControlWidget` เดิม ไม่สร้าง lifecycle control
  ซ้ำ ไม่สูญเสีย Session snapshot และไม่เชื่อม signal ซ้ำ
- compact drawer ปิดด้วยปุ่ม Close หรือ `Escape` และคืน focus ไปยังปุ่มเปิด drawer
- validation failure ที่เกิดภายหลังต้องเปิด drawer, เปิดส่วน form ที่เกี่ยวข้อง และ
  focus field ที่ผิดโดยไม่เริ่ม Session ซ้ำ

Acceptance test ใช้ `1,200 px` และ `1,199 px` เป็น boundary values และตรวจทั้ง
visibility, widget identity, current state และ signal count

## Accessibility Contract

control ที่ผู้ใช้ต้องโต้ตอบต้องเข้าถึงได้ด้วย keyboard และมี focus indicator ที่มองเห็น
บน dark surface โดยเฉพาะ:

- Bot Control trigger, drawer close, Start Bot, Stop Session และ recovery action
- Notification trigger, acknowledge action และ drawer close
- Workspace tabs, Trade History filters, pagination และ chart range/retry controls

การทดสอบจะใช้ Qt keyboard events และตรวจ focus owner หลัง interaction แทนการตรวจ
stylesheet string เพียงอย่างเดียว ส่วน theme test ยังคงตรวจว่ากฎ `:focus` ครอบคลุม
widget ที่ใช้งานจริง

ทุก table ต้องมี accessible name, เป็น read-only และเปิด horizontal scrollbar เมื่อ
content กว้างกว่าพื้นที่แสดง โดยต้องไม่บีบทุก column จนข้อมูลสำคัญอ่านไม่ได้

## Semantic Status Contract

ข้อมูลที่มีความหมายด้าน trading หรือ safety ต้องมีข้อความที่อ่านได้โดยไม่อาศัยสี:

- Runtime State และ Data Freshness แสดงคำสถานะใน persistent header และ Bot Control
- PnL แสดง label/column header และค่าตัวเลขแบบ exact decimal; สีบวก/ลบเป็นเพียง
  presentation เสริม
- Notification แสดง UTC timestamp, Severity, Category และ sanitized message
- unread notification trigger มี accessible name ที่ระบุ count และ highest severity
- Blocked, Stale และ Recovery result ต้องปรากฏใน Workspace หรือ Bot Control ด้วย
  ไม่อยู่เฉพาะ Notification drawer

## Paper Workspace Acceptance Matrix

ใช้ parameterized scenario สำหรับ `MarketType.SPOT` และ `MarketType.FUTURES` โดย
แต่ละ scenario พิสูจน์ flow เดียวกัน:

1. เปิด Desktop โดยไม่มี Active Bot Session และเปิด Trade History ได้
2. กรอก Session configuration ผ่าน UI และ Create Session
3. ยืนยันว่า Create ทำให้ state เป็น Configured แต่ Runtime ยังไม่เริ่ม
4. Start Bot ผ่าน fake/public candle source ที่ deterministic
5. ส่ง completed candles ที่ทำให้เกิด durable trade update และตรวจ Header,
   Position / Basket, Open Orders ตาม authoritative snapshot และ Trade History
6. Stop Session ผ่าน confirmation และยืนยันว่า Runtime เป็น Stopped โดยไม่ปิด Basket
   แบบเทียม
7. ปิดและเปิด Workspace ใหม่จาก SQLite เดิม แล้วตรวจ durable Session และ Trade
   History

Spot ใช้ Paper Spot adapter และ Futures ใช้ Paper Futures adapter ผ่าน application
composition เดิม ทั้งสอง mode ใช้ fake/public market-data source และ SQLite ใน
temporary directory เท่านั้น

## Restart และ Recovery

restart/recovery scenario สร้าง durable lifecycle state ที่บ่งชี้ว่า process เดิมหยุด
ระหว่าง Runtime จากนั้นเปิด Desktop ใหม่และพิสูจน์ว่า:

- startup inspection ไม่เริ่ม Market Data หรือ execution อัตโนมัติ
- Workspace แสดง Blocked พร้อมข้อความ recovery ที่ sanitized
- Start ถูกปิดไว้จนกว่าจะ recovery สำเร็จ
- recovery ใช้ durable facts และเปลี่ยนไปยัง state ที่ application contract อนุญาต
- repeated recovery action ไม่สร้างงานซ้ำ
- Trade History และ Basket facts ที่ durable ยังอ่านได้ตลอด flow

## Failure Isolation

Chart และ Notification เป็น presentation scopes ที่ไม่เป็นเจ้าของ Runtime หรือ durable
trading state:

- Chart load/refresh failure เปลี่ยนเฉพาะ Chart เป็น unavailable พร้อม retry โดย Bot
  Control, trading tables และ Trade History ยังทำงาน
- malformed หรือ rejected Notification presentation event ต้องไม่เปลี่ยน Runtime,
  ลบ durable facts หรือทำให้ Workspace interaction ค้าง
- notification message ต้องมาจาก allowlisted mapping และห้ามแสดง raw exception,
  database path, credentials หรือ transport payload
- failure tests ตรวจ last-known-good content ของ scope ที่ไม่เกี่ยวข้องเพื่อป้องกัน
  silent data loss

จะไม่จับ exception แบบกว้างใน business/application layer เพื่อซ่อน defect ของ UI;
การแยก failure ต้องอยู่ที่ presentation workflow boundary ที่เป็นเจ้าของ async result
นั้น

## Test Structure

ชุดทดสอบจะจัดตามความรับผิดชอบ:

- focused tests ใน `tests/unit/ui/` สำหรับ breakpoint boundary, keyboard focus,
  accessible names, semantic text และ horizontal scrolling
- deterministic desktop acceptance ใน `tests/acceptance/` สำหรับ Spot/Futures
  Create-to-Stop, restart/recovery, Trade History availability และ failure isolation
- helper เฉพาะโดเมนใน `tests/support/` เมื่อมี setup ซ้ำจริงระหว่าง acceptance
  scenarios; ไม่สร้าง generic UI test framework

ทุก behavior change ใช้ TDD: เพิ่ม test ที่ fail ด้วยเหตุผลที่คาดไว้ก่อน แก้ minimal
production code แล้วรัน focused test ซ้ำก่อนขยายไปยัง related suite

## Safety และ Dependency Boundaries

- block network ใน acceptance test เว้นแต่เป็น fake object ใน process
- ไม่อ่าน OS Keyring และไม่รับ credential input
- ไม่ import Live execution, private Binance transport หรือ SQLite จาก `ui`
- UI ส่ง request ไป application boundary และ render immutable snapshot เท่านั้น
- ใช้ temporary SQLite database และ fake/public adapters ที่ deterministic
- ไม่มี Testnet และไม่มีเงินจริงในทุก verification path

## Verification

ก่อนปิด `DEV-139` ต้องรันและอ่านผลของ:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

รวมถึง focused UI/acceptance tests ระหว่าง TDD และตรวจ dependency/safety assertions
ว่าไม่มี Live credentials, Binance Private API หรือเงินจริงเข้ามาใน flow

## เงื่อนไขความสำเร็จ

งานเสร็จเมื่อ acceptance matrix ผ่านทั้ง Spot/Futures, breakpoint และ keyboard contracts
ผ่าน, semantic statuses ไม่พึ่งสี, failure ของ Chart/Notification ไม่ลามไป Runtime หรือ
Trade History, restart/recovery fail closed และ repository quality gates ผ่านทั้งหมด
โดยไม่มีการเปลี่ยน business rules หรือ Live safety boundary
