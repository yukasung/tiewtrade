"""Recovery workers must connect to the restored DB, leaving ambient source config intact."""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import QueuePool

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_internal_restore as recovery
from tests.infra.execution_market import profile_restore as legacy_restore
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.conftest import InternalDatabaseFactory
from tiewtrade.infra.db import DatabaseRole, create_engine_for


@pytest_asyncio.fixture
async def target_engines(
    internal_database: None, internal_database_factory: InternalDatabaseFactory
) -> AsyncIterator[dict[DatabaseRole, AsyncEngine]]:
    internal.guard_database(dict(os.environ))
    async with internal_database_factory() as urls:
        engines = {
            role: create_async_engine(urls[role.url_variable], hide_parameters=True)
            for role in (DatabaseRole.ENGINE, DatabaseRole.ENGINE_SCAN)
        }
        try:
            yield engines
        finally:
            for engine in engines.values():
                await engine.dispose()


@pytest.mark.parametrize("outcome", ["stop", "error", "cancel"])
async def test_worker_factory_routes_both_roles_and_preserves_source_configuration(
    target_engines: dict[DatabaseRole, AsyncEngine],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    before = {role: os.environ[role.url_variable] for role in target_engines}
    source = internal.guard_database(dict(os.environ))
    target = target_engines[DatabaseRole.ENGINE].url.database
    assert source != target
    factory = recovery.restored_worker_factory(target_engines)
    parent_pools = {role: engine.pool for role, engine in target_engines.items()}
    owned: dict[DatabaseRole, tuple[AsyncEngine, QueuePool]] = {}
    seen: list[str] = []
    ready = asyncio.Event()
    stop = tmp_path / "worker.stop"
    failure = RuntimeError("controlled round failure")

    def assert_source_config() -> None:
        if any(os.environ[role.url_variable] != value for role, value in before.items()):
            raise AssertionError("ambient source configuration changed")

    def create(role: DatabaseRole) -> AsyncEngine:
        engine = factory(role)
        assert_source_config()
        assert engine is not target_engines[role]
        owned[role] = (engine, cast(QueuePool, engine.pool))
        return engine

    async def round_trip(**options: Any) -> None:
        assert_source_config()
        for key in ("engine", "scan_engine"):
            async with options[key].connect() as connection:
                seen.append(await connection.scalar(text("SELECT current_database()")))
        ready.set()
        if outcome == "error":
            raise failure
        if outcome == "cancel":
            await asyncio.Event().wait()
        stop.touch()

    monkeypatch.setattr(workload, "run_paper_order_round", round_trip)
    task = asyncio.create_task(
        workload.run_worker_process(
            "restore-routing",
            stop,
            tmp_path / "worker.json",
            engine_factory=create,
        )
    )
    if outcome == "cancel":
        await asyncio.wait_for(ready.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif outcome == "error":
        with pytest.raises(RuntimeError) as caught:
            await task
        assert caught.value is failure
    else:
        await task
    assert seen == [target, target]
    assert_source_config()
    for role, (_, pool) in owned.items():
        assert pool.checkedout() == pool.checkedin() == 0
        assert target_engines[role].pool is parent_pools[role]
        probe = create_engine_for(role)
        try:
            default = cast(QueuePool, probe.pool)
            assert (pool.size(), pool._max_overflow, pool.timeout()) == (
                default.size(),
                default._max_overflow,
                default.timeout(),
            )
        finally:
            await probe.dispose()


async def test_factory_failure_restores_environment_and_preserves_error(
    target_engines: dict[DatabaseRole, AsyncEngine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = dict(os.environ)
    factory = recovery.restored_worker_factory(target_engines)
    failure = RuntimeError("controlled constructor failure")
    monkeypatch.setattr(recovery, "create_engine_for", Mock(side_effect=failure))
    with pytest.raises(RuntimeError) as caught:
        factory(DatabaseRole.ENGINE)
    assert caught.value is failure
    if dict(os.environ) != before:
        raise AssertionError("factory left environment changed")


@pytest.mark.parametrize("failed", [False, True])
async def test_extended_digest_restores_table_scope(
    monkeypatch: pytest.MonkeyPatch,
    failed: bool,
) -> None:
    original = legacy_restore.PAPER_TABLES
    observed = []

    async def digest(engine: Any) -> dict[str, Any]:
        observed.append(legacy_restore.PAPER_TABLES)
        if failed:
            raise RuntimeError("controlled digest failure")
        return {}

    monkeypatch.setattr(legacy_restore, "database_digest", AsyncMock(side_effect=digest))
    if failed:
        with pytest.raises(RuntimeError):
            await recovery.integrated_digest(cast(AsyncEngine, object()))
    else:
        assert await recovery.integrated_digest(cast(AsyncEngine, object())) == {}
    assert observed == [(*original, *recovery.TABLES)]
    assert legacy_restore.PAPER_TABLES is original
