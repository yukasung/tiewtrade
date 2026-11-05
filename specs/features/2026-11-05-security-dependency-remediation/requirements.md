# Security dependency remediation — Requirements

สถานะ: **Approved — เจ้าของตอบ approve ให้ requirements ฉบับนี้ 2026-11-05**
วันที่: 2026-11-05
Branch: `feature/security-dependency-remediation`
ฐานเริ่มต้น: `c8d8ca78971fce3d98f624e0c35128195168d831`

## ทำไมต้องมี

Security CI ตรวจ lockfiles พบ High/Critical ที่ไม่อยู่ในขอบเขตแก้ application/dependencies
ของงาน CI เดิม. เจ้าของตอบ `approve` ให้เริ่มจัดทำ requirements ของงานแยกนี้
พร้อมอนุมัติ secret exceptions ในงาน CI; ยังไม่ใช่การอนุมัติ implementation งานนี้.

| Package | Locked version | Target version | Finding |
|---|---|---|---|
| certifi (PyPI) | 2026.7.22 | 2026.10.18 | GHSA-6q48-6c7w-9gw2 / PYSEC-2026-4320 |
| vite (npm) | 6.4.3 | 6.4.4 | GHSA-587h-7wmj-h5pm |

certifi เป็น transitive dependency ของ httpcore/httpx. Vite เป็น frontend dev dependency;
manifest ปัจจุบัน `^6.0.3` รองรับ target patch อยู่แล้ว. ยืนยัน target releases มีใน
PyPI/npm registry เมื่อ 2026-11-05. ไม่จำเป็นต้องข้าม Vite major.

## ขอบเขต

- อัปเดต dependencies สองรายการและ lockfile metadata ที่จำเป็นต่อการ resolve/install.
- ตรวจผลต่อ HTTP/TLS callers และ frontend build/dev-toolchain โดยไม่ใช้ exchange credentials.
- ยืนยัน findings เป้าหมายหายจากผล scanner ของ candidate จริง และคง security gates.

ไม่รวม application refactor, TLS-policy changes, CA customization, dependency upgrades
อื่นที่ไม่จำเป็น, scanner/policy/exception changes, GitHub settings, secret rotation,
production deployment หรือการเปลี่ยน trading behavior.

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| DR-1 | เปลี่ยน certifi เป็น 2026.10.18 และ Vite 6.4.3 occurrence เป็น 6.4.4 ใน application lockfiles; ไม่เพิ่ม direct dependency โดยไม่มีเหตุผลและไม่เปลี่ยน package ranges ที่รองรับ target อยู่แล้ว | ข้อเสนอที่เจ้าของอนุญาตให้จัดทำ requirements |
| DR-2 | ติดตั้งจาก lockfiles แบบ frozen/clean ได้บน environment ตาม tech stack; lock metadata/integrity สอดคล้องกับ manifest; หาก resolver ต้องเปลี่ยน package อื่น ให้แสดง dependency reason และหยุดขออนุมัติขอบเขตเพิ่มก่อนแก้ | reproducibility; AGENTS.md ขอบเขตหนึ่งงาน |
| DR-3 | สแกน backend/uv.lock และ frontend/package-lock.json ครบ candidate รวม direct/dev/transitive/optional; findings เป้าหมายต้องไม่เหลือ ไม่ใช้ alert state บน main หรือ diff-only scan แทน; ห้ามสร้าง exception เพื่อปล่อย findings เป้าหมาย | Security CI requirements §6.1/§6.3 |
| DR-4 | ตรวจพบ High/Critical หรือ unknown ใหม่ให้คง blocker และรายงาน; ไม่ขยายเป็น broad upgrade, auto-ignore หรืออ้างว่า scanner ผ่านแล้วไม่มีช่องโหว่ทุกชนิด | Security CI RQ-6/7 |
| DR-5 | คง certificate verification และ security defaults ของ HTTP clients; CA bundle เปลี่ยนตาม certifi release เท่านั้น ไม่แก้ application เพื่อปิด verification/เชื่อถือ CA เพิ่ม; tests ที่เกี่ยวข้องกับ HTTP/TLS และ frontend build/toolchain ต้องผ่าน | standards/security.md; advisory remediation |
| DR-6 | ไม่เปลี่ยน sessions/PostgreSQL persistence, migrations, transaction/locking/idempotency, order quantity, balance/position, PnL, leverage/margin/liquidation หรือ Paper/Live isolation; ไม่ใช้ live credentials/ไม่ส่ง Live orders ระหว่าง validation | AGENTS.md; trading-safety.md |
| DR-7 | ก่อน merge ต้องผ่าน review, Feature validation และ required CI บน final candidate; ระบุ SHA/lock fingerprints/tool versions/run URLs และผลจริง แยก local evidence จาก CI; commit/push/PR/merge ต้องมีคำสั่งเจ้าของ | standards/testing.md §6–7; AGENTS.md Git |

## กฎความปลอดภัยและสถาปัตยกรรม

ยึด specs/tech-stack.md, specs/standards/architecture.md, security.md,
trading-safety.md และ testing.md. ไม่มี storage/session architecture ใหม่.
Tests แบบ mock ไม่ถูกใช้เป็นหลักฐานด้าน network/DB correctness ที่มันพิสูจน์ไม่ได้;
เลือก targeted validation ตาม diff/callers จริงในขั้น plan โดยไม่รัน live exchange calls.

## ยังไม่ชัด / Dependencies

- ไม่มี business/trading decision ที่ต้องเพิ่มสำหรับขอบเขตสอง package นี้.
- หาก target versions ใช้ร่วมกับ stack เดิมไม่ได้ หรือ resolver ต้องขยาย scope ให้หยุด
  ขอกำหนดใหม่ ไม่เลี่ยงด้วยลด TLS safety หรือยกเว้น scanner finding.
- Branch นี้แยกจาก Security CI ที่ยังไม่ commit/merge. ขั้น plan ต้องกำหนดการใช้
  scanner evidence และลำดับ candidate integration ให้ชัด; ไม่ถือว่า CI workflow เปิดใช้แล้ว.
- Requirements ได้รับอนุมัติแล้ว; ขั้นถัดไปคือ plan.md + validation.md → owner approval
  → implementation. ยังไม่แก้ lockfiles ก่อนอนุมัติเอกสารทั้งสอง.

## แหล่งอ้างอิง

- [certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)
- [launch-editor / Vite advisory](https://github.com/vitejs/launch-editor/security/advisories/GHSA-587h-7wmj-h5pm)
- [certifi target release](https://pypi.org/project/certifi/2026.10.18/)
- [Vite target release](https://www.npmjs.com/package/vite/v/6.4.4)
