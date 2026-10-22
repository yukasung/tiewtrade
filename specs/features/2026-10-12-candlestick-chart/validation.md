# F-12 — กราฟแท่งเทียนบนหน้าเว็บ — Validation

**Pair-scope amendment — Approved 2026-10-15:** ใช้ F-38 เป็นเกณฑ์ปัจจุบัน:
กราฟรองรับ BTCUSDT และ ETHUSDT × 8 timeframe รวม 16 series และ workload ชุดยาววัด
BTCUSDT 8 series. ผล deep history 40/40 เดิมด้านล่างเป็นหลักฐาน historical เท่านั้น.

ผลหลัง merge ล่าสุด: [post-merge validation checkpoint](evidence/2026-10-14-post-merge.md).
ผลแก้ viewport ตาม P-H3: [anchor regression evidence](evidence/2026-10-14-viewport.md).

## Candle-only chart reads — Approved 2026-10-14

เพิ่ม [continuity validation](candle-continuity-amendment.md): delayed REST, cold reload,
หลายขอบแท่ง, buffer cap, source precedence และ gap จริง.

ใช้ [validation amendment](candle-only-chart-amendment.md) สำหรับหน้ากราฟที่ไม่มี
indicator; bundle/proof checks เดิมคงใช้กับ service ที่ยังรองรับ indicator.

## Amendment — ช่วงประวัติที่เลื่อนดูได้

สถานะ: **Approved** — สำหรับ requirements RQ-37..42 ที่อนุมัติ 2026-10-14;
validation เดิมส่วนอื่นยัง Approved. ผลตรวจและรายการค้างอยู่ใน [history checkpoint](evidence/2026-10-14-history-window.md); ยังไม่ถือว่าผ่านครบ.

| เกณฑ์ | สิ่งที่ต้องพิสูจน์ | Traceability |
|---|---|---|
| V-H1 | ทั้งหก TF 1m–1d ดูถึงสามเดือนปฏิทินจาก server UTC; เดือน 28/29/30/31 วัน, leap year, ขอบที่คร่อมแท่ง, timezone และ client clock skew ถูกต้อง | RQ-37; P-H1 |
| V-H2 | 1w/1M อ่านข้อมูลเกินห้าปีได้เมื่อมีข้อมูลจริง; calendar alignment และขอบเก่าสุดแยกตามคู่/TF; timeout, rate limit, หน้า empty และ gap ไม่ทำให้แจ้งหมดประวัติผิด | RQ-38/41; P-H2 |
| V-H3 | เลื่อนเกิน 1,000 แท่งและหลายหน้าถึงขอบสามเดือนโดยไม่ซ้ำ/ขาดรอยต่อ; โหลดเพิ่มไม่กระโดด viewport และไม่ทับแท่งสดด้วยข้อมูลเก่า | RQ-39/40; P-H3 |
| V-H4 | สลับ TF/คู่, logout, unmount และสลับเร็วระหว่าง 1m/1M ยกเลิกงานเก่า; concurrency, dedup, Retry-After และ manual retry ไม่เกิด request storm | RQ-40; P-H3 |
| V-H5 | Migration อัปเกรดฐานเดิมโดยไม่ลบ/แก้ candles เดิม; constraints, grants, partition/cleanup, restart, lease takeover, rollback และ source failure รักษา progress/idempotency | RQ-41/42; P-H2 |
| V-H6 | exact OHLCV/finality คงเดิม; indicator สูตร/seed ไม่เปลี่ยน และ proof ไม่รับรองหน้าที่อยู่นอก calculation window; ไม่มี order requests | RQ-42; P-H1..3 |
| V-H7 | Initial chart ไม่รอทุกหน้า; หน้าประวัติไม่เกิน 1,000 slots, request ต่อ episode และจำนวนหน้าใน memory ไม่เกิน bound ที่กำหนด; evict แล้วเลื่อนกลับโหลดได้ | RQ-39; P-H3 |
| V-H8 | Browser กับ API จริงตรวจ 1m/5m/15m/1h/4h/1d และ 1w/1M รวม pan/retry/reset; หลักฐานแยก source unavailable จากข้อผิดพลาดโปรแกรม ไม่ใช้ mock smoke แทนการตรวจข้อมูลจริง | RQ-37..42; P-H4 |

ระหว่างพัฒนาเลือก targeted tests ตาม impact รวม calendar/storage/API/pagination,
concurrency และ safety ที่เกี่ยวข้อง พร้อม lint/type-check. ห้ามรัน destructive fixtures
บนฐานที่ UI ใช้อยู่. Full regression/workload เป็น **Pending Full Validation**
จนถึง checkpoint เดิม; ห้ามรายงานดูได้ครบก่อน V-H1..8 มีหลักฐานครบตามข้อจำกัดของต้นทาง.

ผลตรวจ backfill ช่วงล่าสุด: [recent-history priority amendment](recent-history-priority-amendment.md).

ผลตรวจรับหลัง merge ล่าสุดอยู่ใน [acceptance progress 2026-10-14](evidence/2026-10-14-acceptance-progress.md):
browser จริงผ่าน 8 TF; backfill เดิมอีก 15 series จบแล้วและ deep history 40/40 series
ผ่าน continuity กับ API traversal ถึง `display_start`. PREPARED C2 rerun ผ่านช่วงวัดเต็มแล้ว;
V-17 ยังเป็น Pending Full Validation เพราะ F-12 workload, C3/C5, C6/R2-7 และเกณฑ์ release
ที่เหลือยังไม่ครบ. ช่องว่างแท่งสดจาก preview writer unavailable บันทึกแยก ไม่ใช้ deep-history
pass กลบ freshness risk.

ผลติดตาม 2026-10-22 อยู่ใน [live-preview recovery](evidence/2026-10-22-live-preview-recovery.md):
development containers ถูกสร้างจาก base Compose โดยไม่มี chart override ทำให้ candle supervisor
ไม่เริ่ม; recreate ทั้ง market-data/API/frontend ด้วย override เดิมแล้วได้ 16/16 live series.
warning ทั้ง price/candle เกิดหนึ่งครั้งหลัง macOS ตื่นจาก Deep Idle (power log ตรงเวลา),
จากนั้น supervisor reacquire/bootstrap เอง; snapshot หลังเหตุการณ์ยืนยัน connected/bootstrapped,
lease ต่ออายุและ preview อายุ 0.29 วินาที โดยไม่มี warning ซ้ำหลัง recovery.
browser session จริงตรวจ pan แล้วขอหน้าเก่า 1,000 rows ด้วย cursor จริง, รักษา viewport,
reset กลับช่วงล่าสุดโดยไม่ยิง API และ recovery จาก controlled 429 เคารพ Retry-After
ก่อน manual retry ไปยัง API จริงสำเร็จ. เมื่อรวมกับ browser 8 TF และ API traversal เดิม
V-H8 และ history-window V-H1..8 ผ่านแล้ว. ผลนี้ไม่แทน V-17/workload, soak,
release gates หรือ owner manual acceptance.

เกณฑ์และผลตรวจการกู้กราฟหลัง history error อยู่ใน
[amendment ที่อนุมัติ](chart-error-recovery-amendment.md); ไม่ทดแทน full validation เดิม.

สถานะ: **Approved** — เจ้าของอนุมัติวันที่ 2026-10-13 — เกณฑ์ amendment วันที่ 2026-10-13 สำหรับการแสดงแท่งเทียนก่อน indicator; เกณฑ์เดิมส่วนอื่นยังมีผล
การลบ MACD ด้านล่าง: **Approved** — เจ้าของอนุมัติ amendment เมื่อ 2026-10-13; เกณฑ์ใหม่ยังไม่ได้รันและไม่แทนผล Partial/Pending เดิม
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
การเพิ่ม timeframe `1w` และ `1M` ทั้งระบบด้านล่าง: **Approved** — เจ้าของอนุมัติ plan/validation amendment เมื่อ 2026-10-14; ผลล่าสุดอยู่ในตาราง TF-01..TF-18
ข้อจำกัด REST 7 วันสำหรับ `1w`/`1M`: **Approved** — เจ้าของยืนยัน amendment เมื่อ 2026-10-14
วันที่: 2026-10-12
Branch: feature/f-12-candlestick-chart
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [หลักฐานต้นทาง](source-evidence.md)

## Amendment — ตรวจ native timeframe `1w` และ `1M` ทั้งระบบ (Approved 2026-10-14)

ผลในตารางอัปเดตจากหลักฐานรอบล่าสุด; ข้อที่ยังไม่ครบคงเป็น **Partial/Not Run**. Targeted checks ระหว่างพัฒนาไม่แทน full regression หรือ
workload checkpoint และต้องบันทึก command, commit/source hash, fixture/database และเวลารันตาม
`specs/standards/testing.md` §7.

| รหัส | เกณฑ์ตรวจรับ | ระยะรัน | ผล |
|---|---|---|---|
| TF-01 | หลักฐานทางการยืนยัน REST/WebSocket รองรับ `1w`/`1M`, stream naming, close-time fields, update/reconnect, เพดาน connection และ public observation ยืนยัน REST จำกัดช่วงไม่เกิน 7 วัน; fixture ระบุวันเก็บและ checksum | ก่อน implementation | Passed — เอกสารทางการ, REST error `-4088` และ public fixtures `16`/`17` พร้อม SHA-256 ใน source-evidence |
| TF-02 | Unit/property tests พิสูจน์ floor/ceil/next/previous/advance/slot count ของ 8 TF; `1w` เริ่ม Monday UTC และ `1M` ผ่าน Feb 28/29, เดือน 30/31, Dec→Jan โดยไม่ใช้ fixed month duration | ระหว่างพัฒนา | Passed - targeted core calendar/property regression passed; 8 TFs, Monday UTC, leap/month/year transitions, and slot iteration covered |
| TF-03 | Regression ของ 6 TF เดิมให้ boundary/window/gap/initial-window เท่าเดิม; retention ยังคง 365 วัน ส่วน `1w`/`1M` ใช้ calendar five-year cutoff และไม่เกิน 1,000 slots ต่อ page | ระหว่างพัฒนา | Passed - the same core regression covers the original 6 TFs, 365-day retention, calendar five-year cutoffs, and 1,000-slot bounds |
| TF-04 | Migration upgrade จาก 0025 บนฐานที่มีข้อมูลเดิมไม่ rewrite/change checksum แถวเดิม; constraints รับ boundary ถูกของ 8 TF และปฏิเสธค่า/casing/open/end ผิด | ระหว่างพัฒนา | Passed — isolated PostgreSQL migration regression ตรวจ checksum แถวเดิมก่อน/หลัง `0025 -> 0026` และ matrix ปฏิเสธ casing/open/end ที่ผิดของ `1w`/`1M`; boundary ถูกของ 8 TF ผ่าน |
| TF-05 | Migration สร้าง partitions ครบห้าปีย้อนหลังและ horizon เดิมพร้อม grants; rerun/recovery ไม่ชนของเดิม และ downgrade ปฏิเสธแบบไม่สูญข้อมูลเมื่อมี `1w`/`1M` | ระหว่างพัฒนา | Passed — automated inventory ตรวจทุก monthly partition ใน five-year retention ถึง horizon พร้อม API/market-data grants; replay และ atomic downgrade guard ผ่าน |
| TF-06 | SQL indicator functions ให้ boundary/page/next slot ตรงกับ Python schedule สำหรับทุก TF รวม leap/month transition และไม่ตีความ unknown TF เป็น `1d` | ระหว่างพัฒนา | Passed — SQL floor/advance/slot parity ตรง Python schedule ครบ 8 TF ที่ leap day และขอบปี; unknown/casing invalid ยังคง fail closed |
| TF-07 | REST adapter ส่ง `interval=1w`/`1M`, จำกัดหนึ่ง native candle และ upstream range ≤7 วัน, รักษา case และ map native open/close/OHLCV exact โดย `1M` ใช้ monthly end จริง; payload ผิด boundary, ลำดับ หรือ interval fail closed โดยไม่ commit บางส่วน | ระหว่างพัฒนา | Passed - 22 targeted adapter/fixture cases passed, including native `1w`/`1M`, one-slot cap, upstream range <= 7 days, exact OHLCV/end, and rejection above one slot |
| TF-08 | Initial/backfill/refresh/gap repair ของ `1w`/`1M` อยู่ใน retention 5 ปี, แบ่ง weekly/monthly ครั้งละหนึ่งแท่งโดยไม่ขอ REST เกิน 7 วัน, claim fenced/idempotent และ retry ไม่สร้าง duplicate candle/cursor advance ซ้ำ | ระหว่างพัฒนา | Passed — ingestion/calendar regressions ครอบคลุม contiguous, gap, retry, fence/idempotency และ one-native-candle REST cap; history-window acceptance ยืนยัน traversal จริงถึง retention edge |
| TF-09 | Shared live feed สมัครครบ 16 unique streams ตาม F-38 บน connection กลางเดียว; mapper รับ `kline_1w`/`kline_1M`, กัน duplicate/out-of-order/conflict และไม่สร้าง per-user venue connection | ระหว่างพัฒนา | Passed — runtime regression ยืนยัน 2 pairs × 8 TF = 16 series; mapper/preview/shared connection และ development recovery ยืนยันครบ 16/16 โดยไม่มี per-user venue connection |
| TF-10 | Disconnect/reconnect/bootstrap กู้ช่วงขาดด้วย REST timeframe เดียวกัน, ไม่ทำแท่งหาย/ซ้ำ และไม่ประกาศ CLOSED จากเวลา/แท่งถัดไปโดยไม่มีหลักฐาน | ระหว่างพัฒนา | Passed — actual-role PostgreSQL integration ครอบ H1/W1/MN1 ตั้งแต่ preview gap → disconnect → reconnect/bootstrap → fake REST ingestion commit; ทุก request ใช้ TF เดิม, demand COMPLETE, open-time ไม่ซ้ำ และ preview/REST rows ไม่ถูกประกาศ CLOSED |
| TF-11 | Indicator batch/stream รับลำดับ calendar ของ `1w`/`1M`; สูตร/rounding/Money/Quantity ของ TF เดิมไม่เปลี่ยน และข้อมูลไม่พอคืน WARM_UP โดยไม่เติมศูนย์/ลด period/อ่านนอก retention | ระหว่างพัฒนา | Passed — calendar warm-up regression ตรวจ weekly 201 slots ถึง EMA200 และ monthly 60 slots ยังคง WARM_UP พร้อม EMA20 boundary; arithmetic/retention เดิมผ่านและไม่มี float/bare Decimal path ใหม่ |
| TF-12 | Checkpoint codec v2 fixture เดิม decode/round-trip เหมือนเดิม; checkpoint weekly/monthly strict round-trip และ reject skipped/repeated/misaligned calendar slot | ระหว่างพัฒนา | Passed — codec regression ผ่าน fixture/round-trip เดิมและ matrix W1/MN1 สำหรับ skipped, repeated และ misaligned calculation boundary |
| TF-13 | Authenticated candle/chart/indicator APIs รับ `1w`/`1M`; ปฏิเสธ `1W`, `1mo` และ casing อื่นตาม contract; auth/CSRF/error/retry budgets เดิมไม่ถดถอย | ระหว่างพัฒนา | Passed — authenticated candle-page suite ครบ 8 TF; chart history และ indicator route รับ `1w`/`1M` ถึง controller boundary และทั้งสอง route ปฏิเสธ `1W`, `1mo`, trailing-space ด้วย `INPUT_REJECTED`; development session ขอ candle pages จริงได้ HTTP 200 |
| TF-14 | Exported OpenAPI และ generated TypeScript มี enum 8 ค่าและ `npm run check:api` ผ่านโดยไม่มี manual divergence | Candidate | Passed — required CI API contract gate ผ่านบน final source head; exported OpenAPI/generated TypeScript มี enum ครบ 8 ค่าโดยไม่มี generated diff |
| TF-15 | UI ใช้ Admin Template Select แสดง 8 ค่า, default `1h`; การสลับ `1m`↔`1M` เร็ว ๆ ยกเลิก/กัน stale response และไม่ aggregate candle ใน browser | ระหว่างพัฒนา | Passed - 42 frontend targeted tests passed on unchanged UI source, covering 8 options, default `1h`, and existing stale-response behavior |
| TF-16 | Browser smoke เห็น history และ live candle ของ `1w`/`1M`, reset/theme ยังทำงาน, ไม่มี blank chart จากการสลับ TF และ network log ไม่มี order/live-trading request | Candidate | Passed — post-merge runtime smoke แสดง `1w` 479 rows และ `1M` 111 rows พร้อม live OHLCV; reset/theme ผ่าน, ไม่มี page error หรือ order/live-trading request |
| TF-17 | Targeted lint/type/import checks และ tests ของ core, migration/storage, ingestion, venue stream, indicator, API และ frontend ที่ได้รับผลผ่านบน source เดียวกัน | Candidate | Passed — targeted evidence เดิมและ required CI บน final source head ผ่าน: backend 2,710, frontend 237, browser 17 พร้อม static/contracts/container gates |
| TF-18 | Full regression, migration gate, generated contracts และ required CI ผ่าน; workload วัด backfill ห้าปีและ live 40 streams ตามเกณฑ์เดิมโดยไม่ลด safety/error bounds | ก่อน merge/release | Partial — full regression/migration/contracts/required CI ผ่านก่อน merge; workload/resource/endurance ส่วน release ยังคง Pending Full Validation ตาม V-17 |

### Development evidence 2026-10-14 - `1w` / `1M`

รายการด้านล่างเป็น snapshot ระหว่างพัฒนาก่อน post-merge checkpoint; สถานะล่าสุดของ
TF-16..18 และ CI ให้อ้างอิง [หลักฐานหลัง merge](evidence/2026-10-14-post-merge.md).

- Core/indicator/codec/stream mapping: 151 targeted tests passed.
- Binance TH REST adapter and public fixtures `16`/`17`: 22 targeted cases passed via a direct async harness because the existing Windows socket monkeypatch conflicts with the Proactor event loop.
- PostgreSQL storage, ingestion, and 40-series preview persistence: 5 targeted cases passed on migration `0026`.
- Alembic replay `0026 -> 0025 -> 0026` passed after correcting the calendar-retention constraint and SQL-helper teardown order; the populated downgrade guard also rejected atomically.
- Scoped ruff and `mypy src/tiewtrade` (156 source files) passed. Earlier frontend targeted 42 tests, typecheck, and scoped ESLint remain valid because frontend source has not changed since those runs.
- The targeted scheduler catalog gate could not start because the current local database has revoked `CONNECT` from `tiewtrade_indicator_builder`; this is recorded as environment-blocked and is not counted as passed.
- ณ development snapshot นี้ full regression/browser smoke ยังไม่ได้รัน; หลักฐานหลัง merge
  ปิดสองส่วนนั้นแล้ว. Five-year/40-stream workload และ release performance gates ยังคง
  `Pending Full Validation` ใน TF-18/V-17.


### ชุดทดสอบตามผลกระทบ

- Core: `tests/core/test_market_data.py`, `test_indicators.py` และ test ใหม่สำหรับ calendar schedule.
- Database/infra: migration, partitions, permissions, retention, claims, storage, preview และ
  indicator codec/claims/staging/publication/source tests.
- Services/venue/API: ingestion, Binance TH REST/stream mapping/feed, candle/chart/indicator routes,
  numeric windows และ failure contracts.
- Frontend: `CandlestickChartPanel`, chart query/realtime/renderer tests ที่เกี่ยวข้อง พร้อม
  `npm run typecheck`, scoped lint และ API generation check.
- ก่อน merge รัน full backend/frontend gates ตาม testing standard เมื่อ candidate นิ่ง; ไม่รันซ้ำ
  หาก source และ dependencies ไม่เปลี่ยน. Performance/endurance เต็มคงเป็น TF-18/V-17
  `Pending Full Validation` จนถึง release checkpoint.

### Fixtures และ edge cases บังคับ

- Weekly: Sunday ก่อน boundary, Monday 00:00 UTC, year crossing และ window ที่ไม่มีข้อมูล.
- Monthly: Jan 31→Feb 1, Feb leap/non-leap, Apr/Jun/Sep/Nov, Dec→Jan และ five-year cutoff จาก Feb 29.
- Exact case: `1m` กับ `1M` อยู่ร่วมกันใน DB/API/cache/query key โดยไม่ชนกัน.
- Failure: 429/5xx/timeout, malformed close time, partial page, stale HTTP response, duplicate stream,
  reconnect gap, missing partition และ lease/fence loss; retry ต้องไม่เพิ่มข้อมูลหรือ cursor ซ้ำ.
- Safety: ไม่มี test ใดส่ง Live order หรือแก้ balance/position; log/error ห้ามมี API key/secret.

## Amendment — ตรวจ Trading Workspace layout (Approved 2026-10-14)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| TW-01 | Desktop แสดง market bar ด้านบน, chart ด้านซ้าย, order placeholder ด้านขวา และ history ใต้ chart ตาม grid ที่อนุมัติ | Passed — browser screenshot และ bounding boxes ที่ 1440/1280px |
| TW-02 | Chart ยังแสดงพื้นขาว, OHLCV exact, live candle, pan/zoom/crosshair/reset และสลับ pair/TF ได้โดยไม่มี regression | Passed — targeted panel/renderer tests 35 tests และ browser smoke เห็น chart จริง |
| TW-03 | Order placeholder ใช้ shared Admin Template Input/Select/Label/Button; controls ทุกตัว disabled, มี accessible label, ใช้ปุ่มข้อความ `ยังไม่เปิดใช้งาน` และไม่มีปุ่มที่อ้างว่าส่งคำสั่งซื้อ/ขายได้ | Passed — component assertions และ browser disabled-control check |
| TW-04 | ไม่มี submit handler/form action, ไม่มีค่าราคา/จำนวน/balance จำลอง และการกด/พยายามกรอกไม่สร้าง POST/PUT/PATCH/DELETE หรือ order/trading request | Passed — source/component assertions และ browser request log ไม่มี mutation |
| TW-05 | History ใช้ semantic shared table, แสดงหัวตารางกับ empty state เท่านั้น และไม่มี mock order/trade | Passed — component assertions และ visual smoke |
| TW-06 | ที่ viewport 1440px และ 1280px grid ไม่ทับกัน; ที่ 768px และ 390px เรียง market→chart→order→history และ document ไม่มี horizontal overflow | Passed — browser bounding/overflow assertions ทั้ง 4 viewport |
| TW-07 | Default/hover/focus/disabled ของ controls, border, spacing, radius และสีตรง Admin Template โดยตรวจ component assertions และ computed style ของ state ที่เกี่ยวข้อง | Passed — component assertions และ Chromium computed styles ยืนยัน select default/focus กับ disabled button (`8px`, `44px`, focus border, cursor/opacity) ตาม shared tokens |
| TW-08 | Account navigation/module routes, chart-as-default route, authentication และ sidebar toggle ยังทำงาน | Passed — targeted navigation tests และ authenticated browser smoke |
| TW-09 | Diff ไม่มีการเปลี่ยน backend, OpenAPI, database, money/order/balance/position/PnL หรือ exchange integration | Passed — scoped diff review มีเฉพาะ frontend/spec/evidence |
| TW-10 | Type-check, scoped ESLint, targeted component/layout/renderer tests และ browser smoke ผ่านกับโค้ดฉบับสุดท้าย | Passed — type-check/lint exit 0, 35 targeted tests passed, browser smoke ไม่มี page error |
| TW-11 | Desktop workspace พอดีกับพื้นที่ใต้ header, document ไม่มี vertical scrollbar และ history สูงกว่า chart; mobile ยังเรียงแนวตั้งและเลื่อนได้ | Passed — Chromium geometry ที่ 1440×1000 และ 1280×900 ไม่มี page scrollbar, history:chart เป็น 5:4; mobile 390×844 ยังเลื่อนได้ |
| TW-12 | Market bar ไม่แสดง `กราฟแท่งเทียน`, `คู่เทรด`, `Timeframe`, ยังมี accessible select names และมีความสูงลดลงโดยไม่เปลี่ยน control size | Passed — component test และ Chromium ยืนยัน visible labels ไม่มี, select names ครบ, bar สูง 65px และไม่มี page scrollbar |
| TW-13 | History tabs ใช้ underline pattern ของ Admin Template, อยู่ชิดซ้ายใน history header และไม่ทับ chart หรือแกนเวลา | Passed — ใช้ TabWithUnderline source pattern; Chromium ยืนยัน chart bottom เท่ากับ history top, tabs อยู่ภายใน history และไม่มี page scrollbar |
| TW-14 | Header มี theme toggle ตาม Admin Template; default Light, สลับ Light/Dark ได้, accessible name ถูกต้อง และค่าคงอยู่หลัง reload | Passed — component test และ Chromium ตรวจ root class/data attribute/local storage/reload |
| TW-15 | Sidebar/header/workspace/controls/tabs/table/chart เปลี่ยนสีพร้อมกัน โดยข้อมูลกราฟและ viewport ไม่ถูกล้างและไม่มี API request เพิ่ม | Passed — computed colors เปลี่ยนครบ, OHLC ยังแสดง และ request log ระหว่าง toggle ว่าง |
| TW-16 | Targeted theme/layout/renderer tests, type-check, scoped ESLint และ browser smoke ทั้งสองโหมดผ่าน | Passed — 40 tests / 3 files, type-check/ESLint exit 0, Chromium ไม่มี page error |

หลักฐานขั้นต่ำ: test output ของไฟล์ที่ได้รับผลกระทบ, browser screenshots desktop/mobile,
bounding/overflow assertions, computed styles ของ control states และ network request log ระหว่างลองใช้
placeholder กับสลับ timeframe. เก็บผลใน `evidence/checkpoint.md`; เกณฑ์ V-01..V-18 และ
Pending Full Validation เดิมยังคงผลเดิมและไม่ถูกแทนด้วย TW-01..TW-10.

## Amendment — ตรวจการลบตัวเลือกภาษา (Approved 2026-10-14)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| LNG-01 | หน้า Chart ไม่มี label หรือ combobox ชื่อ `ภาษา` | Passed — component test และ served-source smoke |
| LNG-02 | ข้อความและวันเวลาบน Chart ยังแสดงภาษาไทย | Passed — fixed Thai locale และ component test ตรวจหัวข้อ/วันที่ไทย |
| LNG-03 | pair/TF, ปุ่ม `รีเซ็ตกราฟ`, viewport และข้อมูล exact OHLCV ยังทำงาน และไม่มี backend/API change | Passed — targeted component/renderer tests และ diff review |

ตรวจด้วย targeted component/renderer tests, type-check, scoped ESLint และ frontend smoke;
ไม่รัน full suite หรือ performance validation สำหรับการลด control เฉพาะ UI นี้.

หลักฐานรอบ 2026-10-14: targeted component/renderer ผ่าน 2 files/28 tests,
`npm run typecheck`, scoped ESLint และ `git diff --check` ผ่าน. `GET /chart` ตอบ 200;
source ที่ Vite เสิร์ฟไม่มี language key/change handler และใช้ fixed Thai locale. ไม่ใช้ผลนี้แทน full E2E.

## Amendment — ตรวจปุ่มรีเซ็ตกราฟภาษาไทย (Approved 2026-10-14)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| RST-01 | หน้า Chart มีปุ่ม accessible ชื่อ `รีเซ็ตกราฟ` เป็นภาษาไทย | Passed — component test และ frontend smoke |
| RST-02 | หลัง pan/zoom แล้วกดปุ่ม viewport กลับช่วงเริ่มต้นที่ยึดแท่งล่าสุด | Passed — component test ตรวจ logical range เดียวกับ initial viewport |
| RST-03 | การกดปุ่มไม่เปลี่ยน pair/TF/language และไม่ส่ง refresh/retry/history request เพิ่ม | Passed — component test ตรวจค่าตัวเลือกเดิมและ diff review ยืนยันว่า handler เรียกเฉพาะ chart time scale |

ตรวจด้วย targeted component/renderer tests, type-check, scoped ESLint และ frontend smoke;
ไม่รัน full suite หรือ performance validation สำหรับการเพิ่ม control เฉพาะ UI นี้.

หลักฐานรอบ 2026-10-14: targeted component/renderer ผ่าน 2 files/27 tests,
`npm run typecheck` และ scoped ESLint ผ่าน. `GET /chart` ตอบ 200 และ Vite HMR
โหลด handler `resetViewport` จาก source ใหม่แล้ว. ไม่ใช้ผลนี้แทน full E2E หรือด่าน candidate เดิม.

## Amendment — ตรวจการลด controls และข้อความใต้กราฟ (Approved 2026-10-14)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| U-01 | ไม่มี scale note และปุ่ม latest/older/retry/refresh/previous/next ในหน้า Chart | Passed — component test และ source ที่ Vite เสิร์ฟไม่พบ controls/ข้อความดังกล่าว |
| U-02 | pair/TF/language, automatic loading, pan/zoom/crosshair, exact OHLCV และ error alert ยังทำงาน | Partial — targeted component/renderer tests ผ่าน; ยังไม่ได้รัน browser E2E เต็มชุดในรอบแก้ UI นี้ |
| U-03 | ไม่มี dead handler/state/import/CSS จาก controls ที่ลบ และ backend/API ไม่เปลี่ยน | Passed — type check, scoped ESLint และ diff review ผ่าน |

หลักฐานรอบ 2026-10-14: `npm test -- --run tests/CandlestickChartPanel.test.tsx tests/AccountLayout.test.tsx tests/chart-renderer.test.ts`
ผ่าน 3 files/32 tests; `npm run typecheck`, scoped ESLint และ `git diff --check` ผ่าน.
`GET http://localhost:5173/chart` ตอบ 200 และ source ที่ Vite เสิร์ฟไม่พบชื่อ controls หรือ `chart-scale-note`.
การสร้าง Docker image ใหม่ยังทำไม่ได้ในรอบนี้เพราะ Docker DNS หา `auth.docker.io` ไม่พบ;
จึงอัปเดต source ใน frontend container ที่รันอยู่และยืนยัน Vite HMR แล้ว. Full E2E/build ยังคงอยู่ในด่าน candidate เดิม.

ตรวจด้วย targeted component tests, type-check, ESLint และ frontend smoke;
ไม่รัน full suite หรือ performance validation สำหรับการลด UI นี้.

## Amendment — ตรวจการลบ Indicator จาก UI (Approved 2026-10-13)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| I-01 | ไม่มีตัวเลือก ชื่อ ค่า เส้น หรือ pane ของ EMA/RSI/ATR ในหน้า Chart | Passed — component/smoke 2026-10-13 |
| I-02 | แท่งเทียน, exact OHLCV, pair/TF, crosshair, viewport และ gap navigation ยังทำงาน | Partial — targeted component/renderer ผ่าน; ยังไม่รัน full E2E |
| I-03 | Backend/API F-11 และ proof/consistency contract ไม่ถูกเปลี่ยนจากงาน UI นี้ | Passed — diff review 2026-10-13 |

ตรวจด้วย targeted component/renderer tests, type-check, ESLint และ frontend smoke;
ไม่รัน full suite หรือ performance validation สำหรับการลด UI นี้.

ผลรอบ implementation: targeted component/renderer/layout tests 31/31, TypeScript
type-check, ESLint และ `git diff --check` ผ่าน. Rebuild/restart frontend สำเร็จ,
`/chart` ตอบ 200 และ source ที่ให้บริการไม่มีชื่อหรือ controls ของ Indicator.

## Amendment — ตรวจการลบแถบสถานะถาวร (Approved 2026-10-13)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| S-01 | ไม่มี block ข้อความประวัติ/Indicator/gap/feed/as-of/server-check เหนือกราฟ | Passed — component/smoke 2026-10-13 |
| S-02 | Error/alert, finality, disabled/loading controls และ gap ของตำแหน่งที่เลือกยังทำงาน | Passed — targeted component 2026-10-13 |
| S-03 | การลบ presentation ไม่เปลี่ยน request, retry, proof หรือ consistency gate | Partial — E2E ปรับไปตรวจ API state แล้ว; ยังไม่รัน full E2E |

ตรวจด้วย targeted component tests, type-check, ESLint และ frontend smoke;
ไม่รัน full suite หรือ performance validation สำหรับการลบ presentation นี้.

ผลรอบ implementation: targeted component/layout tests 19/19, TypeScript type-check,
ESLint และ `git diff --check` ผ่าน. Rebuild/restart frontend สำเร็จ, `/chart` ตอบ 200
และ source ที่ให้บริการไม่มี `chart-status`. ยังไม่ใช้ผลนี้แทน full E2E หรือ V-17/V-18.

## Amendment — ตรวจรายละเอียดแท่งใน chart (Approved 2026-10-13)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| C-01 | ภายในกรอบกราฟแสดงคู่/TF/ตลาด วันเวลา finality และ O/H/L/C/V exact ของแท่งล่าสุดหรือแท่งที่เลือก โดย V ใช้หน่วยเหรียญฐานและไม่มี Volume pane | Passed — component 2026-10-13 |
| C-02 | Crosshair และปุ่มก่อนหน้า/ถัดไปเปลี่ยนข้อมูลชุดเดียวกัน; ออกจากแท่งแล้วกลับแท่งล่าสุด; indicator ที่ proof ผ่านยังอ่านได้ | Partial — โค้ดและ E2E ปรับแล้ว; ยังไม่รัน full E2E |
| C-03 | ไม่มีชุดวันเวลา/OHLCV ซ้ำใต้กราฟ, header ไม่บังแกนราคาที่ความกว้างเป้าหมาย และ accessibility labels ยังอ่านได้ | Partial — DOM/targeted test ผ่าน; รอตรวจภาพหลายความกว้าง |

ตรวจด้วย targeted component tests, TypeScript type-check, ESLint และ frontend smoke;
ไม่รัน full suite หรือ performance validation สำหรับการย้าย presentation นี้.

ผลรอบ implementation: targeted component tests 12/12, TypeScript type-check และ
ESLint ของไฟล์ที่แก้ผ่าน; `git diff --check` ผ่าน. Rebuild/restart เฉพาะ frontend สำเร็จ
และ `/chart` ตอบ 200. ยังไม่ใช้ผลนี้แทน browser E2E หรือ V-17/V-18 ชุดเต็ม.

## Amendment — ตรวจรับกราฟหลังลบ MACD (Approved 2026-10-13)

| รหัส | เกณฑ์ตรวจ | ผล |
|---|---|---|
| M-01 | ไม่มีชื่อ ตัวเลือก pane/series หรือค่ารายละเอียด MACD ใน UI; EMA20/50/200, RSI14, ATR14 ยังเปิด/ปิดได้ และ ATR อยู่ pane แยกจาก RSI | Superseded/Passed — candle-only chart amendment ที่อนุมัติภายหลังลบ indicator UI ทั้งชุด; component และ browser ยืนยันไม่มี MACD/EMA/RSI/ATR controls หรือ labels |
| M-02 | Component/renderer/E2E ตรวจชุดชื่อใหม่และ no-MACD รวม latest/selected candle, pair/TF switch, loading และ proof mismatch; exact string/projection boundary คงเดิม | Superseded/Passed — candle-only component/renderer/E2E ครอบ exact candle, pair/TF switch, loading และ no-MACD; indicator proof ไม่อยู่ใน chart read path แล้ว |
| M-03 | Browser→API รุ่นใหม่แสดงชุด indicator ที่สอดคล้องกับ candle; ไม่มีค่า MACD จาก response/cache เก่าหรือคำตอบมาช้า; auth/routing ไม่ถดถอย | Superseded/Passed — approved candle-only API path ไม่เรียก `/indicators`; authenticated Chromium request log ไม่มี indicator request และ auth/routing ผ่าน |

รัน targeted tests, lint/type-check/build ที่เกี่ยวข้องและ browser smoke หลัง
backend v2 พร้อม. V-01..18 เดิมยังต้องตรวจตาม checkpoint ที่กำหนด; V-17
ยังเป็น Pending Full Validation ไม่ใช้ M-01..03 แทนเกณฑ์เดิม.

## เสร็จหมายถึงอะไร

ภาพกราฟตามคำสั่งเจ้าของ 2026-10-13: ตรวจแถบคู่/TF/OHLC exact และ finality
บนกราฟ, พื้นสีขาวเริ่มต้น/กริด/เส้นราคาล่าสุด, สถานะข้อมูลที่อ่านได้ และไม่เพิ่ม
ราคา bid/ask หรือปุ่มซื้อขายจากภาพอ้างอิง. ตรวจผ่าน targeted component/renderer
tests, lint/type-check และเปิดหน้าเว็บจริง; ไม่ใช้แทน V-17/V-18 ชุดเต็ม.

ผลรอบภาพกราฟ: targeted component/renderer 21/21 ผ่าน, ESLint ของไฟล์ที่แก้,
TypeScript type-check และ Vite build ผ่าน. Build/restart frontend สำเร็จ; `/chart`
และ API health ตอบ 200 ในรอบก่อนเปลี่ยนพื้นเป็นสีขาว. ฐาน app มี BTC/USDT
1d 364 แท่งและ 1h 1,082 แท่ง ณ รอบตรวจ จึงมีประวัติพอสำหรับ viewport เริ่มต้น.
ยังไม่ได้ตรวจภาพหลังเข้าสู่ระบบด้วย browser automation ในรอบนี้; เกณฑ์ V-17/V-18
และผล Failed/Partial เดิมยังคงตามหลักฐานเดิม.

แกนเวลา 2026-10-13: แก้ tick label ที่เคยแสดงวันเวลาเต็มทุกขีดจนทับกัน
ให้ใช้เวลาสั้น/วัน/เดือน/ปีตามชนิด tick ของ Lightweight Charts โดยแสดง
Asia/Bangkok; crosshair ยังอ่านวันเวลาเต็ม. Targeted renderer tests 11/11,
type-check และ ESLint ผ่าน; build/restart frontend สำเร็จ.

แถบค่าแท่งเทียนบนกราฟ 2026-10-13: ใช้ O/H/L/C แบบกระชับบน chart จาก
exact candle cache; คั่นหลักพันในข้อความโดยไม่แปลงราคาเป็น Number หรือปัดค่า.
Crosshair แสดงแท่งที่ชี้ และกลับแท่งล่าสุดเมื่อออกจากแท่ง; แผงรายละเอียดเดิม
ยังแสดง exact OHLCV/indicator และ finality เต็ม. Targeted component/renderer/
MarketValue tests 25/25, type-check และ ESLint ผ่าน. ไม่เพิ่ม bid/ask หรือคำสั่งซื้อขาย.

ก่อน Completed/release ทุก V ด้านล่างต้องมีหลักฐานและผ่าน
ไม่ใช้การอนุมัติ spec หรือ smoke แทนผลทดสอบชุดเต็ม.
ก่อน merge ต้องผ่านด่านความถูกต้อง/ความปลอดภัยและ V-18 ที่ไม่เลื่อนตามมาตรฐาน.
จุดเข้า/ออกจริงไม่เป็นด่านรอบนี้ตาม NC-40 แต่ติดตามใน roadmap ต่อไป.
F-12 ไม่รับรอง production PREPARED หรือ Live readiness แทน F-11/ชุด9.

| รหัส | เกณฑ์ / วิธีตรวจ | Requirements | ผล |
|---|---|---|---|
| V-01 | Public contract/fixture, adapter partial ordering และ dependency/license checks ตามรายละเอียดด้านล่าง | 2/9/22/25/26 | Partial |
| V-02 | Parser/feed state properties: หน่วย/UTC/รูปร่าง/ordering/conflict/duplicate/reconnect/epoch | 2/3/9/25/26 | Partial |
| V-03 | Bundle OHLC/indicator อ่าน snapshotเดียวและค่าตรง F-11 แบบ LEGACY/PREPARED | 3/6/7/9 | Partial |
| V-04 | Proof ครอบ seed/gap/finality/retention/DDL; CHANGED/UNKNOWN ไม่มี overlay/tooltip | 7/8/11 | Partial |
| V-05 | Cursor/display proof tamper/MAC/purpose/session/expiry/cross replica;ไม่มี token log | 7/11/17/19 | Partial |
| V-06 | Budget/abort/timeout cleanup, no partial bundle; endpoint F-11 เดิมไม่เปลี่ยน | 10/11/16/18 | Partial |
| V-07 | Actual-role migration/grants/lease/fenced preview≤60 rows และ rollback | 1/17/23/25 | Partial |
| V-08 | Internal demand coalescing กับ F-09 users/worker; end boundary/fetch proof/commit | 9/12/13/25/28 | Partial |
| V-09 | Freshness/recovery/Restart/Redis failure/slowconsumer/control limits | 14/15/25/26/27 | Partial |
| V-10 | Auth/CSRF/routingไม่ต่อ session/machine/hidden/401/unsupported input | 1/2/18/19/23 | Partial |
| V-11 | Readiness/refresh controller finite state และเงื่อนไข retry/stop | 11/12/13/16/18/28 | Partial |
| V-12 | Exact text/numeric boundary/renderer whitespace/continuoussegments | 3/5/7/8/17/21 | Partial |
| V-13 | Viewport/page load/history cap/series switch/late response/StrictMode cleanup | 2/5/10/18/20 | Partial |
| V-14 | จริงใน Chromium: chart/panes/crosshair/keyboard/resize/ไทยอังกฤษ/attribution | 4/5/6/20/21/22 | Passed — automated Chromium ครอบ renderer/keyboard/resize/attribution และเจ้าของตรวจ Chart จริงบน development stack ผ่านวันที่ 2026-10-22 |
| V-15 | Browser→API→PG→fake venue worker→bundle/preview/refresh ครบทาง ไม่ mock APIทั้ง flow | 1/3/7/12/13/25/27/28 | Partial |
| V-16 | ภาพ/ข้อความ loading/empty/partial/unconfirmed/stale/failure แยก และไม่มี trading action | 8/9/14/15/23/24 | Partial |
| V-17 | วัดทรัพยากร/latency/budgets ตาม workload ที่กำหนด ไม่มี starvation จาก chart | 10/16/18/25/27/28 | Pending Full Validation |
| V-18 | ด่าน CI/full regression/security/architecture/generated API/build + review/manualผ่าน | ทุกข้อ | Partial — owner manual, static/import, frontend 246 tests/build, generated contracts และ clean-state full backend `3017 passed, 1 skipped, 2 deselected` ผ่าน 2026-10-22 หลังแก้ migration 0030 downgrade ตาม scope ที่เจ้าของอนุมัติ; branch ยังไม่ commit/push/CI และส่วนที่พึ่ง V-17 ยังค้าง |

ผล Partial อ้างอิง [หลักฐานหลัง merge](evidence/2026-10-14-post-merge.md),
[สรุปผลและรายการค้างเดิม](evidence/checkpoint.md),
[รายงาน local preview รอบก่อน](evidence/dev-preview.md) และ snapshot ที่ระบุในรายงาน
ยังไม่ถือว่าผ่านทั้งด่าน; V-17 และเกณฑ์ที่ยังขาดต้องตรวจครบตามระยะรันด้านล่าง

## ระยะรัน — เจ้าของอนุมัติปรับ workflow 2026-10-12

ที่มา: คำสั่งเจ้าของ “Defer full performance validation to release checkpoints”
และ “Record deferred criteria as Pending Full Validation” ในรอบปรับ workflow.
การอนุมัตินี้เปลี่ยนเวลารัน ไม่เปลี่ยน requirements/plan หรือเกณฑ์รับรองผล.

| ระยะ | เกณฑ์ที่ตรวจ |
|---|---|
| ระหว่างพัฒนา | V-01..16 ตามผลกระทบของ code/dependencies รวม correctness/security/concurrency และ smoke ของ bounds/cleanup/recovery ที่จำเป็น |
| Candidate ก่อน merge | V-01..16 ครบพร้อม review/manual ที่กำหนด และ full regression/static/build/contracts/required CI ใน V-18 เมื่อโค้ดนิ่ง |
| Release checkpoint / ชุดที่ 9 | V-17 ชุดเต็มทั้ง LEGACY/PREPARED และส่วนสรุปผล V-18 ที่พึ่ง V-17 ก่อน Completed/production activation/ใช้เงินจริง/เปิดให้คนนอก |

V-17 เป็น `Pending Full Validation` จนรันครบ workload/ระยะเวลา/thresholds เดิม.
หากพบความเสี่ยงจากการเปลี่ยนแปลงที่ smoke พิสูจน์ไม่ได้ ให้ตรวจส่วนที่จำเป็นเร็วขึ้น
ตาม `standards/testing.md` หัวข้อ 7 โดยไม่เลื่อน correctness/trading safety ตาม benchmark.
เก็บ Failed/Partial เดิมและหลักฐานไว้ ไม่ใช้สถานะ Pending กลบผลที่ล้ม.
ทะเบียนงานค้าง: [roadmap ชุดที่ 9](../../roadmap.md#ทะเบียนงานค้างสำหรับชุดที่-9).

## V-01: หลักฐานต้นทางก่อน implementation

- เก็บ raw public fixture จำกัดไม่เกิน2connections/60s รวม≤100frames/file
  สำหรับคู่อย่างน้อย BTC/ETH และ six intervals; ไม่ใช้ key ไม่ส่งออเดอร์.
  บันทึก request/subscription, ack, UTC/timeouts/counters และ raw decimal strings.
- รอบที่เก็บ x=true ถ้าสังเกตไม่ได้ให้ระบุ Not Observed ใช้ synthetic fixture
  ทดสอบ path โดยไม่อ้างว่า source CLOSED ถูกพิสูจน์. รอบนี้ history ยังคง UNCONFIRMED.
- ตรวจ undocumented fields/absence, combined envelope, inclusive end, progress
  และเหตุที่ไม่ใช้ E เป็น total order. If actual observation ขัด acceptance rule
  ต้องแก้ Proposed plan/ขออนุมัติใหม่ก่อน decoder ห้าม relaxparserเอง.
- ตรวจรุ่น Lightweight Charts5.0.9 จาก official package/release/license จริง
  pin exact lockfile; React18/Vite6/Node22 buildผ่านก่อนรับdependency.
  ตรวจ panes API/whitespace behavior ด้วย real library ไม่ผ่าน mockอย่างเดียว.

## Fixtures / properties ที่จำเป็น

Fixture เงิน/ปริมาณเป็น string และ timestamps explicit ไม่ใช้ค่าตลาดจริงเป็นสูตรอ้างอิง.
ตัวอย่าง OHLC: open=100.000000000000000001, high=101.000000000000000001,
low=99.000000000000000001, close=100.500000000000000001,
volume=2.000000000000000001; tooltipต้องอ่านข้อความเดิมทุกหลัก.
วาดเป็น approximation ได้ตาม NC-41 แต่ exact cache ต้องไม่ถูกเปลี่ยน.
เพิ่ม underflow/overflow, zero/negative Scalar ที่ validตามF-11 และหน่วยต่างกัน.
ไม่เอา validator ของ renderer มาใช้สร้าง expected values.

V-02 ใช้ Hypothesis ใน Pythonสร้าง sequences ที่ valid/invalid:
duplicateไม่เปลี่ยน revision, frameเก่าไม่ทับใหม่, sameprogress/conflictingOHLC
ทำให้ไม่พร้อม, epochเก่าหลังreconnect/leasehandoffไม่publish,
unknownseries/boolแทนint/endalignment/invalidunit/malformeddecimal failclosed.
ทดสอบกฎ dominance โดยสร้างลำดับคงที่แล้วสับ/ซ้ำ และพิสูจน์ว่าไม่มีการเลือก
conflictด้วย timestamp/arrival. ไม่เพิ่มกฎ monetary range ใหม่.

V-03/04 ใช้ PostgreSQL snapshot barriers จริงกับ rolesจริง:
- writercommitก่อน/ระหว่าง/หลังbundle; bundleหนึ่งหน้าเป็นชุดเดียวครบ
  และ values/statusตรง F-11 parity reference เดิม ทั้งสอง mode.
- เปลี่ยน seedก่อนviewport, backfillgap, finality/fetch_started_at,
  เปลี่ยน OHLC ใน output, source reset, journalGC, generationexpiry และcleanup
  ต้อง CHANGED/UNVERIFIABLE ไม่ได้ค่ารุ่นใหม่แทรกเข้า tokenเก่า.
- แท่งที่อยู่นอก [L,U) ไม่เปลี่ยนค่าหรือ invalidates historyที่ยังพิสูจน์ได้;
  การเลื่อน cutoff/partitionมีผลตามF-11เดิม ไม่ reseedเพื่อให้ตรวจผ่าน.
- LEGACYตรวจrevisionเต็มด้วยreaderเดิม; ไม่เปิดgate PREPAREDในtestเพื่อหลบfallback.
  PREPAREDใช้generation/checkpoint/sourcejournalจริง ไม่stub proof_valid.
- multi-page 409 หลังมีหน้าสะสมต้องทิ้งทุกหน้า; ไม่มี candleหน้าใหม่ทับเส้นเก่า.

## V-05..10: Backend integrity

- Tokenคนละpurposeต้องใช้แทนกันไม่ได้; loginคนเดิมต่างsession, userอื่น,
  current/previous kid, invalid/retired kid, whitespace/oversize/MACผิด,
  expiryตรงขอบ6h/session/generation ตรวจแบบ frozen DBtime; errorไม่echo input.
- cancellationระหว่าง scan/source query/serialization และ repeated cancel
  cleanup≤2s/connectioninvalidate; slotยังheldจนงานหยุดจริง พิสูจน์reuseได้.
  response2MiBพอดี/เกิน และ input1000/1001slots; ไม่มี partial arrayเมื่อผิดพลาด.
- preview ownerสองตัวแข่ง, leaseหมด, ownerเก่ากลับช้า, commitrollback,
  Redis lost publish และ restart. actorเก่าไม่มีwriteจากepochที่หมดสิทธิ์.
  actualAPIเขียนpreviewไม่ได้; rolesอื่น/secret/audit/orderไม่มีgrantเพิ่ม.
- demandอัตโนมัติ+user requestช่วงเดียวกันมีjob/workerleaseเดิม;
  ไม่resetactivecursor/attempt/backoff; transactionrollbackไม่ประกาศสำเร็จ.
  RESTfetchเริ่มก่อนend_atแม้ตอบหลังยังไม่ผ่าน; หลังend_atcommitแล้วจึงเข้าF-11.
- stream xtrueไม่สร้างCLOSED, previewไม่เข้าตารางsourceF-11;
  ไม่มี financialfloatingpoint ในbackend/DB/newparser.
- freshness6sตรงขอบ/เกิน1µs, eventอนาคต2sตรงขอบ/เกิน, frameค้าง,
  heartbeatโดยไม่มีข้อมูล, Eเก่าแต่receivedใหม่; statusesอิงsnapshotserver.
  เวลาในbrowserถูกปรับ±1hต้องไม่เปลี่ยนfinality/READYของserver.
- REST/backfillล้ม recoveryต้องไม่READY;
  latestslots/coalescing/backpressure ไม่ทำให้queueโตตามframecount.
- แยก Redis failure สองกรณี: (1) notification/invalidation หายหรือ publish
  ล้มหลัง commit แต่ admission ยังใช้ได้ ให้ Live GET อ่าน preview ล่าสุดจาก PG
  ได้; ไม่ rollback commit หรือเปลี่ยน feed readiness เพียงเพราะ notification หาย.
  (2) admission timeout/Redis ใช้งานไม่ได้ รวม Redis ล่มทั้งระบบ ให้ Live GET
  คืน503 CHART_ADMISSION_UNAVAILABLE โดยไม่เรียก preview reader/ไม่ bypass
  admission/ไม่ใช้ local counter; browser หยุด auto poll และไม่เริ่ม readiness
  episode. History/verify ต้องคง admission/error contract ของ F-11 เดิม.
- no-session/expired/revoked, POSTverifyขาดCSRF/invalidorigin,
  machine GET/POSTทั้งหมดไม่ต่อexpiry; manualF-09POSTคงroutingเดิม.
  testsenumerate routepolicyเพื่อจับ endpointใหม่ที่เผลอpublic/renewing.

## V-11..16: Controller และ browser

Staged-history amendment (RQ-3/5/7/10/18):

- ทั้ง initial mount และเปลี่ยน TF: delay coherent history อย่างควบคุมแล้วให้ candle-only
  สำเร็จก่อน; ต้องวาด candles/อ่านข้อความ exact ได้ก่อนปล่อย history response และไม่มี
  indicator series/tooltip จนผ่าน proof. ใช้ controlled response order ไม่ตั้ง latency SLA จาก sample.
- ยืนยัน candle-only เริ่มโดยไม่รอ history cleanup 2s; StrictMode ไม่ซ้อนงาน,
  timeout10s/2MiB/1000rows/identity ถูกบังคับก่อน cache; ไม่มี implicit retry/POST.
- COVERAGE incomplete/unavailable, gaps, zero-volume, empty, error และ finality แสดงจริง.
  Candle-only failure ไม่ยกเลิก coherent read; 401 ไม่คงข้อมูลผู้ใช้เดิม.
- Live ซ้ำ open-time กับ provisional candle ให้เห็นเพียงแท่งเดียว; exact source ไม่ถูกแก้.
  เมื่อ bundle มี correction/different OHLC ต้องแทนทั้งชุดก่อนแสดง indicator;
  ไม่แสดง hybrid history/indicator และไม่ย้อนกลับ provisional เมื่อ bundle refetch/error.
- Candle-only response หลัง bundle/หลัง A→B→A/หลัง retry หรือ logout ถูกกัน;
  cancellation ครบใน hidden/unmount/session lifecycle ตาม controller policy.
- Browser smoke ทั้ง login→default และ 1h→1m: หน่วง history แล้วแสดงกราฟจาก candle-only
  ก่อน history พร้อม; จากนั้นตรวจ coherent handoff และไม่มี page error.
  บันทึกเวลาสองช่วงแยกกัน (first historical candles / coherent indicators) โดยไม่อ้างว่า
  ทดสอบ capacity หรือรับรอง PREPARED แล้ว.

ใช้ fake timers ที่ monotonic + controlled HTTP delays ตรวจ actual query calls:
- initial503notready→poll≥10s/Retry-After→200bundleที่MATCH แสดงได้;
  initial503busy→poll≥2s/Retry-After โดยไม่ซ้อน request และยังอยู่ในงบ12ครั้ง/300s→200bundleแสดงได้;
  amendment อนุมัติ 2026-10-13: initial/idle TF switch เริ่ม history ทันที;
  ยกเลิก history/proof ที่กำลัง fetch ต้องรอ cleanup 2s, เปลี่ยน TF ซ้ำต้องรักษา deadline
  ที่เหลือ, StrictMode ไม่ส่งซ้ำและ late response ไม่เขียนทับ episode ใหม่.
  503รหัสอื่น/429/504/422หยุด ไม่มีrefetchจากfocus/networkมาเปิดงานเอง.
- episodeรวม12คำขอ/300sตรงขอบ; request30sและลดdeadlineตามremaining;
  คำขอช้ากับevent100ครั้งไม่resetbudgetและไม่ส่งrequestซ้อน.
- 409จากหน้าถัดไปหรือexpiryได้restartเพียง1ครั้งทั้งepisode;
  numericfailureต่อด้วยeventรุ่นเดิมไม่retry; token/codeต่างกันไม่เพิ่มrestartquota.
- exhaustedepisode+streamใหม่ยังstopped; manualtryใช้admission/cooldown;
  successfulREFRESH_REQUIREDจบรอบโดยไม่มีPOSTหรือreadinessloopต่อ.
- POST202→pollF-09ไม่เกิน6ครั้ง/60s→bundle; POST200อ่านbundleใหม่;
  FAILED/UNAVAILABLE/pollerror/401/timeoutหยุด ไม่มีค่าค้างอ้างว่าล่าสุด.
- proofเปลี่ยน/UNKNOWN/TTL45s ต้องไม่มีindicatorseriesและtooltipเก่า;
  OHLCของbundleยังผูกas_ofชัด; livepreviewoutsideUไม่invalidateshistoryเอง.
- switch A→B→A/delayedA, unmount, hidden→visible, logout/remount,
  StrictMode doubleeffect; stalecallbackไม่เขียนcache/render.
- 12,000slotscap: pagination/evictionรักษาviewportและseed; เปิดช่วงเก่าได้ใหม่
  ไม่เดาว่าข้อมูลตลาดหมดเพราะbrowsercacheevict.
- realchartอ่านexacttextกับapproximateaxisถูกต้องและไม่มี Volume pane; Gaps/WARM_UP/
  REFRESH_REQUIREDไม่ลากเส้นเชื่อม; ค่า volume แบบข้อความแยก zero จริงจาก missing.
- widths375/768/1440และthemeเดิม, pane scale/legend/keyboardlabels/ThaiEnglish,
  timezoneขอบวันUTC→Bangkok, attribution/logo/linkไม่ถูกUIทับ.

E2Eขั้นต่ำ 6 flows: (1) login→เลือกคู่/timeframe→chart+ราคาสด,
(2) previewupdate/แท่งใหม่→RESTcommit→indicatorbundle,
(3) seedmutation→hide→boundedrebuild, (4) refresh+gap+failure,
(5) network/Redis/workerrestart→recovery, (6) revoke/logout→stoprequests.
อย่างน้อยflows1/2/3/5ใช้DBจริงและFakeVenue/streamserverที่ควบคุมได้
ไม่mockGETchart/indicatorเพื่อแทนbackendทั้งflow. Fixturesmockเฉพาะfailure
ที่ต้องทดสอบclientและมีbackendintegrationแยกพิสูจน์สัญญาเดียวกัน.
Browser networkassertไม่มี Binance requests หรือ order/modechange endpoints.

## V-17: Workload / acceptance — Pending Full Validation ที่ release checkpoint

สภาพแวดล้อม Linux2vCPU/1GiB สำหรับAPI/market-data ตามฐานF-11,
PG/RedisแยกตามComposeเดิม; ChromiumNode22 บันทึกversion/seed/digest.
รันisolatedไม่ใช้ตลาดจริง 10นาทีหลังwarmup60s:
30candle series, 15events/sปกติและburst150events/s10sทุกนาที,
20authenticatedclientsมีlivepoll2s, 5clientsสลับhistoryทุก30s
และproofตาม15s; 5seriesมีsourcecommit/seedmutation/gaps/failedrefresh.

| เกณฑ์ | วิธีตัดสิน |
|---|---|
| Previewreceive→PGcommit | p95≤3s; requestsourceevent→browsertext p95≤5sในcontrollednetwork; ไม่เอาระยะeventproductionต้นทางมาปน |
| LiveGET | p95≤500ms, max≤2sหรือtypedtimeout; slowqueryไม่แย่งF-11pool |
| Queues/rows | preview≤60rows, processqueueslatest≤30series; browser≤12,000slotsและไม่มีgrowthหลัง100mount/unmount |
| Resource | market-data/API incrementalRSSรวมแต่ละprocess≤128MiB, no leakedconnections/listeners/slotsหลังcancel |
| History/proof | ทุกคำขอ≤30sหรือtypedfailureและไม่มีpartial; preparedready workload history p95≤3s; LEGACY1,000sourcefixtureต้องสำเร็จใน30sและsame-snapshotถูกต้อง |
| Starvation | F-10 snapshot/controlและF-09 activejobsยังprogress; sourcewritesไม่blockedเกินtimeoutsเดิม; burstไม่สร้างfeedconnectionต่อuser |
| Max-input correctness | ใช้F-11fixture525,600slotsเดิมตรวจnoout-of-bounds/noallocationallrows/timeoutcleanup; ไม่อ้างว่าปิดcapacity/loadgateF-11จากผลนี้ |

วัด LEGACY/PREPAREDแยก; PREPAREDใช้จริงในisolatedDBพร้อมrolloutinventory/evidence
ไม่activateproduction. เลื่อนเวลารันตามการอนุมัติ workflow ข้างต้นเท่านั้น
ห้ามลดเกณฑ์ ลบผลที่ล้ม หรือใช้ smoke รับรองว่าผ่าน V-17.
ถ้าLEGACYmaxinputอ่านไม่ได้ในงบ ให้แสดงข้อจำกัดตามจริงและติดตามในผล ไม่เรียก
ว่าavailabilityพร้อมครบ365วัน; ต้องเสนอวิธีแก้/ขอคำตัดสินก่อนรับรองพร้อมใช้งานจริง.

## ตรวจด้วยมือและด่านก่อนส่งงาน

รายการด้านล่างเป็นด่าน candidate ก่อน merge ไม่ใช่คำสั่งให้รันครบหลังทุก patch/ทุกงาน
ระหว่างพัฒนาเลือกตามผลกระทบ และใช้ผลเดิมได้เฉพาะเมื่อ inputs ที่เกี่ยวข้องยัง valid.
V-17 และส่วนสรุป V-18 ที่พึ่งรอบนั้นรอ release checkpoint ตามตารางระยะรัน.

เจ้าของตรวจchartจริงผ่านdevenvironmentพร้อมfixture: viewport/เลือกแท่ง/ทุกpane,
ทั้งภาษา/มือถือ, disconnect/stale/unconfirmed, refresh/stopและไม่มีtradingaction.
เก็บ screenshot/time/environment/failure ตามจริง ไม่ใช้mockupเป็นหลักฐานผ่าน.
ผลแต่ละVต้องระบุคำสั่ง/exitcode/artifactpath; failed/partialไม่เปลี่ยนเป็นpassed.

ผล Owner Manual Acceptance: **Passed 2026-10-22** — เจ้าของตรวจหน้า Chart จริงบน
development stack แล้วตอบยืนยันว่า “ตรวจแล้วผ่าน”; ใช้ร่วมกับ automated Chromium/network
evidence ในรายงานวันที่เดียวกัน. ผลนี้ไม่เปลี่ยน V-17 หรือ release-gate status.

Backend: `uv sync --frozen`, `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy`, `uv run lint-imports`, `uv run pytest` พร้อมPG/Redisจริง.
Frontend: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`,
`npm run build`, `npm run test:e2e` ตามCIจริง.
Export `uv run python -m tiewtrade.services.api.openapi_export`,
`npm run gen:api` แล้วตรวจgenerateddiffว่าตรงcommitก่อนmerge.
venue_contractแยกจากเทสต์ปกติ ไม่มีkeyและใช้boundedpublicrequestsเท่านั้น.
review/finalcheckต้องผ่านแล้วจึงอัปเดตroadmapตามผลจริง;
commit/push/mergeยังต้องเจ้าของสั่งแยกต่างหาก.
# Calendar history batch follow-up — 2026-10-14

Approved scope: [calendar-history-batch-amendment.md](calendar-history-batch-amendment.md).
The calendar one-slot request expectation is superseded by bounded start-only
requests; fixed-timeframe seven-day limits remain unchanged. Validation covers
native batches, invalid response bounds/order, legacy in-flight requests, sparse
page repair, durable progress, fencing, rollback and existing retry budgets.
Results: [calendar batch evidence](evidence/2026-10-14-calendar-batch.md).
Full regression and workload acceptance retain their existing pending status.
