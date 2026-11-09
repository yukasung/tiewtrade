# F-17 combined PR — exact evidence false-positive approvals

สถานะ: **Approved A — เจ้าของตอบ approve วันที่ 2026-11-09; เพิ่มเฉพาะ6exact immutable bindings ตรวจ policy แล้วทำ commit/push/หนึ่งPR/requiredCI ต่อ; ไม่อนุญาตmerge**
วันที่:2026-11-09 Asia/Bangkok
Local candidate: `1291c93dc5436548ae747fbe9e9898f42ddc7ae8`.
Owner authorized commit/push/one PR and CI. Related source/tests/spec/evidence have
been committed locally; nothing pushed and no PR/CI started while this known
policy blocker remains. No merge permission.

## Verified scanner result

Pinned/checksum-verified Gitleaks v8.30.1, unchanged project configuration and
complete-history plus current-tree scan completed. Existing exact exception and
immutable-artifact registries applied read-only. Remaining172distinct occurrences
(344raw records because history and tree both report them), all generic-api-key,
in6new immutable bindings on the local candidate. Existing39artifact bindings
still resolve; historical roadmap match is already resolved and needs no new entry.
No unknown severity or real credential identified in these new pending records.

| Exact path under evidence/remaining-paper-20261109/ | Distinct matches | Independently checked meaning |
|---|---:|---|
| cleanup/candidate-sha256.json |34|SHA-256 source fingerprints |
| controlled20/candidate-sha256.json |34|SHA-256 source fingerprints |
| d20_identity/candidate-sha256.json |34|SHA-256 source fingerprints |
| smoke/candidate-sha256.json |34|SHA-256 source fingerprints |
| w4/candidate-sha256.json |34|SHA-256 source fingerprints |
| w4/run/fixture/internal-fixture.json |2|Synthetic UUIDs at pending.intent.key and retry.key |

All170fingerprints were compared to actual producing source bytes and matched.
Both UUID values parse/round-trip as canonical UUID and originate from isolated
request/intake fixture construction (`profile_internal_restore.py`), not API-key
storage. The original staged-tree scan's additional roadmap match is unchanged
from base; complete-history policy confirmed it is already covered.

Concrete proposed rows, exact commit/blob/rule/count/occurrence digests:
[proposed-publication-evidence-bindings.json](evidence/remaining-paper-20261109/proposed-publication-evidence-bindings.json).
Its PENDING approvals are an inactive proposal, never passed to the active policy.
Raw scanner reports/matches remain private under temporary local storage.

## Requested decision — A recommended

Approve only these6immutable artifact bindings as false_positive under the existing
owner-approved policy. After approval append these exact rows to
`.github/security/evidence-exceptions.json` with the owner's decision reference;
keep old rows, scanner/config/pins/checksums/severity/criteria unchanged. No broad
folder/rule/UUID/hex suppression, force push, evidence rewriting or production edit.
A new blob/occurrence remains subject to a new decision.

Verify exact binding resolution and relevant policy tests locally. Commit the
approved registry + this decision/evidence in a follow-up on the same branch,
push once, open one combined PR and follow required CI on its final SHA. Existing
Git/CI authorization remains applicable; merge still requires owner command.
No repeated D20/W4/full suite just for registry/docs. Preserve all prior results
and remaining F17 Full Validation/manual/Release/dependency gates.

The existing security helper instructions say “A new occurrence/content/package
version requires a new decision” (`tools/security/README.md`). Earlier approvals
were exact occurrences on other commits/blobs and cannot be transferred silently.
This approval is needed for registry additions, not because new trading code or
financial rules are being changed. Without approval stop publication here; do not
push a candidate already known to fail Security or alter policy on the owner's behalf.

## Owner decision applied — 2026-11-09

Owner approved A. Appended only the six exact rows to active evidence registry with this decision reference; old39bindings retained. Proposed snapshot keeps PENDING labels as history, not active approval. Pins/scanner/rules/checksums/thresholds unchanged. Relevant policy tests and final-candidate scan precede one combined PR; remote CI is reported separately after execution.
