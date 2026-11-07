"""Pure HTTP boundary checks; no API database fixtures or network access."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from pydantic import BaseModel

from tiewtrade.core.market_data import Timeframe
from tiewtrade.infra.realtime.admission import AdmissionOutcome
from tiewtrade.services.api.authentication import Authenticated
from tiewtrade.services.api.indicator_admission import IndicatorBudget
from tiewtrade.services.api.indicator_http import (
    ChunkedJSON,
    JSONFragments,
    _model_json_bytes,
    _without_automatic_gc,
    encode_json_fragment,
    indicator_response,
)


class Allowed:
    async def outcome(self, subject: str) -> AdmissionOutcome:
        return AdmissionOutcome.ACCEPTED


class Payload(BaseModel):
    text: str


class RowsPayload(BaseModel):
    rows: list[Payload]
    tail: str


def request(disconnected: asyncio.Event) -> tuple[Request, IndicatorBudget, Authenticated]:
    budget = IndicatorBudget()
    app = SimpleNamespace(
        state=SimpleNamespace(indicator_budget=budget, indicator_admission=Allowed())
    )

    async def receive() -> dict[str, object]:
        await disconnected.wait()
        return {"type": "http.disconnect"}

    req = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/market-data/chart/history",
            "headers": [],
            "app": app,
        },
        receive=receive,
    )
    who = Authenticated(uuid4(), "fixture-session", datetime.now(UTC) + timedelta(hours=1))
    return req, budget, who


@pytest.mark.parametrize("extra", [0, 1])
async def test_combined_chart_payload_exact_byte_limit(extra: int) -> None:
    req, budget, who = request(asyncio.Event())
    payload = Payload(text="x" * (2 * 1024 * 1024 - 11 + extra))

    async def work(deadline: float) -> BaseModel:
        return payload

    if extra:
        with pytest.raises(HTTPException) as rejected:
            await indicator_response(req, who, work, disconnect_response=True)
        assert rejected.value.status_code == 503
        assert rejected.value.detail == "INDICATOR_RESOURCE_LIMIT"
    else:
        result = await indicator_response(req, who, work, disconnect_response=True)
        assert len(result.body) == 2 * 1024 * 1024
        assert result.headers["cache-control"] == "private, no-store"
    assert not budget.busy


async def test_chunked_serialization_matches_pydantic() -> None:
    payload = RowsPayload(rows=[Payload(text=str(index)) for index in range(33)], tail="done")
    body = await _model_json_bytes(payload, 2, lambda: 1)
    assert body == payload.model_dump_json().encode()


async def test_preencoded_array_fragments_match_validated_model() -> None:
    expected = RowsPayload(rows=[Payload(text=str(index)) for index in range(33)], tail="done")
    shell = RowsPayload(rows=[], tail="done")
    payload = ChunkedJSON.from_model(
        shell,
        rows=JSONFragments(tuple(encode_json_fragment(row) for row in expected.rows)),
    )

    body = await _model_json_bytes(payload, 2, lambda: 1)

    assert body == expected.model_dump_json().encode()


async def test_large_work_restores_gc_after_collecting_released_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = True
    calls: list[str] = []

    def disable() -> None:
        nonlocal enabled
        enabled = False
        calls.append("disable")

    def enable() -> None:
        nonlocal enabled
        enabled = True
        calls.append("enable")

    async def work() -> str:
        assert not enabled
        return "done"

    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.isenabled", lambda: enabled)
    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.disable", disable)
    monkeypatch.setattr(
        "tiewtrade.services.api.indicator_http.gc.collect",
        lambda generation: calls.append(f"collect:{generation}"),
    )
    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.enable", enable)

    assert await _without_automatic_gc(work()) == "done"
    assert calls == ["disable", "collect:0", "enable"]
    assert enabled


async def test_large_work_restores_gc_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    enabled = True
    calls: list[str] = []

    def disable() -> None:
        nonlocal enabled
        enabled = False

    def enable() -> None:
        nonlocal enabled
        enabled = True
        calls.append("enable")

    async def failed() -> None:
        raise RuntimeError("expected")

    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.isenabled", lambda: enabled)
    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.disable", disable)
    monkeypatch.setattr(
        "tiewtrade.services.api.indicator_http.gc.collect",
        lambda generation: calls.append(f"collect:{generation}"),
    )
    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.enable", enable)

    with pytest.raises(RuntimeError, match="expected"):
        await _without_automatic_gc(failed())
    assert calls == ["collect:0", "enable"]
    assert enabled


async def test_large_work_restores_gc_after_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = True
    calls: list[str] = []

    def disable() -> None:
        nonlocal enabled
        enabled = False

    def enable() -> None:
        nonlocal enabled
        enabled = True
        calls.append("enable")

    async def cancelled() -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.isenabled", lambda: enabled)
    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.disable", disable)
    monkeypatch.setattr(
        "tiewtrade.services.api.indicator_http.gc.collect",
        lambda generation: calls.append(f"collect:{generation}"),
    )
    monkeypatch.setattr("tiewtrade.services.api.indicator_http.gc.enable", enable)

    with pytest.raises(asyncio.CancelledError):
        await _without_automatic_gc(cancelled())
    assert calls == ["collect:0", "enable"]
    assert enabled


async def test_chunked_serialization_checks_deadline_at_slice_boundary() -> None:
    payload = RowsPayload(rows=[Payload(text=str(index)) for index in range(16)], tail="done")
    with pytest.raises(TimeoutError):
        await _model_json_bytes(payload, 1, lambda: 1)


@pytest.mark.parametrize("repeated_cancel", [False, True])
async def test_cancelled_reader_holds_slot_until_cleanup_finishes(repeated_cancel: bool) -> None:
    disconnected, entered, cleanup, release = (asyncio.Event() for _ in range(4))
    req, budget, who = request(disconnected)

    async def work(deadline: float) -> BaseModel:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()
        return cast(BaseModel, None)

    task = asyncio.create_task(indicator_response(req, who, work, disconnect_response=True))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        disconnected.set()
        await asyncio.wait_for(cleanup.wait(), 1)
        assert budget.busy and not task.done()
        if repeated_cancel:
            for _ in range(2):
                task.cancel()
                await asyncio.sleep(0)
            assert budget.busy and not task.done()
        release.set()
        if repeated_cancel:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
        else:
            assert (await asyncio.wait_for(task, 1)).status_code == 499
        assert not budget.busy
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("offset", [-10000, 10000])
@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("stalled", [False, True])
async def test_clock_origin_does_not_change_success_or_timeout(
    monkeypatch: pytest.MonkeyPatch, offset: float, live: bool, stalled: bool
) -> None:
    from time import monotonic

    from tiewtrade.services.api import chart_routes

    req, budget, who = request(asyncio.Event())
    req.app.state.chart_admission = Allowed()
    monkeypatch.setenv("TIEWTRADE_CHART_ENABLED", "1")

    def clock() -> float:
        return monotonic() + offset

    monkeypatch.setattr(chart_routes, "monotonic", clock)
    entered, closed = asyncio.Event(), asyncio.Event()

    async def work(*args: object) -> Payload:
        entered.set()
        try:
            if stalled:
                await asyncio.Event().wait()
            await asyncio.sleep(0)
            return Payload(text="ready")
        finally:
            closed.set()

    monkeypatch.setattr(chart_routes, "_live", work)
    operation = (
        chart_routes.live(
            chart_routes.ChartLiveQuery(base="BTC", quote="USDT", timeframe=Timeframe.H1), req, who
        )
        if live
        else indicator_response(req, who, work, clock=clock, deadline_seconds=0.05)
    )
    # A watchdog fails if a positive origin offset accidentally extends the budget.
    if stalled:
        with pytest.raises(HTTPException) as caught:
            await asyncio.wait_for(operation, 3 if live else 1)
        assert caught.value.status_code == 504
        assert caught.value.detail == (
            "CHART_DEADLINE_EXCEEDED" if live else "INDICATOR_DEADLINE_EXCEEDED"
        )
    else:
        response = await asyncio.wait_for(operation, 1)
        assert response.status_code == 200
        assert response.body == b'{"text":"ready"}'
        assert response.headers["cache-control"] == "private, no-store"
    assert entered.is_set() and closed.is_set()
    assert not budget.busy


@pytest.mark.parametrize("elapsed,status", [(1.999, 200), (2, 504), (2.001, 504)])
async def test_live_serialization_keeps_exact_deadline(
    monkeypatch: pytest.MonkeyPatch, elapsed: float, status: int
) -> None:
    from tiewtrade.services.api import chart_routes

    req, _, who = request(asyncio.Event())
    req.app.state.chart_admission = Allowed()
    monkeypatch.setenv("TIEWTRADE_CHART_ENABLED", "1")
    now = [100.0]
    monkeypatch.setattr(chart_routes, "monotonic", lambda: now[0])

    class Serialized:
        def model_dump_json(self) -> str:
            now[0] += elapsed
            return "{}"

    async def work(*args: object) -> Serialized:
        return Serialized()

    monkeypatch.setattr(chart_routes, "_live", work)
    query = chart_routes.ChartLiveQuery(base="BTC", quote="USDT", timeframe=Timeframe.H1)
    operation = chart_routes.live(query, req, who)
    if status == 200:
        assert (await operation).status_code == 200
    else:
        with pytest.raises(HTTPException) as caught:
            await operation
        assert caught.value.status_code == status
        assert caught.value.detail == "CHART_DEADLINE_EXCEEDED"


@pytest.mark.parametrize("exhausted", [False, True])
async def test_shared_timeout_uses_remaining_budget_before_admission(exhausted: bool) -> None:
    req, budget, who = request(asyncio.Event())
    calls = 0
    entered = asyncio.Event()

    def clock() -> float:
        nonlocal calls
        calls += 1
        # Only 30ms remain at context entry, or the budget is already exhausted.
        if calls == 1:
            return 100.0
        return 101.0 if exhausted else 100.97

    async def work(deadline: float) -> BaseModel:
        assert deadline == 101.0
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    with pytest.raises(HTTPException) as caught:
        await asyncio.wait_for(
            indicator_response(req, who, work, clock=clock, deadline_seconds=1), 0.5
        )
    assert caught.value.status_code == 504
    if not exhausted:
        assert entered.is_set()
    assert not budget.busy


async def test_admission_and_work_share_one_deadline() -> None:
    req, budget, who = request(asyncio.Event())
    now = [100.0]

    class ConsumingAdmission:
        async def outcome(self, subject: str) -> AdmissionOutcome:
            now[0] += 20
            return AdmissionOutcome.ACCEPTED

    req.app.state.indicator_admission = ConsumingAdmission()

    async def work(deadline: float) -> BaseModel:
        assert deadline == 130
        now[0] += 10
        return Payload(text="too late")

    with pytest.raises(HTTPException) as caught:
        await indicator_response(req, who, work, clock=lambda: now[0])
    assert caught.value.status_code == 504
    assert not budget.busy
