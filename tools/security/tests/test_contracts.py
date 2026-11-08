"""Security-specific integration contracts and redacted public reporting."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.response import addinfourl

from tools.security import sarif
from tools.security.model import Candidate, PolicyError, array, digest, manifest, obj, policy_counts
from tools.security.reporting import summary
from tools.security.system import download_verified, install
from tools.security.tests.test_adapters import sarif_report

ROOT = Path(__file__).resolve().parents[3]
RELEASE_URL = "https://github.com/fixture/tool/releases/download/v1/tool.tar.gz"


def release_metadata(url: str = RELEASE_URL) -> dict[str, object]:
    return {
        "assets": [
            {
                "id": 7,
                "name": url.rsplit("/", 1)[1],
                "browser_download_url": url,
                "state": "uploaded",
                "url": "https://untrusted.invalid/must-not-be-followed",
            }
        ]
    }


def binary_response(payload: bytes, content_type: str = "application/octet-stream") -> addinfourl:
    headers = Message()
    headers["Content-Type"] = content_type
    return addinfourl(io.BytesIO(payload), headers, "https://api.github.com/fixture", 200)


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

    def test_action_cli_notification_references_without_telemetry(self) -> None:
        for language, prefix, baseline in [
            ("python", "py", "python"),
            ("javascript-typescript", "js", "javascript"),
            ("actions", "actions", "actions"),
        ]:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "sample.py").write_text("# synthetic source\n")
                report = sarif_report(language)
                run = obj(array(report["runs"])[0])
                tool = obj(run["tool"])
                driver = obj(tool["driver"])
                driver["notifications"] = [{"id": "cli/expected-extracted-files/" + baseline}]
                tool["extensions"] = [
                    {
                        "name": "queries",
                        "notifications": [
                            {"id": prefix + "/diagnostics/successfully-extracted-files"}
                        ],
                    }
                ]
                invocation = obj(array(run["invocations"])[0])
                notes = array(invocation["toolExecutionNotifications"])
                notes.pop(0)
                obj(notes[0])["descriptor"] = {"index": 0, "toolComponent": {"index": 0}}
                obj(notes[1])["descriptor"] = {"index": 0}
                if language == "actions":
                    run["properties"] = {}
                _, coverage = sarif.evaluate(report, root, language)
                self.assertEqual(coverage, 1)
                obj(notes[0])["descriptor"] = {
                    "id": "conflicting",
                    "index": 0,
                    "toolComponent": {"index": 0},
                }
                with self.assertRaises(PolicyError):
                    sarif.evaluate(report, root, language)

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

    def test_transient_download_retries_and_still_verifies_checksum(self) -> None:
        payload = b"synthetic binary fixture"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "download"
            transient = urllib.error.HTTPError(
                "https://github.com/fixture", 503, "private", Message(), None
            )
            with (
                patch.dict("os.environ", {"GH_TOKEN": "PRIVATE_SENTINEL"}),
                patch(
                    "urllib.request.urlopen",
                    side_effect=[
                        transient,
                        io.BytesIO(json.dumps(release_metadata()).encode()),
                        binary_response(payload),
                    ],
                ) as request,
                patch("time.sleep"),
            ):
                download_verified(RELEASE_URL, target, expected)
            self.assertEqual(request.call_count, 3)
            self.assertEqual(target.read_bytes(), payload)
            metadata_request = request.call_args_list[1].args[0]
            binary_request = request.call_args_list[2].args[0]
            self.assertEqual(
                metadata_request.full_url,
                "https://api.github.com/repos/fixture/tool/releases/tags/v1",
            )
            self.assertEqual(
                binary_request.full_url,
                "https://api.github.com/repos/fixture/tool/releases/assets/7",
            )
            self.assertEqual(binary_request.get_header("Accept"), "application/octet-stream")
            for call in (metadata_request, binary_request):
                self.assertIsNone(call.get_header("Authorization"))
            with (
                patch("urllib.request.urlopen", return_value=io.BytesIO(b"tampered")) as request,
                self.assertRaisesRegex(PolicyError, "TOOL_CHECKSUM_MISMATCH"),
            ):
                download_verified("https://github.com/fixture", target, expected)
            self.assertEqual(request.call_count, 1)

    def test_release_fallback_covers_transient_errors_only(self) -> None:
        failures = [
            urllib.error.HTTPError(RELEASE_URL, code, "private", Message(), None)
            for code in (408, 429, 500, 502, 503, 504)
        ] + [urllib.error.URLError("private"), TimeoutError(), ConnectionError()]
        for failure in failures:
            with (
                self.subTest(failure=type(failure).__name__),
                tempfile.TemporaryDirectory() as temp,
            ):
                with (
                    patch(
                        "urllib.request.urlopen",
                        side_effect=[
                            failure,
                            io.BytesIO(json.dumps(release_metadata()).encode()),
                            binary_response(b"fixture"),
                        ],
                    ),
                    patch("time.sleep"),
                ):
                    target = Path(temp) / "archive"
                    download_verified(RELEASE_URL, target, hashlib.sha256(b"fixture").hexdigest())
                self.assertEqual(target.read_bytes(), b"fixture")

    def test_direct_success_does_not_query_release_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "archive"
            with patch("urllib.request.urlopen", return_value=io.BytesIO(b"fixture")) as request:
                download_verified(RELEASE_URL, target, hashlib.sha256(b"fixture").hexdigest())
            request.assert_called_once_with(RELEASE_URL, timeout=60)
            self.assertEqual(target.read_bytes(), b"fixture")

    def test_fallback_shares_three_attempt_budget(self) -> None:
        for metadata_fails in (False, True):
            with self.subTest(metadata_fails=metadata_fails), tempfile.TemporaryDirectory() as temp:
                failure = urllib.error.URLError("private")
                replies: list[object] = [failure]
                for _ in range(2):
                    if not metadata_fails:
                        replies.append(io.BytesIO(json.dumps(release_metadata()).encode()))
                    replies.append(failure)
                with (
                    patch("urllib.request.urlopen", side_effect=replies) as request,
                    patch("time.sleep") as sleep,
                    self.assertRaisesRegex(PolicyError, "TOOL_NETWORK_FAILURE"),
                ):
                    download_verified(RELEASE_URL, Path(temp) / "archive", "0" * 64)
                self.assertEqual(request.call_count, 3 if metadata_fails else 5)
                self.assertEqual(sleep.call_count, 2)

    def test_fallback_rejects_unbound_or_malformed_release_metadata(self) -> None:
        invalid: list[object] = [None, [], {}, {"assets": {}}, {"assets": []}]
        for field, value in (
            ("name", "different.tar.gz"),
            ("browser_download_url", RELEASE_URL.replace("fixture", "other")),
            ("state", "new"),
            ("id", True),
            ("id", 0),
            ("id", -1),
            ("id", "7"),
        ):
            metadata = release_metadata()
            obj(array(metadata["assets"])[0])[field] = value
            invalid.append(metadata)
        duplicate = release_metadata()
        array(duplicate["assets"]).append(copy.deepcopy(array(duplicate["assets"])[0]))
        invalid.append(duplicate)
        payloads = [json.dumps(item).encode() for item in invalid]
        payloads += [b"not json", b"\xff", b" " * (2 * 1024 * 1024 + 1)]
        for index, payload in enumerate(payloads):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp:
                with (
                    patch(
                        "urllib.request.urlopen",
                        side_effect=[TimeoutError(), io.BytesIO(payload)],
                    ) as request,
                    patch("time.sleep"),
                    self.assertRaises(PolicyError),
                ):
                    download_verified(RELEASE_URL, Path(temp) / "archive", "0" * 64)
                self.assertEqual(request.call_count, 2)

    def test_fallback_rejects_non_release_paths_and_credentials(self) -> None:
        for url in (
            "http://github.com/fixture/tool/releases/download/v1/tool.tar.gz",
            RELEASE_URL + "?token=private",
            RELEASE_URL + "#fragment",
            RELEASE_URL.replace("github.com", "github.com.untrusted.invalid"),
            RELEASE_URL.replace("github.com", "private@github.com"),
            RELEASE_URL.replace("github.com", "github.com:443"),
            RELEASE_URL.replace("/v1/", "/../"),
            RELEASE_URL.replace("/fixture/", "/%2e%2e/"),
        ):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as temp:
                with (
                    patch("urllib.request.urlopen", side_effect=TimeoutError()) as request,
                    patch("time.sleep"),
                    self.assertRaisesRegex(PolicyError, "INVALID_TOOL_PIN"),
                ):
                    download_verified(url, Path(temp) / "archive", "0" * 64)
                self.assertEqual(request.call_count, 1)

    def test_fallback_never_installs_json_or_wrong_checksum(self) -> None:
        pin = json.loads((ROOT / ".github/security/tools.json").read_text())["tools"]["gitleaks"]
        url = pin["platforms"]["Linux-x86_64"]["url"]
        for content_type in ("application/json", "application/octet-stream"):
            with self.subTest(content_type=content_type), tempfile.TemporaryDirectory() as temp:
                target = Path(temp)
                with (
                    patch("platform.system", return_value="Linux"),
                    patch("platform.machine", return_value="x86_64"),
                    patch(
                        "urllib.request.urlopen",
                        side_effect=[
                            TimeoutError(),
                            io.BytesIO(json.dumps(release_metadata(url)).encode()),
                            binary_response(b"tampered", content_type),
                        ],
                    ) as request,
                    patch("time.sleep"),
                    self.assertRaisesRegex(
                        PolicyError,
                        "INVALID_TOOL_RELEASE"
                        if content_type == "application/json"
                        else "TOOL_CHECKSUM_MISMATCH",
                    ),
                ):
                    install(ROOT, "gitleaks", target)
                self.assertEqual(request.call_count, 3)
                self.assertEqual(list(target.iterdir()), [])

    def test_permanent_download_error_is_not_retried(self) -> None:
        for code in (401, 403, 404):
            for stage in ("direct", "metadata", "binary"):
                with self.subTest(code=code, stage=stage), tempfile.TemporaryDirectory() as temp:
                    error = urllib.error.HTTPError(RELEASE_URL, code, "private", Message(), None)
                    replies: list[object] = []
                    if stage != "direct":
                        replies.append(TimeoutError())
                    if stage == "binary":
                        replies.append(io.BytesIO(json.dumps(release_metadata()).encode()))
                    replies.append(error)
                    with (
                        patch("urllib.request.urlopen", side_effect=replies) as request,
                        patch("time.sleep"),
                        self.assertRaisesRegex(PolicyError, "TOOL_HTTP_ERROR"),
                    ):
                        download_verified(RELEASE_URL, Path(temp) / "download", "0" * 64)
                    self.assertEqual(request.call_count, len(replies))

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
        self.assertIn("CODEQL_ACTION_FILE_COVERAGE_ON_PRS: 'true'", workflow)
        self.assertEqual(workflow.count("persist-credentials: false"), 5)
