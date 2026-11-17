# Picomatch investigation checkpoint — 2026-11-17

Result: **Blocked — no supported published patched release**. This is a completed
investigation checkpoint, not a completed remediation or F17 release.

## Baseline and verified artifacts

HEAD d3c9eae91f8fd0c0de091862106a77873d72b6b5. Manifest/lock/config hashes and package
source-file hashes are in investigation-summary.json. Downloaded5npm artifacts at
locked URLs, verified SHA512 integrity before extraction:picomatch4.0.7,
tinyglobby0.2.17,Vite6.4.4,Vitest4.1.11,fdir6.5.0. One locked picomatch occurrence,
dev=true; reverse dependency/peer edges recorded. No lifecycle scripts executed.

Official GitHub advisory GHSA-fc5q-39xc-vjpf reports affected<=4.0.7 and no patched
version. npm registry latest remains4.0.7. Referenced upstream PR194 is open/unmerged;
its title alone does not establish a fix for this advisory. No safe published upgrade
was selected, no lockfile/application edits made. Neither unmerged code nor fake
version metadata is an authorized remediation.

## Static pattern provenance

| Path | Observed source/sink | Limit / conclusion |
|---|---|---|
| Vite createFilter, dist/node/chunks/dep-3O3b9SCF.js:554–562 | include/exclude configuration compiled with picomatch; IDs matched later | Config/plugin controlled; not a proof all plugin inputs are trusted |
| Vite importGlobPlugin:13661 / parseImportGlob:13768 | source import.meta.glob strings compiled as patterns; parser requires literals, rejects dynamic template expressions | No direct import.meta.glob found in project source; dependencies/plugins not fully proven absent |
| Vite fsDenyGlob:49416 / isFileServingAllowed:35835 | server.fs.deny config becomes matcher; request file path is matched subject, not that pattern source | server.host=true; Docker npm run dev --host0.0.0.0; compose maps5173:5173. Cannot dismiss dev server exposure |
| Vite patternToIdFilter:42142 | configured pattern compiled, module ID becomes subject | No direct project picomatch import; complete plugin transformations remain uncertain |
| Vitest cli-api:10897 and matchesTestGlob | include/exclude/test discovery and filesystem paths; config patterns passed to matcher | frontend/vitest.config.ts include tests/**/*.test.tsx and tests/**/*.test.ts; no HTTP proof implied |
| tinyglobby dist/index.mjs:217–219 | processed match/ignore patterns compiled, discovered relative paths matched | API callers supply patterns; fdir optional peer edge also present |
| Browser output | No direct project picomatch/tinyglobby imports found by source search; imported Vite paths examined are Node tooling | Actual production bundle/module graph NOT built or verified; do not claim absence from runtime |

This is a static partial mapping, not an exploitability verdict. No route from public
HTTP/WS/account input to attacker-chosen glob has been established, but no comprehensive
proof of unreachability exists. Broad host binding is an exposure consideration, not
proof this specific advisory is remotely exploitable.

## Five bounded local probes

Node22.23.4; independent sequential child processes,256MiB heap cap,2s parent wall
bound per probe. Original integrity-verified picomatch4.0.7 only. No network/server,
owner files or accounts. Parent killed/joined timed-out children; total6.185s<60s.

| Category | Subject length | Result |
|---|---|---|
| *.js positive/negative controls | 8 each | Both returned expected true/false |
| +(*) repeated single branch | 33 | Timeout at2s; killed/joined |
| +(*a) repeated single branch | 29 | Timeout at2s; killed/joined |
| +(*a) repeated single branch | 37 | Timeout at2s; killed/joined |

Patterns derive from the official advisory description. Subject tails force mismatch.
Three bounded stalls corroborate the documented library risk; timings alone do not
prove exponential complexity or an application exploit. No more probes/retries run.

## Cleanup / unchanged scope

All5children joined; verified audit-owned scratch directory removed after recording
hashes/results. No existing node_modules, services, app config, financial code, scanner,
policy or exception registry changed. Baseline hashes unchanged after inspection.
No full app tests/build/CI rerun because no authorized fix was available; applicable
Paper proofs remain retained, release/security blockers remain.

## Next decision

Recommended: retain the blocked Security result and select an official reviewed patched
release when available. No unattended polling is scheduled and no upstream release ETA
is known. If the owner needs an earlier alternative, prepare a separate concrete vendor/
local-patch proposal with immutable provenance, license, matching semantics and bounded
regression tests; PR-2 requires approval before implementation. Such a patch does not
automatically satisfy OSV policy: any exception needs separate exact owner review and
must not be disguised as a scanner clean result. Do not use an unmerged PR automatically.

Sources: [GitHub advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf),
[referenced PR194](https://github.com/micromatch/picomatch/pull/194),
[official registry](https://registry.npmjs.org/picomatch/latest).
