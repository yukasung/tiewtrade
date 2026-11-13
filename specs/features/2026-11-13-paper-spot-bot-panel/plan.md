# Paper Spot Bot Panel — Plan

สถานะ: **Approved — เจ้าของ approve วันที่ 2026-11-13 รวม RQ-13 และ review corrections**
วันที่: 2026-11-13
Requirements: [RQ-01–13 Approved](requirements.md)
ฐาน: `4a9b46a`; branch `feature/paper-spot-bot-panel`

## แนวทางและขอบเขต

เปลี่ยนเฉพาะแผงสร้างออเดอร์ใหม่ของ Paper Spot เป็น UI บอท disabled ตาม RQ-01–12
ทำใน worktree แยก ไม่สลับ runtime ของเจ้าของระหว่างพัฒนา ไม่แก้หน้า Live หรือ backend
navigation เป็น dependency ที่ยังต้องผ่าน workflow ของตัวเอง; ห้ามถือว่าฐานนี้ merged แล้ว

## ของเดิมที่จะใช้ซ้ำ

- `frontend/src/components/ui/{Select,Input,Label,Button,Alert}.tsx`: controls กลางจาก TailAdmin
  ต้นแบบ `references/admin-template/src/components/form/{Select.tsx,input/InputField.tsx,Label.tsx}`
  และ `components/ui/{button/Button.tsx,alert/Alert.tsx}`; ไม่มี appearance ใหม่หรือ library ใหม่
- `frontend/src/TradingWorkspace.tsx`: ใช้ช่อง form/details และ layout เดิม ไม่เพิ่ม global CSS
- `frontend/src/components/MarketValue.tsx`: แสดงยอด string โดยไม่คำนวณเงิน
- `frontend/src/PaperTradePage.tsx`: snapshot/query owner scope, recovery journal/status,
  discovery, risk และ PaperTradingActivity เดิม; คง cancel และ retry payload/key เดิม
- `frontend/src/manualOrderMessages.ts` และรูปแบบ locale เดิม: ใช้ข้อความร่วมที่ความหมายตรง
  เพิ่มข้อความบอทใน module เฉพาะ ไม่เปลี่ยนคำที่หน้า Live ใช้
- `frontend/e2e` fixture/helper เดิมและ API request pattern ที่มี CSRF/idempotency headers:
  ใช้เฉพาะบัญชีทดสอบและฐานแยก ไม่ส่งคำสั่งบัญชีเจ้าของ

## สิ่งที่จะเปลี่ยน

1. เพิ่ม `PaperBotPanel.tsx` รับยอด string/null และสถานะ loading/unavailable/ready จาก parent
   ไม่รับ callback สำหรับส่งออเดอร์หรือเริ่มบอท; state มีเพียงงบร่าง string
   ใช้ section ไม่ใช่ form; Input type=text/inputMode=decimal, Button type=button disabled
   ผูก label/id และข้อความอธิบายกับช่อง/ปุ่ม ไม่มี submit handler หรือ localStorage
   Select แสดง Grid Close System ค่าเดียว; ไม่สร้าง registry/plugin/strategy implementation
2. เพิ่มข้อความไทย/อังกฤษ: หัวข้อ เลือกบอท งบรวม เริ่มบอท และคำอธิบายว่ายังไม่เปิดใช้งาน
   ไม่สร้าง validation จำนวนเงินหรือสัญญาณพร้อมเริ่ม; ยอดแสดงด้วย MarketValue
3. PaperTradePage แทน ManualOrderForm ด้วย panel ที่ key ผูก owner/wallet_id/episode_id/base
   ใช้ outer owner key เดิมด้วย; resize/menu ไม่เปลี่ยน key
   ไม่ reset จาก completed request key; รักษา state/callback สำหรับคำขอ NEW SELL และ recovery; ถอดเฉพาะส่วนเปิด BUY ใหม่
   ห้ามลบ ManualOrderForm กลางเพราะ Live และ component safety tests ยังใช้
4. Parent ส่งยอดเฉพาะ snapshot ที่ตรง PAPER/base/scope และ source พร้อม ไม่มี error/placeholder
   loading/refresh ที่ยังยืนยันข้อมูลไม่ได้แสดงสถานะโหลดหรือไม่พร้อม ไม่ใช้ยอดข้าม scope
   รีเฟรชไม่เปลี่ยน scope จริงต้องไม่ล้างร่าง; เมื่อยืนยัน wallet/episode ใหม่จึงเปลี่ยน key
   ไม่สำเนายอด server ลง state เพื่อรักษาร่าง
5. แยก recoveryNotice, rejection เดิม, risk latch/stop, no-wallet และข้อมูลความปลอดภัยของ
   รายการเดิมไว้ใต้ panel ผ่าน details หรือ sibling section มีหัวข้อชัด ไม่รวมในฟอร์มบอท
   เก็บ discovery/polling/tracked requests และ cancel/TP/SL เดิม ไม่เปลี่ยน gate ของตาราง
   ป้าย manual admission ต้องไม่แสดงว่าบอทพร้อม; เหตุหยุด/ข้อมูลผิดพลาดที่จำเป็นยังต้องเห็น
6. ปรับ tests ที่หา manual form ใน Paper ให้ตรวจ panel ใหม่; unit สำหรับ journaling ก่อน POST
   ย้าย assertions ก่อนส่งไป tests ของ useManualAttempt โดยเรียก send จริง (ไม่ seed journal แทนขั้นก่อน POST); ManualOrderForm ตรวจ payload และ ManualOrderSession ตรวจ session cleanup; page ตรวจ recovery จาก journal fixture และ modal SELL
   ไม่ลบ assertions key เดิม, owner isolation, UNKNOWN, cancel, money หรือ TP/SL

## การปรับ E2E ที่ได้รับผลกระทบ

ค้น callers ของฟอร์มที่ถอดใน `manual-orders.spec.ts`, `risk-limits.spec.ts`,
`protections.spec.ts` และ `top-navigation.spec.ts` ก่อนแก้ ใช้ helper ทดสอบร่วมสำหรับ
สร้างออเดอร์ผ่าน production API ด้วยบัญชี fixture/CSRF/key/scope เดิม
เก็บ assertions server outcome/เงิน/fills/rejection และตรวจหน้ารายการจริงต่อ
ไม่ใช้ API helper แทนการพิสูจน์ browser journal: คง case NEW SELL ผ่าน modal จริงเพื่อพิสูจน์ write-before-POST/network failure/reload; case legacy BUY UNKNOWN/reload ใช้ seed journal
ตาม envelope เดิมและ fault fixture แล้วกดตรวจ/retry บน UI ที่คงอยู่ ตรวจ key/payload ไม่เปลี่ยน
case UI BUY ใหม่ที่เลิกมีแล้วระบุ superseded พร้อมการทดสอบใหม่ว่า panel ไม่ส่ง NEW
คง component/session tests พิสูจน์รูปแบบและ journaling เดิม ไม่ skip ทั้ง suite หรือปรับยอด/timeout
หากต้องเปลี่ยน harness/production contract นอกนี้ ให้หยุดเสนอ amendment

## ฐานข้อมูล API และ session

ไม่มี migration/API/types contract เปลี่ยน ไม่มี bot endpoints หรือ account-use mutation
draft เป็น ephemeral UI state เท่านั้น; session และ business truth ยังอยู่ shared backend เดิม
ไม่เพิ่ม infrastructure และไม่เปลี่ยน routing/authorization/RLS หรือการเปิด Live

## Checkpoints และความเสี่ยง

- หลังอนุมัติ: implement component/page/messages และปรับ targeted unit/E2E fixtures ตามผลกระทบ
- ตรวจ V01–V09 ก่อนแจ้ง Ready for Code Review; ยังไม่ทำ code review เอง
- ความเสี่ยงหลัก: ถอด recovery ไปพร้อมฟอร์ม, ค่าเก่าข้ามเจ้าของ, ร่างหายระหว่าง polling,
  ปุ่ม Enter ส่ง NEW, tests เดิมเสียเพราะถอด UI; พิสูจน์ด้วย validation ด้านล่าง
- ก่อน browser campaign แจ้งขอบเขต/เวลาประมาณตามกฎ testing; ไม่เริ่ม workload/backend full suite
  โดยไม่มีผลกระทบที่ระบุได้ ผลด้านเงิน/DB เดิมใช้ต่อได้เมื่อโค้ดส่วนนั้นไม่เปลี่ยน
- หากเกณฑ์เดิมล้มครบ 3 รอบหยุดรายงานตาม AGENTS.md ไม่ auto-rerun หรือผ่อน safety
- ก่อน merge V10 ต้องผ่าน; หลัง review/fixes รอคำสั่ง refactor ตาม workflow
  commit/push/merge และเปลี่ยน local preview เมื่อเจ้าของสั่งเท่านั้น
- งานนี้ไม่ปิด F-17 หรือ F-20/F-21; Batch/Release เดิมยัง Pending ตาม roadmap


## Review corrections — 2026-11-13 (Approved)

### R1: รักษาช่องทางลด/ปิดสถานะ

RQ-13 Approved: เพิ่มปุ่มบริเวณกิจกรรมใต้กราฟ เปิด shared Modal
ใช้ ManualOrderForm เดิมด้วย optional fixed SELL mode และ submit label สำหรับคำขอขาย
ค่า default ของ component คงเดิมเพื่อไม่เปลี่ยน Live; โหมด fixed SELL ต้องล็อกทั้ง UI
และ payload ห้ามเพียงซ่อนแท็บแต่ state ยัง BUY; ไม่เพิ่ม business validator ใหม่
ใช้ state draftKey/scope/canSubmit(SELL)/useManualAttempt ของหน้าเดิม
ห้าม clear journal เมื่อ modal ปิดหรือ unmount; recovery notices อยู่ด้านนอก modal
ไม่เพิ่มปุ่มขายทั้งหมดหรือคำนวณ available หลังหัก protections ฝั่ง client
source ที่เพิ่มใน diff: ManualOrderForm และ modal/button integration ของ PaperTradePage
ใช้ components/ui/Modal.tsx (ต้นแบบ admin template modal) โดยคง focus behavior เดิม

### R2: พิสูจน์ journal ก่อน POST ที่จุดจริง

เพิ่ม targeted hook harness สำหรับ useManualAttempt/useDurableAttempt path จริง:
- ณ fetch POST ต้องอ่าน journal ที่ตรง owner/key/payload ได้แล้ว
- writeAttempt ล้มต้องมี POST 0 ครั้ง; send ซ้ำขณะ pending ต้อง POST ครั้งเดียว
- network failure → unmount/remount → lookup404 ต้องไม่ POST เอง
- explicit retry ใช้ key/payload/episode เดิม แม้ active episode เปลี่ยน
- owner ไม่ตรงห้ามส่งและไม่อ่าน journal ข้าม owner
คง assertions จาก PaperTradePage.test.tsx:68–98 ใน hook tests และตรวจ UI SELL integration
ไม่อ้าง ManualOrderForm/ManualOrderSession tests ว่าพิสูจน์ network journaling ได้เอง

ก่อน Ready for Code Review ต้องผ่าน V11–V12 เพิ่มด้วย; ไม่มี source เปลี่ยนในรอบแก้เอกสารนี้

## Code-review fixes — เจ้าของสั่งแก้ 2026-11-13

- R1: เพิ่ม `scrollable` แบบ opt-in ใน shared Modal และเปิดเฉพาะ SELL modal;
  ค่า default ของผู้เรียกอื่นคงเดิม ใช้ internal overflow pattern จาก
  `references/admin-template/src/components/calendar/CalendarEventModal.tsx`.
  จำกัด dialog ตาม viewport หัก outer padding เดิม เพื่อ accessibility ของฟอร์มยาว;
  ไม่เปลี่ยนสี/ตัวอักษร/focus lifecycle หรือกฎการส่งคำสั่ง.
- R2: NEW SELL ผ่าน UI จริง พร้อม journal assertion ณ intercept ก่อนส่งต่อ API,
  lost receipt/reload/manual retry key+payload เดิม และ DB command/order หนึ่งรายการ.
- R3: risk rejection ตรวจ status/code ตาม API contract; discovery failure ต้องบล็อก
  SELL submission และไม่มี journal/POST ไม่ใช้ปุ่ม Start disabled เป็นหลักฐาน gate.
- ตรวจเฉพาะ impacted unit/static, scroll matrix และ E2E ใหม่/แก้บน fixture แยก.
  หลังปิด findings ให้ถาม refactor ตาม AGENTS.md ไม่ commit/push เอง.

Display amendment 2026-11-13: ถอด timestamp row และ prop snapshotAt ที่ไม่ใช้จาก PaperBotPanel/caller; คงการอ่านข้อมูลและ gates เดิม. ใช้ component/page tests และ static checks ที่เกี่ยวข้อง.

Compact panel amendment 2026-11-13: ใช้ token spacing/border/label จาก admin template form controls เดิม; compact heading/inline balance. ถอดเฉพาะ summary markup และ imports ที่เลิกใช้ ไม่ถอด risk query/recovery. ปรับ test ของ summary ที่ถูกยกเลิก และ locator heading/setup ที่อ้างข้อความเดิม.

Admission-warning placement 2026-11-13: ย้าย warning block เดิมจาก details ไปแทนรายการเหตุใน SELL modal; ใช้ list marker เพียงชุดเดียว ไม่เปลี่ยน query/payload/validation. ตรวจ page regression ว่าคำเตือนไม่อยู่ภายนอก modal และ SELL ยังถูกบล็อกตามเดิม.

Stable balance refresh 2026-11-13: แยก snapshot readiness จากสถานะ fetching สำหรับ display เท่านั้น; fresh ของ SELL ยังคงต้องไม่ fetching. Panel แสดง amount ก่อน loading เมื่อ parent ยืนยัน scope ได้ พร้อมแถวสถานะที่จองความสูงและ tabular numerals. ใช้ TanStack snapshot เดิม ไม่มี last-balance cache. ตรวจ delayed refresh, error และ owner/scope regression.

Refresh-label amendment: เปลี่ยนสถานะ background update เป็น sr-only และถอด spacing wrapper ที่ไม่จำเป็น; ไม่เปลี่ยนข้อมูลหรือ safety gates.


## Owner-requested refactor — 2026-11-13

ปรับ JSX ของ PaperBotPanel ให้อ่านง่าย, แยก availableQuote expression ใน PaperTradePage และตั้งชื่อ setter ให้ตรงกับ selectedSide. รวม BUY fixture payload ที่ซ้ำใน manual-order/protection suites เป็น postFixtureBuy ใน helper เดิม. ไม่เปลี่ยน query, readiness gates, request identity, เงิน, API หรือพฤติกรรม UI.
