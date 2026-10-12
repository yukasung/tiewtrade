"""Authenticated, read-only F-11 API."""

import asyncio
from datetime import datetime, timedelta
from time import monotonic
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.indicators import FORMULA_VERSION
from tiewtrade.core.market_data import (
    CandleWindow,
    Timeframe,
    align_ceil,
    align_floor,
    retention_cutoff,
)
from tiewtrade.core.money import Money, MoneyError, Quantity, Scalar
from tiewtrade.infra.crypto.indicator_cursor import (
    CursorClaims,
    CursorRejectedError,
    DatasetChangedError,
    PreparedCursorClaims,
    check_expiry,
    issue,
    verify,
)
from tiewtrade.infra.crypto.keys import KeySource
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.db.session import PRESENTED_TOKEN_SETTING, indicator_read_session
from tiewtrade.infra.indicators.codec import CheckpointCodecError
from tiewtrade.infra.indicators.prepared import (
    PreparedNotReadyError,
    PreparedNumericError,
    read_prepared,
    rollout_control,
)
from tiewtrade.infra.market_data.catalog import SOURCE
from tiewtrade.infra.market_data.indicator_reader import read_indicators
from tiewtrade.infra.market_data.records import MarketDataInputError
from tiewtrade.infra.market_data.storage import database_now, parameters
from tiewtrade.infra.realtime.admission import RedisAdmission
from tiewtrade.services.api.authentication import Authenticated, current_user
from tiewtrade.services.api.indicator_admission import IndicatorBudget
from tiewtrade.services.api.indicator_settings import INDICATOR_SETTINGS
from tiewtrade.services.api.safe_input_routes import SafeInputRoute


class IndicatorQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: str | None = None
    quote: str | None = None
    timeframe: Timeframe | None = None
    start: datetime | None = None
    end: datetime | None = None
    page_size: int | None = Field(default=None, ge=1, le=1000)
    cursor: str | None = Field(default=None, max_length=4096)


class IndicatorValueView(BaseModel):
    value: str | None
    unit: str | None
    status: str


class IndicatorPointView(BaseModel):
    open_at: datetime
    seed_open_at: datetime | None
    finality: str | None
    values: dict[str, IndicatorValueView]


class RefreshTarget(BaseModel):
    base: str
    quote: str
    timeframe: Timeframe
    start: datetime
    end: datetime


class RefreshView(BaseModel):
    required: bool
    target: RefreshTarget | None
    more_required: bool
    queue_status: str | None
    failure_code: str | None
    observed_at: datetime


class IndicatorHistoryView(BaseModel):
    source: str
    base: str
    quote: str
    timeframe: Timeframe
    formula_version: str
    dataset_revision: str
    as_of: datetime
    calculation_start: datetime
    calculation_end: datetime
    result_start: datetime
    result_end: datetime
    rows: list[IndicatorPointView]
    refresh: RefreshView
    next_cursor: str | None
    generation_id: UUID | None = None
    prepared_at: datetime | None = None
    generation_age_seconds: int | None = None


class IndicatorInputRoute(SafeInputRoute):
    rejection_code = "INPUT_REJECTED"


router = APIRouter(
    prefix="/market-data/indicators", tags=["market-data"], route_class=IndicatorInputRoute
)


def _claims(
    query: IndicatorQuery, who: Authenticated, now: datetime, keys: KeySource
) -> CursorClaims:
    if query.cursor is not None:
        if query.model_fields_set != {"cursor"}:
            raise CursorRejectedError()
        claims = verify(query.cursor, keys, who.user_id, who.token_hash)
        check_expiry(claims, now)
        if claims.source != SOURCE:
            raise CursorRejectedError()
        parameters(claims.base, claims.quote, claims.timeframe)
        return claims
    if query.base is None or query.quote is None or query.timeframe is None:
        raise CursorRejectedError()
    try:
        base, quote = Quantity.of(0, query.base).asset, Money.of(0, query.quote).currency
    except MoneyError:
        raise CursorRejectedError() from None
    parameters(base, quote, query.timeframe)
    lower = align_ceil(retention_cutoff(now), query.timeframe)
    upper = align_floor(now, query.timeframe)
    if (query.start is None) != (query.end is None):
        raise CursorRejectedError()
    start = query.start or max(lower, upper - 1000 * query.timeframe.span)
    end = query.end or upper
    if start.tzinfo is None or end.tzinfo is None:
        raise CursorRejectedError()
    if start < lower or end > upper:
        raise HTTPException(422, "RANGE_OUTSIDE_RETENTION")
    if (
        start >= end
        or align_floor(start, query.timeframe) != start
        or align_floor(end, query.timeframe) != end
    ):
        raise CursorRejectedError()
    return CursorClaims(
        source=SOURCE,
        base=base,
        quote=quote,
        timeframe=query.timeframe,
        dataset_revision="",
        calculation_start=lower,
        calculation_end=upper,
        as_of=now,
        result_start=start,
        result_end=end,
        next_open_at=start,
        page_size=query.page_size or 1000,
        issued_at=now,
        expires_at=min(now + timedelta(hours=6), who.absolute_expires_at),
    )


async def _read(
    query: IndicatorQuery, request: Request, who: Authenticated, deadline: float
) -> IndicatorHistoryView:
    keys = cast(KeySource, request.app.state.indicator_keys)
    engine = cast(AsyncEngine, request.app.state.indicator_engine)
    async with indicator_read_session(engine, who.user_id) as session:
        now = await database_now(session)
        claims = _claims(query, who, now, keys)
        control = await rollout_control(session, deadline)
        prepared = None
        if control["mode"] == "LEGACY":
            if isinstance(claims, PreparedCursorClaims):
                raise DatasetChangedError()
        else:
            prepared = await read_prepared(
                session,
                claims,
                control,
                now,
                deadline,
                continuation=query.cursor is not None,
                explicit_range=query.start is not None,
            )
            claims = prepared.claims
        end = min(claims.next_open_at + claims.page_size * claims.timeframe.span, claims.result_end)
        result = (
            prepared.result
            if prepared is not None
            else await read_indicators(
                session,
                claims.base,
                claims.quote,
                claims.timeframe,
                CandleWindow(claims.calculation_start, claims.calculation_end),
                CandleWindow(claims.next_open_at, end),
                claims.as_of,
                deadline,
                claims.dataset_revision if query.cursor else None,
            )
        )
        finished = await database_now(session)
        await session.execute(
            "SELECT set_config(:setting,:value,true)",
            {"setting": PRESENTED_TOKEN_SETTING, "value": who.token_hash},
        )
        valid = (
            await session.execute(
                """SELECT EXISTS(SELECT 1 FROM sessions
            WHERE token_hash=:hash AND user_id=:user
              AND idle_expires_at>:finished AND absolute_expires_at>:finished)""",
                {"hash": who.token_hash, "user": who.user_id, "finished": finished},
            )
        ).scalar_one()
        if not valid:
            raise HTTPException(401, "SESSION_EXPIRED")
        if prepared is not None and finished >= prepared.generation["expires_at"]:
            if query.cursor:
                raise DatasetChangedError()
            raise PreparedNotReadyError()
        check_expiry(claims, finished)
    next_claims = claims.model_copy(
        update={"dataset_revision": result.revision, "next_open_at": end}
    )
    next_cursor = (
        issue(next_claims, keys, who.user_id, who.token_hash) if end < claims.result_end else None
    )
    target = None
    if result.refresh_first is not None and result.refresh_first >= retention_cutoff(now):
        target = RefreshTarget(
            base=claims.base,
            quote=claims.quote,
            timeframe=claims.timeframe,
            start=result.refresh_first,
            end=min(result.refresh_first + 1000 * claims.timeframe.span, claims.calculation_end),
        )
    rows = [
        IndicatorPointView(
            open_at=point.open_at,
            seed_open_at=point.seed_open_at,
            finality=point.finality.value if point.finality else None,
            values={
                name: IndicatorValueView(
                    value=value.value.as_text()
                    if isinstance(value.value, Scalar)
                    else value.value.as_parts()["amount"]
                    if value.value is not None
                    else None,
                    unit=value.value.currency if isinstance(value.value, Money) else None,
                    status=value.status.value,
                )
                for name, value in point.values.items()
            },
        )
        for point in result.points
    ]
    return IndicatorHistoryView(
        source=SOURCE,
        base=claims.base,
        quote=claims.quote,
        timeframe=claims.timeframe,
        formula_version=FORMULA_VERSION,
        dataset_revision=result.revision,
        as_of=claims.as_of,
        calculation_start=claims.calculation_start,
        calculation_end=claims.calculation_end,
        result_start=claims.result_start,
        result_end=claims.result_end,
        rows=rows,
        next_cursor=next_cursor,
        generation_id=claims.generation_id if isinstance(claims, PreparedCursorClaims) else None,
        prepared_at=prepared.generation["prepared_at"] if prepared is not None else None,
        generation_age_seconds=int((now - claims.as_of).total_seconds())
        if prepared is not None
        else None,
        refresh=RefreshView(
            required=result.refresh_first is not None,
            target=target,
            more_required=result.refresh_more,
            queue_status=result.queue_status,
            failure_code=result.failure_code,
            observed_at=now,
        ),
    )


async def _read_until_disconnect(
    query: IndicatorQuery, request: Request, who: Authenticated, deadline: float
) -> IndicatorHistoryView:
    """Join both tasks before admission is released, including repeated cancellation."""
    stopping = False

    async def disconnected() -> None:
        while not stopping:
            if (await request.receive())["type"] == "http.disconnect":
                return

    reader = asyncio.create_task(_read(query, request, who, deadline))
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((reader, watcher), return_when=asyncio.FIRST_COMPLETED)
        if watcher in done:
            watcher.result()
            raise asyncio.CancelledError()
        return reader.result()
    finally:
        # Starlette's receive wrapper can consume cancellation while finishing
        # its own task group. Do not begin another receive after it returns.
        stopping = True
        for task in (reader, watcher):
            if not task.done():
                task.cancel()
        joined = asyncio.gather(reader, watcher, return_exceptions=True)
        cancelled = False
        while not joined.done():
            try:
                await asyncio.shield(joined)
            except asyncio.CancelledError:
                # Do not interrupt the reader's bounded transaction cleanup again.
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError()


@router.get("", response_model=IndicatorHistoryView)
async def indicators(
    query: Annotated[IndicatorQuery, Query()],
    request: Request,
    who: Annotated[Authenticated, Depends(current_user)],
) -> Response:
    deadline = monotonic() + INDICATOR_SETTINGS.deadline_seconds
    budget = cast(IndicatorBudget, request.app.state.indicator_budget)
    admission = cast(RedisAdmission, request.app.state.indicator_admission)
    try:
        async with asyncio.timeout_at(deadline):
            async with budget.reserve(admission, who.user_id):
                result = await _read_until_disconnect(query, request, who, deadline)
                body = result.model_dump_json().encode()
                # Synchronous serialization cannot dispatch timeout cancellation.
                # Reject an overrun before returning a successful response.
                if monotonic() >= deadline:
                    raise TimeoutError()
                if len(body) > INDICATOR_SETTINGS.response_bytes:
                    raise HTTPException(503, "INDICATOR_RESOURCE_LIMIT")
                return Response(
                    body,
                    media_type="application/json",
                    headers={"Cache-Control": "private, no-store"},
                )
    except DatasetChangedError:
        raise HTTPException(409, "INDICATOR_DATASET_CHANGED") from None
    except CursorRejectedError:
        raise HTTPException(422, "INPUT_REJECTED") from None
    except MoneyError:
        raise HTTPException(422, "INDICATOR_NUMERIC_ERROR") from None
    except PreparedNumericError:
        raise HTTPException(422, "INDICATOR_NUMERIC_ERROR") from None
    except (PreparedNotReadyError, CheckpointCodecError):
        raise HTTPException(
            503, "INDICATOR_DATA_NOT_READY", headers={"Retry-After": "10"}
        ) from None
    except MarketDataInputError as error:
        raise HTTPException(422, error.code) from None
    except TimeoutError:
        raise HTTPException(504, "INDICATOR_DEADLINE_EXCEEDED") from None
    except InfraError:
        raise HTTPException(503, "INDICATOR_DATA_UNAVAILABLE") from None
