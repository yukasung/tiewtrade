"""Actual pool inventory, return evidence and post-disposal connection checks."""

import json
from pathlib import Path

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
        result = await cleanup_connections(observer_pids=observers)
        assert result["passed"] is False and len(result["remaining"]) == 1
        await held.close()
        # Returning to the pool still leaves a physical client until disposal.
        result = await cleanup_connections(observer_pids=observers)
        assert result["passed"] is False
        await engine.dispose()
        assert (await cleanup_connections(observer_pids=observers))["passed"] is True
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
