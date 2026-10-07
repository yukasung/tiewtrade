> Historical record: เจ้าของยกเลิกขอบเขตหลายกระเป๋า/sub-account 2026-10-07
> ไม่ใช่ spec ที่ใช้เริ่มงานต่อ; ผล tests เป็นของ implementation เดิม

# F-08 ทะเบียนกระเป๋าและผูก API key — Validation

สถานะ: **Superseded** — เจ้าของอนุมัติฉบับรวม TailAdmin และ shared QueryClient 2026-10-07
วันที่: 2026-10-07

เอกสารนี้กำหนดเกณฑ์ก่อน implementation; ผลตรวจหลังอนุมัติและลงมือจริง
บันทึกไว้ในหัวข้อ 7 โดยคงเกณฑ์เดิมสำหรับการตรวจครั้งถัดไป

## 1. “เสร็จ” หมายถึง

| # | เกณฑ์ | วิธีตรวจและผลที่ต้องได้ |
|---|---|---|
| V-1 | สร้างทะเบียนโดยเลือก key ACTIVE ของตนกับ MANUAL/BOT ได้ | API integration + E2E: 201 หลัง commit; key_id/use ตรงคำขอ |
| V-2 | กระเป๋าผูก key แต่ยังไม่ยืนยันบัญชีจริง | DTO account_verified=false, connection_status=LINKED_UNVERIFIED; UI แสดงยังไม่ยืนยันบัญชีจริง |
| V-3 | ไม่มี trading capability | may_trade=false; UI ไม่มีเริ่มบอท/เทรด/Live; F-08 ไม่เพิ่ม order route, engine job หรือ venue endpoint |
| V-4 | สร้างได้ไม่เกิน 6 ต่อผู้ใช้ | 6 สำเร็จ; ใบที่ 7 เป็น 409 WALLET_LIMIT_REACHED; DB count ยัง 6 |
| V-5 | เพดานไม่หลุดด้วยคำขอพร้อมกัน | เริ่มมี 5 ใช้ two transactions/barrier สร้างคนละ key พร้อมกัน; สำเร็จหนึ่ง/ปฏิเสธหนึ่งและ count=6 |
| V-6 | คนละผู้ใช้มีเพดานของตน | A เต็ม 6 ไม่ขวาง B สร้างใบแรก; อ่านได้เฉพาะรายการของตน |
| V-7 | key ไม่ ACTIVE ผูกไม่ได้ | PENDING/REJECTED/UNVERIFIABLE → 409 WALLET_KEY_UNAVAILABLE; ไม่มี wallet/audit สำเร็จ |
| V-8 | key ไม่พบหรือของผู้อื่นไม่เผย ownership | ทั้งสองกรณี 404 code/body เดียวกัน; ไม่คืน key label, tail, user_id หรือ wallet ของผู้อื่น |
| V-9 | key เดิมคนละแถวผูกซ้ำไม่ได้ | เพิ่ม exact public key ภายใต้ label คนละชื่อ ตรวจผ่าน F-07 แล้ว bind อีกครั้ง → 409; active binding มีเพียงหนึ่ง |
| V-10 | key เดิมข้ามผู้ใช้ก็ซ้ำไม่ได้ | สองผู้ใช้มี exact key เดียวกัน; UNIQUE กันแม้ query ภายใต้ RLS ไม่เห็นกัน; error ไม่บอกข้อมูลของผู้ใช้อื่น |
| V-11 | ไม่เทียบเพียงสี่หลักท้าย | synthetic keys ต่างกันที่มี tail เดียวกันผูกคนละ wallet ได้ |
| V-12 | การแข่ง bind key เดียวกันไม่หลุด | two sessions/barrier bind exact key จากคนละแถว; สำเร็จหนึ่ง ปฏิเสธหนึ่ง ไม่มี orphan wallet |
| V-13 | คนละ key ไม่ถือว่าคนละบัญชีจริง | unit/API assertions: account_verified/may_trade คง false; ไม่ใช้ UID ที่ผู้ใช้กรอกหรือยอดเป็นหลักฐาน |
| V-14 | ลบ key คงทะเบียนและประวัติ | existing DELETE /api-keys/id เป็น 204; id/use/created_at wallet เดิมคงอยู่; key_id=NULL, DISCONNECTED; audit เดิมยังอยู่ |
| V-15 | fingerprint ถูกล้างพร้อมการลบ key | ตรวจด้วย migrator ใน test DB: wallet key_fingerprint=NULL; secret row หาย ไม่มี credential สำเนาใน wallet |
| V-16 | ไม่มี replacement หรือการผูกกลับอัตโนมัติ | เพิ่ม key ใหม่หลังลบ; wallet เดิมยัง DISCONNECTED; ไม่มี route bind/replace; UUID ใหม่สร้างทะเบียนใหม่ได้ภายใต้ quota |
| V-17 | กระเป๋าที่ไม่มี key ยังอยู่ใน quota | ลบ key ของ wallet ในกลุ่ม 6; สร้างใบใหม่ยัง 409 ไม่ลบทะเบียน/รีไซเคิลประวัติให้เอง |
| V-18 | bind/delete แข่งกันได้ผลสอดคล้อง | คุมสองลำดับด้วย barriers: delete ก่อน → create ไม่สำเร็จ; bind ก่อน → wallet คงอยู่แต่ disconnect พร้อม audit หลัง delete |
| V-19 | การเปลี่ยนประเภทไม่มีหลักฐานต้องปฏิเสธ | POST /wallets/id/use ของตน → 409 WALLET_ACTIVITY_UNKNOWN; DB direct UPDATE use ก็ถูกปฏิเสธ; use เดิมคงอยู่ |
| V-20 | คนละเจ้าของเข้าถึง wallet ไม่ได้ | GET list ไม่เห็นของคนอื่น; type-change ของคนอื่นและ UUID ไม่พบให้ 404 เหมือนกัน |
| V-21 | audit ของการสร้างและผูกครบและ atomic | transaction สำเร็จได้ WALLET_CREATED + WALLET_KEY_BOUND ที่ subject UUID เดียวกัน |
| V-22 | audit ของผลลบ key ครบและ atomic | API_KEY_DELETED + WALLET_KEY_DISCONNECTED ใน transaction เดียว; details ใช้ key row UUID เท่านั้น |
| V-23 | audit ล้มเหลว = การกระทำ rollback | inject record_event failure หลัง insert และหลัง delete; wallet/credential/binding กลับสภาพเดิมทั้งหมด |
| V-24 | audit shape บังคับทั้ง Python/DB | CREATED details ว่าง; bind/disconnect รับเฉพาะ key_id UUID; mode NOT_APPLICABLE, actor=USER owner, success ไม่มี failure_code; shape ผิดต้องถูกปฏิเสธ |
| V-25 | session และ CSRF บังคับ server | session ไม่ครบถูกปฏิเสธ; mutation ไม่มี/ผิด CSRF ถูกปฏิเสธ ไม่เปลี่ยน DB |
| V-26 | การสร้าง/ผูกต้อง fresh TOTP | ไม่มี code/ผิด/ไม่มี TOTP ถูกปฏิเสธ; code ที่ใช้เพิ่ม key แล้วนำมาสร้าง wallet ใช้ซ้ำไม่ได้ |
| V-27 | รหัสสำรองไม่แทน TOTP | recovery grant ใช้สร้าง wallet ไม่ได้; route reverify=true, accepts_recovery_grant=false |
| V-28 | การเดา TOTP ใช้โควตา F-06 เดิม | failed wallet reverify ใช้ bucket เดียวกับทุกจุดตรวจ; success ไม่ล้างโควตา และไม่เพิ่ม grace period |
| V-29 | ลบ key ไม่เพิ่มข้อกีดขวาง auth เดิม | DELETE route ยังไม่ require reverify; regression ของ F-07 และ FK disconnect ผ่าน |
| V-30 | route ใหม่ทุกเมธอดอยู่ในตารางเดียว | route classification tests: GET/POST /wallets และ POST /wallets/id/use ตรง ROUTE_RULES; unknown route fail closed |
| V-31 | การอ่านรายการไม่ต่ออายุ session | GET /wallets ไม่เลื่อนเวลาหมดอายุ; POST ตาม rule ต่ออายุได้ |
| V-32 | ไม่มี secret หรือ key เต็มใน payload/DTO | ตรวจ JSON keys, repr, OpenAPI และ marker scan; รับเฉพาะ key_id/use, คืนได้เฉพาะ key tail ในข้อมูลสรุป |
| V-33 | input ผิดไม่สะท้อนค่าที่ส่งมา | malformed UUID/use/extra field containing credential marker → 422 WALLET_INPUT_REJECTED ไม่มี marker หรือ validation input |
| V-34 | ไม่มีข้อมูลอ่อนไหวใน error/log/audit/metric | capture logs + inject duplicate/check/database failures; ไม่มี public key/secret/fingerprint หรือ SQL driver detail |
| V-35 | API อ่าน secret ไม่ได้เหมือนเดิม | actual tiewtrade_api SELECT secret_sealed/key_version ต้องถูกปฏิเสธ; F-07 role tests ยังผ่าน |
| V-36 | fingerprint มาจาก DB ไม่เชื่อ caller | actual API role INSERT fingerprint/SELECT fingerprint ถูกปฏิเสธ; ใส่เฉพาะ key_id แล้ว DB คำนวณ SHA-256 จาก exact key |
| V-37 | การกันผู้ใช้ทำงานที่ DB | ENABLE/FORCE RLS, policy owner check, composite FK; cross-user direct INSERT/SELECT ถูกปฏิเสธภายใต้ actual role |
| V-38 | ขอบเขตสิทธิ์ตารางใหม่แคบ | engine/scan/auth/market-data ไม่เข้าตาราง; API ไม่มี UPDATE key_id/user_id/fingerprint และไม่มี DELETE wallet |
| V-39 | การย้อน migration ไม่ทำทะเบียนสูญหาย | disposable DB มี wallet: downgrade 0012 ถูกปฏิเสธและข้อมูลคงเดิม; schema เปล่า downgrade/upgrade ผ่านและ snapshot เท่ากัน |
| V-40 | migration ไม่ทำ F-07 พัง | จาก 0011→0012: pending verification/retry/delete ยังทำงาน และ key ที่มีอยู่ไม่ถูกสร้าง wallet ให้อัตโนมัติ |
| V-41 | เวลาฐานข้อมูลและ DTO ถูกต้อง | created_at aware/UTC จาก DB; UI format ผ่าน locale; เวลา/id ลำดับรายการ deterministic |
| V-42 | UI ครบ loading/empty/error/success | Vitest และ browser: เลือก ACTIVE, MANUAL/BOT, submit pending ป้องกันกดซ้ำ, มี empty/load/refusal ที่อ่านได้ |
| V-43 | ลบ key แล้วทั้งสอง panel ได้สถานะใหม่ผ่าน client ร่วม | render ApiKeyPanel + WalletPanel ภายใน AccountSession จริง; DELETE สำเร็จ invalidate exact api-keys/wallets ของ owner บน client เดียวกัน และ refetch active queries ทั้งคู่โดยไม่ reload/focus; key หายและ wallet เดิมเป็น DISCONNECTED ตาม server; refetch failure แสดง error/สถานะข้อมูลกำลังปรับปรุง ไม่อ้างผลเก่าว่าเป็นล่าสุด; refresh/focus อ่านใหม่ได้ |
| V-44 | timeout ไม่ทำให้สร้างซ้ำเอง | mutation retry ปิด; error บอกให้ตรวจรายการ; ไม่แสดง success ก่อน HTTP/commit; TOTP ไม่ค้างใน error/query key/log |
| V-45 | cache ไม่รั่วข้าม login หรือ response เก่า | AccountSession key=identity.user_id สร้าง client ต่อ mount; query keys ของ key/wallet มี user_id; logout/session expired unmount, cancel pending queries และ clear query/mutation cache; queryFn ส่ง AbortSignal; ทดสอบสลับผู้ใช้ขณะ GET ค้างแล้ว response เก่ามาถึง บัญชีใหม่ต้องไม่เห็นข้อมูล/ผล mutation เก่า และไม่มี mutation retry; ไม่มี cache persistence |
| V-46 | TailAdmin UI accessibility/responsive/i18n | keyboard ไปถึง sidebar/key/use/TOTP/submit/logout; mobile sidebar มี aria-expanded และ Escape/Backdrop ปิดพร้อมคืน focus; labels+aria-live/error associations; 360px และ desktop ไม่ล้น; ข้อความผ่าน i18next และภาษาไทยอ่านได้; button type ชัดเจน ปุ่ม cancel/delete ไม่ submit ฟอร์ม; ไม่มี demo links/data/trading actions |
| V-47 | ไม่มีงานแสดงยอดแฝง | WalletView/Panel ไม่มี balances/free/locked/available/reserved; ไม่มี wallet WebSocket/holdings fetch ใหม่ |
| V-48 | ไม่ออกตลาดจริงจาก F-08 tests | API/infra ใช้ fake verified key fixture; E2E เรียก worker กับ FakeVenue; network/endpoint safety gates เดิมผ่าน |
| V-49 | type/API artifacts ไม่ล้าสมัย | export OpenAPI/gen types แล้วไม่มี diff เพิ่ม; frontend ใช้ generated schemas ไม่มี copy definitions |
| V-51 | template ใช้ร่วมกับ toolchain เดิมได้ | React 18/Vite 6/Node 22 + Tailwind 4 รุ่นใน lockfile ผ่าน lint/typecheck/build; production build ไม่ import references และไม่มี demo/plugin dependencies ที่ไม่ได้ใช้ |
| V-52 | style ของ template ไม่รบกวน auth เดิม | browser regression ของ login/register/TOTP และ API key flow เดิมผ่าน; ไม่มี global Preflight/reset leakage; screenshots ก่อน/หลังบน desktop/360px; ไม่มี remote font fetch ที่เพิ่มเอง |
| V-50 | ทุกด่านมาตรฐานผ่านและบันทึกหลักฐาน | commands ในหัวข้อ 4 ผ่านจริง; DB tests ไม่มี skip; browser/manual observations และ review outcomes อยู่ในบันทึกผล |

## 2. เทสต์ที่ต้องมีและตำแหน่ง

| Path | ประเด็นหลัก |
|---|---|
| `backend/tests/infra/wallets/test_constraints.py` | RLS/FK/trigger, ACTIVE, exact-key digest, tail collision, quota, no replacement |
| `backend/tests/infra/wallets/test_permissions.py` | actual roles, fingerprint column/secret privileges, owner forgery, direct UPDATE/use denial |
| `backend/tests/infra/wallets/test_concurrency.py` | count 5→6 race, duplicate fingerprint race, bind/delete ทั้งสองลำดับ |
| `backend/tests/infra/wallets/test_storage.py` | UserSession-only, create/list/status, stable ordering, delete retains registry |
| `backend/tests/infra/wallets/test_audit.py` | create/bind/disconnect shape และ rollback injected failure |
| `backend/tests/api/test_wallet_routes.py` | TOTP/CSRF/session/ownership/generic errors/type-change failure/payload hygiene |
| `backend/tests/api/test_api_key_routes.py` | F-07 delete audit+wallet disconnect และ regression ของ retry/verification |
| `backend/tests/api/test_route_classification.py` | ROUTE_RULES ครบทุก method/path และไม่สร้าง public route ใหม่ |
| `backend/tests/infra/db/test_migrations.py` | upgrade/downgrade empty snapshot; refuse downgrade populated wallet |
| `backend/tests/infra/audit/test_event_shape.py` | Python action/details ตรง CHECK ใหม่ |
| `frontend/tests/WalletPanel.test.tsx` | server query state, TOTP form, copy/status/refusal, invalidation/cache/timeout ภายใต้ AccountSession |
| `frontend/tests/AccountLayout.test.tsx` | mobile sidebar, keyboard/focus, native button/input semantics และ logout handler เดิม |
| `frontend/tests/AccountSession.test.tsx` | ทั้งสอง panel จริงใช้ client ร่วม; DELETE refetch ทั้งคู่โดยไม่ reload/focus; refetch failure; logout/expiry/user switch, cancel+clear และ late responses |
| `frontend/e2e/wallets.spec.ts` | signed-in→TOTP→fake key→worker verified→wallet→reload→delete key→disconnect |

### ตัวเลขจริงและคุณสมบัติ

V-51/V-52 ตรวจการนำ template มาใช้ตาม plan; ไม่เพิ่มข้อกำหนดการเทรด

F-08 ไม่เพิ่มการคำนวณเงิน จึงไม่มีสูตรเงินใหม่ให้ทดสอบด้วยตัวเลขหรือ Hypothesis
ชุด Money/Quantity เดิมต้องยังผ่าน และไม่เพิ่ม float/Decimal calculation
คุณสมบัติของทะเบียนพิสูจน์ด้วย DB constraints และ concurrency ที่ใช้ barriers:
count≤6, active binding fingerprint ไม่ซ้ำ, key deletion ไม่ลบ wallet และ
identity/trading flags ไม่กลายเป็น true จากการผูก key

อย่าสร้าง mock แทน RLS/unique/FK/advisory lock หรือแก้สถานะ key ด้วย SQL ใน E2E
ใช้ worker ของ F-07 กับ FakeVenue ตาม flow เดิม; fixture DB เฉพาะ unit/integration
ใช้ค่าทดแทนเท่านั้น ไม่มีข้อมูล credential หรือ account response ของเจ้าของ

## 3. ตรวจด้วยมือ

ใช้ข้อมูลทดสอบที่ไม่มีความลับและ key ที่ worker ตรวจผ่าน FakeVenue; F-08 ไม่ต้อง
เรียกตลาดจริงหรือขอให้เจ้าของสร้าง key จริงเพื่อพิสูจน์ทะเบียน

- [ ] เปิดบัญชีทดสอบที่มี TOTP; เห็น key ที่ตรวจผ่านและมีแต่ชื่อ/4 หลักท้าย
- [ ] เลือก MANUAL สร้างทะเบียนด้วย TOTP ใหม่; เห็นข้อความยังไม่ยืนยันบัญชีจริงและยังใช้เทรดไม่ได้
- [ ] สร้างอีกใบเป็น BOT ด้วย key ทดสอบอีกอัน; ไม่มีปุ่มเริ่มบอทหรือแสดงยอด
- [ ] reload แล้วทะเบียนยังอยู่; ดูเวลา/ประเภทและใช้ keyboard ได้ครบ
- [ ] ลบ key ผ่านหน้าจอเดิม; wallet เดิมเป็นยังไม่เชื่อมต่อ ประวัติไม่หาย
- [ ] เพิ่ม key ใหม่; wallet เดิมไม่ผูกกลับเองและไม่มีปุ่มเปลี่ยน key
- [ ] ตรวจกรณี quota 6 รวมใบที่ไม่มี key และข้อความเมื่อสร้างเพิ่มไม่ได้
- [ ] logout แล้วใช้บัญชีทดสอบอีกคน; ไม่มีทะเบียนของคนก่อนหน้า
- [ ] ดูที่ 360px และ desktop พร้อม screenshot และตรวจ browser console ไม่มี pageerror
- [ ] ตรวจ TailAdmin shell/mobile sidebar, Thai typography และหน้า auth/TOTP เดิมว่าไม่มี style leakage
- [ ] ตรวจคำอธิบายการเปลี่ยนประเภท: ปิดไว้เพราะยังไม่มีหลักฐานครบ ไม่บอกว่าไม่มีออเดอร์แล้ว

## 4. ด่านที่ต้องเขียว

ก่อนรันต้องมี **ฐานข้อมูลทดสอบที่ทิ้งได้** แยกจากฐานข้อมูลเดโม/ผู้ใช้จริง
พร้อม env ของทุก role ตาม README ห้ามชี้ migration-cycle tests ไปฐานข้อมูลที่ต้องเก็บ
ใช้ config/postgres.env เป็นแหล่งรุ่น DB ที่เดียว และไม่ปิด safety gates เพื่อให้ผ่าน

Backend (working directory backend):

```sh
uv run alembic upgrade head
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run pytest
uv run python -m tiewtrade.services.api.openapi_export
```

Frontend (working directory frontend):

```sh
npm run gen:api
npm run lint
npm run typecheck
npm run test
npm run test:e2e
npm run build
```

หลัง artifacts อยู่ใน diff ที่ตั้งใจแล้ว เก็บ snapshot ก่อน export/gen รอบตรวจ
แล้วเปรียบเทียบเนื้อหาไฟล์ต้องเท่ากัน; ไม่ใช้ git diff --exit-code เป็นตัวอ้างว่า
generated artifacts ผิดเพียงเพราะยังไม่ได้ commit งานนี้ การตรวจ CI ตาม .github/workflows/ci.yml
ต้องผ่านหลังเจ้าของสั่ง commit/push และก่อน merge

ทุก safety gate ที่อยู่ใน pytest ต้องเขียว รวม core purity, money paths,
venue isolation, venue transport/endpoint safety, credential/log hygiene และ route classification
รายงานจำนวน pass/fail/skip และคำสั่งจริง; missing DB แล้ว skip ไม่เท่ากับผ่าน validation

## 5. Coverage ของ requirements

| Requirements | Validation |
|---|---|
| RQ-1, RQ-15, RQ-21 | V-2, V-3, V-13; identity ไม่ถูกอ้างว่าพิสูจน์แล้ว |
| RQ-2 | V-4–V-6, V-17; ไม่อนุมานว่ารู้บัญชีหลัก/ย่อยจาก key |
| RQ-3 | V-6, V-8, V-10, V-20, V-37, V-45 |
| RQ-4 | V-32–V-36, V-38 |
| RQ-5, RQ-9, RQ-22 | V-3, V-48 และตรวจ diff ไม่มี trading/venue operation ใหม่ |
| RQ-6, RQ-7 | V-48 + domain/import/safety gates เดิม; F-08 ไม่เพิ่มการอ่านตลาดหรือสูตรเงิน |
| RQ-8 | V-21–V-24 |
| RQ-10 | V-47 |
| RQ-11, RQ-12 | ถอนจาก F-08; ไม่ต้องสร้าง implementation/test ของ realtime หรือ stale balances |
| RQ-13 | V-1, V-19, V-42 |
| RQ-14 | V-19, V-20 และ direct DB denial; ยังไม่เปิด success branch เมื่อไม่มีหลักฐาน |
| RQ-16 | V-16; replacement ยังเลื่อนก่อนพิสูจน์บัญชีเดิม |
| RQ-17 | V-14–V-18, V-22, V-23 |
| RQ-18 | V-25–V-28, V-30 |
| RQ-19 | V-1, V-7, V-8, V-42 |
| RQ-20 | V-9–V-12, V-36, V-37 |

## 6. บันทึกผลหลัง implementation

ผล implementation และชุดทดสอบ F-08 บันทึกในหัวข้อ 7 พร้อม baseline, commands,
จำนวน tests, migration/race/audit rollback, ภาพ UI และ review outcomes
NC-21/NC-22 ของการใช้กระเป๋าเทรดยังคงอยู่แม้ทะเบียน F-08 ผ่านครบ


## 7. ผลตรวจ implementation — 2026-10-07

Baseline F-07 `7efbbfb`; branch `feature/f-08-sub-account-wallets`; working-tree implementation
ยังไม่ commit/push/merge งาน F-08 ใช้ข้อมูล synthetic และ FakeVenue เท่านั้น
ไม่มีการเรียกตลาดจริงหรือเก็บ credential/ยอดเงินจริง

| ด่าน | ผลจริง |
|---|---|
| Backend pytest | **1,510 passed, 0 failed/errors/skipped**; 1 venue_contract deselected ตาม config เพื่อไม่เรียกตลาดจริง; 3 deprecation warnings เดิม |
| ruff check / format | ผ่าน; 213 files already formatted |
| mypy | ผ่าน; 196 source files |
| import-linter | 6 contracts kept, 0 broken |
| Frontend Vitest | **54 passed**, 8 suites; auth/TOTP/key regression รวมอยู่ด้วย |
| frontend lint / typecheck / build | ผ่าน; React 18/Vite 6/Node 22 + Tailwind 4.3.3; ไม่เปลี่ยน framework major |
| Playwright E2E | **8 passed**; browser→API→DB→worker/FakeVenue→wallet→reload→delete→DISCONNECTED→logout |
| OpenAPI / generated types | export/gen ซ้ำแล้ว hash เท่ากันทุก byte |
| Docker | backend/frontend image build ผ่าน; frontend production build ใน Linux ผ่าน; API health และ UI→/api/health proxy ผ่าน |
| Review | task API + final whole-feature review; ข้อพบ implementation/coverage ที่รายงานแก้แล้ว; final spec/quality PASS |
| UI evidence | ตรวจภาพ desktop และ viewport 360px; ไม่มี overflow/pageerror; sidebar Escape/backdrop คืน focus; native auth styles ก่อน/หลังเท่ากัน |

ใช้ `.venv/bin/{alembic,ruff,mypy,lint-imports,pytest,python}` แทน `uv run` เพราะ
sandbox ไม่ให้เขียน user uv cache; เป็น tools จาก environment ของโปรเจกต์เดิม
frontend ใช้ npm scripts ตามหัวข้อ 4 ทุกด่าน DB ใช้ actual roles บนฐานข้อมูลทดสอบแยก
ที่สร้างเฉพาะรอบนี้ ไม่ใช้ฐานข้อมูลเดโม/ผู้ใช้จริง และไม่มี DB tests ที่ skip

### หลักฐาน criteria และการแก้จาก review

| Criteria | หลักฐาน |
|---|---|
| V-1–V-3, V-7–V-8, V-13, V-19–V-20 | HTTP wallet tests + immutable summaries; MANUAL/BOT, all nonACTIVE states, fixed404 for foreign/missing, no trading/account identity claims |
| V-4–V-6, V-9–V-12, V-17 | actual DB constraints/permissions/concurrency; count5→6 race, duplicate across rows/owners, same-tail/case-distinct fixtures, retained quota |
| V-14–V-18 | direct FK/digest NULL assertions; real key DELETE; two bind/delete lock orders using events/barriers; registry retained, no replacement route |
| V-21–V-24 | Python/SQL audit shapes; UUID-only references; injected creation failure at CREATED/BOUND and disconnect-audit failure rollback all changes |
| V-25–V-30 | actual HTTP session/CSRF/fresh TOTP; key-add code replay refused; recovery-login grant refused; wrong code refused; alternating key/wallet failures share quota and both reach429; route classification |
| V-31 | actual session last_seen/idle/absolute timestamps unchanged after three GET /wallets |
| V-32–V-38 | DTO/OpenAPI/role permissions; sanitized input and duplicate DB failure; DEBUG log capture contains no synthetic public-key/secret markers; fingerprint not readable/writable by API |
| V-39–V-41 | migration cycles; populated downgrade refusal preserves row/revision/no leaked temporary policy; audit retained after empty downgrade/upgrade; UTC/deterministic order assertions |
| V-42–V-45 | WalletPanel/AccountSession tests; actual two-panel DELETE invalidation, refetch failure/stale disclosure, timeout/no auto retry/no credential mutation variables, old GET and old POST completion after identity switch leave new account unchanged |
| V-46–V-48 | 360px/desktop E2E screenshots, keyboard sidebar/focus, Thai i18next; no balances/WebSocket/new venue operations; FakeVenue-only worker verification |
| V-49–V-52 | artifact regeneration stable, full gates and review, Docker build/runtime, scoped theme without Preflight/remote fonts, original auth/TOTP/key regression |

TDD evidence: ก่อน schema มี wallet tests แดงจาก table ที่ยังไม่มี;
ก่อน storage มี tests แดงจาก missing module; ก่อน API GET /wallets ปฏิเสธ unclassified;
ก่อน UI มี missing AccountSession/WalletPanel/Layout tests แดง ทั้งหมดผ่านหลัง implementation
และมี regression tests จาก review เพิ่มในชุดสุดท้าย

E2E รอบแรกพบ future TOTP ที่ test สร้างผิด และโควตา signup ร่วมที่ใช้จนเต็ม;
ปรับ test ให้รอรหัสช่วงปัจจุบันใหม่จริง และ reset auth_throttle test state ผ่าน role เดิม
ก่อนแต่ละ case เหมือน backend fixture โดยไม่ปิด rate limit; ใช้หนึ่ง worker เพื่อไม่ให้
FakeVenue scan ของต่างไฟล์แย่ง pending keys จาก DB ร่วมกัน
อีก failure เป็น Thai substring locator ที่ตรงสองปุ่ม แก้ exact matching แล้วครบ8ผ่าน

ภาพและ review record อยู่ที่ `specs/reviews/2026-10-07-f08-wallets/` และ
`specs/reviews/2026-10-07-f08-wallets-validation-audit.md`
รายการตรวจด้วยมือในหัวข้อ 3 ใช้หลักฐาน browser/E2E และภาพ synthetic ร่วมกับ HTTP/DB/UI tests
สำหรับ quota/BOT/MANUAL/ownership; ไม่อ้างว่าได้ทดสอบบัญชีหรือ key จริง

### ความเสี่ยงที่คงอยู่

NC-21/NC-22 ยังต้องปิดก่อนใช้ทะเบียนเทรด; F-08 ไม่พิสูจน์บัญชีจริงและยังไม่เปลี่ยน key/use
เมื่อไม่มีหลักฐานครบ ส่วน license tier ของ TailAdmin ที่เจ้าของซื้อไม่ปรากฏใน source;
ตรวจเงื่อนไขการแจกจ่ายก่อนเผยแพร่ตาม README ต้นฉบับ

Docker npm ci/npm audit รายงาน dev dependencies เดิม4รายการ (2 critical,1 high,1 moderate):
vitest3.2.4, @vitest/mocker3.2.4, tinypool1.1.1, source-map-js1.2.1
เปรียบเทียบ HEAD lockfile แล้วทั้งสี่รุ่นไม่เปลี่ยนจาก F-07; ไม่มี dependency เหล่านี้
ใน runtime bundle ที่ใช้เทรด แต่ต้องประเมิน/แก้ในงาน dependency maintenance แยก
ไม่อัปเกรด test stack นอกแผนหรืออ้างว่า npm audit ผ่าน ดู advisory links ใน review record
