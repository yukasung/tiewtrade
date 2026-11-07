# Published candidate CI follow-up — 2026-11-07

Draft PR: https://github.com/yukasung/tiewtrade/pull/59 . Initial published head:
`957559a8e1393820bd97d6fab46f1f96b78a8f01`.

Initial CI https://github.com/yukasung/tiewtrade/actions/runs/42361999048 found one
full-backend mypy error: `profile_internal.py` macOS readiness statements inferred
unreachable on Linux (678 files checked). Backend tests did not run in that job;
do not reuse the prior207 local tests as a claim that remote regression passed.

Fix: bind the runtime platform string to a local before the unchanged exact
`darwin` comparison. Mypy can now check both paths on either analysis host, while
non-macOS still raises HOST_SENSOR_PLATFORM_UNSUPPORTED and no workload starts.
No readiness threshold, command, schedule, financial rule or retry behavior changes.

Affected checks:121preflight/profile cases passed in0.50s; mypy passed the changed
module with both `--platform linux` and `--platform darwin`; Ruff/format passed.
XML: `publication-linux-guard.xml`. Publish this follow-up and track required CI on
its new head; earlier runs belong to the earlier candidate.

The evidence UUID/checksum security finding remains a separate blocker. No new
exception, scanner suppression or security policy change is included. Original
workload and refactor proofs retain their unchanged scope; no merge/deploy or F17
completion is authorized by this follow-up.
