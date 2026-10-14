# PREPARED chart — Milestone A diagnostic, 2026-10-13

ผล: **Investigation complete; readiness not accepted**.
ไม่ใช่ C1/C2/C6 หรือ F-12 V-17 acceptance และไม่อนุญาต production activation
แผน: [prepared-chart-rollout-plan](../../prepared-chart-rollout-plan.md)

## Environment

ใช้ capacity PostgreSQL/Redis แยกจาก application DB; migrate เฉพาะฐานทดสอบ
0023 → 0024 และเติม synthetic candles ที่ขาดตั้งแต่ 2026-10-11 ผ่าน market-data role
กับ source-write protocol เดิม ไม่เปลี่ยน application mode และไม่ส่ง exchange orders
[Image/candidate](environment.json), [source hashes](source-hashes.json);
core indicator hash ใน image ตรง working tree ซึ่งยังมี uncommitted changes
API/builder จำกัดตัวละ 2 CPU/1 GiB; frontend ทดสอบ 5174, API 18002

## Browser smoke

| Scenario | เริ่ม request | รับ/parse body ครบ | ตรวจค่า UI และรอ render |
|---|---:|---:|---:|
| Initial 1h นับจากกด login | 195ms | 624ms | 1050ms |
| Idle 1h → 1m | 14ms | 473ms | 882ms |
| กลับ 1h | 22ms | 465ms | 1017ms |
| 5m → 1m ระหว่าง request เดิม | 2067ms | 2404ms | 3019ms |

[Results](browser-results.json): สี่กรณีได้ PREPARED generation,
1000 candles/1000 indicator rows; close/EMA20 บน UI ตรง response,
พบสีแท่งใน canvas และไม่มี page errors มี screenshots ประกอบ
คอลัมน์สุดท้ายรวม polling และรอเพิ่ม 100ms เป็นขอบเขตบนของการสังเกต
ไม่ใช่เวลาที่ paint ครั้งแรก; pixel count ไม่พิสูจน์ทุกจุดของเส้น indicator
body timing ใช้ fetch clone/JSON decode จึงมี overhead
ไม่ใช่ controlled comparison กับ LEGACY fixture ที่ sparse กว่า

[Source update](source-update-results.json): synthetic BTC 5m write เริ่มหลัง request,
proof ตอบ `CHANGED`, UI ซ่อน indicator เก่า ไม่มี page errors
เป็น invalidation smoke ไม่ใช่ deterministic transaction barrier test
ไม่มี live ingestion ใน fixture จึงไม่รับรองแท่งสดจาก exchange

## Readiness ที่ติด

[Setup](result.json) ใช้ 607.266s ก่อนหยุดตามเพดาน 600s
(poll ทุกประมาณ 10s จึงมี overshoot); [readiness](readiness.json) สูงสุด 29/30
ใช้ source/derived data เดิมแล้ว refresh หลังหยุดไปสองวัน ไม่ใช่ cold C1
แยกเวลานี้จาก measured smoke

ETH 1m ถูก SUPERSEDED สามครั้งจน FAILED_SUPERSEDED,
failure category SUPERSEDED, reason SOURCE_CHANGED, attempts_used=3
SOL 1m ถูก superseded ครั้งหนึ่งก่อนพร้อม ดู [worker attempts](worker-attempts.jsonl)
dense 1m ใช้ประมาณ 48–50s ต่อ build ในรอบนี้
source append ทุก 10s อาจเติมข้อมูลใน bounds ของ candidate ที่เริ่มก่อน append
ต้องตรวจ ordering นี้ต่อ ยังไม่พิสูจน์ว่า publication/scheduler ผิด
การปฏิเสธ candidate เมื่อ source เปลี่ยนเป็น safety behavior ที่ต้องคงไว้
ไม่เพิ่ม retry budget หรือบังคับ READY

## API smoke / profile

[60 probes](probes.json) สองรอบต่อเนื่องใช้ [3.938s](probe-summary.json):
200 จำนวน 19, 503 NOT_READY จำนวน 1, 429 RATE_LIMITED จำนวน 40
ไม่ได้ pace ข้าม admission window และใช้ budget ร่วมกับ browser
จึงใช้ตัดสิน accepted-workload availability ไม่ได้ และไม่ได้พิสูจน์ว่า harness
รอบเต็มเดิมผิด API จำกัด global 30/user 6 ต่อ window ตาม app.py

[Metrics](api-metrics.jsonl) เฉพาะ 19 responses 200: server wall 61–232ms,
max observed loop lag 68.194ms, candle queries 1–2;
40 responses 429 อ่าน candle 0 ครั้ง ไม่มี full parity audit
ไม่พบ lag เกิน 100ms ในตัวอย่างนี้ แต่ไม่ปิด C2 Failed 109.465ms เดิม
worker ทำงานระหว่าง probes และหยุดแบบ DRAINED หลัง setup/หลัง source-update smoke

[XRP 1m profile](request-profile.txt) เปิด cProfile ใน in-process ASGI:
wall 0.854s / CPU 0.830s ไม่ใช่เวลา HTTP จริง
checkpoint replay 1599 slots; read_indicators cumulative 0.416s,
feed_batch 0.256s, stored_rows ของ candles 0.191s, read_history 0.733s
ค่าซ้อนกัน ห้ามบวกเป็นแต่ละ stage
รองรับข้อสรุปว่า PREPARED เลี่ยง full-year replay ใน request;
ยังมี CPU ใน numeric validation/conversion และ candle response
ไม่พิสูจน์ต้นเหตุ historical C2 lag

## Harness / verification

- รอบแรกขาด VITE_CHART_ENABLED และ source-update ถูก 403 เพราะ origin 5174
  ไม่อยู่ใน allowlist; แก้เฉพาะ container ทดสอบ แล้วตรวจใหม่ผ่าน
- Playwright CDP body observation ค้าง/อ่าน body ไม่ได้; เปลี่ยนเป็น fetch clone
  ไม่แก้ production code
- ตรวจ Python diagnostic syntax และ node --check ผ่าน
  ไม่รัน full tests/build/benchmarks และไม่ถือเป็น application lint/type acceptance
- ผล core/digest36, PostgreSQL5, lint/types/imports ของงานก่อนยังอยู่ใน
  [F-12 evidence](../../../2026-10-12-candlestick-chart/evidence/final-candidate.md)
  งานนี้ไม่แก้ production source; ผลเก่าไม่แทน capacity บน candidate ใหม่
- ไม่ได้จับเวลางานอ่าน/เอกสาร/แก้ harness รวม จึงไม่ประมาณเวลารวมขึ้นเอง

คำสั่งหลัก: uv run python run_smoke.py จาก backend โดย role URLs ชี้
127.0.0.1:55434 เท่านั้น; node browser.mjs กับ SMOKE_EMAIL ของ fixture;
เพิ่ม SMOKE_SOURCE_UPDATE=1 สำหรับ invalidation; profile ผ่าน docker exec
python /evidence/profile_request.py กับ SMOKE_BASE=XRP
scripts ใช้ fixture/container เฉพาะ ไม่ใช่ reusable CI suite
อย่ารันซ้ำแล้วเขียนทับหลักฐานเดิมโดยไม่แยก output directory

## ขั้นถัดไป

1. เก็บ source-change/claim/publish trace ของ dense 1m เพื่อแยก ordering
   ออกจาก CPU cost ก่อนเลือก fix; ไม่เพิ่ม retries/ลด safety gates
2. รอบ API diagnostic ถัดไป pace ตาม admission และแยก user budget จาก browser;
   profile loop lag เมื่อ reproduce ได้ ไม่แก้ serialization จากข้อสงสัยอย่างเดียว
3. Cleanup 2s ของ rapid switch คงตามแผนเดิม หากจะลดต้องเสนอ cancellation
   contract และ safety validation ก่อน
4. C2/C6 และ release gates ยังคง Failed/Partial เดิม พร้อม
   **Pending Full Validation**; Milestone B/C ยังไม่เริ่ม

บริการ smoke API/frontend/builder หยุดแล้ว; capacity PostgreSQL/Redis กลับเป็น stopped
เก็บ fixture/artifacts ไม่แก้หรือลบ application data

## Follow-up fix — 2026-10-13

Source journal ที่ยังเก็บอยู่ยืนยัน arrival ordering ของ ETH 1m:

| Build start UTC | Candle open UTC | Source journal created UTC |
|---|---|---|
| 14:05:02.643 | 14:04:00 | 14:05:06.973 |
| 14:10:05.219 | 14:09:00 | 14:10:08.933 |
| 14:12:03.181 | 14:11:00 | 14:12:10.019 |

ทั้งสาม write อยู่ใน candidate bounds และเข้าระหว่าง build; failed generations
ถูก GC แล้ว จึงใช้ attempt log กับ source journal ประกอบ ไม่อ้างว่า replay snapshot ได้
ต้นเหตุที่ยืนยันได้ของ diagnostic นี้คือ producer ผูกกับ observer รอบ 10s
ไม่ใช่หลักฐานว่า production publication ควรยอมรับ source ที่เปลี่ยน

แก้ `run_smoke.py` ให้ producer ทำงานแยกทุก 250ms, propagate producer failure,
รอ Redis window ก่อนแต่ละรอบ 30 probes, หยุดเมื่อพบ terminal build failure,
ลด sleep ตาม setup budget ที่เหลือ และต้องระบุ `--output` เป็น directory ใหม่
อย่ารัน browser พร้อม probe runner เพราะ global budget ยังแชร์กัน
ไม่ล้าง rate-limit keys, ไม่ reset attempts, ไม่แก้ worker หรือสูตร

`test_runner.py` ผ่าน 4 tests (0.97s), Ruff check/format ผ่าน
รวม source progression ขณะ observer รอ, source failure และขอบ Redis window
ผล real PostgreSQL producer อยู่ใน `source-producer-fix.json` (แยกจาก readiness)
ขณะ observer รอ 33.210s, candle 1m ของทั้ง 5 คู่เข้าหลังขอบนาที 64–67ms
ในตัวอย่างหนึ่งรอบ แทน delay 7–10s ที่พบใน harness เดิม
ไม่ได้รัน full suite หรือ capacity รอบเต็มซ้ำ; ยังไม่รับรองว่าระบบผู้ใช้เร็วขึ้น
