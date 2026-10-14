import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from tests.venues.binance_th.conftest import FakeClock, RecordingGuard, transport_for
from tiewtrade import venues
from tiewtrade.core.market_data import CandleFinality, Timeframe, advance, align_floor, next_open
from tiewtrade.venues.binance_th.candles import CANDLES_COST, BinanceThCandles
from tiewtrade.venues.binance_th.rate_limit import IpWeightLimiter, WeightWindow
from tiewtrade.venues.errors import VenueProtocolError, VenueRateLimitedError
from tiewtrade.venues.limits import CallCost
from tiewtrade.venues.symbols import Symbol


def _calendar_kline(open_at: datetime, timeframe: Timeframe) -> list[object]:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    millisecond = timedelta(milliseconds=1)
    return [
        (open_at - epoch) // millisecond,
        "2",
        "3",
        "1",
        "2",
        "0",
        (next_open(open_at, timeframe) - epoch) // millisecond - 1,
        "0",
        0,
        "0",
        "0",
        "0",
    ]


@pytest.mark.parametrize("tf", list(Timeframe))
@pytest.mark.parametrize("kind", ["SITE", "GLOBAL"])
async def test_public_candles_explicit_bounds_cost_and_unknown_finality(
    tf: Timeframe, kind: str
) -> None:
    start = align_floor(datetime(2026, 10, 7, tzinfo=UTC), tf)
    end = next_open(start, tf)
    query_end = min(end, start + timedelta(days=7))
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    millis = (start - epoch) // timedelta(milliseconds=1)
    end_ms = (end - epoch) // timedelta(milliseconds=1)
    query_end_ms = (query_end - epoch) // timedelta(milliseconds=1)
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
        if tf in (Timeframe.W1, Timeframe.MN1):
            assert "endTime" not in request.url.params
            assert request.url.params["limit"] == "1"
        else:
            assert request.url.params["endTime"] == str(query_end_ms - 1)
            assert request.url.params["limit"] == "1000"
        assert request.url.params["interval"] == tf.value
        return httpx.Response(
            200, json=[[millis, "2", "3", "1", "2", "0", end_ms - 1, "0", 0, "0", "0", "0"]]
        )

    source = BinanceThCandles(transport_for(reply, guard=guard), clock=FakeClock())
    page = await source.fetch_candles(Symbol("BTC", "USDT"), tf, start, end, 1000)
    assert page.candles[0].finality is CandleFinality.UNCONFIRMED
    assert page.candles[0].end_at == end
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
        "16-btc-usdt-1w",
        "17-btc-usdt-1M",
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


async def test_oversized_source_span_rejected_before_http_or_budget() -> None:
    clock = FakeClock()
    guard = RecordingGuard()

    def reply(request: httpx.Request) -> httpx.Response:
        raise AssertionError("oversized range must not reach the transport")

    source = BinanceThCandles(transport_for(reply, guard=guard), clock=clock)
    assert source.max_request_span == timedelta(days=7)
    with pytest.raises(ValueError, match="span limit"):
        await source.fetch_candles(
            Symbol("BTC", "USDT"),
            Timeframe.H1,
            clock.now,
            clock.now + timedelta(days=7, microseconds=1),
            1000,
        )
    assert guard.reserved == []


@pytest.mark.parametrize(
    ("timeframe", "start", "end"),
    [
        (
            Timeframe.W1,
            datetime(2026, 1, 5, tzinfo=UTC),
            datetime(2026, 1, 12, tzinfo=UTC),
        ),
        (
            Timeframe.MN1,
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 2, 1, tzinfo=UTC),
        ),
    ],
)
async def test_week_and_month_resume_one_native_slot_without_end_time(
    timeframe: Timeframe, start: datetime, end: datetime
) -> None:
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
        assert request.url.params["interval"] == timeframe.value
        assert "endTime" not in request.url.params
        assert request.url.params["limit"] == "1"
        return httpx.Response(200, json=[])

    source = BinanceThCandles(transport_for(reply), clock=FakeClock())
    page = await source.fetch_candles(Symbol("BTC", "USDT"), timeframe, start, end, 1000)
    assert page.window.start == start and page.window.end == end
    assert len(calls) == 2


@pytest.mark.parametrize("timeframe", [Timeframe.W1, Timeframe.MN1])
async def test_week_and_month_reject_more_than_1000_slots_before_http(
    timeframe: Timeframe,
) -> None:
    start = datetime(2026, 1, 5 if timeframe is Timeframe.W1 else 1, tzinfo=UTC)
    end = advance(start, timeframe, 1001)
    calls: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("oversized range must not reach the transport")

    source = BinanceThCandles(transport_for(reply), clock=FakeClock())
    with pytest.raises(ValueError, match="span limit"):
        await source.fetch_candles(Symbol("BTC", "USDT"), timeframe, start, end, 1000)
    assert calls == []


@pytest.mark.parametrize("payload", [[], [[]], [[-1] * 12], [[0] * 11]])
async def test_history_discovery_rejects_empty_or_malformed_evidence(payload: list) -> None:
    source = BinanceThCandles(
        transport_for(lambda request: httpx.Response(200, json=payload), guard=RecordingGuard()),
        clock=FakeClock(),
    )
    with pytest.raises(VenueProtocolError):
        await source.earliest_open(Symbol("BTC", "USDT"), Timeframe.MN1)


@pytest.mark.parametrize("tf", [Timeframe.W1, Timeframe.MN1])
@pytest.mark.parametrize("count,limit", [(3, 1000), (1000, 1000), (3, 2)])
async def test_calendar_batch_preserves_native_rows_and_bounded_limit(
    tf: Timeframe, count: int, limit: int
) -> None:
    start = align_floor(datetime(2017, 8, 14, tzinfo=UTC), tf)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    unit = timedelta(milliseconds=1)
    expected = min(count, limit)
    payload = [_calendar_kline(advance(start, tf, i), tf) for i in range(expected)]
    discovery = json.loads((Path(__file__).parent / "fixtures/02-exchange-info.json").read_text())

    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(200, text=discovery["body"])
        assert "endTime" not in request.url.params
        assert request.url.params["startTime"] == str((start - epoch) // unit)
        assert request.url.params["limit"] == str(expected)
        return httpx.Response(200, json=payload)

    page = await BinanceThCandles(transport_for(reply), clock=FakeClock()).fetch_candles(
        Symbol("BTC", "USDT"), tf, start, advance(start, tf, count), limit
    )
    assert [c.open_at for c in page.candles] == [advance(start, tf, i) for i in range(expected)]


@pytest.mark.parametrize("tf", [Timeframe.W1, Timeframe.MN1])
@pytest.mark.parametrize("kind", ["duplicate", "reversed", "outside", "unaligned", "over_limit"])
async def test_calendar_batch_rejects_invalid_observations(tf: Timeframe, kind: str) -> None:
    start = align_floor(datetime(2026, 1, 5, tzinfo=UTC), tf)
    offsets = {
        "duplicate": [0, 0],
        "reversed": [1, 0],
        "outside": [0, 2],
        "unaligned": [0, 1],
        "over_limit": [0, 1, 2],
    }[kind]
    payload = [_calendar_kline(advance(start, tf, i), tf) for i in offsets]
    if kind == "unaligned":
        payload[0][0] += 1
    discovery = json.loads((Path(__file__).parent / "fixtures/02-exchange-info.json").read_text())

    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("exchangeInfo"):
            return httpx.Response(200, text=discovery["body"])
        return httpx.Response(200, json=payload)

    with pytest.raises(VenueProtocolError):
        await BinanceThCandles(transport_for(reply), clock=FakeClock()).fetch_candles(
            Symbol("BTC", "USDT"), tf, start, advance(start, tf, 2), 1000
        )
