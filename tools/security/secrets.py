"""Gitleaks occurrence matching; public records never contain matched text."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from tools.security.model import (
    Finding,
    PolicyError,
    array,
    digest,
    natural,
    obj,
    sha,
    string,
)
from tools.security.system import git


def location(row: dict[str, object]) -> tuple[str, int, int]:
    path = string(row.get("File"))
    candidate_path = Path(path)
    if candidate_path.is_absolute():
        raise PolicyError("ABSOLUTE_SECRET_PATH")
    if ".." in candidate_path.parts:
        raise PolicyError("INVALID_SECRET_PATH")
    start, end = natural(row.get("StartLine")), natural(row.get("EndLine"))
    if start == 0 or end < start:
        raise PolicyError("INVALID_SECRET_LOCATION")
    return path, start, end


class GitReads:
    """Immutable, scan-local metadata only; never caches secret text."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.cache: dict[tuple[str, ...], str] = {}
        self.lines: dict[tuple[str, int], tuple[str, int, str]] = {}

    def read(self, *args: str) -> str:
        if args not in self.cache:
            self.cache[args] = git(self.root, *args)
        return self.cache[args]

    def blame(self, path: str, start: int, end: int) -> None:
        boundary = sha(
            self.read(
                "log", "-1", "--format=%H", "--no-renames", "--diff-filter=A", "HEAD", "--", path
            )
        )
        raw = git(
            self.root,
            "blame",
            "--line-porcelain",
            f"-L{start},{end}",
            f"{boundary}..HEAD",
            "--",
            path,
        )
        header: list[str] | None = None
        filename: str | None = None
        mapped: dict[tuple[str, int], tuple[str, int, str]] = {}
        for line in raw.splitlines():
            if re.fullmatch(r"[0-9a-f]{40} \d+ \d+( \d+)?", line):
                header, filename = line.split(), None
            elif line.startswith("filename "):
                filename = line.removeprefix("filename ")
            elif line.startswith("\t"):
                if header is None or filename is None:
                    raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
                key = (path, int(header[2]))
                if key in mapped:
                    raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
                mapped[key] = (header[0], int(header[1]), filename)
                header = None
        if {key[1] for key in mapped} != set(range(start, end + 1)):
            raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
        self.lines.update(mapped)

    def prepare_tree(self, rows: list[object]) -> None:
        ranges: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for value in rows:
            path, start, end = location(obj(value))
            ranges[path].append((start, end))
        for path, spans in ranges.items():
            spans.sort()
            first, last = spans[0]
            for start, end in spans[1:]:
                if max(last, end) - first < 512:
                    last = max(last, end)
                else:
                    self.blame(path, first, last)
                    first, last = start, end
            self.blame(path, first, last)


def occurrence(
    root: Path, row: dict[str, object], tree: bool, *, reads: GitReads | None = None
) -> tuple[str, tuple[str, ...]]:
    reads = reads or GitReads(root)
    path, start, end = location(row)
    commit = row.get("Commit")
    if tree:
        # Treat a rename as a new path occurrence, including a move away and back.
        # Bound blame at the most recent creation of this path so it cannot carry
        # an approval across a rename into another configuration or fixture.
        if any((path, line) not in reads.lines for line in range(start, end + 1)):
            reads.blame(path, start, end)
        mapped = [reads.lines[path, line] for line in range(start, end + 1)]
        if len({line[0] for line in mapped}) != 1:
            raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
        commit = mapped[0][0]
        original_lines = [line[1] for line in mapped]
        if original_lines != list(range(original_lines[0], original_lines[0] + len(mapped))):
            raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
        # Renames retain a filename in porcelain output. Require one original file.
        filenames = {line[2] for line in mapped}
        if len(filenames) != 1:
            raise PolicyError("UNMAPPED_TREE_OCCURRENCE")
        path = filenames.pop()
        start, end = original_lines[0], original_lines[-1]
    commit = sha(commit)
    blob = sha(reads.read("rev-parse", f"{commit}:{path}"))
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


def evaluate(
    report: object, root: Path, *, tree: bool = False, reads: GitReads | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    rows = array(report)
    reads = reads or GitReads(root)
    if tree:
        reads.prepare_tree(rows)
    for value in rows:
        row = obj(value)
        identity, locator = occurrence(root, row, tree, reads=reads)
        findings.append(Finding("secret", identity, "high", locator))
    return findings
