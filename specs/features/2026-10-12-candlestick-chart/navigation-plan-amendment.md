# Account navigation — Plan ส่วนเพิ่ม

สถานะ: **Approved** — เจ้าของสั่ง “implement” หลังตรวจ plan/validation ส่วนเพิ่ม วันที่ 2026-10-12
วันที่: 2026-10-12
อ้างอิง: [ข้อกำหนดที่อนุมัติ](navigation-requirements-amendment.md), [validation](navigation-validation-amendment.md)

## แนวทาง

ใช้ path navigation ภายในแอปเดิม ไม่เพิ่ม routing framework/dependency.
แต่ละ URL เป็นหน้าแยกที่ mount เฉพาะ module ที่เลือก. ใช้ History API
และ `popstate` สำหรับ Back/Forward; internal links intercept เฉพาะ plain click
โดยรักษา Ctrl/Cmd/Shift click และเปิด tab ใหม่ตาม browser ปกติ.
เจ้าของอนุมัติแก้จาก hash เป็น path ด้วยคำสั่ง “แก้ไขให้ถูกต้อง” วันที่ 2026-10-12.

| URL หลังเข้าสู่ระบบ | Module |
|---|---|
| `/chart` | CandlestickChartPanel — default |
| `/account` | รายละเอียดบัญชีและ logout/logout everywhere |
| `/security` | TotpPanel |
| `/api-keys` | ApiKeyPanel |
| `/trading-account` | TradingAccountPanel |
| `/prices` | RealtimePricePanel |

URL หลัก/unknown page ใช้ `replaceState` เป็น `/chart` ไม่เพิ่ม Back entry
และไม่แก้ URL ของหน้าที่รู้จักเมื่อ login. ไม่เปลี่ยน path ขณะยังอยู่ใน auth flow
จนยืนยันตัวตนแล้ว. Session หมด/ถูกเพิกถอนยังใช้ auth flow เดิม.
ถ้า chart flag ปิด หน้า default แสดงข้อความว่าไม่ได้เปิดใช้งาน โดยไม่ mount
chart หรือเรียก chart API; เมนู chart ยังซ่อนตาม flag เดิม.

Vite ใช้ `appType: "spa"` เพื่อ fallback เป็น index.html สำหรับหน้าแอป
บน dev/preview server เดิม โดยรักษา `/api` proxy และ static assets.
ตรวจ HTTP 200 และ browser reload ของ module paths จริง; ไม่เปลี่ยน backend routes.

## ใช้ของเดิมและขอบเขตแก้

- `frontend/src/AccountSession.tsx`: คง QueryClient/session boundary ครอบทุกหน้า
  โดยไม่ remount เมื่อเปลี่ยนหน้า; cleanup เมื่อ identity เปลี่ยน/ออกจากระบบเหมือนเดิม.
- `frontend/src/AuthPanel.tsx`: แยก rendering ของ signed-in modules ตามหน้าปัจจุบัน;
  ไม่เปลี่ยน login/TOTP challenge/logout API handlers. คง signed-in marker
  สำหรับสถานะ authentication ให้ใช้ได้ทุกหน้า.
- `frontend/src/layout/{AccountLayout,AccountSidebar}.tsx`: ส่งหน้าปัจจุบันให้ sidebar,
  ใช้ URL ของหกหน้า, `aria-current="page"`, mobile close และ Escape behavior เดิม.
- เพิ่ม module navigation ขนาดเล็กใน `frontend/src/` เพื่อกำหนดรายการหน้า,
  resolve path/default และ subscribe/unsubscribe `popstate` ที่เดียว.
- ใช้ TotpPanel, ApiKeyPanel, TradingAccountPanel, RealtimePricePanel และ
  CandlestickChartPanel เดิม; unmount inactive modules ให้ cleanup เดิมทำงาน.
  ตรวจ cleanup ของงานค้างและ late response ใน dependencies ที่เกี่ยวข้องก่อนแก้.
- `frontend/src/accountMessages.ts` และ `chartMessages.ts`: เพิ่ม labels ตามระบบ
  i18next เดิม; เปลี่ยนข้อความ chart ที่บอกว่าราคาสดอยู่ด้านบนให้ชี้เมนูราคาสด.
- ปรับ tests/E2E เดิมที่สมมติว่า modules อยู่หน้าเดียวให้ navigate ไป module ก่อน;
  ไม่ลด assertions ของ auth/security/chart หรือเอา mocks แทน real integration.

## ผลต่อแผนเดิม

เมื่ออนุมัติ แผนนี้แทนเฉพาะ mount/anchor ใน F-12 plan §2 และรายการ mount/anchor §8.
Requirements/chart API/budgets/financial precision และ backend contracts คงเดิม.
ไม่เปลี่ยน backend, trading execution หรือ migration และไม่เพิ่ม modules ใหม่.

## Verification และส่งงาน

### Presentation ตามคำสั่งเจ้าของ 2026-10-13

คำสั่งเพิ่มเติมของเจ้าของ: toggle sidebar จาก template และใช้ชุดสีเดียวกับ template.
ใช้ desktop expanded/collapsed (290/90px) และ mobile overlay ตาม AppHeader/
SidebarContext ของ reference; คง session และ module lifecycle เมื่อ toggle.
คัดลอก color palette ของ `references/admin-template/src/index.css` เป็นไฟล์ theme
กลางและใช้ร่วมกับ controls/cards/alerts/chart. Icon assets คัดลอกเฉพาะที่ใช้จริง.

เจ้าของสั่ง “ปรับหน้า ui ให้ใช้ code admin-template”. ใช้แนวทางที่อนุมัติไว้
ใน F-08 UI-template amendment ร่วมกับ F-12 RQ-20: นำ source ของ
`references/admin-template/src/layout/AppLayout.tsx` และ
`components/common/{ComponentCard,PageBreadCrumb}.tsx` มาปรับใช้ใน frontend
โดยคง React18/Vite6, session, paths และ module logic เดิม.
ใช้ Select/Button เดิมที่ปรับจาก template; ไม่ import reference project เข้า runtime.
ตรวจ auth/TOTP/key/account/nav/chart/price UI ตามผลกระทบ พร้อม lint/types/build
และภาพ desktop/mobile โดยไม่รัน backend full suite สำหรับ presentation changes.

รวมการแก้ navigation และ tests ที่เกี่ยวข้องก่อนรัน targeted frontend tests,
lint/typecheck ตาม diff; ใช้ผล backend เดิมถ้า inputs ไม่ได้รับผลกระทบ.
ตรวจ real browser navigation/default/session/cleanup ตาม validation ส่วนเพิ่ม.
ปรับและรัน E2E ที่ได้รับผลกระทบจากการแยกหน้าเมื่อ candidate นิ่งครั้งเดียว;
ไม่รัน backend full suite หรือ V-17 เพียงเพราะเปลี่ยน navigation.
หลังตรวจ build/restart เฉพาะ frontend เพื่อให้ owner ตรวจ localhost.
