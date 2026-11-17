"""OBS-03 exact opt-in, actual monitor timing and fail-fast evidence."""

import argparse
import asyncio
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from tests.infra.execution_market import profile_publisher_lease_load as load
from tests.infra.execution_market.profile_observer_diagnostic import fixture_statement
from tests.infra.execution_market.profile_publisher_fence import FenceObservation
from tests.infra.execution_market.profile_publisher_lease import LeaseTrace
from tests.infra.execution_market.test_observer_diagnostic import observer as observer


def approved(**changes: Any) -> argparse.Namespace:
    values = {
        "phase": "SMOKE",
        "acceptance_profile": "PAPER_INTERNAL20_V1",
        "publisher_lease_observer": True,
        "publisher_fence_observer": True,
        "publisher_fence_fail_fast": True,
        "publisher_fence_timing": True,
        "publisher_clock_recovery": False,
    }
    values.update(changes)
    return argparse.Namespace(**values)


@pytest.mark.parametrize(
    "change",
    [
        {"phase": "W3"},
        {"phase": "W1"},
        {"acceptance_profile": "other"},
        {"publisher_lease_observer": False},
        {"publisher_fence_observer": False},
        {"publisher_fence_fail_fast": False},
        {"publisher_clock_recovery": True},
        {"worker_only": True},
        {"diagnostics": True},
        {"controlled_delay": True},
        {"failure_timeline": True},
        {"publisher_fence_timing": False},
    ],
)
def test_exact_scope(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        load.validate_options(approved(**change))


def test_approved_and_default() -> None:
    load.validate_options(approved())
    load.validate_options(argparse.Namespace())


async def test_monitor_once_with_actual_identity(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = {"backend_pid": 7, "stage": "price_renew", "started": monotonic() - 2}
    trace = cast(
        LeaseTrace, SimpleNamespace(statements=[value], publication=SimpleNamespace(tick=42))
    )
    measured = FenceObservation(lambda: trace, timing=True)
    original = measured.sample
    calls = 0

    async def sample(statement: dict[str, Any]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        assert asyncio.current_task() is measured.task
        try:
            return await original(statement)
        finally:
            measured.stop.set()

    monkeypatch.setattr(measured, "sample", sample)
    measured.start()
    assert measured.task is not None
    await measured.task
    await measured.close()
    report = measured.report()
    assert calls == 1 and report["timing"]["counts"] == {"RETURNED": 1}
    row = report["timing"]["recent"][0]
    assert row["observation"]["publication_tick"] == 42
    assert row["observation"]["publisher_pid"] == 7
    assert len(row["spans"]) == 7 and report["timing"]["lag_task_joined"]
    assert not report["errors"]


async def test_foreign_task_rejected(observer: FenceObservation) -> None:
    measured = FenceObservation(lambda: None, timing=True)
    try:
        with pytest.raises(ValueError, match="owned monitor"):
            await measured.timed_sample({})
        assert not measured.timing_counts
    finally:
        await measured.close()


async def test_timing_retention_and_error_identity(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    measured = FenceObservation(lambda: None, timing=True)
    measured.task = cast(asyncio.Task[None], asyncio.current_task())
    value = {"backend_pid": 7, "stage": "price_renew", "started": monotonic()}
    try:
        for _ in range(70):
            await measured.timed_sample(value)
        primary = RuntimeError("PRIVATE")
        monkeypatch.setattr(measured, "sample", AsyncMock(side_effect=primary))
        with pytest.raises(RuntimeError) as caught:
            await measured.timed_sample(value)
        assert caught.value is primary
        assert len(measured.timings) == 64 and measured.timing_counts == {
            "RETURNED": 70,
            "RuntimeError": 1,
        }
        assert measured.failed_timing is measured.timings[-1]
    finally:
        measured.task = None
        await measured.close()


async def test_sampler_error_signals_fail_fast(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    value = {"backend_pid": 7, "stage": "price_renew", "started": monotonic() - 2}
    trace = cast(LeaseTrace, SimpleNamespace(statements=[value]))
    measured = FenceObservation(lambda: trace, timing=True)
    parent = load.LoadLeaseObserver(
        tmp_path, {}, fence_observer=True, fence_fail_fast=True, fence_timing=True
    )
    parent.fence = measured
    monkeypatch.setattr(measured, "sample", AsyncMock(side_effect=TimeoutError()))
    measured.start()
    assert measured.task is not None
    measured.task.add_done_callback(parent.sampler_finished)
    assert parent.failure is not None
    await asyncio.wait_for(asyncio.shield(parent.failure), 2)
    await measured.close()
    assert parent.failure_reason == "SAMPLER_EVIDENCE_LOST"
    assert measured.report()["timing"]["counts"] == {"TimeoutError": 1}
    parent.flush_failure()
    assert (tmp_path / "publisher-fence-failure.json").exists()


async def test_lag_failure_stops_monitor(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    measured = FenceObservation(lambda: None, timing=True)
    assert measured.lag is not None
    monkeypatch.setattr(measured.lag, "run", AsyncMock(side_effect=RuntimeError("PRIVATE")))
    measured.start()
    assert measured.task is not None
    await asyncio.gather(measured.task, return_exceptions=True)
    await measured.close()
    assert measured.errors == {"LoopLagEvidenceLost": 1}
    assert measured.report()["timing"]["lag_task_joined"]


@pytest.mark.usefixtures("internal_database")
async def test_real_monitor_blocker_timing_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    measured = FenceObservation(lambda: None, timing=True)
    try:
        async with fixture_statement(True) as (value, holder):
            value["started"] = monotonic() - 2
            trace = cast(LeaseTrace, SimpleNamespace(statements=[value]))
            measured.current = lambda: trace
            original = measured.sample

            async def sample(statement: dict[str, Any]) -> dict[str, Any]:
                try:
                    return await original(statement)
                finally:
                    measured.stop.set()

            monkeypatch.setattr(measured, "sample", sample)
            measured.start()
            assert measured.task is not None
            await asyncio.wait_for(measured.task, 3)
            row = measured.report()["timing"]["recent"][0]
            assert row["outcome"] == "RETURNED" and len(row["spans"]) == 7
            assert any(holder in item["blocking_pids"] for item in row["observation"]["activity"])
            assert measured.engine.pool.checkedout() == 0  # type: ignore[attr-defined]
    finally:
        await measured.close()
    assert measured.report()["timing"]["lag_task_joined"]


async def test_no_trigger_is_not_timing_passed(observer: FenceObservation) -> None:
    measured = FenceObservation(lambda: None, timing=True)
    measured.start()
    await asyncio.sleep(0)
    await measured.close()
    assert measured.report()["timing"]["status"] == "NO_TRIGGER"
    assert measured.report()["timing"]["lag_task_completed"] is True
    assert measured.report()["timing"]["counts"] == {}
    assert measured.report()["timing"]["lag_task_joined"]


async def test_shutdown_during_capture_retains_incomplete(
    observer: FenceObservation, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = {"backend_pid": 7, "stage": "price_renew", "started": monotonic() - 2}
    trace = cast(LeaseTrace, SimpleNamespace(statements=[value]))
    measured = FenceObservation(lambda: trace, timing=True)
    entered = asyncio.Event()

    async def wait(statement: dict[str, Any]) -> dict[str, Any]:
        entered.set()
        await asyncio.Event().wait()
        return {}

    monkeypatch.setattr(measured, "sample", wait)
    measured.start()
    await entered.wait()
    assert measured.task is not None
    measured.stop.set()
    measured.task.cancel()
    await measured.close()
    assert measured.report()["timing"]["status"] == "INCOMPLETE"
    assert measured.report()["timing"]["counts"] == {"CancelledError": 1}


@pytest.mark.parametrize(
    "missing", ["status", "lag_task_joined", "lag_task_completed", "count_mismatch", "cancelled"]
)
async def test_incomplete_timing_cannot_flush_as_complete(tmp_path: Path, missing: str) -> None:
    import json

    parent = load.LoadLeaseObserver(
        tmp_path,
        {"write_failed": False},
        fence_observer=True,
        fence_fail_fast=True,
        fence_timing=True,
    )
    parent.outcomes["RETURNED"] = 1
    timing: dict[str, Any] = {
        "status": "RECORDED",
        "lag_task_joined": True,
        "lag_task_completed": True,
        "counts": {"RETURNED": 1},
    }
    if missing == "count_mismatch":
        timing["counts"] = {}
    elif missing == "cancelled":
        timing["status"] = "INCOMPLETE"
    else:
        timing.pop(missing)
    parent.fence = SimpleNamespace(
        errors={}, total=1, report=lambda: {"task_joined": True, "timing": timing}
    )
    (tmp_path / "publisher-readiness.json").write_text(
        json.dumps(
            {
                "scope": "parent publish_market readiness guards only",
                "checks": [],
                "total_checks": 0,
                "discarded_earlier_checks": 0,
                "flush_reason": "test",
            }
        )
    )
    with pytest.raises(ValueError, match="fence observer evidence incomplete"):
        parent.flush()
    assert (tmp_path / "publisher-lease.json").exists()


async def test_internal_smoke_duration_wait_is_supervised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from tests.infra.execution_market import profile_http
    from tests.infra.execution_market import profile_internal as internal
    from tests.infra.execution_market import profile_workload as workload
    from tests.infra.execution_market.profile_parent_poll import ParentPollGate
    from tests.infra.execution_market.test_workload_latency import mock_parent

    args = mock_parent(monkeypatch, tmp_path, phase="SMOKE", case="fast")
    for role in ("API", "AUTH", "ENGINE", "ENGINE_SCAN", "MIGRATOR", "MARKET_DATA"):
        monkeypatch.setenv(
            f"TIEWTRADE_DATABASE_URL_{role}", "postgresql://localhost/tiewtrade_internal20_mock"
        )
    args.acceptance_profile = internal.NAME
    args.owners = args.workers = 20
    args.rate = 2
    args.cycles_per_owner = 6
    args.parent_poll_limit = 4
    args.r8_claim_budget = args.coordinate_claims = True
    args.publisher_heartbeat_per_book = args.final_tail_drain = True
    monkeypatch.setattr(ParentPollGate, "verify_pool", lambda *a: None)
    monkeypatch.setattr(internal, "require_empty_database", AsyncMock())

    @asynccontextmanager
    async def intake(*a: Any, **kw: Any) -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr(profile_http, "internal_intake", intake)
    signal = asyncio.get_running_loop().create_future()
    original_sleep = asyncio.sleep

    async def sleep(seconds: float) -> None:
        if seconds > 1:
            signal.set_result(None)
            await asyncio.Event().wait()
        await original_sleep(seconds)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    verify = workload.verify
    starts: list[float] = []
    with pytest.raises(RuntimeError, match="F17_FENCE_OBSERVER_EVIDENCE_INCOMPLETE"):
        await workload._run(args, observer_failure=signal, measurement_started=starts.append)
    import json

    window = json.loads((args.output / "processing-window.json").read_text())
    assert starts == [window["started"]]
    assert isinstance(verify, AsyncMock)
    verify.assert_not_awaited()
    database: Any = cast(Any, workload).create_engine_for(None)
    database.dispose.assert_awaited()
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("ordering", ["before_start", "before_close", "callback_first"])
async def test_lag_cancellation_never_becomes_normal_close(
    observer: FenceObservation,
    ordering: str,
) -> None:
    measured = FenceObservation(lambda: None, timing=True)
    measured.start()
    if ordering != "before_start":
        await asyncio.sleep(0)
    assert measured.lag_task is not None
    measured.lag_task.cancel()
    if ordering == "callback_first":
        await asyncio.gather(measured.lag_task, return_exceptions=True)
        await asyncio.sleep(0)
    await measured.close()
    report = measured.report()
    assert measured.lag_task.cancelled()
    assert report["errors"] == {"LoopLagEvidenceLost": 1}
    timing = report["timing"]
    assert timing["status"] == "INCOMPLETE"
    assert timing["lag_task_joined"] is True
    assert timing["lag_task_completed"] is False


async def test_report_rejects_cancelled_lag_before_callback(observer: FenceObservation) -> None:
    measured = FenceObservation(lambda: None, timing=True)
    assert measured.lag is not None
    measured.lag_task = asyncio.create_task(measured.lag.run())
    measured.lag_task.cancel()
    await asyncio.gather(measured.lag_task, return_exceptions=True)
    # No callback registered: report must still recognize terminal evidence loss.
    assert not measured.errors
    timing = measured.report()["timing"]
    assert timing["status"] == "INCOMPLETE"
    assert timing["lag_task_completed"] is False
    await measured.close()
