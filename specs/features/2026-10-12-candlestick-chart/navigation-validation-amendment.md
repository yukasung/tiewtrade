# Account navigation — Validation ส่วนเพิ่ม

สถานะ: **Approved** — เจ้าของสั่ง “implement” หลังตรวจ plan/validation ส่วนเพิ่ม วันที่ 2026-10-12
วันที่: 2026-10-12
อ้างอิง: [requirements](navigation-requirements-amendment.md), [plan](navigation-plan-amendment.md)

เจ้าของอนุมัติแก้ routing เป็น paths ไม่มี `#` ด้วยคำสั่ง “แก้ไขให้ถูกต้อง”
วันที่ 2026-10-12. ต้องตรวจ URL paths, direct request/reload และ modified-click
เพิ่มเติม; ผล hash routing เดิมไม่ใช้แทนการตรวจ paths ใหม่.

ผลตรวจรับรวม: **Partial** — implementation และ selected checks ผ่าน;
coverage/รายการค้างอยู่ใน [หลักฐาน navigation](evidence/navigation-implementation.md).
ไม่ถือผลรวมนี้ว่าทุกกรณีของแต่ละ NV ผ่านแล้ว.

| เกณฑ์ | วิธีตรวจ | ข้อกำหนด |
|---|---|---|
| NV-01 | หลัง login/registration ที่ URL หลักแสดง chart เป็น default และไม่มี module อื่น mount; unknown path ใช้ default; chart flag ปิดแสดง disabled โดยไม่เรียก chart API | NAV-01/05/06 |
| NV-02 | เลือกแต่ละเมนูแล้ว URL/active nav/content ตรงทั้งหกหน้า; ไม่มี inactive module หรือ requests/subscriptions ของ module นั้นเริ่มขึ้น | NAV-01/02/03 |
| NV-03 | Direct link/reload ของแต่ละหน้ารักษาหน้าเมื่อ authenticated; Back/Forward เปลี่ยนหน้าถูกต้อง; unauthenticated ยังแสดง auth flow และกลับหน้าที่เปิดโดยตรงหลัง login | NAV-03/06 |
| NV-04 | เปลี่ยนหน้าแล้ว chart history/live/proof/refresh ถูก cancel, price WebSocket/timers ปิด; delayed response ไม่เขียนหน้าถัดไป. StrictMode และ repeated navigation ไม่สะสม listeners/subscriptions | NAV-04 |
| NV-05 | QueryClient/session คงเดิมระหว่างหน้า; logout/logout everywhere/401/revocation ใช้ flow เดิมและหยุดงานทุกหน้า. เปลี่ยนผู้ใช้ไม่ใช้ข้อมูลผู้ใช้เก่า; login/TOTP challenge และ key/account permissions ไม่เปลี่ยน | NAV-04/05 |
| NV-06 | Desktop/mobile sidebar, Escape/backdrop, focus และ keyboard links ยังใช้ได้; active page มี aria-current; labels ชัดและ chart ไม่อ้างราคาสดอยู่ในหน้าเดียวกัน | NAV-02/03 |
| NV-07 | No new order/mode-change calls จาก navigation; chart flag ไม่เปิดเอง; backend contracts/financial calculation ไม่เปลี่ยน | NAV-05 |

## หลักฐานและการเลือก tests

เลือก tests ตาม diff และ affected lifecycle/auth dependencies:
navigation/module selection tests, AuthPanel/logout, AccountLayout, AccountSession,
chart controller และ realtime cleanup ตามผลกระทบจริง. ตรวจ lint/typecheck ของ candidate.
ปรับ existing E2E stories ที่เคยมี modules อยู่หน้าเดียวโดยคงการตรวจเดิม;
real Chromium ต้องพิสูจน์ navigation/default/deep link/Back/Forward และ cleanup.
ใช้ isolated fixtures เดิมสำหรับ integration; ไม่ส่ง Live orders.

บันทึกคำสั่ง/exit code/environment/artifact และ inputs ที่ตรวจ; reuse ผลเดิมได้เมื่อ valid.
ไม่ถือ targeted navigation checks แทน F-12 validation ที่ค้างอยู่.
V-17 ยังคง Pending Full Validation ตามกำหนด release เดิม;
ด่านก่อน merge, generated contracts, final review และ owner manual คงตามมาตรฐาน.
