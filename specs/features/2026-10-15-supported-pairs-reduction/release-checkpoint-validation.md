# F-38 — Release checkpoint validation

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-24**

อ้างอิงแผน: `release-checkpoint-plan.md`

## “ผ่าน” หมายถึง

| รหัส | เกณฑ์ | หลักฐานที่ต้องมี | ผล |
|---|---|---|---|
| RC-01 | candidate แยกจาก F-37/development และไม่มี private venue/Live order traffic | git revision/image digest, effective config, isolated ports/volumes และ network/request log | **Passed 2026-10-26** — isolated C1/combined/S5/restore stacks; private venue และ Live order เป็นศูนย์ |
| RC-02 | provenance audit ระบุได้ว่าหลักฐานเดิมแต่ละชุดพึ่ง source/tests/contracts/migration/config/harness ใดและยัง valid หรือไม่ | diff inventory และ reuse/rerun decision ต่อ artifact | **Passed 2026-10-24** |
| RC-03 | runtime readiness มี BTC+ETH 16/16 series; workload inventory มี BTC 8/8 series โดยไม่มี unsupported pair | R2-C1 result, runtime heads/probes และ metadata 2/16/1/8 | **Passed 2026-10-26** — `capacity/c1-r36`; exact R2-7 Passed |
| RC-04 | combined steady + rejected-load BTC 8 series ผ่านช่วงวัดจริง 3,600 วินาทีและออกผล R2-C2 + R2-C5-steady; ทุก scheduled sample/probe ถูกนับและ valid/fresh READY + correct GET 200 = 100% ต่อ series | result/observations/probes/rejected/metrics/worker attempts | **Passed 2026-10-26** — `capacity/combined-steady-r7`, 3,600.002s, 360/360 และ 60/60 ต่อ series |
| RC-05 | combined dirty/recovery + rejected-load BTC 8 series ผ่าน 3,600 วินาทีและออกผล R2-C3 + R2-C5-dirty: recover ภายใน 600 วินาที, availability ≥80% ต่อ series และหลัง recover พร้อม 100% จนจบ | committed invalidation trace, per-series observations/probes/rejected และ recovery timestamps | **Passed 2026-10-26** — `capacity/combined-dirty-r1`, recovery 60.064s |
| RC-06 | R2-C4 fairness ผ่าน R2-S1–S5; ไม่มี workload series starve เกิน 600 วินาที และ deadline ไม่ถูก retry/poll reset | per-series fairness/resource report และ scheduler trace | **Passed 2026-10-26** — S1–S4 JUnit green; strict fresh-derived S5 ผ่าน 8/8 |
| RC-07 | R2-C5 steady+dirty มาจาก combined phases เดียวกับ RC-04/RC-05; rejected requests ครบ denominator, ถูกปฏิเสธก่อน candle query และไม่แย่ง accepted quota | combined phase results, accepted/rejected request trace และ query-count evidence | **Passed 2026-10-26** — exact BUSY/RATE details และ rejected candle query เป็นศูนย์ |
| RC-08 | R2-C6 aggregate ผ่าน: RC-03–RC-07, R2-7/parity, worker ≤120s, RSS delta ≤128MiB, event-loop lag ≤100ms และไม่มี missing/skipped series | machine-evaluated aggregate result และ links ไป raw artifacts | **Passed 2026-10-26** — `capacity/aggregate-r5/result.json`; raw checks ทุกตัว true |
| RC-09 | V-12/V-13 evidence แยก runtime readiness 16 จาก workload 8 และมี `supported_runtime_pairs=2`, `runtime_readiness_series=16`, `profile_pairs=1`, `profile_series=8` | environment/result JSON ทุก phase | **Passed 2026-10-26** — scope metadata ตรงทุก final phase |
| RC-10 | backup มาจาก quiesced production-like pre-0030 fixture มี checksum/size และ pre-backup counts/digests ครบ โดยไม่รั่ว secret | fixture manifest, dump metadata, sanitized command log | **Passed 2026-10-25** — `restore/r8/result.json` |
| RC-11 | restore ลงฐาน disposable ใหม่คืนข้อมูลก่อน migration ได้ครบ แล้ว upgrade 0030 ซ้ำผ่าน; revision/count/digest/FK/RLS/grants ตรงทั้งหมด | restore/verify result JSON และ SQL summaries | **Passed 2026-10-25** — pre/post revisions และ scoped/non-market digests ตรง |
| RC-12 | restore ผ่าน RPO=0 committed rows หลังหยุด writers และ RTO≤30 นาทีตั้งแต่เริ่ม restore จน verification ผ่านครบ | RPO comparison และ measured restore-to-verified duration | **Passed 2026-10-25** — RPO=0, RTO=2.247043s |
| RC-13 | ไม่มีการแก้/สูญหายของ order/balance/position/user/credential/audit และไม่มี Live order/private venue request | before/after/restored digests และ network guard | **Passed 2026-10-25** — digests ตรง, private venue/Live order เป็นศูนย์ |
| RC-14 | source/harness changes (ถ้ามี) ผ่าน affected tests/static/review และ required candidate CI ตามผลกระทบ; docs-only change ไม่รัน application tests ซ้ำโดยไม่มีเหตุผล | test/static/CI summaries หรือ provenance justification | **Pending required CI** — local backend 3,219 passed, frontend 257 passed, static/contracts/review ผ่าน; ยังไม่มี final commit/remote CI |
| RC-15 | F-38 V-12/V-13/V-15 ถูก map กับหลักฐานครบ ไม่มี Failed/Partial/Not Run ค้าง และ roadmap ไม่อ้างว่า F-11/F-15/production PREPARED ผ่านตาม | final evidence crosswalk และ documentation diff review | **Passed locally 2026-10-26** — map ครบและไม่เปลี่ยนสถานะ feature อื่น/production |

## Mapping ไป F-38

| F-38 | เกณฑ์รอบนี้ |
|---|---|
| V-12 runtime readiness/bootstrap และ BTC-only workload | RC-03–RC-08 |
| V-13 resource/queue bounds | RC-04–RC-09 |
| V-15 backup/restore | RC-10–RC-13 |

## Threshold ที่ห้ามเปลี่ยนระหว่างรัน

- combined C2+C5-steady และ combined C3+C5-dirty วัด phase ละ 3,600 วินาทีจริง รวมสอง phase
- dirty recovery พร้อมภายใน 600 วินาที และ C3 availability อย่างน้อย 80% ต่อ series
- healthy steady-state valid/fresh READY และ correct accepted GET 200 = 100% ต่อ series
- worker attempt รวม cleanup ≤120 วินาที
- API/worker incremental RSS ≤128 MiB ตาม evaluator เดิม
- API event-loop lag ≤100 ms
- accepted probes/scheduled observations ต้องครบ; 429/503/BUSY/timeout ห้ามถูกตัดจาก denominator
- runtime readiness = 2 pairs × 8 timeframe = 16 series
- measured workload = BTC/USDT × 8 timeframe = 8 series
- backup/restore RPO/RTO ใช้ค่าที่เจ้าของอนุมัติใน NC-F38-RC-01 เท่านั้น

## เงื่อนไขล้มทันที

- พบ request ไป private venue/order endpoint หรือ Live Trading ถูกเปิด
- candidate ใช้ฐาน/Redis/volume เดียวกับ development, F-37 หรือ application environment
- unsupported pair ถูกสร้างกลับ, BTC/ETH data เปลี่ยนผิดคาด หรือ digest ตารางนอกขอบเขตต่าง
- evaluator ข้าม sample/series/failure, ลด duration/threshold หรือใช้ smoke แทน full phase
- restore ทับฐานที่กำลังรับ write, ใช้ downgrade แทน backup หรือ backup/หลักฐานมี secret
- source/evaluator เปลี่ยนหลัง measured run โดยไม่ประเมินผลกระทบและ rerun ส่วนที่หมดอายุ

## หลักฐานส่งมอบ

- `README.md` สรุป candidate, environment, commands, elapsed time และผล RC-01–RC-15
- environment/result JSON และ raw observations/probes/metrics/worker/fairness/rejected-load traces
- failure artifacts ทุกครั้งที่เกิด ไม่ลบหรือเขียนทับด้วย rerun
- backup manifest/checksum/size, pre/post/restored counts/digests และ restore timing
- provenance diff, review findings/remediation และ test/static/CI results ที่เกี่ยวข้อง
- final crosswalk ไป F-38 V-12/V-13/V-15 และ roadmap registry

## การตัดสินผล

F-38 เป็น `Completed` ได้เมื่อ RC-01–RC-15 ผ่านทั้งหมดและไม่มี Needs Clarification ค้าง
ผลผ่านเฉพาะ workload ไม่แทน restore และผล restore ไม่แทน workload/resource gate
การปิด F-38 ไม่เปลี่ยนสถานะ F-11, F-15, ชุดที่ 9 ทั้งชุด, production PREPARED หรือ Live Trading

## Amendment สำหรับ dedicated validation และ V-15 quiesced fixture — Approved 2026-10-25

- measured capacity validation ใช้ Docker window แบบ dedicated: บันทึก container ที่กำลังทำงาน,
  หยุด development/F-11 ชั่วคราว และเริ่มคืนเฉพาะรายการเดิม โดยไม่ลบ volume หรือเปลี่ยนข้อมูล
- threshold, duration, denominator และเกณฑ์ resource ทุกข้อข้างต้นคงเดิม
- V-15 ต้องมีห้าฐานครบในทุก scoped table ที่สามารถมีแถวได้ใน quiesced pre-0030 state;
  `indicator_heads` ต้องว่างและ `indicator_generations` ต้องเป็น `EXPIRED`
- digest ของ user/session/audit และตารางนอกขอบเขตยังต้องตรง; RPO=0 และ RTO≤30 นาทีคงเดิม

## Amendment รวม capacity phases เหลือสองชั่วโมง — Approved 2026-10-25

- phase 1 ต้องเขียน `R2-C2` และ `R2-C5-steady` จาก measured run เดียวกัน 3,600 วินาที;
  ผ่านได้เมื่อ steady thresholds และ rejected-load coverage/query/resource gates ผ่านพร้อมกัน
- phase 2 ต้องเขียน `R2-C3` และ `R2-C5-dirty` จาก measured runเดียวกัน 3,600 วินาที;
  เริ่มได้เมื่อผลทั้งสอง gate ของ phase 1 ผ่าน และผ่านได้เมื่อ dirty/recovery thresholds กับ
  rejected-load coverage/query/resource gates ผ่านพร้อมกัน
- gate คู่ใน phase เดียวกันต้องมีผลเดียวกันเสมอ; failure ใด ๆ ทำให้ทั้งคู่ Failed และห้ามนำ
  partial/smoke หรือผลก่อน amendment มาปิดแทน
- duration, scheduled samples/probes, rejected-request denominator, correctness, freshness,
  recovery, worker/RSS/event-loop thresholds และ metadata 2/16/1/8 คงเดิมทั้งหมด
