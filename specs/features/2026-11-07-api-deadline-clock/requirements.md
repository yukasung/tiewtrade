# API deadline clock correctness — Requirements

สถานะ: **Approved — เจ้าของตอบ “อนุมัติ” วันที่ 2026-11-07**
วันที่: 2026-11-07
Branch: `fix/api-deadline-clock`
Base ที่ตรวจพบปัญหา: `f15596df0b1ced53107964a8ed9bb657fda9d336`

## ทำไมต้องมี

ระหว่างตรวจรับงานลบหน้า `/prices` พบ `/market-data/chart/live` ตอบ
504 `CHART_DEADLINE_EXCEEDED` ก่อนเริ่มอ่านฐานข้อมูล ทำให้ recovery flow ไม่ผ่าน
การเปรียบเทียบกับ main ที่ยังไม่แก้ไข ณ base เดียวกันล้มที่ READY assertion เช่นกัน

บนเครื่องตรวจ Python 3.12.15 + uvloop พบ loop.time() สูงกว่า time.monotonic()
ประมาณ 2103.989 วินาที การส่ง deadline จาก monotonic ไปยัง asyncio.timeout_at
จึงทำให้หมดเวลาทันที ไม่ใช่หลักฐานว่า Redis/DB ใช้เวลานาน
การใช้ standard asyncio ผ่าน config ชั่วคราวทำให้ flow READY → RECOVERING → READY
ผ่านใน 8.3 วินาทีโดยคง deadline และ assertions เดิม
ค่าความต่างนี้เป็นผลวัดเฉพาะ environment ไม่ใช่ค่าคงที่ที่นำไปชดเชยในโค้ดได้

เจ้าของสั่ง “เริ่มทำ” ให้จัดทำ spec แยก วันที่ 2026-11-07;
ต่อมาเจ้าของอนุมัติ requirements วันที่ 2026-11-07; plan/validation ได้รับอนุมัติแล้ววันที่ 2026-11-07

## ขอบเขต

แก้ความถูกต้องของ request deadline ใน `services/api/chart_routes.py` และ
`services/api/indicator_http.py` รวม consumers ที่ใช้ boundary นี้ ได้แก่
chart history/verify และ indicator HTTP reads ตรวจผลกระทบจาก admission,
การอ่านข้อมูล, serialization และ cancellation/cleanup

ไม่เปลี่ยน event-loop configuration เพื่อหลบปัญหา ไม่เพิ่ม dependency หรือ infrastructure
ไม่เปลี่ยน schema, migrations, API contract, trading engine หรือ exchange transport
ไม่ขยายเป็นการ refactor clock ทั้ง repository

ตรวจ timeout_at callers อื่นแล้ว: `venues/binance_th/stream_transport.py` และ
`services/indicator_builder/attempt.py` สร้าง deadline ด้วย event-loop clock อยู่แล้ว
จึงไม่อยู่ในขอบเขต source change ของงานนี้

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | API deadlines ต้องทำงานถูกต้องเมื่อ event-loop clock และ application monotonic clock มี origin ต่างกันทั้งบวกและลบ; ห้ามเกิด timeout ทันทีก่อนงบหมด หรือปล่อย request เกินงบเพราะนำ absolute timestamp ข้าม clock domain | ผล diagnostic และความถูกต้องของ timeout |
| RQ-02 | คงงบ chart live 2 วินาที และ indicator/shared response budget 30 วินาทีตาม settings เดิม; admission, work และ serialization ต้องใช้งบรวม ไม่เริ่มงบใหม่ระหว่างขั้น; คงการตรวจ elapsed time ของงาน synchronous และขอบเขตเท่ากับ deadline | chart_routes.py, indicator_settings.py, test_indicator_routes.py |
| RQ-03 | คง HTTP error codes และ response schema เดิม รวม CHART_DEADLINE_EXCEEDED / INDICATOR_DEADLINE_EXCEEDED, database timeout mapping, auth/session expiry, rate/resource limits และ cache-control | API contracts เดิม |
| RQ-04 | timeout, client disconnect และ external cancellation ต้องยุติและรอ cleanup งานลูก/DB ตาม semantics เดิม พร้อมคืน admission/budget resources; ไม่กลืน cancellation หรือเพิ่ม orphan background work | indicator_http.until_disconnect และ architecture/security |
| RQ-05 | คง data freshness/readiness, database clock, candle ordering/finality, exact prices และ session recheck; deadline fix ต้องไม่ทำให้ข้อมูล stale เป็น READY และไม่ทำให้ READY เป็นสิทธิ์ส่งออเดอร์ | trading-safety §6/12, F-12 |
| RQ-06 | ต้องมี regression ที่จำลอง clock-origin offset โดยไม่พึ่ง host sleep history พร้อมตรวจ success, timeout จริง, synchronous overrun และ cleanup; คง tests เดิมที่ยังเกี่ยวข้อง | testing standards; ช่องว่างที่ baseline tests ไม่พบ |
| RQ-07 | ยืนยัน chart recovery ด้วย real disposable PostgreSQL/Redis และ default Uvicorn loop selection บน environment ที่เกิดปัญหา; standard asyncio เป็นการตรวจความเข้ากันได้เพิ่มเติม ไม่ใช้แทน default-loop evidence | review diagnostic / Feature validation blocker |
| RQ-08 | งานลบ `/prices` คง V-03 Partial/Failed จน candidate ที่รวม fix ผ่านเกณฑ์ของงานนั้น; ผล fix แยกสาขาหรือผล temporary asyncio ไม่ทำให้ consumer feature Passed/Completed อัตโนมัติ | testing §7 |

## กฎความปลอดภัยและสถาปัตยกรรม

- ยึด `specs/standards/architecture.md`, `backend.md`, `security.md` และ `testing.md`
- ยึด trading-safety §1/2/4/6/12: ไม่ส่ง Live order ระหว่าง validation ไม่เปลี่ยน
  Paper/Live isolation, credential handling, retry/idempotency หรือ freshness rules
- ไม่เปลี่ยน Money/Quantity, order quantities, balances/positions, PnL, leverage,
  margin หรือ liquidation; ไม่แตะ transaction/locking ของการเทรด
- Session ยังคง PostgreSQL; ไม่เพิ่ม global persistent business/session state,
  Redis dependency หรือ sticky sessions; timeout state มีอายุเฉพาะ request
- การแก้ต้องรักษา injected-clock testability ของ shared indicator boundary
  โดยไม่ผูก API กับ origin ของ event-loop implementation ใด implementation หนึ่ง

## หลักฐานตั้งต้นและข้อจำกัด

หลักฐานต้นทางอยู่ใน worktree งานลบหน้า:
`specs/features/2026-11-07-remove-prices-page/evidence/`:
`review-followup.md`, `review-baseline-recovery.log`,
`review-live-boundary-trace.log`, `review-asyncio-recovery.log`.
เอกสารดังกล่าวยังไม่ commit และไม่อยู่บน base ของสาขานี้;
นี่เป็นการอ้างที่มาของ diagnosis ไม่ใช่หลักฐาน validation ของ fix ใหม่

พบ pattern เดียวกันใน indicator_http แต่ยังไม่ได้พิสูจน์ผลกระทบทุก endpoint
ขอบเขต tests และวิธีใช้ clock จะกำหนดใน plan/validation หลัง requirements อนุมัติ
จะไม่ลด budgets/assertions หรือข้าม failed evidence เพื่อปิดงาน

## ยังไม่ชัด — Needs Clarification

ไม่มี business/architecture decision ที่ต้องเปลี่ยนกฎเดิมในข้อเสนอนี้
RQ-01..08 และ plan.md/validation.md อนุมัติแล้ว; ไม่มี clarification ค้าง
