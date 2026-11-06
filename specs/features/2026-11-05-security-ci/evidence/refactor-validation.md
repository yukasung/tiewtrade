# Security CI — Refactor and validation

วันที่: 2026-11-05
สถานะ: Refactor complete; local tests/static checks passed; security policy Blocked; Feature validation Partial

เจ้าของสั่ง `refactor the code`; จำกัดงานที่ helpers เดิม ไม่เปลี่ยน policy/spec หรือ workflow.

- `severity.py`: แยก metric schemas ออกจาก validation loop; ใช้ชุดค่ารูปแบบเดียว
  ทั้ง single-letter และ word metrics ลดเงื่อนไขแยก v3/v4 และไม่สร้างตารางใหม่ทุก advisory.
- `dependencies.py`: แยก group severity decision ออกจากการตรวจ inventory/group identities
  ทำให้ตรวจหลัก fail closed ของทุก advisory ได้ในฟังก์ชันเดียว.
- ไม่เพิ่ม dependencies, infrastructure หรือ application/session/trading state.

## ผลตรวจหลัง refactor

- 28 tests ผ่าน รวม real Gitleaks rename/move-back/deleted-occurrence และ OSV probes.
- Differential check เปรียบเทียบ validator ก่อน/หลัง refactor 998 กรณี: ผลเหมือนกันทุกกรณี.
  ครอบคลุม supported versions, allowed/invalid metric values และ duplicate metrics.
- Ruff check/format, mypy strict, actionlint และ git diff --check ผ่าน.
- Configuration digest ล่าสุด: `6dc909f41f5837ec6d5c4fb17520b8084d963b4c259cc66105ac9aaa65459439`.
- หลักฐานก่อนหน้าใน feature-candidate.md/review-fixes.md เป็น historical snapshots;
  ใช้ digest นี้กับ implementation หลัง refactor. ไม่มี final commit/PR/CI SHA.

## Validation ที่ยังค้าง

CodeQL จริงทั้งสามภาษา, remote fork/PR/merge blocking, required CI, native settings และ
activation ยังไม่รัน; V-19 ยังคง Not Run — Pending Full Validation.
Dependency blockers ใน certifi/vite ไม่ได้รับการยกเว้นหรือแก้โดย refactor นี้.
ไม่มี commit/push/PR/settings changes หรือการส่ง Live order.

## Local origin-history validation

ผล scanner ทำงานสำเร็จ: 246 commits จาก origin refs ที่มีในเครื่อง พร้อม committed base tree.
พบ 92 unique findings (generic-api-key 80, tiewtrade-sealing-key 12); policy **Blocked**.
ยังไม่ถือว่าเป็น secrets จริง 92 รายการ: ต้อง triage ตามตำแหน่งและหลักฐานเจ้าของ
ไม่ใช้ credential ไม่ rotate/revoke และไม่เพิ่ม exception อัตโนมัติ.

หลักฐานปิดค่า: [local-origin-scan.json](local-origin-scan.json) มี refs/SHAs, identities,
rule/path/line และ counts เท่านั้น ไม่มี Match/Secret/source snippets.
ใช้ disposable Git repo เพื่อไม่เปลี่ยน refs/index/worktree ของผู้ใช้.

ข้อจำกัด: refs เป็น snapshot ที่ fetch ไว้ในเครื่อง ไม่ได้ refresh จาก origin ในรอบนี้;
ไม่ครอบคลุม deleted/unreachable refs. Tree คือ base SHA ไม่รวม implementation ที่ยัง uncommitted.
V-03 จึงยัง Partial และต้องตรวจ candidate/fetched origin ล่าสุดในรอบ Git ที่อนุญาต.

ขั้นถัดไป: triage 92 secret findings และ dependency blockers; remote validation/activation
ต้องรอคำสั่ง commit/push/PR ตาม AGENTS.md. ยังไม่พร้อม merge/Completed.
