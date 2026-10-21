# F-37 — รายการคู่เทรดที่รองรับและการจัดการ — Requirements

สถานะ: **Approved — เจ้าของสั่ง “ทำต่อ” วันที่ 2026-10-21 หลังเสนอ requirements และตัวเลือกแนะนำ NC-F37-01..03; NC-F37-04 เป็นคำชี้แจงแก้ข้อความขัดกันและรออนุมัติพร้อม plan/validation**

วันที่: 2026-10-21

## ทำไมต้องมี

ระบบใช้รายการคู่เทรดคงที่ `BTC/USDT` และ `ETH/USDT` จาก F-38 อยู่ใน source code,
database constraints, market-data workers, API contract และหน้าเว็บหลายส่วน จึงยังเพิ่มหรือถอน
คู่เทรดโดย Platform Admin ตาม `mission.md` หัวข้อ 2 และ 6 ไม่ได้ และ F-16 ยังไม่มี
แหล่งความจริงที่เปลี่ยนได้สำหรับตรวจว่าคำสั่งเพิ่มความเสี่ยงใช้คู่ที่รองรับอยู่จริง

F-37 ต้องสร้างรายการกลางที่เปลี่ยนได้อย่างปลอดภัย ใช้ร่วมกันทั้ง Paper/Live,
manual/bot และ market-data โดยการเพิ่มคู่ต้องไม่เปิดให้เทรดก่อน dependencies พร้อม
ส่วนการถอนต้องหยุดการเปิดความเสี่ยงใหม่ทันที แต่ยังรักษา position, order, ledger,
ประวัติ และทางออกสำหรับลดความเสี่ยงเดิม

งานนี้ไม่ตัดสินชนิดออเดอร์ของ F-16; `NC-08` ยังเป็น Needs Clarification แยกต่างหาก
แม้ F-37 เสร็จแล้ว

## ขอบเขต

### ทำ

- ให้ Platform Admin และ Platform Owner ดูรายการคู่เทรดและเพิ่ม/ถอนคู่ผ่านหน้าจอและ API
- ใช้ catalog เดียวเป็นแหล่งความจริงสำหรับ API, market-data, Paper/Live order validation,
  manual/bot selection และ frontend โดย runtime เริ่มจาก BTC/USDT กับ ETH/USDT ตาม F-38
- ตรวจคู่ใหม่กับ Binance TH Spot public metadata และข้อจำกัดของคู่แบบ fail-closed
- เตรียม market-data dependencies ของคู่ใหม่ก่อนอนุญาตให้เปิดความเสี่ยง และเปิดใช้งานแบบ atomic
- ถอนคู่แบบหยุดการเปิดความเสี่ยงใหม่ โดยไม่ลบหรือแก้ข้อมูลการเงินและประวัติเดิม
- คงเส้นทางลดความเสี่ยงสำหรับ position ที่มีอยู่ตาม trading-safety §3
- หยุดบอทที่ผูกกับคู่ที่ถูกถอนและสร้างหลักฐาน/audit ที่ติดตามได้
- แสดงสถานะคู่และเหตุผลที่ยังเปิดใช้งานไม่ได้หรือถูกถอนได้ทั้งไทยและอังกฤษ
- รองรับ concurrent admin actions, retries, restart และ rollout โดยไม่เกิด catalog สองสถานะ

### ไม่ทำ

- ไม่ตัดสินหรือ implement ชนิดออเดอร์ Market/Limit/อื่น ๆ ของ `NC-08`
- ไม่สร้างหน้าสั่งออเดอร์ของ F-16 และไม่เพิ่ม order transport ของ Live Trading
- ไม่เปิด Live Trading, ไม่ส่งออเดอร์จริง และไม่เรียก private Binance endpoint
- ไม่เพิ่ม Futures, COIN-M, exchange อื่น หรือ quote asset อื่นนอก Binance TH Spot/USDT
- ไม่สร้างกฎคัดสภาพคล่องหรือเพดาน order size ใหม่จากตัวเลขครั้งเดียว
- ไม่ลบ candle, indicator, order, balance, position, ledger, audit หรือ history เมื่อถอนคู่
- ไม่เปลี่ยนสูตร indicator, Money/Quantity, PnL, margin, leverage หรือ liquidation
- ไม่ถือว่าการเพิ่มคู่หนึ่งคู่ทำให้ performance/readiness ของคู่นั้นผ่านโดยอัตโนมัติ

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | ระบบต้องมี supported-pair catalog กลางที่ durable และ versioned; ทุก consumer ใช้ snapshot/version เดียวกันหรือ contract ที่สร้างจากแหล่งนี้ ห้ามมี allowlist runtime ซ้ำที่คลาดกัน | mission §6; F-38; architecture §1 |
| RQ-2 | seed/migration แรกต้องรักษา BTC/USDT และ ETH/USDT เป็นคู่ที่เปิดใช้งานอยู่ตรงกับ F-38 โดยไม่ลบหรือเปลี่ยนข้อมูล market/trading เดิม | F-38; database §6 |
| RQ-3 | F-37 รองรับเฉพาะ Binance TH Spot ที่ quote เป็น USDT; pair identifier ต้องเก็บ base/quote แยกกันและ canonicalize ตาม `Symbol` เดิม ห้ามใช้การต่อ string เป็น identity ภายใน | mission §6; venue contract; existing `tiewtrade.venues.Symbol` |
| RQ-4 | การเพิ่มคู่ต้องยืนยันจาก public venue metadata ว่าคู่มีอยู่, อยู่ในสถานะที่เทรดได้ และมี price/quantity/notional constraints ที่ระบบอ่านได้ครบ; timeout, protocol error, ข้อมูลผิดหรือไม่ครบต้อง fail closed และห้ามเปิดคู่ | F-35; trading-safety §3/10 |
| RQ-5 | คู่ใหม่ต้องยังไม่ปรากฏเป็นทางเลือกสำหรับเปิดความเสี่ยงจน market-data/bootstrap/readiness ที่จำเป็นต่อ runtime ปัจจุบันพร้อมครบ; การเตรียมล้มเหลวหรือ service restart ต้องกลับมาทำต่อได้โดยไม่เปิดครึ่งระบบ | F-09–F-12; trading-safety §6/10 |
| RQ-6 | การ activate ต้อง atomic และมี catalog revision แบบเพิ่มขึ้นทางเดียว; reader ต้องเห็น snapshot ก่อนหรือหลังที่ครบชุด ห้ามเห็นคู่เปิดใช้ใน order path แต่ไม่มีใน market-data/UI หรือกลับกัน | architecture §5; database §2; concurrency safety |
| RQ-7 | ทุกคำสั่งที่เพิ่มความเสี่ยงจากคนหรือบอทต้องตรวจ catalog ล่าสุดที่จุดตรวจกลางก่อนเกิด economic effect; คู่ที่ไม่ active ต้องถูกปฏิเสธแบบ typed และต้องไม่มี order, reservation, fill หรือ ledger effect | trading-safety §3; roadmap F-37/F-16 |
| RQ-8 | คำสั่งลดความเสี่ยงต้องไม่ถูกปฏิเสธเพียงเพราะคู่ถูกถอน และต้องยังผ่านข้อจำกัด pair/position/risk-reduction เดิมทั้งหมด ห้ามใช้ข้อยกเว้นนี้เปิดหรือกลับฝั่ง position | trading-safety §3 |
| RQ-9 | การถอนคู่ต้องกัน opening admission ใหม่แบบ atomic กับ order writer และ bot admission; request ที่แข่งกับการถอนต้องมีผู้ชนะตามลำดับเดียวและห้ามเกิด unintended opening หลังสถานะถอน commit | mission §6; single-writer; concurrency safety |
| RQ-10 | การถอนห้ามแก้หรือลบ position, balance, reservation, order, execution, ledger, PnL, audit หรือ market history เดิม; ผู้ใช้ยังต้องอ่านสถานะเดิมและปิด/ลด position เองได้ | mission §6; database §4; trading-safety §3 |
| RQ-11 | market metadata และข้อมูลที่จำเป็นต่อการตีราคาและลดความเสี่ยงของ exposure เดิมต้องยังพร้อมหลังถอนจนกว่าจะพิสูจน์ได้ว่าไม่มี dependency ที่ต้องใช้; system ห้ามแสดงศูนย์หรือข้อมูลเก่าเป็นข้อมูลสด | mission §6; trading-safety §6/10/12 |
| RQ-12 | บอทที่ใช้คู่ซึ่งถูกถอนต้องหยุดสร้าง signal/order ใหม่แบบ fail-closed และมี durable reason ที่ผู้ใช้และ operator ตรวจได้; restart/retry ต้องไม่เปิดบอทนั้นกลับเองขณะคู่ยังถูกถอน | mission §6; trading-safety §10 |
| RQ-13 | API/UI ต้องแยกอย่างน้อยสถานะกำลังเตรียม, เปิดใช้, ถอน/ห้ามเปิดใหม่ และล้มเหลว พร้อม revision, เวลาเปลี่ยน, ผู้กระทำ และ safe reason; trader เห็นเฉพาะข้อมูลที่จำเป็น ส่วน admin เห็นสถานะจัดการและความคืบหน้า | mission §2/6; security §2/4 |
| RQ-14 | mutation เพิ่ม/ถอนต้องใช้ idempotency key และ canonical payload; exact retry คืนผลเดิม, key เดิม payload ต่างต้อง conflict, concurrent requests ต้องเกิด transition/audit ครั้งเดียว | retry safety; trading-safety §4 |
| RQ-15 | เฉพาะ Platform Admin และ Platform Owner เท่านั้นที่เพิ่ม/ถอนได้; server ตรวจสิทธิ์ที่จุดเดียวและ default deny ผู้ใช้ทั่วไปหรือ process role ที่ไม่เกี่ยวข้องต้องอ่าน/เขียน admin state ไม่ได้ | mission §2; security §2; database §5 |
| RQ-16 | ทุก transition และ rejection ที่ผ่าน authenticated admin mutation ต้องมี append-only audit ระบุ actor, pair, action, old/new state, revision, outcome และ safe reason โดยไม่มี cookie, token, API key หรือ raw venue payload | trading-safety §9; security §4 |
| RQ-17 | PostgreSQL ต้องบังคับ uniqueness/canonical pair, allowed lifecycle transition, monotonic revision และ process grants; migration/rollout ต้องเป็น additive ก่อนย้าย consumer และ old binary ต้องไม่สามารถเปิดคู่หรือเขียน catalog ข้าม capability fence | database §5/6; rollout safety |
| RQ-18 | เมื่อ PostgreSQL/catalog/readiness ตรวจไม่ได้ order path และ bot ต้อง fail closed สำหรับการเพิ่มความเสี่ยง; ห้าม fallback ไป static source list หรือ frontend cache ส่วน read UI ต้องระบุ unavailable/stale อย่างชัดเจน | trading-safety §3/10; security fail-closed |
| RQ-19 | Frontend ต้องโหลด catalog จาก server contract เดียว, ทิ้ง stale response เมื่อ identity/revision เปลี่ยน, ไม่เสนอคู่ที่ยังไม่ active สำหรับ opening และไม่เดาสถานะจากรายการ cache เดิม | F-08/F-12 patterns; security §2 |
| RQ-20 | หน้า admin ต้องใช้ component กลางและ pattern จาก `references/admin-template/` ครบ default/hover/focus/disabled/error/loading/responsive และรองรับ keyboard/focus และข้อความไทย/อังกฤษ | AGENTS.md; frontend standard |
| RQ-21 | การเพิ่ม/ถอนต้องไม่เปลี่ยน Paper/Live isolation: catalog policy ใช้ร่วมกัน แต่ data, credentials, order execution และ economic state ยังแยกขาด; automated validation ห้ามส่ง Live order | ADR-004; trading-safety §1 |
| RQ-22 | activation ของคู่ใหม่ต้องมีหลักฐาน correctness/readiness สำหรับ pair นั้น และต้องติดตาม workload/resource ที่จำเป็นเป็น `Pending Full Validation` จนรันครบ; ห้ามใช้ผล BTC/ETH เดิมรับรองคู่ใหม่ | testing §7; F-38 |
| RQ-23 | API/OpenAPI/frontend types ต้องรองรับ catalog ที่เปลี่ยนได้โดยไม่ encode รายการคู่ runtime เป็น enum ที่ต้อง deploy ใหม่ทุกครั้ง และต้องคง validation membership ที่ server | dynamic catalog; generated contract consistency |
| RQ-24 | การเปลี่ยน catalog ต้องไม่เขียนสูตรการเงินด้วย float/Decimal เปล่า และห้ามเปลี่ยน Money/Quantity rounding/range; constraint values จาก venue ต้องผ่านชนิดเดิม | AGENTS.md; F-02; trading-safety §3 |
| RQ-25 | F-37 เสร็จแล้วให้ F-16 ใช้ catalog นี้เป็น dependency สำหรับ supported-pair check แต่ F-16 ยังเริ่มไม่ได้จน `NC-08` ได้รับคำตอบและ requirements/plan/validation ของ F-16 ผ่านการอนุมัติของตัวเอง | roadmap; AGENTS.md SDD |

## พฤติกรรมหลัก

### เพิ่มคู่

1. Admin ส่งคำขอพร้อม pair และ idempotency key
2. ระบบบันทึกคำขอและตรวจ public venue metadata โดยยังไม่เปิดให้สร้างความเสี่ยง
3. ระบบเตรียมข้อมูลและตรวจ readiness ตาม dependencies ที่อนุมัติใน plan
4. เมื่อทุก gate ผ่าน จึง publish catalog revision ใหม่แบบ atomic
5. หากขั้นใดล้มเหลว คู่ยังเปิดไม่ได้และ retry/restart ทำต่อจาก durable state โดยไม่สร้างงานซ้ำ

### ถอนคู่

1. Admin ส่งคำขอพร้อม pair, expected revision และ idempotency key
2. transition ที่ commit ต้องกัน opening admission และ bot work ใหม่ในลำดับเดียวกัน
3. position/order/ledger/history เดิมไม่ถูกแก้หรือลบ และเส้นทางลดความเสี่ยงยังทำงาน
4. UI/API แสดงว่าคู่นี้ห้ามเปิดใหม่ พร้อมสถานะ bot และ dependencies ที่ยังต้องรักษา
5. การ cleanup ข้อมูลหรือ feed ทำได้ภายหลังเฉพาะตาม lifecycle ที่อนุมัติและพิสูจน์ว่าไม่ตัดทางออกของผู้ใช้

## กฎความปลอดภัยที่เกี่ยวข้อง

- `specs/standards/trading-safety.md` §1: Paper/Live ใช้ policy ร่วมแต่แยก execution และข้อมูล
- `specs/standards/trading-safety.md` §3: opening ต้องอยู่ในรายการ; risk-reducing close ไม่ตรวจ membership
- `specs/standards/trading-safety.md` §4/§10: retry idempotent และ uncertain state ต้อง fail closed/recover
- `specs/standards/trading-safety.md` §9: catalog mutation และผลกระทบต่อ bot/order ต้อง audit
- `specs/standards/database.md` §4–6: history immutable, process grants แคบ และ additive migration
- `specs/standards/security.md` §2–4: server authorization, explicit schema และห้าม secret ใน log
- `specs/standards/testing.md` §7: ตรวจตามผลกระทบและไม่ใช้ smoke แทน release validation

## คำตัดสินหลังเสนอ requirements

### NC-F37-01 — Closed 2026-10-21 — ออเดอร์เปิดที่ค้างอยู่ตอนถอนคู่

เมื่อการถอนชนะลำดับ ให้ยกเลิกส่วนที่ยังไม่ fill ของ opening order แบบ atomic และคืน reservation
เฉพาะส่วนที่เหลือ ส่วนที่ fill แล้วคงเป็น position/history เดิมและผู้ใช้ลดหรือปิดเองได้
คำขอยกเลิก/retry ต้อง idempotent และห้ามเกิด fill ใหม่หลัง withdrawal revision commit

### NC-F37-02 — Closed 2026-10-21 — ขอบเขตการหยุดบอทและแจ้งผู้ใช้

F-37 ส่งมอบ durable stop policy/event/reason และ catalog contract ที่ fail closed เท่านั้น
ไม่สร้างระบบบอทหรือ notification ล่วงหน้า F-20/F-21 ต้องตรวจ policy นี้ก่อนเริ่ม/ทำงานต่อ
และ F-26 ต้องส่ง notification จาก durable event โดยไม่สร้าง event ซ้ำ

### NC-F37-03 — Closed 2026-10-21 — การเพิ่มกลับและการเก็บข้อมูลของคู่ที่ถอน

การเพิ่มคู่เดิมกลับต้องตรวจ venue metadata และ bootstrap/readiness ใหม่ทุกครั้ง ห้ามใช้ readiness
ก่อนถอนรับรอง activation ใหม่ เก็บ market/trading history เดิม และหยุด subscription/feed ได้เมื่อ
authoritative dependencies ยืนยันว่าไม่มี position, order, reservation หรือ bot dependency เหลือ
โดยไม่ลบ history; หากพิสูจน์ไม่ได้ให้คงข้อมูล/feed ที่จำเป็นและ fail closed

### NC-F37-04 — Proposed 2026-10-21 — ขอบเขต atomic ของการถอนและ RQ-10

RQ-10 ให้หมายถึงห้ามแก้หรือลบ **economic facts/history ที่ commit แล้ว** เช่น fill, position lot,
ledger, PnL และ order history การถอนยังต้อง transition opening remainder เป็น canceled และคืนเฉพาะ
reservation ที่ผูกกับ remainder นั้นตาม NC-F37-01

จุด atomic ระดับระบบคือ withdrawal revision commit ซึ่งปิด admission/dispatch/matching ใหม่ทันที
หลังจากนั้น worker ทำ cancel + reservation release แบบ atomic ต่อ order ภายใต้ financial lock เดิม
เป็น bounded batches ห้ามใช้ transaction เดียวคร่อมทุกผู้ใช้ และห้ามมี fill ใหม่หลัง revision commit

**บล็อก:** implementation ทุก milestone จนเจ้าของอนุมัติคำชี้แจงนี้พร้อม plan/validation
