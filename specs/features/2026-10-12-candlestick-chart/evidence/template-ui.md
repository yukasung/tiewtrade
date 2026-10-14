# Admin-template presentation update

วันที่: 2026-10-13 (Asia/Bangkok)
ที่มา: เจ้าของสั่งใช้ code admin-template; ใช้ approved F-08 UI presentation
approach และ F-12 RQ-20 ร่วมกับ navigation plan ส่วนเพิ่ม.

## Source ที่ใช้จริง

- `references/admin-template/src/layout/AppLayout.tsx`: sidebar แยกจาก workspace,
  header และ page content ภายใน workspace; คง main landmark เดียวของ App เดิม.
- `references/admin-template/src/components/common/PageBreadCrumb.tsx`:
  ปรับเป็น `frontend/src/layout/PageBreadcrumb.tsx` พร้อม translated labels และ
  internal path links เดิม. Sidebar แสดง active module ชัดเจน.
- `references/admin-template/src/components/common/ComponentCard.tsx`:
  ปรับเป็น `frontend/src/components/ui/ComponentCard.tsx`; card header/body,
  responsive spacing และ headings/description ใช้กับกราฟและราคาสด.
- `frontend/src/components/ui/{Select,Button}.tsx`: components ที่ปรับจาก template
  เดิม ใช้ร่วมใน chart controls. หน้าบัญชี/TOTP/API keys/trading account/auth
  คง template presentation และ controls เดิม; ใช้ shared shell ที่ปรับใหม่.

ไม่เปลี่ยน API, orders, modes, financial values หรือ session handlers;
ไม่เพิ่ม dependencies/demo accounts/balances จาก template เข้า runtime.

## ผลตรวจ

| Check | Evidence | Result |
|---|---|---|
| Targeted UI/auth/session/security/chart/price tests | [template-ui-tests.xml](template-ui-tests.xml), Node 22 Vitest, 10 selected files | 124 passed, 3 failed: TOTP tests เดิมยังคาดว่า module อยู่หน้า default |
| TOTP หลังปรับ tests ให้เปิด `/security` และ `/account` ตามกรณี | [template-ui-totp-fixed.xml](template-ui-totp-fixed.xml) | 5 passed; ไม่ลด assertions ของ QR, backup codes หรือ auth challenge. รวม 127 unique tests มี passing evidence ต่างรอบ ไม่ใช่ full suite |
| Affected source/tests lint / types | Node 22 ESLint selected files; `tsc --noEmit` | Exit 0; TOTP test lint หลังแก้ผ่าน |
| Real Chromium / controlled workers / isolated DB | `run_browser.py NODE22 --grep 'actual chart panes|module pages|password login' --reporter=list,junit`; [template-ui-e2e.xml](template-ui-e2e.xml) | 3 passed; layout 375/768/1440, keyboard/exact values/languages/attribution, module navigation/mobile, login/series switch/price worker |
| Image + Vite build | `docker compose --env-file config/postgres.env build frontend`; `exec -T frontend npm run build` | Exit 0 ทั้งคู่; Node 22/Vite6 |
| Local update | Chart dev override `up --no-deps --no-build -d frontend` | Exit 0; frontend image manifest `sha256:852aaabe9978ca70aff0b69f45a0ac99c73113e05dbc39a5b6d2ff000a88a80b` |
| Diff hygiene | `git diff --check` | No whitespace errors; pre-existing api-types LF/CRLF warning |

[ภาพกราฟจาก browser integration](template-chart.png) ตรวจด้วยสายตาแล้ว;
ใช้ fixture จริงของ E2E ไม่มีการสร้าง mockup. เป็น full-page screenshot ขณะ scroll
จากการตรวจค่า exact จึงแสดง sticky/fixed header/sidebar ณ scroll position ที่จับภาพ.
ผลรวมรับงานยัง Partial: owner manual และ remaining F-12 validation/CI คงค้าง
ตามรายงานก่อนหน้า. ไม่รัน full suite หรือ V-17 ซ้ำ และไม่แก้ข้อมูลประวัติว่าง/preview STALE.
