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


def test_f19_cli_captures_strict_profile_and_restore_rejects_inline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(profile_workload, "run", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "profile",
            "--phase",
            "W1",
            "--output",
            str(tmp_path),
            "--publisher-mode",
            "child",
            "--acceptance-profile",
            "F19_SET5",
        ],
    )
    assert profile_workload.main() == 0
    assert run.call_args.args[0].acceptance_profile == "F19_SET5"
    monkeypatch.setattr("sys.argv", ["restore", "build", "--output", str(tmp_path), "--f19"])
    with pytest.raises(SystemExit) as rejected:
        profile_restore.main()
    assert rejected.value.code == 2


@pytest.mark.parametrize(
    "extra,allowed",
    [
        ([], True),
        (["--phase", "W2"], False),
        (["--publisher-mode", "inline"], False),
        (["--acceptance-profile", "F18_R34"], False),
        (["--pool-diagnostic-seconds", "60"], False),
        (["--stop-preflight"], False),
        (["--source-diagnostic-seconds", "60"], False),
        (["--dedicated-loss-diagnostic"], False),
    ],
)
def test_nc16_is_explicit_bounded_and_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str], allowed: bool
) -> None:
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(profile_workload, "run", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "profile",
            "--phase",
            "W1",
            "--output",
            str(tmp_path),
            "--publisher-mode",
            "child",
            "--acceptance-profile",
            "F19_SET5",
            "--pool-diagnostic-seconds",
            "180",
            *extra,
        ],
    )
    if allowed:
        assert profile_workload.main() == 0
        assert run.call_args.args[0].pool_diagnostic_seconds == 180
    else:
        with pytest.raises(SystemExit) as rejected:
            profile_workload.main()
        assert rejected.value.code == 2
        run.assert_not_called()


@pytest.mark.parametrize(
    "extra,allowed",
    [
        ([], True),
        (["--phase", "W2"], False),
        (["--publisher-mode", "inline"], False),
        (["--acceptance-profile", "F18_R34"], False),
        (["--risk-diagnostic-seconds", "180"], False),
        (["--stop-preflight"], False),
        (["--pool-diagnostic-seconds", "180"], False),
        (["--risk-observer"], False),
        (["--dedicated-loss-diagnostic"], False),
    ],
)
def test_nc18_explicit_profile_and_exclusive_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str], allowed: bool
) -> None:
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(profile_workload, "run", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "profile",
            "--phase",
            "W1",
            "--output",
            str(tmp_path),
            "--publisher-mode",
            "child",
            "--acceptance-profile",
            "F19_SET5",
            "--risk-diagnostic-seconds",
            "300",
            *extra,
        ],
    )
    if allowed:
        assert profile_workload.main() == 0
        assert run.call_args.args[0].risk_diagnostic_seconds == 300
    else:
        with pytest.raises(SystemExit) as rejected:
            profile_workload.main()
        assert rejected.value.code == 2
        run.assert_not_called()


@pytest.mark.parametrize(
    "extra,allowed",
    [
        ([], True),
        (["--phase", "W2"], False),
        (["--publisher-mode", "inline"], False),
        (["--acceptance-profile", "F18_R34"], False),
        (["--worker", "risk"], False),
        (["--memory-diagnostic-seconds", "60"], False),
        (["--dispatch-diagnostic-seconds", "60"], False),
        (["--source-diagnostic-seconds", "60"], False),
        (["--pool-diagnostic-seconds", "180"], False),
        (["--risk-diagnostic-seconds", "300"], False),
        (["--stop-preflight"], False),
        (["--dedicated-loss-diagnostic"], False),
        (["--dispatch-trace"], False),
        (["--pool-trace"], False),
        (["--partial-barrier", "/tmp/barrier"], False),
        (["--risk-observer"], False),
        (["--stop", "/tmp/stop"], False),
        (["--metrics", "/tmp/metrics"], False),
    ],
)
def test_book_clock_diagnostic_is_explicit_parent_only_and_exclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: list[str],
    allowed: bool,
) -> None:
    run = AsyncMock(return_value=0)
    monkeypatch.setattr(profile_workload, "run", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "profile",
            "--phase",
            "W1",
            "--output",
            str(tmp_path),
            "--acceptance-profile",
            "F19_SET5",
            "--publisher-mode",
            "child",
            "--book-clock-diagnostic-seconds",
            "60",
            *extra,
        ],
    )
    if allowed:
        assert profile_workload.main() == 0
        assert run.call_args.args[0].book_clock_diagnostic_seconds == 60
    else:
        with pytest.raises(SystemExit) as rejected:
            profile_workload.main()
        assert rejected.value.code == 2
        run.assert_not_called()
