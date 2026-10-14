"""Focused tests of diagnostic scheduling, not production capacity acceptance."""

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

spec = importlib.util.spec_from_file_location(
    "smoke_runner", Path(__file__).with_name("run_smoke.py")
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.asyncio
async def test_source_continues_while_observer_is_waiting(monkeypatch):
    stop = asyncio.Event()
    appended_twice = asyncio.Event()
    calls = 0

    async def append(source, ends):
        nonlocal calls
        calls += 1
        if calls == 2:
            appended_twice.set()

    monkeypatch.setattr(runner.capacity, "append", append)
    producer = asyncio.create_task(runner.maintain_source(None, {}, stop))
    try:
        # An observer can remain blocked without delaying the source producer.
        await asyncio.wait_for(appended_twice.wait(), 1)
        assert calls == 2
        stop.set()
        await asyncio.wait_for(producer, 1)
        assert calls == 2
    finally:
        producer.cancel()
        await asyncio.gather(producer, return_exceptions=True)


@pytest.mark.asyncio
async def test_source_failure_is_observable(monkeypatch):
    monkeypatch.setattr(
        runner.capacity, "append", AsyncMock(side_effect=RuntimeError("source failed"))
    )
    with pytest.raises(RuntimeError, match="source failed"):
        await runner.maintain_source(None, {}, asyncio.Event())


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds,micros,delay", [(120, 0, 60.1), (179, 500000, 0.6)])
async def test_admission_wait_uses_redis_clock(monkeypatch, seconds, micros, delay):
    redis = AsyncMock()
    redis.time.return_value = (seconds, micros)
    sleep = AsyncMock()
    monkeypatch.setattr(runner.asyncio, "sleep", sleep)
    await runner.next_admission_window(redis)
    sleep.assert_awaited_once_with(delay)
    redis.eval.assert_not_called()
