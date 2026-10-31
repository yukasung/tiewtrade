"""Separate recovery budget without sleeping through minute-long acceptance bounds."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits import profile_timing as timing
from tests.infra.risk_limits.profile_workload import Fixture


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now

    def timeout(self, seconds: float) -> Any:
        clock = self

        class Timeout:
            end = clock.now + seconds

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, kind: Any, error: Any, tb: Any) -> bool:
                if kind is None and self.expired():
                    raise TimeoutError()
                return False

            def when(self) -> float:
                return self.end

            def expired(self) -> bool:
                return clock.now > self.end

            def reschedule(self, end: float) -> None:
                self.end = end

        return Timeout()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(timing, "monotonic", clock)
    monkeypatch.setattr(timing, "asyncio", SimpleNamespace(timeout=clock.timeout))
    return clock


@pytest.mark.parametrize(
    "before,recovery,after,passed",
    [
        (30, 120, 30, True),
        (0, 120, 60, True),
        (61, 1, 0, False),
        (1, 1, 60, False),
        (0, 121, 0, False),
        (59, 120, 2, False),
    ],
)
async def test_normal_and_recovery_budgets_are_independent(
    tmp_path: Path, clock: Clock, before: int, recovery: int, after: int, passed: bool
) -> None:
    path = tmp_path / "cycles.jsonl"

    async def run() -> None:
        async with timing.cycle_scope(path, owner=UUID(int=1), number=0, recovery_allowed=True):
            clock.now += before
            async with (
                timing.recovery_scope(),
                timing.recovery_stage("reseed-1", order_id=UUID(int=2)),
            ):
                clock.now += recovery
            clock.now += after

    if passed:
        await run()
    else:
        with pytest.raises(TimeoutError):
            await run()
    record = json.loads(path.read_text())
    assert record["outcome"] == ("completed" if passed else "TimeoutError")
    if passed:
        assert record["normal_seconds"] == before + after
        assert record["recovery_seconds"] == recovery and record["seconds"] <= 180
        assert record["stages"][0]["order_id"] == str(UUID(int=2))


@pytest.mark.parametrize("owner,number,allowed", [(1, 0, True), (2, 0, False), (1, 1, False)])
async def test_only_selected_first_cycle_gets_one_recovery(
    tmp_path: Path, clock: Clock, owner: int, number: int, allowed: bool
) -> None:
    fixture: Any = SimpleNamespace(output=tmp_path, selected=UUID(int=1))
    identity: Any = SimpleNamespace(user_id=UUID(int=owner))
    async with Fixture.cycle_scope(fixture, identity, number):
        if allowed:
            async with timing.recovery_scope():
                clock.now += 100
            with pytest.raises(RuntimeError):
                async with timing.recovery_scope():
                    pass
            with pytest.raises(RuntimeError):
                async with timing.recovery_stage("outside"):
                    pass
        else:
            with pytest.raises(RuntimeError):
                async with timing.recovery_scope():
                    pass


@pytest.mark.parametrize("with_gate", [False, True])
async def test_f15_default_still_has_sixty_second_cycle(
    monkeypatch: pytest.MonkeyPatch, clock: Clock, with_gate: bool
) -> None:
    monkeypatch.setattr(
        f15, "asyncio", SimpleNamespace(**{**vars(asyncio), "timeout": clock.timeout})
    )
    monkeypatch.setattr(f15, "monotonic", clock)

    async def cycle(*args: Any) -> None:
        clock.now += 61

    monkeypatch.setattr(f15, "cycle", cycle)
    engine: Any = None
    owner: Any = SimpleNamespace(user_id=UUID(int=1))
    with pytest.raises(TimeoutError):
        await f15.run_scheduled_cycles(
            engine,
            [owner],
            UUID(int=2),
            1,
            10,
            f15.Counters(),
            [],
            f15.FaultGate() if with_gate else None,
        )


async def test_cancellation_preserves_stage_failure_and_resets_scope(tmp_path: Path) -> None:
    entered = asyncio.Event()

    async def run() -> None:
        async with (
            timing.cycle_scope(
                tmp_path / "cancel.jsonl", owner=UUID(int=1), number=0, recovery_allowed=True
            ),
            timing.recovery_scope(),
            timing.recovery_stage("reset"),
        ):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(run())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    record = json.loads((tmp_path / "cancel.jsonl").read_text())
    assert record["outcome"] == record["stages"][0]["outcome"] == "CancelledError"
    with pytest.raises(RuntimeError):
        async with timing.recovery_scope():
            pass


@pytest.mark.parametrize("with_gate", [False, True])
async def test_scheduler_uses_explicit_recovery_scope_without_changing_counters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock, with_gate: bool
) -> None:
    monkeypatch.setattr(f15, "monotonic", clock)
    counters = f15.Counters()
    owner: Any = SimpleNamespace(user_id=UUID(int=1))
    engine: Any = None

    async def cycle(*args: Any) -> None:
        clock.now += 30
        async with timing.recovery_scope():
            clock.now += 100
        clock.now += 20
        counters.completed += 5
        counters.cycles += 1

    def scope(owner: Any, number: int) -> Any:
        return timing.cycle_scope(
            tmp_path / "scheduled.jsonl", owner=owner.user_id, number=number, recovery_allowed=True
        )

    monkeypatch.setattr(f15, "cycle", cycle)
    await f15.run_scheduled_cycles(
        engine,
        [owner],
        UUID(int=2),
        1,
        10,
        counters,
        [],
        f15.FaultGate() if with_gate else None,
        cycle_scope=scope,
    )
    assert counters.completed == 5 and counters.cycles == 1
    record = json.loads((tmp_path / "scheduled.jsonl").read_text())
    assert record["seconds"] == 150 and record["normal_seconds"] == 50


async def test_recovery_evidence_cannot_be_silently_omitted(tmp_path: Path, clock: Clock) -> None:
    with pytest.raises(RuntimeError, match="evidence missing"):
        async with timing.cycle_scope(
            tmp_path / "missing.jsonl", owner=UUID(int=1), number=0, recovery_allowed=True
        ):
            clock.now += 1
