# Review: F-03 Database Foundation — Requirements

วันที่: 2026-09-27  
ไฟล์ที่ตรวจ: [requirements.md](../features/2026-09-27-database-foundation/requirements.md) (Proposed)  
ผล: ยังไม่ควรอนุมัติเพื่อเขียน plan; มี 3 ประเด็นที่กระทบหลักประกันข้อมูลและ 1 จุดที่ต้องระบุรูปแบบตารางให้ชัด

เทียบกับ `specs/standards/`, F-02 และเอกสาร PostgreSQL 16 โดยเลขบรรทัดอ้างจาก requirements ฉบับที่ตรวจ ไม่ได้แก้ requirements หรือเขียนโค้ด

## ข้อค้นพบ

### R-1 [P1] ข้อเสนอให้ `engine` ข้าม RLS ทำให้คำว่า “บังคับระบุผู้ใช้” ไม่เป็นกลไกฐานข้อมูล

ตำแหน่ง: [requirements.md](../features/2026-09-27-database-foundation/requirements.md) บรรทัด 148–160 (Q-3)

ทางเลือก ก บอกว่า `engine` ไม่อยู่ใต้ RLS แต่ “ต้องตั้งผู้ใช้ปัจจุบันเองก่อนแตะข้อมูล” และยังมีตาข่ายจากการระบุผู้ใช้ทุกครั้ง ถ้า role ของ `engine` มี `BYPASSRLS` หรือเป็นเจ้าของตาราง การตั้ง session variable ไม่บังคับให้ query กรองแถวใดเลย: query ที่ลืม `WHERE owner_id = ...` ยังคงเห็นหรือแก้ข้อมูลทุกคนได้ จึงไม่ควรบรรยายว่าเป็นการบังคับที่ระดับฐานข้อมูล ข้อนี้สำคัญเป็นพิเศษเพราะ `engine` อ่าน secret และแก้สถานะการเทรดได้ตาม `database.md` หัวข้อ 5

ข้อเสนอ: ก่อนเลือก Q-3 ให้แยกงานข้ามผู้ใช้ (เช่น ค้นหารายการที่ต้องประมวลผล) ออกจากงานของผู้ใช้รายเดียว แล้วกำหนดว่าจะใช้ role/policy ใดในแต่ละทาง; หากตั้งใจให้ `engine` ข้าม RLS จริง ให้ระบุชัดว่าเป็นการพึ่งการกรองในแอปและเพิ่มเทสต์พิสูจน์กรณีลืมกรอง อย่าเรียกการตั้ง session variable ว่าตาข่ายฐานข้อมูล และอย่าให้ `engine` ใช้ role เจ้าของตารางหรือ superuser

อ้างอิง: [PostgreSQL 16 — Row Security Policies](https://www.postgresql.org/docs/16/ddl-rowsecurity.html) ระบุว่า `BYPASSRLS`/superuser ข้าม policy เสมอ และเจ้าของตารางข้ามได้ตามปกติ

### R-2 [P1] `NUMERIC(38,18)` เพียงอย่างเดียวไม่ผ่านเทสต์ “เกิน 18 หลักต้องถูกปฏิเสธ”

ตำแหน่ง: [requirements.md](../features/2026-09-27-database-foundation/requirements.md) บรรทัด 82–83, 192–202 (RQ-8, RQ-9, Q-7)

Q-7 เสนอ domain บน `NUMERIC(38,18)` พร้อมเทสต์ว่าค่าที่ละเอียดเกิน 18 หลักถูกปฏิเสธ แต่ PostgreSQL ปัดค่าที่ scale เกินตอนแปลงเป็น `NUMERIC(p,s)` อยู่แล้ว เช่น `0.0000000000000000001` อาจกลายเป็นศูนย์ก่อนถึงการตรวจ domain; domain ที่มี base type นี้อย่างเดียวจึงไม่ใช่หลักประกันการปฏิเสธค่าดิบ ขัดกับ F-02 RQ-9 ที่ห้ามฝากการปัดให้ฐานข้อมูล

ข้อเสนอ: กำหนดจุดตรวจ *ก่อน* coercion ให้ชัด เช่นตรวจค่า F-02 ใน persistence adapter ก่อน bind และทดสอบทั้งเส้นทาง adapter กับการเขียนตรงที่อาจเลี่ยง adapter ได้ หรือออกแบบ domain บน `NUMERIC` ที่ยังไม่บังคับ scale แล้วใช้ข้อจำกัดตรวจค่าจริงก่อนเก็บ โดยรักษาช่วงค่าเทียบเท่า `NUMERIC(38,18)` ข้อเลือกวิธีเป็นงาน plan ได้ แต่ requirements ต้องไม่อ้างว่า domain บน `NUMERIC(38,18)` ตรวจค่าดิบที่ถูกปัดไปแล้วได้

อ้างอิง: [PostgreSQL 16 — Numeric Types](https://www.postgresql.org/docs/16/datatype-numeric.html) อธิบายว่าค่าที่มี scale เกินจะถูกปัดเป็น scale ของคอลัมน์

### R-3 [P1] กฎ append-only ยังไม่ครอบคลุม `TRUNCATE`

ตำแหน่ง: [requirements.md](../features/2026-09-27-database-foundation/requirements.md) บรรทัด 46, 81, 173–179 (RQ-7, Q-5)

ข้อเสนอตัด `UPDATE`/`DELETE` ด้วยสิทธิ์และ trigger แต่ `TRUNCATE` เป็นสิทธิ์และเหตุการณ์ trigger แยกต่างหาก จึงยังล้างตารางทั้งก้อนได้ถ้าภายหลังมีการให้ `TRUNCATE` โดยพลาด ทั้งที่ Q-5 บอกว่า trigger ป้องกันได้แม้มีการให้ `GRANT` ผิดในอนาคต สำหรับ audit log และรายการเดินบัญชี ช่องนี้ขัดกับคำว่า “เพิ่มได้อย่างเดียว”

ข้อเสนอ: ระบุว่าทุก runtime role ไม่มี `TRUNCATE` และกลไก append-only ต้องมี `BEFORE TRUNCATE` trigger ระดับ statement หรือมาตรการที่พิสูจน์ความเทียบเท่า พร้อมเทสต์การพยายาม `TRUNCATE` แยกจาก `UPDATE`/`DELETE` และจำกัด DDL/การปิด trigger ให้ `migrator` เท่านั้น

อ้างอิง: [PostgreSQL 16 — GRANT](https://www.postgresql.org/docs/16/sql-grant.html), [Trigger Behavior](https://www.postgresql.org/docs/16/trigger-definition.html)

### R-4 [P2] ตาราง `users` ตารางเดียวทำให้ “คอลัมน์เจ้าของ” ยังตีความได้หลายแบบ

ตำแหน่ง: [requirements.md](../features/2026-09-27-database-foundation/requirements.md) บรรทัด 44–47, 77–78, 119–134 (RQ-3, RQ-4, Q-1)

Q-1 เลือก `users` ที่มีเพียงรหัสประจำตัวและเวลาสร้าง แต่ RQ-3 กำหนดให้ทุกตารางข้อมูลผู้ใช้มีคอลัมน์เจ้าของ `NOT NULL` และ Q-1 เองบอกว่าเจ้าของแถวต้องชี้ไปที่ผู้ใช้ ถ้า `users` อยู่ใต้กฎนี้ ต้องระบุว่าจะใช้ `users.id` เป็นตัวเจ้าของแถวนั้นเอง หรือเพิ่ม `owner_id` ที่ชี้กลับไปยัง `users` เพราะสองแบบมี migration และ RLS policy ต่างกัน หากยกเว้น `users` จาก RQ-3 ก็ต้องบอกข้อยกเว้นและ policy ที่ยังกันผู้ใช้คนอื่นได้

ข้อเสนอ: ระบุรูปแบบที่เลือกไว้ใน Q-1 พร้อมเทสต์ว่า `api` เห็นได้เฉพาะแถวของตัวเอง, เมื่อไม่มี identity เห็นศูนย์แถว, และไม่สามารถสร้างหรือแก้แถวให้ผู้ใช้อื่นผ่าน `WITH CHECK` ได้

## สิ่งที่ทำได้ดี

- แยกบทบาท `migrator` ออกจาก runtime roles และตั้งใจทดสอบสิทธิ์ด้วย PostgreSQL จริง
- เลื่อนตารางของ feature อื่นออกจาก F-03 และไม่เดา schema ที่ยังติด Needs Clarification
- เชื่อมข้อกำหนดเงินของ F-02, RLS, migration และขอบเขต service กลับไปยัง standards ได้ชัด

รีวิวนี้ตรวจเอกสารเท่านั้น ยังไม่ได้รันฐานข้อมูลหรือเทสต์การติดตั้ง
