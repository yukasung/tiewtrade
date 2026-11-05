"""Security-specific integration contracts and redacted public reporting."""

from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.security import sarif
from tools.security.model import Candidate, PolicyError, array, digest, manifest, obj, policy_counts
from tools.security.reporting import summary
from tools.security.system import install
from tools.security.tests.test_adapters import sarif_report

ROOT = Path(__file__).resolve().parents[3]


class ContractTests(unittest.TestCase):
    def test_sarif_index_references_and_incremental_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text("# safe fixture\n")
            report = sarif_report()
            run = obj(array(report["runs"])[0])
            tool = obj(run["tool"])
            driver = obj(tool["driver"])
            rules = driver.pop("rules")
            tool["extensions"] = [{"name": "queries", "rules": rules}]
            result = obj(array(run["results"])[0])
            result.pop("ruleId")
            result["rule"] = {"index": 0, "toolComponent": {"index": 0}}
            metric = obj(array(obj(run["properties"])["metricResults"])[0])
            metric.pop("ruleId")
            metric["rule"] = {"index": 1, "toolComponent": {"index": 0}}
            findings, files = sarif.evaluate(report, root, "python")
            self.assertEqual(files, 1)
            self.assertEqual(findings[0].severity, "high")
            invalid = copy.deepcopy(report)
            obj(obj(array(invalid["runs"])[0])["properties"])["incrementalMode"] = "diff-informed"
            with self.assertRaises(PolicyError):
                sarif.evaluate(invalid, root, "python")
            result["ruleId"] = "py/different-rule"
            with self.assertRaises(PolicyError):
                sarif.evaluate(report, root, "python")

    def test_public_summary_excludes_sarif_messages_and_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text("# safe fixture\n")
            findings, coverage = sarif.evaluate(sarif_report(), root, "python")
            record = manifest(
                "codeql-python",
                Candidate("a" * 40, "a" * 40, "a" * 40, "1", "1"),
                digest("config"),
                policy_counts(findings, frozenset()),
                coverage,
            )
            public = summary(record, findings, frozenset())
            self.assertNotIn("PRIVATE_SENTINEL", public)
            self.assertNotIn("snippet", public)
            self.assertIn("sample.py", public)
            self.assertIn(findings[0].identity, public)
            self.assertNotIn("PRIVATE_SENTINEL", json.dumps(record))

    def test_checksum_mismatch_never_installs_download(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            with (
                patch("urllib.request.urlopen", return_value=io.BytesIO(b"tampered binary")),
                self.assertRaisesRegex(PolicyError, "TOOL_CHECKSUM_MISMATCH"),
            ):
                install(ROOT, "gitleaks", target)
            self.assertFalse((target / "gitleaks").exists())

    def test_workflow_pins_match_registry_and_security_contract(self) -> None:
        import re

        workflow = (ROOT / ".github/workflows/security.yml").read_text()
        pins = obj(obj(json.loads((ROOT / ".github/security/tools.json").read_text()))["actions"])
        for action, commit in re.findall(r"uses: ([^@\s]+)@([^\s]+)", workflow):
            key = "github/codeql-action" if action.startswith("github/codeql-action/") else action
            self.assertRegex(commit, r"^[a-f0-9]{40}$")
            self.assertEqual(commit, obj(pins[key])["sha"])
        for forbidden in (
            "pull_request_target:",
            "workflow_run:",
            "${{ secrets.",
            "write",
            "continue-on-error",
            "paths:",
        ):
            self.assertNotIn(forbidden, workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("upload: never", workflow)
        self.assertIn("CODEQL_ACTION_DIFF_INFORMED_QUERIES: 'false'", workflow)
        self.assertEqual(workflow.count("persist-credentials: false"), 5)
