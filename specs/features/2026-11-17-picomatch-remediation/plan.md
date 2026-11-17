# Picomatch dependency remediation — Plan

สถานะ: Approved — owner approved plan/validation on 2026-11-17
วันที่: 2026-11-17
Requirements: [Approved](requirements.md)
Validation: [Approved](validation.md)

## Baseline and observed risk

Base d3c9eae; preserve other worktrees/F17 evidence. No application or dependency code
has changed. picomatch4.0.7 is dev=true in frontend/package-lock.json; direct callers
include tinyglobby,Vite,Vitest. Dev classification is not a reachability assessment.
GitHub GHSA-fc5q-39xc-vjpf lists<=4.0.7/no patched version; registry latest4.0.7 and
referenced upstream PR194 open/unmerged at previous inspection. Recheck on execution.
frontend/vite.config.ts has server.host=true; do not assume a loopback-only server.
No direct picomatch/tinyglobby/import.meta.glob usage found by initial source search;
transitive/plugin/dev-server call paths remain unproven. Do not claim unreachable.

## Reuse existing paths and patterns

- frontend/package.json/package-lock.json: existing resolver/lock and Node22 scripts.
- frontend/vite.config.ts, vitest.config.ts, playwright*.config.ts: inspect configured
  pattern sources, plugin transforms, filesystem access, server exposure and tests.
- tools/security/cli.py, dependencies.py, pins/config and README.md: checksum-verified
  OSV scanner and policy covering both application lockfiles; no scanner replacement.
- .github/workflows/ci.yml and security.yml: unchanged final required checks/postmerge.
- specs/features/2026-11-05-security-dependency-remediation/: reuse semantic lock diff,
  clean install, build/loopback smoke and sanitized evidence conventions.
No new infrastructure, permanent service, broad dependency upgrade or UI abstraction.

## Execution after plan/validation approval

1. Capture baseline HEAD, manifest/lock/config hashes, official advisory metadata and
   published registry metadata. Record dependency paths/versions/optional occurrences.
   Read caller code from integrity-verified artifacts in an isolated scratch directory;
   avoid modifying the installed environment of running apps or other worktrees.
2. Map pattern provenance from project config, source/plugin transforms, request/URL/
   websocket and filesystem entry points, test discovery and CI inputs. Inspect build
   output/module graph to determine browser bundle inclusion. Distinguish evidence of
   absence from limits of static analysis. Record exposure and concrete attack surface.
3. Run only official-advisory-derived reproductions in isolated local Node22 child
   processes: at most5probes,2s wall bound per child,256MiB heap, one child at a time.
   No network requests/listening server/owner data. Use parent deadline and terminate/
   join only its child. Record pattern category/input length/exit/elapsed/timeout; do
   not interpret a non-reproduction or timeout alone as absence/proof of the full bug.
   Include benign expected matching cases to detect false remediation. No crafted
   patterns against active Vite/CI services. Total probe stage bound60s incl cleanup.
4. Decision checkpoint BEFORE dependency edits:
   - If an official published compatible patched release exists, verify its advisory/
     upstream evidence and integrity, record exact old/new versions and dependency
     edges before updating only necessary lock entries within existing manifest ranges.
     The approved plan authorizes this compatible fix after the record is written.
   - If none exists, record Blocked and a concrete evidence-backed option. Do not
     automatically wait/poll releases or pin an unmerged PR. A fork/local patch/source
     substitution, manifest-range/major change, risk exception or policy change needs
     a separate concrete owner decision under PR-2/PR-3. No implementation before it.
5. For an authorized fix: clean npm ci with Node22 in isolated checkout; compare before/
   after lock hash and semantic diff, repeat bounded probes, run relevant tooling tests,
   frontend lint/typecheck/build. Smoke built assets and required dev transforms only
   on a disposable loopback server, no account mutation. If only lock dependencies
   change, no source refactor approval gate applies under AGENTS.md.
6. Run original pinned OSV against BOTH lockfiles with full inventory, retain sanitized
   identities/counts/SHA; unresolved High/Critical/Unknown or incomplete scan blocks
   publication. Reachability evidence cannot silently override policy. Review affected
   dependency/config evidence. If source changes become necessary, record amendment
   first and apply owner review/refactor gates; do not reuse lock-only exemption.
7. When Feature gates pass: publication under standing Git authorization, required CI
   final candidate, expected-head merge, then postmerge CI/Security. No historical
   Passed/Failed rewriting or extra recursive documentation PR for CI evidence.

## Scope, timing and stopping

Initial investigation estimate15–30min; finite bounded probes≤60s. Authorized compatible
fix local install/tooling checks estimate5–15min; required CI typically25–35min and
postmerge verification another20–30min. Notify before timed stages. These are estimates,
not acceptance thresholds or authority to add attempts. Do not run4h/100-account loads
for an unaffected development dependency. Retain applicable Paper proofs.

Stop/report when no supported fix exists, primary evidence is insufficient, requirements
conflict, or3failed attempts/time-too-long rule applies. Do not change trading/session/
API/schema/admission/Live behavior. Opening and F17Completed require remaining V18/V19/
V20 gates and dependencies; this security task alone cannot satisfy them.

## Evidence to produce

evidence/reachability.md + sanitized machine-readable summary: baseline/version/source
hashes, dependency paths, entry-point mapping, bounded probe outcomes and cleanup,
chosen fix or unresolved decision, semantic lock diff, relevant validation and final
CI SHA/links. Never publish credentials, raw security reports or scratch artifacts.

## Execution checkpoint

Approved investigation executed. Five locked source artifacts integrity verified;
5bounded probes completed with2benign correct results/3timeouts; all children joined,
scratch removed. Source/config/lock hashes unchanged. No supported published fix exists.
Stopped before dependency modification per step4. Reachability remains partial and
actual browser bundle validation Not Run. See evidence/reachability.md. No code review/
refactor or publication claimed; remediation remains blocked and owner decision required
before vendor/local-patch alternative. No automatic release polling or extra probes.

## Local-patch alternative prepared

Owner asked เริ่มทำ after investigation report. Prepared [LP-01 proposal](local-patch-proposal.md)
under PR-2; no local dependency source edits/probes executed. Proposal explicitly separates
isolated prototype from integration and any future exact owner-reviewed exception.
Await concrete decision before prototype implementation; original Security remainsBlocked.

## LP03 review and Stage B proposal — 2026-11-18

Owner requested review of LP03refactor; scoped reviewAPPROVED with no additional findings,
not full remediation acceptance. Owner then approved preparation of StageB. Draft
[Stage B plan](stage-b-plan.md)/[validation](stage-b-validation.md) select isolated native
npm local-tarball feasibility, intrinsic patched bytes rather than lifecycle-only hooks,
actual caller/toolchain/bypass proof and explicit existing scanner local-source blocker.
No StageBimplementation/install/exception approved or performed. Await document approval.

## Evidence commit checkpoint — 2026-11-18

Owner instructed commit. Include only this feature's specs/prototype evidence and its
roadmap notes; no application/dependency/security-policy change. Include explicitly
sanitized test/resolver logs despite generic log ignore. Preserve .patch/.diff bytes and
hashes: their blank unified-diff context lines necessarily contain a leading space;
Git whitespace diagnostics on those lines are patch syntax, not source trailing spaces.
Check whitespace of non-diff files separately; retain exact patch provenance. No push,
PR, CI, installation, exception or F17Completed under this commit-only instruction.
