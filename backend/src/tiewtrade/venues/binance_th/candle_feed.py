"""One shared kline connection with the existing bounded control transport."""

import asyncio
import random
from collections.abc import AsyncGenerator
from contextlib import aclosing
from datetime import datetime
from typing import cast

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import CandleSeries
from tiewtrade.venues.binance_th.candle_stream_mapping import candle_from_stream
from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport, StreamFrame
from tiewtrade.venues.candle_streams import CandleFeedEvent, FeedCandle
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected


class BinanceThCandleFeed:
    def __init__(self, transport: BinanceThStreamTransport) -> None:
        self.transport = transport
        self.generation = 0

    async def events(
        self, series: tuple[CandleSeries, ...]
    ) -> AsyncGenerator[CandleFeedEvent, None]:
        if (
            not series
            or len(set(series)) != len(series)
            or any(item.quote != "USDT" for item in series)
        ):
            raise ValueError("unsupported candle series")
        params = tuple(
            f"{item.base.lower()}{item.quote.lower()}@kline_{item.timeframe.value}"
            for item in series
        )

        def decode(payload: object, received_at: datetime) -> object:
            return candle_from_stream(payload=payload, series=series, received_at=received_at)

        attempt = 0
        while True:
            self.generation += 1
            generation = self.generation
            connected_at = None
            failure, retry_after = "VENUE_UNAVAILABLE", None
            async with aclosing(
                self.transport.frames(params, generation=generation, decode=decode)
            ) as frames:
                async for event in frames:
                    if isinstance(event, StreamFrame):
                        yield FeedCandle(generation, cast(CandleObservation, event.value))
                        continue
                    if isinstance(event, FeedConnected):
                        connected_at = asyncio.get_running_loop().time()
                    if isinstance(event, FeedDisconnected):
                        failure, retry_after = event.failure_code, event.retry_after
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
