"""OBS-01 opt-in supervision, error priority, ownership and independent failure receipt."""

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from tests.infra.execution_market import profile_publisher_lease_load as load
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.test_publisher_lease_load import options
from tests.infra.execution_market.test_workload_latency import mock_parent


def approved(**changes: Any) -> argparse.Namespace:
    return options(
        phase="W3",
        publisher_fence_observer=True,
        publisher_clock_recovery=True,
        publisher_fence_fail_fast=True,
        **changes,
    )


@pytest.mark.parametrize(
    "change",
    [{"phase": phase} for phase in ("SMOKE", "W1", "W2", "W2_OVERFLOW", "BASELINE")]
    + [
        {"acceptance_profile": "PAPER_INTERNAL20_V2"},
        {"acceptance_profile": None},
        {"publisher_lease_observer": False},
        {"publisher_fence_observer": False},
        {"publisher_clock_recovery": False},
        {"worker_only": True},
        {"diagnostics": True},
        {"failure_timeline": True},
        {"controlled_delay": True},
    ],
)
def test_reject_before_side_effects(change: dict[str, Any]) -> None:
    args = approved()
    vars(args).update(change)
    with pytest.raises(ValueError):
        load.validate_options(args)


def test_default_and_exact_scope() -> None:
    load.validate_options(argparse.Namespace())
    load.validate_options(approved())
    load.validate_options(options())


@pytest.mark.parametrize(
    "profile,phase",
    [
        ("W3", phase)
        for phase in ("ready", "startup", "baseline", "cycles", "fault", "duration", "pre_rebuild")
    ]
    + [("SMOKE", phase) for phase in ("ready", "startup", "baseline", "cycles", "pre_rebuild")],
)
async def test_real_parent_stops_before_next_phase_and_disposes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, profile: str
) -> None:
    # Only phase sequencing is simulated; existing real-DB tests prove SQL/rollback/locks.
    args = mock_parent(monkeypatch, tmp_path, phase=profile, case="fast")
    failure: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    next_phase = workload.verify
    original_start = workload.start_worker_processes
    original_cycles = workload.run_scheduled_cycles
    original_stop = workload.stop_worker_processes
    original_sleep = asyncio.sleep

    async def lose(*a: Any, **kw: Any) -> None:
        if not failure.done():
            failure.set_result(None)
        await asyncio.Event().wait()

    if phase == "ready":
        monkeypatch.setattr(workload, "wait_publisher_ready", lose)
    elif phase == "startup":

        async def start(*a: Any, **kw: Any) -> Any:
            result = await original_start(*a, **kw)
            failure.set_result(None)
            return result

        monkeypatch.setattr(workload, "start_worker_processes", start)
    elif phase == "baseline":
        monkeypatch.setattr(workload, "seed_baseline", lose)
    elif phase == "cycles":
        monkeypatch.setattr(workload, "run_scheduled_cycles", lose)
    elif phase == "fault":
        reached = asyncio.Event()

        async def cycles(*a: Any, **kw: Any) -> float:
            result = await original_cycles(*a, **kw)
            reached.set()
            return result

        async def faults(*a: Any, **kw: Any) -> None:
            await reached.wait()
            await lose()

        monkeypatch.setattr(workload, "run_scheduled_cycles", cycles)
        monkeypatch.setattr(workload, "run_fault_schedule", faults)
    elif phase == "duration":

        async def sleep(seconds: float) -> None:
            if seconds > 1:
                await lose()
            await original_sleep(seconds)

        monkeypatch.setattr(asyncio, "sleep", sleep)
    else:

        async def stop(*a: Any, **kw: Any) -> None:
            await original_stop(*a, **kw)
            failure.set_result(None)

        monkeypatch.setattr(workload, "stop_worker_processes", stop)
    with pytest.raises(RuntimeError, match="F17_FENCE_OBSERVER_EVIDENCE_INCOMPLETE"):
        await workload._run(args, observer_failure=failure)
    assert isinstance(next_phase, AsyncMock)
    next_phase.assert_not_awaited()
    database: Any = cast(Any, workload).create_engine_for(None)
    database.dispose.assert_awaited()
    assert not (args.output / "result.json").exists()
    assert json.loads((args.output / "failure.json").read_text())["error_type"] == "RuntimeError"


@pytest.mark.parametrize("which", ["operation", "publisher", "check"])
async def test_simultaneous_real_error_precedes_observer(which: str) -> None:
    error = ValueError("original")
    failure = asyncio.get_running_loop().create_future()
    failure.set_result(None)

    async def result() -> None:
        if which == "operation":
            raise error

    async def producer() -> None:
        if which == "publisher":
            raise error
        await asyncio.Event().wait()

    async def check() -> None:
        if which == "check":
            raise error
        await asyncio.Event().wait()

    operation, publisher, observation = [
        asyncio.create_task(f()) for f in (result, producer, check)
    ]
    await asyncio.sleep(0)
    try:
        with pytest.raises(ValueError) as caught:
            await workload.with_publisher(
                operation, publisher, checks=(observation,), failure=failure
            )
        assert caught.value is error
    finally:
        for task in (publisher, observation):
            task.cancel()
        await asyncio.gather(publisher, observation, return_exceptions=True)


async def test_repeated_cancellation_joins_abandoned_operation() -> None:
    failure = asyncio.get_running_loop().create_future()
    started, cleaning, release, joined = [asyncio.Event() for _ in range(4)]

    async def operation() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            joined.set()

    supervisor = asyncio.create_task(workload.with_publisher(operation(), None, failure=failure))
    await started.wait()
    failure.set_result(None)
    await cleaning.wait()
    supervisor.cancel()
    await asyncio.sleep(0)
    supervisor.cancel()
    release.set()
    with pytest.raises(RuntimeError, match="EVIDENCE_INCOMPLETE"):
        await supervisor
    assert joined.is_set()


@pytest.mark.parametrize("cancel_spawn", [False, True])
async def test_partial_worker_startup_preserves_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_spawn: bool
) -> None:
    child = SimpleNamespace(pid=907001, returncode=None)
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def spawn(*a: Any, **kw: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            if cancel_spawn:
                started.set()
                await release.wait()
            return child
        raise OSError("spawn failed")

    cleanup = AsyncMock()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(workload, "stop_worker_processes", cleanup)
    task = asyncio.create_task(workload.start_worker_processes(2, tmp_path, observed_startup=True))
    if cancel_spawn:
        await started.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        release.set()
    with pytest.raises(asyncio.CancelledError if cancel_spawn else OSError):
        await task
    cleanup.assert_awaited_once_with([child], tmp_path / "worker.stop")
    assert calls == (1 if cancel_spawn else 2)


@pytest.mark.parametrize("normal", [False, True])
async def test_monitor_completion_signals_once_and_expected_close_does_not(
    tmp_path: Path, normal: bool
) -> None:
    observer = load.LoadLeaseObserver(
        tmp_path, {"write_failed": False}, fence_observer=True, fence_fail_fast=True
    )
    stop = asyncio.Event()
    if normal:
        stop.set()
    observer.fence = SimpleNamespace(stop=stop, errors={} if normal else {"TimeoutError": 1})

    async def sampler() -> None:
        return None

    task = asyncio.create_task(sampler())
    await task
    observer.sampler_finished(task)
    observer.sampler_finished(task)
    assert observer.failure is not None and observer.failure.done() == (not normal)
    if not normal:
        assert observer.failure.result() is None
        assert observer.failure_reason == "SAMPLER_EVIDENCE_LOST"
    else:
        observer.failure.cancel()


@pytest.mark.parametrize("io_failure", [False, True])
@pytest.mark.parametrize("status", ["PASSED", "FAILED"])
async def test_failure_receipt_independent_of_readiness_and_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, io_failure: bool, status: str
) -> None:
    observer = load.LoadLeaseObserver(
        tmp_path, {"write_failed": True}, fence_observer=True, fence_fail_fast=True
    )
    envelope: dict[str, Any] = {
        "capture_phase": "activity",
        "db_now": None,
        "activity": [],
        "locks": [],
    }
    observer.fence = SimpleNamespace(
        errors={"TimeoutError": 1},
        report=lambda: {"failed_observation": envelope, "task_joined": True},
    )
    observer.signal_failure("SAMPLER_EVIDENCE_LOST")
    workload.save(tmp_path / "result.json", {"status": status})
    original_save = workload.save

    def save(path: Path, value: Any) -> None:
        if path.name == "publisher-fence-failure.json" and io_failure:
            raise OSError("disk failure")
        original_save(path, value)

    monkeypatch.setattr(workload, "save", save)
    primary = RuntimeError("workload primary")
    with pytest.raises(RuntimeError) as caught, observer.observe():
        raise primary
    assert caught.value is primary
    assert json.loads((tmp_path / "result.json").read_text())["status"] == (
        "FAILED" if status == "FAILED" else "INCOMPLETE"
    )
    if not io_failure:
        receipt = json.loads((tmp_path / "publisher-fence-failure.json").read_text())
        assert receipt["fence_observation"]["failed_observation"] == envelope
        assert receipt["status"] == "INCOMPLETE"
    assert any("evidence failed" in note for note in primary.__notes__)


async def test_owned_finalizer_retains_primary_and_joins_repeated_cancel() -> None:
    started, release, joined = [asyncio.Event() for _ in range(3)]
    primary = ValueError("original")

    async def close() -> None:
        started.set()
        await release.wait()
        joined.set()
        raise OSError("dispose")

    task = asyncio.create_task(workload.finish_observed_cleanup(close(), primary))
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    await task
    assert joined.is_set()
    assert any("OSError" in note for note in primary.__notes__)


@pytest.mark.parametrize("lose_evidence", [False, True])
async def test_tail_supervision_allows_intentional_publisher_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lose_evidence: bool
) -> None:
    failure = asyncio.get_running_loop().create_future()
    stop, joined = asyncio.Event(), asyncio.Event()

    async def producer() -> None:
        try:
            await stop.wait()
        finally:
            joined.set()

    async def recovery(*a: Any, **kw: Any) -> None:
        if lose_evidence:
            failure.set_result(None)
            await asyncio.Event().wait()
        stop.set()

    # Exercise real live-tail supervision; the success case tests its outer normal stop boundary.
    monkeypatch.setattr(workload, "wait_for_input_recovery", recovery)
    publisher = asyncio.create_task(producer())
    try:
        if lose_evidence:
            with pytest.raises(RuntimeError, match="EVIDENCE_INCOMPLETE"):
                await workload.with_publisher(
                    workload.drain_final_tail(
                        cast(Any, None),
                        cast(Any, None),
                        [],
                        publisher,
                        stop,
                        {"last_input_id": 1},
                        tmp_path / "tail.json",
                    ),
                    None,
                    failure=failure,
                )
        else:

            async def tail() -> int:
                stop.set()
                await publisher
                return 42

            assert await workload.with_publisher(tail(), None, failure=failure) == 42
    finally:
        publisher.cancel()
        await asyncio.gather(publisher, return_exceptions=True)
    assert joined.is_set()


@pytest.mark.usefixtures("internal_database")
async def test_real_pg_sampler_loss_stops_transaction_and_releases_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from time import monotonic

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncConnection

    from tests.infra.execution_market.profile_publisher_fence import FenceObservation
    from tests.infra.execution_market.profile_publisher_lease import LeaseTrace
    from tiewtrade.infra.db import DatabaseRole, create_engine_for
    from tiewtrade.infra.db.session import market_data_session

    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    observer = load.LoadLeaseObserver(
        tmp_path, {"write_failed": False}, fence_observer=True, fence_fail_fast=True
    )
    entered = asyncio.Event()
    identity: dict[str, Any] = {}

    async def transaction() -> None:
        async with market_data_session(engine) as session:
            identity["pid"] = (await session.execute("SELECT pg_backend_pid()")).scalar_one()
            identity["xid"] = (await session.execute("SELECT txid_current()")).scalar_one()
            await session.execute("SELECT risk_publication_fence()")
            entered.set()
            await asyncio.Event().wait()

    operation = asyncio.create_task(transaction())
    await asyncio.wait_for(entered.wait(), 3)
    trace = SimpleNamespace(
        statements=[
            {"backend_pid": identity["pid"], "stage": "price_renew", "started": monotonic() - 2}
        ],
        publication=SimpleNamespace(tick=7),
    )
    fence = FenceObservation(lambda: cast(LeaseTrace, trace))
    observer.fence = fence
    execute = AsyncConnection.execute

    async def delayed_activity(connection: Any, sql: Any, *a: Any, **kw: Any) -> Any:
        if "pg_stat_activity" in str(sql):
            await execute(connection, text("SELECT pg_sleep(0.6)"))
        return await execute(connection, sql, *a, **kw)

    monkeypatch.setattr(AsyncConnection, "execute", delayed_activity)
    try:
        fence.start()
        assert fence.task is not None
        fence.task.add_done_callback(observer.sampler_finished)
        with pytest.raises(RuntimeError, match="EVIDENCE_INCOMPLETE"):
            async with asyncio.timeout(4):
                await workload.with_publisher(operation, None, failure=observer.failure)
        assert operation.done() and operation.cancelled()
        await fence.close()
        observer.flush_failure()
        receipt = json.loads((tmp_path / "publisher-fence-failure.json").read_text())
        assert receipt["fence_observation"]["task_joined"]
        assert receipt["fence_observation"]["failed_observation"]["capture_phase"] == "activity"
        # An independent real connection proves rollback and advisory-lock release.
        async with engine.connect() as connection:
            state: str | None = (
                await connection.execute(
                    text("SELECT pg_xact_status(CAST(:xid AS xid8))"), {"xid": identity["xid"]}
                )
            ).scalar_one()
            locks: int = (
                await connection.execute(
                    text("SELECT count(*) FROM pg_locks WHERE pid=:pid AND locktype='advisory'"),
                    {"pid": identity["pid"]},
                )
            ).scalar_one()
        assert state == "aborted" and locks == 0
        assert engine.pool.checkedout() == 0  # type: ignore[attr-defined]
    finally:
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        await fence.close()
        await engine.dispose()


async def test_signal_already_available_does_not_begin_another_operation() -> None:
    failure = asyncio.get_running_loop().create_future()
    failure.set_result(None)
    called = False

    async def operation() -> None:
        nonlocal called
        called = True

    with pytest.raises(RuntimeError, match="EVIDENCE_INCOMPLETE"):
        await workload.with_publisher(operation(), None, failure=failure)
    assert not called


async def test_callback_loss_cannot_leave_passed_even_when_normal_flush_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observer = load.LoadLeaseObserver(
        tmp_path, {"write_failed": False}, fence_observer=True, fence_fail_fast=True
    )
    observer.signal_failure("SAMPLER_EVIDENCE_LOST")
    workload.save(tmp_path / "result.json", {"status": "PASSED"})
    monkeypatch.setattr(observer, "flush", lambda: None)
    with pytest.raises(ValueError, match="fail-fast evidence incomplete"), observer.observe():
        pass
    assert json.loads((tmp_path / "result.json").read_text())["status"] == "INCOMPLETE"


@pytest.mark.parametrize("cancel_publisher", [False, True])
async def test_startup_preserves_completed_publisher_failure_before_observer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_publisher: bool
) -> None:
    args = mock_parent(monkeypatch, tmp_path, phase="W3", case="fast")
    failure: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    released, raised = asyncio.Event(), asyncio.Event()
    primary: BaseException
    if cancel_publisher:
        primary = asyncio.CancelledError("source cancelled")
    else:
        primary = ValueError("source failed")
    original_start = workload.start_worker_processes
    baseline = AsyncMock()
    monkeypatch.setattr(workload, "seed_baseline", baseline)

    async def publisher(source: Any, stop: asyncio.Event, stats: dict[str, Any], **kw: Any) -> None:
        stats["published"] = 2
        await released.wait()
        raised.set()
        raise primary

    async def start(*a: Any, **kw: Any) -> Any:
        result = await original_start(*a, **kw)
        released.set()
        await raised.wait()
        failure.set_result(None)
        return result

    monkeypatch.setattr(workload, "market_publisher", publisher)
    monkeypatch.setattr(workload, "start_worker_processes", start)
    with pytest.raises(type(primary)) as caught:
        await workload._run(args, observer_failure=failure)
    assert caught.value is primary
    baseline.assert_not_awaited()
    assert isinstance(workload.verify, AsyncMock)
    workload.verify.assert_not_awaited()
    assert (
        json.loads((args.output / "failure.json").read_text())["error_type"]
        == type(primary).__name__
    )


@pytest.mark.parametrize("failed_file", ["receipt", "summary", "both"])
@pytest.mark.parametrize("has_primary", [False, True])
async def test_finalizers_attempt_both_files_and_preserve_first_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_file: str, has_primary: bool
) -> None:
    observer = load.LoadLeaseObserver(
        tmp_path, {"write_failed": False}, fence_observer=True, fence_fail_fast=True
    )
    envelope = {"capture_phase": "activity", "task_joined": True}
    observer.fence = SimpleNamespace(report=lambda: envelope)
    observer.signal_failure("SAMPLER_EVIDENCE_LOST")
    workload.save(tmp_path / "result.json", {"status": "PASSED"})
    receipt_error = OSError("receipt unavailable")
    summary_error = ValueError("summary invalid")
    primary = RuntimeError("workload primary")
    original_save = workload.save
    calls = []

    def save(path: Path, value: Any) -> None:
        if path.name == "publisher-fence-failure.json":
            calls.append("receipt")
            if failed_file in {"receipt", "both"}:
                raise receipt_error
        original_save(path, value)

    def flush() -> None:
        calls.append("summary")
        if failed_file in {"summary", "both"}:
            raise summary_error
        original_save(tmp_path / "publisher-lease.json", {"fence_observation": envelope})

    monkeypatch.setattr(workload, "save", save)
    monkeypatch.setattr(observer, "flush", flush)
    expected: BaseException = receipt_error if failed_file in {"receipt", "both"} else summary_error
    if has_primary:
        expected = primary
    with pytest.raises(type(expected)) as caught, observer.observe():
        if has_primary:
            raise primary
    assert caught.value is expected
    assert calls == ["receipt", "summary"]
    retained_file = {
        "receipt": "publisher-lease.json",
        "summary": "publisher-fence-failure.json",
    }.get(failed_file)
    if retained_file is not None:
        retained = json.loads((tmp_path / retained_file).read_text())
        assert retained["fence_observation"] == envelope
    if failed_file == "both":
        assert any("ValueError" in note for note in receipt_error.__notes__)
    assert json.loads((tmp_path / "result.json").read_text())["status"] == "INCOMPLETE"
