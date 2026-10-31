# F-08 Amendment — Paper Trading TOTP Validation

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-10-30
วันที่: 2026-10-30
ข้อกำหนด: [paper-trading-totp-amendment.md](paper-trading-totp-amendment.md)
แผน: [paper-trading-totp-plan.md](paper-trading-totp-plan.md)

## เกณฑ์ตรวจรับ

| รหัส | เกณฑ์และหลักฐาน |
|---|---|
| PT-01 | ผู้ใช้ authenticated ที่ไม่มี API key และไม่ได้เปิด TOTP เลือก `MANUAL` หรือ `BOT` ครั้งแรกได้ด้วย CSRF ที่ถูกต้อง; response/use/audit ตรงกัน |
| PT-02 | missing/invalid CSRF, unauthenticated, invalid/extra input และ cross-owner attempt ถูกปฏิเสธโดยไม่เขียน preference/audit และไม่สะท้อน input/secret |
| PT-03 | concurrent initial selections สำเร็จหนึ่งค่าเท่านั้น; ไม่มี partial audit; existing preference ยังคืน `TRADING_ACCOUNT_ACTIVITY_UNKNOWN` และไม่เปลี่ยนค่า |
| PT-04 | initial selection ไม่ตรวจ/consume TOTP, ไม่รับ recovery grant เป็นสิทธิ์พิเศษ และ frontend ไม่ส่งหรือเก็บ TOTP สำหรับ request นี้ |
| PT-05 | เพิ่ม API key, เปิด Live, เพิ่ม risk limit และ security/admin mutations ที่มีอยู่ยังต้อง fresh TOTP ตาม route policy เดิม; reuse/wrong/missing code ยังปฏิเสธ |
| PT-06 | Paper wallet และ Paper account-use flow ไม่มี venue credential/network dependency; ไม่มี Live request/order และ `may_trade` ไม่เปลี่ยนเป็น true |
| PT-07 | F-15/F-18 authoritative policy คงเดิม: `MANUAL` เท่านั้นที่เปิด order เพิ่มความเสี่ยงได้เมื่อทุก gate พร้อม; `BOT`/`null` ปฏิเสธ; reduction/cancel/stop semantics ไม่เปลี่ยน |
| PT-08 | หน้า Trading Account แสดงตัวเลือกทันทีเมื่อ `use=null` ทุก key/TOTP state, ไม่มีช่อง TOTP, มีข้อความ Paper no-key/no-2FA และ Live safety guidance; loading/stale/error/confirmed-refetch/no-retry/owner-switch behavior คงเดิม |
| PT-09 | UI ใช้ shared TailAdmin components, i18n, keyboard/focus และ responsive state ที่ได้รับผลกระทบ; ไม่มี API secret/raw error ใน DOM/log/storage |
| PT-10 | OpenAPI/request-response schema ไม่เปลี่ยนโดยไม่ตั้งใจ; lint/type/static/build และ targeted regression ที่ระบุผ่านบน candidate สุดท้าย |

## ชุดตรวจตามผลกระทบ

- Backend storage/API:
  `infra/trading_account` tests, `api/test_trading_account_routes.py`, audit rollback,
  RLS/permissions และ concurrency
- Authentication/security:
  route policy/classification, CSRF/session, API-key fresh-TOTP, risk-limit increase และ
  recovery-grant regression ที่เกี่ยวข้อง
- Trading safety:
  manual policy/bridge/request admission สำหรับ MANUAL/BOT/null, no-key Paper path,
  duplicate/idempotency และ no-Live-network gates ที่แตะ caller นี้
- Frontend:
  `TradingAccountPanel`, `AccountSession`, `ApiKeyPanel`, navigation และ component tests;
  browser smoke ของ no-key/no-TOTP desktop/mobile state
- Static/build:
  backend ruff/format/mypy/import checks ที่เกี่ยวข้อง, frontend lint/typecheck/build,
  `git diff --check`; regenerate contract เฉพาะเมื่อ exporter แสดงความต่าง

## ผลเดิมที่ใช้ต่อได้

- F-08 schema/migration/key cap/RLS/audit shape และ TailAdmin shell ที่ dependency ไม่เปลี่ยน
- F-15/F-18 financial calculation, order idempotency, worker concurrency และ W1–W4
  performance เพราะแผนนี้ไม่แตะ runtime/engine/DB schema
- ผลเดิมหมดอายุเฉพาะ F-08 V-4/V-5/V-6, route classification, TradingAccountPanel และ
  composition ที่เคยยืนยัน ACTIVE-key/fresh-TOTP precondition

ถ้า diff จริงแตะ shared authentication middleware, engine, order writer หรือ schema ให้ขยาย
regression ตามผลกระทบและระบุผลเดิมที่หมดอายุใหม่ก่อนรัน

## เวลาประมาณการหลังอนุมัติ

- แก้โค้ดและ targeted tests: 25–40 นาที
- static/build และ targeted browser/composition: 15–25 นาที
- review ผลกระทบและสรุปหลักฐาน: 10–15 นาที

รวมประมาณ **50–80 นาทีหากผ่านครั้งแรก** ไม่รวมการแก้ finding ใหม่หรือ required remote CI
ก่อนเริ่มแต่ละชุดต้องแจ้งขอบเขตและประมาณเวลาใหม่ตามกฎ testing

## เงื่อนไขผ่าน

PT-01–PT-10 ต้องผ่านบน source/configuration เดียวกัน ไม่มี safety/security finding ค้าง
และไม่มี Live order ผล targeted ไม่แทน required CI หรือ validation อื่นที่ยัง Pending

## ผลตรวจ candidate 2026-10-30

ผล local: **Passed — PT-01 ถึง PT-10**

- Backend account/auth/route/concurrency/audit: 77 passed บน PostgreSQL แยก
- Manual order/API key/risk-limit caller regression: 97 passed; API-key add และ
  risk-limit increase ยังคง fresh-TOTP gates
- Frontend account/navigation/API-key components: 58 passed; หลังแก้ข้อความสุดท้าย
  rerun affected TradingAccountPanel 20 passed
- Chromium E2E บนฐานสะอาด: 1 passed — สมัครโดยไม่มี TOTP/key, เลือก `BOT`,
  ตั้ง 2FA/เพิ่ม key ภายหลัง, reload และลบ key โดย preference คงอยู่
- Ruff/format, mypy 595 files, import contracts 7, frontend lint/typecheck/build และ
  `git diff --check` ผ่าน
- Compose API/risk worker healthy และ frontend route ตอบสนองบน candidate ล่าสุด
- ไม่มี schema migration, Live order หรือ F-18 performance rerun ตามขอบเขตที่อนุมัติ

E2E invocation แรก Failed เพราะ reuse ฐาน targeted-test ที่มี key fixtures 26 รายการ;
เก็บผลล้มเหลวไว้และแก้เฉพาะ isolation โดยสร้างฐาน E2E เดิมใหม่ จากนั้น final E2E ผ่าน
โดยไม่เปลี่ยน production code หรือเกณฑ์ Required remote CI ยังคง Pending จนมีการสั่ง
commit/push ตามกฎ Git ของโครงการ
