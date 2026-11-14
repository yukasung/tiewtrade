# PR70 cleanup diagnostic

สถานะ: **Approved — เจ้าของสั่งเริ่ม diagnostic วันที่ 2026-11-14**
วันที่: 2026-11-14 Asia/Bangkok

Candidate bfa9cd5: frontend/Security/API contract/Docker/browser57 Passed. Backend4906 Passed/1Failed at tests/infra/risk_limits/test_profile_resources.py:139; later isolated steps skipped. Initial14c62e6 run was cancelled after replacement; its F19 browser failures are retained.

Failure: cleanup_connections returns passed=False after engine.dispose(). Helper has an existing5s bound and returns remaining pid/state, but assertion does not display the result. These backend files have no diff from main. Existing log cannot distinguish a leaked connection from interference or timing; do not claim flaky or raise timeout.

## Proposed next scope

1. Add failure-only assertion evidence containing existing result(passed, remaining pid/state, seconds), plus the predeclared observer PID set and the deliberate held-connection PID. No SQL contents, credentials, owner data or production changes.
2. Run the exact test once on an isolated fresh database with existing negative leak checks and5s bound unchanged; stop/report if failure. If it passes, use neighboring resource tests to check shared-fixture interaction and report before proposing a fix or CI rerun.
3. Preserve all prior results. No automatic CI rerun, policy change, merge or main retarget. Diagnostic approval does not authorize changing cleanup acceptance.


## Publication approval — 2026-11-14
เจ้าของสั่ง “เริ่มทำ” หลังข้อเสนอส่ง diagnostic ขึ้น CI หนึ่งรอบ: อนุมัติ commit/push diagnostic และติดตาม candidate ใหม่จนจบ. คง production,5s และ assertions เดิม; เก็บผลก่อนหน้าไว้. ไม่อนุญาต auto-rerun, merge หรือเปลี่ยนเกณฑ์.
