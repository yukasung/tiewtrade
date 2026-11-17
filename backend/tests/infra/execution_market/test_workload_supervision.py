"""The workload must preserve the first producer failure and join abandoned work."""

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.infra.execution_market.profile_workload import with_publisher


@pytest.mark.parametrize("fails", [True, False])
async def test_publisher_exit_stops_and_joins_workload(fails: bool) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    joined = asyncio.Event()
    failure = RuntimeError("injected publisher failure")

    async def publisher() -> None:
        await release.wait()
        if fails:
            raise failure

    async def workload() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    producer = asyncio.create_task(publisher())
    task = asyncio.create_task(with_publisher(workload(), producer))
    await started.wait()
    release.set()
    async with asyncio.timeout(1):
        with pytest.raises(RuntimeError) as caught:
            await task
    assert joined.is_set()
    if fails:
        assert caught.value is failure
    else:
        assert str(caught.value) == "F15_WORKLOAD_PUBLISHER_STOPPED_UNEXPECTEDLY"


async def test_completed_operation_keeps_publisher_alive() -> None:
    async def workload() -> int:
        return 42

    async def publisher() -> None:
        await asyncio.Event().wait()

    monitored = asyncio.create_task(publisher())
    try:
        assert await with_publisher(workload(), monitored) == 42
        assert not monitored.done()
    finally:
        monitored.cancel()
        await asyncio.gather(monitored, return_exceptions=True)


async def test_external_cancel_joins_operation_without_canceling_publisher() -> None:
    started = asyncio.Event()
    joined = asyncio.Event()

    async def publisher() -> None:
        await asyncio.Event().wait()

    async def workload() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    producer = asyncio.create_task(publisher())
    task = asyncio.create_task(with_publisher(workload(), producer))
    try:
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert joined.is_set() and not producer.done()
    finally:
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)


def test_mac_resource_sample_preserves_cpu_seconds_and_rss_bytes() -> None:
    from tests.infra.execution_market.profile_workload import mac_process_sample

    assert mac_process_sample(" 123 01:02.50 2048\n456 1-02:03:04.00 1024\n", [123, 456]) == [
        {"Id": 123, "CPU": 62.5, "WorkingSet64": 2097152},
        {"Id": 456, "CPU": 93784.0, "WorkingSet64": 1048576},
    ]
    with pytest.raises(RuntimeError, match="INCOMPLETE"):
        mac_process_sample("123 00:00.01 1\n", [123, 456])


@pytest.mark.parametrize("existing", [None, "42"])
def test_interrupted_pid_publication_never_exposes_partial_value(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch, existing: str | None
) -> None:
    import os
    from pathlib import Path

    from tests.infra.execution_market.profile_workload import publish_runtime_pid

    assert isinstance(tmp_path, Path)
    metrics = tmp_path / "worker.json"
    watched = metrics.with_suffix(".pid")
    if existing is not None:
        watched.write_text(existing)
    original = Path.write_text

    def interrupted(path: Path, data: str, **kwargs: object) -> int:
        original(path, "", encoding="ascii")
        raise OSError("interrupted PID publication")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_text", interrupted)
        with pytest.raises(OSError, match="interrupted"):
            publish_runtime_pid(metrics)
    if existing is None:
        assert not watched.exists()
    else:
        assert watched.read_text() == existing
    publish_runtime_pid(metrics)
    assert int(watched.read_text()) == os.getpid()


@pytest.mark.parametrize("transient", ["missing", "empty"])
async def test_runtime_pid_wait_handles_delayed_file_visibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transient: str
) -> None:
    from tests.infra.execution_market.profile_workload import wait_runtime_pid

    metrics = tmp_path / "worker.json"
    watched = metrics.with_suffix(".pid")
    watched.write_text("4242")
    process = Mock(spec=asyncio.subprocess.Process)
    process.returncode = None
    original = Path.read_text
    first = True

    def delayed(path: Path, **kwargs: object) -> str:
        nonlocal first
        if path == watched and first:
            first = False
            if transient == "missing":
                raise FileNotFoundError("metadata visible before readable file")
            return ""
        return original(path)

    monkeypatch.setattr(Path, "read_text", delayed)
    assert await wait_runtime_pid(process, metrics, timeout_seconds=1) == 4242


@pytest.mark.parametrize("pid", [0, -1])
async def test_runtime_pid_wait_rejects_invalid_process_identity(tmp_path: Path, pid: int) -> None:
    from tests.infra.execution_market.profile_workload import wait_runtime_pid

    metrics = tmp_path / "worker.json"
    metrics.with_suffix(".pid").write_text(str(pid))
    process = Mock(spec=asyncio.subprocess.Process)
    process.returncode = None
    with pytest.raises(RuntimeError, match="PID_INVALID"):
        await wait_runtime_pid(process, metrics)


async def test_dead_worker_cannot_reuse_a_preexisting_runtime_pid(tmp_path: Path) -> None:
    from tests.infra.execution_market.profile_workload import wait_runtime_pid

    metrics = tmp_path / "worker.json"
    metrics.with_suffix(".pid").write_text("4242")
    process = Mock(spec=asyncio.subprocess.Process)
    process.returncode = 1
    with pytest.raises(RuntimeError, match="EXITED_BEFORE_READY"):
        await wait_runtime_pid(process, metrics)


@pytest.mark.parametrize("fails", [True, False])
async def test_background_check_failure_joins_workload_but_success_keeps_it_running(
    fails: bool,
) -> None:
    started, release, joined = asyncio.Event(), asyncio.Event(), asyncio.Event()
    failure = RuntimeError("snapshot failed")

    async def check() -> None:
        await started.wait()
        if fails:
            raise failure

    async def workload() -> int:
        started.set()
        try:
            await release.wait()
            return 42
        finally:
            joined.set()

    async def publisher() -> None:
        await asyncio.Event().wait()

    producer = asyncio.create_task(publisher())
    observation = asyncio.create_task(check())
    task = asyncio.create_task(with_publisher(workload(), producer, checks=(observation,)))
    try:
        await asyncio.gather(observation, return_exceptions=True)
        if fails:
            with pytest.raises(RuntimeError) as caught:
                await task
            assert caught.value is failure and joined.is_set()
        else:
            assert not task.done()
            release.set()
            assert await task == 42
        assert not producer.done()
    finally:
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)


@pytest.mark.parametrize("scheduled", [False, True])
async def test_group_cancel_waits_for_child_cleanup_without_second_cancel(
    monkeypatch: pytest.MonkeyPatch, scheduled: bool
) -> None:
    from typing import Any
    from uuid import uuid4

    from tests.infra.execution_market import profile_workload as workload

    entered = [asyncio.Event(), asyncio.Event()]
    cleaning, release, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    repeated: list[int] = []

    async def operation(index: int) -> None:
        entered[index].set()
        try:
            await asyncio.Event().wait()
        finally:
            if index == 1:
                cleaning.set()
                try:
                    await release.wait()
                    closed.set()
                except asyncio.CancelledError:
                    repeated.append(index)
                    raise

    async def cycle(engine: Any, owner: Any, *args: Any, **kwargs: Any) -> None:
        await operation(owner)

    monkeypatch.setattr(workload, "cycle", cycle)
    owners: list[Any] = [0, 1]
    operation_group = (
        workload.run_scheduled_cycles(
            Mock(),
            owners,
            uuid4(),
            1,
            100000,
            workload.Counters(),
            [],
        )
        if scheduled
        else workload.bounded_map([0, 1], operation, join_on_error=True)
    )
    group = asyncio.create_task(operation_group)
    try:
        await asyncio.wait_for(asyncio.gather(*(e.wait() for e in entered)), 1)
        group.cancel()
        await asyncio.wait_for(cleaning.wait(), 1)
        # Let sibling completion and the parent's finally block run before release.
        for _ in range(10):
            await asyncio.sleep(0)
        assert not repeated
        assert not group.done()
    finally:
        release.set()
        await asyncio.gather(group, return_exceptions=True)
    assert closed.is_set() and group.cancelled()


@pytest.mark.parametrize("scheduled", [False, True])
async def test_real_group_cutoff_returns_connection_before_dispose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scheduled: bool
) -> None:
    import json
    from typing import Any, cast
    from uuid import uuid4

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncConnection
    from sqlalchemy.pool import QueuePool

    from tests.infra.execution_market import profile_workload as workload
    from tests.infra.execution_market.profile_owned_pools import OwnedPools
    from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session

    ready = [asyncio.Event(), asyncio.Event()]
    closing, release = asyncio.Event(), asyncio.Event()
    original_close = AsyncConnection.close
    report = tmp_path / "pools.json"
    with OwnedPools(report, [("ENGINE", 5, 10)]):
        engine = create_engine_for(DatabaseRole.ENGINE)
        pids: list[int] = []

        async def delayed_close(connection: AsyncConnection) -> None:
            if connection.engine is engine and not release.is_set():
                closing.set()
                await release.wait()
            await original_close(connection)

        monkeypatch.setattr(AsyncConnection, "close", delayed_close)

        async def operation(index: int) -> None:
            if index == 0:
                ready[0].set()
                await asyncio.Event().wait()
            else:
                async with user_session(engine, uuid4(), role=DatabaseRole.ENGINE) as session:
                    pids.append((await session.execute("SELECT pg_backend_pid()")).scalar_one())
                    await session.execute("SELECT pg_advisory_xact_lock(78123597)")
                    ready[1].set()
                    await asyncio.Event().wait()

        async def cycle(engine: Any, owner: Any, *args: Any, **kwargs: Any) -> None:
            await operation(owner)

        monkeypatch.setattr(workload, "cycle", cycle)
        owners: list[Any] = [0, 1]
        operation_group = (
            workload.run_scheduled_cycles(
                engine,
                owners,
                uuid4(),
                1,
                100000,
                workload.Counters(),
                [],
            )
            if scheduled
            else workload.bounded_map([0, 1], operation, join_on_error=True)
        )
        group = asyncio.create_task(operation_group)
        try:
            async with asyncio.timeout(5):
                await asyncio.gather(*(e.wait() for e in ready))
                group.cancel()
                await closing.wait()
                for _ in range(10):
                    await asyncio.sleep(0)
                assert not group.done()
                group.cancel()  # An external second cancel must not abandon the owned join.
                await asyncio.sleep(0)
                assert not group.done()
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await group
            assert cast(QueuePool, engine.pool).checkedout() == 0
            async with engine.connect() as connection:
                assert (
                    await connection.execute(
                        text(
                            "SELECT count(*) FROM pg_locks WHERE pid=:pid AND locktype='advisory'"
                        ),
                        {"pid": pids[0]},
                    )
                ).scalar_one() == 0
        finally:
            release.set()
            if not group.done():
                group.cancel()
            await asyncio.gather(group, return_exceptions=True)
            await engine.dispose()
    evidence = json.loads(report.read_text())
    assert evidence["passed"]
    assert evidence["pools"][0]["final_disposal_checked_out"] == 0


async def test_join_owned_children_retains_primary_and_cleanup_errors() -> None:
    from tests.infra.execution_market.profile_workload import join_owned_tasks

    primary = ValueError("primary")
    secondary = RuntimeError("private detail")

    async def fail() -> None:
        raise secondary

    child = asyncio.create_task(fail())
    await asyncio.gather(child, return_exceptions=True)
    await join_owned_tasks([child], primary)
    assert primary.__notes__ == ["owned child cleanup failed: RuntimeError"]
    with pytest.raises(RuntimeError) as caught:
        await join_owned_tasks([child], None)
    assert caught.value is secondary
