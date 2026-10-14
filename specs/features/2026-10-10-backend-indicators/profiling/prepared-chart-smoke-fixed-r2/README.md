# PREPARED readiness follow-up — 2026-10-13

ผล: **30/30 fresh/proof-valid series; 60/60 HTTP 200 ใน smoke**.
ไม่ใช่ C1/C2/C6 acceptance และยังไม่เปิด PREPARED ใน application DB

ใช้ runner ที่แก้ source producer และ admission pacing จาก
[รอบก่อน](../prepared-chart-smoke/README.md) บน isolated capacity fixture เดิม
candidate/image ใน [environment](environment.json); ไม่เปลี่ยน production source,
สูตร, source-proof, retry budget, concurrency หรือข้อมูล application

## หลักฐาน

- [Readiness](readiness.json): เริ่ม 11/30 และครบ 30/30 ที่ 253.469s
  ETH 1m ซึ่งเคย FAILED_SUPERSEDED กลับมาสร้าง READY ตาม scheduler/recovery เดิม
  ไม่มี manual READY หรือการ reset attempts ผ่าน SQL
- [ผลรวม](result.json): ช่วง API smoke 76.203s, 60 requests/60 HTTP 200
  [Probes](probes.json) ครบสองรอบ 5 คู่ × 6 TF; ไม่มี 429/503 ในรอบนี้
- [API metrics](api-metrics.json): server wall 66–292ms,
  max loop lag 76.335ms, RSS delta upper bound สูงสุด 65,880,064 bytes
  ไม่ปิด historical C2 lag failure จากตัวอย่างระยะสั้นนี้
- เป็น warm recovery ของ fixture ที่มี source/derived data อยู่แล้ว ไม่ใช่ cold C1
  ไม่ทำ full parity audit หรือทดแทน F-12 V-17 workload/ระยะรันเดิม

## การกู้สถานะก่อนรอบนี้

รอบ `prepared-chart-smoke-fixed` หยุดเมื่อพบ terminal ETH 1m ที่ค้างจากรอบเก่า
หลัง 1.75s; container stop สิ้นสุดด้วย exit 137 (ไม่ใช่ OOM)
และเหลือ RUNNING ownership จึงตรวจ container ที่หยุดแล้วและใช้ CLI
`indicator_builder.main reap` ตาม protocol เดิม ผล REAPED
กับ owner `acea0b47-eeb9-4bd1-b723-19272d33d4a7`, fence 338
ไม่ได้ข้าม ownership checks หรือเปิด worker ใหม่ก่อน recovery
เหตุ shutdown ครั้งนั้นยังไม่พิสูจน์ root cause; ไม่อ้างว่า shutdown validation ผ่าน

## ผลต่อปัญหาหน้าเว็บ

ปัญหา readiness ใน diagnostic ผ่านแล้ว และการยิง API ตาม rate limit ผ่าน
แต่เว็บ localhost:5173 ยังใช้ LEGACY จึงยังไม่ได้รับความเร็ว PREPARED
การเปิดใช้งานยังถูกบล็อกด้วย full acceptance/rollout ตาม Milestone B/C
คำขออนุมัติ Milestone B (อย่างน้อย 4 ชั่วโมงของช่วงวัด) ส่งให้เจ้าของแล้ว
ผล smoke นี้ไม่ใช่การอนุมัติหรือหลักฐานแทน release gate

คำสั่ง: `uv run python ../specs/features/2026-10-10-backend-indicators/profiling/prepared-chart-smoke/run_smoke.py --output ../specs/features/2026-10-10-backend-indicators/profiling/prepared-chart-smoke-fixed-r2 --setup-seconds 600`
จาก backend โดยใช้ role URLs ของ capacity DB 55434 และ Redis 56380 เท่านั้น
ไม่รัน full test suite หรือ full benchmark ซ้ำ
