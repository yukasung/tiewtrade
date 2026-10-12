# Navigation implementation checkpoint

วันที่: 2026-10-12 (Asia/Bangkok)
ข้อกำหนด/plan/validation ส่วนเพิ่มได้รับอนุมัติจากคำสั่งเจ้าของ “implement”.

## การเปลี่ยนแปลง

แยกหน้า `/#/chart` (default), `/#/account`, `/#/security`, `/#/api-keys`,
`/#/trading-account` และ `/#/prices`. ใช้ hashchange กับ history เดิม;
ไม่เพิ่ม dependencies. AccountSession ครอบทุกหน้าและรักษา QueryClient เดิม;
inactive module unmount. ลิงก์เปิด TOTP จาก keys/account เปลี่ยนเป็นหน้า security.
Chart flag ปิดยังไม่ mount chart/เรียก chart API; default แสดง disabled status.
ข้อความกราฟเปลี่ยนให้ระบุว่าราคาสดอยู่ในเมนูแยก.

## ผลตรวจ

| Check | Command / artifact | ผล |
|---|---|---|
| Initial targeted frontend | Node 22 `vitest run` เลือก navigation, auth/logout, layout, session และ chart controller; [navigation-targeted.xml](navigation-targeted.xml) | 39 passed, 1 failed: test 401 เดิมยังสมมติว่า trading account mount ที่ default |
| Follow-up หลังแก้ test ให้เปิดหน้า trading account ก่อนตรวจ 401 | Node 22 `vitest run` เลือก navigation, session, logout และ realtime panel; [navigation-followup.xml](navigation-followup.xml) | 56 passed; รักษา assertion 401 ต้อง unmount authenticated boundary |
| API key / trading account panels | Node 22 `vitest run tests/ApiKeyPanel.test.tsx tests/TradingAccountPanel.test.tsx`; [navigation-panels.xml](navigation-panels.xml) | 54 passed; รวมลิงก์หน้า security ใหม่ |
| Static checks | Node 22 `tsc --noEmit`; ESLint affected source/tests และ `e2e` | Exit 0; initial tuple typing/async test lint errors แก้แล้วตรวจซ้ำผ่าน |
| Real browser chart/module integration | `run_browser.py NODE22 --reporter=list,junit`; isolated PG/Redis และ controlled workers; [navigation-chart-e2e.xml](navigation-chart-e2e.xml) | 8 passed: 7 chart stories ที่ปรับการเปลี่ยนหน้า และ navigation story ใหม่; ไม่ส่ง Live orders |
| Frontend image / Vite build | `docker compose --env-file config/postgres.env build frontend`; `docker compose --env-file config/postgres.env exec -T frontend npm run build` | Exit 0 ทั้งคู่, Node 22 image |
| Deployment | `docker compose --env-file config/postgres.env -f compose.yaml -f compose.chart.dev.yaml up --no-deps --no-build -d frontend` | Exit 0; recreate เฉพาะ frontend. Image manifest `sha256:53ed1205e54da8ffe38c92ae7740ec45c481378bec7c0208c761b2d46977f6d9` |
| Latest localhost smoke | Chromium ที่ `http://localhost:5173/`; สมัครบัญชี smoke แยกและเลือกทั้งหกเมนู | Default chart, URLs ทั้งหกถูกต้อง, inactive chart ไม่มีใน DOM, ไม่มี pageerror. บัญชี smoke สองบัญชียังคงอยู่ใน development DB |
| Diff hygiene | `git diff --check` | Exit 0; Git แจ้ง LF/CRLF warning ของ api-types เดิม |

Targeted checks รวม **129 unique tests / 9 files** ผ่านโดยอ้างอิงผลต่างรอบข้างต้น;
ไม่ได้รัน frontend/backend full suite ซ้ำ. Failed XML เดิมยังเก็บไว้.
Host browser smoke รอบแรกตรวจ account ด้วย marker `signed-in` ที่มีทุกหน้า
จึง assertion เร็วก่อน navigation commit; เปลี่ยนเป็นรอ module จริงและ retrying
assertion ของ Playwright แล้วตรวจทั้งหกหน้าผ่าน. ไม่แก้ production เพื่อหลบ assertion.

## Coverage / remaining

- NV-01/02: targeted tests และ browser พิสูจน์ default, disabled flag, selected module,
  active nav, shared QueryClient และ six-page URLs.
- NV-03: browser ตรวจ deep link/reload/Back/Forward; chart URL ผ่าน password login.
  ยังไม่ได้รัน unauthenticated direct-link/login ครบทุก module.
- NV-04: module unmount tests, chart controller cleanup และ price cleanup tests;
  browser พิสูจน์ว่า chart requests หยุดหลังเปลี่ยนหน้า.
- NV-05: auth/logout/cache/identity-switch/401 tests ผ่าน. Existing TOTP/API-key/
  trading-account/auth/realtime E2E files ปรับให้เปิดหน้าที่เกี่ยวข้องแล้วและผ่าน lint/types,
  แต่ยังไม่ได้รัน stories แยกเหล่านี้ในรอบ navigation นี้; ไม่อ้างว่าเส้นทาง security
  mutation ทุกทางได้รับการตรวจ real browser ล่าสุดแล้ว.
- NV-06: keyboard/mobile menu close และ history navigation ผ่าน browser;
  owner manual ตรวจหน้าทั้งหกยังค้าง.
- NV-07: ไม่มี backend/order/mode API changes; chart flag guard และ chart E2E
  no-order/no-Binance assertions ยังผ่าน. ไม่ถือผลนี้แทน trading safety gates อื่น.

Navigation implementation เปิดตรวจบน localhost แล้ว แต่ acceptance ยัง **Partial**.
F-12 ยังคง In Progress; ปัญหาข้อมูลประวัติว่าง/preview STALE จาก checkpoint ก่อนหน้า
ไม่ได้แก้ในงาน navigation. V-17 ยัง Pending Full Validation; final review/required CI
และงานค้างใน [checkpoint](checkpoint.md) ต้องติดตามต่อก่อนรับรอง merge/Completed.
