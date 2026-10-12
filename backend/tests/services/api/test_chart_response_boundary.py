"""Pure HTTP boundary checks; no API database fixtures or network access."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from pydantic import BaseModel

from tiewtrade.infra.realtime.admission import AdmissionOutcome
from tiewtrade.services.api.authentication import Authenticated
from tiewtrade.services.api.indicator_admission import IndicatorBudget
from tiewtrade.services.api.indicator_http import indicator_response


class Allowed:
    async def outcome(self, subject: str) -> AdmissionOutcome:
        return AdmissionOutcome.ACCEPTED


class Payload(BaseModel):
    text: str


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
