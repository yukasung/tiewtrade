"""Verify network diagnostic behavior without network access, sudo or APT changes."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import diagnose_e2e_network as network  # noqa: E402


def safe_metadata() -> dict[str, object]:
    return {
        "nameservers": ["127.0.0.53"],
        "resolver_status": "success",
        "proxy_env": dict.fromkeys(network.PROXY_NAMES, False),
        "apt_proxy": False,
        "apt_proxy_status": "success",
    }


class ProbeTests(unittest.TestCase):
    def probe(self, kind: str, result: network.CommandResult) -> dict[str, object]:
        with patch.object(network, "run_command", return_value=result):
            return network.probe(kind, network.HOSTS[1], "user", float("inf"))

    def test_dns_success_requires_actual_addresses_and_rejects_raw_output(self) -> None:
        self.assertEqual(
            self.probe(
                "dns",
                network.CommandResult(
                    "success",
                    "185.125.190.81 STREAM archive.ubuntu.com\n",
                    0,
                ),
            ),
            {"status": "success"},
        )
        for value in ("", "private-config-content\n", "not-an-IP STREAM name\n"):
            with self.subTest(value=value):
                self.assertEqual(
                    self.probe("dns", network.CommandResult("success", value, 0)),
                    {"status": "invalid_response"},
                )
        self.assertEqual(
            self.probe("dns", network.CommandResult("command_failed", "secret", 2)),
            {"status": "dns_failure"},
        )

    def test_https_classifies_dns_proxy_connection_http_tls_and_timeouts(self) -> None:
        expected = {
            5: "proxy_dns_failure",
            6: "dns_failure",
            7: "connection_failure",
            22: "http_failure",
            28: "timeout",
            35: "tls_failure",
            47: "redirect_failure",
            60: "certificate_failure",
            1: "operational_error",
            127: "tool_unavailable",
            124: "timeout",
            137: "timeout",
            -9: "timeout",
        }
        for code, status in expected.items():
            with self.subTest(code=code):
                self.assertEqual(
                    self.probe(
                        "https",
                        network.CommandResult(
                            "command_failed",
                            "private-proxy-credentials",
                            code,
                        ),
                    ),
                    {"status": status},
                )
        for status in ("timeout", "tool_unavailable", "operational_error"):
            self.assertEqual(self.probe("https", network.CommandResult(status)), {"status": status})

    def test_https_requires_success_status_and_never_emits_response_contents(self) -> None:
        self.assertEqual(
            self.probe("https", network.CommandResult("success", "200", 0)),
            {"status": "success", "http_status": 200},
        )
        for code in ("000", "404", "200\nprivate-data", "", "999"):
            with self.subTest(code=code):
                self.assertEqual(
                    self.probe("https", network.CommandResult("success", code, 0)),
                    {"status": "invalid_response"},
                )

    def test_commands_bound_sudo_and_preserve_tls(self) -> None:
        with patch.object(
            network,
            "run_command",
            return_value=network.CommandResult(
                "success",
                "200",
                0,
            ),
        ) as command:
            network.probe("https", network.HTTPS_URLS[0], "sudo", float("inf"))
        argv = command.call_args.args[0]
        self.assertEqual(argv[:6], ["sudo", "-n", "--", "timeout", "--signal=KILL", "7s"])
        self.assertEqual(argv[6:8], ["curl", "--disable"])
        self.assertIn("--max-time", argv)
        self.assertIn("--proto-redir", argv)
        self.assertEqual(argv[argv.index("--retry") + 1], "0")
        self.assertNotIn("--insecure", argv)
        self.assertNotIn("--verbose", argv)
        self.assertLessEqual(command.call_args.args[1], 8.0)

    def test_budget_exhaustion_does_not_start_commands(self) -> None:
        with patch.object(network, "run_command") as command:
            self.assertEqual(
                network.probe("dns", network.HOSTS[0], "sudo", 0), {"status": "budget_exhausted"}
            )
        command.assert_not_called()

    def test_command_boundary_enforces_real_timeout_and_sanitizes_os_errors(self) -> None:
        result = network.run_command([sys.executable, "-c", "import time; time.sleep(10)"], 0.05)
        self.assertEqual(result, network.CommandResult("timeout"))
        for error, status in (
            (FileNotFoundError("secret command"), "tool_unavailable"),
            (PermissionError("secret path"), "operational_error"),
        ):
            with patch.object(subprocess, "run", side_effect=error):
                self.assertEqual(network.run_command(["test"]), network.CommandResult(status))


class MetadataTests(unittest.TestCase):
    def test_metadata_logs_only_ip_nameservers_and_proxy_presence(self) -> None:
        with (
            patch.object(
                Path,
                "read_text",
                return_value=(
                    "nameserver 127.0.0.53\nsearch internal.private.invalid\n"
                    "# credentials: secret-value\nnameserver 2001:db8::1\n"
                ),
            ),
            patch.dict(os.environ, {"HTTPS_PROXY": "https://user:secret@proxy.invalid"}),
            patch.object(
                network,
                "run_command",
                return_value=network.CommandResult(
                    "success",
                    'Acquire::https::Proxy "https://user:secret@proxy.invalid";\n',
                    0,
                ),
            ),
        ):
            result = network.metadata()
        self.assertTrue(network.validate_metadata(result))
        self.assertEqual(result["nameservers"], ["127.0.0.53", "2001:db8::1"])
        self.assertTrue(result["apt_proxy"])
        proxies = result["proxy_env"]
        self.assertIsInstance(proxies, dict)
        assert isinstance(proxies, dict)
        self.assertTrue(proxies["HTTPS_PROXY"])
        for secret in ("secret", "proxy.invalid", "internal.private.invalid", "user:"):
            self.assertNotIn(secret, json.dumps(result))

    def test_missing_metadata_stays_unavailable_without_disclosing_read_error(self) -> None:
        with (
            patch.object(Path, "read_text", side_effect=OSError("secret filename")),
            patch.object(
                network, "run_command", return_value=network.CommandResult("tool_unavailable")
            ),
        ):
            result = network.metadata()
        self.assertEqual(result["resolver_status"], "unavailable")
        self.assertEqual(result["apt_proxy_status"], "tool_unavailable")
        self.assertNotIn("secret", json.dumps(result))

    def test_privileged_metadata_schema_rejects_extra_fields_and_unsanitized_values(self) -> None:
        candidates: list[object] = [
            {**safe_metadata(), "raw_proxy": "secret"},
            {**safe_metadata(), "nameservers": ["secret"]},
            {**safe_metadata(), "proxy_env": {"HTTPS_PROXY": "secret"}},
            {**safe_metadata(), "apt_proxy": "secret"},
            {**safe_metadata(), "resolver_status": "secret"},
            None,
            [],
            "secret",
        ]
        for value in candidates:
            with self.subTest(value=value):
                self.assertFalse(network.validate_metadata(value))


class DiagnosticGateTests(unittest.TestCase):
    def diagnose(
        self,
        dns_status: str = "success",
        sudo_https: str = "success",
        user_https: str = "success",
        metadata_output: str | None = None,
        control_https: str = "success",
    ) -> tuple[dict[str, object], bool]:
        def fake_probe(kind: str, target: str, context: str, deadline: float) -> dict[str, object]:
            if kind == "dns":
                return {"status": dns_status}
            if target == network.HTTPS_URLS[1]:
                return {"status": control_https}
            return {"status": sudo_https if context == "sudo" else user_https}

        with (
            patch.object(network, "metadata", side_effect=safe_metadata),
            patch.object(
                network,
                "run_command",
                return_value=network.CommandResult(
                    "success",
                    json.dumps(safe_metadata()) if metadata_output is None else metadata_output,
                    0,
                ),
            ),
            patch.object(network, "probe", side_effect=fake_probe),
        ):
            return network.diagnose()

    def test_dns_failure_does_not_block_successful_https_via_proxy(self) -> None:
        report, allowed = self.diagnose(dns_status="dns_failure")
        self.assertTrue(allowed)
        self.assertTrue(report["diagnostic_complete"])

    def test_sudo_archive_failure_blocks_even_when_user_https_succeeds(self) -> None:
        for status in ("dns_failure", "timeout", "certificate_failure", "connection_failure"):
            with self.subTest(status=status):
                report, allowed = self.diagnose(sudo_https=status)
                self.assertFalse(allowed)
                self.assertFalse(report["continue_installation"])

    def test_user_or_control_failure_does_not_override_successful_sudo_archive(self) -> None:
        self.assertTrue(self.diagnose(user_https="dns_failure", control_https="http_failure")[1])

    def test_missing_tools_invalid_output_or_incomplete_metadata_fail_closed(self) -> None:
        self.assertFalse(self.diagnose(dns_status="tool_unavailable")[1])
        self.assertFalse(self.diagnose(dns_status="budget_exhausted")[1])
        for output in ("not JSON secret", '{"secret":"value"}', "null"):
            with self.subTest(output=output):
                report, allowed = self.diagnose(metadata_output=output)
                self.assertFalse(allowed)
                self.assertNotIn("secret", json.dumps(report))

    def test_elapsed_global_budget_is_failure_even_after_successful_probes(self) -> None:
        with patch.object(time, "monotonic", side_effect=[0.0, 1.0, 101.0]):
            report, allowed = self.diagnose()
        self.assertFalse(allowed)
        self.assertFalse(report["diagnostic_complete"])

    def test_unavailable_apt_metadata_is_not_a_successful_complete_diagnostic(self) -> None:
        unavailable = {**safe_metadata(), "apt_proxy_status": "unavailable"}
        report, allowed = self.diagnose(metadata_output=json.dumps(unavailable))
        self.assertFalse(allowed)
        self.assertFalse(report["diagnostic_complete"])

    def test_failure_keeps_collecting_all_contexts_and_uses_privileged_metadata(self) -> None:
        with (
            patch.object(network, "metadata", side_effect=safe_metadata),
            patch.object(
                network,
                "run_command",
                return_value=network.CommandResult(
                    "success",
                    json.dumps(safe_metadata()),
                    0,
                ),
            ) as command,
            patch.object(network, "probe", return_value={"status": "dns_failure"}) as probe,
        ):
            report, allowed = network.diagnose()
        self.assertFalse(allowed)
        self.assertTrue(report["diagnostic_complete"])
        self.assertEqual(probe.call_count, 12)
        self.assertEqual(
            {call.args[2] for call in probe.call_args_list},
            {"user", "sudo"},
        )
        argv = command.call_args.args[0]
        self.assertEqual(argv[:3], ["sudo", "-n", "--"])
        self.assertEqual(argv[-3:], [sys.executable, str(network.SCRIPT), "--metadata-only"])

    def test_cli_exit_and_logs_preserve_gate_without_exception_or_secret_dump(self) -> None:
        for allowed in (True, False):
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                patch.object(
                    network, "diagnose", return_value=({"continue_installation": allowed}, allowed)
                ),
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                self.assertEqual(network.main([]), 0 if allowed else 1)
            self.assertEqual(json.loads(stdout.getvalue())["continue_installation"], allowed)
        stderr = io.StringIO()
        with (
            patch.object(network, "diagnose", side_effect=OSError("proxy-password")),
            patch("sys.stderr", stderr),
        ):
            self.assertEqual(network.main([]), 1)
        self.assertNotIn("proxy-password", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
