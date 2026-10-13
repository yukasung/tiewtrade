# F-12 — กราฟแท่งเทียนบนหน้าเว็บ — Plan

สถานะ: **Approved** — เจ้าของอนุมัติวันที่ 2026-10-13 — แผน amendment วันที่ 2026-10-13 สำหรับการแสดงแท่งเทียนก่อน indicator;
การอนุมัติเดิม, การลบ Volume pane และ initial viewport แบบ TradingView ยังมีผลกับส่วนที่ไม่ถูกแก้
การลบ MACD ด้านล่าง: **Approved** — เจ้าของอนุมัติ amendment เมื่อ 2026-10-13
การย้ายรายละเอียดแท่งเข้า chart ด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13
การลบแถบสถานะถาวรด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13
การลบ Indicator จาก UI ด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13
การลด controls และข้อความใต้กราฟด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-14
การเพิ่มปุ่มรีเซ็ตกราฟภาษาไทย: **Approved** — เจ้าของยืนยันเมื่อ 2026-10-14
การลบตัวเลือกภาษาออกจากหน้า Chart: **Approved** — เจ้าของยืนยันเมื่อ 2026-10-14
การจัดหน้าแบบ Trading Workspace ด้านล่าง: **Approved** — เจ้าของสั่งเริ่มปรับ UI เมื่อ 2026-10-14
การปรับสัดส่วนและความสูง workspace: **Approved** — เจ้าของสั่งแก้เมื่อ 2026-10-14
การย่อ market bar และลบ visible labels: **Approved** — เจ้าของสั่งแก้เมื่อ 2026-10-14
การจัดตำแหน่ง history tabs ตาม Admin Template: **Approved** — เจ้าของสั่งแก้เมื่อ 2026-10-14
โหมด Light/Dark จาก Admin Template: **Approved** — เจ้าของสั่งเพิ่มเมื่อ 2026-10-14
วันที่: 2026-10-12
Branch: feature/f-12-candlestick-chart
Requirements: [ฉบับที่รีวิวผ่าน](requirements.md)
หลักฐานต้นทาง: [source-evidence.md](source-evidence.md)
บันทึกสถาปัตยกรรมที่เสนอ: [ADR-003](../../decisions/003-chart-market-data.md)

## Amendment — จัดหน้าแบบ Trading Workspace (Approved 2026-10-14)

### โครงสร้างและของเดิมที่ใช้ซ้ำ

- คง `AccountLayout`, `AccountHeader` และ `AccountSidebar` เพื่อให้ module อื่นยังอยู่คนละหน้า;
  สำหรับ page `chart` ลด presentation ของ breadcrumb/card header ที่กินพื้นที่ และใช้ content width เต็มเดิม.
- ปรับ `CandlestickChartPanel.tsx` ให้เป็น workspace grid โดยย้าย pair/timeframe/reset เข้า market bar,
  วาง chart ใน grid area หลัก และไม่เปลี่ยน `useChartData`, renderer, exact OHLCV, viewport หรือ query key.
- ใช้ `frontend/src/components/ui/{Input,Select,Label,Button}.tsx` สำหรับ form placeholder.
  Controls ทุกตัวใส่ `disabled` จาก markup, ไม่มี submit handler และไม่สร้าง form action.
- เพิ่ม shared table primitives ที่ `frontend/src/components/ui/Table.tsx` โดยปรับจาก
  `references/admin-template/src/components/ui/table/` และใช้โครงสี/spacing จาก
  `references/admin-template/src/components/tables/BasicTables/BasicTableOne.tsx`.
- เพิ่ม horizontal tab presentation ขนาดเล็กใน shared UI โดยปรับ interaction/style จาก
  `references/admin-template/src/components/ui/tabs/VerticalTabs.tsx`; ใน placeholder ใช้เพียง
  active state ด้านภาพและไม่เรียกข้อมูลออเดอร์.
- สร้าง presentation components สำหรับ `TradingOrderPlaceholder` และ `TradeHistoryPlaceholder`
  แยกจาก chart data controller เพื่อให้งาน F-13–F-16/F-28 แทนที่ได้โดยไม่แตะ renderer.

### Layout และ responsive behavior

- Desktop ใช้ CSS grid areas: market bar เต็มความกว้าง, chart ด้านซ้าย, order placeholder ด้านขวา,
  history ใต้ chart โดย order placeholder อยู่ต่อเนื่องด้านขวา. ใช้ border/background/spacing/radius
  จาก Admin Template tokens และไม่คัดลอกสีหรือตราสินค้า Binance.
- ให้ grid สูงเท่าพื้นที่ viewport ใต้ account header, ปิด document overflow ที่เกิดจาก workspace และแบ่ง
  แถวเนื้อหาให้ history สูงกว่า chart; chart canvas ยืดตาม grid row แทนการกำหนดด้วย viewport height ซ้ำ.
- ลบ heading/label ที่มองเห็นใน market bar, ย้ายชื่อ pair/TF ไปเป็น `aria-label` ของ Select และลด
  padding/spacing เฉพาะแถบ โดยคง shared Select/Button และ touch target เดิม.
- เปลี่ยน shared `Tabs` ไปใช้โครง underline tabs จาก Admin Template โดยตรง และวาง history tabs ชิดซ้าย
  ใน header ที่มี border แยกจาก chart; คง disabled semantics ของ placeholder และไม่มี handler.
- เพิ่ม `ThemeProvider` และ `ThemeToggleButton` โดยปรับจาก Admin Template, ใช้ root `.dark`, บันทึก
  `light|dark` ใน local storage และวาง toggle ด้านขวาของ account header.
- เพิ่ม dark tokens/variants ให้ shared controls และ workspace; renderer เพิ่ม `applyTheme()` เพื่ออ่าน CSS
  chart tokens ใหม่แล้วเรียก Lightweight Charts `applyOptions` โดยไม่สร้าง chart/data controller ใหม่.
- กำหนดคอลัมน์ขวาด้วยช่วงความกว้างที่ bounded และให้ chart ใช้พื้นที่ที่เหลือ (`minmax(0, 1fr)`)
  เพื่อไม่ทำให้ canvas ล้น. ความสูง chart ยัง responsive และไม่ลดพื้นที่ต่ำกว่าเกณฑ์เดิมบนจอแคบ.
- ต่ำกว่า desktop breakpoint ให้เรียง market bar → chart → order placeholder → history;
  คืนความสูงเป็น auto เพื่อให้หน้าเลื่อนแนวตั้งได้, table ใช้ container overflow เฉพาะแนวนอน
  และหน้าทั้งหน้าต้องไม่มี horizontal overflow.
- กราฟยังพื้นขาวและ controls ใช้ Admin Template states. ไม่เพิ่ม dark theme ใน amendment นี้.

### ขอบเขตความปลอดภัย

- Placeholder ไม่รับค่าใช้งานจริง: input/select/action disabled, ไม่มีค่า balance/quantity/price เริ่มต้น,
  ไม่มีการคำนวณเงินและไม่มีข้อความที่อ้างว่า Paper หรือ Live พร้อมใช้งาน. ปุ่ม placeholder ใช้ข้อความ
  `ยังไม่เปิดใช้งาน` ไม่ใช้ข้อความซื้อ/ขายหรือข้อความที่ทำให้เข้าใจว่าเป็นปุ่มส่งออเดอร์.
- History แสดงเฉพาะหัวตารางและ empty state; ไม่มี mock order/trade และไม่อ่าน endpoint ใหม่.
- ห้ามแก้ backend, OpenAPI, database, auth, trading domain หรือ exchange adapter.
- ตรวจ diff ให้ไม่มี request ใหม่ชนิด POST/PUT/PATCH/DELETE และ browser smoke ต้องยืนยันว่า interaction
  กับ placeholder ไม่ก่อ order/trading network request.

### ลำดับทำงานและการตรวจระหว่างพัฒนา

1. เพิ่ม shared Table/Tabs จาก source path ของ Admin Template พร้อม focused component tests.
2. เพิ่ม placeholder components แบบ disabled และ assertions ด้าน accessibility/ไม่มี handler.
3. จัด workspace grid และย้าย chart เดิมเข้า area ใหม่โดยไม่แก้ data/rendering behavior.
4. รัน targeted component/layout/renderer tests, type-check และ scoped ESLint เป็นชุดเดียว.
5. อัปเดตเฉพาะ frontend ที่กำลังรัน แล้วทำ browser smoke ที่ desktop/mobile รวม TF switch,
   computed styles ของ controls และ network log. ไม่รัน full suite เพราะ amendment นี้ไม่แตะ contract
   หรือ trading logic; full validation เดิมยังค้างตาม checkpoint F-12.

## Amendment — ลบตัวเลือกภาษาออกจากหน้า Chart (Approved 2026-10-14)

- ลบ language `Select` และ locale state/change handler จาก `CandlestickChartPanel.tsx`.
- ใช้ locale ภาษาไทยคงที่กับ renderer และ `MarketTime`; ไม่แตะ i18n หรือหน้าจอ module อื่น.
- ปรับ component/E2E assertions ให้เหลือคู่เทรด, timeframe และปุ่ม `รีเซ็ตกราฟ` แล้วรัน
  targeted component/renderer tests, type-check และ scoped ESLint.

## Amendment — ปุ่มรีเซ็ตกราฟภาษาไทย (Approved 2026-10-14)

- เพิ่มปุ่ม `รีเซ็ตกราฟ` ใน `CandlestickChartPanel.tsx` โดยใช้ Button component เดิมของ frontend.
- ใช้ renderer/time-scale ที่มีอยู่คืน visible logical range ให้ viewport เริ่มต้นซึ่งยึดแท่งล่าสุด;
  ไม่เพิ่ม query, API call, data mutation หรือ backend change.
- เพิ่ม component test ตรวจข้อความภาษาไทย, keyboard-accessible button, viewport reset และยืนยันว่า
  pair/TF/language ไม่เปลี่ยน. รัน targeted component/renderer tests, type-check และ scoped ESLint.

## Amendment — ลด controls และข้อความใต้กราฟ (Approved 2026-10-14)

- ลบปุ่ม manual navigation/history/retry/refresh และ scale note จาก
  `CandlestickChartPanel.tsx`; ลบ handler/state/import และ CSS ที่ไม่ใช้แล้ว.
- คง pair/TF/language controls, automatic query/recovery, chart pan/zoom/crosshair,
  exact OHLCV header และ error alert.
- ปรับ component/E2E assertions แล้วรัน targeted tests, type-check, ESLint และ
  rebuild/restart เฉพาะ frontend.

## Amendment — ลบ Indicator จาก UI (Approved 2026-10-13)

- ลบ fieldset ตัวเลือก indicator, state/toggle และรายละเอียด indicator จาก
  `CandlestickChartPanel.tsx`; ส่งชุด indicator ว่างให้ renderer เพื่อไม่สร้างเส้นหรือ pane.
- คง candle/gap timeline และ contract การอ่าน history เดิมในรอบนี้ เพื่อไม่เปลี่ยน backend
  หรือ proof/consistency boundary นอกขอบเขต UI.
- ลบ CSS/tests/E2E ที่อ้าง controls และ pane; ยืนยันว่า chart ยังแสดง OHLCV exact,
  เปลี่ยนคู่/TF และเลือกแท่งได้. รัน targeted tests, type-check, ESLint และ rebuild frontend.

## Amendment — ลบแถบสถานะถาวร (Approved 2026-10-13)

- ลบ `chart-status` จาก `CandlestickChartPanel.tsx` และ CSS ที่ใช้เฉพาะ block นี้.
- คง `role="alert"` สำหรับ request/render failure, finality ใน chart, disabled/loading
  state ของ controls และข้อความ gap เมื่อผู้ใช้เลือกตำแหน่งที่ไม่มีแท่ง.
- ปรับ component/E2E assertions ที่อ้างข้อความสถานะถาวร; รัน targeted tests,
  type-check และ ESLint แล้ว rebuild/restart เฉพาะ frontend.

## Amendment — ย้ายรายละเอียดแท่งเข้า chart (Approved 2026-10-13)

- ใช้ `CandlestickChartPanel.tsx` และ `MarketTime`/`MarketValue` เดิม เพิ่มเวลาและ V
  ใน `chart-chart-header` โดยอ่าน exact string จาก candle cache; ไม่คำนวณหรือปัดราคา.
- ลบเฉพาะข้อความวันเวลา/OHLCV ที่ซ้ำใน `chart-selection`; คงปุ่มก่อนหน้า/ถัดไป
  และรายการ indicator เพื่อรักษา keyboard access และข้อมูลที่ proof ผ่าน.
- ปรับ CSS ให้ header wrap บนจอแคบโดยไม่บังแกนราคา และปรับ component tests
  ให้ตรวจ latest/crosshair/keyboard selection, exact O/H/L/C/V และไม่มีข้อมูลซ้ำใต้กราฟ.
- รัน targeted component test, type-check และ ESLint แล้ว rebuild/restart เฉพาะ frontend.

## Amendment — ลบ MACD จากกราฟ (Approved 2026-10-13)

- ใช้ `CandlestickChartPanel.tsx` เดิม: ลบชื่อ MACD ทั้งสามจากรายการตัวเลือก
  และค่ารายละเอียด. ค่าเริ่มต้น EMA20/50/200 ไม่เปลี่ยน.
- ใช้ `chart/renderer.ts` เดิม: ลบการจัด pane ของ MACD แล้วจัด ATR ต่อจาก RSI;
  ไม่กระทบ price pane, candle viewport, exact-value boundary หรือ proof gate.
  ไม่เพิ่มการคำนวณ indicator ใน frontend.
- ปรับ fixture/unit/component/E2E ที่ตรวจรายการตัวเลือกและ pane ให้ยืนยันว่า
  ไม่มี MACD ใน UI และค่าที่เหลือยังเลือก/แสดงได้. ตรวจการเปลี่ยนคู่/timeframe,
  unavailable/proof mismatch และ browser smoke ของกราฟ; lint/type-check/build
  ตามผลกระทบ. ห้ามรัน full workload ซ้ำเพียงเพราะลบตัวเลือก UI.
- เปิด frontend ที่ใช้ชุดใหม่หลัง API v2 พร้อมแล้วเท่านั้น; ไม่แสดงค่า v1 ค้าง
  และไม่ลดเงื่อนไข consistency ของ bundle.

## แนวทาง

เพิ่มกราฟในพื้นที่ Account เดิม ใช้ Lightweight Charts **5.0.9**
ตรวจพบรุ่นนี้ใน npm registry เมื่อ 2026-10-12; pin แบบ exact ใน package.json
และ package-lock ก่อนนำมาใช้ ตรวจ package/license/API จริงใน V-01.
แบ่งข้อมูลเป็น history/indicator ที่อ่านใน snapshot เดียวกัน,
preview ของแท่งกำลังก่อตัวจาก kline feed และราคาสด F-10 ที่แสดงแยกกัน.
ไม่ประกอบ OHLC จาก trade stream และไม่คำนวณ indicator ในเว็บ.

แผนนี้เสนอ endpoint ใหม่สำหรับ bundle/proof/live preview โดยใช้ reader เดิม
ไม่เปลี่ยนผลลัพธ์หรือ cursor ของ endpoint F-09/F-11 เดิม.
LEGACY/PREPARED ยังใช้ gate และ numeric contract ของ F-11;
F-12 ไม่สั่ง activate source proof หรือ PREPARED และไม่ถือว่า capacity ที่ค้างผ่านแล้ว.
ส่วน extension ของ infra/API และการ coalesce demand ภายใน market-data
เจ้าของอนุมัติผ่านแผนฉบับนี้แล้ว; หากต้องเปลี่ยน contract งานเดิมนอกขอบที่ระบุ
ให้เสนอ amendment และหยุดตาม AGENTS.md.

## ของเดิมที่จะใช้ซ้ำ

| ของเดิม / path | การใช้ |
|---|---|
| `core/market_data.py`, `core/money/`, `core/indicators.py` ใต้ `backend/src/tiewtrade/` | Candle/Timeframe/หน่วย/สูตรเดิม ไม่สร้าง numeric rules ใหม่ |
| `venues/binance_th/{stream_transport,stream_mapping,transport,mapping,rate_limit,failures}.py` | gateway/control budgets/decoder/REST transport; แยกส่วน frame transport ที่ไม่ผูก trade โดยรักษา behavior F-10 |
| `venues/{candles,price_streams,fake}.py` | เพิ่ม CandleFeed events และ FakeVenue behavior แทน fake อีกชุด |
| `infra/market_data/{storage,claims,indicator_reader}.py` | history, coalesce, lease/fenced writes และ LEGACY reader |
| `infra/indicators/{prepared,source}.py`, `infra/crypto/indicator_cursor.py` | prepared reader, source proof, cursor/key lifecycle และ canonical serialization |
| `services/api/{indicator_routes,indicator_admission,indicator_settings}.py` | extraction ของ reader/controller สำหรับ bundle ใช้ budget/timeout/disconnect เดิม |
| `infra/db/session.py`, `infra/realtime/admission.py` | actual-role sessions, read-only snapshot, atomic admission |
| `services/market_data/{main,ingestion,realtime}.py` | lifecycle, F-09 worker และตัวอย่าง fencing ของ public feed |
| `frontend/src/{AccountSession,AuthPanel,RealtimePricePanel}.tsx`, `useRealtimePrices.ts` | QueryClient เดียว/auth expiry และราคาสดเดิม |
| `frontend/src/layout/`, `components/ui/`, `components/MarketValue.tsx` | layout/controls/ราคา exact/เวลาไทย |
| `frontend/src/{auth,realtimePrices}.ts`, `api-types.ts`, `*Messages.ts` | CSRF/error helpers, generated contract, translations |
| `backend/tests/infra/{market_data,indicators}/`, `frontend/e2e/helpers/` | actual-role PG races, parity, disposable DB และ E2E workers เดิม |

## 1. หน้ากราฟและขอบเขตข้อมูลในเว็บ

### Amendment: staged history loading

ใช้ของเดิม: GET `/market-data/candles` ใน
`backend/src/tiewtrade/services/api/candle_routes.py`, CandleHistoryView ใน
`frontend/src/api-types.ts`, TanStack Query/controller ใน
`frontend/src/chart/useChartData.ts` และ bounded decoder ใน `frontend/src/chart/api.ts`.
API เดิมใช้ server initial_window และ read_candles ไม่คำนวณ indicator;
อ่านสูงสุด 1,000 slots พร้อม coverage/gaps/observed_at และ finality.
ไม่เพิ่ม endpoint หรือเปลี่ยน seed/rollout mode.

- เพิ่ม candle-only query เริ่มทันทีหลัง mount/เปลี่ยนคู่หรือ TF ผ่าน timer ที่ cleanup ได้ใน
  StrictMode. ใช้ query key ผูก user/source/series/read epoch/window เช่นเดิม;
  หนึ่งคำขอต่อ episode, timeout 10s, payload limit 2MiB, retry=false.
  GET ล่าสุดส่ง series และ limit=1000 โดยไม่ส่งเวลา browser;
  explicit window ส่ง bounds ของการดูช่วงนั้นและ limit=1000.
- Live snapshot และ history/indicator controller คงงบและ failure policy เดิม.
  เจ้าของอนุมัติ 2026-10-13 ให้ History เริ่มผ่าน cancelable timer ทันทีเมื่อไม่มี
  reader เดิมค้าง. เมื่อเปลี่ยน episode และยกเลิก history/proof ที่กำลัง fetch ให้เก็บ
  monotonic cleanup deadline 2s; การเปลี่ยน TF ซ้ำก่อนเริ่ม request ต้องรักษาเวลาที่เหลือ.
  ไม่รอเพราะ candle-only/live query และไม่กั้นสอง query นี้. Server admission และ busy
  retry เดิมยังรองรับ contention จากแท็บอื่นหรือการ remount ใหม่.
  Candle-only error ไม่ยกเลิก coherent read ที่ยังทำงาน; session 401 ใช้ auth flow เดิม.
- ก่อน bundle แรกพร้อม ใช้ candle-only rows สำหรับกราฟและ exact selection พร้อม coverage,
  gaps และ observed_at ของคำตอบนั้น; indicator ทั้ง series/tooltip ถูกซ่อนไว้.
  รวม live เฉพาะ open-time ที่ไม่ซ้ำ โดย live ใช้แทน candle ชั่วคราวที่เวลาเดียวกัน;
  นี่เป็น display เท่านั้น ไม่คำนวณ indicator/finality และไม่เปลี่ยน cache ต้นฉบับ.
- เมื่อ bundle แรกพร้อม ใช้ candles/points/as_of ของ bundle ทั้งชุดใน render เดียวกัน
  และใช้นโยบาย proof/preview เดิมในหัวข้อ 5. คำตอบ candle-only ที่มาภายหลังถูกเพิกเฉยต่อ display.
  Refetch/error ของ bundle ภายหลังไม่ย้อนกลับไป candle-only ของ episode นั้น.
- Reset provisional viewport หนึ่งครั้งเมื่อ bundle แรกพร้อมตามกลไกเดิม; update ถัดไปคง
  user viewport. เปลี่ยนคู่/TF, retry, window, logout หรือ unmount ยกเลิก candle-only งานเก่า.
  ไม่ retain ข้อมูลข้าม user/series หรืออ้างข้อมูลชั่วคราวเป็น proof.
- แสดงสถานะแยกประวัติแท่งเทียนกับ indicator; empty/partial/failed ใช้ coverage/error จริง,
  ไม่เรียก PRESENT ว่า CLOSED. ไม่ POST หรือวน polling candle-only เอง.

ข้อเพิ่มเติมนี้แทนเฉพาะช่วงก่อน coherent bundle แรกในหัวข้อ 5;
ข้อกำหนด snapshot/proof เดิมยังใช้เมื่อแสดง indicator.

การ mount/anchor ในหัวข้อนี้และรายการไฟล์ด้านล่างถูกแทนโดย
[navigation plan ส่วนเพิ่มที่อนุมัติ](navigation-plan-amendment.md) ตามคำสั่ง
เจ้าของ “implement” วันที่ 2026-10-12: หนึ่ง module ต่อหนึ่งหน้า และ chart เป็น default.
ข้ออื่นของแผนนี้ยังมีผลตามเดิม.

- เพิ่ม panel `#market-chart-heading` และ sidebar anchor ใน AccountLayout เดิม
  ไม่เพิ่ม router/framework. ค่าเริ่มต้น BTCUSDT/1h, โหลดล่าสุด ≤1,000 slots.
  Initial viewport แสดง 100 logical slots ล่าสุดและเว้นด้านขวา 5 slots แบบ TradingView;
  แท่งจำนวนน้อยจึงยังเห็นชัดโดยไม่ fit เต็มพื้นที่หรือกองชิดขอบ. เมื่อข้อมูลอัปเดต
  ให้คง logical viewport ที่ผู้ใช้ปรับไว้.
  ไม่ persist ตัวเลือกใน localStorage รอบนี้.
- Candlestick + EMA อยู่บน price pane; ไม่สร้าง Volume pane. RSI/MACD/ATR มี pane แยกสเกล
  โดยใช้ time scale เดียวกัน. EMA20/50/200 เปิดเริ่มต้น; indicator อื่นเปิด/ปิดได้.
  ข้อมูล volume ยังคงอยู่ใน exact-data cache และ textual OHLCV panel แต่ไม่ส่งเข้า chart series.
- ทุกข้อความมีไทย/อังกฤษใน chartMessages; ภาษาผูกตัวเลือกที่มีใน UI ของ panel
  ยังไม่แปลหน้าเดิมทั้งระบบ. เวลาใช้ UTC identity และแสดง Asia/Bangkok ชัดเจน.
- ใช้ exact-data cache ใน AccountSession; chart series เป็น projection สำหรับวาด
  ไม่เป็นแหล่งเก็บ server data อีกชุด. ข้อมูลจริงไม่เก็บใน useState.
- ใช้ query key ผูก user identity/source/pair/timeframe/read epoch/revision.
  query/mutation retry=false, refetchOnWindowFocus=false, refetchOnReconnect=false;
  timer/controller ของแผนเป็นผู้เริ่มรอบทั้งหมด ไม่ปล่อย implicit retry.
- อ่านย้อนหลังทีละ ≤1,000 slots เมื่อผู้ใช้เลื่อนไปขอบหรือกดเพิ่มประวัติ
  โดยคง viewport; ไม่ไล่โหลดทั้งปีเอง. เก็บพร้อมกัน ≤12,000 slots ใน browser
  เป็น cache window ไม่ใช่เพดานประวัติ server. ทิ้งหน้าที่อยู่นอก viewport ±หนึ่งหน้า
  เมื่อเกินเพดานและโหลดกลับเมื่อผู้ใช้ร้องขอ ไม่ตัด seed หรือเปลี่ยนสูตร.
- Gap/ไม่มีค่าใช้ whitespace ที่เวลาเดิมและแยก continuous segments ของเส้น
  ไม่ให้ renderer เชื่อมผ่าน gap; WARM_UP/REFRESH_REQUIRED มีข้อความประกอบ.
- มี textual OHLCV/indicator panel พร้อม prev/next candle controls สำหรับ keyboard
  ใช้เวลาแท่งเพื่ออ่าน exact cache ไม่อ่านราคาย้อนจาก pixel/crosshair price.
- ResizeObserver ปรับ chart; cleanup observers/listeners/timers และ chart.remove()
  เมื่อ unmount. StrictMode/remount ไม่ทำให้ซ้อน listener/requests.
- คง attributionLogo และ NOTICE ใน third-party notices; มีลิงก์ TradingView
  ที่อ่านได้และไม่ถูก controls ทับ ตรวจ bundle/license ก่อนรับ dependency.

## 2. Numeric boundary

การปรับภาพตามคำสั่งเจ้าของ 2026-10-13: ใช้ `CandlestickChartPanel` และ
`chart/renderer` เดิมเพิ่มแถบชื่อคู่/TF/OHLC exact ใน chart frame, สีขาวเป็นค่าเริ่มต้น
chart frame ผ่าน CSS variables, เส้น/ป้ายราคาสุดท้ายของ Lightweight Charts และ
จัดสถานะให้กระชับ. ไม่เพิ่ม data source หรือคำนวณส่วนต่าง/เปอร์เซ็นต์ใน frontend;
ไม่เพิ่ม bid/ask หรือ order controls เพราะไม่มีสัญญาข้อมูลใน F-12.

เพิ่ม `frontend/src/chart/renderer.ts` เป็นจุดเดียวที่แปลง decimal string เป็น Number
ตาม NC-41. ใช้ Number.isFinite; ค่าบวกที่ underflow เป็นศูนย์หรือไม่มี representation
ที่วาดได้ต้องหยุดการวาด series ที่เกี่ยวข้องและแสดงข้อจำกัด.
ตรวจการแปลงทำให้ OHLC ordering ที่ต้นฉบับถูกต้องกลับด้านหรือไม่;
ห้ามปรับ high/low หรือปัดข้อความต้นฉบับเพื่อช่วย renderer.
การสูญเสียหลักท้ายที่ยังวาดได้เป็น approximation ของภาพตาม NC-41.

Tooltip/ตารางใช้ MarketValue/format exact text กลาง; แกนราคาของภาพต้องระบุ
ว่าเป็นสเกลสำหรับภาพ ไม่อ้างว่าเป็น exact quote. ปิด crosshair price label
ที่คำนวณจาก pixel และแสดง exact selected candle ใน panel แทน.
เวลาแปลงเป็น UTC epoch seconds สำหรับ chart โดยไม่เลื่อน timestamp เป็นเวลาไทย;
tick/crosshair time formatter ใช้ Intl กับ Asia/Bangkok.
ไม่เพิ่ม decimal library เพื่อคำนวณเงิน/indicator ใน browser.

## 3. Kline feed และ preview

เพิ่ม `venues/candle_streams.py` กับ adapter `venues/binance_th/candle_feed.py`
ใช้ connection เดียวรวม 30 series คงที่ ไม่ผูกจำนวน user/subscriptions ในเว็บ.
ใช้ explicit SUBSCRIBE/ack, bounded transport เดิม; ไม่แตะ trade connection ของ F-10.
decode e/s/k.s/i/t/T/o/h/l/c/v/n/f/L/x เป็นชนิดกลางที่ตรวจหน่วย/เวลาแล้ว
ชื่อ field ตลาดอยู่เฉพาะ adapter. Normalize inclusive end ตาม parser ของ F-09.

Ordering เป็น partial order ใน connection epoch เดียวกัน:
identity ต้องเหมือนกัน, exact duplicate เป็น no-op, snapshot ที่ต่างต้องมีหลักฐาน
ความคืบหน้าของ cumulative candle ตาม fixture/source checks ใน V-01/02.
ไม่ใช้ E/received_at/arrival order เป็น tie-breaker สำหรับสอง OHLC ที่ขัดกัน.
เสนอใช้ n ที่เพิ่มร่วมกับ open/f เดิม, volume/high ไม่ลดและ low ไม่เพิ่ม
เป็น conservative acceptance rule; ตัวที่ถูก dominate ถือว่าเก่าเฉพาะเมื่อ
หลักฐานดังกล่าวพิสูจน์ได้. Same progress แต่ OHLC ต่าง หรือการย้อน cumulative
ที่แยก stale จาก correction ไม่ได้ ให้ invalidate series และกู้จาก epoch ใหม่
ไม่เลือกค่าข้างใดเอง. ถ้า V-01 ไม่รองรับกฎนี้ ต้องกลับมาแก้แผนก่อน adapter.

ใน preview ระบุ finality=OPEN ระหว่างช่วงเปิด และ UNCONFIRMED เมื่อหมดช่วง
หรือได้รับ x=true; x เป็น upstream hint เท่านั้นในรอบนี้ ไม่เขียน CLOSED history.
ไม่ส่ง preview ให้ indicator reader และไม่ overwrite `market_candles` จาก stream.

เก็บ preview ในตาราง `market_candle_preview` สูงสุดสองแท่งล่าสุด/series (≤60 rows)
พร้อม event time, received_at, epoch, revision และสถานะ. market-data เขียน,
API อ่านเท่านั้น; Redis ส่ง invalidation หลัง commit และหายได้.
ไม่มีข้อมูลผู้ใช้/secret ไม่ต้อง RLS และไม่ใช่ประวัติ 365 วัน.
Restart ต้องเริ่ม RECOVERING; ข้อมูลค้างใน DB ไม่ทำให้พร้อมเอง.

ใช้ `market_candle_feed_state` หนึ่งแถวสำหรับ owner/epoch/lease และสถานะ 30 series
ใน metadata ที่ bounded. Singleton lease 20s, renewal ≤5s; หลังเสีย lease
writer เก่าห้าม publish ด้วย compare owner/epoch ใน transaction.
handoff ทำได้หลัง owner เดิมยืนยันหยุด connection หรือ lease+fence ป้องกัน write;
connection ที่ซ้อนระหว่าง network cleanup ไม่ให้สิทธิ์เขียนของ owner เก่า.
flush/coalesce ไม่เกินหนึ่ง transaction/2s รวม ≤30 changed series;
queue ใช้ latest slot ต่อ series ไม่สะสมทุก frame.

## 4. ประวัติเมื่อแท่งสิ้นสุดและการกู้คืน

เมื่อได้รับข้อมูลว่าช่วงแท่งผ่านแล้ว ให้ market-data ขอ window ของแท่งที่สิ้นสุด
ผ่าน shared demand coalescer ของ F-09 โดยไม่เรียก API service.
แยก `enqueue` user wrapper ออกจาก internal coalescing primitive ที่รับ
UserSession หรือ MarketDataSession ที่ตรวจ role แล้ว; ใช้ row lock,
refresh watermarks และ eligibility เดิม ไม่แก้ active lease/cursor/attempt budget.
ขอหนึ่ง window/series/interval และ deduplicate; ไม่ POST จาก event ทุกครั้ง.

F-09 worker เดิมเป็นผู้ดึง REST หลัง end_at และเขียนภายใต้ claim/source scope เดิม
จึงรักษา fetch_started_at/finality/partition/source journal. การอ่าน indicator
ที่ยอมรับแท่งต้องผ่าน F-11 ใหม่หลัง source commit ไม่อ้างจาก x/COMPLETE.
Source invalidation ของ F-11 และ builder ทำตาม scheduler เดิม.
เริ่มต้น coalesce latest window ≤1,000 slots ของ 30 series ครั้งเดียวต่อ bootstrap
และติดตาม progress; ไม่ reset failed rounds จากการ restart/stream update.

เมื่อ connection หลุด invalidation ทันที; reconnect ใช้ full jitter เพดาน30s,
protocol failure รออย่างน้อย30s, เคารพ Retry-After และ transport rotation เดิม.
กู้ช่วงตั้งแต่ observation ที่ยืนยันล่าสุดถึงช่วงปัจจุบันผ่าน F-09 ภายใน365วัน
ทีละ bounded demand; ไม่ให้ lease recovery ย้อน bounds ออกนอก retention.
REST history ไม่ merge ลง provisional active candle; event รุ่นเก่าทิ้งทั้ง epoch.
READY ต้อง ack + valid fresh event + recent recovery overlap ของแท่งสิ้นสุด
commit แล้ว; backfill ส่วนเก่าที่ยังขาดแสดง coverage แยกและไม่รับรองว่าครบ.
ถ้า recovery overlap ยังไม่สำเร็จ preview แสดงได้พร้อม RECOVERING แต่ไม่ READY.

เกณฑ์สดที่เสนอ: event age ณ server snapshot ≤6s และเวลาตรวจการรับ event ≤6s
ท่อ feed ต่ออยู่/lease valid; เกินเกณฑ์ STALE, ไม่มี event NO_DATA.
E ไม่รับรอง ordering แต่ใช้ตรวจอายุ event ไม่ใช้เวลา recv รีเซ็ต event ที่เก่า.
เวลาอนาคตเกิน2s/เวลาไม่ถูกต้องให้ UNAVAILABLE. ไม่ใช้ browser clock รับรอง READY.
heartbeat/control frames ไม่ทำให้ candle READY. เกณฑ์นี้เป็นของ preview เท่านั้น
ไม่เปลี่ยนเกณฑ์ราคา10s หรือ finality ของ F-11.

## 5. API bundle และการพิสูจน์ความสอดคล้อง

เพิ่ม router `/market-data/chart` แบบ authenticated/no session renewal:

| เส้นทาง | สัญญา |
|---|---|
| GET `/history` | input เหมือน IndicatorQuery; output metadata/rows/refresh/cursor เดิม + `candles` ของ output slots ใน DB snapshot เดียวกัน + `display_proof` |
| GET `/live` | base/quote/timeframe เท่านั้น; preview ≤2 rows/status/epoch/revision/เวลาตรวจ ไม่ส่ง indicator หรือเข้า prepared reader |
| POST `/verify` | read-only computation รับ display_proof ใน JSON+CSRF; output MATCHED/CHANGED/UNVERIFIABLE พร้อมเวลาและ bounds ไม่ enqueue และไม่ต่อ session |

Extract controller/serializer จาก indicator_routes เป็น module กลางใน api และ
reader result assembly ใน infra ไม่ import service อื่นและไม่คัดลอกสูตร.
Bundle เรียก `read_prepared` หรือ `read_indicators` ตาม rollout เดิมใน
indicator_read_session เดิม อ่าน source OHLC output ก่อนจบ transaction เดียวกัน.
ค่า/สถานะทุกจุดต้องเหมือน GET indicators ที่อ้าง dataset เดียวกัน.
ไม่มีการ clamp explicit end ที่ใหม่กว่า prepared U; คง503ตามสัญญาเดิม.
จำกัดผลทั้ง indicator/candles/token รวม ≤2MiB ไม่ใช่งบแยกต่อ array.

display_proof ลงนามด้วย KeySource/keyring ของ indicator cursor โดยแยก purpose
`chart-display-v1`, schema/version และ MAC domain จาก cursor เดิมอย่างชัดเจน.
ผูก user/session/series/formula/dataset/as_of/L/U/output bounds/expiry;
อายุไม่เกิน cursor/generation/session เดิมและสูงสุด6h ไม่ต่ออายุด้วย polling.
ไม่ใส่ OHLC/secret ใน token ไม่ log/analytics/localStorage และไม่ echo input error.

Verify ตรวจ schema/MAC/session/expiry ก่อน DB; malformed=422 INPUT_REJECTED,
expired/changed=CHANGED โดยไม่ส่ง indicator ใหม่แทรกในผล verify.
PREPARED ใช้ proof_valid/source epoch/fence/journal floor และ generation expiry เดิม
ครอบทั้ง seed [L,U); proof state ไม่ READY/GC/DDL ตรวจไม่ได้ให้ UNVERIFIABLE.
LEGACY ไม่มีสิทธิ์แอบใช้ PREPARED: ใช้ read_indicators เดิมด้วย frozen bounds/as_of
และ expected revision ใน read-only snapshot เพื่อพิสูจน์ digest ทั้ง dependencies;
ถึงงบให้ error/unverifiable ไม่ fallback proof ที่ตรวจไม่ครบ.
ผล MATCHED ตรวจได้ ณเวลา snapshot เท่านั้น ไม่ใช่คำรับรองว่า source จะไม่เปลี่ยน.

UI เก็บ history OHLC และ indicator จาก bundle เป็นชุด immutable พร้อม as_of
ไม่ merge OHLC ที่เพิ่ง fetch จาก F-09 ทับชุดเดิม. Preview overlay ได้เฉพาะ
open_at≥calculation_end; preview ที่ทับช่วงคำนวณไม่แทน candle เดิมและระงับ
indicator จน bundle ใหม่สอดคล้องกัน. เมื่อ verify CHANGED/UNVERIFIABLE/error
ให้ซ่อน indicator/tooltip และคง candles ตาม timestamp พร้อมเหตุผล.
Verify ทุก15s สูงสุดหนึ่งงาน ไม่ทับ bundle/readiness request; หาก request ยังไม่จบ
ไม่สะสม timer. เมื่อเริ่ม verify ให้แสดงกำลังตรวจ ไม่อ้างว่าเป็นข้อมูลปัจจุบัน.
Last successful proof เกิน45s ให้ซ่อน overlay จนตรวจใหม่; machine clock ใช้
delivery timeout เท่านั้น ไม่ตัดสิน finality. Error อื่นหยุด auto work และให้ลองใหม่เอง
ตาม RQ-16; initial history `INDICATOR_BUSY` รออย่างน้อย 2s และไม่น้อยกว่า Retry-After
ภายในงบ readiness เดิม; source change ที่ตรวจได้เริ่ม bounded logical read ใหม่ได้หนึ่งรอบ
โดยไม่วนจาก same changed response.

## 6. งบ HTTP/controller ที่เสนอ

| งาน | เพดาน |
|---|---|
| History/verify | ใช้ IndicatorBudget/admission/DB pool เดียวกับ F-11, deadline30s, cleanup2s, query500ms/lock200ms, output≤1,000 slots/หน้า |
| Live GET | dedicated API pool1/overflow0, deadline2s/cleanup2s, statement500ms/lock200ms; admission namespace chart.live global6000/min, subject user120/min; Redis admission ใช้งานไม่ได้ให้ fail closed ตามรายละเอียดด้านล่าง |
| Live browser poll | ทุก2s หนึ่งงาน timeout3s; errorหยุดและแสดง delivery failure; reconnect จาก online/visibility หรือผู้ใช้ให้เริ่ม snapshot ใหม่โดยคง cooldown Retry-After |
| Readiness episode | รวม initial GET + INDICATOR_DATA_NOT_READY/INDICATOR_BUSY polls + 409 restart ≤12 requests, elapsed≤300s, หนึ่งงาน; not-ready spacing≥10s, busy spacing≥2s และทุกกรณี≥Retry-After นับหลัง response; timeout30s/request โดยลดตามเวลารวมที่เหลือ |
| 409 | หนึ่ง restart/logical read รวมทุก pagination/verify/readiness ไม่ reset งบเพราะ token expiry/เหตุผลต่างกัน |
| Refresh F-09 | POSTหนึ่งครั้งแล้ว GETทุก10s ≤6ครั้ง/60s; 200อ่าน bundleใหม่, 202รอ progress; status/error/401/timeout หยุดตาม F-11 |
| Browser display | ≤12,000 slots; หนึ่ง live/หนึ่ง proof-or-history request ต่อ active series; payload decode reject ก่อน cache เมื่อเกิน2MiB |

แยก Redis notification ออกจาก Redis admission: notification/invalidation หาย
หรือส่งไม่สำเร็จหลัง commit ไม่ทำให้ preview ใน PostgreSQL หาย; Live GET ที่ผ่าน
admission ยังอ่าน snapshot ล่าสุดจาก PG ได้โดยไม่ต้องรอ notification.
ถ้า Redis admission timeout/ใช้งานไม่ได้ ให้ Live GET คืน503
`CHART_ADMISSION_UNAVAILABLE` ก่อนอ่าน preview ไม่ bypass admission หรือใช้
local counter แทน. Redis ล่มทั้งระบบเข้ากรณีนี้; browser หยุด auto poll ตาม error
contract ไม่ใช้ readiness polling รอ Redis. History/verify คง admission/error
contract ของ F-11 เดิม. เก็บผล commit แยกจากผล publish ไม่ rollback preview
หรือประกาศ feed ไม่พร้อมเพียงเพราะ notification หาย.

Readiness poll เริ่มเฉพาะ503 INDICATOR_DATA_NOT_READY จากหน้าแรก;
429/504/503รหัสอื่น/422 หยุด ไม่มี framework auto-retry.
Successful response ที่ REFRESH_REQUIRED จบ episode และให้ขอ refresh เอง.
ถ้า MATCH ยังพิสูจน์ไม่ได้ใช้ budget/elapsedเดิม อ่าน bundleใหม่แบบ bounded
ไม่ reset episodeจาก stream event หรือเปลี่ยน revision.
หมดงบหยุดจนผู้ใช้เริ่มใหม่; ไม่ใช้ eventใหม่ทำให้ episodeที่หมดงบกลับเอง.
สัญญาณ source ที่อยู่นอก L/U ไม่ยกเลิก dataset เดิม; ใหม่เข้าเกณฑ์ให้ coalesce
การเริ่มรอบล่าสุดได้เมื่อไม่มี active/stopped episode และไม่ refresh seed เอง.

ทุก POST ใช้ CSRF เดิม; เพิ่ม RouteRule renews=false สำหรับ verify และ GETใหม่
ไม่เพิ่ม PUBLIC_ROUTES. Backend middleware/session checks เดิมใช้ทุก HTTP request.
ออกจากหน้า/เปลี่ยน pair/401 ยกเลิก AbortController/timers และทิ้ง pending results
ด้วย read epoch; visibility hidden หยุด machine requests และซ่อนการรับรอง freshness
กลับ visible รับ live snapshot ใหม่ แล้วตรวจ bundle/proof ก่อนเปิด overlay.

## 7. ฐานข้อมูล / migration / rollback

เสนอ migration `0024_chart_candle_preview.py` (ถ้าเลขนี้ยังว่างตอนลงมือ):
preview ≤60 rows และ feed state bounded metadata; timestamptz UTC,
ราคา/quantity ใช้ domainsเดิม, UNIQUE series/open_at และ lease compare epoch.
ให้ migrator เป็น owner, market-data DML เฉพาะสองตารางใหม่, API SELECT;
ไม่ให้ builder/engine/auth/engine-scan อ่านเพิ่มโดยไม่จำเป็น.
ใช้ database security definer เฉพาะเมื่อจำเป็นต่อ singleton claim โดย pinsearch_path
และ revoke PUBLIC; ไม่มี SQL credentials ใน browser หรือ backend error.

ไม่มี migration แท่งเทียน/indicator checkpoint/retention เพิ่ม และไม่มี journalใหม่
คัดลอกของ F-11. preview cleanup ลบแท่งเก่าภายใน write transaction ที่ fenced.
Rollback ต้องหยุด feed/controllerใหม่และ drain chart readers ก่อน downgrade0024;
ลบเฉพาะ preview/state ไม่ลบ market_candles/indicator generations/ผู้ใช้/audit.
Default feature flagปิดจน migration/role/gateway/tests ผ่าน; flagไม่ได้เปลี่ยน Live.

## 8. สิ่งที่จะเพิ่ม/แก้

| กลุ่มไฟล์ | การเปลี่ยน |
|---|---|
| `backend/src/tiewtrade/venues/candle_streams.py`, `venues/binance_th/{candle_feed,candle_stream_mapping}.py`, `venues/{fake,__init__}.py` | สัญญา/adapter/fake/factory ใหม่ |
| `venues/binance_th/stream_transport.py` | extract reusable bounded frame gateway แยก trade decoder; F-10 golden tests ต้องเหมือนเดิม |
| `infra/market_data/{storage,candle_preview}.py`, `services/market_data/{main,candle_realtime}.py` | internal coalescer, fenced preview/supervisor และ lifecycle |
| `services/api/{chart_routes,indicator_read_controller}.py`, `indicator_routes.py`, `infra/market_data/chart_reader.py`, `infra/crypto/chart_proof.py` | same-snapshot bundle, validation proof; refactorเฉพาะ readerที่ใช้ร่วม |
| `services/api/{app,routing_policy}.py`, `backend/openapi.json`, `frontend/src/api-types.ts` | lifespan/pools/newroutes/generatedcontracts |
| `backend/migrations/versions/0024_chart_candle_preview.py` | schema/grants/rollback ตามข้อ7 |
| `frontend/src/chart/`, `CandlestickChartPanel.tsx`, `chartMessages.ts`, `CandlestickChartPanel.css` | controller/renderer/panes/exact selection/UI |
| `AuthPanel.tsx`, `layout/AccountSidebar.tsx`, `components/MarketValue.tsx` | mount/anchor และ shared exact formatter ตามจำเป็น ไม่เปลี่ยน auth behavior |
| `frontend/package.json`, `package-lock.json`, notices | dependency pin/license |
| `backend/tests/{venues,infra,api,services}/`, `frontend/tests/`, `frontend/e2e/` | coverageตาม validation; extension E2E market-data fake workers |

ชื่อไฟล์ใหม่เป็นสิ่งที่จะสร้าง ไม่อ้างว่ามีแล้ว. ใช้ lifespan ของ `services/api/app.py`
และ entrypoint ของ `services/market_data/main.py` ที่มีอยู่ ไม่สร้าง entrypointคู่ขนาน.

## 9. ลำดับลงมือหลังอนุมัติ

1. V-01 เก็บ fixture/ตรวจ transport/numeric/dependency; เงื่อนไขต้นทางไม่ผ่านหยุดแก้แผน.
2. ทำ bundle/proof shared reader และ V-03..06 ก่อนกราฟ เพื่อพิสูจน์ invariant.
3. เพิ่ม migration/preview/supervisor/internal demand และ V-02/07..10.
4. เพิ่ม controller/renderer/UI ตาม V-11..16 แล้ว browser→API→PG/worker tests.
5. full regression/build/OpenAPI/role/architecture/CI และ manual acceptance;
   reviewerตรวจงานจริง แก้ แล้วตรวจครั้งสุดท้ายก่อนเจ้าของสั่ง Git.

## ความเสี่ยงและสถานะอนุมัติ

Ordering ของต้นทางมีเพียงหลักฐานสั้น ต้องผ่าน V-01/02 ก่อนถือว่า usable;
ไม่พบ closed sample ไม่ใช้เป็น proof. LEGACY verify มีต้นทุน scan สูง
แต่ใช้งบเดิมและต้องรายงานไม่พร้อมตามจริง; ไม่สลับไป PREPARED เพื่อหลบต้นทุน.
V-17 ต้องวัดทั้งสอง mode และไม่ลด scope/สูตร/งบ F-11 ถ้าล้ม.
งบ/availability F-11 ที่เลื่อนไปชุด9ยังค้าง ไม่อ้างผ่านจาก F-12.
เจ้าของอนุมัติแผน/validation วันที่ 2026-10-12 ครอบ bundle/proof extension,
internal coalescer, preview schema, bounds และ rollout ที่ระบุไว้.
การอนุมัติไม่ใช่ผลผ่าน validation และไม่อนุญาตเปลี่ยนแผนที่อนุมัติเอง.
