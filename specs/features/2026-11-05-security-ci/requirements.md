# Security CI — Requirements

สถานะ: **Approved — เจ้าของอนุมัติ requirements ทั้งฉบับ 2026-11-05**

**Approved amendment2026-11-07 (F17 Option A):** RQ-2/3/6/7 and §6.2 also allow an
explicit owner-approved immutable evidence registry binding commit/path/blob/rule
and exact deduplicated occurrence count, with reason/approval/evidence. The fixed
39-entry dataset is defined in [the approved amendment](../2026-11-02-tp-sl/publication-evidence-policy-proposal.md).
Keep full history/tree scanning, existing occurrence approvals, severity rules and
15-minute budget. Changed bindings/new findings remain blocked. Add safe stage
timing and identity-preserving Git lookup optimization, with parity/negative tests;
shape or directory alone never authorizes an exception. Bounded public reports may
group resolved approved artifact occurrences with explicit counts/bindings while
retaining complete private evaluation and unchanged blocking for unresolved rows.

**Approved data extension2026-11-07:** owner approved the exact100tree identities
listed in [the extension](../2026-11-02-tp-sl/tree-occurrence-extension-proposal.md).
Only8of39binding count/set digests change, total48218. No identity/matcher/coverage/
severity/deadline change or generic exception is authorized.
วันที่: 2026-11-05

## ทำไมต้องมี

เจ้าของอนุมัติให้เริ่มเสริม security CI ด้วยเครื่องมือฟรี หลังการประเมินแบบ read-only
พบว่า repository เป็น Public แต่ secret scanning/push protection, Dependabot alerts/security
updates และ CodeQL default setup ยังไม่เปิด และ workflow ไม่มี security scans โดยตรง
เจ้าของอนุมัติ requirements ฉบับแก้ R1–R3 ทั้งฉบับเมื่อ 2026-11-05

ฐานที่ตรวจ: `origin/main` SHA `c8d8ca78971fce3d98f624e0c35128195168d831`.
CI เดิมมี lint/types/imports/tests, API contract, browser และ container checks ครบ 6 jobs;
GitHub บังคับ checks เหล่านี้แบบ strict รวม admins และ default workflow token เป็น read.

## ขอบเขต

- เปิดการตรวจ secrets และป้องกันการ push credentials ที่ GitHub รองรับ
- เปิด Dependabot alerts/security updates และเพิ่มการตรวจ dependency vulnerabilities ก่อน merge
- ใช้ CodeQL ตรวจ Python, JavaScript/TypeScript และ GitHub Actions
- เพิ่ม security gates ที่ตรวจสอบผลสำเร็จและผลปฏิเสธได้ โดยใช้ standard GitHub-hosted runners
- รวมการตั้งค่าฝั่ง GitHub และไฟล์ CI ที่จำเป็นเป็นงานเดียว มีหลักฐานการตรวจรับ

ไม่รวม SonarQube, บริการเสียเงิน, self-hosted/larger runners, การเปลี่ยนสิทธิ์ review ของทีม,
container hardening/image scanning, การแก้ application findings, dependency upgrades ในวงกว้าง
หรือการเปลี่ยนกฎเทรด การพบปัญหาในรายการนอกขอบเขตให้รายงานก่อนเปิดงานแก้แยก

## ข้อกำหนดที่อนุมัติแล้ว

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | ใช้ฟีเจอร์ฟรีสำหรับ Public repository และ standard GitHub-hosted runners เท่านั้น ไม่สมัคร add-on หรือเปิดค่าใช้จ่ายเพิ่ม; ตรวจโควตา artifact/cache และไม่เพิ่มการเก็บผลแบบไม่จำกัด | เจ้าของยืนยันแนวทางเครื่องมือฟรี; roadmap งาน self-hosted CI ที่ Retired |
| RQ-2 | เปิด repository secret scanning และ push protection; ตรวจประวัติ Git ครั้งแรกด้วยเครื่องมือฟรีที่เหมาะสม และมี secret check บน PR ซึ่งครอบคลุมรูปแบบที่เลือกไว้ใน plan โดยต้องระบุข้อจำกัดของการตรวจ | การประเมิน; standards/security.md §4 |
| RQ-3 | ห้ามพิมพ์ค่าของ secret ลง log, PR, รายงาน หรือ artifacts; fixtures สาธารณะต้องยกเว้นเฉพาะรายการพร้อมเหตุผล ไม่ยกเว้น directory กว้าง; หากพบ secret ที่อาจเป็นของจริง ให้รายงานตำแหน่งโดยปิดค่าและหยุดงานส่วนที่ต้องตัดสินใจเรื่อง revoke/rotate โดยไม่ทดสอบ credential กับบริการจริง; historical secret ที่แก้แล้วใช้เกณฑ์ remediated/revoked ในหัวข้อ 6.2 | AGENTS.md; standards/security.md §4; standards/trading-safety.md §2; NC-SEC-CI-02 |
| RQ-4 | เปิด Dependabot alerts และ security updates; ตรวจ dependency ทางตรงและทางอ้อมของ backend/frontend ตาม lockfiles ของ candidate บน PR ให้ครบขอบเขต ไม่ใช้เพียง dependency diff แทนการตรวจ dependencies เดิมที่ยังอยู่; ตรวจซ้ำตามกำหนดเพื่อพบ advisory ใหม่ แม้ไม่มี code diff | การประเมิน; คำสั่งเจ้าของให้เสริม security CI; NC-SEC-CI-01 |
| RQ-5 | ใช้ CodeQL ตรวจ source languages และ workflows ข้างต้นบน PR, default branch และตามกำหนด; เลือก default หรือ advanced setup เพียงวิธีเดียวใน plan เพื่อไม่สแกนซ้ำโดยไม่จำเป็น | การประเมิน; คำสั่งเจ้าของให้เสริม security CI |
| RQ-6 | secret findings ที่ยังไม่ผ่านการยืนยัน fixture/false positive หรือ remediated/revoked ตามหัวข้อ 6.2 บล็อก merge; dependency vulnerabilities ระดับ High/Critical และ CodeQL security findings ระดับ High/Critical บล็อก merge รวม findings เดิมที่ยังคงอยู่ใน candidate ล่าสุดตามหัวข้อ 6.1; ระดับอื่นที่จัดระดับได้รายงานตามจริง และกรณี severity ไม่ชัดใช้หัวข้อ 6.3 ไม่มี blanket baseline เพื่อทำให้ผ่าน | เจ้าของอนุมัติ requirements รวม R1–R3 เมื่อ 2026-11-05 |
| RQ-7 | scan/gate ที่ล้มเหลว อ่านผลไม่ได้ หรือไม่ได้รันตามขอบเขตต้องไม่กลายเป็น Passed; severity ที่ไม่ทราบ/อ่านไม่ได้หรือขัดกันจนตัดสินไม่ได้เป็น Needs Triage และไม่ผ่าน gate จนจัดระดับได้หรือมี exception ที่เจ้าของอนุมัติ; exceptions ต้องมีเหตุผล ขอบเขต และคำอนุมัติเจ้าของ ไม่มี auto-ignore หรือ auto-merge ของ dependency fixes | AGENTS.md; standards/testing.md; NC-SEC-CI-03 |
| RQ-8 | รักษา required CI เดิมทั้ง 6 checks; เพิ่ม security checks เป็น required เมื่อยืนยันชื่อและผลบน candidate จริงแล้ว โดยไม่สร้างช่วงที่ main merge ผ่าน security gate ที่ยังไม่รัน; ก่อน merge ต้องตรวจผลที่ตรง candidate ล่าสุดตามหัวข้อ 6.1 | การตั้งค่า main ปัจจุบัน; standards/testing.md; NC-SEC-CI-01 |
| RQ-9 | PR จาก fork ต้องไม่เข้าถึง secrets หรือ write token; security workflow ขอสิทธิ์เท่าที่จำเป็น ไม่รัน untrusted PR code ด้วยสิทธิ์สูง; Actions ที่เพิ่ม/แก้ในงานนี้ต้องตรึงด้วย full commit SHA | ค่า default token เดิม; แนวทาง GitHub Actions security |
| RQ-10 | ห้ามใช้ exchange credentials จริงหรือส่งออเดอร์ Live ระหว่างตรวจ; คง tests เดิมด้าน auth, CSRF, RLS/user isolation, secret leakage และ Paper isolation โดยไม่เปลี่ยน session storage, persistence, transaction หรือ trading behavior | AGENTS.md; standards/security.md; standards/trading-safety.md |
| RQ-11 | ก่อนเปิด/เปลี่ยน settings ให้บันทึกสถานะเดิมและกำหนดวิธีกู้คืนใน plan; ผลตรวจรับต้องแยก scan Passed, มี findings, Needs Triage, Not Run และข้อจำกัดจริง พร้อม candidate identity ตามหัวข้อ 6.1/ลิงก์ CI และที่มาของ severity ตามหัวข้อ 6.3 โดยไม่ถือว่า CI สีเขียวยืนยันว่าไม่มีช่องโหว่ทุกประเภท | standards/testing.md; ขอบเขตการประเมิน; NC-SEC-CI-01/03 |

## วิธีตรวจ RQ-9 เมื่อไม่มีบัญชี fork

สถานะ: **Approved — เจ้าของอนุมัติข้อเสนอและให้ปรับเอกสาร 2026-11-05**
หลักฐานการตัดสินใจ: [ข้อเสนอที่อนุมัติ](evidence/fork-validation-amendment-proposal.md).

RQ-9 ยังคงบังคับเต็มขอบเขต สำหรับ Security CI รอบนี้ เจ้าของยอมรับหลักฐาน
static contract + GitHub settings readback + effective job permissions ของ PR จริง
ภายใน repository + disposable scanner marker probes ตาม plan แทนการบังคับมี
remote fork run ก่อน merge ต้องบันทึกว่า fork execution/approval และ cross-repository
candidate/API/artifact behavior ยังไม่ได้ทดสอบจริง การยอมรับนี้ไม่ใช่ exception
ให้ workflow เข้าถึง secrets หรือ write token และไม่ใช้ข้าม security/required CI อื่น
ต้องตรวจ fork จริงก่อนรับ merge ของ fork PR แรกตาม plan; ผล same-repo ไม่เทียบเท่า fork run

## รายละเอียด RQ-6 — คำตัดสินจาก requirements review

เจ้าของสั่ง “แก้ไข” ตามข้อเสนอ R1–R3 เมื่อ 2026-11-05;
รายละเอียดต่อไปนี้ปิด NC-SEC-CI-01..03 และได้รับอนุมัติพร้อม requirements ทั้งฉบับ 2026-11-05

### 6.1 ผลต้องตรงกับ candidate ล่าสุด (R1)

- ประเมิน findings ทั้งใหม่และเดิมที่ยังคงอยู่ใน candidate ให้ครบขอบเขตของ scanner
  ไม่ใช้เพียงผลต่างของ PR หรือรายการ open alerts บน `main` แทนผลของ candidate
- ผลต้องผูกกับ head SHA และ base SHA หรือ merge SHA ที่ระบุคู่ head/base ได้ตามวิธีที่ plan เลือก
  เมื่อ head/base เปลี่ยน ผลเก่าต้องไม่ใช้ปิด gate ของ candidate ใหม่
- หาก PR แก้ finding เดิมแล้วและผล candidate พิสูจน์ว่าไม่เหลือ finding นั้น
  ห้ามบล็อกด้วยสถานะ alert ของ `main` ที่ยังไม่อัปเดต; finding อื่นยังตัดสินตามเกณฑ์เดิม
- หาก finding เดิมยังคงอยู่และเข้าเกณฑ์บล็อก ให้คง blocker ตามจริง;
  การแก้ application/dependencies ที่อยู่นอกขอบเขตต้องเป็นงานที่ได้รับอนุมัติแยก
  ไม่ถือว่าการตรวจพบอนุญาตแก้ runtime หรือยกเว้น finding อัตโนมัติ

### 6.2 Secret ในประวัติที่แก้ไขแล้ว (R2)

- เพิ่มผลการพิจารณา `remediated/revoked` แยกจาก fixture และ false positive;
  ใช้ได้เมื่อมีหลักฐานว่า credential เดิมถูก revoke/ทำให้ใช้งานไม่ได้แล้วและเจ้าของรับรอง
  การลบจากไฟล์ปัจจุบันหรือสร้าง credential ใหม่เพียงอย่างเดียวไม่ใช่หลักฐานว่า credential เดิมใช้ไม่ได้
- บันทึกหลักฐานโดยไม่เก็บค่า secret และระบุ occurrence เดิมให้แน่นอน
  เช่น commit, path, ตำแหน่งและ scanner finding identity ตามวิธีใน plan
  จึงปิด blocker ของ occurrence นั้นได้ พร้อมเก็บประวัติว่าเคยเป็น secret จริง
- ห้าม blanket allowlist ค่า secret หรือ directory และห้ามให้ exception เดิมครอบคลุม
  occurrence ใหม่ใน commit ใหม่โดยอัตโนมัติ; กรณีใหม่ต้องผ่านการพิจารณาของตนเอง
- หากยังไม่มีหลักฐาน remediation ให้คง blocker; งาน security CI ไม่อนุญาตให้ agent
  rotate/revoke credential, ทดสอบกับบริการจริง หรือ rewrite Git history โดยอัตโนมัติ

### 6.3 ที่มาของ severity และผลเมื่อข้อมูลไม่ครบ (R3)

- `plan.md` ต้องระบุแหล่งข้อมูล severity, field และ mapping ที่แน่นอนต่อ scanner
  พร้อมวิธีอ้าง advisory หรือ rule metadata ย้อนกลับได้ และแยก CodeQL security severity
  ออกจากระดับ error/warning ของผลวิเคราะห์ทั่วไป
- เมื่อ vulnerability/security finding ไม่ทราบ severity, อ่านไม่ได้ หรือข้อมูลขัดกัน
  จนยังตัดสินตาม mapping ไม่ได้ ให้เป็น `Needs Triage` และไม่ผ่าน gate
  แม้ตัว scanner จะรันสำเร็จ; ห้ามแปลงเป็น Low หรือข้ามเพราะ field ไม่มี
- ปลด blocker ได้เมื่อจัดระดับด้วยหลักฐานตาม mapping แล้วประเมินตาม RQ-6 ใหม่
  หรือมี exception ที่เจ้าของอนุมัติตาม RQ-7; ไม่ถือว่า scanner exit code สำเร็จเป็นผลผ่านนโยบาย

## กฎความปลอดภัยที่เกี่ยวข้อง

- `standards/security.md` §1–4: session ใน PostgreSQL, สิทธิ์, validation และห้าม secrets ใน log
- `standards/trading-safety.md` §2: การจัดการ API credentials
- `AGENTS.md`: ห้ามเปิด Live โดยปริยาย; Stateless Application & Session Management;
  ไม่ commit/push/merge หากเจ้าของยังไม่สั่ง และหยุดตามจุดอนุมัติของ feature
- งานนี้ไม่เพิ่ม persistent application state หรือ infrastructure ใหม่

## ของเดิมที่ต้องพิจารณาใช้ซ้ำเมื่อวางแผน

- `.github/workflows/ci.yml`, `.github/workflows/venue-contract.yml`
- `backend/uv.lock`, `frontend/package-lock.json`
- `backend/tests/api/test_no_secrets.py`, `backend/tests/api/test_auth_flow.py`
- `backend/tests/infra/auth/test_session_rules.py`, `backend/tests/infra/db/test_user_isolation.py`
- `backend/tests/gates/test_paper_isolation.py`, `backend/tests/test_api_key_safety.py`

## ยังไม่ชัด / จุดอนุมัติ

Review R1–R3 แก้ครบตามคำสั่งเจ้าของ 2026-11-05 และตรวจความสอดคล้องของเอกสารแล้ว;
ดูหลักฐานใน [requirements-review.md](requirements-review.md).
**NC-SEC-CI-01..03 Closed** ใน `specs/mission.md` §9; ไม่มี clarification ค้างในขอบเขตนี้
เจ้าของอนุมัติ requirements ฉบับแก้ไขทั้งฉบับแล้วเมื่อ 2026-11-05;
จัดทำ `plan.md` และ `validation.md` ต่อได้ และต้องได้รับอนุมัติเอกสารทั้งสอง
ก่อนเปลี่ยน workflow หรือ GitHub settings

## แหล่งอ้างอิงภายนอก

- [GitHub security features](https://docs.github.com/en/code-security/getting-started/github-security-features)
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
