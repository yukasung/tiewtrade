# Security dependency remediation — Plan

สถานะ: **Approved — เจ้าของตอบ approve ให้ plan/validation ทั้งสองฉบับ 2026-11-05**
วันที่: 2026-11-05
Requirements: [Approved](requirements.md)
Branch: `feature/security-dependency-remediation`

## 1. แนวทาง

เปลี่ยนเฉพาะ locked certifi 2026.7.22 → 2026.10.18 และ Vite 6.4.3 → 6.4.4.
รักษา dependency constraints, application code, TLS verification และ workflow เดิม.
ทำ resolution ใน temporary copy ก่อนย้าย lockfile ที่ตรวจ scope แล้วเข้า branch.
ไม่ยกเว้น findings เป้าหมายและไม่ถือว่า Linux runner ทำให้ Windows advisory ผ่านเอง.

## 2. ของเดิมที่จะใช้ซ้ำ

| ของเดิม | ใช้เพื่อ |
|---|---|
| `backend/pyproject.toml`, `backend/uv.lock` | constraints/Python 3.12 และ frozen backend installation |
| `frontend/package.json`, `frontend/package-lock.json` | Node 22/npm scripts, Vite range เดิม `^6.0.3` และ clean install |
| `backend/src/tiewtrade/venues/binance_th/transport.py` | ตรวจ HTTP client construction และ verification defaults โดยไม่แก้ production code |
| `backend/tests/venues/binance_th/test_failures.py`, `test_error_changes.py`, `test_wallets.py` | error mapping/retry boundary, redaction และ signed-request callers ผ่าน mocks; ไม่อ้างว่า mock พิสูจน์ TLS |
| `backend/tests/test_api_key_safety.py`, `backend/tests/gates/test_paper_isolation.py` | safety boundaries ที่ห้ามเปิด live network/credential access ผิดชั้น |
| `frontend/tests/gates/api-contract.test.ts`, `frontend/tests/AccountSession.test.tsx`, `frontend/tests/ManualOrderForm.test.tsx` | consumer/toolchain smoke ด้วย Vitest; ไม่รัน UI regression ทั้งชุดโดยไม่มีผลกระทบ |
| `frontend/vite.config.ts`, npm `build`/`dev`/`preview` scripts | ตรวจ actual Vite transform/build/serve; ไม่แก้ UI/template |
| Security CI worktree `tools/security/scan.py`, `dependencies.py`, `model.py`, `.github/security/` | pinned OSV, full inventory comparison และ severity policy ใช้เป็น read-only sidecar ไม่คัดลอก helper ลง branch นี้ |
| `.github/workflows/ci.yml` | required CI เดิมบน final PR candidate; ไม่แก้/ลด checks |

## 3. ขั้นตอน implementation หลังอนุมัติ

1. บันทึก base/head, Python/Node/uv/npm versions, SHA256 ของ manifest/lockfiles และ
   inventory ก่อนแก้. ยืนยัน target versions และ affected/fixed ranges จาก advisory/registry.
2. Backend: targeted uv lock update ที่ constrain เฉพาะ certifi เป็น target exact version
   ใน temporary copy; ห้ามเพิ่ม certifi เป็น direct dependency. ตรวจ semantic package diff
   ก่อนนำกลับ: เปลี่ยนได้เฉพาะ certifi version/artifact URL/hash/metadata ของ release ใหม่.
3. Frontend: resolve target Vite patch ใน temporary copy โดยรักษา package manifest เดิม.
   ถ้าต้อง constrain exact target ชั่วคราวใน sandbox ให้คืน root package constraint
   เป็น `^6.0.3` ก่อนตรวจ lock consistency. ไม่คัดลอก temporary manifest เข้างานจริง.
   ตรวจทุก installed occurrence และ package/integrity diff; Vite version อื่นที่ไม่ใช่
   6.4.3 occurrence ไม่เปลี่ยนตามไปโดยไม่มีเหตุผล.
4. ถ้า resolver ต้องเปลี่ยน package อื่น หรือ frozen install ไม่สอดคล้องกับ manifest เดิม
   ให้หยุดพร้อม dependency chain/diff ขออนุมัติเพิ่มก่อนนำผลมาใช้ ตาม DR-2.
   ไม่แก้ hashes ด้วยค่าที่เดา ไม่ลด integrity checks.
5. ใช้ isolated dependency environments ของ worktree นี้: backend frozen sync/check;
   frontend `npm ci` ด้วย Node 22. ไม่ใช้ .venv/node_modules ที่ยังเป็น versions เก่าเป็นหลักฐาน.
   Pin/version tools ตาม repo CI/lock ที่มีอยู่ ไม่เพิ่ม package manager ใหม่.
6. ตรวจ targeted tests และ scanners ตาม validation.md. เก็บ safe results, inventory,
   changed package list, lock fingerprints และ tool/config digests; ไม่เก็บ credentials.
7. โค้ดครบและ checks ผ่านให้แจ้ง **Ready for Code Review** แล้วหยุดรอ `review code`.
   หลัง review/fixes รอ refactor decision ตาม AGENTS; หลัง refactor ที่อนุญาตตรวจ validation ต่อ.

## 4. TLS และ frontend validation

- ยืนยัน certifi target ที่ installed จริง; CA bundle อ่านและโหลดด้วย stdlib SSL ได้;
  default verified context ยังเปิด hostname verification และ CERT_REQUIRED.
- ใช้ test harness ชั่วคราวกับ TLS server บน loopback และ certificate self-signed ที่สร้าง
  ชั่วคราว: HTTPX ต้องปฏิเสธเพราะ certificate verification. ไม่ใช้ exchange endpoint,
  production credentials หรือแก้ CA store/application verification policy.
- Existing venue mocks พิสูจน์ error/retry/redaction เท่านั้น; รายงานแยกจาก TLS probe.
- Build frontend จริงและ serve output ด้วย preview ที่ bind loopback; ตรวจ HTML/assets
  โหลดได้. Dev server bind loopback ตรวจ module transform โดยไม่เรียก launch-editor,
  shell command injection หรือโจมตีเครื่องเพื่อทดสอบ advisory.
- Vite patch fix ใช้ vendor advisory/version + scanner evidence; local smoke บน macOS/Linux
  ไม่ถูกอ้างว่าเป็นการ reproduce exploit ของ Windows. No Live orders.
- ถ้าต้องเก็บ regression test ใหม่ ให้จำกัด `backend/tests/security/` สำหรับ TLS/config
  behavior ที่ tests เดิมไม่ครอบคลุม; ไม่เพิ่ม tests ที่เพียง assert lockfile version ซ้ำ.
  Temporary TLS probes ไม่จำเป็นต้องสร้าง permanent test module หาก evidence เพียงพอ.

## 5. Scanner และการประสานสอง branches

Security CI ยัง uncommitted/ไม่เปิดใช้บน GitHub จึงห้ามอ้างว่า native gate ทำงานแล้ว.
ระหว่าง local ใช้ scanner/helper จาก sibling Security CI worktree แบบ read-only:
ส่ง dependency candidate root และ policy root แยกกัน, รัน scanner ใน temp, เปรียบเทียบ
inventory ครบทั้งสอง lockfiles, บันทึก policy/config digest กับ candidate lock hashes
ก่อนและหลัง scan. ไม่แก้ exceptions ของ dependencies.

ก่อน merge หลังได้รับคำสั่ง Git:
- Dependency PR ใช้ branch นี้เข้า main โดยผ่าน required CI ที่บังคับอยู่จริงและ Feature
  validation ของงานนี้ รวม full-candidate OSV บน final head/merge tree. ถ้า policy helper
  ยังไม่มี committed SHA ต้องบันทึก source digest และไม่เรียกว่า remote security check.
- Merge เฉพาะเจ้าของสั่ง. เมื่อ dependency fix อยู่ใน main จึง refresh Security CI branch
  เพื่อรวม lockfiles ใหม่ตามคำสั่ง Git และตรวจ security workflow ของ integration candidate.
- ไม่เปิด main security enforcement ขณะที่ยังรอ dependency fix จนทำให้ rollout ติดวงจร.
  ไม่ปิด/ลด protection เดิมเพื่อ merge; activation ของ Security CI ยังเป็นงาน CI เดิม.
- ถ้าเจ้าของเลือกเปลี่ยนลำดับ integration ให้บันทึก candidate lineage และ approval ก่อน
  ทำ Git mutation; ห้าม cherry-pick/merge/push เองจากการอนุมัติเอกสารนี้.

## 6. ขอบเขตไฟล์และเวลา

คาดแก้ `backend/uv.lock`, `frontend/package-lock.json`, feature evidence และ roadmap.
Manifest/application/CI ไม่ควรเปลี่ยน. Optional TLS test file ตามหัวข้อ 4 เท่านั้น.
ไม่มี migrations/session/storage/financial calculations หรือ architecture changes.

Local targeted checks หลังติดตั้งประมาณ 5–15 นาทีขึ้นกับ download/cache; ไม่ใช่ SLA.
ไม่เพิ่ม full trading workload, endurance หรือ cross-feature E2E ชุดใหม่.
ก่อน required CI/ชุดยาว ให้แจ้งขอบเขตและเวลาตาม standards/testing.md.

## 7. การกู้คืน

ก่อน commit ใช้สำเนา lockfiles เดิมคืนเฉพาะไฟล์งานนี้เมื่อ resolution ใช้ไม่ได้;
ไม่แตะงานใน worktree อื่น. หลัง merge หากต้องย้อน security patch ให้เจ้าของตัดสิน
พร้อมระบุว่าจะนำ vulnerability กลับมา; ไม่มี automatic downgrade/revert/deployment.
