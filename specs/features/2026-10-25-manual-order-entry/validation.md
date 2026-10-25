# F-16 — สั่งออเดอร์เองผ่านหน้าจอ — Validation

สถานะ: **Approved — เจ้าของตอบ “approve” ต่อ plan/validation ฉบับแก้ F16-R1/R2/R3 วันที่ 2026-10-25**
วันที่: 2026-10-25
Requirements: **Approved 2026-10-25**

## “เสร็จ” หมายถึง

ผลทั้งหมดด้านล่างยังไม่ใช่ Passed เอกสารนี้กำหนดการตรวจล่วงหน้า ไม่ใช้ผล F-15/F-37
เดิมแทนหลักฐานของเส้นทางรับคำขอใหม่ และไม่เปิด Live order ใน automated validation

| # | เกณฑ์ / สิ่งที่พิสูจน์ | ตรวจอย่างไร | ระยะรัน | ผล / หลักฐาน |
|---|---|---|---|---|
| V-1 | รับเฉพาะสามรูปแบบ NC-08 และหน่วยถูกต้อง | API/schema + form tests: MARKET BUY quote, MARKET SELL base, LIMIT BUY/SELL base+price/GTC; reject extras, JSON number, invalid precision/range, zero/negative, unsupported kind/TIF; exact decimal round trip | M1/M3 | Passed — local M1–M4 evidence; test composition only |
| V-2 | Owner/mode isolation และ API ไม่เขียนเงิน | PostgreSQL runtime roles จริง: ข้าม owner/ไม่มี owner อ่านไม่พบ/เขียนไม่ได้; API อ่าน joined command/result/header/projection ได้เฉพาะคอลัมน์ที่อนุมัติ เขียน financial table/อ่าน secret ไม่ได้; request discovery/by-key ข้าม owner ไม่ได้; mode/origin/actor จาก client ถูกปฏิเสธ; scan role เขียนหรืออ่าน payload ไม่ได้ | M1 | Passed — local M1–M4 evidence; test composition only |
| V-3 | คำขอซ้ำมี financial effect ครั้งเดียว | real DB concurrent same-key/same-payload → request/order/linked F-15 command หนึ่งชุด; key เดิม payload ต่าง → conflict; NEW/CANCEL namespaces ชัด; replay หลัง episode ปิดยังได้ผลเดิม; intake/command catalog revision เดิมไม่เปลี่ยนเมื่อ replay และ response loss→reload ยังใช้ key เดิม | M1/M2 | Passed — local M1–M4 evidence; test composition only |
| V-4 | Durable inbox/audit/result atomic และ immutable | บังคับ audit/insert/commit error → ไม่เกิด partial accepted record; update/delete/truncate ถูกปฏิเสธด้วย runtime role; CHECK/invariant ปฏิเสธ shape ผิด; upgrade/downgrade guard บนข้อมูลจริง | M1 | Passed — local M1–M4 evidence; test composition only |
| V-5 | PAPER ไม่เข้าถึง Live executor/credentials | ขยาย isolation gate ของ F-15 ให้ครอบ API→inbox→bridge→worker; instrument outbound order/credential operations ให้ fail หากเรียก; Live page ไม่ยิง Paper mutation แม้แก้ URL/payload | M2/M3 | Passed — local M1–M4 evidence; test composition only |
| V-6 | MANUAL/BOT และลดความเสี่ยงใช้ authoritative state | engine composition fixtures: MANUAL เปิดได้เมื่อ gates พร้อม, BOT/ไม่มี use เปิดไม่ได้, ลดตาม held หลัง reservations ได้ทุกประเภท; oversized SELL/unknown holding ไม่ถูกจัดเป็นลด; หยุดบอทไม่เปลี่ยน use; ไม่มี TOTP เพิ่มสำหรับลด/cancel | M2 | Passed — local M1–M4 evidence; test composition only |
| V-7 | Pending intake บล็อก reset และไม่ข้าม episode | controlled concurrent API intake/reset/engine transfer/fill ด้วย barriers บน PostgreSQL; readiness function/API/engine reset เห็น pending; ผล serialize เป็น intake ก่อนและ reset ปฏิเสธ หรือ reset ก่อนและ intake episode เก่าปฏิเสธ; rollback ไม่ทิ้ง phantom pending | M1/M2 | Passed — local M1–M4 evidence; test composition only |
| V-8 | Lease/retry/crash ไม่ส่งซ้ำหรือเขียนทับ worker ใหม่ | PostgreSQL tests สอง workers, claim expiry/CAS, process disconnect/kill ก่อนและหลัง transfer commit; linked identity/result ต่อ request เดิม, no orphan executable command หรือ duplicate reservation/fill | M2 | Passed — local M1–M4 evidence; test composition only |
| V-9 | Catalog fence ใช้ได้กับ entrypoint ใหม่ | หยุด bridge หลัง inbox commit แล้ว remove→re-add ก่อน transfer ต้อง reject โดยไม่มี F-15 command; หลัง transfer แล้ว remove→re-add ก่อน execution ต้อง reject เช่นกัน; assert command เก็บ admitted_catalog_revision เท่ากับ intake เดิมและ replay ไม่ refresh revision; intake ก่อน/หลัง removal ต้อง serialize ที่ pair fence; BUY ที่ถูก invalidate ไม่กลับเปิดเอง; existing bounded SELL/cancel ผ่านตาม F-37 โดยไม่เปลี่ยน position เดิม; metadata/filter ไม่รองรับยัง reject | M2 | Passed — local M1–M4 evidence; test composition only |
| V-10 | บันทึกไม่ได้ปฏิเสธแม้ลด/cancel | inject DB unavailable, audit failure, transaction rollback, lost acknowledgement: ไม่มี side effect สำหรับ rollback; outcome ไม่ทราบแสดง UNKNOWN; lookup/replay key เดิมตรวจ commit จริงก่อนตอบ ไม่สร้าง key/order ใหม่; reload ขณะ request ยัง in-flight และ lookup 404 ต้องยัง UNKNOWN; journal write/read failure ก่อนส่งต้องไม่เกิด POST | M1/M2/M3 | Passed — local M1–M4 evidence; test composition only |
| V-11 | Snapshot/list/status ถูกต้องและไม่รั่ว | repeatable-read cash/reservation/available/held จาก backend ตรง ledger/projection; source unknown ไม่แสดง 0/READY; cursor owner/episode/filter mismatch ไม่รั่ว; bounded limit, 404 uniform, stale/closed episode และ empty wallet; joined response intake TRANSFERRED/command REJECTED คืน code ได้แม้ไม่มี paper_orders; discovery พบ unresolved ทุก episode และ traverse ได้โดยไม่ข้าม owner; broken transfer link เป็น integrity error ไม่แต่ง state | M1/M2 | Passed — local M1–M4 evidence; test composition only |
| V-12 | Financial results ผ่าน API bridge ตรง F-15 | same fixture inputs ผ่าน bridge และ internal F-15 baseline ให้ intent/events/reservations/fills/ledger/position ผลเท่ากัน; partial/expire/cancel races; hand-calculated examples และ generated duplicate/reorder inputs ไม่เปลี่ยน invariant | M2 | Passed — local M1–M4 evidence; test composition only |
| V-13 | API auth/CSRF/throttle/input/error contracts | API tests unauthenticated, CSRF absent/invalid, forged IDs, rate bucket independence, Retry-After, replay ไม่กิน quota ซ้ำ, 503 policy/dependency unavailable, safe coded errors ไม่มี raw payload/credential/SQL; generated OpenAPI ตรง frontend | M2 | Passed — local M1–M4 evidence; test composition only |
| V-14 | UI แสดงผลจริงและ recover ได้ | component tests: request pending≠order accepted≠filled, cancel pending≠canceled, partial/expired/rejected, UNKNOWN recovery หลัง reload/unmount ด้วย write-before-send journal, same-key retry, discovery failure ไม่แสดงว่าไม่มี pending/เปิดส่งใหม่, no optimistic balance; transfer terminal แต่ command pending ต้อง poll ต่อ, command rejected ไม่มี order แสดงเหตุได้, NEW succeeded ยังติดตาม active order, CANCEL succeeded แต่ target FILLED ห้ามแสดง canceled; journal/queries ล้างเมื่อ logout/เปลี่ยน owner; poll/invalidation หยุดตาม route/visibility/logout และ cache ไม่ข้าม owner/episode/mode | M3 | Passed — local M1–M4 evidence; test composition only |
| V-15 | UI ตรง admin template และใช้ได้จริง | visual/manual inspection ตาม checklist ด้านล่าง + keyboard/focus tests; Thai/English/light/dark/mobile/desktop; ไม่มี local money math/native style ที่แทน shared pattern | M3 | Passed — local M1–M4 evidence; test composition only |
| V-16 | เส้นทาง browser→API→DB→engine→UI ต่อครบ | Chromium isolated Paper harness ใช้ real PostgreSQL/production API/inbox/bridge/F-15 และ recorded source พร้อม explicit test policy: MARKET BUY/SELL, LIMIT partial→cancel, receipt loss→reload→lookup/discovery→same-key retry, command rejected หลัง transfer โดยไม่มี order row, partial cancel/target already FILLED, episode reset race, route reload/back/forward, logout/login owner เดิมและสลับ owner, journal storage failure และ Live unavailable; assert DB identities/effects ไม่ใช่ screenshot อย่างเดียว | M3 | Passed — local M1–M4 evidence; test composition only |
| V-17 | Dependency ไม่พร้อมไม่เปิดคำสั่งโดยอ้อม | production composition ใช้ policy=None; GET readiness blocked และ POST NEW 503 ไม่มี executable inbox row; forged request/UI enabled flag/test env ใช้เปิดไม่ได้; queued execution recheck gate; cancel ของ order เดิมไม่ต้องผ่าน opening policy | M2/M3 | Passed — local M1–M4 evidence; test composition only |
| V-18 | Production Paper order admission พร้อมจริง | หลัง F-18 ได้รับอนุมัติ/implement: เชื่อม risk policy จริงกับ account/price/catalog/order gates, safety/parity tests สำหรับ loss-limit/unknown/price outage/ลดความเสี่ยงตาม trading-safety; full browser→engine acceptance ด้วย production composition และเกณฑ์ที่ F-18 กำหนด | Integration checkpoint หลัง F-18 ก่อน activation/Completed | Pending Dependency — F-18; ห้ามแทนด้วย test policy |
| V-19 | Final candidate ผ่าน review และด่านก่อน merge | แจ้ง Ready for Code Review; resolve Critical/High และ findings ใน scope, backend full regression/lint/format/mypy/import-linter, frontend lint/types/tests/build, API generation/check, Chromium E2E, config/docker/required CI บน candidate สุดท้าย | M4 ก่อน merge | Partial — local review/checks ผ่าน; existing E2E/Docker/required CI ยัง Pending |
| V-20 | Release acceptance รวมเส้นทาง F-16 ไม่ทำให้ order/resource guarantees เสื่อม | ตรวจรวมเส้นทางใหม่นี้ใน release profile ที่อนุมัติ โดยคงเกณฑ์/duration/threshold ของ F-15 V-19/W1–W4 และ dependency release validation ที่เกี่ยวข้อง; บันทึก affected frontend/API intake/queue/recovery/resource evidence บน final candidate ไม่ใช้ targeted smoke รับรองแทน | ชุดที่ 9 / release checkpoint ก่อน Completed | Pending Full Validation — ยังไม่รัน; ต้องมี approved integrated release profile ก่อนเริ่ม |

V-18 เป็น dependency ด้าน correctness/safety ที่ยังไม่พร้อม ไม่ใช่งานโหลดที่เลื่อนแล้ว
ถือว่าผ่านได้. M4 merge เพื่อพัฒนาต่อได้เฉพาะเมื่อ V-1–V-17/V-19 ผ่านครบ และคง
production admission ปิด; ต้องติดตาม V-18/V-20 ใน roadmap ก่อนเรียก Completed
เกณฑ์ Live execution/reconciliation/activation ไม่รับรองโดย F-16 และไม่มี Live order test

## การเลือกตรวจตามผลกระทบ

| ผลกระทบ | หลักฐานเดิมที่ใช้ตั้งต้น | ช่องว่างที่ต้องตรวจเพิ่ม |
|---|---|---|
| Input และ serialization | OrderIntent/codec/Money/Quantity tests เดิม | untrusted API schema, strings→domain→DB→response และ form field switching |
| Inbox กับ single writer | F-15 dispatch/worker tests, F-13 reset tests | pending ก่อนเข้าคิว F-15, transfer atomicity, two queues, scanner lease/owner roles และ joined downstream result เมื่อไม่มี order row |
| Financial effects | F-14/F-15 deterministic fixtures และ property tests | API bridge ไม่เปลี่ยน intent/episode/size/identity; concurrency ผ่าน entrypoint ใหม่ |
| Catalog | F-37 catalog/order-safety ready evidence | pin authoritative revision ตอน intake และรักษาถึง F-15; receipt ก่อน removal/transfer หลัง removal และ remove→re-add ผ่าน inbox ใหม่ |
| Audit/DB roles | audit invariant/migration/RLS tests เดิม | intake actions ใหม่และ API privileges ที่เพิ่ม, rollback/commit ambiguity |
| UI/server cache | PaperWalletPanel/AccountSession/MarketValue/navigation tests | หน้าแยก URL, write-before-send/reload/storage failure recovery, server discovery, pending/command/order lifecycle และ user/episode/mode cache scope |
| Risk integration | F-15 policy=None fail-closed proof | F-18 ยังไม่มี production policy จึงแยก V-17 ผ่านเมื่อปิดถูกต้อง กับ V-18 รอพร้อมจริง |

เลือก tests จาก behavior/callers/contracts/DB/concurrency ที่ diff เปลี่ยน ไม่เลือกตามชื่อไฟล์อย่างเดียว
ใช้ test เดิมก่อนเพิ่มเมื่อยังไม่ครอบคลุม; unit, integration และ browser ต้องพิสูจน์คนละชั้น
Financial/safety failures ต้องแก้ทันที ไม่เลื่อนไป V-20

## ตัวเลขจริงและคุณสมบัติ

- ใช้ hand-calculated fixtures ใน F-15 validation ได้แก่ round trip ETH ที่ราคา 100→120,
  fee-in-received และ partial MARKET 150 ที่ liquidity เพียง 1@99 กับ 0.5@101;
  ผูกผล API/read model กับ expected cash/base/reservation เดิมไม่คำนวณ expected จาก code
- ใช้ reserve race เดิม cash 150 กับ LIMIT BUY 1@100 สองใบ รับได้ไม่เกินหนึ่งใบ;
  ทดสอบใหม่ผ่านคนละ inbox request/worker เพื่อครอบ boundary ที่เพิ่ม
- Hypothesis: same-key retries ไม่เพิ่มจำนวน intents/effects, duplicates ไม่เพิ่ม reservation,
  available ไม่ติดลบ, no sale above unreserved holding, cancel ไม่ย้อน confirmed fill,
  ledger/position ต่อ episode ไม่ข้าม owner หรือ mode
- ไม่มีสูตรเงินใหม่โดยตั้งใจ หากต้องเพิ่ม arithmetic ต้องทำใน core/money ตามกฎเดิม
  และมี hand-calculated/property tests ก่อนรับ ไม่ใช้ browser number หรือ float เป็น oracle

## Browser harness และการตรวจด้วยมือ

harness แยกจาก runtime deployment เช่น pattern `backend/tests/e2e_catalog_app.py`;
ใช้ test-only composition และ recorded market inputs เท่านั้น ไม่มี allow-all factory ที่
production import ได้และไม่มีการเพิ่ม Live request. UI network interception ที่ fake ผล
ใช้ทดสอบ presentation ได้ แต่ไม่นับผ่าน V-16 ซึ่งต้องยืนยัน DB/engine จริง

Checklist V-15/V-16:

1. เข้า `/paper/trade` ด้วย session จริง เห็น PAPER ตลอด, wallet/no-wallet และ readiness
   พร้อม snapshot time; production composition เห็น blocked reason ของ F-18 จริง
2. ใน harness เลือกแต่ละ kind/side ตรวจหน่วยตรง NC-08 และส่งข้อความ decimal exact;
   เช็คคำขอ pending, partial/filled/expired/rejected และยอดจาก server โดยไม่เดา fill
3. LIMIT partially filled แล้ว cancel: หน้าจอคง fill ที่ยืนยันแล้วและคืนเฉพาะส่วนที่ server ยืนยัน
4. ตัด response หลัง commit แล้ว reload/ออกหน้าแล้วกลับ: restore journal และตรวจด้วย key
   เดิม เห็นคำขอ/order เดิม ไม่ส่ง POST อัตโนมัติ; ลบ journal หลัง commit เพื่อทดสอบ discovery
   แยกต่างหาก; กรณี request ยัง in-flight และ lookup 404 ต้องไม่เริ่ม draft เดิมด้วย key ใหม่
   journal เขียนไม่ได้ต้องไม่มี POST; ตัด DB ก่อน commit ต้องไม่มี orphan effect ในฐานข้อมูล
5. บังคับ worker reject หลัง transfer ก่อนสร้าง order: request lookup คืน command failure
   และ order_state=null แทน 404; CANCEL ที่ target FILLED ต้องแสดง FILLED ไม่ใช่ CANCELED
   เปิดคนละ user/episode และ logout/login: ไม่มี orders/balances/errors/journal ของคนก่อนค้าง;
   เปลี่ยนไป `/live/trade` แล้ว reload/back/forward ไม่ยิง Paper mutation หรือเปิด Live
6. Keyboard เข้าถึงทุก control, label/error association, focus-visible, loading/disabled,
   screen-reader status ประกาศผลอย่างเหมาะสม; ไม่ใช้สีอย่างเดียวบอก mode/error/status
7. เปรียบเทียบกับ template paths ใน plan §2 ที่ mobile 375px และ desktop 1440px
   รวม light/dark, default/hover/focus/error/disabled/loading และภาษาไทย/อังกฤษ;
   ตารางเลื่อนแนวนอนได้ตาม template ไม่ทับ form หรือซ่อนผลคำสั่งสำคัญ

## ด่านที่ต้องเขียวและหลักฐาน

ระหว่างพัฒนาเริ่มจาก targeted checks ที่พิสูจน์ diff; ไม่รันชุดเต็มหลังทุก patch
ก่อน merge เมื่อ candidate นิ่ง:

- backend ใน `backend/`: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy`, `uv run lint-imports`, `uv run pytest` พร้อม PostgreSQL/migrations จริง
- frontend ใน `frontend/`: `npm run lint`, `npm run typecheck`, `npm run test`,
  `npm run build`; export OpenAPI และตรวจ generated types ตาม CI เดิม
- Chromium E2E เดิมและ manual-order harness ใหม่, config/Docker และ required CI
  ตาม `.github/workflows/ci.yml`; ไม่ใช้ local green แทน CI บน final commit
- บันทึกคำสั่ง/environment/revision+uncommitted diff/ผล/เวลาที่วัด และ V ที่ครอบคลุม
  ใน evidence checkpoint เดิม; ตรวจซ้ำเฉพาะผลที่ inputs/dependencies เปลี่ยนหรือยังไม่พอ
- อ่าน/วางแผน, implementation, tests/static/build, review และรออนุมัติแยกช่วงที่วัดได้;
  ช่วงไม่ได้วัดระบุว่าไม่ได้วัด ไม่แต่งเวลารวม และไม่รวมเวลางานขนานซ้ำกัน

ชุด performance/workload/stress/endurance/resource ตาม V-20 อยู่ release checkpoint
ไม่รัน timed smoke อัตโนมัติท้าย milestone หากมี risk จำเป็นต้องรันก่อนต้องแจ้งเหตุ
ขอบเขตและเวลาคาดหมายตาม testing §7 ก่อนรัน. ไม่ลดเกณฑ์ที่อนุมัติไว้ของ dependency
และห้ามเปลี่ยน Failed/Partial เดิมให้เป็น Passed เพราะ targeted run ผ่าน

## Document review corrections — 2026-10-25

F16-R1/R2/R3 ผูกกับเกณฑ์เดิมตาม plan §9 โดยเพิ่มกรณี repro เฉพาะช่องว่างที่พบ
ไม่เพิ่ม milestone หรือรัน workload ซ้ำ; ผล runtime ทุกข้อยัง Not Run/Pending
การตรวจเอกสารแก้ไขครอบคลุม catalog revision continuity, joined command outcomes,
reload recovery/owner isolation และความสอดคล้องของ API/สิทธิ์/polling

## M1 checkpoint — 2026-10-25

ดู [หลักฐาน contract/persistence](evidence/m1-contract-persistence.md).
V-1/2/3/4/7/10/11 ส่วน input/inbox/DB/owner/replay/reset/request reader ผ่าน targeted checks
แต่ผลรวมของ V เหล่านี้ยัง **Partial** เพราะ public API/bridge/UI ที่เกี่ยวข้องรอ M2/M3;
V อื่นยัง Not Run และ V-18/V-20 คง Pending ตามตาราง. ไม่มีการใช้ M1 แทน candidate gates

## M2 checkpoint — 2026-10-25

ดู [หลักฐาน engine/API](evidence/m2-engine-api.md) สำหรับคำสั่ง/ผลจริง/เวลาที่วัด
และ failures ที่แก้แล้ว. V-1/2/3/4/5/6/7/8/9/10/11/12/13/17 ขยับเป็น **Partial**
ในขอบเขต backend ที่ระบุในหลักฐาน; ตารางเดิมเป็นเกณฑ์ฉบับอนุมัติและไม่ถูกลดขอบเขต.
V-14/15/16 ยัง Not Run, V-19 รอ M4, V-18/V-20 คง Pending. ไม่มี production activation.

## M3/M4 checkpoint — 2026-10-25

ดู [M3 UI](evidence/m3-ui.md) และ [M4 candidate review](evidence/m4-candidate-review.md)
สำหรับsource mapping, findings/fixes, actual test commands/results/timingและremaining risks.
Ready for Code Review แจ้งก่อน formal reviewแล้ว. V-1–V-17 ผ่านใน local development/test
compositionตามหลักฐาน; ไม่ใช้testpolicyแทนV-18. V-19ยังPartialเพราะexistingE2E/Docker/
requiredCIบนfinalcommitยังไม่ผ่านครบ จึงยังไม่พร้อมmerge/Completed. V-18/V-20คงPendingเดิม.
ผลfailure/partialระหว่างcandidateเก็บไว้ในledger ไม่แทนด้วยคำว่าfullsuiteเขียวหนึ่งรอบ.

### Deep-review fix verification — 2026-10-25

Additional Medium findings for closed-episode recovery and draft rebasing are resolved;
see the remediation section in [M4 evidence](evidence/m4-candidate-review.md).
Affected V-3/7/10/13/14/16 verified with49 backend tests,23 frontend tests and1 new real
Chromium flow. Generic409/lookup404 remain UNKNOWN; only explicit owner-bound immutable
closure proof resolves an absent old-episode attempt. Existing receipts replay first.
V-18/V-19/V-20 keep their pending/partial status; these targeted results do not replace CI.


### V-19 gate follow-up — 2026-10-25

Docker build/start/migration/API/frontend gate passed; catalog Chromium2/2 and F-16
Chromium7/7 passed. Existing Chromium remains Partial: four chart cases lack passing
results after the F-16-related source-URL false positive was fixed and verified.
Live-snapshot failure also reproduces with base-commit backend sources on the isolated
schema0042 environment; root cause remains open. See [M4 evidence](evidence/m4-candidate-review.md)
for failed attempts, comparison limits and logs. Required CI still pending; no commit/push.
V-18/V-20 unchanged; not ready to merge or Completed.


### Resumed V-19 verification — 2026-10-25

Existing Chromium now passed **18/18 /1.7m**, including the four outstanding chart cases,
after restoring the isolated test runtime; application code/deadlines were unchanged.
Local Docker/catalog2/2/manual7/7 evidence remains valid. See [M4 evidence](evidence/m4-candidate-review.md)
and its retained run log. Earlier failures remain recorded and their root cause is not
established. V-19 remains **Partial — required CI on final commit pending**; V-18/V-20
unchanged. No commit/push/merge or production activation.


### PR integration — 2026-10-25

Initial candidate7f51fdc passed6/6 push CI jobs. PR#36 now integrates main's approved
F-14/F-15 fixes; affected financial/recovery tests134 passed, Ruff and mypy src passed.
V-19 merge acceptance must use CI on the integrated final head, tracked by
[PR#36 checks](https://github.com/yukasung/tiewtrade/pull/36/checks), not the superseded
initial candidate. V-18/V-20 remain pending. See M4 ledger for conflict resolution/evidence.
