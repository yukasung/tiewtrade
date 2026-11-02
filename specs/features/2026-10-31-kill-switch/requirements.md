# F-19 — ปุ่มหยุดบอท (Kill Switch) — Requirements

สถานะ: **Approved 2026-11-02** — รวม RQ-07 deep-review และ RQ-22/23 SLA/activation amendments
วันที่: 2026-10-31

## ทำไมต้องมี

ผู้ใช้ต้องหยุดบอทและจัดการออเดอร์ค้างได้ทันที โดยไม่ทำให้ position ที่ถืออยู่
สูญเสียการป้องกัน ส่วนแพลตฟอร์มต้องหยุดการเพิ่มความเสี่ยงของทั้งระบบได้เมื่อมีปัญหา
สถานะหยุดต้องอยู่ต่อหลัง restart และต้องรู้ว่าออเดอร์ใดจัดการแล้วหรือยังมีปัญหา
F-19 เป็น safety dependency ก่อน F-22 ตาม roadmap ไม่ใช่การอนุญาตเปิด Live

## ขอบเขต

- คำสั่งหยุดของผู้ใช้, ตัวหยุดระดับแพลตฟอร์ม, สถานะ durable, หน้าสรุปและการเปิดกลับ
- การจัดการ queued/active/unknown orders ในขอบเขตหยุด พร้อมผลรายออเดอร์และ audit
- ใช้กฎโดเมนเดียวกันสำหรับ Paper/Live แต่แยกเงิน ออเดอร์ และ execution ตาม ADR-004
- เชื่อมกลไกหยุดเพราะ loss limit ของ F-18 โดยไม่เปลี่ยนสูตร loss, latch หรือ reset
- ไม่สร้างกลยุทธ์หรือวงจรชีวิตบอทแทน F-20 ไม่สร้าง Live execution แทน F-22
  และไม่สร้างช่องทางแจ้งเตือนแทน F-26/F-36/F-27; ส่งมอบ Paper authority/UI
  และ integration contracts ก่อนโดยติดตาม dependency ที่เหลือตาม NC-F19-03
- ไม่เพิ่ม cooling-off เทรดมือ ไม่เพิ่มอำนาจ admin เหนือเงิน/position ของผู้ใช้
  และไม่เปลี่ยนเงื่อนไขสลับ MANUAL/BOT

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | ผู้ใช้สั่งหยุดได้ในคลิกเดียวจากทุกหน้าจอภายในแอปที่ลงชื่อเข้าใช้ โดยไม่ต้องยืนยัน TOTP ซ้ำ | trading-safety §8; security §1 |
| RQ-02 | ปุ่มหยุดของผู้ใช้แยก Paper และ Live ชัดเจน: ปุ่ม Paper หยุดเฉพาะ Paper ของตัวเอง ปุ่ม Live หยุดเฉพาะ Live ของตัวเอง แสดงโหมดของปุ่มชัดเจน ไม่กระทบอีกโหมดหรือผู้ใช้อื่น ไม่มีปุ่ม “หยุดทั้งหมด” ของผู้ใช้ | เจ้าของตัดสิน 2026-10-31 — NC-F19-01; trading-safety §8 |
| RQ-03 | การหยุดไม่เปลี่ยน BOT เป็น MANUAL และไม่ให้ manual opening ใน BOT; บัญชี MANUAL เปิดความเสี่ยงใหม่หลัง user stop ได้ตาม safety gates เดิม โดยคำสั่งใหม่นั้นต้องเกิดหลัง durable stop cutoff ตาม RQ-07 ไม่ถูกนับเป็นงานค้างของ stop ครั้งเดิม การปิด/ลด position และ cancel ทำได้ทุกประเภทภายใต้ durable intent/audit เดิม | trading-safety §3/8/9; F-08 RQ-16 |
| RQ-04 | ผู้ใช้หยุดบอททั้งหมดในโหมดที่เลือก และยกเลิกออเดอร์ที่ยังไม่เข้าทั้งของบอทและเทรดมือในโหมดนั้น รวมส่วนที่เหลือหลัง partial fill โดยไม่ปิดส่วนที่เข้าจริงและไม่ยกเลิก TP/SL; อีกโหมดไม่ถูกแตะตาม RQ-02 | trading-safety §8/11 |
| RQ-05 | Platform Admin และ Platform Owner สั่งหยุดทั้งระบบได้: หยุดบอททุกคน บล็อกและทำให้คำสั่งเพิ่มความเสี่ยงที่ยังไม่ส่งทั้ง manual/bot จบด้วยผลว่าถูก platform stop และยกเลิกออเดอร์บอทที่ส่งแล้วแต่ยังไม่เข้ารวมส่วนค้างหลัง partial fill; ไม่ยกเลิกออเดอร์มือที่ส่งแล้ว ไม่แตะ position/TP/SL และไม่ขวางคำสั่งลดความเสี่ยงของผู้ใช้ ต้องแจ้งผู้ใช้ทุกคนทันทีว่าถูกหยุดพร้อมเหตุผล โดยแสดงข้อความที่คงอยู่ในแอประหว่างรอช่องทาง F-26/F-36/F-27 และบันทึกช่องทางที่ยัง Pending Dependency ตาม NC-F19-03 | mission §2; trading-safety §8 |
| RQ-06 | การเปิดกลับจาก platform stop ทำได้เฉพาะ Platform Owner ผู้ใช้และ Platform Admin ปลดไม่ได้; การเปิดกลับระดับหนึ่งต้องไม่ข้ามสาเหตุหยุดหรือ safety gate อื่นที่ยังมีผล | trading-safety §8/13 |
| RQ-07 | แต่ละ stop ต้องมี durable identity/revision และ cutoff ที่จัดลำดับ atomically กับการรับคำสั่ง: opening intent ที่ยังไม่ส่งและอยู่ก่อนหรือเท่ากับ cutoff ต้องอยู่ใน stop snapshot และจบด้วยผลยกเลิกเพราะหยุด ห้ามค้างกำลังส่ง; ใบที่ส่งแล้วหรือไม่รู้ผลห้ามเขียนทับเป็นยกเลิก ให้ reconcile ตาม RQ-08/09 โดย user stop ยกเลิกส่วนค้างของ bot/manual แต่ platform stop ยกเลิกเฉพาะ bot และคง manual ที่ส่งแล้ว; terminal history ไม่เปลี่ยน คำสั่ง MANUAL ที่รับหลัง user stop cutoff เป็น intent ใหม่ตาม RQ-03 ส่วน BOT ถูกปฏิเสธจนเปิดกลับ และ platform stop ปฏิเสธทั้ง manual/bot จน Platform Owner เปิดกลับ คำสั่งลดความเสี่ยงในคิวดำเนินต่อ; stop ที่เกิดหลังรับ intent แต่ก่อน execution ต้องทำให้ intent นั้นไปต่อไม่ได้แม้ stop ถูกเปิดกลับก่อน worker เห็น | Deep-review amendment 2026-10-31; trading-safety §4/8 |
| RQ-08 | ชั้น execution ตรวจ stop identity/revision ล่าสุดและลำดับของคำสั่งอีกครั้งก่อนส่งจริง; หาก stop กับ submit แข่งกัน ต้องมีผล deterministic ตาม durable ordering ใน RQ-07 โดยไม่มีช่องที่คำสั่งก่อน cutoff หลุดออกไป ใบที่ออกไปแล้วห้ามสรุปว่าทิ้งสำเร็จ ให้ตามผลและกระทบยอดตามกฎ unknown outcome โดยไม่ส่ง opening ซ้ำ | trading-safety §4/8/10 |
| RQ-09 | ตัวไล่เก็บ unknown orders ทำงานต่อขณะหยุด: สำหรับ user stop ให้ยกเลิกออเดอร์ bot/manual ที่ยังไม่เข้าหรือส่วนค้าง; สำหรับ platform stop ให้ยกเลิกเฉพาะออเดอร์ bot และไม่ยกเลิกออเดอร์ manual ที่ส่งแล้ว ผลว่าเข้าจริงหรือ partial fill ให้บันทึกจำนวนจริงและแจ้งผู้ใช้ทันที ห้ามเปิดไม้ใหม่หรือปลุกบอทจาก recovery | trading-safety §8; RQ-04/05 |
| RQ-10 | Bracket ที่เข้าจริงแต่ขาด TP/SL ต้องจัดการ protection ต่อแม้หยุด ตาม partial-fill/retry/failure policy เดิม ไม่สร้าง SL ที่ผู้ใช้หรือกลยุทธ์ไม่ได้ขอ | trading-safety §8/11 |
| RQ-11 | บันทึกสถานะหยุด identity/revision/cutoff ขอบเขต ผู้สั่ง เวลา และสาเหตุในฐานข้อมูลสำเร็จก่อนแสดงว่าหยุดแล้ว การกดซ้ำหรือ retry หลังไม่ทราบผลต้องตรวจผล intent เดิมและไม่สร้าง stop ซ้ำ ไม่ทำให้ target snapshot เปลี่ยนย้อนหลัง และไม่เปิดกลับโดยปริยาย | trading-safety §4/8/9 |
| RQ-12 | บอทหยุดโดยไม่รอผล cancel; UI มีสามสถานะ: กำลังหยุดพร้อมจำนวนค้าง, หยุดแล้วครบเมื่อทุกใบรู้ผลและจัดการครบ, หยุดแล้วแต่มีปัญหาพร้อมจำนวนและรายการ ห้ามรายงานครบเมื่อยังค้นหาเป้าหมายไม่ครบหรือมี unknown | trading-safety §8 |
| RQ-13 | Cancel retry ด้วย backoff ตาม rate limits; เมื่อค้างครบ 1 นาทีต้องแจ้งผู้ใช้ทุกช่องทางที่เปิดไว้และแสดงรายการพร้อมทางไปจัดการตรงที่ Binance สำหรับ Live แต่ยัง retry เบื้องหลังจนรู้ผล ออเดอร์ที่ fill แข่งกับ cancel ต้องเข้าสู่ RQ-09/10 ไม่ถือเป็น cancel failure | trading-safety §7/8 |
| RQ-14 | หลัง restart: user/platform/system stop ยังคงหยุด; อ่านสาเหตุไม่ได้หรือไม่มีบันทึกให้ถือว่ายังหยุด การล่ม/deploy ที่ไม่มี stop ค้างกลับทำงานได้เมื่อกระทบยอดแล้วและผ่าน gates เดิม | trading-safety §8/10 |
| RQ-15 | ผู้ใช้เปิดกลับเองได้เมื่อบัญชียังเป็น BOT: user stop ต้องเป็นของตัวเอง; system stop ต้องมี cause-specific proof จากระบบว่าต้นเหตุแก้แล้ว หาก feature ต้นทางยังไม่มี proof contract ให้คง fail-closed ทุกกรณีต้องเห็นสรุป position ค้าง ออเดอร์ที่ยกเลิก/ยกเลิกไม่สำเร็จ และกระทบยอดเสร็จก่อน โดยไม่ต้อง TOTP คำสั่งเปิดกลับผูก expected stop identity/revision และ reconciliation/snapshot revision ที่ผู้ใช้เห็น; ตอนดำเนินการตรวจซ้ำกับ stop ล่าสุดและ gates ทุกข้อ หากมี stop ใหม่หรือข้อมูลสรุปเปลี่ยนต้องปฏิเสธให้ดูข้อมูลล่าสุด ห้ามคำสั่งเก่าหรือ exact retry ปลด stop ครั้งใหม่ และห้ามปลด platform stop/loss latch/cause อื่นตามไปด้วย | NC-F19-02; trading-safety §4/8; security §1 |
| RQ-16 | หยุด/เปิดกลับและผลจัดการรายออเดอร์ต้องมี append-only audit ระบุ actor/scope/time/outcome โดยไม่เปิดเผย secret; user routes และข้อมูลต้องแยกเจ้าของ และตรวจสิทธิ์แพลตฟอร์มฝั่ง server | mission §2/8; trading-safety §9; security |
| RQ-17 | คำสั่งหยุดต้องทำงานได้แม้ส่วนอื่นมีปัญหา เช่น strategy/market data/cancel ไม่พร้อม; ถ้าบันทึก durable intent/audit ไม่ได้ห้ามอ้างว่าหยุดสำเร็จ ถ้า commit ไม่ทราบผลต้องตามผลคำขอเดิมก่อน ไม่ข้ามฐานข้อมูลเพื่อส่งคำสั่ง | trading-safety §8/9; NC-F16-01 |
| RQ-18 | Loss stop ของ F-18 ใช้กลไกหยุดร่วมตามสัญญาที่อนุมัติไว้; การเปิดกลับจาก user/platform stop ไม่ล้าง loss latch และ loss reset ไม่ปลด user/platform/system stop อื่น | trading-safety §8/13; F-18 requirements |
| RQ-19 | แยกพักอัตโนมัติเพราะข้อมูลไม่พร้อมจาก durable stop ให้ชัด: การกลับมาของราคา/การกระทบยอดไม่ปลด user/platform/system stop และไม่แทน loss reset | trading-safety §8/12/13 |
| RQ-20 | ข้อความปุ่ม สถานะ ผลรายออเดอร์ และสรุปก่อนเปิดกลับรองรับไทย/อังกฤษ ใช้ admin template และ UI components กลางตาม frontend standard | mission R-20; AGENTS.md; frontend standard |
| RQ-21 | ไม่เปิด Live โดยปริยาย ไม่ส่ง Live orders ใน automated validation และไม่อ้างผล Paper ว่ารับรอง Live หรือ bot integration ที่ยังไม่มี | mission §4; trading-safety; testing §7 |
| RQ-22 | ภายใต้ workload profile ที่อนุมัติ risk acknowledgement ต้องครบทุก ready input โดยไม่มี missing/clock error; ทั้งราย owner และทั้ง run อย่างน้อย 99.5% ภายใน3วินาที และอย่างน้อย99.9%ภายใน5วินาที; ทุก inputต้องไม่เกิน6วินาที เกณฑ์นี้ไม่อนุญาตให้ลบ/รวม/เลื่อน input เพื่อซ่อน tail และไม่ลด correctness, idempotency, fail-closed, financial หรือ stop safety gates | เจ้าของอนุมัติ 2026-11-02 — SLA amendment จากหลักฐาน NC17 |
| RQ-23 | ระบบ production เปิด Paper และ Live พร้อมกันเมื่อ candidate รวมผ่าน release/activation gates และ dependencies ทั้งหมดเท่านั้น ระหว่างพัฒนาแต่ละ feature อาจเป็น Development Complete หลัง targeted safety/review/CI โดยยังไม่อนุญาต production activation; ห้ามใช้ Paper เป็น production rollout ระหว่างรอ Live | เจ้าของตัดสิน 2026-11-02 — all-or-nothing activation |

## ของเดิมที่สำรวจพบ

รายการนี้ใช้เป็นข้อมูลตั้งต้นในขั้น plan หลังอนุมัติ requirements ไม่ใช่อนุมัติให้แก้โค้ด:

- `backend/src/tiewtrade/core/risk_limits.py`: `RiskStop` และ `RiskStopProgress`
- `backend/src/tiewtrade/infra/risk_limits/stops.py`: durable Paper stop target enrollment,
  cancel/recovery และผลรายเป้าหมายของ F-18
- `backend/src/tiewtrade/infra/risk_limits/stop_views.py`: อ่านผล stop ภายใต้ owner scope
- `backend/src/tiewtrade/infra/risk_limits/boundaries.py` และ `policy.py`: risk admission/fences
- `backend/src/tiewtrade/services/engine/risk_limit.py`: engine integration ของ F-18
- `backend/src/tiewtrade/services/api/risk_limit_routes.py` และ `frontend/src/riskLimits.ts`:
  API อ่านผล stop ของ F-18

ของเดิมรองรับ loss stop ไม่ใช่หลักฐานว่ามี user/platform kill switch หรือ bot/Live lifecycle แล้ว
ต้องประเมินความต่างของ target scope และ authority ใน plan ห้ามขยาย predicate จนแตะ TP/SL

## กฎความปลอดภัยที่เกี่ยวข้อง

- trading-safety §3/4/5/7/8/9/10/11/12/13 และ security §1
- mission §2/4/5/8 และ ADR-004: อำนาจแพลตฟอร์ม หนึ่งบัญชี แยก Paper/Live
- F-18 requirements และ amendments ที่ Approved: คงสูตร/latch/reset และข้อยกเว้น Paper MANUAL
- architecture/database/security: single writer, owner scope, RLS, durable intent และ append-only audit
- testing §7: correctness/safety ทันทีตามผลกระทบ; เกณฑ์ชุดยาวท้ายชุดที่ 5 และ dependency
  ต้องระบุใน validation ก่อนลงมือ ไม่ถือ Pending ว่าผ่าน

## คำตัดสินจาก Needs Clarification

### NC-F19-01 — Closed (2026-10-31): ปุ่มผู้ใช้แยก Paper กับ Live

เจ้าของสั่ง “ไม่ต้องมีปุ่มหยุดทั้งหมด ให้แยกใช้งานปุ่มกันชัดเจน”:
ปุ่ม Paper หยุดเฉพาะ Paper ปุ่ม Live หยุดเฉพาะ Live ของตัวเอง และแสดงโหมดชัดเจน
ไม่มีปุ่มหยุดทั้งหมดของผู้ใช้ แทนขอบเขตสองระดับเดิมใน trading-safety §8
ไม่เปลี่ยนตัวหยุดระดับแพลตฟอร์มของ Platform Admin/Owner ใน RQ-05/06
ปิดข้อบล็อกเรื่องขอบเขตโหมด; requirements และ NC-F19-02/03 ได้รับอนุมัติต่อมาในวันเดียวกัน

### NC-F19-02 — Closed (2026-10-31): เจ้าของบัญชีเปิดกลับหลังระบบยืนยันว่าแก้ต้นเหตุแล้ว

เจ้าของอนุมัติข้อเสนอ A: หลังระบบพิสูจน์ตามสัญญาของสาเหตุนั้นว่าต้นเหตุแก้แล้ว
เจ้าของบัญชีกดรับทราบและเปิดกลับผ่านหน้าสรุปกับ reconciliation เดียวกับ user restart
โดยไม่ต้อง TOTP คำสั่งต้องผูก revision ตาม RQ-15 และห้ามปลด platform stop, loss latch
หรือสาเหตุอื่นตามไปด้วย สาเหตุที่ยังไม่มี proof contract ใน feature ต้นทางต้องคง fail-closed
และ Pending Dependency ห้ามใช้การรับทราบของผู้ใช้แทนหลักฐานว่าแก้ต้นเหตุแล้ว

### NC-F19-03 — Closed (2026-10-31): ทำ Paper และ integration contracts ก่อน

เจ้าของอนุมัติข้อเสนอ A: F-19 ทำ user/platform stop authority และ UI พร้อม Paper execution
ที่มีจริง รวมสัญญาเชื่อมต่อที่ทดสอบได้สำหรับ bot, Live และ notifications พร้อมข้อความ/สถานะ
ที่คงอยู่ใน UI การแจ้งทุกช่องทางและ real bot/Live integration เป็น Pending Dependency
ใน validation/roadmap ห้ามเรียก Completed หรือเปิดความสามารถที่ยังไม่ผ่าน safety integration
จนกว่า dependency และเกณฑ์ตรวจรับของมันจะผ่าน

requirements ฐานเดิมและ NC-F19-01..03 Approved แล้ว แต่คำแก้ RQ-07 ในหัวข้อถัดไป
ยังต้องอนุมัติใหม่พร้อม plan.md และ validation.md ก่อน implementation ตาม AGENTS.md

### V-20 core-loss workload amendment — Approved 2026-10-31

- core workload 100 owners ต้องคง baseline/order volume, rates, thresholds และ partial/correction
  scenarios เดิม แต่ไม่ทำ loss breach/reset/reseed กับ selected core owner เพราะ durable LOSS_LIMIT
  stop ต้องบล็อก opening ต่อหลัง reset ตาม RQ-13/15/18
- เพิ่ม dedicated MANUAL loss owner นอก core counters เพื่อรัน partial exposure จริง, loss breach,
  stop reconciliation, reset และ opening probe ซึ่งต้องยังถูกปฏิเสธด้วย active LOSS_LIMIT stop
- dedicated owner ต้องรวมใน resource/connection/stop evidence แต่ห้ามเปลี่ยน core conservation
  denominator และ amendment นี้ไม่เพิ่ม MANUAL resume, automatic resume หรือเปลี่ยน production policy

### NC-F19-05 platform reconciliation clock — Approved 2026-10-31

- position activity ที่เปลี่ยนระหว่าง active platform stop ต้องเพิ่ม reconciliation revision ใน
  transaction เดียวกัน เพื่อให้ Platform Owner ใช้ snapshot เก่า resume ไม่ได้
- position activity ระหว่างที่ไม่มี active platform stop ต้องไม่เขียน global reconciliation clock
  เพื่อตัด global hot row ออกจาก normal trading
- สิทธิ์อ่าน PLATFORM cause และ UPDATE clock ให้เฉพาะ SECURITY DEFINER trigger owner
  (`tiewtrade_migrator`) ผ่าน FORCE RLS policy ที่จำกัดขอบเขต; API/engine ไม่มีสิทธิ์ UPDATE clock
- transaction ที่ rollback ต้องไม่ทิ้ง clock revision และการแก้นี้ไม่เปลี่ยน position, PnL,
  stop authority หรือ resume criteria อื่น

### NC-F19-06 stop-worker idle cadence — Approved 2026-10-31

- ใช้ risk worker/pools เดิมและคง active tick 20ms; เมื่อ stop request, platform discovery และ
  risk-stop rounds ว่างทั้งหมด ให้ idle delay เพิ่มแบบ bounded 20→40→80→160→250ms และไม่เกิน 250ms
- เมื่อพบ processed/deferred/discovered target, pending risk-stop หรือ active platform stop ต้องกลับ
  20ms ทันที; restart ต้องตรวจ active platform stop ในรอบแรกโดยไม่พึ่ง in-memory state เก่า
- cadence นี้ห้ามเปลี่ยน durable cutoff/fence, idempotency, retry due time, fairness cursor,
  target policy, fail-closed behavior หรือเพิ่ม worker/connection budget; idle request detection
  เพิ่มได้สูงสุด 250ms ก่อนเริ่ม bounded processing

## Review Amendment — Approved 2026-10-31

แก้ RQ-07 หลัง deep review ให้แยก queued-unsent, sent/unknown, active remainder และ terminal
ตาม RQ-08/09 อย่างชัดเจน และคง historical fence สำหรับ intent ที่รับก่อน stop แม้มี resume
เกิดก่อน worker ประมวลผล คำแก้นี้ไม่เปลี่ยนสิทธิ์ MANUAL หลัง user cutoff, ขอบเขต
user/platform cancellation หรือสิทธิ์ลดความเสี่ยง เจ้าของอนุมัติ amendment พร้อม plan/validation
วันที่ 2026-10-31 ก่อน implementation

## SLA and activation amendment — Approved 2026-11-02

เจ้าของอนุมัติข้อความ
`approve F-19 SLA: 99.5% within 3s, 99.9% within 5s, all within 6s; stop NC25`
หลังพิจารณาหลักฐาน NC17 ซึ่งได้ run-wide99.858278%≤3s, ownerต่ำสุด99.575487%≤3s,
มี3/918703samplesเกิน5sจากownerเดียว (ownerนั้น99.967346%≤5s) และ max5.034698s.

เกณฑ์ใหม่ใช้ทั้งราย owner และทั้ง run ที่3s/5s พร้อม absolute6s; acknowledgementsต้องครบ
และ measurement/clock errorsยัง fail closed. Correctness/safety/financial/load/resource/
duration/source criteriaไม่เปลี่ยน การอนุมัตินี้เลือกหยุด NC-F19-25 ก่อน implementation/
execution และห้ามสร้าง clock diagnostic ต่ออัตโนมัติ. Historical Failed ตามเกณฑ์เก่าเก็บไว้;
การประเมินใหม่ต้องเป็น derived evidence แยกและไม่รับรอง current/final candidate แทน run จริง.

เจ้าของกำหนดเพิ่มเติมว่า production ต้องเปิด Paper/Live พร้อมกันเมื่อระบบครบเท่านั้น;
การแยก Development Complete ออกจาก System Ready มีไว้ลดงานทดสอบซ้ำระหว่างพัฒนา ไม่ใช่
อนุญาต Paper-only production หรือข้าม release/Live gates.
