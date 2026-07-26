import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import aiohttp

from tiewtrade.integrations.binance.kline_parser import (
    parse_rest_kline,
    parse_websocket_kline,
)
from tiewtrade.integrations.binance.public_endpoints import (
    BinanceMarketDataPayloadError,
    BinancePublicEndpoints,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig

_INVALID_RESPONSE_MESSAGE = "invalid Binance market-data response"
_PAGE_LIMIT = 1_000


class BinancePublicMarketData:
    """Load completed public Binance candles from one selected endpoint profile."""

    def __init__(
        self,
        endpoints: BinancePublicEndpoints,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._endpoints = endpoints
        self._session = session
        self._closed = False

    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]:
        if count <= 0:
            raise ValueError("count must be positive")
        _require_utc(completed_before, name="completed_before")

        page = await self._load_rest_page(
            config,
            {"symbol": config.symbol, "interval": config.timeframe, "limit": count},
        )
        completed = sorted(
            (candle for candle in page if candle.close_time <= completed_before),
            key=lambda candle: candle.open_time,
        )
        return tuple(completed[-count:])

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        _require_utc(start, name="start")
        _require_utc(end, name="end")
        if end <= start:
            raise ValueError("end must be after start")

        candles: dict[datetime, Candle] = {}
        cursor = start
        while cursor < end:
            page = await self._load_rest_page(
                config,
                {
                    "symbol": config.symbol,
                    "interval": config.timeframe,
                    "startTime": _milliseconds(cursor),
                    "endTime": _milliseconds(end),
                    "limit": _PAGE_LIMIT,
                },
            )
            if not page:
                break

            page_candles = sorted(page, key=lambda candle: candle.open_time)
            for candle in page_candles:
                if start <= candle.open_time < end:
                    candles[candle.open_time] = candle

            next_cursor = page_candles[-1].open_time + config.interval
            if next_cursor <= cursor:
                break
            cursor = next_cursor

        return tuple(candles[open_time] for open_time in sorted(candles))

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._session is not None:
            await self._session.close()

    async def _load_rest_page(
        self, config: MarketDataConfig, params: dict[str, str | int]
    ) -> tuple[Candle, ...]:
        BinancePublicEndpoints.validate_config(config)
        session = self._network_session()
        try:
            async with session.get(
                self._endpoints.rest_klines_url, params=params
            ) as response:
                if not 200 <= response.status < 300:
                    raise ValueError
                payload = await response.json()
            if not isinstance(payload, list):
                raise ValueError
            return tuple(parse_rest_kline(item, config) for item in payload)
        except BinanceMarketDataPayloadError:
            raise
        except (aiohttp.ClientError, TimeoutError, TypeError, ValueError) as error:
            raise BinanceMarketDataPayloadError(_INVALID_RESPONSE_MESSAGE) from error

    async def _stream_completed(
        self, config: MarketDataConfig
    ) -> AsyncIterator[Candle]:
        BinancePublicEndpoints.validate_config(config)
        session = self._network_session()
        stream_url = (
            f"{self._endpoints.websocket_base_url}/"
            f"{config.symbol.lower()}@kline_{config.timeframe}"
        )
        try:
            async with session.ws_connect(stream_url) as websocket:
                async for message in websocket:
                    if message.type is aiohttp.WSMsgType.TEXT:
                        payload = json.loads(message.data)
                        candle = parse_websocket_kline(payload, config)
                        if candle is not None:
                            yield candle
                    elif message.type in {
                        aiohttp.WSMsgType.CLOSE,
                        aiohttp.WSMsgType.CLOSED,
                        aiohttp.WSMsgType.CLOSING,
                    }:
                        return
                    else:
                        raise ValueError
        except BinanceMarketDataPayloadError:
            raise
        except (
            aiohttp.ClientError,
            TimeoutError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as error:
            raise BinanceMarketDataPayloadError(_INVALID_RESPONSE_MESSAGE) from error

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        return self._stream_completed(config)

    def _network_session(self) -> aiohttp.ClientSession:
        if self._closed:
            raise RuntimeError("Binance public market-data source is closed")
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session


def _milliseconds(value: datetime) -> int:
    return int(value.timestamp() * 1_000)


def _require_utc(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must use UTC")
