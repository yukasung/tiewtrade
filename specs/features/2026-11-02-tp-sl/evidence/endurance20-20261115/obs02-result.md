# OBS-02 — refactor และหนึ่ง short diagnostic

สถานะ: **Diagnostic Complete — ไม่เกิด timeout ซ้ำใน fixture นี้; ยังไม่ยืนยันสาเหตุ W3**
[Plan](../../observer-short-diagnostic-plan.md) / [Summary](obs02-result-summary.json)

Refactor เฉพาะ negative-test data matrix ตัด lookup/branch ซ้ำ ไม่เปลี่ยน runner behavior
12 affected cases Passed, Ruff/format/mypy Passed; reuse real-PG/35cases จาก M1
ที่ runtime ไม่เปลี่ยน หลักฐาน hash ตรงกับ candidate ระหว่าง campaign

Preflight Passed 7/7; หนึ่ง campaign ใช้เวลารวม136.3166s (2m16s) รวม cleanup
ครบ30captures (10ต่อกลุ่ม) ไม่มี error/retry/timeout และไม่ส่ง orders

| Fixture | Median total | Max total |
|---|---:|---:|
|cold connection|76.765 ms|80.649 ms|
|reused observer รวม first connection|11.678 ms|56.147 ms|
|known blocker รวม first connection|13.355 ms|38.153 ms|

Cold checkout/setup median53.830ms/max56.380ms; activity median15.684ms/max17.219ms
Reused activity median1.719ms/max13.565ms; known-blocker activity median1.916ms/max8.735ms
Loop lag170samples/max27.132ms เก็บแบบaggregate ไม่อ้าง correlation กับแต่ละ query
ช่วงเวลาทั้งหมดรวม driver/scheduling ไม่ใช่ server execution ล้วน
known-blocker ทั้ง10samplesยืนยัน holderในblocking_pids และ waiterlockยังไม่ได้รับ
ไม่มี synthetic publication tick ไม่มีการฉีด delay/renew/retry

ก่อน DROP: connections0/advisorylocks0. Independent proof หลังDROP: DB absent,
connections0/locks0; source/config/runner bindings unchanged. ไม่มี Redis/worker ใหม่
ไม่ force drop หรือหยุดบริการอื่น Raw: validation-artifacts/f17-obs02-short-20261116/

## ข้อจำกัด / ขั้นถัดไป

รอบนี้แสดงว่าตัว collector เก็บหลักฐานได้ใน fixture เล็ก และ cold connection มีต้นทุน
แต่ยังไม่พิสูจน์ว่าต้นทุนนี้เป็นสาเหตุ timeout W3 ซึ่งเกิดขณะ20workersรับโหลดจริง
ห้ามสรุปว่าสาเหตุแก้แล้วหรือเพิ่ม timeout จากผลนี้ คง OBS-01 Incomplete/poolerrorsเดิม
ไม่ได้รัน4hหรือ finalfinancial/global/replay acceptance; F17ยังไม่Completed

จบหนึ่ง campaign แล้วหยุดตามแผน ไม่มี Git/CI/merge หรือรันทดแทนอัตโนมัติ
ข้อเสนอถัดไป: จัดทำแผนวัด observer timing ภายใต้โหลดสั้น20บัญชีที่มีขอบเขต
เพื่อแยกจาก baseline นี้ ก่อนเปลี่ยน collector/publisher หรือทดสอบ4hใหม่
ยังไม่ได้อนุมัติหรือเริ่ม workload เพิ่มจากข้อเสนอนี้
