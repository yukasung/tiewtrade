"""Actual pool inventory, return evidence and post-disposal connection checks."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.profile_resources import (
    PoolEvidence,
    cleanup_connections,
    connection_budget,
    returned_pools,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", [None, "write", "replace"])
def test_pool_publication_is_complete_and_preserves_previous_evidence_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool, failure: str | None
) -> None:
    tracker = PoolEvidence(tmp_path / "worker-0.pools.json")
    pending = tracker.path.with_suffix(".json.tmp")
    previous = {"pools": [], "finalized": False}
    if existing:
        tracker.path.write_text(json.dumps(previous))
    tracker.entries = [
        {
            "role": "ENGINE",
            "pool_size": 1,
            "max_overflow": 1,
            "checked_out": 0,
            "peak_checked_out": 1,
        }
    ]
    expected = {"pools": tracker.entries, "finalized": True}
    original_write, original_replace = Path.write_text, Path.replace
    stages: list[str] = []

    def assert_previous_visible() -> None:
        if existing:
            assert json.loads(tracker.path.read_text()) == previous
        else:
            assert not tracker.path.exists()

    def interrupted_write(path: Path, data: str, **kwargs: Any) -> int:
        assert path == pending
        original_write(path, "", **kwargs)
        stages.append("incomplete")
        assert_previous_visible()
        if failure == "write":
            raise OSError("controlled pool write failure")
        result = original_write(path, data, **kwargs)
        assert_previous_visible()
        return result

    def interrupted_replace(path: Path, target: Path) -> Path:
        assert path == pending and target == tracker.path
        assert json.loads(path.read_text()) == expected
        stages.append("complete")
        assert_previous_visible()
        if failure == "replace":
            raise OSError("controlled pool replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "write_text", interrupted_write)
    monkeypatch.setattr(Path, "replace", interrupted_replace)
    if failure:
        with pytest.raises(OSError, match=f"controlled pool {failure} failure"):
            tracker.save(finalized=True)
        assert_previous_visible()
    else:
        tracker.save(finalized=True)
        assert tracker.path.read_text() == json.dumps(expected)
    assert stages == (["incomplete"] if failure == "write" else ["incomplete", "complete"])
    assert not pending.exists()


async def test_actual_pool_capacity_and_return_evidence(
    tmp_path: Path, migrator_engine: AsyncEngine
) -> None:
    engine = create_engine_for(DatabaseRole.API, pool_size=1, max_overflow=1)
    tracker = PoolEvidence(tmp_path / "paper-0-0.pools.json")
    tracker.add(engine, DatabaseRole.API)
    budget = await connection_budget(migrator_engine, [tracker.path], expected_counts=[1])
    assert budget["declared_capacity"] == budget["limit"] == 2
    try:
        async with engine.connect(), engine.connect():
            tracker.save(finalized=True)
            assert not returned_pools([tracker.path], budget)
            assert tracker.entries[0]["peak_checked_out"] == 2
        await engine.dispose()
        # W3 recreates pools during connection churn; evidence must follow the new pool.
        async with engine.connect():
            assert tracker.entries[0]["checked_out"] == 1
        await engine.dispose()
        tracker.finish()
        assert returned_pools([tracker.path], budget)
        # A restarted generation must preserve the exact configuration.
        restart = tmp_path / "paper-0-1.pools.json"
        restart.write_text(tracker.path.read_text())
        assert returned_pools([tracker.path, restart], budget)
        document = json.loads(restart.read_text())
        document["pools"][0]["pool_size"] = 2
        restart.write_text(json.dumps(document))
        assert not returned_pools([tracker.path, restart], budget)
        assert not returned_pools([], budget)
        with pytest.raises(ValueError, match="incomplete"):
            await connection_budget(migrator_engine, [tracker.path], expected_counts=[2])
    finally:
        await engine.dispose()
        tracker.finish()


async def test_cleanup_excludes_only_predeclared_observers_and_detects_a_leak(
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.connect() as connection:
        observers: tuple[int, ...] = tuple(
            (
                await connection.execute(
                    text("SELECT pid FROM pg_stat_activity WHERE datname=current_database()")
                )
            ).scalars()
        )
    engine = create_engine_for(DatabaseRole.API, pool_size=1, max_overflow=0)
    held = await engine.connect()
    try:
        held_pid: int = (await held.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        evidence = {"observer_pids": observers, "held_pid": held_pid}
        result = await cleanup_connections(observer_pids=observers)
        assert result["passed"] is False and len(result["remaining"]) == 1, {
            **evidence,
            "phase": "held",
            "result": result,
        }
        await held.close()
        # Returning to the pool still leaves a physical client until disposal.
        result = await cleanup_connections(observer_pids=observers)
        assert result["passed"] is False, {
            **evidence,
            "phase": "returned_to_pool",
            "result": result,
        }
        await engine.dispose()
        result = await cleanup_connections(observer_pids=observers)
        assert result["passed"] is True, {
            **evidence,
            "phase": "disposed",
            "result": result,
        }
    finally:
        await held.close()
        await engine.dispose()


@pytest.mark.parametrize("name,expected", [("paper-0", 2), ("risk", 4)])
async def test_worker_records_actual_pools_and_restores_factories(
    tmp_path: Path, name: str, expected: int
) -> None:
    import argparse
    import asyncio

    from tests.infra.execution_market import profile_workload as f15
    from tests.infra.risk_limits import profile_workload as workload
    from tiewtrade.services.engine import risk_limit_main

    metrics, stop = tmp_path / f"{name}-0.json", tmp_path / "workers.stop"
    before = (vars(f15)["create_engine_for"], vars(risk_limit_main)["create_engine_for"])
    task = asyncio.create_task(
        workload.worker(argparse.Namespace(worker=name, metrics=metrics, stop=stop))
    )
    pools = metrics.with_suffix(".pools.json")
    try:
        async with asyncio.timeout(5):
            while not pools.exists() or len(json.loads(pools.read_text())["pools"]) < expected:
                if task.done():
                    await task
                    pytest.fail("worker exited without complete inventory")
                await asyncio.sleep(0.01)
        stop.touch()
        assert await asyncio.wait_for(task, 5) == 0
        document = json.loads(pools.read_text())
        assert document["finalized"] and len(document["pools"]) == expected
        assert all(p["checked_out"] == 0 for p in document["pools"])
        assert (
            vars(f15)["create_engine_for"],
            vars(risk_limit_main)["create_engine_for"],
        ) == before
    finally:
        stop.touch()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
