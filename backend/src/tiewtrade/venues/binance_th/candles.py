"""Public klines adapter; REST observations have no closure proof."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from tiewtrade.core.market_data import Candle, CandleFinality, Timeframe
from tiewtrade.core.money import Money, Quantity
from tiewtrade.venues.binance_th.constraints import CONSTRAINTS_COST
from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.mapping import (
    _integer,
    _readable,
    _sequence,
    _text,
    market_symbol,
    moment_from_millis,
    pairs_from_exchange_info,
)
from tiewtrade.venues.binance_th.transport import BinanceThTransport
from tiewtrade.venues.candles import CandlePage, validate_request
from tiewtrade.venues.errors import RejectionReason, VenueProtocolError, VenueRejectedError
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.symbols import Symbol

CANDLES_COST = CallCost(weight=1, orders=0)


class BinanceThCandles:
    def __init__(self, transport: BinanceThTransport, *, clock: Callable[[], datetime]) -> None:
        self._transport = transport
        self._clock = clock
        self._known: dict[str, dict[str, object]] | None = None

    async def fetch_candles(
        self, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime, limit: int
    ) -> CandlePage:
        window = validate_request(timeframe, start, end, limit)
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        millisecond = timedelta(milliseconds=1)
        # Upstream open times are integer milliseconds. Ceiling both bounds
        # preserves exactly start <= open_time < end for arbitrary datetimes.
        start_ms = -((epoch - window.start) // millisecond)
        end_ms = -((epoch - window.end) // millisecond)
        if start_ms >= end_ms:
            return CandlePage(symbol, timeframe, window, (), self._clock())
        if self._known is None:
            discovery = await self._transport.get(Endpoint.EXCHANGE_INFO, cost=CONSTRAINTS_COST)
            self._known = pairs_from_exchange_info(discovery.payload)
        name = market_symbol(symbol)
        pair = self._known.get(name)
        if pair is None:
            raise VenueRejectedError(RejectionReason.UNKNOWN_SYMBOL)
        if (pair.get("baseAsset"), pair.get("quoteAsset")) != (symbol.base, symbol.quote):
            raise VenueProtocolError()
        if pair.get("type") not in ("SITE", "GLOBAL"):
            raise VenueProtocolError()
        response = await self._transport.get(
            Endpoint.KLINES,
            cost=CANDLES_COST,
            params={
                "symbol": name,
                "interval": timeframe.value,
                "startTime": str(start_ms),
                "endTime": str(end_ms - 1),
                "limit": str(limit),
            },
        )
        rows = _sequence(response.payload)
        if len(rows) > limit:
            raise VenueProtocolError()
        observations: list[Candle] = []
        for item in rows:
            row = _sequence(item)
            if len(row) != 12:
                raise VenueProtocolError()
            with _readable():
                observations.append(
                    Candle(
                        base=symbol.base,
                        quote=symbol.quote,
                        timeframe=timeframe,
                        open_at=moment_from_millis(row[0]),
                        end_at=moment_from_millis(_integer(row[6]) + 1),
                        open=Money.of(_text(row[1]), symbol.quote),
                        high=Money.of(_text(row[2]), symbol.quote),
                        low=Money.of(_text(row[3]), symbol.quote),
                        close=Money.of(_text(row[4]), symbol.quote),
                        volume=Quantity.of(_text(row[5]), symbol.base),
                        finality=CandleFinality.UNCONFIRMED,
                        observed_at=response.received_at,
                    )
                )
        with _readable():
            return CandlePage(symbol, timeframe, window, tuple(observations), response.received_at)
