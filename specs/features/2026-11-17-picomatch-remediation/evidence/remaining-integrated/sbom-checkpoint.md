## NC-PM-IDENTITY-01 — local scan complete, owner decision pending

The [pinned scanner proof](sbom-probe.json) and [integrated security scan](sbom-integrated.json)
both cover the original 464 lockfile identities and the verified local archive.
The integrated gate returned one blocked High and four Medium findings. The High matches
the upstream advisory and the installed LP04 hash. Coverage is proven. The registry is
unchanged. Required CI and publication await the exact owner decision.

The LP04 matrix (24/24) covers the reported default guard gap.
Actual callers (12/12) and configuration inspection
support a scoped owner exception for this exact dev/build artifact. The browser build
graph excludes picomatch. Tests cover the current configuration; explicitly disabling
the recursion guard, introducing user-controlled patterns or changing build plugins
requires reassessment. Some repeated globs intentionally have narrower matching semantics.
This evidence does not establish a universal regex safety guarantee.

[Proposed registry diff](proposed-exception.diff) is review-only. Its decision applies
to one advisory and one archive. Upstream bytes, a different archive or a different
advisory produce other identities. Retire the entry on adoption of a verified compatible
official fix. Owner review is required by PR-3 and tools/security/README.md.

Local security suite: 66 passed, 4 opt-in skipped. Changed-file Ruff/format and strict mypy
passed. Tested missing SBOM, wrong version, altered SBOM bytes, missing advisory and lock,
other High findings and different artifact bytes. Previous compatibility and trading
evidence remains scoped to its original candidate. The integrated scanner result is local.

Owner approved the exact diff on 2026-11-18. [Validation after approval](approved-sbom-result.json) supersedes the pending decision above.
