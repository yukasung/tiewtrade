# F-37 — รายการคู่เทรดที่รองรับและการจัดการ — Plan

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-24; amended 2026-10-25 ให้ Live cancellation/reconciliation ของ V-10 รอ F-22/F-23 โดย Paper/catalog safety ยังเป็น candidate gate**

อ้างอิง requirements: **Approved 2026-10-24**

## แนวทาง

เปลี่ยน allowlist คงที่เป็น catalog แบบ event-sourced ใน PostgreSQL โดยทุกการเปลี่ยนได้
revision ที่เพิ่มขึ้นและประวัติแก้ย้อนหลังไม่ได้ Redis ใช้เป็นเพียงสัญญาณให้ process โหลด
revision ใหม่; ถ้า Redis หาย ทุก process ต้องสร้าง state จาก PostgreSQL ได้

`core` ยังคงบริสุทธิ์ ไม่อ่านฐานข้อมูลหรือนาฬิกา ผู้เรียกส่ง immutable
`CatalogSnapshot(revision, active_pairs)` เข้า admission function ทุกครั้ง การ submit ที่ API
ตรวจ catalog เพื่อปฏิเสธเร็ว แต่ engine ต้องอ่าน authoritative revision และตรวจซ้ำใน transaction
ก่อน admission/dispatch เสมอ จึงปิด race ระหว่าง “ผ่านตอนเข้าคิว” กับ “Admin ถอนก่อนส่ง”

PostgreSQL มี current fence หนึ่งแถวต่อ pair สำหรับ serialization และมี event history แยกแบบ
append-only; ทั้งสองเป็น catalog ชุดเดียวกันและเปลี่ยนพร้อมกันใน stored function เท่านั้น
order transaction ต้องถือ row lock ของ pair ตั้งแต่ authoritative check ผ่านจน commit admission/fill
ส่วน removal ต้องรอ lock เดียวกันก่อน commit `REMOVED` ดังนั้น Paper admission/fill ที่ commit
หลัง removal commit เกิดไม่ได้ สำหรับ Live order ที่ตลาดรับไปก่อน removal จะใช้ cancellation และ
reconciliation ตามหัวข้อผลของการถอน เพราะฐานข้อมูลย้อนการรับคำสั่งของตลาดไม่ได้

สถานะของคำขอเพิ่มคือ `REQUESTED → PREPARING → ACTIVE` หรือ `FAILED`; การถอนสร้าง
`REMOVED` revision ใน transaction เดียวกับ outbox และ audit ทำให้เปิดความเสี่ยงใหม่ไม่ได้
ทันที ส่วนการหยุดบอท/ทิ้ง queued opening/cancel open entry orders เป็นผลข้างเคียง durable
ที่รายงาน `PENDING / COMPLETE / PARTIAL` แยกจากสถานะ catalog ห้ามแสดง cleanup ครบเมื่อ
ยกเลิกบางใบไม่สำเร็จ

คู่ `REMOVED` ที่ยังมี position หรือ order อยู่จะอยู่ใน maintenance set: ไม่มี public
chart/backfill demand ใหม่ แต่ market-data คงราคาและ constraints ที่สดพอสำหรับการดูแลและ
ลดความเสี่ยง เมื่อไม่มี exposure/order แล้ว engine เขียน durable proof ให้ worker หยุด feed ได้
ประวัติเดิมคงตาม retention เดิม ไม่ลบเพราะถอนคู่

F-20/F-26 ยังไม่มี implementation งานนี้จึงสร้าง typed durable effect/event และ contract tests
ไว้ก่อน หลัง merge ให้สถานะ F-37 เป็น **Development Complete — Pending F-20/F-26
integration**; จะเป็น Completed เมื่อ bot consumer หยุดจริงและ in-app notification แสดงจริง
ตาม V-18 โดย Email/Telegram/LINE ไม่บล็อก F-37

## การตัดสินใจด้านสถาปัตยกรรมที่ขออนุมัติพร้อมแผน

เมื่อแผนนี้ได้รับอนุมัติ ให้สร้าง `specs/decisions/005-dynamic-supported-symbol-catalog.md`
บันทึก catalog projection/event source of truth, shared pair fence, platform audit ownership,
bootstrap role และ rolling protocol gate ก่อนแก้ runtime/import contracts ตาม
`standards/architecture.md` §6

### 1. Bootstrap Platform Owner

เพิ่มบทบาทฐานข้อมูล `tiewtrade_platform_bootstrap` ซึ่ง:

- ไม่เป็น superuser, owner หรือ `BYPASSRLS` และไม่มีสิทธิ์ตารางโดยตรง
- เรียกได้เพียงฟังก์ชัน bootstrap แบบ `SECURITY DEFINER` ที่รับ UUID ของผู้ใช้เดิม
- ฟังก์ชันตรวจว่าผู้ใช้นั้นเปิด TOTP แล้ว, ยังไม่มี Platform Owner และ transaction นี้สร้าง
  owner คนแรกพร้อม audit ได้ครบ มิฉะนั้น rollback
- หลังมี owner คนแรกแล้วเรียกซ้ำไม่ได้ตลอดไป แม้ credential เดิมยังอยู่
- credential ไม่ถูก mount เข้า API/engine/worker; ใช้กับ CLI offline ตอน deploy เท่านั้น

เพิ่มคำสั่ง `platform-owner-bootstrap --user-id <uuid>` ที่ต้องพิมพ์ UUID ซ้ำเพื่อยืนยันใน
terminal interactive และไม่รับ email เพื่อไม่เกิด normalization/บัญชีผิด CLI ไม่ log URL,
credential หรือ TOTP secret การเพิ่ม Admin/Owner คนต่อไปอยู่นอก F-37 และเป็น F-29

การเพิ่ม role นี้ต้องแก้ `standards/database.md` §5 และ provisioning/config ที่เกี่ยวข้องใน diff
เดียวกัน เพราะเป็นบทบาท deployment-only ใหม่ ไม่ใช้ migrator ทำงาน runtime และไม่เพิ่มสิทธิ์
ให้ web process

### 2. Catalog state และ revision

- ตาราง current command/idempotency และตาราง event/history แยกกัน; history/audit append-only
- current pair fence เป็น projection ที่แก้ได้เฉพาะ stored function; event history เป็นหลักฐาน
  append-only และ constraint/trigger ตรวจว่า revision/status ของ projection ตรง event ล่าสุดเสมอ
- pair เก็บ `base`/`quote` แยกและบังคับ `quote = USDT`; normalization ใช้กฎ Money/Quantity เดิม
- revision จัดลำดับภายใต้ database lock หนึ่งจุด; optimistic expected revision กัน lost update
- current view อ่านจาก projection ที่ตรวจเทียบ event ล่าสุด; ห้ามมี static Python/TypeScript enum
  เป็นความจริงอีกชุด
- constraints snapshot เก็บ version/source time แบบ immutable และใช้ชุดเดียวกับ order admission
- `REQUESTED/PREPARING` ไม่อยู่ใน active set และสั่งออเดอร์เพิ่มความเสี่ยงไม่ได้
- activation function ตรวจ proof จาก DB ว่า venue validation, fresh constraints, realtime price และ
  candle/indicator runtime series ทั้ง 8 timeframe พร้อมก่อนเขียน `ACTIVE`

### 2.1 Shared fence และ lock order

- Admin mutation ทุกคู่: acquire global catalog revision advisory lock → `SELECT ... FOR UPDATE`
  pair fence → เขียน event/projection/outbox/audit → commit
- Paper submit เป็น fast rejection เท่านั้น; engine เป็น authoritative writer: ถือ wallet advisory lock
  เดิมก่อน แล้ว `SELECT ... FOR KEY SHARE` pair fence ก่อนอ่าน market input/admit/match และถือถึง
  commit ทุกครั้ง รวมการ advance active LIMIT order ไม่ใช่เฉพาะคำสั่ง NEW
- removal transaction ไม่จับ wallet/user lock และ effect consumer ไม่ถือ pair fence ขณะวนจับ
  wallet locks จึงไม่มีวงจร pair→wallet สวนกับ wallet→pair
- activation/removal ของหลายคู่ใช้ global revision lockก่อน pair fence เสมอ ห้ามจับสอง pair fences
  พร้อมกัน; effect consumer ทำทีละ owner ตาม single-writer เดิม
- ถ้า fence หาย, status/revision อ่านไม่ได้ หรือ protocol mismatch ให้ opening path fail closed;
  cancel/reduce-risk ใช้กฎเดิมและไม่ต้อง ACTIVE แต่ยังต้องอ่าน position/constraints ที่เชื่อถือได้

### 3. สิทธิ์และ mutation

- ผู้ใช้ทุกคนอ่าน active catalog ได้; เฉพาะ Admin/Owner อ่านหน้าจัดการและ impact aggregates
- mutation ผ่าน stored function ที่ตรวจ membership ซ้ำในฐานข้อมูล ไม่เชื่อ role จาก frontend
- route mutation อยู่ใน routing policy แบบ `reverify=True` และไม่รับ recovery grant
- API ตรวจ TOTP ผ่าน middleware เดิม, ต้องรับ `Idempotency-Key`, `expected_revision` และ
  `reason_code` จาก allowlist ที่ประกาศใน typed contract ห้ามรับเหตุผลข้อความอิสระลง history/audit
  จากนั้นเรียก function ซึ่งเขียน command/event/outbox/audit ใน transaction เดียว
- impact preview คืนเฉพาะจำนวนรวมของ bot/order/position และเวลา snapshot ไม่เปิดข้อมูลผู้ใช้อื่น
- ไม่มี endpoint ให้ Admin ดู secret, user trade detail, สั่งออเดอร์ หรือปิด position

### 3.1 Platform audit ownership

- catalog command ที่คนขอ: `owner_user_id` และ `actor_id` เป็น UUID ของ Admin/Owner ผู้ขอ,
  `actor_kind=PLATFORM`; เขียนด้วย user-scoped session ใน transaction ของ mutation
- reason เก็บเป็น typed code เท่านั้นและ UI แปล label จาก i18n; code ที่ไม่รู้จักถูกปฏิเสธก่อน
  mutation เพื่อไม่ให้ audit แบบลบไม่ได้กลายเป็นที่เก็บ secret/PII หรือข้อความอิสระ
- transition อัตโนมัติ เช่น PREPARING→ACTIVE/FAILED: audit ยังคง owned โดยผู้ขอเดิม แต่
  `actor_kind=SYSTEM`, `actor_id=NULL`; typed details มี command/pair/revision โดยไม่เก็บข้อมูลเสรี
- bootstrap owner คนแรก: audit owned โดย owner คนใหม่, `actor_kind=SYSTEM`; ฟังก์ชัน bootstrap
  เขียน membership และ audit ใน transaction เดียว
- เพิ่ม catalog coordinator ใน `services.engine` ไม่ให้ market-data แตะ audit coordinator อ่าน
  public readiness proof ผ่าน infra แล้วเปิด user-scoped engine session ของ requester เพื่อเรียก
  transition function; market-data/indicator เขียนได้เฉพาะ proof ตาม privilege เดิม
- failure ก่อนสร้าง command เช่น schema/TOTP/authorization rejection ไม่สร้าง catalog mutation;
  failure หลังรับ command แล้วต้องสร้าง `FAILED` event และ audit ใน transaction เดียวกัน
  ห้ามเขียน failure audit แยกแล้วปล่อย catalog เปลี่ยนโดยไม่มีคู่บันทึก

### 4. ผลของการถอน

1. lock pair/revision และเขียน `REMOVED` revision ก่อน
2. insert durable effect/outbox สำหรับ engine และ notification ใน transaction เดียวกัน
3. engine ตรวจ revision ตอน claim และก่อน commit admission; queued opening ถูก terminal reject
   ด้วยรหัส catalog removal แต่ cancel/reduce-risk ยังเดินต่อ
4. consumer ใน engine ยกเลิก Paper open entry orders; F-37 เก็บ durable effect contract และแสดง
   `PARTIAL` ตามจริง ส่วนการเชื่อม Live adapter เพื่อแยกผลสำเร็จ/ล้มเหลวและคง TP/SL หรือ
   reduce-risk orders รอ implementation ของ F-22/F-23 ตาม amendment ที่เจ้าของอนุมัติ 2026-10-25
5. bot-stop และ notification ใช้ event เดียวกันเมื่อ F-20/F-26 มา ไม่สร้างกฎซ้ำ
6. UI แสดง catalog removed ทันทีและแสดง cleanup pending/partial แยกกัน

ห้ามผูกการถอนกับการลบ market-data หรือ trading history และห้ามรอการยกเลิกจาก venue ก่อน
ปิด active catalog เพราะช่วงรอนั้นยังเปิดความเสี่ยงใหม่ได้

Paper order ที่ยังไม่ fill ต้องไม่ fill หลัง `REMOVED` commit เพราะ matching ทุกครั้งถือ shared fence
ส่วน Live order ที่ Binance รับก่อน removal อาจ fill ก่อนหรือระหว่าง cancel ได้ ผลดังกล่าวเป็นความจริง
จากตลาดที่ต้อง reconcile เป็น balance/position/order ตาม F-22/F-23 ห้ามทิ้ง fill หรืออ้างว่า removal
ย้อนมันได้ cleanup จึงคง `PARTIAL`/unresolved จนทราบ terminal outcome

### 5. Rolling deployment และ rollback

- migration 0040 เริ่มด้วย catalog mutation disabled และ seed BTC/ETH ให้ runtime เดิมอ่านได้
- deploy readers/writers รุ่นใหม่ทุก process ก่อน โดยแต่ละ process เขียน heartbeat ที่มี
  `catalog_protocol_version`, deployment generation และ lease expiry
- mutation endpoint ปฏิเสธจน owner รัน enable command หลัง drain process รุ่นเก่า, รอ lease เก่า
  หมด และฐานข้อมูลเห็น heartbeat รุ่นใหม่ครบ API, engine, market-data และ indicator-builder
- enable function บันทึก generation/revision/audit และ stored mutation functions ตรวจ protocol gate
  ซ้ำทุกครั้ง ไม่เชื่อเพียง UI หรือ environment flag
- rollback ก่อน enable ทำได้โดยใช้ static compatibility reader; หลัง enable ห้ามย้อน binary ที่ไม่
  รองรับ protocol ต้อง roll forward หรือ disable mutations, drain effects แล้วใช้ migration guard
- validation ต้องจำลอง missing/old heartbeat, old lease, mixed generation และ worker restart;
  ไม่มีช่วงที่ API รุ่นใหม่เปลี่ยน catalog ขณะ writer รุ่นเก่ายังมี lease

## ของเดิมที่จะใช้ซ้ำ

| ของเดิม | ใช้อย่างไร |
|---|---|
| `backend/src/tiewtrade/venues/symbols.py` | `Symbol` และ normalization base/quote; ไม่สร้าง parser กฎใหม่ |
| `backend/src/tiewtrade/venues/binance_th/{order_book,order_book_mapping,constraints}.py` | ใช้ `capability()`/`capability_from_pair()` ตรวจ exact symbol, `TRADING`, order types และ filters จาก `/exchangeInfo`; ใช้ cache/rate limit เดิม แต่ห้ามใช้ `constraints_from_pair()` อย่างเดียวเป็นหลักฐานสถานะตลาด |
| `backend/src/tiewtrade/core/orders.py`, `paper_matching.py` | admission/error contracts เดิม; เปลี่ยนจาก static `PAIRS` เป็น snapshot ที่ผู้เรียกส่งเข้า |
| `backend/src/tiewtrade/infra/paper_orders/{dispatch,worker,storage}.py` | idempotent command, owner serialization, dispatch lease และ terminal result เดิม |
| `backend/src/tiewtrade/infra/audit/{events,writer}.py` | typed audit detail และ transaction atomicity; เพิ่ม action/detail แบบ allowlist |
| `backend/src/tiewtrade/services/api/{authentication,routing_policy}.py` | session, CSRF, TOTP reverify, route coverage และ failure contract เดิม |
| `backend/src/tiewtrade/infra/market_data/` | readiness/checkpoint/feed proof และ constraints snapshot ที่มีอยู่; เปลี่ยน source ของ pair จาก constant เป็น DB snapshot |
| `frontend/src/AccountSession.tsx`, `auth.ts`, `api.ts` | identity-scoped TanStack Query, CSRF/TOTP header และ error handling เดิม |
| `frontend/src/components/ui/{Table,Modal,Button,Input,Label,Select}.tsx` | shared controls เดิม; เพิ่ม Badge/Alert จาก template ถ้ายังไม่มี |
| `references/admin-template/src/components/tables/DataTables/TableTwo/DataTableTwo.tsx` | โครงตาราง catalog และ responsive pagination |
| `references/admin-template/src/components/integration/{AddIntegrationModal,IntegrationDeleteModal}.tsx` | modal เพิ่ม/ถอนและ destructive confirmation |
| `references/admin-template/src/components/ui/{badge/Badge,alert/Alert}.tsx` | status badge และ partial/error alert ผ่าน shared component |

## สิ่งที่จะแก้

| กลุ่มไฟล์ | เปลี่ยนอะไร |
|---|---|
| `specs/decisions/005-dynamic-supported-symbol-catalog.md` | ADR ของ source of truth, fence/lock order, audit ownership, bootstrap และ rollout gate |
| `specs/standards/database.md`, config/provisioning/Compose | บันทึกและสร้าง bootstrap role แบบ deployment-only; ไม่ mount ให้ runtime |
| `backend/migrations/versions/0040_supported_symbol_catalog.py` | additive registry/fence/events/views/functions/grants/triggers, seed BTC/ETH, membership/bootstrap, revision/idempotency/effect/readiness/constraints/protocol heartbeats และ audit shapes; downgrade มี guard เมื่อมี post-seed events |
| `backend/src/tiewtrade/core/market_catalog.py` | แทน Literal/static pairs ด้วย immutable snapshot/status/value contracts ที่ไม่พึ่ง infra |
| `backend/src/tiewtrade/core/paper_matching.py` และ callers | รับ snapshot/revision จาก caller; ลดความเสี่ยงไม่อิง active set เปิดความเสี่ยงต้อง active |
| `backend/src/tiewtrade/infra/platform/` (ใหม่) | storage ของ membership, catalog commands/snapshots/history/effects/impact aggregates และ bootstrap client |
| `backend/src/tiewtrade/infra/audit/` | catalog/membership typed events, validators และ export |
| `backend/src/tiewtrade/infra/paper_orders/`, `infra/positions/` | authoritative recheck, terminal rejection/cancel effect และเลิกปฏิเสธ historical pair เพราะ inactive |
| `backend/src/tiewtrade/infra/market_data/`, `infra/indicators/` | อ่าน active/preparing/maintenance snapshot และผูก proof กับ catalog revision |
| `backend/src/tiewtrade/services/api/catalog_*.py`, `app.py`, `routing_policy.py`, `authentication.py` | read/admin/mutation/preview endpoints, role ใน `/auth/me`, TOTP rule และ router |
| `backend/src/tiewtrade/services/engine/` | catalog coordinator, consume removal effects, authoritative pair fence, reject queued openings, cancel Paper entry orders และเขียน exposure/effect proof |
| `backend/src/tiewtrade/services/market_data/`, `services/indicator_builder/` | hot-reload revision, prepare new pair, retire public demand, keep maintenance feed และเรียก conditional activation |
| `backend/src/tiewtrade/venues/binance_th/{price_feed,candle_feed}.py` | เอา static catalog ออกจาก adapter; รับ bounded unique symbols จาก service โดยไม่รู้ business allowlist |
| `backend/src/tiewtrade/services/platform_bootstrap.py`, `backend/pyproject.toml` | offline CLI สำหรับ owner คนแรกเท่านั้น |
| `frontend/src/{marketCatalog,auth,api-types,accountNavigation,accountMessages}.ts` | server-derived catalog/role/contracts/navigation/i18n; ลบ static pair enum/list |
| `frontend/src/SupportedSymbolPanel.tsx`, stylesheet และ `AccountPages.tsx` | Admin-only table, preview, add/remove modal, TOTP/reason, revision conflict และ cleanup states |
| `frontend/src/components/ui/{Badge,Alert}.tsx` (ถ้าจำเป็น) | shared component ที่ปรับจาก template ไม่เขียน style เฉพาะหน้า |
| tests backend/frontend/e2e และ generated OpenAPI | เพิ่มหลักฐานตาม validation โดยใช้ FakeVenue/fixtures ไม่ส่ง Live order |

ชื่อไฟล์ย่อยอาจปรับให้ตรงโครงสร้างจริงระหว่าง implementation ได้ แต่ห้ามเปลี่ยน boundary,
state machine, safety semantics หรือแยก source of truth จากแผนนี้โดยไม่ขออนุมัติ

## ผลต่อฐานข้อมูล

- migration เป็น additive ก่อน: สร้าง role/function/table/view และ seed revision แรกโดยไม่ลบ
  static constants ใน deployment เดียวกัน จึงรองรับ expand → migrate callers → contract
- seed ต้องให้ BTC/USDT และ ETH/USDT active โดยอ้าง proof/config เดิม และไม่แตะ candle,
  indicator, order, balance หรือ position rows
- migration ต้องแทน CHECK `base IN ('BTC','ETH')` ของ `market_candles`,
  `market_candle_demand`, `market_latest_prices`, `market_candle_preview`,
  `indicator_build_jobs`, `indicator_generations` และ pair constraints ที่เพิ่มหลัง 0030 ด้วย FK
  ไป immutable symbol registry; removal ไม่ลบ registry จึงอ่าน historical pair ได้
- `seed_indicator_build_jobs()`, `claim_indicator_build_job()`,
  `transition_indicator_rollout()` และ SQL/function อื่นที่ฝัง 2 คู่/16 series ต้อง join catalog
  preparation/maintenance set และนับ readiness ต่อ pair × 8 timeframe แทนค่าคงที่
- เพิ่ม migration/source test ที่สำรวจ `pg_constraint`, `pg_get_functiondef` และ runtime source
  เพื่อจับ allowlist/count/scheduler ordering ที่ยังฝัง BTC/ETH; คู่ที่สามต้องเดินครบ ingestion,
  indicator preparation, activation, removal และ re-add โดยไม่แก้ migration 0030 ย้อนหลัง
- append-only ใช้ trigger + revoke เหมือน audit; current state สร้างจาก latest event/view
- grants แคบตาม process: API อ่าน catalog/own membership และ execute admin function,
  engine อ่าน catalog/effects, market-data/indicator อ่าน preparation set และเขียนเฉพาะ proof,
  bootstrap execute ฟังก์ชันครั้งแรกเท่านั้น
- downgrade ทำได้เมื่อมีเพียง seed และไม่มี role/member/catalog mutation ที่ runtime สร้าง;
  ถ้ามีข้อมูลใหม่ต้องปฏิเสธพร้อมข้อความ ไม่ rewrite หรือลบ history เพื่อย้อน schema
- migration up/down/up, privileges, FORCE RLS/aggregate non-disclosure และ old/new rolling window
  ต้องผ่านก่อนตัด static catalog ออกจาก runtime

## ความเสี่ยง

| ความเสี่ยง | การป้องกัน/หลักฐาน |
|---|---|
| service ใช้ revision เก่าแล้วเปิด order | recheck ใน engine transaction, fail closed เมื่ออ่านไม่ได้, race integration V-08 |
| ถอนแล้วผู้ใช้ปิดไม้ไม่ได้ | แยก risk-reducing จาก active catalog และทดสอบ exact/over-size V-09 |
| open order fill หลังถอน | Paper shared fence กัน fill หลัง commit; F-37 เก็บ durable unresolved/partial contract ส่วน Live reconcile fill ที่ตลาดรับก่อน cancel รอ F-22/F-23 ตาม amendment ของ V-10 |
| Admin privilege escalation | DB-enforced membership, TOTP route, offline one-shot bootstrap, privilege matrix V-03/V-04 |
| readiness กล่าวอ้างเกินจริง | PREPARING แยก ACTIVE และ activation function ตรวจ DB proof ทุก dependency V-06 |
| worker เก่าสร้าง pair กลับ | monotonic revision, DB snapshot on restart, stale-writer guard V-12 |
| ลบ/ปฏิเสธ historical pair | decouple historical integrity from active catalog และ migration regression V-13 |
| จำนวนคู่เพิ่มแล้ว resource โตไร้ขอบ | bounded batches/queues/backpressure; candidate multi-pair correctness และ release capacity V-19 |
| bot/notification ยังไม่มี | typed durable contract + Pending integration ชัดเจน ห้ามปิด Completed ก่อน V-18 |
| UI เปิดข้อมูลผู้ใช้อื่น | aggregate-only function, timestamp/stale state และ authorization tests V-15 |
| rolling deployment มี worker รุ่นเก่า | mutation protocol gate, drained leases และ mixed-version tests V-12 |

## Checkpoints การตรวจ

### M1 — Schema, role และ core contract

- ADR-005 บันทึกตาม architectural decisions ที่อนุมัติและ import contracts ยังเขียว
- migration/privilege/bootstrap/audit append-only ผ่านบน PostgreSQL จริง
- SQL constraints/functions เดิมไม่ฝัง 2 คู่ และ dynamic third-pair migration regression ผ่าน
- immutable snapshot และ pure core tests ผ่าน; static catalog ยังเป็น compatibility reader
- หยุดทันทีถ้า role ใหม่ต้องได้สิทธิ์กว้างกว่าที่แผนอนุมัติ

### M2 — API mutation และ readiness

- add/remove/idempotency/concurrency/TOTP/impact preview ผ่านกับ FakeVenue
- market-data/indicator hot reload และ conditional activation ผ่านครบ 8 timeframe
- OpenAPI/generated types ใช้ string + server catalog ไม่สร้าง dynamic enum ปลอม

### M3 — Order/removal safety

- submit/claim/dispatch race, queued rejection, Paper open-order cancellation,
  active-order matching race, reduce-risk exact/over-size และ restart recoveryผ่านบน PostgreSQL/Redis แยก
- ไม่รอ workload ยาวเพื่อพิสูจน์ correctness/trading safety ชุดนี้

### M4 — Frontend/E2E

- Admin/Owner เห็นหน้า, Trader ไม่เห็นและเรียก API ไม่ได้, TOTP/reason/modal/revision conflict,
  responsive/accessibility/loading/error/stale/partial states ผ่าน
- ตรวจ component paths และ computed states ที่ยืมจาก admin template

### M5 — Candidate ก่อน merge

- review diff/dependencies เน้น Critical/High และ trading safety แล้วแก้ findings
- backend full regression, Ruff check/format, strict mypy, import-linter, migrations,
  frontend full tests/lint/type/build, OpenAPI contract, E2E และ required CI ผ่านบน source เดียวกัน
- บันทึก F-20/F-26 เป็น Pending integration; ห้ามเรียก F-37 Completed
- เมื่อ V-01–V-09, V-10 เฉพาะ Paper/catalog contract, V-11–V-17 และ V-20 ผ่านและ candidate
  merge แล้ว ให้บันทึก milestone
  **Catalog/Order Safety Ready** ซึ่งปลด dependency ของ F-16; V-18/V-19 ยังไม่ผ่านและ F-37
  ยังเป็น Development Complete

### Release checkpoint / ชุดที่ 9

- ก่อนรัน V-19 ต้องมี release-validation plan แยกที่เจ้าของอนุมัติ ระบุ digest และจำนวนคู่ USDT
  ใน fixture, add/remove churn rate, PREPARING/ACTIVE/MAINTENANCE mix, duration, restart schedule,
  replicas, latency/freshness/recovery/memory/queue thresholds และ mapping ไปเกณฑ์ F-11/F-12 เดิม
  ครบ; จนกว่าจะมีตัวเลขเหล่านี้ V-19 คง Pending และห้ามกล่าวอ้าง capacity
- profile ต้องครอบคลุมทุกคู่ USDT ใน pinned fixture ที่อนุมัติ ไม่เลือกเฉพาะคู่ที่ผ่านง่าย และใช้
  bounded concurrency/backpressure ของ candidate จริง
- ไม่รัน timed workload อัตโนมัติท้าย M1–M4; ก่อนรันชุดยาวต้องบันทึกเหตุผล environment,
  harness และหลักฐานสั้นที่ยัง valid ตาม testing §7
