# F-17 — Net-fee quantity and local stop readiness — Validation

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-08; ผลตรวจแต่ละเกณฑ์ยัง Not Run จนมีหลักฐาน**
วันที่: 2026-11-08 (Asia/Bangkok)
อ้างอิง: [MR-01–11 Approved A](manual-acceptance-fix-proposal.md),
[implementation plan](manual-acceptance-fix-plan.md), [validation เดิม](validation.md).

| ID | ระยะ | สิ่งที่ต้องพิสูจน์ / วิธีตรวจ | ผล |
|---|---|---|---|
| MF-01 | Feature | core golden case net0.00131868BTC/step0.00001BTC: aligned0.00131, residual0.00000868 ด้วย Quantity; aligned+residual=allocation, aligned≤allocation, deterministic; ใช้ align_quantity เดิม | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-02 | Feature | aligned input ไม่เปลี่ยนผล; zero/below-minimum/min-notional/max bounds/unsupported capability/average-price-unavailable ยังปฏิเสธ; property cases quantum18digits/หลายstep ไม่ปัดขึ้น | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-03 | Feature | setup และ exit ใช้ helper/constraints เดียวกัน; real DB bracket gross/fee/net→ARMEDเฉพาะexecutable→trigger→exit quantity ตรง; buy fee, cash/position/PnL/audit exact ไม่เปลี่ยนสูตร; residualไม่ถูกขายหรือแสดงCLOSED | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-04 | Feature | real-DB partial/late entry, terminal exit partial, zero-executable extra fill และ metadata step/filter change ก่อนtrigger/หลังqueue; exitที่ส่งแล้วไม่resizeและterminal residualไม่สร้างMARKETวน | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-05 | Feature | multi-connection trigger vs SELL/replace/cancel, TPvsSL, overlapping allocations, corrections; one winner/no oversell/no double allocation/reservation, free quantityไม่รวมเศษที่ยังผูกกลุ่ม | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-06 | Feature | transaction fault/rollback, process restart, claim takeover, dropped COMMIT ACK, source replay; exact exit identity/quantity/event/ledger เดิม, no duplicate economic effect; FAILEDเดิมไม่ถูกre-armจากdeploy | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-07 | Feature | API actual-role/auth/CSRF/other-owner/mode/episode isolation; strict string quantities, generated OpenAPI/types; covered/executable/residualตรงscope/state, missing metadataไม่อ้างcoveredหรือเรียกunknownว่าdust | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-08 | Feature | component+controlled browser→API→DB→worker→UI: net-fee bracket, ARMEDpartial coverage, residual/FAILED/EXITING/unknown/reload; ไทย/อังกฤษ, focus/keyboardและtemplateเดิม; EXITINGแสดงquantityที่queueจริง | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-09 | Feature | stop authority default-off503ไม่มีdurable request; opt-inหลังcompatible writer proofรับSTOPผ่านauth/CSRF; exact retry/key conflict/completion/restartจริง; effective API configและstop completionต้องพิสูจน์ก่อนadmission ไม่ใช้workerPID/riskREADYแทน; legacy/source-unready gateยังfailclosed, no Live order | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-10 | Feature | storage getter/getItem/setItem/removeItemโยนSecurityError/QuotaExceeded: STOPครั้งแรกยังส่งได้, มีข้อความข้อจำกัด, same mounted attempt retryใช้keyเดิม/no repeated-click duplicate; cleanupfailureไม่เปลี่ยนknown receiptเป็นunknown. ทดสอบreload/remount/owner-switchโดยstorageใช้ไม่ได้: แสดงserver statusจริง ไม่auto-send/new-key-retryหรืออ้างว่ากู้intentเดิมได้. UI stop5xxเก็บidentityและunknown, known4xxsemanticsเดิม, acknowledgementไม่เท่ากับSTOPPED; ตรวจresume/platform callersหากsharedhelperเปลี่ยน | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-11 | Feature | affected static/regression ผ่าน: Ruff/format/mypy/import-linter, frontend lint/types/tests, generated contract; core Paper/Live parity fixtures, DB concurrency/RLS/risk/stop/protection callersที่diffกระทบ | Passed local scoped evidence — see checkpoint; final review/CI still pending |
| MF-12 | Feature ก่อนmerge | owner review/findings/refactor gates และ required CI บน final published SHA ผ่าน; local evidenceไม่แทนremoteCI. Gitยังต้องownerสั่ง | Latest R1/R2 fixes, owner-authorized refactor and affected validation complete locally; publication / required CI pending |
| MF-13 | Feature local manual checkpoint | owner wallet/riskREADY/source/worker/stop authorityพร้อม; controlledfixture proofผ่านก่อน; ownerหนึ่งรอบตรวจMANUAL STOP receipt/completion/retry, expected unavailable resume และPaperTP/SLUI; ใช้หลักฐานBOT resumeแยกตามApproved A; บันทึกactualresponse/จำนวน/flags/candidateและcleanup. ไม่มีagentเลือกorderแทนowner ไม่มีLive | Partial — owner MANUAL STOP/completion observed; two clicks confirmed, two applied requests; disabled resume confirmed by screenshot. Retained BOT proof scoped separately. owner REPLACE→ARMED and CANCEL→CANCELED verified, cleanup complete/all four gates off; warning contrast remains open |
| MF-14 | Batch/Release เดิม | F17V18โปรไฟล์100บัญชี/4h และV19bot/notification/V20Liveยังคงเดิม; ไม่มีการรันหรือผลPassedเพิ่มจากamendmentนี้ | Pending Full Validation / Dependency |

## ชุดเดิมที่ใช้ก่อนเพิ่มใหม่

- `backend/tests/core/test_protections.py`: เปลี่ยน intentional off-step rejection
  เฉพาะ case ที่ MR อนุมัติ; คง reject เมื่อ aligned portion ไม่ executable.
- `backend/tests/infra/protections/{test_validation,test_lifecycle,test_review_regressions}.py`
  และ F15 matching/reservations/effective-execution tests ที่ callers กระทบ.
- API protection/manual-order และ trading-stop tests เดิม; actual runtime DB roles,
  RLS/transaction/concurrency proof ต้องใช้ PostgreSQL จริงในฐานแยก.
- frontend protection/kill-switch/journal/component tests และ browser protections เดิม.
  ใช้ controlled public feed และ native UI/fetch ไม่ปลอม serverผลลัพธ์เพื่อให้ผ่าน.

ก่อนเพิ่ม case ตรวจช่องว่างเดิมก่อน; ไม่ duplicate suite หรือสร้างtestที่แค่mirrorhelper.
ไม่ใช้float/Decimalเปล่าในfinancial oracleและไม่ใช้ผลจริงเป็นexpectedจากhelperเดียวกัน.
ไม่แตะownerDBเพื่อ fault/replay/race tests. ไม่ลดassertions/timeoutsเพื่อให้ผ่าน.

## หลักฐานและเกณฑ์หยุด

เก็บ candidateSHA/diff, code/config/runner identity, command/ผล/เวลาและเกณฑ์ที่ครอบคลุม
ในcheckpointเดียวของamendment; private owner identifiers/credentials/session cookies
อยู่นอกrepo. เก็บmanualเดิมFailedแยกจากรอบทดแทน; diagnosticsไม่ใช่acceptance.
ไม่รันใหม่อัตโนมัติเมื่อmanualรอบนี้Failed/Incomplete. ถ้า3รอบหรือownerแจ้งนานให้หยุดเสนอ.
ไม่ต้องรัน100-account/4hเพื่อปิดfixนี้ เว้นdiffพิสูจน์ว่ากระทบสิ่งที่หลักฐานเก่ารับรอง.
MF-13ผ่านไม่ได้ปิดMF-14หรือทำให้F17Completed/production-ready.

## Review checkpoint — 2026-11-08

Review R1/R2/R3 ยังเป็น implementation blockers; R4 แก้ current roadmap checkpoint
ในรอบเอกสาร. Read-only reproductions เดิม: validate_setupได้QUANTITY_NOT_ON_STEP
สองชุด; component storage getItem/setItem failure ทำให้ STOP requests0 และไม่มี
component state update. นี่เป็นหลักฐานของปัญหา ไม่ใช่ passing regression ของfix.
MF-01–13 ยัง Not Run; รอบนี้ตรวจเฉพาะเอกสาร ไม่มี source/config/runtime change.


## Implementation/checks — 2026-11-08

Owner approved revised plan/validation, superseding Proposed/Not Run development
statements above where passing evidence now exists. [Checkpoint](evidence/manual-acceptance-fix/implementation-checkpoint.md)
records per-suite scope, retained initial failures and affected rechecks. MF-01–11
are local scoped proof; MF-12/13 and MF-14 are not accepted by these checks.

Owner review and subsequent fix: [STOP lifecycle regression evidence](evidence/manual-acceptance-fix/stop-review-fix.md).
MF-10 additionally covers STOP→resume→STOP despite stale journal cleanup failure,
mounted/remounted recovery and owner switch during a pending receipt lookup.
16STOP cases passed; affected lint/types passed. This does not close MF-12/13/14.

Owner-authorized refactor: [checkpoint](evidence/manual-acceptance-fix/refactor-checkpoint.md),
16STOP tests and frontend lint/types passed. Continued local readiness as approved;
candidate/feed/risk ready, financial facts preserved. Found the MANUAL/BOT-resume
criterion mismatch before owner actions; [A/B proposal](manual-profile-clarification.md)
is Proposed and blocks MF-13 only. No replacement result or Release pass is invented.


## MF-13 approved mapping — 2026-11-08

Owner explicitly approved [option A](manual-profile-clarification.md). This resolves
the criterion mismatch without changing authorization or account type. Original
manual Failed is retained; replacement remains Not Run pending owner UI actions.
Reuse the three scoped fresh-DB BOT stop/restart/snapshot-resume proofs and16STOP
component regressions; neither is a claimed owner-browser BOT resume result.
Local health/proxy remain available; all four gates are off. No order or STOP was
submitted by the agent. First owner action is Paper STOP; verify its durable
receipt/completion before enabling admission or proceeding to owner-selected TP/SL.

Owner confirmations: [STOP observation](evidence/manual-acceptance-fix/owner-stop-observation.md).
MANUAL STOP/expected unavailable resume observed; no owner-browser BOT resume or
forced uncertain retry claimed. TP/SL and final cleanup still pending.

Owner replacement screenshot and DB now confirm one ARMED group, covered0.00131BTC
and residual0.00000868BTC; other historical group remains FAILED. See STOP observation.
MF-13 remains Partial: warning contrast concern and active-protection cleanup pending.
Do not switch protection off while active without owner disposition.

Final owner cleanup: CANCEL APPLIED revision5, no exit/new order, no unresolved
work; all four gates off. Functional manual observations accepted in their scope,
but MF-13 remains Partial for warning contrast; see owner-stop-observation.md.

Warning contrast correction: [evidence](evidence/manual-acceptance-fix/alert-readability-checkpoint.md).
Actual shared component/browser light+dark check and33affected component tests
passed locally. Owner functional manual proof retained; no extra trading round.
Final-candidate review/required CI and Release dependencies still pending.


## Latest review R1/R2 corrections — 2026-11-08

Owner requested fixes. [Evidence](evidence/manual-acceptance-fix/review-corrections/checkpoint.md).
64affected tests, lint/types and6synthetic browser scenarios passed. R1 normal STOP
now fresh after read-only received-receipt recovery; unknown retry keeps key. R2
shows actual queued quantity separately from current allocation/partial fills.
No new owner acceptance or economic real-DB proof claimed. Next owner refactor
instruction required; final CI/Release remain pending.


## R1/R2 refactor checkpoint — 2026-11-08

Owner requested refactor; [evidence](evidence/manual-acceptance-fix/review-corrections/refactor-checkpoint.md).
64targeted tests,6affected browser cases and scoped lint/types passed. No behavior/
financial rule change or owner mutation. Refactor-wait statements above retained
as history. Next requires owner Git instruction for publication/required CI.
