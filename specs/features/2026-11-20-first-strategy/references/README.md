# ต้นฉบับกลยุทธ์จากเจ้าของ

เจ้าของสั่ง “ใช้กลยุทธ์นี้” วันที่ 2026-11-20 โดยระบุไฟล์จาก
`/Users/chainarongjaykeaw/Downloads/` เก็บสองไฟล์แบบ byte-for-byte เพื่ออ้างอิง
requirements ไม่ import หรือ execute เป็นส่วนหนึ่งของระบบ

| ไฟล์ | SHA-256 |
|---|---|
| strategy.py | `26ed3bd9e80be52d03b485e07a0b32da0b4d469f11024c7f9663fdea6dd42808` |
| preset.py | `8c1a7e5833aee5ece6c5f69f4fa2902904bae96b2257dd6af3ca3260648f24fe` |

ต้นฉบับไม่ได้แนบ dependencies, sizing/execution/exit และ parameter UI มาด้วย
กฎที่อ่านได้และช่องว่างบันทึกใน [requirements](../requirements.md)
การ port ต้องใช้ F-20 contracts, Money/Quantity และ PostgreSQL state เดิม
แทน types/process memory ของต้นฉบับ โดยผ่านจุดอนุมัติ requirements/plan/validation ก่อน
