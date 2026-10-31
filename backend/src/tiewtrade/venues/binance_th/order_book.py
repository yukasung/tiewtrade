"""Public-only execution feed using the existing HTTP and WSS gateways."""

from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import UTC, datetime, timedelta
from typing import cast

from tiewtrade.venues.binance_th.endpoints import Endpoint
from tiewtrade.venues.binance_th.mapping import market_symbol, pairs_from_exchange_info
from tiewtrade.venues.binance_th.order_book_mapping import (
    capability_from_pair,
    observation_from_stream,
    snapshot_from_payload,
    trade_samples_from_payload,
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
    TradeSample,
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

    async def trade_history(
        self, symbol: Symbol, *, started_at: datetime, ended_at: datetime
    ) -> tuple[TradeSample, ...]:
        if started_at.tzinfo is None or ended_at.tzinfo is None or not started_at < ended_at:
            raise ValueError("aware ordered trade-history bounds required")

        def millis(value: datetime) -> str:
            return str(
                (value.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC))
                // timedelta(milliseconds=1)
            )

        result: list[TradeSample] = []
        next_id: int | None = None
        while True:
            params = {
                "symbol": market_symbol(symbol),
                "startTime": millis(started_at),
                "endTime": millis(ended_at),
                "limit": "1000",
            }
            if next_id is not None:
                params = {"symbol": market_symbol(symbol), "fromId": str(next_id), "limit": "1000"}
            response = await self._transport.get(
                Endpoint.AGG_TRADES, cost=CallCost(weight=1), params=params
            )
            page = trade_samples_from_payload(symbol, response.payload)
            if not page:
                break
            if result and (
                page[0].aggregate_id != result[-1].aggregate_id + 1
                or page[0].first_trade_id != result[-1].last_trade_id + 1
            ):
                raise VenueProtocolError()
            for sample in page:
                if sample.occurred_at > ended_at:
                    return tuple(result)
                if sample.occurred_at >= started_at:
                    result.append(sample)
            if len(page) < 1000 or page[-1].occurred_at >= ended_at:
                break
            next_id = page[-1].aggregate_id + 1
        return tuple(result)

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
