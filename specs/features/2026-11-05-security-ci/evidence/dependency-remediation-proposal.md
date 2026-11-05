# Security CI — Dependency remediation proposal

วันที่: 2026-11-05
สถานะ: **Approved to draft requirements — ไม่ใช่ implementation approval; ไม่เปลี่ยน lockfiles**

| Package | Locked | เสนอรุ่นแก้ไข | Advisory |
|---|---|---|---|
| PyPI certifi | 2026.7.22 | 2026.10.18 | GHSA-6q48-6c7w-9gw2 / alias PYSEC-2026-4320 |
| npm vite | 6.4.3 | 6.4.4 | GHSA-587h-7wmj-h5pm |

ยืนยันรุ่นเป้าหมายมีอยู่ใน PyPI/npm registry แล้ว; certifi มี callers ใน lockfile คือ httpcore/httpx.
ตรวจ advisory response ปัจจุบันจาก OSV และเผยเฉพาะ metadata:
- [certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2): bundled emSign CA issue; affected range จบที่ 2026.10.18.
- [launch-editor/Vite advisory](https://github.com/vitejs/launch-editor/security/advisories/GHSA-587h-7wmj-h5pm): Windows existence-check bypass; Vite 6.x fixed ที่ 6.4.4.
  ไม่ยกเว้นเพราะ CI runner เป็น Linux และไม่อัปเกรดข้าม Vite major.

## ขอบเขตงานแก้ที่เสนอ

เปิดงาน dependency remediation แยกตาม requirements §6.1 และ AGENTS.md:
requirements → owner approval → plan/validation → owner approval → implementation.
ไม่ถือว่าการอนุมัติ Security CI เดิมอนุญาต runtime dependency changes.

- เปลี่ยนเฉพาะ certifi และ Vite ตามรุ่นข้างต้นพร้อม lock metadata ที่ resolver จำเป็นต้องปรับ;
  ตรวจ diff และหยุดหากต้องขยายเป็น broad upgrade หรือแก้ behavior/application code.
- คง frontend manifest range เดิมหาก lock update อยู่ใน range; ไม่เปลี่ยน TLS verification,
  trusted CA policy เอง หรือ bypass Windows issue.
- ตรวจ OSV ครบสอง lockfiles ใหม่, frozen install/lock consistency, targeted HTTP/TLS callers
  และ frontend build/dev-toolchain tests ที่ได้รับผลกระทบ พร้อม required CI บน final candidate.
- ไม่ใช้ live exchange credentials/ไม่ส่ง Live orders. ไม่แก้ finding ด้วย exception อัตโนมัติ.

เจ้าของตอบ approve ให้จัดทำ requirements แล้ว; ร่างอยู่ใน worktree TiewTrade-security-dependencies, branch feature/security-dependency-remediation และรอ requirements approval.
