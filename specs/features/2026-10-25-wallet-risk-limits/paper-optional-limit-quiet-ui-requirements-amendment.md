# F-18 R36 — Paper optional-limit quiet UI — Requirements Amendment

สถานะ: **Approved — เจ้าของอนุมัติ R36 quiet UI requirements วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Paper optional limit requirements](paper-optional-limit-requirements-amendment.md)

## เหตุผล

หน้าจัดการบัญชีแสดงข้อความ “ไม่บังคับ คุณตั้งเพดานภายหลังได้” ใต้ช่องเพดาน
แม้การปล่อยช่องว่างและการไม่บล็อก Paper order จะสื่อพฤติกรรมนี้อยู่แล้ว ทำให้การ์ด
มีข้อความมากเกินจำเป็นและลดความชัดของ action หลัก.

## ข้อกำหนดที่แก้

| ID | ข้อกำหนด |
|---|---|
| PQUI-RQ-01 | เมื่อ Paper ยังไม่ตั้งเพดาน หน้าปกติไม่แสดงข้อความ `ไม่บังคับ คุณตั้งเพดานภายหลังได้` / `Optional. You can set a loss limit later.` และไม่แสดง badge หรือ alert แทนข้อความดังกล่าว. |
| PQUI-RQ-02 | การ์ดสถานะปกติแสดงเฉพาะหัวข้อ, label `เพดานขาดทุน (USDT)`, input และปุ่ม `บันทึก`; ช่องว่างหมายถึงยังไม่ตั้งค่าและต้องไม่เป็นเหตุ disable Paper MANUAL order. |
| PQUI-RQ-03 | Desktop จัด input และปุ่มในแถวเดียวกัน โดย input ใช้พื้นที่คงเหลือ ปุ่มสูงเท่า input และมีความกว้างคงที่พออ่านข้อความ; mobile เรียงลงและปุ่มเต็มความกว้าง. |
| PQUI-RQ-04 | ใช้ `ComponentCard`, `Label`, `Input`, `Button` กลางที่ดัดแปลงจาก `references/admin-template/`; ไม่สร้างสี spacing border radius หรือ native control style ใหม่ในหน้า. |
| PQUI-RQ-05 | ข้อความ validation ที่ผู้ใช้ต้องแก้, stale/conflict, load failure, latch/stop และ Live-required message ยังคงแสดงเมื่อเกี่ยวข้อง; ซ่อนเฉพาะ Paper unset helper ในสถานะปกติ. |
| PQUI-RQ-06 | Label, focus, keyboard submit, disabled state, screen-reader recovery status และ error association เดิมต้องคงอยู่. |

## ขอบเขตที่ไม่เปลี่ยน

- ไม่เปลี่ยน optional Paper business rule, request/recovery/idempotency หรือการบันทึกค่า.
- ไม่เปลี่ยน Live/BOT, TOTP, Money, schema, API, latch/reset หรือ financial boundary.
- POL-RQ-07 ถูกแทนเฉพาะข้อบังคับให้แสดงข้อความว่าเป็นทางเลือก; Paper ยังต้องไม่แสดง
  ข้อความที่ทำให้เข้าใจว่า unset บล็อกออเดอร์.

## Needs Clarification

ไม่มี.
