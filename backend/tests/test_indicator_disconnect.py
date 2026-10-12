"""Approved V-15/R2-10: an ASGI disconnect must stop an active indicator read."""

import asyncio
from contextlib import suppress
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request

from tiewtrade.infra.db.errors import DatabaseTimeoutError
from tiewtrade.infra.db.session import _begin, _bounded_cleanup, indicator_read_session
from tiewtrade.infra.realtime.admission import AdmissionOutcome
from tiewtrade.services.api import indicator_routes as routes
from tiewtrade.services.api.authentication import Authenticated
from tiewtrade.services.api.indicator_admission import IndicatorBudget


class _AcceptedAdmission:
    async def outcome(self, user: str) -> AdmissionOutcome:
        return AdmissionOutcome.ACCEPTED


def _indicator_request(budget: IndicatorBudget, messages: asyncio.Queue[dict[str, Any]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/market-data/indicators",
            "headers": [],
            "app": SimpleNamespace(
                state=SimpleNamespace(
                    indicator_budget=budget, indicator_admission=_AcceptedAdmission()
                )
            ),
        },
        receive=messages.get,
    )


@pytest.mark.parametrize("cause", ["disconnect", "timeout", "cancel"])
@pytest.mark.parametrize("stalled_invalidate", [False, True])
async def test_stalled_cleanup_aborts_before_releasing_slot(
    monkeypatch: pytest.MonkeyPatch, cause: str, stalled_invalidate: bool
) -> None:
    entered, cleaning = asyncio.Event(), asyncio.Event()
    budget = IndicatorBudget()
    messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    children: list[asyncio.Task[Any]] = []
    detached = closed = invalidated = False

    class Driver:
        def terminate(self) -> None:
            nonlocal closed
            assert budget.busy and detached
            closed = True

    class Raw:
        driver_connection = Driver()

        def detach(self) -> None:
            nonlocal detached
            detached = True

    class Connection:
        async def invalidate(self) -> None:
            nonlocal invalidated
            assert closed and detached
            invalidated = True
            if stalled_invalidate:
                await asyncio.Event().wait()

    async def rollback() -> None:
        cleaning.set()
        await asyncio.Event().wait()

    async def read(*args: Any) -> Any:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup = asyncio.create_task(rollback())
            children.append(cleanup)
            with suppress(DatabaseTimeoutError):
                await _bounded_cleanup(cast(Any, Connection()), cast(Any, Raw()), cleanup, 0.2)

    monkeypatch.setattr(routes, "_read", read)
    if cause == "timeout":
        monkeypatch.setattr(routes, "INDICATOR_SETTINGS", SimpleNamespace(deadline_seconds=0.02))
    request = _indicator_request(budget, messages)
    who = cast(Authenticated, SimpleNamespace(user_id=uuid4()))
    task = asyncio.create_task(routes.indicators(routes.IndicatorQuery(), request, who))
    await asyncio.wait_for(entered.wait(), 1)
    if cause == "disconnect":
        await messages.put({"type": "http.disconnect"})
    elif cause == "cancel":
        task.cancel()
    await asyncio.wait_for(cleaning.wait(), 1)
    if cause == "cancel":
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
            assert budget.busy
    result = (await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 0.5))[0]
    assert closed and detached and invalidated and all(child.done() for child in children)
    assert not budget.busy
    if cause == "timeout":
        assert isinstance(result, HTTPException) and result.status_code == 504
    else:
        assert isinstance(result, asyncio.CancelledError)
    async with budget.reserve(cast(Any, _AcceptedAdmission()), who.user_id):
        assert budget.busy


@pytest.mark.parametrize("failed_body", [False, True])
@pytest.mark.parametrize("stalled_invalidate", [False, True])
async def test_postgres_stalled_exit_discards_transport_and_reuses_pool(
    api_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    failed_body: bool,
    stalled_invalidate: bool,
) -> None:
    # Exercise _begin itself, including the successful-body cleanup path.
    begin = AsyncEngine.begin
    physical: list[Any] = []
    exited = asyncio.Event()
    original_error = ValueError("body failed")

    class StalledExit:
        def __init__(self) -> None:
            self.context = begin(api_engine)

        async def __aenter__(self) -> Any:
            connection = await self.context.__aenter__()
            raw = await connection.get_raw_connection()
            physical.append(raw.driver_connection)
            if stalled_invalidate:

                async def invalidate(*args: Any, **kwargs: Any) -> None:
                    await asyncio.Event().wait()

                monkeypatch.setattr(type(connection), "invalidate", invalidate)
            return connection

        async def __aexit__(self, *args: Any) -> Any:
            try:
                await asyncio.Event().wait()
            finally:
                try:
                    await self.context.__aexit__(*args)
                finally:
                    exited.set()

    monkeypatch.setattr(AsyncEngine, "begin", lambda self: StalledExit())
    started = monotonic()
    with pytest.raises(ValueError if failed_body else DatabaseTimeoutError) as caught:
        async with _begin(api_engine, cleanup_seconds=0.2) as connection:
            pid: int = (await connection.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            if failed_body:
                raise original_error
    assert monotonic() - started < 1
    if failed_body:
        assert caught.value is original_error
    assert physical[0].is_closed() and exited.is_set()
    assert cast(Any, api_engine.pool).checkedout() == 0
    monkeypatch.undo()
    async with api_engine.connect() as connection:
        assert (await connection.execute(text("SELECT pg_backend_pid()"))).scalar_one() != pid
        assert (await connection.execute(text("SELECT 1"))).scalar_one() == 1


async def test_fast_reader_does_not_restart_receive_after_swallowed_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    expected = cast(routes.IndicatorHistoryView, object())

    async def receive() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            # BaseHTTPMiddleware can finish its own cancelled receive group and
            # return a request message instead of propagating cancellation.
            return {"type": "http.request", "body": b"", "more_body": False}
        raise AssertionError("unreachable")

    async def read(*args: Any) -> routes.IndicatorHistoryView:
        return expected

    monkeypatch.setattr(routes, "_read", read)
    request = Request({"type": "http"}, receive=receive)
    who = cast(Authenticated, SimpleNamespace(user_id=uuid4()))
    result = await asyncio.wait_for(
        routes._read_until_disconnect(routes.IndicatorQuery(), request, who, monotonic() + 1),
        1,
    )
    assert result is expected and calls == 1


async def test_disconnect_cancels_reader_before_releasing_local_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = asyncio.Event()
    closed = asyncio.Event()
    messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    budget = IndicatorBudget()

    async def suspended_read(*args: Any) -> Any:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            # Production must join the reader before freeing the shared local slot.
            assert budget.busy
            closed.set()

    monkeypatch.setattr(routes, "_read", suspended_read)
    request = _indicator_request(budget, messages)
    who = cast(Authenticated, SimpleNamespace(user_id=uuid4()))
    task = asyncio.create_task(routes.indicators(routes.IndicatorQuery(), request, who))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await messages.put({"type": "http.disconnect"})
        # No caller-side task.cancel: an ASGI disconnect is not task cancellation.
        await asyncio.wait_for(closed.wait(), 2.5)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 1)
        assert not budget.busy
    finally:
        # Test teardown only; cannot make the assertion above pass.
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("cause", ["disconnect", "cancel", "timeout"])
async def test_cleanup_survives_repeated_cancel_and_slot_is_reusable(
    monkeypatch: pytest.MonkeyPatch, cause: str
) -> None:
    entered, cleaning, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
    messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    budget = IndicatorBudget()

    async def read(*args: Any) -> Any:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await finish.wait()
            assert budget.busy

    monkeypatch.setattr(routes, "_read", read)
    if cause == "timeout":
        monkeypatch.setattr(routes, "INDICATOR_SETTINGS", SimpleNamespace(deadline_seconds=0.05))
    request = _indicator_request(budget, messages)
    who = cast(Authenticated, SimpleNamespace(user_id=uuid4()))
    task = asyncio.create_task(routes.indicators(routes.IndicatorQuery(), request, who))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if cause == "disconnect":
            await messages.put({"type": "http.request", "body": b"", "more_body": False})
            await messages.put({"type": "http.disconnect"})
        elif cause == "cancel":
            task.cancel()
        await asyncio.wait_for(cleaning.wait(), 1)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
            assert budget.busy and not task.done()
        finish.set()
        result = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 1)
        assert isinstance(result[0], asyncio.CancelledError)
        assert not budget.busy
        async with budget.reserve(cast(Any, _AcceptedAdmission()), who.user_id):
            assert bool(budget.busy)
        assert not budget.busy
    finally:
        finish.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("cause", ["disconnect", "timeout", "cancel"])
async def test_postgres_query_stops_and_pool_is_reusable(
    api_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    cause: str,
) -> None:
    entered = asyncio.Event()
    messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    budget = IndicatorBudget()
    user_id = uuid4()

    async def read(*args: Any) -> Any:
        async with indicator_read_session(api_engine, user_id) as session:
            entered.set()
            await session.execute("SELECT pg_sleep(20)")

    monkeypatch.setattr(routes, "_read", read)
    if cause == "timeout":
        monkeypatch.setattr(routes, "INDICATOR_SETTINGS", SimpleNamespace(deadline_seconds=0.2))
    request = _indicator_request(budget, messages)
    who = cast(Authenticated, SimpleNamespace(user_id=user_id))
    task = asyncio.create_task(routes.indicators(routes.IndicatorQuery(), request, who))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        started = monotonic()
        if cause == "disconnect":
            await messages.put({"type": "http.disconnect"})
        elif cause == "cancel":
            task.cancel()
        result = (await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 3))[0]
        assert monotonic() - started < 2
        if cause == "timeout":
            assert isinstance(result, HTTPException) and result.status_code == 504
        else:
            assert isinstance(result, asyncio.CancelledError)
        assert not budget.busy
        assert cast(Any, api_engine.pool).checkedout() == 0
        async with (
            budget.reserve(cast(Any, _AcceptedAdmission()), user_id),
            indicator_read_session(api_engine, user_id) as session,
        ):
            assert (await session.execute("SELECT 1")).scalar_one() == 1
        assert cast(Any, api_engine.pool).checkedout() == 0
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
