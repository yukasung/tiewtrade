# ADR-0010: Fencing ของการส่งคำสั่งไป Binance (Execution Dispatch)

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Amends: [ADR-0002](0002-portfolio-single-writer-engine.md), [ADR-0005](0005-live-execution-gateway-and-credentials.md)
- Related: FR-LIVE-07, NFR-05, NFR-21, P-08

## Context
fencing token ป้องกันได้เฉพาะการเขียน database แต่การส่ง request ไป Binance เป็นผลข้างเคียงภายนอก execution worker ที่หยุดไปนาน (เช่น GC, VM ค้าง) อาจเสีย lease แล้วกลับมาส่ง request ได้ และ engine เจ้าของเก่าอาจส่ง command ที่ล้าสมัยมา

## Decision
1. **บันทึก dispatch ก่อนส่ง:** ก่อนส่ง Order / Cancel ใด execution บันทึกแถว dispatch (order, command, fencing token ของ lease บัญชี, `request_timestamp`, สถานะ `DISPATCHING`) ใน transaction ที่ตรวจว่าตัวเองยังถือ lease ด้วย token ปัจจุบัน
2. **ให้ Binance ช่วย fence ด้วยเวลา:** request ที่ลงนามใช้ `timestamp = request_timestamp` ที่บันทึกในข้อ 1 และ `recvWindow` สั้น (ค่าเริ่มต้น 5 วินาที — Verify ข้อจำกัดของ Binance) Binance จะปฏิเสธ request ที่ส่งช้ากว่า recvWindow worker ที่ค้างไปนานจึงส่งสำเร็จไม่ได้
3. **Self-fencing:** ก่อนส่งจริง worker ตรวจเวลาที่เหลือของ lease ด้วยนาฬิกาแบบ monotonic ถ้าเหลือน้อยกว่า `recvWindow + ระยะปลอดภัย` ให้ยกเลิกการส่ง
4. **เจ้าของใหม่รอและตรวจก่อน:** execution ที่ได้ lease ใหม่รอจนเลย `lease เก่าหมดอายุ + recvWindow` แล้ว **reconcile ทุก dispatch ที่ยังเป็น `DISPATCHING`** ด้วยการ query Binance ด้วย Client Order ID ก่อนรับ command ใหม่
5. **ปฏิเสธ command ล้าสมัย:** command จาก engine มี fencing token ของ Workspace และ `valid_until` execution ปฏิเสธ command ที่ token ต่ำกว่าค่าล่าสุดที่เห็นของ Workspace นั้น หรือเลยเวลา `valid_until` (engine ต้องประเมินใหม่)
6. Client Order ID ยังเป็น idempotency key ที่ Binance ใช้กันการส่งซ้ำของ Order ที่ยังเปิดอยู่ (NFR-05)

## Consequences
- worker ที่เสีย lease ส่ง request สำเร็จไม่ได้ ยกเว้นในช่วงที่ยังอยู่ใน recvWindow ซึ่งถูกครอบด้วย self-fencing และการรอของเจ้าของใหม่
- การย้ายเจ้าของบัญชีช้าลงอย่างน้อย recvWindow (ไม่กี่วินาที)
- ต้องตรวจเวลาของ server ให้ตรงกับ Binance อย่างเข้มงวด (NFR-06)
