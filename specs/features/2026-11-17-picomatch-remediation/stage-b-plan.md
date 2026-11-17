# Stage B — isolated packaging and installed-caller verification

สถานะ: Approved — owner approved isolated Stage B execution on 2026-11-18
วันที่: 2026-11-18
Base: d3c9eae; existing security/picomatch-remediation-20261117 branch.
Requirements: [Approved](requirements.md); prototype: [LP03 refactor](evidence/lp03refactor/checkpoint.md).
Validation: [Approved Stage B](stage-b-validation.md).

Owner approved preparation after scoped prototype reviewAPPROVED. This is NOT approval
to install in the owner's app, change scanner policy or create a security exception.

## Why a separate stage

LP03source fixes the targeted single-top-level-branch guard and has scoped matching/
lifecycle evidence. It intentionally changes some matching semantics; does not prove
all ReDoS variants safe. maxExtglobRecursion:false remains opt-out; multi-alternative
wildcard safety/general caller reachability remains unresolved. Packaging proof is
useful but does not turn those limits into remediation acceptance.

Rechecked official advisory/npm latest during drafting:picomatch4.0.7,no patched release.
Current tools/security/dependencies.py:45–66 rejects local links/paths and any resolved
source outside https://registry.npmjs.org/. Thus a local tarball candidate MUST currently
remainBlocked by policy. Do not plan to pass Security by renaming/version-faking it.

## Selected experimental packaging

Use a local tarball carrying exactly integrity-verified upstream4.0.7 plus the reviewed
LP03lib/parse.js diff; package name/version remain picomatch/4.0.7,MITLICENSE retained.
Store local patch ID/hash and archive/source provenance separately, not as a fake upstream
version. Bind every tar entry (content/path/type); deterministic sorted packaging with
fixed timestamps/ownership and no absolute/parent-traversal/link members. Rebuild twice
and compare hash. Preserve all other upstream files and manifest bytes.

In an AUDIT-OWNED frontend copy only, propose native npm overrides for picomatch to that
immutable local tarball. No postinstall/patch-package or new helper dependency. First
prove npm10/Node22 accepts the tarball override, frozen npm ci and actual transitive
resolution. A planning choice is not evidence of npm support. If resolver rejects it,
stop/report instead of silently switching to hooks/forks/other npm versions. Do not
alter actual repo frontend manifest/lock/node_modules while exploring this candidate.

This makes patched source part of installed bytes independent of lifecycle scripts IF
npm feasibility succeeds. npm ci --ignore-scripts and direct binaries must still be
verified. A postinstall-only patch would leave a known bypass and is not the selected
approach. No publication of tarball to npm/GitHub registry is authorized.

## Reuse and isolation

- frontend/package.json/package-lock.json, Node22 and existing npm scripts/configs.
- LP03reviewed patch/source hashes/license and LP03refactor bounded runner/cleanup.
- tools/security/dependencies.py/cli.py and original scanner policy, unchanged.
- Existing frontend tests/lint/typecheck/build and Dockerfile's Node22 conventions.
- Existing test/resource ownership and sanitized evidence patterns; no new infrastructure.
Fresh scratch copy excludes .git/node_modules/.env/build outputs/private artifacts. Only
synthetic filesystem fixtures and loopback smoke; no real owner session/API/exchange.
Record owner marker and pre/post main worktree hashes. No unrelated service stopping.

## Execution after Stage B plan/validation approval

1. Recheck official published fix once. If one exists, report the supported-upgrade option
   under original plan before spending effort on local packaging; no automatic scope mix.
   Pin candidate/config/patch/license, installed runtime versions and original archive.
2. Verify/rebuild the exact patched artifact; byte-compare all contents against original,
   allow only lib/parse.js diff. Reproducible packaging test includes tampered source/hash,
   wrong version,extra path/link rejection. Reuse scanner helpers only as supported APIs.
3. Resolver feasibility: exactly one candidate resolution using npm install --package-lock-only
   --ignore-scripts in scratch, then isolated npm ci. Record semantic manifest/lock delta,
   all picomatch occurrences/caller edges/integrities. Stop if unsupported or unrelated
   dependency churn cannot be explained. No fallback package tool or version replacement.
4. Prove installed source paths/hashes from each Vite/Vitest/tinyglobby/fdir caller where
   present, normal clean install and an independent --ignore-scripts clean install. Keep
   baseline app lockfiles intact. Test missing/tampered artifact fails installation or
   verification, never silently falling back to upstream vulnerable bytes. Record limits
   of installer behavior versus verification checks separately.
5. Before timed caller probes, freeze the exact finite API/fixture/expected-result matrix.
   At most8sequential child probes,2s/256MiB each,30s total incl owned cleanup. Include
   original adversarial category and ordinary glob through supported Vite/tinyglobby/fdir
   public interfaces where available; verify Vitest discovery with its real test command
   on harmless fixtures. Do not claim a resolved module path alone proves the actual
   public call path. No hostile inputs sent to an active server. Existing library-only
   matrices may be retained when installed parser hashes match; do not repeat for ritual.
6. Existing frontend lint/typecheck/unit tests/build in scratch. Pin output/module graph
   to assess picomatch inclusion, inspect actual bundle rather than dev-label assumptions.
   Start only owned Vite/preview processes on127.0.0.1 with strict available ports; GET
   HTML/module/assets and normal transforms, no API/WS/account mutation. Observe actual
   loaded picomatch paths/hashes with a bounded harness if needed; observer does not
   replace unobserved direct binary invocation (--ignore-scripts bypass check).
7. Run original scanner inventory against both lockfiles on baseline/candidate copies.
   Record baseline High and candidate UNSUPPORTED_PACKAGE_SOURCE/other failures honestly.
   Expect local-source blocker under existing policy. No scanner edits, exceptions,
   reduced coverage, npm-version forgery or clean-scan claim. This is NOT a criterion
   allowing app release with unresolved Security. Do not launch full CI known to block.
8. Join owned children/servers, prove ownership before deletion and remove scratch; keep
   sanitized artifact hashes/diffs/results. If cleanup fails retain resources/report,
   never force-drop unrelated resources. Stop for review and the next explicit decision.

## Outcomes / next decisions

A: Feasibility unsupported → reportBlocked with exact npm diagnostic, preserve evidence;
no repeated override variants/hook experiments automatically.
B: Installed packaging/caller checks pass → scoped prototype evidence only. Still need
full advisory/threat coverage decision and a separately approved trusted-local-source
security policy design plus exact owner-reviewed risk exception IF those paths are
chosen. Neither is requested or approved here. No exception justified merely by tests.
C: Official patched release becomes available → prefer supported remediation path and
retain local experiment results. No waiting/polling daemon is created.

No app installation, source-policy change, commit/push/CI/merge, service exposure or Live
activation in this stage. F17 original V18/V19/V20 obligations remain unchanged.

## Timing and stop rules

Feasibility/artifact/inventory estimate10–20min. If feasible, install/tooling/caller smoke
estimate15–30min; caller probe stage≤30s, announce before execution. Total expected25–50min,
not a new acceptance SLA. Stop after first failed packaging/caller stage and report;
no automatic rerun or alternative mechanism. No4h/100-account workload for dependency
packaging. General3-failure/time-too-long/unclear-safety stop rules still apply.

## Execution checkpoint — 2026-11-18

Owner approved isolated StageB. [Feasibility receipt](evidence/stage-b/checkpoint.md):
artifact/source integrity anddeterministic packaging/6negative checksPassed; native npm
relative override failed once withENOENT under fdir's directory. General local-tarball
support unproven. Stopped at step3; no alternative override or installed caller stage.
Scratch removed,app baseline unchanged. Await decision; policy/advisory gates retained.
