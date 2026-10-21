# F-37 — รายการเหรียญที่รองรับและการจัดการ — Plan

สถานะ: **Proposed — รอเจ้าของอนุมัติ**

อ้างอิง: [requirements.md](requirements.md) · [validation.md](validation.md)

## แนวทาง

เปลี่ยนรายการคู่เทรดจากค่าคงที่ในโปรแกรมเป็น catalog ที่มี version และ lifecycle ใน PostgreSQL
โดยยังให้ `core` บริสุทธิ์: ผู้เรียกต้องส่ง catalog snapshot/revision เข้า pure policy แทนการให้
domain อ่านฐานข้อมูลเอง เส้นทางเพิ่มความเสี่ยงต้องอ่านสถานะ authoritative ภายใน transaction
และ fail closed เมื่ออ่านไม่ได้ ส่วนคำสั่งลดความเสี่ยงต้องไม่ถูกปฏิเสธเพราะคู่ถูกถอน

`api` รับ ตรวจสิทธิ์ และบันทึก command เท่านั้นตาม architecture เดิม จากนั้น worker ใน process
`engine` ทำ transition และงานที่แตะ order/reservation ส่วน `market-data` ตรวจ public venue,
bootstrap ข้อมูล และเขียน readiness proof ลง PostgreSQL Service ไม่เรียก HTTP หากัน; Redis เป็น
เพียง wake-up hint และ worker กู้ต่อจาก PostgreSQL ได้เมื่อ Redis หายหรือ process restart

การถอนมีจุด linearization ที่ transaction เปลี่ยนคู่จาก `ACTIVE` เป็น `WITHDRAWING` และเพิ่ม
catalog revision หลัง commit นี้ opening admission, dispatch และ matching ทุกทางต้องปฏิเสธหรือทิ้ง
งานเพิ่มความเสี่ยง และห้ามเกิด fill ใหม่ Worker จึงยกเลิก opening remainder ของแต่ละบัญชีภายใต้
financial lock เดิม พร้อมคืน reservation ใน transaction เดียวกับ order transition โดยไม่ใช้
transaction ใหญ่คร่อมผู้ใช้ทั้งหมด เมื่อไม่มีงานค้างจึงเปลี่ยนเป็น `RETIRED`

## ของเดิมที่จะใช้ซ้ำ

- `backend/src/tiewtrade/core/market_catalog.py` — canonical `MarketPair`/validation เดิม แต่แทน
  global membership ด้วย pure policy ที่รับ snapshot/revision ชัดเจน
- `backend/src/tiewtrade/venues/binance_th/price_feed.py` และ `candle_feed.py` — public venue
  metadata/stream validation โดยรับชุด symbol จาก caller
- `backend/src/tiewtrade/infra/market_data/` และ
  `backend/src/tiewtrade/services/market_data/` — storage, bootstrap, reconnect, candle และ
  latest-price readiness เดิม
- `backend/src/tiewtrade/infra/paper_orders/` และ
  `backend/src/tiewtrade/services/engine/paper_order.py` — order lifecycle, dispatch fence,
  per-owner financial lock, cancellation และ reservation release เดิม
- `backend/src/tiewtrade/infra/audit/` — append-only audit/redaction/transaction pattern เดิม
  โดยขยาย event shape ให้รองรับ platform actor และ system outcome อย่างชัดเจน
- `backend/src/tiewtrade/services/api/authentication.py` และ `routing_policy.py` — session,
  CSRF, rate-limit และ centralized route policy เดิม
- `frontend/src/components/ui/` และ table/form/modal/alert patterns จาก
  `references/admin-template/` — หน้า catalog และ confirmation dialog
- generated OpenAPI → `frontend/src/api-types.ts` และ identity/revision stale-response pattern
  ที่หน้า market data ใช้อยู่

## แบบข้อมูลและ contract

Migration `0039_supported_pair_catalog` เพิ่มโครงสร้างต่อไปนี้โดยไม่ลบ history:

1. `supported_pairs` เก็บ identity canonical ของคู่ที่เคยรู้จัก (`venue`, `market_type`, `base`,
   `quote`) แบบ unique; row ไม่ถูกลบเมื่อ retire เพื่อให้ FK/history เดิมยังอ้างได้
2. `supported_pair_lifecycles` เก็บ current lifecycle, activation generation, monotonic revision,
   safe reason และเวลาที่เปลี่ยน โดย transition ที่อนุญาตคือ
   `PREPARING -> ACTIVE|PREPARATION_FAILED`, `ACTIVE -> WITHDRAWING`,
   `WITHDRAWING -> RETIRED` และ `RETIRED|PREPARATION_FAILED -> PREPARING`; failure ระหว่างถอน
   ต้องคง lifecycle ที่ `WITHDRAWING` เพื่อไม่เปิด opening กลับและบันทึก failure ใน command progress
3. `supported_pair_commands` เก็บ canonical payload hash, idempotency key, expected revision,
   actor และ outcome; unique actor/action/key ทำให้ retry คืนผลเดิมและ payload ต่าง conflict
4. `supported_pair_readiness` เก็บ proof แยก activation generation จาก venue metadata,
   latest price, candle/bootstrap และ dependencies ที่ runtime ใช้จริง; proof รุ่นเก่าห้ามเปิดรุ่นใหม่
5. `supported_pair_events` เป็น durable outbox/event log สำหรับ catalog changed, pair withdrawn,
   bot-stop policy และ notification consumer ในอนาคต พร้อม unique semantic key
6. `platform_memberships` เก็บ `PLATFORM_ADMIN`/`PLATFORM_OWNER` แบบ default deny และ FK ไป
   user เดิม ไม่มี self-service role mutation ใน F-37; initial membership provision ผ่าน operator
   command ที่รับ user UUID ชัดเจน ใช้ privileged DB role แยก และเขียน append-only audit

CHECK allowlist ที่ F-38 ฝัง BTC/ETH ในตาราง market/order/position ถูกแทนด้วย canonical identity FK
ที่รับคู่ซึ่งเคยผ่าน catalog ส่วนการอนุญาตเปิดความเสี่ยงตัดสินจาก lifecycle/revision ใน transaction
ไม่ใช้ FK ไปเฉพาะแถว `ACTIVE` เพราะจะทำลาย history และทางปิด position หลังถอน

Public read contract คืนเฉพาะข้อมูลที่ trader ต้องใช้: pair, market type, `opening_allowed`,
revision และ availability reason ที่ปลอดภัย Admin contract เพิ่ม lifecycle, generation, readiness,
command progress, actor และ timestamps Runtime pair เป็น string/value object ไม่ใช่ OpenAPI enum
จึงเพิ่มคู่ได้โดยไม่ deploy frontend ใหม่

## Authorization และ mutation policy

1. route อ่าน public catalog ต้องมี session ตาม policy API ปัจจุบัน; route admin ใช้ centralized
   dependency ตรวจ membership จาก server ทุกครั้ง ไม่รับ role จาก header/body
2. add/activate เป็นการเพิ่มขอบเขตความเสี่ยง จึงต้องใช้ fresh TOTP ตาม `security.md` §1;
   recovery code ใช้แทนไม่ได้ Removal เป็นการลดความเสี่ยง ไม่เพิ่ม TOTP gate
3. ทุก mutation ต้องผ่าน CSRF, schema/length allowlist, bounded rate limit, idempotency key และ
   expected revision; response ไม่เปิดเผย raw venue payload, token, cookie หรือ DB detail
4. API role มีสิทธิ์ insert command/read projection ที่กำหนดเท่านั้น ไม่มีสิทธิ์ update lifecycle,
   readiness, audit หรือ economic tables โดยตรง Engine/market-data roles ได้ grant เฉพาะส่วน
5. successful/rejected mutation, worker transition และ recovery outcome เขียน audit/outbox ใน
   transaction เดียวกับ state ที่เกี่ยวข้อง โดย platform actor และ system actor แยกกันชัดเจน

## ลำดับดำเนินการ

### M1 — Domain contract, schema และ authorization

1. เพิ่ม pure catalog lifecycle/policy/snapshot ใน `core` พร้อม typed rejection โดยไม่อ่าน I/O,
   เวลา หรือใช้ `Decimal`/`float` คำนวณเงินและปริมาณ
2. เพิ่ม migration `0039`, seed BTC/USDT และ ETH/USDT เป็น `ACTIVE` revision เริ่มต้น และ
   backfill identity FK จากข้อมูลเดิมโดยตรวจ postcondition/digest
3. เพิ่ม process grants/RLS, platform membership repository, operator provisioning command และ
   centralized API authorization
4. ขยาย audit event contract และ redaction ให้รองรับ platform command/system outcome โดยยัง
   append-only และไม่ลด isolation ของ audit ผู้ใช้เดิม

Checkpoint M1: migration/role/audit/domain tests ผ่าน และ binary เดิมถูก capability fence ไม่ให้
เขียน dynamic pair หรือข้าม lifecycle ใหม่

### M2 — Read contract และเปลี่ยน consumers

1. เพิ่ม repository สำหรับ snapshot/current revision และ API read projections
2. เปลี่ยน market-data, paper order admission/dispatch/matching, positions และ API consumers จาก
   `PAIRS` static ไปใช้ explicit snapshot หรือ authoritative transactional check ตามความเสี่ยง
3. opening path ตรวจ `ACTIVE` revision ภายใต้ pair lifecycle lock ร่วมกับ transaction ของ admission;
   dispatch/matching ตรวจซ้ำก่อน economic write เพื่อ fence งานที่ enqueue ก่อนถอน
4. risk-reducing close ตรวจ position/quantity/reduce-only ตามเดิม แต่ไม่ตรวจ active membership
5. เปลี่ยน frontend catalog/chart/realtime selector ให้โหลด server contract, discard response เมื่อ
   session identity หรือ revision stale และไม่ fallback ไป static list

Checkpoint M2: สองคู่เดิมทำงานเหมือนเดิม, database/catalog unavailable ปิด opening แต่ยังรักษา
ทางลดความเสี่ยงตามสัญญา และ OpenAPI/frontend contract ไม่ drift

### M3 — Add/re-add และ readiness

1. API บันทึก idempotent `ADD` command เป็น `PREPARING`; worker ตรวจ Binance TH Spot metadata
   ว่าเป็น USDT pair ที่เทรดได้และแปลง constraint ผ่าน Money/Quantity types เดิม
2. market-data สร้าง subscription/bootstrap สำหรับ activation generation ใหม่และเขียน proof เมื่อ
   latest-price/candle/readiness ที่ consumers ต้องใช้ผ่านครบ
3. engine worker ล็อก pair+command ตรวจ proof ทั้ง generation และ freshness แล้ว commit `ACTIVE`
   กับ revision, audit และ outbox atomically
4. failure/retry/restart เดินต่อจาก durable command; คู่ยัง opening ไม่ได้จน activation commit
5. re-add สร้าง generation ใหม่เสมอและไม่ใช้ proof ก่อน retire

Checkpoint M3: add/re-add, venue failure, stale proof, duplicate/retry และ crash recovery ผ่านโดยไม่มี
duplicate subscription/event/transition

### M4 — Withdrawal และ cleanup

1. API บันทึก `REMOVE` พร้อม expected revision; worker commit `WITHDRAWING` + revision + event ก่อน
2. admission/dispatch/matching และ future bot policy หยุดงานเพิ่มความเสี่ยงจาก revision นี้ทันที
3. scan opening orders แบบ bounded batches; ต่อบัญชีใช้ financial advisory lock เดิมและ order
   lifecycle API เดิมเพื่อ cancel unfilled remainder + release reservation atomically
4. fill/cancel/withdraw race ใช้ lock ordering `pair lifecycle -> owner financial -> order` และ recheck
   state ก่อน economic write; retry เห็น terminal state แล้ว no-op
5. คง position, fills, ledger และ market history; path ปิด/ลด position ยังใช้ได้
6. เปลี่ยน `RETIRED` เมื่อ opening remainder และ reservation ของคู่นั้นเป็นศูนย์และ durable stop event
   ถูกบันทึกแล้ว Feed cleanup ทำภายหลังเมื่อ authoritative position/order/reservation/dependency claims
   เป็นศูนย์; อ่านไม่ได้ให้คง feed และ fail closed

Checkpoint M4: withdrawal races/multi-owner/restart ผ่าน, ไม่มี fill หลัง withdrawal revision commit,
ยอด reservation/balance/position/ledger คง invariant และคู่อื่นไม่ถูก block ทั้งระบบ

### M5 — Admin UI, rollout และ candidate

1. สร้างหน้า admin จาก shared Table/Input/Button/Modal/Alert/Badge patterns และอ้าง source path
   ของ admin template ใน component ที่เพิ่ม ให้ครบ keyboard/focus/loading/error/responsive/i18n
2. แสดง lifecycle/readiness/progress/reason และ confirmation ของ add/remove; duplicate submit ใช้
   idempotency key เดิมจนได้ terminal response
3. rollout แบบ expand/migrate/contract: deploy schema+dual-compatible readers, migrate consumers,
   เปิด admin mutation หลัง capability/readiness fence ผ่าน แล้วจึงลบ static runtime membership
4. อัปเดต OpenAPI/types/runbook/mission/roadmap และบันทึก `Pending Full Validation` จริง
5. รัน candidate gates ครั้งเดียวเมื่อ diff นิ่งตาม validation; หลัง fix รันเฉพาะผลที่ invalidated

Checkpoint M5: requirements/validation traceability ครบ, deep review ไม่มี Critical/High ค้าง และ
candidate gates ที่บังคับผ่านก่อนขอคำสั่ง commit/push/merge

## ไฟล์/พื้นที่ที่คาดว่าจะแก้

| พื้นที่ | การเปลี่ยนแปลง |
|---|---|
| `core/market_catalog.py` และ order policy callers | value object, lifecycle และ explicit snapshot |
| `backend/migrations/versions/0039_*.py` | catalog/command/readiness/event/membership/FK/grants |
| `infra/supported_pairs/` | repositories, command claim, readiness, projections, audit/outbox |
| `services/api/` | read/admin routes, schemas, centralized authorization/routing policy |
| `services/engine/` | durable command worker, withdrawal/order cancellation coordinator |
| `services/market_data/`, `infra/market_data/`, `venues/` | dynamic subscriptions, validation, generation-scoped readiness |
| `infra/paper_orders/`, position callers | transactional membership fences และ risk-reducing exception |
| `frontend/src/` | dynamic catalog client/store, admin page และ existing selectors |
| tests/specs/OpenAPI | safety, migration, contract, UI, rollout และ evidence |

รายการนี้เป็นขอบเขตคาดการณ์ ไม่อนุญาต refactor ส่วนอื่น หาก implementation พบว่าต้องเปลี่ยน
business rule หรือ dependency boundary ต้องหยุดและแก้ spec/ขออนุมัติตาม AGENTS.md

## ผลต่อฐานข้อมูลและ rollback

- migration เป็น additive และ seed สองคู่เดิมโดยไม่เปลี่ยน economic/history row
- FK ใหม่ใช้ `NOT VALID`/backfill/validate ตามขนาดข้อมูล และมี postcondition ว่าทุก pair เดิม map ได้
- lifecycle, command, event และ audit historyห้าม hard delete/update ย้อนหลัง
- downgrade อนุญาตเฉพาะเมื่อ catalog ยังมีเพียง BTC/ETH และไม่มี command/history ของ dynamic pair;
  มิฉะนั้นต้องปฏิเสธพร้อม safe diagnostic เพื่อไม่ทิ้งข้อมูลเงียบ ๆ
- rollback application ใช้ capability fence ปิด mutation ก่อน; binary เก่าห้ามรันเมื่อ revision/schema
  ระบุ dynamic catalog capability ที่มันไม่เข้าใจ

## ความเสี่ยงและการควบคุม

| ความเสี่ยง | การควบคุม |
|---|---|
| opening/fill หลุดหลังถอน | authoritative check ตอน admission และก่อน economic write; pair lock + revision fence |
| cancel ซ้ำหรือคืน reservation ซ้ำ | order transition/idempotency เดิมภายใต้ owner financial lock; terminal no-op |
| transaction ใหญ่ล็อกผู้ใช้ทั้งหมด | commit fence ก่อน แล้ว cancel แบบ bounded per-owner batches |
| readiness เก่าทำให้ re-add เร็วผิด | activation generation ใหม่และ proof ต้องตรง generation/freshness |
| API/UI/cache เห็นรายการไม่ตรงกัน | PostgreSQL source of truth, monotonic revision, stale identity/revision discard |
| venue/Redis/process ล้ม | durable command/proof/outbox; retry-safe recovery; Redis ไม่ใช่ source of truth |
| user ปลอม role หรือ API แตะ state ตรง | centralized server authorization, DB grants/RLS และ negative permission tests |
| static CHECK/FK ทำลาย history | canonical identity FK แยกจาก active policy; retire ไม่ลบ identity/history |
| pair ใหม่เพิ่ม resource โดยไม่พิสูจน์ | activation readiness ต่อ pair และ release workload เป็น Pending จนมีหลักฐาน |
| F-20/F-21/F-26 ยังไม่มี | durable policy/event/reason contract; ไม่สร้าง bot/notification behavior ล่วงหน้า |

## Traceability

| Requirements | Milestone / Validation |
|---|---|
| RQ-1–RQ-6, RQ-17–RQ-18, RQ-23–RQ-24 | M1–M3 / V-01–V-10, V-25 |
| RQ-7–RQ-12, NC-F37-01/03/04 | M4 / V-11–V-18 |
| RQ-13–RQ-16, RQ-19–RQ-21 | M1, M2, M5 / V-19–V-24 |
| RQ-22 | M3, M5 / V-08, V-26–V-27 |
| RQ-25 | M5 / V-28 |
