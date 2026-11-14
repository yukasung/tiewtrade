"""Owner timing alternative preserves all original financial/resource/fault scope."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_internal as profile
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.test_release_profile import options


@pytest.mark.parametrize(
    "profile_name", [profile.RELEASE_TIMING_NAME, profile.RELEASE_NAME, profile.NAME]
)
async def test_full_diagnostic_guard_is_early_and_keeps_legacy_profiles(
    profile_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = options("SMOKE")
    args.acceptance_profile, args.diagnostics = profile_name, True

    def validated(_: Any) -> None:
        raise RuntimeError("legacy-validation-reached-before-resources")

    monkeypatch.setattr(workload, "validate_options", validated)
    if profile_name == profile.RELEASE_TIMING_NAME:
        with pytest.raises(ValueError, match="does not support full diagnostics"):
            await workload.run(args)
    else:
        with pytest.raises(RuntimeError, match="legacy-validation-reached-before-resources"):
            await workload.run(args)


@pytest.mark.parametrize("phase", ["SMOKE", "W1", "W2", "W3", "W2_OVERFLOW"])
def test_only_cycle_budget_and_processing_p95_differ(phase: str) -> None:
    args = options(phase)
    original = profile.validate(args)
    assert profile.positive_cycle_budget(args) == profile.completion_allowance(args) == 60
    assert profile.processing_acceptance(args, 0.3, 0.9)["passed"] is (phase == "W2_OVERFLOW")
    args.acceptance_profile = profile.RELEASE_TIMING_NAME
    assert profile.validate(args) == original
    assert profile.positive_cycle_budget(args) == profile.completion_allowance(args) == 90
    assert not profile.pilot_selected(args)  # Original connection-growth/resource rules.
    assert profile.fault_schedule_for(args.acceptance_profile) == profile.fault_schedule_for(
        profile.RELEASE_NAME
    )
    manifest = profile.manifest(args)
    assert manifest is not None and manifest["owners"] == 100
    assert manifest["positive_cycle_budget_seconds"] == 90
    assert "original 100-account" in str(manifest["scope"])


@pytest.mark.parametrize(
    "p95,p99,passed",
    [
        (0.5, 1.0, True),
        (0.500001, 0.9, False),
        (0.2, 1.000001, False),
        (None, 0.1, False),
        (0.1, None, False),
        (float("nan"), 0.1, False),
    ],
)
def test_revised_processing_boundaries_keep_old_target(
    p95: float | None,
    p99: float | None,
    passed: bool,
) -> None:
    args = options("W1")
    args.acceptance_profile = profile.RELEASE_TIMING_NAME
    result = profile.processing_acceptance(args, p95, p99)
    assert result["passed"] is passed
    assert result["p95_limit_seconds"] == 0.5 and result["p99_limit_seconds"] == 1.0
    assert result["target_p95_seconds"] == 0.25 and result["target_p99_seconds"] == 1.0
    if passed:
        assert result["performance_warning"] and not result["target_passed"]


@pytest.mark.parametrize("elapsed", [59.0, 61.0, 91.0])
async def test_actual_cycle_time_retains_original_grade_and_revised_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    elapsed: float,
) -> None:
    clock = 0.0

    async def cycle(*args: Any, **kwargs: Any) -> None:
        nonlocal clock
        clock = elapsed

    monkeypatch.setattr(workload, "cycle", cycle)
    monkeypatch.setattr(workload, "monotonic", lambda: clock)
    path = tmp_path / "cycles.json"
    operation = workload.run_scheduled_cycles(
        cast(AsyncEngine, None),
        [cast(workload.OwnerState, SimpleNamespace(user_id=uuid4()))],
        uuid4(),
        1,
        1000,
        workload.Counters(),
        [],
        cycle_budget_seconds=90,
        cycle_report=path,
    )
    if elapsed > 90:
        with pytest.raises(workload.CycleBudgetExceededError):
            await operation
    else:
        assert await operation == elapsed
    result = json.loads(path.read_text())
    assert result["completed"] == 1 and result["max_seconds"] == elapsed
    assert result["original_passed"] is (elapsed <= 60)
    assert result["accepted_passed"] is (elapsed <= 90)


async def test_revised_expiry_remains_failure_and_summary_cannot_mask_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = asyncio.timeout
    requested = []

    def fast(seconds: float | None) -> asyncio.Timeout:
        requested.append(seconds)
        return original(0.01)

    async def cycle(*args: Any, **kwargs: Any) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "timeout", fast)
    monkeypatch.setattr(workload, "cycle", cycle)
    monkeypatch.setattr(workload, "save", lambda *a: (_ for _ in ()).throw(OSError("PRIVATE")))
    with pytest.raises(workload.CycleBudgetExceededError) as caught:
        await workload.run_scheduled_cycles(
            cast(AsyncEngine, None),
            [cast(workload.OwnerState, SimpleNamespace(user_id=uuid4()))],
            uuid4(),
            1,
            1000,
            workload.Counters(),
            [],
            cycle_budget_seconds=90,
            cycle_report=tmp_path / "cycles.json",
        )
    assert requested == [90] and "90-second" in str(caught.value)
    assert "PRIVATE" not in str(caught.value.__notes__)


@pytest.mark.parametrize("elapsed,passed", [(390.0, True), (390.001, False)])
def test_final_workflow_allowance_matches_ninety_second_budget(
    elapsed: float, passed: bool
) -> None:
    args = options("SMOKE")
    assert elapsed > 300 + profile.completion_allowance(args)
    args.acceptance_profile = profile.RELEASE_TIMING_NAME
    assert (elapsed <= 300 + profile.completion_allowance(args)) is passed
