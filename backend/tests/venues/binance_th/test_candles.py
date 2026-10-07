import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from tests.venues.binance_th.conftest import FakeClock, RecordingGuard, transport_for
from tiewtrade import venues
from tiewtrade.core.market_data import CandleFinality, Timeframe
from tiewtrade.venues.binance_th.candles import CANDLES_COST, BinanceThCandles
from tiewtrade.venues.binance_th.rate_limit import IpWeightLimiter, WeightWindow
from tiewtrade.venues.errors import VenueRateLimitedError
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.symbols import Symbol


@pytest.mark.parametrize("tf", list(Timeframe))
@pytest.mark.parametrize("kind", ["SITE", "GLOBAL"])
async def test_public_candles_explicit_bounds_cost_and_unknown_finality(
    tf: Timeframe, kind: str
) -> None:
    start = datetime(2026, 10, 7, tzinfo=UTC)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    millis = (start - epoch) // timedelta(milliseconds=1)
    end_ms = millis + tf.span // timedelta(milliseconds=1)
    guard = RecordingGuard()
    calls: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert "X-MBX-APIKEY" not in request.headers
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(
                200,
                json={
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "type": kind,
                        }
                    ]
                },
            )
        assert request.url.params["startTime"] == str(millis)
        assert request.url.params["endTime"] == str(end_ms - 1)
        assert request.url.params["limit"] == "1000"
        assert request.url.params["interval"] == tf.value
        return httpx.Response(
            200, json=[[millis, "2", "3", "1", "2", "0", end_ms - 1, "0", 0, "0", "0", "0"]]
        )

    source = BinanceThCandles(transport_for(reply, guard=guard), clock=FakeClock())
    page = await source.fetch_candles(Symbol("BTC", "USDT"), tf, start, start + tf.span, 1000)
    assert page.candles[0].finality is CandleFinality.UNCONFIRMED
    assert page.candles[0].end_at == start + tf.span
    assert guard.reserved[-1] == CANDLES_COST == CallCost(weight=1, orders=0)
    assert len(calls) == 2


async def test_reservation_floor_is_atomic_and_headers_do_not_refund() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    limiter = IpWeightLimiter(
        clock=lambda: now,
        windows=[WeightWindow(20, timedelta(seconds=10))],
        reservation_weight_floor=10,
    )
    await limiter.reserve(CallCost(weight=1))
    limiter.observe_used_weight(span=timedelta(seconds=10), used=1, at=now)
    await limiter.reserve(CallCost(weight=1))
    with pytest.raises(VenueRateLimitedError):
        await limiter.reserve(CallCost(weight=1))


async def test_factory_reserves_ten_per_call_with_one_shared_limiter() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(
                200,
                json={
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "type": "GLOBAL",
                        }
                    ]
                },
            )
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        source = venues.live_candle_source(
            client=client, clock=lambda: now, timeout=timedelta(seconds=5)
        )
        for _ in range(99):
            await source.fetch_candles(
                Symbol("BTC", "USDT"), Timeframe.M1, now, now + timedelta(minutes=1), 1000
            )
        with pytest.raises(VenueRateLimitedError):
            await source.fetch_candles(
                Symbol("BTC", "USDT"), Timeframe.M1, now, now + timedelta(minutes=1), 1000
            )
    assert len(calls) == 100


async def test_submillisecond_bounds_preserve_exact_half_open_membership() -> None:
    now = datetime(1970, 1, 1, tzinfo=UTC)
    calls: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(
                200,
                json={
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "type": "GLOBAL",
                        }
                    ]
                },
            )
        assert request.url.params["startTime"] == "1"
        assert request.url.params["endTime"] == "60000"
        return httpx.Response(
            200, json=[[60000, "2", "3", "1", "2", "0", 119999, "0", 0, "0", "0", "0"]]
        )

    source = BinanceThCandles(transport_for(reply), clock=FakeClock())
    page = await source.fetch_candles(
        Symbol("BTC", "USDT"),
        Timeframe.M1,
        now + timedelta(microseconds=1),
        now + timedelta(minutes=1, microseconds=1),
        1,
    )
    assert len(calls) == 2
    assert page.candles[0].open_at == now + timedelta(minutes=1)
    assert page.window.start == now + timedelta(microseconds=1)
    assert page.window.end == now + timedelta(minutes=1, microseconds=1)


@pytest.mark.parametrize(
    "name",
    [
        "03-btc-usdt-1m",
        "04-btc-usdt-1d",
        "05-btc-thb-site-1m",
        "06-boundary-exact",
        "07-boundary-start-plus-one",
        "08-boundary-end-minus-one",
        "09-max-limit-1000",
        "12-btc-usdt-5m",
        "13-btc-usdt-15m",
        "14-btc-usdt-1h",
        "15-btc-usdt-4h",
    ],
)
async def test_saved_public_fixture_contract(name: str) -> None:
    root = Path(__file__).parent / "fixtures"
    recorded = json.loads((root / f"{name}.json").read_text())
    discovery = json.loads((root / "02-exchange-info.json").read_text())
    params = recorded["params"]
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    symbol = Symbol("BTC", "THB" if params["symbol"] == "BTCTHB" else "USDT")

    def reply(request: httpx.Request) -> httpx.Response:
        fixture = discovery if request.url.path.endswith("exchangeInfo") else recorded
        return httpx.Response(fixture["status"], text=fixture["body"], headers=fixture["headers"])

    source = BinanceThCandles(transport_for(reply), clock=FakeClock())
    page = await source.fetch_candles(
        symbol,
        Timeframe(params["interval"]),
        epoch + timedelta(milliseconds=int(params["startTime"])),
        epoch + timedelta(milliseconds=int(params["endTime"]) + 1),
        int(params["limit"]),
    )
    assert len(page.candles) == len(json.loads(recorded["body"]))
    assert all(c.finality is CandleFinality.UNCONFIRMED for c in page.candles)


@pytest.mark.parametrize(
    "payload",
    [{}, [None], [[0] * 11], [[True, "2", "3", "1", "2", "0", 59999, "0", 0, "0", "0", "0"]]],
)
async def test_malformed_candle_payload_is_fixed_protocol_error(payload: object) -> None:
    now = datetime(1970, 1, 1, tzinfo=UTC)

    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(
                200,
                json={
                    "symbols": [
                        {
                            "symbol": "BTCUSDT",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDT",
                            "type": "GLOBAL",
                        }
                    ]
                },
            )
        return httpx.Response(200, json=payload)

    from tiewtrade.venues.errors import VenueProtocolError

    with pytest.raises(VenueProtocolError):
        await BinanceThCandles(transport_for(reply), clock=FakeClock()).fetch_candles(
            Symbol("BTC", "USDT"), Timeframe.M1, now, now + timedelta(minutes=1), 1000
        )


@pytest.mark.parametrize("name", ["10-over-limit-1001", "11-unknown-symbol"])
async def test_recorded_public_failures_use_existing_transport_mapping(name: str) -> None:
    from tiewtrade.venues.binance_th.endpoints import Endpoint
    from tiewtrade.venues.errors import VenueError

    recorded = json.loads((Path(__file__).parent / "fixtures" / f"{name}.json").read_text())

    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            recorded["status"], text=recorded["body"], headers=recorded["headers"]
        )

    with pytest.raises(VenueError):
        await transport_for(reply).get(
            Endpoint.KLINES,
            cost=CANDLES_COST,
            params={str(key): str(value) for key, value in recorded["params"].items()},
        )


async def test_no_representable_open_time_returns_empty_without_discovery_or_budget() -> None:
    clock = FakeClock()
    guard = RecordingGuard()
    calls: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("empty millisecond grid must not use HTTP")

    source = BinanceThCandles(transport_for(reply, guard=guard), clock=clock)
    page = await source.fetch_candles(
        Symbol("BTC", "USDT"),
        Timeframe.M1,
        clock.now + timedelta(microseconds=1),
        clock.now + timedelta(microseconds=2),
        1000,
    )
    assert page.candles == ()
    assert page.received_at == clock.now
    assert calls == []
    assert guard.reserved == []
