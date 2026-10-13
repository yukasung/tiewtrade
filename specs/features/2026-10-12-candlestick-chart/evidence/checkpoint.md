# F-12 — Test and local-preview checkpoint

วันที่: 2026-10-12 (Asia/Bangkok)
สถานะผลตรวจ: **Partial — ยังไม่พร้อมรับรอง Completed หรือ merge**

รายงานนี้รวบรวมหลักฐานที่มีอยู่ ไม่ได้รัน tests, build หรือ benchmarks เพิ่มในรอบจัดทำเอกสาร
และไม่เปลี่ยนเกณฑ์ตรวจรับใน requirements/plan/validation. โค้ดยังเป็น working tree
ที่ไม่ได้ commit; หลักฐานต่างรอบไม่ถือเป็นผลทดสอบโค้ดฉบับเดียวกันทั้งหมดโดยอัตโนมัติ.

## ผลทดสอบที่มีแล้ว

| ชุดตรวจ | วิธีรัน / environment ที่ใช้ในรอบเดิม | ผลและขอบเขต |
|---|---|---|
| Backend full candidate | Linux Python 3.12, PG/Redis แยกสำหรับ tests; `run_backend.py pytest` | [backend-candidate.xml](backend-candidate.xml): **2,578 passed, 1 failed, 1 skipped**; ยังไม่ใช่ full run ที่เขียวทั้งหมด และไม่ได้รวม tests ที่เพิ่มหลังเริ่มรอบนี้ |
| Redis admission และ response boundary หลังแก้ | environment เดิม; เลือก `tests/infra/realtime/test_admission.py` และ `tests/services/api/test_chart_response_boundary.py` ผ่าน `run_backend.py pytest` | [candidate-followup.xml](candidate-followup.xml): **7 passed**; ครอบคลุม Redis fail-closed/timeout/quota และ body 2 MiB/cancellation cleanup |
| Proof fault matrix | เลือก `tests/api/test_chart_routes.py` เฉพาะ fault matrix ผ่าน `run_backend.py pytest` | [proof-faults.xml](proof-faults.xml): **6 passed, 1 failed** จาก fixture expiry ที่ผิด constraint; แก้ fixture ใช้ generation `EXPIRED` และตรวจกรณีนั้นผ่านใน [proof-expiry-fixed.xml](proof-expiry-fixed.xml): **1 passed**. ไม่อ้างว่าเป็น all-green run เดียวกัน |
| Migration/roles/gates | Linux, disposable PG/Redis; migration, roles และ gates ผ่าน `run_backend.py pytest` | [chart-enable-gates.xml](chart-enable-gates.xml): **60 passed**, เป็นหลักฐานรอบก่อน candidate |
| Integrity / lifecycle | selected backend modules ผ่าน `run_backend.py pytest` | [chart-integrity-tests.xml](chart-integrity-tests.xml): **18 passed**; [preview-lifecycle-tests.xml](preview-lifecycle-tests.xml): **9 passed**, เป็นหลักฐานรอบก่อน candidate |
| Frontend full candidate | Linux Node 22; Vitest full run | [frontend-candidate.xml](frontend-candidate.xml): **192 passed / 20 files**, exit 0; ก่อนเพิ่ม tests สถานะหน้า chart สามข้อ |
| Frontend หลังแก้ล่าสุด | Host Node 22; Vitest เฉพาะ panel, controller, read episode, API และ renderer | **37 passed / 5 files**, exit 0 ตาม terminal รอบก่อน; ไม่มี JUnit artifact แยกของรอบนี้ จึงไม่แทน full candidate XML |
| Browser integration | Node 22 / Chromium; `run_browser.py NODE22 --reporter=list,junit`, isolated E2E DB และ controlled workers | [chart-functional-checkpoint.xml](chart-functional-checkpoint.xml): **7 passed**, ครอบคลุม login/series switch, preview→REST→bundle, proof mutation, gap/refresh/failure, disconnect/restart และ logout. รันก่อน frontend guards/status ล่าสุด; ยังไม่รับรอง E2E โค้ดล่าสุดทุก flow |
| Static / build / generated contract | Ruff/format/mypy/import boundaries; frontend lint/types/Vite build บน Node 22; OpenAPI export | รอบก่อนบันทึก exit 0 ใน terminal; [openapi-candidate.json](openapi-candidate.json) hash ตรง backend/openapi.json ณ รอบ export. ยังต้องตรวจ generated frontend types และ exact candidate/CI ให้ครบก่อน merge |

### ผลล้มและข้ามที่ต้องรักษาไว้

- Backend full run ล้ม `test_actual_redis_atomic_limits_and_bounded_keys`:
  การเปิด connections จำนวนมากจาก pool ที่ยังไม่อุ่นทำให้บางคำขอเกิน admission timeout.
  แก้ setup ของ test ให้เตรียม connections ก่อนตรวจ atomic quota โดยคง timeout 500 ms,
  จำนวนคำขอ, quota และ fail-closed assertions เดิม; targeted follow-up ผ่าน.
  ไม่ได้แก้ production admission และผลนี้ไม่พิสูจน์ latency ภายใต้ workload ของ V-17.
- Backend ข้าม `test_compose_resolves_to_the_pinned_image` เพราะ container ทดสอบไม่มี
  Docker CLI; ยังต้องตรวจใน environment ที่มี Docker ก่อนปิดด่านนี้.
- Proof expiry ล้มเพราะ fixture ละเมิด constraint ของ generation; ใช้ `EXPIRED`
  เพื่อทดสอบ `UNVERIFIABLE` โดยไม่เปลี่ยน TTL/constraint ใน production.
- เก็บ failed/diagnostic artifacts เดิมทั้งหมด; targeted pass ไม่เปลี่ยนสถานะ full XML เดิม.

## ตรวจ frontend ที่ deploy บน localhost ล่าสุด

- Build: `docker compose --env-file config/postgres.env build frontend` — exit 0.
- Restart: `docker compose --env-file config/postgres.env -f compose.yaml -f compose.chart.dev.yaml up --no-deps --no-build -d frontend` — exit 0; recreate เฉพาะ frontend.
- Image manifest: `sha256:1c338ef6fbdc0f98e32060d9878efcbb00b401f37327f8de3317965639782735`.
- Chromium ที่ `http://localhost:5173/`, viewport 1440×1000:
  สมัครบัญชี smoke แยกด้วยข้อมูลสุ่ม (ไม่ใช้บัญชีเจ้าของ); chart visible,
  canvas 11 ชิ้น, history HTTP 200 มี indicator rows 1,000, ไม่มี JavaScript pageerror.
  บัญชี smoke ที่สร้างยังอยู่ใน development DB; ไม่ส่งออเดอร์หรือเปลี่ยน trading mode.
- [ภาพ chart ล่าสุด](frontend-latest-chart.png): renderer วาดแท่ง preview/volume ได้
  แต่ประวัติแสดง EMPTY และท่อแท่งสดแสดง STALE พร้อม `ORDER_UNCONFIRMED`.
  Indicator rows 1,000 **ไม่ใช่** หลักฐานว่ามี historical OHLC candles 1,000 แท่ง.
  ผล smoke นี้พิสูจน์การ mount/render บนเว็บล่าสุด ไม่พิสูจน์ historical availability
  หรือ feed readiness; สาเหตุข้อมูลประวัติว่าง/preview เก่ายังไม่ได้วินิจฉัย.

## Coverage และรายการค้าง

ตารางนี้เป็น mapping ของหลักฐาน ไม่ใช่รายการย่อยที่ตรวจครบทั้งหมด;
เกณฑ์ฉบับเต็มยังอยู่ใน [validation.md](../validation.md).

| เกณฑ์ | หลักฐานที่มี | งานค้าง / ข้อจำกัด |
|---|---|---|
| V-01..02 | public capture/ordering, parser และ lifecycle/property tests; Node 22 build, real chart browser | public `x=true` ไม่พบใน capture; synthetic closure ต้องอ้างอิง test ที่ตรงเกณฑ์ ไม่อ้าง public capture แทน. ตรวจ mapping ของ properties/dependency ทุกข้อก่อน Passed |
| V-03..05 | chart bundle/proof integration, snapshot barriers, HMAC purpose/session tests, fault matrix | ตรวจ mapping ให้ครบกรณี seed/gap/finality/retention/DDL/session/expiry ทั้งสอง mode; ผูกหลักฐานกับ inputs สุดท้าย |
| V-06..08 | boundary/cancel tests, migration/roles, fencing/rollback, demand coalescing และ browser REST repair | ยังไม่รับรองทุก timeout/cancel/end-boundary case ด้วยชื่อกลุ่ม tests อย่างเดียว; ตรวจ case mapping และ Docker version-pin ที่ข้าม |
| V-09..10 | freshness boundaries, Redis fail-closed/fencing, auth/CSRF/routing tests; browser recovery/logout | วินิจฉัย STALE/ORDER_UNCONFIRMED บน local preview; ตรวจ revoked/expired session และ remaining control/recovery cases ตามเกณฑ์ |
| V-11..13 | 37 focused frontend tests รวม read budgets/stop/refresh, exact renderer, late response/visibility/proof guards | ตรวจ pagination/eviction/viewport ที่ cap 12,000 slots และกรณี controller ที่ยังไม่มี mapping; targeted pass ไม่แทน coverage ทั้งเกณฑ์ |
| V-14..16 | real Chromium 7 stories รอบก่อน; latest local smoke/screenshot; panel loading/empty/stop tests | E2E เดิมก่อน guards/status ล่าสุด; owner manual ยังไม่ตรวจครบ viewport/panes/language/mobile/stale/refresh/stop. ประวัติบน local ยังว่าง |
| V-17 | bounds smoke เท่านั้น | **Pending Full Validation**: workload/resource/latency ทั้ง LEGACY/PREPARED ตาม thresholds เดิมที่ release checkpoint/ชุดที่ 9 |
| V-18 | full candidate artifacts, targeted follow-ups, static/build/OpenAPI หลักฐานเดิม | final review และการตรวจ diff/coverage/input validity; frontend generated contract comparison; host Docker check; owner manual; required CI ของ commit สุดท้ายยังค้าง. ส่วนที่พึ่ง V-17 ยัง Pending Full Validation |

## ลำดับงานต่อไป

1. ตรวจสาเหตุประวัติ candles ว่างและ preview STALE บน development stack ด้วย
   read-only checks ที่จุดข้อมูลที่เกี่ยวข้องก่อน; ไม่ restart/migrate ทั้ง stack โดยไม่มีเหตุ.
2. ทำ coverage mapping ของกรณีค้างให้ครบ แล้วเลือก checks ตามผลกระทบจริง.
   ใช้ผลสำเร็จเดิมเมื่อ inputs ยัง valid; ถ้าแก้โค้ด ให้รันเฉพาะ checks ที่ถูกกระทบก่อน.
   ไม่รัน full suite ซ้ำเพียงเพราะจัดทำรายงานหรือพบ failed artifact ที่มี targeted fix แล้ว.
3. Owner ตรวจ UI; ปิด review/generated contract/host check ที่ยังค้างเมื่อ candidate นิ่ง.
   Commit/push/merge ต้องเจ้าของสั่งแยก; CI ที่ยังไม่รันห้ามนับว่าผ่าน.

F-12 คง **In Progress**. รายงานนี้ไม่อนุมัติ merge, production PREPARED หรือ Live Trading.

## Trading Workspace layout — 2026-10-14

- Targeted frontend tests: `CandlestickChartPanel`, `AccountNavigation` และ `chart-renderer` ผ่าน **35 tests / 3 files**.
- Frontend type-check และ scoped ESLint ของไฟล์ที่แก้ผ่าน (exit 0).
- Authenticated Chromium smoke ที่ 1440, 1280, 768 และ 390px ยืนยันว่า desktop แบ่ง chart/order และ mobile เรียง market→chart→order→history โดยไม่มี horizontal overflow.
- Placeholder controls ถูก disabled ทั้งหมดและ request log หลังเข้า Chart ไม่มี POST/PUT/PATCH/DELETE; ไม่มี form action, balance, ราคา, จำนวน หรือ order/trade จำลอง.
- ภาพหลักฐาน: [desktop](workspace-desktop.png) และ [mobile](workspace-mobile.png).
- Automated computed-style state matrix ของ TW-07 ยังไม่ครบ จึงคงผล **Partial**; เกณฑ์ V-01..V-18 และ Pending Full Validation เดิมไม่เปลี่ยน.
- ปรับ desktop workspace ให้สูงพอดีกับพื้นที่ใต้ header: ที่ 1440×1000 ได้ workspace 923px,
  chart 347.02px และ history 433.80px; ที่ 1280×900 ได้ workspace 823px, chart 302.58px
  และ history 378.23px. ทั้งสอง viewport มี `scrollHeight === innerHeight` และไม่มี page scrollbar.
- ที่ mobile 390×844 คงการเรียงแนวตั้งและ page scroll ตาม responsive requirement; browser smoke ไม่พบ page error.
- Market bar หลังย่อสูง 65px ที่ desktop, ไม่แสดง `กราฟแท่งเทียน`, `คู่เทรด` หรือ `Timeframe`;
  pair/TF Select ยังคง accessible names เดิม. Targeted component tests **19 passed**, type-check และ scoped ESLint ผ่าน.
- เปลี่ยน order/history tabs เป็น underline pattern จาก Admin Template และย้าย history tabs ชิดซ้ายใน header.
  Chromium ยืนยัน chart bottom และ history top อยู่ที่ 523.44px เดียวกัน, tabs เริ่มภายใน history, ไม่ซ้อนแกนเวลา,
  ไม่มี page scrollbar และไม่พบ page error.
- เพิ่ม Light/Dark ThemeProvider และ toggle จาก Admin Template. Light ใช้ chart `rgb(255,255,255)`;
  Dark ใช้ page `rgb(12,17,29)`, surface/chart `rgb(16,24,40)` และค่าคงอยู่หลัง reload.
  ทั้งสองโหมดยังมี OHLC, ไม่มี page scrollbar; request log ระหว่าง toggle ว่างและไม่พบ page error.
  หลักฐาน: [Light](workspace-light.png) และ [Dark](workspace-dark.png). Targeted tests **40 passed / 3 files**,
  type-check และ scoped ESLint ผ่าน.
