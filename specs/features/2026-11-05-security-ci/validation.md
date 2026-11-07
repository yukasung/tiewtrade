# Security CI — Validation

สถานะ: **Approved — เจ้าของสั่ง “แก้ไข” implementation blocker ตามแผนและเกณฑ์นี้ 2026-11-05**

**Approved amendment2026-11-07 (F17 Option A), Feature:** verify unchanged occurrence
identities/locators and fail-closed behavior after batched Git reads; real scanner
history/tree and rename/reintroduction coverage remains mandatory. V-05 additionally
requires strict immutable evidence schema/config-digest coverage, exact deduplicated
counts, missing/invalid approvals rejected, changed blob/path/commit/rule/new matches
not excepted, and a real new credential in approved or unapproved files blocked.
Group only resolved artifact findings in bounded public output, with explicit counts
and no raw secret text; unresolved output bounds still fail closed. Use safe local
timing/count evidence before a full required-CI run; keep15min timeout. New amendment
validation is Pending until current-candidate tests and remote CI pass; historical
Passed evidence below is not certification of this change.

Option A scoped local checks:46policy tests (42passed/4opt-in skipped), plus3pinned
Gitleaks probes passed; original/optimized147-occurrence identity/locator parity
passed in history and tree modes. Seven files Ruff/format and six files strict mypy
passed. Full local/remote candidate checks still pending. See
[implementation receipt](../2026-11-02-tp-sl/evidence/recovery-20261106/evidence-policy-implementation.md).

Option A full local result: scanner/mapping stages169.73s, but registry validation
**Failed — EVIDENCE_BINDING_MISMATCH**. Tree reports100additional identities with
different columns on the same8immutable blobs. Existing approval not expanded;
new column-variation fail-closed regression passed. Pending owner decision on
[exact data extension](../2026-11-02-tp-sl/tree-occurrence-extension-proposal.md),
then full local identity validation/required CI. No new remote-CI success claim.
วันที่: 2026-11-05
Requirements: [Approved](requirements.md); implementation: [plan.md](plan.md)

## เสร็จหมายถึง

ด่าน Feature V-01..18 ผ่านบน candidate สุดท้ายก่อน merge และ Release checkpoint V-19
หลัง merge ผ่านก่อน Completed พร้อม review/required CI และ GitHub settings evidence ครบ.
การอนุมัติเอกสารหรือ scanner ติดตั้งสำเร็จ
ไม่ใช่ Passed. **Feature validation V-01..18 ผ่านสำหรับ head 34c146a/base 98ff2f8 แล้ว**;
ดู [หลักฐานปัจจุบัน](evidence/rollout-20261106.md) และ
[billing verification](evidence/billing-budget-verification-20261106.md).
เจ้าของสั่ง merge แล้ว; final candidate 9286d5f และ merge SHA 74ca1f4 ผ่าน required CI/security
พร้อม main dispatch/readback ครบ V-19 Passed ตาม [post-merge evidence](evidence/post-merge-20261106.md).

| รหัส | เกณฑ์ / Requirements | วิธีตรวจและผลที่ต้องได้ | ระยะ | ผล / หลักฐาน |
|---|---|---|---|---|
| V-01 | เครื่องมือฟรีและ pins — RQ-1/9 | ตรวจ public repo/standard runners, full action SHAs, CLI/bundle checksum verification; ไม่มี paid add-on/larger runner; ตรวจ artifact/cache budget และ retention | Feature | Passed — public standard runners/pins/checksums/real bundles, bounded safe-only artifacts/cache และ retention ผ่าน; owner Usage billed 0 + Actions/Packages budgets 0 พร้อม Usage blocked, included usage alerts On; billing-budget-verification-20261106.md ระบุข้อจำกัด shared remaining storage ที่ไม่แสดง โดยไม่อนุญาต paid expansion |
| V-02 | Candidate identity — RQ-6/8/11, §6.1 | PR merge SHA ตรง head/base; head หรือ base เปลี่ยนต้องปฏิเสธ manifest เก่า; test run/attempt mismatch และ strict protection ที่ main | Feature | Passed on 34c146a — current-candidate-manifests.json ผูก head/base/merge/run/attempt/config ตรงกันครบ; stale identity regression ผ่าน; strict readback true (activation proof ยังอยู่ V-14) |
| V-03 | Secret history/tree coverage — RQ-2 | Gitleaks จริงกับ temp Git repo: เพิ่มแล้วลบ secret ภายใน PR ยังพบ, secret ใน candidate tree พบ; first origin scan บันทึก refs/SHAs และไม่เป็น shallow; contextual sealing/venue rules มี positive/negative cases | Feature | Passed on 34c146a — full history/tree 238 commits, 92 exact approved exceptions, 0 blocked/triage; initial origin snapshot 246 commits และ real history/tree contextual probes ใช้หลักฐานเดิม |
| V-04 | Secret redaction — RQ-3/11 | ส่ง synthetic sentinel ผ่าน finding, parser failure และ tool stderr; stdout/summary/manifest/artifact ต้องไม่มี sentinel หรือ raw match/snippet/token/URL credential; raw temp ไม่ upload | Feature | Passed on 34c146a — redaction/error-path sentinels ผ่าน; ตรวจ manifests มี safe fields ครบ 5 ไฟล์เท่านั้น; remote CodeQL logs/reporting ไม่มี raw SARIF/database upload |
| V-05 | Exceptions/remediation — RQ-3/6/7, §6.2 | approved exact occurrence พ้น blocker; secret เดิม revoke แล้วมีหลักฐานผ่านเฉพาะ occurrence เดิม; ไม่มีหลักฐาน, commit/path/rule/เนื้อหาเปลี่ยนหรือเพิ่ม occurrence ใหม่ยังบล็อก; inline allow/baseline/blanket ignore ไม่หลบ gate | Feature | Passed on 34c146a — 92 exact exceptions ตรง owner approval; remote scan 0 blocked/triage; occurrence/rename/deletion regressions ผ่านตาม review-fixes.md |
| V-06 | Dependency inventory — RQ-4 | OSV จริงอ่าน uv.lock/package-lock.json; เทียบครบ direct/transitive/dev/optional กับ parsed inventory; test missing lockfile, unsupported source, scanner omission และ API error ต้องไม่ให้ Passed; ไม่ execute lifecycle scripts | Feature | Passed on 34c146a — real OSV 464 inventory entries ตรง backend/frontend locks; missing/unsupported/omission และ execution/API failure tests ใช้หลักฐานเดิม; remote marker guards ไม่พบ lifecycle execution |
| V-07 | Dependency policy/severity — RQ-6/7, §6.3 | fixture scores 0/3.9/4/6.9/7/8.9/9/10; High/Critical รวมไม่มี patched version บล็อก; Low/Medium รายงาน; missing/invalid/out-of-range/group conflicts เป็น Needs Triage; แสดง advisory source/mapping ย้อนกลับได้ | Feature | Passed on 34c146a — numeric/vector/group/unknown regressions ผ่าน; real OSV 464 entries, 0 High/Critical/unknown/triage, 4 Medium records; ไม่มี dependency exception |
| V-08 | CodeQL coverage — RQ-5/6 | real CodeQL extracts Python, JS/TS, Actions และได้ full SARIF; known synthetic insecure/fixed snippets ถูกตรวจ/หายตามคาด; missing language/empty extraction/analyze error ไม่ผ่าน; exclusions ตรง plan | Feature | Passed on 34c146a — remote CodeQL Python 855, JS/TS 176, Actions 3 files; expected/extracted coverage ครบ; local pinned CLI paired unsafe/safe probes ทั้ง 3 ภาษาและ negative coverage tests ผ่าน |
| V-09 | CodeQL parser/policy — RQ-6/7, §6.3 | SARIF driver/extensions, rule lookup, security score boundaries; security metadata หาย/ผิดเป็น Needs Triage, generic warning ไม่ถูกแปลงเป็น High; raw message/snippet ไม่ออก report และ candidate suppression ไม่ใช่ approval | Feature | Passed on 34c146a — real grouped SARIF 3 ภาษาและ driver/extensions/reference/unknown/suppression/privacy tests ผ่าน; compatibility-decision.md เก็บ failures เดิมและ owner-approved bounded fix |
| V-10 | Findings เดิมกับ remediation PR — RQ-4/6, §6.1 | คู่ baseline/candidate: High เดิมไม่ถูกแก้ยังบล็อกแม้ diff ไม่แตะไฟล์/lockfile; candidate แก้แล้วผ่านโดยไม่ต้องรอ main alert ปิด; รวม dependency และ SAST; scanner ผลเก่าต้องไม่แทน candidate ใหม่ | Feature | Passed — retained-finding-proof-20261106.json: hosted run 42152916345 มี baseline/README-only/fixed ต่อ scanner; OSV 3 blocked → 3 blocked → 0 และ CodeQL Critical 1 → 1 → 0; input hashes/diffs ยืนยัน unchanged inputs และ fresh CodeQL database ต่อ phase |
| V-11 | Fail-closed aggregate — RQ-7/8 | success ครบเท่านั้นผ่าน; omitted/skipped/cancelled/timed out job, malformed/missing report, SHA/tool/schema mismatch และ tool execution failure ต้องแดง; findings exit code ไม่ถูกเหมารวมเป็น error หรือ success | Feature | Passed — non-success/missing/skipped/stale/schema/count regressions; real negative 42148532565 failed Python + aggregate ตาม Critical 1, corrected final Security 42152916345 ผ่าน 7/7 พร้อม manifests ครบ 5; compatibility failures เดิม fail closed และเก็บผลเดิมไว้ |
| V-12 | PR permissions — RQ-9; owner-approved alternative 2026-11-05 | static per-job/action contract + repository settings readback + real same-repo PR effective token permissions ไม่มี write + disposable scanner marker probes ไม่ execute entrypoint/lifecycle; หลักฐานผูก run/head/base และคงข้อจำกัด fork runtime ยัง Not Run ตาม requirements/plan amendment | Feature | Passed under approved alternative — static contracts, 7 jobs effective read permissions และ settings readback ผ่าน; PR #49 marker guards ก่อน/หลังครบ 5 jobs พร้อม local positive controls (marker-probes-20261106.json); actual fork Not Run — accepted evidence gap |
| V-13 | Workflow triggers/schedule — RQ-2/4/5 | actionlint และ trigger matrix ครบ PR/main push/daily/manual, ไม่มี paths filter ทำ gate หาย; PR จริงเดินทุก component; ตรวจ cron UTC/ไทยตรง plan และไม่มี CodeQL default setup ซ้ำ; main dispatch จริงอยู่ V-19 เพราะ workflow ใหม่ต้องเข้า default branch ก่อน | Feature | Passed on 34c146a — PR จริงรันครบทุก component; actionlint/PR-main-daily-manual contract ผ่าน, cron 03:17 UTC = 10:17 ไทย; default setup not-configured; main dispatch อยู่ V-19 |
| V-14 | Required checks/activation — RQ-8/11 | snapshot/readback 6 checks เดิม + Security / gate พร้อม app IDs; strict/admin/no-force/no-delete คงเดิม; ตรวจ lock→configure→readback→unlock ตาม plan และ failure recovery ไม่มี merge gap | Feature | Passed — activation-20261106.json: read-before-write → lock → add Security / gate app 15368 → readback → unlock; 6 original checks/app IDs, strict/admin/no-force/no-delete และ fields อื่นคงเดิม; 2 rejected API requests ก่อนแก้ serialization ไม่เปลี่ยน settings |
| V-15 | Native security settings — RQ-2/4/5 | API/UI readback secret scanning/push protection, dependency graph/alerts/security updates เปิด; CodeQL ใช้ advanced เท่านั้น; ตรวจ native alerts โดยไม่เปิดเผยค่าและไม่มี auto-merge/paid features | Feature | Passed — native-settings-20261106.json: secret scanning/push protection, vulnerability alerts + dependency graph, Dependabot security updates enabled; default setup not-configured; validity/non-provider checks disabled; alert-count snapshot ไม่มี secret/raw payload |
| V-16 | Remote rejection proof — RQ-6/7/8 | บน disposable validation PR ที่เจ้าของอนุญาตให้ push ใช้ synthetic non-credential violation ให้ gate แดงและ mergeability ถูกบล็อกจริง; แก้กลับให้เขียว; ไม่ merge negative fixture เข้า main ไม่ใช้ secret จริง | Feature | Passed — PR #49 negative a40f491: original CI 6/6 ทั้ง push/PR + required Security gate failed, mergeStateStatus BLOCKED; final fixed 5054226: Security 7/7 + CI 6/6 ทั้ง push/PR, mergeStateStatus CLEAN; fixed-repair-proof-20261106.json; ปิด PR โดยไม่ merge |
| V-17 | Trading/stateless regression boundary — RQ-10 | diff ยืนยันไม่มี app/DB/session/trading behavior change, scanner ไม่มี exchange calls; required CI เดิมผ่านบน final candidate รวม safety/auth/RLS/Paper isolation; หาก harness/config กระทบ tests เดิมให้ rerun เฉพาะที่กระทบ | Feature | Passed on 34c146a/base 98ff2f8 — no feature application/trading/DB/session change; required push 42148393043 และ PR 42148399157 CI ผ่าน 6/6 ต่อ run รวม F-17 + safety/auth/RLS/Paper regression |
| V-18 | Review และ final candidate — RQ-8/11 | Ready for Code Review→owner review→แก้→owner refactor decision ตาม AGENTS; review ปิด, V-01..17 และ required CI/security ผ่านบน final head/base; รอเจ้าของสั่ง merge | Feature | Passed — final candidate 9286d5f/base 98ff2f8 ผ่าน Security 42158483332 (7/7) และ PR/push CI 42158483256/42158478522 (6/6 ต่อ run); preflight/readback/tree match ผ่าน; owner-authorized squash merge เป็น 74ca1f4 โดย expected-head guard ไม่มี bypass |
| V-19 | Post-merge activation — RQ-8/11 | หลังเจ้าของสั่ง merge ติดตาม CI/security บน merge SHA, readback settings และ workflow_dispatch บน main ผ่านครบทุก component; เก็บ run URLs/SHAs ปิด evidence ก่อน Completed โดยไม่ประกาศ app release/Live ready | Release | Passed — merge SHA 74ca1f4; CI 42160689488 ผ่าน 6/6, push Security 42160689507 และ main dispatch 42161218096 ผ่าน 7/7 ต่อ run; manifests/identity/config/tree/readback ครบ; evidence/post-merge-20261106.md และ .json |

## การเลือกตรวจตามผลกระทบ

- Adapter/policy เป็น logic ใหม่ที่ตัดสิน merge: ใช้ stdlib unittest กับ report fixtures
  ที่ไม่มี secret จริง และ scanner integration ใน temp directory; ไม่อาศัย mock อย่างเดียว
  เพื่ออ้างว่าเครื่องมือจริงอ่าน lockfiles/SARIF ได้.
- Workflow/settings เป็น contract กับ GitHub: ใช้ actionlint, readback และ check runs จริง;
  positive/negative remote proof เสริม unit tests ไม่ใช่ทำซ้ำโดยไม่มีสิ่งที่พิสูจน์เพิ่ม.
- ใช้ tests เดิมที่ plan ระบุสำหรับ application safety ผ่าน required CI; ไม่รัน full suite
  ในเครื่องเพิ่มเพียงเพราะเปลี่ยนเอกสาร/CI. ไม่แก้ `.github/workflows/ci.yml` เพื่อลด tests.
- Tool version/config, exclusions, parser schema, exception registry, workflow permissions,
  head/base SHA หรือ GitHub rules เปลี่ยน → ผลที่เกี่ยวข้องต้องตรวจใหม่.
  เมื่อพบ advisory ใหม่จาก scheduled scan ให้ประเมินผลต่อ candidate ที่กำลังจะ merge
  และ rerun security checks ที่ผลเดิมไม่ครอบคลุม advisory ใหม่นั้น.
- ไม่มี Batch/workload ใหม่ใน scope นี้. Release checkpoint V-19 เป็นการตรวจการเปิดใช้
  security CI หลัง merge โดยทันที ไม่ต้องรอ application release หรือชุดที่ 9.
  งาน application ที่เลื่อนไว้ใน roadmap ยังคงผล/ระยะเดิม;
  ไม่ใช้ security CI ผ่านมาปิด Pending Full Validation ของ feature อื่น.

## เทสต์ที่ต้องมี

- ตัวเลข: severity thresholds เท่านั้น ไม่แตะ Money/Quantity หรือสร้างกฎการเงินใหม่
- คุณสมบัติ: เปลี่ยน identity/เพิ่ม occurrence/ทำข้อมูล severity หายต้องไม่เปลี่ยน Blocked
  เป็น Passed โดยไม่มีหลักฐาน; ใช้ table-driven tests ไม่เพิ่ม framework ถ้า tests เดิมเพียงพอ
- ความปลอดภัย: no-live-order/no-credential-use, read-only PR, redaction ใน error path,
  missing scans fail closed, exact exception matching และ latest candidate binding
- ตัวอย่าง insecure source/credentials สร้างชั่วคราวจาก synthetic data; ไม่ commit
  credential ที่ใช้ได้หรือ secrets ลง public repo เพื่อทดสอบ scanner

## ตรวจด้วยมือและข้อมูลที่เก็บ

1. ยืนยันหน้า Settings/API ให้ตรง snapshot/ค่าที่ plan ระบุ รวม quota และ default token.
2. ตรวจ summary ของ PR: เห็น candidate identity, tool versions, coverage, findings by severity,
   Needs Triage และ exception references โดยไม่มี secret/snippet/raw error payload.
3. ตรวจ GitHub mergeability ของ negative fixture และ final positive candidate;
   ไม่ใช้ admin bypass และไม่ merge fixture. การ push/fork/เปิด PR รอคำสั่ง Git จากเจ้าของ.
4. Secret native push protection ตรวจสถานะเปิดและขอบเขตที่ GitHub รองรับ;
   ไม่ใช้ credential จริงทดลอง push และไม่อ้างว่า native detector ครอบคลุมทุก secret type.
5. บันทึก evidence ใน `evidence/feature-candidate.md`: SHA/run URLs/เวลาตรวจ,
   safe settings snapshot/diff, tool/config digests, ผลแต่ละเกณฑ์และรายการค้าง.
   หากพบ secret จริง บันทึกเฉพาะ locator กับสถานะ triage ไม่แนบ raw reports.

## ด่านและขั้นตอนปิดงาน

- ระหว่างพัฒนา: targeted unit/integration + actionlint + Ruff/format/mypy เฉพาะ helper
  โดยใช้เครื่องมือเวอร์ชันที่ repo ใช้อยู่ ไม่เพิ่มการรัน app DB/browser โดยไม่มีผลกระทบ.
- ก่อนแจ้ง Ready for Code Review: โค้ดครบ plan, targeted checks ผ่าน และแจ้ง V ที่ยังรอ remote
  ตามจริง. หยุดรอคำสั่ง review; ไม่เริ่ม review/fix/refactor เอง.
- ก่อน merge: Feature gates V-01..18 ทุกข้อผ่าน, review ปิด, required CI/security
  บน candidate สุดท้ายผ่าน รวม activation V-14/V-15 และ rejection proof V-16.
- หลัง merge ที่เจ้าของสั่ง: Release checkpoint V-19 รวม post-merge checks/settings
  และ manual dispatch บน main ต้องผ่านก่อน Completed. หากยังค้างให้ระบุ Not Run/Partial
  และ dependency/ขั้นถัดไปตามจริง.
- ชุด scanner remote ครั้งแรกคาดประมาณ 15–30 นาทีโดย matrix ขนาน (ไม่ใช่ SLA);
  ขึ้นกับคิว/ดาวน์โหลดและขนาด repo. แจ้งประมาณใหม่ก่อนรันจริงหากหลักฐานเปลี่ยน.
  ไม่รัน performance/endurance ของระบบเทรดสำหรับงานนี้.

หลักฐานการแก้ findings: [review-fixes.md](evidence/review-fixes.md).

ผลหลัง refactor: [refactor-validation.md](evidence/refactor-validation.md).

Triage 92 findings ครบแล้ว: [ข้อเสนอและ owner decisions](evidence/secret-triage.md).
เพิ่ม 92 exact exceptions ตาม owner approval แล้ว; local secret snapshot ผ่าน แต่ dependency blockers ยังต้องแก้ตาม [ข้อเสนอแยกงาน](evidence/dependency-remediation-proposal.md).

ผลใช้ exceptions: [approval และ re-scan](evidence/exception-approval.md).

## Latest remote checkpoint - 2026-11-05

Security run [42062182504](https://github.com/yukasung/tiewtrade/actions/runs/42062182504)
on head `10380f4ee9d7aa99850eba72abe01a2ddb25dddd` passed all seven jobs,
including all three real CodeQL languages and the aggregate.
See [bounded compatibility result](evidence/compatibility-decision.md) and
[safe manifests](evidence/remote-candidate-manifests.json). Earlier rows describe
local checkpoints; this evidence supersedes their pending-real-SARIF statements,
but does not close their other pending criteria. Dependency remediation is integrated;
current inventory has no High/Critical/unknown records, with four Medium records.

V-12: the owner approved the alternative evidence method on 2026-11-05; see
[evidence/fork-validation-amendment-proposal.md](evidence/fork-validation-amendment-proposal.md).
The amended criterion remains Partial until all replacement evidence passes. Real fork
execution remains **Not Run — accepted evidence gap**; same-repo results are not a fork
test. Test a real fork before accepting merge of the first fork PR. This amendment is
not a Passed result or merge authorization.
Real paired CodeQL probes are complete for all three languages; unsafe Python/JS
Critical findings are blocked and all safe counterparts have zero findings. See
[evidence/codeql-compatibility-probes.json](evidence/codeql-compatibility-probes.json).
V-14/V-15/V-16/V-19 remain Not Run; settings have not been changed.

Latest ordinary CI on the same head completed successfully:
[PR 42062182443](https://github.com/yukasung/tiewtrade/actions/runs/42062182443) and
[push 42062165730](https://github.com/yukasung/tiewtrade/actions/runs/42062165730),
6/6 jobs each. This provides current V-17 regression evidence; it does not close
activation/rejection/marker checks or authorize merge. All seven Security jobs have
read-only effective scopes; repository readback is recorded in
[evidence/pr-effective-permissions.json](evidence/pr-effective-permissions.json).

## Current rollout checkpoint - 2026-11-06

See [rollout-20261106.md](evidence/rollout-20261106.md) for the current head/base,
activation timeline, candidate manifests and real negative/fixed evidence. Earlier
checkpoints remain historical; their pending activation/dependency/CodeQL statements
are superseded by this checkpoint, not silently reclassified as passed.

Local V-10 follow-up could not finish: CodeQL extraction ran out of local disk space,
Docker Desktop was unable to start, and the local OSV follow-up returned a scanner
execution error after its baseline. Only task-owned partial extraction/archive was
removed; user files, Docker images/containers and production data were untouched.
Those local attempts are not used as Passed evidence. The approved controls were
then run on the existing standard GitHub runner in disposable PR #49 instead:
[Security 42152916345](https://github.com/yukasung/tiewtrade/actions/runs/42152916345)
passed all seven jobs, including fresh baseline/unrelated/fixed scans for both tools;
see [retained-finding-proof-20261106.json](evidence/retained-finding-proof-20261106.json).
No scanner, policy threshold, exception or production application code changed.

Native alerts are broader than the approved app inventory: 4 Medium frontend records
and 14 reference-template records, including 5 High. All High records are in the
excluded reference template; they remain open and require a separately authorized
remediation scope. See [native alerts](evidence/native-dependabot-alerts-20261106.json).
Actual fork execution remains Not Run under the owner-approved evidence amendment.

## Owner billing evidence received — 2026-11-06

[billing-budget-verification-20261106.md](evidence/billing-budget-verification-20261106.md)
closes V-01 using the owner's effective zero-budget/blocked readback together with the
existing repo storage/retention and successful real-run evidence. Earlier pending billing
entries remain historical. No numeric account remaining capacity or retroactive invoice
guarantee is inferred. V-01..18 are passed for unchanged head 34c146a/base 98ff2f8;
pre-merge current-candidate checks and owner merge command remain required.
V-19 is still Not Run — Pending Full Validation, and this feature is not Completed.

## Final post-merge checkpoint — 2026-11-06

V-19 Passed on `74ca1f4bc8118f119d9bdd96381c061b961650ee`; see
[evidence/post-merge-20261106.md](evidence/post-merge-20261106.md). This supersedes the
earlier pending merge/Release entries for this feature only. Actual fork execution
remains Not Run under the approved alternative; the real-fork precondition and
reference-template alerts remain documented risks. No application Batch/Release
validation is closed by these CI results. Current project status is in roadmap.md.
