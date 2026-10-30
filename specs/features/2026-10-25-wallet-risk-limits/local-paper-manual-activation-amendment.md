# Local Paper manual-acceptance activation

สถานะ: Approved 2026-10-30

เจ้าของอนุมัติข้อความ “อนุมัติ local Paper manual-acceptance activation โดย production
ยังคงปิด” เพื่อให้ตรวจ browser → API → Paper engine บน `localhost` ได้ก่อน V-21 เสร็จ

## ขอบเขต

- ใช้ได้เฉพาะฐานข้อมูล Docker Compose สำหรับพัฒนาบนเครื่องเจ้าของ และเฉพาะ Paper
- ห้ามประกอบ Live executor, ใช้ venue credentials หรือส่ง Live order
- เปิด protocol ตามลำดับ `publication` → `financial` → `admission`; ก่อนเปิดขั้นถัดไปต้อง
  เห็น publication watermark เดินและ Paper evaluation ที่ตั้ง limit แล้วเป็น `READY`
- ใช้สิทธิ์ operator/deployment ชั่วคราวเท่านั้น ห้ามเพิ่ม migrator credential ให้ API หรือ worker
- เมื่อจบ manual acceptance ต้องปิดย้อนลำดับ `admission` → `financial` → `publication`
- หาก worker, publisher หรือ source ไม่พร้อม ให้คง/คืน admission เป็นปิด ห้ามใช้ allow-all

## สิ่งที่ amendment นี้ไม่อนุมัติ

- ไม่เปลี่ยนกฎเงิน, freshness, risk SLA, W1-W4 หรือเกณฑ์ V-21
- ไม่ใช่หลักฐาน production activation, Completed, merge หรือ release
- ไม่อนุญาต environment switch ที่เปิด production ข้าม validation

บันทึกค่า flags, watermark, evaluation และผล manual order ใน checkpoint M5 โดยแยกจาก
acceptance evidence เดิมอย่างชัดเจน
