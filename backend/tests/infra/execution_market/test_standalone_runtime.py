"""Standalone opt-in survives CLI, recovery and restart without changing the fixture."""

from __future__ import annotations

import argparse
import asyncio
import json
import runpy
import sys
from pathlib import Path
from types import CoroutineType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.infra.execution_market import profile_diagnostics as diagnostic
from tests.infra.execution_market import profile_workload as f15


@pytest.mark.parametrize("r8,coordinate", [(False, False), (True, False), (True, True)])
def test_worker_cli_forwards_budget_before_starting_any_database_work(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, r8: bool, coordinate: bool
) -> None:
    seen = []

    def capture(coroutine: CoroutineType[Any, Any, Any]) -> int:
        assert coroutine.cr_frame is not None
        seen.append(
            (
                coroutine.cr_frame.f_locals["claim_limit"],
                coroutine.cr_frame.f_locals["coordinate_claims"],
            )
        )
        coroutine.close()
        return 0

    monkeypatch.setattr(asyncio, "run", capture)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile_workload",
            "--worker-only",
            "--worker-name",
            "test",
            "--worker-stop",
            str(tmp_path / "stop"),
            "--worker-metrics",
            str(tmp_path / "metrics.json"),
            *(["--r8-claim-budget"] if r8 else []),
            *(["--coordinate-claims"] if coordinate else []),
        ],
    )
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(Path(f15.__file__)), run_name="__main__")
    assert caught.value.code == 0
    assert seen == [(1 if r8 else None, coordinate)]


@pytest.mark.parametrize("r8,coordinate", [(False, False), (True, False), (True, True)])
async def test_diagnostic_worker_uses_same_explicit_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, r8: bool, coordinate: bool
) -> None:
    worker = AsyncMock()
    monkeypatch.setattr(f15, "run_worker_process", worker)
    await diagnostic.observe_worker(
        argparse.Namespace(
            worker_name="test",
            worker_stop=tmp_path / "stop",
            worker_metrics=tmp_path / "metrics.json",
            r8_claim_budget=r8,
            coordinate_claims=coordinate,
        )
    )
    assert worker.await_count == 1
    assert worker.call_args.kwargs == {
        "claim_limit": 1 if r8 else None,
        **({"coordinate_claims": True} if coordinate else {}),
    }


@pytest.mark.parametrize(
    "r8,heartbeat,coordinate",
    [(False, False, False), (True, False, False), (True, True, False), (True, True, True)],
)
@pytest.mark.parametrize("phase", ["W1", "SMOKE", "W2_OVERFLOW", "W3"])
async def test_parent_manifest_and_all_worker_launch_paths_use_selected_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    r8: bool,
    heartbeat: bool,
    coordinate: bool,
    phase: str,
) -> None:
    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(f15, "create_engine_for", lambda role: engine)
    monkeypatch.setattr(f15, "database_manifest", AsyncMock(return_value={}))
    monkeypatch.setattr(f15, "seed_owners", AsyncMock(return_value=[]))
    monkeypatch.setattr(f15, "seed_baseline", AsyncMock())
    worker = SimpleNamespace(returncode=None)

    async def stop_workers(*args: Any) -> None:
        worker.returncode = 1

    monkeypatch.setattr(f15, "stop_worker_processes", stop_workers)
    monkeypatch.setattr(f15, "economic_snapshot", AsyncMock(return_value={}))
    monkeypatch.setattr(f15, "publish_overflow", AsyncMock(return_value=1))
    monkeypatch.setattr(f15, "load_fault_schedule", lambda path: ([], 1, "digest"))
    launched = asyncio.Event()
    launches = []

    async def launch(*args: Any, **kwargs: Any) -> Any:
        launches.append(kwargs)
        if phase == "W1" or len(launches) == 2:
            launched.set()
            raise RuntimeError("controlled launch checkpoint")
        return [worker], tmp_path / "stop", []

    async def publisher(
        source: Any, stop: asyncio.Event, stats: dict[str, Any], *, heartbeat_per_book: bool
    ) -> None:
        assert heartbeat_per_book is heartbeat
        stats["published"] = 2
        await stop.wait()

    async def sampler(*args: Any) -> None:
        await asyncio.Event().wait()

    async def faults(*args: Any, **kwargs: Any) -> None:
        await kwargs["restart_workers"]()

    async def cycles(*args: Any) -> float:
        if phase == "SMOKE":
            raise RuntimeError("controlled launch checkpoint")
        await launched.wait()
        return 0

    monkeypatch.setattr(f15, "start_worker_processes", launch)
    monkeypatch.setattr(f15, "market_publisher", publisher)
    monkeypatch.setattr(f15, "resource_sampler", sampler)
    monkeypatch.setattr(f15, "run_fault_schedule", faults)
    monkeypatch.setattr(f15, "run_scheduled_cycles", cycles)
    output = tmp_path / "run"
    args = argparse.Namespace(
        output=output,
        phase=phase,
        owners=100,
        baseline_orders=20,
        cycles_per_owner=1,
        rate=10,
        workers=20,
        baseline_manifest=None,
        fault_schedule=tmp_path / "schedule.json",
        redis_container="test-redis",
        r8_claim_budget=r8,
        coordinate_claims=coordinate,
        publisher_heartbeat_per_book=heartbeat,
        diagnostics=phase == "SMOKE",
    )
    async with asyncio.timeout(3):
        with pytest.raises(RuntimeError, match="controlled launch checkpoint"):
            await f15._run(args)
    assert all(call["r8_claim_budget"] is r8 for call in launches)
    assert all(call["coordinate_claims"] is coordinate for call in launches)
    assert [call.get("group", "worker") for call in launches] == (
        ["worker"]
        if phase in {"W1", "SMOKE"}
        else ["worker", "recovery-worker" if phase == "W2_OVERFLOW" else "restart-0"]
    )
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["profile"] == f15.PROFILE_VERSION == "F15_W1_W2_W3_V2"
    assert manifest["worker_runtime"] == (
        "F15_STANDALONE_R8_HEARTBEAT_V1"
        if heartbeat
        else "F15_STANDALONE_R8_OPTIN_V1"
        if r8
        else "F15_STANDALONE_DEFAULT_V1"
    )
    assert manifest["worker_round_limit"] == 20
    assert manifest["claim_coordination"] == ("SERIALIZED_CLAIM_V2" if coordinate else None)
    assert manifest["worker_claim_limit"] == (1 if r8 else None)
    assert manifest["worker_tick_seconds"] == 0.02
    assert manifest["publisher_heartbeat_per_book"] is heartbeat
    failure = json.loads((output / "failure.json").read_text())
    assert failure["worker_failures"] == ([] if phase == "W1" else ["worker-0-exited:1"])
    if phase == "SMOKE":
        control = json.loads((output / "dispatch-trace-control.json").read_text())
        assert control["seconds"] == 180 and control["detail_limit"] == 0
        assert not (output / "dispatch-trace-control.json.tmp").exists()


async def test_heartbeat_requires_explicit_r8_before_creating_output(tmp_path: Path) -> None:
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="heartbeat requires"):
        await f15._run(argparse.Namespace(output=output, publisher_heartbeat_per_book=True))
    assert not output.exists()


@pytest.mark.parametrize("extra", [[], ["--worker-only", "--r8-claim-budget"]])
def test_cli_rejects_unsupported_heartbeat_runtime(
    monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["profile", "--publisher-heartbeat-per-book", *extra])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(Path(f15.__file__)), run_name="__main__")
    assert caught.value.code == 2


@pytest.mark.parametrize("enabled,r8", [(1, True), (True, False), (True, 1)])
async def test_invalid_coordination_rejected_before_output_or_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: Any, r8: Any
) -> None:
    monkeypatch.setattr(f15, "create_engine_for", lambda *a: pytest.fail("DB"))
    output = tmp_path / "run"
    args = argparse.Namespace(output=output, coordinate_claims=enabled, r8_claim_budget=r8)
    for parent in (f15.run, f15._run):
        with pytest.raises(ValueError, match="claim coordination requires"):
            await parent(args)
    with pytest.raises(ValueError, match="claim coordination requires"):
        await f15.start_worker_processes(1, output, coordinate_claims=enabled, r8_claim_budget=r8)
    assert not output.exists()


@pytest.mark.parametrize(
    "unsupported",
    [
        {},
        {"claim_limit": 2},
        {"claim_limit": 1, "round_limit": 19},
        {"claim_limit": 1, "prefer_same_pair": True},
        {"claim_limit": 1, "alternate_admission": True},
        {"claim_limit": 1, "source_resumption": True},
    ],
)
async def test_worker_rejects_unsupported_coordination_before_pid_or_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsupported: dict[str, Any]
) -> None:
    monkeypatch.setattr(f15, "create_engine_for", lambda *a: pytest.fail("DB"))
    metrics = tmp_path / "metrics.json"
    with pytest.raises(ValueError, match="claim coordination requires"):
        await f15.run_worker_process(
            "test", tmp_path / "stop", metrics, coordinate_claims=True, **unsupported
        )
    assert not list(tmp_path.iterdir())
