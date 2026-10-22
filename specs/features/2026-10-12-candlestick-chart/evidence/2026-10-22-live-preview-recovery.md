# F-12 live-preview recovery — 2026-10-22

สถานะ: **Compose drift resolved; host-sleep recovery proved; short runtime proof passed**

ตรวจ development stack เท่านั้น ไม่ใช้ API key, ไม่ส่งออเดอร์, ไม่เปลี่ยนโหมดบัญชี
และไม่แตะ Live Trading. ผลนี้ปิด incident ของ environment ปัจจุบัน แต่ไม่แทน
V-17/workload และ owner manual acceptance ที่ยังค้างอยู่.

## อาการและต้นเหตุที่ยืนยันได้

ก่อนแก้ effective Compose config จาก `compose.yaml` + `compose.chart.dev.yaml` ระบุ
`TIEWTRADE_CHART_ENABLED=1` แต่ container ที่กำลังรันทั้ง `market-data`, `api` และ
`frontend` มีค่า chart flag ว่าง เพราะถูกสร้างจาก base Compose โดยไม่ได้ recreate
ด้วย override ที่ F-12 กำหนดไว้.

ผลในฐานข้อมูลก่อนแก้:

- price writer ยังปกติ: `connected=true`, lease เหลือประมาณ 4 วินาทีจาก 5 วินาที;
- candle state: `connected=false`, `bootstrapped=false`, lease หมดอายุกว่า 16 นาที;
- `market_candle_preview` ไม่มีแถว จึงไม่มี live tail ให้ API/browser อ่าน;
- log ของ process รอบนั้นไม่มี `candle preview writer unavailable` เพราะ
  `CandleSupervisor` ไม่ได้ถูกสร้างเลย ไม่ใช่เพราะ writer เริ่มแล้วเสีย lease.

จึงยืนยันต้นเหตุของ incident ปัจจุบันว่าเป็น **runtime Compose configuration drift**.
หลักฐานที่เหลือจาก 2026-10-14 ไม่มี traceback/exception type มากพอจะสรุปย้อนหลังว่า
warning เก่าทั้งสองบรรทัดมีต้นเหตุเดียวกัน จึงไม่อ้างเกินหลักฐาน.

## การแก้

recreate เฉพาะ development containers ด้วย override ที่อนุมัติและมีอยู่แล้ว:

```text
docker compose --env-file config/postgres.env \
  -f compose.yaml -f compose.chart.dev.yaml \
  up -d --force-recreate --no-deps market-data

docker compose --env-file config/postgres.env \
  -f compose.yaml -f compose.chart.dev.yaml \
  up -d --force-recreate --no-deps api frontend
```

หลัง recreate ทั้งสาม container รายงาน chart flag เป็น `1`. ไม่เปลี่ยน production
default ซึ่ง `plan.md` กำหนดให้ปิด, ไม่แก้ source code/schema และไม่ลบข้อมูล.

## หลักฐานหลังแก้

ตรวจบน source ใน image ที่ checksum ตรงกับ working tree สำหรับ
`realtime.py` และ `candle_realtime.py`:

- API `/health` ตอบ HTTP 200;
- chart candle route ตอบ HTTP 401 เมื่อไม่มี session แทน 404/disabled
  แสดงว่า route เปิดและ auth policy ยังทำงาน;
- frontend ตอบ HTTP 200 และ `VITE_CHART_ENABLED=1`;
- price state: `connected=true`, lease ต่ออายุเหลือ 4.2–4.9 วินาทีจาก 5 วินาที;
- candle state: `connected=true`, `bootstrapped=true`, lease ต่ออายุเหลือ
  18.6–19.2 วินาทีจาก 20 วินาที;
- preview มีครบ 16 series (BTC/USDT และ ETH/USDT × 8 timeframe), latest
  `received_at` อายุ 2.7–3.2 วินาทีใน snapshots ที่วัด;
- `market-data` restart count เป็น 0;
- ไม่พบ `candle preview writer unavailable`, `price producer lease lost`,
  bootstrap retry, WARNING หรือ ERROR ในช่วงแรกหลัง recreate ก่อนเครื่องเข้า Deep Idle;
- historical ingestion ยังเดินต่อพร้อมกันและรายงาน `stale=0`.

### Warning หลัง host sleep และการกู้กลับ

final log audit พบ warning ทั้งสองข้อความหนึ่งครั้งใน container เดิม:

- macOS power log ระบุ `Wake from Deep Idle` เวลา `2026-10-22 12:30:36 +07`;
- price warning เวลา `05:30:40.798Z` และ candle warning เวลา `05:30:41.541Z`
  หรือประมาณ 4–5 วินาทีหลังเครื่องตื่น;
- Binance TH REST มี `ConnectError` เวลา `05:31:02Z` ขณะ network หลัง wake ยังฟื้น;
- upstream กลับตอบ 200 ตั้งแต่ `05:31:26Z`; historical round กลับเก็บ 8 rows แล้ว
  16 rows ภายใน `05:32:05Z`;
- snapshot เวลา `05:58:18Z` ยืนยัน price `connected=true`, lease เหลือ 4.67/5 วินาที;
  candle `connected=true`, `bootstrapped=true`, lease เหลือ 19.75/20 วินาที;
  preview ล่าสุดอายุ 0.29 วินาที;
- ตั้งแต่ `05:31:35Z` ถึง final audit ไม่พบ warning สองข้อความนี้ซ้ำ.

ลำดับเวลาเดียวกันของ lease ทั้งสองขนาดกับหลักฐาน Deep Idle พิสูจน์ว่า warning รอบนี้
เกิดจาก host/Docker หยุดเดินระหว่าง sleep จน DB-clock lease หมด ไม่ใช่ writer สองตัวชนกัน
หรือ process crash. Supervisor fail closed แล้ว reacquire/bootstrap สำเร็จตาม recovery design;
จึงไม่แก้ timeout หรือ fencing ใน source code.

การวัดทั้งหมดเป็น short runtime proof หลายรอบ heartbeat/renewal ไม่ใช่ soak.
V-17 และ release gates อื่นยังคงสถานะเดิม.

## Browser session จริงบน development stack

หลังแก้ config drift เปิด Chromium ผ่าน Playwright จาก frontend development container
ไปที่ `/chart` แล้วสมัครบัญชี disposable ผ่านแบบฟอร์มจริง. API ตอบ
`POST /auth/register` 201 และ `GET /auth/me` 200 หลังสร้าง server-side session;
ไม่ได้ inject cookie, mock session, mock Chart API หรือใช้ fixture แทนข้อมูล development.

ผลหลังเข้า Chart:

- URL เป็น `/chart` และ `candlestick-chart` มองเห็นได้;
- renderer มี canvas 7 จุดและแสดง BTC/USDT timeframe 1h พร้อมแท่งย้อนหลัง;
- `GET /market-data/candles/pages` ตอบ 200, `PRESENT`, 1,000 rows;
- `GET /market-data/chart/live` ตอบ 200, `READY`, 1 live row;
- ไม่มี page error และไม่มี request ไป order หรือ trading-mode endpoint;
- console 401 สองรายการเกิดจาก `GET /auth/me` ก่อนสมัครตาม auth bootstrap ปกติ;
  หลัง register ทุก auth/chart request ที่เกี่ยวข้องผ่าน 200;
- ภาพหลักฐาน: [Chart with a real development session](2026-10-22-chart-real-session.png).

รอบนี้พิสูจน์การเข้า Chart ด้วย session จริงและ data flow browser → API → PostgreSQL →
renderer.

## Pan, pagination, Retry-After และ reset บน session จริง

ตรวจต่อบน development stack เดิมด้วยบัญชีและ server-side session จริง โดยไม่รัน
destructive fixture กับฐาน development:

- user gesture บนกราฟทำให้ browser ขอหน้าเก่าด้วย
  `before=2026-09-18T22:00:00Z` เพียงหนึ่งครั้ง;
- หน้าแรกและหน้าเก่าตอบ HTTP 200, `PRESENT`, หน้าใดละ 1,000 rows;
- หน้าเก่ามี `older_before=2026-08-16T14:00:00Z` และ
  `newer_after=2026-09-10T14:00:00Z`; summary/viewport เปลี่ยนจากแท่งล่าสุด
  22 ต.ค. ไปเป็นแท่ง 8 ก.ย. โดยกราฟยัง render ปกติ;
- กด `รีเซ็ตกราฟ` แล้ว summary/viewport กลับแท่งล่าสุด 22 ต.ค. และจำนวน
  `/candles/pages` requests คงที่ 2 — reset ไม่ยิง API หรือเปลี่ยนข้อมูล;
- ทดสอบ recovery โดย intercept เฉพาะ response แรกของหน้า 4h ที่ browser boundary
  ให้เป็น HTTP 429 `CHART_RATE_LIMITED`, `Retry-After: 2`; ข้อมูล/session และ
  request หลัง retry ยังใช้ API จริง;
- ปุ่ม `ลองใหม่` disabled ตลอด cooldown, ไม่มี auto-request เพิ่ม, enabled หลัง
  ครบเวลา; คลิกครั้งเดียวสร้าง request ใหม่หนึ่งครั้ง, API จริงตอบ 200 และ error/button หาย;
- ไม่พบ page error ในทั้งรอบ pagination/reset และ recovery.

ภาพหลักฐาน:

- [viewport หลังโหลดหน้าเก่า](2026-10-22-chart-pagination-older.png)
- [viewport หลัง reset กลับช่วงล่าสุด](2026-10-22-chart-pagination-reset.png)

ผลนี้ร่วมกับ browser 8 timeframe และ API traversal ในหลักฐาน 2026-10-14 ปิด V-H8
และ history-window acceptance V-H1..8. ไม่ใช้แทน V-17, soak, release gates หรือ
owner manual acceptance ที่ยังค้าง.

## Final targeted verification หลังแก้ API batching

ตรวจซ้ำบน development stack เวลา 2026-10-22 หลัง targeted resource regression
ของ F-11 โดยสร้างบัญชี disposable ผ่านฟอร์ม UI จริงใน Chromium process ใหม่:

- `POST /auth/register` ตอบ 201 และ `GET /auth/me` หลังสมัครตอบ 200;
- URL คงเป็น `/chart`, `candlestick-chart` มองเห็นได้ และ renderer มี canvas 7 จุด;
- history `/market-data/candles/pages` และ live `/market-data/chart/live` ตอบ 200;
- ไม่มี page error และไม่ได้ inject cookie, mock session หรือ mock chart response;
- snapshot DB หลัง browser flow: price `connected=true`, lease เหลือ 4.050/5 วินาที;
  candle `connected=true`, `bootstrapped=true`, lease เหลือ 18.987/20 วินาที;
  preview 372 rows และแถวล่าสุดอายุ 1.166 วินาที;
- log 15 นาทีล่าสุดไม่พบ `candle preview writer unavailable`,
  `price producer lease lost`, WARNING, ERROR, traceback หรือ ConnectError.

จึงยืนยันซ้ำว่า development Chart ใช้ server-side session และ data path จริงได้หลัง recovery.
warning สองข้อความยังคงถูกจัดประเภทเป็น host-sleep transient ที่ recover ได้ตามหลักฐานด้านบน;
ไม่เปลี่ยน lease/fencing timeout และผลนี้ไม่แทน V-17/owner manual/release gates.

## Development-closure automation — 2026-10-22

เพิ่ม automated evidence สำหรับช่องว่างที่ยังระบุเป็น Partial/Not Run ใน TF-04..13 และ TW-07
บน branch `fix/f12-development-closure`, base source `4d2eec4c58a5`. การเปลี่ยนแปลงรอบนี้
เพิ่ม tests เท่านั้น ไม่เปลี่ยน production runtime, schema, trading logic หรือ safety bounds.

หลักฐานที่เพิ่ม:

- PostgreSQL migration tests ตรวจ checksum แถวเดิมข้าม `0025 -> 0026`, inventory/grants
  ของ monthly partitions ทุกเดือนใน five-year retention ถึง horizon, invalid casing/open/end
  ของ `1w`/`1M` และ SQL/Python schedule parity ครบ 8 TF ที่ leap/year edges;
- core indicator test ตรวจ weekly warm-up 201 slots ถึง EMA200 และ monthly 60 slots ยัง
  WARM_UP โดยไม่เติมข้อมูลหรือเปลี่ยน Money/Quantity arithmetic;
- checkpoint codec test ปฏิเสธ W1/MN1 ที่ skipped, repeated หรือ misaligned;
- mocked bootstrap test ยืนยัน effective F-38 inventory เป็น 16 series และ state-machine gap
  coalescing ใช้ timeframe เดิมสำหรับ H1/W1/MN1 โดยไม่ประกาศ preview เป็น CLOSED;
- authenticated candle-page route tests ครบ 8 TF; `1W`/`1mo` ยังคงถูกปฏิเสธ;
- frontend E2E เพิ่ม computed-style assertions ของ Admin Template controls และยืนยันว่า
  candle-only page ไม่เรียก `/indicators`.

ผล targeted checks ของ source เดียวกันก่อนบันทึก:

- backend pure affected suites (`test_candle_realtime.py`, `test_indicators.py`,
  `test_codec.py`) ผ่าน;
- candle authenticated route suite **24 passed**;
- migration module บน isolated PostgreSQL ฉบับสุดท้ายผ่าน **18 passed**; ชุด tests ใหม่
  โดยตรงผ่าน **15 passed**. รอบแรกหลัง Docker daemon กลับมาพบ downgrade-guard เดิม
  1 case เห็น row count เป็น 0 หลังการรันที่ถูกขัดจังหวะ; case เดียวกันผ่านเมื่อรันแยก
  และ clean-state full module ผ่าน 18/18 จึงจัดเป็น fixture state จากรอบที่ถูกตัด ไม่ใช่
  production/migration regression และยังเก็บผลล้มนี้ไว้ในบันทึก;
- chart-related backend selection ผ่านทุก assertion; `test_chart_routes.py` ที่เคย setup
  error เพราะ Redis ไม่มี host port ผ่าน **16 passed** หลังใช้ Redis แยกที่ port 56379;
- frontend chart selection ผ่าน **71 tests / 8 files**, type-check และ ESLint ผ่าน;
- Ruff check/format ของ backend files ที่เปลี่ยนและ `git diff --check` ผ่าน.

Chromium จริงจาก Linux container เข้า `http://localhost:5173` ผ่าน development stack,
สมัคร disposable account ด้วยแบบฟอร์มจริงและได้ server-side session. ผลสุดท้าย:

- URL `/chart`, renderer **7 canvases**, options ครบ
  `1m/5m/15m/1h/4h/1d/1w/1M`;
- authenticated candle pages ของ `1w` และ `1M` ตอบ HTTP 200;
- select computed style เป็น `appearance: none`, border `rgb(208, 213, 221)`, radius
  `8px`, height `44px`; focus border `rgb(156, 185, 255)`;
- disabled button เป็น disabled จริง, cursor `not-allowed`, opacity `0.5`, radius `8px`;
- viewport 375/768/1440 ไม่มี document horizontal overflow หลัง responsive layout settle
  และ canvas ยังมองเห็นได้;
- ไม่มี page error และ request log ไม่มี Binance, order, trading-account-use หรือ
  `/indicators` request.

รอบนี้เพิ่มหลักฐานส่วนใหญ่ แต่ review ถัดมาพบว่า TF-10 ยังขาด integration recovery ครบ flow
และ TF-13 ยังขาด chart/indicator API matrix; ทั้งสองช่องว่างถูกปิดใน post-review closure
ด้านล่าง. F-12 ยังคง **In Progress** เพราะ V-17/workload/resource/endurance กับ release gates
ยังเป็น **Pending Full Validation** ตามกำหนดเดิม. ยังไม่มี commit หรือ push ในรอบนี้.

หลังตรวจเสร็จลบ isolated database `tiewtrade_f12_validation`, temporary Redis container
และ browser-validation images ที่สร้างในรอบนี้แล้ว; ไม่ลบหรือแก้ข้อมูลใน development database.

## Owner Manual Acceptance — 2026-10-22

เปิด development stack ด้วย `compose.yaml` + `compose.chart.dev.yaml`; API health ตอบ 200,
frontend `/chart` ตอบ 200 และ services ที่เกี่ยวข้อง healthy. เปิดหน้า Chart ใน Google Chrome
ให้เจ้าของตรวจด้วย session จริง แล้วเจ้าของยืนยันในบทสนทนาว่า **“ตรวจแล้วผ่าน”**.

บันทึกผล owner manual เป็น Passed โดยใช้ร่วมกับ browser/network evidence ด้านบน. F-12
ยังคง **In Progress** เพราะ V-17 workload/resource/endurance และ release gates ที่พึ่ง V-17
ยังเป็น Pending Full Validation; branch ปัจจุบันยังไม่ได้ commit หรือ push.

## Review/refactor checkpoint — 2026-10-22

รีวิวเฉพาะ tests ที่เพิ่ม/แก้ใน development closure แล้ว refactor โดยไม่แตะ production code:
ใช้ `Timeframe` enum แทน timeframe strings ซ้ำ, reuse candle fixture และ calendar schedule,
รวม checkpoint setup, รวม SQL candle insert/checksum helper, ลด intermediate collections และ
เปลี่ยน finality assertion ที่ซ้ำค่าต้นทางให้ตรวจ state ที่ supervisor เก็บจริง. ฝั่ง E2E จัด
computed-style assertion ให้อ่านง่ายและรวม forbidden-request scan โดยคงเงื่อนไขเดิม.

ผลหลัง refactor: backend affected pure suites ผ่าน, migration **18 passed**, authenticated
candle routes **24 passed**, Ruff ทั้ง **493 files**, mypy **450 files** และ import contracts
**7/7** ผ่าน. Frontend ESLint/typecheck ผ่านและ Playwright compile/discovery พบ Chart stories
ครบ **7 tests**. ไม่รัน browser flow ซ้ำเพราะไม่มี runtime/UI behavior เปลี่ยน และ real-browser
หลักฐานก่อน refactor ยังใช้ source runtime เดิม. ลบ PostgreSQL/Redis ชั่วคราวหลังตรวจแล้ว.

## Post-review TF-10/TF-13 closure — 2026-10-22

แก้ findings จาก deep review โดยเพิ่มหลักฐานที่ขาดโดยไม่เปลี่ยน production code:

- TF-10: actual-role PostgreSQL integration 3 cases สำหรับ H1/W1/MN1 จำลอง preview gap,
  disconnect, reconnect/bootstrap และให้ fake REST source ผ่าน ingestion จริงจน demand เป็น
  COMPLETE; ตรวจว่าทุก request ใช้ timeframe เดิม, จำนวน `open_at` ไม่ซ้ำ, จำนวนแถวตรง
  calendar window และทั้ง preview/REST ไม่ถูกประกาศ CLOSED;
- TF-13: authenticated chart-history และ indicator routes รับ `1w`/`1M` ถึง controller
  boundary และปฏิเสธ `1W`, `1mo`, trailing-space ด้วย sanitized `INPUT_REJECTED` รวม 8 cases;
- แก้ migration grant assertion ให้ `bool_and` ตรวจ market-data worker ครบทุกสิทธิ์
  SELECT/INSERT/UPDATE/DELETE และแยก codec misalignment ให้อยู่ใน calculation window.

ผลตรวจบน isolated PostgreSQL/Redis: TF-10 ใหม่ **3 passed**, TF-13 ใหม่ **8 passed**,
codec **88 passed**, focused migration grant regressionผ่าน; Ruff check/format และ
`git diff --check` ผ่าน. การลองรัน chart-route module ทั้งไฟล์ต่อจาก fresh isolated DB พบ
prepared-indicator cases เดิม setup error `SOURCE_BOOTSTRAP_REQUIRED` เพราะ source-proof
bootstrap ของ full-suite ordering ยังไม่ได้รัน; tests ใหม่ทั้ง 11 cases ผ่านแยกและไม่ถูกนับกลบ
ด้วย setup error นี้. ลบฐาน/Redis ชั่วคราวและคืน test container เป็นสถานะเดิมหลังตรวจ.

## Candidate-gate attempt — 2026-10-22

รัน candidate gates กับ uncommitted source บน branch `fix/f12-development-closure`
โดยใช้ containers และ PostgreSQL/Redis แยกจาก development stack:

- backend Ruff check/format, mypy **450 files** และ import contracts **7/7** ผ่าน;
- frontend ESLint/typecheck ผ่าน, Vitest **246 passed**, production build ผ่าน;
- exported OpenAPI และ generated TypeScript ตรงกับไฟล์ใน repo;
- full backend รอบแรกพบว่า
  `0030_supported_pairs_reduction.downgrade()` เปลี่ยน constraint ของ `market_candles`
  โดยไม่เปิด source-maintenance scope และ PostgreSQL ปฏิเสธด้วย
  `SOURCE_MAINTENANCE_SCOPE_REQUIRED`; เจ้าของอนุมัติขยาย scope ให้แก้ migration 0030;
- เพิ่ม maintenance scope ใน downgrade และ actual-PostgreSQL regression ที่ยืนยันว่า event
  trigger เปิดอยู่, downgrade ขยาย constraint ได้ และ upgrade คืน head; focused migration
  regression ผ่าน **3 passed**;
- full run บนฐานที่ใช้ซ้ำพบ resource/setup errors ซึ่งผ่านทันทีเมื่อ rerun **3 passed**;
  ไม่ใช้ผลนั้นเป็น acceptance. จากนั้นสร้าง PostgreSQL/Redis ชั่วคราวใหม่, bootstrap และ
  migrate จาก clean state แล้ว full backend ผ่าน exit 0: **3017 passed, 1 skipped,
  2 deselected** ใน 501.46 วินาที.

รอบ diagnostic ที่ย้ายเฉพาะ `backend/` เข้า container ไม่ใช้เป็น acceptance result เพราะ
repo-relative fixtures หา `specs/`, `.github/`, `config/` และไฟล์ root ไม่พบ; บันทึกไว้เป็น
harness failure เท่านั้น. V-18 ยังคง **Partial** เฉพาะเพราะ branch ยังไม่ commit/push/CI และ
ส่วนที่พึ่ง V-17 ยังเป็น Pending Full Validation; local candidate gates ที่รันในรอบนี้ผ่านแล้ว.
