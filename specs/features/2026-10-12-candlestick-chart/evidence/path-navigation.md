# Path navigation correction

วันที่: 2026-10-13 (Asia/Bangkok)
เจ้าของสั่ง “แก้ไขให้ถูกต้อง” หลังยืนยันว่าต้องการ URL ของแต่ละหน้าโดยไม่มี `#`.
บันทึกข้อกำหนด/แผนส่วนเพิ่มก่อนแก้โค้ด; รายงานนี้แทนสถานะ routing ใน
[navigation implementation รอบ hash](navigation-implementation.md).

## ผลการแก้

ใช้ `/chart` เป็น default และ `/account`, `/security`, `/api-keys`,
`/trading-account`, `/prices` เป็น URL ของ module. Internal links ใช้ History API
และ `popstate` โดยไม่ reload session provider; modified click/new tab ยังทำงาน
แบบ browser ปกติ. Inactive module unmount และรักษา auth/cache cleanup เดิม.

Vite ตั้ง `appType: "spa"` ชัดเจนสำหรับ direct link/reload บน dev/preview server.
Proxy เปลี่ยนจาก prefix `/api` เป็น `^/api(?:/|$)` เพื่อไม่ส่งหน้า `/api-keys`
ไป backend; endpoint `/api/...` และ WebSocket proxy ยังใช้ config เดิม.
แก้ links และ affected tests/E2E เป็น paths ไม่มี hash.

## Verification

- Host Node 22, `vitest run` เลือก AccountNavigation, AuthPanel, AuthPanelLogout,
  AccountLayout, AccountSession, ApiKeyPanel, TradingAccountPanel และ
  RealtimePricePanel: [119 passed / 8 files](path-navigation-tests.xml), exit 0.
  รวม plain-click navigation, QueryClient เดิม, modified-click handling,
  default/disabled flag, identity/session cleanup และ security panels เดิม.
- `tsc --noEmit`: exit 0. ESLint affected source/tests/E2E/config:
  แก้ unnecessary type assertion ใน test แล้ว selected lint check ผ่าน;
  config lint หลังแก้ proxy ผ่าน. การแก้ type-only test ไม่เปลี่ยน behavior ที่ทดสอบ.
- Real Chromium / isolated E2E DB / controlled workers:
  `run_browser.py NODE22 --grep 'module pages|gap selection|password login' --reporter=list,junit`
  ให้ [2 passed, 1 failed](path-navigation-e2e.xml). Failure เป็น direct request
  `/api-keys` ถูก proxy ไป backend; ไม่ได้เป็นปัญหา session หรือ module selection.
- หลังแก้ proxy รันเฉพาะ `--grep 'module pages'`:
  [1 passed](path-navigation-fixed-e2e.xml), exit 0. ครอบคลุมหก module,
  Back/Forward, direct link/reload, mobile nav และหยุด chart requests เมื่อออกหน้า.
  ผลเดิมของ gap/logout และ password login/price worker ไม่ถูกรันซ้ำ;
  ไม่อ้างว่าเป็น single all-green E2E run ของ final inputs.
- `docker compose --env-file config/postgres.env build frontend`: exit 0;
  `up --no-deps --no-build -d frontend` พร้อม chart dev override: exit 0.
  Final image manifest `sha256:6e02e1d45073289fc6a2d9529bb979541c88c7c40c8a55c5ae7f8ce22328fa4e`.
- Deployed localhost Chromium smoke: direct request และ reload ทั้งหก paths
  HTTP 200, URL ไม่มี hash, unauthenticated แสดง login ตามเดิม,
  ไม่มี pageerror; proxied `/api/health` HTTP 200. ไม่สร้างบัญชี dev เพิ่มในรอบนี้.
- `git diff --check`: ไม่มี whitespace errors; no hash routing references ใน
  affected frontend source/navigation test/E2E. ไม่รัน full suites หรือ V-17.

## Remaining

Owner manual, security mutation E2E แยกที่ยังค้าง, final review/CI และ coverage
ค้างของ F-12 ตาม [checkpoint](checkpoint.md) / [navigation report](navigation-implementation.md)
ยังไม่ได้ถือว่าผ่าน. งานนี้ไม่แก้ประวัติ candles ว่างหรือ feed STALE.
V-17 ยัง Pending Full Validation; F-12 ยัง In Progress.
เมื่อมี production hosting ต้องตั้ง SPA fallback ของ host นั้นตาม deployment plan;
รอบนี้ตรวจเฉพาะ Vite development deployment ที่ใช้อยู่จริง.
