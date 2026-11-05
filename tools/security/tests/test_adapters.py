"""Scanner schema and completeness contracts independent of network availability."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.security import dependencies, sarif
from tools.security.model import PolicyError, policy_counts


def lockfiles(root: Path) -> None:
    (root / "backend").mkdir(exist_ok=True)
    (root / "frontend").mkdir(exist_ok=True)
    (root / "backend/uv.lock").write_text("""version = 1
revision = 3
requires-python = ">=3.12"
[[package]]
name = "tiewtrade-backend"
version = "0.1.0"
source = { editable = "." }
[[package]]
name = "Requests"
version = "2.31.0"
source = { registry = "https://pypi.org/simple" }
""")
    (root / "frontend/package-lock.json").write_text(
        json.dumps(
            {
                "name": "fixture",
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "fixture"},
                    "node_modules/lodash": {
                        "version": "4.17.20",
                        "dev": True,
                        "optional": True,
                        "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.20.tgz",
                    },
                },
            }
        )
    )


def osv_report(root: Path) -> dict[str, object]:
    return {
        "results": [
            {
                "source": {"path": str(root / name), "type": "lockfile"},
                "packages": [
                    {"package": {"ecosystem": ecosystem, "name": package, "version": version}}
                ],
            }
            for name, ecosystem, package, version in [
                ("backend/uv.lock", "PyPI", "requests", "2.31.0"),
                ("frontend/package-lock.json", "npm", "lodash", "4.17.20"),
            ]
        ]
    }


def sarif_report(language: str = "python", score: object = "8.1") -> dict[str, object]:
    prefix = {"python": "py", "javascript-typescript": "js", "actions": "actions"}[language]
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQL",
                        "rules": [
                            {
                                "id": prefix + "/unsafe",
                                "properties": {"security-severity": score, "tags": ["security"]},
                            },
                            {
                                "id": prefix + "/lines-of-code",
                                "properties": {"tags": ["lines-of-code"]},
                            },
                        ],
                    }
                },
                "invocations": [{"executionSuccessful": True}],
                "artifacts": [{"location": {"uri": "sample.py"}, "roles": ["analysisTarget"]}],
                "properties": {
                    "metricResults": [{"ruleId": prefix + "/lines-of-code", "value": 10}]
                },
                "results": [
                    {
                        "ruleId": prefix + "/unsafe",
                        "message": {"text": "PRIVATE_SENTINEL"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "sample.py"},
                                    "region": {
                                        "startLine": 1,
                                        "snippet": {"text": "PRIVATE_SENTINEL"},
                                    },
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        lockfiles(self.root)
        (self.root / "sample.py").write_text("# synthetic source\n")

    def test_inventory_includes_dev_optional_and_normalizes_pypi(self) -> None:
        expected = dependencies.inventory(self.root)
        findings, coverage = dependencies.evaluate(osv_report(self.root), self.root, expected)
        self.assertEqual(coverage, 2)
        self.assertEqual(findings, [])

    def test_missing_packages_sources_and_locks_fail(self) -> None:
        expected = dependencies.inventory(self.root)
        report = osv_report(self.root)
        from tools.security.model import array, obj

        array(obj(array(report["results"])[0])["packages"]).clear()
        with self.assertRaises(PolicyError):
            dependencies.evaluate(report, self.root, expected)
        (self.root / "backend/uv.lock").write_text(
            (self.root / "backend/uv.lock")
            .read_text()
            .replace("https://pypi.org/simple", "https://unsupported.invalid/simple")
        )
        with self.assertRaises(PolicyError):
            dependencies.inventory(self.root)
        (self.root / "backend/uv.lock").unlink()
        with self.assertRaises(OSError):
            dependencies.inventory(self.root)

    def test_osv_severity_and_uncovered_conflicting_advisories(self) -> None:
        from tools.security.model import array, obj

        expected = dependencies.inventory(self.root)
        for score, severity in [
            ("7.0", "high"),
            ("9.0", "critical"),
            ("4.0", "medium"),
            (None, "unknown"),
            ("bad", "unknown"),
        ]:
            report = osv_report(self.root)
            package = obj(array(obj(array(report["results"])[0])["packages"])[0])
            package["vulnerabilities"] = [
                {
                    "id": "GHSA-fixture",
                    "severity": [
                        {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
                    ],
                }
            ]
            package["groups"] = [{"ids": ["GHSA-fixture"], "max_severity": score}]
            findings, _ = dependencies.evaluate(report, self.root, expected)
            self.assertEqual(findings[0].severity, severity)
            package["groups"] = []
            with self.assertRaises(PolicyError):
                dependencies.evaluate(report, self.root, expected)
        package["groups"] = [{"ids": ["GHSA-fixture"], "max_severity": "8.0"}]
        package["vulnerabilities"] = [{"id": "GHSA-fixture"}]
        findings, _ = dependencies.evaluate(report, self.root, expected)
        self.assertEqual(findings[0].severity, "unknown")
        package["vulnerabilities"] = [{"id": "GHSA-fixture"}, {"id": "GHSA-fixture"}]
        with self.assertRaises(PolicyError):
            dependencies.evaluate(report, self.root, expected)

    def test_sarif_all_languages_full_results_and_no_message_leak(self) -> None:
        for language in ("python", "javascript-typescript", "actions"):
            findings, coverage = sarif.evaluate(sarif_report(language), self.root, language)
            self.assertEqual(coverage, 1)
            self.assertEqual(findings[0].severity, "high")
            self.assertNotIn("PRIVATE_SENTINEL", repr(findings))
            self.assertEqual(policy_counts(findings, frozenset())["blocked"], 1)

    def test_sarif_failures_coverage_and_suppressions(self) -> None:
        from tools.security.model import array, obj

        original = sarif_report()
        cases: list[tuple[str, object]] = [
            ("invocations", []),
            ("properties", {}),
            ("results", None),
        ]
        for field, value in cases:
            report = copy.deepcopy(original)
            obj(array(report["runs"])[0])[field] = value
            with self.assertRaises(PolicyError):
                sarif.evaluate(report, self.root, "python")
        run = obj(array(original["runs"])[0])
        obj(array(run["results"])[0])["suppressions"] = [{"kind": "inSource", "status": "accepted"}]
        findings, _ = sarif.evaluate(original, self.root, "python")
        self.assertEqual(policy_counts(findings, frozenset())["blocked"], 1)

    def test_sarif_extensions_and_unknown_not_warning_as_high(self) -> None:
        from tools.security.model import array, obj

        report = sarif_report(score=None)
        run = obj(array(report["runs"])[0])
        tool = obj(run["tool"])
        driver = obj(tool["driver"])
        rules = driver.pop("rules")
        tool["extensions"] = [{"name": "codeql/python-queries", "rules": rules}]
        findings, _ = sarif.evaluate(report, self.root, "python")
        self.assertEqual(findings[0].severity, "unknown")
        props = obj(obj(array(rules)[0])["properties"])
        props.pop("security-severity")
        props["tags"] = ["maintainability"]
        findings, _ = sarif.evaluate(report, self.root, "python")
        self.assertEqual(findings, [])

    def test_changed_content_invalidates_exception_identity(self) -> None:
        before, _ = sarif.evaluate(sarif_report(), self.root, "python")
        (self.root / "sample.py").write_text("# changed source\n")
        after, _ = sarif.evaluate(sarif_report(), self.root, "python")
        self.assertNotEqual(before[0].identity, after[0].identity)
        self.assertEqual(
            policy_counts(after, frozenset({("codeql", before[0].identity)}))["blocked"], 1
        )
