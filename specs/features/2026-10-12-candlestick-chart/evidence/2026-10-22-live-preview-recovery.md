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
