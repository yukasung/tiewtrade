"""NC08 profile, independent observers, clocks, caps and phase attribution."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from time import monotonic
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_checkpoint_polling as probe
from tests.infra.execution_market import profile_runtime_observation as runtime
from tests.infra.execution_market.profile_workload import save
from tests.infra.execution_market.test_checkpoint_polling import group_runtime as group_runtime
from tests.infra.risk_limits.profile_pool_timing import TransactionTrace
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db import session as db


def leaves(error: BaseException) -> list[BaseException]:
    if isinstance(error, BaseExceptionGroup):
        return [leaf for child in error.exceptions for leaf in leaves(child)]
    return [error]


def test_profiles_are_explicit_and_default_is_unchanged() -> None:
    assert probe.conditions(runtime.PROFILE) == [(1, n) for n in (0, 100, 100, 0, 100, 0, 0, 100)]
    assert 96 + sum(w * 24 for w, _ in probe.conditions(runtime.PROFILE)) == 288
    assert 96 + sum(w * 24 for w, _ in probe.conditions()) == 576
    with pytest.raises(ValueError, match="unknown"):
        probe.conditions("typo")


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (1, 2, "readiness"),
        (3, 4, "measurement"),
        (5, 6, "shutdown"),
        (2, 4, "cross_boundary"),
        (4, 6, "cross_boundary"),
    ],
)
def test_phase_attribution_keeps_cross_boundary_rows(
    start: float, end: float, expected: str
) -> None:
    assert runtime.interval_phase(start, end, 3, 5) == expected


async def test_disabled_observation_has_no_tasks_files_or_clock_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden() -> Any:
        pytest.fail("disabled profile read clocks")

    monkeypatch.setattr(runtime, "stamp", forbidden)
    observer = runtime.RuntimeObservation(tmp_path / "runtime.json", enabled=False)
    async with observer.observe():
        observer.mark("ready")
    assert not observer.path.exists()


async def test_loop_sampler_skips_missed_ticks_and_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [10.0]
    sleeps = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += 0.45

    monkeypatch.setattr(runtime, "monotonic", lambda: clock[0])
    monkeypatch.setattr(runtime, "time", lambda: 1000.0)
    monkeypatch.setattr(runtime, "process_time", lambda: 2.5)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setattr(runtime, "ROW_LIMIT", 2)
    observer = runtime.RuntimeObservation(tmp_path / "runtime.json", enabled=True)
    with pytest.raises(RuntimeError, match="TRUNCATED"):
        await observer.ticks_until(asyncio.Event())
    assert len(observer.ticks) == 2 and sleeps == [0.1, 0.1, 0.1]
    assert observer.ticks[0]["lag_seconds"] == pytest.approx(0.35)
    assert observer.ticks[0]["missed_intervals"] == 3
    assert observer.ticks[1]["due"] == pytest.approx(10.55)
    assert observer.ticks[0]["wall"] == 1000 and observer.ticks[0]["cpu"] == 2.5


async def test_observer_failure_preserves_writer_error_and_closes(tmp_path: Path) -> None:
    observer = runtime.RuntimeObservation(tmp_path / "runtime.json", enabled=True)
    original = ValueError("writer failed")
    with pytest.raises(ExceptionGroup) as failure:
        async with observer.observe():
            raise original
    assert original in leaves(failure.value)
    result = json.loads(observer.path.read_text())
    assert result["closed"] and result["phases"][-1]["phase"] == "observer_closed"


async def test_slow_docker_does_not_block_other_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = asyncio.Event()
    release = asyncio.Event()
    entered = asyncio.Event()
    counts = {"database": 0, "host": 0, "docker": 0}
    monkeypatch.setattr(runtime, "CADENCES", {"database": 0.005, "host": 0.005, "docker": 0.015})

    async def docker() -> str:
        counts["docker"] += 1
        entered.set()
        await release.wait()
        return "docker"

    async def database() -> str:
        counts["database"] += 1
        return "db"

    async def host() -> str:
        counts["host"] += 1
        return "host"

    task = asyncio.create_task(
        runtime.resources({"database": database, "host": host, "docker": docker}, tmp_path, stop)
    )
    try:
        await entered.wait()
        async with asyncio.timeout(1):
            while min(counts["database"], counts["host"]) < 3:
                await asyncio.sleep(0.005)
        assert counts["docker"] == 1
    finally:
        stop.set()
        release.set()
        await task
    for family, cadence in runtime.CADENCES.items():
        rows = [
            json.loads(s) for s in (tmp_path / f"resource-{family}.jsonl").read_text().splitlines()
        ]
        assert all(r["start_gap_seconds"] >= cadence for r in rows[1:])
        assert all(r["finish"]["monotonic"] >= r["start"]["monotonic"] for r in rows)


async def test_sampler_timeout_retains_missing_row_and_joins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    joined = []
    original = asyncio.timeout
    monkeypatch.setattr(asyncio, "timeout", lambda seconds: original(0.01))

    async def blocked() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            joined.append(True)

    with pytest.raises(TimeoutError):
        await runtime.sample_family("database", blocked, tmp_path / "sample.jsonl", asyncio.Event())
    row = json.loads((tmp_path / "sample.jsonl").read_text())
    assert row["missing"] and row["error"] == "TimeoutError" and joined == [True]


async def test_sampler_cap_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "ROW_LIMIT", 1)

    async def collect() -> int:
        return 1

    with pytest.raises(RuntimeError, match="TRUNCATED"):
        await runtime.sample_family(
            "database", collect, tmp_path / "samples.jsonl", asyncio.Event()
        )
    assert len((tmp_path / "samples.jsonl").read_text().splitlines()) == 1


async def test_cleanup_timeout_cancels_and_joins(monkeypatch: pytest.MonkeyPatch) -> None:
    joined = []
    original = asyncio.timeout
    monkeypatch.setattr(asyncio, "timeout", lambda seconds: original(0.01))

    async def blocked() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            joined.append(True)

    task = asyncio.create_task(blocked())
    with pytest.raises(TimeoutError):
        await runtime.finish_resources(task)
    assert task.done() and joined == [True]


@pytest.mark.parametrize("fault", [None, "writer", "reader", "readiness", "deadline", "observer"])
async def test_profile_group_joins_on_all_fault_paths(
    group_runtime: Any, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    args, state, targets = group_runtime
    args.profile = runtime.PROFILE
    state["fault"] = fault
    original = asyncio.timeout
    monkeypatch.setattr(
        asyncio, "timeout", lambda seconds: original(0.08 if seconds == 10 else 0.025)
    )

    async def resources(*args: Any) -> None:
        if fault == "observer":
            raise ValueError("observer failed")
        await args[-1].wait()

    monkeypatch.setattr(runtime, "resources", resources)
    if fault is None:
        await probe.run_group(args, cast(AsyncEngine, None), targets, [0], 100, {})
    else:
        with pytest.raises(ExceptionGroup) as failure:
            await probe.run_group(args, cast(AsyncEngine, None), targets, [0], 100, {})
        expected = TimeoutError if fault in ("readiness", "deadline") else ValueError
        assert any(isinstance(e, expected) for e in leaves(failure.value))
    assert not state["live"] and state["joined"] == {0}
    assert json.loads((args.output / "runtime.json").read_text())["closed"]


@pytest.mark.parametrize("enabled", [False, True])
async def test_real_trace_monotonic_fields_opt_in_only(
    tmp_path: Path, engine_engine: AsyncEngine, enabled: bool
) -> None:
    control = tmp_path / "control.json"
    save(control, {"started": monotonic(), "seconds": 900})
    trace = TransactionTrace(tmp_path / "trace.jsonl", control=control, monotonic_fields=enabled)
    original = db._begin
    async with (
        trace.observe(),
        user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session,
    ):
        await session.execute("SELECT 1")
    row = json.loads(trace.path.read_text().splitlines()[0])
    assert ("started_monotonic" in row) is enabled
    if enabled:
        assert (
            row["started_monotonic"]
            <= row["checkout_monotonic"]
            <= row["checkin_monotonic"]
            <= row["finished_monotonic"]
        )
        assert row["held_seconds"] == row["checkin_monotonic"] - row["checkout_monotonic"]
    assert db._begin is original and not trace.listeners
