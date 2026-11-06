"""Gitleaks occurrence matching; public records never contain matched text."""

from __future__ import annotations

import re
from pathlib import Path

from tools.security.model import Finding, PolicyError, array, digest, natural, obj, sha, string
from tools.security.system import git


def occurrence(root: Path, row: dict[str, object], tree: bool) -> tuple[str, tuple[str, ...]]:
    path = string(row.get("File"))
    candidate_path = Path(path)
    if candidate_path.is_absolute():
        raise PolicyError("ABSOLUTE_SECRET_PATH")
    if ".." in candidate_path.parts:
        raise PolicyError("INVALID_SECRET_PATH")
    start, end = natural(row.get("StartLine")), natural(row.get("EndLine"))
    if start == 0 or end < start:
        raise PolicyError("INVALID_SECRET_LOCATION")
    commit = row.get("Commit")
    if tree:
        # Treat a rename as a new path occurrence, including a move away and back.
        # Bound blame at the most recent creation of this path so it cannot carry
        # an approval across a rename into another configuration or fixture.
        boundary = sha(
            git(
                root,
                "log",
                "-1",
                "--format=%H",
                "--no-renames",
                "--diff-filter=A",
                "HEAD",
                "--",
                path,
            )
        )
        blame = git(
            root, "blame", "--line-porcelain", f"-L{start},{end}", f"{boundary}..HEAD", "--", path
        )
        headers = [
            line.split()
            for line in blame.splitlines()
            if re.fullmatch(r"[0-9a-f]{40} \d+ \d+( \d+)?", line)
        ]
        if len(headers) != end - start + 1 or len({line[0] for line in headers}) != 1:
            raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
        commit = headers[0][0]
        original_lines = [int(line[1]) for line in headers]
        if original_lines != list(range(original_lines[0], original_lines[0] + len(headers))):
            raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
        # Renames retain a filename in porcelain output. Require one original file.
        filenames = {
            line.removeprefix("filename ")
            for line in blame.splitlines()
            if line.startswith("filename ")
        }
        if len(filenames) != 1:
            raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
        path = filenames.pop()
        start, end = original_lines[0], original_lines[-1]
    commit = sha(commit)
    blob = sha(git(root, "rev-parse", f"{commit}:{path}"))
    identity = digest(
        [
            "gitleaks",
            string(row.get("RuleID")),
            commit,
            path,
            start,
            end,
            natural(row.get("StartColumn")),
            natural(row.get("EndColumn")),
            blob,
        ]
    )
    return identity, (string(row.get("RuleID")), commit, path, str(start), str(end))


def evaluate(report: object, root: Path, *, tree: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    for value in array(report):
        row = obj(value)
        identity, locator = occurrence(root, row, tree)
        findings.append(Finding("secret", identity, "high", locator))
    return findings
