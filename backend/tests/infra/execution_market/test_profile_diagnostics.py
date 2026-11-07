"""Opt-in diagnostics preserve workload behavior and clean up on failure."""

import argparse
import asyncio
import json
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_diagnostics as diagnostic
from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits.profile_dispatch_timing import Recorder, traced_worker
from tests.infra.risk_limits.profile_pool_timing import TransactionTrace
from tiewtrade.core.orders import OrderStatus
from tiewtrade.infra.db import DatabaseRole, scan_session_bypassing_rls, user_session
from tiewtrade.infra.db import session as db
from tiewtrade.services.engine import paper_order


@pytest.mark.parametrize("fail_write", [False, True])
def test_trace_control_is_complete_before_existing_readers_can_see_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_write: bool
) -> None:
    control = tmp_path / "dispatch-trace-control.json"
    recorder = Recorder(tmp_path / "worker.json")
    original = Path.write_text
    started = monotonic()
    checked = False

    def interrupted(path: Path, data: str, **kwargs: Any) -> int:
        nonlocal checked
        # Force a reader into the exact create-before-content interval from the run.
        original(path, "", **kwargs)
        assert path == control.with_suffix(".json.tmp")
        assert not control.exists()
        recorder.activate()
        assert recorder.start is None
        assert not TransactionTrace(tmp_path / "parent.transactions.jsonl").active()
        checked = True
        if fail_write:
            raise OSError("controlled interrupted control publication")
        return original(path, data, **kwargs)

    monkeypatch.setattr(Path, "write_text", interrupted)
    try:
        if fail_write:
            with pytest.raises(OSError, match="interrupted control publication"):
                f15.publish_trace_control(tmp_path, started)
            assert not control.exists()
            recorder.activate()
            assert recorder.start is None
        else:
            f15.publish_trace_control(tmp_path, started)
            assert json.loads(control.read_text()) == {
                "started": started,
                "seconds": 180,
                "owners": [],
                "detail_limit": 0,
            }
            recorder.activate()
            assert recorder.start == started
            assert TransactionTrace(tmp_path / "parent.transactions.jsonl").active()
            assert not control.with_suffix(".json.tmp").exists()
        assert checked
    finally:
        recorder.stream.close()


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("r8,coordinate", [(False, False), (True, False), (True, True)])
@pytest.mark.parametrize("group", ["worker", "recovery-worker", "restart-0"])
async def test_child_diagnostic_flag_is_explicit_and_credentials_stay_filtered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    r8: bool,
    coordinate: bool,
    group: str,
) -> None:
    process = AsyncMock(pid=123, returncode=None)
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(f15, "wait_runtime_pid", AsyncMock(return_value=456))
    monkeypatch.setattr(f15, "WORKER_RUNTIME_PIDS", {})
    monkeypatch.setenv("TIEWTRADE_SEALING_KEY_VENUE_API_SECRET", "PRIVATE_TEST_VALUE")
    processes, stop, metrics = await f15.start_worker_processes(
        1,
        tmp_path,
        group=group,
        diagnostics=enabled,
        r8_claim_budget=r8,
        coordinate_claims=coordinate,
    )
    assert processes == [process] and stop == tmp_path / f"{group}.stop"
    assert metrics == [tmp_path / f"{group}-0.json"]
    assert spawn.await_args is not None
    argv = spawn.await_args.args
    assert ("--diagnostics" in argv) is enabled
    assert ("--r8-claim-budget" in argv) is r8
    assert ("--coordinate-claims" in argv) is coordinate
    assert "TIEWTRADE_SEALING_KEY_VENUE_API_SECRET" not in spawn.await_args.kwargs["env"]
    assert f15.WORKER_RUNTIME_PIDS == {123: 456}


async def test_normal_workload_does_not_enter_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = AsyncMock(return_value=7)
    observed = AsyncMock(side_effect=AssertionError("diagnostics should be disabled"))
    monkeypatch.setattr(f15, "_run", original)
    monkeypatch.setattr(diagnostic, "observe_workload", observed)
    args = argparse.Namespace()
    assert await f15.run(args) == 7
    original.assert_awaited_once_with(args)
    observed.assert_not_awaited()


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("measured", [False, True])
@pytest.mark.parametrize("busy", [False, True])
async def test_coordinator_observation_records_calls_and_restores_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: bool, measured: bool, busy: bool
) -> None:
    gate = AsyncMock(return_value=not busy)
    primary = RuntimeError("controlled selection failure")

    async def selection(*args: Any, **kwargs: Any) -> Any:
        await vars(paper_order)["try_lock_order_selection"](None)
        if fail:
            raise primary
        return None, 0

    monkeypatch.setattr(paper_order, "try_lock_order_selection", gate)
    monkeypatch.setattr(paper_order, "_select_coordinated_claim", selection)
    before = db._begin
    if measured:
        f15.publish_trace_control(tmp_path, monotonic())

    async def operation() -> None:
        assert await paper_order._select_coordinated_claim(None, None, "test") == (None, 0)  # type: ignore[arg-type]

    if fail:
        with pytest.raises(RuntimeError) as caught:
            await traced_worker(operation(), tmp_path / "worker.json")
        assert caught.value is primary
    else:
        await traced_worker(operation(), tmp_path / "worker.json")
    assert vars(paper_order)["try_lock_order_selection"] is gate
    assert paper_order._select_coordinated_claim is selection
    assert db._begin is before
    gate.assert_awaited_once()
    records = [
        json.loads(line) for line in (tmp_path / "worker.dispatch.jsonl").read_text().splitlines()
    ]
    phases = [row["phases"] for row in records if row["event"] in {"SECOND", "TAIL"}]
    phases.extend(row["calls"] for row in records if row["event"] == "SETUP_SUMMARY")
    assert sum(row["event"] == "SETUP_SUMMARY" for row in records) == 1
    for phase in ("order_gate.call", "order_selection.call"):
        assert sum(row.get(phase, {}).get("count", 0) for row in phases) == 1
    assert sum(row.get("order_gate.call", {}).get("busy", 0) for row in phases) == int(busy)
    assert sum(row.get("order_gate.call", {}).get("acquired", 0) for row in phases) == int(not busy)
    assert records[-1]["event"] == "CLOSED"


@pytest.mark.parametrize("busy", [False, True])
async def test_coordinator_hold_and_setup_survive_real_transaction_failure(
    tmp_path: Path, scan_engine: AsyncEngine, busy: bool
) -> None:
    primary = RuntimeError("controlled failure after coordinator acquisition")

    async def operation() -> None:
        async with scan_session_bypassing_rls(scan_engine, cleanup_seconds=2) as session:
            assert await vars(paper_order)["try_lock_order_selection"](session) is not busy
            raise primary

    async with scan_session_bypassing_rls(scan_engine) as holder:
        if busy:
            assert await vars(paper_order)["try_lock_order_selection"](holder)
        with pytest.raises(RuntimeError) as caught:
            await traced_worker(operation(), tmp_path / "worker.json")
    assert caught.value is primary
    async with scan_session_bypassing_rls(scan_engine) as session:
        assert await vars(paper_order)["try_lock_order_selection"](session)
    records = [
        json.loads(line) for line in (tmp_path / "worker.dispatch.jsonl").read_text().splitlines()
    ]
    summary = next(row["calls"] for row in records if row["event"] == "SETUP_SUMMARY")
    assert summary["order_gate.call"]["count"] == 1
    assert summary["order_gate.call"]["busy"] == int(busy)
    if busy:
        assert "order_gate_hold.transaction" not in summary
    else:
        assert summary["order_gate_hold.transaction"]["count"] == 1
        assert summary["order_gate_hold.transaction"]["seconds"] >= 0
    assert records[-1]["event"] == "CLOSED"


@pytest.mark.parametrize("phase", ["W1", "SMOKE"])
async def test_parent_trace_preserves_failure_and_returns_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    output = tmp_path / "run"
    owner, order = uuid4(), uuid4()
    before = (db._begin, vars(f15)["create_engine_for"], f15.wait_status, f15.resource_sampler)
    private = "DO_NOT_SERIALIZE_DIAGNOSTIC_ERROR"

    async def wait_status(*args: Any, **kwargs: Any) -> None:
        async with user_session(args[0], owner) as session:
            assert (
                await session.execute("SELECT CAST(:value AS text)", {"value": private})
            ).scalar_one() == private
            raise RuntimeError(private)

    async def workload(args: argparse.Namespace) -> int:
        output.mkdir()
        f15.save(
            output / "dispatch-trace-control.json",
            {"started": monotonic(), "seconds": 180, "owners": [], "detail_limit": 0},
        )
        engine = vars(f15)["create_engine_for"](DatabaseRole.API)

        try:
            await f15.wait_status(engine, owner, order, OrderStatus.FILLED)
        finally:
            await engine.dispose()
        return 0

    monkeypatch.setattr(f15, "wait_status", wait_status)
    monkeypatch.setattr(f15, "_run", workload)
    with pytest.raises(RuntimeError, match=private):
        await f15.run(argparse.Namespace(diagnostics=True, phase=phase, output=output))
    assert (db._begin, vars(f15)["create_engine_for"], f15.wait_status, f15.resource_sampler) == (
        before[0],
        before[1],
        wait_status,
        before[3],
    )
    rows = [
        json.loads(row) for row in (output / "parent.transactions.jsonl").read_text().splitlines()
    ]
    transaction = next(row for row in rows if row.get("phase") == "wait_status")
    assert transaction["owner"] == str(owner)
    assert transaction["order_id"] == str(order)
    assert transaction["outcome"] == "RuntimeError"
    assert transaction["pool_wait_seconds"] >= 0 and transaction["queries"]
    assert private not in "".join(path.read_text() for path in output.glob("*.json*"))
    pools = json.loads((output / "parent.pools.json").read_text())
    assert pools["finalized"] and pools["pools"][0]["checked_out"] == 0
    assert pools["pools"][0]["pool_size"] == 5
    assert pools["pools"][0]["max_overflow"] == 10
    assert json.loads((output / "diagnostic-only.json").read_text())["acceptance_result"] is False


@pytest.mark.parametrize("baseline", [False, True])
async def test_successful_smoke_observer_records_publisher_without_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, baseline: bool
) -> None:
    output = tmp_path / "run"

    lease = SimpleNamespace(owner=uuid4(), generation=1, last_input_id=12)

    async def publish(engine: AsyncEngine, *args: Any, **kwargs: Any) -> None:
        async with db.market_data_session(engine) as session:
            await session.execute("SELECT clock_timestamp()")

    async def workload(args: argparse.Namespace, **kwargs: Any) -> int:
        output.mkdir()
        if not baseline:
            f15.save(
                output / "dispatch-trace-control.json", {"started": monotonic(), "seconds": 180}
            )
        engine = vars(f15)["create_engine_for"](DatabaseRole.MARKET_DATA)
        try:
            await vars(f15)["publish_market"](engine, lease, trade_id=13)
        finally:
            await engine.dispose()
        return 0

    monkeypatch.setattr(f15, "publish_market", publish)
    monkeypatch.setattr(f15, "_run", workload)
    assert (
        await f15.run(
            argparse.Namespace(
                diagnostics=True,
                phase="SMOKE",
                output=output,
                coordinate_claims=baseline,
                parent_poll_limit=4 if baseline else None,
                r8_claim_budget=baseline,
                publisher_heartbeat_per_book=baseline,
                final_tail_drain=baseline,
            )
        )
        == 0
    )
    rows = [json.loads(x) for x in (output / "parent.transactions.jsonl").read_text().splitlines()]
    assert any(row.get("phase") == "publish_market" and row["queries"] for row in rows)
    publisher = next(row for row in rows if row.get("phase") == "publish_market")
    assert publisher["publisher_tick"] == "13"
    assert publisher["book_owner"] == str(lease.owner)
    assert publisher["book_last_input_id"] == "12"
    assert ("query_details" in publisher) is baseline
    if baseline:
        assert publisher["measurement_active_at_start"] is False
    assert rows[-1]["event"] == "CLOSED" and not rows[-1]["truncated"]
    assert json.loads((output / "diagnostic-only.json").read_text())["acceptance_result"] is False


async def test_worker_failure_restores_observers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = (
        db._begin,
        vars(f15)["create_engine_for"],
        vars(f15)["run_paper_order_round"],
        vars(paper_order)["claim_order"],
    )
    monkeypatch.setattr(f15, "run_worker_process", AsyncMock(side_effect=RuntimeError("private")))
    with pytest.raises(RuntimeError, match="private"):
        await diagnostic.observe_worker(
            argparse.Namespace(
                worker_metrics=tmp_path / "worker.json",
                worker_stop=tmp_path / "stop",
                worker_name="diagnostic",
            )
        )
    assert (
        db._begin,
        vars(f15)["create_engine_for"],
        vars(f15)["run_paper_order_round"],
        vars(paper_order)["claim_order"],
    ) == before
    assert "private" not in "".join(path.read_text() for path in tmp_path.glob("*.json*"))


async def test_existing_output_is_not_modified(tmp_path: Path) -> None:
    with pytest.raises(FileExistsError):
        await diagnostic.observe_workload(argparse.Namespace(phase="W1", output=tmp_path))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("r8", [False, True])
async def test_real_worker_cli_records_pools_and_exits_cleanly(tmp_path: Path, r8: bool) -> None:
    processes, stop, _ = await f15.start_worker_processes(
        1, tmp_path, diagnostics=True, r8_claim_budget=r8
    )
    pools = tmp_path / "worker-0.pools.json"
    try:
        async with asyncio.timeout(5):
            while not pools.exists() or len(json.loads(pools.read_text())["pools"]) != 2:
                assert processes[0].returncode is None
                await asyncio.sleep(0.01)
    finally:
        await f15.stop_worker_processes(processes, stop)
    assert processes[0].returncode == 0
    document = json.loads(pools.read_text())
    assert document["finalized"]
    assert all(pool["checked_out"] == 0 for pool in document["pools"])
    rows = (tmp_path / "worker-0.transactions.jsonl").read_text().splitlines()
    assert json.loads(rows[-1])["acceptance_result"] is False


async def test_cancelling_resource_sampler_joins_both_observers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = [asyncio.Event(), asyncio.Event()]
    cleaned: list[int] = []

    async def observe(index: int, *args: Any) -> None:
        started[index].set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.append(index)

    resource = AsyncMock()

    async def resources(*args: Any) -> None:
        await observe(0, *args)

    async def database(*args: Any) -> None:
        await observe(1, *args)

    monkeypatch.setattr(f15, "resource_sampler", resources)
    monkeypatch.setattr(diagnostic, "sample_database", database)
    with diagnostic.parent_observations(tmp_path):
        task = asyncio.create_task(
            f15.resource_sampler(resource, resource, [], asyncio.Lock(), asyncio.Event(), [])
        )
        try:
            await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started)), 2)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert f15.resource_sampler is resources
    assert sorted(cleaned) == [0, 1]


@pytest.mark.parametrize("fail_write", [False, True])
async def test_cycle_expiry_identifies_owner_without_marking_cancelled_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_write: bool
) -> None:
    owners = [cast(f15.OwnerState, SimpleNamespace(user_id=uuid4())) for _ in range(2)]
    orders = {owner.user_id: uuid4() for owner in owners}
    timeout = asyncio.timeout
    requested: list[float | None] = []
    save = f15.save
    private = "PRIVATE_TIMEOUT_OBSERVER_DETAIL"

    def fast_budget(seconds: float | None) -> asyncio.Timeout:
        requested.append(seconds)
        return timeout(0.04 if len(requested) == 1 else 1)

    def save_observation(path: Path, value: object) -> None:
        if fail_write and path.name == "cycle-timeouts.json":
            raise OSError(private)
        save(path, value)

    async def waiting(*args: Any, **kwargs: Any) -> None:
        await asyncio.Event().wait()

    async def cycle(engine: Any, owner: Any, *args: Any) -> None:
        await f15.wait_status(engine, owner.user_id, orders[owner.user_id], OrderStatus.FILLED)

    monkeypatch.setattr(asyncio, "timeout", fast_budget)
    monkeypatch.setattr(f15, "save", save_observation)
    monkeypatch.setattr(f15, "wait_status", waiting)
    monkeypatch.setattr(f15, "cycle", cycle)
    original = f15.run_scheduled_cycles
    with diagnostic.parent_observations(tmp_path) as records, pytest.raises(TimeoutError):
        await f15.run_scheduled_cycles(
            cast(AsyncEngine, None),
            owners,
            uuid4(),
            1,
            1000,
            f15.Counters(),
            [],
        )
    assert f15.run_scheduled_cycles is original
    assert requested == [60, 60]
    assert len(records) == 1
    assert records[0]["owner"] == str(owners[0].user_id)
    assert records[0]["budget_seconds"] == 60
    status = next(row for row in records[0]["phases"] if row["phase"] == "wait_status")
    assert status["order_id"] == str(orders[owners[0].user_id])
    assert status["expected_status"] == "FILLED" and status["outcome"] == "CancelledError"
    assert diagnostic._CYCLE.get() is None
    if fail_write:
        assert records[0]["write_error"] == "OSError"
    else:
        raw = (tmp_path / "cycle-timeouts.json").read_text()
        assert private not in raw and str(owners[1].user_id) not in raw


@pytest.mark.parametrize("inner_error", [False, True])
async def test_completed_cycles_and_child_timeouts_are_not_budget_expiry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, inner_error: bool
) -> None:
    owner = cast(f15.OwnerState, SimpleNamespace(user_id=uuid4()))

    async def cycle(*args: Any) -> None:
        if inner_error:
            raise TimeoutError("inner-private-error")

    monkeypatch.setattr(f15, "cycle", cycle)
    with diagnostic.parent_observations(tmp_path) as records:
        operation = f15.run_scheduled_cycles(
            cast(AsyncEngine, None),
            [owner],
            uuid4(),
            1,
            1000,
            f15.Counters(),
            [],
        )
        if inner_error:
            with pytest.raises(TimeoutError, match="inner-private-error"):
                await operation
        else:
            await operation
    assert not records and not (tmp_path / "cycle-timeouts.json").exists()
    assert diagnostic._CYCLE.get() is None


async def test_post_stop_snapshot_uses_scanner_and_preserves_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = AsyncMock()
    factory = Mock(return_value=engine)
    # The production factory is synchronous; only the reader/dispose are async.
    monkeypatch.setattr(f15, "create_engine_for", factory)
    command, owner = uuid4(), uuid4()
    reader = AsyncMock(side_effect=RuntimeError("PRIVATE_SNAPSHOT_DETAIL"))
    monkeypatch.setattr(diagnostic, "read_scheduler_diagnostics", reader)
    await diagnostic.write_timeout_queue_snapshot(
        tmp_path, [{"owner": str(owner), "phases": [{"command_id": str(command)}] * 2}]
    )
    factory.assert_called_once_with(DatabaseRole.ENGINE_SCAN)
    reader.assert_awaited_once_with(engine, owner, command_ids=(command,))
    engine.dispose.assert_awaited_once()
    raw = (tmp_path / "timeout-queue-snapshot.json").read_text()
    document = json.loads(raw)
    assert document["after_workers_stopped"] is True
    assert document["error_type"] == "RuntimeError" and "PRIVATE" not in raw


async def test_phase_retention_is_bounded_without_changing_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = cast(f15.OwnerState, SimpleNamespace(user_id=uuid4()))
    original_timeout = asyncio.timeout

    async def status(*args: Any) -> None:
        return

    async def cycle(*args: Any) -> None:
        for _ in range(100):
            await f15.wait_status(
                cast(AsyncEngine, None), owner.user_id, uuid4(), OrderStatus.FILLED
            )
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "timeout", lambda seconds: original_timeout(0.04))
    monkeypatch.setattr(f15, "wait_status", status)
    monkeypatch.setattr(f15, "cycle", cycle)
    with diagnostic.parent_observations(tmp_path) as records, pytest.raises(TimeoutError):
        await f15.run_scheduled_cycles(
            cast(AsyncEngine, None),
            [owner],
            uuid4(),
            1,
            1000,
            f15.Counters(),
            [],
        )
    assert len(records[0]["phases"]) == 32 and records[0]["truncated"] is True


@pytest.mark.parametrize("snapshot_fails", [False, True])
async def test_snapshot_runs_after_worker_cleanup_and_never_replaces_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot_fails: bool
) -> None:
    output = tmp_path / "run"
    owner = cast(f15.OwnerState, SimpleNamespace(user_id=uuid4()))
    stopped = False
    original_timeout = asyncio.timeout

    async def cycle(*args: Any) -> None:
        await asyncio.Event().wait()

    async def workload(args: argparse.Namespace) -> int:
        nonlocal stopped
        output.mkdir()
        try:
            await f15.run_scheduled_cycles(
                cast(AsyncEngine, None), [owner], uuid4(), 1, 1000, f15.Counters(), []
            )
        finally:
            stopped = True
        return 0

    async def read(*args: Any, **kwargs: Any) -> dict[str, object]:
        assert stopped
        if snapshot_fails:
            raise RuntimeError("PRIVATE_QUEUE_FAILURE")
        return {"owner": owner.user_id}

    monkeypatch.setattr(
        asyncio, "timeout", lambda seconds: original_timeout(0.03 if seconds == 60 else seconds)
    )
    monkeypatch.setattr(f15, "cycle", cycle)
    monkeypatch.setattr(f15, "_run", workload)
    monkeypatch.setattr(diagnostic, "read_scheduler_diagnostics", read)
    with pytest.raises(TimeoutError):
        await f15.run(argparse.Namespace(diagnostics=True, phase="W1", output=output))
    document = json.loads((output / "timeout-queue-snapshot.json").read_text())
    assert document["after_workers_stopped"] is True
    if snapshot_fails:
        assert document["error_type"] == "RuntimeError"
    else:
        assert document["snapshots"] == [{"owner": str(owner.user_id)}]
    assert "PRIVATE_QUEUE_FAILURE" not in (output / "timeout-queue-snapshot.json").read_text()
