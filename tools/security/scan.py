"""Execute pinned scanners with explicit configs and private temporary output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tools.security import dependencies, secrets
from tools.security.model import Finding, PolicyError, array, obj, read_json, string
from tools.security.system import git


@contextmanager
def observed_stage(name: str) -> Iterator[dict[str, int]]:
    """Counts and elapsed time only, including on failure; never scanner/error text."""
    started = time.monotonic()
    counts: dict[str, int] = {}
    returned = False
    try:
        yield counts
        returned = True
    finally:
        sys.stderr.write(
            json.dumps(
                {
                    "security_stage": name,
                    "seconds": time.monotonic() - started,
                    "outcome": "RETURNED" if returned else "FAILED",
                    "counts": counts,
                },
                sort_keys=True,
            )
            + "\n"
        )


def execute(args: list[str], cwd: Path, output: Path, allowed: tuple[int, ...]) -> int:
    with output.open("wb") as stream, output.with_suffix(".stderr").open("wb") as errors:
        environment = {
            key: value
            for key, value in os.environ.items()
            if not any(marker in key.upper() for marker in ("TOKEN", "SECRET", "PASSWORD"))
        }
        completed = subprocess.run(
            args, cwd=cwd, env=environment, stdout=stream, stderr=errors, timeout=780, check=False
        )
    if completed.returncode not in allowed:
        raise PolicyError("SCANNER_EXECUTION_FAILED")
    return completed.returncode


def scan_secrets(
    root: Path, policy: Path, binary: Path, *, all_refs: bool = False
) -> tuple[list[Finding], int]:
    if git(root, "rev-parse", "--is-shallow-repository") != "false":
        raise PolicyError("SHALLOW_HISTORY")
    with tempfile.TemporaryDirectory(prefix="security-secrets-") as directory:
        temp = Path(directory)
        ignore = temp / "ignore"
        ignore.write_text("")
        common = [
            "--config",
            str(policy / ".github/security/gitleaks.toml"),
            "--redact=100",
            "--ignore-gitleaks-allow",
            "--gitleaks-ignore-path",
            str(ignore),
            "--report-format",
            "json",
            "--exit-code",
            "10",
            "--no-banner",
        ]
        history = temp / "history.json"
        options = (
            "--full-history --no-renames --all"
            if all_refs
            else "--full-history --no-renames " + git(root, "rev-parse", "HEAD")
        )
        with observed_stage("history_scan") as counts:
            status = execute(
                [
                    str(binary),
                    "git",
                    str(root),
                    "--log-opts=" + options,
                    "--report-path",
                    str(history),
                    *common,
                ],
                temp,
                temp / "history.log",
                (0, 10),
            )
            raw_history = read_json(history)
            counts["matches"] = len(array(raw_history))
            if (status == 10) != bool(array(raw_history)):
                raise PolicyError("INCONSISTENT_SECRET_EXIT")
        reads = secrets.GitReads(root)
        with observed_stage("history_mapping") as counts:
            findings = secrets.evaluate(raw_history, root, reads=reads)
            counts.update(findings=len(findings), cached_git_reads=len(reads.cache))
        tree = temp / "tree"
        tree.mkdir()
        # checkout-index includes export-ignore files that git archive would omit.
        # Verify the index first so only tracked candidate files are scanned.
        with observed_stage("tree_export"):
            git(root, "diff", "--cached", "--quiet", "HEAD")
            git(root, "checkout-index", "--all", "--prefix=" + str(tree) + "/")
        report = temp / "tree.json"
        with observed_stage("tree_scan") as counts:
            status = execute(
                [str(binary), "dir", str(tree), "--report-path", str(report), *common],
                temp,
                temp / "tree.log",
                (0, 10),
            )
            raw_tree = read_json(report)
            counts["matches"] = len(array(raw_tree))
            if (status == 10) != bool(array(raw_tree)):
                raise PolicyError("INCONSISTENT_SECRET_EXIT")
        for value in array(raw_tree):
            row = obj(value)
            reported = Path(string(row.get("File")))
            if reported.is_absolute():
                try:
                    row["File"] = reported.resolve().relative_to(tree.resolve()).as_posix()
                except ValueError:
                    raise PolicyError("INVALID_SECRET_PATH") from None
        with observed_stage("tree_mapping") as counts:
            mapped = secrets.evaluate(raw_tree, root, tree=True, reads=reads)
            findings += mapped
            counts.update(
                findings=len(mapped),
                cached_git_reads=len(reads.cache),
                mapped_lines=len(reads.lines),
            )
    commits = int(git(root, "rev-list", "--count", "--all" if all_refs else "HEAD"))
    if commits <= 0:
        raise PolicyError("EMPTY_HISTORY")
    return findings, commits


def scan_dependencies(root: Path, policy: Path, binary: Path) -> tuple[list[Finding], int]:
    expected = dependencies.inventory(root)
    with tempfile.TemporaryDirectory(prefix="security-osv-") as directory:
        temp = Path(directory)
        report = temp / "osv.json"
        args = [
            str(binary),
            "scan",
            "source",
            "--format=json",
            "--all-packages",
            "--all-vulns",
            "--no-call-analysis=all",
            "--no-resolve",
            "--config=" + str(policy / ".github/security/osv-scanner.toml"),
        ]
        args += ["--lockfile=" + str(root / name) for name in expected]
        status = execute(args, temp, report, (0, 1))
        raw = read_json(report)
        if obj(raw).get("errors"):
            raise PolicyError("OSV_REPORTED_ERRORS")
        findings, coverage = dependencies.evaluate(raw, root, expected)
        if (status == 1) != bool(findings):
            raise PolicyError("INCONSISTENT_OSV_EXIT")
        return findings, coverage
