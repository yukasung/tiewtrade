# F-15 — จำลองการจับคู่ออเดอร์ Paper — Requirements

สถานะ: **Approved** — ฉบับฐาน/NC-F15-01–08 ได้รับอนุมัติแล้ว 2026-10-18
วันที่: 2026-10-18
Branch: feature/f-15-paper-order-matching

## ทำไมต้องมี

F-13 มีกระเป๋าและรอบ Paper ส่วน F-14 รับ execution fact เพื่อคำนวณ position/PnL
ได้แล้ว แต่ยังไม่มีตัวสร้างผลจับคู่จำลองและแหล่ง authoritative ของออเดอร์ค้าง
จึงยังเทรด Paper ไม่ได้และยังพิสูจน์เงื่อนไข reset ของ F-13 ได้ไม่ครบ

R-17 ต้องการ Paper ที่เหมือนจริงมากที่สุด แต่ราคาซื้อขายล่าสุดเพียงค่าเดียว
ไม่ได้บอก bid/ask, depth, ลำดับคิว หรือปริมาณที่ออเดอร์ของเราจะจับคู่ได้จริง
ADR-004 จึงกำหนดให้กฎจำลองและค่าที่ใช้ต้องอนุมัติใน F-15 โดยเฉพาะ
เอกสารนี้รวบรวมข้อกำหนดจาก spec เดิมและคำตัดสินของเจ้าของสำหรับ F-15
คำตอบ “อนุมัติ” วันที่ 2026-10-18 อนุมัติชุดที่แนะนำในหัวข้อคำตัดสินด้านล่าง
ทางเลือกอื่นที่ยกมาเปรียบเทียบไม่ได้ถูกเลือก

## ขอบเขต

### ทำในงานนี้

- ตัวจำลอง execution ของ Paper Spot สำหรับ Binance TH โดยคำสั่งเพิ่มความเสี่ยง
  ต้องใช้รายการคู่ที่ระบบรองรับ ปัจจุบันคือ BTCUSDT และ ETHUSDT ตาม F-38;
  ไม่สร้างรายการคู่แยกอีกชุด การลด position และยกเลิกออเดอร์เดิมต้องไม่ถูกปฏิเสธ
  เพียงเพราะคู่ถูกถอนจากรายการ ตาม trading-safety §3/8 และ RQ-26
- วงจรชีวิตออเดอร์ การยกเลิก และผลจับคู่ตามชนิดคำสั่งและนโยบายที่จะอนุมัติ
- เชื่อมผลจำลองเข้า execution contract/position writer ของ F-14 และรายการเงิน F-13
- การกันเงิน/สินทรัพย์สำหรับออเดอร์ค้างตามนโยบายที่จะอนุมัติ เพื่อป้องกันใช้ยอดซ้ำ
- authoritative open-order activity และการประสานกับ position activity ภายใต้ single writer
  รวม initialization พร้อมหลักฐานสำหรับ episode เดิมและใหม่ก่อนรับ fill แรก
- recovery, idempotency, isolation และประวัติตรวจสอบการเปลี่ยนแปลงการเงิน

### ไม่ทำในงานนี้

- ไม่ส่งหรือยกเลิกออเดอร์จริง ไม่อ่าน credential หรือ balance จริงของผู้ใช้
- ไม่ทำ Futures, short, leverage, margin debt หรือ liquidation
- ไม่ทำหน้าสั่งออเดอร์ F-16, TP/SL/bracket F-17, risk-limit workflow F-18,
  kill switch F-19, strategy/bot F-20/F-21 หรือ Live execution/reconciliation F-22/F-23
- ไม่เพิ่มข้อมูลตลาดชนิดใหม่โดยถือว่า F-10 รองรับแล้ว; ถ้าต้องใช้ bid/ask/depth
  ต้องตัดสินขอบเขตและข้อกำหนดข้อมูลเพิ่มใน NC-F15-02 ก่อน
- ไม่รับรองว่าราคา fill หรือกำไรจำลองจะเท่าตลาดจริง และไม่ลด safety gates เพื่อเปิดใช้เร็วขึ้น
- ไม่เปิด reset success อัตโนมัติเพียงเพราะมี source ใหม่; integration amendment
  และการตรวจรับร่วมกับ F-13/F-14 ต้องผ่านการอนุมัติก่อนตาม NC-F15-06

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | Paper executor ต้องรับคำสั่งผ่าน contract และการตรวจคำสั่งร่วมตาม ADR-004; strategy ต้องไม่ส่งออเดอร์เอง และการเลือก executor ต้องอยู่ที่ server composition boundary | ADR-004; architecture §1/3 |
| RQ-2 | Paper path ห้ามส่งคำขอออเดอร์หรือเรียก credential/Live executor/ข้อมูลเงิน Live; ข้อมูลตลาดต้องรับเป็น input ผ่านขอบเขตที่แยกจากการจำลอง ไม่ต่อเครือข่ายจาก pure core | trading-safety §1; architecture §2; ADR-004 |
| RQ-3 | ผลจำลองต้อง deterministic เมื่อ order, สถานะตั้งต้น, ลำดับข้อมูลตลาด, เวลา และนโยบายเดียวกัน ห้ามใช้ AI หรือค่าสุ่มในการคำนวณเงิน/ปริมาณ; เวลาและรหัสต้องส่งเข้ามาเป็น input | AGENTS.md ข้อ 6; architecture §2 |
| RQ-4 | เงิน ราคา มูลค่า fee และปริมาณต้องใช้ Money/Quantity และกฎหน่วย/ช่วงค่า/การปัดของ tiewtrade.core.money เท่านั้น ห้ามใช้ float หรือ Decimal เปล่าคำนวณหรือสร้างกฎปัดแยก | AGENTS.md ข้อ 6; F-14 RQ-2 |
| RQ-5 | ชนิดออเดอร์, time-in-force, หน่วยขนาดคำสั่ง และเงื่อนไขยอมรับต้องกำหนดชัดก่อน implementation; คำสั่งที่อยู่นอกขอบเขตที่อนุมัติต้องปฏิเสธ ไม่แปลงชนิดหรือเดาความหมาย | NC-F15-01; trading-safety §3 |
| RQ-6 | ราคา ปริมาณ fill, partial fill, slippage, latency และลำดับการจับคู่ต้องมาจากโมเดลที่อนุมัติพร้อม provenance/version ของนโยบายและข้อมูลต้นทางที่ตรวจสอบซ้ำได้ ห้ามถือว่าแตะราคาแล้ว fill ทั้งใบโดยไม่มีข้อกำหนดรองรับ | R-17; ADR-004; NC-F15-02/03 |
| RQ-7 | ห้ามใช้ข้อมูลตลาดในอนาคตสร้างผลย้อนหลังหรือใช้ snapshot เดียวสร้างสภาพคล่องซ้ำเกินโมเดลที่อนุมัติ; การรับข้อมูลซ้ำ ย้อนลำดับ หรือมีช่องว่างต้องมีผลที่กำหนดและตรวจสอบได้ | deterministic/recovery; NC-F15-02/03 |
| RQ-8 | ตรวจความพร้อมและ freshness ฝั่ง server ก่อนใช้ข้อมูลจริง ราคา F-10 ใช้กฎเดิม: อายุเกิน 10 วินาทีใช้ไม่ได้และ feed หลุดเป็นไม่พร้อมทันที; ห้ามอ้างเกณฑ์นี้ว่ารับรอง depth/ข้อมูลใหม่ซึ่งยังไม่มี contract และห้ามสร้าง fill จากข้อมูลที่พิสูจน์ไม่ได้ | F-10 NC-25/26; trading-safety §6/10 |
| RQ-9 | อัตรา fee, maker/taker, สินทรัพย์ที่เก็บ, ส่วนลด/rebate และเวลาที่นโยบายเริ่มมีผลต้องได้รับอนุมัติ ไม่ใช้ค่าศูนย์หรือ hardcode อัตราตลาดโดยเดา; ผล fee ส่งผ่าน execution fact ให้ F-14 ใช้กฎ NC-46 เดิม | ADR-004; F-14 NC-46; NC-F15-04 |
| RQ-10 | การตรวจคำสั่งต้องครอบคลุมข้อจำกัดคู่เทรดและยอดใช้ได้หลังหักภาระออเดอร์ค้าง ห้ามซื้อด้วยเงินก้อนเดียวซ้ำ ขายสินทรัพย์เกินที่ถือ หรือสร้าง Spot short; กฎกันยอด/เผื่อ fee/ปล่อยยอดต้องกำหนดตาม NC-F15-05 | trading-safety §3; F-14 RQ-3 |
| RQ-11 | คำสั่งเพิ่มและลดความเสี่ยงต้องผ่าน safety gates ร่วมตามมาตรฐาน ห้ามทำทางลัดใน simulator เมื่อ gate/dependency ที่จำเป็นยังไม่มีหรือไม่พร้อมต้องไม่กล่าวอ้างว่ารับคำสั่งได้อย่างปลอดภัย; ขอบเขตการเปิดใช้งานก่อน F-18 อยู่ใน NC-F15-06 | trading-safety §3/13; ADR-004 |
| RQ-12 | แยก accepted/pending, partially filled และ terminal outcomes ให้ผู้เรียกไม่สับสนระหว่างรับคำสั่งกับจับคู่สำเร็จ; fill เปลี่ยนเงิน/position เฉพาะปริมาณที่ยืนยันแล้ว ไม่ถือ partial fill เป็นทั้งใบ | trading-safety §6/11; F-14 RQ-4/13 |
| RQ-13 | ทุก order/command/fill ต้องมี identity ถาวรและตรวจ retry ได้ คำขอเดิมหรือ execution เดิมซ้ำต้องคืนผลเดิมโดยไม่เพิ่มผลการเงิน; identity เดิมแต่ payload ขัดกันต้องปฏิเสธ/ระบุ conflict ไม่ทับประวัติ | trading-safety §4/10; F-14 RQ-5/6 |
| RQ-14 | การรับ/ยกเลิก/จับคู่ที่แข่งกันต้องมีลำดับ authoritative เดียวต่อผู้ใช้/โหมด/รอบ; ยกเลิกไม่ย้อน fill ที่ commit แล้ว และห้ามยกเลิกกับ fill ทำให้คืนเงินหรือปริมาณซ้ำ | trading-safety §4/10; NC-F15-03/05 |
| RQ-15 | order state, fill facts, reservation, ledger, position/PnL, source revision และ audit ที่เกี่ยวข้องต้อง commit อย่างสอดคล้องใน transaction ภายใต้ financial writer protocol เดียวกับ F-13/F-14 ห้ามมีเงินหักแล้วแต่ fill/position ไม่บันทึก | trading-safety §4/9; F-14 RQ-7 |
| RQ-16 | ใช้ execution contract และ position calculation ของ F-14 ไม่เขียน weighted-average cost/PnL/fee treatment อีกชุด; คง source sequence, completeness และ append-only correction semantics ตาม NC-48/50 | F-14 requirements/plan; ADR-004 |
| RQ-17 | ข้อมูลต้องผูก user, Paper mode, episode และ order/fill identity ที่ server ตรวจ; ห้ามเขียนเข้า episode ที่ปิดแล้วหรือใช้ผลจากรอบเก่าในรอบใหม่ และห้ามข้อมูลข้ามผู้ใช้/โหมดรวมใน read หรือ cache | F-13 RQ-7/9/11; F-14 RQ-8/9/15 |
| RQ-18 | authoritative open-order source ต้องแยกมีออเดอร์ค้าง/ยืนยันไม่มี/unknown พร้อม revision/provenance; source ไม่ครบ, row หาย, recovery ไม่เสร็จ หรือ error ห้ามแปลว่า idle และห้ามนับเฉพาะ order ที่แสดงบนหน้าเว็บ | F-13 RQ-6; F-14 ความสัมพันธ์กับ F-15 |
| RQ-19 | reset ต้องตรวจทั้ง position และ open order พร้อม source completeness ภายใต้ synchronization boundary เดียวกับ writers; order/fill ที่แข่งกับ reset ต้องไม่เขียนเข้า episode ที่ reset ปิดแล้ว การเปิดเส้นทางนี้ต้องผ่าน amendment ตาม NC-F15-06 | F-13 RQ-6/7; F-14 RQ-14/15 และ plan §1 |
| RQ-20 | หลัง crash/restart/timeout/commit outcome ไม่แน่ชัดต้องอ่าน durable facts และพิสูจน์ผลเดิมก่อนทำต่อ; ห้ามสร้าง fill ใหม่ชดเชยจากการเดา และห้ามประกาศ activity พร้อมก่อนกู้สถานะ/ตรวจความครบสำเร็จ | trading-safety §4/10; F-14 source completeness |
| RQ-21 | ประวัติ order event, execution และรายการเงินต้องตรวจสอบย้อนกลับได้และเพิ่มอย่างเดียว การแก้ fact ต้องใช้ contract correction ที่อนุมัติ ไม่ UPDATE/DELETE ประวัติ; แยก projection ที่ rebuild ได้จากประวัติจริง | trading-safety §9; F-13 RQ-4; F-14 RQ-10 |
| RQ-22 | snapshot/read ต้องสอดคล้องหนึ่ง revision และระบุเวลา/ความพร้อม/โหมด/episode; error แยก input, insufficient funds, unsupported order, stale data, conflict และ source unavailable ได้โดยไม่เผย secret หรือรายละเอียดฐานข้อมูล | F-14 RQ-11/16/19; trading-safety §12 |
| RQ-23 | ต้องพิสูจน์ parity ของ contract/ตรรกะร่วมด้วย fixture เดียวกัน พร้อม isolation, idempotency, partial fill, cancellation race, เงินไม่ถูกใช้ซ้ำ, recovery และ reset race ตามผลกระทบจริง; automated validation ห้ามส่ง Live order | ADR-004; AGENTS.md การตรวจสอบ |
| RQ-24 | F-15 เป็น source owner ฝั่ง Paper ที่รับผิดชอบ initialization ของ position source F-14 และ open-order source สำหรับ episode ที่มีอยู่ก่อนเปิดใช้ F-15, episode ที่สร้างใหม่ และ episode หลัง reset เมื่อ integration ได้รับอนุมัติแล้ว ก่อนรับ fill แรกต้องพิสูจน์ baseline, source sequence/completeness และ proof revision ภายใต้ financial lock เดียวกับ writers; baseline/projection และ transition เป็น READY ต้อง commit สอดคล้องกัน ห้ามใช้เพียงการไม่พบ row เป็นหลักฐานว่าง หากพิสูจน์ไม่ได้ให้คง unknown/conflicted และห้าม apply fill การ retry initialization ต้องไม่สร้าง baseline หรือผลการเงินซ้ำ และการเริ่ม source ไม่ถือว่าอนุญาต reset success โดยอัตโนมัติ | F-14 plan §1/4.1/4.3; F-13 RQ-6/7 |
| RQ-25 | F-15 ต้องลงรายการเงินจาก exact quote cash effects ที่ F-14 คืนและรักษา invariant ต่อ episode/quote currency ว่า wallet balance เท่ากับทุนตั้งต้นบวก quote cash effects ทั้งหมด รวม compensating effects ของ correction; ห้ามเครดิต realized PnL เพิ่มซ้ำกับรายรับขายหรือหัก fee ซ้ำกับ effect ที่รวม fee แล้ว การ REPLACE/VOID ต้อง append compensating ledger effects ตามผล rebuild โดยไม่แก้รายการเดิม และ exact replay ต้องมีผลการเงินเพิ่มเป็นศูนย์ การกัน/คืนยอดเปลี่ยน available/reserved ตาม NC-F15-05 โดยไม่สร้างหรือลบเงินจากยอดรวม; fee สินทรัพย์ที่สามคงหน่วยเดิมตาม F-14 และไม่แปลงเข้ายอด quote โดยเดา | F-14 plan §3/4.2; F-14 NC-46/48/50; F-13 RQ-4/9 |
| RQ-26 | การตรวจ allowlist ต้องใช้กับคำสั่งเพิ่มความเสี่ยง; คำสั่งลด position ที่มีอยู่และการยกเลิกออเดอร์เดิมต้องผ่านถึงเส้นทางที่รับผิดชอบได้แม้คู่ถูกถอนจากรายการ โดยตรวจ owner/mode/episode และ safety gates ที่เกี่ยวข้องตามเดิม ห้ามบังคับปิด position จากการถอนคู่ และห้ามถือว่าการรับคำสั่งลดความเสี่ยงคือ fill สำเร็จ หากไม่มีข้อมูลตลาดที่เชื่อถือได้ยังห้ามสร้าง fill ตาม RQ-8; ข้อกำหนดข้อมูลตลาดสำหรับจัดการสถานะเดิมต้องครอบคลุมใน NC-F15-02/03 | mission §6; trading-safety §3/6/8 |

### กรณีที่ validation ต้องครอบคลุมจาก RQ-24–26

รายการนี้เป็นข้อกำหนดการตรวจรับที่จะนำไปลง validation.md หลัง requirements อนุมัติ:

- **Source initialization:** episode เดิมก่อนเปิดใช้ F-15, episode ใหม่ และ episode หลัง
  reset ที่อนุมัติ integration แล้วต้องรับ fill แรกได้เมื่อหลักฐานครบ; missing/conflicting
  proof ต้องไม่กลายเป็น READY ทดสอบ initialization ที่ retry/แข่งกันและล้มก่อน commit
  แล้วกู้คืน โดยไม่มี baseline/fill/ผลการเงินซ้ำ
- **Cash conservation:** ตรวจ invariant หลัง buy, sell, partial fill, fee, reservation/release,
  REPLACE/VOID และ exact replay โดยใช้ exact effects จาก F-14; ตัวอย่างซื้อด้วยต้นทุน
  100 USDT แล้วขายรับสุทธิ 120 USDT ต้องทำให้เงินสุทธิเพิ่ม 20 USDT จากก่อนซื้อ
  ไม่เพิ่ม realized PnL อีก 20 USDT ซ้ำ และ retry ต้องไม่เปลี่ยนยอดอีก
- **คู่ถูกถอน:** เมื่อมี position/ออเดอร์เดิมแล้วถอนคู่จาก allowlist คำสั่งเพิ่มความเสี่ยง
  ต้องถูกปฏิเสธ แต่การลด position/ยกเลิกต้องไม่ถูกปฏิเสธด้วยเหตุ allowlist;
  คงการตรวจสิทธิ์และขนาดที่ถือจริง รวมกรณีข้อมูลตลาดไม่พร้อมซึ่งห้ามสร้าง fill สมมติ

## ของเดิมที่ตรวจพบเพื่อใช้วางแผนหลัง requirements อนุมัติ

- `backend/src/tiewtrade/core/money/`: ชนิดเงิน/ปริมาณและ arithmetic กลาง
- `backend/src/tiewtrade/core/positions.py` และ `infra/positions/{records,storage}.py`:
  execution facts, position projection และ activity protocol ของ F-14
- `backend/src/tiewtrade/core/paper_wallet.py` และ `infra/paper_wallet/{records,storage}.py`:
  episode, ledger, durable command และ financial lock ของ F-13
- `backend/src/tiewtrade/infra/market_data/{realtime_storage,realtime_records}.py`:
  latest-trade readiness/provenance ของ F-10; ไม่ใช่ order-book source
- `specs/decisions/004-shared-paper-live-trading.md`: contract/ตรรกะร่วมและขอบเขต isolation

รายการนี้เป็นหลักฐานการค้นเบื้องต้น ไม่ใช่ plan ที่อนุมัติหรือการรับรองว่า contract
ปัจจุบันครอบคลุม matching แล้ว รายละเอียดการใช้ซ้ำ/การขยายต้องอยู่ใน plan.md ขั้นถัดไป

## กฎความปลอดภัยที่เกี่ยวข้อง

อ้าง `standards/trading-safety.md` §1 (isolation), §3 (ตรวจคำสั่ง), §4
(idempotency/single writer), §6 (ข้อมูลไม่พร้อม/partial fill), §9 (audit/ledger),
§10 (recovery), §11 (ผล partial fill สำหรับงาน TP/SL ภายหลัง), §12
(readiness) และ §13 (loss limit) โดยไม่ลดกฎหรือเพิ่มกฎการเทรดเอง

## ยังไม่ชัด — Needs Clarification

NC-F15-01–06 ทั้งหมด **Closed — เจ้าของอนุมัติ 2026-10-18** ตามชุดที่แนะนำ
ในหัวข้อคำตัดสินด้านล่าง; **NC-F15-07 Closed — เจ้าของอนุมัติ 2026-10-18** ตาม amendment ท้ายเอกสาร
ตารางนี้เก็บคำถามเดิมและขอบเขตที่คำตัดสินครอบคลุมเพื่อให้ตรวจสอบย้อนกลับได้
plan.md และ validation.md ยังต้องผ่านการอนุมัติแยกก่อน implementation

| รหัส | เรื่องที่เจ้าของต้องตัดสิน | บล็อกอะไร |
|---|---|---|
| NC-F15-01 | รุ่นแรกใช้ชนิดคำสั่งและ time-in-force ใด เช่น MARKET, LIMIT/GTC, IOC/FOK; รับขนาดเป็น base quantity, quote budget หรือทั้งสอง และแก้คำสั่งผ่าน cancel/new หรือมี amend | order contract และวงจรชีวิต RQ-5/12/14 |
| NC-F15-02 | ความเหมือนจริงระดับใด: ใช้ latest trade ที่มีอยู่โดยยอมรับข้อจำกัด หรือเพิ่ม bid/ask/depth; ถ้าเพิ่มต้องกำหนด source, freshness, gap/reconnect และขอบเขตการเพิ่ม market-data ก่อน ไม่อ้างว่าราคาล่าสุดแทน depth ได้; ระบุแหล่งข้อมูลสำหรับลด position เดิมของคู่ที่ถูกถอนจาก allowlist ตาม RQ-26 ด้วย | ราคา/สภาพคล่อง RQ-6/7/8/26 และขอบเขตข้อมูลตลาด |
| NC-F15-03 | กฎ slippage/latency, partial fill, queue priority, การใช้สภาพคล่องร่วมระหว่างออเดอร์/ผู้ใช้, เวลาที่ order เริ่มมีสิทธิ์ fill, ส่วน MARKET ที่จับคู่ไม่ได้ และพฤติกรรมเมื่อ feed ขาด/กู้คืน; ต้องมีสูตร/ค่าหรือแหล่งข้อมูลชัดและไม่สุ่มเงิน | matching/replay/cancel race RQ-6/7/12/14/20 |
| NC-F15-04 | fee schedule จากแหล่งใด อัตรา maker/taker เท่าใด คิดในสินทรัพย์ใด มีส่วนลด/rebate หรือไม่ และ pin นโยบายต่อ order/episode/เวลาอย่างไร; ไม่อนุมานอัตรา Paper จากกฎรับ fee fact ของ F-14 | net fill/ledger/PnL และการกันเงิน RQ-9/10/15 |
| NC-F15-05 | นโยบายกันเงินและสินทรัพย์สำหรับแต่ละชนิด order รวม slippage/fee reserve, market buy ที่ราคาเคลื่อนจนเงินไม่พอ, การขายพร้อมกัน และจังหวะคืนยอดจาก partial/cancel/reject; ไม่มี business cap หรือ tolerance ที่ agent กำหนดเอง | solvency/available balance RQ-10/14/15 |
| NC-F15-06 | F-15 รอบนี้ทำ executor/internal integration โดยยังไม่เปิดรับคำสั่งผู้ใช้จน F-16/F-18 พร้อมหรือขยาย safety integration เท่าใด; รวม F-13 reset integration amendment ในรอบนี้หรือแยกงานอนุมัติภายหลัง โดยยังคง ACTIVITY_UNKNOWN จนหลักฐานครบ | production entrypoint/safety dependencies และ reset success RQ-11/18/19 |

คำตัดสินให้บันทึกในเอกสารนี้และอัปเดตทะเบียน mission §9 ให้ตรงกัน
การเริ่ม F-15 ยังไม่ใช่การอนุมัติ requirements หรือ plan/validation โดยปริยาย

## คำตัดสิน NC-F15-01–06 — Approved 2026-10-18

สถานะส่วนนี้: **Approved** — เจ้าของตอบ “อนุมัติ” หลังเสนอให้อนุมัติ requirements
พร้อมข้อเสนอ NC-F15-01–06 ทั้งชุด วันที่ 2026-10-18 คำว่า “เสนอ” ในหัวข้อย่อย
บันทึกที่มาของตัวเลือกที่ได้รับอนุมัติแล้ว; ตัวเลือกทางเลือกไม่ได้ถูกเลือก
ตัวเลขและสูตรของโมเดลจำลองเป็น simulation policy ที่เจ้าของอนุมัติ ไม่ใช่เงื่อนไขที่ตลาดรับรอง

### หลักฐานจากเอกสารทางการ

ตรวจเอกสารวันที่ 2026-10-18; ยังไม่ได้พิสูจน์ endpoint/stream จริงหรือ capability รายคู่:

- [New Order](https://www.binance.th/api-docs/en/#new-order) ระบุ MARKET, LIMIT,
  timeInForce และ quoteOrderQty สำหรับ MARKET; ต้องตรวจ capability และ filters รายคู่
  ก่อนนำ contract ไปใช้งาน ไม่ถือว่าตัวอย่างในเอกสารรับรองทุก option บนทุกคู่
- [Local order book](https://www.binance.th/api-docs/en/#how-to-manage-a-local-order-book-correctly)
  ระบุการประกอบ REST snapshot กับ diff-depth โดยตรวจ update IDs; snapshot มีขอบเขตจำกัด
  จึงไม่ใช่หลักฐานสภาพคล่องนอกระดับราคาที่ได้รับ
- [VIP schedule](https://www.binance.th/en/faq/spot-trading/4900a0792af24f5e853e2373b84f94e7)
  แสดง VIP 0 ฝั่ง Broker maker/taker 0.10%/0.10%;
  [คำอธิบาย fee](https://www.binance.th/th/faq/spot-trading/0e9f70a2b6ed49e4884b2ee0aed26051)
  ระบุค่าธรรมเนียมลูกค้าทั่วไปของคู่คริปโต 0.1% รวม VAT และเก็บจากสินทรัพย์ที่ได้รับ
  ตาราง/ตัวอย่างนี้ไม่พิสูจน์สิทธิ์ fee ของบัญชีผู้ใช้หรือโปรโมชั่นเฉพาะคู่
- [Trade Fee API](https://www.binance.th/api-docs/en/#trade-fee) ต้องใช้การยืนยันตัวตน;
  ข้อเสนอ Paper ด้านล่างจึงใช้ simulation profile โดยไม่เรียก credential ผู้ใช้

### NC-F15-01 — เสนอ MARKET และ LIMIT/GTC

- MARKET BUY รับงบ USDT (`quoteOrderQty`); MARKET SELL รับปริมาณ base
- LIMIT BUY/SELL รับ base quantity และ limit price ใช้ GTC เท่านั้น
- เปลี่ยนคำสั่งด้วย cancel แล้วสร้าง order ใหม่ที่มี identity ใหม่ ไม่แก้ order เดิมในที่
- ยังไม่รับ IOC/FOK, LIMIT_MAKER, MARKET BUY แบบ base quantity,
  MARKET SELL แบบ quote target หรือ amend; TP/SL ยังคงเป็น F-17
- เป็นขอบเขตผลิตภัณฑ์ที่เสนอ ไม่ใช่ข้อจำกัดทั้งหมดของ Binance TH
  ทางเลือกที่เล็กกว่าคือเริ่ม MARKET อย่างเดียว แต่จะยังไม่ทดสอบ resting-order lifecycle
  ที่ต้องใช้กับออเดอร์ค้างได้ครบ

### NC-F15-02 — เสนอเพิ่ม order book ที่ตรวจลำดับได้

- เพิ่มข้อกำหนด market-data สำหรับ REST depth snapshot + diff-depth และ trade events
  โดยใช้ venue/rate-limit infrastructure เดิม ไม่ให้ simulator เรียกตลาดเอง
- เมื่อ sequence ขาดหรือ reconnect ให้ source ไม่พร้อมทันทีและประกอบ snapshot ใหม่
  ไม่ใช้ latest-trade price แทน book เพื่อ fill
- ใช้ stream target 100ms และเกณฑ์ book verification อายุไม่เกิน 30 วินาที ณ จุดใช้
  ตาม [NC-F15-11](paper-book-freshness-amendment.md); feed/gap/conflict fail closed ทันที
  ต้องมีหลักฐาน source liveness, sequence continuity และ server reference time ประกอบ;
  F-10 latest-trade freshness 10 วินาทียังคงเดิมและไม่ใช้รับรอง depth
- คู่ที่ถูกถอนจาก allowlist แต่ยังมี position/open order ต้องมีข้อมูลตลาดสำหรับจัดการ
  สถานะเดิมต่อไปจนไม่มีภาระค้าง; ไม่เปิดคำสั่งเพิ่มความเสี่ยงให้คู่นั้นกลับมา
- แหล่งข้อมูล/ข้อความที่ไม่รองรับรูปแบบหรือไม่ผ่าน capability checks ทำให้ไม่พร้อม
  และหยุด matching ของคู่ที่ได้รับผล ไม่สร้างข้อมูลตลาดทดแทน
- ลำดับร่วม depth/trade ของ Paper ใช้ combined-stream receive order ตาม
  [NC-F15-12](combined-stream-order-amendment.md); depth ยังตรวจ `U/u` ต่อเนื่อง ส่วน
  trade ID ใช้ bounded dedupe โดยไม่บังคับ monotonic และ economic duplicate ห้าม transition ซ้ำ
- ทางเลือกใช้ latest trade อย่างเดียวมีงานน้อยกว่า แต่ไม่แสดง spread/depth slippage
  จึงไม่ใช่ตัวเลือกที่แนะนำสำหรับ R-17

### NC-F15-03 — เสนอโมเดล deterministic จาก depth และ trade events

- เสนอ simulated execution latency คงที่ 100ms จากเวลา server ยอมรับ order;
  ใช้ book ที่พร้อมและได้รับหลังเวลาที่ order เริ่มมีสิทธิ์จับคู่ ไม่ backdate fill
  latency นี้เป็นค่าจำลอง ไม่ใช่ผลวัดตลาด และไม่เพิ่มค่าสุ่มหรือ fixed slippage percentage
- ฝั่งที่ข้าม spread ใช้ระดับราคาตรงข้ามตามลำดับดีที่สุดไปแย่ที่สุด ภายในขอบเขต
  depth ที่พิสูจน์ได้และ limit/budget ของคำสั่ง; slippage เกิดจากการเดินผ่านระดับราคา
- MARKET จับคู่จาก book ที่พร้อมหนึ่งชุดตามงบ/ปริมาณที่เหลือ;
  ส่วนที่ไม่มีสภาพคล่องที่พิสูจน์ได้เป็น EXPIRED หลังบันทึก partial fill ที่เกิดแล้ว
  ไม่ค้างเป็น LIMIT และไม่สมมติระดับราคาต่อจาก snapshot
- LIMIT ส่วนที่ข้าม spread ในจังหวะรับเป็น taker; ส่วนที่พักรอแล้วจับคู่เป็น maker
  LIMIT ไม่ซื้อแพงกว่า limit และไม่ขายต่ำกว่า limit
- Resting LIMIT ใช้คิวจำลองอย่างระมัดระวัง: เริ่ม queue-ahead ด้วยปริมาณภายนอกที่มองเห็น
  ณ ราคา limit บวก Paper orders ที่เข้าคิวก่อนใน episode เดียวกัน; ให้เฉพาะ trade events
  ที่ตรงราคาและฝั่งซึ่งพิสูจน์ว่าเป็นการซื้อขายกับด้านนั้นลด queue-ahead แล้วจึง fill
  จากปริมาณ trade ที่เหลือ การลด depth หรือราคาเพียงแตะ limit ไม่ใช่ fill
- โมเดลนี้ไม่รู้คิว/hidden liquidity จริง จึงอาจให้ผลต่างจากตลาด โดยเฉพาะ limit order
  trade ที่ระบุฝั่งหรือ ordering ไม่ได้ต้องไม่สร้าง fill
- ordering ที่พิสูจน์ใน Paper หมายถึง durable combined-stream receive order ตาม NC-F15-12;
  source timestamps ยังคงเป็น provenance แต่ไม่ใช้เรียง event ข้าม depth/trade ใหม่
- แยก virtual liquidity ต่อ episode เพื่อไม่ให้ผู้ใช้หนึ่งคนเปลี่ยนผลของอีกคน;
  ภายใน episode เดียวกันแต่ละ input revision/trade ID ถูกใช้ครั้งเดียวตามลำดับถาวร
  ใช้ shared counter ต่อระดับราคาเพื่อไม่ให้ออเดอร์หลายใบใช้ปริมาณเดียวกันซ้ำ
  การเปลี่ยนระดับ depth ไม่ถือว่าเติมปริมาณที่ Paper ใช้ไปแล้วกลับทั้งก้อนโดยอัตโนมัติ
  ต้องเก็บ consumption และลำดับ book/trade ใน input stream ที่ replay ได้
- เมื่อ feed ไม่พร้อมให้พัก matching ทั้งหมด คง reservation และยอมรับ cancel;
  คำสั่งลดความเสี่ยงยังรับเข้าคิวได้ผ่าน gates เดิม แต่ไม่แสดงว่าปิดสำเร็จ
  จนมีข้อมูลพร้อมและ fill จริงใน simulator
- หลัง source กู้คืนสำเร็จให้ rebase คิวที่ยังพักอยู่ตาม depth ที่พิสูจน์ได้ ณ ตอนนั้น
  โดยคงลำดับ Paper orders เดิม ไม่สร้าง fill สำหรับช่วงข้อมูลหาย และเก็บ rebase เป็น fact
  ถ้า consumption/ordering ยังพิสูจน์ไม่ได้ให้ source unknown จน rebuild สำเร็จ
- การจำลอง filters/execution constraints ต้องอิง metadata ที่พิสูจน์ได้ของคู่/เวลา
  หากกฎที่จำเป็นต่อคำสั่งยังไม่รองรับต้องปฏิเสธ ไม่อ้างว่าเดิน depth อย่างเดียวเหมือนตลาดครบ
- NC-F15-13 รองรับ `PERCENT_PRICE`, `MAX_NUM_ORDERS` และ MARKET
  `MIN_NOTIONAL.avgPriceMins` ตาม
  [amendment ที่อนุมัติ](binance-th-execution-filters-amendment.md); reference/history ไม่ครบ
  ต้องปิดคำสั่งและ unknown rules ยังคง fail closed

### NC-F15-04 — เสนอ fee profile คงที่ต่อ episode

- เสนอ profile `PAPER_STANDARD_V1`: maker = taker = 0.1% สำหรับสองคู่ตั้งต้น
  เป็น simulation profile ที่ต้องได้รับอนุมัติ ไม่ใช่ fee เฉพาะบัญชีจริง
- ซื้อ: fee เป็น base ที่ได้รับ; ขาย: fee เป็น quote ที่ได้รับ; ไม่จำลอง BNB discount,
  VIP progression, referral rebate หรือโปรโมชั่นในรุ่นแรก และไม่คิด VAT เพิ่มซ้ำ
- pin version/rate/fee asset policy ตั้งแต่เริ่ม episode และเก็บอ้างอิงทุก fill
  profile ใหม่ใช้กับ episode ใหม่ ไม่แก้ประวัติหรือ order ที่รันอยู่ย้อนหลัง
- การปัดและขอบเขตตัวเลขใช้ Money/Quantity เดิม; ไม่มี rounding rule ใหม่ใน simulator
  กรณี fee/budget ที่แทนไม่ได้ต้องปฏิเสธแบบมีชนิด ไม่ให้ฐานข้อมูลปัดแทน

### NC-F15-05 — เสนอ reserve ตามภาระสูงสุดของชนิดคำสั่ง

ข้อเสนอนี้ผูกกับ fee-in-received-asset ใน NC-F15-04:

- MARKET BUY กันงบ USDT ทั้งก้อน; เงินที่ใช้จริงห้ามเกินงบ ไม่ต้องคาดเดาราคาอนาคต
- LIMIT BUY กัน quote value ที่ราคา limit คูณปริมาณที่เหลือ โดยใช้ arithmetic/rounding
  เดิมที่ทำให้ยอดกันไม่ต่ำกว่าภาระ; ปรับยอดหลัง partial fill และคืนส่วนที่ไม่ต้องใช้
- SELL กัน gross base quantity ที่จะขาย ไม่กัน fee เพิ่มจาก base เพราะ fee ขายอยู่ใน quote
- buy fee หักจาก base ที่ได้รับ จึงไม่กัน quote fee เพิ่ม; sell fee หักจากรายรับ quote
- ตรวจและกันยอดใน financial transaction เดียวกันต่อ episode; การรับคำสั่งพร้อมกัน
  ต้องไม่กัน quote/base ซ้ำ และ reserved ไม่ใช่ ledger debit หรือค่าใช้จ่าย
- หลัง partial fill ใช้จริงเฉพาะ execution effect พร้อมปรับ reservation ตามส่วนคงเหลือ;
  cancel/reject/expire คืนส่วนที่ไม่ใช้เมื่อ terminal fact commit แล้วเท่านั้น
- ยอดไม่พอตั้งแต่รับคำสั่งให้ปฏิเสธ ไม่ลดขนาดเงียบ ๆ; MARKET ที่จับคู่ได้ไม่ครบงบ/ปริมาณ
  ใช้ partial/EXPIRED ตาม NC-F15-03 และคืน reservation ที่เหลือ ไม่ติดหนี้หรือข้าม budget
- ถ้าเปลี่ยน fee policy ไปเก็บสินทรัพย์อื่น ต้องกลับมาอนุมัติ reserve policy ที่สอดคล้องก่อน

### NC-F15-06 — เสนอปิด internal execution และ reset integration ใน F-15

- ทำ executor, durable internal commands, source initialization และการเชื่อมเงิน/position
  ในขอบเขต F-15 พร้อมเทสต์จาก internal callers แต่ยังไม่เปิด endpoint ให้ผู้ใช้ส่งออเดอร์
  จน F-16 และ safety gates/dependencies ที่จำเป็นพร้อม ไม่ข้าม F-18 เพื่อให้ใช้งานได้เร็วขึ้น
- รวม F-13 reset integration amendment ใน requirements/plan/validation ที่จะเสนอ
  ให้เจ้าของอนุมัติ โดยเปิด reset success เฉพาะเมื่อ source ทั้งสองพร้อมและผ่าน
  position/order/reset concurrency, fault/recovery และเกณฑ์ F-13 ที่เกี่ยวข้องครบ
- การเลือกรวมงานนี้ไม่ถือว่า reset ผ่านแล้ว และไม่ปิด pending validation ของ F-13
  จนมีหลักฐานจริง; ก่อนอนุมัติ amendment และผ่านเกณฑ์ยังคง ACTIVITY_UNKNOWN
- ทางเลือกแยก reset integration ไปอนุมัติภายหลังทำได้ แต่ F-15 จะยังไม่ปิด dependency
  ที่ F-13 รออยู่ และต้องระบุงานค้างนั้นใน roadmap ต่อ

### บันทึกการอนุมัติ

2026-10-18: เจ้าของตอบ “อนุมัติ” ต่อข้อเสนอทั้งชุด จึงปิด NC-F15-01–06 และเริ่ม
จัดทำ plan.md/validation.md ได้ การอนุมัติครั้งนี้ยังไม่ใช่การอนุมัติเอกสารสองฉบับนั้น
และยังไม่อนุญาตให้เริ่ม implementation ก่อนผ่านจุดอนุมัติขั้นถัดไป

## Amendment หลัง deep review — NC-F15-07 (Approved)

**Closed — เจ้าของอนุมัติ 2026-10-18:** กฎเดิมห้ามเติม virtual liquidity ที่ใช้ไปแล้วกลับทั้งก้อน
แต่ยังไม่กำหนดผลเมื่อ absolute depth ลด/เพิ่ม/หาย/กลับมาและเมื่อ rebase หลัง gap
สูตรด้านล่างปิดข้อที่เคยบล็อก matching implementation และ V-4/V-5/V-7

เสนอ `PAPER_DEPTH_SHADOW_V1` เป็นส่วนหนึ่งของ pinned simulation profile:

- ต่อ episode/side/price เก็บ reported quantity `A` และ shadow consumption `C`;
  available virtual quantity `V = max(0, A - C)` ทั้งหมดใช้ Quantity arithmetic กลาง
- เมื่อ Paper taker fill `q` ต้อง `q <= V` แล้วเพิ่ม `C` ด้วย `q` แบบ atomic
  ทุก order ใน episode ใช้ state เดียวกัน; episode อื่นมี state ของตน
- absolute update ที่ยืนยันแล้วเป็น `A_new` ใช้ `C_new = min(C, A_new)` และ
  `V_new = A_new - C_new`; duplicate/stale input ไม่ transition ซ้ำ
  ปริมาณที่รายงานลดลงจะลด V ก่อน และลด C เฉพาะส่วนที่เกิน A_new
  การลด C ไม่ใช่ fill, refund หรือการเปลี่ยน economic history
- confirmed zero/removal ทำให้ A/C/V เป็นศูนย์; ปริมาณที่กลับมาภายหลังถือเป็น
  liquidity ใหม่ตามโมเดลนี้ ไม่ถือว่าระดับที่อยู่นอก bounded snapshot เป็น confirmed zero
- recovery snapshot ใช้สูตรเดียวกับ absolute update โดยรักษา C ที่ commit แล้ว
  ห้ามตั้ง C เป็นศูนย์เพราะ generation เปลี่ยน; queue rebase ยังต้องคง Paper FIFO เดิม
  หาก snapshot พิสูจน์ระดับเดิมไม่ได้ให้คง unknown และหยุด matching ของ pair นั้น
- public trade ใช้ลด resting queue และสร้าง maker fill เท่านั้น ไม่ลด A/C/V ซ้ำ;
  depth stream เป็นผู้เปลี่ยน A ส่วน Paper taker เป็นผู้เพิ่ม C แต่ละชนิดมี dedupe
  และ durable merged input sequence; trade/depth ที่ ordering พิสูจน์ไม่ได้ไม่สร้าง fill
- นี่เป็น conservative simulation rule ไม่ใช่ข้ออ้างว่ารู้ identity ของ exchange orders:
  การเปลี่ยนแทนที่ที่ปริมาณรวมเท่าเดิมยังไม่เติม V; confirmed zero แล้วกลับมาจึงเติมได้
  เก็บ A/C/V, input IDs และ rebase facts ให้ replay ตรวจสูตรทุก transition ได้

ตัวอย่างที่เสนอ: A=10/C=0/V=10 → Paper ใช้ 4 → 10/4/6;
depth เป็น 8 → 8/4/4; กลับ 10 → 10/4/6; ลดเหลือ 2 → 2/2/0;
confirmed zero → 0/0/0; กลับ 10 → 10/0/10
หากเกิด gap หลัง 10/4/6 แล้ว snapshot ยืนยัน 10 ต้องยังเป็น 10/4/6
ส่วนระดับที่ snapshot ไม่ครอบคลุมต้องไม่ใช้กรณี zero เพื่อปลด C

2026-10-18: เจ้าของตอบ “approve” ต่อ NC-F15-07 และ plan/validation ฉบับแก้ไข
จึงอนุมัติสูตรนี้และเริ่ม implementation ตาม milestones ได้; ไม่มี Needs Clarification
ที่เกี่ยวกับ F-15 ค้างอยู่ ณ จุดอนุมัตินี้

## Amendment — NC-F15-08 Approved: correction lifecycle

เจ้าของตอบคำถามระหว่าง M3 วันที่ 2026-10-18 ก่อน implementation correction:
- REPLACE/VOID ที่ลดจำนวน fill ของออเดอร์ terminal โดยเฉพาะ FILLED:
  ปิดส่วนที่ขาดเป็น CANCELED และไม่เปิดจับคู่ใหม่; เก็บประวัติ terminal เดิมไว้
- LIMIT ที่ยัง active: คำนวณ queue-ahead ใหม่จาก verified book ปัจจุบันและออเดอร์
  ที่มาก่อน พร้อม append rebase fact; ไม่คง queue-ahead เดิมโดยไม่มี proof
- ยังคงข้อกำหนด solvency/reservation/F-14 rebuild และ conflict เมื่อ downstream
  liabilities ไม่ปลอดภัย; คำตัดสินนี้ไม่อนุญาตให้แก้ immutable history หรือข้าม safety gate

## NC-F15-10 — Approved (2026-10-20)

เจ้าของอนุมัติให้คง revision ของ terminal history เดิม และอัปเดตเฉพาะ active orders/รายการที่เพิ่งจบใน transaction ปัจจุบัน พร้อม reservation ที่ปล่อยเป็นศูนย์อย่าง atomic. Terminal revision ต้องไม่เกิน activity revision; projection/reservation ของรายการเดียวกันต้องสอดคล้องกัน. ใช้ additive migration ปรับ F-13 reset coherence โดยรักษา source proof, event linkage, owner isolation และการปฏิเสธข้อมูลผิด/ไม่ครบ; ไม่แก้ migration 0037. Downgrade ต้องปฏิเสธเมื่อมีข้อมูลที่ contract เดิมรับไม่ได้ ไม่ rewrite ประวัติ.

ใช้ `matching_storage.persist_checkpoint` และ `paper_wallet_reset_readiness` เดิม; เพิ่ม real PostgreSQL safety tests สำหรับ active/current-terminal revision, old terminal rows ไม่ถูกเขียนซ้ำ, corruption, reset, correction, rollback/retry และ migration. กฎเงิน/การจับคู่และเกณฑ์ W1–W4 คงเดิม; ผลที่ได้รับผลกระทบต้องตรวจใหม่ก่อน Completed.
