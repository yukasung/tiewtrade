import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

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
from tiewtrade.market_data.source_errors import (
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
    RetryAfter,
)

_INVALID_RESPONSE_MESSAGE = "invalid Binance market-data response"
_PAGE_LIMIT = 1_000
_HTTP_REQUEST_TIMEOUT_SECONDS = 30.0


def _parse_retry_after(value: str | None) -> RetryAfter | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        seconds = int(normalized)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(normalized)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC)
    if seconds < 0:
        return None
    return timedelta(seconds=seconds)


def _raise_for_http_status(
    status: int,
    *,
    retry_after: str | None,
) -> None:
    if status in {418, 429}:
        raise MarketDataRateLimitError(
            "Binance market data is rate limited",
            retry_after=_parse_retry_after(retry_after),
        )
    if 500 <= status < 600:
        raise MarketDataRetryableError("Binance market-data service is unavailable")
    if not 200 <= status < 300:
        raise MarketDataFatalError("Binance rejected the market-data request")


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
        self._owns_session = session is None
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
            {
                "symbol": config.symbol,
                "interval": config.timeframe,
                "endTime": _last_completed_millisecond(
                    completed_before, interval=config.interval
                ),
                "limit": count,
            },
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
                    "endTime": _last_completed_millisecond(
                        end, interval=config.interval
                    ),
                    "limit": _PAGE_LIMIT,
                },
            )
            if not page:
                break

            page_candles = sorted(page, key=lambda candle: candle.open_time)
            for candle in page_candles:
                if start <= candle.open_time < end and candle.close_time <= end:
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
        if self._owns_session and self._session is not None:
            await self._session.close()

    async def _load_rest_page(
        self, config: MarketDataConfig, params: dict[str, str | int]
    ) -> tuple[Candle, ...]:
        session = self._network_session()
        try:
            async with session.get(
                self._endpoints.rest_klines_url, params=params
            ) as response:
                _raise_for_http_status(
                    response.status,
                    retry_after=response.headers.get("Retry-After"),
                )
                payload = await response.json()
            if not isinstance(payload, list):
                raise ValueError
            return tuple(parse_rest_kline(item, config) for item in payload)
        except (
            MarketDataRetryableError,
            MarketDataRateLimitError,
            MarketDataFatalError,
        ):
            raise
        except (
            aiohttp.ContentTypeError,
            aiohttp.ClientPayloadError,
            BinanceMarketDataPayloadError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as error:
            raise MarketDataFatalError(_INVALID_RESPONSE_MESSAGE) from error
        except (aiohttp.ClientError, TimeoutError) as error:
            raise MarketDataRetryableError(
                "Binance market-data transport failed"
            ) from error

    async def _stream_completed(
        self, config: MarketDataConfig
    ) -> AsyncIterator[Candle]:
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
        except (
            MarketDataRetryableError,
            MarketDataRateLimitError,
            MarketDataFatalError,
        ):
            raise
        except aiohttp.ClientResponseError as error:
            _raise_for_http_status(
                error.status,
                retry_after=(
                    error.headers.get("Retry-After")
                    if error.headers is not None
                    else None
                ),
            )
            raise MarketDataRetryableError(
                "Binance market-data transport failed"
            ) from error
        except (aiohttp.ClientError, TimeoutError) as error:
            raise MarketDataRetryableError(
                "Binance market-data transport failed"
            ) from error
        except (
            BinanceMarketDataPayloadError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as error:
            raise MarketDataFatalError(_INVALID_RESPONSE_MESSAGE) from error

    def stream_completed(self, config: MarketDataConfig) -> AsyncIterator[Candle]:
        return self._stream_completed(config)

    def _network_session(self) -> aiohttp.ClientSession:
        if self._closed:
            raise RuntimeError("Binance public market-data source is closed")
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=_HTTP_REQUEST_TIMEOUT_SECONDS)
            )
        return self._session


def _milliseconds(value: datetime) -> int:
    return int(value.timestamp() * 1_000)


def _last_completed_millisecond(value: datetime, *, interval: timedelta) -> int:
    interval_milliseconds = int(interval.total_seconds() * 1_000)
    return _milliseconds(value) // interval_milliseconds * interval_milliseconds - 1


def _require_utc(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must use UTC")
