# API deadline clock correctness — Plan

สถานะ: **Approved — เจ้าของตอบ “approve” วันที่ 2026-11-07**
วันที่: 2026-11-07
Requirements: [Approved](requirements.md)
Branch: `fix/api-deadline-clock`

## แนวทาง

คง absolute deadline ใน application monotonic clock เพื่อให้ downstream readers,
query_budget และ synchronous serialization checks ใช้ origin เดิมทั้งหมด
เปลี่ยนเฉพาะสอง HTTP boundaries จาก `asyncio.timeout_at(deadline)` เป็น
`asyncio.timeout(max(0, deadline - clock()))` โดย chart live ใช้ monotonic()
และ indicator_response ใช้ injected clock เดิม

asyncio จะสร้าง scheduling deadline ด้วย event-loop clock จากระยะเวลาที่เหลือเอง
ไม่แปลง downstream deadlines เป็น loop.time() และไม่ชดเชย offset ด้วยค่าคงที่
คำนวณ deadline ครั้งเดียวก่อน admission; ไม่รีเซ็ต budget ต่อขั้น ไม่เพิ่ม timeout
คง post-serialization `>= deadline` checks เพื่อจับ synchronous overrun
คง chart live 2 วินาที และ shared boundary 30 วินาทีจาก settings เดิม

ระยะเวลาทดสอบแบบ injected clock ต้องเดินในอัตราเดิมเมื่อทดสอบ offset;
tests ของ synchronous overrun ยังคงจำลองเวลาที่เพิ่มขึ้นด้วยวิธีเดิมได้
ไม่เปลี่ยน query_budget ซึ่งรับ monotonic deadline และจำกัด statement/lock timeouts เดิม

## ของเดิมที่จะใช้ซ้ำ

| Path | การใช้ซ้ำ |
|---|---|
| backend/src/tiewtrade/services/api/indicator_http.py | indicator_response, until_disconnect, serialization และ cleanup boundary |
| backend/src/tiewtrade/services/api/chart_routes.py | live deadline/error mapping และ history/verify consumers |
| backend/src/tiewtrade/services/api/indicator_routes.py | injected monotonic และ settings เดิม; ไม่มีแผนแก้ runtime |
| backend/src/tiewtrade/infra/market_data/indicator_reader.py | query_budget และ deadline propagation เดิม; ไม่มีแผนแก้ runtime |
| backend/tests/services/api/test_chart_response_boundary.py | pure boundary fixtures, budget/serialization tests |
| backend/tests/test_indicator_disconnect.py | timeout/disconnect/external cancellation และ bounded cleanup regressions |
| backend/tests/api/test_indicator_routes.py | exact serialization boundary และ HTTP contract |
| backend/tests/api/test_chart_routes.py | auth/CSRF, DB timeout, history/proof/live readiness contracts |
| frontend/e2e/candlestick-chart.spec.ts, frontend/playwright.chart.config.ts | existing real recovery flow และ default Uvicorn loop selection |

## สิ่งที่จะแก้

| ไฟล์ | เปลี่ยนอะไร |
|---|---|
| backend/src/tiewtrade/services/api/chart_routes.py | ใช้ remaining duration ที่ live timeout เท่านั้น; comment สั้นอธิบาย clock domain |
| backend/src/tiewtrade/services/api/indicator_http.py | ใช้ remaining duration ที่ shared response timeout; คง injected clock และ deadline ที่ส่งให้ work |
| backend/tests/services/api/test_chart_response_boundary.py | เพิ่ม offset ± tests สำหรับ shared boundary และ chart live; success, async timeout, already-exhausted budget, admission budget consumption และ synchronous boundary |
| backend/tests/test_indicator_disconnect.py | ใช้ชุดเดิม; เพิ่ม offset case เฉพาะที่จำเป็นเพื่อพิสูจน์ cleanup/cancellation พร้อม budget release |
| backend/tests/api/test_chart_routes.py, test_indicator_routes.py | ใช้ชุดเดิม; เพิ่ม regression เฉพาะช่องว่างที่ pure tests พิสูจน์ไม่ได้ |
| specs/features/2026-11-07-api-deadline-clock/, specs/roadmap.md | approval/checkpoint/results/evidence ตามจริง |

Tests offset ใช้ clock ที่คืน monotonic()+offset เช่น ±10000 วินาทีโดยไม่แก้
loop.time ทั้ง process; mocked work ไม่อ่าน DB ด้วย shifted deadline ส่วน real DB tests
ใช้ clock จริง ไม่ใช้ค่าจำลองข้ามชั้น ใช้ asyncio events/barriers แทน sleeps เมื่อทำได้
อย่างน้อยหนึ่ง stalled-work test ต้องพิสูจน์ cancellation จริง ไม่ใช่ assert ว่าเรียก timeout API
และมี outer watchdog ป้องกัน test ค้างโดยไม่ใช้แทน acceptance deadline

ไม่เพิ่ม abstraction ใหม่สำหรับการแปลงเวลาเพียงสองจุด ไม่แก้แลกเปลี่ยนข้อมูล,
exchange transport, indicator builder, package versions, config หรือ CI workflow

## ผลต่อฐานข้อมูล ความปลอดภัย และ concurrency

ไม่มี migration หรือ schema/transaction/locking change; session ยังคง PostgreSQL
ไม่เพิ่ม persistent process-local state หรือ infrastructure
คง auth/session recheck, admission, freshness, read-only boundaries และ error sanitization
คง until_disconnect และ DB cancellation cleanup; timeout response อาจต้องรอ cleanup ตามเดิม
งบ request ไม่ใช่คำสัญญาว่า cleanup เสร็จภายในเวลาเดียวกัน ห้ามปล่อย resource/task ทิ้ง
ไม่ส่ง Live orders และไม่เปลี่ยน financial calculations/retry/idempotency

## ความเสี่ยง

- เปลี่ยน clock domain ของ downstream โดยไม่ตั้งใจ: คง absolute deadline เดิมและตรวจ DB contracts
- timeout ถูกรีเซ็ตหรือหมดก่อนเวลา: offset ทั้งสองทิศ, admission + work ใช้งบร่วม, exact boundary
- cleanup หลุด/กลืน cancellation: ชุด disconnect เดิมและ budget-release assertions
- mocked tests ไม่ครอบ uvloop จริง: real recovery default auto loop บน host ที่เกิดปัญหา
- งานลบหน้าเป็นอีกสาขา: ผล backend fix อย่างเดียวไม่ปิด V-03 ของสาขานั้น

## Checkpoints

1. หลัง plan/validation อนุมัติ: เพิ่ม regression ให้เห็นปัญหาเดิม แล้วแก้สอง boundaries
   รัน targeted tests/static checks ตาม validation โดยไม่วน full suite หลังทุก patch
2. รัน real DB API contracts และ recovery ด้วย default loop; standard asyncio เพิ่มเพื่อ compatibility
   ใช้ disposable guarded DB/Redis และพอร์ตว่าง ไม่หยุด dev servers ของเจ้าของ
3. แจ้ง **Ready for Code Review** พร้อมผลและงานค้าง แล้วหยุดรอ `review code`
4. หลัง review/fixes ให้ถาม `refactor the code` และรอคำตอบตาม AGENTS.md
5. ก่อน merge: Feature gates, review และ required CI ต้องผ่าน candidate ล่าสุด
   commit/push/PR/merge ต้องมีคำสั่งเจ้าของแยกต่างหาก
6. งานลบ `/prices` จะตรวจ candidate รวมหลังเจ้าของอนุญาตการรวมงาน;
   ระหว่างนั้นคง blocker ของสาขานั้น ไม่ copy source ไปทับงานหรือ merge เอง

ชุดยาวของ F-11/F-12 ที่ไม่เปลี่ยน computation/data model คงเกณฑ์/หลักฐานและ
checkpoint เดิมใน roadmap ไม่มี workload ใหม่สำหรับ fix นี้ หาก targeted evidence
ไม่พอต้องระบุช่องว่างก่อนขยายการตรวจตาม testing §7
