# F-17 — ทบทวนแผนหลังรอบยาวไม่ผ่าน 4 รอบ

สถานะ: **ทบทวนหลักฐานเสร็จ — ทางเลือกด้านล่างเป็น Proposed ยังไม่อนุมัติให้ทดลอง**
วันที่: 2026-11-16 (Asia/Bangkok)
ขอบเขต: เจ้าของสั่งเริ่มทบทวนเอกสาร/หลักฐานก่อนทดลองเพิ่ม ไม่แก้ source ไม่เปลี่ยนเกณฑ์
และไม่รัน tests/workload ใหม่ ผลเดิมและงานค้างทุกด่านคงเดิม

## 1. ข้อสรุปที่ตัดสินใจได้จากหลักฐาน

ควรพักการรัน 4 ชั่วโมงและแยกตรวจคอขวดก่อน ไม่ใช่เพิ่ม timeout ให้ครอบผลที่ล้ม
ทั้ง 4 รอบมีเป้าหมายเดียวกันแต่หยุดคนละสาเหตุ จึงไม่ใช่หลักฐานว่าแก้ปัญหาเดียว
ผิดซ้ำ 4 ครั้ง และก็ไม่ใช่เหตุผลให้มองข้ามต้นทุนรวมของการทดลองที่ยังไม่ปิดด่าน

เกณฑ์ rebuild 60 วินาทีมีที่มาจาก **แผนตรวจรับที่เจ้าของอนุมัติ** ไม่ใช่ตัวเลข
ที่เพิ่งใส่ตอนเขียน harness แต่ในเอกสารที่ตรวจยังไม่พบ benchmark หรือข้อกำหนด
เวลารอของผู้ใช้ที่ใช้คำนวณตัวเลขนี้ จึงควรทบทวนความเหมาะสมโดยไม่สรุปว่าเกณฑ์ผิด
ไม่มีหลักฐานพอให้เปลี่ยนเป็น 90/120 วินาที หรือรับรองว่า decoder ใหม่จะผ่านรอบยาว

## 2. สี่รอบยาวและสถานะการแก้

| รอบ / หลักฐาน | ผลและจุดหยุด | สิ่งที่พิสูจน์/แก้แล้ว | สิ่งที่ยังไม่พิสูจน์ |
|---|---|---|---|
| [1 — no-retry](evidence/endurance20-20261115/checkpoint.md) | Incomplete; วัด 40นาที11วินาที; timestamp นำ guard 230µs | guard ปฏิเสธถูกต้อง; ต่อมามี CLOCK-01 opt-in ที่อนุมัติ จำกัด 1 event/1 retry/1s และยืนยัน rollback | ไม่ได้แก้ clock ของ host; ไม่รับรองว่าจะไม่มีเหตุซ้ำ |
| [2 — CLOCK-01](evidence/endurance20-20261115/clock01-four-hour-checkpoint.md) | Incomplete; วัดครบ4ชม.; final-tail60sหมดก่อนอ่าน cursor ครบ20owner | TAIL-01 พบ full-history sort บน fixture; TAIL-02 ปรับ query ของ harness พร้อม equivalence/RLS proof; รอบ4 final-tail24.061sและlag0ครบ20owner | เวลา24.061sเป็นหลักฐานเฉพาะ candidate รอบ4 ไม่ใช่ regrade รอบ2หรือรับรอง candidate ใหม่ทั้งหมด |
| [3 — TAIL-02](evidence/endurance20-20261115/tail02-four-hour-checkpoint.md) | Incomplete; วัด3ชม.59นาที31.934วินาที; book lease ไม่ live ตอน UPDATE | ไม่ reacquire/retry โดยเดา; diagnostic ต่อมาจับ price-fence client span9.848sและ rollback witness | ยังไม่มี blocker/server timeline ที่พิสูจน์สาเหตุของ stall; ไม่ถือว่า lease ปัญหาหายแล้ว |
| [4 — FENCE-02](evidence/endurance20-20261115/fence02-w3-checkpoint.md) | Incomplete; วัดครบ4ชม./28200คำสั่ง; replay owner14เกิน60s | final-tailผ่าน;4820snapshotsกลับครบ;13ownerreplaysกลับ; decoder ตรวจ/รีวิว/refactorแล้ว | owner14ไม่ผ่านและ6ownerยังไม่รัน; finalfinancial/global/resource/aggregate acceptanceไม่ครบ; samplerTimeout1ทำให้ blocker evidenceขาด |

จำนวนนี้นับเฉพาะรอบยาวของชุด20บัญชีล่าสุด ไม่รวม diagnostic/CI หรือประวัติ F-17 ทั้งหมด
เวลารวมที่บันทึกของ4รอบประมาณ13ชม.5นาที ไม่รวมพัฒนา รีวิว tests และ diagnostic
แต่ละรอบเก็บขอบเขต setup/cleanup ตาม receipt ของตน จึงไม่ใช่การวัดเวลาทำงานทั้งหมด

## 3. ที่มาของ 60 วินาที และความหมายที่โค้ดวัดจริง

- [F-14 validation V-17](../2026-10-16-position-margin-pnl/validation.md): ต้องมี
  deterministic rebuild/snapshot ตามขนาดและงบที่อนุมัติ ไม่ล็อก owner อื่น และไม่มี
  unbounded memory/query growth; ข้อความนี้ไม่ได้กำหนด 60s เอง
- [Integrated Paper plan — approved 2026-11-06](integrated-paper-acceptance-plan.md)
  หัวข้อ Approved integrated composition ข้อ2–3 กำหนด retained history ครบทุก episode,
  exact oracle และ **each final rebuild within60s** พร้อม query/row/resource evidence
- [Internal20 amendment §4 ข้อ2](internal-paper-acceptance-amendment.md) ยืนยัน
  rebuild≤60s/owner ต่อสำหรับ20episode; ไม่ได้ยกเลิกเกณฑ์เมื่อจำนวนผู้ใช้ลดลง
- `profile_positions.PositionChecks.final` ครอบ `replay_owner_domain` ทั้งฟังก์ชัน
  ด้วย60sและตรวจ elapsed≤60 อีกชั้น ระยะเวลารวม role/session/query/driver/decoding/exit
  ไม่ใช่เวลา CPU fold ล้วน และเวลารวม20ownerอาจถึง20นาทีโดยเกณฑ์รายคนยังไม่เปลี่ยน
- `profile_restore.replay_owner_domain` รวม: อ่าน snapshot → fold effective executions
  และเทียบ held/cost/realized PnL → เทียบ trade/correction cash ledger → อ่านและตรวจ
  execution-input payload ทุกหน้า → โหลด matching checkpoint สำหรับ episode ที่ active

ดังนั้นเกณฑ์ปัจจุบันเป็น **งบรวมของการตรวจ replay/history ราย owner** การตัดช่วง
อ่านหลักฐานออกจาก60sจะเปลี่ยนสิ่งที่รับรอง แม้ยังอ่านหลักฐานครบในอีกช่วงหนึ่งก็ตาม
ห้ามทำเช่นนั้นโดยอ้างว่าเป็นแค่ปรับ timer ต้องอนุมัติ amendment ก่อน
ไม่สับสนเกณฑ์นี้กับ snapshot250ms/1s, engine SLA ของแต่ละ profile, lease5s หรือ
cycle/recovery60s ซึ่งเป็นคนละการรับรองและไม่ได้อนุญาตให้ผ่อนตามกัน

## 4. หลักฐานใหม่ที่ใช้ต่อได้และข้อจำกัด

[REPLAY-01](evidence/endurance20-20261115/replay01-checkpoint.md): fixtureหนึ่งowner
มี96000validinputs;อ่าน36.707s แบ่ง SQL+driver8.659s/decoder27.638s ไม่ใช่ fullrebuild
ของ20ownerหรือข้อมูลการเงินจริงครบ282cycles/owner แผนqueryหน้าแรก sort ลงดิสก์
ก่อนLIMIT4096;ผลนี้ไม่ใช่ physical plan ของฐานที่ล้างจากรอบ4

[REPLAY-02 review/refactor](evidence/endurance20-20261115/replay02-refactor.md):
เลิก decode market ซ้ำเฉพาะเมื่อ source_market ไม่มี โดยคง digest/domain/provenance/
metadata/profile/rebase checks; reviewไม่มีfinding;52targetedcasesผ่านก่อนrefactor,
30affectedcasesผ่านหลังrefactorและ22เดิมใช้ต่อได้ production byte-identical
microbenchmarkเดิม1000row×4arm ให้ผลเท่ากัน: control0.388/0.343s,candidate0.235/0.217s
ใช้ยืนยันงานซ้ำที่ลดได้ แต่ห้ามคูณสัดส่วนนี้เพื่อรับประกัน fullrebuild≤60s หรือ4hผ่าน

[R1/R2 runner fixes](evidence/endurance20-20261115/replay01-review-refactor.md)
ป้องกัน hash/evidence failure ข้าม cleanup หรือกลบ exception หลัก พร้อม faultbinding
แต่ยังไม่มี campaign ใหม่ที่ใช้ correctedrunner ฉบับนั้น ห้ามอ้างว่าผ่าน runtime รอบใหม่

สำหรับ lease: controlled tests พิสูจน์ failure/rollback/ownership mechanics ได้
แต่ FENCE-02 sampler error ไม่มี timestamp/stage/statement association พอจะย้อนหา
blocker การไม่พบ lease loss ในรอบ4ไม่ใช่หลักฐานว่าปัญหาความหน่วงเดิมถูกแก้แล้ว

## 5. ช่องว่างในวิธีตรวจที่ควรแก้ในแผนถัดไป

1. ปัญหาหลังครบ4ชม.ทำให้ต้องเสียต้นทุนรอบยาวก่อนพบคอขวดที่ตรวจแยกได้
2. finalfinancial/global oracle อยู่หลัง replay ที่อาจ timeout ทั้ง4รอบจึงยังไม่มี
   final acceptance จากรอบยาวเหล่านี้ ทั้งนี้ countersครบไม่ได้แปลว่ายอดเงินถูกต้อง
3. การเก็บทุกขั้นในงบเดียวยังถูกต้องตามแผน แต่รายละเอียดช่วง fold/evidence/query/
   decode/session ไม่ครบ จึงวิเคราะห์ยาก; ควรเพิ่ม spans โดยไม่ reset/ยกเว้นเวลา
4. ควรเก็บ financial/global readonly oracles หลังระบบ quiescent ก่อนขั้นราคาแพง
   หรือเป็น post-failure evidence ที่ปลอดภัย โดยแยก grade ชัดและไม่ทำให้รอบล้มกลายเป็นผ่าน
   การปรับลำดับต้องเขียน amendment/ทดสอบผลก่อน ไม่แก้ในงานทบทวนนี้
5. ต้องมี bounded sampler failure envelope ก่อนใช้ observer รอบยาวอีกครั้ง:
   stage/time/partial progress/statement association,ไม่เก็บSQL/tokenและไม่เพิ่มdeadline

## 6. ทางเลือกก่อนทดลองใหม่

| ทางเลือก | ขอบเขต / ผลกระทบ | เวลาและข้อจำกัด |
|---|---|---|
| **A — คง60sและตรวจ fullrebuild แยกก่อน (แนะนำ)** | จัดทำ harness/profile ใหม่ก่อนลงมือ ใช้20fixtureowners/ประวัติตลาด96000รายการต่อownerเป็นupper boundของ13ownerที่สำเร็จ95139–95961รายการ พร้อม financial/history shape282cycles/owner และ oracleเดิม ห้ามแทนด้วย positionว่างหรือแค่ countrows ตรวจเงิน/globalเมื่อquiescentแล้ววัด fullreplayเดิมทีละowner≤60s | ประมาณ30–45นาทีต่อ campaign หลัง harness/safetyพร้อม;เสนอ cap60นาทีรวม120s preflight/seed/verification/cleanup งบพัฒนา harnessต้องประเมินจากการ reuse ก่อนเริ่ม ไม่มี4hหรือretryในขอบเขตนี้ |
| **B — ทบทวนความหมาย SLA ก่อนกำหนดงบใหม่** | ระบุว่าอะไรเป็น recovery ที่ผู้ใช้ต้องรอ และอะไรเป็น offline full-history integrity audit;ยังต้องตรวจข้อมูลครบทุกownerและเงินตรง100% แสดงเวลาแยกได้ แต่ห้ามเปลี่ยน pass criterion จนอนุมัติ requirements/plan/validationใหม่ | ทำข้อเสนอเอกสารก่อนได้ประมาณ15–30นาที;ยังบอกเวลาตรวจไม่ได้จน workload/RTOชัด ไม่เสนอ90/120sจากค่า61sที่ล้มอย่างเดียว |
| **C — รัน4ชม.ทันที** | จ่ายต้นทุนยาวทั้งที่ยังไม่พิสูจน์20ownerrebuild และยังขาด sampler failure attribution | ประมาณ4ชม.15–30นาทีต่อครั้ง ไม่แนะนำ;ไม่รับประกันแก้ปัญหาเดิมได้ |

A เป็น **ข้อเสนอ profile** ไม่ใช่ fixtureที่พัฒนา/พิสูจน์แล้ว การสร้าง financialfacts
และ valid source payload ต้อง reuse production/domain fixtures คง constraints/RLS/
append-only และไม่ส่ง owner/Live orders หากสร้างให้เทียบเคียงไม่ได้ให้หยุดเสนอช่องว่าง
ไม่ลดขนาดหรือข้ามองค์ประกอบเงียบ ๆ แผนถัดไปต้องระบุวิธี seed/counts/digests และ
budget ก่อนอนุมัติให้รัน ตัวเลข96000มาจากหลักฐาน ไม่รับรองประวัติยาวกว่านั้น

เวลาของ A เป็นประมาณการวางแผน: seedหนึ่งowner96000รายการเคยใช้37s แต่20owner
มีปริมาณ/DB distribution ต่างกัน และ fullreplay20คนอาจใช้20นาที จึงไม่เรียกงานนี้ว่า
การตรวจ5นาทีหรือรับประกันเสร็จจากการคูณ benchmark ต้องมีงบหยุดและเก็บผลจริง

## 7. ข้อเสนอแนะและจุดตัดสินใจ

เลือก **A ก่อน**: คงเกณฑ์/ขนาดที่ต้องพิสูจน์และประหยัดการรัน4ชม.ซ้ำ ไม่ใช่ผ่อนให้ผ่าน
หากเจ้าของต้องการเปลี่ยนความหมายของ60sให้เลือกBและตัดสิน requirementก่อน
ไม่อนุมัติBโดยอัตโนมัติจากการเลือกA ไม่ลด correctness/security/trading safety

ด่านก่อนกลับไป4ชม.: profile/safety/reviewพร้อม → fullfinancial/globalและfullrebuild
ครบ20ownerผ่านงบเดิม → observer/failure-cleanupพร้อม → พิจารณาอนุมัติรอบยาวแยก
การผ่านAไม่ปิด lease cause หรือ W3 และไม่แทน100accountRelease/F17dependencies

งานทบทวนนี้จบที่เอกสาร/ทางเลือก ต้องรอเจ้าของเลือกก่อนเพิ่ม harness หรือทดลองใหม่
ตาม AGENTS.md: “เมื่อแก้และตรวจเกณฑ์เดิมแล้วยังไม่ผ่าน 3 รอบ ... ให้หยุดและเสนอ
ทางเลือกพร้อมผลกระทบก่อนทดลองรอบถัดไป” ไม่มี source/test/process/criteria change
ไม่มี tests/campaign/Git/CI ใหม่ และไม่มีผลใดถูกเปลี่ยนเป็นPassedหรือCompleted
