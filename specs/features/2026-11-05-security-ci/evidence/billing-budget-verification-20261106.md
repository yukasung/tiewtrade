# V-01 — Owner-provided billing verification

วันที่: 2026-11-06
ผล: **Passed สำหรับขอบเขต Security CI และ configuration ที่ตรวจ**

## หลักฐานและขอบเขต

เจ้าของส่งภาพหน้า Usage และ Budgets and alerts ในการสนทนาเพื่อปิด V-01:

- Usage: Billed amount ของแถววันที่ 1–6 พฤศจิกายนที่มองเห็นเป็นศูนย์;
  ไม่ใช้ Gross amount เป็นยอดเรียกเก็บจริง
- Account-scoped Actions budget แสดง $0.00 / $0.00 spent และ Usage blocked
- Account-scoped Packages budget แสดง $0.00 / $0.00 spent และ Usage blocked
- Included usage alerts แสดง On

บันทึกเฉพาะค่าที่เกี่ยวกับเกณฑ์ ไม่เก็บ screenshot หรือข้อมูล billing ของผลิตภัณฑ์อื่น
ไม่อ้างว่าได้เปิดหน้าแก้ไข/ตรวจ checkbox ด้วย agent; หลักฐานคือ effective blocked
status ที่เจ้าของแสดงให้เห็น ไม่มีการแก้ budget/payment method หรือเพิ่มวงเงิน

## เหตุผลที่ปิดเกณฑ์ได้

V-01 กำหนดให้ตรวจเครื่องมือฟรี/pins, artifact/cache budget และ retention;
ไม่ได้กำหนดว่าต้องเพิ่มวงเงินหรือเปิด paid storage เพื่อให้ workflow ทำงาน
ใช้หลักฐานร่วมกันดังนี้:

1. Public repository + standard ubuntu-latest runners; immutable action SHAs และ
   CLI/bundle checksum verification ผ่าน ไม่มี larger runner/paid add-on ใหม่
2. Storage snapshot ตรวจ repo artifacts/cache แล้ว; safe manifests เพียง 5 ส่วนต่อ run,
   จำกัด 64 KiB ต่อ manifest, retention 1 วัน และไม่เพิ่ม security cache/DB/raw SARIF upload
3. Real candidate/repair workflow uploads และ aggregate ผ่านบน SHA ที่บันทึกไว้;
   owner Usage แสดง billed amount ศูนย์ และ Actions/Packages มี effective blocked
   budget ที่ศูนย์ จึงไม่มีการอนุญาตเพิ่มค่าใช้จ่ายเพื่อขยาย capacity ในงานนี้
4. หาก quota หรือการ upload ไม่พอในอนาคต workflow ต้อง fail closed ตาม RQ-7;
   ไม่มีการเพิ่มงบ/ซื้อ storage อัตโนมัติ ใช้ทางเลือกใน plan §7 เมื่อเกิด blocker จริง

ตัวเลข shared storage ที่เหลือทั้งบัญชียังไม่ปรากฏในภาพ จึงไม่อ้างตัวเลขนั้นหรือ
รับประกัน bill ย้อนหลัง/การใช้บริการอื่น/ค่าใช้จ่ายอนาคตทั้งหมด การตรวจนี้ยืนยัน
configuration และ cost controls ของ Security CI ขณะตรวจ ไม่ใช่ใบรับรอง billing ทั้งบัญชี
Budget ไม่ได้ลบค่าใช้จ่ายที่เกิดก่อนสร้าง budget; คงข้อจำกัดนี้ตามเอกสาร GitHub

## Candidate applicability และขั้นถัดไป

Feature head 34c146ab4987478ae545714dc8026a7c670d5b86 / base
98ff2f840fe08dc46ab5eb9976f17bdf32b062b1 ยังคงเดิม; อ่าน PR checks กลับพบ SUCCESS
ครบ Security 7 jobs และ ordinary CI 6 jobs ทั้ง push/PR ไม่มี runtime/configuration
change จากการรับข้อมูลภาพ จึงใช้หลักฐานเดิมต่อโดยไม่รัน tests ซ้ำ

V-01 ปิดได้ และ V-18 ปิดสำหรับ candidate ที่ตรวจแล้ว; ยังต้องตรวจด่านปัจจุบันอีกครั้ง
เมื่อเจ้าของสั่ง merge V-19 ยัง Not Run — Pending Full Validation จน post-merge checks,
settings readback และ main workflow_dispatch ผ่าน ห้ามถือว่า Feature validation ทำให้ Completed

อ้างอิง:
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Budget enforcement](https://docs.github.com/en/billing/how-tos/set-up-budgets)
- [Gross versus billable usage](https://docs.github.com/en/billing/how-tos/products/estimate-spending)
