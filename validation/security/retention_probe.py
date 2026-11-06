"""Disposable V-10 controls; reports remain private and this file is never merged."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from tools.security import sarif
from tools.security.model import policy_counts, read_json
from tools.security.scan import execute, scan_dependencies
from tools.security.system import install

ROOT = Path.cwd()
OLD = "c8d8ca78971fce3d98f624e0c35128195168d831"
LOCKS = ("backend/uv.lock", "frontend/package-lock.json")
UNSAFE = '''from flask import Flask, request
app = Flask(__name__)
@app.route("/probe")
def probe():
    return str(eval(request.args["input"]))
'''
SAFE = '''from flask import Flask, request, jsonify
app = Flask(__name__)
@app.route("/probe")
def probe():
    return jsonify(value=request.args["input"])
'''


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("RETENTION_GIT_FAILED")
    return result.stdout


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD").decode().strip()


def history(root: Path) -> None:
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Security Validation Fixture")
    git(root, "config", "user.email", "security-validation@example.invalid")


def identity(root: Path, inputs: tuple[str, ...], first: bool) -> dict:
    changed = [] if first else git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").decode().splitlines()
    return {"commit": git(root, "rev-parse", "HEAD").decode().strip(),
            "changed_paths": changed,
            "input_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in inputs}}


def check(rows: list[dict], changed: list[str]) -> None:
    assert rows[0]["input_sha256"] == rows[1]["input_sha256"], "UNCHANGED_INPUT_REQUIRED"
    assert rows[1]["changed_paths"] == ["README.md"], "ONLY_UNRELATED_DIFF_REQUIRED"
    assert sorted(rows[2]["changed_paths"]) == sorted(changed), "REPAIR_DIFF_REQUIRED"
    assert all(r["counts"]["high"] + r["counts"]["critical"] > 0 for r in rows[:2]), "EXISTING_FINDING_NOT_BLOCKED"
    assert rows[2]["counts"]["blocked"] == rows[2]["counts"]["needs_triage"] == 0, "REPAIR_NOT_ACCEPTED"


def main() -> None:
    # Fetch one public, known ancestor; no credentials are persisted or passed.
    git(ROOT, "fetch", "--quiet", "--depth=1", "origin", OLD)
    tools = Path(os.environ["RUNNER_TEMP"]) / "security-tools"
    osv = install(ROOT, "osv", tools)
    archive = tools / "codeql.tar.gz"
    if not archive.is_file():
        archive = install(ROOT, "codeql", tools)
    with tempfile.TemporaryDirectory(prefix="security-retention-") as private:
        work = Path(private)
        bundle = work / "bundle"
        with tarfile.open(archive) as stream:
            stream.extractall(bundle, filter="data")
        codeql = bundle / "codeql/codeql"
        dependency_root = work / "dependency-history"
        history(dependency_root)
        for relative in LOCKS:
            target = dependency_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git(ROOT, "show", OLD + ":" + relative))
        (dependency_root / "README.md").write_text("baseline\n")
        commit(dependency_root, "baseline")
        dependencies = []
        for phase in ("baseline", "unrelated", "fixed"):
            if phase == "unrelated":
                (dependency_root / "README.md").write_text("documentation only\n")
                commit(dependency_root, "documentation only")
            if phase == "fixed":
                for relative in LOCKS:
                    (dependency_root / relative).write_bytes((ROOT / relative).read_bytes())
                commit(dependency_root, "approved lock remediation")
            findings, coverage = scan_dependencies(dependency_root, ROOT, osv)
            row = {"scanner": "osv", "phase": phase,
                   **identity(dependency_root, LOCKS, phase == "baseline"),
                   "coverage": coverage, "counts": policy_counts(findings, frozenset())}
            dependencies.append(row)
            print("RETENTION_PROBE " + json.dumps(row, sort_keys=True), flush=True)
        check(dependencies, list(LOCKS))
        assert all(r["coverage"] == 464 for r in dependencies), "INCOMPLETE_LOCK_COVERAGE"

        source = work / "source-history"
        history(source)
        (source / "probe.py").write_text(UNSAFE)
        (source / "README.md").write_text("baseline\n")
        commit(source, "baseline")
        sast = []
        for phase in ("baseline", "unrelated", "fixed"):
            if phase == "unrelated":
                (source / "README.md").write_text("documentation only\n")
                commit(source, "documentation only")
            if phase == "fixed":
                (source / "probe.py").write_text(SAFE)
                commit(source, "repair injection")
            # A fresh extraction and analysis per candidate; no reused SARIF/database.
            snapshot = work / ("source-" + phase)
            shutil.copytree(source, snapshot, ignore=shutil.ignore_patterns(".git"))
            database = work / ("database-" + phase)
            report = work / (phase + ".sarif")
            execute([str(codeql), "database", "create", str(database), "--language=python",
                     "--source-root=" + str(snapshot), "--build-mode=none", "--threads=2", "--ram=2048"],
                    work, work / (phase + "-extract.log"), (0,))
            execute([str(codeql), "database", "analyze", str(database),
                     "codeql/python-queries:codeql-suites/python-security-extended.qls",
                     "--format=sarif-latest", "--output=" + str(report),
                     "--sarif-group-rules-by-pack", "--sublanguage-file-coverage",
                     "--no-sarif-include-diagnostics", "--threads=2", "--ram=2048"],
                    work, work / (phase + "-analyze.log"), (0,))
            findings, coverage = sarif.evaluate(read_json(report), snapshot, "python")
            row = {"scanner": "codeql", "phase": phase,
                   **identity(source, ("probe.py",), phase == "baseline"),
                   "coverage": coverage, "counts": policy_counts(findings, frozenset())}
            sast.append(row)
            print("RETENTION_PROBE " + json.dumps(row, sort_keys=True), flush=True)
        check(sast, ["probe.py"])
        print("RETENTION_PROBE_PASSED: existing High/Critical survives README-only diff; repaired candidates pass", flush=True)


if __name__ == "__main__":
    main()
