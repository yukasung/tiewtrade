# CI runner DNS recovery — Plan/validation amendment

สถานะ: **Approved — เจ้าของตอบ approve 2026-11-11**
วันที่: 2026-11-11
อ้างอิง: [แผนที่อนุมัติ](plan.md), [validation](validation.md), [ผล pilot](evidence/github-pilot.json)

## ปัญหาที่พิสูจน์แล้ว

PR #67 บน head `d5e733ecdd6934179ed4c1944bf9bcd69c5bddc4` ผ่าน required checks
6/7 รายการ. CI run 43048918284 attempts 1 และ 2 ล้มก่อนเริ่ม E2E เพราะ
`Temporary failure resolving 'azure.archive.ubuntu.com'` ระหว่างติดตั้ง Playwright
system dependencies; installation exit 100. Retry ครั้งเดียวเฉพาะ E2E บน runner ใหม่
ยังพบสาเหตุเดิม. Required verdict เป็น failure ถูกต้องทั้งสองครั้ง.

Docs-only/cancellation pilot PR #68 ผ่านและปิดโดยไม่ merge; Security และชุด runtime
อื่นผ่าน. ไม่มีหลักฐานว่า application assertions ล้ม เพราะ browser setup ยังไม่สำเร็จ.

## สิ่งที่เสนอให้อนุมัติ

เพิ่ม bootstrap step เฉพาะ E2E ก่อน `npx playwright install --with-deps chromium`:

1. ใช้ helper Python standard library เปลี่ยนเฉพาะ URI ของ Azure Ubuntu mirror
   `http://azure.archive.ubuntu.com/ubuntu` หรือ HTTPS equivalent ให้เป็น
   `https://archive.ubuntu.com/ubuntu` ใน known runner APT configuration ได้แก่
   `/etc/apt/apt-mirrors.txt`, `/etc/apt/sources.list`, และ
   `/etc/apt/sources.list.d/ubuntu.sources` ที่มีอยู่จริง.
2. คง Ubuntu suite/components, security pocket, third-party repository entries,
   signing keys, APT signature verification และ TLS verification เดิม.
   เปลี่ยนเฉพาะ disposable GitHub-hosted runner ของ e2e-run; คำสั่ง Playwright,
   browser version, application dependencies, DB isolation และ test assertions คงเดิม.
3. Helper ต้องทำซ้ำได้ ไม่พิมพ์เนื้อหา config/secrets และรายงานเฉพาะจำนวนไฟล์ที่เปลี่ยน.
   Layout ที่ไม่รู้จัก/เขียนไฟล์ไม่ได้ต้องรายงาน operational failure ชัดเจน
   ไม่แปลง installation/test failure เป็น success และไม่เพิ่ม retry loop อัตโนมัติ.

นี่เป็นข้อเสนอให้ขยายแผนเฉพาะ environment bootstrap ไม่ใช่การอนุมัติแก้กฎเทรด,
เปลี่ยน required protection หรือ merge. เจ้าของอนุมัติแล้ว จึงปรับ plan/validation และลงมือในขอบเขตนี้ได้.

## ไฟล์และของเดิมที่จะใช้ซ้ำ

- `.github/workflows/ci.yml`: เพิ่ม bootstrap step ใน e2e-run ก่อน Playwright install;
  คง workers/check names และ verdict helper เดิม.
- `.github/scripts/prepare_e2e_apt.py`: helper สำหรับแก้ known config โดยมี root path
  สำหรับ fixture tests และ default เป็น `/etc/apt` บน runner.
- `.github/tests/test_e2e_apt.py`: ใช้ unittest/tempfile แบบเดียวกับ CI policy tests เดิม.
- plan/validation/checkpoint: บันทึกข้อยกเว้นจาก baseline execution-block preservation
  เฉพาะ bootstrap ใหม่นี้ และผลที่ตรวจจริง; บันทึกผลล้มสอง attempts เดิมต่อ.

## Validation ที่เสนอ (Feature)

- Fixture tests: รองรับ mirror-list, legacy sources, DEB822; แก้เฉพาะ Azure URI,
  preserve suite/components/security/third-party/signing-key fields; repeat แล้วไม่เปลี่ยนเพิ่ม;
  unsupported/missing layout และ write failure ไม่ได้ success เท็จ.
- Existing 28 CI policy/verdict tests, Ruff, strict mypy และ actionlint ตามผลกระทบ.
- Focused review ของ helper/workflow/bootstrap diff และตรวจ root privilege/config handling.
- GitHub candidate ใหม่ต้องผ่าน required checks 7/7 และ E2E จริงครบทุกชุด.
  Workflow change เลือก full CI ตาม policy ปัจจุบัน; ประเมินรอบใหม่ประมาณ 20–30 นาที
  และไม่ใช้ local fixture tests แทน Linux/browser proof.
- Docs-only/cancellation และชุดที่ source/contract/environment ไม่ได้รับผลกระทบใช้หลักฐาน
  ที่ยัง valid ต่อ; post-merge main/manual full ยังเป็น checkpoint เดิม.

## ทางเลือกและข้อจำกัด

ทางเลือกที่ไม่เปลี่ยนแผนคือรอ environment/mirror ฟื้น แล้ว retry เฉพาะ E2E บน SHA เดิม;
ขณะนี้ยังไม่มีข้อมูลใหม่ว่ารอบถัดไปจะต่างจากสองรอบก่อน จึงยังไม่เพิ่ม rerun.
ข้อเสนอ mirror recovery ลดการพึ่ง Azure mirror ที่พบ DNS failure แต่ไม่รับประกันว่า
Ubuntu archive endpoint หรือ network ของ runner จะเข้าถึงได้; หากยังล้มต้องคง blocker.

## Primary references

- [GitHub runner APT configuration](https://github.com/actions/runner-images/blob/main/images/ubuntu/scripts/build/configure-apt.sh)
- [Ubuntu archive integrity verification](https://documentation.ubuntu.com/security/software-integrity/archive-verification/)

อ้างอิง upstream ปัจจุบันเป็นข้อมูลประกอบ; runtime layout ที่ใช้จริงต้องตรวจบน CI
candidate และ fail ชัดเจนเมื่อไม่รองรับ. คง archive authentication แยกจากการเลือก mirror.
