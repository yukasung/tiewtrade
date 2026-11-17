# Picomatch dependency remediation — Requirements

สถานะ: Approved — owner approved requirements on 2026-11-17
วันที่: 2026-11-17
Branch: security/picomatch-remediation-20261117
Base: d3c9eae91f8fd0c0de091862106a77873d72b6b5

## Problem

Main Security44122272392 blocks High GHSA-fc5q-39xc-vjpf in picomatch4.0.7.
Advisory updated between Passed PR scan and Failed postmerge scan. No lockfile delta.
Registry latest4.0.7 and no patched release listed at investigation. A dev dependency
can still affect build/test/dev-server processes; dev=true is not an exemption.

## Requirements

- PR-1: Map installed picomatch occurrences/callers (tinyglobby/Vite/Vitest), attacker
  controlled pattern reachability in build/test/dev/server flows and release output.
  Record exact source/versions/config and limits; no assertion of safety from labels.
- PR-2: Prefer official published patched compatible dependencies with reproducible
  integrity-checked lockfiles. Check official upstream evidence before selecting.
  An unmerged upstream PR, arbitrary fork, local patch/source replacement or package
  substitution requires a concrete separate owner decision before implementation.
- PR-3: Preserve scanner pins, coverage of dev/transitive/optional dependencies and
  fail-closed High/Critical/Unknown policy. Never falsify version metadata or suppress
  an advisory to obtain a pass. Security exception requires owner review of exact
  registry diff and evidence under security requirements.
- PR-4: Prove remediation with bounded isolated negative/repro tests (subprocess and
  deadline for ReDoS), relevant tooling tests, frontend lint/typecheck/build and real
  scan of final lockfiles. No hostile patterns against owner services or Live trades.
- PR-5: Preserve API/schema/session/trading behavior and existing workload proofs.
  No unrelated upgrades or application refactors. Record unresolved findings honestly.
- PR-6: If no safe patched resolution exists, report Blocked with options; do not claim
  Security Passed or F17Completed. New infrastructure/cost or weaker policy is not
  authorized by this proposal.

## Workflow

Approve these requirements, then prepare plan/validation and obtain their approval
before source/dependency changes, per AGENTS.md. Investigation may continue read-only.
Required candidate CI and postmerge Security remain mandatory. This task removes a
security blocker only; F17 V18/V19/V20 dependencies still require their existing gates.
