# F-08 Amendment — Paper Trading TOTP Implementation Plan

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-10-30

UI layout ล่าสุด: **Approved 2026-10-31**; ดู [Account Dashboard Visual Plan](account-dashboard-visual-plan-amendment.md)
วันที่: 2026-10-30
ข้อกำหนด: [paper-trading-totp-amendment.md](paper-trading-totp-amendment.md)

## เป้าหมายและขอบเขต

ให้ผู้ใช้ authenticated เลือก `MANUAL` หรือ `BOT` ครั้งแรกเพื่อใช้ Paper Trading ได้
โดยไม่มี Binance API key และไม่ต้องเปิดหรือกรอก TOTP โดยการเลือกยังไม่เปิด Live,
ไม่รันบอท และไม่ให้สิทธิ์เพิ่ม credential

ไม่มี schema migration, public request/response shape, financial logic, risk formula,
order execution semantics หรือ idempotency change งานนี้ไม่เปลี่ยนกฎการเปลี่ยนประเภท
หลังเลือกแล้ว

## ของเดิมที่ใช้ซ้ำ

| ส่วน | การใช้ซ้ำ |
|---|---|
| `infra/trading_account/storage.py` | คง authoritative preference, owner-scoped session, UNIQUE constraint และ atomic transaction |
| `services/api/trading_account_routes.py` | คง authenticated dependency, SafeInputRoute และ audit ใน transaction เดียวกัน |
| `services/api/routing_policy.py` | คง CSRF/session renewal; เปลี่ยนเฉพาะ `reverify` ของ initial-use endpoint |
| `frontend/src/components/ui/{Alert,Button,Select}.tsx` | ใช้ TailAdmin shared controls เดิม ไม่เพิ่ม style เฉพาะหน้า |
| `frontend/src/accountNavigation.ts` | ใช้ internal navigation เดิมสำหรับลิงก์ตั้งค่า security/API key |
| F-15 manual policy และ F-18 admission | คง authoritative `MANUAL`/`BOT`/`null` checks และ financial/risk gates เดิม |

## 1. Backend initial-use selection

- เอา API-key lookup/status precondition ออกจาก `select_use`; ไม่อ่านหรือ lock credential
  เพื่อเลือกประเภท
- คง explicit insert เท่านั้น ไม่มี default preference; existing preference ยังปฏิเสธด้วย
  `TRADING_ACCOUNT_ACTIVITY_UNKNOWN`
- ใช้ UNIQUE `(user_id)` เป็น final concurrency guard และแปลง duplicate เป็นผลปฏิเสธเดิม
- คง audit write ใน transaction เดียวกับ preference; audit failure ต้อง rollback
- เอา `TRADING_ACCOUNT_KEY_UNAVAILABLE` ออกจาก path ของ initial selection เท่านั้น
  ห้ามเปลี่ยน API-key verification หรือ Live readiness

## 2. Authentication และ route policy

- เปลี่ยน `POST /trading-account/use` เป็น authenticated + CSRF + session-renewing mutation
  ที่ไม่ `reverify` และไม่รับ/ใช้ recovery grant
- frontend ไม่ส่ง `X-TiewTrade-TOTP` สำหรับ endpoint นี้ และไม่เก็บ TOTP ใน state
- คง `POST /api-keys`, Live activation, risk-limit increase และ security/admin mutations
  เป็น reverify routes ตามกฎเดิม
- ตรวจ route-classification allowlist/default-deny เพื่อไม่ให้การแก้ endpoint เดียวลดด่านอื่น

## 3. Frontend flow

- แสดงตัวเลือก `MANUAL`/`BOT` เมื่อ `use === null` โดยไม่ขึ้นกับ key status หรือ
  `totp_enabled`
- ถอดช่อง TOTP และคำแนะนำที่บอกว่าต้องเพิ่ม key ก่อนเลือกประเภท
- แสดงข้อความข้อมูลว่า Paper Trading ใช้ได้โดยไม่ต้องมี API key/2FA และ API key/2FA
  จะจำเป็นสำหรับ Live โดยใช้ `Alert` จาก admin template; ลิงก์ไป security/API-key
  ต้องใช้ navigation เดิม
- คง key status summary, stale/loading/error, explicit empty selection, disabled while submit,
  no-auto-retry และ confirmed-refetch behavior เดิม
- ข้อความใหม่ทั้งหมดผ่าน i18n; ไม่แสดง secret หรือ raw error

## 4. Callers และ safety boundaries

- ตรวจ F-15 manual order admission: `MANUAL` เปิดเพิ่มความเสี่ยงได้เมื่อด่านอื่นพร้อม;
  `BOT`/`null` ยังปฏิเสธ; reduction/cancel คงเดิม
- ตรวจ F-18 risk admission และ Paper wallet ว่าไม่อ่าน credential/เรียก venue private API
- ตรวจ API-key add ยังคง fresh TOTP และ Live ไม่รับ preference เป็นหลักฐานแทน activation
- ห้ามส่ง Live order ใน automated/manual validation

## 5. การตรวจตามผลกระทบ

ใช้ [paper-trading-totp-validation.md](paper-trading-totp-validation.md):

1. storage/API concurrency, RLS, CSRF, atomic audit และ safe input
2. route classification และ TOTP regression ของ API-key/risk/security routes
3. frontend component tests สำหรับ no-key/no-TOTP flow, stale/refetch และ navigation
4. Paper composition/E2E: สร้าง wallet → เลือก MANUAL โดยไม่มี key/TOTP → ผ่านจนถึง
   risk/order gates ที่เกี่ยวข้อง; BOT/null ถูกปฏิเสธ
5. lint, format, type, import/static และ build เฉพาะ dependencies ที่ได้รับผลกระทบ

ไม่รัน F-18 W1–W4 performance ใหม่ เพราะไม่เปลี่ยน worker/runtime/financial path;
หลักฐาน performance เดิมยังใช้ได้ หาก implementation ล้ำเข้า engine/runtime ให้หยุดและ
ทบทวนขอบเขตกับผล validation ก่อน

## 6. จุดหยุด

- หากพบว่า Live activation พึ่ง fresh TOTP จาก initial-use selection แทนการตรวจของตนเอง
  ให้หยุดและรายงาน security gap ห้ามถอด TOTP ต่อ
- หากต้องเปลี่ยน schema, MANUAL/BOT semantics หรือกฎหลังเลือกแล้ว ให้จัด amendment ใหม่
- ไม่ commit/push/merge โดยไม่มีคำสั่งเจ้าของ
