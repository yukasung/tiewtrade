# Security CI — ข้อเสนอปรับวิธีตรวจ V-12

สถานะ: **Approved — เจ้าของเลือก “อนุมัติข้อเสนอและปรับเอกสาร” 2026-11-05**

นำข้อเสนอไปปรับ requirements.md, plan.md และ validation.md แล้ว ส่วนด้านล่างเก็บ
เหตุผล ข้อความที่เสนอ และความเสี่ยง ณ เวลาตัดสินใจ ไม่ใช่ผลทดสอบ Passed
วันที่: 2026-11-05
PR: https://github.com/yukasung/tiewtrade/pull/48

## เหตุผลและขอบเขตการตัดสินใจ

เจ้าของยืนยันว่าไม่มีบัญชีหรือ organization อื่นสำหรับสร้าง fork จริง และสั่งให้จัดทำ
ข้อเสนอแนวทางทดแทน การสั่งจัดทำข้อเสนอยังไม่ใช่การอนุมัติให้เปลี่ยนเกณฑ์ตรวจรับ
ปัจจุบัน V-12 ยัง Partial: static contract ผ่าน แต่ remote fork test เป็น Not Run
และยังบล็อกการ merge ตาม validation เดิม

เสนอให้คงข้อกำหนด RQ-9 ทุกข้อ แต่ยอมรับวิธีตรวจแบบผสมสำหรับ feature นี้โดยเจ้าของ
รับทราบช่องว่างของหลักฐานอย่างชัดเจน ไม่อ้างว่าการทดสอบ PR ภายใน repo คือ fork test
ไม่สร้างบัญชีแทนเจ้าของ ไม่เปิด token แบบ write และไม่เพิ่ม secrets เพื่อทดสอบ

## ข้อความที่จะเพิ่มใน requirements.md หลังอนุมัติ

เพิ่มหัวข้อ “วิธีตรวจ RQ-9 เมื่อไม่มีบัญชี fork” ต่อจากตารางข้อกำหนด:

> RQ-9 ยังคงบังคับเต็มขอบเขต สำหรับ Security CI รอบนี้ เจ้าของยอมรับหลักฐาน
> static contract + GitHub settings readback + effective job permissions ของ PR จริง
> ภายใน repository + disposable scanner marker probes ตาม plan แทนการบังคับมี
> remote fork run ก่อน merge ต้องบันทึกว่า fork execution/approval และ cross-repository
> candidate/API/artifact behavior ยังไม่ได้ทดสอบจริง การยอมรับนี้ไม่ใช่ exception
> ให้ workflow เข้าถึง secrets หรือ write token และไม่ใช้ข้าม security/required CI อื่น

## สิ่งที่จะเพิ่มใน plan.md หลังอนุมัติ

1. ตรวจ workflow ทุก job และ reusable/action call ที่เกี่ยวข้อง: ใช้ pull_request,
   ไม่มี privileged event, secrets reference/inherit, environment secrets, write permission,
   persisted checkout credential หรือ self-hosted runner; actions ใช้ full SHA
   และตรวจ repository workflow permissions จาก API อีกครั้ง
2. ใช้ PR #48 ที่มีอยู่ตรวจ effective GITHUB_TOKEN permission ของทุก job จากส่วน
   job setup ใน logs เก็บเฉพาะชื่อ permission/ระดับและ job/run/SHA ไม่เก็บ token
   ทุก scope ต้อง read/none ตาม job ไม่มี write; หากพิสูจน์ไม่ได้ให้คง Partial
3. ใน disposable validation PR ที่มีอยู่ในขอบเขต V-16 เพิ่ม marker fixtures ที่ไม่ใช้
   credential จริง: Python/JS entrypoint และ npm lifecycle script ที่จะสร้างไฟล์ marker
   เมื่อถูกรัน ตรวจใน harness รอบ scanners ว่า marker ไม่เกิดทั้งก่อนและหลัง scan
   ใช้ marker เฉพาะ entrypoint/lifecycle ไม่อ้างว่า CodeQL ไม่ประมวลผล source เลย
   policy unit tests และ helper ของ candidate ยังเป็นโค้ดที่ workflow รันด้วย read token
   ตามปกติ ต้องบันทึกขอบเขตนี้ ไม่อ้างว่าไม่มี candidate code รันทั้งหมด
4. คง pinned actions/CLI, standard ephemeral hosted runner, read-only PR token,
   ไม่มี repository secrets และไม่มี cache/raw report/database upload ตามแผนเดิม
   ไม่เพิ่ม secret-sentinel ผ่าน repository secrets หรือทดสอบ token ด้วยคำขอเขียน
5. อ้างอิง GitHub platform contract เรื่อง fork pull_request และบันทึกข้อจำกัดด้านล่าง
   เป็นหลักฐานประกอบ ไม่ใช้เอกสารแพลตฟอร์มแทนผลทดสอบจริงโดยไม่ระบุข้อจำกัด
6. ก่อนรับ merge ของ PR จาก fork ครั้งแรก ต้องตรวจ fork run จริงบน head/base นั้น
   รวม approval policy, candidate API/ref resolution, artifacts, ทุก scanner และ gate
   หากไม่ได้รัน/ล้ม ให้คง PR นั้นไม่พร้อม merge; ไม่ใช้หลักฐาน same-repo เดิมปิดรายการนี้
   การเปลี่ยน events/permissions/secrets/runner หรือ platform policy ต้องประเมินใหม่

การเพิ่ม harness/fixture ทำได้หลังอนุมัติเอกสารที่เกี่ยวข้อง และต้องผ่าน targeted checks
กับ review ตามกฎเดิม ไม่แก้ application/trading code

## ข้อความทดแทน V-12 ใน validation.md หลังอนุมัติ

| รหัส | เกณฑ์ | วิธีตรวจและผลที่ต้องได้ | ระยะ |
|---|---|---|---|
| V-12 | PR permissions — RQ-9; owner-approved alternative | static per-job/action contract + repository settings readback + real same-repo PR effective token permissions ไม่มี write + real disposable scanner marker probes ไม่ execute entrypoint/lifecycle; หลักฐานผูก run/head/base และเจ้าของรับทราบว่า fork runtime ยัง Not Run | Feature |

V-12 จะ Passed ได้เมื่อหลักฐานใหม่ครบหลังอนุมัติเท่านั้น ผลเดิมไม่ถูกเปลี่ยนเป็น Passed
อัตโนมัติ รายการ “remote fork execution: Not Run — accepted evidence gap” ต้องแสดง
ต่อใน validation/remaining risks และ checkpoint แม้ V-12 ที่ปรับแล้วผ่าน
งานนี้ไม่มี Release gate ใหม่ที่แสร้งว่าได้ตรวจ fork แล้ว; V-19 และ Feature gates อื่นคงเดิม
ข้อจำกัดนี้ต้องรายงานเมื่อปิดงาน และทดสอบก่อนรับ merge ของ fork PR ครั้งแรกตาม plan

## ความเสี่ยงที่เจ้าของต้องยอมรับ

- ยังไม่พิสูจน์การ withholding secrets, การปรับสิทธิ์ token และ approval policy
  ใน event จากผู้ส่งภายนอกจริง แม้ GitHub ระบุ platform contract ไว้
- ยังไม่พิสูจน์ cross-repository refs/API visibility และ artifact/gate behavior จริง
  อาจทำให้ fork PR ล้มและต้องแก้ก่อน merge; gate ต้องคง fail closed
- same-repo read-only run และ marker probes เพิ่มหลักฐานบางส่วน แต่ไม่เทียบเท่า fork run
- ข้อเสนอนี้ลดความครอบคลุมของการตรวจรับก่อน merge เมื่อเทียบกับ V-12 เดิม
  โดยไม่ลด security policy/severity/exception/required checks ของ implementation

หากเจ้าของไม่ยอมรับช่องว่างนี้ ให้คง V-12 เดิมและ PR #48 เป็น draft จนมี fork จริง
การอนุมัติข้อเสนอนี้ไม่ใช่คำสั่ง merge หรือการยอมรับว่าเกณฑ์อื่นผ่านแล้ว

## แหล่งอ้างอิง

- [GitHub: Events that trigger workflows — pull requests from forks](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflows-in-forked-repositories): fork pull_request ใช้ read-only GITHUB_TOKEN และไม่ส่ง secrets อื่น
- [GitHub: Workflow syntax — permissions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions): การกำหนด permissions และการปรับสิทธิ์สำหรับ fork
- [GitHub: Managing Actions settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository): repository policy และการอนุมัติ runs จาก fork

ขั้นถัดไป: ตรวจหลักฐานทดแทนตามเอกสารหลักที่แก้แล้ว; ไม่ต้องขออนุมัติแนวทางซ้ำ
ไม่มีการเปลี่ยน settings, commit/push หรือ merge เพื่อจัดทำข้อเสนอนี้
