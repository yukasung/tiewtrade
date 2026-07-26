from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime

import pytest
from aiohttp import WSMsgType

from tiewtrade.integrations.binance.kline_parser import BinanceMarketDataPayloadError
from tiewtrade.integrations.binance.public_endpoints import BinancePublicEndpoints
from tiewtrade.integrations.binance.public_market_data import BinancePublicMarketData
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.trading.session_config import MarketType


class FakeResponse:
    def __init__(self, *, status: int = 200, payload: object = None) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeMessage:
    def __init__(self, payload: object) -> None:
        self.type = WSMsgType.TEXT
        self.data = json.dumps(payload)


class FakeWebSocket:
    def __init__(self, payloads: Iterable[object]) -> None:
        self._messages = iter(FakeMessage(payload) for payload in payloads)

    async def __aenter__(self) -> FakeWebSocket:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def __aiter__(self) -> AsyncIterator[FakeMessage]:
        return self

    async def __anext__(self) -> FakeMessage:
        try:
            return next(self._messages)
        except StopIteration as error:
            raise StopAsyncIteration from error


class FakeSession:
    def __init__(
        self,
        *,
        rest_pages: Iterable[FakeResponse] = (),
        websocket_payloads: Iterable[object] = (),
    ) -> None:
        self._rest_pages = iter(rest_pages)
        self._websocket_payloads = tuple(websocket_payloads)
        self.requests: list[tuple[str, dict[str, str | int]]] = []
        self.websocket_urls: list[str] = []
        self.close_count = 0

    def get(self, url: str, *, params: dict[str, str | int]) -> FakeResponse:
        self.requests.append((url, params))
        return next(self._rest_pages)

    def ws_connect(self, url: str) -> FakeWebSocket:
        self.websocket_urls.append(url)
        return FakeWebSocket(self._websocket_payloads)

    async def close(self) -> None:
        self.close_count += 1


def config(*, timeframe: str = "5m") -> MarketDataConfig:
    return MarketDataConfig(symbol="BTCUSDT", timeframe=timeframe)


def rest_kline(minute: int) -> list[object]:
    return [
        1767225600000 + minute * 60_000,
        "100.10",
        "102.20",
        "99.90",
        "101.30",
        "12.50",
    ]


def websocket_kline(*, closed: bool) -> dict[str, object]:
    return {
        "s": "BTCUSDT",
        "k": {
            "t": 1767225600000,
            "s": "BTCUSDT",
            "i": "5m",
            "o": "100.10",
            "h": "102.20",
            "l": "99.90",
            "c": "101.30",
            "v": "12.50",
            "x": closed,
        },
    }


def source_with(
    *,
    rest_pages: Iterable[FakeResponse] = (),
    websocket_payloads: Iterable[object] = (),
) -> tuple[BinancePublicMarketData, FakeSession]:
    session = FakeSession(
        rest_pages=rest_pages,
        websocket_payloads=websocket_payloads,
    )
    return (
        BinancePublicMarketData(
            BinancePublicEndpoints.for_market_type(MarketType.SPOT), session=session
        ),
        session,
    )


async def collect(source: BinancePublicMarketData) -> tuple[object, ...]:
    return tuple([candle async for candle in source.stream_completed(config())])


def test_load_recent_requests_and_returns_requested_completed_candle_count() -> None:
    source, session = source_with(
        rest_pages=[
            FakeResponse(payload=[rest_kline(-5), rest_kline(0), rest_kline(5)])
        ]
    )

    candles = asyncio.run(
        source.load_recent(
            config(),
            count=3,
            completed_before=datetime(2026, 1, 1, 0, 12, tzinfo=UTC),
        )
    )

    assert [candle.open_time for candle in candles] == [
        datetime(2025, 12, 31, 23, 55, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    ]
    assert session.requests[0][1] == {
        "symbol": "BTCUSDT",
        "interval": "5m",
        "endTime": 1767226199999,
        "limit": 3,
    }


def test_load_recent_excludes_unfinished_candles_from_response() -> None:
    source, _ = source_with(
        rest_pages=[
            FakeResponse(payload=[rest_kline(0), rest_kline(5), rest_kline(10)])
        ]
    )

    candles = asyncio.run(
        source.load_recent(
            config(),
            count=3,
            completed_before=datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
        )
    )

    assert [candle.open_time for candle in candles] == [
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    ]


def test_load_range_paginates_and_returns_ascending_completed_candles() -> None:
    source, session = source_with(
        rest_pages=[
            FakeResponse(payload=[rest_kline(0), rest_kline(5)]),
            FakeResponse(payload=[rest_kline(10)]),
        ]
    )

    candles = asyncio.run(
        source.load_range(
            config(),
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        )
    )

    assert [candle.open_time for candle in candles] == [
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
    ]
    assert [request[1]["startTime"] for request in session.requests] == [
        1767225600000,
        1767226200000,
    ]


def test_load_range_excludes_candle_closing_after_non_aligned_end() -> None:
    source, session = source_with(
        rest_pages=[
            FakeResponse(payload=[rest_kline(0), rest_kline(5), rest_kline(10)])
        ]
    )

    candles = asyncio.run(
        source.load_range(
            config(),
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, 0, 12, tzinfo=UTC),
        )
    )

    assert [candle.open_time for candle in candles] == [
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
    ]
    assert session.requests[0][1]["endTime"] == 1767226199999


@pytest.mark.parametrize(
    ("pages", "request_count", "candle_count"),
    [([[]], 1, 0), ([[rest_kline(0)], [rest_kline(0)]], 2, 1)],
)
def test_load_range_stops_on_empty_or_nonadvancing_page(
    pages: list[list[object]], request_count: int, candle_count: int
) -> None:
    source, session = source_with(
        rest_pages=[FakeResponse(payload=page) for page in pages]
    )

    candles = asyncio.run(
        source.load_range(
            config(),
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        )
    )

    assert len(session.requests) == request_count
    assert len(candles) == candle_count


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(status=503, payload=[]),
        FakeResponse(payload={"code": -1121, "msg": "invalid symbol"}),
        FakeResponse(payload=ValueError("malformed JSON")),
    ],
)
def test_rest_failures_raise_stable_payload_error(response: FakeResponse) -> None:
    source, _ = source_with(rest_pages=[response])

    with pytest.raises(BinanceMarketDataPayloadError, match="invalid Binance"):
        asyncio.run(
            source.load_recent(
                config(),
                count=1,
                completed_before=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )


def test_stream_completed_ignores_open_updates_and_uses_symbol_stream_url() -> None:
    source, session = source_with(
        websocket_payloads=[websocket_kline(closed=False), websocket_kline(closed=True)]
    )

    candles = asyncio.run(collect(source))

    assert len(candles) == 1
    assert candles[0].open_time == datetime(2026, 1, 1, tzinfo=UTC)
    assert session.websocket_urls == [
        "wss://data-stream.binance.vision/ws/btcusdt@kline_5m"
    ]


def test_load_recent_rejects_unsupported_interval_before_rest_request() -> None:
    source, session = source_with(rest_pages=[FakeResponse(payload=[])])

    with pytest.raises(BinanceMarketDataPayloadError, match="unsupported Binance"):
        asyncio.run(
            source.load_recent(
                config(timeframe="7m"),
                count=1,
                completed_before=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )

    assert session.requests == []


def test_load_range_rejects_unsupported_interval_before_rest_request() -> None:
    source, session = source_with(rest_pages=[FakeResponse(payload=[])])

    with pytest.raises(BinanceMarketDataPayloadError, match="unsupported Binance"):
        asyncio.run(
            source.load_range(
                config(timeframe="7m"),
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 1, 1, 0, 7, tzinfo=UTC),
            )
        )

    assert session.requests == []


def test_stream_completed_rejects_unsupported_interval_before_ws_handshake() -> None:
    source, session = source_with(websocket_payloads=[websocket_kline(closed=True)])

    async def collect_invalid_stream() -> tuple[object, ...]:
        return tuple(
            [candle async for candle in source.stream_completed(config(timeframe="7m"))]
        )

    with pytest.raises(BinanceMarketDataPayloadError, match="unsupported Binance"):
        asyncio.run(collect_invalid_stream())

    assert session.websocket_urls == []


def test_close_is_idempotent() -> None:
    source, session = source_with()

    asyncio.run(source.close())
    asyncio.run(source.close())

    assert session.close_count == 1
