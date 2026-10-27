"""Harness timing must not consume the next probe's Redis window."""

import asyncio

import httpx
import pytest

from tests.services.indicator_builder.profile_capacity import SERIES, probes
from tests.services.indicator_builder.profile_capacity_steady import admission_phase_delay


@pytest.mark.parametrize(
    ("seconds", "micros", "expected"),
    [
        (120, 0, 5.0),
        (124, 500000, 0.5),
        (125, 0, 0.0),
        (125, 100000, 59.9),
        (179, 0, 6.0),
    ],
)
def test_alignment_uses_real_redis_window(seconds: int, micros: int, expected: float) -> None:
    delay = admission_phase_delay(seconds, micros)
    assert delay == pytest.approx(expected)
    assert 0 <= delay < 60
    assert (seconds % 60 + micros / 1_000_000 + delay) % 60 == pytest.approx(5)


async def test_rejection_before_barrier_is_not_masked_by_timeout() -> None:
    cancelled = asyncio.Event()

    async def barrier() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={"detail": "limited"}))
    async with httpx.AsyncClient(transport=transport, base_url="http://fixture") as client:
        with pytest.raises(RuntimeError, match="CAPACITY_BARRIER_REQUEST_REJECTED_429"):
            await probes([client, client], 0, barrier)
    assert cancelled.is_set()


async def test_success_can_finish_while_barrier_task_unwinds() -> None:
    async def barrier() -> None:
        await asyncio.sleep(0)

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    async with httpx.AsyncClient(transport=transport, base_url="http://fixture") as client:
        result = await probes([client, client], 0, barrier)
    assert len(result) == len(SERIES)
    assert all(row["status"] == 200 for row in result)


async def test_dirty_data_not_ready_can_finish_while_barrier_task_unwinds() -> None:
    completed = asyncio.Event()

    async def barrier() -> None:
        await asyncio.sleep(0.01)
        completed.set()

    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, json={"detail": "INDICATOR_DATA_NOT_READY"})
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://fixture") as client:
        result = await probes([client, client], 0, barrier)
    assert completed.is_set()
    assert len(result) == len(SERIES)
    assert all(row["status"] == 503 for row in result)


async def test_unavailable_admission_still_fails_before_barrier() -> None:
    async def barrier() -> None:
        await asyncio.Event().wait()

    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, json={"detail": "INDICATOR_ADMISSION_UNAVAILABLE"})
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://fixture") as client:
        with pytest.raises(RuntimeError, match="CAPACITY_BARRIER_REQUEST_REJECTED_503"):
            await probes([client, client], 0, barrier)
