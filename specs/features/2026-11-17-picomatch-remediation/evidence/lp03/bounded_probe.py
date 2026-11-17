"""Bounded LP-02 prototype runner; never installs application dependencies."""

import argparse
import json
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import Any, NoReturn

CHILD_TIMEOUT_SECONDS = 2.0
CLEANUP_RESERVE_SECONDS = 2.0
CHILD_JOIN_SECONDS = 1.0
STAGE_BUDGET_SECONDS = 60.0


def capture_probe(
    command: list[str], deadline: float, timeout: float = CHILD_TIMEOUT_SECONDS
) -> dict[str, Any]:
    allowance = min(timeout, deadline - time.monotonic() - CLEANUP_RESERVE_SECONDS)
    if allowance <= 0:
        raise TimeoutError("stage deadline reached; cleanup reserved")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"PATH": os.environ["PATH"]},
    )
    primary: BaseException | None = None
    try:
        try:
            stdout, stderr = process.communicate(timeout=allowance)
            outcome = "RETURNED" if process.returncode == 0 else "ERROR"
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=CHILD_JOIN_SECONDS)
            outcome = "TIMEOUT"
        return {
            "outcome": outcome,
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "pid": process.pid,
            "joined": True,
        }
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=CHILD_JOIN_SECONDS)
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note(f"child cleanup failed: {type(error).__name__}")


class ProbeCancelledError(Exception):
    """Cancellation that subprocess will not mistake for a retryable OS interruption."""


def handle_termination(signum: int, frame: FrameType | None) -> NoReturn:
    raise ProbeCancelledError("owned probe runner cancelled")


def run_matrix(
    matrix: list[dict[str, Any]],
    command_for: Callable[[dict[str, Any]], list[str]],
    output: Path,
    budget: float = STAGE_BUDGET_SECONDS,
) -> int:
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    report: dict[str, Any] = {"status": "INCOMPLETE", "budget_seconds": budget, "cases": rows}
    primary: BaseException | None = None
    try:
        for case in matrix:
            result = capture_probe(command_for(case), started + budget)
            value = json.loads(result.pop("stdout")) if result["outcome"] == "RETURNED" else {}
            result.update(id=case["id"], category=case["category"], **value)
            result["passed"] = (
                result["outcome"] == "RETURNED"
                and value.get("matched") == case["expected_patched"]
                and (
                    not case["compare_original"]
                    or value.get("baseline") == case["expected_original"]
                )
            )
            rows.append(result)
        if time.monotonic() >= started + budget:
            raise TimeoutError("stage deadline exceeded")
        report["status"] = "PASSED" if all(row["passed"] for row in rows) else "FAILED"
        return 0 if report["status"] == "PASSED" else 1
    except BaseException as error:
        primary = error
        report["error_type"] = type(error).__name__
        raise
    finally:
        report["seconds"] = time.monotonic() - started
        try:
            temporary = output.with_suffix(".tmp")
            temporary.write_text(json.dumps(report, indent=2) + "\n")
            temporary.replace(output)
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note(f"evidence write failed: {type(error).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scratch", type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    matrix = json.loads((here / "probe-matrix.json").read_text())
    previous = signal.signal(signal.SIGTERM, handle_termination)
    try:

        def command(case: dict[str, Any]) -> list[str]:
            return [
                "node",
                "--max-old-space-size=256",
                str(here / "probe-child.js"),
                str(args.scratch / "patched/package"),
                str(args.scratch / "original/package"),
                json.dumps(case),
            ]

        return run_matrix(matrix, command, here / "probe-results.json", budget=30)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
