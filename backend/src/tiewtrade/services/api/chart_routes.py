"""Authenticated coherent chart reads; preview never enters indicator inputs."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import CandleFinality, CandleSeries, Timeframe
from tiewtrade.core.money import MoneyError
from tiewtrade.infra.crypto.chart_proof import issue_display, verify_display
from tiewtrade.infra.crypto.indicator_cursor import (
    DatasetChangedError,
    PreparedCursorClaims,
    check_expiry,
)
from tiewtrade.infra.crypto.keys import KeySource
from tiewtrade.infra.db.errors import DatabaseTimeoutError, InfraError
from tiewtrade.infra.db.session import indicator_read_session
from tiewtrade.infra.indicators.prepared import PreparedNotReadyError
from tiewtrade.infra.market_data.candle_preview import read_live
from tiewtrade.infra.market_data.chart_reader import verify_prepared
from tiewtrade.infra.market_data.records import MarketDataInputError
from tiewtrade.infra.market_data.storage import database_now
from tiewtrade.infra.realtime.admission import AdmissionOutcome, RedisAdmission
from tiewtrade.services.api.authentication import Authenticated, current_user
from tiewtrade.services.api.candle_routes import CandleView, _candle_view
from tiewtrade.services.api.indicator_http import (
    ClientDisconnectedError,
    indicator_response,
    until_disconnect,
)
from tiewtrade.services.api.indicator_read_controller import (
    IndicatorHistoryView,
    IndicatorQuery,
    check_read_session,
    read_history,
)
from tiewtrade.services.api.safe_input_routes import SafeInputRoute


class ChartInputRoute(SafeInputRoute):
    rejection_code = "INPUT_REJECTED"


router = APIRouter(prefix="/market-data/chart", tags=["market-data"], route_class=ChartInputRoute)


class ChartHistoryView(IndicatorHistoryView):
    candles: list[CandleView]
    display_proof: str


class ChartProofRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_proof: str = Field(max_length=4096)


class ChartProofView(BaseModel):
    status: Literal["MATCHED", "CHANGED", "UNVERIFIABLE"]
    checked_at: datetime
    calculation_start: datetime | None = None
    calculation_end: datetime | None = None


class ChartLiveQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: str
    quote: str
    timeframe: Timeframe


class ChartLiveView(BaseModel):
    source: str
    base: str
    quote: str
    timeframe: Timeframe
    rows: list[CandleView]
    status: Literal["READY", "RECOVERING", "STALE", "NO_DATA", "UNAVAILABLE"]
    reason: str | None
    server_time: datetime
    epoch: str
    revision: str | None
    event_at: datetime | None
    received_at: datetime | None
    history_end: datetime | None


def require_enabled() -> None:
    if os.environ.get("TIEWTRADE_CHART_ENABLED") != "1":
        raise HTTPException(404, "CHART_DISABLED")


async def _live(query: ChartLiveQuery, request: Request, who: Authenticated) -> ChartLiveView:
    series = CandleSeries(query.base, query.quote, query.timeframe)
    engine = cast(AsyncEngine, request.app.state.chart_engine)
    async with indicator_read_session(
        engine, who.user_id, statement_timeout_ms=500, lock_timeout_ms=200
    ) as session:
        state, rows, now, recovered = await read_live(session, series)
        await check_read_session(session, who)
    latest = rows[-1] if rows else None
    status: Literal["READY", "RECOVERING", "STALE", "NO_DATA", "UNAVAILABLE"] = "NO_DATA"
    if latest is None and state["failure_code"] not in (None, "RECOVERING"):
        status = "UNAVAILABLE"
    if latest is not None:
        status = "RECOVERING"
        if latest["event_at"] > now + timedelta(seconds=2) or latest[
            "received_at"
        ] > now + timedelta(seconds=2):
            status = "UNAVAILABLE"
        elif now - latest["event_at"] > timedelta(seconds=6) or now - latest[
            "received_at"
        ] > timedelta(seconds=6):
            status = "STALE"
        elif (
            state["connected"]
            and state["lease_until"] > now
            and latest["epoch"] == state["epoch"]
            and recovered
        ):
            status = "READY"
    return ChartLiveView(
        source=state["source"],
        base=series.base,
        quote=series.quote,
        timeframe=series.timeframe,
        rows=[
            CandleView(
                open_at=row["open_at"],
                end_at=row["end_at"],
                open=str(row["open"]),
                high=str(row["high"]),
                low=str(row["low"]),
                close=str(row["close"]),
                volume=str(row["volume"]),
                finality=CandleFinality.UNCONFIRMED
                if now >= row["end_at"]
                else CandleFinality(row["finality"]),
                observed_at=row["received_at"],
                last_checked_at=row["received_at"],
            )
            for row in rows
            if not row["settled"]
        ],
        status=status,
        reason=state["failure_code"],
        server_time=now,
        epoch=str(state["epoch"]),
        revision=str(latest["revision"]) if latest is not None else None,
        event_at=latest["event_at"] if latest is not None else None,
        received_at=latest["received_at"] if latest is not None else None,
        history_end=latest["open_at"] if latest is not None and recovered else None,
    )


@router.get("/live", response_model=ChartLiveView)
async def live(
    query: Annotated[ChartLiveQuery, Query()],
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Response:
    require_enabled()
    deadline = monotonic() + 2
    try:
        async with asyncio.timeout_at(deadline):
            admission = cast(RedisAdmission, request.app.state.chart_admission)
            outcome = await admission.outcome(str(who.user_id))
            if outcome is AdmissionOutcome.DENIED:
                raise HTTPException(429, "CHART_RATE_LIMITED", headers={"Retry-After": "60"})
            if outcome is AdmissionOutcome.UNAVAILABLE:
                raise HTTPException(503, "CHART_ADMISSION_UNAVAILABLE")
            result = await until_disconnect(request, _live(query, request, who))
            body = result.model_dump_json().encode()
            if monotonic() >= deadline:
                raise TimeoutError()
            return Response(
                body, media_type="application/json", headers={"Cache-Control": "private, no-store"}
            )
    except ClientDisconnectedError:
        return Response(status_code=499, headers={"Cache-Control": "private, no-store"})
    except (MoneyError, MarketDataInputError):
        raise HTTPException(422, "INPUT_REJECTED") from None
    except (TimeoutError, DatabaseTimeoutError):
        raise HTTPException(504, "CHART_DEADLINE_EXCEEDED") from None
    except InfraError:
        raise HTTPException(503, "CHART_DATA_UNAVAILABLE") from None


async def _history(
    query: IndicatorQuery, request: Request, who: Authenticated, deadline: float
) -> ChartHistoryView:
    result = await read_history(query, request, who, deadline, with_candles=True)
    keys = cast(KeySource, request.app.state.indicator_keys)
    return ChartHistoryView(
        **result.view.model_dump(),
        candles=[_candle_view(row) for row in result.candles],
        display_proof=issue_display(result.claims, keys, who.user_id, who.token_hash),
    )


@router.get("/history", response_model=ChartHistoryView)
async def history(
    query: Annotated[IndicatorQuery, Query()],
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Response:
    require_enabled()
    return await indicator_response(
        request,
        who,
        lambda deadline: _history(query, request, who, deadline),
        disconnect_response=True,
    )


async def _verify(
    body: ChartProofRequest, request: Request, who: Authenticated, deadline: float
) -> ChartProofView:
    keys = cast(KeySource, request.app.state.indicator_keys)
    # Validate the MAC before opening a database read. Session is bound by the MAC.
    try:
        claims = verify_display(body.display_proof, keys, who.user_id, who.token_hash)
    except DatasetChangedError:
        return ChartProofView(status="CHANGED", checked_at=datetime.now(UTC))
    try:
        if isinstance(claims, PreparedCursorClaims):
            engine = cast(AsyncEngine, request.app.state.indicator_engine)
            async with indicator_read_session(engine, who.user_id) as session:
                now = await database_now(session)
                check_expiry(claims, now)
                checked = await verify_prepared(session, claims, now, deadline)
                finished = await database_now(session)
                await check_read_session(session, who, finished)
                check_expiry(claims, finished)
            return ChartProofView(
                status=checked,
                checked_at=finished,
                calculation_start=claims.calculation_start,
                calculation_end=claims.calculation_end,
            )
        result = await read_history(
            IndicatorQuery(), request, who, deadline, claims_override=claims
        )
        checked_at = result.checked_at
        status: Literal["MATCHED", "CHANGED", "UNVERIFIABLE"] = "MATCHED"
    except DatasetChangedError:
        checked_at, status = datetime.now(UTC), "CHANGED"
    except PreparedNotReadyError:
        checked_at, status = datetime.now(UTC), "UNVERIFIABLE"
    if monotonic() >= deadline:
        raise TimeoutError()
    return ChartProofView(
        status=status,
        checked_at=checked_at,
        calculation_start=claims.calculation_start,
        calculation_end=claims.calculation_end,
    )


@router.post("/verify", response_model=ChartProofView)
async def verify_chart(
    body: ChartProofRequest, request: Request, who: Annotated[Authenticated, Depends(current_user)]
) -> Response:
    require_enabled()
    return await indicator_response(
        request,
        who,
        lambda deadline: _verify(body, request, who, deadline),
        disconnect_response=True,
    )
