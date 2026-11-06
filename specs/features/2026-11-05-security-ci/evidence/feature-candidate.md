# Security CI — Implementation evidence

Latest owner evidence (2026-11-06): V-01 closed using the observed zero budgets and
Usage blocked state plus bounded storage evidence. V-01..18 passed for unchanged
head 34c146a/base 98ff2f8. See billing-budget-verification-20261106.md. Await owner
merge command; V-19 remains Not Run — Pending Full Validation. Older pending notes
below describe historical checkpoints.


Current checkpoint (2026-11-06): [rollout validation](rollout-20261106.md).
Feature head 34c146a/base 98ff2f8 passed Security and both ordinary CI runs. Native
settings and required Security gate are activated; real negative merge rejection is
recorded. Latest fixed/retention validation PR #49 head 5054226 passed Security;
ordinary final CI passed 6/6 each and PR #49 was closed without merging after CLEAN
mergeability proof. Only V-01 account storage/budget evidence remains for Feature acceptance;
V-19 remains after owner-authorized merge.


Latest remote candidate: see [compatibility decision result](compatibility-decision.md)
and [safe manifests](remote-candidate-manifests.json). The local evidence below is
historical; its old uncommitted/no-PR and dependency-blocker statements do not describe
the current PR #48. Native activation/rejection proof and final acceptance remain open.
Fork execution is Not Run: the owner has no second account/organization. The
[replacement-validation amendment](fork-validation-amendment-proposal.md) was approved
and applied to the three specification files on 2026-11-05. V-12 remains Partial
until the replacement evidence passes; real fork behavior remains an accepted evidence gap.

## Historical local checkpoint

สถานะ: **Review findings แก้แล้ว; refactor/local checks ผ่าน; Feature validation Partial**

วันที่บันทึก: 2026-11-05T13:32:38.809188+00:00
Branch: `feature/security-ci-hardening`; checkout/base SHA: `c8d8ca78971fce3d98f624e0c35128195168d831`.
Implementation ยังเป็น uncommitted working-tree changes; ไม่มี PR/head/merge candidate หรือ CI run ของงานนี้.
ไม่ใช้ผล local แทน required CI และไม่ประกาศ Completed/พร้อม merge.

## Local checks

- Python 3.12 stdlib unittest: **25 passed**, รวม real Gitleaks/OSV probes; ไม่มี skipped เมื่อเปิด `SECURITY_SCANNER_PROBES`. หลังเพิ่ม sealing-key positive fixture รัน secret probe ซ้ำผ่าน.
- Ruff 0.16.9 check/format และ mypy 2.3.1 strict: ผ่านเฉพาะ `tools/security`.
- actionlint v1.7.7: `.github/workflows/security.yml` ผ่าน.
- เครื่องมือ Gitleaks 8.30.1, OSV 2.7.0 และ actionlint 1.7.7 ดาวน์โหลดจาก release ที่ pin และตรวจ SHA256 ก่อนใช้; checksum mismatch test ปฏิเสธ binary ที่เปลี่ยน.
- `git diff --check`: ผ่าน; scope ไม่มี app, session, DB, transaction, order, balance, position หรือ financial computation changes.
- workflow ใช้ read permissions, full action SHA, checkout ไม่เก็บ credentials; CodeQL full analysis overrides อ้างอิง `feature-flags.ts` ที่ action SHA `33d7b85da1a04171e211befe2c739303b9a4c066`.

คำสั่งหลัก:

```sh
python -m unittest discover -s tools/security/tests -v
SECURITY_SCANNER_PROBES=/tmp/tiewtrade-security-tools python -m unittest discover -s tools/security/tests -v
ruff check --config backend/pyproject.toml tools/security
ruff format --check --config backend/pyproject.toml tools/security
mypy --strict --explicit-package-bases tools/security
actionlint .github/workflows/security.yml
```

## ผล scanner จริง

Gitleaks temp repo: negative placeholder ผ่าน; contextual venue/sealing positives พบ; inline allow ไม่ทำให้ผ่าน; เพิ่มแล้วลบยังพบใน history; เพิ่ม occurrence ใหม่ได้ identity ใหม่; tree finding map กลับ commit เดิม. ใช้ข้อมูลจำลองเท่านั้น ไม่มีการใช้ credential จริง.

OSV all-packages: **464 unique package-version entries** (PyPI 54, npm 410), ตรง lock inventory รวม dev/transitive/optional/bundled; local editable project แยกออกอย่างชัดเจน. Adapter/inventory probe ผ่าน แต่ security policy **Blocked**.

`{"blocked": 3, "critical": 2, "excepted": 0, "high": 1, "low": 1, "medium": 6, "needs_triage": 0, "none": 0, "unknown": 0}`

| Severity | Package/version | Advisory |
|---|---|---|
| critical | PyPI `certifi 2026.7.22` | [GHSA-6q48-6c7w-9gw2](https://osv.dev/vulnerability/GHSA-6q48-6c7w-9gw2) |
| critical | PyPI `certifi 2026.7.22` | [PYSEC-2026-4320](https://osv.dev/vulnerability/PYSEC-2026-4320) |
| high | npm `vite 6.4.3` | [GHSA-587h-7wmj-h5pm](https://osv.dev/vulnerability/GHSA-587h-7wmj-h5pm) |

certifi สอง advisory IDs อยู่ใน alias group เดียวกัน จึงเป็น 3 blocking records ใน 2 packages ไม่ใช่คำยืนยันว่าเป็นช่องโหว่ต่างกัน 3 รายการ. ไม่แก้ dependencies หรือยกเว้น findings; ต้องให้เจ้าของตัดสิน remediation แยกตาม requirements §6.1.

Lockfile fingerprints:
- `backend/uv.lock`: `5cf0ea9b9a0cf9fe9115e9368c7acbd10a1ec11d818635fec1e08f725886dce3`
- `frontend/package-lock.json`: `ad65775150661158b8aa31171fc01f374dbfbd885bf6ef903b88791b60b882c6`

Configuration digest: `170a2231fdfacb5340c9c67dab1f2b35433a997c2aebd1040df29f60c72fbd65` (pins/config/helper/workflow ณ หลักฐานนี้).

## ที่ยังไม่พิสูจน์ / ห้ามใช้ปิด Feature gate

- CodeQL bundle บน Linux และ real insecure/fixed fixtures ทั้ง Python, JS/TS, Actions: **Not Run**. SARIF fixtures ผ่านเฉพาะ parser/policy; ต้องยืนยัน file coverage, full-results และ action logs ไม่มีข้อมูลอ่อนไหวจริงบน runner.
- Local origin snapshot scan ดำเนินการภายหลัง: 246 commits, 92 findings ต้อง triage; ดู refactor-validation.md. Latest-origin/final-candidate scan ยังไม่รัน.
- Remote PR/fork, changed-head/base race, failure/merge-blocking proof และ required CI เดิมบน final candidate: **Not Run**.
- Native security settings, strict/main required-check activation และ readback: **Not Run**; settings ยังไม่เปลี่ยน.
- Code review findings สองข้อแก้และ refactor ที่อนุญาตแล้ว; ดู refactor-validation.md; ไม่มี commit/push/PR/merge.
- V-19 post-merge CI/settings/manual dispatch: **Not Run — Pending Full Validation**.

## ขั้นตอนถัดไป

Refactor และ local validation ดำเนินการแล้ว; ต้อง triage blockers และมีคำสั่ง Git เพื่อทำ remote validation ตามแผน ก่อน merge.

## ผลหลัง code review

ดู [การแก้สอง findings และ regression evidence](review-fixes.md); configuration digest ข้างบนเป็นของก่อนแก้ ใช้ digest ใน refactor-validation.md สำหรับ implementation ล่าสุด.

## ผลหลัง owner exception approval

นำเข้า 92 exact exceptions และ local origin snapshot re-scan ผ่าน (0 blocked/0 triage);
ดู exception-approval.md และ approved-secret-scan.json สำหรับ config digest ล่าสุด.
ข้อจำกัด final candidate/remote และ dependency blockers ยังคงอยู่.
