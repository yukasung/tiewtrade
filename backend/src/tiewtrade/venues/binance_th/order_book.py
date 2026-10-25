"""Public-only execution feed using the existing HTTP and WSS gateways."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import cast

from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.mapping import market_symbol, pairs_from_exchange_info
from tiewtrade.venues.binance_th.order_book_mapping import (
    capability_from_pair,
    observation_from_stream,
    snapshot_from_payload,
)
from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport, StreamFrame
from tiewtrade.venues.binance_th.transport import BinanceThTransport
from tiewtrade.venues.errors import VenueProtocolError
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.order_books import (
    DepthSnapshot,
    DepthUpdate,
    ExecutionCapability,
    ExecutionFeedData,
    ExecutionFeedEvent,
    TradeObservation,
)
from tiewtrade.venues.symbols import Symbol


class BinanceThOrderBookFeed:
    def __init__(self, transport: BinanceThTransport, stream: BinanceThStreamTransport) -> None:
        self._transport = transport
        self._stream = stream

    async def close(self) -> None:
        await self._transport.close()

    async def snapshot(self, symbol: Symbol) -> DepthSnapshot:
        response = await self._transport.get(
            Endpoint.DEPTH,
            cost=CallCost(weight=10),
            params={"symbol": market_symbol(symbol), "limit": "1000"},
        )
        return snapshot_from_payload(symbol, response.payload, response.received_at)

    async def capability(self, symbol: Symbol) -> ExecutionCapability:
        response = await self._transport.get(Endpoint.EXCHANGE_INFO, cost=CallCost(weight=10))
        row = pairs_from_exchange_info(response.payload).get(market_symbol(symbol))
        if row is None:
            raise VenueProtocolError()
        return capability_from_pair(symbol, row, response.received_at)

    async def events(
        self, symbols: tuple[Symbol, ...], *, generation: int
    ) -> AsyncGenerator[ExecutionFeedEvent, None]:
        params = tuple(
            name
            for symbol in symbols
            for name in (
                f"{market_symbol(symbol).lower()}@depth@100ms",
                f"{market_symbol(symbol).lower()}@trade",
            )
        )
        async with aclosing(
            self._stream.frames(
                params,
                generation=generation,
                decode=lambda payload, received: observation_from_stream(
                    payload, symbols, received
                ),
            )
        ) as events:
            async for event in events:
                if isinstance(event, StreamFrame):
                    yield ExecutionFeedData(
                        event.generation, cast(DepthUpdate | TradeObservation, event.value)
                    )
                else:
                    yield event
