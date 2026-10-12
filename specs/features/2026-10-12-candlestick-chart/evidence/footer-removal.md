# Footer removal

วันที่: 2026-10-13 (Asia/Bangkok)
เจ้าของสั่ง “ลบ footer”; บันทึกข้อยกเว้นการแสดง health/status ใน F-08 UI-template
requirements amendment ก่อนแก้โค้ด.

ลบ system footer และ health request ที่ใช้สำหรับ footer จาก App; ลบ CSS/token
ที่ไม่ได้ใช้ และปรับ auth layout เป็น 100vh. Backend health API/helper contract เดิม
คงอยู่. เปลี่ยน App tests และ health E2E ให้ตรงกับข้อกำหนดใหม่ โดยคงการตรวจ
health endpoint จริงผ่าน API แทนการคาดว่าจะมี status/footer บนหน้าเว็บ.

- Node 22 targeted App/AuthLayout: [3 passed](footer-removal-tests.xml).
- Affected ESLint และ `tsc --noEmit`: exit 0.
- Compose frontend image build และ restart เฉพาะ frontend: exit 0;
  manifest `sha256:43a498df0338b9ffb89d9ce35bb01a6762a35ecf3c8e2068adbd75d76abb48fe`.
- Chromium localhost smoke: login UI แสดง, footer count 0, ไม่มี automatic
  `/api/health` request; explicit API health check HTTP 200.
- Health E2E file ปรับแล้วและผ่าน static checks; ไม่รัน E2E/full suites เพิ่ม
  สำหรับการลบ footer. Authenticated no-footer behavior ตรวจใน App unit test.

ไม่เปลี่ยน session/trading logic; owner manual และ F-12 validation ที่ค้างยังคงเดิม.
