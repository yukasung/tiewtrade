# F08/F18 — Account dashboard visual refresh — Plan Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Requirements](account-dashboard-visual-requirements-amendment.md)

## Reference patterns

- `references/admin-template/src/components/UserProfile/UserMetaCard.tsx`
- `references/admin-template/src/components/finance/FinanceStats.tsx`
- `references/admin-template/src/components/common/ComponentCard.tsx`

## Implementation

1. เพิ่ม wrapper `trading-account-dashboard` และ responsive 12-column grid:
   account summaryเต็มแถว, Paper wallet 7 columns, risk form 5 columnsที่ `xl`.
2. ปรับ account summary เป็น template card พร้อม compact status/action row; ข้อความเหตุผล
   disabled ใช้ muted helper text ไม่แย่ง hierarchy.
3. ปรับ Paper wallet summary เป็น stat tiles: balance เด่น, capital/episode/timestampsรอง;
   วาง actions ชิดท้ายและซ่อนปุ่ม refreshปกติไว้เป็น secondary actionที่ไม่เด่น.
4. ให้ RiskLimitPanel ยืดเต็ม grid columnและจัด form responsiveโดยใช้ shared Input/Buttonเดิม.
5. ใช้ CSS กลางและ class ของ admin template; ไม่สร้าง component abstractionใหม่ถ้าไม่จำเป็น.
6. ไม่เปลี่ยน data fetching, mutations, disabled conditions หรือข้อความ safety.

## Verification

- TradingAccountPanel, PaperWalletPanel และ RiskLimitPanel component tests.
- Desktop/mobile, dark/light, overflow, keyboard focus และ disabled explanation.
- Frontend ESLint, TypeScript typecheck และ production build.

ประมาณเวลา **30–45 นาที** ไม่รวม finding ใหม่หรือ browser environment blocker.

## Implementation checkpoint — 2026-10-31

- ปรับ account summary ให้เต็มความกว้าง และจัด Paper wallet/Risk limit เป็น grid 7/5
  บน desktop โดยเรียงต่อกันบนจอเล็กตามแผน
- ปรับ Paper wallet เป็น stat tiles โดยเน้น balance และลดน้ำหนักของ actions รอง
- ให้ข้อความของ Paper wallet ยึดภาษาจาก `<html lang>` เพื่อไม่ให้หน้าไทยปนอังกฤษตามภาษา browser
- ไม่เปลี่ยน data fetching, mutation, API, schema หรือกฎการเงิน
- Targeted component/session tests ผ่าน **55 tests / 4 files**
- ESLint, TypeScript typecheck, production build และ `git diff --check` ผ่าน
- Frontend container ถูก rebuild/recreate และ `http://localhost:5173/` ตอบสนองแล้ว
- Production build ยังมีคำเตือนเดิมเรื่อง JavaScript chunk ใหญ่กว่า 500 kB ซึ่งไม่ได้เกิดจาก
  behavior change รอบนี้
- การตรวจภาพจริง desktop/mobile และ light/dark ยังต้องยืนยันใน browser หลัง hard refresh
  เพราะ browser access host/Computer Use permission ไม่พร้อมในรอบนี้; ไม่ถือว่า targeted
  automated checks แทน visual acceptance ส่วนนี้
