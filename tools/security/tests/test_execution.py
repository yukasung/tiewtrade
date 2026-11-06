"""Candidate binding and no-secret-output failure boundaries."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.security import cli
from tools.security.model import PolicyError
from tools.security.scan import execute, scan_dependencies, scan_secrets
from tools.security.system import candidate, git

ROOT = Path(__file__).resolve().parents[3]


class ExecutionTests(unittest.TestCase):
    def test_exception_payload_is_never_logged(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.object(cli, "main", side_effect=ValueError("PRIVATE_SENTINEL")),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            self.assertEqual(cli.entrypoint(), 2)
        self.assertNotIn("PRIVATE_SENTINEL", out.getvalue() + err.getvalue())

    def test_policy_error_diagnostics_are_allowlisted(self) -> None:
        for error, expected in [
            (PolicyError("PRIVATE_SENTINEL"), "INVALID_POLICY_DATA"),
            (PolicyError("MISSING_FILE_COVERAGE"), "MISSING_FILE_COVERAGE"),
        ]:
            out, err = io.StringIO(), io.StringIO()
            with (
                patch.object(cli, "main", side_effect=error),
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
            ):
                self.assertEqual(cli.entrypoint(), 2)
            self.assertNotIn("PRIVATE_SENTINEL", out.getvalue() + err.getvalue())
            self.assertIn(expected, err.getvalue())

    def test_tool_stderr_and_failed_exit_remain_private(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with (
            tempfile.TemporaryDirectory() as temp,
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            root = Path(temp)
            script = (
                "import sys; print('PRIVATE_SENTINEL'); "
                "sys.stderr.write('PRIVATE_SENTINEL'); sys.exit(3)"
            )
            with self.assertRaises(PolicyError):
                execute([sys.executable, "-c", script], root, root / "private.json", (0, 1))
        self.assertNotIn("PRIVATE_SENTINEL", out.getvalue() + err.getvalue())

    def test_candidate_checks_checkout_parents_and_current_api(self) -> None:
        commit, head, base = "a" * 40, "b" * 40, "c" * 40
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            event = root / "event.json"
            event.write_text(
                json.dumps(
                    {"pull_request": {"number": 1, "head": {"sha": head}, "base": {"sha": base}}}
                )
            )
            env = {
                "GITHUB_EVENT_PATH": str(event),
                "GITHUB_SHA": commit,
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_REPOSITORY": "owner/repo",
                "GH_TOKEN": "synthetic",
                "GITHUB_RUN_ID": "1",
                "GITHUB_RUN_ATTEMPT": "1",
            }
            for remote_head in (head, "d" * 40):
                response = io.BytesIO(
                    json.dumps(
                        {
                            "head": {"sha": remote_head},
                            "base": {"sha": base},
                            "merge_commit_sha": commit,
                        }
                    ).encode()
                )
                with (
                    patch.dict(os.environ, env),
                    patch("tools.security.system.git", side_effect=[commit, base + " " + head]),
                    patch("urllib.request.urlopen", return_value=response),
                ):
                    if remote_head == head:
                        self.assertEqual(candidate(root).head, head)
                    else:
                        with self.assertRaises(PolicyError):
                            candidate(root)
            with (
                patch.dict(os.environ, env),
                patch("tools.security.system.git", return_value=head),
                self.assertRaises(PolicyError),
            ):
                candidate(root)


@unittest.skipUnless(
    os.environ.get("SECURITY_SCANNER_PROBES"), "opt-in pinned scanner/network probes"
)
class ScannerProbes(unittest.TestCase):
    def test_real_gitleaks_history_tree_and_inline_allow(self) -> None:
        binary = Path(os.environ["SECURITY_SCANNER_PROBES"]) / "gitleaks"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            git(root, "init", "-q")
            git(root, "config", "user.email", "fixture@example.invalid")
            git(root, "config", "user.name", "Synthetic fixture")
            token = hashlib.sha256(b"synthetic venue fixture only").hexdigest()
            source = root / "fixture.env"
            source.write_text('binance_api_key="placeholder"\n')
            git(root, "add", ".")
            git(root, "commit", "-qm", "negative fixture")
            clean, _ = scan_secrets(root, ROOT, binary)
            self.assertEqual(clean, [])
            (root / ".gitattributes").write_text("fixture.env export-ignore\n")
            source.write_text('binance_api_key="' + token + '" # gitleaks:allow\n')
            git(root, "add", ".")
            material = base64.b64encode(hashlib.sha256(b"synthetic fixture only").digest()).decode()
            (root / "sealing.env").write_text("TIEWTRADE_SEALING_KEY_SESSION=1:" + material + "\n")
            git(root, "add", ".")
            git(root, "commit", "-qm", "synthetic addition")
            active, _ = scan_secrets(root, ROOT, binary)
            self.assertTrue(active)
            self.assertTrue(
                {"tiewtrade-venue-credential", "tiewtrade-sealing-key"}
                <= {finding.locator[0] for finding in active}
            )
            self.assertNotIn(token, repr(active))
            source.write_text("# removed\n")
            git(root, "add", ".")
            git(root, "commit", "-qm", "synthetic removal")
            removed, _ = scan_secrets(root, ROOT, binary)
            self.assertTrue(removed)
            self.assertTrue({f.identity for f in active} <= {f.identity for f in removed})
            source.write_text('binance_api_key="' + token + '"\n')
            git(root, "add", ".")
            git(root, "commit", "-qm", "new occurrence")
            reintroduced, _ = scan_secrets(root, ROOT, binary)
            self.assertGreater(
                len({f.identity for f in reintroduced}), len({f.identity for f in removed})
            )

    def test_real_osv_candidate_inventory(self) -> None:
        binary = Path(os.environ["SECURITY_SCANNER_PROBES"]) / "osv"
        findings, coverage = scan_dependencies(ROOT, ROOT, binary)
        self.assertGreater(coverage, 1)
        self.assertIsInstance(findings, list)
