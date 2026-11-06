"""Validated, deliberately small policy objects (Security CI requirements §6)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

COMPONENTS = frozenset(
    {"secrets", "dependencies", "codeql-python", "codeql-javascript-typescript", "codeql-actions"}
)
SEVERITIES = frozenset({"none", "low", "medium", "high", "critical", "unknown"})


class PolicyError(Exception):
    """Only constant error codes may cross the public logging boundary."""


def obj(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PolicyError("INVALID_OBJECT")
    return cast(dict[str, object], value)


def array(value: object) -> list[object]:
    if not isinstance(value, list):
        raise PolicyError("INVALID_ARRAY")
    return cast(list[object], value)


def string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PolicyError("INVALID_STRING")
    return value


def natural(value: object) -> int:
    if type(value) is not int or value < 0:
        raise PolicyError("INVALID_INTEGER")
    return value


def sha(value: object) -> str:
    text = string(value)
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise PolicyError("INVALID_SHA")
    return text


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_json(path: Path, limit: int = 128 * 1024 * 1024) -> object:
    if not path.is_file() or path.stat().st_size > limit:
        raise PolicyError("MISSING_OR_OVERSIZE_REPORT")
    try:

        def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise PolicyError("DUPLICATE_JSON_KEY")
                result[key] = value
            return result

        return cast(object, json.loads(path.read_text(), object_pairs_hook=unique_pairs))
    except (ValueError, UnicodeError):
        raise PolicyError("INVALID_JSON") from None


def score_severity(value: object) -> str:
    # Severity is not a monetary quantity. No CVSS vectors are calculated here.
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return "unknown"
    try:
        score = float(value)
    except ValueError:
        return "unknown"
    if not math.isfinite(score) or not 0 <= score <= 10:
        return "unknown"
    if score >= 9:
        return "critical"
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    return "low" if score > 0 else "none"


@dataclass(frozen=True)
class Finding:
    kind: str
    identity: str
    severity: str
    locator: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {"secret", "dependency", "codeql"}:
            raise PolicyError("INVALID_FINDING_KIND")
        if not re.fullmatch(r"[0-9a-f]{64}", self.identity) or self.severity not in SEVERITIES:
            raise PolicyError("INVALID_FINDING")


@dataclass(frozen=True)
class Candidate:
    commit: str
    head: str
    base: str
    run: str
    attempt: str

    def __post_init__(self) -> None:
        for value in (self.commit, self.head, self.base):
            sha(value)
        if not self.run.isdigit() or not self.attempt.isdigit():
            raise PolicyError("INVALID_RUN_IDENTITY")

    @classmethod
    def parse(cls, value: object) -> Candidate:
        data = obj(value)
        if set(data) != {"commit", "head", "base", "run", "attempt"}:
            raise PolicyError("INVALID_CANDIDATE")
        return cls(*(string(data[key]) for key in ("commit", "head", "base", "run", "attempt")))


def approved_exceptions(path: Path) -> frozenset[tuple[str, str]]:
    data = obj(read_json(path, 256 * 1024))
    if set(data) != {"schema", "exceptions"} or data["schema"] != 1:
        raise PolicyError("INVALID_EXCEPTION_REGISTRY")
    accepted: set[tuple[str, str]] = set()
    for item in array(data["exceptions"]):
        row = obj(item)
        if set(row) != {"kind", "identity", "resolution", "reason", "approval", "evidence"}:
            raise PolicyError("INVALID_EXCEPTION_FIELDS")
        kind, identity = string(row["kind"]), string(row["identity"])
        Finding(kind, identity, "unknown")
        resolutions = (
            {"used_in_tests", "false_positive", "revoked"}
            if kind == "secret"
            else {"false_positive", "owner_exception"}
        )
        if row["resolution"] not in resolutions:
            raise PolicyError("INVALID_RESOLUTION")
        for field in ("reason", "approval", "evidence"):
            string(row[field])
        key = kind, identity
        if key in accepted:
            raise PolicyError("DUPLICATE_EXCEPTION")
        accepted.add(key)
    return frozenset(accepted)


def policy_counts(
    findings: list[Finding], exceptions: frozenset[tuple[str, str]]
) -> dict[str, int]:
    counts = dict.fromkeys((*sorted(SEVERITIES), "excepted", "blocked", "needs_triage"), 0)
    seen: dict[tuple[str, str], str] = {}
    for finding in findings:
        key = finding.kind, finding.identity
        if key in seen:
            if seen[key] != finding.severity:
                raise PolicyError("CONFLICTING_FINDING_SEVERITY")
            continue
        seen[key] = finding.severity
        if key in exceptions:
            counts["excepted"] += 1
            continue
        counts[finding.severity] += 1
        if finding.severity == "unknown":
            counts["needs_triage"] += 1
        elif finding.kind == "secret" or finding.severity in {"high", "critical"}:
            counts["blocked"] += 1
    return counts


def manifest(
    component: str, candidate: Candidate, config_digest: str, counts: dict[str, int], coverage: int
) -> dict[str, object]:
    if (
        component not in COMPONENTS
        or coverage <= 0
        or not re.fullmatch(r"[0-9a-f]{64}", config_digest)
    ):
        raise PolicyError("INCOMPLETE_SCAN")
    return {
        "schema": 1,
        "component": component,
        "candidate": asdict(candidate),
        "configuration": config_digest,
        "coverage": coverage,
        "counts": counts,
        "verdict": "pass" if counts["blocked"] == counts["needs_triage"] == 0 else "blocked",
    }


def aggregate(
    reports: Sequence[object], candidate: Candidate, config_digest: str, jobs: object
) -> None:
    statuses = obj(jobs)
    if set(statuses) != {"policy-tests", "secrets", "dependencies", "codeql"}:
        raise PolicyError("MISSING_JOB")
    if any(obj(status).get("result") != "success" for status in statuses.values()):
        raise PolicyError("JOB_NOT_SUCCESSFUL")
    seen: set[str] = set()
    expected_counts = set(policy_counts([], frozenset()))
    for report in reports:
        data = obj(report)
        if set(data) != {
            "schema",
            "component",
            "candidate",
            "configuration",
            "coverage",
            "counts",
            "verdict",
        }:
            raise PolicyError("INVALID_MANIFEST")
        component = string(data["component"])
        if component not in COMPONENTS or component in seen or data["schema"] != 1:
            raise PolicyError("DUPLICATE_OR_UNKNOWN_COMPONENT")
        seen.add(component)
        if (
            Candidate.parse(data["candidate"]) != candidate
            or data["configuration"] != config_digest
        ):
            raise PolicyError("STALE_MANIFEST")
        counts = obj(data["counts"])
        if set(counts) != expected_counts or any(
            type(n) is not int or n < 0 for n in counts.values()
        ):
            raise PolicyError("INVALID_COUNTS")
        if data["verdict"] != "pass" or any(
            counts[k] != 0 for k in ("blocked", "needs_triage", "high", "critical", "unknown")
        ):
            raise PolicyError("POLICY_NOT_PASSED")
        if component == "secrets" and any(counts[k] != 0 for k in SEVERITIES):
            raise PolicyError("UNRESOLVED_SECRET")
        if natural(data["coverage"]) == 0:
            raise PolicyError("EMPTY_COVERAGE")
    if seen != COMPONENTS:
        raise PolicyError("MISSING_COMPONENT")
