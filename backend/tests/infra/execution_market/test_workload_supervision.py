"""The workload must preserve the first producer failure and join abandoned work."""

import asyncio

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
