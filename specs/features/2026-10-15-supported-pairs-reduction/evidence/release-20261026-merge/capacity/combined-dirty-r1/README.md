# Dirty attempt r1 — preflight interrupted, no acceptance credit

The run was stopped while the baseline-readiness loop was still preparing the
fixture, before T0 or dirty burst. No measured phase/result is claimed.

Preflight review found the recently added barrier fail-fast could misclassify an
expected post-admission `INDICATOR_DATA_NOT_READY` 503 while the barrier coroutine
was finishing. Dirty recovery permits that response. The helper was corrected to
wait for barrier completion in this specific case, while still failing fast on
429 and `INDICATOR_ADMISSION_UNAVAILABLE` 503. Two regression cases were added;
targeted alignment/smoke/scope/gate tests: 78 passed, static checks passed.

The existing passing steady phase returned 200 for every accepted probe, so that
new 503 branch does not affect its evidence. Production image, policy, limits and
thresholds are unchanged. Reuse steady-r7; do not rerun it solely for this fix.
All partial files remain; telemetry collector and runtime were stopped cleanly.
