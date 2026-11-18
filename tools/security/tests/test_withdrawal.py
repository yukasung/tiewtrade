"""An absent advisory requires current, exact withdrawal evidence, never a waiver."""

from __future__ import annotations

import copy
import io
import json
import unittest
from email.message import Message
from typing import Any
from unittest.mock import patch
from urllib.response import addinfourl

from tools.security.dependencies import trusted_findings
from tools.security.model import PolicyError, policy_counts
from tools.security.withdrawal import ADVISORY, API, ARTIFACT, LIMIT, verify_withdrawal


class WithdrawalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = {
            "name": "picomatch",
            "version": "4.0.7",
            "artifact_sha256": ARTIFACT,
        }
        self.row: dict[str, Any] = {
            "package": {
                "ecosystem": "npm",
                "name": "picomatch",
                "version": "4.0.7",
                "purl": "pkg:npm/picomatch@4.0.7",
            },
            "vulnerabilities": [],
            "groups": [],
        }
        self.record: dict[str, Any] = {
            "id": ADVISORY,
            "withdrawn": "2026-11-18T15:38:56Z",
            "affected": [
                {
                    "package": {"ecosystem": "npm", "name": "picomatch"},
                    "ranges": [
                        {
                            "type": "SEMVER",
                            "events": [
                                {"introduced": "0"},
                                {"last_affected": "4.0.7"},
                            ],
                        }
                    ],
                }
            ],
        }

    def responses(self, query: object = None) -> list[addinfourl]:
        return [
            addinfourl(
                io.BytesIO(json.dumps(self.record).encode()),
                Message(),
                API + "/vulns/" + ADVISORY,
                200,
            ),
            addinfourl(
                io.BytesIO(json.dumps({} if query is None else query).encode()),
                Message(),
                API + "/query",
                200,
            ),
        ]

    def test_current_exact_withdrawal_and_requests_repeat_on_every_scan(self) -> None:
        with patch(
            "urllib.request.urlopen", side_effect=self.responses() + self.responses()
        ) as request:
            for _ in range(2):
                self.assertEqual(
                    trusted_findings(self.row, self.entry, verify_withdrawal), []
                )
        self.assertEqual(request.call_count, 4)
        first, second = request.call_args_list[:2]
        self.assertEqual(first.args[0].full_url, API + "/vulns/" + ADVISORY)
        self.assertEqual(first.kwargs, {"timeout": 10})
        self.assertEqual(
            json.loads(second.args[0].data),
            {
                "package": {"ecosystem": "npm", "name": "picomatch"},
                "version": "4.0.7",
            },
        )

    def test_offline_default_and_wrong_package_remain_closed(self) -> None:
        with patch("urllib.request.urlopen") as request:
            with self.assertRaises(PolicyError):
                trusted_findings(self.row, self.entry)
            self.row["package"]["version"] = "0"
            with self.assertRaises(PolicyError):
                trusted_findings(self.row, self.entry, verify_withdrawal)
            request.assert_not_called()

    def test_other_artifact_or_identity_never_uses_withdrawal(self) -> None:
        for key, value in [
            ("artifact_sha256", "a" * 64),
            ("name", "other"),
            ("version", "0"),
        ]:
            entry = {**self.entry, key: value}
            with self.subTest(key=key), patch("urllib.request.urlopen") as request:
                with self.assertRaises(PolicyError):
                    verify_withdrawal(self.row, entry)
                request.assert_not_called()

    def test_wrong_missing_unwithdrawn_invalid_or_future_record_is_rejected(
        self,
    ) -> None:
        original = copy.deepcopy(self.record)
        changes: list[dict[str, object]] = [
            {"id": "OTHER"},
            {"withdrawn": None},
            {"withdrawn": ""},
            {"withdrawn": "2026-11-18"},
            {"withdrawn": "2026-02-30T00:00:00Z"},
            {"withdrawn": "9999-01-01T00:00:00Z"},
            {"affected": []},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.record = {**original, **change}
                with (
                    patch("urllib.request.urlopen", side_effect=self.responses()),
                    self.assertRaises(PolicyError),
                ):
                    verify_withdrawal(self.row, self.entry)

    def test_wrong_package_or_range_in_record_is_rejected(self) -> None:
        original = copy.deepcopy(self.record)
        for fault in ["ecosystem", "name", "range"]:
            record = copy.deepcopy(original)
            if fault == "range":
                record["affected"][0]["ranges"][0]["events"][-1] = {
                    "last_affected": "0"
                }
            else:
                record["affected"][0]["package"][fault] = "other"
            self.record = record
            with (
                self.subTest(fault=fault),
                patch("urllib.request.urlopen", side_effect=self.responses()),
                self.assertRaises(PolicyError),
            ):
                verify_withdrawal(self.row, self.entry)

    def test_query_failure_invalid_shape_or_inconsistent_findings_is_rejected(
        self,
    ) -> None:
        for query in [
            [],
            {"error": "private"},
            {"next_page_token": "more"},
            {"vulns": None},
            {"vulns": [{"id": "OTHER"}]},
            {"vulns": [{"id": ADVISORY}]},
        ]:
            with (
                self.subTest(query=query),
                patch("urllib.request.urlopen", side_effect=self.responses(query)),
                self.assertRaises(PolicyError),
            ):
                verify_withdrawal(self.row, self.entry)
        with (
            patch(
                "urllib.request.urlopen",
                side_effect=[self.responses()[0], TimeoutError("private")],
            ),
            self.assertRaisesRegex(
                PolicyError, "^TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN$"
            ),
        ):
            verify_withdrawal(self.row, self.entry)

    def test_http_failure_malformed_oversize_duplicate_json_and_redirect_are_rejected(
        self,
    ) -> None:
        for content, url, code in [
            (b"not json", API + "/vulns/" + ADVISORY, 200),
            (b"{}" + b" " * LIMIT, API + "/vulns/" + ADVISORY, 200),
            (b'{"id":"wrong","id":"right"}', API + "/vulns/" + ADVISORY, 200),
            (b"{}", "https://other.invalid/", 200),
            (b"{}", API + "/vulns/" + ADVISORY, 503),
        ]:
            response = addinfourl(io.BytesIO(content), Message(), url, code)
            with (
                self.subTest(url=url, code=code, size=len(content)),
                patch("urllib.request.urlopen", return_value=response),
                self.assertRaises(PolicyError),
            ):
                verify_withdrawal(self.row, self.entry)
        with (
            patch("urllib.request.urlopen", side_effect=OSError("private")),
            self.assertRaisesRegex(
                PolicyError, "^TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN$"
            ),
        ):
            verify_withdrawal(self.row, self.entry)

    def test_other_high_critical_unknown_findings_still_block(self) -> None:
        for score, severity in [
            ("8.7", "high"),
            ("9.8", "critical"),
            ("unknown", "unknown"),
        ]:
            advisory = {
                "id": "OTHER",
                "severity": [
                    {
                        "type": "CVSS_V3",
                        "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    }
                ],
            }
            self.row["vulnerabilities"] = [advisory]
            self.row["groups"] = [{"ids": ["OTHER"], "max_severity": score}]
            with patch(
                "urllib.request.urlopen",
                side_effect=self.responses({"vulns": [advisory]}),
            ):
                findings = trusted_findings(self.row, self.entry, verify_withdrawal)
            self.assertEqual(findings[0].severity, severity)
            counts = policy_counts(findings, frozenset())
            self.assertEqual(counts["blocked"] + counts["needs_triage"], 1)
            changed = {**advisory, "severity": []}
            with (
                patch(
                    "urllib.request.urlopen",
                    side_effect=self.responses({"vulns": [changed]}),
                ),
                self.assertRaises(PolicyError),
            ):
                trusted_findings(self.row, self.entry, verify_withdrawal)

    def test_original_active_advisory_path_needs_no_withdrawal_lookup(self) -> None:
        self.row["vulnerabilities"] = [
            {
                "id": ADVISORY,
                "severity": [
                    {
                        "type": "CVSS_V3",
                        "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    }
                ],
            }
        ]
        self.row["groups"] = [{"ids": [ADVISORY], "max_severity": "8.7"}]
        with patch("urllib.request.urlopen") as request:
            findings = trusted_findings(self.row, self.entry, verify_withdrawal)
            request.assert_not_called()
        self.assertEqual(len(findings), 1)
