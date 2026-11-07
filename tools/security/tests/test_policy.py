"""Merge policy invariants; fixtures contain only synthetic public data."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tools.security.model import (
    COMPONENTS,
    Candidate,
    Finding,
    PolicyError,
    aggregate,
    approved_exceptions,
    digest,
    manifest,
    policy_counts,
    read_json,
    score_severity,
)


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = Candidate("a" * 40, "b" * 40, "c" * 40, "123", "1")
        self.config = digest("configuration")
        self.jobs: dict[str, dict[str, object]] = {
            name: {"result": "success"}
            for name in ("policy-tests", "secrets", "dependencies", "codeql")
        }
        self.reports = [
            manifest(name, self.candidate, self.config, policy_counts([], frozenset()), 1)
            for name in COMPONENTS
        ]

    def test_score_boundaries_and_invalid_metadata(self) -> None:
        cases: list[tuple[object, str]] = [
            (0, "none"),
            (3.9, "low"),
            (4, "medium"),
            (6.9, "medium"),
            (7, "high"),
            (8.9, "high"),
            (9, "critical"),
            (10, "critical"),
            (None, "unknown"),
            (True, "unknown"),
            ("NaN", "unknown"),
            ("inf", "unknown"),
            (-1, "unknown"),
            (11, "unknown"),
            ("warning", "unknown"),
            ({}, "unknown"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(score_severity(value), expected)

    def test_policy_and_exact_exception_scope(self) -> None:
        old = Finding("secret", digest("old occurrence"), "high")
        new = Finding("secret", digest("new occurrence"), "high")
        counts = policy_counts([old, old, new], frozenset({("secret", old.identity)}))
        self.assertEqual(counts["excepted"], 1)
        self.assertEqual(counts["blocked"], 1)
        for kind in ("dependency", "codeql"):
            for severity in ("none", "low", "medium", "high", "critical", "unknown"):
                counts = policy_counts(
                    [Finding(kind, digest([kind, severity]), severity)], frozenset()
                )
                self.assertEqual(counts["blocked"], int(severity in {"high", "critical"}))
                self.assertEqual(counts["needs_triage"], int(severity == "unknown"))

    def test_conflicting_duplicate_is_not_first_wins(self) -> None:
        with self.assertRaises(PolicyError):
            policy_counts(
                [
                    Finding("codeql", digest("same"), "low"),
                    Finding("codeql", digest("same"), "high"),
                ],
                frozenset(),
            )

    def test_complete_gate_passes(self) -> None:
        aggregate(self.reports, self.candidate, self.config, self.jobs)

    def test_non_success_job_and_missing_component_fail(self) -> None:
        for name in self.jobs:
            for status in ("failure", "skipped", "cancelled", "timed_out", None):
                jobs = copy.deepcopy(self.jobs)
                jobs[name]["result"] = status
                with self.subTest(name=name, status=status), self.assertRaises(PolicyError):
                    aggregate(self.reports, self.candidate, self.config, jobs)
        for index in range(len(self.reports)):
            with self.assertRaises(PolicyError):
                aggregate(
                    self.reports[:index] + self.reports[index + 1 :],
                    self.candidate,
                    self.config,
                    self.jobs,
                )
        with self.assertRaises(PolicyError):
            aggregate([*self.reports, self.reports[0]], self.candidate, self.config, self.jobs)

    def test_stale_head_base_commit_run_attempt_and_config_fail(self) -> None:
        for field in ("head", "base", "commit", "run", "attempt"):
            value = "d" * 40 if field in {"head", "base", "commit"} else "9"
            with self.subTest(field=field), self.assertRaises(PolicyError):
                aggregate(
                    self.reports, replace(self.candidate, **{field: value}), self.config, self.jobs
                )
        with self.assertRaises(PolicyError):
            aggregate(self.reports, self.candidate, digest("other config"), self.jobs)

    def test_invalid_manifests_fail_closed(self) -> None:
        for field, value in [
            ("schema", 2),
            ("coverage", 0),
            ("coverage", True),
            ("counts", {}),
            ("verdict", "blocked"),
            ("component", "unknown"),
        ]:
            reports = copy.deepcopy(self.reports)
            reports[0][field] = value
            with self.subTest(field=field), self.assertRaises(PolicyError):
                aggregate(reports, self.candidate, self.config, self.jobs)
        counts = policy_counts([Finding("dependency", digest("high"), "high")], frozenset())
        reports = [manifest(name, self.candidate, self.config, counts, 1) for name in COMPONENTS]
        for report in reports:
            report["verdict"] = "pass"  # A forged verdict cannot override counts.
        with self.assertRaises(PolicyError):
            aggregate(reports, self.candidate, self.config, self.jobs)

    def test_exception_requires_evidence_and_no_broad_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "exceptions.json"
            row = {
                "kind": "secret",
                "identity": digest("exact"),
                "resolution": "revoked",
                "reason": "revoked credential",
                "approval": "owner review URL",
                "evidence": "redacted revocation evidence URL",
            }
            path.write_text(json.dumps({"schema": 1, "exceptions": [row]}))
            self.assertEqual(approved_exceptions(path), frozenset({("secret", row["identity"])}))
            for field in ("approval", "evidence", "identity"):
                invalid = {**row, field: ""}
                path.write_text(json.dumps({"schema": 1, "exceptions": [invalid]}))
                with self.assertRaises(PolicyError):
                    approved_exceptions(path)
            path.write_text(json.dumps({"schema": 1, "exceptions": [{**row, "path": "*"}]}))
            with self.assertRaises(PolicyError):
                approved_exceptions(path)

    def test_duplicate_json_keys_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            path.write_text('{"verdict":"blocked","verdict":"pass"}')
            with self.assertRaises(PolicyError):
                read_json(path)
