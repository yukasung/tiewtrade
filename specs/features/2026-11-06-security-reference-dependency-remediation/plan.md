# Reference template dependency remediation — Plan

สถานะ: **Approved — plan/validation และ scope amendments NC-SEC-REF-01/02 อนุมัติ 2026-11-06**
วันที่: 2026-11-06
Requirements: [Approved](requirements.md)
Branch: `feature/security-reference-dependency-remediation`

## 1. แนวทาง

อัปเดตเฉพาะ locked Vite 8.2.2 → 8.2.4, source-map-js 1.2.1 → 1.2.2 และ
js-yaml 4.1.1 → 4.3.2, brace-expansion 5.0.9 → 5.0.11 และ zod 4.5.4 → 4.6.6
ใน `references/admin-template/package-lock.json` ตาม scope amendment ที่อนุมัติแล้ว.
คง manifest ranges, template source/UI, application dependencies และ permanent CI scope.
เพิ่ม secret false-positive exception เพียง exact identity ตาม NC-SEC-REF-02 ที่อนุมัติ.
สร้าง candidate ใน temporary copy ก่อนนำ lockfile ที่ตรวจ semantic diff แล้วกลับ branch.
ไม่มี migration, storage/session architecture ใหม่ หรือ trading behavior change.

## 2. ของเดิมที่จะใช้ซ้ำ

| Path | ใช้เพื่อ |
|---|---|
| `references/admin-template/package.json`, `package-lock.json` | constraints, npm lock v3 และ scripts `build` (`tsc -b && vite build`), `dev`, `preview` |
| `references/admin-template/vite.config.ts` | actual React/SVGR/Tailwind build pipeline; ไม่แก้ config |
| `references/admin-template/src/App.tsx`, `src/layout/AppLayout.tsx` | route/layout อ้างอิงสำหรับ browser checks โดยไม่แก้ UI |
| `frontend/package-lock.json` และ Playwright ใน `frontend/package.json` | external browser harness ที่ version ตรง lock เดิม; ไม่เพิ่ม Playwright เข้า template |
| `tools/security/system.py::install`, `.github/security/tools.json` | checksum-verified OSV v2.7.0 เดิมและ tool fingerprints |
| `tools/security/scan.py::scan_dependencies` | OSV flags และ handling exit/errors เดิม รวม all-packages/all-vulns/no-call-analysis/no-resolve |
| `tools/security/dependencies.py::inventory`, `evaluate`, `package_key` | full inventory และ fail-closed coverage/schema/severity validation เดิม |
| `tools/security/model.py`, `severity.py`, `.github/security/osv-scanner.toml` | safe summaries, severity validation และ config ที่ไม่มี ignores/overrides |
| `.github/workflows/ci.yml`, `security.yml` | required CI และ security gate เดิมหลังเจ้าของสั่ง Git; ไม่แก้ workflows |
| `evidence/requirements-research.json` ของงานนี้ | baseline versions, parent ranges, fingerprints, advisory IDs และ registry targets |

Helpers เดิมรับชื่อ lockfile ของ application แบบตายตัว จึงใช้ staging ตามหัวข้อ 4
แทนแก้ helpers หรือขยาย production CI. ไม่เพิ่ม permanent helper/test source ในงานนี้;
temporary probes เก็บคำสั่ง/เหตุผล/digest ในหลักฐานเพื่อให้ทำซ้ำได้.

## 3. สร้าง dependency candidate หลังอนุมัติ

1. ยืนยัน base/head และ dirty diff; เก็บ SHA256 ของ template manifest/lockfile,
   application lockfiles และ policy/helper sources. ยืนยัน targets กับ official registry
   และ advisory metadata อีกครั้งเมื่อ implementation เริ่ม ไม่ใช้ชื่อ latest แทน exact versions.
2. เลือก Node 22 patch ที่ตรง engines ของ template dependency graph รวม Vite
   `^20.19.0 || >=22.12.0`; บันทึก Node/npm/Python 3.12/OS/architecture จริง.
   ใช้ npm รุ่นเดียวกันสำหรับ baseline และ candidate ไม่เพิ่ม package manager.
3. ใน temporary copy อัปเดตห้า lock entries ด้วย exact target release metadata
   จาก npm registry: version, tarball URL, integrity และ release metadata ที่เปลี่ยนจริง.
   ตรวจ dependencies/optionalDependencies/peerDependencies/bin/engines เทียบ manifest
   ของ release ไม่คัดลอก fields แบบเหมารวม ไม่เดา hash และคง flags/parent ranges ของ graph.
   ไม่เพิ่ม direct deps/overrides ไม่ใช้ broad update หรือ `npm audit fix`.
4. ตรวจ semantic diff ทุก package path กับ baseline: อนุญาตเฉพาะห้า targets และ
   metadata ของมัน; root manifest และ root lock package metadata คงเดิม.
   คง nested LightningCSS 1.33.0 ของ Vite และ global LightningCSS 1.32.0 ของ Tailwind
   ตาม dependency edges เดิม ไม่ flatten/downgrade graph. ตรวจ inventory และ npm
   lock consistency; หากต้องเปลี่ยน package อื่น/range/source ให้หยุดเสนอ scope ก่อนนำกลับ.
5. สแกน candidate ก่อนรัน application/toolchain scripts แล้ว clean install ด้วย
   `npm ci --include=dev --include=optional` ใน isolated directory ไม่มี credentials.
   ห้ามใช้ node_modules เก่าแทน frozen install; ตรวจ installed/resolved target versions
   จาก callers จริงและ `npm ls --all` ว่าไม่มี invalid/missing dependencies.
   OS-specific optional packages ที่ไม่ติดตั้งบน platform นี้ยังต้องอยู่ใน lock inventory scan.
6. Build/dev/preview และ compatibility probes ตามหัวข้อ 5. ยืนยัน lock fingerprint
   ไม่เปลี่ยนจาก npm ci/build/probes; นำเฉพาะ scoped lockfile กลับ branchเมื่อผ่าน.
   Dist/node_modules/browser output เป็น temporary artifacts ไม่ commit.

หาก package metadata ไม่พอสร้าง lockfile ที่ npm ยอมรับ หรือ baseline/candidate
compatibility พิสูจน์ไม่ได้ ให้คง Failed/Partial และหยุดเสนอทางเลือก ไม่ทดลอง broad
resolver upgrade เพื่อให้ผ่านเอง. ใช้กฎหยุดหลังเกณฑ์เดิมล้ม 3 รอบข้าม turn ตาม AGENTS.

## 4. Full template inventory scan โดยไม่เปลี่ยน CI

สร้าง staging root ชั่วคราวสองชุดสำหรับ baseline และ candidate:

- คัดลอก `backend/uv.lock` เดิมไป `backend/uv.lock` เพื่อให้ adapter อ่าน backend
  local-package metadata ได้ และคัดลอก template lock ไป `frontend/package-lock.json`.
  ทั้งสองเป็นสำเนาเท่านั้น ไม่เขียนทับ application lockfiles ใน repository.
- ยืนยัน byte hashes ของ staged frontend lock ตรง template ต้นทางก่อน/หลัง scan;
  บันทึก explicit path mapping นี้ใน evidence ไม่รายงานว่า template เป็น application.
- เรียก `scan_dependencies(staging_root, repository_policy_root, verified_osv_binary)`.
  Scanner จะตรวจ backend เดิมเพิ่มด้วย; แยกผล backend และ template ตาม ecosystem
  และ expected inventory ไม่รวม counts จนทำให้ coverage ของ templateดูครบผิด ๆ.
- ใช้ `inventory`/`evaluate` เดิมเทียบ package set ให้ตรงทุกชื่อ/เวอร์ชัน รวม dev,
  transitive, optional และ nested. เก็บ ledger แยกทุก package path เพิ่มเพื่อยืนยัน
  baseline 373 occurrences / 372 unique name-version pairs; duplicate occurrences
  ที่ version เดียวกันไม่ต้องมี scanner row ซ้ำ แต่ต้องไม่หายจาก ledger.
- ทำ temporary negative coverage control หนึ่งครั้ง: เอา package row ที่มีใน expected
  inventory ออกจากสำเนารายงานแล้ว `evaluate` ต้องปฏิเสธ incomplete inventory.
  ไม่แก้ raw result จริงเพื่อให้ผ่าน และไม่สร้าง fixture PR บน GitHub.
- Baseline scan ต้องตรวจ known eight advisories รวม aliases/CVE mapping ที่เกี่ยวข้อง;
  หาก feed ไม่รายงานบางรายการ ห้ามอ้าง absence เป็น proof ให้รายงานช่องว่างและ
  ตรวจ official advisory metadata ก่อนตัดสินเกณฑ์. Candidate ต้องไม่มี targets ทั้ง 8
  และไม่มี High/Critical/unknown ที่ยังไม่ได้จัดการ. ตรวจ target package versions
  กับ affected ranges ด้วย ไม่พึ่ง alert state บน main หรือ scanner ID เพียงอย่างเดียว.
- เก็บ severity/identity/coverage/fingerprints/tool-policy versions เป็น safe summary;
  raw scanner reports อยู่ temporary storage ไม่ upload/commit. ไม่เพิ่ม dependency exceptions.

Scan นี้เป็น Feature evidence เพิ่มจาก required Security CI ซึ่งยังตรวจ application
สอง lockfiles ตามเดิม; CI เขียวอย่างเดียวจึงยังไม่พิสูจน์ template remediation.

## 5. Targeted compatibility และ UI validation

- `npm run build` ต้องผ่านรวม TypeScript และ Vite pipeline. `source-map-js` ผ่าน
  PostCSS/Tailwind callers จริง; ตรวจ small source-map generate/consume round trip
  และ indexed-section offsets ที่ถูกต้องจาก installed module เพิ่มใน temporary probe.
- js-yaml: ใช้ installed module ที่ resolve จาก cosmiconfig จริง ตรวจ small YAML
  mapping/sequence, anchors/merge, `!!omap`, dump/load และ invalid YAML rejection;
  ใช้ fixtures เดียวกันกับ baseline/candidate เมื่อจำเป็นเพื่อพิสูจน์ compatibility.
  ตรวจ cosmiconfig โหลด temporary YAML config ได้ ไม่สร้าง config ใหม่ใน template.
  ไม่ทำ CPU exhaustion, shell execution หรือ reproduce exploit บนเครื่องผู้ใช้.
- brace-expansion: ใช้ module ที่ resolve จาก minimatch จริง ตรวจ literal/escaped/nested
  brace cases ขนาดเล็กและ minimatch caller ให้ผลถูกต้อง; ไม่ทำ stack exhaustion.
- zod: ใช้ module ที่ resolve จาก eslint-plugin-react-hooks จริง ตรวจ valid/invalid
  constrained collections ขนาดเล็ก; ตรวจ actual ESLint config/plugin loading ด้วย
  temporary valid/invalid hook fixtures ใน isolated template copy แยก expected rule
  rejection ออกจาก tool crash. ไม่แก้ template source/config หรือทำ memory exhaustion.
- Dev และ preview bind เฉพาะ loopback ใช้ port ว่าง/strict port และ cleanup process
  ที่ task สร้างเอง. ตรวจ HTML, transformed TSX, generated JS/CSS/assets โหลดได้.
- ใช้ external Playwright harness ตาม lock เดิมกับ browser ที่มีอยู่/ติดตั้งแยกใน temp
  ถ้าจำเป็น. เปิด `/`, `/form-elements`, `/basic-tables`, `/buttons`, `/signin` ทั้ง
  dev และ preview; ยืนยัน page content/component แสดงจริง, JS/CSS/local assets สำเร็จ,
  ไม่มี page error หรือ failed local module loads และ interaction ตัวแทน เช่น button/input.
  ใช้ viewport desktop 1440×900 และ mobile 390×844 ตรวจ responsive layout จาก template.
  ไม่กรอก credential/ส่ง login จริง; แยก optional external-resource failures ตามสาเหตุจริง.
- เนื่องจาก source/styles ไม่เปลี่ยน ไม่สร้าง pixel-perfect screenshot test ใหม่;
  เก็บ screenshots ตัวแทนและ browser results ในหลักฐาน. ถ้าพบ layout/runtime ต่าง
  หรือ check ล้ม ให้เทียบ baseline ด้วย environment/fixtures/routes เดียวกัน.
  ปัญหา baseline ไม่ทำให้ candidate ผ่านอัตโนมัติ; หากพิสูจน์เกณฑ์ไม่ได้คง blocker.
- ไม่เพิ่ม lint/type exceptions. Type-check อยู่ใน build; ไม่มี TSX diff จึงไม่เพิ่ม
  application lint/tests/full E2E local ซ้ำโดยไม่มีผลกระทบ. Required CI เดิมยังบังคับครบ.

## 6. สิ่งที่จะแก้และหลักฐาน

| Path | เปลี่ยนอะไร |
|---|---|
| `references/admin-template/package-lock.json` | ห้า target entries และ verified release metadata เท่านั้น |
| `.github/security/exceptions.json` | เพิ่ม exact secret false-positive entry ตาม NC-SEC-REF-02 เท่านั้น |
| feature `requirements.md`, `plan.md`, `validation.md` | approval/status/results ตามจริง |
| feature `evidence/feature-candidate.md` และ safe JSON/screenshot evidence เมื่อจำเป็น | ledger, exact commands/probe digests, fingerprints, findings, compatibility/browser/CI results |
| `specs/roadmap.md` | สถานะงานตาม checkpoint; ไม่ประกาศ Completed ก่อนครบเกณฑ์ |

เอกสารปิด PR #48 ที่มีอยู่แล้วถูกยกมารวมไว้ใน worktree นี้จากงานก่อนตามกฎรวม
หลักฐานก่อน commit; แยกจาก dependency diff ของงานนี้. Policy เปลี่ยนได้เฉพาะ
exact checksum exception ที่อนุมัติใน NC-SEC-REF-02.
ไม่มี migration, database/transaction/concurrency changes หรือ persistent business state ใหม่.

## 7. Checkpoints และความเสี่ยง

1. Requirements และ plan/validation Approved ครบแล้ว 2026-11-06; เริ่ม implementation ได้.
2. หลังอนุมัติ: ทำ scoped update + targeted checks/Feature evidence ต่อจนครบ.
   แจ้ง **Ready for Code Review** พร้อม diff/results/blockers แล้วหยุดรอ `review code`.
3. หลัง review/fixes: ตรวจผลกระทบของ fixes. หาก diff มีเพียง lockfile/เอกสารให้
   validation ต่อทันที ไม่ถาม refactor ตามคำสั่งเจ้าของล่าสุด; หากมี source change
   ที่อนุมัติเพิ่ม ให้ใช้ refactor checkpoint ตาม AGENTS ก่อนทำขั้นนั้น.
4. ก่อน merge: Feature gates RV-01..09 ต้องผ่านบน final head/base/merge candidate;
   ถ้า merge base เปลี่ยน ให้ตรวจ diff/fingerprints และ rerun เฉพาะ evidence ที่กระทบ.
   หลังเจ้าของสั่ง commit/push/PR ติดตาม required CI ทั้ง original และ security จนจบ;
   local checks ไม่แทน required CI. Merge ต้องรอคำสั่งแยกจากเจ้าของ.
5. หลัง owner สั่ง merge: ติดตาม main CI/Security บน merge SHA และ native alerts ตาม
   RV-10 แล้วปิด checkpoint; ไม่ dismiss alerts เอง. ไม่มี Batch/workload ใหม่ในงานนี้.
   เกณฑ์ของ feature อื่นคง Pending Full Validation ตาม roadmap เดิม.

ความเสี่ยงหลักคือ js-yaml minor compatibility, source-map/PostCSS behavior,
ความผิดพลาดจาก lock metadata, nested/optional inventory ที่อาจตกหล่น และ advisory feed lag.
ใช้ clean install + actual callers/build/browser + full coverage + official advisory checks
พิสูจน์แต่ละด้าน. Vite advisory เกี่ยวข้องกับ Windows แต่การทดสอบ macOS/Linux ไม่ได้
reproduce Windows exploit; remediation proof คือ fixed version/ranges และ full scanner.
ไม่มีการใช้ exchange API/Live credentials/orders หรือเปิด Live Trading ระหว่าง validation.

## 8. Execution checkpoint 2026-11-06

Full baseline scan พบ High 8; temporary candidate 3 targets เหลือ High 3 ใน
brace-expansion/zod ที่อยู่ใน baseline เดิมและอยู่นอก scope. หยุดก่อน install/build
และก่อนนำ candidate lock กลับ repository ตาม RR-1/4. รอคำตัดสิน NC-SEC-REF-01
ตาม [scope amendment proposal](evidence/scope-amendment-proposal.md); ยังไม่เปลี่ยน
approved scope/ขั้นตอนด้านบน. [หลักฐาน](evidence/feature-candidate.md).

## 9. Scope amendment อนุมัติ 2026-11-06

เจ้าของตอบ approve ให้ [ข้อเสนอ](evidence/scope-amendment-proposal.md) เพิ่ม
brace-expansion/zod และ compatibility probes ตามหัวข้อ 5; NC-SEC-REF-01 Closed.
ผลรอบแรกในหัวข้อ 8 เป็นประวัติที่ยังเก็บไว้ ไม่ใช้แทน full scan ของ candidate ใหม่.

## 10. Implementation checkpoint 2026-11-06

Scope amendment Approved แล้ว; update ห้า entries และ targeted local checks RV-01..08
ผ่านตาม [หลักฐาน](evidence/feature-candidate.md). Ready for Code Review — หยุดรอเจ้าของ
`review code`; review/required CI และ post-merge RV-10 ยังไม่ผ่าน/ยังไม่ถึงกำหนด.
ไม่มี runtime source changes, commit/push/PR/merge หรือ refactor ใน checkpoint นี้.

## 11. Review/publication checkpoint 2026-11-06

Owner สั่ง `review code`; [review APPROVED](evidence/code-review.md) ไม่มี findings ต้องแก้.
เจ้าของตอบ `เริ่มทำ` หลังเสนอ commit/push/open PR จึงทำ publication และติดตาม
required CI ต่อจนจบ; local evidence ใช้ต่อเพราะ dependency/config/harness ไม่เปลี่ยน.
RV-09 Partial จน required CI ผ่านบน final candidate; RV-10 รอ post-merge ตามเดิม.

## 12. Approved exact exception amendment — NC-SEC-REF-02

Owner อนุมัติ [ข้อเสนอ](evidence/checksum-exception-proposal.md) ก่อนแก้ registry:
อนุญาตเพิ่ม `.github/security/exceptions.json` ใน scope เฉพาะ identity
`d84148a55a1db82c511520b0a40131229292c3c7c1fadf8d00f66a6cbbefe8b0` เป็น
secret/false_positive ของ public source SHA256 fingerprint. คง 92 entries เดิม
และไม่เปลี่ยน scanner rules/pins/config/workflow หรือทำ broad ignore.

ตรวจ existing security policy contracts, exact registry diff, checksum proof และ
reevaluate full-template scan ภายใต้ config digest ใหม่. Reuse clean install/build/
caller/browser evidence เพราะ lock/source/harness ไม่เปลี่ยน. บันทึก failed run เดิม;
commit/push authorized fix และติดตาม fresh Security/original CI บน candidate ใหม่จนจบ.
RV-10 ยังรอ owner merge command/post-merge checkpoint. No Git history rewrite/force push.
