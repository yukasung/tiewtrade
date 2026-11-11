"""Fail closed when selection or the required worker has no successful result."""

from __future__ import annotations

import os
import sys


def verdict(selector_result: str, selected: str, worker_result: str) -> str:
    if selector_result != "success":
        raise ValueError("CI selector did not succeed.")
    if selected not in {"true", "false"}:
        raise ValueError("CI selection output is missing or invalid.")
    if selected == "true":
        if worker_result != "success":
            raise ValueError("A required CI worker did not succeed.")
        return "Required CI worker passed."
    if worker_result != "skipped":
        raise ValueError("Worker result does not match the documentation-only selection.")
    return "Not applicable: documentation-only candidate; selector and documentation checks passed."


def main() -> None:
    try:
        message = verdict(
            os.environ.get("CI_SELECTOR_RESULT", ""),
            os.environ.get("CI_SELECTED", ""),
            os.environ.get("CI_WORKER_RESULT", ""),
        )
    except ValueError as error:
        sys.stderr.write(f"{error}\n")
        sys.exit(1)
    sys.stdout.write(f"{message}\n")


if __name__ == "__main__":
    main()
