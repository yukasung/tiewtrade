"""Immutable evidence approval, occurrence parity and real-scanner negative controls."""

from __future__ import annotations

import copy
import hashlib
import html
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from tools.security import cli, secrets
from tools.security.evidence import approved_evidence
from tools.security.model import Candidate, Finding, PolicyError, digest, policy_counts
from tools.security.reporting import summary
from tools.security.scan import observed_stage, scan_secrets
from tools.security.system import configuration, git

ROOT = Path(__file__).resolve().parents[3]


class EvidenceFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        git(self.root, "config", "user.name", "Synthetic fixture")
        self.source = self.root / "records.jsonl"
        self.source.write_text(
            "".join(
                json.dumps({"key": str(uuid5(NAMESPACE_URL, str(i)))}) + "\n" for i in range(600)
            )
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "synthetic records")
        self.commit = git(self.root, "rev-parse", "HEAD")
        self.rows: list[dict[str, Any]] = [
            {
                "File": "records.jsonl",
                "RuleID": "generic-api-key",
                "Commit": self.commit,
                "StartLine": i,
                "EndLine": i,
                "StartColumn": 1,
                "EndColumn": 8,
            }
            for i in (1, 2, 511, 512, 513, 600)
        ]
        self.findings = secrets.evaluate(self.rows, self.root)
        self.data: dict[str, Any] = {
            "schema": 1,
            "entries": [
                {
                    "commit": self.commit,
                    "path": "records.jsonl",
                    "git_blob": git(self.root, "rev-parse", self.commit + ":records.jsonl"),
                    "rule": "generic-api-key",
                    "reported_matches": len(self.findings),
                    "occurrence_digest": digest(sorted(f.identity for f in self.findings)),
                    "resolution": "false_positive",
                    "reason": "Fixed synthetic record identifiers",
                    "approval": "Owner approved this exact fixture dataset",
                    "evidence": "fixture.md",
                }
            ],
        }
        self.registry = self.root / "registry.json"
        self.registry.write_text(json.dumps(self.data))


class EvidenceTests(EvidenceFixture):
    def test_batch_parity_and_bounded_git_calls(self) -> None:
        expected = [
            Finding("secret", identity, "high", locator)
            for identity, locator in (secrets.occurrence(self.root, row, True) for row in self.rows)
        ]
        with patch.object(secrets, "git", wraps=git) as calls:
            actual = secrets.evaluate(self.rows, self.root, tree=True)
        self.assertEqual(actual, expected)
        self.assertEqual(calls.call_count, 4)  # one boundary, two ranges, one original blob
        first = self.findings[0]
        self.assertEqual(
            first.identity,
            digest(
                [
                    "gitleaks",
                    "generic-api-key",
                    self.commit,
                    "records.jsonl",
                    1,
                    1,
                    1,
                    8,
                    self.data["entries"][0]["git_blob"],
                ]
            ),
        )
        self.assertEqual(actual, self.findings)

    def test_duplicate_lines_and_shifted_locations_preserve_original_mapping(self) -> None:
        self.source.write_text("prefix\n" + self.source.read_text())
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "shift records")
        shifted = [
            {**row, "StartLine": row["StartLine"] + 1, "EndLine": row["EndLine"] + 1}
            for row in self.rows
        ]
        self.assertEqual(secrets.evaluate(shifted, self.root, tree=True), self.findings)
        repeated = self.root / "repeated.txt"
        repeated.write_text("same\n" * 8)
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "duplicate content")
        rows = [
            {**self.rows[0], "File": "repeated.txt", "StartLine": i, "EndLine": i}
            for i in range(1, 9)
        ]
        expected = [secrets.occurrence(self.root, row, True) for row in rows]
        self.assertEqual(
            [(f.identity, f.locator) for f in secrets.evaluate(rows, self.root, tree=True)],
            expected,
        )

    def test_mixed_commit_multiline_and_invalid_locations_fail_closed(self) -> None:
        self.source.write_text(
            "changed\n" + "\n".join(self.source.read_text().splitlines()[1:]) + "\n"
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "change first record")
        with self.assertRaises(PolicyError):
            secrets.evaluate([{**self.rows[0], "EndLine": 2}], self.root, tree=True)
        for change in (
            {"File": "../outside"},
            {"File": "/outside"},
            {"StartLine": 0},
            {"EndLine": 0},
            {"StartLine": True},
        ):
            with self.subTest(change=change), self.assertRaises(PolicyError):
                secrets.evaluate([{**self.rows[0], **change}], self.root, tree=True)

    def test_exact_count_deduplicates_history_and_tree_and_preserves_old_approvals(self) -> None:
        tree = secrets.evaluate(self.rows, self.root, tree=True)
        accepted, bindings = approved_evidence(self.root, self.findings + tree, self.registry)
        self.assertEqual(len(accepted), len(self.findings))
        self.assertEqual(bindings[0]["resolved_matches"], len(self.findings))
        counts = policy_counts(self.findings + tree, accepted)
        self.assertEqual(counts["blocked"], 0)
        self.assertEqual(counts["excepted"], len(self.findings))
        old = frozenset({("secret", self.findings[0].identity)})
        self.assertEqual(policy_counts(self.findings, old)["excepted"], 1)

    def test_invalid_registry_or_any_mismatched_binding_rejects(self) -> None:
        changes = [
            {"commit": "a" * 40},
            {"path": "renamed.jsonl"},
            {"git_blob": "a" * 40},
            {"rule": "new-rule"},
            {"reported_matches": 0},
            {"reported_matches": 1},
            {"reported_matches": True},
            {"approval": "PENDING"},
            {"approval": ""},
            {"reason": ""},
            {"resolution": "used_in_tests"},
            {"unexpected": "field"},
            {"path": "../records.jsonl"},
            {"path": "/records.jsonl"},
        ]
        for change in changes:
            data = copy.deepcopy(self.data)
            data["entries"][0].update(change)
            self.registry.write_text(json.dumps(data))
            with self.subTest(change=change), self.assertRaises(PolicyError):
                approved_evidence(self.root, self.findings, self.registry)
        for data in (
            {"schema": True, "entries": []},
            {"schema": 2, "entries": []},
            {**self.data, "entries": self.data["entries"] * 2},
        ):
            self.registry.write_text(json.dumps(data))
            with self.assertRaises(PolicyError):
                approved_evidence(self.root, self.findings, self.registry)
        self.registry.unlink()
        with self.assertRaises(PolicyError):
            approved_evidence(self.root, self.findings, self.registry)

    def test_new_blob_path_commit_and_uuid_shaped_findings_remain_blocked(self) -> None:
        self.source.write_text(self.source.read_text() + 'key="new credential"\n')
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "new data")
        new = [
            {
                **self.rows[0],
                "Commit": git(self.root, "rev-parse", "HEAD"),
                "StartLine": 601,
                "EndLine": 601,
            }
        ]
        found = self.findings + secrets.evaluate(new, self.root, tree=True)
        accepted, _ = approved_evidence(self.root, found, self.registry)
        self.assertEqual(policy_counts(found, accepted)["blocked"], 1)
        git(self.root, "mv", "records.jsonl", "new.jsonl")
        git(self.root, "commit", "-qm", "move path")
        moved = secrets.evaluate([{**self.rows[0], "File": "new.jsonl"}], self.root, tree=True)
        accepted, _ = approved_evidence(self.root, self.findings + moved, self.registry)
        self.assertEqual(policy_counts(self.findings + moved, accepted)["blocked"], 1)

    def test_same_count_with_a_new_occurrence_identity_cannot_borrow_approval(self) -> None:
        replacement = Finding("secret", "f" * 64, "high", self.findings[0].locator)
        with self.assertRaises(PolicyError):
            approved_evidence(self.root, [replacement, *self.findings[1:]], self.registry)

    def test_tree_column_variation_does_not_silently_expand_approved_occurrences(self) -> None:
        tree = secrets.evaluate([{**self.rows[0], "EndColumn": 9}], self.root, tree=True)
        self.assertNotEqual(tree[0].identity, self.findings[0].identity)
        self.assertEqual(tree[0].locator, self.findings[0].locator)
        with self.assertRaises(PolicyError):
            approved_evidence(self.root, self.findings + tree, self.registry)

    def test_configuration_digest_covers_registry_and_public_output_stays_bounded(self) -> None:
        policy = self.root / ".github/security"
        policy.mkdir(parents=True)
        registry = policy / "evidence-exceptions.json"
        registry.write_text(json.dumps(self.data))
        (self.root / ".github/workflows").mkdir()
        (self.root / ".github/workflows/security.yml").write_text("name: fixture\n")
        (self.root / "tools/security").mkdir(parents=True)
        before = configuration(self.root)
        registry.write_text(json.dumps({"schema": 1, "entries": []}))
        self.assertNotEqual(configuration(self.root), before)
        accepted, bindings = approved_evidence(self.root, self.findings, self.registry)
        rendered = summary({"excepted": len(accepted)}, [], accepted, artifact_bindings=bindings)
        self.assertIn("resolved_matches", rendered)
        self.assertNotIn("PRIVATE_SENTINEL", rendered)
        with self.assertRaises(PolicyError):
            summary({}, [], accepted, artifact_bindings=[{"Secret": "PRIVATE_SENTINEL"}])
        error = io.StringIO()
        with (
            redirect_stderr(error),
            self.assertRaises(RuntimeError),
            observed_stage("history_scan"),
        ):
            raise RuntimeError("PRIVATE_SENTINEL")
        self.assertNotIn("PRIVATE_SENTINEL", error.getvalue())

    def test_cli_groups_only_resolved_rows_and_still_reports_and_blocks_new_findings(self) -> None:
        policy = self.root / ".github/security"
        policy.mkdir(parents=True)
        (policy / "exceptions.json").write_text(json.dumps({"schema": 1, "exceptions": []}))
        (policy / "evidence-exceptions.json").write_text(self.registry.read_text())
        (policy / "tools.json").write_text(
            json.dumps({"tools": {"gitleaks": {"version": "fixture"}}})
        )
        new = Finding("secret", "e" * 64, "high", ("generic-api-key", "b" * 40, "other", "1", "1"))
        output = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [
                    "fixture",
                    "secrets",
                    "--root",
                    str(self.root),
                    "--directory",
                    str(self.root / "reports"),
                    "--binary",
                    "fixture",
                ],
            ),
            patch.object(
                cli, "candidate", return_value=Candidate("a" * 40, "a" * 40, "a" * 40, "1", "1")
            ),
            patch.object(cli, "configuration", return_value="a" * 64),
            patch.object(cli, "scan_secrets", return_value=([*self.findings, new], 1)),
            patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}),
            redirect_stdout(output),
        ):
            self.assertEqual(cli.main(), 1)
        public = json.loads(
            html.unescape(output.getvalue().removeprefix("<pre>").strip().removesuffix("</pre>"))
        )
        self.assertEqual(public["scan"]["counts"]["blocked"], 1)
        self.assertEqual(len(public["findings"]), 1)
        self.assertEqual(public["findings"][0]["identity"], new.identity)
        self.assertEqual(public["approved_evidence"][0]["resolved_matches"], len(self.findings))

    def test_unresolved_public_summary_limit_is_not_relaxed(self) -> None:
        findings = [
            Finding("secret", digest(i), "high", ("generic-api-key", "a" * 40, "x" * 900, "1", "1"))
            for i in range(1000)
        ]
        with self.assertRaises(PolicyError):
            summary({}, findings, frozenset())


@unittest.skipUnless(os.environ.get("SECURITY_SCANNER_PROBES"), "opt-in pinned scanner")
class EvidenceScannerTests(EvidenceFixture):
    def test_real_scanner_new_credential_and_new_uuid_are_not_approved(self) -> None:
        binary = Path(os.environ["SECURITY_SCANNER_PROBES"]) / "gitleaks"
        findings, _ = scan_secrets(self.root, ROOT, binary)
        data = copy.deepcopy(self.data)
        data["entries"][0]["reported_matches"] = len({f.identity for f in findings})
        data["entries"][0]["occurrence_digest"] = digest(sorted({f.identity for f in findings}))
        self.registry.write_text(json.dumps(data))
        accepted, _ = approved_evidence(self.root, findings, self.registry)
        self.assertEqual(policy_counts(findings, accepted)["blocked"], 0)
        with self.source.open("a") as out:
            out.write(
                'binance_api_key="' + hashlib.sha256(b"synthetic credential").hexdigest() + '"\n'
            )
        (self.root / "other.jsonl").write_text(
            json.dumps({"key": str(uuid5(NAMESPACE_URL, "other"))})
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "new synthetic credentials")
        changed, _ = scan_secrets(self.root, ROOT, binary)
        accepted, _ = approved_evidence(self.root, changed, self.registry)
        self.assertGreater(policy_counts(changed, accepted)["blocked"], 0)
        opened = [f for f in changed if (f.kind, f.identity) not in accepted]
        self.assertTrue(any(f.locator[2:4] == ("records.jsonl", "601") for f in opened))
        self.assertTrue(any(f.locator[2] == "other.jsonl" for f in opened))
