# Paper Spot Bot Panel — Requirements

สถานะ: **Approved — RQ-01–12 และ RQ-13 amendment เจ้าของ approve วันที่ 2026-11-13**
วันที่: 2026-11-13 (Asia/Bangkok)
Branch: `feature/paper-spot-bot-panel`
ฐาน dependency: responsive top navigation commit `4a9b46a` (ยังไม่ถือว่า merged หรือผ่าน required CI)

## ทำไมต้องมี

เจ้าของต้องการให้แผงขวาของ Paper Spot ใช้ง่าย: เลือกบอท → ใส่งบรวม → เริ่มบอท
และยืนยันว่าไม่ต้องมีเทรดมือในแผงนี้ รอบนี้เตรียมเฉพาะ UI โดยยังไม่สร้าง strategy
หรือระบบรันบอท จึงต้องบอกความสามารถที่ยังไม่เปิดใช้งานอย่างชัดเจน

## ขอบเขต

แทนที่ฟอร์มสร้างออเดอร์มือเฉพาะหน้า `/paper/trade` ด้วยแผงบอท ไม่มีแท็บเทรดมือ
คงกราฟ/timeframe/ออเดอร์/ประวัติ/TP/SL/Settings และการจัดการคำขอเก่า
หน้า Live Spot และ API เทรดมือเดิมไม่เปลี่ยน

ไม่รวม strategy engine, กฎ Grid, การเริ่ม/หยุด bot run, กลยุทธ์ส่วนตัว, catalog API,
สิทธิ์ใหม่, schema/migration หรือการเปลี่ยนประเภทบัญชี MANUAL/BOT
คำขอในอนาคตเรื่องทีมพัฒนาเพิ่มกลยุทธ์ส่วนตัวให้ลูกค้าต้องมี spec แยกก่อนทำจริง
งานนี้ไม่แก้ข้อกำหนด mission เรื่องผู้เขียนกลยุทธ์ และไม่ถือว่า F-20/F-21 เสร็จ

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | แผงขวาหัวข้อ “บอท Paper Spot” แสดงตามลำดับ: เลือกบอท, ยอดที่ใช้ได้, งบรวม (USDT), เริ่มบอท | แผนที่เจ้าของสั่ง implement |
| RQ-02 | ตัวเลือกบอทมี `Grid Close System` ตัวเดียวและเลือกไว้เริ่มต้น ไม่แสดงกลยุทธ์สมมติหรืออ้างว่ามีกลยุทธ์ส่วนตัวพร้อมใช้ | คำตัดสินเจ้าของ |
| RQ-03 | ไม่มีแท็บ/ฟอร์มเทรดมือ, BUY/SELL, MARKET/LIMIT หรือปุ่มส่งออเดอร์ใหม่ในแผงนี้ | เจ้าของ: ไม่ต้องมีเทรดมือ |
| RQ-04 | ช่องงบเริ่มว่าง เป็นข้อความพร้อม decimal input mode เก็บเฉพาะร่างในหน้าจอ ไม่คำนวณเงินด้วย float ไม่กำหนดขั้นต่ำ/ขั้นราคา/การแบ่งไม้หรือกฎ Grid ขึ้นเอง | แผนและ frontend standard |
| RQ-05 | ร่างคงอยู่เมื่อ resize หรือเปิด/ปิดเมนู แต่ล้างเมื่อเปลี่ยนผู้ใช้ กระเป๋า/episode หรือคู่เทรด ไม่บันทึกใน server หรือ persistent browser storage | แผน; owner isolation |
| RQ-06 | ยอดที่ใช้ได้มาจากกระเป๋า Paper เดิม แสดงด้วยตัวจัดรูปแบบเดิม; loading/error/ข้อมูลใช้ไม่ได้ต้องระบุสถานะ ไม่แสดงศูนย์แทนหรือข้อมูลเก่าราวกับพร้อมใช้ และไม่แสดงยอดของผู้ใช้/กระเป๋าอื่น | แผน; frontend §3–4 |
| RQ-07 | ปุ่ม “เริ่มบอท” disabled เสมอ พร้อมข้อความ “ระบบบอทยังไม่เปิดใช้งาน” ที่อ่านได้; การกรอก เลือก กด Enter หรือ resize ไม่สร้าง mutation, request identity, bot run หรือเปลี่ยนประเภทบัญชี | UI-only scope |
| RQ-08 | คงกราฟ, เลือกคู่/timeframe, reset, ออเดอร์เปิด, ประวัติ, TP/SL และ Settings/STOP ตาม flow และ safety gates เดิม | แผน |
| RQ-09 | คงการติดตาม/กู้คืนคำขอเดิมที่ยังไม่ทราบผล การ retry ที่เจ้าของกดโดยใช้ key เดิม และการยกเลิกออเดอร์ ข้อความ/controls กู้คืนแยกจากฟอร์มบอท ไม่เพิ่ม retry อัตโนมัติหรือซ่อนปัญหาคำขอเก่า | แผน; idempotency/trading safety |
| RQ-10 | คงข้อความ safety/recovery ที่จำเป็นต่อรายการเดิมโดยไม่ใช้ manual admission เป็นการรับรองว่าบอทพร้อมหรือปิดบังเหตุหยุด; ไม่มีการลด safety gates | trading-safety standard |
| RQ-11 | ใช้ Select/Input/Label/Button/Alert กลางจาก admin template รองรับไทย/อังกฤษ light/dark, label/focus/keyboard และ 375/768/1280/1440px โดยไม่ทำ navigation หรือแผงล้นแนวนอน | แผน; frontend standard |
| RQ-12 | ไม่เปลี่ยน API/schema/session/สิทธิ์/backend/Live Spot/กฎเงิน; state ใหม่เป็น UI draft เท่านั้น ไม่เป็นแหล่งข้อมูลธุรกิจหรือ session และไม่เปิด Live | แผน; Stateless Application & Session Management |

## การเปลี่ยนข้อกำหนดเดิมอย่างจำกัด

เมื่ออนุมัติเอกสารนี้ จะเปลี่ยนเฉพาะการแสดงฟอร์มสร้างออเดอร์มือใน Paper Spot ของ F-16
เป็น UI บอทที่ยังไม่เปิดใช้งาน การรักษาออเดอร์/position/คำขอเก่าตาม F-16/F-17/F-19
และ API เดิมยังเป็นข้อบังคับ ไม่มีการย้ายฟอร์มเทรดมือไปหน้าใหม่; ข้อยกเว้นช่องทางลด/ปิดสถานะเดิมเสนอใน RQ-13 ด้านล่างและยังรออนุมัติ
แผน/validation ต้องระบุ tests ที่ได้รับผลกระทบจากการถอดฟอร์ม โดยไม่ลบหลักฐาน API safety

## กฎความปลอดภัยและการตรวจรับ

อ้าง `specs/standards/trading-safety.md`, `frontend.md`, `security.md` และ `testing.md`
ต้องพิสูจน์ UI ไม่ส่งคำขอเปลี่ยนข้อมูล และ regression ของ recovery/cancel/TP/SL/STOP ที่เกี่ยวข้อง
ใช้ fixtures ไม่ส่งคำสั่งในบัญชีเจ้าของหรือ Live; ตรวจ targeted tests, lint, typecheck, build
และ required CI ตาม workflow ก่อน merge โดยไม่ใช้ผล local แทน CI
หลักฐานการเงิน/workload เดิมใช้ต่อเฉพาะส่วนไม่กระทบ; ไม่เปลี่ยนสถานะ F-17 หรือเกณฑ์ release

## ยังไม่ชัด

**NC-BOT-UI-01 Resolved:** เจ้าของอนุมัติช่องทางลด/ปิดสถานะตาม RQ-13 วันที่ 2026-11-13; ฟอร์มเดิมเป็นช่องทาง SELL จึงคงความสามารถนี้ไว้ใน modal แยก กฎ Grid และกลยุทธ์ส่วนตัวอยู่นอกขอบเขต
และต้องกำหนด/อนุมัติแยกก่อนทำให้ปุ่มเริ่มใช้งานจริง

## จุดหยุดถัดไป

เจ้าของอนุมัติ requirements ฉบับนี้ → จัดทำ plan/validation เพื่ออนุมัติ → จึงแก้ source
เมื่อ implementation/ตรวจรับครบแจ้ง Ready for Code Review แล้วรอคำสั่งรีวิว
commit/push/merge เฉพาะเมื่อเจ้าของสั่ง ไม่เปลี่ยน local preview ในขั้นเอกสารนี้


## Amendment RQ-13 — ช่องทางลด/ปิดสถานะเดิม (Approved 2026-11-13)

Review พบว่าเอา ManualOrderForm ออกจะเอาช่องทาง SELL ออกด้วย ขัดกับ mission §5
และ trading-safety §8 ที่ยังให้ลด/ปิดสถานะผ่าน safety gates เดิมได้

เสนอปุ่ม “ลด/ปิดสถานะ” ในบริเวณกิจกรรม/รายการใต้กราฟ แยกจากแผงบอท
เปิด modal สำหรับคู่เทรดปัจจุบัน ตายตัวเป็น SELL และใช้ MARKET/LIMIT, ช่องจำนวนเหรียญ,
ราคา LIMIT และการระบุ protection allocations ตาม flow เดิม ไม่มี BUY
ผู้ใช้ต้องกรอกจำนวนและกดยืนยันส่งเอง ไม่กรอกขายทั้งหมด ไม่คำนวณยอด/ปัดเศษฝั่ง frontend
ปุ่มส่งระบุ “ส่งคำขอขาย Paper”; ต้องแสดงว่าการส่งไม่เท่ากับจับคู่หรือปิดสำเร็จ
คงการตรวจยอดถือ/ยอดจอง/source/risk/protection revision ฝั่ง server เดิมทั้งหมด
ไม่ถือว่า SELL ทุกคำสั่งลดความเสี่ยง และไม่เพิ่ม reduce-only contract ที่ backend ไม่มี

คง canSubmit(SELL), recovery journal ก่อน POST, scope/key, UNKNOWN retry เดิม
เมื่อข้อมูลไม่พร้อมให้แสดงเหตุผลและห้ามส่ง; เมื่อไม่มีเหรียญไม่มีการสร้างคำขออัตโนมัติ
ปิด modal/เปลี่ยนคู่ไม่ลบคำขอที่ส่งแล้ว; draft ล้างตาม scope เดิมและเมื่อปิด modal
เมื่อเปิด modal ต้องคง focus/คืน focus และไม่ทับ flow Settings/STOP
RQ-03 ยังใช้กับแผงบอท ไม่มีแท็บหรือฟอร์มเทรดมือในแผงขวา
RQ-07/V02 no-mutation ใช้กับแผงบอท ไม่ได้ห้ามคำขอขายที่เจ้าของตั้งใจส่งใน modal นี้

จุดอนุมัติ: RQ-13 เปลี่ยนขอบเขตจาก UI disabled ล้วนเป็นการรักษาช่องทาง SELL ที่มีจริง
จึงต้องอนุมัติ amendment และ plan/validation ฉบับแก้ก่อน source; ไม่เปลี่ยนกฎการเทรด


Approval receipt: เจ้าของอนุมัติ RQ-13 พร้อม plan/validation ฉบับแก้แล้ว 2026-11-13; NC-BOT-UI-01 Resolved ตาม RQ-13 ข้างต้น ข้อความ Proposed/รออนุมัติในประวัติให้ตีความเป็นสถานะก่อน receipt นี้

## Display amendment — Approved by owner 2026-11-13

เจ้าของสั่งไม่แสดง “ข้อมูล ณ” และวันเวลาในแผงบอท Paper Spot. ข้อยกเว้น frontend §4 นี้จำกัดเฉพาะแผงบอทที่ยัง disabled; คง loading/unavailable และการตรวจ snapshot/scope เดิม. ไม่เปลี่ยนเวลาในกราฟ ออเดอร์ หรือหลักฐานฝั่ง server.

## Compact panel amendment — Approved by owner 2026-11-13

หัวข้อใช้ “Paper Spot” ทั้งสองภาษา; จัดกลุ่ม selector, ยอดใช้ได้แบบบรรทัดเดียว, งบและปุ่มเริ่มให้กระชับตามภาพอ้างอิง โดยใช้ controls/template เดิม. ถอดหัวข้อ “คำขอและผลการตรวจ”, การ์ดเพดานขาดทุน/ลิงก์ตั้งค่า และบรรทัดพร้อมใช้ไม่มี TP/SL ออกจากแผงขวา. คง risk/recovery error และ controls เมื่อมีเหตุ, การตรวจ risk/source, TP/SL, SELL modal และ Settings เดิม. ไม่เพิ่ม leverage/Futures/คำสั่งจากภาพตัวอย่าง.

## Admission-warning placement — Approved by owner 2026-11-13

เจ้าของสั่งย้ายคำเตือนความพร้อมส่งออเดอร์และเหตุจาก admission ไปในหน้าต่างลด/ปิดสถานะ ไม่แสดงซ้ำข้างแผง Paper Spot. คงข้อผิดพลาดของคำขอเก่า ปุ่มกู้คืน risk-stop และการตรวจ server/SELL gates เดิม.

## Stable balance refresh — Approved by owner 2026-11-13

ระหว่าง background refresh ให้แสดงยอดจาก successful snapshot ของ owner/wallet/episode/base ปัจจุบันต่อ พร้อมสถานะอัปเดตในพื้นที่คงที่. Initial loading ไม่มีตัวเลข; error/placeholder/source unavailable ไม่แสดงยอดเก่า. ห้ามสำเนายอดไว้ใน state หรือเปลี่ยน canSubmit/server gates. ข้อนี้แทนข้อเดิมที่ซ่อนยอดทุกช่วง isFetching.

Refresh-label amendment — Approved by owner 2026-11-13: ไม่แสดงข้อความอัปเดตใต้ยอดใช้ได้ระหว่าง background refresh. คงยอดเดิมตาม scope/error gates ที่อนุมัติ; สถานะสำหรับ screen reader คงไว้แบบ sr-only โดยไม่กินพื้นที่หน้าจอ.
