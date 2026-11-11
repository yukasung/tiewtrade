"""Select documentation-only or the complete existing CI without app dependencies."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Operational commands and executable contract inputs take precedence over the whitelist.
# Keep new consumers mapped here; see plan.md for the existing tests that read these files.
RUNTIME_DOC_INPUTS: frozenset[str] = frozenset(
    {
        "README.md",
        "specs/roadmap.md",
        "specs/features/2026-09-28-venue-layer/validation.md",
        "specs/features/2026-10-01-binance-th-adapter/plan.md",
    }
)


@dataclass(frozen=True)
class Selection:
    run_checks: bool
    reason: str
    base: str | None = None

    @property
    def mode(self) -> str:
        return "full" if self.run_checks else "docs-only"


def is_documentation(path: str) -> bool:
    """Only explicitly known documentation locations may skip application checks."""
    if path in RUNTIME_DOC_INPUTS or any(part in {"", ".", ".."} for part in path.split("/")):
        return False
    return path in {"AGENTS.md", "README.md"} or (
        path.startswith("specs/") and path.endswith(".md")
    )


def select_paths(paths: list[str]) -> Selection:
    if not paths:
        return Selection(True, "Empty diff: require all checks.")
    if all(is_documentation(path) for path in paths):
        return Selection(False, "Every changed path is ordinary documentation.")
    return Selection(True, "Runtime, tooling, test or unknown input: require all checks.")


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout


def validate_sha(value: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value) is None
    ):
        raise ValueError("Invalid base commit.")
    return value


def _resolve_comparison_base(repo: Path, event: str, base_sha: str) -> str:
    """Resolve Git history for affected mode without deciding which checks may skip."""
    if event == "workflow_dispatch":
        git(repo, "fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
        base_sha = validate_sha(git(repo, "rev-parse", "refs/remotes/origin/main").decode().strip())
    else:
        base_sha = validate_sha(base_sha)
        try:
            git(repo, "cat-file", "-e", f"{base_sha}^{{commit}}")
        except subprocess.CalledProcessError:
            git(repo, "fetch", "--no-tags", "origin", base_sha)
    return validate_sha(git(repo, "merge-base", base_sha, "HEAD").decode().strip())


def select_for_event(repo: Path, event: str, mode: str = "full", base_sha: str = "") -> Selection:
    if event == "push":
        return Selection(True, "Main push: require all post-merge checks.")
    if event == "workflow_dispatch":
        if mode not in {"full", "affected"}:
            raise ValueError("Manual mode must be full or affected.")
        if mode == "full":
            return Selection(True, "Manual full: require all checks.")
    elif event != "pull_request":
        return Selection(True, "Unknown event: require all checks.")

    try:
        base = _resolve_comparison_base(repo, event, base_sha)
        raw_paths = git(
            repo,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--name-only",
            "-z",
            base,
            "HEAD",
            "--",
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return Selection(True, "Base, fetch or diff unavailable: require all checks.")

    selection = select_paths([os.fsdecode(path) for path in raw_paths.split(b"\0") if path])
    return Selection(selection.run_checks, selection.reason, base)


def main() -> None:
    repo = Path.cwd()
    event = os.environ["GITHUB_EVENT_NAME"]
    base_sha = ""
    if event == "pull_request":
        payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        base_sha = payload["pull_request"]["base"]["sha"]
    selection = select_for_event(repo, event, os.environ.get("CI_MODE", "") or "full", base_sha)
    if not selection.run_checks:
        # The complete candidate diff, including deleted documentation, is checked.
        if selection.base is None:
            raise ValueError("Documentation selection has no diff base.")
        git(repo, "diff", "--no-ext-diff", "--no-textconv", "--check", selection.base, "HEAD", "--")
    outputs = f"run_checks={str(selection.run_checks).lower()}\nselection={selection.mode}\n"
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(outputs)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as summary:
        summary.write(f"### CI selection: {selection.mode}\n\n{selection.reason}\n")
    sys.stdout.write(f"CI selection: {selection.mode}. {selection.reason}\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        # Do not publish success outputs or echo payloads/git output on an incomplete selection.
        sys.stderr.write("CI selection failed; required checks must not succeed.\n")
        sys.exit(1)
