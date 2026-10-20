# F-15 M2 — Public input / storage checkpoint

วันที่: 2026-10-18; branch `feature/f-15-paper-order-matching`; base HEAD
`2eb3000711353e76d81f32e9c9c08287f6788702`; working tree ยังไม่ commit
requirements/NC-F15-07/plan/validation Approved ก่อน implementation

## ขอบเขต

- Venue-neutral depth/trade/capability contracts; Binance TH public adapter ใช้ HTTP/WSS
  gateways เดิม ไม่มี key หรือ signed request และไม่มี order endpoint
- Snapshot 1000 + buffered diff bridge, continuous IDs, absolute levels/confirmed zero,
  bounded coverage, source/receipt/verification clocks, trade side/ordering/dedupe;
  gap/disconnect/overflow ต้องเริ่ม epoch ใหม่ ไม่จับคู่ย้อนหลัง
- PostgreSQL 5s writer lease/generation, 4096-slot public ring, contiguous input IDs,
  coherent read, digest/provenance checks และ typed failure สำหรับ malformed evidence
- Private pair dependencies ภายใต้ wallet lock/RLS; trigger ปรับเฉพาะ public aggregate
  เพื่อให้ market-data อ่าน retention demand ได้โดยไม่มีสิทธิ์อ่าน owner/financial tables
- Migration 0033/0034: order/profile/command/event/reservation schema, signed quote-cash
  extension ของ F-13 ledger, composite owner/episode/pair/order references และ F-14 links
- Full private execution evidence แยกจาก public cache, immutable profile, canonical payload,
  global dedupe registry ข้าม daily partitions, atomic append และ replay
- Daily partition provisioner ใช้ protection/policy helpers เดิม; API/market-data ไม่มีสิทธิ์
  อ่าน evidence, scanner อ่านได้เฉพาะ dispatch metadata; pin profile ไม่อ้าง READY

M2 ยังไม่มี financial order writer, runtime supervisor/composition, order initialization,
cancel/correction/recovery transaction หรือ F-13 reset success; เป็นงาน M3/M4 ตามแผน
fake pipeline ตรวจถึง F-14 pure calculation เท่านั้น ยังไม่ใช่ persisted ledger end-to-end

## Public contract observation

ตรวจ read-only โดยไม่มี API key วันที่ 2026-10-18 เทียบ
[Binance TH official documentation](https://www.binance.th/api-docs/en/)
กับ `/api/v1/exchangeInfo`, `/api/v1/depth?symbol=BTCUSDT&limit=1000`
และ ETHUSDT: ทั้งสาม requests HTTP 200; depth มี `lastUpdateId/bids/asks`,
sequence เป็น integer และ bid/ask อย่างละ 1000 rows ของ string price/quantity
bounded combined WSS observation ได้ depth/trade ของทั้งสองคู่ใน 2.14s:
depth keys `E,U,a,b,e,s,u`; trade keys `E,M,T,e,m,p,q,s,t`

ทั้งสองคู่มี PRICE_FILTER, LOT_SIZE, MIN_NOTIONAL, PERCENT_PRICE และ MAX_NUM_ORDERS;
MIN_NOTIONAL ใช้ avgPriceMins=5. Parser เก็บ source document/version และปฏิเสธ
required rules ที่ยังรองรับไม่ได้ตามแผน §4 ไม่อ้าง synthetic fixture เป็น actual filters
จึงยังรับรองการส่ง production Paper order ด้วย capability จริงของสองคู่นี้ไม่ได้
fixtures `tests/order_book_fixtures.py` ใช้ราคาสังเคราะห์สำหรับ independent oracle;
`venue_rules=True` ตรวจ required-rule rejection โดยไม่ fallback เป็นราคาล่าสุด

## ผลตรวจ

Environment: Windows Python 3.12.3/uv; Linux Python 3.12.12 ใน
`ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, dependencies จาก `uv.lock --frozen`;
isolated PostgreSQL 16 container `tiewtrade-f15-pg16`, localhost port 55435
ฐานข้อมูลสุดท้าย `tiewtrade_f15_m2_final` สร้างใหม่พร้อม bootstrap roles/event trigger
ไม่มีการลบประวัติฐานข้อมูลเดิมหรือใช้ main application database

| ตรวจ | ผล |
|---|---|
| Populated 0032 → 0034 → safe 0033 → 0034; history refusal/rollback | PASS: `uv run python -m tests.infra.execution_market.check_migrations` บน DB ใหม่; capital เดิมไม่เปลี่ยน, pin profile ยังคง UNKNOWN, failed downgrade คืน FORCE RLS ครบ |
| `uv run pytest tests/infra/execution_market tests/infra/paper_wallet tests/infra/positions --tb=short` | **70 passed, 33.64s** หลังแก้ FK ครั้งสุดท้าย |
| Linux regression: `pytest tests/core tests/venues tests/services/market_data/test_order_book.py tests/test_core_purity.py tests/test_venue_isolation.py tests/gates` | 780 passed / 14 failed, 26.29s; สาเหตุและการปิด failures อยู่ด้านล่าง ไม่อ้างรอบนี้เป็น green |
| Linux affected rerun: `pytest tests/venues/binance_th/test_mapping.py tests/venues/binance_th/test_sources.py tests/venues/binance_th/test_order_books.py tests/gates` | **97 passed, 1.95s** บน writable ephemeral repository copy |
| Ruff check / format --check ทุก changed/new Python ยกเว้น fixture trees | **32 files passed/formatted**; หลัง final FK/test patch ตรวจสองไฟล์นั้นซ้ำผ่าน |
| Mypy scoped production + tests ที่เปลี่ยน โดยส่ง source roots พร้อมกัน | **30 source files passed** หลัง final patch |
| `uv run lint-imports` | **7 kept, 0 broken**, 230 files / 1416 dependencies |
| `git diff --check` | ผ่าน |

Real PG cases ครอบคลุม exact retry/conflict, expired lease/takeover, stale source,
renew ไม่ทำให้ book สด, cache corruption/missing cursor, 4097 publications → 4096 slots,
slow consumer gap, concurrent private demand, owner separation, parent/child append-only
รวม privileged UPDATE/DELETE/TRUNCATE, future partition policy/grants, atomic evidence/key
rollback+retry, replay หลัง cache ถูกแทนที่ และ projection ห้ามอ้าง event ของออเดอร์อื่น
Fake feed → real PG → matcher → F-14 ตรวจ one fill, net BTC `0.999`, cash `2400` จาก
capital `2500`/budget `100`; disconnect และ bootstrap overflow ต้อง unavailable

Review correction: composite FK ของ projection เดิมผูก owner/episode/pair แต่ยังไม่ผูก
order ของ last event; เพิ่ม order_id พร้อม negative PG test (SQLSTATE 23503) และ
positive same-order control. ไม่เปลี่ยนข้อกำหนดหรือ trading policy ที่อนุมัติแล้ว

## Failed attempts และการแก้ environment/gates

- Windows broad regression: 5 failed / 604 passed / 185 errors, 36.05s; venue fixture
  ปิด socket.connect กระทบ Windows asyncio self-pipe และ subprocess locale encoding
  จึงใช้ Linux ตรวจชุดนี้ ไม่ลด network isolation ของ fixture
- Linux แรก mount backend อย่างเดียว: 20 failed / 765 passed / 9 errors, 46.24s;
  ขาด repo specs และ executable venv path. รอบ read-only full repo ถัดมามี 14 failures:
  12 มาจาก mypy/import-linter เขียน cache ไม่ได้; แก้ด้วย writable container copy
  ที่ตัด Windows venv/cache/pyc ออก ใช้ Linux venv แยก โดยไม่แก้ application code
- อีก 2 failures เป็น gate เดิมห้าม `avgPrice` ทุก string และห้าม hashlib ทุก import:
  ยอมรับ field `avgPriceMins` ที่ใช้ reject rule; อนุญาตเฉพาะ `from hashlib import sha256`
  ใน public order_book_mapping เพื่อ fingerprint source document. HMAC/general hashing
  และ secret identifiers ยังคงถูกห้าม; affected Linux rerun 97 cases ผ่านครบ
- Mypy ที่ส่ง test เดี่ยวโดยไม่ส่ง source roots มี import-untyped errors; scoped rerun
  พร้อม production sources ผ่าน 30 files ไม่ปิด strict rules หรือ ignore errors

ใช้ผล regression เดิมที่ dependencies ไม่เปลี่ยนร่วมกับ affected rerun ไม่อ้างผลรวมสองรอบ
เป็นจำนวน tests ที่ไม่ซ้ำ และยังไม่ได้รัน full backend candidate suite/required CI ของ M5

## Coverage / งานถัดไป

- V-7/V-8/V-9: **Partial** — source/storage/schema cases มีหลักฐาน แต่ runtime composition,
  withdrawn-pair lifecycle และ old/new financial writer fence ยังต้องตรวจใน integration
- V-16: **Partial** — imports/purity/Paper isolation และ fake pipeline ผ่าน;
  persisted ledger flow ต้อง M3. V-17: **Partial** — bounded public shape observation มีแล้ว;
  whole-system coherence/manual integration checks ยังไม่ครบ
- V-1..V-6 คง Partial; V-10..V-15/V-18 ยัง Not Run; V-19 Pending Full Validation
- M3 ต้องใช้ wallet financial lock, active episode/closure checks และ DB-clock fences จริง
  ใน init/admission/fill/cancel/correction/replay; cash/F-14/event/reservation/evidence ต้อง
  commit หรือ rollback ทั้งชุด และ derive retention release จาก authoritative liabilities
- Daily partitions ต้อง provision ต่อก่อนข้ามช่วงที่สร้างไว้; missing partition fail closed
  แต่ release scheduler/restore/long workload ยังไม่รับรอง. ไม่ใช้ smoke แทน V-19
- Production admission/risk capability ยังไม่มี implementation ที่เปิดได้; actual unsupported
  required filters ต้องคง rejection. ไม่มี public order/correction route หรือ Live activation

เวลาที่มีตัวจับจริงอยู่ในผลตรวจด้านบน; ช่วงอ่าน/เขียน/รีวิวก่อนหน้าไม่ได้จับเวลาแยก
จึงไม่ประมาณเป็นชั่วโมงทำงานหรืออ้างว่าไม่มีเวลารอ. ไม่มีการขออนุมัติซ้ำใน checkpoint นี้
Fingerprint ของ final backend working sources/config/tests อยู่ใน `m2-source-manifest.sha256`
ครอบคลุมทั้ง tracked diff และ untracked implementation; ไม่ใช้ HEAD อย่างเดียวแทนโค้ดที่ตรวจ
Manifest มี 37 files; SHA-256:
`f528e5f73520f7af0fadaedf502f73afc045ff773ef902408b2797209dda7a3a`
Synthetic fixture source SHA-256:
`8debb5f8b707ee288464b9dfac9a14021d456f7718754e0a160947ea69eccc62`
