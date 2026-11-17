# NC-F17-W3-OBS-01 — one observed W3 result

สถานะ: **Incomplete — observer lost required evidence; stopped/reporting, no replacement run**
วันที่: 2026-11-16 (Asia/Bangkok)
[Approved plan](../../observed-w3-fail-fast-plan.md) §5–6; [summary](w3-obs01-result-summary.json)

## ผลจริง

- Preflight Passed 7 samples/120s ก่อนสร้าง owned fixture/Redis; source/runner/config bindings
  unchanged ทั้งรอบ รวม final result `source_unchanged=true`
- เวลารวม 2147.1634s (35m47s); measured ก่อนสั่งหยุด 1972.8285s (32m52.8s)
  ไม่ครบ14400s จึง **ไม่ผ่าน endurance**
- offered3867/admitted3864/completed3863/rejected0, fills1546/cancels772/replays772/cycles772
  เป็น partial counters ขณะหยุด มี in-flight requests ไม่ถือว่าทั้งหมด rollback/ไม่มีผล
- WORKER_RESTART ที่ offset1800s เป็น RECOVERED, actual fault window33.1940s;
  ส่วนอีก6เหตุการณ์ NotRun; worker PID receipts40ตัวรวมสอง generations ไม่ใช่40concurrent
- snapshot rows660 บันทึกแล้ว ไม่ใช่ acceptance ของชุด4820หรือ final replay
- Root error `F17_FENCE_OBSERVER_EVIDENCE_INCOMPLETE`; reason `SAMPLER_EVIDENCE_LOST`
  sampler TimeoutError1/0 successful observations; task joined, envelope retained
- sampler capture phase `activity`, last completed `db_clock`, activity/locks ยังไม่มีข้อมูล
  overall capture about1.280s ภายใต้ observer timeout เดิม; source statement ที่ติดตามจบแล้ว
  ก่อนเริ่ม activity query จึง association `OVERLAPPED_OR_UNCONFIRMED` ไม่ระบุ blocker
  และไม่เรียก phase นี้ว่า server execution/commit ล้วน
- actual publications RETURNED19765/CancelledError1 (tick19766 ตอน shutdown);
  ไม่มี WriterLeaseLost ใน publication outcomes, clock recovery0/event null
  independent source witness committed head19765/generation1/buffer4096 rows
  ข้อมูลนี้ไม่พิสูจน์ว่า original lease-stall cause ถูกแก้แล้ว

Fail-fast เริ่ม safe-stop หลัง sampler failure แทนรอ4hตาม plan แต่ observedW3 ยังคง Incomplete
ทั้ง dedicated failure receipt และ publisher-lease summary ถูกเก็บ ไม่มี auto-rerun/ผ่อนเกณฑ์

## Resource / cleanup / limitations

Parent pool report finalized แต่ `passed=false`, ConnectionResourceError2 จาก CancelledError
ใน ADMIN_OBSERVER sampler และ API request ระหว่างหยุด; deadline_context not_observed และ
quiescing=false ไม่ waiver/เปลี่ยน grade แม้สุดท้ายคืน resources แล้ว

Normal cleanup และ independent admin proof: DB absent,0 connections,0 database locks;
ownedRedis absent; worker PID receipts40 ไม่มี PID ที่ยังอยู่; ownerPostgreSQL healthy และ
ownerRedis running ทั้งสอง restart_count0 ไม่ force drop/หยุดบริการอื่น

Final tail, full snapshots/rebuild, final financial/global/positions/processing/resource/
aggregate acceptance **NotRun** ไม่อ้างเงินหรือ position ผ่านจากการรันที่ถูกขัดจังหวะ
660 snapshots และ partial positive commands ไม่ใช้แทนด่านเหล่านี้

Raw: `validation-artifacts/f17-w3-obs01-20261116/` รวม candidate/runner/config/schedule/
preflight/ownership/failure envelopes/normalและindependent cleanup และ final `result.json`
ค่าระยะเวลาจาก monitoring checkpoint รุ่นแรกที่อ่าน Python3.9 monotonic ต่าง clock ถูกเก็บ
เป็น invalid monitor-only receipt และแก้เป็น Python3.12 แล้ว; workload/coordinator clocks,
fixed14400s/18000s budgets และ final result ไม่เคยใช้ค่าติดตามผิดนั้น

## ขั้นถัดไป / stop

หยุดหลังหนึ่ง campaign ตามแผน เก็บ Incomplete เดิมทั้งหมด ไม่มี Git/CI/merge หรือแก้ source
หลังผลล้ม รอบต่อไปควรเป็นแผนวินิจฉัย observer แบบสั้นแยก เพื่อหาว่าความหน่วงอยู่ที่
connection/driver/scheduling หรือ query โดยคง financial/lease guards และไม่เพิ่ม timeout
เพียงเพื่อให้ผ่าน ต้องจัดทำขอบเขต/เกณฑ์/จุดหยุดก่อนทดลอง ไม่เริ่ม replacement4hเอง
Offline REBUILD20-04 Passed และ Feature checks เดิมคงตาม candidate เดิม; F-17 ยังไม่ Completed
