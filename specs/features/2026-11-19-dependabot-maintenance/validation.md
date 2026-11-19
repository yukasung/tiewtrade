# Dependabot maintenance — Validation

สถานะ: **Approved — เจ้าของอนุมัติ 2026-11-19 (“approve”)**
วันที่: 2026-11-19
อ้างอิง: [Requirements — Approved](requirements.md), [Plan — Approved](plan.md)

## สถานะหลักฐานปัจจุบัน

Current checkpoint: publication closed on PR #80; see the dated closure below.
The following preimplementation record is historical.

ขั้นนี้เป็น spec เท่านั้น: published metadata และ old PR diff/checks ตรวจแบบ read-only
ใน [registry metadata](evidence/registry-metadata.json) และ [PR baseline](evidence/pr-baseline.json).
ไม่มี candidate install/resolution/behavior/security acceptance ถูกดำเนินการสำหรับงานนี้.
Old green checks ไม่แทน final candidate; PR #56 E2E text failure ยังคงเป็น historical
Failed ที่ยังไม่พิสูจน์สาเหตุ. Main PR #79/LP04 receipts ใช้ซ้ำเฉพาะ unchanged source proof.

## Feature — ต้องผ่านก่อน merge

ทุกแถวเป็น Feature ไม่เลื่อน security/correctness ไปท้าย release. `Not Run` หมายถึงยัง
ไม่ได้รัน ไม่ใช่ Passed; เมื่อรันต้องบันทึก exact SHA, environment, command, outcome,
counts/hash และลิงก์หลักฐานที่ตรวจซ้ำได้. ไม่ hardcode จำนวน tests/packages เดิมให้เป็นเกณฑ์ผ่าน.

| รหัส | Requirements | การตรวจและเกณฑ์ผ่าน | สถานะ |
|---|---|---|---|
| DV-01 | DM-01/02/03 | บันทึก baseline/main/สี่ PR heads; final semantic lock delta ครบ every occurrence/edge/source/integrity/flags. Exact targets และ humanfs closure ถูกต้อง, manifest ranges unchanged, unrelated funding/version drift ไม่มี. WASM entries เพิ่มเฉพาะที่ graph/frozen proof จำเป็นภายใน approved list | Passed — local evidence |
| DV-02 | DM-03/04 | Node 22/exact npm receipts; app normal/ignore-scripts/relocated frozen installs ใช้ exact locks โดยไม่ rewrite. Reference normal/relocated frozen installs และ optional-platform graph ถูกต้อง. ทุก installed picomatch occurrence ใช้ LP04 bytes/hash/identity/license จริง; manifests/override/vendor/policy unchanged | Passed — local evidence |
| DV-03 | DM-04/05 | Existing trusted-source negative tests และ isolated tamper/resolution cases ปฏิเสธ invalid sources. Actual Vite 6.4.6/Vitest 4.1.12/tinyglobby/fdir caller inventory/options และ finite matching/build/discovery/filter cases ผ่าน; no unknown/unsafe opt-out. Archived helper source SHA/provenance และ inputs บันทึกไว้ให้ทำซ้ำได้ | Passed — local evidence |
| DV-04 | DM-06/08/09 | App `npm run lint`, `typecheck`, `test`, `check:api`, `build` ผ่านจาก clean actual candidate. Contract ใช้ backend/openapi.json จริง ไม่มี source/generated drift. Dev/preview routes/assets ผ่านพร้อม cleanup; ไม่มี app/UI/test criterion/timeout change เพื่อกลบ incompatibility | Passed — local evidence |
| DV-05 | DM-06/08/09 | Relevant existing Playwright account/trading UI และ supported-symbols/manual-orders/protections/risk-limits flows ผ่านบน isolated fixtures. Required CI selection ไม่ลด. ตรวจ failure logs โดยเฉพาะ historical PR56 โดยไม่สรุปว่า Vite เป็นสาเหตุล่วงหน้า; auth 500ms/protection 1s ไม่เปลี่ยน | Passed — PR80 final candidate CI/Security |
| DV-06 | DM-03/06 | Reference frozen build/typecheck, dev/preview assets และ installed brace/humanfs actual caller behavior ผ่าน; lint baseline/candidate เปรียบเทียบเก็บทั้งคู่ ไม่มี introduced failure. ไม่แก้ reference source/style/React/Vite major เพื่อให้ผ่าน | Passed — baseline lint unchanged (42 errors/4 warnings) |
| DV-07 | DM-04/07 | App backend+frontend actual full lock inventory scan ผ่าน pinned binary/checksum/config เดิมพร้อม LP04 trusted SBOM และ fresh withdrawal evidence; inventory report equality ผ่าน รวม dev/transitive/optional/nested. ไม่มี unresolved High/Critical/Unknown หรือ exception ใหม่; Medium/Low รายงานตามจริง | Passed — local evidence |
| DV-08 | DM-07 | Reference exact-lock sidecar mapping/hashes ตรวจครบ, policy เดิม, ไม่มี fake registry source/app-manifest; expected unique identities และ occurrence ledger ครบและ backend/reference counts แยกกัน. Missing-identity negative report ถูก reject. ไม่มี unresolved High/Critical/Unknown; findings อื่นรายงานตามจริง | Passed — local evidence |
| DV-09 | DM-08/09/12 | Review diff/callers/dependencies และ stateless rules; business/money/order/risk/session/schema/contracts invariants unchanged. ไม่มี Live/owner data/new infra, เก็บ review findings และ affected rechecks ครบ, ไม่มี relevant Needs Clarification หรือ blocker | Passed — local evidence |
| DV-10 | DM-10 | Ready for Code Review แจ้งแล้ว; findings resolved และ Feature local ผ่าน. Final combined PR required CI/Security ทุกด่านผ่านบน latest candidate SHA; ตรวจ expected head/base และ external/owner acceptance ที่ repo/branch protection บังคับครบ ไม่ใช้ automated review แทน required reviewer | Passed — PR80 final candidate CI/Security |

### Reuse และการเลือกรัน

ใช้ tests/config/scripts เดิมก่อนเพิ่ม helper. Frontend toolchain กระทบทั้ง runner/build/
asset/discovery จึงใช้ frontend suite และ relevant trading UI flows; backend money/domain
ไม่มี source diff จึงใช้หลักฐานเดิมเฉพาะส่วนที่ไม่ถูกกระทบ. Required CI ยังคงเป็นด่านเดิม
ครบตาม workflow แม้ local เลือก targeted checks. หากพบผลกระทบที่ proof เดิมไม่ครอบคลุม
ให้บันทึกและขยายเฉพาะส่วนที่มีเหตุผล ไม่รัน full regression ซ้ำเป็นพิธี.

No broad source refactor, backend benchmark หรือ capacity trial planned. หากจำเป็นต้อง
แก้ harness ให้บันทึกก่อนแก้ คง safety assertions/real-DB proof ที่จำเป็น และเก็บ Failed เดิม.
สามรอบยังไม่ผ่านหรือเจ้าของแจ้งใช้เวลามากเกินไปให้หยุดตาม AGENTS.

## Feature — publication closure หลัง merge

| รหัส | Requirements | เกณฑ์ | สถานะ |
|---|---|---|---|
| DV-11 | DM-10 | Merge SHA กับ postmerge CI/Security URLs/outcomes ครบและ Passed; หากล้มคง Failed/Incomplete และไม่ปิด checkpoint | Passed — see publication closure below |
| DV-12 | DM-11 | ยืนยัน intended updates ครบ/PR status ตามจริง, backup และ head reachable main/pushed/CI green ก่อนลบ refs; local `git branch -d`, no force. ถ้าไม่ครบให้คง branch พร้อมสาเหตุ. รายงาน local/remote/PR inventory สุดท้าย | Passed — see publication closure below |

ขั้นนี้อยู่หลัง merge ตามลำดับ Git; ไม่ใช้ postmerge มาแทน DV-01–10 ก่อน merge.

## Batch / Release และผลเก่าที่ต้องคงไว้

ไม่มีเกณฑ์ Batch/Release ใหม่สำหรับ maintenance นี้ และไม่อนุมัติ workload/4-hour/endurance
campaign เพิ่ม. F-17/งานอื่นที่ยัง Pending Full Validation คงสถานะนั้น รวม Failed/Partial/
Incomplete เดิม ไม่ถือว่าผ่านเพราะ dependency CI ผ่าน. งานนี้ไม่รับรอง Live/release acceptance.
หากพบ changed source/contract/harness ที่กระทบหลักฐานเก่า ให้ระบุ impacted proof และ
แก้ขอบเขต/ขออนุมัติตามอำนาจก่อนทดลองเพิ่ม.

## หลักฐานและการปิด checkpoint

เก็บ safe summary ใน feature evidence: baseline/candidate SHA/hashes, runtime versions,
semantic delta/optional rationale, helper provenance, install/caller/test outcomes,
scanner inventory/findings, review/fixes และ PR/CI links. Raw traces/dumps/credentials
ไม่ commit; cleanup เฉพาะ owned temporary roots/services และตรวจว่าไม่หลงเหลือ.
ไม่สร้าง documentation PR วนเพียงเพื่อใส่ CI ของ documentation PR ก่อนหน้า.

พร้อมปิดงานขอบเขตนี้เมื่อ DV-01–11 ผ่านทั้งหมด และ DV-12 ผ่านด้วยการลบ branches
ที่ครบเงื่อนไข หรือบันทึกเหตุผลที่ต้องเก็บแต่ละ branch ตามกฎ DV-12 ให้ชัดเจน.
ข้อยกเว้นการเก็บ branch ใช้เฉพาะ DV-12 ไม่ยกเว้นด่าน DV-01–11 และต้องไม่มี claimed
update ที่ยังไม่ได้ทำ. ต้องรายงาน blocker/failure ตามจริงและขั้นถัดไป; F-17 ไม่ Completed
ตามงานนี้. ข้อความ candidate checks Not Run เป็นบันทึกขั้นเสนอ; ผลปัจจุบันใช้ตารางและ dated checkpoints ด้านล่าง.

ขั้นถัดไป ณ ขั้นเสนอเดิม (historical): รอเจ้าของอนุมัติ plan + validation; หลังอนุมัติจึงทำ implementation,
review, checks และ publication ต่อเนื่องภายใต้ AGENTS โดยไม่ขอคำสั่งย่อยซ้ำ.

## บันทึกอนุมัติ

2026-11-19 เจ้าของตอบ “approve” หลังแก้ finding เกณฑ์ปิดงานแล้ว.
อนุมัติ plan และ validation ฉบับนี้ให้เริ่ม implementation/review/validation/publication
ตามขอบเขตและจุดหยุดเดิม; ข้อความรออนุมัติในเนื้อหาด้านบนเป็นประวัติขั้นเสนอ.

## Local checkpoint — 2026-11-19

[Local results](evidence/local-results.json), [semantic delta](evidence/semantic-delta.json),
[security](evidence/security-results.json), [caller proof](evidence/caller-results.json)
and adjacent install/asset/provenance receipts record executed checks. App709 tests/42files,
source/withdrawal26 tests Passed. Reference baseline and candidate lint42errors/4warnings
identical after path/format normalization; no new lint finding, template build Passed.
Initial wrong-runtime/contract-scratch/formatter/Accept-header failures remain recorded
in local-results and execution notes, not rewritten as Passed. E2E/required CI pending.
Vite main bundle delta verified against integrity-checked6.4.4 archive: changed virtual-ID
escaping/fs access checks/chunk import names; embedded matcher/watcher implementations
unchanged. Public new-version caller behavior separately proved; no broad ReDoS claim.
Latest execution entries supersede preimplementation Not Run statements above.

## Required Security finding — 2026-11-19

Initial head daa1655, Security run44455180767: CodeQL JS High file-system race in recovered
resolution helper. Corrected under recorded engineering amendment; caller12 recheck Passed,
source-symlink negative Rejected. No exception/policy change. [Fix evidence](evidence/security-finding-fix.json).
Required CI/Security on the corrected candidate remains mandatory; prior Failed retained.


## Publication closure verified — 2026-11-19

[PR #80](https://github.com/yukasung/tiewtrade/pull/80) final head
`24d8166a824ff2f281a1710a823348475dc6b4be` passed all 18 reported jobs:
[CI 44455589531](https://github.com/yukasung/tiewtrade/actions/runs/44455589531),
[Security 44455589508](https://github.com/yukasung/tiewtrade/actions/runs/44455589508).
This closes DV-05/10, including the previously pending isolated required E2E checks;
local results and the earlier CodeQL High/PR56 E2E failure remain historical results.
No required reviewer is configured on main; automated checks are not substituted for
owner trading/visual acceptance in other features.

DV-11 Passed: merge `fea157947ce7e9686275291fd435b08ff4546d3b` passed
[postmerge CI 44457883406](https://github.com/yukasung/tiewtrade/actions/runs/44457883406)
and [Security 44457883418](https://github.com/yukasung/tiewtrade/actions/runs/44457883418).
DV-12 Passed: PR50/55/56/57 are MERGED and their exact original heads are ancestors
of main. The pre-audit read-only inventory contained only local main and remote main; no open
PR or leftover dependency/integration ref. Existing backup/provenance records remain
in place; this reconciliation performs no further ref deletion.

The approved maintenance checkpoint DV-01–12 is closed. Reference inherited lint
42 errors/4 warnings and recorded Medium findings are retained with their original
scope; no security exception, assertion or severity change. F-17 remains Pending Full
Validation. Next work is the separate F-17 opening audit in its existing evidence;
no dependency implementation remains in this scope.
