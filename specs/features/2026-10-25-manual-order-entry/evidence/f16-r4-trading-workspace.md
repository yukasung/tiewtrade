# F16-R4 — Compact Trading Workspace checkpoint

วันที่: 2026-10-30 (Asia/Bangkok)
สถานะ: **Implementation complete; Ready for Code Review**

## Candidate และขอบเขต

- เปลี่ยนเฉพาะ frontend layout/components/tests และ F16 requirements/plan/validation amendment
- ไม่มี public API, schema, backend, Money/Quantity, order/risk calculation หรือ Live execution change
- Paper/Live ใช้ shared workspace; chart รับ pair จาก parent; form คง payload, journal,
  idempotency, recovery และ episode scope เดิม
- ไม่มี Order book, market trades, 24h statistics, TP/SL หรือ unsupported controls

## ผลตรวจ

| การตรวจ | ผล | เวลาคำสั่งที่วัด |
|---|---|---:|
| Targeted components: form/page/orders/chart/layout/risk | 58/58 Passed | 3.72s |
| TypeScript | Passed | รวมกับ targeted/full commands |
| ESLint | Passed | รวม lint+build 11.5s |
| Production build | Passed; มี Vite chunk-size warning เดิม | รวม lint+build 11.5s |
| Frontend full unit suite | 33 files, 299/299 Passed | รวม typecheck+tests 26.4s |
| Visual-only Paper/Live; 1440×1000 และ 375×844; light/dark | Passed; no horizontal overflow; Live submit disabled | browser scripts 10.2s (ไม่รวม attempt ที่หยุด) |
| Isolated manual-order Playwright acceptance | Pending | guard หยุดใน 0.87s ก่อนเริ่ม server: `E2E_DATABASE_REJECTED` |

Playwright acceptance ไม่ได้ถูกฝืนรันด้วยค่า DB ที่เดา และไม่มี workload/order เกิดจากรอบที่ guard
ปฏิเสธ. Visual pass ใช้ source ปัจจุบันบน Vite ชั่วคราวและ local API ที่กำลังรัน โดยสมัคร
บัญชีทดสอบและไม่กรอกหรือส่ง Paper/Live order.

## ภาพหน้าจอ

- [Paper light desktop](ui/workspace-paper-light-desktop.png)
- [Paper dark desktop](ui/workspace-paper-dark-desktop.png)
- [Paper light mobile](ui/workspace-paper-light-mobile.png)
- [Paper dark mobile](ui/workspace-paper-dark-mobile.png)
- [Live light desktop](ui/workspace-live-light-desktop.png)
- [Live dark desktop](ui/workspace-live-dark-desktop.png)
- [Live light mobile](ui/workspace-live-light-mobile.png)
- [Live dark mobile](ui/workspace-live-dark-mobile.png)

## รายการค้างจริง

- Code review ตามขั้นตอนโครงการยังไม่เริ่ม
- Isolated manual-order browser acceptance ซึ่งตรวจ mutation/recovery จริงยังต้องรันเมื่อมี
  approved E2E database environment; local visual และ unit tests ไม่แทนหลักฐานนี้
- Required CI/manual acceptance บน final commit ยังคง Pending; ไม่มี commit/push/merge ในรอบนี้

## Code review remediation — 2026-10-30

แก้ findings ในขอบเขต F16-R4 ครบแล้ว:

- market snapshot ผูก `base` และถูกล้างทันทีเมื่อเปลี่ยน pair จึงไม่แสดงราคาคู่เดิม
- compact risk-stop/latch progress แสดงใกล้ฟอร์มโดยไม่ต้องเปิดรายละเอียด
- terminal manual request ถูกย้ายออกจาก pending recovery ไป recent result; recovery section ซ่อนเมื่อไม่มีงานค้าง
- shared Tabs รองรับ roving tab focus, ArrowLeft/ArrowRight/Home/End และ `aria-controls`
- manual-order E2E refresh ไม่ล้าง SELL/LIMIT ก่อน POST และตรวจ `aria-selected` ก่อนส่ง

ผลตรวจ candidate หลังแก้: TypeScript Passed, ESLint Passed, frontend tests **33 files / 302 tests Passed**,
production build Passed (คง Vite chunk-size warning). Isolated manual-order Playwright ยัง Pending ด้วย
environment guard เดิม; ไม่มีการใช้ unit/local visual แทนหลักฐาน mutation acceptance.

## Refactor checkpoint — 2026-10-30

- ย้าย pair/market snapshot state ที่ซ้ำใน Paper/Live ไป `useTradingPair` โดยคงการล้างราคา
  เมื่อเปลี่ยนคู่และการตรวจ snapshot base เดิม
- เปลี่ยน shared Tabs จากการใช้ translated label เป็น state identity ไปใช้ typed stable IDs;
  label ยังแปลและ accessibility/keyboard behavior เดิม
- ลบ message key ที่ไม่ได้ใช้ และไม่เพิ่ม abstraction ให้ส่วนที่ยังมีเพียง implementation เดียว

ผลหลัง refactor: targeted **61/61**, frontend full suite **302/302**, TypeScript, ESLint และ
production build ผ่าน. ไม่มี API/payload/query key/order/risk behavior เปลี่ยน; Vite chunk-size warning
และ isolated Playwright pending คงเดิม.

## Local runtime correction — 2026-10-30

- สาเหตุข้อความ `กราฟยังไม่เปิดใช้งาน` คือ local stack ถูกเปิดด้วย `compose.yaml` เพียงไฟล์เดียว
  จึงไม่มี opt-in flags ของ F-12; เปิด stack ใหม่ด้วย `compose.chart.dev.yaml` ที่มีอยู่แล้ว ทำให้ API,
  market-data และ frontend มี chart flags ครบ โดยไม่เปลี่ยน production default
- ย้ายรายการออเดอร์ให้อยู่ต่อจาก chart/form ก่อนส่วนรายละเอียดความเสี่ยง และลดความสูงขั้นต่ำของ
  chart บน desktop เป็น responsive clamp เพื่อให้แท็บออเดอร์ที่เปิดอยู่/ประวัติออเดอร์เห็นได้โดย
  ไม่ต้องเลื่อนผ่านรายละเอียดก่อน
- Targeted chart + Paper page tests **41/41 Passed**, TypeScript Passed; API และ market-data
  healthy, chart route ตอบ authentication boundary แทน `CHART_DISABLED`
- การแก้นี้ไม่เปลี่ยน order payload, query, pagination, financial/risk logic หรือ Live execution
