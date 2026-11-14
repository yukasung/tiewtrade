# Live form failure-only geometry evidence

สถานะ: **Approved — เจ้าของสั่งเริ่ม วันที่ 2026-11-14; engineering delegation in AGENTS.md**

## Scope and reuse

CI5a3002a andfa2c8d1 failed at top-navigation.spec.ts Live form bottom alignment:
8px versus1px. One unchanged local replacement passed14.3s; cause unknown.
Reuse existing Playwright TestInfo.attach and viewport/rectangle assertions.
Change only failure evidence in the existing Live geometry loop: retain original
separate boundingBox reads and assertions; after failure attach their values,
requested/actual viewport, timestamp and a single browser snapshot of allowlisted
rectangles/computed layout properties. No text content, account state, cookies,
tokens, request payloads or SQL. Collector errors must preserve the original failure.
No production, timeout, tolerance, fixed sleep, polling or retry changes.

## Validation and publication

Inspect diff for unchanged successful path and safety assertions. Targeted
ESLint/typecheck and the exact dense workspace test on fresh isolated fixtures;
retain trace on failure and cleanup proof. Existing fixture runner may override
ports/origins only. Then publish one PR candidate against current main and monitor
required CI. If geometry fails, inspect its attachment and stop/report before
further experiments; do not auto-rerun or claim a fix. Other failures also require
log analysis and scope review. Standing publication/merge rules apply only when
all gates pass. Preserve historical Failed/Incomplete results and current scope.


## Local checkpoint — stop/report

Exact dense workspace test reproduced the original8px failure at width1440.
Observer attached evidence and retained trace; original assertion propagated.
Original separately sampled form: y69/height834; workspace:y68/height828.
Expected bottom895 versus original form bottom903 =>8px discrepancy.
Single page.evaluate immediately after failure: same workspace:y68/height828,
form:y69/height826 => bottom895, discrepancy0px. Header64px; viewport1440x900.
See live-form-geometry-failure.json (allowlisted metadata only).

This demonstrates layout changed between separate measurements; it supports
incoherent sampling as the failure cause, not a persistent8px defect at the
collected snapshot. It does not prove every later frame/viewport is correct.
Recommend reading bar/form/workspace in one browser evaluation before applying
the unchanged assertions. Such test sampling correction is not implemented here.

Initial scoped lint flagged unqualified browser globals; corrected to window.*.
Scoped ESLint/TypeScript and diff checks Passed afterward. No test rerun after
this naming-only fix, no CI publication, commit/push or merge. The first lint
command also used repo rather than frontend cwd; corrected command used existing
frontend config. Original test failure retained, no assertion/timeout/polling fix.

Fresh isolated database dropped with zero connections; dedicated Redis removed.
Private log:/tmp/live-form-observer-browser.log. Trace and attachments:
frontend/test-results/top-navigation-dense-works-63675-erves-it-across-breakpoints/trace.zip.
Private config overrides ports/origins only; owner runtime untouched.
Stop/report reached as prescribed when the geometry failure reproduces locally.
No CI campaign was started because local evidence already captured the failure.


## Owner-directed completion — 2026-11-14

Owner instructed continuous completion under standing engineering/publication
delegation. The self-imposed local stop/report checkpoint is superseded for this
bounded test correction. Before code: read bar/form/workspace together in one
page.evaluate, then retain the same3 assertions and1px tolerance. Keep failure-only
observer and original metadata; no production/CSS/timeout/polling/retry changes.
Run exact local case and scoped lint/typecheck, review final diff, then publish,
monitor required CI, merge with expected SHA when gates pass and monitor post-merge.
Preserve historical failures. Existing safety/financial and3-failure stop rules
still apply; do not introduce extra approval points for routine implementation.


## Atomic sampling correction checkpoint

Local exact case1 Passed(11.7s), scoped ESLint/TypeScript and diff checks Passed.
Failure evidence from the previous run retained in /tmp/live-form-observer-failed-artifacts
and live-form-geometry-failure.json. All3 assertions/tolerance and timeout unchanged.
Successful path adds one synchronous browser snapshot instead of3 awaited calls;
observer runs only after failure and rethrows original errors. No runtime code,
CSS or account/financial behavior changes. Cleanup0 connections then database drop,
dedicated Redis removed. Private success log:/tmp/live-form-atomic-browser.log.
Reviewed diff for safety, evidence privacy and preservation of checks. Proceed
publication under owner instruction; final required CI and post-merge remain pending.
