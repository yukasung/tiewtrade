"""Verify network diagnostic behavior without network access, sudo or APT changes."""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        with patch.object(network, "supervised_command", return_value=result):
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
        result = network.CommandResult(
            "success", json.dumps({"status": "success", "output": "200", "code": 0}), 0
        )
        with patch.object(network, "run_command", return_value=result) as command:
            network.probe("https", network.HTTPS_URLS[0], "sudo", float("inf"))
        argv = command.call_args.args[0]
        self.assertEqual(
            argv,
            [
                "sudo",
                "-n",
                "--",
                sys.executable,
                str(network.SCRIPT),
                "--supervise",
                "https",
                network.HTTPS_URLS[0],
            ],
        )
        curl, seconds = network.fixed_command("https", network.HTTPS_URLS[0])
        self.assertEqual(curl[:2], ["curl", "--disable"])
        self.assertEqual(seconds, 7)
        self.assertEqual(curl[curl.index("--max-time") + 1], "6")
        self.assertEqual(curl[curl.index("--connect-timeout") + 1], "3")
        self.assertIn("--proto-redir", curl)
        self.assertEqual(curl[curl.index("--retry") + 1], "0")
        self.assertNotIn("--insecure", curl)
        self.assertNotIn("--verbose", curl)
        self.assertEqual(command.call_args.args[1], 8.0)
        self.assertEqual(
            network.bounded_command("dns", network.HOSTS[0], "user")[:3],
            [sys.executable, str(network.SCRIPT), "--supervise"],
        )

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


class BoundedRetryTests(unittest.TestCase):
    def test_only_sudo_canonical_archive_timeout_is_retried_and_recorded(self) -> None:
        cases: list[list[dict[str, object]]] = [
            [{"status": "timeout"}, {"status": "success", "http_status": 200}],
            [
                {"status": "timeout"},
                {"status": "timeout"},
                {"status": "success", "http_status": 200},
            ],
            [{"status": "timeout"}] * 3,
            [{"status": "timeout"}, {"status": "certificate_failure"}],
        ]
        for outcomes in cases:
            with (
                self.subTest(outcomes=outcomes),
                patch.object(network, "probe", side_effect=outcomes) as probe,
                patch.object(time, "sleep") as sleep,
            ):
                result = network.https_probe(network.HTTPS_URLS[0], "sudo", float("inf"))
                self.assertEqual(result["attempts"], outcomes)
                self.assertEqual(result["attempt_count"], len(outcomes))
                self.assertEqual(result["status"], outcomes[-1]["status"])
                self.assertEqual(probe.call_count, len(outcomes))
                self.assertEqual(sleep.call_count, len(outcomes) - 1)
                for call in sleep.call_args_list:
                    self.assertEqual(call.args, (0.2,))
                for call in probe.call_args_list:
                    self.assertEqual(
                        call.args, ("https", network.HTTPS_URLS[0], "sudo", float("inf"))
                    )

    def test_other_contexts_endpoints_and_non_timeout_failures_never_retry(self) -> None:
        for target, context, status in (
            (network.HTTPS_URLS[0], "user", "timeout"),
            (network.HTTPS_URLS[1], "sudo", "timeout"),
            *(
                (network.HTTPS_URLS[0], "sudo", status)
                for status in (
                    "success",
                    "certificate_failure",
                    "tls_failure",
                    "http_failure",
                    "invalid_response",
                    "connection_failure",
                    "dns_failure",
                    "proxy_dns_failure",
                    "redirect_failure",
                    "tool_unavailable",
                    "operational_error",
                    "budget_exhausted",
                )
            ),
        ):
            with (
                self.subTest(target=target, context=context, status=status),
                patch.object(network, "probe", return_value={"status": status}) as probe,
                patch.object(time, "sleep") as sleep,
            ):
                result = network.https_probe(target, context, float("inf"))
                self.assertEqual(result["status"], status)
                probe.assert_called_once()
                sleep.assert_not_called()

    def test_insufficient_budget_preserves_failure_without_sleep_or_spawn(self) -> None:
        with (
            patch.object(network, "probe", return_value={"status": "timeout"}) as probe,
            patch.object(time, "monotonic", return_value=92.0),
            patch.object(time, "sleep") as sleep,
        ):
            result = network.https_probe(network.HTTPS_URLS[0], "sudo", 100.0)
        self.assertEqual(
            result,
            {"status": "budget_exhausted", "attempts": [{"status": "timeout"}], "attempt_count": 1},
        )
        probe.assert_called_once()
        sleep.assert_not_called()

    def test_budget_is_rechecked_after_sleep_before_starting_privileged_child(self) -> None:
        with (
            patch.object(time, "monotonic", side_effect=[0.0, 0.0, 101.0]),
            patch.object(time, "sleep"),
            patch.object(
                network,
                "supervised_command",
                return_value=network.CommandResult("command_failed", "private-error", 28),
            ) as command,
        ):
            result = network.https_probe(network.HTTPS_URLS[0], "sudo", 100.0)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(
            result["attempts"], [{"status": "timeout"}, {"status": "budget_exhausted"}]
        )
        command.assert_called_once()
        self.assertNotIn("private-error", json.dumps(result))

    def test_short_budget_never_truncates_privileged_inner_timeout(self) -> None:
        with (
            patch.object(time, "monotonic", return_value=93.0),
            patch.object(network, "run_command") as command,
        ):
            self.assertEqual(
                network.probe("https", network.HTTPS_URLS[0], "sudo", 100.0),
                {"status": "budget_exhausted"},
            )
            metadata, complete = network._context_metadata("sudo", 100.0)
        self.assertFalse(complete)
        self.assertEqual(metadata, {"status": "unavailable_or_invalid"})
        command.assert_not_called()

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups required")
    def test_inner_timeout_kills_descendant_before_outer_timeout(self) -> None:
        # Exercise the same supervisor used inside sudo. The child
        # must never survive to write its marker after the bounded command returns.
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "orphan-marker"
            started = Path(directory) / "descendant-started"
            child = (
                "import pathlib,time,sys,signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "pathlib.Path(sys.argv[2]).touch(); time.sleep(1.5); "
                "pathlib.Path(sys.argv[1]).touch()"
            )
            parent = (
                "import subprocess,sys,time; "
                "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]]); "
                "time.sleep(10)"
            )
            result = network.run_group(
                [sys.executable, "-c", parent, child, str(marker), str(started)], 1.0
            )
            self.assertEqual(result, network.CommandResult("timeout"))
            self.assertTrue(started.exists())
            time.sleep(0.7)
            self.assertFalse(marker.exists())


class SupervisorTests(unittest.TestCase):
    def test_normal_nonzero_missing_tool_and_private_output(self) -> None:
        for code in (0, 2):
            result = network.run_group(
                [sys.executable, "-c", f"import sys; print('private'); sys.exit({code})"], 1.0
            )
            self.assertEqual(
                result,
                network.CommandResult(
                    "success" if code == 0 else "command_failed", "private\n", code
                ),
            )
        self.assertEqual(
            network.run_group(["/nonexistent-tiewtrade-diagnostic-tool"], 1.0),
            network.CommandResult("tool_unavailable"),
        )

    def test_actual_internal_cli_starts_fixed_command_in_its_own_session(self) -> None:
        # Offline executable fixture exercises the real CLI/envelope/parse boundary.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "child-state.json"
            getent = root / "getent"
            getent.write_text(
                f"#!{sys.executable}\n"
                "import json,os,pathlib\n"
                "pathlib.Path(os.environ['TIEWTRADE_DIAGNOSTIC_TEST_RECORD']).write_text("
                "json.dumps({'pid':os.getpid(),'sid':os.getsid(0),'uid':os.geteuid()}))\n"
                "print('192.0.2.1 STREAM archive.ubuntu.com')\n"
            )
            getent.chmod(0o700)
            with patch.dict(
                os.environ,
                {
                    "PATH": directory + os.pathsep + os.environ.get("PATH", ""),
                    "TIEWTRADE_DIAGNOSTIC_TEST_RECORD": str(record),
                },
            ):
                result = network.probe("dns", network.HOSTS[1], "user", float("inf"))
            self.assertEqual(result, {"status": "success"})
            state = json.loads(record.read_text())
            self.assertEqual(state["pid"], state["sid"])
            self.assertEqual(state["uid"], os.geteuid())

    def test_kills_owned_group_then_reaps_and_closes_pipe(self) -> None:
        process = MagicMock()
        process.pid = 12345
        process.communicate.side_effect = subprocess.TimeoutExpired("private", 1)
        with (
            patch.object(subprocess, "Popen", return_value=process) as popen,
            patch.object(os, "killpg") as kill,
        ):
            self.assertEqual(network.run_group(["fixed"], 1.0), network.CommandResult("timeout"))
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        kill.assert_called_once_with(12345, signal.SIGKILL)
        process.wait.assert_called_once_with(timeout=0.5)
        process.stdout.close.assert_called_once()

    def test_cleanup_or_launch_failure_is_operational_not_retryable_timeout(self) -> None:
        with patch.object(subprocess, "Popen", side_effect=PermissionError("private")):
            self.assertEqual(
                network.run_group(["fixed"], 1.0), network.CommandResult("operational_error")
            )
        for failure in ("kill", "wait"):
            process = MagicMock()
            process.communicate.side_effect = subprocess.TimeoutExpired("private", 1)
            process.pid = 12345
            if failure == "wait":
                process.wait.side_effect = subprocess.TimeoutExpired("private", 0.5)
            with (
                patch.object(subprocess, "Popen", return_value=process),
                patch.object(
                    os,
                    "killpg",
                    side_effect=PermissionError("private") if failure == "kill" else None,
                ),
            ):
                self.assertEqual(
                    network.run_group(["fixed"], 1.0), network.CommandResult("operational_error")
                )
            process.wait.assert_called_once_with(timeout=0.5)

    def test_internal_protocol_rejects_supervisor_privilege_and_schema_failures(self) -> None:
        for outer in (
            network.CommandResult("timeout"),
            network.CommandResult("tool_unavailable"),
            network.CommandResult("command_failed", "private", 1),
            *(
                network.CommandResult("success", value, 0)
                for value in (
                    "private",
                    "null",
                    "[]",
                    '{"status":"success"}',
                    '{"status":"success","output":"200","code":1}',
                    '{"status":"success","output":"200","code":true}',
                    '{"status":"timeout","output":"private","code":null}',
                    '{"status":"unknown","output":"private","code":1}',
                )
            ),
        ):
            with (
                self.subTest(outer=outer),
                patch.object(network, "run_command", return_value=outer),
            ):
                self.assertEqual(
                    network.supervised_command("https", network.HTTPS_URLS[0], "sudo"),
                    network.CommandResult("operational_error"),
                )
        for inner in (
            network.CommandResult("timeout"),
            network.CommandResult("tool_unavailable"),
            network.CommandResult("operational_error"),
            network.CommandResult("success", "200", 0),
            network.CommandResult("command_failed", "private", 28),
        ):
            envelope = json.dumps(
                {"status": inner.status, "output": inner.output, "code": inner.code}
            )
            with patch.object(
                network, "run_command", return_value=network.CommandResult("success", envelope, 0)
            ):
                self.assertEqual(
                    network.supervised_command("https", network.HTTPS_URLS[0], "sudo"), inner
                )

    def test_internal_cli_allows_only_existing_operations_targets_and_fixed_limits(self) -> None:
        for operation, target in (
            ("dns", "private.invalid"),
            ("https", "http://archive.ubuntu.com"),
            ("metadata", "private"),
            ("arbitrary", "-"),
        ):
            stdout, stderr = io.StringIO(), io.StringIO()
            with (
                patch.object(network, "run_group") as group,
                patch("sys.stdout", stdout),
                patch("sys.stderr", stderr),
            ):
                self.assertEqual(network.main(["--supervise", operation, target]), 1)
            group.assert_not_called()
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn("private", stderr.getvalue())
        for operation, target, seconds in (
            ("dns", network.HOSTS[0], 5),
            ("https", network.HTTPS_URLS[0], 7),
            ("metadata", "-", 7),
        ):
            stdout = io.StringIO()
            with (
                patch.object(
                    network, "run_group", return_value=network.CommandResult("timeout")
                ) as group,
                patch("sys.stdout", stdout),
            ):
                self.assertEqual(network.main(["--supervise", operation, target]), 0)
            self.assertEqual(
                group.call_args.args, (network.fixed_command(operation, target)[0], seconds)
            )
            self.assertEqual(
                json.loads(stdout.getvalue()), {"status": "timeout", "output": "", "code": None}
            )


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
                "supervised_command",
                return_value=network.CommandResult(
                    "success",
                    json.dumps(safe_metadata()) if metadata_output is None else metadata_output,
                    0,
                ),
            ),
            patch.object(network, "probe", side_effect=fake_probe),
        ):
            return network.diagnose()

    def test_gate_requires_current_sudo_success_and_retains_timeout_attempt(self) -> None:
        statuses = iter(("timeout", "success"))

        def fake_probe(kind: str, target: str, context: str, deadline: float) -> dict[str, object]:
            if kind == "https" and target == network.HTTPS_URLS[0] and context == "sudo":
                return {"status": next(statuses)}
            return {"status": "success"}

        with (
            patch.object(network, "_context_metadata", return_value=(safe_metadata(), True)),
            patch.object(network, "probe", side_effect=fake_probe),
            patch.object(time, "sleep"),
        ):
            report, allowed = network.diagnose()
        self.assertTrue(allowed)
        contexts = report["contexts"]
        assert isinstance(contexts, dict)
        archive = contexts["sudo"]["https"][network.HTTPS_URLS[0]]
        self.assertEqual(
            archive,
            {
                "status": "success",
                "attempts": [{"status": "timeout"}, {"status": "success"}],
                "attempt_count": 2,
            },
        )

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
                "supervised_command",
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
        self.assertEqual(command.call_args.args, ("metadata", "-", "sudo"))
        argv = network.bounded_command("metadata", "-", "sudo")
        self.assertEqual(argv[:3], ["sudo", "-n", "--"])
        self.assertEqual(
            argv[3:], [sys.executable, str(network.SCRIPT), "--supervise", "metadata", "-"]
        )
        self.assertEqual(
            network.fixed_command("metadata", "-"),
            ([sys.executable, str(network.SCRIPT), "--metadata-only"], 7),
        )

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
