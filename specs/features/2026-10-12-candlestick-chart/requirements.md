# F-12 — กราฟแท่งเทียนบนหน้าเว็บ — Requirements

## Amendment — ช่วงประวัติที่เลื่อนดูได้ (Approved 2026-10-14)

เจ้าของอนุมัติให้ `1m`–`1d` ดูย้อนหลังสามเดือนปฏิทิน และ `1w`/`1M`
ดูได้ทั้งหมดเท่าที่ Binance TH ให้ข้อมูล; `1M` คือรายเดือน ไม่ใช่ `1m` รายหนึ่งนาที.
Amendment นี้แทน RQ-10/RQ-32 ในส่วนขอบเขตที่ผู้ใช้ดูได้ และเพดานห้าปีสำหรับ
ประวัติ `1w`/`1M`; กฎ authorization, exact OHLCV, finality, retry และ bounded work ยังใช้เดิม.

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-37 | `1m`, `5m`, `15m`, `1h`, `4h`, `1d` เลื่อนดูย้อนหลังได้สามเดือนปฏิทินจากเวลา server ไม่ใช้ 90 วันคงที่หรือเวลาเครื่องผู้ใช้; ใช้ UTC ตาม schedule เดิม และรวมแท่งที่คร่อมขอบเริ่มช่วง | เจ้าของอนุมัติ 2026-10-14 |
| RQ-38 | `1w`/`1M` เลื่อนดูได้ถึงประวัติเก่าสุดที่ต้นทางมีให้สำหรับแต่ละคู่/TF โดยไม่ตัดที่ห้าปี; ไม่รับรองว่าทุกคู่มีอายุหรือข้อมูลเท่ากัน | เจ้าของอนุมัติ 2026-10-14 |
| RQ-39 | โหลดช่วงล่าสุดก่อน และโหลดช่วงก่อนหน้าเมื่อผู้ใช้เลื่อนใกล้ขอบซ้าย; ไม่โหลดทั้งสามเดือนของ 1m หรือทุกคู่/TF เข้าหน่วยความจำทันที และไม่บังคับให้รอ deep backfill ทั้งหมดก่อนวาด | RQ-10, recent-history-priority amendment |
| RQ-40 | รวมหน้าโดยใช้ source/pair/TF/open-time ไม่ซ้ำ ไม่หายบริเวณรอยต่อ; การเติมทางซ้ายต้องคงแท่งที่ผู้ใช้กำลังดู และต้องยกเลิก/กันผลเก่าเมื่อเปลี่ยน TF, คู่ หรือผู้ใช้ | RQ-18, RQ-31/35 |
| RQ-41 | แยกกรณีโหลดไม่เสร็จ, ช่องว่าง, ต้นทางล้มเหลว และถึงข้อมูลเก่าสุดที่พิสูจน์แล้ว; คำตอบว่างหรือ timeout เพียงครั้งเดียวไม่ใช่หลักฐานว่าถึงจุดเริ่มประวัติ | coverage/finality และ exchange-failure contracts เดิม |
| RQ-42 | ช่วงแสดงสามเดือนไม่ใช่คำสั่งลบข้อมูลที่เก็บอยู่เดิม. การขยายประวัติ weekly/monthly ต้องไม่เปลี่ยนสูตร/seed/period ของ indicator หรือแก้ข้อมูลเงิน/ออเดอร์ และห้าม aggregate native candles เอง | trading safety, RQ-30/34 |

สถานะ plan/validation สำหรับ amendment นี้ดูที่หัวข้อของแต่ละไฟล์แยกจากการอนุมัติ requirements.

การเติมประวัติช่วงล่าสุดก่อน: [amendment ที่อนุมัติ](recent-history-priority-amendment.md).

การกู้กราฟหลัง history error: ใช้ [amendment ที่อนุมัติ](chart-error-recovery-amendment.md)
สำหรับคำขอแท่งเทียนที่กำลังโหลดและปุ่มลองใหม่เฉพาะ error state.

สถานะ: **Approved** — เจ้าของอนุมัติแนวทางวันที่ 2026-10-13 ให้แสดงแท่งเทียนก่อน indicator ทั้งการเปิดหน้าครั้งแรกและเปลี่ยนคู่/TF; amendment ที่อนุมัติก่อนหน้ายังมีผลกับส่วนอื่น การอนุมัติ implementation ดู plan/validation
การเปลี่ยนแปลง MACD ด้านล่าง: **Approved** — เจ้าของยืนยันขอบเขตให้ลบทั้งระบบและอนุมัติ amendment เมื่อ 2026-10-13
การย้ายรายละเอียดแท่งเข้า chart ด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13
การลบแถบสถานะถาวรด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13
การลบ Indicator จาก UI ด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13
การลด controls และข้อความใต้กราฟด้านล่าง: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-14
การเพิ่มปุ่มรีเซ็ตกราฟภาษาไทย: **Approved** — เจ้าของยืนยันเมื่อ 2026-10-14
การลบตัวเลือกภาษาออกจากหน้า Chart: **Approved** — เจ้าของยืนยันเมื่อ 2026-10-14
การจัดหน้าแบบ Trading Workspace ด้านล่าง: **Approved** — เจ้าของอนุมัติ requirements เมื่อ 2026-10-14
การปรับสัดส่วนและความสูง workspace: **Approved** — เจ้าของสั่งแก้เมื่อ 2026-10-14
การย่อ market bar และลบ visible labels: **Approved** — เจ้าของสั่งแก้เมื่อ 2026-10-14
การจัดตำแหน่ง history tabs ตาม Admin Template: **Approved** — เจ้าของสั่งแก้เมื่อ 2026-10-14
โหมด Light/Dark จาก Admin Template: **Approved** — เจ้าของสั่งเพิ่มเมื่อ 2026-10-14
การเพิ่ม timeframe `1w` และ `1M` ทั้งระบบด้านล่าง: **Approved** — เจ้าของอนุมัติ requirements amendment เมื่อ 2026-10-14; รออนุมัติ plan/validation ก่อน implementation
วันที่: 2026-10-12
Branch: feature/f-12-candlestick-chart

## Amendment — native timeframe `1w` และ `1M` ทั้งระบบ (Approved 2026-10-14)

เจ้าของขอเพิ่ม `1w` และ `1M` เป็น timeframe จริงตลอดเส้นทางข้อมูล ไม่ใช่การรวมแท่งที่ frontend.
Binance TH ระบุ `1w` และ `1M` เป็น interval ที่รองรับโดยตรงทั้ง REST Kline และ WebSocket
Kline stream; ระบบจึงต้องขอข้อมูล native interval จาก venue ผ่าน adapter เดิม และห้ามสร้างสอง timeframe นี้
จากแท่งย่อยใน frontend หรือ API. `1M` ต้องคงตัวพิมพ์ใหญ่เพื่อไม่ให้สับสนกับ `1m`.

Amendment นี้แทนข้อจำกัด “6 timeframes” ใน RQ-2 และข้อกำหนด retention 365 วันแบบเดียวกันทุก
timeframe ใน RQ-10 เฉพาะส่วนที่ขัดกัน โดยข้อกำหนดด้าน authorization, exact values, finality,
ordering, consistency, bounded work, retry และ error handling เดิมยังมีผลทั้งหมด.

| รหัส | ข้อกำหนดเพิ่มเติม | ที่มา |
|---|---|---|
| RQ-29 | เพิ่ม `1w` และ `1M` ใน domain enum, REST request/response schema, OpenAPI/generated frontend type, database constraints/index-compatible values, backfill/coverage/gap/claim/storage/retention, live-candle subscription และตัวเลือก timeframe ของหน้า Chart โดยยังจำกัดคู่เทรดเดิม ระบบต้องแยก `1m` กับ `1M` แบบ case-sensitive ตลอดเส้นทาง | คำสั่งเจ้าของ 2026-10-14; Binance TH REST/WebSocket Kline intervals |
| RQ-30 | ใช้แท่ง `1w`/`1M` จาก native Binance TH Kline เท่านั้น ไม่ aggregate จาก timeframe ย่อยใน frontend, API หรือ worker. REST backfill และ live stream ของ timeframe เดียวกันต้องมี identity เดียวกันตาม source/pair/timeframe/open-time และผ่านกฎ duplicate/out-of-order/finality/recovery เดิม | คำสั่งเจ้าของ 2026-10-14; RQ-3/25/26/27 |
| RQ-31 | ขอบเขตเวลาใช้ UTC: `1w` เปิดวันจันทร์ 00:00:00 UTC และสิ้นสุดเมื่อเปิดสัปดาห์ถัดไป; `1M` เปิดวันที่ 1 เวลา 00:00:00 UTC และสิ้นสุดเมื่อเปิดเดือนถัดไป. การตรวจ alignment, `end_at`, slot ถัดไป, จำนวน slot, window, gap และ pagination ต้องใช้ calendar boundary นี้ ห้ามแทน `1M` ด้วย `timedelta` หรือจำนวนวินาที/วันคงที่ | database §2; semantics ของ calendar interval; คำตัดสินเจ้าของ 2026-10-14 |
| RQ-32 | คง logical retention ของ `1m`–`1d` ที่ 365 วัน. `1w` เก็บย้อนหลัง 5 ปีโดยจัด cutoff เข้าขอบสัปดาห์ และ `1M` เก็บย้อนหลัง 5 ปีโดยจัด cutoff เข้าขอบเดือน. Backfill ยังต้อง bounded ตามเพดาน venue/API และไม่รับรองว่าคู่ที่เพิ่งเปิดตลาดจะมีข้อมูลครบทั้งช่วง | คำแนะนำที่เจ้าของอนุมัติ 2026-10-14; F-09 bounded backfill |
| RQ-33 | schema migration ต้องยอมรับค่าใหม่โดยไม่เขียนข้อมูลแท่งเดิมใหม่และไม่ลด constraint เรื่อง timeframe/alignment/end-time. การ deploy ต้องรองรับลำดับ migration ก่อน process รุ่นใหม่เริ่มเขียน `1w`/`1M`; rollback ของ application ห้ามทำให้ข้อมูลใหม่ถูกตีความเป็น timeframe อื่น | database §3/4; architecture §4 |
| RQ-34 | indicator backend ที่รับ timeframe ร่วมกันต้องประมวลผล `1w`/`1M` ด้วยลำดับ calendar เดียวกับ candle. หากประวัติ 5 ปีหรืออายุคู่เทรดไม่พอสำหรับ warm-up ให้คืนสถานะ WARM_UP/ไม่มีค่าตามสัญญาเดิม ห้ามประมาณค่า เติมศูนย์ ลด period หรือดึงข้อมูลนอก retention มาแอบคำนวณ | F-11 RQ-3/5/8/9; RQ-7/8/17 |
| RQ-35 | API และ UI ต้องรักษา `1M` แบบ case-sensitive ใน URL/query/cache key/query key/serialization และ invalid input รวมถึง `1W`, `1mo` หรือ casing อื่นต้องถูกปฏิเสธตาม validation contract เดิม. การเปลี่ยน timeframe ต้องยกเลิก/กันผลคำขอเก่าตาม RQ-18 และไม่ทำให้ข้อมูล timeframe ก่อนหน้าทับชุดใหม่ | RQ-16/18; backend/frontend standards |
| RQ-36 | live-candle subscription ต้องสมัคร stream native `<symbol>@kline_1w` หรือ `<symbol>@kline_1M` ตาม timeframe ที่ใช้งาน รักษา bounded shared subscription/reconnect เดิม และกู้ช่องว่างผ่าน REST timeframe เดียวกันหลัง disconnect โดยไม่สร้างการเชื่อมต่อตลาดต่อผู้ใช้ | Binance TH Kline stream; architecture §1/3; RQ-25/27 |

การเพิ่ม timeframe ไม่เปลี่ยนสูตรราคา ปริมาณ เงิน ออเดอร์ balance/position/PnL, Paper/Live mode
หรือสิทธิ์ส่งออเดอร์ และ automated validation ห้ามส่ง Live order. ก่อน implementation ต้องมี
plan/validation amendment ที่แจกแจง migration, calendar-aware time operations, compatibility ของ API,
backfill/live recovery และ targeted regression สำหรับ timeframe เดิมกับ case-sensitive `1m`/`1M`.

## Amendment — จัดหน้าแบบ Trading Workspace (Approved 2026-10-14)

ใช้ภาพหน้าเทรด Binance ที่เจ้าของให้เป็น **ข้อมูลอ้างอิงเฉพาะการจัดพื้นที่** ของหน้าแรกหลังเข้าสู่ระบบ
ไม่ใช้เป็นข้อกำหนดให้คัดลอกตราสินค้า สี หรือความสามารถซื้อขายของ Binance. หน้า Chart ยังคงใช้
component, design token, interaction state และ responsive pattern จาก `references/admin-template/`
ตาม `specs/standards/frontend.md`; กราฟยังใช้พื้นสีขาวเป็นค่าเริ่มต้นตามข้อกำหนดที่อนุมัติแล้ว.

บนจอ desktop พื้นที่เนื้อหาของหน้าแรกแบ่งเป็น Trading Workspace ดังนี้:

1. แถบสรุปตลาดและตัวเลือกคู่เทรด/timeframe อยู่เหนือพื้นที่หลัก โดยใช้ข้อมูลตลาดที่ F-12 มีอยู่แล้ว
   และไม่สร้าง bid/ask, สถิติ 24 ชั่วโมง หรือยอดคงเหลือจำลองขึ้นเอง
2. กราฟแท่งเทียนเป็นพื้นที่หลักด้านซ้ายและใช้พฤติกรรม/ข้อมูลเดิมของ F-12 ทั้งหมด
3. ด้านขวามีพื้นที่เตรียม form ซื้อขายเพื่อกำหนด layout เท่านั้น. Input/select/tab และปุ่ม action
   ต้องแสดงเป็น disabled พร้อมข้อความชัดเจนว่ายังใช้งานไม่ได้; ห้ามส่งคำขอ, คำนวณจำนวนเงิน,
   แสดง balance จำลอง หรือเปลี่ยนสถานะ Paper/Live. การเปิดใช้งานจริงเป็นขอบเขต F-13–F-16/F-22.
4. ใต้กราฟมีพื้นที่ตารางประวัติ/รายการออเดอร์เพื่อกำหนด layout เท่านั้น. แสดงหัวตารางและ empty state
   ที่บอกว่ายังไม่มีข้อมูลจากระบบ ห้ามสร้างรายการซื้อขายจำลอง; ข้อมูลจริงเป็นขอบเขต F-15/F-16/F-28.
5. Account navigation เดิมยังเข้าถึงแต่ละ module แยกหน้าได้ และหน้า Chart ยังคงเป็นหน้าเริ่มต้น
   หลังเข้าสู่ระบบตาม plan ที่อนุมัติแล้ว.
6. บนจอแคบให้เรียง market summary, chart, form และ history ลงมาตามลำดับโดยไม่มี horizontal overflow;
   chart ต้องยังซูม เลื่อน ใช้ crosshair และรีเซ็ตได้ตามเดิม.

บนจอ desktop ให้ workspace สูงพอดีกับพื้นที่ใต้ account header โดยไม่สร้าง scrollbar ของ document.
พื้นที่ history ใต้กราฟต้องสูงกว่าพื้นที่ chart ตามสัดส่วนของภาพอ้างอิง ส่วน mobile คงการเรียงแนวตั้ง
และอนุญาตให้เลื่อนหน้าเพื่อรักษาขนาดกราฟและ controls ที่ใช้งานได้.
Market bar ไม่แสดงข้อความ `กราฟแท่งเทียน`, `คู่เทรด` และ `Timeframe`; dropdown ยังต้องมี accessible name
เดิมสำหรับ screen reader และลด padding/spacing ของแถบโดยไม่ลดขนาด control ของ Admin Template.
Tabs ของรายการซื้อขายต้องอยู่ชิดซ้ายในแถบหัวของ history โดยไม่ซ้อนพื้นที่ chart/แกนเวลา และใช้รูปแบบ
underline tab จาก `references/admin-template/src/components/ui/tabs/TabWithUnderline.tsx`.

หน้า account ต้องมีปุ่มสลับ Light/Dark ใน header ตาม ThemeToggleButton/ThemeContext ของ Admin Template.
ค่าเริ่มต้นเมื่อยังไม่เคยเลือกคือ Light และบันทึกค่าที่เลือกใน browser เพื่อใช้ในการเปิดหน้าครั้งถัดไป.
Sidebar, header, workspace, form controls, tabs, table และ chart ต้องใช้ theme เดียวกัน; การสลับ theme
ต้องไม่ล้างข้อมูล เปลี่ยน pair/TF/viewport หรือเรียก API เพิ่ม และปุ่มต้องมี accessible name บอกโหมดปลายทาง.

Amendment นี้เปลี่ยนเฉพาะ layout และ placeholder UI. ไม่เพิ่มหรือเปลี่ยน API, database, order domain,
balance/position/PnL, idempotency, exchange integration หรือ trading safety rule ใด ๆ. ก่อนเขียนโค้ดต้องมี
plan/validation amendment ที่ระบุ component ของ admin template ที่นำมาใช้ซ้ำและเกณฑ์ยืนยันว่า controls
ทั้งหมดในพื้นที่ซื้อขายยัง disabled และไม่มี network request สำหรับการส่งออเดอร์.

## Amendment — ลบตัวเลือกภาษาออกจากหน้า Chart (Approved 2026-10-14)

หน้า Chart ต้องไม่แสดง label หรือตัวเลือก **“ภาษา”**. ข้อความและวันเวลาของหน้า Chart ใช้ภาษาไทย
โดยไม่ให้ผู้ใช้สลับเป็นภาษาอังกฤษจากหน้านี้. คงตัวเลือกคู่เทรด, timeframe และปุ่ม `รีเซ็ตกราฟ`;
ไม่เปลี่ยนข้อมูลกราฟ, API, backend หรือการตั้งค่าภาษาใน module อื่น.

## Amendment — ปุ่มรีเซ็ตกราฟภาษาไทย (Approved 2026-10-14)

หน้า Chart ต้องมีปุ่มข้อความ **“รีเซ็ตกราฟ”** เป็นภาษาไทย เพื่อคืน viewport ของกราฟไปยัง
ช่วงเริ่มต้นที่แสดงแท่งล่าสุดตามค่าเริ่มต้นของหน้า ปุ่มนี้รีเซ็ตเฉพาะตำแหน่งและระดับการซูมของกราฟ;
ไม่เปลี่ยนคู่เทรด, timeframe หรือภาษา ไม่ล้างข้อมูล ไม่เรียก refresh/retry/history API
และไม่เปลี่ยนสถานะหรือข้อมูล backend. ปุ่มต้องใช้งานด้วย keyboard และมี accessible name เดียวกับข้อความ.

## Amendment — ลด controls และข้อความใต้กราฟ (Approved 2026-10-14)

ลบข้อความอธิบายสเกลและปุ่มแท่งก่อนหน้า/ถัดไป รวมทั้งปุ่มกลับช่วงล่าสุด,
เพิ่มประวัติก่อนหน้า, ลองใหม่ และขอ refresh ประวัติออกจากหน้า Chart. คงตัวเลือกคู่เทรด,
timeframe และภาษา พร้อม interaction ซูม/เลื่อน/crosshair ของกราฟและการโหลดอัตโนมัติ.
Error ที่ต้องให้ผู้ใช้ทราบยังแสดงได้; ไม่เปลี่ยน API หรือข้อมูล backend.

## Amendment — Candle-only chart reads (Approved 2026-10-14)

[Continuity amendment](candle-continuity-amendment.md) ได้รับอนุมัติแล้ว: รักษา native
stream observations ระหว่างรอ REST ด้วย buffer จำกัด 120 แท่ง/series และ candle-page overlay;
ห้ามสร้างแท่งที่ไม่เคยได้รับข้อมูลจริง และไม่เปลี่ยน canonical indicator input.

เจ้าของอนุมัติ [ข้อกำหนด/แผน/validation](candle-only-chart-amendment.md) ให้หน้า Chart
ใช้เฉพาะ candle history/pagination และ live; ไม่เรียก indicator-backed history/proof.
ข้อกำหนด bundle/proof เดิมไม่ใช้กับหน้ากราฟที่ไม่มี indicator; backend F-11 ยังคงเดิม.

## Amendment — ลบ Indicator จาก UI (Approved 2026-10-13)

หน้า Chart ไม่แสดงตัวเลือก ชื่อ ค่า เส้น หรือ pane ของ EMA20/50/200, RSI14 และ ATR14.
คงเฉพาะแท่งเทียน เวลา/finality/OHLCV และการเลื่อน/ซูม/เลือกแท่ง. ไม่ลบหรือเปลี่ยน
backend/API ของ F-11 เพราะยังเป็นสัญญาข้อมูลของระบบส่วนอื่น และไม่เปลี่ยนสูตรหรือข้อมูลเดิม.

## Amendment — ลบแถบสถานะถาวร (Approved 2026-10-13)

ไม่แสดง block ข้อความสถานะประวัติ, Indicator, ช่องว่างข้อมูล, ท่อแท่งเทียนสด,
เวลาอ้างอิง และเวลาที่ server ตรวจเหนือกราฟ. ยังคงแสดง error/alert ที่ต้องให้ผู้ใช้
ดำเนินการ, สถานะ finality ของแท่งใน chart และสถานะ loading ผ่านการ disable controls
ตามเดิม; ไม่เปลี่ยนสัญญาข้อมูลหรือการตรวจ consistency.

## Amendment — ย้ายรายละเอียดแท่งเข้า chart (Approved 2026-10-13)

แสดงวันเวลา สถานะ finality และค่า O/H/L/C/V ของแท่งที่เลือกเป็นข้อความ exact
ภายในกรอบกราฟแบบ TradingView. ค่า volume แสดงหน่วยเหรียญฐานและไม่สร้าง Volume pane.
เมื่อไม่ได้ชี้แท่งให้แสดงแท่งล่าสุด; เมื่อชี้หรือใช้ปุ่มก่อนหน้า/ถัดไปให้ข้อมูลบนกราฟ
เปลี่ยนตามแท่งนั้น. ลบชุดวันเวลาและ OHLCV ที่ซ้ำใต้กราฟ แต่คงปุ่ม keyboard navigation,
รายละเอียด indicator, สถานะข้อมูล และ accessibility label เดิม.

## Amendment — ลบ MACD จากกราฟ (Approved 2026-10-13)

ตาม F-11 amendment เรื่องลบ MACD ให้แทนรายการ indicator ของ F-12
ด้วย EMA20/50/200, RSI14 และ ATR14 เท่านั้น. ลบตัวเลือก MACD ทั้งสาม,
pane/series และค่ารายละเอียด MACD ออกจากกราฟ; ไม่มีชื่อหรือค่าของ MACD
ในหน้าจอหรือโค้ด frontend ของ F-12. EMA, RSI และ ATR ยังคงเลือกแสดงได้
และใช้ค่าจาก backend ตามเงื่อนไข exact/proof/finality เดิม. แผนและ validation
ต้องปรับเกณฑ์ UI/API/E2E ให้ตรงกับชุดใหม่นี้ก่อนแก้โค้ด.

## ทำไมต้องมี

ผู้ใช้ต้องดูประวัติราคาและ indicator บนกราฟใน TiewTrade ตาม R-14
โดยเห็นข้อมูลชุดเดียวกับที่ backend ใช้ ไม่คำนวณสูตรซ้ำในเบราว์เซอร์
F-09 มี OHLCV/coverage และ F-10 มีราคาล่าสุดพร้อมสถานะแล้ว;
F-11 เปิดสัญญาผล indicator เพื่อให้งานกราฟใช้ต่อได้
สถานะการพัฒนาและข้อจำกัดการตรวจรับของแต่ละงานดูจาก [roadmap](../../roadmap.md)

R-14 รวมจุดเข้า/ออกด้วย แต่ยังไม่มีสัญญาข้อมูลการจับคู่ออเดอร์สำหรับกราฟ
ส่วนราคาล่าสุด F-10 ไม่ใช่แท่งเทียนสดและไม่ใช่หลักฐานว่าแท่งปิดแล้ว
เจ้าของตอบวันที่ 2026-10-12 ให้รวมแท่งเทียนสดใน F-12
และเลื่อนจุดเข้า/ออกจริงจนมีข้อมูลออเดอร์ โดยติดตามใน roadmap
บันทึกคำตัดสินและเรื่องที่ยังต้องตัดสินด้านล่าง

## ขอบเขต

### ฐานขอบเขตจาก spec เดิม

- กราฟแท่งเทียน Spot ของ Binance TH ในเว็บเดิม ใช้ข้อมูลผ่าน API ของ TiewTrade
- คู่ตั้งต้น BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT และ timeframe
  1m, 5m, 15m, 1h, 4h, 1d ตาม mission/NC-09
- แสดง EMA20/50/200, RSI14, MACD12/26/9 และ ATR14 จาก F-11
- รวมแท่งเทียนสดระหว่างกำลังก่อตัวตามคำตอบเจ้าของ 2026-10-12 (NC-39)
- อ่านประวัติภายในขอบเขต 365 วันของ F-09 พร้อมแสดงข้อมูลขาด/รอข้อมูลตามจริง
- ใช้ layout/component และระบบแปลเดิม; วางการรองรับไทย/อังกฤษตั้งแต่ F-12 ตาม roadmap F-30

### ขอบเขต UI ที่เสนอเพื่ออนุมัติในฉบับนี้

- มีหน้ากราฟในพื้นที่ที่ต้องเข้าสู่ระบบ เลือกคู่และ timeframe ได้
- ซูม/เลื่อนช่วงเวลา กลับมาช่วงล่าสุด และอ่านเวลา/OHLCV ของแท่งที่ชี้ได้
- ไม่วาดแท่ง volume บนกราฟ แต่ยังอ่านค่า volume แบบข้อความ exact ในรายละเอียดแท่งเทียนได้;
  เปิด/ปิด indicator ที่รองรับได้ โดย EMA อยู่บนกราฟราคา
  ส่วน RSI, MACD และ ATR แสดงในพื้นที่ที่มีสเกลเหมาะกับหน่วยของตัวเอง
- ขอประวัติเพิ่มและขอ refresh ผ่านทางเดิมของ F-09 พร้อมสถานะงาน
- แสดงราคาล่าสุดและสถานะจาก F-10 แยกจากเวลา/สถานะของแท่งเทียน
- อัปเดตแท่งที่ยังเปิดและรับแท่งถัดไปโดยไม่ให้ผู้ใช้กดโหลดใหม่ทุกแท่ง
  โดยแยก finality และความพร้อมของข้อมูลสดจากข้อมูลประวัติ
- เลื่อนจุดเข้า/ออกจริงจนมีข้อมูลออเดอร์ตามคำตอบเจ้าของ (NC-40)
  ติดตามงานเชื่อมและด่านตรวจรับใน roadmap; รอบนี้ไม่สร้าง marker จำลองใน UI

รายการ UI ข้างต้นเป็นรายละเอียดของ requirements ฉบับที่เจ้าของอนุญาตให้ใช้ทำแผน
ตำแหน่งหน้า ค่าเลือกเริ่มต้น จำนวนแท่งที่เห็น และรายละเอียดการจัดวางให้เสนอใน plan
หลัง requirements ได้รับอนุมัติ โดยไม่เพิ่มความสามารถนอกขอบเขตนี้

### ไม่รวม

การส่ง/แก้/ยกเลิกออเดอร์จากกราฟ, TP/SL, การคำนวณ PnL/position,
buy/sell signal หรือการตีความ indicator เป็นกฎซื้อขาย,
การปรับสูตร/พารามิเตอร์ indicator, drawing tools และ alert จากระดับราคาบนกราฟ
ไม่เพิ่ม Futures, ตลาดใหม่, รายการเหรียญหรือหน้าจอ admin ของ F-37
ไม่เปิด Live หรือเปลี่ยน MANUAL/BOT จากการเปิดหน้ากราฟ
ไม่เปลี่ยนสูตร seed finality retention หรืองบทรัพยากรที่อนุมัติแล้วของ F-09/F-10/F-11
การรับแท่งสดเป็นสัญญาใหม่ของ F-12 ไม่ถือว่า F-10 เดิมมี candle stream แล้ว
ถ้าแผนจำเป็นต้องแก้ข้อกำหนด/แผนที่อนุมัติแล้วของงานเดิม ต้องเสนอ amendment
และได้รับอนุมัติก่อนแก้โค้ดตาม AGENTS.md

## ข้อกำหนด

### ภาพกราฟแบบ TradingView — คำสั่งเจ้าของ 2026-10-13

หน้ากราฟแสดงพื้นที่ plot สีขาวเป็นค่าเริ่มต้นตามคำสั่งเจ้าของล่าสุด กริด/แกนราคาแบบ TradingView พร้อมชื่อคู่/ตลาด/timeframe
และ OHLC ของแท่งที่เลือกไว้บนกราฟ โดยค่าข้อความยัง exact และข้อมูลมาจาก API เดิม.
แสดงเส้นและป้ายราคาของแท่งล่าสุดบนแกนเป็นสเกลภาพตาม NC-41 พร้อมคำอธิบายว่า
ค่าภาพเป็นค่าประมาณ; สถานะข้อมูล/ความสดและรายละเอียด OHLCV แบบข้อความยังต้องอ่านได้.
คง theme ของ admin-template สำหรับโครงหน้าและ controls; สีพื้นกราฟเริ่มต้นเป็นสีขาว.
ภาพอ้างอิงไม่อนุมัติราคา bid/ask, ปุ่มส่งออเดอร์ หรือการเปลี่ยนคู่/TF ตั้งต้น.

### Amendment: แสดงแท่งเทียนก่อน indicator — อนุมัติ 2026-10-13

ทั้งเมื่อเปิดหน้าครั้งแรกและเปลี่ยนคู่/timeframe ให้เริ่มอ่านประวัติแท่งเทียนแบบ bounded
ทันทีโดยไม่รอการคำนวณ indicator. แสดงข้อมูลนี้พร้อม coverage/gaps, เวลาอ้างอิง,
finality และสถานะว่า indicator ยังโหลดอยู่; ข้อความค่าต่าง ๆ คง exact.
เมื่อ coherent bundle พร้อมให้แทนประวัติชั่วคราวทั้งชุดด้วย candles ของ bundle นั้น
และแสดง indicator เฉพาะเมื่อผ่าน RQ-7. ห้ามนำ indicator จาก bundle ไปซ้อนบน
ประวัติชั่วคราวจากคนละ snapshot. ข้อนี้ขยาย RQ-3/5/7/10/18 โดยกฎความสอดคล้องเดิมยังใช้
เมื่อแสดง indicator ร่วมกับ candles. หากคำขอชั่วคราวล้ม/ไม่มีข้อมูลให้แสดงสถานะตามจริง;
การอ่านไม่ทำให้ POST backfill อัตโนมัติ. คำตอบช้าที่มาหลัง bundle ห้ามย้อนกลับไปแสดงข้อมูลชั่วคราว.

คอลัมน์ที่มาระบุข้อกำหนดเดิมกับรายละเอียดที่เสนอใน F-12 ฉบับนี้
การอนุญาตเข้าสู่ขั้นแผนไม่ใช่การอนุมัติวิธี implementation หรือตัวเลขเพดานในแผน

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | แสดงกราฟแท่งเทียนในเว็บ TiewTrade สำหรับผู้ใช้ที่เข้าสู่ระบบ ใช้ API ของระบบ ไม่ให้เบราว์เซอร์เรียกตลาดหรือใช้ API key/secret ของผู้ใช้เพื่อโหลดกราฟ | mission C-8/R-14, architecture §1/3, security §1 |
| RQ-2 | เลือกได้เฉพาะ 5 คู่และ 6 timeframes ตามขอบเขต; การดูกราฟไม่เพิ่มคู่ในรายการ ไม่เพิ่ม subscription ตลาดตาม input ที่ไม่รองรับ | mission §6/NC-09, F-09 RQ-2, F-10 RQ-3 |
| RQ-3 | วาด OHLC จากข้อมูล OHLCV ของ F-09 ตาม source/pair/timeframe/open-time เรียงเวลาและกันซ้ำ โดยไม่วาดแท่ง volume บนกราฟ; ห้ามประกอบแท่งจากราคาล่าสุด F-10 หรือสร้างแท่ง/volume ศูนย์แทนช่องว่าง | F-09 RQ-5/6/10, F-11 RQ-3; เจ้าของขอเอาแท่ง volume ออกจากกราฟวันที่ 2026-10-13 |
| RQ-4 | แสดงคู่ หน่วยราคา timeframe และเวลาอ้างอิงให้เห็นชัด; ตัวตนแท่งใช้ UTC ตาม backend เสนอแสดงเวลา Asia/Bangkok ตาม component เดิม โดยระบุ timezone ให้ผู้ใช้ทราบ | database §2, frontend §2/6; ข้อเสนอ UI ตาม MarketTime เดิม |
| RQ-5 | รองรับการซูม เลื่อนเวลา กลับช่วงล่าสุด และการอ่านเวลา/OHLCV ของแท่งที่ชี้; ค่า volume ยังคงแสดงเป็นข้อความ exact ในรายละเอียดแท่งเทียนโดยไม่มี volume pane และค่าที่ไม่มีข้อมูลต้องแสดงสถานะ ไม่แทนด้วยตัวเลขที่สร้างขึ้น | mission C-8/R-14; ข้อเสนอ UI ฉบับนี้; เจ้าของขอเอาแท่ง volume ออกจากกราฟวันที่ 2026-10-13 |
| RQ-6 | แสดง indicator ชุดเริ่มต้นจาก F-11 เท่านั้น เปิด/ปิดการแสดงแต่ละชุดได้ ไม่คำนวณสูตร seed warm-up หรือสัญญาณซื้อขายที่ frontend | tech-stack §3, frontend §3, F-11 RQ-1/5/10; ข้อเสนอ UI ฉบับนี้ |
| RQ-7 | จับคู่จุด indicator กับ source/pair/timeframe/open-time ที่ตรงกัน พร้อมรักษา dataset/formula revision และ as_of ของชุดอ่าน; ก่อนแสดงร่วมกับ OHLC ต้องพิสูจน์ความสอดคล้องของข้อมูลที่ใช้คำนวณ รวม seed/dependencies ไม่ใช้เวลาแท่งที่ตรงกันเพียงอย่างเดียว เมื่อข้อมูลที่เกี่ยวข้องเปลี่ยนหรือพิสูจน์ไม่ได้ ให้ระงับเส้น/พื้นที่ indicator และค่าของชุดนั้นใน tooltip พร้อมแสดงสถานะรอข้อมูลที่สอดคล้องกัน กลับมาแสดงได้เมื่ออ่านและตรวจชุดที่สอดคล้องกันสำเร็จเท่านั้น คำเตือนไม่อนุญาตให้วาด overlay ที่ตรวจไม่ได้ต่อไป; แผนต้องระบุวิธีพิสูจน์ โดยแท่งสดที่อยู่นอกขอบคำนวณและไม่เปลี่ยน dependencies เดิมไม่ทำให้ผลประวัติที่ยังพิสูจน์ได้ถูกระงับ | tech-stack §3, F-11 RQ-4/5/14; แก้ตาม review ที่เจ้าของสั่ง 2026-10-12 |
| RQ-8 | แสดง WARM_UP, GAP และ REFRESH_REQUIRED ตาม F-11 แยกจากค่า; ไม่แทนด้วยศูนย์ ไม่ forward-fill และไม่ลากเส้นเชื่อมผ่านช่วงที่ไม่มีค่าจนดูเหมือนต่อเนื่อง | F-11 RQ-8/9, NC-31 |
| RQ-9 | คง OPEN/UNCONFIRMED/CLOSED และหลักฐานความพร้อมของ backend; ห้าม frontend ประกาศ CLOSED เพราะนาฬิกาผ่าน end_at หรือเพราะอ่านค่า indicator ได้ ต้องสื่อข้อจำกัด UNCONFIRMED ให้ผู้ใช้เห็น | F-09 RQ-6, F-11 RQ-9/NC-31 |
| RQ-10 | โหลด/แบ่งหน้าประวัติแบบมีขอบเขตตามสัญญา F-09/F-11 ภายใน logical retention 365 วัน ไม่โหลดทุกคู่ทุก timeframe หรือทั้งช่วงเก็บทันที; แสดง coverage/gaps และไม่รับรองว่ามีข้อมูลครบ 365 วัน | F-09 RQ-7..12, F-11 RQ-15 |
| RQ-11 | การอ่าน indicator หลายหน้าต้องคงชุดเดียวกัน เมื่อได้ 409 INDICATOR_DATASET_CHANGED ให้ทิ้งหน้าที่สะสมของรอบนั้นและเริ่มใหม่ตามงบเดิม ไม่ต่อหน้าจากคนละ revision; ข้อมูลจากรอบหรือคู่/timeframe เก่าต้องไม่เขียนทับรอบปัจจุบัน | F-11 RQ-14, plan token/error contract, tech-stack §3 |
| RQ-12 | มีทางให้ผู้ใช้ขอ backfill/refresh ผ่าน F-09 ด้วย session/CSRF เดิม; การอ่าน indicator หรือ required=true ไม่ทำให้ส่ง POST เอง เว้นแต่นโยบายอัตโนมัติได้รับอนุมัติเพิ่มโดยชัดเจน | F-11 plan: Flow refresh, F-09 RQ-9..12; ข้อเสนอ UI ฉบับนี้ |
| RQ-13 | refresh ใช้รอบจำกัดตาม F-11 plan: POST target หนึ่งครั้ง, ตรวจ F-09 ทุก 10 วินาทีสูงสุด 6 ครั้ง/60 วินาทีเมื่อรับ 202 แล้วอ่าน indicator ใหม่จากหน้าแรก; POST คืน 200 ก็ให้อ่าน indicator ใหม่ตาม flow เดิม 202/COMPLETE ไม่รับรองว่าพร้อมคำนวณ ถ้า GET indicator คืน 503 INDICATOR_DATA_NOT_READY ให้แสดงรอผลชุดใหม่และเข้าสู่นโยบาย readiness polling ของ RQ-16 โดยไม่ POST ซ้ำ; ไม่วน POST จาก more_required หรือ REFRESH_REQUIRED เอง และหยุดรอบ F-09 เมื่อ failure/หมดเวลา/session หมดอายุ | F-11 plan: Flow refresh, performance-plan-v2 Flow API และหน้าแรก/cold miss |
| RQ-14 | แสดงราคาล่าสุดจาก F-10 พร้อมเวลาซื้อขาย เวลา snapshot และสถานะท่อส่งเดิม แยกจาก OHLC/indicator; ราคา READY ณ snapshot ไม่รับรองว่าแท่งหรือ indicator ล่าสุดพร้อม และไม่ใช่สิทธิ์ส่งออเดอร์ | F-10 RQ-5/6, NC-26/27, frontend §4 |
| RQ-15 | loading, empty, coverage ไม่ครบ, รอ refresh, ข้อมูลใช้ไม่ได้ และข้อผิดพลาดต้องแสดงแยกกัน; ข้อมูลที่ค้างไว้ต้องมีเวลา/สถานะชัด ไม่แสดงเหมือนเป็นผลล่าสุด หลังต่อกลับต้องใช้ snapshot ใหม่ตาม F-10 | frontend §4, F-09 RQ-11, F-10 RQ-12 |
| RQ-16 | รักษา error/retry contract ของ F-11: 409 restart อัตโนมัติสูงสุดหนึ่งครั้งต่อ logical read โดยทิ้งหน้าที่สะสม; 422 numeric failure และ 429/504/503 รหัสอื่นไม่ retry อัตโนมัติ ข้อยกเว้นของ F-12 คือ GET หน้าแรกที่ได้รับ 503 INDICATOR_DATA_NOT_READY หรือ INDICATOR_BUSY ให้รอตามนโยบาย bounded ด้านล่าง โดย INDICATOR_BUSY ต้องเคารพ Retry-After และนับในงบ logical read เดิม ไม่เพิ่ม retry ภายใน API/builder ไม่สั่งคำนวณซ้ำ และไม่ใช้ผลเก่าที่พิสูจน์ไม่ได้มาแทนผลที่ยังไม่พร้อม | F-11 plan: API และเพดานงาน; performance-plan-v2 Flow API/Error/retry contract; เจ้าของรายงาน intermittent blank chart วันที่ 2026-10-13 |
| RQ-17 | เก็บราคาปริมาณและ indicator จาก API เป็นข้อความ exact สำหรับการอ่านค่า; ไม่มีการคำนวณเงินที่ frontend อนุญาตแปลงเป็น Number เฉพาะขอบตัววาดกราฟตาม NC-41 ไม่ใช้ค่าที่แปลงแล้วคำนวณเงิน/indicator/signal/ออเดอร์ tooltip ใช้ค่า exact ต้นฉบับ และค่าที่วาดไม่ได้ต้องแสดงข้อจำกัด | เจ้าของตอบ NC-41 วันที่ 2026-10-12, AGENTS กฎ6, frontend §3, F-11 RQ-10, MarketValue เดิม |
| RQ-18 | ใช้ TanStack Query จัดการข้อมูล server; state หน้าจอเก็บเฉพาะตัวเลือก/ช่วงที่ดู การเปลี่ยนคู่/timeframe ออกจากหน้า หรือหมด session ต้องยกเลิกรอบอ่าน/refresh ที่เกี่ยวข้องและกันคำตอบที่มาช้า | frontend §3, tech-stack §3, F-11 disconnect contract; ข้อเสนอ lifecycle UI |
| RQ-19 | การรับข้อมูล/refresh/poll อัตโนมัติไม่ต่ออายุ session; เมื่อถูกเพิกถอนหรือหมดอายุให้หยุดงานและใช้ flow auth เดิม ไม่คงข้อมูลผู้ใช้เก่าข้าม session หากภายหลังมีจุดเข้า/ออก | F-05 routing policy, F-10 RQ-11, F-11 RQ-11, security §1 |
| RQ-20 | ใช้ layout, component และ theme เดิม หน้ากราฟปรับขนาดตามพื้นที่ได้ ตัวควบคุมมี label ใช้ keyboard ได้ และเวลา/OHLCV/สถานะอ่านเป็นข้อความได้ ไม่อาศัยสีอย่างเดียว | frontend §1/2; ข้อเสนอ UI ฉบับนี้ |
| RQ-21 | ข้อความใหม่ผ่าน i18next และมีไทย/อังกฤษ; ตัวเลข/วันเวลาจัดรูปผ่าน component กลางโดยรักษาค่า exact ศัพท์เทรดคงอังกฤษ ไม่ขยาย F-12 เป็นการแปลหน้าจอเดิมทั้งหมดของ F-30 | mission R-20, roadmap F-30, frontend §2/6 |
| RQ-22 | ใช้ TradingView Lightweight Charts ตาม tech-stack และแสดงเครดิตตามสัญญาอนุญาต; แผนต้องตรวจเอกสารทางการของรุ่นที่จะใช้ก่อนกำหนด dependency/API/วิธีแสดงเครดิต ไม่ยก chart dependency ของ template มาแทนเอง | tech-stack §3 |
| RQ-23 | การเปิดกราฟไม่เปลี่ยน mode/trading type ไม่เปิด Live และไม่ทำให้มีออเดอร์; ถ้าแสดงบริบทบัญชีให้คง Paper/Live ตามจริง ไม่สร้างปุ่มเปิด Live หรือข้อมูลบัญชีจำลองเพื่อให้หน้ากราฟดูครบ | mission §4/5, trading-safety §1, F-08 scope |
| RQ-24 | เลื่อนจุดเข้า/ออกจริงจนมีข้อมูลออเดอร์ ติดตามใน roadmap โดยไม่สร้าง marker จาก indicator หรือราคาตลาดแทนการจับคู่จริง; งานเชื่อมภายหลังต้องมี spec นิยาม entry/exit, filled/partial fill, เวลา/ราคา และการแยก Paper/Live/ผู้ใช้ ไม่ถือว่ารอบกราฟนี้ตรวจรับ marker แล้ว | เจ้าของตอบ NC-40 วันที่ 2026-10-12, roadmap F-12/R-14, trading-safety §1/5/12 |
| RQ-25 | รับแท่งเทียนสดระหว่างกำลังก่อตัวผ่านสัญญา venue และ market-data ร่วมกัน แล้วส่งผ่าน API ของ TiewTrade; ไม่ให้ frontend ประกอบ OHLCV จากราคาล่าสุด F-10 และไม่สร้างการเชื่อมต่อตลาดต่อผู้ใช้ | เจ้าของตอบ NC-39 วันที่ 2026-10-12, architecture §1/3, F-10 RQ-2 |
| RQ-26 | การรวมประวัติกับข้อมูลสดต้องกัน duplicate/out-of-order และ response เก่าทับแท่งใหม่ตามตัวตนแท่งเดิม แผนต้องพิสูจน์ semantics ของต้นทางก่อนเลือก ordering/finality; ไม่มีหลักฐานว่า CLOSED ให้คง OPEN/UNCONFIRMED ตามสัญญาที่ได้รับอนุมัติ ไม่อนุมานการปิดจากนาฬิกาหรือการเริ่มแท่งถัดไป | F-09 RQ-5/6, F-11 NC-31, tech-stack §3; ข้อเสนอสำหรับแท่งสด |
| RQ-27 | แสดงความไม่พร้อมของท่อแท่งสดแยกจากราคาสด F-10 และ indicator; เมื่อหลุด/ต่อกลับต้องกู้ snapshot/ช่วงขาดตาม F-09 และตรวจความสอดคล้องก่อนแสดงว่าข้อมูลสดพร้อม แผนต้องกำหนด freshness/latency/recovery bounds จากสัญญาต้นทางที่ตรวจแล้ว ไม่ยืมเกณฑ์ราคา 10 วินาทีมาเป็นเกณฑ์แท่งโดยอัตโนมัติ | frontend §4, F-09 RQ-10/11, F-10 RQ-5/8/12; ข้อเสนอสำหรับแท่งสด |
| RQ-28 | เสนอให้ indicator ยึดเกณฑ์ F-11 เดิม: แท่งที่ยังเปิดไม่เพิ่มเข้า seed/state และไม่แสดง indicator intrabar ที่ frontend คำนวณเอง; เมื่อ backend มีข้อมูลแท่งที่เข้าเกณฑ์ F-11 ให้ขอผลใหม่อัตโนมัติแบบ bounded และถ้าได้ 503 INDICATOR_DATA_NOT_READY ให้รอตาม RQ-16 กลับมาแสดงผลเมื่อผ่าน RQ-7 เท่านั้น การอัปเดต OHLC อย่างเดียวหรือการเริ่มแท่งถัดไปไม่รับรองว่ามี prepared result พร้อมแล้ว; cadence และเพดานตามนโยบายด้านล่างต้องระบุใน plan/validation เพื่ออนุมัติก่อน implementation | F-11 RQ-3/5/9/14, NC-31; ข้อเสนอการใช้ indicator คู่แท่งสด |

### นโยบาย readiness polling ที่เสนอใน RQ-16/28

F-11 อนุญาตให้งานผู้ใช้ผลกำหนดนโยบายรอ prepared data ของตัวเอง
ข้อเสนอนี้เป็นนโยบายของ frontend F-12 สำหรับการเปิดกราฟ การอ่านหลัง refresh
และการขอผลใหม่หลังข้อมูลแท่งเข้าเกณฑ์ ไม่เปลี่ยนสัญญา retry ของ API/builder

- เริ่มรอบรอเมื่อ GET หน้าแรกคืน `503 INDICATOR_DATA_NOT_READY` หรือ `503 INDICATOR_BUSY`
  แสดงสถานะรอผล และอ่านหน้าแรกใหม่เมื่อถึงรอบตรวจ ไม่อ่านต่อด้วย cursor เก่า
- มีได้หนึ่งรอบรอต่อ source/pair/timeframe ที่หน้าจอกำลังใช้ และไม่ส่ง GET ซ้อนกัน
  รวมเหตุการณ์ข้อมูลที่เข้ามาระหว่างรอไว้ในรอบเดิม ไม่เริ่มรอบใหม่ทุก event
- กำหนดระยะห่างขั้นต่ำ จำนวนคำขอรวมสูงสุด และเวลารวมสูงสุดที่แน่นอนใน
  plan/validation ก่อนอนุมัติ โดยเคารพ `Retry-After` และ admission เดิม
  การได้รับ INDICATOR_DATA_NOT_READY/INDICATOR_BUSY ซ้ำหรือ event ใหม่ไม่รีเซ็ตจำนวนคำขอ/เวลาที่ใช้ไป
  การ restart จาก 409 ยังใช้งบหนึ่งครั้งต่อ logical read เดิม ไม่เพิ่มงบต่อ poll
- GET ที่รอไม่ทำให้ส่ง POST F-09, reset/retry builder หรือวน refresh จาก
  `more_required`/`REFRESH_REQUIRED`; หากอ่านสำเร็จแต่ยังต้อง refresh
  ให้จบรอบ readiness และแสดงสถานะตาม RQ-8/12/13 ไม่วนรอเพื่อบังคับให้มีค่า
- เมื่อได้ผลสำเร็จและตรวจความสอดคล้องตาม RQ-7 ผ่านแล้วจึงเผยแพร่และจบรอบ;
  หากระหว่างจับคู่พบข้อมูลเปลี่ยน ต้องคงการระงับและใช้งบของรอบเดิม
  ไม่สร้างวงจรอ่านใหม่ไม่จำกัด
- เมื่อหมดงบ หรือพบ error อื่นตาม RQ-16 ให้หยุดและแสดงสถานะ/ทางลองใหม่
  การมาของ event ถัดไปเพียงอย่างเดียวไม่เปิดรอบรอที่หมดงบขึ้นใหม่;
  ผู้ใช้เริ่มรอบใหม่ได้ภายใต้ข้อจำกัดเดิม การเปลี่ยนคู่/timeframe ออกจากหน้า
  หรือ session หมดอายุยกเลิกรอบเดิมตาม RQ-18/19

นโยบาย consumer นี้เป็นฐานของขั้นแผนตามคำสั่งเจ้าของ
ตัวเลขเพดานและการเปิด polling ยังต้องผ่านการอนุมัติ plan/validation ก่อน implementation

## กฎความปลอดภัยที่เกี่ยวข้อง

- `trading-safety.md` §1: Live ไม่เปิดเอง ข้อมูลเกี่ยวกับการเทรดต้องแยก Paper/Live
- §2 และ `security.md` §4: ไม่อ่านหรือเปิดเผย API secret/key ในกราฟ log หรือ error
- §5: หากมีจุดของ Live ต้องใช้ข้อมูลการเทรดที่ยืนยันตามระบบบัญชี ไม่อ้างว่า
  "ส่งคำสั่งแล้ว" คือ "จับคู่แล้ว"; NC-40 ปิดการเลือกขอบเขตแล้วโดยเลื่อนจุดจริง
  นิยาม event และการเชื่อมข้อมูลต้องกำหนดใน spec งานเชื่อมภายหลังตาม RQ-24
- §6/7: บอกเมื่อข้อมูล/การเชื่อมต่อไม่พร้อม รักษาการกู้คืนและ retry bounds เดิม
- §12: ความพร้อมราคากับความพร้อมข้อมูลบัญชีเป็นคนละเรื่อง
  ห้ามใช้สถานะราคาสดรับรองว่าประวัติการเทรดกระทบยอดแล้ว
- `AGENTS.md` กฎ6 และ `frontend.md` §3: ไม่คำนวณเงิน/indicator ที่หน้าบ้าน
  NC-41 อนุญาตเฉพาะขอบตัววาดภาพ ไม่ใช่การอนุญาตใช้ float ในตรรกะโดเมน

## ของเดิมที่พบสำหรับแผนหลังอนุมัติ

- สัญญา F-09: `specs/features/2026-10-07-market-data/{requirements,plan}.md`
  และ API `/market-data/candles`, `/market-data/candles/requests`
- สัญญา F-11: `specs/features/2026-10-10-backend-indicators/{requirements,plan}.md`
  และ amendments ใน `performance-plan-v2.md`; API/schema ใน
  `backend/src/tiewtrade/services/api/indicator_routes.py`
- F-10: `frontend/src/{useRealtimePrices,realtimePrices}.ts`,
  `frontend/src/RealtimePricePanel.tsx` และ `realtimePriceMessages.ts`
- การแสดงค่ากับเวลา: `frontend/src/components/MarketValue.tsx`
- UI/auth: `frontend/src/layout/`, `frontend/src/components/ui/`,
  `frontend/src/AccountSession.tsx`, `frontend/src/api.ts`, `frontend/src/api-types.ts`
- Theme และตัวอย่างระบบแปล: `frontend/src/styles/admin-theme.css`,
  `frontend/src/accountMessages.ts`, `frontend/src/tradingAccountMessages.ts`

รายการนี้เป็นผลค้นของเดิมเพื่อใช้เตรียม plan ไม่กำหนดไฟล์แก้ไข/schema ใหม่
หรืออนุมัติการเปลี่ยน API/สูตรก่อนผ่านขั้น requirements

## ยังไม่ชัด — Needs Clarification

ติดตามรหัสใน `mission.md` §9; คำตอบฉบับละเอียดบันทึกที่นี่แห่งเดียว

### NC-39 — Closed: ขอบเขตแท่งเทียนสด

**คำตอบเจ้าของ 2026-10-12:** “รวมแท่งเทียนสดใน F-12”

ปิดการเลือกระหว่างประวัติอย่างเดียวกับแท่งสด; ไม่ใช่การอนุมัติวิธีรับข้อมูล
หรือการเปลี่ยน finality/formula ของงานเดิม RQ-25..28 เป็นข้อเสนอรายละเอียด
ที่เป็นฐานของขั้นแผน แผนต้องตรวจสัญญาข้อมูลสดจากเอกสารทางการ
และหลักฐานก่อนกำหนด transport/ordering/freshness/cadence/recovery
ถ้าพบช่องว่างที่ต้องเปลี่ยนข้อกำหนดเดิมให้เพิ่ม Needs Clarification และหยุดถาม

### NC-40 — Closed: เลื่อนจุดเข้า/ออกจริง

**คำตอบเจ้าของ 2026-10-12:** “เลื่อนจุดเข้า/ออกจริงจนมีข้อมูลออเดอร์ แล้วติดตามใน roadmap”

R-14 ยังคงต้องมีจุดเข้า/ออก แต่ไม่ตรวจรับในรอบกราฟนี้
เมื่อสัญญาข้อมูลออเดอร์พร้อม ต้องกำหนดงานเชื่อมกราฟ/requirements/plan/validation
และขออนุมัติตามขั้นเดิมก่อน implement; ไม่ถือว่าระบบออเดอร์เสร็จแล้ว
หรือเลือกนิยาม entry/exit ของ Spot แทนเจ้าของ

### NC-41 — Closed: การแทนตัวเลขเฉพาะการวาดกราฟ

กฎเดิมรักษาตัวเลขเงินเป็น exact และ component ปัจจุบันไม่แปลงเป็น Number
แผนต้องตรวจ numeric input ของ Lightweight Charts รุ่นที่จะใช้จากเอกสารทางการ
เจ้าของตอบวันที่ 2026-10-12: “อนุญาตเฉพาะการวาดตามขอบเขตนี้”

**ขอบเขตที่เจ้าของอนุญาต:** แปลงแบบสูญเสียความละเอียดเฉพาะที่ขอบตัววาดกราฟ
เก็บข้อมูล API และข้อความ OHLCV/indicator ที่ผู้ใช้อ่านเป็น exact ต่อไป
ไม่ใช้ค่าที่แปลงแล้วคำนวณเงิน สูตร indicator signal หรือส่งออเดอร์
tooltip/ค่าที่อ่านจากการชี้แท่งใช้ข้อมูล exact ต้นฉบับ ไม่อ่านย้อนจากพิกัดภาพ
ค่าที่วาดไม่ได้หรือแปลงแล้วผิดขอบเขตต้องรายงานข้อจำกัด ไม่วาดข้อมูลหลอก
รายละเอียดเกณฑ์ตรวจการแปลง/แกนราคาเสนอใน plan + validation หลังคำตัดสิน

ปิดคำตัดสินขอบเขตการแปลง; ไม่เปลี่ยน Money/Quantity หรืออนุมัติการคำนวณเงินด้วย float
ยังต้องเสนอ numeric boundary และวิธีแสดงแกนราคาใน plan/validation

## ขั้นอนุมัติ

หลังรีวิวฉบับแก้ไขผ่าน เจ้าของสั่ง “create plan/validation” วันที่ 2026-10-12
จึงบันทึกการอนุญาตเข้าสู่ขั้นแผนของ requirements ฉบับนี้; NC-39..41 ปิดแล้ว
ไม่มี Needs Clarification ที่เปิดอยู่ใน requirements ณการเริ่มขั้นแผน
ตาม [AGENTS.md](../../../AGENTS.md) และ [วิธีเขียน feature spec](../README.md)
สถานะอนุมัติ plan.md + validation.md ดูหัวเอกสารแต่ละฉบับ;
ต้องได้รับอนุมัติขั้นนั้นและมีเงื่อนไขการเขียนโค้ดครบก่อน implementation
