# F-38 release checkpoint — 2026-10-24 ถึง 2026-10-26

สถานะ: **Local acceptance Passed — รอ commit/push และ required candidate CI**

อ้างอิง `release-checkpoint-plan.md` และ `release-checkpoint-validation.md` ที่เจ้าของอนุมัติ
รวม amendments สำหรับ dedicated validation, V-15 quiesced fixture และการรวม capacity เหลือ
สอง measured phases รวม 120 นาที

## Candidate และ isolation

- branch: `validation/f38-release-checkpoint`
- immutable capacity image: `tiewtrade-f38-release-20261025-r9:latest`
- image ID/digest:
  `sha256:c194273af4d61c86ff267e11fcc13420858cf4d826e944474dac01a84665635b`
- capacity stack หลัก: prefix `tiewtrade-f38-release-r9-20261025`, PostgreSQL host port
  55457, Redis host port 56402, API CPU 6–7, builder CPU 4–5, process ละ 1 GiB
- S5 ใช้ fresh stack แยก prefix `tiewtrade-f38-s5-r5-20261026`, PostgreSQL 55474,
  Redis 56424; derived/jobs ว่างก่อนเริ่ม และ runtime ทั้งสามสร้างจาก image เดียวกัน
- workload ที่วัดคือ BTC/USDT × 8 timeframe; runtime readiness ยังคง BTC+ETH 16 series
- harness ไม่มี venue credential/order endpoint และ automated validation ไม่ส่ง Live order
- source AST ของ image ที่วัดตรงกับ final working tree ทุก production module ที่เปลี่ยน;
  ดู `provenance/r9-source-ast.json`

## ผลสุดท้ายตามเกณฑ์

| เกณฑ์ | ผล | หลักฐาน |
|---|---|---|
| RC-01 candidate/isolation/no Live | **Passed** | environment JSON ของ C1/S5, isolated ports/prefixes และ V-15 `private_venue_requests=0`, `live_orders=0` |
| RC-02 provenance | **Passed** | diff audit และ `provenance/r9-source-ast.json` |
| RC-03 R2-C1 + readiness 16/16 | **Passed** | `capacity/c1-r36/result.json`, exact R2-7 raw artifacts |
| RC-04 combined steady 3,600s | **Passed** | `capacity/combined-steady-r7/result.json`: C2+C5-steady Passed, 360/360 observations และ 60/60 probes ต่อ series |
| RC-05 combined dirty 3,600s | **Passed** | `capacity/combined-dirty-r1/result.json`: C3+C5-dirty Passed, recovery 60.064s |
| RC-06 fairness R2-S1–S5 | **Passed** | `capacity/scheduler-r1/tests.xml`, `capacity/s5-r5/result.json`; S5 8/8, deadline เดิมไม่ reset/miss |
| RC-07 rejected load | **Passed** | raw `rejected.json`/API metrics ของสอง combined phases; BUSY 503 และ RATE 429 อย่างละ 1,200/phase, candle query 0 |
| RC-08 aggregate R2-C6 | **Passed** | `capacity/aggregate-r5/result.json`: C4/C6 Passed และ raw checks ทุกตัว true |
| RC-09 metadata 2/16/1/8 | **Passed** | C1, steady, dirty, S5 และ aggregate scope checks |
| RC-10 backup | **Passed** | `restore/r8/result.json`: custom dump 843,063 bytes พร้อม SHA-256 |
| RC-11 restore/upgrade | **Passed** | restore pre-0030 → verify → upgrade 0030; revisions/digests/FK/RLS/grants ตรง |
| RC-12 RPO/RTO | **Passed** | RPO=0 committed rows; RTO 2.247043s ≤1,800s |
| RC-13 non-market/no Live | **Passed** | non-market digests ตรง, private venue requests 0, Live orders 0 |
| RC-14 source/harness gates | **Pending required CI** | local backend/frontend/static/review ผ่าน; ยังไม่มี final commit และ remote candidate CI |
| RC-15 crosswalk/docs | **Passed locally** | V-12/V-13/V-15 และ roadmap registry map ไปหลักฐานชุดนี้โดยไม่เปลี่ยน F-11/F-15/production status |

## Capacity acceptance

### C1 และ R2-7

- `capacity/c1-r36/result.json`: R2-C1 Passed, runtime readiness 16/16, workload 8/8
- exact fixture: 525,600 source rows/logical slots, 527 checkpoints
- cold 1 + warm 5: HTTP 200, 1,000 rows, parity/digest คงที่ทุก request
- evaluator ตรวจซ้ำ latency ≤30s, body ≤2 MiB, candle queries ≤8, lag ≤100ms,
  RSS delta ≤128 MiB และ audit retries

### Combined steady + rejected load

- `capacity/combined-steady-r7/result.json`
- measured 3,600.002s
- R2-C2 และ R2-C5-steady Passed
- ทุก 8 series: valid 360/360 และ audited correct GET 200 60/60
- rejected-load contract ครบและถูกปฏิเสธก่อน candle query

### Combined dirty/recovery + rejected load

- `capacity/combined-dirty-r1/result.json`
- measured 3,600.002s; recovery 60.064s
- R2-C3 และ R2-C5-dirty Passed
- 1m valid 354/360; อีก 7 series 358/360; หลัง recovery พร้อมต่อเนื่อง
- audited correct post-recovery probes 59/60 ต่อ series และ rejected-load contract ครบ

### R2-S5 strict fresh-derived fairness

- `capacity/s5-r5/result.json`: Passed 8/8
- seed source 16 series บน derived/jobs ว่าง; BTC/1m เป็น series เดียวที่รับ historical
  writes ต่อเนื่อง 20 commits ส่วนอีก 15 runtime series เป็น append-only ตั้งแต่ต้น
- BTC/1m ถูก observe ว่า unavailable 135 samples แล้ว recover valid + audited correct GET 200
  ภายใน original 600s deadline; ทุก series เก็บ first eligibility/deadline เดิม ไม่มี miss/reset
- สร้าง builder สอง replicasจริงภายใต้ global slot; trace รอบนี้มี owner ที่ claim งาน 1 ราย
  จึงไม่อ้างว่า replica ทั้งสองได้ claim

### Aggregate

`capacity/aggregate-r5/result.json` คำนวณจาก raw C1/R2-7, steady, dirty, scheduler
S1–S4 และ S5 ไม่เชื่อไฟล์ summary อย่างเดียว ผล R2-C4 และ R2-C6 Passed และไม่มี failure

## Backup/restore

`restore/r8/result.json` ใช้ quiesced production-like pre-0030 fixture ที่มี BTC/ETH/SOL/XRP/
DOGE ครบใน scoped tables ที่มีแถวได้, heads ว่างและ generations เป็น EXPIRED ก่อน backup.
Restore ลงฐาน disposable ใหม่, verify pre-migration, upgrade 0030 และ verify ซ้ำผ่านทั้งหมด.
RPO=0, RTO=2.247043s, non-market/source-restored digests ตรง และไม่มี private/Live traffic.

## Verification และ review

- backend full regression: 3,219 passed, 2 deselected, 0 failed ใน 628.19s
- Ruff check/format, Mypy 464 files และ import contracts 7 ข้อผ่าน
- frontend lint/typecheck ผ่าน; tests 257 passed; generated API contract ไม่ drift
- targeted capacity/evaluator หลัง final hardening: 68 passed
- `verification/backend-full-r2` เก็บรอบ invalid ที่เครื่อง sleep/clock jump; ไม่ใช้รับรอง
- รายละเอียดอยู่ใน `verification/README.md`

Code review เดิมพบ High 3 ข้อและแก้แล้ว:

1. เพิ่ม S5 จริงและบังคับใน aggregate
2. aggregate คำนวณ R2-7 จาก raw fixture/parity/query/resource evidence
3. rejected-load ตรวจ exact error detail `INDICATOR_BUSY`/`INDICATOR_RATE_LIMITED`

Final review พบ High เพิ่มอีก 2 กลุ่มและแก้แล้ว: S5 บังคับ historical writes ครอบคลุม
recovery อย่างต่อเนื่อง และ evaluator ทุกเส้นทางบังคับ timing/resource เป็นค่าจำกัดที่ไม่ติดลบ;
มี negative mutation tests ครอบคลุมทั้งสองกลุ่ม

## Attempt register ที่ยังต้องเก็บ

- เก็บ C1/C2/combined attempts และ restore r1–r7 ทุกชุดไว้ ไม่เขียนทับ failure เดิม
- `combined-steady-r6` invalid เพราะ host sleep/clock jump; r7 ใช้ `caffeinate` และผ่าน
- `verification/backend-full-r2` invalid ด้วย clock jump; r3 ใช้ fresh DB/Redis + `caffeinate`
  และผ่าน
- S5 r1 ผ่านพฤติกรรมแต่ provenance ยังไม่พอ; r2 failed จาก evaluator/runner bug; r3 ถูก
  session ตัดก่อนเขียนผล; r4 setup invalid เพราะ bootstrap mount ผิด path; r5 คือผล final
- aggregate-r4 failed หลังเพิ่ม exact observation scope แบบ 8 series ซึ่งไม่ตรง raw runtime
  readiness 16 series; aggregate-r5 แก้เป็น exact BTC+ETH 16 และคง workload acceptance BTC 8
- ผล final ใช้ c1-r36, combined-steady-r7, combined-dirty-r1, scheduler-r1, s5-r5,
  aggregate-r5 และ restore-r8 เท่านั้น

## งานที่ยังบล็อก Completed

RC-14 ยังต้องมี required GitHub candidate CI บน final commit ตาม `standards/testing.md`.
ยังไม่ commit หรือ push เพราะกฎ Git กำหนดให้เจ้าของสั่งโดยตรง; ผล local ห้ามใช้แทน CI.
จนกว่าด่านนี้ผ่าน F-38 ยังไม่เปลี่ยนเป็น `Completed` และยังไม่เปิด production PREPARED/Live.
