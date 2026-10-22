# F-38 — ลดคู่เทรดช่วงพัฒนา — Validation

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-15**

## “เสร็จ” หมายถึง

| รหัส | เกณฑ์ | ตรวจอย่างไร | ช่วงรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | Backend runtime catalog มี BTC/USDT และ ETH/USDT เท่านั้น | unit/contract test catalog และทุก consumer | ระหว่างพัฒนา | **Passed 2026-10-15** — catalog/consumer targeted tests |
| V-02 | API ปฏิเสธ SOL/XRP/DOGE/unknown ก่อน read/enqueue/write | authenticated API integration; ตรวจ demand count ไม่เพิ่ม | ระหว่างพัฒนา | **Passed 2026-10-15** — API integration และ demand ไม่มี side effect |
| V-03 | Price/live-candle subscriptions มี 2 และ 16 unique streams ตามลำดับบน shared connection | transport/supervisor integration; ตรวจชื่อ stream และ duplicate | ระหว่างพัฒนา | **Passed 2026-10-15** — transport tests และ runtime 2/16 series |
| V-04 | Frontend แสดงสองคู่, BTC default และ stale state fallback โดยไม่ยิงคู่ที่ถอด | component tests และ browser smoke | ระหว่างพัฒนา | **Passed 2026-10-15** — component 20 tests และ browser flow จริง |
| V-05 | Migration ลบข้อมูลคู่ที่ถอดครบทุก market/indicator table โดยไม่แตะ BTC/ETH | PostgreSQL fixture ครบทุกตาราง; pre/post count+digest | Candidate | **Passed 2026-10-15** — restore production-like backup แล้ว count/digest ตรง |
| V-06 | Migration atomic และผลลัพธ์ idempotent | inject failure กลาง transactionแล้วตรวจ rollback; ใช้ state หลัง upgradeตรวจซ้ำด้วย verifier | Candidate | **Passed 2026-10-22** — failure injection rollback และ upgrade verifier ผ่าน; follow-up regression ยืนยัน downgrade ใช้ source-maintenance scope กับ protected `market_candles` แล้ว upgrade คืน head ได้ |
| V-07 | ไม่มี orphan/FK/invalid head/checkpoint และ constraints รับเฉพาะ BTC/ETH | FK/constraint queries และ negative inserts | Candidate | **Passed 2026-10-15** — orphan 0 และ constraints ใหม่ทั้ง 6 กลุ่ม validate |
| V-08 | writer เก่าไม่สร้างข้อมูลกลับระหว่าง/หลัง migration | concurrent insert รอ lockแล้วถูก constraint ปฏิเสธ; restart worker และสังเกต queue/data | Candidate | **Passed 2026-10-15** — old writer ถูกปฏิเสธ; restart สองรอบยัง unsupported 0 |
| V-09 | ไม่มี order/balance/position/user/credential/audit row ถูกแก้ | before/after counts+digest ของตารางนอกขอบเขตที่มีอยู่ | Candidate | **Passed 2026-10-15** — 13 ตารางนอกขอบเขต digest ตรง; schema นี้ยังไม่มี order/balance/position |
| V-10 | Price snapshot schema/decoder ใช้สอง rows และ generated contract ตรงกัน | OpenAPI drift check + backend/frontend contract tests | ระหว่างพัฒนา | **Passed 2026-10-15** — regenerate OpenAPI/API types แล้ว hash คงเดิม |
| V-11 | BTC/ETH candle, price, indicator และ chart correctness เดิมไม่ถดถอย | targeted tests ตาม callers/dependencies; exact OHLCV/indicator parity | Candidate | **Passed candidate 2026-10-22** — clean-state backend 3,017 passed / 1 skipped / 2 deselected; frontend 246 passed; lint/types/imports/build/contracts passed |
| V-12 | Runtime readiness/bootstrap ครบ BTC+ETH 16 series และ BTC-only capacity/workload ครบ 8 timeframe ผ่าน threshold เดิมต่อ series/request | readiness ตรวจ 16 heads; profile runner สร้างโหลด/observe/probe BTC 8 seriesและแยก evidence | Release checkpoint | Pending Full Validation |
| V-13 | resource/queue bounds สอดคล้อง runtime 16 และ test profile 8 โดยไม่เกิด unbounded growth | RSS/lag/queue metrics และ post-run database counts | Release checkpoint | Pending Full Validation |
| V-14 | restart/reconnect/freshness หลัง purge ทำงานและไม่มี stream ของคู่ที่ถอด | disconnect/reconnect integration + runtime smoke | Candidate | **Passed 2026-10-15** — restart สองรอบกลับเป็น connected/bootstrapped และ preview สดครบ 16 |
| V-15 | backup และ restore ขั้นตอนจริงคืนข้อมูลก่อน migration ได้ | disposable production-like DB backup/restore drill | Release checkpoint | Pending Full Validation |
| V-16 | เอกสาร F-09–F-12/mission/roadmap ระบุตัวเลขใหม่และเก็บหลักฐานเดิม | link/diff review และค้นหา 5/30/40 ที่เกี่ยวข้อง | ก่อน merge | **Passed 2026-10-15** — เพิ่ม amendment และเก็บข้อความ/หลักฐานเก่าเป็น historical |

## Test matrix

### ระหว่างพัฒนา

- catalog/venue validation: BTC และ ETH ผ่าน; SOL/XRP/DOGE/unknown ถูกปฏิเสธ
- candle demand/read/chart/indicator routes: rejected input ไม่สร้าง side effect
- price snapshot: สองแถว exact, ordering/revision/generation semantics เดิม
- preview/realtime: 16 series, reconnect, duplicate/out-of-order/fencing เดิม
- frontend: dropdown 2 คู่, BTC default, decoder 2 rows, stale selection fallback
- migration helper/SQL verifier tests บน PostgreSQL จริงเฉพาะกรณีที่แก้
- Ruff, format, Mypy และ frontend lint/type check หลัง diff นิ่ง

### Candidate ก่อน merge

- รัน migration integration ด้วย fixture ที่มีทั้ง 5 คู่และ dependency ครบ
- ทดสอบ failure injection/rollback, concurrent writer, rerun verifier และ restore-independent
  schema downgrade behavior
- targeted regression ของ F-09–F-12 รวม generated OpenAPI drift/build
- browser smoke: BTC/ETH สลับได้, 8 timeframe ยังแสดงกราฟ, ไม่มี request คู่ที่ถูกถอด
- ตรวจ diff และ affected dependencies; full regression รันครั้งเดียวเมื่อ candidate นิ่งตาม
  `specs/standards/testing.md` ไม่รันซ้ำหลังทุก fix

### Release checkpoint

- เตรียม runtime readiness BTC/ETH ครบ 16 series แต่สร้างโหลดและวัด
  capacity/workload/stress/endurance เฉพาะ BTC/USDT × 8 timeframe
- ใช้ระยะรันและ threshold เดิมของ C2/C3/C5, R2-7/C6 และ F-12 V-17 ที่ยังเกี่ยวข้อง;
  เปลี่ยนเฉพาะ catalog input/count ที่อนุมัติใน F-38
- เก็บ latency, event-loop lag, RSS, queue depth, freshness, recovery, parity และ rejected-load
  evidence แยก path ใหม่พร้อม metadata `supported_runtime_pairs=2`, `profile_pairs=1`,
  `profile_series=8`
- ETH workload คงสถานะ Pending และห้ามใช้ผล BTC เปลี่ยนเป็น Passed
- backup/restore drill บน disposable production-like database

## การตรวจ migration โดยละเอียด

1. seed BTC/ETH/SOL/XRP/DOGE ใน candle history/demand, latest prices, preview และ indicator
   job/generation/head/checkpoint/retry/source-change ตาม FK จริง
2. บันทึก count และ deterministic digest แยก table/base รวมทั้งตารางนอกขอบเขต
3. ถือ concurrent transaction ที่พยายามเขียน SOL ระหว่าง migration
4. รัน upgrade `0029 -> 0030`; concurrent writer ต้องไม่แทรกข้อมูลกลับและจบด้วย rejection
5. ตรวจว่า SOL/XRP/DOGE เป็นศูนย์ทุกตาราง, BTC/ETH count+digest ไม่เปลี่ยน, ไม่มี orphan
6. ตรวจ negative insert และ API request ของคู่ที่ถอด
7. restart workers แล้วรออย่างน้อยสอง refresh/reconnect cycles; counts คู่ที่ถอดยังเป็นศูนย์
8. ทดสอบ injected failure ในฐานใหม่และยืนยัน state ทั้งหมดกลับเท่าก่อน migration
9. ทดสอบ backup/restore แยกจาก downgrade เพราะ downgrade ไม่สร้างข้อมูลที่ลบคืน

## Trading safety

- ไม่ส่ง live order ใน automated validation
- ตรวจว่าการเปลี่ยน allowlist ไม่แตะตาราง order, balance หรือ position
- คู่ที่ถูกถอดต้อง fail-closed สำหรับการเพิ่มความเสี่ยงในอนาคต แต่กฎปิด/ลด position เดิม
  ยังไม่ถูกเปลี่ยนโดย feature นี้
- Money/Quantity และ exact OHLCV/indicator values ต้องคงเดิม
- retry migration/deployment ต้องไม่ลบ BTC/ETH เพิ่มและไม่สร้าง duplicate jobs/subscriptions

## หลักฐานที่ต้องบันทึก

- targeted test/JUnit summaries และ static-check results
- migration pre/post counts, digests, rollback และ orphan checks
- runtime stream list และ post-restart zero-count verification
- OpenAPI/generated contract diff check
- BTC-only profile config, metrics และ result JSON
- backup/restore drill log ที่ไม่มี secret

## งานตรวจรับที่เลื่อนได้

V-12, V-13 และ V-15 เป็น `Pending Full Validation` จนถึง release checkpoint ได้ แต่ F-38
ห้ามเป็น Completed และห้ามใช้ PREPARED production จนด่านเหล่านี้ผ่าน ส่วน V-01–V-11,
V-14 และ V-16 ต้องผ่านก่อน merge
