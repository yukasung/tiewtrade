"""Resolve only owner-approved immutable artifact occurrences, after complete scans."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from tools.security.model import (
    Finding,
    PolicyError,
    array,
    digest,
    natural,
    obj,
    read_json,
    sha,
    string,
)
from tools.security.secrets import GitReads


def approved_evidence(
    root: Path, findings: list[Finding], registry: Path
) -> tuple[frozenset[tuple[str, str]], list[dict[str, object]]]:
    data = obj(read_json(registry, 256 * 1024))
    if set(data) != {"schema", "entries"} or type(data["schema"]) is not int or data["schema"] != 1:
        raise PolicyError("INVALID_EVIDENCE_REGISTRY")
    groups: dict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(set)
    for finding in findings:
        if finding.kind == "secret" and len(finding.locator) == 5:
            rule, commit, path, _, _ = finding.locator
            groups[rule, commit, path].add((finding.kind, finding.identity))
    reads = GitReads(root)
    accepted: set[tuple[str, str]] = set()
    bindings: set[tuple[str, str, str]] = set()
    summaries: list[dict[str, object]] = []
    for value in array(data["entries"]):
        row = obj(value)
        if set(row) != {
            "commit",
            "path",
            "git_blob",
            "rule",
            "reported_matches",
            "occurrence_digest",
            "resolution",
            "reason",
            "approval",
            "evidence",
        }:
            raise PolicyError("INVALID_EVIDENCE_FIELDS")
        commit, path, blob = sha(row["commit"]), string(row["path"]), sha(row["git_blob"])
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != path:
            raise PolicyError("INVALID_EVIDENCE_PATH")
        rule, count = string(row["rule"]), natural(row["reported_matches"])
        if count == 0 or row["resolution"] != "false_positive":
            raise PolicyError("INVALID_EVIDENCE_RESOLUTION")
        for field in ("reason", "approval", "evidence"):
            if string(row[field]).strip().upper() in {"", "PENDING", "PROPOSED"}:
                raise PolicyError("UNAPPROVED_EVIDENCE")
        binding = (rule, commit, path)
        if binding in bindings:
            raise PolicyError("DUPLICATE_EVIDENCE_BINDING")
        bindings.add(binding)
        matches = groups.get(binding, set())
        if (
            len(matches) != count
            or digest(sorted(identity for _, identity in matches))
            != string(row["occurrence_digest"])
            or sha(reads.read("rev-parse", f"{commit}:{path}")) != blob
        ):
            raise PolicyError("EVIDENCE_BINDING_MISMATCH")
        accepted.update(matches)
        summaries.append(
            {
                "commit": commit,
                "path": path,
                "git_blob": blob,
                "rule": rule,
                "resolved_matches": count,
            }
        )
    return frozenset(accepted), summaries
