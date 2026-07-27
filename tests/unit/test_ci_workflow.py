import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "verify.yml"
INSTRUCTIONS_PATH = REPOSITORY_ROOT / "AGENTS.md"
PYPROJECT_PATH = REPOSITORY_ROOT / "pyproject.toml"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _repository_instructions_text() -> str:
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def _pyproject_config() -> dict[str, object]:
    with PYPROJECT_PATH.open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def test_ruff_configuration_excludes_markdown_from_formatting() -> None:
    config = _pyproject_config()

    assert config["tool"]["ruff"]["extend-exclude"] == ["*.md"]


def test_verify_workflow_targets_main_without_duplicate_branch_pushes() -> None:
    workflow = _workflow_text()

    assert (
        "on:\n"
        "  push:\n"
        "    branches: [main]\n"
        "  pull_request:\n"
        "    branches: [main]\n"
        "    types: [opened, synchronize, reopened, edited]"
    ) in workflow


def test_verify_workflow_uses_bounded_least_privilege_environment() -> None:
    workflow = _workflow_text()

    assert (
        "permissions:\n"
        "  contents: read\n\n"
        "jobs:\n"
        "  verify:\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 10\n"
        "    env:\n"
        "      PYTHONPATH: src\n"
        "      QT_QPA_PLATFORM: offscreen"
    ) in workflow

    assert (
        "      - name: Check out repository\n"
        "        uses: actions/checkout@v6\n"
        "        with:\n"
        "          fetch-depth: 0"
    ) in workflow

    assert (
        "      - name: Set up Python\n"
        "        uses: actions/setup-python@v6\n"
        "        with:\n"
        '          python-version: "3.12"\n'
        "          cache: pip\n"
        "          cache-dependency-path: pyproject.toml\n\n"
        "      - name: Install application and development tools\n"
        '        run: python -m pip install -e ".[dev]"'
    ) in workflow


def test_verify_workflow_installs_the_qt_egl_runtime() -> None:
    workflow = _workflow_text()

    assert (
        "      - name: Install Qt runtime libraries\n"
        "        run: |\n"
        "          sudo apt-get update\n"
        "          sudo apt-get install --yes libegl1"
    ) in workflow


def test_verify_workflow_runs_the_repository_checklist() -> None:
    workflow = _workflow_text()

    assert (
        "      - name: Run tests\n"
        "        run: python -m pytest -q\n\n"
        "      - name: Run Ruff lint\n"
        "        run: python -m ruff check .\n\n"
        "      - name: Check Ruff formatting\n"
        "        run: python -m ruff format --check .\n\n"
        "      - name: Run Mypy\n"
        "        run: python -m mypy src\n\n"
        "      - name: Check committed whitespace\n"
        "        env:\n"
        "          BASE_SHA: ${{ github.event_name == 'pull_request' && "
        "github.event.pull_request.base.sha || github.event.before }}\n"
        '        run: git diff --check "$BASE_SHA" HEAD'
    ) in workflow
    assert "continue-on-error" not in workflow


def test_repository_instructions_distinguish_local_and_ci_whitespace() -> None:
    instructions = _repository_instructions_text()

    assert "`git diff --check` สำหรับ working-tree changes" in instructions
    assert "`git diff --check <base> HEAD` สำหรับ committed range" in instructions
