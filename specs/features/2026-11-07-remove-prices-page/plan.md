# ลบหน้า “ราคาสด” — Plan

สถานะ: **Approved — เจ้าของอนุมัติทั้งสองฉบับและให้เริ่มแก้ source/tests วันที่ 2026-11-07**
วันที่: 2026-11-07
Requirements: [Approved](requirements.md)
Branch ที่จะใช้: `feature/remove-prices-page`

## แนวทาง

ถอด `prices` จากรายการ route กลางและการ mount panel ใน AuthPanel
sidebar desktop/mobile ใช้รายการเดียวกันจึงไม่ต้องเพิ่มระบบ navigation ใหม่
URL `/prices` ใช้ fallback `/chart` เดิมหลัง authentication รวม replaceState และ
การรักษา query string เดิม; เมื่อ chart flag ปิด ยังคงแสดง CHART_DISABLED ตามเดิม
ไม่เปิดกราฟเองหรือเปลี่ยนสิทธิ์ผู้ใช้

ก่อนเริ่ม source ให้ตรวจ branch/base และ diff ปัจจุบัน ใช้ branch แยกจาก F-17/cleanup
โดยรักษางานค้างของเจ้าของทั้งหมด หากต้องแยก checkout ให้ใช้ worktree
และย้ายเฉพาะเอกสารงานนี้ ห้าม reset/stash/ทับงานอื่นเพื่อจัด workspace
commit/push/merge ต้องรอคำสั่งเจ้าของตามเดิม

## ของเดิมที่จะใช้ซ้ำ

| ตำแหน่ง | การใช้ซ้ำ |
|---|---|
| `frontend/src/accountNavigation.ts` | accountPages, unknown-route fallback, history/popstate และ modified-click behavior |
| `frontend/src/layout/{AccountLayout,AccountSidebar,PageBreadcrumb}.tsx` | layout/menu/title เดิม ไม่เปลี่ยน style หรือ interaction |
| `references/admin-template/src/layout/{AppSidebar,AppLayout}.tsx`, `src/context/SidebarContext.tsx`, `src/components/common/PageBreadCrumb.tsx` ภายใต้ template | ต้นแบบ sidebar, responsive และ breadcrumb; ไม่มีข้อยกเว้นด้าน appearance ใหม่ |
| `frontend/src/AccountSession.tsx` | QueryClient ต่อ identity, cancellation/expiry flow เดิม |
| `frontend/tests/{AccountNavigation,AccountLayout,AccountSession,AuthPanel,AuthPanelLogout,CandlestickChartPanel}.test.tsx` | regression ของ routing, auth, session และกราฟ |
| `frontend/e2e/{realtime-prices,candlestick-chart}.spec.ts`, `helpers/` | ปรับ flow เดิม ใช้ test accounts และ environment guard เดิม |
| `backend/tests/e2e_realtime_runner.py`, `backend/tests/api/test_realtime_prices.py` | producer จำลองและการตรวจ price API/WS กับ session จริง |

## สิ่งที่จะแก้

| ไฟล์ | เปลี่ยนอะไร |
|---|---|
| `frontend/src/accountNavigation.ts` | ถอด `prices` จาก accountPages |
| `frontend/src/AuthPanel.tsx` | ถอด import และ mount ของ RealtimePricePanel |
| `frontend/src/accountMessages.ts` | ลบชื่อเมนู prices ทั้งไทย/อังกฤษ |
| `frontend/src/chartMessages.ts` | disclaimer เหลือ `กราฟ Spot · Asia/Bangkok` / `Spot chart · Asia/Bangkok` |
| `frontend/src/{RealtimePricePanel.tsx,RealtimePricePanel.css,useRealtimePrices.ts,realtimePrices.ts,realtimePriceMessages.ts}` | ลบเมื่อยืนยัน references ก่อนลงมือว่าใช้เฉพาะหน้าที่ถอด; ผลค้นปัจจุบันพบเฉพาะ panel/hook/client และ tests ของมัน |
| `frontend/src/styles/admin-theme.css` | ลบเฉพาะ rule `.icon-prices`; ไม่ขยายไปล้าง asset/template ที่ไม่เกี่ยวข้อง |
| `frontend/tests/AccountNavigation.test.tsx` | ถอด mock/expectation ของ module prices; เปลี่ยน flow เป็นหน้าที่ยังอยู่ และเพิ่มกรณี URL เก่า/fallback/ไม่มีลิงก์ |
| `frontend/tests/{AccountLayout,AuthPanel,CandlestickChartPanel}.test.tsx` | ปรับหรือเพิ่ม assertion เฉพาะช่องว่างด้านเมนู, authentication และข้อความ TH/EN; คง tests เดิมที่ยังใช้ได้ |
| `frontend/tests/{RealtimePricePanel.test.tsx,realtimePrices.test.ts}` | ถอด tests ของ UI/client ที่ถูกยกเลิก; backend contract/security tests ยังคงอยู่ |
| `frontend/e2e/realtime-prices.spec.ts` | เปลี่ยนจาก DOM panel เป็น authenticated GET และ native browser WebSocket โดยใช้ fake producer เดิม; คง READY/STALE/outage alert/recovery, catalog, exact price/timestamps, oversized frame 1008 และ revoke 4401; cleanup socket/producer ทุกครั้ง เลิกเขียนภาพทับหลักฐาน F-10 เดิม |
| `frontend/e2e/candlestick-chart.spec.ts` | แทน prices ใน history/back/forward/reload flow ด้วยหน้าที่ยังอยู่; ตรวจ URL เก่าและเมนู desktop/mobile; flow latest-price worker ตรวจ authenticated API แทน panel พร้อมคง login/series switching |
| `specs/features/2026-10-07-realtime-prices/{plan,validation}.md`, `specs/features/2026-10-12-candlestick-chart/{plan,validation}.md` | เพิ่ม amendment ที่ลิงก์ requirements นี้ ระบุ UI criteria ที่ retired กับ service criteria ที่คงอยู่; ไม่แก้ผล historical ให้เป็นผล candidate ใหม่ |
| requirements ของ F-10/F-12, `specs/mission.md`, `specs/roadmap.md`, เอกสารงานนี้ | บันทึกการอนุมัติและสถานะ/หลักฐานตามจริง |

การแก้ E2E ไม่สร้าง client ราคาสดใหม่ใน runtime; test-only WebSocket ตรวจสัญญา
บริการที่ยังอยู่โดยตรง ไม่ย้าย warning UI ไปหน้าอื่น ไม่ลบ backend/API schema
หรือ shared helpers เช่น market catalog, AccountSession และ auth transport

## ผลต่อฐานข้อมูลและความปลอดภัย

ไม่มี migration หรือการเปลี่ยน backend, dependencies, configuration และ infrastructure
session ยังคง PostgreSQL; ไม่เพิ่ม process-local persistent state, Redis หรือ sticky session
ไม่เปลี่ยน Money/Quantity, transaction, locking, idempotency, trading readiness หรือ Live
การถอด frontend subscriber ไม่เปลี่ยน shared ingestion/price consumers
ตรวจข้อ Stateless Application & Session Management ในการตรวจ diff และ review

## ความเสี่ยงและการตรวจ

- ลิงก์หรือ history ค้าง: ตรวจ `/prices` หลัง login/reload/popstate, เมนูทั้งสองขนาด
  และ fallback เมื่อเปิด/ปิด chart flag โดยไม่เปลี่ยน flag เอง
- การลบ tests ทำให้หลักฐาน session/WS หาย: เก็บ service tests เดิมและปรับ E2E
  ให้ตรวจ protocol/security โดยตรง; ห้ามถอดทั้ง suite เพื่อให้ผ่าน
- กราฟหรือ session ถูก remount ผิด: ใช้ navigation/session/auth และ chart regressions เดิม
- schema หรือ consumer พึ่ง client ที่จะลบ: ค้น references อีกครั้งก่อนลบ;
  หากพบ runtime consumer นอกขอบเขตให้เก็บ dependency นั้นและหยุดทบทวนตาม AGENTS.md
- E2E มี process/DB ร่วม: ใช้ disposable test DB/Redis, environment guards และ configs
  เดิม; ห้ามใช้ production DB หรือหยุด dev server ของเจ้าของเพื่อแย่งพอร์ต

## Checkpoints การตรวจ

1. หลังอนุมัติ plan/validation: ทำ source/tests/docs ให้ครบ แล้วรัน targeted checks
   V-01..V-07 ตาม validation; ใช้หลักฐานเดิมต่อในส่วนที่ไม่กระทบ
2. แจ้ง **Ready for Code Review** พร้อม diff, ผลตรวจ, งานค้างและความเสี่ยง
   แล้วหยุดรอ `review code`; ไม่เริ่ม review อัตโนมัติ
3. หลัง review/fixes ให้ถามเรื่อง `refactor the code` ตาม AGENTS.md;
   หากอนุมัติ refactor ให้ทำและตรวจผลกระทบต่อทันทีตาม validation
4. ก่อน merge: V-01..V-09 ระดับ Feature ต้องผ่านบน candidate สุดท้าย
   รวม required CI เมื่อเจ้าของสั่งเปิด PR; การอนุมัติแผนไม่ใช่คำสั่ง Git

งานนี้ไม่เพิ่ม Batch/Release workload; งานค้างของ feature เดิมคงตาม roadmap
ไม่ยกระดับสถานะ feature เดิมจากผลการลบหน้า
