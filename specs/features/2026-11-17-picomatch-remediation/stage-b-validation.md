# Stage B — Validation

สถานะ: Approved — owner approved isolated Stage B execution on 2026-11-18
วันที่: 2026-11-18
Requirements: [Approved](requirements.md); implementation: [Stage B plan](stage-b-plan.md).

| ID | Acceptance / evidence | Level | Current result |
|---|---|---|---|
| SB-01 | Exact parent/patch/source/npm/Node/config identities; repo app lock/manifest unchanged; audit ownership and isolated copy validated | Feature | Not Run |
| SB-02 | Exact upstream artifact SHA512; MIT license/manifest preserved; only reviewed parser diff; safe tar entry rules and two identical builds; reject tampered source/wrong version/extra entries | Feature | Not Run |
| SB-03 | Native npm override of local tarball actually resolves with Node22/npm10; clean frozen installs reproducible; semantic lock diff explained; no unsupported resolver fallback | Feature | Not Run — feasibility unknown |
| SB-04 | All installed picomatch paths from actual callers resolve to pinned patched bytes; normal and --ignore-scripts installs; direct binaries verified; tampered/missing artifact cannot silently pass verification | Feature | Not Run |
| SB-05 | Frozen finite supported-interface cases,≤8children/2s/256MiB/≤30s stage; correct expected normal/adversarial behavior and child cleanup; no claim from path resolution alone | Feature | Not Run |
| SB-06 | Existing frontend lint/typecheck/unit tests/build pass on isolated candidate; bundle/module graph evidence; ordinary loopback dev/preview HTML/module/assets work; observer and direct-binary evidence separated | Feature | Not Run |
| SB-07 | Both lockfiles retained in scanner inventory; actual existing policy outcomes documented. Local candidate source rejection remains a BLOCKER; no scanner suppression/exception/High waiver | Feature | Known Blocked — not remediation acceptance |
| SB-08 | All owned children/groups/servers joined and scratch removed or safely retained with ownership proof; no app/service/account/Live mutation; evidence sanitized | Feature | Not Run |
| SB-09 | Independent owner review of installed prototype and all remaining semantic/security limits before further scope; failed/Incomplete history preserved | Feature | Pending Review |
| SB-10 | Actual remediation requires safe-source policy, advisory coverage, exact owner exception if applicable and final required CI/postmerge under a separately approved scope | Release | Blocked — outside Stage B |

Passing SB01–06/SB08 is a scoped packaging experiment, never SecurityPassed or permission
to install into the owner app. SB07/SB10 cannot be markedPassed while existing policy
blocks source/advisory. Known global multi-alternative risk/opt-out/partial reachability
limits remain until independently resolved; prototype matching successes do not waive.

No Batch workload is introduced; reuse Paper evidence whose source/contracts are untouched.
F17 original100account/bot/notification/Live requirements remain Pending under their specs.
Draft-only checks: relative links, consistency and git diff whitespace; no install/tests
or packaging implementation until both Stage B documents are approved.

## Stage B result — 2026-11-18

[Checkpoint](evidence/stage-b/checkpoint.md):SB01Passed;SB02Passed;SB03Blocked(relative
path resolves beneath fdir → ENOENT). SB04–06NotRun after stop. SB07knownBlocked/no new
scan;SB08Passed(owned scratch removed,app unchanged);SB09PendingReview;SB10Blocked.
One resolver candidate, no variants/retries orinstall/policy/exception/Git/CI. Tar support
in general remains unproven; no installed/toolchain/security acceptance claim.
