# F-08 — ขยาย TailAdmin ให้ครบทุกหน้าปัจจุบัน

สถานะ: **Approved** — เจ้าของตอบ “approve” หลังตรวจข้อกำหนดส่วนเพิ่ม วันที่ 2026-10-07
วันที่: 2026-10-07
ที่มา: เจ้าของสั่ง “ปรับหน้า ui ให้ใช้ admin template ทุกหน้า”

## เหตุผลและขอบเขต

ปัจจุบัน AccountLayout, API key และบัญชีเทรดใช้รูปแบบ TailAdmin แล้ว
แต่ auth, TOTP, รายละเอียดบัญชี และข้อมูลสถานะระบบยังมีรูปแบบ native เดิม
ส่วนเพิ่มนี้ขยาย RQ-9 ของ requirements.md ให้ครอบคลุมทุกหน้าที่มีอยู่จริง
เป็นส่วนหนึ่งของ F-08 บน branch เดิม ไม่สร้างหน้าฟีเจอร์ที่ยังไม่ได้ implement
ข้อกำหนด Approved เดิมมีผลร่วมกับส่วนเพิ่มนี้

## แนวทางที่เสนอ

แนะนำปรับ markup/layout ของหน้าปัจจุบันจาก source TailAdmin ใน
`references/admin-template/` โดยใช้ theme และ controls ที่ปรับใช้แล้วใน frontend
ร่วมกัน วิธีนี้รักษา React18/Vite6 และ authentication/cache flow เดิม

อีกทางคือย้ายทั้งแอปไป router/dependencies ของ template ซึ่งเพิ่มขอบเขตและ
ความเสี่ยงต่อ session; หรือปรับเฉพาะ CSS ซึ่งทำให้ layout ยังต่างจาก template
จึงไม่เลือกสองแนวทางนี้

## ข้อกำหนดส่วนเพิ่ม

| รหัส | ข้อกำหนด |
|---|---|
| UI-RQ-1 | หน้าล็อกอิน สมัครสมาชิก และยืนยันสองขั้นใช้ auth layout จาก TailAdmin: desktop แบ่งพื้นที่ฟอร์มกับแบรนด์ TiewTrade; mobile ฟอร์มเต็มพื้นที่โดยไม่มี sidebar |
| UI-RQ-2 | หน้าหลังเข้าสู่ระบบใช้ AccountLayout เดิม; รายละเอียดบัญชี, TOTP, API key และบัญชีเทรดใช้ typography, spacing, controls และ feedback ของชุดเดียวกัน |
| UI-RQ-3 | ทุกขั้นของ TOTP ได้แก่เริ่มเปิด/QR/ยืนยัน/รหัสสำรอง/ปิดและข้อผิดพลาด ต้องมีรูปแบบเดียวกัน โดยคงการแสดง secret และรหัสสำรองเฉพาะจังหวะที่ flow เดิมอนุญาต |
| UI-RQ-4 | ชื่อแอปและสถานะระบบจัดอยู่ใน layout ที่เข้ากับ template ไม่เหลือหัวข้อ/รายการข้อมูล native นอกกรอบ; คงการอ่าน health และข้อมูลจริงเดิม |
| UI-RQ-5 | ใช้ component และ design tokens เดิมร่วมกันก่อนสร้างใหม่; theme ครอบ auth และ account โดยไม่เพิ่ม CSS reset ที่ทำให้ controls หรือ semantics เปลี่ยน |
| UI-RQ-6 | คง session/CSRF/TOTP/validation, credential clearing, logout, account cache isolation, polling, fresh-data confirmation และ MANUAL/BOT logic เดิมทั้งหมด |
| UI-RQ-7 | รองรับ desktop และ mobile 360px ไม่มี horizontal overflow; ใช้ keyboard ได้, focus ชัด, labels/alerts/status และ main landmark เดียวถูกต้อง |
| UI-RQ-8 | ข้อความ UI ที่แก้หรือเพิ่มผ่านระบบแปลเดิม รองรับไทย/อังกฤษ; ไม่แสดงข้อมูลบัญชี demo, balance, orders, bot controls หรือ social login/reset-password ที่ backend ยังไม่รองรับ |
| UI-RQ-9 | คง React18/Vite6 และ dependencies ที่ใช้อยู่; ไม่ยก template ทั้งโครงการหรือ demo assets เข้า runtime และไม่เปลี่ยน backend/schema |
| UI-RQ-10 | ก่อนส่งให้ทดลอง ต้องผ่าน tests ของ auth/TOTP/logout/key/account, lint/typecheck/build และตรวจภาพ desktop/mobile รวมสถานะ error/disabled; เปิดชุดทดลองเดิมพร้อม URL ให้เจ้าของตรวจ |

## แหล่งที่ใช้ซ้ำ

- `references/admin-template/src/pages/AuthPages/{AuthPageLayout,SignIn,SignUp,TwoStepVerification}.tsx`
- `references/admin-template/src/components/{form,ui,common}/`
- `frontend/src/layout/{AccountLayout,AccountHeader,AccountSidebar}.tsx`
- `frontend/src/components/ui/{Button,Input,Label,Select}.tsx`
- `frontend/src/styles/admin-theme.css`, `frontend/src/accountPanels.css`
- `frontend/src/AccountSession.tsx` และ auth/API helpers เดิม

## จุดอนุมัติและข้อจำกัด

ข้อกำหนดส่วนเพิ่มได้รับอนุมัติแล้ว; plan.md และ validation.md มีส่วนเพิ่ม
สถานะ Approved หลังเจ้าของตอบ approve วันที่ 2026-10-07
พร้อมเริ่ม implementation ตาม AGENTS.md
ไม่มีข้อธุรกิจหรือกฎการเทรดใหม่ที่ต้องตัดสิน ไม่มี commit/push จากคำขอนี้
