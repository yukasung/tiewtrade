"""Known cycle expiry is a failed criterion; nested timeout/cancellation stay distinct."""

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as workload


@pytest.mark.parametrize("fault_gate", [False, True])
@pytest.mark.parametrize("inner_timeout", [False, True])
async def test_only_expired_cycle_budget_has_failure_identity(
    monkeypatch: pytest.MonkeyPatch, fault_gate: bool, inner_timeout: bool
) -> None:
    original = asyncio.timeout
    requested: list[float | None] = []

    def short_budget(seconds: float | None) -> asyncio.Timeout:
        requested.append(seconds)
        return original(0.01)

    async def cycle(*args: Any, **kwargs: Any) -> None:
        if inner_timeout:
            raise TimeoutError("inner transport timeout")
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "timeout", short_budget)
    monkeypatch.setattr(workload, "cycle", cycle)
    owner = cast(workload.OwnerState, SimpleNamespace(user_id=uuid4()))
    gate = workload.FaultGate() if fault_gate else None
    with pytest.raises(TimeoutError) as failure:
        await workload.run_scheduled_cycles(
            cast(AsyncEngine, None),
            [owner],
            uuid4(),
            1,
            1000,
            workload.Counters(),
            [],
            gate,
        )
    assert isinstance(failure.value, workload.CycleBudgetExceededError) is not inner_timeout
    assert requested == [60]
    if gate is not None:
        assert gate.active == 0


async def test_external_cancellation_is_not_budget_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()

    async def cycle(*args: Any, **kwargs: Any) -> None:
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(workload, "cycle", cycle)
    owner = cast(workload.OwnerState, SimpleNamespace(user_id=uuid4()))
    task = asyncio.create_task(
        workload.run_scheduled_cycles(
            cast(AsyncEngine, None),
            [owner],
            uuid4(),
            1,
            1000,
            workload.Counters(),
            [],
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
