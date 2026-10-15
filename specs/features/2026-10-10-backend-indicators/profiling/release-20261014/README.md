# Release checkpoint — 2026-10-14

สถานะล่าสุด: **C2 PASSED; C3/C5 และด่าน release ที่เหลือยังไม่รัน**

## Rerun หลังแก้ capacity/freshness — 2026-10-14/15

- แก้ harness ให้ C2 ใช้ workload ที่อนุมัติ 30 series (`1m`–`1d`) อย่างชัดเจน,
  ไม่เปิด source-write scope เมื่อ boundary ยังไม่เปลี่ยน และตั้ง rollout/codec ของฐานแยก
  ให้ตรงกับ candidate ปัจจุบัน.
- สร้าง candidate `tiewtrade-capacity-20261014:codec2` จาก source ปัจจุบันและ migrate
  ฐาน capacity แยกถึง migration 0029; ไม่แตะฐาน application และไม่เรียก exchange/order endpoint.
- C1 ของ candidate ผ่าน 30/30 ภายในนาทีที่ 6 และคง valid ถึงนาทีที่ 10. Process จบ non-zero
  เฉพาะ subgate `R2-7` cold/warm resource ที่ยัง Failed จึงบันทึกแยกและไม่ใช้ผลนี้ปิด R2-7.
- C2 ผ่านช่วงวัดเต็ม `3,600.016s`: ทุก series มี valid sample 360/360 และ correct probe
  60/60, failure เป็น null, API max lag `75.283ms` (<100ms), API max RSS `63.219MiB`
  (<128MiB), worker max attempt `50.053008s` (<120s) และ worker max RSS ประมาณ
  `0.012MiB`.
- C3/C5 ยังไม่รัน และ C6/R2-7 ที่ Failed เดิมยังไม่เปลี่ยนผล; ห้ามใช้ C2 เพียงด่านเดียว
  รับรอง production PREPARED.

หลักฐาน rerun: [C1](c1-codec2-r2/result.json) และ [C2](c2-codec2-r2/result.json).

## รอบแรกที่เก็บไว้เพื่อเปรียบเทียบ

- Candidate containers use immutable image `sha256:f0add4466c1cfe5ffcf6b52367b78d830b97714784e406e8ffb482a7c63308d3`, the same image recorded by C1.
- PostgreSQL `127.0.0.1:55434` and Redis `127.0.0.1:56380` are isolated capacity services. No exchange or order endpoint was used.
- C2 kept the approved 30-series workload (`BTC/DOGE/ETH/SOL/XRP` × `1m/5m/15m/1h/4h/1d`). Native `1w`/`1M` have separate F-12 validation gates.
- The first invocation stopped before setup because host `PYTHONPATH` did not include `tests`; the second stopped before setup because the current enum contains `1w`/`1M` while the approved C1 fixture contains 30 series. Neither invocation started measurement.
- The conforming invocation reached the 600-second baseline deadline with 0/30 proofs simultaneously valid and raised `CAPACITY_C2_BASELINE_NOT_READY`. The required 60-minute C2 interval never started.
- Worker attempts completed without a recorded attempt failure. Direct database inspection after shutdown showed 30/30 ready heads with valid proofs, but that post-stop state cannot satisfy the warm-up deadline.
- C3 and C5 were not run because their approved prerequisite requires C2 to pass.

Artifacts: [C2 result](c2/result.json), [baseline observations](c2/before-phase.json), and [warm-up worker attempts](c2/worker-attempts-warmup.jsonl).
