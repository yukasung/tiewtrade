from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "verify.yml"
INSTRUCTIONS_PATH = REPOSITORY_ROOT / "AGENTS.md"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _repository_instructions_text() -> str:
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def test_verify_workflow_targets_main_without_duplicate_branch_pushes() -> None:
    workflow = _workflow_text()

    assert "push:\n    branches: [main]" in workflow
    assert "pull_request:\n    branches: [main]" in workflow


def test_verify_workflow_uses_bounded_least_privilege_environment() -> None:
    workflow = _workflow_text()

    required_fragments = (
        "contents: read",
        "runs-on: ubuntu-latest",
        "timeout-minutes: 10",
        "PYTHONPATH: src",
        "QT_QPA_PLATFORM: offscreen",
        "actions/checkout@v6",
        "fetch-depth: 0",
        "actions/setup-python@v6",
        'python-version: "3.12"',
        "cache: pip",
        "cache-dependency-path: pyproject.toml",
        'python -m pip install -e ".[dev]"',
    )

    for fragment in required_fragments:
        assert fragment in workflow


def test_verify_workflow_runs_the_repository_checklist() -> None:
    workflow = _workflow_text()

    required_commands = (
        "python -m pytest -q",
        "python -m ruff check .",
        "python -m ruff format --check .",
        "python -m mypy src",
        'git diff --check "$BASE_SHA" HEAD',
    )

    for command in required_commands:
        assert command in workflow

    assert "github.event.pull_request.base.sha" in workflow
    assert "github.event.before" in workflow
    assert "continue-on-error" not in workflow


def test_repository_instructions_distinguish_local_and_ci_whitespace() -> None:
    instructions = _repository_instructions_text()

    assert "`git diff --check` สำหรับ working-tree changes" in instructions
    assert "`git diff --check <base> HEAD` สำหรับ committed range" in instructions
