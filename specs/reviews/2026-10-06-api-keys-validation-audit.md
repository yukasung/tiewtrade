# F-07 — ตรวจ validation ทั้งฉบับ

วันที่: 2026-10-06
ผล: **ยังไม่ผ่านครบ · ยังไม่ใช้ key จริง · ไม่เปลี่ยนโค้ดระหว่าง audit**
อ้างอิง: `specs/features/2026-10-04-api-keys/requirements.md`, `plan.md`, `validation.md`
ขอบเขต: implementation ของ F-07 ทั้งที่ Claude ทำไว้และงานต่อใน working tree

## หลักฐานที่รันใหม่

- Backend: **1,096 passed, 1 deselected (ตลาดจริง), 3 warnings เดิม**
  · PostgreSQL 16 ใน Docker, ฐานข้อมูลสร้างแยก, บทบาทจริงทั้ง 6
- Frontend: **31 passed**, lint/typecheck/build ผ่าน
- Backend Ruff lint/format, mypy และ import-linter ผ่าน
- การที่เทสต์เดิมเขียวไม่ใช่หลักฐานว่าเกณฑ์ที่ไม่มีเทสต์ผ่านแล้ว
- Browser/e2e: **7 passed** · API/TOTP/CSRF/worker จริงกับ FakeVenue ไม่ยิงตลาด
- ไม่มีการอ่านค่า key/secret จริง ไม่มีการส่งคำขอไปตลาดจริงใน audit นี้

## พบพฤติกรรมที่ต้องแก้หรือขอคำตัดสิน

### 1. แถวที่ยังไม่ถึงคิวบังงานใหม่

`backend/src/tiewtrade/infra/api_keys/claims.py::_DUE_HINTS` เลือกแถวเก่าที่ยังไม่จบ
ตาม `created_at LIMIT :limit` แต่ไม่กรอง backoff, `not_before` หรือการจองที่ยังมีอายุ
จึงได้แถวเดิมที่ `claim()` ปฏิเสธซ้ำ ๆ แทนแถวใหม่ที่ถึงคิวแล้ว

**ยืนยันบนฐานข้อมูลทดสอบจริง:** สร้างสองแถวเก่าที่รอ backoff กับ PENDING ใหม่หนึ่งแถว
เรียก `run_round(limit=2)` กับ `FakeVenue` → skipped=2, verified=0,
แถวใหม่ยัง PENDING และ attempts=0 · รูปเดียวกันเกิดกับ limit=100 ใน process จริง

ข้อเสนอ: scan เฉพาะงานที่ถึงคิวหรือหมดอายุ โดยใช้เงื่อนไขเดิมร่วมกับคำสั่ง claim
และยังให้ claim เป็นผู้ตัดสินสุดท้าย · ต้องมีเทสต์ >limit และแถวหมดอายุระหว่างรอ

### 2. `may_retry` ไม่ตรงกับเวลารอของตลาด

`backend/src/tiewtrade/infra/api_keys/records.py::ApiKeySummary.may_retry`
ดูเฉพาะสถานะ UNVERIFIABLE · สร้าง summary ที่ `not_before` เป็นปี 2099
แล้วได้ `may_retry=True` จริง จึงส่งค่าให้หน้าจอเปิดปุ่มทั้งที่แสดงเวลารออยู่
เทสต์หน้าบ้านเดิม mock `may_retry=False` จึงไม่พบข้อผิดพลาดฝั่ง server นี้

ด่านฐานข้อมูลยังกันการตรวจเร็วเกินเวลาได้ จึงไม่ใช่การส่งคำขอถึงตลาดก่อนกำหนด
แต่ผลแสดง eligibility ไม่ถูกต้องตาม RQ-11.4/V-30.5

ข้อเสนอ: คำนวณ eligibility จากสถานะและเวลา ณ ฐานข้อมูล และเทสต์คำตอบ API จริง
ก่อน/หลัง `not_before` · ไม่ใช้เวลาหน้าบ้านเป็นผู้ตัดสิน

### 3. คำตอบ market-wait 429 ไม่มี `Retry-After`

`backend/src/tiewtrade/services/api/api_key_routes.py::retry_key` กรณี MUST_WAIT
ส่งเวลาในข้อความ `detail` แต่ไม่ตั้ง header ที่ V-30.4 ระบุ
ส่วนกรณีโควตาของระบบมี header อยู่แล้วและเทสต์เดิมครอบเฉพาะกรณีนั้น

ต้องเพิ่ม endpoint test ด้วยบทบาท API จริง ให้สถานะ UNVERIFIABLE และ
`not_before` ในอนาคต พร้อมตรวจ header/เวลาและไม่มีคำขอตรวจเพิ่มถึงตลาด

### 4. RQ-6 เงื่อนไขเมื่อพบรายงานสิทธิ์ใหม่ยังไม่มีด่าน

`backend/src/tiewtrade/venues/binance_th/mapping.py::holdings_from_account`
อ่าน balances อย่างเดียว · payload จำลองที่มี `permissions=["MARGIN"]` และ balances=[]
ถูกยอมรับเป็น holdings ปกติ ไม่มีการกั้นเมื่อพบรายงานสิทธิ์ใหม่

**นี่ไม่ใช่หลักฐานว่าตลาดจริงรายงาน field นี้แล้วหรือว่ามันเป็นสิทธิ์ของ key จริง**
ห้ามเดาความหมายหรือยืมชื่อสิทธิ์จากตลาดอื่น · RQ-6 กำหนดให้รับเฉพาะอ่าน/Spot
เมื่อมีรายงาน แต่แผนไม่ได้กำหนดรอยต่อเมื่อพบ field ใหม่ที่ยังไม่รู้ความหมาย

ข้อเสนอรอคำตัดสิน: พบ field รายงานสิทธิ์ที่ยังไม่รู้จักให้ fail closed เป็น
VENUE_PROTOCOL/UNVERIFIABLE พร้อมแจ้งผู้ดูแล ไม่เปิด ACTIVE และไม่ตีความเป็น
สิทธิ์ของ key จนตรวจสัญญา/ความหมายกับเอกสารตลาดและขออนุมัติ mapping

## เกณฑ์และหลักฐาน

| เกณฑ์ | หลักฐานที่มี | ยังต้องเพิ่ม/ระบุขอบเขต |
|---|---|---|
| V-1..3 | `tests/infra/api_keys/test_permissions.py`, `test_storage.py` ใช้บทบาทจริง | V-2 ไม่มี SELECT * แบบแยก แต่มีตรวจสองคอลัมน์ลับ |
| V-4/5/7 | `tests/api/test_api_key_routes.py`, signing/transport/wallet tests | เดิน failure paths และตรวจ traceback ให้ครบตามขอบเขต F-07 |
| V-6 | ApiKeyDetails แบบว่างและ CHECK ของ migration 0009 | ไม่มีเทสต์ DB ที่ลอง details ต้องห้ามกับเหตุการณ์ API_KEY ทุกชนิด |
| V-8 | `frontend/tests/ApiKeyPanel.test.tsx`, `e2e/api-keys.spec.ts` | มีหลักฐาน DOM/cache/storage ระหว่างรอและหลังคำตอบ |
| V-9/10/12 | F-07 storage tests + `tests/infra/crypto/test_sealing.py` ที่ใช้ร่วมกัน | เพิ่ม round-trip/owner/rotation สำหรับ purpose VENUE_API_SECRET ใน property tests |
| V-11 | API startup ถอดกุญแจ TOTP ใน `test_route_classification.py` | ยังไม่มี API ที่ขาด VENUE key และ engine ที่ขาดกุญแจ |
| V-13/14/16/17/18 | worker tests ตรวจสถานะ/secret/เหตุผลและ ERROR log | เพิ่ม UNVERIFIABLE ที่หมดอายุและ boundary ครบพอดี |
| V-15 | unavailable/protocol และ rate-limit cases | OutcomeUnknown ยังไม่ถูกทดสอบ; rate limit ยังไม่ assert secret/status ครบ |
| V-19/19.1 | late success/failure ที่คง PENDING จนผลกลับมา | V-19.2 ยังไม่มี transaction เริ่มก่อนเส้นตายแล้วเขียนหลังเส้นตาย/ทดสอบ mutant now() |
| V-20 | ลบขณะ worker รอตลาดไม่สร้างแถวกลับ | มีหลักฐาน worker test |
| V-21 | ปัจจุบันมีเพียงการตรวจ key ไม่มี consumer เทรด | ระบุว่าการตรวจ PENDING เป็นข้อยกเว้นที่จำเป็น; ต้องพิสูจน์ ACTIVE-only เมื่อเพิ่ม consumer ใน F-08/F-16 |
| V-22/22.2 | overlapping workers และ stale worker ไม่ทับผลใหม่ | V-22.1 ยังไม่กดลองใหม่ระหว่าง claim |
| V-22.3..6 | lease expiry/backoff/wait ตรวจบางส่วน | เพิ่ม worker death, stale scan hint หลัง market-wait, backoff 1→5 นาทีที่นาทีสอง และยืนยัน claim ไม่คำนวณ backoff |
| V-23/24/25/26/27 | route policy, TOTP missing, account without TOTP, e2e retry without TOTP | เพิ่ม wrong TOTP/recovery-grant เฉพาะเส้นทาง API key |
| V-28/29/31/31.2 | RLS, DB uniqueness, concurrent cap, column privileges | มีหลักฐานใน storage/permissions/route tests |
| V-30/30.1/30.4 | quota refusal/per-user/Retry-After + frontend display | เพิ่ม ADD bucket ผ่าน HTTP และ market-wait 429 |
| V-30.2 | เทสต์ชื่อ successful แต่ retries ของ PENDING ได้ 409 ทุกครั้ง | ยังไม่พิสูจน์คำขอ retry ที่สำเร็จ 202 ก็ใช้โควตา |
| V-30.3/30.5 | source guards และตรงชั้นเก็บ | เพิ่ม denied-request → ไม่มีงานใหม่ และ market-wait พร้อมโควตาเต็มผ่าน endpoint |
| V-31.1/31.3 | สิทธิ์คอลัมน์และ retry สำเร็จใน e2e | เพิ่ม HTTP endpoint test อ่าน not_before/ตอบรอด้วย API role จริง |
| V-31.4/31.6 | ไม่มีเทสต์ตรงกรณี | กดหลายครั้งระหว่าง claim → ไม่ซ้อนและเกิดอีกเพียงหนึ่งรอบ |
| V-31.5 | user request นำรอบหน้าแล้วกลับไป backoff | มี worker test |
| V-32/32.1/32.2/33/34 | runtime endpoint + ด่านทั่ว src + negative/positive fixtures | ผ่านด่านเดิมในชุด backend ที่รันใหม่ |
| V-35 | deferred, expired, newer success มี assertions | เพิ่ม assert add/retry/delete/permanent rejection ครบตาราง 4.4 และ failure ซ้ำหลายรอบ |
| V-35.1 | backoff/อายุ/ถัง retry ใน source | Needs Clarification NC-18: ~30 หมายถึงรอบอัตโนมัติหรือรวม manual |
| V-36..38 | known-answer HMAC + request capture/stability tests | มีหลักฐาน ไม่ได้ลอก expected จาก signer ของเรา |
| V-39 | fixture ตามชื่อช่องที่เรียกจริง แต่ยอดแต่งเพื่อไม่เก็บเงินจริง | validation เขียนว่าคำตอบจริง ขัดกับ shapes/README; ต้องยืนยันใช้ fixture ที่ลบข้อมูลจริงตามนโยบาย และ assert ปริมาณครบทุกช่อง |
| V-40/41 | malformed wallet และ error mapping tests ของ F-35/F-07 | ตรวจชนิด/รูปแบบชุดใหม่ให้ครอบรายการครบตาม matrix |
| property สถานะ | CHECK มีใน migration | ยังไม่มี generated mixed-outcome sequences ตรวจ state/secret/check invariants |
| manual 1..7 | ยังไม่ได้เริ่ม | ใช้ key ทดสอบของเจ้าของเฉพาะใน UI ไม่ส่งค่าในแชต; ถอน key ที่ตลาดเมื่อจบ |

## Needs Clarification

- **NC-18 — เพดาน V-35.1:** plan 4.4 แยก ~30 แถวของรอบอัตโนมัติออกจาก
  manual retries ที่คุมด้วยถัง RQ-11.5 แต่ validation เขียน ~30 ต่อ key โดยไม่แยก
  · ต้องยืนยันขอบเขต ไม่ลดโควตาหรือเพิ่ม cap เงียบ ๆ
- **NC-19 — รอยต่อรายงานสิทธิ์ใหม่และ fixture:** ยืนยัน fail-closed เมื่อพบ field
  สิทธิ์ที่ยังไม่รู้ความหมาย และใช้รูปร่างจากการเรียกจริงพร้อมค่าทดแทนตามนโยบาย
  ไม่เก็บยอดเงินหรือคำรับรองจริงใน repo · บล็อกการปิด RQ-6/V-39

**หยุดก่อนแก้โค้ดที่ขัดกับ spec** ตาม AGENTS.md · รอเจ้าของอนุมัติรายการซ่อม
และขอบเขตสองข้อข้างบนก่อนปิด validation/เริ่ม key จริง
