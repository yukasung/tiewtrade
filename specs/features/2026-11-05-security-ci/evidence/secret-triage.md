# Security CI — Secret triage proposal

วันที่: 2026-11-05
สถานะ: **Approved — เจ้าของตอบ approve แล้ว; exact exceptions นำเข้า registry แล้ว**

คำอนุมัติและขอบเขต: [exception-approval.md](exception-approval.md).
ข้อความข้อเสนอด้านล่างคงไว้เพื่ออ้างอิงสิ่งที่เจ้าของอนุมัติ.

ตรวจ 92 unique identities จาก local-origin-scan.json โดยอ่าน source ที่ commit/path/line
ของ finding แต่ละรายการ ไม่ใช้ current file มาแทน historical source และไม่ใช้ credential.
หลักฐานนี้ครอบคลุม origin refs snapshot เดิม 246 commits เท่านั้น.

| ประเภท | จำนวน | ข้อเสนอ |
|---|---:|---|
| Source-file hash manifests | 61 | false_positive |
| Docker container IDs | 4 | false_positive |
| Docker container-name replacement | 1 | false_positive |
| Documentation prose / host measurements | 4 | false_positive |
| Public development/CI sealing-key fixtures | 12 | used_in_tests — ต้องรับรองว่าไม่ได้ใช้เป็น key จริง |
| Historical local profiling claim UUIDs | 9 | used_in_tests — ต้องรับรอง test-only provenance |
| PRETEND_SECRET ใน redaction test | 1 | used_in_tests |
| รวม | 92 | 70 false_positive + 22 used_in_tests |

## หลักฐานเฉพาะกลุ่ม

- Hash manifests: ทุก finding เป็น digest 64 hex ที่ผูก source path ใน source-hashes.json
  หรือ chart-enable-snapshot.json. ทดลองเทียบกับ blob ที่ finding commit พบตรง 1/61;
  อีก 60 เป็นคนละ source snapshot จึง **ไม่อ้างว่าได้ยืนยัน digest ตรงทั้งหมด**.
  การจัดประเภทอาศัยโครงสร้าง manifest และชนิดข้อมูล ไม่ใช่การเดาจาก entropy อย่างเดียว.
- Container IDs อยู่ใต้ runtime_containers_created ใน capacity environment snapshots.
- run_smoke.py เป็น Docker argument replacement; literal ต้นทางเป็นตัวแปร container
  ใน backend/tests/services/indicator_builder/profile_capacity_steady.py:152 ที่ commit เดียวกัน.
- Claim UUIDs อยู่ใน n4 profiling snapshots; migration 0016_indicator_build_claims.py
  และ infra/indicators/claims.py ใช้ claim_token เป็น DB lease/fencing UUID.
- Public sealing fixtures มีคำอธิบายใน CI/compose/README ว่าใช้พัฒนา/ทดสอบ.
  Source เพียงอย่างเดียวพิสูจน์ไม่ได้ว่าไม่มีใครนำไปใช้ production; ต้องให้เจ้าของรับรอง.
- PRETEND_SECRET มี comment และ callers ใน test_failures.py ที่ทดสอบการปิดค่าใน errors/logs.

รายการราย identity/commit/path/line พร้อมเหตุผล:
[proposed-secret-exceptions.json](proposed-secret-exceptions.json).
ไฟล์ใช้ proposal schema และ approval=null จึงนำไปอ่านเป็น active registry ไม่ได้.
ไม่มี Match/Secret/source snippets หรือค่า credential ในหลักฐานที่เผยแพร่.

## การตัดสินที่ต้องการ

อนุมัติ exact 70 false positives และ 22 test/development fixtures ตามรายการนี้ โดยรับรอง
ว่า public sealing fixtures ไม่ถูกใช้ในระบบจริงและ profiling IDs เป็นข้อมูลทดสอบเท่านั้น.
หากรับรองบางรายการไม่ได้ ให้คงรายการนั้น Needs Triage ไม่สร้าง revoked exception
โดยไม่มีหลักฐาน และไม่ทดลองใช้ key ติดต่อ provider.

หลังอนุมัติจึงนำเฉพาะ identities ที่อนุมัติเข้า .github/security/exceptions.json พร้อม
approval/evidence reference แล้วตรวจ gate อีกครั้ง. ไม่ยกเว้น rule/directory/value กว้าง;
new occurrence/rename/reintroduced credential ยังต้องถูกบล็อกตาม regression tests.

ข้อจำกัด: ไม่มีการรับรองว่า repo ไม่มี secret ทุกชนิด; final candidate/remote scan ยังต้องผ่าน.
