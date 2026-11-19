# Dependabot maintenance — Plan

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-19 (“approve”)**
วันที่: 2026-11-19
Requirements: [Approved](requirements.md) 2026-11-19
Branch: `spec/dependabot-maintenance`
Baseline ที่ใช้วางแผน: `abd3fe15bc96488897c3fe5e4d813d575dfb4f4c`

## เป้าหมายและเหตุผล

นำ exact updates จาก PR #50/#55/#56/#57 มารวมบน latest main และพิสูจน์ dependency
resolution, LP04 callers, frontend behavior และ security inventory บน candidate เดียว.
ใช้ lock เดิมและ installed graph เดิมเป็นฐาน; ไม่ใช้ broad npm update/audit fix.
ไม่มี application/backend/API/schema/session/UI source change ที่วางแผนไว้.

Requirements อนุมัติแล้วจากคำตอบ “เริ่มทำ” วันที่ 2026-11-19. เอกสารนี้และ
[validation](validation.md) ยังรออนุมัติ: ห้ามเริ่ม merge PR heads, resolve/install,
แก้ lockfiles หรือสร้าง/รัน verification harness ก่อนผ่านจุดนี้.

## สิ่งเดิมที่ใช้ซ้ำ

| ส่วน | แหล่งเดิมและการใช้ |
|---|---|
| Dependency graph | `frontend/package-lock.json` และ `references/admin-template/package-lock.json`; manifest ranges เดิมรองรับ targets จึงคง package.json ทั้งสอง |
| App checks | scripts ใน `frontend/package.json`, `frontend/vitest.config.ts`, `frontend/playwright*.config.ts`, existing tests/E2E; สัญญาจริง `backend/openapi.json` |
| Template checks | scripts/config ใน `references/admin-template/`; ไม่ย้าย React 19/Vite 8 มา app React 18/Vite 6 |
| LP04 bytes/policy | `frontend/vendor/`, `.github/security/`, `tools/security/trusted_sources.py`, `withdrawal.py` และ existing tests; คง source/exception/config/pins |
| Inventory/scan | `tools/security/dependencies.py` inventory/evaluate/package_key และ `tools/security/scan.py::scan_dependencies`; วิธี sidecar จาก [reference remediation plan](../2026-11-06-security-reference-dependency-remediation/plan.md) |
| Caller proofs | LP04 archived `harness/verify_candidate.py`, `installed_resolution.mjs`, `lp04_public_callers.py` และ fixture helpers เฉพาะที่จำเป็น; provenance ตาม [published reconciliation inventory](../../maintenance/2026-11-18-local-reconciliation/inventory.json) |
| Publication | `.github/workflows/ci.yml`, `security.yml` และ AGENTS Git workflow เดิม; ไม่แก้ selection/required checks |

แหล่ง harness เก็บใน verified local backup ของ picomatch worktree ที่ระบุโดย backup
manifest (`TiewTrade-local-backup-20261118-225946` ใน sibling directory). หลังอนุมัติจึง
recover เฉพาะ public-source helpers ที่ต้องใช้ ตรวจ SHA เทียบ published inventory และ
เก็บ source/provenance ที่จำเป็นใน feature นี้ให้ทำซ้ำได้โดยไม่พึ่ง private absolute path.
หาก source ไม่ครบหรือ hash ไม่ตรง ให้บันทึก blocker ห้ามอ้าง archived receipt แทนการทดสอบ.
ไม่ restore private dumps, credentials หรือทั้ง campaign; ใช้ trusted-source validator
ปัจจุบันตรง ๆ ก่อนสร้าง logic ซ้ำ. ปรับเฉพาะ version/path parameters ที่จำเป็นและตรวจ diff.

## ขั้นตอนหลังอนุมัติ

### 1. ยืนยันฐานและรวม updates

- Fetch remote โดยไม่แก้งานอื่น; บันทึก main/PR heads/checks และเทียบกับ
  [PR baseline](evidence/pr-baseline.json). หาก PR head เปลี่ยนให้ตรวจ semantic delta ใหม่.
- ตรวจ Node 22 และบันทึก exact Node/npm versions; ใช้ npm ที่มากับ runtime ที่เลือกให้
  local install modes ใช้รุ่นเดียวกัน. CI ยังคง Node 22/npm ตาม workflow เดิม ไม่เพิ่ม toolchain pin ใหม่.
- รวม heads ของสี่ PR ด้วย normal merges บน branch เดียว ตรวจ/resolve conflicts เป็น
  approved targets และ manifest ranges เดิม. บันทึกแต่ละ merge กับ final delta;
  ไม่ใช้ ours strategy/empty ancestry merge เพื่ออ้างว่าทำ updates แล้ว.
- ตรวจ every package occurrence/edge/resolved/integrity/flags และ diff จาก latest main.
  จำกัด app เป็น Vite 6.4.6 และ Vitest family 4.1.12; reference brace-expansion 5.0.13,
  humanfs node 0.16.8/core 0.19.2/types 0.15.0. ไม่มี funding-only churn นอก scope.
- ตรวจ optional WASM closure หกรายการตาม DM-01/03: parent 4.3.3 metadata, dependency
  edges/hoisting และ frozen install portability. เพิ่มเฉพาะ nested copies ที่จำเป็นพร้อม
  หลักฐาน ไม่ bump parent หรือดึง optional peers อื่น. หากต้องเปลี่ยนนอก scope หยุดขอ amendment.
- ใช้ targeted lock resolution เท่าที่จำเป็น; ไม่ยอมรับ unrelated drift จาก npm serialization.
  บันทึก baseline/candidate semantic delta และ hashes ก่อนตรวจต่อ.

หาก normal merges ไม่สามารถรักษาขอบเขตได้ ให้เสนอวิธีรวมที่ตรวจได้ก่อนทำต่อ;
ห้ามทำให้ประวัติบอกว่า merge ทั้งที่ intended changes ยังไม่ถูกนำมาใช้.

### 2. Frozen install และ LP04

- ใช้ owned temporary roots แยก app/reference พร้อม package manifests, exact locks,
  vendor bytes และ relative layout ที่ scripts ต้องใช้. ไม่ใช้ node_modules เก่าหรือ owner services.
- App ตรวจ `npm ci` ปกติ, `npm ci --ignore-scripts` และ relocation ของ workspace แบบ
  frozen; บันทึก lock hash ก่อน/หลัง, installed graph และ source bytes ทุก picomatch occurrence.
  Ignore-scripts mode ใช้พิสูจน์ resolution/bytes; normal mode ใช้ runtime/build acceptance.
- ใช้ existing LP04 verifier/installed resolver ตรวจ archive/parser/provenance,
  package identity/license และ override จริง. คง archive SHA256
  `9cc97cff17fcae65f9b7e9b249670d38decc451c0210f34678de608a5e8ff39d`
  และ parser SHA256 `b4d1caf92c2aaea62b221cf32138e845f7fa4bfff6c3db3b26e09069b4d1c806`.
- Inventory actual Vite/Vitest/tinyglobby/fdir resolution/options จาก installed source.
  รัน existing finite benign/restricted-pattern caller cases กับรุ่นที่ติดตั้งจริง รวม build,
  discovery/include/exclude และ watcher/filter เส้นทางที่เปลี่ยน. คง negative assertions;
  opt-out/unknown caller ที่พิสูจน์ไม่ได้เป็น blocker. Child cases จำกัดเวลา/หน่วยความจำ
  ตาม harness เดิม; ไม่รัน vulnerable baseline workload หรือขยาย LP04 campaign.
- ใช้ existing negative source tests และ isolated tamper copies พิสูจน์ว่าตรวจพบ source/hash/
  resolution ผิด; ไม่แก้ bytes ใน candidate. Reuse parser proofs เฉพาะส่วนที่ unchanged.
- Reference `npm ci` แยกและ relocation/frozen verification สำหรับ optional closure;
  ตรวจ installed brace/humanfs paths/callers และ graph โดยไม่ปน app override/LP04.

### 3. Behavior และ security

- App: existing lint, typecheck, Vitest suite, actual API contract generation/diff, production
  build และ dev/preview asset smoke (HTML, JS/CSS, route loading, error responses, process cleanup).
  Build/contract outputs ต้องไม่ทิ้ง source drift; ไม่แทน backend contract ด้วย fixture ที่แต่งขึ้น.
- ใช้ Playwright regressions เดิมที่ครอบคลุม account setup/trading UI และ config
  supported-symbols/manual-orders/protections/risk-limits ตาม dependency impact.
  ใช้ isolated owned DB/services และ Paper/FakeVenue เท่านั้น; ไม่มี Live/owner credentials.
  เก็บ screenshot/trace เฉพาะ failure โดยไม่เผย secrets. Required CI ยังรันครบตาม workflow.
- Reference: build (`tsc -b && vite build`), lint baseline/candidate comparison และ dev/preview
  smoke รวม actual tooling callers ของ brace/humanfs. หาก baseline มี lint failure ให้เก็บ
  ทั้งคู่และแยก inherited/new failures; candidate regression/incompatibility บล็อก ไม่กลบด้วย UI edits.
- Application security: scanner เดิมบน backend+frontend locks จริง พร้อม trusted LP04
  source และ fresh OSV withdrawal evidence จาก guard เดิมทุก scan. ใช้ pinned OSV binary/
  checksums/config/flags เดิม; ไม่เปลี่ยน severity gate หรือ exception.
- Reference security: isolated sidecar root วาง exact unchanged `backend/uv.lock` กับ
  exact reference lock ที่ `frontend/package-lock.json`, บันทึก original→staged path mapping
  และ SHA ก่อน/หลัง. เรียก `scan_dependencies(staging_root, repository_policy_root, binary)`
  ด้วย policy เดิม; ไม่ copy app trusted-source manifest มา registry-only sidecar.
  แยก backend/reference findings และ unique identities/occurrences ไม่อ้างว่าเป็น app lock.
  ใช้ inventory/evaluate พิสูจน์ completeness ทุก optional/nested row; negative copy ที่
  ตัด identity ออกจากรายงานต้องถูกปฏิเสธ. ไม่แก้ original report/lock เพื่อให้ scanner ผ่าน.
- Raw scanner reports อยู่ owned temporary/private storage; commit เฉพาะ safe package
  identities, counts, severity, hashes, source mapping, outcome และ command/version receipts.
  High/Critical/Unknown unresolved บล็อก; Medium/Low บันทึกตามจริง.

### 4. Review, publication และ branch closure

เมื่อ implementation ครบ แจ้ง Ready for Code Review พร้อมผล/ความเสี่ยง/validation ค้าง
แล้ว review diff, installed callers/dependencies และ safety/stateless invariants ต่อทันที.
แก้ findings และ refactor เฉพาะที่มีประโยชน์; ตรวจซ้ำเฉพาะ affected proofs ตาม AGENTS.
ไม่ใช้ authorization 500ms/protection 1s ผ่อนเพราะ CI timing และไม่แก้ test เพื่อซ่อน regression.

ผ่าน Feature local/review แล้ว commit/push หนึ่ง combined PR พร้อมหลักฐานที่มีอยู่.
ตาม required CI/Security ของ final SHA ให้ครบ; ถ้าฐาน/หัวเปลี่ยนให้ประเมิน affected proof
และ CI ใหม่ตามจริง. Merge แบบรักษา ancestry ของ incorporated PR heads (ไม่ squash/rebase
จนเสียหลักฐานที่ต้องใช้ลบ refs), ตรวจ expected head/base/mergeability ก่อน merge.
ติดตาม postmerge CI/Security บน merge SHA จนจบตามอำนาจ Git ที่เจ้าของให้ไว้.

เมื่อ final updates ครบและ CI เขียว ตรวจ PR เดิม/heads ไม่เปลี่ยนและแต่ละ head reachable
จาก main จึงจัดสถานะ merged/superseded ตามความจริงและลบเฉพาะ refs ที่ผ่าน merged/pushed/
CI-green พร้อม backup. Local ใช้ `git branch -d` เท่านั้น; ไม่ force push/delete งานใหม่.
ถ้า head ใดไม่ reachable ให้คง branch และรายงาน ไม่สร้าง ancestry ปลอมเพื่อเก็บกวาด.
ประวัติ/validation branches อื่นที่ยังไม่ผ่านกฎลบอยู่นอก implementation scope นี้.

## ขอบเขตไฟล์ ผลกระทบ และจุดหยุด

Expected dependency diff: lockfiles สองแห่งเท่านั้น; package.json ranges/vendor/source/
security config/workflows ไม่เปลี่ยน. เพิ่มเฉพาะ spec/evidence และ minimal reusable verification
helpers ใน feature นี้เมื่อจำเป็น. ไม่มี DB migration, persistent/session storage, business
or trading semantics เปลี่ยน; ตรวจ stateless rules ใน review ว่ายังคง PostgreSQL sessions.

หากพบ implementation/harness defect ในอำนาจวิศวกรรม ให้บันทึกปัญหา หลักฐาน ทางเลือก
เหตุผล ผลกระทบ/การ reuse และ amendment ก่อนแก้ตาม delegated authority 2026-11-14.
หากต้องผ่อน correctness/security/safety, เปลี่ยน LP04 bytes/targets/business rules หรือ
มี relevant Needs Clarification ให้หยุดขอเจ้าของตัดสินใจ. ไม่ผ่านเกณฑ์เดิมครบสามรอบ
หรือเจ้าของแจ้งใช้เวลามากเกินไปให้หยุดเสนอทางเลือกก่อนทดลองอีก ไม่ลดเกณฑ์.

ประมาณ local checks 15–30 นาที, required CI ก่อน/หลัง merge รวมประมาณ 40–60 นาที
(รวมราว 60–90 นาที ขึ้นกับ queue/download). แจ้ง scope/เวลาจริงก่อนชุด E2E/งานยาว;
ไม่ถือประมาณนี้เป็นอนุญาต rerun campaign. ไม่มี workload/endurance/4-hour run ใหม่.

ขั้นถัดไป: เจ้าของอนุมัติ plan และ validation ทั้งสองฉบับ แล้วจึงทำขั้น 1–4 ต่อเนื่องตาม
ขอบเขตนี้และ Git workflow เดิม; การอนุมัติ requirements อย่างเดียวไม่เปิด implementation.

## บันทึกอนุมัติ

2026-11-19 เจ้าของตอบ “approve” หลังแก้ finding เกณฑ์ปิดงานแล้ว.
อนุมัติ plan และ validation ฉบับนี้ให้เริ่ม implementation/review/validation/publication
ตามขอบเขตและจุดหยุดเดิม; ข้อความรออนุมัติในเนื้อหาด้านบนเป็นประวัติขั้นเสนอ.

## Execution note — isolated contract check, 2026-11-19

Evidence: app lint/types/tests/build Passed; `check:api` generated real backend types but
returned 129 because owned scratch was outside a Git repository. This is a scratch-layout
measurement error, not API acceptance. Under engineering delegation 2026-11-14, initialize
an isolated Git repository tracking the original `src/api-types.ts`, then rerun unchanged
`npm run check:api`; compare generated bytes independently to candidate source. Preserve
initial failed measurement. No source/assertion/timeout/policy change. Reference lint46
issues requires baseline comparison before any inherited-status conclusion.

## Execution environment amendment — 2026-11-19

Local Docker daemon is unavailable and no local PostgreSQL server is installed. Existing
required CI supplies isolated PostgreSQL/Redis and runs all five unchanged Playwright
configurations. Execute DV-05 there on the final candidate rather than fabricate local
DB results or add infrastructure; DV-05 remains Not Run until that CI succeeds and is
still mandatory before merge. This changes execution location only under engineering
delegation 2026-11-14; no assertion, selection, timeout, safety criterion or approval gate
is waived. Local frontend709 tests and finite caller12 cases Passed. Reference baseline/
candidate lint both report42 errors/4 warnings; formatted output differs only in padding
caused by absolute path lengths. Compare normalized diagnostics (not raw column padding),
retain initial strict-text comparison failure and both outcomes; do not change template UI.

## Asset smoke harness correction — 2026-11-19

Both app/reference smoke probes reached HTML and executable assets, then failed the
missing-JS assertion. urllib's request omitted an explicit JavaScript Accept header;
Vite SPA HTML fallback serves index.html to generic requests. Before changing the helper,
classify this as a request-contract error, not a product fix: send Accept:
application/javascript for the missing script and retain404 assertion; route HTML still
must return200. Delegated engineering correction only; preserve the failed probes.
No Vite config/source, timeout or acceptance threshold change.

## Security finding correction — 2026-11-19, before patch

Required Security run44455180767 on head daa1655 reported High `js/file-system-race`
in recovered `harness/installed_resolution.mjs:50`. The archived prototype checked a path
with statSync then reopened it to read source; a replacement could invalidate that check.
Under delegated engineering authority2026-11-14, replace path-stat/read with directory
entries, reject symlinks, and open source files with O_NOFOLLOW, fstat and read the same
file descriptor, always closing it. Preserve exact installed parser/manifest/license and
caller assertions. Reuse original helper provenance plus explicit adaptation; do not add
an exception or skip CodeQL. Targeted proof: rerun resolution/caller checks on unchanged
installed candidate plus symlink negative; required Security on next SHA remains mandatory.
Historical High/failed run retained; no app dependency/source/security-policy change.
