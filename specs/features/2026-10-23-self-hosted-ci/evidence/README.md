# Self-hosted CI evidence

แนวทางนี้ retired แล้ว: อ่าน [closure-checkpoint.md](closure-checkpoint.md) สำหรับผล
hosted CI attempt 3 และ PR scope; [cleanup-checkpoint.md](cleanup-checkpoint.md)
ระบุสิ่งที่ลบและสิ่งที่ยังเหลือ. เอกสารอื่นเป็นหลักฐานตามเวลาที่ทดลอง ไม่ใช่สถานะปัจจุบัน.

Bounded PF identity proof ใช้ synthetic localhost listeners เท่านั้น ไม่ใช่ guest isolation
acceptance หรือ GitHub CI. เก็บผล before/after และ scoped counters; ไม่เก็บ registration
tokens, credentials หรือ production data. อ่านผลทั้งหมดก่อนสรุป NI-01..07.

- `pf-identity-probe.json`: completed synthetic host TCP proof + rollback เท่านั้น.
- `proof-identity.json`: manifest ของบัญชีทดลอง disabled-login/non-admin ที่สร้างเอง;
  ใช้ GUID จาก Directory Services ไม่ใช่ generated identity ที่เขียนทับ system attributes.
- `vm-policy-boot.json`: bounded boot-smoke journal; ต้องอ่าน `status` และ `cleanup`
  ไม่ถือว่าไฟล์มีอยู่แปลว่าผ่าน. ระหว่างทำงานอาจมี PF reference สำหรับ reconciliation;
  ไม่ใช่ runner/GitHub credential และห้ามใช้ไฟล์นี้แทน NI-02/03/06 acceptance.
- `vm-policy-recovery.json`: confirmed Stopped ก่อนคืน owned root hook/rules/reference;
  อ่านควบคู่ original failure journal และ `vm-policy-diagnostic.md` ไม่แทน failure ด้วย Passed.
