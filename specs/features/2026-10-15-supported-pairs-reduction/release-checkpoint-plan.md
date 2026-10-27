# F-38 — Release checkpoint plan

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-24**

วันที่จัดทำ: 2026-10-24

อ้างอิง:

- `requirements.md`, `plan.md` และ `validation.md` ของ F-38 ที่อนุมัติแล้ว
- `specs/standards/testing.md` หัวข้อ 7
- `specs/roadmap.md` ชุดที่ 9
- F-11 `performance-plan-v2.md` เฉพาะเกณฑ์ที่ F-38 อ้างถึง
- F-12 V-17 deterministic full rerun วันที่ 2026-10-23

## เป้าหมาย

ปิด F-38 V-12, V-13 และ V-15 โดยไม่เปลี่ยน requirements, threshold หรือ production
behavior และไม่ใช้ smoke/ผล historical 30-series แทนการตรวจรับปัจจุบัน จากนั้นจึงเปลี่ยน
F-38 จาก `Development Complete` เป็น `Completed` ได้

รอบนี้ไม่ปิด F-11, F-15 หรือชุดที่ 9 ทั้งชุด และไม่อนุญาต production PREPARED,
Live Trading หรือการเปิดให้คนนอกโดยอัตโนมัติ

## Candidate และ isolation

- ใช้ clean worktree branch `validation/f38-release-checkpoint` จาก `main`
  revision `076a4b2bc676c7d46fdd969301f68fdf189d850d` เป็นจุดเริ่มต้น
- ไม่รวม working-tree diff ของ F-37 ซึ่งเปลี่ยน catalog, migration และ worker topology
- ใช้ PostgreSQL/Redis/container names, ports และ volumes แยกจาก development/F-37
- ห้ามใช้ฐาน application หรือ backup ที่มี secret; automated validation ห้ามเรียก private
  venue/order endpoint และห้ามส่ง Live order
- ตรึง source revision, image digest, lockfiles, runtime versions, Compose effective config,
  CPU/RAM limits และ database settings ไว้ใน evidence ก่อนเริ่ม measured phase

หากต้องแก้ production source, migration, dependency หรือ workload evaluator ให้หยุดรอบยาว,
review diff และรัน affected gates ใหม่ก่อนสร้าง candidate ใหม่ ผลจาก candidate เก่าห้ามนำมา
ปิดเกณฑ์ที่ source เปลี่ยน

## หลักฐานเดิมที่จะใช้ซ้ำ

| หลักฐาน | การใช้ในรอบนี้ | เหตุผล |
|---|---|---|
| F-38 V-01–V-11/V-14/V-16 | ใช้ต่อเมื่อ provenance audit ยืนยัน source/dependency ที่พึ่งไม่เปลี่ยน | ผ่าน candidate/merge แล้ว |
| F-11 R2-C1 วันที่ 2026-10-23 | ใช้ปิด bootstrap/readiness ส่วน BTC+ETH 16 series และ BTC workload 8 series | เป็นผลหลัง pair-scope amendment บน immutable candidate |
| F-11 R2-7 วันที่ 2026-10-23 | ใช้ปิด max-input/resource/parity ที่ C6 อ้างถึง | exact 525,600 slots ผ่าน threshold เดิม |
| F-12 V-17 วันที่ 2026-10-23 | ใช้ประกอบ chart workload/resource/recovery BTC 8 timeframe | runtime/fixture/evaluator ที่พึ่งไม่เปลี่ยนจาก merge evidence |
| F-11 C2 วันที่ 2026-10-14/15 | ไม่ใช้ปิด F-38 | เป็นผล 30-series historical และไม่มี metadata 2/1/8 ตาม F-38 |
| F-15 W4 วันที่ 2026-10-20 | ไม่ใช้ปิด F-38 V-15 | ไม่ใช่การคืน backup ก่อน destructive migration 0030 |

ก่อนใช้หลักฐานเดิม ให้บันทึก diff/provenance จาก candidate ของหลักฐานถึง revision รอบนี้
ตาม `testing.md` หัวข้อ 7 หากยืนยัน dependency ไม่ได้ให้รันส่วนนั้นใหม่

## ลำดับดำเนินงาน

### 1. Preflight และ harness smoke

1. ตรวจ effective catalog: runtime readiness = BTC/USDT และ ETH/USDT × 8 timeframe
   รวม 16 series; workload = BTC/USDT × 8 timeframe
2. ตรวจ harness isolation guard, output directory ใหม่, metrics sampler, cleanup และ network guard
3. รัน smoke สั้นเฉพาะเพื่อพิสูจน์ setup/evaluator ไม่ใช้ผล smoke ปิดเกณฑ์เต็ม
4. ยืนยันว่า evaluator เขียน metadata ต่อไปนี้ในทุก phase:
   `supported_runtime_pairs=2`, `runtime_readiness_series=16`, `profile_pairs=1`,
   `profile_series=8`

### 2. Capacity/workload สำหรับ V-12 และ V-13

ใช้ `backend/tests/services/indicator_builder/profile_capacity.py`,
`profile_capacity_steady.py`, `profile_capacity_evidence.py` และ harness fairness/global protocol
เดิม ไม่สร้าง threshold ใหม่

1. Reconfirm R2-C1 หาก provenance audit ใช้ผลเดิมไม่ได้
2. รัน combined steady + rejected-load เต็ม 60 นาทีบน BTC 8 series เพียงรอบเดียวเพื่อปิด
   R2-C2 และ R2-C5-steady พร้อมกัน โดย accepted workload ต้องผ่านเกณฑ์ steady-state เดิม
   และ rejected BUSY/rate load ต้องผ่านเกณฑ์ C5 เดิม
3. หลัง combined steady ผ่าน รัน combined dirty/recovery + rejected-load เต็ม 60 นาทีเพียง
   รอบเดียวเพื่อปิด R2-C3 และ R2-C5-dirty พร้อมกัน: invalidate ทั้ง 8 workload series,
   กลับ READY/GET 200 ภายใน 600 วินาที, availability อย่างน้อย 80% ต่อ series และหลัง recover
   ต้องพร้อม 100% จนจบ phase รวมทั้ง rejected-load gate เดิม
4. R2-C4 fairness: เก็บ first eligible, queue wait, claim/build/retry/publish,
   dispatch round, pause/deadline miss, max head age และ max unavailable interval ต่อ series;
   ตรวจ R2-S1–S5 โดยไม่มี starvation เกิน 600 วินาที
5. R2-C5 under load ใช้หลักฐานจากสอง combined phase ในข้อ 2–3; rejected load ต้องถูก
   ปฏิเสธก่อน candle query และไม่ถูกตัดออกเพื่อทำ availability ให้ดีขึ้น ห้ามรัน C2/C3 แบบ
   ไม่มี rejected load แล้วนำมาแทน combined evidence
6. R2-C6 aggregate gate: C1–C5, R2-7, worker ≤120 วินาที, RSS ≤128 MiB,
   event-loop lag ≤100 ms, parity และผลราย series ต้องครบ ไม่มี missing/skipped series

ทุก phase ต้องเก็บ scheduled samples/probes ครบ รวม 429/503/BUSY/timeout ใน denominator
ตามสัญญาเดิม และเก็บผล Failed/Partial ไว้หากเกิดขึ้น

R2-G7/D7 และ release gates อื่นที่ไม่ได้เป็น dependency ของ F-38 V-12/V-13 ยังคงอยู่ใน
ทะเบียน F-11; รอบนี้จะไม่เปลี่ยนสถานะของเกณฑ์เหล่านั้น เว้นแต่ provenance audit พบว่า C6
ของ candidate นี้พึ่งเกณฑ์ดังกล่าวโดยตรง ซึ่งต้องบันทึกก่อนรัน

### 3. Backup/restore drill สำหรับ V-15

1. สร้าง production-like fixture ที่ migration 0029 มี BTC/ETH/SOL/XRP/DOGE ครบในทุก
   market/indicator table และมี user/session/audit รวมทั้ง order/balance/position หาก schema
   revision ที่ใช้มีตารางเหล่านั้น
2. หยุด writers และยืนยัน builder IDLE; บันทึก revision, row counts และ deterministic digests
   แยก table/base รวมทั้งตารางนอกขอบเขต
3. สร้าง PostgreSQL custom-format backup ไปยังพื้นที่ชั่วคราวนอก repository และบันทึก
   checksum/ขนาดโดยไม่บันทึก credential
4. รัน migration 0030 และ verifier เดิมเพื่อยืนยันว่า purge/constraints ทำงาน
5. สร้างฐาน disposable ใหม่แล้ว `pg_restore` จาก backup; ห้าม restore ทับฐานที่กำลังรับ write
6. ตรวจ revision/count/digest/FK/RLS/grants และยืนยันว่าข้อมูลก่อน migration รวมคู่ที่ถูก purge
   กลับมาครบ จากนั้นรัน upgrade 0030 ซ้ำบนฐาน restored และตรวจ postconditions อีกครั้ง
7. บันทึกเวลาตั้งแต่เริ่ม restore ถึงฐานผ่าน verification ทั้งหมด พร้อมปริมาณข้อมูลที่กู้คืน
8. ลบเฉพาะ disposable containers/volumes ที่รอบนี้สร้างหลังเก็บ evidence แล้ว; เก็บ backup
   artifact ตาม retention ที่เจ้าของอนุมัติ

### 4. Review และปิดเอกสาร

1. ตรวจ raw artifacts กับ evaluator output; ห้ามเปลี่ยน Failed/Partial เป็น Passed ด้วยการสรุปมือ
2. Review diff และ evidence เน้น isolation, denominator, catalog counts, resource bounds,
   destructive restore และการไม่แตะ Live/order path
3. ถ้ามี source/harness change ให้รัน affected tests/static gates และ candidate gates ตามผลกระทบ;
   ถ้าเป็น docs/evidence อย่างเดียว ใช้ผลเดิมที่ provenance ยัง valid และตรวจเอกสาร/diff
4. เมื่อ V-12/V-13/V-15 ผ่านทั้งหมด จึงอัปเดต F-38 `validation.md`, evidence และ `roadmap.md`
   เป็น `Completed`; คง F-11/F-15/ชุดที่ 9/production PREPARED ตามผลจริงของแต่ละงาน
5. ไม่ commit หรือ push จนกว่าเจ้าของสั่ง

## การตัดสินใจหลังอนุมัติ

### NC-F38-RC-01 — RPO/RTO — Closed 2026-10-24

เจ้าของอนุมัติค่าต่อไปนี้สำหรับ disposable release drill:

- **RPO = 0 committed rows หลัง writers ถูกหยุด** เทียบกับ quiesced pre-migration snapshot
  ด้วย exact counts/digests ทุกตารางที่กำหนด
- **RTO ≤ 30 นาที** นับจากเริ่ม `pg_restore` จน verification ของ revision/count/digest/FK/
  RLS/grants ผ่านทั้งหมด ไม่รวมเวลาเตรียม fixture หรือสร้าง backup

ค่าดังกล่าวใช้เฉพาะรอบตรวจรับ F-38 นี้ ไม่ได้กำหนด production backup schedule หรือ SLA
ของระบบทั้งหมด

## จุดหยุด

หลังเจ้าของอนุมัติ plan, validation และ NC-F38-RC-01 แล้วจึงเริ่ม preflight/smoke และรันชุดยาว
ตามลำดับข้างต้น หากรอบใดล้มด้าน correctness/safety ให้หยุดรอบถัดไปที่พึ่งผลนั้น วิเคราะห์สาเหตุ
และแก้เฉพาะภายในขอบเขตที่อนุมัติ; หากต้องเปลี่ยน threshold, architecture หรือ requirements
ให้หยุดขออนุมัติ amendment ก่อน

## Amendment หลัง RC-04 Failed — Approved 2026-10-25

เจ้าของอนุมัติให้วิเคราะห์และแก้ production performance หลัง `capacity/c2-r7` พบ
accepted-request event-loop lag `0.195341292s` เกินเกณฑ์ `0.1s` โดยมีเงื่อนไขดังนี้:

- คง duration, correctness, freshness, query/resource bounds และ event-loop lag ≤100ms เดิม
- ห้ามเปลี่ยนสูตร indicator, money semantics, trading behavior หรือ Live Trading
- เมื่อ production source เปลี่ยน หลักฐาน measured ของ candidate เก่าห้ามใช้ปิดเกณฑ์ที่ได้รับผล;
  ต้อง build immutable candidate ใหม่และรัน affected correctness/static/resource gates ก่อน
- กลับมารัน C1–C6 ตาม dependency เดิม แล้วจึงทำ V-15 และ final crosswalk

Amendment นี้อนุญาตเฉพาะการแก้ performance ที่จำเป็นต่อ RC-04/RC-08 ไม่อนุญาตให้ลด
threshold หรือเปลี่ยน architecture โดยไม่ขออนุมัติเพิ่ม

## Amendment สำหรับ dedicated validation และ V-15 quiesced fixture — Approved 2026-10-25

เจ้าของอนุมัติให้ใช้ช่วงตรวจรับ Docker แบบ dedicated โดยมีขอบเขตดังนี้:

- บันทึกสถานะ container ที่กำลังทำงานก่อนเริ่ม แล้วหยุด development และ F-11 containers
  ชั่วคราวระหว่าง measured validation
- เมื่อจบช่วงตรวจรับให้เริ่มใหม่เฉพาะ container ที่บันทึกว่ากำลังทำงานก่อนเริ่ม
- ห้ามลบ volume หรือเปลี่ยนข้อมูลของ environment เหล่านั้น และคง duration/threshold เดิมทั้งหมด

สำหรับ V-15 ให้ตีความ production-like quiesced pre-0030 fixture ตามสถานะที่ schema อนุญาต:

- ตาราง market, jobs, generations, checkpoints, retry requests และ source changes ที่เก็บแถวได้
  ต้องมี BTC/ETH/SOL/XRP/DOGE ครบ
- `indicator_generations` ใช้สถานะ `EXPIRED` และ `indicator_heads` ต้องว่าง เพราะ
  `begin_indicator_source_maintenance()` ทำให้ active generation หมดอายุและลบ head ทั้งหมด
- ต้องตรวจ digest ของ user/session/audit และตารางนอกขอบเขตเหมือนเดิม

Amendment นี้เปลี่ยนเฉพาะ fixture และ isolation ของการตรวจรับ ไม่เปลี่ยน migration, product
behavior, RPO=0, RTO≤30 นาที หรือเกณฑ์ capacity/resource ใด ๆ

## Amendment รวม capacity phases เหลือสองชั่วโมง — Approved 2026-10-25

เจ้าของอนุมัติให้รวม measured capacity phases จากสี่รอบเหลือสองรอบ โดยไม่ลดเวลาหรือ
threshold ของรอบใด:

- combined steady + rejected-load 3,600 วินาทีออกผลทั้ง `R2-C2` และ `R2-C5-steady`
- combined dirty/recovery + rejected-load 3,600 วินาทีออกผลทั้ง `R2-C3` และ
  `R2-C5-dirty` และเริ่มได้เมื่อ combined steady ผ่านทั้งสอง gate แล้ว
- แต่ละรอบต้องเก็บ accepted samples/probes และ rejected BUSY/rate requests ครบ denominator
  เดิม ตรวจ rejected candle-query count = 0 และใช้ resource/correctness/freshness/recovery
  threshold เดิมทุกข้อ
- การรวมหลักฐานใช้ได้เพราะ workload ที่มี rejected load เป็นกรณีเข้มกว่าของ C2/C3 เฉพาะเมื่อ
  evaluator พิสูจน์ว่า rejected request ถูกปฏิเสธก่อน candle query และไม่กิน accepted quota;
  ถ้าพิสูจน์ข้อนี้ไม่ได้ ทั้ง C2/C3 และ C5 ของ phase นั้นต้อง Failed
- ห้ามรันสอง combined phases พร้อมกันบน host เดียวกัน และห้ามใช้ smoke/partial duration ปิด gate

Amendment นี้เปลี่ยนเฉพาะ orchestration และ mapping ของหลักฐาน ลด measured wall-clock จาก
สี่ชั่วโมงเหลือสองชั่วโมง ไม่เปลี่ยน product behavior, workload, denominator หรือเกณฑ์รับใด ๆ
