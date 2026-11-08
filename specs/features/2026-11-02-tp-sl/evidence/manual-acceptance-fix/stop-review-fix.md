# STOP review finding — resolved locally

Date:2026-11-08 Asia/Bangkok. Owner requested `review code`, then authorized `แก้ไข`
after one High finding: failed journal cleanup could reuse a completed STOP key
after resume, returning the old receipt without stopping the new generation.

## Fix and recovery boundary

- Read the persisted owner/mode journal once per mounted control. A known receipt
  retires the in-memory attempt; failed removal cannot make that key the next intent.
  The same mounted unknown submission still retries with its original key.
- After remount, reconcile a persisted key using the existing authenticated
  `/paper|live/kill-switch/requests/by-key/{key}?action=STOP` route. Pending receipts
  are recovered without another POST. An applied receipt is checked against fresh
  server USER-stop status; when resumed, an explicit new STOP gets a fresh UUID.
- Missing receipt keeps the same key for a possibly lost/in-flight submission.
  Failed receipt/status reads remain uncertain and do not generate a new identity.
  A rejected receipt or invalid stored UUID can be retired for an explicit new action.
- Reuse the mounted-owner guard pattern from useDurableAttempt: an old control
  cannot continue an awaited recovery into a POST after owner switch/unmount.
  Reads on mount never automatically send STOP. Hints remain transient UI state;
  authoritative sessions, receipts, stop causes and generations remain PostgreSQL.

No backend endpoint/schema, business rule, financial calculation, activation flag
or Live executor changed. The added client helper calls an existing read-only route.

## Checks

`KillSwitchControls.test.tsx`:16passed in1.37s, covering the existing nine cases and
seven added cases: mounted/remounted STOP→resume→STOP with removal and subsequent
write failures; recovery of pending/applied/missing receipts; failed lookup preserving
the original key; owner switch while the receipt read is pending. Fresh-stop cases
exercise three generations and exact backend-style idempotent receipt reuse.

Frontend typecheck passed. The first expanded ESLint invocation found a test-only
bare setTimeout; using window.setTimeout fixed it. Final scoped ESLint passed and
the affected owner-switch test passed again (1passed/15unselected). These overlapping
runs are not summed. No broad/backend/browser workload rerun was needed: production
changes are confined to the STOP control and its existing-route client helper.

Current file identities: [source-manifest.json](source-manifest.json).
The previous implementation identity is retained in
[source-manifest-before-stop-review-fix.json](source-manifest-before-stop-review-fix.json).
Earlier financial/DB/protection-browser evidence remains within its recorded scope;
those tests did not execute this later STOP recovery fix and are not relabelled.

The High finding is addressed with scoped regression proof. Next is the owner-
authorized refactor gate in AGENTS.md; no refactor step has started. Current-candidate
required CI, manual replacement and Release dependencies remain pending. No
commit/push/deployment/activation or owner-account mutation occurred in this fix.
