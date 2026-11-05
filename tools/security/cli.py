"""Entrypoint: operational errors are reduced to a constant, secret-free message."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from tools.security import sarif
from tools.security.model import (
    PolicyError,
    aggregate,
    approved_exceptions,
    manifest,
    obj,
    policy_counts,
    read_json,
    string,
)
from tools.security.reporting import summary
from tools.security.scan import scan_dependencies, scan_secrets
from tools.security.system import candidate, configuration, install


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument(
        "command", choices=("install", "secrets", "dependencies", "sarif", "gate", "identity")
    )
    result.add_argument("--root", type=Path, default=Path.cwd())
    result.add_argument("--tool", choices=("gitleaks", "osv", "codeql", "actionlint"))
    result.add_argument("--directory", type=Path, required=True)
    result.add_argument("--binary", type=Path)
    result.add_argument("--language", choices=("python", "javascript-typescript", "actions"))
    result.add_argument("--all-refs", action="store_true")
    return result


def main() -> int:
    os.umask(0o077)
    args = parser().parse_args()
    root = args.root.resolve()
    directory = args.directory.resolve()
    if args.command == "install":
        if args.tool is None:
            raise PolicyError("MISSING_TOOL")
        path = install(root, args.tool, directory)
        # Only the local binary path, never the download response or its diagnostics.
        sys.stdout.write(str(path) + "\n")
        return 0
    identity = candidate(root)
    config = configuration(root)
    if args.command == "identity":
        return 0
    if args.command == "gate":
        reports = [read_json(path, 64 * 1024) for path in sorted(directory.glob("*.json"))]
        jobs = json.loads(os.environ["SECURITY_JOB_RESULTS"])
        aggregate(reports, identity, config, jobs)
        sys.stdout.write("Security gate passed: all components match the current candidate.\n")
        return 0
    if args.command in {"secrets", "dependencies"}:
        if args.binary is None:
            raise PolicyError("MISSING_BINARY")
        binary = args.binary.resolve()
        if args.command == "secrets":
            findings, coverage = scan_secrets(root, root, binary, all_refs=args.all_refs)
        else:
            findings, coverage = scan_dependencies(root, root, binary)
        component = args.command
    else:
        if args.language is None:
            raise PolicyError("MISSING_LANGUAGE")
        sarif_paths = list(directory.glob("*.sarif"))
        if len(sarif_paths) != 1:
            raise PolicyError("MISSING_OR_AMBIGUOUS_SARIF")
        findings, coverage = sarif.evaluate(read_json(sarif_paths[0]), root, args.language)
        component = "codeql-" + args.language
    if candidate(root) != identity or configuration(root) != config:
        raise PolicyError("CANDIDATE_CHANGED_DURING_SCAN")
    exceptions = approved_exceptions(root / ".github/security/exceptions.json")
    counts = policy_counts(findings, exceptions)
    record = manifest(component, identity, config, counts, coverage)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory / (component + ".json")).write_text(json.dumps(record, sort_keys=True) + "\n")
    tools = obj(obj(read_json(root / ".github/security/tools.json")).get("tools"))
    versions = {name: string(obj(value).get("version")) for name, value in tools.items()}
    public_summary = summary(record, findings, exceptions, versions)
    sys.stdout.write(public_summary)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a") as output:
            output.write(public_summary)
    return 0 if record["verdict"] == "pass" else 1


def entrypoint() -> int:
    try:
        return main()
    except Exception:
        # Even unexpected parser/HTTP/subprocess exceptions may embed secret input.
        # Never print exception text, arguments or traceback to public CI logs.
        sys.stderr.write("Security gate failed: incomplete scan or invalid policy data.\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(entrypoint())
