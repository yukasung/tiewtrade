# ลดเวลารอ CI — Requirements

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-26**
วันที่: 2026-10-26

## ทำไมต้องมี

เจ้าของสั่งลดงานตรวจซ้ำและเวลารอ CI หลังอนุมัติการเลือก full regression
ตามผลกระทบใน testing §7 วันที่ 2026-10-26. Workflow ปัจจุบันรับทั้ง push ทุก branch
และ pull_request โดยไม่มี cancellation ของรอบเก่า และเรียกทุก job แม้แก้เฉพาะเอกสาร.
ยังไม่มีข้อมูลระยะเวลาราย job เพียงพอสำหรับรับรองว่าจะลดเวลาได้กี่นาที.

## ขอบเขต

ปรับ GitHub-hosted CI เดิมเพื่อหลีกเลี่ยงรอบซ้ำ ยกเลิก candidate เก่า และเลือก job
ตามผลกระทบ โดยรักษา required checks และผลตรวจที่เชื่อถือได้.
ใช้ workflow เดิมเป็นฐาน ไม่รื้อฟื้น self-hosted CI ที่ยุติแล้ว.
ไม่เปลี่ยน application behavior, trading rules, secrets หรือ branch protection.
ไม่ commit/push/dispatch workflow จนเจ้าของสั่งตามกฎ Git.

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | ใช้ pull_request สำหรับ branch ที่เสนอ merge และ push บน main สำหรับตรวจหลัง merge แทน push ทุก branch; มี manual dispatch สำหรับตรวจ branch ที่ยังไม่มี PR และ release โดยไม่ส่ง Live orders | คำสั่งลด CI ซ้ำ; testing §7 |
| RQ-02 | ยกเลิก run เก่าของ PR เดียวกันเมื่อมี candidate ใหม่; ไม่ยกเลิก main/release/manual run ที่กำลังทำงานเพียงเพราะมี run ใหม่ | ลดการตรวจ candidate ที่ถูกแทนที่ โดยรักษาหลักฐาน checkpoint |
| RQ-03 | งานเอกสารทั่วไปไม่เริ่ม application tests, E2E หรือ Docker build; เอกสาร/config ที่ใช้สร้างโค้ดหรือกระทบ runtime ต้องจัดเป็นงานที่มีผลกระทบ ไม่พิจารณาจากนามสกุลไฟล์อย่างเดียว | testing §7 |
| RQ-04 | เลือก backend/frontend/API-contract/E2E/container checks จาก diff และ dependencies/contracts ที่เกี่ยวข้อง; ส่วนกลาง/workflow/lockfiles/schema/config หรือ path ที่ระบุผลกระทบไม่ได้ให้ขยายชุดตรวจอย่างปลอดภัย | กฎ full regression Approved 2026-10-26 |
| RQ-05 | รักษา required check names เดิม ตรวจให้ selector สำเร็จและชุดที่เลือกผ่านก่อนรายงาน success; selected job ที่ล้ม ถูกยกเลิก หรือขาดผลต้องไม่ถูกแปลงเป็น success; ไม่ใช้ workflow paths filter ที่ทำให้ required checks ค้างรอ | testing §1 และ §7; required checks ตามหลักฐาน CI เดิม |
| RQ-06 | คง assertions ของ correctness/trading safety, financial precision, isolation, transaction/concurrency/idempotency และ API contracts ที่เกี่ยวข้อง; ไม่ลบ tests หรือลด thresholds เพื่อให้เร็วขึ้น | AGENTS.md และ testing §2–5 |
| RQ-07 | manual full-validation mode ต้องเรียกทุกชุดที่ CI นี้รับผิดชอบโดยไม่ถูกตัวเลือกตาม diff ตัดออก; workload/endurance ยังคง release checkpoint ตาม validation เดิม ไม่เพิ่มเป็นขั้นอัตโนมัติทุก PR | testing §7 |
| RQ-08 | ถ้าจะแยก E2E ให้รันขนาน ต้องแยก PostgreSQL/Redis/processes และ artifacts ต่อชุด พร้อมพิสูจน์ isolation ก่อนใช้; ถ้ายังพิสูจน์ไม่ได้ให้คงลำดับเดิมและบันทึกข้อจำกัด ไม่เพิ่ม workers บน shared mutable state | testing §7 |
| RQ-09 | ใช้หลักฐานเดิมและ targeted workflow/selector checks ก่อน; ตรวจ trigger, cancellation, path selection, required-check failure propagation และ full mode ด้วยกรณีที่ชัดเจน ไม่รัน application full regression เพื่อพิสูจน์เฉพาะการจัดคิว CI | คำสั่งลดงานตรวจซ้ำ; testing §7 |
| RQ-10 | รายงานแยกผล local กับผลจริงบน GitHub; ไม่อ้างว่า CI เร็วขึ้นเป็นตัวเลขหรือ Completed จนมีหลักฐานที่เกี่ยวข้อง และไม่ข้าม required CI ของ candidate สุดท้าย | testing §7 |

## ของเดิมที่เกี่ยวข้อง

- `.github/workflows/ci.yml`: jobs และชื่อ checks เดิม รวม F-18 E2E ที่มีการแก้ค้างอยู่.
- `frontend/package.json`, `frontend/playwright*.config.ts`: คำสั่ง E2E และข้อจำกัด shared state.
- `specs/standards/testing.md` §7: กฎเลือกชุดตรวจและใช้หลักฐานเดิม.
- `specs/features/2026-10-23-self-hosted-ci/evidence/closure-checkpoint.md`:
  หลักฐาน required checks เดิมและการยุติ self-hosted approach ไม่ใช่แผนที่นำมาใช้ต่อ.

## กฎความปลอดภัยที่เกี่ยวข้อง

คงข้อห้ามส่ง Live orders ใน automated validation, Paper/Live isolation และ
ไม่เปิดเผย secrets ตาม AGENTS.md, testing §4–5 และ trading-safety.md.

## ยังไม่ชัด / จุดหยุด

- ไม่มี Needs Clarification ด้าน business/trading สำหรับขอบเขตที่เสนอ.
- Requirements ได้รับอนุมัติ 2026-10-26; plan/validation ฉบับปรับได้รับอนุมัติ
  2026-11-11 แล้ว. จุดหยุดถัดไปคือ Ready for Code Review → รอ `review code`
  และคำสั่ง Git ตาม AGENTS.md.
- ใช้ branch แยกของงานนี้และรักษางานอื่นที่ค้างอยู่ตาม inventory ใน plan/checkpoint;
  ไม่แก้แผน self-hosted เดิมหรือย้ายการแก้ feature อื่นเข้า branch นี้โดยพลการ.
