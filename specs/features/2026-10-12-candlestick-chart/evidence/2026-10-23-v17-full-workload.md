# F-12 V-17 full workload — 2026-10-23

ผล: **Failed / Partial** — รันช่วงวัดเต็ม 600 วินาทีหลัง warmup 60 วินาที
แยก LEGACY/PREPARED แล้ว แต่มี threshold ที่ล้มและ coverage ของ controlled source fault
ไม่ครบ 5 series จึงห้ามใช้ผลนี้รับรอง V-17 หรือเปิด PREPARED จริง.

## Environment

- Source: `83077c77d2acfe9be2935715fa0d9f30b2e8a3e2`, branch
  `fix/f12-v17-exact-fixture`; production logic และ threshold ไม่เปลี่ยน.
- Candidate image: `sha256:f2e3a9f620a989b432f17b97575e8008cd2056f4e8893a9474aaf51071bb37fd`.
- Browser image: `sha256:3e94be8a5c97e5d20e49ec11ea221a24e474a156de70cba19866a3047d3dbb91`;
  Node 22.23.4, Playwright 1.63.0, Chromium 153.0.8010.12.
- Docker Linux arm64; API และ market-data จำกัด process ละ 2 CPU/1 GiB;
  PostgreSQL/Redis เป็น isolated capacity stack. ไม่มี Binance request, API key หรือ Live order.
- 20 authenticated sessions, BTCUSDT 8 timeframe, 15 events/s และ burst 150 events/s
  10 วินาทีทุกนาที, 100 mount/unmount cycles; deterministic sequence seed 0.
- คำสั่งหลัก: `profile_chart_workload.py --seconds 600 --warmup 60
  --lifecycle-cycles 100`; exit code `1` เพราะ evaluator พบ failed checks.

Environment metadata และ raw metrics อยู่ที่ [v17-full-20261023](v17-full-20261023/).

## ผล threshold

| เกณฑ์ | LEGACY | PREPARED | ผล |
|---|---:|---:|---|
| Preview receive → commit p95 ≤3s | 0.569s | 0.557s | Passed |
| Source event → browser text p95 ≤5s | 2.600s | 2.418s | Passed |
| Live GET p95 ≤500ms | 0.512s | 0.436s | **LEGACY Failed** |
| Live GET max ≤2s หรือ typed timeout | 2.877s | 1.760s | **LEGACY Failed** |
| History ทุก success ≤30s | max 13.011s | max 5.323s | Passed |
| PREPARED history p95 ≤3s | — | 5.053s | **Failed** |
| Browser retained slots ≤12,000 | 5,120 | 5,120 | Passed |
| API incremental RSS ≤128MiB | 12,697,600 B | 22,573,056 B | Passed |
| market-data incremental RSS ≤128MiB | 7,393,280 B | 4,907,008 B | Passed |
| process latest rows ≤16 | ≤8 | ≤8 | Passed |

ทั้งสองโหมดมี live success ระหว่างช่วงวัดเพียง 5/20 clients. LEGACY พบ
`CHART_DATA_UNAVAILABLE` 69 ครั้งและ typed deadline 3 ครั้ง; PREPARED พบ 70 และ 4 ครั้ง
ตามลำดับ. หน้า browser จบพร้อม alert 20/20 clients ใน LEGACY และ 19/20 ใน PREPARED.
LEGACY ยังพบ candle-page HTTP 500 สองครั้ง. จึงไม่ตีความ latency ของ successful requests
ว่าเป็น availability pass.

History/proof concurrency คืน typed `INDICATOR_BUSY` ตาม contract; LEGACY history มี
17 success, 76 busy และ 2 typed deadline. PREPARED มี 17 success, 76 busy และ
2 `INDICATOR_DATA_NOT_READY`. Builder ทำ progress จาก generation sequence 38 → 73
และจบ 16 READY jobs แต่ผลนี้ยังไม่ชดเชย p95 ที่เกินเกณฑ์.

## Coverage gap ของ harness

- Controlled source path พิสูจน์ `SOURCE_UNAVAILABLE → PARTIAL_GAP → COMPLETE`
  ผ่าน F-09 ingestion จริงได้ 3 series (`1m`, `5m`, `15m`) ต่อโหมด ไม่ครบ 5 series
  ที่ V-17 กำหนด เพราะ persistent fixture มี `1h`/`4h` current demand ถูกตอบแล้วก่อนรอบเต็ม.
- PREPARED จบด้วย preview 66 rows เกิน 60 แต่เริ่มรอบที่ 50 rows จาก smoke/LEGACY เดิม;
  จึงบันทึกเป็น contaminated fixture และไม่สรุปว่าเป็น production growth leak.
- Max-input 525,600 slots อ้างอิง exact F-11 R2-7 run บน source/image เดียวกัน;
  ผลนั้นไม่แทน availability/latency failures ของ V-17 รอบนี้.

ต้องทำให้ fixture ต่อโหมดเริ่มจาก preview/demand state ที่ควบคุมได้และบังคับ 5 series
อย่าง deterministic ก่อน rerun. ห้ามลบผล Failed ของรอบนี้เมื่อเพิ่ม rerun.

## Static validation ของ harness

- Backend scoped Ruff, format check และ mypy: Passed.
- Frontend scoped ESLint และ TypeScript: Passed.
- `git diff --check`: Passed.
