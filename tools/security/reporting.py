"""Only locator metadata crosses the public reporting boundary."""

from __future__ import annotations

import html
import json

from tools.security.model import Finding, PolicyError


def summary(
    record: dict[str, object],
    findings: list[Finding],
    exceptions: frozenset[tuple[str, str]],
    versions: dict[str, str] | None = None,
    *,
    artifact_bindings: list[dict[str, object]] | None = None,
) -> str:
    rows: dict[str, object] = {}
    for finding in findings:
        if any(len(value) > 1024 or not value.isprintable() for value in finding.locator):
            raise PolicyError("INVALID_PUBLIC_LOCATOR")
        rows[finding.identity] = {
            "kind": finding.kind,
            "identity": finding.identity,
            "severity": finding.severity,
            "locator": finding.locator,
            "status": "excepted" if (finding.kind, finding.identity) in exceptions else "open",
        }
    # An HTML-escaped preformatted block prevents Markdown/HTML/workflow-command injection.
    # No scanner message, snippet, Match, Secret, or raw error is read here.
    content: dict[str, object] = {
        "scan": record,
        "tool_versions": versions or {},
        "findings": list(rows.values()),
    }
    if artifact_bindings:
        for binding in artifact_bindings:
            if set(binding) != {"commit", "path", "git_blob", "rule", "resolved_matches"} or any(
                isinstance(value, str) and (len(value) > 1024 or not value.isprintable())
                for value in binding.values()
            ):
                raise PolicyError("INVALID_PUBLIC_LOCATOR")
        content["approved_evidence"] = artifact_bindings
    payload = json.dumps(
        content,
        sort_keys=True,
        indent=2,
    )
    if len(payload.encode()) > 900 * 1024:
        raise PolicyError("OVERSIZE_PUBLIC_SUMMARY")
    return "<pre>" + html.escape(payload) + "</pre>\n"
