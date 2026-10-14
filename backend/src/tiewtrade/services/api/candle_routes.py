from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from tiewtrade.core.market_data import CandleFinality, CandleWindow, Timeframe, initial_window
from tiewtrade.core.money import MoneyError, Quantity
from tiewtrade.core.timeframes import (
    advance,
    align_floor,
    chart_display_start,
    next_open,
    retention_cutoff,
)
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.db.session import indicator_read_session
from tiewtrade.infra.market_data.chart_overlay import overlay_preview
from tiewtrade.infra.market_data.records import MarketDataInputError, StoredCandle
from tiewtrade.infra.market_data.storage import database_now, enqueue, parameters, read_candles
from tiewtrade.services.api.authentication import Authenticated, current_user
from tiewtrade.services.api.resources import engine_for
from tiewtrade.services.api.safe_input_routes import SafeInputRoute


class _CandleInputRoute(SafeInputRoute):
    rejection_code = "INPUT_REJECTED"


class RejectedCandleInput(BaseModel):
    detail: str


router = APIRouter(
    prefix="/market-data/candles",
    tags=["market-data"],
    route_class=_CandleInputRoute,
    responses={422: {"model": RejectedCandleInput}},
)


class CandleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: str
    quote: str
    timeframe: Timeframe
    start: datetime | None = None
    end: datetime | None = None


class CandleQuery(CandleRequest):
    limit: int = Field(default=1000, ge=1, le=1000)


class WindowView(BaseModel):
    start: datetime
    end: datetime


class CandleView(BaseModel):
    open_at: datetime
    end_at: datetime
    open: str
    high: str
    low: str
    close: str
    volume: str
    finality: CandleFinality
    observed_at: datetime
    last_checked_at: datetime


class CandleHistoryView(BaseModel):
    base: str
    quote: str
    timeframe: Timeframe
    requested: WindowView
    observed: WindowView | None
    rows: list[CandleView]
    gaps: list[WindowView]
    coverage: Literal["PRESENT", "INCOMPLETE", "UNAVAILABLE"]
    observed_at: datetime
    refresh_pending: bool
    status: str | None
    failure_code: str | None


class CandleRequestView(BaseModel):
    accepted: bool


class ChartPageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: str
    quote: str
    timeframe: Timeframe
    before: datetime | None = None
    after: datetime | None = None


class ChartCandlePage(CandleHistoryView):
    display_start: datetime
    display_end: datetime
    earliest_known: bool
    older_before: datetime | None
    newer_after: datetime | None


@router.get("/pages")
async def candle_page(
    query: Annotated[ChartPageQuery, Query()],
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> ChartCandlePage:
    try:
        tf = query.timeframe
        base, quote = Quantity.of(0, query.base).asset, Quantity.of(0, query.quote).asset
        if query.before is not None and query.after is not None:
            raise ValueError("only one page direction")
        engine = engine_for(request, DatabaseRole.API)
        async with indicator_read_session(engine, who.user_id) as session:
            now = await database_now(session)
            upper = next_open(align_floor(now, tf), tf)
            known = True
            if tf in (Timeframe.W1, Timeframe.MN1):
                oldest = (
                    await session.execute(
                        """SELECT history_start FROM market_candle_demand WHERE source=:source
                    AND base=:base AND quote=:quote AND timeframe=:timeframe""",
                        parameters(base, quote, tf),
                    )
                ).scalar_one_or_none()
                known = oldest is not None
                lower = oldest or align_floor(retention_cutoff(now, tf), tf)
            else:
                lower = chart_display_start(now, tf)
            for boundary in (query.before, query.after):
                if boundary is not None and (
                    boundary != align_floor(boundary, tf) or not lower <= boundary <= upper
                ):
                    raise ValueError("page boundary outside chart history")
            if query.after is not None:
                start = query.after
                end = min(upper, advance(start, tf, 1000))
            else:
                end = query.before or upper
                start = max(lower, advance(end, tf, -1000))
            window = CandleWindow(start, end)
            result = await read_candles(session, base, quote, tf, window, 1000)
            needs_backfill = result.coverage != "PRESENT"
            result = await overlay_preview(session, base, quote, tf, window, result)
        if needs_backfill:
            async with user_session(engine, who.user_id) as session:
                await enqueue(session, base, quote, tf, window)
        rows = [_candle_view(stored) for stored in result.candles]
        return ChartCandlePage(
            base=base,
            quote=quote,
            timeframe=tf,
            requested=WindowView(start=start, end=end),
            observed=WindowView(start=rows[0].open_at, end=rows[-1].end_at) if rows else None,
            rows=rows,
            gaps=[WindowView(start=g.start, end=g.end) for g in result.gaps],
            coverage=result.coverage,
            observed_at=result.observed_at,
            refresh_pending=result.refresh_pending,
            status=result.status,
            failure_code=result.failure_code,
            display_start=lower,
            display_end=upper,
            earliest_known=known,
            older_before=min(end, advance(start, tf, 200)) if start > lower else None,
            newer_after=max(start, advance(end, tf, -200)) if end < upper else None,
        )
    except MarketDataInputError as error:
        raise HTTPException(422, error.code) from None
    except (ValueError, TypeError, MoneyError, OverflowError):
        raise HTTPException(422, "INPUT_REJECTED") from None


def _window(body: CandleRequest, now: datetime) -> CandleWindow:
    if body.start is None and body.end is None:
        return initial_window(body.timeframe, now)
    if body.start is None or body.end is None:
        raise ValueError("both bounds required")
    try:
        return CandleWindow(body.start, body.end)
    except OverflowError:
        raise ValueError("window bounds cannot be represented in UTC") from None


def _units(body: CandleRequest) -> tuple[str, str]:
    return Quantity.of(0, body.base).asset, Quantity.of(0, body.quote).asset


def _candle_view(stored: StoredCandle) -> CandleView:
    candle = stored.candle
    return CandleView(
        open_at=candle.open_at,
        end_at=candle.end_at,
        open=candle.open.as_parts()["amount"],
        high=candle.high.as_parts()["amount"],
        low=candle.low.as_parts()["amount"],
        close=candle.close.as_parts()["amount"],
        volume=candle.volume.as_parts()["quantity"],
        finality=candle.finality,
        observed_at=candle.observed_at,
        last_checked_at=stored.last_checked_at,
    )


@router.get("")
async def candles(
    query: Annotated[CandleQuery, Query()],
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> CandleHistoryView:
    try:
        base, quote = _units(query)
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            window = _window(query, await database_now(session))
            result = await read_candles(session, base, quote, query.timeframe, window, query.limit)
    except MarketDataInputError as error:
        raise HTTPException(422, error.code) from None
    except (ValueError, TypeError, MoneyError):
        raise HTTPException(422, "INPUT_REJECTED") from None
    rows = [_candle_view(stored) for stored in result.candles]
    observed = WindowView(start=rows[0].open_at, end=rows[-1].end_at) if rows else None
    return CandleHistoryView(
        base=base,
        quote=quote,
        timeframe=query.timeframe,
        requested=WindowView(start=window.start, end=window.end),
        observed=observed,
        rows=rows,
        gaps=[WindowView(start=gap.start, end=gap.end) for gap in result.gaps],
        coverage=result.coverage,
        observed_at=result.observed_at,
        refresh_pending=result.refresh_pending,
        status=result.status,
        failure_code=result.failure_code,
    )


@router.post("/requests", responses={202: {"model": CandleRequestView}})
async def request_candles(
    body: CandleRequest,
    request: Request,
    response: Response,
    who: Annotated[Authenticated, Depends(current_user)],
) -> CandleRequestView:
    try:
        base, quote = _units(body)
        async with user_session(engine_for(request, DatabaseRole.API), who.user_id) as session:
            window = _window(body, await database_now(session))
            pending = await enqueue(session, base, quote, body.timeframe, window)
    except MarketDataInputError as error:
        raise HTTPException(422, error.code) from None
    except (ValueError, TypeError, MoneyError):
        raise HTTPException(422, "INPUT_REJECTED") from None
    response.status_code = 202 if pending else 200
    return CandleRequestView(accepted=pending)
