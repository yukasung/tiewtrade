# LP-01 prototype checkpoint — stopped for owner review

Status: **Prototype prepared; matrix Failed19/20; not installable/approved**.
Owner approvedA prototype and bounded tests only. No app install, exception, Git or CI.

## Reviewable artifacts

- [Patch](picomatch-4.0.7-lp01.patch):54-line unified diff, one changed file lib/parse.js.
- [Provenance](provenance.json): locked registry integrity, archive/source/patch hashes;
  upstream package.json/version4.0.7 unchanged. [MIT license](LICENSE) retained.
- [Frozen matrix](probe-matrix.json), [results](probe-results.json), [child](probe-child.js),
  [runner](probe-runner.py), [cleanup](cleanup.json). Matrix fixed before launch.

## What changed

Added a linear lexical star detector. After existing safeOutput handling, a single
branch with an unescaped star outside quotes/brackets uses the existing risky-pattern
literal fallback. No new matching algorithm, dependency tool or application patch.
Existing recognized nested-character star combination handling and the explicit
maxExtglobRecursion:false opt-out remain unchanged.

This intentionally changes glob semantics: +(*a) no longer matches aaaa with default
options, while it can still match the literal pattern string. It is NOT a transparent
optimization or proof of full picomatch compatibility/security.

## Actual outcomes

20child processes sequential,2s deadline each/256MiB, total1.526s<60s; no timeouts or
errors, all joined. Three original adversarial categories returned false promptly
(4.4–6.9ms inside the child vs original2s bounded stalls). Nested wildcard case returned
false as well. Configured/discovery/path/dot/negation/escape/bracket/quote/capture/
literal/nested-safe examples returned expected outcomes. Explicit opt-out continues
to bypass the new guard on the short input tested; not exercised against a long stall.

19of20matrix assertions Passed. Case4 expected original +(*a) against literal +(*a)
to be false, but original AND patched returned true. Original picomatch permits direct
pattern/input equality via its fast path; the baseline expected value was incorrect.
Patched expected=true was met. This is a test-oracle error, not a demonstrated patch
regression. Preserve the Failed receipt; no test changes or automatic rerun performed.

## Risks the reviewer must examine

1. Scanner remains Blocked: upstream4.0.7 is still affected; no exception is requested.
2. Newly literalized patterns include otherwise benign matches. Broader caller and
   matching-semantics acceptance is absent;20examples do not establish compatibility.
3. Quote/bracket lexical interactions require scrutiny. Helper checks quote state before
   bracket context: a quote character inside a bracket class can affect its later star
   detection. This may differ from parser tokenization and could miss a star after the
   class. No additional adversarial probe was run outside the20case budget, so do not
   assert a reproduced bypass or complete fix. Safety of the detector is unproven.
4. maxExtglobRecursion:false intentionally disables analysis. Caller option audit from
   prior source inspected Vite/tinyglobby defaults; exhaustive plugin/caller proof and
   integrated installed execution have NOT been completed.
5. Character-class nesting, escapes, malformed syntax, caller options and all ReDoS
   variants beyond this finite matrix remain unproven. No asymptotic safety claim.

Because of these limits the prototype must not be installed, published or used to justify
an exception. Owner code review may request a narrow correction and a separately bounded
replacement matrix before any packaging proposal. No automatic next-stage work.

## Cleanup and baseline

Only parser changed inside the audit-owned scratch copy. Version/license preserved;
all20children joined, both owned preparation scratch directories removed. App source,
manifest/lock/config, running services and policy registry unchanged. Original baseline
results preserved. No frontend build/full tests/workload/Live validation implied.
