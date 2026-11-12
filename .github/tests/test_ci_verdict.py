"""A complete negative matrix prevents skipped/cancelled work from passing CI."""

from __future__ import annotations

import itertools
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ci_verdict import verdict  # noqa: E402


class VerdictTests(unittest.TestCase):
    def test_only_two_complete_result_combinations_can_pass(self) -> None:
        results = ["success", "failure", "cancelled", "skipped", "", "unknown", "timed_out"]
        selections = ["true", "false", "", "True", "1", "unknown"]
        for selector, selected, worker in itertools.product(results, selections, results):
            allowed = selector == "success" and (
                (selected == "true" and worker == "success")
                or (selected == "false" and worker == "skipped")
            )
            with self.subTest(selector=selector, selected=selected, worker=worker):
                if allowed:
                    self.assertTrue(verdict(selector, selected, worker))
                else:
                    with self.assertRaises(ValueError):
                        verdict(selector, selected, worker)

    def test_cli_propagates_failure_and_reports_docs_not_applicable(self) -> None:
        for selected, worker, code in [
            ("true", "failure", 1),
            ("false", "skipped", 0),
            ("true", "success", 0),
        ]:
            with self.subTest(selected=selected, worker=worker):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "ci_verdict.py")],
                    env={
                        **os.environ,
                        "CI_SELECTOR_RESULT": "success",
                        "CI_SELECTED": selected,
                        "CI_WORKER_RESULT": worker,
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, code)
                if selected == "false":
                    self.assertIn("Not applicable", result.stdout)


if __name__ == "__main__":
    unittest.main()
