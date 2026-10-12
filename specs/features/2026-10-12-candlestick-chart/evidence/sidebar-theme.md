# Admin-template sidebar toggle and colors

วันที่: 2026-10-13 (Asia/Bangkok)
ที่มา: เจ้าของสั่งเพิ่ม toggle sidebar และใช้สีเหมือน admin-template.

## การเปลี่ยนแปลง

- AccountHeader ใช้ toggle icon จาก reference AppHeader; มีปุ่มทั้ง desktop/mobile.
  Desktop toggle ย่อ/ขยาย sidebar 290/90px; rail แสดง icons พร้อม accessible labels
  และขยายชื่อเมนูเมื่อ hover/focus. Mobile ใช้ overlay เดิม; Escape/backdrop/menu
  selection ปิดเมนูและคืน focus. เปลี่ยนขนาดเป็น desktop แล้วปิด mobile backdrop.
- ใช้ local presentation state ใน AccountLayout โดยไม่เพิ่ม provider/dependency
  หรือ remount module/session เมื่อ toggle.
- `admin-colors.css` คัดลอกครบ 91 `--color-*` definitions จาก reference index.css;
  ตรวจด้วย script แล้วทุกชื่อและค่าตรง source. Shared tokens ใช้ palette นี้สำหรับ
  text/background/borders/brand/focus/alerts และ chart grid/candles.
  Active menu ใช้ brand-50/500; hover ใช้ gray-100/700; error alert ใช้ error palette.
- SVG icons คัดลอกจาก reference เฉพาะที่ใช้ และใช้ CSS mask เพื่อรับสี currentColor.
  ไม่มี reference demo data หรือโค้ด trading เพิ่ม.

## Verification

| Check | Command / artifact | Result |
|---|---|---|
| Targeted tests | Node 22 Vitest: layout, navigation, renderer, auth layout, chart panel, price panel; [sidebar-theme-tests.xml](sidebar-theme-tests.xml) | 54 passed / 6 files |
| Types / lint | Node 22 `tsc --noEmit`; ESLint affected layouts/renderer/tests/E2E | Exit 0 |
| Actual browser | `run_browser.py NODE22 --grep 'actual chart panes|module pages' --reporter=list,junit`; [sidebar-theme-e2e.xml](sidebar-theme-e2e.xml) | 2 passed; assert actual sidebar widths 90/290px, exact active-menu colors, mobile close, resize/keyboard/layout/exact chart values |
| Palette comparison | Compare all `--color-*` definitions against reference index.css | 91 exact matches |
| Build / local preview | Compose frontend image build, `exec -T frontend npm run build`, chart override `up --no-deps --no-build -d frontend` | Exit 0 ทั้งหมด; recreate เฉพาะ frontend |
| Final deployed image | Frontend manifest | `sha256:c309553d7c750f86d71a2e9e6dcf5cef9cad8e2a7e763bfae8c809e9eb40bba2` |

ภาพจาก browser: [sidebar/theme chart](sidebar-theme-chart.png).
ไม่รัน full suites หรือ V-17 ซ้ำ. Trading/auth/session logic ไม่เปลี่ยน;
F-12 validation ที่ค้าง, owner manual และ required CI ยังติดตามตาม checkpoint เดิม.
การตรวจสีครอบคลุม theme ปัจจุบันและ assertions ที่ระบุ ไม่ใช่ pixel-perfect
comparison กับทุก demo page หรือการเพิ่ม dark-mode flow ใหม่.
