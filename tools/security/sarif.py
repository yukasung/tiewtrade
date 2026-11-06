"""Full SARIF evaluation without publishing source messages or snippets."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import unquote, urlsplit

from tools.security.model import (
    Finding,
    PolicyError,
    array,
    digest,
    natural,
    obj,
    score_severity,
    string,
)


def source_identity(root: Path, uri: str) -> str:
    parsed = urlsplit(uri)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise PolicyError("INVALID_SOURCE_URI")
    path = (root / unquote(parsed.path)).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise PolicyError("INVALID_SOURCE_PATH")
    # Hash the complete source blob, not a secret value. No source leaves the runner.
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rule_descriptor(
    row: dict[str, object], components: list[dict[str, object]], rules: dict[str, dict[str, object]]
) -> dict[str, object]:
    reference = obj(row.get("rule", {}))
    identifier = row.get("ruleId", reference.get("id"))
    descriptor = None
    index = reference.get("index", row.get("ruleIndex"))
    if index is not None:
        component_reference = obj(reference.get("toolComponent", {}))
        component_index = component_reference.get("index")
        # SARIF toolComponent.index addresses extensions, not the driver.
        component = 0 if component_index is None else natural(component_index) + 1
        if component >= len(components):
            raise PolicyError("MISSING_RULE_COMPONENT")
        descriptors = array(components[component].get("rules", []))
        position = natural(index)
        if position >= len(descriptors):
            raise PolicyError("MISSING_RULE_INDEX")
        descriptor = obj(descriptors[position])
        if identifier is not None and identifier != descriptor.get("id"):
            raise PolicyError("CONFLICTING_RULE_REFERENCE")
    if descriptor is None:
        descriptor = rules.get(string(identifier))
    if descriptor is None:
        raise PolicyError("MISSING_RULE")
    return descriptor


def diagnostic_id(notification: dict[str, object], run: dict[str, object]) -> str | None:
    """Resolve notification descriptors across driver/pack notification tables."""
    reference = obj(notification.get("descriptor", {}))
    identifier = reference.get("id")
    if "index" in reference:
        tool = obj(run.get("tool"))
        components = [obj(tool.get("driver")), *(obj(c) for c in array(tool.get("extensions", [])))]
        component_index = obj(reference.get("toolComponent", {})).get("index")
        component = 0 if component_index is None else natural(component_index) + 1
        if component >= len(components):
            raise PolicyError("MISSING_RULE_COMPONENT")
        notifications = array(components[component].get("notifications", []))
        index = natural(reference["index"])
        if index >= len(notifications):
            raise PolicyError("MISSING_RULE_INDEX")
        resolved = string(obj(notifications[index]).get("id"))
        if identifier is not None and identifier != resolved:
            raise PolicyError("CONFLICTING_RULE_REFERENCE")
        identifier = resolved
    return None if identifier is None else string(identifier)


def extracted_file_count(run: dict[str, object], root: Path, prefix: str) -> int:
    """Compare CodeQL's expected-file descriptors with actual extracted File facts."""
    extracted: set[str] = set()
    expected: set[str] = set()
    language = {"py": "python", "js": "javascript", "actions": "actions"}[prefix]
    success_id = f"{prefix}/diagnostics/successfully-extracted-files"
    expected_ids = {
        f"{prefix}/baseline/expected-extracted-files",
        f"cli/expected-extracted-files/{language}",
    }
    for invocation in array(run.get("invocations")):
        for value in array(obj(invocation).get("toolExecutionNotifications", [])):
            notification = obj(value)
            identifier = diagnostic_id(notification, run)
            if identifier != success_id and identifier not in expected_ids:
                continue
            for location in array(notification.get("locations", [])):
                artifact = obj(obj(obj(location).get("physicalLocation")).get("artifactLocation"))
                uri = string(artifact.get("uri"))
                source_identity(root, uri)
                canonical = (root / unquote(uri)).resolve().relative_to(root.resolve()).as_posix()
                target = extracted if identifier == success_id else expected
                target.add(canonical)
    # Expected-file locations attest the calculated baseline even when the CLI
    # telemetry marker is intentionally omitted by --no-sarif-include-diagnostics.
    if not expected or not extracted or not expected <= extracted:
        raise PolicyError("MISSING_FILE_COVERAGE")
    return len(extracted)


def evaluate(report: object, root: Path, language: str) -> tuple[list[Finding], int]:
    data = obj(report)
    if data.get("version") != "2.1.0":
        raise PolicyError("UNSUPPORTED_SARIF")
    runs = array(data.get("runs"))
    if len(runs) != 1 or language not in {"python", "javascript-typescript", "actions"}:
        raise PolicyError("INVALID_SARIF_RUNS")
    run = obj(runs[0])
    if obj(run.get("properties", {})).get("incrementalMode"):
        raise PolicyError("INCREMENTAL_ANALYSIS_NOT_ALLOWED")
    invocations = array(run.get("invocations"))
    if not invocations or any(obj(i).get("executionSuccessful") is not True for i in invocations):
        raise PolicyError("UNSUCCESSFUL_SARIF_INVOCATION")
    for invocation in invocations:
        for field in ("toolExecutionNotifications", "toolConfigurationNotifications"):
            if any(obj(n).get("level") == "error" for n in array(obj(invocation).get(field, []))):
                raise PolicyError("SARIF_EXECUTION_ERROR")
    tool = obj(run.get("tool"))
    driver = obj(tool.get("driver"))
    if "CodeQL" not in string(driver.get("name")):
        raise PolicyError("WRONG_SARIF_TOOL")
    components = [driver, *(obj(v) for v in array(tool.get("extensions", [])))]
    rules: dict[str, dict[str, object]] = {}
    for component in components:
        for rule in array(component.get("rules", [])):
            row = obj(rule)
            identifier = string(row.get("id"))
            if identifier in rules and rules[identifier] != row:
                raise PolicyError("AMBIGUOUS_RULE")
            rules[identifier] = row
    if not rules:
        raise PolicyError("NO_ANALYSIS_RULES")
    expected_prefix = {"python": "py", "javascript-typescript": "js", "actions": "actions"}[
        language
    ]
    metrics = array(obj(run.get("properties", {})).get("metricResults", []))
    extracted = 0
    for metric in metrics:
        row = obj(metric)
        descriptor = rule_descriptor(row, components, rules)
        tags = array(obj(descriptor.get("properties", {})).get("tags", []))
        if "lines-of-code" in tags and string(descriptor.get("id")).startswith(
            expected_prefix + "/"
        ):
            extracted += natural(row.get("value"))
    if language != "actions" and extracted == 0:
        raise PolicyError("MISSING_EXTRACTION_COVERAGE")
    files = extracted_file_count(run, root, expected_prefix)
    findings: list[Finding] = []
    for value in array(run.get("results")):
        row = obj(value)
        descriptor = rule_descriptor(row, components, rules)
        identifier = string(descriptor.get("id"))
        if not identifier.startswith(expected_prefix + "/"):
            raise PolicyError("WRONG_FINDING_LANGUAGE")
        properties = obj(descriptor.get("properties", {}))
        tags = array(properties.get("tags", []))
        if "security-severity" not in properties and tags and "security" not in tags:
            continue
        severity = score_severity(properties.get("security-severity"))
        locations = array(row.get("locations"))
        if not locations:
            raise PolicyError("MISSING_FINDING_LOCATION")
        identities: list[object] = []
        for location in locations:
            physical = obj(obj(location).get("physicalLocation"))
            artifact = obj(physical.get("artifactLocation"))
            uri = string(artifact.get("uri"))
            region = obj(physical.get("region"))
            line = natural(region.get("startLine"))
            if line == 0:
                raise PolicyError("INVALID_SOURCE_LINE")
            identities.append([uri, line, source_identity(root, uri)])
        findings.append(
            Finding(
                "codeql",
                digest([language, identifier, identities]),
                severity,
                (language, identifier, uri, str(line)),
            )
        )
    return findings, files


def structure_counts(report: object) -> dict[str, int]:
    """Safe schema diagnostics: only fixed labels and counts, never input strings."""

    def mapping(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    def sequence(value: object) -> list[object]:
        return value if isinstance(value, list) else []

    runs = sequence(mapping(report).get("runs"))
    invocations = [mapping(i) for run in runs for i in sequence(mapping(run).get("invocations"))]
    metrics = [
        mapping(m)
        for run in runs
        for m in sequence(mapping(mapping(run).get("properties")).get("metricResults"))
    ]
    artifacts = [mapping(a) for run in runs for a in sequence(mapping(run).get("artifacts"))]
    rules = [
        mapping(rule)
        for run in runs
        for component in [
            mapping(mapping(run).get("tool")).get("driver"),
            *sequence(mapping(mapping(run).get("tool")).get("extensions")),
        ]
        for rule in sequence(mapping(component).get("rules"))
    ]
    return {
        "runs": len(runs),
        "invocations": len(invocations),
        "successful_invocations": sum(i.get("executionSuccessful") is True for i in invocations),
        "metrics": len(metrics),
        "metric_rule_ids": sum("ruleId" in m for m in metrics),
        "metric_rule_references": sum("rule" in m for m in metrics),
        "integer_metric_values": sum(type(m.get("value")) is int for m in metrics),
        "artifacts": len(artifacts),
        "analysis_targets": sum("analysisTarget" in sequence(a.get("roles")) for a in artifacts),
        "artifact_locations": sum("uri" in mapping(a.get("location")) for a in artifacts),
        "rules": len(rules),
        "lines_of_code_rules": sum(
            "lines-of-code" in sequence(mapping(r.get("properties")).get("tags")) for r in rules
        ),
    }
