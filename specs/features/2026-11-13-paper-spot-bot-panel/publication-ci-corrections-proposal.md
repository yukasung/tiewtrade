# PR69 publication corrections

สถานะ: **Approved — เจ้าของสั่ง “เริ่มทำ” หลังเสนอแก้ 4 จุดและตรวจ CI ใหม่**
Candidate: `f239ef4`; dependency navigation `4a9b46a`.

## Evidence

- CI: https://github.com/yukasung/tiewtrade/actions/runs/43459512564
- Security: https://github.com/yukasung/tiewtrade/actions/runs/43459506546 — Passed.
- Frontend: 686 tests passed; E2eEnvironment suite fails before running because browserSetup.ts accesses window in the node environment.
- Browser: 33 passed / 3 failed. paper-wallet width382 exceeds viewport360; dense-workspace requires scrollTop>0 although bot panel is shorter; trading-account locator retains the closed-state accessible name after opening the menu.
- Backend completed Passed, including isolated integration and migration checks. No reruns.

## Proposed scope

1. Guard browser-only setup for browser environments; keep E2eEnvironment in Node and retain isolation assertions. This belongs to the navigation dependency.
2. Reproduce paper-wallet overflow at360px with element bounds before changing layout. Fix only the responsible responsive element; keep no-horizontal-overflow criterion360px.
3. Update dense-workspace assertion to prove controls are reachable and draft persists, requiring internal scroll only when content exceeds the viewport. Retain long-content scroll proof.
4. Use a stable menu locator through its open/closed accessible names; keep expanded state, Escape/focus and close-button assertions.
5. Targeted unit/browser/static validation, then publish one corrected candidate if authorized. Do not change trading rules, money assertions, timeout limits or security policy.

Navigation is published as a base branch only, not merged. Correct dependency and bot-panel changes in their respective branches; no force push or merge. Retargeting to main and final required checks remain separate gates after navigation is ready.


## Implemented and locally validated

Dependency commit14c62e6 guards DOM setup, uses stable menu locator and waits for the expected responsive menu before capture. Combined branch integrates that dependency without merging any PR. Dense-workspace test now requires scrolling only for actual overflowing content and explicitly checks Start in viewport/disabled plus the existing draft assertion.

67 targeted unit tests, frontend lint/typecheck and 3 targeted real-DB browser cases Passed (27.9s). Wallet diagnosis initially passed unchanged locally; bounds at360px fit. No CSS patch was justified: strict viewport assertion remains, with element-bounds-only failure attachment to diagnose any persistent Linux overflow. This issue still needs CI confirmation; local pass is not proof of the original CI cause. No trading/API/timeout/security changes.

Next: one new publication candidate and same-SHA Security; stop and report new failures. No PR merge.
