# ADR-0011: วงจรชีวิตของ Command / Message แบบทนทาน (Postgres Queue + Redis Wakeup + Inbox)

- Status: **Accepted** (2026-09-22)
- Date: 2026-09-22
- Amends: [ADR-0003](0003-postgres-state-ledger-outbox.md), [ADR-0004](0004-redis-streams-non-authoritative.md)
- Related: NFR-20, NFR-22, NFR-23

## Context
Architecture §7.1 ส่ง command ตรงเข้า Redis ก่อนบันทึกลง Postgres ถ้า Redis หายก่อน engine รับ command นั้นหายไปทั้งก้อน `command_id` อย่างเดียวกู้ payload ไม่ได้ และ outbox ของ ADR-0003 แยกไม่ออกว่า "ส่งแล้ว" กับ "ผู้รับประมวลผลแล้ว"

## Decision
1. **ข้อความที่ต้องประมวลผลแน่นอน** (command จาก api / jobs, command จาก engine ไป execution, event ที่ notifier ต้องส่ง) **บันทึกลง Postgres ก่อนเสมอ**
   - api: INSERT แถวในตาราง `commands` (payload ครบ, สถานะ `PENDING`) แล้วค่อย publish
   - engine / execution: เขียนผ่าน outbox ใน transaction เดียวกับ state
2. **Redis Streams เป็นแค่ transport และตัวปลุก** (wakeup) ไม่ใช่ที่เก็บ
3. **ผู้รับบันทึกการประมวลผล (inbox) ใน transaction เดียวกับผลของมัน:** `commands.status = PROCESSED` หรือแถวใน `inbox (consumer, message_id)` ถ้าเคยประมวลผลแล้วให้ข้าม (idempotent)
4. **แยกสถานะ:** `published_at` ของ outbox หมายถึงส่งเข้า transport แล้วเท่านั้น; การประมวลผลวัดจาก inbox / สถานะ command
5. **Replay:** ผู้รับกวาด Postgres หาข้อความที่ยังไม่ประมวลผลเกินเวลาที่กำหนด ทั้งตอนเริ่มทำงาน (หลังได้ lease) และเป็นระยะ ไม่ต้องพึ่ง Redis
6. **Retention:** เก็บ command / outbox จนกว่าผู้รับที่จำเป็นทั้งหมดประมวลผลแล้ว และพ้นระยะเก็บ (M-04)
7. **ข้อความที่หายได้** (ราคาไปหน้าจอ, event อัปเดตหน้าจอ) ส่งผ่าน Redis Pub/Sub ได้โดยไม่บันทึก หน้าจอ resync ผ่าน REST เมื่อ reconnect

## Consequences
- Redis ล่มหรือข้อมูลหาย ไม่มี command หรือ event ที่ต้องประมวลผลหายไป
- เพิ่มการเขียน Postgres หนึ่งครั้งต่อ command (ยอมรับได้ตามปริมาณ NFR-16)
- ต้องมี sweeper และ index ของข้อความที่ค้าง
