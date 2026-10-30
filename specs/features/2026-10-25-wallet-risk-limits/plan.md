# F-18 — เพดานความเสี่ยงต่อกระเป๋า — Plan

สถานะ: **Approved** — เจ้าของตอบ “approve” ต่อ plan/validation ฉบับแก้ F18-R1..R4 วันที่ 2026-10-26; อนุมัติปรับเวลา validation W1/W2/W3 เป็น 10/5/30 นาที วันที่ 2026-10-27
เกณฑ์ปัจจุบัน: **R32 Approved 2026-10-29 — Paper fixture 5Hz**; ดู [amendment](paper-source-cadence-amendment.md) ซึ่งแทนเฉพาะ 10Hz ในข้อความเก่า
โหมดตรวจรับปัจจุบัน: **R33 Approved 2026-10-29 — explicit child publisher** ตาม [amendment](child-acceptance-mode-amendment.md); ใช้เกณฑ์ล่าสุดด้านล่าง
วันที่: 2026-10-25
เกณฑ์ล่าสุด: **R34 Approved — source count ขาดได้ 1/channel/run และ risk ราย owner 99.5% ภายใน3s สำหรับ W1–W3**; [ขอบเขตและการใช้หลักฐานเดิม](paper-acceptance-tolerance-amendment.md)
ปรับล่าสุด: 2026-10-26 — แก้ deep-review F18-R1..R4; Approved 2026-10-26
อ้างอิง: requirements.md **Approved 2026-10-25**, NC-F18-01..08, ADR-004, testing §7

## 1. แนวทางและขอบเขต

เพิ่ม pure risk domain ที่ใช้ Money/Quantity และผล position/PnL ของ F-14 จากนั้น
ประกอบกับ durable owner-scoped risk commands, monitor และ Paper order writer เดิม
API ไม่เขียนเพดานที่มีผลจริง/latch/baseline/order/ledger โดยตรง Redis ใช้ปลุก worker
ได้แต่ PostgreSQL ต้องกู้ commands, cursors, latch และงานยกเลิกที่ค้างได้ทั้งหมด

ทำ Paper integration และการจัดการ queued/active orders ใน F-18 ตาม NC-F18-07
โดยไม่เพิ่มหน้าปุ่ม Kill Switch หรือ bot lifecycle ส่วน Live มี setting/read contract
และ shared domain tests เท่านั้น ความพร้อม PnL ยังคง unknown จน F-23 ส่งหลักฐานครบ
ไม่ประกอบ Live executor ไม่เปิด Live และไม่เพิ่มทาง Paper เข้าถึง venue credential

ช่วงพัฒนาถึง candidate ยังปิด production NEW admission ค่า policy=None เดิมเป็น
dependency guard จน composition จริงและด่าน activation ผ่าน ไม่ใช้ allow-all fallback
หรือ environment switch เปิดข้ามด่าน การเปลี่ยน production composition อยู่ M5
และต้องมีหลักฐาน validation V-18/19/21 ก่อนเปิดใช้งานจริงตาม testing §7

## 2. ของเดิมที่จะใช้ซ้ำ — สำรวจ source แล้ว

ทุก path backend ในตารางอยู่ใต้ `backend/src/tiewtrade/`:

| ของเดิม | Path / วิธีใช้ |
|---|---|
| เงิน/ปริมาณ/การจัดสรร | `core/money/`, `core/money/position_arithmetic.py` — Money, Quantity, allocate_money และ explicit rounding เดิม ไม่สร้าง numeric policy ใหม่ |
| Position/PnL/corrections | `core/positions.py`, `infra/positions/storage.py`, `records.py` — PositionTransition.realized_increment, held/cost, source revision/proof และ effective correction stream |
| Order gates/matching | `core/orders.py`, `core/manual_trading.py`, `core/paper_matching.py` — AdmissionPolicy, authoritative reduction, reservations, cancel/terminal transitions |
| Single writer | `infra/paper_orders/storage.py::lock_episode`, `lock_pair_catalog`, `initialization.py` — owner advisory lock, active episode และ F15 writer marker; ไม่สร้าง financial lock แยก |
| Intake/claim/recovery | `infra/paper_orders/requests.py`, `request_dispatch.py`, `request_worker.py`, `dispatch.py`, `worker.py`, `matching_storage.py`, `corrections.py` — คง inbox/result/claim fence และ persist financial checkpoint เดิม |
| Wallet/reset | `infra/paper_wallet/storage.py`, `services/engine/paper_wallet.py` — episode/ทุน/RESET เดิม แยกจาก loss reset |
| Price readiness | `core/realtime_prices.py`, `infra/market_data/realtime_storage.py::write_price/read_snapshot` — generation/revision/trade timestamp/connection/lease และ MAX_PRICE_AGE เดิม |
| Catalog/delisted exposure | `infra/platform/`, `infra/market_data/catalog.py` — คง price/filter maintenance สำหรับ exposure ที่ถูกถอน ไม่กรอง risk position ตาม active catalog |
| Sessions/roles | `infra/db/session.py`, `services/api/db_resources.py` — owner RLS, API/AUTH/ENGINE/ENGINE_SCAN/MARKET_DATA roles และ repeatable reads |
| TOTP/classification | `services/api/routing_policy.py`, `authentication.py`, `infra/auth/totp.py`, `throttle.py` — middleware reverify/header/quota/replay protection เดิม ไม่อ่าน secret ออกนอกโมดูล |
| Audit | `infra/audit/events.py`, `writer.py` — typed event/details/invariants และ immutable audit |
| API/client recovery | `services/api/manual_order_routes.py`, `paper_wallet_routes.py`, `frontend/src/manualOrderJournal.ts`, `useManualAttempt.ts` — durable receipt/by-key/UNKNOWN pattern; ใช้หรือสกัดส่วนที่ใช้ร่วมจริงภายในขอบงาน ไม่เพิ่ม recovery implementation ชุดที่สาม |
| UI | `frontend/src/PaperTradePage.tsx`, `LiveTradePage.tsx`, `PaperWalletPanel.tsx`, `TotpPanel.tsx`, `components/MarketValue.tsx`, `components/ui/` — mode label, server values, TOTP prompt และ shared controls |

### UI source mapping

- Form: `references/admin-template/src/components/form/form-elements/DefaultInputs.tsx`,
  `InputStates.tsx`, `form/input/InputField.tsx`, `form/Label.tsx`
  ผ่าน shared `Input`, `Label`, `Button`, `ComponentCard` ใน `frontend/src/components/ui/`
- Confirm: `references/admin-template/src/components/UiExample/ModalExample/FormInModal.tsx`
  ผ่าน shared `Modal.tsx`; focus return/keyboard ตาม modal เดิม
- Status: `references/admin-template/src/components/ui/badge/Badge.tsx`, `ui/alert/Alert.tsx`
  ผ่าน shared Badge และปรับ shared Alert จากต้นแบบหากยังไม่มี พร้อม source comment
- Order effects list: `references/admin-template/src/components/tables/BasicTables/BasicTableOne.tsx`
  ผ่าน shared Table; ปุ่ม cancel ของผู้ใช้ยังใช้ F-16 component
- ไม่มี style exception ใหม่ ใช้ template tokens/light/dark/spacing/breakpoints เดิม
  ข้อความเตือนการ reset ที่ยังถือไม้ลบและสถานะ mode มาจาก trading safety

### ไฟล์ที่จะเพิ่มหรือแก้

| Path | การเปลี่ยนแปลงในขอบ F-18 |
|---|---|
| `backend/src/tiewtrade/core/risk_limits.py` | เพิ่ม domain/contracts/policy/reset allowance |
| `backend/src/tiewtrade/infra/risk_limits/{records,storage,requests,dispatch,monitor,stops}.py` | เพิ่ม scoped persistence, inbox, claims, evaluation และ stop consumer โดยเรียก F-15 writer เดิม |
| `backend/src/tiewtrade/infra/paper_orders/{requests,request_worker,worker,manual_policy,trade_views,corrections}.py` | ประกอบ risk evidence ที่ intake/transfer/fill/correction และไม่ขวาง reduction/cancel |
| `backend/src/tiewtrade/infra/paper_wallet/storage.py`, `infra/positions/storage.py` | ผูก episode transition/correction กับ risk revision ไม่เปลี่ยนสูตรเงินเดิม |
| `backend/src/tiewtrade/infra/market_data/realtime_storage.py` | เพิ่ม atomic public risk price frames/feed transitions |
| `backend/src/tiewtrade/services/engine/{risk_limit,risk_limit_main,paper_order,paper_order_main,manual_order}.py` | risk monitor/command rounds และ policy factory ต่อ transaction |
| `backend/src/tiewtrade/services/api/{risk_limit_models,risk_limit_routes,manual_order_routes,manual_order_models,routing_policy,authentication,app}.py` | API/auth receipt/strict routes/readiness/composition |
| `backend/src/tiewtrade/infra/audit/`, `infra/auth/` | typed audit, request-bound TOTP receipt และ quota เดิม; ไม่เผย secret |
| `backend/migrations/versions/0043_wallet_risk_limits.py` และ migration ถัดไปตาม rollout | tables/RLS/grants/writer fence/constraints ตามหัวข้อ4/8 |
| `frontend/src/RiskLimitPanel.tsx`, `riskLimits.ts`, `riskLimitMessages.ts`, `PaperTradePage.tsx`, `LiveTradePage.tsx`, `components/ui/` | shared risk panel/client/translations/template controls และ recovery |
| `backend/tests/{core,infra,api,services,gates}/`, `frontend/src/`, `frontend/e2e/` | เพิ่ม/ขยาย affected tests ตาม validation ไม่เพิ่ม tests ที่ยืนยัน implementation ซ้ำ |
| `compose.yaml` และ test harness/config ที่เริ่ม engine | ต่อ risk process/health/dependency readiness ไม่เพิ่ม venue credential ให้ Paper |

ชื่อไฟล์ใหม่เลือกตาม convention ของ package ตอน implementation ได้โดยไม่เปลี่ยน
responsibilities/contracts ที่อนุมัติ; ถ้าต้องเปลี่ยนแนวทางให้ขอ plan amendment ก่อน

## 3. Domain และฐานการนับ

เพิ่ม `core/risk_limits.py` เป็น public immutable contracts: RiskScope, RiskSetting,
RiskBaseline, PairRiskState, RiskEvaluation, RiskStop และ policy ที่ implement
AdmissionPolicy ผู้เรียกส่ง now, prices, source proofs, revisions และ IDs เข้ามา
core ไม่อ่านนาฬิกา/DB/network และไม่รู้ credential/executor

ตั้งค่าแยก owner/mode; Paper ใช้ wallet และ active episode เป็นขอบ financial source
ค่าเพดานกับ latch อยู่ตลอดอายุ wallet ไม่ใช้ episode ใหม่ล้าง latch; Live ผูกบัญชี
เทรดเดียวของ owner/mode ไม่ผูกประวัติกับ key ID การเปลี่ยน key ทำให้ source unknown
จนพิสูจน์ authority ใหม่ ไม่สร้างฐานศูนย์เอง

### การจัดสรรและการ replay

1. เมื่อ loss reset ผ่าน authoritative snapshot ที่ครบ เก็บ cutoff ของ event streams,
   source revisions/proofs, price frame และ unrealized loss ของแต่ละ pair เป็น
   loss allowance เริ่ม adjusted realized ใหม่ที่ศูนย์ ไม่แก้ cost basis ของ F-14
2. BUY ใช้ cost/quantity ของ F-14 และไม่เพิ่ม allowance เมื่อรวม weighted-average
   position คง allowance เงินเดิมกับ held ใหม่ การ SELL ใช้จำนวนที่ลดจริงของ transition
   เพื่อจัดสรร allowance ตามสัดส่วน held ก่อนขาย ไม่สร้างต้นทุนหรือ fee rule อีกชุด
3. ใช้ allocate_money ปัด allowance ส่วนที่ขาย TOWARD_ZERO ตามกฎไม่เข้าข้างผู้ใช้;
   full close ใช้ allowance คงเหลือทั้งหมดเพื่อปิด residual อย่าง exact ส่วนที่จัดสรร
   ถูกใช้ได้ไม่เกิน realized loss ของส่วนนั้น ที่เหลือหมดไป ไม่กลายเป็นเครดิตกำไร
4. Unrealized loss ที่นับเป็น loss ของจำนวนที่ยังถือหลังหัก allowance คงเหลือ ต่ำสุด0
   adjusted realized ใช้ผล F-14 หลังยกเว้น loss ส่วนที่ขายตามข้อ3 แล้วใช้ NC-F18-02
   รวมข้ามทุก pair ของ wallet รวม closed pairs และ delisted exposure
5. ใช้ตัวเลขที่อนุมัติใน NC-F18-03 เป็น oracle; reset ซ้ำแทน allowance ด้วย loss ค้าง
   ปัจจุบัน ไม่ทบของเดิม ทุน/reset credit ของ F-13 ไม่เข้าผล realized
6. Correction ทำให้ proof เก่าใช้ไม่ได้ rebuild effective fills และ baseline ตาม
   cutoff ที่บันทึก ณ reset โดยใช้ historical price frame เดิม ห้ามเอาราคาปัจจุบัน
   ไปแก้ฐานในอดีต ระหว่าง rebuild ให้ unavailable; ถ้าข้อมูลที่ต้องใช้ขาดยังคง
   unavailable ไม่แทนด้วยศูนย์ ไม่ล้าง latch และไม่เปิด admission จนหลักฐานครบ

แยก setting state (`UNSET`/`SET`), valuation readiness (`READY`/`UNAVAILABLE`),
loss latch และ stop progress (`STOPPING`/`STOPPED`/`PROBLEMS`) เป็นคนละมิติ
ราคาเด้งกลับ/price recovery ไม่ล้าง latch; loss reset ไม่ยกเลิก durable stop/cancel
ที่เกิดก่อนหน้า และไม่เปิดบอทที่หยุดด้วยสาเหตุอื่น

## 4. Persistence, roles และ mutation contract

เพิ่ม additive migration ถัดจาก head 0042 (คาด 0043_wallet_risk_limits.py;
ตรวจ head ก่อนลงมือ ไม่แก้ migration เก่า) และ migration แยกถ้าการเพิ่ม journal/
writer fencing จำเป็นต้อง rollout เป็นขั้น ตามหัวข้อ8

| กลุ่มตารางใหม่ | ความจริงที่เก็บ / สิทธิ์ |
|---|---|
| `risk_limit_requests/results` | immutable action/actor/owner/mode/scope/expected revision/fingerprint และ engine result; API INSERT request/SELECT ของตน ENGINE INSERT result; UNIQUE(owner,mode,idempotency_key) และ action/payload conflict ตรวจได้ถาวร |
| `risk_limit_authorizations` | immutable owner/mode/action/key/fingerprint/expected revision และ authorization ID ที่ AUTH สร้างพร้อม consume TOTP; UNIQUE(owner,mode,idempotency_key) ป้องกันอนุมัติ payload ต่างกันด้วย key เดิม; API อ่านของตนได้แต่ INSERT/UPDATE/DELETE ไม่ได้; request consume-link อ้างได้เพียง request เดียวด้วย FK/UNIQUE |
| `risk_limit_settings/events` | setting projection กับ append-only SET/INCREASE/RESET/BREACH/source-conflict events; ENGINE เขียน API อ่านภายใต้ RLS; monotonic revision และค่าหน่วย Money เดิม |
| `risk_limit_baselines/pairs` | immutable reset identity/cutoffs/source proof/price frame/allowances; per-pair projection สร้างจาก facts/rebuild ได้ ไม่แก้ F-14 history |
| `risk_limit_evaluations` | ผล/เหตุผล/source revisions/price references และเวลาพร้อมของ inputs ถึง durable result; ENGINE เขียน projection ล่าสุดและ immutable decision เมื่อสถานะเปลี่ยน ไม่เขียน audit ต่อ price tick |
| `risk_stop_requests/effects` | breach identity, stop revision, queued/active order targets, immutableผลแต่ละใบ และ recovery cursors; UNIQUE ป้องกัน cancel/job ซ้ำต่อ stop/order; ENGINE writer เท่านั้น |
| `market_risk_price_frames` | public immutable frames จาก F-10 committed price/feed revisions พร้อม readiness/generation/trade_at/lease proof และ publication high-water mark; ไม่มี owner/ข้อมูลเงิน; MARKET_DATA เขียนเฉพาะข้อมูลตลาด API/ENGINE อ่าน |
| `risk_financial_boundaries` | immutable owner-scoped marker ต่อ fill/correction/reset/episode transition: financial revision ก่อน/หลัง, source event references, price high-water mark และ replay status; ENGINE เขียนพร้อม financial commit ภายใต้ publication fence เพื่อกู้ deferred risk replay ได้โดยไม่ย้อน holdings ผิดช่วง |

ทุก user table มี owner NOT NULL, FORCE RLS และ scope/FK/mode constraints
API ไม่ได้ UPDATE/DELETE settings/events/baselines/effects ENGINE_SCAN อ่านเฉพาะ
owner/id/due hints ไม่มี secret หรือสิทธิ์แก้ข้อมูล MARKET_DATA ไม่เห็น user tables
audit เพิ่ม typed RISK_LIMIT_* / RISK_STOP_* พร้อม CHECK/action/subject mapping ให้ครบ
durable request, result และ audit ต้อง commit พร้อมสิ่งที่กล่าวว่าทำสำเร็จ
downgrade ที่มี financial/risk history ต้อง guard ปฏิเสธการลบ ไม่ล้างข้อมูลเพื่อให้ย้อนผ่าน

### API (paths ของ router; browser ใช้ /api prefix เดิม)

| Method/path | Contract |
|---|---|
| GET `/{paper\|live}/risk-limit` | owner setting/revision, nullable scope/source availability, allowance/baseline summary, adjusted loss, latch/stop progress, current stop ID/effects revision/counts และ market/snapshot/evaluated timestamps/readiness reasons; ไม่มี order list/history ใน snapshot ไม่ตีความยังไม่มี wallet/source เป็น0 |
| GET `/{paper\|live}/risk-limit/stops/{stop_id}/effects?cursor=…&limit=…` | owner/mode/stop-scoped targets พร้อมผลล่าสุด ณ snapshot watermark, limit default20/max100/min1, stable keyset pagination มี next_cursor/effects_revision/snapshot_at; รายละเอียดและ snapshot consistency ตามหัวข้อด้านล่าง |
| POST `/{paper\|live}/risk-limit` | SET ครั้งแรกหรือ DECREASE เท่านั้น: strict amount string USDT, expected_revision และ expected wallet/episode สำหรับ Paper; server เปรียบเทียบ current setting ที่ intake และ execution ห้ามใช้ทางนี้เพิ่มเพดานเมื่อ request ค้าง |
| POST `/{paper\|live}/risk-limit/increase` | middleware `reverify=True`, ไม่รับ recovery grant; body เช่นเดิม ต้อง expected revision ตรงและเป็นการเพิ่มจากค่าปัจจุบันที่ engine; TOTP proof ผูกกับ durable request identity/action/payload ไม่เก็บรหัส TOTP ลง inbox/log |
| POST `/{paper\|live}/risk-limit/reset` | expected revision/financial scope; ไม่บังคับ TOTP และไม่จัดเป็น risk-reducing order; engine ต้องมี complete source/ราคาที่ต้องใช้ก่อน reset baseline ไม่ปลด latch จาก unknown |
| GET `/{paper\|live}/risk-limit/requests/{id}` และ GET `.../requests/by-key/{key}` | owner-scoped lookup รวม AUTHORIZATION_ONLY ก่อน inbox commit และ REQUEST_PENDING/APPLIED/REJECTED เมื่อมี request/result; กู้ UNKNOWN ตาม protocol ด้านล่าง replay key เดิม payload ต่าง409 ไม่เริ่ม baseline ใหม่ |

mutation ทุกตัวใช้ Idempotency-Key UUID, CSRF/session/throttle เดิม, extra fields
owner/mode/actor ถูกปฏิเสธ mode จาก route; 202หลัง inbox commit/200replay,
404uniform,409revision/scope,422input,429Retry-After,503dependency
read/poll ไม่ renew session เพิ่ม route classification และ generated OpenAPI/client
ห้ามส่ง JSON number/float แทน Money text หรือ log TOTP/header/payload ดิบ

### Authorization และ recovery ของ increase (แก้ review F18-R3)

1. authenticate session/CSRF และ strict-parse increase input/key ด้วย schema กลาง
   ก่อนตรวจ TOTP สร้าง canonical fingerprint จาก owner/mode/action/key/amount/
   expected revision/financial scope ไม่มี TOTP หรือ session token ใน fingerprint
2. เฉพาะ increase route middleware ตรวจ receipt ของ identity นี้ก่อนยืนยันซ้ำ:
   key เดิมแต่ fingerprint ต่างตอบ409 ไม่มี side effect; ถ้ามี exact receipt ให้
   ดำเนินคำขอเดิม/คืนผลเดิมโดยไม่ consume TOTP อีก ไม่ใช้เป็นสิทธิ์เพิ่ม request ใหม่
   ถ้าไม่มี receipt ต้องใช้ fresh TOTP ตาม F-06 เสมอ ไม่รับ recovery code/grace period
3. AUTH ใช้ lock order/quota/secret-version ของ F-06 เดิม consume TOTP และ INSERT
   authorization receipt ใน transaction เดียว รหัสที่ถูกใช้แล้วไม่มี receipt ต้องไม่
   ได้รับอนุญาต; crash ก่อน commit rollback ทั้งคู่ หลัง commit มี receipt ให้ lookup
   duplicate key race ต้องใช้ receipt fingerprint เดิม หรือ reject conflict ไม่สร้างสองสิทธิ์
4. API restricted intake function อ้าง receipt ที่ฐานข้อมูลตรวจ owner/mode/action/key/
   fingerprint/revision ตรงจริง แล้ว INSERT request และ UNIQUE consume-link atomic
   API role สร้าง authorization เองไม่ได้ ไม่เชื่อ authorization ID/boolean จาก browser
   worker ตรวจ receipt/link และ expected revision ซ้ำก่อนเขียน setting โดยไม่อ่าน TOTP
5. lookup อ่าน authorization/request/result ภายใต้ snapshot เดียว: AUTHORIZATION_ONLY
   หมายถึงยืนยันการกระทำเดิมแล้วแต่ยังไม่รับเข้า inbox จึงไม่มี execution; REQUEST_PENDING
   หมายถึงมี inbox รอผล; APPLIED/REJECTED มาจาก immutable engine result เท่านั้น
   by-key พบ authorization-only ได้แม้ POST ตายก่อนทราบ request ID ไม่คืน404ในกรณีนี้
6. browser เก็บ key/payload เดิมก่อนส่ง เมื่อ UNKNOWN ให้ GET by-key ก่อน หาก
   AUTHORIZATION_ONLY ให้แสดงสถานะและ retry เฉพาะ action/payload/key เดิมผ่าน
   exact-receipt branch โดยไม่ขอรหัสใหม่อัตโนมัติ; 404 ขณะ POST อาจยัง in-flight
   ไม่ใช่หลักฐานว่าไม่เคย commit และไม่สร้าง key ใหม่ การ replay ต้องมี current
   authenticated owner/CSRF เหมือน mutation ปกติ ไม่รับ receipt เป็น bearer credential
7. secret rotation/setting revision เปลี่ยนไม่ทำให้ receipt แปลงเป็นสิทธิ์การกระทำใหม่:
   exact replay คงเป็น intent เดิมที่ authorized แล้ว แต่ engine ต้อง reject revision/scope
   ที่ขัดกัน ไม่แก้ payload หรือเพิ่มเพดานตาม revision ใหม่เอง การรับ action ใหม่ทุกครั้ง
   ยังต้อง fresh TOTP ไม่มีการใช้ receipt กับ action/key/owner/mode อื่น

### Effects pagination และขอบเขต snapshot (แก้ review F18-R4)

- GET risk-limit คืน aggregate counts ที่ engine อัปเดต atomic กับ target/effect
  events ของ stop ปัจจุบัน ไม่ join คืนรายการออเดอร์ทั้งหมดหรือวนประวัติต่อ poll
  คืน target_set_complete แยกจาก counts ระหว่างค้น/enroll targets ยังไม่ครบ
  ห้ามรายงาน STOPPED แม้ pending count ที่ทราบขณะนั้นเป็นศูนย์
- effects endpoint ผูก cursor กับ owner/mode/stop ID/filter/order และ upper watermark
  ของ immutable effect event stream; keyset ใช้ target sequence/order ID ที่คงที่
  คืน target พร้อม last-known state ณ watermark เดียวกัน ไม่เพิ่มแถวจาก revision ใหม่
  ระหว่างหน้า และไม่แสดง target ซ้ำเพราะมี retry events หลายครั้ง
- เมื่อ effects revision เปลี่ยน UI เปิด pagination snapshot ใหม่ คงป้าย snapshot_at
  และแยกข้อมูลเก่าไว้จนโหลดใหม่ ไม่ประกอบ counts ใหม่กับรายการเก่าเสมือนชุดเดียวกัน
  ประวัติ stop เก่าเปิดด้วย stop ID ของเจ้าของได้ ต่าง owner/mode/ไม่พบคืน404เหมือนกัน
- ตรวจ cursor ผิด scope/shape และ limit นอก1..100 อย่างชัดเจน ใช้ safe error เดิม
  query/index เริ่มที่ owner/mode/stop/target sequence และ effect event high-water mark
  ใช้ bounded rows/typed reason codes ไม่คืน raw event history/free-text payload
  STOPPED อาศัย authoritative completeness/counts ของ targets ทั้งชุด ไม่อ้างว่าครบ
  เพียงเพราะหน้าแรกว่างหรือหน้าปัจจุบันไม่มีรายการ pending

## 5. Monitor, ordering และ safety integration

### ราคาและ idle account

เพิ่ม public price frame append ใน transaction ของ `write_price` และ feed-state
transitions เดิม ไม่เปลี่ยนการยอมรับราคา F-10 ทำให้ engine เห็น revision ที่เกิด
ระหว่างสองรอบได้ ไม่พึ่ง latest-only polling จนพลาดการชนชั่วคราวแล้วราคาเด้งกลับ
journal ไม่แตะข้อมูลผู้ใช้ และไม่สร้าง trade หรือ fill ใหม่

เพิ่ม `services/engine/risk_limit.py` และ `risk_limit_main.py` เป็น bounded fair
owner rounds แยก process จาก serial Paper matching เพื่อ account ที่ติด lock ไม่
บล็อกทุกคน; ENGINE_SCAN หางาน ENGINE owner session ประเมิน/เขียน ใช้ async
owner concurrency แบบจำกัด เริ่ม4 และบันทึก pool/limits ใน evidence ไม่มี unbounded tasks
Redis notify เป็น hint มี DB rescan/cursor recovery และ scheduler สำหรับ freshness
expiry/lease loss/5-minute alert แม้ไม่มี trade, order หรือ browser request

รับ frames ตามลำดับพร้อม position/reset source revision ที่ serialize ได้ภายใต้
wallet writer: replay frame ห้ามย้อน financial state หรือใช้ frame ก่อน reset เป็น
เหตุชนรอบใหม่ หาก sequence/proof ไม่ครบให้ unavailable และกู้ facts ที่ขาดก่อน
ให้ risk valuation กลับเป็น READY หรืออนุญาต opening/reset; reduction/cancel ใช้
deferred replay protocol ด้านล่าง ไม่รอ journal gap ถูกซ่อม
price frames/baseline references ที่ยังจำเป็นห้าม prune; prune เฉพาะ fully consumed
และไม่ถูก baseline/history proof อ้างอิงตาม existing retention policies ถ้าจำกัด
ทรัพยากรจนตามไม่ทันต้อง fail closed พร้อม backlog/dependency reason ไม่ทิ้ง gap เงียบ

SLA เริ่มที่ authoritative input transaction พร้อมให้ engine อ่านจน evaluation/latch
Paper commit <=3s (target1s; Live1sคงเดิม) ไม่ใช่เวลาที่ browser เห็น ตรวจแต่ละ decision ไม่ใช้ค่าเฉลี่ยกลบ miss
ถ้า source/monitor/cursor ไม่พร้อมหรือเกิน freshness ที่จำเป็น opening gate ต้องไม่
เชื่อ cached READY; lock timeout/DBfailure ไม่ถูกนับเป็น Passed หรือเป็นข้อยกเว้นล้าง latch

### transaction และ orders

- ใช้ owner wallet advisory lock เดิมก่อน pair catalog fences ตามลำดับ pair คงที่
  แล้ว publication fence ก่อนจับ risk/source projection rows ที่จะเขียน; publisher
  ไม่จับ owner/risk rows และไม่รอ owner lock ดู lock protocol ด้านล่าง
  TOTP verification ใช้ lock order F-06 เดิมก่อน intakeเท่านั้น engineไม่ล็อก auth
- รวมทุกคู่ที่มี held quantity และ realized history ของ financial episode แม้ catalog
  ถอนคู่หรือหน้าเว็บเลือกคู่อื่น ราคา unknown หนึ่งคู่ที่ต้องใช้ทำให้ valuation unavailable
  zero-held ใช้ realized ได้โดยไม่บังคับราคา phantom ของ pair ที่ปิดไปแล้ว
- หลัง fill/correction ใช้ transition ของ F-14 และ reevaluate risk ภายใต้ transaction
  เดียวกับ financial effects เมื่อครบข้อมูล ห้ามบันทึก fill สำเร็จแต่ทิ้ง risk revision
  READY เก่า หากข้อมูลไม่พร้อมบันทึก unavailable และ block เพิ่มความเสี่ยง
- ก่อน financial transition ใช้ atomic publication boundary ด้านล่าง ไม่ใช้เพียง
  snapshot cut ที่ไม่มี fence; opening/loss reset ต้องประเมิน frames ที่จำเป็นครบก่อน
  ทำ mutation ส่วน reduction/cancel ไม่ต้องรอ risk valuation READY หรือ drain สำเร็จ
- ที่ API intake: shared pure checker อ่าน owner snapshot/revision/price freshness
  ห้ามใช้เพียง `policy is not None` เป็น READY; observed breach ต้องมี durable engine
  evaluation request พร้อม refusal/audit ไม่เขียน latch ใน API
- bridge/F-15 admission และก่อนแต่ละ matching batch/fill: ประกอบ policy จาก current
  authoritative state ใต้ writer lock ไม่ใช้ policy object ที่อ่านข้าม transaction
  queued risk-increasing commands ที่อยู่ก่อน breach เป็น terminal rejected/canceled
  ตามชนิดเดิม คง reason/risk revision และ request→command→order links
- breach commit latch+stop request+audit atomic ก่อนเปิดทาง worker อื่น cancel orders
  consumer ใช้ F-15 cancel/checkpoint transitions กับ active orders ในขอบเขต §8
  รวม manual partial remainder; ไม่ปิด position และไม่ cancel TP/SL
- cancellation ไม่สำเร็จใช้ durable per-order retry/backoff/state ตาม §8 เกิน1นาที
  แจ้งผู้ใช้แต่ยังลองต่อ; matching/cancel race ใช้ authoritative final facts ไม่ย้อน fill
  ส่วนที่ filled แล้วไม่กล่าวว่า canceled ไม่คืน reservation ซ้ำ
- queued reduction/cancel ยังผ่านตาม contract เดิม ไม่ต้องมี loss valuation READY
  หรือ TOTP และไม่ใช้ active catalog/ขั้นต่ำออเดอร์ใหม่ขวาง cancel
- loss reset ไม่ล้าง stop effect เก่า; target orders เดิมยังถูกจัดการจนรู้ผล ยอดที่คำนวณ
  ใหม่และ future commands ผูก baseline/risk revision ใหม่ ไม่ฟื้น queued commands เดิม

### Atomic publication boundary (แก้ review F18-R1)

- เพิ่ม transaction-level advisory publication fence สำหรับ risk price source เดียว
  price/feed publisher จับ EXCLUSIVE ก่อน lease/feed/price row locks แล้ว append
  frame+เลื่อน committed publication watermark ใน transaction เดียว ถือถึง commit
  publisher ห้ามจับ owner/catalog fence หรืออ่านข้อมูลผู้ใช้ขณะถือ publication fence
- financial writer จับ owner lock และ catalog fences ก่อน SHARED publication fence
  จากนั้นอ่าน committed watermark+price view บน READ COMMITTED statement ใหม่
  ห้ามใช้ repeatable-read snapshot ที่สร้างก่อน fence จึงเห็น publisher ที่ commitก่อนหน้า
  ถือ SHARED ผ่าน financial boundary marker, risk mutation และ financial commit
- database protocol guard ต้องครอบทุก writer ของ price/feed revision ที่เปลี่ยน risk
  input ไม่ใช่เฉพาะเรียกจาก write_price เวอร์ชันใหม่; หลังเปิด protocol ใหม่ old publisher
  ที่ไม่มี publication fence/frame marker ต้องเขียนไม่ได้ เช่นเดียวกับ old financial
  writer ที่ไม่มี boundary marker สำหรับ fill/correction/baseline/episode transition
  cancelที่ไม่เปลี่ยน holdingsใช้ compatible F-15 writer-version guard โดยไม่ต้องมี
  publication boundary; ทดสอบ mixed-versionทั้งสองฝั่งและcancelก่อนเปิดadmission
- มีเพียงสองลำดับ: publisher EXCLUSIVE ได้ก่อน → financial รอ commit แล้ว consume
  frame ด้วย holdings revision เดิม; financial SHARED ได้ก่อน → publisher commit
  frameใหม่ไม่ได้จน financial commit จึงใช้ holdings revisionใหม่ ไม่มี price commit
  แทรกระหว่าง cut กับ financial commit และ frames ไม่ข้าม reset baseline ผิดรอบ
- บันทึก price watermark และ financial revisionก่อน/หลังใน risk_financial_boundaries
  atomic กับ fill/correction/reset; monitor ภายใต้ owner lock อ่าน markers เป็นเส้นแบ่ง
  ห้าม apply frameเก่ากับ holdingsปัจจุบันโดยข้าม boundary หรือถือ sequence ID ที่จอง
  แต่ยังไม่commitเป็น watermark ข้อมูลที่ rollback ไม่มี marker/cursor effect
- ทำ bounded catch-up ก่อน fence เพื่อไม่ถือ publication gate ขณะ replay backlog ยาว
  final drain ภายใต้ fenceมีขอบเขต; opening/reset ถ้าตามไม่ทันให้ unavailable/defer
  โดยไม่ mutateเงิน/baseline และ release fence ส่วน reductionใช้ protocolถัดไป
  ห้ามทำ network/retry sleep หรือจับ auth locks ขณะถือ fence การจับ fence timeout
  เป็น database transaction failure ไม่มี partial fill/สำเร็จปลอม ไม่ใช่การผ่าน risk gate
- ตรวจ contention ของ publication gate ภายใต้ Paper SLA3s/target1s และ F-10 ingestion ใน V-12/16/21
  หากแนวทางนี้พิสูจน์เกณฑ์ไม่ได้คง admissionปิดและขอ plan amendment ก่อนเปลี่ยนวิธี

### Reduction/cancel ขณะ risk replay ไม่พร้อม (แก้ review F18-R2)

- จำแนกลดความเสี่ยงด้วย authoritative holdings/reservations ตาม F-15 ก่อน ไม่ใช้
  risk valuation/journal readiness แทนหลักฐาน holdings; source holdings ที่พิสูจน์ไม่ได้
  ยังไม่อนุญาตให้เดาว่า SELL เป็น reduction
- เมื่อ holdings/execution inputs พร้อม แต่ risk frame gap/monitor down/price valuation
  unavailable ให้ bounded SELL ใช้ F-15 matching/fee/ledger/position transactionเดิม
  ไม่บังคับ drain หรือสร้าง allowance ที่คำนวณไม่ได้ก่อนส่ง/จับคู่ reduction
- ก่อน commit reduction เก็บ boundary marker ภายใต้ fence พร้อม references ของ
  immutable F-14 events และ stateก่อน/หลังที่ reconstructได้, last-known cursor และ
  missing range/proof; ตั้ง risk state UNAVAILABLE/REPLAY_PENDING atomicกับfill
  ไม่เลื่อน cursor ข้ามข้อมูลหาย ไม่สมมติ allowance0/adjusted loss0 และไม่ล้าง latch
- หลังซ่อมข้อมูล monitor replay frames+financial markers ตามช่วง holdings ที่ถูกต้อง
  rebuild allowances/adjusted realized จาก facts เดิมโดยไม่ส่ง order/fill ซ้ำ แล้วจึง
  อนุญาต opening เมื่อ freshness/proofs/stop state ครบ ระหว่างรอ reduction/cancelอื่น
  ยังใช้ contractเดิม loss resetที่ต้องใช้ฐานครบยังถูกปฏิเสธเมื่อ sourceไม่พร้อม
- cancel ที่ไม่เปลี่ยน holdings ไม่ต้องรอ risk cursor/valuation หรือ publication fence
  ใช้ owner lock/durable order facts/audit ตาม F-15 และไม่คืน reservationก่อนterminal
  failed risk replay ห้าม rollback cancelที่ยืนยันแล้วหรือขัดขวาง retry ของ cancellation

## 6. UI และข้อความ

เพิ่ม shared `frontend/src/RiskLimitPanel.tsx`, `riskLimits.ts`, `riskLimitMessages.ts`
ใช้ใน PaperTradePage และ LiveTradePage ภายใต้ mode ที่ server/route ระบุ
Live ไม่สร้าง Paper mutations และแสดง PnL/source unavailable จน reconciliation พร้อม
ใช้ TanStack Query keyed owner/mode/wallet/episode/revision ยกเลิกเมื่อ logout/unmount
หรือเปลี่ยน owner; browser hidden ไม่หยุด monitor ฝั่ง engine

แสดงตัวเลขจาก server เท่านั้น: limit, adjusted loss, baseline/allowance summary,
source/price time, latch reason และรายการ order effects/ค้าง/ล้มเหลว ไม่มี optimistic
money/latch/reset; pending≠applied และ UNKNOWN คง keyเดิมจน lookup/replayรู้ผล
order effects โหลดผ่าน bounded endpoint ตาม stop ID/watermark ไม่ใส่ทั้ง history
ใน polling query ของ risk snapshot และไม่ตัดรายการที่ยังไม่โหลดเป็นสถานะว่าไม่มีปัญหา
confirmation ของ reset บอกว่าขาดทุนเดิมถูกยกเว้นทั้งที่ยังถือไม้ ไม่ให้ความหมายว่าปิดไม้
INCREASE มี TOTP prompt ผ่าน auth headerเดิม; reset/decrease ไม่มี TOTP เพิ่ม
alert พัก5นาทีแยกจาก market warning60s และ breach/cancel issue ไม่รอครบ5นาที
ไม่สร้าง notification center หรืออ้างว่าส่ง Email/Telegram/LINE แล้ว

## 7. Milestones และการตรวจ

| Milestone | ขอบเขตและ checkpoint | Validation |
|---|---|---|
| M1 | pure domain/reset allowance/correction replay/parity และ hand oracles | V-01..06 |
| M2 | additive migration/RLS/audit/commands/TOTP/replay/API contracts | V-07..11 |
| M3 | durable price frames/monitor/transaction fences และ order-stop consumer/recovery โดย production ยังปิด | V-12..17 |
| M4 | shared UI ไทย/อังกฤษ/template/UNKNOWN และ isolated production-composition browser→engine harness | V-18/19 และ affected frontend/API checks |
| M5 | แจ้ง **Ready for Code Review** พร้อม changed parts/tests/pending/risks ก่อน review; แก้ findingsและตรวจ final candidate ครบ ก่อน merge ตามเจ้าของสั่ง | V-20 |
| Release / activation | integrated workload W1–W4 และ Paper SLA3s/target1s บน final composition/schema; dependency checklist และ explicit activation evidence ไม่ทำท้ายทุก milestone | V-21..23 |

ทุก checkpoint ใช้ `evidence/mN-*.md` ต่อเนื่อง บันทึก diff, commands/results/environment,
revision, งานค้าง และเวลาที่วัดได้แยกอ่าน/เขียน/ตรวจ/รีวิว/รออนุมัติ ไม่อ้างเวลาที่ไม่ได้วัด
ไม่รัน full suite ทุก patch หรือ timed smoke ท้าย milestone โดยอัตโนมัติ

## 8. Rollout, risks และข้อจำกัด

1. เพิ่ม schema/grants/price journal โดย production risk opening ยังปิด โค้ดเก่าที่ไม่
   สร้าง proof/frame ไม่ทำให้ source ใหม่ READY ไม่ auto-adopt risk baseline จาก balance
2. deploy engine/monitor/cancel consumer และตรวจ writer version/fences ก่อนเปลี่ยน
   API composition; old worker ที่ไม่รู้ risk fence ต้องทำ fill/correction/baseline/
   episode transition ไม่ได้ ผ่าน DB writer-version guard เดิมที่ขยายแบบ additive
   และ tested rolling upgrade; compatible cancellation pathยังเขียนterminal facts/
   release reservationsได้โดยไม่ต้องผ่านrisk replay/publication boundary
3. ไม่ใช้ migration ตั้งเพดานหรือปลด latch ของผู้ใช้เดิม ไม่มี silent baseline reset
   มี setting แต่ sourceยังไม่initialized ให้ unavailable จน writerเดิมพิสูจน์ authority
4. เปิด Paper เฉพาะ V-18/19/21 ผ่านและ review/candidate gates พร้อม dependencies
   ในขอบเขตที่จะเปิด ถ้ายังไม่ผ่านให้ mergeเพื่อพัฒนาต่อได้ตาม testing แต่คง admissionปิด
   ห้าม rollback ไป workerเก่าที่ข้าม risk; ปิด opening แล้วใช้ compatible cancel/read path
5. ความเสี่ยงหลัก: allowance ถูกใช้ซ้ำหลัง partial/correction, price ordering ข้าม reset,
   missed transient breach, mixed-version writer, stale API readiness, TOTP TOCTOU,
   cancel/fill race และ resource backlog ต้องมีหลักฐานตาม validation ไม่เพิ่ม refactorนอกงาน
6. F-19/F-20 bot lifecycle และ F-26/F-36/F-27 notification dependencies คง pending
   ไม่เรียก F-18 Completed/รับรอง Live จน validation/dependenciesครบ

การอนุมัติ plan นี้รวมแนวทาง persistence/monitor/API/rounding ข้างต้น ไม่อนุญาต
เปลี่ยนคำตัดสินเงินของ requirements หากพบว่าแนวทางทำไม่ได้ให้เสนอ amendment ก่อนแก้โค้ด

## 9. Checkpoint ขั้นเอกสาร — 2026-10-25

requirements/NC-F18-01..08 Approved ตามคำตอบ “approve” แล้ว plan/validation
ฉบับนี้ยัง Proposed รออนุมัติแยก ไม่มี runtime implementation หรือ Git commit/push
ตรวจเฉพาะเนื้อหา/source reuse/relative links/whitespace ตามผลกระทบเอกสาร
application tests ยังไม่รันและ validation ทุกข้อยังเป็น Not Run/Pending ตามตาราง
เวลาอ่าน/จัดทำ/ตรวจเอกสารรอบนี้ไม่ได้จับเวลา จึงไม่รายงานเป็นค่าที่วัดได้

### แก้ deep-review findings — 2026-10-26

| Finding | การแก้ในแผน | หลักฐานที่ต้องเพิ่มใน validation |
|---|---|---|
| F18-R1 High | publication SHARED/EXCLUSIVE fence และ atomic financial boundary แทน cutที่ปล่อยpricecommitแทรกได้ | V-13/16: publisherก่อน/หลังfill/reset, rollback/kill และ holdings revision oracle |
| F18-R2 High | แยก opening/reset preconditions จาก reduction deferred replay; cancelไม่รอriskcursor | V-14/16/17: riskgapแต่holdings/bookพร้อม ลดได้และrebuildไม่duplicate |
| F18-R3 Medium | AUTHORIZATION_ONLY lookup และ middleware exact-receipt replay; receiptกับTOTPconsume atomic | V-08/09/19: crashหลังAUTHcommitก่อนinbox, concurrent/mismatched replay |
| F18-R4 Medium | snapshotมีcountsเท่านั้น effects endpointจำกัด1..100/keyset+watermark | V-10/18/21: หลายหน้า/ข้ามowner/updatesระหว่างหน้าและresponsebounds |

เป็นการแก้เอกสาร Proposed ยังไม่มี runtime implementation หรือผล tests ที่ผ่าน
requirements ที่อนุมัติแล้วคงเดิม plan/validation ฉบับแก้ต้องอนุมัติก่อนเขียนโค้ด


### เริ่ม implementation — 2026-10-26

เจ้าของอนุมัติ plan/validation ฉบับแก้ F18-R1..R4 ด้วยคำตอบ “approve” และสั่งทำต่อ
จนผ่านเกณฑ์ รวม full regression/final review และ workload ทีละชุด ไม่รัน diagnostic ซ้อน
checkpoint ขั้นเอกสารก่อนหน้านี้เป็นประวัติ ไม่ใช่จุดอนุมัติที่ยังค้าง
เริ่ม M1 domain/hand-oracle/property/parity ก่อนเชื่อม persistence ใน M2
ผล validation ยังไม่เปลี่ยนเป็น Passed จนมีหลักฐานจริง และ production admission คงปิด

### การปรับเวลา validation ที่อนุมัติ 2026-10-27

ใช้ integrated profileV2 ตาม validation§5: W1/W2/W3 เป็น600/300/1800s
โดย reuse `tests.infra.execution_market.profile_workload.endurance_rss` พร้อม
explicit duration สำหรับ F-18 เท่านั้น ค่าเริ่มต้น4ชั่วโมงของ F-15คงเดิม
ใช้ `backend/tests/infra/risk_limits/w3_fault_schedule.json` สำหรับ fault7ครั้ง
ชนิด/ความรุนแรงเดิมภายใน30นาที ไม่ลดโหลดหรือเกณฑ์ safety/SLA/resource
ไม่ถือว่าผล Failed/Partial เดิมผ่าน และไม่เปลี่ยนวิธี publication fence/lock order

### F18-R5 — Approved 2026-10-27

Owner instructed to proceed after reviewing [R5](publication-fence-amendment.md).
This incorporates its complete protocol and validation conditions before further
implementation: bounded owner replay and pure preview before publication fence;
BUY order-state changes/fills require a fenced fresh resolution and recomputation
from the pre-input state at current time before any authoritative effect.
No-op input may proceed without that fence; admission and SELL financial boundary
protocols remain unchanged. Cache only actually fenced context, invalidate on fill.
Preserve every committed frame/transient breach, existing safety/SLA thresholds,
serial scheduling and resource limits. NC-F18-09 is closed.

R5 implementation reuses `infra/paper_orders/worker.py` recovery with
`infra/market_data/order_book_storage.py::{read_latest_book,read_inputs}`.
The recovery batch contains the verified rebase snapshot and at most19 contiguous
inputs committed after it (20total). This fixes repeated rebase discarding a
fresh post-snapshot maker trade when an owner is slower than one second.
It preserves F15 requirements recovery/FIFO/consumption/provenance rules: no
fill from the missing interval, no synthetic liquidity, unchanged freshness,
and a gap/corrupt provenance still fails closed. Exact partial-fill financial
oracle is in `tests/infra/risk_limits/test_matching_recovery.py`.

Monitor implementation tuning within the same replay protocol: retain the bounded
owner-lock wait and fair retries with the same four monitor slots; capture
watermark with the owner-state statement and reuse the last verified frame within
that transaction. The nonblocking owner-lock experiment was reverted after loaded
progress evidence. A bounded256-entry decode cache may reuse immutable
public frame values keyed by id/time/proof/payload text, only after each SQL read
checks completeness/order/checksum. This caches no owner book, evaluation, READY,
authorization or financial result and does not skip/coalesce any frame. Missing
or corrupt rows must fail even when a decoded value was cached previously.

For release measurement, mirror the already separate Compose risk service rather
than putting it in the same CPU quota group as all ten Paper workers. Keep the
aggregate app budget4CPU/2GiB: risk1CPU/512MiB, API/Paper3CPU/1536MiB, PG4CPU/3GiB
unchanged. Same process counts/pools/roles/domain code; share PID namespace solely
so the existing sampler includes every runtime's CPU/RSS. Record topology and
runner hashes in manifest. Risk container receives only ENGINE/SCAN credentials.
Baseline refusal polling reuses existing F15 quarter-second cadence; the measured
retry cadence remains20ms, and measured command/input rates and oracles unchanged.

Apply the existing bounded catch-up/final-drain protocol to a monitor publishing
current READY as well: historical replay/source proof before the publication
fence, then a bounded tail under the compatible shared fence through commit.
`final_publication_fence` is opted into only by the monitor scheduler. Financial
callers keep the original full fence; reduction callers keep their nonblocking
default. Count both replay stages against the same frame budget; do not skip
transient breach/recovery. This prevents a perpetually stale READY marker when
publication advances between the first watermark snapshot and its commit.

Checkpoint projection writes upsert the current pair once and advance other
pairs' global revision in a disjoint writable CTE, preserving the same final
data/replay facts. API refusal backpressure in the harness polls a read-only
readiness hint without taking the owner lock; every intake still reruns the full
fresh production policy. All positive five-command cycles remain bounded60s,
including the existing F18 scenario; no progress deadline/acceptance gate raised.

### F18-R6 — Approved 2026-10-27 before implementation

Owner explicitly approved [R6 API price catch-up](api-price-catchup-amendment.md).
Incorporate its complete scope/conditions/tests: API-only bounded read-only replay
of up to100 price frames, only with complete non-pending financial snapshot and
all financial boundaries replayed; same core evaluator and strict frame validation.
Any observed transient breach refuses and queues the existing durable hint; API
never writes latch, allowance, stop or financial facts. GET Paper snapshots use
consistent read transactions and the same pure checker; no GET mutations.
ENGINE default evidence/matching/financial protocol remains unchanged and fully
fenced before money changes. No change to limits/formulas/resources/rates/SLA or
60s progress bound. Close NC-F18-10; retain old Failed/Partial and pending gates.


## R7 — smaller interleaved runtime rounds (Approved2026-10-27)

Owner explicitly approved [R7](worker-round-amendment.md) before implementation.
The F18-integrated runtime alternates one manual candidate and one matching
candidate, then the same20ms tick. Reuse existing bounded fair due/claim/process
functions and all owner/CAS/lease fences. Define one runtime round limit and use
it in production entrypoint and F18 workload workers; record both phase limits
in the manifest. F15 function/harness defaults remain20. No new dispatcher,
financial decision/price protocol/schema/roles/resource budget/rate/test threshold.
Validate affected safety/composition, then the same60s selected-owner cycle with
source-continuous fixture trade IDs; only after progress proof run W1→W2→W3
sequentially. Keep Failed/Partial history. W4r8 remains valid unless a new restore
contract impact is identified. If the approved scheduling experiment does not
help, revert it and retain failed evidence before proposing another method.


## R8 — bounded hint fallback and one claim per phase (Approved2026-10-27)

Owner explicitly approved [R8](claim-budget-amendment.md) before implementation.
Supersede R7's one-candidate selection with20candidate hints and1successful claim
per phase. Reuse existing ordered due/claim/CAS/owner/lease functions; a None
claim consumes no claim budget, while a claimed item consumes budget even if it
later defers/fails/loses its claim. At most20hints are considered; no unbounded
loop or in-transaction retry. Existing other-owner FIFO/fairness and untouched
candidate schedules remain. Round-function/F15 standalone defaults stay20/no
additional claim budget. Production/F18 harness explicitly use20/1 and record
both limits. All workers/pools/CPU/RAM/rates/60s/SLA/replay/financial gates remain.
Check affected selector/supervision/claim/safety contracts, then repeat the same
counter probe sequentially before fullW1→W2→W3. Keep all Failed/Partial evidence.


## R9 — same-pair dispatch (Approved2026-10-28)

Owner explicitly approved [R9](same-pair-dispatch-amendment.md) before code.
Incorporate its complete scope/guards/validation. Reuse due_orders/claim_order,
_process_new and reschedule_processed_orders: original owner head anchors fairness;
only an eligible earliest unfinished NEW of the same episode/pair may replace an
already-admitted active resting poll. Due CANCEL disables preference. READY and
configured/unlatched/nonpending hints are scheduling only; ENGINE rechecks facts
under owner lock/CAS before claim, then existing full financial/risk gates remain.
Persist at most one preference per original(command_id,next_attempt_at) atomically
with the candidate claim. If no actual covered-work reschedule advances that
anchor, next selection falls back to original head, including failure/crash/ack
loss. No extra claim, network/transaction retry, skipped input, merged financial
event, altered matching FIFO/eligible_at/fee/quantity/UUID or risk protocol.
Add only reconstructible routing projections/guard to dispatch, updated atomic
with canonical facts/status transitions; UNKNOWN/stale hints fall back. SCAN gets
routing/status columns only, no payload/amount/book/secret or write privileges.
Production/F18 explicitly enable the selector option; F15 standalone defaults
remain unchanged. Keep20hints/1claim,10+1workers/pools/tick/CPU/RAM/rates/60s/SLA
and financial/resource gates. Check migration/rolling overlap/affected restore,
selector fairness/CAS, cancel/reduction failure/crash/stop races and financial
oracles, then unchanged60s progress and W1→W2→W3 sequentially. If it does not
help, disable the option back to R8 and retain failure evidence. No new approval
needed for these authorized steps; any different method still needs amendment.

R9 maintenance refactor requested by owner2026-10-28: reuse the existing
`alembic.op.execute`/static-table loop pattern (0053/0056), with one local list
for0056scanner hint column grants and one for routing-refresh trigger tables.
Upgrade/downgrade reference the same lists; rename private routing SQL fragments
for clarity. No new abstraction layer, selector method, emitted SQL, ordering,
permissions, schema or financial behavior; option remains disabled. Verify
expanded migration/runtime SQL equivalence, existing real-DB R9/legacy dispatch
safety and relevant lint/types; reuse unaffected full/workload evidence.


## R10 — bounded admission-priority rounds (Approved2026-10-28)

Owner approved [R10](admission-lane-amendment.md) before code. Incorporate all
its guards, limits and validation. Reuse0056routing metadata and existing
`routing.py` same-pair predicates/`dispatch.py::claim_order` canonical proof,
CAS and atomic guard without financial changes. A distinct admission-first
option orders preferred heads before ordinary heads before the20hint cutoff;
legacy/R9 defaults unchanged. A small engine `matching_round_modes` iterator
uses standard-library cycle/repeat and is shared by production/harness, starts
R8 and alternates before each attempted native round independent of result.
No new scheduling framework/worker/schema. Explicit runtime/harness flag stays
off until affected safety passes; then uninstrumented frozen60s progress and
fresh W1, only on pass W2→W3. If it does not help, disable back to R8 and retain
failures. Preserve all budgets, rates, deadlines, financial gates and pending
dependencies. No repeated approval needed within this scope.

## R11 — bounded source-resumption probe (Approved 2026-10-28)

Owner approved [R11](source-resume-amendment.md) before implementation. Incorporate
its one-probe/failure-streak, unchanged ordinary backoff, original due and bounded
lease requirements. Reuse `routing.py` owner heads and same-pair candidates,
`dispatch.py` owner lock/claim CAS/defer/finish, and native source/financial gates.
0057 adds only wait/probe metadata plus narrow scanner publication grants. A
BEFORE UPDATE OF attempts trigger clears this metadata when existing healthy
finish/covered-pair reschedule writes attempts=0; this keeps old/new writer reset
behavior atomic and default-off SQL compatible with0056. No financial payload
projection or alternative execution path. Explicit runtime/harness mode starts
off; affected safety and controlled comparison precede candidate qualification.
Keep all failed/partial evidence and the unchanged acceptance budgets/dependencies.

R11 rollout review: upgrade treats pre-existing attempts>0 as an unknown probe
history and consumes the optional guard conservatively until the existing healthy
attempts=0 checkpoint. This prevents downgrade/re-upgrade from granting a second
probe in one failure streak. The metadata-only backfill uses the existing
migration pattern: exclusive NOWAIT lock, temporary NO FORCE RLS for the owner,
then FORCE RLS restored atomically. No ordinary retry schedule is changed.

Implementation note (2026-10-28): source-lease SQL roundtrip reduction reuses
`backend/src/tiewtrade/infra/market_data/order_book_storage.py::_locked` and
`backend/src/tiewtrade/infra/market_data/realtime_storage.py::_locked`.
A MATERIALIZED locked-row CTE followed by outer clock_timestamp preserves the
post-lock DB-clock check within one SQL statement. The existing separate price
publication fence still precedes the feed-row lock; owner/generation,5s leases,
final checks and retry/publication methods remain unchanged. Actual row-lock
expiry, mutation rollback and financial publication ordering are regression gates.

## R12 — independent fixture publication (Approved 2026-10-28)

Owner approved independent-fixture-publication-amendment.md. Fixture reuses
f15.acquire_sources/publish_market(update_price=False), native price writers and
existing market pool; two serial source loops supervised by Fixture.publish.
Book stats and price frame evidence are separate; startup waits for both sources.
Failure/cancellation joins both tasks. No resource, freshness, retry, financial
fence, scenario or workload acceptance threshold change. Application defaults
remain unchanged. Added real-fence progress and task cleanup/price-gap tests.

## R13 — pending intake replay deferral (Approved 2026-10-28)

Owner approved intake-replay-pending-amendment.md before implementation.
`infra/paper_orders/request_worker.py` returns explicit RequestOutcome.DEFERRED
only for configured, unlatched, same-scope/manual owner pending price replay,
with matching evaluation cursor/revision and active protocol/catalog. The engine
holds existing owner/publication locks. A successful bounded replay records its
cursor in the evaluation; exception fallback records the captured watermark, so
that fallback is excluded by cursor<current and evaluation-watermark=cursor.
Reuse require_request_claim/defer_request_claim: commit replay progress and normal
claim backoff atomically, without immutable result or native command. Service
manual_order counts this as deferred; previous processed paths retain behavior.
Breach/queued stop, wrong use, missing policy, unset limit, removed catalog and
non-pending failures retain refusal behavior. No extra claim, retry schedule,
source gate or financial rule. Reuse catalog validation helper for both paths.

Implementation note (2026-10-28): reuse existing request_view's joined owner/order
status when observing NEW completion in the integrated harness. Require both
SUCCEEDED command and exact expected order status before returning, retaining
canonical command read and later partial-fill completion proof. This eliminates
a duplicate wait_status transaction for an already observed state; no execution,
retry, publication, workload deadline or commit-timestamp SLA gate is changed.

## R14 — standalone captured-watermark monitor (Approved 2026-10-28)

Owner approved monitor-captured-watermark-amendment.md before implementation.
Standalone scheduler reuses replay_monitor(publication_fence=False) without its
optional final drain. Existing owner lock/immutable ordered frames/boundary and
frame budgets/cursor commit remain; later publications wait for next round.
Financial writers/reset/matching/bridge retain full fenced replay. R6API tail
verification remains unchanged. Tests reuse existing transient breach and fence
contracts; new actual scheduler test proves commit behind advancing publisher
then consumption on next round. No resource, SLA, retry or financial-rule change.

## R15 — nonblocking bounded monitor sweep (Approved 2026-10-28)

Owner approved nonblocking-monitor-sweep-amendment.md before implementation.
Reuse existing owner namespace and pg_try_advisory_xact_lock pattern; shared
private owner-lock helper keeps blocking callers' behavior/defaults unchanged.
Standalone monitor defers without owner reads/mutations when try-lock fails;
service requests limit100 while retaining semaphore/pool4 and20ms post-round
sleep, cursor ordering and replay budgets. Tests prove untouched busy-owner state,
next-owner progress, original owner recovery and four-slot bound at limit100.
No financial caller opts into nonblocking acquisition; other fences/rules remain.

### R16 — Approved standalone batched read snapshot (2026-10-28)

Owner approved [R16](monitor-read-snapshot-amendment.md) before implementation.
Reuse exact F14 position SQL and decoder, risk frame proof/decoder and owner
setting decoder; same replay loop consumes transaction-local captured inputs.
Only standalone scheduler uses this path, after its blocking owner lock.
Financial writers/API keep existing readers and fences. Resources/gates unchanged.

R16 experiment failed its comparison and was rolled back per its terms.
Original standalone read path restored; approved R14 remains active.

### R17 — Approved immutable execution-input decode reuse (2026-10-28)

Owner approved [R17](execution-input-decode-amendment.md) before implementation.
`order_book_storage.read_inputs` keeps fresh state/rows and all original proof
checks; a256-entry exact payload+capability-text cache reuses only public immutable
decoding and canonical digest derivation. Existing codecs and Money/Quantity are
unchanged. No owner/financial/readiness cache, scheduling or resource changes.

Equivalent standalone setup I/O consolidation (2026-10-28): reuse db.session
_begin/_assert_role and the indicator session's scoped set_config pattern.
Actual role verification still precedes SET LOCAL in a separate statement.
Optional owner-lock parameters combine existing user/timeouts/lock preparation
without changing transaction boundaries or default callers. The R16 snapshot
path reuses its already-held owner lock; financial callers still acquire theirs.
Current experimental composition uses R15's bounded100/four-slot page with
original blocking100ms acquisition, R16 reads and R17 public decode. All earlier
Failed results remain; full validation/admission gates remain closed.

The optional session setup batching experiment failed and was fully reverted.
Current candidate retains original db.session and blocking100ms acquisition,
page100/four slots, R16 batched read and R17 public decoding. All diagnostic
failures are preserved. R18 monitor-concurrency-amendment.md is Proposed only;
no pool/concurrency ceiling change before owner approval.

### R18 — Approved monitor concurrency/pool8 (2026-10-28)

Owner approved [R18](monitor-concurrency-amendment.md) before implementation.
One service constant bounds concurrency and sizes/warms the standalone monitor
pool8 (max_overflow0); main passes the same bound to the scheduler. Existing
direct callers default4. Request1/stop2/scan3 pools unchanged. Page100, owner
lock100ms/statement700ms,20ms sleep, CPU/RAM/process counts and all gates remain.
The four additional possible DB connections are an explicit approved change.

### R18 experiment outcome (2026-10-28)

R18 approved8-slot experiment did not establish SLA headroom; both sequential
comparisons failed. Per rollback condition, runtime monitor pool/warming/in-flight
transactions now use risk_limit_main.MONITOR_CONCURRENCY=4. Bounded explicit8-slot
scheduler capability/tests remain dormant. No further resource/retry change is
approved by this outcome. Evidence and pending gates: `evidence/m5-final-candidate.md`.

### Evidence-first Paper validation closure — Approved 2026-10-28

Owner explicitly requested implementation of the five-stage closure plan:
correlate existing evidence, collect only missing timing, fix a proven bottleneck,
pass affected safety/preflight, then sequential W1–W4 and final regression/review.
Retain actual production flags, monitor4 and all SLA/resources/financial gates.
Reuse proven-valid evidence; invalidate affected workload results after runtime
changes. No overlapping workloads/diagnostics, speculative tuning, or repeated
runs without a new reason. V22/V23 remain Pending Dependency. Detailed execution,
coverage matrix and blockers stay in evidence/m5-final-candidate.md. New methods
still require amendment approval; this workflow does not preapprove one.

### R19 — Approved 2026-10-28

Owner approved monitor-page-order-amendment.md before implementation. Reuse
services/engine/risk_limit.py::run_risk_monitor_round: original eligibility,
UUID-selected page and next_owner preserved; only execution list is stably ordered
by selected due_at(NULL first). Runtime4; no retry/resource/schema/financial change.
Safety and comparison outcomes remain in evidence/m5-final-candidate.md.

R19 outcome: both comparisons failed; per approved rollback terms, original
UUID execution order and scanner projection restored. Runtime4; no R19 code is
active. R20 is a separate Proposed amendment, not authorized implementation.

### R20 — Approved 2026-10-28

Owner approved pending-price-monitor-amendment.md before implementation. Migration
0058 grants scanner SELECT(cursor)/SELECT(watermark) only; apply migration before
new runtime. Existing UUID page/cursor/due/NULL/hints unchanged, with committed
watermark-ahead as one additional scheduling hint. Actual work retains owner RLS/
lock and all replay/financial checks. Runtime4, R9/R10/R11off. Safety and decision
comparison in evidence/m5-final-candidate.md; no automatic activation or completion.

### Approved-method composition: R19 with R20

R20's original-order baseline improved eligibility but native verification still
failed30/60300inputs with no missing acknowledgements. Correlated R20 trace shows
an owner missing a just-before-publication scan and then placed last in the next
page, retaining the precise within-page delay R19 addresses. Re-evaluate the
already-approved R19 stable due_at order under the now-approved R20 eligibility;
no new method/grant/resource/retry. R20 first started from restored original order
as specified; its baseline failure is retained. Original page membership/cursor
remain authoritative; only execution order changes exactly as R19 authorized.
This does not erase R19-alone failure or preapprove another selection method.

### Approved R21 — composed monitor capacity trial (2026-10-28)

Owner approved [R21](composed-monitor-capacity-amendment.md): reuse existing R18
8-slot capacity with active R19/R20 scheduling, changing only native monitor
concurrency/pool from4to8. Existing request/stop pools and CPU/RAM/financial/SLA
contracts remain unchanged. One same-instrumentation full-cycle comparison;
revert4 if the proven queue bottleneck fails to improve or safety/progress fails.
This expressly supersedes R20's four-slot constraint for the bounded R21 trial.
Evidence and subsequent gate decisions stay in the M5 checkpoint.

### Approved R22 — replay-local valuation (2026-10-28)

Owner approved [R22](replay-local-valuation-amendment.md). Reuse existing
evaluate_risk arithmetic and latch_risk in a lazy bounded core iterator; its
loss memo exists only for one immutable book and ≤100frames. Infra _evaluate_frames
consumes one decision at a time and keeps the existing persist/transition path.
Every frame checks source/price validity and readiness at its own timestamp.
No Money/Quantity/shared F14 changes, global cache, public API or schema changes.
Parity/safety and deterministic comparison precede native qualifying preflights.

### Superseded Paper two-second timing revision (2026-10-28)

เจ้าของอนุมัติเกณฑ์ Paper every-ready-input <=2s โดยต้องพิสูจน์จาก tests;
คง1sเป็นtargetและนับจำนวนเกิน1sแยกจากhard misses>2s. ปรับเฉพาะ workload
oracle/ขอบเขตtestsและเอกสาร ไม่เปลี่ยน production financial checks, resources,
โหลด, F15 command latency, duration, Live1s หรือ stop completion contract.
เก็บผล Failed เก่าทั้งหมดและไม่รับรองชุดเต็มจาก diagnostic/preflight เดิม

### Paper three-second timing revision (2026-10-28) — superseded by R25

เจ้าของเปลี่ยนhard boundจาก2sเป็น3sต่อทุก ready input ของPaper; target1s
คงเดิม. ใช้oracleเดิมนับtarget misses>1sและhard misses>3sแยกกัน พร้อม
max/distribution/unacknowledgedครบ. เปลี่ยนเฉพาะspecและtest harness threshold
ไม่เปลี่ยนproduction financial runtime, Live1s, F15commandlatency หรือทรัพยากร

### R23 — approved financial policy final-tail replay (2026-10-28)

Owner approved [R23](financial-replay-tail-fence-amendment.md). Configured Paper
BUY resolve/execution_context may prepare bounded historical replay under owner
lock before acquiring the existing shared publication fence for the complete
final tail and commit. This supersedes the monitor-only restriction for these
two policy callers only; unfenced preview remains unfenced, all other financial
callers/defaults retain their protocol. No authorization/mutation before full
fenced evidence. Existing100framebudget, freshness, latch, controls, boundary
markers and all acceptance/resource gates unchanged. Follow R23 safety barriers
and one controlled comparison; roll back if evidence does not support the change.

R23 experiment outcome: unsupported; rolled back to the original fully fenced
financial policy after the single controlled diagnostic. The opt-in described
above is not active. See R23 outcome and M5; retain failures and do not repeat
this configuration unchanged. No acceptance gate is marked passed by this trial.


### Approved Paper processing latency revision — 2026-10-29

เจ้าของอนุมัติปรับ processing p95 เป็น **<=500ms** สำหรับ F-18 Paper integrated
profile `F18_F15_F16_INTEGRATED_V2` เท่านั้น แทนเกณฑ์ที่สืบทอดจาก F-15 <=250ms.
Processing วัด transaction รวมการรอ connection/lock และ commit ตาม instrumentation
เดิม ไม่ใช่เวลาตั้งแต่ส่งคำสั่งจน fill. คง p99<=1s, Paper ทุก ready input<=3s
(target1s), 100owners×20orders, rates/resources, command deadlines, W1–W4 และ
financial correctness/retry/idempotency ทั้งหมด ไม่เปลี่ยน F-15 standalone หรือ
Live criteria. เก็บผล Failed/Partial เดิม ไม่เปลี่ยนผลย้อนหลังเป็น Passed;
ต้องมีหลักฐาน candidate ใหม่ผ่านเกณฑ์ทั้งหมดก่อนรับรอง Paper validation.


### R24/R24-A — Approved 2026-10-29

Owner instructed implementation of [bounded monitor retry and explicit rollback outcome](bounded-monitor-retry-amendment.md). Reuse run_risk_monitor_round, lock_risk_owner and user_session paths named there; opt-in cleanup confirmation only for standalone monitor. Retain the amendment budgets, safety gates, single matched experiment and rollback rule.

R24/R24-A outcome (2026-10-29): single experiment failed risk/resource gates;
rolled back both scheduler retry and opt-in DB cleanup changes. They are inactive.
Retain failed evidence and the unrelated-to-runtime F18 test-isolation corrections;
no acceptance or Completed claim. See M5 and amendment outcome.


### R25 — Approved acceptance revision (2026-10-29)

Implement [R25](paper-acceptance-flexibility-amendment.md), superseding Paper3s
hardgate with per-owner/global99.9%<=3s plus everyinput<=5s; keepLive1s.
Reuse sla_summary input/ack streams and F15 resource_sampler; onlyF18verdict changes.
Add test-harness actual-pool evidence with SQLAlchemy checkout/checkin events,
premeasurementinventory/serverheadroombudget and postshutdown5scleanupquery.
No extra SQL inside financialtransactions. Parent/Paper/riskfactorywrapping records
actual enginepooloptions; remove wrappers/listeners onexit. W3generations must match
frozeninitialinventory. Preserve all oldFailedresults; no R24runtime reactivation.


### R26 — Approved recovery-scenario timing (2026-10-29)

Owner approved [R26](recovery-scenario-budget-amendment.md). Supersedes the60s
inclusive selected-scenario bound only: ordinarycycles andnormalelapsedexcluding
onlyone recordedbreach_reset phase remain<=60s. Thatphase alone<=120s; selected
firstcycleouterguard<=180s. Innerstop30s/price10s/request60s,load/rates/counters,
R25risk/processing/resources,financialchecks andfinalelapsed/drainboundsunchanged.
ReuseF15scheduler withoptionaltest-onlycyclecontext,default60s unchanged; F18
tracksoneeligiblephase and itsstages/20reseedidentities usingmonotonic time.
No productionAPI/schema/pools orruntimechanges. OldFailedresultsnotrelabeled;
targetedbudget/default/cancelcontracts beforeonenativeW1,stoponfailure/noautoretry.


### R27 — Approved explicit under-load RESET schedule (2026-10-29)

Owner approved [R27](declared-reset-workload-amendment.md). Remove extraendRESET
frompositivecycles; keep5tradingcommands/60s,R26one120srecovery/180stotal and
selectedcorrection. Add100scheduledRESETs/run,one/owner,<=1/s,from180s,selectedlast,
withdeclaredfault-awareoffsets. Requireselectedrecoverycompletebeforefirstoffer;
noautoextension. EachRESET60sincludingAPIpoolwait;independentcounters/IDs/timing,
all100completebyexistingduration+60s;noalteredpositivecounts/rates/durations.
DoesnotcertifyRESET20/s or100simultaneousRESETs,notaproductionratelimit.
R25/financial/authorization/resource/poolgates unchanged;oldFailedretained.
ReuseFixture.mutation/F15FaultGate/producer-supervision andoracles. Serialize only
per-ownerfinancial-marker evidence reads/cursorupdates whenRESET andfillsrecord
concurrently; no newfinancialwriteSQL/locks. CHECK is nonaccepting anddoesnot
substituteitsreducedownerfixtureforthe100RESETacceptanceprofile.


R27 fixture restoration detail: selectedowner temporarilyuseslimit5 forbreach/reset/
correctionoracles. Afterthoseanditsfirstfive-commandcyclecomplete,restoretheexisting
standardfixturelimit1000 viaoneexplicitINCREASEreceiptwithF-06/AUTHauthorization,thenmarkrecoveryreadyforproducer.
RecordthisoneINCREASE separately from100scheduledRESETs;noneofthethreshold5oraclesmove
oruse1000instead. Thisrestoresnormalpositive-fixtureconfiguration afterthetest,
withoutchangingdomainrules/productionlimits oraddingper-cycleRESETs. Itsreceipt
mustbeAPPLIEDandrecordedbeforeacceptance. KeepthisinsideR26normalbudget.

R27-A approved 2026-10-29 (owner: เริ่มทำ): restoration uses F-06 verified AUTH
authorization and INCREASE, not SET. One AUTH pool size1/overflow0 is added to
the complete parent inventory (6 pools, capacity +1), disposal and cleanup.
All other R25/R26/R27 gates remain unchanged. See declared-reset-workload-amendment.md.


### Approved bounded memory diagnostic — 2026-10-29

Owner explicitly requested implementation of the RAM-budget plan. Freeze current
R10/R22, monitor4 and allocations. One diagnostic only: native100x20 setup then
60s observation using the existing W1 dataset/rates/scheduling, not W1 acceptance.
Opt-in internal --memory-diagnostic-seconds60 collects VM meminfo/vmstat/PSI and
Docker actual memory usage/limit/cache/anon/optional swap/OOM state at roughly2s
intervals, alongside host paging and existing publication commit timestamps.
Collector failures/OOM and existing workload rejections/timeouts stop the run.
At60s cancel/join pending work and mark WINDOW_COMPLETE/acceptance_result=false;
that cutoff is not proof of complete cycles, financial gates or RESET coverage.
No added SQL in financial transactions, production code, allocation, API or schema
changes. Run sampler/cancellation tests and related static checks before the one
run. Record actual RAM versus limits and uncertainty; stop with one proposal or
specific missing evidence. No W1-W4, allocation changes or automatic repeats.


### Approved single VM-memory experiment — 2026-10-29

Owner instructed เริ่มทำ after the3072MiB VM-memory proposal. Authorizes changing
only Docker Desktop VM Memory to3072MiB, with prior actual control value recorded
for rollback. Per-container CPU/RAM/pools and R25/R26/R27-A financial gates unchanged.
One fresh100x20/60s diagnostic using the same sampler/source as the previous RAM
run; no W1-W4 or repeats. Record new effective VM memory/configuration and compare
aligned phases/counter rates. Roll back if guest pressure/source behavior worsens.
No claim of causal fix/acceptance from one short trial.


### Approved VM3GiB full W1 attempt — 2026-10-29

Owner instructed เริ่มทำ after the proposal for one full10min W1 on VM3GiB.
Accept this VM envelope for this attempt: UI3GiB, effective Linux MemTotal
3,043,373,056bytes; per-container CPU/RAM/pools, R10/R22/monitor4 and all R25/
R26/R27-A gates unchanged. Fresh0058DB,100owners x20orders,10commands/s,600s,
100 scheduled RESETs and selected restoration/oracles fully required. Native
acceptance invocation with no diagnostic cutoff/flags. Preserve source/config
and all failed historical runs. One W1 only; stop on failure, no automatic retry.
No W2-W4 in this attempt; report W1 evidence before progressing.


### Approved W2 on unchanged VM3GiB candidate — 2026-10-29

Owner เริ่มทำ after W1Passed authorizes one native W2:100owners x20baseline,
100commands/s for300s with existing scheduledRESETs/selectedoracles/overflow
recovery and unchanged R25/R26/R27-A gates. Same source/VM3GiB/CPU/container
RAM/pools as passed W1; fresh0058DB, no diagnostic flags. Stop on failure,
no automatic retry or W3/W4 in this attempt. Preserve W1/historical evidence.


### Approved bounded dispatch timeline — 2026-10-29

Owner เริ่มทำ after read-only W2 correlation authorizes one60s diagnostic with
W2 dataset/rates and same VM3GiB/CPU/RAM/pools/R10/R22/monitor4. Instrument only
harness wrappers around existing scan/claim/process/transaction/maintenance calls;
no SQL added or selectors/financial rules changed. Aggregate perworker/sec during
window (<=600SECOND records plus bounded setup/tail/closed summaries), <=100detail
records perPaperworker (<=1000total). Fivefixedordinaryowners; firstcycle subset
identified offline through durable request/order IDs; collected subset may include
latercycles/activepolls for thoseowners within the hard cap. Truncation/collector
failure makes attribution incomplete and stops run. ClaimNone is unclassified,
not assumed lock-busy. Work tags read existing command result_state, no query.
Internal --dispatch-diagnostic-seconds60 only with W2; worker-only --dispatch-trace.
Native acceptance defaults remain disabled. Reuse existing60s cancellation/join
and failure supervision. This is not W2 acceptance; RESETs at180s not covered.
Tests coveridentity/classification/transaction commit/rollback/collector errors/
restoration/cap/default-off before one workload; no automatic repeat or optimization.


### R28 — Approved W2 bounded saturation (2026-10-29)

Owner approve authorizes requirements, harness method and validation in
[w2-bounded-saturation-amendment.md](w2-bounded-saturation-amendment.md). This
supersedes the W2 all30000commands/360s gate only:6000nominalslots,<=100active
cycles/oneperowner, explicit unsubmitted backpressure,300sstartwindow/360sdrain,
allstartedcomplete,>=600completedcycles/everyowner>=1. Actual IDs/perownercounts
drive independent existing oracles; all R25/R26/R27-A safety/RESET/overflow/resource
gates retained. This is client-bounded saturation, not100incomingAPIrequests/s
or a production global queue bound. W1/W3/W4/F15 defaults unchanged; historical
W2Failed retained pending fresh evidence. No production API/schema/trading change.


### R29 — Approved W2 owner service target (2026-10-29)

เจ้าของตอบ “อนุมัติ R29” ตาม [w2-risk-service-target-amendment.md](w2-risk-service-target-amendment.md).
เฉพาะ F18 Paper W2 bounded saturation: ready inputs ต้อง commit ผล/latch ภายใน
3s อย่างน้อย **99.5% ต่อ owner**; รวมทั้ง run คง **99.9%**, ทุก input คง **<=5s**.
ข้อยกเว้นนี้แทน R25/R28 เฉพาะ owner quota ของ W2; W1/W3/default คง99.9%.
นับด้วยจำนวนเต็ม เก็บทุก input/เวลารอ/late receipt; unacknowledged/clock errors
ยังต้องเป็นศูนย์. ยอมรับ quota ที่ล่าช้า3–5sต่อ owner เพิ่มจาก0.1%เป็น0.5%
เฉพาะช่วง saturation. ไม่เปลี่ยน production monitor, เงิน, freshness, fences,
authorization, deadlines, processing500ms/1s, RESET, overflow หรือ resources.
ใช้ sla_summary เดิมแบบระบุ phase และบันทึก owner/global targets แยก;
ทดสอบ boundary/default/missing ACK/hard limit ก่อน W2 ใหม่หนึ่งชุด. ถ้าผ่าน
ทุก gate จึงเริ่ม W3/W4 ตามแผน; หยุดเมื่อ failure ไม่วนรันหรือผ่อนเกณฑ์เอง.
ผล W2 เดิมยัง Failed/Partial; W1 ใช้ต่อได้เมื่อ default/dependencies ไม่เปลี่ยน.
Paper/F18 Pending Full Validation; V22/V23 Pending Dependency.


### R30 — Approved harness measurement and coverage correction (2026-10-29)

Owner approve authorizes R30 in [M5 checkpoint](evidence/m5-final-candidate.md#r30-consolidated-harness-correction--approved-2026-10-29), including NC-R30-01:
price10Hz means10freshBTC and10freshETH observations/s, not lease-only frames or
repeated snapshots. Count committed source data in the fixed nominal window;
report setup/drain separately. Preserve all ready inputs in risk SLA. Historical
W1Passed remains recorded but cannot certify this missing price-load gate; no
automatic W1 reuse or rerun. R25–R29 numeric/safety/resource bounds remain.

Separate overflow injection/recovery/verification and total durations. Start60s
recovery just after final injection commit acknowledgement, before publisher
restart; complete only on captured-watermark progress, READY and consistent live
lag<=20. Normal final drain remains within duration+60; no extra waiting budget.
Check live recovery before stopping source/workers; retain final risk ACK drain
and record shutdown lag separately. W3 gets durable fault/restored/recovered
receipts, transaction-start fault attribution with full raw durations, idle-owner
coverage and fixed1800s RSS windows. W4 compares columnACL/policies/0058roles and
requires base and risk recovery verdicts plus exit0.

Reuse existing publishers, telemetry, resource/fault helpers and restore verifier;
keep shared F15 defaults compatible. Test-only observation helpers are grouped in
backend/tests/infra/risk_limits/profile_observations.py to avoid growing duplicate
phase/source/readiness logic. No production/API/schema/trading/allocation changes.
Implement and run affected tests/static only; the proposed60s measurement and
W1–W4 still require the stated separate authorization/preconditions.

### R32 — Approved Paper source cadence 5Hz (2026-10-29)

เจ้าของยืนยันปรับตาม [R32](paper-source-cadence-amendment.md): book BTC/USDT และ
fresh price BTC/USDT, ETH/USDT อย่างละ5Hzใน F18 Paper fixture เท่านั้น.
ป้อนทุก200msและนับunique actual commitsใน nominal windowเดิม; ไม่เปลี่ยน
100×20, command load, freshness, risk/processing SLA, safety, durations/resources.
ผล10Hzเดิมไม่เปลี่ยนเป็นPassed; ต้องมีหลักฐาน5Hzสำหรับcandidateสุดท้ายก่อนรับรอง.
R31childยังdiagnostic-only, ไม่เริ่มworkloadจากการปรับนี้.


### Publisher failure evidence — approved follow-up after R34 W3
Owner instructed “เริ่มทำ” for the proposed bounded publisher cause reporting.
Reuse SourcePublisher.publish and PublisherLink done event in
backend/tests/infra/risk_limits/profile_publisher{,_process}.py. On failure only,
record fixed stage (ACQUIRE/BOOK/PRICE/PUBLISH) and allowlisted exception category,
UTC time and monotonic time to publisher-failure.json; propagate category to parent.
Never record messages, SQL, parameters, exception chain, arbitrary class names or
credentials. Preserve original failure, cancellation/cleanup and no-retry behavior.
Tests must cover category redaction, stage attribution, parent failure propagation,
normal cancellation and cleanup. No scheduling/financial/resource/criteria change.
No new workload in this follow-up; decide the next measurement after targeted checks.

### W3 recovery snapshot-clock correction

The awake W3 run proved the final recovery timeout was not host sleep or a publisher
failure. Its final repeatable-read inventory had 100 READY owners and complete input
progress, but 23 rows reported source freshness false. `live_baseline` read owners
sequentially in one MVCC snapshot while comparing the frozen source row with a new
`statement_timestamp()` for every SELECT. If the inventory takes over one second,
the harness ages its own snapshot and can never observe all owners fresh together.

Use `transaction_timestamp()` for the observed time, lease and one-second freshness
checks within this read-only recovery snapshot. This preserves the existing 1s
freshness criterion and the same database clock while applying it at one snapshot
boundary for all owners. No production SQL, financial transaction, resource,
deadline, retry or acceptance threshold changes. Verify PostgreSQL clock semantics,
the existing committed-source/owner-progress recovery test, and affected static
checks before another W3 run. Preserve the failed run and do not retry automatically.
