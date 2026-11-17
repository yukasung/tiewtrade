# LP-01 — isolated picomatch local-patch prototype

สถานะ: Approved A — owner approved isolated prototype/bounded tests; stop for review
วันที่: 2026-11-17
Requirements/plan/validation already approved for original investigation. Owner said
เริ่มทำ after the no-published-fix checkpoint; this document concretizes the alternative
before source edits, as PR-2 requires. It does not approve a vulnerability exception.

## Evidence and limits

Verified locked picomatch4.0.7 package integrity/source hashes are in
[evidence](evidence/investigation-summary.json). Baseline5probes:2benign correct and
3single-branch repeated-extglob stalls. Source lib/parse.js:287–346 analyzes repeated
extglobs; branch wildcard checks at299–307 only apply when branches.length>1.
extglobClose at539–560 already has a risky-pattern fallback that converts the entire
extglob to escaped literal when no safeOutput exists. Simply changing >1 to>=1 catches
+(*) but DOES NOT establish +(*a) safe. That one-line change is not a complete fix.

No-patched-release/PR194-open metadata reconfirmed during proposal drafting. The title
of PR194 is about leading? behavior; do not treat it as an accepted solution for this
advisory. Need independent implementation review and compatibility proof.

## Recommended scope A: prototype then stop for review

1. Fresh audit-owned scratch directory; download4.0.7 by locked URL and verifySHA512.
   Preserve MIT LICENSE/notices and original archive/source hashes. Record exact local
   patch diff/hash separately; never label patched source4.0.8 or forge upstream identity.
2. Implement only a parser security guard for single-branch repeated plus/star extglobs
   containing an ambiguous/unbounded wildcard. Reuse the existing risky/literal fallback;
   do not flatten arbitrary regexes or invent a broad new matching algorithm. Inspect
   escaped stars, brackets, nested extglobs and options before selecting the predicate.
   Reject the approach if the detector itself can backtrack unboundedly or leaves the
   observed categories unhandled. Patch source only in scratch, not installed app files.
3. Compatibility is a first-class acceptance condition. The existing fallback deliberately
   changes unsupported/risky glob semantics to literal matching; document the exact new
   rejected pattern class. It is not a semantics-preserving optimization. Compare default
   and caller-used options, literals/escapes/dots/slashes/negation/capture, plus/star
   extglobs and Vite/Vitest/tinyglobby configured pattern behavior with original source.
   No silent acceptance of broad pattern changes. Unexpected differences block proposal.
4. Reuse the approved bounded Node child methodology. BEFORE running, record the finite
   matrix: baseline5cases already valid; at most20new sequential child probes with2s
   wall/256MiB bound, total≤60s including cleanup. Cover observed adversarial examples,
   new parser escape/nesting boundaries and expected harmless matching outcomes. Use
   explicit expected results for fallback semantics; matching baseline alone is not an
   independent oracle. No exponential complexity/safety proof inferred just from timing.
5. Review all changed source and package provenance; record remaining exploitability
   limits and maxExtglobRecursion:false opt-out (do not silently reinterpret that option).
   Audit caller options to see whether any bypass the intended guard. If safety cannot
   be justified, report Failed/Blocked and retain the experiment; no repeated automatic
   patch attempts or broad toolchain replacement.
6. Produce human-reviewable diff, source/patch hashes, license, finite test matrix and
   compatibility/risk report. Join children, remove only owned scratch or retain the
   exact inspected artifact with ownership receipt when necessary for review.
   STOP for owner code review before installation/publication. No commit/push/CI yet.

Expected prototype/review preparation20–40min; bounded probe stage≤60s, announce before
execution. This authorizes only the prototype if approved, not an open-ended library fork.

## Stage B is NOT included in A

After prototype review, prepare a concrete reproducible packaging/integration proposal
and prove actual Vite/Vitest/tinyglobby install/runtime resolution in an isolated app
checkout. Select packaging only after verifying npm support and frozen-install behavior;
there is no existing repo patch-package/override pattern to assume. Do not install a new
patch tool, introduce postinstall code or a fork implicitly. Verify bypass paths such as
npm ci --ignore-scripts/direct binary execution if a lifecycle mechanism is proposed.
Then lint/typecheck/build/tooling tests and artifact provenance are required.

OSV will still identify upstream4.0.7 as affected unless upstream publishes a fixed
version/metadata. A local patch alone DOES NOT make SecurityPassed. Any exact temporary
owner_exception registry entry requires a later owner review of real registry diff,
patch evidence, residual risk, removal condition and applicable policy. No exception is
requested now; no false_positive classification, severity downgrade, scanner/version
change, skip-dev or pin falsification is authorized. If this is unacceptable, retain
Blocked and wait for official patch. Do not spend a full CI round on a known blocker.

## Alternative B: retain Blocked, wait for official patch

No local fork or patch maintenance; no fixed release ETA. No unattended polling/service
is created. Resume when a reviewed published fix exists. Existing app/security gates
and F17 pending status remain honest. Neither option alone closes remaining F17V18/
V19/V20 dependencies.

## LP validation additions (activate only after approval)

| ID | Required proof | Level | Current result |
|---|---|---|---|
| LP-01 | Exact source/patch/license provenance, no version falsification, no installed dependency edits | Feature | Not Run — proposal only |
| LP-02 | Explicit single-branch guard threat model and bounded detector, actual changed semantics/options stated | Feature | Not Run |
| LP-03 | Finite≤20case matrix and bounded isolated child results/expected semantics/cleanup | Feature | Not Run |
| LP-04 | Scoped independent review with unresolved risks, no automatic installation or exception | Feature | Not Run |
| LP-05 | Packaging/actual callers/install bypass proof plus full scanner/CI | Feature | Blocked — separate stage B approval required |

No approved original requirement is silently superseded. PV-07 remains Blocked. Parent
financial/Paper tests remain valid; do not run4h or owner/Live trades for this prototype.


## Prototype implementation record (before source edits)

Use one linear lexical scan of a single branch, respecting backslash escapes, double
quotes and brackets. If an unescaped star remains, return risky:true using existing
literal fallback. Apply only after existing safeOutput analysis so its flattening of
recognized nested single-character star sequences is preserved. Keep the explicit
maxExtglobRecursion:false opt-out unchanged and demonstrate it on short benign input.
This is conservative: even safe uses of newly rejected repeated-star patterns change
to literal matching; LP compatibility report must expose those differences. No full
library ReDoS proof is claimed. No app installation.

Finite matrix locked before execution:20sequential child probes,2s/256MiB each,≤60s
stage. Cases: three prior adversarial categories; risky literal match; intentionally
changed safe short +(*a); JS positive/negative; configured test-discovery glob; negation;
node_modules exclusion; dotfile; slash path; escaped star; bracket literal star; quoted
literal star; literal plus withcapture; literal star; existing nested-safe combination;
nested wildcard; explicit opt-out short input. Baseline original runs only for benign
comparisons within the same child; original adversarial stalls use prior evidence.
A timeout/error/expectation mismatch or unexpected compatibility difference is a
reported failed case; do not modify/rerun automatically after the20case attempt.

## LP-01 execution checkpoint — stop reached

[Prototype artifacts/results](evidence/lp01/checkpoint.md) prepared. MatrixFailed19/20
(one incorrect original expected result), all20childrenjoined/no timeouts, observed
three original stalls now returned. Intentional semantic changes and unproven lexical
edge case documented. No correction/retry/install/publication/exception performed.
Ready for owner review of this amendment; not a feature-wide Ready for Code Review
claim, not remediation complete. Next work requires owner's review instruction.

## LP-02 finding corrections — owner instructed แก้ไข

Before edits: remove duplicate lexical helper entirely. Track actual wildcard-star
recognition on existing extglob tokens, propagate the flag to parent on close and reuse
existing token.conditions for the single-branch test. Native parser already handles
quotes/classes/escapes/options, avoiding a second lexer. Existing safeOutput and explicit
opt-out retained. Flag handling constant work per star/close; conservative propagation
of nested wildcard semantics documented. No new matching algorithm or installation.
Correct original literal equality oracle (case4true). Preserve LP01Failed receipt.
New20probe matrix: original20 except negativeJS/negation/dot/slash (ordinary paths already
covered and unchanged), plus quote-in-class, literal nested[,POSIXclass followed by star,
and nobracket option. All retained LP01 expectations remain except corrected case4.
These are additional independently bounded checks, not retroactive regrading.
Runner correction: monotonic60s stage deadline including reserved child cleanup,2s per
probe,256MiB heap, report before nonzero exit on failure. try/finally kill/join each owned
child on exceptions/cancellation; handle SIGTERM via exception, preserve original error,
write partial receipt. Verify lifecycle with controlled sleeping Python children for
success/failure exit, timeout, overall deadline and parent cancellation; no extra hostile
Node probes. No unbounded retries; one LP02matrix run. Stop/report after fixes and ask
about authorized refactor per AGENTS.md. StageB/security exception still excluded.

LP02 matrix raw resultFailed0/20: child bootstrap inherited node-e argv slice(1) but
new runner invokes a file, requiring slice(2). All20children exited at JSON parsing
before any require/matcher invocation; patch effectiveness is thereforeIncomplete,
not a demonstrated matching failure. Preserve raw result/hash, no matrix retry under
one-attempt scope. Fix bridge and add harmless fake-module CLI regression; no hostile
pattern or patched-library execution. Next replacement matrix requires owner decision
alongside the normal post-finding refactor gate. No source/financial/scanner scope change.
Runner intermediate cancellation tests twice failed because InterruptedError was
handled as retryable OS interruption by subprocess; use custom ProbeCancelledError.
One intermediate test launch had a quoting syntax error before execution. Final4runner
tests Passed; retain these development failures in narrative, not as acceptance passes.

## LP-02R1 — approved refactor and one replacement, 2026-11-18

Owner approved narrow refactor plus one20case replacement then stop for review. Preserve
LP01Failed19/20 and LP02bootstrapFailed receipts. Before edits: copy corrected LP02
runner/tests/matrix/child/patch into distinct lp02r1 evidence. Refactor naming to explicit
capture_probe/run_matrix/handle_termination and centralize duplicate child/cleanup/stage
limits; no parser patch or matrix expectation changes. Tests adapt names only. Reuse
pinned registry archive and apply the exact existing patch to fresh scratch; verify
original/patched source hashes against LP02provenance. Run5runner controls/Ruff/format/
mypy/JSsyntax, then one matrix20children,2s/256MiB,60s stage. No extra matrix/candidate,
installation, registry exception, Git or CI. Stop/report even onfailure; success is
only scoped prototype evidence, not library-wide safety or F17Completed.

### LP02R1 refactor/replacement checkpoint — 2026-11-18

Owner-approved refactor and one replacement finished: [receipt](evidence/lp02r1/checkpoint.md).
20/20matrixPassed1.598s;5runner controls/Ruff/format/mypy/JSsyntaxPassed. Exact parser
patch/matrix retained, code/source bindings unchanged, child PIDs absent/scratchremoved.
HistoricalFailed receipts preserved. Stop for ownerreview, no stageB/install/exception.

## LP-03 — owner requested fixes after LP02R1 review, 2026-11-18

Before edits: preserve LP02R1Passed within its scope. Add a separate top-level-alternative
flag per extglob. Update it only when native pipe token handling sees state.parens equal
to extglob.parens+1; keep existing conditions untouched. New guard uses this flag instead
of conditions, so pipes inside ordinary parentheses do not disable it. No second lexer.
Preserve wildcard propagation/safeOutput/opt-out and document remaining multi-branch risks.
Cancellation tests publish readiness with temp-file rename; start parent runner in its
own session/process group, cleanup owned group in finally even before readiness/PID is
known. Include deliberate pre-readiness failure proof, with child witness read only after
cleanup; no kill of unrelated processes/services.
Finite9case targeted matrix once,2s/256MiB sequential children,30s total budget: nested
ordinary-group adversary; its literal equality; harmless ordinary-group alternatives;
nested extglob alternatives followed by wildcard; simple top-level alternatives;
quoted-pipe wildcard; bracket-pipe wildcard; original +(*a) adversary; short benign
multi-branch wildcard control preserving prior behavior. Do not run hostile baseline;
only harmless comparisons. Preserve old tests/results. Full library/advisory remediation
is NOT established by this scoped matrix. Run runner controls/Ruff/format/mypy/JSsyntax,
then targeted matrix andcleanup; no app install/exception/Git/CI. Stop for refactor decision
per AGENTS.md once findings are corrected and scoped evidence reported.

LP03implementation/targeted checks complete: [receipt](evidence/lp03/checkpoint.md).
9/9matching checks,6runner methods and relevantstatic checksPassed; cleanup complete.
Stop for refactor decision, no installation, broader remediation or exception implied.

## LP03 refactor — owner approved, 2026-11-18

Before edits: keep parser patch/runner/matrix byte-identical and reuse9/9matching proof.
In a separate lp03refactor receipt, make cancellation fixture helper private/descriptive
and consolidate its duplicate owned-process-group kill branches with the same short-
circuit ownership checks and ProcessLookupError handling. No lifecycle/timeout/assertion
change. Run6runner test methods/Ruff/format/mypy; no new hostile matrix, packaging or
policy work. Preserve all prior artifacts. Stop at prototype validation checkpoint;
remaining owner code review/stageB gates unchanged.

LP03refactor completed with [6test/static Passed and source reuse proof](evidence/lp03refactor/checkpoint.md).
Parserpatch unchanged,9/9retained,no newmatchingprobe. Stop awaiting ownerreview.
