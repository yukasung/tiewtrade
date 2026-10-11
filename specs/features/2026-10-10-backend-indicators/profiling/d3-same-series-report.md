# D3 same-series cleanup and continuation

## Review correction: age the actual cursor seed across ordinary retention

Final correction run: **1 lifecycle passed, 0 failures/errors/skips, 102.331 seconds**.
Ruff/format and mypy (340 files) passed. Slot IDLE and runtime sessions zero after
teardown. Ready for re-review; the earlier 125.024-second result is preserved below.

The harness now advances its test clock to `seed + 365 days + 1 microsecond`.
It asserts `grace_cutoff < seed < ordinary_cutoff` and checks that this instant
is after cursor issuance but before both the original cursor expiry and original
generation expiry. It does not backdate or rewrite the generation/cursor.

Both API image processes use a test-only startup wrapper. During D3 only, the
wrapper substitutes the controlled timestamp for Python-issued database clock
expressions and the API authentication clock. The real SQL queries, cursor
decoder, computation and image code remain in use. Each cleanup subprocess uses
the same timestamp for its existing `database_now` read. PostgreSQL's OS clock
and internal function clocks are not globally changed. HTTP generation age must
equal the elapsed time at the controlled instant on **both** replicas, so using
the real clock accidentally does not satisfy the test.

The existing presented session is kept alive through the simulated active-user
interval using the API role and presented-session RLS; its absolute expiry and
the original cursor lifetime are unchanged. Clock files are removed in `finally`
before the lifecycle's D5/D4 checks. No production clock hooks or extra grants
are added. Without the clock files the wrapper delegates to the normal clocks.

Evidence for this correction is `d3-aged-seed-tests.xml` and
`d3-aged-seed-evidence.json`; the original result below is historical and does
not establish the aged-seed case. The new trace includes both cutoffs and the
controlled cleanup instant, in addition to unchanged seed and cross-replica parity.

## Original same-series evidence (before review correction)

Date: 2026-10-11. Scope: the missing short D3 case identified by
`d2-d7-coverage-audit.md`. No production code or retention rule changed.

Result: **1 continuous lifecycle passed, 0 failures/errors/skips, 125.024 seconds**.
Ruff/format and full backend mypy (340 files) passed. Post-test slot was IDLE,
with zero API/auth/builder sessions. Ready for review; no load/soak run performed.

The existing mixed-image lifecycle now issues BTC/USDT/4h's cursor **before**
cleanup, reads a full-scan reference at the generation's original bounds/as-of,
and identifies its real seed at calculation start L. It snapshots that seed's
complete source row, not merely a row count.

Two additional aligned candles of the same series exercise cleanup:

- L−12h: older than the 365-day plus 6h15m grace cutoff; must be removed.
- L−4h: older than the ordinary 365-day cutoff but within physical grace; must remain.

Both probes are outside the generation's calculation interval, so they do not
invalidate its source proof. The L−4h probe is **not** described as the generation's
seed; the actual seed is L. This test proves preservation of that real seed and
the grace probe during pagination, not six-hour-old cursor capacity or exact
microsecond cutoff equality.

The preserved old F-09 binary must fail with SQLSTATE TT011. Each compatible
image then executes its real cleanup. After each cleanup the harness asserts:

1. The complete seed row is unchanged and only the L−4h pre-window probe remains.
2. The pre-existing cursor works on both API replicas with HTTP 200.
3. Every returned row/value/status/seed/finality matches the original full-scan
   reference at the expected offset, and both signed next cursors agree.
4. All signed claims are preserved except the expected next position; the token
   returned after the first cleanup is the input across the second cleanup.

The row projection helper is reused by D2 and D3. The continuous lifecycle also
reruns D2 routing/restart/rejection checks and existing D4/D5 checks. It remains
one pytest case, not a separate passed case for each assertion or gate.

Evidence: `d3-same-series-tests.xml` and `d3-same-series-evidence.json`.
Trace output contains image IDs, generation/seed identity and assertion summaries,
with no secrets, cookies, MACs or cursor values. Test image IDs are recorded in
`d2-d7-coverage-audit.md`; no new API image is needed for this harness-only change.

Independent error scenarios reset the isolated admission buckets as in the
existing fixture. Production quotas are unchanged; D2 retains its 6/min check.
Only isolated PG55433/Redis56379 and auxiliary containers are used. D3 still needs
review with the existing D1 stage/drain/negative-control evidence; D4–D7 and phase-9
capacity are not closed by this result. F-11 remains In Progress.
