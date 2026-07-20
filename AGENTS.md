# Repository Instructions

## การสื่อสาร

- สนทนา อธิบายแผน สรุปผล และเขียน Linear Issues เป็นภาษาไทย
- ใช้ภาษาอังกฤษสำหรับชื่อไฟล์, module, class, function, variable และ code comments
- ใช้คำศัพท์ตาม `CONTEXT.md` และไม่สร้างคำใหม่ที่มีความหมายซ้ำกัน

## เอกสารที่เป็น Source of Truth

ก่อนออกแบบหรือแก้โค้ด ให้อ่านเอกสารที่เกี่ยวข้อง:

- `PRODUCT.md` — ขอบเขตผลิตภัณฑ์และสิ่งที่ไม่ทำ
- `CONTEXT.md` — คำศัพท์และกฎของโดเมน
- `ARCHITECTURE.md` — Module ownership, interfaces และ dependency rules
- `docs/adr/` — เหตุผลของการตัดสินใจด้านสถาปัตยกรรม
- `PROJECT_PLAN.md` — ลำดับการส่งมอบ

หากเอกสารขัดแย้งกัน ให้หยุดและแจ้งข้อขัดแย้งก่อน implement

## Issue Tracker

ใช้ Linear เป็น Issue Tracker หลัก:

- Workspace: `chainarong`
- Team: `Chainarong`
- Team key: `DEV`
- Project: `Tiewtrade`

GitHub ใช้เก็บ source code และ Pull Requests ไม่ใช่ Issue Tracker หลัก

ก่อนเริ่มงาน:

1. อ่าน Main Issue, Sub-issue, acceptance criteria และ blockers
2. ย้ายเฉพาะ Issue ที่กำลังทำเป็น `In Progress`
3. ใช้หนึ่ง Issue branch ต่อหนึ่ง Sub-issue
4. ย้ายเป็น `Done` หลัง implementation และ verification เสร็จจริง

## Development Workflow

- วางแผนก่อนแก้โค้ดสำหรับงานหลายขั้นตอน
- ใช้ Test-Driven Development: failing test → minimal implementation → refactor
- สร้าง Module เมื่อมีพฤติกรรมที่ต้องใช้งานจริง ไม่สร้าง empty folders ล่วงหน้า
- ไม่สร้าง generic interface, base class, registry หรือ factory ก่อนมี adapter/consumer จริงอย่างน้อยสองแบบ
- วาง interface ไว้ที่ Module ผู้ใช้งาน และให้ integrations เป็นผู้ implement
- รักษาไฟล์ให้มีความรับผิดชอบชัดเจน หลีกเลี่ยง `utils.py`, `interfaces.py`, `models.py` หรือ `repository.py` แบบรวมทุกอย่าง

## Git Workflow

- Codex สามารถสร้าง Issue branch, แก้โค้ด, ทดสอบ และ commit ได้
- ต้องรอคำยืนยันจากผู้ใช้ก่อน push ไป GitHub
- ต้องรอคำยืนยันแยกต่างหากก่อน merge เข้า `main`
- ห้าม force-push, ลบ branch/tag หรือ rewrite history เว้นแต่ผู้ใช้ระบุคำสั่งนั้นชัดเจน
- ห้ามแก้หรือลบงานของผู้ใช้ที่ไม่เกี่ยวข้องกับ Issue ปัจจุบัน

## Trading Safety

- ใช้ Paper Trading และ fake adapters ระหว่างการพัฒนาและการทดสอบ
- ห้ามส่ง Live order หรือเชื่อมบัญชีเงินจริงเพื่อทดสอบโดยไม่ได้รับคำสั่งชัดเจน
- ห้ามเก็บ API Key หรือ Secret ใน source code, configuration file, fixtures, logs หรือ SQLite
- Live credentials ต้องเก็บใน OS Keyring
- ห้ามจำลอง Live safety ด้วย Testnet; ใช้ Paper, fake transport และ contract tests
- Paper และ Live ต้องใช้ business/risk policies ร่วมกัน แต่ใช้ execution adapters คนละตัว

## Verification

ก่อนรายงานว่างานเสร็จ:

- รัน unit tests และ integration tests ที่เกี่ยวข้อง
- รัน lint/format checks ที่กำหนดใน `pyproject.toml`
- รัน smoke/acceptance tests เมื่อกระทบ application flow
- ตรวจ `git diff --check`
- สรุปสิ่งที่เปลี่ยน ผลการทดสอบ และความเสี่ยงที่ยังเหลือ
