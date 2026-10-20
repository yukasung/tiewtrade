# F-13 — กระเป๋า Paper และเงินตั้งต้น — Plan

สถานะ: **Approved** — เจ้าของอนุมัติวันที่ 2026-10-15 พร้อมเลือกให้ create/read ใช้งานก่อน และ reset ปฏิเสธ `ACTIVITY_UNKNOWN` จน F-14/F-15 มีข้อมูล authoritative

วันที่: 2026-10-15

Requirements: [ฉบับอนุมัติ](requirements.md) · Branch: `feature/f13-paper-wallet`

**Integration amendment อนุมัติ 2026-10-18:** เจ้าของอนุมัติ [F-15 plan §6](../2026-10-18-paper-order-matching/plan.md#6-financial-writer-และ-f-13-reset-integration-amendment)
ให้ขยาย signed trade/correction cash ledger, authoritative source initialization,
reset writer และ coherent reset readiness/API/UI โดยคง command replay snapshots เดิม
และ financial lock เดียวกัน ผล reset success ยังไม่ Passed จนผ่าน F-15 V-13/V-14/V-15
และเกณฑ์ F-13 ที่อ้างกลับครบ; ก่อน integration พร้อม runtime ยังคง ACTIVITY_UNKNOWN

## 1. แนวทางและขอบเขต

ใช้ `core` ตรวจทุนและคำนวณยอดด้วย `Money` เท่านั้น, PostgreSQL เป็นแหล่งจริงของ
กระเป๋า/รอบ/ledger/คำขอ และ engine เป็นผู้เขียนสถานะการเงินเพียงฝั่งเดียว
API รับคำขอที่ตรวจตัวตนแล้วลง PostgreSQL และอ่านผล ไม่เขียน ledger เอง
ตาม `standards/architecture.md` §3–5 ไม่ส่ง HTTP ระหว่าง service และไม่พึ่ง Redis
เพื่อรับประกันว่าคำขอไม่หาย ไม่มีการเรียก venue หรืออ่าน credential ในเส้นทางนี้

สร้างได้หนึ่งกระเป๋าต่อ user โดยไม่ผูกอายุกระเป๋ากับ API key ไม่เพิ่มเงื่อนไขว่าต้องมี
key ACTIVE, เลือก MANUAL/BOT หรือเปิด TOTP เพื่อใช้เงิน Paper ซึ่ง requirements
ไม่ได้กำหนดไว้ ไม่เปลี่ยน `may_trade=False` ของ F-08 และไม่เปิดการส่งออเดอร์
ทุนทุกรอบเป็น external capital; ไม่เพิ่มสูตร PnL หรือ schema position/order ล่วงหน้า

แนวทางใช้ strategy/ตรรกะโดเมนและฟอร์มร่วมกันระหว่าง Paper/Live ที่เจ้าของยืนยัน
2026-10-15 ดู [ADR-004](../../decisions/004-shared-paper-live-trading.md)
F-13 คงขอบเขตกระเป๋าจำลอง; การแยกหน้าเทรดและ execution เป็นงานถัดไปตาม ADR
เจ้าของอนุมัติแนวทางนี้พร้อมแผนฉบับนี้ และปิด NC-F13-02 ตามข้อยุติใน §8

เอกสารนี้เสนอรายละเอียดเทคนิคเพื่อขออนุมัติ ไม่ใช่อนุญาตเขียนโค้ด
ส่วน reset ที่ต้องตัดสินเพิ่มแยกไว้ใน §8 ห้ามถือว่าอนุมัติ requirements เป็นคำตอบของข้อนั้น

## 2. ของเดิมที่จะใช้ซ้ำ

ค้นใน working tree วันที่ 2026-10-15 แล้ว:

| Path | ใช้ซ้ำ |
|---|---|
| `backend/src/tiewtrade/core/money/{types,limits,validation}.py` | `Money.of`, การเทียบ/บวก, `as_parts`, precision/range/serialization เดิม |
| `backend/src/tiewtrade/infra/db/money.py` | `money_to_columns` / `money_from_columns`; Decimal เฉพาะ adapter เดิม ไม่คำนวณนอก Money |
| `backend/src/tiewtrade/infra/db/{session,engine,errors}.py` | user transaction/RLS, ENGINE/ENGINE_SCAN/API roles และ safe database errors |
| `backend/migrations/versions/0001_foundation.py`, `0003_append_only_partitions.py` | domain `tiewtrade_money_amount`, unit domain และ append-only helper/trigger ที่ห้าม UPDATE/DELETE/TRUNCATE |
| `backend/src/tiewtrade/infra/audit/{events,writer,redaction}.py` | typed audit และ `record_event` ใน transaction เดียวกับการกระทำ |
| `backend/src/tiewtrade/services/api/{authentication,routing_policy,safe_input_routes,resources}.py` | session/CSRF, route classification, sanitized validation และ DB resources |
| `backend/src/tiewtrade/services/engine/verification.py` | อ้าง pattern scan metadata → user-scoped processing; ไม่ใช้ตัวตรวจ key หรือ wallet factory กับ Paper |
| `backend/src/tiewtrade/infra/trading_account/storage.py` | อ้างวิธี owner-scoped read และ fail-closed เมื่อยังไม่มีหลักฐาน activity; ไม่เรียก `get_account` ซึ่งอ่าน key summary |
| `frontend/src/{AccountSession,TradingAccountPanel}.tsx`, `api.ts` | identity-scoped TanStack Query, cancel/clear เมื่อ logout/401 และ API transport |
| `frontend/src/components/MarketValue.tsx` | `MarketValue` แสดง exact text, `MarketTime` แปลงเวลาไทยเฉพาะหน้าจอ |
| `frontend/src/components/ui/{ComponentCard,Input,Label,Button}.tsx` | controls กลางที่ปรับจาก admin template แล้ว |
| `references/admin-template/src/components/{common/ComponentCard.tsx,form/input/InputField.tsx,form/Label.tsx,ui/button/Button.tsx}` | ต้นแบบ form/card และทุก visual state |
| `references/admin-template/src/components/UiExample/ModalExample/FormInModal.tsx`, `ui/modal/index.tsx` | ต้นแบบ reset confirmation; ถ้าต้องเพิ่ม Modal ให้ปรับเป็น shared component ก่อน พร้อม focus management ตาม accessibility |
| `frontend/e2e/helpers/` และ `backend/tests/infra/{db,audit,trading_account}/` | isolated test environment, roles, RLS, append-only และ concurrency patterns |

ไม่มี ledger หรือ Paper command processor เดิมที่นำมาใช้ตรง ๆ ได้
ไม่ใช้ `venues/wallets.py` เพราะเป็นการติดต่อยอดตลาด ไม่ใช่กระเป๋าเงินจำลอง

## 3. Domain และ schema ที่เสนอ

### 3.1 Core

เพิ่ม `core/paper_wallet.py`: immutable domain values, typed error codes,
ตรวจข้อความทุนด้วย `Money.of(..., 'USDT')` แล้วเทียบกับ `Money.of('1000', 'USDT')`
แบบ strict `>`; ไม่สร้างกฎปัด precision หรือเพดานตัวเลขอีกชุด
ยอดเริ่มจาก Money ศูนย์แล้วรวม ledger ของ episode เดียวผ่าน Money
เวลาหรือ ID ทั้งหมดผู้เรียกส่งเข้ามา ไม่อ่านนาฬิกาหรือสร้าง UUID ใน core

ใน F-13 มี ledger kind `EXTERNAL_CAPITAL` เท่านั้น หนึ่งรายการต่อ episode
ไม่สร้าง debit/fee/trade kinds ก่อน spec ของงานนั้น และไม่ส่งค่า PnL ปลอมเป็นศูนย์

### 3.2 Migration ใหม่

working tree มี head `0030_supported_pairs_reduction`; เสนอ
`0031_paper_wallet.py` ต่อจาก head นี้ ตรวจ head อีกครั้งก่อน implementation
ไม่แก้ migration ที่เผยแพร่แล้ว และไม่รัน migration ในขั้นจัดทำเอกสาร

| ตารางที่เสนอ | สาระและ constraints |
|---|---|
| `paper_wallet_commands` | `id`, `user_id`, action CREATE/RESET, idempotency key, canonical payload, requested_at และ expected_episode_id สำหรับ RESET; input เพิ่มอย่างเดียว |
| `paper_wallet_admission_results` | ผลปฏิเสธก่อนเข้าคิวที่ผ่านตัวตนและมี idempotency key แล้ว เช่นทุนไม่ผ่านหรือ key เดิมกับ payload ต่างกัน; เก็บ request fingerprint และ fixed failure code แบบเพิ่มอย่างเดียวเพื่อ replay/audit โดยไม่เก็บ raw invalid input |
| `paper_wallet_command_dispatch` | สถานะจัดคิวที่เปลี่ยนได้หนึ่งแถวต่อ command: attempt count, next_attempt_at, claim id/owner/expiry และ last infrastructure failure code; เป็นข้อมูลควบคุม worker ไม่ใช่ประวัติเงินหรือผลธุรกิจ |
| `paper_wallet_command_results` | หนึ่ง terminal result ต่อ command, owner, outcome/code, response snapshot และ completed_at; เพิ่มอย่างเดียว ผลสำเร็จ commit พร้อม ledger/audit |
| `paper_wallets` | id, user_id UNIQUE, mode CHECK PAPER, created_at; identity เพิ่มอย่างเดียว ไม่เก็บยอดหรือ credential |
| `paper_wallet_episodes` | id, wallet_id, user_id, sequence, started_at, initial_capital, currency USDT, mode PAPER; UNIQUE(wallet_id, sequence), เพิ่มอย่างเดียว |
| `paper_wallet_episode_closures` | episode_id UNIQUE, user_id, closed_at, reset_command_id UNIQUE; ปิดรอบด้วยแถวใหม่ ไม่ UPDATE รอบเดิม |
| `paper_wallet_state` | wallet_id UNIQUE, user_id UNIQUE, active_episode_id, revision; pointer ที่ engine เปลี่ยนภายใต้ lock ไม่ใช่แหล่งเก็บยอดเงิน |
| `paper_wallet_ledger` | id, user_id, wallet_id, episode_id, mode PAPER, kind EXTERNAL_CAPITAL, amount, currency USDT, source_command_id UNIQUE, created_at; UNIQUE(episode_id) ในขอบเขต F-13 |

ใช้ composite foreign keys รวม owner/wallet/episode เพื่อกันแถวของ user A ชี้ resource
ของ user B แม้รู้ UUID; บังคับ initial capital `> 1000` และ unit/mode ที่ DB ด้วย
amount ทุกช่องใช้ domain เดิมซึ่งเป็น unconstrained NUMERIC พร้อม CHECK precision/range
ไม่ cast เป็น NUMERIC(p,s) ที่ปัดก่อนตรวจ และไม่แก้ domain ของ F-02

active pointer ต้องอ้าง episode ของกระเป๋าและ owner เดียวกัน; engine ตรวจว่า episode
ไม่ถูกปิดและมีทุนต้นหนึ่งรายการก่อนคืน snapshot หากโครงสร้างไม่ครบให้ fail-closed
ไม่มี cache balance อีกชุด รวมยอดด้วย Money จากรายการภายใต้ snapshot เดียว

ทุกตารางมี owner NOT NULL, ENABLE/FORCE RLS, migrator เป็นเจ้าของ
และไม่ให้ runtime เป็น owner/superuser:

- API: SELECT ของ owner, INSERT เฉพาะ command/admission result/rejection audit และ
  initial dispatch columns (`command_id`, `user_id`, `next_attempt_at`) ด้วย column grants;
  claim/attempt fields ใช้ DB defaults และ API แก้ไม่ได้ ห้ามเขียน wallet/state/episode/
  ledger/terminal command result หรือ dispatch หลังรับคำขอแล้ว
- ENGINE: SELECT/INSERT ของ owner, UPDATE เฉพาะ active pointer และ dispatch claim/schedule
  ตาม transaction; ไม่มีสิทธิ์แก้ command, admission result, terminal result หรือประวัติเงิน
- ENGINE_SCAN: SELECT เฉพาะ command id/user id และ dispatch timing ที่ถึงคิว;
  ไม่อ่าน payload/ยอด/failure detail/secret และไม่เขียนข้อมูล
- market-data และ indicator-builder: ไม่มีสิทธิ์ตารางเหล่านี้
- append-only helper ครอบ command/admission result/terminal result/wallet/episode/closure/ledger;
  immutable mode รวมถึง state relationships ส่วน dispatch เป็น mutable control table ที่มี grants จำกัด

เพิ่ม audit actions CREATE/RESET และ typed details ที่ระบุ command/wallet/episode,
external capital และเหตุปฏิเสธที่ allowlist ทั้ง application และ DB shape check
เพิ่ม subject kinds สำหรับ PAPER_WALLET, PAPER_WALLET_EPISODE และ PAPER_WALLET_COMMAND;
การปฏิเสธก่อนมีกระเป๋าใช้ admission-result id เป็น subject ของ PAPER_WALLET_COMMAND
ใช้ actor USER ผู้สั่งจริง แม้ engine เป็นผู้ประมวลผล, mode PAPER เสมอ
ไม่แก้ audit ย้อนหลัง ไม่เปลี่ยน retention และไม่ cascade ลบประวัติเมื่อ user ถูกลบ

downgrade ยอมเฉพาะเมื่อไม่มีข้อมูล F-13; ถ้ามีให้ปฏิเสธแบบปลอดภัย
rollback application ต้องเก็บ schema/data ไว้ ไม่ drop/reset ฐานข้อมูล

## 4. Command processing, atomicity และ idempotency

เสนอ PostgreSQL durable inbox/result ตาม architecture เดิม:

1. API ตรวจ authentication/CSRF/schema และรับ `Idempotency-Key` เป็น UUID;
   scope UNIQUE(user_id, action, key) จากนั้นใช้ transaction advisory lock namespace
   ของ admission + user/action/key เพื่อ serialize คำขอ key เดียวกัน
   คำขอที่ยืนยันตัวตนหรือ action identity ไม่ได้ (401/403, body/header ผิดรูป หรือ 429)
   ยังไม่ใช่การตัดสินใจแตะเงิน จึงคืน fixed safe error และไม่เพิ่ม immutable financial audit
   เพื่อไม่ให้ผู้โจมตีขยาย audit log ได้ไม่จำกัด
2. ภายใต้ admission lock ให้ตรวจของเดิมก่อน: payload เดิมคืน command/admission result
   เดิมโดยไม่กินโควตาและไม่เขียน audit ซ้ำ คำขอใหม่หรือ payload conflict ต้องผ่าน
   `PAPER_WALLET_MUTATION` token bucket ต่อผู้ใช้ก่อนดำเนินการต่อ
3. API parse Money และ canonicalize payload ภายใน user transaction
   - ทุนผ่าน: INSERT command + dispatch แบบ atomic; ไม่เขียน audit สำเร็จตั้งแต่รับเข้าคิว
   - ทุนไม่ผ่าน หรือ key เดิมกับ payload ต่างกัน: INSERT admission result และ rejection audit
     แบบ atomic แล้วคืนหลัง transaction commit; UNIQUE(user, action, key, request fingerprint,
     failure code) ทำให้ retry rejection เดิมคืนผลเดิมโดยไม่เพิ่ม audit ซ้ำ
   request fingerprint สร้างจาก action + normalized structural fields ด้วย hash กลาง
   และไม่เก็บ/สะท้อน raw invalid input ใน result, audit, log หรือ error
4. Paper worker ใช้ ENGINE_SCAN อ่านเฉพาะ metadata ที่ `next_attempt_at` ถึงเวลา
   แล้วเปิด ENGINE UserSession ของ owner เพื่อ atomic claim dispatch ด้วย claim UUID/worker/expiry
   ใช้ transaction-scoped advisory lock namespace ของ Paper + owner ก่อนทุก write
   ล็อกนี้ใช้ได้แม้ยังไม่มีกระเป๋า; collision ทำให้รอเท่านั้น ไม่ให้ข้าม RLS
   หลังได้ lock ตรวจ claim ยังเป็นของตนและ result ซ้ำ ก่อนสร้างข้อมูลใด ๆ
5. CREATE ตรวจ owner มี wallet แล้วหรือไม่ จากนั้นสร้าง wallet/episode/state/ทุน/result/
   success audit ใน transaction เดียวกัน; existing wallet เป็น terminal rejection
   ไม่มีข้อมูลครึ่งชุดหาก query, audit, commit หรือ worker ล้ม
6. RESET ต้องเทียบ expected_episode_id ภายใต้ lock กับ active episode
   เพื่อกันสอง key ที่กดจากรอบเดิมสำเร็จต่อกันสองครั้ง แล้วตรวจ authoritative activity
   ตามข้อยุติ NC-F13-02; unknown/unavailable ปฏิเสธ ไม่เปลี่ยน pointer
7. เมื่อหลักฐานปลอดภัยครบเท่านั้น จึง append closure/episode/ทุนใหม่, ย้าย pointer
   และเขียน result/audit ใน transaction เดียวกัน ไม่มีการย้ายยอดหรือ PnL ข้ามรอบ
8. domain rejection หลังเข้าคิวเขียน terminal rejection result + rejection audit แบบ atomic
   แล้วจึงคืน error ไม่ raise จน transaction ที่บันทึกการปฏิเสธ rollback
   infrastructure failure ให้ transaction rollback ทั้งชุด คำขอยังค้างเพื่อ recovery
   ห้ามบันทึกผลสำเร็จปลอมเมื่อ audit ใช้ไม่ได้

processor รันซ้ำจากคำขอไม่มี result ได้หลัง restart; commit สำเร็จแต่ response หาย
ให้ retry key เดิมอ่าน result เดิมโดยไม่ทำซ้ำ ไม่มี in-memory claim เป็นแหล่งจริง
ผล terminal ที่ถูกปฏิเสธ replay ผลเดิม; ต้องส่ง key ใหม่หากตั้งใจเริ่มการกระทำใหม่
idempotency/admission result records ไม่มี TTL ใน F-13 เพราะการลบทำให้ key เดิมทำซ้ำได้
replay คืน snapshot ตอนทำรายการ ไม่เอายอดปัจจุบันมาสวมเป็นผลเดิม

เพิ่ม `Bucket.PAPER_WALLET_MUTATION` และ migration ขยาย CHECK ของ `api_throttle`
โดยใช้ token-bucket/storage/`spend_token` เดิม ค่าเริ่มต้นที่เสนอคือ capacity 3 และเติม
หนึ่ง token ทุก 20 นาทีต่อผู้ใช้ รวม CREATE/RESET และ payload conflict ไว้ถังเดียวกัน
เพื่อไม่ให้สลับ action หรือ idempotency key เพื่อได้โควตาใหม่ exact replay ที่พบภายใต้
admission lock ไม่ใช้ token เพิ่ม ส่วนทุก attempt ใหม่ใช้ token แม้ลงท้ายด้วย domain rejection
การโดน 429 ไม่สร้าง command/result/audit และ client ต้องรอ ไม่ retry อัตโนมัติ
ตัวเลขนี้เป็นส่วนของ plan ที่ต้องได้รับอนุมัติก่อน implementation และทบทวนเมื่อมีข้อมูลจริง

แยก entrypoint `services/engine/paper_wallet_main.py` และ orchestration
`services/engine/paper_wallet.py` จาก key-verification loop เดิม
เพื่อให้เริ่ม Paper worker ได้โดยไม่โหลด sealing key, HTTP client หรือ venue factory
เสนอ polling ทุก 500ms, ครั้งละไม่เกิน 20 commands, transaction lock/statement timeout
5s, claim lease 30 วินาที และปิด transaction เมื่อ cancel; หลาย worker ใช้ claim + lock
ชุดเดียวกัน ไม่ให้ถือ lock ข้าม network call ส่วน key verification เดิมไม่เปลี่ยน
known infrastructure failure ของแต่ละ command ถูกจับแยกจากคำขออื่นแล้ว schedule ด้วย
backoff 1s, 5s, 30s, 5m และคงเพดาน 5m พร้อมเพิ่ม attempt count; ไม่สร้าง terminal
business result หรือ audit ปลอม Unknown programming error ต้อง log fixed context
(command id/attempt เท่านั้น), ปล่อย claim หมดอายุ และ worker เดินคำขออื่นต่อ
การเลือกงานเรียง `next_attempt_at, requested_at, id` และต้องมี fairness test ว่าแถวที่ล้มซ้ำ
ไม่ขวางแถวพร้อมทำงานของผู้ใช้อื่น เมื่อฐานข้อมูลกลับมาหลัง outage คำขอเดิม recover ได้

## 5. API และ UI ที่เสนอ

| Endpoint | สัญญา |
|---|---|
| GET `/paper-wallet` | owner snapshot หรือ `wallet: null`; mode, wallet/episode ID, sequence, ทุน/ยอด exact string, started_at, snapshot_at, revision และ reset availability/reason |
| POST `/paper-wallet` | `{initial_capital: string}` + Idempotency-Key; คืน result ถ้ามีแล้ว มิฉะนั้น 202 + command_id/status URL |
| POST `/paper-wallet/reset` | `{initial_capital: string, expected_episode_id: UUID}` + Idempotency-Key; ไม่รับ owner/mode จาก client |
| GET `/paper-wallet/commands/{command_id}` | owner-only PENDING หรือ terminal result เดิม; foreign/missing ตอบ 404 เหมือนกัน |

schema extra forbid และ strict string; ตัวเลข JSON/bool/null ถูกปฏิเสธ
proposed error mapping: 422 INPUT_REJECTED, 409 WALLET_EXISTS/IDEMPOTENCY_CONFLICT/
EPISODE_CONFLICT/RESET_UNSAFE/ACTIVITY_UNKNOWN, 503 DEPENDENCY_UNAVAILABLE
terminal result ระบุรหัสเดียวกัน; GET status ยังคง 200 เมื่อพบ command
POST ที่ replay terminal failure คืน error เดิม ข้อมูลไม่มี raw driver/stack/input echo
GET snapshot ใช้ statement เดียวหรือ REPEATABLE READ transaction ที่ตั้งก่อน SELECT
รวม active pointer/ทุน/ledger/revision ให้สอดคล้อง ไม่อ่านหลาย statement แบบ READ COMMITTED

ROUTE_RULES: GET ไม่ renew, POST renew พร้อม CSRF; ไม่เพิ่ม fresh TOTP สำหรับ Paper
ใช้ safe input และ token-bucket implementation เดิมกับ bucket ใหม่ตาม §4
ไม่เพิ่มข้อบังคับ Live/API-key กับกระเป๋าจำลอง
worker ยังไม่ทำงานให้แสดง PENDING ไม่แสดงสำเร็จ/ยอดใหม่และไม่สร้าง key ใหม่อัตโนมัติ
UI poll command เดิมทุก 1s ขณะ mount; logout/unmount/401 ต้อง cancel
หาก network error เกิดหลังส่งให้คง key/payload สำหรับ retry เดิม ไม่ auto-resubmit mutation

วาง `PaperWalletPanel` ภายในหน้าบัญชีเทรดเดิมของ `AuthPanel` และ `AccountSession`
ไม่เปลี่ยน layout/order placeholders ของ F-12; แสดง PAPER ชัด, ทุน, ยอด, episode,
เวลาเริ่มและเวลาของ snapshot ผ่าน MarketValue/MarketTime
ช่องเงินใช้ Input type text + inputMode decimal; frontend ไม่เทียบเงินด้วย Number,
parseFloat หรือคำนวณเงิน ไม่แสดง optimistic balance
reset confirmation อธิบายเริ่มรอบใหม่และเก็บประวัติเดิม; disabled พร้อมเหตุผลเมื่อ
server ยังพิสูจน์ไม่ได้ ข้อความ TH/EN ผ่าน i18next ตาม pattern เดิม
query key รวม identity; delayed response ของ user เดิมต้องไม่เปลี่ยน UI user ใหม่
refetch error ต้องแสดงว่ายอดเป็น snapshot เก่า ไม่เปลี่ยนเป็น 0 หรือถือว่าไม่มี wallet

## 6. สิ่งที่จะแก้และ milestones หลังอนุมัติ

| กลุ่มไฟล์ | เปลี่ยนอะไร |
|---|---|
| `backend/src/tiewtrade/core/paper_wallet.py` | pure validation/fold/domain errors |
| `backend/migrations/versions/0031_paper_wallet.py` | additive schema, policies, grants, constraints และ audit shapes |
| `backend/src/tiewtrade/infra/paper_wallet/{records,storage,commands,activity}.py` | owner-only persistence, immutable history, lock, replay และ activity contract หลัง NC ปิด |
| `backend/src/tiewtrade/infra/audit/{events,__init__}.py` | typed actions/details; writer ใช้ของเดิม |
| `backend/src/tiewtrade/services/engine/paper_wallet{,_main}.py` | isolated Paper processor/entrypoint |
| `backend/src/tiewtrade/services/api/{paper_wallet_routes,app,routing_policy}.py` | input/read/result routes และ policy |
| `backend/openapi.json`, `frontend/src/api-types.ts` | regenerate ด้วยเครื่องมือเดิม ไม่แก้ด้วยมือ |
| `frontend/src/{PaperWalletPanel.tsx,paperWallet.ts,paperWalletMessages.ts,TradingAccountPanel.tsx}` | panel, exact contracts, mutation/status และแปลข้อความ |
| `frontend/src/components/ui/Modal.tsx` หากจำเป็น | ปรับจาก template ที่ระบุ พร้อม accessible focus; ไม่เพิ่ม library |
| `backend/tests/{core,infra,api,services,gates}/`, `frontend/tests/`, `frontend/e2e/` | cases ตาม validation และ safety gate พร้อม negative fixtures |
| `.github/workflows/ci.yml` เฉพาะที่จำเป็น | ให้ E2E เริ่ม isolated Paper worker; คง required gates เดิม |

1. **M0 — Spec checkpoint:** requirements/plan/validation Approved วันที่ 2026-10-15;
   NC-F13-02 ปิดด้วยการส่ง create/read ก่อนและ fail-closed reset ตาม §8
2. **M1 — Domain/DB:** เขียน failing numeric/property/RLS/immutability tests ก่อน,
   แล้วทำ schema/storage; ผ่าน V-1..4 และส่วน transaction ของ V-6
3. **M2 — Worker/contract:** ทำ command processing/API/audit/recovery;
   ผ่าน V-5..11 รวม authoritative reset ตามคำตอบที่อนุมัติ ห้ามใช้ mock proof ปิด production gate
4. **M3 — UI/end-to-end:** ทำ panel และ generated contracts ผ่าน V-12..14
5. **M4 — Candidate:** ปิด review findings และด่าน V-15 สำหรับ candidate สุดท้าย
   ส่ง checkpoint พร้อมหลักฐาน/งานค้าง; commit/push/merge เมื่อเจ้าของสั่งเท่านั้น

ระหว่าง milestones ทำต่อภายในขอบเขตที่อนุมัติ ไม่ขออนุมัติซ้ำทุก test/fix
บันทึกเวลาอ่าน/เขียน/ตรวจ/รีวิว/รอใน checkpoint เดิมตาม testing §7
ยังไม่มี implementation หรือผลตรวจผ่านในขั้นเอกสารนี้

## 7. ความเสี่ยงและการกู้คืน

| ความเสี่ยง | วิธีควบคุม / เกณฑ์พิสูจน์ |
|---|---|
| API เขียนเงินข้าม engine | DB grants ปฏิเสธ direct write, import/runtime Paper gate; V-3/11 |
| duplicate/restart หลัง commit | unique input/result/source, lock และ replay; V-5/9 |
| malformed/duplicate requests ทำให้ audit หรือคิวโต | admission result dedupe + mutation token bucket; V-5/14 |
| reset race / old tab | expected episode + lock ที่ writer ทุกตัวใช้; V-7 |
| พิสูจน์ idle จากข้อมูลไม่ครบ | ACTIVITY_UNKNOWN, ไม่มี reset สำเร็จจนปิด NC; V-8 |
| เงินถูก DB ปัดหรือ browser ทำเลขเพี้ยน | domain/adapter Money เดิม, strict string และ exact UI; V-1/2/12 |
| ประวัติถูกแก้หรืออ่านข้าม user | append-only triggers + FORCE RLS/composite FK; V-3/4 |
| snapshot ประกอบคนละรอบ | transaction snapshot, parity กับ ledger; V-10 |
| worker ล่ม/แถวเสียขวางคิว | durable dispatch claim, bounded backoff/fair ordering และ restart recovery; ไม่แตะ Live/venue; V-9/13 |

## 8. NC-F13-02 — Closed (2026-10-15)

**แหล่ง authoritative และจังหวะเปิด reset สำเร็จ**

ตรวจ migration ถึง 0030 และ engine/infra ปัจจุบันแล้ว ยังไม่มี position/order store
หรือ common account writer ที่รายงาน activity ได้ F-08 ปฏิเสธการเปลี่ยนประเภทด้วย
ACTIVITY_UNKNOWN ด้วยเหตุนี้ การถือว่าตารางยังไม่มีเท่ากับไม่มี position/order
หรือสร้าง `is_idle=True` ขึ้นเองจะไม่พิสูจน์ RQ-6 และอาจเปิด reset หลังมีงานค้าง

เจ้าของอนุมัติแนวทางต่อไปนี้:

- ในระยะ F-13 ให้ create/read ใช้งานได้ แต่ reset ตอบ ACTIVITY_UNKNOWN
  จน F-14/F-15 มี authoritative activity และใช้ lock เดียวกันจริง; จึงค่อยตรวจรับ
  reset success และปิด F-13 ตามเกณฑ์ครบ ไม่ถือว่า F-13 Completed ก่อนหน้านั้น
- หากจะเปิด reset สำเร็จ ต้องกำหนดและอนุมัติหลักฐาน authoritative
  สำหรับระยะที่ยังไม่มี position/order รวมวิธีถอนหลักฐานนั้นเมื่อเปิด writer รุ่นถัดไป
  แล้วเติม schema/locking/integration ในแผนและ validation ก่อนเขียนโค้ด

คำตัดสินนี้ไม่เปลี่ยน RQ-6 หรือทำให้ unknown กลายเป็น safe โดยปริยาย
V-7/V-8/V-13 ส่วน reset success ยังคง Not Run และ F-13 คง In Progress จนมีหลักฐานครบ
