# 3m — refresh candidate base after main advanced

สถานะ: **Approved A — เจ้าของอนุมัติ sync main, targeted checks และ CI ทดแทนหนึ่งรอบ; ผ่านแล้วนำขึ้น local**
วันที่: 2026-11-07
อ้างอิง: browser-response-observer-amendment.md §A.4; V3-09

## หลักฐานที่ตรวจแบบอ่านอย่างเดียว

- Feature head89259c131304f9ed31db1e77affa95d1f694d034 ยังสืบจากf15596d
- mainขยับเป็น1237bf6f1e2146fff6c68d01094e4fbb96ebd8c3 จากPR61 API deadline clock
  เมื่อ2026-11-07T23:27:42+07:00 ก่อน feature observer commit23:35:48+07:00
- PR60 API base.sha ยังรายงานf15596d แต่ CI checkout merge commitc5b9039 มีparents
  1237bf6f1e2146fff6c68d01094e4fbb96ebd8c3 และ89259c131304f9ed31db1e77affa95d1f694d034
- tools/security/system.py::candidate ตรวจ merge parents/base/head อย่างเคร่งครัด;
  ความไม่ตรงของฐานนี้อธิบาย identity failure ที่ CLIลดข้อความเป็นINVALID_POLICY_DATA
  ไม่สรุปว่าพบช่องโหว่จากการสแกน: secrets/dependencies/CodeQLหยุดก่อนสแกน
- Security42392101117 Failed; CI42392101171 frontend/API contract/containerผ่าน
  browser job128461721567ผ่านทุกขั้นแล้ว; backend128461721509ยังรัน ณ จุดเสนอ
- ไม่ได้แก้ security policy/helper/configuration และยังไม่เริ่ม local migration

## A — Sync main into feature and run one replacement candidate (แนะนำ)

1. รักษา commit/ผลเก่า ไม่แก้ประวัติ ไม่force push. รวม origin/main ล่าสุดเข้า
   feature/f-12-3m ด้วยmerge commit และคง PR60เปิดไว้
2. ถ้ามีroadmap conflict ให้รักษาทั้งหลักฐาน3mและAPI clock; ห้ามลบงานของอีกfeature
   ตรวจ final diffเทียบmainให้เหลือเฉพาะงาน3mและเอกสารที่เกี่ยวข้อง
3. คง API clock fix ของ main,3m behavior, securitypolicy, Financial/Live rules,
   thresholds/timeouts และ Release profilesเดิม ไม่แก้guardให้ยอมรับidentityผิด
4. ตรวจ branch ancestry/base/head/merge parents และผลกระทบตามdiff; reuseหลักฐาน
   ของโค้ดที่ไม่เปลี่ยน และตรวจ targetedเฉพาะส่วนที่ได้รับผลกระทบ ก่อนcommit/push
5. รัน required CIหนึ่งreplacement roundบนcandidateใหม่ และติดตามทุกjobจนจบ
   หากผ่านจึงนำขึ้นlocalตามแผนเดิม; หากยังล้มหรือพบblockerอื่นให้หยุดรายงาน
   ไม่รันซ้ำหรือแก้security policyโดยอัตโนมัติ
6. คาดประมาณ25–30นาทีรวมCIหลังsync. ควรประสานไม่merge mainเพิ่มระหว่างรอบนี้
   เพื่อไม่ให้candidate baseเปลี่ยนอีก; ไม่หยุดprocess/บริการอื่นหรือเปลี่ยนbranch protection

ผลกระทบ: นำ API clock fix ที่อนุมัติ/mergeแล้วมารวมกับ3m และได้candidate identity
ที่เป็นปัจจุบัน ไม่ลดเกณฑ์Securityและไม่ใช่การmerge PR60เข้าmain

## B — Stop after current CI finishes

เก็บผลที่รันแล้วตามจริง ไม่sync/ทดลอง/อัปเกรดlocalต่อ; localยังไม่มี3m

## เหตุผลที่ต้องรอ

คำอนุมัติ observer A จำกัด required CIหนึ่งรอบ และเอกสาร §A.4 ระบุ
“ไม่ทดลองซ้ำอัตโนมัติหากด่านยังล้ม”. รอบนั้นเกิดSecurity failureแล้ว
จึงไม่ถือว่าคำอนุมัติเดิมอนุญาต replacement เพิ่มหรือแก้security policy

## Final outcome of the observer round — 2026-11-08 Asia/Bangkok

CI42392101171 จบ Success: backend4814testsและทุกisolation/migration gateผ่าน;
browserทุกsuite19/2/7/6/6ผ่าน รวมnative3m observer. Security42392101117จบFailure
ก่อนscansที่candidate identityตามข้างต้น. ทุกjobจบแล้ว ไม่มีงานCIเดิมค้าง
คำตัดสินA/Bสำหรับbase refreshยังไม่มา จึงยังไม่merge mainเข้าbranchหรือทดลองรอบใหม่

## Owner decision — 2026-11-08 Asia/Bangkok

เจ้าของเลือก A ผ่านคำถาม checkpoint. ทำตามขอบเขต A ต่อเนื่องได้
คงsecurity policyและผลเดิมทั้งหมด; หากreplacementยังล้มให้หยุดรายงาน
