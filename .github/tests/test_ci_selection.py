"""CI policy tests run without installing backend/frontend dependencies."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ci_selection as policy  # noqa: E402


class PathPolicyTests(unittest.TestCase):
    def test_only_explicit_documentation_locations_skip_application_checks(self) -> None:
        docs = ["AGENTS.md", "specs/mission.md", "specs/features/a/plan.md"]
        self.assertFalse(policy.select_paths(docs).run_checks)
        for path in [
            "frontend/README.md",
            "notes.md",
            "specs/input.json",
            "specs/script.py",
            "specs/schema.yaml",
            "specs/../backend/readme.md",
            "specs//readme.md",
            "./README.md",
            "/specs/plan.md",
            "Specs/plan.md",
            "specs/plan.MD",
        ]:
            with self.subTest(path=path):
                self.assertTrue(policy.select_paths([path]).run_checks)

    def test_every_runtime_test_tooling_or_unknown_path_requires_all_checks(self) -> None:
        for path in [
            "frontend/tests/example.test.ts",
            "frontend/src/App.tsx",
            "frontend/src/style.css",
            "frontend/public/logo.svg",
            "backend/src/tiewtrade/core/money.py",
            "backend/tests/test_money.py",
            "backend/migrations/versions/0001.py",
            "backend/db/bootstrap/001.sql",
            "backend/openapi.json",
            "frontend/src/api-types.ts",
            "backend/uv.lock",
            "backend/pyproject.toml",
            "frontend/package-lock.json",
            "frontend/package.json",
            "compose.yaml",
            "backend/Dockerfile",
            "config/postgres.env",
            ".github/workflows/ci.yml",
            ".github/scripts/ci_selection.py",
            ".gitattributes",
            "unrecognized/input",
        ]:
            with self.subTest(path=path):
                self.assertTrue(policy.select_paths([path]).run_checks)
                self.assertTrue(policy.select_paths(["README.md", path]).run_checks)

    def test_runtime_documentation_exception_overrides_whitelist(self) -> None:
        with patch.object(policy, "RUNTIME_DOC_INPUTS", frozenset({"specs/generated.md"})):
            self.assertTrue(policy.select_paths(["specs/generated.md"]).run_checks)
            self.assertFalse(policy.select_paths(["specs/ordinary.md"]).run_checks)

    def test_existing_operational_and_contract_inputs_require_full(self) -> None:
        for path in [
            "README.md",
            "specs/roadmap.md",
            "specs/features/2026-09-28-venue-layer/validation.md",
            "specs/features/2026-10-01-binance-th-adapter/plan.md",
        ]:
            with self.subTest(path=path):
                self.assertTrue(policy.select_paths([path]).run_checks)
                self.assertTrue(policy.select_paths(["specs/guide.md", path]).run_checks)

    def test_empty_diff_requires_all_checks(self) -> None:
        self.assertTrue(policy.select_paths([]).run_checks)


class GitSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "candidate"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "CI policy fixture")
        self.git("config", "user.email", "ci@example.invalid")
        self.write("AGENTS.md", "Baseline\n")
        self.write("backend/app.py", "# baseline\n")
        self.base = self.commit()

    def git(self, *args: str) -> str:
        return policy.git(self.repo, *args).decode().strip()

    def write(self, path: str, content: str) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self) -> str:
        self.git("add", "--all")
        self.git("commit", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def select(self, base: str | None = None) -> policy.Selection:
        return policy.select_for_event(self.repo, "pull_request", base_sha=base or self.base)

    def run_cli(
        self, event: str = "pull_request", mode: str = "full"
    ) -> subprocess.CompletedProcess[str]:
        event_path = self.root / "event.json"
        event_path.write_text(json.dumps({"pull_request": {"base": {"sha": self.base}}}))
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "ci_selection.py")],
            cwd=self.repo,
            env={
                **os.environ,
                "GITHUB_EVENT_NAME": event,
                "GITHUB_EVENT_PATH": str(event_path),
                "CI_MODE": mode,
                "GITHUB_OUTPUT": str(self.root / "outputs"),
                "GITHUB_STEP_SUMMARY": str(self.root / "summary"),
            },
            capture_output=True,
            text=True,
            check=False,
        )

    def test_docs_paths_with_spaces_newlines_and_shell_text_are_not_split_or_executed(self) -> None:
        self.write("specs/with space.md", "Documentation\n")
        self.write("specs/line\nbreak.md", "Documentation\n")
        self.write("specs/$(touch injected).md", "Documentation\n")
        self.commit()
        self.assertFalse(self.select().run_checks)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.root / "outputs").read_text(), "run_checks=false\nselection=docs-only\n"
        )
        self.assertIn("docs-only", (self.root / "summary").read_text())
        self.assertFalse((self.repo / "injected").exists())

    def test_deleting_runtime_requires_full(self) -> None:
        (self.repo / "backend/app.py").unlink()
        self.commit()
        self.assertTrue(self.select().run_checks)

    def test_readme_launch_command_change_requires_full_at_cli_boundary(self) -> None:
        command = "uvicorn tiewtrade.services.api.app:app --no-proxy-headers\n"
        self.write("README.md", command)
        self.base = self.commit()
        self.write("README.md", command.replace(" --no-proxy-headers", ""))
        self.commit()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "outputs").read_text(), "run_checks=true\nselection=full\n")

    def test_deleting_documentation_is_docs_only(self) -> None:
        (self.repo / "AGENTS.md").unlink()
        self.commit()
        self.assertFalse(self.select().run_checks)

    def test_rename_runtime_to_docs_requires_full(self) -> None:
        (self.repo / "specs").mkdir()
        (self.repo / "backend/app.py").rename(self.repo / "specs/app.md")
        self.commit()
        self.assertTrue(self.select().run_checks)

    def test_rename_docs_to_runtime_requires_full(self) -> None:
        (self.repo / "AGENTS.md").rename(self.repo / "backend/readme.py")
        self.commit()
        self.assertTrue(self.select().run_checks)

    def test_rename_between_docs_locations_is_docs_only(self) -> None:
        (self.repo / "specs").mkdir()
        (self.repo / "AGENTS.md").rename(self.repo / "specs/readme.md")
        self.commit()
        self.assertFalse(self.select().run_checks)

    def test_empty_missing_and_invalid_base_require_full(self) -> None:
        self.assertTrue(self.select().run_checks)
        for base in ["0" * 40, "--help", "$(touch injected)", "", "a\nb"]:
            with self.subTest(base=base):
                self.assertTrue(
                    policy.select_for_event(self.repo, "pull_request", base_sha=base).run_checks
                )
        self.assertFalse((self.repo / "injected").exists())

    def test_unrelated_histories_and_failed_diff_require_full(self) -> None:
        self.git("checkout", "--orphan", "unrelated")
        self.write("AGENTS.md", "Other history\n")
        self.commit()
        self.assertTrue(self.select().run_checks)
        self.assertTrue(
            policy.select_for_event(self.root, "pull_request", base_sha=self.base).run_checks
        )

    def test_main_and_manual_full_cannot_be_reduced_to_docs_only(self) -> None:
        self.write("AGENTS.md", "Documentation\n")
        self.commit()
        self.assertFalse(self.select().run_checks)
        for event in ["push", "workflow_dispatch", "unknown"]:
            with self.subTest(event=event):
                self.assertTrue(
                    policy.select_for_event(self.repo, event, "full", self.base).run_checks
                )
        with self.assertRaises(ValueError):
            policy.select_for_event(self.repo, "workflow_dispatch", "invalid", self.base)

    def test_manual_affected_fetches_main_and_uses_merge_base(self) -> None:
        self.git("checkout", "-b", "feature")
        self.write("specs/plan.md", "Feature docs\n")
        self.commit()
        origin = self.root / "origin.git"
        policy.git(self.root, "clone", "--bare", str(self.repo), str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.assertFalse(
            policy.select_for_event(self.repo, "workflow_dispatch", "affected").run_checks
        )
        # Main can advance independently without turning its runtime changes into PR changes.
        self.git("checkout", "main")
        self.write("backend/app.py", "# advanced main\n")
        self.commit()
        self.git("push", "origin", "main")
        self.git("checkout", "feature")
        self.assertFalse(
            policy.select_for_event(self.repo, "workflow_dispatch", "affected").run_checks
        )
        self.write("backend/app.py", "# feature runtime change\n")
        self.commit()
        self.assertTrue(
            policy.select_for_event(self.repo, "workflow_dispatch", "affected").run_checks
        )

    def test_manual_affected_without_remote_falls_back_to_full(self) -> None:
        self.assertTrue(
            policy.select_for_event(self.repo, "workflow_dispatch", "affected").run_checks
        )

    def test_pr_diff_uses_checked_out_merge_candidate(self) -> None:
        self.git("checkout", "-b", "feature")
        self.write("specs/plan.md", "Feature docs\n")
        self.commit()
        self.git("checkout", "main")
        self.write("backend/app.py", "# new main\n")
        base = self.commit()
        self.git("merge", "--no-ff", "feature", "-m", "PR merge candidate")
        self.assertFalse(self.select(base).run_checks)

    def test_shallow_history_falls_back_to_full_when_merge_base_is_unavailable(self) -> None:
        origin = self.root / "origin.git"
        policy.git(self.root, "clone", "--bare", str(self.repo), str(origin))
        shallow = self.root / "shallow"
        self.write("AGENTS.md", "Docs change\n")
        self.commit()
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "origin", "main")
        policy.git(self.root, "clone", "--depth=1", origin.as_uri(), str(shallow))
        selection = policy.select_for_event(shallow, "pull_request", base_sha=self.base)
        self.assertTrue(selection.run_checks)
        self.assertIn("unavailable", selection.reason)

    def test_missing_pr_base_is_fetched_from_origin(self) -> None:
        self.git("checkout", "-b", "feature")
        self.write("specs/plan.md", "Feature documentation\n")
        self.commit()
        self.git("checkout", "main")
        self.write("backend/app.py", "# independent main update\n")
        base = self.commit()
        origin = self.root / "origin.git"
        policy.git(self.root, "clone", "--bare", str(self.repo), str(origin))
        candidate = self.root / "single-branch"
        policy.git(
            self.root,
            "clone",
            "--single-branch",
            "--branch",
            "feature",
            origin.as_uri(),
            str(candidate),
        )
        with self.assertRaises(subprocess.CalledProcessError):
            policy.git(candidate, "cat-file", "-e", base)
        selection = policy.select_for_event(candidate, "pull_request", base_sha=base)
        self.assertFalse(selection.run_checks)
        self.assertEqual(policy.git(candidate, "rev-parse", base).decode().strip(), base)

    def test_docs_whitespace_failure_emits_no_success_outputs(self) -> None:
        self.write("AGENTS.md", "Trailing whitespace   \n")
        self.commit()
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "outputs").exists())

    def test_selector_error_emits_no_success_outputs(self) -> None:
        result = self.run_cli(event="workflow_dispatch", mode="invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "outputs").exists())


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = (SCRIPTS.parent / "workflows/ci.yml").read_text()
        self.header, jobs = self.workflow.split("jobs:\n", 1)
        starts = list(re.finditer(r"^  ([a-z0-9-]+):\n", jobs, re.MULTILINE))
        self.jobs = {
            match.group(1): jobs[
                match.start() : starts[i + 1].start() if i + 1 < len(starts) else len(jobs)
            ]
            for i, match in enumerate(starts)
        }

    def test_triggers_keep_pr_main_and_explicit_manual_modes_without_path_filters(self) -> None:
        self.assertIn('  push:\n    branches: ["main"]\n', self.header)
        self.assertIn("    types: [opened, reopened, synchronize]\n", self.header)
        self.assertIn("        default: full\n        options: [full, affected]\n", self.header)
        self.assertNotRegex(self.header, r"(?m)^\s+(paths|paths-ignore|pull_request_target):")
        self.assertIn("permissions:\n  contents: read\n", self.header)

    def test_concurrency_cancels_only_pr_and_uses_unique_main_manual_identity(self) -> None:
        self.assertIn("${{ github.event.pull_request.number || github.run_id }}", self.header)
        self.assertIn("${{ github.workflow }}-${{ github.event_name }}-", self.header)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", self.header)

    def test_config_checks_policy_and_exports_only_a_completed_selection(self) -> None:
        config = self.jobs["config"]
        self.assertIn("fetch-depth: 0", config)
        self.assertIn("python3 -m unittest discover -s .github/tests -v", config)
        self.assertIn("run_checks: ${{ steps.select.outputs.run_checks }}", config)
        self.assertIn("python3 .github/scripts/ci_selection.py", config)
        self.assertNotIn("services:", config)

    def test_apt_preparation_is_only_in_e2e_before_the_original_playwright_command(self) -> None:
        command = "sudo python3 .github/scripts/prepare_e2e_apt.py"
        e2e = self.jobs["e2e-run"]
        self.assertEqual(self.workflow.count(command), 1)
        self.assertLess(
            e2e.index(command), e2e.index("npx playwright install --with-deps chromium")
        )
        self.assertIn("working-directory: frontend", e2e)

    def test_required_checks_cannot_succeed_from_an_implicitly_skipped_dependency(self) -> None:
        names = {
            "config": "ค่ากลาง — เวอร์ชัน PostgreSQL",
            "backend": "หลังบ้าน — lint, types, imports, tests",
            "api-contract": "สัญญา API — ชนิดข้อมูลสองฝั่งต้องตรงกัน",
            "frontend": "หน้าบ้าน — lint, types, tests",
            "e2e": "e2e — เบราว์เซอร์จริงเห็นข้อมูลจาก API จริง",
            "docker": "container — ทั้งสองฝั่งรันใน container ได้",
        }
        for job, name in names.items():
            with self.subTest(job=job):
                self.assertIn(f"    name: {name}\n", self.jobs[job])
                if job == "config":
                    continue
                verdict = self.jobs[job]
                worker = self.jobs[f"{job}-run"]
                self.assertIn("if: ${{ always() }}", verdict)
                self.assertIn(f"needs: [config, {job}-run]", verdict)
                self.assertIn("CI_SELECTOR_RESULT: ${{ needs.config.result }}", verdict)
                self.assertIn("CI_SELECTED: ${{ needs.config.outputs.run_checks }}", verdict)
                self.assertIn(f"CI_WORKER_RESULT: ${{{{ needs.{job}-run.result }}}}", verdict)
                self.assertIn("python3 .github/scripts/ci_verdict.py", verdict)
                self.assertIn("if: ${{ needs.config.outputs.run_checks == 'true' }}", worker)
                self.assertIn("needs: config", worker)
                self.assertNotIn("    services:", verdict)
        self.assertNotIn("continue-on-error:", self.workflow)
        self.assertNotRegex(self.workflow, r"(?m)^\s+ref:")


if __name__ == "__main__":
    unittest.main()
