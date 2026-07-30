from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Iterable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

import aiohttp
import pytest
from aiohttp import WSMsgType

from tiewtrade.integrations.binance.public_endpoints import BinancePublicEndpoints
from tiewtrade.integrations.binance.public_market_data import BinancePublicMarketData
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.market_data.runtime import MarketDataRuntime
from tiewtrade.market_data.runtime_state import (
    MarketDataRuntimeReason,
    MarketDataRuntimeState,
)
from tiewtrade.market_data.source_errors import (
    MarketDataFailureKind,
    MarketDataFatalError,
    MarketDataRateLimitError,
    MarketDataRetryableError,
    MarketDataTimeoutError,
)
from tiewtrade.trading.session_config import MarketType

_T = TypeVar("_T")


class FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: object = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeMessage:
    def __init__(
        self,
        payload: object,
        *,
        message_type: WSMsgType = WSMsgType.TEXT,
    ) -> None:
        self.type = message_type
        self.data = (
            payload
            if message_type is WSMsgType.ERROR or isinstance(payload, str)
            else json.dumps(payload)
        )


class FakeWebSocket:
    def __init__(
        self,
        payloads: Iterable[object],
        *,
        failure: Exception | None = None,
    ) -> None:
        self._messages = iter(
            payload if isinstance(payload, FakeMessage) else FakeMessage(payload)
            for payload in payloads
        )
        self._failure = failure

    async def __aenter__(self) -> FakeWebSocket:
        if self._failure is not None:
            raise self._failure
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
        websocket_failure: Exception | None = None,
    ) -> None:
        self._rest_pages = iter(rest_pages)
        self._websocket_payloads = tuple(websocket_payloads)
        self._websocket_failure = websocket_failure
        self.requests: list[tuple[str, dict[str, str | int]]] = []
        self.websocket_urls: list[str] = []
        self.close_count = 0

    def get(self, url: str, *, params: dict[str, str | int]) -> FakeResponse:
        self.requests.append((url, params))
        return next(self._rest_pages)

    def ws_connect(self, url: str) -> FakeWebSocket:
        self.websocket_urls.append(url)
        return FakeWebSocket(
            self._websocket_payloads,
            failure=self._websocket_failure,
        )

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
    websocket_failure: Exception | None = None,
) -> tuple[BinancePublicMarketData, FakeSession]:
    session = FakeSession(
        rest_pages=rest_pages,
        websocket_payloads=websocket_payloads,
        websocket_failure=websocket_failure,
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


def test_load_recent_rejects_count_above_page_limit_before_request() -> None:
    source, session = source_with()

    with pytest.raises(ValueError, match="count must not exceed 1000"):
        asyncio.run(
            source.load_recent(
                config(),
                count=1_001,
                completed_before=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )

    assert session.requests == []


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


def load_one(source: BinancePublicMarketData) -> None:
    asyncio.run(
        source.load_recent(
            config(),
            count=1,
            completed_before=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )


def test_429_preserves_delta_seconds_retry_after() -> None:
    source, _ = source_with(
        rest_pages=[
            FakeResponse(
                status=429,
                headers={"Retry-After": "45"},
            )
        ]
    )

    with pytest.raises(MarketDataRateLimitError) as captured:
        load_one(source)

    assert captured.value.retry_after == timedelta(seconds=45)


def test_429_preserves_http_date_retry_after() -> None:
    source, _ = source_with(
        rest_pages=[
            FakeResponse(
                status=429,
                headers={"Retry-After": "Thu, 01 Jan 2026 00:01:00 GMT"},
            )
        ]
    )

    with pytest.raises(MarketDataRateLimitError) as captured:
        load_one(source)

    assert captured.value.retry_after == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)


@pytest.mark.parametrize("header", [None, "", "not-a-date", "-1"])
def test_429_without_valid_retry_after_uses_no_directive(
    header: str | None,
) -> None:
    headers = {} if header is None else {"Retry-After": header}
    source, _ = source_with(rest_pages=[FakeResponse(status=429, headers=headers)])

    with pytest.raises(MarketDataRateLimitError) as captured:
        load_one(source)

    assert captured.value.retry_after is None


@pytest.mark.parametrize("status", [418, 429])
def test_rate_limit_statuses_raise_rate_limit_error(status: int) -> None:
    source, _ = source_with(rest_pages=[FakeResponse(status=status)])

    with pytest.raises(MarketDataRateLimitError) as captured:
        load_one(source)

    assert captured.value.kind is MarketDataFailureKind.PROTOCOL


def test_400_raises_fatal_error() -> None:
    source, _ = source_with(rest_pages=[FakeResponse(status=400)])

    with pytest.raises(MarketDataFatalError) as captured:
        load_one(source)

    assert captured.value.kind is MarketDataFailureKind.PROTOCOL


def test_503_raises_retryable_error() -> None:
    source, _ = source_with(rest_pages=[FakeResponse(status=503)])

    with pytest.raises(MarketDataRetryableError) as captured:
        load_one(source)

    assert captured.value.kind is MarketDataFailureKind.PROTOCOL


def test_transport_failure_raises_retryable_error() -> None:
    source, _ = source_with(
        rest_pages=[FakeResponse(payload=aiohttp.ClientConnectionError("offline"))]
    )

    with pytest.raises(MarketDataRetryableError) as captured:
        load_one(source)

    assert captured.value.kind is MarketDataFailureKind.TRANSPORT


def test_timeout_failure_preserves_timeout_action() -> None:
    source, _ = source_with(
        rest_pages=[FakeResponse(payload=TimeoutError("timed out"))]
    )

    with pytest.raises(MarketDataTimeoutError) as captured:
        load_one(source)

    assert captured.value.kind is MarketDataFailureKind.TRANSPORT


class ImmediateRuntimeScheduler:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return datetime(2026, 1, 1, 0, 30, tzinfo=UTC)

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    async def wait_for(self, awaitable: Awaitable[_T], timeout: float) -> _T:
        return await awaitable


class RejectingWarmUpSink:
    async def warm_up(
        self,
        candles: tuple[Candle, ...],
        *,
        received_at: datetime,
    ) -> None:
        raise AssertionError("timed-out source must not reach the sink")

    async def process_completed(self, candle: Candle, *, received_at: datetime) -> None:
        raise AssertionError("timed-out source must not reach the sink")


def test_binance_timeout_exhaustion_remains_warm_up_timeout_in_runtime() -> None:
    source, session = source_with(
        rest_pages=[FakeResponse(payload=TimeoutError("timed out")) for _ in range(4)]
    )
    scheduler = ImmediateRuntimeScheduler()
    runtime = MarketDataRuntime(
        config=config(),
        warm_up_count=1,
        source=source,
        sink=RejectingWarmUpSink(),
        scheduler=scheduler,
    )

    asyncio.run(runtime.run())

    assert len(session.requests) == 4
    assert scheduler.sleeps == [1.0, 2.0, 4.0]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.WARM_UP_TIMEOUT


@pytest.mark.parametrize(
    "payload_error",
    [
        aiohttp.ContentTypeError(request_info=None, history=()),
        aiohttp.ClientPayloadError("invalid response body"),
    ],
)
def test_rest_payload_client_error_raises_fatal_error(
    payload_error: aiohttp.ClientError,
) -> None:
    source, _ = source_with(rest_pages=[FakeResponse(payload=payload_error)])

    with pytest.raises(MarketDataFatalError) as captured:
        load_one(source)

    assert captured.value.kind is MarketDataFailureKind.PAYLOAD


@pytest.mark.parametrize(
    "payload",
    [{"code": -1121, "msg": "invalid symbol"}, ValueError("bad JSON")],
)
def test_invalid_rest_payload_raises_fatal_error(payload: object) -> None:
    source, _ = source_with(rest_pages=[FakeResponse(payload=payload)])

    with pytest.raises(MarketDataFatalError) as captured:
        load_one(source)

    assert captured.value.kind is MarketDataFailureKind.PAYLOAD


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


def test_websocket_connection_failure_raises_retryable_error() -> None:
    source, _ = source_with(websocket_failure=aiohttp.ClientConnectionError("offline"))

    with pytest.raises(MarketDataRetryableError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.TRANSPORT


def test_websocket_handshake_timeout_preserves_timeout_action() -> None:
    source, _ = source_with(websocket_failure=TimeoutError("timed out"))

    with pytest.raises(MarketDataTimeoutError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.TRANSPORT


def test_websocket_error_message_raises_retryable_error() -> None:
    source, _ = source_with(
        websocket_payloads=[
            FakeMessage(
                aiohttp.ClientConnectionError("offline"),
                message_type=WSMsgType.ERROR,
            )
        ]
    )

    with pytest.raises(MarketDataRetryableError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.TRANSPORT


def test_websocket_timeout_message_preserves_timeout_action() -> None:
    source, _ = source_with(
        websocket_payloads=[
            FakeMessage(TimeoutError("timed out"), message_type=WSMsgType.ERROR)
        ]
    )

    with pytest.raises(MarketDataTimeoutError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.TRANSPORT


@pytest.mark.parametrize(
    ("header", "expected_retry_after"),
    [
        ("45", timedelta(seconds=45)),
        (
            "Thu, 01 Jan 2026 00:01:00 GMT",
            datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        ),
    ],
)
def test_websocket_429_preserves_retry_after(
    header: str,
    expected_retry_after: timedelta | datetime,
) -> None:
    source, _ = source_with(
        websocket_failure=websocket_handshake_error(
            429,
            headers={"Retry-After": header},
        )
    )

    with pytest.raises(MarketDataRateLimitError) as captured:
        asyncio.run(collect(source))

    assert captured.value.retry_after == expected_retry_after


@pytest.mark.parametrize("status", [418, 429])
def test_websocket_rate_limit_without_header_uses_no_directive(status: int) -> None:
    source, _ = source_with(websocket_failure=websocket_handshake_error(status))

    with pytest.raises(MarketDataRateLimitError) as captured:
        asyncio.run(collect(source))

    assert captured.value.retry_after is None
    assert captured.value.kind is MarketDataFailureKind.PROTOCOL


def test_websocket_400_handshake_raises_fatal_error() -> None:
    source, _ = source_with(websocket_failure=websocket_handshake_error(400))

    with pytest.raises(MarketDataFatalError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.PROTOCOL


def test_websocket_503_handshake_raises_retryable_error() -> None:
    source, _ = source_with(websocket_failure=websocket_handshake_error(503))

    with pytest.raises(MarketDataRetryableError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.PROTOCOL


@pytest.mark.parametrize("payload", ["not JSON", {"unexpected": "payload"}])
def test_invalid_websocket_payload_raises_fatal_error(payload: object) -> None:
    source, _ = source_with(websocket_payloads=[payload])

    with pytest.raises(MarketDataFatalError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.PAYLOAD


def test_unexpected_websocket_message_is_fatal_protocol_failure() -> None:
    source, _ = source_with(
        websocket_payloads=[
            FakeMessage("binary", message_type=WSMsgType.BINARY),
        ]
    )

    with pytest.raises(MarketDataFatalError) as captured:
        asyncio.run(collect(source))

    assert captured.value.kind is MarketDataFailureKind.PROTOCOL


@pytest.mark.parametrize(
    "failure",
    [
        MarketDataRetryableError(
            "retryable",
            kind=MarketDataFailureKind.TRANSPORT,
        ),
        MarketDataRateLimitError("rate limited", retry_after=None),
        MarketDataFatalError(
            "fatal",
            kind=MarketDataFailureKind.PAYLOAD,
        ),
    ],
)
def test_websocket_domain_error_is_not_remapped(failure: Exception) -> None:
    source, _ = source_with(websocket_failure=failure)

    with pytest.raises(type(failure)) as captured:
        asyncio.run(collect(source))

    assert captured.value is failure


def websocket_handshake_error(
    status: int,
    *,
    headers: dict[str, str] | None = None,
) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=None,
        history=(),
        status=status,
        headers=headers,
    )


def test_close_does_not_close_injected_session() -> None:
    source, session = source_with()

    asyncio.run(source.close())
    asyncio.run(source.close())

    assert session.close_count == 0


def test_owned_session_uses_bounded_timeout_and_closes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(rest_pages=[FakeResponse(payload=[rest_kline(0)])])
    configured_timeouts: list[aiohttp.ClientTimeout | None] = []

    def session_factory(*, timeout: aiohttp.ClientTimeout | None = None) -> FakeSession:
        configured_timeouts.append(timeout)
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", session_factory)
    source = BinancePublicMarketData(
        BinancePublicEndpoints.for_market_type(MarketType.SPOT)
    )

    asyncio.run(
        source.load_recent(
            config(),
            count=1,
            completed_before=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        )
    )
    asyncio.run(source.close())
    asyncio.run(source.close())

    assert configured_timeouts[0] is not None
    assert configured_timeouts[0].total == 30.0
    assert session.close_count == 1


class FailureThenSuccessCloseSession(FakeSession):
    async def close(self) -> None:
        self.close_count += 1
        if self.close_count == 1:
            raise RuntimeError("close failed")


def test_owned_session_close_failure_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FailureThenSuccessCloseSession(
        rest_pages=[FakeResponse(payload=[rest_kline(0)])]
    )
    monkeypatch.setattr(aiohttp, "ClientSession", lambda **_: session)
    source = BinancePublicMarketData(
        BinancePublicEndpoints.for_market_type(MarketType.SPOT)
    )
    load_one(source)

    with pytest.raises(RuntimeError, match="close failed"):
        asyncio.run(source.close())
    asyncio.run(source.close())
    asyncio.run(source.close())

    assert session.close_count == 2


class CancelThenSuccessCloseSession(FakeSession):
    def __init__(self) -> None:
        super().__init__(rest_pages=[FakeResponse(payload=[rest_kline(0)])])
        self.close_started = asyncio.Event()

    async def close(self) -> None:
        self.close_count += 1
        if self.close_count == 1:
            self.close_started.set()
            await asyncio.Event().wait()


def test_owned_session_cancelled_close_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = CancelThenSuccessCloseSession()
    monkeypatch.setattr(aiohttp, "ClientSession", lambda **_: session)
    source = BinancePublicMarketData(
        BinancePublicEndpoints.for_market_type(MarketType.SPOT)
    )

    async def exercise() -> None:
        await source.load_recent(
            config(),
            count=1,
            completed_before=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        )
        close_task = asyncio.create_task(source.close())
        await session.close_started.wait()
        close_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close_task
        await source.close()
        await source.close()

    asyncio.run(exercise())

    assert session.close_count == 2
