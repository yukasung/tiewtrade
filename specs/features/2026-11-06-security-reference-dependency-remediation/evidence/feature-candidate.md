# Reference dependency remediation — Feature checkpoint 2026-11-06

สถานะ: **Code review APPROVED — เตรียม commit/push/PR ตามคำสั่งเจ้าของ; required CI pending**
Requirements, plan/validation และ scope amendment NC-SEC-REF-01 Approved ครบ.
RV-01..08 ผ่าน local; RV-09 review APPROVED/required CI ยัง Not Run; RV-10 Pending Full Validation
ที่ post-merge checkpoint. ยังไม่ Completed/พร้อม merge และยังไม่มี commit/push/PR.

## สิ่งที่เปลี่ยนและตัวตน candidate

Branch `feature/security-reference-dependency-remediation`, base/HEAD
`74ca1f4bc8118f119d9bdd96381c061b961650ee`; changes ยังไม่ commit.
เปลี่ยน runtime dependency data เพียง `references/admin-template/package-lock.json`:

| Package | Before → after |
|---|---|
| Vite | 8.2.2 → 8.2.4 |
| source-map-js | 1.2.1 → 1.2.2 |
| js-yaml | 4.1.1 → 4.3.2 |
| brace-expansion | 5.0.9 → 5.0.11 |
| zod | 4.5.4 → 4.6.6 |

Semantic diff จำกัดห้า lock entries: version/resolved/integrity จาก exact npm registry;
Vite/js-yaml/zod funding metadata เปลี่ยนตาม release metadata ด้วย.
คง root manifest/ranges, graph อื่นรวม nested LightningCSS เดิม; ไม่เพิ่ม packages.
Source/UI/config ของ template, application source/lockfiles, sessions/DB/trading,
workflows/pins/policy/exceptions ไม่เปลี่ยน. ไม่มี Live credentials/orders.

- Baseline template lock SHA256: `8a8c48ced334eaf5d6f06babca467c83b04cc242e37f4326aee7c20d61ea131b`
- Candidate/repository template lock SHA256: `8a8ee180aaa1ea184cbbbd8f241b0c922c9d451874366591908ee6ef9613e9ca`
- Policy/helper configuration digest: `fe5e8d743e9e67e350c8969acd9292e24a9165e57a65bd5c90a48633d91419ad`
- Environment: macOS arm64; Node v22.23.4, npm 10.9.9, Python 3.12;
  external Playwright 1.63.0 ตรง frontend lock เดิม, Chromium headless ที่มีอยู่.
- Node engines ใน lock 217 รายการผ่านทั้งหมด; frozen install แยกใน temporary directory
  ด้วย minimal environment และ empty npm user/global config ไม่ใช้ credentials.

## ผลตรวจ local

| เกณฑ์ | ผลและหลักฐาน |
|---|---|
| RV-01 scoped diff | Passed — เปลี่ยนห้า package entries เท่านั้นและ metadata ตรง targets |
| RV-02 clean/frozen install | Passed — `npm ci --include=dev --include=optional` 30.13 วินาที; `npm ls --all --json` exit 0 ไม่มี invalid/missing; installed targets ตรง; lock hash คงเดิม |
| RV-03 inventory | Passed — 373 template occurrences / 372 unique package pairs + 54 backend supplemental = 426/426 scanner coverage; missing-row negative control ถูกปฏิเสธ |
| RV-04 security | Passed — pinned checksum-verified OSV v2.7.0; baseline High 8/Medium 8/Low 1 → candidate High 0/Critical 0/unknown 0/Medium 3; known High 8 หายครบ; scan 2.71 วินาที |
| RV-05 build | Passed — `npm run build` รวม TypeScript + Vite 8.2.4/Tailwind/SVGR 10.93 วินาที, 1,058 modules; lock hash คงเดิม |
| RV-06 callers | Passed — 10 bounded checks: source-map round trip/indexed interior, YAML structures/round trip/rejection + cosmiconfig actual loader, minimatch brace cases, zod constrained collections ผ่าน plugin resolution, actual ESLint config/plugin valid/invalid hook fixtures |
| RV-07 browser | Passed — 20/20: 5 routes × dev/preview × desktop 1440×900/mobile 390×844; heading/content/interaction/local assets โหลดได้ ไม่มี page errors/failed local requests/HTTP errors/broken images/root horizontal overflow |
| RV-08 scope/identity | Passed local — candidate lock ตรง scanned/installed/built/browser-tested bytes; manifest/application lock/policy/helper fingerprints เดิม; ไม่มี production/session/DB/order/financial code diff |
| RV-09 review/required CI | Partial — review APPROVED; owner สั่ง publication แล้ว; required CI รอ final commit/PR |
| RV-10 post-merge | Not Run — Pending Full Validation จนถึงคำสั่ง merge และ post-merge checkpoint |

Scans ใช้ `tools.security.scan.scan_dependencies` + inventory/evaluate เดิมโดยไม่แก้ source;
checksum binary ตรง Darwin-arm64 pin ใน `.github/security/tools.json`.
Staging mapping: template lock → temporary `frontend/package-lock.json`, backend lock
เดิม → temporary `backend/uv.lock`; policy root เป็น repository จริง. Supplemental
backend ไม่มี findings; findings ทั้งหมดเป็น npm ใน template. ไม่ใช้ permanent
application gate แทน template scan และไม่เพิ่ม scanner ignores/exceptions.

## ผลที่ยังเหลือและข้อจำกัด

Medium 3 records ยังบันทึกตามจริง ไม่มีข้อยกเว้นใหม่:

- @humanfs/node 0.16.6 — GHSA-p498-v437-472g
- brace-expansion 5.0.11 — GHSA-q2hr-2g5m-vwhr
- minimatch 10.2.6 — GHSA-g3hv-75wg-m249

Build มี warning chunk ใหญ่กว่า 500 kB; source/bundling config ไม่เปลี่ยนในงานนี้.
Browser harness อนุญาตเฉพาะ loopback จึง block Google Fonts CSS ทุก page ตามคาด:
console resource error เป็น external font ที่ถูก block; ไม่มี local asset/page errors.
Screenshots แสดง fallback font ไม่ใช้ผลนี้ยืนยัน external font availability.
ตรวจภาพ desktop dashboard/mobile form แล้ว content/layout แสดงถูกต้องและไม่ล้น viewport.

Caller probe ครั้งแรกคาดว่า indexed source-map boundary line 3/column 0 จะได้ line 7
แต่คืน null. ดาวน์โหลด baseline source-map-js 1.2.1 โดยตรวจ npm tarball integrity
แล้วเทียบ fixture เดียวกันกับ candidate 1.2.2: ทั้งสองคืน null ที่ column 0 และ
line 7 ที่ columns 1/2 เหมือนกัน. แก้ assertion ให้ query ภายใน mapped section
(column 1) แล้ว probes ผ่านครบ 10; pre-existing boundary behavior ไม่ได้รับการแก้
และไม่ใช่ regression จาก update นี้. Comparison และประวัติ failure อยู่ใน safe JSON.

ไม่ได้ reproduce Vite Windows exploit หรือทดสอบ resource-exhaustion attacks;
ใช้ fixed-version/advisory ranges + full scan เป็น remediation proof. ไม่เพิ่ม full
application regression/DB workload local เพราะ application dependencies/source ไม่เปลี่ยน;
required CI ยังต้องผ่านจริงก่อน merge ไม่ใช้ผล local แทน.

## ประวัติ checkpoint และวิธีทำซ้ำ

รอบแรกตาม scope เดิม 3 packages แก้ High เป้าหมาย 5 แล้ว แต่ยังเหลือ High 3
ใน brace-expansion/zod จึงหยุดก่อน install/build. เจ้าของ approve
[scope amendment](scope-amendment-proposal.md) แล้วปรับ requirements/plan/validation
ก่อนเพิ่ม targets; NC-SEC-REF-01 Closed. ผลเก่า Failed ไม่ถูกลบ อยู่ใน safe JSON.

- [safe results, inventories, fingerprints, script digests](feature-candidate.json)
- [คำสั่งและ source ของ temporary probes สำหรับทำซ้ำ](validation-commands.md)
- ภาพ: [desktop dashboard](preview-home-1440.png), [mobile forms](preview-form-elements-390.png),
  [desktop buttons](dev-buttons-1440.png), [mobile sign-in](preview-signin-390.png)

Raw scanner/npm-ls reports อยู่ temporary storage ไม่ commit/upload.
Temporary root อ้างอิงจาก `/tmp/tiewtrade-reference-remediation-active-path`;
Node/Python scripts สร้างเฉพาะ fixture/config ที่ต้องใช้ใน temp และ cleanup dev/preview
processes ของงานแล้ว. ไม่แตะ process/container/worktree ของงานอื่น.
เวลาข้างต้นวัดเฉพาะ install/build/scan; browser/caller/อ่านเอกสาร/รออนุมัติไม่ได้จับแยกครบ.

## ขั้นถัดไป

[Code review APPROVED](code-review.md) ตาม owner `review code`; ไม่มี findings ต้องแก้.
เจ้าของสั่ง `เริ่มทำ` ขั้น commit/push/open PR แล้ว. รวมหลักฐานก่อน commit และติดตาม
required CI บน SHA ล่าสุดจนจบ; ผล CI ที่เกิดหลัง commit รายงานใน PR body พร้อม SHA/run URLs
โดยไม่สร้างเอกสาร commit วนเพื่อบันทึก CI ของเอกสารตัวเอง. Merge รอคำสั่งเจ้าของแยก;
RV-10 และ native alert readback คงรอ post-merge ตามระยะเดิม.
