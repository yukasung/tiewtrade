# F-17 — Manual Paper acceptance: fee quantity and stop readiness

สถานะ: **Approved A — เจ้าของตอบ “อนุมัติ A” วันที่ 2026-11-08; อนุมัติเฉพาะ requirements amendment MR-01–11; plan/validation ได้รับ approve เพิ่มเติมแล้ว 2026-11-08**
วันที่: 2026-11-08 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [validation](validation.md),
[local Paper activation](../2026-10-25-wallet-risk-limits/local-paper-manual-activation-amendment.md)

## หลักฐานและขอบเขต

Owner manual acceptance บน local schema0066 พบ BUY สองรายการจบ EXPIRED หลัง
partial fill; protection ทั้งสองเปลี่ยน WAITING_ENTRY → ARMING → FAILED ด้วย
PROTECTION_SETUP_REJECTED. Net allocation ต่อชุดคือ0.00131868BTC; constraints ที่
เก็บกับ entry กำหนด quantity_step0.00001BTC. เรียก unmet_constraints เดิมแบบ pure
กับ Quantity/Money และ constraints ดังกล่าวได้ QUANTITY_NOT_ON_STEP ทั้งสองชุด.
นี่พิสูจน์ quantity violation ไม่ใช่การกู้ exception ย่อยที่ worker ไม่ได้บันทึกไว้.

พฤติกรรมปัจจุบันมี test ตั้งใจรองรับ:
`backend/tests/core/test_protections.py::test_setup_rejects_unexecutable_net_quantity_without_rounding`.
จึงต้องอนุมัติการเปลี่ยนข้อกำหนดก่อนเปลี่ยน test หรือ source; ไม่ลด safety เพื่อให้ผ่าน.

ปุ่มหยุด: local launcher ไม่ได้กำหนด TIEWTRADE_TRADING_STOP_AUTHORITY_ENABLED.
`services/api/kill_switch_routes.py::_require_authority_enabled` ปฏิเสธด้วย503
ก่อน submit; ไม่มี trading_stop_requests/results ในฐานที่ตรวจ. UI เก็บ request key
เมื่อผลเป็น5xx แล้วแสดงผลไม่แน่นอนตาม `killSwitchJournal.ts`.
ยังไม่ได้พิสูจน์ response ของการคลิกเดิมจาก browser network; ไม่อ้างว่าเป็น transport timeout.

หลัง owner จบการทดลอง ปิด admission → financial → publication และ protection แล้ว.
ไม่มี pending command/protection request หรือ active protection; position และประวัติเดิม
ยังอยู่ ไม่ขาย BTC ไม่ reset wallet และไม่สร้างออเดอร์แทน owner.

## ทางเลือกและคำตัดสินที่ต้องการ

- **A (แนะนำ):** อนุญาตให้ protection ใช้เฉพาะจำนวนที่ขายได้จริงตาม step โดยปัดลง
  ด้วย primitive เดิม และแสดงส่วนที่ไม่ได้ป้องกันอย่างชัดเจน; แก้ local stop readiness
  ก่อนการเปิด Paper รอบต่อไป. ต้องทำ plan/validation ให้เจ้าของอนุมัติอีกด่านก่อน code.
- **B:** คงกฎปฏิเสธทั้งชุดเมื่อ net quantity ไม่ตรง step; ปรับคำอธิบาย failure และ
  local stop readiness เท่านั้น. ไม่ถือว่าปัญหา usability ของ bracket fee ถูกแก้แล้ว.

## Proposed requirements amendment — NC-F17-MANUAL-01

| ID | พฤติกรรมที่เสนอเมื่อเลือก A |
|---|---|
| MR-01 | ขอบเขต runtime คือ Paper local/manual acceptance; shared domain ยังคง deterministic และ Paper/Live fixture parity. ไม่เปิด Live, bot หรือ public release |
| MR-02 | ใช้ Money/Quantity และ `core/money/order_arithmetic.py::align_quantity` เดิมเพื่อหาจำนวนปิดที่ไม่เกิน net allocation และตรง step. ห้ามปัดขึ้น ซื้อเพิ่ม หรือเปลี่ยน fee/ledger/position facts |
| MR-03 | จำนวนที่ป้องกัน/ขายได้และส่วนที่ยังไม่ป้องกันต้องแยกแสดงอย่างตรงจริง. ห้าม ARMED/closed ทำให้ผู้ใช้เข้าใจว่าป้องกันหรือขายครบเมื่อยังมีเศษ. ส่วนเศษยังเป็นเหรียญของ owner และไม่มี automatic sell |
| MR-04 | จำนวนที่ปัดลงต้องผ่าน minimum/maximum quantity, notional และ capability/filter เดิมครบ. ถ้าเป็นศูนย์หรือต่ำกว่า minimum ให้แสดงว่าไม่สามารถป้องกันอัตโนมัติได้ ไม่สร้าง zero/invalid exit และไม่แอบรับรอง READY |
| MR-05 | คง non-overlap, held/reserved conservation, exact owner/mode/episode isolation และหนึ่ง exit intent ต่อ trigger. TP/SL ไม่จองซ้ำ; ไม่ให้เศษถูกนับสองกลุ่มหรือถูกขายซ้ำ |
| MR-06 | partial/late entry และ metadata/step change ต้องประเมินจำนวน executable จาก authoritative facts ณ transaction ที่เกี่ยวข้อง; ใช้ constraints เดียวกันระหว่าง setup กับ exit. ไม่เปลี่ยน unknown reconciliation, revision checks หรือกฎ terminal exit/residual ที่ไม่สร้าง MARKET ใหม่วนเอง |
| MR-07 | retry/restart, dropped ACK, duplicate event, manual sale/cancel/replace และ correction ต้องไม่เพิ่ม economic effects หรือเปลี่ยนประวัติเดิม. กลุ่ม FAILED ในฐาน owner ไม่ถูก re-arm/แก้ allocation อัตโนมัติจาก deployment |
| MR-08 | ก่อนเปิด local Paper รอบต่อไป ต้องตรวจ schema/compatible financial writers และ stop-request worker พร้อม แล้วกำหนด stop authority flag ตาม contract เดิม. ห้ามใช้ allow-all, ข้าม auth/CSRF หรือให้ credential ของ operator แก่ API/worker |
| MR-09 | flag เปิด stop authority ไม่ใช่การเปิด Live executor. ห้าม retry คำขอหยุดจาก browser journal อัตโนมัติเพียงเพราะ restart/deploy; owner ยืนยันคำขอเดิมผ่าน UI ตาม idempotency เดิม |
| MR-10 | คงข้อความผลไม่แน่นอนสำหรับ failure ที่ยังพิสูจน์ผลไม่ได้. ไม่ล้าง request key ของ5xxทั้งกลุ่มหรือสรุปว่าหยุดสำเร็จจาก HTTP acknowledgement; ต้องตรวจ durable receipt และ completion จริง |
| MR-11 | คง SLA, risk gates, load profiles และ Release dependencies เดิม; ไม่ใช้ manual acceptance แทน100-account/4h/bot/notification/Live validation และไม่ทำให้ F-17 Completed |

MR-02–06 ขยายการตีความ NC-F17-04 สำหรับ net quantity ที่ไม่ตรง step:
ป้องกันส่วนที่ executable ได้โดยแสดงเศษที่ยังไม่ป้องกัน แทนปฏิเสธทั้งชุด.
ข้อกำหนดนี้ได้รับอนุมัติ A แล้ว; บันทึกการอ้างอิง amendment ใน requirements.md.

## ของเดิมที่ควรใช้ซ้ำเมื่อจัดทำ plan

- `core/protections.py::{validate_setup,evaluate_trigger}` และ lifecycle/exit intent เดิม;
  `infra/protections/{worker,storage,codec}.py` และ `services/api/protection_routes.py`
  สำหรับ owner transaction/replay/truth.
- `core/money/order_arithmetic.py::align_quantity`, `core/orders.py::OrderConstraints.check`
  และ financial primitives เดิม; ไม่เขียนสูตร Decimal/float หรือ rounding ใหม่.
- `services/engine/{paper_order_main,risk_limit_main}.py` และ
  `services/api/kill_switch_routes.py` สำหรับ compatible writers และ stop processing.
- `frontend/src/KillSwitchControls.tsx`, `frontend/src/killSwitchJournal.ts`;
  ใช้ UI กลางและ admin template เดิม.
- `compose.yaml`, `compose.chart.dev.yaml` และ approved local activation procedure;
  ไม่เพิ่ม infrastructure หรือ persistent in-memory business/session state.

## ขอบเขต validation ที่ต้องจัดทำหลัง requirements อนุมัติ

Feature: exact net-fee/off-step fixture จากรอบนี้; aligned amount; zero/minimum/notional;
partial/late fill; metadata change; displayed executable/unprotected residual; real-DB
rollback/races/replay/ACK-loss/duplicate-exit/oversell; Paper/Live domain parity fixtures.
Stop: default-off rejection, compatible opt-in durable STOP/retry/completion, restart,
auth/CSRF/owner isolation และ UI unknown-result/request-key behavior.
ใช้ targeted tests เดิมก่อน เพิ่มเฉพาะช่องว่าง พร้อม affected lint/types/contracts.

หลัง code ครบต้องแจ้ง Ready for Code Review และรอ review code ตาม AGENTS.md.
หลัง review/fix ต้องรอคำสั่ง refactor; จากนั้น affected validation และ required CI
ตาม candidate ล่าสุดก่อน merge. ไม่รัน workload ยาวซ้ำโดยไม่มีผลกระทบที่ระบุได้.
Manual Paper acceptance รอบทดแทนต้องระบุ profile/cleanup/activation scope ใน plan
และได้รับอนุมัติ; ยังไม่เริ่มรอบใหม่จากเอกสารนี้. เก็บผล Failed รอบเดิมตามจริง.

## จุดหยุด

Owner เลือก A และอนุมัติ requirements amendment แล้ว. ขั้นถัดไปคืออนุมัติ
[implementation plan](manual-acceptance-fix-plan.md) และ
[validation](manual-acceptance-fix-validation.md) อีกด่านก่อนแก้ source/config.
ไม่มี commit/push/PR, runtime flags, order, wallet reset หรือ production activation
ที่ได้รับอนุญาตจากการจัดทำข้อเสนอนี้.


Owner approved the revised plan/validation on2026-11-08. Implementation/checkpoint:
[evidence](evidence/manual-acceptance-fix/implementation-checkpoint.md). Local checks
do not authorize Git publication, deployment or release completion.
