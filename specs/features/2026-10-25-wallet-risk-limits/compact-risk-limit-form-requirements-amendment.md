# F18-UI — ฟอร์มเพดานขาดทุนแบบสั้น — Requirements Amendment

สถานะ: **Approved — เจ้าของตอบ “approve requirements amendment” วันที่ 2026-10-30; plan/validation amendment อนุมัติแล้ว**
วันที่: 2026-10-30

## ทำไมต้องเปลี่ยน

หน้าเพดานความเสี่ยงปัจจุบันแสดงค่าการคำนวณ ปุ่มปรับหลายขั้น รายละเอียดทางเทคนิค
และการดำเนินการเพิ่มเติมพร้อมกัน ทำให้ผู้ใช้สับสน. เจ้าของต้องการให้การตั้งค่าหลัก
เหลือเพียงสถานะสั้น ช่อง `เพดานขาดทุน (USDT)` และปุ่ม `บันทึก` โดยไม่เปลี่ยน
กฎความเสี่ยง การเงิน TOTP หรือ durable recovery ของ F-18.

## ขอบเขต

### ทำ

- ปรับ `RiskLimitPanel` ที่ใช้ร่วมกันระหว่าง Paper/Live เป็นฟอร์มสั้นตาม admin template.
- ให้ระบบเลือก `SET`, `DECREASE` หรือ `INCREASE` จากค่าปัจจุบันกับค่าที่ผู้ใช้กรอก.
- ขอ TOTP หลังผู้ใช้กดบันทึกเฉพาะกรณี `INCREASE`.
- แสดง reset เฉพาะเมื่อชนเพดาน และแสดงสถานะ/recovery เมื่อจำเป็นต่อการตัดสินใจ.
- ซ่อนข้อมูลคำนวณและ technical identifiers จากสถานะปกติ แต่คงข้อมูลใน backend/audit.

### ไม่ทำ

- ไม่เปลี่ยน API, schema, Money, สูตร loss, latch/reset, polling, stop processing,
  idempotency หรือ authorization policy.
- ไม่ยกเลิกเพดานความเสี่ยง ไม่สร้างค่า default และไม่เปิด Paper/Live gate เพิ่ม.
- ไม่ตัด alert ที่บอกว่าข้อมูลไม่พร้อม ชนเพดาน งานหยุดมีปัญหา หรือผลคำขอยังไม่แน่นอน.
- ไม่แสดงหรือเก็บ TOTP ใน payload, journal, log หรือข้อความ error.

## ข้อกำหนด

| รหัส | ข้อกำหนด |
|---|---|
| UI-RQ-01 | สถานะปกติต้องแสดงเพียง status สั้น, input `เพดานขาดทุน (USDT)` และปุ่ม `บันทึก`; input เติมค่าปัจจุบันจาก authoritative snapshot หรือว่างเมื่อยังไม่ตั้ง |
| UI-RQ-02 | ปุ่มบันทึกต้อง disabled เมื่อค่าว่าง รูปแบบไม่ถูกต้อง ไม่มากกว่า 0 ไม่เปลี่ยนจากค่าปัจจุบัน กำลังมีคำขอ durable ค้าง หรือ Paper wallet/episode scope ยังไม่พร้อม; client validation ไม่แทน server validation |
| UI-RQ-03 | เมื่อยังไม่มีค่าให้ส่ง `SET`, ค่าต่ำลงส่ง `DECREASE`, ค่าสูงขึ้นส่ง `INCREASE`; เปรียบเทียบด้วย representation ที่ไม่ใช้ floating point และส่ง amount string ตาม API เดิม |
| UI-RQ-04 | `INCREASE` ต้องเปิด modal ขอ TOTP หลังการกดบันทึก; `SET` และ `DECREASE` ไม่ขอ TOTP เพิ่มตาม contract เดิม. รหัสอยู่ใน transient ref/header เท่านั้นและถูกล้างเมื่อปิดหรือส่ง |
| UI-RQ-05 | ห้ามเปลี่ยนค่าที่แสดงแบบ optimistic. Input เปลี่ยนตาม server เมื่อผล `APPLIED` และ snapshot revision ใหม่ยืนยันแล้ว; `REJECTED` ต้องคงค่าที่ผู้ใช้ตรวจแก้ได้พร้อมเหตุผลที่ปลอดภัย |
| UI-RQ-06 | Background refresh ห้ามเขียนทับ draft ที่ผู้ใช้แก้แล้ว. หาก revision, wallet หรือ episode เปลี่ยนระหว่างแก้ ต้องเตือนและบังคับรับ snapshot ล่าสุดก่อนสร้าง key/คำขอใหม่ |
| UI-RQ-07 | สถานะปกติไม่แสดง loss/baseline/allowance/realized PnL, revision, UUID, source revision, timestamps เชิงเทคนิค, ปุ่มเพิ่ม/ลดแยก หรือ disclosure รายละเอียดการคำนวณ; ข้อมูลยังคงอยู่ใน API/backend/audit และไม่ถูกลบ |
| UI-RQ-08 | Loading/error/unavailable/pause/latched/stop problem และ durable UNKNOWN ต้องแสดงข้อความสั้นที่บอกสิ่งที่ผู้ใช้ทำได้. Pending แสดงว่ากำลังดำเนินการและปิดการส่งใหม่; UNKNOWN ให้ตรวจสถานะด้วย identity/key เดิมโดยไม่สร้างคำขอใหม่ |
| UI-RQ-09 | `รีเซ็ตการนับขาดทุน` แสดงเฉพาะใน alert เมื่อ latch ชนเพดาน พร้อมคำเตือนผลต่อ baseline เดิม. การเพิ่มเพดานไม่ล้าง latch และ reset ไม่ใช้ TOTP ตาม contract เดิม |
| UI-RQ-10 | รายละเอียด stop/recovery เชิงเทคนิคซ่อนในสถานะปกติ แต่เมื่อมี stop failure หรือผลไม่แน่นอนต้องมีทางตรวจรายละเอียดที่จำเป็น โดยไม่อ้างว่าหน้าว่างคือ terminal success |
| UI-RQ-11 | Enter ในฟอร์มทำงานเหมือนปุ่มบันทึก; modal คืน focus, รองรับ keyboard, ไทย/อังกฤษ, light/dark และ mobile ตาม frontend standard/admin template |
| UI-RQ-12 | Component เดียวกันต้องรักษา scope Paper/Live แยกกัน; UI change นี้ไม่อนุญาต Live execution และห้ามนำ Paper snapshot/recovery ไปแสดงใน Live |

## การแทนข้อกำหนดเดิม

เมื่อ amendment นี้ได้รับอนุมัติ ให้ UI-RQ-01..12 แทนเฉพาะส่วน **การแสดงข้อมูลพร้อมกันบน
หน้าปกติ** ของ F-18 RQ-15. ข้อกำหนดเดิมที่ต้องแสดงเหตุ block, unavailable, latch,
reset warning และเวลาที่จำเป็นต่อ error/recovery ยังคงมีผลตามรูปแบบ contextual.
ข้อกำหนด RQ-01..14, RQ-16..18, NC-F18-01..08 และ financial/trading-safety gates
ไม่เปลี่ยน.

## Acceptance ระดับ requirements

- ผู้ใช้ตั้ง ลด หรือเพิ่มเพดานจาก input เดียวได้โดยไม่ต้องเลือก action เอง.
- หน้าปกติไม่มีปุ่มและรายละเอียดเกินจำเป็น แต่ผู้ใช้ไม่สูญเสียคำเตือนหรือ recovery action.
- การเพิ่มเพดานยังยืนยัน TOTP และทุก mutation ยังใช้ durable idempotency protocol เดิม.
- การชนเพดานยังค้างจน reset และ reset เข้าถึงได้จากบริบทที่จำเป็น.

## ยังไม่ชัด

ไม่มีข้อที่บล็อก requirements. รายละเอียด state machine ของ draft, modal/recovery layout
และชุด tests จะระบุใน plan/validation amendment หลัง requirements ได้รับอนุมัติ.
