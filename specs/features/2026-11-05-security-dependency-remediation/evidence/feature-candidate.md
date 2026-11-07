# Dependency remediation — Feature candidate evidence

วันที่: 2026-11-05
สถานะ: **Completed — review, Feature validation และ post-merge checkpoint ผ่าน**
Branch: `feature/security-dependency-remediation`
Base: `c8d8ca78971fce3d98f624e0c35128195168d831`
Implementation เป็น uncommitted working-tree changes; ไม่มี PR/merge SHA/CI run ของงานนี้.

## Scope

- `backend/uv.lock`: certifi 2026.7.22 → 2026.10.18 พร้อม release artifacts/hash metadata.
- `frontend/package-lock.json`: node_modules/vite 6.4.3 → 6.4.4 พร้อม resolved URL/integrity.
- Semantic diff พิสูจน์ว่าไม่มี package อื่นเปลี่ยน; pyproject.toml/package.json ไม่เปลี่ยน.
- uv resolver รุ่น 0.13.5 เสนอ revision 3 → 5 ใน temporary copy; นำเฉพาะ generated certifi
  stanza กลับมาเพื่อรักษา lock format เดิม. Frozen sync และ uv lock --check ยืนยันใช้ได้.
- npm resolver ใน temporary copy เปลี่ยน root Vite constraint ชั่วคราว; นำกลับเฉพาะ target
  package entry และรักษา original root metadata/range. npm ci ยืนยัน consistency.
- ไม่มี application, TLS-policy, session/storage/DB, migration หรือ financial/trading code changes.

## Local validation results

| Check | Result |
|---|---|
| Python / Node / package tools | Python 3.12.15, Node 22.23.4, npm 10.9.9, uv 0.13.5 |
| backend frozen install / lock check | uv sync --frozen --all-groups --project backend; uv lock --check --project backend ผ่าน; installed certifi 2026.10.18 |
| frontend clean install | npm ci --no-audit --no-fund ผ่าน; installed vite 6.4.4 |
| Targeted backend safety/callers | 156 tests ผ่าน |
| TLS probe | certifi bundle โหลดได้, CERT_REQUIRED/hostname check เปิด; real self-signed loopback handshake ถูก HTTPX 0.28.1 ปฏิเสธ |
| Frontend build | Vite 6.4.4 build ผ่าน, 214 modules |
| Selected frontend tests | 3 test files / 10 tests ผ่าน |
| Dev/preview smoke | Loopback dev HTML/module transform ผ่าน; preview HTML + 2 assets โหลดสำเร็จ; servers ปิดแล้ว |
| OSV 2.7.0 full inventory | 464 package-version entries ครบ; 0 High/Critical/Unknown; target advisories/aliases ไม่เหลือ |
| Remaining advisories | Medium 4 records ตาม osv-candidate.json; ไม่มี exception/auto-ignore |
| Scope/fingerprints | manifests unchanged; final lock hashes ตรงตอน OSV scan; git diff --check ผ่าน |

Build มี existing-style chunk-size warning >500 kB; ไม่ใช่ build failure และไม่ขยาย scope
ไปทำ UI/code splitting. npm แสดง dependency deprecation warnings; ไม่อัปเกรดนอกสอง targets.
Windows exploit ไม่ได้ reproduce; ใช้ patched version/vendor advisory และ scanner proof
ตาม plan. TLS probe ใช้ temporary self-signed material บน loopback ไม่มี exchange calls.

## Commands and artifacts

Backend:

```sh
uv sync --frozen --all-groups --project backend
uv lock --check --project backend
cd backend
.venv/bin/python -m pytest tests/venues/binance_th/test_failures.py tests/venues/binance_th/test_error_changes.py tests/venues/binance_th/test_wallets.py tests/test_api_key_safety.py tests/gates/test_paper_isolation.py -q
```

Frontend:

```sh
npm ci --no-audit --no-fund
npm run build
npm test -- tests/gates/api-contract.test.ts tests/AccountSession.test.tsx tests/ManualOrderForm.test.tsx
```

Dev/preview ใช้ npm scripts พร้อม --host 127.0.0.1 --port <ephemeral> --strictPort.
TLS probe สร้าง RSA/self-signed localhost certificate ชั่วคราวด้วย cryptography ที่มีอยู่;
HTTPX trust_env=False ใช้ default verification ปฏิเสธ certificate ที่ไม่ได้ trust.
Probe ตรวจ CA context กับ certifi bundle จริงและไม่เก็บ private material.

- [candidate-integrity.json](candidate-integrity.json): base, final fingerprints และ scope checks.
- [osv-candidate.json](osv-candidate.json): full inventory counts, remaining advisory IDs,
  lock hashes และ sidecar policy/config digest จาก Security CI worktree.
- [tls-probe.json](tls-probe.json): SSL settings และ actual loopback rejection.
- [vite-loopback.json](vite-loopback.json): version, HTML/transform/assets proof.
- [before-locks.json](before-locks.json): pre-change manifest/lock fingerprints.

## Remaining gates / next step

Code review APPROVED ตาม code-review.md; งานไม่มี source change จึงข้าม refactor ตามกฎเจ้าของ.
Required CI บน final PR candidate ยังรอรัน.
DV-08/09 ยัง Partial/Not Run; DV-10 Not Run — Pending Full Validation.
ไม่ใช้ผล local แทน required CI. ไม่มี commit/push/PR/merge/settings changes.

เจ้าของอนุญาต commit/push/PR แล้ว; ติดตาม required CI บน SHA ล่าสุดจนจบ.
ไม่มี merge authorization. Local evidence ข้างบนเป็น snapshot ก่อน commit;
final candidate SHA และ CI URLs รายงานใน PR/checkpoint โดยไม่สร้าง evidence-commit loop.
หลัง merge เมื่อมีคำสั่ง จึงส่ง target lockfiles ให้ Security CI integration และ rerun
security checks บน candidate ใหม่; local remediation นี้ไม่ได้ปิด CI activation checkpoint.

## Final checkpoint

ข้อมูลก่อน commit ด้านบนเป็น historical snapshot. PR #47 merge แล้วที่ a3a8652;
required CI ก่อน/หลัง merge ผ่านครบ. ดู [post-merge.md](post-merge.md) สำหรับผลสุดท้าย
และขอบเขต handoff ที่ยังไม่ใช่การปิดงาน Security CI.
