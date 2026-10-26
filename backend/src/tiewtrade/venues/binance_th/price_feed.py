"""Public feed composition and reconnect policy; REST only serves recovery."""

import asyncio
import random
from collections.abc import AsyncIterator

from tiewtrade.core.realtime_prices import QuoteObservation
from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.mapping import market_symbol
from tiewtrade.venues.binance_th.prices import LATEST_PRICE_COST
from tiewtrade.venues.binance_th.stream_mapping import quote_from_trades
from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport
from tiewtrade.venues.binance_th.transport import BinanceThTransport
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedEvent
from tiewtrade.venues.symbols import Symbol


class BinanceThPriceFeed:
    def __init__(
        self, transport: BinanceThTransport, stream_transport: BinanceThStreamTransport
    ) -> None:
        self._transport = transport
        self._stream_transport = stream_transport
        self._generation = 0

    async def snapshot(self, symbol: Symbol) -> QuoteObservation:
        response = await self._transport.get(
            Endpoint.TRADES,
            cost=LATEST_PRICE_COST,
            params={"symbol": market_symbol(symbol), "limit": "1"},
        )
        return quote_from_trades(
            symbol=symbol, payload=response.payload, received_at=response.received_at
        )

    async def events(self, symbols: tuple[Symbol, ...]) -> AsyncIterator[FeedEvent]:
        if (
            not symbols
            or len(set(symbols)) != len(symbols)
            or any(pair.quote != "USDT" for pair in symbols)
        ):
            raise ValueError("unsupported public feed symbols")
        attempt = 0
        while True:
            self._generation += 1
            connected_at = None
            failure = "VENUE_UNAVAILABLE"
            retry_after = None
            async for event in self._stream_transport.connection(
                symbols, generation=self._generation
            ):
                if isinstance(event, FeedConnected):
                    connected_at = asyncio.get_running_loop().time()
                if isinstance(event, FeedDisconnected):
                    failure = event.failure_code
                    retry_after = event.retry_after
                yield event
            if connected_at is not None and asyncio.get_running_loop().time() - connected_at >= 60:
                attempt = 0
            delay = random.uniform(0, min(30, 2 ** min(attempt, 5)))
            if retry_after is not None:
                delay = max(delay, retry_after.total_seconds())
            if failure == "VENUE_PROTOCOL":
                delay = max(delay, 30)
            attempt += 1
            await asyncio.sleep(delay)
