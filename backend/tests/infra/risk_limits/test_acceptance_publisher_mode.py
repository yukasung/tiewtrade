"""R33 acceptance entrypoints select child without enabling diagnostic tracing."""

from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tests.infra.risk_limits import profile_restore, profile_workload


@pytest.mark.parametrize("phase", ["W1", "W2", "W3"])
def test_workload_accepts_explicit_child_without_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    run = AsyncMock(return_value=0)
    diagnostic = AsyncMock(side_effect=AssertionError("diagnostic must not run"))
    monkeypatch.setattr(profile_workload, "run", run)
    monkeypatch.setattr(profile_workload, "run_memory_diagnostic", diagnostic)
    monkeypatch.setattr(
        "sys.argv",
        ["profile", "--phase", phase, "--output", str(tmp_path), "--publisher-mode", "child"],
    )
    assert profile_workload.main() == 0
    args: Namespace = run.call_args.args[0]
    assert args.publisher_mode == "child" and args.source_diagnostic_seconds is None
    diagnostic.assert_not_called()


@pytest.mark.parametrize("selection", [[], ["--publisher-mode", "child"]])
def test_restore_build_receives_selected_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: list[str]
) -> None:
    build = AsyncMock(return_value=0)
    monkeypatch.setattr(profile_restore, "build", build)
    monkeypatch.setattr("sys.argv", ["restore", "build", "--output", str(tmp_path), *selection])
    assert profile_restore.main() == 0
    assert build.call_args.args[0].publisher_mode == ("child" if selection else "inline")
