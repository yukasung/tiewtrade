"""Authenticated, read-only F-11 API."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from typing import cast
from uuid import UUID

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.indicators import FORMULA_VERSION, IndicatorPoint
from tiewtrade.core.market_data import (
    CandleWindow,
    Timeframe,
    advance,
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
from tiewtrade.infra.db.session import PRESENTED_TOKEN_SETTING, UserSession, indicator_read_session
from tiewtrade.infra.indicators.prepared import (
    PreparedNotReadyError,
    read_prepared,
    rollout_control,
)
from tiewtrade.infra.market_data.catalog import SOURCE
from tiewtrade.infra.market_data.indicator_reader import query_budget, read_indicators
from tiewtrade.infra.market_data.records import StoredCandle
from tiewtrade.infra.market_data.storage import (
    database_now,
    parameters,
    require_active_pair,
    stored_rows,
)
from tiewtrade.services.api.authentication import Authenticated
from tiewtrade.services.api.indicator_http import (
    JSON_YIELD_ITEMS,
    ChunkedJSON,
    JSONFragments,
    encode_json_fragment,
)


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


@dataclass(frozen=True, slots=True)
class HistoryRead:
    view: ChunkedJSON
    claims: CursorClaims
    candles: tuple[StoredCandle, ...]
    checked_at: datetime


def _encode_points(points: tuple[IndicatorPoint, ...]) -> tuple[bytes, ...]:
    """Encode one bounded row batch away from the latency-sensitive event loop."""
    return tuple(
        encode_json_fragment(
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
        )
        for point in points
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
    lower = align_ceil(retention_cutoff(now, query.timeframe), query.timeframe)
    upper = align_floor(now, query.timeframe)
    if (query.start is None) != (query.end is None):
        raise CursorRejectedError()
    start = query.start or max(lower, advance(upper, query.timeframe, -1000))
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


async def read_history(
    query: IndicatorQuery,
    request: Request,
    who: Authenticated,
    deadline: float,
    *,
    with_candles: bool = False,
    clock: Callable[[UserSession], Awaitable[datetime]] = database_now,
    claims_override: CursorClaims | None = None,
) -> HistoryRead:
    keys = cast(KeySource, request.app.state.indicator_keys)
    engine = cast(AsyncEngine, request.app.state.indicator_engine)
    async with indicator_read_session(engine, who.user_id) as session:
        now = await clock(session)
        claims = claims_override or _claims(query, who, now, keys)
        await require_active_pair(session, claims.base, claims.quote)
        check_expiry(claims, now)
        continuation = query.cursor is not None or claims_override is not None
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
                continuation=continuation,
                explicit_range=query.start is not None,
            )
            claims = prepared.claims
        end = min(
            advance(claims.next_open_at, claims.timeframe, claims.page_size),
            claims.result_end,
        )
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
                claims.dataset_revision if continuation else None,
            )
        )
        await query_budget(session, deadline)
        candles = (
            await stored_rows(
                session,
                claims.base,
                claims.quote,
                claims.timeframe,
                CandleWindow(claims.next_open_at, end),
            )
            if with_candles
            else ()
        )
        finished = await clock(session)
        await check_read_session(session, who, finished)
        if prepared is not None and finished >= prepared.generation["expires_at"]:
            if continuation:
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
    if result.refresh_first is not None and result.refresh_first >= retention_cutoff(
        now, claims.timeframe
    ):
        target = RefreshTarget(
            base=claims.base,
            quote=claims.quote,
            timeframe=claims.timeframe,
            start=result.refresh_first,
            end=min(advance(result.refresh_first, claims.timeframe, 1000), claims.calculation_end),
        )
    rows: list[bytes] = []
    for start in range(0, len(result.points), JSON_YIELD_ITEMS):
        rows.extend(
            await asyncio.to_thread(
                _encode_points,
                result.points[start : start + JSON_YIELD_ITEMS],
            )
        )
        if monotonic() >= deadline:
            raise TimeoutError()
        await asyncio.sleep(0)
    validated = IndicatorHistoryView(
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
        rows=[],
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
    view = ChunkedJSON.from_model(validated, rows=JSONFragments(tuple(rows)))

    return HistoryRead(
        view, claims.model_copy(update={"dataset_revision": result.revision}), candles, finished
    )


async def check_read_session(
    session: UserSession, who: Authenticated, finished: datetime | None = None
) -> None:
    await session.execute(
        "SELECT set_config(:setting,:value,true)",
        {"setting": PRESENTED_TOKEN_SETTING, "value": who.token_hash},
    )
    valid = (
        await session.execute(
            """WITH checked AS MATERIALIZED (
          SELECT COALESCE(CAST(:finished AS timestamptz),clock_timestamp()) AS finished)
        SELECT EXISTS(SELECT 1 FROM sessions AS s,checked
        WHERE s.token_hash=:hash AND s.user_id=:user
          AND s.idle_expires_at>checked.finished AND s.absolute_expires_at>checked.finished)""",
            {
                "hash": who.token_hash,
                "user": who.user_id,
                "finished": finished,
            },
        )
    ).scalar_one()
    if not valid:
        raise HTTPException(401, "SESSION_EXPIRED")
