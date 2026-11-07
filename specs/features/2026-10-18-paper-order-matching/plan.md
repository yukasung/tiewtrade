# F-15 — จำลองการจับคู่ออเดอร์ Paper — Plan

สถานะ: **Approved** — เจ้าของอนุมัติพร้อม requirements amendment NC-F15-07 และ validation.md วันที่ 2026-10-18
วันที่: 2026-10-18
Branch: feature/f-15-paper-order-matching
อ้างอิง: [requirements และ amendment NC-F15-07 ที่อนุมัติแล้ว](requirements.md), [validation](validation.md)

## 1. ขอบเขตและลำดับข้อมูล

ใช้คำตัดสิน NC-F15-01–06 ที่อนุมัติ 2026-10-18: MARKET BUY แบบ quote budget,
MARKET SELL แบบ base quantity, LIMIT/GTC, depth/trades, latency 100ms,
book verification ไม่เกิน 30s ตาม NC-F15-11 และ PAPER_STANDARD_V1 ต่อ episode
รายละเอียดนโยบายอยู่ใน requirements ไม่สร้างค่าปริยายอีกชุดในแผน
NC-F15-07 Closed: §3 ใช้สูตร amendment ที่อนุมัติแล้วพร้อมแผน/validation นี้

เส้นทางข้อมูล:

1. `market-data` ประกอบ venue-neutral order-book/trade/capability inputs จาก public venue
   ผ่าน transport และ rate limiter เดิม ลง PostgreSQL พร้อม generation/revision ก่อนแจ้ง Redis
2. `engine` อ่าน inputs จาก DB เป็นลำดับ ตรวจ readiness อีกครั้ง และบันทึก input evidence
   ที่ใช้ตัดสินใจใน transaction ของ episode; ไม่ import venue/network/credential
3. pure `core` ตรวจ intent/constraints/reservation และคืน matching transition/fill facts
4. session-bound storage ประกอบ order events, F-14 writer และ F-13 ledger effects
   ภายใต้ financial lock/transaction เดียว แล้วประกาศผลหลัง commit

ไม่สร้าง public order endpoint หรือหน้าเทรดใน F-15 ใช้ internal commands สำหรับประกอบ
F-16 ภายหลัง; production admission ของ order execution ต้อง fail closed เมื่อ shared
safety dependencies ยังไม่ครบ ห้ามใช้ `skip_risk` หรือ boolean จาก caller เป็นใบผ่าน
เทสต์โดเมนใช้ explicit fixture inputs ได้ แต่ production ไม่มี factory ที่สร้าง READY proof ปลอม
การ initialize source และ reset กระเป๋าว่างไม่ต้องเปิดรับคำสั่งเทรดก่อน

## 2. ของเดิมที่จะใช้ซ้ำและส่วนที่ต้องขยาย

| Path / ของเดิม | วิธีใช้ |
|---|---|
| `backend/src/tiewtrade/core/money/{types,rounding,position_arithmetic}.py` | Money/Quantity, times, is_multiple_of, money_for_quantity และ allocate_money; เพิ่ม primitive budget→quantity/step alignment ภายใน package นี้เท่านั้นเมื่อยังไม่มี operation ที่ต้องใช้ |
| `backend/src/tiewtrade/core/trading_limits.py:unmet_constraints` | ใช้ min quantity/step/notional เดิม ขยาย contract กลางสำหรับ price tick/max/type-specific filters โดยไม่ทำ validator อีกชุดใน executor |
| `backend/src/tiewtrade/core/positions.py` | ExecutionFact/FeeEffect/PositionPair และ calculation เดิมทั้งหมด; ไม่คัดลอก cost/PnL |
| `backend/src/tiewtrade/infra/positions/{records,storage}.py` | initialize_position_source, apply_position_event, read_position_activity/snapshot และ exact PairEconomicEffects; writer ไม่ commit เอง |
| `backend/src/tiewtrade/infra/paper_wallet/{records,storage}.py` | durable commands/claim/replay pattern, financial lock, active episode, get_wallet และ fold ledger เดิม; ขยาย ledger/reset ตาม §5/6 |
| `backend/src/tiewtrade/infra/db/{session,money}.py` | UserSession/ScanSession/MarketDataSession, RLS และ exact DB codecs |
| `backend/src/tiewtrade/infra/audit/{events,writer}.py` | typed action/details, shape constraints และ transaction-bound record_event |
| `backend/src/tiewtrade/venues/{symbols,constraints,limits,price_streams}.py` | Symbol/capability contracts, limiter และแนวทาง generation fencing; core รับ core DTO ไม่ import venues |
| `backend/src/tiewtrade/venues/binance_th/{transport,stream_transport,endpoints,mapping,rate_limit}.py` | HTTP/WS parsing/timeout/429/418 และ closed endpoint registry; เพิ่มเฉพาะ public read endpoints ที่จำเป็น ไม่มี order/fee/account credential call ใหม่ |
| `backend/src/tiewtrade/services/market_data/realtime.py` และ `infra/market_data/realtime_storage.py` | lease/generation/readiness/recovery pattern; แยก book source จาก latest-price state ไม่เปลี่ยน F-10 freshness |
| `backend/src/tiewtrade/core/market_catalog.py` | catalog สำหรับเปิดใหม่; เพิ่ม retention demand ของคู่ที่มีภาระเดิมตาม §4 โดยไม่ใส่ user data ใน market-data |
| `backend/src/tiewtrade/services/engine/paper_wallet{,_main}.py` | worker lifecycle/backoff/claim/fairness; ประกอบ orchestration ผ่าน infra ไม่ import service ข้ามกัน |
| `backend/tests/gates/test_paper_isolation.py` และ gate purity/import/endpoint เดิม | ขยาย discovery ให้ครอบคลุมไฟล์ใหม่และ transitive imports; negative fixtures ต้องจับทางลัดได้ |
| `backend/tests/infra/{positions,paper_wallet}/` และ `frontend/e2e/paper-wallet.spec.ts` | PostgreSQL real-role fixtures, barriers/faults และ browser reset integration เดิม |
| `frontend/src/{PaperWalletPanel.tsx,paperWallet.ts,paperWalletMessages.ts}` | wallet query/command polling/idempotency และข้อความสองภาษาเดิม; เพิ่ม reset mutation โดยแยก payload/key จาก CREATE และใช้ expected episode ที่ผู้ใช้ยืนยัน |
| `frontend/src/components/ui/{Button,Input}.tsx` | controls เดิม; confirmation ใช้ pattern จาก `references/admin-template/src/components/UiExample/ModalExample/FormInModal.tsx` และ modal กลางจาก template ตาม frontend standard ไม่ใช้ native confirm |

## 3. Contracts และ pure matching domain

เพิ่ม `core/orders.py`, `core/order_book.py`, `core/paper_matching.py`:

- immutable `OrderIntent`, `OrderState`, `OrderEvent`, `Reservation`, `SimulationProfile`,
  `MarketInput`, `BookState`, `MatchingState`, typed rejection/transition; Money/Quantity ทุก amount
- intent ผูก immutable mode, owner/episode scope, client idempotency identity, action,
  symbol, side/type/TIF และขนาดแบบ discriminated union; extra/ambiguous size ปฏิเสธ
- quantity-based intents ห้ามปรับขนาดเงียบ ๆ; budget BUY คำนวณ quantity ที่ซื้อได้จริง
  ตาม budget/step โดย primitive ใน money และคืนเงินส่วนใช้ไม่ได้ ไม่ใช้ float/Decimal เปล่า
- ใช้ทิศทางปัดของ F-02: ค่าใช้จ่าย/fee/reserve ไม่ต่ำกว่าภาระ และ proceeds/net quantity
  ไม่สูงกว่าที่ได้จริง ปัดเฉพาะ boundary ที่จำเป็น; out-of-range หรือ representation
  ที่พิสูจน์ budget/step ไม่ได้คืน typed failure ก่อนบันทึกผล ไม่ให้ DB ปัดแทน
- order lifecycle: immutable acceptance/rejection; mutable projection derive จาก events
  มี ACCEPTED, PARTIALLY_FILLED และ terminal FILLED/CANCELED/EXPIRED/REJECTED;
  MARKET partial ก่อน EXPIRED ต้องเก็บทั้ง execution และ terminal reason ไม่ทับผลเดิม
- availability แยกจาก order status: feed pause ไม่แปลง order เป็น terminal หรือคืนยอดเอง
- eligibility = server acceptance time + 100ms, input received_at ต้องหลัง eligibility;
  tie-break ด้วย durable episode command sequence ไม่ใช้เวลาหรือ UUID แบบสุ่มตัดสินเงิน
- crossing ใช้ราคาดีที่สุดก่อน; order ภายในราคาเดียวกัน FIFO ตาม episode order sequence
  และใช้ consumed quantity counter ร่วมต่อ input/price ใน episode เดียวกัน
- resting queue ใช้ visible external quantity + Paper quantity ที่มาก่อนตาม requirements;
  นับเฉพาะ trade IDs ที่ถูกฝั่ง/ราคาและยังไม่ใช้ การลด depth ไม่ใช่ maker fill
- เก็บ A/C/V ต่อ episode/side/price ตามสูตร `PAPER_DEPTH_SHADOW_V1` ที่เสนอใน
  requirements amendment NC-F15-07: taker เพิ่ม C, absolute depth ใช้ C_new=min(C,A_new)
  แล้ว V_new=A_new-C_new; duplicate/stale ไม่ transition, confirmed zero เท่านั้นปลด C
  ทั้งก้อน ไม่ใช้การหลุดจาก bounded snapshot เป็น zero; คำนวณด้วย Quantity package
- trade ใช้ resting queue/maker fill ไม่ลด A/C/V ซ้ำ; depth เปลี่ยน A เท่านั้น
  ทั้งสอง cursor/dedupe และ durable merged input sequence อยู่ใน replay evidence
  golden trace ต้องตรวจทั้ง A/C/V และ queue ไม่ใช้เพียงยอดเงินปลายทาง
- input ที่ไม่พอระบุ ordering/side หรือระดับราคานอกขอบเขต snapshot ไม่ใช่ zero liquidity
  ที่รับรองได้: ไม่สร้าง fill นอกขอบเขตนั้น และยก uncertainty เป็น source reason
- merged input order ใช้ combined-stream receive order ตาม NC-F15-12; ตรวจ continuity
  ทีละหนึ่งเฉพาะ depth `U/u`, ส่วน trade ID ใช้ bounded economic-identity dedupe
- rebase หลัง gap ตาม requirements โดยเก็บ rebase fact/เวลา/generation/คิวใหม่ที่ replay ได้
  ไม่จับคู่ย้อนหลังของช่วงหาย และไม่ใช้ snapshot ใหม่ล้างผลเงิน/consumption ที่ commit ไปแล้ว
- common execution result แปลงเป็น F-14 ExecutionFact; sequence execution ต่อ episode
  แยกจาก per-pair fold และ append event sequence; correction คง source sequence เดิม

fee profile เป็น immutable version ต่อ episode; buy fee ใช้ received base, sell fee ใช้
received quote ผ่าน `times("0.001", rounding=...)` ตาม primitive เดิม และส่งเข้า F-14
ไม่คำนวณ cost/PnL ซ้ำใน simulator ไม่เพิ่ม VIP/discount/rebate workflow

## 4. Public market input, completeness และ isolation

เพิ่ม venue-neutral `venues/order_books.py` และ Binance TH adapter สำหรับ snapshot/diff-depth,
trade facts ที่มี ID/ฝั่ง และ execution metadata; ไม่เอา Binance fields ไปใช้ใน services
snapshot bootstrap ต้อง buffer WS, bridge update IDs และยืนยัน continuous sequence
เมื่อ malformed/unknown rule/gap/disconnect/expired writer lease ให้ not-ready ทันที
heartbeat อย่างเดียวไม่ยืนยัน price/depth หรือขยับ book verification time

เริ่มด้วย snapshot limit 1000 และ diff stream 100ms ตามข้อมูลที่ source รองรับจริง
ไม่ extrapolate depth เกินขอบเขต; capability/filters ต้องมี source/version/time
ชนิด rule ที่จำเป็นแต่ parser ไม่รองรับต้องปฏิเสธ use case นั้น ไม่ ignore unknown rule
เก็บ public endpoint/shape fixtures และตรวจ bounded public contract ก่อนรับรอง integration
เมื่อของจริงไม่ตรงเอกสาร/fixtures ให้หยุดตาม AGENTS.md ไม่ทำ fallback โดยเดา

ใช้ per-pair generation/lease/cursor ใน PostgreSQL และ bounded input buffer 4096 slots
ต่อ pair พร้อม monotonically increasing input IDs; overflow หรือ consumer ตามไม่ทัน
เป็น gap ที่พัก/rebase ไม่ใช่เงียบ ๆ drop แล้วคง READY ตัวเลขนี้เป็น operational bound
ไม่ใช่เพดานขนาด order หรือจำนวนผู้ใช้ Redis เป็น wake-up hint เท่านั้น

engine copy ข้อมูลที่ใช้กับ episode ลง append-only `paper_execution_inputs` พร้อม
canonical fields/digest/model/profile version ก่อนใช้เงิน รวม input ที่เปลี่ยน queue/consumption
ไม่เก็บเพียง hash ที่ไม่มีเนื้อหาให้ replay ได้; input ที่ไม่เคยใช้ตัดสินไม่มีผลการเงิน
public buffer เป็น transport cache ที่ overwrite ได้ แต่ evidence ของ accepted decisions
ห้าม GC ตาม cache buffer และห้ามลบประวัติการเงินโดยอ้างว่า market data หมดอายุ

สำหรับคู่ถูกถอน: engine ถือ owner-level dependency records ภายใต้ RLS แล้ว publish
public pair-demand aggregate ผ่าน infra; market-data อ่านเฉพาะ symbol/demand revision
ไม่อ่าน order/position/user table คู่ที่ยังมีภาระค้างอยู่ใน managed feed set แม้ไม่อยู่
opening catalog; ปลด demand เมื่อไม่มีภาระและไม่มี in-flight reference ภายใต้ protocol เดียวกัน
ไม่ขยาย frontend catalog หรือเปิด risk-increasing admission ให้คู่นั้น

## 5. ฐานข้อมูลและ migration

เพิ่ม migration หลัง head 0032 โดยลำดับเสนอ `0033` public inputs/metadata,
`0034` Paper orders/evidence/ledger และ `0035` reset/audit integration;
ยืนยัน head อีกครั้งก่อนลงมือ ห้ามแก้ migration 0031/0032 ที่ใช้แล้ว

| ตาราง/ส่วนเปลี่ยน | หน้าที่และข้อบังคับ |
|---|---|
| `market_execution_state`, bounded `market_execution_buffer`, `market_execution_demand` | public-only feed lease/generation/input IDs, capability/version/readiness และ pair-demand; market-data ไม่เห็น owner |
| `paper_order_commands`, `paper_order_command_results`, `paper_order_dispatch` | immutable intent/terminal response และ mutable claim/schedule; scope unique user/action/key, canonical fingerprint, stale claim fencing |
| `paper_orders`, `paper_order_events` | identity/header และ append-only lifecycle/fill/cancel/rebase history; immutable owner/mode/episode/pair |
| `paper_order_projections`, `paper_reservations` | rebuildable current order/reserved quantities; nonnegative/exact units และ revision checks; ไม่ใช่ mutable cash balance |
| `paper_execution_inputs` | immutable per-episode replay evidence และ cursor decisions; daily time partitions, parent+child permission/trigger tests และ precreated partitions |
| `paper_execution_profiles`, `paper_order_activity` | fee/model policy pinned ต่อ episode; tri-state source completeness/revision/proof และ initialization identity |
| `paper_execution_links` | order/fill ↔ F-14 position event identity; composite FK owner/episode/pair และ unique execution application |
| `paper_wallet_ledger` ขยายแบบ additive | EXTERNAL_CAPITAL เดิมและ TRADE_CASH/CORRECTION_CASH แบบ signed; คงหนึ่งทุนต่อ episode ด้วย partial unique index แทน unique(episode_id) เดิม |

ledger เก็บ source_command_id สำหรับทุน และ source_position_event_id สำหรับ trade/correction
ด้วย CHECK แยก shape และ composite FK ไป F-14; ไม่ใช้ nullable FK เป็นช่องลัดข้าม owner
unique economic source ป้องกันการลงเงินซ้ำ ไม่มี ledger entry ที่ zero effect เว้น contract
ที่พิสูจน์ได้ต้องเก็บเป็น linkage fact แทน; capital entries เดิมไม่ถูก UPDATE/DELETE
ถอน amount>1000 เฉพาะ trade/correction shape โดย capital shape คง >1000 และ USDT
ตามเดิม ทั้งหมดใช้ domains F-02 ไม่ cast NUMERIC(p,s) ให้ DB ปัด

ทุก user table FORCE RLS, owner NOT NULL, composite owner/episode FKs และ append-only
triggers ครอบคลุม UPDATE/DELETE/TRUNCATE; mutable projection/dispatch อัปเดตได้เฉพาะ columns
ENGINE ทำงานใต้ UserSession; ENGINE_SCAN อ่านเฉพาะ opaque ID/owner/due metadata
ผ่าน view/column grants ห้ามอ่านยอด/payload หรือเขียน; API ไม่มี write grant ใน F-15 tables
market-data เขียนเฉพาะ public tables และอ่าน public demand; migrator เท่านั้นเป็น owner

upgrade รองรับข้อมูลทุน/position เดิมโดยไม่สร้าง READY อัตโนมัติจาก missing row
downgrade ทำได้เฉพาะไม่มี F-15 financial/history data และ schema เดิมรับข้อมูลที่เหลือได้
ถ้ามีต้องปฏิเสธแบบมีเหตุผล ไม่ล้างประวัติเพื่อ downgrade
public buffer ที่ไม่ใช่ financial evidence ล้างได้หลังหยุด producer/consumers เท่านั้น

## 6. Financial writer และ F-13 reset integration amendment

ทุก flow ใช้ lock `paper-wallet:{user_id}` เดิมก่อน lock active wallet state → activity
→ order/reservation projections แล้ว append facts; ห้ามถือ financial lock ข้าม network call
claim lease เป็นตัวลดงานซ้ำ ไม่แทน transaction advisory lock หรือ uniqueness

### Initialization และ execution

1. เปิด ENGINE UserSession แล้วตรวจ active episode/closure/profile และ durable completeness
2. episode เดิมที่จะ adopt ต้องพิสูจน์ว่ามีทุนเดิมหนึ่งรายการ ไม่มี unknown economic history
   และ baseline สอดคล้อง F-14; missing/corrupt row ไม่ใช่หลักฐานว่าง
3. initialize position source ผ่าน F-14 และ open-order source พร้อม baseline/proof digest
   กับ profile/cursor ใน transaction เดียว; concurrent retry ต้องได้ผลเดิม
4. admission ตรวจ shared gate capability + owner/episode + side/type/filters + available
   เงิน/quantity ภายใต้ lock ก่อนกันยอด; เมื่อ F-18 ยังไม่มี production gate ต้องไม่รับ order
5. worker ตรวจ claim/expected revision/input generation และ eligibility จาก durable facts
   แล้ว pure matcher คืน fill/event/reservation transitions
6. append input evidence/decision + order event แล้วเรียก F-14 session-bound writer
   APPLIED จึง append exact returned quote_cash_delta; REPLAYED ไม่มี economic effect ใหม่
   CONFLICTED เก็บ durable conflict/result โดยไม่ apply money หรือ state ครึ่งชุด
7. update projection/reservation/cursors/activity และ wallet revision, typed audit/command result
   แล้ว commit ทั้งชุด ถ้า audit/order/ledger write หรือ commit ล้ม rollback และ recover จาก identity

cancel แข่ง fill ต้องตัดสินใต้ lock เดียวกัน: fill ก่อน → cancel ได้เฉพาะ remaining;
cancel ก่อน → fill ไม่ apply ต่อ canceled remainder ไม่มี refund เงินที่ซื้อ/ขายไปแล้ว
correction ใช้ F-14 rebuild/compensating effects และปรับ order/history/reservation ให้ตรง
หาก rebuild ทำให้ subsequent sell/ภาระค้างพิสูจน์ไม่ได้ให้ conflict และหยุด ไม่แก้ยอดติดลบเอง
ไม่เปิด public correction endpoint หรือสิทธิ์ให้ admin เทรดแทนผู้ใช้

### Reset amendment ที่ขออนุมัติพร้อมแผนนี้

ขยาย branch RESET ปัจจุบันที่คืน ACTIVITY_UNKNOWN และเส้นทาง read/API/UI ของ F-13
ให้ครบตาม browser acceptance โดยไม่เพิ่ม public order endpoint:

- ตรวจ terminal replay ก่อน expected episode; replay เก่ายังคืนผลเดิมหลังเปลี่ยนรอบ
- stale expected episode → EPISODE_CONFLICT; source unknown/error/missing/revision
  mismatch → ACTIVITY_UNKNOWN; position/open/pending order/reservation ค้าง → RESET_UNSAFE
- pending/accepted command ที่ยังมีสิทธิ์เขียน episode เดิมเป็น activity ด้วย ไม่ดูเฉพาะ
  projection ออเดอร์ที่ fill ไปแล้ว; stale queued commands ที่มาถึงหลัง reset ต้องถูกปฏิเสธ
- success เมื่อ position/order sources complete และว่างจริงภายใต้ lock เดียวตลอด transaction
  append closure, episode ใหม่, capital ใหม่, pinned profile, source initialization และ
  terminal result/audit พร้อมย้าย pointer/revision โดยไม่ย้ายเงิน/PnL/history ข้ามรอบ
- ขยาย INSERT grants ที่ขาดสำหรับ closure อย่างจำกัด และเพิ่ม PAPER_WALLET_RESET audit
  success shape; source/order audit actions ใช้ enums/details/DB CHECK เดียวกับ conventions เดิม
- ต่อ get_wallet ให้ตรวจ financial revision และ ledger invariant ใน coherent snapshot
  ไม่เพิ่ม trade cash เข้า command replay snapshot เก่า; API contract และ exact string เดิมคงใช้ได้
- สร้าง reset_available/reset_reason จาก position+order completeness, pending commands,
  reservations และ active episode ใน snapshot/revision เดียวกัน; missing/error/conflict
  ต้อง false พร้อม reason ห้ามอาศัย dataclass defaults หรือการไม่พบ row เป็น idle
  เพิ่ม API SELECT เฉพาะ owner-scoped readiness fields/view ที่ต้องใช้ภายใต้ FORCE RLS
  ไม่ให้ API อ่าน execution payload หรือเขียน financial tables; ตรวจ grants ด้วย real roles
- ใช้ reset endpoint/CSRF/command polling เดิม; ขยาย `paperWallet.ts` และ panel ให้ปุ่ม
  อิง readiness จาก server, แสดง reason จริงผ่านข้อความแปล ไม่ hard-code disabled
  confirmation แสดง episode ปัจจุบันและทุนใหม่ตาม F-13; validate รูปแบบโดยไม่คิดเงินใน UI
  ใช้ controls/template ตาม §2; เพิ่ม shared modal เมื่อค้นแล้วยังไม่มี พร้อม source path
- หนึ่ง confirmed reset เก็บ payload, expected_episode_id และ idempotency key เดิม
  ตลอด pending/timeout/unknown-result retry; ป้องกัน double submit และไม่สร้าง key ใหม่
  จนทราบ terminal result; server ตรวจ sources/expected episode ซ้ำภายใต้ financial lock
  เมื่อ conflict ให้โหลด snapshot ใหม่และยืนยันใหม่ ไม่ย้าย reset ไป episode ใหม่เงียบ ๆ
- success ต้อง invalidate/refetch wallet query และแสดงรอบ/ทุน/เวลาใหม่จาก server;
  failure ต้องไม่แสดง reset สำเร็จหรือทิ้งประวัติเดิม และไม่แก้ snapshot ใน browser เอง

เอกสาร F-13/F-14 ที่อนุมัติเดิมไม่ถูกเขียนทับให้เหมือน reset ผ่านแล้ว หลังอนุมัติแผนนี้
ให้เพิ่ม integration amendment พร้อมอ้างกลับมายังแผน/validation นี้ในเอกสารที่เกี่ยวข้อง
ผล F-13 Partial/Not Run คงไว้จนมีหลักฐานใหม่ตาม V-13/V-14 ของ F-15

## 7. Worker, deployment compatibility และไฟล์ที่จะเปลี่ยน

เพิ่ม `infra/paper_orders/{records,storage}.py`, `infra/market_data/order_book_storage.py`,
`services/engine/paper_order{,_main}.py`, `services/market_data/order_book.py` และ tests คู่กัน
venue additions อยู่ใน `venues/order_books.py`, `venues/binance_th/order_book{,_mapping}.py`
และ closed read endpoint registry; core modules ตาม §3 และ money primitive ที่ขาดเท่านั้น
ขยาย `infra/audit/events.py`, migration, isolation/import gates และ F-13 storage ตาม §6
ขยาย F-13 wallet records/read route เท่าที่จำเป็นและ frontend wallet API/panel/messages,
shared modal และ tests สำหรับ reset ตาม §6; ไม่แก้หน้าเทรดหรือสร้าง Live executor

ใช้ durable DB dispatch + Redis hints, per-episode serialization และ fair bounded batches
order worker tick เป้าหมาย 20ms, batch 20 commands, claim 30s, statement/lock timeout 5s
ตาม pattern เดิม; latency 100ms เป็น eligibility floor ไม่ใช่ SLA ว่า fill ใน 100ms
cancel/timeout ปิด transaction/คืน connection; retries ใช้ backoff เดิม 1s/5s/30s/5m
และ re-read facts ไม่สร้าง economic identities ใหม่จากการ retry

schema expand ก่อน code พร้อม grants แล้ว deploy code ที่เข้าใจ ledger ใหม่ทุก financial
writer ก่อนเปิด reset/execution integration ใช้ DB capability fence ให้ old writer ที่ไม่รู้
version ถูกปฏิเสธก่อนแตะ episode ที่ F-15 ดูแล ไม่ใช้ env flag อย่างเดียวกัน mixed-version
rollback application ต้องปิด execution/reset admission และ drain claims ก่อน;
ห้าม downgrade schema/ลบข้อมูลเพื่อให้ old worker เขียนได้

## 8. Milestones, checkpoint และความเสี่ยง

M3 correction amendment NC-F15-08 อนุมัติ 2026-10-18: terminal order ที่ correction
ลด filled ให้ปิด remaining เป็น CANCELED โดยไม่ re-execute; active LIMIT ต้อง rebase
queue จาก current verified book/older orders พร้อม immutable fact ก่อน commit correction
ใช้ F-14 rebuild/exact cash effects และตรวจ reservations ทั้ง episode ก่อน commit เช่นเดิม

| Milestone | งานและ checkpoint |
|---|---|
| M0 | requirements รวม NC-F15-07 และ plan/validation Approved 2026-10-18; เริ่ม M1 ได้ |
| M1 | core contracts/money primitives/book/matching + independent golden/Hypothesis และ deterministic replay; V-1..V-6 |
| M2 | public adapter/input storage/migrations/RLS/evidence + fake feed end-to-end; V-7..V-9/V-16 |
| M3 | ledger/F-14/order worker/init/cancel/correction/recovery integration; V-10..V-12/V-15/V-17 |
| M4 | F-13 reset amendment, real races/faults และ existing browser flow; V-13/V-14 |
| M5 | stable candidate, review Critical/High, full regression/static/build/contracts/required CI; V-18 |
| M6 | release checkpoint V-19 workload/endurance/restore ครบก่อน Completed/activation; ไม่ใช้ smoke แทน |

แต่ละ milestone บันทึก commands, environment, source/diff revision, results และเวลาวัดจริง
ใน evidence/checkpoint เดิม ใช้ผลที่ยัง valid ต่อ ไม่รัน full suite หลังทุก fix
การจบ M5 เป็น Development Complete ได้เฉพาะด่านที่ไม่เลื่อนครบ แต่ยังมี
Pending Full Validation และ production order admission ยังคงรอ downstream safety features
commit/push/merge ทำเมื่อเจ้าของสั่งเท่านั้น

| ความเสี่ยง | วิธีตรวจ/ข้อจำกัด |
|---|---|
| L2 ไม่รู้ hidden queue/latency จริง | disclose model version, conservative maker fixtures, ไม่รับรอง profit parity กับตลาด |
| absolute depth เติม virtual liquidity ซ้ำ | replay/counter properties, same-input multi-order และ restart barrier tests |
| net received fee และ cash ลงซ้ำ | ตรวจ F-14 exact effects/ledger conservation ทุก transition รวม correction |
| missing source ถูกถือว่าว่าง/reset race | real DB sources + lock/fault/initialization/old-episode rejection |
| overload/source gaps | bounded buffers, not-ready fencing, durable rebase; ไม่มี silent drop |
| mixed writers/grants/audit partitions | compatibility fence, role tests, migration/bootstrap/partition coverage |
| public venue shape ต่างจาก fixture | bounded contract check; หยุดก่อนใช้จริงและขอคำตัดสินหากกระทบ approved requirements |

หากลงมือแล้วต้องเปลี่ยนโมเดลคิว/fee/reserve/ข้อกำหนดที่อนุมัติ ให้หยุดขออนุมัติ
การเปลี่ยนก่อนแก้โค้ดตาม AGENTS.md ไม่เปลี่ยนแผนย้อนหลังให้ตรง implementation

## NC-F15-10 — Approved (2026-10-20)

เจ้าของอนุมัติให้คง revision ของ terminal history เดิม และอัปเดตเฉพาะ active orders/รายการที่เพิ่งจบใน transaction ปัจจุบัน พร้อม reservation ที่ปล่อยเป็นศูนย์อย่าง atomic. Terminal revision ต้องไม่เกิน activity revision; projection/reservation ของรายการเดียวกันต้องสอดคล้องกัน. ใช้ additive migration ปรับ F-13 reset coherence โดยรักษา source proof, event linkage, owner isolation และการปฏิเสธข้อมูลผิด/ไม่ครบ; ไม่แก้ migration 0037. Downgrade ต้องปฏิเสธเมื่อมีข้อมูลที่ contract เดิมรับไม่ได้ ไม่ rewrite ประวัติ.

ใช้ `matching_storage.persist_checkpoint` และ `paper_wallet_reset_readiness` เดิม; เพิ่ม real PostgreSQL safety tests สำหรับ active/current-terminal revision, old terminal rows ไม่ถูกเขียนซ้ำ, corruption, reset, correction, rollback/retry และ migration. กฎเงิน/การจับคู่และเกณฑ์ W1–W4 คงเดิม; ผลที่ได้รับผลกระทบต้องตรวจใหม่ก่อน Completed.

### NC-F15-13 — Approved Binance TH execution filters (2026-10-30)

ทำตาม [amendment](binance-th-execution-filters-amendment.md): ใช้ public aggregate-trade
bootstrap + live trade stream สร้าง reference ที่ versioned กับ execution input, ขยาย
OrderConstraints/codec สำหรับ percent range, average window และ max open orders แล้วตรวจใน
owner transaction ก่อน accept พร้อม fail-closed recheck ที่ matching. ใช้ Money/Quantity
และของเดิมด้าน idempotency/owner lock; ไม่เพิ่ม schema หรือ network call ใน API/engine.


### F18 integrated runtime scheduling exception — Approved2026-10-27

Owner approved [F18-R7](../2026-10-25-wallet-risk-limits/worker-round-amendment.md)
before implementation: F18-integrated production/runtime harness alternates
manual1/matching1 with the existing20ms tick, instead of two20-candidate phases.
F15 standalone harness and bounded round-function defaults remain20; all claim,
FIFO/fairness/lease, financial/freshness/eligibility, backoff and W1–W4 thresholds
remain unchanged. See F18 manifest/evidence for this explicitly different runtime.

### Set-4 W1 diagnostic — Owner-approved2026-11-06

After the unchanged W1 failed at the60s positive-cycle bound, the owner selected A:
add test-harness-only diagnostics before a new W1 attempt. Reuse
`tests/infra/risk_limits/profile_pool_timing.py::TransactionTrace/operation_scope/sample_database`,
`profile_resources.py::worker_pool_evidence` and
`profile_dispatch_timing.py::traced_worker`; no new production instrumentation.
Add an opt-in `--diagnostics` flag to the F15 parent/worker launcher. Trace the first
180s of the measured interval, including parent generator phases and worker scan/
claim/process. Reuse the sampler's existing migrator engine for read-only PostgreSQL
activity samples. Preserve pool configuration, SQL/business operations, quantities,
rates,60s cycle bound,30-minute W1 interval, all financial oracles and assertions.
The instrumented run is diagnostic evidence, never acceptance. Use a fresh database,
retain the failed run, verify cancellation/redaction/patch cleanup and child flag
propagation before running. No W2/W3 until this failure has been understood.

### Failure-only W1 cycle timeline — Owner-approved2026-11-06

After3 failed checks, the owner selected A: add per-step timing and owner/order
identity only for a cycle whose60s budget expires, plus a queue snapshot after
workers stop. Keep profile/pool/scheduler and the180s transaction trace unchanged.
Use existing `run_scheduled_cycles(..., cycle_scope=...)` with the identical
`asyncio.timeout(60)` budget and existing `operation_scope` wrappers. Keep only
bounded transient phase entries for each active owner cycle; completed cycles are
discarded. Do not mislabel sibling cancellation or child errors as budget expiry.
Reuse `tests/infra/risk_limits/scheduler_diagnostics.py` and ENGINE_SCAN for a
bounded selected-command snapshot after cleanup; no new grant/role or financial SQL.
Test original deadline/error propagation, task isolation, bounds/redaction, cleanup
and read-only snapshot selection before one fresh diagnostic W1 attempt. Preserve
all failed evidence; this remains non-acceptance and does not authorize new retries
or business/scheduling changes.


### F18 R8 scheduling follow-up — Approved2026-10-27

Owner approved [F18-R8](../2026-10-25-wallet-risk-limits/claim-budget-amendment.md):
F18 runtime scans at most20ordered candidates but claims at most1per phase,
including a claimed item that later fails/defers. Skip claimNone candidates with
unchanged CAS/owner/FIFO rules; defaults/standalone remain20/no claim budget.
This supersedes only R7's one-candidate limit, keeping its short phase alternation
and all safety/resource/validation limits. Incorporated before implementation.

### Standalone R8 opt-in runtime — Approved 2026-11-06

Owner selected option A in the [standalone worker budget amendment](standalone-worker-budget-amendment.md),
including its explicit acceptance mapping. This supersedes the standalone20/no-budget
restriction only when the new opt-in flag is set. Default behavior stays unchanged.
Reuse `profile_workload.py::run_worker_process(claim_limit=1)` and shared
`services/engine/{manual_order,paper_order}.py` R8 semantics: scan20, at most1non-None
claim per phase counted before commit; None skips do not consume this budget.
Forward the flag through initial/recovery/restart workers; manifest records the
separate runtime ID and actual scan/claim limits. No production changes, pool/process
increase, command retries, new infrastructure or trading-rule changes.
Targeted existing R8/real-DB safety plus CLI/default/restart/credential tests and
relevant static checks precede one fresh full W1. Keep prior Failed results.
If W1 fails, diagnose/report before another run. Original W1–W4 financial, load,
duration and SLA criteria remain unchanged; W2/W3 continue only after W1 passes.

### Publisher renewal and latency follow-up — Approved A 2026-11-06

After the authorized R8 W1 failed, the owner asked to continue preparing the next
plan. The [heartbeat/diagnostic amendment](publisher-heartbeat-diagnostic-amendment.md)
defines optional test-only heartbeat renewal and one bounded100-owner diagnostic,
with reuse paths, safety tests and an explicit stop before any performance fix or
full W1. Owner selected A before implementation (NC-SET4-03 closed): implement
only the explicit default-off heartbeat and observer changes, run scoped safety
checks and exactly one diagnostic, then stop/report. All existing acceptance
criteria and failures stay unchanged; no production/performance fix is authorized.

Replacement checkpoint2026-11-06: first diagnostic was Incomplete due to observer
control publication race. Atomic metadata repair passed affected checks; latest
owner A supersedes B and explicitly authorizes one fresh replacement under
NC-SET4-04 and the amendment's unchanged envelope. Stop/report afterward; no
production/performance change, full W1 or Git publication is authorized.

### Checkpoint latency and final-tail follow-up — Approved A 2026-11-06

Owner asked to continue preparing the plan after replacement diagnostic2.
[Checkpoint batch/tail amendment](checkpoint-batch-tail-drain-amendment.md) defines
A: narrowly scoped invoker-rights DB persistence batch and additive migration,
plus opt-in final-tail drain; B: harness tail only. Existing owner/episode/claim/
freshness checks and Python decisions/audit stay in place. Targets, reuse paths,
semantic/trigger/RLS/migration safety gates and one later diagnostic are specified.
NC-SET4-05 closed: owner approved A before implementation, including its safety
gates and exactly one later diagnostic; stop/report afterward. No full W1 or Git
publication is authorized.
No source code or new workload changed while preparing the proposal.


### NC-SET4-06 — Approved A paired latency isolation

Owner requested preparation of the next plan after NC-SET4-05 stopped. Offline
comparison of the existing180s traces is complete; no source/DB/workload changes.
[Paired isolation plan](checkpoint-latency-isolation-plan.md) proposes a test-only
Direct–Batch–Batch–Direct campaign on identical cloned4/22-header fixtures,
three blocks each (24arms/360checkpoint operations), preserving financial snapshots
and existing authority. Approximately5–10minutes,15-minute cap, then stop/report.
Owner approved A before harness edits and campaign execution. This approval is
limited to the paired experiment, then stop/report; W1 acceptance is unchanged.


### NC-SET4-07 — Approved A concurrency/polling isolation

Owner requested the next concrete plan after NC-SET4-06. The
[approved experiment](checkpoint-concurrency-polling-plan.md) freezes0065batch,
compares1/4independent writers with0/100readers at the existing0.25s interval,
in8measured arms plus one4-owner reference (576checkpoints). Post-window final
history/state comparisons avoid verification load during concurrent writes.
Bounded client traces and read-only local test-DB resource observations support
attribution.2–5minutes expected/15-minute cap, then stop. Owner approved A:
harness, targeted tests and one campaign. No production fix or W1 authorized.


### NC-SET4-08 — Approved A paired polling/runtime observation

Owner requested the next plan after NC07. [Proposed plan](checkpoint-runtime-drift-plan.md)
fixes measured writers at1, uses adjacent ABBA/BAAB polling pairs (192 measured +
96 reference =288 checkpoints), and adds opt-in phase/loop/CPU timestamps plus
independent read-only resource observers. Existing CLI/defaults and production stay
unchanged. Targeted gates before one2–5min/cap15min campaign, then stop/report.
Owner approved A before harness implementation; targeted checks in progress.


### NC-SET4-09 — Approved A parent polling budget

Owner requested parent submit/read inspection after NC08. The
[approved plan](parent-poll-budget-plan.md) adds only an opt-in4-reader gate before
owner-session acquisition, preserving deadlines/checks and shared pool defaults.
Targeted safety tests precede one existing100-owner/20-baseline/6-cycle SMOKE
profile with explicit gate and complete measurement trace.10–15min expected,
20min total cap, then stop/report. Owner approved A before harness implementation.
Execution: harness complete;115 targeted tests and scoped static checks passed.
One diagnostic **Incomplete / cycle bound Failed**:813.431s total, baseline2000
orders,289/600 cycles,1732 offered/1731 admitted/1632 completed commands of3000
planned. Gate peak4 and cleanup verified; financial/final-tail checks Not Reached.
See plan execution checkpoint and Batch ledger. Stop/report reached; further
worker/queue trace inspection and next planning await owner direction.

### NC-SET4-10 — Approved A worker selection/claim coordination

Owner requested a concrete next plan after NC09 follow-up. The
[approved amendment](worker-claim-coordination-plan.md) specifies a default-off
PostgreSQL coordinator held only through scan and owner claim commit, released
before parallel processing, with existing claim fences unchanged. It includes
bounded cleanup and targeted real-DB/multi-process safety checks, then stop/report.
Owner approved A before implementation. Three shared source files and two focused
test files implemented;94 targeted cases passed (85 combined +9 setup-blocked cases
rerun), scoped static checks passed and all7 dependency contracts kept. Cleanup
verified. No activation/timed experiment or acceptance mapping. Stop/report reached;
next NC10-scoped code review awaits owner command. See amendment execution checkpoint.
## Consolidated Paper campaign — Approved A 2026-11-06

Owner approved the [integrated Paper acceptance plan](../2026-11-02-tp-sl/integrated-paper-acceptance-plan.md)
after requesting continuous completion work. NC-SET4-01 profile definition is now
closed; actual acceptance remains pending. This authorizes the NC10 harness runtime
option and the explicit diagnostic, followed conditionally by integrated W1–W4
under that plan. Existing safety/SLA criteria and Release dependencies remain.
No production activation or Git publication is included.

The first diagnostic reuses NC09's100-owner/20-baseline/6-cycle composition with
the reviewed coordinator. Harness-only flag/default/restart metadata and read-only
selection/gate-call timing passed133 targeted tests and scoped static checks.
Later HTTP intake/F-14 snapshots/rebuild/extended restore must be implemented and
validated before their acceptance phases; this diagnostic does not certify them.

## Processing latency population correction — Approved A 2026-11-06

After the criteria review, the owner selected A: keep the approved workload and
250ms/1s processing and60s progress criteria; fix only the latency summary and
targeted tests before any further timed campaign. No production/runtime tuning,
load run, commit or push is included in this checkpoint.

Reuse `measured_transaction_seconds` from
`backend/tests/infra/risk_limits/profile_workload.py` by moving the implementation
to the existing shared F15 harness, `backend/tests/infra/execution_market/profile_workload.py`;
retain the existing risk-harness import contract and selection behavior. Attribute
transactions by start in the half-open measured interval, after baseline preparation
and before final drain. Retain full durations across the end/fault boundary; exclude
only starts inside recorded fault-start/restoration intervals. No arbitrary extra
warm-up/recovery grace, clipping, latency-based filtering or fallback to pooled metrics.
Preserve raw samples and record the selected interval/fault boundaries in evidence.
Failure remains Incomplete and does not become a completed acceptance result.
BASELINE and the separate W2_OVERFLOW negative phase have no non-fault positive-load
latency result; report that explicitly, never use setup latency to certify them.
W2 positive-load performance remains mandatory and unchanged.

Validate with timestamp fixtures for setup, drain, exact boundaries, cross-boundary
slow transactions, scheduled faults, missing/empty evidence and restarted workers;
exercise parent result wiring without a database or worker processes. Reuse the
existing risk-population regression and standalone supervision/runtime tests, then
run scoped Ruff/format/mypy. Stop/report after these checks; a new workload or
performance fix requires a separately agreed scope.

Execution checkpoint: implemented the shared start-time selector and explicit
measurement evidence;66 targeted tests passed. Scoped Ruff/format and F15/new-test
mypy passed. The risk harness has2 callback assignment type errors reproduced on
the pre-edit snapshot, so its full type check remains blocked; no unrelated callback
changes made. Retained-data reanalysis still hasp95=470.510ms (Partial only).
See [checks and limits](evidence/latency-population-20261106/README.md). No load run.
