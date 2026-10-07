# F-08 single-account implementation — review issue 3

Date: 2026-10-07. Owner requested fix issue3; branchfeature/f-08-single-trading-account.
Baseline7efbbfb, working-tree review; no commits/push/merge.

Implemented: one stored credential per user across all statuses, DB UNIQUE(user_id),
server preference null until explicit MANUAL/BOT selection with own ACTIVE key and
fresh non-recovery TOTP. Selection is atomic with UUID+use-only audit, fail-closed
against changes with unknown activity, and never grants trading capability.
Removed wallet registry/routes/DTO/UI/binding/disconnect audits and quota6.
Kept TailAdmin, shared identity cache, key verification/retry/delete/auth lifecycle,
E2E database guards and one main landmark from issue1/2 repairs.

OriginalDB metadata-only precondition: revision0010, wallet_registry absent,
zero owners with multiple keys. Old0012 was unapplied. Existing user DB was not
migrated/reset/truncated; the new schema was validated only on disposable databases.

## Verification

- Backend full1480passed,0failure/error/skip;1opt-in venue_contractdeselected,
  3inherited deprecationwarnings,80.03s. XML counts independently confirmed.
- Infra/audit/migration/key/worker281passed; HTTP/auth/key/routes91passed.
  Controlled initialselection/select-versus-delete/keyinsert races; ownerRLS/actualroles;
  no secret read; atomic auditrollback; multiple-key upgrade refusal preserves data;
  populated downgrade refusal and allowed cycle preserve immutable audit.
- Frontend85passed/9suites, lint/typecheck/build pass. Shared exact invalidation on
  key CRUD/retry/poll, stale labels, sanitized errors, no TOTP mutationvariables,
  late GET/POST owner isolation, explicit initial choice and cap1allstatuses.
- Final E2E8passed30.6s, actual API/roles/DB/FakeVenue worker; selectBOT/reload/
  deletekeyretainsuse/logout. Current-period OTP, 360px/keyboard/sidebarfocus,
  native auth styles, no browser errors/credential storage.
- Ruff/format213files, mypy196sourcefiles and6importcontracts pass.
- OpenAPI and generated frontend schemas reproduce byte-for-byte.
- Both Docker images build; Linux UI production build; APIhealth and UIproxy
  /api/health pass against disposable DB. No exchange requests/live/orders added.
- [Desktop](2026-10-07-f08-single-account/trading-account-desktop.png) and
  [360px](2026-10-07-f08-single-account/trading-account-mobile.png) inspected.

## Independent review

Backend task, frontend task and final whole-implementation reviews: PASS by
inspection, no code defect found. Task coverage request for select/delete both
lock orders resolved with actual-transaction tests; production locking passed.
Generated reproduction result completed after final reviewer snapshot.

Issue3 implementation is fixed. Overall document/review closure remains pending:
issue4 nowNC23 (future trading/manual-after-bot-stop business decision), issue5
V7 incorrectly asks directDB for HTTP409, issue6 historical research scope wording.
These are not silently treated as resolved. Roadmap remains InProgress and this
report does not approve merge or claim all original review findings are closed.
Inherited dev dependency security backlog remains documented in the superseded
wallet audit; no unrelated dependency upgrades performed.

Cleanup: only the disposable test/API/UI containers created for this work are
removed after verification; originalDB metadata is rechecked unchanged.


## Review issue 4 resolution — 2026-10-07

Owner requested fixissue4. Aligned the old stop/loss-cap manual-opening wording
with existing MANUAL/BOT exclusivity and idle-evidence mode switching. BOT stays
BOT after stop, manual opening requires MANUAL, risk reduction remains available
under existing gates for all uses. Preserved restart's no-TOTP exception and added
future trading validation cases. NC23Closed; issues5/6 remain. Documentation only,
no runtime trading changes or new test-suite claims. git diff --check passed.


## Review issue 5 resolution — 2026-10-07

Owner requested fixissue5. V7 now distinguishes authorized API409 from direct SQL
UPDATE/DELETE permission denial under tiewtrade_api with the existing preference
retained. Matches current plan/migration/HTTP and actual-role tests already in the
1480passed run. Documentation only, no runtime/schema/grant changes or new test
claims. git diff --check passed; issue6 is the remaining review finding.


## Review issue 6 resolution — 2026-10-07

Owner requested fixissue6. Research now leads with current single-account scope;
old UID/dedup/wallet replacement gates and the unsent support draft explicitly
Superseded. Historical RQ numbers distinguished from current requirements. Original
API evidence/date/links retained; key-power uncertainty tracks NC16, not a new UID
blocker. No new venue claims, network calls or messages. Documentation only;
git diff --check passed. All six review repairs implemented; final document
consistency review remains before roadmap completion.


## Final review closure — 2026-10-07

Two independent document/spec reviewers passed after issues4–6; no remaining
F-08 Spec blockers. All six review repairs closed. Research current/historical
scope, NC16risk, NC23mode rules, V7API/DB semantics and metadata-only implementation
are consistent. Code/test evidence unchanged:1480backend/85frontend/8E2E plus
static/Docker/generated checks. Roadmap updated; no commit/push/merge performed.


## Re-review findings and logout repair — 2026-10-07

Re-review found V13logout boundary retention after POSTsuccess + identityGETfailure,
and V14key-success notices preceding failed refetch. Owner requested only issue1.
AuthPanel now uses dedicated endSession: confirmed logout clears identity/auth
form before CSRF refresh and never waits for another identityGET. Late TOTP
identity callback cannot restore a logged-out or different-owner boundary.
Actual AccountSession cleanup is reused, not replaced with a second cache.

New integration tests13passed (bothlogout endpoints/error-hangfollowups/pendingGET
abort/cacheclear/pendingDELETE mutation and latecompletion/rejectedPOST/lateTOTP).
Fullfrontend98passed/10suites, lint/typecheck/build and diffcheckpass.
Actual E2E8passed33.1s with disposableDB/FakeVenue. Scope reviewPASS. Backend and
Docker suites were not rerun because this repair changed frontend auth flow only.
Only the testcontainer created for this repair is removed after verification.
Issue1fixed; issue2V14 remains. RoadmapInProgress; no commit/push/merge.


## Re-review key-feedback repair and closure — 2026-10-07

Owner requested issue2. Key add/retry/delete notices now await exact owner key
then account refetch and successful/idle/not-invalidated state. Failed refresh
shows a qualified warning and gates stale actions; manualrefresh recovers without
repeating mutation. Existing DELETE confirmation closes on confirmed DELETE.
Stale rows cannot display a successnotice. No credential variables or retries added.

New9cases failbefore/passafter; ApiKeyPanel33casesgreen. Updated DELETE integration
asserts bothpanel alerts and absence of success feedback, preserving stale-data
assertions. Fullfrontend107passed, lint/typecheck/build/diffcheckpass. E2E8passed45.4s
with isolatedactualroles/API/FakeVenue. RebuiltfrontendDocker/Linuxbuild and
APIhealth/UIproxyhealthpass. Backendcode/image unchanged from1480passed evidence.
Scope reviewPASS and both re-reviewfindings closed. No new private exchange calls,
commit/push/merge. Cleanup removes only the disposablecontainers created here.

## TailAdmin ทุกหน้าปัจจุบัน — 2026-10-07

เจ้าของอนุมัติ requirements amendment และ plan/validation ตามลำดับแล้ว
AuthLayout/sharedtheme ครอบ login/register/second-step; account/TOTP/key/trading
ใช้ controlsเดิม และhealthอยู่ในfooter/mainเดียว ไม่มีการแก้ auth/session/trading logic
Frontend113/13suites, lint/typecheck/buildผ่าน; E2E8ผ่าน26.3sบนdisposableDBแยก
keyboard/focus/disabledและ responsive brand assertionsผ่าน ภาพ23ไฟล์ใน
`2026-10-07-f08-single-account/ui-template/`; ภาพมาจากข้อมูลทดสอบเท่านั้น
Standards/spec scopedreviewsผ่านหลังปิด typographytokens/evidencegaps
Preview http://localhost:5182 อัปเดตแล้วและhealthproxyok; ไม่แตะDBpreviewหรือDBเดิม
ฐานE2Eชั่วคราวปิดแล้ว คงpreviewให้เจ้าของทดลอง ไม่มีcommit/push/merge
Backend1480เป็นbaselineเดิม ไม่ได้รันใหม่ในงานpresentationนี้
