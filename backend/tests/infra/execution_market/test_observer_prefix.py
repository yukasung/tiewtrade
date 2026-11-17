"""OBS-05 cutoff priority, partial grades, scope and schedule ownership."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.infra.execution_market import profile_internal as internal
from tests.infra.execution_market import profile_observer_prefix as prefix
from tests.infra.execution_market import profile_publisher_lease_load as load
from tests.infra.execution_market import profile_workload as workload
from tests.infra.execution_market.profile_observer_scheduled import ScheduledObservation
from tests.infra.execution_market.test_observer_scheduled import subject as subject
from tests.infra.execution_market.test_observer_short_load import approved


def options(**changes: Any) -> Any:
    values = {
        "phase": "W3",
        "publisher_clock_recovery": True,
        "observer_scheduled_samples": True,
        "observer_w3_prefix": True,
    }
    values.update(changes)
    return approved(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"phase": "SMOKE"},
        {"phase": "W1"},
        {"acceptance_profile": "other"},
        {"publisher_clock_recovery": False},
        {"publisher_fence_timing": False},
        {"publisher_lease_observer": False},
        {"publisher_fence_observer": False},
        {"publisher_fence_fail_fast": False},
        {"observer_scheduled_samples": False},
        {"worker_only": True},
        {"diagnostics": True},
        {"failure_timeline": True},
        {"controlled_delay": True},
    ],
)
def test_exact_scope(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        load.validate_options(options(**changes))


def test_valid_prefix_and_unchanged_smoke() -> None:
    load.validate_options(options())
    load.validate_options(approved(observer_scheduled_samples=True))
    with pytest.raises(ValueError):
        load.validate_options(options(observer_w3_prefix=False))


async def test_explicit_schedule(subject: ScheduledObservation) -> None:
    longer = ScheduledObservation(w3_prefix=True)
    assert longer.offsets == tuple(range(30, 2400, 60))
    assert len(longer.offsets) == 40
    assert longer.window_seconds == 2400 and longer.slot_seconds == 60
    assert subject.offsets == tuple(range(15, 300, 30))
    await longer.close()
    await subject.close()


async def finished() -> asyncio.Task[None]:
    task = asyncio.create_task(asyncio.sleep(0))
    await task
    return task


async def test_cutoff_cancels_and_joins_operation() -> None:
    entered, released = asyncio.Event(), asyncio.Event()

    async def operation() -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    task = asyncio.create_task(operation())
    await entered.wait()
    timer = await finished()
    with pytest.raises(prefix.PrefixCutoffError):
        await workload.with_publisher(task, None, cutoff=timer)
    assert task.done() and released.is_set()


@pytest.mark.parametrize("source", ["operation", "publisher", "check", "cancel_cleanup"])
async def test_real_error_wins_cutoff(source: str) -> None:
    entered = asyncio.Event()
    error = RuntimeError("original failure")

    async def fail() -> None:
        raise error

    async def pending() -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            if source == "cancel_cleanup":
                raise error

    operation = asyncio.create_task(fail() if source == "operation" else pending())
    publisher = asyncio.create_task(fail()) if source == "publisher" else None
    checks = (asyncio.create_task(fail()),) if source == "check" else ()
    timer = await finished()
    with pytest.raises(RuntimeError) as caught:
        await workload.with_publisher(operation, publisher, checks=checks, cutoff=timer)
    assert caught.value is error
    assert operation.done()


async def test_evidence_failure_wins_cutoff() -> None:
    failure = asyncio.get_running_loop().create_future()
    failure.set_result(None)
    timer = await finished()
    with pytest.raises(RuntimeError, match="F17_FENCE_OBSERVER_EVIDENCE_INCOMPLETE"):
        await workload.with_publisher(asyncio.sleep(10), None, failure=failure, cutoff=timer)


async def test_timer_cancellation_is_not_planned() -> None:
    timer = asyncio.create_task(asyncio.sleep(100))
    timer.cancel()
    await asyncio.gather(timer, return_exceptions=True)
    with pytest.raises(asyncio.CancelledError):
        await workload.with_publisher(asyncio.sleep(100), None, cutoff=timer)


async def test_no_fault_after_cutoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(workload, "monotonic", lambda: 3601)
    restart = AsyncMock()
    gate = workload.FaultGate()
    observations: list[dict[str, object]] = []
    await workload.run_fault_schedule(
        [workload.FaultEvent(3600, 30, "WORKER_RESTART")],
        gate,
        redis_container="unused",
        restart_workers=restart,
        churn_connections=AsyncMock(),
        observations=observations,
        prefix_started=0,
    )
    restart.assert_not_awaited()
    assert not observations


def receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    result = {
        "stop_reason": "PLANNED_PREFIX_CUTOFF",
        "elapsed_seconds": 2400,
        "fault_observations": [
            {"kind": "WORKER_RESTART", "status": "RECOVERED", "scheduled_offset_seconds": 1800}
        ],
        "pool_contract": {"passed": True},
    }
    lease = {
        "scheduled_observation": {"status": "RECORDED", "expected_samples": 40},
        "independent_failure_witness": {"cursor": 1},
        "fence_observation": {"errors": {}, "task_joined": True},
    }
    return result, lease


@pytest.mark.parametrize(
    "missing", ["cutoff", "duration", "fault", "pool", "scheduled", "witness", "natural"]
)
def test_incomplete_evidence_cannot_be_complete(missing: str) -> None:
    result, lease = receipts()
    assert not prefix.completion_errors(result, lease)
    if missing == "cutoff":
        result.pop("stop_reason")
    elif missing == "duration":
        result["elapsed_seconds"] = 2399
    elif missing == "fault":
        result["fault_observations"] = []
    elif missing == "pool":
        result["pool_contract"] = {"passed": False}
    elif missing == "scheduled":
        lease["scheduled_observation"] = None
    elif missing == "witness":
        lease["independent_failure_witness"] = None
    else:
        lease["fence_observation"]["errors"] = {"TimeoutError": 1}
    assert prefix.completion_errors(result, lease)


@pytest.mark.parametrize("cleanup_phase", [None, "resources", "positions", "faults", "publisher"])
async def test_real_parent_prefix_stops_before_acceptance(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, cleanup_phase: str | None
) -> None:
    import json
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from tests.infra.execution_market import profile_http, profile_positions
    from tests.infra.execution_market import profile_publisher_recovery as clock_recovery
    from tests.infra.execution_market.profile_parent_poll import ParentPollGate
    from tests.infra.execution_market.test_workload_latency import mock_parent

    load_schedule = workload.load_fault_schedule
    args = mock_parent(monkeypatch, tmp_path, phase="W3", case="fast")
    monkeypatch.setattr(workload, "load_fault_schedule", load_schedule)
    vars(args).update(vars(options()))
    args.owners = args.workers = 20
    args.rate = 2
    args.cycles_per_owner = 282
    args.parent_poll_limit = 4
    args.r8_claim_budget = args.coordinate_claims = True
    args.publisher_heartbeat_per_book = args.final_tail_drain = True
    args.fault_schedule = internal.fault_schedule_for(internal.NAME)
    for role in ("API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"):
        monkeypatch.setenv(
            f"TIEWTRADE_DATABASE_URL_{role}", "postgresql://localhost/tiewtrade_internal20_mock"
        )
    monkeypatch.setattr(ParentPollGate, "verify_pool", lambda *a: None)
    monkeypatch.setattr(internal, "require_empty_database", AsyncMock())
    monkeypatch.setattr(clock_recovery, "current", lambda: SimpleNamespace())

    @asynccontextmanager
    async def intake(*a: Any, **kw: Any) -> Any:
        yield object()

    monkeypatch.setattr(profile_http, "internal_intake", intake)

    async def wait(*a: Any, **kw: Any) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(
        profile_positions, "PositionChecks", lambda *a: SimpleNamespace(observe_endurance=wait)
    )
    monkeypatch.setattr(workload, "run_scheduled_cycles", wait)
    clock = [100.0]
    monkeypatch.setattr(workload, "monotonic", lambda: clock[0])

    async def cutoff(started: float) -> None:
        clock[0] = started + 2400

    monkeypatch.setattr(prefix, "cutoff", cutoff)
    cleanup_error = RuntimeError("PRIVATE cleanup error")

    async def failing_cleanup(*a: Any, **kw: Any) -> None:
        if cleanup_phase == "publisher":
            a[2]["published"] = 2
        try:
            await asyncio.Event().wait()
        finally:
            raise cleanup_error

    if cleanup_phase == "positions":
        monkeypatch.setattr(
            profile_positions,
            "PositionChecks",
            lambda *a: SimpleNamespace(observe_endurance=failing_cleanup),
        )
    elif cleanup_phase is not None:
        name = {
            "resources": "resource_sampler",
            "faults": "run_fault_schedule",
            "publisher": "market_publisher",
        }[cleanup_phase]
        monkeypatch.setattr(workload, name, failing_cleanup)
    starts: list[float] = []
    signal = asyncio.get_running_loop().create_future()
    if cleanup_phase is None:
        assert (
            await workload._run(args, observer_failure=signal, measurement_started=starts.append)
            == 2
        )
    else:
        with pytest.raises(RuntimeError) as caught:
            await workload._run(args, observer_failure=signal, measurement_started=starts.append)
        assert caught.value is cleanup_error
        receipt = json.loads((args.output / "prefix-cleanup-failure.json").read_text())
        assert receipt["errors"] == [{"phase": cleanup_phase, "error_type": "RuntimeError"}]
        assert "PRIVATE" not in json.dumps(receipt)
    result = json.loads((args.output / "result.json").read_text())
    assert result["status"] == "INCOMPLETE" and result["diagnostic_status"] == "INCOMPLETE"
    assert result["stop_reason"] == "PLANNED_PREFIX_CUTOFF"
    assert result["elapsed_seconds"] == 2400 and result["target_seconds"] == 14400
    assert result["full_replay"] == "NOT_RUN" and result["global_invariants"] is None
    assert len(starts) == 1
    assert isinstance(workload.verify, AsyncMock)
    workload.verify.assert_not_awaited()


@pytest.mark.usefixtures("internal_database")
async def test_real_cutoff_releases_transaction_and_locks() -> None:
    from sqlalchemy import text

    from tests.infra.execution_market.profile_observer_diagnostic import fixture_statement
    from tests.infra.execution_market.profile_publisher_fence import FenceObservation

    entered = asyncio.Event()
    pids: list[int] = []

    async def operation() -> None:
        async with fixture_statement(True) as (statement, holder):
            assert holder is not None
            pids.extend([holder, statement["backend_pid"]])
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(operation())
    observer = FenceObservation(lambda: None)
    try:
        await asyncio.wait_for(entered.wait(), 5)
        timer = await finished()
        with pytest.raises(prefix.PrefixCutoffError):
            await workload.with_publisher(task, None, cutoff=timer)
        assert task.done()
        async with observer.engine.connect() as connection:
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_locks WHERE pid=ANY(CAST(:pids AS int[])) "
                        "AND locktype='advisory'"
                    ),
                    {"pids": pids},
                )
            ).scalar_one() == 0
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE pid=ANY(CAST(:pids AS int[])) "
                        "AND xact_start IS NOT NULL"
                    ),
                    {"pids": pids},
                )
            ).scalar_one() == 0
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await observer.close()


@pytest.mark.parametrize("has_primary", [False, True])
@pytest.mark.parametrize("io_failure", [False, True])
async def test_cleanup_multiple_errors_preserves_original_and_attempts_all(
    tmp_path: Any,
    has_primary: bool,
    io_failure: bool,
) -> None:
    import json
    from unittest.mock import Mock

    first = RuntimeError("PRIVATE first")
    second = ValueError("PRIVATE second")
    primary = LookupError("PRIVATE primary") if has_primary else None

    async def failing() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            raise first

    task = asyncio.create_task(failing())
    await asyncio.sleep(0)
    dispose = AsyncMock(side_effect=second)
    last = AsyncMock()
    result_path = tmp_path / "result.json"
    workload.save(result_path, {"status": "FAILED", "diagnostic_status": "COMPLETE"})
    writer = Mock(side_effect=OSError("PRIVATE io")) if io_failure else workload.save

    async def close() -> None:
        await prefix.close_owned(
            [("resources", task)],
            [("dispose", dispose), ("last", last)],
            output=tmp_path,
            save=writer,
            primary=primary,
        )

    if has_primary:
        await close()
    else:
        with pytest.raises(RuntimeError) as caught:
            await close()
        assert caught.value is first
    assert task.done()
    dispose.assert_awaited_once()
    last.assert_awaited_once()
    original = primary if primary is not None else first
    notes = " ".join(original.__notes__)
    assert "ValueError" in notes and "PRIVATE" not in notes
    if io_failure:
        assert "OSError" in notes
    else:
        result = json.loads(result_path.read_text())
        assert result["status"] == "FAILED"
        assert result["diagnostic_status"] == "INCOMPLETE"
        receipt = json.loads((tmp_path / "prefix-cleanup-failure.json").read_text())
        assert len(receipt["errors"]) == 2


async def test_unexpected_task_cancellation_is_evidence_loss(tmp_path: Any) -> None:
    task = asyncio.create_task(asyncio.sleep(100))
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    dispose = AsyncMock()
    with pytest.raises(asyncio.CancelledError):
        await prefix.close_owned(
            [("resources", task)],
            [("dispose", dispose)],
            output=tmp_path,
            save=workload.save,
            primary=None,
        )
    dispose.assert_awaited_once()
    assert (tmp_path / "prefix-cleanup-failure.json").exists()
