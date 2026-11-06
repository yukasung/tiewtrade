"""Regression cases from the Security CI owner-requested code review."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from tools.security.dependencies import evaluate, inventory
from tools.security.model import array, obj, policy_counts
from tools.security.scan import scan_secrets
from tools.security.severity import valid_vector
from tools.security.system import git
from tools.security.tests.test_adapters import lockfiles, osv_report

V3 = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
V4 = "CVSS:4.0/AV:N/AC:H/AT:P/PR:N/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N"
ROOT = Path(__file__).resolve().parents[3]


class SeverityRegressionTests(unittest.TestCase):
    def test_valid_and_malformed_vectors(self) -> None:
        for kind, vector in [
            ("CVSS_V3", V3),
            ("CVSS_V3", V3.replace("3.1", "3.0")),
            ("CVSS_V3", V3 + "/E:X/MC:L"),
            ("CVSS_V4", V4),
            ("CVSS_V4", V4 + "/MSI:S/U:Amber"),
        ]:
            with self.subTest(vector=vector):
                self.assertTrue(valid_vector({"type": kind, "score": vector}))
        for value in [
            None,
            {},
            {"score": V3},
            {"type": "CVSS_V4", "score": V3},
            {"type": "CVSS_V3", "score": 0},
            *(
                {"type": "CVSS_V3", "score": vector}
                for vector in [
                    "not-a-CVSS-vector",
                    "CVSS:3.1/test",
                    V3 + "/AV:N",
                    V3.replace("/AC:L", ""),
                    V3.replace("AC:L", "AC:INVALID"),
                    V3 + "/UNKNOWN:N",
                    V3 + "/E:",
                ]
            ),
        ]:
            with self.subTest(value=value):
                self.assertFalse(valid_vector(value))

    def test_invalid_advisory_cannot_borrow_group_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lockfiles(root)
            for score in ("0.0", "3.0", "5.0", "9.0"):
                for mixed in (False, True):
                    report = osv_report(root)
                    package = obj(array(obj(array(report["results"])[0])["packages"])[0])
                    advisories = [
                        {
                            "id": "bad",
                            "severity": [{"type": "CVSS_V3", "score": "not-a-CVSS-vector"}],
                        }
                    ]
                    if mixed:
                        advisories.append(
                            {"id": "valid", "severity": [{"type": "CVSS_V3", "score": V3}]}
                        )
                    package["vulnerabilities"] = advisories
                    package["groups"] = [
                        {"ids": [a["id"] for a in advisories], "max_severity": score}
                    ]
                    findings, _ = evaluate(report, root, inventory(root))
                    counts = policy_counts(findings, frozenset())
                    self.assertEqual(counts["needs_triage"], len(advisories))
                    self.assertEqual(counts["none"], 0)


@unittest.skipUnless(os.environ.get("SECURITY_SCANNER_PROBES"), "opt-in pinned scanner probes")
class SecretRenameRegressionTests(unittest.TestCase):
    def test_rename_move_back_and_new_path_approval(self) -> None:
        binary = Path(os.environ["SECURITY_SCANNER_PROBES"]) / "gitleaks"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            git(root, "init", "-q")
            git(root, "config", "user.email", "fixture@example.invalid")
            git(root, "config", "user.name", "Synthetic fixture")
            (root / "old.env").write_text(
                'binance_api_key="'
                + hashlib.sha256(b"synthetic venue fixture only").hexdigest()
                + '"\n'
            )
            git(root, "add", ".")
            git(root, "commit", "-qm", "original occurrence")
            original, _ = scan_secrets(root, ROOT, binary)
            approvals = frozenset((f.kind, f.identity) for f in original)
            git(root, "mv", "old.env", "new.env")
            git(root, "commit", "-qm", "rename")
            moved, _ = scan_secrets(root, ROOT, binary)
            self.assertGreater(policy_counts(moved, approvals)["blocked"], 0)
            moved_approvals = approvals | frozenset((f.kind, f.identity) for f in moved)
            self.assertEqual(policy_counts(moved, moved_approvals)["blocked"], 0)
            (root / "unrelated.txt").write_text("unrelated change\n")
            git(root, "add", ".")
            git(root, "commit", "-qm", "unrelated change")
            unchanged, _ = scan_secrets(root, ROOT, binary)
            self.assertEqual(policy_counts(unchanged, moved_approvals)["blocked"], 0)
            git(root, "mv", "new.env", "old.env")
            git(root, "commit", "-qm", "move back")
            returned, _ = scan_secrets(root, ROOT, binary)
            self.assertGreater(policy_counts(returned, moved_approvals)["blocked"], 0)
            git(root, "rm", "old.env")
            git(root, "commit", "-qm", "remove moved occurrence")
            removed, _ = scan_secrets(root, ROOT, binary)
            self.assertGreater(policy_counts(removed, moved_approvals)["blocked"], 0)
