"""OSV v2.7.0 all-packages inventory and full-candidate policy adapter."""

from __future__ import annotations

import re
from pathlib import Path

import tomllib

from tools.security.model import (
    Finding,
    PolicyError,
    array,
    digest,
    obj,
    read_json,
    score_severity,
    string,
)
from tools.security.severity import valid_vector
from tools.security.trusted_sources import declared_sources

Package = tuple[str, str, str]


def package_key(ecosystem: str, name: str, version: str) -> Package:
    if ecosystem == "PyPI":
        name = re.sub(r"[-_.]+", "-", name).lower()
    return ecosystem, name, version


def inventory(root: Path) -> dict[str, set[Package]]:
    uv = "backend/uv.lock"
    npm = "frontend/package-lock.json"
    result: dict[str, set[Package]] = {uv: set(), npm: set()}
    data = tomllib.loads((root / uv).read_text())
    for entry in array(data.get("package")):
        row = obj(entry)
        source = obj(row.get("source"))
        if source == {"virtual": "."} or source == {"editable": "."}:
            if row.get("name") != "tiewtrade-backend":
                raise PolicyError("UNEXPECTED_LOCAL_PACKAGE")
            continue
        if source != {"registry": "https://pypi.org/simple"}:
            raise PolicyError("UNSUPPORTED_PACKAGE_SOURCE")
        result[uv].add(
            package_key("PyPI", string(row.get("name")), string(row.get("version")))
        )
    data = obj(read_json(root / npm))
    if data.get("lockfileVersion") != 3:
        raise PolicyError("UNSUPPORTED_NPM_LOCK")
    packages = obj(data.get("packages"))
    trusted = declared_sources(root)
    seen_trusted: set[str] = set()
    for location, value in packages.items():
        if not location:
            continue
        row = obj(value)
        if row.get("link") or not location.startswith("node_modules/"):
            raise PolicyError("UNSUPPORTED_PACKAGE_SOURCE")
        name = string(row.get("name", location.rsplit("node_modules/", 1)[-1]))
        source_row = row
        parent = location
        while source_row.get("inBundle") is True and "resolved" not in source_row:
            if "/node_modules/" not in parent:
                raise PolicyError("UNRESOLVED_BUNDLED_PACKAGE")
            parent = parent.rsplit("/node_modules/", 1)[0]
            source_row = obj(packages.get(parent))
        resolved = string(source_row.get("resolved"))
        if location in trusted:
            entry = trusted[location]
            if (
                name != entry["name"]
                or row.get("version") != entry["version"]
                or resolved != entry["resolved"]
                or row.get("integrity") != entry["integrity"]
            ):
                raise PolicyError("TRUSTED_SOURCE_LOCK_MISMATCH")
            seen_trusted.add(location)
        elif not resolved.startswith("https://registry.npmjs.org/"):
            raise PolicyError("UNSUPPORTED_PACKAGE_SOURCE")
        elif trusted and any(
            name == entry["name"] and row.get("version") == entry["version"]
            for entry in trusted.values()
        ):
            raise PolicyError("UNPATCHED_TRUSTED_IDENTITY_OCCURRENCE")
        result[npm].add(package_key("npm", name, string(row.get("version"))))
    if seen_trusted != trusted.keys():
        raise PolicyError("UNUSED_TRUSTED_SOURCE")
    if not all(result.values()):
        raise PolicyError("EMPTY_INVENTORY")
    return result


def group_severity(
    group: dict[str, object], advisories: list[dict[str, object]]
) -> str:
    """A usable group score never excuses an advisory with invalid metadata."""
    severity = score_severity(group.get("max_severity"))
    for advisory in advisories:
        if advisory.get("withdrawn"):
            raise PolicyError("WITHDRAWN_ADVISORY_NEEDS_TRIAGE")
        vectors = array(advisory.get("severity", []))
        if not vectors or any(not valid_vector(vector) for vector in vectors):
            severity = "unknown"
    return severity


def package_findings(
    row: dict[str, object], key: Package, artifact: tuple[str, ...]
) -> list[Finding]:
    findings: list[Finding] = []
    vulnerabilities: dict[str, dict[str, object]] = {}
    for raw_advisory in array(row.get("vulnerabilities", [])):
        advisory = obj(raw_advisory)
        identifier = string(advisory.get("id"))
        if identifier in vulnerabilities:
            raise PolicyError("DUPLICATE_ADVISORY")
        vulnerabilities[identifier] = advisory
    covered: set[str] = set()
    for value_group in array(row.get("groups", [])):
        group = obj(value_group)
        ids = {string(v) for v in array(group.get("ids"))}
        if not ids or not ids <= vulnerabilities.keys() or covered & ids:
            raise PolicyError("INVALID_ADVISORY_GROUP")
        covered |= ids
        severity = group_severity(group, [vulnerabilities[key] for key in sorted(ids)])
        for identifier in sorted(ids):
            locator = (*key, identifier, *artifact)
            findings.append(Finding("dependency", digest(locator), severity, locator))
    if covered != vulnerabilities.keys():
        raise PolicyError("UNCOVERED_ADVISORY")
    return findings


def trusted_findings(row: dict[str, object], entry: dict[str, str]) -> list[Finding]:
    package = obj(row.get("package"))
    key = ("npm", entry["name"], entry["version"])
    if (
        tuple(package.get(k) for k in ("ecosystem", "name", "version")) != key
        or package.get("purl") != f"pkg:npm/{key[1]}@{key[2]}"
    ):
        raise PolicyError("TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN")
    findings = package_findings(row, key, (entry["artifact_sha256"],))
    if not any(
        f.locator[3] == "GHSA-fc5q-39xc-vjpf" and f.severity in {"high", "critical"}
        for f in findings
    ):
        raise PolicyError("TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN")
    return findings


def evaluate(
    report: object,
    root: Path,
    expected: dict[str, set[Package]],
    sbom: tuple[Path, dict[str, str]] | None = None,
) -> tuple[list[Finding], int]:
    data = obj(report)
    seen: dict[str, set[Package]] = {name: set() for name in expected}
    findings: list[Finding] = []
    sources: set[str] = set()
    local_packages = {
        package_key("PyPI", string(obj(p).get("name")), string(obj(p).get("version")))
        for p in array(
            tomllib.loads((root / "backend/uv.lock").read_text()).get("package")
        )
        if obj(p).get("source") in ({"editable": "."}, {"virtual": "."})
    }
    sbom_seen = False
    for entry in array(data.get("results")):
        source = obj(obj(entry).get("source"))
        path = Path(string(source.get("path")))
        path = path if path.is_absolute() else root / path
        packages = array(obj(entry).get("packages"))
        if sbom is not None and path.resolve() == sbom[0].resolve():
            if sbom_seen or source.get("type") != "sbom" or len(packages) != 1:
                raise PolicyError("TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN")
            sbom_seen = True
            findings.extend(trusted_findings(obj(packages[0]), sbom[1]))
            continue
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            raise PolicyError("UNEXPECTED_LOCKFILE") from None
        if (
            source.get("type") != "lockfile"
            or relative not in expected
            or relative in sources
        ):
            raise PolicyError("UNEXPECTED_LOCKFILE")
        sources.add(relative)
        for value in packages:
            row = obj(value)
            package = obj(row.get("package"))
            key = package_key(
                string(package.get("ecosystem")),
                string(package.get("name")),
                string(package.get("version")),
            )
            if relative == "backend/uv.lock" and key in local_packages:
                continue
            seen[relative].add(key)
            findings.extend(package_findings(row, key, ()))
    if sbom is not None and not sbom_seen:
        raise PolicyError("TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN")
    if sources != expected.keys() or seen != expected:
        raise PolicyError("INCOMPLETE_DEPENDENCY_INVENTORY")
    return findings, sum(len(packages) for packages in seen.values())
