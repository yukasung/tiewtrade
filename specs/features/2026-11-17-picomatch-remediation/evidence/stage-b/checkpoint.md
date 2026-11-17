# Stage B — stopped at resolver, 2026-11-18

Status: **Blocked — proposed relative override failed; one candidate only**.
No application install, policy/exception change, Git or CI. No automatic alternatives.

## What completed

- Official metadata still latest4.0.7/no patched release at start; source/head/lock/config
  identities bound in [structured result](feasibility-result.json). Node22.23.4/npm10.9.9.
- Verified upstream archiveSHA512, applied exact reviewed LP03patch with zero fuzz;
  patched parser hash matches prior provenance. Only lib/parse.js changes; package
  name/version4.0.7,manifest/license bytes preserved.
- Produced deterministic local tar bytes twice: hashes identical;sorted paths,fixed
  mtime/uid/gid/modes. Validator rejects parser tampering,wrong version,extra entry,
  absolute path,parent traversal andsymlink. No lifecycle hooks/helper dependency.
- Copied tracked frontend files to audit-owned directory, excluding private/env/cache/
  installed dependencies. Added one scratch-only override:
  picomatch → file:./vendor/picomatch-4.0.7-lp03.tgz.

## Exact failure

Ran once in scratch: npm install --package-lock-only --ignore-scripts --no-audit --no-fund.
Exit254/ENOENT. npm attempted to open:
`<audit-owned-scratch>/frontend/node_modules/fdir/vendor/picomatch-4.0.7-lp03.tgz`.
The intended artifact was at frontend/vendor/. [Sanitized log](resolver.log).

This is a failed RELATIVE override candidate. It does not prove that npm has no local-
tarball support. No absolute-path variant,alias,root direct dependency,hook,npm version
switch or alternate resolver was tried. Stop condition applies before such experiments.

## Validation disposition

SB01baseline/isolationPassed. SB02deterministic artifact and6negative casesPassed.
SB03Blocked at resolver. SB04–06NotRun (frozen installs,ignore-scripts/direct binaries,
installed caller matrix,frontend lint/typecheck/unit/build/loopback/bundle). SB07existing
Security blocker retained, no new scan. SB08cleanupPassed. SB09review of this failed
feasibility checkpoint can proceed; SB10remediation/policy acceptance remainsBlocked.
Do not describe source packaging as installed toolchain acceptance.

## Cleanup / scope

Resolver process exited; no servers,adversarial probes or background services started.
Owned scratch including tar/frontend copy/cache removed after recording hashes/results.
Actual worktree app/manifest/lock/config hashes unchanged; installed owner dependencies,
services/accounts/Live andregistry unchanged. Prior LPmatching andPaper evidence retained.
Elapsed feasibility ~1.1s (early resolver stop), not the25–50min full-stage estimate.

## Next decision

Recommended retainBlocked and prefer an official reviewed patched release; no automatic
release polling or known-blocked fullCI. If owner wants further packaging research,
prepare a narrow amendment for one absolute-path override ONLY IN SCRATCH to distinguish
path resolution from unsupported override. This would not establish portable/reproducible
app packaging: portability,installed callers andsecurity policy remain separate blockers.
No such variant is implemented/approved by this receipt. A source-policy change or exact
exception is not authorized and cannot be justified by this feasibility experiment.
