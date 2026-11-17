"""Runner failure/deadline/cancellation proof using harmless owned child processes."""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import suppress
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bounded_probe", HERE / "bounded_probe.py")
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class BoundedTests(unittest.TestCase):
    def test_success_and_failed_expectation_exit(self) -> None:
        for expected, code in [(True, 0), (False, 1)]:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "result.json"
                case = {
                    "id": 1,
                    "category": "control",
                    "expected_patched": expected,
                    "compare_original": False,
                }

                def command(_: dict[str, Any]) -> list[str]:
                    return [sys.executable, "-c", "print('{\"matched\":true}')"]

                self.assertEqual(probe.run_matrix([case], command, path), code)
                self.assertEqual(
                    json.loads(path.read_text())["status"], "PASSED" if code == 0 else "FAILED"
                )

    def test_real_child_cli_with_harmless_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "fixture.cjs"
            module.write_text("module.exports = () => () => true;")
            case = {"pattern": "safe", "subject": "safe", "options": {}, "compare_original": True}
            result = probe.capture_probe(
                ["node", str(HERE / "probe-child.js"), str(module), str(module), json.dumps(case)],
                time.monotonic() + 3,
            )
            self.assertEqual(result["outcome"], "RETURNED")
            value = json.loads(result["stdout"])
            self.assertIs(value["matched"], True)
            self.assertIs(value["baseline"], True)

    def test_timeout_joins_child(self) -> None:
        result = probe.capture_probe(
            [sys.executable, "-c", "import time;time.sleep(10)"], time.monotonic() + 3, timeout=0.05
        )
        self.assertEqual(result["outcome"], "TIMEOUT")
        with self.assertRaises(ProcessLookupError):
            os.kill(result["pid"], 0)

    def test_overall_deadline_records_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with self.assertRaises(TimeoutError):
                probe.run_matrix([{}], lambda _: [], path, budget=0)
            self.assertEqual(json.loads(path.read_text())["error_type"], "TimeoutError")

    def test_sigterm_joins_and_preserves_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Pass the child script directly as JSON-safe Python source.
            child = (
                f"import os,pathlib,time;pathlib.Path({str(root / 'pid')!r})"
                ".write_text(str(os.getpid()));time.sleep(10)"
            )
            script = (
                "import sys,signal,pathlib;"
                f"sys.path.insert(0,{str(HERE)!r});import bounded_probe as p;"
                "signal.signal(signal.SIGTERM,p.handle_termination);"
                f"p.run_matrix([{{'id':1,'category':'cancel'}}],"
                f"lambda c:[sys.executable,'-c',{child!r}],"
                f"pathlib.Path({str(root / 'report.json')!r}))"
            )
            process = subprocess.Popen([sys.executable, "-c", script], stderr=subprocess.PIPE)
            child_pid = None
            try:
                deadline = time.monotonic() + 2
                while not (root / "pid").exists():
                    if time.monotonic() > deadline:
                        self.fail("child did not start")
                    time.sleep(0.01)
                child_pid = int((root / "pid").read_text())
                process.send_signal(signal.SIGTERM)
                _, stderr = process.communicate(timeout=2)
                self.assertNotEqual(process.returncode, 0)
                self.assertIn(b"ProbeCancelledError", stderr)
                self.assertEqual(
                    json.loads((root / "report.json").read_text())["error_type"],
                    "ProbeCancelledError",
                )
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=1)
                if child_pid is not None:
                    with suppress(ProcessLookupError):
                        os.kill(child_pid, signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
