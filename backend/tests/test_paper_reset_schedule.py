"""Declared RESET traffic must not pause trading, duplicate evidence, or hide failures."""

import asyncio
import io
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from itertools import pairwise
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits import profile_resets as resets
from tests.infra.risk_limits import profile_workload as workload
from tests.test_paper_cycle_budget import Clock


def test_fixed_plan_covers_all_owners_and_declared_faults() -> None:
    owners = [UUID(int=i + 1) for i in range(100)]
    selected = owners[3]
    plain = resets.reset_schedule(owners, selected=selected, run_id=UUID(int=500))
    assert [x.owner for x in plain] == [x for x in owners if x != selected] + [selected]
    assert [x.offset_seconds for x in plain] == list(range(180, 280))
    assert len({x.idempotency_key for x in plain}) == 100
    fault = f15.FaultEvent(225, 30, "WORKER_RESTART")
    shifted = resets.reset_schedule(owners, selected=selected, run_id=UUID(int=500), faults=[fault])
    assert [x.offset_seconds for x in shifted] == list(range(180, 225)) + list(range(255, 310))
    assert [x.idempotency_key for x in shifted] == [x.idempotency_key for x in plain]
    with pytest.raises(ValueError):
        resets.reset_schedule([*owners[:-1], owners[0]], selected=selected, run_id=UUID(int=500))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()

    async def sleep(seconds: float) -> None:
        clock.now += max(0, seconds)
        await asyncio.sleep(0)

    monkeypatch.setattr(resets, "monotonic", clock)
    monkeypatch.setattr(
        resets,
        "asyncio",
        SimpleNamespace(**{**vars(asyncio), "sleep": sleep, "timeout": clock.timeout}),
    )
    return clock


async def test_hundred_resets_are_spaced_and_leave_trading_running(
    tmp_path: Path, clock: Clock
) -> None:
    owners = [UUID(int=i + 1) for i in range(100)]
    plan = resets.reset_schedule(owners, selected=owners[0], run_id=UUID(int=500))
    ready = asyncio.Event()
    ready.set()
    calls: list[tuple[UUID, UUID, float]] = []
    trades = 0

    async def apply(owner: UUID, key: UUID) -> UUID:
        calls.append((owner, key, clock.now))
        clock.now += 0.2
        return UUID(int=len(calls))

    async def trading() -> None:
        nonlocal trades
        for _ in range(10):
            trades += 1
            await asyncio.sleep(0)

    progress = resets.ResetProgress(100)
    await resets.run_scheduled_work(
        trading(),
        resets.run_resets(
            plan,
            started=0,
            recovery_complete=ready,
            apply=apply,
            path=tmp_path / "resets.jsonl",
            progress=progress,
            gate=f15.FaultGate(),
        ),
    )
    assert trades == 10 and progress.passed
    assert len(calls) == len({c[0] for c in calls}) == 100
    assert all(b[2] - a[2] >= 1 for a, b in pairwise(calls))
    assert calls[-1][0] == owners[0]
    events = [json.loads(x) for x in (tmp_path / "resets.jsonl").read_text().splitlines()]
    assert sum(e["event"] == "APPLIED" for e in events) == 100


@pytest.mark.parametrize("ready", [False, True])
async def test_recovery_and_full_reset_deadlines_are_enforced(
    tmp_path: Path, clock: Clock, ready: bool
) -> None:
    recovery = asyncio.Event()
    if ready:
        recovery.set()
    progress = resets.ResetProgress(1)

    async def apply(owner: UUID, key: UUID) -> UUID:
        clock.now += 61
        return key

    with pytest.raises(TimeoutError if ready else RuntimeError):
        await resets.run_resets(
            [resets.ScheduledReset(UUID(int=1), 180, UUID(int=2))],
            started=0,
            recovery_complete=recovery,
            apply=apply,
            path=tmp_path / "resets.jsonl",
            progress=progress,
        )
    assert not progress.passed and progress.offered == int(ready)


async def test_closed_gate_does_not_offer_a_reset_or_change_cycle_activity(tmp_path: Path) -> None:
    gate = f15.FaultGate()
    gate.open.clear()
    recovery = asyncio.Event()
    recovery.set()
    applied = asyncio.Event()

    async def apply(owner: UUID, key: UUID) -> UUID:
        applied.set()
        return key

    progress = resets.ResetProgress(1)
    task = asyncio.create_task(
        resets.run_resets(
            [resets.ScheduledReset(UUID(int=1), 0, UUID(int=2))],
            started=monotonic(),
            recovery_complete=recovery,
            apply=apply,
            path=tmp_path / "resets.jsonl",
            progress=progress,
            gate=gate,
        )
    )
    try:
        for _ in range(3):
            await asyncio.sleep(0)
        assert not applied.is_set() and progress.offered == 0 and gate.active == 0
        gate.open.set()
        await asyncio.wait_for(task, 1)
        assert applied.is_set() and progress.passed and gate.active == 0
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("fails", ["cycles", "resets"])
async def test_first_error_cancels_and_joins_the_peer(fails: str) -> None:
    entered, joined = asyncio.Event(), asyncio.Event()
    original = RuntimeError("original failure")

    async def blocked() -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    async def broken() -> None:
        await entered.wait()
        raise original

    with pytest.raises(RuntimeError) as caught:
        await resets.run_scheduled_work(
            broken() if fails == "cycles" else blocked(),
            broken() if fails == "resets" else blocked(),
        )
    assert caught.value is original and joined.is_set()


async def test_trading_cycle_does_not_submit_an_end_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner: Any = SimpleNamespace(user_id=UUID(int=2))
    fixture: Any = SimpleNamespace(
        output=tmp_path,
        selected=UUID(int=1),
        engine=None,
        partial_ready=asyncio.Event(),
        mutation=AsyncMock(side_effect=AssertionError("extra RESET")),
    )
    fixture.partial_ready.set()
    counters = f15.Counters()

    async def new(*args: Any) -> None:
        counters.offered += 1
        counters.admitted += 1
        counters.completed += 1

    fixture.new = new
    fixture.request = AsyncMock(return_value=SimpleNamespace(state="SUCCEEDED", failure_code=None))
    for name in ("market_buy", "limit_sell", "market_sell"):
        monkeypatch.setattr(f15, name, lambda *args: SimpleNamespace(order_id=UUID(int=3)))
    monkeypatch.setattr(f15, "wait_status", AsyncMock())
    engine: Any = None
    async with workload.Fixture.cycle_scope(fixture, owner, 0):
        await workload.Fixture.cycle(fixture, engine, owner, UUID(int=4), 0, counters, [])
    fixture.mutation.assert_not_awaited()
    assert counters.completed == counters.offered == 5 and counters.cycles == 1
    row = json.loads((tmp_path / "cycle-timing.jsonl").read_text())
    assert row["trading_completed_at"] is not None


async def test_concurrent_marker_recording_does_not_duplicate_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    fixture: Any = SimpleNamespace(
        marker_locks=defaultdict(asyncio.Lock),
        last_markers={},
        input_stream=io.StringIO(),
        started=True,
        api=None,
    )
    owner: Any = SimpleNamespace(user_id=UUID(int=1))
    entered, release = asyncio.Event(), asyncio.Event()
    cursors = []

    @asynccontextmanager
    async def session(*args: Any) -> Any:
        async def execute(sql: str, params: Any) -> Any:
            cursors.append(params["last"])
            if params["last"] == 0:
                entered.set()
                await release.wait()
            return [
                SimpleNamespace(
                    sequence=params["last"] + 1, kind="FILL", ready_at=datetime.now(UTC)
                )
            ]

        yield SimpleNamespace(execute=execute)

    monkeypatch.setattr(workload, "user_session", session)
    tasks = [
        asyncio.create_task(workload.Fixture.record_financial(fixture, owner)) for _ in range(2)
    ]
    try:
        await entered.wait()
        for _ in range(3):
            await asyncio.sleep(0)
        assert cursors == [0]
        release.set()
        await asyncio.gather(*tasks)
        rows = [json.loads(x) for x in fixture.input_stream.getvalue().splitlines()]
        assert [r["cursor"] for r in rows] == [1, 2] and cursors == [0, 1]
    finally:
        release.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_cancelling_the_workload_joins_reset_and_cycle_tasks(tmp_path: Path) -> None:
    recovery = asyncio.Event()
    recovery.set()
    entered, reset_joined, cycle_joined = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def apply(owner: UUID, key: UUID) -> UUID:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            reset_joined.set()
        return key

    async def cycles() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cycle_joined.set()

    progress = resets.ResetProgress(1)
    task = asyncio.create_task(
        resets.run_scheduled_work(
            cycles(),
            resets.run_resets(
                [resets.ScheduledReset(UUID(int=1), 0, UUID(int=2))],
                started=monotonic(),
                recovery_complete=recovery,
                apply=apply,
                path=tmp_path / "cancel.jsonl",
                progress=progress,
            ),
        )
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert reset_joined.is_set() and cycle_joined.is_set()
    assert progress.failed == 1 and not progress.passed


async def test_fault_error_is_not_hidden_by_other_task_cleanup() -> None:
    joined = [asyncio.Event(), asyncio.Event()]
    entered = asyncio.Event()
    original = RuntimeError("fault failed")

    async def blocked(index: int) -> None:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined[index].set()
            raise RuntimeError("secondary cleanup error")

    async def fault() -> None:
        await entered.wait()
        raise original

    with pytest.raises(RuntimeError) as caught:
        await resets.run_scheduled_work(blocked(0), blocked(1), fault())
    assert caught.value is original and all(e.is_set() for e in joined)


async def test_temporary_breach_limit_is_restored_only_after_its_oracles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.infra.execution_market.test_dispatch import intent
    from tiewtrade.infra.risk_limits.records import RiskAction

    owner: Any = SimpleNamespace(user_id=UUID(int=1))
    fixture: Any = SimpleNamespace(
        output=tmp_path,
        selected=owner.user_id,
        engine=None,
        partial_ready=asyncio.Event(),
        recovery_complete=asyncio.Event(),
        selected_limit_restore=None,
    )
    calls: list[str] = []
    counters = f15.Counters()
    buy = intent(owner.user_id, UUID(int=2))

    async def new(*args: Any) -> None:
        counters.offered += 1
        counters.admitted += 1
        counters.completed += 1

    async def breach(*args: Any) -> None:
        assert not fixture.recovery_complete.is_set()
        calls.append("breach/reset/reseed at limit5")

    async def correction(*args: Any) -> None:
        assert not fixture.recovery_complete.is_set()
        calls.append("correction")

    async def mutation(who: Any, action: RiskAction, amount: str) -> UUID:
        assert action is RiskAction.INCREASE and amount == "1000"
        assert counters.completed == 5 and calls == ["breach/reset/reseed at limit5", "correction"]
        calls.append("restore standard limit")
        return UUID(int=700)

    fixture.new, fixture.breach_reset = new, breach
    fixture.correction, fixture.mutation = correction, mutation
    fixture.request = AsyncMock(return_value=SimpleNamespace(state="SUCCEEDED", failure_code=None))
    monkeypatch.setattr(f15, "market_buy", lambda *args: buy)
    for name in ("limit_sell", "market_sell"):
        monkeypatch.setattr(f15, name, lambda *args: SimpleNamespace(order_id=UUID(int=3)))
    monkeypatch.setattr(f15, "wait_status", AsyncMock())
    engine: Any = None
    async with workload.Fixture.cycle_scope(fixture, owner, 0):
        await workload.Fixture.cycle(fixture, engine, owner, UUID(int=4), 0, counters, [])
    assert fixture.recovery_complete.is_set() and fixture.selected_limit_restore == UUID(int=700)
