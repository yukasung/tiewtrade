# Paper Test Entry — ข้อเสนอกฎแท่งตลาดจริง

สถานะ: **Superseded - owner chose the existing RSI Step Grid rules; UNCONFIRMED exception not approved**
วันที่: 2026-11-21 (Asia/Bangkok)
คำขอเจ้าของ: “จัดทำกฎสำหรับแท่งตลาดจริงก่อนแก้”
ขอบเขต: NC-05 ของ Paper Test Entry เท่านั้น; ไม่เปลี่ยน RSI Step Grid/Live/production
Latest decision (explicitly approved by owner2026-11-21): retain CLOSED-only/readiness/Market execution rules used by RSI Step Grid.
RM-01 through RM-13 below are historical proposals, not active rules or awaiting approval.
See the latest NC-05 decision in requirements.md. No runtime change from this proposal.


## 1. หลักฐานและข้อจำกัด

Preview รับคำขอ Start แล้ว แต่ run พักด้วย INDICATOR_NOT_READY หลังเปิด builder แล้ว
อ่าน ATR ได้ READY แต่แท่งยัง UNCONFIRMED จึงไม่ผ่านกฎ CLOSED เดิม

- [F-09 RQ-6 และข้อจำกัด REST](../2026-10-07-market-data/requirements.md):
  หลักฐานตลาดที่มีไม่รับรอง closure; ต้องคง UNCONFIRMED
- [F-11 RQ-9 / NC-31](../2026-10-10-backend-indicators/requirements.md):
  UNCONFIRMED ใช้คำนวณเพื่อแสดงผลได้เมื่อ end_at <= as_of และ fetch_started_at >= end_at
  แต่ความสามารถคำนวณ indicator ไม่ใช่การอนุญาตให้ตัดสินใจเทรด
- [RQ-01/03/09/12/13 เดิม](requirements.md) ต้องได้รับ amendment ก่อนขยาย eligibility
  โค้ดปัจจุบันที่ปฏิเสธ UNCONFIRMED ทำตามกฎเดิม ไม่ใช่เหตุให้แปลงข้อมูลเป็น CLOSED

ข้อเสนอนี้คือ **อนุญาตให้เทรด Paper จากข้อมูลหลังจบช่วงที่ตรวจหลักฐานแล้ว**
ไม่ใช่อ้างว่าตลาดยืนยันปิดแท่งหรือรับรองว่า OHLC จะไม่แก้ย้อนหลัง

## 2. Requirements amendment ที่เสนอ

| รหัส | กฎที่เสนอ |
|---|---|
| RM-01 — ขอบเขต | ใช้เฉพาะ Paper Test Entry รุ่นใหม่ใน owned acceptance environment ที่ API/engine opt-in ตรงกัน; RSI เดิม, Live และ production ไม่มีสิทธิ์ใช้ policy นี้ |
| RM-02 — ตัวตนและ finality | ต้องตรง source/pair/timeframe/open_at/end_at ตามสัญญา UTC เดิม คง finality ของต้นทางทุกชั้น ห้าม relabel UNCONFIRMED เป็น CLOSED |
| RM-03 — แท่งที่ใช้ได้ | (ก) CLOSED ที่มีหลักฐานตามสัญญาเดิม หรือ (ข) UNCONFIRMED ที่ end_at <= as_of และ fetch_started_at >= end_at; as_of เป็นเวลา server/DB ที่เชื่อถือได้สำหรับการประเมิน ไม่รับเวลาจาก browser |
| RM-04 — หลักฐานการดึง | fetch_started_at ต้องเป็นของคำขอ REST จริงที่ให้ OHLC รุ่นนั้นและ commit สำเร็จใน canonical storage; observed_at/last_checked_at/เวลาที่อ่าน/การขึ้นแท่งถัดไป/สัญญาณ WebSocket อย่างเดียวใช้แทนไม่ได้; ดึงก่อนจบแต่ตอบหลังจบยังไม่ผ่าน |
| RM-05 — ปฏิเสธเมื่อไม่พร้อม | OPEN, end_at ในอนาคต, ไม่มีหลักฐาน, ดึงก่อนจบช่วง, refresh กำลังรอ/ล้มเหลว, ช่องว่าง, source ไม่พร้อมหรือ version/proof ไม่ตรง ต้องงดเข้าและแสดงเหตุรอ ห้ามเดา OHLC/ATR หรือใช้ราคาปัจจุบันแทน |
| RM-06 — ATR และ warm-up | ATR14 ของแท่งสัญญาณต้อง READY และผูกกับข้อมูล/source revision ที่พิสูจน์ได้ชุดเดียวกัน ใช้ F-11 NC-31 กับข้อมูลทุกแท่งที่พึ่งพา รักษา warm-up อย่างน้อย250แท่งต่อเนื่องและ numeric/proof/refresh guards เดิม; ไม่ถือว่า250แท่งต้องมี finality CLOSED ทั้งหมดเมื่อ policy นี้อนุมัติ แต่ทุกแท่งต้องผ่านเกณฑ์ข้อมูลที่เกี่ยวข้อง |
| RM-07 — สัญญาณและความสด | BUY เมื่อแท่งที่ผ่าน RM-03 ปิดช่วงสีเขียว (close > open) เท่านั้น ใช้แท่งล่าสุดตาม timeframe ของบอทและ freshness/cutoff/recovery guards เดิม; ห้ามซื้อไล่ตามประวัติหรือ backfill หลังเริ่ม/กู้คืน และห้าม fallback ไปใช้แท่งเก่าเมื่อแท่งล่าสุดยังไม่พร้อม |
| RM-08 — กันซื้อซ้ำ | ต่อ run/pair/timeframe/open_at มี entry ได้ไม่เกินหนึ่งครั้ง แม้ source revision เปลี่ยน, poll/feedback ซ้ำ, worker restart/takeover หรือแท่งถูกแก้ย้อนหลัง; แก้จากแดงเป็นเขียวหลังประเมินแล้วไม่เปิดโอกาสให้ซื้อซ้ำ/ย้อนซื้อแท่งเดิม ต้องรอแท่งใหม่ตาม guards เดิม |
| RM-09 — ตรวจซ้ำก่อนส่ง | ก่อน commit decision และก่อน queued BUY ทำงาน ต้องตรวจหลักฐานที่เกี่ยวข้องตาม revision/source/lease/STOP/risk เดิม หากข้อมูลที่ใช้ตัดสินใจเปลี่ยนให้ปฏิเสธหรือพักตาม policy เดิม; client ห้ามส่ง assertion ว่าแท่งพร้อมเพื่อข้ามการตรวจจาก server |
| RM-10 — หลังเกิด fill | หากข้อมูลตลาดแก้ย้อนหลังหลัง fill ให้คง ledger/position ตาม execution จริง ไม่ลบ trade หรือย้อนออเดอร์ชดเชยอัตโนมัติ; TP/SL ยังตรึงจาก first actual fill ±3×signal ATR ที่บันทึกไว้ ไม่คำนวณทับจาก ATR ใหม่; ใช้ reconciliation/failure/STOP เดิมเมื่อข้อมูลไม่สอดคล้อง |
| RM-11 — เงินและ lifecycle | เงินต่อไม้, ครั้งละหนึ่ง position, pending/unresolved guards, fees/PnL, risk/STOP/catalog/balance, TP/SL/first-fill policy และ manual reduction/cancel ตามเดิมทุกข้อ |
| RM-12 — ตรึง policy ต่อ run | ระบุ policy/version ใน immutable configuration และ audit ของ run รุ่นใหม่อย่างชัดเจน; run รุ่นเดิมยังใช้ CLOSED-only แม้ deploy/เปิด gate ใหม่ ไม่ย้าย policy หรือสร้างคำขอ Start อัตโนมัติ; เปลี่ยนได้ผ่านการหยุด/ตรวจ exposure และ explicit Start ใหม่ตาม replacement proof เดิม |
| RM-13 — UI และ audit | ก่อน Start แสดงข้อความสั้นว่า “ใช้ข้อมูลหลังจบช่วงเวลา ตลาดยังไม่รับรองการปิดแท่ง” และแยกเหตุรอข้อมูลที่ยืนยันแล้ว; ไม่เพิ่ม checkbox แทนคำสั่ง Start; บันทึก policy/version, candle identity, original finality, end_at, fetch_started_at, as_of, source revision/proof และ signal ATR ใน durable decision provenance ตามมาตรฐาน audit เดิม โดยไม่ log secret |

ขอบ fetch_started_at = end_at และ end_at = as_of ผ่านกฎเวลาตาม NC-31 ได้
แต่ยังต้องผ่านเงื่อนไขอื่นทั้งหมด; เกณฑ์นี้ไม่เพิ่ม grace period, cooldown,
จำนวนครั้งดึงซ้ำ หรือเพดานความเสี่ยงใหม่

## 3. ผลกระทบที่ต้องยอมรับก่อนอนุมัติ

ข้อมูล UNCONFIRMED อาจแก้ย้อนหลัง แม้ดึงหลังสิ้นสุดช่วงและ ATR READY แล้ว
จึงอาจเกิด Paper trade จากสัญญาณที่ค่าประวัติภายหลังเปลี่ยนไป ต้องยอมรับ execution
ที่เกิดแล้วตามจริงและตรวจผ่าน audit ไม่แก้ประวัติให้ดูเหมือนไม่เคยซื้อ

นี่เป็นข้อยกเว้นการใช้ข้อมูลตัดสินใจเทรด **เฉพาะกลยุทธ์ทดสอบ Paper** ไม่ใช่การผ่อน
นิยาม CLOSED ของ F-09 หรือหลักฐานที่อนุญาตให้ RSI/Live ใช้ตามได้ ไม่รับรอง latency,
ราคาที่ fill, กำไร หรือว่าทุกช่วงจะผ่าน source/warm-up/execution readiness ได้

ทางเลือกที่คงกฎเข้มเดิม: ใช้ CLOSED-only ต่อและตรวจ flow ด้วย controlled fixtures;
ข้อมูลตลาดจริงปัจจุบันจะยังไม่เข้าเมื่อมีเพียง UNCONFIRMED

## 4. สิ่งที่ต้องพิสูจน์ใน plan/validation หลัง requirements ผ่าน

รายการนี้เป็นผลกระทบเบื้องต้น ยังไม่ใช่แผน implementation ที่อนุมัติแล้ว:

- reuse canonical StoredCandle/refresh_due และ F-11 proof/checkpoint/tail เดิม
  เพิ่ม typed strategy eligibility แยกจาก Candle.finality โดยไม่แก้ semantics ของ shared consumers
- ตรวจเวลา exact boundary, before-end-fetch/after-end-response, missing/stale proof,
  source gap/recovery, wrong series และ ATR/source revision mismatch
- real PG: source correction ระหว่าง evaluate/commit/queued execution, STOP/risk/lease race,
  multiple instances/replay, same candle หลาย revision และ partial/late fills
- immutable policy/config/state version และ old-run/RSI/default gate/Live regression
- actual API/browser กับ **real public-source provenance** และบันทึก original finality;
  controlled fixtures ยังใช้ทดสอบ edge cases แต่ไม่แทนหลักฐานข้อมูลตลาดจริง
- UI readiness/loading, policy disclosure, Start/Stop/reload; owner acceptance และ required CI
  ต้องครบก่อน merge ตาม workflow เดิม ไม่มีการสั่ง Live ใน validation

## 5. จุดอนุมัติ

การตอบให้จัดทำเอกสารยังไม่ใช่อนุมัติใช้ UNCONFIRMED ตัดสินใจซื้อขาย
ขออนุมัติ RM-01–RM-13 และผลกระทบในหัวข้อ3 เป็น requirements amendment ก่อน
หลังจากนั้นจึงจัดทำ plan.md/validation.md ฉบับเพิ่มเติมให้อนุมัติ ก่อนแก้ runtime
NC-05 คง Needs Clarification/รอคำตัดสิน จนเจ้าของอนุมัติหรือเลือกแก้ข้อเสนอ

## 6. จังหวะเข้าที่เจ้าของระบุเพิ่มเติม — 2026-11-21

“เมื่อแท่งเทียน closed ให้ซื้อแท่งเทียนเปิดถัดไป”: แท่ง A สีเขียวเป็นสัญญาณ
ส่งคำสั่ง Market เข้าเมื่อเริ่มแท่ง B ถัดจาก A หลังหลักฐานตาม policy ที่อนุมัติและ
admission พร้อม; ราคาที่ fill จริงอาจต่างจาก open ของ B และยังเป็นฐาน TP/SL เดิม
ห้ามใช้ข้อมูลระหว่างแท่ง A เปิด ห้าม backdate order/fill หรือรับรองราคา open
เมื่อข้อมูลยังไม่พร้อมที่ขอบแท่ง งดส่งขณะนั้น ไม่เพิ่ม retry window/grace period เอง
รายละเอียดเหตุการณ์/ความสด/กรณีหลักฐานมาช้าต้องระบุใน plan/validation ภายใต้กฎเดิม
คำตัดสินเรื่องจังหวะนี้ไม่เท่ากับอนุมัติ RM03 ให้ใช้ UNCONFIRMED; NC05 ยังเปิด
