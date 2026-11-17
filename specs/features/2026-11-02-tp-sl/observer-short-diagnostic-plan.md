# NC-F17-OBS-02 — แยกต้นทุน observer ก่อนทดลอง endurance ใหม่

สถานะ: **Approved A — เจ้าของอนุมัติ implementation/tests; review/refactor ก่อนหนึ่ง diagnostic campaign**
วันที่: 2026-11-16
ขอบเขต: F-17 harness diagnostic บน branch เดิม ไม่มี trading feature ใหม่

## ปัญหาและหลักฐาน

[OBS-01 result](evidence/endurance20-20261115/w3-obs01-result.md) เป็น Incomplete
หลังวัด 1972.8285s จาก SAMPLER_EVIDENCE_LOST / TimeoutError
ตัว sample ใน `backend/tests/infra/execution_market/profile_publisher_fence.py`
ใช้ timeout 1s ครอบ checkout, SET LOCAL สองครั้ง, clock, activity, locks และ session exit
activity ใช้ pg_blocking_pids กับทุก session ของฐานเป้าหมาย ไม่ใช่เฉพาะ publisher
หลักฐานรอบล่าสุดหยุดที่ activity; ไม่ได้เก็บแถว activity/locks จึงยังระบุ blocker ไม่ได้
statement ของ publisher จบก่อน activity capture เริ่ม ไม่ถือว่า observer delay คือ
publisher/server execution time และยังไม่มีหลักฐานพอให้เปลี่ยน query หรือ timeout

## ทางเลือกและคำแนะนำ

A: ตรวจ observer เดิมในฐานแยกแบบสั้น เพื่อวัดต้นทุน connection และช่วง query ก่อน
เพิ่ม workload เหมาะกว่ารัน 4h ซ้ำซึ่งเคยหยุดเพราะหลักฐานขาด
B: วิเคราะห์ไฟล์เดิมอย่างเดียว ได้ข้อจำกัดข้างต้นแต่แยก timing เพิ่มไม่ได้
เลือก A เป็นข้อเสนอ ไม่ถือว่าการจัดทำแผนอนุมัติการทดลองแล้ว
AGENTS มอบอำนาจรายละเอียดทางวิศวกรรม แต่ OBS-01 §6/§13 กำหนดหยุดหลังหนึ่ง campaign
รอบนี้จึงขออนุมัติขอบเขตใหม่ก่อนเพิ่ม harness/ทดลอง ไม่แก้สถานะผลเดิม

## Requirements / ขอบเขต

- ใช้ FenceObservation.sample และ readonly_admin เดิมบนฐานว่างเฉพาะงาน
  reuse isolated fixture และ holder/waiter จาก `test_publisher_fence.py`
  ไม่สร้างบัญชีเจ้าของ ไม่ส่ง orders ไม่สร้าง Redis/worker หรือแก้ production
- เก็บเวลาจาก Python 3.12 monotonic เดียวกัน แยก connect/transaction setup,
  driver calls ของ SET/clock/activity/locks และ session exit; ทุกช่วงรวม await/scheduling
  ห้ามตั้งชื่อว่า server execution ล้วน เก็บ event-loop lag จาก task เดียวของ diagnostic
- เก็บเฉพาะ phase/duration/PID/count/association/outcome และข้อมูลเดิมที่อนุญาต
  ไม่เก็บ SQL text, connection URL, cookie/token หรือ exception message
- ไม่แก้ SQL/timeout 1s, statement_timeout 500ms, lock_timeout 200ms,
  row limits, isolation, fail-fast หรือการจัดเกรดเดิม
- instrumentation อยู่ใน runner/test harness เฉพาะงาน ไม่ monkeypatch ข้าม task
  ไม่ซ้อน retry หรือเรียก sample ทดแทนเมื่อ error

## Plan / หนึ่ง campaign แบบมีขอบเขต

1. เพิ่ม runner เฉพาะงานและ targeted tests สำหรับการเก็บ timing, exception/cancellation
   identity, ไม่มี invocation ซ้ำ, IO failure, task isolation และ bounded retention
   ใช้ tests เดิมของ read-only/blocker/rollback/lock release กับ PostgreSQL จริง
   ตรวจ Ruff/format/mypy เฉพาะไฟล์กระทบก่อน experiment
2. Pin candidate/config/migrations/runner; preflight เดิม 120s/7 samples หนึ่งครั้ง
   ไม่ผ่านให้หยุดก่อน fixture ไม่วนรอ ไม่หยุดบริการอื่น
3. สร้างฐานเฉพาะงาน แล้วตรวจตามลำดับต่อไปนี้ รวมไม่เกิน 30 captures:
   - cold connection: 10 captures ใช้ observer ใหม่ต่อ capture และ close ให้ครบ
   - reused observer: 10 captures ด้วย observer เดียว ไม่ dispose ระหว่าง captures
   - known holder/waiter: 10 captures ด้วย observer เดียว ใช้ fence lock จริงตาม test เดิม
     ต้องเห็น holder ใน blocking_pids และ lock ที่ waiter ยังไม่ได้รับ
   เว้น 250ms หลัง capture สำเร็จ; error/ข้อมูลขาดหยุด campaign ไม่เดินชุดถัดไป
   ใน cold/reused ใช้ backend PID ที่มีอยู่จริงจาก fixture; ระบุชัดว่า synthetic fixture
   ไม่ใช้ชื่อ/tick จำลองอ้างว่าเป็น publication จริงหรือ lease loss reproduction
4. บันทึกผลเมื่อจบ/ล้ม รักษา primary exception หาก evidence write ล้ม
   รอ task ที่เป็นเจ้าของ ปล่อย locks/dispose pools แล้วตรวจจาก connection อิสระ
   ลบเฉพาะฐานที่พิสูจน์ ownership ได้ ไม่มี force drop; cleanup ไม่สำเร็จให้ retain/report
5. ติดตามจน result และ cleanup จบ รายงานเวลารวม/รายช่วง/จำนวนที่ทำจริง/ข้อจำกัดแล้วหยุด

งบ experiment รวม preflight/fixture/cleanup ไม่เกิน 10 นาที สำรอง cleanup 60s
คาด 3–6 นาที ไม่รวมพัฒนาและ targeted checks; ไม่รัน 4h, ไม่ commit/push/CI/merge
หากติด deadline ให้หยุดเริ่ม capture ใหม่และใช้ flow cancel/join เดิม

## Validation และการตีความ

- Feature: tests ต้องพิสูจน์ original ถูกเรียกครั้งเดียว ไม่มีเปลี่ยนผล/exception,
  missing/invalid timing และ evidence IO failure ไม่ถูกตีความเป็น Passed
- Feature: read-only และ known blocker proof ใช้ฐานจริง; cleanup ต้องแยกผลจาก diagnostic
- Diagnostic: ทุก capture มี timestamps/outcome ครบ ผลช้าเก็บทั้งหมด ไม่ตัด outlier
  แสดง cold/reused/known-blocker แยกกัน ไม่ใช้ค่าเฉลี่ยกลบ failed sample
- ผลครบ 30 captures ใช้บอกได้เพียงว่า collector ทำงานใน fixture นี้ ไม่ยืนยันว่า
  production contention หรือ event-loop load ของ 20 workers ถูกจำลองครบ
  ถ้าไม่เกิด TimeoutError ให้รายงานว่าไม่เกิดซ้ำใน fixture นี้ ไม่ถือว่าแก้สาเหตุแล้ว
- Batch/Release: W3 4h และ final financial/global/replay acceptance ยังค้างตามเดิม
  ไม่ใช้ diagnostic ทดแทน เก็บ Incomplete/pool errors ของ OBS-01 ไม่ regrade

## จุดหยุด

เจ้าของอนุมัติ A แล้ว; ยังคง review/refactor gate ก่อน experiment ใหม่
หลัง implementation/checks ให้ผ่าน review/refactor ตาม AGENTS ก่อนหนึ่ง campaign
จบ campaign แล้วหยุด/report ไม่แก้ publisher/SQL/เกณฑ์หรือทดลองโหลดต่อเอง
F-17 ยังไม่ Completed

## Implementation record — ก่อนแก้ source

เจ้าของตอบ approve อนุมัติ A แล้ว การอนุมัติไม่ใช่ผล experiment
ใช้ proxy เฉพาะ engine ของ observer instance ที่ runner สร้างเอง ไม่มี global patch
วัด connect รวม transaction setup ที่ driver ทำ และวัด calls ตามลำดับเดิมโดยไม่คัดลอก SQL
original sample ยังรันครั้งเดียวใน task เดิม; ห้าม monitor/concurrent access ใน proxy
reuse `profile_replay_reads.save_partial_result` สำหรับรักษา primary เมื่อ IO ล้ม และ
`profile_workload.finish_observed_cleanup` สำหรับ join owned cleanup ผ่าน cancellation
runner เก็บสูงสุด 30 captures × 7 spans; lag เป็น count/max/sum ไม่มี unbounded samples
coordinator ตอน campaign จะใช้ preflight/isolated database/pinning/cleanup เดิม
ไม่เริ่ม preflight/campaign ในขั้น implementation/tests นี้

## Implementation checkpoint

[ผลตรวจ](evidence/endurance20-20261115/obs02-implementation.md): 83 distinct tests Passed,
Ruff/format/mypy Passed, independent cleanup Passed. Campaign/preflight Not Run
รอ owner review code ตามด่านที่อนุมัติ ก่อน refactor/affected validation และหนึ่ง campaign

## M1 — บันทึกก่อนแก้ findings

เจ้าของสั่งแก้ไขหลัง review พบ fixture เปิด transaction ก่อน isolated DB guard
หลักฐาน stub ยืนยันว่า environment ที่ guard ปฏิเสธยังเข้า fixture query ได้
ใช้ engineering authority ตาม AGENTS: เรียก `profile_internal.guard_database`
ก่อน create_engine_for ใน fixture_statement ทั้ง idle และ blocked paths
ใช้ guard เดิมตรวจ local isolated prefix และ endpoint/database ตรงกันทุก role
ไม่เพิ่มกฎ connection/SQL/timeout ใหม่ ไม่แก้ production หรือเริ่ม campaign
เพิ่ม negative tests environment missing/nonlocal/nonisolated/mismatched role endpoints
ยืนยัน engine/session factories ไม่ถูกเรียก ใช้ real-PG positive/rollback tests เดิม
หลัง targeted/static checks รายงานแล้วรอคำสั่ง refactor ตาม AGENTS

### ผลแก้ M1

[Checkpoint](evidence/endurance20-20261115/obs02-m1-fix.md): guard ก่อน engine,
12 negative cases ใหม่,47 affected tests Passed,static/independent cleanup Passed
รอ owner refactor; diagnostic campaign ยัง Not Run

## Refactor M1 — ก่อนแก้

เจ้าของสั่ง refactor the code: guard ใช้ helper เดิมแล้ว ไม่เพิ่ม abstraction ใน runner
ปรับเฉพาะ negative tests เป็นตาราง invalid URL โดยตรง ตัดชื่อเงื่อนไขและ lookup ซ้ำ
คง 12 cases และ assertions เดิม ตรวจ affected tests/static แล้วเดินต่อหนึ่ง diagnostic
ใช้ coordinator เดิมแบบ inline helper ที่ pin แล้ว ตัด Redis/workload ออกตาม OBS-02
ก่อน campaign ต้องตรวจ preflight ordering, budget และ cleanup/source bindings

### Refactor และเตรียมหนึ่ง campaign

Refactor เฉพาะ test matrix; 12 affected negative tests Passed และ Ruff/format/mypy Passed
ใช้ real-PG/35cases เดิมจาก M1 ต่อ เพราะ runner source ไม่เปลี่ยน
Coordinator /tmp/tiewtrade-f17-obs02-short.py compile ผ่านทั้ง parent/child;
reuse 5 helper functions จาก OBS01 แบบ inline ตรวจ AST-identical
pin source/config/migrations/parent/child ก่อน120s preflight; สร้างเฉพาะ DB ไม่มี Redis/worker
600s overall/60s reserve; timeout ส่ง SIGINT ให้ child cleanup และ retain DB ถ้า child ยังอยู่
ตรวจ source binding และ connection/locks ผ่าน admin อิสระก่อน normal DROP และยืนยันหลัง DROP
ไม่ force stop/drop หรือรันซ้ำ หลังผลหนึ่งรอบให้หยุด/report ตามอนุมัติเดิม

### One campaign result — stop/report

[Diagnostic Complete](evidence/endurance20-20261115/obs02-result.md): preflight7/7,
30/30captures,total136.3166s,no timeout,source unchanged,independent cleanup Passed
fixture-only ไม่พิสูจน์สาเหตุใต้20workerload; หยุด/report ไม่มีเพิ่ม experiment/4h/Git
