# F-17 — TP/SL และ Bracket — Requirements

สถานะ: **Approved — เจ้าของอนุมัติ requirements ทั้งฉบับ 2026-11-04 หลังอนุมัติ NC-F17-01..05**; **NC-SET4-12 Approved A 2026-11-06; §16/18 Approved 2026-11-07 - separate internal checkpoint**
วันที่: 2026-11-02

## ทำไมต้องมี

ผู้ใช้ต้องเลือก TP/SL พร้อมออเดอร์เข้า หรือเพิ่มให้ position ที่เปิดอยู่ได้ ตาม mission C-7
(R-09) โดยติดตามขนาดที่เข้าจริงและแสดงสถานะการป้องกันตามความจริง
ฉบับนี้รวมกฎเดิมและข้อเสนอทั้ง 5 ข้อที่เจ้าของตอบ “approve” วันที่ 2026-11-04
เจ้าของอนุมัติ requirements ทั้งฉบับแล้ว จัดทำ plan/validation เพื่อขออนุมัติแยก
การอนุมัติคำตัดสินนี้ยังไม่ใช่การอนุมัติ implementation

## ขอบเขต

- TP/SL แบบ bracket และตั้งภายหลังสำหรับ Spot ในบริบทชุดที่ 4 — Paper Trading
- เชื่อมกับออเดอร์/position และหน้าสั่งออเดอร์เดิม F-14/F-15/F-16
- ใช้ตรรกะโดเมนร่วม Paper/Live และแยกข้อมูล/ทางส่งคำสั่งตาม ADR-004
- ส่งมอบ Paper ใช้งานจริง: bracket, ตั้งทีหลัง, แก้ไข/ยกเลิก และสถานะบนหน้าจอ
- Live execution, bot lifecycle และช่องทางแจ้งเตือนที่ยังไม่พร้อมเป็น Pending Dependency;
  ต้องมีคำเตือนในแอปจริง แต่ไม่ถือว่าทดแทนการแจ้งทุกช่องทางครบแล้ว
- ไม่เปิด Live, ไม่ทำ Futures/venue ใหม่ และไม่เปลี่ยนกฎ matching/fee/PnL/risk เดิม
- ไม่เพิ่ม trailing stop, ladder หรือกลยุทธ์ใหม่โดยปริยาย

## ข้อกำหนดที่มีแหล่งอ้างอิงแล้ว

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | รองรับ TP/SL ผูกกับออเดอร์เข้าและตั้งภายหลังกับ position ที่เปิดอยู่ | mission C-7 / R-09 |
| RQ-02 | เทรดมือเลือกเอง ไม่บังคับ SL; กลยุทธ์ประกาศความจำเป็นเอง ห้ามสร้างการป้องกันที่ไม่ได้ขอ | trading-safety §11 |
| RQ-03 | partial fill ต้องตั้งการป้องกันตามขนาดที่เข้าจริงทันที และขยายเมื่อเข้าเพิ่ม ห้ามแสดงว่าป้องกันครบระหว่างยังดำเนินการ | trading-safety §11 |
| RQ-04 | ตั้งไม่สำเร็จใช้รหัสเดิมเพื่อกันซ้ำและลองใหม่ไม่เกิน 3 ครั้ง; ใช้ครั้งแรก + retry อีกไม่เกิน 3 ครั้งตาม NC-F17-05 ด้านล่าง | trading-safety §4/7/11 |
| RQ-05 | เมื่อครบจำนวนแล้วยังตั้งไม่สำเร็จ เทรดมือห้ามปิดให้ ต้องแสดงว่าไม่มีการป้องกันและแจ้งทุกช่องทางที่เปิด; บอทปิดไม้คืน หยุดบอท และแจ้งตามกฎเดิม โดยต้องบอกนโยบายก่อนเปิดบอท | trading-safety §11 |
| RQ-06 | คำสั่งปิดต้องผ่าน safety gate เดิม ขนาดไม่เกิน position จริง ไม่เพิ่มความเสี่ยง และไม่ถูกบล็อกเพียงเพราะชนเพดานหรือคู่ถูกถอน | trading-safety §3/13; F-37 |
| RQ-07 | Kill Switch/ชนเพดานต้องไม่ยกเลิก TP/SL; bracket ที่เข้าแล้วแต่การป้องกันไม่ครบยังต้องจัดการตามกฎเดิม | trading-safety §8/11/13; F-19 RQ-10 |
| RQ-08 | แยก owner/mode/รอบ Paper; Paper ไม่ส่งออเดอร์ออก Binance และไม่เข้าถึง Live credentials; Live ไม่เปิดโดยปริยาย | mission §4; trading-safety §1; ADR-004 |
| RQ-09 | คำนวณเงินและปริมาณด้วย Money/Quantity จาก tiewtrade.core.money และให้ผล deterministic; ไม่สร้างสูตรปัดเศษใหม่ | AGENTS.md §กฎที่ห้ามละเมิด |
| RQ-10 | บันทึก durable intent/audit ก่อน execution, กันคำขอซ้ำ และใช้ single writer; restart/multi-instance ต้องไม่ทำคำสั่งหายหรือซ้ำ ไม่ใช้ process memory เป็นแหล่งข้อมูลหลัก | trading-safety §4/9/10; architecture §4/5; AGENTS.md |
| RQ-11 | ผลไม่ทราบต้องกระทบยอด ไม่ส่งคำสั่งใหม่โดยเดา; UI แยกรับคำสั่งแล้ว/ป้องกันแล้ว/ปิดสำเร็จและข้อผิดพลาดตามผลจริง | trading-safety §4/6/10/11 |
| RQ-12 | ใช้ UI template/shared controls เดิม รองรับไทย/อังกฤษและ accessibility; ห้าม Admin/Owner จัดการ position แทนผู้ใช้ | AGENTS.md; mission §2; frontend |
| RQ-13 | ทดสอบ duplicate/concurrency, partial fill, การปิดแข่ง trigger, stop/risk/catalog interaction, restart และ owner/mode isolation ตามผลกระทบ; ห้ามส่ง Live order ใน automated validation | testing; trading-safety |

## คำตัดสินเจ้าของ — Approved 2026-11-04

เจ้าของตอบ “approve” ต่อข้อเสนอทั้ง 5 ข้อในบทสนทนา; บันทึกขอบเขตตามข้อเสนอนั้น
ไม่ถือว่าอนุมัติ plan/validation หรือ implementation ล่วงหน้า

### NC-F17-01 — ขอบเขตส่งมอบ

Paper ต้องใช้งานได้ครบ bracket, ตั้งทีหลัง, แก้ไข/ยกเลิก และแสดงสถานะ
ใช้โดเมนร่วมกับ Live ตาม ADR-004 แต่ไม่เปิด Live execution
bot lifecycle และช่องทางแจ้งเตือนที่ยังไม่พร้อมเป็น Pending Dependency
ต้องแสดงคำเตือนในแอปจริง และไม่รับรองว่าผ่านข้อกำหนดแจ้งทุกช่องทางแล้ว

### NC-F17-02 — Trigger และคำสั่งปิด

- Spot SELL ใช้ last trade ที่เชื่อถือได้ ไม่ใช้ราคาปิดแท่งเทียน
- TP trigger เมื่อราคา >= TP; SL trigger เมื่อราคา <= SL
- ทั้งสองขาสร้าง MARKET exit โดยใช้ matching/liquidity/fee ของ F-15 เดิม
  ราคา trigger ไม่ใช่ราคาขายที่รับประกัน
- กรอกราคา absolute; ไม่เพิ่มเปอร์เซ็นต์ในรุ่นแรก
- เลือก TP อย่างเดียว, SL อย่างเดียว หรือทั้งคู่ได้
- ตอนตั้ง/แก้ ต้อง TP > ราคาปัจจุบัน และ SL < ราคาปัจจุบันสำหรับขาที่เลือก
  ไม่ผ่านให้ปฏิเสธพร้อมเหตุผล
- bracket ที่รับแล้วแต่ entry เพิ่ง fill หลังราคาข้ามระดับ ให้ประเมิน trigger ทันที
  หลังรับรู้ fill ไม่ปฏิเสธย้อนหลังจน position ไม่มีการจัดการ
- ความสามารถ Live ของแต่ละคู่และการจับคู่สองขาต้องพิสูจน์ในงาน Live ก่อนเปิดใช้งาน
  การมีชนิดคำสั่งในเอกสารตลาดไม่ใช่หลักฐานว่าระบบพร้อมส่งจริง

### NC-F17-03 — ขนาดและการขายมือ

- bracket ป้องกันเฉพาะปริมาณสุทธิที่ได้จาก entry นั้น เพิ่มตาม partial fill จริง
- ตั้งทีหลังเลือกจำนวนได้ ค่าเริ่มต้นคือปริมาณที่ยังไม่มี protection และไม่ถูกจองขาย
- แต่ละหน่วยเหรียญอยู่ได้เพียงชุด protection เดียว; มีหลายชุดได้เมื่อปริมาณไม่ซ้อนกัน
- TP/SL ภายในชุดใช้ปริมาณร่วมกัน ไม่จองสองเท่า
- entry ใหม่ไม่ขยายชุดที่ตั้งทีหลังโดยอัตโนมัติ
- ขายมือใช้ส่วนที่ยังไม่ผูกก่อน หากขายส่วนที่ป้องกันอยู่ ผู้ใช้ต้องระบุชุดที่จะลด/ปิด
  ระบบประสานกับ protection เดิมก่อนส่งขาย ไม่บังคับให้ยกเลิกการป้องกันเองล่วงหน้า

### NC-F17-04 — Lifecycle และ residual

- ขาแรกที่ trigger ได้สิทธิ์ปิดเพียงทางเดียว อีกขาต้องไม่สร้างคำสั่งขายแข่งกัน
- เมื่อ trigger ให้ยกเลิกส่วน entry ที่ค้าง เพื่อไม่ซื้อเพิ่มหลังเริ่มออกจากไม้
- ระหว่างรอยืนยัน cancel ต้องรับรู้และจัดการ fill ที่เพิ่มด้วย ห้ามถือว่ายกเลิกสำเร็จ
  ก่อนผลยืนยัน และต้องไม่ขายเกินปริมาณจริง
- MARKET ปิดบางส่วนต้องแสดงส่วนที่เหลือและแจ้งเตือน ไม่แสดงว่าปิดครบ
  และไม่สร้าง MARKET ใบใหม่วนเอง
- แก้ราคา/จำนวนหรือยกเลิก protection ได้ก่อน trigger; เมื่อเริ่มปิดแล้วให้จัดการ
  ผ่านสถานะคำสั่งปิด
- ขนาดต่ำกว่าข้อจำกัดตลาดให้แสดงว่าส่วนนี้ยังปิดอัตโนมัติไม่ได้ ห้ามปัดขึ้น
  หรือซื้อเพิ่มเพื่อให้ขายได้
- Paper เปลี่ยน protection เดิมเป็นชุดใหม่พร้อมกันใน transaction
  เพื่อไม่เกิดช่วงที่หายทั้งสองชุด

### NC-F17-05 — Retry, SLA และ recovery

- การตั้ง protection ใช้ครั้งแรก + retry อีกไม่เกิน 3 ครั้ง โดยคงรหัสเดิมเพื่อกันซ้ำ
- retry เฉพาะเมื่อทราบผลล้มเหลวแน่นอน เว้น 1, 2, 4 วินาทีตามลำดับหลังทราบผล
- timeout/ไม่ทราบผลต้องกระทบยอดคำสั่งเดิมก่อน ไม่ส่งซ้ำโดยเดา
  และไม่ถือว่า timeout เป็นผลปฏิเสธ
- ข้อผิดพลาดถาวร เช่น จำนวนต่ำกว่าขั้นต่ำ ไม่ยิงคำขอเดิมซ้ำไร้ประโยชน์
  ให้แสดงและแจ้ง failure; ใช้กฎ failure ของเทรดมือ/บอทตาม trading-safety §11
  โดยไม่รอ retry ที่แก้ผลไม่ได้
- ขอบเขต retry นี้คือการตั้ง protection ไม่อนุญาตสร้าง MARKET exit ใหม่วนเอง
- บันทึกงาน protection พร้อม fill และเริ่มประมวลผลภายใน 1 วินาทีหลังข้อมูลจำเป็นพร้อม
  ไม่รับประกันว่าการตั้งหรือปิดจะสำเร็จภายใน 1 วินาที
- feed ขาดไม่ใช้ราคาเก่า trigger และต้องแสดงว่าการเฝ้าราคาไม่พร้อม
- feed กลับมาใช้ราคาสดที่เชื่อถือได้ หากเข้าเงื่อนไขให้ trigger แม้ราคาไม่เคยเท่าระดับพอดี
- หากราคาข้ามแล้วกลับมาก่อนรับข้อมูล ไม่เดาว่าเคย trigger จาก OHLC

## แหล่งอ้างอิงตลาด

ตรวจเอกสาร [Binance TH REST API](https://www.binance.th/api-docs/en/) ในขั้นเสนอคำตัดสิน
วันที่ 2026-11-02: เอกสารอธิบาย STOP_LOSS/TAKE_PROFIT เป็น MARKET เมื่อเข้าเงื่อนไข
ใช้ประกอบการออกแบบเท่านั้น ไม่ใช่หลักฐานทดสอบ venue หรืออนุมัติ Live/OCO

## ยังไม่ชัด

NC-F17-01..05 ปิดตามคำตัดสินข้างต้นแล้ว หากตรวจรายละเอียดต่อไปพบช่องว่างเรื่องเงิน
ความเสี่ยง หรือขัดกับ spec ต้องบันทึก Needs Clarification ใหม่และหยุดส่วนที่เกี่ยวข้อง
ไม่ตีความคำอนุมัติครั้งนี้ให้ครอบคลุมกฎที่ไม่ได้เสนอ

## NC-F17-06 — Approved 2026-11-04: correction และการจัดสรรใหม่

เจ้าของอนุมัติให้คง conflict ตาม F-15 เมื่อ correction ลด held quantity จนไม่พอ
protection allocations/reservations ไม่เลือกตัดปริมาณจากชุดใดให้อัตโนมัติ
ต้องเก็บ correction fact/audit ตาม append-only contract เดิม แจ้งผู้ใช้ และแสดงว่า
การป้องกันที่ได้รับผลกระทบ unavailable จนข้อมูล authoritative และการจัดสรรถูกต้อง
ห้ามสร้าง exit จากปริมาณที่พิสูจน์ไม่ได้หรือคืน reservation ของ exit ที่ยังไม่ทราบผล
ผู้ใช้จัดสรรใหม่ด้วยการลด/ยกเลิก/แทนที่ชุดที่เลือกตาม revision โดยใช้ปริมาณ authoritative
และห้ามเปลี่ยน exit ที่ส่งแล้ว; กลับมาป้องกันเมื่อข้อมูลพร้อมและ allocation รวมปลอดภัย
การเปลี่ยนชุดต้องบันทึก audit และไม่แก้ประวัติ fill/คำสั่งเดิม

หลักฐาน integration: F-14 NC-48/50 และ F-15 RQ-16/21/25, NC-F15-08;
`infra/paper_orders/corrections.py` มี correction/rebuild และ reservation solvency เดิม
คำตัดสินนี้ขยาย protection integration โดยไม่เปลี่ยนวิธีคำนวณเงินหรือ PnL

## NC-F17-07 — Approved: ขายมือแล้วไม่คืน protection อัตโนมัติ

เจ้าของเลือกแบบ A: ปริมาณที่เลือกขายเองต้องออกจาก protection เดิมก่อนส่งขาย
Paper ประสานการลด protection และรับ SELL ใน transaction เดียวตามแผนเดิม
เมื่อ admission ล้มเหลว rollback ทั้งชุดและคง protection เดิม ไม่ทำให้เกิดช่องว่าง
หากออเดอร์ผ่าน admission แล้ว การลด protection ของปริมาณที่เลือกเป็นการลดถาวร
cancel/expired หรือขายไม่ครบคืนเฉพาะปริมาณที่ยังไม่ขายเป็น available/unprotected
ไม่คืน TP/SL เดิมและไม่ตั้ง protection ใหม่อัตโนมัติ
ส่วนที่ไม่ได้เลือกขายยังอยู่ใน protection เดิม

ตัวอย่าง: protection 1 BTC → SELL LIMIT ที่รับแล้ว 0.4 BTC → fill 0.1 BTC → cancel
ส่วนค้าง 0.3 BTC: ถือจริง 0.9 BTC, protection เดิมเหลือ 0.6 BTC,
ส่วน 0.3 BTC ไม่มี protection ผู้ใช้ตั้งใหม่ได้เอง
ก่อนส่งต้องบอกว่าปริมาณที่เลือกจะออกจาก TP/SL เดิมและจะไม่คืนอัตโนมัติเมื่อยกเลิกขาย
หลัง terminal แสดง unprotected quantity จาก authoritative holdings/reservations
ห้ามคืน reservation หรือแสดงว่า available ก่อนยืนยันผลคำสั่ง

คำตัดสินนี้ไม่เปลี่ยนกฎ TP/SL-triggered exit residual หรือใช้เป็นเหตุเปิด Live
สำหรับ Live ต้องยืนยันการลด/ยกเลิก protection เดิมก่อนส่งขายตาม venue contract
และยังคง Pending Dependency; ห้ามนำการทำสองคำขอภายนอกมาอ้างว่า atomic แบบ Paper

## ขั้นตอนถัดไป

requirements/plan/validation ได้รับอนุมัติ และ NC-F17-01..07 ปิดแล้ว
ดำเนิน implementation M1–M4 ต่อถึง Ready for Code Review ตาม AGENTS.md

## Internal Paper checkpoint - NC-SET4-12 Approved A

Owner approved the [internal-pilot requirements/plan/validation amendment](internal-paper-acceptance-amendment.md)
on2026-11-06. Use its parameters as the single source of truth. Scoped harness/checks
and conditional campaign are authorized. Existing100-account results, Release gates,
Completed definition and Git/deploy permissions remain unchanged.


NC12 §16 — owner approved2026-11-07: internal20-account engine processing acceptance
is p95≤500ms/p99≤2s; retain250ms/1s as a separately reported target with warning.
This supersedes IP-R4 only for internal engine-processing acceptance. TP/SL start≤1s,
snapshot limits, financial/safety correctness, workload/duration and100-account Release
criteria remain unchanged. Complete owned pool inventory includes the read-only admin
observer; missing evidence is Incomplete and proven violations remain Failed. See
[approved §16](internal-paper-acceptance-amendment.md#16-revised-acceptance-and-complete-owned-inventory--approved2026-11-07).


NC12 §18 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V2 changes
W2 only to10commands/s/1200s with120cycles-per-owner/12000commands unchanged.
Completion allowance1260s; required book inputs12000 at10Hz. V1/defaults, money,
worker/pool/coordinator/retry and other phase definitions unchanged. Actual V2 name
is forwarded to worker subprocesses and recorded in manifests/timing revision.
Tests233 passed8.77s;5 profile rechecks passed0.31s after test typing correction.
Scoped Ruff/format passed5repo files and private runner; mypy passed5files. Private
runner retains its pre-existing broad cleanup exception with BLE001 excluded only
for that file. Production source hashes unchanged; prior safety evidence remains
valid. W1§16 passing evidence reused only for unchanged assertions. All earlier
Failed/Incomplete runs retained. No§17 diagnostic added or executed.

Next: one approved fresh-DB V2 W2 withpreflight (~25–30min including20min measured),
then overflow/W3/W4 conditional on passing each gate. No repeated W1/D20. A failed/
incomplete gate stops without retry. Internal pilot and F17 remain open pending gates.


NC12 §21 Approved/implemented,2026-11-07. Explicit PAPER_INTERNAL20_V3 changes
W3 only to1800s/30cycles-per-owner/3000commands;7pinned fault kinds/durations retained
at180..1260s offsets. Selected duration drives hold/minimum, RSS window and30periodic
snapshot rounds(620total includingfinal20), with15000inputs and1830s completion
ceiling. V1/V2/default4h/282cycles/original schedule and240periodic rounds unchanged.
Short stability is labelled separately;4h Release remains Pending Full Validation.

Targeted220passed10.73s;6affected final rechecks passed1.50s; scoped Ruff/format and
mypy passed5repo files(private runner scoped Ruff excludes pre-existing BLE001 only).
Actual parent/reporting regression verifies1800s hold/minimum,30snapshot rounds,
short RSS and unchanged financial/counter/latency/resource predicates. Production
source hashes unchanged. Applicable W1/W2/overflow/production safety evidence reused;
no ceremonial reruns. See nc12-section21-*.xml/logs for evidence.

Next: approved one fresh-DB V3 short W3 with existing preflight, estimated35–45min
including30min measured/final replay/cleanup; passing permits W4. A failed/incomplete
gate stops without retry. Prior owner-stopped W3 remains Incomplete; no4h acceptance.
