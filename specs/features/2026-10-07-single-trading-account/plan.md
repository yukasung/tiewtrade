# F-08 บัญชีเทรดเดียวต่อผู้ใช้ — Implementation Plan

สถานะ: **Approved** — เจ้าของสั่งแก้ review issue 3 วันที่ 2026-10-07 ให้ implement บัญชีเดียว/ความเลือกประเภทระดับบัญชีตามฉบับนี้
วันที่: 2026-10-07

Account dashboard visual refresh: **Approved 2026-10-31**; ดู [Plan Amendment](account-dashboard-visual-plan-amendment.md)

## เป้าหมายและของเดิมที่ใช้ซ้ำ

ตัด multi-wallet/sub-account implementation เดิมที่ยังไม่ commit ออก แล้วใช้
F-07 จัดการ key หนึ่งชุดต่อผู้ใช้ พร้อมความเลือก MANUAL/BOT ที่ server
คง React18/Vite6/Tailwind4 และ TailAdmin presentation ที่ทำแล้ว
ไม่เปลี่ยนเงื่อนไข trading/Live ที่ยังไม่ได้ implement ไม่ commit/pushเอง
Subscription แยกต่อบัญชีผู้ใช้ตาม mission; ไม่เพิ่ม schema/routes/logic ของ billing
หรือเดาราคาและสิทธิ์สมาชิกในงาน F-08 นี้

| ของเดิม | ใช้อย่างไร |
|---|---|
| `infra/api_keys/{records,storage}.py` | เข้ารหัส/summary/delete/retry; เปลี่ยน MAX_KEYS_PER_USER เป็น1ตามrequirementsใหม่ |
| `services/engine/verification.py` | ตรวจ key ผ่าน venue เดิม ไม่เพิ่ม account/UID endpoint |
| `infra/db/session.py` | UserSession/RLS/transaction; ห้าม scan session สำหรับข้อมูลผู้ใช้ |
| `services/api/{authentication,routing_policy,safe_input_routes}.py` | auth/CSRF/fresh TOTP/sanitized input เดิม |
| `infra/audit/{events,writer}.py` | บันทึกการเลือกประเภท atomic; ไม่เก็บ credential |
| `frontend/src/AccountSession.tsx`, `layout/`, `components/ui/`, `styles/admin-theme.css` | คง account-scoped cache และ TailAdmin shell/controls |
| `frontend/src/ApiKeyPanel.tsx`, `apiKeys.ts`, `apiKeyMessages.ts` | UI keyเดิม; คง polling/retry/auth และเพิ่มข้อความเพดาน1 |
| `frontend/e2e/helpers/{totp,test}.ts` | TOTP/FakeVenue และ reset test state; ไม่ปิด safety gates |

## 1. ตรวจฐานข้อมูลและแยกงานก่อนแก้โค้ด

- เปลี่ยนชื่อ branch เป็น `feature/f-08-single-trading-account` โดยรักษา working tree
- อ่าน actual migration revision และการมี wallet_registry ก่อนถอด0012เดิม
  ตรวจ 2026-10-07 แล้ว actualDBเป็น0010และไม่มีwallet_registry (อ่านmetadataเท่านั้น)
- ถ้า actualDBยังไม่ถึง0012และไม่มีwallet_registry: ถอด migration0012เดิมที่ยังไม่เผยแพร่
  แล้วใช้0012สำหรับ single-account schema ด้านล่าง
- ถ้ามี0012เดิมใช้แล้ว/มีregistry data: **หยุด** เสนอ forward migration/การเก็บประวัติ
  ไม่เขียนทับ applied migration ไม่dropข้อมูลหรือresetฐานข้อมูล
- ตรวจจำนวนkeyต่อuserแบบmetadata-only; ถ้ามากกว่า1 migrationปฏิเสธ ต้องให้เจ้าของจัดการก่อน

## 2. ยกเลิก code ของ registry เดิมอย่างเจาะจง

ถอดไฟล์ของงานเดิมที่ระบุ ไม่ใช้ git reset/clean เหมารวม:

- `backend/src/tiewtrade/infra/wallets/`, `services/api/wallet_routes.py`, migration0012_wallet_registry (เมื่อpreconditionข้อ1ผ่าน)
- ถอด wallet router/route rules/deletion gather+disconnect audit/WalletDetails/actions จาก app, routing_policy, api_key_routes, audit module
- `backend/tests/infra/wallets/`, `tests/api/test_wallet_routes.py` และ wallet-specific assertions ใน migration/audit tests
- `frontend/src/{WalletPanel.tsx,WalletPanel.css,wallets.ts,walletMessages.ts}` และ wallet tests/E2E
- คง safe validation helper, AccountSession, TailAdmin components/layout/styles และ test fixtures ที่ยังใช้
- คืน key DELETE เป็น F-07 semanticsและauditเดิม; ไม่เพิ่มข้อกีดขวางหรือ TOTP ให้การลบ key
- เอาเมนูกระเป๋า/สร้างกระเป๋า/ข้อความ6ใบ/UID/bindingออกจาก UI
- regenerate OpenAPI/api-types หลังเปลี่ยน routes ไม่แก้ generated artifacts ด้วยมือ
- research/reviewประวัติเดิมเก็บเป็น Superseded ไม่อ้างเป็นspecปัจจุบัน

## 3. Schema และ domain

เพิ่ม `user_trading_preferences(user_id uuid PRIMARY KEY REFERENCES users(id),
use text NOT NULL CHECK(use IN ('MANUAL','BOT')), created_at timestamptz DEFAULT now())`
ภายใต้ ENABLE/FORCE RLS owner policy บน API role ให้ SELECT/INSERTเฉพาะowner/use
ไม่มี UPDATE/DELETEใน F-08; เลือกครั้งแรกได้ครั้งเดียว ไม่มีทางเปลี่ยนuseโดยข้ามAPI
ไม่เก็บ credential/key_id/UID/fingerprint บนตารางนี้

เพิ่ม UNIQUE(user_id)บน user_api_keys; migration precheckหลายแถวต่อownerต้องfail
precheck ต้องมองเห็นครบทุกownerจริงภายใต้ FORCE RLS โดยใช้ temporary migrator
SELECT policy ใน transaction และลบทันที; test ต้องยืนยัน failure rollback ไม่เหลือpolicy
ไม่เพิ่มสิทธิ์runtimeหรือคืนเจ้าของ/credentialในerror
ใช้ audit shape แบบ frozenของ migration0011 เพิ่ม TRADING_USE_SELECTED
subject USER=user UUID, actor USER=owner, details {'use':'MANUAL'|'BOT'},
outcome SUCCEEDED, mode NOT_APPLICABLE, failure_code NULL
Auditของข้อมูลเดิมห้ามrewrite; downgradeปฏิเสธเมื่อpreferencesมีrows

เพิ่ม `infra/trading_account/{records,storage,__init__}.py`:
AccountUse enum, immutable TradingAccountSummary(use|null, key summary|null,
may_trade=False, may_change_use=False), errors fixed codes
get_account(UserSession) อ่านsole key summary+preferenceภายใต้RLS
select_use(UserSession, use) lock keyrowของowner, requireACTIVE,
INSERT preference และให้APIrecord auditใน transactionเดียว
missing/foreignkeyไม่เปิดเผยข้อมูล; unique guardป้องกันrequestsพร้อมกันเลือกสองแบบ
existingpreferenceเปลี่ยนค่าแล้วต้อง ACTIVITY_UNKNOWN409 เพราะยังไม่มีหลักฐาน idle

## 4. API และ UI

- GET `/trading-account`: authenticated, ไม่ต่ออายุsession; summaryของownerเท่านั้น
- POST `/trading-account/use`: `{use:MANUAL|BOT}` extra forbid; renews/reverify true,
  ไม่รับrecovery/grace;201หลังเลือกครั้งแรกcommit;409เมื่อยังพิสูจน์เปลี่ยนแบบไม่ได้
- validation/errorมีfixedcodes ไม่สะท้อน input/driverdetails
- key cap1ทั้งDB/storage; key CRUD/retryของF-07คงauth/rate/secret lifecycleเดิม
- `TradingAccountPanel.tsx`, `tradingAccount.ts`, `tradingAccountMessages.ts` ใช้ generatedschemas
  แสดงบัญชีเดียว/solekey/status/ประเภทที่เลือก; ไม่สร้างหรือเลือกหลายกระเป๋า
- ก่อนเลือกประเภทเป็นnull ให้เลือกMANUAL/BOTและTOTPเมื่อkeyACTIVE; หลังเลือกแสดงหนึ่งแบบ
  ปุ่มเปลี่ยนแบบdisabledพร้อมเหตุผลเมื่อไม่มีหลักฐานครบ;ไม่มี trade/bot/balance controls
- ใช้ AccountSessionร่วมกับApiKeyPanel; querykeysมีuser_id, logout/401cancel+clear,
  mutation retryfalse, TOTPไม่อยู่ในvariables/cacheและล้างทุกผล, errorallowlist
- ลบ/เพิ่ม/retry keyแล้ว invalidate keyและtrading-accountquery exactของowner
  refetchfailureแสดงข้อมูลเก่าอย่างชัดเจน ไม่สร้างสถานะสำเร็จเอง

## 5. Tasks (TDD ก่อน implementation)

- [x] ผ่านpreconditionsและเขียน tests ที่แดง: cap1/direct unique insert/paralleladd,
  owner isolation, initial mode/null/ACTIVE-only/change refusal/atomic audit
- [x] ถอด multi-wallet artifacts ข้อ2 โดยรักษา TailAdmin/F-07baselineและaudit history
- [x] ทำ migration, records/storage/audit, API/ROUTE_RULESตามข้อ3/4
- [x] ปรับ tests ของF-07ที่ใช้หลายkeyของownerเดียวให้ใช้คนละownerเมื่อทดสอบworker
  ไม่ข้าม UNIQUEใหม่ด้วยการปิดconstraintและไม่ลดความหมายของ race/secret tests
- [x] ทำ single-account panel ด้วยTDD, query/cache/mutation/refetchfailure/identity races
- [x] E2Eจริงสมัคร→TOTP→key→FakeVenueตรวจ→เลือกuse→reload→deletekey→ยังมีuseแต่ไม่พร้อมเทรด
- [x] รันครบ validation แล้ว independent review; อัปเดตroadmapCompletedเฉพาะผลฉบับนี้ผ่าน
- [x] ยังไม่commit/push/mergeเอง

## การเปลี่ยนที่ต้องอนุมัติ

RQ-2ลดเพดานkey6→1, initial-use flow และscopeการถอดregistryต่างจากplanเดิม
เจ้าของสั่ง implement ผ่าน review issue 3 แล้ว 2026-10-07; บันทึกการอนุมัติท้ายเอกสาร

## Review issue 1 — แผนแก้ E2E ที่เจ้าของสั่ง 2026-10-07

ใช้ helper `frontend/e2e/helpers/environment.ts` ร่วมกันระหว่าง Playwright config
และ fixture เดิม: บังคับ TIEWTRADE_E2E_DATABASE_NAME ชื่อ tiewtrade_e2e หรือ suffix
ตัวอักษร/ตัวเลขคั่นด้วย underscore, URL PostgreSQL+asyncpg ของทุกบทบาทมี owner role
และชี้ loopback host/port/database เดียวกัน ไม่มี query overrides; errors เป็น fixed code
ส่ง environment ที่ตรวจแล้วให้ server/fixture; pin frontend proxy ไป API ที่เริ่มเอง
ปิด reuseExistingServer และใช้ strictPort ฝั่ง Vite
ก่อน DELETE ตรวจ current_database() ใน AUTH transaction เดียวกัน; ห่อ child errors
ปรับเฉพาะ CI job e2e ให้ใช้ฐาน tiewtrade_e2e และเพิ่มคำแนะนำรัน local
ใช้ tests ก่อนแก้เพื่อพิสูจน์ unsafe environment ถูกปฏิเสธ แล้วรัน static/unit/E2E
ณตอนแก้ issue1 การแก้นี้ไม่เริ่ม implementation บัญชีเดียว; ต่อมาเจ้าของสั่ง issue3 แล้ว

## Review issue 2 — แผนแก้ main landmark ที่เจ้าของสั่ง 2026-10-07

ใช้ main ของ `frontend/src/App.tsx` เป็น page landmark เดิม
เปลี่ยนเฉพาะ container `account-content` ใน AccountLayout เป็น div
เพิ่ม regression test ที่ครอบ AccountLayout ด้วย page main เพื่อพิสูจน์ main มีหนึ่งแห่ง
ตรวจ layout/keyboard tests และ frontend static checks

## การอนุมัติ implementation จาก review issue 3

เจ้าของสั่งแก้ issue 3 วันที่ 2026-10-07 หลังได้รับข้อค้นพบและแนวแก้บัญชีเดียว
คำสั่งนี้อนุมัติการถอด multi-wallet, cap1, server preference และ initial-use flow
ตามเอกสารชุดนี้; ไม่อนุมัติ subscription หรือ trading execution เพิ่มเติม
ณตอนแก้ issue3 ประเด็น manual opening หลังหยุดบอทยังเป็น NC23; เจ้าของสั่งแก้ issue4 ต่อมาและปิดแล้ว
F-08 metadata ยังคง may_trade=False; issue5/6ปิดแล้วจากคำสั่งแก้ของเจ้าของ

ผล implementation issue3: backend1480/frontend85/E2E8 และ static/Docker/generated checks ผ่าน
issue4/5/6ปิดแล้ว; code/document finalreviewsผ่านแล้ว; อัปเดตสถานะที่roadmapแล้ว; ยังไม่มี commit/push/merge

## Review issue 4 — แผนปรับกฎจากคำสั่งเจ้าของ 2026-10-07

ใช้ความเลือก server/RQ-4 และเงื่อนไขเปลี่ยนประเภท/RQ-6 เดิม
ปรับเฉพาะเอกสาร mission, trading-safety หัวข้อ8/13, security ข้อยกเว้น restart,
เกณฑ์ทดสอบ และ F-08 docs/roadmap ให้ใช้กฎเดียวกัน ไม่เพิ่ม runtime trading
บันทึก NC23Closed และเกณฑ์งาน F-16/F-19/F-22: BOTที่หยุดไม่เปิดmanualไม้ใหม่,
MANUALผ่านgatesเดิม, ลดความเสี่ยงทุกประเภท, เปลี่ยนประเภทต้องมีidle evidenceครบ
ตรวจข้อความขัดแย้งและ diff; ไม่ต้องรัน suite โค้ดซ้ำสำหรับการแก้เอกสารนี้

## Review issue 5 — แก้เกณฑ์ V-7 (2026-10-07)

เจ้าของสั่งแก้คำผิดใน validation: APIคืนHTTP409เมื่อ activityunknown;
directDBผ่าน tiewtrade_api ถูกปฏิเสธสิทธิ์ตาม GRANTsเดิมและข้อมูลไม่เปลี่ยน
ไม่มีการเปลี่ยน schema/privileges/routes หรือ runtime behavior

## Review issue 6 — จัดขอบเขต research (2026-10-07)

เจ้าของสั่งแก้ research ให้ UID/dedup/replacement ของ multi-wallet และร่าง support
เป็น Superseded; ใช้ requirements บัญชีเดียวเป็นปัจจุบัน เก็บหลักฐาน API เดิม
พร้อมวันที่ ไม่อ้างว่าตรวจใหม่หรือพิสูจน์ UID แล้ว คงอำนาจ key ภายใต้ NC-16
ไม่มี network/private API/message ส่งให้ตลาดหรือเปลี่ยน runtime code ในงานนี้

Final document consistency review สองผู้ตรวจผ่าน 2026-10-07; ไม่มีข้อบล็อก F-08 ค้าง

## Re-review issue 1 — แผนแก้ logout (2026-10-07)

ใช้ AccountSession cleanup/cancel+clear เดิมและ auth.logOut/logOutEverywhere เดิม
เพิ่ม handler เฉพาะ logout ใน AuthPanel: await POST สำเร็จ แล้ว setIdentity(null)
ล้าง auth form/second-factor feedback และกลับ login mode ก่อน await primeCsrfToken
ไม่เรียก fetchIdentity เพื่อยืนยัน logout ซ้ำ; ป้องกัน onChanged ของ TOTP ที่ตอบช้า
ไม่ให้คืน identity หลัง boundary ถูกถอดหรือผู้ใช้เปลี่ยน
TDD integration tests ทั้งสอง endpoint กับ identity GET failure/hang และ CSRF failure/hang
ตรวจ cache เดิม/queryAbortSignal/late responses และ logout POST failure
รัน frontend suites/static/build; ยังไม่ commit/pushเอง

ผล re-reviewissue1: logout repair ผ่าน13cases/fullfrontend98/E2E8/static/build และ scope review
ยังเหลือ re-reviewissue2/V14; ไม่ปิด feature review ทั้งหมดหรือ commit/pushเอง

## Re-review issue 2 — แผนแก้ key feedback (2026-10-07)

ใช้ ApiKeyPanel/shared QueryClient และ exact owner queries เดิม
refresh key ก่อน แล้ว await trading-account invalidation เพื่อไม่ให้ key GET ที่ invalidate
account ซ้ำทำให้รอผิด request; คืนbooleanจากquery status success/fetchStatus idle/
isInvalidated false ของkeyและaccountqueryที่มีอยู่ ห้ามอาศัย fulfilled Promise อย่างเดียว
ให้add/retry/deleteตั้งข้อความสำเร็จหลังrefreshยืนยันครบเท่านั้น; DELETEที่ยืนยันแล้ว
ปิดconfirmationตามเดิม เมื่อrefreshยืนยันไม่ได้แสดงข้อความเตือนแบบallowlistedและgateactions
ปุ่มrefreshmanualตรวจทั้งสองqueriesและล้างfeedbackเก่า; stale dataไม่แสดงsuccessnotice
TDD testsทุกmutation × key/account failedGET, delayedGET, happy path/noautoretry/secretclear
รันfrontend/static/build และ E2E actualroles บนdisposableDB; ไม่แก้backend/commit/pushเอง

ผล re-reviewissue2: frontend107/E2E8/static/build/DockerLinux/proxy และ scope reviewผ่าน
re-reviewissues1/2ปิดแล้ว; ยังคงไม่commit/push/mergeเอง

## ส่วนเพิ่ม — TailAdmin ทุกหน้าปัจจุบัน

สถานะส่วนเพิ่ม: **Approved** — เจ้าของตอบ approve วันที่ 2026-10-07
วันที่: 2026-10-07

ใช้ skill executing-plans ดำเนินงานตามลำดับใน session เดิม หลังอนุมัติ
รักษา working tree และ branch F-08 เดิม; ไม่มี commit/push โดยอัตโนมัติ
React18/Vite6/dependencies เดิม ไม่มี backend/schema/router ใหม่
ข้อเสนอส่วนนี้แทนข้อจำกัดเดิมที่คง native auth/TOTP presentation เท่านั้น
ผลผ่านก่อนหน้านี้เป็น baseline ไม่ใช่หลักฐานผ่านส่วนเพิ่ม

### 1. Theme และ auth layout (UI-RQ-1/5/7/9)

ใช้ source `references/admin-template/src/pages/AuthPages/AuthPageLayout.tsx`
และ SignIn/SignUp/TwoStepVerification เป็นแบบ layout; ไม่ import reference เข้า runtime

- [x] เพิ่ม `frontend/tests/AuthLayout.test.tsx` ตรวจ children/brand และไม่มี account sidebar/main ซ้อน
- [x] รัน `npm test -- tests/AuthLayout.test.tsx` ให้แดงก่อนสร้าง layout
- [x] สร้าง `frontend/src/layout/AuthLayout.tsx` รับ `children: ReactNode`
  ใช้ wrapper `.auth-layout`, พื้นที่ `.auth-content` และ `.auth-brand` ที่แสดง TiewTrade
  desktop สองคอลัมน์; mobile ซ่อน brand panel โดยคงชื่อแอปในฟอร์ม
- [x] ย้าย shared theme tokens จาก `.account-layout` ไป scope `.app-theme`
  ใน `frontend/src/accountPanels.css`; ให้ `.account-layout` และ `.auth-layout`
  ใช้ shared controls/focus ใน `frontend/src/styles/admin-theme.css`
  ใช้ spacing/colors/z-index tokens เดิม ไม่เพิ่ม Preflight หรือ remote font
- [x] รัน layout tests เดิมและใหม่; standalone AccountLayout ต้องยังมี theme

### 2. Auth และรายละเอียดบัญชี (UI-RQ-1/2/6/8)

- [x] เพิ่ม assertions ใน `frontend/tests/AuthPanel.test.tsx` สำหรับ login/register/
  second-step ภายใน AuthLayout และ disabled/loading/errors ที่ยังใช้ได้
  ใช้ tests logout/cache เดิมเป็น regression; ไม่ย้าย identity ไป provider ใหม่
- [x] รัน targeted tests ก่อนแก้ markup
- [x] ปรับ `frontend/src/AuthPanel.tsx` เฉพาะ presentation: ห่อ anonymous branches
  ด้วย AuthLayout; แทน native controls ด้วย Button/Input/Label ที่มีอยู่
  คง ids, names, testids, autocomplete, handlers และเงื่อนไข disabled เดิม
  จัด signed-in details/logout เป็น section ใน AccountLayout เดิม
- [x] เพิ่ม `frontend/src/authMessages.ts` ตาม i18next pattern ของ apiKeyMessages
  สำหรับข้อความ auth/TOTP/health ไทยและอังกฤษ พร้อม interpolation
  แปลข้อความตอน render; ไม่เปลี่ยนการสร้าง request หรือ refusal handling เดิม
- [x] รัน `npm test -- tests/AuthPanel.test.tsx tests/AuthPanelLogout.test.tsx tests/AccountSession.test.tsx`

### 3. TOTP และสถานะระบบ (UI-RQ-2/3/4/6/8)

- [x] เพิ่ม assertions ใน `frontend/tests/TotpPanel.test.tsx` ครอบ enrollment,
  QR fallback, recovery list และ controls เมื่อเปิด/ปิด; คง flow assertions เดิม
- [x] ปรับ `frontend/src/TotpPanel.tsx` ใช้ shared controls และ section style
  คง QR local generation/state lifecycle และ onChanged เดิม; QR max-width 100%,
  otpauth URI/รหัสสำรอง wrap ได้โดยไม่ซ่อนหรือตัดข้อมูลที่ผู้ใช้ต้องอ่าน
- [x] ปรับ `frontend/src/App.tsx` เป็น `.app-theme` ที่มี main เดียว
  จัด health/error ใน footer แบบ template อยู่ใน main เดียวกับ AuthPanel
  ไม่มีหัวแอป native เพิ่มเหนือ AccountHeader/AuthLayout; คง testids และ health fetch เดิม
- [x] จัด API key/บัญชีเทรด และ account/TOTP sections ด้วย theme เดียว
  แก้ CSS เฉพาะ layout/spacing/feedback ไม่แก้ mutation/query callbacks
- [x] เพิ่ม tests ข้อความอังกฤษ/ไทยใน `frontend/tests/AuthMessages.test.ts`
  และ App assertions ที่ main เดียวทั้งก่อนและหลัง login
- [x] รัน `npm test -- tests/TotpPanel.test.tsx tests/App.test.tsx tests/AuthMessages.test.ts tests/ApiKeyPanel.test.tsx tests/TradingAccountPanel.test.tsx`

### 4. ตรวจทั้ง flow และส่งให้ทดลอง (UI-RQ-7/10)

- [x] ปรับ `frontend/e2e/{auth,totp,trading-account}.spec.ts` ตรวจ auth style ใหม่
  แทน expectation ที่คง native style; คง auth/key/database safety assertions เดิม
- [x] รัน `npm test`, `npm run lint`, `npm run typecheck`, `npm run build` ใน frontend
- [x] รัน `npm run test:e2e` กับ disposable DB ที่ผ่าน environment guard เดิม
  ไม่ใช้ฐานข้อมูล preview ที่เจ้าของกำลังทดลองและไม่ reset ข้อมูลเจ้าของ
- [x] ตรวจภาพ desktop 1440px/mobile 360px: login/register/second-step,
  signed-in/TOTP enrollment/recovery และ error/disabled; keyboard/focus/no overflow
- [x] บันทึกภาพใน `specs/reviews/2026-10-07-f08-single-account/ui-template/`
  และผลใน validation/audit; review diff เฉพาะ UI ส่วนเพิ่ม
- [x] rebuild เฉพาะ frontend ของ project `tiewtrade-f08-preview` ด้วย override
  `/tmp/tiewtrade-f08-preview.yaml`; คง API/DB preview และข้อมูลที่สร้างไว้
  ตรวจ `http://localhost:5182/` และ `/api/health` แล้วแจ้ง URL ให้เจ้าของ
- [x] อัปเดต roadmap ตามผลจริง โดยไม่ใช้ผล baseline แทนผลส่วนเพิ่ม

ความเสี่ยงหลักคือ global CSS กระทบ semantics/controls, responsive URI/QR ล้น
และ markup ทำให้ auth/cache unmount เปลี่ยน; ตรวจด้วย regression/ภาพ/keyboard
ไม่แก้ safety flow หรือเพิ่มการเก็บ credential เพื่อแก้ปัญหาด้าน presentation

ผลส่วนเพิ่ม 2026-10-07: frontend113/13 suites, lint/typecheck/build ผ่าน; E2E8ผ่าน26.3s
ภาพ23ไฟล์เก็บใน review/ui-template; keyboard/focus/brandresponsive/disabledผ่าน
standards/spec reviews ไม่มี findings ค้าง; frontend preview rebuild แล้ว API/healthผ่าน
ยังไม่commit/push/merge; backend1480 เป็นผล baseline ไม่ได้รันใหม่สำหรับงาน UI
