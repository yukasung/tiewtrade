# F-08 บัญชีเทรดเดียวต่อผู้ใช้ — Validation

สถานะ: **Approved** — เจ้าของสั่งแก้ review issue 3 วันที่ 2026-10-07 ให้ implement บัญชีเดียว/ความเลือกประเภทระดับบัญชีตามฉบับนี้
วันที่: 2026-10-07

Account dashboard visual refresh: **Approved 2026-10-31**; ดู [Validation Amendment](account-dashboard-visual-validation-amendment.md)
ผล1510/54/8และภาพก่อนหน้าคือscopeหลายกระเป๋าที่ถูกยกเลิก ไม่ใช่ผลผ่านฉบับนี้

ส่วนเพิ่ม TailAdmin ทุกหน้ามีสถานะ **Approved** ตามหัวข้อท้ายไฟล์
ผลผ่านเดิมไม่ยืนยันส่วนเพิ่มนี้

| # | เกณฑ์และหลักฐานที่ต้องได้ |
|---|---|
| V-1 | ไม่มี active wallet/sub-account registry/routes/DTO/menu/quota6/binding/UID-dedup; snapshot/OpenAPI/diffตรวจจริง ไม่ลบข้อห้ามย้ายเงิน |
| V-2 | API key cap1ทุกสถานะ: ชุดที่2ปฏิเสธ, DB UNIQUE(user_id)กันdirect/concurrent insert, คนละuserมีได้คนละ1 |
| V-3 | migrationไม่เลือก/ลบkeyของuserที่มีมากกว่า1; ถ้ามี0012เก่าใช้แล้วต้องไม่replace/erasehistory |
| V-4 | ก่อนเลือกuseเป็นnull; MANUALและBOTแต่ละcaseเลือกได้ทีละ1เมื่อkeyACTIVE/freshTOTP |
| V-5 | ไม่มีkey/nonACTIVEเลือกไม่ได้; concurrent initialselectionมีsuccess1และข้อมูล/auditไม่ครึ่งทาง |
| V-6 | ใช้รหัสที่เพิ่มkeyแล้วซ้ำไม่ได้; wrong/missingOTP/recoverygrant/CSRF/sessionปฏิเสธ ใช้quotaเดิม |
| V-7 | เมื่อ session/fresh TOTP ถูกต้องและหลักฐาน activity ไม่ครบ: API เปลี่ยนประเภทคืน HTTP 409 TRADING_ACCOUNT_ACTIVITY_UNKNOWN; direct SQL UPDATE/DELETE ผ่าน tiewtrade_api ถูกปฏิเสธสิทธิ์ (NotPermittedError) และ preference เดิมไม่เปลี่ยน; ไม่ใส่ idle ปลอม |
| V-8 | RLS/actualrolesกันข้อมูลข้ามowner; engine/scan/auth/market-dataไม่มีสิทธิ์ตารางpreferencesใหม่ |
| V-9 | auditshapePython/DBตรง; UUID+useเท่านั้น; auditfailrollbackpreference; auditเก่าไม่ถูกrewrite |
| V-10 | GETไม่ต่ออายุlast_seen/idle/absoluteexpiry;ทุกrouteอยู่ROUTE_RULES |
| V-11 | keyเต็ม/secretไม่ออกDTO/OpenAPI/error/log/audit/cache/localstorage;syntheticmarkersและactualroleprivileges |
| V-12 | deletekeyยังauthเดิมและไม่requireTOTP; delete/add/retry/statusrefetchไปsingleaccountpanelโดยsharedclient |
| V-13 | user switch/logout/401cancel+clear; lateGET/POSTไม่เปลี่ยนnewuser; querykeysมีuser_id |
| V-14 | mutationไม่มีauto retry/secretvariables;timeout/refetchfailureไม่แสดงสำเร็จหรืออ้างข้อมูลเก่าว่าใหม่ |
| V-15 | TailAdminคงอยู่;360px/desktop/keyboard/sidebarfocus/Thaii18n/authstyle regressionผ่าน;ไม่มีdemobalances/trades |
| V-16 | account/use selectionไม่เปิดLive/bot/trade;Money/Quantity/venue/endpoint/import/networkgatesเดิมผ่าน |
| V-17 | OpenAPI/genapi-typesรอบตรวจเท่ากันทุกbyte;frontendใช้generatedschemas |
| V-18 | migrationsในDBทิ้งได้:upgrade/emptydowngradecyclesผ่าน;populatedpreferencesdowngradeปฏิเสธ |
| V-19 | backend/frontend/E2E/static/Dockerbuildruntimeทุกด่านผ่านจริง ไม่มีDBskip;logpass/fail/skip/deselectedตามจริง |
| V-20 | independentreviewหลังเปลี่ยนscope + coverageนี้ผ่าน ก่อนCompleted;devdependencysecuritybacklogเดิมยังบันทึกไว้ |

## Tests ที่ต้องสร้าง/ปรับ

- backend/tests/infra/trading_account/{test_storage,test_permissions,test_concurrency,test_audit}.py
- backend/tests/api/test_trading_account_routes.py
- backend/tests/infra/api_keys/ และAPIkey/worker tests สำหรับcap1และowner separation
- backend/tests/infra/db/test_migrations.py, auditshape/routeclassification/safetygates
- frontend/tests/TradingAccountPanel.test.tsx, AccountSession/ApiKeyPanel/AccountLayout tests
- frontend/e2e/trading-account.spec.ts, auth/TOTP/keyregressionและsyntheticscreenshots

## Commands หลังอนุมัติ

Backend: `uv run alembic upgrade head`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`, `uv run pytest`,
`uv run python -m tiewtrade.services.api.openapi_export`
ใช้ toolsจาก .venv เดียวกันได้เมื่อ uv cacheถูกsandboxปฏิเสธ โดยบันทึกคำสั่งจริง
Frontend: `npm run gen:api`, `npm run lint`, `npm run typecheck`, `npm run test`,
`npm run test:e2e`, `npm run build`; Dockerimagebuild/Linuxbuild/APIhealth/UIproxy
ใช้disposableDBแยกbackend/E2E มีenvครบactualroles;ไม่drop/resetฐานข้อมูลผู้ใช้จริง

## ผลปัจจุบัน

implementation บัญชีเดียวตามคำสั่งแก้ issue3 เสร็จแล้วและผ่าน automated checks ด้านล่าง
review issue4/5/6แก้ครบและ final document reviews ผ่านแล้ว; ไม่มี review findings ค้างใน F-08; ไม่ใช้ผลหลายกระเป๋าเดิมแทนผลนี้

## Review issue 1 — เกณฑ์เฉพาะ security repair ที่เจ้าของสั่ง 2026-10-07

- environment ไม่มี declaration/ฐานทั่วไป/remote/malformed/roleผิด/host-port-database
  ไม่ตรง/query override ต้อง fail ก่อน server start หรือ DELETE โดยไม่ echo secret
- config/fixture ใช้ validator เดียว; ไม่ reuse server และ frontend proxy ชี้ API ของ E2E
- AUTH connection ตรวจ current_database() ก่อน DELETE ใน transaction เดียวกัน
- E2E CI ใช้ isolated database; full frontend tests/typecheck/lint ผ่าน
- รัน E2E ด้วย actual roles บน disposable database และบันทึกผลตามจริง
- ผลนี้รับรองเฉพาะ issue 1 ไม่ใช่ validation บัญชีเดียวทั้งฉบับ

ผลตรวจ issue 1 (2026-10-07):

- TDD: guard tests 18 กรณีแดงเมื่อ validator ยังไม่ตรวจ environment แล้วเขียวหลังแก้
- `npm run test`: 72 passed ใน 9 suites; `npm run lint`, `npm run typecheck`,
  `npm run build` และ `git diff --check` ผ่าน
- Playwright เมื่อไม่มี TIEWTRADE_E2E_DATABASE_NAME ปฏิเสธตอนโหลด config
  ด้วย E2E_DATABASE_REJECTED ก่อนเริ่ม server
- `npm run test:e2e`: 8 passed (42.4s) บน PostgreSQL16 container แยก
  `tiewtrade-issue1-e2e-db` ฐาน `tiewtrade_e2e_review`, actual roles/bootstrap/migrations
- รัน Python script ตัวเดียวกับ fixture บนฐานทิ้งได้: เมื่อ declaration ไม่ตรง
  current_database() ปฏิเสธและ throttle sentinel ยังอยู่; เมื่อตรงล้างได้ด้วย AUTH role
- ตรวจแล้วลบเฉพาะ container ทดสอบนี้; ไม่ migrate/drop/reset ฐานข้อมูลผู้ใช้
- ยังไม่ผ่าน validation บัญชีเดียวทั้งฉบับ และไม่ได้ commit/push

## Review issue 2 — main landmark

เกณฑ์เฉพาะที่เจ้าของสั่ง 2026-10-07: AccountLayout ภายใน page main ต้องเหลือ
main landmark หนึ่งแห่ง เนื้อหายังอยู่ใต้ landmark และ keyboard/sidebar tests ผ่าน

ผลตรวจ: regression test แดงก่อนแก้ (พบ main 2 แห่ง) แล้วเขียวหลังเปลี่ยน
account-content เป็น div; `npm run test` 73 passed ใน 9 suites,
typecheck/lint/build และ `git diff --check` ผ่าน
CSS ใช้ class account-content จึงยังใช้กับ container ใหม่ได้
ไม่ได้รัน E2E ซ้ำสำหรับการเปลี่ยน element นี้ และยังไม่ได้ commit/push

## การอนุมัติ implementation จาก review issue 3

เจ้าของสั่งแก้ issue 3 วันที่ 2026-10-07 หลังได้รับข้อค้นพบและแนวแก้บัญชีเดียว
คำสั่งนี้อนุมัติการถอด multi-wallet, cap1, server preference และ initial-use flow
ตามเอกสารชุดนี้; ไม่อนุมัติ subscription หรือ trading execution เพิ่มเติม
ณตอนแก้ issue3 ประเด็น manual opening หลังหยุดบอทยังเป็น NC23; เจ้าของสั่งแก้ issue4 ต่อมาและปิดแล้ว
F-08 metadata ยังคง may_trade=False; issue5/6ปิดแล้วจากคำสั่งแก้ของเจ้าของ

## ผล implementation บัญชีเดียว — review issue 3 (2026-10-07)

- Preconditions: อ่าน actualDB เดิมผ่าน superuser metadata-only พบ revision0010,
  ไม่มี wallet_registry, จำนวน owner ที่มี key มากกว่า1เป็น0 จึงถอด0012เดิมที่ยังไม่ใช้
  ไม่ migrate/reset/drop ฐานเดิม; ใช้เฉพาะ disposable databases สำหรับการตรวจ
- Backend full:1480passed,0failure,0error,0skipped; venue_contract1deselected ตามconfigเดิม;
  3deprecationwarningsเดิม,80.03s. ตรวจจำนวนจาก JUnit XML แยกจากข้อความ pytest
- Infra/audit/migration/key/worker subset281passed รวม cap1ทุกสถานะ/direct/concurrentinsert,
  initialselection race และ select/delete raceทั้งสองลำดับ, atomic audit/RLS/actualroles,
  migrationหลายkeyปฏิเสธไม่ลบrows/policyไม่รั่ว และ downgradeไม่ทำลาย preference/audit
- HTTP/auth/key/route regression91passed รวม owner isolation, nulluse/ACTIVE-only,
  initialMANUAL/BOT, same/change409ด้วยfreshTOTP, OTPreplay/recovery/CSRF/quota,
  GETไม่ต่อsession, sanitizedinput และ auditfailrollback
- Frontend85passed/9suites; lint/typecheck/buildผ่าน; แสดง stale เมื่อ refetchล้มเหลว,
  lateGET/POSTไม่ข้ามowner, cap1ทุกสถานะ, explicituse/noTOTPvariables,
  add/delete/retry/poll เปลี่ยน single-account query ผ่าน sharedclient
- E2E8passed30.6s รอบ final ใช้ actualAPI/roles/DB/worker และ FakeVenue;
  selectBOT/reload/deletekeyคงpreference/logout, 360px/sidebarfocus/nativeauthstyles
- Ruffcheck/format213files, mypy196sourcefiles, importcontracts6/0brokenผ่าน
- OpenAPI/frontendgeneratedtypesสร้างซ้ำเหมือนเดิมทุกbyte; walletregistryroutes/DTOไม่มีแล้ว
- Docker API/UI imagesbuildผ่าน; Linuxfrontendproductionbuildผ่าน;
  APIhealthและUIproxy /api/healthผ่าน บนcontainerที่เชื่อม disposableDBเท่านั้น
- ภาพ desktop/360px ตรวจด้วยตาและเก็บใน specs/reviews/2026-10-07-f08-single-account/
- V-7 หลักฐานจริงคือ API409 และ directDBpermissiondenialตามplan;
  เจ้าของสั่งแก้ issue5 แล้ว เกณฑ์แยก API กับ directDB ชัดเจน ไม่อ้างว่า DBคืนHTTPstatus
- ผล independent finalreviewบันทึกในรายงาน review แยก; issue3ไม่เปิด trading/Live/bot
  และไม่เพิ่ม balances/UIDproof. Dependencysecuritybacklogเดิมยังไม่แก้ในscopeนี้
- ยังไม่ได้ commit/push/merge; เอกสาร/reviewค้างจัดการครบแล้วและอัปเดตroadmapตามผลตรวจ

## Review issue 4 — ผลตรวจเอกสาร (2026-10-07)

เกณฑ์: mission/trading-safety/requirements/roadmap ต้องไม่มีสิทธิ์ manual opening
โดยไม่ตรวจประเภทหลังหยุดบอทหรือชนเพดาน; restart ไม่สลับประเภท/ไม่เพิ่ม TOTP ใหม่
ทุกประเภทลดความเสี่ยงได้ตามหัวข้อ3 และการเปลี่ยนประเภทต้องใช้หลักฐาน RQ-6
standards/testing ระบุกรณี BOTหยุด/MANUAL/ลดความเสี่ยง/เปลี่ยนประเภทหลักฐานไม่ครบ

ผล: แก้ข้อความขัดแย้งครบในเอกสาร active; NC23Closed; ตรวจ git diff --check ผ่าน
ไม่มีการแก้ runtime code จึงไม่รัน unit/integration/E2E ซ้ำ
การทดสอบ order/kill-switch ตามเกณฑ์ใหม่ต้องทำใน F-16/F-19/F-22 ที่ยังไม่ implement
ไม่อ้างว่าการตรวจเอกสารนี้พิสูจน์การส่ง/ปิดออเดอร์จริงแล้ว

## Review issue 5 — ผลตรวจการแยก API/DB (2026-10-07)

เจ้าของสั่งแก้ V-7 ให้ตรงกับ plan ที่ให้ tiewtrade_api เฉพาะ SELECT/INSERT
แก้เกณฑ์เป็น HTTP409/TRADING_ACCOUNT_ACTIVITY_UNKNOWN สำหรับ API ที่ผ่าน auth/TOTP
และ NotPermittedError สำหรับ direct SQL UPDATE/DELETE ด้วย API role พร้อมข้อมูลเดิมคงอยู่
ไม่กำหนด HTTPstatus ให้ PostgreSQL หรืออ้างว่า guard นี้จำกัด superuser

ตรวจเทียบ plan หัวข้อ3, migration0012 GRANTs,
backend/tests/api/test_trading_account_routes.py::test_existing_preference_refuses_changes_with_fresh_totp
และ backend/tests/infra/trading_account/test_permissions.py::test_api_cannot_mutate_or_read_extra_columns
ซึ่งอยู่ใน full backend1480passed ของ issue3; issue5แก้เฉพาะเอกสารจึงไม่รัน suite ซ้ำ
ตรวจ git diff --check ผ่าน; issue5ปิดแล้ว เหลือissue6

## Review issue 6 — ผลตรวจ research (2026-10-07)

เกณฑ์: research มีขอบเขตบัญชีเดียวปัจจุบันและลิงก์ requirements; UID/dedup/
wallet replacement กับร่าง support แสดง Superseded ชัด; รหัส RQ เก่าไม่สับสนกับรหัสใหม่
หลักฐาน/link/dateเดิมยังอยู่; อำนาจ key ยังติดตาม NC-16 โดยไม่อ้างว่าความเสี่ยงหมดไป

ผล: ตรวจข้อความและ git diff --check ผ่าน; issue6ปิดแล้ว
แก้เฉพาะเอกสาร ไม่เรียกตลาดหรือส่งข้อความ และไม่รัน suite โค้ดซ้ำ

## Final review closure (2026-10-07)

Independent code review และ final document consistency/spec reviews ผ่าน
ไม่มี findings ค้างจาก issues1–6; ทุกเกณฑ์ V-1 ถึง V-20 มีหลักฐานของ scope บัญชีเดียว
V-7 ใช้ผล API/directAPIroleDB ที่แก้ถ้อยคำแล้ว; V-20 รวม final doc reviews หลังissues4–6
ไม่มี runtime changes หลัง full test/static/Docker/E2E runs ที่บันทึกไว้ จึงไม่รัน suite ซ้ำ
NC-16 และงาน order/position/Live/billing ภายหลังยังอยู่นอก F-08 ตาม requirements
ตรวจ git diff --check ผ่าน; ไม่ถือว่า authorize commit/push/merge

## Re-review issue 1 — เกณฑ์ก่อนแก้ logout (2026-10-07)

- logout/logout-all POST สำเร็จแล้ว signed-in boundary หายและ caches เดิมถูก clear
  pending GET ถูก abort ก่อนรอ identity lookup หรือ CSRF refresh
- ไม่เรียก /auth/me ซ้ำหลัง POST logout; identity failure/hang ไม่ทำให้ข้อมูลเก่าค้าง
- CSRF refresh failure/hang ไม่ทำให้ account boundary อยู่; late query/TOTP identity
  completion ไม่คืนข้อมูลบัญชีเก่า และ POST logout ที่ล้มเหลวไม่อ้างว่าสำเร็จ
- ทั้งสอง logout endpoint, auth/AccountSession regression, lint/typecheck/build ผ่าน
- re-review issue2/V14 success notices ยังไม่ได้แก้; ห้ามอ้างว่าทุก review findings ปิดแล้ว

## Re-review issue 1 — ผลแก้ logout (2026-10-07)

- Regression ใหม่ AuthPanelLogout13cases ผ่าน: ทั้งสองlogout endpoints,
  identity/CSRF errorหรือhang, querycancel/cacheclear, latequery/TOTPidentity,
  pendingkeyDELETE mutationcacheclear/latecompletion และ POSTfailureไม่อ้างlogoutสำเร็จ
- TDD:11casesแรก9failed2passedก่อนแก้;หลังแก้11passed; เพิ่ม2cases pendingmutation
  เป็นหลักฐานเพิ่มเติมที่ผ่านพฤติกรรมเดิมของ AccountSession cleanup โดยไม่แก้ productionเพิ่ม
- Fullfrontend98passed/10suites; lint/typecheck/build และ git diff --check ผ่าน
- E2E8passed33.1s บนฐาน tiewtrade_e2e_logout_fix ใน disposablePostgreSQL16
  actualroles/bootstrap/migrations/API/FakeVenue; cleanupเฉพาะcontainerทดสอบนี้
- Independent scope reviewPASS: handlerถอดboundaryหลังPOSTก่อนCSRF,
  POSTfailureคงidentity และ lateTOTPresponseไม่คืนboundaryที่ logoutแล้ว
- ไม่แก้backend/schemaจึงไม่รันbackend suiteซ้ำ; ไม่อ้างDocker checksเดิมว่าเป็นbuildหลังrepairนี้
- V13/logout issue1ปิดแล้ว; re-reviewissue2/V14keysuccessnoticeยังค้าง
  roadmapคงInProgressและยังไม่ได้commit/push/merge

## Re-review issue 2 — เกณฑ์ก่อนแก้ key feedback (2026-10-07)

- add/retry/delete responseสำเร็จ + failed keyGETหรือaccountGET ไม่แสดงsuccessnotice
  แสดงrefresh warning/stale data, no mutationretry และไม่เผย credentials/rawerror
- delayed accountGET ต้องไม่มีsuccessnoticeก่อนตอบ; หลังทั้งสองqueryfreshแสดงได้
- manualrefreshเมื่อเครือข่ายกลับมาปลดgateได้โดยไม่ส่ง mutationซ้ำ
- stale key dataต้องไม่แสดงnoticeเก่าเป็นsuccess; happy paths/auth/logout/identityraceผ่าน
- ใช้generic warningไม่มีrawdriver/servertext, credentialinputs/cacheยังclearตามเดิม

## Re-review issue 2 — ผลแก้ key feedback (2026-10-07)

- TDD:9casesใหม่แดง/24เดิมเขียวก่อนแก้; หลังแก้ ApiKeyPanel33casesผ่าน
  ครบadd/retry/delete × failed keyGET/accountGET และ delayed accountGET
  ยืนยันmanualrecovery/no duplicate mutation/credentialclear/rawerrorไม่ออกUI
- Integration test DELETE+accountrefetchfail ปรับตรวจalertในแต่ละpanelอย่างเจาะจง
  และเพิ่มassertไม่มีข้อความลบสำเร็จ แทนการสมมติว่าทั้งหน้ามีalertเดียว
- Fullfrontend107passed/10suites; lint/typecheck/build/diffcheckผ่าน
- E2E8passed45.4s ใช้ disposableDB tiewtrade_e2e_key_feedback กับ actualroles/API/
  worker/FakeVenue; auth/logout/persistence/keyflow/360pxผ่าน
- RebuiltfrontendDockerimageและLinuxproductionbuildผ่าน; APIhealth/UIproxyhealthผ่าน
  ใช้APIimageเดิมที่codebackendไม่เปลี่ยนกับdisposableDBเท่านั้น
- Independent scope reviewPASS: sequentialkey/accountrefresh + status/fetchidle/
  invalidated checks กัน swallowed errors/cancelled fetch; noticesรอข้อมูลยืนยัน
  และ qualifiedwarning/manualrecoveryไม่ส่งmutationซ้ำ ไม่มีการแก้backend/schema
- Re-reviewissues1/2ปิดแล้ว V13/V14มีregressioncoverage; บันทึกผลล่าสุดที่roadmap
- ยังไม่commit/push/merge และยังไม่เปิดtrading/bot/balance/Live

## ส่วนเพิ่ม — TailAdmin ทุกหน้าปัจจุบัน

สถานะส่วนเพิ่ม: **Approved** — เจ้าของตอบ approve วันที่ 2026-10-07
วันที่: 2026-10-07
ข้อกำหนด: ui-template-requirements-amendment.md (Approved)
implementation ส่วนเพิ่มเสร็จและตรวจแล้วตามผลท้ายหัวข้อนี้; ผลก่อนหน้าเป็น baseline

| รหัส | เกณฑ์ผ่าน | วิธีตรวจ / ข้อกำหนด |
|---|---|---|
| UI-V-1 | login/register/second-step ใช้ auth layout อ้างอิง TailAdmin และแบรนด์ TiewTrade ไม่แสดง sidebar ก่อน login | AuthLayout/AuthPanel tests + desktop/mobile screenshots; UI-RQ-1 |
| UI-V-2 | account details/TOTP/key/trading-account อยู่ใน AccountLayout ใช้ controls/theme เดียวกัน | ตรวจ DOM/components/tokens และ screenshots; UI-RQ-2/5 |
| UI-V-3 | setup/replace/reissue/disable TOTP และ recovery login ทำงานเหมือนเดิม; QR สร้างใน browser และ URI fallback อ่านได้ | TotpPanel tests + totp/auth E2E; UI-RQ-3/6 |
| UI-V-4 | health/error แสดงข้อมูลจริงใน footer แบบ template; ไม่มี native heading นอกกรอบและมี main เดียว | App tests ทั้ง anonymous/signed-in + browser DOM; UI-RQ-4/7 |
| UI-V-5 | login/logout ทั้งสองแบบ/CSRF failure/late GET/POST ไม่คืน cache หรือ identity ของผู้ใช้เก่า; secret clearing เดิมผ่าน | AuthPanelLogout/AccountSession/key/account tests เดิมทุกข้อ; UI-RQ-6 |
| UI-V-6 | 360px ไม่มี overflow ทั้งฟอร์ม/QR/URI/recovery list/account panels; 1440px auth สองคอลัมน์ | วัด scrollWidth เทียบ viewport + screenshots; UI-RQ-1/7 |
| UI-V-7 | keyboard เข้าถึง controls/เมนูได้ focus ชัด labels/errors/status ใช้ semantics ถูกต้อง disabled/loading คงเดิม | browser keyboard + layout/auth/TOTP tests; UI-RQ-7 |
| UI-V-8 | ข้อความ presentation ที่แก้มีไทย/อังกฤษและ interpolation; ไม่มี demo balances/trades หรือ controls ของฟีเจอร์ที่ยังไม่รองรับ | AuthMessages tests + source/visual review; UI-RQ-8 |
| UI-V-9 | ไม่มี backend/schema/dependency/router เปลี่ยนหรือ reference/demo import เข้า runtime | git diff + import/package review; UI-RQ-9 |
| UI-V-10 | frontend tests/lint/typecheck/build และ E2E ผ่านหลังแก้ส่วนเพิ่ม; เก็บผลและภาพจริง พร้อม preview URL ที่ตอบได้ | คำสั่งใน plan ส่วนเพิ่มข้อ4 + health/proxy smoke; UI-RQ-10 |

ตรวจด้วยมือบน preview: สมัคร → logout → login → เปิด TOTP/QR/รหัสสำรอง
→ logout → login ด้วย TOTP/รหัสสำรอง → ตรวจ account/key/trading UI
ใช้บัญชีทดลองและข้อมูลทดสอบ ไม่มีการเทรดจริง; key ACTIVE/use flow ใน E2E
ใช้ FakeVenue เดิม ไม่เรียก exchange จริงเพื่อให้ผลภาพหรือ tests ผ่าน
ตรวจ English ผ่านระบบแปลใน tests โดยไม่เพิ่ม language-switch feature ของ F-30

ด่านส่วนเพิ่มต้องผ่านก่อนบันทึก Completed ใหม่; reviewer ตรวจ mapping
UI-RQ-1–10 กับ UI-V-1–10 และรักษา V-1–20 ของ scope เดิม

ผลส่วนเพิ่ม 2026-10-07:

- UI-V-1–10 ผ่าน: frontend113 tests/13 suites (4.00s), lint/typecheck/build ผ่าน
  build145 modules; CSS13.56kB/JS297.54kB
- E2E8 tests ผ่าน26.3s บน tiewtrade_e2e_ui_template/port55444 พร้อม actualAPI/roles/FakeVenue
  และ environment guard เดิม; targetedauth/TOTP4testsผ่าน6.0sก่อน finalfullrun
- keyboard Tab จากแบรนด์ไป email/password และ outline solid ผ่าน;
  registration POST ถูก hold ชั่วคราวเพื่อยืนยัน disabled/opacity0.6 แล้วปล่อยใน finally
  desktop brand visible/mobile brand hidden และ mainเดียว/nooverflowผ่าน
- ภาพ23ไฟล์ใน `specs/reviews/2026-10-07-f08-single-account/ui-template/`
  login/register/second-step/account/enrollment/recovery/error/pending ทั้ง1440/360
  พร้อมภาพkey/trading-account; ตรวจภาพตัวแทนแต่ละ flow แล้ว QR/URI/recovery wrap ได้
  ภาพ credential ทั้งหมดมาจากบัญชีและฐานทดสอบ disposable ไม่มีข้อมูลบัญชีจริง
- เพิ่ม TotpPresentation4 tests สำหรับ replacement/reissue/disable/pending+failure
  ผ่าน; login recovery-count และ credential clearing tests เดิมผ่าน
- Standards review: ย้าย typography literals3ค่ามา theme tokensแล้ว ปิด finding;
  Spec review: keyboard/brand/disabled evidenceเพิ่มแล้ว ไม่มี code findings ค้าง
- Preview frontend rebuilt ตาม sourceล่าสุด; `http://localhost:5182/` และ
  `/api/health` ตอบสำเร็จ คง API/DB preview เดิม ไม่มีการล้างข้อมูลผู้ใช้
- ปิด containerฐานE2Eชั่วคราวแล้ว; previewยังเปิดสำหรับเจ้าของตรวจ
  backend/schema/dependencies/auth/query handlers ไม่เปลี่ยนจาก baseline
  ไม่อ้าง npm audit หรือ Live readiness ผ่านจากงานนี้; ยังไม่commit/push/merge
