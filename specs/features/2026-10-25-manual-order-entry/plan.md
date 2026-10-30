# F-16 — สั่งออเดอร์เองผ่านหน้าจอ — Plan

สถานะ: **Approved — เจ้าของตอบ “approve” ต่อ plan/validation ฉบับแก้ F16-R1/R2/R3 วันที่ 2026-10-25**
วันที่: 2026-10-25
อ้างอิง: requirements.md **Approved 2026-10-25**, ADR-004, testing §7

## 1. แนวทางและขอบเขต checkpoint

เพิ่มช่องรับคำขอของผู้ใช้สำหรับ Paper โดยใช้ API inbox ที่บันทึกอย่างถาวร แล้วให้ engine
แปลงคำขอเป็น `OrderIntent`/cancel และส่งเข้า F-15 เดิม API ไม่เรียก engine ผ่าน HTTP
ไม่ import service อื่น และไม่มีสิทธิ์เขียน orders/reservations/positions/ledger โดยตรง
ตรรกะเงิน การกันยอด fee matching และ financial single writer ยังอยู่ใน F-15

**candidate ของ F-16 รอบนี้ยังไม่เปิด production order admission:** F-18 ยัง Planned
และ `paper_order_main.py` ยังประกอบด้วย `policy=None` ซึ่งต้อง fail closed ต่อไป
ทำ form/read/command lifecycle และพิสูจน์ integration ด้วย test composition ที่แยกจาก
production; ห้ามมี environment switch ที่สร้าง allow-all policy หรือ bypass F-18
การเปิดใช้งานจริงต้องมี approved F-18 integration พร้อมหลักฐานตาม V-18 ใน validation
ไม่ถือว่าการผ่าน test policy ทำให้ด่านนี้ผ่าน และไม่เรียก F-16 Completed ก่อนครบ

หน้า Live ใช้ form component เดียวกันในสถานะ unavailable ไม่ผูก mutation ไปยัง Paper
ไม่เพิ่ม Live executor/credential access หรือเปิดใช้งาน F-22–F-24 ล่วงหน้า

## 2. ของเดิมที่จะใช้ซ้ำ — ตรวจจาก source แล้ว

ทุก path backend ด้านล่างอยู่ใต้ `backend/src/tiewtrade/`:

| ของเดิม | Path / ใช้ทำอะไร |
|---|---|
| OrderIntent, OrderScope, QuoteBudget/BaseSize, lifecycle, AdmissionPolicy | `core/orders.py` — ตรวจรูปคำสั่งกลาง ไม่สร้าง enum/size semantics อีกชุด |
| Matching/admission/reservation | `core/paper_matching.py`, `core/money/`, `core/positions.py` — ใช้สูตรและผล financial effects เดิม |
| Durable NEW/CANCEL และ replay | `infra/paper_orders/dispatch.py` — `submit_order`, `submit_cancel`, `get_order_command`; เรียกจาก engine เท่านั้น |
| Financial writer/source initialization | `infra/paper_orders/initialization.py`, `storage.py`, `worker.py` — lock episode, fence, recovery, catalog check ที่ execution |
| Order worker | `services/engine/paper_order.py`, `paper_order_main.py` — ต่อ intake dispatch ก่อนรอบเดิม โดยคง policy=None ใน production |
| Owner session / transaction | `infra/db/session.py` — API ภายใต้ RLS, engine owner session, scan read-only hints; repeatable read สำหรับ snapshot |
| Wallet/position snapshots | `infra/paper_wallet/storage.py`, `infra/positions/storage.py` — ใช้ข้อมูลจริงพร้อม source availability/proof และ snapshot time |
| Catalog/readiness | `core/market_catalog.py`, `infra/platform/`, `infra/market_data/catalog.py` — ไม่สร้าง allowlist ใหม่ |
| Account type | `core/trading_account.py`, `infra/trading_account/storage.py` — อ่าน MANUAL/BOT โดยไม่แก้ use หรือ key policy ของ F-08 |
| Auth/input/throttle | `services/api/request_identity.py`, `safe_input_routes.py`, `throttling.py`, `infra/auth/throttle.py` — authenticated owner, sanitized validation errors |
| API command pattern | `services/api/paper_wallet_routes.py` — commit ก่อนตอบ 202, status lookup และแยก pending กับ succeeded |
| Audit | `infra/audit/events.py`, `writer.py` — typed details, invariant, append-only; ไม่ใช้ข้อความอิสระ |
| Navigation/session | `frontend/src/accountNavigation.ts`, `AuthPanel.tsx`, `AccountPages.tsx`, `layout/AccountLayout.tsx`, `layout/AccountSidebar.tsx` — ต่อ route ใน shell เดิม ไม่เพิ่ม router package |
| Query/client/format | `frontend/src/paperWallet.ts`, `PaperWalletPanel.tsx`, `components/MarketValue.tsx`, `components/ui/` — ใช้ HTTP/error/query/invalidation patterns เดิม; ตรวจ actual formatter ก่อนเพิ่มชนิดใหม่ |

`frontend/src/components/ui/Tabs.tsx` ปัจจุบันปิดปุ่มทุกตัว จึงใช้ `Select` เดิมสำหรับ
ชนิดออเดอร์/ฝั่ง ไม่แก้ Tabs ทั้งระบบโดยไม่จำเป็น

### UI source mapping

- ฟอร์ม: `references/admin-template/src/components/form/form-elements/DefaultInputs.tsx`,
  `InputStates.tsx`, `components/form/input/InputField.tsx`, `components/form/Select.tsx`
  ใช้ `frontend/src/components/ui/{Input,Select,Label,Button,ComponentCard}.tsx` ก่อน
- ตาราง: `references/admin-template/src/components/tables/BasicTables/BasicTableOne.tsx`
  และ `components/ui/table/index.tsx` ผ่าน shared `Table.tsx`
- status/error: `references/admin-template/src/components/ui/badge/Badge.tsx`,
  `components/ui/alert/Alert.tsx`; หากยังไม่มี shared control ให้ปรับไว้ใน `components/ui/`
  พร้อม comment source path ไม่คัด style ลงแต่ละหน้า
- layout ใช้ AccountLayout ที่ปรับจาก template แล้ว; mode label ต้องเห็นตลอดหน้า
  ใช้ข้อความ PAPER/LIVE พร้อม template status tokens ไม่อาศัยสีอย่างเดียว
- ไม่มีข้อยกเว้น style ใหม่; ใช้ responsive grid/spacing/theme tokens ของ template
  และตรวจ light/dark/default/hover/focus/error/loading/disabled ที่เกี่ยวข้อง

## 3. เส้นทางและ API contract

เพิ่ม frontend page keys `paper/trade` และ `live/trade` ใน navigation เดิม ให้ URL จริง
เป็น `/paper/trade` และ `/live/trade`; back/forward, reload และ modified links ต้องใช้ได้
เข้าผ่าน auth shell เดิม ไม่แปลง live URL ไป Paper อัตโนมัติ

API paths ด้านล่างเป็น path ที่ router ประกาศ; browser ใช้ `/api` prefix ผ่าน client เดิม:

| Method / path | Contract |
|---|---|
| GET `/paper/trade` | snapshot ของ active wallet/episode: PAPER, wallet/episode IDs, account use, cash/reserved/available quote, held/reserved/available base รายคู่, position/order source availability, snapshot_at, catalog revision และ admission readiness/reasons; ถ้ายังไม่มี wallet คืน wallet=null ไม่สมมติเงิน |
| GET `/paper/orders?episode_id=…&cursor=…&limit=…` | order summaries ของตนเองใน episode; limit default 20/max 100, cursor keyset ผูก owner/episode กับลำดับ server ไม่ใช้ offset; มี next_cursor และ snapshot_at ห้ามผสมคนละ episode ใน cache |
| GET `/paper/orders/{order_id}` | authoritative status, side/kind/units, original amounts, filled/remaining/reservation จาก backend, failure code และเวลาที่เกี่ยวข้อง; ของผู้อื่นหรือไม่มีจริงได้ 404 เหมือนกัน |
| POST `/paper/orders` | strict discriminated input ตามสามรูปแบบด้านล่าง + expected wallet/episode IDs; header Idempotency-Key UUID; ห้าม owner/mode/origin/order_id/reduce_only ที่ client กำหนด |
| POST `/paper/orders/{order_id}/cancel` | expected wallet/episode IDs และ Idempotency-Key; ตรวจ ownership จริง ไม่เปิดเผยว่า order ของคนอื่นมีอยู่ |
| GET `/paper/order-requests/{request_id}` | owner-scoped joined snapshot ของ intake/linked command/order ตาม response contract ด้านล่าง; คืน worker rejection ได้แม้ไม่มีแถว paper_orders |
| GET `/paper/order-requests/by-key/{idempotency_key}?action=NEW\|CANCEL` | กู้ผลเมื่อ response หายก่อนทราบ request_id; คืน joined response เดียวกับ lookup ด้วย request_id; owner-bound lookup; key conflict ใช้ canonical fingerprint เดิม |
| GET `/paper/order-requests?state=unresolved&cursor=…&limit=…` | ค้นคำขอที่ยังรอ transfer หรือ linked command ยังไม่มี terminal result ของ owner ปัจจุบัน ครอบคลุมทุก episode ที่ยัง unresolved; default 20/max 100, stable keyset cursor ผูก owner/filter ไม่ตัดรายการ pending เก่าออกด้วย age limit |

### ผลคำขอที่อ่านได้หลังส่งต่อ (Review F16-R2)

request lookup ทั้ง ID/key และ discovery ใช้ response shape เดียวกัน มี typed request summary
(pair/side/kind/หน่วย/จำนวนที่รับจริงสำหรับแสดง pending โดยไม่คืน raw payload), request/action/
wallet/episode/order IDs, snapshot_at และ state สามระดับที่แยกกัน:

- `intake_state`: PENDING / TRANSFERRED / REJECTED และ `intake_failure_code`;
  TRANSFERRED หมายถึงบันทึก link ไป F-15 แล้วเท่านั้น ไม่ใช่ financial acceptance
- `command_id`, `command_state`: null เมื่อยังไม่ transfer, PENDING เมื่อมี command
  แต่ยังไม่มี result, SUCCEEDED / REJECTED ตาม `paper_order_command_results`;
  คืน `command_failure_code` และ typed `command_snapshot` ของ admission/cancel ด้วย
- `order_state`: null จนมี `paper_orders`/projection จริง จากนั้นคืนสถานะ authoritative
  พร้อม order status/เวลาข้อมูล; command REJECTED อาจไม่มี order_state และต้องยังอ่าน
  เหตุปฏิเสธได้ ไม่แปลงกรณีนี้เป็น resource 404

อ่านด้วย owner RLS และ repeatable-read snapshot โดย join immutable transfer link กับ
F-15 command/result และ order header/projection เท่าที่มี ไม่เขียนผล downstream ทับ
immutable intake result; migration ให้ API SELECT เฉพาะคอลัมน์จำเป็นของ link/command/
result/header/projection ไม่มี credential หรือสิทธิ์เขียน financial state
TRANSFERRED ที่ไม่มี linked command จริงเป็น integrity/dependency error ไม่คืน PENDING
หรือ fabricated REJECTED; response ไม่รั่ว raw database/payload error

poll request ต่อเมื่อ intake PENDING หรือ command PENDING; หยุดเมื่อ intake REJECTED
หรือ command terminal และแสดง failure code ที่ระดับถูกต้อง ถ้า NEW SUCCEEDED ให้ติดตาม
active order ผ่าน order detail/list ต่อจน terminal ไม่ถือว่า admission เป็น fill;
ถ้า CANCEL SUCCEEDED ต้องอ่าน target status จริง อาจเป็น FILLED อยู่ก่อนแล้ว ห้ามแสดง
CANCELED เพียงเพราะ cancel command สำเร็จ

สาม input variants: MARKET BUY `quote_budget` เป็นข้อความ USDT; MARKET SELL
`base_quantity` เป็นข้อความ; LIMIT BUY/SELL `base_quantity`, `limit_price` เป็นข้อความ
และ `time_in_force=GTC`. รับคู่ base/quote แยกชัดเจน; extra fields/JSON number/NaN/
ศูนย์/ติดลบ/เกินขอบเขตหรือ precision ที่ Money/Quantity รับไม่ได้ต้องปฏิเสธด้วยรหัส
ไม่ปัดหรือลดขนาดแทนผู้ใช้

**HTTP semantics:** 202 เมื่อ intake commit แล้ว, 200 สำหรับ replay/result/read,
409 สำหรับ identity/episode conflict, 422 สำหรับ input ไม่ตรง contract,
404 สำหรับ resource ไม่พบภายใต้ owner, 429 พร้อม Retry-After, 503 เมื่อ dependency
ไม่พร้อมหรือ production admission ปิด ไม่มี response ที่อ้างรับคำสั่งก่อน commit
หาก connection หาย/commit outcome ไม่ทราบให้ client แสดง UNKNOWN และ lookup/replay
ด้วย key เดิม; 404 จาก lookup ไม่ใช่หลักฐานว่าคำขอที่ยัง in-flight จะไม่ commit

ไม่เพิ่ม Live mutation route ใน F-16; Live page ใช้ local unavailable capability ที่ปิดตาย
และไม่สร้าง Paper queries/mutations ไม่ว่าการนำทางหรือเปลี่ยน payload จะทำอย่างไร

## 4. Inbox, สิทธิ์, transactions และ recovery

เพิ่ม additive migration ถัดจาก `0040` (คาดหมาย `0041_manual_order_requests.py`;
หาก head เปลี่ยนให้เลือกเลขถัดไปก่อนลงมือ ไม่แก้ migration เก่า):

- `paper_order_requests`: immutable intent/cancel payload ที่ schema ตรวจได้, user_id,
  wallet_id, episode_id, action, idempotency_key, fingerprint, request_id, order_id
  ที่ server สร้าง, server-captured `admitted_catalog_revision` สำหรับ BUY และ recorded_at;
  UNIQUE(owner, action, idempotency_key); catalog evidence เป็น immutable metadata
  ไม่รับจาก browser และไม่รวมใน fingerprint ที่แทน canonical client intent
- แยก mutable dispatch/lease/retry metadata ออกจาก immutable transfer/rejection result;
  terminal result ผูก request กับ F-15 command/order identity แบบ unique ไม่สร้างใหม่เมื่อ retry
- API มี SELECT/INSERT เฉพาะ inbox และ typed intake audit ภายใต้ RLS ไม่มี UPDATE/DELETE;
  engine owner role รับ claim/ส่งต่อ/บันทึกผล; scanner อ่านเฉพาะ due hints ไม่มี payload หรือ secret
  API อ่าน F-15 เฉพาะคอลัมน์ command/result/header/projection ที่ response contract ต้องใช้
  ตาม §3 ภายใต้ RLS ไม่มีสิทธิ์เขียน financial tables
- payload ไม่มี secret หรือ client-supplied actor/mode; composite owner/wallet/episode linkage,
  CHECK รูป JSON และ lifecycle, immutable triggers, indexes สำหรับ replay/due/list
- เพิ่ม audit actions สำหรับรับ/ปฏิเสธ/ส่งต่อคำขอ พร้อม typed details/invariant และ CHECK
  ของ details/actor/subject/mode/outcome; acceptance/result ที่ F-15 มีแล้วใช้ event เดิม
  ไม่สร้าง audit ว่าส่งสำเร็จเมื่อเพียง inbox commit
- admission, replay, transfer และ reset ใช้ advisory wallet lock key เดิม
  `paper-wallet:{owner}` ตาม lock order เดิม ไม่ถือ DB lock ขณะเรียกเครือข่าย
- inbox insert ที่ยังไม่ terminal ต้องนับเป็นภาระ pending ใน reset readiness ทั้ง API และ
  engine authoritative reset path; active episode check และ immutable result ทำใน lock เดียวกัน
  ปิด reset/intake/transfer race โดยไม่ย้ายคำขอไป episode ใหม่
- อัปเดต `paper_wallet_reset_readiness` ใน migration ใหม่และ F-08 activity evidence ที่ได้รับผล
  ให้เห็น pending intake; หลักฐานไม่ครบยัง UNKNOWN ไม่ถือ idle
- downgrade ต้องปฏิเสธเมื่อมี request/ผลที่รุ่นเดิมรับต่อไม่ได้ ไม่ลบ financial/audit history
  ไม่ rewrite migration 0037/0038 หรือเปลี่ยน financial writer protocol เดิม

API ทำ replay lookup/fingerprint check ก่อนรับงานใหม่ และสร้าง server order ID ครั้งแรก
ใน transaction เดียวกับ inbox/audit. แยก action namespace NEW/CANCEL ตาม F-15;
retry เดิมต้องได้ request/order เดิม แม้ episode ถูกปิดแล้ว ห้ามเช็ค active ก่อน replay
จนทำให้ผลเก่ากู้ไม่ได้

### Catalog continuity ตั้งแต่ intake ถึง execution (Review F16-R1)

NEW BUY ต้องถือ wallet lock แล้ว pair fence ตามลำดับเดิมก่อนบันทึก inbox ตรวจ active
catalog และจับ revision จาก server ใน transaction เดียวกับ inbox/audit; API ได้เพียง
สิทธิ์เรียก pair-fence function ที่จำเป็น ไม่มีสิทธิ์แก้ catalog. ห้ามเชื่อ revision ใน client
snapshot หรือเริ่มจับ revision ครั้งแรกตอน bridge; replay request เดิมไม่จับ revision ใหม่

bridge ตรวจ `latest_removed_revision > admitted_catalog_revision` ภายใต้ pair fence
ก่อน transfer: หากจริงให้บันทึก intake REJECTED/CATALOG_PAIR_REMOVED แบบ terminal
พร้อม audit ไม่สร้าง F-15 command แม้คู่จะถูกเพิ่มกลับแล้ว. ถ้ายังส่งต่อได้ต้องส่ง revision
เดิมเข้า F-15 และรักษาไว้จน execution; removal หลัง transfer ยังถูก worker ตรวจได้

ปรับ `infra/paper_orders/dispatch.py` ให้ `submit_order` รับ trusted server-captured
`admitted_catalog_revision` แบบ optional สำหรับ bridge และส่งผ่านไป `_submit`:
internal callers เดิมที่ไม่ส่งค่านี้ยังจับ revision ตอน submit ตามเดิม; caller ที่ส่งต้อง
ตรวจ revision ว่าเป็น integer ที่ถูกต้อง ไม่เกิน authoritative current revision และ
ไม่ถูก removal หลัง revision นั้น invalidate. เก็บ revision ต้นทางใน command payload
ห้ามแทนด้วย current revision ห้าม UPDATE command ย้อนหลัง และห้ามเปิด parameter นี้
ใน public request schema. request replay ใช้ fingerprint/identities เดิมก่อน gate ที่เปลี่ยนได้

SELL/cancel ไม่เพิ่มข้อบังคับ active catalog; การจัดเป็นลดความเสี่ยงยังต้องพิสูจน์จาก
holding/reservations ตาม gates เดิม. Test R1 ต้องหยุดได้ทั้งก่อนและหลัง transfer เพื่อ
แยกผลการถอนคู่ในแต่ละ boundary และพิสูจน์ว่า remove→re-add ไม่ฟื้นคำขอเก่า

engine intake bridge claim แบบ lease+revision fencing จำกัดไม่เกิน 20 hints/round และ
หนึ่งงานต่อ owner เช่น F-15; ใน owner transaction ถือ wallet lock ตรวจ episode และ
policy/account use และ catalog continuity ตามด้านบน แล้วเรียก `submit_order`
(ส่ง admitted_catalog_revision เดิมสำหรับ BUY) หรือ `submit_cancel` พร้อมบันทึก transfer
result แบบ atomic. crash ก่อน commit rollback ทั้งสองฝั่ง; หลัง commit replay ได้ identity
เดิม ไม่ยิงคำสั่งใหม่จากการหมด lease; serialization/claim loss ต้องไม่เปลี่ยนผลของ worker ใหม่
ไม่มี Redis-only queue; Redis ใช้เป็น hint ได้แต่ PostgreSQL scan ต้องกู้ได้เอง

**Shared safety:** เพิ่ม adapter ที่ core/infra boundaries ตามหน้าที่ โดยอ่าน authoritative
state ฝั่ง engine, แยกเพิ่ม/ลดความเสี่ยงจาก holding หลังหัก reservations ไม่เชื่อ SELL อย่างเดียว,
ตรวจ origin MANUAL และ account use ที่ execution. delegation ไป F-18 risk policy ต้องชัด
และ policy ไม่พร้อมต้อง fail closed; ห้ามเขียนสูตรเพดาน/RESET หรือ mock READY ใน production
catalog checks ที่ขอบ F-15 และข้อจำกัด execution filters ที่ไม่รองรับยังต้อง reject

NEW intake ใน production ตอบ 503 ก่อนสร้าง executable request ขณะยังไม่มี policy;
คำขอที่ค้างจากช่วงพร้อมแล้วต้อง recheck ที่ execution ไม่กลับมาส่งเองเมื่อเงื่อนไขไม่ผ่าน
cancel สำหรับ order เดิมไม่ต้องมี risk-opening permission/TOTP เพิ่ม แต่ต้องผ่าน
owner/episode/recording/fencing เดิมและไม่แก้ผล fill ที่เกิดแล้ว

### การคุมทรัพยากร

เพิ่ม owner token buckets แยก `PAPER_ORDER_NEW` และ `PAPER_ORDER_CANCEL` ใน api_throttle
ตาม pattern เดิม เสนอ capacity 20 เติม 1 token/วินาทีต่อ bucket; replay ที่พบแล้วไม่เสีย
mutation quota ซ้ำ การยิง NEW ไม่กิน cancel bucket. เป็น server protection ไม่ใช่เพดาน
ขนาดไม้/เงิน และยังไม่แทน quota ของ venue ในงาน Live. อ่าน snapshot/list/status ใช้ bounded
queries และ frontend polling เฉพาะหน้าที่เปิด; ไม่เพิ่ม unbounded background fetch

## 5. Frontend และข้อมูลจริง

เพิ่ม `ManualOrderForm.tsx` (presentation + local draft), `PaperTradePage.tsx`,
`LiveTradePage.tsx`, `PaperOrderList.tsx`, `manualOrders.ts`, `manualOrderMessages.ts`
ตาม pattern repo; state/server effects แยกจาก form ไม่รวมทุกอย่างในไฟล์เดียว

- form แสดงหน่วยตามชนิด หลีกเลี่ยง input type=number ที่แปลงค่าเป็น float;
  ไม่มี quantity slider/เปอร์เซ็นต์/max/ประมาณยอดที่คิดเงินใน browser
- อ่าน wallet/account/catalog/order summary จาก server ด้วย TanStack Query;
  query key มี owner/mode/episode/resource/filter และ cursor, cancel AbortSignal
  เมื่อ route/user/episode เปลี่ยน; logout clear ตาม AccountSession เดิม
- snapshot ตัวเลขและ readiness มาจาก repeatable-read transaction เดียวกัน;
  unavailable ไม่เท่ากับยอด 0; source ไม่พร้อมต้องบอกเหตุและเวลาเดิมให้เห็น
- ทำเครื่องหมายคำขอค้างแยกจากรายการออเดอร์; SUCCEEDED ของ command คือ admission/cancel
  ไม่ใช่ FILLED; ไม่ optimistic update ยอด/position หรือสถานะยกเลิก
- หลัง mutation refetch/invalidate wallet/trade snapshot/list/detail ที่เกี่ยวข้อง;
  command poll ทุก 1 วินาทีเฉพาะ pending ที่มองเห็น หยุดเมื่อ terminal/ออกหน้า/logout
  snapshot/list refetch ทุก 5 วินาทีขณะ visible; background ไม่ poll และไม่ใช้ browser clock
  รับรอง market/account freshness
- **Recovery journal (Review F16-R3):** ก่อนส่ง POST ให้เขียน action/key/canonical payload/
  wallet/episode/owner/PAPER ลง sessionStorage ของ tab แบบ synchronous และตรวจว่าเขียนได้;
  ถ้า storage ใช้ไม่ได้ต้องแจ้งและไม่ส่ง mutation ใหม่ ไม่เก็บ credential/cookie/secret
- restore journal เมื่อ mount/reload/back/forward ของ owner เดิม แล้ว lookup ด้วย key เดิม;
  ไม่ส่ง POST หรือสร้าง key ใหม่อัตโนมัติเมื่อ mount และไม่ล้าง journal เพราะ unmount,
  timeout, 503 หรือ lookup 404. lookup ไม่พบขณะ request เดิม in-flight ยังเป็น UNKNOWN;
  retry ที่ผู้ใช้สั่งต้องใช้ key+payload เดิม ไม่ข้ามไป episode ปัจจุบัน
- journal เก็บเฉพาะ client attempt identity/draft ไม่เป็นสำเนา server state; ผลอ่านทั้งหมด
  อยู่ใน TanStack Query. เมื่อมี request_id แล้วคง key ไว้จนทราบ intake/command terminal
  จึงล้าง attempt; NEW ที่ admission สำเร็จยังปรากฏใน active order list ตามปกติ
- mount/reconnect และ login owner เดิมต้องค้น unresolved requests จาก server ด้วย discovery
  endpoint ตาม §3 และอ่านทุกหน้าที่ผู้ใช้ต้องกู้ โดย merge ตาม request/key ไม่สร้าง POST;
  ทำให้พบ pending ที่มาจากอีก tab หรือที่ browser journal หาย ไม่จำกัด discovery ให้เฉพาะ
  active episode. เช็ค owner/mode/episode ทุกผลก่อนแสดง; query/discovery ล้มเหลวต้องบอกว่า
  ยังตรวจคำขอค้างไม่ได้ ไม่แสดงว่าไม่มีคำขอและไม่เปิด form ให้ส่งใหม่จน recovery อ่านสำเร็จ
- logout/เปลี่ยน owner ต้องหยุด polling, ล้าง journal ของ owner เดิมและ query cache ตาม
  session lifecycle; ห้ามนำ key/draft ไปใช้เป็นอีก owner. กลับมา login ให้ discovery หา
  committed unresolved requests ของตนใหม่; server ไม่ส่งหรือ resubmit คำขอจากการอ่าน
- ระหว่างยังมี UNKNOWN attempt ใน tab ห้ามเริ่มคำสั่งใหม่จาก draft เดิมจน resolve;
  คำขอที่ไม่ commit กู้ด้วย journal+same-key retry ส่วนที่ commit แล้วกู้ได้ทั้ง journal และ
  discovery. ไม่อ้างรับรอง at-most-once ต่อความตั้งใจที่ผู้ใช้ส่งเองด้วยคนละ key/คนละ tab
- `LIVE` แสดงเหตุยังไม่พร้อม, form disabled และทางออกตรงตลาดสำหรับปัญหา Live;
  `PAPER` แสดง admission blocked reason จริง ไม่มีข้อความว่าพร้อมขณะ policy=None
- ไทย/อังกฤษจาก message layer เดิม; สถานะเงิน/ปริมาณ/เวลา/order status ผ่าน formatter/
  shared display component ไม่เขียนคำนวณหรือ mapping กระจายหน้า

## 6. ไฟล์ที่คาดว่าจะเปลี่ยน

| ส่วน | ไฟล์/หน้าที่ |
|---|---|
| API | ใหม่ `services/api/manual_order_routes.py`; ต่อ `app.py`, OpenAPI และ api-types ตาม generator |
| Inbox/read | ใหม่ `infra/paper_orders/requests.py`, `views.py` และ records; discovery/joined command outcome; ปรับ `dispatch.py` ส่งต่อ admitted catalog revision ตาม R1 โดยไม่เปลี่ยน replay เดิม |
| Intake bridge | ใหม่ `services/engine/manual_order.py`; ต่อ `paper_order_main.py` และใช้ infra bridge helpers ห้าม API import engine |
| Safety adapter | `core/orders.py`/โมดูลใหม่ใน core และ infra owner snapshot ตาม boundary; คง policy protocol ของ F-15 หากทำได้ |
| Persistence/audit | migration ใหม่, `infra/audit/events.py`/exports, throttle buckets; reset readiness/activity callers ที่กระทบ |
| UI | ไฟล์ใน §5, navigation/AuthPanel/sidebar/breadcrumb messages และ ui display primitives เท่าที่ขาด |
| Tests/contracts | backend API/infra/engine/gates, frontend tests/e2e, OpenAPI exports/generated types และ CI เฉพาะ hook E2E ที่ต้องเพิ่ม |
| Spec/evidence | validation ผลจริง, evidence checkpoint ตาม M1–M4 และ roadmap สถานะ/pending dependencies |

## 7. Milestones และการตรวจ

| Milestone | งาน / หลักฐานขั้นต่ำ |
|---|---|
| M1 — Contract/persistence | strict inputs, inbox schema/RLS/audit/replay/read models; real PostgreSQL role/isolation/immutability/rollback/reset-pending checks; V-1/2/3/4/7/10/11 |
| M2 — Engine/API | fenced bridge + F-15 integration, owner/episode locks, readiness fail closed, command recovery/read API, throttle; targeted money/order safety and cancel/reset/catalog races; V-3–13/17 |
| M3 — UI | shared form, separate URLs, real queries/states/i18n/template/a11y; component tests + browser flow ด้วย isolated Paper harness; V-1/5/6/12–16/17 |
| M4 — Candidate/review | แจ้ง **Ready for Code Review** ทันทีเมื่อเขียนครบขอบเขต พร้อม changed files/tests/pending/risks; review diff/dependencies เน้น Critical/High → แก้ → final checks; V-19 |

ทุก milestone ใช้หลักฐานเดิมที่ยัง valid ตาม testing §7 และจดเวลาที่วัดจริง/ช่วงไม่ได้วัด
ไม่เพิ่ม timed smoke/workload เป็นพิธีท้ายงาน. ที่ M4 ปิดได้เพียง Development Complete
สำหรับขอบเขตปิด admission เมื่อหลักฐานพร้อม; V-18 และ V-20 ยังต้องติดตามแยก
ห้าม commit/push/merge ก่อนเจ้าของสั่ง

## 8. ความเสี่ยงและเกณฑ์หยุด

- Pending inbox หลุดจาก reset evidence → reset ระหว่างคำสั่งค้าง: พิสูจน์ทั้ง DB function และ
  engine transaction ภายใต้ race จริง ไม่ยอมรับ mock เป็นหลักฐาน
- Response หายหรือ lease หมด → สร้างคำสั่งซ้ำ: พิสูจน์ atomic transfer/unique IDs/CAS/lookup
- ประเภทบัญชีหรือ catalog เปลี่ยนหลังกรอก → เปิดความเสี่ยงผิด: recheck ที่ execution
- Policy ไม่พร้อมแต่ UI ว่าพร้อม → production เปิดโดยอ้อม: gate integration tests และคง
  policy=None; V-18 ไม่ผ่านจน dependency พร้อมจริง
- Filter/capability ที่ F-15 ไม่รองรับ → ปฏิเสธด้วยรหัสเดิม ไม่เพิ่มสูตรหรือลด safety rule
- หาก implementation ต้องเปลี่ยน approved scope/architecture หรือพบโค้ดขัด spec
  ให้บันทึก Needs Clarification และหยุดขออนุมัติก่อนแก้ทาง ไม่ปรับแผนตามหลังโค้ด

## 9. ปิด findings ของ document review — 2026-10-25

เจ้าของสั่ง “แก้ไข” หลัง review CHANGES REQUIRED; แก้เฉพาะ Proposed plan/validation
ภายใต้ requirements เดิม ไม่ถือเป็นอนุมัติ implementation

| Finding | การแก้ในแผน | เกณฑ์ตรวจที่ผูกไว้ |
|---|---|---|
| F16-R1 — High: catalog revision เริ่มใหม่ตอน transfer | server-captured intake revision + pair fence, bridge invalidate และส่ง revision เดิมถึง F-15 | V-3/V-9: replay ไม่เปลี่ยน revision; remove/re-add ก่อนและหลัง transfer |
| F16-R2 — High: อ่าน downstream rejection ไม่ได้ | joined intake/command/order response, จำกัดสิทธิ์ SELECT, polling แยกแต่ละ lifecycle | V-2/V-11/V-14/V-16: reject ไม่มี paper_orders และ cancel target terminal |
| F16-R3 — Medium: reload ทำ key หาย | write-before-send journal + owner-bound unresolved discovery + same-key recovery | V-3/V-10/V-14/V-16: response loss→reload/unmount/login, storage failure และ owner isolation |

สถานะการปิดข้างต้นเป็นการแก้ช่องว่างของเอกสาร ยังไม่มี runtime proof และผล validation
คง Not Run/Pending ตามเดิม; เจ้าของอนุมัติฉบับแก้ไขแล้ว 2026-10-25 ให้เริ่ม M1 ได้

## F16-R4 — Compact Trading Workspace implementation plan — 2026-10-30

สถานะ: **Approved — เจ้าของอนุมัติแผนวันที่ 2026-10-30**

1. ปรับ `CandlestickChartPanel` ให้รับ pair จาก parent และมี embedded presentation โดยหน้า chart
   เดิมยังคง pair/timeframe/history navigation/resize; embedded presentation ไม่แสดง placeholder
   order/history ซ้ำ
2. เพิ่ม shared workspace layout สำหรับ Paper/Live โดยใช้ `Button`, `Select`, `Input`, `Table`,
   `Modal` และ interactive Tabs ที่ปรับจาก admin template; route สองหน้านี้ใช้ content widthเต็ม
   และซ่อน breadcrumb ที่ซ้ำกับ mode header
3. ฟอร์มคง payload/validation เดิม เปลี่ยน side/kind เป็น tabs และซ่อน pair selectorเมื่อ parent
   ควบคุม pair; remount key เดิมยังล้าง draft เมื่อ pair/episode เปลี่ยน
4. Paper แสดง balance/risk summary, blocking reasons และ uncertain recovery ใกล้ฟอร์ม;
   รายละเอียด risk/wallet เปิดตามต้องการ และ recovery section แสดงเฉพาะเมื่อมีงานหรือ error
5. รายการ Paper แยก Open/History จาก rows เดิม; ถ้ายังมี page ที่ไม่โหลด ห้ามสรุปว่า tab ว่าง
6. Live ใช้ catalog+chart เดียวกันและ disabled form โดยไม่ query/render Paper wallet/orders

Source mapping: layout/tabs/forms/tables/modal ยึด
`references/admin-template/src/components/ui/tabs/TabWithUnderline.tsx`,
`references/admin-template/src/components/form/`,
`references/admin-template/src/components/tables/` และ shared controls ใน
`frontend/src/components/ui/`. ข้อยกเว้นจาก template คือกราฟต้องใช้พื้นที่ยืดหยุ่นและแถบฟอร์ม
ประมาณ 360px เพื่อรักษา readability ของ trading workspace; ใช้ theme tokensเดิมทั้งหมด
และไม่เพิ่ม visual system ใหม่
