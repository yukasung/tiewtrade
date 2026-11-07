# Security CI — Requirements Review

วันที่: 2026-11-05
ผลรอบแรก: **Changes Requested — 1 High, 2 Medium**
ผลหลังแก้: **R1–R3 Resolved — requirements ทั้งฉบับ Approved 2026-11-05**
ขอบเขต: requirements RQ-1..11, ขอบเขตงาน, จุดอนุมัติ และ GitHub documentation
เป็น document review ไม่ใช่ code review หรือหลักฐานว่า scanners ผ่าน

## R1 — High: เกณฑ์ findings เดิมยังไม่ผูกกับ candidate ที่จะ merge

ตำแหน่ง: `requirements.md` RQ-6, RQ-8, RQ-11

RQ-6 ให้บล็อก findings เดิมที่ยังเปิดอยู่ แต่ไม่ได้กำหนดว่าเป็น findings ที่ยังมีอยู่
ใน candidate หรือเป็นสถานะ open บน default branch. สถานะ alert บน GitHub อาจยังเปิดบน
`main` ขณะที่ PR ได้แก้แล้ว หาก gate อ่านรายการ open ของ main โดยตรง PR แก้ช่องโหว่
จะถูกบล็อกด้วยปัญหาที่ตนแก้เสร็จแล้ว. ในทางกลับกัน การใช้ dependency review ซึ่งตรวจ
การเปลี่ยน dependencies ใน PR อย่างเดียวพิสูจน์ไม่ได้ว่า dependency เดิมทั้งหมดปลอดจาก
High/Critical ตาม RQ-6.

ข้อเสนอ: กำหนดให้ตัดสินจากผลครบขอบเขตของ candidate ล่าสุดที่ผูก head/base หรือ merge SHA
ตามรูปแบบที่ plan เลือก รวม findings เดิมที่ **ยังคงอยู่ใน candidate**.
ต้องไม่บล็อก PR ด้วยสถานะ main ที่ยังไม่อัปเดต หากผล candidate พิสูจน์ว่าแก้แล้ว;
ต้องไม่ใช้ผลต่างของ PR เพียงอย่างเดียวแทน full candidate coverage.
หากพบ findings เดิมที่ยังต้องแก้ application ให้คง blocker และเปิดงานแก้ตามขอบเขตเดิม
ไม่ถือว่าการตรวจพบอนุญาตแก้ runtime หรือยกเว้นให้อัตโนมัติ.

กรณีตรวจรับที่ต้องเพิ่มภายหลัง: main มี High → PR แก้ → candidate ผ่าน;
PR ไม่แก้ High เดิม → ไม่ผ่าน; SHA เปลี่ยน → ผลเก่าไม่ใช้ปิด gate.

## R2 — Medium: ไม่มีผลลัพธ์ที่ชัดเจนสำหรับ secret จริงที่ revoke แล้ว

ตำแหน่ง: `requirements.md` RQ-2, RQ-3, RQ-6, RQ-7

RQ-2 ตรวจประวัติ Git และ RQ-6 ระบุทางพ้น blocker เฉพาะ fixture/false positive.
secret จริงที่อยู่ใน commit เก่าและถูก revoke แล้วไม่ใช่ทั้งสองประเภท และการลบจาก
ไฟล์ปัจจุบันไม่ได้ลบจากประวัติ. RQ-7 อนุญาต exceptions แบบทั่วไป แต่ยังไม่ระบุว่า
การ remediation ที่พิสูจน์แล้วต้องปิด finding อย่างไร จึงเสี่ยงบล็อกซ้ำไม่สิ้นสุด
หรือปิดเป็น false positive ทั้งที่เคยรั่วจริง.

ข้อเสนอ: เพิ่มสถานะ remediated/revoked ที่เจ้าของรับรองด้วยหลักฐานไม่เปิดเผยค่า;
อนุญาตปิด blocker ของ occurrence ในประวัติที่ระบุแน่นอน พร้อมเก็บเหตุการณ์เดิมตามจริง.
ห้าม blanket allowlist ค่า secret, ห้ามยกเว้นการเพิ่ม secret ซ้ำใน commit ใหม่ และห้าม
ถือว่าการอนุมัติ security CI อนุญาต rotate/revoke หรือ rewrite Git history โดยอัตโนมัติ.
GitHub รองรับ resolution `revoked` แยกจาก `false_positive` และ `used_in_tests` อยู่แล้ว.

กรณีตรวจรับที่ต้องเพิ่มภายหลัง: historical finding ที่ยืนยัน revoke แล้วไม่บล็อกซ้ำ;
finding ที่ไม่มีหลักฐาน remediation และ occurrence ใหม่ยังบล็อก.

## R3 — Medium: High/Critical ยังไม่มีแหล่ง severity และเกณฑ์เมื่อข้อมูลขาด

ตำแหน่ง: `requirements.md` RQ-4, RQ-6, RQ-7

เอกสารไม่ได้ระบุว่าตัดสิน High/Critical จากฐาน advisory หรือ severity field ใด
และจะทำอย่างไรเมื่อ scanner พบ vulnerability แต่ให้ severity ไม่ได้หรือข้อมูลขัดกัน.
การสแกนสำเร็จแต่ severity หายไม่เหมือน scan ล้มเหลว; RQ-7 จึงยังไม่กำหนดผลกรณีนี้
อย่างชัดเจน. ผู้ implement อาจปล่อยผ่าน findings ที่จัดระดับไม่ได้ หรือเลือก severity
ต่างกันจนเกณฑ์เดียวกันให้ผลไม่เหมือนกัน.

ข้อเสนอ: ใน plan ต้องระบุแหล่งและ mapping ที่แน่นอนต่อ scanner พร้อมหลักฐาน advisory;
requirements กำหนดให้ severity ที่ไม่ทราบ/อ่านไม่ได้หรือขัดกันจนยังตัดสินไม่ได้
เป็น Needs Triage และไม่ผ่าน gate จนจัดระดับหรือมี exception ที่เจ้าของอนุมัติ.
ห้ามแปลงเป็น Low หรือข้ามเพราะ field ไม่มี และต้องแยก CodeQL security severity
ออกจากระดับ error/warning ของผลวิเคราะห์ทั่วไป.

กรณีตรวจรับที่ต้องเพิ่มภายหลัง: High/Critical บล็อก, Low/Medium รายงาน,
missing/invalid severity ไม่ผ่านเงียบ ๆ และ advisory mapping ให้ผลที่ตรวจย้อนกลับได้.

## ผลกระทบและขั้นถัดไป

เจ้าของสั่ง “แก้ไข” ตามข้อเสนอทั้งสามเมื่อ 2026-11-05.
แก้ RQ-3/4/6/7/8/11 และเพิ่มรายละเอียดหัวข้อ 6.1–6.3 แล้ว;
NC-SEC-CI-01..03 ใน `specs/mission.md` §9 ปิดตามคำตัดสินนี้.
เจ้าของอนุมัติ requirements ทั้งฉบับ 2026-11-05 แล้ว; จัดทำ plan/validation ต่อ
โดยเอกสารทั้งสองยังต้องได้รับอนุมัติก่อน implementation.
ไม่เปลี่ยน application, workflows, GitHub settings หรือ permission และไม่ commit/push.
ตรวจเฉพาะความสอดคล้องของเอกสาร/ลิงก์/whitespace ไม่รัน runtime tests.

## ตรวจผลการแก้ R1–R3

| Finding | ส่วนที่แก้ใน requirements | ผลตรวจเอกสาร |
|---|---|---|
| R1 | RQ-4/6/8/11 และ §6.1 | ครอบคลุม full candidate, head/base หรือ merge SHA, ผลเก่าหมดอายุเมื่อ candidate เปลี่ยน, PR แก้แล้วไม่ถูกบล็อกด้วยสถานะ main และคง blocker ที่ยังเหลือจริง |
| R2 | RQ-3/6 และ §6.2 | เพิ่ม remediated/revoked พร้อมหลักฐานว่า credential เดิมใช้ไม่ได้; จำกัด occurrence, คงประวัติจริง, ไม่ยกเว้น occurrence ใหม่ และไม่อนุญาต revoke/rotate/rewrite history อัตโนมัติ |
| R3 | RQ-6/7/11 และ §6.3 | กำหนด mapping/แหล่งใน plan, แยก security severity, missing/invalid/conflicting severity เป็น Needs Triage ไม่ผ่านเงียบ ๆ และมีเงื่อนไขปลด blocker |

ผลนี้ยืนยันว่าข้อความแก้ครอบคลุม findings ที่รีวิว ไม่ใช่ผล runtime validation;
กรณีตรวจรับที่ระบุใน R1–R3 ลงใน `validation.md` V-02/V-05/V-07/V-09/V-10 แล้ว;
ยังไม่ใช่ผลทดสอบ scanners หรือ runtime.

## แหล่งอ้างอิง

- [GitHub: code scanning alerts in PRs](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-code-scanning-alerts/triage-alerts-in-pull-requests) — แยก branch alerts, default-branch status และผลของ PR
- [GitHub: dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review) — ตรวจการเปลี่ยน dependency ของ PR
- [GitHub: secret scanning API](https://docs.github.com/en/rest/secret-scanning/secret-scanning) — resolution `revoked` มีแยกจาก false positive/test fixture
- [GitHub: code scanning merge protection](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/manage-your-configuration/set-merge-protection) — แยก alerts และ security-alert thresholds
