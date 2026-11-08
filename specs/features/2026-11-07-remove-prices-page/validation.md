# ลบหน้า “ราคาสด” — Validation

สถานะ: **Approved — เจ้าของอนุมัติทั้งสองฉบับและให้เริ่มแก้ source/tests วันที่ 2026-11-07**
วันที่: 2026-11-07
Requirements: [Approved](requirements.md) · Plan: [Approved](plan.md)

## “เสร็จ” หมายถึง

| รหัส | เกณฑ์ | วิธีตรวจ | ระยะ | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | ไม่มีเมนูราคาสดทั้ง desktop/mobile และ TH/EN; หน้าที่เหลือใช้ layout/template เดิม | AccountNavigation/AccountLayout tests + browser ที่ 375 และ 1440 px ตรวจเปิด/ปิดเมนู active link, keyboard focus และไม่มีลิงก์ `/prices` | Feature | Passed — AccountNavigation/AccountLayout และ removed-prices E2E; ตรวจภาพ TH/EN ที่ 375/1440 px, keyboard focus และเมนูที่ไม่มี /prices |
| V-02 | `/prices` หลัง authentication กลับ `/chart`; reload/history/popstate ไม่ mount panel เก่า; chart flag ปิดยังแสดง disabled; unauthenticated ยังต้อง login | AccountNavigation/AuthPanel tests และ browser deep link ผ่าน login/reload/back/forward; คง query-string behavior เดิม | Feature | Passed — unit tests สำหรับ bookmark/query/popstate/auth/disabled flag; browser login→fallback/reload และ navigation back/forward |
| V-03 | ข้อความกราฟ TH/EN ไม่ชี้ไปหน้าราคาสด; การเลือกคู่/timeframe และสถานะกราฟยังทำงาน | CandlestickChartPanel tests และ targeted candlestick-chart E2E รวม login/series switching และ disconnect/recovery | Feature | Passed — 2026-11-08 candidate รวม base 1237bf6 + prices diff; default-loop chart E2E 4 flows ผ่าน 22.6s รวม recovery/series switching; chart unit 25 เดิมยัง valid; ดู evidence/combined-checkpoint-20261108.md |
| V-04 | ไม่เกิด price GET/WS อัตโนมัติจากหน้าที่เหลือ; navigation ไม่แทนที่ session และ logout/expiry ยัง cleanup | ค้น references; AccountNavigation/AccountSession/AuthPanelLogout tests; browser บันทึก request/socket ระหว่าง flow UI ก่อนเรียก API/WS แบบ explicit ใน service test | Feature | Passed — navigation/session/logout tests; removed-prices browser flow ตรวจทั้ง request และ WebSocket แล้วไม่พบ price subscription อัตโนมัติ |
| V-05 | backend price service ยังส่ง exact price, timestamps/catalog, READY/STALE, alert_due และ recovery; protocol/session security คงอยู่ | ปรับ realtime-prices E2E ให้ตรวจ real fake-producer → PostgreSQL/Redis → GET/native browser WS; frame เกิน limit ปิด 1008, logout-all ปิด 4401; รัน `backend/tests/api/test_realtime_prices.py` กับ disposable PostgreSQL/Redis | Feature | Passed — post-refactor price-service E2E 19.3s บน candidate รวม; backend API 9 tests เดิมยัง valid; ไม่เปลี่ยน backend/threshold |
| V-06 | ไม่มี import/dead references ของ UI ที่ลบ และ build สำเร็จ | frontend ESLint, TypeScript, Vite build และค้น references; ไม่ลบ API generated types หรือ backend endpoints | Feature | Passed — full frontend ESLint, final changed-test ESLint, TypeScript และ Vite build; มี bundle-size warning เดิม |
| V-07 | amendments ตรงขอบเขตที่อนุมัติ; source diff ไม่เปลี่ยน backend, money/risk/order, session storage หรือ infrastructure | ตรวจ diff/links/`git diff --check`; แยก historical evidence และ UI retired criteria ออกจาก backend criteria ที่ยังบังคับ | Feature | Passed — scoped amendments/links/reference check และ git diff --check; backend, OpenAPI/generated types, lockfiles และ configuration ไม่มี source diff |
| V-08 | code review และ findings ปิดตามคำสั่งเจ้าของ พร้อมตรวจผลกระทบหลังแก้ | รอ `review code` หลัง Ready for Code Review; refactor ต้องมีคำตอบเจ้าของก่อน; บันทึกผลและ candidate SHA | Feature | Passed — review findings ปิดแล้ว; เจ้าของอนุญาต refactor งานนี้; test-only cleanup ผ่าน price-service E2E, ESLint, TypeScript และ diff checks; ดู evidence/refactor-checkpoint-20261108.md |
| V-09 | required CI ผ่าน candidate SHA ล่าสุดก่อน merge | ติดตามทุก required check พร้อม SHA/URL หลังเจ้าของสั่ง commit/push/เปิด PR; merge ต้องรอคำสั่งและติดตาม post-merge CI | Feature | Pending - owner authorized commit/push/PR on 2026-11-08; CI results will be reported with candidate SHA/run URL; merge requires a separate command |

## การเลือกตรวจตามผลกระทบ

ใช้ tests เดิมก่อนเพิ่ม assertion สำหรับพฤติกรรมใหม่ที่ยังไม่ครอบคลุม
การยกเลิก panel tests เป็นผลจากการยกเลิกผลิตภัณฑ์เฉพาะหน้านี้ ไม่ยกเลิก
API/WS/session security หรือ backend readiness tests

คำสั่งชุดเริ่มต้นหลัง implementation (จาก `frontend/`):

```sh
npm test -- tests/AccountNavigation.test.tsx tests/AccountLayout.test.tsx tests/AccountSession.test.tsx tests/AuthPanel.test.tsx tests/AuthPanelLogout.test.tsx tests/CandlestickChartPanel.test.tsx
npm run lint
npm run typecheck
npm run build
npx playwright test e2e/realtime-prices.spec.ts
npx playwright test --config=playwright.chart.config.ts --grep 'module pages|password login|live snapshots recover|removed prices'
```

จาก `backend/` ภายใต้ disposable test environment ที่ fixtures กำหนด:

```sh
uv run pytest tests/api/test_realtime_prices.py
```

ใช้ config/environment guards เดิม; ตรวจพอร์ตและ test DB ก่อนเริ่ม
หากไม่มี environment ให้บันทึก Not Run/เหตุผล ห้ามใช้ mocks แทนข้อพิสูจน์ DB/WS จริง
การตรวจ UI ใช้ artifacts ในโฟลเดอร์ evidence ของงานนี้ ไม่เขียนทับภาพประวัติ F-10/F-12

ก่อน cross-feature E2E ให้แจ้งขอบเขตและเวลาประมาณใหม่จาก environment จริง
คาดเบื้องต้นประมาณ 5–15 นาทีไม่รวม setup; ไม่ใช่ timeout หรือเกณฑ์ลดความถูกต้อง
รัน sequential เพราะ workers ใช้ DB/producer ร่วมกัน; หลังแก้รันซ้ำเฉพาะส่วนที่กระทบ
หาก targeted evidence ระบุขอบเขตผลกระทบไม่ได้ ให้ขยาย regression พร้อมบอกเหตุผล
ไม่รัน full regression/workload เป็นพิธีสำหรับงานลบหน้านี้

## การตีความเกณฑ์เดิม

- F-10: retired เฉพาะ DOM/client ของ panel ใน V-2/3/6/8/19/21..26 และกรณี
  rendering/delivery warning ที่ผูกกับ panel; ส่วน backend ordering, schema, alert,
  authentication, limits และ recovery ในเกณฑ์เดียวกันยังบังคับ
- F-10 V-26 ใช้ API/WS end-to-end จาก browser ตาม V-05 แทนการแสดง panel
- F-12: flow ที่เคยเปิดราคาสดเปลี่ยนเป็นตรวจบริการราคาผ่าน API;
  navigation เปลี่ยนใช้หน้าที่ยังอยู่ คง chart freshness/recovery และ auth coverage
- ไม่เขียนผลเก่าทับเป็น Passed ของ candidate ใหม่; amendments ในเอกสารเดิมต้อง
  ลิงก์เกณฑ์ทดแทนและระยะ Feature/Batch/Release ตาม testing §6–7

## Batch / Release และสถานะปัจจุบัน

ไม่มีเกณฑ์ Batch/Release ใหม่เฉพาะงานนี้ งานรวมและ dependency ของ feature เดิม
คงสถานะ/กำหนดเดิมใน roadmap; ไม่อ้างว่าการผ่าน CI ปิดงานเหล่านั้น
Implementation ครบและแจ้ง Ready for Code Review แล้ว; รายละเอียดผลจริงและ failures อยู่ใน
[evidence/implementation-checkpoint.md](evidence/implementation-checkpoint.md).
V-01..V-08 local gates ผ่าน; V-09 required CI ยัง Not Run จึงยังไม่พร้อม merge หรือ Completed.
ขั้นถัดไป: รอคำสั่ง commit/push/เปิด PR แล้วติดตาม required CI บน candidate สุดท้ายตาม checkpoint เดิม.

**Local execution note:** พอร์ต 5173/8000 มี dev servers ของเจ้าของใช้อยู่
จึงใช้ config ชั่วคราวนอก repo บน 18175/18013 สำหรับ price E2E โดยคง
API/WS composition, protocol class และ guards เดิม; ไม่แก้ committed configuration.
Chart E2E ใช้ config เดิม 18174/18012; ทั้งสองชุดใช้ PostgreSQL/Redis disposable แยกจาก dev.

[Combined candidate checkpoint 2026-11-08](evidence/combined-checkpoint-20261108.md).

[Post-review refactor checkpoint](evidence/refactor-checkpoint-20261108.md).

Publication checkpoint: owner authorized commit/push/PR on 2026-11-08; V-09 Pending. Historical Not Run notes above refer to earlier checkpoints.
